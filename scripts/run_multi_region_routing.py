#!/usr/bin/env python
"""The 459-series routing run, region by region.

Round-3 PHASE 5 STEP 2-3.

WHAT THIS IS
------------
`scripts/run_real_roads_real_hazard_slope.py` runs the 459-series scan for
Yeongdeok. This runs the SAME scan, with the SAME parameters, for the two
regions acquired in STEP 2-2, so the three can be put in one table.

Every parameter comes from `config/default.yaml` and is NOT varied per region:
60 m slope sampling (canonical), distance-ranked routing, 600-minute budget,
10-minute time step, stride 18, p_cut 0.5, clip |slope| at 60 %. The point of
the exercise is that only the REGION changes.

WHAT IS DELIBERATELY NOT RUN
----------------------------
**Yeongdeok.** Its committed values are quoted, never re-derived here: its
2026-07-23 walk graph is unrecoverable (docs/DATA_LOSS_2026-07-24.md), and
re-running would silently substitute a different network behind the same
number. `--regions` therefore refuses `yeongdeok_2025`, and the run aborts with
exit 4 if any protected Yeongdeok artifact changes byte-for-byte while it works.

INPUTS COME FROM THE SNAPSHOT STORE, NOT THE CACHE
--------------------------------------------------
`data/cache/**` is git-ignored and may be regenerated underneath a run — that is
exactly how the July graph died. The walk graph, the refuge POIs and the depot
POIs are all read from `data/snapshots/`, resolved through `MANIFEST.json`. The
snapshot bytes are identical to the cache bytes by construction, so this changes
no result; it changes what the result is anchored to.

THREE ARMS PER REGION
---------------------
    flat / undirected     the control: what the run gives with no terrain
    flat / DiGraph        regression — with flat timing, direction carries no
                          information, so this MUST equal the control
    slope 60 m / DiGraph  CANONICAL — the row that goes in the comparison

The flat arm is not decoration. Uljin-Samcheok's DEM does not reach the southern
edge of its own walk bbox, so part of its "slope" arm is silently a flat arm
(see `dem_footprint` in the output). Reporting the flat control beside it is how
that is kept visible instead of implied.

Run:  python scripts/run_multi_region_routing.py
      python scripts/run_multi_region_routing.py --regions uiseong_andong_2025
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import warnings
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from wildfireguardian.config import config_hash, get as _cfg  # noqa: E402
from wildfireguardian.routing.evacuation import future_aware_route, naive_route  # noqa: E402
from wildfireguardian.routing.hazard import HazardSequence  # noqa: E402
from wildfireguardian.routing.rescue import Destination  # noqa: E402
from wildfireguardian.routing.slope import (  # noqa: E402
    build_walk_network, load_snapshot_graph, slowest_edges,
)
from wildfireguardian.spread_v2.extent import (  # noqa: E402
    boundary_contact, check_envelope_coverage, check_routing_clearance,
)
from wildfireguardian.spread_v2.grid import CoarseGrid  # noqa: E402
from pyproj import Transformer  # noqa: E402

_TO_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
_TO_4326 = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)

SNAPSHOTS = REPO / "data" / "snapshots"
MANIFEST = SNAPSHOTS / "MANIFEST.json"

#: Regions this script may run. Yeongdeok is absent BY DESIGN — see the module
#: docstring and docs/HANDOFF_ROUND3.md §5.4.
RUNNABLE_REGIONS = ("uiseong_andong_2025", "uljin_samcheok_2022")

#: Committed artifacts that must be byte-identical before and after. Changing
#: any of them would invalidate figures the submission already cites.
PROTECTED = (
    "data/processed/real_roads_real_hazard.json",
    "data/processed/real_roads_real_hazard_slope_60.json",
    "data/processed/routing_demo.npz",
    "data/processed/rescue_routing.json",
)

#: Matches rescue_demo.REAL_OSM_SCAN_STRIDE and every committed 459-series run.
REAL_OSM_SCAN_STRIDE = int(_cfg("origin_scan.real_osm_stride", 18))

#: The five original buckets plus the additive sixth, plus the residue.
CATEGORIES = ("naive_into_FA_safe", "no_safe_route", "both_safe", "both_enter",
              "naive_unreachable", "fa_exceeds_budget", "unclassified")


# ---------------------------------------------------------------------------
# Provenance helpers
# ---------------------------------------------------------------------------


def _git() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return None


def _sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def protected_digests() -> dict[str, str | None]:
    return {rel: _sha256(REPO / rel) for rel in PROTECTED}


def snapshot_for(region: str, layer: str) -> Path:
    """Resolve one snapshot file for ``region`` from MANIFEST.json.

    ``layer`` is the manifest's ``source`` suffix: ``walk``, ``shelters``,
    ``depots``. Raises rather than guessing a filename — a wrong graph read
    silently is the failure mode this whole store exists to prevent.
    """
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    want_src, want_region = f"osm-{layer}", region.replace("_", "-")
    hits = [s for s in man["snapshots"]
            if s.get("source") == want_src and s.get("region") == want_region
            and s.get("stored_file")]
    if len(hits) != 1:
        raise FileNotFoundError(
            f"expected exactly 1 snapshot for source={want_src!r} "
            f"region={want_region!r}; found {len(hits)}. Run "
            "`python scripts/snapshot_external.py --preset osm` first.")
    p = SNAPSHOTS / hits[0]["stored_file"]
    if not p.exists():
        raise FileNotFoundError(f"manifest lists {p.name} but it is not on disk")
    return p


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


def load_hazard(region: str):
    npz = REPO / f"data/processed/hazard_{region}.npz"
    if not npz.exists():
        raise FileNotFoundError(
            f"{npz.relative_to(REPO)} missing — run STEP 2-1 "
            "(scripts/run_forward_sim_region.py) first")
    z = np.load(npz)
    haz = z["haz_stack"].astype(np.float32)
    times = np.asarray(z["haz_times"], float)
    xmin, ymin, xmax, ymax, cell = [float(v) for v in z["grid_extent"]]
    grid = CoarseGrid(minx=xmin, miny=ymin, maxx=xmax, maxy=ymax,
                      cell_size_m=cell, nrows=haz.shape[1], ncols=haz.shape[2])
    hazard = HazardSequence(grid=grid, times_min=times,
                            surfaces=[haz[i] for i in range(haz.shape[0])])
    return hazard, haz, grid, (xmin, ymin, xmax, ymax, cell), _sha256(npz), npz


def read_poi_snapshot(path: Path, *, kind: str) -> tuple[list[Destination], int]:
    """Read a snapshotted POI GeoJSON exactly as ``rescue._osm_points`` would.

    An EMPTY FeatureCollection is a legitimate answer, not a failure: it is what
    `amenity=fire_station` returns inside Uiseong-Andong's walk bbox. It is
    returned as zero features so the caller can record "not applicable" rather
    than infer "zero dispatches".
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    n_features = len(raw.get("features", []))
    if n_features == 0:
        return [], 0

    import geopandas as gpd

    gdf = gpd.read_file(path)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    gdf = gdf.to_crs("EPSG:5179")
    out: list[Destination] = []
    for i, row in gdf.iterrows():
        g = row.geometry
        if g is None or g.is_empty:
            continue
        name = str(row.get("name") or f"{kind}_{i}")
        out.append(Destination(name, float(g.x), float(g.y), kind=kind, source="osm"))
    return out, n_features


