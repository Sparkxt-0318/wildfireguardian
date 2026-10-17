"""Verdict mapping (mirrors integration/kit/runner/native_tally.py) and dispatch aggregation; pure unit tests."""
import pytest

from api import dispatch as D
from api import verdict as V

OK_RC = {"on_time_complete_publication": True, "exit_code": 0, "cleanup_state": "CLEAN", "deadline_termination_requested": False,
         "memory_guard_triggered": False, "time_v": {"timed_command_RSS_bytes": 300 * 2 ** 20}}
ROUTE_RES = {"primary_status": "CHECKED_ROUTE", "whole_road_check": {"status": "CERTIFIED_ADMISSIBLE"}, "authority_final": True}


def dec(status, ok=None, reason=None):
    return {"authoritative_status": status, "is_successful_journey": status in V.SUCCESS if ok is None else ok, "unresolved_reason": reason}


@pytest.mark.parametrize("status", V.SUCCESS)
def test_success_statuses_are_checked_routes(status):
    assert V.classify(dec(status), OK_RC, ROUTE_RES) == ("checked_route", None, None)


def test_refusal_is_model_no_route_and_centre_only_is_not():
    assert V.classify(dec("FULL_MODEL_REFUSAL_PROVEN"), OK_RC, {"primary_status": "PROVEN_INFEASIBLE", "authority_final": True})[0] == "model_no_route"
    assert V.classify(dec("CENTRE_MODEL_REFUSAL_ONLY"), OK_RC, {})[:2] == ("unresolved", "OTHER")


@pytest.mark.parametrize("reason,code", [("SEARCH_TIMEOUT", "TIMEOUT"), ("WHOLE_ROAD_CHECK_INTERRUPTED", "CHECK_NOT_FINISHED"),
                                         ("WHOLE_ROAD_CHECK_NOT_STARTED", "CHECK_NOT_FINISHED"), ("CANDIDATE_REJECTED_BY_WHOLE_ROAD", "CHECK_FAILED"),
                                         ("STALE_OR_IDENTITY_MISMATCH", "CHECK_FAILED"), ("CONTRADICTORY_EVIDENCE", "CHECK_FAILED")])
def test_unresolved_reasons(reason, code):
    assert V.classify(dec("UNRESOLVED", reason=reason), OK_RC, {"authority_final": True}) == ("unresolved", code, reason)


def test_state_cap_and_memory_and_deadline():
    capped = {"authority_final": True, "rda_stages": [{"stage": "LO", "reason": "MAX_LABELS"}]}
    assert V.classify(dec("UNRESOLVED", reason="SEARCH_TIMEOUT"), OK_RC, capped)[1] == "STATE_CAP"
    assert V.classify(dec("CHECKED_JOURNEY_FEASIBLE"), dict(OK_RC, memory_guard_triggered=True), ROUTE_RES)[1] == "MEMORY_CAP"
    late = dict(OK_RC, on_time_complete_publication=False, deadline_termination_requested=True, termination_requested=True, exit_code=2)
    assert V.classify(dec("UNRESOLVED", reason="LATE_RESULT"), late, {"authority_final": False}) == ("unresolved", "TIMEOUT", "LATE_RESULT")
    crashed = dict(OK_RC, exit_code=1, on_time_complete_publication=False)
    assert V.classify(dec("UNRESOLVED", reason="LATE_RESULT"), crashed, {})[1] == "WORKER_ERROR"
    assert V.classify(dec("CHECKED_JOURNEY_FEASIBLE"), dict(OK_RC, cleanup_state="SURVIVORS"), ROUTE_RES)[1] == "CLEANUP_UNCONFIRMED"


def test_never_checked_without_certified_whole_road_or_centre_feasibility():
    assert V.classify(dec("CHECKED_JOURNEY_FEASIBLE"), OK_RC, dict(ROUTE_RES, whole_road_check={"status": "UNRESOLVED"}))[0] == "unresolved"
    road_only = dict(ROUTE_RES, primary_status="ROAD_CERTIFIED_CENTRE_INFEASIBLE_ROUTE")
    assert V.classify(dec("CHECKED_JOURNEY_FEASIBLE"), OK_RC, road_only) == ("unresolved", "CHECK_FAILED", "ROAD_ONLY_ROUTE")


