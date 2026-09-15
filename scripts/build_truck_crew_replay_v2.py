#!/usr/bin/env python
"""Truck-crew replay v2: HQ's decisions 2, 3 and 6 on the v1 report.

Rule: `docs/truck_crew_replay.md` §6, written BEFORE this ran, transcribing
`docs/auto/briefs/TRUCK_CREW_REPLAY_DECISIONS.md`. Nothing here re-implements routing,
snapping, scheduling or grading; the v1 build and the pipeline own those and are imported.

What is new against v1:
  - **abort rule v2** on the vehicle's own passage, in continuous minutes (decision 2);
  - **four populations** instead of one, so the 30 % immobile draw stops driving the
    headline (decision 3);
  - a **leak-free field arm** beside the canonical one (decision 6).

Writes data/processed/truck_crew_replay_v2_yeongdeok.json and appends §7 to the doc.
The v1 artifact, page and outputs are NOT touched: new results, new filenames.

    python scripts/build_truck_crew_replay_v2.py
"""
from __future__ import annotations

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

from wildfireguardian.routing.hazard import HazardSequence  # noqa: E402
from wildfireguardian.routing.rescue import (  # noqa: E402
    RescueConfig, assess_destinations, rescuer_route, sample_corridor_points,
)
from wildfireguardian.spread_v2.grid import CoarseGrid  # noqa: E402

from build_truck_crew_replay import (  # noqa: E402
    DISPATCH, GRADING, HORIZON, LABEL_KO, MARGIN, NPZ, T_LOAD, T_UNLOAD, W,
    _cell, _f, build_population, run_fleet,
)
from regrade_three_way import MISS, first_seen_grid  # noqa: E402
from run_real_roads_real_hazard_slope import REAL_OSM_SCAN_STRIDE  # noqa: E402
from run_rescue_routing_full import materialise_snapshots  # noqa: E402
from run_rescue_routing_real_hazard import build_scenario  # noqa: E402

PROC = REPO / "data/processed"
LEAKFREE = PROC / "routing_demo_leakfree.npz"
OUT = REPO / "data/processed/truck_crew_replay_v2_yeongdeok.json"
DOC = REPO / "docs/truck_crew_replay.md"

#: k = 4 is the headline everywhere. The two honest-core populations also get k = 2 and 6
#: because they are cheap; the immobile sensitivity is run at k = 4 only (§6).
FLEETS_FULL = (4, 2, 6)
FLEETS_ONE = (4,)


def _git() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def hazard_from_npz(path: Path) -> HazardSequence:
    """A HazardSequence over an npz written on the canonical canvas.

    Constructing the object, not re-implementing a model: the same three lines
    `run_rescue_routing_real_hazard.canonical_hazard` uses, over a chosen file so the
    leak-free field can be swapped in without touching the scenario builder.
    """
    z = np.load(path)
    haz = z["haz_stack"].astype(np.float32)
    times = np.asarray(z["haz_times"], float)
    xmin, ymin, xmax, ymax, cell = [float(v) for v in z["grid_extent"]]
    grid = CoarseGrid(minx=xmin, miny=ymin, maxx=xmax, maxy=ymax,
                      cell_size_m=cell, nrows=haz.shape[1], ncols=haz.shape[2])
    return HazardSequence(grid=grid, times_min=times,
                          surfaces=[haz[i] for i in range(haz.shape[0])])


# --- decision 2: the abort rule on the vehicle's own passage -----------------

