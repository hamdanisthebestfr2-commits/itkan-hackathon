"""FastAPI server: scanner page, mock CRM page, live camera feed, and scan pipeline."""
import asyncio
import json
import time
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import ambient, billing, clinic, config, crm, epcs, labs, reader, seed, summary, validate
from . import eligibility, ledger, portal, reminders  # Track B
from .camera import Camera, list_cameras, pick_camera
from .ambient import router as ambient_router
from .billing_api import router as billing_router
from .clinic_api import router as clinic_router
from .dashboard import router as dashboard_router
from .epcs import router as epcs_router
from .caregaps import router as caregaps_router
from .inbox import router as inbox_router
from .summary import router as summary_router
from .labs import router as labs_router
from .portal import router as portal_router  # Track B
from .eligibility import router as eligibility_router  # Track B
from .ledger import router as ledger_router  # Track B
from .reminders import router as reminders_router  # Track B
from .events import broadcast, subscribers

settings = {"auto_capture": True, "auto_accept": False}
pending: dict[str, dict] = {}       # scan_id -> review result awaiting submit
camera: Camera | None = None
loop: asyncio.AbstractEventLoop | None = None


async def process_scan(jpeg: bytes, source: str) -> None:
    if camera:
        camera.busy = True
    scan_id = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    try:
        started = time.time()
        image = reader.prepare_image(jpeg)
        (config.SCANS_DIR / f"{scan_id}.jpg").write_bytes(image)
        image_url = f"/scans/{scan_id}.jpg"
        broadcast({"type": "captured", "scan_id": scan_id, "image": image_url, "source": source})

        reading = await reader.read_card(image)
        result = validate.review(reading)
        seconds = round(time.time() - started, 1)
        event = {"type": "result", "scan_id": scan_id, "image": image_url, "seconds": seconds, **result}
        pending[scan_id] = {"result": result, "image": image_url, "seconds": seconds, "event": event}
        broadcast(event)

        if settings["auto_accept"] and result["all_clear"]:
            values = {k: f["value"] for k, f in result["fields"].items()}
            await submit(SubmitBody(scan_id=scan_id, values=values, auto=True))
    except reader.ReaderError as e:
        broadcast({"type": "error", "scan_id": scan_id, "message": str(e)})
    except Exception as e:  # keep the demo alive no matter what
        broadcast({"type": "error", "scan_id": scan_id, "message": f"Unexpected error: {e}"})
    finally:
        if camera:
            camera.busy = False


def on_camera_capture(jpeg: bytes) -> None:
    """Called from the camera thread."""
    asyncio.run_coroutine_threadsafe(process_scan(jpeg, "camera"), loop)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global camera, loop
    loop = asyncio.get_running_loop()
    crm.init()
    clinic.init()
    billing.init()
    ambient.init()
    epcs.init()
    labs.init()
    summary.init()
    portal.init()  # Track B
    eligibility.init()  # Track B
    ledger.init()  # Track B
    reminders.init()  # Track B
    if clinic.is_empty():
        seed.seed()
    camera = Camera(pick_camera(config.CAMERA_NAME, config.CAMERA_INDEX), on_camera_capture)
    camera.start()
    yield
    camera.stop()


app = FastAPI(lifespan=lifespan)
app.include_router(clinic_router)
app.include_router(billing_router)
app.include_router(dashboard_router)
app.include_router(ambient_router)
app.include_router(epcs_router)
app.include_router(labs_router)
app.include_router(inbox_router)
app.include_router(caregaps_router)
app.include_router(summary_router)
app.include_router(portal_router)  # Track B
app.include_router(eligibility_router)  # Track B
app.include_router(ledger_router)  # Track B
app.include_router(reminders_router)  # Track B
app.mount("/scans", StaticFiles(directory=config.SCANS_DIR), name="scans")
app.mount("/static", StaticFiles(directory=config.WEB_DIR / "static"), name="static")

# page routes -> html files (no build step)
PAGES = {
    "/": "dashboard.html", "/patients": "patients.html", "/patient": "patient.html",
    "/schedule": "schedule.html", "/visit": "visit.html", "/pharmacy": "pharmacy.html",
    "/inbox": "inbox.html", "/billing": "billing.html", "/claim-form": "claim-form.html", "/savings": "savings.html",
    "/scan": "scanner.html", "/crm": "crm.html",
    "/portal": "portal.html", "/statement": "statement.html",  # Track B
}


