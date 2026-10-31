"""Validator: timeline semantics and every issue code, including resources shared by all vehicles."""
import pytest

from evacplan import validate_solution
from evacplan import validate as V
from evacplan_testkit import (
    board, drive, facility, grid_graph, instance, itinerary, nid, path, shelter, solution, unload, vehicle, wait,
)

H = W = 3
A, B, C = (0, 0), (1, 0), (1, 1)


def base(**kw):
    """F at (1,0) with 4 ambulatory, 2 wheelchair, 1 bedbound; S at (1,2); V at depot (0,0)."""
    g = kw.pop("graph", None) or grid_graph(H, W, travel=50.0)
    fac = kw.pop("facilities", None) or [facility("F", nid(1, 0), amb=4, wc=2, bed=1, board=(10, 20, 30))]
    veh = kw.pop("vehicles", None) or [vehicle("V", nid(0, 0), seats=4, wc=1, stretchers=1)]
    shl = kw.pop("shelters", None) or [shelter("S", nid(1, 2), unload=(5, 10, 15))]
    return instance(g, facilities=fac, vehicles=veh, shelters=shl, **kw)


GOOD = [drive(path(A, B), 0), board("F", amb=2), drive(path(B, C, (1, 2)), 70), unload("S", amb=2)]


def codes(report, vehicle=None):
    return sorted((i.code, i.action) for i in report.issues if vehicle is None or i.vehicle == vehicle)


def test_valid_plan_timeline():
    rep = validate_solution(base(), solution(itinerary("V", *GOOD)))
    assert rep.ok
    sch = rep.schedules[0]
    got = [(s.kind, s.t0, s.t1, s.node or s.edge) for s in sch.segments]
    assert got == [("drive", 0.0, 50.0, path(A, B)[0]), ("board", 50.0, 70.0, nid(1, 0)),
                   ("drive", 70.0, 120.0, path(B, C)[0]), ("drive", 120.0, 170.0, path(C, (1, 2))[0]),
                   ("unload", 170.0, 180.0, nid(1, 2))]
    assert sch.spans == [(0.0, 50.0), (50.0, 70.0), (70.0, 170.0), (170.0, 180.0)]
    assert sch.complete and sch.clock_end == 180.0
    assert sch.unloads[0].counts == (2, 0, 0) and sch.unloads[0].by_facility == {"F": (2, 0, 0)}
    assert sch.boarded == {"F": (2, 0, 0)} and sch.onboard_end == {}


def test_idle_before_departure_needs_a_waitable_node_and_is_a_segment():
    # leave the depot at 30 (idle [0, 30]); arrive 80; board [80, 100]; leave at 120 (idle [100, 120])
    acts = [drive(path(A, B), 30), board("F", amb=2), drive(path(B, C, (1, 2)), 120), unload("S", amb=2)]
    rep = validate_solution(base(), solution(itinerary("V", *acts)))
    assert rep.ok
    idle = [(s.action, s.t0, s.t1, s.node) for s in rep.schedules[0].segments if s.kind == "idle"]
    assert idle == [(0, 0.0, 30.0, nid(0, 0)), (2, 100.0, 120.0, nid(1, 0))]
    assert rep.schedules[0].spans[0] == (0.0, 80.0) and rep.schedules[0].spans[2] == (100.0, 220.0)
    strict = base(graph=grid_graph(H, W, travel=50.0, waitable=False))
    assert codes(validate_solution(strict, solution(itinerary("V", *acts)))) == [
        (V.IDLE_NOT_WAITABLE, 0), (V.IDLE_NOT_WAITABLE, 2)]


