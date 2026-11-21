// AI Ambient Notes panel for the visit page.
// setupAmbient(container, { encId, onInsert(noteText) })
// Two ways in: record the conversation in the browser, or type/dictate a transcript (Wispr Flow: double-tap Caps Lock).

(function () {
  const css = `
  .amb-tabs { display: flex; gap: 6px; margin-bottom: 12px; flex-wrap: wrap; }
  .amb-tab { border: 1px solid var(--border); background: #fff; border-radius: 999px; padding: 6px 14px; cursor: pointer; font-size: 14px; }
  .amb-tab.on { background: #0b2545; border-color: #0b2545; color: #fff; }
  .amb-rec { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
  .amb-big { font-size: 15px; padding: 10px 18px; }
  .amb-big.live { background: #e5484d; border-color: #e5484d; color: #fff; animation: ambpulse 1.4s infinite; }
  @keyframes ambpulse { 50% { opacity: .8; } }
  .amb-timer { font-variant-numeric: tabular-nums; font-weight: 700; font-size: 18px; min-width: 56px; }
  .amb-meter { width: 160px; height: 8px; background: #eef1f5; border-radius: 4px; overflow: hidden; }
  .amb-meter div { height: 100%; width: 0; background: #1f8a4c; transition: width .08s; }
  .amb-hint { font-size: 13px; color: var(--muted); margin-top: 8px; }
  .amb-ta { width: 100%; min-height: 130px; border: 1px dashed #9aa4b1; border-radius: 8px; padding: 10px; font: inherit; font-size: 14px; resize: vertical; }
  .amb-ta:focus { outline: 2px solid #6d3fd6; border-style: solid; }
  .amb-busy { display: flex; gap: 10px; align-items: center; padding: 12px; background: #f3efff; border-radius: 8px; color: #4b2aa8; font-weight: 600; margin-top: 12px; }
  .amb-spin { width: 16px; height: 16px; border: 3px solid #d6caff; border-top-color: #6d3fd6; border-radius: 50%; animation: ambspin .8s linear infinite; }
  @keyframes ambspin { to { transform: rotate(360deg); } }
  .amb-draft { margin-top: 14px; border: 2px solid #c9b8ff; border-radius: 10px; overflow: hidden; }
  .amb-draft .hd { background: linear-gradient(90deg, #6d3fd6, #8b5cf6); color: #fff; padding: 8px 12px; font-weight: 700; display: flex; gap: 8px; align-items: center; }
  .amb-draft .bd { padding: 12px 14px; font-size: 14px; }
  .amb-sec { margin-bottom: 10px; } .amb-sec b { display: inline-block; width: 22px; color: #6d3fd6; }
  .amb-sec div { white-space: pre-wrap; margin-left: 22px; margin-top: -19px; }
  .amb-review { background: var(--check-bg); color: var(--check); border-radius: 6px; padding: 8px 10px; font-size: 13px; margin: 8px 0; }
  .amb-tr { font-size: 13px; color: #52514e; white-space: pre-wrap; max-height: 160px; overflow: auto; background: #fafbfc; border-radius: 6px; padding: 8px; }
  .amb-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }`;
  const style = document.createElement("style");
  style.textContent = css;
  document.head.appendChild(style);

  window.setupAmbient = function (box, { encId, onInsert }) {
    let mode = "record", rec = null, stream = null, chunks = [], timer = null, t0 = 0, meterRaf = null, draft = null, busy = false;

    function render() {
      box.innerHTML = `
        <h3>🎙 AI Ambient Notes <span class="sp"></span><span class="badge" style="background:#ede7ff;color:#6d3fd6">AI draft · you review</span></h3>
        <div class="amb-tabs">
          <button type="button" class="amb-tab ${mode === "record" ? "on" : ""}" data-mode="record">🎙 Record the visit</button>
          <button type="button" class="amb-tab ${mode === "wispr" ? "on" : ""}" data-mode="wispr">⌨ Wispr Flow transcript</button>
        </div>
        ${mode === "record" ? `
          <div class="amb-rec">
            <button type="button" class="btn amb-big ${rec ? "live" : "primary"}" id="ambRecBtn">${rec ? "■ Stop & write note" : "● Start recording"}</button>
            <span class="amb-timer" id="ambTimer"></span>
            <div class="amb-meter" title="Microphone level"><div id="ambLevel"></div></div>
          </div>
          <div class="amb-hint">Let the patient know the visit is being recorded. Talk normally; AI writes the note when you stop. (Max ~9 min for the demo.)</div>`
        : `
          <textarea class="amb-ta" id="ambTranscript" placeholder="Click here, then double-tap Caps Lock to start Wispr Flow and talk through the visit (or paste a transcript). Double-tap again to stop."></textarea>
          <div class="amb-actions"><button type="button" class="btn primary" id="ambWriteBtn">✨ Write SOAP note</button>
            <span class="amb-hint" style="margin:0;align-self:center">Wispr Flow types into whatever box is selected.</span></div>`}
        ${busy ? `<div class="amb-busy"><div class="amb-spin"></div>${busy}</div>` : ""}
        ${draft ? draftHtml() : ""}`;
      box.querySelectorAll("[data-mode]").forEach((b) => b.onclick = () => { if (!rec) { mode = b.dataset.mode; render(); } });
      if ($("ambRecBtn")) $("ambRecBtn").onclick = () => (rec ? stopRecording() : startRecording());
      if ($("ambWriteBtn")) $("ambWriteBtn").onclick = fromTranscript;
      if ($("ambInsert")) $("ambInsert").onclick = insert;
      if ($("ambDiscard")) $("ambDiscard").onclick = () => { draft = null; render(); };
    }

    function draftHtml() {
      const sec = (k, label) => draft[k] ? `<div class="amb-sec"><b>${label}</b><div>${esc(draft[k])}</div></div>` : "";
      return `<div class="amb-draft"><div class="hd">✨ AI note draft <span style="flex:1"></span><span class="small" style="font-weight:400;opacity:.85">review before inserting</span></div><div class="bd">
        ${sec("subjective", "S:")}${sec("objective", "O:")}${sec("assessment", "A:")}${sec("plan", "P:")}
        ${draft.patient_instructions ? `<div class="amb-sec"><b>🗒</b><div><i>Patient instructions:</i> ${esc(draft.patient_instructions)}</div></div>` : ""}
        ${draft.needs_review && draft.needs_review.length ? `<div class="amb-review">⚠ <b>Check before signing:</b> ${draft.needs_review.map(esc).join(" · ")}</div>` : ""}
        <details><summary class="small muted" style="cursor:pointer">Show transcript</summary><div class="amb-tr">${esc(draft.transcript)}</div></details>
        <div class="amb-actions"><button type="button" class="btn primary" id="ambInsert">Insert into visit note</button>
          <button type="button" class="btn" id="ambDiscard">Discard</button></div></div></div>`;
    }

    function noteText() {
      const parts = [["S", draft.subjective], ["O", draft.objective], ["A", draft.assessment], ["P", draft.plan]]
        .filter(([, v]) => v && v.trim()).map(([k, v]) => `${k}: ${v.trim()}`);
      if (draft.patient_instructions) parts.push(`Patient instructions: ${draft.patient_instructions.trim()}`);
      parts.push("(Drafted by AI from the visit conversation; reviewed by the provider.)");
      return parts.join("\n");
    }

    function insert() {
      onInsert(noteText());
      draft = null;
      render();
      toast("AI draft inserted. Review and edit before signing");
    }

    // ---------- recording ----------
    async function startRecording() {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
      } catch (e) {
        toast("Microphone blocked. Allow it in the browser's address bar", "error");
        return;
      }
      chunks = [];
      rec = new MediaRecorder(stream);
      rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
      rec.start(1000);
      t0 = Date.now();
      draft = null;
      render();
      timer = setInterval(() => {
        const s = Math.floor((Date.now() - t0) / 1000);
        if ($("ambTimer")) $("ambTimer").textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
        if (s >= 540) stopRecording();   // stay under the AI's inline audio limit
      }, 250);
      const ctx = new AudioContext(), an = ctx.createAnalyser();
      ctx.createMediaStreamSource(stream).connect(an);
      const buf = new Uint8Array(an.fftSize);
      const tick = () => {
        an.getByteTimeDomainData(buf);
        let peak = 0;
        for (const v of buf) peak = Math.max(peak, Math.abs(v - 128));
        if ($("ambLevel")) $("ambLevel").style.width = Math.min(100, peak / 64 * 100) + "%";
        meterRaf = requestAnimationFrame(tick);
      };
      tick();
      rec._ctx = ctx;
    }

    async function stopRecording() {
      if (!rec) return;
      clearInterval(timer);
      cancelAnimationFrame(meterRaf);
      const r = rec;
      rec = null;
      await new Promise((res) => { r.onstop = res; r.stop(); });
      stream.getTracks().forEach((t) => t.stop());
      r._ctx.close();
      busy = "Listening to the recording and writing the note…";
      render();
      try {
        const wav = await toWav16k(new Blob(chunks, { type: r.mimeType }));
        const fd = new FormData();
        fd.append("file", new File([wav], "visit.wav", { type: "audio/wav" }));
        const res = await fetch(`/api/encounters/${encId}/ambient/audio`, { method: "POST", body: fd });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "AI request failed");
        draft = data;
      } catch (e) {
        toast(e.message, "error");
      }
      busy = false;
      render();
    }

    async function fromTranscript() {
      const text = $("ambTranscript").value.trim();
      if (text.length < 20) { toast("Dictate or paste the conversation first", "error"); $("ambTranscript").focus(); return; }
      busy = "Writing the note from the transcript…";
      render();
      $("ambTranscript").value = text;
      try {
        draft = await api(`/api/encounters/${encId}/ambient/transcript`, { method: "POST", body: { transcript: text } });
      } catch (e) {
        toast(e.message, "error");
      }
      busy = false;
      render();
      if ($("ambTranscript")) $("ambTranscript").value = text;
    }

    render();
  };

  // Decode whatever the browser recorded (webm/opus) and re-encode as 16 kHz mono 16-bit WAV,
  // a format the AI accepts and small enough to send inline (~32 KB per second).
  async function toWav16k(blob) {
    const ctx = new AudioContext();
    const decoded = await ctx.decodeAudioData(await blob.arrayBuffer());
    ctx.close();
    const rate = 16000, len = Math.ceil(decoded.duration * rate);
    const off = new OfflineAudioContext(1, len, rate);
    const src = off.createBufferSource();
    src.buffer = decoded;
    src.connect(off.destination);
    src.start();
    const pcm = (await off.startRendering()).getChannelData(0);
    const buf = new ArrayBuffer(44 + pcm.length * 2), v = new DataView(buf);
    const str = (o, s) => [...s].forEach((c, i) => v.setUint8(o + i, c.charCodeAt(0)));
    str(0, "RIFF"); v.setUint32(4, 36 + pcm.length * 2, true); str(8, "WAVE"); str(12, "fmt ");
    v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true); v.setUint32(24, rate, true);
    v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true); str(36, "data");
    v.setUint32(40, pcm.length * 2, true);
    for (let i = 0; i < pcm.length; i++) v.setInt16(44 + i * 2, Math.max(-1, Math.min(1, pcm[i])) * 0x7fff, true);
    return new Blob([buf], { type: "audio/wav" });
  }
})();
