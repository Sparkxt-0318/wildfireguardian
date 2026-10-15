"""The one processing pipeline shared by file mode and the live booth screen.

Per frame: detect candidates; track them; feed confirmed, non-static tracks to the gate
counter; update the running speed, direction, ember velocity field, glowing trails and the
60 s sparkline; and return a LiveState for the renderer.

Timing: every frame carries its true presentation time (file mode), or its playback time
(the booth plays approved clips in real time and may skip frames it cannot analyse in
time; the times stay true). Repeated frames (difference below the noise level) are skipped
so they never create zero displacements. At a cut in the booth playlist (next segment, or
the same clip again) cut() restarts the background model and the tracks and keeps the counts.
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
class PipelineStats:
    frames_in: int = 0
    frames_analysed: int = 0
    frames_duplicate: int = 0
    tracks_finished: int = 0             # confirmed tracks that ended, static ones included
    tracks_static: int = 0
    proc_ms: deque = field(default_factory=lambda: deque(maxlen=300))

    def as_dict(self) -> dict[str, Any]:
        d = {k: v for k, v in self.__dict__.items() if k != "proc_ms"}
        ms = np.array(self.proc_ms) if self.proc_ms else np.array([np.nan])
        d["proc_ms_median"] = float(np.nanmedian(ms))
        d["proc_ms_p95"] = float(np.nanpercentile(ms, 95))
        return d


HEARTBEAT_COUNTERS = ("frames_in", "frames_analysed", "frames_duplicate")


def heartbeat_counters(key: str | None, stats: "PipelineStats | dict | None") -> dict[str, Any] | None:
    """The active pipeline's frame counters for the booth heartbeat: plain integers, so they
    can be read from another thread (or from the process worker's last stats report)."""
    if stats is None:
        return None
    get = stats.get if isinstance(stats, dict) else (lambda k, d=0: getattr(stats, k, d))
    return {"key": key, **{k: int(get(k, 0) or 0) for k in HEARTBEAT_COUNTERS}}


def _smooth_tail(pts: np.ndarray, max_turn_deg: float = 100.0) -> np.ndarray:
    """The part of a trail after its last sharp reversal (display only).

    A wrong association in a dense shower makes the filtered path zig-zag; drawing only the
    recent smooth part keeps the screen honest about the motion without changing any count.
    """
    if len(pts) < 3:
        return pts
    d = np.diff(pts, axis=0)
    n = np.hypot(d[:, 0], d[:, 1])
    ok = n > 1e-6
    cosang = np.einsum("ij,ij->i", d[:-1], d[1:]) / np.maximum(n[:-1] * n[1:], 1e-12)
    sharp = np.flatnonzero((cosang < math.cos(math.radians(max_turn_deg))) & ok[:-1] & ok[1:])
    return pts[sharp[-1] + 1:] if sharp.size else pts


class Pipeline:
    def __init__(self, cfg: dict, gate: dict | None = None,
                 fps: float | None = None, m_per_px: float | None = None, distance_m: float | None = None,
                 dedupe: bool = True, analysis_max_width: int | None = None, downscale: bool = False,
                 record: bool = False, t_exp_hint: float | None = None):
        self.cfg = cfg
        self.record = record          # keep detections, frames and full tracks for tables()
        # The streak length method (detect.streaks.method; erf, or moments with refine) costs a
        # few ms per frame: file mode (record) only.
        streaks = cfg.get("detect", {}).get("streaks", {})
        self.refine = record and (streaks.get("method", "moments") != "moments" or bool(streaks.get("refine", False)))
        self.t_exp_hint = t_exp_hint  # exposure time (s) for the tracker's search reach
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
        self._rep_px = float(fr.get("repeat_match_px", 0.5))
        self._rep_frac = float(fr.get("repeat_fraction", 0.8))
        self._rep_min = int(fr.get("repeat_min_moving", 2))
        self._rep_move = float(fr.get("repeat_move_px", 1.5))
        self._mask: np.ndarray | None = None
        self.reset()

    # State ----------------------------------------------------------------------------------
    def reset(self) -> None:
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
        self._prev_small: np.ndarray | None = None
        self._moving_last: np.ndarray | None = None
        self._spark: deque = deque()             # (t, crossings in that second)
        self._field: dict[tuple[int, int], dict[int, tuple[float, float, float]]] = {}
        self._speeds: deque = deque()            # (t, speed, vx, vy)
        self._t_ready: float | None = None
        self._finished_count = 0
        self._last_prune = -np.inf
        self.last_state = LiveState()
        self.stats = PipelineStats()

    def cut(self) -> None:
        """A cut in the picture (booth playlist: the next segment, or the same clip again) with
        the counts kept: the background model and the tracks restart, while the gate counts,
        the sparkline and the field run on."""
        if self.counter is not None:
            self._retire(self.tracker.finish_all())
        self.detector = Detector(self.cfg)
        self.tracker = Tracker(self.cfg, fps=self.fps, keep_history=self.record)
        if self.t_exp_hint:
            self.tracker.set_exposure_hint(self.t_exp_hint)
        self._prev_small = None
        self._moving_last = None

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
        analyse = True
        if self.dedupe:
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
        h, w = image.shape[:2]
        self._ensure_gate(w, h)
        det = self.detector.detect(image, mask)
        if self.dedupe and self._content_repeat(det):
            # A lossy re-encode stores a repeated frame with small differences, so the pixel
            # test above misses it; the embers themselves have not moved.
            self.stats.frames_duplicate += 1
            st = self.last_state
            st.image = image
            return st
        self._last_t = t
        if self.refine and len(det):
            from wfglink.detect.streaks import measure_streaks

            det = measure_streaks(det, self.detector.state, self.cfg)
        snaps = self.tracker.update(det, t, frame.index)
        self._remember_moving(frame.index)
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
        if not self.record and t - self._last_prune > 10.0:   # file mode keeps every event
            self.counter.prune_events(t - 120.0)
            self._last_prune = t
        self._update_running(t, snaps, new_events, w, h)
        self.stats.frames_analysed += 1
        self.stats.proc_ms.append((time.perf_counter() - t0) * 1000)
        state = self._build_state(image, t, det, snaps, meta)
        self.last_state = state
        return state

    def _content_repeat(self, det: Detections) -> bool:
        """True when the embers that were moving in the previous analysed frame have not moved:
        at least frames.repeat_fraction of them (and at least frames.repeat_min_moving) have a
        detection within frames.repeat_match_px of where they were measured last frame."""
        pts = self._moving_last
        if pts is None or len(pts) < self._rep_min or len(det) == 0:
            return False
        from scipy.spatial import cKDTree

        d, _ = cKDTree(np.column_stack([det.x, det.y])).query(pts)
        return bool(np.mean(d <= self._rep_px) >= self._rep_frac)

    def _remember_moving(self, frame_index: int) -> None:
        """Last measured positions of the tracks that moved more than frames.repeat_move_px in
        this frame (confirmed, not static, measured now)."""
        dt = self.tracker.nominal_dt or (1.0 / self.fps if self.fps else 1.0 / 30.0)
        pts = []
        for tr in self.tracker.active_tracks():
            if tr.static or not tr.records:
                continue
            r = tr.records[-1]
            if r[0] != frame_index or r[14] or not np.isfinite(r[2]):
                continue
            if math.hypot(r[6], r[7]) * dt > self._rep_move:
                pts.append((r[2], r[3]))
        self._moving_last = np.array(pts) if pts else None

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

    def _prepare(self, frame: Frame) -> tuple[np.ndarray, float, np.ndarray | None, dict]:
        img = frame.image
        if self.downscale and img.shape[1] > self.analysis_max_width:
            s = self.analysis_max_width / img.shape[1]
            img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        return img, frame.t, None, {}

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
            pts = _smooth_tail(np.array([(rr[4], rr[5]) for rr in recs if t - rr[1] <= 0.6]))
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