def crossing_minutes(hazard: HazardSequence, xs, ys, cutoff: float) -> np.ndarray:
    """Minute each sampled point reaches ``cutoff``, interpolated linearly in time.

    `HazardSequence.prob_at_points` interpolates linearly between the forecast slices,
    so the crossing time is solved exactly from the two bracketing slice values rather
    than searched for: that IS the sampler's own interpolation (decision 2), and it is
    a continuous minute, not a slice index. ``inf`` where the point never reaches the
    cutoff inside the forecast window.
    """
    times = np.asarray(hazard.times_min, float)
    probs = np.array([hazard.prob_at_points(xs, ys, float(t)) for t in times])
    out = np.full(len(np.atleast_1d(xs)), np.inf)
    for i in range(len(times)):
        hit = (probs[i] >= cutoff) & ~np.isfinite(out)
        if not hit.any():
            continue
        if i == 0:
            out[hit] = 0.0
            continue
        p0, p1 = probs[i - 1][hit], probs[i][hit]
        span = p1 - p0
        frac = np.where(span > 0, (cutoff - p0) / np.where(span > 0, span, 1.0), 0.0)
        out[hit] = times[i - 1] + frac * (times[i] - times[i - 1])
    return out


def point_travel_minutes(net, path: list[int], seg_ids: np.ndarray) -> np.ndarray:
    """Travel minute from the route's start to each sampled point.

    Reads the sampler's own output: `sample_corridor_points` lays ``nseg + 1`` points
    evenly along segment *i*, so a point's share of that segment's travel time is its
    index within the segment. No geometry is recomputed here.
    """
    if len(path) < 2:
        return np.zeros(len(np.atleast_1d(seg_ids)))
    cum = [0.0]
    for i in range(len(path) - 1):
        cum.append(cum[-1] + net.graph[path[i]][path[i + 1]]["time_min"])
    out = np.zeros(len(seg_ids))
    for i in range(len(path) - 1):
        idx = np.where(seg_ids == i)[0]
        if len(idx) == 0:
            continue
        frac = np.zeros(len(idx)) if len(idx) == 1 else np.arange(len(idx)) / (len(idx) - 1)
        out[idx] = cum[i] + frac * (cum[i + 1] - cum[i])
    return out


def abort_v2(sc, cfg, route, hazard) -> dict:
    """Latest safe departure for one ingress route, and the abort minute from it.

    For every sampled point: the vehicle is there at ``d + t_i`` and the point reaches
    the cutoff at ``T_i``, so the trip is safe iff ``d + t_i < T_i`` for all i. The
    field is monotone in time on this scene, so the binding constraint is
    ``d* = min_i (T_i - t_i)`` and the abort minute is ``d* - 12``.
    """
    path = [int(n) for n in route]
    xs, ys, seg = sample_corridor_points(sc.drive, path, cfg.ingress_sample_spacing_m)
    T = crossing_minutes(hazard, xs, ys, cfg.vehicle_cutoff)
    t = point_travel_minutes(sc.drive, path, seg)
    slack = T - t
    finite = np.isfinite(slack)
    if not finite.any():
        return {"latest_safe_departure_min": None, "abort_min": None,
                "binding_point_index": None, "n_points": int(len(xs)),
                "never_closes_in_window": True}
    j = int(np.argmin(np.where(finite, slack, np.inf)))
    d_star = float(slack[j])
    return {"latest_safe_departure_min": round(d_star, 2),
            "abort_min": round(d_star - MARGIN, 2),
            "binding_point_index": j, "n_points": int(len(xs)),
            "binding_point_cutoff_min": _f(T[j]),
            "binding_point_travel_min": round(float(t[j]), 2),
            "never_closes_in_window": False}


