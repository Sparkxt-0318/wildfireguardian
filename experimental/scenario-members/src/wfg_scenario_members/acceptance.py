"""Empirical weighted acceptance and upper-tail CVaR, not calibrated risk."""
import math
import numpy as np


def _weights(weights, length):
    q = np.asarray(weights, dtype=float)
    if q.shape != (length,) or not np.isfinite(q).all() or (q < 0).any() or q.sum() <= 0:
        raise ValueError("Invalid scenario weights")
    return q / q.sum()


def accept(passed, *, rule="all", k=None, m=None, weights=None):
    flags = list(passed)
    if not flags or any(x is not None and not isinstance(x, (bool, np.bool_)) for x in flags):
        raise ValueError("Members require true/false/unknown")
    m = len(flags) if m is None else m
    if m != len(flags) or isinstance(m, bool):
        raise ValueError("Member count mismatch")
    q = _weights(np.ones(m) if weights is None else weights, m)
    if rule == "all":
        threshold = 1.0
    elif rule == "k_of_m" and isinstance(k, int) and not isinstance(k, bool) and 1 <= k <= m:
        threshold = k / m
    else:
        raise ValueError("Invalid acceptance rule")
    # Explicit uncertainty interval, never silently count unknown as passing.
    lower = math.fsum(float(w) for x, w in zip(flags, q) if x is True or isinstance(x, np.bool_) and x)
    upper = lower + math.fsum(float(w) for x, w in zip(flags, q) if x is None)
    if lower >= threshold or math.isclose(lower, threshold, rel_tol=0, abs_tol=2e-15):
        outcome = "checked_route"
    elif upper < threshold and not math.isclose(upper, threshold, rel_tol=0, abs_tol=2e-15):
        outcome = "rejected_candidate"
    else:
        outcome = "unresolved"
    return {"outcome": outcome, "retained_pass_weight": lower, "possible_pass_weight": upper,
            "acceptance": {"rule": rule, "k": m if rule == "all" else k, "m": m},
            "threshold_weight": threshold, "weights": q.tolist(),
            "interpretation": "empirical retained scenario weight, not a population probability"}


def weighted_cvar(arrivals, weights, *, alpha, horizon):
    """Mean of worst alpha mass, splitting the boundary atom exactly as needed.

    Rockafellar and Uryasev (2000), Journal of Risk 2(3), 21-41. Here alpha is
    upper-tail mass, not the paper's confidence-level parameter 1-alpha.
    """
    if not 0 < alpha <= 1 or not math.isfinite(horizon):
        raise ValueError("Invalid CVaR controls")
    a = np.asarray([horizon if x is None else x for x in arrivals], dtype=float)
    if not np.isfinite(a).all() or (a < 0).any():
        raise ValueError("Invalid arrival")
    q = _weights(weights, len(a))
    left, total = float(alpha), 0.0
    for index in np.argsort(-a, kind="stable"):
        mass = min(left, float(q[index]))
        total += mass * float(a[index])
        left -= mass
        if left <= 1e-15:
            break
    return total / alpha
