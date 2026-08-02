#!/usr/bin/env python
"""The 459-series scan for Yeongdeok, on the CANONICAL hazard field.

Round-3, follow-up to ``data/processed/routing_demo_divergence.json``.

The committed 459 series consumes ``routing_demo.npz``, which the investigation
identified as the surviving output of the 2026-07-20 run that was reverted the
next day. This re-runs the same scan against
``routing_demo_canonical.npz`` — built from the current canonical dataset
(151,904 rows / 2,989 positives) on an unclipped canvas — so the two can be put
side by side.

    ⚠ Writes ONLY ``data/processed/real_roads_real_hazard_canonical.json``.
      Every committed artifact is digest-checked before and after; the run exits
      4 if one moves. It does not touch the slope, objective or budget
      experiments, which are deliberately NOT re-run yet.

WHAT IS AND IS NOT COMPARABLE
-----------------------------
The committed 459 = 438 + 18 + 3 was produced on the 2026-07-23 OSM walk graph,
which no longer exists (``docs/DATA_LOSS_2026-07-24.md``). It is quoted, never
re-derived. The reproducible reference is the 2026-07-24 snapshot graph, whose
flat and slope arms on the OLD hazard field are the committed
``real_roads_real_hazard_slope_60.json`` columns 2 and 3 (460 origins,
440 / 17 / 3). So the honest comparison is three-way:

    committed 459        Jul-23 network, OLD hazard      QUOTED
    slope_60 col2/col3   Jul-24 network, OLD hazard      QUOTED
    this run             Jul-24 network, CANONICAL hazard

Only the last pair differs by one variable.

Run:  python scripts/run_yeongdeok_canonical_routing.py
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
sys.path.insert(0, str(REPO / "scripts"))

from wildfireguardian.config import config_hash, get as _cfg  # noqa: E402
from wildfireguardian.routing.hazard import HazardSequence  # noqa: E402
from wildfireguardian.routing.slope import (  # noqa: E402
    build_walk_network, load_snapshot_graph,
)
from wildfireguardian.spread_v2.extent import (  # noqa: E402
    boundary_contact, check_envelope_coverage, check_routing_clearance,
)
from wildfireguardian.spread_v2.grid import CoarseGrid  # noqa: E402
from pyproj import Transformer  # noqa: E402

# The origin rule and the classification are IMPORTED, never re-stated, so this
# run cannot silently mean something different by "origin" or by "both_safe".
from run_real_roads_real_hazard_slope import (  # noqa: E402
    REAL_OSM_SCAN_STRIDE, candidate_origins, classify,
)
from run_multi_region_routing import (  # noqa: E402
    PROTECTED, protected_digests, read_poi_snapshot, snapshot_for,
)

_TO_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)

REGION = "yeongdeok_2025"
DEM = REPO / "data/raw/firms_data/yeongdeok_2025_dem.tif"
COMMITTED_459 = REPO / "data/processed/real_roads_real_hazard.json"
COMMITTED_SLOPE60 = REPO / "data/processed/real_roads_real_hazard_slope_60.json"


def _git() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--npz", default=str(REPO / "data/processed/routing_demo_canonical.npz"))
    ap.add_argument("--sampling-m", type=float,
                    default=float(_cfg("pedestrian.slope_sampling_m", 60.0)))
    ap.add_argument("--max-abs-slope", type=float,
                    default=float(_cfg("pedestrian.max_abs_slope", 0.60)))
    ap.add_argument("--p-cut", type=float, default=float(_cfg("pedestrian.walk_cutoff_p", 0.5)))
    ap.add_argument("--time-budget-min", type=float,
                    default=float(_cfg("pedestrian.walk_budget_min", 600.0)))
    ap.add_argument("--time-step-min", type=float,
                    default=float(_cfg("time.routing_time_step_min", 10.0)))
    ap.add_argument("--out", default=str(REPO / "data/processed/real_roads_real_hazard_canonical.json"))
    args = ap.parse_args()

    before = protected_digests()
    if any(v is None for v in before.values()):
        print("STOP: a protected artifact is missing.", file=sys.stderr)
        return 2
    print("protected artifacts recorded:")
    for k, v in before.items():
        print(f"  {v[:16]}...  {k}")

    npz = Path(args.npz)
    if not npz.exists():
        print(f"STOP: {npz} missing — run scripts/build_canonical_hazard.py first.",
              file=sys.stderr)
        return 2
    z = np.load(npz)
    haz = z["haz_stack"].astype(np.float32)
    times = np.asarray(z["haz_times"], float)
    xmin, ymin, xmax, ymax, cell = [float(v) for v in z["grid_extent"]]
    grid = CoarseGrid(minx=xmin, miny=ymin, maxx=xmax, maxy=ymax, cell_size_m=cell,
                      nrows=haz.shape[1], ncols=haz.shape[2])
    hazard = HazardSequence(grid=grid, times_min=times,
                            surfaces=[haz[i] for i in range(haz.shape[0])])
    extent = (xmin, ymin, xmax, ymax, cell)
    npz_sha = hashlib.sha256(npz.read_bytes()).hexdigest()
    print(f"\ncanonical hazard: {haz.shape} sha256 {npz_sha[:16]}...")

    snap = snapshot_for(REGION, "walk")
    G = load_snapshot_graph(snap)
    print(f"snapshot walk graph: {snap.name}\n"
          f"  {G.number_of_nodes():,} nodes, {G.number_of_edges():,} directed edges")

    walk_bbox = (_cfg("bbox.multi_region_walk_bbox", {}) or {})[REGION]
    xs, ys = [], []
    for lon, lat in ((walk_bbox[0], walk_bbox[1]), (walk_bbox[0], walk_bbox[3]),
                     (walk_bbox[2], walk_bbox[1]), (walk_bbox[2], walk_bbox[3])):
        x, y = _TO_5179.transform(lon, lat)
        xs.append(x); ys.append(y)
    rb = (min(xs), min(ys), max(xs), max(ys))

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        cov_final = check_envelope_coverage(rb, haz[-1], grid, p_cut=args.p_cut)
        cov_t0 = check_envelope_coverage(rb, haz[0], grid, p_cut=args.p_cut)
        clearance = check_routing_clearance(rb, grid)
        warned = [str(w.message)[:200] for w in caught]
    edge = [dict(boundary_contact(haz[i]), slice=i) for i in range(haz.shape[0])]
    print(f"  envelope coverage (final slice): {cov_final['n_covered']}/"
          f"{cov_final['n_core_cells']} = {cov_final['coverage'] * 100:.1f}%")
    print(f"  boundary: {'REACHED' if any(e['reached'] for e in edge) else 'clear'}")
    print(f"  grid clearance km: {clearance['margins_km']}")

    dests, n_shelter_pois = read_poi_snapshot(snapshot_for(REGION, "shelters"),
                                              kind="shelter")
    if not dests:
        print("STOP (GATE A): zero refuges.", file=sys.stderr)
        return 3
    print(f"  refuges: {n_shelter_pois} POIs")

    def run_arm(label, net, apply_slope):
        net.shelters = {net.nearest_node(d.x, d.y) for d in dests}
        cand, ign = candidate_origins(net, hazard, haz, extent, args.p_cut)
        t0 = time.monotonic()
        counts = classify(net, cand, hazard, args.p_cut, args.time_budget_min,
                          args.time_step_min)
        n = max(len(cand), 1)
        print(f"  {label:26s} N={len(cand):4d}  both_safe={counts['both_safe']:4d}  "
              f"FA_only={counts['naive_into_FA_safe']:3d}  "
              f"no_safe={counts['no_safe_route']:3d}  "
              f"budget={counts['fa_exceeds_budget']:3d}  "
              f"[{time.monotonic() - t0:.0f}s]")
        return {"label": label, "n_origins_scanned": len(cand), "counts": counts,
                "future_aware_only_safe_fraction": counts["naive_into_FA_safe"] / n,
                "n_shelter_nodes": len(net.shelters),
                "n_nodes": net.graph.number_of_nodes(),
                "n_edges": net.graph.number_of_edges(),
                "ignition_proxy_xy_5179": list(ign), "slope_applied": apply_slope}

    print("\narms:")
    net_flat, _ = build_walk_network(G, None, apply_slope=False, directed=False)
    arm_flat = run_arm("flat / undirected", net_flat, False)
    net_slope, st = build_walk_network(G, DEM, sampling_m=args.sampling_m,
                                       max_abs_slope=args.max_abs_slope,
                                       directed=True, apply_slope=True)
    arm_slope = run_arm(f"slope {args.sampling_m:g}m / DiGraph", net_slope, True)

    committed = json.loads(COMMITTED_459.read_text())
    s60 = json.loads(COMMITTED_SLOPE60.read_text())["three_column_comparison"]

    doc = {
        "schema_version": 1,
        "title": "Yeongdeok 459-series on the CANONICAL hazard field",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _git(), "config_hash": config_hash(),
        "does_not_supersede": (
            "real_roads_real_hazard.json and real_roads_real_hazard_slope_60.json "
            "are UNTOUCHED. The PHASE-2/2-C derived experiments (slope 30/90, "
            "routing objective, budget sweep) were deliberately NOT re-run."),
        "hazard_source": {
            "kind": "CANONICAL — 151,904 rows / 2,989 positives, corrected DEMs, "
                    "unclipped canvas",
            "npz_path": str(npz.relative_to(REPO)), "npz_sha256": npz_sha,
            "shape": list(haz.shape), "grid_extent_5179": list(extent),
            "cells_ge_0.5_per_slice": [int((haz[i] >= 0.5).sum())
                                       for i in range(haz.shape[0])],
            "provenance_doc": "data/processed/canonical_hazard.json",
        },
        "network_source": {
            "kind": "REAL — OpenStreetMap, snapshot store (data/cache never read)",
            "snapshot_walk": snap.name, "n_refuge_pois": n_shelter_pois,
            "bbox_wgs84": list(walk_bbox),
        },
        "parameters": {
            "slope_sampling_m": args.sampling_m, "max_abs_slope": args.max_abs_slope,
            "p_cut": args.p_cut, "time_budget_min": args.time_budget_min,
            "time_step_min": args.time_step_min,
            "origin_scan_stride": REAL_OSM_SCAN_STRIDE,
            "routing_objective": "length_m (distance-ranked)",
            "source": "config/default.yaml — unchanged from every 459-series run",
        },
        "preflight": {
            "routing_bbox_5179": [float(v) for v in rb],
            "envelope_coverage": {"final_slice": cov_final, "t0_slice": cov_t0,
                                  "warnings": warned},
            "boundary_contact": {
                "per_slice": edge,
                "any_slice_reached_edge": any(e["reached"] for e in edge),
                "max_edge_p": max(max(e["max_p_per_edge"].values()) for e in edge)},
            "routing_clearance": clearance,
        },
        "arms": {"flat_undirected": arm_flat, "slope_digraph_canonical": arm_slope},
        "side_by_side": {
            "committed_459_jul23_network_old_hazard": {
                "n_origins_scanned": committed["n_origins_scanned"],
                "counts": committed["counts"],
                "status": "QUOTED — its OSM network was overwritten 2026-07-24 "
                          "and is unrecoverable; never re-derived",
            },
            "committed_slope60_col2_jul24_network_old_hazard": {
                "n_origins_scanned": s60["col2_jul24_flat"]["n_origins_scanned"],
                "counts": s60["col2_jul24_flat"]["counts"], "status": "QUOTED"},
            "committed_slope60_col3_jul24_network_old_hazard": {
                "n_origins_scanned": s60["col3_jul24_slope"]["n_origins_scanned"],
                "counts": s60["col3_jul24_slope"]["counts"], "status": "QUOTED"},
            "canonical_flat_jul24_network_canonical_hazard": {
                "n_origins_scanned": arm_flat["n_origins_scanned"],
                "counts": arm_flat["counts"]},
            "canonical_slope_jul24_network_canonical_hazard": {
                "n_origins_scanned": arm_slope["n_origins_scanned"],
                "counts": arm_slope["counts"]},
            "single_variable_pairs": (
                "col2 vs canonical_flat, and col3 vs canonical_slope, differ ONLY "
                "in the hazard field. The committed 459 row differs additionally "
                "by its OSM network and is not a single-variable comparison."),
        },
    }
    Path(args.out).write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")

    after = protected_digests()
    changed = [k for k in before if before[k] != after[k]]
    if changed:
        print(f"\nSTOP (exit 4): protected artifact(s) changed: {changed}",
              file=sys.stderr)
        return 4
    print(f"\nwrote {Path(args.out).relative_to(REPO)}")
    print(f"protected artifacts unchanged ({len(PROTECTED)} verified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