def test_time_tolerance():
    strict = base(graph=grid_graph(H, W, travel=50.0, waitable=False))
    acts = [drive(path(A, B), 0), board("F", amb=2), drive(path(B, C, (1, 2)), 70 + 1e-7), unload("S", amb=2)]
    rep = validate_solution(strict, solution(itinerary("V", *acts)))
    assert rep.ok                                     # a sub-tolerance gap is no idling ...
    assert [s.kind for s in rep.schedules[0].segments][2] == "idle"   # ... but its time is still occupied
    acts[2] = drive(path(B, C, (1, 2)), 70 - 1e-7)
    assert validate_solution(strict, solution(itinerary("V", *acts))).ok
    acts[2] = drive(path(B, C, (1, 2)), 69.0)
    assert codes(validate_solution(strict, solution(itinerary("V", *acts)))) == [(V.TIME_TRAVEL, 2)]


def test_path_connectivity_and_unknown_edges():
    acts = [drive(path(A, B) + path(C, (1, 2)), 0)]
    rep = validate_solution(base(), solution(itinerary("V", *acts)))
    assert codes(rep) == [(V.DISCONNECTED_PATH, 0)]
    acts = [drive(path(A, B), 0), drive(["nope"], 50), board("F", amb=1)]
    rep = validate_solution(base(), solution(itinerary("V", *acts)))
    assert (V.UNKNOWN_EDGE, 1) in codes(rep) and (V.NOT_UNLOADED, 3) in codes(rep)
    sch = rep.schedules[0]
    assert not sch.complete and sch.spans[1] is None and sch.spans[2] is None and sch.clock_end == 50.0


def test_forbidden_turns_persist_through_waits_and_reset_at_stops():
    u_turn = (path(B, A)[0], path(A, B)[0])
    g = grid_graph(H, W, travel=50.0, forbidden=[u_turn])
    inst = base(graph=g)
    rep = validate_solution(inst, solution(itinerary("V", drive(path(A, B, A, B), 0))))
    assert codes(rep) == [(V.FORBIDDEN_TURN, 0)]
    rep = validate_solution(inst, solution(itinerary("V", drive(path(A, B, A), 0), wait(nid(0, 0), 5),
                                                     drive(path(A, B), 105))))
    assert codes(rep) == [(V.FORBIDDEN_TURN, 2)]      # a roadside wait keeps the heading
    g2 = grid_graph(H, W, travel=50.0, forbidden=[(path(A, B)[0], path(B, A)[0])])
    inst2 = base(graph=g2)
    rep = validate_solution(inst2, solution(itinerary("V", drive(path(A, B), 0), board("F", amb=1),
                                                      drive(path(B, A), 60), drive(path(A, B, C, (1, 2)), 110),
                                                      unload("S", amb=1))))
    assert rep.ok                                     # boarding is a stop: the vehicle may leave either way


def test_waiting_and_location_rules():
    g = grid_graph(H, W, travel=50.0, waitable={A})
    inst = base(graph=g)
    rep = validate_solution(inst, solution(itinerary("V", wait(nid(0, 0), 10), drive(path(A, B), 10),
                                                     wait(nid(1, 0), 10), wait(nid(2, 2), 1), board("F", amb=1),
                                                     drive(path(B, C), 81), unload("S", amb=1))))
    assert codes(rep) == [(V.NOT_WAITABLE, 2), (V.NOT_WAITABLE, 3), (V.WRONG_LOCATION, 3), (V.WRONG_LOCATION, 6)]
    rep = validate_solution(inst, solution(itinerary("V", board("F", amb=1), drive(path(A, B), 0))))
    assert (V.WRONG_LOCATION, 0) in codes(rep)
    rep = validate_solution(inst, solution(itinerary("V", wait("zz", 1))))
    assert codes(rep) == [(V.UNKNOWN_NODE, 0)]


