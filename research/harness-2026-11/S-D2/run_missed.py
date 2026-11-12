"""Missed-detection arm (Iris): bias of a hard lower bound when overpasses miss fire.

    python run_missed.py --replicates 4 --workers 4 --out results/missed.json
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

QS = [0.0, 0.2, 0.4]


def job(args):
    r, q, left_open = args
    p = R.make_problem(r)
    held = [R.make_problem(200_000 + 10 * r + j) for j in range(3)]
    base = S.heldout_nll(np.concatenate([[p.k0], p.k]), held)
    obs = R.observe_detections(p, np.random.default_rng(9_000 + r), every=12.0, q=q, left_open=left_open)
    t0 = time.perf_counter()
    theta = S.mcem(p, obs, np.random.default_rng(11_000 + r), **R.MCEM_SHORT)[0]
    e = S.kernel_errors(theta, p)
    e.update(replicate=r, q=q, bracket="left_open" if left_open else "hard", seconds=time.perf_counter() - t0,
             missed_cells=obs["missed_cells"], heldout_excess_nll=S.heldout_nll(theta, held) - base)
    return e


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--replicates", type=int, default=4)
    ap.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))
    ap.add_argument("--out", type=Path, default=Path("results/missed.json"))
    a = ap.parse_args(argv)
    t0 = time.time()
    jobs = [(r, q, lo) for r in range(a.replicates) for q in QS for lo in (False, True)]
    with ProcessPoolExecutor(a.workers) as pool:
        rows = list(pool.map(job, jobs))
    lines = ["| q | bracket | Σk̂/Σk (MCEM) | held-out excess NLL | missed cells |", "|---:|---|---:|---:|---:|"]
    summary = {}
    for q in QS:
        for b in ("hard", "left_open"):
            sub = [x for x in rows if x["q"] == q and x["bracket"] == b]
            rr = np.array([x["total_rate_ratio"] for x in sub])
            nl = np.array([x["heldout_excess_nll"] for x in sub])
            mc = np.mean([x["missed_cells"] for x in sub])
            summary[f"{q}_{b}"] = dict(rate=[float(rr.mean()), float(rr.std(ddof=1))], nll=[float(nl.mean()), float(nl.std(ddof=1))], missed=float(mc))
            lines.append(f"| {q} | {b} | {rr.mean():.3f} ± {rr.std(ddof=1):.3f} | {nl.mean():.4f} ± {nl.std(ddof=1):.4f} | {mc:.0f} |")
    md = "\n".join(lines)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(dict(wall_seconds=time.time() - t0, rows=rows, summary=summary), indent=1))
    a.out.with_suffix(".md").write_text(md + "\n")
    print(md)
    print(f"wall {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
