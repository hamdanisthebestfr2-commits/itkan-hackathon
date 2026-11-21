// Register / edit patient form (used by the Patients list and the patient chart).
// openPatientForm(existingPatient | null, onSaved(patientId))

const US_STATES = "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split(" ");

async function openPatientForm(p, onSaved) {
  const ref = await reference();
  const v = (k) => esc(p ? p[k] ?? "" : "");
  const opt = (list, sel, label = (x) => x.name) =>
    `<option value="">-</option>` + list.map((x) => `<option value="${x.id}" ${x.id === sel ? "selected" : ""}>${esc(label(x))}</option>`).join("");
  const field = (key, label, { span = "", type = "text", req = false, ph = "" } = {}) =>
    `<div class="f ${span}"><label class="${req ? "req" : ""}" for="pf_${key}">${label}</label>
     <input id="pf_${key}" name="${key}" type="${type}" value="${v(key)}" placeholder="${ph}" ${req ? "required" : ""}></div>`;

  const m = openModal(`
    <div class="modal-head"><h2>${p ? "Edit patient" : "Register new patient"}</h2><button class="x" onclick="closeModal()">×</button></div>
    <form id="patientForm" autocomplete="off">
    <div class="modal-body"><div class="form-grid">
      <div class="form-section">Demographics</div>
      ${field("first_name", "First name", { req: true })}
      ${field("last_name", "Last name", { req: true })}
      ${field("dob", "Date of birth", { type: "date", span: "s1" })}
      <div class="f s1"><label for="pf_sex">Sex</label><select id="pf_sex" name="sex">
        <option value=""></option>${Object.entries(SEX).map(([k, l]) => `<option value="${k}" ${p && p.sex === k ? "selected" : ""}>${l}</option>`).join("")}
      </select></div>

      <div class="form-section">Contact</div>
      ${field("phone", "Phone", { type: "tel", ph: "214-555-0100" })}
      ${field("email", "Email", { type: "email", span: "s3" })}
      <div class="f s1"></div>
      ${field("address", "Street address", { span: "s3" })}
      ${field("city", "City", { span: "s1" })}
      <div class="f s1"><label for="pf_state">State</label><select id="pf_state" name="state">
        <option value=""></option>${US_STATES.map((s) => `<option ${(p ? p.state : "TX") === s ? "selected" : ""}>${s}</option>`).join("")}
      </select></div>
      ${field("zip", "ZIP", { span: "s1" })}

      <div class="form-section">Insurance</div>
      <div class="f"><label for="pf_payer_id">Insurance plan</label><select id="pf_payer_id" name="payer_id">${opt(ref.payers, p && p.payer_id)}</select></div>
      ${field("member_id", "Member ID")}
      ${field("group_number", "Group #")}

      <div class="form-section">Pharmacy &amp; clinical</div>
      <div class="f s3"><label for="pf_pharmacy_id">Preferred pharmacy</label><select id="pf_pharmacy_id" name="pharmacy_id">${opt(ref.pharmacies, p && p.pharmacy_id, (x) => `${x.name} (${x.address})`)}</select></div>
      ${field("allergies", "Allergies", { span: "s3", ph: "e.g. Penicillin; Latex (separate with ;)" })}
      ${field("conditions", "Medical conditions", { span: "s3", ph: "e.g. Hypertension; Asthma" })}
      ${field("medications", "Current medications", { span: "s3", ph: "e.g. Lisinopril 10 mg daily" })}
    </div></div>
    <div class="modal-foot">
      <span class="form-error" id="pfError"></span>
      <button type="button" class="btn" onclick="closeModal()">Cancel</button>
      <button type="submit" class="btn primary">${p ? "Save changes" : "Register patient"}</button>
    </div>
    </form>`, { wide: true });

  m.querySelector("#patientForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = {};
    new FormData(e.target).forEach((val, key) => data[key] = String(val).trim() || null);
    for (const k of ["payer_id", "pharmacy_id"]) data[k] = data[k] ? Number(data[k]) : null;
    const err = validatePatient(data, ref);
    if (err) { $("pfError").textContent = err; return; }
    try {
      const res = p ? await api(`/api/patients/${p.id}`, { method: "PUT", body: data })
                    : await api("/api/patients", { method: "POST", body: data });
      closeModal();
      toast(p ? "Patient updated" : `${data.first_name} ${data.last_name} registered ✓`);
      onSaved && onSaved(res.id);
    } catch (ex) {
      $("pfError").textContent = ex.message;
    }
  });
}

function validatePatient(d, ref) {
  if (!d.first_name || !d.last_name) return "First and last name are required.";
  if (d.dob) {
    const dob = new Date(d.dob + "T00:00");
    if (dob > new Date()) return "Date of birth can't be in the future.";
    if (new Date().getFullYear() - dob.getFullYear() > 120) return "Check the date of birth year.";
  }
  if (d.phone) {
    const digits = d.phone.replace(/\D/g, "").replace(/^1(?=\d{10}$)/, "");
    if (digits.length !== 10) return "Phone number should have 10 digits.";
    d.phone = `${digits.slice(0, 3)}-${digits.slice(3, 6)}-${digits.slice(6)}`;
  }
  if (d.email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(d.email)) return "Email address doesn't look right.";
  if (d.zip && !/^\d{5}(-\d{4})?$/.test(d.zip)) return "ZIP should be 5 digits.";
  const payer = ref.payers.find((x) => x.id === d.payer_id);
  if (payer && payer.kind !== "self" && !d.member_id) return "Member ID is required for insurance billing.";
  return "";
}
