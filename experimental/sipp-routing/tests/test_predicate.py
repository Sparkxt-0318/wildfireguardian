"""Each clause of the journey-safety predicate (docs/JOURNEY_SAFETY_PREDICATE.md) is detected: a valid journey passes,
and one targeted mutation per requirement identifier makes exactly that identifier appear."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wfg_sipp import predicate as P, sipp as S  # noqa: E402


def inst():
    # nodes 0 -> 1 -> 2 (edges 0, 1), bypass 0 -> 2 (edge 2); node 1 waitable; destination 2 accepts [5, 50]
    return S.make_instance(n_nodes=3, tail=[0, 1, 0], head=[1, 2, 2], D=[3, 4, 20], origin=0, start_state=3,
                           forbidden={(2, 1)}, waitable=[False, True, False], edge_block={}, wait_block={},
                           accept={2: [(5, 50)]}, departure=0, horizon=60)


GOOD = [("EDGE", 0, 0, 3), ("WAIT", 1, 3, 4), ("EDGE", 1, 4, 8)]


def ids(v):
    return {r for r, _, _ in v}


def test_valid_journey_passes():
    assert P.safe(inst(), GOOD, 8, [{}], peak_limit=10, dose_budget=100)


def test_each_requirement_is_detected():
    I = inst()
    cases = {
        "JS-1": ([("EDGE", 0, 1, 4), ("EDGE", 1, 4, 8)], 8, [{}]),
        "JS-2": ([("EDGE", 0, 0, 3), ("EDGE", 1, 4, 8)], 8, [{}]),
        "JS-3": ([("EDGE", 0, 0, 3), ("WAIT", 1, 3, 3), ("EDGE", 1, 3, 7)], 7, [{}]),
        "JS-4": ([("EDGE", 0, 0, 2), ("EDGE", 1, 2, 6)], 6, [{}]),
        "JS-5": ([("EDGE", 1, 0, 4)], 4, [{}]),
        "JS-6": ([("WAIT", 0, 0, 1), ("EDGE", 0, 1, 4), ("EDGE", 1, 4, 8)], 8, [{}]),
        "JS-7": (GOOD, 8, [{"wait_block": {1: [(3, 3)]}}]),
        "JS-8": (GOOD, 8, [{"edge_block": {1: [(4, 4)]}}]),
        "JS-9": (GOOD, 8, [{"edge_flux": {0: 11}}]),
        "JS-10": (GOOD, 8, [{"edge_flux": {0: 5}, "incurred": 90}]),
        "JS-11": ([("EDGE", 0, 0, 3)], 3, [{}]),
        "JS-12": (GOOD, 8, [{"issue_contact": True}]),
    }
    for rid, (legs, arrival, members) in cases.items():
        found = ids(P.violations(I, legs, arrival, members, peak_limit=10, dose_budget=100))
        assert rid in found, (rid, found)
    assert set(cases) == set(P.REQUIREMENTS)


def test_dwell_dose_counts_only_when_requested():
    I = inst()
    m = [{"dwell_flux": {2: 1}}]
    assert "JS-10" in ids(P.violations(I, GOOD, 8, m, dose_budget=100, dwell_s=150, include_dwell=True))
    assert "JS-10" not in ids(P.violations(I, GOOD, 8, m, dose_budget=100, dwell_s=150, include_dwell=False))


def test_sipp_witness_satisfies_the_predicate_and_union_rule():
    I = inst()
    members = [{"edge_block": {1: [(0, 6)]}}, {"wait_block": {1: [(3, 9)]}}]
    union = P.union_member(members)
    I2 = S.make_instance(n_nodes=3, tail=I.tail, head=I.head, D=I.D, origin=0, start_state=3, forbidden=I.forbidden,
                         waitable=I.waitable, edge_block=union["edge_block"], wait_block=union["wait_block"],
                         accept=I.accept, departure=0, horizon=60)
    r = S.solve(I2)
    assert r["status"] == "FOUND"
    assert P.safe(I2, r["legs"], r["arrival"], members)
    assert P.safe(I2, r["legs"], r["arrival"], [union])
