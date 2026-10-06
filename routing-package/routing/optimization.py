"""One bounded optional optimization: static legal-suffix edge pruning.

No labels are merged. An edge that has no directed turn-legal continuation to
any destination is removed. Hazards, times, resources and openings are ignored
in this backward relaxation; they cannot create a missing graph continuation.
This is generic reachability preprocessing, not a novel research method.
"""

from copy import deepcopy
from collections import deque
import time
from .validation import validate_request, ValidationError


def solve(graph, hazard, request):
    from .core import solve as baseline
    from .independent import check_route

    start = time.perf_counter()
    try:
        q = validate_request(graph, hazard, request)
    except ValidationError:
        return baseline(graph, hazard, request)
    if q.get("solver", "baseline") == "activation":
        return baseline(graph, hazard, q)
    destinations = {d["node"] for d in q["destinations"]}
    edges = {e["id"]: e for e in graph["edges"]}
    into = {n["id"]: [] for n in graph["nodes"]}
    forbidden = {tuple(x) for x in graph["forbidden_turns"]}
    for e in edges.values():
        into[e["v"]].append(e["id"])
    reachable = {e["id"] for e in edges.values() if e["v"] in destinations}
    queue = deque(reachable)
    while queue:
        e = edges[queue.popleft()]
        for incoming in into[e["u"]]:
            if incoming not in reachable and (incoming, e["id"]) not in forbidden:
                reachable.add(incoming)
                queue.append(incoming)
        if time.perf_counter() - start >= q["limits"]["wall_s"]:
            return {
                "status": "TIMEOUT",
                "reason": "SUFFIX_PREPARATION_WALL_CLOCK",
                "arrival": None,
                "legs": [],
                "metrics": {"wall_s": time.perf_counter() - start},
            }
    # Keep the occupied/incoming edge for validation/context even if it lacks a
    # suffix. All remaining moves from such a state are still turn constrained.
    context = q["position"].get("edge", q["incoming_edge"])
    keep = reachable | ({context} if context else set())
    g = deepcopy(graph)
    g["edges"] = [deepcopy(e) for e in graph["edges"] if e["id"] in keep]
    for e in g["edges"]:
        if e.get("reverse_edge") not in keep:
            e.pop("reverse_edge", None)
    g["forbidden_turns"] = [
        t for t in graph["forbidden_turns"] if t[0] in keep and t[1] in keep
    ]
    spent = time.perf_counter() - start
    q["limits"]["wall_s"] = max(0, q["limits"]["wall_s"] - spent)
    result = baseline(g, hazard, q)
    # Check returned witnesses against the full original graph, never only the
    # reduced topology. Preparation and this extra check are charged.
    if result["status"] in ["CONDITIONAL_OPTIMUM", "CHECKED_ROUTE"]:
        checked = check_route(
            graph, hazard, request, result["legs"], result["destination"]
        )
        if not checked["ok"]:
            result.update(
                status="UNSUPPORTED", reason="ORIGINAL_GRAPH_RECHECK_DISAGREEMENT"
            )
        result["checker"] = checked
    result.setdefault("metrics", {}).update(
        wall_s=time.perf_counter() - start,
        suffix_preparation_s=spent,
        edges_before=len(edges),
        edges_after=len(keep),
    )
    result.setdefault("provenance", {})[
        "optional_optimization"
    ] = "STATIC_LEGAL_SUFFIX_PRUNING_NOT_DEFAULT"
    if result["metrics"]["wall_s"] >= request["limits"]["wall_s"]:
        result.update(
            status="TIMEOUT",
            reason="OPTIMIZATION_END_TO_END_WALL_CLOCK",
            arrival=None,
            legs=[],
        )
    return result
