"""Mission decisions under a recorded acceptance rule (Contract D) with a pluggable contact planner.

Decision procedure (research evaluation, centre semantics):
  1. Plan the exact contact-only relaxation (planner, e.g. the frozen sweep or SIPP) under the members the rule
     requires; dose and peak are relaxed in the plan.
  2. Check the witness per member with the frozen centre checker (`check.member_reports`): contact, peak, linear dose,
     TDU dose, pass flag. Apply the rule with the redistributed member weights.
  3. If a contact-free candidate fails a dose or peak limit, use lazy constraint generation when the planner accepts
     extra blocked (edge, departure-window) constraints: block the departure windows of the legs that carry the failing
     member's exposure and replan, up to `lazy_cap` iterations; otherwise, and when the cap is reached, the mission is
     UNRESOLVED (never a route, never a refusal).

Outcomes use the Route-Check API verdicts: checked_route, model_no_route, unresolved.

Chance-constrained (k_of_m) search is exact subset enumeration: a journey that passes in a member subset S of weight
>= k/m must avoid contact in S, and arrival(S) is monotone in S, so the earliest relaxed arrival is the minimum over the
minimal qualifying subsets. Two exact prunings: (a) the present-fire enclosure is shared by every member, so
arrival(shared) <= arrival(S) <= arrival(all) and equality of the two ends settles the search; (b) a member whose
first-new ignition cells touch no road edge bounding box (padded by 1 m, the sweep's own prefilter) cannot change any
plan and is added to every subset for free. Enumeration beyond `subset_cap` planner calls stops with UNRESOLVED unless a
route already attains the shared lower bound.
"""
from __future__ import annotations

import itertools
import math
import time
from fractions import Fraction as F

from . import acceptance as A
from .check import member_reports
from .planner import NO_ROUTE, ROUTE, UNRESOLVED, sweep_plan

CHECKED, NOROUTE, UNRES = "checked_route", "model_no_route", "unresolved"


def road_cells(graph):
    """Graph cells whose rectangle, padded by 1 m, meets the bounding box of some directed edge (cached per graph)."""
    key = id(graph)
    cached = _ROAD_CELLS.get(key)
    if cached is not None and cached[0] is graph:
        return cached[1]
    g = graph["grid"]
    res, x0, y0, W, H = float(g["resolution"]), float(g["x0"]), float(g["y0"]), int(g["width"]), int(g["height"])
    nodes = {n["id"]: (float(n["x"]), float(n["y"])) for n in graph["nodes"]}
    cells = set()
    for e in graph["edges"]:
        (ux, uy), (vx, vy) = nodes[e["u"]], nodes[e["v"]]
        c0 = max(0, math.floor((min(ux, vx) - 1 - x0) / res)); c1 = min(W - 1, math.floor((max(ux, vx) + 1 - x0) / res))
        r0 = max(0, math.floor((min(uy, vy) - 1 - y0) / res)); r1 = min(H - 1, math.floor((max(uy, vy) + 1 - y0) / res))
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                cells.add(r * W + c)
    _ROAD_CELLS[key] = (graph, cells)
    return cells


_ROAD_CELLS = {}


def free_members(graph, model):
    roads = road_cells(graph)
    return [j for j, ev in enumerate(model.events) if not (set(ev) & roads)]


def _legs_to_block(graph, hazard, request, legs, destination, member_index):
    """Departure windows to forbid for a member that fails dose or peak: every EDGE leg whose span carries positive
    flux in that member (lazy constraint generation). Returns {edge index: [(start, start)]}."""
    from .check import journey_spans
    from . import kit
    ind = kit.install()["independent"]
    nodes = {n["id"]: n for n in graph["nodes"]}
    edges = {e["id"]: e for e in graph["edges"]}
    eidx = {e["id"]: i for i, e in enumerate(graph["edges"])}
    m = hazard["members"][member_index]
    out = {}
    for leg in legs:
        if leg["kind"] != "EDGE":
            continue
        for cell, a, b in ind._occupancy(graph, leg, nodes, edges):
            import bisect
            k = min(max(0, bisect.bisect_right(m["breakpoints"], float(a)) - 1), len(m["flux"]) - 1)
            if float(m["flux"][k][cell]) > 0:
                out.setdefault(eidx[leg["edge"]], []).append((int(leg["start"]), int(leg["start"])))
                break
    return out


