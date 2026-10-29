"""SIPP versus a brute-force time-expanded search on random small instances, and metamorphic properties.

The equivalence test runs 10,000 Hypothesis cases (environment variable WFG_SIPP_CASES overrides; the derandomised
database-free profile makes the run reproducible). Any mismatch is a SIPP bug until proven otherwise.
"""
import os
import random
import sys
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
from strategies import instances, rebuild  # noqa: E402
from wfg_sipp import bruteforce, predicate, sipp as S  # noqa: E402
from wfg_sipp.intervals import Covered, complement, normalise  # noqa: E402

CASES = int(os.environ.get("WFG_SIPP_CASES", "10000"))
PROFILE = dict(deadline=None, derandomize=True, database=None, suppress_health_check=list(HealthCheck))


def _solve(inst):
    return S.solve(inst)


@settings(max_examples=CASES, **PROFILE)
@given(instances())
def test_sipp_equals_bruteforce_and_returns_a_legal_witness(inst):
    expected = bruteforce.earliest_arrival(inst)
    res = _solve(inst)
    got = res["arrival"] if res["status"] == "FOUND" else None
    assert res["status"] in ("FOUND", "EXHAUSTED")
    assert got == expected
    if got is not None:
        assert bruteforce.check_legs(inst, res["legs"], got)
        member = {"edge_block": inst.edge_block, "wait_block": inst.wait_block}
        assert predicate.safe(inst, res["legs"], got, [member]), predicate.violations(inst, res["legs"], got, [member])


@settings(max_examples=max(200, CASES // 20), **PROFILE)
@given(instances(), st.integers(0, 2**31 - 1))
def test_adding_unsafe_intervals_never_decreases_the_optimal_arrival(inst, seed):
    rng = random.Random(seed)
    base = _solve(inst)
    eb = {j: list(v) for j, v in inst.edge_block.items()}
    for _ in range(rng.randint(1, 4)):
        j = rng.randrange(inst.E)
        a = rng.randint(0, inst.horizon)
        eb.setdefault(j, []).append((a, a + rng.randint(0, 10)))
    more = _solve(rebuild(inst, edge_block=eb))
    if base["status"] != "FOUND":
        assert more["status"] != "FOUND"
    elif more["status"] == "FOUND":
        assert more["arrival"] >= base["arrival"]


@settings(max_examples=max(200, CASES // 20), **PROFILE)
@given(instances(with_members=True))
def test_union_certificate_holds_for_each_member_and_every_subset(case):
    inst, members = case
    res = _solve(inst)
    if res["status"] != "FOUND":
        return
    union = predicate.union_member(members)
    assert predicate.safe(inst, res["legs"], res["arrival"], [union])
    for k in range(len(members)):                    # certified under the union => certified under each member alone
        assert predicate.safe(inst, res["legs"], res["arrival"], [members[k]])
    if len(members) > 1:                             # removing members never makes a certified journey unsafe
        assert predicate.safe(inst, res["legs"], res["arrival"], members[1:])


@settings(max_examples=max(200, CASES // 20), **PROFILE)
@given(instances(), st.integers(1, 50))
def test_shifting_all_times_shifts_the_solution(inst, c):
    sh = lambda ivs: [(a + c, b + c) for a, b in ivs]
    moved = rebuild(inst, departure=inst.departure + c, horizon=inst.horizon + c,
                    edge_block={j: sh(v) for j, v in inst.edge_block.items()},
                    wait_block={n: sh(v) for n, v in inst.wait_block.items()},
                    accept={n: sh(v) for n, v in inst.accept.items()})
    a, b = _solve(inst), _solve(moved)
    assert (a["status"], b["status"]) in (("FOUND", "FOUND"), ("EXHAUSTED", "EXHAUSTED"))
    if a["status"] == "FOUND":
        assert b["arrival"] == a["arrival"] + c


@settings(max_examples=max(200, CASES // 20), **PROFILE)
@given(instances(), st.integers(0, 2**31 - 1))
def test_relabelling_edges_and_nodes_changes_nothing(inst, seed):
    rng = random.Random(seed)
    pe = list(range(inst.E))
    rng.shuffle(pe)                                  # new index of old edge j is pe[j]
    pn = list(range(inst.n_nodes))
    rng.shuffle(pn)
    inv = {pe[j]: j for j in range(inst.E)}
    E = inst.E
    relabel_s = lambda s: E if s == E else pe[s]
    moved = rebuild(inst, tail=[pn[inst.tail[inv[k]]] for k in range(E)], head=[pn[inst.head[inv[k]]] for k in range(E)],
                    D=[inst.D[inv[k]] for k in range(E)], origin=pn[inst.origin], start_state=relabel_s(inst.start_state),
                    forbidden={(relabel_s(s), pe[j]) for s, j in inst.forbidden},
                    waitable=[inst.waitable[pn.index(k)] for k in range(inst.n_nodes)],
                    edge_block={pe[j]: v for j, v in inst.edge_block.items()},
                    wait_block={pn[n]: v for n, v in inst.wait_block.items()}, accept={pn[n]: v for n, v in inst.accept.items()})
    a, b = _solve(inst), _solve(moved)
    assert a["status"] == b["status"] and a["arrival"] == b["arrival"]


@settings(max_examples=500, **PROFILE)
@given(st.lists(st.tuples(st.integers(0, 40), st.integers(0, 8)), max_size=6), st.integers(0, 50), st.integers(0, 50))
def test_interval_complement_and_covered_sets(raw, lo, hi):
    ivs = normalise([(a, a + d) for a, d in raw])
    free = complement(ivs, lo, hi)
    for t in range(min(lo, hi) - 2, max(lo, hi) + 3):
        in_free = any(a <= t <= b for a, b in free)
        assert in_free == (lo <= t <= hi and not any(a <= t <= b for a, b in ivs))
    cov = Covered()
    for a, b in ivs:
        cov.add(a, b)
    assert cov.ivs == ivs
    assert cov.subtract(lo, hi) == free
