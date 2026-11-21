// Shared page shell: top navigation + small helpers used by every page.
// Rename the product here (one place).
const PRODUCT_NAME = "Iris";

// Browser-tab icon on every page that loads the shell (staff pages and the patient portal).
(() => {
  if (document.querySelector('link[rel="icon"]')) return;
  const l = document.createElement("link");
  l.rel = "icon"; l.type = "image/png"; l.href = "/static/favicon.png";
  document.head.appendChild(l);
})();

// Iris loading screen: the spinning logo shows for exactly IRIS_LOADER_MS on every page change, counted from
// the click (or from the start of the page load for navigations done in code). The screen itself is drawn by
// app.css (html.iris-boot / html.iris-leave), so it is up from the first paint. Automated test browsers skip it.
const IRIS_LOADER_MS = 2000;
(() => {
  const html = document.documentElement;
  if (navigator.webdriver) { html.classList.remove("iris-boot"); return; }
  if (html.classList.contains("iris-boot")) {
    let started = performance.timeOrigin || Date.now();
    try {
      const clicked = Number(sessionStorage.getItem("iris-nav"));
      sessionStorage.removeItem("iris-nav");
      if (clicked > 0 && Date.now() - clicked < IRIS_LOADER_MS + 3000) started = clicked;
    } catch (e) { /* storage blocked: count from the page load */ }
    setTimeout(() => {
      html.classList.add("iris-out", "iris-reveal");
      setTimeout(() => html.classList.remove("iris-boot", "iris-out"), 360);
      setTimeout(() => html.classList.remove("iris-reveal"), 1400);
    }, Math.max(0, IRIS_LOADER_MS - (Date.now() - started)));
  }
  // Leaving: put the screen up right away, then go. The next page keeps it up until 2 s after this click.
  document.addEventListener("click", (e) => {
    const a = e.target.closest && e.target.closest("a[href]");
    if (!a || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    if ((a.target && a.target !== "_self") || a.hasAttribute("download")) return;
    const url = new URL(a.href, location.href);
    if (url.origin !== location.origin || /^\/(api|static|video|r)\b/.test(url.pathname)) return;
    if (url.pathname === location.pathname && url.search === location.search) return;   // same page / #section
    e.preventDefault();
    try { sessionStorage.setItem("iris-nav", String(Date.now())); } catch (err) { /* fine */ }
    html.classList.add("iris-leave");
    setTimeout(() => { location.href = url.href; }, 200);
  });
  // Back/forward restores a page from cache: never leave the leaving screen on it.
  window.addEventListener("pageshow", () => html.classList.remove("iris-leave"));
})();

const NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/schedule", label: "Schedule" },
  { href: "/inbox", label: "Inbox" },  // Track A3: Clinical Inbox (badge = items waiting)
  { href: "/patients", label: "Patients" },
  { href: "/scan", label: "Scan Intake" },
  { href: "/billing", label: "Billing" },
  { href: "/pharmacy", label: "Pharmacy" },
  { href: "/savings", label: "Savings" },
  { href: "/portal", label: "Patient Portal ↗" },  // Track B
];

function renderNav(active) {
  const nav = document.getElementById("nav");
  if (!nav) return;
  nav.className = "nav";
  nav.innerHTML = `
    <a class="brand" href="/"><img class="mark" src="/static/iris-mark-white.png" alt="">${esc(PRODUCT_NAME)}</a>
    <div class="links">${NAV.map((n) => n.soon
      ? `<span class="link soon" title="Coming in a later phase">${n.label}</span>`
      : `<a class="link ${n.href === active ? "active" : ""}" href="${n.href}">${n.label}</a>`).join("")}
    </div>
    <span class="clinic">Plano Community Clinic · demo</span>`;
  document.title = document.title ? `${document.title} · ${PRODUCT_NAME}` : PRODUCT_NAME;
  _inboxBadge();
  let t;
  onEvent((ev) => {
    if (["lab_resulted", "lab_reviewed", "message_created", "message_updated", "clinic_reset"].includes(ev.type)) {
      clearTimeout(t); t = setTimeout(_inboxBadge, 300);
    }
  });
}

// Clinical Inbox count on the nav link (red when an abnormal result is waiting).
async function _inboxBadge() {
  const link = document.querySelector('.nav a.link[href="/inbox"]');
  if (!link) return;
  try {
    const c = await api("/api/inbox/count");
    link.innerHTML = "Inbox" + (c.total ? ` <span class="nav-badge ${c.urgent ? "urgent" : ""}">${c.total}</span>` : "");
  } catch (e) { /* the badge is a nicety; never block the page for it */ }
}

