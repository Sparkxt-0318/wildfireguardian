"""A fullscreen camera preview for `calibrate` and `record` (Qt).

The camera is read on a capture thread that keeps only the newest frame; `on_capture`, when
given, also runs there for every frame (recording must not lose frames when the window is
busy). The window shows the newest frame mirrored (like a mirror, so the person at the
standing spot can place themselves), with what `on_frame` returns: outlines, text lines at
the bottom and a big centred text. It goes fullscreen on the booth's screen (the external
monitor when one is connected, as `live --screen auto`). Esc closes it early.

Camera permission (macOS) is asked on the main thread before the capture thread starts.
"""
from __future__ import annotations

import os
import platform
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from wfglink.io.frames import Frame


@dataclass
class Overlay:
    lines: list[str] = field(default_factory=list)              # text under the picture
    polygons: list[np.ndarray] = field(default_factory=list)   # outlines, in the mirrored picture's px
    big: str = ""                                               # a big text in the middle of the picture
    color: str = "#30D158"                                      # outlines
    text_color: str = "#FFFFFF"
    done: bool = False


class LatestFrame(threading.Thread):
    """Reads a source until stopped, keeping the newest frame."""

    def __init__(self, source: Any, on_capture: Callable[[Frame], None] | None = None):
        super().__init__(daemon=True, name="wfglink-preview-capture")
        self.source = source
        self.on_capture = on_capture
        self.frame: Frame | None = None
        self.count = 0
        self.error: str | None = None
        self._halt = threading.Event()
        self._lock = threading.Lock()

    def run(self) -> None:
        try:
            while not self._halt.is_set():
                f = self.source.read()
                if f is None:
                    if not getattr(self.source, "is_live", False):
                        break
                    continue
                if self.on_capture is not None:
                    self.on_capture(f)
                with self._lock:
                    self.frame = f
                    self.count += 1
        except Exception as exc:          # reported in the window and to the caller
            self.error = f"{type(exc).__name__}: {exc}"

    def latest(self) -> Frame | None:
        with self._lock:
            return self.frame

    def stop(self) -> None:
        self._halt.set()


def open_camera(cfg: dict) -> Any:
    """The configured camera, opened, after asking for permission on this (main) thread."""
    from wfglink.io.camera import CameraSource, request_permission

    request_permission(float((cfg.get("camera") or {}).get("permission_timeout_s", 30)))
    src = CameraSource(cfg)
    src.open()
    return src


def run_preview(cfg: dict, on_frame: Callable[[Frame], Overlay], *, screen: str | None = None,
                timeout_s: float | None = None, source: Any = None, done_hold_s: float = 3.0,
                on_capture: Callable[[Frame], None] | None = None) -> dict[str, Any]:
    if platform.system() != "Darwin" and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
    from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF
    from PySide6.QtWidgets import QApplication, QWidget

    from wfglink.ui.fonts import load_fonts, ui_font

    src = source if source is not None else open_camera(cfg)
    if source is not None and getattr(src, "state", "") in ("closed", ""):
        src.open()
    app = QApplication.instance() or QApplication(sys.argv[:1])
    load_fonts()
    cap = LatestFrame(src, on_capture)
    cap.start()
    info: dict[str, Any] = {"camera": getattr(src, "name", ""), "unique_id": (getattr(src, "info", {}) or {}).get("unique_id"),
                            "backend": (getattr(src, "info", {}) or {}).get("backend"), "cancelled": False}

    class Window(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("wfglink")
            self.setStyleSheet("background: black;")
            self.img: np.ndarray | None = None
            self.ov = Overlay(lines=["카메라를 여는 중 · Opening the camera"])
            self.last_index = -1
            self.t0 = time.monotonic()
            self.t_done: float | None = None

        def keyPressEvent(self, ev) -> None:  # noqa: N802
            if ev.key() == Qt.Key.Key_Escape:
                info["cancelled"] = True
                self.close()

        def tick(self) -> None:
            now = time.monotonic()
            if cap.error:
                self.ov = Overlay(lines=[f"camera: {cap.error}"], color="#FF453A")
                info["error"] = cap.error
            f = cap.latest()
            if f is not None and f.index != self.last_index:
                self.last_index = f.index
                self.ov = on_frame(f)
                self.img = np.ascontiguousarray(f.image[:, ::-1])
                if self.ov.done and self.t_done is None:
                    self.t_done = now
            if self.t_done is not None and now - self.t_done >= done_hold_s:
                self.close()
            elif timeout_s and now - self.t0 > timeout_s and self.t_done is None:
                info["timed_out"] = True
                self.close()
            self.update()

        def paintEvent(self, ev) -> None:  # noqa: N802
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            W, H = self.width(), self.height()
            p.fillRect(QRectF(0, 0, W, H), QColor("#000000"))
            p.setFont(ui_font(max(14, int(H * 0.03))))
            line_h = p.fontMetrics().height()
            band = max(0.12 * H, (len(self.ov.lines) + 1.2) * line_h)      # room for every line under the picture
            if self.img is not None:
                ih, iw = self.img.shape[:2]
                s = min(W / iw, (H - band) / ih)
                ox, oy = (W - iw * s) / 2, (H - band - ih * s) / 2
                q = QImage(self.img.data, iw, ih, self.img.strides[0], QImage.Format.Format_BGR888)
                p.drawImage(QRectF(ox, oy, iw * s, ih * s), q)
                pen = QPen(QColor(self.ov.color), max(2.0, H / 300))
                p.setPen(pen)
                for poly in self.ov.polygons:
                    p.drawPolygon(QPolygonF([QPointF(ox + x * s, oy + y * s) for x, y in poly]))
                if self.ov.big:
                    p.setFont(ui_font(int(H * 0.22), "semibold"))
                    p.setPen(QColor("#FFFFFF"))
                    p.drawText(QRectF(ox, oy, iw * s, ih * s), Qt.AlignmentFlag.AlignCenter, self.ov.big)
            p.setFont(ui_font(max(14, int(H * 0.03))))
            p.setPen(QColor(self.ov.text_color))
            p.drawText(QRectF(0.04 * W, H - band, 0.92 * W, band),
                       int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap), "\n".join(self.ov.lines))
            p.end()

    win = Window()
    ui = cfg.get("ui") or {}
    try:
        from wfglink.ui.booth_app import BUILTIN_SCREEN, choose_screen

        scr = choose_screen(app.screens(), app.primaryScreen(), screen or ui.get("screen", "auto"),
                            ui.get("builtin_screen") or BUILTIN_SCREEN)
    except Exception:             # the booth's screen rule is not essential here
        scr = app.primaryScreen()
    if scr is not None:
        win.setScreen(scr)
        win.setGeometry(scr.geometry())
    win.showFullScreen()
    timer = QTimer()
    timer.timeout.connect(win.tick)
    timer.start(15)
    app.exec()
    timer.stop()
    cap.stop()
    cap.join(timeout=3.0)
    try:
        src.close()
    except Exception:
        pass
    info["frames"] = cap.count
    return info
