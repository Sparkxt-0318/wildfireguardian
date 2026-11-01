"""Per-facility deadlines and unservable residents: every state comes from the oracle, deadlines are
hand-worked, model_no_route is declared only when it is certain (scoped), and unknown stays
unresolved. SYNTHETIC fixtures (geometry as in test_reach: 100 m cells, 50 s edges)."""
import numpy as np
import pytest

from evacplan import Oracle, State
from evacplan.deadlines import class_deadlines, facility_summary
from evacplan.oracle import (
    NO_ROUTE, NO_SHELTER_CAPACITY, NO_VEHICLE_IN_TIME, NO_VEHICLE_SPACE, PROBE_VEHICLE, RELAXATION_INCOMPLETE,
)
from evacplan_testkit import (
    NAN, eid, facility, grid_graph, instance, make_set, nid, quiet, random_case, shelter, vehicle,
)

PERSIST = 1e9


def case(*, H=1, W=4, ig_cells=(), burn=PERSIST, horizon=10_000.0, residents=(5, 0, 0), release=0.0,
         vehicles=None, shelter_cap=(100, 100, 100), window=((0.0, 1e6),), waitable=True, forbidden=(), sup=None):
    ig = quiet(H, W)
    for (r, c), t in ig_cells:
        ig[0, r, c] = t
    ss = make_set(ig, horizon=horizon, burn=burn, sup=sup)
    inst = instance(grid_graph(H, W, waitable=waitable, forbidden=forbidden),
                    facilities=[facility("F", nid(0, 0), *residents, release=release)],
                    vehicles=vehicles if vehicles is not None else [vehicle("V", nid(0, W - 1))],
                    shelters=[shelter("S", nid(0, W - 1), cap=shelter_cap, windows=window)])
    return inst, ss


def one(inst, ss, cls="ambulatory"):
    (d,) = [x for x in class_deadlines(inst, ss) if x.mobility_class == cls]
    return d


def test_checked_deadline_hand_worked():
    # cell (0,1) burns from 500: the last checkable departure from F is 424 (test_reach); boarding one
    # ambulatory resident takes 10 s -> the first vehicle must arrive by 414.
    inst, ss = case(ig_cells=[((0, 1), 500.0)])
    d = one(inst, ss)
    assert d.state is State.CHECKED and d.cause is None and d.unservable == 0
    assert (d.arrive_by_s, d.leave_by_s, d.shelter) == (414.0, 424.0, "S")
    assert d.route == [eid((0, 0), (0, 1)), eid((0, 1), (0, 2)), eid((0, 2), (0, 3))]
    assert d.probe_state is State.CHECKED and 0 <= d.probe_min_slack_s <= 1.0     # sup of safe delays: 1 s, not attained
    assert "per facility and mobility class" in d.scope
    # the oracle itself rejects the same trip one second later: contact at the instant 500
    oracle = Oracle(inst, ss)
    late = oracle.probe_trip("F", 0, 415.0, [
        _drive([eid((0, 0), (0, 1)), eid((0, 1), (0, 2)), eid((0, 2), (0, 3))], 425.0),
        _unload("S")])
    assert late.state is State.MODEL_NO_ROUTE and late.cause == "FLAME_CONTACT"
    s = facility_summary([d])["F"]
    assert s["arrive_by_s"] == 414.0 and s["leave_by_s"] == 424.0 and s["unservable"] == 0


def _drive(edges, t):
    from evacplan_testkit import drive
    return drive(edges, t)


def _unload(sid, amb=1):
    from evacplan_testkit import unload
    return unload(sid, amb)


def test_burning_facility_is_scoped_model_no_route():
    inst, ss = case(ig_cells=[((0, 0), -100.0)])            # the facility's own cell burns from before issue
    d = one(inst, ss)
    assert d.state is State.MODEL_NO_ROUTE and d.cause == "UNSERVABLE:" + NO_ROUTE
    assert d.unservable == d.residents == 5 and d.arrive_by_s is None and d.leave_by_s is None
    assert "horizon" in d.scope and "not a promise" in d.scope
    assert d.detail.startswith("certain-contact relaxation:")        # the fire is what refuses here


