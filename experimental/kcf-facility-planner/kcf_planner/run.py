"""Plan a raw case dict end to end: parse, solve, independently replay, cross-check with wfg_sipp, gate."""
from __future__ import annotations

import time

from . import planner, replay, sipp_check
from .model import CaseError, parse_case


def invalid(raw, err):
    cid = raw.get("case_id") if isinstance(raw, dict) and isinstance(raw.get("case_id"), str) else None
    return {"schema_version": planner.RESULT_SCHEMA, "case_id": cid, "status": "INVALID_INPUT",
            "reason": "%s: %s" % (err.code, err.detail), "reason_codes": [err.code], "final_unload_s": None,
            "groups_total": None, "people_total": None, "people_with_checked_transport": 0, "trips": [],
            "missing_information": [], "assumptions": [], "tool": planner.TOOL}


def run_case(raw, *, max_labels=2_000_000, time_limit_s=None, crosscheck=True):
    try:
        case = parse_case(raw)
    except CaseError as err:
        return invalid(raw, err)
    result = planner.solve_case(case, max_labels=max_labels, time_limit_s=time_limit_s)
    t0 = time.perf_counter()
    violations = replay.replay(raw, result)
    ver = {"independent_replay": {"module": "kcf_planner.replay", "violations": violations, "ok": not violations}}
    if crosscheck:
        try:
            ver["wfg_sipp"] = sipp_check.check_result(case, result)
        except Exception as exc:  # the cross-check must never turn an error into a claim
            ver["wfg_sipp"] = {"available": False, "error": repr(exc)}
    ver["wall_s"] = round(time.perf_counter() - t0, 6)
    result["verification"] = ver
    sipp_bad = crosscheck and ver["wfg_sipp"].get("available") and not ver["wfg_sipp"].get("all_ok", True)
    if violations or sipp_bad:
        # Certifying gate: a witness that does not replay is never issued as a checked result.
        result["gated_from_status"] = result["status"]
        result["status"] = "UNRESOLVED"
        result["reason"] = "Emitted witness failed independent replay; withheld. " + result["reason"]
        result["reason_codes"] = ["WITNESS_REPLAY_FAILED"] + result.get("reason_codes", [])
        result["final_unload_s"] = None
        result["trips"] = []
        result["people_with_checked_transport"] = 0
        result["groups_with_checked_transport"] = []
        result["groups_awaiting_checked_transport"] = [g["id"] for g in raw["groups"]]
        result["people_awaiting_checked_transport"] = result.get("people_total") or 0
        result.pop("conditional_trips", None)
        result.pop("conditional_final_unload_s", None)
        result.pop("optimistic_final_unload_s", None)
        result["missing_information"] = []
    return result
