"""Tests for rescue-aware evacuation routing (ingress survival + the rescuer side).

These run without the (git-ignored) FIRMS bundle: small hazards/networks are
built synthetically, and the 영덕 integration test uses the labelled synthetic
fallback (:func:`build_synthetic_demo`), so the whole pipeline is exercised
end-to-end offline. The four required tests from the brief are:

  * ingress-survival equals the known cutting time slice (unit),
  * the rescuer router prefers a longer SURVIVING corridor over a shorter CUT
    one (unit),
  * road-segment → hazard-cell sampling is orientation-correct and drops no
    segments (regression),
  * the 영덕 four-way split sums to N and ``rescue_reachable ⊆ safe`` (integration).
"""

from __future__ import annotations

import math

import networkx as nx
import numpy as np
import pytest

from wildfireguardian.routing.future_front import RoadNetwork
from wildfireguardian.routing.hazard import HazardSequence
from wildfireguardian.routing.rescue import (
    FOUR_WAY_CLASSES,
    RescueConfig,
    classify_origin,
    corridor_survival_time,
    ingress_corridor,
    node_survival_time,
    rescuer_route,
    rescuer_shortest_ingress,
    sample_corridor_points,
)
from wildfireguardian.routing.rescue_demo import (
    build_synthetic_demo,
    run_pipeline,
    sensitivity_sweep,
)
from wildfireguardian.spread_v2.grid import CoarseGrid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _line_grid(ncols=21, nrows=1, cell=500.0):
    return CoarseGrid(minx=0.0, miny=0.0, maxx=ncols * cell, maxy=nrows * cell,
                      cell_size_m=cell, nrows=nrows, ncols=ncols)


def _line_drive_net(ncols=21, cell=500.0, speed_ms=10.0):
    """A west→east chain drive network with vehicle ``time_min`` edges."""
    g = nx.Graph()
    for i in range(ncols):
        g.add_node(i, x=i * cell, y=250.0)
    edge_time = (cell / speed_ms) / 60.0
    for i in range(ncols - 1):
        g.add_edge(i, i + 1, length_m=cell, time_min=edge_time)
    return RoadNetwork(graph=g, shelters=set())


# ---------------------------------------------------------------------------
# 1. Ingress-survival equals the known cutting time slice (UNIT)
# ---------------------------------------------------------------------------


def test_ingress_survival_equals_known_cut_slice():
    """One segment's cell crosses the vehicle cutoff at a known slice → survival == it."""
    g = _line_grid(ncols=21, cell=500.0)
    times = [0.0, 30.0, 60.0, 90.0, 120.0]
    cut_x = 12 * 500.0 + 250.0  # centre of cell col=12, on the corridor
    surfaces = []
    X, _ = g.center_grids()
    for t in times:
        s = np.zeros((1, 21), dtype=float)
        if t >= 60.0:                       # this cell ignites exactly at t = 60
            s[0, 11:14] = 1.0               # a 3-cell band around the segment
        surfaces.append(s)
    haz = HazardSequence(grid=g, times_min=np.array(times), surfaces=surfaces)
    drive = _line_drive_net(ncols=21, cell=500.0, speed_ms=10.0)
    cfg = RescueConfig(vehicle_cutoff=0.7, ingress_sample_spacing_m=100.0,
                       responder_safety_margin_min=0.0)
    res = ingress_corridor(drive, depot_node=0, target_node=20, hazard=haz, cfg=cfg)
    assert res.ingress_survival_time_min == pytest.approx(60.0)
    # And the helper agrees on a single point at that cell centre.
    assert node_survival_time(haz, cut_x, 250.0, 0.7) == pytest.approx(60.0)


def test_corridor_never_cut_survives_forever():
    g = _line_grid(ncols=11, cell=500.0)
    surfaces = [np.zeros((1, 11)), np.zeros((1, 11))]
    haz = HazardSequence(grid=g, times_min=np.array([0.0, 60.0]), surfaces=surfaces)
    drive = _line_drive_net(ncols=11, cell=500.0)
    cfg = RescueConfig()
    res = ingress_corridor(drive, 0, 10, haz, cfg)
    assert math.isinf(res.ingress_survival_time_min)
    assert res.reachable                      # never cut ⇒ reachable within window


