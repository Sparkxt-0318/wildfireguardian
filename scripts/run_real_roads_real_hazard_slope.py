#!/usr/bin/env python
"""Re-run the 459-origin scan with DEM slope on the OSM walk edges.

Round-3 PHASE 2-B.

Purely additive. Writes only
``data/processed/real_roads_real_hazard_slope_{30,60,90}.json``; the committed
``real_roads_real_hazard.json`` is never touched.

WHAT IS AND IS NOT VARIED
-------------------------
The committed 459-origin numbers were produced on an OSM graph that no longer
exists (docs/DATA_LOSS_2026-07-24.md), so a two-column "before slope / after
slope" table would silently attribute network drift to the slope model. The
comparison is therefore three columns:

    1. committed        Jul-23 network, flat        QUOTED, never re-run
    2. Jul-24 network, flat                         isolates NETWORK DRIFT
    3. Jul-24 network, slope                        isolates SLOPE

Columns 2 and 3 read the same snapshot graph with osmnx pinned to 2.0.7 (the
version recorded in the snapshot's `created_with`), so 2 -> 3 is a
single-variable contrast.

Run:  python scripts/run_real_roads_real_hazard_slope.py
      python scripts/run_real_roads_real_hazard_slope.py --spacings 60
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

from wildfireguardian.config import config_hash, get as _cfg  # noqa: E402
from wildfireguardian.routing.evacuation import future_aware_route, naive_route  # noqa: E402
from wildfireguardian.routing.hazard import HazardSequence  # noqa: E402
from wildfireguardian.routing.rescue import RescueConfig, load_shelters  # noqa: E402
from wildfireguardian.routing.slope import (  # noqa: E402
    build_walk_network, load_snapshot_graph, slowest_edges,
)
from wildfireguardian.spread_v2.grid import CoarseGrid  # noqa: E402
from wildfireguardian.utils import regions  # noqa: E402
from pyproj import Transformer  # noqa: E402

_TO_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)

SNAPSHOT = REPO / "data/snapshots/osm-walk_yeongdeok-2025_20260724_2bff8d85.graphml.gz"
DEM = REPO / "data/raw/firms_data/yeongdeok_2025_dem.tif"
NPZ = REPO / "data/processed/routing_demo.npz"
COMMITTED = REPO / "data/processed/real_roads_real_hazard.json"

#: Matches rescue_demo.REAL_OSM_SCAN_STRIDE and the committed run.
REAL_OSM_SCAN_STRIDE = int(_cfg("origin_scan.real_osm_stride", 18))


def load_hazard():
    z = np.load(NPZ)
    haz = z["haz_stack"].astype(np.float32)
    times = np.asarray(z["haz_times"], float)
    xmin, ymin, xmax, ymax, cell = [float(v) for v in z["grid_extent"]]
    grid = CoarseGrid(minx=xmin, miny=ymin, maxx=xmax, maxy=ymax,
                      cell_size_m=cell, nrows=haz.shape[1], ncols=haz.shape[2])
    hazard = HazardSequence(grid=grid, times_min=times,
                            surfaces=[haz[i] for i in range(haz.shape[0])])
    sha = hashlib.sha256(NPZ.read_bytes()).hexdigest()
    return hazard, haz, (xmin, ymin, xmax, ymax, cell), sha


def candidate_origins(net, hazard, haz, extent, p_cut):
    """The committed run's origin rule, unchanged: stride, p_cut, reach band."""
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
    return cand, (ign_x, ign_y)


def classify(net, cand, hazard, p_cut, budget, step, objective="length_m"):
    """The 6-bucket PARTITION from run_routing_integration.py, PLUS one category.

    ``fa_exceeds_budget`` — naive route is safe, but the future-aware router
    cannot finish within ``budget`` — is ADDITIVE. The five original categories
    keep their exact definitions and evaluation order, so committed results are
    unaffected.

    The addition exists because the original partition was written when the
    budget never bound. Once it does, "naive safe, future-aware over budget"
    becomes the commonest state, and it previously fell through every branch into
    ``unclassified`` — 235 of 460 origins at a 30-minute budget (PHASE 2-C-2).
    That is a state with a meaning, not a residue.

    At a 600-minute budget the new category is EMPTY and the five original counts
    are unchanged; ``tests/test_partition_categories.py`` asserts exactly that.
    """
    classes = {"naive_into_FA_safe": [], "no_safe_route": [], "both_safe": [],
               "both_enter": [], "naive_unreachable": [], "fa_exceeds_budget": [],
               "unclassified": []}
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
        # --- ADDITIVE: everything above is untouched -------------------------
        elif not nv.enters_hazard and not fa.reached:
            classes["fa_exceeds_budget"].append(n)
        else:
            classes["unclassified"].append(n)
    counts = {k: len(v) for k, v in classes.items()}
    assert sum(counts.values()) == len(cand), "classification must partition"
    return counts


