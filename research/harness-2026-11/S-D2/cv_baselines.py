"""Baselines and distance-band Brier on the SAME cells and folds as results/cv_part_a.json (Iris).

Cells are reconstructed exactly as in cv_part_a.score_fire: per survey interval, unburned real cells within BAND_M of
the start extent. Labels are checked equal to the kernel checkpoints, element by element. Baselines (definitions
from forecast/wildfire/baselines.py; covariate-free, like the kernels):
- persistence: p = 0;
- dilation_k: 0/1, Chebyshev growth of floor(T/k) cells (k = 1, 2, 4, 8 h per cell). Also `dilation_best`: k chosen
  per fold by pooled TRAINING-fold Brier (choose_dilation);
- logistic_cf: logistic regression fitted per fold on the training folds' cells, on the covariate-free hand
  features log1p(d), d/T and log T (d = distance in cells to the nearest burned cell, capped at 40). The full
  hand-feature logistic also needs wind, slope and biome, which these covariate-free fits do not have, so it is NOT
  this model.
Kernel predictions (plugin, composite, meanfield_nll, mcem) are read from the fold checkpoints.
Reported: pooled Brier overall and per distance band (0-1, 1-2, 2-4 km), and a paired fire bootstrap of each model
minus plug-in and minus mcem (10 000 draws, seed 20261112).

    python cv_baselines.py --brackets DIR --cv results/cv_part_a.json --ckpt DIR --out results/cv_baselines.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt

import cv_part_a as C
import real_bracket_fit as F
import synthetic as S
from forecast_baselines import dilation, choose_dilation, fit_logistic, predict_logistic  # noqa: F401

KS = (1, 2, 4, 8)
BANDS = [(0, 1000), (1000, 2000), (2000, 4000)]
KERNELS = ["plugin", "composite", "meanfield_nll", "mcem"]


def fire_cells(path, hours):
    """Per interval: start mask (2-D), population mask, labels, distance (m), interval hours. Mirrors score_fire."""
    p, obs = F.load_fire(Path(path), hours, 0)
    z = np.load(path)
    h, w = z["first_survey"].shape
    real = np.zeros((p.n, p.n), bool)
    real[:h, :w] = True
    real = real.ravel()
    hi_t = np.where(obs["burned"], obs["hi"], S.INF)
    rows = []
    for a, b in zip(obs["surveys"][:-1], obs["surveys"][1:]):
        start = hi_t <= a
        if not start.any():
            continue
        y = (hi_t > a) & (hi_t <= b)
        dist = distance_transform_edt(~start.reshape(p.n, p.n)).ravel() * C.CELL_M
        pop = real & ~start & (dist <= C.BAND_M)
        rows.append(dict(start=start.reshape(p.n, p.n), pop=pop, y=y[pop].astype(np.int8), dist=dist[pop],
                         T=float(b - a)))
    return rows


def preds_baselines(rows, k):
    return np.concatenate([dilation(r["start"], r["T"], k).ravel()[r["pop"]] for r in rows])


def feats(rows):
    out = []
    for r in rows:
        d = np.minimum(distance_transform_edt(~r["start"]).ravel()[r["pop"]], 40.0)
        out.append(np.stack([np.log1p(d), d / max(r["T"], 1e-9), np.full(d.shape, np.log(r["T"]))], 1))
    return np.concatenate(out)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--brackets", type=Path, required=True)
    ap.add_argument("--cv", type=Path, default=Path("results/cv_part_a.json"))
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--hours", type=float, default=240.0)
    ap.add_argument("--out", type=Path, default=Path("results/cv_baselines.json"))
    a = ap.parse_args(argv)
    cv = json.loads(a.cv.read_text())
    folds = cv["folds"]
    cells = {f: fire_cells(a.brackets / f"{f}.npz", a.hours) for fs in folds for f in fs}
    P, Y, D, FIRE = {}, [], [], []
    for k, fs in enumerate(folds):
        ck = json.loads((a.ckpt / f"fold{k}.json").read_text())
        train = [f for f in sum(folds, []) if f not in fs]
        # dilation k chosen on training fires
        ytr = np.concatenate([np.concatenate([r["y"] for r in cells[f]]) for f in train])
        tr_scores = {kk: float(np.mean((np.concatenate([preds_baselines(cells[f], kk) for f in train]) - ytr) ** 2))
                     for kk in KS}
        kbest = choose_dilation(tr_scores)
        lg = fit_logistic(np.concatenate([feats(cells[f]) for f in train]), ytr, seed=0)
        for f in fs:
            y = np.concatenate([r["y"] for r in cells[f]])
            yck = np.asarray(ck["per_fire"][f]["mcem"]["y"], np.int8)
            if not np.array_equal(y, yck):
                raise ValueError(f"cell reconstruction differs from checkpoint: {f}")
            Y.append(y)
            D.append(np.concatenate([r["dist"] for r in cells[f]]))
            FIRE.append(np.full(len(y), f, dtype=object))
            add = {"persistence": np.zeros(len(y))}
            for kk in KS:
                add[f"dilation_{kk}h"] = preds_baselines(cells[f], kk)
            add["dilation_best"] = preds_baselines(cells[f], kbest)
            add["logistic_cf"] = predict_logistic(lg, feats(cells[f]))
            for m in KERNELS:
                add[m] = np.asarray(ck["per_fire"][f][m]["p"])
            for m, v in add.items():
                P.setdefault(m, []).append(v)
        print(f"fold {k}: dilation_best k={kbest} (training Brier {tr_scores})", flush=True)
    Y, D, FIRE = np.concatenate(Y), np.concatenate(D), np.concatenate(FIRE)
    P = {m: np.concatenate(v) for m, v in P.items()}
    res = {}
    for m, p in P.items():
        r = dict(brier=float(np.mean((p - Y) ** 2)))
        for lo, hi in BANDS:
            s = (D > lo) & (D <= hi)
            r[f"brier_{lo//1000}-{hi//1000}km"] = float(np.mean((p[s] - Y[s]) ** 2))
            r[f"sum_sq_{lo//1000}-{hi//1000}km"] = float(np.sum((p[s] - Y[s]) ** 2))
        res[m] = r
    fires = np.unique(FIRE)
    idx = {f: np.flatnonzero(FIRE == f) for f in fires}
    err = {m: np.array([np.sum((P[m][idx[f]] - Y[idx[f]]) ** 2) for f in fires]) for m in P}
    n = np.array([len(idx[f]) for f in fires])
    rng = np.random.default_rng(20261112)
    draws = rng.integers(0, len(fires), size=(10_000, len(fires)))
    paired = {}
    for ref in ("plugin", "mcem"):
        for m in P:
            if m == ref:
                continue
            dd = (err[m][draws].sum(1) - err[ref][draws].sum(1)) / n[draws].sum(1)
            paired[f"{m}_minus_{ref}"] = dict(point=float((err[m].sum() - err[ref].sum()) / n.sum()),
                                              ci95=[float(np.percentile(dd, 2.5)), float(np.percentile(dd, 97.5))],
                                              better_fires=f"{int((err[m] < err[ref]).sum())}/{len(fires)}")
    out = dict(command="python cv_baselines.py " + " ".join(argv or sys.argv[1:]), cells=int(len(Y)),
               positives=int(Y.sum()), pooled=res, paired=paired,
               note="covariate-free logistic (log1p d, d/T, log T); not the full hand-feature logistic")
    a.out.write_text(json.dumps(out, indent=1))
    for m, r in sorted(res.items(), key=lambda kv: kv[1]["brier"]):
        print(f"{m:15s} {r['brier']:.4f}  0-1km {r['brier_0-1km']:.4f}  1-2km {r['brier_1-2km']:.4f}  2-4km {r['brier_2-4km']:.4f}")


if __name__ == "__main__":
    main()