# ---------------------------------------------------------------------------
# 2. Rescuer router prefers a longer SURVIVING corridor over a shorter CUT one
# ---------------------------------------------------------------------------


def _diamond_drive_net(cell=1000.0, speed_ms=1.667):
    """depot(D)→home(H) with a short branch via S and a longer branch via L1..L3."""
    g = nx.Graph()
    # Short branch: D(0) - S(1) - H(2), straight east.
    g.add_node(0, x=0.0, y=0.0)            # D
    g.add_node(1, x=cell, y=0.0)           # S  (will be cut)
    g.add_node(2, x=2 * cell, y=0.0)       # H
    # Long branch: D - L1 - L2 - L3 - H, detouring north then back.
    g.add_node(10, x=0.0, y=cell)          # L1
    g.add_node(11, x=cell, y=cell)         # L2
    g.add_node(12, x=2 * cell, y=cell)     # L3

    def t(d):
        return (d / speed_ms) / 60.0

    for u, v, d in [(0, 1, cell), (1, 2, cell),
                    (0, 10, cell), (10, 11, cell), (11, 12, cell), (12, 2, cell)]:
        g.add_edge(u, v, length_m=d, time_min=t(d))
    return RoadNetwork(graph=g, shelters=set())


def test_rescuer_prefers_longer_surviving_corridor():
    """The short branch's mid-cell gets cut during the window; rescuer takes the long one."""
    cell = 1000.0
    # Hazard grid covering the diamond (x in [-cell, 3cell], y in [-cell, 2cell]).
    grid = CoarseGrid(minx=-cell, miny=-cell, maxx=3 * cell, maxy=2 * cell,
                      cell_size_m=cell, nrows=3, ncols=4)
    X, Y = grid.center_grids()
    times = [0.0, 5.0, 10.0, 15.0, 20.0, 30.0]
    surfaces = []
    for tt in times:
        s = np.zeros_like(X)
        if tt >= 5.0:                       # S's cell (x≈cell, y≈0) ignites from t=5
            s[(np.abs(X - cell) < cell * 0.6) & (np.abs(Y - 0.0) < cell * 0.6)] = 1.0
        surfaces.append(s)
    haz = HazardSequence(grid=grid, times_min=np.array(times), surfaces=surfaces)
    drive = _diamond_drive_net(cell=cell, speed_ms=1.667)   # ~6 km/h → 1 km ≈ 10 min
    # delay 0 → responder departs at t0 (S still clear) and meets the cut en route.
    cfg = RescueConfig(vehicle_cutoff=0.7, time_step_min=5.0, responder_dispatch_delay_min=0.0,
                       responder_time_budget_min=120.0, ingress_sample_spacing_m=200.0)

    sa = rescuer_route(drive, depot_node=0, home_node=2, hazard=haz, cfg=cfg)
    assert sa.reached
    assert not sa.enters_hazard
    assert 1 not in sa.route                # avoided the cut short branch (node S=1)
    assert {10, 11, 12}.issubset(set(sa.route))   # took the surviving long branch

    # The fire-blind shortest-distance ingress would have used the short, cut branch.
    sp = rescuer_shortest_ingress(drive, 0, 2, haz, cfg)
    assert sp.enters_hazard
    assert 1 in sp.route
    # Survival-aware avoids hazard the shortest path walks into.
    assert sa.exposure <= sp.exposure


# ---------------------------------------------------------------------------
# 3. Road-segment → hazard-cell sampling is orientation-correct (REGRESSION)
# ---------------------------------------------------------------------------


def _ne_corner_hazard():
    """Hazard = 1.0 ONLY in the north-east corner cell; 0 elsewhere (orientation probe)."""
    grid = CoarseGrid(minx=1_000_000.0, miny=1_800_000.0,
                      maxx=1_000_000.0 + 5 * 500.0, maxy=1_800_000.0 + 4 * 500.0,
                      cell_size_m=500.0, nrows=4, ncols=5)
    surf = np.zeros((4, 5), dtype=float)
    surf[0, 4] = 1.0                        # row 0 = NORTH (max y), col 4 = EAST (max x)
    return grid, HazardSequence(grid=grid, times_min=np.array([0.0]), surfaces=[surf])


