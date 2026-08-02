#!/usr/bin/env python
"""PHASE 2's slope sweep, re-run on the CANONICAL hazard field.

Round-3 step 2 of the canonical-field reconstruction.

WHY
---
`docs/slope_integration.md` reports a null result: at 30, 60 and 90 m sampling
the buckets stay 440 / 17 / 3, flat *and* slope. That was measured on
``routing_demo.npz`` — the near-static field of the run reverted on 2026-07-21
(``data/processed/routing_demo_divergence.json``). On the canonical field the
flat arm already reads 415 / 41 / 2 and the 60 m arm 414 / 42 / 2, so the null
does not obviously survive.

THE QUESTION THAT DECIDES IT
----------------------------
One origin moving is not a result on its own. It is a result only if it is the
**same** origin at all three sampling spacings: a single origin that flips at
60 m but not at 30 m and 90 m is sampling noise, whereas one that flips at every
spacing is terrain doing something. This script therefore tracks bucket
membership per origin, not just counts, and intersects the moved sets across
spacings.

CONTROLS
--------
* **flat / undirected** — the no-terrain baseline.
* **flat / DiGraph** — with flat timing, direction carries no information, so
  this MUST equal the undirected control. A divergence means the conversion is
  broken and nothing downstream is readable.
* **traversal-time change** — a property of the graph and the DEM, NOT of the
  hazard. It must reproduce the committed +26.594 % at 60 m. If it does not,
  the implementation moved and that is the finding.
* **naive route stability** — `naive_route` ranks by `length_m`, so its path is
  slope-invariant by construction and the count of changed naive routes must be
  exactly 0. Any other value is a bug, not a discovery.

Writes ``data/processed/slope_sweep_canonical.json``. Every committed artifact
is digest-checked before and after; exits 4 if one moves.

Run:  python scripts/run_yeongdeok_canonical_slope_sweep.py
"""

from __future__ import annotations

import argparse
import hashlib
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

from wildfireguardian.config import config_hash, get as _cfg  # noqa: E402
from wildfireguardian.routing.evacuation import future_aware_route, naive_route  # noqa: E402
from wildfireguardian.routing.hazard import HazardSequence  # noqa: E402
from wildfireguardian.routing.slope import (  # noqa: E402
    build_walk_network, load_snapshot_graph,
)
from wildfireguardian.spread_v2.grid import CoarseGrid  # noqa: E402

from run_real_roads_real_hazard_slope import candidate_origins  # noqa: E402
from run_multi_region_routing import (  # noqa: E402
    PROTECTED, classify, protected_digests, read_poi_snapshot, snapshot_for,
)

REGION = "yeongdeok_2025"
DEM = REPO / "data/raw/firms_data/yeongdeok_2025_dem.tif"
COMMITTED_SLOPE = {s: REPO / f"data/processed/real_roads_real_hazard_slope_{s}.json"
                   for s in (30, 60, 90)}
#: The committed reading, on the reverted run's field. QUOTED, never re-derived.
COMMITTED_COUNTS = {"both_safe": 440, "naive_into_FA_safe": 17, "no_safe_route": 3}
COMMITTED_TIME_PCT_60M = 26.594