def test_horizon_only_refusal_has_its_own_cause(tmp_path):
    """Nothing burns, the horizon is 100 s and F -> S is three 50 s edges: no trip can end by the horizon,
    with no contact involved. That is its own cause, NO_TRIP_BY_HORIZON (still model_no_route scoped to the
    horizon, ASSUMPTIONS #74, until Siyeong answers question 12), with a detail that names the horizon and not
    the certain-contact relaxation. The oracle rates the actual trip unresolved (BEYOND_HORIZON), and the
    facilities CSV shows the distinct cause next to that outcome."""
    from evacplan.harness import facility_outcomes, make_facility_rows, make_row, read_rows, upsert_rows
    from evacplan_testkit import board, drive, itinerary, path, solution, unload

    inst, ss = case(horizon=100.0)
    d = one(inst, ss)
    assert d.state is State.MODEL_NO_ROUTE and d.cause == "UNSERVABLE:NO_TRIP_BY_HORIZON"
    assert d.unservable == d.residents == 5 and d.arrive_by_s is None
    assert "horizon" in d.detail and "100" in d.detail and "no fire" in d.detail and "contact" not in d.detail
    trip = itinerary("V", drive(path((0, 3), (0, 2), (0, 1), (0, 0)), 0.0), board("F", 5),
                     drive(path((0, 0), (0, 1), (0, 2), (0, 3)), 200.0), unload("S", 5))
    sol = solution(trip)
    plan = Oracle(inst, ss).check_plan(sol)
    assert plan.delivered_total == 0 and plan.model_no_route_total == 0
    assert plan.unresolved_total == 5 and plan.unresolved_by_reason == {"BEYOND_HORIZON": 5}

    class Entry:
        id, generator, generator_version, config, fingerprint, label = inst.name, "hand", "0", {}, "none", "SYNTHETIC"
    row = make_row(entry=Entry, set_name="dev", method_name="hand", method_config={}, seed=0, budget_s=60.0,
                   plan=plan, runtime_s=0.0, best_bound=None, commit="c", host="h")
    csv_path = tmp_path / "hand.facilities.csv"
    upsert_rows(csv_path, make_facility_rows(entry=Entry, method_name="hand", seed=0, row=row, instance=inst,
                                             deadlines=class_deadlines(inst, ss),
                                             outcomes=facility_outcomes(inst, sol, plan)))
    (r,) = read_rows(csv_path)
    assert (r["deadline_state"], r["deadline_cause"], r["unservable"]) == (
        "model_no_route", "UNSERVABLE:NO_TRIP_BY_HORIZON", "5")
    assert (r["delivered_checked"], r["unresolved"], r["model_no_route"]) == ("0", "5", "0")


def test_horizon_only_vehicle_refusal_keeps_the_deadline():
    # F -> S fits the 400 s horizon (leave by 245, arrive by 235, checked), but the only vehicle starts at 300 at
    # S's node and needs 150 s to reach F: no fire involved, only the horizon
    inst, ss = case(horizon=400.0, vehicles=[vehicle("V", nid(0, 3), start=300.0)])
    d = one(inst, ss)
    assert d.state is State.MODEL_NO_ROUTE and d.cause == "UNSERVABLE:NO_TRIP_BY_HORIZON" and d.unservable == 5
    assert (d.arrive_by_s, d.leave_by_s) == (235.0, 245.0) and d.probe_state is State.CHECKED
    assert "V:" in d.detail and "horizon" in d.detail and "contact" not in d.detail
    # starting at 0 it is in time
    inst, ss = case(horizon=400.0, vehicles=[vehicle("V", nid(0, 3), start=0.0)])
    assert one(inst, ss).state is State.CHECKED


def test_refusals_without_fire_or_horizon_are_not_blamed_on_contact():
    # the only shelter closes at 100 s, before any trip from F can reach it, whatever the fire and the horizon
    inst, ss = case(window=((0.0, 100.0),))
    d = one(inst, ss)
    assert d.state is State.MODEL_NO_ROUTE and d.cause == "UNSERVABLE:" + NO_ROUTE
    assert "no fire" in d.detail and "contact" not in d.detail
    # the only vehicle's shift ends before it can finish one trip
    inst, ss = case(ig_cells=[((0, 1), 500.0)], vehicles=[vehicle("V", nid(0, 3), start=0.0, shift=250.0)])
    d = one(inst, ss)
    assert d.cause == "UNSERVABLE:" + NO_VEHICLE_IN_TIME and "shift" in d.detail and "contact" not in d.detail


def test_no_vehicle_in_time_keeps_the_deadline():
    # the only vehicle starts east of the fire at 450: it can never cross cell (0,1) again
    inst, ss = case(ig_cells=[((0, 1), 500.0)], vehicles=[vehicle("V", nid(0, 3), start=450.0)])
    d = one(inst, ss)
    assert d.state is State.MODEL_NO_ROUTE and d.cause == "UNSERVABLE:" + NO_VEHICLE_IN_TIME
    assert (d.arrive_by_s, d.leave_by_s) == (414.0, 424.0) and d.unservable == 5
    # the same vehicle starting at 0 is in time
    inst, ss = case(ig_cells=[((0, 1), 500.0)], vehicles=[vehicle("V", nid(0, 3), start=0.0)])
    assert one(inst, ss).state is State.CHECKED
    # ... unless its shift ends before it could finish one trip
    inst, ss = case(ig_cells=[((0, 1), 500.0)], vehicles=[vehicle("V", nid(0, 3), start=0.0, shift=250.0)])
    assert one(inst, ss).cause == "UNSERVABLE:" + NO_VEHICLE_IN_TIME


