"""REST API for the clinic platform: patients, schedule, visits, e-prescribing."""
import asyncio
from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import billing, clinic, drugs, mailer, seed
from .events import broadcast

router = APIRouter(prefix="/api")


# ---- reference data ----------------------------------------------------------
@router.get("/reference")
def reference():
    return {
        "providers": clinic.providers(),
        "payers": clinic.payers(),
        "pharmacies": clinic.pharmacies(),
        "drugs": drugs.formulary(),
        "email_enabled": mailer.enabled(),
    }


@router.post("/demo/reset")
def demo_reset():
    seed.seed()
    broadcast({"type": "clinic_reset"})
    return {"ok": True}


# ---- patients ----------------------------------------------------------------
class PatientBody(BaseModel):
    first_name: str
    last_name: str
    dob: str | None = None
    sex: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    payer_id: int | None = None
    member_id: str | None = None
    group_number: str | None = None
    pharmacy_id: int | None = None
    allergies: str | None = None
    conditions: str | None = None
    medications: str | None = None


@router.get("/patients")
def patients(q: str = ""):
    return clinic.list_patients(q)


@router.post("/patients")
def register_patient(body: PatientBody):
    data = body.model_dump()
    if not data["first_name"].strip() or not data["last_name"].strip():
        raise HTTPException(400, "First and last name are required")
    existing = clinic.find_patient(data["first_name"], data["last_name"], data["dob"], data["phone"])
    if existing:
        raise HTTPException(409, f"This patient is already registered (id {existing})")
    patient_id = clinic.create_patient(data)
    broadcast({"type": "patient_created", "patient_id": patient_id})
    return {"id": patient_id}


@router.get("/patients/{patient_id}")
def patient(patient_id: int):
    p = clinic.get_patient(patient_id)
    if p is None:
        raise HTTPException(404, "Patient not found")
    return p


@router.put("/patients/{patient_id}")
def edit_patient(patient_id: int, body: PatientBody):
    clinic.update_patient(patient_id, body.model_dump())
    return clinic.get_patient(patient_id)


# ---- scheduling --------------------------------------------------------------
class AppointmentBody(BaseModel):
    patient_id: int
    provider_id: int
    start: str            # YYYY-MM-DDTHH:MM:SS
    duration_min: int = 30
    reason: str = ""
    visit_type: str = "follow_up"


class AppointmentUpdate(BaseModel):
    provider_id: int | None = None
    start: str | None = None
    duration_min: int | None = None
    reason: str | None = None
    status: str | None = None


@router.get("/appointments")
def appointments(day: str | None = None):
    return clinic.list_appointments(day or date.today().isoformat())


@router.post("/appointments")
def book(body: AppointmentBody):
    if clinic.slot_taken(body.provider_id, body.start, body.duration_min):
        raise HTTPException(409, "That provider already has an appointment at this time")
    appt_id = clinic.create_appointment(body.model_dump())
    broadcast({"type": "schedule_changed", "day": body.start[:10]})
    return {"id": appt_id}


