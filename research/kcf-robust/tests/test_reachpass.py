"""Brute-force checks of the compiled pass and the dilation (PROTOCOL.md section 4).

Random small road instances with random cell closures. The brute force is a forward search over every (edge state,
second) using the physical rule of research/kcf-replay (an edge entered at t is blocked if t + D * z_end >= b for one
of its segments; a wait at v from t is blocked if t + 1 >= b of v's cell; departure blocked if t >= b of the origin
cell; arrival a accepted if a <= H - dwell and a + dwell < b of the shelter cell; every move ends by H). It does not
use intervals, the engine or the pass. Checked: latest departure per (shelter, origin) and, over a ladder of nested
closure levels (dilations of a random raster), the largest level with a safe departure.

    python3 -m unittest research/kcf-robust/tests/test_reachpass.py -v
"""
from __future__ import annotations

import math
import random
import sys
import unittest
from fractions import Fraction as F
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import lib  # noqa: E402
import reachpass as RP  # noqa: E402
from wfg_roadlayer import engine  # noqa: E402
from wfg_roadlayer.vendor.deadline_field import core  # noqa: E402

N_CASES = int(__import__('os').environ.get('KCF_ROBUST_CASES', '2000'))


class FakeRoad:
    def __init__(self, rng, n_nodes, n_edges, n_cells):
        self.node_ids = list(range(n_nodes))
        self.tail, self.head, self.D, self.seg = [], [], [], []
        while len(self.tail) < n_edges:
            u, v = rng.randrange(n_nodes), rng.randrange(n_nodes)
            if u == v:
                continue
            self.tail.append(u); self.head.append(v); self.D.append(rng.randint(1, 6))
            k = rng.randint(1, 3)
            ends = sorted(F(rng.randint(1, 9), 9) for _ in range(k - 1)) + [F(1)]
            self.seg.append([(rng.randrange(n_cells), e) for e in ends])
        self.waitable = [rng.random() < 0.5 for _ in range(n_nodes)]
        self.node_cell = [rng.randrange(n_cells) for _ in range(n_nodes)]
        self.inc_by_node, self.out_by_node = {}, {}
        for j, (u, v) in enumerate(zip(self.tail, self.head)):
            self.inc_by_node.setdefault(v, []).append(j)
            self.out_by_node.setdefault(u, []).append(j)
        self.forbidden = set()
        for j in range(n_edges):
            for i in self.inc_by_node.get(self.tail[j], []):
                if rng.random() < 0.25:
                    self.forbidden.add((i, j))


class FakeRegion:
    def __init__(self, road, origins, shelters_by_origin):
        self.road = road
        self.origins = [{"id": "o%d" % o, "node": o, "checkable": True} for o in origins]
        self.cands = {"o%d" % o: [{"node": s} for s in shelters_by_origin[o]] for o in origins}


def brute_feasible(road, close, o, sn, t, H, dwell):
    """Forward search over (edge state, second); state -1 = at the origin before any move."""
    def blocked_edge(j, tt):
        for c, z in road.seg[j]:
            b = close.get(c)
            if b is not None and tt + road.D[j] * z >= b:
                return True
        return False

    bo = close.get(road.node_cell[o])
    if bo is not None and t >= bo:
        return False
    bs = close.get(road.node_cell[sn])
    seen = set()
    stack = [(-1, o, t)]
    while stack:
        s, v, tt = stack.pop()
        if (s, v, tt) in seen:
            continue
        seen.add((s, v, tt))
        for j in road.out_by_node.get(v, []):
            if s >= 0 and (s, j) in road.forbidden:
                continue
            a = tt + road.D[j]
            if a > H or blocked_edge(j, tt):
                continue
            if road.head[j] == sn and a <= H - dwell and (bs is None or a + dwell < bs):
                return True
            stack.append((j, road.head[j], a))
        if road.waitable[v] and tt + 1 <= H:
            bv = close.get(road.node_cell[v])
            if not (bv is not None and tt + 1 >= bv):
                stack.append((s, v, tt + 1))
    return False


def brute_latest(road, close, o, sn, H, dwell):
    L = -1
    for t in range(H + 1):
        if brute_feasible(road, close, o, sn, t, H, dwell):
            L = t
    return L


