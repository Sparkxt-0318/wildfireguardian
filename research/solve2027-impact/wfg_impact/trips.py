"""Path A fire-free trip times and legal-walk lengths on the routing graph (standard library only).

A legal walk follows the routing kit's rule (``integration/kit/routing_candidate/baseline/temporal_contract.py``
``check_mission``): each EDGE leg starts at the current node and ``(incoming edge, edge)`` is not in
``forbidden_turns``; the first leg has no incoming edge. Travel time of an edge = ``travel_ticks`` x ``dt``
(the graph assumes 40 km/h rounded up to whole 1 s ticks). Waiting never shortens a fire-free trip, so the fastest
fire-free trip is a turn-aware Dijkstra over directed edges (state = the last edge driven).

The fire-free trip decides whether a departure could be checked at all inside the scenario window: the kit accepts a
destination arrival only if arrival + required stay <= min(destination window close, hazard valid_until)
(``check_mission``: ``end = t + dwell; end <= horizon and ... end <= close``). If even the fastest fire-free trip does
not fit, no route can be checked at that departure whatever the fire does ("window-limited").
"""
from __future__ import annotations

import heapq

from .maxflow import RoadGraph

_INF = float('inf')


def fastest_trips(g: RoadGraph, origin: int, dests: list[int]) -> dict[int, int]:
    """Fastest fire-free legal travel time in ticks from ``origin`` to each destination node (None if unreachable)."""
    dist: dict[int, int] = {}
    heap = []
    for b in g.out_edges[origin]:
        t = g.ticks[b]
        if t < dist.get(b, _INF):
            dist[b] = t
            heapq.heappush(heap, (t, b))
    remaining, best = set(dests), {}
    while heap and remaining:
        t, a = heapq.heappop(heap)
        if t != dist[a]:
            continue
        v = g.ev[a]
        if v in remaining:                      # first settled edge into v = earliest arrival at v
            best[v] = t
            remaining.discard(v)
        for b in g.out_edges[v]:
            if (a, b) in g.forbidden:
                continue
            nt = t + g.ticks[b]
            if nt < dist.get(b, _INF):
                dist[b] = nt
                heapq.heappush(heap, (nt, b))
    return {d: best.get(d) for d in dests}


def walk_length_to_edge_end(g: RoadGraph, origin: int, target_edge: int) -> float:
    """Shortest legal-walk length (sum of straight edge chords, EPSG:5179 metres) from ``origin`` to the end of
    ``target_edge`` (inclusive)."""
    dist: dict[int, float] = {}
    heap = []
    for b in g.out_edges[origin]:
        d = g.edge_length_m(b)
        if d < dist.get(b, _INF):
            dist[b] = d
            heapq.heappush(heap, (d, b))
    while heap:
        d, a = heapq.heappop(heap)
        if d != dist[a]:
            continue
        if a == target_edge:
            return d
        v = g.ev[a]
        for b in g.out_edges[v]:
            if (a, b) in g.forbidden:
                continue
            nd = d + g.edge_length_m(b)
            if nd < dist.get(b, _INF):
                dist[b] = nd
                heapq.heappush(heap, (nd, b))
    raise ValueError('target edge not reachable from the origin')
