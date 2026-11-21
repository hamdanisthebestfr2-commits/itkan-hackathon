# CLAUDE.md: ITKAN Hackathon project handoff

Read this first. It holds everything a new Claude session needs to continue the project.
The user is a high-school student leading the team; Claude acts as the "master agent":
planning, research and all the programming. The user handles the physical/CAD side.

---

## 1. The hackathon
- **Event:** ITKAN AI Hackathon, https://www.itkan.one/I-Hackathon
- **When/where:** **Saturday Nov 21, 2026**, 8:30 AM to 7:00 PM, ITKAN Hub, 1701 10th St, Plano TX. In person.
- **Format:** about 7.5 hours of building, then a **live demo** to judges. Middle/high-school teams of 2 to 5.
- **Rules:** pre-planning and **pre-written code are allowed** (confirmed by the user).
- **Prizes:** $1,000 / $600 / $400.
- **Judges:** Mohammad Musa (Deepen AI), Ehab Gabr (Sigmatic, which applies **AI to healthcare operations**, the most relevant judge), Reshma Hyder (MASRIF / StyleMeAI), Ahmed Reza (Yobi), Eric van Gemeren (Discreetize), and one TBA.

---

## 2. Product vision (as of Nov 20 evening)

**One clinic platform, an "athenaOne alternative" for small clinics, built AI-first.**

**Pitch:** athenaOne charges small clinics a **percentage of everything they collect** (third-party
estimates: about 4-8% of monthly collections, sometimes over 10%, with small practices quoted at the high end).
For 3 providers that is roughly $65k-185k/yr; for 5-10 providers, $150k-450k/yr. Most of that percentage pays for
**billing paperwork** (claims, denials, insurer rules). We automate that paperwork with AI and charge a
**flat monthly price**.

**Framing rule:** say "unfair for small clinics", not "scam". The percentage does include billing services,
and judges respect a pitch that gives the other side credit. Real complaints back this up: confusing pricing,
high cost for small practices, slow billing support (G2 3.4/5, Capterra 3.8/5).

### Feature set (what the user asked for)
1. **Card scanner (DONE):** a webcam reads handwritten health-fair intake cards; the AI fills the record.
2. **Patients:** register new patients, search, and a patient chart (demographics, insurance, vitals history,
   visits, prescriptions, claims).
3. **Scheduling:** book appointments by provider and time slot, a day/week calendar, check-in, status.
4. **Visits/charting:** the provider writes or dictates a visit note; vitals come from the scan.
5. **Prescriptions (e-prescribe):** pick a drug, dose and pharmacy, then "Send". It goes **automatically** to the
   pharmacy, shown in a **mock pharmacy inbox page** in real time, plus an optional **real email** via SMTP to an
   address the team controls.
   - Be honest in the pitch: real US e-prescribing uses the **Surescripts** network (NCPDP SCRIPT), not email.
     Our demo simulates it.
6. **AI billing pipeline:** the main differentiator against athena's percentage fee.
   1. **AI coding:** the AI suggests ICD-10 diagnosis codes and CPT procedure codes from the visit note.
      Each code cites the note text it is based on, and codes are checked against a **fixed curated code list**
      so the AI can't invent codes. **Staff approve** before anything is used (same review idea as the scanner).
   2. **Claim checker ("scrubber"):** catches errors that get claims rejected *before* they are sent: missing
      insurance or member ID, a procedure code without a diagnosis that justifies it, missing DOB, and so on.
   3. **Claim:** a CMS-1500-style claim view, then "submit" to a **mock insurer**, which returns paid or denied
      (denials use standard reason codes, CARC).
   4. **Denial fighter:** the AI explains the denial and **drafts an appeal letter**.
   5. **Savings dashboard:** "athenaOne at 6% of collections would cost $X/yr; our flat price is $Y."
7. **Dashboard:** today's schedule, patients seen, claims status, revenue, follow-ups needed, savings.

**Product name:** not decided. "FlatRate Health" is a placeholder; ask the user.
The current scanner UI is called "IntakeScan" and the mock CRM "Clinic CRM".

### Honesty / safety rules for the demo
- **Fake patients only.** Never real patient data (it would be HIPAA-protected).
- The AI **suggests** and a human **approves**. Nothing medical or financial is sent without review.
- The mock insurer, mock pharmacy and fake insurers/pharmacies use **fictional names** (no real company names
  as if they were partners).
- Screening alerts are labeled "screening flags, not a diagnosis".
- **Roadmap items to mention, not build:** clearinghouse integration (e.g. Availity) for real claims,
  Surescripts for real e-prescribing, HIPAA hosting with a BAA, ONC certification.

---

## 3. What exists right now (working)

`scanner/` holds a working FastAPI app. **Start:** double-click `scanner\start.bat`. It opens
`http://127.0.0.1:8000/` (Scanner) and `http://127.0.0.1:8000/crm` (mock CRM).

### Scanner flow
Webcam → auto-detect card → hold steady 0.8 s → beep → best frame flattened → **Gemini reads it twice in
parallel with two different models** → merge (fields where the reads disagree are flagged) → validation → review
screen → Enter → saved to the mock CRM → the record "types itself in" on the CRM page.

