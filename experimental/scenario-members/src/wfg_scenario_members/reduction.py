"""Finite empirical scenario reduction with deterministic tie breaking.

    Greedy forward selection minimizes sum_i p_i min_j c(i,j), following
    Dupacova et al. (2003), Mathematical Programming 95, 493-511 and Heitsch
    and Romisch (2003), Computational Optimization and Applications 24,187-206.
    Added corridor extremes are heuristics, not a conservatism theorem.
"""
import numpy as np


def distances(first_burn_hour, *, horizon_hours, method="l1", road_weights=None,
              edge_arrival_s=None, edge_lengths_m=None, fixed_hour=1):
    a = np.asarray(first_burn_hour)
    if a.ndim != 3 or a.dtype.kind not in "iu" or (a == -2).any():
        raise ValueError("Distance requires complete known trajectory fields")
    cap = horizon_hours + 1
    if method == "edge_arrival":
        x = np.asarray(edge_arrival_s, dtype=float)
        w = np.asarray(edge_lengths_m, dtype=float)
        if x.ndim != 2 or x.shape[0] != len(a) or w.shape != (x.shape[1],) or not np.isfinite(w).all() or (w < 0).any():
            raise ValueError("Edge arrival/length shape or weight")
        x = np.minimum(x, horizon_hours * 3600)
    elif method == "l1":
        x = np.where(a < 0, cap, a).reshape(len(a), -1).astype(float)
        w = np.ones(x.shape[1])
    elif method == "road_symmetric_difference":
        x = ((a >= 0) & (a <= fixed_hour)).reshape(len(a), -1).astype(float)
        if road_weights is None:
            raise ValueError("Road weights required")
        w = np.asarray(road_weights, dtype=float).ravel()
        if w.shape != (x.shape[1],) or not np.isfinite(w).all() or (w < 0).any():
            raise ValueError("Road weight shape/range")
    else:
        raise ValueError("Unknown distance")
    if not np.isfinite(x).all():
        raise ValueError("Invalid distance features")
    d = np.zeros((len(a), len(a)))
    for i in range(len(a)):
        d[i] = (np.abs(x - x[i]) * w).sum(axis=1)
    return d


def reduce_scenarios(distance_matrix, k, *, method="forward_selection", probabilities=None,
                     extreme_indices=(), max_iterations=100):
    d = np.asarray(distance_matrix, dtype=float)
    n = len(d)
    if d.shape != (n, n) or not np.isfinite(d).all() or (d < 0).any() or not np.allclose(d, d.T) or not np.allclose(np.diag(d), 0):
        raise ValueError("Finite symmetric distance matrix with zero diagonal required")
    if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= n:
        raise ValueError("Invalid k")
    p = np.ones(n) / n if probabilities is None else np.asarray(probabilities, dtype=float)
    if p.shape != (n,) or not np.isfinite(p).all() or (p < 0).any() or p.sum() <= 0:
        raise ValueError("Invalid probabilities")
    p = p / p.sum()
    if method == "first_k":
        kept = list(range(k))
    elif method in ("forward_selection", "k_medoids"):
        kept, nearest = [], np.full(n, np.inf)
        for _ in range(k):
            candidates = [i for i in range(n) if i not in kept]
            costs = [float(np.minimum(nearest, d[:, j]) @ p) for j in candidates]
            chosen = candidates[int(np.argmin(costs))]
            kept.append(chosen)
            nearest = np.minimum(nearest, d[:, chosen])
        if method == "k_medoids":
            for _ in range(max_iterations):
                base = float(np.min(d[:, kept], axis=1) @ p)
                best, new = base, None
                for slot in range(k):
                    for candidate in range(n):
                        if candidate in kept:
                            continue
                        trial = kept.copy(); trial[slot] = candidate
                        cost = float(np.min(d[:, trial], axis=1) @ p)
                        if cost < best - 1e-12:
                            best, new = cost, trial
                if new is None:
                    break
                kept = new
    else:
        raise ValueError("Unknown reduction method")
    for index in extreme_indices:
        if isinstance(index, bool) or not isinstance(index, (int, np.integer)) or not 0 <= index < n:
            raise ValueError("Invalid corridor extreme")
        if int(index) not in kept:
            kept.append(int(index))
    assignment = np.argmin(d[:, kept], axis=1)
    # Give an exact duplicate medoid its own atom, avoiding zero-weight retained
    # scenarios while preserving the same optimal nearest-distance cost.
    for j, i in enumerate(kept):
        assignment[i] = j
    weights = np.bincount(assignment, weights=p, minlength=len(kept))
    return {"selected_indices": kept, "weights": weights.tolist(),
            "assignment": assignment.tolist(), "reduction_cost": float(np.min(d[:, kept], axis=1) @ p),
            "requested_k": k, "retained_count": len(kept), "method": method,
            "extremes_are_not_conservatism_proof": True}
