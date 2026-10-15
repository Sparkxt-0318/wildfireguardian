"""Streak length methods for file mode (detect.streaks.method), applied after detection.

The detector measures each blob's second moments inside its thresholded component. A long,
faint streak spreads its light thinly, so its ends fall below the threshold and the
window cuts them off: the length comes out short. A short streak has the opposite
problem, because its window is mostly noise and blur, and noise makes a round spot look
elongated (a floor of a few pixels).

method "moments" keeps the detector's moments; with streaks.refine it recomputes the
moments of the signed residual, with no threshold, inside a rectangle along the first
estimate's axis that reaches streaks.margin_sigma PSF widths beyond the ends and to each
side, and repeats streaks.iterations times (`refine_streaks`). A refinement that moves the
centroid more than half the length, or changes the length by more than
streaks.max_change, is discarded (a neighbour in the window, or noise), and the first
estimate stays.

method "erf" fits a model instead (`erf_streaks`). A streak is a segment of length L,
blurred by the PSF (sigma s). Summed across its axis it is a profile along the axis u with
two error-function edges, F / L [Phi((u - c + L/2) / s) - Phi((u - c - L/2) / s)]; summed
along its axis it is a Gaussian of the same s across the axis. Per detection:
1. The luma is decoded with the power law streaks.erf.gamma before the background is
   subtracted, because the model is linear in light and video luma is gamma encoded (a
   tone curve compresses a streak's plateau relative to its edges and widens it).
2. The signed residual is sampled (bilinear, step streaks.erf.step_px) on a grid along the
   detector's moment axis: half-length reach L0 / 2 + margin_sigma s0, half-width
   half_width_sigma s0, from the detector's length L0 and minor-axis sigma s0. No
   threshold, so the faint ends are inside.
3. The across profile (the grid summed along the axis, weighted by the first estimate's
   box) gives the axis offset and s; the along profile (summed across, weighted by that
   Gaussian, the matched filter) is then fitted jointly with the across profile: F, c, L,
   s shared by both, and the across amplitude and offset. s comes from the across profile
   wherever the edges cannot separate it from L (short streaks), from both otherwise.
   With streaks.erf.ramp_sigma > 0 the brightness may also change linearly along the
   streak (flicker within the exposure), with a Gaussian prior of that sd on the change.
4. streaks.erf.iterations = 2 repeats steps 2 and 3 once on a window centred on the fit,
   long enough for the fitted length, with the axis turned by the offset between the
   across centroids of the streak's two halves (streaks that are resolved only).
5. A fit that does not converge to a streak inside its window (non-finite, an edge outside
   the window, or s at a bound) keeps the detector's length. Positions are not changed.

The fit uses only the frame itself, so noise still biases the length of streaks shorter
than about two PSF widths upward: the axis is the direction in which the noisy blob looks
longest. Off in live mode (cost); used in file mode and validation.
"""
from __future__ import annotations

import math
from dataclasses import replace
from functools import lru_cache

import cv2
import numpy as np
from scipy.special import ndtr

from wfglink.detect.candidates import Detections, DetectorState


def _cfg(cfg: dict) -> dict:
    s = cfg.get("detect", {}).get("streaks", {})
    return {"min_length": float(s.get("refine_min_length_px", 2.0)), "iterations": int(s.get("iterations", 2)),
            "margin": float(s.get("margin_sigma", 2.5)), "max_change": float(s.get("max_change", 0.6)),
            "min_sigma": float(s.get("min_psf_sigma_px", 0.7))}


def _moments(res: np.ndarray, xs: np.ndarray, ys: np.ndarray):
    f = res.sum()
    if f <= 0:
        return None
    mx, my = (res * xs).sum() / f, (res * ys).sum() / f
    dx, dy = xs - mx, ys - my
    cxx, cyy, cxy = (res * dx * dx).sum() / f, (res * dy * dy).sum() / f, (res * dx * dy).sum() / f
    half = (cxx + cyy) / 2
    disc = math.sqrt(max(((cxx - cyy) / 2) ** 2 + cxy ** 2, 0.0))
    l1, l2 = max(half + disc, 0.0), max(half - disc, 0.0)
    return mx, my, l1, l2, 0.5 * math.atan2(2 * cxy, cxx - cyy), f


