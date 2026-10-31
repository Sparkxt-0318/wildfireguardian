"""SYNTHETIC instance generator: road graph, care facilities, fleet, shelters and a threatening fire.

Every instance is deterministic from its :class:`SyntheticConfig` ``(size, tightness, graph, seed)``
and labelled SYNTHETIC everywhere (instance name and id, ``Instance.synthetic``, provenance, the
hazard's ``meta.synthetic``/``source``, facility and shelter names). The layout (roads, facility,
shelter and depot nodes, residents, boarding and unloading times, vehicle types, depots and start
times, the fire's direction and member perturbations) depends only on ``(size, graph, seed)``;
``tightness`` in [0, 1] only moves the knobs below, so the same seed at two tightness levels is a
controlled comparison. Shelters (east band) and depots (eastern third) are ranked by how late the
layout's most aggressive fire (tightness 1) reaches them, which keeps them out of the fire's reach
at the tightness levels of the frozen split (the diagnostics report any site the fire reaches).

Tightness knobs (linear in ``t``; see ``docs/ASSUMPTIONS.md``, section "Synthetic generator")
-------------------------------------------------------------------------------------------
* fire proximity: the ignition is placed upwind of the facilities so that the EARLIEST fire
  arrival at any facility node, over all members, is exactly ``lead`` = 150 min -> 30 min after
  issue (found by bisection on the realized ``hazard_contract.synthetic`` members);
* fire spread: head rate of spread 0.08 -> 0.30 m/s;
* release times (staff ready): uniform in [0, 5 -> 45 min] per facility;
* driver shift limits: 100 % -> 50 % of the hazard horizon;
* fleet size: a prefix of the size's vehicle list, max -> min vehicles.

Sizes (problem v0): S ~2 facilities, 1-2 vehicles, 20-40 residents; M 6, 3-5, ~150; L 15, 8-12
(10 at medium tightness), ~600.

The fire is ``hazard_contract.synthetic`` (elliptical spread, K perturbed members) with the repo's
packet heat-source parameters; burned cells stay burning through the horizon ("roads close"),
ignition times are floored to whole seconds (outward) so instances regenerate bit-identically.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

import hazard_contract as hc
from hazard_contract.geometry import polyline_cells

from ..schema import (
    Budgets, ClassCounts, ClassDurations, Facility, HazardRef, Instance, Shelter, Vehicle, save_instance,
)
from .graphs import Layout, make_layout, node_id, to_road_graph

GENERATOR = "evacplan.generators.synthetic"
GENERATOR_VERSION = "evacplan.synthetic/1"
LABEL = "SYNTHETIC"

CRS_EPSG = 3310                         # abstract metres; no real place is implied
CELL_M = 375.0                          # hazard cell (the study packets' resolution)
SPACING_M = 750.0                       # road spacing
SPEED_KMH = 40.0                        # the router graphs' assumed speed
GRID_MARGIN_CELLS = 2                   # roads stay this far inside the hazard grid
WEST_EXTENSION_M = 4000.0               # wildland west of the roads where the fire may start
K_MEMBERS = 8
T_IGNITION_S = -3600.0                  # the fire started 1 h before issue
PERSIST_S = 48 * 3600.0                 # burned cells stay burning through every horizon used here
ISSUE_TIME_UTC = "2000-01-01T00:00:00Z"  # neutral date: no real event
SHELTER_OPEN_S = 48 * 3600.0            # shelters stay open through the plan
PACKET_HEAT = dict(fuel_load_kg_m2=10.0, consumed_fraction=0.1, heat_content_kj_kg=18608.0, radiative_fraction=0.3,
                   burn_duration_s=3970.4642815249267, emission_height_m=5.0, receiver_height_m=0.0)
BUDGETS = dict(peak_kw_m2=10.0, dose_kj_m2=100.0)   # router API defaults

# Vehicle space per type: (seats, wheelchair slots, stretcher slots). Seats exclude the driver.
VEHICLE_TYPES: dict[str, tuple[int, int, int]] = {
    "van": (8, 2, 0),          # wheelchair-accessible van
    "bus": (40, 2, 0),         # lift-equipped bus
    "ambulance": (1, 0, 1),    # one stretcher, one seated passenger
}
# Mobility mix by facility type (ambulatory, wheelchair, bedbound): classes are the space a
# resident needs IN THE VEHICLE (a wheelchair user who can transfer to a seat is ambulatory).
FACILITY_MIX: dict[str, tuple[float, float, float]] = {
    "snf": (0.75, 0.18, 0.07),   # skilled nursing facility
    "alf": (0.90, 0.09, 0.01),   # assisted living facility
}
P_SNF = 0.6
BOARDING_S = (45.0, 150.0, 360.0)      # per resident, before the facility multiplier
UNLOADING_S = (30.0, 90.0, 240.0)      # per resident, before the shelter multiplier
TIME_MULT = (0.8, 1.25)


@dataclass(frozen=True)
class SizeSpec:
    region_m: tuple[float, float]       # road region width (east-west) x height
    n_facilities: int
    residents: tuple[int, int]          # inclusive range of the total
    fleet: tuple[str, ...]              # vehicle types in order; tightness keeps a prefix
    fleet_n: tuple[int, int]            # (tight, loose) number of vehicles
    n_shelters: int
    n_depots: int
    horizon_s: float


SIZES: dict[str, SizeSpec] = {
    "S": SizeSpec((7500.0, 6000.0), 2, (20, 40), ("van", "ambulance"), (1, 2), 2, 1, 3 * 3600.0),
    "M": SizeSpec((12000.0, 9000.0), 6, (130, 170), ("bus", "van", "ambulance", "van", "ambulance"), (3, 5),
                  3, 2, 4 * 3600.0),
    "L": SizeSpec((18000.0, 13500.0), 15, (550, 650),
                  ("bus", "van", "ambulance", "van", "ambulance", "van", "bus", "ambulance", "van", "van",
                   "ambulance", "van"), (8, 12), 4, 3, 6 * 3600.0),
}
SIZE_CODE = {"S": 1, "M": 2, "L": 3}
GRAPH_CODE = {"grid": 1, "geo": 2}
STREAMS = {"graph": 1, "facilities": 2, "people": 3, "fire": 4, "sites": 5, "fleet": 6, "hazard": 7}


class SyntheticConfig(BaseModel):
    """Everything an instance is generated from."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    size: Literal["S", "M", "L"]
    tightness: float = Field(ge=0.0, le=1.0)
    graph: Literal["grid", "geo"] = "grid"
    seed: int = Field(ge=0)

    @property
    def instance_id(self) -> str:
        return f"{LABEL}-{self.size}-{self.graph}-t{_half_up(100 * self.tightness):02d}-s{self.seed}"


