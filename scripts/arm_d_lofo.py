#!/usr/bin/env python
"""Leave-one-fire-out for Arm D, under Arm A's protocol (Session 10, Phase 5).

The LOFO loop here is a faithful transcription of
``spread_v2.model.leave_one_fire_out`` with ONE difference: the feature column
list is a parameter instead of the module constant. Arm A's function is not
modified, imported-and-monkeypatched, or subclassed — it is left exactly alone.

Because a transcription can drift from its original, this script can run itself
against Arm A's own 16 columns (``--features A``). That run must reproduce the
committed ``data/processed/spread_v2_lofo.json`` pooled AUC exactly. If it does
not, the Arm A-vs-Arm D comparison is not measuring what it claims to and the
session says so instead of reporting the delta.

    python scripts/arm_d_lofo.py --features A --fold uljin_samcheok_2022
    python scripts/arm_d_lofo.py --features D          # all remaining folds
    python scripts/arm_d_lofo.py --features D --aggregate

Writes ONLY under data/processed/arms/. No Arm A path is touched.
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

ARM_ROOT = REPO / "data" / "processed" / "arms"
DATASET = ARM_ROOT / "D" / "arm_d_dataset.pkl"

#: Cold-start split. A slice with at most this many prior overpasses is "early":
#: the assimilation features are undefined or rest on a single observation,
#: which is the regime the system is most needed in and least informed in.
EARLY_MAX_PRIORS = 1


def feature_columns(tag: str) -> tuple[str, ...]:
    from wildfireguardian.spread_v2.features import FEATURE_COLUMNS
    from wildfireguardian.spread_v2_armd.dataset import ARM_D_ALL_FEATURE_COLUMNS

    return {"A": FEATURE_COLUMNS, "D": ARM_D_ALL_FEATURE_COLUMNS}[tag]


def out_dir(tag: str) -> Path:
    d = ARM_ROOT / ("D" if tag == "D" else "A_replication") / "lofo"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_dataset():
    with DATASET.open("rb") as fh:
        return pickle.load(fh)


def run_fold(ds, held: str, cols: tuple[str, ...], seed: int) -> dict:
    """One held-out fire. Mirrors Arm A's fold body exactly."""
    from sklearn.metrics import roc_auc_score

    from wildfireguardian.spread_v2.model import IgnitionModelV2

    def safe_auc(y, p):
        y = np.asarray(y)
        if y.min() == y.max():
            return None
        return float(roc_auc_score(y, p))

    train = ds[ds["fire_id"] != held]
    test = ds[ds["fire_id"] == held]
    if train["label"].nunique() < 2 or len(test) == 0:
        return {"fire": held, "auc": None, "skipped": True}

    model = IgnitionModelV2(seed=seed, feature_columns=tuple(cols)).fit(train)
    p = model.predict_proba(test)
    y = test["label"].to_numpy()
    auc = safe_auc(y, p)

    # Permutation importance, per fold. Arm A's own rng is seeded once for the
    # whole run and consumed fold by fold; a per-fold generator is used here so
    # folds can be computed in any order and still be reproducible. This changes
    # the random stream, not the estimator, and the same choice is applied to
    # both arms so the comparison is like-for-like.
    rng = np.random.default_rng(seed)
    X = test[list(cols)].to_numpy(dtype="float64")
    drops: dict[str, float] = {}
    if auc is not None:
        for j, name in enumerate(cols):
            Xp = X.copy()
            Xp[:, j] = rng.permutation(Xp[:, j])
            ap = safe_auc(y, model.predict_proba_matrix(Xp))
            drops[name] = (auc - ap) if ap is not None else 0.0

    prior = test["n_prior_overpasses"].to_numpy()
    early, late = prior <= EARLY_MAX_PRIORS, prior > EARLY_MAX_PRIORS
    band = test["dist_band"].to_numpy()

    return {
        "fire": held,
        "n_test_rows": int(len(test)),
        "n_test_positives": int(y.sum()),
        "auc": auc,
        "auc_far": safe_auc(y[band == "far"], p[band == "far"]) if (band == "far").any() else None,
        "auc_mid": safe_auc(y[band == "mid"], p[band == "mid"]) if (band == "mid").any() else None,
        "cold_start": {
            "early_max_priors": EARLY_MAX_PRIORS,
            "n_early": int(early.sum()), "n_late": int(late.sum()),
            "positives_early": int(y[early].sum()), "positives_late": int(y[late].sum()),
            "auc_early": safe_auc(y[early], p[early]) if early.any() else None,
            "auc_late": safe_auc(y[late], p[late]) if late.any() else None,
        },
        "permutation_importance": drops,
        "oof": {"label": y.astype(int).tolist(), "prob": [float(v) for v in p],
                "dist_band": band.tolist(), "n_prior": prior.astype(int).tolist()},
    }


