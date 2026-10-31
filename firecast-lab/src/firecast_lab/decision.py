"""The decision metric: fixed routing requests checked by ``evacplan.oracle`` against a model's scenario set and
against a truth scenario set (exact definitions: METRICS.md section 7).

Per window (cutoff c, lead L) of a fire that has a road graph:

1. ``build_requests``: single-vehicle itineraries made ONLY from cutoff information (the static road graph, the
   cutoff burned state, the grid, the lead and the seed; never a forecast, the truth or the scoring domain). Origins
   are road nodes outside the cutoff burned area within ``origin_max_m`` of it; destinations lie a declared
   straight-line distance away; the path is the static shortest-time path with turn rules kept; a waitable origin
   may hold a stationary wait; the trip ends inside the lead. Deterministic per (fire, cutoff, seed). Each request
   is an evacplan ``Itinerary`` of one vehicle that starts at its origin; the window's requests share one
   ``Instance`` and pass the hazard-free validator, so no verdict can come from a resource rule.
2. ``model_verdicts``: ``evacplan.oracle`` on the model's K-member set; cleared = checked in ALL K members,
   model_no_route or unresolved = not cleared. The same oracle on nested member subsets K' = 1, 2, 4, ... (the
   set's order and member-shuffled repeats) gives ``k_curve``.
3. Truth (``truth_from_reconstruction``: Korean fires, labelled reconstruction truth; ``truth_from_perimeters``:
   observed perimeters), hazard_contract ``from_perimeters`` in mode ``envelope``: truth model_no_route = hit,
   checked = safe, unresolved = excluded from the scored set and counted, never safe.
4. ``summarize``: false-safe P(hit | cleared), miss rate, clearance rate and false-unsafe rate with whole-fire
   bootstrap intervals; ``plot_tradeoff``: false-safe against clearance as K varies, per member coupling.

Program rule 3: only ``evacplan.oracle`` declares checked / model_no_route / unresolved. This module reads its states.
"""
from __future__ import annotations

import heapq
import json
import os
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import hazard_contract as hc
import numpy as np
from evacplan import (Budgets, Drive, HazardRef, Instance, InstanceIndex, Itinerary, Oracle, RoadGraph, Solution,
                      Vehicle, Wait, validate_solution)
from hazard_contract.geometry import polyline_cells
from scipy import ndimage

from firecast_lab import baselines as bl
from firecast_lab import harness
from firecast_lab import metrics as m
from firecast_lab import producer
from firecast_lab.data import Window, case_seed
from firecast_lab.members import COUPLINGS

PEAK_KW_M2 = 10.0                # the router's request budgets (integration/src/wfg_latest/packets.py:178):
DOSE_KJ_M2 = 100.0               # peak 10 kW/m2 and dose 100 kJ/m2 in every member
TRUTH_MODE = "envelope"          # from_perimeters mode of every truth set (METRICS.md section 7)
COPULA_LENGTH_CELLS = 8.0        # declared copula correlation length of the decision metric: 8 cells = 3 km at 375 m
OUTCOMES = ("hit", "safe", "unresolved")
REQUEST_STREAM = 0x52455153      # keeps request and member-order draws apart from the member draws of a window seed
GRAPHS_ENV = "FIRECAST_GRAPHS"
# The Korean router study graphs (folder names of the fetched routing inputs). KFS_01 (uiseong_andong_2025,
# yeongdeok_2025) is a TEST fire and deliberately absent: its graphs are never used without Siyeong's approval.
GRAPH_FOLDERS = {"KFS_02": "uljin_2022", "KFS_05": "hongseong_2023", "KFS_11": "miryang_2022"}
COLUMNS = ("model", "split", "fold", "fire", "country", "cutoff_utc", "lead_h", "members", "coupling",
           "length_cells", "request", "origin", "destination", "front_m", "start_s", "wait_s", "depart_s", "arrive_s",
           "n_edges", "length_m", "truth_kind", "truth", "truth_state", "truth_cause", "model_state", "model_cause",
           "cleared", "cleared_up_to", "in_sample", "synthetic", "window_seed")


class RoadGraphsNotFound(FileNotFoundError):
    """No road-graph folder: the decision metric needs the real road graphs and never falls back."""


