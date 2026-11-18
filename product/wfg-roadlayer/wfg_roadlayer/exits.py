"""Independent road exits of a village: edge-disjoint routes to any shelter, and the road whose loss cuts the most.

Fire-independent road structure (no new science, standard graph theory):

* The road graph is read as undirected road pieces: an edge and its reverse edge (``reverse_edge``) are one piece,
  usable by one route only; a one-way edge is a piece usable in its direction only. Turn restrictions are ignored
  (they never lower the count of physically separate roads; stated on the cards).
* **Exits** = the maximum number of routes from the village's road entry node to any checkable shelter that share no
  road piece (Menger: = the fewest road pieces whose loss disconnects the village from every shelter). Shelters at the
  village's own entry node are left out. Found by successive shortest paths (minimum total travel time), so the routes
  drawn are the quickest set of that many disjoint routes. Counted up to ``max_exits``.
* **Dangerous road** = the road stretch inside one 375 m road cell (the unit by which the model closes roads; every
  road piece with a segment in the cell is lost) whose loss lowers the exit count the most. The village's own entry
  cell is left out (losing it means fire at the village). Every cell on the drawn routes is tried (a cell on none of
  them cannot lower the count). Ties: the cell nearest the village along the routes (travel time to its first use),
  then the smallest cell number. It is named by the OSM way that carries most of the routes through that cell.
  A whole OSM way is not used as the unit: a village part-way along a way would always lose both directions with it,
  which no single closure does.
"""
from __future__ import annotations

import heapq

INF = 1 << 60