def test_sampling_orientation_matches_raster_convention():
    """NE corner reads hot, SW corner reads cold — no N/S or E/W mirror."""
    grid, haz = _ne_corner_hazard()
    ne_x, ne_y = grid.center_xy(0, grid.ncols - 1)      # north-east cell centre
    sw_x, sw_y = grid.center_xy(grid.nrows - 1, 0)      # south-west cell centre
    # Cell mapping is orientation-correct (mirror of the existing raster test).
    assert grid.cell_of_xy(ne_x, ne_y) == (0, grid.ncols - 1)
    assert grid.cell_of_xy(sw_x, sw_y) == (grid.nrows - 1, 0)
    # Hazard read through the sampler agrees: hot in the NE, cold in the SW.
    assert haz.prob_at(ne_x, ne_y, 0.0) == pytest.approx(1.0)
    assert haz.prob_at(sw_x, sw_y, 0.0) == pytest.approx(0.0)
    # A corridor crossing the NE corner is cut; one across the SW is not.
    assert math.isfinite(node_survival_time(haz, ne_x, ne_y, 0.5))
    assert math.isinf(node_survival_time(haz, sw_x, sw_y, 0.5))


def test_sample_corridor_drops_no_segments():
    """Every segment of a path contributes samples; none silently dropped."""
    g = nx.Graph()
    g.add_node(0, x=0.0, y=0.0)
    g.add_node(1, x=1000.0, y=0.0)
    g.add_node(2, x=1000.0, y=900.0)
    net = RoadNetwork(graph=g, shelters=set())
    xs, ys, seg = sample_corridor_points(net, [0, 1, 2], spacing_m=200.0)
    assert set(seg.tolist()) == {0, 1}                 # both segments represented
    assert (seg == 0).sum() >= 2 and (seg == 1).sum() >= 2
    assert len(xs) == len(ys) == len(seg)
    # Endpoints are present (first sample == node 0, a sample hits the corner node 1).
    assert (xs[0], ys[0]) == (0.0, 0.0)
    # Single-node corridor degenerates to one sample (no crash, not dropped).
    xs1, ys1, seg1 = sample_corridor_points(net, [1], spacing_m=200.0)
    assert len(xs1) == 1 and seg1.tolist() == [0]


def test_corridor_survival_time_iterates_discrete_slices():
    """corridor_survival_time returns a value from times_min, not an interpolated time."""
    grid, haz = _ne_corner_hazard()
    haz2 = HazardSequence(grid=grid, times_min=np.array([0.0, 40.0, 80.0]),
                          surfaces=[np.zeros((4, 5)), np.zeros((4, 5)),
                                    _ne_corner_hazard()[1].surfaces[0]])
    ne_x, ne_y = grid.center_xy(0, grid.ncols - 1)
    xs = np.array([ne_x])
    ys = np.array([ne_y])
    assert corridor_survival_time(haz2, xs, ys, 0.5) == pytest.approx(80.0)
    assert corridor_survival_time(haz2, xs, ys, 0.5) in set(haz2.times_min.tolist())


# ---------------------------------------------------------------------------
# 4. 영덕 integration: four-way split sums to N; rescue_reachable ⊆ safe (INTEGRATION)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fast_scenario():
    """A coarse, fast synthetic 영덕 scenario for the integration assertions."""
    cfg = RescueConfig(route_cell_m=2000.0, hazard_cell_m=1000.0, scan_stride=6,
                       resident_time_budget_min=300.0, n_synthetic_shelters=8,
                       n_synthetic_inland_shelters=6, n_synthetic_depots=2,
                       sweep_max_origins=60)
    scenario = build_synthetic_demo(cfg)
    return scenario, run_pipeline(scenario)


def test_pipeline_runs_end_to_end_on_synthetic_fallback(fast_scenario):
    scenario, results = fast_scenario
    assert results.n_origins > 0
    assert scenario.shelters_source == "synthetic"
    assert scenario.depots_source == "synthetic"
    assert scenario.hazard_source == "synthetic"
    # Provenance tags the synthetic sources for the outputs.
    assert results.provenance["sources"]["shelters"] == "synthetic"


