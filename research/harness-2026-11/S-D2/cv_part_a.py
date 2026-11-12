"""Fire-level cross-validation on NIROPS part a (Iris's test: is the higher rate the right rate?).

Covariate-free homogeneous spatial hazard (5x5 kernel + background), as in ``real_bracket_fit.py``. For each of
5 folds (fires sorted by name, fold = index mod 5), four estimators are fitted on the training fires, POOLED:

* ``plugin``          complete-data MLE with arrival = first observation time;
* ``composite``       sum of independent-bracket composite log-likelihoods;
* ``meanfield_nll``   sum of mean-field endpoint NLLs (forecast-v2 perimeter regime, NLL loss);
* ``mcem``            latent-time MCEM, with a per-fire Gibbs E-step and a joint M-step.

Each held-out fire is then forecast from every survey cutoff a (with a <= ``--hours``) to the next survey b,
starting from the exact mapped state at a. ``--sims`` exact forward Markov simulations per window give per-cell
P(burned by b). Scored on initially unburned real-grid cells within 4 km of the cutoff mapped extent (the S-D9
primary band rule):

* Brier;
* positives at p < 1e-5 and p < 1/1024;
* lowest-bin calibration gap over [0, 1e-3);
* predicted vs observed new-burn area;
* distance profile: share of new burn in (0,1], (1,2], (2,4] km, predicted vs observed.

This tests rate attribution, not forecast skill: there are no covariates and the rate is constant. Part-a data only
(see ``results/nirops_part_a_index.json``).

    python cv_part_a.py --brackets DIR --fit results/real_bracket_fit.json --workers 4 --out results/cv_part_a.json
"""
from __future__ import annotations

import argparse
import heapq
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import runenv

import numpy as np
from scipy.ndimage import distance_transform_edt
from scipy.optimize import minimize

import real_bracket_fit as F
import synthetic as S
import synthetic_robust as R

CELL_M = 375.0
BAND_M = 4000.0
RINGS_KM = [(0, 1), (1, 2), (2, 4)]


# ------------------------------------------------------------------ pooled fits

class FitFailed(RuntimeError):
    pass


def _lbfgs(f, D1, x0=None, floor=1e-9):
    """L-BFGS-B with a guard (after Owen's finding): an all-at-floor solution, a non-finite objective or gradient at
    the solution, or a solution worse than the start is a failed optimization, not a fit. It raises FitFailed."""
    x0 = np.full(D1, 0.02) if x0 is None else np.maximum(x0, 1e-4)
    res = minimize(f, x0, jac=True, method="L-BFGS-B", bounds=[(floor, None)] * D1,
                   options=dict(maxiter=3000, ftol=1e-12, gtol=1e-9))
    fx, gx = f(res.x)
    f0 = f(x0)[0]
    if np.all(res.x <= floor * (1 + 1e-6)) or not np.isfinite(fx) or not np.all(np.isfinite(gx)) or fx > f0:
        raise FitFailed(f"L-BFGS-B failed: all_at_floor={bool(np.all(res.x <= floor * (1 + 1e-6)))}, "
                        f"f={fx}, f0={f0}, finite_grad={bool(np.all(np.isfinite(gx)))}, msg={res.message}")
    return res.x


def pooled_complete(stats):
    """MLE of sum over fires of the complete-data log-likelihood. stats: list of (events, exposure)."""
    ev = np.concatenate([s[0] for s in stats])
    ex = np.sum([s[1] for s in stats], axis=0)

    def f(th):
        lam = ev @ th
        return -(np.log(lam).sum() - ex @ th), -(ev.T @ (1 / lam) - ex)
    return _lbfgs(f, ex.shape[0])


def fit_plugin(fires):
    stats = []
    for p, obs in fires:
        point = np.where(obs["burned"], obs["hi"], S.INF)
        stats.append(S.sufficient_stats(p, point))
    return pooled_complete(stats)


