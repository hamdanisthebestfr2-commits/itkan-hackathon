# Intake Card Scanner: Software Plan

ITKAN AI Hackathon, Sat Nov 21, 2026. Pre-building is allowed.

**Goal:** a health-fair volunteer slides a handwritten intake card into the holder. Within seconds the fields appear in a Salesforce-style CRM. Uncertain fields are flagged for a quick human check, and nothing wrong is ever entered silently.

---

## 1. How it works

```
 Webcam (C920 in 3D-printed holder)
        │  live video
        ▼
 ┌─────────────────────────────────────────────────────────────┐
 │  Python app on the laptop (FastAPI server)                  │
 │                                                             │
 │  1. CAPTURE   OpenCV: detect card → wait until steady →     │
 │               pick sharpest of ~5 frames → flatten/crop     │
 │  2. EXTRACT   Claude vision reads the card → structured     │
 │               JSON (value + confidence + alternates/field)  │
 │               Read twice in parallel; disagreements flagged │
 │  3. VALIDATE  Format + range rules, normalize phone/BP/date │
 │               Abnormal vitals → "follow-up" alert           │
 │  4. REVIEW    Web page: card image + form, flagged fields   │
 │               yellow with zoomed handwriting crop           │
 │  5. SUBMIT    Save to the CRM (mock now, real Salesforce    │
 │               later via the same interface)                 │
 └─────────────────────────────────────────────────────────────┘
        │
        ▼
 Mock CRM web page: patient list + record page; new record
 fills in field by field during the demo
```

On the demo laptop, the **Scanner** page and the **CRM** page sit side by side.

---

## 2. Tech stack

All of it is free except the API usage, and there is no complicated build step.

| Part | Choice | Why |
|---|---|---|
| Language | Python 3.12 | Simple, with the best libraries for camera and AI work |
| Web server | FastAPI + Uvicorn | Small and fast; streams live camera video and updates to the browser |
| Camera / image | OpenCV | Capture, card detection, sharpness check, perspective correction |
| AI | Anthropic Python SDK, `claude-opus-5-5` | Strongest handwriting reading. Structured outputs guarantee valid JSON |
| Data schema | Pydantic | One definition of the card fields, used by the AI output, the validation and the CRM |
| Database | SQLite (built into Python) | No setup; one file |
| Frontend | Plain HTML/JS + a CSS framework from a CDN | No build tools to break at the event |
| Real Salesforce (stretch) | `simple_salesforce` + free Developer Edition | Same interface as the mock, switched in config |

---

## 3. Project layout

```
ITKAN Hackathon/
  PLAN.md
  shopping-list.html
  scanner/
    run.py               # one command: starts server + opens both pages
    .env                 # ANTHROPIC_API_KEY (never shared or committed)
    requirements.txt
    app/
      main.py            # FastAPI routes, live video stream, push updates
      camera.py          # capture, card detection, stability + sharpness, warp
      card_template.py   # card layout: field names + box positions (for crops)
      schema.py          # Pydantic models: card fields, per-field confidence
      extract.py         # Claude call(s), double-read merge
      validate.py        # normalization + range rules + clinical alerts
      crm/
        base.py          # CrmClient interface (create_contact, add_screening, find_duplicate)
        mock_crm.py      # SQLite implementation (demo)
        salesforce.py    # simple_salesforce implementation (stretch)
    web/
      scanner.html       # live preview, status, review form
      crm.html           # Salesforce-style list + record page
      static/            # css/js/sounds
    eval/
      cards/             # test photos + ground-truth .json per card
      run_eval.py        # accuracy per field, % auto-accepted, avg time
```

---

## 4. Each stage in detail

