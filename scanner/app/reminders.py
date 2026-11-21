"""Appointment reminder emails + patient confirmations (Track B).

Each reminder says when/where/with whom, what to bring, what's expected at check-in (copay from the
eligibility answer), warns about insurance problems, mentions any old balance, and has two links:
"Confirm" and "Need to reschedule?". Rescheduling creates an appointment_request in the portal's
`messages` table, so it lands with the front desk / Track A's Clinical Inbox.

Email safety: reminders are only ever emailed to the team's demo inbox (mailer.recipient(), the same
override the e-prescriptions use), never to the fictional patients' addresses. With email off (no SMTP
in .env) they are saved as previews that staff can open in the app.
No FOREIGN KEY on patient_id: clinic.reset() deletes patients with foreign keys ON; seed() clears this table.
"""
import asyncio
import html
import os
import secrets
from datetime import date, datetime, timedelta
from email.message import EmailMessage

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from . import clinic, config, eligibility, ledger, mailer, portal
from .events import broadcast

SCHEMA = """
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY,
    appointment_id INTEGER, patient_id INTEGER,
    status TEXT,                -- sent | preview (email off) | failed | none (answered in the portal, no reminder)
    sent_to TEXT, patient_email TEXT,
    subject TEXT, body_text TEXT, body_html TEXT,
    token TEXT UNIQUE,
    response TEXT,              -- confirmed | reschedule | NULL
    responded_at TEXT, responded_via TEXT, error TEXT, created_at TEXT
);
"""
APP_URL = os.environ.get("APP_URL", "http://127.0.0.1:8000")   # links in the email open the app on this laptop
CLINIC = {"name": "Plano Community Clinic", "address": "100 Example Pkwy, Suite 200, Plano, TX 75074",
          "phone": "(972) 555-0100"}
MAX_PER_BATCH = 20


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def init() -> None:
    with clinic._conn() as con:
        con.executescript(SCHEMA)


def reset() -> None:
    init()
    with clinic._conn() as con:
        con.execute("DELETE FROM reminders")


# ---- the email --------------------------------------------------------------------------------
def _when(start: str) -> tuple[str, str]:
    d = datetime.fromisoformat(start)
    return d.strftime("%A, %B %d").replace(" 0", " "), d.strftime("%I:%M %p").lstrip("0")