def aggregate(tag: str) -> dict:
    from sklearn.metrics import roc_auc_score

    cols = feature_columns(tag)
    folds = []
    for p in sorted(out_dir(tag).glob("fold_*.json")):
        folds.append(json.loads(p.read_text(encoding="utf-8")))
    if not folds:
        raise SystemExit(f"no folds computed for arm {tag}")

    y = np.concatenate([np.array(f["oof"]["label"]) for f in folds if f.get("auc") is not None])
    p = np.concatenate([np.array(f["oof"]["prob"]) for f in folds if f.get("auc") is not None])
    band = np.concatenate([np.array(f["oof"]["dist_band"]) for f in folds if f.get("auc") is not None])
    prior = np.concatenate([np.array(f["oof"]["n_prior"]) for f in folds if f.get("auc") is not None])

    def auc(yy, pp):
        return float(roc_auc_score(yy, pp)) if len(yy) and yy.min() != yy.max() else None

    aucs = {f["fire"]: f["auc"] for f in folds}
    vals = [v for v in aucs.values() if v is not None]

    # Row-weighted importance, as Arm A aggregates it, PLUS the fold-level
    # spread. Reporting the weighted mean alone is what let a point estimate
    # with unmeasured spread be read as a finding once already.
    imp = {}
    for c in cols:
        pairs = [(f["permutation_importance"].get(c), f["n_test_rows"])
                 for f in folds if f.get("auc") is not None and c in f["permutation_importance"]]
        if not pairs:
            continue
        d = np.array([a for a, _ in pairs], dtype=float)
        w = np.array([b for _, b in pairs], dtype=float)
        imp[c] = {
            "weighted_mean_auc_drop": float(np.average(d, weights=w)),
            "fold_mean": float(d.mean()),
            "fold_sd": float(d.std(ddof=1)) if len(d) > 1 else None,
            "fold_min": float(d.min()), "fold_max": float(d.max()),
            "n_folds": int(len(d)),
        }
    ranked = sorted(imp.items(), key=lambda kv: -kv[1]["weighted_mean_auc_drop"])

    early = prior <= EARLY_MAX_PRIORS
    payload = {
        "arm": tag,
        "provenance": "derived",
        "seed": 20250603,
        "protocol": "leave-one-fire-out over 6 fires, HistGradientBoostingClassifier, "
                    "spread_v2 hyperparameters unchanged",
        "n_features": len(cols),
        "feature_columns": list(cols),
        "n_oof_rows": int(len(y)),
        "n_oof_positives": int(y.sum()),
        "pooled_auc": auc(y, p),
        "far_band_auc": auc(y[band == "far"], p[band == "far"]),
        "mid_band_auc": auc(y[band == "mid"], p[band == "mid"]),
        "per_fire_auc": aucs,
        "mean_of_folds_auc": float(np.mean(vals)) if vals else None,
        "fold_auc_sd": float(np.std(vals, ddof=1)) if len(vals) > 1 else None,
        "fold_auc_min": float(np.min(vals)) if vals else None,
        "fold_auc_max": float(np.max(vals)) if vals else None,
        "cold_start_pooled": {
            "early_max_priors": EARLY_MAX_PRIORS,
            "n_early": int(early.sum()), "n_late": int((~early).sum()),
            "auc_early": auc(y[early], p[early]),
            "auc_late": auc(y[~early], p[~early]),
        },
        "importance_ranking": [
            {"rank": i + 1, "feature": c, **v} for i, (c, v) in enumerate(ranked)
        ],
    }
    path = ARM_ROOT / ("D" if tag == "D" else "A_replication") / f"lofo_arm_{tag}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: payload[k] for k in
                      ("arm", "n_oof_rows", "pooled_auc", "mean_of_folds_auc",
                       "fold_auc_sd", "far_band_auc")}, indent=2))
    print(f"wrote {path}")
    return payload


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", choices=["A", "D"], required=True)
    ap.add_argument("--fold", action="append", default=None)
    ap.add_argument("--aggregate", action="store_true")
    ap.add_argument("--seed", type=int, default=20250603)
    args = ap.parse_args()

    if args.aggregate:
        aggregate(args.features)
        return 0

    ds = load_dataset()
    cols = feature_columns(args.features)
    fires = sorted(ds["fire_id"].unique())
    for held in (args.fold or fires):
        dest = out_dir(args.features) / f"fold_{held}.json"
        if dest.exists():
            print(f"cached {held}")
            continue
        print(f"fold {held} ({args.features}) ...", flush=True)
        res = run_fold(ds, held, cols, args.seed)
        dest.write_text(json.dumps(res) + "\n", encoding="utf-8")
        print(f"  auc={res.get('auc')} rows={res.get('n_test_rows')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
