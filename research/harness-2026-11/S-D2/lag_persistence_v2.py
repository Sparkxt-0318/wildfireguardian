"""Iris's follow-up to the lag-1 persistence check (lag1_persistence.py), covering her points 1 and 3.

* Lags 1, 2 and 3. Pairs lie within runs of time-contiguous, non-stalled intervals of one fire (next.a == this.b).
* Lag 1 after removing a within-fire linear trend in interval index. This separates "trend" from "state":
  if the excess is mostly trend, fire age as a cutoff covariate is the cheaper model.
* Pearson and Spearman, pooled over pairs.
* Null: values permuted within each fire (the pair positions stay fixed).
  excess = observed r − mean null r.
* Fire-clustered bootstrap 95% interval for the excess. Fires are resampled with replacement; in each draw the null
  mean is re-estimated with --perms-per-draw permutations.

Point 2 (which kernels drove the simulations) is not addressed here. The input displacement files used each fire's
OWN fitted kernel (displacement_diag.py), so a per-fire level is already partly absorbed. The re-measure on
cross-validation-fold kernels waits for cv_part_a.

    python lag_persistence_v2.py --inputs results/displacement_mcem.json --out results/lag_persistence_v2.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

from displacement_checks import ranks_random_ties


def fire_series(d, rng, drop_detached):
    """Per fire: rank, log ratio, interval index, and run id (contiguous non-stalled stretches)."""
    out = {}
    for f, rs in d["per_fire"].items():
        rs = sorted(rs, key=lambda r: r["a"])
        keep, run, runs, prev = [], 0, [], None
        for i, r in enumerate(rs):
            if r["stalled"] or (drop_detached and r.get("detached")):
                prev = None
                continue
            if prev is None or abs(r["a"] - prev["b"]) > 1e-6:
                run += 1
            keep.append((i, r))
            runs.append(run)
            prev = r
        if len(keep) < 2:
            continue
        rows = [r for _, r in keep]
        out[f] = dict(rank=ranks_random_ties(rows, rng),
                      log_ratio=np.array([np.log(r["d_obs_m"] / np.median(r["d_sim_m"])) for r in rows]),
                      index=np.array([i for i, _ in keep], float), run=np.array(runs))
    return out


def detrend(v, idx):
    if len(v) < 3:
        return v - v.mean()
    b = np.polyfit(idx, v, 1)
    return v - np.polyval(b, idx)


def pairs_for(s, lag):
    n = len(s["run"])
    i = np.arange(n - lag)
    return i[s["run"][i] == s["run"][i + lag]]  # same run => all intermediate intervals contiguous


def corr(x, y, spearman):
    if spearman:
        x, y = rankdata(x), rankdata(y)
    return float(np.corrcoef(x, y)[0, 1])


def stat(per, fires, metric, lag, det, spearman, rng=None):
    xs, ys = [], []
    for f in fires:
        s = per[f]
        v = detrend(s[metric], s["index"]) if det else s[metric]
        if rng is not None:
            v = v[rng.permutation(len(v))]
        p = pairs_for(s, lag)
        xs.append(v[p])
        ys.append(v[p + lag])
    x, y = np.concatenate(xs), np.concatenate(ys)
    return corr(x, y, spearman) if len(x) > 2 else np.nan


def analyse(per, metric, lag, det, spearman, rng, perms, boot, ppd):
    fires = sorted(f for f in per if len(pairs_for(per[f], lag)))
    obs = stat(per, fires, metric, lag, det, spearman)
    null = np.array([stat(per, fires, metric, lag, det, spearman, rng) for _ in range(perms)])
    ex = []
    for _ in range(boot):
        pick = [fires[i] for i in rng.integers(0, len(fires), len(fires))]
        o = stat(per, pick, metric, lag, det, spearman)
        nm = np.mean([stat(per, pick, metric, lag, det, spearman, rng) for _ in range(ppd)])
        ex.append(o - nm)
    return dict(pairs=int(sum(len(pairs_for(per[f], lag)) for f in fires)), fires=len(fires), r=obs,
                null_mean=float(null.mean()), null_sd=float(null.std()), excess=float(obs - null.mean()),
                excess_ci95=[float(np.nanpercentile(ex, 2.5)), float(np.nanpercentile(ex, 97.5))],
                p_one_sided=float((1 + (null >= obs).sum()) / (perms + 1)))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", type=Path, nargs="+", required=True)
    ap.add_argument("--perms", type=int, default=5000)
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--perms-per-draw", type=int, default=50)
    ap.add_argument("--seed", type=int, default=20261112)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    res = {}
    for path in a.inputs:
        d = json.loads(path.read_text())
        est = d.get("estimator", path.stem)
        for drop in (False, True):
            per = fire_series(d, np.random.default_rng(a.seed), drop)
            for metric in ("rank", "log_ratio"):
                for spear in (False, True):
                    for lag, det in ((1, False), (2, False), (3, False), (1, True)):
                        key = f"{est}{'_no_detached' if drop else ''}|{metric}|{'spearman' if spear else 'pearson'}|lag{lag}{'_detrended' if det else ''}"
                        rng = np.random.default_rng([a.seed, lag, det, spear, drop, metric == "rank"])
                        res[key] = analyse(per, metric, lag, det, spear, rng, a.perms, a.boot, a.perms_per_draw)
                        print(key, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in res[key].items()},
                              flush=True)
    a.out.write_text(json.dumps(dict(command="python lag_persistence_v2.py " + " ".join(argv or sys.argv[1:]),
                                     kernel_note="input simulations use each fire's own fitted kernel", results=res),
                                indent=1))


if __name__ == "__main__":
    main()
