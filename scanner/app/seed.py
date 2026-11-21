"""Fictional demo data. All people, insurers and pharmacies are made up.

Appointments are created relative to *today*, so the schedule always looks like a
busy clinic day whenever the demo is reset.
"""
from datetime import date, datetime, timedelta

from . import billing, clinic
from . import payer as insurer

PROVIDERS = [
    ("Dr. Amina Rahman", "MD", "Family Medicine", "#3b82f6", "1000000011"),
    ("Dr. Daniel Ortiz", "DO", "Internal Medicine", "#10b981", "1000000029"),
    ("Sarah Kim", "FNP-C", "Nurse Practitioner", "#f59e0b", "1000000037"),
]

PAYERS = [
    ("Bluebonnet Health Plan", "commercial", "BBHP1"),
    ("Prairie Mutual Insurance", "commercial", "PMI02"),
    ("Gulf Coast Care PPO", "commercial", "GCC03"),
    ("Medicare (demo)", "government", "MCR00"),
    ("Self-pay", "self", "SELF"),
]

PHARMACIES = [
    ("Legacy Drive Pharmacy", "4100 Legacy Dr, Plano TX", "(972) 555-0140", "rx@legacydrive-pharmacy.example"),
    ("Main Street Rx", "1200 Main St, Plano TX", "(972) 555-0177", "orders@mainstreetrx.example"),
    ("Collin Community Pharmacy", "820 Coit Rd, Plano TX", "(469) 555-0123", "erx@collincommunity.example"),
]

# first, last, dob, sex, phone, payer#, member, pharmacy#, allergies, conditions, medications
PATIENTS = [
    ("Maria", "Gonzalez", "1968-03-14", "F", "214-555-0101", 1, "BB4471902", 1, "Penicillin", "Hypertension", "Lisinopril 10 mg daily"),
    ("James", "Carter", "1955-11-02", "M", "972-555-0102", 4, "1EG4-TE5-MK72", 2, "", "Type 2 diabetes; Hyperlipidemia", "Metformin 500 mg BID; Atorvastatin 20 mg"),
    ("Aisha", "Khan", "1990-07-21", "F", "469-555-0103", 2, "PM88213307", 1, "Sulfa drugs", "Asthma", "Albuterol inhaler PRN"),
    ("Robert", "Nguyen", "1979-01-09", "M", "214-555-0104", 3, "GC5521890", 3, "", "", ""),
    ("Linda", "Patel", "1962-09-30", "F", "972-555-0105", 1, "BB9930011", 2, "Codeine", "Hypothyroidism", "Levothyroxine 75 mcg"),
    ("Omar", "Haddad", "1985-05-17", "M", "469-555-0106", 2, "PM10293847", 1, "", "Obesity", ""),
    ("Emily", "Brooks", "2001-12-05", "F", "214-555-0107", 5, "", 3, "Latex", "", ""),
    ("David", "Kim", "1971-04-26", "M", "972-555-0108", 3, "GC7781234", 2, "", "GERD", "Omeprazole 20 mg"),
    ("Fatima", "Ali", "1958-08-11", "F", "469-555-0109", 4, "2FH7-RT3-QX91", 1, "Aspirin", "Hypertension; Osteoarthritis", "Amlodipine 5 mg"),
    ("Michael", "Johnson", "1994-02-28", "M", "214-555-0110", 1, "BB2200981", 3, "", "", ""),
]

STREETS = ["2100 Willow Bend Dr", "415 Parker Rd", "3308 Spring Creek Pkwy", "77 Legacy Ct", "1902 Alma Dr",
           "640 Park Blvd", "2511 Independence Pkwy", "118 Custer Rd", "905 Jupiter Rd", "1430 Coit Rd"]

# patient#, provider#, "HH:MM", minutes, reason, visit_type, status
TODAY = [
    (1, 1, "08:30", 30, "Blood pressure follow-up", "follow_up", "completed"),
    (3, 3, "09:00", 30, "Asthma check", "follow_up", "checked_in"),
    (2, 2, "09:00", 45, "Diabetes management", "follow_up", "booked"),
    (6, 1, "09:30", 30, "Weight management consult", "new", "booked"),
    (8, 2, "10:00", 30, "Heartburn, medication review", "follow_up", "booked"),
    (5, 3, "10:30", 30, "Thyroid lab review", "follow_up", "booked"),
    (9, 1, "11:00", 30, "Joint pain, BP check", "follow_up", "booked"),
    (4, 2, "13:00", 60, "Annual physical", "new", "booked"),
    (10, 3, "14:00", 30, "Sore throat", "sick", "booked"),
    (7, 1, "15:00", 30, "New patient visit", "new", "booked"),
]
TOMORROW = [
    (1, 2, "09:00", 30, "Lab follow-up", "follow_up"),
    (4, 1, "10:30", 30, "Follow-up", "follow_up"),
    (3, 3, "14:00", 30, "Inhaler refill", "follow_up"),
]

