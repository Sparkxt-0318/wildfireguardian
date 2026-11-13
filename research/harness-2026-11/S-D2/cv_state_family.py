"""Wide-grid state family (RULE_state_family.md @ d0c7f0ad, committed before this code).

Stage 1 (per fold, per kernel): for each test fire and interval, SIMS exact simulations to TMAX*T with the fold's
kernel. Arrival times give p_m = P(tau <= m*T) for every grid value. Stored per fire (checkpointed).
Stage 2 (aggregate): arms mcem_state_wide, mcem_lag1_wide, plugin_state_wide; comparators, bar, reports.

    python cv_state_family.py --brackets DIR --cv-ckpt DIR --ckpt DIR --only-fold k --kernel mcem|plugin
    python cv_state_family.py --brackets DIR --cv-ckpt DIR --ckpt DIR --out results/cv_state_family.json
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from pathlib import Path

import runenv

import numpy as np

import cv_baselines as CB
import real_bracket_fit as F
from cv_rate_arm import signflip_p, simulate_times

GRID = np.array([1 / 16, 1 / 8, 1 / 4, 1 / 2, 1.0, 2.0, 4.0, 8.0])
SIMS = 512
TMAX = 8.0
EPS = 1.0 / (SIMS + 1)
RHOS = (0.0, 0.25, 0.5, 0.75, 0.9)
KAPPAS = (1.0, 10.0, 100.0, 1000.0)
SEED0 = {"mcem": 99_000, "plugin": 99_500}
ALPHA = 0.05 / 3


def run_fold(cv, k, kernel, a):
    theta = np.asarray(cv["thetas"][str(k)][kernel])
    for i, f in enumerate(cv["folds"][k]):
        fp = a.ckpt / f"{kernel}_fold{k}.fire{i}.npz"
        if fp.exists():
            continue
        t0 = time.time()
        p, _ = F.load_fire(a.brackets / f"{f}.npz", a.hours, 0)
        rows = CB.fire_cells(a.brackets / f"{f}.npz", a.hours)
        rng = np.random.default_rng(SEED0[kernel] + 31 * k + i)
        grids, ys, ds, ns = [], [], [], []
        for r in rows:
            cnt = np.zeros((len(GRID), int(r["pop"].sum())), np.int32)
            for _ in range(SIMS):
                tau = simulate_times(p, r["start"].ravel(), TMAX * r["T"], theta, rng)[r["pop"]]
                cnt += tau[None, :] <= (GRID[:, None] * r["T"])
            grids.append(cnt.astype(np.float32) / SIMS)
            ys.append(r["y"])
            ds.append(r["dist"])
            ns.append(int(r["pop"].sum()))
        tmp = fp.with_name(fp.name + ".tmp.npz")
        np.savez_compressed(tmp, env=json.dumps(runenv.info()), p_grid=np.concatenate(grids, 1), y=np.concatenate(ys), dist=np.concatenate(ds),
                            n=np.array(ns), seconds=time.time() - t0)
        tmp.replace(fp)
        print(f"{kernel} fold {k} fire {i} done {time.time() - t0:.0f}s", flush=True)


def interval_ll(pg, y, ns):
    """[intervals, grid] untempered Bernoulli log-likelihood sums and per-cell means."""
    pc = np.clip(pg, EPS, 1 - EPS)
    ll = np.where(y[None, :].astype(bool), np.log(pc), np.log1p(-pc))
    e = np.cumsum([0] + list(ns))
    s = np.array([ll[:, a:b].sum(1) for a, b in zip(e[:-1], e[1:])])
    return s, s / np.array(ns)[:, None]


def em_weights(L):
    pi = np.full(L.shape[1], 1.0 / L.shape[1])
    for _ in range(1000):
        lw = L + np.log(pi)[None, :]
        r = np.exp(lw - lw.max(1, keepdims=True))
        r /= r.sum(1, keepdims=True)
        new = r.mean(0)
        if np.abs(new - pi).max() < 1e-12:
            return new
        pi = new
    return pi


def lag1_weights(pi, Lmean, rho, kappa):
    """Weights per interval: first = pi; then rho*q_{j-1} + (1-rho)*pi, q ∝ pi*exp(kappa*mean ll)."""
    W = [pi]
    for j in range(1, Lmean.shape[0]):
        lq = np.log(pi) + kappa * Lmean[j - 1]
        q = np.exp(lq - lq.max())
        q /= q.sum()
        W.append(rho * q + (1 - rho) * pi)
    return np.array(W)


def mix_predict(pg, ns, W):
    e = np.cumsum([0] + list(ns))
    return np.concatenate([W[j] @ pg[:, a:b] for j, (a, b) in enumerate(zip(e[:-1], e[1:]))])


def aggregate(cv, a):
    folds = cv["folds"]
    fires = [f for fs in folds for f in fs]
    fold_of = {f: k for k, fs in enumerate(folds) for f in fs}
    G = {}
    for kern in ("mcem", "plugin"):
        for k, fs in enumerate(folds):
            for i, f in enumerate(fs):
                z = np.load(a.ckpt / f"{kern}_fold{k}.fire{i}.npz")
                G[(kern, f)] = dict(pg=z["p_grid"].astype(np.float64), y=z["y"], dist=z["dist"], n=z["n"])
    Y = {f: G[("mcem", f)]["y"] for f in fires}
    D = {f: G[("mcem", f)]["dist"] for f in fires}
    P, info = {}, dict(state_weights={}, lag1_choice={})
    # comparators (identical cells, checked)
    for k, fs in enumerate(folds):
        ck = json.loads((a.cv_ckpt / f"fold{k}.json").read_text())
        for f in fs:
            if not (np.array_equal(np.asarray(ck["per_fire"][f]["mcem"]["y"]), Y[f])
                    and np.array_equal(G[("plugin", f)]["y"], Y[f])):
                raise ValueError(f"cells differ: {f}")
            for m in ("plugin", "mcem"):
                P.setdefault(m, {})[f] = np.asarray(ck["per_fire"][f][m]["p"])
    cells = {f: CB.fire_cells(a.brackets / f"{f}.npz", a.hours) for f in fires}
    for k, fs in enumerate(folds):
        train = [f for f in fires if f not in fs]
        ytr = np.concatenate([np.concatenate([r["y"] for r in cells[f]]) for f in train])
        lg = CB.fit_logistic(np.concatenate([CB.feats(cells[f]) for f in train]), ytr, seed=0)
        for f in fs:
            P.setdefault("logistic_cf", {})[f] = CB.predict_logistic(lg, CB.feats(cells[f]))
            P.setdefault("persistence", {})[f] = np.zeros(len(Y[f]))
            P.setdefault("dilation_8h", {})[f] = CB.preds_baselines(cells[f], 8)
    rr = json.loads(a.round1.read_text())   # round-1 mcem_state is recomputed below from m<=2 for the check
    LL = {(kern, f): interval_ll(G[(kern, f)]["pg"], Y[f], G[(kern, f)]["n"]) for kern in ("mcem", "plugin")
          for f in fires}
    for k, fs in enumerate(folds):
        other = [f for f in fires if fold_of[f] != k]
        for kern, arm in (("mcem", "mcem_state_wide"), ("plugin", "plugin_state_wide")):
            pi = em_weights(np.concatenate([LL[(kern, f)][0] for f in other]))
            info["state_weights"].setdefault(arm, {})[k] = pi.tolist()
            for f in fs:
                P.setdefault(arm, {})[f] = pi @ G[(kern, f)]["pg"]
        # round-1 check: state arm restricted to m <= 2
        sub = GRID <= 2.0
        pi2 = em_weights(np.concatenate([LL[("mcem", f)][0][:, sub] for f in other]))
        for f in fs:
            P.setdefault("check_mcem_state_m_le_2", {})[f] = pi2 @ G[("mcem", f)]["pg"][sub]
            for kern in ("mcem", "plugin"):
                P.setdefault(f"check_{kern}_m1_512", {})[f] = G[(kern, f)]["pg"][GRID == 1.0][0]
        # lag-1: choose (rho, kappa) on other folds by untempered predictive log-likelihood
        pi = np.asarray(info["state_weights"]["mcem_state_wide"][k])
        best = None
        for rho, kap in itertools.product(RHOS, KAPPAS):
            tot = 0.0
            for f in other:
                Ls, Lm = LL[("mcem", f)]
                W = lag1_weights(pi, Lm, rho, kap)
                # predictive log-likelihood of each interval under its mixture
                pc = np.clip(mix_predict(G[("mcem", f)]["pg"], G[("mcem", f)]["n"], W), EPS, 1 - EPS)
                tot += float(np.where(Y[f].astype(bool), np.log(pc), np.log1p(-pc)).sum())
            if best is None or tot > best[0]:
                best = (tot, rho, kap)
        info["lag1_choice"][k] = dict(rho=best[1], kappa=best[2])
        for f in fs:
            W = lag1_weights(pi, LL[("mcem", f)][1], best[1], best[2])
            P.setdefault("mcem_lag1_wide", {})[f] = mix_predict(G[("mcem", f)]["pg"], G[("mcem", f)]["n"], W)
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
    pooled["round1_mcem_state_reported"] = dict(brier=rr["pooled"]["mcem_state"]["brier"])
    err = {m: np.array([np.sum((P[m][f] - Y[f]) ** 2) for f in fires]) for m in P}
    n = np.array([len(Y[f]) for f in fires])
    draws = np.random.default_rng(20261112).integers(0, len(fires), size=(10_000, len(fires)))
    arms = ("mcem_state_wide", "mcem_lag1_wide", "plugin_state_wide")
    comp = {}
    for arm in arms:
        for ref in ("plugin", "logistic_cf", "mcem", "persistence"):
            d = err[arm] - err[ref]
            bs = d[draws].sum(1) / n[draws].sum(1)
            comp[f"{arm}_minus_{ref}"] = dict(point=float(d.sum() / n.sum()),
                                              ci95=[float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))],
                                              signflip_p=signflip_p(d, np.random.default_rng(20261112)),
                                              better_fires=f"{int((d < 0).sum())}/{len(fires)}")
    qual = {arm: all(comp[f"{arm}_minus_{r}"]["ci95"][1] < 0 and comp[f"{arm}_minus_{r}"]["signflip_p"] < ALPHA
                     for r in ("plugin", "logistic_cf")) for arm in arms}
    # POST-HOC, DESCRIPTIVE (Iris, 2026-11-13, after Owen's row-53 verification; not in RULE_state_family.md and
    # not used by `qualifies`): paired lag-1 minus state on the MCEM kernel. Same bootstrap draws and sign-flip seed.
    d = err["mcem_lag1_wide"] - err["mcem_state_wide"]
    bs = d[draws].sum(1) / n[draws].sum(1)
    posthoc = {"mcem_lag1_wide_minus_mcem_state_wide": dict(
        point=float(d.sum() / n.sum()), ci95=[float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))],
        signflip_p=signflip_p(d, np.random.default_rng(20261112)), better_fires=f"{int((d < 0).sum())}/{len(fires)}",
        note="post-hoc descriptive pair; not part of the rule or of qualifies")}
    # first vs later for lag-1
    split = {}
    for name, first in (("first_interval", True), ("later_intervals", False)):
        for m in ("mcem_lag1_wide", "mcem_state_wide", "mcem", "plugin", "logistic_cf", "persistence"):
            pv, yv = [], []
            for f in fires:
                msk = np.zeros(len(Y[f]), bool)
                msk[: int(G[("mcem", f)]["n"][0])] = True
                sel = msk if first else ~msk
                pv.append(P[m][f][sel])
                yv.append(Y[f][sel])
            pv, yv = np.concatenate(pv), np.concatenate(yv)
            split.setdefault(name, {})[m] = dict(brier=float(np.mean((pv - yv) ** 2)), cells=int(len(yv)))
    edges = {arm: {k: dict(bottom_1_16=w[0], top_8=w[-1]) for k, w in ws.items()}
             for arm, ws in info["state_weights"].items()}
    out = dict(command="python cv_state_family.py " + " ".join(sys.argv[1:]), rule="RULE_state_family.md @ d0c7f0ad", env=runenv.info(),
               grid=GRID.tolist(), sims=SIMS, tmax=TMAX, alpha_signflip=ALPHA,
               disclosure="round 2 on the same 25 fires; two earlier arms (mcem_rate, mcem_state) tried and failed",
               pooled=pooled, comparisons=comp, posthoc_descriptive=posthoc, qualifies=qual,
               stopping_rule_triggered=not any(qual.values()), state_weights=info["state_weights"],
               edge_weights=edges, lag1_choice=info["lag1_choice"], first_vs_later_lag1=split)
    a.out.write_text(json.dumps(out, indent=1))
    for m, r in sorted(pooled.items(), key=lambda kv: kv[1]["brier"]):
        print(f"{m:28s} {r['brier']:.4f}  " + "  ".join(f"{b} {r.get('brier_' + b, float('nan')):.4f}"
                                                        for b in ("0-1km", "1-2km", "2-4km")))
    print(json.dumps(dict(comparisons=comp, qualifies=qual, edges=edges, lag1=info["lag1_choice"], split=split),
                     indent=1))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--brackets", type=Path, required=True)
    ap.add_argument("--cv", type=Path, default=Path("results/cv_part_a.json"))
    ap.add_argument("--cv-ckpt", type=Path, required=True)
    ap.add_argument("--round1", type=Path, default=Path("results/cv_rate_arm.json"))
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--hours", type=float, default=240.0)
    ap.add_argument("--only-fold", type=int, default=None)
    ap.add_argument("--kernel", choices=["mcem", "plugin"], default=None)
    ap.add_argument("--out", type=Path, default=Path("results/cv_state_family.json"))
    a = ap.parse_args(argv)
    runenv.require_pinned()
    a.ckpt.mkdir(parents=True, exist_ok=True)
    cv = json.loads(a.cv.read_text())
    if a.only_fold is not None:
        run_fold(cv, a.only_fold, a.kernel, a)
    else:
        aggregate(cv, a)


if __name__ == "__main__":
    main()