# ------------------------------------------------------------------------------------------------- requests
@dataclass(frozen=True)
class RequestConfig:
    """Declared request parameters, recorded in every result's config."""

    n_requests: int = 32                              # requests per window
    origin_max_m: float = 3000.0                      # origin within this distance of the cutoff burned area
    trip_m: tuple[float, float] = (2000.0, 4000.0)    # straight-line origin -> destination distance
    wait_share: float = 0.5                           # share of waitable origins that hold a wait before leaving
    wait_max_s: float = 3600.0                        # wait drawn in whole seconds from [1, wait_max_s]
    attempts: int = 20                                # draws per wanted request before the window stops trying

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Request:
    """One fixed itinerary: a vehicle at ``origin`` from ``start_s`` (seconds after the cutoff), an optional
    stationary wait there, then the static shortest-time path to ``destination`` departing at ``depart_s``."""

    id: str
    origin: str
    destination: str
    front_m: float          # the origin's distance to the cutoff burned area (cell centres)
    start_s: float
    wait_s: float
    depart_s: float
    arrive_s: float
    edges: tuple[str, ...]
    length_m: float

    def itinerary(self) -> Itinerary:
        wait = [Wait(node=self.origin, duration_s=self.wait_s)] if self.wait_s > 0 else []
        return Itinerary(vehicle=self.id, actions=[*wait, Drive(edges=list(self.edges), depart_s=self.depart_s)])


@dataclass(frozen=True, eq=False)
class RequestSet:
    """The fixed requests of one window and the evacplan ``Instance`` they run in (one vehicle per request)."""

    fire: str
    cutoff_utc: str
    lead_h: int
    window_seed: int
    config: RequestConfig
    requests: tuple[Request, ...]
    instance: Instance
    origin_candidates: int


def _hazard_ref(offset_s: float) -> HazardRef:
    return HazardRef(scenario_set="in-memory", t0_offset_s=float(offset_s),
                     budgets=Budgets(peak_kw_m2=PEAK_KW_M2, dose_kj_m2=DOSE_KJ_M2))


class _Roads:
    """Static lookups on a road graph over a hazard grid: node positions and touched cells, shortest paths."""

    def __init__(self, instance: Instance, grid: hc.Grid):
        self.index, self.grid = InstanceIndex(instance), grid
        nodes = instance.graph.nodes
        self.ids = [n.id for n in nodes]
        self.position = {nid: i for i, nid in enumerate(self.ids)}
        self.xy = np.array([[n.x, n.y] for n in nodes], dtype=np.float64).reshape(-1, 2)
        self.waitable = np.array([n.waitable for n in nodes], dtype=bool)
        self.cells = [polyline_cells(grid, p[None]) for p in self.xy]
        self.inside = np.array([rows.size > 0 and not outside for rows, _, outside in self.cells], dtype=bool)
        self._edge_inside: dict[str, bool] = {}

    def edge_inside(self, edge: str) -> bool:
        if edge not in self._edge_inside:
            rows, _, outside = polyline_cells(self.grid, self.index.edge_geometry(edge))
            self._edge_inside[edge] = bool(rows.size) and not outside
        return self._edge_inside[edge]

    def length_m(self, edges) -> float:
        return float(sum(np.hypot(*np.diff(self.index.edge_geometry(e), axis=0).T).sum() for e in edges))

    def shortest_from(self, origin: str):
        """Static shortest travel times from ``origin`` with labels on edges, so forbidden turns are kept; ties go to
        the smaller edge id. Returns node times (graph order, inf = unreachable), the last edge into each reached
        node and each settled edge's predecessor."""
        edges, out, forbidden = self.index.edges, self.index.out_edges, self.index.forbidden
        best: dict[str, float] = {}
        prev: dict[str, str | None] = {}
        heap = []
        for e in out(origin):
            if edges[e].travel_time_s < best.get(e, np.inf):
                best[e], prev[e] = edges[e].travel_time_s, None
                heapq.heappush(heap, (best[e], e))
        position = self.position
        times = np.full(len(self.ids), np.inf)
        times[position[origin]] = 0.0
        last: dict[str, str] = {}
        done: set[str] = set()
        while heap:
            t, e = heapq.heappop(heap)
            if e in done:
                continue
            done.add(e)
            v = edges[e].v
            if t < times[position[v]]:
                times[position[v]], last[v] = t, e
            for nxt in out(v):
                if nxt in done or (e, nxt) in forbidden:
                    continue
                t2 = t + edges[nxt].travel_time_s
                if t2 < best.get(nxt, np.inf):
                    best[nxt], prev[nxt] = t2, e
                    heapq.heappush(heap, (t2, nxt))
        return times, last, prev


def _path(destination: str, last: dict, prev: dict) -> list[str]:
    path, e = [], last[destination]
    while e is not None:
        path.append(e)
        e = prev[e]
    return path[::-1]


