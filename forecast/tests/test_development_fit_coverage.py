"""Independent synthetic development admission, without scientific model runs."""
import json
from pathlib import Path
import pickle
import shutil

import pytest

if __package__:
    from .test_blind_forecast_protocol import (freezer, freeze_inputs, fit_coverage_module, fit_coverage_state,
                                              supported_skip_fixture)
else:
    from test_blind_forecast_protocol import (freezer, freeze_inputs, fit_coverage_module, fit_coverage_state,
                                             supported_skip_fixture)


def fold_paths(module, root, run, variant="burnout_spotting", fold="2020"):
    phase = module.intended_phase(variant, "fold", fold)
    result = run / phase["result"]
    receipt = root / f"research/forecast-v2/executions/a{5 if variant == 'burnout_spotting' else 3:02d}_{phase['job_suffix']}.json"
    return result, receipt


def resign(module, result_path, receipt_path, result=None, receipt=None):
    if result is not None: result_path.write_text(json.dumps(result))
    receipt = json.loads(receipt_path.read_text()) if receipt is None else receipt
    receipt["output_sha256"] = module.sha(result_path)
    receipt_path.write_text(json.dumps(receipt))


def audit(module, root, inputs, caches, run):
    return module.audit_coverage(root, inputs, caches, run, root / "research/forecast-v2/CACHE_AUDIT.json")


def test_all21_development_phases_bind_exact_train_validation_prefixes_and_real_default_cap(freezer, freeze_inputs):
    module, root, run, inputs, caches, _, record = fit_coverage_state(freezer, freeze_inputs)
    phases = record["development"]
    assert len(phases) == 21
    for name, phase in phases.items():
        mixed = phase["intended_phase"]["variant"] == "mixed_base"
        assert phase["training"]["sample_count"] == (15 if mixed else 6)
        assert phase["validation"]["sample_count"] == 3
        assert len(phase["training"]["cases"]) == phase["training"]["sample_count"]
        assert phase["budget"]["effective_arguments"]["intervals_per_epoch"] == "160"
        assert phase["budget"]["argument_origins"]["intervals_per_epoch"] == "IMMUTABLE_ARGPARSE_DEFAULT"
        assert phase["budget"]["interval_cap_status"] == "NONBINDING_CAP"
        assert phase["schedule_evidence"] == "SOURCE_DERIVED_SCHEDULE_INFERENCE_NO_RUNTIME_IDS_RECORDED"
        assert phase["runtime_membership"] is None
        assert all(case["kind"] == "perimeter" for case in phase["validation"]["cases"])
        assert all(epoch["optimizer_steps"] == phase["training"]["sample_count"] for epoch in phase["epochs"])
    selection = json.loads((root / "research/forecast-v2/MODEL_SELECTION.json").read_text())
    assert selection["development_coverage_sha256"] == module.object_sha(phases)
    assert audit(module, root, inputs, caches, run)["development"] == phases


@pytest.mark.parametrize("tamper", ["epochs", "maxfit", "cap", "samples_per_step", "hidden", "lr", "balance",
                                    "equals_last_arg", "no_epochs", "short_epoch", "counter", "missing_train_event", "wrong_validation_event"])
def test_phase_admission_rejects_wrong_fixed_development_budget_before_source_coverage(freezer, freeze_inputs, tamper):
    module, root, run, _, _, _, _ = fit_coverage_state(freezer, freeze_inputs)
    result_path, receipt_path = fold_paths(module, root, run)
    result, receipt = json.loads(result_path.read_text()), json.loads(receipt_path.read_text())
    if tamper in ("epochs", "maxfit", "cap", "samples_per_step", "hidden", "lr"):
        option, value = {"epochs": ("--epochs", "1"), "maxfit": ("--max-fit-intervals-per-fire", "1"),
            "cap": ("--intervals-per-epoch", "1"), "samples_per_step": ("--samples-per-step", "2"),
            "hidden": ("--hidden", "1"), "lr": ("--lr", ".1")}[tamper]
        receipt["command"] += [option, value]
    if tamper == "balance": receipt["command"].remove("--balance")
    if tamper == "equals_last_arg": receipt["command"] += ["--epochs", "3", "--epochs=1"]
    if tamper == "no_epochs": result["fit"]["history"] = []
    if tamper == "short_epoch": result["fit"]["history"].pop()
    if tamper == "counter": result["fit"]["history"][0]["optimizer_steps"] -= 1
    if tamper == "missing_train_event": result["train_events"].pop()
    if tamper == "wrong_validation_event": result["validation_events"] = ["synthetic_fit_second"]
    resign(module, result_path, receipt_path, result, receipt)
    with pytest.raises(ValueError): module.phase_result(root, run, "burnout_spotting", "fold", "2020")


