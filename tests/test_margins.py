"""Tests for round-trip margins, trigger lines and advisories (Session 8 Phase 1).

The pinned behaviour from the brief: a corridor that is survivable at ingress
but closed at egress must produce a NEGATIVE margin — the same corridor at
``t_in`` and ``t_out`` is a different edge of the time-expanded graph (the
의성 responder-isolation failure mode described in the field consultation).
"""

from __future__ import annotations

import math
from dataclasses import replace

import networkx as nx
import numpy as np
import pytest

from wildfireguardian.routing.future_front import RoadNetwork
from wildfireguardian.routing.hazard import HazardSequence
from wildfireguardian.routing.margins import (
    RECOMMENDATIONS,
    advisory,
    margin_band,
    recommend,
    round_trip_margin,
    withdrawal_trigger_line,
)
from wildfireguardian.routing.rescue import RescueConfig
from wildfireguardian.spread_v2.grid import CoarseGrid


def _line_grid(ncols=21, nrows=1, cell=500.0):
    return CoarseGrid(minx=0.0, miny=0.0, maxx=ncols * cell, maxy=nrows * cell,
                      cell_size_m=cell, nrows=nrows, ncols=ncols)


def _line_drive_net(ncols=21, cell=500.0, speed_ms=10.0):
    g = nx.Graph()
    for i in range(ncols):
        g.add_node(i, x=i * cell, y=250.0)
    edge_time = (cell / speed_ms) / 60.0
    for i in range(ncols - 1):
        g.add_edge(i, i + 1, length_m=cell, time_min=edge_time)
    return RoadNetwork(graph=g, shelters=set())


def _hazard_cutting_at(grid, t_cut: float, cols: slice,
                       times=(0.0, 30.0, 60.0, 90.0, 120.0, 150.0)):
    """Hazard where ``cols`` of the single row cross 1.0 exactly at ``t_cut``."""
    surfaces = []
    for t in times:
        s = np.zeros((grid.nrows, grid.ncols))
        if t >= t_cut:
            s[0, cols] = 1.0
        surfaces.append(s)
    return HazardSequence(grid=grid, times_min=np.array(times, float),
                         surfaces=surfaces)


# ---------------------------------------------------------------------------
# 1. PINNED: survivable at ingress, closed at egress -> negative margin
# ---------------------------------------------------------------------------


def test_ingress_ok_egress_closed_gives_negative_margin():
    """Corridor open when the responder drives in, cut before the round trip
    completes: the one-way check passes, the round-trip margin must not."""
    g = _line_grid(ncols=21, cell=500.0)
    # 21 cells x 500 m; vehicle 10 m/s -> one-way travel = 10000 m / 10 m/s
    # = 1000 s ~= 16.67 min. Dispatch delay 30 -> ETA_in ~= 46.67 min.
    haz = _hazard_cutting_at(g, t_cut=60.0, cols=slice(9, 12))
    drive = _line_drive_net(ncols=21, cell=500.0, speed_ms=10.0)
    cfg = RescueConfig(responder_dispatch_delay_min=30.0,
                       responder_safety_margin_min=0.0,
                       vehicle_cutoff=0.7, t_load_min=10.0,
                       egress_policy="same_route",
                       ingress_sample_spacing_m=100.0)
    m = round_trip_margin(drive, 0, 20, haz, cfg)
    # One-way: survivable (S = 60 >= ETA_in ~= 46.67).
    assert m.ingress_survival_time_min == pytest.approx(60.0)
    assert m.eta_in_min < 60.0
    # Round trip: 46.67 + 10 (load) + 16.67 (egress) ~= 73.3 > 60 -> negative.
    assert m.margin_minutes < 0.0
    assert m.margin_minutes == pytest.approx(
        60.0 - (m.eta_in_min + 10.0 + m.eta_out_min))


def test_never_cut_corridor_gives_infinite_margin():
    g = _line_grid(ncols=11)
    haz = _hazard_cutting_at(g, t_cut=math.inf, cols=slice(0, 0))
    drive = _line_drive_net(ncols=11)
    cfg = RescueConfig(egress_policy="same_route")
    m = round_trip_margin(drive, 0, 10, haz, cfg)
    assert math.isinf(m.margin_minutes) and m.margin_minutes > 0
    assert m.corridor_never_cut
    assert m.as_dict()["margin_minutes"] is None  # inf serialises to null


