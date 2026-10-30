"""Empirical weighted acceptance and upper-tail CVaR, not calibrated risk."""
import math
from fractions import Fraction
import numpy as np


def _weights(weights, length):
    q = np.asarray(weights, dtype=float)
    if q.shape != (length,) or not np.isfinite(q).all() or (q < 0).any() or not (q > 0).any():
        raise ValueError("Invalid scenario weights")
    positive = q > 0
    q = q / q.max()
    q = q / q.sum()
    if (positive & (q == 0)).any():
        raise ValueError("Scenario weight dynamic range underflows normalized mass")
    return q


def accept(passed, *, rule="all", k=None, m=None, weights=None):
    flags = list(passed)
    if not flags or any(x is not None and not isinstance(x, (bool, np.bool_)) for x in flags):
        raise ValueError("Members require true/false/unknown")
    m = len(flags) if m is None else m
    if m != len(flags) or isinstance(m, bool):
        raise ValueError("Member count mismatch")
    q = _weights(np.ones(m) if weights is None else weights, m)
    raw = np.ones(m) if weights is None else np.asarray(weights, dtype=float)
    exact = [Fraction(float(w)) for w in raw]
    mass = sum(exact, Fraction(0))
    exact = [w / mass for w in exact]
    if rule == "all":
        threshold = Fraction(1)
    elif rule == "k_of_m" and isinstance(k, int) and not isinstance(k, bool) and 1 <= k <= m:
        threshold = Fraction(k, m)
    else:
        raise ValueError("Invalid acceptance rule")
    # Explicit uncertainty interval, never silently count unknown as passing.
    lower = sum((w for x, w in zip(flags, exact) if x is True or isinstance(x, np.bool_) and x), Fraction(0))
    upper = lower + sum((w for x, w in zip(flags, exact) if x is None), Fraction(0))
    if lower >= threshold:
        outcome = "checked_route"
    elif upper < threshold:
        outcome = "rejected_candidate"
    else:
        outcome = "unresolved"
    return {"outcome": outcome, "retained_pass_weight": float(lower), "possible_pass_weight": float(upper),
            "retained_pass_weight_exact": str(lower), "possible_pass_weight_exact": str(upper),
            "acceptance": {"rule": rule, "k": m if rule == "all" else k, "m": m},
            "threshold_weight": float(threshold), "threshold_weight_exact": str(threshold), "weights": q.tolist(),
            "interpretation": "empirical retained scenario weight, not a population probability"}


def weighted_cvar(arrivals, weights, *, alpha, horizon):
    """Mean of worst alpha mass, splitting the boundary atom exactly as needed.

    Rockafellar and Uryasev (2000), Journal of Risk 2(3), 21-41. Here alpha is
    upper-tail mass, not the paper's confidence-level parameter 1-alpha.
    """
    if isinstance(alpha, bool) or not 0 < alpha <= 1 or not math.isfinite(horizon) or horizon < 0:
        raise ValueError("Invalid CVaR controls")
    a = np.asarray([horizon if x is None else x for x in arrivals], dtype=float)
    if a.ndim != 1 or not len(a) or not np.isfinite(a).all() or (a < 0).any():
        raise ValueError("Invalid arrival")
    _weights(weights, len(a))  # validates representable normalized masses
    exact = [Fraction(float(w)) for w in weights]
    denominator = sum(exact, Fraction(0))
    q = [w / denominator for w in exact]
    tail = Fraction(float(alpha))
    left, total = tail, Fraction(0)
    for index in np.argsort(-a, kind="stable"):
        mass = min(left, q[index])
        total += mass * Fraction(float(a[index]))
        left -= mass
        if left <= 0:
            break
    return float(total / tail)
