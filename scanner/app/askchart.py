"""Ask the chart (Track A6): staff ask a question about one patient; the AI answers ONLY from that chart.

The chart is flattened into numbered sources (profile, each visit, prescription, lab, claim, plus care gaps,
balance, coverage, appointments and portal messages). The AI must cite source ids inline like [V12]; ids that
don't exist are dropped, and the page turns real ones into clickable chips. "Not in the chart" is a valid answer.
Like athenaOne's "Sage" assistant, it summarizes and finds things; it does not make treatment decisions.
"""
import re
from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import ai, billing, caregaps, clinic, config, labs, portal

router = APIRouter(prefix="/api")
VITAL_NAMES = {"bp_systolic": "BP sys", "bp_diastolic": "BP dia", "heart_rate": "HR", "spo2": "SpO2", "temperature": "temp",
               "respiratory_rate": "RR", "blood_glucose": "glucose", "weight_lbs": "weight lb", "height_ft": "height ft",
               "height_in": "height in", "bmi": "BMI", "smoking": "smoking", "alcohol": "alcohol",
               "physical_activity": "physical activity", "temperature_unit": "temp unit"}


def _fmt_date(iso: str | None) -> str:
    if not iso:
        return ""
    d = date.fromisoformat(iso[:10])
    return f"{d:%b} {d.day}" + (f", {d.year}" if d.year != date.today().year else "")


