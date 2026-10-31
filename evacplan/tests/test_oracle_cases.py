"""Oracle: hand-worked cases with exact expected states, causes and slacks (all SYNTHETIC).

Grid: 3 x 3 cells of 100 m (cell (r, c) spans x in [100c, 100c+100], y in [100(2-r), 100(3-r)]);
nodes at cell centres, lattice edges of 50 s unless stated otherwise.
"""
import numpy as np
import pytest

from evacplan import (
    Edge, Node, Oracle, OracleInputError, RoadGraph, State, check_itinerary, check_plan, validate_solution,
)
from evacplan_testkit import (
    CRS, INF, NAN, board, drive, facility, grid_graph, instance, itinerary, make_set, nid, path, quiet, shelter,
    solution, unload, vehicle, wait,
)

CHECKED, MNR, UNR = State.CHECKED, State.MODEL_NO_ROUTE, State.UNRESOLVED
ROW = [(1, 0), (1, 1), (1, 2)]


def through_row(ig, ex=None, *, horizon=10_000.0, **kw):
    """Board 2 at F (1,0) [0, 20], drive (1,0)->(1,1)->(1,2) [20, 70], [70, 120], unload at S [120, 130]."""
    ss = make_set(ig, ex, horizon=horizon)
    inst = instance(grid_graph(3, 3), facilities=[facility("F", nid(1, 0), amb=2)],
                    vehicles=[vehicle("V", nid(1, 0))], shelters=[shelter("S", nid(1, 2))], **kw)
    sol = solution(itinerary("V", board("F", amb=2), drive(path(*ROW), 20), unload("S", amb=2)))
    return inst, ss, sol


def states(res):
    return [lg.state for lg in res.legs]


# ------------------------------------------------------------------ a leg through a burning cell
def test_leg_through_a_burning_cell_is_model_no_route():
    ig = quiet(3, 3)
    ig[0, 1, 1] = 50.0                      # the middle cell ignites while the vehicle crosses it
    inst, ss, sol = through_row(ig)
    r = check_plan(inst, ss, sol)
    v = r.vehicles[0]
    assert [lg.kind for lg in v.legs] == ["board", "drive", "drive", "unload"]
    assert states(v) == [CHECKED, MNR, MNR, MNR]
    assert v.legs[1].reasons == ["FLAME_CONTACT"] and v.legs[1].cause == "FLAME_CONTACT"
    assert v.legs[2].hazard_state is None   # not evaluated after a certain violation (cannot improve)
    assert v.trips[0].state is MNR and r.delivered_total == 0
    assert r.model_no_route_by_reason == {"FLAME_CONTACT": 2} and r.unresolved_total == 0


def test_contact_uses_closed_occupancy_and_half_open_burning():
    # the vehicle enters the middle cell at x = 100, t = 20 + 25 = 45 exactly
    ig = quiet(3, 3)
    ig[0, 1, 1] = -500.0
    ex = np.where(np.isfinite(ig), 45.0, ig)        # burning [-500, 45): out at the entry instant
    assert check_plan(*through_row(ig, ex)).vehicles[0].state is CHECKED
    ex = np.where(np.isfinite(ig), np.nextafter(45.0, INF), ig)
    assert check_plan(*through_row(ig, ex)).vehicles[0].state is MNR
    # the vehicle leaves the middle cell at x = 200, t = 70 + 25 = 95; ignition at 95 is contact, later is not
    ig[0, 1, 1] = 95.0
    assert check_plan(*through_row(ig)).vehicles[0].legs[2].hazard_state is MNR
    ig[0, 1, 1] = np.nextafter(95.0, INF)
    assert check_plan(*through_row(ig)).vehicles[0].state is CHECKED


