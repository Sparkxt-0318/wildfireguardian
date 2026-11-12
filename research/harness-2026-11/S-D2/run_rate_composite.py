"""A1 §3.2 rate_composite step 1: composite shape + bracket-likelihood scale vs full MCEM.

Regimes (fixed in A1 at 45644c89):
* slow = the verified Markov setting (kernel scale 0.025, crossing time about 6.6 h);
* fast = kernel x4 (scale 0.1, crossing time about 2 h; the 56x56 grid burns out within T = 48 h).
Both use 12 h and 24 h perimeter brackets and seeds 0-4. Matching rule (A1, agreed); all must hold in both regimes:
* rate: mean |log r_hat/r| of full MCEM minus that of rate_composite is <= 0.05;
* likelihood: mean paired held-out log-lik difference (full - composite) < 2 SD / sqrt(n);
* shape: rate_composite rel-L2 not worse than full by more than paired 2 SE.

    python run_rate_composite.py --workers 4 --out results/rate_composite.json
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

REGIMES = {"slow": 0.025, "fast": 0.1}
BRACKETS = [12.0, 24.0]
SEEDS = range(5)


def job(args):
    regime, every, seed = args
    sc = REGIMES[regime]
    p = R.make_problem(seed, scale=sc)
    held = [R.make_problem(300_000 + 10 * seed + j, scale=sc) for j in range(3)]
    base = S.heldout_nll(np.concatenate([[p.k0], p.k]), held)
    obs = S.observe_perimeter(p, every=every)
    out = []
    for name, fn in (("rate_composite", lambda rng: R.fit_rate_composite(p, obs, rng, **R.MCEM_SHORT)),
                     ("mcem", lambda rng: S.mcem(p, obs, rng, **R.MCEM_SHORT)[0])):
        t0 = time.perf_counter()
        theta = fn(np.random.default_rng(13_000 + 97 * seed + int(every)))
        e = S.kernel_errors(theta, p)
        e.update(regime=regime, bracket_hours=every, seed=seed, estimator=name, seconds=time.perf_counter() - t0,
                 abs_log_rate=abs(float(np.log(e["total_rate_ratio"]))),
                 heldout_loglik=-(S.heldout_nll(theta, held) - base), crossing_hours=R.crossing_time(p))
        out.append(e)
    return out


def decide(rows):
    verdict = {}
    for regime in REGIMES:
        for every in BRACKETS:
            sub = [x for x in rows if x["regime"] == regime and x["bracket_hours"] == every]
            f = {x["seed"]: x for x in sub if x["estimator"] == "mcem"}
            c = {x["seed"]: x for x in sub if x["estimator"] == "rate_composite"}
            seeds = sorted(f)
            n = len(seeds)
            rate_adv = np.mean([c[s]["abs_log_rate"] - f[s]["abs_log_rate"] for s in seeds])
            dl = np.array([f[s]["heldout_loglik"] - c[s]["heldout_loglik"] for s in seeds])
            ds = np.array([c[s]["rel_l2"] - f[s]["rel_l2"] for s in seeds])
            cond = dict(rate=bool(rate_adv <= 0.05),
                        loglik=bool(dl.mean() < 2 * dl.std(ddof=1) / np.sqrt(n)),
                        shape=bool(ds.mean() <= 2 * ds.std(ddof=1) / np.sqrt(n)))
            verdict[f"{regime}_{int(every)}h"] = dict(
                full_rate_advantage=float(rate_adv), loglik_diff_mean=float(dl.mean()),
                loglik_tol=float(2 * dl.std(ddof=1) / np.sqrt(n)), shape_diff_mean=float(ds.mean()),
                shape_tol=float(2 * ds.std(ddof=1) / np.sqrt(n)), conditions=cond, all_hold=all(cond.values()),
                rate_ratio=dict(mcem=float(np.mean([f[s]["total_rate_ratio"] for s in seeds])),
                                rate_composite=float(np.mean([c[s]["total_rate_ratio"] for s in seeds]))),
                seconds=dict(mcem=float(np.mean([f[s]["seconds"] for s in seeds])),
                             rate_composite=float(np.mean([c[s]["seconds"] for s in seeds]))))
    verdict["rate_composite_is_refit_candidate"] = all(v["all_hold"] for v in verdict.values())
    return verdict


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))
    ap.add_argument("--out", type=Path, default=Path("results/rate_composite.json"))
    a = ap.parse_args(argv)
    t0 = time.time()
    jobs = [(r, b, s) for r in REGIMES for b in BRACKETS for s in SEEDS]
    with ProcessPoolExecutor(a.workers) as pool:
        rows = [x for rs in pool.map(job, jobs) for x in rs]
    verdict = decide(rows)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(dict(rule="A1 §3.2 item 23 at 45644c89", wall_seconds=time.time() - t0,
                                     rows=rows, verdict=verdict), indent=1))
    print(json.dumps(verdict, indent=1))
    print(f"wall {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
