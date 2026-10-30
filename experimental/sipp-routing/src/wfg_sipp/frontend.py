"""Geometry front end: builds the abstract SIPP instance of one (graph, request, contact model) with exactly the sweep's
occupancy semantics, and exposes SIPP through the planner interface of `wfg_members.planner`.

Safe intervals are computed per sub-segment and intersected along the edge with its time shifts, as zsweep does: for a
directed edge with D = travel_ticks * dt, every occupancy o of the edge on the unit clock (the open sub-segments between
grid-line cuts with their midpoint cell, and every cut point with its floor cell, from the frozen
`core.edge_occupancies`) and every exact half-open activity interval [b, e) of o's cell, the departure seconds

    t in [ceil(b - D * z_end(o)), ceil(e - D * z_start(o)) - 1]  (clipped to [departure, horizon])

meet flame; their union is the edge's blocked set and its complement the edge's safe departure intervals. A node wait
from t to t + 1 is blocked for t in [ceil(b - 1), ceil(e) - 1]. Destination acceptance at t needs an opening [a, c] with
a <= t and t + dwell <= c, t + dwell <= horizon, and no activity interval with t < e and t + dwell >= b at the node
cell. Edges are prefiltered by the sweep's own bounding-box test (cell rectangles padded by 1 m).

This module imports the frozen kit through track 1C-1 (`wfg_members.kit`), which pins every frozen source hash.
"""
from __future__ import annotations

import math
import sys
import time
from fractions import Fraction as F
from pathlib import Path

import numpy as np

from . import adapter as kit
from .adapter import normalise as _normalise

from . import sipp as S  # noqa: E402
from .intervals import complement, normalise  # noqa: E402


