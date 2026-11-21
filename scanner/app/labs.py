"""Lab orders + a mock reference lab + results (Track A3).

Orders are placed from a visit. The mock lab "runs" each test and returns results after
LAB_SECONDS (or immediately via the demo button). Values are realistic and consistent with the
patient's chart (diabetic -> high A1c, hypothyroid -> high TSH, ...), deterministic per order.
The portal (Track B) reads GET /api/patients/{id}/results; the Clinical Inbox lists unreviewed results.
"""
import asyncio
import json
import os
import random
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import clinic
from .events import broadcast

router = APIRouter(prefix="/api")
LAB_SECONDS = float(os.environ.get("LAB_SECONDS", "20"))   # mock lab turnaround for the demo
_tasks: set = set()

SCHEMA = """
CREATE TABLE IF NOT EXISTS lab_orders (
    id INTEGER PRIMARY KEY,
    patient_id INTEGER, encounter_id INTEGER, provider_id INTEGER,
    test_code TEXT, test_name TEXT, cpt TEXT,
    status TEXT,                  -- ordered | resulted | reviewed
    ordered_at TEXT, resulted_at TEXT,
    results TEXT,                 -- JSON list of {analyte, value, unit, ref_range, flag}
    abnormal INTEGER DEFAULT 0,
    reviewed_at TEXT, reviewed_by TEXT, provider_comment TEXT
);
"""

# test code -> (name, CPT, [(analyte, unit, low, high, decimals)])  low/high None = one-sided range
CATALOG = {
    "CBC": ("Complete blood count (CBC)", "85025", [
        ("WBC", "K/uL", 4.0, 11.0, 1), ("Hemoglobin", "g/dL", 12.0, 17.5, 1),
        ("Hematocrit", "%", 36.0, 50.0, 1), ("Platelets", "K/uL", 150, 400, 0)]),
    "CMP": ("Comprehensive metabolic panel (CMP)", "80053", [
        ("Glucose", "mg/dL", 70, 99, 0), ("BUN", "mg/dL", 7, 20, 0), ("Creatinine", "mg/dL", 0.6, 1.3, 2),
        ("Sodium", "mmol/L", 135, 145, 0), ("Potassium", "mmol/L", 3.5, 5.1, 1), ("Calcium", "mg/dL", 8.5, 10.5, 1),
        ("ALT", "U/L", 7, 56, 0), ("AST", "U/L", 10, 40, 0), ("Albumin", "g/dL", 3.5, 5.0, 1)]),
    "LIPID": ("Lipid panel", "80061", [
        ("Total cholesterol", "mg/dL", None, 199, 0), ("LDL cholesterol", "mg/dL", None, 99, 0),
        ("HDL cholesterol", "mg/dL", 40, None, 0), ("Triglycerides", "mg/dL", None, 149, 0)]),
    "A1C": ("Hemoglobin A1c", "83036", [("Hemoglobin A1c", "%", 4.0, 5.6, 1)]),
    "TSH": ("Thyroid stimulating hormone (TSH)", "84443", [("TSH", "mIU/L", 0.4, 4.0, 2)]),
    "GLU": ("Glucose", "82947", [("Glucose", "mg/dL", 70, 99, 0)]),
    "UA": ("Urinalysis, dipstick", "81002", [
        ("Leukocyte esterase", "", "Negative", None, None), ("Nitrite", "", "Negative", None, None),
        ("Protein", "", "Negative", None, None), ("Glucose (urine)", "", "Negative", None, None)]),
}


def init() -> None:
    with clinic._conn() as con:
        con.executescript(SCHEMA)
    # results that were still "at the lab" when the app stopped come back now
    with clinic._conn() as con:
        overdue = [r["id"] for r in con.execute("SELECT id FROM lab_orders WHERE status = 'ordered'")]
    for oid in overdue:
        _result(oid, announce=False)


def reset() -> None:
    with clinic._conn() as con:
        con.executescript(SCHEMA)
        con.execute("DELETE FROM lab_orders")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _row(r) -> dict:
    d = dict(r)
    d["results"] = json.loads(d["results"]) if d.get("results") else []
    return d


# ---- the mock lab ------------------------------------------------------------------------
def _ref(low, high) -> str:
    if isinstance(low, str):
        return low
    if low is None:
        return f"≤ {high:g}"
    if high is None:
        return f"≥ {low:g}"
    return f"{low:g}-{high:g}"


