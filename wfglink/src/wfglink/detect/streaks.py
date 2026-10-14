"""Streak refinement for file mode: moments in an oriented window along each streak.

The detector measures each blob's second moments inside its thresholded component. A long,
faint streak spreads its light thinly, so its ends fall below the threshold and the
window cuts them off: the length comes out short (by about a fifth at 10 to 20 px on the
synthetic core suite). A short streak has the opposite problem, because its window is
mostly noise and blur. Refinement recomputes the moments of the signed residual, with no
threshold, inside a rectangle along the first estimate's axis that reaches
streaks.margin_sigma PSF widths beyond the ends and to each side, and repeats
streaks.iterations times. A refinement that moves the centroid more than half the length,
or changes the length by more than streaks.max_change, is discarded (a neighbour in the
window, or noise), and the first estimate stays.

Off in live mode (cost); on in file mode and validation.
"""
from __future__ import annotations

import math
from dataclasses import replace

import numpy as np

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
