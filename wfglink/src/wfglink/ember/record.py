"""`python -m wfglink record NAME [--seconds S]`: record the configured camera to data/raw/NAME.mp4.

The camera picture shows fullscreen (mirrored) with a countdown of ember.record.countdown_s
seconds, then a red REC tag with the time left; only the S seconds after the countdown are
written. H.264 (ember.record.crf), with each frame's own capture time as its timestamp, so
the timing of the motion is true. The file is the camera's own picture (not mirrored; the
pipeline mirrors it, as in the booth). An existing file is kept unless --force.

The recordings the validation expects (python -m wfglink validate --suite ember):
  ember_free   the phone, showing the ember page, moved freely at the standing spot
  ember_ruler  the phone resting at the 0 mark of a 1 m path marked at the standing spot,
               moved to the 100 cm mark in about 1 s, resting again
"""
from __future__ import annotations

import re
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np

from wfglink import PROJECT_ROOT
from wfglink.io.frames import Frame

HINTS = {
    "ember_free": ("서는 자리에서 폰 화면을 카메라 쪽으로 향하고 자유롭게 움직이세요",
                   "At the standing spot, screen toward the camera, move the phone freely"),
    "ember_ruler": ("0 표시에 멈춤, 약 1초 동안 100 cm 표시까지 이동, 다시 멈춤",
                    "Rest at the 0 mark, move to the 100 cm mark in about 1 s, rest again"),
}


def _rc(cfg: dict) -> dict[str, Any]:
    return ((cfg.get("ember") or {}).get("record") or {})


class Recorder:
    """Writes frames after the countdown, for `seconds`; thread-safe (called from the capture thread)."""

    def __init__(self, path: Path, seconds: float, countdown_s: float, fps: float, crf: int):
        self.path, self.seconds, self.countdown_s = path, float(seconds), float(countdown_s)
        self.fps, self.crf = float(fps), int(crf)
        self.t_first: float | None = None
        self.t_rec: float | None = None
        self.frames = 0
        self.writer = None
        self.done = threading.Event()
        self.times: list[float] = []
        self.size: tuple[int, int] | None = None
        self.error: str | None = None
        self._lock = threading.RLock()     # add() runs on the capture thread, finish() also on the main one

    def phase(self, t: float) -> tuple[str, float]:
        """("countdown", seconds left) or ("rec", seconds left) or ("done", 0)."""
        if self.t_first is None:
            return "countdown", self.countdown_s
        if self.done.is_set():
            return "done", 0.0
        el = t - self.t_first
        if el < self.countdown_s:
            return "countdown", self.countdown_s - el
        return "rec", max(0.0, self.countdown_s + self.seconds - el)

    def add(self, f: Frame) -> None:
        from wfglink.synth.degrade import VideoWriter

        with self._lock:
            if self.done.is_set():
                return
            if self.t_first is None:
                self.t_first = f.t
            if f.t - self.t_first < self.countdown_s:
                return
            if self.t_rec is None:
                self.t_rec = f.t
                h, w = f.image.shape[:2]
                self.size = (w, h)
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.writer = VideoWriter(self.path, (w, h), self.fps, crf=self.crf, preset="veryfast", encoder_threads=2)
            t = f.t - self.t_rec
            if t > self.seconds:
                self.finish()
                return
            if f.image.shape[1::-1] != self.size:
                return                       # the camera changed size mid-recording: skip such frames
            try:
                self.writer.write(f.image, t)
            except ValueError:               # a repeated timestamp
                return
            except RuntimeError as exc:
                self.error = str(exc)
                self.finish()
                return
            self.frames += 1
            self.times.append(t)

    def finish(self) -> None:
        with self._lock:
            if self.writer is not None and not self.done.is_set():
                try:
                    self.writer.close()
                except RuntimeError as exc:
                    self.error = str(exc)
            self.done.set()

    def summary(self) -> dict[str, Any]:
        dts = np.diff(self.times) if len(self.times) > 1 else np.array([])
        return {"file": str(self.path), "frames": self.frames, "seconds": round(self.times[-1], 3) if self.times else 0.0,
                "size": list(self.size) if self.size else None,
                "fps_mean": round(float(1 / dts.mean()), 2) if dts.size else None,
                "interval_max_ms": round(float(dts.max() * 1000), 1) if dts.size else None, "error": self.error}


def record(cfg: dict, name: str, seconds: float | None = None, *, out_dir: str | Path | None = None,
           fake: str | None = None, preview: bool = True, force: bool = False, screen: str | None = None) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9_\-]+", name or ""):
        raise ValueError(f"{name!r}: use letters, digits, _ and - only (for example ember_free)")
    rc = _rc(cfg)
    seconds = float(seconds or rc.get("seconds", 20))
    countdown = float(rc.get("countdown_s", 3))
    out = Path(out_dir) if out_dir else PROJECT_ROOT / "data" / "raw"
    path = out / f"{name}.mp4"
    if path.exists() and not force:
        raise FileExistsError(f"{path} exists: give another name, or --force to replace it")
    fps = float((cfg.get("camera") or {}).get("fps", 30))
    rec = Recorder(path, seconds, countdown, fps, int(rc.get("crf", 18)))
    if fake:
        from wfglink.io.camera import FakeCameraSource

        is_file = Path(fake).is_file()             # a video file, else the name of a generated scene
        src = FakeCameraSource(fake if is_file else None, scene=None if is_file else fake, realtime=True, cfg=cfg)
        src.open()
    else:
        from wfglink.ember.preview import open_camera

        src = open_camera(cfg)
    camera = getattr(src, "name", "")
    if preview:
        from wfglink.ember.preview import Overlay, run_preview

        hint = HINTS.get(name, ("", ""))

        def on_frame(f: Frame) -> Overlay:
            ph, left = rec.phase(f.t)
            if ph == "countdown":
                return Overlay(lines=[x for x in hint if x] + [f"{name}.mp4"], big=f"{max(1, int(np.ceil(left)))}",
                               color="#FFFFFF")
            if ph == "rec":
                return Overlay(lines=[x for x in hint if x] + [f"● REC  {left:4.1f} s  ·  {name}.mp4"],
                               text_color="#FF453A")
            return Overlay(lines=[f"저장했습니다 · Saved  {path}"], done=True, text_color="#30D158")

        info = run_preview(cfg, on_frame, screen=screen, source=src, done_hold_s=2.0, on_capture=rec.add,
                           timeout_s=countdown + seconds + 30)
        if info.get("cancelled") and not rec.done.is_set():
            rec.finish()
            res = rec.summary()
            res.update({"cancelled": True, "camera": camera})
            return res
    else:
        t_end = time.monotonic() + countdown + seconds + 30
        try:
            while not rec.done.is_set() and time.monotonic() < t_end:
                f = src.read()
                if f is None:
                    if not getattr(src, "is_live", False):
                        break
                    continue
                rec.add(f)
        finally:
            src.close()
    rec.finish()
    res = rec.summary()
    res["camera"] = camera
    return res
