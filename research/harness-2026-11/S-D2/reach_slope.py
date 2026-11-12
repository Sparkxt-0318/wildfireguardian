"""Two non-mechanical checks on the displacement misfit (Iris, Owen).

1. Confounding check (the earlier ad hoc run, now committed). Spearman correlation of fire age with simulated lead.
   Then, within each age tercile, rho(simulated lead, rank); and within each lead tercile, rho(age, rank).

2. Reach calibration slope. Ordinary least squares of log observed reach on log simulated median reach, with a
   fire-clustered bootstrap 95% interval.
   - slope 1: the model's variation in reach is real;
   - slope below 1: shrink it;
   - slope near 0: no skill beyond the average.
   The simulated lead is then split into a length part and a modulation part. The length part is the fitted value of
   a pooled OLS of log simulated median reach on log interval length; the modulation part is the residual. NOTE: the
   input simulations use each fire's own homogeneous lattice kernel (real_bracket_fit), with no weather or fuel
   covariates. So the "modulation part" here is the non-length variation: between-fire kernel rates and the
   start-state geometry. It is NOT a weather or fuel effect. Both enter one regression and both slopes are reported. A third
   regression uses log interval length directly.
   Between-fire / within-fire split (Iris): OLS of fire-mean log obs on fire-mean log sim (one point per distinct
   fire in the sample), and pooled OLS of the deviations from fire means. A fire drawn k times in a bootstrap draw
   is treated as one fire with k times its rows, so the between slope uses the distinct fires in that draw.
   Rows are non-stalled intervals. Observed reach is d_obs_m, which is positive by construction; rows with
   d_obs_m <= 0 are dropped and counted.

    python reach_slope.py --input results/displacement_mcem.json --out results/reach_slope_mcem.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

import cutoff_covariates as C


def ols(X, y):
    X = np.column_stack([np.ones(len(y)), *X])
    return np.linalg.lstsq(X, y, rcond=None)[0]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--boot", type=int, default=10_000)
    ap.add_argument("--seed", type=int, default=20261112)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    d = json.loads(a.input.read_text())
    # 1. Confounding check (same rows and tie-breaking as cutoff_covariates.py with the same seed).
    rows = C.table(d, np.random.default_rng(a.seed))
    age = np.array([r["age"] for r in rows]); lead = np.array([r["sim_lead"] for r in rows])
    rank = np.array([r["rank"] for r in rows])
    conf = dict(rho_age_lead=float(spearmanr(age, lead)[0]), lead_within_age_tercile=[], age_within_lead_tercile=[])
    for key, by, other in (("lead_within_age_tercile", age, lead), ("age_within_lead_tercile", lead, age)):
        g = np.digitize(by, np.quantile(by, [1 / 3, 2 / 3]))
        for j in range(3):
            m = g == j
            conf[key].append(dict(n=int(m.sum()), rho=float(spearmanr(other[m], rank[m])[0])))
    # 2. Slopes.
    rec = []
    for f, rs in d["per_fire"].items():
        for r in rs:
            if not r["stalled"]:
                rec.append((f, r["d_obs_m"], float(np.median(r["d_sim_m"])), r["hours"]))
    dropped = sum(1 for x in rec if x[1] <= 0)
    rec = [x for x in rec if x[1] > 0]
    fires = np.array([x[0] for x in rec]); yo = np.log([x[1] for x in rec]); ls = np.log([x[2] for x in rec])
    lh = np.log([x[3] for x in rec])

    def fit(idx):
        b_lead = ols([ls[idx]], yo[idx])[1]
        g = ols([lh[idx]], ls[idx])
        lpart = g[0] + g[1] * lh[idx]
        mpart = ls[idx] - lpart
        b2 = ols([lpart, mpart], yo[idx])
        b_len = ols([lh[idx]], yo[idx])[1]
        # Between / within split (Iris). Fire means are taken over the resampled rows; a fire drawn twice counts twice.
        fi = fires[idx]
        keys, inv = np.unique(fi, return_inverse=True)
        cnt = np.bincount(inv)
        mo = np.bincount(inv, yo[idx]) / cnt
        ms = np.bincount(inv, ls[idx]) / cnt
        b_between = ols([ms], mo)[1]
        b_within = ols([ls[idx] - ms[inv]], yo[idx] - mo[inv])[1]
        return np.array([b_lead, b2[1], b2[2], b_len, g[1], b_between, b_within])

    names = ["slope_on_log_sim_lead", "slope_on_length_part", "slope_on_modulation_part",
             "slope_on_log_hours_direct", "sim_lead_elasticity_in_hours",
             "between_fire_slope", "within_fire_slope"]
    est = fit(np.arange(len(yo)))
    uf = np.unique(fires); by = {f: np.flatnonzero(fires == f) for f in uf}
    rng = np.random.default_rng(a.seed)
    draws = np.array([fit(np.concatenate([by[uf[i]] for i in rng.integers(0, len(uf), len(uf))]))
                      for _ in range(a.boot)])
    slopes = {n: dict(estimate=float(est[k]), ci95=[float(np.percentile(draws[:, k], 2.5)),
                                                     float(np.percentile(draws[:, k], 97.5))])
              for k, n in enumerate(names)}
    sd = dict(log_sim_lead=float(ls.std()), modulation_part=float((ls - (ols([lh], ls)[0] + ols([lh], ls)[1] * lh)).std()),
              log_obs=float(yo.std()))
    out = dict(command="python reach_slope.py " + " ".join(argv or sys.argv[1:]), estimator=d.get("estimator"),
               intervals=len(yo), fires=len(uf), dropped_nonpositive_obs=dropped, confounding=conf, slopes=slopes,
               sd=sd, boot=a.boot, seed=a.seed)
    a.out.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
