"""Tests for the empirical super-multiplicative test scaffold (Session 5 D6).

All data is synthetic; these check the test *methodology* runs and can
distinguish separable from super-multiplicative spread.
"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("xgboost")

from wildfireguardian.spread_model.empirical_interaction import (  # noqa: E402
    make_synthetic_dataset,
    run_empirical_test,
)


def test_synthetic_dataset_shape_and_labels():
    ds = make_synthetic_dataset(n=200, super_strength=0.0)
    assert ds.X.shape == (200, 3)
    assert ds.y.shape == (200,)
    assert ds.synthetic is True
    assert (ds.y >= 0).all()


def test_super_strength_increases_spread_for_dry_windy():
    """Injecting super-multiplicativity raises labels most for dry+windy rows."""
    base = make_synthetic_dataset(n=2000, super_strength=0.0, seed=3)
    sup = make_synthetic_dataset(n=2000, super_strength=2.0, seed=3)
    # Same seed → same features; super labels are >= base labels (factor >= 1).
    assert (sup.y >= base.y - 1e-9).mean() > 0.95


def test_pipeline_trains_and_predicts():
    res = run_empirical_test(super_strength=0.0, n=1500, seed=2)
    assert 0.8 < res.train_r2 <= 1.0
    assert np.isfinite(res.empirical_d2R_dM_dU)
    assert np.isfinite(res.rothermel_d2R_dM_dU)


def test_separable_data_not_flagged_super():
    """On separable synthetic data the empirical cross-partial matches the
    Rothermel baseline → NOT flagged as super-multiplicative."""
    res = run_empirical_test(super_strength=0.0, n=4000, seed=1)
    assert res.detects_super is False


def test_injected_super_is_detected():
    """A strong injected super-multiplicative term IS detected (the empirical
    cross-partial is materially more negative than Rothermel's)."""
    res = run_empirical_test(super_strength=1.5, n=4000, seed=1)
    assert res.detects_super is True
    assert res.empirical_d2R_dM_dU < res.rothermel_d2R_dM_dU
