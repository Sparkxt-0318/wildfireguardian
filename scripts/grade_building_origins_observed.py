#!/usr/bin/env python
"""Building-origin routes (WFG-275 population) graded against the observed FIRMS footprint,
plus a diagnosis of every no-safe-route node. Rules: docs/building_origins_observed_grading.md
(pre-registered). Writes data/processed/building_origins_observed_grading_yeongdeok.json and
appends §4 to the doc. Nothing committed is modified.

    python scripts/grade_building_origins_observed.py
"""
from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from wildfireguardian.buildings import load_buildings  # noqa: E402
from wildfireguardian.routing.evacuation import (  # noqa: E402
    _time_to_cutoff, future_aware_route, naive_route,
)
from wildfireguardian.routing.rescue import RescueConfig, rescuer_reachable  # noqa: E402
from wildfireguardian.routing.slope import build_walk_network, load_snapshot_graph  # noqa: E402

from regrade_three_way import classify_route, first_seen_grid  # noqa: E402
from run_building_origin_routing import load_hazard, origin_filter  # noqa: E402
from run_multi_region_routing import read_poi_snapshot, snapshot_for  # noqa: E402
from run_real_roads_real_hazard_slope import REAL_OSM_SCAN_STRIDE  # noqa: E402
from run_rescue_routing_full import materialise_snapshots  # noqa: E402
from run_rescue_routing_real_hazard import build_scenario  # noqa: E402

OUT = REPO / "data/processed/building_origins_observed_grading_yeongdeok.json"
DOC = REPO / "docs/building_origins_observed_grading.md"
REGION = "yeongdeok_2025"
MAX_SNAP, P_CUT, BUDGET, STEP = 500.0, 0.5, 600.0, 10.0
SAMPLING_M, MAX_SLOPE = 60.0, 0.6
CLASSES = ["admissible_all", "indeterminate", "inadmissible_all", "unsupported", "not_reached"]


def dilate(fs):
    """First-seen grid where every cell within one cell of a detected cell inherits the
    earliest first_seen of its detected neighbours (A4 sensitivity)."""
    out = fs.copy()
    R, C = fs.shape
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            sh = np.full_like(fs, np.inf)
            r0, r1 = max(0, dr), min(R, R + dr); c0, c1 = max(0, dc), min(C, C + dc)
            sh[r0:r1, c0:c1] = fs[r0 - dr:r1 - dr, c0 - dc:c1 - dc]
            out = np.minimum(out, sh)
    return out


def cell_of(grid, x, y):
    col = int(math.floor((x - grid.minx) / grid.cell_size_m)); row = int(math.floor((grid.maxy - y) / grid.cell_size_m))
    return row, col