@pytest.mark.parametrize("status,code", [("INVALID_INPUT", "INPUT_REJECTED"), ("UNSUPPORTED_INPUT", "INPUT_REJECTED"),
                                         ("AT_ISSUE_FAILURE", "AT_ISSUE_FAILURE"), ("DISCONNECTED", "DISCONNECTED")])
def test_pass_through_statuses_are_unresolved(status, code):
    assert V.classify(dec(status), OK_RC, {"authority_final": True})[:2] == ("unresolved", code)


def test_independent_check_applies_the_scorer_rules():
    good = {"status": "OK", "contradictions": [], "classification": {"trajectory": "VALID", "whole_road_contact": "CLEAR", "centre_model": "FEASIBLE"},
            "optimality_or_refusal": {"verdict": "INDEPENDENTLY_CERTIFIED_OPTIMAL"}}
    full = dec("CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN")
    assert V.classify(full, OK_RC, ROUTE_RES, good)[0] == "checked_route"
    assert V.classify(full, OK_RC, ROUTE_RES, dict(good, contradictions=["X"]))[0] == "unresolved"
    disputed = dict(good, optimality_or_refusal={"verdict": "NOT_OPTIMAL_COUNTEREXAMPLE"})
    assert V.classify(full, OK_RC, ROUTE_RES, disputed)[2] == "INDEPENDENT_DISPUTE_UNCLEARED"
    refusal = dec("FULL_MODEL_REFUSAL_PROVEN")
    res = {"primary_status": "PROVEN_INFEASIBLE", "authority_final": True}
    assert V.classify(refusal, OK_RC, res, dict(good, optimality_or_refusal={"verdict": "INDEPENDENTLY_CERTIFIED_REFUSAL"}))[0] == "model_no_route"
    assert V.classify(refusal, OK_RC, res, dict(good, optimality_or_refusal={"verdict": "FEASIBLE_ROUTE_EXISTS"}))[0] == "unresolved"
    assert V.classify(refusal, OK_RC, res, dict(good, optimality_or_refusal={"verdict": "NOT_INDEPENDENTLY_CERTIFIED"}))[2] == "UNSUPPORTED_REFUSAL_CLAIM"


def att(d, off, v, arr=None):
    return {"destination_id": d, "depart_offset_s": off, "verdict": v, "reason_code": None if v != "unresolved" else "TIMEOUT",
            "arrival_s": arr, "lower_bound_L_s": None, "compute_s": 1.0, "route_check_job_id": None}


def test_best_verdict_rules():
    assert D.best_verdict([att("a", 0, "unresolved"), att("b", 0, "checked_route", 100)]) == "checked_route"
    assert D.best_verdict([att("a", 0, "model_no_route"), att("b", 0, "model_no_route")]) == "model_no_route"
    # one unresolved attempt means a refusal cannot be concluded for the origin
    assert D.best_verdict([att("a", 0, "model_no_route"), att("b", 0, "unresolved")]) == "unresolved"
    assert D.best_verdict([]) == "unresolved"


def test_latest_checked_offset_and_urgency_order():
    order = {"a": 0, "b": 1}
    p1 = D.origin_plan("late", None, [att("a", 0, "checked_route", 500), att("a", 600, "checked_route", 1200), att("b", 600, "checked_route", 900)], order)
    p2 = D.origin_plan("early", None, [att("a", 0, "checked_route", 400), att("a", 600, "model_no_route")], order)
    p3 = D.origin_plan("refused", None, [att("a", 0, "model_no_route"), att("a", 600, "model_no_route")], order)
    p4 = D.origin_plan("unknown", None, [att("a", 0, "unresolved"), att("a", 600, "model_no_route")], order)
    assert p1["latest_checked_depart_offset_s"] == 600 and p1["best"]["destination_id"] == "b"   # earliest arrival at the latest safe offset
    assert p2["latest_checked_depart_offset_s"] == 0
    ranked = D.sort_by_urgency([p4, p3, p1, p2], {"late": 0, "early": 1, "refused": 2, "unknown": 3})
    assert [p["origin_id"] for p in ranked] == ["early", "late", "refused", "unknown"]
    assert [p["urgency_rank"] for p in ranked] == [1, 2, 3, 4]
    s = D.summary(ranked, [a for p in ranked for a in p["attempts"]])
    assert (s["checked_route"], s["model_no_route"], s["unresolved"]) == (2, 1, 1)
