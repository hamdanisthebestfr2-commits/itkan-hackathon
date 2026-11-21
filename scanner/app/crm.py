"""Mock CRM stored in SQLite, shaped like Salesforce.

Objects and field names follow Salesforce conventions (Contact + a custom
Health_Screening__c object), so a real org could be wired in later by mapping
these same records onto the Salesforce REST API.
"""
import json
import random
import sqlite3
import string
from datetime import date, datetime

from . import config
from .validate import calc_bmi

_ID_CHARS = string.ascii_letters + string.digits

SCHEMA = """
CREATE TABLE IF NOT EXISTS Contact (
    Id TEXT PRIMARY KEY,
    FirstName TEXT, LastName TEXT, Birthdate TEXT, Phone TEXT, Gender__c TEXT,
    CreatedDate TEXT
);
CREATE TABLE IF NOT EXISTS Health_Screening__c (
    Id TEXT PRIMARY KEY,
    Name TEXT,
    Contact__c TEXT REFERENCES Contact(Id),
    Screening_Date__c TEXT, Event_Name__c TEXT, Card_Patient_ID__c TEXT,
    Height_Ft__c INTEGER, Height_In__c INTEGER, Weight_Lbs__c REAL,
    Systolic_BP__c INTEGER, Diastolic_BP__c INTEGER, Heart_Rate__c INTEGER,
    Respiratory_Rate__c INTEGER, SpO2__c INTEGER,
    Temperature__c REAL, Temperature_Unit__c TEXT, Blood_Glucose__c INTEGER,
    BMI_Recorded__c REAL, BMI_Calculated__c REAL,
    Smoker__c TEXT, Alcohol_Use__c TEXT, Physically_Active__c TEXT,
    Medical_Conditions__c TEXT, Current_Medications__c TEXT, Notes__c TEXT,
    Collected_By__c TEXT,
    Needs_Follow_Up__c INTEGER, Alerts__c TEXT,
    Source_Image__c TEXT, Fields_Auto_Accepted__c INTEGER, Fields_Corrected__c INTEGER,
    Processing_Seconds__c REAL,
    CreatedDate TEXT
);
"""


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init() -> None:
    with _conn() as con:
        con.executescript(SCHEMA)


def _sf_id(prefix: str) -> str:
    return prefix + "".join(random.choices(_ID_CHARS, k=15))


def _iso(mmddyyyy: str | None) -> str | None:
    if not mmddyyyy:
        return None
    try:
        return datetime.strptime(mmddyyyy, "%m/%d/%Y").date().isoformat()
    except ValueError:
        return None


def _int(v):
    try:
        return int(float(v)) if v not in (None, "") else None
    except ValueError:
        return None


def _float(v):
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None


def _split_name(full: str | None) -> tuple[str, str]:
    parts = (full or "").split()
    if not parts:
        return "", "(Unknown)"
    return " ".join(parts[:-1]), parts[-1]


def find_duplicate(con, first: str, last: str, birthdate: str | None, phone: str | None) -> str | None:
    row = con.execute(
        """SELECT Id FROM Contact
           WHERE lower(LastName) = lower(?) AND lower(FirstName) = lower(?)
             AND (Birthdate = ? OR Phone = ?)""",
        (last, first, birthdate, phone),
    ).fetchone()
    return row["Id"] if row else None