### Files
| File | What it does |
|---|---|
| `scanner/app/schema.py` | **Single source of truth for card fields** (`FIELDS`), plus the Pydantic `FieldReading`/`CardReading` (value, confidence, alternatives, note, `box_2d`) |
| `scanner/app/reader.py` | Gemini calls (`google-genai` SDK), the prompts, image prep (EXIF fix, max 1600 px), double-read merge, `_clean()` (X/dash = blank) |
| `scanner/app/validate.py` | Normalization (dates, phone, numbers, choices), ranges, cross-checks (BP order, temp unit, **BMI vs height/weight**), `clinical_alerts()` (urgent / follow_up / info) |
| `scanner/app/camera.py` | Background camera thread, card detection, steadiness check, best-frame pick, flattening, MJPEG preview, camera pick by name |
| `scanner/app/crm.py` | SQLite mock CRM, Salesforce-shaped: `Contact` + `Health_Screening__c`, duplicate check (name + DOB or phone), stats |
| `scanner/app/main.py` | FastAPI routes: `/video` (MJPEG), `/api/events` (SSE), `/api/status`, `/api/settings`, `/api/scan`, `/api/upload`, `/api/submit`, `/api/pending`, `/api/cameras`, `/api/crm/*` |
| `scanner/web/scanner.html` | Live video, Scan/Upload, camera dropdown, auto-scan and auto-submit toggles, review form (color-coded, **handwriting crops from `box_2d`**, alternative chips), keyboard: Space = scan, Enter = submit, Esc = discard |
| `scanner/web/crm.html` | Stats bar, patient list, record page with Salesforce API names, animated "typing" fill, source card image |
| `scanner/web/static/app.css` | Shared styles (CSS variables) |
| `scanner/eval/run_eval.py` | Accuracy test: `eval/cards/cardNN.jpg` + `cardNN.json` (true values). Reports field accuracy, errors caught vs. slipped through |
| `scanner/run.py`, `scanner/start.bat` | Launcher (uvicorn on 127.0.0.1:8000, opens both pages) |
| `scanner/.env` | **Secrets/config. Never print or commit.** `GEMINI_API_KEY`, `CAMERA_INDEX=1`, optional `CAMERA_NAME`, `GEMINI_MODEL`, `GEMINI_MODEL_2`, `DOUBLE_READ`, `EVENT_NAME` |
| `scanner/README.md` | User-facing quick start |
| `PLAN.md`, `shopping-list.html` | Earlier planning docs. PLAN.md assumed the Claude API; **we switched to Gemini** (see below) |

### Key decisions and findings
- **AI provider: Google Gemini free tier.** The team chose not to buy Claude API credit (budget).
  Benchmark on the real card: `gemini-3.5-flash-lite` and `gemini-3.1-flash-lite` with
  `thinking_level="minimal"` were **25/25 fields correct in about 3.5 s**. Full flash models were equally accurate
  but took 12-160 s, so don't use them for live scanning. `gemini-2.5-*` returns 404 for new users. The key
  works with newer models (list them via `client.models.list()`).
  The double read uses both lite models in parallel, about 7-8 s per card. `DOUBLE_READ=0` halves calls if
  rate-limited.
- **Structured output:** `response_schema=CardReading` (Pydantic), `response.parsed`.
  `box_2d` (0-1000 normalized `[ymin, xmin, ymax, xmax]`) is accurate enough for crops.
- **Sample card** (`eval/cards/card01.jpg`, filled in with fake data): "Jhon Harzorwick", BP 120/80
  (systolic handwriting is messy; the user has **not yet confirmed it is 120**). BMI is written as 24.9, but
  5'6"/220 lb = **35.5**; the app flags this, a good demo moment.
- **Card layout:** "Patient Health Record". Patient ID; Full Name; DOB MM/DD/YYYY; Phone; Gender
  (Male/Female/Other checkboxes); Height ft/in; Weight lbs; BP sys/dia; Heart Rate; Respiratory Rate; SpO2;
  Temperature (°F/°C circled); Blood Glucose; BMI; Smoking/Alcohol/Physical Activity Yes/No; Medical Conditions;
  Current Medications; Notes box; Date of Visit; Collected By. **There are no insurance fields**, and billing
  needs them: plan a v2 card or capture insurance at registration.
- **Camera:** Logitech C920 ("HD Pro Webcam C920"). On this laptop: 0 = Integrated Camera,
  1 = C920, 2 = OBS Virtual Camera (but numbering can change). The app **picks the camera by name**
  (`pygrabber`) with `CAMERA_INDEX` as fallback. Requires `cv2.CAP_DSHOW` + MJPG for 1080p.
- **Card detection** (`camera.py::find_card`), tuned with a synthetic harness (the real card pasted into real
  C920 frames of the user's room, which has black/white striped walls, fingers over the edges, rotations,
  landscape/portrait):
  1. A fast closed-contour outline plus a paper check (bright, with ink).
  2. Otherwise, `_card_region`: a bright area dense with printed ink. Inside that area, look for an exact outline
     from straight lines (Hough), scored by **direction-aware edge coverage**. An outline must contain at least
     90% of the card's ink, which rejects the section boxes printed on the card.
  3. Otherwise scan a **generous padded box**. Too big is harmless; cutting the card off is not.

  Results: 90% scan-usable on the hard synthetic set (the old detector got 2%), 0 false positives on the empty
  room, about 17-55 ms per frame.

  "Holding still" = **image difference inside the card area** < `MOTION_THRESHOLD`, not corner positions.
  `HOLD_FRAMES` keeps the last outline through brief misses. The user confirmed: "this is perfect".
