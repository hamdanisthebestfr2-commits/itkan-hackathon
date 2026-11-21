// Care gaps / quality measures UI (Track A4).
// gapRows(gaps)                                     -> read-only list (patient chart)
// setupCareGaps(box, { patientId, encId, locked,   -> visit-page card with one-click "close the gap" actions
//                      insertNote, focusVitals })

function gapRow(g, action = "", showNext = true) {
  const open = g.status === "open";
  return `<div class="gap ${open ? "open" : "met"}">
    <span class="gi">${open ? "!" : "✓"}</span>
    <div class="gm"><div><b>${esc(g.title)}</b> <span class="cms" title="${esc(g.about)}">${esc(g.cms)}</span></div>
      <div class="gd">${esc(g.detail)}${open && showNext && g.upcoming ? ` · <span class="muted">next visit ${fmtDate(g.upcoming.slice(0, 10))}</span>` : ""}</div></div>
    ${action}</div>`;
}

function gapRows(gaps) {
  if (!gaps.length) return '<span class="muted small">No quality measures apply to this patient.</span>';
  const open = gaps.filter((g) => g.status === "open"), met = gaps.filter((g) => g.status === "met");
  return open.map((g) => gapRow(g)).join("") + met.map((g) => gapRow(g)).join("");
}

function setupCareGaps(box, { patientId, encId, locked, insertNote, focusVitals }) {
  let prevOpen = null;

  function action(g, i) {
    if (locked || !g.close) return "";
    const k = g.close.kind;
    const label = { lab: `Order ${g.close.test === "A1C" ? "A1c" : g.close.test}`, note: "Add to note", vitals: "Go to vitals",
                    rx: "Prescribe", book: "Book" }[k];
    if (k === "book") return `<a class="btn small" href="/schedule?patient_id=${patientId}" title="${esc(g.close.label)}">${label}</a>`;
    return `<button class="btn small" type="button" data-i="${i}" title="${esc(g.close.label)}${g.close.text ? ": " + esc(g.close.text) : ""}">${label}</button>`;
  }

  async function load() {
    const gaps = await api(`/api/patients/${patientId}/care-gaps`);
    const open = gaps.filter((g) => g.status === "open"), met = gaps.filter((g) => g.status === "met");
    if (prevOpen) {
      gaps.filter((g) => g.status === "met" && prevOpen.has(g.id)).forEach((g) => toast(`✓ Care gap closed: ${g.title}`));
    }
    prevOpen = new Set(open.map((g) => g.id));
    const all = [...open, ...met];
    box.innerHTML = `<h3>✅ Care gaps ${open.length ? `<span class="badge red" style="margin-left:4px">${open.length} open</span>` : '<span class="badge green" style="margin-left:4px">all met</span>'}</h3>
      ${all.length ? all.map((g, i) => gapRow(g, action(g, i), false)).join("") : '<span class="muted small">No quality measures apply.</span>'}
      <div class="muted small" style="margin-top:6px">Simplified CMS quality measures. Close a gap during the visit and it updates live.</div>`;
    box.querySelectorAll("[data-i]").forEach((b) => b.onclick = async () => {
      const g = all[Number(b.dataset.i)], c = g.close;
      if (c.kind === "lab") {
        b.disabled = true;
        try { await api(`/api/encounters/${encId}/labs`, { method: "POST", body: { tests: [c.test] } }); toast(`${c.test === "A1C" ? "A1c" : c.test} sent to the lab ✓`); }
        catch (e) { toast(e.message, "error"); }
        load();
      } else if (c.kind === "note") {
        insertNote(c.text);   // the visit page refreshes gaps after the autosave
      } else if (c.kind === "vitals") {
        focusVitals(g.id === "bmi" ? "height_ft" : "bp_systolic");
      } else if (c.kind === "rx") {
        const rx = document.getElementById("rxForm");
        if (rx) { rx.scrollIntoView({ behavior: "smooth", block: "center" }); toast(c.label); }
      }
    });
  }

  onEvent((ev) => { if (["lab_ordered", "lab_resulted", "rx_sent"].includes(ev.type) && (ev.patient_id === patientId || (ev.rx && ev.rx.patient_id === patientId))) load(); });
  load();
  return { refresh: load };
}
