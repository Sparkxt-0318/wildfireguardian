"""Tests for the Session 4 warm-up fix (disc ignition) and baseline fairness."""

from __future__ import annotations

import math

import numpy as np
import pytest

from wildfireguardian.spread_model.cellular_automaton import (
    CellState,
    FireGrid,
    WindField,
)
from wildfireguardian.utils.regions import YEONGDEOK_2025
from wildfireguardian.validation.baselines import (
    BaselineConfig,
    run_isotropic_baseline,
    run_persistence_baseline,
)


# ---------------------------------------------------------------------------
# ignite_disc
# ---------------------------------------------------------------------------


def test_ignite_disc_lights_multiple_cells() -> None:
    grid = FireGrid(nrows=41, ncols=41, cell_size_m=100.0)
    n = grid.ignite_disc(20, 20, radius_m=250.0)
    # radius 250m at 100m cells → cells within 2.5 cell-radii
    assert n > 1
    burning = int((grid.state == CellState.BURNING).sum())
    assert burning == n


def test_ignite_disc_area_approximates_pi_r2() -> None:
    grid = FireGrid(nrows=101, ncols=101, cell_size_m=50.0)
    radius = 500.0
    n = grid.ignite_disc(50, 50, radius_m=radius)
    burned_area = n * 50.0 * 50.0
    expected = math.pi * radius ** 2
    # Discretisation error: within 15%.
    assert abs(burned_area - expected) / expected < 0.15


def test_ignite_disc_tiny_radius_lights_center() -> None:
    grid = FireGrid(nrows=11, ncols=11, cell_size_m=100.0)
    n = grid.ignite_disc(5, 5, radius_m=10.0)   # smaller than half a cell
    assert n == 1
    assert grid.state[5, 5] == CellState.BURNING


def test_ignite_disc_clips_at_grid_edge() -> None:
    grid = FireGrid(nrows=11, ncols=11, cell_size_m=100.0)
    # Disc centred at corner; only in-bounds cells lit.
    n = grid.ignite_disc(0, 0, radius_m=300.0)
    assert n >= 1
    # No crash, all lit cells in-bounds.
    ii, jj = np.where(grid.state == CellState.BURNING)
    assert (ii >= 0).all() and (jj >= 0).all()


# ---------------------------------------------------------------------------
# Disc ignition fixes the warm-up: faster early spread than point ignition
# ---------------------------------------------------------------------------


def test_disc_ignition_grows_faster_early_than_point() -> None:
    """A disc-ignited fire has a larger burned area at 30 min than a
    point-ignited one (the warm-up fix)."""
    def run(radius_m: float) -> int:
        grid = FireGrid(nrows=81, ncols=81, cell_size_m=100.0,
                        residence_time_min=120.0)
        from wildfireguardian.spread_model.rothermel import KOREAN_PINUS
        grid.fuel_model_id[:] = KOREAN_PINUS
        grid.fuel_moisture[:] = 0.40
        if radius_m > 0:
            grid.ignite_disc(40, 40, radius_m=radius_m)
        else:
            grid.ignite_point(40, 40)
        wind = WindField.from_meteo(4.0, 270.0)
        for t in range(30):
            grid.step(1.0, wind, current_time_min=float(t))
        return int((grid.state >= CellState.BURNING).sum())

    point_cells = run(0.0)
    disc_cells = run(200.0)
    assert disc_cells > point_cells


# ---------------------------------------------------------------------------
# Baseline fairness: baselines honour initial_radius_m
# ---------------------------------------------------------------------------


def _bcfg(initial_radius_m: float = 0.0) -> BaselineConfig:
    return BaselineConfig(
        ignition_xy_5179=(1_170_000.0, 1_830_000.0),
        duration_min=360.0,
        snapshot_every_min=60.0,
        cell_size_m=100.0,
        initial_radius_m=initial_radius_m,
    )


def test_persistence_baseline_uses_initial_disc_when_set() -> None:
    series = run_persistence_baseline(_bcfg(initial_radius_m=200.0))
    expected_area = math.pi * 200.0 ** 2
    for s in series:
        assert s.area_m2 == pytest.approx(expected_area, rel=1e-3)


def test_persistence_baseline_single_cell_when_zero_radius() -> None:
    series = run_persistence_baseline(_bcfg(initial_radius_m=0.0))
    assert series[0].area_m2 == pytest.approx(100.0 * 100.0)


def test_isotropic_baseline_starts_at_initial_radius() -> None:
    r0 = 200.0
    R = 10.0
    series = run_isotropic_baseline(_bcfg(initial_radius_m=r0), head_fire_rate_m_min=R)
    # At t=0, area = π r0²
    assert series[0].area_m2 == pytest.approx(math.pi * r0 ** 2, rel=1e-3)
    # At t=60, radius = r0 + R*60
    expected_r = r0 + R * 60.0
    assert series[1].area_m2 == pytest.approx(math.pi * expected_r ** 2, rel=1e-3)


def test_isotropic_baseline_zero_radius_starts_at_origin() -> None:
    series = run_isotropic_baseline(_bcfg(initial_radius_m=0.0), head_fire_rate_m_min=10.0)
    assert series[0].area_m2 == 0.0


# ---------------------------------------------------------------------------
# Harness wiring: ModelConfig.ignition_radius_m reaches the grid
# ---------------------------------------------------------------------------


def test_model_config_ignition_radius_increases_initial_burn() -> None:
    """run_validation_with_baselines with a non-zero ignition radius should
    start the model with more than one burning cell."""
    from pathlib import Path

    from wildfireguardian.validation import (
        ModelConfig,
        load_case,
        run_validation_with_baselines,
    )
    case = load_case(
        Path(__file__).resolve().parents[1]
        / "data" / "validation_cases" / "yeongdeok_2025.json"
    )
    cfg = ModelConfig(
        cell_size_m=500.0, duration_min=60.0, dt_min=10.0,
        snapshot_every_min=30.0, dem_source="srtm", fuel_source="synthetic",
        ignition_radius_m=1000.0,
    )
    result = run_validation_with_baselines(case, cfg, horizons_min=(60.0,))
    # First predicted snapshot area should exceed a single 500m cell (0.25 km² = 25 ha)
    first_area_ha = result.predicted_model[0].area_m2 / 1e4
    assert first_area_ha > 25.0
    # Baselines got the same initial disc.
    assert result.metrics_persistence[0].predicted_area_ha > 25.0
