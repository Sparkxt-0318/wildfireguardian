"""EXPERIMENTAL copy of routing/core.py with cross-time label dominance.

Only change versus routing.core.solve: when every member's hazard is
monotone in time (flux non-decreasing, flame never ends, support never
returns) and every destination opening interval starts at or before
departure, a label (t1, dose1) dominates (t2, dose2) at the same
(node, incoming edge, admission) when t1 <= t2 and dose1 <= dose2.
Edge durations are constant, so arriving earlier along the same suffix
meets componentwise-smaller hazard: dominance stays exact. If the
monotonicity check fails, the unmodified routing.core.solve runs.
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
    from routing.independent import check_route as independent_check

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


def _solve_monotone(graph, hazard, request, *, prepared=None):
    """Exact vector search; optional explicit prepared graph admission reuse.

    Pass a PreparedGraph as graph, or a raw graph with prepared= to require
    exact contents equality. Forecast/request admission and checker still run.
    """
    from routing import validation
    from routing.prepared import PreparedGraph

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
    solver = (
        request.get("solver", "baseline") if isinstance(request, dict) else "baseline"
    )

    def finish(status, reason, **extra):
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
        return result

    try:
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
        return finish("INVALID_INPUT", "REQUEST_SHAPE", message=str(exc))
    if solver == "activation":
        return finish("UNSUPPORTED", "ACTIVATION_NOT_PROMOTED")
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
    position, incoming = request["position"], request["incoming_edge"]
    partial = None
    if "node" in position:
        origin = position["node"]
        issue = [
            {
                "cell": node_cell(graph, nodes[origin]),
                "start": departure,
                "end": departure,
            }
        ]
    else:
        partial = edges[position["edge"]]
        origin = partial["v"]
        issue = edge_occupancies(
            partial,
            departure,
            departure,
            position["fraction"],
            position["fraction"],
            graph,
            nodes,
        )
    metrics["occupancy_evaluations"] += 1
    issue_check = evaluate_occupancy(graph, hazard, issue)
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
    # Static turn-aware disconnect is independent of the forecast/support mask.
    if time.perf_counter() - start_clock >= limits["wall_s"]:
        return finish("TIMEOUT", "WALL_CLOCK", solver_status="INCOMPLETE_CAP")
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
    distance = (
        _lower_bounds(graph, request["destinations"], dt)
        if solver == "astar"
        else {n: 0 for n in nodes}
    )
    cost_cache = {}

    def cost(key, occupancy):
        if key not in cost_cache:
            metrics["occupancy_evaluations"] += 1
            c = evaluate_occupancy(graph, hazard, occupancy)
            c["admissible"] = c["ok"] and all(
                v["peak"] <= peak_budget for v in c["per_member"].values()
            )
            cost_cache[key] = c
        return cost_cache[key]

    # Record: node, incoming edge, absolute time, admission flag, dose, parent, leg.
    # Admission is part of the dominance key: a WAIT is never a fresh admission.
    records, front, heap = [], {}, []
    cap = None

    def add(node, edge, t, admission, dose, parent, leg):
        nonlocal cap
        if any(v > b for v, b in zip(dose, budgets)):
            return
        key = (node, edge, admission)
        old = front.get(key, [])
        if any(records[j][2] <= t and all(a <= b for a, b in zip(records[j][4], dose)) for j in old):
            metrics["dominated"] += 1
            return
        keep = [j for j in old if not (t <= records[j][2] and all(a <= b for a, b in zip(dose, records[j][4])))]
        if len(keep) >= limits["frontier_width"]:
            cap = "FRONTIER_WIDTH"
            return
        if len(records) >= limits["max_labels"]:
            cap = "MAX_LABELS"
            return
        idx = len(records)
        records.append((node, edge, t, admission, dose, parent, leg))
        front[key] = keep + [idx]
        heapq.heappush(heap, (t + distance[node], t, idx))
        metrics["labels"] = len(records)
        metrics["peak_frontier"] = max(metrics["peak_frontier"], len(keep) + 1)

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
                edge_occupancies(first_edge, departure, end, fraction, 1, graph, nodes),
            )
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
        node, incoming, _, admission, dose, parent, previous_leg = records[idx]
        if idx not in front.get((node, incoming, admission), []):
            continue
        if admission:
            for d in destinations.get(node, []):
                end = t + d["dwell"]
                if end > horizon or not any(
                    a <= t and end <= b for a, b in d["open_intervals"]
                ):
                    continue
                c = cost(
                    ("DWELL", node, t, end),
                    [{"cell": node_cell(graph, nodes[node]), "start": t, "end": end}],
                )
                if not c["admissible"]:
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
                    continue
                legs = route_legs(idx)
                checked = check_route(graph, hazard, request, legs, node)
                if not checked["ok"]:
                    return finish(
                        "UNSUPPORTED",
                        "INDEPENDENT_CHECK_DISAGREEMENT",
                        checker=checked,
                        solver_status="CHECK_FAILURE",
                    )
                if time.perf_counter() - start_clock >= limits["wall_s"]:
                    return finish(
                        "TIMEOUT",
                        "WALL_CLOCK_AFTER_CHECK",
                        solver_status="INCOMPLETE_CAP",
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
                edge_occupancies(e, t, end, graph=graph, node_lookup=nodes),
            )
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
                [{"cell": node_cell(graph, nodes[node]), "start": t, "end": t + dt}],
            )
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


def hazard_is_monotone(hazard):
    for m in hazard["members"]:
        for a, b in zip(m["flux"], m["flux"][1:]):
            if any(y < x for x, y in zip(a, b)):
                return False
        for key, bad in (("flame", True), ("support", False)):
            for a, b in zip(m[key], m[key][1:]):
                if any(x == bad and y != bad for x, y in zip(a, b)):
                    return False
    return True


def solve(graph, hazard, request, *, prepared=None):
    from routing.core import solve as exact
    ok = hazard_is_monotone(hazard) and all(
        all(a <= request["departure"] for a, _ in d["open_intervals"]) for d in request["destinations"])
    if not ok:
        r = exact(graph, hazard, request, prepared=prepared)
        r.setdefault("provenance", {})["dominance"] = "TIME_KEYED_FALLBACK"
        return r
    r = _solve_monotone(graph, hazard, request, prepared=prepared)
    r.setdefault("provenance", {})["dominance"] = "CROSS_TIME_MONOTONE"
    return r
