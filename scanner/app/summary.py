"""AI after-visit summary (Track A5).

Signing a visit drafts a plain-language summary for the patient in the background (like AI coding).
The provider edits it (or re-drafts it in another language) and sends it; only then does it reach the
patient portal (Track B reads `encounters.summary`) together with a "your summary is ready" message.
The AI may only restate what is in the note/visit data: no new diagnoses, medicines or doses.
"""
import asyncio
from datetime import date, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import ai, clinic, config, labs, portal
from .events import broadcast

router = APIRouter(prefix="/api")
_tasks: set = set()
LANGUAGES = ["English", "Spanish", "Arabic", "Urdu", "Vietnamese", "Chinese (Simplified)", "Hindi"]


def init() -> None:
    with clinic._conn() as con:
        cols = {r[1] for r in con.execute("PRAGMA table_info(encounters)")}
        for col, typ in (("summary", "TEXT"), ("summary_draft", "TEXT"), ("summary_language", "TEXT"),
                         ("summary_status", "TEXT"), ("summary_sent_at", "TEXT"), ("summary_ai", "INTEGER")):
            if col not in cols:
                con.execute(f"ALTER TABLE encounters ADD COLUMN {col} {typ}")


def _set(enc_id: int, **cols) -> None:
    with clinic._conn() as con:
        con.execute(f"UPDATE encounters SET {', '.join(f'{k} = ?' for k in cols)} WHERE id = ?", (*cols.values(), enc_id))


def state(enc_id: int) -> dict:
    e = clinic.get_encounter(enc_id)
    return {"encounter_id": enc_id, "status": e.get("summary_status") or "none", "draft": e.get("summary_draft"),
            "sent": e.get("summary"), "sent_at": e.get("summary_sent_at"), "language": e.get("summary_language") or "English",
            "signed": e["status"] == "signed", "languages": LANGUAGES}


# ---- the AI ------------------------------------------------------------------------------
class AfterVisitSummary(BaseModel):
    summary: str = Field(description="The complete after-visit summary as plain text with the section headings")
    needs_review: list[str] = Field(description="Anything the provider should double-check (unclear doses, missing "
                                                "follow-up time...). Empty if nothing. Always in English.")


SYSTEM = """You write after-visit summaries for patients of a primary-care clinic, from the provider's visit note.
Write for a patient with a 6th-grade reading level: short sentences, everyday words, "you", warm and calm.
Explain medical words in plain language the first time (e.g. "high blood pressure (hypertension)").
Use these sections, each heading on its own line followed by short lines or "- " bullets:
Why you came in / What we found / Your medicines / Tests / What to do next / When to get help
Skip a section only if there is truly nothing for it (write "Your medicines: no changes" rather than skipping).
STRICT RULES:
- Use ONLY facts in the visit data. Never add a diagnosis, medicine, dose, test result or instruction that isn't there.
- Medicines: list what was started or changed today with the exact dose and how to take it. For a CHANGED dose, say
  clearly to stop the old dose and start the new one (e.g. "Stop: 75 mcg. Start: 100 mcg"). Then "keep taking" home
  medicines if the note says to continue them.
- Test results from today: give the value and say in plain words whether it is high, low or normal and what it means.
- Tests ordered without a result yet: say the results will appear in their patient portal.
- "When to get help": only warning signs that fit today's problems, plus "call 911 for an emergency".
- No billing codes, no internal abbreviations (no "BID", "PRN", "f/u", "HTN"), no doctor-to-doctor language.
- Write every word, including the headings, in the requested language, with correct spelling and ALL accents and
  special characters of that language (e.g. Spanish "¿Por qué vino?", "día", "estómago"). A translated summary must
  contain every fact and number the English one would. Keep medicine names exactly as on the prescription label.
  needs_review stays in English.
- Plain text only: no markdown symbols (#, **, tables)."""


def _context(enc: dict) -> str:
    p = clinic.get_patient(enc["patient_id"])
    appt = next((a for a in p["appointments"] if a["id"] == enc["appointment_id"]), None)
    nxt = sorted(a["start"] for a in p["appointments"]
                 if a["status"] in ("booked", "checked_in") and a["start"][:10] > enc["date"][:10])
    v = enc.get("vitals") or {}
    vit = ", ".join(f"{k}={val}" for k, val in v.items()) or "not recorded"
    rx = "\n".join(f"- {r['drug']} {r['strength']}: {r['sig']} (qty {r['quantity']}, {r['refills']} refills, sent to "
                   f"{r['pharmacy_name']})" for r in enc["prescriptions"]) or "none"
    lab_lines = []
    for o in labs.list_orders(encounter_id=enc["id"]):
        if o["status"] == "ordered":
            lab_lines.append(f"- {o['test_name']}: ordered, result not back yet")
        else:
            vals = "; ".join(f"{r['analyte']} {r['value']} {r['unit']} ({'HIGH' if r['flag'] == 'H' else 'LOW' if r['flag'] == 'L' else 'normal'})"
                             for r in o["results"])
            lab_lines.append(f"- {o['test_name']}: {vals}")
    return f"""PATIENT: {p['first_name']}, age {(date.today() - date.fromisoformat(p['dob'])).days // 365 if p.get('dob') else 'unknown'}.
Allergies: {p.get('allergies') or 'none known'}. Home medicines: {p.get('medications') or 'none listed'}.
VISIT: {enc['date'][:10]} with {enc.get('provider_name') or 'the provider'}. Reason: {appt['reason'] if appt else 'walk-in visit'}.
Vitals: {vit}
Prescriptions sent today:
{rx}
Lab tests today:
{chr(10).join(lab_lines) or 'none'}
Next appointment already booked: {nxt[0].replace('T', ' at ')[:19] if nxt else 'none booked'}

PROVIDER'S VISIT NOTE:
\"\"\"
{enc.get('note') or ''}
\"\"\""""