- **Validation flag vs. clinical alert:** a flag means "possible misread, verify". An alert means "real but
  concerning" (e.g. BP ≥ 180/120 is urgent). BP "info" starts above 120/80 so a normal 120/80 doesn't trigger
  a false alarm.

### Environment notes (Windows laptop)
- Python 3.12 was installed per-user via winget: `%LOCALAPPDATA%\Programs\Python\Python312\python.exe`.
  The venv is `scanner\.venv`. Run things with `scanner\.venv\Scripts\python.exe`. Packages are listed in
  `scanner\requirements.txt` (google-genai, fastapi, uvicorn[standard], python-multipart, opencv-python, numpy,
  pydantic, python-dotenv, pillow, httpx, pygrabber).
- The project lives in **OneDrive** (`C:\Users\hamda\OneDrive\Desktop\ITKAN Hackathon`).
- **Git Bash gotcha:** paths like `/c/Users/...` embedded *inside* `python -c "..."` strings are NOT converted
  (they become `C:\c\Users\...`). Use Windows paths (`r'C:\Users\...'`) inside Python code.
- **Headless screenshots** for UI checks: `msedge --headless=new --screenshot=... --timeout=4000 URL`. Don't
  use `--virtual-time-budget`, because the SSE connection makes it hang.
- Only one process can own the webcam. Stop the app before running camera test scripts.
- The server has no auto-reload. Restart it after Python changes (static HTML changes only need a page refresh).

---

## 4. Build plan for the platform (next steps, in priority order)

**Principle:** every phase must leave a working, demoable app. Build in order; stop wherever time runs out.
**Process the user asked for:** build **one phase at a time**, then stop and report the changes. Wait for the
user's OK before starting the next phase. Before big new scope, present the plan first and get approval.

### Status
| Phase | Status |
|---|---|
| 1. Platform shell + Patients + scanner hookup | ✅ Done and approved by the user |
| 2. Scheduling | ✅ Done and approved by the user |
| 3. Visit + e-prescribe + pharmacy inbox + email | ✅ Done and approved. **Email is live** (SMTP in `.env`, test email confirmed) |
| 4. AI coding + claim checker + Billing page + CMS-1500 view | ✅ Done and approved |
| 5. Mock insurer + denial fighter + AI model fallback | ✅ Done and approved |
| 6. Dashboard + savings calculator | ✅ Done and approved |
| 7. Polish + rehearsal + demo guide | ✅ **Done (Nov 20 night)**, waiting for the user's review. The user still needs to record the backup video |

### Phase 7 summary
- **`DEMO_SCRIPT.md` (project root)** = the team's day-of guide: morning checklist, a timed 3-minute click-by-click
  demo with talking points, a "what if something breaks" table, judge Q&A, 6-slide pitch outline, how to record the
  backup video, and post-hackathon cleanup (revoke the Gemini key + Gmail App Password).
- Checked every page at 1366×768: no horizontal overflow, no errors.
- **Full dress rehearsal** (Playwright, real AI, email off) passes in about 40 s: dashboard → upload Jhon card → BMI flag
  fix → save (new patient) → chart edit (insurance/pharmacy) → walk-in visit → copy screening vitals → note → e-Rx
  nicotine patch (arrives live at the pharmacy, status back) → sign → AI coding (about 5 s) → accept → checker clean →
  approve → submit → paid $135 → Aisha denial → appeal → approved $52.50 → savings → dashboard 35 min → 1 hr 14 min.
- Fixes: schedule runs 8 AM-**7 PM** (evening demo); the visit page's signed banner reflects the claim status (paid, with insurer…);
  **Reset demo data** button on the dashboard; `CODING_MODELS` reordered so fast lite models are the first fallbacks;
  `ai.CALL_TIMEOUT` 20 s.
- `scanner/README.md` rewritten for the whole platform.

