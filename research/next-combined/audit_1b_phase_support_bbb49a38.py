"""Bounded independent phase/source/support/public-route controls.

Only temporary synthetic inputs, dummy checkpoint bytes and tiny mechanism
calls are used. No training, actual model, study source, future source, heldout
prediction or shared heavy lease is accessed. Owner fixture constructors are
reused; the mutations and assertions below are independent.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import pytest
import numpy as np
import torch

sys.dont_write_bytecode = True


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def run(repo):
    sys.path.insert(0, str(repo / "forecast"))
    sys.path.insert(0, str(repo / "research/forecast-v2/scripts"))
    from wildfire.burnout import FlamingWindow
    from wildfire.meanfield import propagate_mean_field
    from wildfire.survival import PerimeterSample, sample_forecast, sample_tensors
    t = load("independent_bbb_fixture", repo / "forecast/tests/test_blind_forecast_protocol.py")
    observations = []

    def probe(name, fn, refuse=False, reason=None):
        try:
            value = fn()
            passed = not refuse and value is not False
            observed = dict(state="RETURNED", value=value)
        except (ValueError, KeyError, TypeError, FileNotFoundError, RuntimeError) as error:
            passed = refuse and (reason is None or reason in str(error))
            observed = dict(state="RAISED", type=type(error).__name__, reason=str(error))
        observations.append(dict(id=name, pass_check=bool(passed), observed=observed))

    # Explicit age/FRT arithmetic, independent of a learned checkpoint.
    for residence in [2., torch.tensor([[[[1., 3.]]]])]:
        initial = torch.tensor([[[[.25, .5]]]])
        ages = torch.tensor([[[[5., 0.]]]])
        history = [(.5, torch.tensor([[[[.1, .1]]]])), (2.5, torch.tensor([[[[.2, .2]]]]))]
        current = initial + sum(v for _, v in history)
        law = FlamingWindow(residence, .4)
        expected = initial * (ages + 3. < torch.as_tensor(residence))
        for clock, increment in history:
            expected += increment * (3. - clock < torch.as_tensor(residence))
        actual = law.flaming_source(initial, ages, history, 3., current=current)
        probe("flaming_age_history_" + ("scalar" if isinstance(residence, float) else "per_cell"),
              lambda: torch.equal(actual, expected) and bool((law.source(initial, ages, history, 3., current=current) >= actual).all()))

    mechanism = load("independent_bbb_mechanism", repo / "forecast/tests/test_spotting_flaming_only.py")
    old_threads = torch.get_num_threads()
    torch.set_num_threads(1)
    try:
        model, old_case = mechanism.sample(100.)
        rng = torch.random.get_rng_state().clone()
        with torch.no_grad():
            q, valid = sample_forecast(model, old_case)
            local, _ = sample_forecast(model, old_case, use_spotting=False)
        probe("old_cell_no_long_range_but_positive_local_smoulder", lambda: bool(valid[30, 30]) and float(q[30, 30]) == float(local[30, 30]) == 0. and float(q[30, 21]) > 0.)
        probe("mechanism_rng_unchanged", lambda: torch.equal(rng, torch.random.get_rng_state()))
        young_model, young = mechanism.sample(0.)
        with torch.no_grad():
            young_q, young_valid = sample_forecast(young_model, young)
        probe("young_cell_retains_long_range_branch", lambda: bool(young_valid[30, 30]) and float(young_q[30, 30]) > 0.)
        tensors = sample_tensors(young)
        def callback(source, step): return torch.zeros_like(source)
        callback.source_mode = "flaming_only"
        callback.source_radius = 0
        probe("flaming_callback_without_window_refused", lambda: propagate_mean_field(young_model, tensors["initial"], tensors["environment"], [1.], boundary="zero", extra_rate_fn=callback), True, "flaming-window")
        callback.source_mode = "arbitrary"
        probe("unknown_callback_source_mode_refused", lambda: propagate_mean_field(young_model, tensors["initial"], tensors["environment"], [1.], boundary="zero", extra_rate_fn=callback), True, "source_mode")
        # Same explicit shared callback versus the public default, no RNG draw.
        del callback.source_mode
        with torch.no_grad():
            default = propagate_mean_field(young_model, tensors["initial"], tensors["environment"], [1.], boundary="zero", burnout=young_model.flaming_window(), extra_rate_fn=callback)
            callback.source_mode = "shared"
            shared = propagate_mean_field(young_model, tensors["initial"], tensors["environment"], [1.], boundary="zero", burnout=young_model.flaming_window(), extra_rate_fn=callback)
        probe("default_callback_equals_explicit_shared", lambda: torch.equal(default.valid, shared.valid) and torch.equal(default.new_burn_probability, shared.new_burn_probability))
    finally:
        torch.set_num_threads(old_threads)

    with tempfile.TemporaryDirectory(prefix="wfg-bbb-source-phase-") as temporary, pytest.MonkeyPatch.context() as mp:
        folder = Path(temporary).resolve()
        f = t.freezer.__wrapped__()
        fixture = t.freeze_inputs.__wrapped__(f, folder, mp)
        root, runroot, selection_path, comparator, selection = fixture
        m, _, _, inputs, caches, _, recorded = t.fit_coverage_state(f, fixture)
        audit_path = root / selection["cache_audit"]["path"]
        def build(): return f.build_registry(root, runroot, selection_path, comparator)
        def audit(): return m.audit_coverage(root, inputs, caches, runroot, audit_path)
        good = build()
        probe("complete_current_phase_registry_positive", lambda: good["current_phase"] == m.current_phase_identity() and good["execution_status"] == "NOT_READY_FOR_2026_EXECUTION")
        probe("intended_map_exact28_and_only_spotting_suffix_changed", lambda: len(good["current_phase"]["phases"]) == 28 and all((p["artifact_suffix"] == "_flaming_only") == (p["variant"] == "burnout_spotting") for p in good["current_phase"]["phases"]))
        pristine = {p: p.read_bytes() for p in folder.rglob("*") if p.is_file()}
        def restore():
            for p in folder.rglob("*"):
                if p.is_file() and p not in pristine: p.unlink()
            for p, raw in pristine.items(): p.write_bytes(raw)
        def negative(name, change, fn=build, reason=None):
            restore()
            def exercise():
                change()
                return fn()
            probe(name, exercise, True, reason)
            restore()
        def resign_fold(variant, change_result=None, change_receipt=None):
            phase = m.intended_phase(variant, "fold", "2020")
            path = runroot / phase["result"]
            receipt_path = root / f"research/forecast-v2/executions/a{5 if variant == 'burnout_spotting' else 3:02d}_{phase['job_suffix']}.json"
            value, receipt = json.loads(path.read_text()), json.loads(receipt_path.read_text())
            if change_result: change_result(value)
            path.write_text(json.dumps(value)); receipt["output_sha256"] = m.sha(path)
            if change_receipt: change_receipt(receipt)
            receipt_path.write_text(json.dumps(receipt))
            # Re-freeze only synthetic development metadata, as the public builder allows.
            values, records = m.development_selection(root, runroot)
            frozen = json.loads(selection_path.read_text())
            frozen.update(development_brier=values, development_phases=records)
            selection_path.write_text(json.dumps(frozen))
        def bad_budget():
            resign_fold("burnout_spotting", lambda r: r.update(train_samples=1, validation_samples=2),
                lambda r: r["command"].extend(["--max-fit-intervals-per-fire", "1", "--epochs", "1", "--intervals-per-epoch", "1"]))
        negative("development_budget_and_sample_membership_change_refused", bad_budget)
        negative("development_same_fire_keys_zero_samples_refused", lambda: resign_fold("burnout_spotting", lambda r: r.update(train_samples=0, validation_samples=0)))
        negative("development_wrong_fit_fire_membership_refused", lambda: resign_fold("burnout_spotting", lambda r: r.update(train_events=["wrong_fold_fire"])))
        negative("development_fire_omission_refused", lambda: resign_fold("burnout_spotting", lambda r: r["validation_per_fire"].pop(next(iter(r["validation_per_fire"])))), reason="fire membership")
        def old_spot():
            phase = m.intended_phase("burnout_spotting", "final")
            p = root / f"research/forecast-v2/executions/a05_{phase['job_suffix']}.json"
            r = json.loads(p.read_text()); r["job"] = "a03_" + phase["job_suffix"]; p.write_text(json.dumps(r))
        negative("old_spotting_attempt_renamed_to_current_refused", old_spot, reason="attempt5")
        def old_law():
            import gzip
            p = root / "forecast/wildfire/survival.py"
            raw = p.read_text().replace('spotting.source_mode = "flaming_only"', 'spotting.source_mode = "shared"').encode()
            digest = hashlib.sha256(raw).hexdigest()
            snapshot = root / "research/forecast-v2/source_snapshots" / digest / "survival.py.gz"
            snapshot.parent.mkdir(parents=True, exist_ok=True); snapshot.write_bytes(gzip.compress(raw, mtime=0))
            phase = m.intended_phase("burnout_spotting", "final")
            p = root / f"research/forecast-v2/executions/a05_{phase['job_suffix']}.json"
            r = json.loads(p.read_text()); r["source_sha256"]["forecast/wildfire/survival.py"] = digest; p.write_text(json.dumps(r))
        negative("preserved_old_emitter_law_refused", old_law, reason="flaming-only source contract")
        # Successful runtime accounting with a preexisting policy2 skip, before mutations.
        restore(); state = t.supported_skip_fixture(f, fixture, "unknown_environment")
        _, _, _, _, _, _, mixed_result, mixed_receipt = state
        support = audit()["variants"]["mixed_base"]
        probe("source_unknown_logged_skip_positive", lambda: support["coverage_status"] == "FULL_INPUT_ATTEMPTED_WITH_LOGGED_UNSUPPORTED" and all(len(e["optimized_case_ids"]) == 11 and len(e["skipped_samples"]) == 1 for e in support["epoch_optimized_and_unsupported"]))
        probe("unsupported_accounting_not_zero_brier_or_mask_replay", lambda: all("NOT_RUNTIME_LOGGED" in e["optimized_identity_evidence"] and "NOT_PER_OPTIMIZER_MASK_REPLAY" in e["skipped_samples"][0]["evidence"] for e in support["epoch_optimized_and_unsupported"]) and "brier" not in support)
        skip_pristine = {p: p.read_bytes() for p in folder.rglob("*") if p.is_file()}
        def skip_change(mode):
            for p, raw in skip_pristine.items(): p.write_bytes(raw)
            r = json.loads(mixed_result.read_text()); history = r["fit"]["history"][0]; epoch = r["fit"]["runtime_membership"]["epochs"][0]
            if mode == "unlogged": history["skipped_unsupported_intervals"] = []
            if mode == "wrong_case": epoch["skipped_case_ids"] = ["f" * 64]
            if mode == "duplicate": epoch["skipped_case_ids"] *= 2
            if mode == "wrong_count": epoch["optimizer_steps"] += 1
            if mode == "zero_updates": epoch["optimizer_steps"] = history["optimizer_steps"] = 0
            mixed_result.write_text(json.dumps(r)); receipt = json.loads(mixed_receipt.read_text()); receipt["output_sha256"] = m.sha(mixed_result); mixed_receipt.write_text(json.dumps(receipt))
        for mode in ["unlogged", "wrong_case", "duplicate", "wrong_count", "zero_updates"]:
            skip_change(mode); probe("unsupported_" + mode + "_refused", audit, True)
        restore()
        source_sample = SimpleNamespace(initial=np.zeros((20, 20), bool), score_mask=np.ones((20, 20), bool),
            environment=np.zeros((1, 20, 20)), label_weight=np.ones((20, 20)), hours=12., weather="cutoff_repeated")
        source_sample.initial[0, 0] = True; source_sample.score_mask[0, 0] = False
        probe("finite_inputs_cannot_explain_numerical_skip", lambda: m.unsupported_source_reason(source_sample), True, "retains positive source weight")
        source_sample.label_weight[1, 1] = np.nan
        probe("nonfinite_weights_not_data_unsupported", lambda: m.unsupported_source_reason(source_sample), True, "finite nonnegative weights")
        # Resume admission authenticates a saved registry; no external2026 clearance follows.
        registry_path = root / "research/forecast-v2/BLIND_REGISTRY.json"
        registry_path.write_text(json.dumps(build()))
        def saved(): return m.saved_registry_admission(root, runroot, selection_path, json.loads(selection_path.read_text()), registry_path)
        probe("saved_registry_positive_before_and_after_dummy_assessment", lambda: saved()["current_phase"] == m.current_phase_identity())
        p = root / "research/forecast-v2/scripts/blind_inventory.py"; raw = p.read_bytes(); p.write_bytes(raw + b"changed")
        probe("resumed_registry_source_change_refused", saved, True, "source closure changed"); p.write_bytes(raw)
        # Tiny report control uses synthetic metrics, not a heldout prediction.
        report = load("independent_bbb_report", repo / "research/forecast-v2/scripts/report.py")
        mp.setattr(report, "REPO", root)
        for phase in m.current_phase_identity()["phases"]:
            p = runroot / phase["result"]; r = json.loads(p.read_text()); r.update(parameters=1, fit_seconds=1.)
            p.write_text(json.dumps(r)); q = root / f"research/forecast-v2/executions/a{5 if phase['variant']=='burnout_spotting' else 3:02d}_{phase['job_suffix']}.json"
            v = json.loads(q.read_text()); v["output_sha256"] = m.sha(p); q.write_text(json.dumps(v))
        out = folder / "mocked-report"; out.mkdir()
        held = runroot / "heldout"; held.mkdir(); (held / "fixture.npz").write_bytes(b"not-read")
        (runroot / "report_inputs.json").write_text('{"n_samples":1024}')
        names = ["burnout_spotting_seed0", "persistence", "dilation_best"]
        entries = dict(predictions={n: np.array([.1]) for n in names})
        scores = dict(models={n: dict(pooled=dict(lowest_bin=dict(count=1, mean_prediction=.1, observed_frequency=.1)), per_fire={}) for n in names}, paired={names[0] + "__vs__" + n: dict(percentile_95_interval=[-.1, -.01]) for n in names[1:]})
        ablation = {v: dict(mean_fire_brier=.01 if v == "burnout_spotting" else .1, folds=["2020", "2021", "2022"], seeds=[0]) for v in m.VARIANTS}
        mp.setattr(report, "ablation", lambda path: ablation); mp.setattr(report, "style", lambda: None)
        mp.setattr(report, "load_assessment", lambda path: (entries, dict(status="COMPLETE", failed_or_unavailable=[])))
        mp.setattr(report, "detailed_scores", lambda entries: scores)
        for n in ["figure_ablation", "figure_reliability", "figure_per_fire", "figure_example"]: mp.setattr(report, n, lambda *a: None)
        mp.setattr(sys, "argv", ["report.py", "--run", str(runroot), "--out", str(out)])
        probe("spotting_primary_report_uses_scoring_model_identity", report.main)

    # Public route only constructs commands; no subprocess or numerical lease runs.
    with tempfile.TemporaryDirectory(prefix="wfg-bbb-command-") as temporary, pytest.MonkeyPatch.context() as mp:
        runner = load("independent_bbb_runner", repo / "research/forecast-v2/scripts/run_campaign.py")
        folder = Path(temporary).resolve(); data = folder / "data"; data.mkdir(); (data / "EXTRACTION_MANIFEST.json").write_text("synthetic identity")
        mp.setattr(runner, "DATA", data); mp.setattr(runner, "RUN", folder / "run")
        mp.setattr(runner, "job", lambda *args: (_ for _ in ()).throw(AssertionError("no outer lease")))
        calls = []; mp.setattr(runner.subprocess, "run", lambda command, **kw: calls.append((command, kw)))
        registry = folder / "synthetic-registry.json"
        mp.setattr(sys, "argv", ["run_campaign.py", "heldout", "--registry", str(registry)])
        runner.main()
        probe("public_heldout_routes_both_cohorts_to_guarded_case_scorer", lambda: len(calls) == 2 and all(Path(c[1]).name == "score_cohorts.py" and c[-2:] == ["--registry", str(registry)] and kw["check"] for c, kw in calls))
        pipeline = load("independent_bbb_pipeline", repo / "research/forecast-v2/scripts/pipeline.py")
        probe("legacy_pipeline_heldout_refuses", lambda: pipeline.command_heldout(SimpleNamespace()), True, "retired")

    paths = ["forecast/wildfire/burnout.py", "forecast/wildfire/meanfield.py", "forecast/wildfire/models.py", "forecast/wildfire/survival.py", "forecast/tests/test_blind_forecast_protocol.py", "forecast/tests/test_spotting_flaming_only.py", "research/forecast-v2/scripts/audit_fit_coverage.py", "research/forecast-v2/scripts/freeze_registry.py", "research/forecast-v2/scripts/run_campaign.py", "research/forecast-v2/scripts/pipeline.py", "research/forecast-v2/scripts/score_cohorts.py", "research/forecast-v2/scripts/blind_test.py", "research/forecast-v2/scripts/status.py", "research/forecast-v2/scripts/report.py", "research/forecast-v2/RUN_PROTOCOL_EXTENSION_2.json", "research/forecast-v2/RUN_PROTOCOL_EXTENSION_10.json"]
    return dict(source_head=subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip(), scope=__doc__, host=platform.platform(), python=sys.version, numpy=np.__version__, torch=torch.__version__, script_sha256=sha(__file__), source_sha256={p: sha(repo / p) for p in paths}, observations=observations, checks=len(observations), passed=sum(r["pass_check"] for r in observations), actual_study_inputs_or_models_accessed=False, shared_heavy_lease=False, training_executed=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--track-b", type=Path, required=True); parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(); result = run(args.track_b.resolve())
    result["status"] = "PASS_SCOPED_SOURCE_PHASE_SUPPORT_ROUTES" if result["checks"] == result["passed"] else "HOLD_SCOPED_SOURCE_PHASE_SUPPORT_ROUTES"
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: result[k] for k in ["status", "checks", "passed"]}))
    print(json.dumps([r for r in result["observations"] if not r["pass_check"]], indent=2))
    raise SystemExit(0 if result["checks"] == result["passed"] else 1)
