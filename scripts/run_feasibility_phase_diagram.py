#!/usr/bin/env python
"""Evacuation feasibility phase diagram on the real 영덕 hazard (deterministic sensitivity).

Grid, definitions and checks: docs/feasibility_phase_diagram.md (pre-declared).
Writes data/processed/feasibility_phase_diagram_yeongdeok.json and
docs/figures/phase_diagram_*.png, appends §5 to the doc. Reuses the NH-057 scenario
builder and the pipeline's own helpers; nothing committed is modified.

    python scripts/run_feasibility_phase_diagram.py
"""
from __future__ import annotations

import copy
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

from wildfireguardian.routing.future_front import RoadNetwork  # noqa: E402
from wildfireguardian.routing.hazard import HazardSequence  # noqa: E402
from wildfireguardian.routing.rescue import (  # noqa: E402
    RescueConfig, assess_destinations, rescuer_reachable, resident_policies,
)
from wildfireguardian.routing.rescue_demo import _immobile_homes  # noqa: E402

from run_real_roads_real_hazard_slope import REAL_OSM_SCAN_STRIDE  # noqa: E402
from run_rescue_routing_full import materialise_snapshots  # noqa: E402
from run_rescue_routing_real_hazard import build_scenario  # noqa: E402

OUT = REPO / "data/processed/feasibility_phase_diagram_yeongdeok.json"
DOC = REPO / "docs/feasibility_phase_diagram.md"
FIG = REPO / "docs/figures"
DELAYS = [0, 30, 60, 90, 120]
BUDGETS = [45, 60, 75, 90, 120]
CLOSURES = [0, 1, 2, 3]
DISPATCH_SLICE = [60, 90]          # at W = 75, all L
D_BASE, W_BASE = 30.0, 75.0
R_CUT, R_ALT, SPACING = 200.0, 300.0, 2000.0
CLASSES = ("already_safe", "saved_by_rescue_reachable_refuge", "no_safe_pedestrian_route", "no_surviving_vehicle_ingress")


def in_grid(grid, x, y):
    return grid.minx <= x <= grid.maxx and grid.miny <= y <= grid.maxy


def cut_network(net: RoadNetwork, points: list[tuple[float, float]], r: float) -> RoadNetwork:
    """Remove every edge that passes within ``r`` of a corridor point.

    Run 1 (2026-09-13, artifact *_run1_endpoint_rule.json) tested only the edge ENDPOINTS,
    so a corridor edge longer than 2 r had no node inside the disc and closure 2 removed
    nothing. Run 2 tests the nearest point of the segment to the corridor point, so the
    corridor edge itself is always cut.
    """
    g = copy.deepcopy(net.graph)
    if points:
        drop = []
        for u, v in g.edges():
            ax, ay = g.nodes[u]["x"], g.nodes[u]["y"]; bx, by = g.nodes[v]["x"], g.nodes[v]["y"]
            for (px, py) in points:
                dx, dy = bx - ax, by - ay
                L2 = dx * dx + dy * dy
                t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
                if math.hypot(ax + t * dx - px, ay + t * dy - py) <= r:
                    drop.append((u, v)); break
        g.remove_edges_from(drop)
    return RoadNetwork(graph=g, shelters=set(net.shelters))


def corridor_points(sc, cfg, homes_drive, depot_nodes):
    usage: dict[tuple, int] = {}
    for h in homes_drive:
        ok, rt, _ = rescuer_reachable(sc.drive, depot_nodes, h, sc.hazard, cfg)
        if ok and rt is not None:
            for a, b in zip(rt.route[:-1], rt.route[1:]):
                k = (min(a, b), max(a, b)); usage[k] = usage.get(k, 0) + 1
    ranked = sorted(usage.items(), key=lambda kv: (-kv[1], kv[0]))
    pts, meta = [], []
    for (a, b), n in ranked:
        ax, ay = sc.drive.node_xy(a); bx, by = sc.drive.node_xy(b)
        mx, my = (ax + bx) / 2, (ay + by) / 2
        if all(math.hypot(mx - px, my - py) >= SPACING for px, py in pts):
            pts.append((mx, my)); meta.append({"edge": [int(a), int(b)], "midpoint_5179": [round(mx, 1), round(my, 1)], "homes_using": n})
        if len(pts) == 3:
            break
    return pts, meta, len(usage)


