"""Ember velocity from tracks and from motion-blur streaks.

Track velocity, per point. At every measured point a polynomial of degree
velocity.savgol_order is fitted by least squares to the positions in a sliding window of
velocity.savgol_window points, using the actual timestamps, and differentiated at that
point's own time. With uniform spacing this equals the Savitzky-Golay derivative filter;
with variable frame intervals it stays exact for polynomial motion. Near the track ends
the window is shifted inward (same size), so those points use one-sided fits; they are
marked `interior = False`. Coasted points (no measurement) are skipped.

Track velocity, whole track. A straight-line fit x(t), y(t) gives the mean velocity, the
speed and the direction, and the RMS residual tells how straight the track is.

Streak velocity. A streak of length L recorded during an exposure T_exp gives the speed
|v| = L / T_exp along the streak axis. The axis is known only mod 180 degrees, so the
sign comes from the track direction.

Fusion. Speeds are reported three ways and kept separate: track-only, streak-only and
fused. Fusion is used only for tracks shorter than velocity.fuse_max_points (5) points,
where the track speed is poor. It is an inverse-variance weighted mean of the track speed
and the track's mean streak speed. The streak variance has an independent part (length
noise, which averages down over the streak points) and a shared part from the exposure
uncertainty, which does not average down, neither over the points of one track nor over
many tracks. The fused result reports that shared part separately (`fused_shared_sd`),
so any average over tracks must add it back coherently.

Known gain on curved motion. The polynomial derivative is exact for motion that is
polynomial of degree <= order inside the window, so straight constant-velocity motion
has gain 1. On circular motion at angular rate omega, sampled every dt, a centred
symmetric derivative filter with weights c_k returns G times the true velocity with
G(omega) = sum_k c_k sin(k omega dt) / omega and no phase error. For the 5-point,
order 2 filter (the same weights as order 1) G = (sin(a) + 2 sin(2a)) / (5 a) with
a = omega dt, about 1 - 17 a^2 / 30: 0.8% low for a 33 rpm turntable at 30 fps and 4.2%
low at 78 rpm. `derivative_gain` computes G for any window and order, and
`correct_circular_speed` divides it out for the LED turntable test. The correction holds
for interior points only (the one-sided end fits have other gains and a phase error).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from wfglink.detect.candidates import FLAG_SATURATED


def _odd_window(window: int) -> int:
    window = max(int(window), 2)
    return window if window % 2 == 1 else window + 1


def derivative_weights(window: int, order: int, dt: float = 1.0) -> np.ndarray:
    """Centred derivative weights c_k (k = -h..h) for uniform spacing dt, in 1/s.

    The estimate is v = sum_k c_k x[i + k]. Equals scipy.signal.savgol_coeffs(window,
    order, deriv=1, delta=dt) up to the ordering of the taps.
    """
    window = _odd_window(window)
    half = window // 2
    order = min(int(order), window - 1)
    k = np.arange(-half, half + 1, dtype=np.float64)
    a = k[:, None] ** np.arange(order + 1)[None, :]
    pinv = np.linalg.pinv(a)
    return pinv[1] / dt


def derivative_noise_gain(window: int, order: int, dt: float) -> float:
    """Standard deviation of the velocity estimate per 1 px of white position noise (1/s)."""
    return float(np.sqrt(np.sum(derivative_weights(window, order, dt) ** 2)))


def derivative_gain(omega: float | np.ndarray, dt: float, window: int, order: int
                    ) -> np.ndarray | float:
    """Gain G of the centred polynomial derivative on a sinusoid or circular motion.

    G(omega) = sum_k c_k sin(k omega dt) / omega; G -> 1 as omega -> 0.
    """
    c = derivative_weights(window, order, dt)
    half = c.size // 2
    k = np.arange(-half, half + 1, dtype=np.float64)
    om = np.asarray(omega, dtype=np.float64)
    safe = np.where(np.abs(om) > 1e-12, om, 1.0)
    g = np.sum(c * np.sin(np.multiply.outer(safe, k * dt)), axis=-1) / safe
    g = np.where(np.abs(om) > 1e-12, g, 1.0)
    return float(g) if g.ndim == 0 else g


def correct_circular_speed(speed: float | np.ndarray, omega: float, dt: float, window: int,
                           order: int) -> np.ndarray | float:
    """Undo the derivative gain for constant-speed circular motion at angular rate omega."""
    return np.asarray(speed, dtype=np.float64) / derivative_gain(abs(omega), dt, window, order)


def estimate_angular_rate(t: np.ndarray, vx: np.ndarray, vy: np.ndarray) -> float:
    """Angular rate (rad/s) of the velocity direction: slope of its unwrapped angle over time.

    In image axes (y down) a positive value is clockwise on screen.
    """
    ok = np.isfinite(t) & np.isfinite(vx) & np.isfinite(vy)
    if np.count_nonzero(ok) < 2:
        return float("nan")
    phi = np.unwrap(np.arctan2(vy[ok], vx[ok]))
    tt = t[ok] - t[ok].mean()
    return float(np.sum(tt * (phi - phi.mean())) / np.sum(tt * tt))


def local_poly_velocity(t: np.ndarray, x: np.ndarray, y: np.ndarray, window: int, order: int
                        ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-point velocity (px/s) by local polynomial least squares on actual timestamps.

    Returns (vx, vy, interior). NaN positions (coasted points) are skipped and get NaN.
    `interior` marks points whose window has the full configured size (window, made odd)
    and is centred on them. Only those points have the noise gain and the circular-motion
    gain of the configured filter; a track with fewer measured points than the window is
    fitted over all of its points and has no interior points.
    """
    t = np.asarray(t, dtype=np.float64)
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    n_all = t.size
    vx = np.full(n_all, np.nan)
    vy = np.full(n_all, np.nan)
    interior = np.zeros(n_all, dtype=bool)
    ok = np.isfinite(t) & np.isfinite(x) & np.isfinite(y)
    idx_ok = np.flatnonzero(ok)
    n = idx_ok.size
    if n < 2:
        return vx, vy, interior
    tt, xx, yy = t[idx_ok], x[idx_ok], y[idx_ok]
    w_full = _odd_window(window)
    w = min(w_full, n)
    p = min(int(order), w - 1)
    half = w // 2
    i = np.arange(n)
    start = np.clip(i - half, 0, n - w)
    win = start[:, None] + np.arange(w)[None, :]                  # (n, w)
    tw = tt[win]
    scale = (tw[:, -1] - tw[:, 0]) / max(w - 1, 1)
    scale = np.where(scale > 0, scale, 1.0)
    s = (tw - tt[:, None]) / scale[:, None]                        # evaluate at own time
    a = s[:, :, None] ** np.arange(p + 1)[None, None, :]           # (n, w, p+1)
    ata = np.einsum("nwi,nwj->nij", a, a)
    rhs = np.stack((xx[win], yy[win]), axis=-1)                    # (n, w, 2)
    atb = np.einsum("nwi,nwk->nik", a, rhs)
    coef = np.linalg.solve(ata, atb)                               # (n, p+1, 2)
    vx[idx_ok] = coef[:, 1, 0] / scale
    vy[idx_ok] = coef[:, 1, 1] / scale
    interior[idx_ok] = (start == i - half) & (w == w_full)
    return vx, vy, interior


