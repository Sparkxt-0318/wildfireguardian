"""Tests for the spotting kernel (Session 6 D3)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from wildfireguardian.spread_model.spotting import (
    flame_length_m,
    landing_cell,
    max_spot_distance,
    sample_spot_landing,
)


# ---------------------------------------------------------------------------
# Flame length / spot distance scaling
# ---------------------------------------------------------------------------


def test_flame_length_increases_with_intensity():
    assert flame_length_m(10000.0) > flame_length_m(1000.0)
    assert flame_length_m(0.0) == 0.0


def test_flame_length_byram_magnitude():
    """A ~1000 kW/m surface fire → ~2 m flame; ~10 MW/m crown → ~5–6 m."""
    assert 1.5 < flame_length_m(1000.0) < 3.0
    assert 4.0 < flame_length_m(10000.0) < 7.0


def test_spot_distance_increases_with_wind_and_intensity():
    d_lowU = max_spot_distance(5.0, 5.0)
    d_hiU = max_spot_distance(5.0, 25.0)
    assert d_hiU > d_lowU
    d_lowL = max_spot_distance(2.0, 15.0)
    d_hiL = max_spot_distance(8.0, 15.0)
    assert d_hiL > d_lowL


def test_spot_distance_physical_range_for_crown_fire():
    """Crown-fire flame (~5–6 m) at 10–30 m/s → hundreds of m to ~1.5 km."""
    fl = flame_length_m(10000.0)
    d10 = max_spot_distance(fl, 10.0)
    d30 = max_spot_distance(fl, 30.0)
    assert 100.0 < d10 < 1500.0, d10
    assert 300.0 < d30 < 3000.0, d30


def test_no_spot_without_wind_or_flame():
    assert max_spot_distance(0.0, 20.0) == 0.0
    assert max_spot_distance(5.0, 0.0) == 0.0


# ---------------------------------------------------------------------------
# Landing geometry
# ---------------------------------------------------------------------------


def test_landing_cell_downwind_east():
    """Wind blowing east (90°) → ember lands east (larger j, same i)."""
    ni, nj = landing_cell(50, 50, distance_m=500.0, bearing_deg=90.0, cell_size_m=50.0)
    assert nj > 50
    assert ni == 50


def test_landing_cell_downwind_north():
    """Wind toward north (0°) → ember lands north (smaller i)."""
    ni, nj = landing_cell(50, 50, distance_m=500.0, bearing_deg=0.0, cell_size_m=50.0)
    assert ni < 50
    assert nj == 50


def test_sample_landing_within_cone_and_range():
    rng = np.random.default_rng(0)
    d_max = 1000.0
    for _ in range(200):
        d, bearing = sample_spot_landing(rng, d_max, wind_to_deg=90.0, cone_half_deg=25.0)
        assert 0.3 * d_max <= d <= d_max
        # bearing within ±25° of 90 (mod 360)
        diff = abs(((bearing - 90.0 + 180) % 360) - 180)
        assert diff <= 25.0 + 1e-9


# ---------------------------------------------------------------------------
# Integration: spotting creates downwind ignitions ahead of the front
# ---------------------------------------------------------------------------


def test_spotting_creates_detached_ignitions():
    """With spotting ON and active-crown cells, embers ignite cells ahead of
    the contiguous front."""
    from wildfireguardian.spread_model.cellular_automaton import (
        CellState,
        FireGrid,
        WindField,
    )
    from wildfireguardian.spread_model.rothermel import KOREAN_PINUS

    grid = FireGrid(nrows=120, ncols=120, cell_size_m=50.0, residence_time_min=120.0)
    grid.fuel_model_id[:] = KOREAN_PINUS
    grid.fuel_moisture[:] = 0.40
    grid.enable_crown_fire = True
    grid.enable_spotting = True
    grid.spotting_seed = 1
    grid.spot_probability_per_min = 0.1   # raise for a deterministic-ish test
    # Force a block of active-crown burning cells by hand near the centre.
    grid.ignite_disc(60, 40, radius_m=300.0)
    # Strong 10-m wind so crowning + spotting fire.
    wind = WindField.from_meteo(speed_ms=2.5, from_deg=270.0)   # midflame; .at_10m = /0.1 = 25 m/s
    for t in range(40):
        grid.step(1.0, wind, current_time_min=float(t))
    # Spotting should have produced at least one ember ignition.
    assert grid.n_spot_ignitions >= 1
