"""Displacement diagnostic on NIROPS part a (Iris): which survey intervals ran faster than the fitted model allows?

For every survey interval (a, b] of every fire in ``results/real_bracket_fit.json`` (first ``--hours``):

* observed displacement D_obs = the largest distance (m) from the cutoff mapped extent at a to a cell newly mapped
  by b. ``D_obs / (b - a)`` is a lower bound on the speed during the interval, and it does not depend on latent
  arrival times;
* model displacement: the same quantity in ``--sims`` exact forward simulations of that fire's fitted MCEM kernel,
  started from the exact cutoff state, giving its 95th percentile D_95.

An interval is flagged as a *run* if D_obs > D_95, i.e. the fire got farther than the model reaches in 95% of runs.
We report the share of intervals flagged, the share of new burn they carry, and the ratio D_obs / D_95.

A *saturation* flag marks intervals whose new burn touches the grid edge (the 3-cell margin), where displacement is
truncated.

This is a covariate-free development diagnostic; part-a data only.

    python displacement_diag.py --brackets DIR --fit results/real_bracket_fit.json --out results/displacement.json
"""
from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt, label

import real_bracket_fit as F
import synthetic as S
from cv_part_a import simulate_cells

CELL_M = 375.0


def fire_job(args):
    path, theta, hours, sims, seed = args
    p, obs = F.load_fire(Path(path), hours, 0)
    z = np.load(path)
    h, w = z["first_survey"].shape
    edge = np.zeros((p.n, p.n), bool)
    edge[:h, :w] = True
    edge[3:h - 3, 3:w - 3] = False          # margin ring of the real grid
    edge = edge.ravel()
    hi_t = np.where(obs["burned"], obs["hi"], S.INF)
    theta = np.asarray(theta)
    rng = np.random.default_rng(seed)
    rows = []
    for a, b in zip(obs["surveys"][:-1], obs["surveys"][1:]):
        start = hi_t <= a
        new = (hi_t > a) & (hi_t <= b)
        if not start.any():
            continue
        if not new.any():
            rows.append(dict(a=float(a), b=float(b), hours=float(b - a), new_cells=0, stalled=True))
            continue
        dist = distance_transform_edt(~start.reshape(p.n, p.n)).ravel() * CELL_M
        d_obs = float(dist[new].max())
        # Detached: the farthest new cell's 8-connected component of (start | new) contains no start cell.
        comp, _ = label((start | new).reshape(p.n, p.n), structure=np.ones((3, 3)))
        comp = comp.ravel()
        far = np.flatnonzero(new & (dist == d_obs))[0]
        detached = not bool((comp[start] == comp[far]).any())
        d_sim = []
        for _ in range(sims):
            done = simulate_cells(p, start, float(b - a), theta, rng)
            nb = done & ~start
            d_sim.append(float(dist[nb].max()) if nb.any() else 0.0)
        d95 = float(np.percentile(d_sim, 95))
        ds = np.array(d_sim)
        rank = float(((ds < d_obs).sum() + 0.5 * (ds == d_obs).sum()) / len(ds))   # PIT-style mid-rank
        rows.append(dict(a=float(a), b=float(b), hours=float(b - a), new_cells=int(new.sum()), stalled=False,
                         rank=rank, detached=detached, d_obs_m=d_obs,
                         d95_model_m=d95, ratio=d_obs / max(d95, CELL_M), run=bool(d_obs > d95),
                         saturated=bool((new & edge).any()), min_speed_kmh=d_obs / 1000 / float(b - a)))
    return Path(path).stem, rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--brackets", type=Path, required=True)
    ap.add_argument("--fit", type=Path, default=Path("results/real_bracket_fit.json"))
    ap.add_argument("--hours", type=float, default=240.0)
    ap.add_argument("--sims", type=int, default=64)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--out", type=Path, default=Path("results/displacement.json"))
    a = ap.parse_args(argv)
    fit = json.loads(a.fit.read_text())
    jobs = [(str(a.brackets / f"{f['fire']}.npz"), f["estimators"]["mcem"]["theta"], a.hours, a.sims, 5150 + i)
            for i, f in enumerate(fit["fires"])]
    t0 = time.time()
    with ProcessPoolExecutor(a.workers) as pool:
        res = dict(pool.map(fire_job, jobs))
    stalled = [r for rs in res.values() for r in rs if r["stalled"]]
    allr = [r for rs in res.values() for r in rs if not r["stalled"]]
    runs = [r for r in allr if r["run"]]
    ranks = np.array([r["rank"] for r in allr])
    # Fire-clustered bootstrap of the share of intervals with rank >= 0.95 (nominal 0.05).
    rng = np.random.default_rng(20261030)
    names = list(res)
    per = {f: np.array([r["rank"] >= 0.95 for r in res[f] if not r["stalled"]], dtype=float) for f in names}
    boots = []
    for _ in range(10_000):
        pick = rng.integers(0, len(names), len(names))
        hits = np.concatenate([per[names[i]] for i in pick])
        boots.append(hits.mean() if len(hits) else np.nan)
    top = dict(share=float((ranks >= 0.95).mean()), nominal=0.05,
               ci95_fire_bootstrap=[float(np.nanpercentile(boots, 2.5)), float(np.nanpercentile(boots, 97.5))])
    sat = [r for r in allr if r["saturated"]]
    summary = dict(intervals=len(allr), run_intervals=len(runs),
                   run_share=len(runs) / max(len(allr), 1),
                   new_burn_share_in_runs=sum(r["new_cells"] for r in runs) / max(sum(r["new_cells"] for r in allr), 1),
                   median_ratio=float(np.median([r["ratio"] for r in allr])),
                   median_ratio_runs=float(np.median([r["ratio"] for r in runs])) if runs else None,
                   saturated_intervals=len(sat),
                   rank_histogram_10=np.histogram(ranks, bins=10, range=(0, 1))[0].tolist(),
                   rank_low_share=float((ranks < 0.05).mean()), rank_top=top,
                   stalled_intervals=len(stalled), stalled_share=len(stalled) / max(len(stalled) + len(allr), 1),
                   detached_runs=sum(r["detached"] for r in runs),
                   detached_share_all=float(np.mean([r["detached"] for r in allr])),
                   fires_with_runs=sum(any(r.get("run", False) for r in rs) for rs in res.values()), fires=len(res))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(dict(command="python displacement_diag.py " + " ".join(argv or os.sys.argv[1:]),
                                     sims=a.sims, hours=a.hours, wall_seconds=time.time() - t0,
                                     summary=summary, per_fire=res), indent=1))
    print(json.dumps(summary, indent=1))
    print(f"wall {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
