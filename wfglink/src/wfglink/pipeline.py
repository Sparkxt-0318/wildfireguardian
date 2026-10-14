"""The one processing pipeline shared by file mode, live mode and the booth.

Per frame: (booth only) rectify the filmed screen and decode its frame code; detect
candidates; track them; feed confirmed, non-static tracks to the gate counter; update the
running speed, direction, ember velocity field, glowing trails and the 60 s sparkline; and
return a LiveState for the renderer.

Timing rules:
- File mode uses each frame's true presentation time. Repeated frames (difference below
  the noise level) are skipped so they never create zero displacements.
- Booth mode uses the decoded source frame index and the booth-prep sidecar, so velocities
  are in source time whatever the playback speed. Only clean frames (all four codes agree,
  no gray cell) are analysed; a repeated index is skipped; a backward jump means the clip
  looped, so tracker and counts restart and the loop number increases.
- Live mode without codes uses the camera clock.
"""
from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from wfglink.detect.candidates import Detections, Detector
from wfglink.io.frames import Frame
from wfglink.measure.gate import Gate, GateCounter
from wfglink.render.scene import LiveState
from wfglink.track.tracker import Tracker


@dataclass
class BoothContext:
    """What booth mode needs: the rectifier and the sidecar of source timestamps."""

    rectifier: Any                      # wfglink.screen.rectify.ScreenRectifier
    source_times: np.ndarray            # seconds, indexed by source frame index


@dataclass
class PipelineStats:
    frames_in: int = 0
    frames_analysed: int = 0
    frames_duplicate: int = 0
    frames_unclean: int = 0
    frames_blended: int = 0
    frames_torn: int = 0
    frames_no_code: int = 0
    loops: int = 0
    tracks_finished: int = 0             # confirmed tracks that ended, static ones included
    tracks_static: int = 0
    proc_ms: deque = field(default_factory=lambda: deque(maxlen=300))

    def as_dict(self) -> dict[str, Any]:
        d = {k: v for k, v in self.__dict__.items() if k != "proc_ms"}
        ms = np.array(self.proc_ms) if self.proc_ms else np.array([np.nan])
        d["proc_ms_median"] = float(np.nanmedian(ms))
        d["proc_ms_p95"] = float(np.nanpercentile(ms, 95))
        seen = self.frames_analysed + self.frames_unclean
        d["clean_frame_yield"] = (self.frames_analysed + self.frames_duplicate) / max(self.frames_in, 1) if seen else None
        return d


