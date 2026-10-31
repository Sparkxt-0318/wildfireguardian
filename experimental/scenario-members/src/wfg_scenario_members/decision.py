"""Bounded contact proposal plus complete cell-centre journey checking.

The copied checker is explicit about its centre-surrogate scope. A rejected
candidate is never a no-route certificate. Lazy cuts are heuristics and lose
global completeness, so exhausted cuts return unresolved. Whole-road and law-v2
acceptance remain external gates.
"""
from __future__ import annotations
import bisect
import copy
from fractions import Fraction
from pathlib import Path
import sys
import time

for name in ("synthetic-truth", "sipp-routing"):
    path = str(Path(__file__).resolve().parents[3] / name / "src")
    if path not in sys.path:
        sys.path.insert(0, path)
from wfg_synthetic_truth import frozen_checker as checker
from wfg_synthetic_truth.checker import evaluate_decision
from .acceptance import accept


def member_reports(graph, hazard, request, plan, *, radiation_law="v1"):
    if radiation_law != "v1":
        evaluate_decision(plan, radiation_law=radiation_law)
    rows = []
    for member in hazard["members"]:
        view = dict(hazard, members=[member])
        result = checker.check_route(graph, view, request, plan["legs"], plan["destination"])
        mid = member["id"]; stats = result["per_member"][mid]
        codes = set(result["codes"])
        rows.append(dict(id=mid, contact="FLAME_CONTACT" in codes, peak=stats["peak"],
                         dose=stats["dose"], dose_exact=stats["dose_exact"],
                         dose_tdu=None, passed=None if "MISSING_SUPPORT" in codes else result["ok"],
                         codes=sorted(codes), scope="full journey, frozen cell-centre surrogate"))
    return rows


def decide(graph, hazard, request, model, *, planner=None, acceptance=None,
           weights=None, wall_s=30, lazy_cap=8, radiation_law="v1"):
    from wfg_sipp.frontend import sipp_plan
    planner = planner or sipp_plan
    start = time.perf_counter(); extra = {}
    acceptance = acceptance or {"rule": "all", "k": len(model.ids), "m": len(model.ids)}
    for iteration in range(lazy_cap + 1):
        remaining = wall_s - (time.perf_counter() - start)
        if remaining <= 0:
            break
        plan = planner(graph, request, model, extra_blocked=extra or None, wall_s=remaining)
        if plan["status"] != "ROUTE":
            return {"outcome": "model_no_route" if plan["status"] == "NO_ROUTE" and not extra and acceptance["rule"] == "all" else "unresolved",
                    "reason": plan["raw_status"], "arrival_s": None, "per_member": [],
                    "lazy_iterations": iteration, "binding_constraints": None}
        reports = member_reports(graph, hazard, request, plan, radiation_law=radiation_law)
        if any("ROUTE_STRUCTURE" in r["codes"] for r in reports):
            break
        verdict = accept([r["passed"] for r in reports], weights=weights, **acceptance)
        if verdict["outcome"] == "checked_route" and time.perf_counter() - start < wall_s:
            return {"outcome": "checked_route", "arrival_s": plan["arrival"], "legs": plan["legs"],
                    "destination": plan["destination"], "per_member": reports, "acceptance": verdict,
                    "lazy_iterations": iteration, "global_earliest_claim": not extra and acceptance["rule"] == "all",
                    "binding_constraints": None, "scope": "complete journey under cell-centre source law v1"}
        if verdict["outcome"] == "unresolved":
            break
        # Exact departure singleton avoids this failed witness. It can also cut
        # good alternatives, so no refusal or optimality claim survives the cut.
        edge_leg = next((leg for leg in plan["legs"] if leg["kind"] == "EDGE"), None)
        if edge_leg is None:
            break
        index = next(i for i, e in enumerate(graph["edges"]) if e["id"] == edge_leg["edge"])
        cut = (int(edge_leg["start"]), int(edge_leg["start"]))
        if cut in extra.get(index, []):
            break
        extra.setdefault(index, []).append(cut)
    return {"outcome": "unresolved", "reason": "CHECK_OR_LAZY_CAP", "arrival_s": None,
            "per_member": reports if "reports" in locals() else [],
            "binding_constraints": None, "scope": "no global refusal after heuristic cuts"}