def refine_streaks(det: Detections, state: DetectorState, cfg: dict) -> Detections:
    if len(det) == 0 or state.luma is None:
        return det
    c = _cfg(cfg)
    y, bg = state.luma, state.background
    h, w = y.shape
    x_, y_ = det.x.copy(), det.y.copy()
    L, th = det.length.copy(), det.theta.copy()
    l1s, l2s = det.lam1.copy(), det.lam2.copy()
    for i in range(len(det)):
        if not (np.isfinite(L[i]) and L[i] >= c["min_length"] and np.isfinite(x_[i])):
            continue
        mx, my, length, theta = float(x_[i]), float(y_[i]), float(L[i]), float(th[i])
        sig = max(math.sqrt(max(float(l2s[i]), 0.0)), c["min_sigma"])
        ok = True
        est = None
        for _ in range(c["iterations"]):
            hl, hw = length / 2 + c["margin"] * sig, c["margin"] * sig
            ct, st = math.cos(theta), math.sin(theta)
            ext_x, ext_y = abs(hl * ct) + abs(hw * st), abs(hl * st) + abs(hw * ct)
            x0, x1 = max(int(mx - ext_x), 0), min(int(mx + ext_x) + 2, w)
            y0, y1 = max(int(my - ext_y), 0), min(int(my + ext_y) + 2, h)
            if x1 - x0 < 2 or y1 - y0 < 2:
                ok = False
                break
            gx, gy = np.meshgrid(np.arange(x0, x1, dtype=np.float64), np.arange(y0, y1, dtype=np.float64))
            u = (gx - mx) * ct + (gy - my) * st
            v = -(gx - mx) * st + (gy - my) * ct
            inside = (np.abs(u) <= hl) & (np.abs(v) <= hw)
            res = (y[y0:y1, x0:x1].astype(np.float64) - bg[y0:y1, x0:x1]
                   - state.offset_map[y0:y1, x0:x1] - state.offset_delta)[inside]
            est = _moments(res, gx[inside], gy[inside])
            if est is None:
                ok = False
                break
            nmx, nmy, nl1, nl2, nth, _ = est
            nlen = math.sqrt(max(12.0 * (nl1 - nl2), 0.0))
            if math.hypot(nmx - x_[i], nmy - y_[i]) > max(0.5 * L[i], 2.0) or abs(nlen - L[i]) > c["max_change"] * max(L[i], 3.0):
                ok = False
                break
            mx, my, length, theta = nmx, nmy, nlen, nth
        if ok and est is not None:
            x_[i], y_[i], L[i], th[i] = mx, my, length, theta
            l1s[i], l2s[i] = est[2], est[3]
    return replace(det, x=x_, y=y_, length=L, theta=th, lam1=l1s, lam2=l2s, width=4.0 * np.sqrt(l2s))


# Edge-profile fit (method "erf") ----------------------------------------------------------
_SQ2PI = math.sqrt(2.0 * math.pi)
_REMAP_MAX_ROWS = 32000


def _erf_cfg(cfg: dict) -> dict:
    s = cfg.get("detect", {}).get("streaks", {})
    e = s.get("erf") or {}
    return {"gamma": float(e.get("gamma", 2.2)), "reach": float(e.get("reach", 1.5)),
            "margin": float(e.get("margin_sigma", 3.0)), "half_width": float(e.get("half_width_sigma", 3.0)),
            "step": float(e.get("step_px", 1.0)), "iterations": int(e.get("iterations", 1)),
            "ramp_sigma": float(e.get("ramp_sigma", 0.0)), "max_iter": int(e.get("max_iter", 8)),
            "across_iter": int(e.get("across_iter", 4)),
            "max_turn": math.radians(float(e.get("max_turn_deg", 20.0))),
            "max_half_length": float(e.get("max_half_length_px", 60.0)),
            "sigma_range": tuple(float(v) for v in e.get("sigma_range_px", (0.3, 6.0))),
            "min_sigma": float(s.get("min_psf_sigma_px", 0.7))}


@lru_cache(maxsize=4)
def _decode_lut(gamma: float) -> np.ndarray:
    return (255.0 * (np.arange(256) / 255.0) ** gamma).astype(np.float32)


def _decode(v: np.ndarray, gamma: float) -> np.ndarray:
    if gamma == 1.0:
        return v
    return np.float32(255.0) * (np.clip(v, 0.0, 255.0) / np.float32(255.0)) ** np.float32(gamma)