def _jsonable(d: dict) -> dict:
    """JSON-native copy (tuples become lists) so that instances round-trip through files equal."""
    return json.loads(json.dumps(d))


def _half_up(x: float) -> int:
    return int(math.floor(x + 0.5))


def _rng(cfg: SyntheticConfig, stream: str) -> np.random.Generator:
    return np.random.default_rng(np.random.SeedSequence(
        [cfg.seed, SIZE_CODE[cfg.size], GRAPH_CODE[cfg.graph], STREAMS[stream]]))


def tightness_params(cfg: SyntheticConfig) -> dict:
    """The tightness knobs for this config (all rounded: minutes, 1e-4 m/s, whole vehicles)."""
    spec, t = SIZES[cfg.size], cfg.tightness

    def lerp(a: float, b: float) -> float:
        return a + (b - a) * t

    lo, hi = spec.fleet_n
    return {
        "lead_s": 60.0 * _half_up(lerp(150.0, 30.0)),
        "ros_m_s": round(lerp(0.08, 0.30), 4),
        "release_max_s": 60.0 * _half_up(lerp(5.0, 45.0)),
        "shift_limit_s": 60.0 * _half_up(lerp(1.0, 0.5) * spec.horizon_s / 60.0),
        "n_vehicles": lo + _half_up((hi - lo) * (1.0 - t)),
    }


