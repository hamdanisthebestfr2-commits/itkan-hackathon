// AI after-visit summary card on the visit page (Track A5).
// setupAvs(box, { encId, patientName }): draft (auto on sign, or on demand, any language) -> edit -> send to the portal.

function setupAvs(box, { encId, patientName }) {
  let st = null, review = [], busy = false;

  async function load() {
    st = await api(`/api/encounters/${encId}/summary`);
    render();
  }

  function render() {
    const s = st.status, text = s === "sent" ? st.sent : st.draft;
    const langSel = `<select id="avsLang" title="Language for the patient">${st.languages.map((l) =>
      `<option ${l === st.language ? "selected" : ""}>${esc(l)}</option>`).join("")}</select>`;
    const head = `<h3>📝 After-visit summary <span class="muted small" style="text-transform:none;letter-spacing:0;font-weight:400">for ${esc(patientName)} · plain language · goes to their portal</span></h3>`;
    if (s === "drafting" || busy) {
      box.innerHTML = `${head}<div class="avs-busy"><span class="spinner"></span> AI is writing ${esc(patientName)}'s summary from the visit note…</div>`;
      return;
    }
    if (!text) {
      box.innerHTML = `${head}
        ${s === "failed" ? `<div class="warnbox">The AI couldn't draft it just now. Try again, or write it yourself below.</div>` : ""}
        <p class="muted small" style="margin:4px 0 10px">${st.signed ? "No summary yet." : "The AI drafts this automatically when you sign the visit. You can also draft it now."}</p>
        <div class="avs-actions">${langSel}<button class="btn primary small" id="avsDraft" type="button">✨ Draft summary</button>
          <button class="btn small" id="avsManual" type="button">Write it myself</button></div>`;
      box.querySelector("#avsDraft").onclick = draft;
      box.querySelector("#avsManual").onclick = () => { st.draft = " "; st.status = "draft"; render(); box.querySelector("#avsText").value = ""; box.querySelector("#avsText").focus(); };
      return;
    }
    box.innerHTML = `${head}
      ${s === "sent" ? `<div class="avs-sent">✓ Sent to ${esc(patientName)}'s patient portal · ${fmtDateTime(st.sent_at)}${st.language !== "English" ? ` · ${esc(st.language)}` : ""}</div>`
        : `<div class="aibox">AI draft${st.language !== "English" ? ` in ${esc(st.language)}` : ""}: read it and edit anything before sending. It only restates your note.</div>`}
      ${review.length && s !== "sent" ? `<div class="warnbox"><b>Check before sending:</b><ul style="margin:4px 0 0 18px;padding:0">${review.map((r) => `<li>${esc(r)}</li>`).join("")}</ul></div>` : ""}
      <textarea id="avsText" class="avs-text" spellcheck="true" ${st.language === "Arabic" || st.language === "Urdu" ? 'dir="rtl"' : ""}>${esc(text.trim())}</textarea>
      <div class="avs-actions">
        <button class="btn primary" id="avsSend" type="button" ${st.signed ? "" : 'disabled title="Sign the visit first: patients only see finished visits"'}>
          ${s === "sent" ? "Update in portal" : "Send to patient portal ➜"}</button>
        <button class="btn small" id="avsPrint" type="button">🖨 Print</button>
        <span class="sp"></span>${langSel}<button class="btn small" id="avsDraft" type="button">✨ Re-draft</button></div>
      ${st.signed ? "" : '<div class="muted small" style="margin-top:6px">Sign the visit to send it.</div>'}`;
    box.querySelector("#avsDraft").onclick = () => {
      if (box.querySelector("#avsText").value.trim() !== (text || "").trim() && !confirm("Replace your edits with a new AI draft?")) return;
      draft();
    };
    box.querySelector("#avsSend").onclick = send;
    box.querySelector("#avsPrint").onclick = () => {
      const w = window.open("", "_blank");
      w.document.write(`<title>After-visit summary</title><body style="font:15px/1.5 system-ui,sans-serif;max-width:680px;margin:32px auto;white-space:pre-wrap"${st.language === "Arabic" || st.language === "Urdu" ? ' dir="rtl"' : ""}><h2>Plano Community Clinic: after-visit summary</h2><p>${esc(patientName)}</p>${esc(box.querySelector("#avsText").value)}</body>`);
      w.document.close(); w.print();
    };
  }

  async function draft() {
    const language = box.querySelector("#avsLang").value;
    busy = true; render();
    try {
      const r = await api(`/api/encounters/${encId}/summary/draft`, { method: "POST", body: { language } });
      review = r.needs_review || [];
      st = r;
    } catch (e) { toast(e.message, "error"); await load(); }
    busy = false; render();
  }

  async function send() {
    const b = box.querySelector("#avsSend"); b.disabled = true;
    try {
      st = await api(`/api/encounters/${encId}/summary/send`, { method: "POST", body: { text: box.querySelector("#avsText").value } });
      toast(`Summary sent to ${patientName}'s portal ✓`);
      render();
    } catch (e) { toast(e.message, "error"); b.disabled = false; }
  }

  onEvent((ev) => {
    if (ev.type !== "summary_updated" || ev.encounter_id !== encId || busy) return;
    if (ev.needs_review) review = ev.needs_review;
    if (document.activeElement && document.activeElement.id === "avsText") return;   // don't clobber typing
    load();
  });
  load();
}
