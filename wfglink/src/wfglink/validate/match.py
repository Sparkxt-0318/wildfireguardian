"""One-to-one matching of estimated points to ground-truth points within a radius.

Each ground-truth point carries its own match radius: max(r0, f L) where L is its true
streak length in that frame, r0 is validate.match_radius_px (3 px) and f is
validate.streak_radius_frac (0.5). A streak's centroid can sit anywhere along a dashed
streak, so long streaks get a proportionally larger radius.

The matching is a Hungarian assignment (scipy's linear_sum_assignment) on Euclidean
distance, restricted to pairs within the ground truth's radius. Pairs with only one
possible partner on both sides are matched directly; the rest are solved on the smallest
dense sub-matrix. An invalid pair costs more than any complete set of valid pairs, so
the number of matches is maximised first and the total distance second.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import linear_sum_assignment


def match_radius(streak_length_px: np.ndarray, cfg: dict | None = None,
                 base_px: float | None = None, streak_frac: float | None = None) -> np.ndarray:
    """Per-ground-truth match radius max(base_px, streak_frac * L)."""
    v = (cfg or {}).get("validate", {})
    base = float(v.get("match_radius_px", 3.0)) if base_px is None else float(base_px)
    frac = float(v.get("streak_radius_frac", 0.5)) if streak_frac is None else float(streak_frac)
    length = np.nan_to_num(np.asarray(streak_length_px, dtype=np.float64), nan=0.0)
    return np.maximum(base, frac * length)


def match_points(gt_xy: np.ndarray, det_xy: np.ndarray, radius: float | np.ndarray
                 ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Match detections to ground truth one to one within each truth's radius.

    gt_xy (n, 2), det_xy (m, 2), radius scalar or (n,). Returns (gt_index, det_index,
    distance) of the matched pairs, sorted by gt_index.
    """
    gt_xy = np.asarray(gt_xy, dtype=np.float64).reshape(-1, 2)
    det_xy = np.asarray(det_xy, dtype=np.float64).reshape(-1, 2)
    n, m = gt_xy.shape[0], det_xy.shape[0]
    empty = (np.zeros(0, np.int64), np.zeros(0, np.int64), np.zeros(0))
    if n == 0 or m == 0:
        return empty
    rad = np.broadcast_to(np.asarray(radius, dtype=np.float64), (n,))
    dx = det_xy[None, :, 0] - gt_xy[:, None, 0]
    dy = det_xy[None, :, 1] - gt_xy[:, None, 1]
    dist = np.sqrt(dx * dx + dy * dy)
    rows, cols = np.nonzero(dist <= rad[:, None])
    if rows.size == 0:
        return empty
    cost = dist[rows, cols]
    rc = np.bincount(rows, minlength=n)
    cc = np.bincount(cols, minlength=m)
    simple = (rc[rows] == 1) & (cc[cols] == 1)
    gi, di = rows[simple], cols[simple]
    if not simple.all():
        hard = ~simple
        ur, ir = np.unique(rows[hard], return_inverse=True)
        uc, ic = np.unique(cols[hard], return_inverse=True)
        hc = cost[hard]
        big = (float(hc.max()) + 1.0) * (min(ur.size, uc.size) + 1)
        sub = np.full((ur.size, uc.size), big)
        sub[ir, ic] = hc
        ok_sub = np.zeros(sub.shape, dtype=bool)
        ok_sub[ir, ic] = True
        r, c = linear_sum_assignment(sub)
        ok = ok_sub[r, c]
        gi = np.concatenate((gi, ur[r[ok]]))
        di = np.concatenate((di, uc[c[ok]]))
    order = np.argsort(gi, kind="stable")
    gi, di = gi[order], di[order]
    return gi, di, dist[gi, di]