# ---------------------------------------------------------------------------
# The origin rule and the classification — LIFTED, not re-derived
# ---------------------------------------------------------------------------


def candidate_origins(net, hazard, haz, extent, p_cut):
    """The committed run's origin rule, unchanged: stride, p_cut, reach band.

    Identical to ``run_real_roads_real_hazard_slope.candidate_origins``. It is
    duplicated rather than imported so that a later edit to the Yeongdeok script
    cannot silently redefine what the multi-region rows mean; the two are pinned
    against each other in tests/test_multi_region_routing.py.
    """
    xmin, ymin, xmax, ymax, cell = extent
    core = haz[0] >= 0.5
    rr, cc = np.where(core)
    ign_y = float(ymax - (rr.mean() + 0.5) * cell)
    ign_x = float(xmin + (cc.mean() + 0.5) * cell)
    band = 0.45 * (ymax - ymin)
    nodes_sorted = sorted(net.graph.nodes)
    cand = []
    for i, n in enumerate(nodes_sorted):
        if i % REAL_OSM_SCAN_STRIDE:
            continue
        x, y = net.node_xy(n)
        if hazard.prob_at(x, y, 0.0) >= p_cut:
            continue
        if abs(y - ign_y) > band:
            continue
        cand.append(n)
    return cand, (ign_x, ign_y), band