### ⚠ AI quota (read this before testing anything)
- The Gemini key is on the **FREE tier: about 20 requests per model per day** (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`,
  resets at midnight Pacific). Development and testing on Nov 20 used up `gemini-3.5-flash` (alias of 3.6-flash).
- `app/ai.py` = the single entry point for all Gemini calls (`ai.generate(models, contents, schema, system, thinking)`).
  It **falls back through a model list** on 429/503/404 and timeouts (45 s per call), remembers exhausted models
  (1 h cooldown), retries "minimal" thinking as "low" for models that reject it, and raises `ai.AIUnavailable`
  with a staff-friendly message. Lists in `config.py`: `CODING_MODELS` (coding + appeals) and `READ_FALLBACKS`
  (card reading; the double read uses `GEMINI_MODEL` + `GEMINI_MODEL_2` first).
- **Recommended to the user:** enable billing on the Gemini API key in Google AI Studio (pay-as-you-go, costs pennies)
  before the demo. Do NOT use multiple free projects to get around quotas (against Google's terms).
- **Be frugal in tests:** avoid AI calls unless the test is about the AI. About 5 calls per full demo run
  (2 scan + 1 coding + 1-2 appeals).

### What Phase 1 added (files)
- `app/clinic.py`: SQLite tables + queries: providers, payers, pharmacies, patients, appointments, encounters,
  prescriptions. Includes `record_scan()` (a scanned card becomes a patient + screening encounter) and
  `slot_taken()` (double-booking check).
- `app/seed.py`: fictional demo data (3 providers, 5 payers, 3 pharmacies with `.example` emails, 10 patients,
  10 appointments **today** + 3 tomorrow, past visits and prescriptions). Runs on first start (empty DB) and via
  `POST /api/demo/reset`.
- `app/clinic_api.py`: `/api/reference`, `/api/demo/reset`, `/api/patients` (GET list/search, POST register with
  duplicate 409, GET/PUT one), `/api/appointments` (GET by day, POST book with double-booking 409, PATCH status/time,
  POST `/{id}/start-visit`), `/api/encounters/{id}` (GET/PUT; signing completes the appointment),
  `/api/prescriptions` (POST send with allergy check 409 unless `override_allergy`; `/check`; PATCH status),
  `/api/pharmacy/inbox`. All broadcast live events.
- `app/events.py`: shared SSE `broadcast()` (moved out of main.py).
- `app/drugs.py`: about 30-drug demo formulary + `allergy_conflicts()` (e.g. Penicillin allergy → Amoxicillin).
- `app/mailer.py`: Gmail SMTP sender for prescriptions. **Only sends to `PHARMACY_EMAIL_OVERRIDE`** (set in `.env` to
  the user's demo inbox `ibrahimosman123cc@gmail.com`). Needs `SMTP_USER` + `SMTP_PASS` (a Gmail App Password) in
  `.env`; not set yet (Phase 3).
- `app/main.py`: includes the clinic router, seeds on startup, page routes in the `PAGES` dict
  (`/` and `/patients` → patients.html for now; `/patient`, `/scan`, `/crm`). The scan submit also calls `clinic.record_scan`.
- `app/camera.py::pick_camera`: if the C920 isn't plugged in, it now picks a **real** camera (never "OBS Virtual Camera").
- `web/static/shell.js`: **PRODUCT_NAME constant** (rename here), top nav (future pages shown greyed out as
  "soon"), helpers (`api`, `esc`, `fmtDate`, `age`, `toast`, `openModal`, `onEvent` SSE, `reference()`), plus an
  on-page red error bar for any JS error.
- `web/static/patient-form.js`: register/edit modal with validation (phone/ZIP/email/DOB; member ID required for insurance).
- `web/patients.html` (list/search/register; `/patients#register` opens the form), `web/patient.html` (chart:
  allergy banner, insurance, contact/pharmacy, problems/meds, appointments, latest vitals with abnormal highlighting,
  vitals history, visits with scanned card thumbnail, prescriptions). Book/Start visit/Prescribe buttons are
  disabled until Phases 2-3.
- `web/scanner.html`: now uses the shared nav and the "Save to patient record" button; after saving it shows
  "Open patient chart ↗".
- `app.css`: shell/nav/table/form/modal/badge styles; `[hidden]{display:none!important}` (fixed the review header showing when empty).
- `run.py` opens `/patients` and `/scan`.
- Product name placeholder: **FlatRate Health** (user will choose the real name later).

