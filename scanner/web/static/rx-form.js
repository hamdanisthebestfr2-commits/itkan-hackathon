// e-Prescribe form (visit page + patient chart).
// renderRxForm(container, { patient, encounterId?, providerId?, onSent(rx) })
// Without providerId, the form asks which provider is prescribing.
// Controlled substances (DEA schedule) switch to the EPCS flow: days' supply, PDMP review, two-factor signing.

async function renderRxForm(container, { patient, encounterId = null, providerId = null, onSent }) {
  const ref = await reference();
  const allergies = (patient.allergies || "").split(";").map((a) => a.trim()).filter(Boolean);
  const plain = ref.drugs.filter((d) => !d.schedule), controlled = ref.drugs.filter((d) => d.schedule);
  container.innerHTML = `
    <form class="rx-form" autocomplete="off"><div class="form-grid">
      ${providerId ? "" : `<div class="f s6"><label class="req">Prescriber</label><select name="provider_id">${ref.providers.map((p) =>
        `<option value="${p.id}">${esc(p.name)}, ${esc(p.credentials)}</option>`).join("")}</select></div>`}
      <div class="f s3"><label class="req">Medication</label><select name="drug" required>
        <option value="">Choose a medication…</option>
        <optgroup label="Medications">${plain.map((d) => `<option value="${esc(d.name)}">${esc(d.name)} (${esc(d.drug_class)})</option>`).join("")}</optgroup>
        <optgroup label="Controlled substances (EPCS, 2-factor signing)">${controlled.map((d) =>
          `<option value="${esc(d.name)}">${esc(d.name)} · ${esc(d.schedule)} (${esc(d.drug_class)})</option>`).join("")}</optgroup></select></div>
      <div class="f s3"><label class="req">Strength</label><select name="strength" required><option value="">-</option></select></div>
      <div class="f s6"><label class="req">Directions (sig)</label><input name="sig" required placeholder="e.g. Take 1 tablet by mouth once daily"></div>
      <div class="f s1"><label class="req">Quantity</label><input name="quantity" type="number" min="1" max="999" value="30" required></div>
      <div class="f s1"><label>Refills</label><input name="refills" type="number" min="0" max="11" value="0"></div>
      <div class="f s1 rx-days" hidden><label class="req">Days' supply</label><input name="days_supply" type="number" min="1" max="90" value="30"></div>
      <div class="f"><label class="req">Pharmacy</label><select name="pharmacy_id" required>${ref.pharmacies.map((ph) =>
        `<option value="${ph.id}" ${ph.id === patient.pharmacy_id ? "selected" : ""}>${esc(ph.name)}${ph.id === patient.pharmacy_id ? " (preferred)" : ""}</option>`).join("")}</select></div>
      <div class="f s6 rx-warning"></div>
      <div class="f s6 rx-controlled" hidden></div>
    </div>
    <div class="rx-2fa" hidden></div>
    <div class="rx-actions">
      <span class="form-error"></span>
      <span class="muted small rx-mailnote">${ref.email_enabled ? "Also emailed to the demo pharmacy inbox ✉" : "Sent to the pharmacy inbox (email not set up)"}</span>
      <button type="submit" class="btn primary">Send to pharmacy ➜</button>
    </div></form>`;

  const form = container.querySelector("form");
  const warn = container.querySelector(".rx-warning");
  const ctl = container.querySelector(".rx-controlled");
  const twofa = container.querySelector(".rx-2fa");
  const err = container.querySelector(".form-error");
  const submitBtn = form.querySelector('button[type="submit"]');
  let conflicts = [], drug = null, pdmpTimer = null;

  const isControlled = () => !!(drug && drug.schedule);
  const setButton = (text) => { submitBtn.textContent = text || (isControlled() ? "Sign with 2-factor & send ➜" : "Send to pharmacy ➜"); };

  form.drug.onchange = async () => {
    drug = ref.drugs.find((x) => x.name === form.drug.value) || null;
    form.strength.innerHTML = drug ? drug.strengths.map((s) => `<option>${esc(s)}</option>`).join("") : `<option value="">-</option>`;
    if (drug) { form.sig.value = drug.sig; form.quantity.value = drug.quantity; }
    twofa.hidden = true; twofa.innerHTML = "";
    container.querySelector(".rx-days").hidden = !isControlled();
    ctl.hidden = !isControlled();
    form.refills.disabled = isControlled() && drug.schedule === "C-II";
    if (isControlled()) {
      form.days_supply.value = drug.days || 30;
      if (drug.schedule === "C-II") form.refills.value = 0;
      form.refills.max = drug.schedule === "C-II" ? 0 : 5;
      loadPdmp();
    } else {
      form.refills.max = 11;
    }
    setButton();
    conflicts = drug ? (await api("/api/prescriptions/check", { method: "POST", body: { patient_id: patient.id, pharmacy_id: 1, drug: drug.name } })).allergy_conflicts : [];
    warn.innerHTML = conflicts.length
      ? `<div class="alert urgent"><b>Allergy alert</b>${esc(patient.first_name)} is allergic to <b>${conflicts.map(esc).join(", ")}</b>.
         ${esc(drug.name)} (${esc(drug.drug_class)}) may cause a reaction. Choose another medication, or override with a reason.
         <div class="override-row"><label><input type="checkbox" name="override"> Override: I've reviewed the allergy</label>
         <input name="override_reason" placeholder="Reason (e.g. tolerated before)"></div></div>`
      : (allergies.length && drug ? `<span class="badge green">✓ No allergy conflict</span> <span class="muted small">checked against: ${allergies.map(esc).join(", ")}</span>` : "");
  };
  ["strength", "quantity", "days_supply"].forEach((n) => form[n].addEventListener("input", () => {
    if (!isControlled()) return;
    clearTimeout(pdmpTimer); pdmpTimer = setTimeout(loadPdmp, 400);
  }));

  // ---------- PDMP (prescription-monitoring) report ----------
  async function loadPdmp() {
    const sched = drug.schedule;
    ctl.innerHTML = `<div class="epcs-box"><div class="epcs-hd">⚠ Controlled substance · DEA Schedule ${esc(sched)}</div>
      <div class="epcs-bd muted">Checking the state PDMP…</div></div>`;
    const r = await api(`/api/pdmp/${patient.id}`, { method: "POST", body: {
      drug: drug.name, strength: form.strength.value, quantity: Number(form.quantity.value), days_supply: Number(form.days_supply.value) } });
    const rules = sched === "C-II" ? "No refills allowed (C-II). Opioids limited to 7 days in this demo."
      : "Up to 5 refills within 6 months (C-III to C-V).";
    ctl.innerHTML = `<div class="epcs-box"><div class="epcs-hd">⚠ Controlled substance · DEA Schedule ${esc(sched)}
        <span class="sp"></span><span class="small" style="font-weight:400">${esc(rules)}</span></div>
      <div class="epcs-bd">
        <div class="small muted">PDMP report: ${esc(r.source)} · checked ${new Date(r.checked_at).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}</div>
        ${r.flags.map((f) => `<div class="alert ${f.level === "urgent" ? "urgent" : "follow_up"}"><b>${f.level === "urgent" ? "⛔ Risk" : "⚠ Caution"}</b>${esc(f.text)}</div>`).join("")}
        <div class="epcs-ind">${r.indicators.prescribers_90d} prescriber${r.indicators.prescribers_90d === 1 ? "" : "s"} · ${r.indicators.pharmacies_90d} pharmac${r.indicators.pharmacies_90d === 1 ? "y" : "ies"} (90 days)
          · active opioid: ${r.indicators.active_opioid ? "<b>yes</b>" : "no"} · active benzodiazepine: ${r.indicators.active_benzo ? "<b>yes</b>" : "no"}
          · daily MME incl. this Rx: <b>${r.indicators.daily_mme}</b></div>
        ${r.fills.length ? `<table class="data epcs-fills"><thead><tr><th>Filled</th><th>Drug</th><th>Qty / days</th><th>Prescriber</th><th>Pharmacy</th><th></th></tr></thead><tbody>
          ${r.fills.map((f) => `<tr><td>${fmtDate(f.filled)}</td><td>${esc(f.drug)} ${esc(f.strength)} <span class="badge">${esc(f.schedule)}</span></td>
            <td>${f.quantity} / ${f.days_supply}d</td><td>${esc(f.prescriber)}</td><td>${esc(f.pharmacy)}</td>
            <td>${f.active ? `<span class="badge amber">active</span>` : ""}</td></tr>`).join("")}</tbody></table>`
          : `<div class="badge green" style="margin:8px 0">✓ No controlled-substance fills in the last 12 months</div>`}
        <label class="epcs-check"><input type="checkbox" name="pdmp_reviewed"> I reviewed this PDMP report</label>
      </div></div>`;
  }

  // ---------- submit ----------
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    err.textContent = "";
    if (conflicts.length && !(form.override && form.override.checked)) {
      err.textContent = "Allergy conflict: choose another medication or tick override.";
      return;
    }
    if (conflicts.length && !form.override_reason.value.trim()) {
      err.textContent = "Add a reason for the allergy override.";
      return;
    }
    const body = {
      patient_id: patient.id, encounter_id: encounterId,
      provider_id: providerId || Number(form.provider_id.value),
      pharmacy_id: Number(form.pharmacy_id.value), drug: form.drug.value, strength: form.strength.value,
      sig: form.sig.value.trim() + (conflicts.length ? ` [Allergy override: ${form.override_reason.value.trim()}]` : ""),
      quantity: Number(form.quantity.value), refills: Number(form.refills.value || 0),
      override_allergy: conflicts.length > 0,
    };
    if (isControlled()) return startEpcs({ ...body, days_supply: Number(form.days_supply.value),
      pdmp_reviewed: !!(form.pdmp_reviewed && form.pdmp_reviewed.checked) });
    submitBtn.disabled = true; setButton("Sending…");
    try {
      const res = await api("/api/prescriptions", { method: "POST", body });
      done(body, res);
    } catch (ex) {
      err.textContent = ex.message;
    } finally {
      submitBtn.disabled = false; setButton();
    }
  });

  function done(body, res) {
    const ph = ref.pharmacies.find((x) => x.id === body.pharmacy_id);
    toast(`${body.drug} sent to ${ph.name}${res.emailed ? " + emailed ✉" : ""} ✓`);
    onSent && onSent(res);
    form.reset(); form.drug.onchange();
  }

  // ---------- EPCS two-factor signing ----------
  async function startEpcs(body) {
    if (!body.pdmp_reviewed) { err.textContent = "Tick “I reviewed this PDMP report” before signing."; return; }
    submitBtn.disabled = true; setButton("Checking…");
    let ch;
    try {
      ch = await api("/api/epcs/challenge", { method: "POST", body });
    } catch (ex) {
      err.textContent = ex.message;
      submitBtn.disabled = false; setButton();
      return;
    }
    submitBtn.hidden = true;
    twofa.hidden = false;
    twofa.innerHTML = `<div class="epcs-2fa">
      <div class="epcs-2fa-hd">🔐 Two-factor signing for a ${esc(ch.schedule)} controlled substance</div>
      <div class="small">${ch.sent_to ? `A 6-digit code was sent to <b>${esc(ch.sent_to)}</b> (the provider's device).`
        : `Email is off: demo code <b class="epcs-code">${esc(ch.dev_code)}</b>${ch.note ? ` (${esc(ch.note)})` : ""}`}</div>
      <div class="epcs-2fa-row">
        <label>Provider PIN <input name="epcs_pin" type="password" inputmode="numeric" maxlength="8" placeholder="PIN" autocomplete="off"></label>
        <label>Code from device <input name="epcs_code" inputmode="numeric" maxlength="6" placeholder="123456" autocomplete="one-time-code"></label>
        <button type="button" class="btn primary" data-epcs="sign">Sign &amp; send ➜</button>
        <button type="button" class="btn" data-epcs="cancel">Cancel</button>
      </div>
      <div class="small muted">Demo PIN: ${esc(ch.pin_hint)} · code expires in ${Math.round(ch.expires_in / 60)} minutes ·
        DEMO of DEA-style 2FA (something you know + something you have)</div></div>`;
    twofa.querySelector('[name="epcs_pin"]').focus();
    const reset = () => { twofa.hidden = true; twofa.innerHTML = ""; submitBtn.hidden = false; submitBtn.disabled = false; setButton(); };
    twofa.querySelector('[data-epcs="cancel"]').onclick = reset;
    twofa.querySelector('[data-epcs="sign"]').onclick = async () => {
      err.textContent = "";
      const btn = twofa.querySelector('[data-epcs="sign"]');
      btn.disabled = true; btn.textContent = "Signing…";
      try {
        const res = await api("/api/epcs/sign", { method: "POST", body: { request_id: ch.request_id,
          pin: twofa.querySelector('[name="epcs_pin"]').value, code: twofa.querySelector('[name="epcs_code"]').value } });
        reset();
        done(body, res);
      } catch (ex) {
        err.textContent = ex.message;
        btn.disabled = false; btn.textContent = "Sign & send ➜";
        if (/expired|Too many|not found/.test(ex.message)) reset();
      }
    };
  }
}

const RX_STATUS = { sent: ["Sent", "blue"], received: ["Received by pharmacy", "amber"], filled: ["Filled", "green"], ready: ["Ready for pickup", "green"] };
function rxStatusBadge(rx) {
  const [label, cls] = RX_STATUS[rx.status] || [rx.status, ""];
  return `${rx.schedule ? `<span class="badge red" title="Controlled substance, signed with 2-factor EPCS">${esc(rx.schedule)} · EPCS</span> ` : ""}` +
    `<span class="badge ${cls}">${label}</span>${rx.emailed ? ' <span class="badge" title="Emailed to the demo pharmacy inbox">✉ emailed</span>' : ""}`;
}
