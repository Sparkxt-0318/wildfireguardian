"""Line-gate crossing counts, count rates and projected particle number flux.

Gate geometry. A gate is the segment p1 -> p2 in image pixels (x right, y down). Its unit
normal is n = (-(y2 - y1), x2 - x1) / |p2 - p1| and the signed distance of a point p is
d = (p - p1) . n. A crossing toward the normal (d from negative to positive) has
direction +1, the reverse -1.

Crossing detection, per track, from consecutive filtered positions of measured points
(coasted predictions are never counted):
- Hysteresis. A track's side is committed only when |d| > h (gate.hysteresis_px). A
  crossing is a change of committed side, so jitter inside the band |d| <= h never counts.
- Crossing point. Whenever consecutive positions change the sign of d, the zero
  crossing is interpolated linearly (time and position). The last such point before the
  side change is the crossing; it counts only if it projects inside the segment.
- Re-arming. After a crossing in either direction, both directions are disarmed. The
  direction toward -d re-arms only when the track has been seen beyond +2h, and the
  direction toward +d only beyond -2h. So a track that wobbles within the 2h band after
  crossing counts once, while a track that really crosses and comes back counts once
  each way.

Counts: gross (all crossings), net (+1 minus -1) and per direction, plus the event list
(track id, time, direction, position along the gate). The same counter works live (call
`update_tracks` with the active confirmed tracks every frame; each track is processed
from where it stopped last time, including its tentative points once confirmed) and
offline (call it once with all finished tracks). Tracks flagged static are skipped from
then on, and crossings they made after their slow window began are withdrawn.

Derived quantities:
- Count rate: crossings in the trailing gate.rate_window_s seconds divided by that
  window (or by the observed time when shorter).
- Cumulative Particle Count (gate): gross and net counts since the start.
- Particle Number Flux (projected, 2D): crossings / (gate length / 100 px) / duration,
  in crossings per 100 px per second; with a metres-per-pixel scale valid at a stated
  distance Z it becomes crossings per metre per second (m^-1 s^-1) "at Z".
These names mirror NIST's but are analogous to, not comparable with, NIST CPC (m^-2) and
PNF (m^-2 s^-1), which use a 3D surface.

Uncertainty: the Garwood exact Poisson interval for counts (chi-square quantiles) and a
moving-block bootstrap over 1 s bins for rates, which also captures gust-driven
overdispersion. For small counts the Garwood interval is the honest one; `rate_interval`
reports both and their union.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np
from scipy.stats import chi2


class Gate:
    """A line segment gate with hysteresis."""

    def __init__(self, p1: Sequence[float], p2: Sequence[float], hysteresis_px: float,
                 name: str = "gate"):
        self.p1 = (float(p1[0]), float(p1[1]))
        self.p2 = (float(p2[0]), float(p2[1]))
        dx, dy = self.p2[0] - self.p1[0], self.p2[1] - self.p1[1]
        self.length = math.hypot(dx, dy)
        if self.length <= 0:
            raise ValueError("gate end points must differ")
        self.ux, self.uy = dx / self.length, dy / self.length
        self.nx, self.ny = -dy / self.length, dx / self.length
        self.h = float(hysteresis_px)
        self.name = str(name)

    @classmethod
    def from_spec(cls, spec: dict, cfg: dict) -> "Gate":
        """Gate from a {name, p1, p2} dict (as in meta.json) and gate.hysteresis_px."""
        return cls(spec["p1"], spec["p2"], float(cfg.get("gate", {}).get("hysteresis_px", 2.0)),
                   spec.get("name", "gate"))

    @property
    def normal(self) -> tuple[float, float]:
        return self.nx, self.ny

    def signed_distance(self, x, y):
        """Signed distance (px) to the gate line; positive on the normal side."""
        return (np.asarray(x, dtype=np.float64) - self.p1[0]) * self.nx + \
               (np.asarray(y, dtype=np.float64) - self.p1[1]) * self.ny

    def along(self, x, y):
        """Position along the segment as a fraction: 0 at p1, 1 at p2."""
        return ((np.asarray(x, dtype=np.float64) - self.p1[0]) * self.ux +
                (np.asarray(y, dtype=np.float64) - self.p1[1]) * self.uy) / self.length

    def __repr__(self) -> str:
        return f"Gate({self.name!r}, p1={self.p1}, p2={self.p2}, h={self.h})"


@dataclass(frozen=True, slots=True)
class CrossingEvent:
    gate: str
    track_id: int
    t: float           # interpolated crossing time, s
    direction: int     # +1 toward the gate normal, -1 against
    s: float           # crossing position along the gate, 0 at p1 and 1 at p2
    x: float
    y: float


class _TrackState:
    __slots__ = ("side", "armed_pos", "armed_neg", "prev", "cand", "cursor")

    def __init__(self):
        self.side = 0              # committed side: -1, +1, or 0 before the first commit
        self.armed_pos = True
        self.armed_neg = True
        self.prev: tuple[float, float, float, float] | None = None   # (d, t, x, y)
        self.cand: tuple[float, float, float, float] | None = None   # (t, s, x, y)
        self.cursor = 0            # next record index to process (track input)


class GateCounter:
    """Incremental crossing counter for one gate."""

    def __init__(self, gate: Gate, cfg: dict | None = None, exclude_static: bool = True):
        g = (cfg or {}).get("gate", {})
        self.gate = gate
        self.rate_window_s = float(g.get("rate_window_s", 10.0))
        self.exclude_static = exclude_static
        self.reset()

    def reset(self) -> None:
        self._state: dict[int, _TrackState] = {}
        self._events: list[CrossingEvent] = []
        self._excluded: set[int] = set()
        self._archived = {"gross": 0, "positive": 0, "negative": 0}
        self._archive_cut = -np.inf
        self.t_first: float | None = None
        self.t_last: float | None = None

    # Bounded memory for long live runs ----------------------------------------------------
    def forget(self, track_id: int) -> None:
        """Drop the per-track state of a finished track (its events are kept)."""
        self._state.pop(int(track_id), None)
        self._excluded.discard(int(track_id))

    def prune_events(self, before_t: float) -> int:
        """Fold events older than `before_t` into running totals and drop them.

        Totals, flux and rates over windows that start after `before_t` stay exact;
        counts(t0, t1) with t0 earlier than the cut no longer sees the pruned events.
        Returns the number of events folded.
        """
        old = [e for e in self._events if e.t < before_t]
        if not old:
            return 0
        for e in old:
            self._archived["gross"] += 1
            self._archived["positive" if e.direction > 0 else "negative"] += 1
        self._events = [e for e in self._events if e.t >= before_t]
        self._archive_cut = max(self._archive_cut, float(before_t))
        return len(old)

    # Input -------------------------------------------------------------------------------
    def observe(self, t: float) -> None:
        """Extend the observed time span (call once per processed frame when live)."""
        t = float(t)
        self.t_first = t if self.t_first is None else min(self.t_first, t)
        self.t_last = t if self.t_last is None else max(self.t_last, t)

    def update_point(self, track_id: int, t: float, x: float, y: float) -> CrossingEvent | None:
        """Feed one position of one track (in time order). Returns a new event or None."""
        track_id = int(track_id)
        if track_id in self._excluded:
            return None
        st = self._state.get(track_id)
        if st is None:
            st = self._state[track_id] = _TrackState()
        return self._step(st, track_id, float(t), float(x), float(y))

    def update_track(self, track) -> list[CrossingEvent]:
        """Process the records of a `wfglink.track.tracker.Track` not seen before.

        A track flagged static has its unseen records processed first and is then
        excluded with `since = track.static_since`, so live use (records seen frame by
        frame before the flag) and offline use (the whole finished track at once) keep
        exactly the same crossings: those before the slow window began.
        """
        tid = int(track.track_id)
        if tid in self._excluded:
            return []
        st = self._state.get(tid)
        if st is None:
            st = self._state[tid] = _TrackState()
        out = []
        recs = track.records
        for i in range(st.cursor, len(recs)):
            r = recs[i]
            if r[14]:                       # coasted: a prediction, not a measurement
                continue
            ev = self._step(st, tid, r[1], r[4], r[5])
            if ev is not None:
                out.append(ev)
        st.cursor = len(recs)
        if self.exclude_static and track.static:
            since = getattr(track, "static_since", None)
            self.exclude(tid, since=since)
            cut = -np.inf if since is None or not np.isfinite(since) else float(since)
            out = [e for e in out if e.t < cut]
        return out

    def update_tracks(self, tracks: Iterable) -> list[CrossingEvent]:
        out: list[CrossingEvent] = []
        for tr in tracks:
            out.extend(self.update_track(tr))
        return out

    def exclude(self, track_id: int, since: float | None = None) -> None:
        """Ignore a track from now on and withdraw its crossings at or after `since`.

        With since = None every crossing of the track is withdrawn. For a track flagged
        static, `since` is the start of its slow window: a static light loses every
        jitter crossing, while an ember that crossed and then came to rest keeps its
        earlier crossing.
        """
        track_id = int(track_id)
        self._excluded.add(track_id)
        self._state.pop(track_id, None)
        cut = -np.inf if since is None or not np.isfinite(since) else float(since)
        self._events = [e for e in self._events if e.track_id != track_id or e.t < cut]

    def _step(self, st: _TrackState, tid: int, t: float, x: float, y: float
              ) -> CrossingEvent | None:
        g = self.gate
        d = (x - g.p1[0]) * g.nx + (y - g.p1[1]) * g.ny
        if st.prev is not None:
            pd, pt, px, py = st.prev
            if (pd < 0.0 <= d) or (pd > 0.0 >= d) or (pd == 0.0 and d != 0.0):
                f = pd / (pd - d) if pd != d else 0.0
                cx, cy = px + f * (x - px), py + f * (y - py)
                s = ((cx - g.p1[0]) * g.ux + (cy - g.p1[1]) * g.uy) / g.length
                st.cand = (pt + f * (t - pt), s, cx, cy)
        event = None
        if abs(d) > g.h:
            side = 1 if d > 0 else -1
            if st.side != 0 and side != st.side:
                armed = st.armed_pos if side > 0 else st.armed_neg
                if armed and st.cand is not None and 0.0 <= st.cand[1] <= 1.0:
                    ct, cs, cx, cy = st.cand
                    event = CrossingEvent(g.name, tid, ct, side, cs, cx, cy)
                    self._events.append(event)
                    st.armed_pos = st.armed_neg = False
            st.side = side
            st.cand = None
        if d > 2.0 * g.h:
            st.armed_neg = True
        elif d < -2.0 * g.h:
            st.armed_pos = True
        st.prev = (d, t, x, y)
        return event

    # Output ------------------------------------------------------------------------------
    @property
    def events(self) -> list[CrossingEvent]:
        return sorted(self._events, key=lambda e: (e.t, e.track_id))

    def counts(self, t0: float | None = None, t1: float | None = None) -> dict[str, int]:
        """Gross, net, positive and negative crossings with t0 <= t < t1 (all when None)."""
        ev = [e for e in self._events
              if (t0 is None or e.t >= t0) and (t1 is None or e.t < t1)]
        pos = sum(1 for e in ev if e.direction > 0)
        neg = len(ev) - pos
        if t0 is None or t0 < self._archive_cut:  # include events folded by prune_events
            pos += self._archived["positive"]
            neg += self._archived["negative"]
        return {"gross": pos + neg, "net": pos - neg, "positive": pos, "negative": neg}

    def duration(self) -> float:
        if self.t_first is None or self.t_last is None:
            return 0.0
        return self.t_last - self.t_first

    def rate(self, t_now: float | None = None, window_s: float | None = None,
             net: bool = False) -> float:
        """Crossings per second over the trailing window ending at t_now."""
        w = self.rate_window_s if window_s is None else float(window_s)
        if t_now is None:
            t_now = self.t_last if self.t_last is not None else 0.0
        span = w if self.t_first is None else min(w, t_now - self.t_first)
        if span <= 0:
            return float("nan")
        val = sum((e.direction if net else 1) for e in self._events if t_now - w < e.t <= t_now)
        return val / span

    def cumulative_particle_count(self, ci: float = 0.95) -> dict[str, float]:
        """Cumulative Particle Count (gate): gross and net, with Garwood intervals."""
        c = self.counts()
        g_lo, g_hi = garwood_interval(c["gross"], ci)
        p_lo, p_hi = garwood_interval(c["positive"], ci)
        n_lo, n_hi = garwood_interval(c["negative"], ci)
        # Net = positive - negative; a conservative interval combines the extremes.
        return {"gross": c["gross"], "gross_lo": g_lo, "gross_hi": g_hi,
                "net": c["net"], "net_lo": p_lo - n_hi, "net_hi": p_hi - n_lo,
                "positive": c["positive"], "negative": c["negative"]}

    def particle_number_flux(self, duration_s: float | None = None, net: bool = False,
                             m_per_px: float | None = None, z_m: float | None = None,
                             ci: float = 0.95) -> "FluxValue":
        dur = self.duration() if duration_s is None else float(duration_s)
        c = self.counts()
        n = c["net"] if net else c["gross"]
        return particle_number_flux(n, self.gate.length, dur, m_per_px=m_per_px, z_m=z_m,
                                    ci=ci, net=net)

    def rate_interval(self, t0: float | None = None, t1: float | None = None,
                      net: bool = False, cfg: dict | None = None, seed: int = 0,
                      ci: float = 0.95) -> dict[str, float]:
        """Rate over [t0, t1) with Garwood and moving-block bootstrap intervals."""
        t0 = self.t_first if t0 is None else t0
        t1 = self.t_last if t1 is None else t1
        if t0 is None or t1 is None or t1 <= t0:
            nan = float("nan")
            return {"rate": nan, "garwood_lo": nan, "garwood_hi": nan, "boot_lo": nan,
                    "boot_hi": nan, "lo": nan, "hi": nan, "n": 0}
        ev = [e for e in self._events if t0 <= e.t < t1]
        times = np.array([e.t for e in ev], dtype=np.float64)
        w = np.array([e.direction for e in ev], dtype=np.float64) if net else np.ones(len(ev))
        g = (cfg or {}).get("gate", {})
        boot = block_bootstrap_rate(times, w, t0, t1, bin_s=float(g.get("bootstrap_bin_s", 1.0)),
                                    block_bins=g.get("bootstrap_block_bins"),
                                    n_boot=int(g.get("bootstrap", 1000)), ci=ci, seed=seed)
        dur = t1 - t0
        if net:
            pos = int(np.sum(w > 0))
            neg = len(ev) - pos
            p_lo, p_hi = garwood_interval(pos, ci)
            n_lo, n_hi = garwood_interval(neg, ci)
            g_lo, g_hi = (p_lo - n_hi) / dur, (p_hi - n_lo) / dur
        else:
            g_lo, g_hi = (v / dur for v in garwood_interval(len(ev), ci))
        return {"rate": boot["rate"], "garwood_lo": g_lo, "garwood_hi": g_hi,
                "boot_lo": boot["lo"], "boot_hi": boot["hi"],
                "lo": min(g_lo, boot["lo"]), "hi": max(g_hi, boot["hi"]), "n": len(ev)}

    def events_frame(self):
        """Events as a pandas DataFrame."""
        import pandas as pd

        ev = self.events
        return pd.DataFrame({
            "gate": pd.Series([e.gate for e in ev], dtype=object),
            "track_id": np.array([e.track_id for e in ev], dtype=np.int64),
            "t": np.array([e.t for e in ev], dtype=np.float64),
            "direction": np.array([e.direction for e in ev], dtype=np.int8),
            "s": np.array([e.s for e in ev], dtype=np.float64),
            "x": np.array([e.x for e in ev], dtype=np.float64),
            "y": np.array([e.y for e in ev], dtype=np.float64)})


def count_crossings(gate: Gate, tracks: Iterable, cfg: dict | None = None,
                    exclude_static: bool = True,
                    t_span: tuple[float, float] | None = None) -> GateCounter:
    """Offline: count crossings of finished tracks.

    The observed span (used by rates, `duration` and the flux) should be the span of the
    processed frames, given as t_span = (first frame time, last frame time). Without it
    the span of the tracks is used, which is shorter than the clip whenever the first or
    last frames hold no track, and then the rate and flux come out too high.
    """
    counter = GateCounter(gate, cfg, exclude_static)
    if t_span is not None:
        counter.observe(t_span[0])
        counter.observe(t_span[1])
    for tr in tracks:
        counter.update_track(tr)
        if tr.records and t_span is None:
            counter.observe(tr.t_start)
            counter.observe(tr.t_end)
    return counter


# Statistics ------------------------------------------------------------------------------
def garwood_interval(n, ci: float = 0.95):
    """Garwood exact Poisson confidence interval for an observed count n (scalar or array).

    lower = chi2.ppf(alpha / 2, 2 n) / 2 (0 when n = 0),
    upper = chi2.ppf(1 - alpha / 2, 2 n + 2) / 2.
    """
    n_arr = np.asarray(n, dtype=np.float64)
    alpha = 1.0 - ci
    lo = np.where(n_arr > 0, chi2.ppf(alpha / 2, 2 * np.maximum(n_arr, 1.0)) / 2, 0.0)
    hi = chi2.ppf(1 - alpha / 2, 2 * n_arr + 2) / 2
    if n_arr.ndim == 0:
        return float(lo), float(hi)
    return lo, hi


def block_bootstrap_rate(times: np.ndarray, weights: np.ndarray, t0: float, t1: float,
                         bin_s: float = 1.0, block_bins: int | None = None,
                         n_boot: int = 1000, ci: float = 0.95, seed: int = 0) -> dict[str, float]:
    """Moving-block bootstrap of an event rate over fixed time bins.

    Events (with weights: 1 for gross, +-1 for net) are binned into bins of bin_s seconds
    over [t0, t1]. Blocks of `block_bins` consecutive bins (default round(n_bins^(1/3)))
    are drawn with replacement from all overlapping blocks and concatenated to the
    original length. The rate is the bin total over the duration.
    """
    times = np.asarray(times, dtype=np.float64)
    weights = np.asarray(weights, dtype=np.float64)
    dur = float(t1 - t0)
    nan = float("nan")
    if dur <= 0:
        return {"rate": nan, "lo": nan, "hi": nan, "sd": nan, "n_bins": 0, "block_bins": 0}
    n_bins = max(1, int(math.ceil(dur / bin_s - 1e-9)))
    idx = np.clip(((times - t0) / bin_s).astype(np.int64), 0, n_bins - 1)
    per_bin = np.bincount(idx, weights, minlength=n_bins).astype(np.float64)
    rate = float(per_bin.sum() / dur)
    blk = int(block_bins) if block_bins else max(1, int(round(n_bins ** (1.0 / 3.0))))
    blk = min(blk, n_bins)
    n_blocks = int(math.ceil(n_bins / blk))
    starts_all = n_bins - blk + 1
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, starts_all, size=(n_boot, n_blocks))
    cum = np.concatenate(([0.0], np.cumsum(per_bin)))
    block_sums = cum[np.arange(starts_all) + blk] - cum[np.arange(starts_all)]
    # The last block may overhang the original length: keep only its first bins.
    tail = n_bins - (n_blocks - 1) * blk
    tail_sums = cum[np.arange(starts_all) + tail] - cum[np.arange(starts_all)]
    totals = block_sums[starts[:, :-1]].sum(axis=1) + tail_sums[starts[:, -1]]
    boot = totals / dur
    alpha = 1.0 - ci
    lo, hi = np.quantile(boot, [alpha / 2, 1 - alpha / 2])
    return {"rate": rate, "lo": float(lo), "hi": float(hi), "sd": float(np.std(boot, ddof=1)),
            "n_bins": n_bins, "block_bins": blk}


@dataclass(frozen=True)
class FluxValue:
    value: float
    lo: float
    hi: float
    unit: str
    label: str


def particle_number_flux(n: float, gate_length_px: float, duration_s: float,
                         m_per_px: float | None = None, z_m: float | None = None,
                         ci: float = 0.95, net: bool = False) -> FluxValue:
    """Particle Number Flux (projected, 2D) with a Garwood interval on the count.

    Uncalibrated: crossings / (gate length / 100 px) / duration, per 100 px per second.
    With m_per_px (valid at distance z_m): crossings / (gate length in m) / duration, in
    m^-1 s^-1. For a net flux the interval is omitted (NaN); use `rate_interval`.
    """
    nan = float("nan")
    if duration_s <= 0 or gate_length_px <= 0:
        return FluxValue(nan, nan, nan, "", "")
    if m_per_px is not None:
        length = gate_length_px * float(m_per_px)
        unit = "m^-1 s^-1"
        label = "Particle Number Flux (projected)" + (f" at Z = {z_m:g} m" if z_m else "")
    else:
        length = gate_length_px / 100.0
        unit = "per 100 px per s"
        label = "Particle Number Flux (projected, uncalibrated px)"
    scale = 1.0 / (length * duration_s)
    if net:
        return FluxValue(n * scale, nan, nan, unit, label + ", net")
    lo, hi = garwood_interval(n, ci)
    return FluxValue(n * scale, lo * scale, hi * scale, unit, label)
