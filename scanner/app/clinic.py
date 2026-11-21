"""Clinic platform data: patients, providers, scheduling, visits, prescriptions.

Plain SQLite in the same database file as the mock CRM. Every function opens its own
short connection, so it is safe to call from any request.
"""
import json
import sqlite3
from datetime import datetime

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS providers (
    id INTEGER PRIMARY KEY, name TEXT, credentials TEXT, specialty TEXT, color TEXT, npi TEXT
);
CREATE TABLE IF NOT EXISTS payers (
    id INTEGER PRIMARY KEY, name TEXT, kind TEXT, payer_code TEXT
);
CREATE TABLE IF NOT EXISTS pharmacies (
    id INTEGER PRIMARY KEY, name TEXT, address TEXT, phone TEXT, email TEXT
);
CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY, mrn TEXT UNIQUE,
    first_name TEXT, last_name TEXT, dob TEXT, sex TEXT,
    phone TEXT, email TEXT, address TEXT, city TEXT, state TEXT, zip TEXT,
    payer_id INTEGER REFERENCES payers(id), member_id TEXT, group_number TEXT,
    pharmacy_id INTEGER REFERENCES pharmacies(id),
    allergies TEXT, conditions TEXT, medications TEXT,
    source TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY,
    patient_id INTEGER REFERENCES patients(id), provider_id INTEGER REFERENCES providers(id),
    start TEXT, duration_min INTEGER, reason TEXT, visit_type TEXT,
    status TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS encounters (
    id INTEGER PRIMARY KEY,
    patient_id INTEGER REFERENCES patients(id), provider_id INTEGER REFERENCES providers(id),
    appointment_id INTEGER REFERENCES appointments(id),
    date TEXT, type TEXT, vitals TEXT, note TEXT, status TEXT, source_image TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS prescriptions (
    id INTEGER PRIMARY KEY,
    encounter_id INTEGER REFERENCES encounters(id), patient_id INTEGER REFERENCES patients(id),
    provider_id INTEGER REFERENCES providers(id), pharmacy_id INTEGER REFERENCES pharmacies(id),
    drug TEXT, strength TEXT, sig TEXT, quantity INTEGER, refills INTEGER,
    status TEXT, emailed INTEGER, sent_at TEXT, updated_at TEXT
);
"""

APPOINTMENT_STATUSES = ("booked", "checked_in", "in_visit", "completed", "cancelled", "no_show")
PATIENT_FIELDS = (
    "first_name", "last_name", "dob", "sex", "phone", "email", "address", "city", "state", "zip",
    "payer_id", "member_id", "group_number", "pharmacy_id", "allergies", "conditions", "medications",
)


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _rows(rows) -> list[dict]:
    return [dict(r) for r in rows]


def init() -> None:
    with _conn() as con:
        con.executescript(SCHEMA)
        if "alerts" not in {r["name"] for r in con.execute("PRAGMA table_info(encounters)")}:
            con.execute("ALTER TABLE encounters ADD COLUMN alerts TEXT")


def is_empty() -> bool:
    with _conn() as con:
        return con.execute("SELECT count(*) FROM providers").fetchone()[0] == 0


def reset() -> None:
    with _conn() as con:
        con.executescript(
            "DELETE FROM prescriptions; DELETE FROM encounters; DELETE FROM appointments;"
            "DELETE FROM patients; DELETE FROM pharmacies; DELETE FROM payers; DELETE FROM providers;"
        )


# ---- reference data ----------------------------------------------------------
def providers() -> list[dict]:
    with _conn() as con:
        return _rows(con.execute("SELECT * FROM providers ORDER BY id"))


def payers() -> list[dict]:
    with _conn() as con:
        return _rows(con.execute("SELECT * FROM payers ORDER BY id"))


def pharmacies() -> list[dict]:
    with _conn() as con:
        return _rows(con.execute("SELECT * FROM pharmacies ORDER BY id"))


# ---- patients ----------------------------------------------------------------
def _next_mrn(con) -> str:
    n = con.execute("SELECT count(*) FROM patients").fetchone()[0]
    return f"MRN-{100001 + n}"


def create_patient(data: dict, source: str = "front desk") -> int:
    cols = [c for c in PATIENT_FIELDS if c in data]
    with _conn() as con:
        cur = con.execute(
            f"INSERT INTO patients (mrn, {', '.join(cols)}, source, created_at) VALUES (?, {', '.join('?' * len(cols))}, ?, ?)",
            (_next_mrn(con), *[data[c] for c in cols], source, _now()),
        )
        return cur.lastrowid


def update_patient(patient_id: int, data: dict) -> None:
    cols = [c for c in PATIENT_FIELDS if c in data]
    if not cols:
        return
    with _conn() as con:
        con.execute(
            f"UPDATE patients SET {', '.join(f'{c} = ?' for c in cols)} WHERE id = ?",
            (*[data[c] for c in cols], patient_id),
        )


def find_patient(first: str, last: str, dob: str | None, phone: str | None) -> int | None:
    """Duplicate check: same name and (same DOB or same phone)."""
    with _conn() as con:
        row = con.execute(
            """SELECT id FROM patients WHERE lower(first_name) = lower(?) AND lower(last_name) = lower(?)
               AND (dob = ? OR phone = ?)""",
            (first, last, dob, phone),
        ).fetchone()
    return row["id"] if row else None


def list_patients(q: str = "") -> list[dict]:
    like = f"%{q.lower()}%"
    with _conn() as con:
        return _rows(con.execute(
            """SELECT p.*, py.name AS payer_name,
                      (SELECT max(date) FROM encounters e WHERE e.patient_id = p.id) AS last_visit,
                      (SELECT min(start) FROM appointments a WHERE a.patient_id = p.id
                         AND a.start >= date('now', 'localtime') AND a.status IN ('booked', 'checked_in')) AS next_appt
               FROM patients p LEFT JOIN payers py ON py.id = p.payer_id
               WHERE lower(p.first_name || ' ' || p.last_name) LIKE ? OR p.phone LIKE ? OR lower(p.mrn) LIKE ?
               ORDER BY p.last_name, p.first_name""",
            (like, like, like),
        ))


def get_patient(patient_id: int) -> dict | None:
    with _conn() as con:
        p = con.execute(
            """SELECT p.*, py.name AS payer_name, ph.name AS pharmacy_name
               FROM patients p LEFT JOIN payers py ON py.id = p.payer_id
               LEFT JOIN pharmacies ph ON ph.id = p.pharmacy_id WHERE p.id = ?""",
            (patient_id,),
        ).fetchone()
        if not p:
            return None
        appts = con.execute(
            """SELECT a.*, pr.name AS provider_name FROM appointments a
               JOIN providers pr ON pr.id = a.provider_id WHERE a.patient_id = ? ORDER BY a.start DESC""",
            (patient_id,),
        ).fetchall()
        encs = con.execute(
            """SELECT e.*, pr.name AS provider_name FROM encounters e
               LEFT JOIN providers pr ON pr.id = e.provider_id WHERE e.patient_id = ? ORDER BY e.date DESC, e.id DESC""",
            (patient_id,),
        ).fetchall()
        rxs = con.execute(
            """SELECT r.*, ph.name AS pharmacy_name, pr.name AS provider_name FROM prescriptions r
               LEFT JOIN pharmacies ph ON ph.id = r.pharmacy_id LEFT JOIN providers pr ON pr.id = r.provider_id
               WHERE r.patient_id = ? ORDER BY r.sent_at DESC""",
            (patient_id,),
        ).fetchall()
    return {
        **dict(p),
        "appointments": _rows(appts),
        "encounters": [{**dict(e), "vitals": json.loads(e["vitals"] or "{}")} for e in encs],
        "prescriptions": _rows(rxs),
    }


# ---- scheduling --------------------------------------------------------------
def list_appointments(day: str) -> list[dict]:
    """day: YYYY-MM-DD"""
    with _conn() as con:
        return _rows(con.execute(
            """SELECT a.*, p.first_name, p.last_name, p.mrn, p.dob, pr.name AS provider_name, pr.color AS provider_color,
                      (SELECT id FROM encounters e WHERE e.appointment_id = a.id) AS encounter_id
               FROM appointments a JOIN patients p ON p.id = a.patient_id JOIN providers pr ON pr.id = a.provider_id
               WHERE date(a.start) = ? ORDER BY a.start""",
            (day,),
        ))


def create_appointment(data: dict) -> int:
    with _conn() as con:
        cur = con.execute(
            """INSERT INTO appointments (patient_id, provider_id, start, duration_min, reason, visit_type, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'booked', ?)""",
            (data["patient_id"], data["provider_id"], data["start"], data.get("duration_min", 30),
             data.get("reason", ""), data.get("visit_type", "follow_up"), _now()),
        )
        return cur.lastrowid


def update_appointment(appt_id: int, data: dict) -> None:
    cols = [c for c in ("provider_id", "start", "duration_min", "reason", "visit_type", "status") if c in data]
    if "status" in data and data["status"] not in APPOINTMENT_STATUSES:
        raise ValueError(f"Unknown status {data['status']}")
    with _conn() as con:
        con.execute(f"UPDATE appointments SET {', '.join(f'{c} = ?' for c in cols)} WHERE id = ?",
                    (*[data[c] for c in cols], appt_id))


def get_appointment(appt_id: int) -> dict | None:
    with _conn() as con:
        r = con.execute("SELECT * FROM appointments WHERE id = ?", (appt_id,)).fetchone()
    return dict(r) if r else None


def slot_taken(provider_id: int, start: str, duration_min: int, ignore_id: int | None = None) -> bool:
    """True if the provider already has an active appointment overlapping this time."""
    with _conn() as con:
        row = con.execute(
            """SELECT 1 FROM appointments WHERE provider_id = ? AND status NOT IN ('cancelled', 'no_show')
               AND id != coalesce(?, -1)
               AND datetime(start) < datetime(?, '+' || ? || ' minutes')
               AND datetime(start, '+' || duration_min || ' minutes') > datetime(?)""",
            (provider_id, ignore_id, start, duration_min, start),
        ).fetchone()
    return row is not None


# ---- visits ------------------------------------------------------------------
def create_encounter(data: dict) -> int:
    with _conn() as con:
        cur = con.execute(
            """INSERT INTO encounters (patient_id, provider_id, appointment_id, date, type, vitals, note, status, source_image,
                                       alerts, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["patient_id"], data.get("provider_id"), data.get("appointment_id"),
             data.get("date") or datetime.now().date().isoformat(), data.get("type", "office visit"),
             json.dumps(data.get("vitals") or {}), data.get("note", ""), data.get("status", "open"),
             data.get("source_image"), json.dumps(data.get("alerts") or []), _now()),
        )
        return cur.lastrowid


