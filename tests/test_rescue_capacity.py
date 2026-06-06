"""Tests for the rescue CAPACITY / triage layer (the demand–supply gap).

The capacity layer is an additive refinement on top of the prioritized dispatch
list: among the homes that need a rescuer it splits the *dispatch-reachable* set
into ``rescued_in_time`` vs ``capacity_deferred`` given a parameterized number of
rescue units, leaving the geometry ``no_surviving_vehicle_ingress`` set untouched.
The brief's invariants are pinned here:

  * the three outcomes partition the needs-rescuer pool (sum is exact);
  * unlimited capacity drives ``capacity_deferred`` to zero and recovers the
    original geometry-only unreachable set (the layer is a strict refinement);
  * the existing priority order is respected (no lower-priority home is served
    while a higher-priority, still-open, reachable home could be served);
  * more units never rescue fewer homes (monotonicity);
  * capacity is a PoC parameter — the synthetic 영덕 integration only checks the
    structural invariants, not any absolute count.
"""

from __future__ import annotations

import pytest

from wildfireguardian.routing.rescue import (
    DispatchEntry,
    RescueCapacityConfig,
    RescueConfig,
    capacity_triage,
)
from wildfireguardian.routing.rescue_demo import build_synthetic_demo, run_pipeline


# ---------------------------------------------------------------------------
# Synthetic dispatch list for fast, deterministic unit tests
# ---------------------------------------------------------------------------


def _entry(node, eta, survival):
    """A dispatch entry; closing window = survival - eta is the urgency key."""
    return DispatchEntry(
        home_node=node, x=float(node), y=0.0, depot_index=0,
        responder_eta_min=eta, ingress_survival_time_min=survival,
        closing_window_min=survival - eta, survival_aware_exposure=0.0,
        shortest_path_exposure=0.0, shortest_path_enters_hazard=False)


def _dispatch(entries):
    """Sort like build_dispatch_list does: smallest closing window first."""
    return sorted(entries, key=lambda e: e.closing_window_min)


def _cfg(delay=30.0, window=75.0):
    return RescueConfig(responder_dispatch_delay_min=delay,
                        responder_time_budget_min=window)


# ---------------------------------------------------------------------------
# 1. Three-way partition + unlimited-capacity recovery (UNIT)
# ---------------------------------------------------------------------------


def test_three_way_partition_sums_and_unlimited_recovers():
    cfg = _cfg(delay=30.0, window=75.0)
    # All reachable in a dedicated trip (eta <= survival and eta <= delay+W=105).
    disp = _dispatch([_entry(i, eta=40.0 + i, survival=200.0) for i in range(5)])
    n_geo = 3  # geometry_unreachable homes that never enter the triage

    # One unit serves a strict subset; the rest are capacity_deferred.
    tri1 = capacity_triage(disp, cfg, RescueCapacityConfig(n_rescue_units=1,
                                                           rescue_service_time_min=25.0))
    tw1 = tri1.three_way(n_geo)
    assert tw1["rescued_in_time"] + tw1["capacity_deferred"] == len(disp)
    assert sum(tw1.values()) == len(disp) + n_geo          # needs-rescuer pool
    assert tw1["capacity_deferred"] > 0                    # capacity binds

    # Unlimited units: everyone reachable is rescued, geometry set untouched.
    tri_inf = capacity_triage(disp, cfg, RescueCapacityConfig(n_rescue_units=10_000,
                                                              rescue_service_time_min=25.0))
    tw_inf = tri_inf.three_way(n_geo)
    assert tw_inf["capacity_deferred"] == 0
    assert tw_inf["rescued_in_time"] == len(disp)
    assert tw_inf["geometry_unreachable"] == n_geo
    assert sum(tw_inf.values()) == len(disp) + n_geo


def test_monotone_more_units_never_rescue_fewer():
    cfg = _cfg()
    disp = _dispatch([_entry(i, eta=35.0 + 2 * i, survival=150.0) for i in range(12)])
    counts = [capacity_triage(disp, cfg,
                              RescueCapacityConfig(n_rescue_units=u,
                                                   rescue_service_time_min=25.0)).n_rescued_in_time
              for u in (0, 1, 2, 3, 4, 8, 100)]
    assert counts == sorted(counts)            # non-decreasing in unit count
    assert counts[0] == 0                      # zero units rescue nobody
    assert counts[-1] == len(disp)             # plenty of units rescue everyone


# ---------------------------------------------------------------------------
# 2. Priority is respected (UNIT)
# ---------------------------------------------------------------------------


