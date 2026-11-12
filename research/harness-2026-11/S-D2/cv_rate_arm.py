"""Between-fire rate arm on the MCEM kernel (Iris item 2). Rule: RULE_rate_arm.md (ba71e7ca, before this code).

Per test fire and interval, SIMS exact simulations of the fold's MCEM kernel are run to 2T and the arrival time of
every cell is recorded. A uniform rate multiplier m is an exact time change, so p_m = P(tau <= m*T) for every grid
value comes from the same runs. Forecast: the prior-anchored online Bayesian mixture over m. The weights use only
the fire's EARLIER intervals. Checkpoints are kept per fire, so a restart costs at most one fire.

    python cv_rate_arm.py --brackets DIR --cv results/cv_part_a.json --ckpt DIR --only-fold k   (per fold)
    python cv_rate_arm.py --brackets DIR --cv results/cv_part_a.json --ckpt DIR --out results/cv_rate_arm.json
"""
from __future__ import annotations

import argparse
import heapq
import json
import sys
import time
from pathlib import Path

import numpy as np

import cv_baselines as CB
import cv_part_a as C
import real_bracket_fit as F
import synthetic as S

GRID = np.array([1 / 16, 1 / 8, 1 / 4, 1 / 2, 1.0, 2.0])
PRIOR = np.array([0.1, 0.1, 0.1, 0.1, 0.5, 0.1])
SIMS = 512
TMAX = 2.0


def simulate_times(problem, burned0, length, theta, rng):
    """cv_part_a.simulate_cells, but returns arrival times (inf if not burned by ``length``)."""
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
    tau[~done] = S.INF
    return tau


def score_fire(path, hours, theta, seed):
    p, obs = F.load_fire(Path(path), hours, 0)
    rows = CB.fire_cells(path, hours)
    eps = 1.0 / (SIMS + 1)
    logw = np.log(PRIOR)
    out = dict(p_mix=[], p_m1=[], p_grid=[], y=[], dist=[], w_before=[])
    rng = np.random.default_rng(seed)
    for r in rows:
        start = r["start"].ravel()
        T = r["T"]
        cnt = np.zeros((len(GRID), int(r["pop"].sum())))
        for _ in range(SIMS):
            tau = simulate_times(p, start, TMAX * T, np.asarray(theta), rng)[r["pop"]]
            cnt += tau[None, :] <= (GRID[:, None] * T)
        pm = cnt / SIMS
        w = np.exp(logw - logw.max())
        w /= w.sum()
        out["w_before"].append(w.tolist())
        out["p_mix"].append(w @ pm)
        out["p_m1"].append(pm[GRID == 1.0][0])
        out["p_grid"].append(pm.astype(np.float32))
        out["y"].append(r["y"])
        out["dist"].append(r["dist"])
        pc = np.clip(pm, eps, 1 - eps)          # update with THIS interval only after forecasting it
        y = r["y"].astype(bool)
        logw = logw + np.where(y[None, :], np.log(pc), np.log1p(-pc)).sum(1)
    res = {k: (np.concatenate(v).tolist() if k not in ("w_before", "p_grid") else v) for k, v in out.items()}
    res["p_grid"] = np.concatenate(out["p_grid"], axis=1).tolist() if out["p_grid"] else []
    res["n_per_interval"] = [int(r["pop"].sum()) for r in rows]
    return res


def run_fold(cv, k, a):
    fs = cv["folds"][k]
    theta = cv["thetas"][str(k)]["mcem"]
    for i, f in enumerate(fs):
        fp = a.ckpt / f"rate_fold{k}.fire{i}.json"
        if fp.exists():
            continue
        t0 = time.time()
        res = score_fire(a.brackets / f"{f}.npz", a.hours, theta, 88_000 + 31 * k + i)
        res.update(fire=f, seconds=time.time() - t0)
        tmp = fp.with_suffix(".tmp")
        tmp.write_text(json.dumps(res))
        tmp.replace(fp)
        print(f"fold {k} fire {i} done {time.time() - t0:.0f}s", flush=True)


def signflip_p(d, rng, n=10_000):
    obs = d.sum()
    flips = rng.choice([-1.0, 1.0], size=(n, len(d)))
    return float((1 + (np.abs((flips * d).sum(1)) >= abs(obs)).sum()) / (n + 1))