def test_safety_slack_is_exact_from_cell_intervals():
    ig = quiet(3, 3)
    ig[0, 1, 1] = 130.0                     # the vehicle last touches the middle cell at t = 95
    inst, ss, sol = through_row(ig)
    v = check_plan(inst, ss, sol).vehicles[0]
    assert states(v) == [CHECKED] * 4
    board_leg, d1, d2, unl = v.legs
    assert d1.slack_s == pytest.approx(130.0 - 70.0)    # first edge ends at the middle node at t = 70
    assert d2.slack_s == pytest.approx(130.0 - 95.0)    # second edge leaves the middle cell at t = 95
    assert board_leg.slack_s == pytest.approx(10_000.0 - 20.0)   # nothing burns near: capped at the horizon
    assert unl.slack_s == pytest.approx(10_000.0 - 130.0)
    assert v.min_slack_s == pytest.approx(35.0)
    # delaying the plan by just under the slack keeps it checked; by the slack, it is contact
    for delay, want in ((34.999, CHECKED), (35.0, MNR)):
        sol2 = solution(itinerary("V", wait(nid(1, 0), delay), board("F", amb=2),
                                  drive(path(*ROW), 20 + delay), unload("S", amb=2)))
        assert check_plan(inst, ss, sol2).vehicles[0].trips[0].state is want


def test_slack_is_capped_at_the_horizon_and_takes_the_earliest_member():
    ig = quiet(3, 3, K=2)
    ig[0, 1, 1] = 400.0
    ig[1, 1, 1] = 200.0
    inst, ss, sol = through_row(ig, horizon=300.0)
    v = check_plan(inst, ss, sol).vehicles[0]
    assert v.legs[2].slack_s == pytest.approx(200.0 - 95.0)      # member 1 burns first
    assert v.legs[0].slack_s == pytest.approx(300.0 - 20.0)      # horizon cap


# ------------------------------------------------------------- a wait in a cell that ignites
def wait_case(ignite):
    ig = quiet(3, 3)
    ig[0, 1, 1] = ignite
    ss = make_set(ig)
    inst = instance(grid_graph(3, 3), facilities=[facility("F", nid(1, 1), amb=1)],
                    vehicles=[vehicle("V", nid(1, 1))], shelters=[shelter("S", nid(1, 0))])
    sol = solution(itinerary("V", board("F", amb=1), wait(nid(1, 1), 100.0), drive(path((1, 1), (1, 0)), 110),
                             unload("S", amb=1)))
    return check_plan(inst, ss, sol)


@pytest.mark.parametrize("ignite,want", [(60.0, MNR), (110.0, MNR), (np.nextafter(110.0, INF), None)])
def test_wait_in_a_cell_that_ignites(ignite, want):
    r = wait_case(ignite)
    v = r.vehicles[0]
    board_leg, wait_leg = v.legs[:2]
    assert board_leg.state is CHECKED and board_leg.slack_s == pytest.approx(ignite - 10.0)
    if want is MNR:                                   # waiting [10, 110] meets the ignition (closed interval)
        assert wait_leg.hazard_state is MNR and wait_leg.cause == "FLAME_CONTACT"
        assert r.model_no_route_total == 1 and r.delivered_total == 0
    else:                                             # the wait is fine but driving out crosses the cell
        assert wait_leg.state is CHECKED and wait_leg.slack_s == pytest.approx(ignite - 110.0)
        assert v.legs[2].hazard_state is MNR


# --------------------------------------------------------------------------- a corner touch
def corner_case(burn_from, burn_to, *, shift=0.0):
    """Edge P->Q along x + y = 400 - shift: through the corner (200, 200) at t = 50 when shift = 0."""
    nodes = [Node(id="P", x=150.0, y=250.0 - shift, waitable=True), Node(id="Q", x=250.0 - shift, y=150.0)]
    g = RoadGraph(crs_epsg=CRS, nodes=nodes, edges=[Edge(id="PQ", u="P", v="Q", travel_time_s=100.0)])
    ig = quiet(3, 3)
    ig[0, 0, 2] = burn_from                           # the top-right cell touches the road only at the corner
    ex = np.where(np.isfinite(ig), burn_to, ig)
    ss = make_set(ig, ex)
    inst = instance(g, vehicles=[vehicle("V", "P")])
    return check_itinerary(inst, ss, itinerary("V", drive(["PQ"], 0.0)))


def test_corner_touch_is_contact_with_closed_cells():
    assert corner_case(40.0, 60.0).state is MNR                   # burning while the road meets the corner
    assert corner_case(40.0, 60.0).legs[0].cause == "FLAME_CONTACT"
    assert corner_case(0.0, 30.0).state is CHECKED                # burned out before the corner instant
    assert corner_case(50.0, 60.0).state is MNR                   # ignites exactly at the corner instant
    assert corner_case(40.0, 50.0).state is CHECKED               # extinguished exactly then (half-open)
    assert corner_case(40.0, 60.0, shift=1.0).state is CHECKED    # 0.7 m away from the corner: no touch


