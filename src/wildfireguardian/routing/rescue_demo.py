"""End-to-end rescue-routing scenario + evaluation on the 영덕 extent.

This wires the reusable logic in :mod:`.rescue` into a runnable pipeline. Because
the real FIRMS bundle is git-ignored (absent in a fresh clone / this sandbox),
the scenario here is built from a **clearly-labelled synthetic fallback**:

- a coastal Yeongdeok-shaped extent (sea on the east, mountains inland west),
- a growing, severity-scaled probabilistic hazard envelope (no thin jet),
- synthetic refuges (coast assembly points) and synthetic responder depots
  (proxy 119안전센터), all tagged ``source = "synthetic"``,
- the existing walk network builder + a vehicle drive network.

Everything is deterministic (seeded, config-driven). The same
:func:`build_synthetic_demo` is used by the integration test, so the test
exercises the real end-to-end path. Swapping in real data is a matter of
pointing :class:`~.rescue.RescueConfig` at real shelter/depot files and an OSM
network, and feeding a real :class:`~.hazard.HazardSequence` from
``forward_simulate`` — the evaluation code below is unchanged.

Honesty: the four-way origin split always sums to N; the unreachable set is
reported, never imputed; contrasts (with vs without survival-awareness) are the
robust result, absolute magnitudes are illustrative (single-fire PoC + synthetic
inputs).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from pyproj import Transformer

from ..spread_v2 import grid as gridmod
from ..utils import regions
from .evacuation import build_evacuation_network, future_aware_route, naive_route
from .future_front import RoadNetwork
from .hazard import HazardSequence
from .rescue import (
    FOUR_WAY_CLASSES,
    Depot,
    Destination,
    DestinationAssessment,
    RescueConfig,
    assess_destinations,
    build_dispatch_list,
    build_drive_network,
    load_depots,
    load_drive_network,
    load_shelters,
    load_walk_network,
    rescuer_reachable,
    rescuer_route,
    resident_policies,
)

_TO_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)

#: Origin-scan stride for the REAL OSM walk graph. The OSM ``walk`` network for the
#: 영덕 extent is ~6x denser (≈8.4k nodes) than the synthetic route lattice (≈1.4k),
#: so the synthetic-default stride of 3 would sample ≈2.6k origins and make the
#: full-N verification sweeps intractable (~60 s per split × dozens of cells).
#: Raising the stride to 18 holds the sampled-candidate count near the synthetic
#: scale (≈439, vs the synthetic 452), keeping the two runs directly comparable.
#: The *procedure* is unchanged — this is only its stride knob, adapted to the
#: denser graph (recorded in the report / provenance).
REAL_OSM_SCAN_STRIDE: int = 18


# ---------------------------------------------------------------------------
# Scenario container
# ---------------------------------------------------------------------------


@dataclass
class RescueScenario:
    """Everything a rescue-routing run needs, on one (synthetic or real) extent."""

    cfg: RescueConfig
    route_grid: gridmod.CoarseGrid
    hazard_grid: gridmod.CoarseGrid
    elevation: np.ndarray
    burnable_frac: np.ndarray
    hazard: HazardSequence
    walk: RoadNetwork
    drive: RoadNetwork
    destinations: list[Destination]
    depots: list[Depot]
    origins: list[int]
    shelters_source: str
    depots_source: str
    hazard_source: str
    ignition_xy: tuple[float, float]
    walk_source: str = "synthetic"
    drive_source: str = "synthetic"
    terrain_source: str = "synthetic"
    origins_source: str = "sampled candidates"


# ---------------------------------------------------------------------------
# Synthetic-fallback layers (deterministic, tagged)
# ---------------------------------------------------------------------------


def _synthetic_terrain(grid: gridmod.CoarseGrid) -> tuple[np.ndarray, np.ndarray]:
    """Synthetic elevation + burnable for a coastal extent (sea on the EAST).

    Mirrors the repo's synthetic-DEM convention (rises east→west / coast→inland)
    so the geometry matches the real Yeongdeok layout: forested mountains inland
    (west, high) and the sea on the east. The easternmost strip is sea (burnable
    ≈ 0); everything else is burnable forest. Clearly synthetic.
    """
    nrows, ncols = grid.nrows, grid.ncols
    cols = np.arange(ncols)
    # West (col 0) high → east (last col) low; coast/sea at the far east.
    elev_profile = 900.0 * (1.0 - cols / max(ncols - 1, 1))
    elevation = np.tile(elev_profile, (nrows, 1)).astype(float)
    # Sea = the easternmost ~12% of columns.
    sea_from = int(round(ncols * 0.88))
    burnable = np.ones((nrows, ncols), dtype=float)
    burnable[:, sea_from:] = 0.0
    elevation[:, sea_from:] = 0.0
    return elevation, burnable


def _synthetic_hazard(
    grid: gridmod.CoarseGrid, burnable_frac: np.ndarray, ignition_xy: tuple[float, float],
    cfg: RescueConfig,
) -> HazardSequence:
    """A growing, severity-scaled probabilistic hazard envelope (no thin jet).

    P(ignited by t) at a cell is a smooth function of (reach radius at t − distance
    from ignition), clamped to [0, 1], made monotone non-decreasing in time, and
    masked to 0 over the sea. The reach grows with time (severity-scaled). This is
    the SYNTHETIC stand-in for ``forward_simulate``'s output and has the identical
    :class:`HazardSequence` shape, so the router consumes it unchanged.
    """
    X, Y = grid.center_grids()
    ix, iy = ignition_xy
    dist = np.hypot(X - ix, Y - iy)
    is_sea = burnable_frac <= 0.05
    times_min = np.array([0.0, 15.0, 30.0, 45.0, 60.0, 75.0, 90.0, 120.0, 150.0,
                          180.0, 240.0, 300.0, 420.0, 540.0, 600.0])
    # Reach radius grows broadly with time (severity-scaled, monotone). Linear
    # growth keeps the envelope a broad disc, not a thin directional jet.
    reach_m = cfg.syn_fire_base_reach_m + cfg.syn_fire_reach_rate_m_per_min * times_min
    width = cfg.syn_fire_edge_width_m
    surfaces: list[np.ndarray] = []
    prev = np.zeros_like(dist)
    for r in reach_m:
        s = 1.0 / (1.0 + np.exp((dist - r) / width))
        s = np.clip(s, 0.0, 1.0)
        s = np.maximum(s, prev)        # monotone non-decreasing in time
        s[is_sea] = 0.0                # no hazard over water
        surfaces.append(s.copy())
        prev = s
    return HazardSequence(grid=grid, times_min=times_min, surfaces=surfaces)


def synthetic_shelters(walk: RoadNetwork, n: int, *, seed: int) -> list[Destination]:
    """Synthetic refuges = coast assembly nodes spread along the shore.

    Reuses the walk network's coast-adjacent ``shelters`` (real land/sea geometry
    on a real extent; synthetic-on-synthetic here) and samples ``n`` of them evenly
    along the coast. Tagged ``synthetic``.
    """
    coast = sorted(walk.shelters)
    if not coast:
        return []
    coast_sorted = sorted(coast, key=lambda nid: walk.node_xy(nid)[1])  # by northing
    if n >= len(coast_sorted):
        chosen = coast_sorted
    else:
        idx = np.linspace(0, len(coast_sorted) - 1, n).round().astype(int)
        chosen = [coast_sorted[i] for i in idx]
    out: list[Destination] = []
    for k, nid in enumerate(chosen):
        x, y = walk.node_xy(nid)
        out.append(Destination(f"synthetic_refuge_{k}", x, y, kind="shelter",
                               source="synthetic"))
    return out


def synthetic_inland_shelters(
    walk: RoadNetwork, grid: gridmod.CoarseGrid, n: int, ignition_xy: tuple[float, float],
    *, seed: int, flank_radius_m: float = 6000.0,
) -> list[Destination]:
    """Synthetic inland open-space refuges on the fire's FLANK ring (proxy POIs).

    Placed on a ring around the ignition: far enough that the cell itself survives
    long enough for a slow walker (so the pedestrian router *can* reach them — they
    look "safe"), but close enough that the vehicle access road from a coastal depot
    is cut early. They are therefore the key *safe-but-not-rescue-reachable* case
    the rescue-reachable constraint must exclude — exactly what separates policy (c)
    from policy (b). Snapped to the nearest land node; tagged ``synthetic``.
    """
    ix, iy = ignition_xy
    out: list[Destination] = []
    seen: set[int] = set()
    # Bias the ring toward the INLAND/west semicircle (angles 90°–270°): these sit
    # on the far side of the fire from the eastern coastal depots, so their vehicle
    # corridor must cross the fire even while the refuge cell itself stays cool.
    for k in range(n):
        frac = k / max(n - 1, 1)
        ang = np.pi * 0.5 + np.pi * frac             # 90° → 270°, sweeping west
        r = flank_radius_m * (1.0 + 0.45 * (k % 2))  # two radii: nearer / farther
        tx, ty = ix + r * np.cos(ang), iy + r * np.sin(ang)
        nid = walk.nearest_node(tx, ty)
        if nid in seen:
            continue
        seen.add(nid)
        x, y = walk.node_xy(nid)
        out.append(Destination(f"synthetic_inland_refuge_{k}", x, y,
                               kind="open_space", source="synthetic"))
    return out


def synthetic_depots(drive: RoadNetwork, grid: gridmod.CoarseGrid, n: int) -> list[Depot]:
    """Synthetic responder depots near the coast/town (east), spread north→south."""
    # Candidate near-coast land nodes: those in the eastern third of the extent.
    east_x = grid.minx + 0.70 * (grid.maxx - grid.minx)
    cand = [nid for nid in drive.graph.nodes if drive.node_xy(nid)[0] >= east_x]
    if not cand:
        cand = list(drive.graph.nodes)
    cand.sort(key=lambda nid: drive.node_xy(nid)[1])  # by northing
    if n >= len(cand):
        chosen = cand
    else:
        idx = np.linspace(0, len(cand) - 1, n).round().astype(int)
        chosen = [cand[i] for i in idx]
    out: list[Depot] = []
    for k, nid in enumerate(chosen):
        x, y = drive.node_xy(nid)
        out.append(Depot(f"synthetic_depot_{k}", x, y, source="synthetic"))
    return out


# ---------------------------------------------------------------------------
# Scenario assembly
# ---------------------------------------------------------------------------


def build_synthetic_demo(cfg: RescueConfig | None = None) -> RescueScenario:
    """Build the full deterministic synthetic-fallback scenario on the 영덕 extent."""
    cfg = cfg or RescueConfig()
    region = regions.lookup(cfg.region_name)
    route_grid = gridmod.build_grid(region.bbox_wgs84, cell_size_m=cfg.route_cell_m)
    hazard_grid = gridmod.build_grid(region.bbox_wgs84, cell_size_m=cfg.hazard_cell_m)

    elevation, burnable = _synthetic_terrain(route_grid)
    # Hazard terrain mask: re-derive burnable on the hazard grid (finer).
    _, burnable_h = _synthetic_terrain(hazard_grid)

    # Ignition (config-driven fraction of the extent; inland-west, mid-latitude).
    fx, fy = cfg.syn_ignition_frac
    ix = route_grid.minx + fx * (route_grid.maxx - route_grid.minx)
    iy = route_grid.miny + fy * (route_grid.maxy - route_grid.miny)
    hazard = _synthetic_hazard(hazard_grid, burnable_h, (ix, iy), cfg)
    hazard_source = "synthetic"

    walk = build_evacuation_network(route_grid, elevation, burnable,
                                    flat_speed_ms=cfg.elderly_walk_speed_ms)
    drive = build_drive_network(route_grid, elevation, burnable,
                                vehicle_speed_kmh=cfg.vehicle_speed_kmh)

    # Destinations: real source if configured, else synthetic coast assembly nodes
    # plus inland open-space refuges (some of which the fire will overrun).
    dests, shelters_source = load_shelters(cfg, region.bbox_wgs84, to_5179=_TO_5179)
    if not dests:
        dests = synthetic_shelters(walk, cfg.n_synthetic_shelters, seed=cfg.seed)
        dests += synthetic_inland_shelters(
            walk, route_grid, cfg.n_synthetic_inland_shelters, (ix, iy),
            seed=cfg.seed, flank_radius_m=cfg.syn_inland_flank_radius_m)
        shelters_source = "synthetic"

    # Depots: real source if configured, else synthetic near-coast depots.
    depots, depots_source = load_depots(cfg, region.bbox_wgs84, to_5179=_TO_5179)
    if not depots:
        depots = synthetic_depots(drive, route_grid, cfg.n_synthetic_depots)
        depots_source = "synthetic"

    origins = _scan_origins(walk, hazard, route_grid, (ix, iy), cfg)

    return RescueScenario(
        cfg=cfg, route_grid=route_grid, hazard_grid=hazard_grid,
        elevation=elevation, burnable_frac=burnable, hazard=hazard,
        walk=walk, drive=drive, destinations=dests, depots=depots, origins=origins,
        shelters_source=shelters_source, depots_source=depots_source,
        hazard_source=hazard_source, ignition_xy=(ix, iy),
        walk_source="synthetic", drive_source="synthetic", terrain_source="synthetic",
        origins_source="sampled candidates",
    )


def build_real_demo(cfg: RescueConfig | None = None) -> RescueScenario:
    """Build the 영덕 scenario on REAL OpenStreetMap inputs (partial real flip).

    Real / OSM (``source="osm"``):
      - walk + drive road networks (OSMnx, reprojected EPSG:5179, disk-cached),
      - refuges (OSM ``amenity=shelter`` / ``community_centre`` / ``leisure=park``),
      - responder depots (OSM ``amenity=fire_station`` — the actual 소방서/119안전센터).

    Still SYNTHETIC (``source="synthetic"``), clearly labelled, pending the
    git-ignored FIRMS fire-data bundle:
      - the fire **hazard** surface (severity-scaled envelope stand-in for the
        spread_v2 forward-sim), and
      - the **terrain** / land–sea mask the hazard sea-clip and ignition use.

    Origins remain **sampled candidates** (real per-household elderly locations are
    private). If OSM is unavailable (no cache / no network) each real loader falls
    back to its labelled synthetic layer, so this still runs end-to-end — the
    provenance then reports exactly which inputs degraded, never silently.

    Data-source honesty: the road/refuge/depot GEOMETRY is now real; the fire that
    drives every survival / reachability number is still a synthetic envelope on a
    synthetic coastline. Contrasts remain the robust result; absolute magnitudes
    stay illustrative until the real hazard is flipped in.
    """
    from dataclasses import replace

    cfg = cfg or RescueConfig(use_osm=True)
    updates: dict = {}
    if not cfg.use_osm:
        updates["use_osm"] = True          # the real demo forces the OSM path on
    if cfg.scan_stride == RescueConfig.scan_stride:  # caller left the synthetic default
        updates["scan_stride"] = REAL_OSM_SCAN_STRIDE  # adapt to the denser OSM graph
    if updates:
        cfg = replace(cfg, **updates)
    region = regions.lookup(cfg.region_name)
    bbox = region.bbox_wgs84
    route_grid = gridmod.build_grid(bbox, cell_size_m=cfg.route_cell_m)
    hazard_grid = gridmod.build_grid(bbox, cell_size_m=cfg.hazard_cell_m)

    # Synthetic terrain (labelled) still drives the hazard sea-mask + is the
    # fallback for the network builders if OSM is unreachable. Terrain is NOT
    # real here — it waits on the DEM in the FIRMS bundle.
    elevation, burnable = _synthetic_terrain(route_grid)
    _, burnable_h = _synthetic_terrain(hazard_grid)

    # Synthetic hazard (labelled) on the real extent — same HazardSequence shape
    # the router consumes; swapped for forward_simulate output once FIRMS lands.
    fx, fy = cfg.syn_ignition_frac
    ix = route_grid.minx + fx * (route_grid.maxx - route_grid.minx)
    iy = route_grid.miny + fy * (route_grid.maxy - route_grid.miny)
    hazard = _synthetic_hazard(hazard_grid, burnable_h, (ix, iy), cfg)
    hazard_source = "synthetic"

    # Real OSM networks (fall back to labelled synthetic lattice if unreachable).
    walk, walk_source = load_walk_network(cfg, route_grid, elevation, burnable, bbox)
    drive, drive_source = load_drive_network(cfg, route_grid, elevation, burnable, bbox)

    # Real OSM refuges + depots (fall back to labelled synthetic if unreachable).
    dests, shelters_source = load_shelters(cfg, bbox, to_5179=_TO_5179)
    if not dests:
        dests = synthetic_shelters(walk, cfg.n_synthetic_shelters, seed=cfg.seed)
        dests += synthetic_inland_shelters(
            walk, route_grid, cfg.n_synthetic_inland_shelters, (ix, iy),
            seed=cfg.seed, flank_radius_m=cfg.syn_inland_flank_radius_m)
        shelters_source = "synthetic"

    depots, depots_source = load_depots(cfg, bbox, to_5179=_TO_5179)
    if not depots:
        depots = synthetic_depots(drive, route_grid, cfg.n_synthetic_depots)
        depots_source = "synthetic"

    origins = _scan_origins(walk, hazard, route_grid, (ix, iy), cfg)

    return RescueScenario(
        cfg=cfg, route_grid=route_grid, hazard_grid=hazard_grid,
        elevation=elevation, burnable_frac=burnable, hazard=hazard,
        walk=walk, drive=drive, destinations=dests, depots=depots, origins=origins,
        shelters_source=shelters_source, depots_source=depots_source,
        hazard_source=hazard_source, ignition_xy=(ix, iy),
        walk_source=walk_source, drive_source=drive_source, terrain_source="synthetic",
        origins_source="sampled candidates",
    )


def _scan_origins(walk, hazard, grid, ignition_xy, cfg) -> list[int]:
    """Candidate elderly-home origins: land nodes within the fire's reach band."""
    nodes = sorted(walk.graph.nodes)
    cand = [n for i, n in enumerate(nodes) if i % cfg.scan_stride == 0]
    iy = ignition_xy[1]
    out = []
    for n in cand:
        x, y = walk.node_xy(n)
        if hazard.prob_at(x, y, 0.0) >= cfg.walk_cutoff:
            continue                       # already burning at t0
        if abs(y - iy) > 0.45 * (grid.maxy - grid.miny):
            continue                       # keep roughly within the reach band
        out.append(n)
    return out


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


