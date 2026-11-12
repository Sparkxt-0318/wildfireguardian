"""Feature ablation for the mean-field NLL far-share gap (Iris). Rule: TOLERANCE_feature_ablation.md (01d7c466).

Truth: the ``low_far`` kernel of run_shape_recovery.py (far_share 0.072), on the same 64x64 grid, with T = 240 h,
24 h perimeter brackets, 5 seeds (0-4) and the same estimators (plug-in, composite, mean-field NLL, MCEM_SHORT at a
0.1 h step). Each arm adds ONE real-data feature. All feature scales below were fixed in this docstring and committed
before any run of this file. They are not tuned on estimator outputs.

* ``baseline``: no feature (the generator of run_shape_recovery.py).
* ``state_error``: perimeter-mapping error in the survey-time states. Each newly burned (non-seed) cell has its
  observed bracket moved by one survey with probability p = 0.20 (half earlier, half later, clipped to the survey
  range). A cell moved past the last survey is reported unburned. A priori scale: a 375 m NIROPS cell is about one
  pixel of mapping offset, and about a fifth of new cells lie within one pixel of the advancing edge at the median
  part-a interval growth. This is stated, not measured.
* ``time_varying``: a piecewise-constant multiplicative rate per 24 h day.
  - m_d = lognormal(0, 1.0). With probability 0.2 the day is quiet instead, with m_d = 0.05.
  - The multipliers are rescaled so that mean(m) = 1 over the 10 days.
  - Simulated exactly as a time change: arrivals in operational time s with rates k, then t = M^{-1}(s), where
    M(t) = ∫ m. This is exact for first passage under a uniform modulator.
* ``barriers``: unburnable patches covering 15% of non-seed cells. They are the lowest 15% of Gaussian-smoothed
  white noise (sigma 3 cells) and never ignite or spread. The fitters do not know about them.
* ``detached``: spotting at distance 5-6 downwind (synthetic_robust.spotting_offsets), outside the fitted radius 2.
  - The spotting rate is calibrated ONLY to the measured part-a share of 0.15. The calibration target is the share of
    24 h intervals in which at least one newly burned cell arrived through a spotting offset; the simulator tracks
    this.
  - Calibration uses calibration seeds 100-109, not the evaluation seeds, over the grid of rates in CAL_RATES. It
    picks the rate whose share is closest to 0.15 and records the calibration table.
  - No estimator is fitted during calibration.
  - DESIGN REVISION, made before any estimator run (generator-only check, about 13:20 UTC). The first draft calibrated the
    displacement_diag "detached" flag (the farthest new cell's 8-connected component has no cutoff-burned cell). On
    the synthetic baseline WITHOUT spotting, that flag is already 0.7-0.8 per interval. The reasons are the ~20
    background ignitions (k0 = 2e-5 over 64x64 cells and 240 h), which the fitters model through k0, and radius-2
    jumps that break 8-connectivity. So 0.15 was unattainable and not comparable. The flag is still reported per arm
    as `detached_share`. The first CAL_RATES grid (1e-4 to 3.2e-3) gave spot-interval shares of 0.70 and above,
    because every burned cell keeps emitting. The grid was moved down to 2.5e-7 to 1.6e-5 and then refined between
    8e-6 and 1.6e-5 (8e-6 gave 0.08 and 1.6e-5 gave 0.25), again before any estimator run.

    python feature_ablation.py --workers 4 --out results/feature_ablation.json
"""
from __future__ import annotations

import argparse
import heapq
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt, gaussian_filter, label

import run_shape_recovery as X
import synthetic as S
import synthetic_robust as R
from synthetic import INF

ARMS = ["baseline", "state_error", "time_varying", "barriers", "detached"]
P_SHIFT = 0.20
TV_SIGMA, TV_QUIET_P, TV_QUIET_M = 1.0, 0.2, 0.05
BARRIER_FRAC, BARRIER_SIGMA = 0.15, 3.0
DETACHED_TARGET = 0.15
CAL_RATES = [2.5e-7, 5e-7, 1e-6, 2e-6, 4e-6, 8e-6, 1e-5, 1.2e-5, 1.4e-5, 1.6e-5]
CAL_SEEDS = range(100, 110)