def test_re_signed_small_counters_and_full_firekeys_cannot_substitute_for_actual_development_membership(freezer, freeze_inputs):
    module, root, run, inputs, caches, _, _ = fit_coverage_state(freezer, freeze_inputs)
    result_path, receipt_path = fold_paths(module, root, run)
    result = json.loads(result_path.read_text())
    result.update(train_samples=1, validation_samples=2)
    for epoch in result["fit"]["history"]: epoch["optimizer_steps"] = 1
    resign(module, result_path, receipt_path, result)
    module.phase_result(root, run, "burnout_spotting", "fold", "2020")
    with pytest.raises(ValueError, match="every independently derived first3"):
        audit(module, root, inputs, caches, run)


@pytest.mark.parametrize("tamper", ["omit", "extra", "duplicate", "wrong_cutoff", "wrong_kind", "wrong_values", "missing_cache"])
@pytest.mark.parametrize("event", ["synthetic_fit", "synthetic_fit_second"])
def test_source_recomputed_first3_cache_cannot_omit_replace_or_add_training_or_validation_cases(freezer, freeze_inputs, tamper, event):
    module, root, run, inputs, caches, _, _ = fit_coverage_state(freezer, freeze_inputs)
    path = caches / f"samples/perimeter_crop_first3_{event}.pkl"
    samples = pickle.loads(path.read_bytes())
    if tamper == "missing_cache": path.unlink()
    else:
        if tamper == "omit": samples.pop()
        if tamper == "extra": samples.append(pickle.loads(path.with_name(path.name.replace("first3", "first0")).read_bytes())[-1])
        if tamper == "duplicate": samples[1] = samples[0]
        if tamper == "wrong_cutoff": samples[0].t1 = "2020-01-01T01:00:00+00:00"; samples[0].hours = 11.
        if tamper == "wrong_kind": samples[0].kind = "kriged"
        if tamper == "wrong_values": samples[0].environment[:] = 123.
        path.write_bytes(pickle.dumps(samples, protocol=5))
        audit_path = root / "research/forecast-v2/CACHE_AUDIT.json"
        value = json.loads(audit_path.read_text())
        row = next(row for row in value["records"] if Path(row["cache"]) == path)
        row.update(cache_sha256=module.sha(path), samples=len(samples), cached_value_identity=module.sample_list_identity(samples),
                   recomputed_value_identity=module.sample_list_identity(samples))
        audit_path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="first3|existing files"):
        audit(module, root, inputs, caches, run)


@pytest.mark.parametrize("which", ["train", "validation", "evaluation"])
def test_immutable_producer_cannot_claim_full_counts_while_consuming_a_subset(freezer, freeze_inputs, which):
    module, root, run, inputs, caches, _, _ = fit_coverage_state(freezer, freeze_inputs)
    path = root / "research/forecast-v2/scripts/pipeline.py"
    original = path.read_bytes()
    snapshot = root / "research/forecast-v2/source_snapshots" / module.sha(path) / path.name
    snapshot.parent.mkdir(parents=True, exist_ok=True); snapshot.write_bytes(original)
    text = original.decode()
    expression = {'train': 'train = fit_samples(args, train_events, env, mixed=spec.get("mixed", False))',
                  'validation': 'validation = fit_samples(args, validation_events, env, mixed=False)',
                  'evaluation': 'scores = evaluate_samples(model, validation)'}[which]
    replacement = expression + '[:1]' if which != 'evaluation' else 'scores = evaluate_samples(model, validation[:1])'
    path.write_text(text.replace(expression, replacement, 1))
    _, receipt_path = fold_paths(module, root, run, "base")
    receipt = json.loads(receipt_path.read_text()); receipt["source_sha256"]["research/forecast-v2/scripts/pipeline.py"] = module.sha(path)
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError): audit(module, root, inputs, caches, run)


