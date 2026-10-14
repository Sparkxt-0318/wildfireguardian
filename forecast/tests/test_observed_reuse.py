"""Saved predictions can be reused only with authenticated scientific inputs."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from tests.test_observed_combined import inventory, write_case
from wildfire.observed_combined import CombinedObservedConfig, _case_manifest, select_cases
from wildfire.observed_data import ARCHIVE_SHA256, DOI
from wildfire.observed_evaluation import M548_SHA256
from wildfire.observed_reuse import (HISTORICAL_PREDICTION_SIGNATURE, MissingStoredCase,
    authenticate_reuse)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n")


def snapshot(directory):
    return {str(path.relative_to(directory)): sha(path) for path in directory.rglob("*") if path.is_file()}


def resign_case(path):
    save(path / "combined_case_manifest.json", _case_manifest(path))


@pytest.fixture
def stored(tmp_path):
    """Create authenticated fixture exports without invoking either model."""
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "output"
    checkpoint = tmp_path / "checkpoint.pt"
    checkpoint.write_bytes(b"checkpoint fixture authenticated by the calling target protocol")
    engine = tmp_path / "native/src/TestFARSITE"
    engine.parent.mkdir(parents=True)
    engine.write_bytes(b"native engine fixture")
    probe = engine.parent.parent / "observed_clock_probe"
    probe.write_bytes(b"native probe fixture")
    engine_manifest = dict(executable=str(engine), executable_sha256=sha(engine),
        native_clock_probe=str(probe), native_clock_probe_sha256=sha(probe),
        clock_loading_changes=True, spread_physics_changes=False)
    save(engine.parent.parent / "observed_build_manifest.json", engine_manifest)
    root = tmp_path / "data"
    region = root / "regions/US_TEST"
    region.mkdir(parents=True)
    grid = region / "grid.json"
    grid.write_text("{}")
    observations = tmp_path / "catalog/US_TEST/US_TEST.geojson"
    observations.parent.mkdir(parents=True)
    observations.write_text("{}")
    config = SimpleNamespace(reuse_results=source, output_dir=output, checkpoint=checkpoint,
        engine=engine, data_root=root, archive=tmp_path / "source.zip",
        prepared_directory=tmp_path / "prepared", observations_dir=tmp_path / "catalog",
        n_samples=8, seed=0, trajectory_batch_size=4, threads=4, threshold=.5,
        timestep_minutes=1, timeout_seconds=1800)
    cases, _, _ = select_cases(inventory(), CombinedObservedConfig())
    case = cases[0]
    signature = dict(HISTORICAL_PREDICTION_SIGNATURE)
    signature["observed_combined.py"] = "orchestration-only"
    protocol = dict(schema_version=1, configuration={name: str(value) if isinstance(value, Path) else value
        for name, value in vars(config).items() if name != "reuse_results"},
        checkpoint_sha256=M548_SHA256, archive_sha256=ARCHIVE_SHA256,
        test_only=True, split="test_only", partition_binding={"fixture": "original saved split"},
        checkpoint_test_events=["US_TEST"], authenticated_split_sha256={"test.npz": "fixture"},
        cases=[case], implementation_sha256=signature,
        input_sha256={str(grid.relative_to(root)): sha(grid)})
    case_dir = source / "cases" / case["case_id"]
    case_dir.parent.mkdir()
    one = SimpleNamespace(**{**vars(config), "output_dir": case_dir, "event": case["event"],
        "cutoff": case["cutoff"], "endpoint": case["endpoint"], "hours": case["hours"]})
    report = write_case(one, 0)
    report["models"][0]["path"] = str(checkpoint)
    report["models"][1].update(path=str(engine), sha256=sha(engine))
    report["protocol"].update(method="matched_observed_perimeter", full_rectangle=True,
        boundary="zero", environment_policy="repeated_current", duration_minutes=case["duration_minutes"],
        hours=case["hours"], implementation_sha256={name: signature[name] for name in
            ("observed_evaluation.py", "rollout.py", "data.py", "farsite_inputs.py", "metrics.py")})
    report["engine"] = engine_manifest
    report["farsite_input_manifest"] = dict(event_id=case["event"], cutoff_utc=case["cutoff"],
        endpoint_utc=case["endpoint"], hours=case["hours"], timestep_minutes=1,
        source_files=[], grid_source=dict(path=str(grid), sha256=sha(grid)),
        clock=dict(start_local=case["cutoff"], end_local=case["endpoint"]))
    start, end = datetime.fromisoformat(case["cutoff"]), datetime.fromisoformat(case["endpoint"])
    report["native_clock_verification"] = dict(start_hhmm=start.hour*100+start.minute,
        end_hhmm=end.hour*100+end.minute, duration_minutes=case["duration_minutes"])
    report["observations"] = dict(path=str(observations), sha256=sha(observations),
        reconstructed_fire_labels_used=False, same_rectangle_for_both_models=True,
        publisher_provenance=dict(archive_sha256=ARCHIVE_SHA256, dataset_doi=DOI,
            incident_component=case["event"], source_record_ids=case["source_record_ids"],
            geojson_sha256=sha(observations)))
    save(case_dir / "report.json", report)
    save(case_dir / "protocol.json", report["protocol"])
    resign_case(case_dir)
    save(source / "protocol.json", protocol)
    save(source / "report.json", dict(status="complete", protocol=protocol, models=report["models"]))
    target = deepcopy(protocol)
    target["configuration"]["output_dir"] = str(output)
    return SimpleNamespace(config=config, target=target, source=source, case=case,
        case_dir=case_dir, engine=engine, observations=observations, cases=cases)


def test_no_reuse_source_means_no_authentication_io():
    assert authenticate_reuse(SimpleNamespace(reuse_results=None), {}) is None


def test_complete_exports_are_copied_and_source_bytes_preserved(stored):
    before = snapshot(stored.source)
    source = authenticate_reuse(stored.config, stored.target)
    destination = stored.config.output_dir / "cases" / stored.case["case_id"]
    proof = source.copy_case(stored.case, destination)
    assert proof["models_reexecuted"] is False
    assert proof["prediction_origin"] == "current"
    assert source.binding["source_protocol_sha256"] == sha(stored.source / "protocol.json")
    assert (destination / "report.json").read_bytes() == (stored.case_dir / "report.json").read_bytes()
    assert (destination / "reuse_provenance.json").exists()
    assert snapshot(stored.source) == before
    assert not any(path.is_symlink() for path in destination.iterdir())


def test_exact_pinned_historical_signature_survives_current_cache_implementation(stored):
    stored.target["implementation_sha256"]["rollout.py"] = "optimized current rollout"
    stored.target["implementation_sha256"]["observed_evaluation.py"] = "optimized current observed runner"
    stored.target["implementation_sha256"]["rollout_cache.py"] = "current environment cache"
    source = authenticate_reuse(stored.config, stored.target)
    assert source.implementation_kind == "historical"
    proof = source.copy_case(stored.case, stored.config.output_dir / "case")
    assert proof["prediction_origin"] == "historical"
    assert "Historical stored predictions" in proof["interpretation"]


def mutate_root(stored, mutation):
    protocol = json.loads((stored.source / "protocol.json").read_text())
    mutation(protocol)
    report = json.loads((stored.source / "report.json").read_text())
    report["protocol"] = protocol
    save(stored.source / "protocol.json", protocol)
    save(stored.source / "report.json", report)


@pytest.mark.parametrize("module", ["rollout.py", "models.py", "data.py", "farsite_inputs.py"])
def test_arbitrary_inference_drift_cannot_be_authorized_by_editing_stored_protocol(stored, module):
    mutate_root(stored, lambda protocol: protocol["implementation_sha256"].update({module: "untrusted modified code"}))
    with pytest.raises(ValueError, match="neither the current nor pinned historical"):
        authenticate_reuse(stored.config, stored.target)


@pytest.mark.parametrize("field,value", [("n_samples", 16), ("seed", 1),
    ("trajectory_batch_size", 8), ("threads", 2), ("threshold", .6),
    ("timestep_minutes", 2), ("timeout_seconds", 1200)])
def test_changed_simulation_controls_are_rejected(stored, field, value):
    stored.target["configuration"][field] = value
    with pytest.raises(ValueError, match=field):
        authenticate_reuse(stored.config, stored.target)


@pytest.mark.parametrize("field", ["checkpoint_sha256", "archive_sha256", "partition_binding",
    "checkpoint_test_events", "authenticated_split_sha256"])
def test_changed_checkpoint_archive_or_partition_binding_is_rejected(stored, field):
    stored.target[field] = "different authenticated source"
    with pytest.raises(ValueError, match=field):
        authenticate_reuse(stored.config, stored.target)


def test_root_report_protocol_mismatch_is_rejected(stored):
    report = json.loads((stored.source / "report.json").read_text())
    report["protocol"]["n_samples"] = 16
    save(stored.source / "report.json", report)
    with pytest.raises(ValueError, match="root report and protocol disagree"):
        authenticate_reuse(stored.config, stored.target)


def test_changed_selected_covariate_hash_is_rejected(stored):
    stored.target["input_sha256"]["regions/US_TEST/grid.json"] = "changed geometry"
    with pytest.raises(ValueError, match="covariate binding"):
        authenticate_reuse(stored.config, stored.target)


def test_exact_case_source_records_cannot_be_changed(stored):
    stored.target["cases"][0]["source_record_ids"] = [999]
    with pytest.raises(ValueError, match="component source records"):
        authenticate_reuse(stored.config, stored.target)


def test_case_outside_source_plan_is_missing_and_never_borrowed(stored):
    stored.target["cases"].append(stored.cases[1])
    source = authenticate_reuse(stored.config, stored.target)
    with pytest.raises(MissingStoredCase, match="outside this stored source's authenticated plan"):
        source.copy_case(stored.cases[1], stored.config.output_dir / "missing")
    assert not (stored.config.output_dir / "missing").exists()


@pytest.mark.parametrize("state", ["running", "failed", "interrupted"])
def test_incomplete_source_results_are_missing_without_modification(stored, state):
    report = json.loads((stored.case_dir / "report.json").read_text())
    report["status"] = state
    save(stored.case_dir / "report.json", report)
    before = snapshot(stored.source)
    source = authenticate_reuse(stored.config, stored.target)
    with pytest.raises(MissingStoredCase) as raised:
        source.copy_case(stored.case, stored.config.output_dir / "case")
    assert raised.value.status == state
    assert snapshot(stored.source) == before


def test_manifest_corruption_is_rejected_instead_of_treated_as_missing(stored):
    save(stored.case_dir / "combined_case_manifest.json", {})
    source = authenticate_reuse(stored.config, stored.target)
    with pytest.raises(ValueError, match="checksum manifest"):
        source.copy_case(stored.case, stored.config.output_dir / "case")


def change_case_report(stored, change):
    report = json.loads((stored.case_dir / "report.json").read_text())
    change(report)
    save(stored.case_dir / "report.json", report)
    save(stored.case_dir / "protocol.json", report["protocol"])
    resign_case(stored.case_dir)


def test_resigned_wrong_native_clock_is_rejected(stored):
    change_case_report(stored, lambda report: report["native_clock_verification"].update(duration_minutes=1))
    source = authenticate_reuse(stored.config, stored.target)
    with pytest.raises(ValueError, match="actual native clock"):
        source.copy_case(stored.case, stored.config.output_dir / "case")


def test_changed_native_engine_binary_is_rejected(stored):
    stored.engine.write_bytes(b"different engine")
    source = authenticate_reuse(stored.config, stored.target)
    with pytest.raises(ValueError, match="engine identity"):
        source.copy_case(stored.case, stored.config.output_dir / "case")


def test_changed_observed_geojson_is_rejected(stored):
    stored.observations.write_text('{"modified": true}')
    source = authenticate_reuse(stored.config, stored.target)
    with pytest.raises(ValueError, match="observed-reference provenance"):
        source.copy_case(stored.case, stored.config.output_dir / "case")


def test_resigned_nonempirical_monte_carlo_probabilities_are_rejected(stored):
    path = stored.case_dir / "m548_prediction.npz"
    with np.load(path, allow_pickle=False) as payload:
        arrays = {key: payload[key].copy() for key in payload.files}
    arrays["probability"][0, 0, 0, 1] = .3
    arrays["burned_probability"][0, 0, 0, 1] = .3
    np.savez_compressed(path, **arrays)
    resign_case(stored.case_dir)
    source = authenticate_reuse(stored.config, stored.target)
    with pytest.raises(ValueError, match="empirical trajectory counts"):
        source.copy_case(stored.case, stored.config.output_dir / "case")


def test_symlinked_export_is_rejected(stored, tmp_path):
    path = stored.case_dir / "reference.npz"
    moved = tmp_path / "elsewhere.npz"
    path.rename(moved)
    path.symlink_to(moved)
    source = authenticate_reuse(stored.config, stored.target)
    with pytest.raises(ValueError, match="symlinked export"):
        source.copy_case(stored.case, stored.config.output_dir / "case")


def test_source_root_changes_after_authentication_are_rejected(stored):
    source = authenticate_reuse(stored.config, stored.target)
    report_path = stored.source / "report.json"
    report_path.write_text(report_path.read_text() + " ")
    with pytest.raises(ValueError, match="changed after authentication"):
        source.copy_case(stored.case, stored.config.output_dir / "case")


def test_failed_copy_removes_its_partial_destination_and_preserves_source(stored, monkeypatch):
    import wildfire.observed_reuse as module
    before = snapshot(stored.source)
    original = module.shutil.copyfile
    count = 0
    def failure(source, target):
        nonlocal count
        count += 1
        if count == 3:
            raise OSError("fixture copy interrupted")
        return original(source, target)
    monkeypatch.setattr(module.shutil, "copyfile", failure)
    source = authenticate_reuse(stored.config, stored.target)
    destination = stored.config.output_dir / "case"
    with pytest.raises(OSError, match="copy interrupted"):
        source.copy_case(stored.case, destination)
    assert not destination.exists()
    assert snapshot(stored.source) == before


def test_source_and_destination_paths_must_not_overlap(stored):
    stored.config.output_dir = stored.source / "new-reports"
    with pytest.raises(ValueError, match="must not overlap"):
        authenticate_reuse(stored.config, stored.target)

