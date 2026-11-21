"""Webcam capture with automatic card detection.

Runs in a background thread:
  no_card -> steadying (card found, waiting for it to hold still) -> capture best frame
  -> waiting_removal (won't re-scan the same card) -> no_card ...
"""
import threading
import time
from collections import deque

import cv2
import numpy as np

STABLE_SECONDS = 0.8     # card must hold still this long before auto-capture
MOTION_THRESHOLD = 5.0   # avg brightness change (0-255) inside the card area that still counts as holding still
HOLD_FRAMES = 6          # keep showing the last outline through this many missed detections (no flicker)
MIN_CARD_AREA = 0.08     # card must fill at least this fraction of the frame
GONE_FRAMES = 12         # frames without a card before we re-arm after a capture
DETECT_WIDTH = 640


def list_cameras() -> list[str]:
    """Camera names in DirectShow order (same numbering OpenCV uses with CAP_DSHOW)."""
    try:
        from pygrabber.dshow_graph import FilterGraph
        return FilterGraph().get_input_devices()
    except Exception:
        return []


def pick_camera(name_hint: str, fallback: int) -> int:
    """Index of the first camera whose name contains name_hint (e.g. 'C920'). Lets the app
    find the webcam even if Windows renumbers devices. If it isn't plugged in, use a real
    camera (never a virtual one like OBS, which only shows a placeholder image)."""
    names = list_cameras()
    if not names:
        return fallback
    for i, name in enumerate(names):
        if name_hint and name_hint.lower() in name.lower():
            return i
    real = [i for i, n in enumerate(names) if "virtual" not in n.lower() and "obs" not in n.lower()]
    external = [i for i in real if "integrated" not in names[i].lower()]
    return (external or real or [fallback])[0]


def _order_corners(pts: np.ndarray) -> np.ndarray:
    """Return corners as top-left, top-right, bottom-right, bottom-left."""
    pts = pts.reshape(4, 2).astype(np.float32)
    s, d = pts.sum(axis=1), np.diff(pts, axis=1).ravel()
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]], dtype=np.float32)


CARD_ASPECT = (0.5, 0.97)  # short side / long side; the Patient Health Record card is ~0.75
MIN_SIDE_COVERAGE = 0.5    # each side of the outline must be traced by real edges this much (fingers hide some)
MIN_MEAN_COVERAGE = 0.7
EDGE_STRENGTH = 60         # Sobel gradient needed to count as an edge


def _plausible_card(corners: np.ndarray, width: int, height: int) -> bool:
    """Reject walls, stripes, and backgrounds that merely look like big bright rectangles."""
    tl, tr, br, bl = corners
    w = (np.linalg.norm(tr - tl) + np.linalg.norm(br - bl)) / 2
    h = (np.linalg.norm(bl - tl) + np.linalg.norm(br - tr)) / 2
    if not w or not h or not (CARD_ASPECT[0] <= min(w, h) / max(w, h) <= CARD_ASPECT[1]):
        return False
    margin = 0.01 * max(width, height)
    xs, ys = corners[:, 0], corners[:, 1]
    touching = sum([xs.min() <= margin, ys.min() <= margin, xs.max() >= width - margin, ys.max() >= height - margin])
    return touching < 2  # a held card may clip one edge, but not two


