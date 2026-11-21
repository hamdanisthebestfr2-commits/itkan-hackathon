# FlatRate Health: Demo Script & Day-Of Guide
ITKAN AI Hackathon · Saturday Nov 21, 2026 · *(product name is a placeholder; swap it in `scanner/web/static/shell.js`)*

---

## 1. Morning checklist (do this before judging starts)

**Hardware**
- [ ] Laptop charged + charger plugged in
- [ ] **Plug in the Logitech C920 before starting the app** (the app finds it by name)
- [ ] Close Zoom/Teams/OBS. Only one app can use the camera at a time
- [ ] Card holder set up: card fills most of the camera view with dark background around it
- [ ] 2-3 filled-in **fake** intake cards ready (the Jhon Harzorwick card + spares)
- [ ] Phone hotspot ready in case venue Wi-Fi drops (the AI needs internet)

**Software**
- [ ] Close any old black `start.bat` windows, then double-click `scanner\start.bat`
- [ ] Dashboard opens → click **↺ Reset demo data** (bottom right). This fills **today's** schedule
- [ ] Open a **second browser window** with the **Pharmacy** page and put it side by side (or on a 2nd screen)
- [ ] Pharmacy → **Send test email** → check that the email arrived on your phone (ibrahimosman123cc@gmail.com)
- [ ] Warm-up: scan the Jhon card once to confirm camera + AI work → then **Reset demo data again**
- [ ] Open Gmail on your phone so you can show the prescription email arriving
- [ ] Browser zoom 100% (Ctrl+0); full screen (F11) looks cleanest on a projector

**AI limit reminder:** on the free Gemini plan each AI model allows only about 20 requests a day. One full demo uses
about 5 requests. The app automatically switches to backup models, but **don't do lots of practice scans on demo day.**
If billing is turned on for the Gemini key, this limit goes away.

---

## 2. The 3-minute demo (clicks + what to say)

> **Opening line (15 s):** "Small clinics pay companies like athenaOne **4-8% of everything they collect**, which is
> $65K-$185K a year for a 3-doctor clinic, mostly for billing paperwork. We built **FlatRate Health**: the whole
> clinic system, with AI doing the paperwork, for a flat monthly price."

| Time | Click | Say |
|---|---|---|
| 0:15 | **Dashboard** is on screen | "This is the clinic's day: schedule, patients, money, and how much staff time AI has saved." |
| 0:25 | **Scan intake card** → hold the Jhon card in the holder → beep | "Health fairs collect hundreds of handwritten cards. Watch: we just hold it up." |
| 0:40 | Review screen appears | "Two AI models read it independently and cross-check each other. Anything uncertain turns yellow, with a zoom of the handwriting." |
| 0:50 | Point at the yellow **BMI** field → click **Use calculated 35.5** | "It even caught a mistake *on the card*: BMI says 24.9, but 5'6" and 220 lbs is 35.5." |
| 1:00 | **Save to patient record** → **Open patient chart** | "He's now a registered patient: no typing." |
| 1:05 | **Edit** → add insurance (Bluebonnet, any member ID), pharmacy → Save → **Start visit** → choose provider | "Now he sees the doctor." |
| 1:15 | **Use vitals from screening** → **🎤 Dictate** (or type) the note | "The doctor just talks. The vitals came straight from the card." |
| 1:30 | Prescribe **Nicotine patch** → **Send to pharmacy** | "One click: it goes to the pharmacy…" → **point at the pharmacy window + phone email** → "…instantly." |
| 1:45 | **Sign & complete visit** → **Open claim** | "The moment it's signed, AI codes the visit for billing." |
| 1:55 | Hover a code (evidence lights up) → **Accept all** | "Every code quotes the exact sentence that justifies it, and it can only use real codes from an approved list. A human approves." |
| 2:05 | Point at the **Claim checker** → **Approve claim** → **Submit to insurer** | "The checker catches what gets claims rejected *before* sending. And… paid." |
| 2:20 | Open **Aisha Khan's** claim → **🤖 Fight this denial** | "When insurers deny, this is where clinics lose money. AI reads the denial, the insurer's policy and the note…" |
| 2:30 | Show the recommendation + letter → **Submit appeal** | "…and writes the appeal. Approved: $52.50 recovered. And when a denial is *correct*, it says so and recommends writing it off. It's honest." |
| 2:45 | **Savings** page → move the providers slider | "A 3-doctor clinic saves about $79,000 a year. The more a clinic earns, the more a percentage takes; ours stays flat." |
| 2:55 | **Dashboard** | "And the time-saved number just went up while we talked." |

