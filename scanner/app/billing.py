"""Claims: AI-suggested codes, staff review, and the claim checker ("scrubber").

A claim is created when a provider signs an office visit. Codes live on the claim as JSON:
  diagnoses:  [{code, description, evidence, confidence, reason, source: ai|manual, status: suggested|accepted|rejected}]
  procedures: [{... same ..., units, charge, modifiers: [], dx: [icd codes this line is billed for]}]
Only *accepted* codes go on the claim. The checker runs on every read, so fixing the
patient record (e.g. adding a member ID) clears the issue immediately.
"""
import json
from datetime import date, datetime

from . import clinic, codes
from . import payer as payer_rules

SCHEMA = """
CREATE TABLE IF NOT EXISTS claims (
    id INTEGER PRIMARY KEY,
    encounter_id INTEGER UNIQUE REFERENCES encounters(id),
    patient_id INTEGER REFERENCES patients(id), provider_id INTEGER REFERENCES providers(id),
    status TEXT,                -- review | ready | submitted | paid | partial | denied | appealed | closed
    diagnoses TEXT, procedures TEXT,
    ai_status TEXT, ai_message TEXT, em_rationale TEXT,
    paid_amount REAL, denial_code TEXT, denial_reason TEXT,
    created_at TEXT, updated_at TEXT, submitted_at TEXT,
    remittance TEXT, appeal TEXT, prior_auth TEXT
);
"""
CLOSED = ("submitted", "paid", "partial", "denied", "appealed", "closed")
JSON_FIELDS = ("diagnoses", "procedures", "remittance", "appeal")


def init() -> None:
    with clinic._conn() as con:
        con.executescript(SCHEMA)
        have = {r["name"] for r in con.execute("PRAGMA table_info(claims)")}
        for col in ("remittance", "appeal", "prior_auth"):  # databases created before Phase 5
            if col not in have:
                con.execute(f"ALTER TABLE claims ADD COLUMN {col} TEXT")


def reset() -> None:
    with clinic._conn() as con:
        con.execute("DELETE FROM claims")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _row(r) -> dict:
    d = dict(r)
    d["diagnoses"] = json.loads(d["diagnoses"] or "[]")
    d["procedures"] = json.loads(d["procedures"] or "[]")
    d["remittance"] = json.loads(d["remittance"]) if d.get("remittance") else None
    d["appeal"] = json.loads(d["appeal"]) if d.get("appeal") else None
    return d


# ---- storage ---------------------------------------------------------------------
def create_for_encounter(enc_id: int) -> int:
    """Create (or return the existing) claim for a signed office visit."""
    e = clinic.get_encounter(enc_id)
    with clinic._conn() as con:
        r = con.execute("SELECT id FROM claims WHERE encounter_id = ?", (enc_id,)).fetchone()
        if r:
            return r["id"]
        cur = con.execute(
            """INSERT INTO claims (encounter_id, patient_id, provider_id, status, diagnoses, procedures, ai_status,
                                   created_at, updated_at) VALUES (?, ?, ?, 'review', '[]', '[]', 'pending', ?, ?)""",
            (enc_id, e["patient_id"], e["provider_id"], _now(), _now()),
        )
        return cur.lastrowid


def get_raw(claim_id: int) -> dict | None:
    with clinic._conn() as con:
        r = con.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
    return _row(r) if r else None


def claim_for_encounter(enc_id: int) -> dict | None:
    with clinic._conn() as con:
        r = con.execute("SELECT * FROM claims WHERE encounter_id = ?", (enc_id,)).fetchone()
    return _row(r) if r else None


def update(claim_id: int, **fields) -> None:
    for k in JSON_FIELDS:
        if k in fields and fields[k] is not None:
            fields[k] = json.dumps(fields[k])
    fields["updated_at"] = _now()
    with clinic._conn() as con:
        con.execute(f"UPDATE claims SET {', '.join(f'{k} = ?' for k in fields)} WHERE id = ?", (*fields.values(), claim_id))


def list_claims() -> list[dict]:
    with clinic._conn() as con:
        rows = con.execute(
            """SELECT c.*, e.date AS dos, p.first_name, p.last_name, p.mrn, py.name AS payer_name, pr.name AS provider_name
               FROM claims c JOIN encounters e ON e.id = c.encounter_id JOIN patients p ON p.id = c.patient_id
               LEFT JOIN payers py ON py.id = p.payer_id LEFT JOIN providers pr ON pr.id = c.provider_id
               ORDER BY e.date DESC, c.id DESC"""
        ).fetchall()
    out = []
    for r in rows:
        c = _row(r)
        c["total_charge"] = total_charge(c)
        c["issues"] = _issue_counts(c) if c["status"] not in CLOSED else {"error": 0, "warning": 0}
        out.append(c)
    return out


