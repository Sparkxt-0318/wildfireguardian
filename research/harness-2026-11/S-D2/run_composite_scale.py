"""Iris's cheaper candidate: composite kernel shape, then a scalar rate by exact forward simulation.

Runs ``synthetic_robust.fit_composite_then_scale`` on the same truths and brackets as ``run_robust.py``.
Problems and perimeter brackets are deterministic per (replicate, scenario), so the stored MCEM, composite and
plug-in rows of ``results/robust.json`` are compared directly, without rerunning MCEM.

    python run_composite_scale.py --replicates 8 --workers 4 --out results/composite_scale.json
"""
from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

import run_robust as RR
import synthetic as S
import synthetic_robust as R

SCENARIOS = ["perim_6h", "perim_12h", "perim_24h", "perim_spotting_12h"]


def job(args):
    r, scn = args
    gen = RR.generator(scn)
    p = R.make_problem(r, **gen)
    held = [R.make_problem(200_000 + 10 * r + j, **gen) for j in range(3)]
    base = S.heldout_nll(np.concatenate([[p.k0], p.k]), held)
    every = float(scn.split("_")[-1].rstrip("h"))
    obs = S.observe_perimeter(p, every=every)
    t0 = time.perf_counter()
    theta = R.fit_composite_then_scale(p, obs, seed=7_000 + r)
    sec = time.perf_counter() - t0
    e = S.kernel_errors(theta, p)
    e.update(replicate=r, scenario=scn, estimator="composite_scale", seconds=sec,
             heldout_excess_nll=S.heldout_nll(theta, held) - base)
    return e


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--replicates", type=int, default=8)
    ap.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))
    ap.add_argument("--stored", type=Path, default=Path("results/robust.json"))
    ap.add_argument("--out", type=Path, default=Path("results/composite_scale.json"))
    a = ap.parse_args(argv)
    t0 = time.time()
    jobs = [(r, s) for r in range(a.replicates) for s in SCENARIOS]
    with ProcessPoolExecutor(a.workers) as pool:
        rows = list(pool.map(job, jobs))
    stored = json.loads(a.stored.read_text())["rows"]
    by = {(x["estimator"], x["scenario"], x["replicate"]): x for x in stored}
    summary, lines = {}, []
    for scn in SCENARIOS:
        reps = list(range(a.replicates))
        new = {x["replicate"]: x for x in rows if x["scenario"] == scn}
        tab = {}
        for name in ("plugin", "bracket_composite", "mcem", "composite_scale"):
            src = [new[q] if name == "composite_scale" else by[(name, scn, q)] for q in reps]
            v = {m: np.array([x[m] for x in src]) for m in ("total_rate_ratio", "heldout_excess_nll", "rel_l2", "seconds")}
            tab[name] = {m: [float(x.mean()), float(x.std(ddof=1))] for m, x in v.items()}
        d = np.array([new[q]["heldout_excess_nll"] - by[("mcem", scn, q)]["heldout_excess_nll"] for q in reps])
        tab["composite_scale"]["better_than_mcem_nll"] = f"{int((d < 0).sum())}/{len(d)}"
        summary[scn] = tab
        lines.append(f"\n### {scn} ({a.replicates} replicates)\n")
        lines.append("| Estimator | Σk̂/Σk | Held-out excess NLL | rel. L2 | s |")
        lines.append("|---|---:|---:|---:|---:|")
        for name, m in tab.items():
            lines.append(f"| {name} | {m['total_rate_ratio'][0]:.3f} ± {m['total_rate_ratio'][1]:.3f} | "
                         f"{m['heldout_excess_nll'][0]:.4f} ± {m['heldout_excess_nll'][1]:.4f} | "
                         f"{m['rel_l2'][0]:.3f} | {m['seconds'][0]:.1f} |")
        lines.append(f"\ncomposite_scale beats MCEM on held-out NLL in {tab['composite_scale']['better_than_mcem_nll']}.")
    md = "\n".join(lines)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(dict(command="python run_composite_scale.py " + " ".join(argv or os.sys.argv[1:]),
                                     stored=str(a.stored), wall_seconds=time.time() - t0, rows=rows,
                                     summary=summary), indent=1))
    a.out.with_suffix(".md").write_text(md + "\n")
    print(md)
    print(f"\nwall {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