def _side_coverage(corners: np.ndarray, gx: np.ndarray, gy: np.ndarray) -> list[float]:
    """For each side of the quad: fraction of points along it that sit on an edge running
    ALONG that side. Direction matters: hair or fabric has edges everywhere, but pointing
    every which way, so a fake outline through it scores low."""
    h, w = gx.shape
    out = []
    for i in range(4):
        a, b = corners[i], corners[(i + 1) % 4]
        length = np.linalg.norm(b - a)
        d = (b - a) / max(length, 1e-6)
        nrm = np.array([-d[1], d[0]])
        n = max(int(length / 2), 4)
        base = a + (b - a) * np.linspace(0.04, 0.96, n)[:, None]
        hit = np.zeros(n, bool)
        for off in (-1.5, 0.0, 1.5):
            p = (base + nrm * off).round().astype(int)
            ok = (p[:, 0] >= 0) & (p[:, 0] < w) & (p[:, 1] >= 0) & (p[:, 1] < h)
            px, py = p[:, 0].clip(0, w - 1), p[:, 1].clip(0, h - 1)
            g_across = np.abs(gx[py, px] * nrm[0] + gy[py, px] * nrm[1])
            g_along = np.abs(gx[py, px] * d[0] + gy[py, px] * d[1])
            hit |= ok & (g_across > EDGE_STRENGTH) & (g_across > 3.0 * g_along)
        out.append(float(hit.mean()))
    return out


def _intersect(l1, l2):
    """Intersection of two lines given as (point, unit direction)."""
    (p1, d1), (p2, d2) = l1, l2
    m = np.array([[d1[0], -d2[0]], [d1[1], -d2[1]]], dtype=np.float64)
    if abs(np.linalg.det(m)) < 1e-6:
        return None
    t = np.linalg.solve(m, p2 - p1)[0]
    return p1 + d1 * t


def _line_quads(edges: np.ndarray, min_side: float, max_lines: int = 12) -> list[np.ndarray]:
    """Card outlines built from long straight lines (the paper edge or the printed border).
    Works even when fingers break the outline, because each side only needs to be a line."""
    segs = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=40, minLineLength=int(min_side * 0.5), maxLineGap=15)
    if segs is None:
        return []
    # merge collinear segments into lines: (angle, offset, point, direction, total length)
    lines = []
    for x1, y1, x2, y2 in segs.reshape(-1, 4).astype(np.float64):
        d = np.array([x2 - x1, y2 - y1]); length = np.linalg.norm(d)
        d /= length
        if d[0] < 0 or (d[0] == 0 and d[1] < 0):
            d = -d
        ang = np.arctan2(d[1], d[0])  # in (-pi/2, pi/2]
        normal = np.array([-d[1], d[0]])
        p = np.array([x1, y1]); off = float(p @ normal)
        for ln in lines:
            if abs(ln[0] - ang) < np.deg2rad(3) and abs(ln[1] - off) < 6:
                ln[4] += length
                break
        else:
            lines.append([ang, off, p, d, length])
    lines = sorted(lines, key=lambda l: -l[4])[:max_lines]

    # pairs of roughly parallel lines far enough apart to be opposite card sides
    pairs = []
    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            a, b = lines[i], lines[j]
            dang = abs(a[0] - b[0])
            dang = min(dang, np.pi - dang)
            if dang < np.deg2rad(15):
                sep = abs((b[2] - a[2]) @ np.array([-a[3][1], a[3][0]]))
                if sep >= min_side:
                    pairs.append((a, b, (a[0] + b[0]) / 2 if abs(a[0] - b[0]) < np.pi / 2 else a[0]))
    quads = []
    for i in range(len(pairs)):
        for j in range(i + 1, len(pairs)):
            (a1, a2, angA), (b1, b2, angB) = pairs[i], pairs[j]
            dang = abs(angA - angB) % np.pi
            if not (np.deg2rad(60) <= dang <= np.deg2rad(120)):
                continue
            pts = [_intersect((a[2], a[3]), (b[2], b[3])) for a, b in ((a1, b1), (a1, b2), (a2, b2), (a2, b1))]
            if any(p is None for p in pts):
                continue
            quad = _order_corners(np.array(pts))
            if cv2.isContourConvex(quad.reshape(-1, 1, 2)):
                quads.append(quad)
    return quads


def _contour_quads(edges: np.ndarray, min_area: float) -> list[np.ndarray]:
    """Card outlines from closed contours (the easy case: clean outline, no fingers in the way)."""
    found, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    quads = []
    for c in found:
        hull = cv2.convexHull(c)
        if cv2.contourArea(hull) < min_area:
            continue
        peri = cv2.arcLength(hull, True)
        for eps in (0.02, 0.04):
            approx = cv2.approxPolyDP(hull, eps * peri, True)
            if len(approx) == 4:
                quads.append(_order_corners(approx))
                break
    return quads


