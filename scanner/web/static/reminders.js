// Appointment reminders UI (Track B), used by the schedule.
//   openRemindersModal(day, onDone)       send / preview a day's reminders
//   openEmailPreview({ appointmentId } | { reminderId })
//   renderReminderRow(el, appt, onChange) reminder status inside the appointment popup
//   remTag(summary)                       "Confirmed" / "Reschedule" tag on schedule blocks
// Needs shell.js (api, esc, toast, openModal, closeModal, fmtDate).

(function injectRemStyles() {
  if (document.getElementById("remStyles")) return;
  const s = document.createElement("style");
  s.id = "remStyles";
  s.textContent = `
  .rem-tag { display: inline-block; font-size: 10px; font-weight: 700; padding: 0 5px; border-radius: 4px; margin-left: 5px; vertical-align: 1px; letter-spacing: .2px; }
  .rem-tag.ok { background: #d8f0e1; color: #17703d; } .rem-tag.warn { background: #fde2c8; color: #9a4a00; }
  .rem-banner { padding: 8px 12px; border-radius: 8px; font-size: 13px; margin-bottom: 12px; }
  .rem-banner.on { background: var(--ok-bg); color: #17703d; } .rem-banner.off { background: #fff7e0; color: #7a5300; }
  table.rem { width: 100%; border-collapse: collapse; font-size: 14px; }
  table.rem th { text-align: left; font-size: 12px; color: var(--muted); padding: 6px 8px; border-bottom: 1px solid var(--border); }
  table.rem td { padding: 8px; border-bottom: 1px solid #eef0f3; vertical-align: middle; }
  table.rem tr.dis td { color: var(--muted); }
  .rem-frame { width: 100%; height: 520px; border: 1px solid var(--border); border-radius: 8px; background: #f4f7f7; }
  .rem-meta { font-size: 13px; margin-bottom: 8px; } .rem-meta b { display: inline-block; width: 70px; color: var(--muted); font-weight: 600; }`;
  document.head.appendChild(s);
})();

const REM_STATUS = { sent: ["Emailed", "green"], preview: ["Saved (email off)", "amber"], failed: ["Email failed", "red"], none: ["No reminder", ""] };
const remTime = (iso) => {
  const d = new Date(iso), today = new Date(), y = new Date(); y.setDate(y.getDate() - 1);
  const t = d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  return d.toDateString() === today.toDateString() ? `today ${t}` : d.toDateString() === y.toDateString() ? `yesterday ${t}` : `${fmtDate(iso.slice(0, 10))} ${t}`;
};

function remTag(s) {
  if (!s || !s.response) return "";
  return s.response === "confirmed" ? '<span class="rem-tag ok" title="Patient confirmed">✓ Confirmed</span>'
                                    : '<span class="rem-tag warn" title="Patient asked to reschedule">Reschedule</span>';
}

function remStatusText(s) {
  const parts = [];
  if (s.reminder && s.reminder.status !== "none") {
    const [label, cls] = REM_STATUS[s.reminder.status] || [s.reminder.status, ""];
    parts.push(`<span class="badge ${cls}">${label}</span> <span class="muted small">${remTime(s.reminder.created_at)}</span>`);
  } else parts.push('<span class="muted small">Not sent</span>');
  if (s.response === "confirmed") parts.push(`<span class="badge green">✓ Confirmed</span> <span class="muted small">${remTime(s.responded_at)} via ${esc(s.responded_via)}</span>`);
  if (s.response === "reschedule") parts.push(`<span class="badge amber">Wants to reschedule</span> <span class="muted small">via ${esc(s.responded_via)}</span>`);
  return parts.join(" ");
}