def test_positive_margin_when_round_trip_completes_before_cut():
    g = _line_grid(ncols=11, cell=500.0)
    # one-way = 5000 m / 10 m/s ~= 8.33 min; delay 10 -> round trip done ~31.7.
    haz = _hazard_cutting_at(g, t_cut=120.0, cols=slice(4, 6))
    drive = _line_drive_net(ncols=11, cell=500.0, speed_ms=10.0)
    cfg = RescueConfig(responder_dispatch_delay_min=10.0, t_load_min=5.0,
                       egress_policy="same_route")
    m = round_trip_margin(drive, 0, 10, haz, cfg)
    assert m.margin_minutes > 0
    assert math.isfinite(m.margin_minutes)


# ---------------------------------------------------------------------------
# 2. Egress policy: same_route vs free
# ---------------------------------------------------------------------------


def _diamond_net(cell=1000.0, speed_ms=16.667):
    """depot(0) -> home(2): short south chain via 1; long north detour 10-11-12."""
    g = nx.Graph()
    g.add_node(0, x=0.0, y=250.0)
    g.add_node(1, x=cell, y=250.0)
    g.add_node(2, x=2 * cell, y=250.0)
    g.add_node(10, x=0.0, y=250.0 + cell)
    g.add_node(11, x=cell, y=250.0 + cell)
    g.add_node(12, x=2 * cell, y=250.0 + cell)
    t = (cell / speed_ms) / 60.0
    for u, v in ((0, 1), (1, 2)):
        g.add_edge(u, v, length_m=cell, time_min=t)
    for u, v in ((0, 10), (10, 11), (11, 12), (12, 2)):
        g.add_edge(u, v, length_m=cell, time_min=t)
    return RoadNetwork(graph=g, shelters=set())


def test_free_egress_survives_where_same_route_is_negative():
    """The short ingress corridor closes after ingress; a northern detour stays
    open. same_route -> negative margin; free -> the router detours and the
    margin is computed on the surviving egress corridor."""
    cell = 1000.0
    grid = CoarseGrid(minx=-500.0, miny=0.0, maxx=2 * cell + 500.0,
                      maxy=2 * cell, cell_size_m=500.0, nrows=4, ncols=6)
    times = np.array([0.0, 30.0, 60.0, 90.0, 120.0])
    surfaces = []
    for t in times:
        s = np.zeros((4, 6))
        if t >= 30.0:
            s[3, 2:4] = 1.0     # bottom row (y ~ 250, the short chain) closes at 30
        surfaces.append(s)
    haz = HazardSequence(grid=grid, times_min=times, surfaces=surfaces)
    net = _diamond_net(cell=cell, speed_ms=16.667)   # 1 km/min
    # ETA_in = 20 + 2 = 22 < 30 (ingress OK); completion = 22 + 15 + 2 = 39 > 30.
    cfg = RescueConfig(responder_dispatch_delay_min=20.0, t_load_min=15.0,
                       responder_safety_margin_min=0.0, vehicle_cutoff=0.7,
                       responder_time_budget_min=200.0,
                       ingress_sample_spacing_m=200.0, time_step_min=5.0)

    same = round_trip_margin(net, 0, 2, haz, replace(cfg, egress_policy="same_route"))
    free = round_trip_margin(net, 0, 2, haz, replace(cfg, egress_policy="free"))
    assert same.margin_minutes < 0.0
    # The free egress leg detours north (nodes 12-11-10), which never ignites.
    assert math.isinf(free.egress_survival_time_min) and free.egress_survival_time_min > 0
    assert free.margin_minutes > same.margin_minutes


# ---------------------------------------------------------------------------
# 3. Trigger line
# ---------------------------------------------------------------------------