@dataclass
class MeanVelocity:
    """Straight-line fit of a track."""

    u: float                 # px/s
    v: float                 # px/s
    speed: float             # px/s
    direction_deg: float     # atan2(v, u) in image axes: 0 = right, +90 = down
    rms_resid_px: float      # RMS of the 2D residual distance
    sd_axis_px: float        # pooled per-axis residual sd (n - 2 dof), NaN for n <= 2
    speed_sd: float          # standard error of the speed, px/s
    n: int
    duration_s: float


def mean_velocity(t: np.ndarray, x: np.ndarray, y: np.ndarray, meas_sigma_px: float = 0.0
                  ) -> MeanVelocity:
    """Mean velocity from straight-line fits of x(t) and y(t), skipping NaN points.

    The speed standard error uses the larger of the residual sd and meas_sigma_px, so a
    two-point track still gets a sensible uncertainty.
    """
    t = np.asarray(t, dtype=np.float64)
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    ok = np.isfinite(t) & np.isfinite(x) & np.isfinite(y)
    t, x, y = t[ok], x[ok], y[ok]
    n = t.size
    nan = float("nan")
    if n < 2:
        return MeanVelocity(nan, nan, nan, nan, nan, nan, nan, n, 0.0)
    tc = t - t.mean()
    stt = float(np.sum(tc * tc))
    if stt <= 0:
        return MeanVelocity(nan, nan, nan, nan, nan, nan, nan, n, 0.0)
    u = float(np.sum(tc * (x - x.mean())) / stt)
    v = float(np.sum(tc * (y - y.mean())) / stt)
    rx = x - x.mean() - u * tc
    ry = y - y.mean() - v * tc
    ss = float(np.sum(rx * rx + ry * ry))
    rms = float(np.sqrt(ss / n))
    sd_axis = float(np.sqrt(ss / (2 * (n - 2)))) if n > 2 else nan
    sigma = max(sd_axis if np.isfinite(sd_axis) else 0.0, float(meas_sigma_px))
    speed = float(np.hypot(u, v))
    return MeanVelocity(u, v, speed, float(np.degrees(np.arctan2(v, u))), rms, sd_axis,
                        float(sigma / np.sqrt(stt)), n, float(t[-1] - t[0]))


