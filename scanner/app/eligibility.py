"""Insurance eligibility check (Track B): a mock of the insurer's 270/271 eligibility exchange.

Real clinics ask the insurer "is this member covered today, and what will they owe?" before a visit
(athenaOne runs it automatically before appointments and again at check-in). Here a fictional insurer
answers deterministically from the patient's plan and member ID:
  - copay / coinsurance come from payer.PAYERS, so the copay collected at check-in matches what the mock
    insurer later puts on the remittance as patient responsibility (PR-3 / PR-2);
  - deductible and out-of-pocket progress are derived from the member ID (stable across runs);
  - members in TERMINATED had coverage end last month (demo: Michael Johnson), so the front desk sees a
    red flag before the visit instead of a denial weeks later.
No FOREIGN KEY on patient_id: clinic.reset() deletes patients with foreign keys ON; seed() clears this table.
"""
import asyncio
import hashlib
import json
import random
from datetime import date, datetime, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import clinic
from . import payer as insurer
from .events import broadcast

SCHEMA = """
CREATE TABLE IF NOT EXISTS eligibility_checks (
    id INTEGER PRIMARY KEY,
    patient_id INTEGER, appointment_id INTEGER,
    source TEXT,                -- booking | check_in | chart | batch | auto
    status TEXT,                -- active | inactive | not_found | missing_id | self_pay | no_insurance
    result TEXT,                -- JSON (the full 271-style answer)
    checked_at TEXT
);
"""

# Fictional plan details per payer_code (names are made up; copay/coinsurance come from payer.PAYERS).
PLANS = {
    "BBHP1": {"plan": "Bluebonnet Choice PPO", "type": "Commercial PPO", "deductible": 1500, "oop_max": 6000, "specialist_copay": 50},
    "PMI02": {"plan": "Prairie Mutual Silver HMO", "type": "Commercial HMO", "deductible": 2500, "oop_max": 7500, "specialist_copay": 60},
    "GCC03": {"plan": "Gulf Coast Care PPO 1000", "type": "Commercial PPO", "deductible": 1000, "oop_max": 5000, "specialist_copay": 40},
    "MCR00": {"plan": "Medicare Part B (demo)", "type": "Medicare", "deductible": 257, "oop_max": None, "specialist_copay": 0},
}
# Member IDs whose coverage ended at the end of last month (demo story: Michael Johnson, Bluebonnet).
TERMINATED = {"BB2200981"}
STALE_AFTER_DAYS = 7   # an older answer isn't trusted for a visit; re-check


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def init() -> None:
    with clinic._conn() as con:
        con.executescript(SCHEMA)


def reset() -> None:
    init()
    with clinic._conn() as con:
        con.execute("DELETE FROM eligibility_checks")


def _seed_int(member_id: str, salt: str) -> int:
    return int(hashlib.sha256(f"{salt}:{member_id}".encode()).hexdigest()[:8], 16)


