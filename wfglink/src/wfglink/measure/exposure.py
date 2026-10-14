"""Exposure time T_exp from tracked embers: streak length versus track speed.

An ember moving at speed |v| during an exposure T_exp leaves a streak of length
L = T_exp |v|. Both L (from image moments) and |v| (from the track) are noisy, so T_exp is
the slope of a Deming regression through the origin, which allows errors in both
variables. With the variance ratio delta = sigma_L^2 / sigma_v^2 (s^2) and the uncentred
sums Sxx = sum v^2, Syy = sum L^2, Sxy = sum v L:

    T = (Syy - delta Sxx + sqrt((Syy - delta Sxx)^2 + 4 delta Sxy^2)) / (2 Sxy)

sigma_L is velocity.exposure.length_sigma_px; sigma_v is the speed noise of the
polynomial derivative, track.meas_sigma_px times the derivative filter's noise gain at
the nominal frame interval (`speed_noise_sd`).

Measured lengths are not always proportional to speed. The moment length of a short
streak has a floor (noise and compression ringing make a round spot look elongated), and
the faint ends of a long streak fall outside the thresholded window, so L / (T_exp |v|)
can fall steadily with streak length. A slope through the origin then depends on which
speeds are in the fit. An earlier version chose its points by the predicted length
T |v| of its own previous answer and, with short streaks, had more than one
self-consistent answer, so small upstream changes flipped it between them. Here the
selection never depends on T, so there is one answer, and the estimate is declined when
the data cannot confirm that L scales with |v|.

Steps (all parameters under velocity.exposure, points in a window of window_s seconds):
1. Points: finite speed and length, interior track points (centred derivative window),
   per-frame displacement |v| / fps >= min_disp_px, no saturated flag.
2. Screen: measured L >= screen_frac x min_length_px. This removes point-like false
   tracks (L near 0 at high speed) before anything is fitted. It sits well below the
   lengths that are fitted (step 3), so it cuts almost none of their noise. False tracks
   measured at a floor of a few pixels pass it; the outlier rejection (step 4) removes
   the ones far from the line, and many of the rest make the proportionality check
   (step 5) decline the estimate.
3. Speed cut: the candidate cuts are the speed quantiles cut_quantiles of the screened
   points. From the lowest, the points at or above the cut are fitted (step 4); the first
   cut whose predicted length T v_cut reaches min_length_px is used. Cutting on speed
   instead of measured length keeps the slope free of selection bias (the speed is the
   regressor), and the cuts are fixed before any fit, so there is no feedback from T.
4. Fit: robust Deming regression. The start is the median of L / |v|; each iteration
   computes the standardised residuals (L - T |v|) / sqrt(sigma_L^2 + T^2 sigma_v^2),
   rejects points further than outlier_k scaled MADs from their median, and refits,
   until the inlier set stops changing (at most max_iter iterations).
5. Checks. The estimate is declined, with the reason, when any fails:
   - starting value: refits from the start scaled by 1 - check_start_frac and
     1 + check_start_frac must agree with the fit within stable_tol;
   - speed cut: a refit at the neighbouring quantile cut must agree within stable_tol;
   - speed range: the 90th percentile of the inlier speeds must be at least
     min_speed_ratio times the 10th, or proportionality cannot be tested;
   - proportionality: a refit with a free intercept, L = a + b |v| (least squares on
     the tracks' mean speeds and lengths, weighted by their points, so that speed noise
     does not flatten it), must give T / b - 1 within prop_tol, and so must its
     bootstrap interval at level prop_ci (an equivalence test; step 6) when there are
     at least min_tracks_interval tracks. With fewer tracks (a turntable with three
     LEDs) a bootstrap over tracks says little and only the point value is checked. A
     length offset of a pixels biases the slope through the origin by about a / L, and
     a floor or lost ends act like one. A bias that is the same fraction at every
     length cannot be seen from L and |v| alone.
6. Uncertainty: points of one track are correlated (same ember, same speed error), so the
   intervals come from a bootstrap over tracks, not points. With the inlier set fixed by
   the full fit, each replicate only needs per-track sums of 1, v, L, v^2, L^2 and v L,
   so all replicates are one matrix product. The estimate needs at least min_tracks
   distinct tracks.

The duty cycle is T_exp times the nominal frame rate.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from wfglink.detect.candidates import FLAG_SATURATED
from wfglink.measure.velocity import derivative_noise_gain, local_poly_velocity


def deming_origin(x: np.ndarray, y: np.ndarray, delta: float) -> float:
    """Deming slope through the origin for y = b x, with delta = var(y error) / var(x error)."""
    sxx = float(np.dot(x, x))
    syy = float(np.dot(y, y))
    sxy = float(np.dot(x, y))
    return _deming_from_sums(sxx, syy, sxy, delta)


def _deming_from_sums(sxx, syy, sxy, delta):
    sxx, syy, sxy = np.asarray(sxx, float), np.asarray(syy, float), np.asarray(sxy, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        if delta == np.inf:
            b = sxy / sxx
        elif delta == 0:
            b = syy / sxy
        else:
            # Positive root of sxy b^2 - d b - delta sxy = 0, written without cancellation:
            # for d < 0 use b = 2 delta sxy / (sqrt(.) - d) (the product of the roots is -delta).
            d = syy - delta * sxx
            root = np.sqrt(d * d + 4.0 * delta * sxy * sxy)
            b = np.where(d >= 0, (d + root) / (2.0 * sxy), 2.0 * delta * sxy / (root - d))
    b = np.where(sxy > 0, b, np.nan)
    return float(b) if b.ndim == 0 else b


def _between_track_slope(sums):
    """Slope b of L = a + b v with a free intercept, fitted to track means.

    `sums` holds, along the first axis, the weighted sums over tracks of w, w v, w L,
    w v^2 and w v L, with w the track's point count and v, L its mean speed and length (a
    matrix of bootstrap sums gives one slope per column). Track means average out the
    point speed noise, which would otherwise flatten a slope fitted with a free
    intercept: a clip's speed spread is often only a few times that noise. NaN when the
    track speeds do not spread or the slope is not positive.
    """
    sw, swv, swl, swvv, swvl = sums
    with np.errstate(divide="ignore", invalid="ignore"):
        den = swvv - swv * swv / sw
        b = (swvl - swv * swl / sw) / den
    b = np.where((den > 0) & (b > 0), b, np.nan)
    return float(b) if np.ndim(b) == 0 else b


def speed_noise_sd(meas_sigma_px: float, fps: float, window: int, order: int) -> float:
    """Speed noise (px/s) of the centred polynomial derivative for white position noise."""
    return float(meas_sigma_px * derivative_noise_gain(window, order, 1.0 / fps))


@dataclass
class ExposureEstimate:
    """Exposure time estimate. Times in seconds; NaN when not estimable (ok = False)."""

    t_exp: float
    ci_low: float
    ci_high: float
    sd: float
    duty: float
    duty_ci: tuple[float, float]
    n_tracks: int
    n_points: int
    n_outliers: int
    t_start: float
    t_end: float
    ok: bool
    reason: str = ""
    details: dict = field(default_factory=dict)


def _exp_cfg(cfg: dict) -> dict:
    e = cfg.get("velocity", {}).get("exposure", {})
    quantiles = e.get("cut_quantiles", [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8])
    return {
        "window_s": float(e.get("window_s", 10.0)),
        "min_disp_px": float(e.get("min_disp_px", 5.0)),
        "min_tracks": int(e.get("min_tracks", 20)),
        "min_length_px": float(e.get("min_length_px", 4.0)),
        "screen_frac": float(e.get("screen_frac", 0.5)),
        "cut_quantiles": sorted(float(q) for q in quantiles),
        "length_sigma_px": float(e.get("length_sigma_px", 1.0)),
        "outlier_k": float(e.get("outlier_k", 3.5)),
        "max_iter": int(e.get("max_iter", 20)),
        "check_start_frac": float(e.get("check_start_frac", 0.3)),
        "stable_tol": float(e.get("stable_tol", 0.05)),
        "min_speed_ratio": float(e.get("min_speed_ratio", 1.3)),
        "prop_tol": float(e.get("prop_tol", 0.10)),
        "prop_ci": float(e.get("prop_ci", 0.9)),
        "min_tracks_interval": int(e.get("min_tracks_interval", 10)),
        "bootstrap": int(e.get("bootstrap", 200)),
        "ci": float(e.get("ci", 0.95)),
    }


def _std_resid(v: np.ndarray, length: np.ndarray, t_exp: float, sig_l: float, sig_v: float
               ) -> np.ndarray:
    return (length - t_exp * v) / np.sqrt(sig_l ** 2 + (t_exp * sig_v) ** 2)


def _robust_fit(v: np.ndarray, length: np.ndarray, delta: float, sig_l: float, sig_v: float,
                k: float, max_iter: int, t0: float
                ) -> tuple[float, np.ndarray, float, float]:
    """Iterated Deming fit with MAD rejection on standardised residuals.

    Returns (T, inliers, median, scale) where median and scale describe the standardised
    residuals of the final iteration.
    """
    t_exp = t0
    inl = np.ones(v.size, dtype=bool)
    med, mad = 0.0, 1.0
    for _ in range(max_iter):
        r = _std_resid(v, length, t_exp, sig_l, sig_v)
        # Location and scale from all points: the MAD tolerates up to half outliers and,
        # unlike a scale from the current inliers only, does not shrink every iteration.
        med = float(np.median(r))
        mad = 1.4826 * float(np.median(np.abs(r - med)))
        if not mad > 0:
            mad = float(np.std(r)) or 1.0
        new = np.abs(r - med) <= k * mad
        if new.sum() < 2:
            break
        t_new = deming_origin(v[new], length[new], delta)
        if not np.isfinite(t_new) or t_new <= 0:
            break
        changed = not np.array_equal(new, inl)
        inl, t_exp = new, t_new
        if not changed:
            break
    return t_exp, inl, med, mad


def estimate_exposure(track_id: np.ndarray, t: np.ndarray, speed: np.ndarray,
                      length: np.ndarray, flags: np.ndarray, *, fps: float, cfg: dict,
                      t_now: float | None = None, interior: np.ndarray | None = None,
                      speed_sd: float | None = None, seed: int = 0) -> ExposureEstimate:
    """Estimate T_exp (s) from per-point track speeds (px/s) and streak lengths (px).

    All inputs are 1D arrays over track points. Points in (t_now - window_s, t_now] are
    used; t_now defaults to the latest time. `speed_sd` defaults to `speed_noise_sd`
    from the config at the nominal fps. A declined estimate (ok False) has NaN times,
    the reason, and in `details` whatever was computed before the failing check.
    """
    c = _exp_cfg(cfg)
    vcfg = cfg.get("velocity", {})
    window, order = int(vcfg.get("savgol_window", 5)), int(vcfg.get("savgol_order", 2))
    meas_sigma = float(cfg.get("track", {}).get("meas_sigma_px", 1.0))
    if speed_sd is None:
        speed_sd = speed_noise_sd(meas_sigma, fps, window, order)
    sig_v = float(speed_sd)
    sig_l = c["length_sigma_px"]
    delta = sig_l ** 2 / sig_v ** 2 if sig_v > 0 else np.inf
    min_len, k, max_iter = c["min_length_px"], c["outlier_k"], c["max_iter"]

    track_id = np.asarray(track_id)
    t = np.asarray(t, dtype=np.float64)
    speed = np.asarray(speed, dtype=np.float64)
    length = np.asarray(length, dtype=np.float64)
    flags = np.asarray(flags).astype(np.int64)
    nan = float("nan")
    details: dict = {"delta_s2": delta, "sigma_length_px": sig_l, "sigma_speed_px_s": sig_v}
    if t.size == 0:
        return ExposureEstimate(nan, nan, nan, nan, nan, (nan, nan), 0, 0, 0, nan, nan, False,
                                "no points", details)
    t_end = float(np.nanmax(t)) if t_now is None else float(t_now)
    t_start = t_end - c["window_s"]
    base = (np.isfinite(speed) & np.isfinite(length) & (t > t_start) & (t <= t_end)
            & (speed / fps >= c["min_disp_px"]) & ((flags & FLAG_SATURATED) == 0))
    if interior is not None:
        base &= np.asarray(interior, dtype=bool)

    def n_tracks_of(mask):
        return len(np.unique(track_id[mask]))

    def fail(reason, mask=None):
        n_tr, n_pt = (n_tracks_of(mask), int(mask.sum())) if mask is not None else (0, 0)
        return ExposureEstimate(nan, nan, nan, nan, nan, (nan, nan), n_tr, n_pt, 0, t_start,
                                t_end, False, reason, details)

    def fit(mask, scale=1.0):
        v, ln = speed[mask], length[mask]
        return _robust_fit(v, ln, delta, sig_l, sig_v, k, max_iter, scale * float(np.median(ln / v)))

    # Steps 2 and 3: screen, then the lowest speed cut whose streaks are long enough.
    cand = base & (length >= c["screen_frac"] * min_len)
    if n_tracks_of(cand) < c["min_tracks"]:
        return fail("too few tracks", cand)
    v_cand = speed[cand]
    cuts = [float(np.quantile(v_cand, q)) for q in c["cut_quantiles"]]
    chosen = None
    out_of_tracks = False
    scan = details["cut_scan"] = []     # (quantile, speed cut, T, tracks) for each cut tried
    for i, v_cut in enumerate(cuts):
        sel = cand & (speed >= v_cut)
        n_sel = n_tracks_of(sel)
        if n_sel < c["min_tracks"]:
            out_of_tracks = True
            break
        t_exp, inl, _, _ = fit(sel)
        if not np.isfinite(t_exp):
            return fail("fit failed", sel)
        scan.append((c["cut_quantiles"][i], v_cut, float(t_exp), n_sel))
        if t_exp * v_cut >= min_len:
            chosen = i
            break
    if chosen is None:
        details["t_exp_unchecked"] = None
        where = ("at every speed cut with enough tracks" if out_of_tracks else
                 f"at every speed cut (speed quantiles up to {max(c['cut_quantiles'], default=0.0):g})")
        reason = f"predicted streak length T |v| under {min_len:g} px {where}"
        if len(scan) > 1 and abs(scan[-1][2] / scan[0][2] - 1.0) > c["stable_tol"]:
            reason += (f"; T also moves from {1000 * scan[0][2]:.3g} to {1000 * scan[-1][2]:.3g} ms "
                       "across the cuts (streak length not proportional to speed)")
        return fail(reason, cand)
    v_cut = cuts[chosen]
    details.update(speed_cut_px_s=v_cut, cut_quantile=c["cut_quantiles"][chosen],
                   t_exp_unchecked=float(t_exp))
    v2, l2, tid = speed[sel], length[sel], track_id[sel]

    # Step 5: checks. Starting value.
    tol = c["stable_tol"]
    alt = [fit(sel, 1.0 + s)[0] for s in (-c["check_start_frac"], c["check_start_frac"])]
    details["t_exp_other_starts"] = [float(a) for a in alt]
    if not all(np.isfinite(a) and abs(a / t_exp - 1.0) <= tol for a in alt):
        return fail("estimate depends on the starting value of the fit", sel)
    # Speed cut: the next quantile cut, or the previous one when the next has too few tracks.
    other = [j for j in (chosen + 1, chosen - 1) if 0 <= j < len(cuts)
             and n_tracks_of(cand & (speed >= cuts[j])) >= c["min_tracks"]]
    if not other:
        return fail("too few tracks to check the speed cut", sel)
    t_j = fit(cand & (speed >= cuts[other[0]]))[0]
    details["t_exp_other_cut"] = float(t_j)
    if not (np.isfinite(t_j) and abs(t_j / t_exp - 1.0) <= tol):
        return fail("estimate changes with the speed cut (streak length not proportional to speed)", sel)
    # Proportionality: refit with a free intercept, L = a + b |v|. With proportional
    # lengths b equals T; a length offset (a floor, or ends lost) moves T away from b.
    vi, li = v2[inl], l2[inl]
    p10, p90 = np.quantile(vi, [0.1, 0.9])
    details["speed_ratio_90_10"] = float(p90 / p10)
    if p90 / p10 < c["min_speed_ratio"]:
        return fail("speed range too narrow to test that streak length scales with speed", sel)
    uniq, inv = np.unique(tid[inl], return_inverse=True)
    sums = np.zeros((uniq.size, 6))
    np.add.at(sums, inv, np.column_stack((np.ones_like(vi), vi, li, vi * vi, li * li, vi * li)))
    w, v_mean, l_mean = sums[:, 0], sums[:, 1] / sums[:, 0], sums[:, 2] / sums[:, 0]
    tsums = np.column_stack((w, w * v_mean, w * l_mean, w * v_mean ** 2, w * v_mean * l_mean))
    b_free = _between_track_slope(tsums.sum(axis=0))
    offset_effect = t_exp / b_free - 1.0 if np.isfinite(b_free) else np.inf
    details.update(t_exp_free_intercept=float(b_free), offset_effect=float(offset_effect))
    if not np.isfinite(b_free):
        return fail("streak length does not grow with speed", sel)
    if not abs(offset_effect) <= c["prop_tol"]:
        return fail("streak length not proportional to speed (a free intercept changes the slope by "
                    f"{100 * offset_effect:+.0f} percent)", sel)

    # Bootstrap over tracks with the inlier set fixed: the interval of T, and the interval
    # of the intercept effect, which must lie within prop_tol to confirm proportionality
    # (only with at least min_tracks_interval tracks; see the module notes).
    rng = np.random.default_rng(seed)
    b = c["bootstrap"]
    alpha = 1.0 - c["ci"]
    if b > 0 and uniq.size > 1:
        counts = rng.multinomial(uniq.size, np.full(uniq.size, 1.0 / uniq.size), size=b)
        rep = counts @ sums
        boot = _deming_from_sums(rep[:, 3], rep[:, 4], rep[:, 5], delta)
        with np.errstate(divide="ignore", invalid="ignore"):
            eff = boot / _between_track_slope((counts @ tsums).T) - 1.0
        eff = np.nan_to_num(eff, nan=1e3, posinf=1e3)   # no rising line: far outside
        a_p = 1.0 - c["prop_ci"]
        e_lo, e_hi = (float(q) for q in np.quantile(eff, [a_p / 2, 1 - a_p / 2]))
        details["offset_effect_ci"] = [e_lo, e_hi]
        if uniq.size >= c["min_tracks_interval"] and not -c["prop_tol"] <= e_lo <= e_hi <= c["prop_tol"]:
            return fail("too little speed range or too few tracks to confirm that streak length scales "
                        "with speed", sel)
        boot = boot[np.isfinite(boot)]
        lo, hi = np.quantile(boot, [alpha / 2, 1 - alpha / 2])
        sd = float(np.std(boot, ddof=1))
    else:
        lo = hi = sd = nan
    n_screened = int(np.count_nonzero(base & ~cand & (speed >= v_cut)))
    return ExposureEstimate(
        t_exp=float(t_exp), ci_low=float(lo), ci_high=float(hi), sd=sd, duty=float(t_exp * fps),
        duty_ci=(float(lo * fps), float(hi * fps)), n_tracks=int(uniq.size),
        n_points=int(inl.sum()), n_outliers=n_screened + int((~inl).sum()),
        t_start=t_start, t_end=t_end, ok=True, details=details)


def exposure_points_from_track(arrs: dict[str, np.ndarray], window: int, order: int
                               ) -> dict[str, np.ndarray]:
    """Per-point speed, length, flags and interior mask of one track (from `Track.arrays()`)."""
    vx, vy, interior = local_poly_velocity(arrs["t"], arrs["x_meas"], arrs["y_meas"], window, order)
    meas = np.isfinite(np.asarray(arrs["x_meas"], dtype=np.float64))
    return {"t": np.asarray(arrs["t"], np.float64)[meas], "speed": np.hypot(vx, vy)[meas],
            "length": np.asarray(arrs["length"], np.float64)[meas],
            "flags": np.asarray(arrs["flags"]).astype(np.int64)[meas], "interior": interior[meas]}


class RollingExposure:
    """Rolling T_exp estimator fed with finished (or growing) tracks.

    `add_track` takes `Track.arrays()` of a track; points older than the window are
    dropped on `estimate`. Adding the same track id again replaces its earlier points.
    """

    def __init__(self, cfg: dict, fps: float, seed: int = 0):
        self.cfg = cfg
        self.fps = float(fps)
        self.seed = seed
        v = cfg.get("velocity", {})
        self.window = int(v.get("savgol_window", 5))
        self.order = int(v.get("savgol_order", 2))
        self.window_s = _exp_cfg(cfg)["window_s"]
        self._pts: dict[int, dict[str, np.ndarray]] = {}

    def add_track(self, track_id: int, arrs: dict[str, np.ndarray]) -> None:
        self._pts[int(track_id)] = exposure_points_from_track(arrs, self.window, self.order)

    def estimate(self, t_now: float | None = None) -> ExposureEstimate:
        if t_now is not None:
            cutoff = float(t_now) - self.window_s
            old = [k for k, p in self._pts.items() if p["t"].size == 0 or p["t"].max() <= cutoff]
            for k in old:
                del self._pts[k]
        if not self._pts:
            return estimate_exposure(np.zeros(0), np.zeros(0), np.zeros(0), np.zeros(0),
                                     np.zeros(0), fps=self.fps, cfg=self.cfg, t_now=t_now)
        ids = np.concatenate([np.full(p["t"].size, k) for k, p in self._pts.items()])
        cat = {f: np.concatenate([p[f] for p in self._pts.values()])
               for f in ("t", "speed", "length", "flags", "interior")}
        return estimate_exposure(ids, cat["t"], cat["speed"], cat["length"], cat["flags"],
                                 fps=self.fps, cfg=self.cfg, t_now=t_now,
                                 interior=cat["interior"], seed=self.seed)
