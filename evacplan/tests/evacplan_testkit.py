"""Test helpers: tiny hand-built SYNTHETIC instances and scenario sets.

Grid convention used throughout the tests: an H x W hazard grid of ``CELL`` m cells with the
north-up affine ``(CELL, 0, 0, 0, -CELL, H * CELL)``, so cell (r, c) spans
x in [c*CELL, (c+1)*CELL] and y in [(H-r-1)*CELL, (H-r)*CELL]. Road node ``n{r}_{c}`` sits at the
centre of cell (r, c); edge ``n{r}_{c}>n{r2}_{c2}`` joins 4-neighbours (both directions).
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from hazard_contract import HeatSource, ScenarioMeta, ScenarioSet
from evacplan.schema import (
    Board, Budgets, ClassCounts, ClassDurations, Drive, Edge, Facility, HazardRef, Instance, Itinerary, Node,
    RoadGraph, Shelter, Solution, Unload, Vehicle, Wait,
)

INF, NAN = np.inf, np.nan
CELL = 100.0
CRS = 3310
# The repo's packet parameters (wfg_latest): q_rad = 1.40598 kW/m^2 with T = 3970.46 s (scalar policy).
PACKET_HEAT = dict(fuel_load_kg_m2=10.0, consumed_fraction=0.1, heat_content_kj_kg=18608.0, radiative_fraction=0.3,
                   burn_duration_s=3970.4642815249267, emission_height_m=5.0, receiver_height_m=0.0)


def make_set(ig, ex=None, sup=None, *, cell=CELL, horizon=10_000.0, burn=1000.0) -> ScenarioSet:
    """SYNTHETIC scenario set from ignition times ``[K, H, W]`` or ``[H, W]`` (nan = unknown)."""
    ig = np.asarray(ig, dtype=float)
    if ig.ndim == 2:
        ig = ig[None]
    K, H, W = ig.shape
    if ex is None:
        ex = np.where(np.isfinite(ig), ig + burn, ig)
    ex = np.asarray(ex, dtype=float).reshape(K, H, W)
    if sup is None:
        sup = ~np.isnan(ig) & ~np.isnan(ex)
    sup = np.asarray(sup, dtype=bool).reshape(K, H, W)
    meta = ScenarioMeta(
        crs_epsg=CRS, transform=(cell, 0.0, 0.0, 0.0, -cell, H * cell), height=H, width=W, K=K,
        issue_time_utc=datetime(2021, 8, 17, tzinfo=timezone.utc), horizon_s=float(horizon), source="synthetic",
        synthetic=True, model_version="evacplan-test", weather_source="SYNTHETIC",
        heat_source=HeatSource(**PACKET_HEAT),
    )
    return ScenarioSet(ig, ex, sup, meta)


def quiet(H: int, W: int, K: int = 1) -> np.ndarray:
    """Ignition array with nothing burning."""
    return np.full((K, H, W), INF)


def nid(r: int, c: int) -> str:
    return f"n{r}_{c}"


def eid(a: tuple[int, int], b: tuple[int, int]) -> str:
    return f"{nid(*a)}>{nid(*b)}"


def centre(r: int, c: int, H: int, cell: float = CELL) -> tuple[float, float]:
    return (c * cell + cell / 2, (H - r) * cell - cell / 2)


def grid_graph(H: int, W: int, *, cell: float = CELL, travel: float = 50.0, waitable=True,
               forbidden=(), extra_nodes=(), extra_edges=()) -> RoadGraph:
    """4-neighbour lattice on the cell centres. ``waitable``: bool or a set of (r, c)."""
    nodes = []
    for r in range(H):
        for c in range(W):
            x, y = centre(r, c, H, cell)
            w = waitable if isinstance(waitable, bool) else (r, c) in waitable
            nodes.append(Node(id=nid(r, c), x=x, y=y, waitable=w))
    edges = []
    for r in range(H):
        for c in range(W):
            for dr, dc in ((0, 1), (1, 0), (0, -1), (-1, 0)):
                r2, c2 = r + dr, c + dc
                if 0 <= r2 < H and 0 <= c2 < W:
                    edges.append(Edge(id=eid((r, c), (r2, c2)), u=nid(r, c), v=nid(r2, c2), travel_time_s=travel))
    return RoadGraph(crs_epsg=CRS, nodes=nodes + list(extra_nodes), edges=edges + list(extra_edges),
                     forbidden_turns=list(forbidden))


def path(*cells: tuple[int, int]) -> list[str]:
    """Edge ids along consecutive lattice cells."""
    return [eid(a, b) for a, b in zip(cells, cells[1:])]


def manhattan(a: tuple[int, int], b: tuple[int, int], rows_first: bool = True) -> list[tuple[int, int]]:
    (r, c), (r2, c2) = a, b
    out = [(r, c)]

    def step_rows():
        nonlocal r
        while r != r2:
            r += 1 if r2 > r else -1
            out.append((r, c))

    def step_cols():
        nonlocal c
        while c != c2:
            c += 1 if c2 > c else -1
            out.append((r, c))

    if rows_first:
        step_rows()
        step_cols()
    else:
        step_cols()
        step_rows()
    return out


def facility(fid: str, node: str, amb=0, wc=0, bed=0, *, board=(10.0, 20.0, 30.0), release=0.0) -> Facility:
    return Facility(id=fid, node=node, residents=ClassCounts(ambulatory=amb, wheelchair=wc, bedbound=bed),
                    boarding_s=ClassDurations(ambulatory=board[0], wheelchair=board[1], bedbound=board[2]),
                    release_s=release)


def vehicle(vid: str, depot: str, *, start=0.0, seats=8, wc=2, stretchers=1, shift=None) -> Vehicle:
    return Vehicle(id=vid, depot=depot, start_s=start, seats=seats, wheelchair_slots=wc, stretcher_slots=stretchers,
                   shift_limit_s=shift)


def shelter(sid: str, node: str, cap=(100, 100, 100), *, windows=((0.0, 1e6),), unload=(5.0, 10.0, 15.0)) -> Shelter:
    return Shelter(id=sid, node=node, capacity=ClassCounts.of(cap), open_windows=[tuple(w) for w in windows],
                   unloading_s=ClassDurations(ambulatory=unload[0], wheelchair=unload[1], bedbound=unload[2]))


def instance(graph: RoadGraph, *, facilities=(), vehicles=(), shelters=(), peak=10.0, dose=100.0, offset=0.0,
             name="SYNTHETIC-test", scenario_set="hazard") -> Instance:
    return Instance(name=name, synthetic=True, graph=graph, facilities=list(facilities), vehicles=list(vehicles),
                    shelters=list(shelters),
                    hazard=HazardRef(scenario_set=scenario_set, t0_offset_s=offset,
                                     budgets=Budgets(peak_kw_m2=peak, dose_kj_m2=dose)))


def counts(amb=0, wc=0, bed=0) -> ClassCounts:
    return ClassCounts(ambulatory=amb, wheelchair=wc, bedbound=bed)


def drive(edges, depart) -> Drive:
    return Drive(edges=list(edges), depart_s=float(depart))


def wait(node, duration) -> Wait:
    return Wait(node=node, duration_s=float(duration))


def board(fid, amb=0, wc=0, bed=0) -> Board:
    return Board(facility=fid, counts=counts(amb, wc, bed))


def unload(sid, amb=0, wc=0, bed=0) -> Unload:
    return Unload(shelter=sid, counts=counts(amb, wc, bed))


def itinerary(vid, *actions) -> Itinerary:
    return Itinerary(vehicle=vid, actions=list(actions))


def solution(*itineraries, name="SYNTHETIC-test", method="hand") -> Solution:
    return Solution(instance=name, method=method, itineraries=list(itineraries))