def build_requests(graph: RoadGraph, burned, transform, lead_h: int, *, fire: str, cutoff_utc: str, seed: int,
                   config: RequestConfig = RequestConfig(), synthetic: bool = False) -> RequestSet:
    """The fixed requests of one window from cutoff information only (module doc).

    ``burned``: the cutoff burned state ``[H, W]`` on the hazard grid ``transform``; ``seed``: the run seed (the
    window seed is ``data.case_seed(seed, fire, cutoff_utc)``). Origins and destinations must not touch the grid's
    outside, nor may any edge of the path: such a trip could never be verified."""
    burned = np.asarray(burned, dtype=bool)
    if burned.ndim != 2:
        raise ValueError("burned must be the [H, W] cutoff burned state")
    if not burned.any():
        raise ValueError("no burned cell at the cutoff: there is no front to place requests near")
    grid = hc.Grid(tuple(float(v) for v in transform), *burned.shape)
    sx, sy = grid.cell_size
    front = ndimage.distance_transform_edt(~burned, sampling=(sy, sx))   # metres between cell centres
    name = f"decision requests {fire} {cutoff_utc}"
    roads = _Roads(Instance(name=name, synthetic=bool(synthetic), graph=graph, hazard=_hazard_ref(0.0)), grid)
    origins, front_m = [], []
    for i, (rows, cols, _) in enumerate(roads.cells):
        if roads.inside[i] and not burned[rows, cols].any() and front[rows, cols].min() <= config.origin_max_m:
            origins.append(i)
            front_m.append(float(front[rows, cols].min()))
    window_seed = case_seed(seed, fire, cutoff_utc)
    rng = np.random.default_rng([window_seed, REQUEST_STREAM])
    lead_s, (near, far) = 3600.0 * lead_h, config.trip_m
    trees: dict[int, tuple] = {}
    requests: list[Request] = []
    for _ in range(config.n_requests * config.attempts):
        if len(requests) == config.n_requests or not origins:
            break
        j = int(rng.integers(len(origins)))
        o = origins[j]
        if o not in trees:
            trees[o] = roads.shortest_from(roads.ids[o])
        times, last, prev = trees[o]
        distance = np.hypot(*(roads.xy - roads.xy[o]).T)
        ok = roads.inside & np.isfinite(times) & (distance >= near) & (distance <= far)
        ok[o] = False
        candidates = np.flatnonzero(ok)
        if not candidates.size:
            continue
        d = int(candidates[rng.integers(candidates.size)])
        edges = _path(roads.ids[d], last, prev)
        if not all(roads.edge_inside(e) for e in edges):
            continue
        wait = 0.0
        if roads.waitable[o] and rng.random() < config.wait_share:
            wait = float(rng.integers(1, int(config.wait_max_s) + 1))
        slack = lead_s - wait - float(times[d]) - 1.0        # 1 s margin: the trip ends strictly inside the lead
        if slack < 0:
            continue
        start = float(np.floor(rng.uniform(0.0, slack)))
        requests.append(Request(id=f"R{len(requests):03d}", origin=roads.ids[o], destination=roads.ids[d],
                                front_m=front_m[j], start_s=start, wait_s=wait, depart_s=start + wait,
                                arrive_s=start + wait + float(times[d]), edges=tuple(edges),
                                length_m=roads.length_m(edges)))
    vehicles = [Vehicle(id=r.id, depot=r.origin, start_s=r.start_s, seats=0, kind="decision request") for r in requests]
    instance = Instance(name=name, synthetic=bool(synthetic), graph=graph, vehicles=vehicles, hazard=_hazard_ref(0.0),
                        provenance=dict(fire=fire, cutoff_utc=cutoff_utc, window_seed=window_seed,
                                        requests=config.as_dict(), note="decision-metric requests: cutoff information "
                                                                        "only (firecast_lab.decision)"))
    report = validate_solution(instance, Solution(instance=name, itineraries=[r.itinerary() for r in requests]))
    if not report.ok:   # pragma: no cover - the builder keeps turn rules, waitable nodes and the clock
        raise AssertionError(f"invalid request itineraries: {[i.code for i in report.issues][:5]}")
    return RequestSet(fire=fire, cutoff_utc=cutoff_utc, lead_h=int(lead_h), window_seed=window_seed, config=config,
                      requests=tuple(requests), instance=instance, origin_candidates=len(origins))


def requests_for(window: Window, graph: RoadGraph, *, seed: int, config: RequestConfig = RequestConfig()) -> RequestSet:
    """``build_requests`` for a window: it hands over the cutoff state, grid, lead and identity only, never the
    window's outcome, final perimeter or scoring domain."""
    return build_requests(graph, window.inputs.burned, window.transform, window.lead_h, fire=window.fire,
                          cutoff_utc=window.cutoff_utc, seed=seed, config=config, synthetic=window.synthetic)