def get_encounter(enc_id: int) -> dict | None:
    with _conn() as con:
        e = con.execute(
            """SELECT e.*, pr.name AS provider_name FROM encounters e
               LEFT JOIN providers pr ON pr.id = e.provider_id WHERE e.id = ?""",
            (enc_id,),
        ).fetchone()
        if not e:
            return None
        rxs = con.execute(
            """SELECT r.*, ph.name AS pharmacy_name FROM prescriptions r LEFT JOIN pharmacies ph ON ph.id = r.pharmacy_id
               WHERE r.encounter_id = ? ORDER BY r.id""",
            (enc_id,),
        ).fetchall()
    return {**dict(e), "vitals": json.loads(e["vitals"] or "{}"), "prescriptions": _rows(rxs)}


def update_encounter(enc_id: int, data: dict) -> None:
    sets, vals = [], []
    for c in ("note", "status", "type", "provider_id"):
        if c in data:
            sets.append(f"{c} = ?")
            vals.append(data[c])
    if "vitals" in data:
        sets.append("vitals = ?")
        vals.append(json.dumps(data["vitals"]))
    if sets:
        with _conn() as con:
            con.execute(f"UPDATE encounters SET {', '.join(sets)} WHERE id = ?", (*vals, enc_id))


def latest_vitals(patient_id: int, exclude_encounter: int | None = None) -> dict:
    """Most recent recorded vitals (e.g. from today's health-fair card scan), with where they came from."""
    with _conn() as con:
        r = con.execute(
            """SELECT vitals, date, type FROM encounters WHERE patient_id = ? AND vitals != '{}' AND id != coalesce(?, -1)
               ORDER BY date DESC, id DESC LIMIT 1""",
            (patient_id, exclude_encounter),
        ).fetchone()
    return {"vitals": json.loads(r["vitals"]), "date": r["date"], "type": r["type"]} if r else {}