def test_release_time_and_shelter_windows_are_closed_intervals():
    inst = base(facilities=[facility("F", nid(1, 0), amb=4, board=(10, 20, 30), release=60.0)],
                shelters=[shelter("S", nid(1, 2), windows=((0.0, 150.0), (200.0, 300.0)), unload=(5, 10, 15))])
    acts = [drive(path(A, B), 0), board("F", amb=1), drive(path(B, C, (1, 2)), 60), unload("S", amb=1)]
    rep = validate_solution(inst, solution(itinerary("V", *acts)))
    assert codes(rep) == [(V.BEFORE_RELEASE, 1), (V.SHELTER_CLOSED, 3)]   # boards at 50; unloads [160, 165]
    acts = [drive(path(A, B), 10), board("F", amb=1), drive(path(B, C, (1, 2)), 70), unload("S", amb=1)]
    # boards [60, 70] exactly at release; unloads [170, 175] in the gap between windows
    assert codes(validate_solution(inst, solution(itinerary("V", *acts)))) == [(V.SHELTER_CLOSED, 3)]
    acts[2] = drive(path(B, C, (1, 2)), 95)           # unloads [195, 200]: ends at opening, starts before
    assert codes(validate_solution(inst, solution(itinerary("V", *acts)))) == [(V.SHELTER_CLOSED, 3)]
    acts[2] = drive(path(B, C, (1, 2)), 100)          # unloads [200, 205]: inside the second window
    assert validate_solution(inst, solution(itinerary("V", *acts))).ok
    edge = [drive(path(A, B), 10), board("F", amb=1), drive(path(B, C, (1, 2)), 195), unload("S", amb=1)]
    assert validate_solution(inst, solution(itinerary("V", *edge))).ok   # unloads [295, 300]: closed end


@pytest.mark.parametrize("cnt,space,ok", [
    ((4, 0, 0), dict(seats=4, wc=0, stretchers=0), True),
    ((5, 0, 0), dict(seats=4, wc=2, stretchers=1), False),
    ((0, 2, 0), dict(seats=8, wc=1, stretchers=1), False),       # wheelchair users need wheelchair slots
    ((0, 0, 1), dict(seats=8, wc=2, stretchers=0), False),       # bedbound residents need stretchers
    ((2, 2, 1), dict(seats=2, wc=2, stretchers=1), True),
])
def test_per_class_vehicle_space(cnt, space, ok):
    inst = base(facilities=[facility("F", nid(1, 0), amb=5, wc=2, bed=1)],
                vehicles=[vehicle("V", nid(0, 0), **space)])
    acts = [drive(path(A, B), 0), board("F", *cnt)]
    rep = validate_solution(inst, solution(itinerary("V", *acts)))
    assert ((V.VEHICLE_CAPACITY, 1) not in codes(rep)) == ok
    assert (V.NOT_UNLOADED, 2) in codes(rep)


def test_capacity_counts_the_load_across_boardings():
    inst = base(vehicles=[vehicle("V", nid(0, 0), seats=3, wc=0, stretchers=0)])
    acts = [drive(path(A, B), 0), board("F", amb=2), board("F", amb=2)]
    assert (V.VEHICLE_CAPACITY, 2) in codes(validate_solution(inst, solution(itinerary("V", *acts))))
    acts = [drive(path(A, B), 0), board("F", amb=2), drive(path(B, C, (1, 2)), 70), unload("S", amb=2),
            drive(path((1, 2), C, B), 180), board("F", amb=2), drive(path(B, C, (1, 2)), 300), unload("S", amb=2)]
    assert validate_solution(inst, solution(itinerary("V", *acts))).ok


def test_unloading_more_than_on_board_and_leftovers():
    acts = [drive(path(A, B), 0), board("F", amb=1), drive(path(B, C, (1, 2)), 60), unload("S", amb=2)]
    rep = validate_solution(base(), solution(itinerary("V", *acts)))
    assert codes(rep) == [(V.UNLOAD_EXCEEDS_LOAD, 3)]
    assert rep.schedules[0].unloads[0].counts == (1, 0, 0)        # only real residents are moved
    acts = [drive(path(A, B), 0), board("F", amb=2, wc=1), drive(path(B, C, (1, 2)), 90), unload("S", amb=2)]
    rep = validate_solution(base(), solution(itinerary("V", *acts)))
    assert codes(rep) == [(V.NOT_UNLOADED, 4)]
    assert rep.schedules[0].onboard_end == {"F": (0, 1, 0)}


