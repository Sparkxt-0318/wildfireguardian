"""Independent checks of observation-only, strictly held-out case selection."""
from copy import deepcopy

import pytest

from wildfire.observed_combined import CombinedObservedConfig, select_cases


def pair(cutoff, endpoint, minutes):
    return {"cutoff_utc": cutoff, "endpoint_utc": endpoint,
            "duration_minutes": minutes, "hours": minutes / 60}


def event(identifier="US-test", *, eligible=True, exposure="held_out_event", train=0,
          validation=0, test=5):
    return {"event_id": identifier, "eligible": eligible,
            "exclusion_reasons": [] if eligible else ["No paired observed perimeters acquired"],
            "m548_exposure": exposure,
            "m548_partition": {"train": train, "validation": validation, "test": test},
            "source_record_ids": [4, 5, 6],
            # Intentionally unsorted to check chronological selection.
            "consecutive_intervals": [
                pair("2024-08-03T04:11:00+00:00", "2024-08-04T04:11:00+00:00", 1440),
                pair("2024-08-02T03:06:00+00:00", "2024-08-03T04:11:00+00:00", 1505),
            ]}


def inventory(rows, declared=None):
    return {"events": rows,
            "m548_checkpoint_test_events": declared if declared is not None else [row["event_id"] for row in rows]}


@pytest.mark.parametrize("changes", [
    {"train": 1}, {"validation": 1}, {"test": 0},
    {"exposure": "training_or_validation_event"}, {"exposure": "unrepresented_event"},
])
def test_saved_training_or_validation_exposure_cannot_enter_test_pool(changes):
    bad = event("contaminated", **changes)
    cases, selected, exclusions = select_cases(inventory([event(), bad]), CombinedObservedConfig())
    assert {case["event"] for case in cases} == {"US-test"}
    assert [row["event_id"] for row in selected] == ["US-test"]
    assert any(row["event_id"] == "contaminated" and "held-out" in " ".join(row["reasons"])
               for row in exclusions)


def test_checkpoint_contract_must_independently_declare_test_event():
    # A forged inventory exposure label and positive saved test count alone
    # must not bypass the original checkpoint's held-out declarations.
    cases, selected, exclusions = select_cases(inventory([event()], declared=[]), CombinedObservedConfig())
    assert cases == []
    assert selected == []
    assert "held-out" in " ".join(exclusions[0]["reasons"])


def test_unavailable_observations_remain_excluded_even_for_test_events():
    cases, selected, exclusions = select_cases(inventory([event("KFS_06", eligible=False)]), CombinedObservedConfig())
    assert not cases and not selected
    assert "No paired observed perimeters" in " ".join(exclusions[0]["reasons"])


def test_explicit_non_test_or_unavailable_event_is_rejected():
    data = inventory([event("US-test"), event("training", train=3), event("KFS_06", eligible=False)])
    for identifier in ("training", "KFS_06"):
        with pytest.raises(ValueError, match="unavailable or not test-only"):
            select_cases(data, CombinedObservedConfig(events=(identifier,)))


def test_unknown_explicit_event_is_rejected():
    with pytest.raises(ValueError, match="Unknown requested events"):
        select_cases(inventory([event()]), CombinedObservedConfig(events=("unknown",)))


def test_actual_duration_filter_never_interpolates_six_hour_reference():
    data = inventory([event()])
    cases, selected, exclusions = select_cases(data, CombinedObservedConfig(hours=6))
    assert not cases and not selected
    assert "No observed interval matches" in exclusions[0]["reasons"][0]
    cases, selected, exclusions = select_cases(data, CombinedObservedConfig(hours=1505 / 60))
    assert len(cases) == 1
    assert cases[0]["duration_minutes"] == 1505
    assert cases[0]["endpoint"] == "2024-08-03T04:11:00+00:00"
    assert len(selected) == 1 and not exclusions


def test_first_selection_is_chronological_and_filter_applies_first():
    data = inventory([event()])
    first, _, _ = select_cases(data, CombinedObservedConfig(intervals="first"))
    assert len(first) == 1
    assert first[0]["cutoff"] == "2024-08-02T03:06:00+00:00"
    filtered, _, _ = select_cases(data, CombinedObservedConfig(intervals="first", hours=24))
    assert filtered[0]["cutoff"] == "2024-08-03T04:11:00+00:00"


def test_case_identity_independent_of_simulation_budget_and_does_not_mutate_inventory():
    data = inventory([event("B"), event("A")])
    original = deepcopy(data)
    small, _, _ = select_cases(data, CombinedObservedConfig(n_samples=256))
    large, _, _ = select_cases(data, CombinedObservedConfig(n_samples=4096))
    assert [case["case_id"] for case in small] == [case["case_id"] for case in large]
    assert [case["event"] for case in small] == ["A", "A", "B", "B"]
    assert data == original


def test_case_limit_applies_independently_to_each_event():
    cases, selected, _ = select_cases(inventory([event("A"), event("B")]),
                                      CombinedObservedConfig(max_intervals_per_event=1))
    assert len(cases) == len(selected) == 2
    assert {case["event"] for case in cases} == {"A", "B"}
    assert {case["duration_minutes"] for case in cases} == {1505}


@pytest.mark.parametrize("kwargs", [{"max_intervals_per_event": True}, {"max_intervals_per_event": 0},
                                   {"intervals": "best"}, {"events": ("A", "A")}])
def test_selection_controls_reject_ambiguous_or_outcome_optimized_requests(kwargs):
    with pytest.raises(ValueError):
        CombinedObservedConfig(**kwargs)
