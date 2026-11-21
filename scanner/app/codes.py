"""Approved billing code list for the demo clinic (primary care).

The AI may only suggest codes from these lists, so it can't invent codes.
Descriptions are our own short wording (official CPT descriptors are AMA-copyrighted).
Charges are the clinic's demo fee schedule.
"""

# ICD-10-CM diagnosis codes: code -> description
ICD10 = {
    # cardiovascular / metabolic
    "I10": "Essential (primary) hypertension",
    "R03.0": "Elevated blood pressure reading, no hypertension diagnosis",
    "I25.10": "Coronary artery disease, no angina",
    "E11.9": "Type 2 diabetes without complications",
    "E11.65": "Type 2 diabetes with hyperglycemia",
    "R73.03": "Prediabetes",
    "R73.9": "Hyperglycemia, unspecified",
    "E78.5": "Hyperlipidemia, unspecified",
    "E78.00": "Pure hypercholesterolemia",
    "E03.9": "Hypothyroidism, unspecified",
    "E66.9": "Obesity, unspecified",
    "E66.01": "Severe obesity due to excess calories",
    "E66.3": "Overweight",
    "Z68.25": "BMI 25.0-25.9, adult", "Z68.27": "BMI 27.0-27.9, adult", "Z68.29": "BMI 29.0-29.9, adult",
    "Z68.30": "BMI 30.0-30.9, adult", "Z68.31": "BMI 31.0-31.9, adult", "Z68.32": "BMI 32.0-32.9, adult",
    "Z68.33": "BMI 33.0-33.9, adult", "Z68.34": "BMI 34.0-34.9, adult", "Z68.35": "BMI 35.0-35.9, adult",
    "Z68.36": "BMI 36.0-36.9, adult", "Z68.37": "BMI 37.0-37.9, adult", "Z68.38": "BMI 38.0-38.9, adult",
    "Z68.39": "BMI 39.0-39.9, adult", "Z68.41": "BMI 40.0-44.9, adult",
    # respiratory / infections
    "J45.909": "Asthma, unspecified, uncomplicated",
    "J45.901": "Asthma, unspecified, with acute exacerbation",
    "J02.9": "Acute pharyngitis (sore throat), unspecified",
    "J02.0": "Strep throat",
    "J06.9": "Acute upper respiratory infection",
    "R05.9": "Cough, unspecified",
    "R06.2": "Wheezing",
    "R09.02": "Low blood oxygen (hypoxemia)",
    "R50.9": "Fever, unspecified",
    "N39.0": "Urinary tract infection",
    # GI / musculoskeletal / other
    "K21.9": "GERD (acid reflux) without esophagitis",
    "M17.9": "Osteoarthritis of knee, unspecified",
    "M25.561": "Pain in right knee", "M25.562": "Pain in left knee",
    "M54.50": "Low back pain, unspecified",
    "R51.9": "Headache, unspecified",
    "F41.1": "Generalized anxiety disorder",
    "F32.A": "Depression, unspecified",
    "G47.00": "Insomnia, unspecified",
    # tobacco
    "F17.210": "Nicotine dependence, cigarettes, uncomplicated",
    "Z72.0": "Tobacco use",
    # preventive / screening / counseling
    "Z00.00": "Adult general exam, no abnormal findings",
    "Z00.01": "Adult general exam, with abnormal findings",
    "Z13.1": "Screening for diabetes",
    "Z13.6": "Screening for cardiovascular disorders",
    "Z71.3": "Dietary counseling",
    "Z71.6": "Tobacco cessation counseling",
    "Z23": "Encounter for immunization",
    "Z79.899": "Long-term (current) use of other medications",
}

