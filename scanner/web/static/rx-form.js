// e-Prescribe form (visit page + patient chart).
// renderRxForm(container, { patient, encounterId?, providerId?, onSent(rx) })
// Without providerId, the form asks which provider is prescribing.

async function renderRxForm(container, { patient, encounterId = null, providerId = null, onSent }) {
  const ref = await reference();
  const allergies = (patient.allergies || "").split(";").map((a) => a.trim()).filter(Boolean);
  container.innerHTML = `
    <form class="rx-form" autocomplete="off"><div class="form-grid">
      ${providerId ? "" : `<div class="f s6"><label class="req">Prescriber</label><select name="provider_id">${ref.providers.map((p) =>
        `<option value="${p.id}">${esc(p.name)}, ${esc(p.credentials)}</option>`).join("")}</select></div>`}
      <div class="f s3"><label class="req">Medication</label><select name="drug" required>
        <option value="">Choose a medication…</option>
        ${ref.drugs.map((d) => `<option value="${esc(d.name)}">${esc(d.name)} (${esc(d.drug_class)})</option>`).join("")}</select></div>
      <div class="f s3"><label class="req">Strength</label><select name="strength" required><option value="">-</option></select></div>
      <div class="f s6"><label class="req">Directions (sig)</label><input name="sig" required placeholder="e.g. Take 1 tablet by mouth once daily"></div>
      <div class="f s1"><label class="req">Quantity</label><input name="quantity" type="number" min="1" max="999" value="30" required></div>
      <div class="f s1"><label>Refills</label><input name="refills" type="number" min="0" max="11" value="0"></div>
      <div class="f"><label class="req">Pharmacy</label><select name="pharmacy_id" required>${ref.pharmacies.map((ph) =>
        `<option value="${ph.id}" ${ph.id === patient.pharmacy_id ? "selected" : ""}>${esc(ph.name)}${ph.id === patient.pharmacy_id ? " (preferred)" : ""}</option>`).join("")}</select></div>
      <div class="f s6 rx-warning"></div>
    </div>
    <div class="rx-actions">
      <span class="form-error"></span>
      <span class="muted small">${ref.email_enabled ? "Also emailed to the demo pharmacy inbox ✉" : "Sent to the pharmacy inbox (email not set up)"}</span>
      <button type="submit" class="btn primary">Send to pharmacy ➜</button>
    </div></form>`;

  const form = container.querySelector("form");
  const warn = container.querySelector(".rx-warning");
  const err = container.querySelector(".form-error");
  let conflicts = [];

  form.drug.onchange = async () => {
    const d = ref.drugs.find((x) => x.name === form.drug.value);
    form.strength.innerHTML = d ? d.strengths.map((s) => `<option>${esc(s)}</option>`).join("") : `<option value="">-</option>`;
    if (d) { form.sig.value = d.sig; form.quantity.value = d.quantity; }
    conflicts = d ? (await api("/api/prescriptions/check", { method: "POST", body: { patient_id: patient.id, pharmacy_id: 1, drug: d.name } })).allergy_conflicts : [];
    warn.innerHTML = conflicts.length
      ? `<div class="alert urgent"><b>Allergy alert</b>${esc(patient.first_name)} is allergic to <b>${conflicts.map(esc).join(", ")}</b>.
         ${esc(d.name)} (${esc(d.drug_class)}) may cause a reaction. Choose another medication, or override with a reason.
         <div class="override-row"><label><input type="checkbox" name="override"> Override: I've reviewed the allergy</label>
         <input name="override_reason" placeholder="Reason (e.g. tolerated before)"></div></div>`
      : (allergies.length && d ? `<span class="badge green">✓ No allergy conflict</span> <span class="muted small">checked against: ${allergies.map(esc).join(", ")}</span>` : "");
  };

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
    const btn = form.querySelector('button[type="submit"]');
    btn.disabled = true; btn.textContent = "Sending…";
    try {
      const res = await api("/api/prescriptions", { method: "POST", body });
      const ph = ref.pharmacies.find((x) => x.id === body.pharmacy_id);
      toast(`${body.drug} sent to ${ph.name}${res.emailed ? " + emailed ✉" : ""} ✓`);
      onSent && onSent(res);
      form.reset(); form.drug.onchange();
    } catch (ex) {
      err.textContent = ex.message;
    } finally {
      btn.disabled = false; btn.textContent = "Send to pharmacy ➜";
    }
  });
}

const RX_STATUS = { sent: ["Sent", "blue"], received: ["Received by pharmacy", "amber"], filled: ["Filled", "green"], ready: ["Ready for pickup", "green"] };
function rxStatusBadge(rx) {
  const [label, cls] = RX_STATUS[rx.status] || [rx.status, ""];
  return `<span class="badge ${cls}">${label}</span>${rx.emailed ? ' <span class="badge" title="Emailed to the demo pharmacy inbox">✉ emailed</span>' : ""}`;
}
