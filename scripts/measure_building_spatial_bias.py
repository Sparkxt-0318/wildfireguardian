#!/usr/bin/env python
"""PHASE 18 — is the building layer village-centred, and does that explain the result?

THE QUESTION THIS EXISTS TO SETTLE
----------------------------------
Building origins give a LOWER future-aware-only share than the stride rule in all
three regions. Two explanations survive that observation, and they have opposite
consequences:

  (a) TERRAIN — real buildings genuinely sit where evacuation is easy, so the
      stride rule (which samples graph nodes, including remote ones) overstates
      risk; or
  (b) MAPPING — OSM maps the conspicuous, so its buildings sit in village cores
      and on trunk roads, and the isolated houses that are hardest to evacuate
      were never mapped at all.

Under (a) the building number is the better one. Under (b) it is biased toward
safety and must not be quoted as a household result.

THE DISCRIMINATING MEASUREMENT
------------------------------
ESA WorldCover class 50 (built-up) is an independent, uniformly-sampled statement
of WHERE SETTLEMENT IS. It is not a building count, but it is unbiased with
respect to what OSM mappers found interesting, which is exactly the bias in
question.

So compare, in the same units, over the same bbox:

    distance to the nearest walk node, for OSM buildings
    distance to the nearest walk node, for settlement (area-weighted)

If the two distributions agree, the mapped buildings represent settlement's
relationship to the road network and (a) is live. If settlement is systematically
FARTHER from the network than the mapped buildings are, then OSM has sampled the
road-adjacent subset and (b) is established — the shortfall is the part of
settlement the building layer cannot see.

Also reports, because the brief asked and because they are the same question from
other angles:

  * the complete fate of every building (routable / filtered / unsnappable), with
    the reason, so that nothing is unaccounted for;
  * 1 km quadrat concentration — Gini and top-decile share for buildings against
    the same statistic for settlement area;
  * how much settlement sits in quadrats with NO mapped building at all;
  * distance to the fire core, for buildings and for settlement.

Run:  python scripts/measure_building_spatial_bias.py
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

REGIONS = ("yeongdeok_2025", "uiseong_andong_2025", "uljin_samcheok_2022")
FUEL = {r: REPO / f"data/raw/firms_data/{r}_fuel.tif" for r in REGIONS}
HAZ = {
    "yeongdeok_2025": REPO / "data/processed/routing_demo_canonical.npz",
    "uiseong_andong_2025": REPO / "data/processed/hazard_uiseong_andong_2025.npz",
    "uljin_samcheok_2022": REPO / "data/processed/hazard_uljin_samcheok_2022.npz",
}
BUILT_UP = 50
QUADRAT_M = 1000.0


def _git() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _d(a: np.ndarray) -> dict:
    return {"n": int(len(a)),
            "p50_m": round(float(np.percentile(a, 50)), 1),
            "p75_m": round(float(np.percentile(a, 75)), 1),
            "p90_m": round(float(np.percentile(a, 90)), 1),
            "p95_m": round(float(np.percentile(a, 95)), 1),
            "p99_m": round(float(np.percentile(a, 99)), 1),
            "max_m": round(float(a.max()), 1),
            "mean_m": round(float(a.mean()), 1),
            "beyond_150m_pct": round(100.0 * float((a > 150).mean()), 2),
            "beyond_300m_pct": round(100.0 * float((a > 300).mean()), 2),
            "beyond_500m_pct": round(100.0 * float((a > 500).mean()), 2)}


def _gini(x: np.ndarray) -> float:
    if x.sum() <= 0:
        return float("nan")
    s = np.sort(x.astype(float))
    n = len(s)
    return float((2 * np.arange(1, n + 1) - n - 1).dot(s) / (n * s.sum()))


def settlement_points(region: str, bbox):
    """Built-up pixel centres in EPSG:5179, plus the ground area of one pixel."""
    import rasterio
    from rasterio.windows import from_bounds
    from pyproj import Transformer

    to5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
    W, S, E, N = bbox
    with rasterio.open(FUEL[region]) as ds:
        b = ds.bounds
        covers = (b.left <= W + 1e-9 and b.right >= E - 1e-9
                  and b.bottom <= S + 1e-9 and b.top >= N - 1e-9)
        win = from_bounds(max(W, b.left), max(S, b.bottom),
                          min(E, b.right), min(N, b.top), ds.transform)
        arr = ds.read(1, window=win)
        tr = ds.window_transform(win)
    rr, cc = np.where(arr == BUILT_UP)
    x, y = to5179.transform(tr.c + (cc + 0.5) * tr.a, tr.f + (rr + 0.5) * tr.e)
    mid = (S + N) / 2
    px_m2 = abs(tr.a * 110320.0 * np.cos(np.radians(mid))) * abs(tr.e * 110574.0)
    return np.column_stack([x, y]), float(px_m2), bool(covers)


def fire_core_xy(haz: np.ndarray, extent) -> np.ndarray:
    xmin, _ymin, _xmax, ymax, cell = extent
    rr, cc = np.where(haz[0] >= 0.5)
    return np.column_stack([xmin + (cc + 0.5) * cell, ymax - (rr + 0.5) * cell])


def measure(region: str, args) -> dict:
    from scipy.spatial import cKDTree

    bbox = (_cfg("bbox.multi_region_walk_bbox", {}) or {})[region]
    bld = load_buildings(region, source=args.source, repo=REPO)
    _ids, node_xy, _crs = load_walk_nodes(region, repo=REPO)
    z = np.load(HAZ[region])
    haz = z["haz_stack"].astype(np.float32)
    extent = [float(v) for v in z["grid_extent"]]
    xmin, ymin, xmax, ymax, cell = extent

    sett, px_m2, covers = settlement_points(region, bbox)
    node_tree = cKDTree(node_xy)

    # ---- THE DISCRIMINATING COMPARISON -----------------------------------
    d_bld, _ = node_tree.query(bld.xy, k=1)
    d_set, _ = node_tree.query(sett, k=1)
    rec: dict = {
        "region": region,
        "n_buildings": int(len(bld)),
        "settlement_pixels": int(len(sett)),
        "settlement_area_km2": round(len(sett) * px_m2 / 1e6, 2),
        "settlement_raster_covers_whole_bbox": covers,
        "distance_to_nearest_walk_node": {
            "osm_buildings": _d(d_bld),
            "settlement_area_weighted": _d(d_set),
            "interpretation": (
                "If OSM buildings were a fair sample of settlement, these two "
                "distributions would agree. Every metre by which settlement is "
                "farther is settlement the building layer does not represent."),
        },
    }
    for t in (150, 300, 500):
        rec["distance_to_nearest_walk_node"][f"gap_beyond_{t}m_pp"] = round(
            100.0 * float((d_set > t).mean() - (d_bld > t).mean()), 2)

    # ---- fate of every building ------------------------------------------
    ncore_r, ncore_c = np.where(haz[0] >= 0.5)
    ign_y = float(ymax - (ncore_r.mean() + 0.5) * cell)
    band = 0.45 * (ymax - ymin)
    nrows, ncols = haz[0].shape
    col = np.floor((bld.xy[:, 0] - xmin) / cell).astype(int)
    row = np.floor((ymax - bld.xy[:, 1]) / cell).astype(int)
    inside = (col >= 0) & (col < ncols) & (row >= 0) & (row < nrows)
    p0 = np.full(len(bld.xy), np.nan)
    p0[inside] = haz[0][row[inside], col[inside]]

    unsnap = d_bld > args.max_snap_m
    outside_grid = ~inside
    burning = inside & (p0 >= args.p_cut)
    out_band = np.abs(bld.xy[:, 1] - ign_y) > band
    routable = (~unsnap) & inside & (~burning) & (~out_band)
    # first matching reason wins, in the order the runner applies them
    rec["fate"] = {
        "routable": int(routable.sum()),
        "excluded_unsnappable_gt_cap": int(unsnap.sum()),
        "excluded_outside_hazard_grid": int((~unsnap & outside_grid).sum()),
        "excluded_already_at_p_ge_pcut_at_t0": int((~unsnap & burning).sum()),
        "excluded_outside_reach_band": int((~unsnap & inside & ~burning
                                            & out_band).sum()),
        "unclassified_after_routing": 0,
        "note": ("Every building is in exactly one row. `unclassified` is a "
                 "ROUTING bucket and is 0 in all three regions — an origin that "
                 "reaches classification always lands in one of the six defined "
                 "buckets."),
    }
    assert sum(v for k, v in rec["fate"].items() if isinstance(v, int)) == len(bld)

    # ---- village-centre concentration ------------------------------------
    def quad(xy):
        return (np.floor((xy[:, 0] - xmin) / QUADRAT_M).astype(int),
                np.floor((xy[:, 1] - ymin) / QUADRAT_M).astype(int))

    bq = set(zip(*[a.tolist() for a in quad(bld.xy)]))
    sq_i, sq_j = quad(sett)
    keys = np.array(list(zip(sq_i.tolist(), sq_j.tolist())), dtype=object)
    uniq_s, counts_s = np.unique([f"{i}_{j}" for i, j in zip(sq_i, sq_j)],
                                 return_counts=True)
    bcnt = {}
    for i, j in zip(*[a.tolist() for a in quad(bld.xy)]):
        bcnt[f"{i}_{j}"] = bcnt.get(f"{i}_{j}", 0) + 1
    b_per_quad = np.array([bcnt.get(k, 0) for k in uniq_s])
    settled_quads = len(uniq_s)
    empty = int((b_per_quad == 0).sum())
    area_in_empty = float(counts_s[b_per_quad == 0].sum() * px_m2)

    order = np.argsort(-b_per_quad)
    top10 = max(1, settled_quads // 10)
    rec["quadrat_1km"] = {
        "settled_quadrats": settled_quads,
        "quadrats_with_a_mapped_building": int((b_per_quad > 0).sum()),
        "quadrats_with_NO_mapped_building": empty,
        "quadrats_with_no_mapped_building_pct": round(100.0 * empty / settled_quads, 1),
        "settlement_area_in_those_quadrats_km2": round(area_in_empty / 1e6, 2),
        "settlement_area_in_those_quadrats_pct": round(
            100.0 * area_in_empty / (len(sett) * px_m2), 1),
        "gini_buildings_over_settled_quadrats": round(_gini(b_per_quad.astype(float)), 3),
        "gini_settlement_area_over_settled_quadrats": round(
            _gini(counts_s.astype(float)), 3),
        "top_decile_share_of_buildings_pct": round(
            100.0 * float(b_per_quad[order][:top10].sum()) / max(len(bld), 1), 1),
        "top_decile_share_of_settlement_area_pct": round(
            100.0 * float(np.sort(counts_s)[::-1][:top10].sum()) / len(sett), 1),
        "interpretation": (
            "A Gini for buildings well above the Gini for settlement area means "
            "the mapped buildings are concentrated into a few places that "
            "settlement itself is not concentrated into — village cores."),
    }
    _ = bq, keys

    # ---- nearest-neighbour spacing ---------------------------------------
    if len(bld) > 1:
        nn_b, _ = cKDTree(bld.xy).query(bld.xy, k=2)
        rec["nearest_neighbour_m"] = {
            "osm_buildings_p50": round(float(np.median(nn_b[:, 1])), 1),
            "osm_buildings_p90": round(float(np.percentile(nn_b[:, 1], 90)), 1),
        }

    # ---- distance to the fire core ---------------------------------------
    core = fire_core_xy(haz, extent)
    if len(core):
        ct = cKDTree(core)
        dc_b, _ = ct.query(bld.xy, k=1)
        dc_s, _ = ct.query(sett, k=1)
        rec["distance_to_fire_core_t0"] = {
            "osm_buildings": _d(dc_b),
            "settlement_area_weighted": _d(dc_s),
            "routable_buildings_p50_m": round(float(np.median(dc_b[routable])), 1)
            if routable.any() else None,
            "excluded_buildings_p50_m": round(float(np.median(dc_b[~routable])), 1)
            if (~routable).any() else None,
        }
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--regions", nargs="+", default=list(REGIONS))
    ap.add_argument("--source", default=_cfg("building_origins.source", "osm"))
    ap.add_argument("--max-snap-m", type=float,
                    default=float(_cfg("building_origins.max_snap_distance_m", 500.0)))
    ap.add_argument("--p-cut", type=float,
                    default=float(_cfg("pedestrian.walk_cutoff_p", 0.5)))
    ap.add_argument("--out",
                    default=str(REPO / "data/processed/building_spatial_bias.json"))
    args = ap.parse_args()

    regions = [measure(r, args) for r in args.regions]
    doc = {
        "schema_version": 1,
        "title": ("PHASE 18 — does the building layer represent settlement, or "
                  "only its road-adjacent, village-centre subset?"),
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _git(), "config_hash": config_hash(),
        "quadrat_size_m": QUADRAT_M,
        "regions": regions,
    }
    Path(args.out).write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")

    for r in regions:
        print(f"\n=== {r['region']}")
        f = r["fate"]
        print(f"  fate of {r['n_buildings']} buildings: routable {f['routable']} | "
              f"unsnappable {f['excluded_unsnappable_gt_cap']} | "
              f"off-grid {f['excluded_outside_hazard_grid']} | "
              f"burning@t0 {f['excluded_already_at_p_ge_pcut_at_t0']} | "
              f"out-of-band {f['excluded_outside_reach_band']} | "
              f"unclassified {f['unclassified_after_routing']}")
        d = r["distance_to_nearest_walk_node"]
        b, s = d["osm_buildings"], d["settlement_area_weighted"]
        print(f"  distance to nearest walk node")
        print(f"    OSM buildings   p50 {b['p50_m']:>6.0f}  p90 {b['p90_m']:>6.0f}"
              f"  >150m {b['beyond_150m_pct']:>5.1f}%  >500m {b['beyond_500m_pct']:>5.1f}%")
        print(f"    settlement      p50 {s['p50_m']:>6.0f}  p90 {s['p90_m']:>6.0f}"
              f"  >150m {s['beyond_150m_pct']:>5.1f}%  >500m {s['beyond_500m_pct']:>5.1f}%")
        print(f"    GAP beyond 150m: {d['gap_beyond_150m_pp']:+.1f} pp   "
              f"beyond 500m: {d['gap_beyond_500m_pp']:+.1f} pp")
        q = r["quadrat_1km"]
        print(f"  1 km quadrats: {q['settled_quadrats']} settled, "
              f"{q['quadrats_with_NO_mapped_building']} "
              f"({q['quadrats_with_no_mapped_building_pct']} %) hold NO mapped building"
              f" — {q['settlement_area_in_those_quadrats_pct']} % of settlement area")
        print(f"    Gini buildings {q['gini_buildings_over_settled_quadrats']} vs "
              f"settlement {q['gini_settlement_area_over_settled_quadrats']}; "
              f"top decile {q['top_decile_share_of_buildings_pct']} % of buildings vs "
              f"{q['top_decile_share_of_settlement_area_pct']} % of area")
    print(f"\n-> {Path(args.out).relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
