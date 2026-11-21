"""Patient portal (Track B): what a patient sees, plus patient <-> clinic messages.

`messages` is the shared contract with Track A's Clinical Inbox:
  direction: to_clinic | to_patient
  kind:      message | refill_request | appointment_request
  status:    new | done            (for to_patient rows: new = unread by the patient)
  rx_id:     the prescription a refill request is for
Extra columns (Track A can ignore them): reply_to (thread parent), details (JSON, e.g. appointment
preferences), sender (who wrote a reply), done_at.
Track A can use the staff endpoints below instead of SQL: GET /api/messages, PATCH /api/messages/{id},
POST /api/messages/{id}/reply. Every change broadcasts `message_created` / `message_updated`.

No FOREIGN KEY on patient_id on purpose: clinic.reset() deletes patients with foreign keys ON, and a
FK here would make "Reset demo data" fail. seed() clears this table instead.
"""
import json
from datetime import date, datetime, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import clinic
from .events import broadcast

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    patient_id INTEGER,
    direction TEXT,             -- to_clinic | to_patient
    kind TEXT,                  -- message | refill_request | appointment_request
    subject TEXT, body TEXT,
    status TEXT,                -- new | done
    rx_id INTEGER,
    created_at TEXT,
    reply_to INTEGER, details TEXT, sender TEXT, done_at TEXT
);
"""
KINDS = ("message", "refill_request", "appointment_request")
TIME_OF_DAY = {"morning": "Morning (8 AM-12 PM)", "afternoon": "Afternoon (12-5 PM)",
               "evening": "Evening (5-7 PM)", "any": "Any time"}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def init() -> None:
    with clinic._conn() as con:
        con.executescript(SCHEMA)


def reset() -> None:
    init()
    with clinic._conn() as con:
        con.execute("DELETE FROM messages")


def _row(r) -> dict:
    d = dict(r)
    d["details"] = json.loads(d["details"]) if d.get("details") else None
    return d


# ---- storage -------------------------------------------------------------------
def create_message(patient_id: int, direction: str, kind: str, subject: str, body: str, *, rx_id: int | None = None,
                   reply_to: int | None = None, details: dict | None = None, sender: str | None = None,
                   status: str = "new", created_at: str | None = None) -> dict:
    with clinic._conn() as con:
        cur = con.execute(
            """INSERT INTO messages (patient_id, direction, kind, subject, body, status, rx_id, created_at,
                                     reply_to, details, sender) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (patient_id, direction, kind, subject, body, status, rx_id, created_at or _now(), reply_to,
             json.dumps(details) if details else None, sender),
        )
        msg_id = cur.lastrowid
    return get_message(msg_id)


def get_message(msg_id: int) -> dict | None:
    with clinic._conn() as con:
        r = con.execute(
            """SELECT m.*, p.first_name, p.last_name, p.mrn, p.dob, r.drug AS rx_drug, r.strength AS rx_strength
               FROM messages m LEFT JOIN patients p ON p.id = m.patient_id
               LEFT JOIN prescriptions r ON r.id = m.rx_id WHERE m.id = ?""",
            (msg_id,),
        ).fetchone()
    return _row(r) if r else None


def list_messages(patient_id: int | None = None, status: str | None = None, kind: str | None = None,
                  direction: str | None = None) -> list[dict]:
    where, args = [], []
    for col, val in (("m.patient_id", patient_id), ("m.status", status), ("m.kind", kind), ("m.direction", direction)):
        if val is not None:
            where.append(f"{col} = ?")
            args.append(val)
    with clinic._conn() as con:
        rows = con.execute(
            f"""SELECT m.*, p.first_name, p.last_name, p.mrn, p.dob, r.drug AS rx_drug, r.strength AS rx_strength
                FROM messages m LEFT JOIN patients p ON p.id = m.patient_id
                LEFT JOIN prescriptions r ON r.id = m.rx_id
                {('WHERE ' + ' AND '.join(where)) if where else ''} ORDER BY m.created_at DESC, m.id DESC""",
            args,
        ).fetchall()
    return [_row(r) for r in rows]


def set_status(msg_id: int, status: str) -> None:
    with clinic._conn() as con:
        con.execute("UPDATE messages SET status = ?, done_at = ? WHERE id = ?",
                    (status, _now() if status == "done" else None, msg_id))


