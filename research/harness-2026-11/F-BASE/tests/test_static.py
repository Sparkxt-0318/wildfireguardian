"""S1/S2 static-snapshot baselines and the no-re-entry reading (fbase_static)."""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fbase import replay, solve_brute, solve_exact  # noqa: E402
from fbase_static import no_reentry, solve_static, static_instance  # noqa: E402
from test_fbase import make, random_instance  # noqa: E402


def test_s1_unsound_when_edge_burns_after_departure():
    # 0 -(2)-> 1 -(2)-> 2. Edge 1 (1->2) is blocked during [1, 6]: free at departure, burning when reached.
    inst = make(3, [(0, 1, 2), (1, 2, 2)], waitable=set(), EB={1: [(1, 6)]}, AC={2: [(0, 20)]})
    assert solve_exact(inst)[:2] == ("NO_ROUTE", None)
    claim, T, wit = solve_static(inst, "S1")
    assert (claim, T) == ("ROUTE", 4)
    assert not replay(inst, wit, T)  # the S1 route is illegal in the true instance


def test_s2_refuses_when_block_is_avoidable():
    # Edge 1 is blocked only during [0, 1]; waiting at node 1 lets the route through after the block.
    inst = make(3, [(0, 1, 2), (1, 2, 2)], waitable={1}, EB={1: [(0, 1)]}, AC={2: [(0, 20)]})
    assert solve_exact(inst)[:2] == ("ROUTE", 4)
    assert solve_static(inst, "S2")[:2] == ("NO_ROUTE", None)


def test_no_reentry_closes_blocks_to_horizon():
    inst = make(3, [(0, 1, 2), (1, 2, 2)], waitable={1}, EB={1: [(3, 4), (8, 9)]}, WB={1: [(5, 5)]},
                AC={2: [(0, 20)]}, H=20)
    nr = no_reentry(inst)
    assert nr.EB == {1: [(3, 20)]} and nr.WB == {1: [(5, 20)]}
    # reopening: depart edge 1 at t=2 (before the block) -> T=4; no-re-entry agrees here, and after the block opens
    # again (t>=10) reopening would allow it while no-re-entry never does.
    assert solve_exact(nr)[:2] == ("ROUTE", 4)


def test_static_instances_are_exact_on_their_own_instance():
    rng = random.Random(3)
    for _ in range(400):
        inst = random_instance(rng)
        for mode in ("S1", "S2"):
            si = static_instance(inst, mode)
            assert solve_static(inst, mode)[:2] == solve_brute(si)
        nr = no_reentry(inst)
        assert solve_exact(nr)[:2] == solve_brute(nr)


def test_s3_large_delta_equals_executing_s1_plan():
    from fbase_static import solve_s3
    rng = random.Random(11)
    for _ in range(600):
        inst = random_instance(rng)
        out, T, legs, _ = solve_s3(inst, delta=10 ** 9)
        s1 = solve_static(inst, "S1")
        if s1[0] == "NO_ROUTE":
            assert out == "REFUSED"
        elif replay(inst, s1[2], s1[1]):
            assert (out, T) == ("ROUTE", s1[1])
        else:
            assert out == "VIOLATION"


def test_s3_legal_routes_replay_and_never_beat_exact():
    from fbase_static import solve_s3
    rng = random.Random(12)
    seen = set()
    for _ in range(600):
        inst = random_instance(rng)
        ex = solve_exact(inst)
        for d in (1, 3, 7):
            out, T, legs, _ = solve_s3(inst, delta=d)
            seen.add(out)
            assert out != "UNRESOLVED", inst
            if out == "ROUTE":
                assert replay(inst, legs, T)
                assert ex[0] == "ROUTE" and T >= ex[1]
    assert {"ROUTE", "VIOLATION", "REFUSED"} <= seen


def test_s3_replanning_avoids_a_fire_s1_walks_into():
    from fbase_static import solve_s3
    # 0 -(2)-> 1 (not waitable); from 1 two edges to 2: A (D=2) blocked [2, 6], B (D=5) never blocked.
    # S1 at t=0 sees A free and takes it, departing at t=2 -> VIOLATION. S3 with delta=2 re-plans at node 1 (t=2) on a
    # fresh snapshot, where A is blocked for the whole horizon (rule (e)), and takes B -> arrives at 7 = exact.
    inst = make(3, [(0, 1, 2), (1, 2, 2), (1, 2, 5)], waitable=set(), EB={1: [(2, 6)]}, AC={2: [(0, 20)]})
    assert solve_exact(inst)[:2] == ("ROUTE", 7)
    assert solve_s3(inst, delta=10 ** 9)[0] == "VIOLATION"
    assert solve_s3(inst, delta=2)[:2] == ("ROUTE", 7)


def test_s3_snapshot_blocks_whole_horizon_so_s3_can_refuse_where_exact_waits():
    from fbase_static import solve_s3
    # Single edge A from waitable node 1, blocked [2, 6]: exact waits at 1 and departs at 7 (T=9). A re-plan at t=2
    # sees A blocked in the snapshot for the whole horizon and refuses (rule (e): S1 snapshot semantics).
    inst = make(3, [(0, 1, 2), (1, 2, 2)], waitable={1}, EB={1: [(2, 6)]}, AC={2: [(0, 20)]})
    assert solve_exact(inst)[:2] == ("ROUTE", 9)
    assert solve_s3(inst, delta=2)[0] == "REFUSED"
