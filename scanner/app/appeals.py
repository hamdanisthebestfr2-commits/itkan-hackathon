"""AI denial fighter: explains a denial, recommends what to do, and drafts the appeal letter.

Honesty rule: the model must say when a denial is correct (recommend write-off or correction
instead of an appeal), may only quote what the note actually says, and leaves anything it
doesn't know as a [bracketed placeholder] for staff to fill in.
"""
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from . import ai, config


class DenialAnalysis(BaseModel):
    plain_english: str = Field(description="2-3 sentences a non-expert understands: what was denied and why")
    recommendation: Literal["appeal", "correct_and_resubmit", "write_off", "bill_patient"]
    recommendation_reason: str = Field(description="1-2 sentences")
    winnable: Literal["likely", "possible", "unlikely"]
    evidence_quotes: list[str] = Field(description="Exact quotes from the visit note that support the appeal (empty if none)")
    letter: str = Field(description="Complete appeal letter if recommending appeal, otherwise an empty string")
    attachments: list[str] = Field(description="Documents to attach to the appeal (empty if not appealing)")


SYSTEM = """You are an experienced medical billing specialist who fights insurance denials for a small clinic.
Given a denied claim line, the insurer's policy, and the signed visit note, you:
1. Explain the denial in plain English (no jargon) in 2-3 sentences.
2. Recommend the honest best action:
   - "appeal" only if the record genuinely meets the policy or a policy exception;
   - "correct_and_resubmit" if it was a fixable billing error (wrong code, missing modifier/info, missing auth number);
   - "write_off" if the denial is correct per contract (e.g. a bundling rule) and the patient can't be billed;
   - "bill_patient" if the service is non-covered and the patient agreed in advance to pay.
   Never recommend appealing a denial that is correct; wasted appeals cost staff time.
3. If appealing, write a complete, formal, concise appeal letter (plain text, under 350 words):
   clinic letterhead line, date, insurer appeals department, RE: line with patient name, DOB, member ID, claim number,
   date of service, CPT code and denial code; the argument citing the policy/exception and QUOTING the note; a clear
   request to reprocess and pay; closing with the provider's name and credentials.
   Only state facts present in the materials. Use [brackets] for anything unknown (e.g. [Fax number]).
4. evidence_quotes must be EXACT quotes copied from the note."""


async def analyze(claim: dict, line: dict) -> DenialAnalysis:
    p, enc, prov, payer = claim["patient"], claim["encounter"], claim["provider"] or {}, claim["payer"] or {}
    rem = claim["remittance"]
    codes_txt = "; ".join(f"{d['code']} {d['description']}" for d in claim["diagnoses"] if d["status"] == "accepted")
    procs_txt = "; ".join(f"{x['code']} {x['description']}" for x in claim["procedures"] if x["status"] == "accepted")
    context = f"""CLINIC: {config.CLINIC_NAME}, Plano, TX. Today's date: {date.today().isoformat()}
INSURER: {payer.get('name')} (payer ID {payer.get('payer_code')})
CLAIM NUMBER: {rem['claim_number']}   DATE OF SERVICE: {enc['date']}
PATIENT: {p['first_name']} {p['last_name']}, DOB {p.get('dob')}, member ID {p.get('member_id')}
RENDERING PROVIDER: {prov.get('name')}, {prov.get('credentials')}, NPI {prov.get('npi')}
DIAGNOSES BILLED: {codes_txt}
PROCEDURES BILLED: {procs_txt}

DENIED LINE: CPT {line['code']} ({line['description']}), charge ${line['charge']:.2f}
DENIAL CODE: {line['carc']}: {line['carc_text']}
INSURER POLICY: {line.get('policy') or 'not provided'}

SIGNED VISIT NOTE:
\"\"\"
{enc['note']}
\"\"\""""
    result, _ = await ai.generate(config.CODING_MODELS, context, DenialAnalysis, system=SYSTEM,
                                  thinking=config.CODING_THINKING)
    return result
