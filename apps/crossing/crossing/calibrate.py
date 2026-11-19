"""Calibration (DESIGN.md section 7): measured thickness, predicted-vs-measured pairs, conformal recalibration.

Measured thickness
------------------
``measure_thickness``: time the roof flux plate stays above a threshold during a crossing, times the mean GNSS
ground speed over that time [m] (the DESIGN 7 definition). Assumptions: constant-ish speed, straight crossing
perpendicular to the front. A truncated pulse (record starts or ends above threshold), gaps > 0.5 s, invalid flux
samples inside the pulse, missing GNSS coverage or a mean speed < 0.5 m/s make it invalid.

Threshold (D7, 2026-11-17): ``max(threshold_kw_m2, frac_of_peak * pulse peak)`` with defaults 5.0 kW/m2 and 0.5,
i.e. the full width at HALF the pulse maximum, floored at 5 kW/m2 (``frac_of_peak = 0`` gives the old fixed
5 kW/m2). Why: a fixed 5 kW/m2 counts the radiant halo ahead of and behind the flames (a 2 m flame gives > 5 kW/m2
several metres away) plus the smoothing of the plate-flux estimate, so on the SIMULATED ``crossing`` sample
(3.0 m true flaming depth, 5 m/s) it measured about 13 m. Half maximum is defensible and conservative: if the flux
inside the flames is roughly uniform (a top hat of width = depth) and the estimate is smoothed by any symmetric
unimodal kernel (the centred derivative window is), the width at half maximum is never LESS than the flaming
depth (equal while the kernel is shorter than the crossing time, wider otherwise); the radiant halo can only widen
it further. A measured value that is too high widens the calibrated intervals and blocks ``trust_radar_ceiling``
(conservative), but it LOWERS dB/m, which lengthens the radar-loss depth (estimator e), raises the combined lo_m and
so LOWERS the dose (TDU ~ I^(4/3) D_lo^(-4/3) (D_hi + L) falls as depth grows): ANTI-conservative for dB/m (PHYS-4).
Mitigation as built: dB/m is the 90th percentile of loss_db / measured_m (an upper quantile, i.e. biased high),
not the median; the high bias of measured_m itself remains and is a KNOWN BIAS until corrected on real crossings.
An absolute threshold well above 5 kW/m2 would NOT be conservative either: a weak fire whose peak barely exceeds it
would give a sliver of a pulse and a thickness far below the depth.
Remaining bias: still HIGH (halo above half maximum, plate response); not verified on a real crossing.

Conformal recalibration
-----------------------
The requested ``research/kcf-margin`` does not exist in this repository. The rule used is the conformal risk
control rule of ``research/harness-2026-11/S-D9/sd9bench/crc.py`` (Angelopoulos et al., bound B = 1), with the
crossing as the exchangeable unit and miscoverage as the loss:
    score_i = |ln(measured_i / predicted_i)| / (z * sigma_log_i),   z = 1.6449
    s_hat   = smallest s in {score_i} with  n/(n+1) * mean_i 1{score_i > s} + 1/(n+1) <= alpha   (alpha = 0.10)
    scale   = max(1.0, s_hat)  (never shrink below the nominal interval)
The combined interval is then exp(mu +- z * sigma * scale) (depth.combine). Dividing the score by z makes
``scale`` the factor on the nominal 90 % interval, so "uncalibrated scale 1.5" and "never below 1.0" mean what
DESIGN 6.6 says. Infeasible when alpha < 1/(n+1), i.e. n < 9 at alpha 0.10: then the uncalibrated scale 1.5 is
kept and the status reads "uncalibrated (n = k, need >= 9)". The guarantee is marginal (on average over
exchangeable crossings), not per crossing.

dB/m per fuel: 90th percentile of loss_db / measured_m over pairs with loss_db > 0, needs n >= 3 (PHYS-4).
trust_radar_ceiling per fuel: n >= 9 pairs and every pair has a radar ceiling with measured <= ceiling.

Independent crossings (FS-5): every pair carries a dedup ``key`` (session, fuel, pulse end on the Pi clock rounded
to 1 s; or the prediction for a tape-measured manual mark) and its pulse window. ``recalibrate`` keeps one pair per
key (rows without a key: one per (session, measured, predicted)), and the scale, dB/m and ceiling trust take effect
only with pairs from >= 2 distinct sessions (MIN_SESSIONS). Replays of recorded real sessions write to a separate
store (pairs_replay.jsonl, pipeline.py) and never calibrate live decisions.

Estimator d (flicker_extent, experimental) is recorded on every pair (value, lo, hi, valid, reason) with
``flicker_extent_agrees`` = measured inside [lo, hi] (None when d is invalid or nothing was measured); per-fuel
counts n_d_valid / n_d_agree / n_d_disagree are reported in the calibration status (experimental; never used for
the scale, dB/m or trust decisions).

Pairs are stored append-only as JSONL. Default path ``apps/crossing/records/calibration/pairs.jsonl`` (git-ignored
runtime data, per laptop).
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from . import _repo
from .depth import UNCALIBRATED_SCALE, Z90

ALPHA = 0.10
THICKNESS_Q_KW_M2 = 5.0
THICKNESS_FRAC_OF_PEAK = 0.5   # half maximum (see module docstring); 0 = the fixed THICKNESS_Q_KW_M2 threshold
MIN_DB_PAIRS = 3
MIN_CRC_PAIRS = 9              # n >= 9 per fuel before the interval scale changes (alpha 0.10: 1/(n+1) <= alpha)
MIN_CEILING_PAIRS = 9          # n >= 9 per fuel, all within the radar ceiling, before trust_radar_ceiling
MIN_SESSIONS = 2               # pairs from >= 2 distinct sessions before any calibration takes effect (FS-5)
DB_PER_M_QUANTILE = 90.0       # upper quantile of loss_db / measured_m (PHYS-4: high dB/m is the safe side)
DEFAULT_PAIRS_PATH = _repo.APP / "records" / "calibration" / "pairs.jsonl"
CRC_SOURCE = "research/harness-2026-11/S-D9/sd9bench/crc.py (research/kcf-margin does not exist)"


def _isnum(v) -> bool:
    return isinstance(v, (int, float, np.floating, np.integer)) and not isinstance(v, bool) and math.isfinite(v)


def _get(obj, *names, default=None):
    for n in names:
        if isinstance(obj, dict):
            if n in obj:
                return obj[n]
        elif hasattr(obj, n):
            return getattr(obj, n)
    return default


# ------------------------------------------------------------------------------------------- measured thickness
@dataclass
class ThicknessResult:
    valid: bool
    thickness_m: Optional[float] = None
    duration_s: Optional[float] = None
    mean_speed_m_s: Optional[float] = None
    t_start: Optional[float] = None
    t_end: Optional[float] = None
    reason: str = ""
    threshold_kw_m2: Optional[float] = None       # threshold actually used
    peak_kw_m2: Optional[float] = None


def _flux_rows(flux_samples) -> List[Tuple[float, float, bool]]:
    rows = []
    for s in flux_samples:
        if isinstance(s, (tuple, list)):
            t, q = s[0], s[1]
            ok = True
        else:
            t = _get(s, "t", "t_s")
            q = _get(s, "q_kw_m2", "q")
            ok = bool(_get(s, "valid", default=True))
        good = ok and _isnum(t) and _isnum(q)
        rows.append((float(t) if _isnum(t) else float("nan"), float(q) if _isnum(q) else float("nan"), good))
    rows = [r for r in rows if math.isfinite(r[0])]
    rows.sort(key=lambda r: r[0])
    return rows


def _gnss_rows(gnss_samples) -> np.ndarray:
    out = []
    for s in gnss_samples:
        if isinstance(s, (tuple, list)):
            t, v = s[0], s[1]
        else:
            t = _get(s, "t", "t_s")
            v = _get(s, "speed_m_s", "speed")
            fix = _get(s, "fix", default=1)
            if not fix:
                continue
        if _isnum(t) and _isnum(v) and 0 <= v < 100:
            out.append((float(t), float(v)))
    out.sort()
    return np.array(out, dtype=float).reshape(-1, 2)


def measure_thickness(flux_samples, gnss_samples, threshold_kw_m2: float = THICKNESS_Q_KW_M2,
                      max_gap_s: float = 0.5, max_gnss_gap_s: float = 2.0,
                      min_speed_m_s: float = 0.5,
                      frac_of_peak: float = THICKNESS_FRAC_OF_PEAK) -> ThicknessResult:
    """Measured thickness [m] = (time plate flux > threshold) x (mean GNSS speed over that time).

    Threshold = max(threshold_kw_m2, frac_of_peak * peak of the pulse) (module docstring; frac_of_peak = 0 gives
    the fixed threshold). The peak is the largest valid flux of the longest pulse above threshold_kw_m2.
    flux_samples: (t_s, q_kw_m2) tuples or objects/dicts with t, q_kw_m2 and optional valid (flux.FluxSample).
    gnss_samples: (t_s, speed_m_s) tuples or dicts/objects with t, speed_m_s, fix. Same clock as the flux.
    The longest pulse above threshold is used; its start and end are interpolated linearly between samples.
    """
    rows = _flux_rows(flux_samples)
    if len(rows) < 3:
        return ThicknessResult(False, reason="too few flux samples")
    t = np.array([r[0] for r in rows])
    q = np.array([r[1] for r in rows])
    good = np.array([r[2] for r in rows])
    if not (_isnum(frac_of_peak) and 0.0 <= frac_of_peak < 1.0):
        return ThicknessResult(False, reason="frac_of_peak must be in [0, 1)")
    above = good & (q > threshold_kw_m2)
    if not above.any():
        return ThicknessResult(False, reason="flux never above %.1f kW/m2" % threshold_kw_m2)
    peak = None
    if frac_of_peak > 0:
        a0, b0 = _longest_run(above, t)
        peak = float(np.max(q[a0:b0 + 1]))
        thr = max(float(threshold_kw_m2), frac_of_peak * peak)
        if thr > threshold_kw_m2:
            threshold_kw_m2 = thr
            above = good & (q > threshold_kw_m2)
    i0, i1 = _longest_run(above, t)
    if i0 == 0 or i1 == len(t) - 1:
        return ThicknessResult(False, reason="pulse truncated by the record")
    if not (good[i0 - 1] and good[i1 + 1]):
        return ThicknessResult(False, reason="invalid flux sample at the pulse edge")
    if np.any(np.diff(t[i0 - 1:i1 + 2]) > max_gap_s):
        return ThicknessResult(False, reason="flux gap > %.1f s in the pulse" % max_gap_s)

    def cross(ia, ib):
        qa, qb = q[ia], q[ib]
        if qb == qa:
            return 0.5 * (t[ia] + t[ib])
        return t[ia] + (threshold_kw_m2 - qa) / (qb - qa) * (t[ib] - t[ia])

    t0 = float(cross(i0 - 1, i0))
    t1 = float(cross(i1, i1 + 1))
    dur = t1 - t0
    if not dur > 0:
        return ThicknessResult(False, reason="zero-length pulse")
    g = _gnss_rows(gnss_samples)
    if g.shape[0] < 2:
        return ThicknessResult(False, duration_s=dur, t_start=t0, t_end=t1, reason="no GNSS speed")
    if g[0, 0] > t0 + 0.5 or g[-1, 0] < t1 - 0.5:
        return ThicknessResult(False, duration_s=dur, t_start=t0, t_end=t1, reason="GNSS does not cover the pulse")
    inside = g[(g[:, 0] >= t0 - max_gnss_gap_s) & (g[:, 0] <= t1 + max_gnss_gap_s)]
    if inside.shape[0] < 2 or np.any(np.diff(inside[:, 0]) > max_gnss_gap_s):
        return ThicknessResult(False, duration_s=dur, t_start=t0, t_end=t1, reason="GNSS gap in the pulse")
    grid = np.linspace(t0, t1, 101)
    v = np.interp(grid, g[:, 0], g[:, 1])
    vmean = float(np.mean(0.5 * (v[1:] + v[:-1])))
    if vmean < min_speed_m_s:
        return ThicknessResult(False, duration_s=dur, mean_speed_m_s=vmean, t_start=t0, t_end=t1,
                               reason="mean speed %.2f m/s < %.2f" % (vmean, min_speed_m_s),
                               threshold_kw_m2=threshold_kw_m2, peak_kw_m2=peak)
    return ThicknessResult(True, thickness_m=dur * vmean, duration_s=dur, mean_speed_m_s=vmean, t_start=t0,
                           t_end=t1, reason="ok", threshold_kw_m2=threshold_kw_m2, peak_kw_m2=peak)


def _longest_run(above: np.ndarray, t: np.ndarray) -> Tuple[int, int]:
    """(first, last) index of the longest (in time) run of consecutive True values; ``above.any()`` required."""
    best, cur_start, runs = None, None, []
    for i, a in enumerate(above):
        if a and cur_start is None:
            cur_start = i
        if (not a or i == len(above) - 1) and cur_start is not None:
            end = i if a else i - 1
            runs.append((cur_start, end))
            cur_start = None
    for (a, b) in runs:
        dur = t[b] - t[a]
        if best is None or dur > best[2]:
            best = (a, b, dur)
    return best[0], best[1]


# ------------------------------------------------------------------------------------------------------ pairs
@dataclass
class Pair:
    """One predicted-vs-measured crossing. Depths in m, loss in dB, time as UTC ISO string."""
    fuel: str
    predicted_m: float
    lo_m: float
    hi_m: float
    sigma_log: float
    measured_m: float
    estimates: Dict[str, Optional[float]] = field(default_factory=dict)   # per-estimator values (m)
    loss_db: Optional[float] = None
    time: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    session: Optional[str] = None
    sim: bool = False
    # FS-5 (added fields; rows written before them load with None)
    key: Optional[str] = None                     # dedup key: one pair per physical crossing
    t_start_pi: Optional[float] = None            # measured pulse window (Pi clock), when measured from the flux
    t_end_pi: Optional[float] = None
    prediction_rx: Optional[float] = None         # laptop receipt time of the prediction used
    source: Optional[str] = None                  # "auto" | "manual"
    # R6: estimator d (experimental) recorded on every pair, valid or not
    est_flicker_extent_lo_m: Optional[float] = None
    est_flicker_extent_hi_m: Optional[float] = None
    est_flicker_extent_valid: Optional[bool] = None
    est_flicker_extent_reason: Optional[str] = None
    flicker_extent_agrees: Optional[bool] = None

    @property
    def ceiling_m(self) -> Optional[float]:
        v = self.estimates.get("radar_ceiling") if self.estimates else None
        return float(v) if _isnum(v) else None

    def usable(self) -> bool:
        return (bool(self.fuel) and _isnum(self.predicted_m) and self.predicted_m > 0 and _isnum(self.measured_m)
                and self.measured_m > 0 and _isnum(self.sigma_log) and self.sigma_log > 0)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Pair":
        keys = cls.__dataclass_fields__.keys()
        return cls(**{k: d[k] for k in keys if k in d})


def pair_key(p: Pair) -> str:
    """Dedup key of a pair: its own ``key``, else (rows written before keys) session + measured + predicted."""
    if p.key:
        return str(p.key)
    return "legacy|%s|%s|%r|%r" % (p.session, p.fuel, p.measured_m, p.predicted_m)


def make_key(session: Optional[str], fuel: str, kind: str, t: Optional[float]) -> str:
    """``session|fuel|kind|t`` with t rounded to 1 s ("?" when unknown)."""
    tt = "%d" % int(round(t)) if _isnum(t) else "?"
    return "%s|%s|%s|%s" % (session, fuel, kind, tt)


def dedup(pairs: Iterable[Pair]) -> Tuple[List[Pair], int]:
    """(pairs with one per ``pair_key``, first kept; number dropped)."""
    seen, out, dropped = set(), [], 0
    for p in pairs:
        k = pair_key(p)
        if k in seen:
            dropped += 1
            continue
        seen.add(k)
        out.append(p)
    return out, dropped


def is_duplicate(new: Pair, existing: Iterable[Pair]) -> Optional[str]:
    """Why ``new`` repeats a stored crossing (same key; same session + fuel with an overlapping pulse window; same
    session + prediction), or None."""
    for p in existing:
        if pair_key(p) == pair_key(new):
            return "same crossing key %s" % pair_key(new)
        if p.session != new.session or p.fuel != new.fuel:
            continue
        if all(_isnum(x) for x in (p.t_start_pi, p.t_end_pi, new.t_start_pi, new.t_end_pi)) \
                and p.t_start_pi <= new.t_end_pi and new.t_start_pi <= p.t_end_pi:
            return "same flux pulse as a stored pair (session %s)" % new.session
        if _isnum(p.prediction_rx) and _isnum(new.prediction_rx) and abs(p.prediction_rx - new.prediction_rx) < 1e-6:
            return "same depth prediction as a stored pair (session %s)" % new.session
    return None


class PairStore:
    """Append-only JSONL store of pairs (one JSON object per line). Malformed lines are skipped and counted."""

    def __init__(self, path=None):
        self.path = Path(path) if path is not None else DEFAULT_PAIRS_PATH
        self.skipped = 0

    def append(self, pair: Pair) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(pair.to_dict(), sort_keys=True, allow_nan=False)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def load(self) -> List[Pair]:
        self.skipped = 0
        out: List[Pair] = []
        if not self.path.exists():
            return out
        with open(self.path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    p = Pair.from_dict(json.loads(line))
                except (ValueError, TypeError, KeyError):
                    self.skipped += 1
                    continue
                out.append(p)
        return out


# ------------------------------------------------------------------------------------------------- recalibrate
def crc_scale(scores: Sequence[float], alpha: float = ALPHA) -> dict:
    """Conformal risk control (S-D9 crc.py rule) for the interval scale.

    Returns dict(feasible, s_hat, n, alpha, required_risk). s_hat is the smallest s in {scores} with
    n/(n+1) * mean(1{score > s}) + 1/(n+1) <= alpha; infeasible when alpha < 1/(n+1).
    """
    sc = np.sort(np.asarray([s for s in scores if _isnum(s) and s >= 0], dtype=float))
    n = int(sc.size)
    if not 0 < alpha < 1:
        raise ValueError("0 < alpha < 1 required")
    req = (alpha * (n + 1) - 1) / n if n else float("-inf")
    if n == 0:
        return dict(feasible=False, s_hat=None, n=0, alpha=alpha, required_risk=req)
    for s in sc:                                       # ascending -> first ok is the smallest
        risk = float(np.mean(sc > s))
        if n / (n + 1) * risk + 1.0 / (n + 1) <= alpha + 1e-12:
            return dict(feasible=True, s_hat=float(s), n=n, alpha=alpha, required_risk=req)
    return dict(feasible=False, s_hat=None, n=n, alpha=alpha, required_risk=req)


@dataclass
class FuelCalibration:
    fuel: str
    n_pairs: int = 0
    n_skipped: int = 0
    alpha: float = ALPHA
    calibrated: bool = False
    scale: float = UNCALIBRATED_SCALE
    s_hat: Optional[float] = None
    status: str = ""
    db_per_m: Optional[float] = None
    n_db: int = 0
    trust_radar_ceiling: bool = False
    ceiling_note: str = ""
    method: str = CRC_SOURCE
    n_sessions: int = 0
    n_duplicates: int = 0
    n_d_valid: int = 0                       # R6: estimator d (experimental), information only
    n_d_agree: int = 0
    n_d_disagree: int = 0
    d_note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def score(pair: Pair, z: float = Z90) -> float:
    """|ln(measured / predicted)| / (z * sigma_log)."""
    return abs(math.log(pair.measured_m / pair.predicted_m)) / (z * pair.sigma_log)


def db_per_m(pairs: Iterable[Pair], quantile: float = DB_PER_M_QUANTILE) -> Tuple[Optional[float], int]:
    """Upper quantile (default 90th percentile) of loss_db / measured_m over pairs with loss_db > 0; None unless
    n >= 3. An upper quantile, not the median, because a LOW dB/m lengthens the radar-loss depth and lowers the dose
    (PHYS-4); the high bias of measured_m (half-maximum width) still pushes it low: known bias."""
    r = [p.loss_db / p.measured_m for p in pairs
         if _isnum(p.loss_db) and p.loss_db > 0 and _isnum(p.measured_m) and p.measured_m > 0]
    if len(r) < MIN_DB_PAIRS:
        return None, len(r)
    return float(np.percentile(r, quantile)), len(r)


def recalibrate(pairs: Iterable[Pair], fuel: str, alpha: float = ALPHA, z: float = Z90) -> FuelCalibration:
    """Calibration for one fuel from all stored pairs (other fuels ignored, unusable pairs skipped, repeated
    crossings counted once; nothing takes effect with pairs from fewer than MIN_SESSIONS sessions)."""
    mine_all = [p for p in pairs if p.fuel == fuel]
    mine, n_dup = dedup(mine_all)
    usable = [p for p in mine if p.usable()]
    cal = FuelCalibration(fuel=fuel, n_pairs=len(usable), n_skipped=len(mine) - len(usable), alpha=alpha,
                          n_duplicates=n_dup)
    n = len(usable)
    sessions = {p.session if p.session else "?" for p in usable}
    cal.n_sessions = len(sessions)
    indep = cal.n_sessions >= MIN_SESSIONS
    sess_note = "" if indep else "; pairs from %d session(s), need >= %d" % (cal.n_sessions, MIN_SESSIONS)
    res = crc_scale([score(p, z) for p in usable], alpha)
    need = max(MIN_CRC_PAIRS, int(math.ceil(1.0 / alpha - 1.0 - 1e-9)))
    if res["feasible"] and n >= need and indep:
        cal.calibrated = True
        cal.s_hat = res["s_hat"]
        cal.scale = max(1.0, float(res["s_hat"]))
        cal.status = "calibrated (n = %d, alpha = %.2f, scale %.2f)" % (n, alpha, cal.scale)
    else:
        cal.status = "uncalibrated (n = %d, need >= %d%s)" % (n, need, sess_note)
    if n_dup:
        cal.status += " (%d repeated pair(s) ignored)" % n_dup
    dbm, cal.n_db = db_per_m(usable)
    cal.db_per_m = dbm if indep else None
    with_ceiling = [p for p in usable if p.ceiling_m is not None]
    if n >= MIN_CEILING_PAIRS and len(with_ceiling) == n and all(p.measured_m <= p.ceiling_m for p in usable) \
            and indep:
        cal.trust_radar_ceiling = True
        cal.ceiling_note = "every pair (n = %d) had measured <= radar ceiling" % n
    else:
        bad = sum(1 for p in with_ceiling if p.measured_m > p.ceiling_m)
        cal.ceiling_note = ("not trusted: n = %d, %d with ceiling, %d exceeded it (needs n >= 9, all within%s)"
                            % (n, len(with_ceiling), bad, sess_note))
    dv = [p for p in usable if p.est_flicker_extent_valid is True]
    cal.n_d_valid = len(dv)
    cal.n_d_agree = sum(1 for p in dv if p.flicker_extent_agrees is True)
    cal.n_d_disagree = sum(1 for p in dv if p.flicker_extent_agrees is False)
    cal.d_note = ("estimator d (experimental, information only): valid on %d pair(s), measured inside its "
                  "interval on %d, outside on %d" % (cal.n_d_valid, cal.n_d_agree, cal.n_d_disagree))
    return cal


def calibrate_all(pairs: Iterable[Pair], alpha: float = ALPHA) -> Dict[str, FuelCalibration]:
    ps = list(pairs)
    return {f: recalibrate(ps, f, alpha) for f in sorted({p.fuel for p in ps if p.fuel})}


def make_pair(fuel: str, depth_result, measured_m: float, loss_db: Optional[float] = None, **meta) -> Pair:
    """Build a Pair from a depth.DepthResult (uses its depth, interval, sigma_log and per-estimator values).

    Estimator d (flicker_extent, experimental) is recorded whether valid or not, with ``flicker_extent_agrees`` =
    (lo <= measured <= hi) when it is valid (R6). ``meta`` may carry the FS-5 fields (key, t_start_pi, ...)."""
    est = {}
    d = None
    for e in (getattr(depth_result, "estimates", None) or []):
        if isinstance(e, dict) and e.get("valid"):
            est[e["name"]] = e.get("value_m")
        if isinstance(e, dict) and e.get("name") == "flicker_extent":
            d = e
    m = float(measured_m)
    if d is not None:
        lo, hi, ok = d.get("lo_m"), d.get("hi_m"), d.get("valid") is True
        meta.setdefault("est_flicker_extent_lo_m", lo if _isnum(lo) else None)
        meta.setdefault("est_flicker_extent_hi_m", hi if _isnum(hi) else None)
        meta.setdefault("est_flicker_extent_valid", bool(ok))
        meta.setdefault("est_flicker_extent_reason", str(d.get("reason") or "")[:200])
        meta.setdefault("flicker_extent_agrees", (lo <= m <= hi) if (ok and _isnum(lo) and _isnum(hi)
                                                                     and _isnum(m)) else None)
    return Pair(fuel=fuel, predicted_m=depth_result.depth_m, lo_m=depth_result.lo_m, hi_m=depth_result.hi_m,
                sigma_log=depth_result.sigma_log, measured_m=m, estimates=est, loss_db=loss_db,
                **meta)
