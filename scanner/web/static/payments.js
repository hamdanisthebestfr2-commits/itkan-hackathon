// Payments UI (Track B): take a payment (card / cash / check), copay at check-in, balance card.
//   openPaymentModal({ patient, amount, kind, source, appointmentId, title, note, methods, maxAmount, skipLabel, onPaid, onSkip })
//   renderCopayPanel(el, appointment, { onCollect })
//   renderBalanceCard(el, patientId, { compact })
// Needs shell.js (api, esc, toast, openModal, closeModal, fmtDate). The card processor is a MOCK: nothing is charged.

(function injectPayStyles() {
  if (document.getElementById("payStyles")) return;
  const s = document.createElement("style");
  s.id = "payStyles";
  s.textContent = `
  .pay-amount { display: flex; align-items: center; gap: 6px; font-size: 28px; font-weight: 700; }
  .pay-amount input { font-size: 28px; font-weight: 700; width: 160px; border: 1px solid var(--border); border-radius: 8px; padding: 4px 10px; }
  .pay-tabs { display: flex; gap: 6px; margin: 14px 0 12px; }
  .pay-tabs button { flex: 1; border: 1px solid var(--border); background: #fff; border-radius: 8px; padding: 8px; cursor: pointer; font: inherit; }
  .pay-tabs button.on { border-color: var(--brand); background: #eef5ff; color: var(--brand); font-weight: 600; }
  .pay-fields { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px 12px; }
  .pay-fields .full { grid-column: span 3; }
  .pay-fields label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; font-weight: 600; color: var(--muted); }
  .pay-fields input { border: 1px solid var(--border); border-radius: 7px; padding: 8px 10px; font: inherit; color: var(--text); }
  .pay-demo { font-size: 12px; color: #7a5300; background: #fff7e0; border: 1px solid #f0dfa8; border-radius: 7px; padding: 6px 10px; margin-top: 12px; }
  .pay-ok { text-align: center; padding: 10px 0; }
  .pay-ok .big { width: 56px; height: 56px; border-radius: 50%; background: var(--ok); color: #fff; font-size: 30px; display: grid; place-items: center; margin: 0 auto 10px; }
  .pay-ok table { margin: 12px auto 0; font-size: 14px; text-align: left; } .pay-ok td { padding: 3px 10px; } .pay-ok td:first-child { color: var(--muted); }
  .copay-box { border: 1px solid var(--border); border-radius: 10px; padding: 10px 12px; font-size: 14px; display: flex; flex-direction: column; gap: 8px; }
  .copay-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
  .copay-row .amt { font-size: 18px; font-weight: 700; }
  .copay-row .grow { flex: 1; min-width: 160px; }
  .copay-row.done .amt { color: var(--ok); }
  .bal-big { font-size: 26px; font-weight: 700; }
  .bal-big.owe { color: var(--missing); } .bal-big.zero { color: var(--ok); }
  table.ledger { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 8px; }
  table.ledger td { padding: 5px 4px; border-top: 1px solid #eef0f3; }
  table.ledger td.num { text-align: right; white-space: nowrap; }
  @media (max-width: 640px) { .pay-fields { grid-template-columns: 1fr 1fr; } .pay-fields .full { grid-column: span 2; } }`;
  document.head.appendChild(s);
})();

