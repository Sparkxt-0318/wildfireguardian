#!/usr/bin/env python
"""PHASE 18 STEP 1 — route from BUILDING locations, three regions, one rule.

WHAT THIS COMPUTES, AND WHY IT IS A CENSUS RATHER THAN A SAMPLE
---------------------------------------------------------------
Buildings snap onto walk nodes many-to-one, so the number of distinct routing
problems is bounded by the graph, not by the building count. For the acquired
OSM layers that bound is 110 / 165 / 588 nodes — about 40 seconds of routing in
total. Sampling first would therefore save nothing and lose the exact answer.

So this routes the FULL routable building census, once per distinct node, and
then derives every sample-size result by RESAMPLING the census. The convergence
curve costs no extra routing, and the N-building answer is a subset of an exact
answer rather than an estimate of an unknown one.

⚠ THE STRIDE RULE IS UNTOUCHED. This writes new filenames and reads the
committed stride artifacts only to place them beside these numbers.

THE FOUR THINGS THAT ARE RECORDED RATHER THAN RESOLVED
------------------------------------------------------
* ``unsnappable`` — buildings with no walk node within ``max_snap_distance_m``.
  Listed individually with coordinates and distance. A building 1.7 km from the
  nearest mapped path is a statement about the network.
* ``origin_filter_rejected`` — buildings already at p >= p_cut at t=0, or outside
  the reach band. The committed 459-series rule, unchanged.
* ``infeasible`` sample sizes — an N larger than the region's routable census.
  Reported as infeasible, never clamped to the census size.
* ``buildings_per_node`` — the many-to-one multiplicity, kept per node, because
  it is the "how many buildings sit behind this dispatch point" proxy.

Run:  python scripts/run_building_origin_routing.py
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from wildfireguardian.buildings import load_buildings, load_walk_nodes  # noqa: E402
from wildfireguardian.config import config_hash, get as _cfg  # noqa: E402
from wildfireguardian.routing.slope import (  # noqa: E402
    build_walk_network, load_snapshot_graph,
)

from run_multi_region_routing import (  # noqa: E402
    CATEGORIES, classify, read_poi_snapshot, snapshot_for,
)

REGIONS = ("yeongdeok_2025", "uiseong_andong_2025", "uljin_samcheok_2022")

#: Per-region hazard field. Yeongdeok is NOT ``hazard_yeongdeok_2025.npz`` — it
#: has none. Its field is the CANONICAL one, and it must never be
#: ``routing_demo.npz``, which is the output of a reverted run
#: (HANDOFF_ROUND3.md §2-A, rule 20). ``run_multi_region_routing.load_hazard``
#: refuses Yeongdeok by design, so this mapping is stated here explicitly rather
#: than inherited.
HAZARD_NPZ = {
    "yeongdeok_2025": "data/processed/routing_demo_canonical.npz",
    "uiseong_andong_2025": "data/processed/hazard_uiseong_andong_2025.npz",
    "uljin_samcheok_2022": "data/processed/hazard_uljin_samcheok_2022.npz",
}


def load_hazard(region: str):
    """``(HazardSequence, haz, extent, sha256, path)`` for any of the three."""
    import hashlib

    from wildfireguardian.routing.hazard import HazardSequence
    from wildfireguardian.spread_v2.grid import CoarseGrid

    p = REPO / HAZARD_NPZ[region]
    if "routing_demo.npz" in str(p):  # belt and braces against rule 20
        raise RuntimeError("routing_demo.npz is a reverted run's output")
    z = np.load(p)
    haz = z["haz_stack"].astype(np.float32)
    times = np.asarray(z["haz_times"], float)
    xmin, ymin, xmax, ymax, cell = [float(v) for v in z["grid_extent"]]
    grid = CoarseGrid(minx=xmin, miny=ymin, maxx=xmax, maxy=ymax,
                      cell_size_m=cell, nrows=haz.shape[1], ncols=haz.shape[2])
    hazard = HazardSequence(grid=grid, times_min=times,
                            surfaces=[haz[i] for i in range(haz.shape[0])])
    return (hazard, haz, (xmin, ymin, xmax, ymax, cell),
            hashlib.sha256(p.read_bytes()).hexdigest(), p)

#: The committed stride arm each building arm is placed beside. The headline arm
#: is the slope DiGraph one, which is what these runs also use.
STRIDE_ARTIFACT = {
    "yeongdeok_2025": ("real_roads_real_hazard_canonical.json",
                       "arms.slope_digraph_canonical"),
    "uiseong_andong_2025": ("real_roads_real_hazard_uiseong_andong_2025.json",
                            "arms.slope_digraph_canonical"),
    "uljin_samcheok_2022": ("real_roads_real_hazard_uljin_samcheok_2022.json",
                            "arms.slope_digraph_canonical"),
}


def _git() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _dig(doc: dict, dotted: str):
    cur = doc
    for part in dotted.split("."):
        cur = cur[part]
    return cur


def stride_reference(region: str) -> dict:
    fname, path = STRIDE_ARTIFACT[region]
    p = REPO / "data/processed" / fname
    if not p.exists():
        return {"available": False, "artifact": fname}
    arm = _dig(json.loads(p.read_text(encoding="utf-8")), path)
    c = arm["counts"]
    n = arm["n_origins_scanned"]
    return {"available": True, "artifact": fname, "arm": path,
            "n_origins": n, "counts": c,
            "fa_only_pct": round(100.0 * c["naive_into_FA_safe"] / max(n, 1), 2)}


def origin_filter(XY: np.ndarray, haz: np.ndarray, extent, p_cut: float):
    """The committed 459-series origin rule, applied to arbitrary points."""
    xmin, ymin, xmax, ymax, cell = extent
    core = haz[0] >= 0.5
    rr, cc = np.where(core)
    ign_y = float(ymax - (rr.mean() + 0.5) * cell)
    ign_x = float(xmin + (cc.mean() + 0.5) * cell)
    band = 0.45 * (ymax - ymin)
    nrows, ncols = haz[0].shape
    col = np.floor((XY[:, 0] - xmin) / cell).astype(int)
    row = np.floor((ymax - XY[:, 1]) / cell).astype(int)
    ok = (col >= 0) & (col < ncols) & (row >= 0) & (row < nrows)
    p0 = np.zeros(len(XY), np.float32)
    p0[ok] = haz[0][row[ok], col[ok]]
    keep = (p0 < p_cut) & (np.abs(XY[:, 1] - ign_y) <= band)
    return keep, (ign_x, ign_y), band


def convergence(bucket_of_building: np.ndarray, sizes, repeats, seed) -> list[dict]:
    """Resample the census at each N and report the spread of each bucket share.

    ⚠ This measures SAMPLING noise around a known census. It cannot measure how
    well the census represents the region's real buildings — that is the OSM
    coverage question, reported separately and separately caveated.
    """
    rng = np.random.default_rng(seed)
    total = len(bucket_of_building)
    out = []
    for N in sizes:
        if N > total:
            out.append({"n": int(N), "feasible": False,
                        "reason": f"census has {total} routable buildings"})
            continue
        shares = {k: np.empty(repeats) for k in CATEGORIES}
        for r in range(repeats):
            pick = rng.choice(total, size=N, replace=False)
            b = bucket_of_building[pick]
            for i, k in enumerate(CATEGORIES):
                shares[k][r] = float((b == i).mean())
        entry = {"n": int(N), "feasible": True, "repeats": int(repeats)}
        for k in CATEGORIES:
            s = shares[k]
            if s.max() == 0.0:
                continue
            entry[k] = {"mean_pct": round(100 * float(s.mean()), 3),
                        "sd_pct": round(100 * float(s.std(ddof=1)), 3),
                        "p2.5_pct": round(100 * float(np.percentile(s, 2.5)), 3),
                        "p97.5_pct": round(100 * float(np.percentile(s, 97.5)), 3),
                        "half_ci95_pp": round(
                            100 * float(np.percentile(s, 97.5)
                                        - np.percentile(s, 2.5)) / 2, 3)}
        out.append(entry)
    return out


def spatial_bias(xy: np.ndarray, sizes, repeats, seed) -> list[dict]:
    """Does a uniform draw of N move the spatial distribution off the census?

    Reported even though the expected answer is "no": a null that was measured
    is worth more than an assumption that was not. The bias that DOES exist is
    census-vs-region, not sample-vs-census, and lives in
    ``building_snapping_measurement.json``.
    """
    rng = np.random.default_rng(seed + 1)
    total, cen = len(xy), xy.mean(axis=0)
    sd = xy.std(axis=0)
    out = []
    for N in sizes:
        if N > total:
            out.append({"n": int(N), "feasible": False})
            continue
        off, sdr = np.empty(repeats), np.empty(repeats)
        for r in range(repeats):
            s = xy[rng.choice(total, size=N, replace=False)]
            off[r] = float(np.hypot(*(s.mean(axis=0) - cen)))
            sdr[r] = float(np.mean(s.std(axis=0) / np.where(sd == 0, 1, sd)))
        out.append({
            "n": int(N), "feasible": True,
            "centroid_offset_m": {"mean": round(float(off.mean()), 1),
                                  "p95": round(float(np.percentile(off, 95)), 1),
                                  "max": round(float(off.max()), 1)},
            "spread_ratio_vs_census": {"mean": round(float(sdr.mean()), 4),
                                       "p05": round(float(np.percentile(sdr, 5)), 4),
                                       "p95": round(float(np.percentile(sdr, 95)), 4)},
        })
    return out


def run_region(region: str, args) -> dict:
    print(f"\n{'=' * 70}\n=== {region}\n{'=' * 70}")
    t0 = time.monotonic()

    bld = load_buildings(region, source=args.source, repo=REPO)
    _ids, node_xy, node_crs = load_walk_nodes(region, repo=REPO)
    hazard, haz, extent, npz_sha, npz_path = load_hazard(region)

    G = load_snapshot_graph(snapshot_for(region, "walk"))
    dem = REPO / f"data/raw/firms_data/{region}_dem.tif"
    net, slope_stats = build_walk_network(
        G, dem, sampling_m=args.sampling_m, max_abs_slope=args.max_abs_slope,
        directed=True, apply_slope=True)
    dests, n_shelter = read_poi_snapshot(snapshot_for(region, "shelters"),
                                         kind="shelter")
    if not dests:
        raise RuntimeError("GATE A: zero refuges — not writing output")
    net.shelters = {net.nearest_node(d.x, d.y) for d in dests}

    # -- snap ---------------------------------------------------------------
    # net.nearest_node is the routing layer's own snapper: using anything else
    # would let the measured snap distance and the routed origin disagree.
    n_bld = len(bld)
    snap_node, snap_dist = [], np.empty(n_bld)
    for i in range(n_bld):
        x, y = float(bld.xy[i, 0]), float(bld.xy[i, 1])
        nid = net.nearest_node(x, y)
        nx_, ny_ = net.node_xy(nid)
        snap_node.append(nid)
        snap_dist[i] = float(np.hypot(nx_ - x, ny_ - y))
    snap_node = np.array(snap_node)

    within = snap_dist <= args.max_snap_m
    unsnap_idx = np.where(~within)[0]
    unsnappable = [{
        "building_id": bld.ids[int(i)],
        "centroid_5179": [round(float(bld.xy[i, 0]), 1), round(float(bld.xy[i, 1]), 1)],
        "nearest_walk_node_distance_m": round(float(snap_dist[i]), 1),
        "footprint_area_m2": round(float(bld.area_m2[i]), 1),
    } for i in unsnap_idx]

    keep_of, ign, band = origin_filter(bld.xy, haz, extent, args.p_cut)
    routable = within & keep_of
    n_routable = int(routable.sum())
    print(f"buildings {n_bld}  -> within {int(args.max_snap_m)} m: {int(within.sum())}"
          f"  -> after origin filter: {n_routable}"
          f"   (unsnappable {len(unsnappable)}, "
          f"filtered {int((within & ~keep_of).sum())})")

    if not n_routable:
        return {"region": region, "n_buildings": n_bld, "n_routable": 0,
                "unsnappable": unsnappable,
                "note": "no routable buildings — nothing routed"}

    # -- route ONCE per distinct node ---------------------------------------
    r_idx = np.where(routable)[0]
    r_nodes = snap_node[r_idx]
    uniq, inverse, counts = np.unique(r_nodes, return_inverse=True,
                                      return_counts=True)
    print(f"distinct walk nodes to route: {len(uniq)} "
          f"(buildings/node median {np.median(counts):.0f}, max {counts.max()})")
    t_route = time.monotonic()
    node_counts, node_classes = classify(net, [int(n) for n in uniq], hazard,
                                         args.p_cut, args.time_budget_min,
                                         args.time_step_min)
    route_s = time.monotonic() - t_route
    print(f"  routed {len(uniq)} nodes in {route_s:.1f}s "
          f"({route_s / max(len(uniq),1) * 1000:.0f} ms/node)")

    # -- attribute each building its node's bucket --------------------------
    cat_index = {k: i for i, k in enumerate(CATEGORIES)}
    node_bucket = np.full(len(uniq), cat_index["unclassified"], dtype=int)
    pos = {int(n): i for i, n in enumerate(uniq)}
    for k, members in node_classes.items():
        for n in members:
            node_bucket[pos[int(n)]] = cat_index[k]
    bld_bucket = node_bucket[inverse]

    bcounts = {k: int((bld_bucket == cat_index[k]).sum()) for k in CATEGORIES}
    print(f"  BUILDING-level: both_safe={bcounts['both_safe']} "
          f"FA_only={bcounts['naive_into_FA_safe']} "
          f"no_safe={bcounts['no_safe_route']}")

    # -- per-node multiplicity, kept -----------------------------------------
    inv_cat = {v: k for k, v in cat_index.items()}
    per_node = [{"walk_node": int(uniq[i]), "n_buildings": int(counts[i]),
                 "bucket": inv_cat[int(node_bucket[i])]}
                for i in range(len(uniq))]
    per_node.sort(key=lambda r: -r["n_buildings"])

    sizes = list(args.sizes)
    rec = {
        "region": region,
        "rule": {
            "source": bld.source, "source_file": bld.source_file,
            "max_snap_distance_m": args.max_snap_m,
            "p_cut": args.p_cut, "time_budget_min": args.time_budget_min,
            "time_step_min": args.time_step_min,
            "slope_sampling_m": args.sampling_m, "max_abs_slope": args.max_abs_slope,
            "arm": "slope DiGraph — the same arm the committed stride headline uses",
            "snapper": "net.nearest_node (the routing layer's own)",
            "walk_graphml_crs_as_stored": node_crs,
        },
        "n_buildings": int(n_bld),
        "n_within_snap_cap": int(within.sum()),
        "n_unsnappable": len(unsnappable),
        "n_origin_filtered": int((within & ~keep_of).sum()),
        "n_routable": n_routable,
        "snap_distance_m": {
            "median": round(float(np.median(snap_dist)), 1),
            "p90": round(float(np.percentile(snap_dist, 90)), 1),
            "p99": round(float(np.percentile(snap_dist, 99)), 1),
            "max": round(float(snap_dist.max()), 1),
            "note": "measured with net.nearest_node over ALL buildings, pre-cap",
        },
        "unsnappable": unsnappable,
        "distinct_walk_nodes_routed": int(len(uniq)),
        "buildings_per_node": {
            "median": float(np.median(counts)), "mean": round(float(counts.mean()), 3),
            "p95": float(np.percentile(counts, 95)), "max": int(counts.max()),
            "nodes_with_more_than_one": int((counts > 1).sum()),
        },
        "per_node": per_node,
        "node_level_counts": node_counts,
        "building_level_counts": bcounts,
        "building_fa_only_pct": round(100.0 * bcounts["naive_into_FA_safe"]
                                      / max(n_routable, 1), 2),
        "routing_seconds": round(route_s, 1),
        "hazard_npz": str(npz_path.relative_to(REPO)), "hazard_npz_sha256": npz_sha,
        "n_shelter_pois": n_shelter,
        "slope_stats": slope_stats.as_dict() if slope_stats is not None else None,
        "ignition_proxy_xy_5179": [ign[0], ign[1]], "reach_band_m": band,
        "convergence": convergence(bld_bucket, sizes, args.repeats, args.seed),
        "spatial_bias_of_sampling": spatial_bias(bld.xy[r_idx], sizes,
                                                 min(args.repeats, 200), args.seed),
        "stride_reference": stride_reference(region),
        "region_seconds": round(time.monotonic() - t0, 1),
    }
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--regions", nargs="+", default=list(REGIONS))
    ap.add_argument("--source", default=_cfg("building_origins.source", "osm"))
    ap.add_argument("--max-snap-m", type=float,
                    default=float(_cfg("building_origins.max_snap_distance_m", 500.0)))
    ap.add_argument("--seed", type=int,
                    default=int(_cfg("building_origins.sample_seed", 20260805)))
    ap.add_argument("--sizes", type=int, nargs="+",
                    default=list(_cfg("building_origins.convergence_sample_sizes",
                                      [50, 100, 250, 500, 1000, 2000])))
    ap.add_argument("--repeats", type=int,
                    default=int(_cfg("building_origins.convergence_repeats", 400)))
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
    ap.add_argument("--out",
                    default=str(REPO / "data/processed/building_origin_routing.json"))
    args = ap.parse_args()

    started = time.monotonic()
    regions = [run_region(r, args) for r in args.regions]
    doc = {
        "schema_version": 1,
        "title": "PHASE 18 — building-location origins, three regions, one rule",
        "series_note": (
            "This is a SECOND origin rule beside the committed stride-18 rule, "
            "not a replacement for it. The stride rule samples the walk graph; "
            "this one enumerates buildings. They count different things. Every "
            "table that shows one must show the other, and neither is the "
            "corrected version of the other."),
        "coverage_warning": (
            "⚠ The OSM building layer covers a SMALL and REGION-DEPENDENT "
            "fraction of the real building stock (measured: 124 / 339 / 1,220 "
            "against a STEP-0 estimate of 1.5-6 man per bbox). Comparing these "
            "three regions on any building-derived rate without the mapping- "
            "coverage column repeats exactly the confound HANDOFF_ROUND3.md §5 "
            "rules 7 and 12 forbid."),
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _git(), "config_hash": config_hash(),
        "total_seconds": round(time.monotonic() - started, 1),
        "regions": regions,
    }
    Path(args.out).write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")
    print(f"\n-> {Path(args.out).relative_to(REPO)}  "
          f"({doc['total_seconds']:.0f}s total)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
