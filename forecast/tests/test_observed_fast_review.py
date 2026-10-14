"""Independent checks for short-runtime selection and saved-result reporting."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json

import pytest

from wildfire.observed_combined import CombinedObservedConfig, run_combined, select_cases
from tests.test_observed_combined import workflow
from tests.test_observed_combined_review import event, inventory, pair


def intervals_event(identifier="US-test"):
    row = event(identifier)
    row["consecutive_intervals"] = [
        pair("2024-08-04T04:11:00+00:00", "2024-08-04T05:11:00+00:00", 60),
        pair("2024-08-02T03:06:00+00:00", "2024-08-03T04:11:00+00:00", 1505),
        pair("2024-08-03T04:11:00+00:00", "2024-08-03T05:11:00+00:00", 60),
        pair("2024-08-05T05:11:00+00:00", "2024-08-05T06:41:00+00:00", 90),
    ]
    return row


def test_shortest_defaults_to_one_authentic_interval_per_test_event():
    data = inventory([intervals_event("B"), intervals_event("A")])
    cases, selected, excluded = select_cases(data, CombinedObservedConfig(intervals="shortest"))
    assert len(cases) == len(selected) == 2
    assert [case["event"] for case in cases] == ["A", "B"]
    assert {case["duration_minutes"] for case in cases} == {60}
    assert {case["cutoff"] for case in cases} == {"2024-08-03T04:11:00+00:00"}
    assert not excluded


def test_shortest_per_event_limit_orders_duration_then_exact_timestamps():
    data = inventory([intervals_event()])
    cases, _, _ = select_cases(data, CombinedObservedConfig(intervals="shortest", max_intervals_per_event=3))
    assert [case["duration_minutes"] for case in cases] == [60, 60, 90]
    assert [case["cutoff"] for case in cases[:2]] == [
        "2024-08-03T04:11:00+00:00", "2024-08-04T04:11:00+00:00"]


def test_duration_cap_applies_before_chronological_first_selection():
    cases, _, _ = select_cases(inventory([intervals_event()]),
        CombinedObservedConfig(intervals="first", max_hours=1.5))
    assert len(cases) == 1
    assert cases[0]["duration_minutes"] == 60
    assert cases[0]["cutoff"] == "2024-08-03T04:11:00+00:00"


def test_duration_cap_is_inclusive_and_never_interpolates_observed_endpoint():
    data = inventory([intervals_event()])
    cases, _, _ = select_cases(data, CombinedObservedConfig(max_hours=1))
    assert len(cases) == 2
    assert all(case["hours"] == 1 and case["duration_minutes"] == 60 for case in cases)
    assert {case["endpoint"] for case in cases} == {
        "2024-08-03T05:11:00+00:00", "2024-08-04T05:11:00+00:00"}
    cases, selected, exclusions = select_cases(data, CombinedObservedConfig(max_hours=.99))
    assert cases == [] and selected == []
    assert exclusions


def test_maximum_duration_and_exact_duration_filters_apply_together():
    data = inventory([intervals_event()])
    cases, _, _ = select_cases(data, CombinedObservedConfig(hours=1.5, max_hours=1.5, intervals="shortest"))
    assert len(cases) == 1 and cases[0]["duration_minutes"] == 90
    cases, _, _ = select_cases(data, CombinedObservedConfig(hours=1.5, max_hours=1))
    assert not cases


def test_shortest_never_relaxes_saved_test_partition_requirements():
    good = intervals_event("held-out")
    contaminated = intervals_event("training")
    contaminated["m548_partition"]["train"] = 1
    contaminated["consecutive_intervals"][0]["hours"] = .01
    cases, selected, exclusions = select_cases(inventory([contaminated, good]),
        CombinedObservedConfig(intervals="shortest"))
    assert [case["event"] for case in cases] == ["held-out"]
    assert [row["event_id"] for row in selected] == ["held-out"]
    assert any(row["event_id"] == "training" for row in exclusions)
    with pytest.raises(ValueError, match="unavailable or not test-only"):
        select_cases(inventory([contaminated, good]),
            CombinedObservedConfig(intervals="shortest", events=("training",)))


def test_shortest_selection_does_not_consume_outcomes_or_saved_completion_status():
    row = intervals_event()
    row["consecutive_intervals"][0]["saved_status"] = "complete"
    row["consecutive_intervals"][0]["brier"] = 0
    row["consecutive_intervals"][2]["saved_status"] = "failed"
    row["consecutive_intervals"][2]["brier"] = 1
    data = inventory([row])
    original = deepcopy(data)
    cases, _, _ = select_cases(data, CombinedObservedConfig(intervals="shortest"))
    assert cases[0]["cutoff"] == "2024-08-03T04:11:00+00:00"
    assert data == original
    row["consecutive_intervals"].reverse()
    repeated, _, _ = select_cases(data, CombinedObservedConfig(intervals="shortest"))
    assert repeated == cases


@pytest.mark.parametrize("value", [True, False, 0, -1, float("nan"), float("inf")])
def test_invalid_maximum_duration_is_rejected(value):
    with pytest.raises(ValueError):
        CombinedObservedConfig(max_hours=value)


def snapshot_files(directory):
    return {str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in directory.rglob("*") if path.is_file()}


def prohibit_execution(monkeypatch, module):
    from wildfire import farsite_observed_build, observed_catalog_data
    invoked = []
    def forbidden(*args, **kwargs):
        invoked.append(True)
        raise AssertionError("Report-only mode attempted model execution or source extraction")
    monkeypatch.setattr(module, "run_observed_evaluation", forbidden)
    monkeypatch.setattr(observed_catalog_data, "extract_catalog", forbidden)
    monkeypatch.setattr(farsite_observed_build, "build_observed_engine", forbidden)
    return invoked


def reporting_fixture_exports(directory, monkeypatch):
    """The small runner fixture isolates scoring from native provenance.

    Full engine, reference and source authentication have independent positive
    and tampering tests in test_observed_reuse.py; this fixture tests the
    report-only execution boundary and report reconstruction.
    """
    from wildfire.observed_reuse import ReuseSource
    for path in (directory / "cases").glob("*/report.json"):
        report = json.loads(path.read_text())
        (path.parent / "protocol.json").write_text(json.dumps(report["protocol"]))
    monkeypatch.setattr(ReuseSource, "_validate_native_and_reference", lambda *args: None)


def test_report_only_without_saved_predictions_retains_selected_plan_and_runs_no_models(workflow, monkeypatch):
    module, config, model_calls = workflow
    source = replace(config, plots=False, plan_only=True)
    run_combined(source)
    before = snapshot_files(source.output_dir)
    invoked = prohibit_execution(monkeypatch, module)
    output = config.output_dir.with_name("missing-results-report")
    report = run_combined(replace(config, output_dir=output, plots=False,
        reuse_results=source.output_dir, report_only=True))
    assert report["status"] == "failed"
    assert report["planned_case_count"] == 2
    assert report["completed_case_count"] == 0
    assert len(report["failures"]) == 2
    assert not report["summary"]
    assert not invoked and not model_calls
    assert snapshot_files(source.output_dir) == before
    assert (output / "report.md").exists()


def test_report_only_recomputes_metrics_from_complete_saved_outputs_without_mutating_source(workflow, monkeypatch):
    module, config, model_calls = workflow
    source = replace(config, plots=False)
    original = run_combined(source)
    assert len(model_calls) == 2
    reporting_fixture_exports(source.output_dir, monkeypatch)
    before = snapshot_files(source.output_dir)
    invoked = prohibit_execution(monkeypatch, module)
    output = config.output_dir.with_name("saved-results-report")
    report = run_combined(replace(config, output_dir=output, plots=False,
        reuse_results=source.output_dir, report_only=True))
    assert report["status"] == "complete"
    assert report["completed_case_count"] == report["planned_case_count"] == 2
    assert report["summary"] == original["summary"]
    assert report["per_event"] == original["per_event"]
    assert len(report["monte_carlo_checks"]) == 2
    assert not invoked and len(model_calls) == 2
    assert snapshot_files(source.output_dir) == before


def test_report_only_manifest_corruption_is_excluded_without_rerunning(workflow, monkeypatch):
    module, config, model_calls = workflow
    source = replace(config, plots=False)
    run_combined(source)
    reporting_fixture_exports(source.output_dir, monkeypatch)
    manifest = next((source.output_dir / "cases").glob("*/combined_case_manifest.json"))
    manifest.write_text(json.dumps({"report.json": "tampered"}))
    before = snapshot_files(source.output_dir)
    invoked = prohibit_execution(monkeypatch, module)
    report = run_combined(replace(config, output_dir=config.output_dir.with_name("corrupt-report"),
        plots=False, reuse_results=source.output_dir, report_only=True))
    assert report["status"] == "partial"
    assert report["planned_case_count"] == 2
    assert report["completed_case_count"] == 1
    assert len(report["failures"]) == 1
    assert not invoked and len(model_calls) == 2
    assert snapshot_files(source.output_dir) == before