def simulate(p, rng, *, spot=None, blocked=None, T_sim=None, via_spot=None):
    """simulate_fpp (shape 1) with optional extra spotting offsets, blocked cells and horizon T_sim.

    If ``via_spot`` (bool array, n*n) is given, it is set True for cells whose final arrival came via a spot offset."""
    n = p.n
    T = p.T if T_sim is None else T_sim
    offs, rates = p.offs, p.k
    if spot is not None:
        offs = np.concatenate([offs, spot[0]])
        rates = np.concatenate([rates, spot[1]])
    tau = np.full(n * n, INF)
    heap = []
    for s in p.seeds:
        tau[s] = 0.0
        heap.append((0.0, int(s)))
    bg = rng.exponential(1.0 / p.k0, size=n * n)
    for i in np.flatnonzero(bg <= T):
        if (blocked is None or not blocked[i]) and tau[i] > bg[i]:
            tau[i] = bg[i]
            heap.append((bg[i], int(i)))
    heapq.heapify(heap)
    done = np.zeros(n * n, bool)
    while heap:
        t, j = heapq.heappop(heap)
        if done[j] or t > T:
            continue
        done[j] = True
        r, c = divmod(j, n)
        tr, tc = r + offs[:, 0], c + offs[:, 1]
        ok = (tr >= 0) & (tr < n) & (tc >= 0) & (tc < n)
        tgt = tr[ok] * n + tc[ok]
        k = rates[ok]
        is_spot = (np.arange(len(offs)) >= len(p.offs))[ok]
        cand = t + rng.exponential(1.0 / k)
        better = (cand < tau[tgt]) & ~done[tgt] & (cand <= T)
        if blocked is not None:
            better &= ~blocked[tgt]
        for i, v, sp in zip(tgt[better], cand[better], is_spot[better]):
            if v < tau[i]:
                tau[i] = v
                if via_spot is not None:
                    via_spot[i] = sp
                heapq.heappush(heap, (v, int(i)))
    tau[tau > T] = INF
    return tau


def spot_interval_share(tau, via_spot, T, every=X.EVERY):
    surveys = np.arange(0.0, T + 1e-9, every)
    flags = [bool(via_spot[(tau > a) & (tau <= b)].any()) for a, b in zip(surveys[:-1], surveys[1:])
             if ((tau > a) & (tau <= b)).any()]
    return float(np.mean(flags)) if flags else 0.0


def base_problem(seed):
    """Same truth and seeds as run_shape_recovery.make (without simulating)."""
    cfg = X.KERNELS["low_far"]
    rng = np.random.default_rng(seed)
    offs = S.offsets(2)
    k = S.true_kernel(offs, scale=cfg["scale"], length=cfg["length"])
    n, c = X.N, X.N // 2
    seeds = np.unique([int(rng.integers(c - 6, c + 7)) * n + int(rng.integers(c - 6, c + 7)) for _ in range(6)])
    return S.Problem(n=n, offs=offs, k=k, k0=2e-5, T=X.T, seeds=seeds), rng


def detached_share(p, every=X.EVERY):
    n = p.n
    surveys = np.arange(0.0, p.T + 1e-9, every)
    flags = []
    for a, b in zip(surveys[:-1], surveys[1:]):
        start = (p.tau <= a)
        new = (p.tau > a) & (p.tau <= b)
        if not new.any() or not start.any():
            continue
        dist = distance_transform_edt(~start.reshape(n, n)).ravel()
        far = np.flatnonzero(new)[np.argmax(dist[new])]
        comp, _ = label((start | new).reshape(n, n), structure=np.ones((3, 3)))
        comp = comp.ravel()
        flags.append(not start[comp == comp[far]].any())
    return float(np.mean(flags)) if flags else 0.0


def generate(arm, seed, spot_rate=None):
    p, rng = base_problem(seed)
    info = {}
    if arm in ("baseline", "state_error"):
        p.tau = R.simulate_fpp(p, rng)  # identical to run_shape_recovery for baseline
    elif arm == "time_varying":
        days = int(np.ceil(p.T / 24.0))
        m = np.exp(rng.normal(0.0, TV_SIGMA, days))
        m[rng.random(days) < TV_QUIET_P] = TV_QUIET_M
        m = m / m.mean()
        edges = np.arange(days + 1) * 24.0
        M = np.concatenate([[0.0], np.cumsum(m * 24.0)])
        s = simulate(p, rng, T_sim=M[-1])
        t = np.full_like(s, INF)
        fin = np.isfinite(s)
        d = np.clip(np.searchsorted(M, s[fin], side="right") - 1, 0, days - 1)
        t[fin] = edges[d] + (s[fin] - M[d]) / m[d]
        t[p.seeds] = 0.0
        p.tau = t
        info["multipliers"] = m.round(3).tolist()
    elif arm == "barriers":
        noise = gaussian_filter(rng.normal(size=(p.n, p.n)), BARRIER_SIGMA).ravel()
        cand = np.ones(p.n * p.n, bool)
        cand[p.seeds] = False
        thr = np.quantile(noise[cand], BARRIER_FRAC)
        blocked = cand & (noise <= thr)
        p.tau = simulate(p, rng, blocked=blocked)
        info["blocked_frac"] = float(blocked.mean())
    elif arm == "detached":
        vs = np.zeros(p.n * p.n, bool)
        p.tau = simulate(p, rng, spot=R.spotting_offsets(rate=spot_rate), via_spot=vs)
        info["spot_rate"] = spot_rate
        info["spot_interval_share"] = spot_interval_share(p.tau, vs, p.T)
    obs = S.observe_perimeter(p, every=X.EVERY)
    if arm == "state_error":
        srng = np.random.default_rng([seed, 0x5E])
        surveys = obs["surveys"]
        movable = np.flatnonzero(obs["burned"])
        movable = movable[~np.isin(movable, p.seeds)]
        hit = movable[srng.random(len(movable)) < P_SHIFT]
        k = np.searchsorted(surveys, obs["hi"][hit])
        k = k + np.where(srng.random(len(hit)) < 0.5, -1, 1)
        k = np.clip(k, 1, len(surveys))
        gone = k >= len(surveys)
        keep = hit[~gone]
        obs["hi"][keep] = surveys[k[~gone]]
        obs["lo"][keep] = surveys[k[~gone] - 1]
        drop = hit[gone]
        obs["burned"][drop] = False
        obs["lo"][drop] = obs["hi"][drop] = np.nan
        info["shifted"] = int(len(hit))
        info["dropped_past_last"] = int(gone.sum())
    info["detached_share"] = detached_share(p)
    info["burned"] = int(np.isfinite(p.tau).sum())
    return p, obs, info


