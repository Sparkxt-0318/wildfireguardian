#!/usr/bin/env python
"""The assisted-pickup intervention re-run with the two scheduler defects repaired.

HQ decision 4 (`docs/auto/briefs/TRUCK_CREW_REPLAY_DECISIONS.md`): fix both defects the
truck-crew build found, under a new function name, re-run under a new artifact name, and
report whether the committed 9-of-24 / 40-of-74 result moves.

`schedule` and `data/processed/vehicle_pickup_intervention_yeongdeok.json` are untouched;
this uses `schedule_fixed` and writes
`data/processed/vehicle_pickup_intervention_fixed_yeongdeok.json`.

    python scripts/run_vehicle_pickup_intervention_fixed.py
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

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from wildfireguardian.routing.rescue import (  # noqa: E402
    RescueConfig, assess_destinations, node_survival_time,
)

from run_real_roads_real_hazard_slope import REAL_OSM_SCAN_STRIDE  # noqa: E402
from run_rescue_routing_full import materialise_snapshots  # noqa: E402
from run_rescue_routing_real_hazard import build_scenario  # noqa: E402
from run_vehicle_pickup_intervention import (  # noqa: E402
    DIAG, DISPATCH, FLEETS, MARGIN, T_LOAD, T_UNLOAD, W, schedule, schedule_fixed,
)

OUT = REPO / "data/processed/vehicle_pickup_intervention_fixed_yeongdeok.json"
#: the committed result this re-run is asked to confirm or contradict
COMMITTED = {"completed_walk_nodes": 9, "credible_walk_nodes": 24,
             "completed_buildings": 40, "credible_buildings": 74}


def main() -> int:
    t0 = time.monotonic()
    diag = json.loads(DIAG.read_text(encoding="utf-8"))
    cred = [d for d in diag["diagnosis"] if d["credible"]]
    tmp = Path(tempfile.mkdtemp(prefix="wfg-vpf-"))
    try:
        materialise_snapshots(tmp / "yeongdeok_2025")
        cfg = RescueConfig(use_osm=True, osm_cache_dir=str(tmp),
                           scan_stride=REAL_OSM_SCAN_STRIDE, responder_time_budget_min=W)
        sc = build_scenario(cfg)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    depot_nodes = [sc.drive.nearest_node(d.x, d.y) for d in sc.depots]

    homes = []
    for d in cred:
        hd = int(d["drive_node"])
        x, y = sc.drive.node_xy(hd)
        dl = node_survival_time(sc.hazard, x, y, cfg.vehicle_cutoff)
        homes.append({"walk_node": d["node"], "drive_node": hd,
                      "n_buildings": d["n_buildings"],
                      "deadline": (1e9 if math.isinf(dl) else float(dl)),
                      "drive_snap_m": d["drive_snap_m"]})
    distinct = len({h["drive_node"] for h in homes})

    runs = {}
    for D in DISPATCH:
        cfgD = replace(cfg, responder_dispatch_delay_min=D)
        ass = assess_destinations(sc.destinations, sc.drive, depot_nodes, sc.hazard, cfgD)
        refuges = sorted({a.node for a in ass if a.rescue_reachable})
        for k in FLEETS:
            out_fix, veh_fix, groups = schedule_fixed(sc, cfgD, homes, refuges, k, D)
            out_old, veh_old = schedule(sc, cfgD, homes, refuges, k, D)

            def tally(outcome):
                comp_w = [h for h in homes if outcome[h["drive_node"]]["status"] == "completed"]
                return {
                    "completed_walk_nodes": len(comp_w),
                    "completed_buildings": sum(h["n_buildings"] for h in comp_w),
                    "completed_road_points": sum(
                        1 for n, o in outcome.items() if o["status"] == "completed"),
                    "missed_road_points": sum(
                        1 for n, o in outcome.items() if o["status"] == "missed"),
                    "unsafe_egress_road_points": sum(
                        1 for n, o in outcome.items() if o["status"] == "unsafe_egress"),
                }
            trips_fix = sum(len(v["log"]) for v in veh_fix)
            trips_old = sum(len(v["log"]) for v in veh_old)
            runs[f"D{int(D)}_k{k}"] = {
                "dispatch_delay_min": D, "vehicles": k,
                "fixed": {**tally(out_fix), "trips_dispatched": trips_fix},
                "original": {**tally(out_old), "trips_dispatched": trips_old},
                "repeat_visits_removed": trips_old - trips_fix,
            }
            f, o = runs[f"D{int(D)}_k{k}"]["fixed"], runs[f"D{int(D)}_k{k}"]["original"]
            print(f"D={D} k={k}: fixed {f['completed_walk_nodes']}/{len(homes)} nodes, "
                  f"{f['completed_buildings']} buildings, {f['trips_dispatched']} trips | "
                  f"original {o['completed_walk_nodes']}/{len(homes)}, "
                  f"{o['completed_buildings']}, {o['trips_dispatched']} trips", flush=True)

    moved = any(r["fixed"]["completed_walk_nodes"] != r["original"]["completed_walk_nodes"]
                or r["fixed"]["completed_buildings"] != r["original"]["completed_buildings"]
                for r in runs.values())
    head = runs[f"D{int(DISPATCH[0])}_k4"]
    result = {
        "schema_version": 1,
        "title": "Assisted pickup re-run with the two scheduler defects repaired "
                 "(HQ decision 4)",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                                     capture_output=True, text=True).stdout.strip(),
        "rule_doc": "docs/auto/briefs/TRUCK_CREW_REPLAY_DECISIONS.md decision 4",
        "compares_with": "data/processed/vehicle_pickup_intervention_yeongdeok.json "
                         "(committed, unchanged)",
        "defects_repaired": [
            "outcome keyed by drive node while dispatch was per walk node, so one road "
            "point could be visited several times and the node counts were really "
            "road-point counts",
            "an unsafe-egress pickup advanced the vehicle's clock, wrote no log entry, and "
            "left the vehicle at its previous location",
        ],
        "population": {"credible_walk_nodes": len(homes),
                       "distinct_road_points": distinct,
                       "credible_buildings": sum(h["n_buildings"] for h in homes)},
        "committed_result": COMMITTED,
        "headline_moved": bool(moved),
        "headline_fixed": {"completed_walk_nodes": head["fixed"]["completed_walk_nodes"],
                           "completed_buildings": head["fixed"]["completed_buildings"]},
        "parameters": {"W_min": W, "margin_min": MARGIN, "t_load_min": T_LOAD,
                       "t_unload_min": T_UNLOAD, "fleets": FLEETS,
                       "dispatch_delays": DISPATCH},
        "runs": runs,
        "seconds": round(time.monotonic() - t0, 1),
    }
    OUT.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(REPO)}; headline moved: {moved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
