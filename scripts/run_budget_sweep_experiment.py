#!/usr/bin/env python
"""w(t): evacuation failure as the walking budget tightens (PHASE 2-C-2).

Closes the Round-2 "future work" item in Ⅴ-2, which left the 30 / 60 / 90-minute
w(t) sweep unmeasured.

WHY A BUDGET SWEEP
------------------
PHASE 2 and 2-C-1 both returned an invariant classification. Cause 2 of the
three identified: the 600-minute budget is never exhausted — the longest walk is
444 min under distance-ranked routing and only 353 min once routing is
time-aware. A budget nobody reaches cannot discriminate between routing
policies.

600 minutes was always an ALGORITHMIC CEILING, not an operational evacuation
window; the Round-2 documents said so as a stated limitation. This experiment
turns that caveat into numbers.

DEFINITIONS — read these before quoting anything
------------------------------------------------
An origin is EVACUABLE within budget t under objective O if its status-quo route
(nearest shelter, ranked by O) simultaneously:
  * reaches a shelter,
  * does not enter the predicted hazard, and
  * takes <= t minutes.

    w_naive(t, O) = 1 - evacuable / n_origins

`naive_route` carries no budget of its own, so the budget is applied explicitly
to its traversal time. That is the operational question: can this resident, who
walks to the nearest shelter, actually get there in time?

Separately, w_system(t) uses `future_aware_route` with time_budget_min = t —
the system's own recommendation under the same clock.

⚠ THIS DOES NOT REPLACE THE COMMITTED w ~= 11.4 %. That figure is at a
600-minute budget, on a different pipeline (the 439-origin rescue run, over
n_mobile = 307), and it remains valid. w(t) here is an ADDITIONAL measurement
under operational budgets. Never quote a short-budget w without its budget.

Run:  python scripts/run_budget_sweep_experiment.py
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
OUT = REPO / "data" / "processed" / "budget_sweep_experiment.json"
BUDGETS = [30.0, 60.0, 90.0, 120.0, 600.0]


def _git():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return None


def route_hilliness(net_flat, net_slope, route) -> float | None:
    """(slope time / flat time - 1) along a route: how much terrain costs it."""
    if not route or len(route) < 2:
        return None
    tf = ts = 0.0
    for a, b in zip(route, route[1:]):
        if not (net_flat.graph.has_edge(a, b) and net_slope.graph.has_edge(a, b)):
            return None
        tf += net_flat.graph[a][b]["time_min"]
        ts += net_slope.graph[a][b]["time_min"]
    return (ts / tf - 1.0) if tf > 0 else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--budgets", type=float, nargs="+", default=BUDGETS)
    ap.add_argument("--sampling-m", type=float,
                    default=_cfg("pedestrian.slope_sampling_m", 60.0))
    ap.add_argument("--p-cut", type=float, default=_cfg("pedestrian.walk_cutoff_p", 0.5))
    ap.add_argument("--time-step-min", type=float,
                    default=_cfg("time.routing_time_step_min", 10.0))
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    hazard, haz, extent, npz_sha = load_hazard()
    G = load_snapshot_graph(SNAPSHOT)
    cfg = RescueConfig(use_osm=True, osm_cache_dir=str(REPO / "data/cache/osm"))
    dests, shelter_src = load_shelters(cfg, regions.lookup(cfg.region_name).bbox_wgs84,
                                       to_5179=_TO_5179)
    print("building networks ...")
    net_flat, _ = build_walk_network(G, None, apply_slope=False, directed=True)
    net_slope, _ = build_walk_network(G, DEM, sampling_m=args.sampling_m,
                                      directed=True, apply_slope=True)
    for n in (net_flat, net_slope):
        n.shelters = {n.nearest_node(d.x, d.y) for d in dests}

    cand, _ = candidate_origins(net_flat, hazard, haz, extent, args.p_cut)
    n_org = len(cand)
    print(f"origins: {n_org}")

    # Status-quo routes are budget-independent, so compute each once.
    print("computing status-quo routes (3 network/objective combinations) ...")
    naive: dict[str, dict] = {}
    for tag, net, obj in (("flat/length_m", net_flat, "length_m"),
                          ("slope/length_m", net_slope, "length_m"),
                          ("slope/time_min", net_slope, "time_min")):
        naive[tag] = {n: naive_route(net, n, hazard, departure_min=0.0,
                                     p_cut=args.p_cut, objective=obj) for n in cand}

    def w_naive(tag: str, budget: float):
        """Returns (evacuable, failures, why) with the failure cause decomposed.

        The three causes are NOT interchangeable. "over budget" is a timing
        failure the budget sweep is designed to expose; "enters hazard" is a
        SAFETY failure that a time-ranked detour can introduce, because neither
        status-quo objective is hazard-aware.
        """
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

    rows, flips = [], {}
    print("\nsweeping budgets ...")
    for b in args.budgets:
        ok_d, fail_d, why_d = w_naive("slope/length_m", b)
        ok_t, fail_t, why_t = w_naive("slope/time_min", b)
        ok_f, fail_f, why_f = w_naive("flat/length_m", b)
        # System recommendation under the same clock.
        counts = classify(net_slope, cand, hazard, args.p_cut, b, args.time_step_min)
        rescued = sorted(set(ok_t) - set(ok_d))     # objective switch saved these
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
            "budget_min": b,
            "n_origins": n_org,
            "distance_objective": {"n_fail": len(fail_d),
                                   "w": len(fail_d) / n_org, "why": why_d},
            "time_objective": {"n_fail": len(fail_t), "w": len(fail_t) / n_org,
                               "why": why_t},
            "flat_distance_objective_control": {"n_fail": len(fail_f),
                                                "w": len(fail_f) / n_org,
                                                "why": why_f},
            "difference_n_fail": len(fail_d) - len(fail_t),
            "difference_w": (len(fail_d) - len(fail_t)) / n_org,
            "n_rescued_by_time_objective": len(rescued),
            "n_lost_by_time_objective": len(lost),
            "rescued_route_hilliness": {
                "n": len(hill_r),
                "mean": float(np.mean(hill_r)) if hill_r else None,
                "median": float(np.median(hill_r)) if hill_r else None,
            },
            "all_route_hilliness": {
                "n": len(hill_all),
                "mean": float(np.mean(hill_all)),
                "median": float(np.median(hill_all)),
            },
            "future_aware_counts": counts,
        })
        r = rows[-1]
        print(f"  budget {b:5.0f} min   dist w={r['distance_objective']['w']:6.2%} "
              f"({len(fail_d):3d})   time w={r['time_objective']['w']:6.2%} "
              f"({len(fail_t):3d})   diff={r['difference_n_fail']:+3d}   "
              f"rescued={len(rescued):3d}")
        print(f"{'':17s}   dist why={why_d}   time why={why_t}")

    doc = {
        "schema_version": 1,
        "title": "w(t): evacuation failure vs walking budget (PHASE 2-C-2)",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _git(), "config_hash": config_hash(),
        "closes": "Round-2 Ⅴ-2 future-work item: the 30/60/90-minute w(t) sweep.",
        "definitions": {
            "evacuable": "status-quo route reaches a shelter, does not enter the "
                         "predicted hazard, AND takes <= budget minutes",
            "w": "1 - evacuable / n_origins",
            "denominator": f"{n_org} scanned origins on the 2026-07-24 snapshot "
                           "network — NOT the 439-origin rescue run's n_mobile=307",
            "budget_application": "naive_route carries no budget, so the budget is "
                                  "applied explicitly to its traversal time; "
                                  "future_aware_counts uses time_budget_min=budget",
        },
        "does_not_replace": (
            "600분 기준 w ≈ 11.4%는 커밋된 값이며 유효합니다. 본 실험의 단축 예산 "
            "w(t)는 운영 조건에서의 추가 측정이며 대체값이 아닙니다. "
            "The committed w = 11.4 % is a 600-minute figure from the 439-origin "
            "rescue pipeline over n_mobile = 307. It stands. These are additional "
            "measurements on a different denominator under operational budgets."
        ),
        "design": {
            "budgets_min": args.budgets,
            "objectives": ["length_m (committed default)", "time_min (opt-in)"],
            "slope_sampling_m": args.sampling_m,
            "flat_arm": "distance objective only, as the 600-min control",
            "held_constant": ["snapshot walk graph 2026-07-24", "osmnx 2.0.7",
                              f"p_cut={args.p_cut}", "shelters", "origin scan rule"],
            "hazard_npz_sha256": npz_sha,
            "shelter_source": shelter_src,
        },
        "sweep": rows,
        "objective_flips": flips,
        "caveat": "Snapshot-network values, separate from the committed 459-origin "
                  "figures. Never quote a short-budget w without its budget.",
    }
    Path(args.out).write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")
    o = Path(args.out)
    print(f"\nwrote {o.relative_to(REPO) if o.is_relative_to(REPO) else o}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
