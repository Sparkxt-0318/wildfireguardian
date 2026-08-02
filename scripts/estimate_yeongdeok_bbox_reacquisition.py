#!/usr/bin/env python
"""What would re-drawing Yeongdeok's walk bbox around the canonical fire cost?

Round-3 step 4. **ESTIMATION ONLY — this script acquires nothing.** It performs
no network I/O, and it is written so that it cannot: nothing here imports osmnx
or touches `data/cache/`.

THE PROBLEM
-----------
Yeongdeok's walk bbox covers **32.6 %** of its own canonical predicted fire core
(1,036 cells at p >= 0.5, final slice). It covered 50.4 % of the reverted run's
smaller core. The bbox did not move; the fire quadrupled.

WHAT IS ESTIMATED
-----------------
A walk bbox that would actually contain the canonical core, and what acquiring
it would imply for node count, origin count, grid clearance and download size.

⚠ THE EXTRAPOLATION IS THE WEAK PART, AND IT IS BIASED HIGH. Node and road
densities are taken from the CURRENT bbox, which is coastal and contains
Yeongdeok town. The extension runs 25 km WEST into the Taebaek range, where
settlement and road density are lower. So the projected counts are an UPPER
BOUND; the true figures would be smaller by an unmeasured amount.

Writes ``data/processed/yeongdeok_bbox_reacquisition_estimate.json``.

Run:  python scripts/estimate_yeongdeok_bbox_reacquisition.py
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from wildfireguardian.config import config_hash, get as _cfg  # noqa: E402
from pyproj import Transformer  # noqa: E402

_TO_4326 = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
_TO_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)

CANON_NPZ = REPO / "data/processed/routing_demo_canonical.npz"
COMPLETENESS = REPO / "data/processed/osm_completeness.json"
CANON_ROUTING = REPO / "data/processed/real_roads_real_hazard_canonical.json"


def _git() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def bbox_area_km2(W, S, E, N) -> float:
    xs, ys = [], []
    for lon, lat in ((W, S), (W, N), (E, S), (E, N)):
        x, y = _TO_5179.transform(lon, lat)
        xs.append(x); ys.append(y)
    return (max(xs) - min(xs)) * (max(ys) - min(ys)) / 1e6


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--margin-km", type=float, default=5.0,
                    help="clearance added around the core, matching the "
                         "walk_margin_km used for the two acquired regions")
    ap.add_argument("--out", default=str(
        REPO / "data/processed/yeongdeok_bbox_reacquisition_estimate.json"))
    args = ap.parse_args()

    # ---- the canonical core -------------------------------------------------
    z = np.load(CANON_NPZ)
    h = z["haz_stack"].astype(np.float32)
    xmin, ymin, xmax, ymax, cell = [float(v) for v in z["grid_extent"]]
    final = h[-1]
    rr, cc = np.where(final >= 0.5)
    core = {
        "n_cells": int(len(rr)),
        "extent_5179": [xmin + cc.min() * cell, ymax - (rr.max() + 1) * cell,
                        xmin + (cc.max() + 1) * cell, ymax - rr.min() * cell],
    }
    cx0, cy0, cx1, cy1 = core["extent_5179"]
    core["width_km"] = (cx1 - cx0) / 1000.0
    core["height_km"] = (cy1 - cy0) / 1000.0

    m = args.margin_km * 1000.0
    prop_5179 = (cx0 - m, cy0 - m, cx1 + m, cy1 + m)
    lo0, la0 = _TO_4326.transform(prop_5179[0], prop_5179[1])
    lo1, la1 = _TO_4326.transform(prop_5179[2], prop_5179[3])
    prop_wgs = (round(lo0, 3), round(la0, 3), round(lo1, 3), round(la1, 3))
    prop_area = bbox_area_km2(*prop_wgs)

    # ---- the current bbox, as the density basis -----------------------------
    comp = {r["region"]: r for r in json.loads(COMPLETENESS.read_text())["regions"]}
    y = comp["yeongdeok_2025"]
    cur_area = y["bbox_area_km2"]
    node_density = y["node_density_per_km2"]
    road_density = y["road_density_km_per_km2"]
    edges_per_km2 = y["walk_edges_directed"] / cur_area
    shelters_per_km2 = y["shelter_pois"] / cur_area

    routing = json.loads(CANON_ROUTING.read_text())
    cur_origins = routing["arms"]["slope_digraph_canonical"]["n_origins_scanned"]
    stride = int(_cfg("origin_scan.real_osm_stride", 18))
    retention = cur_origins / (y["walk_nodes"] / stride)

    scale = prop_area / cur_area
    est = {
        "area_km2": round(prop_area, 1),
        "area_multiple_of_current": round(scale, 2),
        "walk_nodes": int(round(prop_area * node_density)),
        "walk_edges_directed": int(round(prop_area * edges_per_km2)),
        "walk_length_km": round(prop_area * road_density, 1),
        "shelter_pois": int(round(prop_area * shelters_per_km2)),
        "origins_at_stride_18": int(round(prop_area * node_density / stride * retention)),
        "graphml_mb": round(12.06 * scale, 1),
        "basis": {
            "node_density_per_km2": node_density,
            "road_density_km_per_km2": road_density,
            "edges_directed_per_km2": round(edges_per_km2, 2),
            "origin_retention_vs_stride": round(retention, 4),
            "current_walk_graphml_mb": 12.06,
        },
    }

    # ---- does it still sit inside the simulation grid? ----------------------
    clearance = {
        "west_km": round((prop_5179[0] - xmin) / 1000.0, 2),
        "south_km": round((prop_5179[1] - ymin) / 1000.0, 2),
        "east_km": round((xmax - prop_5179[2]) / 1000.0, 2),
        "north_km": round((ymax - prop_5179[3]) / 1000.0, 2),
    }
    need = float(_cfg("grid.boundary_check.routing_clearance_km", 5.0))
    tight = sorted(k for k, v in clearance.items() if v < need)

    acq = json.loads((REPO / "data/processed/osm_acquisition.json").read_text())
    secs = []
    for a in acq["acquisitions"]:
        w = a.get("layers", {}).get("walk.graphml", {})
        if w.get("seconds"):
            secs.append((a["region"], w["seconds"], w["n_nodes"]))

    doc = {
        "schema_version": 1,
        "title": "ESTIMATE ONLY — re-drawing Yeongdeok's walk bbox around the "
                 "canonical fire core",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _git(), "config_hash": config_hash(),
        "nothing_was_acquired": (
            "This script performs no network I/O and imports no OSM client. It "
            "reads committed artifacts and extrapolates. No bbox was changed and "
            "no graph was fetched."),
        "canonical_core": core,
        "current_bbox": {
            "wgs84_wsen": y["walk_bbox_wgs84_wsen"], "area_km2": cur_area,
            "walk_nodes": y["walk_nodes"],
            "walk_edges_directed": y["walk_edges_directed"],
            "walk_length_km": y["walk_length_km"],
            "shelter_pois": y["shelter_pois"],
            "origins_at_stride_18": cur_origins,
            "envelope_coverage_final_slice": routing["preflight"]
                ["envelope_coverage"]["final_slice"]["coverage"],
        },
        "proposed_bbox": {
            "rule": f"canonical p>=0.5 final-slice core, plus {args.margin_km:g} km "
                    "on every side — the same walk_margin_km the two acquired "
                    "regions used",
            "wgs84_wsen": list(prop_wgs),
            "extent_5179": [round(v) for v in prop_5179],
            "width_km": round((prop_5179[2] - prop_5179[0]) / 1000.0, 1),
            "height_km": round((prop_5179[3] - prop_5179[1]) / 1000.0, 1),
            "would_cover_core": True,
        },
        "extrapolated_from_current_density": est,
        "extrapolation_caveat": (
            "⚠ BIASED HIGH. Densities come from the CURRENT bbox, which is "
            "coastal and contains Yeongdeok town. The proposal extends ~25 km "
            "WEST into the Taebaek range, where settlement and road density are "
            "lower. Treat every projected count as an upper bound. The error is "
            "unmeasured — measuring it would require the acquisition this "
            "estimate exists to avoid."),
        "simulation_grid_clearance": {
            "grid_extent_5179": [xmin, ymin, xmax, ymax],
            "grid_note": "the CANONICAL grid, already extended 0.05 deg west",
            "margins_km": clearance,
            "required_km": need,
            "sides_below_requirement": tight,
            "fits_with_required_clearance": not tight,
        },
        "acquisition_scale_reference": {
            "measured_walk_graph_fetches": [
                {"region": r, "seconds": s, "n_nodes": n} for r, s, n in secs],
            "note": "Overpass fetch times for the two 2026-08-02 acquisitions, at "
                    "919-924 km2. A bbox of "
                    f"{prop_area:.0f} km2 is {scale:.1f}x that area; Overpass cost "
                    "scales with extracted features, not linearly with area, so "
                    "treat this as an order-of-magnitude reference only.",
        },
    }
    Path(args.out).write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")

    print("ESTIMATE ONLY — nothing acquired\n")
    print(f"canonical core: {core['n_cells']} cells, "
          f"{core['width_km']:.1f} x {core['height_km']:.1f} km")
    print(f"current  bbox : {y['walk_bbox_wgs84_wsen']}  {cur_area:.0f} km2  "
          f"{y['walk_nodes']:,} nodes  {cur_origins} origins  "
          f"coverage {doc['current_bbox']['envelope_coverage_final_slice']:.1%}")
    print(f"proposed bbox : {list(prop_wgs)}  {prop_area:.0f} km2  "
          f"({scale:.2f}x)")
    print(f"  projected: {est['walk_nodes']:,} nodes, "
          f"{est['walk_edges_directed']:,} directed edges, "
          f"{est['walk_length_km']:,.0f} km road")
    print(f"  projected: {est['origins_at_stride_18']} origins at stride 18, "
          f"{est['shelter_pois']} refuge POIs, ~{est['graphml_mb']:.0f} MB graphml")
    print(f"  grid clearance km: {clearance}  "
          f"{'OK' if not tight else 'TIGHT on ' + '/'.join(tight)}")
    print(f"\nwrote {Path(args.out).relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
