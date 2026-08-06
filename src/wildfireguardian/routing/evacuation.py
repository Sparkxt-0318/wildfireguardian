"""Evacuation routing that consumes the spread_v2 probabilistic hazard.

Deliverables 1-3. Two routers move a rural-elderly evacuee from an origin to a
safe destination over a georeferenced network; the contrast between them is
the project's headline.

- :func:`naive_route` — **fire-blind**: shortest-distance path to the nearest
  shelter (the status-quo "just run to the nearest exit"). It is then
  *evaluated* against the predicted hazard (does it walk into the future
  reach? how much exposure?), but its path never sees the fire.

- :func:`future_aware_route` — minimises cumulative **exposure** to the
  *predicted future* hazard on a time-expanded graph (Deliverable 2): a node
  is ``(location, time)`` and an edge traversed so the evacuee arrives at time
  ``t`` costs ``P(ignition at that location, t) x travel_time``. Locations
  whose predicted ignition probability at the arrival time is at/above an
  impassable cutoff are forbidden. It respects the moving, growing,
  severity-scaled reach envelope and reports the clearance margin.

The hazard is the :class:`~wildfireguardian.routing.hazard.HazardSequence`
produced by forward-simulating spread_v2 — consumed as-is, probabilistic, not
a deterministic front.

Walking speed: rural-elderly gait is slow (community-dwelling older adults
~0.6-0.8 m/s; we default to 0.7 m/s on the flat) and terrain-sensitive. Edge
speed uses an elderly-scaled Tobler (1993) hiking function so up/down slopes
slow the evacuee.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field

import networkx as nx
import numpy as np

from ..config import get as _cfg
from ..spread_v2.grid import CoarseGrid
from .future_front import RoadNetwork
from .hazard import HazardSequence

# Parameters below are sourced from config/default.yaml (PHASE 1-A). Each call
# passes the historical literal as an explicit fallback, so an absent or
# unreadable config degrades to the Round-2 values rather than to something new.

#: Default elderly walking speed on flat ground (m/s).
ELDERLY_FLAT_SPEED_MS: float = float(_cfg("pedestrian.elderly_flat_speed_ms", 0.7))
#: Floor so very steep edges never give an absurd (near-zero) speed.
_MIN_SPEED_MS: float = float(_cfg("pedestrian.min_speed_ms", 0.15))
#: Tobler (1993) hiking-function constants: w = B exp(-K |S + O|) km/h.
_TOBLER_BASE_KMH: float = float(_cfg("pedestrian.tobler_base_kmh", 6.0))
_TOBLER_SLOPE_COEFF: float = float(_cfg("pedestrian.tobler_slope_coeff", 3.5))
_TOBLER_SLOPE_OFFSET: float = float(_cfg("pedestrian.tobler_slope_offset", 0.05))


def elderly_speed_ms(slope_fraction: float, flat_speed_ms: float = ELDERLY_FLAT_SPEED_MS) -> float:
    """Elderly walking speed (m/s) on a given slope (rise/run).

    Tobler (1993) hiking function ``w = 6 exp(-3.5 |S + 0.05|)`` km/h gives
    ~1.4 m/s flat for a fit adult; we rescale so the flat speed is
    ``flat_speed_ms`` (default 0.7 m/s for rural elderly) and keep Tobler's
    slope dependence.
    """
    b, k, o = _TOBLER_BASE_KMH, _TOBLER_SLOPE_COEFF, _TOBLER_SLOPE_OFFSET
    tobler_flat = b * math.exp(-k * o)                    # km/h at S=0
    scale = (flat_speed_ms * 3.6) / tobler_flat           # m/s target -> km/h ratio
    w_kmh = b * math.exp(-k * abs(slope_fraction + o)) * scale
    return max(w_kmh / 3.6, _MIN_SPEED_MS)


# ---------------------------------------------------------------------------
# Network construction on the real fire extent
# ---------------------------------------------------------------------------


def build_evacuation_network(
    grid: CoarseGrid,
    elevation: np.ndarray,
    burnable_frac: np.ndarray,
    *,
    flat_speed_ms: float = ELDERLY_FLAT_SPEED_MS,
    water_burnable_max: float = 0.05,
    shoreline_is_safe: bool = True,
) -> RoadNetwork:
    """Build a walkable 8-connected network on the coarse grid's land cells.

    OSM (osmnx) is not reachable in this offline environment, so the network
    is a **synthetic lattice laid on the REAL DEM / land-cover extent** — node
    positions, elevations, slopes and the coast are all real; only the
    street topology is synthetic (clearly labelled). The routing algorithm is
    identical on a real OSM graph.

    Walkable cells are land (``burnable_frac > water_burnable_max`` is treated
    as land; open sea is excluded). Safe-destination nodes are land cells on
    the **coast** (adjacent to sea) — for the coastal Yeongdeok demonstration
    the shore is the real assembly direction — plus any large non-burnable
    open patch a fire cannot follow.
    """
    g = nx.Graph()
    nrows, ncols = grid.nrows, grid.ncols
    elev = np.where(np.isfinite(elevation), elevation, 0.0)
    is_land = burnable_frac > water_burnable_max
    is_sea = (burnable_frac <= water_burnable_max) & (elev < 30.0)

    def nid(r: int, c: int) -> int:
        return r * ncols + c

    for r in range(nrows):
        for c in range(ncols):
            if not is_land[r, c]:
                continue
            x, y = grid.center_xy(r, c)
            g.add_node(nid(r, c), x=x, y=y, row=r, col=c,
                       elevation=float(elev[r, c]),
                       burnable=float(burnable_frac[r, c]))

    cs = grid.cell_size_m
    diag = cs * math.sqrt(2.0)
    for r in range(nrows):
        for c in range(ncols):
            if not is_land[r, c]:
                continue
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                rr, ccol = r + dr, c + dc
                if not (0 <= rr < nrows and 0 <= ccol < ncols) or not is_land[rr, ccol]:
                    continue
                length = diag if (dr != 0 and dc != 0) else cs
                dz = abs(elev[rr, ccol] - elev[r, c])
                slope = dz / length
                speed = elderly_speed_ms(slope, flat_speed_ms)
                g.add_edge(nid(r, c), nid(rr, ccol),
                           length_m=length, time_min=(length / speed) / 60.0)

    # Safe destinations: land cells adjacent to the sea (coast access).
    shelters: set[int] = set()
    if shoreline_is_safe:
        for r in range(nrows):
            for c in range(ncols):
                if not is_land[r, c]:
                    continue
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        rr, ccol = r + dr, c + dc
                        if 0 <= rr < nrows and 0 <= ccol < ncols and is_sea[rr, ccol]:
                            if nid(r, c) in g:
                                shelters.add(nid(r, c))
    # Keep only shelters that are actually connected to the main component.
    if shelters and g.number_of_nodes():
        comps = list(nx.connected_components(g))
        main = max(comps, key=len) if comps else set()
        shelters = {s for s in shelters if s in main}

    return RoadNetwork(graph=g, shelters=shelters)


# ---------------------------------------------------------------------------
# Route results
# ---------------------------------------------------------------------------


@dataclass
class RouteResult:
    """Outcome of one evacuation solve, evaluated against the hazard."""

    kind: str                                  # "naive" | "future_aware"
    reached: bool
    route: list[int]
    target: int | None
    departure_min: float
    total_distance_m: float
    total_time_min: float
    arrival_times_min: list[float] = field(default_factory=list)   # clock time at each node
    node_hazard: list[float] = field(default_factory=list)         # hazard at each node on arrival
    exposure: float = 0.0                      # integral P(ignition) dt  (prob*min)
    max_hazard: float = 0.0                    # worst hazard encountered
    enters_hazard: bool = False                # ever at/above the impassable cutoff
    clearance_margin_min: float | None = None  # min time-to-cutoff slack on route
    note: str = ""

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "reached": self.reached,
            "route_len_nodes": len(self.route),
            "target": self.target,
            "departure_min": self.departure_min,
            "total_distance_m": round(self.total_distance_m, 1),
            "total_time_min": round(self.total_time_min, 2),
            "exposure": round(self.exposure, 4),
            "max_hazard": round(self.max_hazard, 4),
            "enters_hazard": self.enters_hazard,
            "clearance_margin_min": (None if self.clearance_margin_min is None
                                     else round(self.clearance_margin_min, 2)),
            "note": self.note,
        }


def _node_xy(net: RoadNetwork, n: int) -> tuple[float, float]:
    d = net.graph.nodes[n]
    return float(d["x"]), float(d["y"])


def _time_to_cutoff(hazard: HazardSequence, x: float, y: float, p_cut: float) -> float:
    """Earliest hazard time (min) at which a location reaches the cutoff (inf if never)."""
    for t in hazard.times_min:
        if hazard.prob_at(x, y, float(t)) >= p_cut:
            return float(t)
    return math.inf


def _evaluate_path(
    net: RoadNetwork, path: list[int], hazard: HazardSequence,
    departure_min: float, p_cut: float, kind: str, target: int | None,
) -> RouteResult:
    """Score a fixed path against the hazard (used by both routers)."""
    arrivals = [departure_min]
    for i in range(len(path) - 1):
        arrivals.append(arrivals[-1] + net.graph[path[i]][path[i + 1]]["time_min"])
    node_haz: list[float] = []
    exposure = 0.0
    max_haz = 0.0
    enters = False
    clearance = math.inf
    for i, n in enumerate(path):
        x, y = _node_xy(net, n)
        clk = arrivals[i]
        h = hazard.prob_at(x, y, clk)
        node_haz.append(h)
        max_haz = max(max_haz, h)
        if h >= p_cut:
            enters = True
        tc = _time_to_cutoff(hazard, x, y, p_cut)
        if math.isfinite(tc):
            clearance = min(clearance, tc - clk)
        if i < len(path) - 1:
            dt = net.graph[path[i]][path[i + 1]]["time_min"]
            exposure += h * dt
    total_dist = sum(net.graph[path[i]][path[i + 1]]["length_m"] for i in range(len(path) - 1))
    return RouteResult(
        kind=kind, reached=True, route=path, target=target,
        departure_min=departure_min,
        total_distance_m=total_dist, total_time_min=arrivals[-1] - departure_min,
        arrival_times_min=arrivals, node_hazard=node_haz,
        exposure=exposure, max_hazard=max_haz, enters_hazard=enters,
        clearance_margin_min=(None if math.isinf(clearance) else clearance),
    )


# ---------------------------------------------------------------------------
# Naive (fire-blind) router
# ---------------------------------------------------------------------------


#: Objective for :func:`naive_route`. ``"length_m"`` is the committed Round-2
#: behaviour and the DEFAULT; do not change it without re-reporting.
NAIVE_OBJECTIVES: tuple[str, ...] = ("length_m", "time_min")


def naive_route(
    net: RoadNetwork,
    start: int,
    hazard: HazardSequence,
    *,
    departure_min: float = 0.0,
    p_cut: float = 0.5,
    objective: str = "length_m",
) -> RouteResult:
    """Fire-blind shortest path to the nearest shelter, then scored against the hazard.

    Parameters
    ----------
    objective
        ``"length_m"`` (DEFAULT, and the committed Round-2 behaviour) minimises
        DISTANCE. ``"time_min"`` minimises TRAVERSAL TIME.

        The distinction only matters once edge times stop being proportional to
        length — i.e. once DEM slope is applied. Under distance minimisation the
        chosen path is slope-invariant by construction, which is why PHASE 2
        measured zero path changes from slope across 460 origins
        (docs/slope_integration.md). Under time minimisation a walker may prefer
        a longer, gentler detour to a steep short-cut.

        The default is NOT changed: the committed 407- and 459-origin results
        are distance-ranked, and reinterpreting them requires that behaviour to
        stay reachable.
    """
    if not net.shelters:
        raise ValueError("network has no shelters")
    if objective not in NAIVE_OBJECTIVES:
        raise ValueError(f"objective must be one of {NAIVE_OBJECTIVES}, got {objective!r}")
    # One Dijkstra from the origin to all nodes, then pick the nearest
    # reachable shelter (far cheaper than a Dijkstra per shelter).
    lengths, paths = nx.single_source_dijkstra(net.graph, start, weight=objective)
    best_path: list[int] | None = None
    best_len = math.inf
    best_target = None
    for shelter in net.shelters:
        if shelter in lengths and lengths[shelter] < best_len:
            best_len, best_path, best_target = lengths[shelter], paths[shelter], shelter
    if best_path is None:
        return RouteResult(kind="naive", reached=False, route=[], target=None,
                           departure_min=departure_min, total_distance_m=0.0,
                           total_time_min=0.0, note="no path to any shelter")
    # _evaluate_path recomputes distance and time from the edges, so the reported
    # totals are correct under either objective.
    kind = "naive" if objective == "length_m" else "naive_time"
    return _evaluate_path(net, best_path, hazard, departure_min, p_cut, kind, best_target)


# ---------------------------------------------------------------------------
# Future-aware router (time-expanded, exposure-minimising)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TimeExpandedField:
    """The node x time-bin hazard table, and everything derived from it.

    Round-3 PHASE 20.

    WHY THIS IS A SEPARATE OBJECT
    -----------------------------
    :func:`future_aware_route` needs a table of P(ignition) at every node at
    every time bin, so that its inner Dijkstra loop is an O(1) array lookup
    rather than millions of bilinear samples. Building it costs one
    ``prob_at_points`` call per bin over every node — for Yeongdeok, 61 calls
    over 8,443 nodes, about 515,000 samples.

    ⚠ THE TABLE DOES NOT DEPEND ON ``start``. It is a pure function of the
    network's node coordinates, the hazard, the departure time, the budget and
    the step. A 459-series scan holds all five fixed across its origins, so the
    committed code was rebuilding the *same array* 458 times — measured at
    35–58 % of the whole scan (``docs/service_layer.md`` §5.1).

    Hoisting it is memoisation of a pure function, so the values are identical
    by construction rather than by argument. That is the only reason this
    optimisation was allowed: there is no version of it that returns a
    different number.
    """

    nodes: list[int]
    idx: dict[int, int]
    #: ``(n_nodes, n_bins)``; ``table[i, k]`` is P(ignition) at ``nodes[i]`` at
    #: ``departure_min + k * time_step_min``.
    table: np.ndarray
    n_bins: int
    departure_min: float
    time_budget_min: float
    p_cut: float
    time_step_min: float
    #: Earliest time each node reaches the cutoff. Carried because the
    #: committed code computed it; nothing reads it today.
    t_cut: np.ndarray

    def check(self, net: RoadNetwork, start: int, *, departure_min: float,
              time_budget_min: float, p_cut: float, time_step_min: float) -> None:
        """Refuse a field that was built for a different question.

        A silently mismatched table would not raise — it would return a
        plausible route computed against the wrong hazard. So the four scalars
        are compared exactly and the node set is size-checked, and a caller
        that gets it wrong gets an exception instead of an answer.
        """
        if (departure_min, time_budget_min, p_cut, time_step_min) != (
                self.departure_min, self.time_budget_min, self.p_cut,
                self.time_step_min):
            raise ValueError(
                "time-expanded field was built for different parameters: "
                f"built for (departure={self.departure_min}, "
                f"budget={self.time_budget_min}, p_cut={self.p_cut}, "
                f"step={self.time_step_min}), asked for (departure="
                f"{departure_min}, budget={time_budget_min}, p_cut={p_cut}, "
                f"step={time_step_min})")
        if len(self.nodes) != net.graph.number_of_nodes():
            raise ValueError(
                f"time-expanded field has {len(self.nodes)} nodes but the "
                f"network has {net.graph.number_of_nodes()}")
        if start not in self.idx:
            raise ValueError(f"origin {start} is not in the field's node set")


def build_time_expanded_field(
    net: RoadNetwork,
    hazard: HazardSequence,
    *,
    departure_min: float = 0.0,
    time_budget_min: float = 240.0,
    p_cut: float = 0.5,
    time_step_min: float = 5.0,
) -> TimeExpandedField:
    """Build the node x time-bin hazard table once, for reuse across origins.

    The body is the committed one, moved rather than rewritten: same node
    order, same bin arithmetic, same ``prob_at_points`` calls in the same
    order. Moving code that produces floats is the only way to keep the floats
    identical.
    """
    nodes = list(net.graph.nodes)
    idx = {n: i for i, n in enumerate(nodes)}
    nx_arr = np.array([net.graph.nodes[n]["x"] for n in nodes], float)
    ny_arr = np.array([net.graph.nodes[n]["y"] for n in nodes], float)
    n_bins = int(math.ceil(time_budget_min / time_step_min)) + 1
    table = np.empty((len(nodes), n_bins), float)
    for k in range(n_bins):
        table[:, k] = hazard.prob_at_points(nx_arr, ny_arr,
                                            departure_min + k * time_step_min)
    # Earliest time each node reaches the cutoff (for clearance reporting).
    over = table >= p_cut
    t_cut = np.where(over.any(axis=1),
                     departure_min + over.argmax(axis=1) * time_step_min, math.inf)
    return TimeExpandedField(
        nodes=nodes, idx=idx, table=table, n_bins=n_bins,
        departure_min=departure_min, time_budget_min=time_budget_min,
        p_cut=p_cut, time_step_min=time_step_min, t_cut=t_cut)


def future_aware_route(
    net: RoadNetwork,
    start: int,
    hazard: HazardSequence,
    *,
    departure_min: float = 0.0,
    time_budget_min: float = 240.0,
    p_cut: float = 0.5,
    time_step_min: float = 5.0,
    field: TimeExpandedField | None = None,
) -> RouteResult:
    """Exposure-minimising evacuation on a time-expanded graph.

    ``field`` is an optional precomputed :class:`TimeExpandedField`. Omitted,
    one is built here and the function behaves exactly as it always has — every
    existing caller is unaffected. Supplied, the identical table is reused
    instead of rebuilt, which is what makes a 458-origin scan stop paying for
    the same array 458 times. The field is validated against this call's
    parameters before it is used.

    State is ``(node, time_bin)``; time advances by each edge's elderly
    traversal time rounded **up** to ``time_step_min`` (conservative: the
    evacuee meets slightly-grown hazard). Edge cost is the predicted ignition
    probability at the destination at arrival time, integrated over travel
    time. Edges into a location whose hazard >= ``p_cut`` at arrival are
    forbidden, as is starting inside the cutoff. Among exposure-minimal
    routes, earlier arrival breaks ties. Returns a clean "no safe route"
    result when the growing envelope overtakes every shelter in time.
    """
    if not net.shelters:
        raise ValueError("network has no shelters")

    # The node x time-bin hazard table makes the inner Dijkstra loop an O(1)
    # array lookup instead of millions of bilinear samples. Time bin k
    # corresponds to clock = departure_min + k*time_step_min; travel time is
    # rounded UP to a bin (conservative: the evacuee meets slightly-grown
    # hazard). True travel clock is still carried exactly for edge timing.
    if field is None:
        field = build_time_expanded_field(
            net, hazard, departure_min=departure_min,
            time_budget_min=time_budget_min, p_cut=p_cut,
            time_step_min=time_step_min)
    else:
        field.check(net, start, departure_min=departure_min,
                    time_budget_min=time_budget_min, p_cut=p_cut,
                    time_step_min=time_step_min)
    nodes, idx, table, n_bins = field.nodes, field.idx, field.table, field.n_bins

    s_idx = idx[start]
    if table[s_idx, 0] >= p_cut:
        return RouteResult(kind="future_aware", reached=False, route=[], target=None,
                           departure_min=departure_min, total_distance_m=0.0,
                           total_time_min=0.0, enters_hazard=True,
                           note="origin already at/above the impassable cutoff at departure")

    shelters_idx = {idx[s] for s in net.shelters if s in idx}
    start_state = (s_idx, 0)
    # Dijkstra over cumulative exposure; tie-break by clock then node.
    dist: dict[tuple[int, int], float] = {start_state: 0.0}
    prev: dict[tuple[int, int], tuple[int, int]] = {}
    pq: list[tuple[float, float, int, int]] = [(0.0, departure_min, s_idx, 0)]
    visited: set[tuple[int, int]] = set()
    goal_state: tuple[int, int] | None = None

    while pq:
        exp_u, clk_u, ui, ub = heapq.heappop(pq)
        state = (ui, ub)
        if state in visited:
            continue
        visited.add(state)
        if ui in shelters_idx:
            goal_state = state
            break
        for v in net.graph.neighbors(nodes[ui]):
            vi = idx[v]
            tt = net.graph[nodes[ui]][v]["time_min"]
            arrive = clk_u + tt
            if arrive - departure_min > time_budget_min + 1e-9:
                continue
            kb = int(math.ceil((arrive - departure_min) / time_step_min))
            if kb >= n_bins:
                kb = n_bins - 1
            hv = table[vi, kb]
            if hv >= p_cut:
                continue  # impassable at the time we would arrive
            nexp = exp_u + hv * tt
            vstate = (vi, kb)
            if vstate in visited:
                continue
            if nexp < dist.get(vstate, math.inf) - 1e-12:
                dist[vstate] = nexp
                prev[vstate] = state
                heapq.heappush(pq, (nexp, arrive, vi, kb))

    if goal_state is None:
        return RouteResult(kind="future_aware", reached=False, route=[], target=None,
                           departure_min=departure_min, total_distance_m=0.0,
                           total_time_min=0.0,
                           note="no safe route: hazard envelope overtakes all shelters within budget")

    # Reconstruct the node path (states are (node_index, time_bin)).
    chain = [goal_state]
    while chain[-1] != start_state:
        chain.append(prev[chain[-1]])
    chain.reverse()
    path = [nodes[i] for (i, _b) in chain]
    res = _evaluate_path(net, path, hazard, departure_min, p_cut, "future_aware",
                         nodes[goal_state[0]])
    return res


__all__ = [
    "ELDERLY_FLAT_SPEED_MS",
    "elderly_speed_ms",
    "NAIVE_OBJECTIVES",
    "TimeExpandedField",
    "build_evacuation_network",
    "build_time_expanded_field",
    "RouteResult",
    "naive_route",
    "future_aware_route",
]
