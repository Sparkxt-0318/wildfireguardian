"""Rescue-aware evacuation routing: refuges whose *vehicle ingress survives*.

This module extends the future-aware evacuation router (:mod:`.evacuation`) with
one tightly-scoped idea drawn from wildfire-evacuation science: **shelter-in-
refuge / be-rescued** is a recognised protective action (Cova et al.), but it is
only safe if the **access route and the responders survive** the predicted fire.
Our spread model already predicts a time-varying per-cell ignition *probability*
surface (:class:`~wildfireguardian.routing.hazard.HazardSequence`), so we model
"rescue-reachable" as a **constraint on top of that existing prediction**, never
a new black box.

Three things are added, all on top of the existing hazard + routers:

1. **A drivable road layer + auxiliary destinations/depots** (§:func:`load_drive_network`,
   :func:`load_shelters`, :func:`load_depots`). Each has a *real-source loader*
   (OSMnx / Korea public open data) **and** a clearly-labelled *synthetic
   fallback* so the pipeline runs end-to-end with no network access or API key.
   Every destination/depot is tagged ``source = "real" | "synthetic"``.

2. **Ingress-corridor survival** (§:func:`assess_ingress`). For a destination
   (or a resident's home, in the rescuer case) we take the vehicle access route
   from the nearest depot, sample it into points, read each point's time-sliced
   ignition probability, and compute the earliest forecast slice at which **any**
   segment exceeds a *separate, higher* vehicle-impassability cutoff. The
   destination is ``rescue_reachable`` iff that survival time is at least the
   responder ETA plus a safety margin.

3. **Resident- and rescuer-side routing** (§:func:`resident_policies`,
   §:func:`rescuer_route`, §:func:`classify_origin`). Residents are routed only
   to rescue-reachable refuges; for people who cannot self-evacuate the responder
   route (depot → home) is computed on the drive network. The honest four-way
   outcome split — saved / already-safe / no-safe-walk / no-surviving-ingress —
   always sums to N, and the unreachable set is reported, never imputed.

Honesty stance (non-negotiable): no fabricated routes or reachability. "No safe
route" / "rescuer can't reach" are valid, expected outputs. Contrasts (with vs
without survival-awareness) are the robust result; absolute magnitudes are
illustrative given a single-fire PoC and any synthetic inputs.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

import networkx as nx
import numpy as np

from ..spread_v2.grid import CoarseGrid
from .evacuation import (
    ELDERLY_FLAT_SPEED_MS,
    RouteResult,
    future_aware_route,
    naive_route,
)
from .future_front import RoadNetwork
from .hazard import HazardSequence

#: Default responder vehicle speed (km/h) on rural East-Coast roads. ASSUMED.
DEFAULT_VEHICLE_SPEED_KMH: float = 40.0
#: Pedestrian (elderly) impassable cutoff — reuse the routing default.
DEFAULT_WALK_CUTOFF: float = 0.5
#: SEPARATE, higher vehicle-impassable cutoff: a responder vehicle moves fast and
#: may accept more risk than a walking elder. ASSUMED; exposed via config.
DEFAULT_VEHICLE_CUTOFF: float = 0.7


# ---------------------------------------------------------------------------
# Config — single source of truth for every path / cutoff / speed / seed
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RescueConfig:
    """All knobs for the rescue-aware pipeline. Synthetic/assumed values tagged.

    Anything marked ``# ASSUMED`` or ``# SYNTHETIC`` is a placeholder a reviewer
    can change; it is also echoed into :meth:`provenance` so every run reports
    exactly which inputs were synthetic or assumed.
    """

    # -- geography / grids -------------------------------------------------
    region_name: str = "yeongdeok_2025"        # key into utils.regions.ALL_REGIONS
    crs: str = "EPSG:5179"
    hazard_cell_m: float = 375.0               # 375 m hazard grid for 영덕 (per brief)
    route_cell_m: float = 750.0               # walk/drive lattice spacing (synthetic net)

    # -- speeds (ASSUMED, literature defaults) -----------------------------
    elderly_walk_speed_ms: float = ELDERLY_FLAT_SPEED_MS   # 0.7 m/s, Tobler-scaled
    vehicle_speed_kmh: float = DEFAULT_VEHICLE_SPEED_KMH    # ASSUMED 40 km/h

    # -- impassability cutoffs ---------------------------------------------
    walk_cutoff: float = DEFAULT_WALK_CUTOFF               # pedestrian, 0.5
    vehicle_cutoff: float = DEFAULT_VEHICLE_CUTOFF         # ASSUMED separate, 0.7

    # -- responder operational window (ASSUMED) ----------------------------
    # ETA = dispatch delay (detection + mobilisation) + drive travel time. A
    # delayed responder is a documented cause of death for the immobile, so this
    # delay is first-class, not cosmetic.
    responder_dispatch_delay_min: float = 30.0  # ASSUMED detection + mobilisation lag
    responder_safety_margin_min: float = 12.0   # ASSUMED margin before corridor cut
    responder_time_budget_min: float = 75.0     # ASSUMED dispatch budget (depot->home)
    resident_time_budget_min: float = 600.0     # reuse routing default (slow elder)

    # -- corridor sampling / time discretisation ---------------------------
    ingress_sample_spacing_m: float = 150.0     # < hazard cell so no cell is skipped
    time_step_min: float = 10.0

    # -- immobile residents (the "send the rescuer" population) ------------
    immobile_fraction: float = 0.3              # ASSUMED fraction that cannot self-evac

    # -- synthetic fallback knobs (ALL SYNTHETIC, tagged) ------------------
    n_synthetic_shelters: int = 12              # SYNTHETIC coastal refuge count
    n_synthetic_inland_shelters: int = 8        # SYNTHETIC inland open-space refuges
    n_synthetic_depots: int = 2                 # SYNTHETIC fire-station count
    scan_stride: int = 3                        # sub-sample stride for the origin scan
    sweep_max_origins: int = 200                # cap origins in the sensitivity sweep

    # -- synthetic hazard envelope (SYNTHETIC; tunable, no FIRMS present) ---
    syn_ignition_frac: tuple[float, float] = (0.46, 0.5)   # (E-W, N-S) of extent
    syn_fire_base_reach_m: float = 2200.0       # reach radius at t0 (early footprint)
    syn_fire_reach_rate_m_per_min: float = 52.0  # ~3 km/h sustained broad growth
    syn_fire_edge_width_m: float = 1100.0       # probabilistic edge transition width
    syn_inland_flank_radius_m: float = 5000.0   # ring radius for inland flank refuges

    # -- real-source data (optional; loaders fall back to synthetic) -------
    shelters_path: str | None = None            # 공공데이터포털 대피소 GeoJSON/CSV
    depots_path: str | None = None              # 119안전센터 / OSM fire_station file
    osm_cache_dir: str = "data/cache/osm"
    use_osm: bool = False                       # try OSMnx download (needs network)

    # -- determinism -------------------------------------------------------
    seed: int = 20250603

    @property
    def vehicle_speed_ms(self) -> float:
        return self.vehicle_speed_kmh / 3.6

    def provenance(self) -> dict:
        """Machine-readable record of synthetic/assumed inputs for the outputs."""
        return {
            "region_name": self.region_name,
            "crs": self.crs,
            "hazard_cell_m": self.hazard_cell_m,
            "route_cell_m": self.route_cell_m,
            "assumed": {
                "elderly_walk_speed_ms": self.elderly_walk_speed_ms,
                "vehicle_speed_kmh": self.vehicle_speed_kmh,
                "walk_cutoff": self.walk_cutoff,
                "vehicle_cutoff": self.vehicle_cutoff,
                "responder_dispatch_delay_min": self.responder_dispatch_delay_min,
                "responder_safety_margin_min": self.responder_safety_margin_min,
                "responder_time_budget_min": self.responder_time_budget_min,
                "resident_time_budget_min": self.resident_time_budget_min,
                "ingress_sample_spacing_m": self.ingress_sample_spacing_m,
                "immobile_fraction": self.immobile_fraction,
            },
            "synthetic_when_no_real_source": {
                "shelters": "coastal assembly nodes + inland open-space POIs (seeded)",
                "depots": "seeded near-town nodes (proxy 119안전센터)",
                "road_network": "8-connected lattice on the real/synthetic extent",
                "hazard": "growing severity-scaled envelope (no FIRMS bundle present)",
                "n_synthetic_shelters": self.n_synthetic_shelters,
                "n_synthetic_inland_shelters": self.n_synthetic_inland_shelters,
                "n_synthetic_depots": self.n_synthetic_depots,
                "syn_ignition_frac": list(self.syn_ignition_frac),
                "syn_fire_base_reach_m": self.syn_fire_base_reach_m,
                "syn_fire_reach_rate_m_per_min": self.syn_fire_reach_rate_m_per_min,
                "syn_fire_edge_width_m": self.syn_fire_edge_width_m,
                "syn_inland_flank_radius_m": self.syn_inland_flank_radius_m,
            },
            "seed": self.seed,
        }


# ---------------------------------------------------------------------------
# Auxiliary data: destinations (refuges) and responder depots
# ---------------------------------------------------------------------------


@dataclass
class Destination:
    """A candidate refuge / shelter in EPSG:5179."""

    name: str
    x: float
    y: float
    kind: str = "shelter"
    source: str = "synthetic"     # "real" | "synthetic"

    def as_dict(self) -> dict:
        return {"name": self.name, "x": self.x, "y": self.y,
                "kind": self.kind, "source": self.source}


@dataclass
class Depot:
    """A responder depot (fire station / 119안전센터) in EPSG:5179."""

    name: str
    x: float
    y: float
    source: str = "synthetic"     # "real" | "synthetic"

    def as_dict(self) -> dict:
        return {"name": self.name, "x": self.x, "y": self.y, "source": self.source}


# ---------------------------------------------------------------------------
# Real-source loaders + synthetic fallbacks (OSM / Korea public open data)
# ---------------------------------------------------------------------------


def load_shelters(cfg: RescueConfig, bbox_wgs84: tuple[float, float, float, float],
                  *, to_5179) -> tuple[list[Destination], str]:
    """Load candidate refuges. Real source first, else labelled synthetic fallback.

    Real source: Korea public open data 대피소·긴급대피장소 (행정안전부 / 공공데이터포털,
    https://www.data.go.kr/, e.g. dataset "전국 대피소 표준데이터"), supplied as a
    local GeoJSON/CSV at ``cfg.shelters_path`` (lon/lat columns). Returns
    ``([], "real")`` style tagging. If no file/network is available the caller
    uses :func:`synthetic_shelters` instead; this function returns ``([],
    "unavailable")`` so the fallback is explicit, never silent.
    """
    if cfg.shelters_path:
        try:
            dests = _read_point_file(cfg.shelters_path, to_5179, kind="shelter",
                                     source="real")
            if dests:
                return dests, "real"
        except Exception as exc:  # pragma: no cover - depends on local file
            return [], f"real-source-error: {exc}"
    if cfg.use_osm:
        try:  # pragma: no cover - needs network
            dests = _osm_points(bbox_wgs84, {"amenity": ["shelter", "community_centre"],
                                             "leisure": ["park"]},
                                to_5179, kind="shelter", source="real",
                                cache_dir=cfg.osm_cache_dir, tagname="shelters")
            if dests:
                return dests, "real"
        except Exception as exc:  # pragma: no cover
            return [], f"osm-error: {exc}"
    return [], "unavailable"


def load_depots(cfg: RescueConfig, bbox_wgs84: tuple[float, float, float, float],
                *, to_5179) -> tuple[list[Depot], str]:
    """Load responder depots. Real source first, else labelled synthetic fallback.

    Real source: 소방청 119안전센터 locations (공공데이터포털 "소방청_전국 119안전센터
    현황") or OSM ``amenity=fire_station``, supplied as a local GeoJSON/CSV at
    ``cfg.depots_path``. Same explicit-fallback contract as :func:`load_shelters`.
    """
    if cfg.depots_path:
        try:
            pts = _read_point_file(cfg.depots_path, to_5179, kind="depot",
                                   source="real")
            depots = [Depot(p.name, p.x, p.y, source="real") for p in pts]
            if depots:
                return depots, "real"
        except Exception as exc:  # pragma: no cover - depends on local file
            return [], f"real-source-error: {exc}"
    if cfg.use_osm:
        try:  # pragma: no cover - needs network
            pts = _osm_points(bbox_wgs84, {"amenity": "fire_station"}, to_5179,
                              kind="depot", source="real",
                              cache_dir=cfg.osm_cache_dir, tagname="depots")
            depots = [Depot(p.name, p.x, p.y, source="real") for p in pts]
            if depots:
                return depots, "real"
        except Exception as exc:  # pragma: no cover
            return [], f"osm-error: {exc}"
    return [], "unavailable"


def _read_point_file(path, to_5179, *, kind: str, source: str) -> list[Destination]:
    """Read a GeoJSON/CSV of points into reprojected :class:`Destination` rows.

    Accepts a GeoJSON FeatureCollection of Points, or a CSV with lon/lat columns
    named any of (lon, longitude, x) / (lat, latitude, y). Names come from a
    ``name``/``시설명`` property when present. Geometry is reprojected to 5179.
    """
    import geopandas as gpd  # lazy: only needed for the real-source path

    p = str(path)
    if p.lower().endswith((".geojson", ".json", ".shp", ".gpkg")):
        gdf = gpd.read_file(p)
        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:4326")
        gdf = gdf.to_crs("EPSG:5179")
        out: list[Destination] = []
        for i, row in gdf.iterrows():
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue
            name = str(row.get("name") or row.get("시설명") or f"{kind}_{i}")
            out.append(Destination(name, float(geom.x), float(geom.y),
                                   kind=kind, source=source))
        return out
    # CSV path.
    import csv

    out = []
    with open(p, newline="", encoding="utf-8") as fh:
        for i, row in enumerate(csv.DictReader(fh)):
            lon = row.get("lon") or row.get("longitude") or row.get("x") or row.get("경도")
            lat = row.get("lat") or row.get("latitude") or row.get("y") or row.get("위도")
            if lon is None or lat is None:
                continue
            x, y = to_5179.transform(float(lon), float(lat))
            name = str(row.get("name") or row.get("시설명") or f"{kind}_{i}")
            out.append(Destination(name, float(x), float(y), kind=kind, source=source))
    return out


def _osm_points(bbox_wgs84, tags, to_5179, *, kind, source, cache_dir, tagname):  # pragma: no cover
    """Fetch point POIs from OSM via OSMnx (real source; needs network).

    osmnx>=2.0: ``features_from_bbox(bbox=(left, bottom, right, top), tags=...)``.
    Results are cached to ``cache_dir`` as GeoJSON so re-runs are offline.
    """
    import os

    import geopandas as gpd
    import osmnx as ox

    os.makedirs(cache_dir, exist_ok=True)
    cache = os.path.join(cache_dir, f"{tagname}.geojson")
    if os.path.exists(cache):
        gdf = gpd.read_file(cache)
    else:
        minlon, minlat, maxlon, maxlat = bbox_wgs84
        gdf = ox.features_from_bbox(bbox=(minlon, minlat, maxlon, maxlat), tags=tags)
        gdf = gdf[gdf.geometry.notna()].copy()
        gdf["geometry"] = gdf.geometry.centroid
        gdf.to_file(cache, driver="GeoJSON")
    gdf = gdf.to_crs("EPSG:5179")
    out = []
    for i, row in gdf.iterrows():
        g = row.geometry
        if g is None or g.is_empty:
            continue
        name = str(row.get("name") or f"{kind}_{i}")
        out.append(Destination(name, float(g.x), float(g.y), kind=kind, source=source))
    return out


def load_drive_network(cfg: RescueConfig, grid: CoarseGrid, elevation, burnable_frac,
                       bbox_wgs84=None) -> tuple[RoadNetwork, str]:
    """Vehicle (responder) network. Real OSM ``drive`` graph first, else synthetic.

    The synthetic fallback is an 8-connected lattice on the real/synthetic extent
    with **constant vehicle speed** edge times (clearly labelled). The real path
    downloads an OSM drive network, reprojects to EPSG:5179, and attaches
    ``time_min`` per edge from ``cfg.vehicle_speed_kmh``.
    """
    if cfg.use_osm and bbox_wgs84 is not None:
        try:  # pragma: no cover - needs network
            net = _osm_drive_network(cfg, bbox_wgs84)
            return net, "real"
        except Exception:  # pragma: no cover
            pass
    return build_drive_network(grid, elevation, burnable_frac,
                               vehicle_speed_kmh=cfg.vehicle_speed_kmh), "synthetic"


def _osm_drive_network(cfg, bbox_wgs84):  # pragma: no cover - needs network
    """Download + reproject an OSM drive graph into our :class:`RoadNetwork`."""
    import os

    import osmnx as ox

    os.makedirs(cfg.osm_cache_dir, exist_ok=True)
    cache = os.path.join(cfg.osm_cache_dir, "drive.graphml")
    if os.path.exists(cache):
        G = ox.load_graphml(cache)
    else:
        minlon, minlat, maxlon, maxlat = bbox_wgs84
        G = ox.graph_from_bbox(bbox=(minlon, minlat, maxlon, maxlat),
                               network_type="drive")
        ox.save_graphml(G, cache)
    G = ox.project_graph(G, to_crs="EPSG:5179")
    g = nx.Graph()
    speed_ms = cfg.vehicle_speed_ms
    for n, d in G.nodes(data=True):
        g.add_node(n, x=float(d["x"]), y=float(d["y"]))
    for u, v, d in G.edges(data=True):
        length = float(d.get("length", 0.0)) or 1.0
        if g.has_edge(u, v):
            continue
        g.add_edge(u, v, length_m=length, time_min=(length / speed_ms) / 60.0)
    return RoadNetwork(graph=g, shelters=set())


# ---------------------------------------------------------------------------
# Drive network (synthetic fallback) — vehicle-speed lattice on the extent
# ---------------------------------------------------------------------------


def build_drive_network(
    grid: CoarseGrid,
    elevation: np.ndarray,
    burnable_frac: np.ndarray,
    *,
    vehicle_speed_kmh: float = DEFAULT_VEHICLE_SPEED_KMH,
    water_burnable_max: float = 0.05,
) -> RoadNetwork:
    """8-connected vehicle lattice on land cells with constant-speed edge times.

    Mirrors :func:`~wildfireguardian.routing.evacuation.build_evacuation_network`
    (same land mask / node ids so a walk node and a drive node on the same cell
    share an id) but uses a flat vehicle speed for ``time_min`` rather than the
    elderly Tobler walk speed. Shelters are intentionally empty: depots and
    destinations are attached by the caller. Clearly synthetic when the extent
    itself is synthetic; the algorithm is identical on a real OSM drive graph.
    """
    g = nx.Graph()
    nrows, ncols = grid.nrows, grid.ncols
    elev = np.where(np.isfinite(elevation), elevation, 0.0)
    is_land = burnable_frac > water_burnable_max
    speed_ms = vehicle_speed_kmh / 3.6

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
                g.add_edge(nid(r, c), nid(rr, ccol),
                           length_m=length, time_min=(length / speed_ms) / 60.0)
    return RoadNetwork(graph=g, shelters=set())


# ---------------------------------------------------------------------------
# Ingress-corridor survival (the core new logic)
# ---------------------------------------------------------------------------


def sample_corridor_points(
    net: RoadNetwork, nodes: list[int], spacing_m: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Sample a node path into EPSG:5179 points, ``spacing_m`` apart per segment.

    Returns ``(xs, ys, seg_id)``. **Every** segment ``i`` of the path contributes
    at least its two endpoints, so no segment is ever silently dropped — the
    orientation/coverage regression test asserts exactly this. A degenerate
    single-node "corridor" (depot == target) samples that one node.
    """
    if len(nodes) == 0:
        return np.empty(0), np.empty(0), np.empty(0, dtype=int)
    if len(nodes) == 1:
        x, y = net.node_xy(nodes[0])
        return np.array([x]), np.array([y]), np.array([0])
    xs: list[float] = []
    ys: list[float] = []
    seg: list[int] = []
    for i in range(len(nodes) - 1):
        x0, y0 = net.node_xy(nodes[i])
        x1, y1 = net.node_xy(nodes[i + 1])
        dist = math.hypot(x1 - x0, y1 - y0)
        nseg = max(1, int(math.ceil(dist / spacing_m)))
        for k in range(nseg + 1):
            t = k / nseg
            xs.append(x0 + t * (x1 - x0))
            ys.append(y0 + t * (y1 - y0))
            seg.append(i)
    return np.asarray(xs, float), np.asarray(ys, float), np.asarray(seg, int)


def corridor_survival_time(
    hazard: HazardSequence, xs: np.ndarray, ys: np.ndarray, cutoff: float,
) -> float:
    """Earliest forecast *time slice* (min) at which ANY sampled point ≥ ``cutoff``.

    Iterates the hazard's **discrete** ``times_min`` slices (mirroring
    :func:`evacuation._time_to_cutoff`) so the result is exactly one of the model's
    forecast times — which is what the unit test pins down. ``inf`` if the corridor
    never crosses the cutoff within the horizon.
    """
    if len(xs) == 0:
        return math.inf
    for t in hazard.times_min:
        probs = hazard.prob_at_points(xs, ys, float(t))
        if np.any(probs >= cutoff):
            return float(t)
    return math.inf


def node_survival_time(hazard: HazardSequence, x: float, y: float, cutoff: float) -> float:
    """Earliest time slice at which a single location reaches ``cutoff`` (inf if never)."""
    return corridor_survival_time(hazard, np.array([x]), np.array([y]), cutoff)


@dataclass
class IngressResult:
    """Vehicle-ingress assessment for one destination/home from one (best) depot."""

    reachable: bool
    depot_index: int | None
    responder_eta_min: float
    ingress_survival_time_min: float        # inf if the corridor never gets cut
    closing_window_min: float               # survival - ETA  (urgency; smaller = sooner)
    corridor_nodes: list[int] = field(default_factory=list)
    n_samples: int = 0
    note: str = ""

    def as_dict(self) -> dict:
        d = asdict(self)
        d.pop("corridor_nodes")
        d["corridor_len_nodes"] = len(self.corridor_nodes)
        for k in ("responder_eta_min", "ingress_survival_time_min", "closing_window_min"):
            v = d[k]
            d[k] = (None if (v is None or math.isinf(v)) else round(v, 2))
        return d


def ingress_corridor(
    drive: RoadNetwork, depot_node: int, target_node: int, hazard: HazardSequence,
    cfg: RescueConfig, *, depot_index: int = 0,
) -> IngressResult:
    """Assess the vehicle access corridor depot → target on the drive network.

    The corridor is the **shortest-time** drive route (the access route a
    responder would take). ``responder_ETA`` is the *estimated time of arrival* =
    dispatch delay (detection + mobilisation) + drive travel time at vehicle
    speed. The corridor is sampled and its earliest cutoff-crossing time is the
    ``ingress_survival_time``. The target is ``rescue_reachable`` from this depot
    iff ``survival ≥ ETA + safety_margin`` (the brief's formula, with a realistic
    delayed ETA).
    """
    try:
        travel, path = nx.single_source_dijkstra(
            drive.graph, depot_node, target=target_node, weight="time_min")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return IngressResult(False, depot_index, math.inf, math.inf, -math.inf,
                             [], 0, "no drive path depot->target")
    eta = cfg.responder_dispatch_delay_min + travel
    xs, ys, _seg = sample_corridor_points(drive, path, cfg.ingress_sample_spacing_m)
    survival = corridor_survival_time(hazard, xs, ys, cfg.vehicle_cutoff)
    window = survival - eta
    reachable = survival >= eta + cfg.responder_safety_margin_min
    return IngressResult(
        reachable=reachable, depot_index=depot_index,
        responder_eta_min=eta, ingress_survival_time_min=survival,
        closing_window_min=window, corridor_nodes=path, n_samples=len(xs),
        note="" if reachable else "ingress cut before responder ETA + margin",
    )


def assess_ingress(
    drive: RoadNetwork, depot_nodes: list[int], target_node: int,
    hazard: HazardSequence, cfg: RescueConfig,
) -> IngressResult:
    """Best vehicle-ingress assessment over all depots for one target.

    Among depots whose corridor is ``reachable`` we pick the smallest responder
    ETA (fastest help). If none can reach in time we return the corridor with the
    largest (least-negative / longest) closing window for honest reporting, marked
    ``reachable = False``. Never invents a reachable corridor.
    """
    results = [ingress_corridor(drive, dn, target_node, hazard, cfg, depot_index=i)
               for i, dn in enumerate(depot_nodes)]
    feasible = [r for r in results if r.reachable]
    if feasible:
        return min(feasible, key=lambda r: r.responder_eta_min)
    if not results:
        return IngressResult(False, None, math.inf, math.inf, -math.inf, [], 0,
                             "no depots")
    # Report the best-surviving (largest closing window) infeasible corridor.
    return max(results, key=lambda r: r.closing_window_min)


@dataclass
class DestinationAssessment:
    """Per-destination node attributes attached for the router (brief §2)."""

    name: str
    node: int
    x: float
    y: float
    source: str
    is_shelter: bool
    vehicle_accessible: bool
    ingress_survival_time_min: float
    responder_eta_min: float
    rescue_reachable: bool
    safe: bool

    def as_dict(self) -> dict:
        d = asdict(self)
        for k in ("ingress_survival_time_min", "responder_eta_min"):
            v = d[k]
            d[k] = (None if (v is None or math.isinf(v)) else round(v, 2))
        return d


def assess_destinations(
    destinations: list[Destination], drive: RoadNetwork, depot_nodes: list[int],
    hazard: HazardSequence, cfg: RescueConfig,
) -> list[DestinationAssessment]:
    """Snap each destination to the drive net and assess its rescue-reachability.

    ``safe`` is the weaker property "this location is not (about to be) impassable
    at t0" (its own survival time ≥ the responder margin). ``rescue_reachable``
    additionally requires a surviving corridor from a depot within ETA + margin.
    By construction ``rescue_reachable ⊆ safe`` (the destination is the corridor
    endpoint, so corridor survival ≤ its own survival).
    """
    out: list[DestinationAssessment] = []
    for d in destinations:
        node = drive.nearest_node(d.x, d.y)
        ing = assess_ingress(drive, depot_nodes, node, hazard, cfg)
        own_surv = node_survival_time(hazard, d.x, d.y, cfg.vehicle_cutoff)
        safe = own_surv >= cfg.responder_safety_margin_min
        vehicle_accessible = bool(ing.corridor_nodes)
        out.append(DestinationAssessment(
            name=d.name, node=node, x=d.x, y=d.y, source=d.source,
            is_shelter=True, vehicle_accessible=vehicle_accessible,
            ingress_survival_time_min=ing.ingress_survival_time_min,
            responder_eta_min=ing.responder_eta_min,
            rescue_reachable=bool(ing.reachable), safe=bool(safe),
        ))
    return out


# ---------------------------------------------------------------------------
# Resident-side routing (policies a / b / c)
# ---------------------------------------------------------------------------


def _walk_net_to(net: RoadNetwork, shelter_nodes: set[int]) -> RoadNetwork:
    """A shallow view of ``net`` whose shelter (target) set is ``shelter_nodes``."""
    return RoadNetwork(graph=net.graph, shelters=set(shelter_nodes))


def resident_policies(
    walk: RoadNetwork, origin: int, hazard: HazardSequence,
    refuge_nodes_all: set[int], refuge_nodes_reachable: set[int], cfg: RescueConfig,
    *, departure_min: float = 0.0,
) -> dict[str, RouteResult]:
    """Three resident policies to the same refuge universe; only the policy differs.

    (a) ``naive`` — fire-blind shortest walk to the nearest refuge (status quo).
    (b) ``future_aware_any`` — exposure-minimising walk to *any* safe refuge
        (the current method).
    (c) ``future_aware_rescue`` — exposure-minimising walk to the nearest
        *rescue-reachable* refuge (the new method).
    """
    net_all = _walk_net_to(walk, refuge_nodes_all)
    net_rr = _walk_net_to(walk, refuge_nodes_reachable)
    out: dict[str, RouteResult] = {}
    out["naive"] = naive_route(net_all, origin, hazard, departure_min=departure_min,
                               p_cut=cfg.walk_cutoff)
    out["future_aware_any"] = future_aware_route(
        net_all, origin, hazard, departure_min=departure_min,
        time_budget_min=cfg.resident_time_budget_min, p_cut=cfg.walk_cutoff,
        time_step_min=cfg.time_step_min)
    if refuge_nodes_reachable:
        out["future_aware_rescue"] = future_aware_route(
            net_rr, origin, hazard, departure_min=departure_min,
            time_budget_min=cfg.resident_time_budget_min, p_cut=cfg.walk_cutoff,
            time_step_min=cfg.time_step_min)
    else:
        out["future_aware_rescue"] = RouteResult(
            kind="future_aware", reached=False, route=[], target=None,
            departure_min=departure_min, total_distance_m=0.0, total_time_min=0.0,
            note="no rescue-reachable refuge exists")
    return out


# ---------------------------------------------------------------------------
# Rescuer-side routing ("send the rescuer, not the resident")
# ---------------------------------------------------------------------------


def rescuer_route(
    drive: RoadNetwork, depot_node: int, home_node: int, hazard: HazardSequence,
    cfg: RescueConfig, *, departure_min: float | None = None,
) -> RouteResult:
    """Survival-aware responder route depot → home on the drive network.

    Reuses the future-aware (exposure-minimising, time-expanded) router with the
    **vehicle** speed (already baked into the drive net's ``time_min``) and the
    **vehicle** cutoff, targeting the home, departing at the dispatch delay (so it
    meets the fire as it will be when the responder actually moves). Because
    forbidden edges are those into cells at/above the vehicle cutoff at the arrival
    time, a shorter corridor that gets cut is rejected in favour of a longer
    surviving one — exactly the behaviour the unit test asserts.
    """
    dep = cfg.responder_dispatch_delay_min if departure_min is None else departure_min
    net = _walk_net_to(drive, {home_node})
    return future_aware_route(
        net, depot_node, hazard, departure_min=dep,
        time_budget_min=cfg.responder_time_budget_min, p_cut=cfg.vehicle_cutoff,
        time_step_min=cfg.time_step_min)


def rescuer_shortest_ingress(
    drive: RoadNetwork, depot_node: int, home_node: int, hazard: HazardSequence,
    cfg: RescueConfig, *, departure_min: float | None = None,
) -> RouteResult:
    """Fire-blind shortest-distance responder ingress (the contrast for §5)."""
    dep = cfg.responder_dispatch_delay_min if departure_min is None else departure_min
    net = _walk_net_to(drive, {home_node})
    return naive_route(net, depot_node, hazard, departure_min=dep,
                       p_cut=cfg.vehicle_cutoff)


def rescuer_reachable(
    drive: RoadNetwork, depot_nodes: list[int], home_node: int,
    hazard: HazardSequence, cfg: RescueConfig,
) -> tuple[bool, RouteResult | None, int | None]:
    """Strongest honest home-reachability test: can ANY depot's survival-aware
    responder route actually reach the home safely (detours allowed) within budget?

    Returns ``(reachable, best_route, depot_index)``. This — not the direct-corridor
    screening — is what decides the four-way ``no_surviving_vehicle_ingress`` class
    and the dispatch/unreachable split, so a home is only ever called unreachable
    when even the exposure-minimising, detouring router fails. Never imputes a route.
    """
    best: tuple[int, RouteResult] | None = None
    for i, dn in enumerate(depot_nodes):
        rt = rescuer_route(drive, dn, home_node, hazard, cfg)
        if rt.reached and not rt.enters_hazard:
            if best is None or rt.exposure < best[1].exposure:
                best = (i, rt)
    if best is None:
        return False, None, None
    return True, best[1], best[0]


@dataclass
class DispatchEntry:
    """One home on the prioritized responder dispatch list."""

    home_node: int
    x: float
    y: float
    depot_index: int | None
    responder_eta_min: float
    ingress_survival_time_min: float
    closing_window_min: float            # urgency key (ascending = most urgent first)
    survival_aware_exposure: float
    shortest_path_exposure: float
    shortest_path_enters_hazard: bool

    def as_dict(self) -> dict:
        d = asdict(self)
        for k in ("responder_eta_min", "ingress_survival_time_min",
                  "closing_window_min", "survival_aware_exposure",
                  "shortest_path_exposure"):
            v = d[k]
            d[k] = (None if (v is None or math.isinf(v)) else round(v, 3))
        return d


def build_dispatch_list(
    home_nodes: list[int], drive: RoadNetwork, depot_nodes: list[int],
    depots: list[Depot], hazard: HazardSequence, cfg: RescueConfig,
) -> tuple[list[DispatchEntry], list[dict]]:
    """Prioritized dispatch list + the honestly-reported unreachable set.

    ``home_nodes`` are the homes that need a rescuer (residents who cannot self-
    evacuate on foot — immobile, or whose pedestrian route the fire cut). A home is
    dispatchable iff the survival-aware responder router can actually reach it
    (:func:`rescuer_reachable`); otherwise it goes on the unreachable set —
    reported, never imputed. Dispatchable homes are ranked by urgency =
    ``ingress_survival_time − responder_ETA`` (closing window) ascending (smallest
    window = most urgent first), and carry the survival-aware vs shortest-path
    ingress exposures for the responder-side contrast.
    """
    dispatch: list[DispatchEntry] = []
    unreachable: list[dict] = []
    for h in home_nodes:
        hx, hy = drive.node_xy(h)
        reachable, sa, depot_idx = rescuer_reachable(drive, depot_nodes, h, hazard, cfg)
        if not reachable or depot_idx is None:
            best = assess_ingress(drive, depot_nodes, h, hazard, cfg)  # for context only
            unreachable.append({
                "home_node": int(h), "x": hx, "y": hy,
                "nearest_depot_index": best.depot_index,
                "best_closing_window_min": (None if math.isinf(best.closing_window_min)
                                            else round(best.closing_window_min, 2)),
                "reason": "no surviving vehicle ingress (even with detours) in budget",
            })
            continue
        depot_node = depot_nodes[depot_idx]
        ing = ingress_corridor(drive, depot_node, h, hazard, cfg, depot_index=depot_idx)
        sp = rescuer_shortest_ingress(drive, depot_node, h, hazard, cfg)
        dispatch.append(DispatchEntry(
            home_node=int(h), x=hx, y=hy, depot_index=depot_idx,
            responder_eta_min=ing.responder_eta_min,
            ingress_survival_time_min=ing.ingress_survival_time_min,
            closing_window_min=ing.closing_window_min,
            survival_aware_exposure=(sa.exposure if sa else math.inf),
            shortest_path_exposure=(sp.exposure if sp.reached else math.inf),
            shortest_path_enters_hazard=bool(sp.enters_hazard),
        ))
    dispatch.sort(key=lambda e: e.closing_window_min)
    return dispatch, unreachable


# ---------------------------------------------------------------------------
# Four-way origin classification (must sum to N)
# ---------------------------------------------------------------------------

#: The four mutually-exclusive, exhaustive origin outcome classes.
FOUR_WAY_CLASSES: tuple[str, ...] = (
    "saved_by_rescue_reachable_refuge",   # new method gets the resident out safely
    "already_safe",                       # naive route was already safe
    "no_safe_pedestrian_route",           # can't self-evac, BUT a rescuer can reach
    "no_surviving_vehicle_ingress",       # can't self-evac AND rescuer can't reach
)


def classify_origin(
    policies: dict[str, RouteResult], home_reachable_by_rescuer: bool,
) -> str:
    """Assign one origin to exactly one of :data:`FOUR_WAY_CLASSES`.

    Decision order (exclusive & exhaustive):

    1. naive walk already safe                      -> ``already_safe``
    2. else future-aware → rescue-reachable refuge safe
                                                    -> ``saved_by_rescue_reachable_refuge``
    3. else a responder CAN reach the home          -> ``no_safe_pedestrian_route``
       (the resident cannot self-evacuate, but a responder can be dispatched)
    4. else                                         -> ``no_surviving_vehicle_ingress``
       (cannot walk out *and* cannot be driven out — the honest unreachable set)

    ``home_reachable_by_rescuer`` is the strongest honest test
    (:func:`rescuer_reachable`): only if even the detouring, exposure-minimising
    responder route fails is the home placed in the unreachable class.
    """
    naive = policies["naive"]
    fa_rr = policies["future_aware_rescue"]
    if naive.reached and not naive.enters_hazard:
        return "already_safe"
    if fa_rr.reached and not fa_rr.enters_hazard:
        return "saved_by_rescue_reachable_refuge"
    if home_reachable_by_rescuer:
        return "no_safe_pedestrian_route"
    return "no_surviving_vehicle_ingress"


__all__ = [
    "DEFAULT_VEHICLE_SPEED_KMH",
    "DEFAULT_WALK_CUTOFF",
    "DEFAULT_VEHICLE_CUTOFF",
    "RescueConfig",
    "Destination",
    "Depot",
    "load_shelters",
    "load_depots",
    "load_drive_network",
    "build_drive_network",
    "sample_corridor_points",
    "corridor_survival_time",
    "node_survival_time",
    "IngressResult",
    "ingress_corridor",
    "assess_ingress",
    "DestinationAssessment",
    "assess_destinations",
    "resident_policies",
    "rescuer_route",
    "rescuer_shortest_ingress",
    "DispatchEntry",
    "build_dispatch_list",
    "FOUR_WAY_CLASSES",
    "classify_origin",
]
