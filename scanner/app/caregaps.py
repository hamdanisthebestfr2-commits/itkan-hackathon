"""Care gaps / quality measures (Track A4).

Simplified versions of real CMS quality measures (eCQMs), computed live from the chart: conditions,
vitals on every encounter (incl. card scans), visit notes (signed or in progress), lab results, prescriptions.
Each measure returns None (patient not in the measure), or a dict with status 'met' | 'open'.
An open gap carries a `close` hint the visit page can act on (order a lab, enter vitals, insert note text, book).
Demo simplification: real eCQMs have exact value sets, exclusions and a calendar measurement year.
"""
import re
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException

from . import clinic, labs

router = APIRouter(prefix="/api")
YEAR = 365

STATINS = ("atorvastatin", "rosuvastatin", "simvastatin", "pravastatin", "lovastatin", "pitavastatin")
TOBACCO_NOTE = re.compile(r"\b(smok\w*|tobacco|nicotine|cigarette\w*|vap\w*)\b", re.I)
CESSATION = re.compile(r"\b(cessation|quit\w*|stop smoking|nicotine (patch|gum|lozenge)|varenicline|bupropion|99406|99407)\b", re.I)
WEIGHT_PLAN = re.compile(r"\b(diet\w*|exercise|weight (loss|management|counsel\w*)|nutrition\w*|calori\w*|physical activity|G0447)\b", re.I)
BP_PLAN = re.compile(r"\b(recheck|follow[- ]?up|lifestyle|low[- ]sodium|dash diet|lisinopril|amlodipine|losartan|hydrochlorothiazide)\b", re.I)
BP_WORDS = re.compile(r"\b(BP|blood pressure|hypertension)\b", re.I)
A1C_IN_NOTE = re.compile(r"\bA1c\s*(?:of|is|was|=|:)?\s*(\d{1,2}(?:\.\d)?)\s*%?", re.I)

MEASURES = [  # id, CMS number, title, who is in it
    ("bp_control", "CMS165", "Controlling high blood pressure", "Patients with hypertension: latest BP below 140/90"),
    ("bp_screen", "CMS22", "High BP screening follow-up", "Elevated BP reading without a hypertension diagnosis: follow-up plan documented"),
    ("a1c", "CMS122", "Diabetes: A1c control", "Patients with diabetes: A1c in the last 6 months and below 8%"),
    ("statin", "CMS347", "Statin therapy", "Diabetes or high cholesterol, age 40-75: on a statin"),
    ("bmi", "CMS69", "BMI screening & follow-up", "Adults: BMI in the last year, plus a plan if 30 or higher"),
    ("tobacco", "CMS138", "Tobacco screening & cessation", "Adults: asked about tobacco in the last year, counseled if they use it"),
    ("awv", "AWV", "Annual wellness visit (65+)", "Patients 65 and older: a preventive or annual visit in the last year"),
]
MEASURE = {m[0]: m for m in MEASURES}


def _age(dob: str | None) -> int | None:
    if not dob:
        return None
    b, t = date.fromisoformat(dob), date.today()
    return t.year - b.year - ((t.month, t.day) < (b.month, b.day))


def _days_ago(d: str) -> int:
    return (date.today() - date.fromisoformat(d[:10])).days


def _d(iso: str) -> str:
    """'2026-11-20' -> 'Nov 20' (adds the year if it isn't this year)."""
    d = date.fromisoformat(iso[:10])
    return f"{d:%b} {d.day}" + (f", {d.year}" if d.year != date.today().year else "")


def _bmi(v: dict) -> float | None:
    try:
        inches = float(v.get("height_ft") or 0) * 12 + float(v.get("height_in") or 0)
        if inches and v.get("weight_lbs"):
            return round(703 * float(v["weight_lbs"]) / inches / inches, 1)
        return float(v["bmi"]) if v.get("bmi") else None
    except (TypeError, ValueError):
        return None


def _gap(mid: str, status: str, detail: str, close: dict | None = None, when: str | None = None) -> dict:
    _, cms, title, about = MEASURE[mid]
    return {"id": mid, "cms": cms, "title": title, "about": about, "status": status, "detail": detail,
            "close": close if status == "open" else None, "when": when}