def engine_latest(road, close, o, sn, H, dwell):
    inst = engine.build_instance(road, close, H)
    inst.A = [[] for _ in range(len(road.tail))]
    for j in road.inc_by_node.get(sn, []):
        inst.A[j] = engine.accept(road, close, sn, H, dwell)
    fld = core.backward(inst)
    inst.IB = {o: engine.origin_closure(road, close, o, H)}
    S = core.issue_set(fld, o)
    return S


class TestReachPass(unittest.TestCase):
    def test_random_instances(self):
        rng = random.Random(20261119)
        n_pairs = n_levels = n_feas = 0
        for case in range(N_CASES):
            n_cells = rng.randint(2, 9)
            road = FakeRoad(rng, rng.randint(3, 7), rng.randint(4, 14), n_cells)
            H = rng.randint(8, 30)
            dwell = rng.randint(0, 3)
            # nested levels: base closures, then each level closes some cells earlier (like a growing dilation)
            base = {c: rng.randint(0, H + 5) for c in range(n_cells) if rng.random() < 0.6}
            levels = [dict((c, b) for c, b in base.items() if b <= H)]
            cur = dict(base)
            for _ in range(rng.randint(1, 4)):
                for c in range(n_cells):
                    if rng.random() < 0.4:
                        cur[c] = max(0, min(cur.get(c, H + 5), rng.randint(0, H + 5)) - rng.randint(0, 4))
                levels.append(dict((c, b) for c, b in cur.items() if b <= H))
            nodes = list(range(len(road.node_ids)))
            o = rng.choice(nodes)
            shel = [s for s in nodes if s != o]
            rng.shuffle(shel)
            region = FakeRegion(road, [o], {o: shel[:rng.randint(1, 2)]})
            g = RP.Graph(road)
            closes = np.stack([RP.close_array(lv, n_cells) for lv in levels])
            best, raw, pairs = RP.latest_by_level(g, region, closes, H, dwell)
            brute_best = []
            for k, lv in enumerate(levels):
                bl = -1
                for m, (oid, sn) in enumerate(pairs):
                    want = brute_latest(road, lv, o, sn, H, dwell)
                    got = raw[k, m]
                    self.assertEqual(got, want, "case %d level %d shelter %d" % (case, k, sn))
                    S = engine_latest(road, lv, o, sn, H, dwell)
                    self.assertEqual(-1 if not S else S[-1][1], want, "engine vs brute, case %d" % case)
                    if S:
                        self.assertEqual(S[0][0], 0, "feasible set not downward closed")
                        self.assertEqual(len(S), 1, "feasible set not one interval")
                    bl = max(bl, want)
                    n_pairs += 1
                self.assertEqual(best["o%d" % o][k], bl)
                brute_best.append(bl)
                n_feas += bl >= 0
                n_levels += 1
            # largest level index with a safe departure (the tolerance read-off)
            tol_brute = max([k for k in range(len(levels)) if brute_best[k] >= 0], default=-1)
            tol_pass = max([k for k in range(len(levels)) if best["o%d" % o][k] >= 0], default=-1)
            self.assertEqual(tol_brute, tol_pass)
        print("random instances", N_CASES, "pair-levels", n_pairs, "levels", n_levels, "levels with a safe departure", n_feas)

    def test_dilation(self):
        rng = np.random.default_rng(7)
        cx, cy = lib.cell_centres()
        for _ in range(30):
            m = np.full(lib.HH * lib.W, np.inf)
            idx = rng.choice(m.size, 40, replace=False)
            m[idx] = rng.uniform(0, 480, 40)
            r = float(rng.choice([0.2, 0.375, 0.5, 0.75, 1.0, 1.3, 2.0]))
            got = lib.dilate_minutes(m, r)
            # brute force over the finite cells
            want = m.copy()
            for k in idx:
                dd = np.hypot(cx - cx[k], cy - cy[k]) <= r * 1000.0 + 1e-6
                want = np.where(dd, np.minimum(want, m[k]), want)
            self.assertTrue(np.array_equal(got, want), r)


if __name__ == "__main__":
    unittest.main()