@router.patch("/appointments/{appt_id}")
def change_appointment(appt_id: int, body: AppointmentUpdate):
    appt = clinic.get_appointment(appt_id)
    if appt is None:
        raise HTTPException(404, "Appointment not found")
    data = body.model_dump(exclude_none=True)
    restoring = appt["status"] in ("cancelled", "no_show") and data.get("status") not in (None, "cancelled", "no_show")
    if restoring or "start" in data or "provider_id" in data or "duration_min" in data:
        merged = {**appt, **data}
        if clinic.slot_taken(merged["provider_id"], merged["start"], merged["duration_min"], ignore_id=appt_id):
            raise HTTPException(409, "That provider already has an appointment at this time")
    try:
        clinic.update_appointment(appt_id, data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    broadcast({"type": "schedule_changed", "day": (data.get("start") or appt["start"])[:10]})
    return clinic.get_appointment(appt_id)


@router.post("/appointments/{appt_id}/start-visit")
def start_visit(appt_id: int):
    """Check-in -> visit: opens (or reuses) the encounter for this appointment."""
    appt = clinic.get_appointment(appt_id)
    if appt is None:
        raise HTTPException(404, "Appointment not found")
    existing = [a for a in clinic.list_appointments(appt["start"][:10]) if a["id"] == appt_id][0]["encounter_id"]
    enc_id = existing or clinic.create_encounter({
        "patient_id": appt["patient_id"], "provider_id": appt["provider_id"], "appointment_id": appt_id,
        "date": appt["start"][:10], "type": "office visit", "note": "",
        "vitals": {},
    })
    clinic.update_appointment(appt_id, {"status": "in_visit"})
    broadcast({"type": "schedule_changed", "day": appt["start"][:10]})
    return {"encounter_id": enc_id}


# ---- visits ------------------------------------------------------------------
class WalkInBody(BaseModel):
    patient_id: int
    provider_id: int


@router.post("/encounters")
def walk_in(body: WalkInBody):
    """Start a visit without an appointment (walk-in), e.g. from the patient chart."""
    if clinic.get_patient(body.patient_id) is None:
        raise HTTPException(404, "Patient not found")
    enc_id = clinic.create_encounter({"patient_id": body.patient_id, "provider_id": body.provider_id,
                                      "type": "office visit", "note": "", "vitals": {}})
    return {"encounter_id": enc_id}


class EncounterUpdate(BaseModel):
    note: str | None = None
    vitals: dict | None = None
    status: str | None = None


@router.get("/encounters/{enc_id}")
def encounter(enc_id: int):
    e = clinic.get_encounter(enc_id)
    if e is None:
        raise HTTPException(404, "Visit not found")
    return {**e, "patient": clinic.get_patient(e["patient_id"]), "latest_vitals": clinic.latest_vitals(e["patient_id"], exclude_encounter=enc_id)}


@router.put("/encounters/{enc_id}")
async def save_encounter(enc_id: int, body: EncounterUpdate):
    e = clinic.get_encounter(enc_id)
    if e is None:
        raise HTTPException(404, "Visit not found")
    if e["status"] == "signed" and (body.note is not None or body.vitals is not None):
        raise HTTPException(409, "This visit is signed and locked")
    clinic.update_encounter(enc_id, body.model_dump(exclude_none=True))
    if body.status == "signed" and e["appointment_id"]:
        clinic.update_appointment(e["appointment_id"], {"status": "completed"})
        broadcast({"type": "schedule_changed", "day": e["date"]})
    result = clinic.get_encounter(enc_id)
    if body.status == "signed" and e["status"] != "signed" and e["type"] != "screening" and e["provider_id"]:
        from .billing_api import start_coding
        claim_id = billing.create_for_encounter(enc_id)
        broadcast({"type": "claim_created", "claim_id": claim_id, "encounter_id": enc_id})
        start_coding(claim_id)
        result["claim_id"] = claim_id
    return result


# ---- e-prescribing -----------------------------------------------------------
class PrescriptionBody(BaseModel):
    encounter_id: int | None = None
    patient_id: int
    provider_id: int | None = None
    pharmacy_id: int
    drug: str
    strength: str = ""
    sig: str = ""
    quantity: int = 30
    refills: int = 0
    override_allergy: bool = False


class PrescriptionUpdate(BaseModel):
    status: str


@router.post("/prescriptions/check")
def check_prescription(body: PrescriptionBody):
    p = clinic.get_patient(body.patient_id)
    return {"allergy_conflicts": drugs.allergy_conflicts(body.drug, p and p["allergies"])}


@router.post("/prescriptions")
async def prescribe(body: PrescriptionBody):
    p = clinic.get_patient(body.patient_id)
    if p is None:
        raise HTTPException(404, "Patient not found")
    if body.encounter_id:
        e = clinic.get_encounter(body.encounter_id)
        if e and e["status"] == "signed":
            raise HTTPException(409, "This visit is signed. Prescribe from the patient chart instead")
    if not body.drug.strip() or body.quantity < 1 or not (0 <= body.refills <= 11):
        raise HTTPException(400, "Check the drug, quantity (at least 1) and refills (0-11)")
    conflicts = drugs.allergy_conflicts(body.drug, p["allergies"])
    if conflicts and not body.override_allergy:
        raise HTTPException(409, f"Allergy alert: patient is allergic to {', '.join(conflicts)}")
    rx_id = clinic.create_prescription(body.model_dump())
    rx = clinic.get_prescription(rx_id)
    broadcast({"type": "rx_sent", "rx": rx})

    emailed = False
    if mailer.enabled():
        try:
            await asyncio.to_thread(mailer.send_prescription, rx)
            clinic.update_prescription(rx_id, {"emailed": 1})
            emailed = True
            broadcast({"type": "rx_updated", "rx": clinic.get_prescription(rx_id)})
        except Exception as e:  # the in-app pharmacy inbox still has it
            broadcast({"type": "toast", "level": "error", "text": f"Email to pharmacy failed: {e}"})
    return {"id": rx_id, "emailed": emailed}


@router.get("/email/status")
def email_status():
    return {"enabled": mailer.enabled(), "to": mailer.recipient()}


@router.post("/email/test")
async def email_test():
    if not mailer.enabled():
        raise HTTPException(400, "Email isn't set up: add SMTP_USER and SMTP_PASS to scanner/.env and restart")
    try:
        await asyncio.to_thread(mailer.send_test)
    except Exception as e:
        raise HTTPException(502, f"Email failed: {e}")
    return {"ok": True, "to": mailer.recipient()}


@router.get("/pharmacy/inbox")
def inbox(pharmacy_id: int | None = None):
    return clinic.pharmacy_inbox(pharmacy_id)


@router.patch("/prescriptions/{rx_id}")
def update_rx(rx_id: int, body: PrescriptionUpdate):
    if body.status not in ("sent", "received", "filled", "ready"):
        raise HTTPException(400, "Unknown status")
    clinic.update_prescription(rx_id, {"status": body.status})
    rx = clinic.get_prescription(rx_id)
    broadcast({"type": "rx_updated", "rx": rx})
    return rx