def _frame_images(state: DetectorState, gamma: float) -> tuple[np.ndarray, np.ndarray]:
    """Decoded luma and the background level (background plus tile offsets, still encoded),
    float32, computed once per frame."""
    img = cv2.LUT(state.luma, _decode_lut(gamma)) if gamma != 1.0 else state.luma.astype(np.float32)
    bg = state.background.astype(np.float32)
    if state.offset_map is not None:
        bg += state.offset_map
    bg += np.float32(state.offset_delta)
    return img, bg


def _sample(images, gamma: float, xc, yc, th, U, V) -> np.ndarray:
    """Signed residual (decoded luma minus decoded background) at the points
    (xc + u cos th - v sin th, yc + u sin th + v cos th), bilinear. U (m, nu) and V (m, nv)
    are the axis coordinates; returns (m, nv, nu), NaN outside the frame."""
    img, bg = images
    m, nu, nv = U.shape[0], U.shape[1], V.shape[1]
    ct, st = np.cos(th)[:, None, None], np.sin(th)[:, None, None]
    u, v = U[:, None, :], V[:, :, None]
    mx = (xc[:, None, None] + u * ct - v * st).astype(np.float32).reshape(m * nv, nu)
    my = (yc[:, None, None] + u * st + v * ct).astype(np.float32).reshape(m * nv, nu)
    nan = float("nan")
    ys = np.empty((m * nv, nu), np.float32)
    bs = np.empty((m * nv, nu), np.float32)
    # cv2.remap needs fewer than SHRT_MAX rows per call (many detections in one frame).
    for a in range(0, m * nv, _REMAP_MAX_ROWS):
        b = a + _REMAP_MAX_ROWS
        ys[a:b] = cv2.remap(img, mx[a:b], my[a:b], cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=nan)
        bs[a:b] = cv2.remap(bg, mx[a:b], my[a:b], cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=nan)
    return (ys - _decode(bs, gamma)).astype(np.float64).reshape(m, nv, nu)


def _phi(z: np.ndarray) -> np.ndarray:
    return np.exp(-0.5 * z * z) / _SQ2PI


def _along(u, F, c, L, s, k=None):
    """Box of length L centred at c, blurred by N(0, s^2), total F: the model and its
    derivatives by (F, c, L, s), and by k when given (a linear brightness change, relative,
    from one end to the other)."""
    Ls = np.maximum(L, 1e-3)
    z1 = (c - Ls / 2 - u) / s
    z2 = (c + Ls / 2 - u) / s
    D = ndtr(z2) - ndtr(z1)
    p1, p2 = _phi(z1), _phi(z2)
    q = F / Ls
    dD_dc = (p2 - p1) / s
    dD_dL = (p1 + p2) / (2 * s)
    dD_ds = (z1 * p1 - z2 * p2) / s
    if k is None:
        return q * D, (D / Ls, q * dD_dc, q * (dD_dL - D / Ls), q * dD_ds)
    dp = p1 - p2
    wpos = (u - c) / Ls
    G = (1 + k * wpos) * D + k * s / Ls * dp
    dP_dc = (z2 * p2 - z1 * p1) / s
    dP_dL = (z1 * p1 + z2 * p2) / (2 * s)
    dP_ds = (z1 * z1 * p1 - z2 * z2 * p2) / s
    dG_dc = -k / Ls * D + (1 + k * wpos) * dD_dc + k * s / Ls * dP_dc
    dG_dL = -k * wpos / Ls * D + (1 + k * wpos) * dD_dL - k * s / Ls ** 2 * dp + k * s / Ls * dP_dL
    dG_ds = (1 + k * wpos) * dD_ds + k / Ls * dp + k * s / Ls * dP_ds
    dG_dk = wpos * D + s / Ls * dp
    return q * G, (G / Ls, q * dG_dc, q * dG_dL - q / Ls * G, q * dG_ds, q * dG_dk)


def _across(v, FA, v0, s):
    z = (v - v0) / s
    g = _phi(z) / s
    return FA * g, (g, FA * g * z / s, FA * g * (z * z - 1) / s)