### What Phase 2 added
- `web/schedule.html` (`/schedule`, enabled in the nav):
  - **Day view:** one column per provider, 8 AM to 5 PM in 15-minute rows (`PX_PER_MIN = 1.5`), prev/today/next and a
    date picker (`?date=YYYY-MM-DD`), status summary pills, legend, a red "now" line, past slots hatched (can't book).
  - **Booking:** click a slot to open the modal (patient typeahead search with arrow keys/Enter, "+ New patient" opens
    the register form and then returns with that patient selected, date/time/length/provider/visit type/reason).
    Past times are blocked client-side; double-booking is blocked server-side (409, shown in the modal).
  - **Appointment popup:** Check in / Undo, Reschedule (date/time/length/provider), No-show, Cancel (confirm),
    Restore. "Start visit" is disabled until Phase 3.
  - **Show cancelled** toggle, **Reset demo data** button, live refresh on SSE `schedule_changed`.
  - `?patient_id=` = **booking mode** (banner "Booking for X: click an open slot"). `?appt=` opens that
    appointment's popup.
- `patient.html`: **Book appointment** → `/schedule?patient_id=`; appointment times link to `/schedule?date=&appt=`.
- `clinic_api.change_appointment`: restoring a cancelled/no-show appointment also runs the double-booking check.
- **Demo-day note:** seeded appointments are created for *the day the data is seeded*. **On Nov 21 morning, press
  "Reset demo data"** on the Schedule page so today's schedule is full.

### What Phase 3 added
- `web/visit.html` (`/visit?id=ENCOUNTER`): header (patient, insurance, date, provider, reason or walk-in, status), allergy bar.
  - **Vitals grid:** abnormal values turn amber/red, BMI is calculated, and "Use vitals from <screening> · <date>"
    copies the latest recorded vitals (e.g. from today's card scan) via `latest_vitals` (which includes date and type).
  - **Note:** autosaves (700 ms debounce, "Saved ✓ time"). **🎤 Dictate** uses the browser Web Speech API
    (`webkitSpeechRecognition`, works in Edge/Chrome, needs the mic and internet). Also "Insert SOAP template" and
    "Insert vitals" (writes a sentence such as "Vitals: BP 124/78, HR 88, SpO2 91%.").
  - **Prescriptions this visit:** the list with live statuses, plus the shared Rx form.
  - **Sign & complete visit:** requires a note and a confirm. The encounter is set to `signed`, the appointment to `completed`,
    and the page becomes read-only. The server rejects edits (409) and prescribing on signed visits.
  - Side panel: conditions, meds, pharmacy, insurance, previous visits, medication history.
- `web/static/rx-form.js` (`renderRxForm`, `rxStatusBadge`): formulary dropdown → strengths/default sig/qty,
  preferred pharmacy preselected, **live allergy check** (red alert; sending is blocked unless "Override" is ticked
  *and* a reason is given; the reason is appended to the sig as `[Allergy override: …]`), sends, and reports email status.
- `web/pharmacy.html` (`/pharmacy`, nav enabled): "Simulated pharmacy (demo) / Surescripts" disclaimer, tabs per
  pharmacy, counts, e-Rx cards (drug, sig, qty/refills, patient + DOB + allergies, prescriber). New ones **arrive live**
  with an animation, chime and toast. Buttons: Mark received → Mark filled → Ready for pickup; the status shows live on
  the visit page and the chart. Email status badge, plus a **Send test email** button when SMTP is configured.
- Schedule popup: **Check in & start visit** (booked), **Start visit** (checked in), **Open visit** (in visit),
  **View signed visit** (completed), all via `POST /api/appointments/{id}/start-visit` (reuses an existing encounter).
- Patient chart: **Start visit** = walk-in modal (choose provider; warns about an unsigned visit, with a link) via
  `POST /api/encounters`. **Prescribe** opens the Rx form in a modal (asks for the prescriber). Visits have a
  "Continue/View visit →" link. Prescriptions show live status badges.
- API additions: `POST /api/encounters` (walk-in), `GET /api/email/status`, `POST /api/email/test`; quantity/refills validation.
- **Email setup (the user must do this; never paste the password in chat):** Gmail → Google Account → Security →
  2-Step Verification ON → "App passwords" → create one → add to `scanner/.env`:
  `SMTP_USER=<the sending gmail address>` and `SMTP_PASS=<16-char app password>`, then restart. Emails go only to
  `PHARMACY_EMAIL_OVERRIDE=ibrahimosman123cc@gmail.com`. Check with Pharmacy page → Send test email.

### What Phase 4 added
- `app/codes.py`: approved code lists. About 70 ICD-10 codes (our own short descriptions) and about 32 CPT/HCPCS codes
  with demo charges. Also E/M groups (new 9920x / established 9921x / preventive), `SUPPORTED_BY` (which diagnoses
  justify each procedure, prefix match), `CONFLICTS` (Excludes1-style diagnosis pairs), `search()`, `bmi_code()`.
- `app/billing.py`: `claims` table (one per signed office visit; codes stored as JSON lists with
  status suggested/accepted/rejected, source ai/manual, evidence, confidence, reason; procedures also have
  units/charge/modifiers/dx links). `patient_status()` = new vs established (signed office visit in the prior 3 years).
  **`check()` = claim checker** (runs on every read): insurance/member ID/DOB/sex/address/NPI; pending suggestions;
  no codes; duplicates; diagnosis conflicts; one E/M only; new-vs-established mismatch (fix: swap); preventive age
  band (swap); preventive + problem E/M needs modifier 25 (fix); every procedure linked to a diagnosis (fix: link);
  **medical necessity** (fix: link an existing supporting diagnosis, otherwise REMOVE the procedure. **We never
  auto-add a diagnosis**, which would be upcoding/fraud); BMI Z68 needs E66 (fix: remove Z68); BMI code vs measured
  BMI (swap); $0 total; timely filing (1 year). `apply_fix()` handles remove/swap/modifier/link.
- `app/coder.py`: Gemini (`CODING_MODEL=gemini-3.5-flash`, `CODING_THINKING=low`, about 3-4 s) with structured output
  `CodingResult` (diagnoses + procedures with evidence quotes, confidence, reason, dx links, em_rationale).
  The prompt includes the full approved code list and the **MDM 2-of-3 rule** (problems/data/risk), so E/M levels are
  right (tested: HTN not at goal + dose change → 99214; new obesity + smoking counseling → 99203 + 99406;
  new strep with rapid test + antibiotics → 99203 + 87880 + J02.0). After the AI: unknown codes are removed (and
  reported), quotes not found in the note get low confidence, links are filtered, and staff-added codes are kept on re-run.
  It runs as a background task: **signing a visit creates the claim and starts coding** (`clinic_api.save_encounter`
  is now async), and progress is broadcast as `claim_created` / `claim_updated`.
- `app/billing_api.py`: `GET /api/claims`, `GET /api/claims/{id}` (detail + issues), `GET /api/encounters/{id}/claim`,
  `POST /api/claims/{id}/ai-code`, `PUT /api/claims/{id}/codes` (validates against the lists, recomputes charges),
  `POST /api/claims/{id}/fix`, `POST /api/claims/{id}/ready` (409 if errors or unreviewed suggestions),
  `POST /api/claims/{id}/reopen`, `GET /api/codes?q=&kind=dx|cpt`. Closed claims (submitted/paid/denied/appealed) → 409 on edits.
- `web/billing.html` (`/billing?claim=ID`, nav enabled): claims list with status/total/errors; claim detail with an AI
  status bar (running spinner, "AI suggested N codes", errors), the **signed note with evidence highlighted**
  (hovering a code highlights its quote), diagnoses with letters A-L, procedures with "Billed for" dx chips (click to
  link/unlink), Accept ✓ / Reject ✕ / Undo / Remove, "Accept all high-confidence", add-code search boxes, "Why this
  visit level" box, total charge, **Claim checker** panel with one-click fix buttons (edit-patient fixes open the
  patient form), Approve claim (disabled while errors or pending), Edit codes. "Submit to insurer" is disabled until Phase 5.
- `web/claim-form.html` (`/claim-form?id=`): printable CMS-1500-style form (boxes 1a, 2, 3, 5, 11, 21 dx A-L,
  24 lines with dx pointers, 25-33), marked DEMO.
- `visit.html`: after signing, the green bar shows live "AI is suggesting billing codes…" → "codes ready → Open claim".
- `seed.py`: billing history (Maria and James paid, Fatima submitted) + fictional street addresses for all patients.

### What Phase 5 added
- `app/payer.py`: **mock insurer** with fictional per-payer rules keyed by `payer_code`: allowed rate, copay (PR-3),
  coinsurance (PR-2, Medicare 20%), `prior_auth` (Prairie Mutual: 94010 spirometry and 93000 ECG, each with a
  policy-exception appeal test), `bundled` (Gulf Coast: 82962/81002 bundled into E/M, never appealable),
  `not_covered` (Medicare: preventive 9938x/9939x), `frequency` (A1c once per 90 days unless therapy changed/uncontrolled).
  `adjudicate(detail)` returns a line-level **remittance** (like an ERA/EOB) with CARC codes (CO-16/11/29/96/97/119/197,
  CO-45 contractual adjustment) and a hidden `appealable` flag per denied line. `review_appeal()` overturns appealable
  denials and upholds the rest. `warnings_for()` feeds the claim checker with **pre-submission warnings**
  (prior auth missing → fix "Enter auth #", bundling, non-covered).
- `app/appeals.py`: **AI denial fighter** (`DenialAnalysis`: plain_english, recommendation
  appeal|correct_and_resubmit|write_off|bill_patient, winnable, evidence_quotes, letter, attachments). The prompt
  forbids recommending appeals of correct denials, invented facts get [placeholders], and quotes must be exact.
  Verified: Aisha (CO-197, note documents an exacerbation) → "appeal, likely" plus a proper letter citing PM-RES-114 →
  approved, $52.50 recovered. David (CO-97 bundling) → "write off" with the reason.
- `app/billing.py`: claims have new `remittance`, `appeal`, `prior_auth` columns (auto-migrated with ALTER TABLE);
  statuses: review → ready → submitted → paid | partial | denied → appealed → paid/partial/denied, or closed.
- `app/billing_api.py`: `POST /api/claims/{id}/prior-auth`, `/submit` (ready only; self-pay → 400; adjudicates after
  2.5 s "clearinghouse" delay), `/check-status` (submitted → answer now), `/denial/analyze {code}` (AI),
  `PUT /appeal {letter}`, `/appeal/submit {letter}` (insurer decides after 3 s), `/write-off {code}`,
  `/correct` (reopen denied as a corrected claim). Events carry `event`: submitted/adjudicated/appeal_submitted/appeal_decided.
- `web/billing.html`: "Submit to <insurer>" (spinner until the response), "Check claim status", **Insurer response
  table** (billed/allowed/paid/patient owes, PAID/DENIED with CARC + text, remarks), **🤖 Fight this denial** →
  **Denial fighter** panel (plain English, insurer policy, recommendation + chance, evidence quotes also highlighted
  in the note, editable letter, Submit appeal / Print letter / Write off $X / Correct & resubmit / Draft an appeal
  anyway, live outcome). Prior auth # field. Summary pills: with insurer / with denials / $ collected.
- Demo history (seed): Maria and James paid (adjudicated at seed time), Fatima submitted (use "Check claim status"),
  **Aisha partly denied: 94010 CO-197 (winnable appeal)**, **David partly denied: 82962 CO-97 (write off)**.

### What Phase 6 added
- `app/dashboard.py` → `GET /api/dashboard`: today's appointment counts + up-next list, patients (total / new today /
  card scans today), prescriptions (sent today / at pharmacy / emailed), billing money (collected, recovered by
  appeals, written off, open denials $), AI activity (cards read, visits coded, codes suggested, staff acceptance %,
  appeals drafted/won), **follow-ups** (screenings in the last 30 days with urgent/follow-up alerts + whether
  they're booked), billing action items, and **estimated staff time saved** (`MINUTES_SAVED`: card 2.5, coding 7,
  appeal 30 minutes; the assumptions are shown on the page).