def _values_for(patient: dict, encounter: dict | None, code: str, rng: random.Random) -> dict:
    """Targets (analyte -> value) consistent with the chart; everything else is a normal value."""
    conds = f"{patient.get('conditions') or ''} {(encounter or {}).get('note') or ''}".lower()
    v = {}
    diabetic = "diabetes" in conds and "prediabetes" not in conds
    if diabetic:
        v.update({"Hemoglobin A1c": rng.uniform(7.6, 8.4), "Glucose": rng.uniform(150, 190)})
    elif "prediabetes" in conds or "obes" in conds:
        v.update({"Hemoglobin A1c": rng.uniform(5.8, 6.2), "Glucose": rng.uniform(100, 118)})
    if "hypothyroid" in conds:
        v["TSH"] = rng.uniform(7.5, 9.5)
    if "hyperlipidemia" in conds or "cholesterol" in conds or "obes" in conds or diabetic:
        v.update({"Total cholesterol": rng.uniform(225, 260), "LDL cholesterol": rng.uniform(150, 175),
                  "HDL cholesterol": rng.uniform(34, 39), "Triglycerides": rng.uniform(180, 240)})
    if "uti" in conds or "urinary" in conds or "dysuria" in conds:
        v.update({"Leukocyte esterase": "Positive (2+)", "Nitrite": "Positive"})
    return v


def _generate(order: dict) -> list[dict]:
    patient = clinic.get_patient(order["patient_id"])
    enc = clinic.get_encounter(order["encounter_id"]) if order["encounter_id"] else None
    rng = random.Random(order["id"] * 7919 + 17)
    targets = _values_for(patient, enc, order["test_code"], rng)
    rows = []
    for analyte, unit, low, high, dec in CATALOG[order["test_code"]][2]:
        if isinstance(low, str):  # qualitative (urinalysis)
            val = targets.get(analyte, low)
            rows.append({"analyte": analyte, "value": val, "unit": unit, "ref_range": low,
                         "flag": "A" if val != low else ""})
            continue
        if analyte in targets:
            x = targets[analyte]
        else:  # comfortably inside the normal range
            lo = low if low is not None else high * 0.45
            hi = high if high is not None else low * 1.6
            x = rng.uniform(lo + (hi - lo) * 0.2, hi - (hi - lo) * 0.2)
        x = round(x, dec) if dec else int(round(x))
        flag = "H" if high is not None and x > high else "L" if low is not None and x < low else ""
        rows.append({"analyte": analyte, "value": x, "unit": unit, "ref_range": _ref(low, high), "flag": flag})
    return rows


def _result(order_id: int, announce: bool = True) -> dict | None:
    order = get_order(order_id)
    if order is None or order["status"] != "ordered":
        return order
    rows = _generate(order)
    abnormal = sum(1 for r in rows if r["flag"])
    with clinic._conn() as con:
        con.execute("UPDATE lab_orders SET status = 'resulted', resulted_at = ?, results = ?, abnormal = ? WHERE id = ?",
                    (_now(), json.dumps(rows), abnormal, order_id))
    order = get_order(order_id)
    if announce:
        broadcast({"type": "lab_resulted", "order": order, "patient_id": order["patient_id"]})
    return order


async def _result_later(order_id: int) -> None:
    await asyncio.sleep(LAB_SECONDS)
    _result(order_id)


# ---- storage -----------------------------------------------------------------------------
def get_order(order_id: int) -> dict | None:
    with clinic._conn() as con:
        r = con.execute(
            """SELECT o.*, p.first_name, p.last_name, p.mrn, p.dob, pr.name AS provider_name
               FROM lab_orders o JOIN patients p ON p.id = o.patient_id LEFT JOIN providers pr ON pr.id = o.provider_id
               WHERE o.id = ?""", (order_id,)).fetchone()
    return _row(r) if r else None


def list_orders(patient_id: int | None = None, encounter_id: int | None = None, status: str | None = None) -> list[dict]:
    where, args = [], []
    for col, val in (("o.patient_id", patient_id), ("o.encounter_id", encounter_id), ("o.status", status)):
        if val is not None:
            where.append(f"{col} = ?")
            args.append(val)
    with clinic._conn() as con:
        rows = con.execute(
            f"""SELECT o.*, p.first_name, p.last_name, p.mrn, p.dob, pr.name AS provider_name
                FROM lab_orders o JOIN patients p ON p.id = o.patient_id LEFT JOIN providers pr ON pr.id = o.provider_id
                {('WHERE ' + ' AND '.join(where)) if where else ''} ORDER BY o.ordered_at DESC, o.id DESC""", args).fetchall()
    return [_row(r) for r in rows]


def create_order(patient_id: int, encounter_id: int | None, provider_id: int | None, code: str,
                 ordered_at: str | None = None) -> int:
    name, cpt, _ = CATALOG[code]
    with clinic._conn() as con:
        cur = con.execute(
            """INSERT INTO lab_orders (patient_id, encounter_id, provider_id, test_code, test_name, cpt, status, ordered_at)
               VALUES (?, ?, ?, ?, ?, ?, 'ordered', ?)""",
            (patient_id, encounter_id, provider_id, code, name, cpt, ordered_at or _now()))
        return cur.lastrowid


def orders_for_coding(encounter_id: int) -> str:
    """One line for the AI coder: which tests were ordered at this visit."""
    orders = list_orders(encounter_id=encounter_id)
    return "; ".join(f"{o['test_name']} (CPT {o['cpt']})" for o in orders) or "none"


