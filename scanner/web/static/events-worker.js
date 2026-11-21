// One live-update connection (/api/events) shared by every open tab of the app.
// Why: browsers allow only 6 open connections per site over HTTP/1.1. Each tab used to hold its own
// never-ending event stream (and the Scan page also holds the camera video), so with ~5 tabs open every
// new page stalled on "Loading…" / "Failed to fetch". A SharedWorker keeps it to ONE connection total.
const ports = new Set();
let es = null;

function connect() {
  es = new EventSource("/api/events");   // reconnects by itself if the server restarts
  es.onmessage = (m) => {
    for (const p of ports) {
      try { p.postMessage(m.data); } catch (e) { ports.delete(p); }
    }
  };
}

onconnect = (e) => {
  const port = e.ports[0];
  ports.add(port);
  port.onmessage = (m) => { if (m.data === "bye") ports.delete(port); };   // tab closing
  port.start();
  if (!es) connect();
};
