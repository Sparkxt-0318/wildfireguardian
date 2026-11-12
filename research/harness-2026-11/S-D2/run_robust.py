"""Round-2 robustness runs: misspecified truths, bracket-width sweep, cheaper estimators.

    python run_robust.py --replicates 8 --workers 4 --out results/robust.json

Scenarios per replicate (same seed => same truth across the scenarios that share
a generator):

  kriged_calibrated   Markov truth, independent error, stated sd correct
  kriged_correlated   Markov truth, error smoothed over 3 cells (kriging-like)
  kriged_miscal       Markov truth, true error = 1.75 x stated sd (the measured US factor)
  perim_{3,6,12,24}h  Markov truth, survey brackets of that spacing
  perim_nonexp_12h    Gamma(shape 4) passage delays (non-exponential), 12 h brackets
  perim_spotting_12h  Markov truth plus downwind distance-5/6 spotting offsets
                      outside the fitted 5x5 kernel, 12 h brackets

Scores: total-rate ratio (sum of fitted offsets over the true fitted-offset sum),
kernel rel. L2, held-out excess NLL (fitted Markov model on true arrivals of
three fresh fields from the same generator, minus the true-kernel Markov model:
for misspecified truths this baseline is itself not the generating law, so the
excess can be negative), wall time and Python-heap peak per estimator.
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
import synthetic_robust as R

SCENARIOS = ["kriged_calibrated", "kriged_correlated", "kriged_miscal", "perim_3h", "perim_6h",
             "perim_12h", "perim_24h", "perim_nonexp_12h", "perim_spotting_12h"]


def _t(memory, fn, *a, **kw):
    return R.timed(fn, *a, memory=memory, **kw)


def generator(scn):
    if scn == "perim_nonexp_12h":
        return dict(shape=4.0)
    if scn == "perim_spotting_12h":
        return dict(spot=R.spotting_offsets())
    return {}


def run_scenario(r, scn, memory=False):
    gen = generator(scn)
    p = R.make_problem(r, **gen)
    held = [R.make_problem(200_000 + 10 * r + j, **gen) for j in range(3)]
    truth = np.concatenate([[p.k0], p.k])
    base = S.heldout_nll(truth, held)
    rng = np.random.default_rng(5_000 + 31 * r + SCENARIOS.index(scn))
    src, _ = S._neighbour_table(p.n, p.offs)
    est = {}
    if scn.startswith("kriged"):
        kw = dict(kriged_correlated=dict(corr_cells=3.0), kriged_miscal=dict(true_factor=1.75)).get(scn, {})
        obs = R.observe_kriged_robust(p, rng, **kw)
        point = np.where(obs["burned"], np.clip(obs["tau_hat"], 1e-3, p.T), S.INF)
        point[p.seeds] = 0.0
        hard = lambda cells, t: ((point[cells] > t) & (point[cells] <= t + 1)).astype(float)
        X, y, _, _ = S.hourly_rows(p, point, hard, src)
        est["hard_hourly"] = _t(memory, S.fit_bernoulli, X, y)
        est["plugin"] = _t(memory, lambda: S.fit_complete([S.sufficient_stats(p, point, src)]))
        est["soft_risk_softfeat"] = _t(memory, lambda: S.fit_bernoulli(*S.soft_risk_rows(p, obs, point, src, soft_features=True)))
        if scn == "kriged_miscal":
            fixed = dict(obs, sd=obs["sd"] * 1.75)
            est["soft_risk_softfeat_recal"] = _t(memory, lambda: S.fit_bernoulli(*S.soft_risk_rows(p, fixed, point, src, soft_features=True)))
            est["mcem_recal"] = _t(memory, S.mcem, p, fixed, rng, **R.MCEM_SHORT)
        est["mcem"] = _t(memory, S.mcem, p, obs, rng, **R.MCEM_SHORT)
        if scn == "kriged_calibrated":
            est["mcem_long"] = _t(memory, S.mcem, p, obs, rng, **R.MCEM_LONG)
    else:
        every = float(scn.split("_")[-1].rstrip("h"))
        obs = S.observe_perimeter(p, every=every)
        point = np.where(obs["burned"], obs["hi"], S.INF)
        point[p.seeds] = 0.0
        est["plugin"] = _t(memory, lambda: S.fit_complete([S.sufficient_stats(p, point, src)]))
        est["bracket_composite"] = _t(memory, R.fit_bracket_composite, p, obs)
        est["meanfield_nll"] = _t(memory, R.fit_meanfield, p, obs, loss="nll")
        est["meanfield_brier"] = _t(memory, R.fit_meanfield, p, obs, loss="brier")
        est["mcem"] = _t(memory, S.mcem, p, obs, rng, **R.MCEM_SHORT)
    rows = []
    crossing = R.crossing_time(p)
    for name, (out, sec, mib) in est.items():
        theta = out[0] if isinstance(out, tuple) else out
        e = S.kernel_errors(theta, p)
        e.update(replicate=r, scenario=scn, estimator=name, seconds=sec, peak_mib=mib,
                 heldout_excess_nll=S.heldout_nll(theta, held) - base, crossing_hours=crossing,
                 burned=int(np.isfinite(p.tau).sum()))
        rows.append(e)
    return rows


def job(args):
    r, scn, memory = args
    return run_scenario(r, scn, memory)


def summarise(rows):
    out = {}
    for scn in SCENARIOS:
        sub = [x for x in rows if x["scenario"] == scn]
        if not sub:
            continue
        reps = sorted({x["replicate"] for x in sub})
        names = list(dict.fromkeys(x["estimator"] for x in sub))
        by = {(x["estimator"], x["replicate"]): x for x in sub}
        tab = {}
        for n in names:
            v = {m: np.array([by[(n, q)][m] for q in reps]) for m in
                 ("total_rate_ratio", "rel_l2", "rel_l2_near", "rel_l2_far", "heldout_excess_nll", "seconds")}
            tab[n] = {m: [float(a.mean()), float(a.std(ddof=1)) if len(a) > 1 else None] for m, a in v.items()}
            if n != "mcem":
                d = np.array([by[("mcem", q)]["heldout_excess_nll"] - by[(n, q)]["heldout_excess_nll"] for q in reps])
                tab[n]["mcem_better_nll"] = f"{int((d < 0).sum())}/{len(d)}"
        out[scn] = dict(replicates=len(reps), crossing_hours=float(np.median([by[(names[0], q)]["crossing_hours"] for q in reps])),
                        estimators=tab)
    return out


def markdown(summary):
    L = []
    for scn, s in summary.items():
        L.append(f"\n### {scn} ({s['replicates']} replicates; median crossing time {s['crossing_hours']:.2f} h)\n")
        L.append("| Estimator | Σk̂/Σk | Held-out excess NLL | rel. L2 (near / far) | s | peak MiB | MCEM better NLL |")
        L.append("|---|---:|---:|---:|---:|---:|---:|")
        for n, m in s["estimators"].items():
            f = lambda k, d: f"{m[k][0]:.{d}f} ± {m[k][1]:.{d}f}" if m[k][1] is not None else f"{m[k][0]:.{d}f}"
            L.append(f"| {n} | {f('total_rate_ratio', 3)} | {f('heldout_excess_nll', 4)} | "
                     f"{m['rel_l2'][0]:.3f} ({m['rel_l2_near'][0]:.3f} / {m['rel_l2_far'][0]:.3f}) | "
                     f"{m['seconds'][0]:.1f} | {m.get('peak_mib', '—')} | {m.get('mcem_better_nll', '—')} |")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--replicates", type=int, default=8)
    ap.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))
    ap.add_argument("--scenarios", nargs="+", default=SCENARIOS)
    ap.add_argument("--out", type=Path, default=Path("results/robust.json"))
    ap.add_argument("--memory", action="store_true",
                    help="trace Python-heap peak per estimator (slower; use a separate small run)")
    a = ap.parse_args(argv)
    t0 = time.time()
    jobs = [(r, s, a.memory) for r in range(a.replicates) for s in a.scenarios]
    # Longest jobs first for better packing.
    jobs.sort(key=lambda j: j[1] != "kriged_calibrated")
    with ProcessPoolExecutor(a.workers) as pool:
        rows = [x for rs in pool.map(job, jobs) for x in rs]
    summary = summarise(rows)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(dict(
        command=" ".join(["python", "run_robust.py"] + (argv if argv is not None else os.sys.argv[1:])),
        replicates=a.replicates, scenarios=a.scenarios, mcem_short=R.MCEM_SHORT, mcem_long=R.MCEM_LONG,
        wall_seconds=time.time() - t0, host=platform.platform(), python=platform.python_version(),
        numpy=np.__version__, rows=rows, summary=summary), indent=1))
    md = markdown(summary)
    a.out.with_suffix(".md").write_text(md + "\n")
    print(md)
    print(f"\nwall {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