def _context(p: dict) -> dict:
    encs = [e for e in p["encounters"] if _days_ago(e["date"]) <= YEAR]   # newest first
    # clinician notes only: a health-fair card's own advice ("offer cessation resources") isn't documentation
    notes = [(e["date"], e["note"]) for e in encs if e.get("note") and e["type"] != "screening"]
    conds = (p.get("conditions") or "").lower()
    meds = " ".join([p.get("medications") or ""] + [r["drug"] for r in p["prescriptions"]]).lower()
    bps = [(e["date"], int(float(e["vitals"]["bp_systolic"])), int(float(e["vitals"]["bp_diastolic"])))
           for e in encs if e["vitals"].get("bp_systolic") and e["vitals"].get("bp_diastolic")]
    orders = labs.list_orders(patient_id=p["id"])
    a1cs = [(o["resulted_at"][:10], float(o["results"][0]["value"])) for o in orders
            if o["test_code"] == "A1C" and o["status"] != "ordered" and o["results"]]
    for d, text in notes:
        a1cs += [(d, float(m)) for m in A1C_IN_NOTE.findall(text) if 3 < float(m) < 20]
    a1cs.sort(reverse=True)
    upcoming = sorted(a["start"] for a in p["appointments"]
                      if a["status"] in ("booked", "checked_in") and a["start"][:10] >= date.today().isoformat())
    return {"encs": encs, "notes": notes, "conds": conds, "meds": meds, "bps": sorted(bps, reverse=True),
            "a1cs": a1cs, "pending": {o["test_code"] for o in orders if o["status"] == "ordered"}, "age": _age(p.get("dob")), "upcoming": upcoming[0] if upcoming else None}


def _bp_control(p, c):
    if "hypertension" not in c["conds"]:
        return None
    if not c["bps"]:
        return _gap("bp_control", "open", "No blood pressure recorded in the last year", {"kind": "vitals", "label": "Take BP at this visit"})
    d, s, dia = c["bps"][0]
    if s < 140 and dia < 90:
        return _gap("bp_control", "met", f"BP {s}/{dia} on {_d(d)}", when=d)
    return _gap("bp_control", "open", f"BP {s}/{dia} on {_d(d)} is not at goal (<140/90)",
                {"kind": "vitals", "label": "Recheck BP today; adjust treatment if still high"}, when=d)


def _bp_screen(p, c):
    if "hypertension" in c["conds"]:
        return None
    high = [(d, s, dia) for d, s, dia in c["bps"] if s >= 130 or dia >= 80]
    if not high:
        return None
    d, s, dia = high[0]
    plan = any(nd >= d and BP_PLAN.search(t) and BP_WORDS.search(t) for nd, t in c["notes"])
    if plan:
        return _gap("bp_screen", "met", f"BP {s}/{dia} on {_d(d)}: follow-up plan documented", when=d)
    return _gap("bp_screen", "open", f"BP {s}/{dia} on {_d(d)}: no follow-up plan documented yet",
                {"kind": "note", "label": "Document a BP follow-up plan",
                 "text": f"Elevated BP {s}/{dia} ({_d(d)}). Plan: reduce salt, keep a home BP log, recheck BP in 4 weeks."},
                when=d)


def _a1c(p, c):
    if "diabetes" not in c["conds"] or "prediabetes" in c["conds"]:
        return None
    recent = [(d, v) for d, v in c["a1cs"] if _days_ago(d) <= 182]
    if not recent and "A1C" in c["pending"]:
        return _gap("a1c", "open", "A1c ordered: waiting for the lab result")
    if not recent:
        last = f" (last: {c['a1cs'][0][1]}% on {_d(c['a1cs'][0][0])})" if c["a1cs"] else ""
        return _gap("a1c", "open", f"A1c is overdue: none in the last 6 months{last}", {"kind": "lab", "test": "A1C", "label": "Order A1c"})
    d, v = recent[0]
    if v < 8:
        return _gap("a1c", "met", f"A1c {v}% on {_d(d)}", when=d)
    return _gap("a1c", "open", f"A1c {v}% on {_d(d)} is above goal (<8%)",
                {"kind": "note", "label": "Document a treatment change",
                 "text": f"A1c {v}% above goal. Plan: intensify diabetes treatment, diet review, recheck A1c in 3 months."}, when=d)


def _statin(p, c):
    if not ("diabetes" in c["conds"] and "prediabetes" not in c["conds"] or "hyperlipidemia" in c["conds"]
            or "cholesterol" in c["conds"]) or not c["age"] or not 40 <= c["age"] <= 75:
        return None
    if any(s in c["meds"] for s in STATINS):
        return _gap("statin", "met", "On a statin")
    return _gap("statin", "open", "Not on a statin", {"kind": "rx", "label": "Consider a statin (e.g. atorvastatin 20 mg)"})


