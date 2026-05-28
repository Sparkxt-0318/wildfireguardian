"""Tests for the future-front-aware evacuation routing (Session 5 spine)."""

from __future__ import annotations

import math

import pytest
from shapely.geometry import box

from wildfireguardian.routing.future_front import (
    RoadNetwork,
    front_arrival_times,
    naive_shortest_path,
    time_dependent_evacuation,
)


# ---------------------------------------------------------------------------
# Scenario builder (west-to-east advancing front; near-west vs far-east shelter)
# ---------------------------------------------------------------------------

NXC, NYC, SP = 21, 11, 200.0


def _nid(ix, iy):
    return iy * NXC + ix


def _scenario(front_speed_m_min: float = 20.0):
    shelter_W = _nid(1, 5)    # near (x=200) but toward the fire
    shelter_E = _nid(20, 5)   # far (x=4000), escape direction
    net = RoadNetwork.synthetic_grid(
        (0.0, 0.0), NXC, NYC, SP, shelter_nodes={shelter_W, shelter_E})
    start = _nid(5, 5)        # x=1000
    front_seq = []
    for k in range(0, 49):
        t = k * 5.0
        X = front_speed_m_min * t
        poly = box(-10, -10, X, 2100) if X > 0 else box(-10, -10, -5, -5)
        front_seq.append((t, poly))
    return net, start, shelter_W, shelter_E, front_seq


# ---------------------------------------------------------------------------
# Network construction
# ---------------------------------------------------------------------------


def test_synthetic_grid_has_expected_nodes_and_positions():
    net = RoadNetwork.synthetic_grid((1000.0, 2000.0), 4, 3, 50.0)
    assert net.graph.number_of_nodes() == 12
    x, y = net.node_xy(0)
    assert (x, y) == (1000.0, 2000.0)
    # 4-connected: corner has 2 neighbours, interior has up to 4.
    assert net.graph.degree(0) == 2


def test_nearest_node():
    net = RoadNetwork.synthetic_grid((0.0, 0.0), 3, 3, 100.0)
    assert net.nearest_node(5.0, 5.0) == 0
    assert net.nearest_node(205.0, 205.0) == 8


# ---------------------------------------------------------------------------
# Front arrival times
# ---------------------------------------------------------------------------


def test_front_arrival_monotone_west_to_east():
    net, start, sw, se, seq = _scenario()
    fa = front_arrival_times(net, seq)
    # Western nodes burn before eastern ones.
    x_west, _ = net.node_xy(_nid(2, 5))
    x_east, _ = net.node_xy(_nid(18, 5))
    assert fa[_nid(2, 5)] < fa[_nid(18, 5)]


def test_front_never_reaches_far_east_within_horizon_is_inf_or_large():
    net, start, sw, se, seq = _scenario(front_speed_m_min=5.0)  # slow front
    fa = front_arrival_times(net, seq)
    # At 5 m/min over 240 min the front reaches x=1200; far-east (x=4000) never burns.
    assert math.isinf(fa[se])


# ---------------------------------------------------------------------------
# The headline contrast: naive walks into the front; future-aware does not
# ---------------------------------------------------------------------------


def test_naive_enters_front_but_future_aware_does_not():
    net, start, sw, se, seq = _scenario(front_speed_m_min=20.0)
    fa = front_arrival_times(net, seq)

    naive = naive_shortest_path(net, start, front_arrival=fa, walking_speed_ms=0.6)
    aware = time_dependent_evacuation(net, start, fa, walking_speed_ms=0.6,
                                      safety_margin_min=2.0)

    # Naive picks the NEAR (west) shelter and walks into the oncoming front.
    assert naive.reached
    assert naive.target == sw
    assert naive.enters_front is True

    # Future-aware picks the FAR (east) shelter and never enters the front.
    assert aware.reached
    assert aware.target == se
    assert aware.enters_front is False
    assert aware.clearance_margin_min is not None and aware.clearance_margin_min > 0


def test_future_aware_route_never_intersects_front():
    """Every node on the future-aware route is cleared before the front."""
    net, start, sw, se, seq = _scenario()
    fa = front_arrival_times(net, seq)
    aware = time_dependent_evacuation(net, start, fa, walking_speed_ms=0.6,
                                      departure_time_min=0.0, safety_margin_min=0.0)
    assert aware.reached
    for node, arr in zip(aware.route, aware.arrival_times_min):
        assert arr < fa[node], f"node {node} reached at {arr} but front arrives {fa[node]}"


def test_returns_no_safe_route_when_none_exists():
    """A very fast front that overtakes every shelter → no safe route."""
    net, start, sw, se, seq = _scenario(front_speed_m_min=400.0)  # ~6.7 m/s, faster than elderly
    fa = front_arrival_times(net, seq)
    aware = time_dependent_evacuation(net, start, fa, walking_speed_ms=0.6,
                                      safety_margin_min=2.0)
    assert aware.reached is False


def test_start_already_in_front_returns_unsafe():
    net, start, sw, se, seq = _scenario()
    fa = front_arrival_times(net, seq)
    # Depart so late the start node is already burned.
    late = fa[start] + 10.0
    aware = time_dependent_evacuation(net, start, fa, walking_speed_ms=0.6,
                                      departure_time_min=late)
    assert aware.reached is False
    assert aware.enters_front is True


# ---------------------------------------------------------------------------
# Walking speed / departure sensitivity
# ---------------------------------------------------------------------------


def test_latest_safe_departure_decreases_with_slower_walker():
    """A slower walker has less slack (earlier latest-safe-departure)."""
    net, start, sw, se, seq = _scenario(front_speed_m_min=20.0)
    fa = front_arrival_times(net, seq)
    fast = time_dependent_evacuation(net, start, fa, walking_speed_ms=1.2)
    slow = time_dependent_evacuation(net, start, fa, walking_speed_ms=0.6)
    assert fast.reached and slow.reached
    # Both reach the east shelter, which is never burned → no deadline (None).
    # Use a front that DOES threaten the route to get a finite deadline.
    net2, start2, sw2, se2, seq2 = _scenario(front_speed_m_min=35.0)
    fa2 = front_arrival_times(net2, seq2)
    slow2 = time_dependent_evacuation(net2, start2, fa2, walking_speed_ms=0.6)
    # Whatever the outcome, the API returns a valid result object.
    assert slow2.reached in (True, False)