# ---- what the patient sees -------------------------------------------------------
def portal_view(patient_id: int) -> dict | None:
    p = clinic.get_patient(patient_id)
    if p is None:
        return None
    now = datetime.now().isoformat(timespec="seconds")
    today = date.today().isoformat()
    appts = p["appointments"]
    reasons = {a["id"]: a["reason"] for a in appts}
    upcoming = sorted([a for a in appts if a["status"] in ("booked", "checked_in", "in_visit") and a["start"][:10] >= today],
                      key=lambda a: a["start"])
    past_appts = [a for a in appts if a not in upcoming and a["start"] < now]

    # Only finished (signed) visits are shown to the patient; unsigned notes are still drafts.
    visits = []
    for e in p["encounters"]:
        if e["status"] != "signed":
            continue
        visits.append({
            "id": e["id"], "date": e["date"], "type": e["type"], "provider_name": e["provider_name"],
            "reason": reasons.get(e["appointment_id"]), "summary": e.get("summary"),
            "note": e["note"], "vitals": e["vitals"],
            "alerts": json.loads(e["alerts"]) if e.get("alerts") else [],
        })

    msgs = list_messages(patient_id=patient_id)
    open_refills = {m["rx_id"] for m in msgs if m["kind"] == "refill_request" and m["status"] == "new"}
    rxs = [{**r, "refill_requested": r["id"] in open_refills} for r in p["prescriptions"]]
    return {
        "patient": {k: p[k] for k in ("id", "mrn", "first_name", "last_name", "dob", "sex", "phone", "email", "address",
                                      "city", "state", "zip", "payer_name", "member_id", "group_number", "pharmacy_id",
                                      "pharmacy_name", "allergies", "conditions", "medications")},
        "upcoming": upcoming,
        "past_appointments": past_appts[:10],
        "visits": visits,
        "prescriptions": rxs,
        "messages": msgs,
        "unread": sum(m["direction"] == "to_patient" and m["status"] == "new" for m in msgs),
        "appointment_requests": [m for m in msgs if m["kind"] == "appointment_request"],
    }


# ---- demo data --------------------------------------------------------------------
def seed(patient_ids: list[int]) -> None:
    """Called at the end of seed.seed(). patient_ids are in seed.PATIENTS order."""
    reset()
    now = datetime.now()
    ago = lambda **kw: (now - timedelta(**kw)).isoformat(timespec="seconds")
    maria, james, aisha, linda = patient_ids[0], patient_ids[1], patient_ids[2], patient_ids[4]

    # An answered question (shows a full conversation in Maria's portal)
    q = create_message(maria, "to_clinic", "message", "Best time to take lisinopril?",
                       "Hi, is it better to take my lisinopril in the morning or at night? Sometimes I feel a bit dizzy "
                       "after taking it. Thank you, Maria", status="done", created_at=ago(days=3, hours=2))
    create_message(maria, "to_patient", "message", "Re: Best time to take lisinopril?",
                   "Hi Maria, morning is best for most people. Mild dizziness can happen when you stand up quickly, so "
                   "get up slowly. If the dizziness gets worse or you faint, call us right away. We'll check your blood "
                   "pressure at today's visit.", reply_to=q["id"], sender="Dr. Amina Rahman's care team",
                   status="done", created_at=ago(days=3))

    # New items waiting for the clinic (Track A's Clinical Inbox / the front desk)
    with clinic._conn() as con:
        r = con.execute("SELECT id, drug, strength FROM prescriptions WHERE patient_id = ? AND drug = 'Metformin'",
                        (james,)).fetchone()
    if r:
        create_message(james, "to_clinic", "refill_request", f"Refill request: {r['drug']} {r['strength']}",
                       "I have about 5 days of metformin left. Please send the refill to Main Street Rx.",
                       rx_id=r["id"], created_at=ago(hours=1, minutes=10))
    create_message(aisha, "to_clinic", "message", "Still wheezing at night",
                   "I finished the prednisone but I still wake up wheezing 2-3 nights a week and use my inhaler then. "
                   "Should I come in sooner than planned?", created_at=ago(minutes=40))
    create_message(linda, "to_clinic", "appointment_request", "Appointment request: Thyroid follow-up",
                   "Thyroid follow-up after my dose change.\nPreferred: next week, mornings, any provider.",
                   details={"reason": "Thyroid follow-up after my dose change", "visit_type": "follow_up",
                            "preferred_date": (date.today() + timedelta(days=7)).isoformat(),
                            "time_of_day": "morning", "provider_id": None},
                   created_at=ago(hours=2))


# ---- API --------------------------------------------------------------------------
router = APIRouter(prefix="/api")


def _patient_or_404(patient_id: int) -> dict:
    p = clinic.get_patient(patient_id)
    if p is None:
        raise HTTPException(404, "Patient not found")
    return p


def _announce(msg: dict, created: bool = True) -> dict:
    broadcast({"type": "message_created" if created else "message_updated", "message": msg,
               "patient_id": msg["patient_id"]})
    return msg


@router.get("/portal/{patient_id}")
def portal(patient_id: int):
    view = portal_view(patient_id)
    if view is None:
        raise HTTPException(404, "Patient not found")
    return view


class PortalMessage(BaseModel):
    subject: str
    body: str
    reply_to: int | None = None


@router.post("/portal/{patient_id}/messages")
def send_message(patient_id: int, body: PortalMessage):
    _patient_or_404(patient_id)
    subject, text = body.subject.strip(), body.body.strip()
    if not subject or not text:
        raise HTTPException(400, "Please add a subject and a message")
    if len(subject) > 120 or len(text) > 4000:
        raise HTTPException(400, "That message is too long")
    return _announce(create_message(patient_id, "to_clinic", "message", subject, text, reply_to=body.reply_to))