def detail(claim_id: int) -> dict | None:
    c = get_raw(claim_id)
    if c is None:
        return None
    enc = clinic.get_encounter(c["encounter_id"])
    patient = clinic.get_patient(c["patient_id"])
    provider = next((p for p in clinic.providers() if p["id"] == c["provider_id"]), None)
    payer = next((p for p in clinic.payers() if p["id"] == patient["payer_id"]), None)
    c.update({
        "encounter": enc, "patient": patient, "provider": provider, "payer": payer,
        "total_charge": total_charge(c), "patient_status": patient_status(c["patient_id"], enc),
        "issues": check(c, enc, patient, provider, payer) if c["status"] not in CLOSED else [],
    })
    return c


def accepted(items: list[dict]) -> list[dict]:
    return [x for x in items if x.get("status") == "accepted"]


def total_charge(c: dict) -> float:
    return round(sum(p.get("charge", 0) * p.get("units", 1) for p in accepted(c["procedures"])), 2)


def make_line(kind: str, code: str, source: str = "manual", **extra) -> dict:
    line = {"code": code, "description": codes.describe(code), "evidence": extra.get("evidence", ""),
            "confidence": extra.get("confidence", "high"), "reason": extra.get("reason", ""),
            "source": source, "status": extra.get("status", "accepted" if source == "manual" else "suggested")}
    if kind == "cpt":
        line.update({"units": extra.get("units", 1), "charge": codes.charge(code),
                     "modifiers": extra.get("modifiers", []), "dx": extra.get("dx", [])})
    return line


# ---- new vs established patient -----------------------------------------------
def patient_status(patient_id: int, enc: dict) -> str:
    """'new' unless the patient had a signed office visit in the 3 years before this one (the CMS rule)."""
    with clinic._conn() as con:
        r = con.execute(
            """SELECT 1 FROM encounters WHERE patient_id = ? AND id != ? AND type != 'screening' AND status = 'signed'
               AND date < ? AND date >= date(?, '-3 years') LIMIT 1""",
            (patient_id, enc["id"], enc["date"], enc["date"]),
        ).fetchone()
    return "established" if r else "new"


def _age_on(dob: str | None, on: str) -> int | None:
    if not dob:
        return None
    b, d = date.fromisoformat(dob), date.fromisoformat(on)
    return d.year - b.year - ((d.month, d.day) < (b.month, b.day))


def _bmi(v: dict) -> float | None:
    try:
        inches = float(v.get("height_ft") or 0) * 12 + float(v.get("height_in") or 0)
        return round(703 * float(v["weight_lbs"]) / inches ** 2, 1) if inches and v.get("weight_lbs") else None
    except (ValueError, KeyError):
        return None


