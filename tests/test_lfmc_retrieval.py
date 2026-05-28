"""Unit tests for the LFMC retrieval scaffold (Session 3 Tier 2)."""

from __future__ import annotations

import numpy as np
import pytest

from wildfireguardian.lfmc_model.retrieval import (
    FEATURE_NAMES,
    LFMCRetrievalModel,
    demo_train_synthetic,
    generate_synthetic_training_set,
)


def test_feature_names_match_published_literature() -> None:
    """The feature set should match Rao 2020 / Wang 2019 published features."""
    expected = {
        "sar_vv_db", "sar_vh_db", "vh_vv_ratio",
        "ndvi", "ndmi", "precip_acc_30d",
        "elevation_m", "slope_deg", "aspect_deg", "forest_type_code",
    }
    assert set(FEATURE_NAMES) == expected


def test_synthetic_training_set_has_expected_columns() -> None:
    X, y, meta = generate_synthetic_training_set(n_samples=500)
    assert X.shape == (500, len(FEATURE_NAMES))
    assert y.shape == (500,)
    assert meta["synthetic"] is True
    assert "SYNTHETIC" in meta["provenance"]


def test_synthetic_lfmc_in_physical_range() -> None:
    X, y, _ = generate_synthetic_training_set(n_samples=1000, random_seed=7)
    assert (y >= 15.0).all() and (y <= 200.0).all()


def test_xgboost_model_trains_and_predicts() -> None:
    pytest.importorskip("xgboost")
    X, y, _ = generate_synthetic_training_set(n_samples=500, random_seed=42)
    m = LFMCRetrievalModel().fit(X, y, n_estimators=50)
    y_pred = m.predict(X)
    # Training RMSE should be small (model fits the synthetic data)
    rmse = float(np.sqrt(((y_pred - y) ** 2).mean()))
    assert rmse < 20.0, f"training RMSE {rmse:.2f} unexpectedly high"


def test_feature_importances_populated_after_fit() -> None:
    pytest.importorskip("xgboost")
    m = demo_train_synthetic(n_samples=500)
    importances = m.feature_importances_
    assert set(importances) == set(FEATURE_NAMES)
    # All importances are non-negative, sum to ~1.0
    assert all(v >= 0.0 for v in importances.values())
    total = sum(importances.values())
    assert 0.95 < total < 1.05


def test_demo_train_synthetic_tags_metadata_as_synthetic() -> None:
    pytest.importorskip("xgboost")
    m = demo_train_synthetic(n_samples=500)
    assert m.metadata["synthetic"] is True
    assert m.metadata["do_not_use_for_production"] is True


def test_top_features_match_published_literature() -> None:
    """The top 3 features by importance should be VH/VV ratio, NDMI, or
    30-day precipitation — those drive LFMC in the published Rao/Wang work."""
    pytest.importorskip("xgboost")
    m = demo_train_synthetic(n_samples=1500, random_seed=42)
    sorted_features = sorted(
        m.feature_importances_.items(), key=lambda kv: -kv[1],
    )
    top3 = {name for name, _ in sorted_features[:3]}
    published_drivers = {"vh_vv_ratio", "ndmi", "precip_acc_30d", "ndvi"}
    overlap = top3 & published_drivers
    assert len(overlap) >= 2, (
        f"expected ≥ 2 of top-3 to be in published-driver set; got top3={top3}"
    )


def test_predict_before_fit_raises() -> None:
    m = LFMCRetrievalModel()
    with pytest.raises(RuntimeError):
        m.predict(np.zeros((1, len(FEATURE_NAMES))))


def test_fit_with_wrong_feature_count_raises() -> None:
    pytest.importorskip("xgboost")
    bad_X = np.zeros((10, len(FEATURE_NAMES) - 1))
    bad_y = np.zeros(10)
    with pytest.raises(ValueError, match="feature dim mismatch"):
        LFMCRetrievalModel().fit(bad_X, bad_y)
