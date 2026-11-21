"""Single source of truth for the Patient Health Record card fields.

The AI output schema, validation rules, review form and CRM all read from FIELDS.
"""
from dataclasses import dataclass
from typing import Literal, Optional

from pydantic import BaseModel, Field, create_model


@dataclass(frozen=True)
class CardField:
    key: str
    label: str
    section: str
    kind: str  # text | date | phone | int | number | choice
    hint: str = ""
    choices: tuple[str, ...] = ()
    required: bool = False


FIELDS: list[CardField] = [
    CardField("patient_id", "Patient ID", "Header", "text", "Top-right line. Often blank, an X, or a dash."),
    CardField("full_name", "Full Name", "Patient Information", "text", "Patient's full name as written.", required=True),
    CardField("date_of_birth", "Date of Birth", "Patient Information", "date", "Written in three blanks as MM / DD / YYYY.", required=True),
    CardField("phone", "Phone Number", "Patient Information", "phone", "US phone number, 10 digits.", required=True),
    CardField("gender", "Gender", "Patient Information", "choice", "Checkbox: whichever box is checked.", ("Male", "Female", "Other")),
    CardField("height_ft", "Height (ft)", "Patient Information", "int", "Feet part of height, usually 3-7."),
    CardField("height_in", "Height (in)", "Patient Information", "int", "Inches part of height, 0-11."),
    CardField("weight_lbs", "Weight (lbs)", "Patient Information", "number", "Weight in pounds, usually 50-400."),
    CardField("bp_systolic", "BP Systolic", "Vital Signs", "int", "Blood pressure number BEFORE the slash, usually 80-200.", required=True),
    CardField("bp_diastolic", "BP Diastolic", "Vital Signs", "int", "Blood pressure number AFTER the slash, usually 40-130.", required=True),
    CardField("heart_rate", "Heart Rate", "Vital Signs", "int", "Beats per minute, usually 40-180.", required=True),
    CardField("respiratory_rate", "Respiratory Rate", "Vital Signs", "int", "Breaths per minute, usually 8-40."),
    CardField("spo2", "SpO2 (%)", "Vital Signs", "int", "Oxygen saturation percent, usually 70-100.", required=True),
    CardField("temperature", "Temperature", "Vital Signs", "number", "Body temperature, usually 95-105 F or 35-41 C.", required=True),
    CardField("temperature_unit", "Temp Unit", "Vital Signs", "choice", "Which of F / C is circled. If neither is circled, return null.", ("F", "C")),
    CardField("blood_glucose", "Blood Glucose", "Vital Signs", "int", "mg/dL, usually 50-400."),
    CardField("bmi", "BMI", "Additional Information", "number", "kg/m2, usually 15-60. Copy what is written; do not calculate."),
    CardField("smoking", "Smoking History", "Additional Information", "choice", "Checkbox Yes / No.", ("Yes", "No")),
    CardField("alcohol", "Alcohol Use", "Additional Information", "choice", "Checkbox Yes / No.", ("Yes", "No")),
    CardField("physical_activity", "Physical Activity", "Additional Information", "choice", "Checkbox Yes / No.", ("Yes", "No")),
    CardField("medical_conditions", "Medical Conditions", "Additional Information", "text", "Free text, may span lines. 'None' is a valid answer."),
    CardField("current_medications", "Current Medications", "Additional Information", "text", "Free text, may span lines. 'None' is a valid answer."),
    CardField("notes", "Notes", "Notes / Additional Comments", "text", "Free text box at the bottom."),
    CardField("visit_date", "Date of Visit", "Footer", "date", "Written in three blanks as MM / DD / YYYY.", required=True),
    CardField("collected_by", "Collected By", "Footer", "text", "Name of the staff member or volunteer."),
]

FIELD_BY_KEY = {f.key: f for f in FIELDS}


class FieldReading(BaseModel):
    value: Optional[str] = Field(description="Exactly what is written, or null if blank, crossed out, or unreadable.")
    confidence: Literal["high", "medium", "low"]
    alternatives: list[str] = Field(description="Other plausible readings when unsure. Empty if confident.")
    note: Optional[str] = Field(description="Short reason when confidence is not high, e.g. 'digit could be 1 or 7'.")
    box_2d: Optional[list[int]] = Field(
        description="Where the handwritten answer (or the answer blank, if empty) is in the image: [ymin, xmin, ymax, xmax] normalized 0-1000."
    )


# One FieldReading per card field, in card order.
CardReading = create_model(
    "CardReading",
    **{f.key: (FieldReading, Field(description=f"{f.label}: {f.hint}")) for f in FIELDS},
)
