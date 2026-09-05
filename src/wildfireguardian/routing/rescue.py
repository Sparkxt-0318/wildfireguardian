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

import heapq
import math
from dataclasses import asdict, dataclass, field

import networkx as nx
import numpy as np

from ..config import get as _cfg
from ..spread_v2.grid import CoarseGrid
from .evacuation import (
    ELDERLY_FLAT_SPEED_MS,
    RouteResult,
    future_aware_route,
    naive_route,
)
from .future_front import RoadNetwork
from .hazard import HazardSequence

# Every default below is read from config/default.yaml (PHASE 1-A) with the
# historical Round-2 literal as an explicit fallback. Moving the values, not
# changing them: scripts/verify_numbers.py asserts config == these literals.

#: Default responder vehicle speed (km/h) on rural East-Coast roads. ASSUMED.
DEFAULT_VEHICLE_SPEED_KMH: float = float(_cfg("responder.vehicle_speed_kmh", 40.0))
#: Pedestrian (elderly) impassable cutoff — reuse the routing default.
DEFAULT_WALK_CUTOFF: float = float(_cfg("pedestrian.walk_cutoff_p", 0.5))
#: SEPARATE, higher vehicle-impassable cutoff: a responder vehicle moves fast and
#: may accept more risk than a walking elder. ASSUMED; exposed via config.
DEFAULT_VEHICLE_CUTOFF: float = float(_cfg("responder.vehicle_cutoff_p", 0.7))


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
    region_name: str = _cfg("project.region_name", "yeongdeok_2025")  # key into utils.regions
    crs: str = _cfg("project.crs", "EPSG:5179")
    hazard_cell_m: float = float(_cfg("grid.hazard_cell_m", 375.0))   # 375 m hazard grid (per brief)
    route_cell_m: float = float(_cfg("grid.route_cell_m", 750.0))     # walk/drive lattice spacing

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
    responder_dispatch_delay_min: float = float(_cfg("responder.dispatch_delay_min", 30.0))
    responder_safety_margin_min: float = float(_cfg("responder.safety_margin_min", 12.0))
    responder_time_budget_min: float = float(_cfg("responder.time_budget_min", 75.0))
    resident_time_budget_min: float = float(_cfg("pedestrian.walk_budget_min", 600.0))

    # -- corridor sampling / time discretisation ---------------------------
    ingress_sample_spacing_m: float = float(_cfg("responder.ingress_sample_spacing_m", 150.0))
    time_step_min: float = float(_cfg("time.routing_time_step_min", 10.0))

    # -- round-trip margin (SESSION 8, Phase 1) ----------------------------
    # On-scene load (승차·수용) time. ASSUMED — swept in scripts/run_margin_sweep.py.
    t_load_min: float = float(_cfg("responder.t_load_min", 10.0))
    # Egress policy: "same_route" returns along the ingress corridor (현장
    # 실무자 자문 N=1: 「들어가서 그 길로 나오는 게 원칙」 — a stated doctrine,
    # not a measurement; docs/firefighter_consultation.md §2). "free" lets the
    # survival-aware router pick a fresh egress route at the egress departure
    # time.
    egress_policy: str = str(_cfg("responder.egress_policy", "same_route"))

    # -- immobile residents (the "send the rescuer" population) ------------
    immobile_fraction: float = float(_cfg("population.immobile_fraction", 0.3))

    # -- synthetic fallback knobs (ALL SYNTHETIC, tagged) ------------------
    n_synthetic_shelters: int = int(_cfg("synthetic_hazard.n_shelters", 12))
    n_synthetic_inland_shelters: int = int(_cfg("synthetic_hazard.n_inland_shelters", 8))
    n_synthetic_depots: int = int(_cfg("responder.n_depots_synthetic", 2))
    scan_stride: int = int(_cfg("origin_scan.rescue_stride", 3))
    sweep_max_origins: int = int(_cfg("origin_scan.sweep_max_origins", 200))

    # -- synthetic hazard envelope (SYNTHETIC; tunable, no FIRMS present) ---
    syn_ignition_frac: tuple[float, float] = tuple(  # type: ignore[assignment]
        _cfg("synthetic_hazard.ignition_frac", (0.46, 0.5)))     # (E-W, N-S) of extent
    syn_fire_base_reach_m: float = float(_cfg("synthetic_hazard.base_reach_m", 2200.0))
    syn_fire_reach_rate_m_per_min: float = float(
        _cfg("synthetic_hazard.reach_rate_m_per_min", 52.0))     # ~3 km/h sustained growth
    syn_fire_edge_width_m: float = float(_cfg("synthetic_hazard.edge_width_m", 1100.0))
    syn_inland_flank_radius_m: float = float(
        _cfg("synthetic_hazard.inland_flank_radius_m", 5000.0))

    # -- real-source data (optional; loaders fall back to synthetic) -------
    shelters_path: str | None = None            # 공공데이터포털 대피소 GeoJSON/CSV
    depots_path: str | None = None              # 119안전센터 / OSM fire_station file
    osm_cache_dir: str = _cfg("paths.osm_cache_dir", "data/cache/osm")
    # NB: the effective directory is `osm_cache_path` = this / region_name.
    # Never join cache filenames onto `osm_cache_dir` directly.
    use_osm: bool = False                       # try OSMnx download (needs network)

    # -- determinism -------------------------------------------------------
    seed: int = int(_cfg("seeds.canonical", 20250603))

    @property
    def vehicle_speed_ms(self) -> float:
        return self.vehicle_speed_kmh / 3.6

    @property
    def osm_cache_path(self) -> "Path":
        """Per-region OSM cache directory: ``{osm_cache_dir}/{region_name}/``.

        The cache filenames are fixed (``walk.graphml``, ``shelters.geojson``,
        …), so before Round-3 PHASE 5 every region shared one directory and
        acquiring a second region would have silently OVERWRITTEN the first.
        That is exactly how the 2026-07-23 walk graph was lost
        (``docs/DATA_LOSS_2026-07-24.md``) — a fixed path plus a new fetch.

        Isolating by region makes the collision impossible rather than unlikely.
        """
        from pathlib import Path

        return Path(self.osm_cache_dir) / self.region_name

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
                "t_load_min": self.t_load_min,
                "egress_policy": self.egress_policy,
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
                                to_5179, kind="shelter", source="osm",
                                cache_dir=str(cfg.osm_cache_path), tagname="shelters")
            if dests:
                return dests, "osm"
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
                              kind="depot", source="osm",
                              cache_dir=str(cfg.osm_cache_path), tagname="depots")
            depots = [Depot(p.name, p.x, p.y, source="osm") for p in pts]
            if depots:
                return depots, "osm"
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
    ``time_min`` per edge from ``cfg.vehicle_speed_kmh``. The OSM path returns the
    tag ``"osm"`` (OpenStreetMap road geometry — a real-world source, distinct from
    an authoritative government road file).
    """
    if cfg.use_osm and bbox_wgs84 is not None:
        try:  # pragma: no cover - needs network
            net = _osm_drive_network(cfg, bbox_wgs84)
            return net, "osm"
        except Exception:  # pragma: no cover
            pass
    return build_drive_network(grid, elevation, burnable_frac,
                               vehicle_speed_kmh=cfg.vehicle_speed_kmh), "synthetic"


def load_walk_network(cfg: RescueConfig, grid: CoarseGrid, elevation, burnable_frac,
                      bbox_wgs84=None) -> tuple[RoadNetwork, str]:
    """Pedestrian (resident) network. Real OSM ``walk`` graph first, else synthetic.

    This fills the walk-network gap that mirrored :func:`load_drive_network` on
    the vehicle side. The synthetic fallback is the slope-aware elderly-walk
    lattice built by
    :func:`~wildfireguardian.routing.evacuation.build_evacuation_network` (node
    positions / elevations / coast are real when the extent is real; only the
    street topology is synthetic). The real path downloads an OSM ``walk`` graph,
    reprojects to EPSG:5179, and attaches ``time_min`` per edge from a **flat**
    elderly walk speed (``cfg.elderly_walk_speed_ms``) — the OSM path carries no
    per-node elevation here, so no synthetic slope is invented; terrain-aware
    walk timing waits on the DEM in the FIRMS bundle. Returns tag ``"osm"``.
    """
    from .evacuation import build_evacuation_network

    if cfg.use_osm and bbox_wgs84 is not None:
        try:  # pragma: no cover - needs network
            net = _osm_walk_network(cfg, bbox_wgs84)
            return net, "osm"
        except Exception:  # pragma: no cover
            pass
    return build_evacuation_network(grid, elevation, burnable_frac,
                                    flat_speed_ms=cfg.elderly_walk_speed_ms), "synthetic"


def _osm_walk_network(cfg, bbox_wgs84):  # pragma: no cover - needs network
    """Download + reproject an OSM ``walk`` graph into our :class:`RoadNetwork`.

    Edge ``time_min`` uses the flat elderly walk speed (no DEM => no synthetic
    slope). Cached to ``walk.graphml`` so re-runs are offline. ``shelters`` is left
    empty; the caller attaches the snapped shelter-POI nodes as targets.
    """
    import os

    import osmnx as ox

    os.makedirs(cfg.osm_cache_path, exist_ok=True)
    cache = os.path.join(cfg.osm_cache_path, "walk.graphml")
    if os.path.exists(cache):
        G = ox.load_graphml(cache)
    else:
        minlon, minlat, maxlon, maxlat = bbox_wgs84
        G = ox.graph_from_bbox(bbox=(minlon, minlat, maxlon, maxlat),
                               network_type="walk")
        ox.save_graphml(G, cache)
    G = ox.project_graph(G, to_crs="EPSG:5179")
    g = nx.Graph()
    speed_ms = cfg.elderly_walk_speed_ms
    for n, d in G.nodes(data=True):
        g.add_node(n, x=float(d["x"]), y=float(d["y"]))
    for u, v, d in G.edges(data=True):
        length = float(d.get("length", 0.0)) or 1.0
        if g.has_edge(u, v):
            continue
        g.add_edge(u, v, length_m=length, time_min=(length / speed_ms) / 60.0)
    return RoadNetwork(graph=g, shelters=set())


def _osm_drive_network(cfg, bbox_wgs84):  # pragma: no cover - needs network
    """Download + reproject an OSM drive graph into our :class:`RoadNetwork`."""
    import os

    import osmnx as ox

    os.makedirs(cfg.osm_cache_path, exist_ok=True)
    cache = os.path.join(cfg.osm_cache_path, "drive.graphml")
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


# ---------------------------------------------------------------------------
# Rescue CAPACITY / supply-side triage  (additive layer on top of dispatch)
# ---------------------------------------------------------------------------
#
# The pipeline above computes the *demand*: which homes need a rescuer and, of
# those, which have a surviving vehicle corridor (the prioritized dispatch list)
# vs none (geometry_unreachable). It never asked whether the fire service can
# *supply* that many rescues in the operational window. This layer closes that
# gap WITHOUT touching the spread model or the routing logic: it takes the
# already-built, already-prioritized dispatch list and the already-computed
# per-home responder ETA / ingress-survival, adds a parameterized number of
# rescue units + a per-rescue service time, and runs a transparent capacity-
# limited assignment over the EXISTING priority order. The framing is the
# demand–supply gap (the quantitative case for pre-positioning + triage), not a
# single "X saved" — capacity numbers are PoC parameters, not measured 영덕
# fire-service capacity.


@dataclass(frozen=True)
class RescueCapacityConfig:
    """PoC supply-side parameters for the capacity/triage layer (new, additive).

    These are **PoC parameters, NOT measured 영덕 fire-service capacity** — the
    deliverable is the demand–supply *curve* across unit counts, never a single
    "X rescued". The operational window ``W`` and the per-home responder ETA /
    ingress-survival come unchanged from :class:`RescueConfig`; this only adds the
    *supply* side. Anything here is flagged in :meth:`provenance`.
    """

    n_rescue_units: int = 3                  # PoC: simultaneous rescue teams from depot(s)
    rescue_service_time_min: float = 25.0    # PoC fixed per-rescue cycle occupancy; ASSUMED

    def provenance(self) -> dict:
        return {
            "n_rescue_units": self.n_rescue_units,
            "rescue_service_time_min": self.rescue_service_time_min,
            "PoC_not_measured": (
                "Capacity (unit count + service time) is a PoC parameter, NOT "
                "measured 영덕 fire-service capacity. The result is the demand–"
                "supply curve; absolute 'rescued' counts are illustrative."
            ),
        }


#: The two capacity-triage outcomes for the DISPATCHABLE (reachable) homes. Together
#: with the unchanged ``no_surviving_vehicle_ingress`` (geometry) set they form the
#: three-way partition of the needs-rescuer pool.
TRIAGE_CLASSES: tuple[str, ...] = ("rescued_in_time", "capacity_deferred")


@dataclass
class TriageOutcome:
    """Capacity-triage result for one dispatchable (reachable) home."""

    home_node: int
    x: float
    y: float
    outcome: str                     # "rescued_in_time" | "capacity_deferred"
    priority_rank: int               # 0 = most urgent (closing window ascending)
    depot_index: int | None
    responder_eta_min: float
    ingress_survival_time_min: float
    closing_window_min: float
    deadline_min: float              # min(ingress_survival, dispatch_delay + W)
    assigned_unit: int | None        # serving unit id (None if deferred)
    depart_min: float | None         # when the serving unit left the depot
    arrival_min: float | None        # earliest-available unit's arrival at the home
    #  (== the actual arrival when rescued; the best a unit could have done when
    #   deferred — recorded so the priority/feasibility invariant is auditable)

    def as_dict(self) -> dict:
        d = asdict(self)
        for k in ("responder_eta_min", "ingress_survival_time_min",
                  "closing_window_min", "deadline_min", "depart_min", "arrival_min"):
            v = d[k]
            d[k] = (None if (v is None or math.isinf(v)) else round(v, 2))
        return d


@dataclass
class CapacityTriageResult:
    """Outcome of one capacity-limited triage over a fixed dispatch list."""

    n_rescue_units: int
    rescue_service_time_min: float
    window_min: float
    dispatch_delay_min: float
    n_dispatch: int
    n_rescued_in_time: int
    n_capacity_deferred: int
    outcomes: list[TriageOutcome] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        return {"rescued_in_time": self.n_rescued_in_time,
                "capacity_deferred": self.n_capacity_deferred}

    def three_way(self, n_geometry_unreachable: int) -> dict[str, int]:
        """The three-way partition of the needs-rescuer pool (sums to its size)."""
        return {"rescued_in_time": self.n_rescued_in_time,
                "capacity_deferred": self.n_capacity_deferred,
                "geometry_unreachable": int(n_geometry_unreachable)}

    def summary(self, n_geometry_unreachable: int) -> dict:
        tw = self.three_way(n_geometry_unreachable)
        needs = sum(tw.values())
        return {
            "n_rescue_units": self.n_rescue_units,
            "rescue_service_time_min": self.rescue_service_time_min,
            "window_min": self.window_min,
            "dispatch_delay_min": self.dispatch_delay_min,
            "n_needs_rescuer": needs,
            "n_dispatch_reachable": self.n_dispatch,
            "three_way": tw,
            "pct_demand_met": (round(100.0 * tw["rescued_in_time"] / needs, 1)
                               if needs else 0.0),
            "pct_reachable_demand_met": (round(100.0 * self.n_rescued_in_time
                                               / self.n_dispatch, 1)
                                         if self.n_dispatch else 0.0),
        }


def capacity_triage(
    dispatch: list[DispatchEntry], cfg: RescueConfig, cap: RescueCapacityConfig,
) -> CapacityTriageResult:
    """Capacity-limited triage over the EXISTING priority order (greedy discrete-event).

    ``dispatch`` is the prioritized dispatch list from :func:`build_dispatch_list`
    — the homes whose vehicle corridor survives long enough for a responder to reach
    them (the *demand* a rescuer can in principle serve), already ranked by urgency =
    ``ingress_survival − responder_ETA`` ascending (smallest closing window = most
    urgent first). This layer adds the *supply* constraint: only ``cap.n_rescue_units``
    teams operate, each occupied ``cap.rescue_service_time_min`` per rescue.

    Assignment rule (transparent, auditable — the existing priority IS the triage):

    1. Every unit is available to depart the depot at ``responder_dispatch_delay_min``
       (mobilised once after the initial detection + mobilisation lag).
    2. Walk the dispatch list **most-urgent first**. Assign each home to the unit that
       becomes free earliest; that unit departs at its ``free_at`` and ARRIVES at the
       home at ``free_at + (responder_ETA − dispatch_delay)`` — i.e. it drives the
       already-computed responder corridor (the dispatch-delay part of the ETA is the
       one-time mobilisation, already in ``free_at``).
    3. The home is ``rescued_in_time`` iff that arrival is no later than its
       ``deadline = min(ingress_survival_time, dispatch_delay + W)`` — the access
       corridor is still open AND the responder is within the operational window. The
       serving unit is then busy for ``rescue_service_time_min`` (one rescue cycle)
       before it can take another home.
    4. Otherwise the home is ``capacity_deferred`` — a *supply* failure: a surviving
       route exists, but no unit reaches it in time given the unit count + window.

    Because units only ever become free *later*, the earliest-available unit gives the
    earliest achievable arrival for the current home; if even it misses the deadline,
    no unit can — so deferral respects priority (a lower-priority home is never served
    while a higher-priority, still-open, reachable home could have been served by a
    free unit). At ``n_rescue_units ≥ len(dispatch)`` every dispatchable home is
    rescued, so ``capacity_deferred → 0`` and the layer is a strict refinement that
    recovers the original geometry-only unreachable set. ``geometry_unreachable`` homes
    are not in ``dispatch`` and never enter here.
    """
    delay = float(cfg.responder_dispatch_delay_min)
    window = float(cfg.responder_time_budget_min)
    service = float(cap.rescue_service_time_min)
    n_units = max(0, int(cap.n_rescue_units))

    # Min-heap of (free_at, unit_id); every unit mobilised at the dispatch delay.
    free: list[tuple[float, int]] = [(delay, u) for u in range(n_units)]
    heapq.heapify(free)

    outcomes: list[TriageOutcome] = []
    n_rescued = 0
    for rank, e in enumerate(dispatch):           # dispatch is priority-ordered
        travel_in = max(0.0, e.responder_eta_min - delay)
        deadline = min(e.ingress_survival_time_min, delay + window)
        unit = depart = arrival = None
        served = False
        if free:
            t, uid = free[0]                      # earliest-available unit
            arr = t + travel_in
            arrival = arr
            if arr <= deadline + 1e-9:
                heapq.heapreplace(free, (t + service, uid))
                served, unit, depart = True, uid, t
        if served:
            n_rescued += 1
        outcomes.append(TriageOutcome(
            home_node=e.home_node, x=e.x, y=e.y,
            outcome="rescued_in_time" if served else "capacity_deferred",
            priority_rank=rank, depot_index=e.depot_index,
            responder_eta_min=e.responder_eta_min,
            ingress_survival_time_min=e.ingress_survival_time_min,
            closing_window_min=e.closing_window_min, deadline_min=deadline,
            assigned_unit=unit, depart_min=depart, arrival_min=arrival))

    return CapacityTriageResult(
        n_rescue_units=n_units, rescue_service_time_min=service, window_min=window,
        dispatch_delay_min=delay, n_dispatch=len(dispatch),
        n_rescued_in_time=n_rescued, n_capacity_deferred=len(dispatch) - n_rescued,
        outcomes=outcomes)


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
    "load_walk_network",
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
    "RescueCapacityConfig",
    "TRIAGE_CLASSES",
    "TriageOutcome",
    "CapacityTriageResult",
    "capacity_triage",
]
