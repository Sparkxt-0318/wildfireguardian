"""Tracking of up to ember.max_tracks phones, with IDs, trails and speeds.

A small dedicated tracker (phones are few, large and bright; the fire tracker is built for
many faint embers):

- Prediction: the last position plus the last velocity, held for ember.track.coast_hold_s
  while a track is unseen and then slowing with time constant ember.track.coast_tau_s (a hand
  keeps moving for a moment when the phone turns away).
- Association: Hungarian assignment within a reach of ember.track.gate_m (at the standing
  distance), plus ember.track.gate_speed_frac of the predicted motion and
  ember.track.gate_grow_m_s per second unseen, at most ember.track.gate_max_m. The cost is the
  distance to the prediction plus the reach gained while unseen, so of two candidates the one
  seen more recently wins. In turn: the confirmed tracks seen in the previous frame, then the
  unseen ones (embers first), then the new ones; so a track that lost its phone for a moment
  never takes it back from the track that found it, and a phone that comes back after a turn
  goes to its old ember before any new track starts.
- Life: a track is confirmed after ember.track.confirm_hits detections within
  ember.track.confirm_window_s. It is shown (an ember on screen, with a display ID from 1 to
  ember.max_tracks) once it has moved ember.track.min_travel_m from where it was first seen,
  has been at least ember.track.min_show_speed_m_s fast, its blob is not on the background
  model's bright static pixels, and fewer than ember.max_tracks embers are shown. A confirmed
  track that has not shown after ember.track.static_s is a static light (the static-time
  rule): it is kept, so its light never starts a new track, but it shows only if it later
  moves as above. An ember that rests (moves less than ember.track.min_travel_m) for
  ember.track.static_s on the background model's bright static pixels has caught a lamp as
  its phone went by: it stops showing and becomes a static light. An ember unseen for
  ember.track.max_coast_s ends (a phone turned away or hidden for less keeps its ID); a track
  not yet shown ends after ember.track.lost_s unseen, a static light after
  ember.track.static_forget_s.
- Speed: the least-squares line through the positions of the last ember.track.speed_window_s
  (at least ember.track.speed_min_points of them), in px/s; the pipeline converts it to m/s.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import linear_sum_assignment

from wfglink.ember.detect import Blobs

BIG = 1e9
MAX_POINTS = 3600          # points kept per track (two minutes at 30 fps)


@dataclass
class EmberTrack:
    tid: int
    t0: float
    x: float
    y: float
    last_t: float
    anchor: tuple[float, float]
    pts: list[tuple[float, float, float]] = field(default_factory=list)   # (t, x, y) of every detection
    vx: float = 0.0
    vy: float = 0.0
    speed: float | None = None          # px/s from the trailing least-squares line
    hits: int = 1
    confirmed: bool = False
    shown: bool = False
    shown_t: float | None = None
    slot: int | None = None
    static: bool = False
    travel: float = 0.0
    peak_speed: float = 0.0
    on_bg: bool = False
    rest_at: tuple[float, float] | None = None     # where the track last started resting, and when
    rest_t: float = 0.0
    box: tuple[int, int, int, int] | None = None
    diam: float = 0.0
    seen: bool = True                   # detected in the latest frame


class EmberTracker:
    def __init__(self, cfg: dict, px_per_m: float):
        e = cfg.get("ember") or {}
        c = e.get("track") or {}
        self.max_tracks = int(e.get("max_tracks", 6))
        self.px_per_m = float(px_per_m)                 # image px per metre at the standing distance
        self.confirm_hits = int(c.get("confirm_hits", 3))
        self.confirm_window_s = float(c.get("confirm_window_s", 0.25))
        self.gate_px = float(c.get("gate_m", 0.15)) * self.px_per_m
        self.gate_speed_frac = float(c.get("gate_speed_frac", 0.5))
        self.gate_grow = float(c.get("gate_grow_m_s", 1.0)) * self.px_per_m
        self.gate_max = float(c.get("gate_max_m", 1.0)) * self.px_per_m
        self.coast_tau = float(c.get("coast_tau_s", 0.3))
        self.coast_hold = float(c.get("coast_hold_s", 0.15))
        self.max_coast_s = float(c.get("max_coast_s", 3.0))
        self.lost_s = float(c.get("lost_s", 0.4))
        self.static_forget_s = float(c.get("static_forget_s", 3.0))
        self.min_travel = float(c.get("min_travel_m", 0.08)) * self.px_per_m
        self.min_show_speed = float(c.get("min_show_speed_m_s", 0.15)) * self.px_per_m
        self.static_s = float(c.get("static_s", 2.0))
        self.speed_window_s = float(c.get("speed_window_s", 0.2))
        self.speed_min_points = int(c.get("speed_min_points", 3))
        self.tracks: list[EmberTrack] = []
        self.finished: list[EmberTrack] = []           # ended tracks since the last pop_finished()
        self._next_id = 1
        self.t: float | None = None
        self.t_prev: float | None = None

    # association ------------------------------------------------------------------------------
    def _predict(self, tr: EmberTrack, t: float) -> tuple[float, float, float]:
        dt = max(0.0, t - tr.last_t)
        held = min(dt, self.coast_hold)
        rest = dt - held
        k = held + (self.coast_tau * (1.0 - math.exp(-rest / self.coast_tau)) if self.coast_tau > 0 else rest)
        reach = (self.gate_px + self.gate_speed_frac * math.hypot(tr.vx, tr.vy) * dt
                 + self.gate_grow * max(0.0, dt - 0.05))
        return tr.x + tr.vx * k, tr.y + tr.vy * k, min(reach, self.gate_max)

    def _assign(self, tracks: list[EmberTrack], det_xy: np.ndarray, free: np.ndarray, t: float) -> list[tuple[int, int]]:
        cols = np.flatnonzero(free)
        if not tracks or cols.size == 0:
            return []
        cost = np.full((len(tracks), cols.size), BIG)
        for i, tr in enumerate(tracks):
            px, py, reach = self._predict(tr, t)
            d = np.hypot(det_xy[cols, 0] - px, det_xy[cols, 1] - py)
            ok = d <= reach
            # Distance in px, plus the reach a track gained while unseen: between two candidates
            # the one seen more recently wins (a stale track's wide reach must not win by itself).
            cost[i, ok] = d[ok] + self.gate_grow * max(0.0, t - tr.last_t)
        rows, cc = linear_sum_assignment(cost)
        return [(int(r), int(cols[c])) for r, c in zip(rows, cc) if cost[r, c] < BIG]

    # update -----------------------------------------------------------------------------------
    def update(self, blobs: Blobs, t: float) -> None:
        self.t = t
        det_xy = np.column_stack([blobs.x, blobs.y]) if len(blobs) else np.zeros((0, 2))
        free = np.ones(len(det_xy), bool)
        prev = self.t_prev
        self.t_prev = t
        for tr in self.tracks:
            tr.seen = False
        known = [tr for tr in self.tracks if tr.shown or tr.confirmed]
        live = [tr for tr in known if prev is not None and tr.last_t >= prev]
        unseen = sorted([tr for tr in known if not (prev is not None and tr.last_t >= prev)],
                        key=lambda tr: (not tr.shown, tr.static))
        rest = [tr for tr in self.tracks if not (tr.shown or tr.confirmed)]
        for group in (live, unseen, rest):
            for r, j in self._assign(group, det_xy, free, t):
                free[j] = False
                self._hit(group[r], blobs, j, t)
        for j in np.flatnonzero(free):
            tr = EmberTrack(self._next_id, t, float(det_xy[j, 0]), float(det_xy[j, 1]), t,
                            (float(det_xy[j, 0]), float(det_xy[j, 1])), [(t, float(det_xy[j, 0]), float(det_xy[j, 1]))],
                            on_bg=bool(blobs.on_bg[j]), box=blobs.boxes[j], diam=float(blobs.diam[j]))
            self._next_id += 1
            self.tracks.append(tr)
        self._lifecycle(t)

    def _hit(self, tr: EmberTrack, blobs: Blobs, j: int, t: float) -> None:
        x, y = float(blobs.x[j]), float(blobs.y[j])
        tr.pts.append((t, x, y))
        tr.x, tr.y, tr.last_t = x, y, t
        tr.hits += 1
        tr.seen = True
        tr.on_bg = bool(blobs.on_bg[j])
        tr.box = blobs.boxes[j]
        tr.diam = float(blobs.diam[j])
        tr.travel = max(tr.travel, math.hypot(x - tr.anchor[0], y - tr.anchor[1]))
        if tr.rest_at is None or math.hypot(x - tr.rest_at[0], y - tr.rest_at[1]) >= self.min_travel:
            tr.rest_at, tr.rest_t = (x, y), t
        # A static light's track can live all day: keep only its last few seconds of points
        # (an ember keeps its whole path, at most MAX_POINTS, for the trail and the ruler check).
        if tr.static and not tr.shown and len(tr.pts) > 300:
            tr.pts = tr.pts[-150:]
        elif len(tr.pts) > MAX_POINTS:
            tr.pts = tr.pts[-MAX_POINTS // 2:]
        v = self._velocity(tr)
        if v is not None:
            tr.vx, tr.vy, n = v
            sp = math.hypot(tr.vx, tr.vy)
            tr.speed = sp if n >= self.speed_min_points else None
            if tr.speed is not None:
                tr.peak_speed = max(tr.peak_speed, sp)

    def _velocity(self, tr: EmberTrack) -> tuple[float, float, int] | None:
        t_end = tr.pts[-1][0]
        sel = [p for p in tr.pts[-64:] if p[0] >= t_end - self.speed_window_s - 1e-9]
        if len(sel) < 2:
            if len(tr.pts) >= 2:
                (t1, x1, y1), (t2, x2, y2) = tr.pts[-2], tr.pts[-1]
                dt = t2 - t1
                if dt > 0:
                    return (x2 - x1) / dt, (y2 - y1) / dt, 2
            return None
        a = np.array(sel)
        tt = a[:, 0] - a[:, 0].mean()
        den = float((tt * tt).sum())
        if den <= 0:
            return None
        return float((tt * a[:, 1]).sum() / den), float((tt * a[:, 2]).sum() / den), len(sel)

    def _lifecycle(self, t: float) -> None:
        keep = []
        shown = sum(1 for tr in self.tracks if tr.shown)
        for tr in sorted(self.tracks, key=lambda tr: tr.t0):
            unseen = t - tr.last_t
            if not tr.confirmed and tr.hits >= self.confirm_hits and tr.last_t - tr.t0 <= self.confirm_window_s + 1e-9:
                tr.confirmed = True
            if not tr.confirmed:
                if t - tr.t0 > self.confirm_window_s + 1e-9 or unseen > self.lost_s:
                    self._end(tr, counted=False)
                    continue
            elif not tr.shown:
                if (tr.seen and tr.travel >= self.min_travel and tr.peak_speed >= self.min_show_speed
                        and not tr.on_bg and shown < self.max_tracks):
                    tr.shown, tr.shown_t, tr.static = True, t, False
                    taken = {o.slot for o in self.tracks if o.shown and o is not tr}
                    tr.slot = next(k for k in range(1, self.max_tracks + 1) if k not in taken)
                    shown += 1
                elif t - tr.t0 >= self.static_s:
                    tr.static = True
            if tr.shown and tr.seen and tr.on_bg and t - tr.rest_t >= self.static_s:
                # A shown track resting on a bright static light: it caught the light, not a phone.
                tr.shown, tr.static, tr.slot, tr.shown_t = False, True, None, None
                tr.anchor, tr.travel, tr.peak_speed = (tr.x, tr.y), 0.0, 0.0
                shown -= 1
            if tr.shown and unseen > self.max_coast_s:
                self._end(tr)
                shown -= 1
                continue
            if not tr.shown and tr.confirmed and unseen > (self.static_forget_s if tr.static else self.lost_s):
                self._end(tr)
                continue
            keep.append(tr)
        self.tracks = keep

    def _end(self, tr: EmberTrack, counted: bool = True) -> None:
        if counted:
            self.finished.append(tr)
        tr.slot = None

    def pop_finished(self) -> list[EmberTrack]:
        out, self.finished = self.finished, []
        return out

    def finish_all(self) -> list[EmberTrack]:
        out = self.pop_finished() + [tr for tr in self.tracks if tr.confirmed]
        self.tracks = []
        return out

    def shown(self) -> list[EmberTrack]:
        return [tr for tr in self.tracks if tr.shown]

    def static_tracks(self) -> list[EmberTrack]:
        return [tr for tr in self.tracks if tr.static and not tr.shown]