- `encounters.alerts` column (auto-migrated); `record_scan` stores screening alerts there.
- `web/dashboard.html` = **home page `/`**: greeting, quick actions (Scan / Register / Schedule), **hero figure =
  staff time saved by AI** (with a "How is this estimated?" tooltip), 6 clickable stat tiles, and lists: Up next (Start/Open
  visit), Needs follow-up (Book link), Billing to-do. Live refresh on SSE events.
- `web/savings.html` (`/savings`): sliders (providers, monthly collections per provider, % fee 3-10%, FlatRate
  $/provider/month **placeholder default $499**), hero = savings per year, 4 tiles, an **SVG line chart** (annual
  cost vs monthly collections; % model orange `#eb6834` with a 10% wash, flat blue `#2a78d6`; palette validated with the
  dataviz `validate_palette.js`: all checks pass), direct end labels, "your clinic" markers with a 2px white ring,
  crosshair + tooltip on hover, a clinic-size table (1/3/5/10 providers), honest sourcing notes, and a "what the %
  pays for → how FlatRate handles it" table. Default (3 providers, $45K/mo, 6%, $499) → **$79,236/yr saved**.
- Nav: Dashboard + Savings enabled; the brand links to `/`; `run.py` opens `/` and `/scan`.
- Seed: patients backdated 200 days (so "new today" = 0); past claims stored as AI-coded and accepted, with one AI
  suggestion rejected (James: Z79.899), so the dashboard shows 35 min saved / 94% acceptance at the start; plus a
  **health-fair screening yesterday for Robert Nguyen (BP 168/104 → follow-up)**, who is booked today
  (a nice story: the fair flagged him and he came in).

