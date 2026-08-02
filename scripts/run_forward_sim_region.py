#!/usr/bin/env python
"""Forward-simulate a region's hazard field, with the boundary guard on.

Round-3 PHASE 5 STEP 2-1. NO NEW ACQUISITION — every input (FIRMS detections,
SRTM DEM, WorldCover fuel, ERA5 weather) is already present for all eight fires.

WHAT IT DOES
------------
For each target fire:
  1. builds the spread_v2 feature dataset over ALL fires (once, shared),
  2. fits the model on every fire EXCEPT the target, so the target's hazard is
     genuinely out-of-sample — the same leave-one-out discipline as the
     Yeongdeok run,
  3. forward-simulates on a grid built from the fire's own manifest bbox,
  4. RUNS THE BOUNDARY GUARD. A fire that reaches the edge of its canvas
     under-reports area, breadth and drift, so this raises rather than
     truncating (docs/grid_extent.md). Uiseong-Andong burned 45,000 ha — twelve
     times Yeongdeok — so hitting the edge is a live possibility, not a
     formality.
  5. writes the hazard field as an npz with the same schema the routing scripts
     already consume, plus a JSON summary carrying the envelope geometry.

⚠ THE SIMULATION GRID IS THE FIRE'S OWN MANIFEST BBOX.
Yeongdeok's committed field used the (larger) fire-ACQUISITION bbox instead
(docs/grid_extent.md), so its grid is 181x147 while these are built from
fire_manifest.json. Envelope AREA is a physical quantity and is comparable as
long as nothing is clipped — which is exactly what the boundary guard checks.

Run:  python scripts/run_forward_sim_region.py --fires uiseong_andong_2025 uljin_samcheok_2022
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from pyproj import Transformer  # noqa: E402

from wildfireguardian.config import config_hash, get as _cfg  # noqa: E402
from wildfireguardian.routing.hazard import HazardSequence  # noqa: E402
from wildfireguardian.spread_v2 import data, features, grid as gridmod  # noqa: E402
from wildfireguardian.spread_v2.extent import (  # noqa: E402
    GridBoundaryError, assert_envelope_within_grid, boundary_contact,
)
from wildfireguardian.spread_v2.features import StaticLayers  # noqa: E402
from wildfireguardian.spread_v2.forward_sim import (  # noqa: E402
    envelope_breadth_deg, forward_simulate,
)
from wildfireguardian.spread_v2.model import IgnitionModelV2  # noqa: E402
from wildfireguardian.spread_v2.weather import weather_series_from_event  # noqa: E402

_TO_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
_TO_WGS = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
OUT_DIR = REPO / "data" / "processed"


def _git() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def envelope_extent(surface: np.ndarray, g, p: float):
    """Bounding box of cells at/above ``p``, in EPSG:5179. None if empty."""
    rr, cc = np.where(surface >= p)
    if not len(rr):
        return None
    c = g.cell_size_m
    return {
        "minx": float(g.minx + cc.min() * c),
        "miny": float(g.maxy - (rr.max() + 1) * c),
        "maxx": float(g.minx + (cc.max() + 1) * c),
        "maxy": float(g.maxy - rr.min() * c),
        "n_cells": int(len(rr)),
    }


def to_wgs(e: dict) -> list[float]:
    lo1, la1 = _TO_WGS.transform(e["minx"], e["miny"])
    lo2, la2 = _TO_WGS.transform(e["maxx"], e["maxy"])
    return [round(lo1, 4), round(la1, 4), round(lo2, 4), round(la2, 4)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fires", nargs="+",
                    default=["uiseong_andong_2025", "uljin_samcheok_2022"])
    ap.add_argument("--cell-m", type=float,
                    default=_cfg("grid.routing_integration_hazard_cell_m", 500.0))
    ap.add_argument("--n-steps", type=int, default=_cfg("time.forward_sim_n_steps", 4))
    ap.add_argument("--step-hours", type=float,
                    default=_cfg("time.forward_sim_step_hours", 3.0))
    ap.add_argument("--advance-threshold", type=float,
                    default=_cfg("time.forward_sim_advance_threshold", 0.3))
    ap.add_argument("--p-cut", type=float, default=_cfg("pedestrian.walk_cutoff_p", 0.5))
    ap.add_argument("--seed", type=int, default=_cfg("seeds.canonical", 20250603))
    ap.add_argument("--walk-margin-km", type=float, default=5.0,
                    help="margin added around the envelope to derive the walk bbox")
    args = ap.parse_args()

    if not data.data_available():
        print("STOP: FIRMS bundle absent", file=sys.stderr)
        return 2

    manifest = json.loads((REPO / "data/raw/firms_data/fire_manifest.json")
                          .read_text(encoding="utf-8"))
    by_id = {f["id"]: f for f in manifest["fires"]}

    print("[1/2] building the shared feature dataset over all fires ...")
    fire_ids = [m.id for m in data.list_fires()]
    ds = features.build_dataset(fire_ids, cell_size_m=args.cell_m,
                                buffer_m=_cfg("grid.feature_buffer_m", 6000.0))
    usable = sorted(ds["fire_id"].unique())
    print(f"      {len(ds):,} rows over {len(usable)} usable fires: {usable}")

    results = []
    for fid in args.fires:
        print(f"\n[2/2] {fid} ...")
        if fid not in usable:
            print(f"      SKIP: {fid} not in the usable set", file=sys.stderr)
            continue
        meta = by_id[fid]
        bbox = tuple(meta["bbox"])
        g = gridmod.build_grid(bbox, cell_size_m=args.cell_m)
        print(f"      manifest bbox {bbox} -> grid {g.nrows}x{g.ncols} @ "
              f"{args.cell_m:g} m ({g.ncols*args.cell_m/1000:.0f} x "
              f"{g.nrows*args.cell_m/1000:.0f} km)")

        model = IgnitionModelV2(seed=args.seed).fit(ds[ds["fire_id"] != fid])
        ev = data.load_event(fid)
        ws = weather_series_from_event(ev)
        snaps = gridmod.overpass_snapshots(ev, g, gap_minutes=90.0)
        static = StaticLayers.from_event(ev, g)
        sim = forward_simulate(model, ev, g, static, snaps[0].cumulative_mask,
                               snaps[0].time, ws, n_steps=args.n_steps,
                               step_hours=args.step_hours,
                               advance_threshold=args.advance_threshold)
        hazard = HazardSequence.from_forward_sim(sim)

        # --- the boundary guard -------------------------------------------
        reports = [dict(boundary_contact(s), slice=i)
                   for i, s in enumerate(hazard.surfaces)]
        touched = [r for r in reports if r["reached"]]
        max_edge = max(max(r["max_p_per_edge"].values()) for r in reports)
        status = "CLEAR" if not touched else "REACHED BOUNDARY"
        print(f"      boundary: {status}  (max edge p = {max_edge:.4f})")
        clipped = bool(touched)
        if clipped:
            print(f"      ⚠ slices touching the edge: "
                  f"{[(r['slice'], r['edges_reached']) for r in touched]}")
            try:
                assert_envelope_within_grid(hazard.surfaces, grid=g, context=fid)
            except GridBoundaryError as exc:
                print(f"      {str(exc).splitlines()[0]}")

        areas = [sim.envelope_area_ha(s, args.p_cut) for s in range(sim.n_steps)]
        core = [int((hazard.surfaces[i] >= 0.5).sum())
                for i in range(len(hazard.surfaces))]
        core3 = [int((hazard.surfaces[i] >= 0.3).sum())
                 for i in range(len(hazard.surfaces))]
        ign_xy = np.array(_TO_5179.transform(*meta["ignition"]), float)
        breadth = [envelope_breadth_deg(sim, s, tuple(ign_xy), p_cut=0.3)
                   for s in range(sim.n_steps)]
        print(f"      envelope_area_ha {areas}")
        print(f"      cells >=0.5      {core}")

        # --- derived walk bbox: envelope + margin --------------------------
        env = envelope_extent(hazard.surfaces[-1], g, args.p_cut)
        walk = None
        if env:
            m = args.walk_margin_km * 1000.0
            walk = {"minx": env["minx"] - m, "miny": env["miny"] - m,
                    "maxx": env["maxx"] + m, "maxy": env["maxy"] + m}
            walk["width_km"] = (walk["maxx"] - walk["minx"]) / 1000
            walk["height_km"] = (walk["maxy"] - walk["miny"]) / 1000
            walk["area_km2"] = walk["width_km"] * walk["height_km"]
            walk["wgs84_wsen"] = to_wgs(walk)
            walk["clearance_to_sim_grid_km"] = {
                "west": (walk["minx"] - g.minx) / 1000,
                "south": (walk["miny"] - g.miny) / 1000,
                "east": (g.maxx - walk["maxx"]) / 1000,
                "north": (g.maxy - walk["maxy"]) / 1000,
            }
            walk["fits_inside_sim_grid"] = all(
                v >= 0 for v in walk["clearance_to_sim_grid_km"].values())
            print(f"      derived walk bbox {walk['wgs84_wsen']}  "
                  f"{walk['width_km']:.1f} x {walk['height_km']:.1f} km "
                  f"= {walk['area_km2']:.0f} km2   "
                  f"fits={walk['fits_inside_sim_grid']}")

        npz = OUT_DIR / f"hazard_{fid}.npz"
        np.savez_compressed(
            npz,
            grid_extent=np.array([g.minx, g.miny, g.maxx, g.maxy, g.cell_size_m], float),
            haz_times=np.asarray(hazard.times_min, float),
            haz_stack=np.array(hazard.surfaces, dtype=np.float32),
            ignition_xy=ign_xy)
        sha = hashlib.sha256(npz.read_bytes()).hexdigest()

        results.append({
            "fire_id": fid,
            "reported_ha": meta.get("reported_ha"),
            "n_detections": meta.get("n_detections"),
            "simulation_bbox_wgs84": list(bbox),
            "simulation_bbox_source": "data/raw/firms_data/fire_manifest.json",
            "grid": {"nrows": g.nrows, "ncols": g.ncols, "cell_size_m": g.cell_size_m,
                     "extent_5179": [g.minx, g.miny, g.maxx, g.maxy],
                     "width_km": g.ncols * g.cell_size_m / 1000,
                     "height_km": g.nrows * g.cell_size_m / 1000},
            "boundary_check": {"clear": not clipped, "max_edge_p": max_edge,
                               "per_slice": reports},
            "envelope_area_ha": areas,
            "cells_ge_0.5": core, "cells_ge_0.3": core3,
            "envelope_breadth_deg": breadth,
            "envelope_extent_5179_p_cut": env,
            "envelope_extent_wgs84_p_cut": to_wgs(env) if env else None,
            "derived_walk_bbox": walk,
            "walk_margin_km": args.walk_margin_km,
            "hazard_npz": str(npz.relative_to(REPO)),
            "hazard_npz_sha256": sha,
            "start_time": str(sim.start_time),
        })

    doc = {
        "schema_version": 1,
        "title": "Per-region forward simulation for the multi-region routing extension",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _git(), "config_hash": config_hash(),
        "no_new_acquisition": True,
        "parameters": {"cell_m": args.cell_m, "n_steps": args.n_steps,
                       "step_hours": args.step_hours,
                       "advance_threshold": args.advance_threshold,
                       "p_cut": args.p_cut, "seed": args.seed,
                       "training": "leave-the-target-fire-out"},
        "grid_note": ("The simulation grid is each fire's own fire_manifest.json "
                      "bbox. Yeongdeok's committed field instead used the larger "
                      "fire-ACQUISITION bbox (docs/grid_extent.md), so its grid is "
                      "181x147. Envelope AREA is physical and comparable provided "
                      "nothing is clipped — which the boundary guard checks."),
        "regions": results,
    }
    out = OUT_DIR / "forward_sim_regions.json"
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False, default=str) + "\n",
                   encoding="utf-8")
    print(f"\nwrote {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
