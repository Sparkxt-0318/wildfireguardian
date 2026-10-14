"""Fullscreen live check window (sitting 1, check A).

It exercises the real live architecture on the real hardware:
- capture runs in its own thread (a SourceChain or a single source), keeping only the
  newest frame;
- a processing QThread runs the detector and emits an immutable Result through a queued
  signal; the Result owns its pre-scaled image buffer;
- the GUI thread only paints the newest Result.

It shows the camera picture with detected embers in orange, a large green detection
count, the frame rate and the capture-to-paint latency, and toggles Korean and English
with L. Esc or the time limit ends it. run_live_check returns timing statistics for the
sitting report.
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import cv2
import numpy as np

from PySide6.QtCore import QObject, QRectF, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

from wfglink.config import load_config
from wfglink.detect.candidates import Detector
from wfglink.io.capture import SourceChain
from wfglink.ui.fonts import ui_font

GREEN = QColor("#30D158")
ORANGE = QColor("#FF9F0A")
WHITE = QColor("#FFFFFF")
GRAY = QColor("#8E8E93")

TEXT = {
    "ko": {"count": "검출된 불티", "fps": "초당 프레임", "latency": "지연", "check": "카메라 점검 A", "hint": "L 언어 · Esc 종료",
           "waiting": "카메라 연결 중"},
    "en": {"count": "Detected embers", "fps": "Frames per second", "latency": "Latency", "check": "Camera check A",
           "hint": "L language · Esc quit", "waiting": "Connecting camera"},
}


@dataclass
class Result:
    image: np.ndarray              # BGR uint8, already scaled to the drawing size
    qimage: QImage                 # wraps `image`; valid while this Result lives
    xs: np.ndarray                 # detection positions in drawing coordinates
    ys: np.ndarray
    n: int
    t_wall_capture: float
    proc_ms: float
    source_label: str
    source_state: str
    meta: dict[str, Any] = field(default_factory=dict)


class ProcessingThread(QThread):
    result_ready = Signal(object)

    def __init__(self, get_frame: Callable[[], tuple[Any, Any]], target_size: Callable[[], tuple[int, int]], cfg: dict):
        super().__init__()
        self.get_frame = get_frame
        self.target_size = target_size
        self.detector = Detector(cfg)
        self._running = True
        self._last_index: tuple[str, int] | None = None
        self.proc_ms: list[float] = []

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        while self._running:
            frame, status = self.get_frame()
            key = (getattr(status, "key", "") or "", frame.index) if frame is not None else None
            if frame is None or key == self._last_index:
                self.msleep(2)
                continue
            self._last_index = key
            t0 = time.perf_counter()
            det = self.detector.detect(frame.image)
            w, h = self.target_size()
            ih, iw = frame.image.shape[:2]
            s = min(w / iw, h / ih)
            dw, dh = max(1, int(iw * s)), max(1, int(ih * s))
            img = cv2.resize(frame.image, (dw, dh), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR)
            img = np.ascontiguousarray(img)
            qimg = QImage(img.data, dw, dh, img.strides[0], QImage.Format.Format_BGR888)
            ms = (time.perf_counter() - t0) * 1000
            self.proc_ms.append(ms)
            self.result_ready.emit(Result(img, qimg, det.x * s, det.y * s, len(det), frame.t_wall, ms,
                                          getattr(status, "label", "") or getattr(status, "key", "") or "",
                                          getattr(status, "state", "live"), dict(frame.meta)))


class CheckWindow(QWidget):
    def __init__(self, lang: str = "ko"):
        super().__init__()
        self.setWindowTitle("wfglink check A")
        self.setStyleSheet("background-color: #000000;")
        self.setCursor(Qt.CursorShape.BlankCursor)
        self.lang = lang
        self.result: Result | None = None
        self.paint_times: list[float] = []
        self.latencies: list[float] = []
        self.counts: list[int] = []
        self.toggles = 0

    def on_result(self, r: Result) -> None:
        self.result = r
        self.update()

    def keyPressEvent(self, ev) -> None:  # noqa: N802 (Qt naming)
        if ev.key() == Qt.Key.Key_L:
            self.lang = "en" if self.lang == "ko" else "ko"
            self.toggles += 1
            self.update()
        elif ev.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Q):
            self.close()

    def paintEvent(self, ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#000000"))
        W, H = self.width(), self.height()
        txt = TEXT[self.lang]
        r = self.result
        if r is not None:
            ih, iw = r.image.shape[:2]
            ox, oy = (W - iw) // 2, (H - ih) // 2
            p.drawImage(ox, oy, r.qimage)
            pen = QPen(ORANGE, 2)
            p.setPen(pen)
            for x, y in zip(r.xs, r.ys):
                p.drawEllipse(QRectF(ox + x - 7, oy + y - 7, 14, 14))
            self.latencies.append((time.monotonic() - r.t_wall_capture) * 1000)
            self.counts.append(r.n)
            # Large green count, top left.
            p.setPen(GREEN)
            p.setFont(ui_font(max(48, H // 10), "semibold"))
            p.drawText(QRectF(40, 30, W / 2, H / 8), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, f"{r.n}")
            p.setPen(WHITE)
            p.setFont(ui_font(max(18, H // 36)))
            p.drawText(QRectF(42, 30 + H / 8, W / 2, H / 20), Qt.AlignmentFlag.AlignLeft, txt["count"])
        else:
            p.setPen(GRAY)
            p.setFont(ui_font(max(24, H // 24)))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, txt["waiting"])
        now = time.monotonic()
        self.paint_times.append(now)
        recent = [t for t in self.paint_times[-60:] if now - t < 2.0]
        fps = (len(recent) - 1) / (recent[-1] - recent[0]) if len(recent) > 2 else 0.0
        lat = np.median(self.latencies[-30:]) if self.latencies else float("nan")
        p.setPen(GRAY)
        p.setFont(ui_font(max(16, H // 50)))
        src = f"{r.source_label} · {r.source_state}" if r is not None else ""
        line = f"{txt['check']}   {src}   {txt['fps']} {fps:.0f}   {txt['latency']} {lat:.0f} ms   {txt['hint']}"
        p.drawText(QRectF(40, H - 60, W - 80, 40), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, line)
        p.end()


def choose_screen(app: QGuiApplication, preference: str = "external"):
    screens = app.screens()
    primary = app.primaryScreen()
    if preference not in ("external", "primary"):
        for s in screens:
            if s.name() == preference:
                return s
    if preference == "external":
        for s in screens:
            if s is not primary:
                return s
    return primary


def run_live_check(chain: SourceChain, duration_s: float = 20.0, screen: str = "external",
                   lang: str = "ko", cfg: dict | None = None) -> dict[str, Any]:
    """Show the fullscreen check window for `duration_s` seconds and return statistics."""
    cfg = cfg or load_config()
    app = QApplication.instance() or QApplication(sys.argv[:1])
    win = CheckWindow(lang)
    scr = choose_screen(app, screen)
    win.setScreen(scr)
    win.setGeometry(scr.geometry())
    win.showFullScreen()
    size = (win.width() or scr.geometry().width(), win.height() or scr.geometry().height())

    def target_size() -> tuple[int, int]:
        dpr = win.devicePixelRatioF()
        return int(win.width() * dpr) or size[0], int(win.height() * dpr) or size[1]

    worker = ProcessingThread(chain.latest, target_size, cfg)
    worker.result_ready.connect(win.on_result, Qt.ConnectionType.QueuedConnection)
    worker.start()
    t0 = time.monotonic()
    QTimer.singleShot(int(duration_s * 1000), win.close)
    closed = {"done": False}
    win.destroyed.connect(lambda *_: closed.update(done=True))
    while win.isVisible() and time.monotonic() - t0 < duration_s + 2:
        app.processEvents()
        time.sleep(0.002)
    worker.stop()
    if not worker.wait(5000):
        worker.terminate()
        worker.wait(1000)
    elapsed = time.monotonic() - t0
    pt = np.array(win.paint_times)
    paint_fps = float((len(pt) - 1) / (pt[-1] - pt[0])) if len(pt) > 2 else 0.0
    lat = np.array(win.latencies) if win.latencies else np.array([np.nan])
    proc = np.array(worker.proc_ms) if worker.proc_ms else np.array([np.nan])
    geom = scr.geometry()
    win.deleteLater()
    app.processEvents()
    return {
        "duration_s": round(elapsed, 2),
        "results_painted": len(win.latencies),
        "paint_fps": round(paint_fps, 1),
        "processed_frames": len(worker.proc_ms),
        "processing_ms_median": round(float(np.nanmedian(proc)), 2),
        "processing_ms_p95": round(float(np.nanpercentile(proc, 95)), 2),
        "latency_ms_median": round(float(np.nanmedian(lat)), 1),
        "latency_ms_p95": round(float(np.nanpercentile(lat, 95)), 1),
        "detections_mean": round(float(np.mean(win.counts)), 2) if win.counts else 0.0,
        "language_toggles": win.toggles,
        "screen": {"name": scr.name(), "geometry": [geom.x(), geom.y(), geom.width(), geom.height()],
                   "dpr": scr.devicePixelRatio(), "refresh_hz": round(scr.refreshRate(), 1),
                   "is_primary": scr is app.primaryScreen(), "n_screens": len(app.screens())},
        "qt_platform": app.platformName(),
    }
