"""Dose model (kcf_heat/dose.py) on a real frozen packet against independent sampled bounds (kcf_heat/dose_check.py).

Needs the frozen routing inputs at $WFG_ROUTING_DATA or <repo>/data/routing; skipped otherwise.
"""
import math
import os
import random
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from kcf_heat.closure import HeatPacketModel, ROOT  # noqa: E402
from kcf_heat.dose import RLE, DoseModel, max_rle, rle_from_dense, seg_rect_dist  # noqa: E402
from kcf_heat.dose_check import DoseBounds  # noqa: E402

DATA = Path(os.environ.get("WFG_ROUTING_DATA", ROOT / "data" / "routing"))
REGION, TAG = "uiseong_andong_2025", "20250324T090000Z"
PACKET = DATA / "latest_inputs_try02" / "packets" / REGION / TAG
GRAPH = DATA / "graphs" / REGION / "graph.json"
needs_data = pytest.mark.skipif(not (PACKET.is_dir() and GRAPH.is_file()), reason="frozen routing inputs not present")


def test_helpers():
    assert max_rle([(0, 4, 2), (3, 9, 5), (12, 12, 1)]) == [(0, 2, 2), (3, 9, 5), (12, 12, 1)]
    assert rle_from_dense(np.array([0, 3, 3, 0, 1])) == [(1, 2, 3), (4, 4, 1)]
    r = RLE([(2, 4, 7), (9, 9, 1)])
    assert r.split(0, 10) == [(0, 1, 0), (2, 4, 7), (5, 8, 0), (9, 9, 1), (10, 10, 0)]
    assert [r.at(t) for t in (1, 2, 4, 5, 9)] == [0, 7, 7, 0, 1]
    rnd = random.Random(1)
    for _ in range(2000):
        rect = (0.0, 10.0, 0.0, 5.0)
        p = [rnd.uniform(-20, 30) for _ in range(4)]
        d = float(seg_rect_dist([p[0]], [p[1]], [p[2]], [p[3]], rect)[0])
        z = np.linspace(0, 1, 4001)
        X, Y = p[0] + z * (p[2] - p[0]), p[1] + z * (p[3] - p[1])
        ds = np.hypot(np.maximum.reduce([0 - X, 0 * X, X - 10]), np.maximum.reduce([0 - Y, 0 * Y, Y - 5])).min()
        step = math.hypot(p[2] - p[0], p[3] - p[1]) / 4000
        assert d <= ds + 1e-9 and d >= ds - step / 2 - 1e-9


@pytest.fixture(scope="module")
def models():
    pm = HeatPacketModel(GRAPH, PACKET)
    dm = DoseModel(pm)
    return pm, dm, DoseBounds(dm)


@needs_data
def test_edge_and_point_doses_within_independent_bounds(models):
    pm, dm, ob = models
    rnd = random.Random(20261117)
    q = dm.quantum
    near = [j for j in range(len(pm.g.u)) if dm.edge(j)]
    assert len(near) > 100
    checked = positive = 0
    for j in rnd.sample(near, 120):
        D = int(pm.g.ticks[j])
        runs = dm.edge(j).runs
        ts = {rnd.randint(0, pm.H - D) for _ in range(4)} | {min(r[0], pm.H - D) for r in runs[:3]}
        ts |= {max(r[1], 0) for r in runs[-2:]}
        for t in ts:
            v = dm.edge(j).at(t) * q
            lo, hi = ob.edge(j, t)
            assert lo - 1e-9 <= v <= hi + D * q + 1e-9, (j, t, lo, v, hi)
            checked += 1; positive += v > 0
    nodes = sorted({pm.g.u[j] for j in near})[:60]
    for node in nodes:
        n = pm.nidx[node]
        for t in {rnd.randint(0, pm.H - 121) for _ in range(5)}:
            v = dm.dwell(n, 120).at(t) * q
            lo, hi = ob.point(node, t, 120)
            assert lo - 1e-9 <= v <= hi + 120 * q + 1e-9, (node, t, lo, v, hi)
            w = dm.wait(n).at(t) * q
            lo, hi = ob.point(node, t, 1)
            assert lo - 1e-9 <= w <= hi + q + 1e-9
            checked += 1
    assert checked > 500 and positive > 50
