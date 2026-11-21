"""Common primary-care medications for the prescribing screen (demo formulary).

allergy_terms: words in a patient's allergy list that should block or warn on this drug.
"""

# name, strengths, default sig, default quantity, drug class, allergy terms
DRUGS = [
    ("Lisinopril", ["5 mg tablet", "10 mg tablet", "20 mg tablet"], "Take 1 tablet by mouth once daily", 90, "ACE inhibitor", ["lisinopril", "ace inhibitor"]),
    ("Losartan", ["25 mg tablet", "50 mg tablet", "100 mg tablet"], "Take 1 tablet by mouth once daily", 90, "ARB", ["losartan"]),
    ("Amlodipine", ["2.5 mg tablet", "5 mg tablet", "10 mg tablet"], "Take 1 tablet by mouth once daily", 90, "Calcium channel blocker", ["amlodipine"]),
    ("Hydrochlorothiazide", ["12.5 mg capsule", "25 mg tablet"], "Take 1 tablet by mouth once daily in the morning", 90, "Thiazide diuretic", ["sulfa", "hydrochlorothiazide"]),
    ("Metoprolol succinate ER", ["25 mg tablet", "50 mg tablet"], "Take 1 tablet by mouth once daily", 90, "Beta blocker", ["metoprolol"]),
    ("Atorvastatin", ["10 mg tablet", "20 mg tablet", "40 mg tablet"], "Take 1 tablet by mouth once daily at bedtime", 90, "Statin", ["atorvastatin", "statin"]),
    ("Rosuvastatin", ["5 mg tablet", "10 mg tablet"], "Take 1 tablet by mouth once daily", 90, "Statin", ["rosuvastatin", "statin"]),
    ("Metformin", ["500 mg tablet", "850 mg tablet", "1000 mg tablet"], "Take 1 tablet by mouth twice daily with meals", 180, "Biguanide", ["metformin"]),
    ("Glipizide", ["5 mg tablet", "10 mg tablet"], "Take 1 tablet by mouth once daily before breakfast", 90, "Sulfonylurea", ["glipizide", "sulfa"]),
    ("Levothyroxine", ["25 mcg tablet", "50 mcg tablet", "75 mcg tablet", "100 mcg tablet"], "Take 1 tablet by mouth once daily on an empty stomach", 90, "Thyroid hormone", ["levothyroxine"]),
    ("Omeprazole", ["20 mg capsule", "40 mg capsule"], "Take 1 capsule by mouth once daily before breakfast", 30, "Proton pump inhibitor", ["omeprazole"]),
    ("Albuterol HFA inhaler", ["90 mcg/actuation"], "Inhale 2 puffs every 4-6 hours as needed for wheezing", 1, "Bronchodilator", ["albuterol"]),
    ("Fluticasone nasal spray", ["50 mcg/spray"], "1 spray in each nostril once daily", 1, "Nasal steroid", ["fluticasone"]),
    ("Montelukast", ["10 mg tablet"], "Take 1 tablet by mouth once daily in the evening", 30, "Leukotriene blocker", ["montelukast"]),
    ("Cetirizine", ["10 mg tablet"], "Take 1 tablet by mouth once daily", 30, "Antihistamine", ["cetirizine"]),
    ("Amoxicillin", ["500 mg capsule", "875 mg tablet"], "Take 1 by mouth twice daily for 10 days", 20, "Penicillin antibiotic", ["penicillin", "amoxicillin"]),
    ("Azithromycin", ["250 mg tablet (Z-pak)"], "Take 2 tablets on day 1, then 1 tablet daily for 4 days", 6, "Macrolide antibiotic", ["azithromycin", "macrolide"]),
    ("Cephalexin", ["500 mg capsule"], "Take 1 capsule by mouth four times daily for 7 days", 28, "Cephalosporin antibiotic", ["cephalexin", "cephalosporin"]),
    ("Sulfamethoxazole-trimethoprim DS", ["800-160 mg tablet"], "Take 1 tablet by mouth twice daily for 7 days", 14, "Sulfonamide antibiotic", ["sulfa", "bactrim"]),
    ("Ibuprofen", ["400 mg tablet", "600 mg tablet"], "Take 1 tablet by mouth every 6-8 hours as needed with food", 30, "NSAID", ["ibuprofen", "nsaid", "aspirin"]),
    ("Naproxen", ["250 mg tablet", "500 mg tablet"], "Take 1 tablet by mouth twice daily as needed with food", 30, "NSAID", ["naproxen", "nsaid", "aspirin"]),
    ("Acetaminophen", ["500 mg tablet"], "Take 1-2 tablets by mouth every 6 hours as needed (max 3 g/day)", 60, "Analgesic", ["acetaminophen"]),
    ("Sertraline", ["25 mg tablet", "50 mg tablet", "100 mg tablet"], "Take 1 tablet by mouth once daily", 30, "SSRI", ["sertraline"]),
    ("Escitalopram", ["5 mg tablet", "10 mg tablet"], "Take 1 tablet by mouth once daily", 30, "SSRI", ["escitalopram"]),
    ("Gabapentin", ["100 mg capsule", "300 mg capsule"], "Take 1 capsule by mouth three times daily", 90, "Anticonvulsant", ["gabapentin"]),
    ("Prednisone", ["10 mg tablet", "20 mg tablet"], "Take as directed, tapering over 5 days", 10, "Corticosteroid", ["prednisone"]),
    ("Nicotine patch", ["21 mg/24 hr", "14 mg/24 hr", "7 mg/24 hr"], "Apply 1 patch to skin once daily; rotate sites", 28, "Smoking cessation", ["nicotine"]),
    ("Varenicline", ["0.5 mg tablet", "1 mg tablet"], "Take as directed (starter pack, then 1 mg twice daily)", 56, "Smoking cessation", ["varenicline"]),
    ("Vitamin D3", ["1000 IU tablet", "2000 IU tablet"], "Take 1 tablet by mouth once daily", 90, "Supplement", []),
    ("Ondansetron", ["4 mg ODT"], "Dissolve 1 tablet on tongue every 8 hours as needed for nausea", 12, "Antiemetic", ["ondansetron"]),
]

