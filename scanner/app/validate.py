"""Turns raw AI readings into review-ready fields.

Two kinds of output:
- per-field status: ok (green), check (yellow: possible misread), missing (red), empty (blank optional field)
- clinical alerts: real-but-concerning readings. Screening flags, not a diagnosis.
"""
import re
from datetime import date

from .schema import FIELDS, FIELD_BY_KEY

# Plausible ranges: values outside are more likely misreads than real.
RANGES = {
    "height_ft": (3, 7), "height_in": (0, 11), "weight_lbs": (50, 500),
    "bp_systolic": (70, 250), "bp_diastolic": (40, 150), "heart_rate": (30, 220),
    "respiratory_rate": (6, 60), "spo2": (70, 100), "blood_glucose": (30, 600), "bmi": (10, 80),
}
TEMP_RANGES = {"F": (93, 108), "C": (34, 42)}


def _num(value: str | None) -> float | None:
    if value is None:
        return None
    m = re.search(r"-?\d+(\.\d+)?", value.replace(",", ""))
    return float(m.group()) if m else None


def _fmt_num(x: float) -> str:
    return str(int(x)) if x == int(x) else str(x)


def _parse_date(value: str) -> date | None:
    m = re.match(r"^\s*(\d{1,2})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{2,4})\s*$", value)
    if not m:
        return None
    month, day, year = (int(g) for g in m.groups())
    if year < 100:
        year += 2000 if year <= date.today().year % 100 else 1900
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _normalize(f, value: str | None) -> tuple[str | None, list[str]]:
    """Returns (normalized value for the form, list of issues)."""
    if value is None:
        return None, []
    issues = []
    if f.kind == "text":
        value = re.sub(r"\s+", " ", value).strip()
        if f.key == "full_name":
            if any(c.isdigit() for c in value) or len(re.sub(r"[^A-Za-z]", "", value)) < 2:
                issues.append("Doesn't look like a name")
            elif value.isupper() or value.islower():
                value = value.title()
    elif f.kind == "date":
        d = _parse_date(value)
        if d is None:
            issues.append("Not a valid date")
        else:
            value = d.strftime("%m/%d/%Y")
            if d > date.today():
                issues.append("Date is in the future")
    elif f.kind == "phone":
        digits = re.sub(r"\D", "", value)
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        if len(digits) == 10:
            value = f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
        else:
            issues.append(f"Phone has {len(digits)} digits, expected 10")
    elif f.kind in ("int", "number"):
        x = _num(value)
        if x is None:
            issues.append("Not a number")
        else:
            value = _fmt_num(x)
            lo_hi = RANGES.get(f.key)
            if lo_hi and not (lo_hi[0] <= x <= lo_hi[1]):
                issues.append(f"Unusual value (expected {lo_hi[0]}-{lo_hi[1]}) - verify")
    elif f.kind == "choice":
        match = next((c for c in f.choices if c.lower() == value.strip().lower().lstrip("°")), None)
        if match:
            value = match
        else:
            issues.append(f"Expected one of: {', '.join(f.choices)}")
    return value, issues


def calc_bmi(height_ft, height_in, weight_lbs) -> float | None:
    ft, inch, lbs = _num(height_ft), _num(height_in) or 0, _num(weight_lbs)
    if not ft or not lbs:
        return None
    total_in = ft * 12 + inch
    return round(703 * lbs / (total_in ** 2), 1) if total_in > 0 else None


def _cross_checks(fields: dict) -> None:
    """Checks that need more than one field. Adds issues in place."""
    v = {k: f["value"] for k, f in fields.items()}

    sys_, dia = _num(v["bp_systolic"]), _num(v["bp_diastolic"])
    if sys_ and dia and sys_ <= dia:
        for k in ("bp_systolic", "bp_diastolic"):
            fields[k]["issues"].append("Systolic should be higher than diastolic - check order/digits")

    temp, unit = _num(v["temperature"]), v["temperature_unit"]
    if temp is not None:
        if unit is None:
            fields["temperature_unit"]["value"] = unit = "F" if temp > 50 else "C"
            fields["temperature_unit"]["note"] = "Unit not circled - inferred from value"
        lo, hi = TEMP_RANGES.get(unit, TEMP_RANGES["F"])
        if not (lo <= temp <= hi):
            fields["temperature"]["issues"].append(f"Unusual for °{unit} (expected {lo}-{hi}) - verify value/unit")

    bmi_calc = calc_bmi(v["height_ft"], v["height_in"], v["weight_lbs"])
    bmi_card = _num(v["bmi"])
    if bmi_calc and bmi_card and abs(bmi_calc - bmi_card) > 1.0:
        fields["bmi"]["issues"].append(
            f"Card says {_fmt_num(bmi_card)}, but {v['height_ft']}'{v['height_in'] or 0}\" / {v['weight_lbs']} lbs = {bmi_calc}"
        )
        fields["bmi"]["suggestion"] = str(bmi_calc)

    dob, visit = _parse_date(v["date_of_birth"] or ""), _parse_date(v["visit_date"] or "")
    if dob and (visit or date.today()).year - dob.year > 115:
        fields["date_of_birth"]["issues"].append("Age over 115 - check the year")


