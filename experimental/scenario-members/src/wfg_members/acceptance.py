"""Mission-level acceptance rules and reporting statistics (Contract D).

Rules (recorded in `settings["acceptance"]`):
  all      the journey must pass in every retained member (the frozen rule; default);
  k_of_m   the journey must pass in members carrying at least the fraction k/m of the retained weight, i.e. 1 - alpha
           with alpha = 1 - k/m. With equal weights this is "at least k of the m members". Weights are the redistributed
           scenario-reduction weights q_j, never silently 1/K.

All comparisons use exact rationals. `cvar` is the empirical conditional value at risk of member arrival times
(Rockafellar and Uryasev 2000, Journal of Risk 2(3):21-41): the weighted mean of the worst alpha fraction of the
distribution, with a member in which the journey is not admissible counted at the horizon. It is a reporting quantity;
no search here minimises it (the minimax arrival over scenarios is NP-hard even for two scenarios, Yu and Yang 1998,
Computers and Operations Research 25(6):457-468).
"""
from __future__ import annotations

from fractions import Fraction as F
import math


def as_fraction(w):
    return w if isinstance(w, F) else F(w)


def normalise_weights(weights):
    w = [as_fraction(x) for x in weights]
    total = sum(w)
    if total <= 0 or any(x < 0 for x in w):
        raise ValueError("nonnegative weights with positive total required")
    return [x / total for x in w]


def required_fraction(rule):
    if rule["rule"] == "all":
        return F(1)
    if rule["rule"] == "k_of_m":
        k, m = int(rule["k"]), int(rule["m"])
        if not 1 <= k <= m:
            raise ValueError("1 <= k <= m required")
        return F(k, m)
    raise ValueError("unknown acceptance rule %r" % rule["rule"])


def k_of_m_rule(m, fraction=0.9):
    """The prompt's k = ceil(fraction * m) rule (e.g. k = ceil(0.9 m))."""
    return {"rule": "k_of_m", "k": int(math.ceil(F(str(fraction)) * m)), "m": int(m)}


def passes(flags, weights, rule):
    """True iff the journey passes the mission rule given per-member pass flags."""
    w = normalise_weights(weights)
    if len(flags) != len(w):
        raise ValueError("one flag per member")
    if rule["rule"] == "all":
        return all(flags)
    return sum(x for x, ok in zip(w, flags) if ok) >= required_fraction(rule)


def passing_weight(flags, weights):
    w = normalise_weights(weights)
    return sum(x for x, ok in zip(w, flags) if ok)


def cvar(values, weights, alpha):
    """Weighted mean of the worst (largest) alpha fraction; alpha in (0, 1]. alpha -> 0 gives the maximum."""
    w = normalise_weights(weights)
    pairs = sorted(zip((F(v) for v in values), w), key=lambda p: p[0], reverse=True)
    alpha = as_fraction(alpha)
    if alpha <= 0:
        return float(pairs[0][0])
    if alpha > 1:
        raise ValueError("alpha must lie in (0, 1]")
    left, acc = alpha, F(0)
    for v, p in pairs:
        take = min(p, left)
        acc += take * v
        left -= take
        if left <= 0:
            break
    return float(acc / alpha)


def member_arrivals(arrival, flags, horizon):
    return [float(arrival) if ok and arrival is not None else float(horizon) for ok in flags]
