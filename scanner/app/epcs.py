"""Controlled-substance e-prescribing (EPCS), DEMO ONLY.

Mirrors the real requirements in a simulated way:
  - DEA schedule per drug (drugs.SCHEDULE); C-II: no refills; C-III-V: max 5 refills; days' supply required
  - PDMP check (fictional state prescription-monitoring history) must be reviewed before signing
  - two-factor signing: provider PIN (something you know) + one-time code emailed to the demo inbox
    (something you have), like the DEA's 2FA rule for EPCS
  - the prescription goes to the pharmacy inbox and is emailed, clearly marked as a DEMO (not a valid prescription)
Real EPCS needs a certified EPCS app, DEA registration and identity proofing; this only demonstrates the workflow.
"""
import asyncio
import random
import re
import time
import uuid
from datetime import date, datetime, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import clinic, drugs, mailer
from .events import broadcast

router = APIRouter(prefix="/api")
DEMO_PIN = "2468"                 # every demo provider's signing PIN (shown on screen as a demo hint)
CODE_TTL = 5 * 60                 # seconds a 2FA code stays valid
MAX_TRIES = 3
_pending: dict[str, dict] = {}    # request_id -> {payload, code, expires, tries}

# Morphine milligram equivalent factors (CDC) for daily-MME risk checks.
MME_FACTOR = {"Hydrocodone-acetaminophen": 1.0, "Oxycodone": 1.5, "Tramadol": 0.2}


def init() -> None:
    with clinic._conn() as con:
        rx_cols = {r["name"] for r in con.execute("PRAGMA table_info(prescriptions)")}
        for col, typ in (("schedule", "TEXT"), ("days_supply", "INTEGER"), ("dea_number", "TEXT"),
                         ("epcs_signed_at", "TEXT"), ("pdmp_reviewed", "INTEGER")):
            if col not in rx_cols:
                con.execute(f"ALTER TABLE prescriptions ADD COLUMN {col} {typ}")
        if "dea" not in {r["name"] for r in con.execute("PRAGMA table_info(providers)")}:
            con.execute("ALTER TABLE providers ADD COLUMN dea TEXT")
        con.execute("UPDATE providers SET dea = 'DEMO-DEA-' || printf('%04d', id) WHERE dea IS NULL")


# ---- PDMP (fictional) ------------------------------------------------------------------
# Demo histories keyed by MRN: Fatima = multiple-provider red flag, Linda = active benzodiazepine,
# David = one old tramadol fill. Everyone else is clean. Dates are relative to today.
_PDMP_DEMO = {
    "MRN-100009": [  # Fatima Ali
        ("Hydrocodone-acetaminophen", "5-325 mg tablet", 60, 15, 70, "Dr. K. Morgan (orthopedics)", "Coit Road Pharmacy"),
        ("Tramadol", "50 mg tablet", 90, 30, 40, "Dr. L. Brooks (urgent care)", "Parker Rd Pharmacy"),
        ("Hydrocodone-acetaminophen", "5-325 mg tablet", 30, 10, 6, "Dr. S. Park (emergency dept.)", "Spring Creek Pharmacy"),
    ],
    "MRN-100005": [  # Linda Patel
        ("Alprazolam", "0.5 mg tablet", 60, 30, 10, "Dr. R. Shah (psychiatry)", "Main Street Rx"),
    ],
    "MRN-100008": [  # David Kim
        ("Tramadol", "50 mg tablet", 20, 5, 120, "Dr. Daniel Ortiz, DO", "Main Street Rx"),
    ],
}


def _mg(strength: str) -> float:
    m = re.match(r"\s*([\d.]+)", strength or "")
    return float(m.group(1)) if m else 0.0


def _fill(drug, strength, qty, days, filled: date, prescriber, pharmacy, source):
    until = filled + timedelta(days=days)
    return {"drug": drug, "strength": strength, "schedule": drugs.SCHEDULE.get(drug), "quantity": qty, "days_supply": days,
            "filled": filled.isoformat(), "until": until.isoformat(), "active": until >= date.today(),
            "prescriber": prescriber, "pharmacy": pharmacy, "source": source}


def _daily_mme(f: dict) -> float:
    factor = MME_FACTOR.get(f["drug"])
    if not factor or not f["days_supply"]:
        return 0.0
    return round(_mg(f["strength"]) * f["quantity"] / f["days_supply"] * factor, 1)


