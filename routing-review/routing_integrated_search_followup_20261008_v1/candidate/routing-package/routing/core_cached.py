"""Bounded exact lattice search with per-member additive exposure labels.

All claims concern the supplied edge-grid forecast and discrete model only.
Search caps fail closed; the separately implemented checker gates every route.
"""

import bisect
import heapq
import math
import resource
import sys
import time
from fractions import Fraction


def node_cell(graph, node):
    g = graph["grid"]
    col = math.floor(
        (Fraction(node["x"]) - Fraction(g["x0"])) / Fraction(g["resolution"])
    )
    row = math.floor(
        (Fraction(node["y"]) - Fraction(g["y0"])) / Fraction(g["resolution"])
    )
    return row * g["width"] + col


def edge_occupancies(
    edge, start, end, from_fraction=0, to_fraction=1, graph=None, node_lookup=None
):
    """Exact rational chord/grid intersections, including every point contact.

    JSON segment fractions are canonical floating encodings for admission only;
    geometry is recomputed from represented coordinates to avoid cut rounding.
    """
    if graph is None:
        raise ValueError("graph required for exact geometry occupancy")
    ns = node_lookup or {n["id"]: n for n in graph["nodes"]}
    u, v = ns[edge["u"]], ns[edge["v"]]
    g = graph["grid"]
    f, q = Fraction(from_fraction), Fraction(to_fraction)
    cuts = {f, q}
    for axis, base, count in [("x", "x0", "width"), ("y", "y0", "height")]:
        a, b = Fraction(u[axis]), Fraction(v[axis])
        origin = Fraction(g[base])
        res = Fraction(g["resolution"])
        if a != b:
            for line in range(1, g[count]):
                c = (origin + line * res - a) / (b - a)
                if f < c < q:
                    cuts.add(c)
    cuts = sorted(cuts)

    def point(z):
        return {
            "x": Fraction(u["x"]) + z * (Fraction(v["x"]) - Fraction(u["x"])),
            "y": Fraction(u["y"]) + z * (Fraction(v["y"]) - Fraction(u["y"])),
        }

    def when(z):
        return (
            Fraction(start)
            if q == f
            else Fraction(start) + (Fraction(end) - Fraction(start)) * (z - f) / (q - f)
        )

    out = []
    for a, b in zip(cuts, cuts[1:]):
        out.append(
            {
                "cell": node_cell(graph, point((a + b) / 2)),
                "start": when(a),
                "end": when(b),
            }
        )
    for z in cuts:
        out.append(
            {"cell": node_cell(graph, point(z)), "start": when(z), "end": when(z)}
        )
    return out


def evaluate_occupancy(graph, hazard, occupancies):
    """Internal independent-of-search integration, not the delivery checker."""
    codes = set()
    per_member = {}
    for member in hazard["members"]:
        bp = member["breakpoints"]
        dose_exact, peak = Fraction(0), 0.0
        for occ in occupancies:
            cell, lo, hi = occ["cell"], occ["start"], occ["end"]
            if lo < bp[0] or hi > bp[-1] or hi < lo:
                codes.add("UNSUPPORTED")
                continue
            points = [lo, hi] + [p for p in bp[1:-1] if lo < p < hi]
            for p in points:
                i = min(len(bp) - 2, bisect.bisect_right(bp, p) - 1)
                if not member["support"][i][cell]:
                    codes.add("UNSUPPORTED")
                if member["flame"][i][cell]:
                    codes.add("FLAME_CONTACT")
                peak = max(peak, member["flux"][i][cell])
            first = max(0, bisect.bisect_right(bp, lo) - 1)
            for i in range(first, len(bp) - 1):
                a, b = max(lo, bp[i]), min(hi, bp[i + 1])
                if b > a:
                    dose_exact += (Fraction(b) - Fraction(a)) * Fraction(
                        member["flux"][i][cell]
                    )
                if bp[i + 1] >= hi:
                    break
        try:
            reported_dose = float(dose_exact)
        except OverflowError:
            reported_dose = None
        per_member[member["id"]] = {
            "dose": reported_dose,
            "dose_exact": dose_exact,
            "peak": peak,
        }
    return {"ok": not codes, "codes": sorted(codes), "per_member": per_member}


def check_route(graph, hazard, request, legs, destination):
    """Every public check delegates to the independently authored checker."""
    from .independent import check_route as independent_check

    return independent_check(graph, hazard, request, legs, destination)