# CPT / HCPCS procedure codes: code -> (description, charge in USD)
CPT = {
    "99202": ("Office visit, new patient, straightforward", 110),
    "99203": ("Office visit, new patient, low complexity", 170),
    "99204": ("Office visit, new patient, moderate complexity", 250),
    "99205": ("Office visit, new patient, high complexity", 330),
    "99212": ("Office visit, established patient, straightforward", 90),
    "99213": ("Office visit, established patient, low complexity", 140),
    "99214": ("Office visit, established patient, moderate complexity", 200),
    "99215": ("Office visit, established patient, high complexity", 280),
    "99385": ("Preventive exam, new patient, age 18-39", 250),
    "99386": ("Preventive exam, new patient, age 40-64", 270),
    "99387": ("Preventive exam, new patient, age 65+", 290),
    "99395": ("Preventive exam, established patient, age 18-39", 220),
    "99396": ("Preventive exam, established patient, age 40-64", 240),
    "99397": ("Preventive exam, established patient, age 65+", 260),
    "99406": ("Tobacco cessation counseling, 3-10 minutes", 30),
    "99407": ("Tobacco cessation counseling, over 10 minutes", 55),
    "99401": ("Preventive counseling, about 15 minutes", 55),
    "G0447": ("Behavioral counseling for obesity, 15 minutes", 35),
    "96127": ("Brief emotional/behavioral screening (e.g. PHQ-9)", 15),
    "83036": ("Hemoglobin A1c test", 35),
    "82947": ("Blood glucose test, quantitative", 15),
    "82962": ("Blood glucose by home-type monitor (fingerstick)", 12),
    "80061": ("Lipid panel", 45),
    "80053": ("Comprehensive metabolic panel (CMP)", 50),
    "85025": ("Complete blood count (CBC) with differential", 25),
    "84443": ("Thyroid stimulating hormone (TSH) test", 40),
    "81002": ("Urinalysis, dipstick, non-automated", 10),
    "87880": ("Rapid strep test", 30),
    "93000": ("Electrocardiogram (ECG) with interpretation", 60),
    "94640": ("Nebulizer breathing treatment", 40),
    "94010": ("Spirometry (lung function test)", 70),
    "90471": ("Vaccine administration, first injection", 25),
    "90686": ("Flu vaccine, preservative-free, 0.5 mL", 40),
}

EM_NEW = ["99202", "99203", "99204", "99205"]
EM_EST = ["99212", "99213", "99214", "99215"]
PREVENTIVE_NEW = ["99385", "99386", "99387"]
PREVENTIVE_EST = ["99395", "99396", "99397"]
EM_CODES = set(EM_NEW + EM_EST)
PREVENTIVE = set(PREVENTIVE_NEW + PREVENTIVE_EST)

# Which diagnoses justify a procedure ("medical necessity"). Prefix match on the ICD-10 code.
# A procedure not listed here can be supported by any diagnosis.
SUPPORTED_BY = {
    "99406": ["F17.", "Z72.0"], "99407": ["F17.", "Z72.0"],
    "G0447": ["E66.", "Z68.3", "Z68.4"],
    "83036": ["E11.", "R73.", "Z13.1"],
    "82947": ["E11.", "R73.", "Z13.1"], "82962": ["E11.", "R73.", "Z13.1"],
    "80061": ["E78.", "Z13.6", "I10", "E11.", "I25."],
    "84443": ["E03.", "R53.", "Z00."],
    "87880": ["J02."],
    "94640": ["J45.", "R06.2", "R09.02", "R05"],
    "94010": ["J45.", "R06.2", "R05"],
    "93000": ["I10", "I25.", "R07.", "Z00.", "R00."],
    "90686": ["Z23"], "90471": ["Z23"],
    "96127": ["F41.", "F32.", "Z00.", "Z13."],
    "99385": ["Z00."], "99386": ["Z00."], "99387": ["Z00."],
    "99395": ["Z00."], "99396": ["Z00."], "99397": ["Z00."],
}

# Diagnosis pairs that shouldn't be coded together (ICD-10 "Excludes1"-style conflicts).
CONFLICTS = [
    ("R03.0", "I10", "An elevated BP reading (R03.0) can't be coded together with diagnosed hypertension (I10)"),
    ("Z72.0", "F17.210", "Use either tobacco use (Z72.0) or nicotine dependence (F17.210), not both"),
    ("E11.9", "E11.65", "Type 2 diabetes can't be both 'without complications' (E11.9) and 'with hyperglycemia' (E11.65)"),
    ("R73.03", "E11.", "Prediabetes can't be coded with type 2 diabetes"),
    ("J45.909", "J45.901", "Asthma can't be both uncomplicated and in exacerbation"),
    ("Z00.00", "Z00.01", "An exam is either with or without abnormal findings, not both"),
    ("E66.9", "E66.01", "Pick one obesity code"),
    ("J02.9", "J02.0", "Strep throat (J02.0) is more specific than sore throat (J02.9); use one"),
]


def describe(code: str) -> str:
    if code in ICD10:
        return ICD10[code]
    if code in CPT:
        return CPT[code][0]
    return ""


def charge(code: str) -> float:
    return float(CPT[code][1]) if code in CPT else 0.0


def search(q: str, limit: int = 12) -> list[dict]:
    q = q.strip().lower()
    out = [{"kind": "dx", "code": c, "description": d} for c, d in ICD10.items()]
    out += [{"kind": "cpt", "code": c, "description": d, "charge": p} for c, (d, p) in CPT.items()]
    if q:
        out = [x for x in out if q in x["code"].lower() or q in x["description"].lower()]
    return out[:limit]


def bmi_code(bmi: float) -> str | None:
    """Adult BMI Z-code for a BMI value, if one is in our list."""
    if bmi >= 40:
        return "Z68.41" if bmi < 45 else None
    code = f"Z68.{int(bmi)}"
    return code if code in ICD10 else None