class Pipeline:
    def __init__(self, cfg: dict, gate: dict | None = None, booth: BoothContext | None = None,
                 fps: float | None = None, m_per_px: float | None = None, distance_m: float | None = None,
                 dedupe: bool = True, analysis_max_width: int | None = None, downscale: bool = False,
                 record: bool = False, t_exp_hint: float | None = None):
        self.cfg = cfg
        self.record = record          # keep detections, frames and full tracks for tables()
        self.t_exp_hint = t_exp_hint  # exposure time (s) for the tracker's search reach
        self.booth = booth
        self.fps = fps
        self.m_per_px = m_per_px
        self.distance_m = distance_m
        self.dedupe = dedupe
        self.analysis_max_width = analysis_max_width or int(cfg.get("live", {}).get("analysis_max_width", 1280))
        self.gate_spec = gate
        self.downscale = downscale   # live display: analyse at most analysis_max_width wide
        self.stats = PipelineStats()
        f = cfg.get("field", {})
        self.field_grid = tuple(int(v) for v in f.get("grid", [16, 9]))
        self.field_window = float(f.get("live_window_s", 3.0))
        self.field_min_n = int(f.get("min_tracks_show", 5))
        fr = cfg.get("frames", {})
        self._dup_dn = int(fr.get("duplicate_dn", 6))          # a pixel changed by this much is a change
        self._dup_max_px = int(fr.get("duplicate_max_px", 2))  # at most this many changed pixels: repeat
        self._mask: np.ndarray | None = None
        self.reset()

    # State ----------------------------------------------------------------------------------
    def reset(self, keep_loops: bool = False) -> None:
        self.detector = Detector(self.cfg)
        self.tracker = Tracker(self.cfg, fps=self.fps, keep_history=self.record)
        if self.t_exp_hint:
            self.tracker.set_exposure_hint(self.t_exp_hint)
        self._rec_det: list[dict[str, np.ndarray]] = []
        self._rec_frames: list[tuple[int, float, bool, bool]] = []
        self.counter: GateCounter | None = None
        self._gate_obj: Gate | None = None
        self._size: tuple[int, int] | None = None
        self._last_t: float | None = None
        self._last_index: int | None = None
        self._prev_small: np.ndarray | None = None
        self._spark: deque = deque()             # (t, crossings in that second)
        self._field: dict[tuple[int, int], dict[int, tuple[float, float, float]]] = {}
        self._speeds: deque = deque()            # (t, speed, vx, vy)
        self._t_ready: float | None = None
        self._finished_count = 0
        self._last_prune = -np.inf
        self.last_state = LiveState()
        if not keep_loops:
            self.stats = PipelineStats()

    def _ensure_gate(self, w: int, h: int) -> None:
        if self._gate_obj is not None and self._size == (w, h):
            return
        self._size = (w, h)
        spec = self.gate_spec or {"p1": [0.62 * w, 0.08 * h], "p2": [0.62 * w, 0.92 * h], "name": "gate"}
        p1, p2 = spec["p1"], spec["p2"]
        if max(abs(v) for v in (*p1, *p2)) <= 1.0:  # fractions of the frame
            p1, p2 = [p1[0] * w, p1[1] * h], [p2[0] * w, p2[1] * h]
        self._gate_obj = Gate(tuple(p1), tuple(p2), float(self.cfg["gate"]["hysteresis_px"]), spec.get("name", "gate"))
        self.counter = GateCounter(self._gate_obj, self.cfg)

    # Main entry ---------------------------------------------------------------------------
    def process(self, frame: Frame) -> LiveState:
        t0 = time.perf_counter()
        self.stats.frames_in += 1
        image, t, mask, meta = self._prepare(frame)
        if image is None:
            return self._state_without_analysis(frame, meta)
        analyse = True
        if self.dedupe and self.booth is None:
            # A repeated frame (constant-frame-rate re-encode) changes almost no pixel; a real
            # new frame changes many, through sensor noise or anything that moved. A thumbnail
            # difference is not enough: a few small embers on a static night scene barely
            # change a thumbnail, and real frames were dropped that way.
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
            if self._prev_small is not None and self._prev_small.shape == gray.shape:
                changed = cv2.countNonZero(cv2.compare(cv2.absdiff(gray, self._prev_small), self._dup_dn, cv2.CMP_GE))
                if changed <= self._dup_max_px:
                    self.stats.frames_duplicate += 1
                    analyse = False
            self._prev_small = gray
        if t is not None and self._last_t is not None and t <= self._last_t:
            self.stats.frames_duplicate += 1
            analyse = False
        if not analyse:
            st = self.last_state
            st.image = image
            return st
        self._last_t = t
        h, w = image.shape[:2]
        self._ensure_gate(w, h)
        det = self.detector.detect(image, mask)
        snaps = self.tracker.update(det, t, frame.index)
        if self.record:
            self._record(frame.index, t, det)
        self.counter.observe(t)
        new_events = 0
        for s in snaps:
            if s.static or s.coasted:
                continue
            ev = self.counter.update_point(s.track_id, s.t, s.x, s.y)
            if ev is not None:
                new_events += 1
        self._retire(self.tracker.pop_finished())
        if t - self._last_prune > 10.0:
            self.counter.prune_events(t - 120.0)
            self._last_prune = t
        self._update_running(t, snaps, new_events, w, h)
        self.stats.frames_analysed += 1
        self.stats.proc_ms.append((time.perf_counter() - t0) * 1000)
        state = self._build_state(image, t, det, snaps, meta)
        self.last_state = state
        return state

    def _retire(self, tracks) -> None:
        for tr in tracks:
            if tr.static:
                self.counter.exclude(tr.track_id, since=getattr(tr, "static_since", None))
                self.stats.tracks_static += 1
            self.counter.forget(tr.track_id)          # bounded memory over a booth day
            self._finished_count += 1
            self.stats.tracks_finished += 1

    def _record(self, index: int, t: float, det: Detections) -> None:
        self._rec_frames.append((int(index), float(t), bool(self.detector.ready), len(det) > 0))
        if len(det):
            cols = {k: getattr(det, k) for k in ("x", "y", "area", "peak", "flux", "length", "width", "theta",
                                                "sat_frac", "color", "flags")}
            cols["frame"] = np.full(len(det), int(index), np.int64)
            cols["t"] = np.full(len(det), float(t))
            self._rec_det.append(cols)

    def tables(self) -> dict[str, Any]:
        """Recorded tables (record=True): detections, analysed frames and track points."""
        import pandas as pd

        from wfglink.track.tracker import tracks_to_frame

        det_cols = ("frame", "t", "x", "y", "area", "peak", "flux", "length", "width", "theta", "sat_frac", "color", "flags")
        if self._rec_det:
            det = pd.DataFrame({k: np.concatenate([d[k] for d in self._rec_det]) for k in det_cols})
        else:
            det = pd.DataFrame({k: np.zeros(0) for k in det_cols})
        frames = pd.DataFrame(self._rec_frames, columns=["frame", "t", "ready", "has_detections"])
        tracks = tracks_to_frame(self.tracker.all_tracks(include_active=True))
        return {"detections": det, "frames": frames, "tracks": tracks}

    def finish(self) -> None:
        """End of a file: finish the confirmed tracks still open so the stats include them."""
        if self.counter is not None:
            self._retire(self.tracker.finish_all())

    def _prepare(self, frame: Frame) -> tuple[np.ndarray | None, float | None, np.ndarray | None, dict]:
        meta: dict[str, Any] = {}
        if self.booth is None:
            img = frame.image
            if self.downscale and img.shape[1] > self.analysis_max_width:
                s = self.analysis_max_width / img.shape[1]
                img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
            return img, frame.t, None, meta
        r = self.booth.rectifier.process(frame.image)
        meta["markers"] = r.markers_found
        if r.image is None or r.code is None:
            self.stats.frames_no_code += 1
            return None, None, None, meta
        code = r.code
        if code.blended:
            self.stats.frames_blended += 1
        if code.torn:
            self.stats.frames_torn += 1
        if not code.clean or code.index is None:
            self.stats.frames_unclean += 1
            meta["rect_image"] = r.image
            return None, None, None, meta
        idx = int(code.index)
        if self._last_index is not None and idx < self._last_index:
            loops = self.stats.loops + 1
            self.reset(keep_loops=True)
            self.stats.loops = loops
        if self._last_index is not None and idx == self._last_index:
            self.stats.frames_duplicate += 1
            self.last_state.image = r.image
            return None, None, None, {**meta, "duplicate": True, "rect_image": r.image}
        self._last_index = idx
        times = self.booth.source_times
        t = float(times[idx]) if 0 <= idx < len(times) and np.isfinite(times[idx]) else idx / 30.0
        return r.image, t, r.mask, {**meta, "source_index": idx}

    def _state_without_analysis(self, frame: Frame, meta: dict) -> LiveState:
        st = self.last_state
        if meta.get("rect_image") is not None:
            st.image = meta["rect_image"]
        elif st.image is None:
            st.image = frame.image
        return st

    # Running statistics ---------------------------------------------------------------------
    def _update_running(self, t: float, snaps, new_events: int, w: int, h: int) -> None:
        if self.detector.ready and self._t_ready is None:
            self._t_ready = t
        sec = math.floor(t)
        if self._spark and self._spark[-1][0] == sec:
            self._spark[-1] = (sec, self._spark[-1][1] + new_events)
        else:
            self._spark.append((sec, new_events))
        while self._spark and self._spark[0][0] < sec - 60:
            self._spark.popleft()
        cols, rows = self.field_grid
        for s in snaps:
            if s.static or s.coasted or s.n_points < 3:
                continue
            sp = math.hypot(s.vx, s.vy)
            self._speeds.append((t, sp, s.vx, s.vy))
            c, r = int(np.clip(s.x / w * cols, 0, cols - 1)), int(np.clip(s.y / h * rows, 0, rows - 1))
            self._field.setdefault((r, c), {})[s.track_id] = (t, s.vx, s.vy)
        while self._speeds and self._speeds[0][0] < t - 2.0:
            self._speeds.popleft()
        for key in list(self._field):
            cell = self._field[key]
            for tid in [k for k, v in cell.items() if v[0] < t - self.field_window]:
                del cell[tid]
            if not cell:
                del self._field[key]

    def _build_state(self, image: np.ndarray, t: float, det: Detections, snaps, meta: dict) -> LiveState:
        cols, rows = self.field_grid
        fld = np.zeros((rows, cols, 3))
        for (r, c), cell in self._field.items():
            v = np.array([[u, vv] for _, u, vv in cell.values()])
            fld[r, c] = (np.median(v[:, 0]), np.median(v[:, 1]), len(cell))
        speed = direction = None
        if len(self._speeds) >= 3:
            arr = np.array(self._speeds)
            speed = float(np.median(arr[:, 1]))
            mvx, mvy = float(np.median(arr[:, 2])), float(np.median(arr[:, 3]))
            if math.hypot(mvx, mvy) > 1e-6:
                direction = math.degrees(math.atan2(mvy, mvx))
        trails, ages = [], []
        for tr in self.tracker.active_tracks():
            if tr.static or tr.n_points < 2:
                continue
            recs = tr.records[-12:]
            pts = np.array([(rr[4], rr[5]) for rr in recs if t - rr[1] <= 0.6])
            if len(pts) >= 2:
                trails.append(pts)
                ages.append(max(0.0, t - recs[-1][1]))
        # Fixed 60 s window, one bin per second; seconds before the start stay empty (NaN).
        spark = np.full(60, np.nan)
        if self._spark:
            now = math.floor(t)
            first = self._spark[0][0]
            for k in range(60):
                sec = now - 59 + k
                if sec >= first:
                    spark[k] = 0.0
            for sec, n in self._spark:
                k = sec - (now - 59)
                if 0 <= k < 60:
                    spark[k] = n
        warm = 0.0
        if self._t_ready is not None:
            warm = float(np.clip((t - self._t_ready) / 1.0, 0, 1))
        calibrated = self.m_per_px is not None
        rate = self.counter.rate(t) if self.counter else None
        cpc = self.counter.counts()["gross"] if self.counter else None
        dur = self.counter.duration() if self.counter else 0.0
        pnf = None
        if self.counter and dur > 0:
            pnf = self.counter.particle_number_flux(m_per_px=self.m_per_px, z_m=self.distance_m).value
        sp_out = speed * self.m_per_px if (speed is not None and calibrated) else speed
        g = self._gate_obj
        return LiveState(
            image=image, t=t, detections=np.column_stack([det.x, det.y]) if len(det) else np.zeros((0, 2)),
            trails=trails, trail_ages=ages, count_rate=rate if rate is not None and np.isfinite(rate) else None,
            cpc_gross=cpc, cpc_net=self.counter.counts()["net"] if self.counter else None, pnf=pnf,
            speed=sp_out, direction_deg=direction, field_uvn=fld, field_min_n=self.field_min_n,
            gate=(tuple(g.p1), tuple(g.p2)) if g is not None else None, sparkline=spark,
            calibrated=calibrated, distance_m=self.distance_m, warm=warm,
        )
