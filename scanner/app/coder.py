"""AI medical coding: suggests ICD-10 + CPT codes for a signed visit note.

Guardrails: the model only sees our approved code list, every suggestion must quote the
note, and the output is re-checked here (unknown codes are removed, quotes that aren't in
the note get low confidence). Suggestions stay "suggested" until a human accepts them.
"""
import re
from typing import Literal

from pydantic import BaseModel, Field

from . import ai, billing, clinic, codes, config
from .events import broadcast


class DxSuggestion(BaseModel):
    code: str
    evidence: str = Field(description="Short exact quote from the note that supports this diagnosis")
    confidence: Literal["high", "medium", "low"]
    reason: str = Field(description="One short sentence")


class ProcSuggestion(BaseModel):
    code: str
    units: int
    dx_codes: list[str] = Field(description="Diagnosis codes (from your diagnoses list) that justify this procedure")
    evidence: str = Field(description="Short exact quote from the note showing it was done/addressed")
    confidence: Literal["high", "medium", "low"]
    reason: str = Field(description="One short sentence")


class CodingResult(BaseModel):
    diagnoses: list[DxSuggestion]
    procedures: list[ProcSuggestion]
    em_rationale: str = Field(description="1-2 sentences: why this office-visit level")


SYSTEM = """You are a certified professional medical coder for a small primary-care clinic.
Suggest ICD-10-CM diagnosis codes and CPT/HCPCS procedure codes for ONE signed visit.

Rules:
1. Use ONLY codes from the approved lists provided. Never invent codes.
2. Code only what the visit note documents as addressed or performed today. The problem list alone is not enough.
3. Every code needs evidence: a short EXACT quote copied from the note.
4. Choose exactly one office-visit (E/M) code by medical decision making (MDM). The MDM level is the level met by
   at least 2 of these 3 elements:
   PROBLEMS: minimal = 1 self-limited/minor problem; low = 2+ minor problems, OR 1 stable chronic illness, OR 1 acute
     uncomplicated illness (e.g. strep throat, UTI); moderate = 1+ chronic illness with exacerbation/progression/not at
     goal, OR 2+ stable chronic illnesses, OR an undiagnosed new problem with uncertain prognosis, OR acute illness with
     systemic symptoms; high = severe exacerbation or threat to life/bodily function.
   DATA: minimal = none or 1 test; limited = 2 items (each unique test ordered/reviewed or external note reviewed);
     moderate = 3+ items, or independent interpretation of a test.
   RISK: minimal = rest, fluids; low = over-the-counter drugs; moderate = PRESCRIPTION DRUG MANAGEMENT (starting,
     changing or continuing a prescription); high = drugs needing intensive monitoring, decision about hospitalization.
   Level -> code: straightforward 99202/99212, low 99203/99213, moderate 99204/99214, high 99205/99215.
   Use 9920x if the patient status is NEW, 9921x if ESTABLISHED. Use preventive codes (9938x/9939x) only if the note
   documents an annual/preventive exam. In em_rationale, state the level of each of the 3 elements.
5. Add other procedures only if the note says they were performed (tests, counseling with time, treatments).
   Tobacco counseling: 99406 for 3-10 min, 99407 for >10 min.
6. Link each procedure to the diagnosis codes that justify it (dx_codes); the E/M links to the main problems addressed.
7. Prefer the most specific code the note supports. Don't code a symptom (fever, cough, sore throat) when a confirmed
   diagnosis explains it.
8. BMI Z68 codes only alongside an addressed weight diagnosis (E66.x).
9. confidence: high = clearly documented; medium = documented but a judgment call; low = weak support."""


def _code_list() -> str:
    dx = "\n".join(f"{c}: {d}" for c, d in codes.ICD10.items())
    cpt = "\n".join(f"{c}: {d}" for c, (d, _) in codes.CPT.items())
    return f"APPROVED DIAGNOSIS CODES (ICD-10-CM):\n{dx}\n\nAPPROVED PROCEDURE CODES (CPT/HCPCS):\n{cpt}"