# ---- claim checker -----------------------------------------------------------------
def check(c: dict, enc: dict, patient: dict, provider: dict | None, payer: dict | None) -> list[dict]:
    """Returns issues: {level: error|warning|info, message, fix?}. Errors block the claim."""
    issues = []

    def add(level, message, fix=None):
        issues.append({"level": level, "message": message, "fix": fix})

    dxs, procs = accepted(c["diagnoses"]), accepted(c["procedures"])
    dx_codes = [d["code"] for d in dxs]
    pending = [x for x in c["diagnoses"] + c["procedures"] if x.get("status") == "suggested"]

    # --- patient & insurance ---
    if not payer:
        add("error", "No insurance on file for this patient.", {"type": "edit_patient", "label": "Add insurance"})
    elif payer["kind"] == "self":
        add("info", "Self-pay patient: this becomes a patient statement, not an insurance claim.")
    elif not patient.get("member_id"):
        add("error", f"Missing insurance member ID ({payer['name']}). Claims without it are rejected.",
            {"type": "edit_patient", "label": "Add member ID"})
    if not patient.get("dob"):
        add("error", "Patient date of birth is missing.", {"type": "edit_patient", "label": "Add date of birth"})
    if not patient.get("sex"):
        add("error", "Patient sex is missing (required on the claim form).", {"type": "edit_patient", "label": "Add sex"})
    if not patient.get("address") and payer and payer["kind"] != "self":
        add("warning", "Patient address is missing. Some insurers require it.", {"type": "edit_patient", "label": "Add address"})
    if not provider or not provider.get("npi"):
        add("error", "Rendering provider NPI is missing.")

    # --- codes present ---
    if pending:
        add("warning", f"{len(pending)} AI suggestion{'s' if len(pending) != 1 else ''} not reviewed yet. Accept or reject each code.")
    pending_dx = any(x.get("status") == "suggested" for x in c["diagnoses"])
    pending_px = any(x.get("status") == "suggested" for x in c["procedures"])
    if not dxs and not pending_dx:
        add("error", "No diagnosis codes. Every claim needs at least one.")
    if not procs and not pending_px:
        add("error", "No procedure codes. Add the office visit level (E/M) at least.")
    if len(dxs) > 12:
        add("error", "A claim form holds at most 12 diagnosis codes.")
    seen = set()
    for x in dxs + procs:
        if x["code"] in seen:
            add("error", f"{x['code']} is listed twice.", {"type": "remove", "code": x["code"], "label": f"Remove duplicate {x['code']}"})
        seen.add(x["code"])

    # --- diagnosis conflicts ---
    for a, b, why in codes.CONFLICTS:
        has_a = [d for d in dx_codes if d == a or (a.endswith(".") and d.startswith(a))]
        has_b = [d for d in dx_codes if d == b or (b.endswith(".") and d.startswith(b))]
        if has_a and has_b:
            add("error", why + ".", {"type": "remove", "code": has_a[0], "label": f"Remove {has_a[0]}"})

    # --- E/M rules ---
    status = patient_status(patient["id"], enc)
    ems = [p for p in procs if p["code"] in codes.EM_CODES]
    prev = [p for p in procs if p["code"] in codes.PREVENTIVE]
    if len(ems) > 1:
        lower = sorted(ems, key=lambda p: p["code"])[0]
        add("error", "Only one office-visit level (E/M) can be billed per visit.",
            {"type": "remove", "code": lower["code"], "label": f"Remove {lower['code']}"})
    for p in ems:
        if status == "established" and p["code"] in codes.EM_NEW:
            to = codes.EM_EST[codes.EM_NEW.index(p["code"])]
            add("error", f"{p['code']} is a NEW-patient code, but this patient was seen in the last 3 years (established).",
                {"type": "swap", "from": p["code"], "to": to, "label": f"Change to {to}"})
        if status == "new" and p["code"] in codes.EM_EST:
            to = codes.EM_NEW[codes.EM_EST.index(p["code"])]
            add("error", f"{p['code']} is an ESTABLISHED-patient code, but this is the patient's first visit (new patient).",
                {"type": "swap", "from": p["code"], "to": to, "label": f"Change to {to}"})
    age = _age_on(patient.get("dob"), enc["date"])
    for p in prev:
        band = 0 if age is not None and age < 40 else 1 if age is not None and age < 65 else 2
        right = (codes.PREVENTIVE_NEW if status == "new" else codes.PREVENTIVE_EST)[band]
        if age is not None and p["code"] != right:
            add("error", f"{p['code']} doesn't match a {status} patient aged {age}.",
                {"type": "swap", "from": p["code"], "to": right, "label": f"Change to {right}"})
    if prev and ems:
        for p in ems:
            if "25" not in p.get("modifiers", []):
                add("error", f"A problem visit billed with a preventive exam needs modifier -25 on {p['code']}.",
                    {"type": "modifier", "code": p["code"], "modifier": "25", "label": f"Add modifier 25 to {p['code']}"})

    # --- medical necessity: each procedure must point to a diagnosis that justifies it ---
    for p in procs:
        linked = [d for d in p.get("dx", []) if d in dx_codes]
        if not linked:
            support = _supporting(p["code"], dx_codes)
            add("error", f"{p['code']} isn't linked to any diagnosis.",
                {"type": "link", "code": p["code"], "dx": support, "label": f"Link to {support}"} if support else None)
            continue
        if len(linked) > 4:
            add("warning", f"{p['code']} points to {len(linked)} diagnoses; the claim form allows 4.")
        need = codes.SUPPORTED_BY.get(p["code"])
        if need and not any(any(d.startswith(n) for n in need) for d in linked):
            # Only link a diagnosis that is already documented. Never add one just to get paid (that's upcoding).
            support = _supporting(p["code"], dx_codes)
            if support:
                add("error", f"Medical necessity: {p['code']} ({p['description']}) isn't linked to the diagnosis that "
                             f"justifies it. Insurers deny this.",
                    {"type": "link", "code": p["code"], "dx": support, "label": f"Link to {support}"})
            else:
                add("error", f"Medical necessity: nothing documented in this visit justifies {p['code']} "
                             f"({p['description']}). Document the reason in the note, or remove the code.",
                    {"type": "remove", "code": p["code"], "label": f"Remove {p['code']}"})

    # --- BMI codes ---
    bmi_codes = [d for d in dx_codes if d.startswith("Z68.")]
    if bmi_codes and not any(d.startswith("E66.") for d in dx_codes):
        add("warning", "BMI codes (Z68.x) are only billable alongside a documented weight diagnosis (E66.x).",
            {"type": "remove", "code": bmi_codes[0], "label": f"Remove {bmi_codes[0]}"})
    measured = _bmi(enc.get("vitals") or {})
    if measured and bmi_codes:
        right = codes.bmi_code(measured)
        if right and right not in bmi_codes:
            add("error", f"BMI code {bmi_codes[0]} doesn't match the recorded BMI of {measured}.",
                {"type": "swap", "from": bmi_codes[0], "to": right, "label": f"Change to {right}"})

    # --- this insurer's own rules (prevent denials before submitting) ---
    for msg in payer_rules.warnings_for(c, payer):
        fix = {"type": "prior_auth", "label": "Enter auth #"} if "prior authorization" in msg else None
        add("warning", msg, fix)

    # --- money & timing ---
    if procs and total_charge(c) <= 0:
        add("error", "Total charge is $0.")
    if (date.today() - date.fromisoformat(enc["date"])).days > 365:
        add("error", "Past the 1-year timely filing limit for most insurers.")

    order = {"error": 0, "warning": 1, "info": 2}
    return sorted(issues, key=lambda i: order[i["level"]])