def streak_velocity(length: np.ndarray, theta: np.ndarray, t_exp: float,
                    ref_vx: np.ndarray | float, ref_vy: np.ndarray | float
                    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Streak velocity: speed L / T_exp along the axis theta, signed to agree with (ref_vx, ref_vy).

    Returns (vx, vy, speed) in px/s. When the reference velocity is zero or NaN the
    sign cannot be resolved and vx, vy are NaN (the speed is still returned).
    """
    length = np.asarray(length, dtype=np.float64)
    theta = np.asarray(theta, dtype=np.float64)
    speed = length / float(t_exp)
    cx, cy = np.cos(theta), np.sin(theta)
    dot = cx * np.asarray(ref_vx, dtype=np.float64) + cy * np.asarray(ref_vy, dtype=np.float64)
    sign = np.where(dot > 0, 1.0, np.where(dot < 0, -1.0, np.nan))
    return speed * cx * sign, speed * cy * sign, speed


@dataclass
class SpeedSummary:
    """Track-only, streak-only and fused speed of one track (px/s), kept separate."""

    n_points: int
    track_speed: float
    track_speed_sd: float
    u: float
    v: float
    direction_deg: float
    rms_resid_px: float
    streak_speed: float          # mean of L / T_exp over usable streak points
    streak_sd_indep: float       # length-noise part, averages down over points
    streak_sd_shared: float      # exposure part, shared by every point and every track
    n_streak: int
    fused_speed: float           # NaN unless n_points < fuse_max_points and both exist
    fused_sd: float
    fused_shared_sd: float       # part of fused_sd that comes from the exposure error
    best_speed: float
    best_source: str             # "fused", "track", "streak" or "none"


def summarize_track_speed(t: np.ndarray, x: np.ndarray, y: np.ndarray, length: np.ndarray,
                          theta: np.ndarray, flags: np.ndarray, cfg: dict,
                          t_exp: float | None = None, t_exp_sd: float = 0.0) -> SpeedSummary:
    """Speeds of one track from its measured points (NaN rows are skipped).

    Config: track.meas_sigma_px, velocity.fuse_max_points (default 5),
    velocity.streak_min_length_px (default 5.0) and velocity.exposure.length_sigma_px
    (default 1.0). Saturated points are not used for streak speed.
    """
    vcfg = cfg.get("velocity", {})
    meas_sigma = float(cfg.get("track", {}).get("meas_sigma_px", 1.0))
    fuse_max = int(vcfg.get("fuse_max_points", 5))
    min_len = float(vcfg.get("streak_min_length_px", 5.0))
    sigma_l = float(vcfg.get("exposure", {}).get("length_sigma_px", 1.0))
    mv = mean_velocity(t, x, y, meas_sigma)
    nan = float("nan")
    s_speed = s_ind = s_sh = nan
    n_st = 0
    if t_exp is not None and t_exp > 0:
        length = np.asarray(length, dtype=np.float64)
        flags = np.asarray(flags)
        use = (np.isfinite(length) & (length > min_len) & np.isfinite(np.asarray(x, float))
               & ((flags.astype(np.int64) & FLAG_SATURATED) == 0))
        n_st = int(np.count_nonzero(use))
        if n_st:
            s_speed = float(np.mean(length[use]) / t_exp)
            s_ind = sigma_l / (t_exp * np.sqrt(n_st))
            s_sh = s_speed * float(t_exp_sd) / t_exp
    f_speed = f_sd = f_sh = nan
    if (mv.n < fuse_max and np.isfinite(mv.speed) and np.isfinite(s_speed)
            and mv.speed_sd > 0):
        w_tr = 1.0 / mv.speed_sd ** 2
        var_st = s_ind ** 2 + s_sh ** 2
        if var_st > 0:
            w_st = 1.0 / var_st
            f_speed = (w_tr * mv.speed + w_st * s_speed) / (w_tr + w_st)
            f_sd = float(np.sqrt(1.0 / (w_tr + w_st)))
            f_sh = w_st / (w_tr + w_st) * s_sh
    if np.isfinite(f_speed):
        best, src = f_speed, "fused"
    elif np.isfinite(mv.speed):
        best, src = mv.speed, "track"
    elif np.isfinite(s_speed):
        best, src = s_speed, "streak"
    else:
        best, src = nan, "none"
    return SpeedSummary(mv.n, mv.speed, mv.speed_sd, mv.u, mv.v, mv.direction_deg,
                        mv.rms_resid_px, s_speed, s_ind, s_sh, n_st, f_speed, f_sd, f_sh,
                        best, src)


def track_point_velocities(arrs: dict[str, np.ndarray], cfg: dict,
                           t_exp: float | None = None) -> dict[str, np.ndarray]:
    """Per-point velocities of one track (arrays from `Track.arrays()`).

    Returns vx_poly, vy_poly, speed_poly, interior and, when t_exp is given, the streak
    velocity at each point (vx_streak, vy_streak, speed_streak) signed by vx_poly, vy_poly.
    Positions are the measured ones (x_meas, y_meas); coasted points get NaN.
    Streak values are NaN where the streak is not usable, with the same rules as
    `summarize_track_speed`: length at most velocity.streak_min_length_px (default 5 px;
    a point-like blob has L near 0, which is not a speed of 0) and, when `arrs` has
    flags, saturated points (clipped streaks look shorter).
    """
    vcfg = cfg.get("velocity", {})
    window = int(vcfg.get("savgol_window", 5))
    order = int(vcfg.get("savgol_order", 2))
    min_len = float(vcfg.get("streak_min_length_px", 5.0))
    vx, vy, interior = local_poly_velocity(arrs["t"], arrs["x_meas"], arrs["y_meas"], window, order)
    out = {"vx_poly": vx, "vy_poly": vy, "speed_poly": np.hypot(vx, vy), "interior": interior}
    if t_exp is not None and t_exp > 0:
        length = np.asarray(arrs["length"], dtype=np.float64)
        usable = np.isfinite(length) & (length > min_len)
        if "flags" in arrs:
            usable &= (np.asarray(arrs["flags"]).astype(np.int64) & FLAG_SATURATED) == 0
        sx, sy, ss = streak_velocity(np.where(usable, length, np.nan), arrs["theta"], t_exp,
                                     vx, vy)
        out.update(vx_streak=sx, vy_streak=sy, speed_streak=ss)
    return out


def add_point_velocities(points, cfg: dict, t_exp: float | None = None):
    """Add per-point velocity columns to a long track-points DataFrame (one row per record).

    `points` needs track_id, t, x_meas, y_meas (and length, theta for streak columns), as
    written by `wfglink.track.tracker.tracks_to_frame`. Returns a new DataFrame with the
    same row order and index.
    """
    df = points.copy()
    cols = ["vx_poly", "vy_poly", "speed_poly", "interior"]
    if t_exp is not None and t_exp > 0:
        cols += ["vx_streak", "vy_streak", "speed_streak"]
    n = len(df)
    out = {c: (np.zeros(n, dtype=bool) if c == "interior" else np.full(n, np.nan)) for c in cols}
    if n:
        order = np.lexsort((df["t"].to_numpy(dtype=np.float64), df["track_id"].to_numpy()))
        tid = df["track_id"].to_numpy()[order]
        cuts = np.flatnonzero(tid[1:] != tid[:-1]) + 1
        src = {k: df[k].to_numpy(dtype=np.float64)[order] for k in ("t", "x_meas", "y_meas")}
        has_streak = "length" in df and "theta" in df
        if has_streak:
            src["length"] = df["length"].to_numpy(dtype=np.float64)[order]
            src["theta"] = df["theta"].to_numpy(dtype=np.float64)[order]
            if "flags" in df:
                src["flags"] = df["flags"].to_numpy().astype(np.int64)[order]
        for a, b in zip(np.r_[0, cuts].tolist(), np.r_[cuts, n].tolist()):
            arrs = {k: v[a:b] for k, v in src.items()}
            res = track_point_velocities(arrs, cfg, t_exp if has_streak else None)
            rows = order[a:b]
            for c in cols:
                if c in res:
                    out[c][rows] = res[c]
    for c in cols:
        df[c] = out[c]
    return df
