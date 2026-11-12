"""Iris's checks on the displacement rank histogram (reads results/displacement_<estimator>.json).

1. Ties broken at random (seeded), plus the observed reach in cells for low-rank intervals.
2. Fire-clustered bootstrap intervals for both tails (rank < 0.05 and rank >= 0.95).
3. Which kernel drove the simulations (MCEM, the corrected rate, vs plug-in, the lower rate).
4. Low-rank share against interval length and night-time fraction (local mean solar time).
5. The upper tail with detached-component intervals removed.

    python displacement_checks.py --out results/displacement_checks.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def ranks_random_ties(rows, rng):
    out = []
    for r in rows:
        ds = np.asarray(r["d_sim_m"])
        below = (ds < r["d_obs_m"] - 1e-6).sum()
        ties = (np.abs(ds - r["d_obs_m"]) <= 1e-6).sum()
        out.append((below + rng.uniform(0, ties + 1)) / (len(ds) + 1))
    return np.array(out)


def clustered_ci(fires_rows, pred, rng, n=10_000):
    names = list(fires_rows)
    per = {f: np.array([pred(r) for r in fires_rows[f]], float) for f in names}
    draws = []
    for _ in range(n):
        pick = rng.integers(0, len(names), len(names))
        v = np.concatenate([per[names[i]] for i in pick])
        draws.append(v.mean() if len(v) else np.nan)
    allv = np.concatenate(list(per.values()))
    return dict(share=float(allv.mean()), ci95=[float(np.nanpercentile(draws, 2.5)), float(np.nanpercentile(draws, 97.5))])


def analyse(path, seed=20261112):
    d = json.loads(Path(path).read_text())
    rng = np.random.default_rng(seed)
    fires = {f: [r for r in rs if not r["stalled"]] for f, rs in d["per_fire"].items()}
    rows = [r for rs in fires.values() for r in rs]
    rr = ranks_random_ties(rows, rng)
    i = 0
    for rs in fires.values():
        for r in rs:
            r["rank_rt"] = float(rr[i])
            i += 1
    low = [r for r in rows if r["rank_rt"] < 0.05]
    res = dict(
        estimator=d["estimator"], intervals=len(rows),
        histogram_10_random_ties=np.histogram(rr, bins=10, range=(0, 1))[0].tolist(),
        low_tail=clustered_ci(fires, lambda r: r["rank_rt"] < 0.05, rng),
        top_tail=clustered_ci(fires, lambda r: r["rank_rt"] >= 0.95, rng),
        top_tail_without_detached=clustered_ci({f: [r for r in rs if not r["detached"]] for f, rs in fires.items()},
                                               lambda r: r["rank_rt"] >= 0.95, rng),
        detached_intervals=sum(r["detached"] for r in rows),
        low_rank_observed_reach_cells=dict(
            median=float(np.median([r["d_obs_cells"] for r in low])) if low else None,
            share_at_most_1_cell=float(np.mean([r["d_obs_cells"] <= 1.0 + 1e-9 for r in low])) if low else None),
    )
    # Covariates: interval length and night fraction, low-rank vs the rest.
    hrs = np.array([r["hours"] for r in rows])
    night = np.array([r["night_fraction"] for r in rows])
    is_low = rr < 0.05
    res["covariates"] = dict(
        hours_median_low=float(np.median(hrs[is_low])) if is_low.any() else None,
        hours_median_rest=float(np.median(hrs[~is_low])),
        night_fraction_mean_low=float(night[is_low].mean()) if is_low.any() else None,
        night_fraction_mean_rest=float(night[~is_low].mean()),
        low_share_by_hours={f"{lo}-{hi}h": float(is_low[(hrs > lo) & (hrs <= hi)].mean()) if ((hrs > lo) & (hrs <= hi)).any() else None
                            for lo, hi in [(0, 20), (20, 26), (26, 1000)]},
        low_share_by_night={f"{lo}-{hi}": float(is_low[(night >= lo) & (night < hi)].mean()) if ((night >= lo) & (night < hi)).any() else None
                            for lo, hi in [(0, 0.4), (0.4, 0.6), (0.6, 1.01)]})
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", nargs="+", default=["results/displacement_mcem.json", "results/displacement_plugin.json"])
    ap.add_argument("--out", type=Path, default=Path("results/displacement_checks.json"))
    a = ap.parse_args(argv)
    out = {Path(p).stem: analyse(p) for p in a.inputs}
    a.out.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
