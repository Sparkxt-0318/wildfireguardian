"""Statistics for E3 (no scipy in the Track C stack): Clopper-Pearson intervals, cluster effective sample
sizes, and the scenario-approach bounds.

* ``betainc`` / ``beta_ppf``: regularized incomplete beta (Lentz continued fraction, Numerical Recipes 6.4)
  and its inverse by bisection; non-integer arguments allowed (Korn-Graubard intervals).
* ``clopper_pearson(x, n)``: exact two-sided interval; ``x`` and ``n`` may be non-integer (effective counts).
* ``cluster_ci``: per-resident rate with clusters = (instance, fresh member). Three upper bounds: naive
  (resident-member pairs independent), Korn-Graubard (CP with n_eff = n / deff from the cluster-robust variance
  of the ratio estimator) and Kish (CP with n_eff = (sum n_c)^2 / sum n_c^2, i.e. perfect correlation inside a
  cluster: each cluster counts once, weighted by its residents; the most conservative under this clustering).
* Scenario approach. Campi & Garatti (2008), a priori, convex programs with d decision variables:
  P{V > eps} <= sum_{i<d} C(K,i) eps^i (1-eps)^(K-i), and E[V] <= d/(K+1). Campi & Garatti (2018,
  "wait-and-judge", convex and non-degenerate): eps(k) = 1 - t(k), t(k) the root in (0,1) of
  beta/(K+1) sum_{i=k}^{K} C(i,k) t^(i-k) - C(K,k) t^(K-k) = 0, with k the observed number of support
  scenarios. Campi, Garatti & Ramponi (2018, non-convex decisions, any algorithm with a compression set of
  size k): eps(k) = 1 - (beta / (K C(K,k)))^(1/(K-k)) for k < K, eps(K) = 1.
"""
from __future__ import annotations

import math

import numpy as np


# ------------------------------------------------------------------------- incomplete beta
def _betacf(a: float, b: float, x: float) -> float:
    tiny, eps = 1e-300, 1e-15
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 200_000):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            return h
    raise ArithmeticError(f"betacf did not converge (a={a}, b={b}, x={x})")


def betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a, b) for a, b > 0, 0 <= x <= 1."""
    if not (a > 0 and b > 0):
        raise ValueError("a and b must be > 0")
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbt = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(lbt) * _betacf(a, b, x) / a
    return 1.0 - math.exp(lbt) * _betacf(b, a, 1.0 - x) / b


def beta_ppf(q: float, a: float, b: float) -> float:
    """Inverse of I_x(a, b) in x (bisection to 1e-12)."""
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if betainc(a, b, mid) < q:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-12:
            break
    return 0.5 * (lo + hi)


def clopper_pearson(x: float, n: float, conf: float = 0.95) -> tuple[float, float]:
    """Exact two-sided interval for a binomial proportion; x, n may be non-integer (effective counts)."""
    if n <= 0:
        return (math.nan, math.nan)
    x = min(max(float(x), 0.0), float(n))
    a = (1.0 - conf) / 2.0
    lo = 0.0 if x <= 0 else beta_ppf(a, x, n - x + 1.0)
    hi = 1.0 if x >= n else beta_ppf(1.0 - a, x + 1.0, n - x)
    return lo, hi


# ------------------------------------------------------------------------- cluster intervals
def cluster_ci(x_c, n_c, pairs: float | None = None, conf: float = 0.95) -> dict:
    """Weighted rate sum(x_c) / sum(n_c) over independent clusters c (e.g. instance x fresh member; ``x_c`` and
    ``n_c`` may carry weights), with three Clopper-Pearson intervals: naive (``pairs`` resident-member pairs taken
    as independent; reference only), Korn-Graubard (effective n = p(1-p) / v, v the cluster-robust variance of the
    ratio estimator, capped at ``pairs``) and Kish (effective n = (sum n_c)^2 / sum n_c^2: perfect correlation
    inside a cluster, the most conservative under this clustering). With no failure (or all failing) there is no
    variance estimate and Korn-Graubard falls back to Kish. Clusters with n_c = 0 are ignored."""
    x_c = np.asarray(x_c, dtype=float)
    n_c = np.asarray(n_c, dtype=float)
    keep = n_c > 0
    x_c, n_c = x_c[keep], n_c[keep]
    C = int(x_c.size)
    n, x = float(n_c.sum()), float(x_c.sum())
    pairs = float(pairs) if pairs is not None else n
    out = {"clusters": C, "pairs": pairs, "rate": math.nan}
    nan_keys = ("naive_lo", "naive_hi", "kg_lo", "kg_hi", "kish_lo", "kish_hi", "n_eff_kg", "n_eff_kish", "deff")
    if n <= 0:
        out.update({k: math.nan for k in nan_keys})
        return out
    p = x / n
    out["rate"] = p
    out["violations"] = p * pairs
    out["naive_lo"], out["naive_hi"] = clopper_pearson(p * pairs, pairs, conf)
    n_kish = float(n ** 2 / np.sum(n_c ** 2))
    out["n_eff_kish"] = n_kish
    out["kish_lo"], out["kish_hi"] = clopper_pearson(p * n_kish, n_kish, conf)
    var = C / (C - 1.0) * float(np.sum((x_c - p * n_c) ** 2)) / n ** 2 if C > 1 else 0.0
    if 0.0 < p < 1.0 and var > 0:
        n_kg = min(pairs, p * (1.0 - p) / var)
        out["deff"] = pairs / n_kg
        out["n_eff_kg"] = n_kg
        out["kg_lo"], out["kg_hi"] = clopper_pearson(p * n_kg, n_kg, conf)
    else:
        out["deff"] = math.nan
        out["n_eff_kg"] = n_kish
        out["kg_lo"], out["kg_hi"] = out["kish_lo"], out["kish_hi"]
    return out


# ------------------------------------------------------------------------- scenario bounds
def _lbinom(n: int, k: int) -> float:
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def eps_nonconvex(k: int, K: int, beta: float) -> float:
    """Campi, Garatti & Ramponi (2018): violation level guaranteed with confidence 1 - beta for a decision with
    a compression (support) set of k out of K i.i.d. scenarios, any decision rule."""
    if k >= K:
        return 1.0
    return 1.0 - math.exp((math.log(beta) - math.log(K) - _lbinom(K, k)) / (K - k))


def eps_wait_and_judge(k: int, K: int, beta: float) -> float:
    """Campi & Garatti (2018) wait-and-judge level for k support scenarios out of K (convex, non-degenerate
    programs): 1 - t(k), t(k) the root in (0, 1) of beta/(K+1) sum_{i=k}^{K} C(i,k) t^(i-k) = C(K,k) t^(K-k)."""
    if k >= K:
        return 1.0

    def f(t: float) -> float:
        s = sum(math.exp(_lbinom(i, k) + (i - k) * math.log(t)) for i in range(k, K + 1))
        return beta / (K + 1.0) * s - math.exp(_lbinom(K, k) + (K - k) * math.log(t))

    lo, hi = 1e-300, 1.0 - 1e-15
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if f(mid) > 0:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-14:
            break
    return 1.0 - 0.5 * (lo + hi)


def eps_a_priori(d: int, K: int, beta: float) -> float:
    """Campi & Garatti (2008): the smallest eps with sum_{i<d} C(K,i) eps^i (1-eps)^(K-i) <= beta (convex
    programs with d decision variables; 1 if d >= K)."""
    if d >= K:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        tail = betainc(d, K - d + 1, mid) if d > 0 else 1.0     # P{Bin(K, mid) >= d} = I_mid(d, K-d+1)
        if 1.0 - tail > beta:                                   # P{Bin(K, mid) <= d-1} > beta: eps too small
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-12:
            break
    return hi
