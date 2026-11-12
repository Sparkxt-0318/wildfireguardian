"""Conformal risk control for warning zones (A1 §5.4, revision 27; DEVELOPMENT-ONLY).

Warning zone for threshold t: Z_t = {scored cells with p >= t}. The loss of one fire is its
false-negative rate, FNR_f(t) = (#positives with p < t) / (#positives), pooled over that fire's
intervals; it lies in [0, 1] and is non-decreasing in t. Fires are the exchangeable unit.

Calibration (Angelopoulos et al., conformal risk control, with bound B = 1): on n calibration
fires choose
    t_hat = max { t in T : n/(n+1) * mean_f FNR_f(t) + 1/(n+1) <= alpha },
where T is 0 plus every positive's probability on the calibration fires (FNR changes only
there). If no t > 0 qualifies, t_hat = 0 and the zone is the whole scored domain (the
procedure is then uninformative at that alpha and n). Under exchangeability of fires,
E[FNR_test(t_hat)] <= alpha.

Feasibility is arithmetic, fixed before any data: a non-trivial zone needs
mean FNR <= (alpha (n+1) - 1) / n, which is negative (infeasible) when alpha < 1/(n+1).
"""

from __future__ import annotations

import numpy as np


def fire_fnr(pos_p_sorted: np.ndarray, t: np.ndarray) -> np.ndarray:
    """FNR at thresholds t for one fire, given its positives' probabilities sorted ascending."""
    if len(pos_p_sorted) == 0:
        raise ValueError("a calibration fire must have at least one positive")
    return np.searchsorted(pos_p_sorted, t, side="left") / len(pos_p_sorted)


def calibrate(pos_by_fire: list[np.ndarray], alpha: float) -> dict:
    n = len(pos_by_fire)
    if n < 1 or not 0 < alpha < 1:
        raise ValueError("need at least one calibration fire and 0 < alpha < 1")
    sorted_pos = [np.sort(np.asarray(p, dtype=np.float64)) for p in pos_by_fire]
    cand = np.unique(np.concatenate([[0.0]] + sorted_pos))
    risk = np.mean([fire_fnr(p, cand) for p in sorted_pos], axis=0)
    adjusted = n / (n + 1) * risk + 1 / (n + 1)
    ok = adjusted <= alpha
    feasible = bool(ok[cand > 0].any())
    t = float(cand[ok].max()) if ok.any() else 0.0
    return dict(threshold=t if feasible else 0.0, feasible=feasible, n_calibration_fires=n, alpha=alpha,
                calibration_mean_fnr=float(np.mean([fire_fnr(p, np.array([t]))[0] for p in sorted_pos]))
                if feasible else 0.0,
                required_mean_fnr=(alpha * (n + 1) - 1) / n)


def evaluate(p: np.ndarray, y: np.ndarray, interval: np.ndarray, t: float) -> dict:
    """Held-out FNR and zone size for one fire at threshold t (zone = p >= t)."""
    p, y = np.asarray(p, float), np.asarray(y, float)
    zone = p >= t
    pos = y == 1
    per_interval = np.bincount(np.unique(interval, return_inverse=True)[1], weights=zone.astype(float))
    return dict(threshold=t, positives=int(pos.sum()),
                fnr=float((~zone & pos).sum() / pos.sum()) if pos.any() else None,
                zone_cells_mean_per_interval=float(per_interval.mean()),
                zone_share_of_scored=float(zone.mean()),
                precision=float((zone & pos).sum() / zone.sum()) if zone.any() else None)


def leave_one_fire_out(fires: np.ndarray, p: np.ndarray, y: np.ndarray, interval: np.ndarray,
                       alpha: float) -> dict:
    names = sorted(np.unique(fires).tolist())
    rows = {}
    for held in names:
        cal = [p[(fires == f) & (y == 1)] for f in names if f != held]
        c = calibrate(cal, alpha)
        m = fires == held
        rows[held] = dict(calibration=c, held_out=evaluate(p[m], y[m], interval[m], c["threshold"]))
    fnrs = [r["held_out"]["fnr"] for r in rows.values() if r["held_out"]["fnr"] is not None]
    feas = [r for r in rows.values() if r["calibration"]["feasible"]]
    feas_fnr = [r["held_out"]["fnr"] for r in feas if r["held_out"]["fnr"] is not None]
    # "all folds" averages count an infeasible fold as FNR 0 and zone 1 (the whole domain); the
    # feasible-only means exclude those uninformative folds (Hannah's note). Report both.
    return dict(alpha=alpha, folds=len(names), per_fire=rows,
                mean_held_out_fnr=float(np.mean(fnrs)) if fnrs else None,
                mean_zone_share=float(np.mean([r["held_out"]["zone_share_of_scored"] for r in rows.values()])),
                folds_feasible=len(feas),
                mean_held_out_fnr_feasible_only=float(np.mean(feas_fnr)) if feas_fnr else None,
                mean_zone_share_feasible_only=float(np.mean([r["held_out"]["zone_share_of_scored"] for r in feas]))
                if feas else None)
