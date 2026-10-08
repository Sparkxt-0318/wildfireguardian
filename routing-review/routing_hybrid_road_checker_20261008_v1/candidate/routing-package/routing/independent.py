"""Independent occupancy checker and bounded exhaustive timed-walk oracle.

No candidate solver imports, pruning, cost cache, or dominance implementation.
All times are mission seconds; flux integrates to kJ/m2. These checks establish
the declared finite fixture contract, never physical safety.
"""

import bisect
import heapq
import itertools
import math
from fractions import Fraction


def _number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _cell(graph, node):
    g = graph["grid"]
    x = math.floor(
        (Fraction(node["x"]) - Fraction(g["x0"])) / Fraction(g["resolution"])
    )
    y = math.floor(
        (Fraction(node["y"]) - Fraction(g["y0"])) / Fraction(g["resolution"])
    )
    if not (0 <= x < g["width"] and 0 <= y < g["height"]):
        raise ValueError("node outside grid")
    return y * g["width"] + x


def _occupancy(graph, leg, nodes, edges):
    """Closed cell occupancy spans, with dose only on positive measure."""
    if leg["kind"] == "WAIT":
        return [(_cell(graph, nodes[leg["node"]]), leg["start"], leg["end"])]
    edge = edges[leg["edge"]]
    u, v = nodes[edge["u"]], nodes[edge["v"]]
    grid = graph["grid"]
    first, last = Fraction(leg["from_fraction"]), Fraction(leg["to_fraction"])
    breaks = [first, last]
    for dimension, base, size in [("x", "x0", "width"), ("y", "y0", "height")]:
        change = Fraction(v[dimension]) - Fraction(u[dimension])
        if change:
            for j in range(1, grid[size]):
                at = (
                    Fraction(grid[base])
                    + j * Fraction(grid["resolution"])
                    - Fraction(u[dimension])
                ) / change
                if first < at < last:
                    breaks.append(at)
    breaks = sorted(set(breaks))
    spans = []
    for j, at in enumerate(breaks):
        coordinate = {
            dimension: Fraction(u[dimension])
            + at * (Fraction(v[dimension]) - Fraction(u[dimension]))
            for dimension in ("x", "y")
        }
        now = Fraction(leg["start"]) + (
            Fraction(leg["end"]) - Fraction(leg["start"])
        ) * (at - first) / (last - first)
        spans.append((_cell(graph, coordinate), now, now))
        if j + 1 < len(breaks):
            right = breaks[j + 1]
            middle = (at + right) / 2
            interior = {
                dimension: Fraction(u[dimension])
                + middle * (Fraction(v[dimension]) - Fraction(u[dimension]))
                for dimension in ("x", "y")
            }
            until = Fraction(leg["start"]) + (
                Fraction(leg["end"]) - Fraction(leg["start"])
            ) * (right - first) / (last - first)
            spans.append((_cell(graph, interior), now, until))
    return spans


def _position_spans(graph, pos, now, nodes, edges):
    if "node" in pos:
        return [(_cell(graph, nodes[pos["node"]]), now, now)]
    e = edges[pos["edge"]]
    f = pos["fraction"]
    u, v = nodes[e["u"]], nodes[e["v"]]
    point = {
        dim: Fraction(u[dim]) + Fraction(f) * (Fraction(v[dim]) - Fraction(u[dim]))
        for dim in ("x", "y")
    }
    spans = [
        (s["cell"], now, now) for s in e["segments"] if s["start"] <= f <= s["end"]
    ]
    spans.append((_cell(graph, point), now, now))
    return spans


def _json_stats(stats):
    out = {}
    for k, v in stats.items():
        try:
            displayed = float(v["dose"])
        except OverflowError:
            displayed = None
        out[k] = {"dose": displayed, "dose_exact": str(v["dose"]), "peak": v["peak"]}
    return out