def _evaluate(graph, hazard, request, plan, weights, rule, radiation_law, reporter=None):
    if reporter is not None:
        reports = reporter(plan)
    else:
        reports = member_reports(graph, hazard, request, plan["legs"], plan["destination"], radiation_law=radiation_law)
    flags = [r["passed"] for r in reports]
    return reports, flags, A.passes(flags, weights, rule)


def decide(graph, hazard, request, model, *, rule=None, weights=None, planner=sweep_plan, wall_s=600.0, radiation_law="v1",
           lazy_cap=8, subset_cap=256, reporter=None):
    """Return a decision dict (Contract D fields) for one mission. `reporter(plan) -> per-member reports` replaces the
    frozen checker (hazard may then be None; lazy constraints then need the hazard and are unavailable)."""
    rule = rule or {"rule": "all", "k": len(model.ids), "m": len(model.ids)}
    if hazard is not None and [m["id"] for m in hazard["members"]] != list(model.ids):
        raise ValueError("hazard members and contact model members differ")
    weights = A.normalise_weights(weights if weights is not None else model.weights)
    t0 = time.perf_counter()
    log = {"planner_calls": 0, "lazy_iterations": 0, "subsets_evaluated": 0}

    def plan(m, extra=None):
        log["planner_calls"] += 1
        return planner(graph, request, m, extra_blocked=extra, wall_s=wall_s) if extra else planner(graph, request, m, wall_s=wall_s)

    def finish(verdict, reason, plan_=None, reports=None, flags=None, subset=None):
        horizon = float(request["horizon"])
        arrival = plan_["arrival"] if (plan_ is not None and verdict == CHECKED) else None
        out = {"verdict": verdict, "reason": reason, "rule": rule, "arrival_s": arrival,
               "legs": plan_["legs"] if verdict == CHECKED else [], "destination": plan_["destination"] if verdict == CHECKED else None,
               "per_member": reports, "member_pass": flags, "weights": [float(w) for w in weights],
               "passing_weight": float(A.passing_weight(flags, weights)) if flags else None,
               "planning_subset": subset, "planner": plan_["planner"] if plan_ else None,
               "plan_raw_status": plan_["raw_status"] if plan_ else None, "wall_s": time.perf_counter() - t0, **log}
        if verdict == CHECKED and flags is not None:
            alpha = 1 - A.required_fraction(rule) if rule["rule"] == "k_of_m" else F(1, 10)
            out["cvar_alpha"] = float(alpha)
            out["cvar_arrival_s"] = A.cvar(A.member_arrivals(arrival, flags, horizon), weights, alpha)
        return out

    def check_with_lazy(sub_model, subset):
        extra = {}
        p = plan(sub_model)
        while True:
            if p["status"] == NO_ROUTE:
                # after a lazy cut the relaxation is no longer exact, so exhaustion is not a refusal
                return ("NO_ROUTE", p, None, None) if not extra else ("LAZY_CUTS_EXHAUSTED", p, None, None)
            if p["status"] != ROUTE:
                return ("UNRESOLVED", p, None, None)
            reports, flags, ok = _evaluate(graph, hazard, request, p, weights, rule, radiation_law, reporter)
            if ok:
                return ("OK", p, reports, flags)
            # contact-free in the planning subset but failing the rule: contact in other members (k_of_m), or dose/peak
            failing = [j for j in subset if not flags[j] and not reports[j]["contact"]]
            if not failing:
                return ("RULE_FAILED", p, reports, flags)
            if hazard is None:
                return ("LAZY_UNSUPPORTED", p, reports, flags)
            if log["lazy_iterations"] >= lazy_cap:
                return ("LAZY_CAP", p, reports, flags)
            add = _legs_to_block(graph, hazard, request, p["legs"], p["destination"], failing[0])
            add = {e: [w for w in ws if w not in extra.get(e, [])] for e, ws in add.items()}
            add = {e: ws for e, ws in add.items() if ws}
            if not add:
                return ("LAZY_NO_CONSTRAINT", p, reports, flags)
            for e, ws in add.items():
                extra.setdefault(e, []).extend(ws)
            log["lazy_iterations"] += 1
            try:
                p = plan(sub_model, extra)
            except NotImplementedError:
                return ("LAZY_UNSUPPORTED", p, reports, flags)

    all_idx = list(range(len(model.ids)))
    if rule["rule"] == "all":
        state, p, reports, flags = check_with_lazy(model, all_idx)
        if state == "OK":
            return finish(CHECKED, "ALL_MEMBERS_PASS", p, reports, flags, all_idx)
        if state == "NO_ROUTE":
            return finish(NOROUTE, p["raw_status"] + ":" + str(p["reason"]), p, subset=all_idx)
        return finish(UNRES, state + ":" + str(p.get("raw_status")), p, reports, flags, all_idx)

    # ---------------------------------------------------------------- k_of_m: exact subset enumeration
    need = A.required_fraction(rule)
    shared = plan(model.shared_only())
    if shared["status"] == NO_ROUTE:
        return finish(NOROUTE, "SHARED_PRESENT_FIRE_" + str(shared["raw_status"]), shared, subset=[])
    if shared["status"] != ROUTE:
        return finish(UNRES, "SHARED_PLAN_" + str(shared["raw_status"]), shared, subset=[])
    state, p_all, rep_all, flags_all = check_with_lazy(model, all_idx)
    if state == "OK" and p_all["arrival"] == shared["arrival"]:
        return finish(CHECKED, "ALL_MEMBERS_ATTAIN_SHARED_BOUND", p_all, rep_all, flags_all, all_idx)
    free = free_members(graph, model)
    nonfree = [j for j in all_idx if j not in free]
    w_free = sum(weights[j] for j in free)
    best = (p_all, rep_all, flags_all, all_idx) if state == "OK" else None
    capped = False
    states = []
    # minimal qualifying subsets of the non-free members, smallest first
    for r in range(0, len(nonfree) + 1):
        found_at_size = False
        for combo in itertools.combinations(nonfree, r):
            wsum = w_free + sum(weights[j] for j in combo)
            if wsum < need:
                continue
            if any(w_free + sum(weights[j] for j in combo if j != i) >= need for i in combo):
                continue                                        # not minimal
            if log["subsets_evaluated"] >= subset_cap:
                capped = True
                break
            log["subsets_evaluated"] += 1
            subset = sorted(free + list(combo))
            st, p, reports, flags = check_with_lazy(model.subset(subset), subset)
            states.append(st)
            found_at_size = True
            if st == "OK" and (best is None or p["arrival"] < best[0]["arrival"]):
                best = (p, reports, flags, subset)
                if p["arrival"] == shared["arrival"]:
                    return finish(CHECKED, "K_OF_M_SUBSET_ATTAINS_SHARED_BOUND", p, reports, flags, subset)
        if capped:
            break
        _ = found_at_size
    if best is not None and not capped:
        exact = all(s in ("OK", "NO_ROUTE") for s in states)
        return finish(CHECKED, "K_OF_M_MINIMUM_OVER_MINIMAL_SUBSETS" if exact else "K_OF_M_CHECKED_NOT_PROVEN_EARLIEST", *best)
    if capped:
        if best is not None:
            return finish(UNRES, "SUBSET_CAP_BEST_NOT_PROVEN_EARLIEST", best[0], best[1], best[2], best[3])
        return finish(UNRES, "SUBSET_CAP", shared, subset=[])
    if states and all(s == "NO_ROUTE" for s in states):
        return finish(NOROUTE, "EVERY_MINIMAL_QUALIFYING_SUBSET_EXHAUSTED", shared, subset=[])
    return finish(UNRES, "NO_CHECKED_ROUTE_" + ",".join(sorted(set(states))), shared, subset=[])
