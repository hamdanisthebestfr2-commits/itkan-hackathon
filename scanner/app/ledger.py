"""Patient balances, payments (copay at check-in, front desk, portal) and statements (Track B).

What a patient owes is computed live from the claims, so nothing here edits billing data:
  - insured visits: the patient-responsibility amounts on the insurer's remittance (PR-3 copay, PR-2
    coinsurance). Denied and written-off lines are the clinic's loss (CO = contractual), never billed to the patient.
  - self-pay visits: the approved claim's charges at the clinic's self-pay discount.
  - visits still with the insurer are listed as "pending insurance" (not owed yet).
Payments live in the `payments` table. Balance = charges - payments (negative = credit on the account).

The card "processor" is a mock: it validates the number (Luhn), expiry and CVC, declines the usual test
numbers, and stores ONLY the brand and last 4 digits. No real card is ever charged.
No FOREIGN KEY on patient_id: clinic.reset() deletes patients with foreign keys ON; seed() clears this table.
"""
import asyncio
import random
from datetime import date, datetime, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import billing, clinic, eligibility
from .events import broadcast

SCHEMA = """
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY,
    patient_id INTEGER, appointment_id INTEGER, claim_id INTEGER,
    amount REAL,
    kind TEXT,                  -- copay | payment
    method TEXT,                -- card | cash | check
    card_brand TEXT, card_last4 TEXT, check_number TEXT, auth_code TEXT,
    source TEXT,                -- check_in | front_desk | portal | seed
    receipt TEXT, note TEXT, created_at TEXT
);
"""
SELF_PAY_DISCOUNT = 0.40          # fictional clinic policy: self-pay patients pay 60% of the charge
SELF_PAY_DEPOSIT = 95.00          # collected at check-in from self-pay / uninsured patients
STATEMENT_DUE_DAYS = 30
DECLINES = {"4000000000000002": "Card declined by the issuer.", "4000000000009995": "Insufficient funds."}
SOURCES = ("check_in", "front_desk", "portal")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def init() -> None:
    with clinic._conn() as con:
        con.executescript(SCHEMA)


def reset() -> None:
    init()
    with clinic._conn() as con:
        con.execute("DELETE FROM payments")


# ---- charges (from claims) ------------------------------------------------------------------
def _payer(patient: dict) -> dict | None:
    return next((p for p in clinic.payers() if p["id"] == patient.get("payer_id")), None)


