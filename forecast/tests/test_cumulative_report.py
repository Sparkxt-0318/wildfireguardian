"""Independent pooled-score oracles and public cumulative report workflows."""

import csv
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch


def _checkpoint(directory, name="model", rate=0.2):
    from wildfire.models import EnvironmentConditionedConvolution, initialize_kernel_rate

    path = directory / name / "checkpoint.pt"
    path.parent.mkdir(parents=True, exist_ok=True)
    with torch.random.fork_rng():
        torch.manual_seed(31)
        kernel = EnvironmentConditionedConvolution(1, 3, 2).double()
    initialize_kernel_rate(kernel, rate)
    contract = dict(
        format_version=1, architecture="EnvironmentConditionedConvolution",
        in_channels=1, channels=["fixture.temperature"], kernel_size=3,
        hidden_channels=2, dt_hours=1.0, center_rate=0.0,
        eligibility="at_least_one_burned_neighbor",
        splits={"fixture-event": "test"},
    )
    torch.save(dict(
        contract=contract, model_state_dict=kernel.state_dict(),
        normalization_mean=torch.zeros(1, dtype=torch.float64),
        normalization_std=torch.ones(1, dtype=torch.float64), best_epoch=1,
    ), path)
    return path


def _reference(hours=6, cutoff=10_000):
    """One original rectangle; missing reference states stay unknown."""
    states = np.zeros((hours + 1, 1, 7, 9), dtype=np.float64)
    states[:, 0, 3, 2] = 1
    states[max(1, hours // 2):, 0, 3, 3] = 1
    states[-1, 0, 3, 4] = 1
    valid = np.ones_like(states, dtype=bool)
    valid[0, 0, 0, 8] = False
    # These outcome fields are deliberately present only in the reference.
    return dict(
        features=torch.ones((hours + 1, 1, 7, 9), dtype=torch.float64),
        feature_valid=torch.ones((hours + 1, 1, 7, 9), dtype=torch.bool),
        burned_area=torch.from_numpy(states), burned_area_valid=torch.from_numpy(valid),
        channel_names=("fixture.temperature",),
        time_utc=np.arange(hours + 1, dtype=np.int64) * 3600 + cutoff,
        time_valid=np.ones(hours + 1, dtype=bool), pixel_valid=np.ones((7, 9), dtype=bool),
        event_id="fixture-event", arrival_hours=torch.zeros((1, 7, 9)),
        arrival_valid=torch.ones((1, 7, 9), dtype=torch.bool),
        newly_burned_area=torch.zeros_like(torch.from_numpy(states)),
        newly_burned_area_valid=torch.ones_like(torch.from_numpy(valid)),
    )


def _csv(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _data_root(directory):
    root = directory / "data"
    root.mkdir()
    (root / "events.json").write_text("[]\n", encoding="utf-8")
    return root


def _prediction(reference, hours, *, unavailable=()):
    from wildfire import CumulativePrediction, Prediction

    probability = torch.full((1, 1, 7, 9), .25, dtype=torch.float64)
    probability[0, 0, 3, 2] = 0
    total = probability.clone()
    total[0, 0, 3, 2] = 1
    valid = torch.ones_like(probability, dtype=torch.bool)
    for row, col in unavailable:
        valid[0, 0, row, col] = False
    details = SimpleNamespace(
        probability=probability, valid=valid,
        rate=torch.full_like(probability, torch.nan), rate_valid=torch.zeros_like(valid),
    )
    endpoint = Prediction.from_details(
        details, dt_hours=hours, time_utc=reference["time_utc"][:1],
        event_id=reference["event_id"], burned_probability=total,
        pixel_valid=reference["pixel_valid"], time_valid=reference["time_valid"][:1],
        metadata=dict(method="recursive", n_samples=32, seed=4,
                      boundary="zero", missing_burned_area="unburned",
                      environment_policy="repeat_current"),
    )
    return CumulativePrediction((hours,), (endpoint,))


def test_pool_recomputes_rank_scores_instead_of_averaging_case_scores():
    from wildfire.cumulative_report import _pool

    parts = [dict(y=np.asarray([1, 0]), p=np.asarray([.9, .8])),
             dict(y=np.asarray([1, 0]), p=np.asarray([.2, .1]))]
    pooled = _pool(parts, threshold=.5)
    metrics = pooled["metrics"]
    assert metrics["sample_count"] == 4
    assert metrics["roc_auc"] == pytest.approx(.75)
    assert metrics["average_precision"] == pytest.approx(5 / 6)
    assert metrics["brier"] == pytest.approx((.01 + .64 + .64 + .01) / 4)
    assert pooled["classification"]["tp"] == 1
    assert pooled["classification"]["fp"] == 1
    assert pooled["classification"]["tn"] == 1
    assert pooled["classification"]["fn"] == 1
    assert sum(item["sample_count"] for item in pooled["calibration"]["bins"]) == 4


def test_pool_keeps_exact_infinity_separate_from_floored_scores():
    from wildfire.cumulative_report import _pool

    pooled = _pool([dict(y=np.asarray([0, 1]), p=np.asarray([0., 0.]))], threshold=.5)
    scores = pooled["metrics"]
    assert scores["exact_negative_log_likelihood_mean"] == "infinity"
    assert scores["bernoulli_kl_divergence_mean"] == "infinity"
    assert np.isfinite(scores["clipped_log_loss"])
    assert scores["brier"] == .5
    assert scores["bernoulli_wasserstein_2_distance_mean"] == .5
    assert scores["unsupported_positive_sample_count"] == 1
    json.dumps(pooled, allow_nan=False)


@pytest.mark.parametrize("parts", [[], [dict(y=np.asarray([]), p=np.asarray([]))]])
def test_empty_pooled_cohort_has_explicit_undefined_scores(parts):
    from wildfire.cumulative_report import _pool

    pooled = _pool(parts, threshold=.5)
    assert pooled["metrics"]["sample_count"] == 0
    assert pooled["metrics"]["brier"] is None
    assert pooled["metrics"]["roc_auc"] is None
    assert pooled["classification"]["f1"] is None
    json.dumps(pooled, allow_nan=False)


@pytest.mark.parametrize("empty_first", [False, True])
def test_csv_schema_is_stable_when_populated_and_empty_cohorts_alternate(tmp_path, empty_first):
    from wildfire.cumulative_report import _CSV, _pool

    populated = _pool([dict(y=np.asarray([0, 1]), p=np.asarray([.2, .7]))], .5)
    empty = _pool([], .5)
    scores = [empty, populated] if empty_first else [populated, empty]
    path = tmp_path / "scores.csv"
    writer = _CSV(path)
    try:
        for index, score in enumerate(scores):
            writer.append(dict(model_id=str(index), **score))
    finally:
        writer.close()
    rows = _csv(path)
    assert len(rows) == 2
    assert set(rows[0]) == set(rows[1])
    assert "metrics.classification_at_0_5" not in rows[0]
    assert sorted(int(row["metrics.sample_count"]) for row in rows) == [0, 2]
    assert "classification.f1" in rows[0]
    # The CSV omits only the duplicate nested record; JSON retains it.
    assert isinstance(populated["metrics"]["classification_at_0_5"], dict)
    assert empty["metrics"]["classification_at_0_5"] is None
    json.dumps(dict(populated=populated, empty=empty), allow_nan=False)


def test_case_seed_is_identity_stable_and_leaves_global_generators_unchanged():
    from wildfire.cumulative_report import case_seed

    numpy_state = np.random.get_state()
    torch_state = torch.random.get_rng_state().clone()
    cases = [("event-a", "2024-08-01T00:00:00Z"),
             ("event-b", "2024-08-01T00:00:00Z"),
             ("event-a", "2024-08-01T01:00:00Z")]
    forward = {key: case_seed(7, *key) for key in cases}
    backward = {key: case_seed(7, *key) for key in reversed(cases)}
    assert forward == backward
    assert len(set(forward.values())) == 3
    assert all(isinstance(value, int) and value >= 0 for value in forward.values())
    assert case_seed(8, *cases[0]) != forward[cases[0]]
    after = np.random.get_state()
    assert after[0] == numpy_state[0]
    np.testing.assert_array_equal(after[1], numpy_state[1])
    assert after[2:] == numpy_state[2:]
    assert torch.equal(torch.random.get_rng_state(), torch_state)


def test_command_dispatch_returns_a_success_exit_status_instead_of_the_result_dictionary(monkeypatch):
    import sys
    import wildfire.__main__ as command

    original = sys.argv
    received = []

    def run():
        received.extend(sys.argv[1:])
        return {"status": "complete", "summary": [{"metrics": {"brier": .2}}]}

    monkeypatch.setattr(command, "import_module", lambda *args, **kwargs: SimpleNamespace(main=run))
    assert command.main(["evaluate-cumulative", "--hours", "6"]) is None
    assert received == ["--hours", "6"]
    assert sys.argv is original


def test_discovery_is_deterministic_and_does_not_include_last_or_roundtrip_files(tmp_path):
    from wildfire.cumulative_report import discover_checkpoints

    first = _checkpoint(tmp_path, "z-model")
    second = _checkpoint(tmp_path, "a-model", rate=.4)
    (first.parent / "last.pt").write_bytes(first.read_bytes())
    (first.parent / "roundtrip.pt").write_bytes(first.read_bytes())
    discovered = discover_checkpoints((tmp_path,), selection="all")
    assert discovered == sorted([first.resolve(), second.resolve()])
    # Repeated roots and explicit paths must not score the same identity twice.
    assert discover_checkpoints((tmp_path, tmp_path), explicit=(first,), selection="all") == discovered


def test_best_selection_without_registry_accepts_one_model_but_rejects_ambiguous_roots(tmp_path):
    from wildfire.cumulative_report import discover_checkpoints

    first = _checkpoint(tmp_path, "one-model")
    assert discover_checkpoints((tmp_path,), selection="best") == [first.resolve()]
    _checkpoint(tmp_path, "second-model", rate=.4)
    with pytest.raises(ValueError, match="registr|best|ambig"):
        discover_checkpoints((tmp_path,), selection="best")


def test_best_registry_hash_is_checked_before_using_the_selected_checkpoint(tmp_path):
    import hashlib
    from wildfire.cumulative_report import discover_checkpoints

    checkpoint = _checkpoint(tmp_path)
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    (tmp_path / "best_models.json").write_text(json.dumps({
        "fixture": dict(checkpoint=str(checkpoint), checkpoint_sha256=digest),
    }), encoding="utf-8")
    assert discover_checkpoints((tmp_path,), selection="best") == [checkpoint.resolve()]
    with checkpoint.open("ab") as stream:
        stream.write(b"deliberate checkpoint mutation")
    with pytest.raises(ValueError, match="hash"):
        discover_checkpoints((tmp_path,), selection="best")


def test_explicit_cutoffs_cannot_be_silently_truncated_by_a_case_limit():
    from wildfire.cumulative_report import EvaluationConfig

    with pytest.raises(ValueError, match="cutoff"):
        EvaluationConfig(cutoffs=("2024-08-01T00:00:00Z", "2024-08-01T06:00:00Z"),
                         max_cutoffs_per_event=1)


def test_held_out_events_require_exclusive_test_membership_in_all_bayesian_components():
    from wildfire.cumulative_report import _test_events

    outer = dict(splits={"shared": "test", "training-member": "test",
                         "mixed-rows": "test", "missing-member": "test"})
    first = dict(splits={"shared": ["test"], "training-member": "train",
                         "mixed-rows": ["train", "test"], "missing-member": "test"})
    second = dict(splits={"shared": "test", "training-member": "test", "mixed-rows": "test"})
    components = [SimpleNamespace(contract=first), SimpleNamespace(contract=second)]
    model = SimpleNamespace(contract=outer, predictor=SimpleNamespace(contract=outer, components=components))
    assert set(_test_events(model)) == {"shared"}


def test_score_case_preserves_unknown_reference_and_initial_burn_exclusions():
    from wildfire.cumulative_report import _score_case

    reference = _reference(6)
    prediction = _prediction(reference, 6, unavailable=((2, 4),))
    report, selected = _score_case(prediction, reference, 6, quantity="new_burn", threshold=.5)
    row = report["per_horizon"][0]
    assert row["metrics"]["sample_count"] == 60
    assert row["metrics"]["positive_sample_count"] == 2
    assert row["coverage"]["initially_burned_excluded_cells"] == 1
    assert len(selected["y"]) == len(selected["p"]) == 60
    assert np.count_nonzero(selected["y"]) == 2
    assert np.all(selected["p"] == .25)
    assert not reference["burned_area_valid"][0, 0, 0, 8]
    total, occupied = _score_case(prediction, reference, 6, quantity="burned", threshold=.5)
    assert total["per_horizon"][0]["metrics"]["sample_count"] == 62
    assert total["per_horizon"][0]["metrics"]["positive_sample_count"] == 3
    assert np.count_nonzero(occupied["p"] == 1) == 1


def _patch_cases(monkeypatch, module, reference):
    monkeypatch.setattr(module, "available_events", lambda **options: ["fixture-event"])
    monkeypatch.setattr(module, "available_cutoffs", lambda *args, **options: ["1970-01-01T02:46:40Z"])
    calls = []

    def load_case(model, event, cutoff, hours, data_root):
        assert event == "fixture-event"
        assert hours + 1 == len(reference["time_utc"])
        calls.append((str(model.checkpoint_path), event, cutoff, hours, str(data_root)))
        return reference

    monkeypatch.setattr(module, "_load_case", load_case)
    return calls


def test_case_loader_requests_only_the_exact_bounded_full_rectangle_interval(tmp_path, monkeypatch):
    import pandas as pd
    import wildfire.cumulative_report as module
    from wildfire.api import load_model

    model = load_model(_checkpoint(tmp_path / "models"))
    reference = _reference(6)
    calls = []

    class Dataset:
        closed = False

        def __len__(self):
            return 1

        def __getitem__(self, index):
            assert index == 0
            return reference

        def close(self):
            self.closed = True

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    dataset = Dataset()

    def data(root, **options):
        calls.append((root, options))
        return dataset

    monkeypatch.setattr(module, "load_data", data)
    loaded = module._load_case(model, "fixture-event", "1970-01-01T02:46:40Z", 6, tmp_path / "data")
    assert loaded is reference
    assert dataset.closed
    assert len(calls) == 1
    root, options = calls[0]
    assert Path(root) == tmp_path / "data"
    assert tuple(options["events"]) == ("fixture-event",)
    assert options["sequence_length"] == 7
    assert options.get("patch_size") is None
    assert options["daily_policy"] == "completed_day"
    start, end = options["time_range"]
    assert pd.Timestamp(start).timestamp() == 10_000
    assert pd.Timestamp(end).timestamp() == 31_600


@pytest.mark.parametrize("hours", [2, 6])
def test_saved_checkpoint_runner_uses_only_cutoff_inputs_and_exports_reports(tmp_path, monkeypatch, hours):
    import wildfire.cumulative_report as module
    from wildfire.api import load_model

    checkpoint = _checkpoint(tmp_path / "models")
    reference = _reference(hours)
    calls = _patch_cases(monkeypatch, module, reference)
    predictions = []

    def guarded_model(path, **options):
        model = load_model(path, **options)
        original = model.predict_cumulative

        def predict(sample, **controls):
            assert not set(sample) & {"arrival_hours", "arrival_valid", "newly_burned_area", "newly_burned_area_valid"}
            assert len(sample["time_utc"]) == 1
            assert int(sample["time_utc"][0]) == 10_000
            assert sample["features"].shape == (1, 1, 7, 9)
            assert sample["burned_area"].shape == (1, 1, 7, 9)
            assert int(sample["burned_area"].sum()) == 1
            assert controls["method"] == "recursive"
            assert controls["boundary"] == "zero"
            assert controls["missing_burned_area"] == "unburned"
            assert controls.get("environmental_forecast") is None
            result = original(sample, **controls)
            predictions.append(result)
            return result

        model.predict_cumulative = predict
        return model

    monkeypatch.setattr(module, "load_model", guarded_model)
    output = tmp_path / "report"
    config = module.EvaluationConfig(
        model_roots=(), checkpoints=(checkpoint,), data_root=_data_root(tmp_path), output_dir=output,
        hours=hours, n_samples=32, trajectory_batch_size=16, seed=4,
        events=("fixture-event",), split="all", save_predictions=True, plots=False,
    )
    result = module.run_evaluation(config)
    assert calls and len(predictions) == 1
    assert result
    assert predictions[0].at(hours=hours).probability.shape == (1, 1, 7, 9)
    assert predictions[0].metadata["boundary"] == "zero"
    assert not reference["burned_area_valid"][0, 0, 0, 8]
    for name in ("report.json", "protocol.json"):
        payload = json.loads((output / name).read_text(encoding="utf-8"))
        assert payload
        json.dumps(payload, allow_nan=False)
    assert (output / "report.md").stat().st_size > 0
    for name in ("summary.csv", "per_event.csv", "per_cutoff.csv", "calibration.csv"):
        assert _csv(output / name)
    # Preserve the concrete requested duration in machine-readable outputs.
    summaries = _csv(output / "summary.csv")
    assert all(float(row["hours"]) == hours for row in summaries)
    assert list(output.rglob("*.npz"))


def test_every_model_is_compared_on_the_same_intersection_and_keeps_native_coverage(tmp_path, monkeypatch):
    import wildfire.cumulative_report as module
    from wildfire.api import load_model

    models = tmp_path / "models"
    _checkpoint(models, "a-model", rate=.2)
    _checkpoint(models, "b-model", rate=.4)
    reference = _reference(6)
    _patch_cases(monkeypatch, module, reference)

    def masked_model(path, **options):
        model = load_model(path, **options)
        excluded = ((2, 4),) if Path(path).parent.name == "a-model" else ((2, 5), (2, 6))
        model.predict_cumulative = lambda sample, **controls: _prediction(reference, 6, unavailable=excluded)
        return model

    monkeypatch.setattr(module, "load_model", masked_model)
    output = tmp_path / "report"
    module.run_evaluation(module.EvaluationConfig(
        model_roots=(models,), output_dir=output, data_root=_data_root(tmp_path),
        hours=6, n_samples=32, events=("fixture-event",), split="all", plots=False,
    ))
    rows = _csv(output / "summary.csv")
    for quantity, expected in (("new_burn", [58, 58, 59, 60]), ("burned", [60, 60, 61, 62])):
        selected = [row for row in rows if row["quantity"] == quantity]
        count = lambda row: int(row.get("sample_count", row.get("metrics.sample_count")))
        assert sorted(count(row) for row in selected) == expected
    common = [row for row in rows if row["quantity"] == "new_burn" and row["cohort"] == "shared_models"]
    assert len(common) == 2
    for row in common:
        value = row.get("brier", row.get("metrics.brier"))
        assert float(value) == pytest.approx((2 * .75**2 + 56 * .25**2) / 58)
    # Reference masks remain original rather than inheriting the simulation fill.
    assert not reference["burned_area_valid"][0, 0, 0, 8]


def test_plan_only_records_the_model_and_exact_cases_without_loading_rasters(tmp_path, monkeypatch):
    import wildfire.cumulative_report as module

    checkpoint = _checkpoint(tmp_path / "models")
    reference = _reference(6)
    calls = _patch_cases(monkeypatch, module, reference)
    output = tmp_path / "plan"
    result = module.run_evaluation(module.EvaluationConfig(
        model_roots=(), checkpoints=(checkpoint,), data_root=_data_root(tmp_path),
        output_dir=output, events=("fixture-event",), split="all", plan_only=True,
    ))
    assert result["status"] == "planned"
    assert result["summary"] == []
    assert not calls
    case = result["protocol"]["cases"][0]
    assert case["cutoff"] == "1970-01-01T02:46:40Z"
    assert case["endpoint"] == "1970-01-01T08:46:40Z"
    assert result["protocol"]["model_count"] == 1
    assert result["protocol"]["model_case_count"] == 1
    assert len(result["models"][0]["sha256"]) == 64
    assert (output / "protocol.json").is_file()
    assert (output / "report.json").is_file()


def test_failure_after_one_case_preserves_partial_outputs_and_marks_progress_failed(tmp_path, monkeypatch):
    import pandas as pd
    import wildfire.cumulative_report as module
    from wildfire.api import load_model

    checkpoint = _checkpoint(tmp_path / "models")
    starts = ["1970-01-01T02:46:40Z", "1970-01-01T08:46:40Z"]
    monkeypatch.setattr(module, "available_events", lambda **options: ["fixture-event"])
    monkeypatch.setattr(module, "available_cutoffs", lambda *args, **options: starts)
    monkeypatch.setattr(module, "_load_case", lambda model, event, cutoff, hours, data_root:
                        _reference(hours, int(pd.Timestamp(cutoff).timestamp())))

    def failing_model(path, **options):
        model = load_model(path, **options)

        def predict(sample, **controls):
            cutoff = int(sample["time_utc"][0])
            if cutoff != 10_000:
                raise RuntimeError("fixture abort after first complete cutoff")
            return _prediction(_reference(6, cutoff), 6)

        model.predict_cumulative = predict
        return model

    monkeypatch.setattr(module, "load_model", failing_model)
    output = tmp_path / "partial"
    config = module.EvaluationConfig(
        model_roots=(), checkpoints=(checkpoint,), data_root=_data_root(tmp_path),
        output_dir=output, events=("fixture-event",), split="all", stride_hours=1, plots=False,
    )
    with pytest.raises(RuntimeError, match="fixture abort"):
        module.run_evaluation(config)
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    progress = json.loads((output / "progress.json").read_text(encoding="utf-8"))
    assert report["status"] == progress["status"] == "failed"
    assert report["completed_cases"] == progress["completed_cases"] == 1
    assert report["protocol"]["case_count"] == 2
    assert report["summary"] == []
    assert report["failures"][0]["case"]["cutoff"] == starts[1]
    assert len(_csv(output / "per_cutoff.csv")) == 4
    assert list((output / "_entries").glob("*.bin"))


def test_failed_checkpoint_is_recorded_and_existing_output_is_preserved(tmp_path):
    import wildfire.cumulative_report as module

    checkpoint = tmp_path / "bad" / "checkpoint.pt"
    checkpoint.parent.mkdir()
    checkpoint.write_bytes(b"a checkpoint deliberately corrupted for this test")
    output = tmp_path / "failed"
    config = module.EvaluationConfig(model_roots=(), checkpoints=(checkpoint,), output_dir=output,
                                     data_root=tmp_path / "data", split="all")
    with pytest.raises(ValueError):
        module.run_evaluation(config)
    saved = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert "fail" in json.dumps(saved).lower()
    original = (output / "report.json").read_bytes()
    with pytest.raises((FileExistsError, ValueError), match="exist|empty|overwrite|preserv"):
        module.run_evaluation(config)
    assert (output / "report.json").read_bytes() == original


def _forest_checkpoint(directory, *, cache_digest=None):
    from wildfire.models import PatchRandomForest

    environment = np.zeros((4, 1, 3, 3), dtype=np.float32)
    burned = np.zeros_like(environment)
    burned[:, 0, 1, 0] = 1
    environment[2:] = 1
    model = PatchRandomForest(kernel_size=3, n_estimators=2, max_depth=2,
                              n_jobs=1, random_state=11)
    metadata = dict(normalization_mean=[0.], normalization_std=[1.])
    if cache_digest is not None:
        metadata['cache_metadata_sha256'] = cache_digest
    model.fit(environment, burned, np.asarray([0, 1, 0, 1]), np.ones(4),
              channel_names=('fixture.temperature',))
    path = directory / 'forests' / 'rf3_depth2.joblib'
    path.parent.mkdir(parents=True, exist_ok=True)
    model.save(path, metadata=metadata)
    return path


def test_all_and_best_discovery_include_forests_and_authenticate_registry_hashes(tmp_path):
    from wildfire.cumulative_report import discover_checkpoints, _sha256

    tensor = _checkpoint(tmp_path, 'tensor')
    forest = _forest_checkpoint(tmp_path)
    assert discover_checkpoints((tmp_path, tmp_path), (forest,)) == sorted([tensor.resolve(), forest.resolve()])
    registry = dict(tensor=dict(checkpoint=str(tensor), checkpoint_sha256=_sha256(tensor)),
                    forest=dict(checkpoint=str(forest), checkpoint_sha256=_sha256(forest)))
    (tmp_path / 'best_models.json').write_text(json.dumps(registry))
    assert discover_checkpoints((tmp_path,), selection='best') == sorted([tensor.resolve(), forest.resolve()])
    with forest.open('ab') as stream:
        stream.write(b'deliberate registry mismatch')
    with pytest.raises(ValueError, match='hash'):
        discover_checkpoints((tmp_path,), selection='best')


def test_matching_cache_partition_enables_mixed_forest_tensor_report_with_plots(tmp_path, monkeypatch):
    import wildfire.cumulative_report as module

    models = tmp_path / 'models'
    tensor = _checkpoint(models, 'tensor')
    saved = torch.load(tensor, map_location='cpu', weights_only=True)
    saved['contract'].update(cache_metadata_sha256='fixture-saved-cache')
    torch.save(saved, tensor)
    forest = _forest_checkpoint(models, cache_digest='fixture-saved-cache')
    _patch_cases(monkeypatch, module, _reference(2))
    output = tmp_path / 'mixed_report'
    result = module.run_evaluation(module.EvaluationConfig(
        model_roots=(models,), data_root=_data_root(tmp_path), output_dir=output,
        hours=2, n_samples=8, trajectory_batch_size=8, events=('fixture-event',),
        split='test', save_predictions=True,
    ))
    assert result['status'] == 'complete'
    assert len(result['models']) == 2
    record = next(row for row in result['models'] if row['architecture'] == 'PatchRandomForest')
    assert record['inference_device'] == 'cpu'
    provenance = record['training_partition_provenance']
    assert provenance['source_checkpoint'] == str(tensor)
    assert provenance['source_sha256'] == module._sha256(tensor)
    assert provenance['cache_metadata_sha256'] == 'fixture-saved-cache'
    assert record['all_selected_events_exclusively_test']
    assert record['event_split_membership'] == {'fixture-event': ['test']}
    assert result['protocol']['plots'] is True
    assert result['plots']['model_count'] == 2
    assert (output / 'plots' / 'manifest.json').is_file()
    assert 'new_burn_curves' in result['plots']['figures']
    assert not (output / '_entries').exists()
    for figure in result['plots']['figures'].values():
        for asset in figure['outputs'].values():
            assert (output / asset['path']).is_file()
            assert module._sha256(output / asset['path']) == asset['sha256']
    markdown = (output / 'report.md').read_text()
    for label in ('Floored KL', 'TV', 'Hellinger', 'JS divergence', 'JS distance',
                  'Bhattacharyya', 'Wasserstein-1', 'Wasserstein-2', 'native:',
                  'shared_models:', 'plots/new_burn_metrics.png'):
        assert label in markdown
    shared = [row for row in result['summary'] if row['cohort'] == 'shared_models' and row['quantity'] == 'new_burn']
    assert len({row['metrics']['sample_count'] for row in shared}) == 1
    arrays = np.load(output / 'predictions' / '000000.npz')
    assert arrays['probability'].shape == (2, 1, 1, 7, 9)
    assert str(forest) in record['path']


def test_forest_without_authenticated_partition_requires_explicit_retrospective_scope(tmp_path, monkeypatch):
    import wildfire.cumulative_report as module

    forest = _forest_checkpoint(tmp_path / 'models')
    calls = _patch_cases(monkeypatch, module, _reference(6))
    config = dict(model_roots=(), checkpoints=(forest,), data_root=_data_root(tmp_path),
                  events=('fixture-event',), plan_only=True)
    with pytest.raises(ValueError, match='partition|retrospective'):
        module.run_evaluation(module.EvaluationConfig(**config, output_dir=tmp_path / 'test_plan'))
    result = module.run_evaluation(module.EvaluationConfig(**config, split='all', output_dir=tmp_path / 'all_plan'))
    assert result['status'] == 'planned'
    assert result['models'][0]['training_partition_provenance']['policy'] == 'unavailable'
    assert not result['models'][0]['all_selected_events_exclusively_test']
    assert not calls
    assert not (tmp_path / 'all_plan' / 'plots').exists()


def test_conflicting_partitions_with_same_saved_cache_digest_are_rejected(tmp_path):
    from wildfire.api import load_model
    from wildfire.cumulative_report import _forest_partitions

    paths = [_checkpoint(tmp_path, 'tensor-a'), _checkpoint(tmp_path, 'tensor-b')]
    for index, path in enumerate(paths):
        saved = torch.load(path, map_location='cpu', weights_only=True)
        saved['contract'].update(cache_metadata_sha256='fixture-saved-cache',
                                 splits={'fixture-event': 'test' if index == 0 else 'train'})
        torch.save(saved, path)
    paths.append(_forest_checkpoint(tmp_path, cache_digest='fixture-saved-cache'))
    # The contradictory witness is present but omitted from model selection.
    selected = [paths[0], paths[2]]
    models = [load_model(path) for path in selected]
    with pytest.raises(ValueError, match='Conflicting'):
        _forest_partitions(models, selected, (tmp_path,))


def test_no_plots_cli_option_preserves_explicit_simulation_settings(tmp_path, monkeypatch):
    import wildfire.cumulative_report as module

    received = []
    monkeypatch.setattr(module, 'run_evaluation', lambda config: received.append(config))
    module.main(['--checkpoint', str(tmp_path / 'forest.joblib'), '--hours', '8',
                 '--n-samples', '256', '--no-plots', '--split', 'all'])
    assert len(received) == 1
    assert received[0].hours == 8
    assert received[0].n_samples == 256
    assert received[0].plots is False
    assert received[0].model_roots == ()
