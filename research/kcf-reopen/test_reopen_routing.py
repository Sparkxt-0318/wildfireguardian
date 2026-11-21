"""Step 3 (PROTOCOL §4): the deadline field with reopening windows against brute force.

    python3 -m unittest research/kcf-reopen/test_reopen_routing.py -v       (KCF_REOPEN_CASES, default 6000)

Random small road graphs: edges cross 1-3 cells (exact fractions), cells close on [b, r) with r inside the horizon in
at least half of the closed cells. The instance is built by the product's windowed builder
(`engine.build_instance/accept/origin_closure` with `open_s`). Checks per case:
  1. builder: every B_j, W_v, A_j, IB_o equals a second-by-second brute force of PROTOCOL §1.2 (vehicle occupancy
     [t + D z_in, t + D z_out] meets [b, r));
  2. with no reopening the builder equals the unchanged product rule (the pre-change code, copied below);
  3. `core.issue_set` equals `checker.feasible_set` (research/kcf-theorem/checker.py, imports nothing from the repo);
  4. `core.witness` at the first and last second of every feasible interval passes `checker.check_route`.
Writes results/routing_property.json."""
from __future__ import annotations

import json
import os
import random
import sys
import unittest
from collections import Counter
from fractions import Fraction as F
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "product/wfg-roadlayer"))
sys.path.insert(0, str(REPO / "research/kcf-theorem"))
import checker  # noqa: E402
from wfg_roadlayer import engine  # noqa: E402
from wfg_roadlayer.vendor.deadline_field import core  # noqa: E402
from wfg_roadlayer.vendor.deadline_field import intervals as iv  # noqa: E402

N = int(os.environ.get("KCF_REOPEN_CASES", "6000"))


class Road:
    """The RoadModel fields the engine reads."""

    def __init__(self, n, tail, head, D, seg, node_cell, waitable, forbidden):
        self.node_ids = list(range(n))
        self.tail, self.head, self.D, self.seg = tail, head, D, seg
        self.node_cell, self.waitable, self.forbidden = node_cell, waitable, forbidden
        self.inc_by_node = {}
        for j, v in enumerate(head):
            self.inc_by_node.setdefault(v, []).append(j)


def old_build_instance(road, close_s, H):
    """product/wfg-roadlayer engine.build_instance at c437771f, verbatim logic (permanent closures)."""
    B = []
    for j, segs in enumerate(road.seg):
        Dq = F(road.D[j])
        lo = None
        for c, zb in segs:
            b = close_s.get(c)
            if b is None:
                continue
            s = max(engine.ceil_q(F(b) - Dq * zb), 0)
            lo = s if lo is None else min(lo, s)
        B.append([(lo, H)] if lo is not None and lo <= H else [])
    W = []
    for v, c in enumerate(road.node_cell):
        b = close_s.get(c)
        W.append([(max(b - 1, 0), H)] if (road.waitable[v] and b is not None and b - 1 <= H) else [])
    return B, W


def gen(rnd):
    n = rnd.randint(2, 7)
    H = rnd.randint(8, 30)
    ncell = rnd.randint(1, 5)
    E = rnd.randint(1, 12)
    tail, head, D, seg = [], [], [], []
    for _ in range(E):
        u = rnd.randrange(n)
        v = rnd.randrange(n - 1)
        v = v + 1 if v >= u else v
        tail.append(u); head.append(v); D.append(rnd.randint(1, 4))
        k = rnd.randint(1, 3)
        cuts = sorted(F(rnd.randint(1, 7), 8) for _ in range(k - 1)) + [F(1)]
        seg.append([(rnd.randrange(ncell), z) for z in cuts])
    node_cell = [rnd.randrange(ncell) for _ in range(n)]
    waitable = [rnd.random() < 0.4 for _ in range(n)]
    forbidden = {(i, j) for i in range(E) for j in range(E) if head[i] == tail[j] and rnd.random() < 0.15}
    close_s, open_s = {}, {}
    for c in range(ncell):
        if rnd.random() < 0.75:
            b = rnd.randint(0, H + 2)
            close_s[c] = b
            x = rnd.random()
            if x < 0.6:
                open_s[c] = rnd.randint(b + 1, H) if b + 1 <= H else H + 3
            elif x < 0.67:
                open_s[c] = rnd.randint(max(0, b - 3), b)  # empty window
            elif x < 0.75:
                open_s[c] = rnd.randint(H + 1, H + 5)   # reopens after the horizon
    road = Road(n, tail, head, D, seg, node_cell, waitable, forbidden)
    return road, H, close_s, open_s, rnd.randrange(n), rnd.randint(0, 3)


def closed_cell(close_s, open_s, c, H):
    b = close_s.get(c)
    if b is None:
        return None
    r = open_s.get(c)
    if r is not None and r <= H and r <= b:
        return None  # [b, r) is empty
    return (b, None if r is None or r > H else r)


def meets(lo, hi, b, r):
    """[lo, hi] (exact) meets [b, r) (r None = infinity)."""
    return hi >= b and (r is None or lo < r)


def brute_B(road, H, close_s, open_s):
    out = []
    for j, segs in enumerate(road.seg):
        S, zin = set(), F(0)
        for c, zout in segs:
            w = closed_cell(close_s, open_s, c, H)
            if w is not None:
                for t in range(H + 1):
                    if meets(t + road.D[j] * zin, t + road.D[j] * zout, *w):
                        S.add(t)
            zin = zout
        out.append(S)
    return out


