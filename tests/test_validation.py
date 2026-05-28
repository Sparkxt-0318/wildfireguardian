"""Unit tests for the validation metrics and harness (Session 2)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import Polygon, box

from wildfireguardian.validation.harness import (
    ModelConfig,
    ValidationCase,
    load_case,
    run_validation,
)
from wildfireguardian.validation.metrics import (
    PerimeterAtTime,
    brier_score,
    brier_skill_score,
    lead_time_gain,
    perimeter_iou,
    perimeter_sorensen_dice,
    perimeter_symmetric_difference_area_km2,
    temporal_perimeter_rmse,
)


# ---------------------------------------------------------------------------
# IoU / Sørensen-Dice
# ---------------------------------------------------------------------------


def test_iou_identical_polygons() -> None:
    p = box(0, 0, 100, 100)
    assert perimeter_iou(p, p) == pytest.approx(1.0)


def test_iou_disjoint_polygons() -> None:
    a = box(0, 0, 100, 100)
    b = box(200, 200, 300, 300)
    assert perimeter_iou(a, b) == 0.0


def test_iou_partial_overlap_half() -> None:
    """Two identical-area boxes that overlap 50% → IoU = 1/3."""
    a = box(0, 0, 100, 100)         # area 10_000
    b = box(50, 0, 150, 100)        # area 10_000, half overlaps
    # intersection = 50*100 = 5000; union = 10000 + 10000 - 5000 = 15000
    expected = 5000 / 15000
    assert perimeter_iou(a, b) == pytest.approx(expected)


def test_iou_none_inputs() -> None:
    assert perimeter_iou(None, None) == 1.0
    p = box(0, 0, 10, 10)
    assert perimeter_iou(None, p) == 0.0
    assert perimeter_iou(p, None) == 0.0


def test_sorensen_dice_identical() -> None:
    p = box(0, 0, 100, 100)
    assert perimeter_sorensen_dice(p, p) == pytest.approx(1.0)


def test_sorensen_dice_disjoint() -> None:
    a = box(0, 0, 100, 100)
    b = box(200, 200, 300, 300)
    assert perimeter_sorensen_dice(a, b) == 0.0


def test_sorensen_dice_partial_overlap_half() -> None:
    a = box(0, 0, 100, 100)
    b = box(50, 0, 150, 100)
    # 2*5000 / (10000 + 10000) = 0.5
    assert perimeter_sorensen_dice(a, b) == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Symmetric difference area
# ---------------------------------------------------------------------------


def test_symmetric_difference_disjoint_in_km2() -> None:
    """Two disjoint 1 km² boxes → sym-diff area = 2 km²."""
    # 1000 m × 1000 m = 1 km².
    a = box(0, 0, 1000, 1000)
    b = box(2000, 2000, 3000, 3000)
    assert perimeter_symmetric_difference_area_km2(a, b) == pytest.approx(2.0)


def test_symmetric_difference_identical_zero() -> None:
    p = box(0, 0, 1000, 1000)
    assert perimeter_symmetric_difference_area_km2(p, p) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Brier score
# ---------------------------------------------------------------------------


def test_brier_perfect_prediction_is_zero() -> None:
    pred = np.array([[1.0, 0.0], [0.0, 1.0]])
    obs = np.array([[1, 0], [0, 1]], dtype=np.uint8)
    assert brier_score(pred, obs) == pytest.approx(0.0)


def test_brier_constant_half_on_binary() -> None:
    """Constant 0.5 prediction on a 50/50 binary truth → BS = 0.25."""
    pred = np.full((10, 10), 0.5)
    obs = np.zeros((10, 10), dtype=np.uint8)
    obs[:5] = 1
    assert brier_score(pred, obs) == pytest.approx(0.25)


def test_brier_perfectly_wrong_is_one() -> None:
    pred = np.array([[0.0, 1.0]])
    obs = np.array([[1, 0]], dtype=np.uint8)
    assert brier_score(pred, obs) == pytest.approx(1.0)


def test_brier_skill_score_perfect_is_one() -> None:
    pred = np.array([[1.0, 0.0]])
    obs = np.array([[1, 0]], dtype=np.uint8)
    assert brier_skill_score(pred, obs) == pytest.approx(1.0)


def test_brier_skill_score_on_degenerate_obs_returns_nan() -> None:
    pred = np.array([[0.7]])
    obs_all_zero = np.array([[0]], dtype=np.uint8)
    import math
    assert math.isnan(brier_skill_score(pred, obs_all_zero))


def test_brier_shape_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        brier_score(np.array([0.5]), np.array([[1]], dtype=np.uint8))


# ---------------------------------------------------------------------------
# Lead-time gain
# ---------------------------------------------------------------------------


def test_lead_time_gain_positive_means_earlier_prediction() -> None:
    pred_t = datetime(2025, 3, 22, 12, 0, 0)
    actual_t = datetime(2025, 3, 22, 14, 30, 0)
    gain = lead_time_gain(pred_t, actual_t)
    assert gain == timedelta(hours=2, minutes=30)
    assert gain.total_seconds() > 0


def test_lead_time_gain_zero_when_simultaneous() -> None:
    t = datetime(2025, 3, 22, 12, 0, 0)
    assert lead_time_gain(t, t) == timedelta(0)


def test_lead_time_gain_negative_when_late() -> None:
    pred_t = datetime(2025, 3, 22, 16, 0, 0)
    actual_t = datetime(2025, 3, 22, 14, 30, 0)
    assert lead_time_gain(pred_t, actual_t) == timedelta(hours=-1, minutes=-30)


def test_lead_time_gain_tz_consistency_required() -> None:
    from datetime import timezone
    aware = datetime(2025, 3, 22, 12, 0, 0, tzinfo=timezone.utc)
    naive = datetime(2025, 3, 22, 14, 0, 0)
    with pytest.raises(ValueError):
        lead_time_gain(aware, naive)


# ---------------------------------------------------------------------------
# Temporal RMSE
# ---------------------------------------------------------------------------


def test_temporal_perimeter_rmse_identical_series_is_zero() -> None:
    series = [
        PerimeterAtTime(time_min=60.0, polygon=None, area_m2=10_000.0),
        PerimeterAtTime(time_min=180.0, polygon=None, area_m2=50_000.0),
    ]
    rmse = temporal_perimeter_rmse(series, series, time_horizons_min=(60.0, 180.0))
    assert rmse[60.0] == pytest.approx(0.0)
    assert rmse[180.0] == pytest.approx(0.0)


def test_temporal_perimeter_rmse_picks_nearest_snapshot() -> None:
    pred = [PerimeterAtTime(50.0, None, 12_000.0)]
    obs = [PerimeterAtTime(60.0, None, 10_000.0)]
    rmse = temporal_perimeter_rmse(pred, obs, time_horizons_min=(60.0,))
    # diff = (12000 - 10000) / 10000 = 0.2 ha → RMSE = 0.2
    assert rmse[60.0] == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# Harness end-to-end on synthetic data
# ---------------------------------------------------------------------------


def test_load_case_reads_yeongdeok_manifest() -> None:
    path = Path(__file__).resolve().parents[1] / "data" / "validation_cases" / "yeongdeok_2025.json"
    assert path.exists(), path
    case = load_case(path)
    assert case.region.name == "yeongdeok_2025"
    assert case.observed_ignition_point_wgs84 == (129.37, 36.50)
    assert case.observed_total_burn_area_ha == 3800.0
    assert len(case.observed_official_warnings) == 2


def test_harness_runs_end_to_end_on_synthetic_yeongdeok() -> None:
    """Smoke test: validation harness completes without crashing."""
    from wildfireguardian.utils.regions import YEONGDEOK_2025

    case = ValidationCase(
        region=YEONGDEOK_2025,
        observed_ignition_point_wgs84=(129.37, 36.50),
        observed_total_burn_area_ha=3800.0,
    )
    # Use a coarse/short config for the test.
    cfg = ModelConfig(
        cell_size_m=1000.0,        # very coarse — for test speed
        duration_min=120.0,
        dt_min=5.0,
        snapshot_every_min=60.0,
    )
    results = run_validation(case, cfg)
    assert results.predicted_perimeters
    assert results.predicted_perimeters[-1].area_m2 >= 0.0
    # Temporal RMSE is computed because observed_total_burn_area_ha is set.
    assert results.temporal_area_rmse_ha
    # As a dict for serialisation.
    d = results.as_dict()
    assert d["region"] == "yeongdeok_2025"


def test_harness_handles_missing_observed_data_gracefully() -> None:
    """No observed perimeter, no observed area → harness skips comparison
    metrics without crashing."""
    from wildfireguardian.utils.regions import YEONGDEOK_2025

    case = ValidationCase(region=YEONGDEOK_2025)
    cfg = ModelConfig(cell_size_m=1000.0, duration_min=60.0, dt_min=5.0,
                     snapshot_every_min=30.0)
    results = run_validation(case, cfg)
    assert results.final_iou is None
    assert results.brier_score_final is None
    # But predicted perimeters should still be there.
    assert results.predicted_perimeters