def aggregate(cv, a):
    base = json.loads(a.baselines.read_text())
    folds = cv["folds"]
    recs = {}
    for k, fs in enumerate(folds):
        for i, f in enumerate(fs):
            recs[f] = json.loads((a.ckpt / f"rate_fold{k}.fire{i}.json").read_text())
    # comparators on identical cells: recompute from the CV checkpoints and the baselines script
    fires = [f for fs in folds for f in fs]
    Y = {f: np.asarray(recs[f]["y"]) for f in fires}
    P = {"mcem_rate": {f: np.asarray(recs[f]["p_mix"]) for f in fires},
         "mcem_m1_512": {f: np.asarray(recs[f]["p_m1"]) for f in fires}}
    for k, fs in enumerate(folds):
        ck = json.loads((a.cv_ckpt / f"fold{k}.json").read_text())
        for f in fs:
            if not np.array_equal(np.asarray(ck["per_fire"][f]["mcem"]["y"]), Y[f]):
                raise ValueError(f"cells differ from CV: {f}")
            for m in ("plugin", "mcem"):
                P.setdefault(m, {})[f] = np.asarray(ck["per_fire"][f][m]["p"])
    # logistic_cf / persistence / dilation_8h, refitted exactly as in cv_baselines (same folds, same seed)
    cells = {f: CB.fire_cells(a.brackets / f"{f}.npz", a.hours) for f in fires}
    for k, fs in enumerate(folds):
        train = [f for f in fires if f not in fs]
        ytr = np.concatenate([np.concatenate([r["y"] for r in cells[f]]) for f in train])
        lg = CB.fit_logistic(np.concatenate([CB.feats(cells[f]) for f in train]), ytr, seed=0)
        for f in fs:
            P.setdefault("logistic_cf", {})[f] = CB.predict_logistic(lg, CB.feats(cells[f]))
            P.setdefault("persistence", {})[f] = np.zeros(len(Y[f]))
            P.setdefault("dilation_8h", {})[f] = CB.preds_baselines(cells[f], 8)
    # quiet/active-per-interval arm: grid weights fitted by EM on OTHER folds' intervals only
    grid_p = {f: np.asarray(recs[f]["p_grid"], dtype=np.float64) for f in fires}
    eps = 1.0 / (SIMS + 1)
    state_w = {}
    for k, fs in enumerate(folds):
        other = [f for f in fires if f not in fs]
        L = []                                    # per-interval log-likelihood under each grid value
        for f in other:
            pc = np.clip(grid_p[f], eps, 1 - eps)
            y = Y[f].astype(bool)
            ll = np.where(y[None, :], np.log(pc), np.log1p(-pc))
            edges = np.cumsum([0] + recs[f]["n_per_interval"])
            L += [ll[:, a:b].sum(1) for a, b in zip(edges[:-1], edges[1:])]
        L = np.array(L)                           # [intervals, grid]
        pi = np.full(len(GRID), 1.0 / len(GRID))
        for _ in range(500):
            lw = L + np.log(pi)[None, :]
            r = np.exp(lw - lw.max(1, keepdims=True))
            r /= r.sum(1, keepdims=True)
            new = r.mean(0)
            if np.abs(new - pi).max() < 1e-10:
                pi = new
                break
            pi = new
        state_w[k] = pi.tolist()
        for f in fs:
            P.setdefault("mcem_state", {})[f] = pi @ grid_p[f]
    D = {f: np.asarray(recs[f]["dist"]) for f in fires}
    ally = np.concatenate([Y[f] for f in fires])
    alld = np.concatenate([D[f] for f in fires])
    pooled = {}
    for m, pm in P.items():
        pv = np.concatenate([pm[f] for f in fires])
        r = dict(brier=float(np.mean((pv - ally) ** 2)))
        for lo, hi in CB.BANDS:
            s = (alld > lo) & (alld <= hi)
            r[f"brier_{lo // 1000}-{hi // 1000}km"] = float(np.mean((pv[s] - ally[s]) ** 2))
        pooled[m] = r
    for m in ("logistic_cf", "plugin"):
        if abs(pooled[m]["brier"] - base["pooled"][m]["brier"]) > 1e-12:
            raise ValueError(f"{m} differs from cv_baselines: {pooled[m]['brier']} vs {base['pooled'][m]['brier']}")
    err = {m: np.array([np.sum((P[m][f] - Y[f]) ** 2) for f in fires]) for m in P}
    n = np.array([len(Y[f]) for f in fires])
    rng = np.random.default_rng(20261112)
    draws = rng.integers(0, len(fires), size=(10_000, len(fires)))
    comp = {}
    for arm, ref in [(a_, r_) for a_ in ("mcem_rate", "mcem_state")
                     for r_ in ("plugin", "logistic_cf", "mcem", "persistence")] + [("mcem_rate", "mcem_state")]:
        d = err[arm] - err[ref]
        bs = d[draws].sum(1) / n[draws].sum(1)
        comp[f"{arm}_minus_{ref}"] = dict(
            point=float(d.sum() / n.sum()), ci95=[float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))],
            signflip_p=signflip_p(d, np.random.default_rng(20261112)),
            better_fires=f"{int((d < 0).sum())}/{len(fires)}")
    qual = {arm: all(comp[f"{arm}_minus_{r}"]["ci95"][1] < 0 and comp[f"{arm}_minus_{r}"]["signflip_p"] < 0.05
                     for r in ("plugin", "logistic_cf")) for arm in ("mcem_rate", "mcem_state")}
    # Iris's reporting additions (no rule change)
    first = {f: np.zeros(len(Y[f]), bool) for f in fires}
    for f in fires:
        first[f][: recs[f]["n_per_interval"][0]] = True
    split = {}
    for m in ("mcem_rate", "mcem", "plugin", "logistic_cf", "persistence"):
        for name, sel in (("first_interval", True), ("later_intervals", False)):
            pv = np.concatenate([P[m][f][first[f] == sel] for f in fires])
            yv = np.concatenate([Y[f][first[f] == sel] for f in fires])
            split.setdefault(name, {})[m] = dict(brier=float(np.mean((pv - yv) ** 2)), cells=int(len(yv)))
    edge = dict(
        state_weight_bottom_top_by_fold={k: [w[0], w[-1]] for k, w in state_w.items()},
        rate_weight_bottom_top_mean_over_intervals=[
            float(np.mean([w[0] for f in fires for w in recs[f]["w_before"]])),
            float(np.mean([w[-1] for f in fires for w in recs[f]["w_before"]]))],
        rate_intervals_with_over_half_weight_at_bottom=int(sum(w[0] > 0.5 for f in fires for w in recs[f]["w_before"])),
        rate_intervals_with_over_half_weight_at_top=int(sum(w[-1] > 0.5 for f in fires for w in recs[f]["w_before"])),
        rate_intervals_total=int(sum(len(recs[f]["w_before"]) for f in fires)))
    note = ("Two arms are each tested against two bars (four tests) with no multiplicity adjustment. Grid edges: "
            "1/16 at the bottom, 2 at the top (simulations run to 2T). Weight piled at an edge means the result is a "
            "lower bound on what the idea can do.")
    post = {f: dict(final_mean_m=float(np.dot(recs[f]["w_before"][-1], GRID)),
                    final_w_m1=float(recs[f]["w_before"][-1][int(np.flatnonzero(GRID == 1.0)[0])]))
            for f in fires}
    out = dict(command="python cv_rate_arm.py " + " ".join(sys.argv[1:]), rule="RULE_rate_arm.md @ ba71e7ca + addendum",
               grid=GRID.tolist(), prior=PRIOR.tolist(), sims=SIMS, pooled=pooled, comparisons=comp,
               qualifies_for_part_b_consideration=qual, multiplicity_note=note, state_weights_by_fold=state_w,
               grid_edge_weights=edge, first_vs_later_intervals=split,
               posterior_last_interval=post)
    a.out.write_text(json.dumps(out, indent=1))
    for m, r in sorted(pooled.items(), key=lambda kv: kv[1]["brier"]):
        print(f"{m:13s} {r['brier']:.4f}  " + "  ".join(f"{b} {r['brier_' + b]:.4f}" for b in ("0-1km", "1-2km", "2-4km")))
    print(json.dumps(comp, indent=1))
    print("QUALIFIES:", qual)
    print(json.dumps(dict(edge=edge, first_vs_later=split), indent=1))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--brackets", type=Path, required=True)
    ap.add_argument("--cv", type=Path, default=Path("results/cv_part_a.json"))
    ap.add_argument("--cv-ckpt", type=Path, required=True, help="cv_part_a fold checkpoints (for identical cells)")
    ap.add_argument("--baselines", type=Path, default=Path("results/cv_baselines.json"))
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--hours", type=float, default=240.0)
    ap.add_argument("--only-fold", type=int, default=None)
    ap.add_argument("--out", type=Path, default=Path("results/cv_rate_arm.json"))
    a = ap.parse_args(argv)
    a.ckpt.mkdir(parents=True, exist_ok=True)
    cv = json.loads(a.cv.read_text())
    if a.only_fold is not None:
        run_fold(cv, a.only_fold, a)
    else:
        aggregate(cv, a)


if __name__ == "__main__":
    main()
