"""SYNTHETIC end-to-end example on ``hazard_contract.synthetic``: files on disk, reload, oracle.

A 9 km x 9 km SYNTHETIC fire (24 x 24 cells of 375 m, 4 members, 3 h horizon, cells burn 4 h)
ignites 1 h before issue at the centre and spreads north-east. Roads: a 12 x 12 lattice through
odd cell centres, 750 m edges of 68 s (40 km/h, rounded up like the router graphs); only site
nodes are waitable. Plan (all SYNTHETIC):

* V1 evacuates F_W in the unburned west to shelter S_SW -> checked;
* V2 picks up 4 at F_N (north-east, burns after ~1 h) and drives straight south through the
  burning centre to S_S -> model_no_route (flame contact);
* V3 picks up 4 + 2 wheelchair users at F_N right after V2 and detours east and south -> checked;
* V4 waits at its depot past the horizon, then serves F_S -> unresolved (beyond the horizon).
"""
import numpy as np
import pytest

import hazard_contract as hc
from hazard_contract.geometry import polyline_cells
from evacplan import (
    Budgets, Edge, HazardRef, Instance, Node, PlanResult, RelaxedContactCheck, RoadGraph, State, check_plan,
    load_instance, load_scenario_set, load_solution, save_instance, save_solution, validate_solution,
)
from evacplan_testkit import board, drive, facility, itinerary, shelter, solution, unload, vehicle, wait

CELL, N, TRAVEL = 375.0, 24, 68.0
ODD = range(1, N, 2)
SITES = {(11, 1), (5, 15), (19, 13), (23, 1), (23, 13), (13, 1), (1, 23), (23, 23)}


def nid(r, c):
    return f"n{r}_{c}"


def lattice(*corners):
    """Edge ids along straight lattice runs between consecutive corner cells."""
    cells = [corners[0]]
    for (r, c), (r2, c2) in zip(corners, corners[1:]):
        while (r, c) != (r2, c2):
            if r != r2:
                r += 2 if r2 > r else -2
            else:
                c += 2 if c2 > c else -2
            cells.append((r, c))
    return [f"{nid(*a)}>{nid(*b)}" for a, b in zip(cells, cells[1:])]


def scenario():
    return hc.synthetic(K=4, height=N, width=N, cell_m=CELL, seed=11, t_ignition_s=-3600.0, ros_m_s=0.3,
                        spread_dir_deg=45.0, head_ratio=3.0, ros_cv=0.1, dir_sd_deg=10.0, noise_sd=0.1,
                        horizon_s=3 * 3600.0, burn_duration_s=4 * 3600.0)


def build(ss):
    nodes = [Node(id=nid(r, c), x=(c + 0.5) * CELL, y=(N - r - 0.5) * CELL, waitable=(r, c) in SITES)
             for r in ODD for c in ODD]
    edges = [Edge(id=f"{nid(r, c)}>{nid(r + dr, c + dc)}", u=nid(r, c), v=nid(r + dr, c + dc), travel_time_s=TRAVEL)
             for r in ODD for c in ODD for dr, dc in ((2, 0), (-2, 0), (0, 2), (0, -2))
             if (r + dr) in ODD and (c + dc) in ODD]
    graph = RoadGraph(crs_epsg=ss.meta.crs_epsg, nodes=nodes, edges=edges,
                      provenance={"generator": "SYNTHETIC lattice for the end-to-end test"})
    board_s = (30.0, 90.0, 180.0)
    inst = Instance(
        name="SYNTHETIC e2e lattice", synthetic=True, graph=graph,
        facilities=[facility("F_W", nid(11, 1), amb=6, wc=2, bed=1, board=board_s),
                    facility("F_N", nid(5, 15), amb=10, wc=2, board=board_s),
                    facility("F_S", nid(19, 13), amb=4, bed=1, board=board_s)],
        vehicles=[vehicle("V1", nid(13, 1), seats=8, wc=2, stretchers=1),
                  vehicle("V2", nid(1, 23), seats=8, wc=2, stretchers=0),
                  vehicle("V3", nid(1, 23), seats=8, wc=2, stretchers=0),
                  vehicle("V4", nid(23, 23), seats=8, wc=1, stretchers=1)],
        shelters=[shelter("S_SW", nid(23, 1), cap=(40, 10, 5), unload=(20.0, 60.0, 120.0)),
                  shelter("S_S", nid(23, 13), cap=(40, 10, 5), unload=(20.0, 60.0, 120.0))],
        hazard=HazardRef(scenario_set="hazard", t0_offset_s=0.0, budgets=Budgets(peak_kw_m2=10.0, dose_kj_m2=100.0)),
        provenance={"seed": 11, "note": "SYNTHETIC test instance"},
    )
    to_fw, fw_out = lattice((13, 1), (11, 1)), lattice((11, 1), (23, 1))
    to_fn, through, around = lattice((1, 23), (1, 15), (5, 15)), lattice((5, 15), (5, 13), (23, 13)), \
        lattice((5, 15), (5, 23), (23, 23), (23, 13))
    to_fs, fs_out = lattice((23, 23), (19, 23), (19, 13)), lattice((19, 13), (23, 13))
    t_fn = TRAVEL * len(to_fn)                                  # both V2 and V3 reach F_N at 408 s
    late = 11_000.0                                            # past the 10 800 s horizon
    plan = solution(
        itinerary("V1", drive(to_fw, 0.0), board("F_W", amb=6, wc=2, bed=1),
                  drive(fw_out, TRAVEL + 6 * 30 + 2 * 90 + 180), unload("S_SW", amb=6, wc=2, bed=1)),
        itinerary("V2", drive(to_fn, 0.0), board("F_N", amb=4), drive(through, t_fn + 4 * 30), unload("S_S", amb=4)),
        itinerary("V3", drive(to_fn, 0.0), wait(nid(5, 15), 120.0), board("F_N", amb=4, wc=2),
                  drive(around, t_fn + 120 + 4 * 30 + 2 * 90), unload("S_S", amb=4, wc=2)),
        itinerary("V4", wait(nid(23, 23), late), drive(to_fs, late), board("F_S", amb=4, bed=1),
                  drive(fs_out, late + TRAVEL * len(to_fs) + 4 * 30 + 180), unload("S_S", amb=4, bed=1)),
        name=inst.name, method="hand (SYNTHETIC e2e)")
    return inst, plan


