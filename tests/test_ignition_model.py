"""Tests for metric helpers, baselines, and the leave-one-fire-out harness."""

from __future__ import annotations

import numpy as np
import pandas as pd

from wildfireguardian.ignition_model.config import PipelineConfig
from wildfireguardian.ignition_model.features import FEATURE_COLUMNS
from wildfireguardian.ignition_model.model import (
    _conditional_by_distance,
    _operating_point,
    _safe_auc,
    leave_one_fire_out,
    make_model,
)


def test_safe_auc_single_class_is_none():
    assert _safe_auc(np.array([0, 0, 0]), np.array([0.1, 0.2, 0.3])) is None
    assert _safe_auc(np.array([0, 1]), np.array([0.1, 0.9])) == 1.0


def test_operating_point_prevalence_matched():
    y = np.array([1, 1, 0, 0, 0, 0])
    p = np.array([0.9, 0.8, 0.7, 0.2, 0.1, 0.05])
    op = _operating_point(y, p)
    # K=2 positives -> top-2 predicted; both true positives are in top-2
    assert op["k"] == 2
    assert op["recall"] == 1.0
    assert op["precision"] == 1.0
    assert op["iou"] == 1.0


def test_operating_point_partial():
    y = np.array([1, 0, 1, 0])
    p = np.array([0.9, 0.8, 0.2, 0.1])  # top-2 = {0.9(TP),0.8(FP)}
    op = _operating_point(y, p)
    assert op["k"] == 2
    assert op["recall"] == 0.5
    assert op["precision"] == 0.5
    assert abs(op["iou"] - 1 / 3) < 1e-9


def test_conditional_by_distance_partitions():
    # bands are (lo, hi]: 375 m (orthogonal neighbour) lands in the first band
    y = np.array([0, 1, 0, 1])
    p = np.array([0.1, 0.9, 0.2, 0.8])
    dist = np.array([100.0, 375.0, 1000.0, 5000.0])
    cond = _conditional_by_distance(y, p, dist)
    assert cond["<=375m"]["n"] == 2  # 100 and exactly-375
    assert cond["750-1500m"]["n"] == 1  # 1000
    assert cond[">1500m"]["n"] == 1  # 5000
    # single-class bands -> auc None
    assert cond["750-1500m"]["auc"] is None
    assert cond[">1500m"]["auc"] is None


def test_make_model_is_conservative():
    m = make_model(PipelineConfig())
    params = m.get_params()
    assert params["max_depth"] == 4
    assert params["n_estimators"] == 300
    assert params.get("scale_pos_weight") in (None, 1, 1.0)


def _toy_fire(fire_id, n, seed, signal):
    rng = np.random.default_rng(seed)
    df = pd.DataFrame(
        {c: rng.normal(size=n) for c in FEATURE_COLUMNS}
    )
    df["dist_to_nearest_burning_m"] = rng.uniform(0, 2000, n)
    # label correlated with proximity + a feature so AUC > 0.5 is learnable
    score = -df["dist_to_nearest_burning_m"] / 2000 + signal * df["slope_alignment"]
    df["label"] = (score > np.quantile(score, 0.95)).astype(int)
    df["fire_id"] = fire_id
    df["transition"] = 0
    df["row"] = np.arange(n)
    df["col"] = np.arange(n)
    return df


def test_leave_one_fire_out_runs_and_separates_fires():
    cfg = PipelineConfig()
    data = pd.concat(
        [_toy_fire(f"fire{i}", 400, seed=i, signal=1.0) for i in range(3)],
        ignore_index=True,
    )
    res = leave_one_fire_out(data, cfg)
    assert set(res["per_fire"]) == {"fire0", "fire1", "fire2"}
    for fid, r in res["per_fire"].items():
        assert "roc_auc" in r
        assert 0.0 <= r["roc_auc"] <= 1.0
        # held-out predictions exist for every fire and only that fire
        oof_fire = res["oof"][res["oof"]["fire_id"] == fid]
        assert len(oof_fire) == 400