def add_v2_abort(sc, cfg, hazard, run: dict) -> dict:
    """Attach the v2 abort quantities to every ordered trip of one fleet run."""
    trips = [t for v in run["per_vehicle"] for t in v["trips"]]
    for tr in trips:
        start, home = tr["start_node"], tr["drive_node"]
        rt = rescuer_route(sc.drive, start, home, sc.hazard, cfg,
                           departure_min=tr["ingress"]["departure_min"])
        if not (rt.reached and not rt.enters_hazard):
            raise RuntimeError(f"v2: ingress to {home} did not reproduce")
        a = abort_v2(sc, cfg, rt.route, hazard)
        tr["abort_v2"] = a
        late = a["abort_min"] is not None and tr["ingress"]["departure_min"] > a["abort_min"]
        tr["aborted_by_rule_v2"] = bool(late)
        tr["reached_before_observed_closure_v2"] = bool(
            (not late) and (tr["pickup_observed_first_seen_min"] is None
                            or tr["pickup_observed_first_seen_min"] > tr["eta_min"]))
    n = len(trips)
    k = sum(1 for t in trips if t["aborted_by_rule_v2"])
    m = sum(1 for t in trips if t["reached_before_observed_closure_v2"])
    run["v2"] = {
        "trips_ordered": n, "aborted_by_rule": k,
        "reached_before_observed_closure": m, "not_reached": n - k - m,
        "trips_with_no_abort_minute": sum(
            1 for t in trips if t["abort_v2"]["abort_min"] is None),
        "trips_with_an_inadmissible_ingress_leg_m0":
            run["trips_with_an_inadmissible_ingress_leg_m0"],
        "buildings_behind_reached_trips": sum(
            t["n_buildings"] for t in trips if t["reached_before_observed_closure_v2"]),
    }
    return run


# --- decision 3: the four populations ---------------------------------------

def credible_no_safe_walk() -> set[int]:
    """The diagnosis's credible no-safe-route nodes (the honest core)."""
    d = json.loads(GRADING.read_text(encoding="utf-8"))
    return {int(r["node"]) for r in d["diagnosis"] if r["credible"]}


def draw_at(cfg, fraction: float):
    """The pipeline's own deterministic immobile draw at a chosen fraction."""
    from types import SimpleNamespace

    from wildfireguardian.routing.rescue_demo import _immobile_homes

    def select(walk_nodes, no_safe, _immobile):
        drawn = _immobile_homes(SimpleNamespace(origins=walk_nodes),
                                replace(cfg, immobile_fraction=fraction))
        return set(drawn) | no_safe
    return select


def populations(cfg) -> dict:
    core = credible_no_safe_walk()
    return {
        "core_credible": {
            "label": "the credible no-safe-walk nodes (HQ decision 3a; includes the "
                     "10-node cluster)",
            "select": (lambda w, ns, im: core), "fleets": FLEETS_FULL, "headline": True},
        "no_safe_walk": {
            "label": "every no-safe-walk node in the forecast partition (3b)",
            "select": (lambda w, ns, im: set(ns)), "fleets": FLEETS_FULL, "headline": True},
        "immobile_10pct": {
            "label": "immobile draw at 0.10 plus the no-safe-walk class (3c, sensitivity)",
            "select": draw_at(cfg, 0.10), "fleets": FLEETS_ONE, "headline": False},
        "immobile_30pct": {
            "label": "immobile draw at 0.30 plus the no-safe-walk class (3c, sensitivity; "
                     "this is v1's population)",
            "select": draw_at(cfg, 0.30), "fleets": FLEETS_ONE, "headline": False},
    }


# --- the run matrix ---------------------------------------------------------

