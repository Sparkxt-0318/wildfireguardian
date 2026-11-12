"""Independent toy check: hourly CA vs fine-step CA vs first-passage sampler.

Spec (own choice; the direction document's exact toy spec was not available):
40x40 grid, 5x5 stencil, centre coefficient 0, the other 24 coefficients equal
(sum = 0.043/h "slow" or 1.0/h "fast") at every cell, initial burned = 3x3 block
at the grid centre, 12 h horizon, 2,000 trajectories, zero boundary.

    python research/harness-2026-11/s-d1/toy_check.py [--n 2000] [--out RESULTS_toy.json]
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fpp import cellular_automaton, first_passage  # noqa: E402


def toy_kernel(total, size=40, k=5):
    K = np.full((k * k, size, size), total / (k * k - 1))
    K[(k * k) // 2] = 0
    return K


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--hours", type=float, default=12.0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    init = np.zeros((40, 40), bool)
    init[19:22, 19:22] = True
    first_passage(toy_kernel(0.1)[:, :8, :8], init[16:24, 16:24], [1.0], n_samples=2, seed=0)  # JIT warm-up
    results = {"spec": "40x40, 5x5 uniform off-centre, 3x3 centre ignition, zero boundary",
               "n": args.n, "hours": args.hours, "regimes": {}}
    for name, total in (("slow", 0.043), ("fast", 1.0)):
        K = toy_kernel(total)
        rows = {}
        for m in (1, 2, 4, 8, 16, 32):
            t0 = time.perf_counter()
            _, tot = cellular_automaton(K, init, [args.hours], dt=1 / m, n_samples=args.n,
                                        seed=100 + m, return_totals=True)
            sec = time.perf_counter() - t0
            x = tot[0]
            rows[f"ca_dt=1/{m}"] = dict(mean=float(x.mean()), se=float(x.std(ddof=1) / np.sqrt(len(x))),
                                        seconds=sec)
        t0 = time.perf_counter()
        _, arr = first_passage(K, init, [args.hours], n_samples=args.n, seed=7,
                               keep_arrivals=args.n)
        sec = time.perf_counter() - t0
        x = ((arr <= args.hours) & ~init).sum(axis=(1, 2))
        rows["first_passage"] = dict(mean=float(x.mean()), se=float(x.std(ddof=1) / np.sqrt(len(x))),
                                     seconds=sec)
        # Richardson extrapolation of the CA in dt (first order): 2*CA(dt/2) - CA(dt)
        rows["ca_richardson_1/16_1/32"] = dict(mean=2 * rows["ca_dt=1/32"]["mean"] - rows["ca_dt=1/16"]["mean"])
        results["regimes"][name] = dict(coefficient_sum_per_h=total, rows=rows)
        for k, v in rows.items():
            print(f"{name:5s} {k:26s} mean={v['mean']:9.3f}" + (f" se={v['se']:.3f} t={v['seconds']:.2f}s" if 'se' in v else ""))
    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