def sources_for(patient_id: int) -> list[dict] | None:
    """Every fact the AI may use, as {id, kind, label, href, text}."""
    p = clinic.get_patient(patient_id)
    if p is None:
        return None
    age = (date.today() - date.fromisoformat(p["dob"])).days // 365 if p.get("dob") else "unknown"
    chart = f"/patient?id={patient_id}"
    out = [{"id": "P", "kind": "profile", "label": "Profile", "href": chart, "text":
            f"{p['first_name']} {p['last_name']}, {age} years old, sex {p.get('sex') or '?'}, DOB {p.get('dob')}, MRN {p['mrn']}. "
            f"Allergies: {p.get('allergies') or 'none known'}. Problem list: {p.get('conditions') or 'none'}. "
            f"Home medications: {p.get('medications') or 'none listed'}. Insurance: {p.get('payer_name') or 'self-pay'} "
            f"(member {p.get('member_id') or '-'}). Preferred pharmacy: {p.get('pharmacy_name') or '-'}. "
            f"Phone {p.get('phone') or '-'}. Registered via {p.get('source') or 'front desk'}."}]

    for e in sorted(p["encounters"], key=lambda e: (e["date"], e["id"])):
        vit = ", ".join(f"{VITAL_NAMES.get(k, k)} {v}" for k, v in e["vitals"].items() if v not in (None, ""))
        kind = "Health-fair screening card" if e["type"] == "screening" else f"Office visit ({e['status']})"
        out.append({"id": f"V{e['id']}", "kind": "visit", "label": f"{'Screening' if e['type'] == 'screening' else 'Visit'} {_fmt_date(e['date'])}",
                    "href": chart if e["type"] == "screening" else f"/visit?id={e['id']}", "text":
                    f"{kind} on {e['date'][:10]} with {e.get('provider_name') or 'health fair staff'}. "
                    f"Vitals: {vit or 'none recorded'}.\nNote: {e.get('note') or '(no note)'}"
                    + (f"\nAfter-visit summary sent to the patient." if e.get("summary") else "")})

    for r in sorted(p["prescriptions"], key=lambda r: r["sent_at"] or ""):
        out.append({"id": f"RX{r['id']}", "kind": "rx", "label": f"Rx {r['drug']} {_fmt_date(r['sent_at'])}", "href": chart, "text":
                    f"Prescription {r['drug']} {r['strength']}: {r['sig']}. Qty {r['quantity']}, {r['refills']} refills, sent "
                    f"{(r['sent_at'] or '')[:10]} by {r.get('provider_name') or '-'} to {r.get('pharmacy_name') or '-'}; pharmacy "
                    f"status {r['status']}." + (f" Controlled substance {r['schedule']}, {r.get('days_supply')} days' supply, "
                                                f"signed with EPCS 2FA." if r.get("schedule") else "")})

    for o in labs.list_orders(patient_id=patient_id):
        if o["status"] == "ordered":
            res = "ordered, result not back yet"
        else:
            res = "; ".join(f"{x['analyte']} {x['value']} {x['unit']} (normal {x['ref_range']}){' ' + {'H': 'HIGH', 'L': 'LOW'}.get(x['flag'], 'ABNORMAL') if x['flag'] else ''}"
                            for x in o["results"])
        out.append({"id": f"L{o['id']}", "kind": "lab", "label": f"Lab {o['test_code']} {_fmt_date(o['resulted_at'] or o['ordered_at'])}",
                    "href": chart, "text": f"Lab {o['test_name']}, ordered {o['ordered_at'][:10]}"
                    + (f", resulted {o['resulted_at'][:10]}" if o["resulted_at"] else "") + f": {res}. Status {o['status']}."
                    + (f" Note to patient: {o['provider_comment']}" if o["provider_comment"] else "")})

    gaps = caregaps.gaps_for(patient_id)
    if gaps:
        out.append({"id": "G", "kind": "gaps", "label": "Care gaps", "href": chart, "text": "Quality measures (simplified CMS): " +
                    "; ".join(f"{g['title']} ({g['cms']}): {'MET' if g['status'] == 'met' else 'OPEN'}, {g['detail']}" for g in gaps)})

    for c in [c for c in billing.list_claims() if c["patient_id"] == patient_id]:
        rem = c.get("remittance") or {}
        lines = "; ".join(f"{l.get('code')} {l.get('status')}" + (f" ({l['carc']}: {l.get('carc_text')})" if l.get("carc") else "")
                          + (" written off" if l.get("written_off") else "") for l in rem.get("lines", []))
        out.append({"id": f"CL{c['id']}", "kind": "claim", "label": f"Claim #{c['id']}", "href": f"/billing?claim={c['id']}", "text":
                    f"Insurance claim #{c['id']} for the {c['dos'][:10]} visit, {c.get('payer_name') or 'self-pay'}: status {c['status']}, "
                    f"billed ${c['total_charge']:.2f}, paid ${c.get('paid_amount') or 0:.2f}." + (f" Lines: {lines}." if lines else "")
                    + (f" Appeal {c['appeal'].get('status')}." if c.get("appeal") else "")})

    try:  # Track B modules (balance, coverage); optional so this works on any branch
        from . import ledger
        b = ledger.balance(patient_id)
        out.append({"id": "BAL", "kind": "balance", "label": "Balance", "href": f"/statement?patient_id={patient_id}", "text":
                    f"Patient account: balance due ${b['due']:.2f}, credit ${b['credit']:.2f}, total charged ${b['charges_total']:.2f}, "
                    f"paid ${b['payments_total']:.2f}; {len(b['pending'])} visit(s) still pending with insurance."
                    + (f" Last payment {b['last_payment']['created_at'][:10]} ${b['last_payment']['amount']:.2f}." if b.get("last_payment") else "")})
    except Exception:
        pass
    try:
        from . import eligibility
        el = eligibility.latest(patient_id)
        if el:
            out.append({"id": "INS", "kind": "coverage", "label": "Coverage check", "href": chart, "text":
                        f"Insurance eligibility check {el['checked_at'][:10]}: {el.get('label') or el.get('status')}. "
                        f"{el.get('message') or ''} Plan: {el.get('plan') or '-'}." + (" (check is stale)" if el.get("stale") else "")})
    except Exception:
        pass

    appts = sorted(p["appointments"], key=lambda a: a["start"])
    if appts:
        out.append({"id": "A", "kind": "appointments", "label": "Appointments", "href": f"/schedule?date={date.today().isoformat()}", "text":
                    "Appointments: " + "; ".join(f"{a['start'][:16].replace('T', ' ')} with {a['provider_name']}, {a['reason'] or a['visit_type']}, "
                                                 f"status {a['status']}" for a in appts)})
    msgs = portal.list_messages(patient_id=patient_id)[:12]
    if msgs:
        out.append({"id": "M", "kind": "messages", "label": "Portal messages", "href": "/inbox", "text":
                    "Patient portal messages (newest first): " + " | ".join(
                        f"{m['created_at'][:10]} {'patient → clinic' if m['direction'] == 'to_clinic' else 'clinic → patient'} "
                        f"({m['kind']}, {m['status']}): {m['subject']}: {(m['body'] or '')[:300]}" for m in msgs)})
    return out