def _ceil(q):
    return -((-q.numerator) // q.denominator)


class PreparedGraph:
    def __init__(self, graph):
        K = kit.install()
        self.core = K["core"]
        self.graph = graph
        self.nodes = {n["id"]: n for n in graph["nodes"]}
        self.node_list = list(self.nodes)
        self.nidx = {n: i for i, n in enumerate(self.node_list)}
        self.edges = graph["edges"]
        self.eidx = {e["id"]: i for i, e in enumerate(self.edges)}
        self.tail = [self.nidx[e["u"]] for e in self.edges]
        self.head = [self.nidx[e["v"]] for e in self.edges]
        self.waitable = [bool(self.nodes[n]["waitable"]) for n in self.node_list]
        self.node_cells = [self.core.node_cell(graph, self.nodes[n]) for n in self.node_list]
        self.forbidden_ids = set(tuple(t) for t in graph["forbidden_turns"])
        E = len(self.edges)
        self.forbidden_pairs = {(self.eidx[a], self.eidx[b]) for a, b in self.forbidden_ids if a in self.eidx and b in self.eidx}
        U = np.array([(float(self.nodes[e["u"]]["x"]), float(self.nodes[e["u"]]["y"])) for e in self.edges])
        V = np.array([(float(self.nodes[e["v"]]["x"]), float(self.nodes[e["v"]]["y"])) for e in self.edges])
        self.bx0, self.bx1 = np.minimum(U[:, 0], V[:, 0]), np.maximum(U[:, 0], V[:, 0])
        self.by0, self.by1 = np.minimum(U[:, 1], V[:, 1]), np.maximum(U[:, 1], V[:, 1])
        g = graph["grid"]
        self.res, self.x0, self.y0, self.W = float(g["resolution"]), float(g["x0"]), float(g["y0"]), int(g["width"])
        self.occ = {}
        self.E = E
        self.succ_cache = {}

    def occupancies(self, i):
        o = self.occ.get(i)
        if o is None:
            o = self.occ[i] = [(int(x["cell"]), F(x["start"]), F(x["end"]))
                               for x in self.core.edge_occupancies(self.edges[i], 0, 1, 0, 1, self.graph, self.nodes)]
        return o

    def candidate_edges(self, cells):
        if not cells:
            return np.zeros(0, dtype=np.int64)
        cells = np.array(sorted(cells))
        cx0 = self.x0 + (cells % self.W) * self.res - 1
        cx1 = self.x0 + (cells % self.W + 1) * self.res + 1
        cy0 = self.y0 + (cells // self.W) * self.res - 1
        cy1 = self.y0 + (cells // self.W + 1) * self.res + 1
        cand = np.zeros(self.E, bool)
        for lo in range(0, cells.size, 512):
            sl = slice(lo, lo + 512)
            cand |= ((self.bx0[:, None] <= cx1[None, sl]) & (self.bx1[:, None] >= cx0[None, sl])
                     & (self.by0[:, None] <= cy1[None, sl]) & (self.by1[:, None] >= cy0[None, sl])).any(axis=1)
        return np.flatnonzero(cand)


def prepared(graph):
    # No process-global object-identity cache: caller mutation cannot reuse stale
    # geometry. Complete-request measurements include a fresh preparation.
    return PreparedGraph(graph)


def build_instance(graph, request, model, *, extra_blocked=None, prepared_graph=None):
    pg = prepared_graph if prepared_graph is not None else prepared(graph)
    if request["position"].get("node") is None:
        raise ValueError("SIPP_SCOPE_NODE_POSITION_ONLY")
    dep, hor = F(request["departure"]), F(request["horizon"])
    if dep.denominator != 1 or hor.denominator != 1:
        raise ValueError("SIPP_INTEGER_CLOCK_REQUIRED")
    dep, hor = int(dep), int(hor)
    cells = model.cell_intervals
    edge_block = {}
    for i in pg.candidate_edges(set(cells)):
        Dq = F(int(pg.edges[i]["travel_ticks"]))
        blocked = []
        for c, za, zb in pg.occupancies(int(i)):
            for b, e in cells.get(c, ()):
                lo_t = max(dep, _ceil(b - Dq * zb))
                hi_t = min(hor, _ceil(e - Dq * za) - 1)
                if lo_t <= hi_t:
                    blocked.append((lo_t, hi_t))
        if blocked:
            edge_block[int(i)] = blocked
    for j, ws in (extra_blocked or {}).items():
        edge_block.setdefault(int(j), []).extend((int(a), int(b)) for a, b in ws)
    wait_block = {}
    for ni, c in enumerate(pg.node_cells):
        if c in cells and pg.waitable[ni]:
            bl = []
            for b, e in cells[c]:
                lo_t, hi_t = max(0, _ceil(b - 1)), min(hor, _ceil(e) - 1)
                if lo_t <= hi_t:
                    bl.append((lo_t, hi_t))
            if bl:
                wait_block[ni] = bl
    accept = {}
    for d in request["destinations"]:
        ni = pg.nidx[d["node"]]
        w = F(d["dwell"])
        ok = []
        for a, b in d["open_intervals"]:
            lo_t = max(dep, _ceil(F(a)))
            hi_t = min(hor, math.floor(F(b) - w), math.floor(hor - w))
            if lo_t <= hi_t:
                ok.append((lo_t, hi_t))
        ok = normalise(ok)
        bl = []
        for b, e in cells.get(pg.node_cells[ni], ()):
            lo_t, hi_t = _ceil(b - w), _ceil(e) - 1
            if lo_t <= hi_t:
                bl.append((lo_t, hi_t))
        bl = normalise(bl)
        free = []
        for lo, hi in ok:
            free.extend(complement(bl, lo, hi))
        accept[ni] = normalise(accept.get(ni, []) + free)
    origin = pg.nidx[request["position"]["node"]]
    incoming = request["incoming_edge"]
    E = pg.E
    start = E if incoming is None else pg.eidx[incoming]
    forbidden = set(pg.forbidden_pairs)
    inst = S.make_instance(n_nodes=len(pg.node_list), tail=pg.tail, head=pg.head,
                           D=[int(e["travel_ticks"]) * 1 for e in pg.edges], origin=origin, start_state=start,
                           forbidden=forbidden, waitable=pg.waitable, edge_block=edge_block, wait_block=wait_block,
                           accept=accept, departure=dep, horizon=hor)
    key = (id(graph), start, origin)
    if key in pg.succ_cache:
        inst.succ = pg.succ_cache[key]
    else:
        pg.succ_cache[key] = inst.successors()
    return inst, pg


def _cell_contact(cells, cell, lo, hi):
    return any(lo < e and hi >= b for b, e in cells.get(cell, ()))


def sipp_plan(graph, request, model, *, extra_blocked=None, wall_s=600.0, max_labels=None):
    """Planner interface (same result layout as wfg_members.planner.sweep_plan)."""
    t0 = time.perf_counter()
    if getattr(model, "supported", True) is not True:
        return _normalise({"status": "UNSUPPORTED", "reason": "UNKNOWN_TRAJECTORY_SUPPORT", "metrics": {}}, "sipp", time.perf_counter() - t0)
    dep = F(request["departure"])
    pg = prepared(graph)
    cells = model.cell_intervals
    origin = request["position"]["node"]
    budgets = request["budgets"]["dose"]
    if _cell_contact(cells, pg.node_cells[pg.nidx[origin]], dep, dep) or any(
            F(request["incurred"][m]) > F(budgets[m]) for m in request["incurred"]):
        return _normalise({"status": "AT_ISSUE_FAILURE", "reason": "AT_ISSUE_CONSTRAINT_VIOLATION", "metrics": {}}, "sipp",
                          time.perf_counter() - t0)
    t_build = time.perf_counter()
    inst, pg = build_instance(graph, request, model, extra_blocked=extra_blocked, prepared_graph=pg)
    build_s = time.perf_counter() - t_build
    res = S.solve(inst, deadline=t0 + wall_s, max_labels=max_labels)
    metrics = dict(res["metrics"], build_s=build_s, search_s=res["wall_s"], blocked_edges=len(inst.edge_block),
                   blocked_wait_nodes=len(inst.wait_block))
    if res["status"] == "FOUND":
        legs = []
        for kind, ident, a, b in res["legs"]:
            if kind == "EDGE":
                legs.append({"kind": "EDGE", "edge": pg.edges[ident]["id"], "start": a, "end": b, "from_fraction": 0, "to_fraction": 1})
            else:
                legs.append({"kind": "WAIT", "node": pg.node_list[ident], "start": a, "end": b})
        dest = pg.node_list[res["destination_node"]] if res["legs"] else origin
        ind = kit.install()["independent"]
        try:
            ind._shape(graph, {"dt": 1}, request, legs, dest)
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            return _normalise({"status": "UNSUPPORTED", "reason": "WITNESS_STRUCTURE:" + str(exc), "metrics": metrics}, "sipp",
                              time.perf_counter() - t0)
        return _normalise({"status": "CONDITIONAL_OPTIMUM", "reason": "SIPP_FIRST_GOAL", "arrival": res["arrival"], "legs": legs,
                           "destination": dest, "metrics": metrics}, "sipp", time.perf_counter() - t0)
    if res["status"] == "EXHAUSTED":
        if not S.structurally_reachable(inst):
            return _normalise({"status": "DISCONNECTED", "reason": "TURN_GRAPH_DISCONNECTED", "metrics": metrics}, "sipp",
                              time.perf_counter() - t0)
        return _normalise({"status": "PROVEN_INFEASIBLE", "reason": "SIPP_OPEN_LIST_EXHAUSTED", "metrics": metrics}, "sipp",
                          time.perf_counter() - t0)
    return _normalise({"status": "TIMEOUT", "reason": res["status"], "metrics": metrics}, "sipp", time.perf_counter() - t0)