def chord_cells(ss, inst, edge_id):
    nodes = {n.id: n for n in inst.graph.nodes}
    e = next(e for e in inst.graph.edges if e.id == edge_id)
    r, c, _ = polyline_cells(ss.grid, np.array([[nodes[e.u].x, nodes[e.u].y], [nodes[e.v].x, nodes[e.v].y]]))
    return r, c


@pytest.fixture(scope="module")
def case(tmp_path_factory):
    d = tmp_path_factory.mktemp("synthetic_e2e")
    ss = scenario()
    ss.write(d / "hazard")
    inst, plan = build(ss)
    save_instance(inst, d / "instance.json")
    save_solution(plan, d / "solution.json")
    inst2 = load_instance(d / "instance.json")
    ss2 = load_scenario_set(inst2)
    plan2 = load_solution(d / "solution.json")
    assert inst2 == inst and plan2 == plan
    np.testing.assert_array_equal(ss2.ignite_s, ss.ignite_s)
    return d, inst2, ss2, plan2, check_plan(inst2, ss2, plan2)


def test_premises_of_the_synthetic_fire(case):
    """If hazard_contract.synthetic changes, these fail first (the plan below relies on them)."""
    _, inst, ss, plan, _ = case
    assert ss.meta.synthetic and ss.meta.source == "synthetic"
    H = ss.meta.horizon_s
    assert np.all(ss.ignite_s[:, 11, 13] < 0) and np.all(ss.extinguish_s[:, 11, 13] > H)   # V2 passes here
    for e in plan.itineraries[0].actions[0].edges + plan.itineraries[0].actions[2].edges:  # V1: never burns
        r, c = chord_cells(ss, inst, e)
        assert np.all(np.isinf(ss.ignite_s[:, r, c]))
    detour = plan.itineraries[2].actions[3]
    for i, e in enumerate(detour.edges):                                               # V3: burns later only
        r, c = chord_cells(ss, inst, e)
        leaves = detour.depart_s + TRAVEL * (i + 1)
        assert np.all(ss.ignite_s[:, r, c] > leaves + 600.0)


def test_plan_is_resource_valid(case):
    _, inst, _, plan, _ = case
    assert validate_solution(inst, plan).ok


def test_three_states_end_to_end(case):
    _, inst, ss, plan, r = case
    assert r.label == "SYNTHETIC" and r.synthetic and r.scope.synthetic and r.scope.source == "synthetic"
    assert r.scope.K == 4 and r.scope.horizon_instance_s == 10_800.0
    got = {v.vehicle: (v.state, v.cause) for v in r.vehicles}
    assert got == {"V1": (State.CHECKED, None), "V2": (State.MODEL_NO_ROUTE, "FLAME_CONTACT"),
                   "V3": (State.CHECKED, None), "V4": (State.UNRESOLVED, "BEYOND_HORIZON")}
    assert r.delivered.vector() == (10, 4, 1) and r.delivered_total == 15
    assert {k: v.vector() for k, v in r.delivered_by_facility.items()} == {"F_N": (4, 2, 0), "F_W": (6, 2, 1)}
    assert r.model_no_route_by_reason == {"FLAME_CONTACT": 4}
    assert r.unresolved_by_reason == {"BEYOND_HORIZON": 5}
    assert {k: v.vector() for k, v in r.not_planned.items()} == {"F_N": (2, 0, 0)}
    assert r.delivered_total + r.unresolved_total + r.model_no_route_total + r.not_planned_total == r.residents_total
    v2 = next(v for v in r.vehicles if v.vehicle == "V2")
    contact = next(lg for lg in v2.legs if lg.cause == "FLAME_CONTACT")
    assert contact.kind == "drive" and contact.members is not None
    assert any(m.contact for m in contact.members)                 # one member with contact is enough
    slacks = [v.min_slack_s for v in r.vehicles if v.state is State.CHECKED]
    assert r.min_slack_s == min(slacks) and r.min_slack_s > 600.0
    assert r.makespan_s == max(v.end_s for v in r.vehicles)


def test_relaxed_check_flags_the_blocked_route_only(case):
    _, inst, ss, plan, _ = case
    rc = RelaxedContactCheck(inst, ss)
    out = {it.vehicle: rc.itinerary(it) for it in plan.itineraries}
    assert out["V2"].first_blocked is not None
    assert out["V1"].first_blocked is None and out["V3"].first_blocked is None and out["V4"].first_blocked is None
    assert out["V4"].any_uncertain and not out["V1"].any_uncertain


def test_result_json_round_trip_and_determinism(case):
    d, inst, ss, plan, r = case
    p = d / "result.json"
    p.write_text(r.model_dump_json(indent=1))
    back = PlanResult.model_validate_json(p.read_text())
    assert back == r
    assert '"label":"SYNTHETIC"' in r.model_dump_json()
    assert check_plan(inst, ss, plan) == r