def _sample(member, cell, t, hazard):
    if t < hazard["valid_from"] or t > hazard["valid_until"]:
        return None
    k = bisect.bisect_right(member["breakpoints"], t) - 1
    k = min(k, len(member["flux"]) - 1)
    if k < 0 or not member["support"][k][cell]:
        return None
    return member["flux"][k][cell], member["flame"][k][cell]


def _charge(spans, hazard, stats, include_dose, codes):
    for member in hazard["members"]:
        out = stats[member["id"]]
        for cell, a, b in spans:
            cuts = (
                [a]
                + [t for t in member["breakpoints"] if a < t < b]
                + ([b] if b != a else [])
            )
            for t in cuts:
                sample = _sample(member, cell, t, hazard)
                if sample is None:
                    codes.add("MISSING_SUPPORT")
                else:
                    flux, flame = sample
                    out["peak"] = max(out["peak"], flux)
                    if flame:
                        codes.add("FLAME_CONTACT")
            if include_dose:
                for left, right in zip(cuts, cuts[1:]):
                    sample = _sample(member, cell, left, hazard)
                    if sample is not None:
                        out["dose"] += Fraction(sample[0]) * (
                            Fraction(right) - Fraction(left)
                        )


def _shape(graph, hazard, request, legs, destination):
    """Reject malformed route structure without relying on candidate logic."""
    nodes = {n["id"]: n for n in graph["nodes"]}
    edges = {e["id"]: e for e in graph["edges"]}
    destinations = {d["node"]: d for d in request["destinations"]}
    if destination not in destinations or not isinstance(legs, list):
        raise ValueError("invalid destination or legs")
    dt = hazard["dt"]
    pos = request["position"].copy()
    incoming = request["incoming_edge"]
    if pos.get("fraction") == 1 and "edge" in pos:
        incoming = pos["edge"]
        pos = {"node": edges[pos["edge"]]["v"]}
    now = request["departure"]
    admission = "node" in pos
    for index, leg in enumerate(legs):
        if not isinstance(leg, dict) or leg.get("kind") not in ("EDGE", "WAIT"):
            raise ValueError("invalid leg kind")
        if not _number(leg.get("start")) or not _number(leg.get("end")):
            raise ValueError("nonfinite leg times")
        if leg["start"] != now or leg["end"] <= now:
            raise ValueError("noncontiguous or nonpositive leg")
        if ((Fraction(leg["end"]) - Fraction(now)) / Fraction(dt)).denominator != 1:
            raise ValueError("off lattice leg")
        if leg["end"] > request["horizon"]:
            raise ValueError("horizon exceeded")
        if leg["kind"] == "WAIT":
            if (
                "node" not in pos
                or leg.get("node") != pos["node"]
                or not nodes[pos["node"]]["waitable"]
            ):
                raise ValueError("illegal wait")
            admission = False
        else:
            if leg.get("edge") not in edges:
                raise ValueError("unknown directed edge")
            edge = edges[leg["edge"]]
            f, q = leg.get("from_fraction"), leg.get("to_fraction")
            if not _number(f) or not _number(q) or not (0 <= f < q <= 1) or q != 1:
                raise ValueError("invalid edge fractions")
            if "edge" in pos:
                original = edges[pos["edge"]]
                forward = edge["id"] == pos["edge"] and f == pos["fraction"]
                reverse = (
                    graph.get("mid_edge_reversal") is True
                    and original.get("reverse_edge") == edge["id"]
                    and edge.get("reverse_edge") == original["id"]
                    and Fraction(f) == Fraction(1) - Fraction(pos["fraction"])
                )
                if index != 0 or not (forward or reverse):
                    raise ValueError("partial position mismatch or forbidden reversal")
                if request["incoming_edge"] != original["id"] or (
                    reverse and [original["id"], edge["id"]] in graph["forbidden_turns"]
                ):
                    raise ValueError("partial incoming edge or forbidden reversal turn")
            else:
                if edge["u"] != pos["node"] or f != 0:
                    raise ValueError("edge discontinuity")
                if (
                    incoming is not None
                    and [incoming, edge["id"]] in graph["forbidden_turns"]
                ):
                    raise ValueError("forbidden turn")
            ticks = math.ceil(edge["travel_ticks"] * (Fraction(q) - Fraction(f)))
            if Fraction(leg["end"]) - Fraction(now) != ticks * Fraction(dt):
                raise ValueError("edge travel duration mismatch")
            pos = {"node": edge["v"]}
            incoming = edge["id"]
            admission = True
        now = leg["end"]
    if "node" not in pos or pos["node"] != destination or not admission:
        raise ValueError("route does not end at destination admission")
    dest = destinations[destination]
    finish = now + dest["dwell"]
    if finish > request["horizon"] or not any(
        a <= now and finish <= b for a, b in dest["open_intervals"]
    ):
        raise ValueError("destination dwell horizon or opening violation")
    return nodes, edges, now, finish


