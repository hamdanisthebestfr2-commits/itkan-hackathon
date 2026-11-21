// Lab orders + results UI (Track A3).
// labTable(order)                              -> HTML table of result rows with H/L flags
// setupLabs(box, { encId, patientId, locked }) -> "Lab orders" card on the visit page (order tests, live results)

function labTable(o) {
  if (!o.results || !o.results.length) return "";
  return `<table class="labres"><thead><tr><th>Test</th><th>Result</th><th>Normal range</th><th></th></tr></thead><tbody>
    ${o.results.map((r) => `<tr class="${r.flag ? "abn" : ""}"><td>${esc(r.analyte)}</td>
      <td><b>${esc(r.value)}</b> ${esc(r.unit)}</td><td class="muted">${esc(r.ref_range)}</td>
      <td>${r.flag ? `<span class="flag ${esc(r.flag)}">${r.flag === "H" ? "HIGH" : r.flag === "L" ? "LOW" : "ABNORMAL"}</span>` : ""}</td></tr>`).join("")}
    </tbody></table>`;
}

function labStatus(o) {
  if (o.status === "ordered") return `<span class="lab-wait"><span class="dot"></span>At the lab…</span>`;
  const abn = o.abnormal ? `<span class="badge red">${o.abnormal} abnormal</span>` : `<span class="badge green">Normal</span>`;
  return abn + (o.status === "reviewed" ? ` <span class="badge">Reviewed</span>` : ` <span class="badge amber">Needs review</span>`);
}

async function setupLabs(box, { encId, locked }) {
  const catalog = await api("/api/labs/catalog");
  let orders = [];

  async function load() {
    orders = await api(`/api/encounters/${encId}/labs`);
    render();
  }

  function render() {
    const have = new Set(orders.map((o) => o.test_code));
    box.innerHTML = `<h3>🧪 Lab orders <span class="sp"></span>
        <span class="muted small" style="text-transform:none;letter-spacing:0;font-weight:400">mock reference lab · results arrive in the Inbox</span></h3>
      ${locked ? "" : `<div class="lab-pick">${catalog.map((t) => `<label title="CPT ${esc(t.cpt)}: ${esc(t.analytes.join(", "))}">
          <input type="checkbox" value="${esc(t.code)}" ${have.has(t.code) ? "disabled" : ""}> ${esc(t.name)}</label>`).join("")}</div>
        <div style="margin-top:10px;display:flex;gap:8px;align-items:center">
          <button class="btn primary small" id="labOrderBtn" type="button">Order selected tests</button>
          <span class="muted small">They're billed automatically when the visit is coded.</span></div>`}
      <div style="margin-top:8px">${orders.map((o) => `<div class="lab-order">
          <div class="hd"><b>${esc(o.test_name)}</b> <span class="muted small">CPT ${esc(o.cpt)}</span><span class="sp"></span>${labStatus(o)}
            ${o.status === "ordered" && !locked ? `<button class="btn small" type="button" data-now="${o.id}" title="Demo: the lab finishes now">Result now (demo)</button>` : ""}</div>
          ${o.status !== "ordered" ? `<div style="margin-top:6px">${labTable(o)}</div>` : ""}
          ${o.provider_comment ? `<div class="small" style="margin-top:6px"><b>Note to patient:</b> ${esc(o.provider_comment)}</div>` : ""}
        </div>`).join("") || (locked ? `<span class="muted small">No labs ordered at this visit.</span>` : "")}</div>`;
    const btn = box.querySelector("#labOrderBtn");
    if (btn) btn.onclick = async () => {
      const tests = [...box.querySelectorAll(".lab-pick input:checked")].map((i) => i.value);
      if (!tests.length) { toast("Pick at least one test", "error"); return; }
      btn.disabled = true;
      try {
        const r = await api(`/api/encounters/${encId}/labs`, { method: "POST", body: { tests } });
        toast(`Sent ${r.ordered.length} test${r.ordered.length === 1 ? "" : "s"} to the lab ✓ (results in ~${Math.round(r.turnaround_seconds)} s)`);
        await load();
      } catch (e) { toast(e.message, "error"); btn.disabled = false; }
    };
    box.querySelectorAll("[data-now]").forEach((b) => b.onclick = async () => {
      b.disabled = true;
      await api(`/api/labs/${b.dataset.now}/result-now`, { method: "POST" });
      load();
    });
  }

  onEvent((ev) => {
    if ((ev.type === "lab_resulted" || ev.type === "lab_reviewed") && ev.order && ev.order.encounter_id === encId) load();
  });
  load();
}
