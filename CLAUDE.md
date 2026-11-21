# CLAUDE.md: ITKAN Hackathon project handoff

Read this first. It holds everything a new Claude session needs to continue the project.
The user is a high-school student leading the team; Claude acts as the "master agent":
planning, research and all the programming. The user handles the physical/CAD side.

---

## ⭐ PRODUCT NAME = **Iris** (decided Nov 21 afternoon; replaces the "FlatRate Health" placeholder everywhere)
- Logo: `C:\Users\hamda\Downloads\Interconnected Medical Cross Icon.png` (white mark on black). Derived assets in
  `scanner/web/static/`: `iris-mark-white.png` (nav bar), `iris-mark-dark.png` (portal, light backgrounds), `-1024` versions,
  `iris-icon.png` + `favicon.png` (navy rounded square; `shell.js` injects the favicon on every page). `PRODUCT_NAME = "Iris"`
  in `shell.js`; savings page, README, run.py and start.bat (`title Iris`, CRLF) renamed.
- **Pitch deck (judges):** Slides artifact https://claude.ai/artifact/P5DDAiutEfjJCHZHRE7ztc. 16 slides:
  - 8% problem → yearly cost by clinic size. These are the user's figures: small (3-5 providers) ≈ $100K/yr, medium (10-15) $180K-$420K, large $500K-$1.8M.
  - Why it's unfair → the Iris solution.
  - Pricing table: $499/provider/month billed yearly = $5,988/provider/yr; a 3-provider clinic keeps ≈ $82K/yr.
  - Patient journey → 8 AI features → 4 screenshot slides → what's different → "AI suggests, people approve" → roadmap → close.

  No team names (the user's choice). Source files are in the session scratchpad `deck/project/` and are lost between sessions,
  so edit the artifact with the Artifact tool (`read` first). It stays private until the user shares it.
- **Deck v2 (user feedback: TIME SAVED is the #1 message):** now 19 slides. Added "Clinics are drowning in paperwork"
  (2 h of computer work per 1 h with patients, Sinsky et al., Annals of Internal Medicine 2016; healthcare slow to adopt AI),
  "About 4.5 hours back per doctor per day" (estimate: coding 7 min×20, summaries 5 min×20, 1 appeal 30 min, 5 cards×2.5 min)
  and a dedicated scanner slide. The cover reads "The clinic platform built to save time".
- **Pitch script:** `Iris Pitch Script.pdf` in the project root (9 pages). A: slide-by-slide SAY lines + WHY boxes (~4 min).
  B: the user's questions answered (why Iris is cheaper: AI replaces billing staff, software scales, built for small clinics,
  web app; why $499 per provider: HIPAA hosting/BAA, AI usage, Surescripts/clearinghouse fees, EPCS identity proofing,
  certification, support all scale per prescriber; per-provider is predictable and the industry norm; ≈70-80% less than
  athenaOne per provider). C: likely judge Q&A + a numbers cheat sheet with sources.
- **New-user guide:** `Iris User Guide.pdf` in the project root (19 pages: real screenshots, every screen, quick reference,
  troubleshooting, glossary). Built from an HTML file + Playwright screenshots in the scratchpad, printed with Edge.
- **Camera safety fix (Nov 21):** `CAMERA_NAME=none|off|disabled` now means NO camera (`main.py` lifespan). Before, `pick_camera`
  fell back to "any real camera", so a test server grabbed the user's C920 and auto-scanned a frame (the images were deleted).
  Scan-page tests: load `/scan` with `wait_until="domcontentloaded"` (the MJPEG stream never finishes loading).
- **UI redesign v2 (Nov 21, same layouts, modern skin):** all in a theme layer at the end of `web/static/app.css`.
  - Inter + Space Grotesk via `@import` (system fonts offline); new tokens: brand #2F6FD0, navy #0E1F38, radius 14, shadows.
  - Sticky gradient nav with an animated underline; the logo turns on hover; the urgent Inbox badge pulses.
  - Cards lift on hover; gradient primary buttons with press feedback; focus rings; pop-in modals with a blurred backdrop;
    a slide-up toast; brand-colored links; content rises in (staggered) when the loader lifts (`html.iris-reveal`).
  - **2-second loading screen:** pages carry `<html class="iris-boot">` (all except crm.html). app.css draws the spinning
    logo with `body::before/::after` from the first paint. `shell.js` lifts it 2 s after the click: the click handler stores
    `sessionStorage.iris-nav` and shows `html.iris-leave`. Otherwise it lifts 2 s after `performance.timeOrigin`.
    - Same-page/#hash links, `target=_blank`, /api, /static, /video and /r are skipped.
    - It lifts by itself after 4 s if JS fails, and it's hidden in print.
    - **Skipped when `navigator.webdriver`** (Playwright), so tests aren't slowed. To test the loader, add the init script
      `Object.defineProperty(navigator,'webdriver',{get:()=>false})`.
    - Measured: click → fade starts at 2.0 s, fully visible ≈ 2.4 s.
- **Pushed (Nov 21 afternoon, `7257601` → main/track-a/track-b):** A6, the rebrand, UI v2 + loader, the camera fix, the PDFs.
- **`DEMO_SCRIPT.md` rewritten for Iris:** a ~4-min live demo, 5 page changes.
  - Flow: Dashboard → scan the Jhon card → Schedule → Robert → Check in & start visit → **copay window** (💵 Cash → Record
    $20.00 cash → Done; the B3 feature) → AI note from the transcript (backup transcript in the script) → 3 care gaps →
    nicotine patch → lipid panel → sign → Spanish summary → Ask the chart → Open claim → accept all → approve → submit (paid)
    → Aisha's appeal → Dashboard.
  - Right window: Pharmacy tab + Robert's Portal tab.
  - The dry-run script (`demo_dry.py` in the scratchpad) passed every step with real AI.

## ⭐ START HERE: current state + architecture map (updated Nov 21, 2026, about midday)

**Where we are (after Merge 2, `main` = `910a6a5`, about 5 h before judging):** the Nov 20 platform (Phases 1-7) is done.
Track A (Claude) finished A1 Ambient Notes, A2 EPCS, A3 Labs + Clinical Inbox, A4 Care gaps, A5 AI after-visit summary.
Track B (partner, GitHub `talha18-sys`) finished B1 Patient Portal, B2 Eligibility, B3 Balances/payments/statements,
B4 Reminder emails. **Everything is merged into `main`; `track-a` and `track-b` were reset to `main` on GitHub** (the
partner must `git pull` on `track-b`). Gemini billing is ON (prepaid credits).
**Plan for the remaining time (agreed with the user):** hours 1-3 = last features (Claude: optional A6 "Ask the chart",
like athenaOne's Sage; partner: optional B5 insurance-card photo → AI fills insurance) + merge 3; about 1.5 h before judging =
**code freeze**, then demo prep: rewrite `DEMO_SCRIPT.md` for today's features (pick the strongest 3-minute story), pitch
outline + judge Q&A, the user rehearses twice and records the backup video. After that comes merge 2 (`track-a` + `track-b` → `main`); see section 0 → Collaboration workflow.
**How the user works:** build one task → test it → report in plain language → the user says OK → commit + push to
`track-a` → next task. Keep CLAUDE.md updated *before* each commit.

### How to run
- User's app: double-click `scanner\start.bat` → http://127.0.0.1:8000/ (dashboard) + `/scan`. `run.py` detects an
  already-running copy and just opens the browser. There is no auto-reload: restart after Python changes.
- On demo morning (and after seed changes): Dashboard → **Reset demo data** (re-creates today's schedule).
- **Tests never touch the user's app:** run a separate server on port 8010:
  `cd scanner && LAB_SECONDS=3 DATA_DIR=<scratchpad>\testdata SMTP_PASS= CAMERA_NAME=none CAMERA_INDEX=9 .venv/Scripts/python.exe -m uvicorn app.main:app --port 8010`
  (`DATA_DIR` = separate DB, empty `SMTP_PASS` = no emails, `CAMERA_*` = don't grab the webcam, `LAB_SECONDS` = fast mock lab).
  API tests: httpx scripts. UI tests: Playwright with the installed Edge (`channel="msedge"`). JS syntax: `node --check`.
  Test scripts live in the session scratchpad (not the repo); recreate them as needed. Be frugal with AI calls (free quota).

### Stack
FastAPI (one process, `scanner/app/main.py`) + SQLite (`scanner/data/`, or `DATA_DIR`) + plain HTML/JS pages
(no build step) in `scanner/web/`, shared CSS in `web/static/app.css`, shared helpers in `web/static/shell.js`.
AI = Google Gemini via `app/ai.py` only (free tier; model fallback lists in `config.py`). Live updates = Server-Sent
Events: Python `events.broadcast({...})` → `/api/events` → one SharedWorker per browser (`static/events-worker.js`)
→ `onEvent(fn)` in every page. Email = Gmail SMTP (`mailer.py`), only ever sent to `PHARMACY_EMAIL_OVERRIDE`.

### Backend modules (`scanner/app/`)
| Module | Owns | Key endpoints (all under `/api`) |
|---|---|---|
| `main.py` | app setup, `PAGES` (URL → html), scanner/camera routes, SSE, calls every module's `init()` | `/scan`, `/upload`, `/submit`, `/events`, `/crm/*` |
| `config.py` | env/.env settings; model lists `READ_FALLBACKS`, `CODING_MODELS`, `SCRIBE_MODELS`; `DATA_DIR` | |
| `ai.py` | the ONLY Gemini entry point: `await ai.generate(models, contents, schema, system, thinking)` → (parsed, model); falls back on 429/503/404/timeout; raises `ai.AIUnavailable` | |
| `schema.py`, `reader.py`, `validate.py`, `camera.py`, `crm.py` | card scanner (fields, double read, validation/alerts, webcam, Salesforce-shaped mock CRM) | |
| `clinic.py` | tables providers, payers, pharmacies, patients, appointments, encounters, prescriptions. `get_patient()` returns the patient + appointments + encounters (vitals JSON) + prescriptions | |
| `clinic_api.py` | patients, schedule, visits, normal e-Rx, pharmacy inbox, demo reset | `/reference`, `/demo/reset`, `/patients…`, `/appointments…`, `/encounters…`, `/prescriptions…`, `/pharmacy/inbox` |
| `seed.py` | all fictional demo data; calls `epcs.init()`, `portal.seed()`, `labs.seed()`, `summary.seed()` | |
| `drugs.py` | formulary + `CONTROLLED` (DEA schedules) + `allergy_conflicts()` | |
| `epcs.py` (A2) | controlled-substance Rx: mock PDMP, rules, 2FA (PIN 2468 + emailed code) | `/pdmp/{pid}`, `/epcs/challenge`, `/epcs/sign` |
| `ambient.py` (A1) | AI ambient notes (audio or transcript → SOAP draft) | `/encounters/{id}/ambient/audio`, `/…/transcript` |
| `labs.py` (A3) | `lab_orders` table, mock lab, review | `/labs/catalog`, `/encounters/{id}/labs`, `/labs/{id}/result-now`, `/labs/{id}/review`, `/patients/{id}/results` |
| `inbox.py` (A3) | Clinical Inbox list + refill approve/deny + AI reply drafts (reads Track B's `messages`) | `/inbox`, `/inbox/count`, `/inbox/refills/{id}/approve` and `/deny`, `/inbox/messages/{id}/draft` |
| `caregaps.py` (A4) | 7 quality measures computed from the chart | `/patients/{id}/care-gaps`, `/care-gaps` |
| `askchart.py` (A6) | "Ask the chart": `sources_for(pid)` flattens the chart into cited sources (P profile, V<enc> visits incl. vitals/notes, RX<id>, L<order>, G care gaps, CL<claim>, BAL balance, INS coverage, A appointments, M portal messages); AI answers only from them with inline [ID] citations (invalid ids stripped); treatment questions → "the decision is the clinician's" + relevant facts | `/patients/{id}/ask` {question, history}, `/patients/{id}/ask/sources` |
| `summary.py` (A5) | AI after-visit summary: `encounters.summary` (sent text the portal shows), `summary_draft`, `summary_language`, `summary_status` (none/drafting/draft/failed/sent), `summary_sent_at`, `summary_ai`. Drafted in the background on signing (`draft_on_sign`, hooked in `clinic_api.save_encounter`) | `/encounters/{id}/summary` (GET), `/…/summary/draft` {language}, `/…/summary/send` {text} (signed visits only; also posts a portal message) |
| `codes.py`, `coder.py`, `billing.py`, `billing_api.py` | code lists, AI coding (sees the note + Rx + ordered labs), `claims` table + claim checker, billing API | `/claims…`, `/codes` |
| `payer.py`, `appeals.py` | mock insurer (remittance, CARC denials), AI denial fighter | via `/claims/{id}/submit`, `/denial/analyze`, `/appeal/submit` |
| `dashboard.py` | dashboard numbers + time-saved estimate | `/dashboard` |
| `mailer.py`, `events.py` | email (Rx, EPCS code), SSE broadcast | |
| `portal.py` (Track B) | `messages` table + patient portal | `/portal/{pid}…`, `/messages`, `/messages/{id}` (PATCH), `/messages/{id}/reply` |
| `eligibility.py` (B2) | mock insurer 270/271 eligibility: active/terminated (demo: Michael Johnson terminated), copay/coinsurance from `payer.PAYERS`, deductible progress; checked at booking + check-in | `/eligibility/check`, `/eligibility/patient/{pid}`, `/eligibility/day`, `/eligibility/batch` |
| `ledger.py` (B3) | `payments` table; balances computed live from claim remittances (PR-2/PR-3) + self-pay; mock card processor (Luhn, stores brand + last 4 only); statements | `/patients/{pid}/balance`, `/appointments/{id}/copay`, `/payments` (GET/POST); page `/statement?patient_id=` |
| `reminders.py` (B4) | `reminders` table; reminder emails (demo inbox only) with Confirm / Need to reschedule links (reschedule → `appointment_request` in `messages` → Clinical Inbox) | `/reminders`, `/reminders/preview/{appt}`, `/reminders/send`, `/appointments/{id}/confirm`, public `/r/{token}` |

Each module's `init()` creates its tables (plus `ALTER TABLE` auto-migrations for new columns). "Reset demo data" runs
`seed.seed()`, which clears and re-creates everything. **To add a module:** call its `init()` in `main.py` startup,
add its router with `app.include_router`, add any page to `PAGES` (and a nav link in `shell.js`), and add a `seed()`
hook in `seed.py` if it has demo data.

### Pages (`scanner/web/`) and shared scripts (`web/static/`)
- `/` dashboard.html: KPIs, AI time saved, up next, follow-ups, billing to-do, **Quality measures + Close care gaps today**.
- `/schedule` · `/inbox` (A3) · `/patients` · `/patient?id=` chart (care gaps, labs, visits, Rx).
- `/visit?id=`: vitals, ambient AI notes, note + dictation, **after-visit summary card**, Rx incl. EPCS, **lab orders**, **care gaps card**, sign.
- `/scan` card scanner · `/billing?claim=` · `/claim-form?id=` · `/pharmacy` mock pharmacy · `/savings` · `/crm` ·
  `/portal` (Track B patient portal).
- Shared JS:
  - `shell.js`: nav incl. the Inbox badge, `api()`, `esc`, `fmtDate`, `toast`, `openModal`, `onEvent`.
  - `rx-form.js`: normal + EPCS prescribing.
  - `ambient.js`.
  - `labs.js`: `labTable`, `labStatus`, `setupLabs`.
  - `caregaps.js`: `gapRows`, `setupCareGaps`.
  - `askchart.js`: `setupAskChart` (floating "✨ Ask the chart" button + drawer on the chart and visit pages; one per page).
  - `avs.js`: `setupAvs` (summary draft/edit/language/send/print). **Card scripts must look up their own elements with
    `box.querySelector`, not `$()`**: the visit page re-renders and a stale card would hit null (the Merge 2 bug).
  - Track B: `eligibility.js`, `payments.js` (balance card, payments), `reminders.js` (schedule page).
  - `patient-form.js`, `events-worker.js`.

### Live events (type → who listens)
- `schedule_changed`, `clinic_reset`, `patient_created`, `crm_saved`.
- `rx_sent` / `rx_updated`: pharmacy, visit, chart.
- `claim_created` / `claim_updated`: billing, visit, dashboard.
- `lab_ordered` / `lab_resulted` / `lab_reviewed`: visit lab card, chart, inbox, nav badge, dashboard.
- `message_created` / `message_updated`: inbox, portal, nav badge.
- `summary_updated` (drafting/draft/failed/sent): visit summary card; the portal reloads on it (it carries `patient_id`).
- `toast`.

### Demo story additions from today
- **Visit page:**
  - Record the conversation → AI SOAP draft (A1).
  - Prescribe tramadol → PDMP + two-factor signing (A2).
  - Order TSH/A1c → the result arrives in the Inbox about 20 s later → review it with a note → the patient sees it in the portal (A3).
  - Robert Nguyen's 1 PM annual physical: 3 care gaps (BP follow-up, BMI plan, tobacco) closed in 3 clicks (A4).
  - Sign Linda's visit → the AI after-visit summary is drafted in about 2 s → switch to Spanish → send → it appears in her
    portal's Visit summaries with a "your summary is ready" message (A5).
- **Inbox:** approve James's metformin refill (it goes to the pharmacy + email + a portal reply); AI-draft a reply to Aisha.

---

## 0. HACKATHON DAY PLAN (Sat Nov 21, 2026): plan + detailed progress log
The platform from Phases 1-7 (sections 3-4) is **done and working**. Today (~7 h at the event) we add the
athenaOne features we're missing, built by **two people in parallel**: Claude on Track A, the user/partner on Track B.
Status: plan approved. The user said to **start Track A directly** (skeleton/partner setup still pending; the partner's
GitHub username and judging time haven't been given yet).

**Progress (branch `track-a`):**
- ✅ **A1 AI Ambient Notes**: `app/ambient.py` (`POST /api/encounters/{id}/ambient/audio` with a 16 kHz mono WAV upload,
  `POST /api/encounters/{id}/ambient/transcript` with `{transcript}` → `AmbientNote` {transcript, subjective, objective,
  assessment, plan, patient_instructions, needs_review, model}; saves `encounters.ambient_transcript`; 409 on signed
  visits) + `web/static/ambient.js` (panel on the visit page: "🎙 Record the visit" (MediaRecorder → re-encoded in the
  browser to 16 kHz WAV → upload; live level meter + timer; auto-stop at 9 min) and "⌨ Wispr Flow transcript"
  (the user has **Wispr Flow** installed; **double-tap Caps Lock** starts/stops it and it types into the focused box)).
  The draft shows S/O/A/P + patient instructions + "check before signing" + transcript → **Insert into visit note**
  (asks replace vs. add below) → autosave. The prompt forbids invented findings/doses and boilerplate exam phrases.
  Uses `config.SCRIBE_MODELS` (lite models first: on Nov 21 morning `gemini-3.5-flash` was taking >20 s even for
  trivial prompts). `ai.generate` now prints `[ai] <model> failed (<kind>)` to the server log on each fallback.
  Tested: TTS two-voice conversation fed as Edge's fake microphone (`--use-file-for-fake-audio-capture=x.wav%noloop`)
  → draft 7.6 s after stop, accurate (levothyroxine 75→100, TSH, 6-week follow-up); transcript path OK; 9/9 UI checks.
- ✅ **A2 EPCS (controlled substances, DEMO)**: `app/drugs.py` `CONTROLLED` (9 drugs with schedules: tramadol C-IV,
  hydrocodone-APAP C-II, oxycodone C-II, alprazolam C-IV, lorazepam C-IV, zolpidem C-IV, amphetamine salts C-II,
  methylphenidate ER C-II, pregabalin C-V) + `SCHEDULE/DEFAULT_DAYS/OPIOIDS/BENZOS`. `app/epcs.py`: prescriptions
  get `schedule, days_supply, dea_number, epcs_signed_at, pdmp_reviewed` columns; providers get `dea`
  (`DEMO-DEA-0001`…, also set on Reset demo data); **fictional PDMP** (`POST /api/pdmp/{patient_id}` {drug, strength, quantity,
  days_supply}): demo histories by MRN (Fatima = 3 prescribers/3 pharmacies multiple-provider flag, Linda = active
  alprazolam → opioid+benzo boxed warning, David = old tramadol) + this clinic's controlled Rx; flags for duplicate
  active Rx and daily MME ≥50/≥90. Rules: C-II 0 refills, C-III-V ≤5, days' supply 1-90 required, C-II opioids ≤7
  days, PDMP must be reviewed, allergy check. **2FA:** `POST /api/epcs/challenge` emails a 6-digit code (or returns
  `dev_code` when email is off) → `POST /api/epcs/sign` {request_id, pin (demo PIN **2468**), code}; 5-min expiry,
  3 tries, no replay. Signed Rx → pharmacy inbox (DEA schedule/DEA#/days/"signed with 2-factor") + email with a
  "CONTROLLED SUBSTANCE (EPCS) DEMO: NOT A VALID PRESCRIPTION" banner. The normal `/api/prescriptions` rejects
  controlled drugs (409). UI in `rx-form.js` (controlled optgroup, PDMP panel, days' supply, refills locked for C-II,
  inline 2FA step); `rxStatusBadge` shows "C-II · EPCS". Tested: 17/17 API + 9/9 UI.
- `run.py`: if the app is already running (start.bat double-clicked), it now just opens the browser instead of crashing
  on port 8000. `start.bat` title is now "FlatRate Health".
- **Testing isolation (important):** the user may have the app running. Run test servers on **port 8010** with
  `DATA_DIR=<scratchpad>\testdata SMTP_PASS= CAMERA_NAME=none CAMERA_INDEX=9` (new `DATA_DIR` env in `config.py`) so
  tests never reset the user's demo DB, grab the camera, or send email.
- **Merge 1 (about 10:45, Nov 21):** `track-a` (A1+A2) + `track-b` (B1) → `main` (merge commit `7fc0fab`). The only
  conflicts were in `main.py` (both tracks added imports/init/routers; kept both). Tested on the merged code: EPCS 17/17 + 9/9,
  10 pages loading with 10 tabs open, live updates OK, no page errors. Local `track-a` was fast-forwarded to `main`.
  **The partner should run `git pull origin main` into `track-b` before continuing.**
- **Track B so far (partner = GitHub `talha18-sys`):** ✅ **B1 Patient Portal** `/portal` (`app/portal.py`, `web/portal.html`):
  demo sign-in by picking a patient; appointments + request; message threads; refill requests; test results (reads
  Track A's `GET /api/patients/{id}/results`, **not built yet: A3 must add it**); visit summaries (`encounters.summary`,
  **A5 writes it**); billing placeholder. It owns the `messages` table; staff endpoints for the Clinical Inbox:
  `GET /api/messages`, `PATCH /api/messages/{id}`, `POST /api/messages/{id}/reply` (events `message_created`/`message_updated`).
  Also a fix: all tabs share ONE SSE stream via a SharedWorker (`static/events-worker.js`) because browsers cap 6 connections
  per site (5+ tabs used to hang); the scan page releases the camera stream while hidden; `api()` retries GETs during restarts.
- ✅ **A3 Lab orders + results + Clinical Inbox** (commit `9adfdb1` on `track-a`): `app/labs.py` (`lab_orders` table; `CATALOG`
  CBC/CMP/LIPID/A1C/TSH/GLU/UA with CPTs; **mock lab** returns chart-consistent values (diabetic → high A1c, hypothyroid →
  high TSH, obesity/HLD → high lipids, UTI → positive UA), deterministic per order, after `LAB_SECONDS` (env, default 20;
  "Result now (demo)" button); flags H/L/A; `POST/GET /api/encounters/{id}/labs`, `POST /api/labs/{id}/result-now`,
  `POST /api/labs/{id}/review` {comment, reviewer}, **`GET /api/patients/{id}/results`** (portal contract: test_name, status,
  results[{analyte,value,unit,ref_range,flag}], provider_comment); events `lab_ordered`/`lab_resulted`/`lab_reviewed`;
  seed: reviewed history + Omar A1c 5.9 H and Maria lipid waiting). `app/inbox.py`: `GET /api/inbox` (unreviewed results +
  Track B `messages` with status new/to_clinic, abnormal first), `/api/inbox/count` (nav badge in `shell.js`),
  refill approve (new Rx → pharmacy + email + portal reply; controlled drugs → 409 "use EPCS"; allergy check) / deny,
  `POST /api/inbox/messages/{id}/draft` (AI reply draft with urgency note, `SCRIBE_MODELS`). Plain replies/mark done use
  Track B's endpoints. `web/inbox.html` (`/inbox`, filters, "Working as" provider, live arrivals), `web/static/labs.js`
  (lab card on the visit page, results panel on the chart). Coder prompt now lists labs ordered at the visit (billable);
  CPT 80053 added. Patients see results immediately in the portal (Cures Act style); the review adds a note.
  Tested: API 18/18, UI 11/11 (+ AI draft 1 s), EPCS regression 17/17.
- ✅ **A4 Care gaps / quality measures** (commit `8bc40bd` on `track-a`): `app/caregaps.py`: 7 simplified measures computed
  live from the chart: CMS165 BP control (HTN, latest BP <140/90), CMS22 elevated-BP follow-up (no HTN dx, BP ≥130/80 →
  note mentions BP + a plan), CMS122 A1c (diabetes: A1c ≤6 months and <8%; pending order = "waiting"), CMS347 statin
  (diabetes/HLD 40-75), CMS69 BMI (+ weight plan if ≥30), CMS138 tobacco (screened via card `smoking` field or note;
  users need cessation counseling), AWV (65+, annual visit). **Only clinician notes count** (screening-card advice text
  doesn't). Open gaps carry `close` {kind lab|note|vitals|rx|book}. `GET /api/patients/{id}/care-gaps`, `GET /api/care-gaps`
  (per-measure met/eligible + today's scheduled patients with open gaps). UI `web/static/caregaps.js`: visit-page side
  card with one-click close (Order A1c / Add to note / Go to vitals) that updates live after autosave ("✓ Care gap closed"
  toast); chart "Care gaps" panel; dashboard "Quality measures" bars + "Close care gaps today" list.
  Seed: heights + `smoking: No` on past visits; **Robert's fair card = BP 168/104, BMI 31.6, smoker** (3 gaps, closed live
  at his 1 PM annual physical, a good demo moment); James's seeded A1c pinned to 7.8. Tested 14/14 + A3/EPCS regressions.
- ✅ **A5 AI after-visit summary** (`app/summary.py`, `web/static/avs.js`): signing a visit drafts a 6th-grade-level
  summary in the background (sections: Why you came in / What we found / Your medicines / Tests / What to do next /
  When to get help). The prompt forbids new facts, says "Stop: old dose / Start: new dose" for changes, explains lab
  values, and has no jargon or markdown. **7 languages** (English, Spanish, Arabic, Urdu, Vietnamese, Chinese, Hindi; RTL
  for Arabic/Urdu) with correct accents. The provider edits it → "Send to patient portal" (409 unless signed) →
  `encounters.summary` + portal message "Your visit summary … is ready"; Re-draft keeps the sent version until re-sent;
  Print. Seed: summaries on Maria's and Aisha's past visits. Dashboard time saved includes 5 min per summary sent.
  Tested 16/16 (draft about 1.7 s after signing) + regressions (care gaps 14, labs 18+11, EPCS 17).
- **Merge 2 (Nov 21 afternoon):** `track-a` (A3-A5) + `track-b` (B2-B4) → `main` = `910a6a5`. Conflicts (`main.py` imports,
  `seed.py` seed calls, `patient.html` script tags) were keep-both. The merged rehearsal found an `avs.js` bug (page-wide
  `$()` lookups in a card that can go stale after re-render) → fixed in the merge commit. Tested on the merged code: original
  demo rehearsal 100%, 12 pages open at once, labs 18+11, gaps 14, EPCS 17, AVS 15, Track B endpoints OK. Merged-app tests
  ran from a temporary `git worktree` with a launcher that loads the real `.env` key (never printed) with email off.
- ✅ **A6 Ask the chart** (built + tested; **NOT pushed: the user said to wait for their OK before pushing to `track-a`**):
  `app/askchart.py`, `web/static/askchart.js`, styles in `app.css`, hooked into `patient.html` + `visit.html`.
  About 1 s per answer (`SCRIBE_MODELS`, lite first). Verified: Robert pre-visit summary (BP 168/104, BMI, smoker, 3 gaps),
  James last A1c 7.8 [lab] + follow-up "is that at goal?", Linda "favorite food" → "That isn't in the chart", Aisha denial
  CO-197 [claim], Michael coverage terminated [INS], Maria "double her lisinopril?" → clinician's decision + dose, last BP,
  normal CMP. UI 10/10 + regressions (gaps 14, labs UI 11, all pages 15).
- ⏭ Next: push A6 when the user OKs it; merge 3; code freeze; demo prep.

### Research summary: athenaOne vs. us (Nov 21)
athenaOne = athenaClinicals (EHR) + athenaCollector (practice management/billing) + athenaCommunicator (patients).
**Already have:** charting/templates, dictation, e-prescribing + allergy checks, scheduling, registration,
check-in, claim scrubbing, claim submission, payment posting (remittance), denial management + AI appeals,
dashboard, card-scan intake.
**Missing → building today** (below). **Out of scope (roadmap only, say so in the pitch):** real pharmacy network
(Surescripts) and clearinghouse connections, government/ONC certification, mobile app, telehealth video,
immunization registry, fax.

### Track A: AI clinical (Claude, branch `track-a`), in priority order
1. **🎙 AI Ambient Notes** (~1.5 h): browser records the doctor-patient conversation (MediaRecorder) →
   audio sent to Gemini (multimodal) → draft SOAP note → doctor edits → sign. Matches athenaOne's flagship
   "Ambient Notes" (athenaAmbient, used by 170K+ clinicians). Must say "AI draft, review before signing".
2. **💊 Controlled-substance e-prescribing (EPCS), DEMO** (~1 h; the user explicitly approved it). It sends to the pharmacy
   inbox **and automatically emails** the demo inbox, like normal Rx. Demo rules to build:
   - Formulary gains controlled drugs with a DEA schedule (e.g. tramadol C-IV, alprazolam C-IV, zolpidem C-IV,
     pregabalin C-V, oxycodone C-II, amphetamine salts C-II); schedule badge shown.
   - **Mock PDMP check** (fictional state prescription-monitoring history) shown before signing, with risk flags.
   - **Two-factor signing:** a one-time code emailed to the demo inbox (stands in for the DEA-required 2FA) must be
     entered to sign.
   - **C-II: 0 refills enforced**, days-supply limit; prescriber's fictional DEA number on the Rx.
   - Email + inbox clearly labeled **"CONTROLLED SUBSTANCE (EPCS) DEMO: NOT A VALID PRESCRIPTION"**.
     Pitch note: the real version requires a certified EPCS app + DEA registration + identity proofing.
3. **🧪 Lab orders + results + 📥 Clinical Inbox** (~2 h): order labs on the visit (CBC, CMP, A1c, lipid, TSH, UA…)
   → mock lab returns results after a short delay (abnormal ones flagged H/L) → **Clinical Inbox** page listing results
   to review/sign + **refill requests + patient messages from Track B's portal**.
4. **✅ Care gaps / quality measures** (~1 h): rules on chart + dashboard (BP not controlled ≥140/90, A1c overdue
   for diabetics, tobacco cessation counseling due, BMI ≥30 follow-up, annual exam due).
5. **📝 AI after-visit summary** (~30 min, if time allows): patient-friendly summary saved on the encounter; the portal shows it.
6. If time allows: **"Ask the chart" AI assistant** (like athenaOne's Sage).

### Track B: front desk & patients (user/partner, branch `track-b`), in priority order
1. **📱 Patient Portal** (~2 h): patient view (pick a demo patient): upcoming appointments, request an
   appointment, lab results (from Track A), visit summaries, messages to the clinic, **refill requests**, bill + pay.
2. **🛡 Eligibility check** (~1 h): mock insurer response (active/inactive, plan, copay, deductible remaining)
   at booking and check-in; flag inactive coverage.
3. **💵 Patient balances, copay collection at check-in, statements** (~1.5 h): patient ledger (copays +
   patient responsibility from remittances), take payment (mock card), printable statement.
4. **✉ Appointment reminder emails** (~45 min) via the existing mailer (demo inbox only).
5. If time allows: **insurance card photo → AI fills insurance fields** (reuse the card reader).

### How Tracks A and B connect (the contract; the skeleton creates these so neither waits on the other)
- `messages` table (owned by B): `id, patient_id, direction ('to_clinic'|'to_patient'), kind ('message'|'refill_request'|
  'appointment_request'), subject, body, status ('new'|'done'), rx_id, created_at`. B writes from the portal;
  A's Clinical Inbox reads `kind`/`status` and marks items done. Event: `message_created`.
- `lab_orders` / `lab_results` (owned by A); `GET /api/patients/{id}/results` (A) is read by the portal (B). Event: `lab_resulted`.
- `encounters.summary` column (A writes the after-visit summary); the portal reads it from `GET /api/patients/{id}`.
- `GET /api/patients/{id}/balance` (B) may be shown on the chart by A.
- Each module creates **its own tables** in its own `init()`; no edits to other tracks' tables.

### Collaboration workflow (Git branches + merges, not copy-pasting code)
0. **Skeleton (Claude, about 15 min, on `main`):** empty modules/routers/pages for every feature above, nav links,
   page routes in `main.py`, shared tables from the contract, plus `COLLAB.md` (file ownership + rules). Push to `main`.
1. **Partner setup:** add them as a repo collaborator (**ask the user for their GitHub username and confirm before
   adding**) → clone → venv + `pip install -r scanner/requirements.txt` → **their own `scanner/.env` with their OWN
   Gemini key** (a shared key hits the 20 requests/model/day free limit fast) → `git checkout -b track-b`.
2. Claude works on `track-a`. **Both commit + push every ~30 min.**
3. **Merges** at about +2 h, +4 h and the final merge: Claude merges both branches into `main`, resolves conflicts, runs the
   rehearsal test (scratchpad `rehearsal.py`-style), pushes; both then `git pull origin main` into their branch.
4. **Rules:** edit only files your track owns (listed in `COLLAB.md`). Shared files (`main.py`, `shell.js`,
   `app.css`, `seed.py`, `clinic.py`) are changed **only by Claude**; ask before touching them.
   Never commit `.env`; run the secret grep (section 6) before every push.
5. **Code freeze about 1.5 h before judging** → final merge, Reset demo data, rehearse, record the backup video.

### Open questions for the user
- Who is the partner? Do they have a laptop, and will they use Claude Code? Their **GitHub username** (for repo access)?
- **What time is judging?** (Sets the merge times and the code freeze.)
- Product name + real flat price (placeholders: "FlatRate Health", $499/provider/month).

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

### Files (scanner part; the full module map is in ⭐ START HERE at the top)
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
- **UPDATE Nov 21 (midday): billing is ON, PREPAID.** The user added prepaid credits in AI Studio (https://ai.studio/projects),
  so the free-tier 20/day limit no longer applies. If credits run out, EVERY model fails with **402 "prepayment credits are
  depleted"** (ai.py treats it as quota → all fallbacks fail → `AIUnavailable`): the user must add credits there.
  Still avoid wasteful AI calls in tests (they cost real money, though only fractions of a cent each).
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

### Architecture (the original Nov 20 plan; for what actually exists see ⭐ START HERE at the top)
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
- Don't commit or print `.env`. The repo is on GitHub (section 6); run the secret grep before every commit.
