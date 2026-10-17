"""Map the kit's authoritative journey decision (journey_decision_v2_1) onto exactly three API verdicts.

The mapping is strict and mirrors the frozen campaign scorer (integration/kit/runner/native_tally.py):
receipt-level failures (memory guard, worker failure, no publication) override everything; only a successful
authoritative journey whose mandatory whole-road check is CERTIFIED_ADMISSIBLE becomes ``checked_route`` (a route the
runtime centre model rejects -- ROAD_CERTIFIED_CENTRE_INFEASIBLE_ROUTE -- is a road-only route and stays unresolved);
only FULL_MODEL_REFUSAL_PROVEN becomes ``model_no_route``. Everything else is ``unresolved`` with a reason code.
When the offline independent checker was requested, its result is applied exactly as the scorer applies it
(contradictions, invalid trajectory, uncleared disputes or a non-certified refusal downgrade to unresolved).
"""
from __future__ import annotations

CHECKED = "checked_route"
NO_ROUTE = "model_no_route"
UNRESOLVED = "unresolved"
SUCCESS = ("CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN", "CHECKED_JOURNEY_CENTRE_OPTIMUM", "CHECKED_JOURNEY_FEASIBLE")
STATE_CAP_REASONS = ("MAX_LABELS", "MAX_EXPANSIONS", "FRONTIER")
DISPUTE_OPT = ("NOT_OPTIMAL_COUNTEREXAMPLE",)
DISPUTE_REF = ("REFUSAL_CONTRADICTED", "FEASIBLE_ROUTE_EXISTS")

CHECK_FAILED_REASONS = ("CANDIDATE_REJECTED_BY_WHOLE_ROAD", "WHOLE_ROAD_CHECK_UNRESOLVED", "WHOLE_ROAD_CHECK_NOT_BOUND_TO_ROUTE",
                        "STALE_OR_IDENTITY_MISMATCH", "REFUSAL_IDENTITY_UNVERIFIED", "CONTRADICTORY_EVIDENCE")
CHECK_NOT_FINISHED_REASONS = ("WHOLE_ROAD_CHECK_INTERRUPTED", "WHOLE_ROAD_CHECK_NOT_STARTED")
PASS_THROUGH = {"INVALID_INPUT": "INPUT_REJECTED", "UNSUPPORTED_INPUT": "INPUT_REJECTED",
                "AT_ISSUE_FAILURE": "AT_ISSUE_FAILURE", "DISCONNECTED": "DISCONNECTED"}


def _stage_reasons(result: dict) -> list:
    out = []
    for s in result.get("rda_stages") or []:
        if isinstance(s, dict):
            out += [str(s.get("reason") or ""), str(s.get("status") or "")]
    r = result.get("result") or {}
    out += [str(r.get("reason") or ""), str(r.get("solver_status") or ""), str(result.get("primary_reason") or "")]
    return out


def _cap_reason(result: dict):
    text = " ".join(_stage_reasons(result))
    if "RSS_LIMIT" in text:
        return "MEMORY_CAP"
    if any(k in text for k in STATE_CAP_REASONS):
        return "STATE_CAP"
    return None