def classify(net, cand, hazard, p_cut, budget, step, objective="length_m"):
    """The 7-way PARTITION from run_real_roads_real_hazard_slope.classify."""
    classes: dict[str, list[int]] = {k: [] for k in CATEGORIES}
    for n in cand:
        nv = naive_route(net, n, hazard, departure_min=0.0, p_cut=p_cut,
                         objective=objective)
        fa = future_aware_route(net, n, hazard, departure_min=0.0,
                                time_budget_min=budget, p_cut=p_cut,
                                time_step_min=step)
        if not nv.reached:
            classes["naive_unreachable"].append(n)
        elif nv.enters_hazard and fa.reached and not fa.enters_hazard:
            classes["naive_into_FA_safe"].append(n)
        elif nv.enters_hazard and not fa.reached:
            classes["no_safe_route"].append(n)
        elif not nv.enters_hazard and fa.reached and not fa.enters_hazard:
            classes["both_safe"].append(n)
        elif nv.enters_hazard and fa.enters_hazard:
            classes["both_enter"].append(n)
        elif not nv.enters_hazard and not fa.reached:
            classes["fa_exceeds_budget"].append(n)
        else:
            classes["unclassified"].append(n)
    counts = {k: len(v) for k, v in classes.items()}
    assert sum(counts.values()) == len(cand), "classification must partition"
    return counts, classes


# ---------------------------------------------------------------------------
# Pre-flight checks — every one recorded, whether it passes or not
# ---------------------------------------------------------------------------