def test_four_way_split_sums_to_n(fast_scenario):
    scenario, results = fast_scenario
    assert set(results.four_way_counts) == set(FOUR_WAY_CLASSES)
    assert sum(results.four_way_counts.values()) == results.n_origins
    assert results.n_origins == len(scenario.origins)


def test_rescue_reachable_is_subset_of_safe(fast_scenario):
    _scenario, results = fast_scenario
    for a in results.dest_assessments:
        if a.rescue_reachable:
            assert a.safe, f"{a.name} rescue_reachable but not safe"


def test_unreachable_set_is_reported_not_imputed(fast_scenario):
    _scenario, results = fast_scenario
    # The unreachable set is an explicit list (possibly empty), never fabricated.
    assert isinstance(results.unreachable_homes, list)
    n_dispatch = results.responder_exposure["n_dispatch"]
    n_unreach = results.responder_exposure["n_unreachable"]
    assert n_unreach == len(results.unreachable_homes)
    assert n_dispatch >= 0 and n_unreach >= 0


def test_four_way_reconciles_with_dispatch_and_unreachable(fast_scenario):
    """The four-way no-walk / no-ingress counts ARE the dispatch / unreachable split."""
    _scenario, results = fast_scenario
    c = results.four_way_counts
    assert c["no_safe_pedestrian_route"] == len(results.dispatch)
    assert c["no_surviving_vehicle_ingress"] == len(results.unreachable_homes)
    # Everyone needing rescue is either immobile or had their walk route cut.
    re = results.responder_exposure
    assert re["n_need_rescue"] == re["n_need_rescue_immobile"] + re["n_need_rescue_walk_cut"]
    assert re["n_need_rescue"] == len(results.dispatch) + len(results.unreachable_homes)


def test_classify_origin_decision_tree():
    """The reference four-way decision function is exclusive and exhaustive."""
    from wildfireguardian.routing.evacuation import RouteResult

    def rr(reached, enters):
        return RouteResult(kind="x", reached=reached, route=[1], target=1,
                           departure_min=0.0, total_distance_m=0.0, total_time_min=0.0,
                           enters_hazard=enters)
    safe = rr(True, False)
    unsafe = rr(True, True)
    # naive already safe -> already_safe (regardless of the rest)
    pol = {"naive": safe, "future_aware_any": safe, "future_aware_rescue": safe}
    assert classify_origin(pol, home_reachable_by_rescuer=False) == "already_safe"
    # naive unsafe, fa_rescue safe -> saved
    pol = {"naive": unsafe, "future_aware_any": safe, "future_aware_rescue": safe}
    assert classify_origin(pol, False) == "saved_by_rescue_reachable_refuge"
    # neither walk works, rescuer can reach -> no_safe_pedestrian_route
    pol = {"naive": unsafe, "future_aware_any": unsafe, "future_aware_rescue": unsafe}
    assert classify_origin(pol, True) == "no_safe_pedestrian_route"
    # neither walk works, rescuer cannot reach -> no_surviving_vehicle_ingress
    assert classify_origin(pol, False) == "no_surviving_vehicle_ingress"


def test_sensitivity_sweep_each_point_sums_to_n(fast_scenario):
    scenario, _results = fast_scenario
    sweeps = sensitivity_sweep(scenario)
    for group, points in sweeps.items():
        if "counts" in points:                 # the "baseline" entry
            assert sum(points["counts"].values()) == points["n_origins"]
            continue
        for label, rec in points.items():
            assert sum(rec["counts"].values()) == rec["n_origins"], \
                f"{group}={label} did not sum to its N"


def test_sweep_more_risk_tolerant_vehicle_cutoff_helps_or_neutral(fast_scenario):
    """Raising the vehicle cutoff should not shrink the rescuable population."""
    scenario, _results = fast_scenario
    sweeps = sensitivity_sweep(scenario)
    vc = sweeps["vehicle_cutoff"]
    low = vc["0.40"]["counts"]["no_surviving_vehicle_ingress"]
    high = vc["0.80"]["counts"]["no_surviving_vehicle_ingress"]
    # A more risk-tolerant vehicle cutoff cuts fewer corridors ⇒ fewer unreachable.
    assert high <= low
