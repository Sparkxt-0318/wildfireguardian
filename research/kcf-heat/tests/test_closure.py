"""Heat closure rule on a real frozen packet, against an independent float sampling oracle.

Needs the frozen routing inputs (tools/fetch_routing_inputs.py) at $WFG_ROUTING_DATA or <repo>/data/routing; skipped
otherwise. The oracle re-derives the rule from its text (rectangles, halo, phases, lead) with plain floats and samples
each traversal every 0.05 s; it shares no code with closure.py's interval construction.
"""
import json
import math
import os
import random
import sys
from fractions import Fraction as F
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from kcf_heat.closure import HeatPacketModel, HeatRule, ROOT, iv  # noqa: E402

DATA = Path(os.environ.get("WFG_ROUTING_DATA", ROOT / "data" / "routing"))
CACHE = ROOT / "planner" / "cache" / "uiseong_andong_2025" / "20250323T010000Z.json"
PACKET = DATA / "latest_inputs_try02" / "packets" / "uiseong_andong_2025" / "20250323T010000Z"
GRAPH = DATA / "graphs" / "uiseong_andong_2025" / "graph.json"
needs_data = pytest.mark.skipif(not (PACKET.is_dir() and GRAPH.is_file()), reason="frozen routing inputs not present")


def test_rule_constants():
    r = HeatRule()
    assert (r.lead_s(10), float(r.halo_m(10)), r.lead_s(2.5), float(r.halo_m(2.5))) == (84, 7.96, 350, 33.16)
    assert r.lead_s(10) >= 83.09 and float(r.halo_m(10)) >= r.spread_m_s * 83.09


@pytest.fixture(scope="module")
def pm():
    return HeatPacketModel(GRAPH, PACKET)


def oracle_blocked(pm, j, t, rule, eps_t=0.0, eps_x=0.0):
    """Sampled check of the rule text; eps widens rectangles (m) and phases (s) for the tolerant direction."""
    g, grid = pm.g, pm.g.grid
    T, h = rule.lead_s(rule.q_vehicle_kw_m2), float(rule.halo_m(rule.q_vehicle_kw_m2))
    p0 = [float(v) for v in g.xy(g.u[j])]; p1 = [float(v) for v in g.xy(g.v[j])]
    D = float(g.ticks[j])
    for c in pm.burning:
        x0, x1, y0, y1 = (float(v) for v in grid.rect(c))
        for b, x, _s in pm.closed_ph.get(c, ()):
            b = float(b); x = float(x) if x is not None else math.inf
            n = max(2, int(D / 0.05) + 1)
            for k in range(n + 1):
                z = k / n; tt = t + z * D
                px, py = p0[0] + z * (p1[0] - p0[0]), p0[1] + z * (p1[1] - p0[1])
                e = eps_x
                inside = x0 - e <= px <= x1 + e and y0 - e <= py <= y1 + e
                near = x0 - h - e <= px <= x1 + h + e and y0 - h - e <= py <= y1 + h + e
                if (inside and b - T - eps_t <= tt < x + eps_t) or (near and b - eps_t <= tt < x + eps_t):
                    return True
    return False


@needs_data
def test_heat_blocks_contain_closed_blocks(pm):
    for j in pm.touching_edges:
        for lo, hi in pm.B["closed"][j]:
            assert iv.subtract((lo, hi), pm.B["heat"][j]) == []


@needs_data
def test_heat_blocks_agree_with_sampling_oracle(pm):
    rng = random.Random(20261117)
    edges = [j for j in range(len(pm.g.u)) if pm.B["heat"][j]]
    assert edges, "no heat-blocked edge on this packet"
    checked = 0
    for j in rng.sample(edges, min(25, len(edges))):
        blocks = pm.B["heat"][j]
        probe = set()
        for lo, hi in blocks:                      # boundaries and interiors of every interval, and just outside
            probe.update({lo, hi, lo - 1, hi + 1, (lo + hi) // 2})
        probe.update(rng.randrange(0, pm.H + 1) for _ in range(5))
        for t in sorted(p for p in probe if 0 <= p <= pm.H):
            blocked = iv.contains(blocks, t)
            if oracle_blocked(pm, j, t, pm.heat):                  # a sampled violation is always closed
                assert blocked, ("missed", j, t)
            if blocked:                                            # every closure is confirmed within the sampling step
                assert oracle_blocked(pm, j, t, pm.heat, eps_t=0.1, eps_x=2.0), ("spurious", j, t)
            checked += 1
    assert checked > 100


@needs_data
def test_heat_field_never_later_than_cert(pm):
    sys.path.insert(0, str(ROOT / "research" / "harness-2026-11" / "F-3.1"))
    from deadline_field.core import backward, issue_set
    doc = json.loads(CACHE.read_text())
    specs = {}
    for job in list((doc.get("route_checks") or {}).values())[:400]:
        q = job["request"]
        specs.setdefault((q["destination"]["node_id"], q["dwell_s"], tuple(q["destination_window"])), set()).add(q["start"]["node_id"])
    later = 0; compared = 0
    for (dn, dw, win), origins in list(specs.items())[:3]:
        dest = [{"node": dn, "dwell": dw, "window": list(win)}]
        fc = backward(pm.instance("cert", dest, sorted(origins)))
        fh = backward(pm.instance("cert_heat", dest, sorted(origins)))
        for o in origins:
            a, b = issue_set(fc, pm.nidx[o]), issue_set(fh, pm.nidx[o])
            assert iv.subtract_all(b, a) == []         # heat-feasible departures are a subset of cert-feasible ones
            compared += 1
            later += bool(b and a and b[-1][1] > a[-1][1])
    assert compared > 0 and later == 0