def main() -> int:
    t0 = time.monotonic()
    bld = load_buildings(REGION, source="juso_main", repo=REPO)
    hazard, haz, extent, npz_sha, npz_path = load_hazard(REGION)
    z = np.load(npz_path); fs, obs_t = first_seen_grid(z); fs_dil = dilate(fs)
    G = load_snapshot_graph(snapshot_for(REGION, "walk"))
    net, _ = build_walk_network(G, REPO / f"data/raw/firms_data/{REGION}_dem.tif", sampling_m=SAMPLING_M,
                                max_abs_slope=MAX_SLOPE, directed=True, apply_slope=True)
    dests, _ = read_poi_snapshot(snapshot_for(REGION, "shelters"), kind="shelter")
    net.shelters = {net.nearest_node(d.x, d.y) for d in dests}
    grid = hazard.grid

    # snap + filter, exactly as WFG-275
    n_bld = len(bld); snap_node = np.empty(n_bld, dtype=object); snap_dist = np.empty(n_bld)
    for i in range(n_bld):
        x, y = float(bld.xy[i, 0]), float(bld.xy[i, 1]); nid = net.nearest_node(x, y); nx_, ny_ = net.node_xy(nid)
        snap_node[i] = nid; snap_dist[i] = math.hypot(nx_ - x, ny_ - y)
    within = snap_dist <= MAX_SNAP
    keep, ign, band = origin_filter(bld.xy, haz, extent, P_CUT)
    routable = within & keep
    r_idx = np.where(routable)[0]; r_nodes = snap_node[r_idx]
    uniq, inverse, counts = np.unique(r_nodes.astype(np.int64), return_inverse=True, return_counts=True)
    w_of = {int(n): int(c) for n, c in zip(uniq, counts)}
    print(f"buildings {n_bld} within {int(within.sum())} routable {len(r_idx)} nodes {len(uniq)}", flush=True)

    # route once per node; grade on forecast and observation
    rows = {}
    for k, n in enumerate(uniq):
        n = int(n)
        nv = naive_route(net, n, hazard, departure_min=0.0, p_cut=P_CUT, objective="length_m")
        fa = future_aware_route(net, n, hazard, departure_min=0.0, time_budget_min=BUDGET, p_cut=P_CUT, time_step_min=STEP)
        if nv.reached and nv.enters_hazard and fa.reached and not fa.enters_hazard: b = "naive_into_FA_safe"
        elif nv.reached and nv.enters_hazard and not fa.reached: b = "no_safe_route"
        elif nv.reached and not nv.enters_hazard and fa.reached and not fa.enters_hazard: b = "both_safe"
        else: b = "other"
        row = {"node": n, "n_buildings": w_of[n], "forecast_bucket": b}
        for arm, r in (("fire_blind", nv), ("forecast_aware", fa)):
            if not r.reached or r.total_time_min > BUDGET:
                row[arm] = {"forecast_reached": bool(r.reached), "class": "not_reached", "class_dilated": "not_reached"}
            else:
                c = classify_route(net, list(r.route), fs, obs_t, grid); cd = classify_route(net, list(r.route), fs_dil, obs_t, grid)
                # A4 sensitivity as pre-registered: a neighbour-of-detected cell is POSSIBLY affected,
                # so a touch there can make a route indeterminate, never inadmissible.
                # (The first run, 2026-09-13T06:07Z, let it read as inadmissible; corrected before the rerun.)
                dil = cd["class_m0"]
                if dil == "inadmissible_all" and c["class_m0"] != "inadmissible_all":
                    dil = "indeterminate"
                row[arm] = {"forecast_reached": True, "forecast_enters": bool(r.enters_hazard), "time_min": round(r.total_time_min, 1),
                            "class": c["class_m0"], "class_dilated": dil}
        rows[n] = row
        if (k + 1) % 500 == 0: print(f"  [{k+1}/{len(uniq)}] {time.monotonic()-t0:.0f}s", flush=True)
    fb = {k: v for k, v in rows.items()}
    fc = {"naive_into_FA_safe": 0, "no_safe_route": 0, "both_safe": 0, "other": 0}
    for r in rows.values(): fc[r["forecast_bucket"]] += 1

    def tally(arm, key, weighted):
        out = {c: 0 for c in CLASSES}
        for r in rows.values(): out[r[arm][key]] += (r["n_buildings"] if weighted else 1)
        return out
    def paired(key, weighted):
        tab = {}
        for r in rows.values():
            k = f"{r['fire_blind'][key]}|{r['forecast_aware'][key]}"; tab[k] = tab.get(k, 0) + (r["n_buildings"] if weighted else 1)
        return dict(sorted(tab.items()))
    summary = {lvl: {arm: {"a4_base": tally(arm, "class", w), "a4_dilated": tally(arm, "class_dilated", w)} for arm in ("fire_blind", "forecast_aware")}
               for lvl, w in (("nodes", False), ("buildings", True))}
    summary["paired"] = {lvl: {"a4_base": paired("class", w), "a4_dilated": paired("class_dilated", w)} for lvl, w in (("nodes", False), ("buildings", True))}
    fa_only = [r for r in rows.values() if r["forecast_bucket"] == "naive_into_FA_safe"]
    summary["forecast_only"] = {lvl: {key: {c: sum((r["n_buildings"] if w else 1) for r in fa_only if r["forecast_aware"][key] == c) for c in CLASSES}
                                      for key in ("class", "class_dilated")} for lvl, w in (("nodes", False), ("buildings", True))}

    # ---- diagnosis of no_safe_route nodes ------------------------------------------
    tmp = Path(tempfile.mkdtemp(prefix="wfg-bo-"))
    try:
        materialise_snapshots(tmp / REGION)
        cfg = RescueConfig(use_osm=True, osm_cache_dir=str(tmp), scan_stride=REAL_OSM_SCAN_STRIDE)
        sc = build_scenario(cfg)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    depot_nodes = [sc.drive.nearest_node(d.x, d.y) for d in sc.depots]
    cfg75 = replace(cfg, responder_time_budget_min=75.0, responder_dispatch_delay_min=30.0)
    diag = []
    nsr = [r for r in rows.values() if r["forecast_bucket"] == "no_safe_route"]
    for r in nsr:
        n = r["node"]; x, y = net.node_xy(n)
        b_idx = [int(i) for i in r_idx[np.where(r_nodes.astype(np.int64) == n)[0]]]
        dists = [float(snap_dist[i]) for i in b_idx]
        nv = naive_route(net, n, hazard, departure_min=0.0, p_cut=P_CUT, objective="length_m")
        t_origin = _time_to_cutoff(hazard, x, y, P_CUT)
        first_haz = next(((i, nv.arrival_times_min[i]) for i, h in enumerate(nv.node_hazard) if h >= P_CUT), (None, None))
        fa900 = future_aware_route(net, n, hazard, departure_min=0.0, time_budget_min=900.0, p_cut=P_CUT, time_step_min=STEP)
        fa1200 = future_aware_route(net, n, hazard, departure_min=0.0, time_budget_min=1200.0, p_cut=P_CUT, time_step_min=STEP)
        fa07 = future_aware_route(net, n, hazard, departure_min=0.0, time_budget_min=BUDGET, p_cut=0.7, time_step_min=STEP)
        rr, cc = cell_of(grid, x, y)
        origin_first_seen = float(fs[rr, cc]) if 0 <= rr < fs.shape[0] and 0 <= cc < fs.shape[1] else None
        hd = sc.drive.nearest_node(x, y); hx, hy = sc.drive.node_xy(hd)
        reach, rt, dep = rescuer_reachable(sc.drive, depot_nodes, hd, sc.hazard, cfg75)
        d = {"node": n, "n_buildings": r["n_buildings"], "snap_m_median": round(float(np.median(dists)), 1), "snap_m_max": round(max(dists), 1),
             "buildings_over_200m": sum(1 for v in dists if v > 200),
             "fire_blind_reached": bool(nv.reached), "fire_blind_time_min": round(nv.total_time_min, 1), "fire_blind_distance_m": round(nv.total_distance_m, 0),
             "origin_forecast_cutoff_min": (None if math.isinf(t_origin) else t_origin),
             "first_hazard_node_index": first_haz[0], "first_hazard_time_min": (None if first_haz[1] is None else round(first_haz[1], 1)),
             "fa_900_reached": bool(fa900.reached and not fa900.enters_hazard), "fa_1200_reached": bool(fa1200.reached and not fa1200.enters_hazard),
             "fa_pcut07_reached": bool(fa07.reached and not fa07.enters_hazard),
             "fire_blind_observed_class": r["fire_blind"]["class"], "fire_blind_observed_class_dilated": r["fire_blind"]["class_dilated"],
             "origin_cell_first_seen_min": (None if origin_first_seen is None or math.isinf(origin_first_seen) else origin_first_seen),
             "vehicle_reachable_W75": bool(reach), "vehicle_depot": dep, "drive_node": int(hd), "drive_snap_m": round(math.hypot(hx - x, hy - y), 1),
             "vehicle_eta_min": (None if rt is None else round(30.0 + rt.total_time_min, 1))}
        flags = []
        if d["buildings_over_200m"] * 2 >= d["n_buildings"]: flags.append("snap-suspect")
        if d["fa_900_reached"] or d["fa_1200_reached"]: flags.append("budget-bound")
        if d["fa_pcut07_reached"]: flags.append("threshold-bound")
        if d["fire_blind_observed_class"] == "admissible_all": flags.append("forecast-only")
        if d["origin_forecast_cutoff_min"] is not None and d["origin_forecast_cutoff_min"] <= d["fire_blind_time_min"]: flags.append("origin-burns-first")
        if not flags: flags.append("corridor-burns")
        d["flags"] = flags; d["primary"] = flags[0]
        d["credible"] = not any(f in flags for f in ("snap-suspect", "budget-bound", "threshold-bound", "forecast-only"))
        diag.append(d)
    diag.sort(key=lambda d: -d["n_buildings"])
    cat = {}
    for d in diag:
        cat.setdefault(d["primary"], {"nodes": 0, "buildings": 0}); cat[d["primary"]]["nodes"] += 1; cat[d["primary"]]["buildings"] += d["n_buildings"]
    cred = [d for d in diag if d["credible"]]
    cred_summary = {"nodes": len(cred), "buildings": sum(d["n_buildings"] for d in cred),
                    "vehicle_reachable_nodes": sum(1 for d in cred if d["vehicle_reachable_W75"]),
                    "vehicle_reachable_buildings": sum(d["n_buildings"] for d in cred if d["vehicle_reachable_W75"]),
                    "origin_ever_detected_nodes": sum(1 for d in cred if d["origin_cell_first_seen_min"] is not None)}

    result = {
        "schema_version": 1, "title": "WFG-275 population graded against the observed footprint + no-safe-route diagnosis",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip(),
        "rule_doc": "docs/building_origins_observed_grading.md §1-§3 (pre-registered)",
        "inputs": {"buildings": bld.source_file, "hazard_npz": str(npz_path.relative_to(REPO)), "hazard_npz_sha256": npz_sha, "obs_times_min": [float(v) for v in obs_t]},
        "denominators": {"main_buildings_inside_box": int(n_bld), "within_snap_cap": int(within.sum()), "unsnappable": int((~within).sum()),
                         "origin_filtered": int((within & ~keep).sum()), "routable_buildings": int(len(r_idx)), "distinct_nodes": int(len(uniq))},
        "forecast_partition_nodes": fc, "forecast_partition_buildings": {k: sum(r["n_buildings"] for r in rows.values() if r["forecast_bucket"] == k) for k in fc},
        "wfg275_reference": {"nodes": {"both_safe": 4439, "naive_into_FA_safe": 477, "no_safe_route": 54}, "buildings": {"both_safe": 17454, "naive_into_FA_safe": 1606, "no_safe_route": 190}},
        "summary": summary, "diagnosis_categories": cat, "credible_failures": cred_summary, "diagnosis": diag,
        "per_node": list(rows.values()), "seconds": round(time.monotonic() - t0, 1),
    }
    OUT.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    S = summary; L = ["", f"_Run {result['generated_utc']} at `{result['git_commit'][:7]}`; artifact `{OUT.relative_to(REPO)}`; forecast partition nodes {fc} (WFG-275: 4439/477/54); {result['seconds']:.0f} s._", "",
         "### Observed grading (three-way, A4 base | A4 dilated)", "", "| level | arm | admissible for all | indeterminate | inadmissible for all | not reached |", "|---|---|---:|---:|---:|---:|"]
    for lvl in ("nodes", "buildings"):
        for arm in ("fire_blind", "forecast_aware"):
            a, b = S[lvl][arm]["a4_base"], S[lvl][arm]["a4_dilated"]
            L.append(f"| {lvl} | {arm} | {a['admissible_all']} \\| {b['admissible_all']} | {a['indeterminate']} \\| {b['indeterminate']} | {a['inadmissible_all']} \\| {b['inadmissible_all']} | {a['not_reached']} |")
    L += ["", "Paired fire-blind × forecast-aware, buildings, A4 base: " + ", ".join(f"{k} = {v}" for k, v in S["paired"]["buildings"]["a4_base"].items()),
          "Paired, buildings, A4 dilated: " + ", ".join(f"{k} = {v}" for k, v in S["paired"]["buildings"]["a4_dilated"].items()), ""]
    fo = S["forecast_only"]["buildings"]
    L += [f"Forecast-only class (1,606 buildings / 477 nodes), forecast-aware route observed: base admissible {fo['class']['admissible_all']}, indeterminate {fo['class']['indeterminate']}, inadmissible {fo['class']['inadmissible_all']}; dilated {fo['class_dilated']['admissible_all']} / {fo['class_dilated']['indeterminate']} / {fo['class_dilated']['inadmissible_all']}.", "",
          "### Diagnosis of the no-safe-route nodes", "", "| primary category | nodes | buildings |", "|---|---:|---:|"]
    for k, v in sorted(cat.items(), key=lambda kv: -kv[1]["buildings"]): L.append(f"| {k} | {v['nodes']} | {v['buildings']} |")
    L += ["", f"Credible failures (none of snap-suspect / budget-bound / threshold-bound / forecast-only): **{cred_summary['nodes']} nodes, {cred_summary['buildings']} buildings**; "
          f"of these a survival-aware vehicle route from some depot exists (W = 75, D = 30) for {cred_summary['vehicle_reachable_nodes']} nodes / {cred_summary['vehicle_reachable_buildings']} buildings; "
          f"the origin cell was itself detected at some overpass for {cred_summary['origin_ever_detected_nodes']} of them.", "",
          "Flag counts over all no-safe-route nodes: " + ", ".join(f"{f}: {sum(1 for d in diag if f in d['flags'])}" for f in ("snap-suspect", "budget-bound", "threshold-bound", "forecast-only", "origin-burns-first", "corridor-burns")) + ".", "",
          "Ten largest nodes:", "", "| node | buildings | snap med/max m | fire-blind time | origin cutoff (forecast) | first hazard node time | observed class | origin first seen | vehicle W75 | flags |", "|---|---:|---|---:|---:|---:|---|---|---|---|"]
    for d in diag[:10]:
        L.append(f"| {d['node']} | {d['n_buildings']} | {d['snap_m_median']}/{d['snap_m_max']} | {d['fire_blind_time_min']} | {d['origin_forecast_cutoff_min']} | {d['first_hazard_time_min']} | {d['fire_blind_observed_class']} | {d['origin_cell_first_seen_min']} | {d['vehicle_reachable_W75']} | {', '.join(d['flags'])} |")
    DOC.write_text(DOC.read_text(encoding="utf-8").rstrip("\n") + "\n" + "\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
