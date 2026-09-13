#!/usr/bin/env python
"""Last safe departure (LSD) per building-origin node, fire-blind vs time-aware, on the
committed 영덕 forecast. The doctrine's currency is minutes before fire-line arrival; this
reports minutes of lead the forecast-aware policy buys.

Rule (declared before the run): for each of the WFG-275 nodes, LSD_FB = the latest
departure d in {0, 10, ..., 600} at which the fire-blind shortest path (fixed geometry)
reaches a refuge without entering p >= 0.5 at any node; LSD_FA = the latest d at which the
time-aware search (600-min budget, 10-min step) finds such a route. Safety is monotone in d
because the forecast is monotone, so a binary search over the grid is exact. d + walk time
can exceed the 720-min horizon for late departures; the sampler then clamps to the last
surface (a lower bound on risk), so an LSD of 600 is reported as censored (">= 600").
Buildings inherit their node's values. Nothing committed is modified.

    python scripts/measure_last_safe_departure.py
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from wildfireguardian.buildings import load_buildings  # noqa: E402
from wildfireguardian.routing.evacuation import _evaluate_path, future_aware_route, naive_route  # noqa: E402
from wildfireguardian.routing.slope import build_walk_network, load_snapshot_graph  # noqa: E402

from run_building_origin_routing import load_hazard, origin_filter  # noqa: E402
from run_multi_region_routing import read_poi_snapshot, snapshot_for  # noqa: E402

OUT = REPO / "data/processed/last_safe_departure_yeongdeok.json"
DOC = REPO / "docs/last_safe_departure.md"
REGION = "yeongdeok_2025"
P_CUT, BUDGET, STEP, MAX_SNAP = 0.5, 600.0, 10.0, 500.0
GRID = [float(d) for d in range(0, 601, 10)]


def lsd_fixed(net, path, hazard):
    """Latest grid departure at which the fixed path is safe; -1 if never (not even at 0)."""
    lo, hi = -1, len(GRID) - 1
    def ok(i):
        r = _evaluate_path(net, path, hazard, GRID[i], P_CUT, "lsd", path[-1])
        return r.reached and not r.enters_hazard and r.total_time_min <= BUDGET
    if not ok(0):
        return -1.0
    while lo < hi - 1 or (lo == -1 and hi == 0):
        mid = (lo + hi + 1) // 2 if lo >= 0 else (hi // 2 if hi > 0 else 0)
        if mid == lo: break
        if ok(mid): lo = mid
        else: hi = mid - 1
        if lo == hi: break
    # linear fix-up around the boundary (cheap, exact)
    i = max(lo, 0)
    while i + 1 < len(GRID) and ok(i + 1): i += 1
    return GRID[i]


def lsd_search(net, n, hazard):
    def ok(i):
        r = future_aware_route(net, n, hazard, departure_min=GRID[i], time_budget_min=BUDGET, p_cut=P_CUT, time_step_min=STEP)
        return r.reached and not r.enters_hazard
    if not ok(0):
        return -1.0
    lo, hi = 0, len(GRID) - 1
    if ok(hi): return GRID[hi]
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if ok(mid): lo = mid
        else: hi = mid
    return GRID[lo]


def main() -> int:
    t0 = time.monotonic()
    bld = load_buildings(REGION, source="juso_main", repo=REPO)
    hazard, haz, extent, npz_sha, npz_path = load_hazard(REGION)
    G = load_snapshot_graph(snapshot_for(REGION, "walk"))
    net, _ = build_walk_network(G, REPO / f"data/raw/firms_data/{REGION}_dem.tif", sampling_m=60.0, max_abs_slope=0.6, directed=True, apply_slope=True)
    dests, _ = read_poi_snapshot(snapshot_for(REGION, "shelters"), kind="shelter")
    net.shelters = {net.nearest_node(d.x, d.y) for d in dests}
    n_bld = len(bld); snap_node = np.empty(n_bld, dtype=object); snap_dist = np.empty(n_bld)
    for i in range(n_bld):
        x, y = float(bld.xy[i, 0]), float(bld.xy[i, 1]); nid = net.nearest_node(x, y); nx_, ny_ = net.node_xy(nid)
        snap_node[i] = nid; snap_dist[i] = math.hypot(nx_ - x, ny_ - y)
    keep, _, _ = origin_filter(bld.xy, haz, extent, P_CUT)
    routable = (snap_dist <= MAX_SNAP) & keep
    r_nodes = snap_node[np.where(routable)[0]].astype(np.int64)
    uniq, counts = np.unique(r_nodes, return_counts=True); w = {int(n): int(c) for n, c in zip(uniq, counts)}
    print(f"nodes {len(uniq)} buildings {int(routable.sum())}", flush=True)
    rows = []
    for k, n in enumerate(uniq):
        n = int(n)
        nv = naive_route(net, n, hazard, departure_min=0.0, p_cut=P_CUT, objective="length_m")
        fb = lsd_fixed(net, list(nv.route), hazard) if nv.reached else -1.0
        fa = lsd_search(net, n, hazard)
        rows.append({"node": n, "n_buildings": w[n], "lsd_fire_blind_min": fb, "lsd_time_aware_min": fa,
                     "fb_walk_min": round(nv.total_time_min, 1) if nv.reached else None})
        if (k + 1) % 250 == 0: print(f"  [{k+1}/{len(uniq)}] {time.monotonic()-t0:.0f}s", flush=True)
    def wq(vals, ws, q):
        o = np.argsort(vals); v = np.asarray(vals)[o]; c = np.cumsum(np.asarray(ws)[o]); return float(v[np.searchsorted(c, q * c[-1])])
    def summarise(sub, label):
        if not sub: return {"label": label, "n_nodes": 0, "n_buildings": 0}
        ws = [r["n_buildings"] for r in sub]
        gain = [r["lsd_time_aware_min"] - r["lsd_fire_blind_min"] for r in sub]
        return {"label": label, "n_nodes": len(sub), "n_buildings": sum(ws),
                "lsd_fb_median_b": wq([r["lsd_fire_blind_min"] for r in sub], ws, 0.5), "lsd_fa_median_b": wq([r["lsd_time_aware_min"] for r in sub], ws, 0.5),
                "gain_median_b": wq(gain, ws, 0.5), "gain_p25_b": wq(gain, ws, 0.25), "gain_p75_b": wq(gain, ws, 0.75),
                "buildings_fb_below_300": sum(r["n_buildings"] for r in sub if r["lsd_fire_blind_min"] < 300), "buildings_fa_below_300": sum(r["n_buildings"] for r in sub if r["lsd_time_aware_min"] < 300),
                "buildings_fb_never": sum(r["n_buildings"] for r in sub if r["lsd_fire_blind_min"] < 0), "buildings_fa_never": sum(r["n_buildings"] for r in sub if r["lsd_time_aware_min"] < 0),
                "buildings_fa_censored_600": sum(r["n_buildings"] for r in sub if r["lsd_time_aware_min"] >= 600), "buildings_fb_censored_600": sum(r["n_buildings"] for r in sub if r["lsd_fire_blind_min"] >= 600),
                "buildings_gain_positive": sum(r["n_buildings"] for r in sub if r["lsd_time_aware_min"] > r["lsd_fire_blind_min"]),
                "buildings_gain_negative": sum(r["n_buildings"] for r in sub if r["lsd_time_aware_min"] < r["lsd_fire_blind_min"])}
    all_s = summarise(rows, "all routable")
    fa_only = summarise([r for r in rows if r["lsd_fire_blind_min"] < 0 <= r["lsd_time_aware_min"]], "fire-blind never safe, time-aware safe at some departure")
    both = summarise([r for r in rows if r["lsd_fire_blind_min"] >= 0 and r["lsd_time_aware_min"] >= 0], "both safe at departure 0")
    threatened = summarise([r for r in rows if 0 <= r["lsd_fire_blind_min"] < 600], "fire-blind safe now but closes before 600 min (threatened)")
    result = {"schema_version": 1, "title": "Last safe departure, fire-blind vs time-aware, 영덕 주건물 population (forecast-graded)",
              "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip(),
              "rule": __doc__, "inputs": {"buildings": bld.source_file, "hazard_npz": str(npz_path.relative_to(REPO)), "hazard_npz_sha256": npz_sha},
              "parameters": {"p_cut": P_CUT, "budget_min": BUDGET, "step_min": STEP, "departure_grid_min": [GRID[0], GRID[-1], 10]},
              "summaries": [all_s, both, threatened, fa_only], "per_node": rows, "seconds": round(time.monotonic() - t0, 1)}
    OUT.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    L = [f"# Last safe departure — fire-blind vs time-aware, 영덕 주건물 population", "",
         f"_Run {result['generated_utc']} at `{result['git_commit'][:7]}`; artifact `{OUT.relative_to(REPO)}`; {len(rows)} nodes / {all_s['n_buildings']} buildings; forecast-graded; {result['seconds']:.0f} s. Rule in the script docstring (declared before the run)._", "",
         "LSD = the latest departure (minutes after the forecast clock's zero, 10-min grid, ≤ 600) at which the policy's route still reaches a refuge without entering p ≥ 0.5. −1 = never, even at 0. 600 = censored (still safe at the last grid point; the horizon clamp applies beyond 720 min). Building-weighted medians.", "",
         "| subset | nodes | buildings | LSD fire-blind median | LSD time-aware median | gain median (p25–p75) | buildings gaining | losing | FB < 5 h | TA < 5 h | FB never | TA never | FB ≥ 600 | TA ≥ 600 |", "|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for s in result["summaries"]:
        if s["n_nodes"] == 0: L.append(f"| {s['label']} | 0 | 0 | | | | | | | | | | | |"); continue
        L.append(f"| {s['label']} | {s['n_nodes']} | {s['n_buildings']} | {s['lsd_fb_median_b']:.0f} | {s['lsd_fa_median_b']:.0f} | {s['gain_median_b']:.0f} ({s['gain_p25_b']:.0f}–{s['gain_p75_b']:.0f}) | {s['buildings_gain_positive']} | {s['buildings_gain_negative']} | {s['buildings_fb_below_300']} | {s['buildings_fa_below_300']} | {s['buildings_fb_never']} | {s['buildings_fa_never']} | {s['buildings_fb_censored_600']} | {s['buildings_fa_censored_600']} |")
    L += ["", "What it does not show: passability, households, the observed footprint (this page is forecast-graded like the committed arms), or anything outside 영덕. Censoring at 600 min means the medians are lower bounds where the ≥ 600 column is large."]
    DOC.write_text("\n".join(L) + "\n", encoding="utf-8"); print("\n".join(L)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