@dataclass
class RescueResults:
    """Headline outputs of one rescue-routing run."""

    n_origins: int
    four_way_counts: dict[str, int]
    dest_assessments: list[DestinationAssessment]
    n_refuges_rescue_reachable: int
    resident_exposure: dict[str, dict]          # policy -> {mean, n}
    dispatch: list                              # DispatchEntry list (homes needing rescue)
    unreachable_homes: list[dict]
    responder_exposure: dict                    # survival-aware vs shortest-path
    examples: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)


def _refuge_node_sets(scenario: RescueScenario, cfg: RescueConfig):
    """Snap destinations to BOTH nets; return (assessments, all_walk_nodes, rr_walk_nodes)."""
    assessments = assess_destinations(scenario.destinations, scenario.drive,
                                      [scenario.drive.nearest_node(d.x, d.y)
                                       for d in scenario.depots],
                                      scenario.hazard, cfg)
    all_walk: set[int] = set()
    rr_walk: set[int] = set()
    for d, a in zip(scenario.destinations, assessments):
        wnode = scenario.walk.nearest_node(d.x, d.y)
        all_walk.add(wnode)
        if a.rescue_reachable:
            rr_walk.add(wnode)
    return assessments, all_walk, rr_walk


def run_pipeline(scenario: RescueScenario, cfg: RescueConfig | None = None) -> RescueResults:
    """Run the full resident + rescuer evaluation and the honest four-way split.

    Immobile residents (config fraction) cannot self-evacuate on foot, so they are
    never ``already_safe``/``saved`` — they are forced onto the rescuer path and end
    up either dispatchable (``no_safe_pedestrian_route``) or, honestly,
    ``no_surviving_vehicle_ingress``. The four-way counts reconcile with the
    dispatch/unreachable split by construction (same rescuer-reachability test).
    """
    cfg = cfg or scenario.cfg
    depot_nodes = [scenario.drive.nearest_node(d.x, d.y) for d in scenario.depots]
    assessments, all_walk, rr_walk = _refuge_node_sets(scenario, cfg)
    n_rr = sum(1 for a in assessments if a.rescue_reachable)
    immobile = set(_immobile_homes(scenario, cfg))

    counts = {k: 0 for k in FOUR_WAY_CLASSES}
    expo = {p: [] for p in ("naive", "future_aware_any", "future_aware_rescue")}
    saved_examples: list = []
    n_c_differs = 0          # mobile origins where the rescue constraint changed refuge
    n_c_safer = 0            # ... and policy (b)'s refuge was NOT rescue-reachable
    paired_b: list[float] = []   # paired b/c exposure over origins where BOTH reached
    paired_c: list[float] = []
    needs_rescue: list[int] = []          # origin walk-nodes that cannot self-evacuate
    needs_rescue_immobile = 0
    for n in scenario.origins:
        if n in immobile:
            needs_rescue.append(n)
            needs_rescue_immobile += 1
            continue
        policies = resident_policies(scenario.walk, n, scenario.hazard,
                                     all_walk, rr_walk, cfg)
        naive, fa_rr = policies["naive"], policies["future_aware_rescue"]
        for p, r in policies.items():
            if r.reached:
                expo[p].append(r.exposure)
        b, c = policies["future_aware_any"], policies["future_aware_rescue"]
        if b.reached and c.reached:
            paired_b.append(b.exposure)
            paired_c.append(c.exposure)
            if b.target != c.target:
                n_c_differs += 1
                if b.target not in rr_walk:   # (b) would have sent them to a cut-off refuge
                    n_c_safer += 1
        if naive.reached and not naive.enters_hazard:
            counts["already_safe"] += 1
        elif fa_rr.reached and not fa_rr.enters_hazard:
            counts["saved_by_rescue_reachable_refuge"] += 1
            saved_examples.append((n, policies))
        else:
            needs_rescue.append(n)

    resident_exposure = {
        p: {"mean": (float(np.mean(v)) if v else None),
            "median": (float(np.median(v)) if v else None), "n": len(v)}
        for p, v in expo.items()
    }
    # Label the metric distinctly so it is never read against the responder scale.
    resident_exposure["units"] = "prob_min"
    resident_exposure["route_type"] = "pedestrian"
    resident_exposure["policy_c_changed_refuge_count"] = n_c_differs
    resident_exposure["policy_c_avoided_cutoff_refuge_count"] = n_c_safer
    # Honest PAIRED b-vs-c contrast (same origins, where both reached) — unlike the
    # unpaired per-policy means above, which are over different reached subsets.
    resident_exposure["paired_b_vs_c"] = {
        "mean_future_aware_any": (float(np.mean(paired_b)) if paired_b else None),
        "mean_future_aware_rescue": (float(np.mean(paired_c)) if paired_c else None),
        "n": len(paired_b),
    }

    # Rescuer side: dispatch everyone who cannot self-evacuate; the four-way
    # no-walk / no-ingress counts are exactly the dispatch / unreachable split.
    needs_rescue_drive = [scenario.drive.nearest_node(*scenario.walk.node_xy(n))
                          for n in needs_rescue]
    dispatch, unreachable = build_dispatch_list(
        needs_rescue_drive, scenario.drive, depot_nodes, scenario.depots,
        scenario.hazard, cfg)
    counts["no_safe_pedestrian_route"] = len(dispatch)
    counts["no_surviving_vehicle_ingress"] = len(unreachable)

    sa = [e.survival_aware_exposure for e in dispatch
          if np.isfinite(e.survival_aware_exposure)]
    sp = [e.shortest_path_exposure for e in dispatch
          if np.isfinite(e.shortest_path_exposure)]
    responder_exposure = {
        "survival_aware": {"mean": (float(np.mean(sa)) if sa else None), "n": len(sa)},
        "shortest_path": {"mean": (float(np.mean(sp)) if sp else None), "n": len(sp)},
        "shortest_path_enters_hazard_count":
            int(sum(1 for e in dispatch if e.shortest_path_enters_hazard)),
        "n_dispatch": len(dispatch),
        "n_unreachable": len(unreachable),
        "n_need_rescue": len(needs_rescue),
        "n_need_rescue_immobile": needs_rescue_immobile,
        "n_need_rescue_walk_cut": len(needs_rescue) - needs_rescue_immobile,
        "units": "prob_min",
        "route_type": "vehicle",
    }

    examples = _figure_examples(scenario, cfg, depot_nodes, all_walk, rr_walk,
                                dispatch, saved_examples)

    prov = cfg.provenance()
    prov["sources"] = {
        "walk_network": scenario.walk_source,
        "drive_network": scenario.drive_source,
        "shelters": scenario.shelters_source,
        "depots": scenario.depots_source,
        "hazard": scenario.hazard_source,
        "terrain": scenario.terrain_source,
        "origins": scenario.origins_source,
    }
    # Tag semantics: "osm" = OpenStreetMap (real-world geometry); "real" = an
    # authoritative government file (e.g. data.go.kr); "synthetic" = a labelled
    # stand-in; "assumed" = a literature/PoC constant (see provenance()["assumed"]).
    prov["source_legend"] = {
        "osm": "OpenStreetMap via OSMnx (real-world roads / POIs)",
        "real": "authoritative government dataset file (e.g. data.go.kr)",
        "synthetic": "labelled synthetic stand-in (not real data)",
        "assumed": "literature / PoC constant",
        "sampled candidates": "seeded candidate origins; real elderly-home "
        "locations are private",
    }
    partial_real = any(s in ("osm", "real")
                       for s in (scenario.walk_source, scenario.drive_source,
                                 scenario.shelters_source, scenario.depots_source))
    if partial_real and scenario.hazard_source == "synthetic":
        prov["honesty"] = (
            "PARTIAL REAL FLIP (영덕). Road networks / refuges / depots are REAL "
            "OpenStreetMap geometry (source='osm'); the fire HAZARD and the TERRAIN "
            "(land–sea mask) remain SYNTHETIC, pending the git-ignored FIRMS "
            "fire-data bundle that the spread_v2 forward-sim needs. Every survival / "
            "reachability number is therefore still driven by a synthetic fire on a "
            "synthetic coastline — contrasts are the robust result; absolute "
            "magnitudes stay illustrative until the real hazard is flipped in. "
            "'No safe route' / 'rescuer can't reach' are valid outputs, reported, "
            "never imputed."
        )
    else:
        prov["honesty"] = (
            "Single-fire (영덕) PoC on synthetic fallback inputs. Contrasts are the "
            "robust result; absolute magnitudes are illustrative. 'No safe route' / "
            "'rescuer can't reach' are valid outputs and are reported, never imputed."
        )

    return RescueResults(
        n_origins=len(scenario.origins), four_way_counts=counts,
        dest_assessments=assessments, n_refuges_rescue_reachable=n_rr,
        resident_exposure=resident_exposure, dispatch=dispatch,
        unreachable_homes=unreachable, responder_exposure=responder_exposure,
        examples=examples, provenance=prov,
    )


