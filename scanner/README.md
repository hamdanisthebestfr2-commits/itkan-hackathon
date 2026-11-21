# FlatRate Health (demo)

An AI-first clinic platform for small clinics: intake card scanning, patients, scheduling, visits, e-prescribing,
AI billing codes, a claim checker, a mock insurer, and an AI denial fighter. All patients, insurers and pharmacies are fictional.

## Start
1. Plug in the webcam (Logitech C920) first.
2. Double-click **`start.bat`**. The **Dashboard** and **Scan Intake** pages open in your browser.
3. Close the black window to stop. Data is saved between runs.

On demo morning: **Dashboard → ↺ Reset demo data** fills today's schedule. Full guide: `..\DEMO_SCRIPT.md`.

## Pages
| Page | What it does |
|---|---|
| Dashboard `/` | Today at a glance, staff time saved by AI, follow-ups, billing to-dos |
| Schedule `/schedule` | Day view per provider; click a slot to book, click an appointment to check in / start visit |
| Patients `/patients`, chart `/patient?id=` | Register, search, full chart; Book / Start visit / Prescribe |
| Scan Intake `/scan` | Webcam reads handwritten health-fair cards → review → patient + screening visit |
| Visit `/visit?id=` | Vitals, dictated note, e-prescribe (allergy checks), sign → AI coding starts |
| Pharmacy `/pharmacy` | Simulated pharmacy inbox (prescriptions arrive live; optional real email) |
| Billing `/billing` | AI codes with evidence, claim checker + fixes, submit to mock insurer, denial fighter + appeal letters |
| Savings `/savings` | Percentage-of-collections vs flat-price calculator |

## Settings (`.env`, private: never share)
```
GEMINI_API_KEY=...                 # Google AI Studio key (free tier = ~20 requests per model per day)
CAMERA_INDEX=1                     # fallback if the C920 isn't found by name
SMTP_USER=... / SMTP_PASS=...      # Gmail + App Password for prescription emails
PHARMACY_EMAIL_OVERRIDE=...        # the only address prescription emails go to
DOUBLE_READ=1                      # 0 = one AI read per card (saves AI quota)
```

## Accuracy test for the scanner
Card photos + answer keys in `eval/cards/` (`cardNN.jpg` + `cardNN.json`), then:
`.venv\Scripts\python.exe eval\run_eval.py`