def seed(patient_ids: list[int]) -> None:
    """Demo lab history: older reviewed results + one abnormal result waiting in the Clinical Inbox."""
    reset()
    now = datetime.now()

    def past(pid, code, days, reviewed, comment=None):
        oid = create_order(pid, None, 1, code, (now - timedelta(days=days)).isoformat(timespec="seconds"))
        _result(oid, announce=False)
        when = (now - timedelta(days=days, hours=-14)).isoformat(timespec="seconds")  # back ~14 h after ordering
        with clinic._conn() as con:
            con.execute("UPDATE lab_orders SET resulted_at = ? WHERE id = ?", (when, oid))
            if reviewed:
                con.execute("UPDATE lab_orders SET status = 'reviewed', reviewed_at = ?, reviewed_by = ?, provider_comment = ? "
                            "WHERE id = ?", (when, "Dr. Amina Rahman", comment, oid))

    past(patient_ids[1], "A1C", 60, True, "Your A1c is 7.8%, above goal. Keep taking metformin and we'll review diet at your visit.")
    past(patient_ids[1], "LIPID", 60, True, "Cholesterol is high. Please keep taking atorvastatin every night.")
    past(patient_ids[0], "CMP", 92, True, "Kidney function and potassium are normal on lisinopril.")
    past(patient_ids[0], "LIPID", 1, False)   # waiting for review in the Clinical Inbox
    past(patient_ids[5], "A1C", 2, False)     # Omar: prediabetes-range A1c, waiting for review


# ---- API ---------------------------------------------------------------------------------
@router.get("/labs/catalog")
def catalog():
    return [{"code": c, "name": n, "cpt": cpt, "analytes": [a[0] for a in rows]} for c, (n, cpt, rows) in CATALOG.items()]


class OrderBody(BaseModel):
    tests: list[str]


@router.post("/encounters/{enc_id}/labs")
async def order_labs(enc_id: int, body: OrderBody):
    enc = clinic.get_encounter(enc_id)
    if enc is None:
        raise HTTPException(404, "Visit not found")
    if enc["status"] == "signed":
        raise HTTPException(409, "This visit is signed")
    bad = [t for t in body.tests if t not in CATALOG]
    if bad or not body.tests:
        raise HTTPException(400, f"Pick at least one valid test{': unknown ' + ', '.join(bad) if bad else ''}")
    already = {o["test_code"] for o in list_orders(encounter_id=enc_id)}
    ids = []
    for code in dict.fromkeys(body.tests):
        if code in already:
            continue
        oid = create_order(enc["patient_id"], enc_id, enc["provider_id"], code)
        ids.append(oid)
        task = asyncio.create_task(_result_later(oid))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)
    broadcast({"type": "lab_ordered", "encounter_id": enc_id, "patient_id": enc["patient_id"]})
    return {"ordered": ids, "skipped_duplicates": len(body.tests) - len(ids), "turnaround_seconds": LAB_SECONDS}


@router.get("/encounters/{enc_id}/labs")
def encounter_labs(enc_id: int):
    return list_orders(encounter_id=enc_id)


@router.post("/labs/{order_id}/result-now")
def result_now(order_id: int):
    """Demo button: the mock lab finishes this test immediately."""
    order = _result(order_id)
    if order is None:
        raise HTTPException(404, "Lab order not found")
    return order


class ReviewBody(BaseModel):
    comment: str = ""
    reviewer: str = "Your care team"


@router.post("/labs/{order_id}/review")
def review(order_id: int, body: ReviewBody):
    order = get_order(order_id)
    if order is None:
        raise HTTPException(404, "Lab order not found")
    if order["status"] == "ordered":
        raise HTTPException(409, "No results yet")
    with clinic._conn() as con:
        con.execute("UPDATE lab_orders SET status = 'reviewed', reviewed_at = ?, reviewed_by = ?, provider_comment = ? "
                    "WHERE id = ?", (_now(), body.reviewer, body.comment.strip() or None, order_id))
    order = get_order(order_id)
    broadcast({"type": "lab_reviewed", "order": order, "patient_id": order["patient_id"]})
    return order


@router.get("/patients/{patient_id}/results")
def patient_results(patient_id: int):
    """Contract with the portal (Track B): one entry per test with result rows + the provider's note."""
    if clinic.get_patient(patient_id) is None:
        raise HTTPException(404, "Patient not found")
    return [{"id": o["id"], "test_name": o["test_name"], "status": o["status"], "ordered_at": o["ordered_at"],
             "resulted_at": o["resulted_at"], "results": o["results"] if o["status"] != "ordered" else [],
             "abnormal": o["abnormal"], "provider_comment": o["provider_comment"], "provider_name": o["provider_name"]}
            for o in list_orders(patient_id=patient_id)]