def test_historical_mixed_skips_remain_source_inferred_and_all_validation_inputs_are_retained(freezer, freeze_inputs):
    module, root, run, inputs, caches, audit_path, _, _ = supported_skip_fixture(freezer, freeze_inputs, "unknown_environment")
    record = module.audit_coverage(root, inputs, caches, run, audit_path)
    phases = [phase for phase in record["development"].values() if phase["intended_phase"]["variant"] == "mixed_base"]
    assert len(phases) == 3
    for phase in phases:
        assert phase["training"]["sample_count"] == 15 and phase["validation"]["sample_count"] == 3
        assert phase["runtime_membership"] is None
        assert phase["coverage_status"] == "FULL_INPUT_SOURCE_INFERRED_WITH_LOGGED_UNSUPPORTED"
        for epoch in phase["epochs"]:
            assert epoch["optimizer_steps"] == 14
            assert len(epoch["source_derived_skipped_samples"]) == 1
            assert "NO_RUNTIME_CASE_IDS" in epoch["evidence"]


@pytest.mark.parametrize("tamper", ["unlogged", "unknown_reason", "duplicate", "mismatched_cutoff"])
def test_historical_mixed_source_unavailable_skips_require_exact_case_bound_accounting(freezer, freeze_inputs, tamper):
    module, root, run, inputs, caches, audit_path, _, _ = supported_skip_fixture(freezer, freeze_inputs)
    result_path, receipt_path = fold_paths(module, root, run, "mixed_base")
    result = json.loads(result_path.read_text())
    row = result["fit"]["history"][0]
    if tamper == "unlogged": row["skipped_unsupported_intervals"] = []; row["optimizer_steps"] += 1
    if tamper == "unknown_reason": row["skipped_unsupported_intervals"][0]["reason"] = "manual exclusion"
    if tamper == "duplicate": row["skipped_unsupported_intervals"] *= 2; row["optimizer_steps"] -= 1
    if tamper == "mismatched_cutoff": row["skipped_unsupported_intervals"][0]["cutoff"] = "2020-01-01T13:00:00Z"
    resign(module, result_path, receipt_path, result)
    with pytest.raises(ValueError): module.audit_coverage(root, inputs, caches, run, audit_path)


def test_saved_registry_development_admission_relocates_without_original_training_inputs(freezer, freeze_inputs, tmp_path):
    root, run, selection_path, comparator, selection = freeze_inputs
    module = fit_coverage_module(freezer)
    registry_path = root / "research/forecast-v2/BLIND_REGISTRY.json"
    registry = freezer.build_registry(root, run, selection_path, comparator)
    registry_path.write_text(json.dumps(registry))
    record = json.loads((root / selection["fit_coverage"]["path"]).read_text())
    relocated = tmp_path / "relocated-model-root"
    shutil.copytree(root, relocated)
    shutil.rmtree(record["input_root"]); shutil.rmtree(record["cache_root"])
    relocated_run = relocated / run.relative_to(root)
    admitted = module.saved_registry_admission(relocated, relocated_run, relocated / selection_path.relative_to(root),
                                               selection, relocated / registry_path.relative_to(root))
    assert admitted["development_coverage_sha256"] == registry["development_coverage_sha256"]
    assert not Path(record["input_root"]).exists() and not Path(record["cache_root"]).exists()


def test_new_explicit_zero_cap_is_recorded_without_relabelling_historical_default(freezer, freeze_inputs):
    module, root, run, inputs, caches, _, _ = fit_coverage_state(freezer, freeze_inputs)
    result_path, receipt_path = fold_paths(module, root, run)
    receipt = json.loads(receipt_path.read_text()); receipt["command"] += ["--intervals-per-epoch", "0"]
    resign(module, result_path, receipt_path, receipt=receipt)
    record = audit(module, root, inputs, caches, run)
    assert record["development"]["burnout_spotting_fold2020_seed0_flaming_only"]["budget"]["interval_cap_status"] == "UNRESTRICTED_CAP_ZERO"
    assert record["development"]["base_fold2020_seed0"]["budget"]["effective_arguments"]["intervals_per_epoch"] == "160"