def check_route(graph, hazard, request, legs, destination):
    """Check continuity, turns, occupancy, all member budgets, and dwell."""
    stats = {
        m["id"]: {"dose": Fraction(request["incurred"][m["id"]]), "peak": 0.0}
        for m in hazard["members"]
    }
    codes = set()
    try:
        nodes, edges, arrival, finish = _shape(
            graph, hazard, request, legs, destination
        )
        pos = request["position"]
        issue = _position_spans(graph, pos, request["departure"], nodes, edges)
        _charge(issue, hazard, stats, False, codes)
        issue_failure = bool(codes & {"FLAME_CONTACT"}) or any(
            v["peak"] > request["budgets"]["peak"]
            or v["dose"] > Fraction(request["budgets"]["dose"][k])
            for k, v in stats.items()
        )
        for leg in legs:
            _charge(_occupancy(graph, leg, nodes, edges), hazard, stats, True, codes)
        _charge(
            [(_cell(graph, nodes[destination]), arrival, finish)],
            hazard,
            stats,
            request["exposure_scope"] == "including_dwell",
            codes,
        )
        if any(v["peak"] > request["budgets"]["peak"] for v in stats.values()):
            codes.add("PEAK_BUDGET")
        if any(
            v["dose"] > Fraction(request["budgets"]["dose"][k])
            for k, v in stats.items()
        ):
            codes.add("DOSE_BUDGET")
        status = (
            "AT_ISSUE_FAILURE"
            if issue_failure
            else (
                "UNSUPPORTED"
                if "MISSING_SUPPORT" in codes
                else ("CHECKED_ROUTE" if not codes else "REJECTED_ROUTE")
            )
        )
        return {
            "ok": not codes,
            "status": status,
            "codes": sorted(codes),
            "per_member": _json_stats(stats),
            "arrival": arrival,
        }
    except (KeyError, TypeError, ValueError, IndexError, OverflowError) as error:
        return {
            "ok": False,
            "status": "INVALID_ROUTE",
            "codes": ["ROUTE_STRUCTURE"],
            "reason": str(error),
            "per_member": _json_stats(stats),
            "arrival": None,
        }


def _global_support(hazard, request):
    return (
        request["departure"] >= hazard["valid_from"]
        and request["horizon"] <= hazard["valid_until"]
        and all(all(all(row) for row in m["support"]) for m in hazard["members"])
    )