def pdmp_report(patient_id: int, proposed: dict | None = None) -> dict:
    """Fictional PDMP lookup + risk flags. `proposed` = the controlled Rx being written (drug/strength/qty/days)."""
    p = clinic.get_patient(patient_id)
    if p is None:
        raise HTTPException(404, "Patient not found")
    today = date.today()
    fills = [_fill(d, s, q, days, today - timedelta(days=ago), pr, ph, "state PDMP")
             for d, s, q, days, ago, pr, ph in _PDMP_DEMO.get(p["mrn"], [])]
    with clinic._conn() as con:   # controlled Rx already sent from this clinic
        for r in con.execute(
                """SELECT r.*, ph.name AS pharmacy_name, pr.name AS provider_name FROM prescriptions r
                   LEFT JOIN pharmacies ph ON ph.id = r.pharmacy_id LEFT JOIN providers pr ON pr.id = r.provider_id
                   WHERE r.patient_id = ? AND r.schedule IS NOT NULL""", (patient_id,)):
            fills.append(_fill(r["drug"], r["strength"], r["quantity"], r["days_supply"] or 30,
                               datetime.fromisoformat(r["sent_at"]).date(), r["provider_name"], r["pharmacy_name"],
                               "this clinic"))
    fills.sort(key=lambda f: f["filled"], reverse=True)
    recent = [f for f in fills if (today - date.fromisoformat(f["filled"])).days <= 90]
    active = [f for f in fills if f["active"]]
    prescribers, pharmacies = {f["prescriber"] for f in recent}, {f["pharmacy"] for f in recent}
    mme = sum(_daily_mme(f) for f in active)

    flags = []
    if len(prescribers) >= 3 or len(pharmacies) >= 3:
        flags.append({"level": "urgent", "text": f"Multiple-provider pattern: {len(prescribers)} prescribers and "
                                                 f"{len(pharmacies)} pharmacies in the last 90 days."})
    active_opioid = [f for f in active if f["drug"] in drugs.OPIOIDS]
    active_benzo = [f for f in active if f["drug"] in drugs.BENZOS]
    if proposed and proposed.get("drug"):
        new = proposed["drug"]
        if new in drugs.OPIOIDS and active_benzo:
            flags.append({"level": "urgent", "text": f"Opioid + benzodiazepine: patient has active {active_benzo[0]['drug']} "
                                                     f"(until {active_benzo[0]['until']}). FDA boxed warning: risk of "
                                                     f"respiratory depression."})
        if new in drugs.BENZOS and active_opioid:
            flags.append({"level": "urgent", "text": f"Benzodiazepine + opioid: patient has active {active_opioid[0]['drug']}. "
                                                     f"FDA boxed warning."})
        same = [f for f in active if f["drug"] == new]
        if same:
            flags.append({"level": "warning", "text": f"Already has an active {new} prescription until {same[0]['until']} "
                                                      f"({same[0]['prescriber']})."})
        if new in MME_FACTOR and proposed.get("days_supply"):
            mme += _daily_mme({"drug": new, "strength": proposed.get("strength", ""), "quantity": proposed.get("quantity", 0),
                               "days_supply": proposed["days_supply"]})
    if mme >= 90:
        flags.append({"level": "urgent", "text": f"Total daily dose {mme:.0f} MME (≥ 90): high overdose risk; consider naloxone."})
    elif mme >= 50:
        flags.append({"level": "warning", "text": f"Total daily dose {mme:.0f} MME (≥ 50): increased overdose risk."})
    return {
        "source": "Texas Prescription Monitoring Program (DEMO: fictional data)",
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "patient": f"{p['first_name']} {p['last_name']}", "fills": fills,
        "indicators": {"prescribers_90d": len(prescribers), "pharmacies_90d": len(pharmacies),
                       "active_opioid": bool(active_opioid), "active_benzo": bool(active_benzo),
                       "daily_mme": round(mme, 1)},
        "flags": flags,
    }


class PdmpQuery(BaseModel):
    drug: str | None = None
    strength: str | None = None
    quantity: int | None = None
    days_supply: int | None = None


@router.post("/pdmp/{patient_id}")
def pdmp(patient_id: int, body: PdmpQuery):
    return pdmp_report(patient_id, body.model_dump())


# ---- 2FA signing -------------------------------------------------------------------------
class EpcsBody(BaseModel):
    encounter_id: int | None = None
    patient_id: int
    provider_id: int
    pharmacy_id: int
    drug: str
    strength: str = ""
    sig: str = ""
    quantity: int
    refills: int = 0
    days_supply: int
    pdmp_reviewed: bool = False
    override_allergy: bool = False