async function openEmailPreview({ appointmentId = null, reminderId = null, back = null } = {}) {
  const r = reminderId ? await api(`/api/reminders/${reminderId}`) : await api(`/api/reminders/preview/${appointmentId}`);
  const html = r.html || r.body_html;
  const to = reminderId ? (r.sent_to ? `${esc(r.sent_to)} <span class="muted">(demo inbox, standing in for ${esc(r.patient_email || "the patient")})</span>`
                                     : `<span class="muted">not emailed (email is off): saved in the app</span>`)
                        : '<span class="muted">preview, not sent yet</span>';
  const m = openModal(`<div class="modal-head"><h2>Reminder email</h2><button class="x" onclick="closeModal()">×</button></div>
    <div class="modal-body">
      <div class="rem-meta"><b>Subject</b>${esc(r.subject)}</div>
      <div class="rem-meta"><b>To</b>${to}</div>
      ${reminderId && r.status === "failed" ? `<div class="rem-banner off">Email failed: ${esc(r.error)}</div>` : ""}
      <iframe class="rem-frame" sandbox="allow-popups allow-popups-to-escape-sandbox" title="Email preview"></iframe>
    </div>
    <div class="modal-foot">${back ? '<button class="btn" id="remBack">← Back</button>' : ""}<button class="btn primary" onclick="closeModal()">Close</button></div>`, { wide: true });
  m.querySelector("iframe").srcdoc = html.replace("<head>", '<head><base target="_blank">');
  if (back) m.querySelector("#remBack").onclick = back;
}