class RefillBody(BaseModel):
    rx_id: int
    note: str = ""
    pharmacy_id: int | None = None


@router.post("/portal/{patient_id}/refill-requests")
def request_refill(patient_id: int, body: RefillBody):
    p = _patient_or_404(patient_id)
    rx = clinic.get_prescription(body.rx_id)
    if rx is None or rx["patient_id"] != patient_id:
        raise HTTPException(404, "Prescription not found")
    if any(m["rx_id"] == body.rx_id and m["status"] == "new"
           for m in list_messages(patient_id=patient_id, kind="refill_request")):
        raise HTTPException(409, "A refill for this medication is already waiting for your care team")
    pharmacy = next((ph for ph in clinic.pharmacies() if ph["id"] == (body.pharmacy_id or rx["pharmacy_id"])), None)
    text = f"Please refill {rx['drug']} {rx['strength']} ({rx['sig']})."
    if pharmacy:
        text += f"\nPharmacy: {pharmacy['name']}."
    if body.note.strip():
        text += f"\nNote from {p['first_name']}: {body.note.strip()[:1000]}"
    return _announce(create_message(patient_id, "to_clinic", "refill_request",
                                    f"Refill request: {rx['drug']} {rx['strength']}", text, rx_id=rx["id"],
                                    details={"pharmacy_id": pharmacy and pharmacy["id"]}))


class AppointmentRequest(BaseModel):
    reason: str
    visit_type: str = "follow_up"
    preferred_date: str          # YYYY-MM-DD
    time_of_day: str = "any"
    provider_id: int | None = None


@router.post("/portal/{patient_id}/appointment-requests")
def request_appointment(patient_id: int, body: AppointmentRequest):
    _patient_or_404(patient_id)
    reason = body.reason.strip()
    if not reason:
        raise HTTPException(400, "Tell us the reason for the visit")
    try:
        when = date.fromisoformat(body.preferred_date)
    except ValueError:
        raise HTTPException(400, "Pick a preferred date")
    if when < date.today() or when > date.today() + timedelta(days=180):
        raise HTTPException(400, "Pick a date between today and 6 months from now")
    if body.time_of_day not in TIME_OF_DAY:
        raise HTTPException(400, "Unknown time of day")
    provider = next((pr for pr in clinic.providers() if pr["id"] == body.provider_id), None)
    text = (f"{reason[:1000]}\nPreferred: {when.strftime('%a %b %d, %Y').replace(' 0', ' ')}, "
            f"{TIME_OF_DAY[body.time_of_day].lower()}, {provider['name'] if provider else 'any provider'}.")
    details = {**body.model_dump(), "reason": reason}
    return _announce(create_message(patient_id, "to_clinic", "appointment_request",
                                    f"Appointment request: {reason[:60]}", text, details=details))


@router.post("/portal/{patient_id}/messages/read")
def mark_read(patient_id: int):
    """The patient opened their messages: clinic replies are no longer 'new'."""
    with clinic._conn() as con:
        con.execute("UPDATE messages SET status = 'done', done_at = ? WHERE patient_id = ? AND direction = 'to_patient' "
                    "AND status = 'new'", (_now(), patient_id))
    return {"ok": True}


# ---- staff side (front desk / Track A's Clinical Inbox) ------------------------------
@router.get("/messages")
def messages(status: str | None = None, kind: str | None = None, direction: str | None = None,
             patient_id: int | None = None):
    return list_messages(patient_id=patient_id, status=status, kind=kind, direction=direction)


class StatusBody(BaseModel):
    status: str


@router.patch("/messages/{msg_id}")
def change_status(msg_id: int, body: StatusBody):
    if body.status not in ("new", "done"):
        raise HTTPException(400, "Status must be 'new' or 'done'")
    if get_message(msg_id) is None:
        raise HTTPException(404, "Message not found")
    set_status(msg_id, body.status)
    return _announce(get_message(msg_id), created=False)


class ReplyBody(BaseModel):
    body: str
    sender: str = "Your care team"
    mark_done: bool = True


@router.post("/messages/{msg_id}/reply")
def reply(msg_id: int, body: ReplyBody):
    """Clinic answers a patient: a to_patient message the portal shows live (and the original is marked done)."""
    original = get_message(msg_id)
    if original is None:
        raise HTTPException(404, "Message not found")
    if not body.body.strip():
        raise HTTPException(400, "The reply is empty")
    subject = original["subject"] if original["subject"].startswith("Re: ") else f"Re: {original['subject']}"
    msg = create_message(original["patient_id"], "to_patient", original["kind"], subject, body.body.strip(),
                         reply_to=msg_id, sender=body.sender.strip() or "Your care team", rx_id=original["rx_id"])
    if body.mark_done:
        set_status(msg_id, "done")
        _announce(get_message(msg_id), created=False)
    return _announce(msg)
