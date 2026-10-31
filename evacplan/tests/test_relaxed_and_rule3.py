"""The RELAXED check (never a final state) and ground rule 3 (only evacplan.oracle declares states)."""
import re
from pathlib import Path

import numpy as np

from evacplan import RelaxedContactCheck, RelaxedItinerary, RelaxedLeg, State
from evacplan_testkit import NAN, drive, grid_graph, instance, itinerary, make_set, nid, path, quiet, vehicle, wait

SRC = Path(__file__).resolve().parents[1] / "src" / "evacplan"


def checker(ig, **kw):
    ss = make_set(ig, **kw)
    inst = instance(grid_graph(3, 3), vehicles=[vehicle("V", nid(1, 0))])
    return RelaxedContactCheck(inst, ss)


def test_relaxed_legs():
    ig = quiet(3, 3)
    ig[0, 1, 1] = 50.0
    ig[0, 0, 0] = NAN
    rc = checker(ig, horizon=1000.0)
    e = path((1, 0), (1, 1))[0]                 # in the middle cell during [25, 50] after departure
    assert rc.traverse(e, 0.0) == RelaxedLeg(blocked=True, uncertain=False)
    assert rc.traverse(e, -30.0) == RelaxedLeg(blocked=False, uncertain=False)
    assert rc.stay(nid(0, 0), 0.0, 10.0) == RelaxedLeg(blocked=False, uncertain=True)   # unknown: not blocked
    assert rc.stay(nid(2, 2), 990.0, 1001.0) == RelaxedLeg(blocked=False, uncertain=True)


def test_relaxed_itinerary_stops_at_the_first_blocked_leg_and_lists_issues():
    ig = quiet(3, 3)
    ig[0, 1, 1] = 0.0
    rc = checker(ig)
    it = itinerary("V", wait(nid(1, 0), 5.0), drive(path((1, 0), (1, 1), (1, 2)), 5.0), wait(nid(2, 2), 1.0))
    out = rc.itinerary(it)
    assert isinstance(out, RelaxedItinerary)
    assert out.first_blocked == 1 and len(out.legs) == 2
    full = rc.itinerary(it, stop_at_block=False)
    assert len(full.legs) == 4 and [c.code for c in full.issues] == ["WRONG_LOCATION"]


def test_relaxed_results_carry_no_final_state():
    rc = checker(quiet(3, 3))
    leg = rc.stay(nid(1, 1), 0.0, 1.0)
    out = rc.itinerary(itinerary("V", wait(nid(1, 0), 1.0)))
    for obj in (leg, out):
        assert not isinstance(obj, State)
        assert not any(isinstance(v, State) for v in vars(obj).values())
        assert "state" not in vars(obj)


def test_only_the_oracle_declares_final_states():
    """Program rule 3: no other module may construct states or oracle results (reading them is fine)."""
    declare = re.compile(r"State\(|=\s*State\.|\b(LegResult|ActionResult|TripResult|ItineraryResult|PlanResult)\(")
    offenders = []
    for f in sorted(SRC.rglob("*.py")):
        if f.name == "oracle.py":
            continue
        for i, line in enumerate(f.read_text().splitlines(), 1):
            if declare.search(line):
                offenders.append(f"{f.relative_to(SRC)}:{i}: {line.strip()}")
    assert not offenders, offenders
    assert declare.search((SRC / "oracle.py").read_text())        # the pattern does match the oracle itself
