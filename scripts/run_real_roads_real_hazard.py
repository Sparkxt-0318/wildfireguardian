#!/usr/bin/env python
"""Evacuation routing on REAL OSM roads AND the REAL spread_v2 forward-sim hazard.

This is the third cell of the project's real/synthetic axis: the 407-origin
`run_routing_integration` run had a REAL hazard on a SYNTHETIC road lattice; the
~439-origin `run_rescue_routing` run had REAL OSM roads on a SYNTHETIC hazard.
Here BOTH are real, closing the stated limitation that road topology and the
fire-risk surface were never simultaneously real.

Purely additive: writes only data/processed/real_roads_real_hazard.json. Touches
no existing committed artifact. If OSMnx cannot reach the network it STOPS and
reports rather than falling back to a synthetic lattice.

Method matches the repo:
  - roads/refuges: wildfireguardian.routing.rescue OSM loaders (source='osm'),
  - hazard: HazardSequence built directly from data/processed/routing_demo.npz,
  - routing: evacuation.naive_route / future_aware_route (unchanged),
  - classification: the 6-bucket PARTITION from scripts/run_routing_integration.py,
  - knobs: p_cut=0.5, time_budget=600 min (comparable to the 407 run).

Run:  python scripts/run_real_roads_real_hazard.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from wildfireguardian.config import config_hash, get as _cfg  # noqa: E402
from wildfireguardian.spread_v2.grid import CoarseGrid  # noqa: E402
from wildfireguardian.routing.hazard import HazardSequence  # noqa: E402
from wildfireguardian.routing.rescue import (  # noqa: E402
    RescueConfig, _osm_walk_network, load_shelters,
)
from wildfireguardian.routing.evacuation import naive_route, future_aware_route  # noqa: E402
from wildfireguardian.utils import regions  # noqa: E402
from pyproj import Transformer  # noqa: E402

_TO_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
KNOWN_ORIGIN = (1153094.95, 1832745.46)   # a known routing origin, for the hazard sanity check
# Sourced from config/default.yaml (PHASE 1-A); literal fallback = Round-2 value.
REAL_OSM_SCAN_STRIDE = int(_cfg("origin_scan.real_osm_stride", 18))  # == rescue_demo's stride


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--npz", default=str(REPO / _cfg("paths.hazard_npz",
                                                     "data/processed/routing_demo.npz")))
    ap.add_argument("--p-cut", type=float, default=_cfg("pedestrian.walk_cutoff_p", 0.5))
    ap.add_argument("--time-budget-min", type=float,
                    default=_cfg("pedestrian.walk_budget_min", 600.0))
    ap.add_argument("--time-step-min", type=float,
                    default=_cfg("time.routing_time_step_min", 10.0))
    ap.add_argument("--osm-cache-dir",
                    default=str(REPO / _cfg("paths.osm_cache_dir", "data/cache/osm")))
    ap.add_argument("--out", default=str(REPO / "data" / "processed" / "real_roads_real_hazard.json"))
    args = ap.parse_args()

    npz_path = Path(args.npz)
    if not npz_path.exists():
        print(f"STOP: hazard npz not found at {npz_path} (git-ignored bulk; needs the "
              f"routing_demo run present in the working tree).", file=sys.stderr)
        return 2

    # ---- REAL hazard -------------------------------------------------------
    npz_sha = hashlib.sha256(npz_path.read_bytes()).hexdigest()
    z = np.load(npz_path)
    haz_stack = z["haz_stack"].astype(np.float32)
    haz_times = np.asarray(z["haz_times"], float)
    xmin, ymin, xmax, ymax, cell = [float(v) for v in z["grid_extent"]]
    nrows, ncols = haz_stack.shape[1], haz_stack.shape[2]
    grid = CoarseGrid(minx=xmin, miny=ymin, maxx=xmax, maxy=ymax,
                      cell_size_m=cell, nrows=nrows, ncols=ncols)
    hazard = HazardSequence(grid=grid, times_min=haz_times,
                            surfaces=[haz_stack[i] for i in range(haz_stack.shape[0])])
    p_known = hazard.prob_at(KNOWN_ORIGIN[0], KNOWN_ORIGIN[1], 0.0)
    assert np.isfinite(p_known) and 0.0 <= p_known <= 1.0, "hazard sample invalid"

    # ---- REAL OSM walk network (STOP on network failure) -------------------
    cfg = RescueConfig(use_osm=True, osm_cache_dir=args.osm_cache_dir)
    bbox = regions.lookup(cfg.region_name).bbox_wgs84
    print("[1/4] downloading REAL OSM walk graph (OSMnx -> EPSG:5179) ...")
    try:
        walk = _osm_walk_network(cfg, bbox)
    except Exception as exc:  # noqa: BLE001
        print(f"STOP: OSMnx could not build the walk network ({type(exc).__name__}: {exc}). "
              f"Not falling back to a synthetic lattice.", file=sys.stderr)
        return 3
    xs = np.array([walk.graph.nodes[n]["x"] for n in walk.graph.nodes], float)
    ys = np.array([walk.graph.nodes[n]["y"] for n in walk.graph.nodes], float)
    inside = (xs >= xmin) & (xs <= xmax) & (ys >= ymin) & (ys <= ymax)
    n_outside = int((~inside).sum())
    if n_outside > 0:
        print(f"      note: {n_outside} OSM nodes outside hazard extent -> hazard clips them "
              f"to 0 (no extrapolation).")

    # ---- REAL OSM refuges -> shelter nodes (GATE A) ------------------------
    print("[2/4] loading REAL OSM refuges + snapping to walk nodes ...")
    dests, shelters_source = load_shelters(cfg, bbox, to_5179=_TO_5179)
    shelter_nodes = {walk.nearest_node(d.x, d.y) for d in dests}
    walk.shelters = shelter_nodes
    if len(shelter_nodes) == 0:
        print("STOP (GATE A): zero shelters — every origin would be unreachable and the run "
              "would be meaningless. Not writing output.", file=sys.stderr)
        return 4
    print(f"      shelters: {len(shelter_nodes)} nodes from {len(dests)} OSM POIs "
          f"(source={shelters_source})")

    # ---- candidate origins: same stride/reach/cutoff rule ------------------
    core = haz_stack[0] >= 0.5
    rr, cc = np.where(core)
    ign_x = float(xmin + (cc.mean() + 0.5) * cell)
    ign_y = float(ymax - (rr.mean() + 0.5) * cell)
    band = 0.45 * (ymax - ymin)
    nodes_sorted = sorted(walk.graph.nodes)
    cand0 = [n for i, n in enumerate(nodes_sorted) if i % REAL_OSM_SCAN_STRIDE == 0]
    cand = []
    for n in cand0:
        x, y = walk.node_xy(n)
        if hazard.prob_at(x, y, 0.0) >= args.p_cut:
            continue
        if abs(y - ign_y) > band:
            continue
        cand.append(n)

    # ---- 6-bucket PARTITION classification (from run_routing_integration) --
    print(f"[3/4] classifying {len(cand)} origins (p_cut={args.p_cut}, "
          f"budget={args.time_budget_min} min) ...")
    classes = {"naive_into_FA_safe": [], "no_safe_route": [], "both_safe": [],
               "both_enter": [], "naive_unreachable": [], "unclassified": []}
    best_headline, best_gain, no_safe_example = None, -np.inf, None
    for n in cand:
        nv = naive_route(walk, n, hazard, departure_min=0.0, p_cut=args.p_cut)
        fa = future_aware_route(walk, n, hazard, departure_min=0.0,
                                time_budget_min=args.time_budget_min, p_cut=args.p_cut,
                                time_step_min=args.time_step_min)
        if not nv.reached:
            classes["naive_unreachable"].append(n); continue
        if nv.enters_hazard and fa.reached and not fa.enters_hazard:
            classes["naive_into_FA_safe"].append(n)
            if (nv.exposure - fa.exposure) > best_gain:
                best_gain, best_headline = nv.exposure - fa.exposure, (n, nv, fa)
        elif nv.enters_hazard and not fa.reached:
            classes["no_safe_route"].append(n)
            if no_safe_example is None:
                no_safe_example = (n, nv, fa)
        elif not nv.enters_hazard and fa.reached and not fa.enters_hazard:
            classes["both_safe"].append(n)
        elif nv.enters_hazard and fa.enters_hazard:
            classes["both_enter"].append(n)
        else:
            classes["unclassified"].append(n)

    total = sum(len(v) for v in classes.values())
    assert total == len(cand), f"classification must partition: {total} != {len(cand)}"

    def route_xy(route):
        return [[float(walk.graph.nodes[n]["x"]), float(walk.graph.nodes[n]["y"])] for n in route]

    try:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO).decode().strip()
    except Exception:  # noqa: BLE001
        head = None

    summary = {
        "title": "Real roads + real hazard evacuation-routing run (Yeongdeok 2025)",
        "p_cut": args.p_cut, "time_budget_min": args.time_budget_min,
        "time_step_min": args.time_step_min,
        "n_origins_scanned": len(cand),
        "counts": {k: len(v) for k, v in classes.items()},
        "partition_holds": total == len(cand),
        "network_source": {
            "kind": "REAL — OpenStreetMap via OSMnx",
            "osmnx_query": f"ox.graph_from_bbox(bbox={tuple(bbox)}, network_type='walk')",
            "reprojected_to": "EPSG:5179 via ox.project_graph",
            "bbox_wgs84": list(bbox), "region_name": cfg.region_name,
            "n_nodes": int(walk.graph.number_of_nodes()),
            "n_edges": int(walk.graph.number_of_edges()),
            "n_nodes_outside_hazard_extent": n_outside,
            "shelter_source": shelters_source,
            "n_refuge_pois": len(dests), "n_shelter_nodes": len(shelter_nodes),
            "origin_scan": {"stride": REAL_OSM_SCAN_STRIDE, "walk_cutoff": args.p_cut,
                            "ignition_proxy_xy_5179": [ign_x, ign_y],
                            "note": "ignition proxy = centroid of t0 >=0.5 hazard core; "
                                    "reach band does not bind (exceeds graph footprint)"},
        },
        "hazard_source": {
            "kind": "REAL — spread_v2 forward-simulation ignition-probability field",
            "npz_path": str(npz_path.relative_to(REPO)) if npz_path.is_relative_to(REPO) else str(npz_path),
            "npz_sha256": npz_sha,
            "shape": list(haz_stack.shape), "times_min": haz_times.tolist(),
            "grid_extent_5179": [xmin, ymin, xmax, ymax, cell],
            "constructed_via": "HazardSequence(grid, times_min, surfaces) — direct, not from_forward_sim",
            "known_origin_prob_at_t0": p_known,
        },
        "git_head": head,
        "config_hash": config_hash(),
        "provenance": {
            "roads_real": True, "hazard_real": True,
            "statement": "BOTH road topology AND fire-hazard surface are REAL. Roads/refuges "
                         "are real OpenStreetMap geometry (OSMnx, EPSG:5179); the hazard is the "
                         "real spread_v2 forward-simulated ignition-probability field for the "
                         "held-out Yeongdeok 2025 fire. Closes the limitation that road topology "
                         "and fire-hazard surface were never simultaneously real.",
            "still_synthetic_or_assumed": [
                "elderly walk speed 0.7 m/s (assumed)",
                "no per-node DEM slope on OSM walk edges (flat-speed timing)",
                "elderly-home origins (seeded sampled candidates; real data private)"],
            "gate_b_temporal_resolution": {
                "npz_hazard": "5 slices at 180-min steps [0,180,360,540,720]",
                "rescue_run_synthetic_hazard": "15 slices at 15-min steps [0,15,...,600]",
                "factor": "~12x coarser",
                "cells_ge_0.5_per_frame": [int((haz_stack[i] >= 0.5).sum())
                                           for i in range(haz_stack.shape[0])],
                "cells_ge_0.3_per_frame": [int((haz_stack[i] >= 0.3).sum())
                                           for i in range(haz_stack.shape[0])],
                "consequences": [
                    "results dominated by the near-static >=0.5 core, not front advance",
                    "NOT directly comparable to the ~439-origin rescue run on timing",
                    "third cell of the real/synthetic axis table, not a like-for-like replacement"],
            },
        },
        "method_matches_repo": "6-bucket partition from scripts/run_routing_integration.py; "
                               "routing via evacuation.naive_route / future_aware_route (unchanged).",
    }
    if best_headline is not None:
        o, nv, fa = best_headline
        summary["headline"] = {
            "origin_node": int(o), "origin_xy_5179": route_xy([o])[0],
            "naive": nv.as_dict(), "future_aware": fa.as_dict(),
            "exposure_reduction_abs": nv.exposure - fa.exposure,
            "exposure_reduction_pct": (100.0 * (nv.exposure - fa.exposure) / nv.exposure
                                       if nv.exposure > 0 else None),
        }
    if no_safe_example is not None:
        nn, nnv, nfa = no_safe_example
        summary["no_safe_route_example"] = {
            "origin_node": int(nn), "naive": nnv.as_dict(), "future_aware": nfa.as_dict()}

    print("[4/4] writing JSON ...")
    Path(args.out).write_text(json.dumps(summary, indent=2, default=str))
    c = summary["counts"]
    print(f"done. counts={c} (sum={sum(c.values())}=N={len(cand)}); wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