def test_resource_claims():
    inst, ss = case(residents=(2, 0, 1), vehicles=[vehicle("V", nid(0, 3), stretchers=0)])
    d = one(inst, ss, "bedbound")
    assert d.state is State.MODEL_NO_ROUTE and d.cause == "UNSERVABLE:" + NO_VEHICLE_SPACE and d.unservable == 1
    assert one(inst, ss).state is State.CHECKED
    inst, ss = case(residents=(2, 0, 1), shelter_cap=(100, 100, 0))
    d = one(inst, ss, "bedbound")
    assert d.cause == "UNSERVABLE:" + NO_SHELTER_CAPACITY and d.unservable == 1


def test_unknown_is_never_model_no_route():
    # unknown cells on the only road: no checkable route, but nothing certain either -> unresolved
    ig = quiet(1, 4)
    ig[0, 0, 1] = NAN
    inst, ss = case()
    ss = make_set(ig, horizon=10_000.0, burn=PERSIST)
    d = one(inst, ss)
    assert d.state is State.UNRESOLVED and d.unservable == 0 and d.leave_by_s is None
    # a refusal that needs waits or turns the relaxation allows stays unresolved too
    uturns = [(eid((0, c), (0, c + k)), eid((0, c + k), (0, c))) for c in range(4) for k in (-1, 1) if 0 <= c + k < 4]
    inst, ss = case(ig_cells=[((0, 1), 500.0)], window=((1000.0, 1e6),), waitable={(0, 0)}, forbidden=uturns)
    d = one(inst, ss)
    assert d.state is State.UNRESOLVED and d.unservable == 0


def test_relaxation_claims_need_a_complete_lattice():
    # the facility burns through the horizon, but another cell stops burning within it: the 1 s
    # lattice is no longer complete for the relaxation, so the refusal is not certified
    ig = quiet(1, 4)
    ig[0, 0, 0] = -100.0
    ig[0, 0, 3] = 9000.0
    ex = np.where(np.isfinite(ig), ig + PERSIST, ig)
    ex[0, 0, 3] = 9500.0
    inst, _ = case()
    ss = make_set(ig, ex, horizon=10_000.0)
    d = one(inst, ss)
    assert d.state is State.UNRESOLVED and d.cause == f"{RELAXATION_INCOMPLETE}:{NO_ROUTE}" and d.unservable == 0
    assert "not certified" in d.detail
    # a contradiction between a checked probe and a route refusal is a bug, never a state
    inst, ss = case(ig_cells=[((0, 1), 500.0)])
    oracle = Oracle(inst, ss)
    probe = oracle.probe_trip("F", 0, 414.0, [
        _drive([eid((0, 0), (0, 1)), eid((0, 1), (0, 2)), eid((0, 2), (0, 3))], 424.0), _unload("S")])
    assert probe.state is State.CHECKED and probe.vehicle == PROBE_VEHICLE
    with pytest.raises(AssertionError):
        oracle.class_deadline("F", 0, probe=probe, board_start_s=414.0, leave_s=424.0, claim=NO_ROUTE)


@pytest.mark.parametrize("seed", range(15))
def test_random_cases_keep_the_three_state_rules(seed):
    inst, ss, _ = random_case(700 + seed)
    ds = class_deadlines(inst, ss)
    assert len(ds) == sum(1 for f in inst.facilities for c in range(3) if f.residents.vector()[c])
    for d in ds:
        assert d.state in (State.CHECKED, State.MODEL_NO_ROUTE, State.UNRESOLVED)
        assert (d.unservable > 0) == (d.state is State.MODEL_NO_ROUTE and d.residents > 0)
        assert d.unservable in (0, d.residents)
        if d.state is State.CHECKED:
            assert d.probe_state is State.CHECKED and d.leave_by_s >= d.arrive_by_s >= d.release_s
            f = next(x for x in inst.facilities if x.id == d.facility)
            c = ["ambulatory", "wheelchair", "bedbound"].index(d.mobility_class)
            assert d.leave_by_s - d.arrive_by_s == f.boarding_s.vector()[c]
        if d.state is State.MODEL_NO_ROUTE:
            assert d.cause.startswith("UNSERVABLE:")
        if d.state is State.UNRESOLVED:
            assert d.unservable == 0
