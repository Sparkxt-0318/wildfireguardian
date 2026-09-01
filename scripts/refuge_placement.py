#!/usr/bin/env python
"""Session 22 — if ONE temporary refuge could go anywhere, where should it go?

    python scripts/refuge_placement.py --baseline      # Phase 0 record
    python scripts/refuge_placement.py --optimize      # Phases 1-2
    python scripts/refuge_placement.py --verify        # Phase 2/3 checks
    python scripts/refuge_placement.py --collect       # assemble + write

⚠⚠ THIS OPTIMISES REACHABILITY, NOT FIRE SAFETY. The objective is "can these
households WALK there inside the evaluation window", nothing more. Session 17's
zero-hazard control showed this layer's failure set is set-identical with no
fire at all at every horizon, so the quantity being maximised here is a
geometric one. **A refuge placed where the fire will arrive is worse than
useless**, and this objective cannot tell you that. Phase 3 runs the survival
filter on the recommendations separately; it is not part of the objective.

⚠ PROVISIONAL. Session 21 (real 도로명주소 building footprints) has NOT run —
it is blocked on a logged-in portal download (docs/BLOCKERS.md). Every
household count here rests on the **124-building OSM snapshot**, which is
sparse for rural Korea: the same Overpass query returns 1,763 buildings for
Mati and 988 for Paradise against 74–124 for 영덕. **Every count below is
provisional and will move when real footprints land.**

WHY A FAST EXACT SEARCH IS LEGITIMATE HERE
------------------------------------------
Evaluating one candidate through the full layer costs ~50 s (4 ignitions x 3
scenarios x 110 origins). Thousands of candidates is not feasible that way.
But Session 17 measured that the failing set is IDENTICAL under a null hazard
at all six horizons, so under this layer's own semantics a household fails iff
its free-flow walk time to the nearest surviving refuge exceeds the horizon.
That makes the search a shortest-path problem: 110 single-source Dijkstras give
every household's time to EVERY node, and each candidate is then a lookup.

**This is a claim, so it is checked rather than trusted.** ``--verify`` re-runs
the TOP candidates through the full layer with the real elliptical hazard and
compares the saved-household sets. A disagreement is reported, not smoothed.

THE LINE THIS DOES NOT CROSS
----------------------------
This is a GEOMETRIC RECOMMENDATION under stated assumptions. It is not a siting
decision. Land ownership, construction feasibility, building standards, budget,
capacity, staffing, opening hours and community consultation are **not
modelled**. The only defensible sentence is: "현재 가정 하에서, 이 위치에
임시 대피소를 두면 N가구가 도보 대피 가능 범위 안으로 들어옵니다."
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

OUT = REPO / "data" / "processed" / "vulnerability"
CACHE = OUT / "placement_cache"

#: Horizons the recommendation is tested across. The default is 240 (grounded
#: in Session 20); the others are here because ranking instability across
#: horizons is a KNOWN property of this layer (rho = 0.333 between 30 and 240).
HORIZONS = (60.0, 120.0, 240.0)
DEFAULT_HORIZON = 240.0

#: --- CANDIDATE CONSTRAINTS. The constraint set determines the answer, so
#: every one of these is stated, and each is swept in --collect. ---

#: 1. REACHABLE. Candidates are walk-network nodes, so reachability holds by
#:    construction. This is an ENUMERATION, not a sample — there is no
#:    sampling density to sweep because nothing is sampled.

#: 2. FAR FROM THE MOUNTAIN. 행안부's wildfire guidance names 산에서 멀리
#:    떨어진 마을회관·학교·공터. Encoded as: the candidate's distance to the
#:    nearest grid cell whose burnable fraction is at or above
#:    FUEL_IS_FOREST must exceed MOUNTAIN_CLEARANCE_M.
FUEL_IS_FOREST = 0.5
MOUNTAIN_CLEARANCE_M = 300.0
MOUNTAIN_CLEARANCE_SWEEP_M = (0.0, 150.0, 300.0, 500.0)

#: 3. PLAUSIBLE HOST. A refuge needs somewhere to be. Either an existing
#:    building within HOST_BUILDING_M (designating an existing structure is far
#:    cheaper than building one), or open low-fuel ground within HOST_OPEN_M of
#:    the node (공터). Reported per candidate so the reader can see which.
HOST_BUILDING_M = 60.0
HOST_OPEN_M = 100.0


def _load():
    from vulnerability_sensitivity import load_yeongdeok
    return load_yeongdeok()


def _node_arrays(net):
    nodes = list(net.graph.nodes)
    xy = np.array([net.node_xy(n) for n in nodes], dtype="float64")
    return nodes, xy


def household_time_matrix(net, origin_nodes, nodes):
    """(n_households_unique, n_nodes) free-flow walk minutes.

    One Dijkstra per distinct origin node — 110 of them over ~8.4k nodes.
    """
    import networkx as nx

    idx = {n: i for i, n in enumerate(nodes)}
    D = np.full((len(origin_nodes), len(nodes)), np.inf, dtype="float64")
    for i, src in enumerate(origin_nodes):
        if src not in net.graph:
            continue
        dist = nx.single_source_dijkstra_path_length(net.graph, src,
                                                     weight="time_min")
        for n, t in dist.items():
            j = idx.get(n)
            if j is not None:
                D[i, j] = t
    return D


def fuel_distance(grid, burnable, xy):
    """Distance (m) from each point to the nearest forest-fuel grid cell."""
    from scipy.spatial import cKDTree

    b = np.asarray(burnable, dtype="float64")
    rows, cols = np.where(b >= FUEL_IS_FOREST)
    if not len(rows):
        return np.full(len(xy), np.inf)
    # Grid cell centres in projected metres.
    cx = grid.minx + (cols + 0.5) * grid.cell_size_m
    cy = grid.maxy - (rows + 0.5) * grid.cell_size_m
    tree = cKDTree(np.column_stack([cx, cy]))
    d, _ = tree.query(np.asarray(xy, dtype="float64"), k=1)
    return d


def build_candidates(res, clearance_m=MOUNTAIN_CLEARANCE_M):
    """Every walk node that satisfies the stated constraints."""
    from scipy.spatial import cKDTree

    net = res["net"]
    nodes, nxy = _node_arrays(net)
    d_fuel = fuel_distance(res["grid"], res["burnable"], nxy)

    bxy = np.asarray(res["buildings"].xy, dtype="float64")
    d_build = (cKDTree(bxy).query(nxy, k=1)[0] if len(bxy)
               else np.full(len(nxy), np.inf))

    existing = np.asarray(res["refuge_xy"], dtype="float64")
    d_refuge = (cKDTree(existing).query(nxy, k=1)[0] if len(existing)
                else np.full(len(nxy), np.inf))

    far_enough = d_fuel > clearance_m
    host_building = d_build <= HOST_BUILDING_M
    host_open = d_fuel > HOST_OPEN_M
    plausible = host_building | host_open
    keep = far_enough & plausible

    return {
        "nodes": nodes, "xy": nxy, "mask": keep,
        "d_fuel_m": d_fuel, "d_building_m": d_build, "d_refuge_m": d_refuge,
        "host_building": host_building, "host_open": host_open,
        "n_nodes_total": int(len(nodes)),
        "n_candidates": int(keep.sum()),
        "clearance_m": clearance_m,
    }


def coverage(D, inv, failing_mask, horizon):
    """(n_candidates_all_nodes,) bitmask of which FAILING households each node saves."""
    # D is per distinct origin node; expand to households via `inv`.
    Dh = D[inv]                                    # (n_households, n_nodes)
    reach = Dh <= horizon                          # household can walk there
    fail_idx = np.where(failing_mask)[0]
    return reach[fail_idx], fail_idx               # (n_failing, n_nodes)


def baseline_state(res, horizon=DEFAULT_HORIZON):
    """Who fails now, and how far each is from the nearest existing refuge."""
    net = res["net"]
    nodes, _ = _node_arrays(net)
    origin_nodes = [int(n) for n in res["uniq_nodes"]]
    inv = np.asarray(res["inverse"])

    D = household_time_matrix(net, origin_nodes, nodes)
    idx = {n: i for i, n in enumerate(nodes)}
    ref_cols = [idx[s] for s in net.shelters if s in idx]
    t_ref = (D[:, ref_cols].min(axis=1) if ref_cols
             else np.full(len(origin_nodes), np.inf))
    t_hh = t_ref[inv]
    failing = t_hh > horizon
    return {"D": D, "nodes": nodes, "inv": inv, "t_hh": t_hh,
            "failing": failing, "n_refuges": len(ref_cols),
            "n_households": int(len(t_hh)),
            "n_failing": int(failing.sum()), "horizon_min": horizon}


def _summ(v):
    v = np.asarray(v, dtype="float64"); f = v[np.isfinite(v)]
    if not len(f):
        return None
    return {"n_finite": int(len(f)), "median": round(float(np.median(f)), 1),
            "min": round(float(f.min()), 1), "max": round(float(f.max()), 1)}


def optimize(horizon=DEFAULT_HORIZON, clearance_m=MOUNTAIN_CLEARANCE_M,
             top_n=10):
    res, _ = _load()
    base = baseline_state(res, horizon)
    cand = build_candidates(res, clearance_m)

    reach_fail, fail_idx = coverage(base["D"], base["inv"], base["failing"],
                                    horizon)
    mask = cand["mask"]
    saves = reach_fail & mask[None, :]              # (n_failing, n_nodes)
    n_saved = saves.sum(axis=0)
    n_saved[~mask] = 0

    # ⚠ DEDUPLICATE BY COVERAGE SET. Adjacent walk nodes in the same isolated
    # pocket save the SAME households, so a raw top-10 is ten near-identical
    # points 40 m apart — useless to an operator. One row per distinct coverage
    # set, and the representative is the node with the LOWEST post-placement
    # median walk time, which is a real outcome tiebreak rather than an
    # arbitrary one. The count of equivalent nodes is reported because it IS
    # useful: it is how much siting freedom the recommendation allows.
    by_set: dict[int, list[int]] = {}
    for j in np.where(mask)[0]:
        if n_saved[j] == 0:
            continue
        bits = 0
        for i in np.where(saves[:, j])[0]:
            bits |= (1 << int(i))
        by_set.setdefault(bits, []).append(int(j))

    def after_median(j, hh):
        before = base["t_hh"][hh]
        return float(np.median(np.minimum(before, base["D"][base["inv"][hh], j])))

    ranked = []
    for bits, js in by_set.items():
        hh = [int(fail_idx[i]) for i in range(len(fail_idx)) if (bits >> i) & 1]
        rep = min(js, key=lambda j: after_median(j, hh))
        ranked.append((len(hh), -after_median(rep, hh), rep, bits, len(js)))
    ranked.sort(key=lambda t: (-t[0], -t[1]))

    top = []
    for n_hh, _neg, j, bits, n_equiv in ranked[:top_n]:
        hh = [int(fail_idx[i]) for i in range(len(fail_idx)) if (bits >> i) & 1]
        before = base["t_hh"][hh]
        after = np.minimum(before, base["D"][base["inv"][hh], j])
        top.append({
            "n_equivalent_nodes": n_equiv,
            "node": int(cand["nodes"][j]),
            "x": round(float(cand["xy"][j, 0]), 1),
            "y": round(float(cand["xy"][j, 1]), 1),
            "n_saved": int(n_saved[j]),
            "saved_households": hh,
            "walk_min_before_median": round(float(np.median(before)), 1),
            "walk_min_after_median": round(float(np.median(after)), 1),
            "distance_to_forest_fuel_m": round(float(cand["d_fuel_m"][j]), 1),
            "distance_to_nearest_building_m": round(float(cand["d_building_m"][j]), 1),
            "distance_to_nearest_existing_refuge_m": round(float(cand["d_refuge_m"][j]), 1),
            "host_type": ("existing building within "
                          f"{HOST_BUILDING_M:.0f} m"
                          if cand["host_building"][j] else "open low-fuel ground"),
        })

    # --- marginal curve: exact optimum for k = 1, 2, 3 over DISTINCT coverage
    # sets. Deduplicating by coverage bitmask collapses thousands of nodes to a
    # handful of distinct sets, so the triple search is exact, not greedy.
    masks: dict[int, int] = {}
    for j in np.where(mask)[0]:
        bits = 0
        for i in np.where(saves[:, j])[0]:
            bits |= (1 << int(i))
        if bits and (bits not in masks):
            masks[bits] = int(j)
    keys = list(masks)

    def popcount(x):
        return bin(x).count("1")

    # Combinations are over DISTINCT sets and never reuse the same set twice —
    # placing "two refuges" that are the same site is not two refuges.
    best = {}
    best[1] = max(((popcount(a), (a,)) for a in keys), default=(0, ()))
    best[2] = max(((popcount(keys[i] | keys[j2]), (keys[i], keys[j2]))
                   for i in range(len(keys)) for j2 in range(i + 1, len(keys))),
                  default=(0, ()))
    best[3] = max(((popcount(keys[i] | keys[j2] | keys[k]),
                    (keys[i], keys[j2], keys[k]))
                   for i in range(len(keys))
                   for j2 in range(i + 1, len(keys))
                   for k in range(j2 + 1, len(keys))), default=(0, ()))

    union_all = 0
    for a in keys:
        union_all |= a
    unsavable = [int(fail_idx[i]) for i in range(len(fail_idx))
                 if not (union_all >> i) & 1]

    return {
        "horizon_min": horizon,
        "provisional": (
            "PROVISIONAL — Session 21 (real 도로명주소 footprints) has not run; "
            "these counts rest on the 124-building OSM snapshot, which is sparse "
            "for rural Korea. Every household count will move when real "
            "footprints land."),
        "objective": (
            "Number of currently-failing households whose free-flow walk time "
            "to the new refuge is within the horizon. REACHABILITY ONLY — this "
            "does not ask whether the refuge survives the fire."),
        "constraints": {
            "reachable": "candidates ARE walk-network nodes; enumeration, not a sample",
            "mountain_clearance_m": clearance_m,
            "fuel_is_forest_burnable_fraction": FUEL_IS_FOREST,
            "host_building_within_m": HOST_BUILDING_M,
            "host_open_ground_fuel_distance_m": HOST_OPEN_M,
            "n_walk_nodes_total": cand["n_nodes_total"],
            "n_candidates_after_filter": cand["n_candidates"],
        },
        "baseline": {
            "n_households": base["n_households"],
            "n_failing": base["n_failing"],
            "n_existing_refuges": base["n_refuges"],
            "walk_min_failing": _summ(base["t_hh"][base["failing"]]),
            "walk_min_safe": _summ(base["t_hh"][~base["failing"]]),
            "failing_households": [int(i) for i in np.where(base["failing"])[0]],
        },
        "top": top,
        "marginal_curve": {
            "k1_saved": int(best[1][0]),
            "k2_saved": int(best[2][0]),
            "k3_saved": int(best[3][0]),
            "k1_nodes": [int(cand["nodes"][masks[m]]) for m in best[1][1]],
            "k2_nodes": [int(cand["nodes"][masks[m]]) for m in best[2][1]],
            "k3_nodes": [int(cand["nodes"][masks[m]]) for m in best[3][1]],
            "k2_gain_over_k1": int(best[2][0] - best[1][0]),
            "k3_gain_over_k2": int(best[3][0] - best[2][0]),
            "n_distinct_coverage_sets": len(keys),
            "method": ("exact over distinct coverage bitmasks, not greedy — "
                       "deduplication makes the k=3 search tractable"),
        },
        "ceiling": {
            "n_savable_by_any_placement": int(popcount(union_all)),
            "n_unsavable": len(unsavable),
            "unsavable_households": unsavable,
            "reading": (
                "Households no single refuge at ANY candidate site can bring "
                "inside the horizon. Refuge placement cannot help them; they "
                "need a different intervention — vehicle-assisted evacuation, "
                "pre-emptive relocation, or road work. Naming this set is as "
                "much of the result as the optimum is."),
        },
    }


def verify_against_full_layer(node, horizon=DEFAULT_HORIZON):
    """Phase 2 check — does the FULL layer agree with the fast search?

    Adds the candidate to the refuge set and re-runs the real evaluation
    (elliptical hazard, 4 ignitions x 3 scenarios). The fast search is exact
    only if the null-hazard equivalence holds; this is what tests that instead
    of assuming it.
    """
    import vulnerability_layer as vlm
    from wildfireguardian.vulnerability.hazard_sources import EllipticalHazard
    from wildfireguardian.vulnerability.ignition import IgnitionSampler

    res, _ = _load()
    net = res["net"]
    hp = vlm.human_points(res)
    igs = IgnitionSampler(prior="human_proximity").sample(
        res["grid"], res["burnable"], hp, 4, res["buildings"].xy)

    def run():
        nr = vlm.evaluate_ignitions(res, igs, EllipticalHazard(),
                                    horizon_min=horizon, refuge_buffer_min=0.0)
        h = vlm.to_households(res, nr)
        v = np.asarray(h["vulnerability"], dtype="float64")
        return set(int(i) for i in np.where(v > 0)[0]), h["vulnerability_mean"]

    before_set, before_mean = run()
    original = set(net.shelters)
    net.shelters = original | {int(node)}
    try:
        after_set, after_mean = run()
    finally:
        net.shelters = original

    predicted = set(baseline_predicted_saves(res, node, horizon))
    actual = before_set - after_set
    return {
        "node": int(node), "horizon_min": horizon,
        "full_layer_failing_before": len(before_set),
        "full_layer_failing_after": len(after_set),
        "full_layer_saved": sorted(actual),
        "fast_search_predicted_saved": sorted(predicted),
        "agree": bool(actual == predicted),
        "only_in_full_layer": sorted(actual - predicted),
        "only_in_fast_search": sorted(predicted - actual),
        "vulnerability_mean_before": before_mean,
        "vulnerability_mean_after": after_mean,
    }


def baseline_predicted_saves(res, node, horizon):
    base = baseline_state(res, horizon)
    nodes = base["nodes"]
    idx = {n: i for i, n in enumerate(nodes)}
    j = idx.get(int(node))
    if j is None:
        return []
    Dh = base["D"][base["inv"], j]
    return [int(i) for i in np.where(base["failing"] & (Dh <= horizon))[0]]


def survival_check(nodes, horizon=DEFAULT_HORIZON):
    """Phase 3 — would the fire reach the recommended sites?

    Runs the SAME refuge-survival filter the layer uses, over the same
    ignition x scenario set, on the recommended locations.
    """
    import vulnerability_layer as vlm
    from wildfireguardian.vulnerability.hazard_sources import (
        EllipticalHazard, Weather)
    from wildfireguardian.vulnerability.ignition import IgnitionSampler
    from wildfireguardian.vulnerability.refuge import time_to_cutoff

    res, _ = _load()
    net = res["net"]
    hp = vlm.human_points(res)
    igs = IgnitionSampler(prior="human_proximity").sample(
        res["grid"], res["burnable"], hp, 4, res["buildings"].xy)
    times = np.linspace(0.0, horizon, vlm.N_TIME_SLICES)
    src = EllipticalHazard()

    rows = []
    n_pairs = 0
    for ig in igs:
        for name, spd, toward in vlm.SCENARIOS:
            hz = src.build(res["grid"], (ig.x, ig.y), Weather(spd, toward, name),
                           times_min=times, elevation=res["elevation"],
                           burnable_frac=res["burnable"])
            n_pairs += 1
            for nd in nodes:
                x, y = net.node_xy(int(nd))
                t = time_to_cutoff(hz, x, y, vlm.P_CUT)
                if np.isfinite(t):
                    rows.append({"node": int(nd), "scenario": name,
                                 "burn_time_min": round(float(t), 1)})
    return {
        "horizon_min": horizon,
        "n_sites_checked": len(nodes),
        "n_ignition_scenario_pairs": n_pairs,
        "n_site_scenario_evaluations": len(nodes) * n_pairs,
        "n_reached_by_fire": len(rows),
        "reached": rows,
        "filter_binding": bool(rows),
        "note": ("The survival filter is NOT part of the objective. The "
                 "objective maximises reachability only; this is a separate "
                 "check on the recommendations."),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", action="store_true")
    ap.add_argument("--optimize", action="store_true")
    ap.add_argument("--horizon", type=float, default=DEFAULT_HORIZON)
    ap.add_argument("--clearance", type=float, default=MOUNTAIN_CLEARANCE_M)
    ap.add_argument("--horizons", action="store_true",
                    help="does the recommendation survive a horizon change?")
    ap.add_argument("--sweep", action="store_true",
                    help="sensitivity to the mountain-clearance constraint")
    ap.add_argument("--verify", action="store_true",
                    help="full-layer check + refuge-survival check on the top")
    a = ap.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)

    if a.baseline:
        res, _ = _load()
        t = time.time()
        b = baseline_state(res, a.horizon)
        out = {
            "horizon_min": a.horizon,
            "n_households": b["n_households"],
            "n_failing": b["n_failing"],
            "n_existing_refuges": b["n_refuges"],
            "failing_households": [int(i) for i in np.where(b["failing"])[0]],
            "walk_min_per_household": [
                (None if not np.isfinite(v) else round(float(v), 1))
                for v in b["t_hh"]],
            "walk_min_failing": _summ(b["t_hh"][b["failing"]]),
            "walk_min_safe": _summ(b["t_hh"][~b["failing"]]),
            "seconds": round(time.time() - t, 1),
        }
        (CACHE / f"baseline_h{int(a.horizon)}.json").write_text(
            json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({k: out[k] for k in
                          ("n_households", "n_failing", "n_existing_refuges",
                           "walk_min_failing", "walk_min_safe", "seconds")},
                         indent=2, ensure_ascii=False))

    if a.optimize:
        t = time.time()
        o = optimize(a.horizon, a.clearance)
        o["seconds"] = round(time.time() - t, 1)
        p = CACHE / f"opt_h{int(a.horizon)}_c{int(a.clearance)}.json"
        p.write_text(json.dumps(o, indent=2, ensure_ascii=False) + "\n",
                     encoding="utf-8")
        print(json.dumps({"constraints": o["constraints"],
                          "baseline": {k: o["baseline"][k] for k in
                                       ("n_households", "n_failing",
                                        "n_existing_refuges")},
                          "top3": o["top"][:3],
                          "marginal_curve": o["marginal_curve"],
                          "ceiling": {k: o["ceiling"][k] for k in
                                      ("n_savable_by_any_placement",
                                       "n_unsavable", "unsavable_households")},
                          "seconds": o["seconds"]},
                         indent=2, ensure_ascii=False))

    if a.horizons:
        rows = []
        for H in HORIZONS:
            o = optimize(H, a.clearance)
            best = o["top"][0] if o["top"] else None
            rows.append({
                "horizon_min": H,
                "n_failing": o["baseline"]["n_failing"],
                "best_node": best["node"] if best else None,
                "best_n_saved": best["n_saved"] if best else 0,
                "best_saved_households": best["saved_households"] if best else [],
                "k1": o["marginal_curve"]["k1_saved"],
                "k2": o["marginal_curve"]["k2_saved"],
                "n_unsavable": o["ceiling"]["n_unsavable"],
            })
        # Does the SAME site stay best? Compare the saved-household SETS, since
        # equivalent nodes are interchangeable and node ids are not the point.
        sets = [set(r["best_saved_households"]) for r in rows]
        stable = all(s == sets[-1] for s in sets)
        out = {"by_horizon": rows,
               "recommendation_stable_across_horizons": bool(stable),
               "note": ("Compared by the SET OF HOUSEHOLDS SAVED, not by node "
                        "id — hundreds of adjacent nodes are interchangeable, "
                        "so comparing ids would report spurious instability.")}
        (CACHE / "horizon_robustness.json").write_text(
            json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(out, indent=2, ensure_ascii=False))

    if a.sweep:
        rows = []
        for c in MOUNTAIN_CLEARANCE_SWEEP_M:
            o = optimize(a.horizon, c)
            best = o["top"][0] if o["top"] else None
            rows.append({"clearance_m": c,
                         "n_candidates": o["constraints"]["n_candidates_after_filter"],
                         "best_n_saved": best["n_saved"] if best else 0,
                         "best_saved_households": best["saved_households"] if best else [],
                         "k1": o["marginal_curve"]["k1_saved"],
                         "k2": o["marginal_curve"]["k2_saved"]})
        sets = [set(r["best_saved_households"]) for r in rows]
        out = {"sweep": rows,
               "answer_invariant_to_constraint": bool(all(s == sets[0] for s in sets)),
               "note": ("The mountain-clearance threshold is a CHOICE, so its "
                        "effect on the answer is measured rather than assumed.")}
        (CACHE / "clearance_sweep.json").write_text(
            json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(out, indent=2, ensure_ascii=False))

    if a.verify:
        o = optimize(a.horizon, a.clearance)
        top_nodes = [t["node"] for t in o["top"]]
        v = verify_against_full_layer(top_nodes[0], a.horizon)
        s = survival_check(top_nodes, a.horizon)
        out = {"full_layer_verification": v, "survival_check": s}
        (CACHE / "verification.json").write_text(
            json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({"full_layer_verification": v,
                          "survival_check": {k: s[k] for k in
                                             ("n_sites_checked",
                                              "n_site_scenario_evaluations",
                                              "n_reached_by_fire",
                                              "filter_binding")}},
                         indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
