// Shared page shell: top navigation + small helpers used by every page.
// Rename the product here (one place).
const PRODUCT_NAME = "FlatRate Health";

const NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/schedule", label: "Schedule" },
  { href: "/patients", label: "Patients" },
  { href: "/scan", label: "Scan Intake" },
  { href: "/billing", label: "Billing" },
  { href: "/pharmacy", label: "Pharmacy" },
  { href: "/savings", label: "Savings" },
];

function renderNav(active) {
  const nav = document.getElementById("nav");
  if (!nav) return;
  nav.className = "nav";
  nav.innerHTML = `
    <a class="brand" href="/"><span class="mark">✚</span>${esc(PRODUCT_NAME)}</a>
    <div class="links">${NAV.map((n) => n.soon
      ? `<span class="link soon" title="Coming in a later phase">${n.label}</span>`
      : `<a class="link ${n.href === active ? "active" : ""}" href="${n.href}">${n.label}</a>`).join("")}
    </div>
    <span class="clinic">Plano Community Clinic · demo</span>`;
  document.title = document.title ? `${document.title} · ${PRODUCT_NAME}` : PRODUCT_NAME;
}

// Show script errors on the page instead of failing silently (a frozen "Loading…" is worse in a demo).
function _showError(msg) {
  let bar = document.getElementById("errorBar");
  if (!bar) {
    bar = document.createElement("div");
    bar.id = "errorBar";
    bar.style.cssText = "position:fixed;left:0;right:0;bottom:0;background:#c4291c;color:#fff;padding:8px 16px;font:13px monospace;z-index:99";
    document.body.appendChild(bar);
  }
  bar.textContent = "Error: " + msg;
}
window.addEventListener("error", (e) => _showError(`${e.message} (${(e.filename || "").split("/").pop()}:${e.lineno})`));
window.addEventListener("unhandledrejection", (e) => _showError(e.reason && e.reason.stack ? e.reason.stack.split("\n").slice(0, 2).join(" ") : String(e.reason)));

// ---------- helpers ----------
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(path, options = {}) {
  const opts = { ...options, headers: { "Content-Type": "application/json", ...(options.headers || {}) } };
  if (opts.body && typeof opts.body !== "string") opts.body = JSON.stringify(opts.body);
  const r = await fetch(path, opts);
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

// One shared live-update stream per page.
const _listeners = [];
function onEvent(fn) {
  _listeners.push(fn);
  if (_listeners.length === 1) {
    const es = new EventSource("/api/events");
    es.onmessage = (m) => { const ev = JSON.parse(m.data); _listeners.forEach((f) => f(ev)); };
  }
}

let _reference = null;
async function reference() {
  return _reference || (_reference = await api("/api/reference"));
}
