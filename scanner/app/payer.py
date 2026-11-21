"""Mock insurer: deterministic claim adjudication with real-style denial reasons (CARC codes).

The payers, policies and policy numbers are fictional. Each rule can carry an appeal test:
some denials are winnable (the record meets a policy exception), others are correct and
should be written off. That gives the AI denial fighter a real judgment call.
"""
import re
from datetime import date, timedelta

from . import clinic, codes

CARC = {
    "CO-16": "Claim lacks information or has submission/billing errors.",
    "CO-11": "The diagnosis is inconsistent with the procedure.",
    "CO-29": "The time limit for filing has expired.",
    "CO-96": "Non-covered charge(s).",
    "CO-97": "The benefit for this service is included in the payment for another service already adjudicated.",
    "CO-119": "Benefit maximum for this time period or occurrence has been reached.",
    "CO-197": "Precertification/authorization/notification absent.",
    "CO-45": "Charge exceeds fee schedule/maximum allowable (contractual adjustment).",
    "PR-3": "Co-payment amount (patient responsibility).",
    "PR-2": "Coinsurance amount (patient responsibility).",
}


def _has(note: str, *words: str) -> bool:
    n = re.sub(r"\s+", " ", (note or "").lower())
    return any(w in n for w in words)


# Per-payer rules, keyed by payer_code. Each special rule: code -> {policy, appeal(note) -> bool}
PAYERS = {
    "BBHP1": {"rate": 0.80, "copay": 25, "coins": 0.0, "prior_auth": {}, "bundled": {}, "not_covered": {},
              "frequency": {"83036": 90}},
    "PMI02": {
        "rate": 0.75, "copay": 30, "coins": 0.0,
        "prior_auth": {
            "94010": {"policy": "Policy PM-RES-114: spirometry (94010) requires prior authorization. EXCEPTION: authorization "
                                "is waived when spirometry is performed during an acute exacerbation documented in the "
                                "medical record; submit the visit note on appeal.",
                      "appeal": lambda note: _has(note, "exacerbation", "acute asthma", "acute attack")},
            "93000": {"policy": "Policy PM-CARD-020: routine ECG (93000) requires prior authorization unless chest pain or "
                                "arrhythmia is documented.",
                      "appeal": lambda note: _has(note, "chest pain", "palpitation", "arrhythmia", "irregular")},
        },
        "bundled": {}, "not_covered": {}, "frequency": {"83036": 90},
    },
    "GCC03": {
        "rate": 0.78, "copay": 20, "coins": 0.0, "prior_auth": {},
        "bundled": {
            "82962": {"policy": "Policy GC-LAB-07: fingerstick glucose by monitor (82962) is included in the payment for "
                                "the office visit and is not separately payable. No exceptions.",
                      "appeal": lambda note: False},
            "81002": {"policy": "Policy GC-LAB-07: dipstick urinalysis (81002) is included in the office visit payment.",
                      "appeal": lambda note: False},
        },
        "not_covered": {}, "frequency": {"83036": 90},
    },
    "MCR00": {
        "rate": 0.62, "copay": 0, "coins": 0.20, "prior_auth": {}, "bundled": {},
        "not_covered": {c: {"policy": "Medicare (demo) does not cover routine preventive physicals (99381-99397). Bill the "
                                      "Annual Wellness Visit (G0438/G0439) instead; the patient may be billed with a signed ABN.",
                            "appeal": lambda note: False} for c in codes.PREVENTIVE},
        "frequency": {"83036": 90},
    },
}
FREQUENCY_POLICY = ("Hemoglobin A1c (83036) is payable once every 90 days. EXCEPTION: more frequent testing is covered "
                    "after a change in diabetes therapy or when diabetes is documented as uncontrolled.")


def rules(payer_code: str | None) -> dict | None:
    return PAYERS.get(payer_code or "")


def warnings_for(c: dict, payer: dict | None) -> list[dict]:
    """Payer-specific problems the claim checker can warn about BEFORE submitting (denial prevention)."""
    r = rules(payer and payer["payer_code"])
    if not r:
        return []
    out = []
    procs = [p["code"] for p in c["procedures"] if p.get("status") == "accepted"]
    for code in procs:
        if code in r["prior_auth"] and not c.get("prior_auth"):
            out.append(f"{payer['name']} requires prior authorization for {code}. Enter the authorization number, "
                       f"or expect a CO-197 denial.")
        if code in r["bundled"]:
            out.append(f"{payer['name']} bundles {code} into the office visit. It won't be paid separately.")
        if code in r["not_covered"]:
            out.append(f"{payer['name']} doesn't cover {code}. The claim line will be denied as non-covered.")
    return out


def _paid_recently(patient_id: int, code: str, before: str, days: int, claim_id: int) -> bool:
    import json
    since = (date.fromisoformat(before) - timedelta(days=days)).isoformat()
    with clinic._conn() as con:
        rows = con.execute(
            """SELECT c.remittance FROM claims c JOIN encounters e ON e.id = c.encounter_id
               WHERE c.patient_id = ? AND c.id != ? AND e.date >= ? AND e.date < ? AND c.remittance IS NOT NULL""",
            (patient_id, claim_id, since, before),
        ).fetchall()
    for r in rows:
        for line in json.loads(r["remittance"])["lines"]:
            if line["code"] == code and line["status"] == "paid":
                return True
    return False