# Controlled substances (DEA schedules). Prescribed only through EPCS signing (2FA + PDMP check), see epcs.py.
# name, strengths, default sig, default quantity, class, allergy terms, schedule, default days' supply
CONTROLLED = [
    ("Tramadol", ["50 mg tablet"], "Take 1 tablet by mouth every 6 hours as needed for pain", 20, "Opioid analgesic",
     ["tramadol", "opioid"], "C-IV", 5),
    ("Hydrocodone-acetaminophen", ["5-325 mg tablet", "10-325 mg tablet"], "Take 1 tablet by mouth every 6 hours as needed for severe pain",
     12, "Opioid analgesic", ["hydrocodone", "opioid", "codeine"], "C-II", 3),
    ("Oxycodone", ["5 mg tablet"], "Take 1 tablet by mouth every 6 hours as needed for severe pain", 12, "Opioid analgesic",
     ["oxycodone", "opioid", "codeine"], "C-II", 3),
    ("Alprazolam", ["0.25 mg tablet", "0.5 mg tablet"], "Take 1 tablet by mouth up to twice daily as needed for anxiety", 30,
     "Benzodiazepine", ["alprazolam", "benzodiazepine"], "C-IV", 30),
    ("Lorazepam", ["0.5 mg tablet", "1 mg tablet"], "Take 1 tablet by mouth up to twice daily as needed for anxiety", 30,
     "Benzodiazepine", ["lorazepam", "benzodiazepine"], "C-IV", 30),
    ("Zolpidem", ["5 mg tablet", "10 mg tablet"], "Take 1 tablet by mouth at bedtime as needed for sleep", 30,
     "Sedative-hypnotic", ["zolpidem"], "C-IV", 30),
    ("Amphetamine-dextroamphetamine", ["10 mg tablet", "20 mg tablet"], "Take 1 tablet by mouth every morning", 30,
     "Stimulant (ADHD)", ["amphetamine"], "C-II", 30),
    ("Methylphenidate ER", ["18 mg tablet", "36 mg tablet"], "Take 1 tablet by mouth every morning", 30,
     "Stimulant (ADHD)", ["methylphenidate"], "C-II", 30),
    ("Pregabalin", ["75 mg capsule", "150 mg capsule"], "Take 1 capsule by mouth twice daily", 60,
     "Anticonvulsant (nerve pain)", ["pregabalin"], "C-V", 30),
]
DRUGS += [c[:6] for c in CONTROLLED]
SCHEDULE = {c[0]: c[6] for c in CONTROLLED}
DEFAULT_DAYS = {c[0]: c[7] for c in CONTROLLED}
OPIOIDS = {c[0] for c in CONTROLLED if c[4] == "Opioid analgesic"}
BENZOS = {c[0] for c in CONTROLLED if c[4] == "Benzodiazepine"}

DRUG_BY_NAME = {d[0]: d for d in DRUGS}


def formulary() -> list[dict]:
    return [{"name": n, "strengths": s, "sig": sig, "quantity": q, "drug_class": c,
             "schedule": SCHEDULE.get(n), "days": DEFAULT_DAYS.get(n)} for n, s, sig, q, c, _ in DRUGS]


def allergy_conflicts(drug_name: str, allergies: str | None) -> list[str]:
    """Allergy words from the patient's list that match this drug or its class."""
    drug = DRUG_BY_NAME.get(drug_name)
    if not drug or not allergies:
        return []
    terms = drug[5]
    listed = [a.strip() for a in allergies.replace(",", ";").split(";") if a.strip()]
    return [a for a in listed if any(t in a.lower() or a.lower() in t for t in terms)]
