"""Per-cell assimilation features built from STRICTLY PRIOR observations.

Sign conventions follow ``spread_v2.features`` exactly so the two feature sets
describe the same geometry:

    east  = (col - col0) * cell_size_m
    north = (row0 - row) * cell_size_m        # row index increases southward

Every function here takes the full overpass list plus the index ``k`` of the
prediction time and slices to ``overpasses[:k]`` as its first act. Nothing
downstream of that slice can see the present or the future.
"""

from __future__ import annotations

import numpy as np

#: Ordered Arm D feature columns, appended after the 16 Arm A columns.
ARM_D_FEATURE_COLUMNS: tuple[str, ...] = (
    "obs_spread_dist_m",        # centroid displacement magnitude, last two priors
    "obs_spread_speed_mps",     # that displacement divided by its own elapsed time
    "obs_alignment",            # cos(cell bearing-from-prior-front, observed spread bearing)
    "obs_staleness_h",          # t - time of the most recent prior overpass
    "dist_to_prior_active_m",   # distance to the nearest strictly-prior detection
    "obs_front_persistence",    # share of the last N priors active near this cell
    "n_prior_overpasses",       # how much history exists at all (cold-start indicator)
)

#: How many prior overpasses the persistence measure looks back over.
ARM_D_PERSISTENCE_N: int = 3

#: Radius within which a prior new-detection counts as "near this cell".
ARM_D_PERSISTENCE_RADIUS_M: float = 1500.0


def _centroid_rc(mask: np.ndarray) -> tuple[float, float] | None:
    """Centroid of a boolean mask in (row, col) units, or None if empty."""
    if not mask.any():
        return None
    rr, cc = np.nonzero(mask)
    return float(rr.mean()), float(cc.mean())


def _distance_to_mask_m(mask: np.ndarray, cell_size_m: float):
    """Euclidean distance (metres) from every cell to the nearest True cell.

    Returns ``(dist_m, src_row, src_col)``; ``(None, None, None)`` if the mask
    is empty, because "distance to nothing" has no honest value.
    """
    from scipy.ndimage import distance_transform_edt

    if not mask.any():
        return None, None, None
    dist_cells, (src_r, src_c) = distance_transform_edt(~mask, return_indices=True)
    return dist_cells * cell_size_m, src_r, src_c


def prior_observation_features(
    overpasses: list,
    k: int,
    rows: np.ndarray,
    cols: np.ndarray,
    *,
    cell_size_m: float,
    persistence_n: int = ARM_D_PERSISTENCE_N,
    persistence_radius_m: float = ARM_D_PERSISTENCE_RADIUS_M,
) -> dict[str, np.ndarray]:
    """Arm D features for candidate cells ``(rows, cols)`` at transition ``k``.

    Parameters
    ----------
    overpasses:
        The full overpass list for one fire. **Only ``overpasses[:k]`` is
        read.** Passing a longer or shorter tail must not change the result;
        ``tests/test_arm_d_leakage.py`` asserts exactly that.
    k:
        Index of the overpass whose time is the prediction time ``t``.
    rows, cols:
        Grid indices of the candidate cells, in the order the caller wants the
        returned arrays.

    Undefined features are NaN, never a filled-in default. ``n_prior_overpasses``
    is always defined and is the flag a reader should use to tell a cold start
    from a real measurement: sklearn's HistGradientBoostingClassifier consumes
    NaN natively, so a degraded slice stays in the dataset and stays visible
    instead of being silently dropped or silently imputed.
    """
    n = len(rows)
    out: dict[str, np.ndarray] = {
        name: np.full(n, np.nan, dtype="float64") for name in ARM_D_FEATURE_COLUMNS
    }

    # ---- THE LEAKAGE BOUNDARY. Nothing below this line may index past it. ----
    priors = list(overpasses[:max(0, int(k))])
    # -------------------------------------------------------------------------

    out["n_prior_overpasses"] = np.full(n, float(len(priors)), dtype="float64")
    if not priors:
        return out

    t = overpasses[k].time
    latest = priors[-1]

    # Observation staleness: how old the freshest usable observation is.
    out["obs_staleness_h"] = np.full(
        n, (t - latest.time).total_seconds() / 3600.0, dtype="float64")

    # Distance to the nearest strictly-prior detection, and the bearing from it.
    dist_m, src_r, src_c = _distance_to_mask_m(latest.cumulative_mask, cell_size_m)
    if dist_m is not None:
        out["dist_to_prior_active_m"] = dist_m[rows, cols].astype("float64")

    # Observed spread vector between the two most recent priors.
    if len(priors) >= 2:
        a, b = priors[-2], priors[-1]
        ca, cb = _centroid_rc(a.cumulative_mask), _centroid_rc(b.cumulative_mask)
        if ca is not None and cb is not None:
            east = (cb[1] - ca[1]) * cell_size_m
            north = (ca[0] - cb[0]) * cell_size_m
            mag = float(np.hypot(east, north))
            out["obs_spread_dist_m"] = np.full(n, mag, dtype="float64")

            dt_s = (b.time - a.time).total_seconds()
            if dt_s > 0:
                out["obs_spread_speed_mps"] = np.full(n, mag / dt_s, dtype="float64")

            # Per-cell alignment with the observed direction of travel. Both
            # vectors are unit-normalised, so this is a cosine in [-1, 1] and is
            # directly comparable to Arm A's `wind_alignment`.
            if mag > 1e-6 and dist_m is not None:
                sx, sy = east / mag, north / mag
                s_r = src_r[rows, cols]
                s_c = src_c[rows, cols]
                ce = (cols - s_c).astype("float64") * cell_size_m
                cn = (s_r - rows).astype("float64") * cell_size_m
                cnorm = np.hypot(ce, cn)
                safe = np.where(cnorm > 1e-6, cnorm, 1.0)
                out["obs_alignment"] = (ce / safe) * sx + (cn / safe) * sy

    # Front persistence over the last N priors: the share of those overpasses
    # that put a NEW detection within `persistence_radius_m` of the cell. A cell
    # the front has repeatedly approached scores high; one it has passed near
    # once does not.
    window = priors[-int(persistence_n):] if persistence_n > 0 else []
    if window:
        hits = np.zeros(n, dtype="float64")
        counted = 0
        for op in window:
            d, _, _ = _distance_to_mask_m(op.new_mask, cell_size_m)
            if d is None:
                continue
            counted += 1
            hits += (d[rows, cols] <= persistence_radius_m).astype("float64")
        if counted:
            out["obs_front_persistence"] = hits / float(counted)

    return out


__all__ = [
    "ARM_D_FEATURE_COLUMNS",
    "ARM_D_PERSISTENCE_N",
    "ARM_D_PERSISTENCE_RADIUS_M",
    "prior_observation_features",
]
