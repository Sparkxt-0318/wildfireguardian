"""Synthetic report control: valid base winner first, corrected spotting second.

Numerical scores, source admission and plotting are mocked. Exact production
phase-result parsing and report/main model-name use execute on temporary dummy
artifacts. No heldout data, prediction, actual checkpoint or training is read.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import numpy as np
import pytest
sys.dont_write_bytecode = True


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module); return module


def run(repo):
    sys.path.insert(0, str(repo / "forecast"))
    tests = load("independent_report_name_fixtures", repo / "forecast/tests/test_blind_forecast_protocol.py")
    observations = []
    with tempfile.TemporaryDirectory(prefix="wfg-report-name-") as temporary, pytest.MonkeyPatch.context() as mp:
        folder = Path(temporary).resolve(); freezer = tests.freezer.__wrapped__()
        root, runroot, _, _, _ = tests.freeze_inputs.__wrapped__(freezer, folder, mp)
        coverage = tests.fit_coverage_module(freezer)
        report = load("independent_report_name", repo / "research/forecast-v2/scripts/report.py")
        mp.setattr(report, "REPO", root)
        for phase in coverage.current_phase_identity()["phases"]:
            path = runroot / phase["result"]; result = json.loads(path.read_text())
            result.update(parameters=1, fit_seconds=1.); path.write_text(json.dumps(result))
            receipt_path = root / f"research/forecast-v2/executions/a{5 if phase['variant']=='burnout_spotting' else 3:02d}_{phase['job_suffix']}.json"
            receipt = json.loads(receipt_path.read_text()); receipt["output_sha256"] = coverage.sha(path)
            receipt_path.write_text(json.dumps(receipt))
        out = folder / "mocked-report"; out.mkdir()
        heldout = runroot / "heldout"; heldout.mkdir(); (heldout / "synthetic.npz").write_bytes(b"not opened"); (heldout / "ASSESSMENT.json").write_text("{}")
        (runroot / "report_inputs.json").write_text('{"n_samples":1024}')
        names = ["base_seed0", "burnout_spotting_seed0", "persistence", "dilation_best"]
        entries = dict(predictions={name: np.array([.1]) for name in names})
        scores = dict(entries=1, fires=["synthetic"], models={name: dict(pooled=dict(lowest_bin=dict(count=1, mean_prediction=.1, observed_frequency=.1)), per_fire={}) for name in names}, paired={primary + "__vs__" + baseline: dict(percentile_95_interval=[-.1, -.01]) for primary in names[:2] for baseline in names[2:]})
        ablation = {variant: dict(mean_fire_brier=.1, folds=["2020", "2021", "2022"], seeds=[0]) for variant in coverage.VARIANTS}
        mp.setattr(report, "ablation", lambda path: ablation); mp.setattr(report, "style", lambda: None)
        mp.setattr(report, "load_assessment", lambda path: (entries, dict(status="COMPLETE", failed_or_unavailable=[], events=["synthetic"], cases=[dict(status="SCORED")])))
        mp.setattr(report, "detailed_scores", lambda entries: scores)
        mp.setattr(report, "load_report_inputs", lambda *a: dict(n_samples=1024))
        mp.setattr(report, "figure_unavailable", lambda *a: None)
        figures = out / "figures"; figures.mkdir()
        for stem in ["fig01_reliability_all_models", "fig02_per_fire_brier_paired", "fig03_ablation_forest_plot", "fig04_meanfield_vs_mc_rmse_by_horizon", "fig05_example_forecast_vs_perimeter"]:
            for ext in ["png", "svg"]: (figures / (stem + "." + ext)).write_bytes(b"MOCK FIGURE: alias unit control only")
        for name in ["figure_ablation", "figure_reliability", "figure_per_fire", "figure_example"]: mp.setattr(report, name, lambda *a: None)
        mp.setattr(sys, "argv", ["report.py", "--run", str(runroot), "--out", str(out)])
        for primary in ["base", "burnout_spotting"]:
            for variant, row in ablation.items(): row["mean_fire_brier"] = .01 if variant == primary else .1
            try:
                report.main()
                result = json.loads((out / "RESULTS.json").read_text())
                gate = result["retrospective_superiority_gate"]
                passed = (result["primary_candidate"]["variant"] == primary and gate["diagnostic_status"] == "AVAILABLE" and gate["calibration_pass"] is True and all(gate["brier_comparisons_pass"].values()) and gate["criteria_pass"] is False and primary + "_seed0" in gate["lowest_bin_absolute_gaps"])
                observed = dict(state="RETURNED", primary_candidate=result["primary_candidate"], retrospective_gate=gate)
            except KeyError as error:
                passed = False; observed = dict(state="RAISED", type=type(error).__name__, reason=str(error))
            observations.append(dict(id=primary + "_winner_report", pass_check=passed, observed=observed))
    return dict(source_head=subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip(), scope=__doc__ + " Parent637 adaptation mocks added source-auth report entry points and creates explicit dummy figure bytes; only name lookup/gate access is tested, no data-admission or visual claim.", script_sha256=sha(__file__), source_sha256={path: sha(repo / path) for path in ["research/forecast-v2/scripts/report.py", "research/forecast-v2/scripts/audit_fit_coverage.py", "research/forecast-v2/scripts/score_cohorts.py", "forecast/tests/test_blind_forecast_protocol.py"]}, host=platform.platform(), observations=observations, checks=len(observations), passed=sum(row["pass_check"] for row in observations), actual_study_inputs_or_models_accessed=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--track-b", type=Path, required=True); parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(); result = run(args.track_b.resolve()); result["status"] = "PASS_REPORT_MODEL_NAME" if result["checks"] == result["passed"] else "FAIL_REPORT_MODEL_NAME"
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(dict(status=result["status"], checks=result["checks"], passed=result["passed"], observations=result["observations"])))
    raise SystemExit(0 if result["checks"] == result["passed"] else 1)