def compose(appt_id: int, token: str = "PREVIEW") -> dict:
    a = clinic.get_appointment(appt_id)
    p = clinic.get_patient(a["patient_id"])
    prov = next((x for x in clinic.providers() if x["id"] == a["provider_id"]), {})
    day, time = _when(a["start"])
    relative = {0: "today", 1: "tomorrow"}.get((date.fromisoformat(a["start"][:10]) - date.today()).days, f"on {day}")
    copay = ledger.copay_status(appt_id)
    elig = eligibility.latest(p["id"])
    insurance_problem = elig and not elig.get("stale") and elig["status"] in ("inactive", "not_found", "missing_id")
    confirm = f"{APP_URL}/r/{token}?do=confirm"
    resched = f"{APP_URL}/r/{token}?do=reschedule"
    portal_url = f"{APP_URL}/portal?patient={p['id']}"
    who = f"{prov.get('name', 'your provider')}{', ' + prov['credentials'] if prov.get('credentials') else ''}"

    pay_line = (f"Expected at check-in: {copay['label'].lower()} ${copay['due']:.2f}." if copay and copay["due"] > 0
                else "Nothing is due at check-in; we'll bill you after your insurance pays.")
    extra = []
    if insurance_problem:
        extra.append(f"IMPORTANT: we couldn't confirm your insurance ({elig['label']}). Please bring your current insurance card.")
    if copay and copay["balance"] > 0:
        extra.append(f"You also have a balance of ${copay['balance']:.2f} from earlier visits. You can pay it online in the patient portal.")

    subject = f"Reminder: your appointment {relative} at {time} with {prov.get('name', 'your provider')}"
    text = f"""Hi {p['first_name']},

This is a reminder of your appointment {relative}:

  {day} at {time} ({a['duration_min']} min)
  {who}{' - ' + a['reason'] if a['reason'] else ''}
  {CLINIC['name']}, {CLINIC['address']}

Confirm:            {confirm}
Need to reschedule? {resched}

Please bring a photo ID, your insurance card and a list of your medicines, and arrive 10 minutes early.
{pay_line}
{chr(10).join(extra)}

Questions? Call {CLINIC['phone']} or message us in the patient portal: {portal_url}

-- DEMO: fictional patient. In the real product this goes to the patient's own email or phone.
   (Demo links open the app on the clinic laptop.)
"""
    e = html.escape
    btn = "display:inline-block;padding:11px 20px;border-radius:8px;font-weight:700;text-decoration:none;margin:4px 6px 4px 0"
    body_html = f"""<!doctype html><html><body style="margin:0;background:#f4f7f7;font-family:Segoe UI,Arial,sans-serif;color:#17202b">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f7f7;padding:20px 0"><tr><td align="center">
<table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;background:#fff;border-radius:12px;overflow:hidden;border:1px solid #dfe3e9">
<tr><td style="background:#0f766e;color:#fff;padding:16px 24px;font-size:18px;font-weight:700">&#10010; {e(CLINIC['name'])}</td></tr>
<tr><td style="padding:24px">
  <p style="margin:0 0 12px;font-size:16px">Hi {e(p['first_name'])},</p>
  <p style="margin:0 0 16px">This is a reminder of your appointment <b>{e(relative)}</b>:</p>
  <div style="border:1px solid #dfe3e9;border-radius:10px;padding:14px 16px;margin-bottom:18px">
    <div style="font-size:18px;font-weight:700">{e(day)} at {e(time)}</div>
    <div style="margin-top:4px">{e(who)}{(' &middot; ' + e(a['reason'])) if a['reason'] else ''}</div>
    <div style="margin-top:4px;color:#5f6b7a;font-size:14px">{e(CLINIC['name'])}, {e(CLINIC['address'])}</div>
  </div>
  <a href="{e(confirm)}" style="{btn};background:#0f766e;color:#fff">&#10003; Confirm</a>
  <a href="{e(resched)}" style="{btn};background:#fff;color:#0f766e;border:1px solid #0f766e">Need to reschedule?</a>
  <p style="margin:18px 0 6px;font-size:14px"><b>Please bring</b> a photo ID, your insurance card and a list of your medicines. Arrive 10 minutes early.</p>
  <p style="margin:0 0 6px;font-size:14px">&#128181; {e(pay_line)}</p>
  {''.join(f'<p style="margin:8px 0;padding:8px 12px;border-radius:8px;background:#fff4dc;font-size:14px">{e(x)}</p>' for x in extra)}
  <p style="margin:16px 0 0;font-size:14px">Questions? Call {e(CLINIC['phone'])} or <a href="{e(portal_url)}" style="color:#0f766e">message us in the patient portal</a>.</p>
</td></tr>
<tr><td style="background:#fff7e0;color:#7a5300;font-size:12px;padding:10px 24px">DEMO: fictional patient. In the real product this goes to
the patient's own email or phone. Demo links open the app on the clinic laptop.</td></tr>
</table></td></tr></table></body></html>"""
    return {"subject": subject, "text": text, "html": body_html, "patient": p, "appointment": a}


# ---- storage ----------------------------------------------------------------------------------
def _row(r) -> dict:
    return dict(r)


def latest_for(appt_id: int) -> dict | None:
    with clinic._conn() as con:
        r = con.execute("SELECT * FROM reminders WHERE appointment_id = ? ORDER BY id DESC LIMIT 1", (appt_id,)).fetchone()
    return _row(r) if r else None


def response_for(appt_id: int) -> dict | None:
    """The patient's latest answer (confirm / reschedule) to any reminder for this appointment."""
    with clinic._conn() as con:
        r = con.execute("""SELECT response, responded_at, responded_via FROM reminders WHERE appointment_id = ?
                           AND response IS NOT NULL ORDER BY responded_at DESC LIMIT 1""", (appt_id,)).fetchone()
    return dict(r) if r else None


def _summary(appt_id: int) -> dict:
    last, resp = latest_for(appt_id), response_for(appt_id)
    return {"reminder": last and {k: last[k] for k in ("id", "status", "created_at", "sent_to", "error")},
            "response": resp and resp["response"], "responded_at": resp and resp["responded_at"],
            "responded_via": resp and resp["responded_via"]}


def for_day(day: str) -> list[dict]:
    out = []
    for a in clinic.list_appointments(day):
        if a["status"] in ("cancelled", "no_show"):
            continue
        p = clinic.get_patient(a["patient_id"])
        out.append({"appointment_id": a["id"], "patient_id": a["patient_id"], "name": f"{a['first_name']} {a['last_name']}",
                    "start": a["start"], "provider": a["provider_name"], "reason": a["reason"], "status": a["status"],
                    "patient_email": p.get("email"), "can_send": a["status"] == "booked", **_summary(a["id"])})
    return out


