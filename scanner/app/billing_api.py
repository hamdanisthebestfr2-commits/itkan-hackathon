"""REST API for billing: claims, AI coding, code review, claim checker fixes."""
import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import billing, codes, coder
from .events import broadcast

router = APIRouter(prefix="/api")
_tasks: set = set()  # keep background coding tasks referenced until they finish


def start_coding(claim_id: int) -> None:
    task = asyncio.create_task(coder.code_claim(claim_id))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


def _claim_or_404(claim_id: int) -> dict:
    c = billing.get_raw(claim_id)
    if c is None:
        raise HTTPException(404, "Claim not found")
    return c


def _editable(c: dict) -> None:
    if c["status"] in billing.CLOSED:
        raise HTTPException(409, f"This claim is {c['status']} and can't be edited")


@router.get("/claims")
def claims():
    return billing.list_claims()


@router.get("/claims/{claim_id}")
def claim(claim_id: int):
    c = billing.detail(claim_id)
    if c is None:
        raise HTTPException(404, "Claim not found")
    return c


@router.get("/encounters/{enc_id}/claim")
def claim_for_visit(enc_id: int):
    c = billing.claim_for_encounter(enc_id)
    return {"claim_id": c["id"] if c else None, "ai_status": c["ai_status"] if c else None,
            "status": c["status"] if c else None}


@router.post("/claims/{claim_id}/ai-code")
async def run_ai(claim_id: int):
    _editable(_claim_or_404(claim_id))
    start_coding(claim_id)
    return {"ok": True}


class CodesBody(BaseModel):
    diagnoses: list[dict]
    procedures: list[dict]


@router.put("/claims/{claim_id}/codes")
def save_codes(claim_id: int, body: CodesBody):
    """Staff edits: accept/reject suggestions, add/remove codes, change links/units/modifiers."""
    c = _claim_or_404(claim_id)
    _editable(c)
    dxs, procs = [], []
    for d in body.diagnoses:
        if d.get("code") not in codes.ICD10:
            raise HTTPException(400, f"{d.get('code')} isn't on the approved diagnosis list")
        dxs.append({**billing.make_line("dx", d["code"]), **{k: d[k] for k in ("evidence", "confidence", "reason", "source", "status") if k in d}})
    for p in body.procedures:
        if p.get("code") not in codes.CPT:
            raise HTTPException(400, f"{p.get('code')} isn't on the approved procedure list")
        line = billing.make_line("cpt", p["code"])
        line.update({k: p[k] for k in ("evidence", "confidence", "reason", "source", "status", "modifiers", "dx") if k in p})
        line["units"] = max(1, min(int(p.get("units", 1)), 99))
        procs.append(line)
    billing.update(claim_id, diagnoses=dxs, procedures=procs, status="review")
    broadcast({"type": "claim_updated", "claim_id": claim_id})
    return billing.detail(claim_id)


class FixBody(BaseModel):
    fix: dict


@router.post("/claims/{claim_id}/fix")
def fix(claim_id: int, body: FixBody):
    c = _claim_or_404(claim_id)
    _editable(c)
    billing.update(claim_id, **billing.apply_fix(c, body.fix), status="review")
    broadcast({"type": "claim_updated", "claim_id": claim_id})
    return billing.detail(claim_id)


@router.post("/claims/{claim_id}/ready")
def mark_ready(claim_id: int):
    c = billing.detail(claim_id)
    if c is None:
        raise HTTPException(404, "Claim not found")
    _editable(c)
    errors = [i for i in c["issues"] if i["level"] == "error"]
    if errors:
        raise HTTPException(409, f"Fix {len(errors)} claim checker error{'s' if len(errors) != 1 else ''} first")
    if any(x["status"] == "suggested" for x in c["diagnoses"] + c["procedures"]):
        raise HTTPException(409, "Review every AI suggestion (accept or reject) first")
    billing.update(claim_id, status="ready")
    broadcast({"type": "claim_updated", "claim_id": claim_id})
    return billing.detail(claim_id)


