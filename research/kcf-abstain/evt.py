#!/usr/bin/env python3
"""Tail question (PROTOCOL.md section 8): GEV on the 28 per-fire maximum 5 h reaches; return period of 40 km.

    python3 evt.py --out derived/evt.json

Per-fire maximum of `reach_km` (5 km rule) at h = 5 over every eligible issue hour, from
kcf-margin/derived/gofer_reach.csv.gz. GEV with shape xi (scipy genextreme uses c = -xi), maximum likelihood.
p40 = P(per-fire maximum > 40 km); T40 = 1 / p40 fires. 95% profile-likelihood intervals for xi and for p40
(p40 profiled directly: mu is solved from F(40) = 1 - p40 for each (xi, sigma)), parametric bootstrap beside them.
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import optimize, stats

HERE = Path(__file__).resolve().parent
REACH = HERE.parent / "kcf-margin/derived/gofer_reach.csv.gz"
Z40 = 40.0
CHI = stats.chi2.ppf(0.95, 1)
BOOT, SEED = 2000, 20261118


def nll(mu, sig, xi, z):
    if sig <= 0:
        return np.inf
    y = (z - mu) / sig
    if abs(xi) < 1e-7:
        return z.size * math.log(sig) + y.sum() + np.exp(-y).sum()
    t = 1 + xi * y
    if np.any(t <= 0):
        return np.inf
    return z.size * math.log(sig) + (1 + 1 / xi) * np.log(t).sum() + (t ** (-1 / xi)).sum()


def fit(z, xi_fixed=None):
    """MLE (mu, sigma, xi); with xi_fixed, profile over (mu, sigma). Several starts, Nelder-Mead."""
    s0 = z.std() * math.sqrt(6) / math.pi
    m0 = z.mean() - 0.5772 * s0
    best = (np.inf, None)
    xis = [xi_fixed] if xi_fixed is not None else [-0.4, -0.2, 0.0, 0.2, 0.4]
    for x0 in xis:
        for sm in (0.6, 1.0, 1.6):
            if xi_fixed is None:
                f = lambda p: nll(p[0], math.exp(p[1]), p[2], z)  # noqa: E731
                r = optimize.minimize(f, [m0, math.log(s0 * sm), x0], method="Nelder-Mead",
                                      options=dict(xatol=1e-9, fatol=1e-10, maxiter=20000, maxfev=40000))
                p = (r.x[0], math.exp(r.x[1]), r.x[2])
            else:
                f = lambda p: nll(p[0], math.exp(p[1]), xi_fixed, z)  # noqa: E731
                r = optimize.minimize(f, [m0, math.log(s0 * sm)], method="Nelder-Mead",
                                      options=dict(xatol=1e-9, fatol=1e-10, maxiter=20000, maxfev=40000))
                p = (r.x[0], math.exp(r.x[1]), xi_fixed)
            if r.fun < best[0]:
                best = (r.fun, p)
    return best


def exceed(z0, mu, sig, xi):
    """P(M > z0) for GEV(mu, sig, xi)."""
    if abs(xi) < 1e-7:
        return 1 - math.exp(-math.exp(-(z0 - mu) / sig))
    t = 1 + xi * (z0 - mu) / sig
    if t <= 0:
        return 0.0 if xi < 0 else 1.0
    return 1 - math.exp(-t ** (-1 / xi))


def profile_p(z, p):
    """Max log-lik with P(M > 40) = p fixed; free (xi, log sigma), mu solved."""
    yp = -math.log(1 - p)

    def mu_of(sig, xi):
        if abs(xi) < 1e-7:
            return Z40 + sig * math.log(yp)
        return Z40 - sig * (yp ** (-xi) - 1) / xi

    def f(q):
        xi, sig = q[0], math.exp(q[1])
        return nll(mu_of(sig, xi), sig, xi, z)

    best = np.inf
    s0 = z.std() * math.sqrt(6) / math.pi
    for x0 in (-0.6, -0.3, -0.1, 0.1, 0.3, 0.6, 1.0):
        for sm in (0.5, 1.0, 2.0):
            r = optimize.minimize(f, [x0, math.log(s0 * sm)], method="Nelder-Mead",
                                  options=dict(xatol=1e-9, fatol=1e-10, maxiter=20000, maxfev=40000))
            best = min(best, r.fun)
    return -best


def n_needed(p):
    if p is None or not np.isfinite(p) or p <= 0:
        return None
    if p >= 1:
        return 1
    return int(math.ceil(math.log(0.05) / math.log(1 - p)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    r = pd.read_csv(REACH)
    mx = r[r.h == 5].groupby("fire").reach_km.max().sort_values()
    z = mx.to_numpy(float)
    f0, (mu, sig, xi) = fit(z)
    ll0 = -f0
    p40 = exceed(Z40, mu, sig, xi)
    upper_end = (mu - sig / xi) if xi < 0 else math.inf

    # profile for xi
    grid = np.round(np.arange(-1.0, 1.5001, 0.01), 2)
    prof_xi = np.array([-fit(z, x)[0] for x in grid])
    inside = grid[2 * (ll0 - prof_xi) <= CHI]
    xi_ci = [float(inside.min()), float(inside.max())]

    # profile for p40
    pg = np.unique(np.r_[np.logspace(-12, math.log10(0.95), 160), [p40] if 0 < p40 < 1 else []])
    prof_p = np.array([profile_p(z, p) for p in pg])
    okp = pg[2 * (ll0 - prof_p) <= CHI]
    lower_reaches_zero = bool(okp.size and okp.min() <= pg.min() * 1.0001)
    p_ci = [0.0 if lower_reaches_zero else float(okp.min()), float(okp.max())] if okp.size else [None, None]

    # parametric bootstrap
    rng = np.random.default_rng(SEED)
    bp = []
    for _ in range(BOOT):
        zs = stats.genextreme.rvs(-xi, loc=mu, scale=sig, size=z.size, random_state=rng)
        _, (m_, s_, x_) = fit(np.sort(zs))
        bp.append(exceed(Z40, m_, s_, x_))
    bp = np.array(bp)
    boot_ci = [float(np.quantile(bp, 0.025)), float(np.quantile(bp, 0.975))]

    finite = (p_ci[0] is not None and p_ci[0] > 0 and p_ci[1] is not None and p_ci[1] < 1)
    T40 = (1 / p40) if p40 > 0 else math.inf
    out = dict(
        data=dict(source="kcf-margin/derived/gofer_reach.csv.gz, h = 5, reach_km (5 km rule), max over each fire's "
                         "eligible issue hours", n_fires=int(z.size), per_fire_max_km={k: float(v) for k, v in mx.items()},
                  largest_km=float(z.max()), extrapolation_ratio_40_over_largest=float(Z40 / z.max()), label="MEASURED"),
        gev_mle=dict(mu=mu, sigma=sig, xi=xi, loglik=ll0, xi_ci95_profile=xi_ci,
                     upper_endpoint_km=upper_end if np.isfinite(upper_end) else None),
        p40=dict(mle=p40, ci95_profile=p_ci, ci95_parametric_bootstrap=boot_ci,
                 bootstrap_share_exactly_zero=float(np.mean(bp == 0)), bootstrap=dict(resamples=BOOT, seed=SEED)),
        T40_fires=dict(mle=T40 if np.isfinite(T40) else None,
                       ci95_profile=[(1 / p_ci[1]) if p_ci[1] else None, (1 / p_ci[0]) if p_ci[0] else None]),
        fires_needed_to_bound=dict(at_mle=n_needed(p40), at_ci_upper_p=n_needed(p_ci[1]),
                                   at_ci_lower_p=n_needed(p_ci[0]) if p_ci[0] else None,
                                   rule="n = ceil(ln 0.05 / ln(1 - p40)): fires with no exceedance needed for a one-sided "
                                        "95% upper bound at p40 (about 3 / p40)"),
        trust=dict(T40_interval_finite=bool(finite),
                   verdict=("number reported" if finite else
                            "fit cannot bound the 40 km return period with 28 fires (profile interval for p40 reaches 0)")),
        profile_xi=dict(grid=grid.tolist(), loglik=prof_xi.tolist()),
        profile_p40=dict(grid=pg.tolist(), loglik=prof_p.tolist()))
    json.dump(out, open(a.out, "w"), indent=1)
    print(json.dumps({k: out[k] for k in ("gev_mle", "p40", "T40_fires", "fires_needed_to_bound", "trust")}, indent=1))


if __name__ == "__main__":
    main()