# ------------------------------------------------------------------------------------------- truth sets
def truth_from_reconstruction(window: Window, *, heat: hc.HeatSource = producer.PACKET_HEAT) -> hc.ScenarioSet:
    """Reconstruction truth (Korean fires): the reconstructed arrival's hourly isochrones as a perimeter series in
    mode ``envelope``. A cell arriving in hour (h - 1, h] after the cutoff burns on [h - 1, h + T) hours, T the heat
    source's burn duration (the producer's, so model and truth share one physics). Mapped mask = the window's scoring
    domain (outside it: unknown, unresolved); inside it, cells outside the final perimeter never burn (METRICS.md
    section 2). Horizon = the lead; issue time = the cutoff."""
    outcome = np.asarray(window.outcome_h, dtype=np.float64)
    burned_ever = np.isfinite(outcome)
    first = min(int(np.floor(outcome[burned_ever].min())) - 1, -1) if burned_ever.any() else -1
    hours = np.arange(first, window.lead_h + 1)
    series = [(3600.0 * h, burned_ever & (outcome <= h)) for h in hours]   # the first isochrone is empty
    height, width = outcome.shape
    return hc.from_perimeters(series, heat.burn_duration_s, transform=window.transform, height=height, width=width,
                              crs_epsg=window.epsg, issue_time_utc=window.cutoff_utc, K=1, mode=TRUTH_MODE,
                              mapped_mask=np.asarray(window.domain, dtype=bool), horizon_s=3600.0 * window.lead_h,
                              heat=heat, synthetic=window.synthetic,
                              model_version="reconstruction truth: hourly isochrones of the reconstructed arrival, "
                                            "envelope")


def _utc(stamp) -> datetime:
    if isinstance(stamp, datetime):
        value = stamp
    else:
        value = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("times must be timezone-aware")
    return value.astimezone(timezone.utc)


def truth_from_perimeters(window: Window, series, *, heat: hc.HeatSource = producer.PACKET_HEAT) -> hc.ScenarioSet:
    """Perimeter truth (US NIROPS surveys): observed perimeters ``[(time, shape), ...]`` in mode ``envelope``.

    ``time``: seconds after the cutoff, or a tz-aware datetime / ISO string. ``shape``: a bool mask on the window's
    grid or polygon rings in its CRS. Pass the surveys up to the window's end: earlier ones date the fire burning at
    the cutoff, none may lie after the lead. Horizon = the last survey (later trips are unresolved); issue time = the
    cutoff; mapped mask = the window's scoring domain."""
    cutoff = _utc(window.cutoff_utc)
    times = [float(t) if isinstance(t, (int, float, np.integer, np.floating)) else (_utc(t) - cutoff).total_seconds()
             for t, _ in series]
    if not times or max(times) > 3600.0 * window.lead_h:
        raise ValueError("perimeter truth needs surveys up to the window's end and none after it")
    height, width = window.inputs.shape
    return hc.from_perimeters([(t, shape) for t, (_, shape) in zip(times, series)], heat.burn_duration_s,
                              transform=window.transform, height=height, width=width, crs_epsg=window.epsg,
                              issue_time_utc=window.cutoff_utc, K=1, mode=TRUTH_MODE,
                              mapped_mask=np.asarray(window.domain, dtype=bool), heat=heat,
                              synthetic=window.synthetic, model_version="perimeter truth: observed surveys, envelope")


# --------------------------------------------------------------------------------------------- verdicts
def member_subset(scenarios: hc.ScenarioSet, members) -> hc.ScenarioSet:
    """The scenario set restricted to ``members`` (in that order): a valid hazard_contract set of K' members."""
    idx = np.asarray(members, dtype=int).reshape(-1)
    meta = scenarios.meta.model_copy(update=dict(K=int(idx.size)))
    return hc.ScenarioSet(scenarios.ignite_s[idx], scenarios.extinguish_s[idx], scenarios.supported[idx], meta)


def oracle_states(requests: RequestSet, scenarios: hc.ScenarioSet, which=None) -> list[tuple[str, str | None]]:
    """``(state, cause)`` of the requests ``which`` (indices; default all) as ``evacplan.oracle`` declares them on
    ``scenarios`` (all its members). Instance time 0 is the cutoff; the hazard offset comes from the set's issue time."""
    offset = (_utc(requests.cutoff_utc) - scenarios.meta.issue_time_utc).total_seconds()
    oracle = Oracle(requests.instance.model_copy(update=dict(hazard=_hazard_ref(offset))), scenarios)
    chosen = requests.requests if which is None else [requests.requests[i] for i in which]
    out = []
    for r in chosen:
        result = oracle.check_itinerary(r.itinerary())
        out.append((result.state.value, result.cause))
    return out