def clinical_alerts(values: dict) -> list[dict]:
    """Screening flags for staff. level: urgent | follow_up | info."""
    alerts = []

    def add(level, text):
        alerts.append({"level": level, "text": text})

    sys_, dia = _num(values.get("bp_systolic")), _num(values.get("bp_diastolic"))
    if sys_ and dia:
        bp = f"{_fmt_num(sys_)}/{_fmt_num(dia)}"
        if sys_ >= 180 or dia >= 120:
            add("urgent", f"BP {bp}: severely elevated (180/120+). Refer for immediate evaluation.")
        elif sys_ >= 140 or dia >= 90:
            add("follow_up", f"BP {bp}: high blood pressure range. Recommend doctor follow-up.")
        elif sys_ >= 130 or dia > 80:
            add("info", f"BP {bp}: above normal. Recheck at next visit.")
        elif sys_ < 90 or dia < 60:
            add("follow_up", f"BP {bp}: low blood pressure.")

    spo2 = _num(values.get("spo2"))
    if spo2 is not None:
        if spo2 < 90:
            add("urgent", f"SpO2 {_fmt_num(spo2)}%: low oxygen. Refer for immediate evaluation.")
        elif spo2 < 94:
            add("follow_up", f"SpO2 {_fmt_num(spo2)}%: below normal. Recommend follow-up.")

    hr = _num(values.get("heart_rate"))
    if hr is not None:
        if hr > 150 or hr < 40:
            add("urgent", f"Heart rate {_fmt_num(hr)} bpm: far outside normal range.")
        elif hr > 120 or hr < 50:
            add("follow_up", f"Heart rate {_fmt_num(hr)} bpm: outside normal range.")

    temp, unit = _num(values.get("temperature")), values.get("temperature_unit") or "F"
    if temp is not None:
        temp_f = temp * 9 / 5 + 32 if unit == "C" else temp
        if temp_f >= 103:
            add("urgent", f"Temperature {_fmt_num(temp)}°{unit}: high fever.")
        elif temp_f >= 100.4:
            add("follow_up", f"Temperature {_fmt_num(temp)}°{unit}: fever.")

    glucose = _num(values.get("blood_glucose"))
    if glucose is not None:
        if glucose >= 300 or glucose < 54:
            add("urgent", f"Blood glucose {_fmt_num(glucose)} mg/dL: dangerously {'high' if glucose >= 300 else 'low'}.")
        elif glucose >= 200:
            add("follow_up", f"Blood glucose {_fmt_num(glucose)} mg/dL: high. Recommend diabetes screening.")
        elif glucose < 70:
            add("follow_up", f"Blood glucose {_fmt_num(glucose)} mg/dL: low.")

    bmi = calc_bmi(values.get("height_ft"), values.get("height_in"), values.get("weight_lbs")) or _num(values.get("bmi"))
    if bmi:
        if bmi >= 40:
            add("follow_up", f"BMI {bmi}: severe obesity range. Recommend follow-up.")
        elif bmi >= 30:
            add("info", f"BMI {bmi}: obesity range. Offer nutrition/activity resources.")

    if (values.get("smoking") or "").lower() == "yes":
        add("info", "Smoker: offer cessation resources.")

    order = {"urgent": 0, "follow_up": 1, "info": 2}
    return sorted(alerts, key=lambda a: order[a["level"]])


def review(reading: dict) -> dict:
    """reading: output of reader.read_card. Returns fields + alerts for the review screen."""
    fields = {}
    for f in FIELDS:
        r = reading[f.key]
        value, issues = _normalize(f, r["value"])
        fields[f.key] = {
            "key": f.key, "label": f.label, "section": f.section, "kind": f.kind,
            "choices": list(f.choices), "required": f.required,
            "value": value, "read_as": r["value"], "confidence": r["confidence"],
            "alternatives": [a for a in r["alternatives"] if a != r["value"]],
            "note": r["note"], "agree": r.get("agree", True), "box": r.get("box_2d"),
            "issues": issues, "suggestion": None,
        }
    _cross_checks(fields)

    for fld in fields.values():
        if fld["value"] is None:
            fld["status"] = "missing" if FIELD_BY_KEY[fld["key"]].required else (
                "check" if fld["confidence"] == "low" else "empty")
        elif fld["issues"] or fld["confidence"] != "high" or not fld["agree"]:
            fld["status"] = "check"
        else:
            fld["status"] = "ok"

    values = {k: f["value"] for k, f in fields.items()}
    alerts = clinical_alerts(values)
    counts = {s: sum(1 for f in fields.values() if f["status"] == s) for s in ("ok", "check", "missing", "empty")}
    return {
        "fields": fields,
        "alerts": alerts,
        "counts": counts,
        "needs_follow_up": any(a["level"] in ("urgent", "follow_up") for a in alerts),
        "all_clear": counts["check"] == 0 and counts["missing"] == 0,
    }
