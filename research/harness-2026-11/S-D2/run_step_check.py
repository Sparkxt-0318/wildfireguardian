"""Bound the discretised-Gibbs approximation (Victor's finding 3): MCEM at grid step 0.25 h vs 0.05 h.

Same truths and 24 h brackets as ``run_shape_recovery.py`` (low_far and high_far, seeds 0-4). The two steps are
paired by seed. Reported: total-rate ratio and far_share at each step, and their paired differences.

    python run_step_check.py --seeds 5 --workers 2 --out results/step_check.json
"""
from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

import run_shape_recovery as X
import synthetic as S
import synthetic_robust as R

STEPS = [0.25, 0.05]


def job(args):
    name, seed, step = args
    p = X.make(seed, **X.KERNELS[name])
    obs = S.observe_perimeter(p, every=X.EVERY)
    t0 = time.perf_counter()
    th = S.mcem(p, obs, np.random.default_rng(31_000 + seed), step=step, **R.MCEM_SHORT)[0]
    e = S.kernel_errors(th, p)
    return dict(kernel=name, seed=seed, step=step, total_rate_ratio=e["total_rate_ratio"],
                far_share=X.far_share(th, p.offs), rel_l2=e["rel_l2"], seconds=time.perf_counter() - t0)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--out", type=Path, default=Path("results/step_check.json"))
    a = ap.parse_args(argv)
    t0 = time.time()
    jobs = [(k, s, st) for k in X.KERNELS for s in range(a.seeds) for st in STEPS]
    with ProcessPoolExecutor(a.workers) as pool:
        rows = list(pool.map(job, jobs))
    summary = {}
    for k in X.KERNELS:
        by = {(r["seed"], r["step"]): r for r in rows if r["kernel"] == k}
        d_rate = [by[(s, 0.25)]["total_rate_ratio"] - by[(s, 0.05)]["total_rate_ratio"] for s in range(a.seeds)]
        d_far = [by[(s, 0.25)]["far_share"] - by[(s, 0.05)]["far_share"] for s in range(a.seeds)]
        summary[k] = dict(
            rate_ratio={str(st): float(np.mean([by[(s, st)]["total_rate_ratio"] for s in range(a.seeds)])) for st in STEPS},
            far_share={str(st): float(np.mean([by[(s, st)]["far_share"] for s in range(a.seeds)])) for st in STEPS},
            paired_rate_diff_mean=float(np.mean(d_rate)), paired_rate_diff_max_abs=float(np.max(np.abs(d_rate))),
            paired_far_diff_mean=float(np.mean(d_far)), paired_far_diff_max_abs=float(np.max(np.abs(d_far))),
            seconds={str(st): float(np.mean([by[(s, st)]["seconds"] for s in range(a.seeds)])) for st in STEPS})
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(dict(command="python run_step_check.py " + " ".join(argv or os.sys.argv[1:]),
                                     wall_seconds=time.time() - t0, summary=summary, rows=rows), indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