def _lm(fun, p, y, lo, hi, max_iter):
    """Batched Levenberg-Marquardt with box bounds (clipped steps). fun(p, rows) returns the
    model (len(rows), n) and Jacobian (len(rows), n, k) of those rows. A fit stops when an
    accepted step lowers its cost by less than 1e-4 of it, or its damping runs away; the
    rest go on, up to max_iter steps. Returns the parameters."""
    m = p.shape[0]
    rows = np.arange(m)
    p = np.clip(p, lo, hi)
    mod, J = fun(p, rows)
    r = y - mod
    cost = np.einsum("mn,mn->m", r, r)
    lam = np.full(m, 1e-2)
    eye = np.eye(p.shape[1])
    act = rows
    for _ in range(max_iter):
        Ja = J[act]
        Jt = Ja.transpose(0, 2, 1)
        JtJ = Jt @ Ja
        g = (Jt @ r[act][..., None])[..., 0]
        diag = np.einsum("mii->mi", JtJ)
        A = JtJ + lam[act][:, None, None] * (diag[:, :, None] * eye) + 1e-12 * eye
        try:
            step = np.linalg.solve(A, g[..., None])[..., 0]
        except np.linalg.LinAlgError:
            step = np.zeros((act.size, p.shape[1]))
        pn = np.clip(p[act] + step, lo[act], hi[act])
        modn, Jn = fun(pn, act)
        rn = y[act] - modn
        cn = np.einsum("mn,mn->m", rn, rn)
        c_old = cost[act]
        better = np.isfinite(cn) & (cn < c_old)
        finished = (better & (c_old - cn <= 1e-4 * c_old)) | (lam[act] >= 1e6)
        b = act[better]
        p[b], J[b], r[b], cost[b] = pn[better], Jn[better], rn[better], cn[better]
        lam[act] = np.clip(np.where(better, lam[act] * 0.3, lam[act] * 10.0), 1e-9, 1e6)
        act = act[~finished]
        if act.size == 0:
            break
    return p


def _fit_pass(images, c, xc, yc, th, L0, s0, hl, hw, ramp):
    """One window per detection: sample, collapse to profiles, fit the across profile, then
    fit both profiles jointly. Returns the parameters (F, c, L, s, FA, v0, k), a validity
    mask and the samples (for the axis update)."""
    m = xc.size
    step = c["step"]
    nu = 2 * int(math.ceil(float(hl.max()) / step)) + 1
    nv = 2 * int(math.ceil(float(hw.max()) / step)) + 1
    U = np.broadcast_to((np.arange(nu) - (nu - 1) / 2) * step, (m, nu))
    V = np.broadcast_to((np.arange(nv) - (nv - 1) / 2) * step, (m, nv))
    mu = np.abs(U) <= hl[:, None] + 1e-9
    mv = np.abs(V) <= hw[:, None] + 1e-9
    S = _sample(images, c["gamma"], xc, yc, th, U, V)
    inside = mv[:, :, None] & mu[:, None, :]
    valid = ~np.any(np.isnan(S) & inside, axis=(1, 2))
    S = np.where(inside & np.isfinite(S), S, 0.0)
    # Across profile, weighted along by the first estimate's box (its light, not the ends' noise).
    wu = (ndtr((U + L0[:, None] / 2) / s0[:, None]) - ndtr((U - L0[:, None] / 2) / s0[:, None])) * mu
    A = np.einsum("mvu,mu->mv", S, wu) * step
    lo_s, hi_s = c["sigma_range"]
    tiny = 1e-9

    def across_fun(p, rows):
        mod, d = _across(V[rows], p[:, 0:1], p[:, 1:2], p[:, 2:3])
        return mod * mv[rows], np.stack(d, axis=-1) * mv[rows][..., None]

    pa0 = np.column_stack([np.maximum(A.sum(1) * step, tiny), np.zeros(m), np.clip(s0, lo_s, hi_s)])
    lo_a = np.column_stack([np.full(m, tiny), -hw, np.full(m, lo_s)])
    hi_a = np.column_stack([np.full(m, np.inf), hw, np.full(m, hi_s)])
    pa = _lm(across_fun, pa0, A, lo_a, hi_a, c["across_iter"]) if c["across_iter"] > 0 else pa0
    # Along profile, weighted across by that Gaussian (the matched filter).
    wv = np.exp(-0.5 * ((V - pa[:, 1:2]) / pa[:, 2:3]) ** 2) * mv
    P = np.einsum("mvu,mv->mu", S, wv) * step
    y = np.concatenate([P, A], axis=1)

    def joint_fun(p, rows, lam=None):
        # Parameters: F, c, L, s (along), FA, v0 (across; s shared), and k with a prior of
        # weight lam (the brightness change along the streak) when there are seven.
        npar = p.shape[1]
        F, cc, L, s, FA, v0 = (p[:, j:j + 1] for j in range(6))
        mu_r, mv_r = mu[rows], mv[rows]
        mb, db = _along(U[rows], F, cc, L, s, p[:, 6:7] if npar == 7 else None)
        ma, da = _across(V[rows], FA, v0, s)
        mod = np.concatenate([mb * mu_r, ma * mv_r], axis=1)
        J = np.zeros((rows.size, nu + nv, npar))
        for j in range(len(db)):
            J[:, :nu, (0, 1, 2, 3, 6)[j]] = db[j] * mu_r
        J[:, nu:, 4] = da[0] * mv_r
        J[:, nu:, 5] = da[1] * mv_r
        J[:, nu:, 3] = da[2] * mv_r
        if lam is not None:
            mod = np.concatenate([mod, lam[rows, None] * p[:, 6:7]], axis=1)
            Jp = np.zeros((rows.size, 1, npar))
            Jp[:, 0, 6] = lam[rows]
            J = np.concatenate([J, Jp], axis=1)
        return mod, J

    p0 = np.column_stack([np.maximum(P.sum(1) * step, tiny), np.zeros(m), np.clip(L0, 0.5, 2 * hl), pa[:, 2],
                          pa[:, 0], pa[:, 1]])
    lo = np.column_stack([np.full(m, tiny), -hl, np.zeros(m), np.full(m, lo_s), np.full(m, tiny), -hw])
    hi = np.column_stack([np.full(m, np.inf), hl, 2 * hl, np.full(m, hi_s), np.full(m, np.inf), hw])
    p = _lm(joint_fun, p0, y, lo, hi, c["max_iter"])
    if ramp:
        # The prior's weight is the along profile's residual noise in the fit without k.
        rP = (y - joint_fun(p, np.arange(m))[0])[:, :nu]
        lam = np.sqrt((rP * rP).sum(1) / np.maximum(mu.sum(1) - 4, 1)) / c["ramp_sigma"]
        p = _lm(lambda q, rows: joint_fun(q, rows, lam), np.column_stack([p, np.zeros(m)]),
                np.concatenate([y, np.zeros((m, 1))], axis=1), np.column_stack([lo, np.full(m, -2.0)]),
                np.column_stack([hi, np.full(m, 2.0)]), c["max_iter"])
    F, cc, L, s = p[:, 0], p[:, 1], p[:, 2], p[:, 3]
    ok = (valid & np.all(np.isfinite(p), axis=1) & (F > 2 * tiny) & (p[:, 4] > 2 * tiny)
          & (s > lo_s * 1.01) & (s < hi_s * 0.99) & (np.abs(cc) + L / 2 <= hl))
    return {"p": p, "ok": ok, "S": S, "U": U, "V": V}


