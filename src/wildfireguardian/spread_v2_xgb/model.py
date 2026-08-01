# forbidden-ok: XGBoost
"""XGBoost classifier + leave-one-fire-out evaluation (Deliverables 3–5).

The estimator is a gradient-boosted tree with **frozen, untuned**
hyper-parameters (see :data:`XGB_PARAMS`) — we deliberately do NOT search them
# forbidden-ok: XGBoost
against the CV metric, per the honesty principle. XGBoost's native missing
handling lets the weather-incomplete fire (gangneung_donghae, no ERA5) train
and predict with weather = NaN.

Evaluation is **leave-one-fire-out (LOFO)**: hold out an entire fire, train on
the rest, predict the held-out fire. This is the only honest protocol — a
random split would leak neighbouring cells of the same fire across train/test.
We report per-fire ROC-AUC / PR-AUC / Brier (mean ± std), pooled out-of-fold
AUC overall and conditioned on the distance band, footprint IoU/capture, and
LOFO permutation importance.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    roc_auc_score,
)
from xgboost import XGBClassifier

from .features import distance_band

# Frozen, untuned hyper-parameters. Conservative depth + min_child_weight to
# resist over-fitting on the small folds; NOT tuned against the CV metric.
XGB_PARAMS = dict(
    n_estimators=400,
    learning_rate=0.05,
    max_depth=4,
    min_child_weight=5.0,
    subsample=0.8,
    colsample_bytree=0.8,
    reg_lambda=1.0,
    gamma=0.0,
    objective="binary:logistic",
    eval_metric="logloss",
    tree_method="hist",
    n_jobs=-1,
)

BANDS = ["0-375", "375-750", "750-1500", ">1500"]


def make_model(seed: int) -> XGBClassifier:
    return XGBClassifier(random_state=seed, missing=np.nan, **XGB_PARAMS)


def lofo_predict(
    df: pd.DataFrame, features: list[str], seed: int = 42,
) -> tuple[pd.DataFrame, dict]:
    """Leave-one-fire-out out-of-fold predictions.

    Returns ``(oof, fold_models)`` where ``oof`` has columns
    ``[fire_id, label, oof_pred, dist_to_nearest_burning, band]`` and
    ``fold_models[test_fire]`` is the fitted estimator for that fold.
    """
    fires = sorted(df["fire_id"].unique())
    parts: list[pd.DataFrame] = []
    fold_models: dict[str, XGBClassifier] = {}

    for test_fire in fires:
        tr = df[df["fire_id"] != test_fire]
        te = df[df["fire_id"] == test_fire]
        model = make_model(seed)
        model.fit(tr[features], tr["label"])
        pred = model.predict_proba(te[features])[:, 1]
        fold_models[test_fire] = model
        parts.append(pd.DataFrame({
            "fire_id": test_fire,
            "label": te["label"].to_numpy(),
            "oof_pred": pred,
            "dist_to_nearest_burning": te["dist_to_nearest_burning"].to_numpy(),
            "row": te["row"].to_numpy(),
            "col": te["col"].to_numpy(),
            "k": te["k"].to_numpy(),
        }))

    oof = pd.concat(parts, ignore_index=True)
    oof["band"] = distance_band(oof["dist_to_nearest_burning"].to_numpy())
    return oof, fold_models


def _safe_auc(y, p) -> float:
    y = np.asarray(y)
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(roc_auc_score(y, p))


def per_fire_metrics(oof: pd.DataFrame) -> pd.DataFrame:
    """ROC-AUC / PR-AUC / Brier per held-out fire."""
    rows = []
    for fid, g in oof.groupby("fire_id"):
        y, p = g["label"].to_numpy(), g["oof_pred"].to_numpy()
        rows.append({
            "fire_id": fid,
            "n": len(g),
            "positives": int(y.sum()),
            "roc_auc": _safe_auc(y, p),
            "pr_auc": float(average_precision_score(y, p)) if y.sum() else float("nan"),
            "brier": float(brier_score_loss(y, p)),
            "prevalence": float(y.mean()),
        })
    return pd.DataFrame(rows)


def summary_metrics(oof: pd.DataFrame) -> dict:
    """Pooled overall + mean±std-across-fires + per-band conditional AUC."""
    pf = per_fire_metrics(oof)
    y, p = oof["label"].to_numpy(), oof["oof_pred"].to_numpy()
    band_auc = {}
    for b in BANDS:
        g = oof[oof["band"] == b]
        band_auc[b] = {
            "roc_auc": _safe_auc(g["label"], g["oof_pred"]),
            "n": int(len(g)),
            "positives": int(g["label"].sum()),
        }
    return {
        "overall_pooled_roc_auc": _safe_auc(y, p),
        "overall_pooled_pr_auc": float(average_precision_score(y, p)),
        "overall_pooled_brier": float(brier_score_loss(y, p)),
        "mean_fire_roc_auc": float(pf["roc_auc"].mean()),
        "std_fire_roc_auc": float(pf["roc_auc"].std(ddof=0)),
        "mean_fire_pr_auc": float(pf["pr_auc"].mean()),
        "std_fire_pr_auc": float(pf["pr_auc"].std(ddof=0)),
        "mean_fire_brier": float(pf["brier"].mean()),
        "band_auc": band_auc,
        "per_fire": pf.to_dict(orient="records"),
    }


def footprint_metrics(
    oof: pd.DataFrame, sequences: dict, grids: dict,
) -> pd.DataFrame:
    """Per-fire footprint IoU / capture at the observed-ignition budget.

    For each fire, rank its candidate cells by OOF probability (max over a
    cell's appearances), take the top-N where N = observed positive cells, union
    with the overpass-0 seed, and compare to the observed final burned mask.
    IoU and capture are the standard perimeter-agreement metrics. The
    mechanistic CA baseline footprint IoU was ~9 % — the comparison reference.
    """
    rows = []
    for fid, g in oof.groupby("fire_id"):
        seq = sequences[fid]
        grid = grids[fid]
        seed_mask = seq.cumulative[0]
        observed = seq.final_mask()
        n_pos = int(g["label"].sum())
        # max OOF prob per unique candidate cell
        gg = g.groupby(["row", "col"])["oof_pred"].max().reset_index()
        gg = gg.sort_values("oof_pred", ascending=False)
        top = gg.head(n_pos)
        pred = seed_mask.copy()
        pred[top["row"].to_numpy(), top["col"].to_numpy()] = True
        inter = np.logical_and(pred, observed).sum()
        union = np.logical_or(pred, observed).sum()
        iou = float(inter / union) if union else float("nan")
        capture = float(inter / observed.sum()) if observed.sum() else float("nan")
        rows.append({
            "fire_id": fid, "n_pred_ignitions": n_pos,
            "observed_cells": int(observed.sum()),
            "iou": round(iou, 4), "capture": round(capture, 4),
        })
    return pd.DataFrame(rows)


def permutation_importance_lofo(
    df: pd.DataFrame, features: list[str], fold_models: dict,
    base_oof: pd.DataFrame, seed: int = 42, n_repeats: int = 5,
) -> pd.DataFrame:
    """LOFO permutation importance = pooled-AUC drop when a feature is shuffled.

    Reuses the already-fitted per-fold models; for each held-out fire we shuffle
    one feature column in the test fold, re-predict, and measure the drop in
    pooled out-of-fold ROC-AUC, averaged over ``n_repeats`` shuffles.
    """
    rng = np.random.default_rng(seed)
    base_auc = _safe_auc(base_oof["label"], base_oof["oof_pred"])
    fires = sorted(df["fire_id"].unique())
    rows = []
    for feat in features:
        drops = []
        for _ in range(n_repeats):
            parts = []
            for test_fire in fires:
                te = df[df["fire_id"] == test_fire].copy()
                te[feat] = rng.permutation(te[feat].to_numpy())
                p = fold_models[test_fire].predict_proba(te[features])[:, 1]
                parts.append(pd.DataFrame({"label": te["label"].to_numpy(), "p": p}))
            allp = pd.concat(parts, ignore_index=True)
            drops.append(base_auc - _safe_auc(allp["label"], allp["p"]))
        rows.append({
            "feature": feat,
            "auc_drop_mean": float(np.mean(drops)),
            "auc_drop_std": float(np.std(drops)),
        })
    return pd.DataFrame(rows).sort_values("auc_drop_mean", ascending=False)


def feature_group(feat: str) -> str:
    from .features import FUEL, PROXIMITY, TERRAIN, V1_PROXY, WEATHER
    if feat in PROXIMITY:
        return "intensity/proximity"
    if feat in TERRAIN:
        return "terrain"
    if feat in FUEL:
        return "fuel"
    if feat in WEATHER:
        return "weather"
    if feat in V1_PROXY:
        return "v1_proxy"
    return "other"


__all__ = [
    "XGB_PARAMS", "BANDS", "make_model", "lofo_predict", "per_fire_metrics",
    "summary_metrics", "footprint_metrics", "permutation_importance_lofo",
    "feature_group",
]
