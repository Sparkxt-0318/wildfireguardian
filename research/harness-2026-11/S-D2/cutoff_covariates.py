"""Iris's cutoff-time covariates for the displacement ranks: is the misfit predictable from what is known at the
start of an interval?

Covariates, all known at the interval start (cutoff):
- fire age: hours since the first observation;
- interval index within the fire;
- growth in the previous interval: log(1 + new cells);
- simulated lead: log of the median simulated reach (d_sim) for this interval.

For each covariate: Spearman rho with the rank, and the low-rank share (rank < 0.05) by covariate tercile. Both
come with fire-clustered bootstrap 95% intervals (10 000 draws, seeded). Non-stalled intervals only; ties are broken
at random, as in displacement_checks.py. The first interval of a fire has no previous growth and is left out of
that covariate only.

    python cutoff_covariates.py --input results/displacement_mcem.json --out results/cutoff_covariates_mcem.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

from displacement_checks import ranks_random_ties


def table(d, rng):
    rows = []
    for f, rs in d["per_fire"].items():
        rs = sorted(rs, key=lambda r: r["a"])
        t0 = rs[0]["a"]
        prev = None
        for i, r in enumerate(rs):
            if not r["stalled"]:
                rows.append(dict(fire=f, rank=float(ranks_random_ties([r], rng)[0]), age=r["a"] - t0, index=i,
                                 prev_growth=np.log1p(prev["new_cells"]) if prev is not None else np.nan,
                                 sim_lead=float(np.log(np.median(r["d_sim_m"])))))
            prev = r
    return rows


def boot(rows, fn, rng, n):
    fires = sorted({r["fire"] for r in rows})
    by = {f: [r for r in rows if r["fire"] == f] for f in fires}
    est = fn(rows)
    draws = []
    for _ in range(n):
        pick = rng.integers(0, len(fires), len(fires))
        draws.append(fn([r for i in pick for r in by[fires[i]]]))
    draws = np.array(draws, float)
    return est, [float(np.nanpercentile(draws, 2.5)), float(np.nanpercentile(draws, 97.5))]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--boot", type=int, default=10_000)
    ap.add_argument("--seed", type=int, default=20261112)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    d = json.loads(a.input.read_text())
    rng = np.random.default_rng(a.seed)
    rows = table(d, rng)
    res = dict(intervals=len(rows), fires=len({r["fire"] for r in rows}),
               low_rank_share=float(np.mean([r["rank"] < 0.05 for r in rows])), covariates={})
    for cov in ("age", "index", "prev_growth", "sim_lead"):
        sub = [r for r in rows if np.isfinite(r[cov])]
        rho, ci = boot(sub, lambda rs: spearmanr([r[cov] for r in rs], [r["rank"] for r in rs])[0], rng, a.boot)
        cuts = np.quantile([r[cov] for r in sub], [1 / 3, 2 / 3])
        terc = {}
        for k, (lo, hi) in enumerate([(-np.inf, cuts[0]), (cuts[0], cuts[1]), (cuts[1], np.inf)]):
            t = [r for r in sub if lo < r[cov] <= hi] if k else [r for r in sub if r[cov] <= hi]
            s, c = boot(t, lambda rs: np.mean([r["rank"] < 0.05 for r in rs]) if rs else np.nan, rng, a.boot)
            terc[f"T{k + 1}"] = dict(n=len(t), range=[float(min(r[cov] for r in t)), float(max(r[cov] for r in t))],
                                     low_rank_share=float(s), ci95=c)
        res["covariates"][cov] = dict(n=len(sub), spearman=float(rho), ci95=ci, terciles=terc)
    a.out.write_text(json.dumps(dict(command="python cutoff_covariates.py " + " ".join(argv or __import__("sys").argv[1:]),
                                     estimator=d.get("estimator"), **res), indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