async def draft(enc_id: int, language: str = "English", announce: bool = True) -> dict:
    enc = clinic.get_encounter(enc_id)
    if not (enc.get("note") or "").strip():
        raise HTTPException(400, "Write the visit note first: the summary is made from it")
    _set(enc_id, summary_status="drafting")
    if announce:
        broadcast({"type": "summary_updated", "encounter_id": enc_id, "patient_id": enc["patient_id"], "status": "drafting"})
    try:
        result, model = await ai.generate(config.SCRIBE_MODELS, _context(enc) + f"\n\nWrite the summary in: {language}",
                                          AfterVisitSummary, system=SYSTEM, thinking="low")
    except ai.AIUnavailable as e:
        _set(enc_id, summary_status="failed")
        broadcast({"type": "summary_updated", "encounter_id": enc_id, "patient_id": enc["patient_id"], "status": "failed",
                   "error": str(e)})
        raise HTTPException(503, str(e))
    text = result.summary.replace("**", "").replace("## ", "").replace("# ", "").strip()
    _set(enc_id, summary_draft=text, summary_language=language, summary_status="draft", summary_ai=1)
    out = {**state(enc_id), "needs_review": result.needs_review, "model": model}
    broadcast({"type": "summary_updated", "encounter_id": enc_id, "patient_id": enc["patient_id"], "status": "draft",
               "needs_review": result.needs_review})
    return out


def draft_on_sign(enc_id: int) -> None:
    """Called when a visit is signed: draft the summary in the background (a failure just leaves a 'Draft' button)."""
    async def run():
        try:
            await draft(enc_id)
        except HTTPException:
            pass
    task = asyncio.create_task(run())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


# ---- API ---------------------------------------------------------------------------------
def _enc_or_404(enc_id: int) -> dict:
    e = clinic.get_encounter(enc_id)
    if e is None or e["type"] == "screening":
        raise HTTPException(404, "Visit not found")
    return e


@router.get("/encounters/{enc_id}/summary")
def get_summary(enc_id: int):
    _enc_or_404(enc_id)
    return state(enc_id)


class DraftBody(BaseModel):
    language: str = "English"


@router.post("/encounters/{enc_id}/summary/draft")
async def draft_summary(enc_id: int, body: DraftBody):
    _enc_or_404(enc_id)
    if body.language not in LANGUAGES:
        raise HTTPException(400, "Unsupported language")
    return await draft(enc_id, body.language)


class SendBody(BaseModel):
    text: str


@router.post("/encounters/{enc_id}/summary/send")
def send_summary(enc_id: int, body: SendBody):
    e = _enc_or_404(enc_id)
    if e["status"] != "signed":
        raise HTTPException(409, "Sign the visit first: patients only see finished visits")
    text = body.text.strip()
    if len(text) < 20:
        raise HTTPException(400, "The summary is empty")
    first_time = not e.get("summary")
    _set(enc_id, summary=text, summary_draft=text, summary_status="sent",
         summary_sent_at=datetime.now().isoformat(timespec="seconds"))
    when = date.fromisoformat(e["date"][:10])
    msg = portal.create_message(
        e["patient_id"], "to_patient", "message",
        f"Your visit summary from {when:%b} {when.day} is ready" if first_time else f"Updated visit summary from {when:%b} {when.day}",
        "Your after-visit summary is ready. Open \"Visit summaries\" in your portal to read it: what we found, your "
        "medicines and your next steps.", sender=e.get("provider_name") or "Your care team")
    portal._announce(msg)
    broadcast({"type": "summary_updated", "encounter_id": enc_id, "patient_id": e["patient_id"], "status": "sent"})
    return state(enc_id)


# ---- demo data ---------------------------------------------------------------------------
SEEDED = {  # patient index in seed.PATIENTS -> a summary for their past signed visit
    0: """Why you came in
- A check of your blood pressure.

What we found
- Your blood pressure was high: 152/94. A healthy goal is below 130/80.
- High blood pressure (hypertension) often has no symptoms, but over time it can hurt your heart, brain and kidneys.

Your medicines
- NEW: Lisinopril 10 mg. Take 1 tablet by mouth once a day.

What to do next
- Eat less salt: fewer canned soups, chips and fast food.
- Come back in 3 months so we can check your blood pressure again.

When to get help
- Call us if you feel dizzy or faint, or if your lips or face swell.
- Call 911 for chest pain, trouble breathing, or sudden weakness on one side of the body.""",
    2: """Why you came in
- Wheezing and chest tightness for 2 days after a cold.

What we found
- Your asthma was flaring up (an asthma attack). Your oxygen level was a little low: 93%.
- A breathing treatment in the clinic helped.

Your medicines
- Prednisone 40 mg once a day for 5 days, to calm the swelling in your airways.
- Keep using your albuterol inhaler when you wheeze.

Tests
- Breathing test (spirometry): your lungs were moving less air than normal during this flare.

What to do next
- Come back in 1 week for a recheck.

When to get help
- Call us if you need your inhaler more than every 4 hours.
- Call 911 if you can't speak in full sentences, your lips turn blue, or the inhaler doesn't help.""",
}


def seed(patient_ids: list[int]) -> None:
    init()
    for idx, text in SEEDED.items():
        with clinic._conn() as con:
            r = con.execute("SELECT id, date FROM encounters WHERE patient_id = ? AND type != 'screening' AND status = 'signed' "
                            "ORDER BY date LIMIT 1", (patient_ids[idx],)).fetchone()
        if r:
            _set(r["id"], summary=text, summary_draft=text, summary_status="sent", summary_language="English",
                 summary_sent_at=f"{r['date'][:10]}T17:00:00", summary_ai=1)
