"""EmberPipeline: camera frames in, the booth's LiveState out, for the "Become an ember" mode.

Per frame: mirror the picture (ember.mirror, so a visitor moving right moves right on
screen), scale it down to camera.width when wider, detect phone screens
(wfglink.ember.detect), track them (wfglink.ember.track), and fill a LiveState:

- image (the mirrored picture), detections (the embers seen in this frame), trails and
  trail_ages (each ember's last ember.track.trail_s), speed (median speed in m/s of the
  embers on screen), direction_deg (of their median velocity; image axes, 0 right, 90 down);
- field_uvn: wind arrows from all embers. ember.field_grid cells; each ember adds its
  velocity (m/s) to the cell it is in, one sample per ember and cell, kept for
  ember.field_window_s; a cell holds the median of its samples and their count, and shows
  with at least ember.field_min_tracks (field_min_n);
- sparkline: the most embers on screen in each of the last 60 s;
- mode "ember", embers [{id, track_id, speed_m_s, x, y, age_s}], ember_count, speed_unit
  "m/s", measured_at_m and distance_m (ember.distance_m), calibrated, camera_state "ok",
  warm (0 to 1 once the background model has warmed up).

Scale. Speeds are image speeds turned into metres per second at the standing distance Z
(ember.distance_m): m/px = Z / f. f is camera.focal_px when an A4 calibration exists
(ember.calibration, made at its size; scaled when the picture's width differs with the same
aspect), else (W / 2) / tan(camera.hfov_deg / 2), the nominal field of view (calibrated is
then false). A calibration made with another camera than the one delivering the frames
(frame.meta["camera"]) is not used. A phone nearer or farther than Z moves faster or slower
on screen than the same motion at Z, so the label says "measured at" Z.
"""
from __future__ import annotations

import math
import time
from collections import deque
from typing import Any

import cv2
import numpy as np

from wfglink.ember.detect import EmberDetector
from wfglink.ember.track import EmberTrack, EmberTracker
from wfglink.io.frames import Frame
from wfglink.pipeline import PipelineStats
from wfglink.render.scene import LiveState


def nominal_focal_px(width: int, hfov_deg: float) -> float:
    return (width / 2.0) / math.tan(math.radians(float(hfov_deg)) / 2.0)


def focal_for(cfg: dict, width: int, height: int, camera: str | None = None) -> tuple[float, bool, str]:
    """(focal length in px for a picture of this size, calibrated, where it came from)."""
    cam = cfg.get("camera") or {}
    cal = (cfg.get("ember") or {}).get("calibration") or None
    f_cal = cam.get("focal_px")
    if cal and f_cal:
        size = cal.get("size") or [cam.get("width", 1280), cam.get("height", 720)]
        cw, ch = float(size[0]), float(size[1])
        same_aspect = abs(width / height - cw / ch) < 0.01
        same_camera = not camera or not cal.get("camera") or str(cal.get("camera")) == str(camera)
        if same_aspect and same_camera:
            return float(f_cal) * width / cw, True, "calibration"
        why = "another camera" if not same_camera else "another aspect"
        return nominal_focal_px(width, cam.get("hfov_deg", 70.0)), False, f"nominal (calibration is for {why})"
    return nominal_focal_px(width, cam.get("hfov_deg", 70.0)), False, "nominal"