def main() -> int:
    t0 = time.monotonic()
    tmp = Path(tempfile.mkdtemp(prefix="wfg-tcr2-"))
    try:
        prov = materialise_snapshots(tmp / "yeongdeok_2025")
        cfg = RescueConfig(use_osm=True, osm_cache_dir=str(tmp),
                           scan_stride=REAL_OSM_SCAN_STRIDE,
                           responder_time_budget_min=W,
                           responder_dispatch_delay_min=DISPATCH)
        sc_canon = build_scenario(cfg)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"[1/5] scenario: drive={sc_canon.drive.graph.number_of_nodes()} nodes", flush=True)

    # the observation is the same file on both fields (verified identical), so the
    # grading clock never depends on which forecast planned the route
    z = np.load(NPZ)
    fs, tobs = first_seen_grid(z)
    fields = {
        "canonical": {"hazard": sc_canon.hazard, "npz": str(NPZ.relative_to(REPO)),
                      "note": "the committed field v1 used; known to be flattered by the "
                              "의성·안동 training leak (docs/leakfree_fold.md)"},
        "leakfree": {"hazard": hazard_from_npz(LEAKFREE),
                     "npz": str(LEAKFREE.relative_to(REPO)),
                     "note": "the leak-free refit (G3/WFG-032), about half the size; a "
                             "sensitivity arm, NOT the base (HQ decision 6)"},
    }
    depot_nodes = [int(sc_canon.drive.nearest_node(d.x, d.y)) for d in sc_canon.depots]
    pops = populations(cfg)

    runs: dict = {}
    pop_stats: dict = {}
    for fname, fdef in fields.items():
        sc = sc_canon if fname == "canonical" else replace(sc_canon, hazard=fdef["hazard"])
        ass = assess_destinations(sc.destinations, sc.drive, depot_nodes, sc.hazard, cfg)
        refuges = sorted({a.node for a in ass if a.rescue_reachable})
        for pname, pdef in pops.items():
            pickups, pop = build_population(sc, cfg, select=pdef["select"])
            grid = sc.hazard.grid
            obs_first: dict[int, float] = {}
            for p in pickups:
                rc = _cell(grid, p["x"], p["y"])
                p["cell"] = None if rc is None else [rc[0], rc[1]]
                p["observed_first_seen_min"] = None
                if rc is not None and math.isfinite(fs[rc]):
                    p["observed_first_seen_min"] = float(fs[rc])
                    obs_first[p["drive_node"]] = float(fs[rc])
            pop["label"] = pdef["label"]
            pop["refuges_rescue_reachable"] = len(refuges)
            pop_stats[f"{fname}.{pname}"] = pop
            for k in pdef["fleets"]:
                tk = time.monotonic()
                r = run_fleet(sc, cfg, pickups, refuges, depot_nodes, k, fs, tobs, obs_first)
                r = add_v2_abort(sc, cfg, fdef["hazard"], r)
                r["population"] = pname
                r["field"] = fname
                r["headline"] = pdef["headline"]
                runs[f"{fname}.{pname}.k{k}"] = r
                v2 = r["v2"]
                print(f"[2/5] {fname}/{pname}/k{k}: ordered {v2['trips_ordered']}, "
                      f"reached {v2['reached_before_observed_closure']}, "
                      f"aborted_v2 {v2['aborted_by_rule']} "
                      f"(v1 aborted {r['aborted_by_rule']}) "
                      f"({time.monotonic()-tk:.0f}s)", flush=True)

    payload = {
        "schema_version": 1,
        "title": "Truck-crew replay v2: passage-based abort rule, four populations, "
                 "leak-free arm (HQ decisions 2/3/6)",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _git(),
        "rule_doc": "docs/truck_crew_replay.md §6 (pre-registered, transcribing "
                    "docs/auto/briefs/TRUCK_CREW_REPLAY_DECISIONS.md)",
        "supersedes": "data/processed/truck_crew_replay_yeongdeok.json (v1, "
                      "slice-boundary abort rule) — kept as the record, not rewritten",
        "label_ko": LABEL_KO,
        "inputs": {
            "hazard_npz_canonical": str(NPZ.relative_to(REPO)),
            "hazard_npz_canonical_sha256": hashlib.sha256(NPZ.read_bytes()).hexdigest(),
            "hazard_npz_leakfree": str(LEAKFREE.relative_to(REPO)),
            "hazard_npz_leakfree_sha256": hashlib.sha256(LEAKFREE.read_bytes()).hexdigest(),
            "observation": "obs_stack of the canonical npz; byte-identical in both files, "
                           "so the grading clock does not depend on the field",
            "population": str(GRADING.relative_to(REPO)),
            "snapshots": prov,
        },
        "parameters": {
            "horizon_min": HORIZON, "dispatch_delay_min": DISPATCH,
            "responder_budget_min": W, "safety_margin_min": MARGIN,
            "t_load_min": T_LOAD, "t_unload_min": T_UNLOAD,
            "vehicle_cutoff": cfg.vehicle_cutoff,
            "ingress_sample_spacing_m": cfg.ingress_sample_spacing_m,
            "miss_allowances": list(MISS),
            "abort_rule_v2": "latest departure d* = min over sampled points of "
                             "(interpolated cutoff-crossing minute - travel minute to that "
                             "point); abort minute = d* - 12. Continuous minutes, "
                             "linear-in-time between the five forecast slices.",
            "abort_rule_v1": "arrival > (earliest slice at which any sampled point reaches "
                             "the cutoff) - 12. Kept in §4 as the slice-boundary version.",
            "fleets_headline_populations": list(FLEETS_FULL),
            "fleets_sensitivity_populations": list(FLEETS_ONE),
        },
        "fields": {k: {kk: vv for kk, vv in v.items() if kk != "hazard"}
                   for k, v in fields.items()},
        "populations": pop_stats,
        "runs": runs,
        "caveats": [
            "buildings are not households; a pickup is a road point, not a door",
            "the leak-free arm is a sensitivity, not the base (HQ decision 6)",
            "the success line is NOT quotable until HQ says so (decision 1)",
            "one pickup per trip; no capacity in persons, no queues, no traffic",
            "영덕 only, one fire, one observation",
        ],
        "seconds": round(time.monotonic() - t0, 1),
    }
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[3/5] wrote {OUT.relative_to(REPO)} "
          f"({OUT.stat().st_size/1024:.0f} KiB)", flush=True)
    print("\n".join(append_results(payload)))
    return 0