def _composite_objective(problem, obs):
    """Return f(theta) -> (nll, grad) of the independent-bracket composite (same as R.fit_bracket_composite)."""
    src, _ = S._neighbour_table(problem.n, problem.offs)
    T = problem.T
    burned = obs["burned"]
    lo = np.where(burned, obs["lo"], S.INF)
    hi = np.where(burned, obs["hi"], S.INF)
    lo[problem.seeds] = hi[problem.seeds] = 0.0
    not_seed = np.ones(problem.cells, bool)
    not_seed[problem.seeds] = False
    cells = np.flatnonzero(not_seed)
    s = src[cells]
    ok = s >= 0
    sc = np.clip(s, 0, None)
    na = np.where(ok, lo[sc], S.INF)
    nb = np.where(np.isfinite(na), hi[sc], S.INF)
    Li = np.where(burned[cells], lo[cells], T)
    Ui = hi[cells]
    bc = burned[cells]

    def logS(t, theta):
        f, g = R._uniform_exp_expect(t[:, None], na, nb, theta[1:][None, :])
        f = np.clip(f, 1e-300, None)
        return -theta[0] * t + np.log(f).sum(axis=1), np.concatenate([-t[:, None], g / f], axis=1)

    def nll(theta):
        la, ga = logS(Li, theta)
        lu, gu = logS(np.where(np.isfinite(Ui), Ui, T), theta)
        r = np.exp(np.minimum(lu - la, 0.0))
        om = np.clip(1.0 - r, 1e-300, None)
        val = np.where(bc, la + np.log(om), la)
        d = np.where(bc[:, None], (ga - r[:, None] * gu) / om[:, None], ga)
        return -val.sum(), -d.sum(axis=0)
    return nll


def fit_composite(fires):
    objs = [_composite_objective(p, o) for p, o in fires]

    def f(th):
        vals = [o(th) for o in objs]
        return sum(v[0] for v in vals), np.sum([v[1] for v in vals], axis=0)
    return _lbfgs(f, len(fires[0][0].k) + 1)


def fit_meanfield(fires):
    parts = []
    for p, obs in fires:
        tau = p.tau
        W, Tg, M = [], [], []
        for a, b in zip(obs["surveys"][:-1], obs["surveys"][1:]):
            st = (tau <= a).astype(float)
            if st.sum() == 0:
                continue
            W.append((st, int(round(b - a))))
            Tg.append((tau <= b).astype(float))
            M.append((st == 0).astype(float))
        parts.append((p, W, Tg, M))

    def f(th):
        tot, g = 0.0, np.zeros_like(th)
        for p, W, Tg, M in parts:
            v, gr = R._meanfield_loss_grad(p, th, W, Tg, M, "nll")
            tot += v
            g += gr
        return tot, g
    return _lbfgs(f, len(fires[0][0].k) + 1)


def fit_mcem(fires, rng, iterations=30, sweeps=3, keep=2, average_last=10, ckpt=None):
    """MCEM. With ``ckpt`` (a file path), the full chain state (iteration, theta, history, latent times and the RNG
    bit-generator state) is saved after every iteration and restored on restart, so a resumed run is bit-identical
    to an uninterrupted one."""
    import pickle
    samplers = [S.LatentSampler(p, o) for p, o in fires]
    start = 0
    if ckpt is not None and Path(ckpt).exists():
        st = pickle.loads(Path(ckpt).read_bytes())
        start, theta, hist, taus = st["it"], st["theta"], st["hist"], st["taus"]
        rng.bit_generator.state = st["rng"]
    else:
        taus = [s.initial() for s in samplers]
        theta = pooled_complete([S.sufficient_stats(p, t, s.src) for (p, _), t, s in zip(fires, taus, samplers)])
        hist = []
    for it in range(start, iterations):
        kept = [[] for _ in range(keep)]
        for j, ((p, _), s) in enumerate(zip(fires, samplers)):
            for sw in range(sweeps):
                taus[j] = s.sweep(taus[j], theta, rng)
                if sw >= sweeps - keep:
                    kept[sw - (sweeps - keep)].append(S.sufficient_stats(p, taus[j], s.src))
        combined = [(np.concatenate([x[0] for x in k]), np.sum([x[1] for x in k], axis=0)) for k in kept]
        theta = S.fit_complete(combined, x0=theta)
        hist.append(theta.copy())
        if ckpt is not None:
            tmp = Path(str(ckpt) + ".tmp")
            tmp.write_bytes(pickle.dumps(dict(it=it + 1, theta=theta, hist=hist, taus=taus,
                                              rng=rng.bit_generator.state)))
            tmp.replace(ckpt)
    return np.mean(hist[-average_last:], axis=0)