class EmberPipeline:
    def __init__(self, cfg: dict, focal_px: float | None = None):
        self.cfg = cfg
        e = cfg.get("ember") or {}
        self.mirror = bool(e.get("mirror", True))
        self.distance_m = float(e.get("distance_m", 2.0))
        self.max_width = int((cfg.get("camera") or {}).get("width", 1280))
        self.field_grid = tuple(int(v) for v in e.get("field_grid", [16, 9]))
        self.field_window_s = float(e.get("field_window_s", 3.0))
        self.field_min_tracks = int(e.get("field_min_tracks", 1))
        tc = e.get("track") or {}
        self.count_hold_s = float(tc.get("count_hold_s", 0.4))
        self.trail_s = float(tc.get("trail_s", 0.8))
        self.focal_override = focal_px
        self.reset()

    def reset(self) -> None:
        self.detector: EmberDetector | None = None
        self.tracker: EmberTracker | None = None
        self.size: tuple[int, int] | None = None
        self.f_px = 0.0
        self.calibrated = False
        self.scale_source = ""
        self.m_per_px = 0.0
        self._last_t: float | None = None
        self._t_ready: float | None = None
        self._field: dict[tuple[int, int], dict[int, tuple[float, float, float]]] = {}
        self._spark: deque = deque()
        self.last_state = LiveState()
        self.stats = PipelineStats()
        self.history: list[dict[str, Any]] | None = None    # per-frame records when record() was called
        self.finished: list[EmberTrack] = []                 # ended tracks, kept only while recording

    def record(self) -> None:
        """Keep a record of every analysed frame (validation): time and each shown ember."""
        self.history = []
        self.finished = []

    def all_tracks(self) -> list[EmberTrack]:
        """Every confirmed track so far, ended ones included (while recording)."""
        live = [tr for tr in (self.tracker.tracks if self.tracker else []) if tr.confirmed]
        return self.finished + live

    def _setup(self, w: int, h: int, camera: str | None) -> None:
        if self.focal_override:
            self.f_px, self.calibrated, self.scale_source = float(self.focal_override), True, "given"
        else:
            self.f_px, self.calibrated, self.scale_source = focal_for(self.cfg, w, h, camera)
        self.m_per_px = self.distance_m / self.f_px
        self.detector = EmberDetector(self.cfg, self.f_px)
        self.tracker = EmberTracker(self.cfg, self.f_px / self.distance_m)
        self.size = (w, h)

    def process(self, frame: Frame) -> LiveState:
        t0 = time.perf_counter()
        self.stats.frames_in += 1
        img = frame.image
        if img.shape[1] > self.max_width:
            s = self.max_width / img.shape[1]
            img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        if self.mirror:
            img = cv2.flip(img, 1)
        h, w = img.shape[:2]
        if self.size != (w, h):
            self._setup(w, h, frame.meta.get("camera"))
        t = float(frame.t)
        if self._last_t is not None and t <= self._last_t:
            self.stats.frames_duplicate += 1
            st = self.last_state
            st.image = img
            return st
        self._last_t = t
        blobs = self.detector.detect(img)
        self.tracker.update(blobs, t)
        ended = self.tracker.pop_finished()
        if self.history is not None:
            self.finished.extend(ended)
        self.detector.protect([tr.box for tr in self.tracker.shown() if tr.seen and tr.box is not None])
        if self.detector.ready and self._t_ready is None:
            self._t_ready = t
        state = self._state(img, t, frame)
        self.stats.frames_analysed += 1
        self.stats.proc_ms.append((time.perf_counter() - t0) * 1000)
        self.last_state = state
        return state

    # state --------------------------------------------------------------------------------------
    def _ember_speed(self, tr: EmberTrack) -> float | None:
        return None if tr.speed is None else tr.speed * self.m_per_px

    def _state(self, img: np.ndarray, t: float, frame: Frame) -> LiveState:
        live = [tr for tr in self.tracker.shown() if t - tr.last_t <= self.count_hold_s]
        embers = [{"id": int(tr.slot), "track_id": int(tr.tid), "speed_m_s": self._ember_speed(tr),
                   "x": float(tr.x), "y": float(tr.y), "age_s": float(t - (tr.shown_t or t))}
                  for tr in sorted(live, key=lambda tr: tr.slot or 0)]
        seen = [tr for tr in live if tr.seen]
        det = np.array([(tr.x, tr.y) for tr in seen]) if seen else np.zeros((0, 2))
        trails, ages = [], []
        for tr in self.tracker.shown():
            age = t - tr.last_t
            if age > 1.0:
                continue
            pts = [(x, y) for tt, x, y in tr.pts[-64:] if tt >= tr.last_t - self.trail_s]
            if len(pts) >= 2:
                trails.append(np.array(pts))
                ages.append(age)
        # Wind arrows from every ember on screen.
        cols, rows = self.field_grid
        w, h = self.size
        for tr in seen:
            if tr.speed is None:
                continue
            c = int(np.clip(tr.x / w * cols, 0, cols - 1))
            r = int(np.clip(tr.y / h * rows, 0, rows - 1))
            self._field.setdefault((r, c), {})[tr.tid] = (t, tr.vx * self.m_per_px, tr.vy * self.m_per_px)
        fld = np.zeros((rows, cols, 3))
        for key in list(self._field):
            cell = {k: v for k, v in self._field[key].items() if v[0] >= t - self.field_window_s}
            if not cell:
                del self._field[key]
                continue
            self._field[key] = cell
            uv = np.array([(u, v) for _, u, v in cell.values()])
            fld[key[0], key[1]] = (np.median(uv[:, 0]), np.median(uv[:, 1]), len(cell))
        speeds = [e["speed_m_s"] for e in embers if e["speed_m_s"] is not None]
        vel = [(tr.vx, tr.vy) for tr in live if tr.speed is not None]
        speed = float(np.median(speeds)) if speeds else None
        direction = None
        if vel:
            mv = np.median(np.array(vel), axis=0)
            if math.hypot(*mv) > 1e-6:
                direction = math.degrees(math.atan2(mv[1], mv[0]))
        # Sparkline: the most embers on screen in each second of the last minute.
        sec = math.floor(t)
        if self._spark and self._spark[-1][0] == sec:
            self._spark[-1] = (sec, max(self._spark[-1][1], len(embers)))
        else:
            self._spark.append((sec, len(embers)))
        while self._spark and self._spark[0][0] < sec - 60:
            self._spark.popleft()
        spark = np.full(60, np.nan)
        first = self._spark[0][0]
        for k in range(60):
            if sec - 59 + k >= first:
                spark[k] = 0.0
        for s_, n in self._spark:
            if 0 <= s_ - (sec - 59) < 60:
                spark[s_ - (sec - 59)] = n
        warm = 0.0 if self._t_ready is None else float(np.clip((t - self._t_ready) / 1.0, 0, 1))
        meta = frame.meta or {}
        st = LiveState(image=img, t=t, detections=det, trails=trails, trail_ages=ages, speed=speed,
                       direction_deg=direction, field_uvn=fld, field_min_n=self.field_min_tracks, sparkline=spark,
                       calibrated=self.calibrated, distance_m=self.distance_m, warm=warm,
                       source_label=str(meta.get("camera") or ""),
                       source_state="synthetic" if meta.get("synthetic") else "camera")
        for k, v in (("mode", "ember"), ("embers", embers), ("ember_count", len(embers)), ("speed_unit", "m/s"),
                     ("measured_at_m", self.distance_m), ("camera_state", "ok")):
            setattr(st, k, v)
        if self.history is not None:
            self.history.append({"t": t, "embers": [dict(e, seen=any(tr.tid == e["track_id"] for tr in seen))
                                                    for e in embers]})
        return st