def _looks_like_paper(gray: np.ndarray, quad: np.ndarray, ink: np.ndarray) -> bool:
    """Mostly bright, with some printed ink (blank walls and doors have none)."""
    mask = np.zeros_like(gray)
    cv2.fillPoly(mask, [quad.astype(np.int32)], 255)
    return np.median(gray[mask > 0]) >= 90 and (ink[mask > 0] > 0).mean() >= 0.03


def _quick_quad(gray: np.ndarray, ink: np.ndarray, min_area: float) -> np.ndarray | None:
    """Fast path: the card's outline is a clean closed shape (card against a contrasting
    background, edges not covered)."""
    sh, sw = gray.shape
    edges = cv2.dilate(cv2.Canny(gray, 40, 120), np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
        if cv2.contourArea(c) < min_area:
            break
        approx = cv2.approxPolyDP(c, 0.02 * cv2.arcLength(c, True), True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            quad = _order_corners(approx)
            if _plausible_card(quad, sw, sh) and _looks_like_paper(gray, quad, ink):
                return quad
    return None


def _find_quad(gray: np.ndarray, min_area: float, accept=None) -> np.ndarray | None:
    """Exact card outline in a grayscale image, or None.

    Candidate outlines come from closed contours and from long straight lines; each is
    scored by how much of its outline is traced by real edges in the image. A finger only
    hides a small gap, while a fake rectangle (e.g. wall stripe + card side) has long
    stretches with no edge. Candidates must also look like paper with ink on it.
    """
    sh, sw = gray.shape
    min_side = np.sqrt(min_area * CARD_ASPECT[0])
    edges = cv2.Canny(gray, 40, 120)
    edges_d = cv2.dilate(edges, np.ones((3, 3), np.uint8))
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)

    candidates, seen = [], set()
    for quad in _contour_quads(edges_d, min_area) + _line_quads(edges, min_side):
        key = tuple((quad / 4).round().astype(int).ravel())
        if key in seen or not _plausible_card(quad, sw, sh):
            continue
        seen.add(key)
        area = cv2.contourArea(quad)
        if area >= min_area:
            candidates.append((area, quad))

    # Every outline that passes is a real printed/paper rectangle; the biggest is the card
    # itself (smaller ones are the section boxes printed on it). Check biggest first.
    ink = None
    for area, quad in sorted(candidates, key=lambda c: -c[0]):
        cov = _side_coverage(quad, gx, gy)
        if min(cov) < MIN_SIDE_COVERAGE or sum(cov) / 4 < MIN_MEAN_COVERAGE:
            continue
        if ink is None:
            ink = _ink(gray)
        if _looks_like_paper(gray, quad, ink) and (accept is None or accept(quad)):
            return quad
    return None


def _ink(gray: np.ndarray) -> np.ndarray:
    """Dark-on-light strokes (printed lines, text, handwriting)."""
    return cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 21, 12)


def _card_region(gray: np.ndarray, ink: np.ndarray) -> tuple[tuple[int, int, int, int], np.ndarray] | None:
    """Rough card location: the biggest bright area densely covered in printed ink.
    Cheap (~10 ms) and doesn't need the card's edges, so fingers and white walls don't matter."""
    sh, sw = gray.shape
    density = cv2.blur(ink.astype(np.float32) / 255, (21, 21))
    bright = cv2.blur((gray > 120).astype(np.float32), (21, 21))
    mask = ((density > 0.05) & (density < 0.35) & (bright > 0.6)).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))
    found, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not found:
        return None
    c = max(found, key=cv2.contourArea)
    if cv2.contourArea(c) < 0.06 * sh * sw:
        return None
    x, y, w, h = cv2.boundingRect(c)
    blob = np.zeros_like(mask)
    cv2.drawContours(blob, [c], -1, 255, -1)
    return (x, y, x + w, y + h), blob