def preflight(region, G, hazard, haz, grid, extent, walk_bbox_wgs84, dem_path,
              p_cut) -> dict:
    xmin, ymin, xmax, ymax, _cell = extent

    xs, ys = [], []
    for lon, lat in ((walk_bbox_wgs84[0], walk_bbox_wgs84[1]),
                     (walk_bbox_wgs84[0], walk_bbox_wgs84[3]),
                     (walk_bbox_wgs84[2], walk_bbox_wgs84[1]),
                     (walk_bbox_wgs84[2], walk_bbox_wgs84[3])):
        x, y = _TO_5179.transform(lon, lat)
        xs.append(x); ys.append(y)
    routing_bbox = (min(xs), min(ys), max(xs), max(ys))

    # -- 1. does the walk bbox cover the predicted fire core? -----------------
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        cov_final = check_envelope_coverage(routing_bbox, haz[-1], grid, p_cut=p_cut)
        cov_t0 = check_envelope_coverage(routing_bbox, haz[0], grid, p_cut=p_cut)
        cov_warned = [str(w.message)[:200] for w in caught]

    # -- 2. did the fire touch the edge of its own canvas? --------------------
    edge = [dict(boundary_contact(haz[i]), slice=i) for i in range(haz.shape[0])]

    # -- 3. is the routing extent comfortably inside the hazard grid? ---------
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        clearance = check_routing_clearance(routing_bbox, grid)
        clearance_warned = [str(w.message)[:200] for w in caught]

    # -- 4. are the walk nodes actually inside the hazard grid? ---------------
    #    Nodes outside read p=0 — no hazard, no extrapolation — i.e. optimistic.
    gx = np.array([d["x"] for _, d in G.nodes(data=True)], float)
    gy = np.array([d["y"] for _, d in G.nodes(data=True)], float)
    projected = str(G.graph.get("crs", "")).lower() == "epsg:5179"
    if not projected:                       # Yeongdeok's snapshot is EPSG:4326
        gx, gy = _TO_5179.transform(gx, gy)
    inside = (gx >= xmin) & (gx <= xmax) & (gy >= ymin) & (gy <= ymax)
    n_outside = int((~inside).sum())

    # -- 5. does the DEM footprint cover the walk network? -------------------
    #    A node outside the DEM reads nodata, and slope.build_walk_network then
    #    times its edges as FLAT. Silent unless counted.
    import rasterio

    lon, lat = _TO_4326.transform(gx, gy)
    with rasterio.open(dem_path) as src:
        b = src.bounds
        dem_bounds = [float(b.left), float(b.bottom), float(b.right), float(b.top)]
        dem_crs = str(src.crs)
    in_dem = ((lon >= b.left) & (lon <= b.right)
              & (lat >= b.bottom) & (lat <= b.top))
    n_no_dem = int((~in_dem).sum())

    return {
        "routing_bbox_5179": [float(v) for v in routing_bbox],
        "walk_bbox_wgs84_wsen": list(walk_bbox_wgs84),
        "envelope_coverage": {
            "final_slice": cov_final, "t0_slice": cov_t0,
            "warnings": cov_warned,
            "definition": "share of grid cells at p >= p_cut that fall inside "
                          "the walk bbox, by CELL COUNT (not bbox overlap)",
        },
        "boundary_contact": {
            "per_slice": edge,
            "any_slice_reached_edge": any(e["reached"] for e in edge),
            "max_edge_p": max(max(e["max_p_per_edge"].values()) for e in edge),
        },
        "routing_clearance": dict(clearance, warnings=clearance_warned),
        "walk_nodes_vs_hazard_grid": {
            "n_nodes": int(len(gx)),
            "n_outside_hazard_extent": n_outside,
            "frac_outside": n_outside / max(len(gx), 1),
            "graph_crs_as_stored": str(G.graph.get("crs", "")),
            "note": "nodes outside the hazard grid read p=0 — no extrapolation, "
                    "but also no hazard, which is OPTIMISTIC",
        },
        "dem_footprint": {
            "dem_path": str(Path(dem_path).relative_to(REPO)),
            "dem_crs": dem_crs, "dem_bounds_wsen": dem_bounds,
            "n_nodes_outside_dem": n_no_dem,
            "frac_nodes_outside_dem": n_no_dem / max(len(gx), 1),
            "node_lat_range": [float(lat.min()), float(lat.max())],
            "note": "a walk node outside the DEM footprint reads nodata, and the "
                    "slope build then times its edges as FLAT. Where this count "
                    "is non-zero the 'slope' arm is partly a flat arm, and the "
                    "flat control arm in this same file is the honest bound.",
        },
    }


# ---------------------------------------------------------------------------
# One region
# ---------------------------------------------------------------------------