def save_screening(values: dict, meta: dict) -> dict:
    """values: final reviewed field values (card field keys). meta: alerts, image, stats.
    Returns ids and whether the contact was new."""
    first, last = _split_name(values.get("full_name"))
    birthdate, phone = _iso(values.get("date_of_birth")), values.get("phone")
    now = datetime.now().isoformat(timespec="seconds")
    with _conn() as con:
        contact_id = find_duplicate(con, first, last, birthdate, phone)
        is_new = contact_id is None
        if is_new:
            contact_id = _sf_id("003")
            con.execute(
                "INSERT INTO Contact VALUES (?,?,?,?,?,?,?)",
                (contact_id, first, last, birthdate, phone, values.get("gender"), now),
            )
        else:  # keep contact details current
            con.execute(
                "UPDATE Contact SET Phone = coalesce(?, Phone), Gender__c = coalesce(?, Gender__c) WHERE Id = ?",
                (phone, values.get("gender"), contact_id),
            )
        count = con.execute("SELECT count(*) FROM Health_Screening__c").fetchone()[0]
        screening_id = _sf_id("a01")
        con.execute(
            "INSERT INTO Health_Screening__c VALUES (" + ",".join("?" * 33) + ")",
            (
                screening_id, f"HS-{count + 1:05d}", contact_id,
                _iso(values.get("visit_date")) or date.today().isoformat(), config.EVENT_NAME, values.get("patient_id"),
                _int(values.get("height_ft")), _int(values.get("height_in")), _float(values.get("weight_lbs")),
                _int(values.get("bp_systolic")), _int(values.get("bp_diastolic")), _int(values.get("heart_rate")),
                _int(values.get("respiratory_rate")), _int(values.get("spo2")),
                _float(values.get("temperature")), values.get("temperature_unit"), _int(values.get("blood_glucose")),
                _float(values.get("bmi")), calc_bmi(values.get("height_ft"), values.get("height_in"), values.get("weight_lbs")),
                values.get("smoking"), values.get("alcohol"), values.get("physical_activity"),
                values.get("medical_conditions"), values.get("current_medications"), values.get("notes"),
                values.get("collected_by"),
                int(bool(meta.get("needs_follow_up"))), json.dumps(meta.get("alerts", [])),
                meta.get("image"), meta.get("auto_accepted", 0), meta.get("corrected", 0),
                meta.get("seconds"), now,
            ),
        )
    return {"contact_id": contact_id, "screening_id": screening_id, "new_contact": is_new}


def _screening_dict(row) -> dict:
    d = dict(row)
    d["Alerts__c"] = json.loads(d["Alerts__c"] or "[]")
    return d


def list_contacts(q: str = "") -> list[dict]:
    like = f"%{q.lower()}%"
    with _conn() as con:
        rows = con.execute(
            """SELECT c.*, s.Id AS LastScreeningId, s.Screening_Date__c, s.Systolic_BP__c, s.Diastolic_BP__c,
                      s.SpO2__c, s.Needs_Follow_Up__c, s.CreatedDate AS LastScreened,
                      (SELECT count(*) FROM Health_Screening__c x WHERE x.Contact__c = c.Id) AS Screenings
               FROM Contact c
               LEFT JOIN Health_Screening__c s ON s.Id = (
                   SELECT Id FROM Health_Screening__c WHERE Contact__c = c.Id ORDER BY CreatedDate DESC LIMIT 1)
               WHERE lower(c.FirstName || ' ' || c.LastName) LIKE ? OR c.Phone LIKE ?
               ORDER BY s.CreatedDate DESC""",
            (like, like),
        ).fetchall()
    return [dict(r) for r in rows]


def get_contact(contact_id: str) -> dict | None:
    with _conn() as con:
        c = con.execute("SELECT * FROM Contact WHERE Id = ?", (contact_id,)).fetchone()
        if not c:
            return None
        screenings = con.execute(
            "SELECT * FROM Health_Screening__c WHERE Contact__c = ? ORDER BY CreatedDate DESC", (contact_id,)
        ).fetchall()
    return {**dict(c), "screenings": [_screening_dict(s) for s in screenings]}


def stats() -> dict:
    with _conn() as con:
        r = con.execute(
            """SELECT count(*) AS cards, avg(Processing_Seconds__c) AS avg_seconds,
                      sum(Fields_Auto_Accepted__c) AS auto, sum(Fields_Corrected__c) AS corrected,
                      sum(Needs_Follow_Up__c) AS follow_ups
               FROM Health_Screening__c"""
        ).fetchone()
        patients = con.execute("SELECT count(*) FROM Contact").fetchone()[0]
    cards, auto, corrected = r["cards"] or 0, r["auto"] or 0, r["corrected"] or 0
    manual_minutes_per_card = 2.5  # rough hand-typing time for a 25-field card
    return {
        "cards": cards,
        "patients": patients,
        "avg_seconds": round(r["avg_seconds"] or 0, 1),
        "auto_rate": round(100 * auto / (auto + corrected)) if auto + corrected else None,
        "follow_ups": r["follow_ups"] or 0,
        "minutes_saved": round(cards * manual_minutes_per_card - (cards * (r["avg_seconds"] or 0)) / 60, 1),
    }


def reset() -> None:
    with _conn() as con:
        con.executescript("DELETE FROM Health_Screening__c; DELETE FROM Contact;")