def _page(filename: str):
    return lambda: FileResponse(config.WEB_DIR / filename)


for _path, _file in PAGES.items():
    app.add_api_route(_path, _page(_file), methods=["GET"], include_in_schema=False)


# ---- camera ---------------------------------------------------------------
@app.get("/video")
async def video():
    async def frames():
        last = None
        while True:
            frame = camera.preview if camera else None
            if frame is not None and frame is not last:
                last = frame
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            await asyncio.sleep(0.05)

    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/api/cameras")
def cameras():
    names = list_cameras()
    return [{"index": i, "name": n} for i, n in enumerate(names)] or [{"index": i, "name": f"Camera {i}"} for i in range(4)]


@app.get("/api/status")
def status():
    return {
        "camera_state": camera.state if camera else "no_camera",
        "progress": camera.progress if camera else 0,
        "camera_index": camera.index if camera else None,
        "busy": camera.busy if camera else False,
        **settings,
    }


class SettingsBody(BaseModel):
    auto_capture: bool | None = None
    auto_accept: bool | None = None
    camera_index: int | None = None


@app.post("/api/settings")
def update_settings(body: SettingsBody):
    if body.auto_capture is not None:
        settings["auto_capture"] = body.auto_capture
        camera.auto = body.auto_capture
    if body.auto_accept is not None:
        settings["auto_accept"] = body.auto_accept
    if body.camera_index is not None and body.camera_index != camera.index:
        camera.switch(body.camera_index)
    return status()


# ---- scanning -------------------------------------------------------------
@app.post("/api/scan")
async def scan_now():
    jpeg = camera.snapshot() if camera else None
    if jpeg is None:
        raise HTTPException(503, "Camera not ready")
    asyncio.create_task(process_scan(jpeg, "manual"))
    return {"ok": True}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    asyncio.create_task(process_scan(await file.read(), "upload"))
    return {"ok": True}


class SubmitBody(BaseModel):
    scan_id: str
    values: dict[str, str | None]
    auto: bool = False


@app.post("/api/submit")
async def submit(body: SubmitBody):
    scan = pending.pop(body.scan_id, None)
    if scan is None:
        raise HTTPException(404, "Scan not found or already submitted")
    fields = scan["result"]["fields"]
    values = {k: (v.strip() if isinstance(v, str) and v.strip() else None) for k, v in body.values.items()}
    changed = sum(1 for k, f in fields.items() if (values.get(k) or "") != (f["value"] or ""))
    filled = sum(1 for v in values.values() if v)
    alerts = validate.clinical_alerts(values)
    saved = crm.save_screening(values, {
        "alerts": alerts,
        "needs_follow_up": any(a["level"] in ("urgent", "follow_up") for a in alerts),
        "image": scan["image"],
        "auto_accepted": max(filled - changed, 0),
        "corrected": changed,
        "seconds": scan["seconds"],
    })
    visit = clinic.record_scan(values, scan["image"], alerts)
    broadcast({"type": "crm_saved", **saved, **visit, "auto": body.auto, "values": values, "alerts": alerts})
    return {**saved, **visit}


@app.get("/api/pending")
def latest_pending():
    """Most recent scan awaiting review, so a page refresh doesn't lose it."""
    return pending[max(pending)]["event"] if pending else None


@app.post("/api/discard/{scan_id}")
def discard(scan_id: str):
    pending.pop(scan_id, None)
    return {"ok": True}


@app.get("/api/events")
async def events():
    q: asyncio.Queue = asyncio.Queue()
    subscribers.add(q)

    async def stream():
        try:
            yield "retry: 1000\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            subscribers.discard(q)

    return StreamingResponse(stream(), media_type="text/event-stream")


# ---- CRM ------------------------------------------------------------------
@app.get("/api/crm/contacts")
def crm_contacts(q: str = ""):
    return crm.list_contacts(q)


@app.get("/api/crm/contacts/{contact_id}")
def crm_contact(contact_id: str):
    contact = crm.get_contact(contact_id)
    if contact is None:
        raise HTTPException(404, "Contact not found")
    return contact


@app.get("/api/crm/stats")
def crm_stats():
    return crm.stats()


@app.post("/api/crm/reset")
def crm_reset():
    crm.reset()
    broadcast({"type": "crm_reset"})
    return {"ok": True}