// Show script errors on the page instead of failing silently (a frozen "Loading…" is worse in a demo).
function _showError(msg) {
  if (_leaving) return;
  let bar = document.getElementById("errorBar");
  if (!bar) {
    bar = document.createElement("div");
    bar.id = "errorBar";
    bar.style.cssText = "position:fixed;left:0;right:0;bottom:0;background:#c4291c;color:#fff;padding:8px 16px;font:13px monospace;z-index:99";
    document.body.appendChild(bar);
  }
  bar.textContent = "Error: " + msg;
}
// Requests cut off because the user clicked to another page are not errors; don't flash the red bar for them.
let _leaving = false;
window.addEventListener("pagehide", () => { _leaving = true; });
window.addEventListener("beforeunload", () => { _leaving = true; });
// Back/forward cache restored a page we had "left": reload so data and live updates are fresh.
window.addEventListener("pageshow", (e) => { if (e.persisted) location.reload(); });
window.addEventListener("error", (e) => _showError(`${e.message} (${(e.filename || "").split("/").pop()}:${e.lineno})`));
window.addEventListener("unhandledrejection", (e) => _showError(e.reason && e.reason.stack ? e.reason.stack.split("\n").slice(0, 2).join(" ") : String(e.reason)));

// ---------- helpers ----------
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(path, options = {}) {
  const opts = { ...options, headers: { "Content-Type": "application/json", ...(options.headers || {}) } };
  if (opts.body && typeof opts.body !== "string") opts.body = JSON.stringify(opts.body);
  const method = (opts.method || "GET").toUpperCase();
  let r;
  for (let attempt = 0; ; attempt++) {
    try {
      r = await fetch(path, opts);
      break;
    } catch (e) {
      // Network failure (server restarting / unreachable). Reads are safe to retry; writes are not
      // (the server may have already saved it), so those fail right away with a clear message.
      if (method !== "GET" || attempt >= 4) {
        throw new Error("Can't reach the app server. Check that start.bat is still running, then try again.");
      }
      await new Promise((res) => setTimeout(res, 600 * (attempt + 1)));
    }
  }
  const data = await r.json().catch(() => null);
  if (!r.ok) throw new Error((data && data.detail) || `Request failed (${r.status})`);
  return data;
}

function fmtDate(iso) {
  if (!iso) return "";
  const d = new Date(iso.length === 10 ? iso + "T00:00" : iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}
function fmtDateTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" }) + " · " +
    d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
}
function age(dob) {
  if (!dob) return "";
  const b = new Date(dob + "T00:00"), n = new Date();
  let a = n.getFullYear() - b.getFullYear();
  if (n < new Date(n.getFullYear(), b.getMonth(), b.getDate())) a--;
  return a;
}
const SEX = { M: "Male", F: "Female", X: "Other" };

function toast(text, kind = "ok") {
  let t = document.querySelector(".toast");
  if (!t) { t = document.createElement("div"); document.body.appendChild(t); }
  t.textContent = text;
  t.className = `toast show ${kind === "error" ? "err" : ""}`;
  clearTimeout(t._h);
  t._h = setTimeout(() => t.className = "toast", 2800);
}

// Modal: openModal(html) returns the dialog element; closeModal() closes it.
function openModal(html, { wide = false } = {}) {
  closeModal();
  const back = document.createElement("div");
  back.className = "modal-back";
  back.innerHTML = `<div class="modal ${wide ? "wide" : ""}" role="dialog">${html}</div>`;
  back.addEventListener("mousedown", (e) => { if (e.target === back) closeModal(); });
  document.body.appendChild(back);
  const first = back.querySelector("input, select, textarea");
  if (first) first.focus();
  return back.querySelector(".modal");
}
function closeModal() { document.querySelectorAll(".modal-back").forEach((m) => m.remove()); }
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

// Live updates. All open tabs share ONE connection through a SharedWorker (static/events-worker.js):
// browsers allow only 6 connections per site, and one stream per tab used to make new pages hang.
const _listeners = [];
function onEvent(fn) {
  _listeners.push(fn);
  if (_listeners.length > 1) return;
  const deliver = (data) => { const ev = JSON.parse(data); _listeners.forEach((f) => f(ev)); };
  if (window.SharedWorker) {
    try {
      const w = new SharedWorker("/static/events-worker.js", { name: "live-events" });
      w.port.onmessage = (m) => deliver(m.data);
      w.port.start();
      window.addEventListener("pagehide", () => w.port.postMessage("bye"));
      return;
    } catch (e) { /* fall through to a direct connection */ }
  }
  const es = new EventSource("/api/events");
  es.onmessage = (m) => deliver(m.data);
  window.addEventListener("pagehide", () => es.close());
}

let _reference = null;
async function reference() {
  return _reference || (_reference = await api("/api/reference"));
}
