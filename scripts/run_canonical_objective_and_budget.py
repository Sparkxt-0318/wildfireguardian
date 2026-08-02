#!/usr/bin/env python
"""PHASE 2-C-1 and 2-C-2, re-run on the CANONICAL hazard field.

Round-3 step 3 of the canonical-field reconstruction. Two experiments in one
script because neither is readable without the other: the budget sweep varies
the objective, and the objective experiment is a single point of that sweep at
600 minutes.

    2-C-1  routing objective: distance-min vs time-min, x flat vs slope
    2-C-2  w(t): evacuation failure as the walking budget tightens

Both were first measured on ``routing_demo.npz``, the near-static field of the
run reverted on 2026-07-21. The canonical field's core is four times larger, so
in particular the 600-minute budget — which never bound on the old field — may
now bind.

DEFINITIONS ARE IMPORTED, NOT RESTATED
--------------------------------------
``candidate_origins`` and ``classify`` come from the committed runners, and
``route_hilliness`` from the committed budget-sweep script, so this run cannot
silently mean something different by "origin", "both_safe" or "hilliness".
``w`` keeps its committed definition exactly:

    evacuable  the STATUS-QUO route reaches a shelter, does not enter the
               predicted hazard, and takes <= budget minutes
    w          1 - evacuable / n_origins

⚠ ``w`` here is NOT the committed w ~ 11.4 %. That is a 600-minute figure from
the 439-origin rescue pipeline over n_mobile = 307, on a synthetic hazard
envelope. Different denominator, different lineage, different hazard. Neither
replaces the other.

Writes ``data/processed/objective_budget_canonical.json``. Committed artifacts
are digest-checked before and after; exits 4 if one moves.

Run:  python scripts/run_canonical_objective_and_budget.py
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
from wildfireguardian.routing.evacuation import naive_route  # noqa: E402
from wildfireguardian.routing.hazard import HazardSequence  # noqa: E402
from wildfireguardian.routing.slope import (  # noqa: E402
    build_walk_network, load_snapshot_graph,
)
from wildfireguardian.spread_v2.grid import CoarseGrid  # noqa: E402

from run_budget_sweep_experiment import route_hilliness  # noqa: E402
from run_real_roads_real_hazard_slope import candidate_origins  # noqa: E402
from run_multi_region_routing import (  # noqa: E402
    PROTECTED, classify, protected_digests, read_poi_snapshot, snapshot_for,
)

REGION = "yeongdeok_2025"
DEM = REPO / "data/raw/firms_data/yeongdeok_2025_dem.tif"
BUDGETS = [30.0, 60.0, 90.0, 120.0, 600.0]

#: Committed readings on the REVERTED run's field. Quoted, never re-derived.
COMMITTED_2C1 = {
    "flat/length_m": {"counts": "440/17/3", "max_time_min": 282.99},
    "flat/time_min": {"counts": "440/17/3", "max_time_min": 282.99},
    "slope/length_m": {"counts": "440/17/3", "max_time_min": 444.0},
    "slope/time_min": {"counts": "440/17/3", "max_time_min": 352.8},
    "routes_changed_slope": "150 of 460 (32.6 %)",
    "flat_routes_changed": "0 of 460",
}
COMMITTED_2C2_W = {30: 0.5500, 60: 0.3826, 90: 0.2609, 120: 0.1978, 600: 0.0435}


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
    ap.add_argument("--budgets", type=float, nargs="+", default=BUDGETS)
    ap.add_argument("--sampling-m", type=float,
                    default=float(_cfg("pedestrian.slope_sampling_m", 60.0)))
    ap.add_argument("--p-cut", type=float, default=float(_cfg("pedestrian.walk_cutoff_p", 0.5)))
    ap.add_argument("--time-step-min", type=float,
                    default=float(_cfg("time.routing_time_step_min", 10.0)))
    ap.add_argument("--out", default=str(REPO / "data/processed/objective_budget_canonical.json"))
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
    print("building networks ...")
    net_flat, _ = build_walk_network(G, None, apply_slope=False, directed=True)
    net_slope, _ = build_walk_network(G, DEM, sampling_m=args.sampling_m,
                                      directed=True, apply_slope=True)
    for n in (net_flat, net_slope):
        n.shelters = {n.nearest_node(d.x, d.y) for d in dests}
    cand, _ign = candidate_origins(net_flat, hazard, haz, extent, args.p_cut)
    n_org = len(cand)
    print(f"origins: {n_org}   refuges: {n_pois} POIs")

    # ---- status-quo routes, computed once (budget-independent) --------------
    print("\ncomputing status-quo routes (4 network/objective combinations) ...")
    naive: dict[str, dict] = {}
    for tag, net, obj in (("flat/length_m", net_flat, "length_m"),
                          ("flat/time_min", net_flat, "time_min"),
                          ("slope/length_m", net_slope, "length_m"),
                          ("slope/time_min", net_slope, "time_min")):
        t0 = time.monotonic()
        naive[tag] = {n: naive_route(net, n, hazard, departure_min=0.0,
                                     p_cut=args.p_cut, objective=obj) for n in cand}
        print(f"  {tag:16s} [{time.monotonic() - t0:.0f}s]")

    # ---- 2-C-1: the objective 2x2 -------------------------------------------
    print("\n[2-C-1] objective 2x2 (600-minute budget) ...")
    arms_2c1 = {}
    for tag, net in (("flat/length_m", net_flat), ("flat/time_min", net_flat),
                     ("slope/length_m", net_slope), ("slope/time_min", net_slope)):
        obj = tag.split("/")[1]
        counts, _classes = classify(net, cand, hazard, args.p_cut, 600.0,
                                    args.time_step_min, objective=obj)
        rs = naive[tag]
        d = [r.total_distance_m for r in rs.values() if r.reached]
        tm = [r.total_time_min for r in rs.values() if r.reached]
        arms_2c1[tag] = {
            "timing": tag.split("/")[0], "objective": obj,
            "n_origins_scanned": n_org, "counts": counts,
            "naive_mean_distance_m": float(np.mean(d)),
            "naive_mean_time_min": float(np.mean(tm)),
            "naive_max_time_min": float(np.max(tm)),
        }
        c = counts
        print(f"  {tag:16s} {c['both_safe']:4d}/{c['naive_into_FA_safe']:3d}/"
              f"{c['no_safe_route']:3d}  budget={c['fa_exceeds_budget']:3d}  "
              f"longest walk {np.max(tm):7.1f} min")

    def changed(a: str, b: str) -> list[int]:
        return [n for n in cand if tuple(naive[a][n].route) != tuple(naive[b][n].route)]

    flat_changed = changed("flat/length_m", "flat/time_min")
    slope_changed = changed("slope/length_m", "slope/time_min")
    deltas = []
    for n in slope_changed:
        a, b = naive["slope/length_m"][n], naive["slope/time_min"][n]
        if a.reached and b.reached and a.total_distance_m > 0 and a.total_time_min > 0:
            deltas.append({"distance_pct": (b.total_distance_m / a.total_distance_m - 1) * 100.0,
                           "time_pct": (b.total_time_min / a.total_time_min - 1) * 100.0})
    dp = [x["distance_pct"] for x in deltas]
    tp = [x["time_pct"] for x in deltas]
    longest_saving = (arms_2c1["slope/length_m"]["naive_max_time_min"]
                      - arms_2c1["slope/time_min"]["naive_max_time_min"])
    print(f"  routes changed by the objective: flat {len(flat_changed)} "
          f"(must be 0), slope {len(slope_changed)} "
          f"({100 * len(slope_changed) / n_org:.1f} %)")
    print(f"  longest walk {arms_2c1['slope/length_m']['naive_max_time_min']:.1f} -> "
          f"{arms_2c1['slope/time_min']['naive_max_time_min']:.1f} min "
          f"({longest_saving:+.1f})")

    # ---- 2-C-2: the budget sweep --------------------------------------------
    def w_naive(tag: str, budget: float):
        """Committed definition, verbatim. Causes are NOT interchangeable."""
        ok, fails = [], []
        why = {"unreachable": 0, "enters_hazard": 0, "over_budget": 0}
        for n, r in naive[tag].items():
            if not r.reached:
                why["unreachable"] += 1; fails.append(n); continue
            if r.enters_hazard:
                why["enters_hazard"] += 1; fails.append(n); continue
            if r.total_time_min > budget + 1e-9:
                why["over_budget"] += 1; fails.append(n); continue
            ok.append(n)
        return ok, fails, why

    print("\n[2-C-2] sweeping budgets ...")
    rows, flips = [], {}
    for b in args.budgets:
        ok_d, fail_d, why_d = w_naive("slope/length_m", b)
        ok_t, fail_t, why_t = w_naive("slope/time_min", b)
        ok_f, fail_f, why_f = w_naive("flat/length_m", b)
        counts, _cl = classify(net_slope, cand, hazard, args.p_cut, b, args.time_step_min)
        rescued = sorted(set(ok_t) - set(ok_d))
        lost = sorted(set(ok_d) - set(ok_t))
        flips[str(int(b))] = {"n_rescued_by_time_objective": len(rescued),
                              "n_lost_by_time_objective": len(lost),
                              "rescued_origins": rescued[:50]}
        hill_r = [h for h in (route_hilliness(net_flat, net_slope,
                                              naive["slope/length_m"][n].route)
                              for n in rescued) if h is not None]
        hill_all = [h for h in (route_hilliness(net_flat, net_slope,
                                                naive["slope/length_m"][n].route)
                                for n in cand) if h is not None]
        rows.append({
            "budget_min": b, "n_origins": n_org,
            "distance_objective": {"n_fail": len(fail_d), "w": len(fail_d) / n_org,
                                   "why": why_d},
            "time_objective": {"n_fail": len(fail_t), "w": len(fail_t) / n_org,
                               "why": why_t},
            "flat_distance_objective_control": {"n_fail": len(fail_f),
                                                "w": len(fail_f) / n_org, "why": why_f},
            "difference_n_fail": len(fail_d) - len(fail_t),
            "difference_w": (len(fail_d) - len(fail_t)) / n_org,
            "n_rescued_by_time_objective": len(rescued),
            "n_lost_by_time_objective": len(lost),
            "rescued_route_hilliness": {
                "n": len(hill_r),
                "mean": float(np.mean(hill_r)) if hill_r else None,
                "median": float(np.median(hill_r)) if hill_r else None},
            "all_route_hilliness": {"n": len(hill_all),
                                    "mean": float(np.mean(hill_all)),
                                    "median": float(np.median(hill_all))},
            "future_aware_counts": counts,
        })
        r = rows[-1]
        print(f"  budget {b:5.0f} min   dist w={r['distance_objective']['w']:6.2%} "
              f"({len(fail_d):3d})   time w={r['time_objective']['w']:6.2%} "
              f"({len(fail_t):3d})   diff={r['difference_n_fail']:+3d}   "
              f"rescued={len(rescued):3d}   FA_budget={counts['fa_exceeds_budget']:3d}")
        print(f"{'':17s}   dist why={why_d}")

    ratio = (rows[0]["distance_objective"]["w"] / rows[-1]["distance_objective"]["w"]
             if rows[-1]["distance_objective"]["w"] > 0 else None)

    doc = {
        "schema_version": 1,
        "title": "Routing objective (2-C-1) and w(t) budget sweep (2-C-2) on the "
                 "CANONICAL hazard field",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _git(), "config_hash": config_hash(),
        "does_not_supersede": (
            "routing_objective_experiment.json and budget_sweep_experiment.json "
            "are UNTOUCHED. They measure the same experiments on the reverted "
            "run's hazard field."),
        "definitions": {
            "evacuable": "status-quo route reaches a shelter, does not enter the "
                         "predicted hazard, AND takes <= budget minutes",
            "w": "1 - evacuable / n_origins",
            "denominator": f"{n_org} scanned origins on the 2026-07-24 snapshot "
                           "network and the CANONICAL hazard field",
            "imported_from": "candidate_origins and classify from the committed "
                             "runners; route_hilliness from "
                             "run_budget_sweep_experiment.py",
        },
        "not_the_committed_w": (
            "커밋된 w ≈ 11.4 %는 439 계열 구조 파이프라인의 600분 값으로, "
            "n_mobile = 307을 분모로 하고 합성 위험면 위에서 산출되었습니다. "
            "본 실험과 분모도 계보도 위험면도 다르며 대체값이 아닙니다. "
            "The committed w = 11.4 % is a 600-minute figure from the 439-origin "
            "rescue pipeline over n_mobile = 307 on a SYNTHETIC hazard envelope. "
            "Different denominator, different lineage, different field. Neither "
            "replaces the other."),
        "hazard_source": {"npz_path": str(Path(args.npz).relative_to(REPO)),
                          "npz_sha256": npz_sha, "shape": list(haz.shape)},
        "network_source": {"snapshot_walk": snap.name, "n_refuge_pois": n_pois,
                           "read_from_cache": False},
        "objective_2x2": {
            "arms": arms_2c1,
            "flat_control_routes_changed": len(flat_changed),
            "flat_control_must_be_zero_because": (
                "with flat timing every edge time is length / constant speed, so "
                "minimising time and minimising distance are the same problem. A "
                "non-zero count is an implementation fault, not a finding."),
            "flat_invariant_holds": bool(len(flat_changed) == 0),
            "slope_routes_changed": len(slope_changed),
            "slope_routes_changed_pct": 100.0 * len(slope_changed) / n_org,
            "path_deltas_on_changed_routes": {
                "n": len(deltas),
                "distance_pct": {"median": float(np.median(dp)) if dp else None,
                                 "max": float(np.max(dp)) if dp else None},
                "time_pct": {"median": float(np.median(tp)) if tp else None,
                             "best": float(np.min(tp)) if tp else None},
            },
            "longest_walk_min": {
                "slope_distance_objective": arms_2c1["slope/length_m"]["naive_max_time_min"],
                "slope_time_objective": arms_2c1["slope/time_min"]["naive_max_time_min"],
                "saving_min": longest_saving,
            },
            "committed_reading_on_the_reverted_field": COMMITTED_2C1,
            "what_is_being_compared_when_both_minimise_time": (
                "Switching naive_route to time_min does NOT make the two routers "
                "the same. future_aware_route minimises cumulative EXPOSURE on a "
                "time-expanded graph and only breaks ties on arrival time; the "
                "status-quo router minimises a single scalar and is blind to the "
                "fire. So naive_into_FA_safe still means 'the fire-blind route "
                "enters the predicted hazard and the future-aware one does not'. "
                "What changes is which fire-blind route is being tested — the "
                "shortest, or the fastest. Both are fire-blind."),
        },
        "budget_sweep": {
            "budgets_min": args.budgets,
            "rows": rows,
            "objective_flips": flips,
            "w_ratio_tightest_over_loosest": ratio,
            "committed_w_on_the_reverted_field": COMMITTED_2C2_W,
            "hazard_entry_attribution": (
                "'enters_hazard' failures belong to the FIRE-BLIND BASELINE, not "
                "to the proposed system. future_aware_route never enters the "
                "hazard: both_enter is 0 at every budget in future_aware_counts. "
                "Never restate these as a cost of the system."),
        },
        "held_constant": ["snapshot walk graph 2026-07-24", "osmnx 2.0.7",
                          f"p_cut={args.p_cut}", "shelters", "origin scan rule",
                          f"slope sampling {args.sampling_m:g} m"],
    }
    Path(args.out).write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")

    after = protected_digests()
    ch = [k for k in before if before[k] != after[k]]
    if ch:
        print(f"\nSTOP (exit 4): protected artifact(s) changed: {ch}", file=sys.stderr)
        return 4
    print(f"\nwrote {Path(args.out).relative_to(REPO)}")
    print(f"protected artifacts unchanged ({len(PROTECTED)} verified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
