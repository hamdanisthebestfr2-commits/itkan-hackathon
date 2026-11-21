// "Ask the chart" assistant (Track A6): floating button + side drawer on the chart and visit pages.
// setupAskChart({ patientId, patientName }). Answers come only from this patient's chart, with clickable sources.

const ASK_STARTERS = [
  "Summarize this patient before the visit",
  "Is the blood pressure improving?",
  "Any abnormal lab results?",
  "What changed at the last visit?",
  "Which care gaps are open?",
  "Any unpaid claims, denials or balance?",
];

function setupAskChart({ patientId, patientName }) {
  if (document.getElementById("askFab")) return;   // the page re-renders; keep one assistant
  const history = [];   // [{q, a}] for follow-up questions

  const fab = document.createElement("button");
  fab.id = "askFab"; fab.className = "ask-fab"; fab.type = "button";
  fab.innerHTML = "✨ Ask the chart";
  const drawer = document.createElement("aside");
  drawer.className = "ask-drawer"; drawer.hidden = true;
  drawer.innerHTML = `
    <div class="ask-hd"><div><b>✨ Ask the chart</b><div class="ask-sub">${esc(patientName)} · answers only from this chart · check the sources</div></div>
      <button class="x" type="button" aria-label="Close">×</button></div>
    <div class="ask-log" aria-live="polite"><div class="ask-starters">${ASK_STARTERS.map((s) => `<button type="button" class="ask-chip">${esc(s)}</button>`).join("")}</div></div>
    <form class="ask-form"><input type="text" placeholder="Ask about ${esc(patientName)}'s chart…" maxlength="500" autocomplete="off">
      <button class="btn primary small" type="submit">Ask</button></form>`;
  document.body.append(fab, drawer);
  const log = drawer.querySelector(".ask-log"), form = drawer.querySelector("form"), input = form.querySelector("input");

  const open = () => { drawer.hidden = false; fab.hidden = true; input.focus(); };
  const close = () => { drawer.hidden = true; fab.hidden = false; };
  fab.onclick = open;
  drawer.querySelector(".x").onclick = close;
  drawer.addEventListener("keydown", (e) => { if (e.key === "Escape") { e.stopPropagation(); close(); } });
  drawer.addEventListener("click", (e) => { const c = e.target.closest(".ask-chip"); if (c) ask(c.textContent); });
  form.onsubmit = (e) => { e.preventDefault(); ask(input.value); };

  function renderAnswer(r) {
    const byId = Object.fromEntries(r.sources.map((s) => [s.id, s]));
    // escape first, then turn [ID] markers into links to the source
    const html = esc(r.answer).replace(/ ?\[([A-Z]{1,3}\d*)\]/g, (m, id) => byId[id]
      ? ` <a class="ask-src" href="${esc(byId[id].href)}" target="_blank" title="Open the source">${esc(byId[id].label)}</a>` : "");
    return `<div class="ask-a ${r.not_in_chart ? "none" : ""}">${html}</div>
      ${r.follow_ups.length ? `<div class="ask-starters">${r.follow_ups.map((f) => `<button type="button" class="ask-chip">${esc(f)}</button>`).join("")}</div>` : ""}`;
  }

  async function ask(q) {
    q = (q || "").trim();
    if (!q) return;
    input.value = "";
    log.querySelectorAll(".ask-starters").forEach((el) => el.remove());   // old suggestions go away
    const turn = document.createElement("div");
    turn.className = "ask-turn";
    turn.innerHTML = `<div class="ask-q">${esc(q)}</div><div class="ask-a thinking"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>`;
    log.appendChild(turn);
    log.scrollTop = log.scrollHeight;
    try {
      const r = await api(`/api/patients/${patientId}/ask`, { method: "POST", body: { question: q, history } });
      turn.querySelector(".thinking").outerHTML = renderAnswer(r);
      history.push({ q, a: r.answer });
    } catch (e) {
      turn.querySelector(".thinking").outerHTML = `<div class="ask-a none">${esc(e.message)}</div>`;
    }
    log.scrollTop = log.scrollHeight;
    input.focus();
  }
}
