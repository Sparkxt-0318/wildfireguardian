#!/usr/bin/env python
"""One feasible intervention on the credible walk-out failures: assisted pickup by a small,
explicitly counted fleet with explicit timing. Rules: docs/vehicle_pickup_intervention.md
(pre-registered). Reads data/processed/building_origins_observed_grading_yeongdeok.json
(the diagnosed no-safe-route nodes); writes
data/processed/vehicle_pickup_intervention_yeongdeok.json and appends §4 to the doc.

    python scripts/run_vehicle_pickup_intervention.py
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
    RescueConfig, assess_destinations, node_survival_time, rescuer_route,
)

from run_real_roads_real_hazard_slope import REAL_OSM_SCAN_STRIDE  # noqa: E402
from run_rescue_routing_full import materialise_snapshots  # noqa: E402
from run_rescue_routing_real_hazard import build_scenario  # noqa: E402

DIAG = REPO / "data/processed/building_origins_observed_grading_yeongdeok.json"
OUT = REPO / "data/processed/vehicle_pickup_intervention_yeongdeok.json"
DOC = REPO / "docs/vehicle_pickup_intervention.md"
FLEETS = [1, 2, 3, 4, 6, 8]
DISPATCH = [30.0, 15.0]
T_LOAD, T_UNLOAD, MARGIN, W = 10.0, 10.0, 12.0, 75.0


def schedule(sc, cfg, homes, refuge_nodes, k, D):
    """Earliest-deadline-first assignment of k vehicles (round-robin over depots).

    A pickup completes iff a survival-aware ingress route from the vehicle's current
    location reaches the home by deadline − MARGIN and a survival-aware egress route to
    some rescue-reachable refuge exists afterwards; each leg within W. Deterministic."""
    depot_nodes = [sc.drive.nearest_node(d.x, d.y) for d in sc.depots]
    vehicles = [{"id": i, "at": depot_nodes[i % len(depot_nodes)], "free": D, "log": []} for i in range(k)]
    pending = sorted(homes, key=lambda h: h["deadline"])
    outcome = {h["drive_node"]: None for h in homes}
    while pending:
        h = pending.pop(0)
        best = None
        for v in vehicles:
            rt = rescuer_route(sc.drive, v["at"], h["drive_node"], sc.hazard, cfg, departure_min=v["free"])
            if not (rt.reached and not rt.enters_hazard):
                continue
            arr = v["free"] + rt.total_time_min
            if arr + MARGIN > h["deadline"]:
                continue
            if best is None or arr < best[1]:
                best = (v, arr, rt)
        if best is None:
            outcome[h["drive_node"]] = {"status": "missed", "reason": "no vehicle reaches it safely before deadline − margin"}
            continue
        v, arr, rt = best
        dep_out = arr + T_LOAD
        eg = None
        for rn in refuge_nodes:
            r = rescuer_route(sc.drive, h["drive_node"], rn, sc.hazard, cfg, departure_min=dep_out)
            if r.reached and not r.enters_hazard and (eg is None or r.total_time_min < eg[1].total_time_min):
                eg = (rn, r)
        if eg is None:
            outcome[h["drive_node"]] = {"status": "unsafe_egress", "vehicle": v["id"], "arrival_min": round(arr, 1)}
            v["free"] = dep_out; continue
        v["at"] = eg[0]; v["free"] = dep_out + eg[1].total_time_min + T_UNLOAD
        v["log"].append({"home": h["drive_node"], "arrival_min": round(arr, 1), "deadline_min": h["deadline"], "refuge_node": int(eg[0]), "free_at": round(v["free"], 1)})
        outcome[h["drive_node"]] = {"status": "completed", "vehicle": v["id"], "arrival_min": round(arr, 1), "refuge_node": int(eg[0]), "delivered_min": round(v["free"] - T_UNLOAD, 1)}
    return outcome, vehicles


def schedule_fixed(sc, cfg, homes, refuge_nodes, k, D):
    """`schedule` with the two defects the truck-crew build found, repaired.

    Added 2026-09-14 on HQ's instruction (`docs/auto/briefs/TRUCK_CREW_REPLAY_DECISIONS.md`
    decision 4). `schedule` above is UNCHANGED and still produces
    `data/processed/vehicle_pickup_intervention_yeongdeok.json`; this twin writes a new
    artifact under a new name so the committed numbers are not disturbed.

    Defect 1 — **the outcome was keyed by drive node while dispatch was per walk node.**
    In the committed run the 24 credible walk nodes collapse onto 12 distinct drive nodes
    (one of them six times), so `outcome` held 12 entries, a vehicle was sent to the same
    road point up to six times, and 「9 of 24 nodes completed」 really meant 「walk nodes
    whose drive node was completed」. Repair: walk nodes are grouped onto their drive node
    and each road point is visited **once**; the per-walk-node outcome is then read off
    its road point, which is what the original counting was trying to express.

    Defect 2 — **an unsafe-egress pickup advanced the vehicle's clock and wrote no log
    entry**, and left the vehicle at its PREVIOUS location although it had driven to the
    home. Repair: the leg is logged, and the vehicle is left at the home it actually
    reached. This changes where the vehicle continues from, so it can change later trips.
    """
    depot_nodes = [sc.drive.nearest_node(d.x, d.y) for d in sc.depots]
    vehicles = [{"id": i, "at": depot_nodes[i % len(depot_nodes)], "free": D, "log": []}
                for i in range(k)]
    # defect 1: one road point is one pickup, carrying every walk node behind it
    by_node: dict[int, dict] = {}
    for h in homes:
        g = by_node.setdefault(int(h["drive_node"]), {
            "drive_node": int(h["drive_node"]), "deadline": h["deadline"],
            "walk_nodes": [], "n_buildings": 0})
        g["walk_nodes"].append(h.get("walk_node", h.get("node")))
        g["n_buildings"] += int(h.get("n_buildings", 0))
        g["deadline"] = min(g["deadline"], h["deadline"])
    pending = sorted(by_node.values(), key=lambda g: g["deadline"])
    outcome = {g["drive_node"]: None for g in pending}
    while pending:
        h = pending.pop(0)
        best = None
        for v in vehicles:
            rt = rescuer_route(sc.drive, v["at"], h["drive_node"], sc.hazard, cfg,
                               departure_min=v["free"])
            if not (rt.reached and not rt.enters_hazard):
                continue
            arr = v["free"] + rt.total_time_min
            if arr + MARGIN > h["deadline"]:
                continue
            if best is None or arr < best[1]:
                best = (v, arr, rt)
        if best is None:
            outcome[h["drive_node"]] = {"status": "missed",
                                        "reason": "no vehicle reaches it safely before deadline - margin"}
            continue
        v, arr, rt = best
        dep_out = arr + T_LOAD
        eg = None
        for rn in refuge_nodes:
            r = rescuer_route(sc.drive, h["drive_node"], rn, sc.hazard, cfg, departure_min=dep_out)
            if r.reached and not r.enters_hazard and (eg is None or r.total_time_min < eg[1].total_time_min):
                eg = (rn, r)
        if eg is None:
            # defect 2: log the leg, and leave the vehicle where it actually is
            v["at"] = h["drive_node"]
            v["free"] = dep_out
            v["log"].append({"home": h["drive_node"], "arrival_min": round(arr, 1),
                             "deadline_min": h["deadline"], "refuge_node": None,
                             "free_at": round(v["free"], 1), "status": "unsafe_egress"})
            outcome[h["drive_node"]] = {"status": "unsafe_egress", "vehicle": v["id"],
                                        "arrival_min": round(arr, 1)}
            continue
        v["at"] = eg[0]
        v["free"] = dep_out + eg[1].total_time_min + T_UNLOAD
        v["log"].append({"home": h["drive_node"], "arrival_min": round(arr, 1),
                         "deadline_min": h["deadline"], "refuge_node": int(eg[0]),
                         "free_at": round(v["free"], 1), "status": "completed"})
        outcome[h["drive_node"]] = {"status": "completed", "vehicle": v["id"],
                                    "arrival_min": round(arr, 1), "refuge_node": int(eg[0]),
                                    "delivered_min": round(v["free"] - T_UNLOAD, 1)}
    return outcome, vehicles, by_node


def main() -> int:
    t0 = time.monotonic()
    diag = json.loads(DIAG.read_text(encoding="utf-8"))
    cred = [d for d in diag["diagnosis"] if d["credible"]]
    tmp = Path(tempfile.mkdtemp(prefix="wfg-vp-"))
    try:
        materialise_snapshots(tmp / "yeongdeok_2025")
        cfg = RescueConfig(use_osm=True, osm_cache_dir=str(tmp), scan_stride=REAL_OSM_SCAN_STRIDE, responder_time_budget_min=W)
        sc = build_scenario(cfg)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    depot_nodes = [sc.drive.nearest_node(d.x, d.y) for d in sc.depots]
    homes = []
    for d in cred:
        hd = int(d["drive_node"]); x, y = sc.drive.node_xy(hd)
        dl = node_survival_time(sc.hazard, x, y, cfg.vehicle_cutoff)
        homes.append({"walk_node": d["node"], "drive_node": hd, "n_buildings": d["n_buildings"], "deadline": (None if math.isinf(dl) else float(dl)), "drive_snap_m": d["drive_snap_m"]})
    finite = [h for h in homes if h["deadline"] is not None]
    for h in homes:
        if h["deadline"] is None:
            h["deadline"] = 1e9   # never reaches the vehicle cutoff in the forecast window: no deadline binds
    runs = {}
    for D in DISPATCH:
        cfgD = replace(cfg, responder_dispatch_delay_min=D)
        ass = assess_destinations(sc.destinations, sc.drive, depot_nodes, sc.hazard, cfgD)
        refuge_nodes = sorted({a.node for a in ass if a.rescue_reachable})
        for k in FLEETS:
            outcome, vehicles = schedule(sc, cfgD, homes, refuge_nodes, k, D)
            comp = [h for h in homes if outcome[h["drive_node"]]["status"] == "completed"]
            runs[f"D{int(D)}_k{k}"] = {
                "dispatch_delay_min": D, "vehicles": k, "refuges_rescue_reachable": len(refuge_nodes),
                "completed_nodes": len(comp), "completed_buildings": sum(h["n_buildings"] for h in comp),
                "missed_nodes": sum(1 for h in homes if outcome[h["drive_node"]]["status"] == "missed"),
                "unsafe_egress_nodes": sum(1 for h in homes if outcome[h["drive_node"]]["status"] == "unsafe_egress"),
                "last_delivery_min": (max(outcome[h["drive_node"]]["delivered_min"] for h in comp) if comp else None),
                "per_home": {str(h["drive_node"]): outcome[h["drive_node"]] for h in homes},
                "vehicle_logs": [v["log"] for v in vehicles],
            }
            print(f"D={D} k={k}: completed {len(comp)}/{len(homes)} nodes ({runs[f'D{int(D)}_k{k}']['completed_buildings']} buildings), missed {runs[f'D{int(D)}_k{k}']['missed_nodes']}, unsafe egress {runs[f'D{int(D)}_k{k}']['unsafe_egress_nodes']}", flush=True)
    access_only = sum(1 for d in cred if d["vehicle_reachable_W75"])
    result = {
        "schema_version": 1, "title": "Assisted pickup with an explicit fleet and timing on the credible no-safe-route nodes (영덕)",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip(),
        "rule_doc": "docs/vehicle_pickup_intervention.md §1-§3 (pre-registered)",
        "population": {"credible_nodes": len(homes), "credible_buildings": sum(h["n_buildings"] for h in homes), "finite_deadline_nodes": len(finite),
                       "deadline_min": {"min": (min(h["deadline"] for h in finite) if finite else None), "median": (sorted(h["deadline"] for h in finite)[len(finite)//2] if finite else None), "max": (max(h["deadline"] for h in finite) if finite else None)}},
        "baselines": {"walk_only_completed": 0, "access_only_reachable_nodes_W75_D30": access_only},
        "parameters": {"W_min": W, "margin_min": MARGIN, "t_load_min": T_LOAD, "t_unload_min": T_UNLOAD, "vehicle_cutoff": cfg.vehicle_cutoff, "fleets": FLEETS, "dispatch_delays": DISPATCH,
                       "deadline": "earliest forecast time the home's drive node reaches the vehicle cutoff (node_survival_time)", "policy": "earliest-deadline-first, one home per trip, egress to nearest rescue-reachable refuge, vehicle continues from the refuge"},
        "homes": homes, "runs": runs, "seconds": round(time.monotonic() - t0, 1),
    }
    OUT.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    L = ["", f"_Run {result['generated_utc']} at `{result['git_commit'][:7]}`; artifact `{OUT.relative_to(REPO)}`; {len(homes)} credible nodes / {result['population']['credible_buildings']} buildings; deadlines (forecast vehicle cutoff at the home) min/median/max {result['population']['deadline_min']}; {result['seconds']:.0f} s._", "",
         f"Baselines: walking completes 0 (the class is defined by it); access-only reading (a survival-aware route exists, W = 75, D = 30, no fleet, no timing): {access_only} of {len(homes)} nodes.", "",
         "| dispatch delay | vehicles | completed nodes | completed buildings | missed (deadline) | unsafe egress | last delivery (min) |", "|---|---:|---:|---:|---:|---:|---:|"]
    for key, r in runs.items():
        L.append(f"| {int(r['dispatch_delay_min'])} | {r['vehicles']} | {r['completed_nodes']} | {r['completed_buildings']} | {r['missed_nodes']} | {r['unsafe_egress_nodes']} | {r['last_delivery_min']} |")
    DOC.write_text(DOC.read_text(encoding="utf-8").rstrip("\n") + "\n" + "\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