def test_waiting_on_a_grid_corner_touches_all_four_cells():
    g = RoadGraph(crs_epsg=CRS, nodes=[Node(id="X", x=200.0, y=200.0, waitable=True)])
    inst = instance(g, vehicles=[vehicle("V", "X")])
    for r, c in ((0, 1), (0, 2), (1, 1), (1, 2)):
        ig = quiet(3, 3)
        ig[0, r, c] = 5.0
        assert check_itinerary(inst, make_set(ig), itinerary("V", wait("X", 10.0))).state is MNR
    ig = quiet(3, 3)
    ig[0, 2, 2] = 5.0                                              # not adjacent to the corner
    assert check_itinerary(inst, make_set(ig), itinerary("V", wait("X", 10.0))).state is CHECKED


# ------------------------------------------------------------------- dose across trips
def shuttle_case(n_trips=4):
    """Shuttle between S at (2,0) and F at (1,1), next to the burning cell (0,2): 100 s boardings."""
    ig = quiet(3, 3)
    ig[0, 0, 2] = -100.0
    ss = make_set(ig, burn=1e6)
    inst_kw = dict(facilities=[facility("F", nid(1, 1), bed=n_trips, board=(10, 20, 100))],
                   vehicles=[vehicle("V", nid(2, 0), seats=0, wc=0, stretchers=1)],
                   shelters=[shelter("S", nid(2, 0))])
    acts, t = [], 0.0
    for _ in range(n_trips):
        acts += [drive(path((2, 0), (1, 0), (1, 1)), t), board("F", bed=1)]
        t += 100 + 100
        acts += [drive(path((1, 1), (1, 0), (2, 0)), t), unload("S", bed=1)]
        t += 100 + 15
    return ss, inst_kw, solution(itinerary("V", *acts))


def independent_trip_doses(inst, ss, sol):
    """Per-trip dose bounds [K] summed from hazard_contract queries on the validator's timeline."""
    sch = validate_solution(inst, sol).schedules[0]
    off = inst.hazard.t0_offset_s
    lo, hi, per_trip = np.zeros(ss.K), np.zeros(ss.K), []
    unloads = {u.action for u in sch.unloads}
    for seg in sch.segments:
        if seg.edge is not None:
            e = next(e for e in inst.graph.edges if e.id == seg.edge)
            nodes = {n.id: n for n in inst.graph.nodes}
            geom = np.array([[nodes[e.u].x, nodes[e.u].y], [nodes[e.v].x, nodes[e.v].y]])
            hz = ss.query_uniform(geom, seg.t0 + off, seg.t1 + off)
        else:
            n = next(n for n in inst.graph.nodes if n.id == seg.node)
            hz = ss.query(np.array([[n.x, n.y]]), seg.t0 + off, seg.t1 + off)
        lo += [h.dose_lower for h in hz]
        hi += [h.dose_upper for h in hz]
        if seg.action in unloads and seg.kind == "unload":
            per_trip.append((lo.copy(), hi.copy()))
            lo[:], hi[:] = 0.0, 0.0
    return per_trip


def test_dose_accumulates_across_trips():
    n = 8
    ss, kw, sol = shuttle_case(n)
    probe = instance(grid_graph(3, 3), **kw)
    trips = independent_trip_doses(probe, ss, sol)
    single_hi = max(float(h[0]) for _, h in trips)
    budget = single_hi * 1.001                        # every trip alone passes for sure
    cum_lo = np.cumsum([float(lo[0]) for lo, _ in trips])
    cum_hi = np.cumsum([float(hi[0]) for _, hi in trips])
    want = [MNR if cum_lo[i] > budget else UNR if cum_hi[i] > budget else CHECKED for i in range(n)]
    # the case shows accumulation: trip 1 is safe, the next ones are uncertain, the last ones certainly over
    assert want[0] is CHECKED and want[1] is UNR and want[-1] is MNR
    r = check_plan(instance(grid_graph(3, 3), dose=budget, **kw), ss, sol)
    got = [t.state for t in r.vehicles[0].trips]
    assert got == want
    causes = [t.cause for t in r.vehicles[0].trips]
    assert causes[1] == "DOSE_UNRESOLVED" and causes[-1] == "DOSE_ABOVE_BUDGET"
    assert r.delivered_total == 1
    assert r.unresolved_by_reason == {"DOSE_UNRESOLVED": want.count(UNR)}
    assert r.model_no_route_by_reason == {"DOSE_ABOVE_BUDGET": want.count(MNR)}
    first_mnr = want.index(MNR)
    v = r.vehicles[0]
    for i, t in enumerate(v.trips[:first_mnr]):           # the oracle's running sums match, trip by trip
        end_leg = [lg for lg in v.legs if lg.action == t.action][-1]
        assert end_leg.cum_dose_lower[0] == pytest.approx(cum_lo[i], rel=1e-9)
        assert end_leg.cum_dose_upper[0] == pytest.approx(cum_hi[i], rel=1e-9)
    over = next(lg for lg in v.legs if lg.dose_state is MNR)          # where the lower sum crosses the budget
    assert over.cum_dose_lower[0] > budget and over.cause == "DOSE_ABOVE_BUDGET"
    assert v.trips[first_mnr - 1].action < over.action <= v.trips[first_mnr].action