class FlowGraph:
    def __init__(self, road, shelter_nodes):
        self.road = road
        n = len(road.node_ids)
        self.n = n
        self.t = n  # super sink
        self.to, self.cap0, self.cost, self.edge = [], [], [], []
        self.adj = [[] for _ in range(n + 1)]
        eid = {e: j for j, e in enumerate(road.edge_ids)}
        self.rev_of = [None] * len(road.edge_ids)
        self.cell_arcs = {}
        seen = set()
        for j in range(len(road.edge_ids)):
            if j in seen:
                continue
            r = road.reverse_edge[j] if getattr(road, "reverse_edge", None) else None
            k = eid.get(r) if r else None
            u, v, d = road.tail[j], road.head[j], road.D[j]
            if k is not None and k not in seen and road.tail[k] == v and road.head[k] == u:
                seen.update((j, k))
                a = self._arc(u, v, 1, d, j)
                b = self._arc(v, u, 1, road.D[k], k)
                arcs = [a, a ^ 1, b, b ^ 1]
            else:
                seen.add(j)
                a = self._arc(u, v, 1, d, j)
                arcs = [a, a ^ 1]
            for e in ((j, k) if k is not None and len(arcs) == 4 else (j,)):
                for c, _ in road.seg[e]:
                    self.cell_arcs.setdefault(c, set()).update(arcs)
        self.sink_arcs = {}
        for s in sorted(shelter_nodes):
            self.sink_arcs[s] = self._arc(s, self.t, INF, 0, None)

    def _arc(self, u, v, c, w, j):
        i = len(self.to)
        self.to += [v, u]
        self.cap0 += [c, 0]
        self.cost += [w, -w]
        self.edge += [j, j]
        self.adj[u].append(i)
        self.adj[v].append(i + 1)
        return i

    # ------------------------------------------------------------------------------------------ min-cost flow
    def exits(self, s, max_exits, excluded_sinks=()):
        """Successive shortest paths from node s to the sink. Returns (k, paths), each path a list of edge indices."""
        cap = list(self.cap0)
        for sn in excluded_sinks:
            a = self.sink_arcs.get(sn)
            if a is not None:
                cap[a] = 0
        pot = [0] * (self.n + 1)
        to, cost, adj = self.to, self.cost, self.adj
        flow = 0
        while flow < max_exits:
            dist = {s: 0}
            prev = {}
            heap = [(0, s)]
            done = set()
            while heap:
                d, u = heapq.heappop(heap)
                if u in done:
                    continue
                done.add(u)
                if u == self.t:
                    break
                pu = pot[u]
                for a in adj[u]:
                    if cap[a] <= 0:
                        continue
                    v = to[a]
                    if v in done:
                        continue
                    nd = d + cost[a] + pu - pot[v]
                    if nd < dist.get(v, INF):
                        dist[v] = nd
                        prev[v] = a
                        heapq.heappush(heap, (nd, v))
            if self.t not in done:
                break
            dt = dist[self.t]
            # Johnson potentials with an early stop: settled nodes get dist - dt, every other node 0 (the same as
            # adding min(dist, dt) everywhere, shifted by the constant -dt), so reduced costs stay non-negative.
            for v in done:
                pot[v] += dist[v] - dt
            v = self.t
            while v != s:
                a = prev[v]
                cap[a] -= 1
                cap[a ^ 1] += 1
                v = to[a ^ 1]
            flow += 1
        return flow, self._decompose(s, cap, flow)

    def _decompose(self, s, cap, k):
        used = {}
        for a in range(0, len(self.to), 2):
            f = self.cap0[a] - cap[a] if self.cap0[a] != INF else 0
            if f > 0 and self.edge[a] is not None:
                used.setdefault(self.to[a ^ 1], []).append(a)
        paths = []
        for _ in range(k):
            u, path, seen_nodes = s, [], {s: 0}
            while True:
                if u in self.sink_arcs and not used.get(u):
                    break
                lst = used.get(u)
                if not lst:
                    if u in self.sink_arcs:
                        break
                    return paths  # should not happen
                a = lst.pop()
                path.append(self.edge[a])
                u = self.to[a]
                if u in seen_nodes:  # drop a cycle
                    path = path[:seen_nodes[u]]
                    seen_nodes = {n: i for n, i in seen_nodes.items() if i <= len(path)}
                seen_nodes[u] = len(path)
                if u in self.sink_arcs and not used.get(u):
                    break
            paths.append(path)
        return paths

    # ------------------------------------------------------------------------------------------ plain max flow
    def max_flow(self, s, limit, removed_arcs=(), excluded_sinks=()):
        """Unit augmenting paths (BFS), stops at ``limit``."""
        cap = list(self.cap0)
        for a in removed_arcs:
            cap[a] = 0
        for sn in excluded_sinks:
            a = self.sink_arcs.get(sn)
            if a is not None:
                cap[a] = 0
        to, adj, t = self.to, self.adj, self.t
        flow = 0
        while flow < limit:
            prev = {s: None}
            q = [s]
            found = False
            for u in q:
                for a in adj[u]:
                    if cap[a] > 0 and to[a] not in prev:
                        prev[to[a]] = a
                        if to[a] == t:
                            found = True
                            break
                        q.append(to[a])
                if found:
                    break
            if not found:
                break
            v = t
            while v != s:
                a = prev[v]
                cap[a] -= 1
                cap[a ^ 1] += 1
                v = to[a ^ 1]
            flow += 1
        return flow


def analyse(fg: FlowGraph, s: int, max_exits: int, excluded_sinks=()):
    """Exit count, the routes, and the dangerous road for entry node s."""
    k, paths = fg.exits(s, max_exits, excluded_sinks)
    road = fg.road
    own = road.node_cell[s]
    first_use, ways_in = {}, {}
    for i, p in enumerate(paths):
        t = 0
        for j in p:
            for c, _ in road.seg[j]:
                if c == own:
                    continue
                if c not in first_use or t < first_use[c]:
                    first_use[c] = t
                ways_in.setdefault(c, {}).setdefault(road.source_way[j], set()).add(i)
            t += road.D[j]
    results = []
    for c in sorted(first_use):
        f = fg.max_flow(s, k, fg.cell_arcs.get(c, ()), excluded_sinks)
        way = sorted(ways_in[c].items(), key=lambda kv: (-len(kv[1]), kv[0]))[0][0]
        results.append({"cell": c, "way": way, "cut": k - f, "first_s": first_use[c],
                        "routes": sorted({i for v in ways_in[c].values() for i in v})})
    best = None
    if results:
        top = max(r["cut"] for r in results)
        tied = sorted((r for r in results if r["cut"] == top), key=lambda r: (r["first_s"], r["cell"]))
        best = dict(tied[0], tied=len(tied))
    return {"exits": k, "paths": paths, "danger": best, "cell_cuts": results}