def test_trigger_line_is_a_hazard_isochrone_at_the_commitment_time():
    """The emitted cells' arrival time equals the latest forecast slice <= the
    latest safe commitment time, and the slice index points at it."""
    g = _line_grid(ncols=21, cell=500.0)
    times = np.array([0.0, 30.0, 60.0, 90.0, 120.0, 150.0])
    surfaces = []
    for t in times:
        s = np.zeros((1, 21))
        # fire marches east one 3-cell band per slice from col 0
        k = int(t // 30)
        s[0, : min(3 * k, 21)] = 1.0
        surfaces.append(s)
    haz = HazardSequence(grid=g, times_min=times, surfaces=surfaces)
    drive = _line_drive_net(ncols=21, cell=500.0, speed_ms=10.0)
    cfg = RescueConfig(responder_dispatch_delay_min=10.0, t_load_min=10.0,
                       responder_safety_margin_min=0.0, vehicle_cutoff=0.7,
                       egress_policy="same_route", ingress_sample_spacing_m=100.0)
    m = round_trip_margin(drive, 20, 10, haz, cfg)  # depot east, home mid-line
    assert math.isfinite(m.margin_minutes)
    tl = withdrawal_trigger_line(haz, cfg, m)
    assert tl.hazard_slice_index is not None
    slice_t = float(times[tl.hazard_slice_index])
    assert tl.arrival_time_min == pytest.approx(slice_t)
    assert slice_t <= m.margin_minutes           # snapped DOWN (conservative)
    # every emitted cell first crosses the cutoff exactly at that slice
    prev_t = float(times[tl.hazard_slice_index - 1]) if tl.hazard_slice_index else None
    for (r, c) in tl.cells_rc:
        assert surfaces[tl.hazard_slice_index][r, c] >= cfg.vehicle_cutoff
        if prev_t is not None:
            assert surfaces[tl.hazard_slice_index - 1][r, c] < cfg.vehicle_cutoff
    assert "planning-scale" in tl.note


def test_trigger_line_absent_when_corridor_never_cut():
    g = _line_grid(ncols=11)
    haz = _hazard_cutting_at(g, t_cut=math.inf, cols=slice(0, 0))
    drive = _line_drive_net(ncols=11)
    cfg = RescueConfig()
    m = round_trip_margin(drive, 0, 10, haz, cfg)
    tl = withdrawal_trigger_line(haz, cfg, m)
    assert tl.cells_rc == [] and tl.hazard_slice_index is None


# ---------------------------------------------------------------------------
# 4. Advisory
# ---------------------------------------------------------------------------


def test_recommend_thresholds():
    cfg = RescueConfig(responder_safety_margin_min=12.0)
    assert recommend(30.0, cfg) == RECOMMENDATIONS[0]     # 진입 권장
    assert recommend(5.0, cfg) == RECOMMENDATIONS[1]      # 진입 보류 권장
    assert recommend(-3.0, cfg) == RECOMMENDATIONS[2]     # 철수 권장
    assert recommend(math.inf, cfg) == RECOMMENDATIONS[0]
    assert recommend(-math.inf, cfg) == RECOMMENDATIONS[2]
    # the categorical 불가 never appears
    assert all("불가" not in r for r in RECOMMENDATIONS)


def test_margin_band_is_real_spread_or_null():
    g = _line_grid(ncols=21, cell=500.0)
    haz = _hazard_cutting_at(g, t_cut=60.0, cols=slice(9, 12))
    drive = _line_drive_net(ncols=21, cell=500.0, speed_ms=10.0)
    cfg = RescueConfig(responder_dispatch_delay_min=30.0, t_load_min=10.0,
                       egress_policy="same_route", ingress_sample_spacing_m=100.0)
    band = margin_band(drive, 0, 20, haz, cfg)
    assert band is not None
    assert band["low_min"] <= band["high_min"]
    assert band["n_finite"] >= 1
    # zero-hazard scenario: no cutoff is ever crossed -> no defensible band
    haz0 = _hazard_cutting_at(g, t_cut=math.inf, cols=slice(0, 0))
    assert margin_band(drive, 0, 20, haz0, cfg) is None


def test_advisory_record_shape_and_basis_auditable():
    g = _line_grid(ncols=21, cell=500.0)
    haz = _hazard_cutting_at(g, t_cut=60.0, cols=slice(9, 12))
    drive = _line_drive_net(ncols=21, cell=500.0, speed_ms=10.0)
    cfg = RescueConfig(responder_dispatch_delay_min=30.0, t_load_min=10.0,
                       responder_safety_margin_min=0.0,
                       egress_policy="same_route", ingress_sample_spacing_m=100.0)
    a = advisory(drive, 0, 20, haz, cfg)
    assert set(a) == {"home_node", "margin_minutes", "margin_band",
                      "recommendation", "trigger_line", "basis", "note"}
    assert a["recommendation"] in RECOMMENDATIONS
    b = a["basis"]
    # the audit fields the recommendation was computed from
    for k in ("ingress_survival_time_min", "eta_in_min", "t_load_min",
              "eta_out_min", "egress_policy", "vehicle_cutoff", "formula"):
        assert k in b
    assert b["t_load_source"] == "assumed"   # never presented as measured


def test_advisory_deterministic():
    g = _line_grid(ncols=21, cell=500.0)
    haz = _hazard_cutting_at(g, t_cut=60.0, cols=slice(9, 12))
    drive = _line_drive_net(ncols=21, cell=500.0, speed_ms=10.0)
    cfg = RescueConfig(responder_dispatch_delay_min=30.0, t_load_min=10.0,
                       egress_policy="same_route", ingress_sample_spacing_m=100.0)
    assert advisory(drive, 0, 20, haz, cfg) == advisory(drive, 0, 20, haz, cfg)
