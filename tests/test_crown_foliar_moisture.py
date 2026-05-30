"""Session 7: the crown foliar-moisture conflation bug and its fix.

The Session-6 crown trigger fed the surface live-fuel moisture (the
drought-cured-understory LFMC, ~40%) into the Van Wagner tree-crown check.
Live conifer crowns stay ~80-120% (measured Korean value 119%). Using 40%
artificially lowers the critical intensity and makes crowning trigger too
easily. These tests pin the bug and the decoupling fix.
"""

from __future__ import annotations

import numpy as np
import pytest

from wildfireguardian.spread_model.cellular_automaton import (
    CellState, FireGrid, WindField,
)
from wildfireguardian.spread_model.crown_fire import (
    CrownRegime, critical_surface_intensity,
)
from wildfireguardian.spread_model.rothermel import KOREAN_PINUS


def test_critical_intensity_much_higher_at_realistic_foliar_moisture():
    """I_o at the measured 119% is ~3.6x the value at the buggy 40%."""
    io_buggy = critical_surface_intensity(4.0, 40.0)    # ~463
    io_real = critical_surface_intensity(4.0, 119.0)    # ~1686
    assert io_real > 3.0 * io_buggy


def test_grid_default_reuses_surface_lfmc_as_crown_fmc():
    """Default (crown_foliar_moisture_pct=None) reproduces the Session-6
    behaviour: FMC = surface LFMC × 100."""
    grid = FireGrid(nrows=5, ncols=5)
    grid.fuel_moisture[:] = 0.40
    assert grid._crown_foliar_moisture_pct(0.40) == pytest.approx(40.0)


def test_grid_decoupled_crown_fmc_overrides():
    grid = FireGrid(nrows=5, ncols=5)
    grid.crown_foliar_moisture_pct = 119.0
    assert grid._crown_foliar_moisture_pct(0.40) == pytest.approx(119.0)


def _run_small(crown_fmc, slope_deg=30.0, midflame=2.5):
    """A small uniform grid of steep, windy Korean pine; return active-crown
    fraction among burned cells."""
    grid = FireGrid(nrows=40, ncols=40, cell_size_m=50.0, residence_time_min=90.0)
    grid.fuel_model_id[:] = KOREAN_PINUS
    grid.fuel_moisture[:] = 0.40
    grid.slope_degrees[:] = slope_deg
    grid.enable_crown_fire = True
    grid.crown_foliar_moisture_pct = crown_fmc
    grid.ignite_disc(20, 12, radius_m=200.0)
    wind = WindField.from_meteo(midflame, 270.0)   # midflame; .at_10m = /0.1
    for t in range(60):
        grid.step(1.0, wind, current_time_min=float(t))
    burned = grid.state >= CellState.BURNING
    nb = int(burned.sum())
    return int((grid.regime[burned] == 2).sum()) / max(nb, 1)


def test_buggy_fmc_crowns_on_steep_terrain():
    """At the buggy 40% FMC, steep windy Korean pine crowns substantially."""
    frac = _run_small(crown_fmc=None)   # None → uses 40% surface LFMC
    assert frac > 0.2, frac


def test_realistic_fmc_largely_suppresses_crowning():
    """Decoupling to the measured 119% collapses crowning on the same stand —
    confirming the Session-6 crown result was a foliar-moisture artifact."""
    frac_buggy = _run_small(crown_fmc=None)
    frac_real = _run_small(crown_fmc=119.0)
    assert frac_real < 0.2 * frac_buggy + 1e-9
    assert frac_real < 0.05, frac_real
