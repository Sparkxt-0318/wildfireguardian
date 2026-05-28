"""Session 3 validation tests: baselines + observed-perimeter loading +
end-to-end harness with baselines."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from shapely.geometry import Polygon

from wildfireguardian.utils.regions import YEONGDEOK_2025
from wildfireguardian.validation import (
    BaselineConfig,
    HorizonMetrics,
    ModelConfig,
    ValidationCase,
    compute_horizon_metrics,
    load_case,
    load_observed_perimeter_series,
    run_isotropic_baseline,
    run_persistence_baseline,
    run_validation_with_baselines,
)


# ---------------------------------------------------------------------------
# Persistence baseline
# ---------------------------------------------------------------------------


def _bcfg() -> BaselineConfig:
    return BaselineConfig(
        ignition_xy_5179=(1_170_000.0, 1_830_000.0),
        duration_min=360.0,
        snapshot_every_min=60.0,
        cell_size_m=100.0,
    )


def test_persistence_baseline_area_constant() -> None:
    series = run_persistence_baseline(_bcfg())
    assert len(series) >= 6
    expected_area_m2 = 100.0 * 100.0
    for s in series:
        assert s.area_m2 == pytest.approx(expected_area_m2)


def test_persistence_baseline_polygon_doesnt_change() -> None:
    series = run_persistence_baseline(_bcfg())
    polys = [s.polygon for s in series]
    # Same area at every snapshot.
    areas = [p.area for p in polys]
    assert max(areas) - min(areas) < 1.0


# ---------------------------------------------------------------------------
# Isotropic baseline
# ---------------------------------------------------------------------------


def test_isotropic_baseline_grows_as_pi_r2() -> None:
    series = run_isotropic_baseline(_bcfg(), head_fire_rate_m_min=10.0)
    # At t=60 min, r = 600 m, area ≈ π * 600² = 1.131e6 m²
    s60 = series[1]
    assert s60.time_min == pytest.approx(60.0)
    expected = 3.14159265 * 600.0 * 600.0
    assert s60.area_m2 == pytest.approx(expected, rel=1e-3)


def test_isotropic_baseline_zero_at_t0() -> None:
    series = run_isotropic_baseline(_bcfg(), head_fire_rate_m_min=10.0)
    assert series[0].time_min == 0.0
    assert series[0].polygon is None
    assert series[0].area_m2 == 0.0


def test_isotropic_baseline_polygon_is_circle() -> None:
    """Polygon at t=60 should be approximately circular (low aspect ratio)."""
    series = run_isotropic_baseline(_bcfg(), head_fire_rate_m_min=5.0)
    poly = series[1].polygon
    assert poly is not None
    minx, miny, maxx, maxy = poly.bounds
    width = maxx - minx
    height = maxy - miny
    # Width and height should be equal to within ~1% (circle has equal axes)
    assert abs(width - height) / max(width, height) < 0.02


# ---------------------------------------------------------------------------
# Observed perimeter loading
# ---------------------------------------------------------------------------


def test_load_observed_perimeter_series_for_yeongdeok() -> None:
    case = load_case(
        Path(__file__).resolve().parents[1]
        / "data" / "validation_cases" / "yeongdeok_2025.json"
    )
    series = load_observed_perimeter_series(case)
    # Should have the 11 features from the approximate perimeter
    assert len(series) == 11
    # Sorted by time
    for prev, nxt in zip(series, series[1:]):
        assert nxt.time_min >= prev.time_min
    # First (ignition) area near 0.5 ha, last (24h) is 3800 ha
    assert abs(series[0].area_m2 - 5000.0) < 100.0
    assert abs(series[-2].area_m2 - 38_000_000.0) < 10_000.0


def test_observed_perimeters_are_in_epsg5179_metres() -> None:
    """After loading + reprojection, perimeters must have EPSG:5179 coords
    (large positive metres)."""
    case = load_case(
        Path(__file__).resolve().parents[1]
        / "data" / "validation_cases" / "yeongdeok_2025.json"
    )
    series = load_observed_perimeter_series(case)
    # Final perimeter at t=24h
    poly = series[-1].polygon
    assert poly is not None
    minx, miny, maxx, maxy = poly.bounds
    # Yeongdeok area in EPSG:5179 lies near (1.16e6, 1.83e6)
    assert 1.0e6 < minx < 1.2e6
    assert 1.8e6 < miny < 1.9e6


def test_load_observed_perimeter_returns_empty_when_missing() -> None:
    case = ValidationCase(region=YEONGDEOK_2025)
    series = load_observed_perimeter_series(case)
    assert series == []


# ---------------------------------------------------------------------------
# compute_horizon_metrics
# ---------------------------------------------------------------------------


def test_compute_horizon_metrics_identical_series_gives_iou_1() -> None:
    from wildfireguardian.validation.metrics import PerimeterAtTime
    poly = Polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])
    s = [
        PerimeterAtTime(60.0, poly, 100.0),
        PerimeterAtTime(180.0, poly, 100.0),
    ]
    metrics = compute_horizon_metrics(s, s, (60.0, 180.0))
    assert all(m.iou == pytest.approx(1.0) for m in metrics)
    assert all(m.sorensen_dice == pytest.approx(1.0) for m in metrics)


def test_compute_horizon_metrics_disjoint_gives_iou_0() -> None:
    from wildfireguardian.validation.metrics import PerimeterAtTime
    p1 = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    p2 = Polygon([(100, 0), (110, 0), (110, 10), (100, 10)])
    s1 = [PerimeterAtTime(60.0, p1, 100.0)]
    s2 = [PerimeterAtTime(60.0, p2, 100.0)]
    metrics = compute_horizon_metrics(s1, s2, (60.0,))
    assert metrics[0].iou == 0.0


def test_compute_horizon_metrics_returns_none_metrics_when_no_observed() -> None:
    metrics = compute_horizon_metrics([], [], (60.0, 180.0))
    assert all(m.iou is None for m in metrics)


# ---------------------------------------------------------------------------
# Smoke test: end-to-end with baselines on Yeongdeok
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[1] / "data" / "raw" / "dem" / "srtm" / "N36E129.hgt").exists(),
    reason="SRTM tile not cached",
)
def test_run_validation_with_baselines_end_to_end() -> None:
    """Smoke test: harness completes and returns metric structure."""
    case = load_case(
        Path(__file__).resolve().parents[1]
        / "data" / "validation_cases" / "yeongdeok_2025.json"
    )
    # Coarse config for test speed.
    cfg = ModelConfig(
        cell_size_m=500.0,
        wind_speed_midflame_ms=4.0,
        wind_from_deg=270.0,
        dead_moisture_1h=0.08,
        live_moisture_lfmc=0.40,
        residence_time_min=60.0,
        duration_min=240.0,
        dt_min=5.0,
        snapshot_every_min=60.0,
        dem_source="srtm",
        fuel_source="synthetic",
    )
    result = run_validation_with_baselines(case, cfg, horizons_min=(60.0, 180.0))

    # Structural checks
    assert len(result.metrics_model) == 2
    assert len(result.metrics_persistence) == 2
    assert len(result.metrics_isotropic) == 2
    assert result.mean_head_rate_m_min > 0.0

    # Provenance is recorded
    assert result.data_provenance["dem_source"] == "srtm"
    assert result.data_provenance["dem_synthetic"] is False
    assert result.data_provenance["fuel_synthetic"] is True

    # Persistence baseline area is constant
    persistence_areas = [m.predicted_area_ha for m in result.metrics_persistence]
    assert all(abs(a - persistence_areas[0]) < 0.1 for a in persistence_areas)


def test_validation_with_baselines_requires_ignition_point() -> None:
    case = ValidationCase(region=YEONGDEOK_2025)
    with pytest.raises(ValueError, match="observed_ignition_point_wgs84"):
        run_validation_with_baselines(case)
