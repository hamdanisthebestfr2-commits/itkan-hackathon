# Iris: Live Demo Script & Day-Of Guide
ITKAN AI Hackathon · Saturday Nov 21, 2026

The pitch itself (slides + what to say + the "why" behind every number) is in **`Iris Pitch Script.pdf`**.
The deck is at https://claude.ai/artifact/P5DDAiutEfjJCHZHRE7ztc (Share → Export for PowerPoint/PDF).
This file is the **live demo**: what to click, what to say, and what to do if something breaks.

**Tested:** this exact path was dry-run end to end with real AI on Nov 21 afternoon (all steps passed; Robert’s claim
paid $147.70, Aisha’s appeal approved, time saved 45 min → 1 hr 30 min).

**The one message of the demo: Iris saves time.** Every step shows a job that used to take minutes being done by AI
in seconds, with a person approving it.

---

## 1. Setup checklist (before judging)

**Hardware**
- [ ] Laptop charged, charger plugged in. Phone hotspot ready (the AI needs internet).
- [ ] **Plug in the Logitech C920 before starting Iris** (Iris picks it by name).
- [ ] Close Zoom/Teams/OBS: only one app can use the camera.
- [ ] The **Jhon Harzorwick card** ready (plus a spare fake card).

**Software**
- [ ] Close any old black `start.bat` windows → double-click `scanner\start.bat`.
- [ ] Press **Ctrl+F5** once in the browser so the new Iris look loads.
- [ ] Dashboard → scroll down → **Reset demo data**. This fills today’s schedule.
- [ ] Warm-up: scan the Jhon card once (camera + AI check) → **Reset demo data again**.
- [ ] **Window layout:**
  - **Left (big, main screen):** Iris staff app on the Dashboard.
  - **Right window, two tabs:**
    - **Tab 1: Pharmacy** (`/pharmacy`).
    - **Tab 2: Patient Portal**: Patient Portal → pick **Robert Nguyen** → **Visit summaries**.
  - Switching browser tabs doesn’t trigger the 2-second loading screen, only page changes do.
- [ ] Phone: Gmail open on the demo inbox (prescription emails arrive there).
- [ ] Gemini credits: check the balance at https://ai.studio/projects (one demo uses about 8 AI calls, a few cents).
- [ ] Browser zoom 100% (Ctrl+0). F11 full screen looks best on a projector.
- [ ] Copy the **backup transcript** (section 2, step 4) somewhere you can paste it from quickly (e.g. Notepad).

> The 2-second Iris loading screen appears on every page change. This demo uses only about 5 page changes on purpose.
> Use the pause: it’s a good moment to say your next sentence.

---

## 2. The live demo (about 4 minutes)

### Step 1 · Dashboard (0:00–0:15) · no clicks
**Say:** “This is Iris on a clinic morning. Up here: how much staff time the AI has already saved. Down here: today’s
patients, quality scores and the money. Let me show you where that time comes from.”

### Step 2 · Scan a paper card (0:15–1:00) · *page change 1*
1. Click **Scan intake card** (top right).
2. Hold the Jhon card in front of the camera. Green outline → hold still → **beep**.
   (No beep? Press **Space** or **Scan now**.)
3. The review screen appears in about 7 seconds.

**Say:** “Clinics and health fairs still use paper. We don’t make them stop. Two AI models read the handwriting at the
same time and check each other, about 7 seconds instead of 2 to 3 minutes of typing.”

4. Point at the yellow **BMI** field → click **Use calculated 35.5**.

**Say:** “It even caught a mistake on the card: it says BMI 24.9, but 5 foot 6 and 220 pounds is 35.5.”

5. Press **Enter** (Save to patient record).

**Say:** “He’s a patient now, with his vitals in the chart. Nobody typed anything.”

### Step 3 · Robert’s visit (1:00–2:30) · *page changes 2 and 3*
1. Click **Schedule** → click **Robert Nguyen** (1:00 PM, Annual physical) → **Check in & start visit**.
   The copay window opens (Iris checked his insurance: $20 copay) → **💵 Cash** → **Record $20.00 cash** → **Done**.
   The visit opens. *(In a hurry: **Skip, collect later**.)*

**Say (while paying):** “Check-in already knows his insurance is active and his copay is twenty dollars: no phone
call to the insurer.”

**Say:** “Robert came from a health fair with a blood pressure of 168 over 104. Iris already shows his care gaps on the
right: things insurers and Medicare score clinics on.”

2. **AI ambient notes.** Choose one:
   - **Live (most impressive):** click **Record the visit** → **Start recording**. Your partner plays Robert and you
     play the doctor for about 20 seconds (use the transcript below as your lines) → stop.
   - **Safe:** click the **Wispr Flow transcript** tab → paste the backup transcript → **✨ Write SOAP note**.

   Backup transcript:
   > Doctor: Hi Robert, I see the health fair flagged your blood pressure at 168 over 104. How have you been feeling?
   > Robert: Mostly fine, some headaches. I smoke about a pack a day and I want to quit.
   > Doctor: Today your blood pressure is still high. Let's start a nicotine patch, 21 milligrams a day, cut back on salt,
   > walk 30 minutes a day, and recheck your blood pressure in 4 weeks. I'll also order a cholesterol test.

3. When the draft appears → **Insert into visit note**.

**Say:** “The doctor just talked to the patient. The AI wrote the note. The doctor reads it and approves it.”

