"""Multi-target ember tracker: constant-velocity Kalman filters with Hungarian assignment.

Per frame (`Tracker.update`):
1. Time step. dt is the true timestamp difference. A "virtual frame" counter advances by
   the larger of the frame-index step and round(dt / nominal interval), so dropped frames
   and time gaps both count as missed frames for coasting and confirmation.
2. Gap expiry. Tracks that could not legitimately be matched after a long gap (they would
   exceed the coasting limit or could no longer reach confirmation) end before association.
3. Kinematic tracks (two or more hits) are predicted to t. The assignment cost is the
   squared Mahalanobis distance d2 with the innovation covariance S = H P H^T + R, gated at
   track.gate_chi2. When a detection is a streak (length above track.angle_min_length_px,
   default 5 px) and the angle between the predicted velocity and the streak axis
   (mod 180 degrees) exceeds track.angle_penalty_deg, track.angle_penalty_cost is added.
   scipy's linear_sum_assignment solves it and gated pairs are discarded. Confirmed
   tracks are assigned first and tentative tracks get the remaining detections.
   Density-adaptive gate: the gate ellipse {d2 <= g} covers pi g sqrt(det S) px^2, so at a
   local density lambda of detections (per px^2, from the distance to the
   track.clutter_knn-th nearest detection in the frame) it holds lambda pi g sqrt(det S)
   other detections on average. A pair is kept only while that number, with g set to the
   pair's own d2, stays at or below track.gate_clutter_max: in a dense shower a coasting
   track with a wide gate does not grab a neighbour, in a sparse scene it rarely binds.
   Process noise per track: the power spectral density is scaled by a factor between 1
   and (track.accel_sigma_max_px / track.accel_sigma_px)^2. A new track starts at the top
   and every matched innovation moves the log factor by track.accel_adapt_rate
   (ln d2 - E[ln d2]), with E[ln d2] = ln 2 - 0.5772 for a well-modelled track, at most
   track.accel_adapt_up_max upward and track.accel_adapt_down_max downward
   (`Tracker._adapt_noise`): a smoothly moving ember earns a tight gate within a few hits,
   while a track whose innovations stay large (an LED on a turntable, an ember in a
   vortex) keeps a wide one, and one lucky small innovation of such a track cannot drop
   its gate to the floor.
4. Single-hit tentative tracks have no velocity yet. Their first association takes the
   nearest remaining detection within max(track.birth_radius_px, 1.5 L) (L is the longer
   streak of the pair; 1.5 is track.birth_length_factor), scaled by the frames elapsed.
   Without an exposure estimate the length term is divided by track.birth_duty_min, the
   smallest exposure fraction of the frame interval assumed (a streak from a half-frame
   exposure is half the per-frame displacement).
   When an exposure estimate is known (`set_exposure_hint`) the length term becomes
   1.5 L dt / T_exp, the expected per-frame displacement of a streak. Streak orientation
   is a hint: a displacement that disagrees with either streak axis by more than
   track.angle_penalty_deg costs track.angle_penalty_cost. The same clutter limit applies:
   the second point must lie closer than the distance within which
   track.gate_clutter_max other detections are expected at the candidate's local density
   (searched over the full disk, or only over the two wedges within
   track.angle_penalty_deg of the axis when the pair is aligned with a streak, because a
   competitor would have to be aligned too). The second hit initialises the Kalman state
   by two-point differencing.
5. Remaining detections start new tentative tracks.
6. Lifecycle. A tentative track is confirmed after track.confirm_hits hits within
   track.confirm_window frames of its birth, and dropped as soon as that becomes
   impossible. A confirmed track coasts on predictions for up to track.max_coast frames,
   then finishes; trailing coasted points are trimmed so a track ends on a real hit. When
   a coasting track is matched again, its coasted records are replaced by the cubic
   Hermite interpolation between the filtered states before and after the gap
   (`_fill_gap`); the live snapshots of those frames were the predictions.
7. Static lights. A confirmed track whose least-squares speed over the trailing
   track.static_seconds stays below track.static_speed_px_s, once it has existed that
   long, is flagged static (permanently) and `static_since` records where that slow window
   began. The fit uses running sums, so it costs O(1) per hit.

Each track stores one record per frame it was alive in (RECORD_FIELDS): frame, time,
measured position (NaN when coasted), filtered state, the detection's length, theta,
peak, flux, color and flags, a coasted flag and the detection's index in that frame.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Iterable

import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.spatial import cKDTree

from wfglink.detect.candidates import Detections
from wfglink.track import kalman as kf

RECORD_FIELDS = ("frame", "t", "x_meas", "y_meas", "x", "y", "vx", "vy", "length", "theta",
                 "peak", "flux", "color", "flags", "coasted", "det_index")
_RECORD_DTYPES = {"frame": np.int64, "flags": np.uint8, "coasted": bool, "det_index": np.int64}

TENTATIVE = "tentative"
CONFIRMED = "confirmed"
FINISHED = "finished"

_NAN = float("nan")
# Mean of ln d2 when d2 follows a chi-square law with 2 degrees of freedom: ln 2 minus
# Euler's constant.
_LOG_D2_MEAN = math.log(2.0) - 0.5772156649015329


@dataclass(slots=True)
class TrackSnapshot:
    """State of one active confirmed track at the current frame."""

    track_id: int
    frame: int
    t: float
    x: float          # filtered position, px
    y: float
    vx: float         # filtered velocity, px/s
    vy: float
    n_hits: int
    n_points: int
    coasted: bool     # no detection this frame, position is a prediction
    static: bool
    length: float     # streak length of this frame's detection, NaN when coasted
    theta: float


class Track:
    """One track: identity, status and per-frame records (tuples in RECORD_FIELDS order)."""

    __slots__ = ("track_id", "status", "static", "static_since", "records", "birth_vframe",
                 "hits", "last_hit_vframe", "t_first", "_sums", "_window")

    def __init__(self, track_id: int, vframe: int, t: float):
        self.track_id = track_id
        self.status = TENTATIVE
        self.static = False
        self.static_since = _NAN     # start of the slow window that flagged the track static
        self.records: list[tuple] = []
        self.birth_vframe = vframe
        self.hits = 0
        self.last_hit_vframe = vframe
        self.t_first = t
        # Running sums for the static test: n, St, Stt, Sx, Sy, Stx, Sty over the window.
        self._sums = [0.0] * 7
        self._window: deque = deque()

    def __len__(self) -> int:
        return len(self.records)

    def __repr__(self) -> str:
        return (f"Track(id={self.track_id}, status={self.status}, static={self.static}, "
                f"points={len(self.records)}, hits={self.hits})")

    @property
    def n_points(self) -> int:
        return len(self.records)

    @property
    def t_start(self) -> float:
        return self.records[0][1] if self.records else _NAN

    @property
    def t_end(self) -> float:
        return self.records[-1][1] if self.records else _NAN

    @property
    def duration(self) -> float:
        return self.t_end - self.t_start if self.records else 0.0

    def arrays(self) -> dict[str, np.ndarray]:
        """Records as a dict of numpy arrays keyed by RECORD_FIELDS."""
        if not self.records:
            return {k: np.zeros(0, dtype=_RECORD_DTYPES.get(k, np.float64)) for k in RECORD_FIELDS}
        cols = list(zip(*self.records))
        return {k: np.asarray(c, dtype=_RECORD_DTYPES.get(k, np.float64))
                for k, c in zip(RECORD_FIELDS, cols)}

    def to_frame(self):
        """Records as a pandas DataFrame with track_id, status and static columns."""
        import pandas as pd

        df = pd.DataFrame(self.arrays())
        df.insert(0, "track_id", np.int64(self.track_id))
        df["status"] = self.status
        df["static"] = self.static
        return df

    # Static test ------------------------------------------------------------------------
    def _static_push(self, t_rel: float, x: float, y: float) -> None:
        s = self._sums
        s[0] += 1.0
        s[1] += t_rel
        s[2] += t_rel * t_rel
        s[3] += x
        s[4] += y
        s[5] += t_rel * x
        s[6] += t_rel * y
        self._window.append((t_rel, x, y))

    def _static_check(self, t_rel_now: float, window_s: float, speed_thr: float,
                      tol_s: float, t_now: float) -> None:
        s, w = self._sums, self._window
        cutoff = t_rel_now - window_s
        while w and w[0][0] <= cutoff - tol_s:
            tr, x, y = w.popleft()
            s[0] -= 1.0
            s[1] -= tr
            s[2] -= tr * tr
            s[3] -= x
            s[4] -= y
            s[5] -= tr * x
            s[6] -= tr * y
        if self.status != CONFIRMED or s[0] < 3:
            return
        den = s[0] * s[2] - s[1] * s[1]
        if den <= 0:
            return
        ux = (s[0] * s[5] - s[1] * s[3]) / den
        uy = (s[0] * s[6] - s[1] * s[4]) / den
        if math.hypot(ux, uy) < speed_thr:
            self.static = True
            self.static_since = t_now - window_s
            w.clear()


def tracks_to_frame(tracks: Iterable[Track]):
    """Concatenate the records of many tracks into one long pandas DataFrame."""
    import pandas as pd

    frames = [tr.to_frame() for tr in tracks]
    if not frames:
        cols = {"track_id": np.zeros(0, np.int64)}
        cols.update(Track(0, 0, 0.0).arrays())
        df = pd.DataFrame(cols)
        df["status"] = pd.Series(dtype=object)
        df["static"] = pd.Series(dtype=bool)
        return df
    return pd.concat(frames, ignore_index=True)


def _fill_gap(records: list[tuple], t1: float, x1: list[float]) -> None:
    """Replace the trailing coasted records by an interpolation up to the new hit.

    The coasted records hold one-sided predictions from the last hit. Once the track is
    matched again at time t1 with filtered state x1 = [x, y, vx, vy], the positions and
    velocities in between follow from the cubic Hermite curve through the two filtered
    states (position and velocity at both ends), which is exact for constant acceleration.
    The records stay flagged as coasted, with no measured position.
    """
    k = len(records)
    while k > 0 and records[k - 1][14]:
        k -= 1
    if k == 0:
        return
    h = records[k - 1]
    t0 = h[1]
    span = t1 - t0
    if not span > 0:
        return
    p0 = (h[4], h[5])
    v0 = (h[6], h[7])
    if not (math.isfinite(v0[0]) and math.isfinite(v0[1])):
        v0 = ((x1[0] - p0[0]) / span, (x1[1] - p0[1]) / span)
    p1, v1 = (x1[0], x1[1]), (x1[2], x1[3])
    for i in range(k, len(records)):
        r = records[i]
        s = (r[1] - t0) / span
        s2, s3 = s * s, s * s * s
        h00, h10, h01, h11 = 2 * s3 - 3 * s2 + 1, s3 - 2 * s2 + s, -2 * s3 + 3 * s2, s3 - s2
        d00, d10, d01, d11 = 6 * s2 - 6 * s, 3 * s2 - 4 * s + 1, -6 * s2 + 6 * s, 3 * s2 - 2 * s
        pos = [h00 * p0[c] + h10 * span * v0[c] + h01 * p1[c] + h11 * span * v1[c] for c in (0, 1)]
        vel = [(d00 * p0[c] + d01 * p1[c]) / span + d10 * v0[c] + d11 * v1[c] for c in (0, 1)]
        records[i] = r[:4] + (pos[0], pos[1], vel[0], vel[1]) + r[8:]


def _local_density(xy: np.ndarray, k: int) -> np.ndarray:
    """Density of other detections around each detection (per px^2), from the k-th neighbour.

    lambda_j = k / (pi d_k^2) with d_k the distance from detection j to its k-th nearest
    other detection in the same frame. With fewer than k others, all of them are used.
    A detection with no other detection gets density 0.
    """
    m = xy.shape[0]
    if m < 2:
        return np.zeros(m)
    kk = min(k, m - 1)
    dist, _ = cKDTree(xy).query(xy, k=kk + 1)
    dk = np.maximum(dist[:, kk], 0.5)
    return kk / (np.pi * dk * dk)


def _wrap_axis(a: np.ndarray) -> np.ndarray:
    """Absolute angle difference folded to [0, pi/2] for axes defined mod pi."""
    return np.abs(np.mod(a + np.pi / 2, np.pi) - np.pi / 2)


def _assign(rows: np.ndarray, cols: np.ndarray, cost: np.ndarray, n: int, m: int
            ) -> tuple[np.ndarray, np.ndarray]:
    """Minimum-cost one-to-one assignment over the listed valid (row, col, cost) pairs.

    Pairs whose row and column each have no other valid partner are matched directly.
    The rest go to scipy's linear_sum_assignment on the smallest dense sub-matrix, where
    an invalid pair costs more than any complete set of valid pairs, so the solver first
    maximises the number of valid matches and then minimises their total cost. Assigned
    invalid pairs are discarded. Returns matched (rows, cols).
    """
    if rows.size == 0:
        e = np.zeros(0, np.int64)
        return e, e
    rc = np.bincount(rows, minlength=n)
    cc = np.bincount(cols, minlength=m)
    simple = (rc[rows] == 1) & (cc[cols] == 1)
    if simple.all():
        return rows, cols
    hard = ~simple
    hr, hc, hcost = rows[hard], cols[hard], cost[hard]
    ur, ir = np.unique(hr, return_inverse=True)
    uc, ic = np.unique(hc, return_inverse=True)
    big = (float(hcost.max()) + 1.0) * (min(ur.size, uc.size) + 1)
    sub = np.full((ur.size, uc.size), big)
    sub[ir, ic] = hcost
    ok_sub = np.zeros(sub.shape, dtype=bool)
    ok_sub[ir, ic] = True
    r, c = linear_sum_assignment(sub)
    ok = ok_sub[r, c]
    return (np.concatenate((rows[simple], ur[r[ok]])),
            np.concatenate((cols[simple], uc[c[ok]])))


class Tracker:
    """Track ember detections frame by frame.

    Parameters
    ----------
    cfg: resolved config; reads the `track` section.
    fps: nominal frame rate. When None, the nominal frame interval is the median of the
        first `dt_estimate_frames` observed timestamp differences.
    keep_history: keep every finished confirmed track for `all_tracks` (offline use).
        Live use can turn it off and consume `pop_finished` instead.
    """

    def __init__(self, cfg: dict, fps: float | None = None, keep_history: bool = True,
                 dt_estimate_frames: int = 15):
        t = cfg["track"]
        self.gate_chi2 = float(t["gate_chi2"])
        self.angle_penalty_rad = math.radians(float(t["angle_penalty_deg"]))
        self.angle_penalty_cost = float(t["angle_penalty_cost"])
        self.angle_min_length = float(t.get("angle_min_length_px", 5.0))
        self.confirm_hits = max(2, int(t["confirm_hits"]))
        self.confirm_window = max(self.confirm_hits, int(t["confirm_window"]))
        self.max_coast = max(0, int(t["max_coast"]))
        # Density-adaptive gating: at most this many other detections are expected inside a
        # gate or closer than a new track's second point (0 turns it off); the local
        # density comes from the distance to the clutter_knn-th nearest detection.
        self.clutter_max = max(0.0, float(t.get("gate_clutter_max", 0.0)))
        self.clutter_knn = max(1, int(t.get("clutter_knn", 4)))
        self._wedge_frac = min(1.0, 4.0 * float(t["angle_penalty_deg"]) / 360.0)
        # Adaptive process noise: each kinematic track scales q by a factor between 1 and
        # (accel_sigma_max_px / accel_sigma_px)^2, starting at the top (see _adapt_noise).
        a0 = float(t.get("accel_sigma_px", 3.0))
        a_max = max(a0, float(t.get("accel_sigma_max_px", a0)))
        self._log_qs_max = 2.0 * math.log(a_max / a0) if a0 > 0 else 0.0
        self.accel_adapt_rate = max(0.0, float(t.get("accel_adapt_rate", 1.0)))
        self.accel_adapt_up_max = max(0.0, float(t.get("accel_adapt_up_max", 0.25)))
        self.accel_adapt_down_max = max(0.0, float(t.get("accel_adapt_down_max", 0.5)))
        self.birth_radius = float(t["birth_radius_px"])
        self.birth_length_factor = float(t.get("birth_length_factor", 1.5))
        # Without an exposure estimate the streak may cover only part of the frame interval;
        # the reach assumes it covers at least this fraction (1.0 keeps the plain 1.5 L).
        self.birth_duty_min = min(1.0, max(0.05, float(t.get("birth_duty_min", 1.0))))
        self.static_seconds = float(t["static_seconds"])
        self.static_speed = float(t["static_speed_px_s"])
        self.keep_history = keep_history
        self.dt_estimate_frames = max(1, int(dt_estimate_frames))
        self._fixed_dt = fps is not None
        self.model = kf.ConstantVelocityModel(cfg, 1.0 / float(fps) if fps else None)
        self.t_exp_hint: float | None = None
        # Track ids are unique over the tracker's lifetime, also across `reset`, so
        # consumers keyed by track id (gate counters, the rolling exposure estimate) that
        # are not reset at the same time never confuse a new track with an old one.
        self._next_id = 1
        self.reset()

    # Public API -------------------------------------------------------------------------
    def reset(self) -> None:
        """Forget every track and the time base (for example when a booth clip loops).

        Track ids keep increasing, so ids from before the reset are never reused.
        """
        self._kin: list[Track] = []
        self._x = np.zeros((0, 4))
        self._p = np.zeros((0, 4, 4))
        self._lqs = np.zeros(0)          # log of each kinematic track's process-noise scale
        self._single: list[Track] = []
        self._s_xy = np.zeros((0, 2))
        self._s_len = np.zeros(0)
        self._s_theta = np.zeros(0)
        self._s_t = np.zeros(0)
        self._s_vf = np.zeros(0, np.int64)
        self._s_r = np.zeros((0, 2, 2))
        self._finished_queue: list[Track] = []
        self._archive: list[Track] = []
        self._t_prev: float | None = None
        self._f_prev: int | None = None
        self._t_origin = 0.0
        self._vframe = 0
        self._dts: list[float] = []
        if not self._fixed_dt:
            self.model.dt_nominal = None
            self.model.q = float("nan")
        self.n_frames = 0
        self.n_deleted_tentative = 0

    def set_exposure_hint(self, t_exp: float | None) -> None:
        """Exposure time (s) from `wfglink.measure.exposure`, or None to forget it."""
        self.t_exp_hint = float(t_exp) if t_exp is not None and t_exp > 0 else None

    @property
    def nominal_dt(self) -> float | None:
        return self.model.dt_nominal

    def update(self, det: Detections, t: float, frame_index: int) -> list[TrackSnapshot]:
        """Process the detections of one frame taken at time t (s).

        Returns snapshots of the active confirmed tracks (coasting and static ones included).
        """
        t = float(t)
        frame_index = int(frame_index)
        if self._t_prev is None:
            dt = 0.0
            step = 1
            self._t_origin = t
        else:
            dt = t - self._t_prev
            if not dt > 0:
                raise ValueError(f"frame times must increase: {t} after {self._t_prev}")
            if not self._fixed_dt and len(self._dts) < self.dt_estimate_frames:
                self._dts.append(dt)
                self.model.set_nominal_dt(float(np.median(self._dts)))
            step = max(frame_index - self._f_prev, int(round(dt / self.model.dt_nominal)), 1)
        self._vframe += step
        vf = self._vframe
        self.n_frames += 1

        m = len(det)
        if m:
            det_xy = np.column_stack((det.x, det.y)).astype(np.float64)
            det_len = np.nan_to_num(np.asarray(det.length, np.float64))
            det_theta = np.nan_to_num(np.asarray(det.theta, np.float64))
            det_r = self.model.meas_cov(det_len, det_theta)
        else:
            det_xy = np.zeros((0, 2))
            det_len = det_theta = np.zeros(0)
            det_r = np.zeros((0, 2, 2))
        dl = _DetLists(det, det_xy, det_len, det_theta) if m else None
        used = np.zeros(m, dtype=bool)
        lam = _local_density(det_xy, self.clutter_knn) if self.clutter_max > 0 and m else None

        self._expire_before(vf)

        # 1) Kinematic tracks: predict, associate, update, record.
        if self._kin:
            x, p = kf.predict(self._x, self._p, dt, self.model.q * np.exp(self._lqs))
            rows = cols = np.zeros(0, np.int64)
            if m:
                pr, pc, cost = kf.gated_pairs(x, p, det_xy, det_r, self.gate_chi2)
                if lam is not None and pr.size:
                    # The ellipse {d2 <= g} has area pi g sqrt(det S); shrink g so that it
                    # holds at most gate_clutter_max other detections at the local density.
                    a = p[pr, 0, 0] + det_r[pc, 0, 0]
                    b = p[pr, 0, 1] + det_r[pc, 0, 1]
                    d = p[pr, 1, 1] + det_r[pc, 1, 1]
                    ok = cost * np.pi * lam[pc] * np.sqrt(a * d - b * b) <= self.clutter_max
                    pr, pc, cost = pr[ok], pc[ok], cost[ok]
                streak = det_len[pc] > self.angle_min_length
                if streak.any() and self.angle_penalty_cost != 0:
                    heading = np.arctan2(x[pr, 3], x[pr, 2])
                    off = _wrap_axis(heading - det_theta[pc])
                    pen = (off > self.angle_penalty_rad) & streak
                    cost = cost + self.angle_penalty_cost * pen
                # Matching cascade: confirmed tracks choose first, tentative ones take
                # what is left, so a noise-born track cannot steal an established track's
                # detection.
                n = len(self._kin)
                conf = np.fromiter((tr.status == CONFIRMED for tr in self._kin), bool, n)
                first = conf[pr]
                r1, c1 = _assign(pr[first], pc[first], cost[first], n, m)
                taken = np.zeros(m, dtype=bool)
                taken[c1] = True
                second = ~first & ~taken[pc]
                r2, c2 = _assign(pr[second], pc[second], cost[second], n, m)
                rows, cols = np.concatenate((r1, r2)), np.concatenate((c1, c2))
                if rows.size:
                    if self._log_qs_max > 0 and self.accel_adapt_rate > 0:
                        self._adapt_noise(x, p, det_xy, det_r, rows, cols)
                    x[rows], p[rows] = kf.update(x[rows], p[rows], det_xy[cols], det_r[cols])
                    used[cols] = True
            self._x, self._p = x, p
            match = np.full(len(self._kin), -1, np.int64)
            match[rows] = cols
            self._record_kinematic(match.tolist(), x.tolist(), dl, frame_index, t, vf)

        # 2) Single-hit tentative tracks take their second point.
        rem = np.flatnonzero(~used)
        if self._single:
            self._associate_singles(rem, det_xy, det_len, det_theta, det_r, dl, used,
                                    frame_index, t, vf, lam)
            rem = np.flatnonzero(~used)

        # 3) Births from what is left.
        if rem.size:
            self._birth(rem, det_xy, det_len, det_theta, det_r, dl, frame_index, t, vf)

        # 4) Lifecycle and static test.
        self._lifecycle_after(vf, t)

        self._t_prev = t
        self._f_prev = frame_index
        return self._snapshots(frame_index, t)

    def pop_finished(self) -> list[Track]:
        """Confirmed tracks that finished since the last call."""
        out, self._finished_queue = self._finished_queue, []
        return out

    def finish_all(self) -> list[Track]:
        """End of stream: finish every confirmed track, drop tentative ones, return the queue."""
        keep = np.zeros(len(self._kin), dtype=bool)
        for tr in self._kin:
            if tr.status == CONFIRMED:
                self._finish(tr)
            else:
                self.n_deleted_tentative += 1
        self.n_deleted_tentative += len(self._single)
        self._kin = []
        self._x, self._p, self._lqs = self._x[keep], self._p[keep], self._lqs[keep]
        self._clear_singles()
        return self.pop_finished()

    def active_tracks(self, include_tentative: bool = False) -> list[Track]:
        """Tracks still alive. Single-hit tentative tracks are included only on request."""
        out = [tr for tr in self._kin if include_tentative or tr.status == CONFIRMED]
        if include_tentative:
            out.extend(self._single)
        return out

    def all_tracks(self, include_active: bool = True) -> list[Track]:
        """Every finished confirmed track (when keep_history) plus active confirmed ones."""
        out = list(self._archive)
        if include_active:
            out.extend(tr for tr in self._kin if tr.status == CONFIRMED)
        return sorted(out, key=lambda tr: tr.track_id)

    # Internals --------------------------------------------------------------------------
    def _new_track(self, vf: int, t: float) -> Track:
        tr = Track(self._next_id, vf, t)
        self._next_id += 1
        return tr

    def _adapt_noise(self, x: np.ndarray, p: np.ndarray, z: np.ndarray, r: np.ndarray,
                     rows: np.ndarray, cols: np.ndarray) -> None:
        """Move each matched track's process-noise scale by its normalised innovation.

        A new track starts at accel_sigma_max_px, because two points say nothing about how
        its ember accelerates. The squared Mahalanobis distance d2 of a correct match
        follows a chi-square law with 2 degrees of freedom when the predicted spread is
        right, and then ln d2 has mean ln 2 - 0.5772 (Euler's constant). The log scale moves
        by accel_adapt_rate (ln d2 - (ln 2 - 0.5772)): it drifts down while the predicted
        spread is too wide (a smoothly moving ember), stays put on average while it is
        right, and grows while the innovations stay larger than predicted (an ember turning
        in a vortex, an LED on a turntable). Each step is limited to accel_adapt_up_max
        upward, so one large innovation (a wrong neighbour, a noise spike) cannot open the
        gate, and to accel_adapt_down_max downward, so one lucky small innovation of a
        turning track (centroid noise cancelling its acceleration) cannot close it: an
        uncapped downward step, or a target of ln 2, which keeps the predicted spread about
        1.8 times too narrow, broke noisy turntable LEDs at 2 to 4 px per frame squared into
        many short tracks. The scale stays within [1, (accel_sigma_max_px /
        accel_sigma_px)^2].
        """
        d2 = kf.mahalanobis_pairs(x, p, z, r, rows, cols)
        step = self.accel_adapt_rate * (np.log(np.maximum(d2, 1e-6)) - _LOG_D2_MEAN)
        step = np.clip(step, -self.accel_adapt_down_max, self.accel_adapt_up_max)
        self._lqs[rows] = np.clip(self._lqs[rows] + step, 0.0, self._log_qs_max)

    def _remaining(self, tr: Track, vf: int) -> int:
        """Frames left in the confirmation window after frame vf."""
        return tr.birth_vframe + self.confirm_window - 1 - vf

    def _finish(self, tr: Track) -> None:
        recs = tr.records
        while recs and recs[-1][14]:
            recs.pop()
        tr.status = FINISHED
        self._finished_queue.append(tr)
        if self.keep_history:
            self._archive.append(tr)

    def _keep_kinematic(self, keep: np.ndarray) -> None:
        if keep.all():
            return
        idx = np.flatnonzero(keep)
        self._kin = [self._kin[i] for i in idx.tolist()]
        self._x, self._p, self._lqs = self._x[idx], self._p[idx], self._lqs[idx]

    def _expire_before(self, vf: int) -> None:
        """End tracks that a gap has already pushed past their coasting or confirm limits."""
        if self._kin:
            keep = np.ones(len(self._kin), dtype=bool)
            for i, tr in enumerate(self._kin):
                if tr.status == CONFIRMED:
                    if vf - tr.last_hit_vframe - 1 > self.max_coast:
                        self._finish(tr)
                        keep[i] = False
                elif tr.hits + max(0, self._remaining(tr, vf) + 1) < self.confirm_hits:
                    self.n_deleted_tentative += 1
                    keep[i] = False
            self._keep_kinematic(keep)
        if self._single:
            left = self._s_vf + self.confirm_window - 1 - vf + 1
            self._keep_singles(1 + np.maximum(left, 0) >= self.confirm_hits)

    def _record_kinematic(self, match: list[int], xl: list[list[float]], dl: "_DetLists | None",
                          frame_index: int, t: float, vf: int) -> None:
        t_rel = t - self._t_origin
        for tr, j, xi in zip(self._kin, match, xl):
            if j >= 0:
                if tr.records and tr.records[-1][14]:
                    _fill_gap(tr.records, t, xi)
                tr.records.append((frame_index, t, dl.x[j], dl.y[j], xi[0], xi[1], xi[2], xi[3],
                                   dl.length[j], dl.theta[j], dl.peak[j], dl.flux[j],
                                   dl.color[j], dl.flags[j], False, j))
                tr.hits += 1
                tr.last_hit_vframe = vf
                if not tr.static:
                    tr._static_push(t_rel, dl.x[j], dl.y[j])
            else:
                tr.records.append((frame_index, t, _NAN, _NAN, xi[0], xi[1], xi[2], xi[3],
                                   _NAN, _NAN, _NAN, _NAN, _NAN, 0, True, -1))

    def _associate_singles(self, rem: np.ndarray, det_xy: np.ndarray, det_len: np.ndarray,
                           det_theta: np.ndarray, det_r: np.ndarray, dl: "_DetLists | None",
                           used: np.ndarray, frame_index: int, t: float, vf: int,
                           lam: np.ndarray | None = None) -> None:
        ns = len(self._single)
        rows = cols = np.zeros(0, np.int64)
        if rem.size:
            d = det_xy[rem][None, :, :] - self._s_xy[:, None, :]          # (ns, k, 2)
            dist2 = d[..., 0] ** 2 + d[..., 1] ** 2
            el_f = (vf - self._s_vf).astype(np.float64)[:, None]
            el_t = (t - self._s_t)[:, None]
            lmax = np.maximum(self._s_len[:, None], det_len[rem][None, :])
            if self.t_exp_hint:
                reach = self.birth_length_factor * lmax * np.maximum(el_t / self.t_exp_hint, 1.0)
                radius = np.maximum(self.birth_radius * el_f, reach)
            else:
                radius = np.maximum(self.birth_radius,
                                    self.birth_length_factor * lmax / self.birth_duty_min) * el_f
            pr, pc = np.nonzero(dist2 <= radius ** 2)
            dd, rad = dist2[pr, pc], radius[pr, pc]
            pen = np.zeros(pr.size)
            aligned_streak = np.zeros(pr.size, dtype=bool)
            if pr.size:
                # Streak orientation: a displacement that disagrees with either streak axis
                # by more than angle_penalty_deg pays angle_penalty_cost per streak.
                pd = d[pr, pc]
                heading = np.arctan2(pd[:, 1], pd[:, 0])
                dj = rem[pc]
                s_streak = self._s_len[pr] > self.angle_min_length
                d_streak = det_len[dj] > self.angle_min_length
                pen = ((_wrap_axis(heading - self._s_theta[pr]) > self.angle_penalty_rad)
                       & s_streak).astype(np.float64)
                pen += (_wrap_axis(heading - det_theta[dj]) > self.angle_penalty_rad) & d_streak
                aligned_streak = (s_streak | d_streak) & (pen == 0)
            if lam is not None and pr.size:
                # Clutter cap: no more than gate_clutter_max other detections are expected
                # closer than the chosen one. For a pair aligned with a streak, a competitor
                # must be aligned too, so only the two wedges within angle_penalty_deg of the
                # axis count.
                frac = np.where(aligned_streak, self._wedge_frac, 1.0)
                cap2 = self.clutter_max / (np.pi * np.maximum(lam[rem[pc]], 1e-12) * frac)
                ok = dd <= cap2
                pr, pc, dd, pen = pr[ok], pc[ok], dd[ok], pen[ok]
                rad = np.minimum(rad[ok], np.sqrt(cap2[ok]))
            cost = self.gate_chi2 * dd / rad ** 2 + self.angle_penalty_cost * pen
            rows, cols = _assign(pr, pc, cost, ns, rem.size)
        if rows.size:
            j = rem[cols]
            used[j] = True
            # The two-point velocity covariance uses the base process noise; the track's own
            # (higher) scale applies from its first prediction on. Scaling it here as well
            # gave more identity switches on the dense core cases.
            x0, p0 = kf.init_from_two(self._s_xy[rows], self._s_t[rows], self._s_r[rows],
                                      det_xy[j], np.full(rows.size, t), det_r[j], self.model.q)
            t_rel = t - self._t_origin
            xl = x0.tolist()
            new = []
            for k, (si, dj) in enumerate(zip(rows.tolist(), j.tolist())):
                tr = self._single[si]
                xi = xl[k]
                tr.records.append((frame_index, t, dl.x[dj], dl.y[dj], xi[0], xi[1], xi[2], xi[3],
                                   dl.length[dj], dl.theta[dj], dl.peak[dj], dl.flux[dj],
                                   dl.color[dj], dl.flags[dj], False, dj))
                tr.hits += 1
                tr.last_hit_vframe = vf
                tr._static_push(t_rel, dl.x[dj], dl.y[dj])
                new.append(tr)
            self._kin.extend(new)
            self._x = np.concatenate((self._x, x0))
            self._p = np.concatenate((self._p, p0))
            self._lqs = np.concatenate((self._lqs, np.full(rows.size, self._log_qs_max)))
        keep = np.ones(ns, dtype=bool)
        keep[rows] = False
        # Unmatched singles survive only while confirmation is still possible.
        left = self._s_vf + self.confirm_window - 1 - vf
        feasible = 1 + np.maximum(left, 0) >= self.confirm_hits
        self.n_deleted_tentative += int(np.count_nonzero(keep & ~feasible))
        self._keep_singles(keep & feasible, count_deleted=False)

    def _keep_singles(self, keep: np.ndarray, count_deleted: bool = True) -> None:
        if keep.all():
            return
        if count_deleted:
            self.n_deleted_tentative += int(np.count_nonzero(~keep))
        idx = np.flatnonzero(keep)
        self._single = [self._single[i] for i in idx.tolist()]
        self._s_xy, self._s_len = self._s_xy[idx], self._s_len[idx]
        self._s_theta, self._s_t = self._s_theta[idx], self._s_t[idx]
        self._s_vf, self._s_r = self._s_vf[idx], self._s_r[idx]

    def _clear_singles(self) -> None:
        self._keep_singles(np.zeros(len(self._single), dtype=bool), count_deleted=False)

    def _birth(self, rem: np.ndarray, det_xy: np.ndarray, det_len: np.ndarray,
               det_theta: np.ndarray, det_r: np.ndarray, dl: "_DetLists",
               frame_index: int, t: float, vf: int) -> None:
        t_rel = t - self._t_origin
        new = []
        for j in rem.tolist():
            tr = self._new_track(vf, t)
            tr.records.append((frame_index, t, dl.x[j], dl.y[j], dl.x[j], dl.y[j], _NAN, _NAN,
                               dl.length[j], dl.theta[j], dl.peak[j], dl.flux[j], dl.color[j],
                               dl.flags[j], False, j))
            tr.hits = 1
            tr._static_push(t_rel, dl.x[j], dl.y[j])
            new.append(tr)
        self._single.extend(new)
        k = rem.size
        self._s_xy = np.concatenate((self._s_xy, det_xy[rem]))
        self._s_len = np.concatenate((self._s_len, det_len[rem]))
        self._s_theta = np.concatenate((self._s_theta, det_theta[rem]))
        self._s_t = np.concatenate((self._s_t, np.full(k, t)))
        self._s_vf = np.concatenate((self._s_vf, np.full(k, vf, np.int64)))
        self._s_r = np.concatenate((self._s_r, det_r[rem]))

    def _lifecycle_after(self, vf: int, t: float) -> None:
        if not self._kin:
            return
        keep = np.ones(len(self._kin), dtype=bool)
        t_rel = t - self._t_origin
        tol = 0.25 * (self.model.dt_nominal or 0.0)
        for i, tr in enumerate(self._kin):
            if tr.status == TENTATIVE:
                if tr.hits >= self.confirm_hits:
                    tr.status = CONFIRMED
                elif tr.hits + max(0, self._remaining(tr, vf)) < self.confirm_hits:
                    self.n_deleted_tentative += 1
                    keep[i] = False
                    continue
            if tr.status == CONFIRMED:
                if vf - tr.last_hit_vframe > self.max_coast:
                    self._finish(tr)
                    keep[i] = False
                    continue
                if not tr.static and t - tr.t_first >= self.static_seconds - tol:
                    tr._static_check(t_rel, self.static_seconds, self.static_speed, tol, t)
        self._keep_kinematic(keep)

    def _snapshots(self, frame_index: int, t: float) -> list[TrackSnapshot]:
        out = []
        if not self._kin:
            return out
        xl = self._x.tolist()
        for tr, xi in zip(self._kin, xl):
            if tr.status != CONFIRMED:
                continue
            rec = tr.records[-1]
            out.append(TrackSnapshot(tr.track_id, frame_index, t, xi[0], xi[1], xi[2], xi[3],
                                     tr.hits, len(tr.records), rec[14], tr.static, rec[8], rec[9]))
        return out


class _DetLists:
    """Detection columns as Python lists, so per-track record tuples are cheap to build."""

    __slots__ = ("x", "y", "length", "theta", "peak", "flux", "color", "flags")

    def __init__(self, det: Detections, det_xy: np.ndarray, det_len: np.ndarray,
                 det_theta: np.ndarray):
        self.x = det_xy[:, 0].tolist()
        self.y = det_xy[:, 1].tolist()
        self.length = det_len.tolist()
        self.theta = det_theta.tolist()
        self.peak = np.asarray(det.peak, np.float64).tolist()
        self.flux = np.asarray(det.flux, np.float64).tolist()
        self.color = np.asarray(det.color, np.float64).tolist()
        self.flags = np.asarray(det.flags).astype(np.int64).tolist()
