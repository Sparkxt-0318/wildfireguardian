"""Road graph (wfg routing graph JSON) in a compact form, plus the fire-free earliest-arrival search.

``fastest_ticks`` is the structural (no hazard) earliest arrival under the router's own movement rules
(kit ``routing/core.py::solve``): a journey from a node position with no incoming edge may take any outgoing edge;
afterwards a turn (incoming, next) listed in ``forbidden_turns`` is never taken; every EDGE leg lasts
``travel_ticks * dt`` seconds; a destination is admitted only on arrival over an edge. Waiting never shortens a
fire-free journey, so the earliest arrival is the shortest edge-state path. The search is exact (integer ticks).
"""
from __future__ import annotations

import heapq
import json
from pathlib import Path

from .geometry import Grid, exact


class RoadGraph:
    def __init__(self, raw: dict):
        self.revision = raw.get("revision")
        self.crs = raw.get("crs")
        self.grid = Grid.from_graph(raw["grid"])
        self.node_xy = {n["id"]: (n["x"], n["y"]) for n in raw["nodes"]}
        self.waitable = {n["id"]: n.get("waitable") is True for n in raw["nodes"]}
        self.edge_ids = [e["id"] for e in raw["edges"]]
        self.edge_index = {eid: i for i, eid in enumerate(self.edge_ids)}
        self.u = [e["u"] for e in raw["edges"]]
        self.v = [e["v"] for e in raw["edges"]]
        self.ticks = [int(e["travel_ticks"]) for e in raw["edges"]]
        self.source_way = [e.get("source_way") for e in raw["edges"]]
        self.out: dict = {}
        for i, a in enumerate(self.u):
            self.out.setdefault(a, []).append(i)
        self.forbidden = set()
        for a, b in raw.get("forbidden_turns", []):
            if a in self.edge_index and b in self.edge_index:
                self.forbidden.add((self.edge_index[a], self.edge_index[b]))
        if raw.get("mid_edge_reversal"):
            raise ValueError("mid-edge reversal graphs are not supported by this tool")

    @classmethod
    def load(cls, path) -> "RoadGraph":
        return cls(json.loads(Path(path).read_text()))

    def xy(self, node_id: str):
        x, y = self.node_xy[node_id]
        return (exact(x), exact(y))

    def edge(self, edge_id: str) -> dict:
        i = self.edge_index[edge_id]
        return {"id": edge_id, "u": self.u[i], "v": self.v[i], "travel_ticks": self.ticks[i], "source_way": self.source_way[i]}

    def fastest_ticks(self, start_node: str, targets, max_ticks: int | None = None) -> dict:
        """Earliest fire-free arrival (in ticks after departure) at each target node; None when not reachable
        within ``max_ticks`` (or at all)."""
        targets = set(targets)
        best = {t: None for t in targets}
        dist: dict = {}
        heap = []
        for e in self.out.get(start_node, []):
            d = self.ticks[e]
            if max_ticks is not None and d > max_ticks:
                continue
            if d < dist.get(e, 1 << 62):
                dist[e] = d
                heapq.heappush(heap, (d, e))
        remaining = set(targets)
        while heap and remaining:
            d, e = heapq.heappop(heap)
            if d != dist.get(e):
                continue
            node = self.v[e]
            if node in remaining:
                best[node] = d
                remaining.discard(node)
            for f in self.out.get(node, []):
                if (e, f) in self.forbidden:
                    continue
                nd = d + self.ticks[f]
                if max_ticks is not None and nd > max_ticks:
                    continue
                if nd < dist.get(f, 1 << 62):
                    dist[f] = nd
                    heapq.heappush(heap, (nd, f))
        return best