@router.post("/claims/{claim_id}/reopen")
def reopen(claim_id: int):
    c = _claim_or_404(claim_id)
    _editable(c)
    billing.update(claim_id, status="review")
    broadcast({"type": "claim_updated", "claim_id": claim_id})
    return billing.detail(claim_id)


@router.get("/codes")
def code_search(q: str = "", kind: str | None = None):
    found = codes.search(q, limit=40)
    return [x for x in found if not kind or x["kind"] == kind][:12]


# ---- Phase 5: submit to the (mock) insurer, denials, appeals -------------------------
from . import ai, appeals, payer  # noqa: E402

CLEARINGHOUSE_SECONDS = 2.5   # feels like a real round trip in the demo
APPEAL_REVIEW_SECONDS = 3.0


def _status_from(rem: dict) -> str:
    open_denials = [l for l in rem["lines"] if l["status"] == "denied" and not l.get("written_off")]
    if not open_denials:
        return "paid" if rem["total_paid"] > 0 else "closed"
    return "partial" if rem["total_paid"] > 0 else "denied"


def _adjudicate_now(claim_id: int) -> None:
    c = billing.detail(claim_id)
    rem = payer.adjudicate(c)
    billing.update(claim_id, remittance=rem, status=_status_from(rem), paid_amount=rem["total_paid"])
    broadcast({"type": "claim_updated", "claim_id": claim_id, "event": "adjudicated"})


async def _adjudicate_later(claim_id: int) -> None:
    await asyncio.sleep(CLEARINGHOUSE_SECONDS)
    _adjudicate_now(claim_id)


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


class PriorAuthBody(BaseModel):
    number: str


@router.post("/claims/{claim_id}/prior-auth")
def set_prior_auth(claim_id: int, body: PriorAuthBody):
    c = _claim_or_404(claim_id)
    _editable(c)
    billing.update(claim_id, prior_auth=body.number.strip() or None)
    broadcast({"type": "claim_updated", "claim_id": claim_id})
    return billing.detail(claim_id)


@router.post("/claims/{claim_id}/submit")
async def submit(claim_id: int):
    c = billing.detail(claim_id)
    if c is None:
        raise HTTPException(404, "Claim not found")
    if c["status"] != "ready":
        raise HTTPException(409, "Approve the claim before submitting it")
    if c["payer"] and c["payer"]["kind"] == "self":
        raise HTTPException(400, "Self-pay patient: there's no insurer to bill. Send the patient a statement instead")
    billing.update(claim_id, status="submitted", submitted_at=billing._now(), remittance=None)
    broadcast({"type": "claim_updated", "claim_id": claim_id, "event": "submitted"})
    _spawn(_adjudicate_later(claim_id))
    return {"ok": True}


@router.post("/claims/{claim_id}/check-status")
def check_status(claim_id: int):
    """For claims sitting in 'submitted' (e.g. from demo history): get the insurer's answer now."""
    c = _claim_or_404(claim_id)
    if c["status"] != "submitted":
        raise HTTPException(409, "Only submitted claims are waiting on the insurer")
    _adjudicate_now(claim_id)
    return billing.detail(claim_id)


class LineBody(BaseModel):
    code: str


def _denied_line(c: dict, code: str) -> dict:
    rem = c.get("remittance")
    line = next((l for l in (rem or {}).get("lines", []) if l["code"] == code and l["status"] == "denied"), None)
    if line is None:
        raise HTTPException(404, f"No denied line {code} on this claim")
    return line