# ------------------------------------------------------------------ forecasting

def simulate_cells(problem, burned0, length, theta, rng):
    """One exact Markov forward run over a window; returns the burned mask at its end."""
    n, offs = problem.n, problem.offs
    k0, rates = theta[0], theta[1:]
    tau = np.full(n * n, S.INF)
    tau[burned0] = 0.0
    heap = [(0.0, int(i)) for i in np.flatnonzero(burned0)]
    if k0 > 0:
        bg = rng.exponential(1.0 / k0, size=n * n)
        for i in np.flatnonzero((bg <= length) & ~burned0):
            tau[i] = bg[i]
            heap.append((bg[i], int(i)))
    heapq.heapify(heap)
    done = np.zeros(n * n, bool)
    pos = rates > 0
    o, r_ = offs[pos], rates[pos]
    while heap:
        t, j = heapq.heappop(heap)
        if done[j] or t > length:
            continue
        done[j] = True
        r, c = divmod(j, n)
        tr, tc = r + o[:, 0], c + o[:, 1]
        ins = (tr >= 0) & (tr < n) & (tc >= 0) & (tc < n)
        tgt = tr[ins] * n + tc[ins]
        cand = t + rng.exponential(1.0 / r_[ins])
        better = (cand < tau[tgt]) & ~done[tgt] & (cand <= length)
        for i, v in zip(tgt[better], cand[better]):
            if v < tau[i]:
                tau[i] = v
                heapq.heappush(heap, (v, int(i)))
    return done


def score_fire(path, hours, thetas, sims, seed):
    """Per-cell scores for one held-out fire under each fitted theta."""
    p, obs = F.load_fire(Path(path), hours, 0)
    z = np.load(path)
    h, w = z["first_survey"].shape
    real = np.zeros((p.n, p.n), bool)
    real[:h, :w] = True
    real = real.ravel()
    hi_t = np.where(obs["burned"], obs["hi"], S.INF)
    out = {name: dict(p=[], y=[], dist=[]) for name in thetas}
    for a, b in zip(obs["surveys"][:-1], obs["surveys"][1:]):
        start = hi_t <= a
        if not start.any():
            continue
        y = (hi_t > a) & (hi_t <= b)
        dist = distance_transform_edt(~start.reshape(p.n, p.n)).ravel() * CELL_M
        pop = real & ~start & (dist <= BAND_M)
        for name, th in thetas.items():
            rng = np.random.default_rng(seed)
            cnt = np.zeros(p.cells)
            for _ in range(sims):
                cnt += simulate_cells(p, start, float(b - a), th, rng)
            out[name]["p"].append(cnt[pop] / sims)
            out[name]["y"].append(y[pop].astype(np.int8))
            out[name]["dist"].append(dist[pop])
    return {k: {kk: np.concatenate(vv) if vv else np.array([]) for kk, vv in v.items()} for k, v in out.items()}


def metrics(pv, yv, dv):
    if len(pv) == 0:
        return None
    low = pv < 1e-3
    prof = {}
    for lo_km, hi_km in RINGS_KM:
        m = (dv > lo_km * 1000) & (dv <= hi_km * 1000)
        prof[f"{lo_km}-{hi_km}km"] = dict(pred=float(pv[m].sum()), obs=int(yv[m].sum()))
    return dict(cells=int(len(pv)), positives=int(yv.sum()), brier=float(np.mean((pv - yv) ** 2)),
                pos_below_1e5=int(((pv < 1e-5) & (yv == 1)).sum()),
                pos_below_1_1024=int(((pv < 1 / 1024) & (yv == 1)).sum()),
                lowbin_gap=float(abs(pv[low].mean() - yv[low].mean())) if low.any() else None,
                lowbin_n=int(low.sum()), pred_area=float(pv.sum()), obs_area=int(yv.sum()), profile=prof)