def _globally_supported(hazard, request):
    # Deliberately conservative: unsupported cells outside this route withhold
    # a global optimality/infeasibility claim, even if no search label used them.
    return hazard["valid_from"] <= request["departure"] <= request["horizon"] <= hazard[
        "valid_until"
    ] and all(all(row) for m in hazard["members"] for row in m["support"])


def _lower_bounds(graph, destinations, dt):
    reverse = {n["id"]: [] for n in graph["nodes"]}
    for e in graph["edges"]:
        reverse[e["v"]].append((e["u"], e["travel_ticks"] * dt))
    distance = {v: math.inf for v in reverse}
    heap = []
    for d in destinations:
        distance[d["node"]] = 0
        heapq.heappush(heap, (0, d["node"]))
    while heap:
        cost, node = heapq.heappop(heap)
        if cost != distance[node]:
            continue
        for u, length in reverse[node]:
            candidate = cost + length
            if candidate < distance[u]:
                distance[u] = candidate
                heapq.heappush(heap, (candidate, u))
    return distance


def solve_cached(graph, hazard, request, *, prepared=None, geometry_cache=None, cache_enabled=True):
    """Instrumented exact search; opt-in lazy costs and static geometry reuse.

    Pass a PreparedGraph as graph, or a raw graph with prepared= to require
    exact contents equality. Forecast/request admission and checker still run.
    """
    from . import validation
    from .prepared import PreparedGraph
    from .search_geometry_cache import SearchGeometryCache

    start_clock = time.perf_counter()
    metrics = {
        "labels": 0,
        "expansions": 0,
        "dominated": 0,
        "peak_frontier": 0,
        "edge_candidates": 0,
        "wait_candidates": 0,
        "occupancy_evaluations": 0,
    }
    timing = {k: 0.0 for k in ("validation", "geometry_cache_binding", "geometry", "exposure", "dominance", "heuristic", "independent_check", "finalization")}
    cache_owner = None
    cache_initial = None
    limits = None
    loop_start = None
    structural_start = None
    structural_end = None
    setup_start = None
    setup_end = None
    live_pending = set()
    cost_cache = {}
    front, heap = {}, []
    metrics.update({k: 0 for k in ("generated_labels", "dose_rejected_labels", "evicted_dominance_labels", "heap_pushes", "heap_pops", "stale_heap_pops", "peak_heap_entries", "peak_live_pending_labels", "cost_cache_hits", "cost_cache_misses", "geometry_calls", "destination_labels", "destination_contract_attempts", "dwell_contract_rejects", "exposure_rejects", "destination_dose_rejects", "route_witness_checks", "checked_incumbents", "wait_retained_labels", "cap_rejected_labels", "live_front_references", "peak_front_references", "edge_geometry_calls", "node_geometry_calls", "rejected_costs", "wait_exposure_rejects", "edge_exposure_rejects")})
    solver = (
        request.get("solver", "baseline") if isinstance(request, dict) else "baseline"
    )

    def finish(status, reason, **extra):
        final_start = time.perf_counter()
        metrics["retained_labels"] = metrics["labels"]
        metrics["expanded_labels"] = metrics["expansions"]
        metrics["live_pending_labels"] = len(live_pending)
        metrics["cost_cache_entries"] = len(cost_cache)
        metrics["heap_entries"] = len(heap)
        metrics["peak_rss_mb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1048576 if sys.platform == "darwin" else 1024)
        metrics["rss_scope"] = "process lifetime maximum; includes imports, prior searches and external preparation in this process"
        metrics["cache_enabled"] = cache_enabled
        if cache_owner is not None:
            info = cache_owner.cache_info()
            metrics["geometry_cache_lifetime"] = info
            metrics["geometry_cache_search"] = {k: info[k]-cache_initial[k] for k in ("hits", "misses", "materializations", "evictions")}
        now = time.perf_counter()
        timing["search_loop"] = now-loop_start if loop_start is not None else 0.0
        timing["structural_preprocess"] = (structural_end if structural_end is not None else now)-structural_start if structural_start is not None else 0.0
        timing["search_setup"] = (setup_end if setup_end is not None else now)-setup_start if setup_start is not None else 0.0
        metrics["timing_s"] = timing
        metrics["timing_scope"] = "wall-clock phases; search_setup includes cache binding/issue geometry/exposure, search_loop includes geometry/exposure/dominance/check and initial finalization introspection; constructor and graph binding charged; external warm cache construction caller lifecycle"
        metrics["wall_s"] = time.perf_counter() - start_clock
        result = {
            "status": status,
            "reason": reason,
            "legs": [],
            "arrival": None,
            "destination": None,
            "per_member": {},
            "solver_status": status,
            "metrics": dict(metrics),
            "hazard_version": (
                hazard.get("version") if isinstance(hazard, dict) else None
            ),
            "provenance": {
                "solver": solver,
                "evidence_class": (
                    hazard.get("evidence_class") if isinstance(hazard, dict) else None
                ),
                "model": "EXACT_LATTICE_EDGEGRID",
                "physical_safety_claim": False,
            },
            "certificate_conditions": [],
        }
        result.update(extra)
        timing["finalization"] += time.perf_counter()-final_start
        result["metrics"] = dict(metrics)
        # Last elapsed sample follows all normal report/cache/RSS construction.
        # The enclosing caller must additionally charge serialization/launch work.
        final_elapsed = time.perf_counter()-start_clock
        result["metrics"]["wall_s"] = final_elapsed
        final_cap = ("WALL_CLOCK_DURING_FINALIZATION" if limits is not None and final_elapsed >= limits["wall_s"] else "RSS_LIMIT_DURING_FINALIZATION" if limits is not None and metrics["peak_rss_mb"] > limits.get("rss_limit_mb", 3072) else None)
        if final_cap is not None and status in ("CONDITIONAL_OPTIMUM", "CHECKED_ROUTE", "PROVEN_INFEASIBLE", "DISCONNECTED"):
            result["completed_decision_after_cap"] = {k: result[k] for k in ("status", "reason", "solver_status")}
            if result.get("checker", {}).get("ok"):
                result["checked_incumbent"] = {k: result[k] for k in ("legs", "arrival", "destination", "per_member", "checker", "hazard_version")}
                result["checked_incumbent"].update(status="CHECKED_ROUTE", proof_level="checked witness; optimum unresolved under cap", physical_safety_claim=False)
                metrics["checked_incumbents"] += 1
            result.update(status="TIMEOUT", reason=final_cap, solver_status="INCOMPLETE_CAP", legs=[], arrival=None, destination=None, per_member={}, certificate_conditions=[])
        result["metrics"]["checked_incumbents"] = metrics["checked_incumbents"]
        return result

    validation_start = time.perf_counter()
    try:
        if type(cache_enabled) is not bool:
            raise validation.ValidationError("GEOMETRY_CACHE_FLAG", "cache_enabled must be bool")
        if prepared is not None:
            if type(prepared) is not PreparedGraph:
                raise validation.ValidationError(
                    "PREPARED_GRAPH_TYPE", "prepared must be a PreparedGraph"
                )
            if not prepared.matches(graph):
                raise validation.ValidationError(
                    "PREPARED_GRAPH_MISMATCH",
                    "graph contents changed; prepare the replacement explicitly",
                )
            graph = prepared.snapshot()
        elif type(graph) is PreparedGraph:
            graph = graph.snapshot()
        else:
            graph = validation.validate_graph(graph)
        hazard = validation.validate_hazard(
            graph, hazard, as_of=request.get("as_of"), _graph_validated=True
        )
        request = validation.validate_request(
            graph, hazard, request, _validated_inputs=True
        )
    except validation.ValidationError as exc:
        timing["validation"] += time.perf_counter()-validation_start
        return finish(
            (
                "UNSUPPORTED"
                if "UNSUPPORTED" in exc.code or "IDENTIT" in exc.code
                else "INVALID_INPUT"
            ),
            exc.code,
            message=str(exc),
        )
    except (AttributeError, TypeError, KeyError) as exc:
        timing["validation"] += time.perf_counter()-validation_start
        return finish("INVALID_INPUT", "REQUEST_SHAPE", message=str(exc))
    timing["validation"] += time.perf_counter()-validation_start
    if solver == "activation":
        return finish("UNSUPPORTED", "ACTIVATION_NOT_PROMOTED")
    setup_start = time.perf_counter()
    nodes = {n["id"]: n for n in graph["nodes"]}
    edges = {e["id"]: e for e in graph["edges"]}
    outgoing = {n: [] for n in nodes}
    for e in graph["edges"]:
        outgoing[e["u"]].append(e)
    forbidden = set(tuple(t) for t in graph["forbidden_turns"])
    dt, departure, horizon = hazard["dt"], request["departure"], request["horizon"]
    member_ids = [m["id"] for m in hazard["members"]]
    # Exact arithmetic over the represented JSON numeric inputs. A positive
    # dose must never disappear when added to a large already-incurred dose.
    budgets = tuple(Fraction(request["budgets"]["dose"][m]) for m in member_ids)
    incurred = tuple(Fraction(request["incurred"][m]) for m in member_ids)
    peak_budget = request["budgets"]["peak"]
    limits = request["limits"]
    complete = _globally_supported(hazard, request)
    bind_start = time.perf_counter()
    if cache_enabled:
        if geometry_cache is None:
            cache_owner = SearchGeometryCache(graph)
        elif type(geometry_cache) is not SearchGeometryCache:
            timing["geometry_cache_binding"] += time.perf_counter()-bind_start
            return finish("INVALID_INPUT", "GEOMETRY_CACHE_TYPE")
        elif not geometry_cache.matches(graph):
            timing["geometry_cache_binding"] += time.perf_counter()-bind_start
            return finish("INVALID_INPUT", "GEOMETRY_CACHE_MISMATCH")
        else:
            cache_owner = geometry_cache
        cache_initial = cache_owner.cache_info()
    elif geometry_cache is not None:
        timing["geometry_cache_binding"] += time.perf_counter()-bind_start
        return finish("INVALID_INPUT", "GEOMETRY_CACHE_DISABLED_WITH_OWNER")
    timing["geometry_cache_binding"] += time.perf_counter()-bind_start

    def geometry(edge, start, end, from_fraction=0, to_fraction=1):
        mark = time.perf_counter()
        metrics["geometry_calls"] += 1
        metrics["edge_geometry_calls"] += 1
        try:
            if cache_owner is not None:
                return cache_owner.occupancies(edge["id"], start, end, from_fraction, to_fraction)
            return edge_occupancies(edge, start, end, from_fraction, to_fraction, graph, nodes)
        finally:
            timing["geometry"] += time.perf_counter()-mark

    def node_occupancy(node, start, end):
        mark = time.perf_counter()
        metrics["geometry_calls"] += 1
        metrics["node_geometry_calls"] += 1
        try:
            return [{"cell": node_cell(graph, nodes[node]), "start": start, "end": end}]
        finally:
            timing["geometry"] += time.perf_counter()-mark

    def exposure(occupancy):
        mark = time.perf_counter()
        try:
            return evaluate_occupancy(graph, hazard, occupancy)
        finally:
            timing["exposure"] += time.perf_counter()-mark

    position, incoming = request["position"], request["incoming_edge"]
    partial = None
    if "node" in position:
        origin = position["node"]
        issue = node_occupancy(origin, departure, departure)
    else:
        partial = edges[position["edge"]]
        origin = partial["v"]
        issue = geometry(
            partial,
            departure,
            departure,
            position["fraction"],
            position["fraction"],
        )
    metrics["occupancy_evaluations"] += 1
    issue_check = exposure(issue)
    if "UNSUPPORTED" in issue_check["codes"]:
        return finish("UNSUPPORTED", "AT_ISSUE_MISSING_SUPPORT")
    if (
        issue_check["codes"]
        or any(v > b for v, b in zip(incurred, budgets))
        or any(v["peak"] > peak_budget for v in issue_check["per_member"].values())
    ):
        for mid, spent in zip(member_ids, incurred):
            issue_check["per_member"][mid]["dose"] = request["incurred"][mid]
            issue_check["per_member"][mid].pop("dose_exact", None)
        return finish(
            "AT_ISSUE_FAILURE",
            "AT_ISSUE_CONSTRAINT_VIOLATION",
            per_member=issue_check["per_member"],
        )
    setup_end = time.perf_counter()
    # Static turn-aware disconnect is independent of the forecast/support mask.
    if time.perf_counter() - start_clock >= limits["wall_s"]:
        return finish("TIMEOUT", "WALL_CLOCK", solver_status="INCOMPLETE_CAP")
    structural_start = time.perf_counter()
    structural_seeds = [(origin, incoming)]
    if (
        partial is not None
        and graph.get("mid_edge_reversal")
        and 0 < position["fraction"] < 1
        and Fraction(1 - position["fraction"])
        == Fraction(1) - Fraction(position["fraction"])
        and partial.get("reverse_edge") in edges
        and (incoming, partial["reverse_edge"]) not in forbidden
    ):
        rev = edges[partial["reverse_edge"]]
        structural_seeds.append((rev["v"], rev["id"]))
    reachable, pending = set(structural_seeds), list(structural_seeds)
    destination_nodes = {d["node"] for d in request["destinations"]}
    while pending:
        if (
            len(reachable) % 64 == 0
            and time.perf_counter() - start_clock >= limits["wall_s"]
        ):
            return finish(
                "TIMEOUT", "WALL_CLOCK_PREPROCESS", solver_status="INCOMPLETE_CAP"
            )
        n, inc = pending.pop()
        for e in outgoing[n]:
            next_state = (e["v"], e["id"])
            if (inc, e["id"]) not in forbidden and next_state not in reachable:
                reachable.add(next_state)
                pending.append(next_state)
    structural_end = time.perf_counter()
    if not any(n in destination_nodes for n, _ in reachable):
        if time.perf_counter() - start_clock >= limits["wall_s"]:
            return finish(
                "TIMEOUT", "WALL_CLOCK_PREPROCESS", solver_status="INCOMPLETE_CAP"
            )
        return finish(
            "DISCONNECTED",
            "TURN_GRAPH_DISCONNECTED",
            solver_status="STRUCTURAL_DISCONNECT",
            certificate_conditions=[
                "declared directed graph and turn rules",
                "independent of forecast",
                "no physical safety claim",
            ],
        )
    heuristic_start = time.perf_counter()
    distance = (
        _lower_bounds(graph, request["destinations"], dt)
        if solver == "astar"
        else {n: 0 for n in nodes}
    )
    timing["heuristic"] += time.perf_counter()-heuristic_start

    def cost(key, build_occupancy):
        # Disabled mode deliberately preserves the original eager geometry call.
        occupancy = build_occupancy() if not cache_enabled else None
        if key not in cost_cache:
            metrics["cost_cache_misses"] += 1
            if occupancy is None:
                occupancy = build_occupancy()
            metrics["occupancy_evaluations"] += 1
            c = exposure(occupancy)
            c["admissible"] = c["ok"] and all(
                v["peak"] <= peak_budget for v in c["per_member"].values()
            )
            if not c["admissible"]:
                metrics["rejected_costs"] += 1
            cost_cache[key] = c
        else:
            metrics["cost_cache_hits"] += 1
        return cost_cache[key]

    # Record: node, incoming edge, absolute time, admission flag, dose, parent, leg.
    # Admission is part of the dominance key: a WAIT is never a fresh admission.
    records, front, heap = [], {}, []
    cap = None

    def _add(node, edge, t, admission, dose, parent, leg):
        nonlocal cap
        metrics["generated_labels"] += 1
        if any(v > b for v, b in zip(dose, budgets)):
            metrics["dose_rejected_labels"] += 1
            return
        key = (node, edge, t, admission)
        old = front.get(key, [])
        if any(all(a <= b for a, b in zip(records[j][4], dose)) for j in old):
            metrics["dominated"] += 1
            return
        keep = [j for j in old if not all(a <= b for a, b in zip(dose, records[j][4]))]
        if len(keep) >= limits["frontier_width"]:
            metrics["cap_rejected_labels"] += 1
            cap = "FRONTIER_WIDTH"
            return
        if len(records) >= limits["max_labels"]:
            metrics["cap_rejected_labels"] += 1
            cap = "MAX_LABELS"
            return
        idx = len(records)
        records.append((node, edge, t, admission, dose, parent, leg))
        metrics["live_front_references"] += len(keep)+1-len(old)
        metrics["peak_front_references"] = max(metrics["peak_front_references"], metrics["live_front_references"])
        metrics["evicted_dominance_labels"] += len(old)-len(keep)
        for j in old:
            if j not in keep:
                live_pending.discard(j)
        live_pending.add(idx)
        front[key] = keep + [idx]
        heapq.heappush(heap, (t + distance[node], t, idx))
        metrics["heap_pushes"] += 1
        metrics["peak_heap_entries"] = max(metrics["peak_heap_entries"], len(heap))
        metrics["peak_live_pending_labels"] = max(metrics["peak_live_pending_labels"], len(live_pending))
        if leg is not None and leg["kind"] == "WAIT":
            metrics["wait_retained_labels"] += 1
        metrics["labels"] = len(records)
        metrics["peak_frontier"] = max(metrics["peak_frontier"], len(keep) + 1)

    def add(*args):
        mark = time.perf_counter()
        try:
            return _add(*args)
        finally:
            timing["dominance"] += time.perf_counter()-mark

    if partial is not None and position["fraction"] < 1:
        choices = [(partial, position["fraction"])]
        if (
            graph.get("mid_edge_reversal")
            and 0 < position["fraction"] < 1
            and Fraction(1 - position["fraction"])
            == Fraction(1) - Fraction(position["fraction"])
            and partial.get("reverse_edge") in edges
            and (incoming, partial["reverse_edge"]) not in forbidden
        ):
            choices.append((edges[partial["reverse_edge"]], 1 - position["fraction"]))
        for first_edge, fraction in choices:
            # Literal IEEE float multiplication + ceil is the declared residual
            # computational rule; no tolerance silently shortens traversal.
            end = (
                departure
                + math.ceil(
                    (Fraction(1) - Fraction(fraction)) * first_edge["travel_ticks"]
                )
                * dt
            )
            if end > horizon:
                continue
            leg = {
                "kind": "EDGE",
                "edge": first_edge["id"],
                "start": departure,
                "end": end,
                "from_fraction": fraction,
                "to_fraction": 1,
            }
            c = cost(
                ("PARTIAL", first_edge["id"], departure, fraction),
                lambda: geometry(first_edge, departure, end, fraction, 1),
            )
            if not c["admissible"]:
                metrics["edge_exposure_rejects"] += 1
            if c["admissible"]:
                initial_dose = tuple(
                    a + c["per_member"][m]["dose_exact"]
                    for a, m in zip(incurred, member_ids)
                )
                add(first_edge["v"], first_edge["id"], end, True, initial_dose, -1, leg)
    else:
        add(origin, incoming, departure, True, incurred, -1, None)

    def route_legs(idx):
        legs = []
        while idx >= 0:
            rec = records[idx]
            if rec[6] is not None:
                legs.append(rec[6])
            idx = rec[5]
        return list(reversed(legs))

    destinations = {}
    for d in request["destinations"]:
        destinations.setdefault(d["node"], []).append(d)
    loop_start = time.perf_counter()
    while heap:
        if cap:
            return finish("TIMEOUT", cap, solver_status="INCOMPLETE_CAP")
        if time.perf_counter() - start_clock >= limits["wall_s"]:
            return finish("TIMEOUT", "WALL_CLOCK", solver_status="INCOMPLETE_CAP")
        if metrics["expansions"] % 64 == 0:
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (
                1048576 if sys.platform == "darwin" else 1024
            )
            metrics["peak_rss_mb"] = rss
            if rss > limits.get("rss_limit_mb", 3072):
                return finish("TIMEOUT", "RSS_LIMIT", solver_status="INCOMPLETE_CAP")
        _, t, idx = heapq.heappop(heap)
        metrics["heap_pops"] += 1
        live_pending.discard(idx)
        node, incoming, _, admission, dose, parent, previous_leg = records[idx]
        if idx not in front.get((node, incoming, t, admission), []):
            metrics["stale_heap_pops"] += 1
            continue
        if admission:
            if node in destinations:
                metrics["destination_labels"] += 1
            for d in destinations.get(node, []):
                metrics["destination_contract_attempts"] += 1
                end = t + d["dwell"]
                if end > horizon or not any(
                    a <= t and end <= b for a, b in d["open_intervals"]
                ):
                    metrics["dwell_contract_rejects"] += 1
                    continue
                c = cost(
                    ("DWELL", node, t, end),
                    lambda: node_occupancy(node, t, end),
                )
                if not c["admissible"]:
                    metrics["exposure_rejects"] += 1
                    continue
                final_dose = (
                    tuple(
                        v + c["per_member"][m]["dose_exact"]
                        for v, m in zip(dose, member_ids)
                    )
                    if request["exposure_scope"] == "including_dwell"
                    else dose
                )
                if any(v > b for v, b in zip(final_dose, budgets)):
                    metrics["destination_dose_rejects"] += 1
                    continue
                legs = route_legs(idx)
                check_start = time.perf_counter()
                metrics["route_witness_checks"] += 1
                checked = check_route(graph, hazard, request, legs, node)
                timing["independent_check"] += time.perf_counter()-check_start
                if not checked["ok"]:
                    return finish(
                        "UNSUPPORTED",
                        "INDEPENDENT_CHECK_DISAGREEMENT",
                        checker=checked,
                        solver_status="CHECK_FAILURE",
                    )
                if time.perf_counter() - start_clock >= limits["wall_s"]:
                    metrics["checked_incumbents"] += 1
                    return finish(
                        "TIMEOUT",
                        "WALL_CLOCK_AFTER_CHECK",
                        solver_status="INCOMPLETE_CAP",
                        checked_incumbent={
                            "status": "CHECKED_ROUTE",
                            "legs": legs,
                            "arrival": t,
                            "destination": node,
                            "per_member": checked["per_member"],
                            "checker": checked,
                            "hazard_version": hazard["version"],
                            "proof_level": "independently checked supplied-scenario witness; optimum unresolved under cap",
                            "physical_safety_claim": False,
                        },
                    )
                return finish(
                    "CONDITIONAL_OPTIMUM" if complete else "CHECKED_ROUTE",
                    "EXACT_SEARCH_CHECKED" if complete else "PARTIAL_GLOBAL_SUPPORT",
                    legs=legs,
                    arrival=t,
                    destination=node,
                    per_member=checked["per_member"],
                    checker=checked,
                    solver_status="EXACT_OPTIMUM" if complete else "ADMISSIBLE_ONLY",
                    certificate_conditions=(
                        [
                            "supplied ensemble only",
                            "declared lattice and geometry",
                            "complete search before caps",
                            "independent route check",
                            "no physical safety claim",
                        ]
                        if complete
                        else ["independent route check", "no global optimality claim"]
                    ),
                )
        if metrics["expansions"] >= limits["max_expansions"]:
            return finish("TIMEOUT", "MAX_EXPANSIONS", solver_status="INCOMPLETE_CAP")
        metrics["expansions"] += 1
        if t >= horizon:
            continue
        for e in outgoing[node]:
            if (incoming, e["id"]) in forbidden:
                continue
            end = t + e["travel_ticks"] * dt
            if end > horizon:
                continue
            metrics["edge_candidates"] += 1
            c = cost(
                ("EDGE", e["id"], t),
                lambda: geometry(e, t, end),
            )
            if not c["admissible"]:
                metrics["edge_exposure_rejects"] += 1
            if c["admissible"]:
                ndose = tuple(
                    v + c["per_member"][m]["dose_exact"]
                    for v, m in zip(dose, member_ids)
                )
                add(
                    e["v"],
                    e["id"],
                    end,
                    True,
                    ndose,
                    idx,
                    {
                        "kind": "EDGE",
                        "edge": e["id"],
                        "start": t,
                        "end": end,
                        "from_fraction": 0,
                        "to_fraction": 1,
                    },
                )
                if cap:
                    break
        if cap:
            continue
        if nodes[node]["waitable"] and t + dt <= horizon:
            metrics["wait_candidates"] += 1
            c = cost(
                ("WAIT", node, t),
                lambda: node_occupancy(node, t, t + dt),
            )
            if not c["admissible"]:
                metrics["wait_exposure_rejects"] += 1
            if c["admissible"]:
                ndose = tuple(
                    v + c["per_member"][m]["dose_exact"]
                    for v, m in zip(dose, member_ids)
                )
                add(
                    node,
                    incoming,
                    t + dt,
                    False,
                    ndose,
                    idx,
                    {"kind": "WAIT", "node": node, "start": t, "end": t + dt},
                )
    if cap:
        return finish("TIMEOUT", cap, solver_status="INCOMPLETE_CAP")
    return finish(
        "PROVEN_INFEASIBLE" if complete else "UNSUPPORTED",
        "EXACT_FRONTIER_EXHAUSTED" if complete else "MISSING_GLOBAL_SUPPORT",
        solver_status="EXHAUSTED" if complete else "SUPPORT_INCOMPLETE",
        certificate_conditions=(
            [
                "complete supported lattice search",
                "supplied ensemble only",
                "no physical safety claim",
            ]
            if complete
            else []
        ),
    )
