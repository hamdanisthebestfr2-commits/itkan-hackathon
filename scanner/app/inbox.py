"""Clinical Inbox (Track A3): one to-do list for the care team.

Items: lab results to review (labs.py) + patient messages, refill requests and appointment requests
from the portal (Track B's `messages` table, via portal.py functions/endpoints).
Actions here: review results (labs.py), approve/deny refills, AI-drafted replies. Plain replies and
"mark done" use Track B's endpoints (POST /api/messages/{id}/reply, PATCH /api/messages/{id}).
"""
import asyncio
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import ai, clinic, config, drugs, labs, mailer, portal
from .events import broadcast

router = APIRouter(prefix="/api")
KIND_LABEL = {"message": "Message", "refill_request": "Refill request", "appointment_request": "Appointment request"}


def items() -> list[dict]:
    out = []
    for o in labs.list_orders(status="resulted"):
        out.append({"type": "result", "id": o["id"], "patient_id": o["patient_id"],
                    "patient": f"{o['first_name']} {o['last_name']}", "mrn": o["mrn"],
                    "title": o["test_name"], "when": o["resulted_at"], "urgent": o["abnormal"] > 0,
                    "summary": (f"{o['abnormal']} abnormal value{'s' if o['abnormal'] != 1 else ''}: " +
                                ", ".join(f"{r['analyte']} {r['value']} {r['flag']}" for r in o["results"] if r["flag"]))
                               if o["abnormal"] else "All values in the normal range",
                    "order": o})
    for m in portal.list_messages(status="new", direction="to_clinic"):
        root = m["reply_to"] or m["id"]   # the whole conversation this message belongs to
        thread = [x for x in portal.list_messages(patient_id=m["patient_id"]) if root in (x["id"], x["reply_to"])]
        out.append({"type": m["kind"], "id": m["id"], "patient_id": m["patient_id"],
                    "patient": f"{m['first_name']} {m['last_name']}", "mrn": m["mrn"],
                    "title": m["subject"], "when": m["created_at"], "urgent": False,
                    "summary": (m["body"] or "")[:140], "message": m,
                    "thread": sorted(thread, key=lambda x: x["created_at"] or "")})
    # abnormal results first, then newest first
    return sorted(out, key=lambda x: (0 if x["urgent"] else 1, -_ts(x["when"])))


def _ts(iso: str | None) -> float:
    try:
        return datetime.fromisoformat(iso).timestamp()
    except (TypeError, ValueError):
        return 0.0


@router.get("/inbox")
def inbox():
    return items()


@router.get("/inbox/count")
def inbox_count():
    it = items()
    return {"total": len(it), "urgent": sum(1 for x in it if x["urgent"])}


# ---- refill requests -----------------------------------------------------------------
def _refill_or_404(msg_id: int) -> tuple[dict, dict]:
    m = portal.get_message(msg_id)
    if m is None or m["kind"] != "refill_request":
        raise HTTPException(404, "Refill request not found")
    if m["status"] != "new":
        raise HTTPException(409, "This request was already handled")
    rx = clinic.get_prescription(m["rx_id"]) if m["rx_id"] else None
    if rx is None:
        raise HTTPException(404, "The original prescription wasn't found")
    return m, rx


class ApproveBody(BaseModel):
    provider_id: int = 1
    pharmacy_id: int | None = None
    refills: int = 0
    note: str = ""