class ChartAnswer(BaseModel):
    answer: str = Field(description="Direct answer, 1-6 short sentences or '- ' bullets, with source ids in square brackets after each fact, e.g. [V12]")
    not_in_chart: bool = Field(description="True if the chart doesn't contain the answer")
    follow_ups: list[str] = Field(description="Up to 3 short follow-up questions the user might ask next")


SYSTEM = """You are a chart assistant inside a primary-care clinic's software. Staff (doctors, nurses, front desk,
billers) ask questions about ONE patient. Answer ONLY from the SOURCES below.
Rules:
- Every fact gets its source id in square brackets right after it, e.g. "BP was 152/94 [V3]". Use only ids that exist.
- If the chart doesn't say, answer "That isn't in the chart." (and set not_in_chart) and suggest where it might be found.
  Never guess, never use outside knowledge about this patient.
- Trends: list the values with dates in order, then say plainly whether it is going up, down or flat.
- You may summarize, compare and point out open care gaps or abnormal results. Do NOT recommend new medicines, doses or
  diagnoses. If asked for a treatment decision (e.g. "should I increase the dose?"), say in one short sentence that the
  decision is the clinician's, then list the chart facts that matter for it (current dose, recent values with dates,
  allergies, relevant results), with sources. That is NOT "not in the chart".
- Be brief and scannable. Plain text only: no markdown headings or bold. Dates like "Nov 20". Today is {today}."""


class AskBody(BaseModel):
    question: str
    history: list[dict] = []    # [{q, a}] earlier turns in this panel, for follow-up questions


@router.post("/patients/{patient_id}/ask")
async def ask(patient_id: int, body: AskBody):
    q = body.question.strip()
    if not q:
        raise HTTPException(400, "Ask a question")
    if len(q) > 500:
        raise HTTPException(400, "That question is too long")
    srcs = sources_for(patient_id)
    if srcs is None:
        raise HTTPException(404, "Patient not found")
    by_id = {s["id"]: s for s in srcs}
    doc = "\n\n".join(f"[{s['id']}] {s['label']}\n{s['text']}" for s in srcs)
    turns = "".join(f"\nEarlier question: {h.get('q', '')}\nEarlier answer: {h.get('a', '')}" for h in body.history[-3:])
    prompt = f"SOURCES:\n{doc}\n{turns}\n\nQUESTION: {q}"
    try:
        result, model = await ai.generate(config.SCRIBE_MODELS, prompt, ChartAnswer,
                                          system=SYSTEM.replace("{today}", _fmt_date(date.today().isoformat())), thinking="low")
    except ai.AIUnavailable as e:
        raise HTTPException(503, str(e))
    answer = result.answer.replace("**", "").strip()
    if answer.startswith("- "):   # bullets the model ran together on one line
        answer = re.sub(r"\s+-\s+(?=[A-Z])", "\n- ", answer)
    # keep citations that exist; drop invented ids (and the brackets around them)
    answer = re.sub(r"\s*\[([A-Z]{1,3}\d*)\]", lambda m: f" [{m.group(1)}]" if m.group(1) in by_id else "", answer)
    cited = list(dict.fromkeys(re.findall(r"\[([A-Z]{1,3}\d*)\]", answer)))
    return {"answer": answer, "not_in_chart": result.not_in_chart, "follow_ups": result.follow_ups[:3], "model": model,
            "sources": [{k: by_id[i][k] for k in ("id", "kind", "label", "href")} for i in cited]}


@router.get("/patients/{patient_id}/ask/sources")
def sources(patient_id: int):
    """What the assistant can see (for debugging and the 'what does it know' tooltip)."""
    srcs = sources_for(patient_id)
    if srcs is None:
        raise HTTPException(404, "Patient not found")
    return srcs