def append_results(payload: dict) -> list[str]:
    runs, pops = payload["runs"], payload["populations"]
    L = ["", "## 7. Results, v2 (appended by `scripts/build_truck_crew_replay_v2.py`; "
             "nothing in §6 is edited after the run)", "",
         f"_Run {payload['generated_utc']} at `{payload['git_commit'][:7]}`; artifact "
         f"`data/processed/truck_crew_replay_v2_yeongdeok.json`; "
         f"{payload['seconds']:.0f} s._", "",
         "**Populations** (pickups are road points; a walk node that shares a road point "
         "with another is one pickup):", "",
         "| field | population | walk nodes | pickups | buildings |",
         "|---|---|---:|---:|---:|"]
    for key, p in pops.items():
        f, n = key.split(".", 1)
        L.append(f"| {f} | {n} | {p['rescue_needing_walk_nodes']} | {p['pickups']} | "
                 f"{p['buildings_behind_pickups']} |")
    L += ["", "**The four counts under the v2 abort rule**, with v1's abort count beside "
              "them so the change in the rule is visible:", "",
          "| field | population | k | ordered | reached | not reached | aborted (v2) | "
          "aborted (v1, slice) | no abort minute | ingress inadmissible (m = 0) |",
          "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for key in sorted(runs):
        r = runs[key]
        v2 = r["v2"]
        f, n, k = key.split(".")
        L.append(f"| {f} | {n} | {k[1:]} | {v2['trips_ordered']} | "
                 f"{v2['reached_before_observed_closure']} | {v2['not_reached']} | "
                 f"{v2['aborted_by_rule']} | {r['aborted_by_rule']} | "
                 f"{v2['trips_with_no_abort_minute']} | "
                 f"{v2['trips_with_an_inadmissible_ingress_leg_m0']} |")
    L += ["", "The success line is **not** filled here: HQ decision 1 says it is not "
              "quotable, and decision 3 says the finals sentence is written from the two "
              "honest-core populations only. The numbers above are the record, not a claim.",
          ""]
    DOC.write_text(DOC.read_text(encoding="utf-8").rstrip("\n") + "\n" + "\n".join(L) + "\n",
                   encoding="utf-8")
    return L


if __name__ == "__main__":
    raise SystemExit(main())