def test_dose_budgets_are_per_member():
    ss1, kw, sol = shuttle_case(1)
    ig = np.stack([ss1.ignite_s[0], np.full((3, 3), INF)])         # member 1: no fire at all
    ss = make_set(ig, burn=1e6)
    hi = independent_trip_doses(instance(grid_graph(3, 3), **kw), ss, sol)[0][1]
    assert hi[1] == 0.0 and hi[0] > 0.0
    tight_m0 = instance(grid_graph(3, 3), dose=[hi[0] / 10, 1.0], **kw)
    tight_m1 = instance(grid_graph(3, 3), dose=[hi[0] * 1.001, 0.0], **kw)
    assert check_plan(tight_m0, ss, sol).vehicles[0].trips[0].state is not CHECKED
    assert check_plan(tight_m1, ss, sol).vehicles[0].trips[0].state is CHECKED   # zero dose in member 1


# --------------------------------------------------------------------------- peak budget
def test_peak_budget_lower_and_upper_bounds():
    ss, kw, sol = shuttle_case(1)
    inst = instance(grid_graph(3, 3), **kw)
    v = check_plan(inst, ss, sol).vehicles[0]
    board_leg = next(lg for lg in v.legs if lg.kind == "board")
    lo, up = board_leg.members[0].flux_lower, board_leg.members[0].flux_upper
    assert 0 < lo < up
    r = check_plan(instance(grid_graph(3, 3), peak=lo / 2, **kw), ss, sol)
    assert r.vehicles[0].trips[0].state is MNR and r.vehicles[0].trips[0].cause == "PEAK_ABOVE_BUDGET"
    r = check_plan(instance(grid_graph(3, 3), peak=(lo + up) / 2, **kw), ss, sol)
    assert r.vehicles[0].trips[0].state is UNR and r.vehicles[0].trips[0].cause == "PEAK_UNRESOLVED"
    assert check_plan(instance(grid_graph(3, 3), peak=up, **kw), ss, sol).delivered_total == 1


# --------------------------------------------------------------------------- horizon overrun
def two_trips(horizon, offset=0.0):
    """Trip 1 unloads [120, 130]; trip 2 drives back and unloads [380, 390] (instance time)."""
    ss = make_set(quiet(3, 3), horizon=horizon)
    inst = instance(grid_graph(3, 3), facilities=[facility("F", nid(1, 0), amb=4)],
                    vehicles=[vehicle("V", nid(1, 0))], shelters=[shelter("S", nid(1, 2))], offset=offset)
    acts = [board("F", amb=2), drive(path(*ROW), 20), unload("S", amb=2),
            drive(path(*ROW[::-1]), 130), board("F", amb=2), drive(path(*ROW), 250), unload("S", amb=2)]
    return check_plan(inst, ss, solution(itinerary("V", *acts)))


def test_horizon_overrun_is_unresolved():
    r = two_trips(horizon=300.0)
    v = r.vehicles[0]
    assert [t.state for t in v.trips] == [CHECKED, UNR]
    assert v.trips[1].cause == "BEYOND_HORIZON"
    first_late = next(lg for lg in v.legs if lg.t_end > 300.0)
    assert first_late.hazard_state is UNR and "BEYOND_HORIZON" in first_late.reasons
    assert all(lg.state is CHECKED for lg in v.legs if lg.t_end <= 300.0)
    assert r.delivered_total == 2 and r.unresolved_by_reason == {"BEYOND_HORIZON": 2}
    assert r.scope.horizon_instance_s == 300.0
    assert two_trips(horizon=400.0).delivered_total == 4