const usd = (n) => (n < 0 ? "-" : "") + "$" + Math.abs(Number(n)).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function openPaymentModal(opts) {
  const { patient, amount = 0, kind = "payment", source = "front_desk", appointmentId = null, title = "Take a payment",
          note = "", methods = ["card", "cash", "check"], maxAmount = null, skipLabel = null, onPaid, onSkip } = opts;
  let method = methods[0];
  const m = openModal(`
    <div class="modal-head"><h2>${esc(title)}</h2><button class="x" type="button" data-pay="close">×</button></div>
    <form id="payForm" autocomplete="off"><div class="modal-body">
      <div class="muted small">${esc(patient.first_name)} ${esc(patient.last_name)}${patient.mrn ? " · " + esc(patient.mrn) : ""}</div>
      <div class="pay-amount" style="margin-top:6px">$<input id="payAmt" type="number" min="0.01" step="0.01" value="${Number(amount).toFixed(2)}" ${maxAmount !== null ? `max="${maxAmount}"` : ""}></div>
      ${note ? `<div class="muted small" style="margin-top:4px">${esc(note)}</div>` : ""}
      ${methods.length > 1 ? `<div class="pay-tabs">${methods.map((k) => `<button type="button" data-method="${k}" class="${k === method ? "on" : ""}">${{ card: "💳 Card", cash: "💵 Cash", check: "🧾 Check" }[k]}</button>`).join("")}</div>` : '<div style="height:12px"></div>'}
      <div id="payFields"></div>
    </div>
    <div class="modal-foot"><span class="form-error" id="payErr"></span>
      ${skipLabel ? `<button type="button" class="btn" data-pay="skip">${esc(skipLabel)}</button>` : `<button type="button" class="btn" data-pay="close">Cancel</button>`}
      <button type="submit" class="btn primary" id="paySubmit">Charge</button></div></form>`);

  const fields = () => {
    m.querySelector("#payFields").innerHTML = method === "card" ? `
      <div class="pay-fields">
        <label class="full">Name on card<input id="cName" value="${esc(patient.first_name)} ${esc(patient.last_name)}"></label>
        <label class="full">Card number<input id="cNum" inputmode="numeric" placeholder="4242 4242 4242 4242" maxlength="23"></label>
        <label>Expiry<input id="cExp" placeholder="MM/YY" maxlength="5"></label>
        <label>CVC<input id="cCvc" inputmode="numeric" placeholder="123" maxlength="4"></label>
        <label>ZIP<input id="cZip" inputmode="numeric" maxlength="5" value="${esc(patient.zip || "")}"></label>
      </div>
      <div class="pay-demo">Demo card processor: nothing is really charged and only the last 4 digits are saved.
        Try <b>4242 4242 4242 4242</b>, any future expiry, any CVC. <b>4000 0000 0000 0002</b> is declined.</div>`
      : method === "check" ? `<div class="pay-fields"><label class="full">Check number<input id="cCheck" inputmode="numeric"></label></div>`
      : `<p class="muted small" style="margin:0">Count the cash and give change if needed.</p>`;
    const num = m.querySelector("#cNum"), exp = m.querySelector("#cExp");
    if (num) num.oninput = () => { num.value = num.value.replace(/\D/g, "").slice(0, 19).replace(/(\d{4})(?=\d)/g, "$1 "); };
    if (exp) exp.oninput = () => { const d = exp.value.replace(/\D/g, "").slice(0, 4); exp.value = d.length > 2 ? d.slice(0, 2) + "/" + d.slice(2) : d; };
    updateLabel();
  };
  const updateLabel = () => {
    const v = Number(m.querySelector("#payAmt").value || 0);
    m.querySelector("#paySubmit").textContent = method === "card" ? `Charge ${usd(v)}` : `Record ${usd(v)} ${method}`;
  };
  m.querySelector("#payAmt").oninput = updateLabel;
  m.querySelectorAll("[data-method]").forEach((b) => b.onclick = () => {
    method = b.dataset.method;
    m.querySelectorAll("[data-method]").forEach((x) => x.classList.toggle("on", x === b));
    fields();
  });
  m.querySelectorAll('[data-pay="close"]').forEach((b) => b.onclick = () => closeModal());
  const skip = m.querySelector('[data-pay="skip"]');
  if (skip) skip.onclick = () => { closeModal(); onSkip && onSkip(); };
  fields();

  m.querySelector("#payForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const err = m.querySelector("#payErr"), btn = m.querySelector("#paySubmit");
    const amt = Math.round(Number(m.querySelector("#payAmt").value) * 100) / 100;
    if (!(amt > 0)) { err.textContent = "Enter an amount."; return; }
    if (maxAmount !== null && amt > maxAmount + 0.001) { err.textContent = `The most you can pay is ${usd(maxAmount)}.`; return; }
    const body = { patient_id: patient.id, amount: amt, method, kind, source, appointment_id: appointmentId };
    if (method === "card") body.card = { number: m.querySelector("#cNum").value, exp: m.querySelector("#cExp").value,
                                          cvc: m.querySelector("#cCvc").value, name: m.querySelector("#cName").value, zip: m.querySelector("#cZip").value };
    if (method === "check") body.check_number = m.querySelector("#cCheck").value;
    err.textContent = "";
    btn.disabled = true; btn.textContent = method === "card" ? "Processing…" : "Saving…";
    try {
      const res = await api("/api/payments", { method: "POST", body });
      const p = res.payment;
      m.innerHTML = `<div class="modal-head"><h2>Payment received</h2></div>
        <div class="modal-body"><div class="pay-ok"><div class="big">✓</div>
          <div style="font-size:22px;font-weight:700">${usd(p.amount)}</div>
          <table>
            <tr><td>Receipt</td><td><b>${esc(p.receipt)}</b></td></tr>
            <tr><td>Paid with</td><td>${p.method === "card" ? `${esc(p.card_brand)} •••• ${esc(p.card_last4)} · auth ${esc(p.auth_code)}` : p.method === "check" ? `Check #${esc(p.check_number)}` : "Cash"}</td></tr>
            <tr><td>Balance now</td><td><b>${res.credit ? usd(res.credit) + " credit" : usd(res.due)}</b></td></tr>
          </table></div></div>
        <div class="modal-foot"><button class="btn primary" id="payDone">Done</button></div>`;
      m.querySelector("#payDone").onclick = () => { closeModal(); onPaid && onPaid(res); };
      m.querySelector("#payDone").focus();
    } catch (ex) {
      err.textContent = ex.message;
      btn.disabled = false; updateLabel();
    }
  });
  return m;
}

// Copay / amount due at check-in, shown in the schedule's appointment popup.
async function renderCopayPanel(el, appt, { onCollect } = {}) {
  el.innerHTML = '<div class="copay-box muted">Loading…</div>';
  let s;
  try { s = await api(`/api/appointments/${appt.id}/copay`); } catch (e) { el.innerHTML = ""; return null; }
  const done = s.remaining <= 0;
  el.innerHTML = `<div class="copay-box">
    <div class="copay-row ${done ? "done" : ""}">
      <span class="amt">${s.due > 0 ? (done ? "✓ " : "") + usd(s.due) : "$0"}</span>
      <span class="grow"><b>${s.due > 0 ? `${esc(s.label)} due today` : "Nothing to collect today"}</b>${s.due > 0 && done ? ` · collected` : s.collected && !done ? ` · ${usd(s.collected)} collected, ${usd(s.remaining)} left` : ""}<br>
        <span class="muted small">${esc(s.note)}</span></span>
      ${done ? "" : `<button type="button" class="btn small primary" data-copay="collect">Collect ${usd(s.remaining)}</button>`}
    </div>
    ${s.balance > 0 ? `<div class="copay-row"><span class="grow small">⚠ Also owes <b>${usd(s.balance)}</b> from earlier visits.</span>
      <button type="button" class="btn small" data-copay="balance">Collect balance</button></div>` : ""}
  </div>`;
  const patient = { id: appt.patient_id, first_name: appt.first_name, last_name: appt.last_name, mrn: appt.mrn };
  const collect = el.querySelector('[data-copay="collect"]');
  if (collect) collect.onclick = () => onCollect ? onCollect(s) : openPaymentModal({ patient, amount: s.remaining, kind: "copay",
    source: "check_in", appointmentId: appt.id, title: `Collect ${s.label.toLowerCase()}`, note: s.note });
  const bal = el.querySelector('[data-copay="balance"]');
  if (bal) bal.onclick = () => openPaymentModal({ patient, amount: s.balance, title: "Collect balance from earlier visits" });
  return s;
}

// Balance card for the patient chart.
async function renderBalanceCard(el, patient, { onChange } = {}) {
  let b;
  try { b = await api(`/api/patients/${patient.id}/balance`); } catch (e) { el.innerHTML = `<span class="muted small">${esc(e.message)}</span>`; return; }
  const recent = b.entries.slice(-5).reverse();
  el.innerHTML = `
    <div style="display:flex;align-items:baseline;gap:10px;flex-wrap:wrap">
      <span class="bal-big ${b.due > 0 ? "owe" : "zero"}">${b.credit ? usd(b.credit) : usd(b.due)}</span>
      <span class="muted small">${b.credit ? "credit on account" : b.due > 0 ? "patient owes" : "nothing owed"}</span></div>
    ${b.pending.length ? `<div class="muted small" style="margin-top:4px">${b.pending.length} visit${b.pending.length > 1 ? "s" : ""} still with insurance (not billed to the patient yet).</div>` : ""}
    ${recent.length ? `<table class="ledger">${recent.map((e) => `<tr><td class="muted">${fmtDate(e.date)}</td><td>${esc(e.description)}</td>
      <td class="num" style="color:${e.amount < 0 ? "var(--ok)" : "inherit"}">${usd(e.amount)}</td></tr>`).join("")}</table>` : ""}
    <div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap">
      <button type="button" class="btn small primary" data-bal="pay">Take payment</button>
      <a class="btn small" href="/statement?patient_id=${patient.id}" target="_blank">Print statement</a></div>`;
  el.querySelector('[data-bal="pay"]').onclick = () => openPaymentModal({ patient, amount: b.due,
    title: "Take a payment", onPaid: () => { renderBalanceCard(el, patient, { onChange }); onChange && onChange(); } });
}