4. Care gaps: click **Add to note** on each open gap (3 clicks) → they turn green.

**Say:** “Three quality gaps closed in three clicks, documented properly.”

5. **Prescriptions this visit:** choose **Nicotine patch** → **Send to pharmacy ➜**. Point at the **right window (Pharmacy tab)** and
   your phone.

**Say:** “It goes straight to the pharmacy… there it is, and the email just arrived on my phone.”

6. *(Optional)* **🧪 Lab orders:** tick **Lipid panel** → **Order selected tests** → **Result now (demo)**.
7. Click **Sign & complete visit** → OK.

**Say:** “Signing does three things at once: it locks the note, the AI codes the visit for billing, and the AI writes
Robert a summary in plain language.”

8. In **📝 After-visit summary**: pick **Spanish** → **✨ Re-draft** → **Send to patient portal**. Switch the right
   window to the **Portal tab**: the summary appears.

**Say:** “Patients get a summary they can actually read, in their own language, in seconds.”

### Step 4 · Ask the chart (2:30–2:50) · no page change
Click **✨ Ask the chart** (bottom right) → **Summarize this patient before the visit**. Click one blue source chip.

**Say:** “Doctors spend ages hunting through charts. Ask in plain English and get an answer in about a second, with a
link to where every fact came from. If it’s not in the chart, it says so.”

### Step 5 · Billing (2:50–3:40) · *page change 4*
1. In the green bar at the top of the visit: **Open claim →**.
2. Hover a code: the words in the note that justify it light up. Click **Accept all high-confidence** → **Approve
   claim** (if the **Claim checker** shows an issue, click its one-click fix first: “it catches what gets claims
   rejected before they’re sent”) → **Submit to insurer**.

**Say:** “Coding a visit by hand takes a billing person about 7 minutes. The AI does it in seconds, quoting the note,
using only real codes. And… paid.”

3. In the claims list on the left, click **Aisha Khan** (Partly denied) → **🤖 Fight this denial** → **Submit appeal**.

**Say:** “Denials are where clinics lose money and hours. The AI explains it, checks the note and writes the appeal.
Approved: fifty-two fifty back. If a denial is correct, it says so instead.”

### Step 6 · Close on the Dashboard (3:40–4:00) · *page change 5*
Click **Dashboard**.

**Say:** “The time-saved number went from 45 minutes to about an hour and a half while we talked. That’s Iris: AI doing the paperwork so clinics get their time
back, at a flat price instead of a cut of their revenue.”

**Short on time? Cut in this order:** the lab order (3.6), the Spanish re-draft (3.8, just send English), Ask the chart
(step 4), the appeal (5.3).

---

## 3. If something goes wrong

| Problem | What to do (stay calm, it’s part of the story) |
|---|---|
| Card won’t auto-scan | Press **Space** (or **Scan now**). Or **Upload photo** with a phone picture of the card. |
| The AI misreads a field | “That’s exactly why a person reviews it.” Fix it and continue. |
| “AI unavailable” / “credits depleted” | Switch to the phone hotspot if Wi-Fi dropped. If it says credits: add credits at ai.studio/projects. Meanwhile type the note, add codes with the search box on the claim, or play the backup video. |
| Recording doesn’t work | Use the **Wispr Flow transcript** tab with the backup transcript. |
| Camera shows the laptop camera | Choose **HD Pro Webcam C920** in the camera drop-down on Scan Intake. |
| Pharmacy/portal didn’t update | Click the tab again (it updates live; at worst press F5 in that window). |
| Loading screen seems stuck | It lifts by itself within 4 seconds. If the page is blank, check that the black start.bat window is still open. |
| Iris is frozen or closed | Close the black window, double-click `start.bat` again. Nothing is lost. |
| Schedule looks empty / Robert already done | Dashboard → **Reset demo data** (wait for it, then start over at step 1). |
| Total disaster | Play the **backup video** (section 5). |

---

## 4. Judge questions

Full answers are in **`Iris Pitch Script.pdf`** → Sections B and C. The short versions:
- **Why so cheap?** AI does the billing work that percentage-based companies pay people to do, and software costs
  almost nothing extra per clinic.
- **Why $499 per provider?** Real deployment costs (HIPAA hosting, AI usage, pharmacy/claims network fees, DEA identity
  checks, certification, support) grow per doctor, not per dollar earned. It’s still about 70–80% less than athenaOne.
- **Old-school clinics won’t adopt AI.** Iris doesn’t make them change: paper cards still work, the screens are normal,
  and a person approves every AI suggestion.
- **Is the AI accurate?** It shows its evidence (quotes, sources), uses only approved codes, double-reads cards, and a
  person approves everything.
- **HIPAA?** Demo = fictional patients only. Production = HIPAA hosting with business associate agreements.
- **What’s real?** The whole software flow and the AI. Simulated: pharmacy network, insurers, lab, prescription
  monitoring.

---

## 5. Backup video (record after one clean rehearsal)
1. Reset demo data, then run the demo once while recording.
2. **Windows:** **Win + Alt + R** (Xbox Game Bar) starts/stops recording the browser window, or use OBS → Display
   Capture → Start Recording.
3. Trim in **Clipchamp** (built into Windows) to about 3–4 minutes. Save it on the desktop *and* your phone.

---

## 6. After the hackathon
- Delete the Gemini API key in Google AI Studio and the Gmail App Password in your Google account (both were shared in
  chat). Turn off auto-reload on the Gemini credits if you turned it on.