def _supporting(cpt: str, dx_codes: list[str]) -> str | None:
    need = codes.SUPPORTED_BY.get(cpt)
    for d in dx_codes:
        if need is None or any(d.startswith(n) for n in need):
            return d
    return None


def _issue_counts(c: dict) -> dict:
    enc = clinic.get_encounter(c["encounter_id"])
    patient = clinic.get_patient(c["patient_id"])
    provider = next((p for p in clinic.providers() if p["id"] == c["provider_id"]), None)
    payer = next((p for p in clinic.payers() if p["id"] == patient["payer_id"]), None)
    issues = check(c, enc, patient, provider, payer)
    return {"error": sum(i["level"] == "error" for i in issues), "warning": sum(i["level"] == "warning" for i in issues)}


def apply_fix(c: dict, fix: dict) -> dict:
    """One-click fixes from the checker. Returns updated {diagnoses, procedures}."""
    dxs, procs = c["diagnoses"], c["procedures"]
    t = fix["type"]
    if t == "remove":
        dxs = [d for d in dxs if not (d["code"] == fix["code"] and d["status"] == "accepted")] if fix["code"] in codes.ICD10 else dxs
        if fix["code"] in codes.CPT:
            keep, removed = [], False
            for p in procs:  # remove one copy (handles duplicates)
                if not removed and p["code"] == fix["code"] and p["status"] == "accepted":
                    removed = True
                    continue
                keep.append(p)
            procs = keep
        for p in procs:
            p["dx"] = [d for d in p.get("dx", []) if d != fix["code"]]
    elif t == "swap":
        for x in dxs + procs:
            if x["code"] == fix["from"] and x["status"] == "accepted":
                new = make_line("cpt" if fix["to"] in codes.CPT else "dx", fix["to"])
                x.update({k: new[k] for k in ("code", "description")})
                if "charge" in new:
                    x["charge"] = new["charge"]
        for p in procs:
            p["dx"] = [fix["to"] if d == fix["from"] else d for d in p.get("dx", [])]
    elif t == "modifier":
        for p in procs:
            if p["code"] == fix["code"] and fix["modifier"] not in p.setdefault("modifiers", []):
                p["modifiers"].append(fix["modifier"])
    elif t == "link":
        for p in procs:
            if p["code"] == fix["code"] and fix["dx"] not in p.setdefault("dx", []):
                p["dx"].insert(0, fix["dx"])
    elif t == "add_dx":
        if not any(d["code"] == fix["code"] and d["status"] == "accepted" for d in dxs):
            dxs.append(make_line("dx", fix["code"], reason="Added by claim checker"))
        if fix.get("for"):
            for p in procs:
                if p["code"] == fix["for"] and fix["code"] not in p.setdefault("dx", []):
                    p["dx"].insert(0, fix["code"])
    return {"diagnoses": dxs, "procedures": procs}
