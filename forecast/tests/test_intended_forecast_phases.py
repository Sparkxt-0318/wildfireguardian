"""Metadata-only plans and source-derived support controls, no study inputs."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import numpy as np
import pytest


def load_script(name):
    path = Path(__file__).resolve().parents[2] / f"research/forecast-v2/scripts/{name}.py"
    spec = importlib.util.spec_from_file_location("synthetic_phase_" + name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_one_fixed_map_changes_only_spotting_and_preserves_mixed_fold_suffix():
    module = load_script("audit_fit_coverage")
    for variant in module.VARIANTS:
        for stage, fold in [("fold", "2020"), ("final", None)]:
            phase = module.intended_phase(variant, stage, fold)
            expected = "_flaming_only" if variant == "burnout_spotting" else ("_utc_fixed" if variant == "mixed_base" and stage == "fold" else "")
            assert phase["artifact_suffix"] == expected
            assert phase["phase_id"].endswith("seed0" + expected)
    assert len(module.current_phase_identity()["phases"]) == 28


@pytest.mark.parametrize("stage,expected_count", [("spotting-repair", 4), ("fits", 24)])
def test_runner_plans_exact_intended_jobs_without_starting_numerical_work(tmp_path, monkeypatch, stage, expected_count):
    runner = load_script("run_campaign")
    data, run = tmp_path / "data", tmp_path / "run"
    data.mkdir(); (data / "EXTRACTION_MANIFEST.json").write_text("synthetic input identity")
    monkeypatch.setattr(runner, "DATA", data); monkeypatch.setattr(runner, "RUN", run)
    jobs = []
    monkeypatch.setattr(runner, "job", lambda *args: jobs.append(args))
    monkeypatch.setattr(sys, "argv", ["run_campaign.py", stage])
    runner.main()
    assert len(jobs) == expected_count
    if stage == "spotting-repair":
        assert [command[2] for _, command, _ in jobs] == ["fold", "fold", "fold", "final"]
        assert all(name.startswith("a05_") and name.endswith("_flaming_only") for name, _, _ in jobs)
        assert all(command[-1] != "" and "_flaming_only" in command for _, command, _ in jobs)
        assert all("burnout_spotting" in command for _, command, _ in jobs)
        for name, command, output in jobs:
            assert command[command.index("--seed") + 1] == "0"
            assert command[command.index("--epochs") + 1] == "3"
            assert output.parent.name.endswith("_flaming_only")
        assert jobs[-1][1][-4:] == ["--max-fit-intervals-per-fire", "0", "--intervals-per-epoch", "0"]
    else:
        assert all("burnout_spotting" not in command for _, command, _ in jobs)
        assert sum(output.parent.name.endswith("_utc_fixed") for _, _, output in jobs) == 3


def test_repair_attempt_and_pipeline_suffix_refuse_before_loading_models(tmp_path, monkeypatch):
    runner = load_script("run_campaign")
    monkeypatch.setattr(sys, "argv", ["run_campaign.py", "spotting-repair", "--attempt", "4"])
    with pytest.raises(ValueError, match="attempt5"):
        runner.main()
    pipeline = load_script("pipeline")
    args = SimpleNamespace(variant="burnout_spotting", seed=0, fold="2020", artifact_suffix="")
    monkeypatch.setattr(pipeline, "Environment", lambda *args: pytest.fail("must reject before source loading"))
    with pytest.raises(ValueError, match="intended phase"): pipeline.command_final(args)
    with pytest.raises(ValueError, match="intended phase"): pipeline.command_fold(args)


@pytest.mark.parametrize("hours", [.25, 1., 2.5, 12.])
def test_conservative_support_classifier_retains_unknown_covariate_inputs_without_scoring_them(hours):
    module = load_script("audit_fit_coverage")
    sample = SimpleNamespace(initial=np.zeros((20, 20), dtype=bool), score_mask=np.ones((20, 20), dtype=bool),
        environment=np.full((2, 20, 20), np.nan), label_weight=np.ones((20, 20)), hours=hours, weather="cutoff_repeated")
    sample.initial[0, 0] = True; sample.score_mask[0, 0] = False
    result = module.unsupported_source_reason(sample)
    assert result["classification"] == "EMPTY_REPEATED_CUTOFF_ENVIRONMENT_SUPPORT"
    assert result["reference_positive_weight_cells"] == 399
    assert result["supported_positive_weight_cells"] == 0
    assert "NOT_PER_OPTIMIZER_MASK_REPLAY" in result["evidence"]
    sample.environment[:] = 0
    with pytest.raises(ValueError, match="retains positive source weight"):
        module.unsupported_source_reason(sample)


def test_support_recurrence_is_needed_beyond_one_hour_and_has_known_zero_exterior():
    module = load_script("audit_fit_coverage")
    sample = SimpleNamespace(initial=np.zeros((30, 30), bool), score_mask=np.zeros((30, 30), bool),
        environment=np.zeros((1, 30, 30)), label_weight=np.ones((30, 30)), hours=1., weather="cutoff_repeated")
    sample.environment[:, 15, 15] = np.nan
    sample.score_mask[15, 23] = True
    with pytest.raises(ValueError, match="retains positive source weight"):
        module.unsupported_source_reason(sample)
    sample.hours = 2.
    assert module.unsupported_source_reason(sample)["classification"] == "EMPTY_REPEATED_CUTOFF_ENVIRONMENT_SUPPORT"
    sample.environment[:] = 0; sample.score_mask[:] = False; sample.score_mask[0, 0] = True
    with pytest.raises(ValueError, match="retains positive source weight"):
        module.unsupported_source_reason(sample)


def test_campaign_heldout_uses_two_guarded_scorers_without_an_outer_job_lock(tmp_path, monkeypatch):
    runner = load_script("run_campaign")
    data, run = tmp_path / "data", tmp_path / "run"
    data.mkdir(); (data / "EXTRACTION_MANIFEST.json").write_text("synthetic input identity")
    monkeypatch.setattr(runner, "DATA", data); monkeypatch.setattr(runner, "RUN", run)
    monkeypatch.setattr(runner, "job", lambda *args: pytest.fail("guarded per-case scorer cannot be wrapped in job lock"))
    calls = []
    monkeypatch.setattr(runner.subprocess, "run", lambda command, **kwargs: calls.append((command, kwargs)))
    registry = tmp_path / "synthetic-BLIND_REGISTRY.json"
    monkeypatch.setattr(sys, "argv", ["run_campaign.py", "heldout", "--registry", str(registry)])
    runner.main()
    assert [command[command.index("--cohort") + 1] for command, _ in calls] == ["us2024", "korea2025"]
    assert all(Path(command[1]).name == "score_cohorts.py" for command, _ in calls)
    assert all(command[-2:] == ["--registry", str(registry)] and kwargs["check"] for command, kwargs in calls)
    pipeline = load_script("pipeline")
    with pytest.raises(RuntimeError, match="retired.*score_cohorts"):
        pipeline.command_heldout(SimpleNamespace())
