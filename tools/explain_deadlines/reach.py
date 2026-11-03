"""Flame-avoiding earliest-arrival relaxation (a lower bound used only to PROVE that no journey fits a window).

Every recorded ``checked_route`` is a journey whose whole trajectory has no closed-footprint flame contact in any of
the four members (the mandatory runtime whole-road check, ``contact_first.check_contact``). The relaxation below keeps
exactly that constraint for EDGE traversals and the issue point, keeps the router's movement rules (turn
restrictions, travel ticks, 1 s lattice, admission on edge arrival) and drops everything else:

* waiting is allowed at every node and is never checked (a superset of the router's waitable-node waits);
* heat limits (peak flux, dose) are ignored.

Hence the set of relaxed journeys contains every checked journey, and the relaxed earliest arrival is a lower bound
on any checked journey's arrival. With free waiting the network is FIFO, so a label-setting search over edge states
with "earliest free departure" is exact for the relaxation.

A traversal of edge e starting at integer second t meets closed-rule flame in a burning cell occupied (relative to
the start) on [enter, leave] with phase [b, x) iff t lies in [b - leave, x - enter)  (closed occupancy, half-open
phase; see replay.py). The union of these intervals over all members and cells is the blocked set of e.
"""
from __future__ import annotations

import heapq
from fractions import Fraction as F

from .geometry import ceil_q, clip_closed
from .packet import Packet
from .roads import RoadGraph


class ContactIndex:
    """Blocked departure intervals of edges and points, for one packet and graph (cached per edge)."""

    def __init__(self, graph: RoadGraph, packet: Packet):
        if packet.dt != 1:                    # travel ticks, waits and departure offsets are used as seconds
            raise ValueError("routing tick is not 1 s")
        self.g = graph
        self.pk = packet
        self.burning = set(packet.burning_cells)
        self._edge: dict = {}
        self._point: dict = {}

    def occupancies(self, p0, p1, dur: F) -> list:
        """[(cell, enter, leave)] closed-footprint occupancies of burning cells, relative to the segment start."""
        grid = self.g.grid
        out = []
        for cell in grid.cells_touching_box(min(p0[0], p1[0]), max(p0[0], p1[0]), min(p0[1], p1[1]), max(p0[1], p1[1])):
            if cell not in self.burning:
                continue
            u = clip_closed(p0, p1, grid.rect(cell))
            if u is not None:
                out.append((cell, dur * u[0], dur * u[1]))
        return out

    def _intervals(self, occ) -> list:
        """[(lo, hi, member, cell, birth)] blocked start-time intervals [lo, hi) of a relative occupancy list."""
        out = []
        for s in range(self.pk.S):
            for cell, enter, leave in occ:
                ph = self.pk.phases[s].get(cell)
                if ph is None:
                    continue
                lo, hi = ph[0] - leave, ph[1] - enter
                if lo < hi:
                    out.append((lo, hi, s, cell, ph[0]))
        return out

    def edge_blocks(self, e: int) -> list:
        if e not in self._edge:
            g = self.g
            occ = self.occupancies(g.xy(g.u[e]), g.xy(g.v[e]), F(g.ticks[e]))
            self._edge[e] = self._intervals(occ)
        return self._edge[e]

    def point_blocks(self, node: str, dur: F) -> list:
        key = (node, dur)
        if key not in self._point:
            p = self.g.xy(node)
            self._point[key] = self._intervals(self.occupancies(p, p, dur))
        return self._point[key]


def earliest_free(blocks: list, a: int, latest: int):
    """Smallest integer t >= a with t not inside any [lo, hi) of ``blocks``; None if it exceeds ``latest``."""
    t = a
    moved = True
    while moved:
        if t > latest:
            return None
        moved = False
        for lo, hi, *_ in blocks:
            if lo <= t < hi:
                t = max(t, ceil_q(hi) if hi.denominator != 1 else int(hi))
                moved = True
    return t if t <= latest else None


def flame_avoiding(index: ContactIndex, start: str, depart: int, targets, latest_arrival: int, *, turns: bool = True) -> dict:
    """Relaxed earliest arrival at each target (None when not reachable by ``latest_arrival``) and the issue-point
    status, plus the two ways the relaxed search stops at an edge leaving a reached node:

    * ``frontier`` -- flame-blocked: the edge can still be started before ``latest_arrival - ticks`` but every such
      start second meets flame (closed rule, some member);
    * ``horizon_cut`` -- time ran out: even an immediate start would end after ``latest_arrival``.

    ``turns=False`` also drops the turn restrictions (a further superset: every edge leaving a reached node is tried).
    ``frontier_exits`` / ``horizon_cut_exits`` keep only the edges whose end node was never reached, i.e. the roads that
    leave the reached area (a blocked edge between two reached nodes does not close anything off).
    Returns {"arrival", "issue_blocked", "frontier": [(edge, at_s)], "horizon_cut": [(edge, at_s)], "frontier_exits",
    "horizon_cut_exits", "reached_nodes"}."""
    g = index.g
    targets = set(targets)
    issue = [b for b in index.point_blocks(start, F(0)) if b[0] <= depart < b[1]]
    out = {"arrival": {t: None for t in targets}, "issue_blocked": bool(issue), "frontier": [], "horizon_cut": [],
           "frontier_exits": [], "horizon_cut_exits": [], "reached_nodes": 0,
           "issue_pairs": [(b[2], b[3], b[4]) for b in issue]}
    if issue:
        return out
    dist: dict = {}
    heap = []
    frontier, cut = {}, {}

    def relax(e, a):
        tau = g.ticks[e]
        if a > latest_arrival - tau:
            if e not in cut or a < cut[e]:
                cut[e] = a
            return
        t = earliest_free(index.edge_blocks(e), a, latest_arrival - tau)
        if t is None:
            if e not in frontier or a < frontier[e]:
                frontier[e] = a
            return
        arr = t + tau
        if arr < dist.get(e, 1 << 62):
            dist[e] = arr
            heapq.heappush(heap, (arr, e))

    for e in g.out.get(start, []):
        relax(e, depart)
    reached = {start}
    remaining = set(targets)
    while heap:
        d, e = heapq.heappop(heap)
        if d != dist.get(e):
            continue
        node = g.v[e]
        reached.add(node)
        if node in remaining:
            out["arrival"][node] = d
            remaining.discard(node)
        for f in g.out.get(node, []):
            if turns and (e, f) in g.forbidden:
                continue
            relax(f, d)
    # an edge is a frontier edge only if no relaxed journey ever traverses it
    out["frontier"] = sorted(((g.edge_ids[e], a) for e, a in frontier.items() if e not in dist), key=lambda x: (x[1], x[0]))
    out["horizon_cut"] = sorted(((g.edge_ids[e], a) for e, a in cut.items() if e not in dist and e not in frontier),
                                key=lambda x: (x[1], x[0]))
    out["frontier_exits"] = [(eid, a) for eid, a in out["frontier"] if g.v[g.edge_index[eid]] not in reached]
    out["horizon_cut_exits"] = [(eid, a) for eid, a in out["horizon_cut"] if g.v[g.edge_index[eid]] not in reached]
    out["reached_nodes"] = len(reached)
    return out


def dwell_free_arrival(index: ContactIndex, node: str, a_min: int, a_max: int, dwell: int):
    """Earliest integer arrival a in [a_min, a_max] whose stay [a, a + dwell] at ``node`` has no closed-rule contact."""
    return earliest_free(index.point_blocks(node, F(dwell)), a_min, a_max)
