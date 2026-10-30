"""Synthetic report outputs, never study data, checkpoints, or MC executions."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

import numpy as np
from PIL import Image
import pytest


def load_report():
    path = Path(__file__).resolve().parents[2] / "research/forecast-v2/scripts/report.py"
    spec = importlib.util.spec_from_file_location("synthetic_report_readiness", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1) + "\n")


def build_fixture(report, root, *, outcome="empty", primary="base", zero_growth=False):
    """Generate actual tiny receipt-bound arrays plus fixed synthetic phase metadata."""
    # Reuse the independently source-audited synthetic training population.
    # Plot controls must not bypass the shared development membership freeze.
    if __package__:
        from .test_blind_forecast_protocol import freezer as freezer_fixture, freeze_inputs as fit_fixture
    else:
        from test_blind_forecast_protocol import freezer as freezer_fixture, freeze_inputs as fit_fixture
    with pytest.MonkeyPatch.context() as metadata_patch:
        freezer = freezer_fixture.__wrapped__()
        root, run, selection_path, _, selection = fit_fixture.__wrapped__(freezer, Path(root), metadata_patch)
    out, inputs = root / "research/forecast-v2", root / "synthetic-heldout-inputs"
    for phase in report.F.current_phase_identity()["phases"]:
        if phase["stage"] != "fold":
            continue
        result_path = run / phase["result"]
        result = json.loads(result_path.read_text())
        for values in result["validation_per_fire"].values():
            values["brier"] = .05 if phase["variant"] == primary else .1
        write(result_path, result)
        job = f"a{5 if phase['variant'] == 'burnout_spotting' else 3:02d}_{phase['job_suffix']}"
        receipt_path = out / f"executions/{job}.json"
        receipt = json.loads(receipt_path.read_text()); receipt["output_sha256"] = report.sha256(result_path)
        write(receipt_path, receipt)
    original = json.loads((root / selection["fit_coverage"]["path"]).read_text())
    proof = report.F.audit_coverage(root, original["input_root"], original["cache_root"], run, original["cache_audit"]["path"])
    proof_path = out / "FIT_COVERAGE_REPORT_FIXTURE.json"
    report.F.write_new(proof_path, proof)
    development_brier, development_phases = report.F.development_selection(root, run)
    selection.update(development_brier=development_brier, development_phases=development_phases, selected_variant=primary,
        fit_coverage=report.F.identity(root, proof_path), development_coverage_sha256=report.F.object_sha(proof["development"]))
    write(selection_path, selection)
    sources = report.F.producer_sources(root)
    events = ["SYNTHETIC_A", "SYNTHETIC_B"]
    initial = np.zeros((10, 10), dtype=bool); initial[0, 0] = True
    endpoint = initial.copy()
    if not zero_growth: endpoint[:, 1::3] = True
    mask = ~initial
    rows, cols = np.nonzero(mask)
    y = endpoint[mask].astype(np.int8)
    manifest = dict(events={})
    for fire in events:
        path = inputs / f"perimeters/{fire}/states.npz"; path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, states=np.stack([initial, endpoint]), times=np.array(["2024-01-01T00:00:00Z", "2024-01-01T12:00:00Z"]))
        manifest["events"][fire] = dict(states_sha256=report.sha256(path))
    write(inputs / "perimeters/PERIMETER_MANIFEST.json", manifest)
    write(inputs / "EXTRACTION_MANIFEST.json", dict(synthetic=True))
    frozen = dict(current_phase=report.F.current_phase_identity(), spotting_source_contract=report.F.spotting_source_contract(root, sources),
                  trajectories=1024, seed=0, extraction_manifest_sha256=report.sha256(inputs / "EXTRACTION_MANIFEST.json"),
                  perimeter_manifest_sha256=report.sha256(inputs / "perimeters/PERIMETER_MANIFEST.json"))
    heldout = run / "heldout"
    write(heldout / "FROZEN_ASSESSMENT.json", frozen)
    frozen_sha = report.sha256(heldout / "FROZEN_ASSESSMENT.json")
    names = {*(v + "_seed0" for v in report.F.VARIANTS), "persistence", "dilation_best", "logistic", "c651_mc", "c651_mf", *(f"dilation_{n}h" for n in (1, 2, 4, 8))}
    predictions = {name: np.where(y, .9, 0.) for name in names}
    predictions["persistence"] = np.zeros(len(y))
    predictions["dilation_best"] = np.where(y, .4, .05)
    predictions["c651_mc"] = np.where(y, .7, .01)
    cases, failures, files = [], [], {}
    for i, fire in enumerate(events):
        scored = outcome == "complete" or outcome == "partial" and i == 0
        record = dict(case_id=f"synthetic_case_{i}", case=dict(event=fire, cutoff="2024-01-01T00:00:00Z"),
                      assessment_sha256=frozen_sha, status="SCORED" if scored else "UNAVAILABLE", scored_cells=len(y) if scored else 0)
        if scored:
            path = heldout / (fire + ".npz")
            np.savez_compressed(path, row=rows, col=cols, y=y, interval=np.zeros(len(y), dtype=np.int64),
                t1=np.array(["2024-01-01T00:00:00Z"]), hours=np.array([12.]), **{"p_"+name: p for name, p in predictions.items()})
            files[path.name] = report.sha256(path)
        else:
            record["reason"] = "No common supported cells" if i == 0 else "Source support unavailable after the declared horizon"
            failures.append(record)
        cases.append(record)
    assessment = dict(receipt_version="wfg.forecast-assessment/2", status="COMPLETE" if outcome == "complete" else "HOLD",
                      frozen_sha256=frozen_sha, per_fire_files=files, events=events, cases=cases, failed_or_unavailable=failures)
    write(heldout / "ASSESSMENT.json", assessment)
    write(run / "report_inputs.json", dict(perimeters=str(inputs / "perimeters"), data_root=str(inputs / "environment"), n_samples=1024,
          seed=0, frozen_assessment_sha256=frozen_sha, data_manifest_sha256=frozen["extraction_manifest_sha256"]))
    return SimpleNamespace(root=root, run=run, out=out, inputs=inputs, assessment=assessment, primary=primary, predictions=predictions)


@pytest.fixture
def report():
    return load_report()


def execute(report, fixture, monkeypatch):
    monkeypatch.setattr(report, "REPO", fixture.root)
    monkeypatch.setattr(sys, "argv", ["report.py", "--run", str(fixture.run), "--out", str(fixture.out), "--label", "SYNTHETIC FIXTURE"])
    report.main()
    return json.loads((fixture.out / "RESULTS.json").read_text())


@pytest.mark.parametrize("outcome", ["empty", "partial", "complete"])
def test_authenticated_reports_keep_absence_subset_and_complete_metrics_distinct(report, tmp_path, monkeypatch, outcome):
    fixture = build_fixture(report, tmp_path, outcome=outcome)
    result = execute(report, fixture, monkeypatch)
    heldout, gate = result["heldout"], result["retrospective_superiority_gate"]
    assert heldout["unscored_outcomes"] == fixture.assessment["failed_or_unavailable"]
    assert heldout["declared_fires"] == fixture.assessment["events"]
    assert heldout["assessment_status"] == fixture.assessment["status"]
    if outcome == "empty":
        assert heldout["entries"] == 0 and heldout["positives"] is None
        assert heldout["models"] == {} and heldout["paired"] == {}
        assert heldout["metric_status"] == "UNAVAILABLE_NO_SCORED_ENTRIES"
        assert result["example_figure"] is None
        for name in ("fig01_reliability_all_models", "fig02_per_fire_brier_paired", "fig05_example_forecast_vs_perimeter"):
            assert result["figure_evidence"][name]["status"] == "GENERATED_WITH_UNAVAILABLE_EVIDENCE"
            assert result["figure_evidence"][name]["metric_data_available"] is False
            assert "UNAVAILABLE" in (fixture.out / "figures" / (name + ".svg")).read_text()
    else:
        assert heldout["entries"] == (99 if outcome == "partial" else 198)
        np.testing.assert_allclose(heldout["models"]["base_seed0"]["pooled"]["brier"], 30 / 99 * .01)
        assert gate["descriptive_subset_criteria"]["calibration"] is True
        assert all(gate["descriptive_subset_criteria"]["brier_comparisons"].values())
        assert result["figure_evidence"]["fig01_reliability_all_models"]["metric_data_available"] is True
        if outcome == "partial":
            assert "supported subset" in heldout["statistic_scope"]
            assert "HOLD: supported subset only" in (fixture.out / "figures/fig01_reliability_all_models.svg").read_text()
    assert gate["criteria_pass"] is (outcome == "complete")
    assert gate["complete_cohort_pass"] is (outcome == "complete")
    assert gate["calibration_pass"] is (outcome == "complete")
    assert all(value is (outcome == "complete") for value in gate["brier_comparisons_pass"].values())
    assert result["report_status"] == ("GENERATED_PENDING_VISUAL_QA" if outcome == "complete" else "HOLD")
    dimensions = {"fig01_reliability_all_models": (2160, 900), "fig02_per_fire_brier_paired": (2160, 780),
                  "fig03_ablation_forest_plot": (1050, 900), "fig04_meanfield_vs_mc_rmse_by_horizon": (1050, 720),
                  "fig05_example_forecast_vs_perimeter": (2160, 600)}
    for name, size in dimensions.items():
        png = fixture.out / "figures" / (name + ".png")
        svg = png.with_suffix(".svg")
        assert png.is_file() and svg.is_file()
        width, height = Image.open(png).size
        assert width == size[0] and abs(height - size[1]) <= 1  # Existing bar-height arithmetic quantizes to whole pixels.
        assert report.sha256(png) == result["figure_evidence"][name]["files_sha256"]["png"]


def test_corrected_spotting_phase_uses_stable_metric_alias_and_keeps_intended_path(report, tmp_path, monkeypatch):
    fixture = build_fixture(report, tmp_path, outcome="complete", primary="burnout_spotting")
    result = execute(report, fixture, monkeypatch)
    assert result["primary_candidate"]["run"] == "burnout_spotting_seed0_flaming_only"
    assert "burnout_spotting_seed0" in result["heldout"]["models"]
    assert result["example_figure"] is not None
    assert result["retrospective_superiority_gate"]["criteria_pass"] is True


def test_metrics_and_fixed_bootstrap_are_unchanged_for_positive_scored_entries(report, tmp_path, monkeypatch):
    fixture = build_fixture(report, tmp_path, outcome="complete")
    monkeypatch.setattr(report, "REPO", fixture.root)
    entries, assessment = report.load_assessment(fixture.run / "heldout")
    reference = report.B.score_entries(entries, draws=10000, seed=20261030)
    detailed = report.assessment_scores(entries, assessment)
    for model, record in reference["models"].items():
        for metric in ("brier", "average_precision", "roc_auc", "ece_10_bins", "clipped_nll", "lowest_bin", "calibration"):
            assert record["pooled"][metric] == detailed["models"][model]["pooled"][metric]
        assert reference["paired"].get(model + "__vs__persistence") == detailed["paired"].get(model + "__vs__persistence")


@pytest.mark.parametrize("tamper", ["frozen_binding", "n_samples", "seed", "input_hash", "entry_hash", "missing_file"])
def test_re_signed_handoff_or_missing_scored_bytes_cannot_change_report_evidence(report, tmp_path, monkeypatch, tamper):
    fixture = build_fixture(report, tmp_path, outcome="partial")
    monkeypatch.setattr(report, "REPO", fixture.root)
    path = fixture.run / "report_inputs.json"; inputs = json.loads(path.read_text())
    if tamper == "frozen_binding": inputs["frozen_assessment_sha256"] = "0" * 64
    if tamper == "n_samples": inputs["n_samples"] = 2
    if tamper == "seed": inputs["seed"] = 1
    if tamper == "input_hash": inputs["data_manifest_sha256"] = "0" * 64
    write(path, inputs)
    scored = fixture.run / "heldout/SYNTHETIC_A.npz"
    if tamper == "entry_hash": scored.write_bytes(b"changed synthetic entries")
    if tamper == "missing_file": scored.unlink()
    with pytest.raises(ValueError):
        entries, assessment = report.load_assessment(fixture.run / "heldout")
        report.load_report_inputs(fixture.run, assessment)


def test_empty_secondary_reconstruction_hold_is_reported_with_all_reasons(report, tmp_path, monkeypatch):
    fixture = build_fixture(report, tmp_path, outcome="empty")
    korea = fixture.run / "korean2025"; korea.mkdir()
    for name in ("ASSESSMENT.json", "FROZEN_ASSESSMENT.json"):
        shutil.copyfile(fixture.run / "heldout" / name, korea / name)
    result = execute(report, fixture, monkeypatch)
    secondary = result["korean2025_secondary_reconstruction"]
    assert secondary["metric_status"] == "UNAVAILABLE_NO_SCORED_ENTRIES"
    assert secondary["unscored_outcomes"] == fixture.assessment["failed_or_unavailable"]
    assert result["report_status"] == "HOLD"
