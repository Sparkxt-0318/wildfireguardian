"""Path A road redundancy: unit-capacity max-flow written for this package (standard library only).

Definition (both variants are direction-aware; a two-way road is two directed edges):

* ``turn_aware`` (primary) - the largest number of walks from the origin's entry node to any of its candidate
  destination nodes that pairwise share no directed edge and that each respect the graph's ``forbidden_turns``,
  exactly the legality rule the routing kit applies (``integration/kit/routing_candidate/baseline/
  temporal_contract.py`` ``check_mission``: an EDGE leg is legal iff ``e.u`` is the current node and
  ``(incoming_edge, e.id)`` is not a forbidden turn; the first leg has no incoming edge). Computed on the node-split
  line graph: vertex ``in(e) -> out(e)`` with capacity 1 for every directed edge ``e``; ``out(a) -> in(b)`` for every
  allowed turn; a super-source to ``in(b)`` for every edge leaving the entry node and ``out(a)`` to a super-sink for
  every edge entering a destination node. Menger: max-flow = number of edge-disjoint legal walks = size of the
  smallest set of directed road edges whose removal leaves no legal walk.
* ``plain`` - the same count ignoring turn restrictions (unit capacity per directed edge, super-sink behind the
  destination nodes). On a plain directed graph flow cancellation makes this equal to the count of paths that are
  disjoint even as physical (two-way) segments.

Turn and super-source/sink arcs carry a large capacity, so every minimum cut consists of directed road edges only;
``cut_edges`` reports the source-side minimum cut (the bottleneck edges nearest to the origin).
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

BIG = 1 << 30


class UnitFlow:
    """Residual network with paired arcs (``k`` and ``k ^ 1`` are reverses) and reusable per-query arcs."""

    __slots__ = ('n', 'to', 'cap', 'adj', '_stamp', '_seen', '_prev')

    def __init__(self, n: int):
        self.n = n
        self.to: list[int] = []
        self.cap: list[int] = []
        self.adj: list[list[int]] = [[] for _ in range(n)]
        self._stamp = 0
        self._seen = [0] * n
        self._prev = [-1] * n

    def add_arc(self, u: int, v: int, c: int) -> int:
        k = len(self.to)
        self.to.append(v)
        self.cap.append(c)
        self.adj[u].append(k)
        self.to.append(u)
        self.cap.append(0)
        self.adj[v].append(k + 1)
        return k

    def _bfs(self, s: int, t: int) -> bool:
        self._stamp += 1
        stamp, seen, prev, cap, to, adj = self._stamp, self._seen, self._prev, self.cap, self.to, self.adj
        seen[s] = stamp
        queue = [s]
        i = 0
        while i < len(queue):
            u = queue[i]
            i += 1
            for k in adj[u]:
                if cap[k] > 0:
                    v = to[k]
                    if seen[v] != stamp:
                        seen[v] = stamp
                        prev[v] = k
                        if v == t:
                            return True
                        queue.append(v)
        return False

    def max_flow(self, s: int, t: int, extra_arcs: list[tuple[int, int, int]]):
        """Max-flow from s to t after adding ``extra_arcs`` (removed again, all capacities restored, on return).
        Returns (value, source_side) where source_side(v) tells whether v is reachable in the final residual."""
        base_len = len(self.to)
        added = []
        for u, v, c in extra_arcs:
            self.add_arc(u, v, c)
            added.append((u, v))
        saved: dict[int, tuple[int, int]] = {}
        flow = 0
        while self._bfs(s, t):
            # bottleneck along the path
            b, v = BIG, t
            while v != s:
                k = self._prev[v]
                b = min(b, self.cap[k])
                v = self.to[k ^ 1]
            v = t
            while v != s:
                k = self._prev[v]
                pair = k & ~1                          # save each arc pair once, before its first change
                if pair < base_len and pair not in saved:
                    saved[pair] = (self.cap[pair], self.cap[pair + 1])
                self.cap[k] -= b
                self.cap[k ^ 1] += b
                v = self.to[k ^ 1]
            flow += b
        stamp, seen = self._stamp, list(self._seen)   # final failed BFS = source side of a minimum cut
        for pair, (c0, c1) in saved.items():
            self.cap[pair], self.cap[pair + 1] = c0, c1
        for u, v in reversed(added):                  # per-query arcs were appended last to these lists
            self.adj[v].pop()
            self.adj[u].pop()
        del self.to[base_len:]
        del self.cap[base_len:]
        return flow, (lambda x: seen[x] == stamp)


class RoadGraph:
    """The routing graph as arrays (EPSG:5179 node coordinates, directed edges, forbidden turns)."""

    def __init__(self, path: Path):
        g = json.loads(Path(path).read_text(encoding='utf-8'))
        self.revision = g['revision']
        self.node_ids = [n['id'] for n in g['nodes']]
        self.node_index = {nid: i for i, nid in enumerate(self.node_ids)}
        self.xy = [(float(n['x']), float(n['y'])) for n in g['nodes']]
        self.edge_ids = [e['id'] for e in g['edges']]
        self.edge_index = {eid: i for i, eid in enumerate(self.edge_ids)}
        self.eu = [self.node_index[e['u']] for e in g['edges']]
        self.ev = [self.node_index[e['v']] for e in g['edges']]
        self.ticks = [int(e['travel_ticks']) for e in g['edges']]
        self.source_way = [e.get('source_way') for e in g['edges']]
        self.forbidden = {(self.edge_index[a], self.edge_index[b]) for a, b in g['forbidden_turns']}
        self.out_edges: list[list[int]] = [[] for _ in self.node_ids]
        self.in_edges: list[list[int]] = [[] for _ in self.node_ids]
        for i, (u, v) in enumerate(zip(self.eu, self.ev)):
            self.out_edges[u].append(i)
            self.in_edges[v].append(i)
        del g

    def edge_length_m(self, i: int) -> float:
        (x0, y0), (x1, y1) = self.xy[self.eu[i]], self.xy[self.ev[i]]
        return ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5


class RedundancySolver:
    """Both flow networks of one region, built once and queried per origin."""

    def __init__(self, graph: RoadGraph):
        self.g = graph
        m, n = len(graph.edge_ids), len(graph.node_ids)
        # turn-aware: in(e) = 2e, out(e) = 2e + 1, S = 2m, T = 2m + 1
        self.ta = UnitFlow(2 * m + 2)
        self.ta_s, self.ta_t = 2 * m, 2 * m + 1
        self.ta_vertex_arc = [self.ta.add_arc(2 * e, 2 * e + 1, 1) for e in range(m)]
        turns = 0
        for x in range(n):
            for a in graph.in_edges[x]:
                for b in graph.out_edges[x]:
                    if (a, b) not in graph.forbidden:
                        self.ta.add_arc(2 * a + 1, 2 * b, BIG)
                        turns += 1
        self.allowed_turns = turns
        # plain: graph nodes 0..n-1, super-sink T = n
        self.pl = UnitFlow(n + 1)
        self.pl_t = n
        for e in range(m):
            self.pl.add_arc(graph.eu[e], graph.ev[e], 1)

    def turn_aware(self, origin: int, dests: list[int]):
        g = self.g
        extra = [(self.ta_s, 2 * b, BIG) for b in g.out_edges[origin]]
        extra += [(2 * a + 1, self.ta_t, BIG) for d in dests for a in g.in_edges[d]]
        value, src = self.ta.max_flow(self.ta_s, self.ta_t, extra)
        cut = [g.edge_ids[e] for e in range(len(g.edge_ids)) if src(2 * e) and not src(2 * e + 1)]
        return value, cut

    def plain(self, origin: int, dests: list[int]):
        extra = [(d, self.pl_t, BIG) for d in dests]
        value, _ = self.pl.max_flow(origin, self.pl_t, extra)
        return value


def turn_counts(graph: RoadGraph) -> dict:
    possible = sum(len(graph.in_edges[x]) * len(graph.out_edges[x]) for x in range(len(graph.node_ids)))
    return {'possible_turns': possible, 'forbidden_turns': len(graph.forbidden)}


def degree_summary(graph: RoadGraph) -> dict:
    d = defaultdict(int)
    for x in range(len(graph.node_ids)):
        d[len(graph.out_edges[x])] += 1
    return dict(sorted(d.items()))
