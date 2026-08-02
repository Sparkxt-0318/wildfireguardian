#!/usr/bin/env python
"""OSM completeness covariates, measured identically for every region.

Round-3 PHASE 5 STEP 2-2.

WHY THIS EXISTS
---------------
A region whose roads are less completely mapped will look worse on any routing
metric, and that has nothing to do with its terrain or its fire. Comparing `w`
— or any routing outcome — across regions without these numbers beside it
cannot distinguish "regions differ" from "mapping differs".

So every cross-region table carries: road density, node density, the share of
edges with real geometry, the share with a `highway` tag, and shelter/depot POI
density. Same method, same denominators (each region's own walk-bbox area).

⚠ THE DEPOT COLUMN IS NOT A SCORE. Uiseong-Andong has zero mapped fire stations
inside its 919 km² ignition-centred box while the wider 3,926 km² manifest box
contains six. That is a fact about the box and about OSM coverage, not about
whether the county has a fire service.

Run:  python scripts/measure_osm_completeness.py
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import networkx as nx  # noqa: E402
import osmnx as ox  # noqa: E402
from pyproj import Transformer  # noqa: E402

from wildfireguardian.config import config_hash, get as _cfg  # noqa: E402
from wildfireguardian.routing.rescue import RescueConfig  # noqa: E402

_TO_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
OUT = REPO / "data" / "processed" / "osm_completeness.json"


def _git() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def bbox_area_km2(bbox) -> float:
    W, S, E, N = bbox
    xs, ys = [], []
    for lon in (W, E):
        for lat in (S, N):
            x, y = _TO_5179.transform(lon, lat)
            xs.append(x); ys.append(y)
    return (max(xs) - min(xs)) * (max(ys) - min(ys)) / 1e6


def n_features(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return len(json.loads(path.read_text(encoding="utf-8")).get("features", []))
    except Exception:  # noqa: BLE001
        return 0


def measure(region: str, bbox) -> dict | None:
    cfg = RescueConfig(region_name=region)
    d = REPO / cfg.osm_cache_path
    walk = d / "walk.graphml"
    if not walk.exists():
        print(f"  {region}: walk.graphml absent — skipped")
        return None

    G = ox.load_graphml(walk)
    U = nx.Graph(G)
    n_dir = G.number_of_edges()
    total_len_m = sum(float(a.get("length", 0.0)) for _, _, a in G.edges(data=True)) / 2
    n_geom = sum(1 for _, _, a in G.edges(data=True) if a.get("geometry") is not None)
    n_hw = sum(1 for _, _, a in G.edges(data=True) if a.get("highway"))
    area = bbox_area_km2(bbox)
    n_shelter = n_features(d / "shelters.geojson")
    n_depot = n_features(d / "depots.geojson")

    return {
        "region": region,
        "walk_bbox_wgs84_wsen": list(bbox),
        "bbox_area_km2": round(area, 1),
        "walk_nodes": G.number_of_nodes(),
        "walk_edges_directed": n_dir,
        "walk_edges_undirected": U.number_of_edges(),
        "walk_length_km": round(total_len_m / 1000, 1),
        # --- the covariates ------------------------------------------------
        "road_density_km_per_km2": round(total_len_m / 1000 / area, 3),
        "node_density_per_km2": round(G.number_of_nodes() / area, 2),
        "geometry_edge_fraction": round(n_geom / n_dir, 4) if n_dir else None,
        "highway_tag_fraction": round(n_hw / n_dir, 4) if n_dir else None,
        "shelter_pois": n_shelter,
        "shelter_density_per_100km2": round(n_shelter / area * 100, 2),
        "depot_pois": n_depot,
        "depot_density_per_100km2": round(n_depot / area * 100, 2),
        "responder_side_available": n_depot > 0,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    table = _cfg("bbox.multi_region_walk_bbox", {}) or {}
    rows = [r for r in (measure(k, v) for k, v in sorted(table.items())) if r]
    if not rows:
        print("STOP: no region has an acquired walk graph", file=sys.stderr)
        return 2

    base = next((r for r in rows if r["region"] == "yeongdeok_2025"), None)
    if base:
        for r in rows:
            r["relative_to_yeongdeok"] = {
                k: (round(r[k] / base[k], 3) if base[k] else None)
                for k in ("road_density_km_per_km2", "node_density_per_km2",
                          "shelter_density_per_100km2", "depot_density_per_100km2")
            }

    doc = {
        "schema_version": 1,
        "title": "OSM completeness covariates per region",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _git(), "config_hash": config_hash(),
        "osmnx_version": ox.__version__,
        "why": ("A less completely mapped region looks worse on any routing "
                "metric for reasons that have nothing to do with its terrain or "
                "its fire. These covariates must accompany every cross-region "
                "comparison so 'regions differ' can be told apart from "
                "'mapping differs'."),
        "depot_note": (
            "발화점 중심 919 km² 범위 내에 OSM에 매핑된 fire_station이 없으며, "
            "더 넓은 3,926 km² 범위에는 6곳이 있습니다. "
            "Uiseong-Andong has NO amenity=fire_station mapped in OSM inside its "
            "919 km² ignition-centred walk bbox; the wider 3,926 km² manifest "
            "bbox contains SIX. This is a property of the bbox and of OSM "
            "coverage — NOT a statement that the county has no fire service. "
            "The responder side is therefore recorded as NOT APPLICABLE for that "
            "region, never as zero dispatches. The resident-side 3-way split, "
            "which is the cross-region comparison metric, is unaffected."),
        "fire_station_counts_by_extent": {
            "uiseong_andong_2025": {
                "walk_bbox_919km2": 0, "manifest_bbox_3926km2": 6,
                "walk_bbox_with_police_tag": 10,
                "measured_utc": "2026-08-02",
                "note": "counted directly via ox.features_from_bbox to confirm "
                        "the empty result was real, not a transient failure",
            },
            "uljin_samcheok_2022": {"walk_bbox_924km2": 4},
            "yeongdeok_2025": {"walk_bbox_931km2": 4},
        },
        "regions": rows,
    }
    Path(args.out).write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")

    print(f"\n{'region':22s} {'area km2':>9s} {'road km/km2':>12s} {'nodes/km2':>10s} "
          f"{'geom %':>7s} {'hwy %':>6s} {'shelter/100':>12s} {'depot/100':>10s}")
    print("-" * 96)
    for r in rows:
        print(f"{r['region']:22s} {r['bbox_area_km2']:9.0f} "
              f"{r['road_density_km_per_km2']:12.3f} {r['node_density_per_km2']:10.2f} "
              f"{r['geometry_edge_fraction']*100:6.1f}% {r['highway_tag_fraction']*100:5.1f}% "
              f"{r['shelter_density_per_100km2']:12.2f} {r['depot_density_per_100km2']:10.2f}")
    o = Path(args.out)
    print(f"\nwrote {o.relative_to(REPO) if o.is_relative_to(REPO) else o}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
