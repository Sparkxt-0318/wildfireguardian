#!/usr/bin/env python
"""Does the ROUTING OBJECTIVE decide whether slope can matter? (PHASE 2-C-1)

PHASE 2 found that DEM slope raises walking times ~26 % yet moves no count in
the 6-bucket classification. Three causes were identified; this experiment
addresses the most fundamental one:

    `naive_route` minimises DISTANCE, so its chosen path is slope-invariant BY
    CONSTRUCTION. No refinement of the hazard field can change that — the path
    was never looking at terrain in the first place.

Four arms, 2x2:

                    flat timing        slope timing (60 m)
    distance-min    the committed behaviour     PHASE 2 (counts unchanged)
    time-min        new                         new

Under time minimisation a walker may prefer a longer, gentler detour to a steep
short-cut, so slope can change the ROUTE and not merely its duration.

Purely additive: writes data/processed/routing_objective_experiment.json.
Nothing else is touched.

Run:  python scripts/run_routing_objective_experiment.py
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
from wildfireguardian.routing.evacuation import future_aware_route, naive_route  # noqa: E402
from wildfireguardian.routing.rescue import RescueConfig, load_shelters  # noqa: E402
from wildfireguardian.routing.slope import build_walk_network, load_snapshot_graph  # noqa: E402
from wildfireguardian.utils import regions  # noqa: E402
from pyproj import Transformer  # noqa: E402

sys.path.insert(0, str(REPO / "scripts"))
from run_real_roads_real_hazard_slope import (  # noqa: E402
    DEM, SNAPSHOT, candidate_origins, classify, load_hazard,
)

_TO_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
OUT = REPO / "data" / "processed" / "routing_objective_experiment.json"


def _git():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sampling-m", type=float,
                    default=_cfg("pedestrian.slope_sampling_m", 60.0))
    ap.add_argument("--p-cut", type=float, default=_cfg("pedestrian.walk_cutoff_p", 0.5))
    ap.add_argument("--time-budget-min", type=float,
                    default=_cfg("pedestrian.walk_budget_min", 600.0))
    ap.add_argument("--time-step-min", type=float,
                    default=_cfg("time.routing_time_step_min", 10.0))
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    hazard, haz, extent, npz_sha = load_hazard()
    G = load_snapshot_graph(SNAPSHOT)
    cfg = RescueConfig(use_osm=True, osm_cache_dir=str(REPO / "data/cache/osm"))
    bbox = regions.lookup(cfg.region_name).bbox_wgs84
    dests, shelter_src = load_shelters(cfg, bbox, to_5179=_TO_5179)

    print("building networks ...")
    nets = {
        "flat": build_walk_network(G, None, apply_slope=False, directed=True)[0],
        "slope": build_walk_network(G, DEM, sampling_m=args.sampling_m,
                                    directed=True, apply_slope=True)[0],
    }
    for n in nets.values():
        n.shelters = {n.nearest_node(d.x, d.y) for d in dests}

    cand, _ = candidate_origins(nets["flat"], hazard, haz, extent, args.p_cut)
    print(f"origins: {len(cand)}")

    arms, routes = {}, {}
    for timing, net in nets.items():
        for objective in ("length_m", "time_min"):
            key = f"{timing}/{objective}"
            counts = classify(net, cand, hazard, args.p_cut,
                              args.time_budget_min, args.time_step_min)
            rs = {}
            for n in cand:
                r = naive_route(net, n, hazard, departure_min=0.0,
                                p_cut=args.p_cut, objective=objective)
                rs[n] = r
            routes[key] = rs
            reached = [r for r in rs.values() if r.reached]
            arms[key] = {
                "timing": timing, "objective": objective,
                "n_origins_scanned": len(cand), "counts": counts,
                "naive_mean_distance_m": float(np.mean([r.total_distance_m for r in reached])),
                "naive_mean_time_min": float(np.mean([r.total_time_min for r in reached])),
                "naive_max_time_min": float(np.max([r.total_time_min for r in reached])),
            }
            print(f"  {key:22s} both_safe={counts['both_safe']:4d} "
                  f"FA_only={counts['naive_into_FA_safe']:3d} "
                  f"no_safe={counts['no_safe_route']:3d}   "
                  f"mean dist {arms[key]['naive_mean_distance_m']:8.0f} m  "
                  f"mean time {arms[key]['naive_mean_time_min']:7.1f} min")

    def path_delta(a: str, b: str) -> dict:
        ra, rb = routes[a], routes[b]
        both = [n for n in cand if ra[n].reached and rb[n].reached]
        changed = [n for n in both if ra[n].route != rb[n].route]
        longer = [n for n in changed
                  if rb[n].total_distance_m > ra[n].total_distance_m + 1e-6]
        faster = [n for n in changed
                  if rb[n].total_time_min < ra[n].total_time_min - 1e-9]
        dd = [rb[n].total_distance_m / max(ra[n].total_distance_m, 1e-9) - 1
              for n in changed]
        dt = [rb[n].total_time_min / max(ra[n].total_time_min, 1e-9) - 1
              for n in changed]
        return {
            "from": a, "to": b, "n_comparable": len(both),
            "n_path_changed": len(changed),
            "frac_path_changed": len(changed) / max(len(both), 1),
            "n_detour_is_longer": len(longer),
            "n_detour_is_faster": len(faster),
            "median_distance_change_pct": float(np.median(dd) * 100) if dd else 0.0,
            "max_distance_change_pct": float(np.max(dd) * 100) if dd else 0.0,
            "median_time_change_pct": float(np.median(dt) * 100) if dt else 0.0,
            "min_time_change_pct": float(np.min(dt) * 100) if dt else 0.0,
        }

    print("\npath changes:")
    deltas = {
        "slope_effect_under_distance_min": path_delta("flat/length_m", "slope/length_m"),
        "slope_effect_under_time_min": path_delta("flat/time_min", "slope/time_min"),
        "objective_effect_under_flat": path_delta("flat/length_m", "flat/time_min"),
        "objective_effect_under_slope": path_delta("slope/length_m", "slope/time_min"),
    }
    for k, d in deltas.items():
        print(f"  {k:34s} {d['n_path_changed']:4d}/{d['n_comparable']:4d} changed "
              f"({d['frac_path_changed']*100:5.1f}%)  "
              f"longer-but-chosen={d['n_detour_is_longer']:4d}  "
              f"faster={d['n_detour_is_faster']:4d}")

    key = deltas["slope_effect_under_time_min"]
    doc = {
        "schema_version": 1,
        "title": "Routing objective vs slope sensitivity (PHASE 2-C-1)",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _git(), "config_hash": config_hash(),
        "question": "PHASE 2 found slope moves no count. Is that because "
                    "naive_route minimises DISTANCE, making its path "
                    "slope-invariant by construction?",
        "design": {
            "arms": "2x2: timing (flat | slope 60 m) x objective (length_m | time_min)",
            "held_constant": ["snapshot walk graph (2026-07-24)", "osmnx 2.0.7",
                              "hazard field (routing_demo.npz)",
                              f"p_cut={args.p_cut}",
                              f"time_budget_min={args.time_budget_min}",
                              "shelters, origin scan rule"],
            "hazard_npz_sha256": npz_sha,
            "shelter_source": shelter_src,
            "sampling_m": args.sampling_m,
        },
        "arms": arms,
        "path_deltas": deltas,
        "finding": {
            "slope_changes_route_under_time_min": key["n_path_changed"] > 0,
            "n_routes_changed_by_slope_under_time_min": key["n_path_changed"],
            "counts_moved": any(arms[k]["counts"] != arms["flat/length_m"]["counts"]
                                for k in arms),
        },
        "caveat": "Arm values are on the 2026-07-24 snapshot network and are "
                  "SEPARATE from the committed 459-origin figures, whose network "
                  "is unrecoverable. The default objective is unchanged: "
                  "length_m remains the committed behaviour.",
    }
    Path(args.out).write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")
    shown = Path(args.out)
    print(f"\nwrote {shown.relative_to(REPO) if shown.is_relative_to(REPO) else shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