@router.post("/claims/{claim_id}/denial/analyze")
async def analyze_denial(claim_id: int, body: LineBody):
    c = billing.detail(claim_id)
    if c is None:
        raise HTTPException(404, "Claim not found")
    line = _denied_line(c, body.code)
    try:
        a = await appeals.analyze(c, line)
    except ai.AIUnavailable as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        raise HTTPException(502, f"AI analysis failed: {str(e)[:200]}")
    appeal = {"line_code": body.code, "status": "draft", "created": billing._now(), **a.model_dump()}
    billing.update(claim_id, appeal=appeal)
    broadcast({"type": "claim_updated", "claim_id": claim_id})
    return billing.detail(claim_id)


class LetterBody(BaseModel):
    letter: str


@router.put("/claims/{claim_id}/appeal")
def save_letter(claim_id: int, body: LetterBody):
    c = _claim_or_404(claim_id)
    if not c["appeal"] or c["appeal"]["status"] != "draft":
        raise HTTPException(409, "No draft appeal to edit")
    billing.update(claim_id, appeal={**c["appeal"], "letter": body.letter})
    return {"ok": True}


async def _review_later(claim_id: int) -> None:
    await asyncio.sleep(APPEAL_REVIEW_SECONDS)
    c = billing.detail(claim_id)
    before = c["remittance"]["total_paid"]
    rem = payer.review_appeal(c, c["remittance"])
    recovered = round(rem["total_paid"] - before, 2)
    appeal = {**c["appeal"], "status": "approved" if recovered > 0 else "upheld", "recovered": recovered,
              "decided": billing._now()}
    billing.update(claim_id, remittance=rem, appeal=appeal, status=_status_from(rem), paid_amount=rem["total_paid"])
    broadcast({"type": "claim_updated", "claim_id": claim_id, "event": "appeal_decided"})


@router.post("/claims/{claim_id}/appeal/submit")
async def submit_appeal(claim_id: int, body: LetterBody):
    c = _claim_or_404(claim_id)
    if not c["appeal"] or c["appeal"]["status"] != "draft":
        raise HTTPException(409, "Draft an appeal first")
    if len(body.letter.strip()) < 100:
        raise HTTPException(400, "The appeal letter is too short")
    billing.update(claim_id, status="appealed",
                   appeal={**c["appeal"], "letter": body.letter, "status": "submitted", "submitted": billing._now()})
    broadcast({"type": "claim_updated", "claim_id": claim_id, "event": "appeal_submitted"})
    _spawn(_review_later(claim_id))
    return {"ok": True}


@router.post("/claims/{claim_id}/write-off")
def write_off(claim_id: int, body: LineBody):
    c = _claim_or_404(claim_id)
    rem = c.get("remittance")
    line = next((l for l in (rem or {}).get("lines", []) if l["code"] == body.code and l["status"] == "denied"), None)
    if line is None:
        raise HTTPException(404, f"No denied line {body.code} on this claim")
    line["written_off"] = True
    line["remarks"].append("Written off by clinic (contractual)")
    rem["written_off"] = round(sum(l["charge"] for l in rem["lines"] if l.get("written_off")), 2)
    rem["denied_amount"] = round(sum(l["charge"] for l in rem["lines"] if l["status"] == "denied" and not l.get("written_off")), 2)
    appeal = c["appeal"]
    if appeal and appeal.get("line_code") == body.code and appeal["status"] == "draft":
        appeal = {**appeal, "status": "written_off"}
    billing.update(claim_id, remittance=rem, appeal=appeal, status=_status_from(rem))
    broadcast({"type": "claim_updated", "claim_id": claim_id})
    return billing.detail(claim_id)


@router.post("/claims/{claim_id}/correct")
def correct_and_resubmit(claim_id: int):
    """Reopen a denied claim as a corrected claim: fix the codes/info, approve, submit again."""
    c = _claim_or_404(claim_id)
    if c["status"] not in ("denied", "partial"):
        raise HTTPException(409, "Only denied claims can be corrected")
    billing.update(claim_id, status="review", remittance=None, appeal=None, paid_amount=None)
    broadcast({"type": "claim_updated", "claim_id": claim_id})
    return billing.detail(claim_id)
