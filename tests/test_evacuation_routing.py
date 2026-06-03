"""Tests for the probabilistic-hazard evacuation router (the routing spine).

These build the hazard and network synthetically, so they run without the
(git-ignored) FIRMS dataset. The constructed "danger case" mirrors the real
demonstration: a hazard that grows from the west makes the *nearest* (western)
shelter unsafe, so the fire-blind naive router walks into it while the
future-aware router detours to the safe eastern shelter.
"""

from __future__ import annotations

import networkx as nx
import numpy as np
import pytest

from wildfireguardian.routing.evacuation import (
    ELDERLY_FLAT_SPEED_MS,
    RouteResult,
    elderly_speed_ms,
    future_aware_route,
    naive_route,
)
from wildfireguardian.routing.future_front import RoadNetwork
from wildfireguardian.routing.hazard import HazardSequence
from wildfireguardian.spread_v2.grid import CoarseGrid


# ---------------------------------------------------------------------------
# Elderly speed
# ---------------------------------------------------------------------------


def test_elderly_flat_speed_is_default():
    assert elderly_speed_ms(0.0) == pytest.approx(ELDERLY_FLAT_SPEED_MS, rel=1e-6)


def test_elderly_speed_slows_on_steep_slopes():
    assert elderly_speed_ms(0.3) < elderly_speed_ms(0.0)
    assert elderly_speed_ms(-0.3) < elderly_speed_ms(0.0)
    assert elderly_speed_ms(1.0) >= 0.15  # floored, never zero


# ---------------------------------------------------------------------------
# Hazard sequence sampling
# ---------------------------------------------------------------------------


def _line_grid(ncols=21, cell=500.0):
    return CoarseGrid(minx=0.0, miny=0.0, maxx=ncols * cell, maxy=cell,
                      cell_size_m=cell, nrows=1, ncols=ncols)


def _front_hazard(grid: CoarseGrid, times, front_x):
    """0/1 surfaces where hazard covers all cells with centre_x <= front_x(t)."""
    X, _ = grid.center_grids()
    surfaces = [np.where(X <= fx, 1.0, 0.0) for fx in front_x]
    return HazardSequence(grid=grid, times_min=np.array(times, float), surfaces=surfaces)


def test_hazard_temporal_interpolation_and_clamp():
    g = _line_grid()
    haz = _front_hazard(g, [0.0, 60.0], [500.0, 5000.0])
    x_mid = 2500.0  # a cell centre
    # At t=0 dry, at t=60 burning; halfway in time -> ~0.5.
    assert haz.prob_at(x_mid, 250.0, 0.0) == pytest.approx(0.0, abs=1e-6)
    assert haz.prob_at(x_mid, 250.0, 60.0) == pytest.approx(1.0, abs=1e-6)
    assert haz.prob_at(x_mid, 250.0, 30.0) == pytest.approx(0.5, abs=1e-6)
    # Before first / after last clamp.
    assert haz.prob_at(x_mid, 250.0, -100.0) == pytest.approx(0.0, abs=1e-6)
    assert haz.prob_at(x_mid, 250.0, 999.0) == pytest.approx(1.0, abs=1e-6)


def test_hazard_zero_outside_grid():
    g = _line_grid()
    haz = _front_hazard(g, [0.0], [99999.0])
    assert haz.prob_at(-9999.0, 250.0, 0.0) == 0.0


# ---------------------------------------------------------------------------
# Constructed danger-case network
# ---------------------------------------------------------------------------


def _chain_network(ncols=21, cell=500.0, speed=ELDERLY_FLAT_SPEED_MS):
    g = nx.Graph()
    for i in range(ncols):
        g.add_node(i, x=i * cell, y=250.0)
    edge_time = (cell / speed) / 60.0
    for i in range(ncols - 1):
        g.add_edge(i, i + 1, length_m=cell, time_min=edge_time)
    # Near-west shelter (toward the advancing fire) + far-east shelter (safe).
    return RoadNetwork(graph=g, shelters={2, 20})


def test_naive_walks_into_growing_western_hazard():
    g = _line_grid()
    # Fire front advances from the west; reaches the western shelter region
    # well before the slow evacuee can clear it.
    haz = _front_hazard(g, [0, 30, 60, 120, 240, 480],
                        [500, 1600, 2700, 5000, 9000, 12000])
    net = _chain_network()
    start = 6  # x = 3000 m
    nv = naive_route(net, start, haz, departure_min=0.0, p_cut=0.5)
    assert nv.reached
    assert nv.target == 2                 # chose the NEAR (west) shelter
    assert nv.enters_hazard               # ... and walked into the fire
    assert nv.max_hazard >= 0.5


def test_future_aware_detours_to_safe_shelter():
    g = _line_grid()
    haz = _front_hazard(g, [0, 30, 60, 120, 240, 480],
                        [500, 1600, 2700, 5000, 9000, 12000])
    net = _chain_network()
    start = 6
    fa = future_aware_route(net, start, haz, departure_min=0.0,
                            time_budget_min=600.0, p_cut=0.5, time_step_min=5.0)
    assert fa.reached
    assert fa.target == 20                # detoured to the FAR (east) shelter
    assert not fa.enters_hazard
    assert fa.max_hazard < 0.5            # never knowingly entered an above-cutoff cell


def test_future_aware_has_lower_exposure_than_naive():
    g = _line_grid()
    haz = _front_hazard(g, [0, 30, 60, 120, 240, 480],
                        [500, 1600, 2700, 5000, 9000, 12000])
    net = _chain_network()
    nv = naive_route(net, 6, haz, p_cut=0.5)
    fa = future_aware_route(net, 6, haz, time_budget_min=600.0, p_cut=0.5, time_step_min=5.0)
    assert fa.exposure < nv.exposure


def test_future_aware_is_reproducible():
    g = _line_grid()
    haz = _front_hazard(g, [0, 30, 60, 120, 240, 480],
                        [500, 1600, 2700, 5000, 9000, 12000])
    net = _chain_network()
    a = future_aware_route(net, 6, haz, time_budget_min=600.0, p_cut=0.5, time_step_min=5.0)
    b = future_aware_route(net, 6, haz, time_budget_min=600.0, p_cut=0.5, time_step_min=5.0)
    assert a.route == b.route and a.exposure == pytest.approx(b.exposure)


# ---------------------------------------------------------------------------
# No-safe-route and origin-in-fire (honest failure modes)
# ---------------------------------------------------------------------------


def test_no_safe_route_returns_cleanly():
    g = _line_grid()
    # Fire engulfs the whole line within 40 min — faster than the slow evacuee
    # can reach either shelter — so no safe route exists.
    haz = _front_hazard(g, [0, 40], [500, 99999])
    net = _chain_network()
    fa = future_aware_route(net, 6, haz, time_budget_min=600.0, p_cut=0.5, time_step_min=5.0)
    assert not fa.reached
    assert fa.route == []
    assert "no safe route" in fa.note


def test_origin_already_in_fire_returns_cleanly():
    g = _line_grid()
    haz = _front_hazard(g, [0.0], [99999.0])  # everything hazardous at t=0
    net = _chain_network()
    fa = future_aware_route(net, 6, haz, p_cut=0.5)
    assert not fa.reached
    assert fa.enters_hazard
    assert "origin" in fa.note


def test_naive_raises_without_shelters():
    g = _line_grid()
    haz = _front_hazard(g, [0.0], [0.0])
    net = RoadNetwork(graph=_chain_network().graph, shelters=set())
    with pytest.raises(ValueError):
        naive_route(net, 6, haz)
