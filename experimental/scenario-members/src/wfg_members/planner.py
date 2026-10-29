"""Planner interface and the frozen contact-sweep planner.

A planner is a callable `plan(graph, request, model, *, extra_blocked=None, wall_s=...) -> dict` that solves the exact
contact-only relaxation (flame contact under the union of the members in `model`; dose and peak relaxed) and returns

  {"status": "ROUTE" | "NO_ROUTE" | "UNRESOLVED", "raw_status", "reason", "arrival", "legs", "destination",
   "metrics", "planner", "complete"}

ROUTE: earliest relaxed arrival with a witness journey; NO_ROUTE: the complete relaxation proves that no journey avoids
contact (model-scoped), or the mission fails at issue, or the turn graph is disconnected; UNRESOLVED: anything that did
not finish (time cap, unsupported scope). `extra_blocked` maps a directed edge index to extra blocked departure-second
intervals (lazy constraints); the frozen sweep cannot take them and refuses.

`sweep_plan` runs the frozen `integration/kit/phaseB/zsweep.contact_sweep` unchanged. It needs a hazard object only for
`dt`, member identifiers and global support, so a minimal stub is passed; the witness check passed to the sweep checks
structure only (the full per-member check is done separately by `check.member_reports`).
"""
from __future__ import annotations

import copy
import time

from . import kit

ROUTE, NO_ROUTE, UNRESOLVED = "ROUTE", "NO_ROUTE", "UNRESOLVED"
_MAP = {"CONDITIONAL_OPTIMUM": ROUTE, "CHECKED_ROUTE": ROUTE, "PROVEN_INFEASIBLE": NO_ROUTE,
        "AT_ISSUE_FAILURE": NO_ROUTE, "DISCONNECTED": NO_ROUTE}


def hazard_stub(request):
    horizon = float(request["horizon"])
    return {"dt": 1, "valid_from": 0.0, "valid_until": horizon, "version": request.get("hazard_version", 1),
            "members": [{"id": i, "breakpoints": [0.0, horizon], "support": [[True]]} for i in request["incurred"]]}


def _structure_check(graph, hazard, request, legs, destination, zero_view):
    ind = kit.install()["independent"]
    try:
        ind._shape(graph, hazard, request, legs, destination)
        return {"ok": True, "per_member": {}, "status": "STRUCTURE_OK"}
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        return {"ok": False, "per_member": {}, "status": "INVALID_ROUTE", "reason": str(exc)}


def normalise(raw, planner_name, wall):
    status = _MAP.get(raw.get("status"), UNRESOLVED)
    complete = raw.get("status") in ("CONDITIONAL_OPTIMUM", "PROVEN_INFEASIBLE", "AT_ISSUE_FAILURE", "DISCONNECTED")
    return {"status": status, "raw_status": raw.get("status"), "reason": raw.get("reason"), "arrival": raw.get("arrival"),
            "legs": raw.get("legs") or [], "destination": raw.get("destination"), "metrics": raw.get("metrics", {}),
            "planner": planner_name, "complete": bool(complete), "wall_s": wall}


def sweep_plan(graph, request, model, *, extra_blocked=None, wall_s=600.0):
    if extra_blocked:
        raise NotImplementedError("the frozen sweep has no edge-level lazy constraints")
    K = kit.install()
    req = copy.deepcopy(request)
    req["solver"] = "astar_opening"
    t0 = time.perf_counter()
    raw = K["zsweep"].contact_sweep(graph, hazard_stub(req), req, model, wall_s=wall_s, core=K["core"],
                                    check_route_mode=_structure_check, zero_view=None)
    return normalise(raw, "frozen_zsweep", time.perf_counter() - t0)
