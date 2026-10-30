from types import SimpleNamespace
from wfg_scenario_members.decision import decide


def test_union_no_route_cannot_be_a_chance_policy_refusal():
    def no_route(*args, **kwargs):
        return {"status": "NO_ROUTE", "raw_status": "EXHAUSTED"}
    result = decide({}, {}, {}, SimpleNamespace(ids=["a", "b"]), planner=no_route,
                    acceptance={"rule": "k_of_m", "k": 1, "m": 2})
    assert result["outcome"] == "unresolved"


def test_complete_union_exhaustion_can_be_a_scoped_all_policy_refusal():
    def no_route(*args, **kwargs):
        return {"status": "NO_ROUTE", "raw_status": "EXHAUSTED"}
    result = decide({}, {}, {}, SimpleNamespace(ids=["a", "b"]), planner=no_route)
    assert result["outcome"] == "model_no_route"
