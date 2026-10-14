"""Combined test-event evaluation uses identical pooled entries and safe resume."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from wildfire.cumulative_report import _pool, case_seed
from wildfire.observed_combined import CombinedObservedConfig, case_entries, run_combined
from wildfire.observed_data import ARCHIVE_SHA256
from wildfire.observed_evaluation import M548_SHA256


def inventory():
    def event(event_id, exposure, count, pairs):
        return dict(event_id=event_id, eligible=True, exclusion_reasons=[],
            m548_exposure=exposure, m548_partition=dict(train=0 if exposure == "held_out_event" else 10,
                validation=0, test=count), source_record_ids=[1, 2, 3],
            consecutive_intervals=pairs)
    first = datetime(2024, 8, 22, 8, 2, tzinfo=timezone.utc)
    times = [first, first + timedelta(minutes=65), first + timedelta(minutes=155)]
    pairs = [dict(cutoff_utc=a.isoformat(), endpoint_utc=b.isoformat(),
                  duration_minutes=int((b-a).total_seconds()/60), hours=(b-a).total_seconds()/3600)
             for a, b in zip(times, times[1:])]
    return dict(events=[event("US_TEST", "held_out_event", 100, pairs),
                        event("US_TRAIN", "training_or_validation_event", 0, pairs)],
                m548_split_source=dict(source_files={"metadata.json": "fixture"}),
                m548_checkpoint_test_events=["US_TEST"], m548_authenticated_split_sha256={},
                archive_sha256=ARCHIVE_SHA256)


def write_case(config, position):
    output = config.output_dir
    output.mkdir()
    origin = int(datetime.fromisoformat(config.cutoff).timestamp())
    duration = int(round(config.hours * 60))
    initial = np.zeros((2, 3))
    initial[0, 0] = 1
    endpoint = initial.copy()
    endpoint[0, 1] = 1
    if position == 0:
        endpoint[0, 2] = 1
    reference = dict(burned_area=np.stack([initial, endpoint])[:, None],
        burned_area_valid=np.ones((2, 1, 2, 3), dtype=bool),
        time_utc=np.array([origin, origin + duration * 60]))
    np.savez_compressed(output / "reference.npz", **reference)
    shape = (1, 1, 2, 3)
    mixed_p = np.array([0, .25, .5, .125, 0, 0]).reshape(shape)
    valid = np.ones(shape, dtype=bool)
    if position:
        valid[0, 0, 1, 2] = False
    lower = np.maximum(mixed_p - .2, 0)
    upper = np.minimum(mixed_p + .2, 1)
    upper[0, 0, 0, 0] = 0
    common = dict(time_utc=np.array([origin]), dt_hours=np.array(config.hours))
    mixed_metadata = dict(method="recursive", n_samples=config.n_samples, seed=case_seed(config.seed, config.event, config.cutoff),
        trajectory_batch_size=config.trajectory_batch_size, uncertainty_kind="monte_carlo")
    np.savez_compressed(output / "m548_prediction.npz", **common,
        probability=mixed_p, burned_probability=np.maximum(mixed_p, initial[None, None]),
        valid=valid, rate=np.full(shape, np.nan), rate_valid=np.zeros(shape, dtype=bool),
        mc_standard_error=np.sqrt(mixed_p*(1-mixed_p)/config.n_samples),
        confidence_lower=lower, confidence_upper=upper, metadata_json=np.array(json.dumps(mixed_metadata)))
    farsite_p = np.zeros(shape)
    farsite_p[0, 0, 0, 1] = 1
    np.savez_compressed(output / "farsite_prediction.npz", **common, probability=farsite_p,
        burned_probability=np.maximum(farsite_p, initial[None, None]), valid=np.ones(shape, dtype=bool),
        metadata_json=np.array(json.dumps(dict(method="farsite_deterministic"))))
    report = dict(status="complete", protocol=dict(event=config.event, cutoff=config.cutoff,
        endpoint=config.endpoint, n_samples=config.n_samples, seed=config.seed,
        trajectory_batch_size=config.trajectory_batch_size, threshold=config.threshold),
        models=[dict(model_id="M548", display_label="M548", architecture="MixedNonnegativeKernel", path="fixture", sha256=M548_SHA256),
                dict(model_id="FARSITE", display_label="FARSITE", architecture="FARSITE", path="fixture-engine", sha256="fixture")])
    (output / "report.json").write_text(json.dumps(report))
    return report


@pytest.fixture
def workflow(tmp_path, monkeypatch):
    import wildfire.observed_combined as module
    checkpoint = tmp_path / "checkpoint.pt"
    checkpoint.write_bytes(b"fixture")
    digest = module._sha256
    monkeypatch.setattr(module, "_sha256", lambda value: M548_SHA256 if Path(value) == checkpoint else digest(value))
    monkeypatch.setattr(module, "build_inventory", lambda *args, **kwargs: inventory())
    monkeypatch.setattr(module, "_authenticate_partition", lambda *args: None)
    monkeypatch.setattr(module, "load_model", lambda *args, **kwargs: SimpleNamespace())
    import wildfire.observed_catalog_data as catalog
    calls = []
    monkeypatch.setattr(catalog, "extract_catalog", lambda archive, rows, directory: {"US_TEST": tmp_path / "observations.geojson"})
    def evaluate(config, **kwargs):
        position = len(calls)
        calls.append(config)
        return write_case(config, position)
    monkeypatch.setattr(module, "run_observed_evaluation", evaluate)
    config = CombinedObservedConfig(checkpoint=checkpoint, data_root=tmp_path / "environment",
        output_dir=tmp_path / "result", engine=tmp_path / "engine", n_samples=8, trajectory_batch_size=4,
        plots=True)
    return module, config, calls


def test_combined_runner_pools_entries_generates_plots_and_resumes(workflow):
    module, config, calls = workflow
    report = run_combined(config)
    assert report["status"] == "complete"
    assert len(calls) == 2
    assert report["completed_case_count"] == 2
    assert report["completed_events"] == ["US_TEST"]
    assert {"models.py", "prediction.py", "cumulative.py", "schema.py", "cumulative_report.py"} <= set(report["protocol"]["implementation_sha256"])
    assert any("held-out" in reason for row in report["exclusions"] for reason in row["reasons"])
    assert len(report["monte_carlo_checks"]) == 2
    assert all(row["empirical_counts_verified"] for row in report["monte_carlo_checks"])
    assert len(report["plots"]["figures"]) == 18
    assert len(list((config.output_dir / "plots").glob("*.png"))) == 18
    assert "actual survey intervals" in (config.output_dir / "plots/new_burn_reliability.svg").read_text()
    cases = report["protocol"]["cases"]
    parts = [case_entries(config.output_dir / "cases" / case["case_id"], case, config)[0][0, "shared_models", "new_burn"] for case in cases]
    pooled = _pool(parts, config.threshold)
    row = next(row for row in report["summary"] if row["model_id"] == "M548" and row["cohort"] == "shared_models" and row["quantity"] == "new_burn")
    assert row["metrics"]["sample_count"] == 9
    assert row["metrics"]["brier"] == pooled["metrics"]["brier"]
    assert row["metrics"]["average_precision"] == pooled["metrics"]["average_precision"]
    assert row["calibration"] == pooled["calibration"]
    resumed = run_combined(replace(config, progress=False))
    assert len(calls) == 2
    assert resumed["summary"] == report["summary"]
    assert "progress" not in report["protocol"]["configuration"]
    assert (config.output_dir / "availability.csv").exists()


def test_changed_configuration_cannot_resume(workflow):
    _, config, _ = workflow
    run_combined(replace(config, plan_only=True))
    with pytest.raises(ValueError, match="different settings"):
        run_combined(replace(config, plan_only=True, n_samples=16))


def test_availability_csv_retains_country_specific_fields(tmp_path):
    import csv
    from wildfire.observed_combined import _write_availability
    data = inventory()
    data["events"][1]["country"] = "KR"
    data["events"][1]["coarser_satellite_reference"] = {"product": "MCD64A1", "pixels_inspected": False}
    _write_availability(tmp_path, data, [])
    with (tmp_path / "availability.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["coarser_satellite_reference.product"] == ""
    assert rows[1]["coarser_satellite_reference.product"] == "MCD64A1"


def test_plan_only_runs_no_case_and_can_transition_to_execution(workflow):
    _, config, calls = workflow
    report = run_combined(replace(config, plan_only=True))
    assert report["status"] == "planned" and not calls
    assert len(report["protocol"]["cases"]) == 2
    assert not (config.output_dir / "cases").exists()
    executed = run_combined(config)
    assert executed["status"] == "complete"


def test_corrupted_case_manifest_cannot_enter_pooled_results(workflow):
    _, config, calls = workflow
    run_combined(config)
    manifest = next((config.output_dir / "cases").glob("*/combined_case_manifest.json"))
    manifest.write_text("{}")
    report = run_combined(config)
    assert report["status"] == "partial"
    assert len(report["failures"]) == 1
    assert report["completed_case_count"] == 1
    assert len(calls) == 2


def test_all_failed_cases_produce_failed_report_without_fabricated_scores(workflow, monkeypatch):
    module, config, _ = workflow
    def failure(*args, **kwargs):
        raise RuntimeError("native fixture failure")
    monkeypatch.setattr(module, "run_observed_evaluation", failure)
    report = run_combined(config)
    assert report["status"] == "failed"
    assert len(report["failures"]) == 2
    assert report["summary"] == []
    assert (config.output_dir / "report.md").exists()
    assert "plots" not in report


def test_success_followed_by_native_failure_retains_partial_report(workflow, monkeypatch):
    module, config, calls = workflow
    original = module.run_observed_evaluation
    def partially_failing(config, **kwargs):
        if calls:
            raise RuntimeError("second native case failed")
        return original(config, **kwargs)
    monkeypatch.setattr(module, "run_observed_evaluation", partially_failing)
    report = run_combined(config)
    assert report["status"] == "partial"
    assert report["completed_case_count"] == 1
    assert len(report["failures"]) == 1
    assert "second native case failed" in (config.output_dir / "intervals.csv").read_text()


def test_commit_failure_aborts_instead_of_excluding_already_pooled_case(workflow, monkeypatch):
    module, config, _ = workflow
    original = module._CSV.append
    def broken(self, row):
        if self.stream.name.endswith("per_cutoff.csv"):
            raise OSError("fixture disk write failed")
        return original(self, row)
    monkeypatch.setattr(module._CSV, "append", broken)
    with pytest.raises(OSError, match="disk write"):
        run_combined(config)
    report = json.loads((config.output_dir / "report.json").read_text())
    assert report["status"] == "failed"
    assert report["summary"] == []
    assert report["failures"] == []


def test_m548_fixed_or_nonempirical_export_is_rejected(workflow):
    _, config, _ = workflow
    case = dict(event="US_TEST", cutoff="2024-08-22T08:02:00+00:00", hours=65/60, duration_minutes=65)
    endpoint = (datetime.fromisoformat(case["cutoff"]) + timedelta(minutes=65)).isoformat()
    one = replace(config, output_dir=config.output_dir / "one")
    one.output_dir.parent.mkdir()
    write_case(ObservedEvaluationConfigForFixture(one, case, endpoint), 0)
    path = one.output_dir / "m548_prediction.npz"
    with np.load(path, allow_pickle=False) as saved:
        arrays = {key: saved[key].copy() for key in saved.files}
    metadata = json.loads(str(arrays["metadata_json"]))
    metadata["method"] = "fixed"
    arrays["metadata_json"] = np.array(json.dumps(metadata))
    np.savez_compressed(path, **arrays)
    with pytest.raises(ValueError, match="recursive Monte Carlo"):
        case_entries(one.output_dir, case, config)
    metadata["method"] = "recursive"
    arrays["metadata_json"] = np.array(json.dumps(metadata))
    arrays["probability"][0, 0, 0, 1] = .3
    arrays["burned_probability"][0, 0, 0, 1] = .3
    np.savez_compressed(path, **arrays)
    with pytest.raises(ValueError, match="empirical trajectory counts"):
        case_entries(one.output_dir, case, config)


@pytest.mark.parametrize("status", ["failed", "partial"])
def test_cli_exits_nonzero_for_incomplete_comparison(monkeypatch, status):
    import wildfire.observed_combined as module
    monkeypatch.setattr(module, "run_combined", lambda config: dict(status=status))
    with pytest.raises(SystemExit) as result:
        module.main([])
    assert result.value.code == 1


def test_partition_authentication_requires_original_arrays_and_saved_split(tmp_path, monkeypatch):
    import wildfire.observed_combined as module
    for name in module.FROZEN_SPLIT_SHA256:
        (tmp_path / name).write_bytes(b"fixture")
    hashes = {name: module._sha256(tmp_path / name) for name in module.FROZEN_SPLIT_SHA256}
    monkeypatch.setattr(module, "FROZEN_SPLIT_SHA256", hashes)
    monkeypatch.setattr(module, "_test_events", lambda model: {"US_TEST"})
    model = SimpleNamespace(contract=dict(cache_metadata_sha256="original"))
    source = dict(m548_split_source=dict(source_files={"metadata.json": "original"}))
    module._authenticate_partition(model, source, tmp_path)
    assert source["m548_checkpoint_test_events"] == ["US_TEST"]
    assert source["m548_authenticated_split_sha256"] == hashes
    (tmp_path / "train.npz").write_bytes(b"changed")
    with pytest.raises(ValueError, match="original M548 benchmark"):
        module._authenticate_partition(model, source, tmp_path)


def ObservedEvaluationConfigForFixture(config, case, endpoint):
    from wildfire.observed_evaluation import ObservedEvaluationConfig
    return ObservedEvaluationConfig(event=case["event"], cutoff=case["cutoff"], endpoint=endpoint,
        hours=case["hours"], output_dir=config.output_dir, n_samples=config.n_samples, seed=config.seed,
        trajectory_batch_size=config.trajectory_batch_size)
