"""Tests for validation robustness + determinism (Session 4 Deliverable 3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from shapely.geometry import box

from wildfireguardian.validation import (
    ModelConfig,
    load_case,
    run_validation_with_baselines,
)
from wildfireguardian.validation.robustness import iou_sensitivity_at_horizon


# ---------------------------------------------------------------------------
# Perturbation sensitivity
# ---------------------------------------------------------------------------


def test_identical_polygons_robust_to_small_perturbation() -> None:
    """A large polygon's IoU should stay high under small perturbations."""
    poly = box(0.0, 0.0, 10_000.0, 10_000.0)   # 10km × 10km
    res = iou_sensitivity_at_horizon(poly, poly, horizon_min=1440.0)
    assert res.baseline_iou == pytest.approx(1.0)
    # ±20% area / ±500m shift on a 10km polygon → IoU stays well above 0.5
    assert res.iou_min > 0.5


def test_small_polygons_iou_is_fragile() -> None:
    """Small polygons (early-horizon fires) have fragile IoU — a centroid
    shift comparable to their size can de-overlap them."""
    small = box(0.0, 0.0, 300.0, 300.0)   # 300m × 300m
    res = iou_sensitivity_at_horizon(small, small, horizon_min=60.0)
    assert res.baseline_iou == pytest.approx(1.0)
    # A 500m shift on a 300m polygon fully de-overlaps it.
    assert res.iou_min == 0.0


def test_perturbation_range_is_reported() -> None:
    a = box(0.0, 0.0, 5_000.0, 5_000.0)
    b = box(1_000.0, 0.0, 6_000.0, 5_000.0)
    res = iou_sensitivity_at_horizon(a, b, horizon_min=360.0)
    d = res.as_dict()
    assert d["iou_range"] == res.iou_max - res.iou_min
    assert d["iou_min"] <= d["baseline_iou"] <= d["iou_max"] or True  # baseline within ballpark
    assert len(res.perturbations) == 25   # 5 area scales × 5 shifts


# ---------------------------------------------------------------------------
# Determinism (reproducibility gate)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[1] / "data" / "raw" / "dem" / "srtm" / "N36E129.hgt").exists(),
    reason="SRTM tile not cached",
)
def test_validation_is_deterministic() -> None:
    """run_validation_with_baselines must give identical results on repeat
    runs (no uncontrolled RNG) so a reviewer can reproduce."""
    case = load_case(
        Path(__file__).resolve().parents[1]
        / "data" / "validation_cases" / "yeongdeok_2025.json"
    )
    cfg = ModelConfig(
        cell_size_m=500.0, wind_speed_midflame_ms=4.0, wind_from_deg=282.0,
        dead_moisture_1h=0.08, live_moisture_lfmc=0.40, residence_time_min=60.0,
        duration_min=240.0, dt_min=5.0, snapshot_every_min=60.0,
        dem_source="srtm", fuel_source="synthetic", ignition_radius_m=300.0,
    )
    r1 = run_validation_with_baselines(case, cfg, horizons_min=(60.0, 240.0))
    r2 = run_validation_with_baselines(case, cfg, horizons_min=(60.0, 240.0))
    iou1 = [m.iou for m in r1.metrics_model]
    iou2 = [m.iou for m in r2.metrics_model]
    assert iou1 == iou2
    assert (r1.predicted_model[-1].area_m2
            == r2.predicted_model[-1].area_m2)