def _axis_turn(r: dict, max_turn: float) -> tuple[np.ndarray, np.ndarray]:
    """Angle between the fitted axis and the line through the across centroids of the
    streak's two halves (signed residual within 2 s of the axis). Returns (turn, usable)."""
    p, S, U, V = r["p"], r["S"], r["U"], r["V"]
    cc, L, s, v0 = p[:, 1], p[:, 2], p[:, 3], p[:, 5]
    band = (np.abs(V - v0[:, None]) <= 2 * s[:, None])[:, :, None]
    out = []
    for lo_u, hi_u in ((cc - L / 2, cc), (cc, cc + L / 2)):
        w = np.where(band & ((U >= lo_u[:, None]) & (U <= hi_u[:, None]))[:, None, :], S, 0.0)
        f = w.sum(axis=(1, 2))
        with np.errstate(invalid="ignore", divide="ignore"):
            out.append((f, (w.sum(axis=1) * U).sum(1) / f, (w.sum(axis=2) * V).sum(1) / f))
    (fb, ub, vb), (ff, uf, vf) = out
    with np.errstate(invalid="ignore"):
        turn = np.arctan2(vf - vb, uf - ub)
    usable = r["ok"] & (L > 2 * s) & (fb > 0) & (ff > 0) & np.isfinite(turn) & (np.abs(turn) <= max_turn)
    return np.where(usable, turn, 0.0), usable