### Testing notes
- Phase 6: 11/11 (dashboard API numbers, renders, live update on check-in, start visit from dashboard, savings math
  $79,236 default and $264,120 for 10 providers, preset buttons, chart tooltip, no page errors). Regression: Phase 2
  14/14, Phase 3 21/21, UI Phase 2 7/7, UI Phase 3 12/12.
- Phase 5: API 19/19 (seeded denials, AI appeal → approved, AI write-off, check status, prior-auth warning,
  submit → paid, locks). UI click-through 9/9 (appeal flow with live outcome, write-off, check status), no page errors.
  The test scripts live in the session scratchpad (not the repo); recreate them if needed.
- **Run test servers with email OFF** so automated tests don't email the user's inbox:
  `SMTP_PASS= .venv/Scripts/python.exe -m uvicorn app.main:app --port 8000` (an env var overrides `.env`). (Before this
  was noticed, the Phase 3/4 test runs sent about 10-15 fictional prescription emails to the demo inbox; the user was told.)
- Phase 4: API test 20/20 (claim on sign, AI coding about 3 s, checker rules, one-click fixes, approve, locks), UI click-through
  9/9 (sign visit → codes ready on visit page → billing suggestions → hover evidence → accept all → add lipid panel →
  medical-necessity error → one-click remove → approve → CMS-1500 renders), no page errors.
- Phase 3: API test 21/21 (start visit + reuse, autosave, prescribe, penicillin → amoxicillin blocked (409), override,
  validation, inbox, status flow, sign → appointment completed, signed lock (409), walk-in, email status/test).
  UI click-through 12/12 with two browser windows (provider + pharmacy: live arrival and live status back), plus the
  override path. Dictation can't be tested headless (needs a real microphone); it is disabled with a tooltip if unsupported.
- **UI click-through tests use Playwright driving the installed Edge** (`pip install playwright` is in the venv,
  not in requirements; `p.chromium.launch(channel="msedge", headless=True)`, no browser download needed).
  The Phase 2 script booked via search, registered + booked a new patient, checked the double-booking error, checked in,
  rescheduled, and tested chart → booking mode: 7/7 passed with no page errors. Use forward slashes in paths
  inside Python f-strings (a `\u` sequence breaks them) and set `PYTHONIOENCODING=utf-8` when printing arrows.
- Phase 2 API test: 14/14 passed (book, overlap 409, same time on another provider OK, check-in, cancel frees the slot,
  restore into a taken slot 409, reschedule, provider move 409, bad status 400).
- Phase 1 API/integration test passed 15/15 (register, duplicate block, edit, chart, card upload → new patient + screening).
- Headless Edge screenshots can fire before async fetches finish and show "Loading…". Use `--timeout=8000`
  and a fresh `--user-data-dir`, or `--dump-dom`.
- Don't measure latency with one-off `httpx.get()` calls on Windows (about 730 ms client setup each). Use one
  `httpx.Client()`: the server answers in about 6-8 ms.
- Check inline page JS syntax: extract the `<script>` blocks and run `node --check` (Node v24 is installed).

### Architecture
- **Grow the existing FastAPI app** (same server, same port, no build step, plain HTML/JS + shared CSS). Rename
  the folder/app only if the user picks a name.
- **Same SQLite DB**, with new tables: `providers`, `patients` (demographics + insurance: payer, member ID, group),
  `pharmacies` (fictional, each with an email), `appointments`, `encounters` (visit note, vitals,
  status), `prescriptions` (drug, dose, sig, qty, refills, pharmacy, status sent/received/filled),
  `claims` + `claim_lines` (CPT, ICD-10 pointers, charge), `payer_responses` (paid/denied, CARC), `appeals`.
