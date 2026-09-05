#!/usr/bin/env python
"""End-to-end rescue-aware evacuation routing on the 영덕 (Yeongdeok) extent.

Runs the resident- and rescuer-side rescue routing (see
``wildfireguardian.routing.rescue``) on a clearly-labelled SYNTHETIC fallback
scenario (the real FIRMS bundle is git-ignored, so it is absent in a fresh
clone / sandbox). To run on real data, point ``RescueConfig`` at real shelter /
depot files and an OSM network and feed a real ``HazardSequence`` — the
evaluation below is unchanged.

Outputs (small JSON committed; bulk NPZ git-ignored):
  data/processed/rescue_routing.json   four-way split, exposure contrasts,
                                       dispatch list, unreachable set, sensitivity
                                       sweep, provenance (synthetic/assumed tags).
  data/processed/rescue_routing.npz    arrays for scripts/make_rescue_figures.py.

Run:  python scripts/run_rescue_routing.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from wildfireguardian.routing.rescue import RescueConfig  # noqa: E402
from wildfireguardian.routing.rescue_demo import (  # noqa: E402
    build_real_demo,
    build_synthetic_demo,
    run_pipeline,
    sensitivity_sweep,
)


def _node_survival_times(hazard, xs, ys, cutoff) -> np.ndarray:
    """Earliest forecast slice each (x, y) reaches ``cutoff`` (vectorised; inf if never)."""
    surv = np.full(len(xs), np.inf)
    for t in hazard.times_min:
        p = hazard.prob_at_points(xs, ys, float(t))
        newly = (p >= cutoff) & ~np.isfinite(surv)
        surv[newly] = float(t)
    return surv


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--route-cell-m", type=float, default=None)
    ap.add_argument("--hazard-cell-m", type=float, default=None)
    ap.add_argument("--vehicle-cutoff", type=float, default=None)
    ap.add_argument("--vehicle-speed-kmh", type=float, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--synthetic", action="store_true",
                    help="force the fully-synthetic fallback (offline CI); default "
                         "is the REAL OSM partial-flip scenario")
    ap.add_argument("--out", default=str(REPO / "data" / "processed"))
    args = ap.parse_args()

    overrides = {k: v for k, v in {
        "route_cell_m": args.route_cell_m, "hazard_cell_m": args.hazard_cell_m,
        "vehicle_cutoff": args.vehicle_cutoff, "vehicle_speed_kmh": args.vehicle_speed_kmh,
        "seed": args.seed,
    }.items() if v is not None}
    if not args.synthetic:
        overrides["use_osm"] = True
    cfg = RescueConfig(**overrides)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    if args.synthetic:
        print("[1/4] building SYNTHETIC 영덕 scenario (labelled fallback) ...")
        scenario = build_synthetic_demo(cfg)
    else:
        print("[1/4] building REAL 영덕 scenario (OSM roads/refuges/depots; "
              "synthetic hazard+terrain) ...")
        scenario = build_real_demo(cfg)
    print(f"      sources: walk={scenario.walk_source} drive={scenario.drive_source} "
          f"shelters={scenario.shelters_source} depots={scenario.depots_source} "
          f"hazard={scenario.hazard_source} terrain={scenario.terrain_source}")
    print(f"      walk nodes={scenario.walk.graph.number_of_nodes()}, "
          f"drive nodes={scenario.drive.graph.number_of_nodes()}, "
          f"refuges={len(scenario.destinations)}, "
          f"depots={len(scenario.depots)}, origins={len(scenario.origins)}")

    print("[2/4] running resident + rescuer evaluation ...")
    results = run_pipeline(scenario, cfg)
    c = results.four_way_counts
    print(f"      four-way split (sum={sum(c.values())}=N): "
          f"saved={c['saved_by_rescue_reachable_refuge']}, safe={c['already_safe']}, "
          f"no-walk={c['no_safe_pedestrian_route']}, "
          f"no-ingress={c['no_surviving_vehicle_ingress']}")
    rex = results.resident_exposure
    print("      resident exposure a/b/c (prob·min): "
          f"{_m(rex['naive'])} / {_m(rex['future_aware_any'])} / {_m(rex['future_aware_rescue'])}; "
          f"policy-c changed refuge for {rex['policy_c_changed_refuge_count']} origins")
    pe = results.responder_exposure
    print(f"      responder exposure survival-aware/shortest-path: "
          f"{_m(pe['survival_aware'])} / {_m(pe['shortest_path'])}; "
          f"dispatch={pe['n_dispatch']}, unreachable={pe['n_unreachable']}")

    print("[3/4] sensitivity sweep (robustness of the reachable/unreachable split) ...")
    sweeps = sensitivity_sweep(scenario, cfg)
    vc = sweeps["vehicle_cutoff"]
    print("      vehicle-cutoff sweep no-ingress count: " +
          ", ".join(f"{k}->{v['counts']['no_surviving_vehicle_ingress']}"
                    for k, v in vc.items()))

    print("[4/4] writing JSON summary + NPZ arrays ...")
    summary = {
        "provenance": results.provenance,
        "n_origins": results.n_origins,
        "four_way_counts": results.four_way_counts,
        "four_way_sums_to_n": sum(results.four_way_counts.values()) == results.n_origins,
        "n_refuges": len(results.dest_assessments),
        "n_refuges_rescue_reachable": results.n_refuges_rescue_reachable,
        "destinations": [a.as_dict() for a in results.dest_assessments],
        "resident_exposure": results.resident_exposure,
        "responder_exposure": results.responder_exposure,
        "dispatch_top20": [e.as_dict() for e in results.dispatch[:20]],
        "unreachable_homes": results.unreachable_homes,
        "sensitivity_sweep": sweeps,
        # SESSION 8 Phase 1 — ADDITIVE key. Human-facing margin advisories
        # (round-trip margin, band, recommendation, trigger line for the
        # top-20, basis). Machine-facing keys above are byte-compatible with
        # the pre-session artifact.
        "margin_advisories": results.advisories,
    }
    (out / "rescue_routing.json").write_text(json.dumps(summary, indent=2, default=str))

    # Arrays for the figure script.
    drive = scenario.drive
    dnodes = list(drive.graph.nodes)
    dx = np.array([drive.graph.nodes[n]["x"] for n in dnodes], float)
    dy = np.array([drive.graph.nodes[n]["y"] for n in dnodes], float)
    dsurv = _node_survival_times(scenario.hazard, dx, dy, cfg.vehicle_cutoff)
    g = scenario.hazard_grid
    dest_xy = np.array([[a.x, a.y] for a in results.dest_assessments], float)
    dest_rr = np.array([a.rescue_reachable for a in results.dest_assessments], bool)
    dest_safe = np.array([a.safe for a in results.dest_assessments], bool)
    depot_xy = np.array([[d.x, d.y] for d in scenario.depots], float)
    unreach_xy = np.array([[h["x"], h["y"]] for h in results.unreachable_homes],
                          float).reshape(-1, 2)
    ex = results.examples
    np.savez_compressed(
        out / "rescue_routing.npz",
        grid_extent=np.array([g.minx, g.miny, g.maxx, g.maxy, g.cell_size_m], float),
        haz_times=scenario.hazard.times_min,
        haz_stack=np.array(scenario.hazard.surfaces, dtype=np.float32),
        ignition_xy=np.array(scenario.ignition_xy, float),
        drive_xy=np.column_stack([dx, dy]),
        drive_survival=np.where(np.isfinite(dsurv), dsurv, -1.0),  # -1 == never cut
        dest_xy=dest_xy, dest_rescue_reachable=dest_rr, dest_safe=dest_safe,
        depot_xy=depot_xy, unreachable_xy=unreach_xy,
        responder_route_xy=np.array(ex.get("responder_route_xy", []), float).reshape(-1, 2),
        responder_depot_xy=np.array(ex.get("responder_depot_xy", []), float).reshape(-1),
        responder_home_xy=np.array(ex.get("responder_home_xy", []), float).reshape(-1),
        resident_naive_xy=np.array(ex.get("resident_naive_xy", []), float).reshape(-1, 2),
        resident_rescue_xy=np.array(ex.get("resident_rescue_xy", []), float).reshape(-1, 2),
        resident_origin_xy=np.array(ex.get("resident_origin_xy", []), float).reshape(-1),
    )
    print(f"done. wrote {out}/rescue_routing.json and rescue_routing.npz")
    return 0


def _m(d) -> str:
    v = d.get("mean") if isinstance(d, dict) else None
    return "n/a" if v is None else f"{v:.2f}"


if __name__ == "__main__":
    raise SystemExit(main())
