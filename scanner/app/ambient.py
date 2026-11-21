"""AI Ambient Notes: turn the doctor-patient conversation into a draft SOAP note.

Two inputs, same output:
  - audio recorded in the browser (16 kHz mono WAV) -> Gemini listens, transcribes, and drafts the note
  - a transcript typed by Wispr Flow (or any dictation tool) -> Gemini drafts the note
The draft is never signed automatically: the doctor reviews it and inserts it into the visit note.
"""
from fastapi import APIRouter, File, HTTPException, UploadFile
from google.genai import types
from pydantic import BaseModel, Field

from . import ai, clinic, config

router = APIRouter(prefix="/api")
MAX_AUDIO_BYTES = 18 * 1024 * 1024   # Gemini inline limit is ~20 MB (about 9 minutes of 16 kHz mono WAV)


def init() -> None:
    with clinic._conn() as con:
        if "ambient_transcript" not in {r["name"] for r in con.execute("PRAGMA table_info(encounters)")}:
            con.execute("ALTER TABLE encounters ADD COLUMN ambient_transcript TEXT")


class AmbientNote(BaseModel):
    transcript: str = Field(description="The conversation as lines like 'Doctor: ...' / 'Patient: ...'. For a typed "
                                        "transcript, return it cleaned up with speaker labels where obvious.")
    subjective: str = Field(description="S: chief complaint, history of present illness, relevant ROS, meds/allergies mentioned")
    objective: str = Field(description="O: exam findings and vitals stated in the conversation or provided vitals. "
                                       "Empty if none were mentioned")
    assessment: str = Field(description="A: diagnoses/problems the doctor stated, numbered")
    plan: str = Field(description="P: tests, prescriptions, counseling, referrals, follow-up the doctor stated, numbered")
    patient_instructions: str = Field(description="1-3 plain-language sentences the patient was told to do")
    needs_review: list[str] = Field(description="Things that were unclear or not stated and the doctor should check "
                                                "(e.g. 'Dose of metformin not stated'). Empty if none")


SYSTEM = """You are a medical scribe for a primary-care clinic. From the doctor-patient conversation, write a concise,
professional SOAP note draft that the doctor will review and edit before signing.

Rules:
- Document ONLY what was said in the conversation (or given in the vitals). Never invent findings, doses, test
  results, or diagnoses. If something important is missing or ambiguous, leave it out and list it in needs_review.
- Do NOT add standard exam phrases that were not said (e.g. "RRR", "no murmurs", "regular rhythm", "alert and
  oriented"). Write exam findings in the doctor's own words, e.g. "heart and lungs clear".
- Diagnoses and plans must come from what the DOCTOR said, not from your own judgment.
- Use standard clinical style: short phrases, common abbreviations (HTN, SOB, BID, f/u), numbered lists for A and P.
- Ignore small talk. Keep each section brief.
- Write in English even if the conversation was in another language."""


def _context(enc: dict) -> str:
    p = clinic.get_patient(enc["patient_id"])
    v = enc.get("vitals") or {}
    vit = ", ".join(f"{k}={val}" for k, val in v.items()) or "none recorded"
    return (f"Patient: {p['first_name']} {p['last_name']}, sex {p.get('sex') or '?'}, DOB {p.get('dob') or '?'}. "
            f"Known conditions: {p.get('conditions') or 'none'}. Home meds: {p.get('medications') or 'none'}. "
            f"Allergies: {p.get('allergies') or 'none'}. Vitals entered for this visit: {vit}.")


def _encounter_or_error(enc_id: int) -> dict:
    enc = clinic.get_encounter(enc_id)
    if enc is None:
        raise HTTPException(404, "Visit not found")
    if enc["status"] == "signed":
        raise HTTPException(409, "This visit is already signed")
    return enc


async def _draft(contents, enc_id: int) -> dict:
    try:
        result, model = await ai.generate(config.SCRIBE_MODELS, contents, AmbientNote, system=SYSTEM,
                                          thinking=config.CODING_THINKING)
    except ai.AIUnavailable as e:
        raise HTTPException(503, str(e))
    with clinic._conn() as con:
        con.execute("UPDATE encounters SET ambient_transcript = ? WHERE id = ?", (result.transcript, enc_id))
    return {**result.model_dump(), "model": model}


@router.post("/encounters/{enc_id}/ambient/audio")
async def from_audio(enc_id: int, file: UploadFile = File(...)):
    enc = _encounter_or_error(enc_id)
    audio = await file.read()
    if len(audio) < 2000:
        raise HTTPException(400, "The recording is empty. Check that the microphone is allowed")
    if len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "Recording too long for the demo (about 9 minutes max)")
    mime = file.content_type if file.content_type and file.content_type.startswith("audio/") else "audio/wav"
    contents = [types.Part.from_bytes(data=audio, mime_type=mime),
                _context(enc) + "\n\nListen to this recording of the visit. Transcribe it with speaker labels, "
                                "then write the SOAP note draft."]
    return await _draft(contents, enc_id)


class TranscriptBody(BaseModel):
    transcript: str


@router.post("/encounters/{enc_id}/ambient/transcript")
async def from_transcript(enc_id: int, body: TranscriptBody):
    enc = _encounter_or_error(enc_id)
    text = body.transcript.strip()
    if len(text) < 20:
        raise HTTPException(400, "The transcript is too short. Dictate the conversation first")
    contents = _context(enc) + f"\n\nVISIT CONVERSATION (typed by a dictation tool, speakers may be unlabeled):\n\"\"\"\n{text}\n\"\"\"\n\nWrite the SOAP note draft."
    return await _draft(contents, enc_id)