def _immobile_homes(scenario: RescueScenario, cfg: RescueConfig) -> list[int]:
    """Deterministically flag a fraction of origins as cannot-self-evacuate."""
    rng = np.random.default_rng(cfg.seed)
    origins = list(scenario.origins)
    if not origins:
        return []
    k = max(1, int(round(cfg.immobile_fraction * len(origins))))
    idx = rng.choice(len(origins), size=min(k, len(origins)), replace=False)
    return [origins[i] for i in sorted(idx)]


def _figure_examples(scenario, cfg, depot_nodes, all_walk, rr_walk, dispatch,
                     saved_examples) -> dict:
    """Collect one example responder route and one example resident route."""
    ex: dict = {}
    # Example responder route: the most-urgent reachable home.
    if dispatch:
        e = dispatch[0]
        depot_node = depot_nodes[e.depot_index]
        rr = rescuer_route(scenario.drive, depot_node, e.home_node, scenario.hazard, cfg)
        if rr.reached:
            ex["responder_route_xy"] = _route_xy(scenario.drive, rr.route)
            ex["responder_depot_xy"] = list(scenario.drive.node_xy(depot_node))
            ex["responder_home_xy"] = [e.x, e.y]
            ex["responder_exposure"] = rr.exposure
    # Example resident route: a saved origin's naive vs rescue-reachable route.
    if saved_examples:
        n, policies = saved_examples[len(saved_examples) // 2]
        nv = policies["naive"]
        fc = policies["future_aware_rescue"]
        ex["resident_origin_xy"] = list(scenario.walk.node_xy(n))
        if nv.route:
            ex["resident_naive_xy"] = _route_xy(scenario.walk, nv.route)
            ex["resident_naive_exposure"] = nv.exposure
        if fc.route:
            ex["resident_rescue_xy"] = _route_xy(scenario.walk, fc.route)
            ex["resident_rescue_exposure"] = fc.exposure
    return ex


def _route_xy(net: RoadNetwork, route: list[int]) -> list[list[float]]:
    return [list(net.node_xy(n)) for n in route]


# ---------------------------------------------------------------------------
# Sensitivity sweep — robustness of the reachable/unreachable split
# ---------------------------------------------------------------------------


def _split_counts(scenario: RescueScenario, cfg: RescueConfig) -> dict:
    """Lighter four-way split for the sweep (prunes already-safe origins early).

    Matches :func:`run_pipeline`'s logic: immobile residents are forced onto the
    rescuer path; mobile residents safe under naive routing are short-circuited.
    Only the rescue-reachable refuge set and rescuer reachability depend on the
    swept (vehicle-side) parameters, so this stays cheap.
    """
    depot_nodes = [scenario.drive.nearest_node(d.x, d.y) for d in scenario.depots]
    assessments, all_walk, rr_walk = _refuge_node_sets(scenario, cfg)
    immobile = set(_immobile_homes(scenario, cfg))
    counts = {k: 0 for k in FOUR_WAY_CLASSES}
    for n in scenario.origins:
        x, y = scenario.walk.node_xy(n)
        if n not in immobile:
            nv = naive_route(_view(scenario.walk, all_walk), n, scenario.hazard,
                             p_cut=cfg.walk_cutoff)
            if nv.reached and not nv.enters_hazard:
                counts["already_safe"] += 1
                continue
            fa_rr = None
            if rr_walk:
                fa_rr = future_aware_route(
                    _view(scenario.walk, rr_walk), n, scenario.hazard,
                    time_budget_min=cfg.resident_time_budget_min, p_cut=cfg.walk_cutoff,
                    time_step_min=cfg.time_step_min)
            if fa_rr is not None and fa_rr.reached and not fa_rr.enters_hazard:
                counts["saved_by_rescue_reachable_refuge"] += 1
                continue
        reachable, _rt, _di = rescuer_reachable(
            scenario.drive, depot_nodes, scenario.drive.nearest_node(x, y),
            scenario.hazard, cfg)
        if reachable:
            counts["no_safe_pedestrian_route"] += 1
        else:
            counts["no_surviving_vehicle_ingress"] += 1
    return {
        "counts": counts,
        "n_origins": len(scenario.origins),
        "n_refuges_rescue_reachable": sum(1 for a in assessments if a.rescue_reachable),
        "n_refuges": len(assessments),
    }


def _view(net: RoadNetwork, shelters: set[int]) -> RoadNetwork:
    return RoadNetwork(graph=net.graph, shelters=set(shelters))


def sensitivity_sweep(scenario: RescueScenario, base_cfg: RescueConfig | None = None) -> dict:
    """Vary vehicle cutoff, responder ETA (via vehicle speed), and time budget.

    Reports how the four-way reachable/unreachable split moves. This robustness —
    not any single absolute split — is the real result (single-fire PoC).
    """
    from dataclasses import replace

    base_cfg = base_cfg or scenario.cfg
    # The sweep is a trend analysis; cap the origin set so it stays fast at full res.
    sw_scen = scenario
    if len(scenario.origins) > base_cfg.sweep_max_origins:
        stride = int(np.ceil(len(scenario.origins) / base_cfg.sweep_max_origins))
        sw_scen = replace(scenario, origins=scenario.origins[::stride])

    sweeps: dict = {"baseline": _split_counts(sw_scen, base_cfg)}
    sweeps["vehicle_cutoff"] = {
        f"{v:.2f}": _split_counts(sw_scen, replace(base_cfg, vehicle_cutoff=v))
        for v in (0.4, 0.5, 0.6, 0.7, 0.8)
    }
    sweeps["vehicle_speed_kmh"] = {  # proxy for responder ETA / depot proximity
        f"{v:.0f}": _split_counts(sw_scen, replace(base_cfg, vehicle_speed_kmh=v))
        for v in (20.0, 30.0, 40.0, 60.0)
    }
    sweeps["responder_dispatch_delay_min"] = {  # detection + mobilisation lag
        f"{d:.0f}": _split_counts(sw_scen, replace(base_cfg, responder_dispatch_delay_min=d))
        for d in (0.0, 15.0, 30.0, 45.0, 60.0)
    }
    sweeps["responder_time_budget_min"] = {
        f"{b:.0f}": _split_counts(sw_scen, replace(base_cfg, responder_time_budget_min=b))
        for b in (45.0, 60.0, 75.0, 90.0)
    }
    return sweeps


__all__ = [
    "RescueScenario",
    "RescueResults",
    "build_synthetic_demo",
    "build_real_demo",
    "synthetic_shelters",
    "synthetic_depots",
    "run_pipeline",
    "sensitivity_sweep",
]