def main() -> int:
    t_all = time.monotonic()
    tmp = Path(tempfile.mkdtemp(prefix="wfg-pd-"))
    try:
        prov = materialise_snapshots(tmp / "yeongdeok_2025")
        cfg0 = RescueConfig(use_osm=True, osm_cache_dir=str(tmp), scan_stride=REAL_OSM_SCAN_STRIDE)
        sc = build_scenario(cfg0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    grid = sc.hazard.grid
    zero = HazardSequence(grid=grid, times_min=np.array([0.0, 720.0]), surfaces=[np.zeros(grid_shape := (grid.nrows, grid.ncols), np.float32)] * 2)
    origins = list(sc.origins)
    immobile = set(_immobile_homes(sc, cfg0))
    unsupported = [int(n) for n in origins if not in_grid(grid, *sc.walk.node_xy(n))]
    origins = [n for n in origins if n not in set(unsupported)]
    depot_nodes0 = [sc.drive.nearest_node(d.x, d.y) for d in sc.depots]
    walk_of_drive = {n: sc.drive.nearest_node(*sc.walk.node_xy(n)) for n in origins}
    all_walk = {sc.walk.nearest_node(d.x, d.y) for d in sc.destinations}
    print(f"origins {len(origins)} (unsupported {len(unsupported)}), immobile {len(immobile)}, depots {len(depot_nodes0)}, refuges {len(sc.destinations)}", flush=True)

    # baseline needs-rescue set for corridor ranking: immobile + mobile with no safe walk at d=0, D=30
    cfgb = replace(cfg0, responder_dispatch_delay_min=D_BASE, responder_time_budget_min=W_BASE)
    ass = assess_destinations(sc.destinations, sc.drive, depot_nodes0, sc.hazard, cfgb)
    rr0 = {sc.walk.nearest_node(d.x, d.y) for d, a in zip(sc.destinations, ass) if a.rescue_reachable}
    base_need = []
    for n in origins:
        if n in immobile:
            base_need.append(n); continue
        pol = resident_policies(sc.walk, n, sc.hazard, all_walk, rr0, cfgb, departure_min=0.0)
        if not ((pol["naive"].reached and not pol["naive"].enters_hazard) or (pol["future_aware_rescue"].reached and not pol["future_aware_rescue"].enters_hazard)):
            base_need.append(n)
    pts, corridors, n_edges_used = corridor_points(sc, cfgb, [walk_of_drive[n] for n in base_need], depot_nodes0)
    print(f"baseline needs rescue {len(base_need)}; corridors: {corridors}", flush=True)

    nets = {}
    for L in CLOSURES:
        nets[(L, R_CUT)] = (cut_network(sc.walk, pts[:L], R_CUT), cut_network(sc.drive, pts[:L], R_CUT))
    nets[(1, R_ALT)] = (cut_network(sc.walk, pts[:1], R_ALT), cut_network(sc.drive, pts[:1], R_ALT))
    edges_removed = {f"L{L}_R{int(r)}": {"walk": sc.walk.graph.number_of_edges() - nets[(L, r)][0].graph.number_of_edges(),
                                         "drive": sc.drive.graph.number_of_edges() - nets[(L, r)][1].graph.number_of_edges()} for (L, r) in nets}
    depots_cut = {f"L{L}_R{int(r)}": [i for i, dn in enumerate(depot_nodes0) if nets[(L, r)][1].graph.degree(dn) == 0] for (L, r) in nets}

    res_cache: dict = {}
    def resident_classes(hz, walk, d, D, L, r, step=None):
        cfg = replace(cfg0, responder_dispatch_delay_min=float(D), responder_time_budget_min=W_BASE, **({"time_step_min": step} if step else {}))
        drive = nets[(L, r)][1]
        assess = assess_destinations(sc.destinations, drive, depot_nodes0, hz, cfg)
        rr = frozenset(sc.walk.nearest_node(dd.x, dd.y) for dd, a in zip(sc.destinations, assess) if a.rescue_reachable)
        key = (id(hz), d, L, r, rr, step)
        if key not in res_cache:
            out = {}
            for n in origins:
                if n in immobile:
                    out[n] = "needs"; continue
                pol = resident_policies(walk, n, hz, all_walk, set(rr), cfg, departure_min=float(d))
                nv, fr = pol["naive"], pol["future_aware_rescue"]
                out[n] = ("already_safe" if nv.reached and not nv.enters_hazard else
                          "saved_by_rescue_reachable_refuge" if fr.reached and not fr.enters_hazard else "needs")
            res_cache[key] = out
        return res_cache[key], len(rr), sum(1 for a in assess if a.safe)

    reach_cache: dict = {}
    def reachable(hz, drive, home_drive, D, W, L, r):
        key = (id(hz), home_drive, D, W, L, r)
        if key not in reach_cache:
            cfg = replace(cfg0, responder_dispatch_delay_min=float(D), responder_time_budget_min=float(W))
            reach_cache[key] = bool(rescuer_reachable(drive, depot_nodes0, home_drive, hz, cfg)[0])
        return reach_cache[key]

    def cell(hz, d, W, L, D=D_BASE, r=R_CUT, step=None):
        t0 = time.monotonic()
        walk, drive = nets[(L, r)]
        cls, n_rr, n_safe = resident_classes(hz, walk, d, D, L, r, step)
        counts = {k: 0 for k in CLASSES}
        for n, c in cls.items():
            if c != "needs":
                counts[c] += 1
            elif reachable(hz, drive, walk_of_drive[n], D, W, L, r):
                counts["no_safe_pedestrian_route"] += 1
            else:
                counts["no_surviving_vehicle_ingress"] += 1
        served = len(origins) - counts["no_surviving_vehicle_ingress"]
        return {"d": d, "W": W, "L": L, "D": D, "R": r, "time_step": step, **counts, "needs_rescue": counts["no_safe_pedestrian_route"] + counts["no_surviving_vehicle_ingress"],
                "served_access_feasible": served, "refuge_walk_nodes_rescue_reachable": n_rr, "refuges_safe": n_safe, "seconds": round(time.monotonic() - t0, 1)}

    cells, control = [], []
    for L in CLOSURES:
        for d in DELAYS:
            for W in BUDGETS:
                cells.append(cell(sc.hazard, d, W, L)); print(cells[-1], flush=True)
        for D in DISPATCH_SLICE:
            cells.append(cell(sc.hazard, 0, W_BASE, L, D=D)); print(cells[-1], flush=True)
        for W in BUDGETS:
            control.append(cell(zero, 0, W, L)); print("control", control[-1], flush=True)
    checks = {"time_step_5": cell(sc.hazard, 60, W_BASE, 1, step=5.0), "time_step_10": cell(sc.hazard, 60, W_BASE, 1, step=10.0),
              "radius_300_d0": cell(sc.hazard, 0, W_BASE, 1, r=R_ALT), "radius_300_d60": cell(sc.hazard, 60, W_BASE, 1, r=R_ALT)}
    result = {
        "schema_version": 1, "title": "Evacuation feasibility phase diagram, 영덕 real hazard (deterministic sensitivity)",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip(),
        "rule_doc": "docs/feasibility_phase_diagram.md §1-§4 (pre-declared)",
        "inputs": {"scenario": "scripts/run_rescue_routing_real_hazard.py build_scenario (NH-057)", "snapshots": prov},
        "grid": {"delays_min": DELAYS, "budgets_min": BUDGETS, "closures": CLOSURES, "dispatch_slice_min": DISPATCH_SLICE, "dispatch_base_min": D_BASE, "cut_radius_m": R_CUT, "corridor_spacing_m": SPACING},
        "population": {"n_origins": len(origins), "n_unsupported_outside_grid": len(unsupported), "unsupported_origins": unsupported, "n_immobile": len(immobile), "n_refuges": len(sc.destinations), "n_depots": len(depot_nodes0)},
        "baseline_needs_rescue": len(base_need), "corridors": corridors, "n_drive_edges_used_by_baseline_ingress": n_edges_used,
        "edges_removed": edges_removed, "depots_isolated_by_closure": depots_cut,
        "served_definition": "walk-out exists or a survival-aware ingress route exists; NOT a completed transport (no vehicle occupancy)",
        "timeouts": "none: the routers have no timeout; budget exhaustion is the infeasible outcome",
        "cells": cells, "no_fire_control": control, "checks": checks,
        "seconds_total": round(time.monotonic() - t_all, 1),
    }
    OUT.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    write_figures(result); append_doc(result)
    print("wrote", OUT.relative_to(REPO), f"{result['seconds_total']}s"); return 0


def write_figures(res):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    FIG.mkdir(exist_ok=True)
    n = res["population"]["n_origins"]
    main = [c for c in res["cells"] if c["D"] == D_BASE and c["R"] == R_CUT and c["time_step"] is None]
    for key, title, fname in (("no_surviving_vehicle_ingress", "origins with no survival-aware ingress (unserved)", "phase_diagram_unserved.png"),
                              ("needs_rescue", "origins needing rescue (immobile + no safe walk)", "phase_diagram_needs_rescue.png")):
        fig, axes = plt.subplots(1, len(CLOSURES), figsize=(4.2 * len(CLOSURES), 4), sharey=True)
        vmax = max(c[key] for c in main)
        for ax, L in zip(axes, CLOSURES):
            M = np.array([[next(c[key] for c in main if c["d"] == d and c["W"] == W and c["L"] == L) for W in BUDGETS] for d in DELAYS])
            im = ax.imshow(M, origin="lower", cmap="magma_r", vmin=0, vmax=max(vmax, 1))
            ax.set_xticks(range(len(BUDGETS))); ax.set_xticklabels(BUDGETS); ax.set_yticks(range(len(DELAYS))); ax.set_yticklabels(DELAYS)
            ax.set_xlabel("responder budget W (min)"); ax.set_title(f"closure L={L}")
            for i in range(len(DELAYS)):
                for j in range(len(BUDGETS)):
                    ax.text(j, i, str(M[i, j]), ha="center", va="center", color="white" if M[i, j] > vmax * 0.6 else "black", fontsize=8)
        axes[0].set_ylabel("preparation delay d (min)")
        fig.colorbar(im, ax=axes, shrink=0.8, label=f"{key} (of {n})")
        fig.suptitle(f"영덕 real hazard · {title} · deterministic, D=30, R=200 m", fontsize=10)
        fig.savefig(FIG / fname, dpi=130, bbox_inches="tight"); plt.close(fig)
    # control comparison at W=75
    fig, ax = plt.subplots(figsize=(6, 4))
    for L in CLOSURES:
        ys = [next(c["no_surviving_vehicle_ingress"] for c in main if c["d"] == d and c["W"] == W_BASE and c["L"] == L) for d in DELAYS]
        ax.plot(DELAYS, ys, marker="o", label=f"fire, L={L}")
        c0 = next(c for c in res["no_fire_control"] if c["W"] == W_BASE and c["L"] == L)
        ax.axhline(c0["no_surviving_vehicle_ingress"], ls="--", lw=0.8, color=ax.lines[-1].get_color())
    ax.set_xlabel("preparation delay d (min)"); ax.set_ylabel(f"unserved origins (of {n}), W=75"); ax.legend(fontsize=8)
    ax.set_title("solid: real hazard · dashed: no-fire control (same closure)", fontsize=9)
    fig.savefig(FIG / "phase_diagram_control.png", dpi=130, bbox_inches="tight"); plt.close(fig)


def append_doc(res):
    n = res["population"]["n_origins"]
    main = [c for c in res["cells"] if c["D"] == D_BASE and c["R"] == R_CUT and c["time_step"] is None]
    L = ["", "### Run 2 (segment-distance closure rule)", "", f"_Run {res['generated_utc']} at `{res['git_commit'][:7]}`; artifact `data/processed/feasibility_phase_diagram_yeongdeok.json`; {n} origins per cell ({res['population']['n_unsupported_outside_grid']} unsupported excluded), {res['population']['n_immobile']} immobile; figures `docs/figures/phase_diagram_*.png`; {res['seconds_total']:.0f} s._", "",
         "Corridors (from baseline ingress usage): " + "; ".join(f"{i+1}: edge {c['edge']} used by {c['homes_using']} homes" for i, c in enumerate(res["corridors"])) + ".",
         "Edges removed per closure: " + ", ".join(f"{k} walk {v['walk']} / drive {v['drive']}" for k, v in res["edges_removed"].items()) + ". Depots isolated: " + json.dumps(res["depots_isolated_by_closure"]) + ".", "",
         "### Unserved origins (no survival-aware ingress) — rows d, columns W", ""]
    for Lc in CLOSURES:
        L += [f"**closure L = {Lc}**", "", "| d \\ W | " + " | ".join(str(w) for w in BUDGETS) + " | no-fire control (d=0) |", "|---|" + "---:|" * (len(BUDGETS) + 1)]
        for d in DELAYS:
            row = [next(c for c in main if c["d"] == d and c["W"] == W and c["L"] == Lc) for W in BUDGETS]
            ctrl = [next(c for c in res["no_fire_control"] if c["W"] == W and c["L"] == Lc) for W in BUDGETS]
            L.append(f"| {d} | " + " | ".join(f"{c['no_surviving_vehicle_ingress']} (need {c['needs_rescue']})" for c in row) + " | " + "/".join(str(c["no_surviving_vehicle_ingress"]) for c in ctrl) + " |")
        L.append("")
    L += ["### Dispatch-delay slice (W = 75, d = 0)", "", "| L | D=30 | D=60 | D=90 |", "|---|---:|---:|---:|"]
    for Lc in CLOSURES:
        r30 = next(c for c in main if c["d"] == 0 and c["W"] == W_BASE and c["L"] == Lc)
        r60 = next(c for c in res["cells"] if c["D"] == 60 and c["L"] == Lc); r90 = next(c for c in res["cells"] if c["D"] == 90 and c["L"] == Lc)
        L.append(f"| {Lc} | {r30['no_surviving_vehicle_ingress']} | {r60['no_surviving_vehicle_ingress']} | {r90['no_surviving_vehicle_ingress']} |")
    ch = res["checks"]
    L += ["", "### Checks", "", f"- time step 5 vs 10 min at (d=60, W=75, L=1): unserved {ch['time_step_5']['no_surviving_vehicle_ingress']} vs {ch['time_step_10']['no_surviving_vehicle_ingress']}; needs rescue {ch['time_step_5']['needs_rescue']} vs {ch['time_step_10']['needs_rescue']}.",
          f"- cut radius 300 vs 200 m at L=1: unserved {ch['radius_300_d0']['no_surviving_vehicle_ingress']} vs {next(c for c in main if c['d']==0 and c['W']==W_BASE and c['L']==1)['no_surviving_vehicle_ingress']} (d=0), {ch['radius_300_d60']['no_surviving_vehicle_ingress']} vs {next(c for c in main if c['d']==60 and c['W']==W_BASE and c['L']==1)['no_surviving_vehicle_ingress']} (d=60).",
          f"- rescue-reachable refuge WALK NODES (distinct; two refuges can share a node) / safe refuges per closure at D=30: " + ", ".join(f"L{Lc}: {next(c for c in main if c['d']==0 and c['W']==W_BASE and c['L']==Lc)['refuge_walk_nodes_rescue_reachable']}/{next(c for c in main if c['d']==0 and c['W']==W_BASE and c['L']==Lc)['refuges_safe']}" for Lc in CLOSURES) + f" of {res['population']['n_refuges']}.",
          "- timeouts: none (the routers have none; budget exhaustion is the infeasible outcome).", ""]
    DOC.write_text(DOC.read_text(encoding="utf-8").rstrip("\n") + "\n" + "\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
