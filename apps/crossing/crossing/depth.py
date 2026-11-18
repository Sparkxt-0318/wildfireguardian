"""Step 5: depth of the flaming zone D [m] (along the road) from independent estimators, and Byram intensity.

Estimators (DESIGN.md 6.6). Every estimate carries a log-normal 1-sigma ``sigma_log`` and a nominal 90 % interval.
  a  spread_burn     D = R * t_r. R [m/s] = least-squares rate at which the near edge advances towards the vehicle
                     in a world frame (positions already corrected for vehicle motion with GNSS + course), t_r from
                     the fuel. Assumes a steady front over the fit window (>= 5 s) and that the flaming zone depth
                     equals R * t_r (Anderson residence time, point scale).
  b  byram           flame length L >= observed flame height (vertical flame assumed; wind tilt makes L longer than
                     the height, so this UNDER-estimates L and I when tilted), I = (L / 0.0775)^(1/0.46) [kW/m]
                     (Byram), D = I * t_r / (H * w). sigma_log = sqrt(0.6^2 + residence_rel_sigma^2 + 0.3^2):
                     flame-length model part 0.6, the fuel's residence-time error, heat content x load 0.3
                     (all placeholders).
  c  radar_ceiling   far solid echo minus near edge [m]: an UPPER bound only (flame may end before the echo).
                     NEVER enters the mean (it would pull depth_m and lo_m up towards the echo, and a higher lo_m
                     lowers the in-flame flux chi*I_hi/(pi*D_lo)). When calibration sets trust_radar_ceiling for the
                     fuel it only caps the upper end: hi_m = min(hi_m, ceiling) when ceiling >= depth_m; a ceiling
                     below depth_m is flagged as a conflict and not used. Untrusted: reported and ignored.
  d  flicker_extent  range extent of radar bins beyond the near edge with flicker z >= k. EXPERIMENTAL, off by
                     default, always reported.
  e  radar_loss_depth  loss_db / (dB per m), only when calibration holds a dB/m for the fuel (n >= 3 pairs).

``combine``: generalised least squares (GLS) mean of the log values of the valid, enabled estimators. spread_burn
(D = R t_r) and byram (D = I t_r / (H w)) share the fuel's residence-time error t_r; each estimate reports that shared
part as ``details["shared_log_sigma"]`` (residence_rel_sigma for a and b, 0 for c, d, e) and the covariance is
C_ii = sigma_i^2, C_ij = s_i * s_j (same fuel: correlation 1). mu = 1'C^-1 lv / 1'C^-1 1, var = 1 / 1'C^-1 1, so the
shared t_r error is not averaged away (var >= residence_rel_sigma^2 when every estimator used depends on t_r). If
the solve fails, the single estimator with the widest interval is used. Interval exp(mu +- z * sigma * scale),
z = 1.6449 (90 %), scale from conformal calibration (section 7) or 1.5 uncalibrated (flagged). No valid estimator
-> DepthResult(valid=False) -> the decision is CLOSED.

Decision upper end (``hi_decision_m``, DEPTH-HI rule, 2026-11-17). depth_m / lo_m / hi_m stay the combined value and
interval FOR DISPLAY (and for calibration pairs). The dose uses ``hi_decision_m`` (decision.depth_hi_for_decision):
  hi_decision_m = max(upper end of the combination of the non-experimental estimators,
                      hi_m of every valid estimator of kind "estimate": spread_burn, byram, radar_loss_depth)
The GLS mean follows the narrowest estimator, so its upper end can fall below the truth when that estimator is
biased low (SIMULATED flame_front sample, true depth 3.0 m: combined [0.27, 1.4] m from spread_burn ~0.6 m while
byram gave ~1.2 [0.33, 4.7] m). The experimental flicker_extent (d) never raises or lowers hi_decision_m (it is
left out of the decision combination even when enabled for the mean); with only experimental estimators usable the
result is INVALID (they never decide). The radar ceiling is not an estimate: it never raises hi_decision_m and
lowers it only when calibration sets trust_radar_ceiling (cap min(hi, ceiling) when the ceiling is >= the central
value, as for hi_m). The max rule stays unless ``narrow_decision_hi`` is set (config ``depth.narrow_decision_hi``,
default false) AND the fuel is calibrated with n_pairs >= ``narrow_min_pairs``; then hi_decision_m = the combined
upper end (flagged). ESTIMATORS_DISAGREE is flagged when the largest / smallest central value of those estimators
exceeds ``disagree_factor`` (default 3.0, placeholder); it does not close by itself (the max upper end is already
used).

``intensity``: Byram inverse from the flame height interval and/or I = R * H * w from estimator a.
hi = max of available upper ends. No source -> invalid -> CLOSED. Fail closed: a flame-height source whose central
value or upper end is missing, not finite, above 100 m or (upper end) below the central value makes the result
INVALID ("flame height upper bound unbounded"), whatever the spread-rate source says (geometry returns h_hi = inf
when a perturbed ray misses the ground, e.g. an occluded flame base); it is never replaced by the central height.

None of this has been checked against a real flame front yet: the formulas are literature relations with
placeholder uncertainties until calibration pairs exist.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

import numpy as np

from .fuels import Fuel

Z90 = 1.6448536269514722                 # two-sided 90 % normal quantile
UNCALIBRATED_SCALE = 1.5
BYRAM_A = 0.0775                         # L = 0.0775 * I^0.46 (experimental/flame-front-radiation intensity.py)
BYRAM_B = 0.46
BYRAM_SIGMA_LOG = 0.6                    # placeholder: flame-length (Byram) model part of byram's sigma_log
BYRAM_HW_SIGMA_LOG = 0.3                 # placeholder: heat content x consumed load (H * w) part of byram's sigma
FLICKER_SIGMA_LOG = 0.8                  # placeholder (experimental estimator)
LOSS_DEPTH_SIGMA_LOG = 0.5               # placeholder until calibration provides a spread
DEFAULT_ENABLED = ("spread_burn", "byram", "radar_loss_depth")
EXPERIMENTAL = ("flicker_extent",)       # never decide, whatever their ``kind`` says
DISAGREE_FACTOR = 3.0                    # placeholder: ESTIMATORS_DISAGREE when max/min central value exceeds this
NARROW_MIN_PAIRS = 30                    # placeholder: calibrated pairs per fuel before narrow_decision_hi may apply
DISAGREE_FLAG = "ESTIMATORS_DISAGREE"


def _isnum(v) -> bool:
    return isinstance(v, (int, float, np.floating, np.integer)) and not isinstance(v, bool) and math.isfinite(v)


@dataclass
class Estimate:
    """One depth estimate. value/lo/hi in m; sigma_log = 1-sigma of ln(value)."""
    name: str
    value_m: Optional[float]
    lo_m: Optional[float]
    hi_m: Optional[float]
    sigma_log: Optional[float]
    valid: bool
    reason: str = ""
    kind: str = "estimate"               # "estimate" | "ceiling" | "experimental"
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"name": self.name, "value_m": self.value_m, "lo_m": self.lo_m, "hi_m": self.hi_m,
                "sigma_log": self.sigma_log, "valid": self.valid, "reason": self.reason, "kind": self.kind,
                "details": dict(self.details)}


def _invalid(name: str, reason: str, kind: str = "estimate", **details) -> Estimate:
    return Estimate(name, None, None, None, None, False, reason, kind, dict(details))


def _lognormal(name: str, value: float, sigma_log: float, kind: str = "estimate", reason: str = "ok",
               **details) -> Estimate:
    return Estimate(name, float(value), float(value * math.exp(-Z90 * sigma_log)),
                    float(value * math.exp(Z90 * sigma_log)), float(sigma_log), True, reason, kind, dict(details))


# ----------------------------------------------------------------------------------------------- estimator a
def spread_burn(near_edge_world_track, fuel: Fuel, toward_en: Optional[Sequence[float]] = None,
                min_span_s: float = 5.0, min_points: int = 5, min_rate_m_s: float = 0.02,
                max_rel_se: float = 0.5) -> Estimate:
    """Estimator a: D = R * t_r.

    near_edge_world_track: rows (t_s, x_m) with x the near-edge position along the axis pointing TOWARDS the
    vehicle, or rows (t_s, east_m, north_m) in a local ENU frame together with ``toward_en`` (unit-ish vector
    from the front towards the vehicle). Positions must already be world positions (vehicle motion removed).
    Invalid if span < min_span_s, too few points, R <= min_rate_m_s, or relative SE of R > max_rel_se (poor fit).
    sigma_log = sqrt((SE_R / R)^2 + residence_rel_sigma^2) (first-order log error of a product).
    """
    name = "spread_burn"
    try:
        arr = np.asarray(near_edge_world_track, dtype=float)
    except (TypeError, ValueError):
        return _invalid(name, "track not numeric")
    if arr.ndim != 2 or arr.shape[0] == 0 or arr.shape[1] not in (2, 3):
        return _invalid(name, "track must be rows of (t, x) or (t, east, north)")
    if not np.all(np.isfinite(arr)):
        return _invalid(name, "track has non-finite values")
    t = arr[:, 0]
    if arr.shape[1] == 3:
        if toward_en is None:
            return _invalid(name, "toward_en required for (t, east, north) track")
        u = np.asarray(toward_en, dtype=float)
        nrm = float(np.hypot(u[0], u[1])) if u.shape == (2,) and np.all(np.isfinite(u)) else 0.0
        if nrm <= 0:
            return _invalid(name, "toward_en invalid")
        x = (arr[:, 1] * u[0] + arr[:, 2] * u[1]) / nrm
    else:
        x = arr[:, 1]
    n = len(t)
    span = float(t.max() - t.min()) if n else 0.0
    if n < min_points:
        return _invalid(name, "too few points (%d < %d)" % (n, min_points), n=n)
    if span < min_span_s:
        return _invalid(name, "track span %.1f s < %.1f s" % (span, min_span_s), span_s=span)
    tm = t - t.mean()
    sxx = float(np.dot(tm, tm))
    if sxx <= 0:
        return _invalid(name, "degenerate time axis")
    rate = float(np.dot(tm, x - x.mean()) / sxx)
    resid = x - (x.mean() + rate * tm)
    dof = max(n - 2, 1)
    se = math.sqrt(float(np.dot(resid, resid)) / dof / sxx)
    if rate <= min_rate_m_s:
        return _invalid(name, "spread rate %.3f m/s <= %.3f" % (rate, min_rate_m_s), spread_m_s=rate, se=se)
    rel_se = se / rate
    if rel_se > max_rel_se:
        return _invalid(name, "poor fit: SE/R = %.2f > %.2f" % (rel_se, max_rel_se), spread_m_s=rate, se=se)
    sigma = math.sqrt(rel_se ** 2 + fuel.residence_rel_sigma ** 2)
    return _lognormal(name, rate * fuel.residence_s, max(sigma, 1e-3), spread_m_s=rate, spread_se_m_s=se,
                      residence_s=fuel.residence_s, n=n, span_s=span,
                      shared_log_sigma=float(fuel.residence_rel_sigma))


# ----------------------------------------------------------------------------------------------- estimator b
def byram_intensity_from_length(length_m: float) -> float:
    """Byram inverse: I = (L / 0.0775)^(1 / 0.46) [kW/m], L in m."""
    return (length_m / BYRAM_A) ** (1.0 / BYRAM_B)


def byram(flame_height_m: Optional[float], fuel: Fuel, sigma_log: float = BYRAM_SIGMA_LOG,
          hw_sigma_log: float = BYRAM_HW_SIGMA_LOG) -> Estimate:
    """Estimator b: D = I * t_r / (H * w) with I from flame length L = flame height (vertical flame assumed).

    sigma_log of the estimate = sqrt(sigma_log^2 + fuel.residence_rel_sigma^2 + hw_sigma_log^2): ``sigma_log`` is
    the flame-length (Byram) part only, the t_r part is the fuel's own and is reported as ``shared_log_sigma``
    (shared with spread_burn, see ``combine``). All three are placeholders."""
    name = "byram"
    if not _isnum(flame_height_m) or flame_height_m <= 0:
        return _invalid(name, "no valid flame height")
    if flame_height_m > 100:
        return _invalid(name, "flame height %.1f m out of range" % flame_height_m)
    i_kw_m = byram_intensity_from_length(float(flame_height_m))
    depth = i_kw_m * fuel.residence_s / fuel.energy_kj_m2
    tr = float(fuel.residence_rel_sigma)
    total = math.sqrt(float(sigma_log) ** 2 + tr ** 2 + float(hw_sigma_log) ** 2)
    return _lognormal(name, depth, total, intensity_kw_m=i_kw_m, flame_length_m=float(flame_height_m),
                      assumption="vertical flame: L = height (tilt makes L longer)", shared_log_sigma=tr,
                      sigma_parts={"byram_model": float(sigma_log), "residence_time": tr,
                                   "heat_content_x_load": float(hw_sigma_log)})


# ----------------------------------------------------------------------------------------------- estimator c
def radar_ceiling(near_edge_m: Optional[float], far_echo_m: Optional[float],
                  range_res_m: float = 0.1) -> Estimate:
    """Estimator c: far solid echo - near edge [m], an upper bound on depth. sigma_log from range resolution."""
    name = "radar_ceiling"
    if not (_isnum(near_edge_m) and _isnum(far_echo_m)):
        return _invalid(name, "near edge or far echo missing", kind="ceiling")
    if near_edge_m < 0 or far_echo_m <= near_edge_m:
        return _invalid(name, "far echo not beyond near edge", kind="ceiling")
    v = float(far_echo_m - near_edge_m)
    sig = max(0.05, 2.0 * float(range_res_m) / v)
    return _lognormal(name, v, sig, kind="ceiling", reason="ceiling (upper bound)", far_echo_m=float(far_echo_m),
                      near_edge_m=float(near_edge_m))


# ----------------------------------------------------------------------------------------------- estimator d
def flicker_extent(per_bin_flicker_z, near_edge_m: Optional[float], range_res_m: float = 0.1, k: float = 4.0,
                   max_gap_bins: int = 1, sigma_log: float = FLICKER_SIGMA_LOG) -> Estimate:
    """Estimator d (experimental): range extent [m] of bins beyond the near edge with flicker z >= k.

    Bin i is at range i * range_res_m. Starting at the first flagged bin beyond the near edge, the run continues
    while gaps of unflagged bins are <= max_gap_bins; extent = (last flagged range - near edge) + one bin.
    """
    name = "flicker_extent"
    if not _isnum(near_edge_m) or near_edge_m < 0 or not _isnum(range_res_m) or range_res_m <= 0:
        return _invalid(name, "no near edge", kind="experimental")
    try:
        z = np.asarray(per_bin_flicker_z, dtype=float)
    except (TypeError, ValueError):
        return _invalid(name, "flicker z not numeric", kind="experimental")
    if z.ndim != 1 or z.size == 0:
        return _invalid(name, "no flicker bins", kind="experimental")
    rng = np.arange(z.size) * range_res_m
    flagged = np.where((rng >= near_edge_m) & np.isfinite(z) & (z >= k))[0]
    if flagged.size == 0:
        return _invalid(name, "no flicker beyond the near edge", kind="experimental")
    last = flagged[0]
    for b in flagged[1:]:
        if b - last - 1 > max_gap_bins:
            break
        last = b
    v = float(rng[last] - near_edge_m + range_res_m)
    return _lognormal(name, v, sigma_log, kind="experimental", reason="experimental", first_bin=int(flagged[0]),
                      last_bin=int(last))


# ----------------------------------------------------------------------------------------------- estimator e
def radar_loss_depth(loss_db: Optional[float], db_per_m: Optional[float],
                     sigma_log: float = LOSS_DEPTH_SIGMA_LOG) -> Estimate:
    """Estimator e: D = loss_db / (dB per m); only with a calibrated dB/m for the fuel."""
    name = "radar_loss_depth"
    if not _isnum(db_per_m) or db_per_m <= 0:
        return _invalid(name, "no calibrated dB/m for this fuel")
    if not _isnum(loss_db) or loss_db <= 0:
        return _invalid(name, "no radar loss")
    return _lognormal(name, float(loss_db) / float(db_per_m), sigma_log, db_per_m=float(db_per_m),
                      loss_db=float(loss_db))


# ----------------------------------------------------------------------------------------------- combination
@dataclass
class DepthResult:
    valid: bool
    depth_m: Optional[float] = None
    lo_m: Optional[float] = None
    hi_m: Optional[float] = None
    level: float = 0.90
    used: List[str] = field(default_factory=list)
    calibrated: bool = False
    n_pairs: int = 0
    method: str = ""
    scale: float = UNCALIBRATED_SCALE
    sigma_log: Optional[float] = None
    flags: List[str] = field(default_factory=list)
    ceiling_m: Optional[float] = None
    reason: str = ""
    estimates: List[dict] = field(default_factory=list)
    # DEPTH-HI rule (module docstring): the upper end the dose uses; None when invalid. hi_m stays the display one.
    hi_decision_m: Optional[float] = None
    hi_decision_from: str = ""           # estimator name, "combined", or "radar_ceiling (trusted cap)"
    hi_decision_rule: str = ""
    disagree_ratio: Optional[float] = None   # max / min central value of the decision estimators (>= 2 valid)

    def to_dict(self) -> dict:
        return {k: (list(v) if isinstance(v, list) else v) for k, v in self.__dict__.items()}


def is_experimental(e: Estimate) -> bool:
    return e.kind == "experimental" or e.name in EXPERIMENTAL


def combine(estimates: Iterable[Estimate], calib: Any = None, z: float = Z90,
            enabled: Optional[Iterable[str]] = None, disagree_factor: float = DISAGREE_FACTOR,
            narrow_decision_hi: bool = False, narrow_min_pairs: int = NARROW_MIN_PAIRS) -> DepthResult:
    """Combine estimates per DESIGN 6.6.

    calib: object with attributes ``scale`` (float), ``calibrated`` (bool), ``n_pairs`` (int),
    ``trust_radar_ceiling`` (bool) and optionally ``status`` (str) -- e.g. calibrate.FuelCalibration -- or None.
    enabled: estimator names allowed to enter the mean (default spread_burn, byram, radar_loss_depth;
    flicker_extent only if listed here explicitly). radar_ceiling NEVER enters the mean, even if listed: it is an
    upper bound only. When ``trust_radar_ceiling`` is set it caps hi_m (min(hi_m, ceiling), only when ceiling >=
    depth_m); it never raises lo_m and never moves depth_m. Estimators sharing the fuel's residence-time error
    (``details["shared_log_sigma"]``) are combined by GLS (module docstring).
    hi_decision_m (the upper end the dose uses) follows the DEPTH-HI rule of the module docstring: at least the
    largest hi_m of the valid non-experimental estimates, unless ``narrow_decision_hi`` and the fuel is calibrated
    with n_pairs >= ``narrow_min_pairs``. ``disagree_factor``: ESTIMATORS_DISAGREE threshold (max/min central).
    """
    ests = list(estimates)
    trust = bool(getattr(calib, "trust_radar_ceiling", False)) if calib is not None else False
    calibrated = bool(getattr(calib, "calibrated", False)) if calib is not None else False
    n_pairs = int(getattr(calib, "n_pairs", 0) or 0) if calib is not None else 0
    scale = UNCALIBRATED_SCALE
    flags: List[str] = []
    if calibrated:
        s = getattr(calib, "scale", None)
        if _isnum(s) and s >= 1.0:
            scale = float(s)
        else:
            calibrated = False
            flags.append("calibration scale invalid; uncalibrated scale used")
    if not calibrated:
        flags.append("uncalibrated (scale %.1f)" % UNCALIBRATED_SCALE)
        status = getattr(calib, "status", None) if calib is not None else None
        if status:
            flags.append(str(status))
    allowed = set(enabled) if enabled is not None else set(DEFAULT_ENABLED)
    allowed.discard("radar_ceiling")            # an upper bound only: never in the mean (PHYS-1)

    def usable(e: Estimate) -> bool:
        return (e.valid and _isnum(e.value_m) and e.value_m > 0 and _isnum(e.sigma_log) and e.sigma_log > 0)

    ceiling = None
    for e in ests:
        if e.name == "radar_ceiling" and usable(e):
            ceiling = float(e.value_m)
    used = [e for e in ests if e.name in allowed and usable(e)]
    if not used:
        return DepthResult(valid=False, calibrated=calibrated, n_pairs=n_pairs, method="none", scale=scale,
                           flags=flags, ceiling_m=ceiling, reason="no valid depth estimator",
                           estimates=[e.to_dict() for e in ests])
    dec_used = [e for e in used if not is_experimental(e)]
    if not dec_used:
        return DepthResult(valid=False, calibrated=calibrated, n_pairs=n_pairs, method="none", scale=scale,
                           flags=flags, ceiling_m=ceiling,
                           reason="only experimental depth estimators usable (they never decide)",
                           estimates=[e.to_dict() for e in ests])
    mu, sig, method = _gls(used)
    if mu is None:
        return DepthResult(valid=False, calibrated=calibrated, n_pairs=n_pairs, method="none", scale=scale,
                           flags=flags, ceiling_m=ceiling, reason="depth combination failed",
                           estimates=[e.to_dict() for e in ests])
    if len(dec_used) == len(used):
        mu_d, sig_d = mu, sig
    else:                                        # experimental estimator in the mean: decide without it
        mu_d, sig_d, _ = _gls(dec_used)
        if mu_d is None:
            return DepthResult(valid=False, calibrated=calibrated, n_pairs=n_pairs, method="none", scale=scale,
                               flags=flags, ceiling_m=ceiling, reason="depth combination failed (decision set)",
                               estimates=[e.to_dict() for e in ests])
    depth = math.exp(mu)
    lo = math.exp(mu - z * sig * scale)
    hi = math.exp(mu + z * sig * scale)
    if ceiling is not None:
        if trust:
            if ceiling >= depth:
                if ceiling < hi:
                    hi = ceiling
                    flags.append("upper end capped by trusted radar ceiling")
            else:
                flags.append("radar ceiling below combined depth: conflict, not capped")
        elif ceiling < hi:
            flags.append("radar ceiling %.1f m below upper end; not trusted for this fuel, ignored" % ceiling)

    # ---- DEPTH-HI rule: the upper end the dose uses (module docstring)
    dec_ests = [e for e in ests if e.kind == "estimate" and not is_experimental(e) and e.name != "radar_ceiling"
                and usable(e) and _isnum(e.hi_m) and e.hi_m > 0]
    hi_comb_d = math.exp(mu_d + z * sig_d * scale)
    hd, hd_from = hi_comb_d, "combined"
    for e in dec_ests:
        if float(e.hi_m) > hd:
            hd, hd_from = float(e.hi_m), e.name
    rule = "max(combined upper end, largest valid estimator upper end)"
    narrow_ok = (narrow_decision_hi is True and calibrated and _isnum(narrow_min_pairs)
                 and n_pairs >= int(narrow_min_pairs))
    if narrow_ok:
        hd, hd_from = hi_comb_d, "combined"
        rule = "combined upper end (narrow_decision_hi on, calibrated n = %d >= %d)" % (n_pairs, int(narrow_min_pairs))
        flags.append("decision upper end narrowed to the combined interval by config (n = %d calibrated pairs)"
                     % n_pairs)
    if ceiling is not None and trust and ceiling >= math.exp(mu_d) and ceiling < hd:
        hd, hd_from = ceiling, "radar_ceiling (trusted cap)"
        flags.append("decision upper end capped by trusted radar ceiling")
    ratio = None
    if len(dec_ests) >= 2:
        vals = sorted(((float(e.value_m), e.name) for e in dec_ests))
        ratio = vals[-1][0] / vals[0][0]
        fac = float(disagree_factor) if _isnum(disagree_factor) and disagree_factor > 1.0 else DISAGREE_FACTOR
        if ratio > fac:
            flags.append("%s: %s %.2f m vs %s %.2f m = %.1fx (> %.1fx); decision uses the largest upper end"
                         % (DISAGREE_FLAG, vals[-1][1], vals[-1][0], vals[0][1], vals[0][0], ratio, fac))
    return DepthResult(valid=True, depth_m=depth, lo_m=lo, hi_m=hi, level=0.90, used=[e.name for e in used],
                       calibrated=calibrated, n_pairs=n_pairs,
                       method=method + ", interval exp(mu +- z*sigma*scale)", scale=scale,
                       sigma_log=sig, flags=flags, ceiling_m=ceiling, reason="ok",
                       estimates=[e.to_dict() for e in ests], hi_decision_m=hd, hi_decision_from=hd_from,
                       hi_decision_rule=rule, disagree_ratio=ratio)


def _shared(e: Estimate) -> float:
    s = (e.details or {}).get("shared_log_sigma", 0.0)
    return float(s) if _isnum(s) and s > 0 else 0.0


def _gls(used: List[Estimate]):
    """(mu, sigma, method) of the log values: GLS with C_ii = sigma_i^2, C_ij = s_i * s_j (shared residence-time
    error, correlation 1). Falls back to the single estimator with the largest sigma_log (widest interval) when the
    solve fails or gives a non-finite / non-positive variance. (None, None, "") only if that is impossible too."""
    lv = np.array([math.log(e.value_m) for e in used])
    sg = np.array([float(e.sigma_log) for e in used])
    sh = np.array([min(_shared(e), float(e.sigma_log)) for e in used])
    cov = np.outer(sh, sh)
    np.fill_diagonal(cov, sg ** 2)
    ones = np.ones(len(used))
    try:
        a = np.linalg.solve(cov, ones)
        b = np.linalg.solve(cov, lv)
        den = float(ones @ a)
        mu = float(ones @ b) / den
        var = 1.0 / den
        if not (math.isfinite(mu) and math.isfinite(var) and var > 0):
            raise ValueError("non-finite GLS result")
        method = ("log-space GLS mean (shared residence-time error)" if np.any(sh > 0) and len(used) > 1
                  else "log-space inverse-variance mean")
        return mu, math.sqrt(var), method
    except (np.linalg.LinAlgError, ValueError, ZeroDivisionError):
        k = int(np.argmax(sg))
        if not (math.isfinite(lv[k]) and math.isfinite(sg[k]) and sg[k] > 0):
            return None, None, ""
        return float(lv[k]), float(sg[k]), "GLS failed: widest single estimator (%s)" % used[k].name


# ----------------------------------------------------------------------------------------------- intensity
@dataclass
class IntensityResult:
    valid: bool
    i_kw_m: Optional[float] = None
    lo: Optional[float] = None
    hi: Optional[float] = None
    sources: List[str] = field(default_factory=list)
    reason: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {k: (list(v) if isinstance(v, list) else v) for k, v in self.__dict__.items()}


def intensity(flame_height, spread, fuel: Fuel, z: float = Z90) -> IntensityResult:
    """Byram intensity [kW/m] from the flame height interval and/or the spread rate.

    flame_height: None, a number, or (h, h_lo, h_hi) [m]. Byram inverse of each (vertical flame: L = h; a tilted
    flame has L > h, so these values are LOW when there is wind; stated, not corrected).
    spread: None, an Estimate from ``spread_burn`` (details spread_m_s, spread_se_m_s), or a rate in m/s.
    I = R * H * w with R +- z * SE.
    Central value = max of the source central values, lo = min of lows, hi = max of upper ends (conservative).
    Fail closed (FS-2 / PHYS-2): a flame-height source whose h is not a finite number in (0, 100] m, or whose
    upper end hh is not finite, above 100 m or below h, gives an INVALID result, also when a spread-rate source is
    present (a finite spread hi must not hide an unbounded height hi). A missing / bad lower end only sets lo to 0.
    """
    vals, los, his, sources, det = [], [], [], [], {}
    if flame_height is not None:
        if isinstance(flame_height, (tuple, list)) and len(flame_height) == 3:
            h, hl, hh = flame_height
        else:
            h, hl, hh = flame_height, flame_height, flame_height
        if not (_isnum(h) and 0 < h <= 100):
            return IntensityResult(valid=False, reason="flame height %r not a finite value in (0, 100] m" % (h,),
                                   details={"byram": {"h_m": h, "h_lo_m": hl, "h_hi_m": hh}})
        if not (_isnum(hh) and h <= hh <= 100):
            return IntensityResult(valid=False, reason="flame height upper bound unbounded (h_hi = %r)" % (hh,),
                                   details={"byram": {"h_m": h, "h_lo_m": hl, "h_hi_m": hh}})
        hl = hl if (_isnum(hl) and 0 < hl <= h) else 0.0          # a lower end is never raised to h
        vals.append(byram_intensity_from_length(h))
        los.append(byram_intensity_from_length(hl))
        his.append(byram_intensity_from_length(hh))
        sources.append("byram_flame_height")
        det["byram"] = {"h_m": h, "h_lo_m": hl, "h_hi_m": hh, "i_kw_m": vals[-1]}
    if spread is not None:
        rate, se = None, 0.0
        if isinstance(spread, Estimate):
            if spread.valid:
                rate = spread.details.get("spread_m_s")
                se = spread.details.get("spread_se_m_s", 0.0) or 0.0
        elif _isnum(spread):
            rate = float(spread)
        if _isnum(rate) and rate > 0 and _isnum(se) and se >= 0:
            e = fuel.energy_kj_m2
            vals.append(rate * e)
            los.append(max(rate - z * se, 0.0) * e)
            his.append((rate + z * se) * e)
            sources.append("spread_rate")
            det["spread"] = {"spread_m_s": rate, "se_m_s": se, "energy_kj_m2": e, "i_kw_m": vals[-1]}
    if not vals:
        return IntensityResult(valid=False, reason="no intensity source", details=det)
    i_c = max(vals)
    lo = min(los)
    hi = max(his)
    if not (_isnum(i_c) and _isnum(hi) and i_c > 0 and hi >= i_c):
        return IntensityResult(valid=False, reason="non-finite intensity", details=det)
    return IntensityResult(valid=True, i_kw_m=i_c, lo=lo, hi=hi, sources=sources, reason="ok", details=det)
