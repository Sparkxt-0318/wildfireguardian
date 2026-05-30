"""Deliverables 3-5 -- training, leave-one-fire-out CV, baselines, importance.

The estimator is an XGBoost gradient-boosted-tree classifier with *standard,
conservative* hyper-parameters (shallow trees, heavy subsampling, no class
re-weighting). They are deliberately NOT tuned against held-out AUC -- doing
so would be the exact metric-chasing this project has twice been burned by.
XGBoost is used partly because it handles missing features natively, which is
how the fuel-blind fires (NaN fuel columns) are predicted.

Evaluation is strictly leave-one-fire-out: every reported number for a fire
comes from a model that never saw a single cell of that fire.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    roc_auc_score,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from .config import DISTANCE_BAND_LABELS, DISTANCE_BANDS_M, PipelineConfig
from .features import FEATURE_COLUMNS, build_fire_features
from .grid import get_fire_sequence, observed_vs_reported

# Baseline uses only always-present (never-NaN) physical features.
BASELINE_FEATURES = [
    "dist_to_nearest_burning_m",
    "slope_deg",
    "slope_alignment",
    "elevation_rel_m",
]


def make_model(config: PipelineConfig) -> XGBClassifier:
    return XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5.0,
        reg_lambda=1.0,
        gamma=0.0,
        objective="binary:logistic",
        eval_metric="logloss",
        tree_method="hist",
        n_jobs=-1,
        random_state=config.random_seed,
        # No scale_pos_weight: keep probabilities honest for the Brier score
        # (AUC/PR-AUC are rank-based and unaffected anyway).
    )


def assemble_dataset(
    config: PipelineConfig,
    fires: list[str] | None = None,
    return_sequences: bool = False,
) -> tuple[pd.DataFrame, dict]:
    """Build the pooled candidate table across all usable fires."""
    import json

    manifest = json.loads((config.data_dir / "fire_manifest.json").read_text())
    reported = {f["id"]: float(f["reported_ha"]) for f in manifest["fires"]}
    all_ids = [f["id"] for f in manifest["fires"]]
    if fires is None:
        fires = [f for f in all_ids if f not in config.drop_fires]

    frames, meta = [], {"fires": {}, "area": {}, "class_balance": {}}
    sequences = {}
    for fid in fires:
        seq = get_fire_sequence(fid, config)
        if return_sequences:
            sequences[fid] = seq
        df, diags = build_fire_features(seq, config)
        meta["fires"][fid] = {
            "n_overpasses": seq.n_overpasses,
            "n_transitions_with_samples": int(sum(1 for d in diags if d.get("n_candidates", 0) > 0)),
            "n_candidates": int(len(df)),
            "n_positive": int(df["label"].sum()) if len(df) else 0,
            "positive_rate": float(df["label"].mean()) if len(df) else None,
            "mean_capture_rate": float(
                np.mean([d["capture_rate"] for d in diags if d.get("capture_rate") is not None])
            )
            if any(d.get("capture_rate") is not None for d in diags)
            else None,
            "fuel_blind": fid in config.fuel_broken_fires,
        }
        meta["area"][fid] = observed_vs_reported(seq, reported[fid])
        if len(df):
            frames.append(df)

    data = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    meta["total_candidates"] = int(len(data))
    meta["total_positive"] = int(data["label"].sum()) if len(data) else 0
    meta["overall_positive_rate"] = (
        float(data["label"].mean()) if len(data) else None
    )
    if return_sequences:
        return data, meta, sequences
    return data, meta


def _safe_auc(y, p):
    if len(np.unique(y)) < 2:
        return None
    return float(roc_auc_score(y, p))


def _conditional_by_distance(y, p, dist) -> dict:
    out = {}
    # Bands are (lo, hi]: left-open, right-closed, so the 375 m orthogonal-
    # neighbour ring lands in the first band rather than an empty [0,375).
    for (lo, hi), label in zip(DISTANCE_BANDS_M, DISTANCE_BAND_LABELS):
        m = (dist > lo) & (dist <= hi)
        n = int(m.sum())
        npos = int(y[m].sum()) if n else 0
        out[label] = {
            "n": n,
            "n_pos": npos,
            "auc": _safe_auc(y[m], p[m]) if n else None,
        }
    return out


def _recall_at_topk(y, p, k) -> float | None:
    """Recall when the top-k highest-probability candidates are called positive."""
    n = len(y)
    if k <= 0 or k > n:
        return None
    order = np.argsort(p)[::-1][:k]
    tp = int(y[order].sum())
    total_pos = int(y.sum())
    return tp / total_pos if total_pos else None


def _operating_point(y, p) -> dict:
    """Prevalence-matched (top-K) threshold: predict exactly as many ignitions
    as were actually observed. A non-tuned operating point for footprint/IoU.

    Also report recall at 2x/3x that budget: at the strict 1:1 point precision
    and recall are equal and low; the looser budgets show how much observed
    burned area is captured for a modest false-positive cost (the metric most
    comparable to the ~9% area-capture of the retired mechanistic model)."""
    k = int(y.sum())
    n = len(y)
    if k == 0 or k == n:
        return {"threshold": None, "iou": None, "recall": None, "precision": None, "k": k}
    thr = np.sort(p)[::-1][k - 1]
    pred = p >= thr
    tp = int((pred & (y == 1)).sum())
    fp = int((pred & (y == 0)).sum())
    fn = int((~pred & (y == 1)).sum())
    iou = tp / (tp + fp + fn) if (tp + fp + fn) else None
    return {
        "threshold": float(thr),
        "iou": float(iou) if iou is not None else None,
        "recall": tp / (tp + fn) if (tp + fn) else None,
        "precision": tp / (tp + fp) if (tp + fp) else None,
        "k": k,
        "recall_at_2k": _recall_at_topk(y, p, 2 * k),
        "recall_at_3k": _recall_at_topk(y, p, 3 * k),
    }


def leave_one_fire_out(
    data: pd.DataFrame, config: PipelineConfig, model_factory=make_model
) -> dict:
    """Train on all-other-fires, predict held-out fire; rotate through all."""
    fires = sorted(data["fire_id"].unique())
    results = {"per_fire": {}, "oof": []}
    for held in fires:
        train = data[data["fire_id"] != held]
        test = data[data["fire_id"] == held]
        if test["label"].nunique() < 2 or len(train) == 0:
            results["per_fire"][held] = {"skipped": "held-out fire has <2 classes"}
            continue
        Xtr = train[FEATURE_COLUMNS].to_numpy(dtype="float32")
        ytr = train["label"].to_numpy()
        Xte = test[FEATURE_COLUMNS].to_numpy(dtype="float32")
        yte = test["label"].to_numpy()

        model = model_factory(config)
        model.fit(Xtr, ytr)
        p = model.predict_proba(Xte)[:, 1]

        dist = test["dist_to_nearest_burning_m"].to_numpy()
        results["per_fire"][held] = {
            "n": int(len(test)),
            "n_pos": int(yte.sum()),
            "pos_rate": float(yte.mean()),
            "roc_auc": _safe_auc(yte, p),
            "pr_auc": float(average_precision_score(yte, p)),
            "brier": float(brier_score_loss(yte, p)),
            "conditional_auc": _conditional_by_distance(yte, p, dist),
            "operating_point": _operating_point(yte, p),
            "fuel_blind": held in config.fuel_broken_fires,
            "sparse": held in config.sparse_fires,
        }
        oof = test[["fire_id", "transition", "row", "col", "label"]].copy()
        oof["pred"] = p
        results["oof"].append(oof)
    if results["oof"]:
        results["oof"] = pd.concat(results["oof"], ignore_index=True)
    else:
        results["oof"] = pd.DataFrame()
    results["summary"] = _summarise(results["per_fire"], config)
    return results


def _summarise(per_fire: dict, config: PipelineConfig) -> dict:
    def collect(ids, key):
        vals = [
            per_fire[f][key]
            for f in ids
            if f in per_fire and isinstance(per_fire[f], dict) and per_fire[f].get(key) is not None
        ]
        return vals

    head = [f for f in config.headline_fires if f in per_fire and "roc_auc" in per_fire[f]]
    aucs = collect(head, "roc_auc")
    praucs = collect(head, "pr_auc")
    summary = {
        "headline_fires": head,
        "headline_mean_auc": float(np.mean(aucs)) if aucs else None,
        "headline_std_auc": float(np.std(aucs)) if aucs else None,
        "headline_mean_pr_auc": float(np.mean(praucs)) if praucs else None,
    }
    # Far-band (>1500m) mean AUC across headline fires -- the honesty contrast.
    far = []
    for f in head:
        cond = per_fire[f].get("conditional_auc", {})
        v = cond.get(">1500m", {}).get("auc")
        if v is not None:
            far.append(v)
    summary["headline_mean_auc_far_band"] = float(np.mean(far)) if far else None
    return summary


# ---------------------------------------------------------------------------
# Deliverable 4 -- baselines
# ---------------------------------------------------------------------------
def baseline_distance_only(data, config) -> dict:
    """Parameter-free proximity baseline: rank candidates by -distance."""
    results = {"per_fire": {}}
    for held in sorted(data["fire_id"].unique()):
        test = data[data["fire_id"] == held]
        if test["label"].nunique() < 2:
            continue
        y = test["label"].to_numpy()
        p = -test["dist_to_nearest_burning_m"].to_numpy()  # closer = higher score
        results["per_fire"][held] = {
            "roc_auc": _safe_auc(y, p),
            "pr_auc": float(average_precision_score(y, p)),
            "conditional_auc": _conditional_by_distance(
                y, p, test["dist_to_nearest_burning_m"].to_numpy()
            ),
        }
    return results


def baseline_logistic_distslope(data, config) -> dict:
    """Physics-lite baseline: logistic regression on distance + slope terms,
    same leave-one-fire-out protocol as the full model."""
    results = {"per_fire": {}}
    for held in sorted(data["fire_id"].unique()):
        train = data[data["fire_id"] != held]
        test = data[data["fire_id"] == held]
        if test["label"].nunique() < 2 or len(train) == 0:
            continue
        clf = make_pipeline(
            SimpleImputer(strategy="median"),  # elevation_rel can be NaN at DEM voids
            StandardScaler(),
            LogisticRegression(max_iter=1000, random_state=config.random_seed),
        )
        clf.fit(train[BASELINE_FEATURES].to_numpy(), train["label"].to_numpy())
        p = clf.predict_proba(test[BASELINE_FEATURES].to_numpy())[:, 1]
        y = test["label"].to_numpy()
        results["per_fire"][held] = {
            "roc_auc": _safe_auc(y, p),
            "pr_auc": float(average_precision_score(y, p)),
            "conditional_auc": _conditional_by_distance(
                y, p, test["dist_to_nearest_burning_m"].to_numpy()
            ),
        }
    return results


# ---------------------------------------------------------------------------
# Deliverable 5 -- feature importance
# ---------------------------------------------------------------------------
def feature_importance(data, config, with_shap: bool = True) -> dict:
    """Fit on the full pooled dataset; return gain importances (+ optional SHAP)."""
    X = data[FEATURE_COLUMNS].to_numpy(dtype="float32")
    y = data["label"].to_numpy()
    model = make_model(config)
    model.fit(X, y)
    booster = model.get_booster()
    booster.feature_names = list(FEATURE_COLUMNS)
    gain = booster.get_score(importance_type="gain")
    gain_full = {f: float(gain.get(f, 0.0)) for f in FEATURE_COLUMNS}
    total = sum(gain_full.values()) or 1.0
    gain_norm = {f: v / total for f, v in gain_full.items()}

    out = {
        "gain": gain_full,
        "gain_normalised": gain_norm,
        "ranking": sorted(gain_norm, key=gain_norm.get, reverse=True),
    }
    if with_shap:
        try:
            import shap

            expl = shap.TreeExplainer(model)
            # subsample for speed
            rng = np.random.default_rng(config.random_seed)
            idx = rng.choice(len(X), size=min(5000, len(X)), replace=False)
            sv = expl.shap_values(X[idx])
            mean_abs = np.abs(sv).mean(axis=0)
            out["shap_mean_abs"] = {
                f: float(v) for f, v in zip(FEATURE_COLUMNS, mean_abs)
            }
            out["shap_ranking"] = sorted(
                out["shap_mean_abs"], key=out["shap_mean_abs"].get, reverse=True
            )
        except Exception as exc:  # pragma: no cover - shap optional
            out["shap_error"] = str(exc)
    return out, model
