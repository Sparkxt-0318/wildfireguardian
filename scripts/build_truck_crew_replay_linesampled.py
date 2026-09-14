#!/usr/bin/env python
"""The line-sampled router arm of the truck-crew replay (HQ round-two answer 1).

Rule: `docs/truck_crew_replay.md` §10, written BEFORE this ran. The only difference from
§7's v2 run is the router's admissibility test: `rescuer_route_line_sampled` reads the same
150 m interpolated line the abort rule v2 reads, instead of cell membership at route nodes.
`rescuer_route` is untouched, the scheduler is untouched, and the abort rule keeps its v2
name and definition.

The arm is run by BINDING the name `rescuer_route` to `rescuer_route_line_sampled` in the two
modules that call it, for the duration of this script. Neither module is edited; the binding
is recorded in the artifact.

Writes data/processed/truck_crew_replay_yeongdeok_v2_linesampled.json and appends §11.

    python scripts/build_truck_crew_replay_linesampled.py
"""
from __future__ import annotations

import functools
import hashlib
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

from wildfireguardian.routing import rescue as rescue_mod  # noqa: E402
from wildfireguardian.routing.rescue import (  # noqa: E402
    RescueConfig, assess_destinations, edge_line_closing_minutes,
    rescuer_route_line_sampled,
)

import build_truck_crew_replay as V1  # noqa: E402
import build_truck_crew_replay_v2 as V2  # noqa: E402
import run_vehicle_pickup_intervention as VP  # noqa: E402
from regrade_three_way import MISS, first_seen_grid  # noqa: E402
from run_real_roads_real_hazard_slope import REAL_OSM_SCAN_STRIDE  # noqa: E402
from run_rescue_routing_full import materialise_snapshots  # noqa: E402
from run_rescue_routing_real_hazard import build_scenario  # noqa: E402

OUT = REPO / "data/processed/truck_crew_replay_yeongdeok_v2_linesampled.json"
DOC = REPO / "docs/truck_crew_replay.md"
#: §10b: the three populations HQ named, on both fields.
POPS = ("core_credible", "no_safe_walk", "immobile_30pct")
FLEETS = {"core_credible": (4, 2, 6), "no_safe_walk": (4, 2, 6), "immobile_30pct": (4,)}