# ---- prescriptions -----------------------------------------------------------
def create_prescription(data: dict) -> int:
    with _conn() as con:
        cur = con.execute(
            """INSERT INTO prescriptions (encounter_id, patient_id, provider_id, pharmacy_id, drug, strength, sig,
                                          quantity, refills, status, emailed, sent_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'sent', 0, ?, ?)""",
            (data.get("encounter_id"), data["patient_id"], data.get("provider_id"), data["pharmacy_id"],
             data["drug"], data.get("strength", ""), data.get("sig", ""), data.get("quantity", 30),
             data.get("refills", 0), _now(), _now()),
        )
        return cur.lastrowid


def get_prescription(rx_id: int) -> dict | None:
    with _conn() as con:
        r = con.execute(
            """SELECT r.*, p.first_name, p.last_name, p.dob, p.mrn, p.allergies,
                      ph.name AS pharmacy_name, ph.email AS pharmacy_email,
                      pr.name AS provider_name, pr.credentials AS provider_credentials, pr.npi AS provider_npi
               FROM prescriptions r JOIN patients p ON p.id = r.patient_id
               LEFT JOIN pharmacies ph ON ph.id = r.pharmacy_id LEFT JOIN providers pr ON pr.id = r.provider_id
               WHERE r.id = ?""",
            (rx_id,),
        ).fetchone()
    return dict(r) if r else None


