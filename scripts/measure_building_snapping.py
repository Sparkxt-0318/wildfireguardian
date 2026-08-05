#!/usr/bin/env python
"""PHASE 18 STEP 1 — measure building→walk-network snapping BEFORE any routing.

Reports, for each region, exactly what the brief asked for before a routing run
is authorised:

  * snap-distance distribution (median / p90 / p99 / max)
  * how many buildings are excluded at a 100 / 200 / 300 / 500 m cap
  * whether the excluded buildings are spatially concentrated
  * buildings per walk node under the many-to-one snap (the "how many households
    sit behind this point" proxy)
  * how much of the region's settlement the OSM building layer actually
    represents, measured against the committed ESA WorldCover raster

⚠ It does NOT route and it does NOT sample. Writes one new JSON artifact and
nothing else. No committed artifact is read for writing.

Run:  python scripts/measure_building_snapping.py
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

from wildfireguardian.buildings import load_buildings, load_walk_nodes  # noqa: E402
from wildfireguardian.config import config_hash, get as _cfg  # noqa: E402

CAPS_M = (100.0, 200.0, 300.0, 500.0)
REGIONS = ("yeongdeok_2025", "uiseong_andong_2025", "uljin_samcheok_2022")

FUEL = {r: REPO / f"data/raw/firms_data/{r}_fuel.tif" for r in REGIONS}
HAZ = {
    "yeongdeok_2025": REPO / "data/processed/routing_demo_canonical.npz",
    "uiseong_andong_2025": REPO / "data/processed/hazard_uiseong_andong_2025.npz",
    "uljin_samcheok_2022": REPO / "data/processed/hazard_uljin_samcheok_2022.npz",
}
BUILT_UP = 50  # ESA WorldCover class


def _git() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _pcts(d: np.ndarray) -> dict:
    if not len(d):
        return {}
    return {"n": int(len(d)), "min_m": float(d.min()),
            "p50_m": float(np.percentile(d, 50)), "p75_m": float(np.percentile(d, 75)),
            "p90_m": float(np.percentile(d, 90)), "p95_m": float(np.percentile(d, 95)),
            "p99_m": float(np.percentile(d, 99)), "max_m": float(d.max()),
            "mean_m": float(d.mean())}


def builtup_pixels(fuel_path: Path, bbox) -> tuple[np.ndarray, float, bool]:
    """Class-50 pixel centres inside the walk bbox, projected to EPSG:5179."""
    import rasterio
    from rasterio.windows import from_bounds
    from pyproj import Transformer

    to5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
    W, S, E, N = bbox
    with rasterio.open(fuel_path) as ds:
        b = ds.bounds
        covers = (b.left <= W + 1e-9 and b.right >= E - 1e-9
                  and b.bottom <= S + 1e-9 and b.top >= N - 1e-9)
        win = from_bounds(max(W, b.left), max(S, b.bottom),
                          min(E, b.right), min(N, b.top), ds.transform)
        arr = ds.read(1, window=win)
        tr = ds.window_transform(win)
    rr, cc = np.where(arr == BUILT_UP)
    lon = tr.c + (cc + 0.5) * tr.a
    lat = tr.f + (rr + 0.5) * tr.e
    x, y = to5179.transform(lon, lat)
    midlat = (S + N) / 2
    px_m2 = abs(tr.a * 110320.0 * np.cos(np.radians(midlat))) * abs(tr.e * 110574.0)
    return np.column_stack([x, y]), float(px_m2), bool(covers)


def origin_mask(XY: np.ndarray, haz: np.ndarray, extent, p_cut: float) -> np.ndarray:
    """The committed 459-series origin filter, minus the stride."""
    xmin, ymin, xmax, ymax, cell = extent
    core = haz[0] >= 0.5
    rr, _cc = np.where(core)
    ign_y = float(ymax - (rr.mean() + 0.5) * cell)
    band = 0.45 * (ymax - ymin)
    nrows, ncols = haz[0].shape
    col = np.floor((XY[:, 0] - xmin) / cell).astype(int)
    row = np.floor((ymax - XY[:, 1]) / cell).astype(int)
    ok = (col >= 0) & (col < ncols) & (row >= 0) & (row < nrows)
    p0 = np.zeros(len(XY), np.float32)
    p0[ok] = haz[0][row[ok], col[ok]]
    return (p0 < p_cut) & (np.abs(XY[:, 1] - ign_y) <= band)


def measure(region: str, p_cut: float) -> dict:
    from scipy.spatial import cKDTree

    bbox = (_cfg("bbox.multi_region_walk_bbox", {}) or {})[region]
    bld = load_buildings(region, repo=REPO)
    node_ids, node_xy, node_crs = load_walk_nodes(region, repo=REPO)

    rec: dict = {
        "region": region, "walk_bbox_wsen": list(bbox),
        "source": bld.source, "source_file": bld.source_file,
        "walk_graphml_crs_as_stored": node_crs,
        "n_walk_nodes": int(len(node_ids)),
        "n_buildings": int(len(bld.xy)),
    }
    if not len(bld.xy):
        rec["note"] = "no buildings in this region's layer"
        return rec

    rec["footprint_area_m2"] = {
        "total": float(bld.area_m2.sum()), "median": float(np.median(bld.area_m2)),
        "mean": float(bld.area_m2.mean()), "p90": float(np.percentile(bld.area_m2, 90)),
        "max": float(bld.area_m2.max()),
    }
    rec["building_tag_values"] = bld.tag_counts

    # --- snap ---------------------------------------------------------------
    tree = cKDTree(node_xy)
    dist, idx = tree.query(bld.xy, k=1)
    rec["snap_distance"] = _pcts(dist)

    caps = {}
    for cap in CAPS_M:
        keep = dist <= cap
        n_ex = int((~keep).sum())
        node_idx = idx[keep]
        uniq, counts = (np.unique(node_idx, return_counts=True)
                        if len(node_idx) else (np.array([], int), np.array([], int)))
        entry = {
            "kept": int(keep.sum()), "excluded": n_ex,
            "excluded_pct": round(100.0 * n_ex / len(dist), 2),
            "distinct_walk_nodes": int(len(uniq)),
            "distinct_nodes_pct_of_graph": round(100.0 * len(uniq) / len(node_ids), 2),
        }
        if len(counts):
            entry["buildings_per_node"] = {
                "median": float(np.median(counts)), "mean": float(counts.mean()),
                "p95": float(np.percentile(counts, 95)), "max": int(counts.max()),
                "nodes_with_more_than_one": int((counts > 1).sum()),
            }
        # Is the exclusion spatially concentrated, or spread out?
        if n_ex:
            ex = bld.xy[~keep]
            entry["excluded_spatial"] = {
                "x_range_km": round(float(np.ptp(ex[:, 0])) / 1000.0, 2),
                "y_range_km": round(float(np.ptp(ex[:, 1])) / 1000.0, 2),
                "centroid_offset_from_all_km": round(float(np.hypot(
                    *(ex.mean(axis=0) - bld.xy.mean(axis=0)))) / 1000.0, 2),
                "median_nn_distance_m": _median_nn(ex),
            }
        caps[f"{int(cap)}m"] = entry
    rec["snap_caps"] = caps

    # --- how many survive the ORIGIN filter, per cap -------------------------
    z = np.load(HAZ[region])
    haz = z["haz_stack"].astype(np.float32)
    extent = [float(v) for v in z["grid_extent"]]
    om = origin_mask(bld.xy, haz, extent, p_cut)
    rec["origin_filter"] = {
        "p_cut": p_cut,
        "buildings_passing": int(om.sum()),
        "buildings_rejected": int((~om).sum()),
    }
    for cap in CAPS_M:
        keep = (dist <= cap) & om
        uniq = np.unique(idx[keep]) if keep.any() else np.array([], int)
        rec["snap_caps"][f"{int(cap)}m"]["routable_buildings"] = int(keep.sum())
        rec["snap_caps"][f"{int(cap)}m"]["routable_distinct_nodes"] = int(len(uniq))

    # --- how much settlement does this layer actually represent? -------------
    px, px_m2, covers = builtup_pixels(FUEL[region], bbox)
    rec["worldcover_builtup"] = {
        "raster_covers_whole_bbox": covers,
        "pixels": int(len(px)), "area_km2": round(len(px) * px_m2 / 1e6, 2),
        "note": ("ESA WorldCover class 50 inside the walk bbox, from the "
                 "committed fuel raster. Used as an independent statement of "
                 "where settlement is — NOT as a building count."),
    }
    if len(px):
        d_b, _ = cKDTree(bld.xy).query(px, k=1)
        rec["worldcover_builtup"]["builtup_pixel_to_nearest_building_m"] = _pcts(d_b)
        rec["worldcover_builtup"]["builtup_area_within_m_of_a_building_pct"] = {
            f"{t}m": round(100.0 * float((d_b <= t).mean()), 2)
            for t in (100, 250, 500, 1000, 2000)
        }
    # Concentration: what share of the bbox's settlement is anywhere near the
    # mapped buildings? A layer of 124 polygons all inside one town describes
    # one town, not a region.
    rec["mapped_extent"] = {
        "building_x_range_km": round(float(np.ptp(bld.xy[:, 0])) / 1000.0, 2),
        "building_y_range_km": round(float(np.ptp(bld.xy[:, 1])) / 1000.0, 2),
        "walk_node_x_range_km": round(float(np.ptp(node_xy[:, 0])) / 1000.0, 2),
        "walk_node_y_range_km": round(float(np.ptp(node_xy[:, 1])) / 1000.0, 2),
    }
    return rec


def _median_nn(pts: np.ndarray) -> float:
    from scipy.spatial import cKDTree
    if len(pts) < 2:
        return float("nan")
    d, _ = cKDTree(pts).query(pts, k=2)
    return float(np.median(d[:, 1]))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--regions", nargs="+", default=list(REGIONS))
    ap.add_argument("--p-cut", type=float, default=0.30)
    ap.add_argument("--out",
                    default=str(REPO / "data/processed/building_snapping_measurement.json"))
    args = ap.parse_args()

    out = {
        "schema_version": 1,
        "phase": "PHASE 18 STEP 1 — snapping measurement, NO routing, NO sampling",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _git(), "config_hash": config_hash(),
        "snap_caps_measured_m": list(CAPS_M),
        "regions": [measure(r, args.p_cut) for r in args.regions],
    }
    Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")

    for r in out["regions"]:
        print(f"\n=== {r['region']} ===")
        print(f"  buildings {r['n_buildings']:,}   walk nodes {r['n_walk_nodes']:,}"
              f"   graphml crs as stored: {r['walk_graphml_crs_as_stored']}")
        if not r["n_buildings"]:
            continue
        s = r["snap_distance"]
        print(f"  snap distance  p50={s['p50_m']:.0f}  p90={s['p90_m']:.0f}"
              f"  p99={s['p99_m']:.0f}  max={s['max_m']:.0f} m")
        for cap, e in r["snap_caps"].items():
            bpn = e.get("buildings_per_node", {})
            print(f"    cap {cap:>5s}: kept {e['kept']:>5d}  excluded {e['excluded']:>4d}"
                  f" ({e['excluded_pct']:>5.2f} %)  distinct nodes {e['distinct_walk_nodes']:>5d}"
                  f"  routable {e.get('routable_buildings',0):>5d}"
                  f"  bldg/node med {bpn.get('median',0):.0f} max {bpn.get('max',0)}")
        w = r.get("worldcover_builtup", {})
        if "builtup_area_within_m_of_a_building_pct" in w:
            pc = w["builtup_area_within_m_of_a_building_pct"]
            print(f"  settlement (WorldCover {w['area_km2']} km2) within "
                  f"250 m of a mapped building: {pc['250m']} % ; "
                  f"1 km: {pc['1000m']} % ; 2 km: {pc['2000m']} %")
    print(f"\n-> {Path(args.out).relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