def test_shift_limit_flags_the_first_action_ending_late():
    inst = base(vehicles=[vehicle("V", nid(0, 0), start=0.0, seats=4, shift=100.0)])
    rep = validate_solution(inst, solution(itinerary("V", *GOOD)))
    assert codes(rep) == [(V.SHIFT_LIMIT, 2)]                     # second drive ends at 170
    inst = base(vehicles=[vehicle("V", nid(0, 0), start=0.0, seats=4, shift=180.0)])
    assert validate_solution(inst, solution(itinerary("V", *GOOD))).ok


def two_vehicle_instance(fac_amb=4, cap=(3, 0, 0)):
    return base(facilities=[facility("F", nid(1, 0), amb=fac_amb)],
                vehicles=[vehicle("V1", nid(0, 0), seats=4), vehicle("V2", nid(2, 0), seats=4)],
                shelters=[shelter("S", nid(1, 2), cap=cap)])


def trip(vid, depot, t0, amb):
    first = path(depot, B)
    t_board = t0 + 50
    t_go = t_board + 10 * amb
    return itinerary(vid, drive(first, t0), board("F", amb=amb), drive(path(B, C, (1, 2)), t_go), unload("S", amb=amb))


def test_shelter_capacity_is_shared_first_come_first_served():
    inst = two_vehicle_instance(cap=(3, 0, 0))
    rep = validate_solution(inst, solution(trip("V1", A, 0, 2), trip("V2", (2, 0), 100, 2)))
    assert codes(rep) == [(V.SHELTER_CAPACITY, 3)] and rep.issues[0].vehicle == "V2"
    rep = validate_solution(inst, solution(trip("V1", A, 100, 2), trip("V2", (2, 0), 0, 2)))
    assert codes(rep) == [(V.SHELTER_CAPACITY, 3)] and rep.issues[0].vehicle == "V1"
    assert validate_solution(two_vehicle_instance(cap=(4, 0, 0)),
                             solution(trip("V1", A, 0, 2), trip("V2", (2, 0), 100, 2))).ok


def test_nobody_boards_twice():
    inst = two_vehicle_instance(fac_amb=3, cap=(10, 0, 0))
    rep = validate_solution(inst, solution(trip("V1", A, 0, 2), trip("V2", (2, 0), 100, 2)))
    assert codes(rep) == [(V.OVERBOARDED, 1)] and rep.issues[0].vehicle == "V2"


def test_unknown_and_duplicate_vehicles():
    inst = two_vehicle_instance()
    rep = validate_solution(inst, solution(trip("V1", A, 0, 1), trip("V1", A, 300, 1), itinerary("X")))
    assert [(i.code, i.itinerary) for i in rep.issues] == [(V.DUPLICATE_ITINERARY, 1), (V.UNKNOWN_VEHICLE, 2)]
    assert not rep.schedules[1].known and not rep.schedules[2].known
    assert rep.schedules[1].segments == [] and rep.schedules[0].known


def test_unloading_is_first_in_first_out_per_class():
    g = grid_graph(H, W, travel=50.0)
    inst = instance(g, facilities=[facility("F1", nid(1, 0), amb=3), facility("F2", nid(1, 1), amb=3)],
                    vehicles=[vehicle("V", nid(0, 0), seats=8)], shelters=[shelter("S", nid(1, 2))])
    acts = [drive(path(A, B), 0), board("F1", amb=2), drive(path(B, C), 70), board("F2", amb=3),
            drive(path(C, (1, 2)), 150), unload("S", amb=3), unload("S", amb=2)]
    rep = validate_solution(inst, solution(itinerary("V", *acts)))
    assert rep.ok
    u1, u2 = rep.schedules[0].unloads
    assert u1.by_facility == {"F1": (2, 0, 0), "F2": (1, 0, 0)} and u2.by_facility == {"F2": (2, 0, 0)}