def test_offset_maps_instance_time_to_hazard_time():
    r = two_trips(horizon=300.0, offset=200.0)                     # instance horizon is 100 s
    assert [t.state for t in r.vehicles[0].trips] == [UNR, UNR]
    assert r.scope.horizon_instance_s == 100.0
    assert two_trips(horizon=600.0, offset=200.0).delivered_total == 4


# ------------------------------------------------------------ unsupported data, never improves
def test_unknown_cell_on_the_route_is_unresolved_never_delivered():
    ig = quiet(3, 3)
    ig[0, 1, 1] = NAN
    r = check_plan(*through_row(ig))
    v = r.vehicles[0]
    assert states(v) == [CHECKED, UNR, UNR, UNR]
    assert v.legs[1].reasons == ["UNSUPPORTED_HAZARD"] and v.legs[1].members[0].contact is None
    assert r.delivered_total == 0 and r.unresolved_by_reason == {"UNSUPPORTED_HAZARD": 2}


def test_leaving_the_hazard_grid_is_unresolved():
    g = grid_graph(3, 3, extra_nodes=[Node(id="out", x=450.0, y=150.0)],
                   extra_edges=[Edge(id="away", u=nid(1, 2), v="out", travel_time_s=50.0)])
    inst = instance(g, vehicles=[vehicle("V", nid(1, 1))])
    v = check_itinerary(inst, make_set(quiet(3, 3)), itinerary("V", drive([path((1, 1), (1, 2))[0], "away"], 0)))
    assert [lg.hazard_state for lg in v.legs] == [CHECKED, UNR]
    assert v.legs[1].reasons == ["OUTSIDE_HAZARD_GRID", "DOSE_UNRESOLVED"]    # unbounded dose outside the grid
    assert v.legs[1].cause == "OUTSIDE_HAZARD_GRID" and v.legs[1].cum_dose_upper == [float("inf")]


def test_state_never_improves_and_a_later_violation_still_counts():
    ig = quiet(3, 3)
    ig[0, 1, 1] = NAN
    ig[0, 2, 2] = 0.0
    ss = make_set(ig)
    inst = instance(grid_graph(3, 3), facilities=[facility("F", nid(1, 0), amb=3)],
                    vehicles=[vehicle("V", nid(1, 0))], shelters=[shelter("S", nid(1, 2))])
    acts = [board("F", amb=1), drive(path(*ROW), 10), unload("S", amb=1),          # through unknown: UNR
            drive(path((1, 2), (0, 2), (1, 2)), 115), unload("S", amb=0),          # a quiet loop: stays UNR
            drive(path((1, 2), (2, 2)), 215)]                                      # into the fire: MNR
    v = check_plan(inst, ss, solution(itinerary("V", *acts))).vehicles[0]
    assert not v.issues
    assert [t.state for t in v.trips] == [UNR, UNR]
    quiet_leg = v.legs[4]
    assert quiet_leg.edge == path((1, 2), (0, 2))[0]
    assert quiet_leg.hazard_state is CHECKED and quiet_leg.state is UNR and quiet_leg.cause == "UNSUPPORTED_HAZARD"
    assert v.state is MNR and v.cause == "FLAME_CONTACT"


def test_resource_violation_is_model_no_route_from_its_action_on():
    ss = make_set(quiet(3, 3))
    inst = instance(grid_graph(3, 3), facilities=[facility("F", nid(1, 0), amb=6)],
                    vehicles=[vehicle("V", nid(1, 0), seats=2)], shelters=[shelter("S", nid(1, 2))])
    acts = [board("F", amb=2), drive(path(*ROW), 20), unload("S", amb=2),
            drive(path(*ROW[::-1]), 130), board("F", amb=3), drive(path(*ROW), 260), unload("S", amb=3)]
    r = check_plan(inst, ss, solution(itinerary("V", *acts)))
    v = r.vehicles[0]
    assert [t.state for t in v.trips] == [CHECKED, MNR]
    assert v.trips[1].cause == "RESOURCE:VEHICLE_CAPACITY"
    assert v.actions[4].issues == ["VEHICLE_CAPACITY"] and v.actions[3].state is CHECKED
    assert r.delivered_total == 2 and r.model_no_route_by_reason == {"RESOURCE:VEHICLE_CAPACITY": 3}
    assert r.not_planned_total == 1 and r.not_planned["F"].ambulatory == 1