def _validate(b: EpcsBody) -> dict:
    sched = drugs.SCHEDULE.get(b.drug)
    if not sched:
        raise HTTPException(400, f"{b.drug} is not a controlled substance")
    p = clinic.get_patient(b.patient_id)
    if p is None:
        raise HTTPException(404, "Patient not found")
    if b.encounter_id:
        e = clinic.get_encounter(b.encounter_id)
        if e and e["status"] == "signed":
            raise HTTPException(409, "This visit is signed. Prescribe from the patient chart instead")
    if not (1 <= b.days_supply <= 90):
        raise HTTPException(400, "Days' supply must be 1-90")
    if b.quantity < 1:
        raise HTTPException(400, "Quantity must be at least 1")
    if sched == "C-II" and b.refills != 0:
        raise HTTPException(400, "Schedule II drugs can't have refills (federal rule)")
    if sched != "C-II" and b.refills > 5:
        raise HTTPException(400, "Schedule III-V drugs allow at most 5 refills")
    if sched == "C-II" and b.drug in drugs.OPIOIDS and b.days_supply > 7:
        raise HTTPException(400, "Schedule II opioids for acute pain are limited to 7 days in this demo (state rules vary)")
    if not b.pdmp_reviewed:
        raise HTTPException(400, "Review the PDMP report before signing a controlled-substance prescription")
    conflicts = drugs.allergy_conflicts(b.drug, p["allergies"])
    if conflicts and not b.override_allergy:
        raise HTTPException(409, f"Allergy alert: patient is allergic to {', '.join(conflicts)}")
    provider = next((x for x in clinic.providers() if x["id"] == b.provider_id), None)
    if not provider or not provider.get("dea"):
        raise HTTPException(400, "Prescriber has no DEA number on file")
    return {"schedule": sched, "provider": provider, "patient": p}


def _mask(email: str) -> str:
    name, _, domain = email.partition("@")
    return (name[:2] + "•" * max(len(name) - 2, 3) + "@" + domain) if domain else "the provider's device"


@router.post("/epcs/challenge")
async def challenge(body: EpcsBody):
    """Step 1: validate, then send a one-time code to the provider's device (the demo email inbox)."""
    info = _validate(body)
    code = f"{random.SystemRandom().randint(0, 999999):06d}"
    rid = uuid.uuid4().hex
    _pending[rid] = {"payload": body.model_dump(), "code": code, "expires": time.time() + CODE_TTL, "tries": 0,
                     "schedule": info["schedule"], "dea": info["provider"]["dea"]}
    res = {"request_id": rid, "expires_in": CODE_TTL, "schedule": info["schedule"], "pin_hint": DEMO_PIN}
    if mailer.enabled():
        try:
            await asyncio.to_thread(mailer.send_code, info["provider"]["name"], code, body.drug, info["schedule"])
            res["sent_to"] = _mask(mailer.recipient())
        except Exception as e:
            res["sent_to"] = None
            res["dev_code"] = code
            res["note"] = f"Email failed ({str(e)[:80]}); demo code shown instead."
    else:
        res["sent_to"] = None
        res["dev_code"] = code   # email is off (e.g. tests): show the code so the demo still works
    return res


class SignBody(BaseModel):
    request_id: str
    code: str
    pin: str


@router.post("/epcs/sign")
async def sign(body: SignBody):
    """Step 2: check PIN + one-time code, then create, route and email the prescription."""
    req = _pending.get(body.request_id)
    if req is None:
        raise HTTPException(404, "Signing request not found. Start again")
    if time.time() > req["expires"]:
        _pending.pop(body.request_id, None)
        raise HTTPException(410, "The code expired. Start again to get a new one")
    req["tries"] += 1
    if req["tries"] > MAX_TRIES:
        _pending.pop(body.request_id, None)
        raise HTTPException(429, "Too many attempts. Start again")
    if body.pin.strip() != DEMO_PIN or body.code.strip() != req["code"]:
        left = MAX_TRIES - req["tries"]
        raise HTTPException(401, f"PIN or code is incorrect ({left} attempt{'s' if left != 1 else ''} left)")
    _pending.pop(body.request_id, None)

    data = req["payload"]
    rx_id = clinic.create_prescription({k: data[k] for k in ("encounter_id", "patient_id", "provider_id", "pharmacy_id",
                                                             "drug", "strength", "sig", "quantity", "refills")})
    with clinic._conn() as con:
        con.execute("""UPDATE prescriptions SET schedule = ?, days_supply = ?, dea_number = ?, epcs_signed_at = ?,
                       pdmp_reviewed = 1 WHERE id = ?""",
                    (req["schedule"], data["days_supply"], req["dea"], datetime.now().isoformat(timespec="seconds"), rx_id))
    rx = clinic.get_prescription(rx_id)
    broadcast({"type": "rx_sent", "rx": rx})
    emailed = False
    if mailer.enabled():
        try:
            await asyncio.to_thread(mailer.send_prescription, rx)
            clinic.update_prescription(rx_id, {"emailed": 1})
            emailed = True
            broadcast({"type": "rx_updated", "rx": clinic.get_prescription(rx_id)})
        except Exception as e:
            broadcast({"type": "toast", "level": "error", "text": f"Email to pharmacy failed: {e}"})
    return {"id": rx_id, "emailed": emailed, "schedule": req["schedule"]}