# ------------------------------------------------------------------ folds

def _ckpt_write(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj))
    tmp.replace(path)


def _beat(ckpt, fold, msg):
    if ckpt:
        Path(ckpt).mkdir(parents=True, exist_ok=True)
        with open(Path(ckpt) / f"fold{fold}.heartbeat.log", "a") as fh:
            fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {msg}\n")


def run_fold(args):
    """One fold. With a checkpoint dir, saves the fitted thetas and every scored test fire as they finish, so a
    restart resumes inside the fold. Seeds are unchanged (fit: 424242 + fold; fire i: 77_000 + 31*fold + i), so a
    resumed fold equals an uninterrupted one."""
    fold, train, test, bdir, hours, sims, ckpt = args
    key = dict(train=train, test=test, sims=sims, hours=hours)
    if ckpt:
        cp = Path(ckpt) / f"fold{fold}.json"
        if cp.exists():
            r = json.loads(cp.read_text())
            if all(r[k] == v for k, v in key.items()):
                return r
    t0 = time.time()
    tp = Path(ckpt) / f"fold{fold}.thetas.json" if ckpt else None
    if tp is not None and tp.exists() and all(json.loads(tp.read_text())[k] == v for k, v in key.items()):
        saved = json.loads(tp.read_text())
        thetas = {k: np.asarray(v) for k, v in saved["thetas"].items()}
        fit_s = saved["fit_seconds"]
        _beat(ckpt, fold, "thetas loaded from checkpoint")
    else:
        _beat(ckpt, fold, "fit start")
        fires = [F.load_fire(Path(bdir) / f"{f}.npz", hours, 0) for f in train]
        fitters = {"plugin": lambda: fit_plugin(fires), "composite": lambda: fit_composite(fires),
                   "meanfield_nll": lambda: fit_meanfield(fires),
                   "mcem": lambda: fit_mcem(fires, np.random.default_rng(424242 + fold),
                                            ckpt=Path(ckpt) / f"fold{fold}.mcem_state.pkl" if ckpt else None)}
        thetas = {}
        for name, fn in fitters.items():       # each estimator's theta is checkpointed on its own
            ep = Path(ckpt) / f"fold{fold}.theta_{name}.json" if ckpt else None
            if ep is not None and ep.exists() and all(json.loads(ep.read_text())[k] == v for k, v in key.items()):
                thetas[name] = np.asarray(json.loads(ep.read_text())["theta"])
                _beat(ckpt, fold, f"{name} loaded from checkpoint")
                continue
            thetas[name] = fn()
            if ep is not None:
                _ckpt_write(ep, dict(key, theta=thetas[name].tolist()))
            _beat(ckpt, fold, f"{name} fitted")
        fit_s = time.time() - t0
        if tp is not None:
            _ckpt_write(tp, dict(key, thetas={k: v.tolist() for k, v in thetas.items()}, fit_seconds=fit_s))
        _beat(ckpt, fold, f"fit done {fit_s:.0f}s")
    per_fire = {}
    for i, f in enumerate(test):
        fp = Path(ckpt) / f"fold{fold}.fire{i}.json" if ckpt else None
        if fp is not None and fp.exists():
            per_fire[f] = json.loads(fp.read_text())["scores"]
            _beat(ckpt, fold, f"fire {i} loaded from checkpoint")
            continue
        sc = score_fire(str(Path(bdir) / f"{f}.npz"), hours, thetas, sims, 77_000 + 31 * fold + i)
        per_fire[f] = {k: dict(p=v["p"].tolist(), y=v["y"].tolist(), dist=v["dist"].tolist()) for k, v in sc.items()}
        if fp is not None:
            _ckpt_write(fp, dict(fire=f, scores=per_fire[f]))
        _beat(ckpt, fold, f"fire {i} scored")
    out = dict(fold=fold, env=runenv.info(), train=train, test=test, sims=sims, hours=hours,
               thetas={k: v.tolist() for k, v in thetas.items()},
               fit_seconds=fit_s, total_seconds=time.time() - t0, per_fire=per_fire)
    if ckpt:                       # per-fold checkpoint: a container restart costs at most the running stage
        _ckpt_write(Path(ckpt) / f"fold{fold}.json", out)
        _beat(ckpt, fold, "fold done")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--brackets", type=Path, required=True)
    ap.add_argument("--fit", type=Path, default=Path("results/real_bracket_fit.json"))
    ap.add_argument("--hours", type=float, default=240.0)
    ap.add_argument("--sims", type=int, default=1024)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))
    ap.add_argument("--out", type=Path, default=Path("results/cv_part_a.json"))
    ap.add_argument("--checkpoint-dir", type=Path, default=None,
                    help="write each finished fold here and reuse it on rerun (same train/test/sims/hours)")
    ap.add_argument("--only-fold", type=int, default=None,
                    help="run just this fold (writes its checkpoint) and exit; needs --checkpoint-dir")
    a = ap.parse_args(argv)
    runenv.require_pinned()
    fires = sorted(json.loads(a.fit.read_text())["eligible"])
    folds = [[f for i, f in enumerate(fires) if i % a.folds == k] for k in range(a.folds)]
    jobs = [(k, [f for f in fires if f not in folds[k]], folds[k], str(a.brackets), a.hours, a.sims,
             str(a.checkpoint_dir) if a.checkpoint_dir else None)
            for k in range(a.folds)]
    t0 = time.time()
    if a.only_fold is not None:
        assert a.checkpoint_dir is not None
        run_fold(jobs[a.only_fold])
        return
    with ProcessPoolExecutor(a.workers) as pool:
        res = list(pool.map(run_fold, jobs))
    names = ["plugin", "composite", "meanfield_nll", "mcem"]
    pooled, per_fire = {}, {}
    for n in names:
        P = np.concatenate([np.array(r["per_fire"][f][n]["p"]) for r in res for f in r["test"]])
        Y = np.concatenate([np.array(r["per_fire"][f][n]["y"]) for r in res for f in r["test"]])
        Dd = np.concatenate([np.array(r["per_fire"][f][n]["dist"]) for r in res for f in r["test"]])
        pooled[n] = metrics(P, Y, Dd)
    for r in res:
        for f in r["test"]:
            per_fire[f] = {n: metrics(np.array(r["per_fire"][f][n]["p"]), np.array(r["per_fire"][f][n]["y"]),
                                      np.array(r["per_fire"][f][n]["dist"])) for n in names}
    # Paired per-fire Brier difference vs mcem, with a fire bootstrap of the pooled difference.
    rng = np.random.default_rng(20261030)
    fl = list(per_fire)
    boot = {}
    for n in ("plugin", "composite", "meanfield_nll"):
        se = np.array([per_fire[f][n]["brier"] * per_fire[f][n]["cells"] for f in fl])
        sm = np.array([per_fire[f]["mcem"]["brier"] * per_fire[f]["mcem"]["cells"] for f in fl])
        nc = np.array([per_fire[f]["mcem"]["cells"] for f in fl])
        draws = []
        for _ in range(10_000):
            idx = rng.integers(0, len(fl), len(fl))
            draws.append((sm[idx].sum() - se[idx].sum()) / nc[idx].sum())
        boot[f"mcem_minus_{n}"] = dict(point=float((sm.sum() - se.sum()) / nc.sum()),
                                       ci95=[float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))],
                                       mcem_better_fires=f"{int(sum(per_fire[f]['mcem']['brier'] < per_fire[f][n]['brier'] for f in fl))}/{len(fl)}")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(dict(
        command="python cv_part_a.py " + " ".join(argv or os.sys.argv[1:]), env=runenv.info(), hours=a.hours, sims=a.sims, folds=folds,
        band_m=BAND_M, wall_seconds=time.time() - t0, thetas={r["fold"]: r["thetas"] for r in res},
        fit_seconds={r["fold"]: r["fit_seconds"] for r in res}, pooled=pooled, brier_diff_vs_mcem=boot,
        per_fire=per_fire), indent=1))
    print(json.dumps(dict(pooled=pooled, brier_diff_vs_mcem=boot), indent=1))
    print(f"wall {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