### 4.1 Capture (`camera.py`)
- Open the C920 at 1920×1080. **Lock focus and exposure** once the holder distance is fixed, so nothing drifts between scans.
- **Find the card:** the holder fixes its position, so start from a fixed crop region. A contour search for the largest 4-sided shape is the fallback if the card shifts.
- **Auto-capture:** when a card is present and the image has been steady for about 0.7 s (low frame-to-frame difference), grab ~5 frames and keep the sharpest one (by a standard blur score).
- Also keep a **manual Scan button / spacebar** as a backup trigger.
- **Perspective-correct** the card into a flat rectangle, resize so the long edge is about 1568 px (the size Claude reads best at without wasted cost), and save it as a JPEG.
- **Feedback:** beep plus an on-screen flash on capture, and a "hold steady / too blurry / no card" status line.

### 4.2 Extract (`extract.py`, `schema.py`)
- **Model:** `claude-opus-5-5`, chosen for handwriting accuracy. Thinking effort starts at `medium`. We'll tune `low`/`medium` on our test cards: lower is faster and cheaper, and we keep it if accuracy holds.
- **Structured output:** `client.messages.parse(...)` with a Pydantic model. The API guarantees the response matches the schema, so there's no broken JSON.
- **Each field returns:**
  ```
  value:        string | null      (null = unreadable / blank)
  confidence:   "high" | "medium" | "low"
  alternatives: list[string]       (other plausible readings)
  note:         string | null      (e.g. "digit 3 or 8")
  ```
- **The prompt describes every field's expected format** (BP `###/##`, SpO₂ 70–100, 10-digit phone, etc.). It tells the model to **return null instead of guessing**, and to copy exactly what's written without "correcting" it.
- **Double read:** two calls run in parallel, so the wait isn't doubled. If the two values for a field disagree, that field's confidence drops to low and both readings appear as alternatives. This can be turned off in settings to halve the cost.
- **Refusal safety net:** server-side `fallbacks` are enabled, so if the model ever declines a request, the API automatically retries on a fallback model instead of failing mid-demo.
- **Error handling:** no internet or an API error shows a clear message and offers **manual entry**. The demo never just freezes.

### 4.3 Validate (`validate.py`)
| Field | Normalize | Flag if |
|---|---|---|
| Name | Trim, capitalize | Contains digits, or under 2 letters |
| Phone | Store as `(214) 555-0123` | Not 10 digits |
| Email | Lowercase | Fails the email format check |
| DOB | Store as `YYYY-MM-DD` | Invalid date or age not 0–110 |
| Blood pressure | Split into systolic/diastolic | Sys outside 70–250, dia outside 40–150, or sys ≤ dia |
| SpO₂ | Integer % | Outside 70–100 |
| Pulse | Integer bpm | Outside 30–220 |
| Temp | °F | Outside 93–108 |

- **Validation flag vs. clinical alert:** "flag" means *possible misread, please verify*. A separate **clinical alert** means *the reading is real but concerning* (e.g., BP ≥ 180/120 or SpO₂ < 92), and it sets **Needs Follow-Up** on the record. This is a useful feature for health fairs and a good one to show judges.
- The final status for each field is green (accepted), yellow (verify) or red (missing or unreadable).

### 4.4 Review screen (`scanner.html`)
- **Left side:** the captured card image. **Right side:** the form with every field, color-coded.
- Each yellow or red field shows a **zoomed crop of that box's handwriting** beside the input, plus one-click alternate readings.
- **Keyboard-first:** Tab jumps only between flagged fields, and Enter submits.
- An "Auto-accept when everything is green" toggle gives the fully hands-free demo moment.
- Field crop positions come from `card_template.py`, which we map once from the real card.

### 4.5 Mock CRM (`crm/`, `crm.html`)
- **Salesforce-shaped data**, so connecting the real thing later is a config change:
  - `Contact`: FirstName, LastName, Phone, Email, Birthdate, MailingPostalCode, …
  - `Health_Screening__c`: Contact__c, Screening_Date__c, Event_Name__c, Systolic_BP__c, Diastolic_BP__c, SpO2__c, Heart_Rate__c, Temperature__c, Needs_Follow_Up__c, Source_Image__c, Reviewed_By__c
