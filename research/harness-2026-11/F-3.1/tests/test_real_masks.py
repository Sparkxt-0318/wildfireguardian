"""Real data: the closed-form blocked start intervals equal direct per-second contact evaluation with the replay tool's
exact rules (``Packet.contact_router`` / ``Packet.contact_closed``), for every edge that touches a burning cell and
probe seconds at every interval boundary (+-1) plus random seconds; also for waits, dwells and issue points.
Requires data/routing (tools/fetch_routing_inputs.py)."""
from __future__ import annotations

import os
import random
from fractions import Fraction as F
from pathlib import Path

import pytest

from deadline_field import intervals as iv
from deadline_field.real import ROOT, PacketModel
from tools.explain_deadlines.geometry import chord_pieces, clip_closed

DATA = ROOT / "data" / "routing"
PACKETS = sorted((DATA / "latest_inputs_try02" / "packets").glob("*_2025/*")) if DATA.exists() else []
FULL = os.environ.get("F31_FULL") == "1"


def direct_edge(pm: PacketModel, j: int, t: int, rule: str) -> bool:
    g, grid, pk, H = pm.g, pm.g.grid, pm.pk, pm.H
    p0, p1 = g.xy(g.u[j]), g.xy(g.v[j])
    Dq = F(g.ticks[j])
    if rule == "router":
        pieces, points = chord_pieces(grid, p0, p1)
        occ = [(c, t + Dq * a, t + Dq * b) for c, a, b in pieces] + [(c, t + Dq * z, t + Dq * z) for c, z in points]
        return any(pk.contact_router(s, c, lo, hi) == "FLAME_CONTACT" for s in range(pk.S) for c, lo, hi in occ)
    for c in grid.cells_touching_box(min(p0[0], p1[0]), max(p0[0], p1[0]), min(p0[1], p1[1]), max(p0[1], p1[1])):
        u = clip_closed(p0, p1, grid.rect(c))
        if u is None:
            continue
        for s in range(pk.S):
            w = pk.contact_closed(s, c, t + Dq * u[0], t + Dq * u[1])
            if w is not None and w <= H:
                return True
    return False


def direct_point(pm: PacketModel, node: str, t: int, length: F, rule: str) -> bool:
    grid, pk, H = pm.g.grid, pm.pk, pm.H
    p = pm.g.xy(node)
    if rule == "router":
        c = grid.cell_of(*p)
        return any(pk.contact_router(s, c, F(t), t + length) == "FLAME_CONTACT" for s in range(pk.S))
    for c in grid.cells_touching_box(p[0], p[0], p[1], p[1]):
        if clip_closed(p, p, grid.rect(c)) is None:
            continue
        for s in range(pk.S):
            w = pk.contact_closed(s, c, F(t), t + length)
            if w is not None and w <= H:
                return True
    return False


def probes(ivs, H, rnd, k=8):
    ts = set(rnd.sample(range(H + 1), k))
    for lo, hi in ivs:
        ts.update({lo - 1, lo, lo + 1, hi - 1, hi, hi + 1})
    return sorted(t for t in ts if 0 <= t <= H)


@pytest.mark.skipif(not PACKETS, reason="routing inputs not installed")
@pytest.mark.parametrize("packet_dir", PACKETS, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_masks_equal_direct_contact(packet_dir):
    region = packet_dir.parent.name
    pm = PacketModel(DATA / "graphs" / region / "graph.json", packet_dir)
    rnd = random.Random(20261112)
    H = pm.H
    # every edge whose bounding box touches a burning cell, INCLUDING those whose masks came out empty (these must
    # then be clear at every probe second)
    touching = list(pm.touching_edges)
    empty = [j for j in touching if not pm.B["router"][j] and not pm.B["closed"][j]]
    cand = touching if FULL else rnd.sample(touching, min(150, len(touching))) + rnd.sample(empty, min(50, len(empty)))
    checked = 0
    for j in cand:
        for rule in ("router", "closed"):
            for t in probes(pm.B[rule][j], H - pm.g.ticks[j], rnd):
                assert direct_edge(pm, j, t, rule) == iv.contains(pm.B[rule][j], t), (j, t, rule)
                checked += 1
    # points: waitable nodes, and a sample of nodes in or next to burning cells, with lengths 0 (issue), 1 (wait),
    # 120 (dwell)
    nodes = [n for n in pm.node_ids if any(pm.point_blocks(n, F(1), r) for r in ("router", "closed"))]
    nodes = nodes if FULL else rnd.sample(nodes, min(60, len(nodes)))
    for n in nodes:
        for length in (F(0), F(1), F(120)):
            for rule in ("router", "closed"):
                b = pm.point_blocks(n, length, rule)
                for t in probes(b, H - int(length), rnd):
                    assert direct_point(pm, n, t, length, rule) == iv.contains(b, t), (n, t, length, rule)
                    checked += 1
    assert checked > 1000