def update_prescription(rx_id: int, data: dict) -> None:
    cols = [c for c in ("status", "emailed") if c in data]
    with _conn() as con:
        con.execute(f"UPDATE prescriptions SET {', '.join(f'{c} = ?' for c in cols)}, updated_at = ? WHERE id = ?",
                    (*[data[c] for c in cols], _now(), rx_id))


def pharmacy_inbox(pharmacy_id: int | None = None) -> list[dict]:
    with _conn() as con:
        return _rows(con.execute(
            """SELECT r.*, p.first_name, p.last_name, p.dob, p.mrn, p.allergies, ph.name AS pharmacy_name,
                      pr.name AS provider_name, pr.credentials AS provider_credentials
               FROM prescriptions r JOIN patients p ON p.id = r.patient_id
               LEFT JOIN pharmacies ph ON ph.id = r.pharmacy_id LEFT JOIN providers pr ON pr.id = r.provider_id
               WHERE ? IS NULL OR r.pharmacy_id = ? ORDER BY r.sent_at DESC, r.id DESC""",
            (pharmacy_id, pharmacy_id),
        ))


# ---- scanner integration -----------------------------------------------------
def record_scan(values: dict, image: str | None, alerts: list[dict]) -> dict:
    """A reviewed intake card becomes a patient (new or existing) plus a screening visit."""
    parts = (values.get("full_name") or "").split()
    first, last = (" ".join(parts[:-1]), parts[-1]) if len(parts) > 1 else ("", parts[0] if parts else "(Unknown)")
    dob = _iso(values.get("date_of_birth"))
    phone = values.get("phone")
    patient_id = find_patient(first, last, dob, phone)
    is_new = patient_id is None
    sex = {"Male": "M", "Female": "F", "Other": "X"}.get(values.get("gender") or "")
    if is_new:
        patient_id = create_patient({
            "first_name": first, "last_name": last, "dob": dob, "sex": sex, "phone": phone,
            "conditions": values.get("medical_conditions"), "medications": values.get("current_medications"),
        }, source="card scan")
    vitals = {k: values.get(k) for k in (
        "height_ft", "height_in", "weight_lbs", "bp_systolic", "bp_diastolic", "heart_rate",
        "respiratory_rate", "spo2", "temperature", "temperature_unit", "blood_glucose", "bmi",
        "smoking", "alcohol", "physical_activity") if values.get(k)}
    note_lines = [f"Health fair screening (card collected by {values.get('collected_by') or 'staff'})."]
    if values.get("medical_conditions"):
        note_lines.append(f"Reported conditions: {values['medical_conditions']}.")
    if values.get("current_medications"):
        note_lines.append(f"Reported medications: {values['current_medications']}.")
    if values.get("notes"):
        note_lines.append(f"Notes: {values['notes']}.")
    note_lines += [f"Screening flag ({a['level'].replace('_', '-')}): {a['text']}" for a in alerts]
    encounter_id = create_encounter({
        "patient_id": patient_id, "date": _iso(values.get("visit_date")), "type": "screening",
        "vitals": vitals, "note": "\n".join(note_lines), "status": "signed", "source_image": image, "alerts": alerts,
    })
    return {"patient_id": patient_id, "encounter_id": encounter_id, "new_patient": is_new}


def _iso(mmddyyyy: str | None) -> str | None:
    if not mmddyyyy:
        return None
    try:
        return datetime.strptime(mmddyyyy, "%m/%d/%Y").date().isoformat()
    except ValueError:
        return None
