"""Tests for the F-BASE solvers (run: python -m pytest research/harness-2026-11/F-BASE/tests -q)."""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fbase import (Instance, instance_text, parse_instance, replay, solve_brute, solve_exact,  # noqa: E402
                   solve_n1, solve_n2, solve_n3)


def make(nV, edges, *, dep=0, H=20, origin=0, waitable=(), forbid=(), EB=None, WB=None, AC=None):
    tail = [a for a, _, _ in edges]
    head = [b for _, b, _ in edges]
    D = [d for _, _, d in edges]
    return Instance(nV, len(edges), dep, H, origin, len(edges), tail, head, D, set(waitable), set(forbid),
                    EB or {}, WB or {}, AC or {})


def random_instance(rng, nV=5, nE=8, H=25):
    edges = []
    for _ in range(nE):
        a, b = rng.randrange(nV), rng.randrange(nV)
        if a == b:
            b = (a + 1) % nV
        edges.append((a, b, rng.randint(1, 5)))
    def ivs():
        out, t = [], rng.randint(0, 6)
        while t < H and rng.random() < 0.7:
            w = rng.randint(0, 5)
            out.append((t, min(H, t + w)))
            t += w + 2 + rng.randint(0, 5)
        return out
    EB = {j: v for j in range(nE) if rng.random() < 0.6 and (v := ivs())}
    waitable = {n for n in range(nV) if rng.random() < 0.5}
    WB = {n: v for n in waitable if rng.random() < 0.4 and (v := ivs())}
    dest = rng.randrange(1, nV)
    AC = {dest: ivs() or [(0, H)]}
    forbid = {(s, j) for s in range(nE + 1) for j in range(nE) if rng.random() < 0.05}
    return make(nV, edges, H=H, waitable=waitable, forbid=forbid, EB=EB, WB=WB, AC=AC,
                dep=rng.randint(0, 3))


def test_exact_equals_brute_force_and_witnesses_replay():
    rng = random.Random(0)
    routes = 0
    for _ in range(1500):
        inst = random_instance(rng)
        claim, T, wit = solve_exact(inst)
        assert (claim, T) == solve_brute(inst), instance_text(inst)
        if claim == "ROUTE":
            routes += 1
            assert replay(inst, wit, T), instance_text(inst)
    assert routes > 200


def test_parse_roundtrip():
    rng = random.Random(1)
    for _ in range(50):
        inst = random_instance(rng)
        again = parse_instance(instance_text(inst))
        assert instance_text(again) == instance_text(inst)
        assert solve_exact(again)[:2] == solve_exact(inst)[:2]


def test_nonwaitable_node_needs_later_arrival_n2_incomplete():
    # 0 -(1)-> 1 (non-waitable) -(1)-> 2 (dest). Edge 1->2 blocked at second 1, so arriving at 1 at t=1 is a
    # dead end. A slower parallel edge 0 -(2)-> 1 arrives at t=2 and can depart. One earliest label at the
    # state "arrived via edge 0" cannot see this, but state = incoming edge separates them... so make both
    # arrivals use the SAME incoming edge by waiting at the waitable origin.
    inst = make(3, [(0, 1, 1), (1, 2, 1)], waitable={0}, EB={1: [(1, 1)]}, AC={2: [(0, 20)]})
    assert solve_exact(inst)[:2] == ("ROUTE", 3) == solve_brute(inst)
    # N2 keeps only the earliest label of state 0 (t=1) at the non-waitable node and finds no departure.
    assert solve_n2(inst) == ("NO_ROUTE", None)


def test_waiting_at_nonwaitable_node_n1_unsound():
    # Only route needs waiting at non-waitable node 1: edge 1->2 blocked during [1, 5].
    inst = make(3, [(0, 1, 1), (1, 2, 1)], waitable=set(), EB={1: [(1, 5)]}, AC={2: [(0, 20)]})
    assert solve_exact(inst)[:2] == ("NO_ROUTE", None) == solve_brute(inst)
    assert solve_n1(inst) == ("ROUTE", 7)


def test_acceptance_window_n3_early():
    inst = make(2, [(0, 1, 2)], waitable={0}, AC={1: [(5, 9)]})
    assert solve_exact(inst)[:2] == ("ROUTE", 5) == solve_brute(inst)
    assert solve_n3(inst) == ("ROUTE", 2)