# ---- the mock insurer's answer ----------------------------------------------------------
def respond(patient: dict, on: date | None = None) -> dict:
    """Build a 271-style eligibility response for this patient as of `on` (default today)."""
    on = on or date.today()
    payer = next((p for p in clinic.payers() if p["id"] == patient.get("payer_id")), None)
    member = (patient.get("member_id") or "").strip()
    base = {
        "payer": payer and payer["name"], "payer_code": payer and payer["payer_code"], "payer_id": patient.get("payer_id"),
        "member_id": member or None, "group_number": patient.get("group_number"),
        "subscriber": f"{patient['first_name']} {patient['last_name']}", "dob": patient.get("dob"),
        "service_date": on.isoformat(), "trace": f"TRN-{random.randint(10**8, 10**9 - 1)}",
    }
    if not payer:
        return {**base, "status": "no_insurance", "level": "error", "label": "No insurance on file",
                "message": "There is no insurance plan on this patient's record.",
                "action": "Ask for an insurance card and add it to the patient record, or register them as self-pay."}
    if payer["kind"] == "self":
        return {**base, "status": "self_pay", "level": "info", "label": "Self-pay patient",
                "message": "No insurance to verify. The patient pays the clinic directly.",
                "action": "Quote the self-pay price and collect at check-in."}
    rules, plan = insurer.rules(payer["payer_code"]), PLANS.get(payer["payer_code"])
    if not member:
        return {**base, "status": "missing_id", "level": "error", "label": "Member ID missing",
                "reject_code": "AAA-72", "message": f"{payer['name']} rejected the request: invalid or missing member ID (AAA-72).",
                "action": "Copy the member ID from the patient's insurance card into their record, then re-check."}
    if not rules or not plan:
        return {**base, "status": "not_found", "level": "error", "label": "Member not found",
                "reject_code": "AAA-75", "message": f"{payer['name']} could not find this member (AAA-75).",
                "action": "Check the member ID, name and date of birth against the insurance card."}

    year_start = date(on.year, 1, 1)
    if member in TERMINATED:
        ended = on.replace(day=1) - timedelta(days=1)          # last day of the previous month
        ended_txt = ended.strftime("%b %d, %Y").replace(" 0", " ")
        return {**base, "status": "inactive", "level": "error", "label": f"Coverage ended {ended_txt}",
                "plan": plan["plan"], "coverage_type": plan["type"],
                "effective": date(on.year - 1, 1, 1).isoformat(), "terminated": ended.isoformat(),
                "message": f"{payer['name']} reports this member's coverage was terminated on {ended_txt}. "
                           "A claim for today's visit would be denied.",
                "action": "Ask the patient for their new insurance card. If they have none, check them in as self-pay "
                          "and collect the self-pay price."}

    ded = plan["deductible"]
    ded_met = min(ded, round(ded * (_seed_int(member, "ded") % 101) / 100 / 10) * 10)
    oop_max = plan["oop_max"]
    oop_met = min(oop_max, ded_met + round((_seed_int(member, "oop") % 900) / 10) * 10) if oop_max else None
    copay, coins = rules["copay"], rules["coins"]
    if copay:
        estimate = {"due_today": float(copay), "kind": "copay",
                    "note": f"${copay} office-visit copay (the deductible doesn't apply to office visits on this plan)."}
    else:
        estimate = {"due_today": 0.0, "kind": "coinsurance",
                    "note": f"No copay. The patient owes {round(coins * 100)}% coinsurance after the insurer pays"
                            + (f" (${ded - ded_met:.0f} of the deductible is still left)." if ded_met < ded else ".")}
    return {
        **base, "status": "active", "level": "ok", "label": "Active coverage",
        "plan": plan["plan"], "coverage_type": plan["type"],
        "effective": year_start.isoformat(), "terminated": None,
        "copay": copay, "specialist_copay": plan["specialist_copay"], "coinsurance_pct": round(coins * 100),
        "deductible": {"amount": ded, "met": ded_met, "remaining": ded - ded_met},
        "oop": {"max": oop_max, "met": oop_met, "remaining": (oop_max - oop_met) if oop_max else None},
        "estimate": estimate,
        "message": f"{payer['name']} confirms active coverage for {on.strftime('%b %d, %Y').replace(' 0', ' ')}.",
        "action": None,
    }


# ---- storage ------------------------------------------------------------------------------
def _row(r) -> dict:
    return {**json.loads(r["result"]), "id": r["id"], "patient_id": r["patient_id"], "appointment_id": r["appointment_id"],
            "source": r["source"], "checked_at": r["checked_at"]}