# Past visits so charts have history: patient#, provider#, days ago, vitals, note
PAST_VISITS = [
    (1, 1, 92, {"bp_systolic": "152", "bp_diastolic": "94", "heart_rate": "78", "weight_lbs": "168", "spo2": "98"},
     "BP elevated at 152/94. Started lisinopril 10 mg daily. Low-sodium diet counseling. Recheck in 3 months."),
    (2, 2, 60, {"bp_systolic": "134", "bp_diastolic": "82", "heart_rate": "72", "weight_lbs": "201", "blood_glucose": "168"},
     "Type 2 diabetes, A1c 7.8. Continue metformin 500 mg BID, discussed diet and exercise. Statin continued."),
    (9, 1, 45, {"bp_systolic": "146", "bp_diastolic": "88", "heart_rate": "80", "weight_lbs": "155", "spo2": "97"},
     "Hypertension not at goal. Increased amlodipine to 5 mg. Knee osteoarthritis, acetaminophen as needed."),
    (3, 3, 20, {"bp_systolic": "122", "bp_diastolic": "78", "heart_rate": "104", "respiratory_rate": "24", "spo2": "93"},
     "Acute asthma exacerbation for 2 days after a cold: wheezing, chest tightness, using albuterol every 3 hours. "
     "Exam: diffuse expiratory wheezes, SpO2 93%. Nebulizer treatment given in clinic with improvement. "
     "Spirometry performed during the exacerbation: FEV1 62% of predicted. Assessment: asthma with acute exacerbation. "
     "Plan: prednisone 40 mg daily for 5 days, continue albuterol, recheck in 1 week."),
    (8, 2, 35, {"bp_systolic": "126", "bp_diastolic": "82", "heart_rate": "74", "blood_glucose": "102"},
     "Heartburn after meals for 3 weeks, worse lying down. No weight loss, no trouble swallowing. Fingerstick glucose 102 "
     "(patient asked about diabetes risk). Assessment: GERD without esophagitis. Plan: omeprazole 20 mg daily before "
     "breakfast, avoid late meals, follow up in 6 weeks."),
]
# Billing history for those visits: status, diagnoses, [(procedure, linked diagnoses)].
# "adjudicate" = sent through the mock insurer at seed time (Aisha: spirometry denied for no prior auth, but the
# note documents an acute exacerbation, so the appeal is winnable; David: fingerstick glucose bundled = write off).
PAST_CLAIMS = [
    ("adjudicate", ["I10"], [("99204", ["I10"])]),
    ("adjudicate", ["E11.9", "E78.5"], [("99204", ["E11.9", "E78.5"]), ("83036", ["E11.9"])]),
    ("submitted", ["I10", "M17.9"], [("99204", ["I10", "M17.9"])]),
    ("adjudicate", ["J45.901"], [("99204", ["J45.901"]), ("94640", ["J45.901"]), ("94010", ["J45.901"])]),
    ("adjudicate", ["K21.9", "Z13.1"], [("99203", ["K21.9"]), ("82962", ["Z13.1"])]),
]
PAST_REJECTED = {2: ["Z79.899"]}  # patient# -> AI-suggested diagnoses staff rejected
PAST_RX = [  # patient#, provider#, pharmacy#, drug, strength, sig, qty, refills, days ago
    (1, 1, 1, "Lisinopril", "10 mg tablet", "Take 1 tablet by mouth once daily", 90, 3, 92),
    (2, 2, 2, "Metformin", "500 mg tablet", "Take 1 tablet by mouth twice daily with meals", 180, 3, 60),
    (9, 1, 1, "Amlodipine", "5 mg tablet", "Take 1 tablet by mouth once daily", 90, 3, 45),
]