# ------------------------------------------------------------------------------- the result
@dataclass
class GeneratedInstance:
    config: SyntheticConfig
    instance: Instance
    hazard: hc.ScenarioSet
    diagnostics: dict = field(default_factory=dict)

    @property
    def instance_id(self) -> str:
        return self.config.instance_id

    def write(self, folder, *, overwrite: bool = False) -> Path:
        """``folder/instance.json`` and ``folder/hazard/`` (the scenario set)."""
        folder = Path(folder)
        self.hazard.write(folder / self.instance.hazard.scenario_set, overwrite=overwrite)
        save_instance(self.instance, folder / "instance.json", overwrite=overwrite)
        return folder

    def fingerprint(self) -> str:
        from ..instances import fingerprint
        return fingerprint(self.instance, self.hazard)


# --------------------------------------------------------------------------- site selection
def _spread_pick(rng: np.random.Generator, xy: np.ndarray, cand: np.ndarray, k: int, min_dist: float,
                 score: dict[int, float] | None = None) -> list[int]:
    """Pick ``k`` candidates at least ``min_dist`` apart (relaxed when impossible). Candidates are
    tried by descending ``score`` (ties in random order), or in random order."""
    order = rng.permutation(cand.size)
    if score is not None:
        order = order[np.argsort([-score[i] for i in cand[order].tolist()], kind="stable")]
    picked: list[int] = []
    d = float(min_dist)
    while len(picked) < k:
        for i in cand[order].tolist():
            if i in picked:
                continue
            if all(math.hypot(*(xy[i] - xy[j])) >= d for j in picked):
                picked.append(i)
                if len(picked) == k:
                    break
        d *= 0.7
        if d < 1.0 and len(picked) < k:
            raise ValueError("not enough candidate nodes")
    return picked


def _band(xy: np.ndarray, region: tuple[float, float], x: tuple[float, float], y: tuple[float, float],
          exclude=()) -> np.ndarray:
    w, h = region
    m = ((xy[:, 0] >= x[0] * w) & (xy[:, 0] <= x[1] * w) & (xy[:, 1] >= y[0] * h) & (xy[:, 1] <= y[1] * h))
    skip = set(exclude)
    return np.array([i for i in np.flatnonzero(m).tolist() if i not in skip], dtype=np.int64)


# ------------------------------------------------------------------------------------ fire
class _Fire:
    """The hazard grid and ``hazard_contract.synthetic`` members for one layout."""

    def __init__(self, cfg: SyntheticConfig, spec: SizeSpec, origin: np.ndarray):
        w, h = spec.region_m
        m = GRID_MARGIN_CELLS * CELL_M
        self.x0 = float(origin[0] - WEST_EXTENSION_M - m)
        self.y0 = float(origin[1] - m)
        self.width = int(math.ceil((w + WEST_EXTENSION_M + 2 * m) / CELL_M))
        self.height = int(math.ceil((h + 2 * m) / CELL_M))
        self.horizon = spec.horizon_s
        self.seed = int(np.random.SeedSequence(
            [cfg.seed, SIZE_CODE[cfg.size], GRAPH_CODE[cfg.graph], STREAMS["hazard"]]).generate_state(1)[0])
        self.heat = hc.HeatSource(**PACKET_HEAT, note="the repo packets' heat-source parameters (SYNTHETIC fire)")

    def members(self, ignition_xy, ros_m_s: float, spread_dir_deg: float) -> hc.ScenarioSet:
        return hc.synthetic(
            K=K_MEMBERS, height=self.height, width=self.width, cell_m=CELL_M, x0=self.x0, y0=self.y0,
            crs_epsg=CRS_EPSG, ignition_xy=(float(ignition_xy[0]), float(ignition_xy[1])),
            t_ignition_s=T_IGNITION_S, ros_m_s=ros_m_s, spread_dir_deg=spread_dir_deg, horizon_s=self.horizon,
            burn_duration_s=PERSIST_S, issue_time_utc=ISSUE_TIME_UTC, heat=self.heat, seed=self.seed)

    def inside(self, p: np.ndarray) -> bool:
        m = GRID_MARGIN_CELLS * CELL_M
        return (self.x0 + m <= p[0] <= self.x0 + self.width * CELL_M - m
                and self.y0 + m <= p[1] <= self.y0 + self.height * CELL_M - m)


def _arrival(ss: hc.ScenarioSet, geom_xy) -> float:
    """Earliest ignition over all members of the closed cells a point or chord touches (inf: never
    within the horizon)."""
    rows, cols, outside = polyline_cells(ss.grid, np.asarray(geom_xy, dtype=float))
    if outside:
        raise ValueError("a road touches the outside of the hazard grid")
    return float(np.min(ss.ignite_s[:, rows, cols])) if rows.size else math.inf