> **Closing line:** "Scanning, charting, e-prescribing, billing and denials in one system, with AI that shows
> its work and a human who approves it."

---

## 3. If something goes wrong

| Problem | What to do (stay calm, it's part of the story) |
|---|---|
| Card won't auto-scan | Press **Space** (or **Scan now**). Or **Upload photo** with a phone picture of the card |
| AI misreads a field | "That's exactly why the review screen exists": fix it and continue |
| "AI daily limit reached" / AI busy | Say: "We're on the free AI tier; in production this is a paid key." Type codes by hand on the Billing page (search box), or switch to the backup video |
| Wi-Fi drops | Switch to the phone hotspot. Everything except AI and email works offline |
| Camera not showing | Pick **HD Pro Webcam C920** in the camera dropdown; replug it and restart `start.bat` |
| App frozen / closed | Close the black window, double-click `start.bat` again. Data is saved, nothing is lost |
| Schedule looks empty | Dashboard → **Reset demo data** |
| Total disaster | Play the **backup video** (section 6) |

---

## 4. Likely judge questions

- **"Is this HIPAA compliant?"** Not yet; it's a demo with fictional patients. Production would run on HIPAA-eligible
  hosting with signed BAAs (including the AI provider, e.g. Google Cloud Vertex AI or Anthropic enterprise), encryption,
  access logs and user logins. We never put real patient data into the free AI tier.
- **"How accurate is it?"** On our test card the scanner read **25/25 fields** correctly. Uncertain fields are flagged
  instead of guessed, and two AI models cross-check each other. The AI coder chose the correct codes for every test visit after
  we taught it the official "2 of 3" visit-level rule. *(Small test set: say so honestly. More test cards = stronger numbers; see section 7.)*
- **"What if the AI makes up a code or a fact?"** It can only choose from an approved code list (unknown codes are
  removed), every code must quote the note (quotes not found are flagged), and a human approves every code and every appeal.
- **"Isn't AI billing risky (fraud/upcoding)?"** We designed against it: the claim checker *never* adds a diagnosis
  just to get paid; it only links what the doctor documented, or removes the charge.
- **"Is the insurer/pharmacy real?"** Simulated. Next step: a claims clearinghouse (e.g. Availity) for real claims and
  Surescripts for real e-prescriptions. The data is already in standard shapes (CMS-1500, CARC denial codes).
- **"Why is your price flat? How do you make money?"** AI does most of the billing work that percentage-based companies
  pay people to do, so our cost doesn't grow with the clinic's revenue. The demo price is $499/provider/month *(team: confirm your number)*.
- **"Competitors?"** athenaOne, eClinicalWorks, Tebra (full systems); AI billing startups like RapidClaims, Arintra,
  Amperos (mostly target bigger groups). We combine the full clinic system + AI billing for **small** clinics.
- **"What does the AI cost to run?"** A fraction of a cent per request; about 5 requests per patient visit end-to-end.

---

## 5. Pitch slides (6 slides)
1. **Problem:** small clinics pay 4-8% of collections ($65K-$185K/yr for 3 providers) + hours of typing intake forms.
2. **Solution:** FlatRate Health: one system (intake → schedule → visit → e-Rx → billing) with AI doing the paperwork.
3. **Demo** (live).
4. **AI with guardrails:** two-model cross-check, approved code lists, evidence quotes, human approval, honest denial advice, no upcoding.
5. **Results & savings:** 25/25 fields on the test card · full workflow ~40 seconds · $79K/yr saved for a 3-provider clinic.
6. **Next steps:** clearinghouse + Surescripts integrations, HIPAA hosting, pilot with a local clinic. Team slide.

---

## 6. Record a backup video (do this tonight or early morning)
1. Reset demo data, then run the whole demo once while recording.
2. **Windows:** press **Win + Alt + R** (Xbox Game Bar) to start/stop recording the browser window. Or use **OBS**
   (already installed): add "Display Capture" → Start Recording.
3. Trim in **Clipchamp** (built into Windows). Keep it ~3 minutes. Put the file on the desktop *and* your phone.

---

## 7. Optional, if time allows
- Fill **10-15 more fake cards** in different handwriting, photograph them, and put them in `scanner\eval\cards\`
  (copy `card01.json` as the answer key) → run `scanner\.venv\Scripts\python.exe scanner\eval\run_eval.py` for
  real accuracy numbers for slide 5.
- Decide the real **product name** and **price**.

## 8. After the hackathon
- Delete the Gemini API key in Google AI Studio and the Gmail App Password in your Google account (both were shared in chat).