def main() -> int:
    t0 = time.monotonic()
    tmp = Path(tempfile.mkdtemp(prefix="wfg-ls-"))
    try:
        prov = materialise_snapshots(tmp / "yeongdeok_2025")
        cfg = RescueConfig(use_osm=True, osm_cache_dir=str(tmp),
                           scan_stride=REAL_OSM_SCAN_STRIDE,
                           responder_time_budget_min=V1.W,
                           responder_dispatch_delay_min=V1.DISPATCH)
        sc_canon = build_scenario(cfg)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"[1/4] scenario: drive={sc_canon.drive.graph.number_of_nodes()} nodes", flush=True)

    z = np.load(V1.NPZ)
    fs, tobs = first_seen_grid(z)
    fields = {
        "canonical": sc_canon.hazard,
        "leakfree": V2.hazard_from_npz(V2.LEAKFREE),
    }
    depot_nodes = [int(sc_canon.drive.nearest_node(d.x, d.y)) for d in sc_canon.depots]
    all_pops = V2.populations(cfg)

    runs: dict = {}
    edge_stats: dict = {}
    orig = rescue_mod.rescuer_route
    try:
        for fname, hazard in fields.items():
            sc = sc_canon if fname == "canonical" else replace(sc_canon, hazard=hazard)
            te = time.monotonic()
            closing = edge_line_closing_minutes(
                sc.drive, hazard, cfg.vehicle_cutoff, cfg.ingress_sample_spacing_m)
            finite = [v for v in closing.values() if math.isfinite(v)]
            edge_stats[fname] = {
                "directed_edges": len(closing),
                "edges_that_ever_close": len(finite),
                "edges_closed_at_or_before_t0": sum(1 for v in finite if v <= 0.0),
                "seconds": round(time.monotonic() - te, 1),
            }
            print(f"[2/4] {fname}: {edge_stats[fname]['edges_that_ever_close']} of "
                  f"{len(closing)} directed edges ever close; "
                  f"{edge_stats[fname]['edges_closed_at_or_before_t0']} already cut at t=0 "
                  f"({edge_stats[fname]['seconds']}s)", flush=True)

            # §10a: bind the name, edit nothing
            patched = functools.partial(rescuer_route_line_sampled, edge_closing=closing)
            rescue_mod.rescuer_route = patched
            VP.rescuer_route = patched
            V1.rescuer_route = patched
            try:
                ass = assess_destinations(sc.destinations, sc.drive, depot_nodes,
                                          sc.hazard, cfg)
                refuges = sorted({a.node for a in ass if a.rescue_reachable})
                for pname in POPS:
                    pdef = all_pops[pname]
                    pickups, pop = V1.build_population(sc, cfg, select=pdef["select"])
                    grid = sc.hazard.grid
                    obs_first: dict[int, float] = {}
                    for p in pickups:
                        rc = V1._cell(grid, p["x"], p["y"])
                        p["cell"] = None if rc is None else [rc[0], rc[1]]
                        p["observed_first_seen_min"] = None
                        if rc is not None and math.isfinite(fs[rc]):
                            p["observed_first_seen_min"] = float(fs[rc])
                            obs_first[p["drive_node"]] = float(fs[rc])
                    for k in FLEETS[pname]:
                        tk = time.monotonic()
                        r = V1.run_fleet(sc, cfg, pickups, refuges, depot_nodes, k,
                                         fs, tobs, obs_first)
                        r = V2.add_v2_abort(sc, cfg, hazard, r)
                        r["population"], r["field"], r["arm"] = pname, fname, "line_sampled"
                        r["refuges_rescue_reachable"] = len(refuges)
                        runs[f"{fname}.{pname}.k{k}"] = r
                        v2 = r["v2"]
                        print(f"[3/4] {fname}/{pname}/k{k}: ordered {v2['trips_ordered']}, "
                              f"reached {v2['reached_before_observed_closure']}, "
                              f"aborted {v2['aborted_by_rule']} "
                              f"({time.monotonic()-tk:.0f}s)", flush=True)
            finally:
                rescue_mod.rescuer_route = orig
                VP.rescuer_route = orig
                V1.rescuer_route = orig
    finally:
        rescue_mod.rescuer_route = orig
        VP.rescuer_route = orig
        V1.rescuer_route = orig

    payload = {
        "schema_version": 1,
        "title": "Truck-crew replay, line-sampled router arm (HQ round-two answer 1)",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                                     capture_output=True, text=True).stdout.strip(),
        "rule_doc": "docs/truck_crew_replay.md §10 (pre-registered)",
        "compares_with": "data/processed/truck_crew_replay_v2_yeongdeok.json (the v2 arm; "
                         "same scheduler, same abort rule, cell-membership router)",
        "arm": {
            "router": "wildfireguardian.routing.rescue.rescuer_route_line_sampled",
            "committed_router_unchanged": "rescuer_route",
            "abort_rule": "v2, unchanged (docs/truck_crew_replay.md §6a)",
            "how_run": "the name `rescuer_route` was bound to the line-sampled router in "
                       "wildfireguardian.routing.rescue, run_vehicle_pickup_intervention "
                       "and build_truck_crew_replay for the duration of the run; no module "
                       "was edited",
            "edge_admissibility": "enter edge e no later than E_e = min_j (T_j - t_j) over "
                                  "its 150 m sampled points",
        },
        "label_ko": V1.LABEL_KO,
        "field_is_a_hindcast": (
            "the committed field is hindcast-track under the project's own protocol "
            "(docs/benchmark/results_v0.1.md §2); these runs measure what the routing "
            "method gains from a good spread field, not the accuracy of a forecast"),
        "inputs": {
            "hazard_npz_canonical": str(V1.NPZ.relative_to(REPO)),
            "hazard_npz_canonical_sha256": hashlib.sha256(V1.NPZ.read_bytes()).hexdigest(),
            "hazard_npz_leakfree": str(V2.LEAKFREE.relative_to(REPO)),
            "hazard_npz_leakfree_sha256": hashlib.sha256(V2.LEAKFREE.read_bytes()).hexdigest(),
            "population": str(V1.GRADING.relative_to(REPO)),
            "snapshots": prov,
        },
        "parameters": {
            "horizon_min": V1.HORIZON, "dispatch_delay_min": V1.DISPATCH,
            "responder_budget_min": V1.W, "safety_margin_min": V1.MARGIN,
            "vehicle_cutoff": cfg.vehicle_cutoff,
            "ingress_sample_spacing_m": cfg.ingress_sample_spacing_m,
            "miss_allowances": list(MISS),
            "populations": list(POPS), "fleets": {k: list(v) for k, v in FLEETS.items()},
        },
        "edge_closing_stats": edge_stats,
        "runs": runs,
        "caveats": [
            "the committed field is a hindcast, not a forecast",
            "buildings are not households; a pickup is a road point, not a door",
            "nothing here is quotable (HQ decision 1); no success line is filled",
            "영덕 only, one fire, one observation",
        ],
        "seconds": round(time.monotonic() - t0, 1),
    }
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[4/4] wrote {OUT.relative_to(REPO)} ({OUT.stat().st_size/1024:.0f} KiB)", flush=True)
    print("\n".join(append_results(payload)))
    return 0