def run_region(region: str, args) -> dict:
    print(f"\n{'=' * 70}\n=== {region}\n{'=' * 70}")
    t_region = time.monotonic()

    walk_bbox = (_cfg("bbox.multi_region_walk_bbox", {}) or {}).get(region)
    if walk_bbox is None:
        raise KeyError(f"no walk bbox in config for {region}")
    dem = REPO / f"data/raw/firms_data/{region}_dem.tif"
    if not dem.exists():
        raise FileNotFoundError(f"DEM missing: {dem.relative_to(REPO)}")

    hazard, haz, grid, extent, npz_sha, npz_path = load_hazard(region)
    print(f"hazard: {haz.shape} sha256 {npz_sha[:16]}...")

    snap_walk = snapshot_for(region, "walk")
    G = load_snapshot_graph(snap_walk)
    print(f"snapshot walk graph: {snap_walk.name}\n"
          f"  {G.number_of_nodes():,} nodes, {G.number_of_edges():,} directed edges")

    print("[1/5] pre-flight ...")
    pf = preflight(region, G, hazard, haz, grid, extent, walk_bbox, dem, args.p_cut)
    cov = pf["envelope_coverage"]["final_slice"]
    print(f"  envelope coverage (final slice): {cov['n_covered']}/{cov['n_core_cells']}"
          f" = {(cov['coverage'] or 0) * 100:.1f}%  (min {cov['min_fraction']:.0%})")
    print(f"  boundary contact: "
          f"{'REACHED' if pf['boundary_contact']['any_slice_reached_edge'] else 'clear'}"
          f"  (max edge p {pf['boundary_contact']['max_edge_p']:.3f})")
    print(f"  grid clearance km: {pf['routing_clearance']['margins_km']}")
    print(f"  walk nodes outside hazard grid: "
          f"{pf['walk_nodes_vs_hazard_grid']['n_outside_hazard_extent']}")
    nd = pf["dem_footprint"]["n_nodes_outside_dem"]
    print(f"  walk nodes outside DEM footprint: {nd}"
          + (f"  ⚠ {nd / pf['walk_nodes_vs_hazard_grid']['n_nodes'] * 100:.2f}% "
             "will be timed FLAT" if nd else ""))

    # -- refuges (GATE A) -----------------------------------------------------
    print("[2/5] refuges + depots from the snapshot store ...")
    snap_shelters = snapshot_for(region, "shelters")
    dests, n_shelter_features = read_poi_snapshot(snap_shelters, kind="shelter")
    snap_depots = snapshot_for(region, "depots")
    depots, n_depot_features = read_poi_snapshot(snap_depots, kind="depot")
    print(f"  shelters: {n_shelter_features} POIs from {snap_shelters.name}")
    print(f"  depots  : {n_depot_features} POIs from {snap_depots.name}")
    if not dests:
        raise RuntimeError(
            "GATE A: zero refuges — every origin would be unreachable and the "
            "run would be meaningless. Not writing output.")

    responder_available = n_depot_features > 0

    # -- arms -----------------------------------------------------------------
    def run_arm(label, net, stats):
        net.shelters = {net.nearest_node(d.x, d.y) for d in dests}
        cand, ign, band = candidate_origins(net, hazard, haz, extent, args.p_cut)
        if args.limit_origins:
            cand = cand[:args.limit_origins]
        t0 = time.monotonic()
        counts, classes = classify(net, cand, hazard, args.p_cut,
                                   args.time_budget_min, args.time_step_min)
        n = max(len(cand), 1)
        print(f"  {label:26s} N={len(cand):4d}  both_safe={counts['both_safe']:4d}  "
              f"FA_only={counts['naive_into_FA_safe']:3d}  "
              f"no_safe={counts['no_safe_route']:3d}  "
              f"unreach={counts['naive_unreachable']:3d}  "
              f"[{time.monotonic() - t0:.0f}s]")
        return {
            "label": label,
            "n_origins_scanned": len(cand),
            "counts": counts,
            "future_aware_only_safe_fraction": counts["naive_into_FA_safe"] / n,
            "n_shelter_nodes": len(net.shelters),
            "shelter_source": "osm (snapshot store)",
            "n_nodes": net.graph.number_of_nodes(),
            "n_edges": net.graph.number_of_edges(),
            "ignition_proxy_xy_5179": [ign[0], ign[1]],
            "reach_band_m": band,
            "reach_band_binds": bool(
                band < max(abs(pf["routing_bbox_5179"][1] - ign[1]),
                           abs(pf["routing_bbox_5179"][3] - ign[1]))),
            "slope_stats": stats.as_dict() if stats is not None else None,
            "origin_nodes_by_bucket": {
                k: [int(v) for v in classes[k]]
                for k in ("naive_into_FA_safe", "no_safe_route", "both_enter",
                          "naive_unreachable", "fa_exceeds_budget", "unclassified")
            },
        }

    print("[3/5] flat arms (control + DiGraph regression) ...")
    net_u, _ = build_walk_network(G, None, apply_slope=False, directed=False)
    net_d, _ = build_walk_network(G, None, apply_slope=False, directed=True)
    arm_flat = run_arm("flat / undirected", net_u, None)
    arm_flat_di = run_arm("flat / DiGraph (regr.)", net_d, None)
    identical = (arm_flat["counts"] == arm_flat_di["counts"]
                 and arm_flat["n_origins_scanned"] == arm_flat_di["n_origins_scanned"])
    print(f"  -> DiGraph regression: "
          f"{'PASS (identical)' if identical else 'FAIL — DIVERGES'}")
    if not identical:
        raise RuntimeError(
            "the DiGraph conversion changed a flat-timing result; slope must not "
            "be applied until that is resolved")

    print(f"[4/5] slope arm ({args.sampling_m:g} m, clip {args.max_abs_slope:g}) ...")
    net_s, st = build_walk_network(G, dem, sampling_m=args.sampling_m,
                                   max_abs_slope=args.max_abs_slope,
                                   directed=True, apply_slope=True)
    arm_slope = run_arm(f"slope {args.sampling_m:g}m / DiGraph", net_s, st)
    arm_slope["top_slowed_edges"] = slowest_edges(st, net_s, k=10)

    slope_changes_counts = arm_slope["counts"] != arm_flat["counts"]
    print(f"  -> slope changes the bucket counts: {slope_changes_counts}")

    # -- which scanned origins sit in the DEM hole? --------------------------
    dem_hole_origins = None
    if pf["dem_footprint"]["n_nodes_outside_dem"]:
        import rasterio

        with rasterio.open(dem) as src:
            b = src.bounds
        by_bucket: dict[str, int] = {}
        n_hole = 0
        # Rebuild the origin list once on the canonical (slope) network.
        cand, _ign, _band = candidate_origins(net_s, hazard, haz, extent, args.p_cut)
        if args.limit_origins:
            cand = cand[:args.limit_origins]
        holes = set()
        for n in cand:
            x, y = net_s.node_xy(n)
            lo, la = _TO_4326.transform(x, y)
            if not (b.left <= lo <= b.right and b.bottom <= la <= b.top):
                holes.add(n)
                n_hole += 1
        for k, members in arm_slope["origin_nodes_by_bucket"].items():
            by_bucket[k] = sum(1 for m in members if m in holes)
        by_bucket["both_safe"] = n_hole - sum(by_bucket.values())
        dem_hole_origins = {
            "n_scanned_origins_outside_dem": n_hole,
            "frac_of_scanned_origins": n_hole / max(arm_slope["n_origins_scanned"], 1),
            "by_bucket": by_bucket,
            "note": "these origins were routed on FLAT-timed edges inside a run "
                    "labelled 'slope'. Their bucket membership is listed so the "
                    "effect on the headline can be bounded rather than assumed.",
        }
        print(f"  -> scanned origins inside the DEM hole: {n_hole} "
              f"({by_bucket})")

    print("[5/5] assembling ...")
    n = max(arm_slope["n_origins_scanned"], 1)
    doc = {
        "title": f"Real roads + real hazard + real terrain ({region}, "
                 f"{args.sampling_m:g} m slope sampling)",
        "schema_version": 1,
        "series": "459",
        "series_note": (
            "459-SERIES, THREE BUCKETS. The reported cross-region quantity is "
            "`future_aware_only_safe_fraction` = naive_into_FA_safe / "
            "n_origins_scanned — the share of origins that reach safety ONLY on "
            "the future-aware route. It is NOT the walk-failure rate w: w belongs "
            "to the 439 series, which is bound to a synthetic hazard envelope and "
            "cannot be carried inland."),
        "region": region,
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _git(),
        "config_hash": config_hash(),
        "runtime_s": round(time.monotonic() - t_region, 1),
        "parameters": {
            "identical_to_yeongdeok": True,
            "slope_sampling_m": args.sampling_m,
            "is_canonical_sampling": abs(
                args.sampling_m - float(_cfg("pedestrian.slope_sampling_m", 60.0))) < 1e-9,
            "max_abs_slope": args.max_abs_slope,
            "routing_objective": "length_m (distance-ranked)",
            "p_cut": args.p_cut,
            "time_budget_min": args.time_budget_min,
            "time_step_min": args.time_step_min,
            "origin_scan_stride": REAL_OSM_SCAN_STRIDE,
            "osmnx_pin": "2.0.7",
            "source": "config/default.yaml — NOT varied per region",
        },
        "headline": {
            "n_origins_scanned": arm_slope["n_origins_scanned"],
            "both_safe": arm_slope["counts"]["both_safe"],
            "future_aware_only_safe": arm_slope["counts"]["naive_into_FA_safe"],
            "no_safe_route": arm_slope["counts"]["no_safe_route"],
            "future_aware_only_safe_fraction": arm_slope["counts"]["naive_into_FA_safe"] / n,
            "arm": "slope 60 m / DiGraph (canonical)",
        },
        "arms": {
            "flat_undirected_control": arm_flat,
            "flat_digraph_regression": arm_flat_di,
            "slope_digraph_canonical": arm_slope,
        },
        "digraph_regression": {
            "identical": identical,
            "why": "with flat timing, direction carries no information, so the "
                   "DiGraph conversion MUST leave results unchanged",
        },
        "slope_effect": {
            "counts_changed_vs_flat": slope_changes_counts,
            "flat_counts": arm_flat["counts"],
            "slope_counts": arm_slope["counts"],
            "why_it_can_be_nil": "naive_route ranks by DISTANCE, so its path is "
                                 "slope-invariant by construction; at a 600-minute "
                                 "budget the future-aware router is not time-bound "
                                 "either. Yeongdeok showed the same null result "
                                 "(docs/slope_integration.md).",
        },
        "preflight": pf,
        "dem_hole_origins": dem_hole_origins,
        "responder_side": {
            "responder_side_available": responder_available,
            "n_depot_pois": n_depot_features,
            "computed": False,
            "status": ("NOT APPLICABLE — no amenity=fire_station is mapped in OSM "
                       "inside this region's ignition-centred walk bbox"
                       if not responder_available else
                       "AVAILABLE but NOT COMPUTED in this run"),
            "note": ("The 459 series is RESIDENT-SIDE ONLY for every region, "
                     "Yeongdeok included: it contrasts a fire-blind walking route "
                     "with a future-aware one and never dispatches a vehicle. "
                     "Where responder_side_available is false the responder side "
                     "additionally COULD NOT be computed even if the series called "
                     "for it, because build_dispatch_list would have no depot to "
                     "dispatch from. Record that as 'not applicable'. It is NEVER "
                     "zero dispatches."),
            "depot_phrasing_rule": (
                "발화점 중심 walk bbox 범위 내에 OSM에 매핑된 fire_station이 "
                "없다는 뜻이며, 해당 지역에 소방서가 없다는 뜻이 아닙니다. "
                "Uiseong-Andong's wider 3,926 km² manifest bbox contains six "
                "(data/processed/osm_completeness.json). NEVER write "
                "'Uiseong-Andong has no fire stations.'"),
        },
        "network_source": {
            "kind": "REAL — OpenStreetMap, read from the SNAPSHOT store",
            "snapshot_walk": snap_walk.name,
            "snapshot_shelters": snap_shelters.name,
            "snapshot_depots": snap_depots.name,
            "read_from_cache": False,
            "why_snapshot": "data/cache/** is git-ignored and may be regenerated "
                            "underneath a run; the snapshot store is the evidence "
                            "layer. The bytes are identical by construction.",
            "bbox_wgs84": list(walk_bbox),
            "n_refuge_pois": n_shelter_features,
        },
        "hazard_source": {
            "kind": "REAL — spread_v2 forward-simulated ignition probability",
            "npz_path": str(npz_path.relative_to(REPO)),
            "npz_sha256": npz_sha,
            "shape": list(haz.shape),
            "times_min": hazard.times_min.tolist(),
            "grid_extent_5179": list(extent),
            "cells_ge_0.5_per_slice": [int((haz[i] >= 0.5).sum())
                                       for i in range(haz.shape[0])],
            "core_growth_pct_first_to_last": (
                (int((haz[-1] >= 0.5).sum()) / max(int((haz[0] >= 0.5).sum()), 1) - 1.0)
                * 100.0),
        },
        "terrain_source": {
            "kind": "REAL — SRTM",
            "dem_path": str(dem.relative_to(REPO)),
            "sampling_m": args.sampling_m,
            "max_abs_slope": args.max_abs_slope,
            "tobler": "wildfireguardian.routing.evacuation.elderly_speed_ms "
                      "(REUSED, identical to Yeongdeok)",
        },
        "provenance": {
            "roads_real": True, "hazard_real": True, "terrain_real": True,
            "yeongdeok_rerun": False,
            "statement": "OSM road topology, the spread_v2 forward-simulated "
                         "hazard for this region's fire, and SRTM terrain slope "
                         "on the walk edges — all three real simultaneously.",
            "still_synthetic_or_assumed": [
                f"elderly walk speed {_cfg('pedestrian.elderly_flat_speed_ms', 0.7)} m/s "
                "(literature/assumed)",
                "elderly-home origins (stride-sampled walk nodes; real "
                "per-household data is private)",
                "slope clipping is a defence against DEM registration error, "
                "NOT a physical correction",
            ],
        },
    }
    if args.limit_origins:
        doc["SMOKE_TEST"] = {
            "origin_limit_applied": args.limit_origins,
            "warning": "TRUNCATED ORIGIN LIST — not a reportable result",
        }
    return doc


# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--regions", nargs="+", default=list(RUNNABLE_REGIONS))
    ap.add_argument("--sampling-m", type=float,
                    default=float(_cfg("pedestrian.slope_sampling_m", 60.0)))
    ap.add_argument("--max-abs-slope", type=float,
                    default=float(_cfg("pedestrian.max_abs_slope", 0.60)))
    ap.add_argument("--p-cut", type=float,
                    default=float(_cfg("pedestrian.walk_cutoff_p", 0.5)))
    ap.add_argument("--time-budget-min", type=float,
                    default=float(_cfg("pedestrian.walk_budget_min", 600.0)))
    ap.add_argument("--time-step-min", type=float,
                    default=float(_cfg("time.routing_time_step_min", 10.0)))
    ap.add_argument("--limit-origins", type=int, default=0,
                    help="SMOKE TEST ONLY: truncate the origin list. Output is "
                         "written under a _SMOKE_ prefix and is not reportable.")
    ap.add_argument("--out-dir", default=str(REPO / "data" / "processed"))
    args = ap.parse_args()

    bad = [r for r in args.regions if r not in RUNNABLE_REGIONS]
    if bad:
        print(f"STOP: {bad} is not runnable here. Yeongdeok's committed values are "
              "QUOTED, never re-derived: its 2026-07-23 network is unrecoverable "
              "(docs/DATA_LOSS_2026-07-24.md).", file=sys.stderr)
        return 2

    before = protected_digests()
    missing = [k for k, v in before.items() if v is None]
    if missing:
        print(f"STOP: protected artifact(s) missing, cannot guard them: {missing}",
              file=sys.stderr)
        return 2
    print("protected artifacts (sha256 recorded before the run):")
    for k, v in before.items():
        print(f"  {v[:16]}...  {k}")

    out_dir = Path(args.out_dir)
    written, failed = [], []
    for region in args.regions:
        try:
            doc = run_region(region, args)
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED {region}: {type(exc).__name__}: {exc}", file=sys.stderr)
            failed.append((region, f"{type(exc).__name__}: {exc}"))
            continue
        prefix = "_SMOKE_" if args.limit_origins else ""
        out = out_dir / f"{prefix}real_roads_real_hazard_{region}.json"
        out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
        written.append(out)
        print(f"  wrote {out.relative_to(REPO) if out.is_relative_to(REPO) else out}")

    # -- the guard, checked LAST and unconditionally --------------------------
    after = protected_digests()
    changed = [k for k in before if before[k] != after[k]]
    if changed:
        print("\nSTOP (exit 4): a PROTECTED artifact changed during this run:",
              file=sys.stderr)
        for k in changed:
            print(f"  {k}\n    before {before[k]}\n    after  {after[k]}",
                  file=sys.stderr)
        return 4
    print(f"\nprotected artifacts unchanged ({len(before)} verified byte-for-byte)")

    if failed:
        print(f"\nSTOP: {len(failed)} region(s) failed.", file=sys.stderr)
        for r, e in failed:
            print(f"  {r}: {e}", file=sys.stderr)
        return 3
    print(f"done — {len(written)} file(s) written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
