"""The stop-sequence realizer shared by B2 and B3: ASAP replay on the POSITIVE masks, units dropped at an
impossible boarding, re-realization after an impossible unloading, skipped stops, merged actions. Every
realized plan must pass the validator. SYNTHETIC hand-built instances."""
import pytest

from evacplan import Oracle, State, validate_solution
from evacplan.methods.realize import BOARD, UNLOAD, Realizer, Sequence, Stop, Unit
from evacplan.reach import Reach
from evacplan_testkit import eid, facility, grid_graph, instance, make_set, nid, quiet, shelter, vehicle


def line(*, release_b=0.0, shift=None, cap_s=(100, 100, 100), uturns_forbidden=False):
    """1 x 5 road, 50 s per edge: van at n0_4 (shelter S), A at n0_0, B at n0_2, nothing burns."""
    forb = []
    if uturns_forbidden:
        for c in range(4):
            a, b = (0, c), (0, c + 1)
            forb += [(eid(a, b), eid(b, a)), (eid(b, a), eid(a, b))]
    inst = instance(grid_graph(1, 5, forbidden=forb),
                    facilities=[facility("A", nid(0, 0), amb=3), facility("B", nid(0, 2), amb=2, release=release_b)],
                    vehicles=[vehicle("V", nid(0, 4), seats=4, shift=shift)], shelters=[shelter("S", nid(0, 4), cap=cap_s)])
    return inst, make_set(quiet(1, 5), horizon=5000.0)


def board(fid):
    return Stop(nid(0, 0) if fid == "A" else nid(0, 2), ((BOARD, fid),))


S = Stop(nid(0, 4), ((UNLOAD, "S"),))


def test_asap_replay_is_valid_and_checked():
    inst, ss = line()
    seq = Sequence("V", [board("A"), board("B"), S], [Unit("A", 0, 2, 0, ((2, "S", 2),)), Unit("B", 0, 2, 1, ((2, "S", 2),))])
    real = Realizer(inst, Reach(inst, ss)).realize([seq])
    sol = real.solution(inst, "test")
    assert validate_solution(inst, sol).ok
    plan = Oracle(inst, ss).check_plan(sol)
    assert plan.delivered_total == 4 and all(t.state is State.CHECKED for v in plan.vehicles for t in v.trips)
    acts = sol.itineraries[0].actions
    assert [a.kind for a in acts] == ["drive", "board", "drive", "board", "drive", "unload"]
    assert acts[0].depart_s == 0.0 and acts[2].depart_s == 200.0 + 20.0      # leaves A right after boarding 2 x 10 s
    assert real.vehicles["V"].kept == {0, 1} and real.vehicles["V"].restarts == 0


def test_impossible_boarding_drops_its_units_and_skips_the_stop():
    """B releases its residents only after the van's shift has ended: B's unit is dropped, the van does not
    even drive to B (a stop without an action would keep the heading and could make a forbidden U-turn)."""
    inst, ss = line(release_b=2000.0, shift=1000.0, uturns_forbidden=True)
    seq = Sequence("V", [board("B"), board("A"), S], [Unit("B", 0, 2, 0, ((2, "S", 2),)), Unit("A", 0, 3, 1, ((2, "S", 3),))])
    real = Realizer(inst, Reach(inst, ss)).realize([seq])
    vp = real.vehicles["V"]
    assert vp.kept == {1} and set(vp.dropped) == {0} and "boarding" in vp.dropped[0]
    sol = real.solution(inst, "test")
    assert validate_solution(inst, sol).ok
    assert [a.facility for a in sol.itineraries[0].actions if a.kind == "board"] == ["A"]
    assert Oracle(inst, ss).check_plan(sol).delivered_total == 3


def test_impossible_unloading_restarts_without_those_units():
    """The shelter takes only 2 ambulatory residents: the unloading of 4 fails after both boardings, so the
    vehicle is realized again without the units of that unloading; a later trip with 2 still fits."""
    inst, ss = line(cap_s=(2, 0, 0))
    units = [Unit("A", 0, 2, 0, ((2, "S", 2),)), Unit("B", 0, 2, 1, ((2, "S", 2),)), Unit("A", 0, 1, 3, ((4, "S", 1),))]
    seq = Sequence("V", [board("A"), board("B"), S, board("A"), S], units)
    real = Realizer(inst, Reach(inst, ss)).realize([seq])
    vp = real.vehicles["V"]
    assert vp.restarts == 1 and set(vp.dropped) == {0, 1} and "full" in vp.dropped[0]
    sol = real.solution(inst, "test")
    assert validate_solution(inst, sol).ok and Oracle(inst, ss).check_plan(sol).delivered_total == 1
    assert real.summary([seq]) == {"residents_planned": 5, "residents_realized": 1,
                                   "residents_dropped": {"shelter full": 4}, "restarts": 1}


def test_consecutive_boardings_merge_and_units_are_checked():
    inst, ss = line()
    seq = Sequence("V", [board("A"), board("A"), S], [Unit("A", 0, 1, 0, ((2, "S", 1),)), Unit("A", 0, 2, 1, ((2, "S", 2),))])
    sol = Realizer(inst, Reach(inst, ss)).realize([seq]).solution(inst, "test")
    assert [(a.kind, a.counts.ambulatory if a.kind != "drive" else None) for a in sol.itineraries[0].actions] == \
        [("drive", None), ("board", 3), ("drive", None), ("unload", 3)]
    with pytest.raises(ValueError):
        Unit("A", 0, 2, 1, ((1, "S", 2),))              # an unloading before the boarding
    with pytest.raises(ValueError):
        Unit("A", 0, 2, 0, ((1, "S", 1),))              # residents lost on the way
