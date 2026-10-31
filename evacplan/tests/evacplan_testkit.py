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


# ------------------------------------------------------------------------- random test cases
def random_case(seed: int, *, p_unknown: float = 0.04, p_burn: float = 0.08):
    """A small random SYNTHETIC instance, scenario set and (often imperfect) plan, from one seed.

    Plans are purposeful (depot -> facility -> shelter trips on lattice paths) with random idles,
    waits, partial or excessive boardings and partial unloads, so every state and many validator
    issues occur. Returns ``(instance, scenario_set, solution)``.
    """
    rng = np.random.default_rng(seed)
    K, H, W = int(rng.integers(1, 3)), int(rng.integers(3, 6)), int(rng.integers(3, 6))
    horizon = float(rng.choice([400.0, 900.0, 5000.0]))
    kind = rng.choice(3, p=[1 - p_unknown - p_burn, p_burn, p_unknown], size=(K, H, W))
    ig = np.full((K, H, W), INF)
    ex = np.full((K, H, W), INF)
    burn, unk = kind == 1, kind == 2
    ig[burn] = rng.choice([-80.0, 0.0, 90.0, 160.0, 260.0, 420.0, 700.0], size=int(burn.sum()))
    ex[burn] = ig[burn] + rng.choice([15.0, 60.0, 250.0, 5000.0], size=int(burn.sum()))
    ig[unk] = NAN
    ex[unk] = NAN
    ss = make_set(ig, ex, horizon=horizon)

    travel = float(rng.choice([20.0, 35.0, 50.0]))
    cells = [(r, c) for r in range(H) for c in range(W)]
    waitable = {rc for rc in cells if rng.random() < 0.9}
    forbidden = []
    for (r, c) in cells:                       # a few banned U-turns
        for dr, dc in ((0, 1), (1, 0)):
            r2, c2 = r + dr, c + dc
            if r2 < H and c2 < W and rng.random() < 0.1:
                forbidden.append((eid((r, c), (r2, c2)), eid((r2, c2), (r, c))))
    graph = grid_graph(H, W, travel=travel, waitable=waitable, forbidden=forbidden)

    def pick():
        return cells[int(rng.integers(len(cells)))]

    fac_rc = {f"F{i}": pick() for i in range(int(rng.integers(1, 3)))}
    shl_rc = {f"S{i}": pick() for i in range(int(rng.integers(1, 3)))}
    dep_rc = {f"V{i}": pick() for i in range(int(rng.integers(1, 3)))}
    facilities = [facility(f, nid(*rc), *(int(x) for x in rng.integers(0, 4, size=3)),
                           board=tuple(float(x) for x in rng.choice([0.0, 5.0, 15.0], size=3)),
                           release=float(rng.choice([0.0, 0.0, 0.0, 30.0, 120.0]))) for f, rc in fac_rc.items()]
    win = [((0.0, 1e5),), ((0.0, 200.0), (300.0, 1e5)), ((100.0, 600.0),)]
    shelters = [shelter(s, nid(*rc), cap=tuple(int(x) for x in rng.integers(0, 7, size=3)),
                        windows=win[int(rng.integers(len(win)))],
                        unload=tuple(float(x) for x in rng.choice([0.0, 5.0, 10.0], size=3))) for s, rc in shl_rc.items()]
    vehicles = [vehicle(v, nid(*rc), start=float(rng.choice([0.0, 0.0, 20.0])), seats=int(rng.integers(1, 9)),
                        wc=int(rng.integers(0, 3)), stretchers=int(rng.integers(0, 3)),
                        shift=[None, None, 300.0, 900.0][int(rng.integers(4))]) for v, rc in dep_rc.items()]
    peak = float(rng.choice([1e-3, 0.01, 0.1, 1.0, 10.0]))
    dose = [float(x) for x in rng.choice([0.01, 0.1, 1.0, 10.0, 100.0], size=K)]
    inst = instance(graph, facilities=facilities, vehicles=vehicles, shelters=shelters, peak=peak,
                    dose=dose if rng.random() < 0.5 else dose[0], offset=float(rng.choice([0.0, 0.0, 25.0])))

    fac = {f.id: f for f in facilities}
    shl = {s.id: s for s in shelters}
    left = {f.id: list(f.residents.vector()) for f in facilities}
    its = []
    for v in vehicles:
        pos, clock, acts, load = dep_rc[v.id], v.start_s, [], [0, 0, 0]

        def go(dest):
            nonlocal pos, clock
            cs = manhattan(pos, dest, rows_first=bool(rng.random() < 0.5))
            if len(cs) > 1:
                t = clock + float(rng.choice([0.0, 0.0, 0.0, 0.0, 15.0]))
                acts.append(drive(path(*cs), t))
                for _ in cs[1:]:
                    t = t + travel
                clock = t
            pos = dest

        for _ in range(int(rng.integers(0, 3))):
            f = fac[list(fac)[int(rng.integers(len(fac)))]]
            s = shl[list(shl)[int(rng.integers(len(shl)))]]
            go(fac_rc[f.id])
            if rng.random() < 0.2:
                d = float(rng.choice([5.0, 30.0]))
                acts.append(wait(nid(*pos), d))
                clock = clock + d
            room = [v.capacity()[c] - load[c] for c in range(3)]
            cnt = [int(rng.integers(0, max(min(left[f.id][c], room[c]), 0) + 1 + int(rng.random() < 0.05)))
                   for c in range(3)]
            acts.append(board(f.id, *cnt))
            clock = clock + f.boarding_s.duration(counts(*cnt))
            load = [load[c] + cnt[c] for c in range(3)]
            left[f.id] = [left[f.id][c] - cnt[c] for c in range(3)]
            go(shl_rc[s.id])
            out = load if rng.random() > 0.1 else [int(rng.integers(0, x + 1)) for x in load]
            acts.append(unload(s.id, *out))
            clock = clock + s.unloading_s.duration(counts(*out))
            load = [load[c] - out[c] for c in range(3)]
        its.append(itinerary(v.id, *acts))
    return inst, ss, solution(*its)
