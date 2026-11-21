// Insurance eligibility UI (Track B), used by the schedule (booking + check-in) and the patient chart.
//   renderEligibility(el, patientId, { appointmentId, source, auto, compact, onResult, onEditInsurance })
//   eligBadge(check)  -> small chip for schedule blocks
// Needs shell.js (api, esc, fmtDate, toast).

(function injectStyles() {
  if (document.getElementById("eligStyles")) return;
  const s = document.createElement("style");
  s.id = "eligStyles";
  s.textContent = `
  .elig { border: 1px solid var(--border); border-radius: 10px; padding: 10px 12px; background: #fff; font-size: 14px; }
  .elig.ok { border-color: #bfe3cc; background: #f5fbf7; }
  .elig.error { border-color: #f2b8b1; background: #fff6f5; }
  .elig.info { border-color: #c9d9f2; background: #f5f8fd; }
  .elig.stale { border-style: dashed; }
  .elig-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .elig-head .ic { width: 22px; height: 22px; border-radius: 50%; display: grid; place-items: center; font-size: 13px; font-weight: 700; color: #fff; flex-shrink: 0; }
  .elig.ok .ic { background: var(--ok); } .elig.error .ic { background: var(--missing); } .elig.info .ic { background: var(--info); }
  .elig.none .ic, .elig.loading .ic { background: #9aa4b2; }
  .elig-head .ttl { font-weight: 700; }
  .elig-head .when { color: var(--muted); font-size: 12px; margin-left: auto; }
  .elig .msg { margin: 6px 0 0; }
  .elig .todo { margin-top: 6px; padding: 6px 10px; border-radius: 7px; background: #fff; border-left: 3px solid var(--missing); font-size: 13px; }
  .elig.info .todo { border-left-color: var(--info); }
  .elig-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 6px 14px; margin-top: 8px; }
  .elig-grid .k { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .4px; }
  .elig-grid .v { font-weight: 600; }
  .elig .bar { height: 6px; background: #e4e8ee; border-radius: 3px; margin-top: 4px; overflow: hidden; }
  .elig .bar span { display: block; height: 100%; background: var(--brand); }
  .elig .due { margin-top: 8px; padding: 6px 10px; border-radius: 7px; background: #fff; border: 1px solid #bfe3cc; font-size: 13px; }
  .elig-foot { display: flex; gap: 8px; align-items: center; margin-top: 8px; flex-wrap: wrap; }
  .elig-foot .src { color: var(--muted); font-size: 11px; flex: 1; }
  .elig-spin { width: 14px; height: 14px; border: 2px solid #c7cfda; border-top-color: var(--brand); border-radius: 50%; animation: eligspin .8s linear infinite; }
  @keyframes eligspin { to { transform: rotate(360deg); } }
  .elig-chip { display: inline-grid; place-items: center; width: 16px; height: 16px; border-radius: 50%; font-size: 10px; font-weight: 800;
               color: #fff; margin-right: 5px; vertical-align: 1px; flex-shrink: 0; }
  .elig-chip.ok { background: var(--ok); } .elig-chip.error { background: var(--missing); } .elig-chip.info { background: var(--info); }
  .elig-chip.none { background: #aab2bf; }`;
  document.head.appendChild(s);
})();

const ELIG_ICON = { active: "✓", inactive: "!", not_found: "!", missing_id: "!", no_insurance: "!", self_pay: "$" };
const ELIG_PROBLEM = ["inactive", "not_found", "missing_id", "no_insurance"];
const ELIG_SOURCE = { auto: "automatic check the night before", batch: "schedule check", booking: "checked at booking",
                      check_in: "checked at check-in", chart: "checked from the chart", portal: "checked from the portal" };
const money = (n) => "$" + Number(n).toLocaleString("en-US", { maximumFractionDigits: 0 });

function eligWhen(iso) {
  const d = new Date(iso), today = new Date();
  const t = d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  if (d.toDateString() === today.toDateString()) return `today ${t}`;
  const y = new Date(today); y.setDate(y.getDate() - 1);
  if (d.toDateString() === y.toDateString()) return `yesterday ${t}`;
  return fmtDate(iso.slice(0, 10));
}

function eligBadge(chk) {
  if (!chk) return `<span class="elig-chip none" title="Insurance not verified yet">?</span>`;
  if (chk.stale) return `<span class="elig-chip none" title="Re-check insurance: ${esc(chk.stale_reason || "")}">↻</span>`;
  return `<span class="elig-chip ${chk.level}" title="${esc(chk.label)}${chk.plan ? " · " + esc(chk.plan) : ""}">${ELIG_ICON[chk.status] || "?"}</span>`;
}