def _visit_context(c: dict) -> str:
    enc = clinic.get_encounter(c["encounter_id"])
    p = clinic.get_patient(c["patient_id"])
    status = billing.patient_status(p["id"], enc)
    age = billing._age_on(p.get("dob"), enc["date"])
    v = enc.get("vitals") or {}
    bmi = billing._bmi(v)
    vitals = ", ".join(f"{k}={val}" for k, val in v.items()) + (f", BMI={bmi}" if bmi else "")
    rx = "; ".join(f"{r['drug']} {r['strength']} ({r['sig']})" for r in enc["prescriptions"]) or "none"
    appt = next((a for a in p["appointments"] if a["id"] == enc["appointment_id"]), None)
    return f"""PATIENT: {age} year old {dict(M='male', F='female').get(p.get('sex'), 'patient')}. Patient status: {status.upper()}.
Problem list: {p.get('conditions') or 'none'}. Home medications: {p.get('medications') or 'none'}.
VISIT: {enc['date']}, reason: {appt['reason'] if appt else 'walk-in'}.
Vitals: {vitals or 'not recorded'}
Prescriptions sent this visit: {rx}

VISIT NOTE:
\"\"\"
{enc['note']}
\"\"\""""


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9%./ ]", " ", s.lower())).strip()


def _validate(result: CodingResult, note: str) -> tuple[list, list, list[str]]:
    """Keep only approved codes; check evidence quotes against the note."""
    note_n, removed = _norm(note), []

    def evidence_ok(q: str) -> bool:
        q = _norm(q)
        return bool(q) and (q in note_n or all(w in note_n for w in q.split()[:6]))

    dxs, seen = [], set()
    for d in result.diagnoses:
        code = d.code.strip().upper()
        if code not in codes.ICD10:
            removed.append(code)
            continue
        if code in seen:
            continue
        seen.add(code)
        conf, reason = d.confidence, d.reason
        if not evidence_ok(d.evidence):
            conf, reason = "low", reason + " (quote not found in the note: please verify)"
        dxs.append(billing.make_line("dx", code, source="ai", evidence=d.evidence, confidence=conf, reason=reason))

    procs, seen = [], set()
    for p in result.procedures:
        code = p.code.strip().upper()
        if code not in codes.CPT:
            removed.append(code)
            continue
        if code in seen:
            continue
        seen.add(code)
        linked = [x.strip().upper() for x in p.dx_codes if x.strip().upper() in {d["code"] for d in dxs}]
        if not linked:
            s = billing._supporting(code, [d["code"] for d in dxs])
            linked = [s] if s else []
        conf, reason = p.confidence, p.reason
        if not evidence_ok(p.evidence):
            conf, reason = "low", reason + " (quote not found in the note: please verify)"
        procs.append(billing.make_line("cpt", code, source="ai", evidence=p.evidence, confidence=conf, reason=reason,
                                       units=max(1, p.units), dx=linked[:4]))
    return dxs, procs, removed


async def code_claim(claim_id: int) -> None:
    """Run AI coding for a claim (background task). Keeps any codes staff added by hand."""
    c = billing.get_raw(claim_id)
    if c is None:
        return
    billing.update(claim_id, ai_status="running", ai_message=None)
    broadcast({"type": "claim_updated", "claim_id": claim_id})
    try:
        enc = clinic.get_encounter(c["encounter_id"])
        if not (enc["note"] or "").strip():
            raise ValueError("The visit note is empty")
        result, _ = await ai.generate(config.CODING_MODELS, [_code_list(), _visit_context(c)], CodingResult,
                                      system=SYSTEM, thinking=config.CODING_THINKING)
        dxs, procs, removed = _validate(result, enc["note"])
        manual_dx = [d for d in c["diagnoses"] if d["source"] == "manual"]
        manual_px = [p for p in c["procedures"] if p["source"] == "manual"]
        msg = f"Removed {', '.join(removed)}: not on the approved code list." if removed else None
        billing.update(claim_id, diagnoses=manual_dx + dxs, procedures=manual_px + procs, ai_status="done",
                       ai_message=msg, em_rationale=result.em_rationale, status="review")
    except Exception as e:  # never leave the claim stuck; staff can code by hand
        why = str(e) if isinstance(e, ai.AIUnavailable) else f"AI coding failed: {str(e)[:200]}."
        billing.update(claim_id, ai_status="error", ai_message=f"{why} You can add codes manually.")
    broadcast({"type": "claim_updated", "claim_id": claim_id})