def _git() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def bucket_of(classes: dict[str, list[int]]) -> dict[int, str]:
    return {n: k for k, ns in classes.items() for n in ns}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--npz", default=str(REPO / "data/processed/routing_demo_canonical.npz"))
    ap.add_argument("--spacings", type=float, nargs="+",
                    default=_cfg("pedestrian.slope_sampling_sweep_m", [30.0, 60.0, 90.0]))
    ap.add_argument("--max-abs-slope", type=float,
                    default=float(_cfg("pedestrian.max_abs_slope", 0.60)))
    ap.add_argument("--p-cut", type=float, default=float(_cfg("pedestrian.walk_cutoff_p", 0.5)))
    ap.add_argument("--time-budget-min", type=float,
                    default=float(_cfg("pedestrian.walk_budget_min", 600.0)))
    ap.add_argument("--time-step-min", type=float,
                    default=float(_cfg("time.routing_time_step_min", 10.0)))
    ap.add_argument("--out", default=str(REPO / "data/processed/slope_sweep_canonical.json"))
    args = ap.parse_args()

    before = protected_digests()
    if any(v is None for v in before.values()):
        print("STOP: a protected artifact is missing.", file=sys.stderr)
        return 2

    z = np.load(args.npz)
    haz = z["haz_stack"].astype(np.float32)
    xmin, ymin, xmax, ymax, cell = [float(v) for v in z["grid_extent"]]
    grid = CoarseGrid(minx=xmin, miny=ymin, maxx=xmax, maxy=ymax, cell_size_m=cell,
                      nrows=haz.shape[1], ncols=haz.shape[2])
    hazard = HazardSequence(grid=grid, times_min=np.asarray(z["haz_times"], float),
                            surfaces=[haz[i] for i in range(haz.shape[0])])
    extent = (xmin, ymin, xmax, ymax, cell)
    npz_sha = hashlib.sha256(Path(args.npz).read_bytes()).hexdigest()
    print(f"canonical hazard {haz.shape} sha256 {npz_sha[:16]}...")

    snap = snapshot_for(REGION, "walk")
    G = load_snapshot_graph(snap)
    dests, n_pois = read_poi_snapshot(snapshot_for(REGION, "shelters"), kind="shelter")
    print(f"snapshot {snap.name}: {G.number_of_nodes():,} nodes; {n_pois} refuge POIs")

    arms: dict[str, dict] = {}
    membership: dict[str, dict[int, str]] = {}
    routes: dict[str, dict[int, tuple]] = {}

    def run_arm(key, label, net, stats):
        net.shelters = {net.nearest_node(d.x, d.y) for d in dests}
        cand, _ign = candidate_origins(net, hazard, haz, extent, args.p_cut)
        t0 = time.monotonic()
        counts, classes = classify(net, cand, hazard, args.p_cut,
                                   args.time_budget_min, args.time_step_min)
        # Routes are recorded so "did the PATH change?" can be answered
        # separately from "did the BUCKET change?".
        rts = {}
        for n in cand:
            nv = naive_route(net, n, hazard, departure_min=0.0, p_cut=args.p_cut)
            fa = future_aware_route(net, n, hazard, departure_min=0.0,
                                    time_budget_min=args.time_budget_min,
                                    p_cut=args.p_cut, time_step_min=args.time_step_min)
            rts[n] = (tuple(nv.route), tuple(fa.route),
                      nv.total_distance_m, nv.total_time_min,
                      fa.total_distance_m, fa.total_time_min)
        membership[key] = bucket_of(classes)
        routes[key] = rts
        print(f"  {label:28s} N={len(cand):4d}  both={counts['both_safe']:4d}  "
              f"FA_only={counts['naive_into_FA_safe']:3d}  "
              f"no_safe={counts['no_safe_route']:3d}  "
              f"budget={counts['fa_exceeds_budget']:3d}  "
              f"[{time.monotonic() - t0:.0f}s]")
        d = {"label": label, "n_origins_scanned": len(cand), "counts": counts,
             "n_nodes": net.graph.number_of_nodes(),
             "n_edges": net.graph.number_of_edges()}
        if stats is not None:
            sd = stats.as_dict()
            d["slope_stats"] = sd
            d["traversal_time_pct_change"] = float(
                sd["traversal_time"]["pct_change_mean_of_directions"])
            d["mean_abs_slope"] = float(sd["slope_abs"]["mean"])
        arms[key] = d
        return d

    print("\ncontrols:")
    net_u, _ = build_walk_network(G, None, apply_slope=False, directed=False)
    run_arm("flat_undirected", "flat / undirected", net_u, None)
    net_d, _ = build_walk_network(G, None, apply_slope=False, directed=True)
    run_arm("flat_digraph", "flat / DiGraph (regr.)", net_d, None)
    regression_ok = arms["flat_undirected"]["counts"] == arms["flat_digraph"]["counts"]
    print(f"  -> DiGraph regression: {'PASS' if regression_ok else 'FAIL — DIVERGES'}")
    if not regression_ok:
        print("STOP: flat DiGraph diverges from the undirected control.", file=sys.stderr)
        return 3

    print("\nslope arms (DiGraph, clipped):")
    nets = {}
    for s in args.spacings:
        net_s, st = build_walk_network(G, DEM, sampling_m=s,
                                       max_abs_slope=args.max_abs_slope,
                                       directed=True, apply_slope=True)
        nets[int(s)] = net_s
        run_arm(f"slope_{int(s)}", f"slope {s:g} m / DiGraph", net_s, st)

    # ---- THE question: is it the same origin every time? --------------------
    base = membership["flat_undirected"]
    moved_sets, per_spacing = {}, {}
    for s in args.spacings:
        k = f"slope_{int(s)}"
        moved = {n: (base[n], membership[k][n]) for n in base
                 if membership[k].get(n) != base[n]}
        moved_sets[int(s)] = set(moved)
        per_spacing[int(s)] = {
            "n_moved": len(moved),
            "moved": {str(n): {"flat_bucket": a, "slope_bucket": b}
                      for n, (a, b) in sorted(moved.items())},
        }
        print(f"  spacing {int(s):2d} m: {len(moved)} origin(s) changed bucket "
              f"vs the flat control -> {sorted(moved)}")

    common = set.intersection(*moved_sets.values()) if moved_sets else set()
    union = set.union(*moved_sets.values()) if moved_sets else set()
    print(f"\n  moved at ALL spacings : {sorted(common)}")
    print(f"  moved at ANY spacing  : {sorted(union)}")
    verdict = ("consistent_across_spacings" if common and common == union else
               "inconsistent_across_spacings" if union else "no_movement")

    # ---- did any PATH change? ----------------------------------------------
    path_changes = {}
    for s in args.spacings:
        k = f"slope_{int(s)}"
        nv_changed = [n for n in routes["flat_undirected"]
                      if routes[k][n][0] != routes["flat_undirected"][n][0]]
        fa_changed = [n for n in routes["flat_undirected"]
                      if routes[k][n][1] != routes["flat_undirected"][n][1]]
        path_changes[int(s)] = {
            "naive_routes_changed": len(nv_changed),
            "future_aware_routes_changed": len(fa_changed),
            "naive_must_be_zero_because": (
                "naive_route ranks by length_m, which slope does not alter, so "
                "its path is slope-invariant by construction"),
            "naive_invariant_holds": bool(len(nv_changed) == 0),
        }
        print(f"  spacing {int(s):2d} m: naive routes changed {len(nv_changed)}, "
              f"future-aware routes changed {len(fa_changed)}")

    # ---- what do the moved origins look like? -------------------------------
    moved_detail = {}
    for n in sorted(union):
        rec = {"flat_bucket": base[n], "by_spacing": {}}
        f = routes["flat_undirected"][n]
        rec["flat"] = {"naive_distance_m": f[2], "naive_time_min": f[3],
                       "fa_distance_m": f[4], "fa_time_min": f[5]}
        for s in args.spacings:
            k = f"slope_{int(s)}"
            r = routes[k][n]
            rec["by_spacing"][str(int(s))] = {
                "bucket": membership[k][n],
                "naive_time_min": r[3], "fa_time_min": r[5],
                "fa_distance_m": r[4],
                "naive_time_ratio_vs_flat": float(r[3] / f[3]) if f[3] else None,
                "fa_route_changed": bool(r[1] != f[1]),
            }
        moved_detail[str(n)] = rec

    t60 = arms.get("slope_60", {}).get("traversal_time_pct_change")
    t60 = float(t60) if t60 is not None else None
    time_ok = bool(t60 is not None and abs(t60 - COMMITTED_TIME_PCT_60M) < 0.01)

    doc = {
        "schema_version": 1,
        "title": "Slope sampling sweep on the CANONICAL Yeongdeok hazard field",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _git(), "config_hash": config_hash(),
        "does_not_supersede": (
            "real_roads_real_hazard_slope_{30,60,90}.json are UNTOUCHED. This is "
            "the same sweep on a different hazard field, written to a new name."),
        "hazard_source": {"npz_path": str(Path(args.npz).relative_to(REPO)),
                          "npz_sha256": npz_sha, "shape": list(haz.shape)},
        "network_source": {"snapshot_walk": snap.name, "n_refuge_pois": n_pois,
                           "read_from_cache": False},
        "parameters": {"spacings_m": list(args.spacings),
                       "max_abs_slope": args.max_abs_slope, "p_cut": args.p_cut,
                       "time_budget_min": args.time_budget_min,
                       "time_step_min": args.time_step_min,
                       "objective": "length_m (distance-ranked)"},
        "arms": arms,
        "digraph_regression": {"identical": bool(regression_ok)},
        "committed_reading_on_the_reverted_field": {
            "counts": COMMITTED_COUNTS, "n_origins_scanned": 460,
            "spacings": "identical at 30, 60 and 90 m — the PHASE-2 null result",
            "source": "data/processed/real_roads_real_hazard_slope_{30,60,90}.json",
            "status": "QUOTED, never re-derived. Its hazard field came from the "
                      "run reverted on 2026-07-21.",
        },
        "bucket_movement_vs_flat_control": {
            "per_spacing": per_spacing,
            "moved_at_all_spacings": sorted(common),
            "moved_at_any_spacing": sorted(union),
            "verdict": verdict,
            "how_to_read": (
                "An origin that changes bucket at EVERY spacing is terrain doing "
                "something the router can see. One that flips at a single "
                "spacing is sampling noise: the spacing changes which DEM pixels "
                "are read, and a marginal origin can cross the budget or the "
                "cutoff either way."),
            "detail": moved_detail,
        },
        "path_changes_vs_flat_control": path_changes,
        "traversal_time_check": {
            "committed_60m_pct": COMMITTED_TIME_PCT_60M,
            "canonical_60m_pct": t60,
            "matches": time_ok,
            "why_it_must_match": (
                "Traversal time is a property of the walk graph and the DEM. The "
                "hazard field does not enter it, and Yeongdeok's DEM was not "
                "re-acquired, so this number must be unchanged. A mismatch would "
                "mean the slope implementation moved, not the fire."),
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
    print(f"\ntraversal time at 60 m: committed {COMMITTED_TIME_PCT_60M:.3f} % vs "
          f"canonical {t60:.3f} % -> {'MATCH' if time_ok else 'MISMATCH'}")
    print(f"wrote {Path(args.out).relative_to(REPO)}")
    print(f"protected artifacts unchanged ({len(PROTECTED)} verified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