def _box_corners(x0, y0, x1, y1) -> np.ndarray:
    return np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], dtype=np.float32)


def find_card(frame: np.ndarray, full_search: bool = True) -> np.ndarray | None:
    """Card corners in full-resolution coords, or None.

    1. Fast path: the card's outline is a clean closed shape.
    2. Otherwise find roughly where the card is (bright + dense printed ink) and look for
       the exact outline only inside that area, where hair/stripes elsewhere can't distract it.
    3. No exact outline (e.g. fingers over the edges)? Still scan, using a box around the
       card; the AI reads it fine without perfect corners.
    full_search: if no rough area is found, also try an exact-outline search over the
    whole frame (slower; the camera loop does this only on some frames).
    """
    scale = DETECT_WIDTH / frame.shape[1]
    small = cv2.resize(frame, None, fx=scale, fy=scale)
    sh, sw = small.shape[:2]
    gray = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), (3, 3), 0)

    ink = _ink(gray)
    quad = _quick_quad(gray, ink, MIN_CARD_AREA * sh * sw)
    if quad is not None:
        return quad / scale

    region = _card_region(gray, ink)
    if region is not None:
        (x0, y0, x1, y1), blob = region
        px, py = int((x1 - x0) * 0.2), int((y1 - y0) * 0.2)
        rx0, ry0, rx1, ry1 = max(x0 - px, 0), max(y0 - py, 0), min(x1 + px, sw), min(y1 + py, sh)
        roi = gray[ry0:ry1, rx0:rx1]
        roi_blob = blob[ry0:ry1, rx0:rx1]
        blob_px = max(int((roi_blob > 0).sum()), 1)

        def covers_card(quad):
            # must contain nearly all of the card's ink, or it's a section box printed on the card
            m = np.zeros_like(roi_blob)
            cv2.fillPoly(m, [quad.astype(np.int32)], 255)
            return ((m > 0) & (roi_blob > 0)).sum() / blob_px >= 0.9

        quad = _find_quad(roi, 0.25 * roi.shape[0] * roi.shape[1], accept=covers_card)
        if quad is not None:
            return (quad + [rx0, ry0]) / scale
        # No exact outline: scan a generous box around the card. Too big is harmless (we crop
        # from the full-resolution frame); cutting off part of the card is not.
        return _box_corners(rx0, ry0, rx1 - 1, ry1 - 1) / scale
    if full_search:
        quad = _find_quad(gray, MIN_CARD_AREA * sh * sw)
        if quad is not None:
            return quad / scale
    return None


def warp_card(frame: np.ndarray, corners: np.ndarray) -> np.ndarray:
    """Flatten the card to a straight-on rectangle."""
    tl, tr, br, bl = corners
    w = int(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
    h = int(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
    dst = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], dtype=np.float32)
    return cv2.warpPerspective(frame, cv2.getPerspectiveTransform(corners, dst), (w, h))


def sharpness(img: np.ndarray) -> float:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, (800, int(800 * gray.shape[0] / gray.shape[1])))
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def encode_jpeg(img: np.ndarray, quality: int = 92) -> bytes:
    return cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])[1].tobytes()