def test_residents_left_on_board_are_model_no_route():
    ss = make_set(quiet(3, 3))
    inst = instance(grid_graph(3, 3), facilities=[facility("F", nid(1, 0), amb=2)],
                    vehicles=[vehicle("V", nid(1, 0))], shelters=[shelter("S", nid(1, 2))])
    r = check_plan(inst, ss, solution(itinerary("V", board("F", amb=2), drive(path(*ROW), 20))))
    assert r.vehicles[0].state is MNR and r.vehicles[0].cause == "RESOURCE:NOT_UNLOADED"
    assert r.vehicles[0].onboard_end.ambulatory == 2
    assert r.model_no_route_by_reason == {"RESOURCE:NOT_UNLOADED": 2}
    assert r.delivered_total + r.unresolved_total + r.model_no_route_total + r.not_planned_total == 2


# --------------------------------------------------------------------- plan-level accounting
def test_plan_accounting_scope_and_labels():
    ig = quiet(3, 3, K=2)
    ig[1, 2, 2] = 0.0                       # member 1 only: fire in the bottom-right cell
    ss = make_set(ig)
    inst = instance(grid_graph(3, 3), facilities=[facility("F", nid(1, 0), amb=3, wc=1), facility("G", nid(0, 0), amb=2)],
                    vehicles=[vehicle("V1", nid(1, 0)), vehicle("V2", nid(2, 0))], shelters=[shelter("S", nid(1, 2))])
    v1 = itinerary("V1", board("F", amb=2, wc=1), drive(path(*ROW), 40), unload("S", amb=2, wc=1))
    v2 = itinerary("V2", drive(path((2, 0), (2, 1), (2, 2), (1, 2)), 0), unload("S"))      # empty run through fire
    r = check_plan(inst, ss, solution(v1, v2))
    assert r.label == "SYNTHETIC" and r.synthetic and r.scope.K == 2 and r.scope.model_version == "evacplan-test"
    assert r.delivered.vector() == (2, 1, 0) and r.delivered_by_facility["F"].vector() == (2, 1, 0)
    assert r.vehicles[1].state is MNR                # contact in member 1 is enough
    assert r.not_planned == {"F": r.not_planned["F"], "G": r.not_planned["G"]}
    assert r.not_planned["F"].vector() == (1, 0, 0) and r.not_planned["G"].vector() == (2, 0, 0)
    assert r.residents_total == 6 == r.delivered_total + r.not_planned_total
    # V1: board 2 amb + 1 wc [0, 40], drive [40, 140], unload [140, 160]; V2: drive [0, 150], empty unload
    assert r.vehicle_time_s == pytest.approx(160.0 + 150.0) and r.makespan_s == pytest.approx(160.0)
    assert r.min_slack_s == pytest.approx(10_000.0 - 160.0)
    assert r.model_dump_json()                       # serialisable (inf written as a string)


def test_input_mismatches_are_refused():
    ss = make_set(quiet(3, 3))
    inst = instance(grid_graph(3, 3), vehicles=[vehicle("V", nid(0, 0))])
    other_crs = inst.model_copy(update={"graph": inst.graph.model_copy(update={"crs_epsg": 5179})})
    with pytest.raises(OracleInputError):
        Oracle(other_crs, ss)
    with pytest.raises(OracleInputError):
        Oracle(instance(grid_graph(3, 3), dose=[1.0, 2.0]), ss)
    with pytest.raises(OracleInputError):
        check_plan(inst, ss, solution(name="another instance"))


def test_check_itinerary_matches_check_plan_and_evaluating_after_failure_changes_no_state():
    ig = quiet(3, 3)
    ig[0, 1, 1] = 50.0
    inst, ss, sol = through_row(ig)
    alone = check_itinerary(inst, ss, sol.itineraries[0])
    assert alone == check_plan(inst, ss, sol).vehicles[0]
    full = Oracle(inst, ss, evaluate_after_failure=True).check_plan(sol).vehicles[0]
    assert states(full) == states(alone)
    assert full.legs[2].hazard_state is not None and alone.legs[2].hazard_state is None