def _store(appt_id: int, mail: dict, token: str, status: str, sent_to: str | None = None, error: str | None = None,
           created_at: str | None = None) -> dict:
    with clinic._conn() as con:
        cur = con.execute(
            """INSERT INTO reminders (appointment_id, patient_id, status, sent_to, patient_email, subject, body_text, body_html,
                                      token, error, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (appt_id, mail["patient"]["id"], status, sent_to, mail["patient"].get("email"), mail["subject"], mail["text"],
             mail["html"], token, error, created_at or _now()))
        return _row(con.execute("SELECT * FROM reminders WHERE id = ?", (cur.lastrowid,)).fetchone())


async def send(appt_id: int) -> dict:
    """Email the reminder (demo inbox only) or, with email off, save it as a preview."""
    token = secrets.token_urlsafe(12)
    mail = compose(appt_id, token)
    status, error, sent_to = "preview", None, None
    if mailer.enabled():
        msg = EmailMessage()
        msg["Subject"] = mail["subject"]
        msg["From"] = config.SMTP_USER
        msg["To"] = sent_to = mailer.recipient()          # demo inbox only, never the patient's address
        msg.set_content(mail["text"])
        msg.add_alternative(mail["html"], subtype="html")
        try:
            await asyncio.to_thread(mailer._send, msg)
            status = "sent"
        except Exception as e:      # keep the reminder (preview) and show what went wrong
            status, error = "failed", str(e)[:300]
    return _store(appt_id, mail, token, status, sent_to, error)


def respond(token: str, answer: str, via: str = "email") -> dict | None:
    with clinic._conn() as con:
        r = con.execute("SELECT * FROM reminders WHERE token = ?", (token,)).fetchone()
        if not r:
            return None
        con.execute("UPDATE reminders SET response = ?, responded_at = ?, responded_via = ? WHERE id = ?",
                    (answer, _now(), via, r["id"]))
    rem = _row(r)
    appt = clinic.get_appointment(rem["appointment_id"])
    if answer == "reschedule" and appt:
        day, time = _when(appt["start"])
        msg = portal.create_message(
            appt["patient_id"], "to_clinic", "appointment_request", "Reschedule request",
            f"I can't make my appointment on {day} at {time}. Please help me find a new time.",
            details={"reason": "Reschedule", "visit_type": appt["visit_type"], "appointment_id": appt["id"],
                     "preferred_date": None, "time_of_day": "any", "provider_id": appt["provider_id"]})
        broadcast({"type": "message_created", "patient_id": appt["patient_id"], "message": msg})
    broadcast({"type": "appointment_confirmed", "appointment_id": rem["appointment_id"], "response": answer,
               "patient_id": rem["patient_id"], "day": appt and appt["start"][:10]})
    return {**rem, "response": answer, "appointment": appt}


def seed() -> None:
    """Yesterday evening's reminders for today's booked patients; a few already confirmed."""
    reset()
    evening = (datetime.now().replace(hour=17, minute=0, second=0, microsecond=0) - timedelta(days=1)).isoformat(timespec="seconds")
    confirmed = {"Robert", "Linda", "Omar"}
    for a in clinic.list_appointments(date.today().isoformat()):
        if a["status"] in ("cancelled", "no_show"):
            continue
        token = secrets.token_urlsafe(12)
        rem = _store(a["id"], compose(a["id"], token), token, "sent", mailer.recipient() or None, created_at=evening)
        if a["first_name"] in confirmed:
            with clinic._conn() as con:
                con.execute("UPDATE reminders SET response = 'confirmed', responded_at = ?, responded_via = 'email' WHERE id = ?",
                            ((datetime.fromisoformat(evening) + timedelta(minutes=47)).isoformat(timespec="seconds"), rem["id"]))



# ---- API ---------------------------------------------------------------------------------------
router = APIRouter()


@router.get("/api/reminders")
def reminders_for_day(day: str | None = None):
    day = day or (date.today() + timedelta(days=1)).isoformat()
    return {"day": day, "email_enabled": mailer.enabled(), "sent_to": mailer.recipient() or None, "appointments": for_day(day)}


@router.get("/api/reminders/preview/{appt_id}")
def preview(appt_id: int):
    if clinic.get_appointment(appt_id) is None:
        raise HTTPException(404, "Appointment not found")
    m = compose(appt_id)
    return {"subject": m["subject"], "html": m["html"], "text": m["text"]}


@router.get("/api/reminders/{rem_id}")
def reminder(rem_id: int):
    with clinic._conn() as con:
        r = con.execute("SELECT * FROM reminders WHERE id = ?", (rem_id,)).fetchone()
    if not r:
        raise HTTPException(404, "Reminder not found")
    return _row(r)


class SendBody(BaseModel):
    appointment_ids: list[int]
    resend: bool = False


@router.post("/api/reminders/send")
async def send_reminders(body: SendBody):
    if not body.appointment_ids:
        raise HTTPException(400, "Pick at least one appointment")
    if len(body.appointment_ids) > MAX_PER_BATCH:
        raise HTTPException(400, f"At most {MAX_PER_BATCH} reminders at a time")
    results, skipped = [], []
    for aid in dict.fromkeys(body.appointment_ids):
        a = clinic.get_appointment(aid)
        if a is None:
            raise HTTPException(404, f"Appointment {aid} not found")
        if a["status"] != "booked":
            skipped.append({"appointment_id": aid, "reason": f"appointment is {a['status'].replace('_', ' ')}"})
            continue
        last = latest_for(aid)
        if last and last["status"] != "failed" and not body.resend:
            skipped.append({"appointment_id": aid, "reason": "already reminded"})
            continue
        results.append(await send(aid))
    days = {clinic.get_appointment(r["appointment_id"])["start"][:10] for r in results}
    for d in days:
        broadcast({"type": "reminders_sent", "day": d, "count": len(results)})
    return {"sent": sum(r["status"] == "sent" for r in results), "previews": sum(r["status"] == "preview" for r in results),
            "failed": [{"appointment_id": r["appointment_id"], "error": r["error"]} for r in results if r["status"] == "failed"],
            "skipped": skipped, "email_enabled": mailer.enabled(), "sent_to": mailer.recipient() or None,
            "reminders": [{k: r[k] for k in ("id", "appointment_id", "status", "subject", "created_at")} for r in results]}


class ConfirmBody(BaseModel):
    response: str = "confirmed"      # confirmed | reschedule
    via: str = "portal"


@router.post("/api/appointments/{appt_id}/confirm")
def confirm_appointment(appt_id: int, body: ConfirmBody):
    """Patient answers from the portal (no email needed): records it like a reminder click."""
    a = clinic.get_appointment(appt_id)
    if a is None:
        raise HTTPException(404, "Appointment not found")
    if body.response not in ("confirmed", "reschedule") or body.via not in ("portal", "phone"):
        raise HTTPException(400, "Unknown response")
    if a["status"] in ("cancelled", "no_show", "completed"):
        raise HTTPException(409, f"This appointment is {a['status'].replace('_', ' ')}")
    rem = latest_for(appt_id)
    if rem is None:   # answered in the portal without any reminder: keep a record so the schedule shows it
        token = secrets.token_urlsafe(12)
        rem = _store(appt_id, compose(appt_id, token), token, "none")
    out = respond(rem["token"], body.response, via=body.via)
    return {"appointment_id": appt_id, "response": out["response"]}


PAGE = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title></head><body style="margin:0;font-family:Segoe UI,Arial,sans-serif;background:#f4f7f7;color:#17202b">
<div style="max-width:480px;margin:48px auto;background:#fff;border:1px solid #dfe3e9;border-radius:14px;padding:28px;text-align:center">
<div style="width:60px;height:60px;border-radius:50%;background:{color};color:#fff;font-size:32px;line-height:60px;margin:0 auto 14px">{icon}</div>
<h1 style="font-size:22px;margin:0 0 8px">{title}</h1><p style="margin:0 0 18px;color:#4a5565">{body}</p>
<a href="{portal}" style="display:inline-block;padding:10px 18px;border-radius:8px;background:#0f766e;color:#fff;text-decoration:none;font-weight:600">Open the patient portal</a>
<p style="margin:18px 0 0;font-size:12px;color:#7a5300">Demo: fictional patient.</p></div></body></html>"""


@router.get("/r/{token}", include_in_schema=False)
def reminder_link(token: str, do: str = "confirm"):
    """The links inside the reminder email."""
    if do not in ("confirm", "reschedule"):
        do = "confirm"
    out = respond(token, "confirmed" if do == "confirm" else "reschedule")
    if out is None or out["appointment"] is None:
        return HTMLResponse(PAGE.format(title="Link not found", color="#c4291c", icon="!", portal="/portal",
                                        body="This reminder link is no longer valid. Please call us or use the patient portal."),
                            status_code=404)
    a = out["appointment"]
    day, time = _when(a["start"])
    portal_url = f"/portal?patient={a['patient_id']}#appointments"
    if do == "confirm":
        return HTMLResponse(PAGE.format(title="You're confirmed!", color="#1f8a4c", icon="&#10003;", portal=portal_url,
                                        body=f"Thanks! See you {html.escape(day)} at {html.escape(time)}."))
    return HTMLResponse(PAGE.format(title="We got your request", color="#0f766e", icon="&#9993;", portal=portal_url,
                                    body=f"The front desk will contact you to find a new time for your {html.escape(day)} "
                                         f"{html.escape(time)} appointment."))