function eligCardHtml(c, { compact = false } = {}) {
  if (!c) {
    return `<div class="elig none"><div class="elig-head"><span class="ic">?</span><span class="ttl">Insurance not verified yet</span></div>
      <div class="elig-foot"><span class="src">Check coverage with the insurer before the visit.</span>
      <button type="button" class="btn small primary" data-elig="check">🛡 Check eligibility</button></div></div>`;
  }
  const active = c.status === "active";
  const d = c.deductible, o = c.oop;
  const grid = active ? `<div class="elig-grid">
      <div><div class="k">Member ID</div><div class="v">${esc(c.member_id)}</div></div>
      <div><div class="k">Office visit</div><div class="v">${c.copay ? money(c.copay) + " copay" : c.coinsurance_pct + "% coinsurance"}</div></div>
      ${compact ? "" : `<div><div class="k">Specialist</div><div class="v">${c.specialist_copay ? money(c.specialist_copay) + " copay" : "-"}</div></div>
      <div><div class="k">Coinsurance</div><div class="v">${c.coinsurance_pct}%</div></div>`}
      <div><div class="k">Deductible</div><div class="v">${money(d.met)} of ${money(d.amount)} met</div>
        <div class="bar"><span style="width:${Math.round(100 * d.met / d.amount)}%"></span></div></div>
      ${!compact && o && o.max ? `<div><div class="k">Out-of-pocket max</div><div class="v">${money(o.met)} of ${money(o.max)}</div>
        <div class="bar"><span style="width:${Math.round(100 * o.met / o.max)}%"></span></div></div>` : ""}
    </div>
    ${c.estimate ? `<div class="due">💵 <b>Due at check-in: ${money(c.estimate.due_today)}</b> · ${esc(c.estimate.note)}</div>` : ""}` : "";
  return `<div class="elig ${c.level} ${c.stale ? "stale" : ""}">
    <div class="elig-head"><span class="ic">${ELIG_ICON[c.status] || "?"}</span>
      <span class="ttl">${esc(c.label)}</span><span class="muted">${esc(c.plan || c.payer || "")}</span>
      <span class="when">${c.stale ? "⚠ " + esc(c.stale_reason) : "Verified " + eligWhen(c.checked_at)}</span></div>
    ${!active ? `<div class="msg">${esc(c.message)}</div>` : ""}
    ${c.action ? `<div class="todo"><b>Next step:</b> ${esc(c.action)}</div>` : ""}
    ${grid}
    <div class="elig-foot"><span class="src">Mock insurer response (demo) · ${esc(ELIG_SOURCE[c.source] || c.source)} · ${esc(c.trace || "")}</span>
      ${ELIG_PROBLEM.includes(c.status) ? `<button type="button" class="btn small" data-elig="edit">Update insurance</button>` : ""}
      <button type="button" class="btn small ${c.stale ? "primary" : ""}" data-elig="check">↻ Re-check</button></div>
  </div>`;
}

async function renderEligibility(el, patientId, opts = {}) {
  const { appointmentId = null, source = "chart", auto = false, compact = false, onResult, onEditInsurance } = opts;
  let current = null;
  const paint = (c) => {
    current = c;
    el.innerHTML = eligCardHtml(c, { compact });
    const chk = el.querySelector('[data-elig="check"]');
    if (chk) chk.onclick = run;
    const edit = el.querySelector('[data-elig="edit"]');
    if (edit) edit.onclick = () => onEditInsurance ? onEditInsurance(current) : (location.href = `/patient?id=${patientId}`);
    onResult && onResult(c);
  };
  async function run() {
    el.innerHTML = `<div class="elig loading"><div class="elig-head"><span class="elig-spin"></span>
      <span class="ttl">Checking coverage with the insurer…</span></div></div>`;
    try {
      paint(await api("/api/eligibility/check", { method: "POST", body: { patient_id: patientId, appointment_id: appointmentId, source } }));
    } catch (e) {
      el.innerHTML = `<div class="elig error"><div class="elig-head"><span class="ic">!</span><span class="ttl">Couldn't check eligibility</span></div>
        <div class="msg">${esc(e.message)}</div><div class="elig-foot"><span class="src"></span><button type="button" class="btn small" data-elig="check">Try again</button></div></div>`;
      el.querySelector('[data-elig="check"]').onclick = run;
    }
  }
  el.innerHTML = `<div class="elig loading"><div class="elig-head"><span class="elig-spin"></span><span class="ttl">Loading insurance status…</span></div></div>`;
  let latest = null;
  try { latest = (await api(`/api/eligibility/patient/${patientId}`)).latest; } catch (e) { /* show the empty state */ }
  if (auto && (!latest || latest.stale)) return run();
  paint(latest);
  return { recheck: run, get current() { return current; } };
}