def erf_streaks(det: Detections, state: DetectorState, cfg: dict) -> Detections:
    """Streak lengths from a two-edge (error function) profile fit; see the module notes."""
    if len(det) == 0 or state.luma is None or state.background is None:
        return det
    c = _erf_cfg(cfg)
    L_in = np.asarray(det.length, np.float64)
    use = np.flatnonzero(np.isfinite(det.x) & np.isfinite(det.y) & np.isfinite(det.theta) & np.isfinite(L_in))
    if use.size == 0:
        return det
    L0 = np.maximum(L_in[use], 0.0)
    s0 = np.sqrt(np.maximum(np.nan_to_num(det.lam2[use].astype(np.float64)), c["min_sigma"] ** 2))
    hl = np.minimum(c["reach"] * L0 / 2 + c["margin"] * s0, c["max_half_length"])
    # Detections of similar window length are fitted together (the arrays are padded to
    # the longest window of a group).
    order = np.argsort(hl, kind="stable")
    images = _frame_images(state, c["gamma"])
    L_out, s_out, th_out = L_in[use].copy(), np.full(use.size, np.nan), det.theta[use].astype(np.float64)
    done = np.zeros(use.size, bool)
    start = 0
    while start < order.size:
        stop = start + 1
        while stop < order.size and hl[order[stop]] <= 1.5 * hl[order[start]] + 2.0:
            stop += 1
        g = order[start:stop]
        i = use[g]
        res = _erf_group(images, c, det.x[i].astype(np.float64), det.y[i].astype(np.float64),
                         det.theta[i].astype(np.float64), L0[g], s0[g], hl[g])
        L_out[g], s_out[g], th_out[g], done[g] = res
        start = stop
    length = L_in.copy()
    width = np.asarray(det.width, np.float64).copy()
    theta = np.asarray(det.theta, np.float64).copy()
    length[use] = L_out
    width[use] = np.where(done, 4.0 * s_out, width[use])
    theta[use] = np.where(done, (th_out + np.pi / 2) % np.pi - np.pi / 2, theta[use])
    return replace(det, length=length, width=width, theta=theta)


def _erf_group(images, c, xc, yc, th, L0, s0, hl):
    """Fit one group of detections, with the window iteration. Returns the lengths (the
    input length where no pass gave a valid fit), PSF sigmas, axis angles and the mask of
    valid fits."""
    hw = c["half_width"] * s0
    n_iter = max(c["iterations"], 1)
    L_out, s_out, th_out = L0.copy(), np.full(xc.size, np.nan), th.copy()
    done = np.zeros(xc.size, bool)
    for it in range(n_iter):
        last = it == n_iter - 1
        r = _fit_pass(images, c, xc, yc, th, L0, s0, hl, hw, c["ramp_sigma"] > 0 and last)
        p, ok = r["p"], r["ok"]
        L_out = np.where(ok, p[:, 2], L_out)
        s_out = np.where(ok, p[:, 3], s_out)
        th_out = np.where(ok, th, th_out)
        done |= ok
        if last:
            break
        # The next window is centred on the fit, long enough for the fitted length, and its
        # axis is turned towards the across centroids of the streak's two halves.
        turn, _ = _axis_turn(r, c["max_turn"])
        cc, v0 = p[:, 1], p[:, 5]
        xc = np.where(ok, xc + cc * np.cos(th) - v0 * np.sin(th), xc)
        yc = np.where(ok, yc + cc * np.sin(th) + v0 * np.cos(th), yc)
        th = th + turn
        L0 = np.where(ok, p[:, 2], L0)
        s0 = np.where(ok, np.maximum(p[:, 3], c["min_sigma"]), s0)
        hl = np.where(ok, np.minimum(L0 / 2 + c["margin"] * s0, c["max_half_length"]), hl)
        hw = np.where(ok, c["half_width"] * s0, hw)
    return L_out, s_out, th_out, done


def streak_method(cfg: dict) -> str | None:
    """The file-mode streak method the config asks for: "erf", "moments_refined", or None
    for the detector's moments as they are."""
    s = cfg.get("detect", {}).get("streaks", {})
    method = str(s.get("method", "moments"))
    if method == "erf":
        return "erf"
    if method != "moments":
        raise ValueError(f"unknown detect.streaks.method {method!r} (moments or erf)")
    return "moments_refined" if bool(s.get("refine", False)) else None


def measure_streaks(det: Detections, state: DetectorState, cfg: dict) -> Detections:
    """Apply the configured file-mode streak method (`streak_method`)."""
    method = streak_method(cfg)
    if method == "erf":
        return erf_streaks(det, state, cfg)
    if method == "moments_refined":
        return refine_streaks(det, state, cfg)
    return det
