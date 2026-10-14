"""Multiple saved runs pool unique cases without rerunning either model."""
from dataclasses import replace
import json
from pathlib import Path
import shutil

import numpy as np
import pytest

from tests.test_observed_combined import workflow
from tests.test_observed_fast_review import prohibit_execution, reporting_fixture_exports, snapshot_files
from wildfire.observed_combined import CombinedObservedConfig, _case_manifest, run_combined


def sources(workflow, monkeypatch):
    module, config, calls = workflow
    original = run_combined(replace(config, plots=False))
    reporting_fixture_exports(config.output_dir, monkeypatch)
    second = config.output_dir.with_name("second-source")
    shutil.copytree(config.output_dir, second)
    protocol = json.loads((second / "protocol.json").read_text())
    protocol["configuration"]["output_dir"] = str(second)
    report = json.loads((second / "report.json").read_text())
    report["protocol"] = protocol
    (second / "protocol.json").write_text(json.dumps(protocol))
    (second / "report.json").write_text(json.dumps(report))
    return module, config, calls, second, original


@pytest.mark.parametrize("missing", [None, 0, 1])
def test_merge_identical_overlaps_once_and_preserve_sources(workflow, monkeypatch, missing):
    module, config, calls, second, original = sources(workflow, monkeypatch)
    cases = original["protocol"]["cases"]
    if missing is not None:
        shutil.rmtree(config.output_dir / "cases" / cases[missing]["case_id"])
    before = [snapshot_files(path) for path in (config.output_dir, second)]
    invoked = prohibit_execution(monkeypatch, module)
    merged_config = replace(config, output_dir=config.output_dir.with_name("merged"),
        reuse_results=config.output_dir, additional_reuse_results=(second,),
        report_only=True, plots=False)
    report = run_combined(merged_config)
    assert report["status"] == "complete"
    assert report["completed_case_count"] == report["reused_case_count"] == 2
    assert report["duplicate_case_count"] == (2 if missing is None else 1)
    assert report["stored_source_count"] == 2
    assert report["newly_simulated_case_count"] == 0
    assert report["summary"] == original["summary"]
    assert report["per_event"] == original["per_event"]
    assert len(report["monte_carlo_checks"]) == 2
    assert len(report["protocol"]["additional_reuse_source_bindings"]) == 1
    assert not invoked and len(calls) == 2
    assert before == [snapshot_files(path) for path in (config.output_dir, second)]
    reversed_report = run_combined(replace(merged_config,
        output_dir=config.output_dir.with_name("reversed-merged"), reuse_results=second,
        additional_reuse_results=(config.output_dir,)))
    assert reversed_report["summary"] == report["summary"]
    assert reversed_report["duplicate_case_count"] == report["duplicate_case_count"]


def test_conflicting_duplicate_predictions_are_excluded_and_never_rerun(workflow, monkeypatch):
    module, config, calls, second, original = sources(workflow, monkeypatch)
    case = original["protocol"]["cases"][0]
    directory = second / "cases" / case["case_id"]
    with np.load(directory / "m548_prediction.npz", allow_pickle=False) as saved:
        data = {key: saved[key].copy() for key in saved.files}
    index = (0, 0, 1, 0)
    data["probability"][index] = data["burned_probability"][index] = .375
    data["mc_standard_error"][index] = np.sqrt(.375 * .625 / config.n_samples)
    data["confidence_lower"][index] = .175
    data["confidence_upper"][index] = .575
    np.savez_compressed(directory / "m548_prediction.npz", **data)
    (directory / "combined_case_manifest.json").write_text(json.dumps(_case_manifest(directory)))
    before = [snapshot_files(path) for path in (config.output_dir, second)]
    invoked = prohibit_execution(monkeypatch, module)
    report = run_combined(replace(config, output_dir=config.output_dir.with_name("conflict"),
        reuse_results=config.output_dir, additional_reuse_results=(second,),
        report_only=True, plots=False))
    assert report["status"] == "partial"
    assert report["completed_case_count"] == 1
    assert "Conflicting stored exports" in report["failures"][0]["error"]
    assert report["newly_simulated_case_count"] == 0
    assert not invoked and len(calls) == 2
    assert before == [snapshot_files(path) for path in (config.output_dir, second)]


def test_repeated_source_flags_forward_to_configuration(monkeypatch, tmp_path):
    import wildfire.observed_combined as module
    captured = []
    monkeypatch.setattr(module, "run_combined", lambda config: captured.append(config) or {"status": "planned"})
    first, second = tmp_path / "first", tmp_path / "second"
    module.main(["--reuse-results", str(first), "--reuse-results", str(second),
        "--report-only", "--output-dir", str(tmp_path / "out")])
    assert captured[0].reuse_results == first
    assert captured[0].additional_reuse_results == (second,)
    assert captured[0].report_only


def test_duplicate_or_unbound_extra_sources_are_rejected(tmp_path):
    with pytest.raises(ValueError, match="primary"):
        CombinedObservedConfig(additional_reuse_results=(tmp_path / "source",))
    with pytest.raises(ValueError, match="distinct"):
        CombinedObservedConfig(reuse_results=tmp_path / "source",
            additional_reuse_results=(tmp_path / "source",))
    with pytest.raises(ValueError, match="separate"):
        CombinedObservedConfig(reuse_results=tmp_path / "source",
            additional_reuse_results=(tmp_path / "output",), output_dir=tmp_path / "output")