def seed() -> None:
    billing.init()
    billing.reset()
    clinic.reset()
    con = clinic._conn()
    with con:
        con.executemany("INSERT INTO providers (name, credentials, specialty, color, npi) VALUES (?,?,?,?,?)", PROVIDERS)
        con.executemany("INSERT INTO payers (name, kind, payer_code) VALUES (?,?,?)", PAYERS)
        con.executemany("INSERT INTO pharmacies (name, address, phone, email) VALUES (?,?,?,?)", PHARMACIES)
    con.close()
    from . import epcs
    epcs.init()  # gives the re-created providers their (fictional) DEA numbers

    ids = []
    for first, last, dob, sex, phone, payer, member, pharm, allergies, conds, meds in PATIENTS:
        ids.append(clinic.create_patient({
            "first_name": first, "last_name": last, "dob": dob, "sex": sex, "phone": phone,
            "email": f"{first.lower()}.{last.lower()}@example.com", "address": STREETS[len(ids) % len(STREETS)],
            "city": "Plano", "state": "TX", "zip": "75074",
            "payer_id": payer, "member_id": member or None, "group_number": "GRP-1001" if payer <= 3 else None,
            "pharmacy_id": pharm, "allergies": allergies, "conditions": conds, "medications": meds,
        }))

    today = date.today()
    for p, prov, hhmm, mins, reason, vtype, status in TODAY:
        appt = clinic.create_appointment({
            "patient_id": ids[p - 1], "provider_id": prov, "start": f"{today.isoformat()}T{hhmm}:00",
            "duration_min": mins, "reason": reason, "visit_type": vtype,
        })
        if status != "booked":
            clinic.update_appointment(appt, {"status": status})
    for p, prov, hhmm, mins, reason, vtype in TOMORROW:
        clinic.create_appointment({
            "patient_id": ids[p - 1], "provider_id": prov,
            "start": f"{(today + timedelta(days=1)).isoformat()}T{hhmm}:00",
            "duration_min": mins, "reason": reason, "visit_type": vtype,
        })

    for (p, prov, days, vitals, note), (status, dxs, procs) in zip(PAST_VISITS, PAST_CLAIMS):
        enc = clinic.create_encounter({
            "patient_id": ids[p - 1], "provider_id": prov, "date": (today - timedelta(days=days)).isoformat(),
            "type": "office visit", "vitals": vitals, "note": note, "status": "signed",
        })
        claim = billing.create_for_encounter(enc)
        # history as if coded by the AI and approved by staff (one suggestion was rejected, see PAST_REJECTED)
        lines = [billing.make_line("cpt", c, source="ai", status="accepted", dx=dx) for c, dx in procs]
        diagnoses = [billing.make_line("dx", d, source="ai", status="accepted") for d in dxs]
        diagnoses += [billing.make_line("dx", d, source="ai", status="rejected", confidence="low",
                                        reason="Staff rejected: not addressed in this visit")
                      for d in PAST_REJECTED.get(p, [])]
        billing.update(claim, diagnoses=diagnoses, procedures=lines,
                       status="submitted" if status == "submitted" else "ready", ai_status="done",
                       submitted_at=(datetime.now() - timedelta(days=days - 1)).isoformat(timespec="seconds"))
        if status == "adjudicate":
            rem = insurer.adjudicate(billing.detail(claim))
            rem["processed"] = (today - timedelta(days=max(days - 14, 1))).isoformat()
            open_denials = [l for l in rem["lines"] if l["status"] == "denied"]
            billing.update(claim, remittance=rem, paid_amount=rem["total_paid"],
                           status=("partial" if rem["total_paid"] else "denied") if open_denials else "paid")
    # The fictional patients registered months ago (so the dashboard's "new today" starts at 0)
    with clinic._conn() as con:
        con.execute("UPDATE patients SET created_at = datetime('now', '-200 days')")

    # A health-fair screening from yesterday that flagged high blood pressure (shows on the dashboard).
    from .validate import clinical_alerts
    fair_vitals = {"bp_systolic": "168", "bp_diastolic": "104", "heart_rate": "88", "spo2": "97", "blood_glucose": "132"}
    alerts = clinical_alerts(fair_vitals)
    clinic.create_encounter({
        "patient_id": ids[3], "date": (today - timedelta(days=1)).isoformat(), "type": "screening",
        "vitals": fair_vitals, "status": "signed", "alerts": alerts,
        "note": "Health fair screening (card collected by volunteer).\n" + "\n".join(
            f"Screening flag ({a['level'].replace('_', '-')}): {a['text']}" for a in alerts),
    })

    for p, prov, pharm, drug, strength, sig, qty, refills, days in PAST_RX:
        rx = clinic.create_prescription({
            "patient_id": ids[p - 1], "provider_id": prov, "pharmacy_id": pharm,
            "drug": drug, "strength": strength, "sig": sig, "quantity": qty, "refills": refills,
        })
        sent = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
        with clinic._conn() as c:
            c.execute("UPDATE prescriptions SET status = 'filled', sent_at = ?, updated_at = ? WHERE id = ?", (sent, sent, rx))

    from . import eligibility, portal  # Track B: clears + seeds its tables (no stale rows after "Reset demo data")
    portal.seed(ids)
    eligibility.seed()  # overnight insurance check for today + tomorrow
