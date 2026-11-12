"""Synthetic kernel-SHAPE recovery (Iris / Victor): does each estimator recover the far-offset share?

Two known 5x5 Markov kernels (anisotropic, distance-decaying), both with total rate about 0.055 /h (the median
MCEM rate on the 25 part-a NIROPS fires):
* ``low_far``: decay length 0.33, far share about 0.07;
* ``high_far``: decay length 4.0, far share about 0.60.

far_share = Σ_(Chebyshev ≥ 2) k / Σ k, i.e. offsets outside the 3x3 neighbourhood (the A1 descriptive-row
definition, unmodulated here). Arrivals are simulated exactly over T = 240 h on a 64x64 grid and observed only
as 24 h survey brackets, as on part a.
Estimators: plug-in (first observation time), independent-bracket composite, mean-field endpoint NLL, MCEM.
Reported per estimator and kernel over seeds: recovered far share, total-rate ratio and kernel rel-L2.

    python run_shape_recovery.py --seeds 5 --workers 4 --out results/shape_recovery.json
"""
from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

import synthetic as S
import synthetic_robust as R

KERNELS = {"low_far": dict(length=0.33, scale=0.0099), "high_far": dict(length=4.0, scale=0.00288)}
N, T, EVERY = 64, 240.0, 24.0


def far_mask(offs):
    return np.abs(offs).max(axis=1) >= 2


def far_share(theta, offs):
    k = np.asarray(theta)[1:]
    return float(k[far_mask(offs)].sum() / k.sum())


def make(seed, length, scale):
    rng = np.random.default_rng(seed)
    offs = S.offsets(2)
    k = S.true_kernel(offs, scale=scale, length=length)
    c = N // 2
    seeds = np.unique([int(rng.integers(c - 6, c + 7)) * N + int(rng.integers(c - 6, c + 7)) for _ in range(6)])
    p = S.Problem(n=N, offs=offs, k=k, k0=2e-5, T=T, seeds=seeds)
    p.tau = R.simulate_fpp(p, rng)
    return p


def job(args):
    name, seed = args
    cfg = KERNELS[name]
    p = make(seed, **cfg)
    obs = S.observe_perimeter(p, every=EVERY)
    point = np.where(obs["burned"], obs["hi"], S.INF)
    point[p.seeds] = 0.0
    src, _ = S._neighbour_table(p.n, p.offs)
    fits = {
        "plugin": lambda: S.fit_complete([S.sufficient_stats(p, point, src)]),
        "composite": lambda: R.fit_bracket_composite(p, obs),
        "meanfield_nll": lambda: R.fit_meanfield(p, obs, loss="nll"),
        "mcem": lambda: S.mcem(p, obs, np.random.default_rng(31_000 + seed), **R.MCEM_SHORT)[0],
    }
    true_share = far_share(np.concatenate([[p.k0], p.k]), p.offs)
    rows = []
    for est, fn in fits.items():
        t0 = time.perf_counter()
        th = fn()
        e = S.kernel_errors(th, p)
        rows.append(dict(kernel=name, seed=seed, estimator=est, far_share=far_share(th, p.offs),
                         true_far_share=true_share, total_rate_ratio=e["total_rate_ratio"], rel_l2=e["rel_l2"],
                         seconds=time.perf_counter() - t0, burned=int(np.isfinite(p.tau).sum()),
                         crossing_hours=R.crossing_time(p)))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))
    ap.add_argument("--out", type=Path, default=Path("results/shape_recovery.json"))
    a = ap.parse_args(argv)
    t0 = time.time()
    jobs = [(k, s) for k in KERNELS for s in range(a.seeds)]
    with ProcessPoolExecutor(a.workers) as pool:
        rows = [r for rs in pool.map(job, jobs) for r in rs]
    summary = {}
    for k in KERNELS:
        summary[k] = {}
        for est in ("plugin", "composite", "meanfield_nll", "mcem"):
            sub = [r for r in rows if r["kernel"] == k and r["estimator"] == est]
            fs = np.array([r["far_share"] for r in sub])
            summary[k][est] = dict(far_share_mean=float(fs.mean()), far_share_sd=float(fs.std(ddof=1)),
                                   true_far_share=sub[0]["true_far_share"],
                                   abs_error_mean=float(np.mean(np.abs(fs - sub[0]["true_far_share"]))),
                                   rate_ratio_mean=float(np.mean([r["total_rate_ratio"] for r in sub])),
                                   rel_l2_mean=float(np.mean([r["rel_l2"] for r in sub])),
                                   seconds_mean=float(np.mean([r["seconds"] for r in sub])))
        summary[k]["burned_median"] = float(np.median([r["burned"] for r in rows if r["kernel"] == k]))
        summary[k]["crossing_hours_median"] = float(np.median([r["crossing_hours"] for r in rows if r["kernel"] == k]))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(dict(command="python run_shape_recovery.py " + " ".join(argv or os.sys.argv[1:]),
                                     kernels=KERNELS, grid=N, T=T, every=EVERY, wall_seconds=time.time() - t0,
                                     summary=summary, rows=rows), indent=1))
    print(json.dumps(summary, indent=1))
    print(f"wall {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