def calibrate():
    table = []
    for r in CAL_RATES:
        shares = [generate("detached", s, spot_rate=r)[2]["spot_interval_share"] for s in CAL_SEEDS]
        table.append(dict(rate=r, share_mean=float(np.mean(shares))))
    best = min(table, key=lambda x: abs(x["share_mean"] - DETACHED_TARGET))
    return best["rate"], table


def job(args):
    arm, seed, spot_rate = args
    p, obs, info = generate(arm, seed, spot_rate)
    point = np.where(obs["burned"], obs["hi"], S.INF)
    point[p.seeds] = 0.0
    src, _ = S._neighbour_table(p.n, p.offs)
    fits = {
        "plugin": lambda: S.fit_complete([S.sufficient_stats(p, point, src)]),
        "composite": lambda: R.fit_bracket_composite(p, obs),
        "meanfield_nll": lambda: R.fit_meanfield(p, obs, loss="nll"),
        "mcem": lambda: S.mcem(p, obs, np.random.default_rng(31_000 + seed), **R.MCEM_SHORT)[0],
    }
    rows = []
    for est, fn in fits.items():
        t0 = time.perf_counter()
        th = fn()
        rows.append(dict(arm=arm, seed=seed, estimator=est, far_share=X.far_share(th, p.offs),
                         total=float(np.sum(th[1:])), true_total=float(p.k.sum()),
                         seconds=time.perf_counter() - t0, **info))
    return rows


def verdicts(summary, true_share):
    out = {}
    for arm, s in summary.items():
        m = s["mcem"]
        mcem_ok = abs(m["far_share_mean"] - true_share) <= 0.05 and m["far_share_sd"] <= 0.05
        nll_up = s["meanfield_nll"]["far_share_mean"] > 0.40
        out[arm] = "the cause" if (nll_up and mcem_ok) else ("both affected" if nll_up else "not the cause")
        out[arm] += f" (NLL {s['meanfield_nll']['far_share_mean']:.3f}; MCEM within tolerance: {mcem_ok})"
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--arms", nargs="+", default=ARMS)
    ap.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))
    ap.add_argument("--out", type=Path, default=Path("results/feature_ablation.json"))
    a = ap.parse_args(argv)
    t0 = time.time()
    spot_rate, cal = (calibrate() if "detached" in a.arms else (None, None))
    jobs = [(arm, s, spot_rate) for arm in a.arms for s in range(a.seeds)]
    with ProcessPoolExecutor(a.workers) as pool:
        rows = [r for rs in pool.map(job, jobs) for r in rs]
    true_share = X.far_share(np.concatenate([[0.0], base_problem(0)[0].k]), S.offsets(2))
    summary = {}
    for arm in a.arms:
        summary[arm] = {}
        for est in ("plugin", "composite", "meanfield_nll", "mcem"):
            fs = np.array([r["far_share"] for r in rows if r["arm"] == arm and r["estimator"] == est])
            summary[arm][est] = dict(far_share_mean=float(fs.mean()), far_share_sd=float(fs.std(ddof=1)))
        summary[arm]["detached_share_mean"] = float(np.mean([r["detached_share"] for r in rows
                                                             if r["arm"] == arm and r["estimator"] == "mcem"]))
    out = dict(command="python feature_ablation.py " + " ".join(argv or sys.argv[1:]), true_far_share=true_share,
               spot_rate=spot_rate, calibration=cal, wall_seconds=time.time() - t0, summary=summary,
               verdicts=verdicts(summary, true_share), rows=rows)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=1))
    print(json.dumps(dict(summary=summary, verdicts=out["verdicts"], calibration=cal), indent=1))


if __name__ == "__main__":
    main()
