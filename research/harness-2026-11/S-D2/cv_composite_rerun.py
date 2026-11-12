"""Rerun ONLY the pooled composite estimator of the part-a CV, in the pinned environment (Owen's finding).

In results/cv_part_a.json (96f99bf6) the composite fit collapsed to the 1e-9 floor in folds 0, 2, 3 and 4 under
numpy 2.1.3 / scipy 1.14.1: a failed optimization, not an estimate. Here, per fold, the composite is refitted with
cv_part_a.fit_composite. _lbfgs now raises FitFailed on an all-at-floor solution, a non-finite gradient, or f worse
than the start. Each test fire is then rescored with the SAME seed as the CV (77_000 + 31*fold + i). score_fire
re-seeds per estimator and interval, so the other estimators' numbers are unchanged. Writes per-fold checkpoints,
then results/cv_composite_rerun.json with the composite rows and pairs (vs plug-in and mcem) on the same cells.

    python cv_composite_rerun.py --brackets DIR --cv-ckpt DIR --ckpt DIR [--only-fold k]
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

import runenv

import numpy as np
import scipy

import cv_part_a as C
import real_bracket_fit as F


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--brackets", type=Path, required=True)
    ap.add_argument("--cv", type=Path, default=Path("results/cv_part_a.json"))
    ap.add_argument("--cv-ckpt", type=Path, required=True)
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--hours", type=float, default=240.0)
    ap.add_argument("--sims", type=int, default=1024)
    ap.add_argument("--only-fold", type=int, default=None)
    ap.add_argument("--out", type=Path, default=Path("results/cv_composite_rerun.json"))
    a = ap.parse_args(argv)
    runenv.require_pinned()
    a.ckpt.mkdir(parents=True, exist_ok=True)
    cv = json.loads(a.cv.read_text())
    folds = cv["folds"]
    env = dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__)
    todo = [a.only_fold] if a.only_fold is not None else range(len(folds))
    for k in todo:
        fp = a.ckpt / f"composite_fold{k}.json"
        if fp.exists():
            continue
        train = [f for f in sum(folds, []) if f not in folds[k]]
        fires = [F.load_fire(a.brackets / f"{f}.npz", a.hours, 0) for f in train]
        th = C.fit_composite(fires)
        per = {}
        for i, f in enumerate(folds[k]):
            sc = C.score_fire(str(a.brackets / f"{f}.npz"), a.hours, {"composite": th}, a.sims, 77_000 + 31 * k + i)
            per[f] = {kk: v.tolist() for kk, v in sc["composite"].items()}
        fp.write_text(json.dumps(dict(fold=k, theta=th.tolist(), env=env, per_fire=per)))
        print(f"fold {k}: composite sum {th.sum():.4g} k0 {th[0]:.3g}", flush=True)
    if a.only_fold is not None:
        return
    Y, P = {}, {}
    for k, fs in enumerate(folds):
        r = json.loads((a.ckpt / f"composite_fold{k}.json").read_text())
        ck = json.loads((a.cv_ckpt / f"fold{k}.json").read_text())
        for f in fs:
            y = np.asarray(r["per_fire"][f]["y"])
            if not np.array_equal(y, np.asarray(ck["per_fire"][f]["mcem"]["y"])):
                raise ValueError(f"cells differ: {f}")
            Y[f] = y
            P.setdefault("composite_rerun", {})[f] = np.asarray(r["per_fire"][f]["p"])
            for m in ("plugin", "mcem", "meanfield_nll"):
                P.setdefault(m, {})[f] = np.asarray(ck["per_fire"][f][m]["p"])
    fires = [f for fs in folds for f in fs]
    n = np.array([len(Y[f]) for f in fires])
    err = {m: np.array([np.sum((P[m][f] - Y[f]) ** 2) for f in fires]) for m in P}
    draws = np.random.default_rng(20261030).integers(0, len(fires), size=(10_000, len(fires)))
    pairs = {}
    for ref in ("plugin", "mcem"):
        d = err["composite_rerun"] - err[ref]
        bs = d[draws].sum(1) / n[draws].sum(1)
        pairs[f"composite_rerun_minus_{ref}"] = dict(point=float(d.sum() / n.sum()),
                                                     ci95=[float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))],
                                                     better_fires=f"{int((d < 0).sum())}/{len(fires)}")
    D = np.concatenate([np.asarray(json.loads((a.ckpt / f"composite_fold{k}.json").read_text())["per_fire"][f]["dist"])
                        for k, fs in enumerate(folds) for f in fs])
    pv = np.concatenate([P["composite_rerun"][f] for f in fires])
    yv = np.concatenate([Y[f] for f in fires])
    out = dict(command="python cv_composite_rerun.py " + " ".join(sys.argv[1:]), env=env,
               thetas={k: json.loads((a.ckpt / f"composite_fold{k}.json").read_text())["theta"] for k in range(len(folds))},
               metrics=C.metrics(pv, yv, D), pairs=pairs,
               note="supersedes every composite number in results/cv_part_a.json and cv_baselines.json (floor collapse)")
    a.out.write_text(json.dumps(out, indent=1))
    print(json.dumps(dict(metrics=out["metrics"], pairs=pairs), indent=1))


if __name__ == "__main__":
    main()