def record(patient: dict, appointment_id: int | None, source: str, on: date | None = None,
           checked_at: str | None = None) -> dict:
    result = respond(patient, on)
    with clinic._conn() as con:
        cur = con.execute(
            "INSERT INTO eligibility_checks (patient_id, appointment_id, source, status, result, checked_at) VALUES (?, ?, ?, ?, ?, ?)",
            (patient["id"], appointment_id, source, result["status"], json.dumps(result), checked_at or _now()),
        )
        row = con.execute("SELECT * FROM eligibility_checks WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _with_freshness(_row(row), patient)


def _with_freshness(check: dict, patient: dict) -> dict:
    """Stale = too old, or the insurance on the record changed since the check (e.g. a new card was entered)."""
    age = (datetime.now() - datetime.fromisoformat(check["checked_at"])).days
    changed = (check.get("payer_id") != patient.get("payer_id")
               or (check.get("member_id") or None) != ((patient.get("member_id") or "").strip() or None))
    check["stale"] = age >= STALE_AFTER_DAYS or changed
    check["stale_reason"] = ("Insurance on the record changed since this check" if changed
                             else f"Last checked {age} days ago" if check["stale"] else None)
    return check


def latest(patient_id: int) -> dict | None:
    p = clinic.get_patient(patient_id)
    if p is None:
        return None
    with clinic._conn() as con:
        r = con.execute("SELECT * FROM eligibility_checks WHERE patient_id = ? ORDER BY checked_at DESC, id DESC LIMIT 1",
                        (patient_id,)).fetchone()
    return _with_freshness(_row(r), p) if r else None


def history(patient_id: int, limit: int = 10) -> list[dict]:
    with clinic._conn() as con:
        rows = con.execute("SELECT * FROM eligibility_checks WHERE patient_id = ? ORDER BY checked_at DESC, id DESC LIMIT ?",
                           (patient_id, limit)).fetchall()
    return [_row(r) for r in rows]


def for_day(day: str) -> dict:
    """patient_id -> latest check summary, for the patients on that day's schedule (schedule badges)."""
    out = {}
    for a in clinic.list_appointments(day):
        if a["patient_id"] in out:
            continue
        chk = latest(a["patient_id"])
        out[a["patient_id"]] = None if chk is None else {
            k: chk.get(k) for k in ("status", "level", "label", "checked_at", "stale", "stale_reason", "plan", "payer", "source")}
    return out


def seed() -> None:
    """Called by seed.seed(): pretend the overnight batch already verified today's and tomorrow's patients."""
    reset()
    last_night = (datetime.now().replace(hour=19, minute=30, second=0, microsecond=0) - timedelta(days=1)).isoformat(timespec="seconds")
    seen = set()
    for d in (date.today(), date.today() + timedelta(days=1)):
        for a in clinic.list_appointments(d.isoformat()):
            if a["patient_id"] in seen or a["status"] in ("cancelled", "no_show"):
                continue
            seen.add(a["patient_id"])
            record(clinic.get_patient(a["patient_id"]), a["id"], "auto", on=d, checked_at=last_night)


# ---- API ----------------------------------------------------------------------------------------
router = APIRouter(prefix="/api/eligibility")
SOURCES = ("booking", "check_in", "chart", "batch", "portal")


class CheckBody(BaseModel):
    patient_id: int
    appointment_id: int | None = None
    source: str = "chart"


@router.post("/check")
async def check(body: CheckBody):
    p = clinic.get_patient(body.patient_id)
    if p is None:
        raise HTTPException(404, "Patient not found")
    if body.source not in SOURCES:
        raise HTTPException(400, "Unknown source")
    on = None
    if body.appointment_id:
        appt = clinic.get_appointment(body.appointment_id)
        if appt is None or appt["patient_id"] != body.patient_id:
            raise HTTPException(404, "Appointment not found for this patient")
        on = max(date.fromisoformat(appt["start"][:10]), date.today())
    await asyncio.sleep(random.uniform(0.5, 0.9))     # the insurer "thinking" (a real 271 takes ~1-5 s)
    chk = record(p, body.appointment_id, body.source, on=on)
    broadcast({"type": "eligibility_checked", "patient_id": p["id"], "appointment_id": body.appointment_id,
               "status": chk["status"]})
    return chk


@router.get("/patient/{patient_id}")
def patient_checks(patient_id: int):
    if clinic.get_patient(patient_id) is None:
        raise HTTPException(404, "Patient not found")
    return {"latest": latest(patient_id), "history": history(patient_id)}


@router.get("/day")
def day_checks(day: str | None = None):
    return for_day(day or date.today().isoformat())


class BatchBody(BaseModel):
    day: str


@router.post("/batch")
async def batch(body: BatchBody):
    """Verify everyone on a day's schedule at once (what clinics run the night before)."""
    try:
        on = date.fromisoformat(body.day)
    except ValueError:
        raise HTTPException(400, "day must be YYYY-MM-DD")
    await asyncio.sleep(random.uniform(0.8, 1.2))
    counts, seen = {}, set()
    for a in clinic.list_appointments(body.day):
        if a["patient_id"] in seen or a["status"] in ("cancelled", "no_show", "completed"):
            continue
        seen.add(a["patient_id"])
        chk = record(clinic.get_patient(a["patient_id"]), a["id"], "batch", on=max(on, date.today()))
        counts[chk["status"]] = counts.get(chk["status"], 0) + 1
    broadcast({"type": "eligibility_checked", "day": body.day, "batch": True})
    return {"checked": len(seen), "counts": counts, "problems": sum(v for k, v in counts.items() if k not in ("active", "self_pay"))}
