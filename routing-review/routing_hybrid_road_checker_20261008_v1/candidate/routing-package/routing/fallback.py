"""Checked return along recorded directed travel, never a shortest-path substitute."""

from copy import deepcopy
import math
import time
from fractions import Fraction


def _finite_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, ValueError):
        return False


def _failure(status, reason, hazard):
    return {
        "status": status,
        "reason": reason,
        "legs": [],
        "hazard_version": hazard.get("version") if isinstance(hazard, dict) else None,
        "solver_status": "NOT_SEARCHED",
    }


def checked_return(
    graph, hazard, request, history, endpoint, dwell=0, *, prepared=None
):
    """Reverse only the traversed history and independently check actual occupancy.

    A partial final history entry must end at the actual current fraction. The
    graph must explicitly permit mid-edge reversal; every reverse directed edge
    and turn remains subject to the ordinary checker. Failure of this particular
    return is not an infeasibility certificate for the routing problem.
    """
    started = time.perf_counter()

    def capped():
        limits = request.get("limits", {}) if isinstance(request, dict) else {}
        value = limits.get("wall_s")
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and time.perf_counter() - started >= value
        )

    from .validation import (
        validate_graph,
        validate_hazard,
        validate_request,
        ValidationError,
    )
    from .independent import check_route

    if not isinstance(request, dict):
        return _failure("INVALID_INPUT", "REQUEST_SHAPE", hazard)
    try:
        from .prepared import PreparedGraph

        reused = prepared is not None or type(graph) is PreparedGraph
        if prepared is not None:
            if type(prepared) is not PreparedGraph:
                raise ValidationError(
                    "PREPARED_GRAPH_TYPE", "prepared must be a PreparedGraph"
                )
            if not prepared.matches(graph):
                raise ValidationError(
                    "PREPARED_GRAPH_MISMATCH", "explicit graph replacement required"
                )
            graph = prepared.snapshot()
        elif type(graph) is PreparedGraph:
            graph = graph.snapshot()
        else:
            graph = validate_graph(graph)
        hazard = validate_hazard(
            graph, hazard, request.get("as_of"), _graph_validated=reused
        )
        req = deepcopy(request)
        endpoint_spec = (
            endpoint if isinstance(endpoint, dict) else req.get("return_endpoint")
        )
        if isinstance(endpoint, dict):
            endpoint = endpoint["node"]
        declared = next(
            (d for d in req.get("destinations", []) if d.get("node") == endpoint), None
        )
        if declared is None and endpoint_spec is not None:
            if (
                not isinstance(endpoint_spec, dict)
                or endpoint_spec.get("node") != endpoint
            ):
                return _failure(
                    "INVALID_INPUT", "RETURN_ENDPOINT_DECLARATION_MISMATCH", hazard
                )
            declared = endpoint_spec
        if declared is None and dwell > 0:
            return _failure(
                "UNSUPPORTED", "RETURN_DWELL_REQUIRES_ENDPOINT_CONDITIONS", hazard
            )
        req["destinations"] = [
            {
                "node": endpoint,
                "dwell": max(dwell, declared["dwell"]) if declared else dwell,
                "open_intervals": (
                    deepcopy(declared["open_intervals"])
                    if declared
                    else [[req["departure"], req["horizon"]]]
                ),
            }
        ]
        req = validate_request(graph, hazard, req, _validated_inputs=reused)
    except (ValidationError, KeyError, TypeError, ValueError, AttributeError) as exc:
        return _failure("INVALID_INPUT", getattr(exc, "code", str(exc)), hazard)
    if capped():
        return _failure("TIMEOUT", "RETURN_CHECK_WALL_CLOCK", hazard)
    edges = {e["id"]: e for e in graph["edges"]}
    nodes = {n["id"] for n in graph["nodes"]}
    if endpoint not in nodes or not isinstance(history, list):
        return _failure("INVALID_INPUT", "INVALID_RETURN_HISTORY_OR_ENDPOINT", hazard)
    records = []
    previous = None
    try:
        for i, entry in enumerate(history):
            if capped():
                return _failure("TIMEOUT", "RETURN_CHECK_WALL_CLOCK", hazard)
            e = edges[entry["edge"]]
            a, b = entry["from_fraction"], entry["to_fraction"]
            if (
                isinstance(a, bool)
                or isinstance(b, bool)
                or not _finite_number(a)
                or not _finite_number(b)
                or a != 0
                or not 0 < b <= 1
            ):
                raise ValueError("INVALID_HISTORY_FRACTION")
            if previous is not None and previous["v"] != e["u"]:
                raise ValueError("DISCONTINUOUS_HISTORY")
            if b < 1 and i != len(history) - 1:
                raise ValueError("PARTIAL_HISTORY_NOT_LAST")
            records.append((e, b))
            previous = e
        pos = req["position"]
        if "edge" in pos:
            if (
                not records
                or records[-1][0]["id"] != pos["edge"]
                or records[-1][1] != pos["fraction"]
            ):
                raise ValueError("CURRENT_PARTIAL_HISTORY_MISMATCH")
            if not graph.get("mid_edge_reversal", False):
                return _failure(
                    "UNSUPPORTED", "MID_EDGE_REVERSAL_NOT_PERMITTED", hazard
                )
        elif records:
            if records[-1][1] != 1 or records[-1][0]["v"] != pos["node"]:
                raise ValueError("CURRENT_NODE_HISTORY_MISMATCH")
            if req["incoming_edge"] != records[-1][0]["id"]:
                raise ValueError("INCOMING_HISTORY_MISMATCH")
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _failure("INVALID_INPUT", str(exc), hazard)
    legs = []
    t = req["departure"]
    reached = pos.get("node") == endpoint
    if not reached:
        for e, b in reversed(records):
            if capped():
                return _failure("TIMEOUT", "RETURN_CHECK_WALL_CLOCK", hazard)
            reverse_id = e.get("reverse_edge")
            reverse = edges.get(reverse_id)
            if reverse is None or reverse["u"] != e["v"] or reverse["v"] != e["u"]:
                return _failure(
                    "UNSUPPORTED", "DIRECTED_REVERSE_EDGE_UNAVAILABLE", hazard
                )
            start_fraction = 1 - b
            if Fraction(start_fraction) != Fraction(1) - Fraction(b):
                return _failure(
                    "UNSUPPORTED", "REVERSE_FRACTION_NOT_EXACTLY_REPRESENTABLE", hazard
                )
            duration = (
                math.ceil(
                    (Fraction(1) - Fraction(start_fraction)) * reverse["travel_ticks"]
                )
                * hazard["dt"]
            )
            legs.append(
                {
                    "kind": "EDGE",
                    "edge": reverse_id,
                    "start": t,
                    "end": t + duration,
                    "from_fraction": start_fraction,
                    "to_fraction": 1,
                }
            )
            t += duration
            if reverse["v"] == endpoint:
                reached = True
                break
    if not reached:
        return _failure("UNSUPPORTED", "ENDPOINT_NOT_ON_RECORDED_RETURN", hazard)
    checked = check_route(graph, hazard, req, legs, endpoint)
    if capped():
        return _failure("TIMEOUT", "RETURN_CHECK_WALL_CLOCK", hazard)
    if not checked.get("ok"):
        status = checked.get("status", "UNSUPPORTED")
        if status not in {"UNSUPPORTED", "INVALID_INPUT", "AT_ISSUE_FAILURE"}:
            status = "UNSUPPORTED"
        result = _failure(status, "RECORDED_RETURN_REFUSED", hazard)
        result["codes"] = checked.get("codes", [])
        result["check"] = checked
        return result
    return {
        "status": "CHECKED_ROUTE",
        "reason": "RECORDED_RETURN_INDEPENDENTLY_CHECKED",
        "legs": legs,
        "arrival": checked["arrival"],
        "destination": endpoint,
        "per_member": checked["per_member"],
        "hazard_version": hazard["version"],
        "solver_status": "RETURN_ONLY_CHECKED",
        "provenance": deepcopy(hazard["provenance"]),
        "endpoint_availability": (
            "DECLARED_ENDPOINT_WINDOWS"
            if declared
            else "POINT_SUPPORT_CHECKED_NO_VERIFIED_SHELTER_OR_OPENING_REQUIREMENT"
        ),
        "certificate_conditions": [
            "Recorded directed path only",
            "Actual departure and incurred exposure",
            "Declared member set, grid support, and endpoint dwell",
        ],
    }