def visit_charges(patient_id: int) -> tuple[list[dict], list[dict]]:
    """(charges the patient owes, visits still waiting on insurance)."""
    patient = clinic.get_patient(patient_id)
    payer = _payer(patient)
    providers = {p["id"]: p["name"] for p in clinic.providers()}
    with clinic._conn() as con:
        rows = con.execute(
            """SELECT c.id FROM claims c JOIN encounters e ON e.id = c.encounter_id
               WHERE c.patient_id = ? ORDER BY e.date, c.id""", (patient_id,)).fetchall()
    owed, pending = [], []
    for r in rows:
        c = billing.get_raw(r["id"])
        enc = clinic.get_encounter(c["encounter_id"])
        base = {"claim_id": c["id"], "dos": enc["date"], "provider": providers.get(c["provider_id"]),
                "billed": billing.total_charge(c)}
        rem = c.get("remittance")
        if rem:
            lines = [{"code": l["code"], "description": l["description"], "charge": l["charge"],
                      "insurance_paid": l["paid"], "patient_resp": l["patient_resp"],
                      "adjustment": round(l["charge"] - l["paid"] - l["patient_resp"], 2),
                      "note": (f"Denied ({l['carc']}): not billed to you" if l["status"] == "denied" else
                               "; ".join(x.replace("PR-3 copay", "Copay").replace("PR-2 coinsurance", "Coinsurance")
                                         for x in l.get("remarks", []) if x.startswith("PR-")) or None)}
                     for l in rem["lines"]]
            resp = round(sum(l["patient_resp"] for l in lines), 2)
            owed.append({**base, "type": "insurance", "date": rem.get("processed") or enc["date"],
                         "payer": rem.get("payer"), "insurance_paid": rem["total_paid"],
                         "adjustment": round(sum(l["adjustment"] for l in lines), 2), "amount": resp, "lines": lines,
                         "description": f"Visit {enc['date']}: your share after {rem.get('payer') or 'insurance'} paid"})
        elif payer and payer["kind"] == "self":
            if c["status"] == "review":      # codes not approved yet
                pending.append({**base, "status": "coding", "description": "Visit charges are being finalized"})
                continue
            price = round(base["billed"] * (1 - SELF_PAY_DISCOUNT), 2)
            lines = [{"code": p["code"], "description": p["description"], "charge": round(p["charge"] * p.get("units", 1), 2),
                      "insurance_paid": 0.0, "patient_resp": round(p["charge"] * p.get("units", 1) * (1 - SELF_PAY_DISCOUNT), 2),
                      "adjustment": round(p["charge"] * p.get("units", 1) * SELF_PAY_DISCOUNT, 2), "note": None}
                     for p in billing.accepted(c["procedures"])]
            owed.append({**base, "type": "self_pay", "date": enc["date"], "payer": None, "insurance_paid": 0.0,
                         "adjustment": round(base["billed"] - price, 2), "amount": price, "lines": lines,
                         "description": f"Visit {enc['date']}: self-pay price ({round(SELF_PAY_DISCOUNT * 100)}% self-pay discount)"})
        else:   # insured, not answered yet (being coded, approved, submitted or under appeal)
            pending.append({**base, "status": c["status"], "payer": payer and payer["name"],
                            "description": f"Visit {enc['date']}: billed to {payer['name'] if payer else 'insurance'}, waiting for their answer"})
    return owed, pending


# ---- payments -----------------------------------------------------------------------------
def payments(patient_id: int | None = None, day: str | None = None) -> list[dict]:
    where, args = [], []
    if patient_id is not None:
        where.append("patient_id = ?"); args.append(patient_id)
    if day:
        where.append("date(created_at) = ?"); args.append(day)
    with clinic._conn() as con:
        rows = con.execute(f"SELECT * FROM payments {('WHERE ' + ' AND '.join(where)) if where else ''} "
                           "ORDER BY created_at, id", args).fetchall()
    return [dict(r) for r in rows]


def _receipt(con) -> str:
    n = con.execute("SELECT count(*) FROM payments").fetchone()[0]
    return f"R-{date.today().strftime('%y%m%d')}-{1001 + n}"


