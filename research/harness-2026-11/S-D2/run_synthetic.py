"""Run the synthetic known-kernel comparison and write results JSON + a table.

    python run_synthetic.py --replicates 8 --workers 4 --out results/synthetic.json

Each replicate simulates one training field (seeded by its index) and three
fresh held-out fields from the same kernel.  Every estimator sees only its
observation model; the held-out score uses the true arrival times of the
fresh fields, so it measures the fitted kernel, not the observation noise.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

import synthetic as S

GRID = dict(n=56, n_seeds=8, radius=2, T=48.0)
MCEM = dict(iterations=30, sweeps=3, keep=2, average_last=10)


def replicate(r: int, sd_choices, every):
    t0 = time.time()
    p = S.make_problem(r, **GRID)
    heldout = [S.make_problem(100_000 + 10 * r + j, **GRID) for j in range(3)]
    truth = np.concatenate([[p.k0], p.k])
    base = S.heldout_nll(truth, heldout)
    rows = []
    for kind in ("kriged", "perimeter"):
        rng = np.random.default_rng(1_000 + r * 7 + (kind == "perimeter"))
        obs = S.observe_kriged(p, rng, sd_choices=sd_choices) if kind == "kriged" else S.observe_perimeter(p, every=every)
        t1 = time.time()
        est, _ = S.estimate_all(p, obs, rng, mcem_kwargs=MCEM)
        for name, theta in est.items():
            e = S.kernel_errors(theta, p)
            e.update(replicate=r, observation=kind, estimator=name,
                     heldout_excess_nll=S.heldout_nll(theta, heldout) - base,
                     burned=int(np.isfinite(p.tau).sum()))
            rows.append(e)
        rows.append(dict(replicate=r, observation=kind, estimator="_timing", seconds=time.time() - t1))
    return rows, time.time() - t0


def summarise(rows):
    out = {}
    for kind in ("kriged", "perimeter"):
        sub = [r for r in rows if r["observation"] == kind and r["estimator"] != "_timing"]
        names = list(dict.fromkeys(r["estimator"] for r in sub))
        reps = sorted({r["replicate"] for r in sub})
        table = {}
        for n in names:
            vals = {m: np.array([r[m] for r in sub if r["estimator"] == n])
                    for m in ("rel_l2", "rel_l2_near", "rel_l2_far", "total_rate_ratio", "heldout_excess_nll")}
            table[n] = {m: dict(mean=float(v.mean()), sd=float(v.std(ddof=1)) if len(v) > 1 else None)
                        for m, v in vals.items()}
        # Paired comparisons of MCEM against each other non-oracle estimator.
        paired = {}
        by = {(r["estimator"], r["replicate"]): r for r in sub}
        for n in names:
            if n in ("mcem", "oracle"):
                continue
            d = np.array([by[("mcem", q)]["heldout_excess_nll"] - by[(n, q)]["heldout_excess_nll"] for q in reps])
            dl2 = np.array([by[("mcem", q)]["rel_l2"] - by[(n, q)]["rel_l2"] for q in reps])
            paired[n] = dict(mcem_minus_other_heldout_nll_mean=float(d.mean()),
                             mcem_minus_other_heldout_nll_sd=float(d.std(ddof=1)) if len(d) > 1 else None,
                             mcem_better_nll=f"{int((d < 0).sum())}/{len(d)}",
                             mcem_minus_other_rel_l2_mean=float(dl2.mean()),
                             mcem_better_rel_l2=f"{int((dl2 < 0).sum())}/{len(dl2)}")
        out[kind] = dict(replicates=len(reps), estimators=table, paired_vs_mcem=paired)
    return out


def markdown(summary):
    lines = []
    for kind, s in summary.items():
        lines.append(f"\n### Observation model: {kind} ({s['replicates']} replicates, mean ± sd)\n")
        lines.append("| Estimator | Held-out excess NLL / arrival | Kernel rel. L2 | near (8) | far (16) | Σk̂ / Σk |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for n, m in s["estimators"].items():
            f = lambda k, d=4: f"{m[k]['mean']:.{d}f} ± {m[k]['sd']:.{d}f}" if m[k]["sd"] is not None else f"{m[k]['mean']:.{d}f}"
            lines.append(f"| {n} | {f('heldout_excess_nll')} | {f('rel_l2', 3)} | {f('rel_l2_near', 3)} | "
                         f"{f('rel_l2_far', 3)} | {f('total_rate_ratio', 3)} |")
        lines.append("\n| MCEM vs | Δ held-out NLL (mcem − other) | MCEM better (NLL) | Δ rel. L2 | MCEM better (L2) |")
        lines.append("|---|---:|---:|---:|---:|")
        for n, d in s["paired_vs_mcem"].items():
            sd = d["mcem_minus_other_heldout_nll_sd"]
            lines.append(f"| {n} | {d['mcem_minus_other_heldout_nll_mean']:.4f}"
                         f"{'' if sd is None else f' ± {sd:.4f}'} | {d['mcem_better_nll']} | "
                         f"{d['mcem_minus_other_rel_l2_mean']:+.3f} | {d['mcem_better_rel_l2']} |")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--replicates", type=int, default=8)
    ap.add_argument("--first", type=int, default=0)
    ap.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))
    ap.add_argument("--sd", type=float, nargs="+", default=[0.5, 2.0, 6.0])
    ap.add_argument("--every", type=float, default=12.0)
    ap.add_argument("--out", type=Path, default=Path("results/synthetic.json"))
    a = ap.parse_args(argv)
    t0 = time.time()
    reps = list(range(a.first, a.first + a.replicates))
    with ProcessPoolExecutor(a.workers) as pool:
        results = list(pool.map(replicate, reps, [tuple(a.sd)] * len(reps), [a.every] * len(reps)))
    rows = [r for rs, _ in results for r in rs]
    summary = summarise(rows)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    record = dict(command=" ".join(["python", "run_synthetic.py"] + (argv if argv is not None else os.sys.argv[1:])),
                  grid=GRID, mcem=MCEM, sd_choices=a.sd, perimeter_every_hours=a.every,
                  replicates=reps, wall_seconds=time.time() - t0, host=platform.platform(),
                  python=platform.python_version(), numpy=np.__version__,
                  rows=rows, summary=summary)
    a.out.write_text(json.dumps(record, indent=1))
    md = markdown(summary)
    a.out.with_suffix(".md").write_text(md + "\n")
    print(md)
    print(f"\nwall {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
