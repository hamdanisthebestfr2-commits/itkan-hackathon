import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
# Benchmarked on the sample card: the flash-lite models were 100% correct in ~3.5 s;
# full flash models were equally accurate but took 12-160 s.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
# Second, different model for the cross-check read; disagreements get flagged for review.
GEMINI_MODEL_2 = os.environ.get("GEMINI_MODEL_2", "gemini-3.1-flash-lite")
THINKING_LEVEL = os.environ.get("THINKING_LEVEL", "minimal")
# Medical coding needs more reasoning than reading a card; it isn't time-critical (runs after signing).
CODING_THINKING = os.environ.get("CODING_THINKING", "low")


def _models(env: str, default: str) -> list[str]:
    return [m.strip() for m in os.environ.get(env, default).split(",") if m.strip()]


# Fallback chains: the free tier allows ~20 requests per model per day, so if one model is out of quota
# (or busy) the next one is used automatically. Best model first.
# Order = best first, then FAST fallbacks (lite models answer in ~1-3 s), slow big models last.
CODING_MODELS = _models("CODING_MODELS", "gemini-3.5-flash,gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemini-3.7-flash,gemini-3.8-flash")
# Ambient notes are interactive (the doctor waits): fast lite models first, bigger model as backup.
SCRIBE_MODELS = _models("SCRIBE_MODELS", "gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemini-3.5-flash,gemini-3.7-flash")
READ_FALLBACKS = _models("READ_FALLBACKS", "gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemini-3.7-flash")
DOUBLE_READ = os.environ.get("DOUBLE_READ", "1") == "1"
# Camera is picked by name (Windows can renumber devices); CAMERA_INDEX is the fallback.
CAMERA_NAME = os.environ.get("CAMERA_NAME", "C920")
CAMERA_INDEX = int(os.environ.get("CAMERA_INDEX", "0"))
EVENT_NAME = os.environ.get("EVENT_NAME", "ITKAN Community Health Fair")
CLINIC_NAME = os.environ.get("CLINIC_NAME", "Plano Community Clinic (demo)")

# Optional: real email for e-prescriptions (Gmail: use an App Password). Sent only to the override address.
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
PHARMACY_EMAIL_OVERRIDE = os.environ.get("PHARMACY_EMAIL_OVERRIDE", "")

# Tests point DATA_DIR at a scratch folder so they never touch the real demo database.
DATA_DIR = Path(os.environ.get("DATA_DIR") or ROOT / "data")
SCANS_DIR = DATA_DIR / "scans"
DB_PATH = DATA_DIR / "crm.sqlite3"
WEB_DIR = ROOT / "web"

SCANS_DIR.mkdir(parents=True, exist_ok=True)