async function openRemindersModal(day, onDone) {
  const data = await api(`/api/reminders?day=${day}`);
  const list = data.appointments;
  const sendable = list.filter((x) => x.can_send);
  const m = openModal(`<div class="modal-head"><h2>Appointment reminders</h2><button class="x" onclick="closeModal()">×</button></div>
    <div class="modal-body">
      <div style="display:flex;gap:10px;align-items:center;margin-bottom:10px;flex-wrap:wrap">
        <label class="small muted" for="remDay">Day</label><input type="date" id="remDay" value="${day}" style="border:1px solid var(--border);border-radius:7px;padding:5px 8px">
        <span class="muted small">${fmtDate(day)} · ${list.length} appointment${list.length === 1 ? "" : "s"}</span></div>
      <div class="rem-banner ${data.email_enabled ? "on" : "off"}">${data.email_enabled
        ? `✉ Email is on: reminders go to the team's demo inbox <b>${esc(data.sent_to)}</b> (never to the fictional patients).`
        : "Email is off on this computer: reminders are saved here so you can preview them. Add SMTP settings to <code>scanner/.env</code> to email them to the demo inbox."}</div>
      ${list.length ? `<table class="rem"><thead><tr><th><input type="checkbox" id="remAll" title="Select all"></th><th>Time</th><th>Patient</th><th>Status</th><th></th></tr></thead><tbody>
        ${list.map((x) => `<tr class="${x.can_send ? "" : "dis"}">
          <td><input type="checkbox" data-appt="${x.appointment_id}" ${x.can_send ? "" : "disabled"} ${x.can_send && !x.reminder ? "checked" : ""}></td>
          <td>${new Date(x.start).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}</td>
          <td><b>${esc(x.name)}</b><br><span class="muted small">${esc(x.provider)}${x.reason ? " · " + esc(x.reason) : ""}</span></td>
          <td>${x.can_send ? remStatusText(x) : `<span class="muted small">${esc(x.status.replace("_", " "))}</span>`}</td>
          <td style="white-space:nowrap">${x.reminder && x.reminder.status !== "none" ? `<button class="btn small" data-view="${x.reminder.id}">View sent</button>` : ""}
            <button class="btn small" data-preview="${x.appointment_id}">Preview</button></td></tr>`).join("")}</tbody></table>`
        : '<p class="muted">No appointments on this day.</p>'}
    </div>
    <div class="modal-foot"><span class="form-error" id="remErr"></span><button class="btn" onclick="closeModal()">Close</button>
      <button class="btn primary" id="remSend" ${sendable.length ? "" : "disabled"}>Send reminders</button></div>`, { wide: true });

  const boxes = () => [...m.querySelectorAll("input[data-appt]:not(:disabled)")];
  const sync = () => {
    const n = boxes().filter((b) => b.checked).length;
    const btn = m.querySelector("#remSend");
    btn.textContent = n ? `${data.email_enabled ? "Email" : "Save"} ${n} reminder${n === 1 ? "" : "s"}` : "Send reminders";
    btn.disabled = !n;
  };
  boxes().forEach((b) => b.onchange = sync);
  const all = m.querySelector("#remAll");
  if (all) all.onchange = () => { boxes().forEach((b) => b.checked = all.checked); sync(); };
  sync();
  m.querySelector("#remDay").onchange = (e) => e.target.value && openRemindersModal(e.target.value, onDone);
  const back = () => openRemindersModal(day, onDone);
  m.querySelectorAll("[data-preview]").forEach((b) => b.onclick = () => openEmailPreview({ appointmentId: Number(b.dataset.preview), back }));
  m.querySelectorAll("[data-view]").forEach((b) => b.onclick = () => openEmailPreview({ reminderId: Number(b.dataset.view), back }));
  m.querySelector("#remSend").onclick = async () => {
    const ids = boxes().filter((b) => b.checked).map((b) => Number(b.dataset.appt));
    const btn = m.querySelector("#remSend");
    btn.disabled = true; btn.textContent = "Sending…";
    try {
      const res = await api("/api/reminders/send", { method: "POST", body: { appointment_ids: ids, resend: true } });
      const n = res.sent + res.previews;
      toast(res.failed.length ? `${res.failed.length} email${res.failed.length > 1 ? "s" : ""} failed: ${res.failed[0].error}`
        : res.sent ? `✉ ${res.sent} reminder${res.sent > 1 ? "s" : ""} emailed to the demo inbox` : `${n} reminder${n === 1 ? "" : "s"} saved (email is off)`,
        res.failed.length ? "error" : "ok");
      onDone && onDone();
      openRemindersModal(day, onDone);
    } catch (e) { m.querySelector("#remErr").textContent = e.message; btn.disabled = false; sync(); }
  };
}

async function renderReminderRow(el, appt, onChange) {
  let data;
  try { data = await api(`/api/reminders?day=${appt.start.slice(0, 10)}`); } catch (e) { el.innerHTML = ""; return; }
  const s = data.appointments.find((x) => x.appointment_id === appt.id);
  if (!s) { el.innerHTML = '<span class="muted small">-</span>'; return; }
  const sentBefore = s.reminder && s.reminder.status !== "none";
  el.innerHTML = `${remStatusText(s)}
    ${s.can_send ? `<button type="button" class="btn small" data-rem="send" style="margin-left:6px">${sentBefore ? "Resend" : "✉ Send reminder"}</button>` : ""}
    ${sentBefore ? `<button type="button" class="btn small" data-rem="view">View</button>`
                 : `<button type="button" class="btn small" data-rem="preview">Preview</button>`}`;
  const send = el.querySelector('[data-rem="send"]');
  if (send) send.onclick = async () => {
    send.disabled = true; send.textContent = "Sending…";
    try {
      const r = await api("/api/reminders/send", { method: "POST", body: { appointment_ids: [appt.id], resend: true } });
      toast(r.failed.length ? `Email failed: ${r.failed[0].error}` : r.sent ? "✉ Reminder emailed to the demo inbox" : "Reminder saved (email is off)",
            r.failed.length ? "error" : "ok");
    } catch (e) { toast(e.message, "error"); }
    renderReminderRow(el, appt, onChange);
    onChange && onChange();
  };
  const view = el.querySelector('[data-rem="view"]');
  if (view) view.onclick = () => openEmailPreview({ reminderId: s.reminder.id });
  const prev = el.querySelector('[data-rem="preview"]');
  if (prev) prev.onclick = () => openEmailPreview({ appointmentId: appt.id });
}