def brute_node(road, H, close_s, open_s, v, span):
    w = closed_cell(close_s, open_s, road.node_cell[v], H)
    return set() if w is None else {t for t in range(H + 1) if meets(t, t + span, *w)}


def run(n_cases):
    c = Counter()
    first_fail = None
    for seed in range(n_cases):
        road, H, close_s, open_s, sn, dwell = gen(random.Random("reopen-%d" % seed))
        c["cases"] += 1
        reopen_inside = any(close_s.get(k) is not None and close_s[k] < r <= H for k, r in open_s.items())
        c["cases_with_reopening_inside_H"] += reopen_inside
        inst = engine.build_instance(road, close_s, H, open_s)
        fails = []
        # 1. builder vs brute force
        if [iv.to_set(b) for b in inst.B] != brute_B(road, H, close_s, open_s):
            fails.append("B")
        for v in range(len(road.node_ids)):
            want_w = brute_node(road, H, close_s, open_s, v, 1) if road.waitable[v] else set()
            if iv.to_set(inst.W[v]) != want_w:
                fails.append("W")
            ib = engine.origin_closure(road, close_s, v, H, open_s=open_s)
            if iv.to_set(ib) != brute_node(road, H, close_s, open_s, v, 0):
                fails.append("IB")
        acc = engine.accept(road, close_s, sn, H, dwell, open_s=open_s)
        want_acc = set(range(0, H - dwell + 1)) - brute_node(road, H, close_s, open_s, sn, dwell) if H - dwell >= 0 else set()
        if iv.to_set(acc) != want_acc:
            fails.append("A")
        # 2. no reopening: identical to the unchanged rule
        B0, W0 = old_build_instance(road, close_s, H)
        i0 = engine.build_instance(road, close_s, H)
        if (i0.B, i0.W) != (B0, W0) or engine.build_instance(road, close_s, H, {}).B != B0:
            fails.append("unchanged_rule")
        # 3, 4. field vs brute force, witnesses through the independent checker
        inst.A = [[] for _ in road.tail]
        for j in road.inc_by_node.get(sn, []):
            inst.A[j] = list(acc)
        inst.AN, inst.IB = {}, {}
        fld = core.backward(inst)
        chk = {"H": H, "n_nodes": len(road.node_ids), "edges": [[a, b, d] for a, b, d in zip(road.tail, road.head, road.D)],
               "waitable": [v for v in range(len(road.node_ids)) if road.waitable[v]],
               "forbidden": [list(p) for p in sorted(road.forbidden)],
               "B": {j: [list(p) for p in b] for j, b in enumerate(inst.B)}, "W": {v: [list(p) for p in w] for v, w in enumerate(inst.W)},
               "A": {j: [list(p) for p in a] for j, a in enumerate(inst.A)}, "IB": {}, "AN": {}}
        for o in range(len(road.node_ids)):
            if o == sn:
                continue
            ib = engine.origin_closure(road, close_s, o, H, open_s=open_s)
            inst.IB = {o: ib}
            chk["IB"] = {o: [list(p) for p in ib]}
            m = checker.Model(chk)
            S = core.issue_set(fld, o)
            T = set(checker.feasible_set(m, o))
            c["origins"] += 1
            c["feasible_seconds"] += len(T)
            if iv.to_set(S) != T:
                fails.append("issue_set")
            if len(S) > 1:
                c["origins_with_gap"] += 1
            for lo, hi in S:
                for t in {lo, hi}:
                    w = core.witness(fld, o, t)
                    c["witnesses"] += 1
                    ok, why = (False, "no witness") if w is None else checker.check_route(m, o, t, [[k, x, a, b] for k, x, a, b in w[1]])
                    if not ok:
                        fails.append("witness")
            inst.IB = {}
        for f in set(fails):
            c["fail_" + f] += 1
        if fails and first_fail is None:
            first_fail = {"seed": seed, "fails": sorted(set(fails))}
    return dict(c), first_fail


class ReopenRouting(unittest.TestCase):
    def test_property(self):
        c, first = run(N)
        res = {"cases": c, "first_failure": first, "n_requested": N}
        (HERE / "results").mkdir(exist_ok=True)
        (HERE / "results/routing_property.json").write_text(json.dumps(res, indent=1, sort_keys=True))
        print(json.dumps(res, indent=1, sort_keys=True))
        self.assertIsNone(first, first)
        self.assertGreaterEqual(c["cases"], 5000)
        self.assertGreaterEqual(c["cases_with_reopening_inside_H"], c["cases"] // 2)

    def test_toy_reopen(self):
        """One edge through one cell closed on [2, 6), D = 2, H = 12: departures that meet [2, 6) are refused."""
        road = Road(2, [0], [1], [2], [[(0, F(1))]], [5, 6], [False, False], set())
        inst = engine.build_instance(road, {0: 2}, 12, {0: 6})
        self.assertEqual(inst.B, [[(0, 5)]])
        inst = engine.build_instance(road, {0: 2}, 12)
        self.assertEqual(inst.B, [[(0, 12)]])


if __name__ == "__main__":
    unittest.main()