def _bmi_gap(p, c):
    if c["age"] is None or c["age"] < 18:
        return None
    found = next(((e["date"], _bmi(e["vitals"])) for e in c["encs"] if _bmi(e["vitals"])), None)
    if not found:
        return _gap("bmi", "open", "No BMI in the last year", {"kind": "vitals", "label": "Enter height and weight"})
    d, bmi = found
    if bmi < 30:
        return _gap("bmi", "met", f"BMI {bmi} on {_d(d)}", when=d)
    if any(nd >= d and WEIGHT_PLAN.search(t) for nd, t in c["notes"]):
        return _gap("bmi", "met", f"BMI {bmi} on {_d(d)}: follow-up plan documented", when=d)
    return _gap("bmi", "open", f"BMI {bmi} on {_d(d)}: no weight follow-up plan documented",
                {"kind": "note", "label": "Document a weight plan",
                 "text": f"BMI {bmi}. Counseled on diet and physical activity; goal 5% weight loss; follow up in 3 months."}, when=d)


def _tobacco(p, c):
    if c["age"] is None or c["age"] < 18:
        return None
    smokes = [(e["date"], e["vitals"]["smoking"]) for e in c["encs"] if e["vitals"].get("smoking")]
    mentioned = [(d, t) for d, t in c["notes"] if TOBACCO_NOTE.search(t)]
    user = any(v == "Yes" for _, v in smokes) or any(w in c["conds"] for w in ("tobacco", "smok", "nicotine")) or \
        any(re.search(r"\b(current smoker|smokes|smoking \d|pack[- ]?(a[- ]day|years?))\b", t, re.I) for _, t in mentioned)
    if not smokes and not mentioned and not user:
        return _gap("tobacco", "open", "Tobacco use not asked in the last year",
                    {"kind": "note", "label": "Ask and document tobacco use", "text": "Tobacco use: screened, never smoker."})
    if not user:
        return _gap("tobacco", "met", "Screened: does not use tobacco")
    if any(CESSATION.search(t) for _, t in c["notes"]) or any(w in c["meds"] for w in ("nicotine", "varenicline", "bupropion")):
        return _gap("tobacco", "met", "Tobacco user: cessation counseling documented")
    return _gap("tobacco", "open", "Uses tobacco: no cessation counseling yet",
                {"kind": "note", "label": "Document cessation counseling",
                 "text": "Tobacco cessation counseling, 5 minutes: discussed health risks and quitting options; offered nicotine replacement."})


def _awv(p, c):
    if c["age"] is None or c["age"] < 65:
        return None
    for a in p["appointments"]:
        if a["status"] == "completed" and _days_ago(a["start"]) <= YEAR and \
                re.search(r"annual|wellness|physical|preventive", a["reason"] or "", re.I):
            return _gap("awv", "met", f"Annual visit on {_d(a['start'][:10])}", when=a["start"][:10])
    return _gap("awv", "open", "No annual wellness visit in the last year", {"kind": "book", "label": "Book an annual wellness visit"})


RULES = [_bp_control, _bp_screen, _a1c, _statin, _bmi_gap, _tobacco, _awv]


def gaps_for(patient_id: int) -> list[dict] | None:
    p = clinic.get_patient(patient_id)
    if p is None:
        return None
    c = _context(p)
    out = [g for g in (rule(p, c) for rule in RULES) if g]
    for g in out:
        g["upcoming"] = c["upcoming"] if g["status"] == "open" else None
    return out


def clinic_summary() -> dict:
    """Per-measure performance for every patient + today's scheduled patients with open gaps."""
    with clinic._conn() as con:
        pts = [dict(r) for r in con.execute("SELECT id, first_name, last_name FROM patients ORDER BY last_name")]
    per = {m[0]: {"id": m[0], "cms": m[1], "title": m[2], "about": m[3], "met": 0, "eligible": 0} for m in MEASURES}
    by_patient = {}
    for pt in pts:
        gaps = gaps_for(pt["id"])
        by_patient[pt["id"]] = gaps
        for g in gaps:
            per[g["id"]]["eligible"] += 1
            per[g["id"]]["met"] += g["status"] == "met"
    today = [a for a in clinic.list_appointments(date.today().isoformat())
             if a["status"] in ("booked", "checked_in", "in_visit")]
    close_today = []
    for a in sorted(today, key=lambda a: a["start"]):
        open_ = [g for g in by_patient.get(a["patient_id"], []) if g["status"] == "open"]
        if open_:
            close_today.append({"patient_id": a["patient_id"], "patient": f"{a['first_name']} {a['last_name']}",
                                "start": a["start"], "appointment_id": a["id"], "encounter_id": a["encounter_id"],
                                "gaps": [{"title": g["title"], "detail": g["detail"]} for g in open_]})
    total_open = sum(1 for gaps in by_patient.values() for g in gaps if g["status"] == "open")
    return {"measures": list(per.values()), "close_today": close_today, "open_total": total_open}


@router.get("/patients/{patient_id}/care-gaps")
def patient_gaps(patient_id: int):
    gaps = gaps_for(patient_id)
    if gaps is None:
        raise HTTPException(404, "Patient not found")
    return gaps


@router.get("/care-gaps")
def care_gaps():
    return clinic_summary()
