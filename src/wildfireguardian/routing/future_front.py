"""Evacuation routing that avoids the fire's *future* front position.

This is the Session-5 spine: the core contribution. A naive evacuation
router sends people along the shortest path to the nearest shelter,
ignoring where the fire will be when they get there — which can route an
evacuee straight into the oncoming front. This module instead treats the
predicted fire front as a **moving obstacle** and solves a
time-dependent shortest path that keeps the evacuee out of the front's
footprint at every moment of their journey.

Inputs
------
- A road / pedestrian network (:class:`RoadNetwork`): a ``networkx`` graph
  whose nodes carry EPSG:5179 ``(x, y)`` positions and whose edges carry a
  ``length_m``. The demo builds a synthetic georeferenced grid for the
  Yeongdeok region (no OSM download available in this sandbox).
- A **predicted front sequence**: ``[(time_min, Polygon), ...]`` giving the
  cumulative on-fire / burned footprint at each forecast time, in EPSG:5179.
  This comes from the spread model (Deliverable 4). The router is agnostic
  to how the front is produced; its safety is only as good as that
  prediction (see the honest note in the notebook / report).

Method
------
1. :func:`front_arrival_times` computes, per node, the earliest forecast
   time at which the front covers it (``inf`` if it never burns).
2. :func:`time_dependent_evacuation` runs a Dijkstra on edge *travel time*
   (edge length / walking speed) from the resident's start node, **pruning**
   any node the evacuee would reach at or after the front arrives there
   (within a safety margin). The target is any reachable shelter. It also
   reports the **latest safe departure time** and the temporal **clearance
   margin** along the chosen route.
3. :func:`naive_shortest_path` is the contrast: the plain
   shortest-distance path to the nearest shelter, ignoring the fire — then
   evaluated for whether it actually enters the front.

Walking speed defaults to ~0.6 m/s (rural elderly), configurable.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field

import networkx as nx
from shapely.geometry import Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

#: Default walking speed for a rural-elderly evacuee, m/s.
ELDERLY_WALK_SPEED_MS: float = 0.6


# ---------------------------------------------------------------------------
# Road network
# ---------------------------------------------------------------------------


@dataclass
class RoadNetwork:
    """A georeferenced pedestrian/road network in EPSG:5179.

    Nodes are integers with ``graph.nodes[n]['x']`` / ``['y']`` in metres.
    Edges carry ``['length_m']``. ``shelters`` is the set of safe-destination
    nodes.
    """

    graph: nx.Graph
    shelters: set[int] = field(default_factory=set)

    def node_xy(self, n: int) -> tuple[float, float]:
        d = self.graph.nodes[n]
        return float(d["x"]), float(d["y"])

    def nearest_node(self, x: float, y: float) -> int:
        best, best_d2 = None, math.inf
        for n, d in self.graph.nodes(data=True):
            d2 = (d["x"] - x) ** 2 + (d["y"] - y) ** 2
            if d2 < best_d2:
                best, best_d2 = n, d2
        assert best is not None
        return best

    @classmethod
    def synthetic_grid(
        cls,
        origin_xy: tuple[float, float],
        nx_cells: int,
        ny_cells: int,
        spacing_m: float,
        shelter_nodes: set[int] | None = None,
    ) -> "RoadNetwork":
        """Build a synthetic 4-connected grid road network in EPSG:5179.

        Nodes are laid on a regular lattice starting at ``origin_xy``. This
        stands in for a real OSM network (unavailable offline); the routing
        algorithm is identical on a real graph.
        """
        g = nx.Graph()
        ox, oy = origin_xy

        def nid(ix: int, iy: int) -> int:
            return iy * nx_cells + ix

        for iy in range(ny_cells):
            for ix in range(nx_cells):
                g.add_node(nid(ix, iy), x=ox + ix * spacing_m, y=oy + iy * spacing_m)
        for iy in range(ny_cells):
            for ix in range(nx_cells):
                if ix + 1 < nx_cells:
                    g.add_edge(nid(ix, iy), nid(ix + 1, iy), length_m=spacing_m)
                if iy + 1 < ny_cells:
                    g.add_edge(nid(ix, iy), nid(ix, iy + 1), length_m=spacing_m)
        return cls(graph=g, shelters=set(shelter_nodes or set()))


# ---------------------------------------------------------------------------
# Front arrival times
# ---------------------------------------------------------------------------


def _cumulative_front(front_sequence: list[tuple[float, BaseGeometry]]) -> list[tuple[float, BaseGeometry]]:
    """Make the front footprints cumulative (monotone non-shrinking) in time."""
    seq = sorted(front_sequence, key=lambda x: x[0])
    out: list[tuple[float, BaseGeometry]] = []
    acc: BaseGeometry | None = None
    for t, poly in seq:
        if poly is None or poly.is_empty:
            out.append((t, acc if acc is not None else Polygon()))
            continue
        acc = poly if acc is None else unary_union([acc, poly])
        out.append((t, acc))
    return out


def front_arrival_times(
    network: RoadNetwork,
    front_sequence: list[tuple[float, BaseGeometry]],
) -> dict[int, float]:
    """Earliest forecast time (min) at which the front covers each node.

    Returns ``{node: arrival_min}`` with ``inf`` for nodes the front never
    reaches within the forecast horizon.
    """
    cum = _cumulative_front(front_sequence)
    arrival: dict[int, float] = {n: math.inf for n in network.graph.nodes}
    for n, d in network.graph.nodes(data=True):
        pt = Point(d["x"], d["y"])
        for t, poly in cum:
            if not poly.is_empty and poly.contains(pt):
                arrival[n] = t
                break
    return arrival


# ---------------------------------------------------------------------------
# Evacuation results
# ---------------------------------------------------------------------------


@dataclass
class EvacuationResult:
    """Outcome of one evacuation solve."""

    reached: bool
    route: list[int]
    target: int | None
    arrival_times_min: list[float]            # cumulative travel time at each node
    total_distance_m: float
    total_time_min: float
    enters_front: bool                         # does the route ever occupy a burned node?
    latest_safe_departure_min: float | None    # latest t0 that still clears the front
    clearance_margin_min: float | None         # min (front_arrival - arrival_clock) on route

    def as_dict(self) -> dict:
        return {
            "reached": self.reached,
            "route_len_nodes": len(self.route),
            "target": self.target,
            "total_distance_m": self.total_distance_m,
            "total_time_min": self.total_time_min,
            "enters_front": self.enters_front,
            "latest_safe_departure_min": self.latest_safe_departure_min,
            "clearance_margin_min": self.clearance_margin_min,
        }


def _edge_minutes(network: RoadNetwork, u: int, v: int, speed_ms: float) -> float:
    length = network.graph[u][v]["length_m"]
    return (length / speed_ms) / 60.0


# ---------------------------------------------------------------------------
# Future-front-aware routing
# ---------------------------------------------------------------------------


def time_dependent_evacuation(
    network: RoadNetwork,
    start: int,
    front_arrival: dict[int, float],
    *,
    walking_speed_ms: float = ELDERLY_WALK_SPEED_MS,
    departure_time_min: float = 0.0,
    safety_margin_min: float = 0.0,
) -> EvacuationResult:
    """Time-dependent shortest path that never enters the predicted front.

    Dijkstra on edge travel time, pruning any node the evacuee would reach
    at/after ``front_arrival[node] - safety_margin_min`` (clock time
    ``departure_time_min + cumulative_travel``). Target: any shelter in
    ``network.shelters`` reachable under that constraint. Minimises total
    travel time.
    """
    if start not in network.graph:
        raise ValueError(f"start node {start} not in network")

    def forbidden(node: int, clock: float) -> bool:
        fa = front_arrival.get(node, math.inf)
        return clock >= fa - safety_margin_min

    # If the start is already in the front, no safe route.
    if forbidden(start, departure_time_min):
        return EvacuationResult(
            reached=False, route=[], target=None, arrival_times_min=[],
            total_distance_m=0.0, total_time_min=0.0, enters_front=True,
            latest_safe_departure_min=None, clearance_margin_min=None,
        )

    dist: dict[int, float] = {start: 0.0}
    prev: dict[int, int] = {}
    pq: list[tuple[float, int]] = [(0.0, start)]
    visited: set[int] = set()
    target: int | None = None

    while pq:
        g, u = heapq.heappop(pq)
        if u in visited:
            continue
        visited.add(u)
        if u in network.shelters:
            target = u
            break
        for v in network.graph.neighbors(u):
            if v in visited:
                continue
            ng = g + _edge_minutes(network, u, v, walking_speed_ms)
            if forbidden(v, departure_time_min + ng):
                continue
            if ng < dist.get(v, math.inf):
                dist[v] = ng
                prev[v] = u
                heapq.heappush(pq, (ng, v))

    if target is None:
        return EvacuationResult(
            reached=False, route=[], target=None, arrival_times_min=[],
            total_distance_m=0.0, total_time_min=0.0, enters_front=False,
            latest_safe_departure_min=None, clearance_margin_min=None,
        )

    # Reconstruct.
    route = [target]
    while route[-1] != start:
        route.append(prev[route[-1]])
    route.reverse()
    arrivals = [dist[n] for n in route]
    total_dist = sum(
        network.graph[route[i]][route[i + 1]]["length_m"]
        for i in range(len(route) - 1)
    )
    # Latest safe departure & clearance over finite-arrival nodes.
    latest_dep = math.inf
    clearance = math.inf
    for n, a in zip(route, arrivals):
        fa = front_arrival.get(n, math.inf)
        if math.isfinite(fa):
            latest_dep = min(latest_dep, fa - safety_margin_min - a)
            clearance = min(clearance, fa - (departure_time_min + a))
    return EvacuationResult(
        reached=True, route=route, target=target, arrival_times_min=arrivals,
        total_distance_m=total_dist, total_time_min=dist[target],
        enters_front=False,
        latest_safe_departure_min=(None if math.isinf(latest_dep) else latest_dep),
        clearance_margin_min=(None if math.isinf(clearance) else clearance),
    )


# ---------------------------------------------------------------------------
# Naive (fire-blind) contrast
# ---------------------------------------------------------------------------


def naive_shortest_path(
    network: RoadNetwork,
    start: int,
    *,
    walking_speed_ms: float = ELDERLY_WALK_SPEED_MS,
    departure_time_min: float = 0.0,
    front_arrival: dict[int, float] | None = None,
    safety_margin_min: float = 0.0,
) -> EvacuationResult:
    """Plain shortest-distance path to the nearest shelter, ignoring the fire.

    If ``front_arrival`` is supplied, the result is *evaluated* for safety
    (``enters_front``) but the path itself is NOT fire-aware — this is the
    baseline that can walk an evacuee into the oncoming front.
    """
    if not network.shelters:
        raise ValueError("network has no shelters")
    # Dijkstra on distance to the nearest shelter (multi-target).
    best: EvacuationResult | None = None
    for shelter in network.shelters:
        try:
            length, path = nx.single_source_dijkstra(
                network.graph, start, target=shelter, weight="length_m",
            )
        except nx.NetworkXNoPath:
            continue
        if best is None or length < best.total_distance_m:
            # cumulative travel times
            arrivals = [0.0]
            for i in range(len(path) - 1):
                arrivals.append(arrivals[-1] + _edge_minutes(
                    network, path[i], path[i + 1], walking_speed_ms))
            enters = False
            clearance = math.inf
            if front_arrival is not None:
                for n, a in zip(path, arrivals):
                    fa = front_arrival.get(n, math.inf)
                    if departure_time_min + a >= fa - safety_margin_min:
                        enters = True
                    if math.isfinite(fa):
                        clearance = min(clearance, fa - (departure_time_min + a))
            best = EvacuationResult(
                reached=True, route=path, target=shelter, arrival_times_min=arrivals,
                total_distance_m=length, total_time_min=arrivals[-1],
                enters_front=enters,
                latest_safe_departure_min=None,
                clearance_margin_min=(None if math.isinf(clearance) else clearance),
            )
    if best is None:
        return EvacuationResult(
            reached=False, route=[], target=None, arrival_times_min=[],
            total_distance_m=0.0, total_time_min=0.0, enters_front=False,
            latest_safe_departure_min=None, clearance_margin_min=None,
        )
    return best


__all__ = [
    "ELDERLY_WALK_SPEED_MS",
    "RoadNetwork",
    "front_arrival_times",
    "EvacuationResult",
    "time_dependent_evacuation",
    "naive_shortest_path",
]
