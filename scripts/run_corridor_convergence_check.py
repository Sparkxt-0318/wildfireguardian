#!/usr/bin/env python
"""Corridor convergence check, 영덕 2025, deterministic. Rules: docs/corridor_convergence_check.md
(declared before the run). Additive diagnostic: nothing committed is modified, nothing is
registered, nothing reaches a judge-facing surface.

    python scripts/run_corridor_convergence_check.py [--smoke]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import networkx as nx
import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from wildfireguardian.routing.rescue import (  # noqa: E402
    FOUR_WAY_CLASSES, RescueConfig, build_dispatch_list, classify_origin,
    rescuer_reachable, resident_policies,
)
from wildfireguardian.routing.rescue_demo import (  # noqa: E402
    _immobile_homes, _refuge_node_sets,
)

from run_real_roads_real_hazard_slope import REAL_OSM_SCAN_STRIDE  # noqa: E402
from run_rescue_routing_real_hazard import build_scenario  # noqa: E402
from run_rescue_routing_full import materialise_snapshots  # noqa: E402

NPZ = REPO / "data/processed/routing_demo_canonical.npz"
COMMITTED = REPO / "data/processed/rescue_routing_real_hazard.json"
OUTDIR = REPO / "data/processed/corridor_convergence"
OUT = OUTDIR / "convergence_yeongdeok.json"
DOC = REPO / "docs/corridor_convergence_check.md"
FIG = REPO / "docs/figures"

TOP_N = 25                 # §4 top-N shared edges per network
SAMPLE_M = 100.0           # §5 sampling along an edge
P_WALK, P_VEHICLE = 0.5, 0.7   # §5 envelope thresholds (the committed cutoffs)


# --------------------------------------------------------------------------- helpers
def _git() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def edge_key(u: int, v: int) -> tuple[int, int]:
    return (u, v) if u <= v else (v, u)


def route_edges(route: list[int]) -> set[tuple[int, int]]:
    """Undirected edge keys of a node path; each edge at most once (§4)."""
    return {edge_key(a, b) for a, b in zip(route[:-1], route[1:]) if a != b}


def sample_points(net, u: int, v: int, spacing: float = SAMPLE_M):
    ax, ay = net.node_xy(u)
    bx, by = net.node_xy(v)
    L = math.hypot(bx - ax, by - ay)
    n = max(1, int(L // spacing))
    return [(ax + (i / n) * (bx - ax), ay + (i / n) * (by - ay)) for i in range(n + 1)], L


def envelope_probe(net, hazard, u: int, v: int) -> dict:
    """§5: max hazard over every sample point and EVERY forecast slice."""
    pts, L = sample_points(net, u, v)
    xs = np.array([p[0] for p in pts]); ys = np.array([p[1] for p in pts])
    per_slice = []
    for t in hazard.times_min:
        p = np.asarray(hazard.prob_at_points(xs, ys, float(t)), dtype=float)
        per_slice.append(float(np.max(p)))
    mx = max(per_slice)
    def first_at(thr):
        for i, v_ in enumerate(per_slice):
            if v_ >= thr:
                return float(hazard.times_min[i])
        return None
    return {"length_m": round(L, 1), "n_samples": len(pts),
            "max_p_any_slice": round(mx, 4),
            "max_p_by_slice": [round(v_, 4) for v_ in per_slice],
            "first_min_p_ge_0_5": first_at(P_WALK),
            "first_min_p_ge_0_7": first_at(P_VEHICLE),
            "fire_exposed": bool(mx >= P_WALK)}


def used_subgraph(net, routes: dict[int, list[int]]) -> nx.Graph:
    g = nx.Graph()
    for route in routes.values():
        for a, b in zip(route[:-1], route[1:]):
            if a == b:
                continue
            x1, y1 = net.node_xy(a); x2, y2 = net.node_xy(b)
            g.add_node(a, x=x1, y=y1); g.add_node(b, x=x2, y=y2)
            g.add_edge(a, b)
    return g


def _comp_of(g: nx.Graph) -> dict[int, int]:
    """node -> component id, one pass."""
    out: dict[int, int] = {}
    for i, comp in enumerate(nx.connected_components(g)):
        for n in comp:
            out[n] = i
    return out


def structural(net, routes: dict[int, list[int]], targets_of: dict[int, set[int]],
               label: str) -> dict:
    """§6: articulation points and bridges of the used subgraph, re-tested on the full net.

    Every candidate is tested (no budget): for one candidate the graph is cut once and
    connected components are computed once, then each household on it is a component
    lookup. That is what makes the exhaustive sweep affordable.
    """
    g = used_subgraph(net, routes)
    full = nx.Graph(net.graph)
    arts = sorted(nx.articulation_points(g))
    brs = sorted(edge_key(u, v) for u, v in nx.bridges(g))
    on_node: dict[int, set[int]] = defaultdict(set)
    on_edge: dict[tuple[int, int], set[int]] = defaultdict(set)
    for h, route in routes.items():
        for n in route:
            on_node[n].add(h)
        for e in route_edges(route):
            on_edge[e].add(h)

    def cut(G, kind, item):
        H = G.copy()
        if kind == "node":
            if item in H:
                H.remove_node(item)
        elif H.has_edge(*item):
            H.remove_edge(*item)
        return _comp_of(H)

    def score(kind, item):
        users = on_node[item] if kind == "node" else on_edge[item]
        comp_used = cut(g, kind, item)
        comp_full = cut(full, kind, item)
        cut_used, cut_full = [], []
        for h in sorted(users):
            tg = targets_of.get(h) or set()
            if not tg:
                continue
            origin = routes[h][0]
            if kind == "node" and (item == origin or item in tg):
                continue
            for comp, sink in ((comp_used, cut_used), (comp_full, cut_full)):
                c = comp.get(origin)
                if c is None or not any(comp.get(t) == c for t in tg):
                    sink.append(h)
        return cut_used, cut_full

    cands = [("node", a, len(on_node[a])) for a in arts] + \
            [("edge", e, len(on_edge[e])) for e in brs]
    cands.sort(key=lambda t: (-t[2], str(t[1])))
    findings = []
    for kind, item, n_users in cands:
        cu, cf = score(kind, item)
        if len(cu) > 1 or len(cf) > 1:
            xy = (net.node_xy(item) if kind == "node"
                  else [list(net.node_xy(item[0])), list(net.node_xy(item[1]))])
            findings.append({"network": label, "kind": kind,
                             "id": (item if kind == "node" else list(item)),
                             "xy": (list(xy) if kind == "node" else xy),
                             "households_on_it": n_users,
                             "households_cut_used_subgraph": len(cu),
                             "households_cut_full_network": len(cf),
                             "cut_full_network_households": cf[:20]})
    findings.sort(key=lambda d: (-d["households_cut_full_network"],
                                 -d["households_cut_used_subgraph"], -d["households_on_it"]))
    # Serialisation: every full-network finding is kept in full (that is the headline,
    # §6); the thin-subgraph-only ones are counted and the worst 50 listed, so the
    # artifact stays small enough to commit. Nothing is dropped from the counts.
    full = [f for f in findings if f["households_cut_full_network"] > 1]
    only = [f for f in findings if f["households_cut_full_network"] <= 1]
    return {"network": label,
            "n_findings_cutting_more_than_one_household": len(findings),
            "n_findings_full_network": len(full),
            "n_findings_used_subgraph_only": len(only),
            "findings_used_subgraph_only_top50": only[:50],
            "used_subgraph": {"nodes": g.number_of_nodes(), "edges": g.number_of_edges()},
            "n_articulation_points": len(arts), "n_bridges": len(brs),
            "n_candidates_tested": len(cands), "n_candidates_total": len(cands),
            "test_budget": "exhaustive (every articulation point and bridge tested)",
            "findings": full}


# --------------------------------------------------------------------------- run
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="first 40 origins; writes nothing")
    args = ap.parse_args()
    t0 = time.monotonic()

    # ---- gate 1: the committed hazard field is the one the committed run used (§3)
    committed = json.loads(COMMITTED.read_text(encoding="utf-8"))
    sha = hashlib.sha256(NPZ.read_bytes()).hexdigest()
    assert sha == committed["what_is_real"]["hazard_sha256"], \
        f"hazard field hash mismatch: {sha} != {committed['what_is_real']['hazard_sha256']}"
    print(f"[gate 1] canonical hazard sha256 matches the committed run ({sha[:12]}…)", flush=True)

    tmp = Path(tempfile.mkdtemp(prefix="wfg-conv-"))
    try:
        materialise_snapshots(tmp / "yeongdeok_2025")
        cfg = RescueConfig(use_osm=True, osm_cache_dir=str(tmp),
                           scan_stride=REAL_OSM_SCAN_STRIDE)
        sc = build_scenario(cfg)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"[setup] walk={sc.walk.graph.number_of_nodes()} drive={sc.drive.graph.number_of_nodes()} "
          f"refuges={len(sc.destinations)} depots={len(sc.depots)} origins={len(sc.origins)} "
          f"{time.monotonic()-t0:.0f}s", flush=True)

    depot_nodes = [sc.drive.nearest_node(d.x, d.y) for d in sc.depots]
    assessments, all_walk, rr_walk = _refuge_node_sets(sc, cfg)
    immobile = set(_immobile_homes(sc, cfg))
    origins = sc.origins[:40] if args.smoke else sc.origins

    # ---- one pass: the pipeline's own calls, keeping the routes (§4)
    counts = {k: 0 for k in FOUR_WAY_CLASSES}
    walk_routes: dict[int, list[int]] = {}      # deployed resident walk route per origin
    naive_routes: dict[int, list[int]] = {}     # status-quo comparison
    walk_targets: dict[int, set[int]] = {}
    needs_rescue: list[int] = []
    for n in origins:
        if n in immobile:
            needs_rescue.append(n)
            continue
        pol = resident_policies(sc.walk, n, sc.hazard, all_walk, rr_walk, cfg)
        naive, fa_rr = pol["naive"], pol["future_aware_rescue"]
        if naive.reached and len(naive.route) > 1:
            naive_routes[n] = list(naive.route)
        if naive.reached and not naive.enters_hazard:
            counts["already_safe"] += 1
            dep = fa_rr if (fa_rr.reached and len(fa_rr.route) > 1) else naive
        elif fa_rr.reached and not fa_rr.enters_hazard:
            counts["saved_by_rescue_reachable_refuge"] += 1
            dep = fa_rr
        else:
            needs_rescue.append(n)
            continue
        if dep.reached and len(dep.route) > 1:
            walk_routes[n] = list(dep.route)
            walk_targets[n] = {int(dep.target)} if dep.target is not None else set()

    needs_drive = {n: sc.drive.nearest_node(*sc.walk.node_xy(n)) for n in needs_rescue}
    dispatch, unreachable = build_dispatch_list(list(needs_drive.values()), sc.drive,
                                                depot_nodes, sc.depots, sc.hazard, cfg)
    counts["no_safe_pedestrian_route"] = len(dispatch)
    counts["no_surviving_vehicle_ingress"] = len(unreachable)

    drive_routes: dict[int, list[int]] = {}
    drive_targets: dict[int, set[int]] = {}
    for n, hd in needs_drive.items():
        ok, rt, di = rescuer_reachable(sc.drive, depot_nodes, hd, sc.hazard, cfg)
        if ok and rt is not None and len(rt.route) > 1:
            # the router solves depot -> home; the household's "reachable depot set" is
            # the depot this route actually used, and the route is stored home-first so
            # route[0] is the household's own node (§6 origin convention).
            r = list(rt.route)
            if r[0] in depot_nodes:
                r = r[::-1]
            drive_routes[n] = r
            drive_targets[n] = {int(depot_nodes[di])} if di is not None else set(depot_nodes)

    # ---- gate 2: the four-way split reproduces the committed run exactly (§3)
    if args.smoke:
        print(f"[smoke] counts {counts}; walk routes {len(walk_routes)}, "
              f"drive routes {len(drive_routes)}; nothing written")
        return 0
    exp = committed["four_way_counts"]
    assert len(origins) == committed["n_origins"], \
        f"origin count {len(origins)} != committed {committed['n_origins']}"
    assert counts == exp, f"four-way split did not reproduce: {counts} != {exp}"
    print(f"[gate 2] four-way split reproduced exactly: {counts}", flush=True)
    print(f"[routes] deployed walk {len(walk_routes)}, naive walk {len(naive_routes)}, "
          f"rescuer drive {len(drive_routes)} {time.monotonic()-t0:.0f}s", flush=True)

    # ---- edge tally (§4)
    def tally(routes: dict[int, list[int]]) -> dict[tuple[int, int], set[int]]:
        out: dict[tuple[int, int], set[int]] = defaultdict(set)
        for h, r in routes.items():
            for e in route_edges(r):
                out[e].add(h)
        return out

    tallies = {"walk_deployed": (sc.walk, tally(walk_routes)),
               "walk_naive": (sc.walk, tally(naive_routes)),
               "drive_rescuer": (sc.drive, tally(drive_routes))}

    top_tables = {}
    for name, (net, tal) in tallies.items():
        ranked = sorted(tal.items(), key=lambda kv: (-len(kv[1]),
                                                     -math.hypot(*(np.subtract(net.node_xy(kv[0][1]),
                                                                               net.node_xy(kv[0][0])))),
                                                     kv[0]))
        rows = []
        for e, hh in ranked[:TOP_N]:
            probe = envelope_probe(net, sc.hazard, *e)
            rows.append({"edge": list(e), "households": len(hh),
                         "xy": [list(net.node_xy(e[0])), list(net.node_xy(e[1]))], **probe})
        top_tables[name] = {
            "n_edges_used": len(tal),
            "n_edges_shared_by_2_or_more": sum(1 for v in tal.values() if len(v) > 1),
            "max_households_on_one_edge": (max((len(v) for v in tal.values()), default=0)),
            "top": rows,
            "n_top_fire_exposed": sum(1 for r in rows if r["fire_exposed"]),
        }
        print(f"[tally] {name}: {len(tal)} edges used, "
              f"{top_tables[name]['n_edges_shared_by_2_or_more']} shared by ≥2 households, "
              f"max {top_tables[name]['max_households_on_one_edge']} on one edge, "
              f"{top_tables[name]['n_top_fire_exposed']}/{len(rows)} of the top-{TOP_N} fire-exposed",
              flush=True)

    # ---- structural test (§6)
    struct = {"walk": structural(sc.walk, walk_routes, walk_targets, "walk"),
              "drive": structural(sc.drive, drive_routes, drive_targets, "drive")}
    # §5 applied to the structural findings too: a chokepoint the fire never reaches is a
    # road-network fact, not a wildfire finding. A node is probed over its incident edges
    # in the used subgraph; an edge over itself.
    for net_name, net, routes in (("walk", sc.walk, walk_routes), ("drive", sc.drive, drive_routes)):
        g = used_subgraph(net, routes)
        for f in struct[net_name]["findings"]:
            if f["households_cut_full_network"] <= 1:
                continue
            segs = ([(f["id"], m) for m in g[f["id"]]] if f["kind"] == "node"
                    else [tuple(f["id"])])
            probes = [envelope_probe(net, sc.hazard, a, b) for a, b in segs]
            f["max_p_any_slice"] = max(pr["max_p_any_slice"] for pr in probes)
            f["fire_exposed"] = any(pr["fire_exposed"] for pr in probes)
            firsts = [pr["first_min_p_ge_0_5"] for pr in probes if pr["first_min_p_ge_0_5"] is not None]
            f["first_min_p_ge_0_5"] = min(firsts) if firsts else None
    for k, s in struct.items():
        print(f"[structural] {k}: used subgraph {s['used_subgraph']}, "
              f"{s['n_articulation_points']} articulation points, {s['n_bridges']} bridges, "
              f"{len(s['findings'])} cutting >1 household {time.monotonic()-t0:.0f}s", flush=True)

    # ---- cross-check (§6)
    cross = {}
    for net_name, tkey in (("walk", "walk_deployed"), ("drive", "drive_rescuer")):
        top_edges = {tuple(r["edge"]) for r in top_tables[tkey]["top"]}
        top_nodes = {n for e in top_edges for n in e}
        s = struct[net_name]
        choke_edges = {tuple(f["id"]) for f in s["findings"]
                       if f["kind"] == "edge" and f["households_cut_full_network"] > 1}
        choke_nodes = {f["id"] for f in s["findings"]
                       if f["kind"] == "node" and f["households_cut_full_network"] > 1}
        cross[net_name] = {
            "top_convergence_edges": len(top_edges),
            "full_network_chokepoint_edges": len(choke_edges),
            "full_network_chokepoint_nodes": len(choke_nodes),
            "edges_in_both": sorted(list(e) for e in (top_edges & choke_edges)),
            "chokepoint_nodes_on_a_top_edge": sorted(choke_nodes & top_nodes),
            "overlap": bool((top_edges & choke_edges) or (choke_nodes & top_nodes)),
        }

    headline = {}
    for net_name, tkey in (("walk", "walk_deployed"), ("drive", "drive_rescuer")):
        full = struct[net_name]["findings"]
        top = top_tables[tkey]["top"]
        headline[net_name] = {
            "worst_chokepoint_households_cut": (full[0]["households_cut_full_network"] if full else 0),
            "worst_chokepoint": (full[0]["id"] if full else None),
            "worst_chokepoint_kind": (full[0]["kind"] if full else None),
            "worst_chokepoint_fire_exposed": (full[0].get("fire_exposed") if full else None),
            "worst_chokepoint_max_p_any_slice": (full[0].get("max_p_any_slice") if full else None),
            "n_full_network_chokepoints": len(full),
            "n_full_network_chokepoints_fire_exposed": sum(1 for f in full if f.get("fire_exposed")),
            "max_households_on_one_edge": top_tables[tkey]["max_households_on_one_edge"],
            "n_top_fire_exposed": top_tables[tkey]["n_top_fire_exposed"],
            "households_routed": (len(walk_routes) if net_name == "walk" else len(drive_routes)),
            "wildfire_specific_finding": bool(
                any(f.get("fire_exposed") for f in full) or any(r["fire_exposed"] for r in top)),
        }
    nv = top_tables["walk_naive"]
    headline["walk_naive_contrast"] = {
        "max_households_on_one_edge_naive": nv["max_households_on_one_edge"],
        "max_households_on_one_edge_deployed": top_tables["walk_deployed"]["max_households_on_one_edge"],
        "n_top_fire_exposed_naive": nv["n_top_fire_exposed"],
        "n_top_fire_exposed_deployed": top_tables["walk_deployed"]["n_top_fire_exposed"],
        "fire_exposed_naive_edges": [{"edge": r["edge"], "households": r["households"],
                                      "max_p_any_slice": r["max_p_any_slice"],
                                      "first_min_p_ge_0_5": r["first_min_p_ge_0_5"]}
                                     for r in nv["top"] if r["fire_exposed"]],
    }
    doc = {
        "schema_version": 1,
        "headline": headline,
        "title": "Corridor convergence check, 영덕 2025 (deterministic, additive diagnostic)",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _git(),
        "rule_doc": "docs/corridor_convergence_check.md §1-§6 (declared before the run)",
        "status": "exploratory; not registered in docs/NUMBERS.json; not on any judge-facing surface",
        "does_not_model": [
            "road or corridor capacity, flow, queueing or congestion of any kind",
            "any change to the routes: the tally is read-only and fed back into nothing",
            "the rescue-UNIT supply capacity layer (RescueCapacityConfig / capacity_triage), which is untouched",
        ],
        "reproduction_gate": {
            "hazard_sha256": sha,
            "hazard_sha256_source": "data/processed/rescue_routing_real_hazard.json what_is_real.hazard_sha256",
            "n_origins": len(origins), "four_way_counts": counts,
            "four_way_counts_committed": exp, "reproduced": counts == exp,
        },
        "scenario": {"walk_nodes": sc.walk.graph.number_of_nodes(),
                     "drive_nodes": sc.drive.graph.number_of_nodes(),
                     "refuges": len(sc.destinations), "depots": len(sc.depots),
                     "refuges_rescue_reachable": sum(1 for a in assessments if a.rescue_reachable),
                     "scan_stride": cfg.scan_stride, "walk_cutoff": cfg.walk_cutoff,
                     "vehicle_cutoff": cfg.vehicle_cutoff},
        "routes_collected": {"walk_deployed": len(walk_routes), "walk_naive": len(naive_routes),
                             "drive_rescuer": len(drive_routes),
                             "no_route_contributed": len(unreachable)},
        "convergence": top_tables,
        "structural": struct,
        "cross_check": cross,
        "seconds_total": round(time.monotonic() - t0, 1),
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    figure(sc, top_tables, struct)
    append_doc(doc)
    print(f"[done] wrote {OUT.relative_to(REPO)} and appended {DOC.relative_to(REPO)} "
          f"({doc['seconds_total']/60:.1f} min)", flush=True)
    return 0


# --------------------------------------------------------------------------- outputs
def figure(sc, top_tables, struct) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = top_tables["walk_deployed"]["top"] + top_tables["drive_rescuer"]["top"]
    if not rows:
        return
    FIG.mkdir(exist_ok=True)
    g = sc.hazard.grid
    H = np.asarray(sc.hazard.surfaces[-1], dtype=float)
    fig, ax = plt.subplots(figsize=(9, 10))
    xs = np.linspace(g.minx + g.cell_size_m / 2, g.maxx - g.cell_size_m / 2, g.ncols)
    ys = np.linspace(g.maxy - g.cell_size_m / 2, g.miny + g.cell_size_m / 2, g.nrows)
    ax.contourf(xs, ys, H, levels=[0.5, 1.01], colors=["#f2c9c2"], alpha=0.8)
    ax.contour(xs, ys, H, levels=[0.5], colors="firebrick", linewidths=1.0)
    ax.contour(xs, ys, np.asarray(sc.hazard.surfaces[0], dtype=float),
               levels=[0.5], colors="dimgrey", linewidths=0.8)
    mx = max(r["households"] for r in rows)
    cmap = plt.get_cmap("viridis")
    for name, rr in (("walk", top_tables["walk_deployed"]["top"]),
                     ("drive", top_tables["drive_rescuer"]["top"])):
        for r in rr:
            (x1, y1), (x2, y2) = r["xy"]
            ax.plot([x1, x2], [y1, y2], color=cmap(r["households"] / mx),
                    lw=3.4 if name == "walk" else 2.4,
                    ls="-" if name == "walk" else "--", solid_capstyle="round", zorder=3)
    for r in top_tables["walk_naive"]["top"]:
        if r["fire_exposed"]:
            (x1, y1), (x2, y2) = r["xy"]
            ax.plot([x1, x2], [y1, y2], color="red", lw=3.4, solid_capstyle="round", zorder=6,
                    label="_shared segment on a status-quo (naive) route that the fire reaches")
    ch = [f for s in struct.values() for f in s["findings"]
          if f["households_cut_full_network"] > 1]
    if ch:
        px = [f["xy"][0] if f["kind"] == "node" else (f["xy"][0][0] + f["xy"][1][0]) / 2 for f in ch]
        py = [f["xy"][1] if f["kind"] == "node" else (f["xy"][0][1] + f["xy"][1][1]) / 2 for f in ch]
        ax.scatter(px, py, s=55, facecolors="none",
                   edgecolors=["red" if f.get("fire_exposed") else "black" for f in ch], lw=1.1,
                   label="chokepoint cutting >1 household (full network); red if fire-exposed",
                   zorder=4)
    if any(r["fire_exposed"] for r in top_tables["walk_naive"]["top"]):
        ax.plot([], [], color="red", lw=3.4,
                label="shared naive-route segment the fire reaches (p≥0.5)")
    ax.scatter([d.x for d in sc.destinations], [d.y for d in sc.destinations],
               s=10, c="dodgerblue", label="refuges", zorder=5)
    ax.scatter([d.x for d in sc.depots], [d.y for d in sc.depots], s=45, marker="^",
               c="black", label="depots", zorder=5)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(0, mx))
    fig.colorbar(sm, ax=ax, shrink=0.6, label="distinct households whose route crosses the segment")
    ax.set_title(f"Corridor convergence, Yeongdeok 2025 — top-{TOP_N} shared segments per network\n"
                 "solid: resident walk routes; dashed: rescuer drive routes; "
                 "shaded: forecast envelope p≥0.5 at 720 min (grey: at t0)\n"
                 "read-only diagnostic — no capacity, flow or congestion is modelled",
                 fontsize=9)
    # frame the drawn features (routes, chokepoints, POIs, envelope), not the whole canvas
    fx = [v for r in rows for v in (r["xy"][0][0], r["xy"][1][0])] + \
         [d.x for d in sc.destinations] + [d.x for d in sc.depots]
    fy = [v for r in rows for v in (r["xy"][0][1], r["xy"][1][1])] + \
         [d.y for d in sc.destinations] + [d.y for d in sc.depots]
    if ch:
        fx += px; fy += py
    er, ec = np.where(H >= 0.5)
    if len(er):
        fx += [g.minx + (ec.min()) * g.cell_size_m, g.minx + (ec.max() + 1) * g.cell_size_m]
        fy += [g.maxy - (er.max() + 1) * g.cell_size_m, g.maxy - (er.min()) * g.cell_size_m]
    pad = 0.06 * max(max(fx) - min(fx), max(fy) - min(fy))
    ax.set_xlim(min(fx) - pad, max(fx) + pad); ax.set_ylim(min(fy) - pad, max(fy) + pad)
    ax.set_aspect("equal")
    ax.legend(loc="lower left", fontsize=7)
    fig.savefig(FIG / "corridor_convergence_yeongdeok.png", dpi=140, bbox_inches="tight")
    plt.close(fig)


def append_doc(d: dict) -> None:
    g = d["reproduction_gate"]
    L = ["", f"_Run {d['generated_utc']} at `{d['git_commit'][:7]}`; artifact "
            f"`data/processed/corridor_convergence/convergence_yeongdeok.json`; "
            f"figure `docs/figures/corridor_convergence_yeongdeok.png`; {d['seconds_total']/60:.1f} min._", "",
         f"**Gate.** Canonical hazard sha256 `{g['hazard_sha256'][:16]}…` matches the committed run. "
         f"Four-way split re-derived on {g['n_origins']} origins as {g['four_way_counts']} — "
         f"{'identical to' if g['reproduced'] else 'DIFFERENT FROM'} the committed "
         f"`rescue_routing_real_hazard.json`. Routes collected: "
         f"{d['routes_collected']['walk_deployed']} deployed resident walks, "
         f"{d['routes_collected']['walk_naive']} naive walks, "
         f"{d['routes_collected']['drive_rescuer']} rescuer drives "
         f"({d['routes_collected']['no_route_contributed']} homes with no surviving ingress "
         f"contribute no route).", "",
         "### 7.0 Headline", ""]
    for k in ("walk", "drive"):
        h = d["headline"][k]
        if h["worst_chokepoint"] is None:
            L.append(f"- **{k}**: no articulation point or bridge in this run cuts more than one "
                     f"household from every refuge/depot it reaches, once the full network is "
                     f"allowed to offer a detour. Checked and ruled out (§6).")
        else:
            L.append(
                f"- **{k}**: convergence is real — the most-used single segment carries "
                f"**{h['max_households_on_one_edge']} of {h['households_routed']}** routed households, "
                f"and **{h['n_full_network_chokepoints']}** articulation points/bridges cut more than "
                f"one household from every refuge/depot it reaches even with the whole network available. "
                f"The worst is {h['worst_chokepoint_kind']} `{h['worst_chokepoint']}`, cutting "
                f"**{h['worst_chokepoint_households_cut']}** households. "
                + (f"**{h['n_full_network_chokepoints_fire_exposed']}** of those chokepoints ever enter "
                   f"the forecast envelope, and {h['n_top_fire_exposed']} of the top-{TOP_N} convergence "
                   f"edges do."
                   if h["wildfire_specific_finding"] else
                   f"**None of them is a wildfire finding**: no full-network chokepoint and none of the "
                   f"top-{TOP_N} convergence edges ever reaches p ≥ 0.5 at any forecast slice "
                   f"(worst chokepoint peaks at p = {h['worst_chokepoint_max_p_any_slice']}). Under §5 "
                   f"this is checked and ruled out for this fire on this terrain: the convergence "
                   f"exists, the fire does not go there."))
    c = d["headline"]["walk_naive_contrast"]
    L.append(
        f"- **status quo vs deployed (walk)**: the fire-blind `naive` routes put at most "
        f"{c['max_households_on_one_edge_naive']} households on one segment and "
        f"{c['n_top_fire_exposed_naive']} of their top-{TOP_N} shared segments are fire-exposed"
        + (f" ({', '.join(str(e['edge']) + ' — ' + str(e['households']) + ' households, p reaches ' + str(e['max_p_any_slice']) + ' by ' + str(e['first_min_p_ge_0_5']) + ' min' for e in c['fire_exposed_naive_edges'])})"
           if c["fire_exposed_naive_edges"] else "")
        + f"; the deployed future-aware routes put up to {c['max_households_on_one_edge_deployed']} "
        f"on one segment and {c['n_top_fire_exposed_deployed']} of theirs are fire-exposed. "
        f"So the router moves households off the shared segments the fire actually reaches and, "
        f"in doing so, concentrates them harder on shared segments it does not. Both halves of "
        f"that sentence are counts of routes, not of traffic (§1, §7.4).")
    L += ["",
         "### 7.1 Edge convergence", "",
         "| route set | edges used | edges shared by ≥2 households | most households on one edge | "
         f"fire-exposed in the top-{TOP_N} |", "|---|---:|---:|---:|---:|"]
    for k, t in d["convergence"].items():
        L.append(f"| {k} | {t['n_edges_used']} | {t['n_edges_shared_by_2_or_more']} | "
                 f"{t['max_households_on_one_edge']} | {t['n_top_fire_exposed']} |")
    for k, t in d["convergence"].items():
        fx = [r for r in t["top"] if r["fire_exposed"]]
        L += ["", f"**{k} — top shared segments that enter the forecast envelope "
                  f"(p ≥ 0.5 at some slice); {len(fx)} of {len(t['top'])} shown.**", ""]
        if not fx:
            L.append("None. Every one of this set's most-shared segments stays outside the "
                     "forecast envelope at every slice, so none of them is a wildfire finding (§5).")
            continue
        L += ["| edge (u, v) | households | length m | max p (any slice) | first min p≥0.5 | first min p≥0.7 |",
              "|---|---:|---:|---:|---:|---:|"]
        for r in fx:
            L.append(f"| {r['edge'][0]}–{r['edge'][1]} | {r['households']} | {r['length_m']} | "
                     f"{r['max_p_any_slice']} | {r['first_min_p_ge_0_5'] if r['first_min_p_ge_0_5'] is not None else '—'} | "
                     f"{r['first_min_p_ge_0_7'] if r['first_min_p_ge_0_7'] is not None else '—'} |")
    L += ["", "### 7.2 Articulation points and bridges (§6)", "",
          "| network | used subgraph nodes | edges | articulation points | bridges | tested | cutting >1 household |",
          "|---|---:|---:|---:|---:|---:|---:|"]
    for k, s in d["structural"].items():
        L.append(f"| {k} | {s['used_subgraph']['nodes']} | {s['used_subgraph']['edges']} | "
                 f"{s['n_articulation_points']} | {s['n_bridges']} | {s['n_candidates_tested']} | "
                 f"{s['n_findings_cutting_more_than_one_household']} |")
    for k, s in d["structural"].items():
        full = s["findings"]
        L += ["", f"**{k} network — candidates cutting more than one household.** "
                  f"{s['n_findings_full_network']} survive the full-network test (the headline, §6); "
                  f"{s['n_findings_used_subgraph_only']} more cut >1 household only in the thin "
                  f"union-of-routes subgraph, where a segment with no parallel route is "
                  f"trivially a bridge.", ""]
        if not full:
            L.append("None found: no articulation point or bridge cuts more than one household "
                     "from every refuge/depot it reaches once the full network may offer a detour.")
            continue
        L += ["| kind | id | households on it | cut (used subgraph) | cut (full network) | max p any slice | fire-exposed |",
              "|---|---|---:|---:|---:|---:|---|"]
        for f in full[:20]:
            L.append(f"| {f['kind']} | {f['id']} | {f['households_on_it']} | "
                     f"{f['households_cut_used_subgraph']} | {f['households_cut_full_network']} | "
                     f"{f.get('max_p_any_slice', '—')} | "
                     f"{'yes' if f.get('fire_exposed') else ('no' if 'fire_exposed' in f else '— (not probed: cuts ≤1 on the full network)')} |")
    L += ["", "### 7.3 Cross-check: are the two methods finding the same thing? (§6)", ""]
    for k, c in d["cross_check"].items():
        L.append(f"- **{k}**: {c['top_convergence_edges']} top convergence edges vs "
                 f"{c['full_network_chokepoint_edges']} full-network chokepoint edges and "
                 f"{c['full_network_chokepoint_nodes']} chokepoint nodes. "
                 f"{'Overlap: ' if c['overlap'] else 'No overlap — '}"
                 f"{('edges in both ' + str(c['edges_in_both']) + '; chokepoint nodes lying on a top edge ' + str(c['chokepoint_nodes_on_a_top_edge'])) if c['overlap'] else 'convergence-by-use and structural necessity are finding different segments in this terrain.'}")
    L += ["", "### 7.4 What this does and does not license", "",
          "Every count above is a count of routes over a segment. It is **not** a delay, a "
          "queue, a capacity breach or a congestion estimate; no such quantity is computed "
          "anywhere in this run, and no route was changed by it (§1). A segment listed here "
          "is a place a flow model *would have to be applied* to say anything about "
          "throughput — the Coclite–Garavello–Piccoli junction formulation (§2a) is the "
          "class of model that would be needed, and this repository does not contain one. "
          "The rescue-UNIT supply capacity layer is a different layer and is unaffected."]
    DOC.write_text(DOC.read_text(encoding="utf-8").rstrip("\n") + "\n" + "\n".join(L) + "\n",
                   encoding="utf-8")
    print("\n".join(L), flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
