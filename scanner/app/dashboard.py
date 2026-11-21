"""Dashboard numbers: today's clinic day, billing money, AI activity, follow-ups.

Time-saved figures are estimates from stated assumptions (shown on the page), not measurements.
"""
import json
from datetime import date, datetime, timedelta

from fastapi import APIRouter

from . import billing, clinic

router = APIRouter(prefix="/api")

# Manual-work assumptions behind "staff time saved" (minutes per item). Shown on the dashboard.
MINUTES_SAVED = {
    "card": 2.5,     # typing one 25-field intake card by hand
    "coding": 7.0,   # a coder reading a note and picking ICD-10/CPT codes
    "appeal": 30.0,  # researching a denial and writing an appeal letter
    "summary": 5.0,  # writing a patient-friendly after-visit summary
}


def summary() -> dict:
    today = date.today().isoformat()
    appts = clinic.list_appointments(today)
    count = lambda s: sum(a["status"] == s for a in appts)
    now = datetime.now().isoformat(timespec="seconds")
    upcoming = [a for a in appts if a["status"] in ("booked", "checked_in", "in_visit")]
    upcoming.sort(key=lambda a: ({"in_visit": 0, "checked_in": 1}.get(a["status"], 2), a["start"]))

    with clinic._conn() as con:
        patients_total = con.execute("SELECT count(*) FROM patients").fetchone()[0]
        new_today = con.execute("SELECT count(*) FROM patients WHERE date(created_at) = ?", (today,)).fetchone()[0]
        scans_total = con.execute("SELECT count(*) FROM encounters WHERE type = 'screening' AND source_image IS NOT NULL").fetchone()[0]
        scans_today = con.execute("SELECT count(*) FROM encounters WHERE type = 'screening' AND source_image IS NOT NULL AND date(created_at) = ?",
                                  (today,)).fetchone()[0]
        rx_today = con.execute("SELECT count(*), coalesce(sum(emailed), 0) FROM prescriptions WHERE date(sent_at) = ?", (today,)).fetchone()
        rx_waiting = con.execute("SELECT count(*) FROM prescriptions WHERE status IN ('sent', 'received')").fetchone()[0]
        since = (date.today() - timedelta(days=30)).isoformat()
        flagged = con.execute(
            """SELECT e.id, e.date, e.alerts, p.id AS patient_id, p.first_name, p.last_name,
                      (SELECT min(start) FROM appointments a WHERE a.patient_id = p.id AND a.start >= ? AND a.status IN ('booked','checked_in')) AS next_appt
               FROM encounters e JOIN patients p ON p.id = e.patient_id
               WHERE e.type = 'screening' AND e.date >= ? AND e.alerts IS NOT NULL ORDER BY e.date DESC""",
            (today, since),
        ).fetchall()

    follow_ups = []
    for r in flagged:
        serious = [a for a in json.loads(r["alerts"] or "[]") if a["level"] in ("urgent", "follow_up")]
        if serious:
            follow_ups.append({"patient_id": r["patient_id"], "name": f"{r['first_name']} {r['last_name']}", "date": r["date"],
                               "level": "urgent" if any(a["level"] == "urgent" for a in serious) else "follow_up",
                               "text": serious[0]["text"], "next_appt": r["next_appt"]})

    claims = billing.list_claims()
    by = lambda *s: [c for c in claims if c["status"] in s]
    open_denied = 0.0
    recovered = written_off = 0.0
    ai_suggested = ai_accepted = ai_decided = appeals_drafted = appeals_won = 0
    coded_by_ai = 0
    for c in claims:
        rem = c.get("remittance")
        if rem:
            open_denied += sum(l["charge"] for l in rem["lines"] if l["status"] == "denied" and not l.get("written_off"))
            written_off += sum(l["charge"] for l in rem["lines"] if l.get("written_off"))
        ai_lines = [x for x in c["diagnoses"] + c["procedures"] if x.get("source") == "ai"]
        if ai_lines:
            coded_by_ai += 1
        ai_suggested += len(ai_lines)
        ai_accepted += sum(x["status"] == "accepted" for x in ai_lines)
        ai_decided += sum(x["status"] in ("accepted", "rejected") for x in ai_lines)
        if c.get("appeal"):
            appeals_drafted += 1
            if c["appeal"].get("status") == "approved":
                appeals_won += 1
                recovered += c["appeal"].get("recovered") or 0
    with clinic._conn() as con:
        summaries = con.execute("SELECT count(*) FROM encounters WHERE summary_ai = 1 AND summary IS NOT NULL").fetchone()[0]
    minutes = (scans_total * MINUTES_SAVED["card"] + coded_by_ai * MINUTES_SAVED["coding"]
               + appeals_drafted * MINUTES_SAVED["appeal"] + summaries * MINUTES_SAVED["summary"])

    action_items = [{"claim_id": c["id"], "name": f"{c['first_name']} {c['last_name']}", "status": c["status"],
                     "amount": c["total_charge"], "errors": c["issues"]["error"]}
                    for c in by("review", "ready", "denied", "partial")]
    return {
        "date": today,
        "now": now,
        "appointments": {"total": len([a for a in appts if a["status"] not in ("cancelled", "no_show")]),
                         "booked": count("booked"), "waiting": count("checked_in"), "in_visit": count("in_visit"),
                         "done": count("completed"), "no_show": count("no_show") + count("cancelled")},
        "upcoming": [{"id": a["id"], "start": a["start"], "name": f"{a['first_name']} {a['last_name']}", "reason": a["reason"],
                      "provider": a["provider_name"], "color": a["provider_color"], "status": a["status"],
                      "encounter_id": a["encounter_id"]} for a in upcoming[:7]],
        "patients": {"total": patients_total, "new_today": new_today, "scanned_today": scans_today},
        "prescriptions": {"sent_today": rx_today[0], "emailed_today": rx_today[1], "at_pharmacy": rx_waiting},
        "billing": {
            "needs_review": len(by("review")), "ready": len(by("ready")), "with_insurer": len(by("submitted", "appealed")),
            "denials_open": len(by("denied", "partial")), "denied_amount": round(open_denied, 2),
            "collected": round(sum(c.get("paid_amount") or 0 for c in claims), 2),
            "recovered": round(recovered, 2), "written_off": round(written_off, 2),
        },
        "ai": {"cards_read": scans_total, "visits_coded": coded_by_ai, "codes_suggested": ai_suggested,
               "acceptance_rate": round(100 * ai_accepted / ai_decided) if ai_decided else None,
               "appeals_drafted": appeals_drafted, "appeals_won": appeals_won, "summaries_sent": summaries},
        "time_saved_minutes": round(minutes),
        "assumptions": MINUTES_SAVED,
        "follow_ups": follow_ups,
        "action_items": action_items,
    }


@router.get("/dashboard")
def dashboard():
    return summary()