def _git():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spacings", type=float, nargs="+",
                    default=_cfg("pedestrian.slope_sampling_sweep_m", [30.0, 60.0, 90.0]))
    ap.add_argument("--p-cut", type=float, default=_cfg("pedestrian.walk_cutoff_p", 0.5))
    ap.add_argument("--time-budget-min", type=float,
                    default=_cfg("pedestrian.walk_budget_min", 600.0))
    ap.add_argument("--time-step-min", type=float,
                    default=_cfg("time.routing_time_step_min", 10.0))
    ap.add_argument("--max-abs-slope", type=float,
                    default=_cfg("pedestrian.max_abs_slope", 0.60))
    ap.add_argument("--out-dir", default=str(REPO / "data" / "processed"))
    args = ap.parse_args()

    for p in (SNAPSHOT, DEM, NPZ, COMMITTED):
        if not p.exists():
            print(f"STOP: missing required input {p}", file=sys.stderr)
            return 2

    hazard, haz, extent, npz_sha = load_hazard()
    print(f"hazard: {haz.shape} sha256 {npz_sha[:16]}...")
    G = load_snapshot_graph(SNAPSHOT)
    print(f"snapshot walk graph: {G.number_of_nodes():,} nodes, "
          f"{G.number_of_edges():,} directed edges")

    cfg = RescueConfig(use_osm=True, osm_cache_dir=str(REPO / "data/cache/osm"))
    bbox = regions.lookup(cfg.region_name).bbox_wgs84

    committed = json.loads(COMMITTED.read_text())
    results: dict[str, dict] = {}

    def run_arm(label, net, stats):
        dests, src_ = load_shelters(cfg, bbox, to_5179=_TO_5179)
        net.shelters = {net.nearest_node(d.x, d.y) for d in dests}
        cand, ign = candidate_origins(net, hazard, haz, extent, args.p_cut)
        counts = classify(net, cand, hazard, args.p_cut,
                          args.time_budget_min, args.time_step_min)
        print(f"  {label:34s} N={len(cand):4d}  "
              f"both_safe={counts['both_safe']:4d}  "
              f"FA_only={counts['naive_into_FA_safe']:3d}  "
              f"no_safe={counts['no_safe_route']:3d}  "
              f"unreach={counts['naive_unreachable']:3d}")
        return {"label": label, "n_origins_scanned": len(cand), "counts": counts,
                "n_shelter_nodes": len(net.shelters), "shelter_source": src_,
                "n_nodes": net.graph.number_of_nodes(),
                "n_edges": net.graph.number_of_edges(),
                "slope_stats": stats.as_dict() if stats is not None else None}

    # ---- regression gate: DiGraph must not change a FLAT run -----------------
    print("\n[1/3] regression: flat timing, undirected vs DiGraph "
          "(must be identical) ...")
    net_u, _ = build_walk_network(G, None, apply_slope=False, directed=False)
    net_d, _ = build_walk_network(G, None, apply_slope=False, directed=True)
    arm_flat_undirected = run_arm("flat / undirected (col 2)", net_u, None)
    arm_flat_digraph = run_arm("flat / DiGraph  (regression)", net_d, None)
    identical = (arm_flat_undirected["counts"] == arm_flat_digraph["counts"]
                 and arm_flat_undirected["n_origins_scanned"]
                 == arm_flat_digraph["n_origins_scanned"])
    print(f"  -> DiGraph regression: "
          f"{'PASS (identical)' if identical else 'FAIL — DIVERGES'}")
    if not identical:
        print("STOP: the DiGraph conversion changed a flat-timing result. Slope "
              "must not be applied until this is resolved.", file=sys.stderr)
        return 3

    # ---- slope arms ----------------------------------------------------------
    print("\n[2/3] slope arms ...")
    for spacing in args.spacings:
        for clip in (args.max_abs_slope, None):
            tag = f"slope {spacing:g}m " + (f"clip{clip:g}" if clip else "NOCLIP")
            net_s, st = build_walk_network(
                G, DEM, sampling_m=spacing, max_abs_slope=clip,
                directed=True, apply_slope=True)
            arm = run_arm(tag, net_s, st)
            arm["top_slowed_edges"] = slowest_edges(st, net_s, k=10)
            results[f"{int(spacing)}m_{'clipped' if clip else 'unclipped'}"] = arm

    # ---- write one file per spacing ------------------------------------------
    print("\n[3/3] writing ...")
    out_dir = Path(args.out_dir)
    written = []
    for spacing in args.spacings:
        key_c = f"{int(spacing)}m_clipped"
        key_u = f"{int(spacing)}m_unclipped"
        canonical = abs(spacing - float(_cfg("pedestrian.slope_sampling_m", 60.0))) < 1e-9
        doc = {
            "title": "Real roads + real hazard + real terrain "
                     f"(Yeongdeok 2025, {spacing:g} m slope sampling)",
            "schema_version": 1,
            "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "git_commit": _git(),
            "config_hash": config_hash(),
            "is_canonical_sampling": canonical,
            "p_cut": args.p_cut,
            "time_budget_min": args.time_budget_min,
            "time_step_min": args.time_step_min,
            "three_column_comparison": {
                "col1_committed_jul23_flat": {
                    "source": "data/processed/real_roads_real_hazard.json",
                    "n_origins_scanned": committed["n_origins_scanned"],
                    "counts": committed["counts"],
                    "note": "QUOTED, NOT re-run. Its OSM network was overwritten "
                            "2026-07-24 and is unrecoverable "
                            "(docs/DATA_LOSS_2026-07-24.md).",
                },
                "col2_jul24_flat": arm_flat_undirected,
                "col3_jul24_slope": results[key_c],
            },
            "unclipped_arm": results[key_u],
            "digraph_regression": {
                "undirected_counts": arm_flat_undirected["counts"],
                "digraph_counts": arm_flat_digraph["counts"],
                "identical": identical,
                "why": "With flat timing, direction carries no information, so "
                       "converting to a DiGraph MUST leave results unchanged. A "
                       "divergence here would mean the conversion is buggy.",
            },
            "network_source": {
                "kind": "REAL — OpenStreetMap, read from the SNAPSHOT store",
                "snapshot_file": SNAPSHOT.name,
                "snapshot_sha256_note": "uncompressed digest in "
                                        "data/snapshots/MANIFEST.json",
                "bbox_wgs84": list(bbox),
                "osmnx_pin": "2.0.7 (matches the snapshot's created_with)",
            },
            "hazard_source": {
                "kind": "REAL — spread_v2 forward-simulated ignition probability",
                "npz_path": "data/processed/routing_demo.npz",
                "npz_sha256": npz_sha,
                "shape": list(haz.shape),
            },
            "terrain_source": {
                "kind": "REAL — SRTM",
                "dem_path": "data/raw/firms_data/yeongdeok_2025_dem.tif",
                "sampling_m": spacing,
                "max_abs_slope": args.max_abs_slope,
                "tobler": "wildfireguardian.routing.evacuation.elderly_speed_ms "
                          "(REUSED, not reimplemented — identical to the 407-origin run)",
                "straight_line_edges": "OSM omits geometry where a way runs "
                                       "straight between its two nodes; those edges "
                                       "are interpolated straight, which is the "
                                       "intended reading rather than a fallback.",
            },
            "provenance": {
                "roads_real": True, "hazard_real": True, "terrain_real": True,
                "statement": "ALL THREE axes are real simultaneously: OpenStreetMap "
                             "road topology, the spread_v2 forward-simulated hazard "
                             "for the held-out Yeongdeok 2025 fire, and SRTM terrain "
                             "slope on the walk edges.",
                "slope_provenance": f"per-node DEM slope applied (Tobler, "
                                    f"{spacing:g}m arc-length sampling, DiGraph, "
                                    f"slope clipped at ±{args.max_abs_slope*100:g}%)",
                "supersedes_disclosure": "Replaces the Round-2 disclosure 'no "
                                         "per-node DEM slope on OSM walk edges "
                                         "(flat-speed timing)'.",
                "still_synthetic_or_assumed": [
                    f"elderly walk speed {_cfg('pedestrian.elderly_flat_speed_ms', 0.7)} m/s (literature/assumed)",
                    "elderly-home origins (seeded sampled candidates; real "
                    "per-household data is private)",
                    "slope clipping is a defence against DEM registration error "
                    "(bridges/tunnels/cuttings), NOT a physical correction",
                ],
            },
            "sampling_sensitivity": {
                f"{int(s)}m": {
                    "counts": results[f"{int(s)}m_clipped"]["counts"],
                    "n_origins_scanned": results[f"{int(s)}m_clipped"]["n_origins_scanned"],
                    "pct_change_mean_of_directions":
                        results[f"{int(s)}m_clipped"]["slope_stats"]
                        ["traversal_time"]["pct_change_mean_of_directions"],
                } for s in args.spacings
            },
        }
        out = out_dir / f"real_roads_real_hazard_slope_{int(spacing)}.json"
        out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
        written.append(out)
        shown = out.relative_to(REPO) if out.is_relative_to(REPO) else out
        print(f"  wrote {shown}" + ("   [CANONICAL]" if canonical else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