def _finalise_hazard(ss: hc.ScenarioSet, provenance: dict) -> hc.ScenarioSet:
    """Floor ignition times to whole seconds (outward) and keep cells burning PERSIST_S."""
    ig = np.floor(ss.ignite_s)
    ex = np.where(np.isfinite(ig), ig + PERSIST_S, np.inf)
    meta = hc.ScenarioMeta(**{
        **ss.meta.model_dump(),
        "model_version": "evacplan-synthetic-fire/1 (hazard_contract synthetic-ellipse-v1, persistent burning)",
        "provenance": provenance,
    })
    return hc.ScenarioSet(ig, ex, ss.supported, meta)


# --------------------------------------------------------------------------------- generate
def generate(config: SyntheticConfig | dict) -> GeneratedInstance:
    """Generate one SYNTHETIC instance and its scenario set (deterministic from ``config``)."""
    cfg = config if isinstance(config, SyntheticConfig) else SyntheticConfig.model_validate(config)
    spec = SIZES[cfg.size]
    knobs = tightness_params(cfg)
    w, h = spec.region_m
    origin = np.zeros(2)

    # roads (layout depends on size, graph kind and seed only)
    layout: Layout = make_layout(cfg.graph, _rng(cfg, "graph"), w, h, SPACING_M)
    xy = layout.xy

    # facilities in the central band
    rng_f = _rng(cfg, "facilities")
    cand = _band(xy, spec.region_m, (0.30, 0.65), (0.12, 0.88))
    min_sep = 0.6 * math.sqrt(0.35 * w * 0.76 * h / spec.n_facilities)
    fac_nodes = _spread_pick(rng_f, xy, cand, spec.n_facilities, min_sep)
    fac_nodes = sorted(fac_nodes, key=lambda i: (xy[i, 0], xy[i, 1]))

    # fire: from the west towards the facilities; the ignition sits behind the most upwind facility
    rng_fire = _rng(cfg, "fire")
    theta = float(rng_fire.uniform(-20.0, 20.0))
    u = np.array([math.cos(math.radians(theta)), math.sin(math.radians(theta))])
    fire = _Fire(cfg, spec, origin)
    first = xy[fac_nodes[int(np.argmin(xy[fac_nodes] @ u))]]

    def place(ros: float, target: float) -> tuple[np.ndarray, hc.ScenarioSet]:
        """Ignition on the line behind ``first`` such that the earliest arrival at any facility
        node over all members is ``target`` (bisection on the realized members)."""
        def lead(dist: float) -> float:
            ss = fire.members(first - dist * u, ros, theta)
            return min(_arrival(ss, xy[i]) for i in fac_nodes)

        lo, hi = 0.0, 0.0
        while fire.inside(first - (hi + CELL_M) * u):
            hi += CELL_M
        if lead(hi) >= target:
            for _ in range(40):
                mid = 0.5 * (lo + hi)
                lo, hi = (mid, hi) if lead(mid) < target else (lo, mid)
                if hi - lo < 0.05:
                    break
        ignition = np.round(first - hi * u, 1)          # else: cannot push the fire further back
        return ignition, fire.members(ignition, ros, theta)

    # shelters (east band) and depots (eastern third) do not move with tightness: candidates are
    # ranked by how late the most aggressive fire of this layout (tightness 1) reaches them
    ref_knobs = tightness_params(cfg.model_copy(update={"tightness": 1.0}))
    _, ref = place(ref_knobs["ros_m_s"], ref_knobs["lead_s"])
    rng_s = _rng(cfg, "sites")

    def ref_arrival(i: int) -> float:
        t = _arrival(ref, xy[i])
        for a, b in layout.edges[(layout.edges[:, 0] == i) | (layout.edges[:, 1] == i)].tolist():
            t = min(t, _arrival(ref, xy[[a, b]]))
        return t

    sh_cand = _band(xy, spec.region_m, (0.82, 1.0), (0.0, 1.0), exclude=fac_nodes)
    score = {i: ref_arrival(i) for i in sh_cand.tolist()}
    shelters_n = _spread_pick(rng_s, xy, sh_cand, spec.n_shelters, 0.8 * h / spec.n_shelters, score)
    dep_cand = _band(xy, spec.region_m, (0.68, 1.0), (0.05, 0.95), exclude=fac_nodes + shelters_n)
    score.update({i: ref_arrival(i) for i in dep_cand.tolist() if i not in score})
    depots_n = _spread_pick(rng_s, xy, dep_cand, spec.n_depots, 0.8 * h / spec.n_depots, score)

    ros, target = knobs["ros_m_s"], knobs["lead_s"]
    ignition, raw = place(ros, target)
    hazard = _finalise_hazard(raw, {
        "label": LABEL, "generator": GENERATOR, "generator_version": GENERATOR_VERSION,
        "producer": "hazard_contract.adapters.synthetic", "seed": fire.seed, "instance": cfg.instance_id,
        "ignition_xy": ignition.tolist(), "t_ignition_s": T_IGNITION_S, "ros_m_s": ros, "spread_dir_deg": theta,
        "lead_target_s": target,
        "post": "ignite_s floored to whole seconds (outward); every ignited cell burns until 48 h after "
                "ignition, i.e. through the horizon (burned roads stay closed)",
    })

    # fire arrival at the sites: their own cells, plus the cells of their incident roads
    sites = fac_nodes + shelters_n + depots_n
    node_arr = {i: _arrival(hazard, xy[i]) for i in sites}
    site_arr = dict(node_arr)
    for a, b in layout.edges.tolist():
        if a in site_arr or b in site_arr:
            t_ab = _arrival(hazard, xy[[a, b]])
            for i in (a, b):
                if i in site_arr:
                    site_arr[i] = min(site_arr[i], t_ab)

    graph = to_road_graph(layout, crs_epsg=CRS_EPSG, offset_xy=(0.0, 0.0), speed_kmh=SPEED_KMH,
                          waitable_sites=sites,
                          provenance={"label": LABEL, "generator": GENERATOR, "spacing_m": SPACING_M})

    # residents (layout stream: independent of tightness)
    rng_p = _rng(cfg, "people")
    total = int(rng_p.integers(spec.residents[0], spec.residents[1] + 1))
    nf = spec.n_facilities
    kinds = ["snf" if r < P_SNF else "alf" for r in rng_p.random(nf)]
    shares = rng_p.dirichlet(np.full(nf, 4.0))
    sizes = 3 + rng_p.multinomial(total - 3 * nf, shares)
    mult_f = rng_p.uniform(*TIME_MULT, size=nf)
    release_u = rng_p.random(nf)
    facilities = []
    for k, (node, kind) in enumerate(zip(fac_nodes, kinds)):
        counts = rng_p.multinomial(int(sizes[k]), FACILITY_MIX[kind])
        board = [float(max(1, _half_up(b * mult_f[k]))) for b in BOARDING_S]
        release = 60.0 * _half_up(release_u[k] * knobs["release_max_s"] / 60.0)
        fid = f"F{k + 1:02d}"
        facilities.append(Facility(
            id=fid, node=node_id(node), residents=ClassCounts.of(counts),
            boarding_s=ClassDurations(ambulatory=board[0], wheelchair=board[1], bedbound=board[2]),
            release_s=release, name=f"{LABEL} {kind.upper()} {fid}"))
    by_class = np.sum([f.residents.vector() for f in facilities], axis=0)

    # shelters: S1 is medical (all classes), the others general (no stretchers)
    weights = rng_p.dirichlet(np.full(spec.n_shelters, 3.0))
    mult_s = rng_p.uniform(*TIME_MULT, size=spec.n_shelters)
    opens = rng_p.choice([0.0, 0.0, 900.0, 1800.0], size=spec.n_shelters)
    shelters = []
    for k, node in enumerate(shelters_n):
        medical = k == 0
        cap = (int(math.ceil(1.3 * by_class[0] * weights[k])) + 5,
               int(math.ceil(1.3 * by_class[1] * weights[k])) + 2,
               int(math.ceil(1.3 * by_class[2])) + 1 if medical else 0)
        unload = [float(max(1, _half_up(b * mult_s[k]))) for b in UNLOADING_S]
        shelters.append(Shelter(
            id=f"S{k + 1}", node=node_id(node), capacity=ClassCounts.of(cap),
            open_windows=[(0.0 if medical else float(opens[k]), SHELTER_OPEN_S)],
            unloading_s=ClassDurations(ambulatory=unload[0], wheelchair=unload[1], bedbound=unload[2]),
            name=f"{LABEL} {'medical' if medical else 'general'} shelter S{k + 1}"))

    # fleet: a prefix of the size's vehicle list (start times drawn for the whole list)
    rng_v = _rng(cfg, "fleet")
    starts = 60.0 * rng_v.integers(0, 16, size=len(spec.fleet))
    vehicles = []
    for k in range(knobs["n_vehicles"]):
        kind = spec.fleet[k]
        seats, wc, st = VEHICLE_TYPES[kind]
        vehicles.append(Vehicle(id=f"V{k + 1:02d}", depot=node_id(depots_n[k % len(depots_n)]),
                                start_s=float(starts[k]), seats=seats, wheelchair_slots=wc, stretcher_slots=st,
                                shift_limit_s=knobs["shift_limit_s"], kind=kind))

    def arr(v: float):
        return None if math.isinf(v) else v

    diagnostics = {
        "fire_arrival_note": "earliest ignition over all members of the cells a site's node touches (null: never "
                             "within the horizon); site_access adds the cells of its incident roads",
        "lead_realized_s": arr(min(float(node_arr[i]) for i in fac_nodes)),
        "facility_fire_arrival_s": {f.id: arr(float(node_arr[n])) for f, n in zip(facilities, fac_nodes)},
        "shelter_access_fire_arrival_s": {s.id: arr(float(site_arr[n])) for s, n in zip(shelters, shelters_n)},
        "depot_access_fire_arrival_s": {node_id(n): arr(float(site_arr[n])) for n in depots_n},
        "facilities_reached_within_horizon": int(sum(np.isfinite(node_arr[i]) for i in fac_nodes)),
        "residents_by_class": [int(x) for x in by_class],
        "fleet_space": [int(x) for x in np.sum([v.capacity() for v in vehicles], axis=0)],
        "ignition_xy": ignition.tolist(),
        "sites_ranked_by": "fire arrival under this layout's tightness-1 fire",
        "edge_burning_members": int(np.sum(hazard.edge_burning())),
    }
    instance = Instance(
        name=cfg.instance_id, synthetic=True, graph=graph, facilities=facilities, vehicles=vehicles,
        shelters=shelters,
        hazard=HazardRef(scenario_set="hazard", t0_offset_s=0.0, budgets=Budgets(**BUDGETS)),
        provenance=_jsonable({
            "label": LABEL, "generator": GENERATOR, "generator_version": GENERATOR_VERSION,
            "config": cfg.model_dump(), "tightness_params": knobs,
            "constants": {"crs_epsg": CRS_EPSG, "cell_m": CELL_M, "spacing_m": SPACING_M, "speed_kmh": SPEED_KMH,
                          "K": K_MEMBERS, "horizon_s": spec.horizon_s, "t_ignition_s": T_IGNITION_S,
                          "vehicle_types": VEHICLE_TYPES, "facility_mix": FACILITY_MIX,
                          "boarding_s": BOARDING_S, "unloading_s": UNLOADING_S},
            "diagnostics": diagnostics,
        }),
    )
    return GeneratedInstance(config=cfg, instance=instance, hazard=hazard, diagnostics=diagnostics)


def summary(gen: GeneratedInstance) -> dict:
    """Small, stable description (sizes and the fire's reach) for the split file and listings."""
    inst = gen.instance
    return {
        "nodes": len(inst.graph.nodes), "edges": len(inst.graph.edges), "facilities": len(inst.facilities),
        "vehicles": len(inst.vehicles), "shelters": len(inst.shelters), "residents": inst.residents_total,
        "residents_by_class": gen.diagnostics["residents_by_class"], "K": gen.hazard.K,
        "horizon_s": gen.hazard.meta.horizon_s, "lead_realized_s": gen.diagnostics["lead_realized_s"],
        "facilities_reached_within_horizon": gen.diagnostics["facilities_reached_within_horizon"],
    }


def config_json(cfg: SyntheticConfig) -> str:
    return json.dumps(cfg.model_dump(), sort_keys=True, separators=(",", ":"))