def classify(decision: dict, receipt: dict, result: dict, independent: dict | None = None,
             guard_mib: float = 3072.0) -> tuple[str, str | None, str | None]:
    """Return (verdict, reason_code, raw_reason)."""
    rc = receipt or {}
    res = result or {}
    a = decision.get("authoritative_status")
    raw = decision.get("unresolved_reason")
    tv = rc.get("time_v") or {}
    rss = tv.get("timed_command_RSS_bytes")
    over = rss is not None and rss / 2 ** 20 > guard_mib
    # ---- receipt-level classes override every decision row (native_tally.py) --------------------------------------
    if over or rc.get("memory_guard_triggered"):
        return UNRESOLVED, "MEMORY_CAP", "MEMORY_GUARD_EXCEEDED"
    failed = (not rc.get("deadline_termination_requested")) and rc.get("exit_code") not in (0, None)
    if failed:
        return UNRESOLVED, "WORKER_ERROR", "WORKER_FAILED"
    if rc.get("cleanup_state") not in (None, "CLEAN"):
        return UNRESOLVED, "CLEANUP_UNCONFIRMED", "CLEANUP_%s" % rc.get("cleanup_state")
    if raw in ("LATE", "LATE_RESULT") and not rc.get("termination_requested", rc.get("deadline_termination_requested")) \
            and not res.get("authority_final"):
        return UNRESOLVED, "WORKER_ERROR", "NO_PUBLICATION"
    if rc.get("deadline_termination_requested") and a not in SUCCESS + ("FULL_MODEL_REFUSAL_PROVEN",):
        return UNRESOLVED, _cap_reason(res) or "TIMEOUT", raw or "DEADLINE_STOP"
    if not rc.get("on_time_complete_publication") and (a in SUCCESS or a == "FULL_MODEL_REFUSAL_PROVEN"):
        return UNRESOLVED, "TIMEOUT", "LATE_RESULT"     # defensive: the decision already requires on-time publication
    ind = independent or None
    ci = (ind or {}).get("classification") or {}
    opt = (ind or {}).get("optimality_or_refusal") or {}
    contra = list((ind or {}).get("contradictions") or [])
    # ---- successful journey ---------------------------------------------------------------------------------------
    if a in SUCCESS and decision.get("is_successful_journey"):
        wr = (res.get("whole_road_check") or {}).get("status")
        if wr != "CERTIFIED_ADMISSIBLE":
            return UNRESOLVED, "CHECK_FAILED", "WHOLE_ROAD_NOT_CERTIFIED"
        if res.get("primary_status") == "ROAD_CERTIFIED_CENTRE_INFEASIBLE_ROUTE":
            return UNRESOLVED, "CHECK_FAILED", "ROAD_ONLY_ROUTE"
        if ind is not None:
            if ind.get("status") in ("TIMEOUT", "FAILED", "INVALID_OUTPUT"):
                return CHECKED, None, None              # corroboration unavailable; runtime authority stands (noted by caller)
            if contra:
                return UNRESOLVED, "CHECK_FAILED", "INDEPENDENT_CONTRADICTION"
            if ci.get("trajectory") != "VALID" or ci.get("whole_road_contact") != "CLEAR":
                return UNRESOLVED, "CHECK_FAILED", "INDEPENDENT_CONTRADICTION"
            if a == "CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN" and opt.get("verdict") in DISPUTE_OPT:
                return UNRESOLVED, "CHECK_FAILED", "INDEPENDENT_DISPUTE_UNCLEARED"
            if ci.get("centre_model") != "FEASIBLE":
                return UNRESOLVED, "CHECK_FAILED", "ROAD_ONLY_ROUTE"
        return CHECKED, None, None
    # ---- scoped refusal ---------------------------------------------------------------------------------------------
    if a == "FULL_MODEL_REFUSAL_PROVEN":
        if ind is not None and ind.get("status") not in ("TIMEOUT", "FAILED", "INVALID_OUTPUT"):
            v = opt.get("verdict")
            if contra or v in DISPUTE_REF:
                return UNRESOLVED, "CHECK_FAILED", "INDEPENDENT_CONTRADICTION"
            if v != "INDEPENDENTLY_CERTIFIED_REFUSAL":
                return UNRESOLVED, "CHECK_FAILED", "UNSUPPORTED_REFUSAL_CLAIM"
        return NO_ROUTE, None, None
    if a == "CENTRE_MODEL_REFUSAL_ONLY":
        return UNRESOLVED, "OTHER", "CENTRE_REFUSAL_ONLY"
    if a in PASS_THROUGH:
        return UNRESOLVED, PASS_THROUGH[a], a
    # ---- UNRESOLVED -------------------------------------------------------------------------------------------------
    if raw == "LATE_RESULT":
        return UNRESOLVED, _cap_reason(res) or "TIMEOUT", raw
    if raw == "SEARCH_TIMEOUT":
        return UNRESOLVED, _cap_reason(res) or "TIMEOUT", raw
    if raw in CHECK_NOT_FINISHED_REASONS:
        return UNRESOLVED, "CHECK_NOT_FINISHED", raw
    if raw in CHECK_FAILED_REASONS:
        return UNRESOLVED, "CHECK_FAILED", raw
    if raw == "NO_SOLVER_WITNESS":
        cap = _cap_reason(res)
        if cap:
            return UNRESOLVED, cap, raw
        if res.get("primary_status") == "TIMEOUT":
            return UNRESOLVED, "TIMEOUT", raw
        return UNRESOLVED, "OTHER", raw
    return UNRESOLVED, "OTHER", raw or a