def exhaustive(graph, hazard, request, max_walks=200000):
    """Enumerate every timed walk in arrival order; no dominance or merging.

    The cap limits popped walks, never proves infeasibility. A completed route
    is optimal only under complete declared support. Input schema validation
    remains the caller's responsibility; returned routes are independently checked.
    """
    nodes = {n["id"]: n for n in graph["nodes"]}
    edges = {e["id"]: e for e in graph["edges"]}
    destinations = {d["node"]: d for d in request["destinations"]}
    serial = itertools.count()
    start_pos = request["position"].copy()
    start_incoming = request["incoming_edge"]
    if start_pos.get("fraction") == 1 and "edge" in start_pos:
        start_incoming = start_pos["edge"]
        start_pos = {"node": edges[start_pos["edge"]]["v"]}
    queue = [(request["departure"], next(serial), start_pos, start_incoming, True, [])]
    popped = 0
    full = _global_support(hazard, request)
    issue_stats = {
        m["id"]: {"dose": Fraction(request["incurred"][m["id"]]), "peak": 0.0}
        for m in hazard["members"]
    }
    issue_codes = set()
    pos = request["position"]
    spans = _position_spans(graph, pos, request["departure"], nodes, edges)
    _charge(spans, hazard, issue_stats, False, issue_codes)
    if "FLAME_CONTACT" in issue_codes or any(
        s["peak"] > request["budgets"]["peak"]
        or s["dose"] > Fraction(request["budgets"]["dose"][k])
        for k, s in issue_stats.items()
    ):
        return {
            "status": "AT_ISSUE_FAILURE",
            "arrival": None,
            "legs": [],
            "walks": 0,
            "reason": "ISSUE_OCCUPANCY_OR_INCURRED_BUDGET",
        }
    while queue:
        if popped >= max_walks:
            return {
                "status": "UNRESOLVED",
                "arrival": None,
                "legs": [],
                "walks": popped,
                "reason": "REFERENCE_WALK_CAP",
            }
        now, _, pos, incoming, admission, legs = heapq.heappop(queue)
        popped += 1
        if "node" in pos and admission and pos["node"] in destinations:
            checked = check_route(graph, hazard, request, legs, pos["node"])
            if checked["ok"]:
                return {
                    **checked,
                    "status": "CONDITIONAL_OPTIMUM" if full else "CHECKED_ROUTE",
                    "legs": legs,
                    "destination": pos["node"],
                    "walks": popped,
                }
        actions = []
        if "edge" in pos:
            edge = edges[pos["edge"]]
            actions.append((edge, pos["fraction"]))
            reverse_id = edge.get("reverse_edge")
            if (
                graph.get("mid_edge_reversal") is True
                and reverse_id in edges
                and 0 < pos["fraction"] < 1
                and Fraction(1 - pos["fraction"])
                == Fraction(1) - Fraction(pos["fraction"])
                and [edge["id"], reverse_id] not in graph["forbidden_turns"]
            ):
                actions.append((edges[reverse_id], 1 - pos["fraction"]))
        else:
            for edge in graph["edges"]:
                if edge["u"] == pos["node"] and (
                    incoming is None
                    or [incoming, edge["id"]] not in graph["forbidden_turns"]
                ):
                    actions.append((edge, 0))
            end = now + hazard["dt"]
            if nodes[pos["node"]]["waitable"] and end <= request["horizon"]:
                wait = {"kind": "WAIT", "node": pos["node"], "start": now, "end": end}
                heapq.heappush(
                    queue,
                    (end, next(serial), pos.copy(), incoming, False, legs + [wait]),
                )
        for edge, f in actions:
            end = (
                now
                + math.ceil(edge["travel_ticks"] * (Fraction(1) - Fraction(f)))
                * hazard["dt"]
            )
            if end <= request["horizon"]:
                leg = {
                    "kind": "EDGE",
                    "edge": edge["id"],
                    "start": now,
                    "end": end,
                    "from_fraction": f,
                    "to_fraction": 1,
                }
                heapq.heappush(
                    queue,
                    (
                        end,
                        next(serial),
                        {"node": edge["v"]},
                        edge["id"],
                        True,
                        legs + [leg],
                    ),
                )
    return {
        "status": "PROVEN_INFEASIBLE" if full else "UNSUPPORTED",
        "arrival": None,
        "legs": [],
        "walks": popped,
        "reason": "COMPLETE_TIMED_WALK_ENUMERATION" if full else "INCOMPLETE_SUPPORT",
    }