class Camera:
    def __init__(self, index: int, on_capture):
        self.index = index
        self.on_capture = on_capture  # called with JPEG bytes of the flattened card
        self.auto = True              # auto-capture when a card holds still
        self.busy = False             # set by the app while a scan is being processed
        self.state = "starting"
        self.progress = 0.0
        self.preview: bytes | None = None
        self._frame: np.ndarray | None = None
        self._corners: np.ndarray | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ---- lifecycle -------------------------------------------------------
    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)

    def switch(self, index: int):
        self.stop()
        self.index = index
        self.preview = None
        self.start()

    # ---- manual capture --------------------------------------------------
    def snapshot(self) -> bytes | None:
        """Current card (flattened if detected, else the full frame)."""
        with self._lock:
            frame, corners = self._frame, self._corners
        if frame is None:
            return None
        return encode_jpeg(warp_card(frame, corners) if corners is not None else frame)

    # ---- main loop -------------------------------------------------------
    def _open(self) -> cv2.VideoCapture:
        cap = cv2.VideoCapture(self.index, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))  # needed for 1080p30 on the C920
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        return cap

    def _run(self):
        cap = self._open()
        if not cap.isOpened():
            self.state = "no_camera"
            return
        prev_small = None
        stable_since = None
        candidates: deque = deque(maxlen=8)  # (sharpness, frame, corners) during the stable window
        gone = 0
        waiting_removal = False
        last_seen, misses = None, 0

        while not self._stop.is_set():
            ok, frame = cap.read()
            if not ok:
                self.state = "no_camera"
                time.sleep(0.2)
                continue
            corners = find_card(frame, full_search=False)
            # brief misses (a finger shifts, a reflection) keep the last outline instead of resetting
            if corners is not None:
                last_seen, misses = corners, 0
            elif last_seen is not None and misses < HOLD_FRAMES:
                corners, misses = last_seen, misses + 1
            else:
                last_seen = None
            with self._lock:
                self._frame, self._corners = frame, corners
            now = time.time()

            # "holding still" = the picture itself isn't changing, measured on a tiny copy
            small = cv2.cvtColor(cv2.resize(frame, (160, 90)), cv2.COLOR_BGR2GRAY).astype(np.float32)
            motion = np.inf
            if prev_small is not None and corners is not None:
                sx, sy = 160 / frame.shape[1], 90 / frame.shape[0]
                x0, y0 = int(max(corners[:, 0].min() * sx, 0)), int(max(corners[:, 1].min() * sy, 0))
                x1, y1 = int(min(corners[:, 0].max() * sx + 1, 160)), int(min(corners[:, 1].max() * sy + 1, 90))
                if x1 > x0 and y1 > y0:
                    motion = float(np.abs(small[y0:y1, x0:x1] - prev_small[y0:y1, x0:x1]).mean())
            prev_small = small

            if corners is None:
                gone += 1
                if gone >= GONE_FRAMES:
                    waiting_removal = False
                stable_since = None
                candidates.clear()
                self.state, self.progress = ("waiting_removal" if waiting_removal else "no_card"), 0.0
            else:
                gone = 0
                if waiting_removal or self.busy or not self.auto:
                    self.state = "waiting_removal" if waiting_removal else ("busy" if self.busy else "manual")
                    self.progress = 0.0
                elif motion > MOTION_THRESHOLD:
                    stable_since = now
                    candidates.clear()
                    self.state, self.progress = "steadying", 0.0
                else:
                    stable_since = stable_since or now
                    candidates.append((sharpness(frame), frame, corners))
                    self.progress = min(1.0, (now - stable_since) / STABLE_SECONDS)
                    self.state = "steadying"
                    if self.progress >= 1.0 and candidates:
                        _, best_frame, best_corners = max(candidates, key=lambda c: c[0])
                        candidates.clear()
                        waiting_removal = True
                        self.state = "captured"
                        self.on_capture(encode_jpeg(warp_card(best_frame, best_corners)))

            self.preview = encode_jpeg(self._overlay(frame, corners), quality=70)
        cap.release()

    def _overlay(self, frame: np.ndarray, corners: np.ndarray | None) -> np.ndarray:
        view = cv2.resize(frame, (960, int(960 * frame.shape[0] / frame.shape[1])))
        if corners is not None:
            s = 960 / frame.shape[1]
            color = {"captured": (80, 200, 80), "waiting_removal": (80, 200, 80)}.get(self.state, (0, 200, 255))
            cv2.polylines(view, [(corners * s).astype(np.int32)], True, color, 4)
            if self.state == "steadying":
                h = view.shape[0]
                cv2.rectangle(view, (0, h - 10), (int(960 * self.progress), h), (0, 200, 255), -1)
        return view
