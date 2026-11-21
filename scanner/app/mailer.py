"""Optional real email for e-prescriptions (demo stand-in for the Surescripts network).

Only sends when SMTP is configured in .env, and only to PHARMACY_EMAIL_OVERRIDE (an inbox
the team controls). The fictional pharmacies' addresses are never emailed.
"""
import smtplib
from email.message import EmailMessage

from . import config


def enabled() -> bool:
    return bool(config.SMTP_USER and config.SMTP_PASS and config.PHARMACY_EMAIL_OVERRIDE)


def recipient() -> str:
    return config.PHARMACY_EMAIL_OVERRIDE


def prescription_email(rx: dict) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = f"New e-Prescription for {rx['first_name']} {rx['last_name']}: {rx['drug']} {rx['strength']}"
    msg["From"] = config.SMTP_USER
    msg["To"] = config.PHARMACY_EMAIL_OVERRIDE
    msg.set_content(
        f"""New prescription (DEMO - fictional patient, not a real prescription)

To: {rx['pharmacy_name']}
Rx #: {rx['id']}

Patient:   {rx['first_name']} {rx['last_name']}   DOB {rx['dob']}   {rx['mrn']}
Allergies: {rx['allergies'] or 'None reported'}

Medication: {rx['drug']} {rx['strength']}
Sig:        {rx['sig']}
Quantity:   {rx['quantity']}    Refills: {rx['refills']}

Prescriber: {rx['provider_name']}, {rx['provider_credentials']}   NPI {rx['provider_npi']}
Sent:       {rx['sent_at']}
Clinic:     {config.CLINIC_NAME}
"""
    )
    return msg


def _send(msg: EmailMessage) -> None:
    with smtplib.SMTP_SSL(config.SMTP_HOST, 465, timeout=15) as s:
        s.login(config.SMTP_USER, config.SMTP_PASS)
        s.send_message(msg)


def send_prescription(rx: dict) -> None:
    """Blocking; call from a worker thread. Raises on failure."""
    _send(prescription_email(rx))


def send_test() -> None:
    msg = EmailMessage()
    msg["Subject"] = f"{config.CLINIC_NAME}: e-prescription email is working"
    msg["From"] = config.SMTP_USER
    msg["To"] = config.PHARMACY_EMAIL_OVERRIDE
    msg.set_content("Test message from the hackathon demo. Prescriptions sent in the app will arrive here.")
    _send(msg)