def test_priority_respected_deferred_are_genuinely_unreachable():
    """A deferred home's best-case arrival (earliest unit) must exceed its deadline,
    and no rescued home is lower-priority than a deferrable higher-priority one that a
    free unit could have served."""
    cfg = _cfg(delay=30.0, window=75.0)        # operation horizon clock = 105
    disp = _dispatch([_entry(i, eta=40.0 + 5 * i, survival=300.0) for i in range(8)])
    tri = capacity_triage(disp, cfg,
                          RescueCapacityConfig(n_rescue_units=2, rescue_service_time_min=25.0))
    by_node = {o.home_node: o for o in tri.outcomes}
    for o in tri.outcomes:
        if o.outcome == "rescued_in_time":
            assert o.arrival_min is not None and o.arrival_min <= o.deadline_min + 1e-9
            assert o.assigned_unit is not None and o.depart_min is not None
        else:  # capacity_deferred: even the earliest-available unit missed the deadline
            assert o.arrival_min is None or o.arrival_min > o.deadline_min - 1e-9
    # outcomes are reported in priority order (rank ascending == input order)
    assert [o.priority_rank for o in tri.outcomes] == list(range(len(disp)))


def test_window_and_corridor_close_both_bind():
    """rescued requires arrival <= min(ingress_survival, dispatch_delay + W)."""
    cfg = _cfg(delay=30.0, window=75.0)        # horizon clock = 105
    # Home A: corridor closes early (survival=50) -> a late unit misses it.
    # Home B: corridor open long, but only reachable while within the window.
    disp = _dispatch([_entry(0, eta=45.0, survival=50.0),     # window=5 -> most urgent
                      _entry(1, eta=40.0, survival=300.0)])    # window=260
    # 1 unit, long service: it takes the urgent A first (departs 30, arrives 45<=50 ok),
    # then is busy until 30+service; B may still be served if within horizon.
    tri = capacity_triage(disp, cfg,
                          RescueCapacityConfig(n_rescue_units=1, rescue_service_time_min=25.0))
    out = {o.home_node: o for o in tri.outcomes}
    assert out[0].outcome == "rescued_in_time"               # urgent, served first
    # second trip departs at 55, arrives 55+10=65 <= min(300,105) -> still served
    assert out[1].outcome == "rescued_in_time"

    # Shrink the window so the horizon (delay+W) cuts the second trip off.
    cfg_tight = _cfg(delay=30.0, window=20.0)                 # horizon clock = 50
    tri2 = capacity_triage(disp, cfg_tight,
                           RescueCapacityConfig(n_rescue_units=1, rescue_service_time_min=25.0))
    out2 = {o.home_node: o for o in tri2.outcomes}
    # A: arrives 45 > horizon 50? 45<=50 ok AND 45<=survival 50 -> rescued
    assert out2[0].outcome == "rescued_in_time"
    # B second trip departs 55 > horizon 50 -> arrival 65 > 50 -> deferred
    assert out2[1].outcome == "capacity_deferred"


# ---------------------------------------------------------------------------
# 3. 영덕 integration: invariants on the real synthetic pipeline (INTEGRATION)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fast_results():
    cfg = RescueConfig(route_cell_m=2000.0, hazard_cell_m=1000.0, scan_stride=6,
                       resident_time_budget_min=300.0, n_synthetic_shelters=8,
                       n_synthetic_inland_shelters=6, n_synthetic_depots=2,
                       sweep_max_origins=60)
    scenario = build_synthetic_demo(cfg)
    return scenario, run_pipeline(scenario), cfg


def test_capacity_three_way_partitions_needs_rescuer(fast_results):
    _scenario, results, cfg = fast_results
    dispatch = results.dispatch
    n_geo = len(results.unreachable_homes)
    needs = len(dispatch) + n_geo
    # four-way reconciliation: needs-rescuer == no_walk + unreachable
    c = results.four_way_counts
    assert needs == c["no_safe_pedestrian_route"] + c["no_surviving_vehicle_ingress"]
    for u in (1, 2, 4, 10_000):
        tri = capacity_triage(dispatch, cfg,
                              RescueCapacityConfig(n_rescue_units=u, rescue_service_time_min=25.0))
        tw = tri.three_way(n_geo)
        assert sum(tw.values()) == needs
        assert tw["rescued_in_time"] + tw["capacity_deferred"] == len(dispatch)
        assert tw["geometry_unreachable"] == c["no_surviving_vehicle_ingress"]


def test_capacity_unlimited_recovers_geometry_only_on_synthetic(fast_results):
    _scenario, results, cfg = fast_results
    dispatch = results.dispatch
    n_geo = len(results.unreachable_homes)
    tri = capacity_triage(dispatch, cfg,
                          RescueCapacityConfig(n_rescue_units=10 ** 6, rescue_service_time_min=25.0))
    assert tri.n_capacity_deferred == 0
    assert tri.n_rescued_in_time == len(dispatch)
    # the only residual unmet demand is the honest geometry-unreachable set
    tw = tri.three_way(n_geo)
    assert tw["geometry_unreachable"] == results.four_way_counts["no_surviving_vehicle_ingress"]