- **Duplicate check:** a matching name plus phone attaches the new screening to the existing contact instead of creating a duplicate.
- **Pages:** a patient list view with search, a record page showing contact details and screening history, and a live "New record" panel where fields animate in as the scan completes.
- **Stats bar:** cards processed, average seconds per card, % auto-accepted, estimated minutes saved compared with manual entry.
- **Final field names** will match the real card and the clinic's Salesforce fields if we can get them.

### 4.6 Measuring accuracy (`eval/`)
- Collect 20–30 cards filled in by different people, including messy handwriting on purpose. Write the true values for each in a `.json` file.
- `run_eval.py` reports field-level accuracy, the **% of wrong values that were flagged** (the key safety number), % auto-accepted, average time and cost per card.
- We use it to tune effort level and prompt wording, and the real numbers go on a pitch slide.

---

## 5. Cost and speed (estimates; to be measured with `run_eval.py`)
- One read is about 3K input tokens (card image + instructions) and about 1–2K output tokens, which comes to **about $0.03–0.05 per read** on Opus 5.5.
- With double read that's **about $0.06–0.10 per card**. **Load $15–20 of API credit**, which covers 150+ cards of testing plus the demo.
- Expect about 5–15 s per card, with both reads running in parallel. Lower effort is faster. The UI shows a progress animation so the wait feels short.

---

## 6. Build schedule

| When | Team | Claude (me) |
|---|---|---|
| **Wed Nov 18** | Send card photos (blank + fake-filled), dimensions, field list. Install Python 3.12 + VS Code. Create the API key and add credit. | Scaffold the project, schema, mock CRM, extraction pipeline |
| **Thu Nov 19** | **Register the team (deadline 11:59 PM).** Fill out 20–30 test cards. Webcam arrives, print the holder. | Run the accuracy eval on phone photos and tune the prompt. Camera capture + auto-capture |
| **Fri Nov 20** | Final holder print. Full rehearsal on the demo laptop. | Review UI, validation, CRM animation, stats, polish. Record a **backup demo video** |
| **Sat Nov 21** | Demo! | Fixes + stretch goals |

**Stretch goals, only after the core demo works:** real Salesforce Developer Edition connection, batch mode for a stack of cards, CSV export, Arduino status LED.

---

## 7. Demo script (about 90 s)
1. **Problem:** "Hundreds of cards, hours of typing, transcription errors."
2. Slide a messy card into the holder. It beeps, and the fields fill into the CRM within seconds.
3. One field is yellow. The crop shows the scrawl; fix it in 2 seconds and press Enter.
4. A card with BP 185/122 triggers a **follow-up alert** on the record.
5. Show the stats bar and the accuracy results: "X% fields read correctly, Y% of errors caught for review, Z seconds per card vs ~2 min by hand."
6. Close with privacy and production notes: fake data in the demo; a real deployment would use encrypted storage, a HIPAA-compliant setup with the AI vendor, and the clinic's Salesforce.

---

## 8. Risks and backups
| Risk | Backup |
|---|---|
| Venue Wi-Fi drops | Phone hotspot; manual-entry mode; backup demo video |
| Webcam fails or is late | Phone as webcam (Phone Link / Camo / Iriun); upload-a-photo button |
| Glare or shadows at the venue | Open-sided holder; desk lamp or phone light; locked exposure |
| A misread during the live demo | That's the review screen working: flagged and fixed on the spot |
| API key leaks | Kept in `.env`, never shown on screen or shared |

---

## 9. Needed from the team
1. Photos of the real card (one blank, one with **fake** info) and its dimensions
2. Final list of fields on the card, plus clinic Salesforce field names if available
3. Python 3.12 + VS Code installed on the demo laptop
4. Anthropic API key with $15–20 credit
