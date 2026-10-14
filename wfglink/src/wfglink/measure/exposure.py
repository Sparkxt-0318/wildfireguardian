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

Points used, over a rolling window of velocity.exposure.window_s seconds:
- finite speed and length, interior track points (centred derivative window);
- per-frame displacement |v| / fps >= velocity.exposure.min_disp_px;
- no saturated flag;
- L >= velocity.exposure.min_length_px (3 px). Cutting on the noisy L biases the slope
  upward (points whose noise pushed L over the cut are kept, the others dropped), so
  after a first pass the cut is moved to the predicted length T |v|, which depends only
  on the much less noisy speed. Those later passes also admit only points inside the
  previous pass's residual band (velocity.exposure.outlier_k scaled MADs), which keeps
  out point-like false tracks (L near 0 at high speed). The band is symmetric about the
  previous line; since the first line is biased by the cut, the passes repeat with the
  band re-centred until T changes by less than velocity.exposure.rel_tol (at most
  velocity.exposure.max_passes passes).

Robustness: the first estimate is the median of L / |v|. Each iteration computes the
standardised residuals (L - T |v|) / sqrt(sigma_L^2 + T^2 sigma_v^2), rejects points
further than velocity.exposure.outlier_k scaled MADs from their median, and refits by
Deming regression, until the inlier set stops changing.

Uncertainty: points of one track are correlated (same ember, same speed error), so the
confidence interval comes from a bootstrap over tracks, not points. With the inlier set
fixed by the full fit, each replicate only needs per-track sums of v^2, L^2 and v L, so
all replicates are one matrix product. The estimate needs at least
velocity.exposure.min_tracks distinct tracks.

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
    return {
        "window_s": float(e.get("window_s", 10.0)),
        "min_disp_px": float(e.get("min_disp_px", 5.0)),
        "min_tracks": int(e.get("min_tracks", 20)),
        "min_length_px": float(e.get("min_length_px", 3.0)),
        "length_sigma_px": float(e.get("length_sigma_px", 1.0)),
        "outlier_k": float(e.get("outlier_k", 3.5)),
        "max_iter": int(e.get("max_iter", 20)),
        "max_passes": max(1, int(e.get("max_passes", 10))),
        "rel_tol": float(e.get("rel_tol", 1e-4)),
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
    from the config at the nominal fps.
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

    track_id = np.asarray(track_id)
    t = np.asarray(t, dtype=np.float64)
    speed = np.asarray(speed, dtype=np.float64)
    length = np.asarray(length, dtype=np.float64)
    flags = np.asarray(flags).astype(np.int64)
    nan = float("nan")
    if t.size == 0:
        return ExposureEstimate(nan, nan, nan, nan, nan, (nan, nan), 0, 0, 0, nan, nan, False,
                                "no points")
    t_end = float(np.nanmax(t)) if t_now is None else float(t_now)
    t_start = t_end - c["window_s"]
    base = (np.isfinite(speed) & np.isfinite(length) & (t > t_start) & (t <= t_end)
            & (speed / fps >= c["min_disp_px"]) & ((flags & FLAG_SATURATED) == 0))
    if interior is not None:
        base &= np.asarray(interior, dtype=bool)

    def fail(reason, n_tr=0, n_pt=0):
        return ExposureEstimate(nan, nan, nan, nan, nan, (nan, nan), n_tr, n_pt, 0, t_start,
                                t_end, False, reason)

    # Pass 1: cut on the measured length.
    sel = base & (length >= c["min_length_px"])
    if len(np.unique(track_id[sel])) < c["min_tracks"]:
        return fail("too few tracks", len(np.unique(track_id[sel])), int(sel.sum()))
    v1, l1 = speed[sel], length[sel]
    t1, _, med1, mad1 = _robust_fit(v1, l1, delta, sig_l, sig_v, c["outlier_k"], c["max_iter"],
                                    float(np.median(l1 / v1)))
    if not np.isfinite(t1):
        return fail("fit failed", len(np.unique(track_id[sel])), int(sel.sum()))
    # Later passes: cut on the predicted length T |v| instead, which avoids selection
    # bias, and admit only points inside the previous pass's residual band. The band is
    # symmetric about the fitted line and keeps out point-like false tracks (L near 0 at
    # high speed) that pass 1 never saw. A biased first line would make the band
    # lopsided, so the passes repeat with the band re-centred until T settles.
    t_prev, med, mad = t1, med1, mad1
    t_exp = t1
    for _ in range(c["max_passes"]):
        r_all = _std_resid(speed, length, t_prev, sig_l, sig_v)
        cand = base & (t_prev * speed >= c["min_length_px"])
        sel = cand & (np.abs(r_all - med) <= c["outlier_k"] * mad)
        n_band_out = int(np.count_nonzero(cand & ~sel))
        tid = track_id[sel]
        n_tracks = len(np.unique(tid))
        if n_tracks < c["min_tracks"]:
            return fail("too few tracks", n_tracks, int(sel.sum()))
        v2, l2 = speed[sel], length[sel]
        t_exp, inl, med, mad = _robust_fit(v2, l2, delta, sig_l, sig_v, c["outlier_k"],
                                           c["max_iter"], t_prev)
        if not np.isfinite(t_exp):
            return fail("fit failed", n_tracks, int(sel.sum()))
        if abs(t_exp - t_prev) <= c["rel_tol"] * t_prev:
            break
        t_prev = t_exp

    # Bootstrap over tracks with the inlier set fixed.
    uniq, inv = np.unique(tid[inl], return_inverse=True)
    vi, li = v2[inl], l2[inl]
    sums = np.zeros((uniq.size, 3))
    np.add.at(sums, inv, np.column_stack((vi * vi, li * li, vi * li)))
    rng = np.random.default_rng(seed)
    b = c["bootstrap"]
    alpha = 1.0 - c["ci"]
    if b > 0 and uniq.size > 1:
        counts = rng.multinomial(uniq.size, np.full(uniq.size, 1.0 / uniq.size), size=b)
        rep = counts @ sums
        boot = _deming_from_sums(rep[:, 0], rep[:, 1], rep[:, 2], delta)
        boot = boot[np.isfinite(boot)]
        lo, hi = np.quantile(boot, [alpha / 2, 1 - alpha / 2])
        sd = float(np.std(boot, ddof=1))
    else:
        lo = hi = sd = nan
    return ExposureEstimate(
        t_exp=float(t_exp), ci_low=float(lo), ci_high=float(hi), sd=sd, duty=float(t_exp * fps),
        duty_ci=(float(lo * fps), float(hi * fps)), n_tracks=int(uniq.size),
        n_points=int(inl.sum()), n_outliers=n_band_out + int((~inl).sum()),
        t_start=t_start, t_end=t_end,
        ok=True, details={"delta_s2": delta, "sigma_length_px": sig_l, "sigma_speed_px_s": sig_v,
                          "first_pass_t_exp": float(t1)})


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