def add_payment(patient_id: int, amount: float, *, kind: str = "payment", method: str = "card", source: str = "front_desk",
                appointment_id: int | None = None, card_brand: str | None = None, card_last4: str | None = None,
                check_number: str | None = None, note: str | None = None, created_at: str | None = None) -> dict:
    with clinic._conn() as con:
        cur = con.execute(
            """INSERT INTO payments (patient_id, appointment_id, amount, kind, method, card_brand, card_last4, check_number,
                                     auth_code, source, receipt, note, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (patient_id, appointment_id, round(amount, 2), kind, method, card_brand, card_last4, check_number,
             f"A{random.randint(100000, 999999)}" if method == "card" else None, source, _receipt(con), note,
             created_at or _now()))
        row = con.execute("SELECT * FROM payments WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


# ---- balance / ledger -------------------------------------------------------------------------
def balance(patient_id: int) -> dict:
    owed, pending = visit_charges(patient_id)
    pays = payments(patient_id)
    entries = [{"date": o["date"], "kind": "charge", "description": o["description"], "amount": o["amount"],
                "claim_id": o["claim_id"]} for o in owed if o["amount"]]
    entries += [{"date": p["created_at"][:10], "kind": "payment", "amount": -p["amount"], "receipt": p["receipt"],
                 "description": f"{'Copay' if p['kind'] == 'copay' else 'Payment'} · " + (
                     f"{p['card_brand']} •••• {p['card_last4']}" if p["method"] == "card" else
                     f"check #{p['check_number']}" if p["method"] == "check" else "cash") +
                    {"portal": " (paid online)", "check_in": " (at check-in)"}.get(p["source"], "")}
                for p in pays]
    entries.sort(key=lambda e: (e["date"], 0 if e["kind"] == "charge" else 1))
    running = 0.0
    for e in entries:
        running = round(running + e["amount"], 2)
        e["balance"] = running
    charged = round(sum(o["amount"] for o in owed), 2)
    paid = round(sum(p["amount"] for p in pays), 2)
    bal = round(charged - paid, 2)
    return {"patient_id": patient_id, "balance": bal, "due": max(bal, 0.0), "credit": max(-bal, 0.0),
            "charges_total": charged, "payments_total": paid, "visits": owed, "pending": pending,
            "payments": list(reversed(pays)), "entries": entries,
            "last_payment": pays[-1] if pays else None,
            "statement_date": date.today().isoformat(),
            "due_date": (date.today() + timedelta(days=STATEMENT_DUE_DAYS)).isoformat()}


def copay_status(appointment_id: int) -> dict | None:
    """What to collect at check-in for this appointment (from the insurance eligibility answer)."""
    appt = clinic.get_appointment(appointment_id)
    if appt is None:
        return None
    patient = clinic.get_patient(appt["patient_id"])
    chk = eligibility.latest(patient["id"])
    if chk is None or chk.get("stale"):
        chk = eligibility.respond(patient)              # no stored answer: ask the (mock) insurer quietly
    if chk["status"] == "active":
        due, label = chk["estimate"]["due_today"], ("Copay" if chk["estimate"]["kind"] == "copay" else "Nothing")
        note = chk["estimate"]["note"]
    else:   # self-pay, or coverage problem -> treat as self-pay at the desk
        due, label = SELF_PAY_DEPOSIT, "Self-pay deposit"
        note = (f"Self-pay visit deposit (applied to the self-pay price)." if chk["status"] == "self_pay"
                else f"{chk['label']}: collect the self-pay deposit unless the patient has a new insurance card.")
    collected = round(sum(p["amount"] for p in payments(patient["id"]) if p["appointment_id"] == appointment_id), 2)
    return {"appointment_id": appointment_id, "patient_id": patient["id"], "due": float(due), "label": label, "note": note,
            "collected": collected, "remaining": round(max(float(due) - collected, 0.0), 2),
            "coverage_status": chk["status"], "balance": balance(patient["id"])["due"]}


# ---- demo data ----------------------------------------------------------------------------------
def seed(patient_ids: list[int]) -> None:
    """Past copays paid at the visit: Maria and Aisha are paid up; James (Medicare coinsurance) and David owe."""
    reset()
    with clinic._conn() as con:
        visits = {r["patient_id"]: r["date"] for r in con.execute(
            "SELECT patient_id, max(date) AS date FROM encounters WHERE type = 'office visit' AND status = 'signed' GROUP BY patient_id")}
    for idx, amount, last4 in ((0, 25.0, "4242"), (2, 30.0, "1881")):
        pid = patient_ids[idx]
        if pid in visits:
            add_payment(pid, amount, kind="copay", method="card", source="check_in", card_brand="Visa", card_last4=last4,
                        created_at=f"{visits[pid]}T08:52:00")


# ---- mock card processor ------------------------------------------------------------------------
def _luhn(digits: str) -> bool:
    total, alt = 0, False
    for d in reversed(digits):
        n = int(d)
        if alt:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
        alt = not alt
    return total % 10 == 0


def _brand(digits: str) -> str:
    if digits.startswith("4"):
        return "Visa"
    if digits[:2] in ("34", "37"):
        return "Amex"
    if digits[:2] in {str(n) for n in range(51, 56)} or 2221 <= int(digits[:4]) <= 2720:
        return "Mastercard"
    if digits.startswith("6011") or digits.startswith("65"):
        return "Discover"
    return "Card"


def charge_card(number: str, exp: str, cvc: str) -> dict:
    digits = "".join(ch for ch in number if ch.isdigit())
    if not 13 <= len(digits) <= 19 or not _luhn(digits):
        raise HTTPException(400, "That card number isn't valid. Check the digits.")
    try:
        mm, yy = exp.replace(" ", "").split("/")
        mm, yy = int(mm), int(yy) + (2000 if len(yy.strip()) == 2 else 0)
        if not 1 <= mm <= 12:
            raise ValueError
    except ValueError:
        raise HTTPException(400, "Expiry should look like MM/YY.")
    today = date.today()
    if (yy, mm) < (today.year, today.month):
        raise HTTPException(400, "This card has expired.")
    if not cvc.isdigit() or len(cvc) not in (3, 4):
        raise HTTPException(400, "The security code (CVC) should be 3 or 4 digits.")
    if digits in DECLINES:
        raise HTTPException(402, DECLINES[digits])
    return {"brand": _brand(digits), "last4": digits[-4:]}


# ---- API ---------------------------------------------------------------------------------------
router = APIRouter(prefix="/api")


def _patient_or_404(patient_id: int) -> dict:
    p = clinic.get_patient(patient_id)
    if p is None:
        raise HTTPException(404, "Patient not found")
    return p


@router.get("/patients/{patient_id}/balance")
def patient_balance(patient_id: int):
    _patient_or_404(patient_id)
    return balance(patient_id)


@router.get("/appointments/{appointment_id}/copay")
def appointment_copay(appointment_id: int):
    s = copay_status(appointment_id)
    if s is None:
        raise HTTPException(404, "Appointment not found")
    return s


class Card(BaseModel):
    number: str
    exp: str
    cvc: str
    name: str = ""
    zip: str = ""


class PaymentBody(BaseModel):
    patient_id: int
    amount: float
    method: str = "card"             # card | cash | check
    kind: str = "payment"            # copay | payment
    source: str = "front_desk"       # check_in | front_desk | portal
    appointment_id: int | None = None
    card: Card | None = None
    check_number: str | None = None
    note: str | None = None


@router.post("/payments")
async def take_payment(body: PaymentBody):
    p = _patient_or_404(body.patient_id)
    amount = round(body.amount, 2)
    if not 0 < amount <= 10000:
        raise HTTPException(400, "Enter an amount between $0.01 and $10,000")
    if body.method not in ("card", "cash", "check") or body.kind not in ("copay", "payment") or body.source not in SOURCES:
        raise HTTPException(400, "Unknown payment method, kind or source")
    if body.source == "portal":
        if body.method != "card":
            raise HTTPException(400, "Online payments are by card")
        due = balance(p["id"])["due"]
        if due <= 0:
            raise HTTPException(400, "There is nothing to pay right now")
        if amount > due:
            raise HTTPException(400, f"That's more than your balance of ${due:.2f}")
    if body.appointment_id:
        appt = clinic.get_appointment(body.appointment_id)
        if appt is None or appt["patient_id"] != p["id"]:
            raise HTTPException(404, "Appointment not found for this patient")
    card = {}
    if body.method == "card":
        if body.card is None:
            raise HTTPException(400, "Card details are required")
        await asyncio.sleep(random.uniform(0.6, 1.0))     # the "processor"
        card = charge_card(body.card.number, body.card.exp, body.card.cvc)
    if body.method == "check" and not (body.check_number or "").strip():
        raise HTTPException(400, "Enter the check number")
    pay = add_payment(p["id"], amount, kind=body.kind, method=body.method, source=body.source,
                      appointment_id=body.appointment_id, card_brand=card.get("brand"), card_last4=card.get("last4"),
                      check_number=(body.check_number or "").strip() or None, note=body.note)
    new = balance(p["id"])
    broadcast({"type": "payment_posted", "patient_id": p["id"], "appointment_id": body.appointment_id,
               "amount": amount, "source": body.source, "balance": new["balance"]})
    return {"payment": pay, "balance": new["balance"], "due": new["due"], "credit": new["credit"]}


@router.get("/payments")
def list_payments(day: str | None = None, patient_id: int | None = None):
    rows = payments(patient_id, day)
    return {"payments": list(reversed(rows)), "total": round(sum(r["amount"] for r in rows), 2)}