def k_values(K: int) -> list[int]:
    """Nested subset sizes: 1, 2, 4, ... below K, then K."""
    return sorted({2 ** i for i in range(int(K).bit_length()) if 2 ** i < K} | {int(K)})


def member_order(K: int, repeat: int, seed: int) -> np.ndarray:
    """Member order of a curve repeat: the set's own order for repeat 0, a seeded shuffle otherwise (the same
    shuffle in every window)."""
    return np.arange(K) if repeat == 0 else np.random.default_rng([REQUEST_STREAM, seed, repeat]).permutation(K)


def model_verdicts(requests: RequestSet, scenarios: hc.ScenarioSet, *, repeats: int = 4,
                   seed: int = 0) -> list[tuple[str, str | None, list[int]]]:
    """``(state, cause, cleared_up_to)`` per request. ``state``: the oracle on the K-member set (cleared = checked).
    ``cleared_up_to[r]``: for member order r (``member_order``), the largest K' in ``k_values(K)`` whose first K'
    members the oracle declares checked (0 if none), each K' verdict from the oracle on that K'-member subset.

    Subset verdicts are nested (adding members can never clear a request again; the tests run every subset and
    confirm it), so a request checked in all K members is checked in every subset and is not re-run, and for the
    others each order binary-searches the K' lattice: about log2(len(k_values)) oracle runs per request and order."""
    full = oracle_states(requests, scenarios)
    K, ks = scenarios.K, k_values(scenarios.K)
    up_to = []
    for r in range(repeats):
        order = member_order(K, r, seed)
        # per request not cleared at K: (index into ks of the largest K' known checked or -1, of the smallest known not)
        bounds = {i: (-1, len(ks) - 1) for i, (state, _) in enumerate(full) if state != "checked"}
        while any(hi - lo > 1 for lo, hi in bounds.values()):
            probes: dict[int, list[int]] = {}
            for i, (lo, hi) in bounds.items():
                if hi - lo > 1:
                    probes.setdefault((lo + hi) // 2, []).append(i)
            for j, which in sorted(probes.items()):
                states = oracle_states(requests, member_subset(scenarios, order[:ks[j]]), which=which)
                for i, (state, _) in zip(which, states):
                    lo, hi = bounds[i]
                    bounds[i] = (j, hi) if state == "checked" else (lo, j)
        row = [K if state == "checked" else 0 for state, _ in full]
        for i, (lo, _) in bounds.items():
            row[i] = ks[lo] if lo >= 0 else 0
        up_to.append(row)
    return [(state, cause, [up_to[r][i] for r in range(repeats)]) for i, (state, cause) in enumerate(full)]


def truth_outcome(state: str, cause: str | None) -> str:
    """hit (truth model_no_route: certain contact, or peak or dose above budget), safe (truth checked) or unresolved."""
    if state == "model_no_route":
        if cause and cause.startswith("RESOURCE:"):
            raise AssertionError(f"a request broke a resource rule ({cause}); truth hits must come from the hazard")
        return "hit"
    return "safe" if state == "checked" else "unresolved"


# ----------------------------------------------------------------------------------------------- one window
def decide_window(window: Window, graph: RoadGraph, model, *, K: int, seed: int, truth: hc.ScenarioSet,
                  truth_kind: str, couplings=COUPLINGS, length_cells: float = COPULA_LENGTH_CELLS,
                  config: RequestConfig = RequestConfig(), repeats: int = 4) -> tuple[list[dict], dict]:
    """Rows (``COLUMNS``, one per request and coupling) and a note for one window. Members come from
    ``baselines.forecast`` with the window's seed; models with their own members (c651) give one coupling, "own"."""
    requests = requests_for(window, graph, seed=seed, config=config)
    truth_states = oracle_states(requests, truth)
    record = window.record
    base = dict(model=model.name, split=record.get("split"), fold=record.get("fold"), fire=window.fire,
                country=record.get("country"), cutoff_utc=window.cutoff_utc, lead_h=window.lead_h, members=K,
                truth_kind=truth_kind, in_sample=model.name == "c651" and record.get("c651_role") == "train+validation",
                synthetic=bool(window.synthetic or truth.meta.synthetic), window_seed=requests.window_seed)
    rows = []
    for coupling in (("own",) if hasattr(model, "members") else tuple(couplings)):
        length = length_cells if coupling == "copula" else None
        hours, _ = bl.forecast(model, window, K=K, seed=seed, coupling=coupling, length_cells=length)
        scenarios = producer.from_window(window, hours, model=model, seed=seed,
                                         config=dict(model=model.name, K=K, coupling=coupling, length_cells=length))
        verdicts = model_verdicts(requests, scenarios, repeats=repeats, seed=seed)
        for r, (t_state, t_cause), (state, cause, up_to) in zip(requests.requests, truth_states, verdicts):
            rows.append(dict(base, coupling=coupling, length_cells=length, request=r.id, origin=r.origin,
                             destination=r.destination, front_m=round(r.front_m, 1), start_s=r.start_s,
                             wait_s=r.wait_s, depart_s=r.depart_s, arrive_s=r.arrive_s, n_edges=len(r.edges),
                             length_m=round(r.length_m, 1), truth=truth_outcome(t_state, t_cause), truth_state=t_state,
                             truth_cause=t_cause, model_state=state, model_cause=cause, cleared=state == "checked",
                             cleared_up_to="|".join(map(str, up_to))))
    note = dict(fire=window.fire, cutoff_utc=window.cutoff_utc, requests_wanted=config.n_requests,
                requests_built=len(requests.requests), origin_candidates=requests.origin_candidates)
    return rows, note


# --------------------------------------------------------------------------------------------- scoring
TERMS = ("cleared_hit", "cleared", "hit", "not_cleared_safe", "safe", "scored")
RATES = {"false_safe": ("cleared_hit", "cleared"), "miss_rate": ("cleared_hit", "hit"),
         "clearance_rate": ("cleared", "scored"), "false_unsafe": ("not_cleared_safe", "safe")}
UNDEFINED_FALSE_SAFE = "undefined: nothing was cleared (clearance 0); never report it as 0"


def summarize(fire, cleared, truth, *, draws: int = 10000, seed: int = m.BOOTSTRAP_SEED, level: float = 0.95) -> dict:
    """The four rates on the scored requests (truth hit or safe) with whole-fire bootstrap intervals.

    Every rate is pooled: a ratio of request counts summed over fires; ``metrics.fire_bootstrap`` resamples whole
    fires with the same draws for every rate. A rate whose denominator is 0 has ``point`` None and ``defined`` False;
    false-safe then carries ``note`` (with clearance 0). Truth-unresolved requests are left out and counted."""
    fire, cleared, truth = np.asarray(fire), np.asarray(cleared, dtype=bool), np.asarray(truth)
    if fire.ndim != 1 or not fire.shape == cleared.shape == truth.shape:
        raise ValueError("fire, cleared and truth need one entry per request")
    if not np.isin(truth, OUTCOMES).all():
        raise ValueError(f"truth outcomes must be one of {OUTCOMES}")
    scored, hit, safe = truth != "unresolved", truth == "hit", truth == "safe"
    flags = dict(cleared_hit=cleared & hit, cleared=cleared & scored, hit=hit, not_cleared_safe=~cleared & safe,
                 safe=safe, scored=scored)
    counts = {k: int(v.sum()) for k, v in flags.items()}
    out = dict(requests=int(fire.size), truth_unresolved=int((~scored).sum()),
               cleared_truth_unresolved=int((cleared & ~scored).sum()), fires=int(np.unique(fire[scored]).size),
               fires_with_requests=int(np.unique(fire).size), counts=counts)
    terms = np.stack([flags[k] for k in TERMS], axis=1).astype(np.float64)[scored]
    for name, (num, den) in RATES.items():
        entry = dict(point=None, defined=counts[den] > 0, interval=[None, None], level=level, numerator=counts[num],
                     denominator=counts[den], draws=draws, seed=seed, undefined_draws=None)
        if counts[den] > 0:
            a, b = TERMS.index(num), TERMS.index(den)
            boot = m.fire_bootstrap(fire[scored], terms, lambda s, a=a, b=b: s[..., a] / s[..., b], draws=draws,
                                    seed=seed, level=level)
            entry.update(point=boot["point"], interval=boot["interval"], undefined_draws=boot["undefined_draws"])
        out[name] = entry
    if counts["cleared"] == 0:
        out["false_safe"]["note"] = UNDEFINED_FALSE_SAFE
    return out


def k_curve(cleared_up_to, truth, K: int) -> list[dict]:
    """Clearance and false-safe of the nested member subsets ``k_values(K)``, pooled over the requests, for every
    member order: a request is cleared at K' in order r iff ``cleared_up_to[r] >= K'`` (``model_verdicts``).
    ``false_safe`` is None where nothing is cleared."""
    up = np.array([[int(v) for v in (u.split("|") if isinstance(u, str) else u)] for u in cleared_up_to])
    truth = np.asarray(truth)
    if up.ndim != 2 or up.shape[0] != truth.size:
        raise ValueError("one cleared_up_to entry per request, with one value per member order")
    scored, hit, out = truth != "unresolved", truth == "hit", []
    for r in range(up.shape[1]):
        for k in k_values(K):
            cleared = (up[:, r] >= k) & scored
            n, bad = int(cleared.sum()), int((cleared & hit).sum())
            out.append(dict(k=k, repeat=r, scored=int(scored.sum()), cleared=n, cleared_hits=bad,
                            clearance_rate=n / scored.sum() if scored.any() else None,
                            false_safe=bad / n if n else None))
    return out


def report(rows: list[dict], *, draws: int = 10000, seed: int = m.BOOTSTRAP_SEED) -> dict:
    """Per coupling: the headline rates at the full K (``summarize``), the K curve, truth-unresolved causes and the
    model's verdict counts."""
    out = {}
    for coupling in dict.fromkeys(r["coupling"] for r in rows):
        rs = [r for r in rows if r["coupling"] == coupling]
        truth = [r["truth"] for r in rs]
        out[coupling] = dict(
            length_cells=rs[0]["length_cells"], members=rs[0]["members"],
            headline=summarize([r["fire"] for r in rs], [r["cleared"] for r in rs], truth, draws=draws, seed=seed),
            k_curve=k_curve([r["cleared_up_to"] for r in rs], truth, rs[0]["members"]),
            truth_unresolved_by_cause=dict(Counter(str(r["truth_cause"]) for r in rs if r["truth"] == "unresolved")),
            model_states=dict(Counter(r["model_state"] for r in rs)))
    return out


def rate_text(entry: dict) -> str:
    """One rate for printing: ``0.123 [0.050, 0.210]`` or why it is undefined."""
    if not entry["defined"]:
        return entry.get("note", "undefined (denominator 0)")
    lo, hi = entry["interval"]
    return f"{entry['point']:.3f} [{lo:.3f}, {hi:.3f}] ({entry['numerator']}/{entry['denominator']})"


# ---------------------------------------------------------------------------------------------------- figure
SURFACE, INK, INK_SECONDARY, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
SERIES = {"shared": "#2a78d6", "copula": "#eb6834", "own": "#1baf7a"}   # categorical slots 1-3, fixed per coupling


def plot_tradeoff(curves: dict, path, *, title: str, synthetic: bool, labels: dict | None = None,
                  note: str = "") -> Path:
    """False-safe against clearance as K varies, one series per coupling (``k_curve`` points): the member-order
    curve with K' marked at its ends, member-shuffled repeats as faint dots. Points where nothing is cleared have no
    false-safe rate; they are listed under the plot, never drawn at 0. The PNG's Title metadata repeats the title."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    full_title = ("SYNTHETIC - " if synthetic else "") + title
    fig = Figure(figsize=(7.2, 5.4), dpi=150, facecolor=SURFACE)
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(facecolor=SURFACE)
    undefined, top = [], 0.0
    for coupling, points in curves.items():
        color, label = SERIES.get(coupling, "#6250d6"), (labels or {}).get(coupling, coupling)
        shuffled = [p for p in points if p["repeat"] > 0 and p["false_safe"] is not None]
        ax.scatter([p["clearance_rate"] for p in shuffled], [p["false_safe"] for p in shuffled], s=12, color=color,
                   alpha=0.3, linewidths=0, zorder=2)
        main = sorted((p for p in points if p["repeat"] == 0), key=lambda p: p["k"])
        shown = [p for p in main if p["false_safe"] is not None]
        blank = [str(p["k"]) for p in main if p["false_safe"] is None]
        undefined += [f"{label}: K' = {', '.join(blank)}"] if blank else []
        xs, ys = [p["clearance_rate"] for p in shown], [p["false_safe"] for p in shown]
        ax.plot(xs, ys, color=color, lw=2, solid_capstyle="round", solid_joinstyle="round", marker="o", ms=7,
                mec=SURFACE, mew=1.5, label=label, zorder=3)
        for p, dy in zip(shown[:1] + shown[1:][-1:], (5, -12)):        # K' at the curve's ends: first above, last below
            ax.annotate(f"K'={p['k']}", (p["clearance_rate"], p["false_safe"]), xytext=(6, dy),
                        textcoords="offset points", fontsize=8, color=INK_SECONDARY)
        top = max([top, *ys, *(p["false_safe"] for p in shuffled)])
    top = max(0.05, 1.15 * top)
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02 * top, top)
    ax.set_xlabel("clearance rate (cleared / scored requests)", color=INK_SECONDARY)
    ax.set_ylabel("false-safe rate P(hit | cleared)", color=INK_SECONDARY)
    ax.grid(True, color=GRID, linewidth=0.8, linestyle="-")
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_SECONDARY, labelsize=8)
    ax.legend(frameon=False, fontsize=8, labelcolor=INK, loc="upper left")
    if synthetic:
        ax.text(0.99, 0.98, "SYNTHETIC", transform=ax.transAxes, ha="right", va="top", fontsize=10,
                fontweight="bold", color=INK)
    ax.set_title(full_title, fontsize=10, color=INK, loc="left")
    foot = [note] if note else []
    if undefined:
        foot.append("nothing cleared, so false-safe undefined (not 0): " + "; ".join(undefined))
    fig.text(0.01, 0.01, "\n".join(foot), fontsize=7, color=INK_SECONDARY, va="bottom", wrap=True)
    fig.subplots_adjust(bottom=0.11 + 0.035 * len(foot), left=0.1, right=0.97, top=0.92)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=SURFACE, metadata={"Title": full_title})
    return path


# ------------------------------------------------------------------------------------ road graphs and runs
def graphs_root(path=None) -> Path:
    """The road-graph folder: ``path``, else ``$FIRECAST_GRAPHS``. Never a fallback."""
    raw = path if path is not None else os.environ.get(GRAPHS_ENV)
    if not raw or not Path(raw).expanduser().is_dir():
        raise RoadGraphsNotFound(f"road graphs not found: pass --graphs DIR or set {GRAPHS_ENV} (DIR/<fire>/graph.json, "
                                 f"or the Korean study folders {sorted(GRAPH_FOLDERS.values())})")
    return Path(raw).expanduser()


def graph_path(root: Path, fire: str) -> Path | None:
    """``root/<fire>/graph.json``, else the fire's Korean study folder; None if the fire has no graph."""
    for folder in (fire, GRAPH_FOLDERS.get(fire)):
        if folder and (root / folder / "graph.json").is_file():
            return root / folder / "graph.json"
    return None


def load_road_graph(path) -> RoadGraph:
    """An evacplan ``RoadGraph`` JSON as is, or a router ``graph.json`` through evacplan's router-graph adapter with
    the router's own admission (``wfg_latest``, i.e. ``integration/src``, must be importable)."""
    data = json.loads(Path(path).read_text())
    if "crs_epsg" in data:
        return RoadGraph.model_validate(data)
    from evacplan.adapters import from_wfg_graph
    try:
        return from_wfg_graph(data, validate=True)
    except ModuleNotFoundError as error:
        raise ModuleNotFoundError(f"the router-graph admission needs wfg_latest (put integration/src on the path): "
                                  f"{error}") from error


def scorable_fires(fire_ids, splits: dict, graphs_dir=None) -> tuple[dict[str, Path], dict[str, str]]:
    """Fires with a road graph and a supported truth (``{fire: graph path}``), and the skipped ones with a reason.
    Korean fires use reconstruction truth; US fires need NIROPS survey perimeters, which have no loader yet."""
    root = graphs_root(graphs_dir)
    country = {f["id"]: f.get("country") for f in splits["fires"]}
    found, skipped = {}, {}
    for fire in fire_ids:
        path = graph_path(root, fire)
        if path is None:
            skipped[fire] = "no road graph"
        elif country.get(fire) != "KR":
            skipped[fire] = "US truth needs NIROPS survey perimeters (truth_from_perimeters); no NIROPS loader yet"
        else:
            found[fire] = path
    return found, skipped


def run(name: str, split: str, windows_of, splits: dict, *, graphs: dict, K: int, seed: int,
        length_cells: float = COPULA_LENGTH_CELLS, config: RequestConfig = RequestConfig(), repeats: int = 4,
        options: dict | None = None) -> tuple[list[dict], list[dict]]:
    """Decision rows and window notes for every window of ``graphs``' fires (``{fire: graph.json}``, Korean fires,
    reconstruction truth), with models cross-fitted by whole-fire folds exactly as ``harness.crossfit`` does."""
    rows, notes, loaded = [], [], {}
    for window, model, _ in harness.crossfit(name, split, windows_of, splits, options=options):
        if window.fire not in graphs:
            continue
        if window.fire not in loaded:
            loaded[window.fire] = load_road_graph(graphs[window.fire])
        r, note = decide_window(window, loaded[window.fire], model, K=K, seed=seed,
                                truth=truth_from_reconstruction(window), truth_kind="reconstruction",
                                length_cells=length_cells, config=config, repeats=repeats)
        rows += r
        notes.append(note)
    return rows, notes