def adjudicate(c: dict) -> dict:
    """c = billing.detail(claim). Returns a remittance (like an ERA/EOB) with line-level results."""
    payer, patient, enc = c["payer"], c["patient"], c["encounter"]
    r = rules(payer and payer["payer_code"])
    procs = [p for p in c["procedures"] if p.get("status") == "accepted"]
    dx_codes = [d["code"] for d in c["diagnoses"] if d.get("status") == "accepted"]
    claim_level = None
    if not r:
        claim_level = ("CO-16", "No active insurance coverage found for this member.")
    elif not patient.get("member_id"):
        claim_level = ("CO-16", "Member ID missing.")
    elif (date.today() - date.fromisoformat(enc["date"])).days > 365:
        claim_level = ("CO-29", "Submitted more than 365 days after the date of service.")

    lines, copay_left = [], (r or {}).get("copay", 0)
    has_em = any(p["code"] in codes.EM_CODES for p in procs)
    for p in procs:
        charge = round(p["charge"] * p.get("units", 1), 2)
        line = {"code": p["code"], "description": p["description"], "charge": charge, "allowed": 0.0, "paid": 0.0,
                "patient_resp": 0.0, "adjustment": charge, "status": "denied", "carc": None, "carc_text": None,
                "policy": None, "appealable": False, "remarks": []}
        denial = None
        if claim_level:
            denial = (claim_level[0], claim_level[1], None, False)
        elif p["code"] in r["not_covered"]:
            rule = r["not_covered"][p["code"]]
            denial = ("CO-96", CARC["CO-96"], rule["policy"], rule["appeal"](enc["note"]))
        elif p["code"] in r["prior_auth"] and not c.get("prior_auth"):
            rule = r["prior_auth"][p["code"]]
            denial = ("CO-197", CARC["CO-197"], rule["policy"], rule["appeal"](enc["note"]))
        elif p["code"] in r["bundled"] and has_em:
            rule = r["bundled"][p["code"]]
            denial = ("CO-97", CARC["CO-97"], rule["policy"], rule["appeal"](enc["note"]))
        elif codes.SUPPORTED_BY.get(p["code"]) and not any(
                any(d.startswith(n) for n in codes.SUPPORTED_BY[p["code"]]) for d in p.get("dx", []) if d in dx_codes):
            denial = ("CO-11", CARC["CO-11"], "Procedure must be linked to a diagnosis that supports medical necessity.", False)
        elif p["code"] in r["frequency"] and _paid_recently(patient["id"], p["code"], enc["date"], r["frequency"][p["code"]], c["id"]):
            denial = ("CO-119", CARC["CO-119"], FREQUENCY_POLICY,
                      _has(enc["note"], "uncontrolled", "changed", "increase", "started insulin", "new medication"))
        if denial:
            line.update({"carc": denial[0], "carc_text": denial[1], "policy": denial[2], "appealable": denial[3]})
        else:
            allowed = round(charge * r["rate"], 2)
            resp = 0.0
            if p["code"] in codes.EM_CODES or (not has_em and copay_left == r["copay"]):
                resp = min(copay_left, allowed)
                copay_left -= resp
                if resp:
                    line["remarks"].append(f"PR-3 copay ${resp:.2f}")
            if r["coins"]:
                coins = round(allowed * r["coins"], 2)
                resp += coins
                line["remarks"].append(f"PR-2 coinsurance ${coins:.2f}")
            line.update({"allowed": allowed, "patient_resp": round(resp, 2), "paid": round(allowed - resp, 2),
                         "adjustment": round(charge - allowed, 2), "status": "paid"})
            if line["adjustment"]:
                line["remarks"].insert(0, f"CO-45 contractual adjustment ${line['adjustment']:.2f}")
        lines.append(line)

    paid = round(sum(l["paid"] for l in lines), 2)
    denied = [l for l in lines if l["status"] == "denied"]
    status = "denied" if denied and not paid else "partial" if denied else "paid"
    return {
        "payer": payer["name"] if payer else None, "processed": date.today().isoformat(),
        "claim_number": f"{(payer or {}).get('payer_code', 'NA')}-{c['id']:06d}",
        "lines": lines, "status": status,
        "total_charge": round(sum(l["charge"] for l in lines), 2),
        "total_allowed": round(sum(l["allowed"] for l in lines), 2),
        "total_paid": paid,
        "patient_resp": round(sum(l["patient_resp"] for l in lines), 2),
        "denied_amount": round(sum(l["charge"] for l in denied), 2),
    }


def review_appeal(c: dict, remittance: dict) -> dict:
    """Mock appeal review: overturns denied lines whose policy exception is met by the record."""
    r = rules(c["payer"] and c["payer"]["payer_code"])
    for line in remittance["lines"]:
        if line["status"] != "denied" or line.get("written_off"):
            continue
        if line["appealable"]:
            allowed = round(line["charge"] * r["rate"], 2)
            coins = round(allowed * r["coins"], 2) if r["coins"] else 0.0
            line.update({"status": "paid", "allowed": allowed, "patient_resp": coins, "paid": round(allowed - coins, 2),
                         "adjustment": round(line["charge"] - allowed, 2), "appeal_result": "overturned"})
            line["remarks"].append("Appeal approved: denial overturned")
        else:
            line["appeal_result"] = "upheld"
            line["remarks"].append("Appeal reviewed: denial upheld")
    paid = round(sum(l["paid"] for l in remittance["lines"]), 2)
    denied = [l for l in remittance["lines"] if l["status"] == "denied" and not l.get("written_off")]
    remittance.update({
        "total_paid": paid, "total_allowed": round(sum(l["allowed"] for l in remittance["lines"]), 2),
        "patient_resp": round(sum(l["patient_resp"] for l in remittance["lines"]), 2),
        "denied_amount": round(sum(l["charge"] for l in denied), 2),
        "status": "denied" if denied and not paid else "partial" if denied else "paid",
    })
    return remittance