- **Scanner integration:** scan submit → find or create the **patient** → create a **screening encounter**
  with the vitals. Keep the existing `/crm` Salesforce-shaped view working, or fold it into the
  patient chart.
- **Left-nav app shell:** Dashboard · Schedule · Patients · Scan Intake · Billing · Pharmacy (mock) · Savings.
- **Seed data:** 2-3 fictional providers, about 10 fictional patients with insurance, about 3 fictional
  pharmacies, a few fictional insurers, and an appointments-filled day for Nov 21.
- **Curated code lists** (`codes.py`): about 40 common primary-care ICD-10 codes (I10 hypertension,
  E66.9 obesity, E11.9 type 2 diabetes, F17.210 nicotine dependence, Z00.00 adult exam, Z71.6 tobacco counseling,
  R03.0 elevated BP reading, ...) and CPT codes (99202-99205 new and 99212-99215 established office visits,
  99406/99407 tobacco counseling, 82947 glucose, 93000 ECG, ...). **Write our own short descriptions**
  (official CPT descriptions are AMA-copyrighted). Add a charge per CPT for claims.
- **Drug list** (`drugs.py`): about 30 common generic meds with strengths and default sig (lisinopril 10 mg,
  amlodipine 5 mg, metformin 500 mg, atorvastatin 20 mg, ...). Optional simple interaction/allergy warnings.
- **Email:** `smtplib` with Gmail SMTP + **app password** in `.env` (`SMTP_USER`, `SMTP_PASS`, `PHARMACY_EMAIL_OVERRIDE`).
  If not configured, show only the in-app pharmacy inbox. Never email real pharmacies.

### Phases
1. **Platform shell + Patients:** nav, seed data, patient list/search, register form (incl. insurance),
   patient chart. The scanner creates/updates patients.
2. **Scheduling:** day view per provider (time slots), book/reschedule/cancel, check-in → "start visit".
3. **Visit + e-prescribe:** encounter page (vitals from scan, note text area + **browser dictation** via
   Web Speech API), prescriptions → pharmacy inbox page (live via SSE) + optional email.
4. **AI coding + claim checker:** Gemini suggests codes from the note (structured output, validated against
   `codes.py`, with evidence quotes and confidence). Staff approve, then scrubber rules run, then the claim is built.
5. **Mock insurer + denial fighter:** submit → deterministic mock adjudication (e.g. a missing pre-auth or
   mismatched code → denied with a CARC code) → AI explanation + appeal letter (editable, printable).
6. **Dashboard + savings calculator:** KPIs, claims pipeline, "percentage-of-collections vs flat fee" chart.
7. **Polish:** a demo script, seeded "demo day" data, reset button, record a **backup demo video**, pitch slides.

### Demo story (target, about 3 min)
New patient walks in → scan intake card (patient auto-registered, BMI mismatch caught) → book/check-in →
provider dictates a note → AI suggests codes, provider approves → e-prescribe lisinopril, which appears in the pharmacy
inbox / email instantly → claim checker catches a missing field, fixed in one click → submit → one older claim
shows a denial, and the AI writes the appeal → dashboard: "this clinic would pay athenaOne $X/yr; with us, $Y."

---

## 5. Open items / questions for the user
- Product **name**?
- Confirm the sample card's **systolic BP = 120**.
- **Card dimensions** (the CAD holder needs a camera distance of about 1.25× the card height).
- More **test cards** (10-15, varied handwriting) for `eval/run_eval.py`. Pitch-slide accuracy numbers come from these.
- **Gmail app password** for real pharmacy emails (optional).
- After the hackathon: **delete and replace the Gemini API key** (it was pasted in chat).
- **Insurance on the intake card:** a v2 card design, or collect insurance at registration.

---

## 6. GitHub repo
- **https://github.com/hamdanisthebestfr2-commits/itkan-hackathon** (PRIVATE, branch `main`). The project root is the
  repo root. `gh` is logged in as `hamdanisthebestfr2-commits`.
- Root `.gitignore` excludes `.env` (API key + Gmail App Password), `.venv/`, `scanner/data/` (SQLite DB + scans),
  and `__pycache__`. **Before every commit, check that no secret is staged:** `git grep --cached -n -E "(GEMINI_API_KEY|SMTP_PASS)=[A-Za-z0-9]"`.
- New laptop setup: clone → `cd scanner` → `py -3.12 -m venv .venv` → `.venv\Scripts\pip install -r requirements.txt`
  → create `scanner\.env` by hand (see `scanner/README.md` → Settings) → `start.bat`.
- Commit/push only when the user asks; end commit messages with the attribution line from the system reminder.

## 7. Working conventions
- Match the existing code style: small focused modules, short docstrings explaining *why*, plain HTML/JS.
- Keep `FIELDS`-style single sources of truth (code lists, drug list, seed data).
- After changing reader or prompt logic, run `scanner\.venv\Scripts\python.exe scanner\eval\run_eval.py`.
- Verify UI changes with headless Edge screenshots; verify APIs with small httpx scripts.
- Keep the demo safe: everything should degrade gracefully (AI error → manual entry; no SMTP → in-app inbox).
- Don't commit or print `.env`. There is no git repo yet.