def append_results(payload: dict) -> list[str]:
    v2 = json.loads((REPO / "data/processed/truck_crew_replay_v2_yeongdeok.json")
                    .read_text(encoding="utf-8"))["runs"]
    L = ["", "## 11. Results, line-sampled arm (appended by "
             "`scripts/build_truck_crew_replay_linesampled.py`; §10 is not edited after "
             "the run)", "",
         f"_Run {payload['generated_utc']} at `{payload['git_commit'][:7]}`; artifact "
         f"`data/processed/truck_crew_replay_yeongdeok_v2_linesampled.json`; "
         f"{payload['seconds']:.0f} s._", "",
         "**How much of the road network the line test cuts**, before any trip is planned:",
         "", "| field | directed edges | ever close | already cut at t = 0 |",
         "|---|---:|---:|---:|"]
    for f, e in payload["edge_closing_stats"].items():
        L.append(f"| {f} | {e['directed_edges']} | {e['edges_that_ever_close']} | "
                 f"{e['edges_closed_at_or_before_t0']} |")
    L += ["", "**The four counts, line-sampled router beside the v2 (cell-membership) "
              "router.** Same scheduler, same abort rule v2, same populations; only the "
              "router's admissibility test differs.", "",
          "| field | population | k | arm | ordered | reached | not reached | aborted | "
          "no abort minute | ingress inadmissible (m = 0) |",
          "|---|---|---:|---|---:|---:|---:|---:|---:|---:|"]
    for key in sorted(payload["runs"]):
        ls = payload["runs"][key]["v2"]
        f, n, k = key.split(".")
        row = (f"| {f} | {n} | {k[1:]} | **line-sampled** | {ls['trips_ordered']} | "
               f"{ls['reached_before_observed_closure']} | {ls['not_reached']} | "
               f"{ls['aborted_by_rule']} | {ls['trips_with_no_abort_minute']} | "
               f"{ls['trips_with_an_inadmissible_ingress_leg_m0']} |")
        L.append(row)
        if key in v2:
            c = v2[key]["v2"]
            L.append(f"| {f} | {n} | {k[1:]} | v2 (cell) | {c['trips_ordered']} | "
                     f"{c['reached_before_observed_closure']} | {c['not_reached']} | "
                     f"{c['aborted_by_rule']} | {c['trips_with_no_abort_minute']} | "
                     f"{c['trips_with_an_inadmissible_ingress_leg_m0']} |")
    L += ["", "Nothing here is quotable (HQ decision 1). The committed field is a hindcast "
              "(§10c), so these counts measure what the routing method gains from a given "
              "spread field, not the accuracy of a forecast.", ""]
    DOC.write_text(DOC.read_text(encoding="utf-8").rstrip("\n") + "\n" + "\n".join(L) + "\n",
                   encoding="utf-8")
    return L


if __name__ == "__main__":
    raise SystemExit(main())