@router.post("/inbox/refills/{msg_id}/approve")
async def approve_refill(msg_id: int, body: ApproveBody):
    m, rx = _refill_or_404(msg_id)
    if rx["drug"] in drugs.SCHEDULE:
        raise HTTPException(409, f"{rx['drug']} is a controlled substance ({drugs.SCHEDULE[rx['drug']]}): open the "
                                 f"patient's chart and sign it with two-factor EPCS")
    p = clinic.get_patient(m["patient_id"])
    conflicts = drugs.allergy_conflicts(rx["drug"], p["allergies"])
    if conflicts:
        raise HTTPException(409, f"Allergy alert: patient is allergic to {', '.join(conflicts)}. Review in the chart")
    pharmacy_id = body.pharmacy_id or (m["details"] or {}).get("pharmacy_id") or rx["pharmacy_id"]
    new_id = clinic.create_prescription({"patient_id": rx["patient_id"], "provider_id": body.provider_id,
                                         "pharmacy_id": pharmacy_id, "drug": rx["drug"], "strength": rx["strength"],
                                         "sig": rx["sig"], "quantity": rx["quantity"], "refills": max(0, min(body.refills, 11))})
    new_rx = clinic.get_prescription(new_id)
    broadcast({"type": "rx_sent", "rx": new_rx})
    emailed = False
    if mailer.enabled():
        try:
            await asyncio.to_thread(mailer.send_prescription, new_rx)
            clinic.update_prescription(new_id, {"emailed": 1})
            emailed = True
            broadcast({"type": "rx_updated", "rx": clinic.get_prescription(new_id)})
        except Exception as e:
            broadcast({"type": "toast", "level": "error", "text": f"Email to pharmacy failed: {e}"})
    provider = next((x for x in clinic.providers() if x["id"] == body.provider_id), {"name": "Your care team"})
    text = f"Your refill of {rx['drug']} {rx['strength']} was approved and sent to {new_rx['pharmacy_name']}."
    if body.note.strip():
        text += f"\n{body.note.strip()}"
    reply = portal.create_message(m["patient_id"], "to_patient", "refill_request", f"Re: {m['subject']}", text,
                                  reply_to=msg_id, sender=provider["name"], rx_id=new_id)
    portal.set_status(msg_id, "done")
    portal._announce(portal.get_message(msg_id), created=False)
    portal._announce(reply)
    return {"rx_id": new_id, "emailed": emailed, "pharmacy": new_rx["pharmacy_name"]}


class DenyBody(BaseModel):
    reason: str
    provider_id: int = 1


@router.post("/inbox/refills/{msg_id}/deny")
def deny_refill(msg_id: int, body: DenyBody):
    m, rx = _refill_or_404(msg_id)
    if not body.reason.strip():
        raise HTTPException(400, "Give the patient a reason")
    provider = next((x for x in clinic.providers() if x["id"] == body.provider_id), {"name": "Your care team"})
    reply = portal.create_message(m["patient_id"], "to_patient", "refill_request", f"Re: {m['subject']}",
                                  f"We can't refill {rx['drug']} right now. {body.reason.strip()}",
                                  reply_to=msg_id, sender=provider["name"], rx_id=rx["id"])
    portal.set_status(msg_id, "done")
    portal._announce(portal.get_message(msg_id), created=False)
    portal._announce(reply)
    return {"ok": True}


# ---- AI-drafted replies ----------------------------------------------------------------
class DraftReply(BaseModel):
    reply: str = Field(description="Warm, plain-language reply to the patient, 2-5 sentences, signed 'Your care team'")
    needs_clinician: bool = Field(description="True if the message describes symptoms that a clinician must assess")
    urgency_note: str = Field(description="If urgent symptoms (chest pain, trouble breathing, stroke signs, suicidal "
                                          "thoughts, severe bleeding), a one-line warning for staff; else empty")


DRAFT_SYSTEM = """You draft replies from a primary-care clinic's care team to patient portal messages.
Rules: be warm, clear and brief; never diagnose or change medications in the reply; for symptoms, offer an
appointment or a call from a nurse; if anything sounds like an emergency, tell the patient to call 911 or go to
the ER. Use only facts from the chart summary and the message. The draft is reviewed by staff before sending."""


@router.post("/inbox/messages/{msg_id}/draft")
async def draft_reply(msg_id: int):
    m = portal.get_message(msg_id)
    if m is None:
        raise HTTPException(404, "Message not found")
    p = clinic.get_patient(m["patient_id"])
    appts = [a for a in p["appointments"] if a["status"] in ("booked", "checked_in")]
    context = (f"Patient: {p['first_name']} {p['last_name']}. Conditions: {p.get('conditions') or 'none'}. "
               f"Medications: {p.get('medications') or 'none'}. Next appointment: "
               f"{appts[-1]['start'] if appts else 'none booked'}.\n\nMESSAGE ({KIND_LABEL.get(m['kind'], 'Message')}): "
               f"{m['subject']}\n{m['body']}")
    try:
        result, _ = await ai.generate(config.SCRIBE_MODELS, context, DraftReply, system=DRAFT_SYSTEM, thinking="low")
    except ai.AIUnavailable as e:
        raise HTTPException(503, str(e))
    return result.model_dump()
