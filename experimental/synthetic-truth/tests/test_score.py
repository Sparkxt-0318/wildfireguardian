import pytest
from wfg_synthetic_truth import score_decision, summarize


def case(outcome="checked_route", **kwargs):
    decision = {"outcome": outcome, "arrival_s": 10}
    return score_decision(decision, evaluator=lambda _: dict(supported=True, passed=False, contact=True, peak=0.1, dose=2),
                          clairvoyant={"scope": "full_policy", "outcome": "checked_route", "arrival_s": 9},
                          cutoff="fixture", truth_source="holdout_trajectory", forecast_source="fixture", mission="fixture", **kwargs)


def test_truth_contact_is_false_safe_and_refusal_is_false_refusal():
    assert case()["false_safe"] is True
    assert case("model_no_route")["false_refusal"] is True
    assert case("unresolved")["outcome"] == "unresolved"
    assert summarize([case("unresolved")])["unresolved"] == 1


def test_truth_leakage_rejected():
    with pytest.raises(ValueError, match="TRUTH_LEAKAGE"):
        case(truth_id=1, planning_ids=[1, 2])


def test_unknown_truth_never_becomes_zero_risk_but_known_contact_is_a_violation():
    arguments = dict(clairvoyant={"scope": "full_policy", "outcome": "unresolved"}, cutoff="fixture",
                     truth_source="holdout_trajectory", forecast_source="fixture", mission="fixture")
    unknown = score_decision({"outcome": "checked_route", "arrival_s": 10},
        evaluator=lambda _: dict(supported=False, passed=None, contact=None), **arguments)
    assert unknown["false_safe"] is None
    contact = score_decision({"outcome": "checked_route", "arrival_s": 10},
        evaluator=lambda _: dict(supported=False, passed=False, contact=True), **arguments)
    assert contact["false_safe"] is True
