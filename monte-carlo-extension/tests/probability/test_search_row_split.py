"""Kernel searches retain row-split authority and report its scientific scope."""

import json

import numpy as np
import pytest
import torch

from wildfire.search import Search as kernel_search
from wildfire.search import ScheduledSearch as kernel_search_scheduled
from wildfire.search import MixedSearch as kernel_search_mixed
from wildfire.search import MultiscaleSearch as kernel_search_multiscale
from wildfire.cache import CachedSplit
from wildfire.cache import fit_normalization
from wildfire.cache import load_split
from wildfire.cache import validate_partition_disjointness
from wildfire.cohort import cohort_summary
from wildfire.cohort import common_indices
from wildfire.cohort import crop_split
from wildfire.cohort import native_indices
from wildfire.inference import load_single_trained_model
from wildfire.train import fit_global_rate
from wildfire.metrics import fit_categorical_balance
from wildfire.metrics import brier


SEARCHES = (kernel_search, kernel_search_scheduled, kernel_search_mixed, kernel_search_multiscale)


@pytest.fixture(autouse=True)
def _one_thread():
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(previous)


def _data(event_index, offset=0):
    count = 12
    burned = np.zeros((count, 1, 9, 9), dtype=np.float32)
    burned[:, 0, 3, 4] = 1
    rng = np.random.default_rng(79 + offset)
    return CachedSplit(
        environment=rng.normal(size=(count, 2, 9, 9)).astype(np.float32),
        burned=burned, target=(np.arange(count) % 3 == 0).astype(np.float32),
        weight=np.where(np.arange(count) % 3 == 0, 1, 4).astype(np.float64),
        event_index=np.full(count, event_index, dtype=np.int64),
        time_utc=np.full(count, 3600, dtype=np.int64),
        row=np.arange(count, dtype=np.int32) + offset,
        col=np.ones(count, dtype=np.int32),
    )


@pytest.fixture
def row_cache(tmp_path):
    directory = tmp_path / "cache"
    directory.mkdir()
    metadata = dict(
        dt_hours=1.0, kernel_size=9,
        channels=["weather.temperature_2m", "terrain.slope_degrees"],
        event_ids=["development_fire", "test_fire"], split_unit="cell_hour",
        splits={"development_fire": ["train", "validation"], "test_fire": ["test"]},
        original_splits={"development_fire": "train", "test_fire": "test"},
        data_root=str(directory), source_files=[], smoke_verification_only=True,
        generalization_scope="Within-fire cell-hour interpolation; overlapping spatial contexts and fire histories across train/validation",
    )
    (directory / "metadata.json").write_text(json.dumps(metadata))
    for name, data in (("train", _data(0)), ("validation", _data(0, 100)), ("test", _data(1))):
        np.savez_compressed(directory / f"{name}.npz", **vars(data))
    return directory, metadata


def _setup(search, output, directory):
    options = {} if search is kernel_search else dict(
        learning_rates=(.001,), schedules=("constant",), warmup_epochs=0, restart_period=2,
    )
    return search.setup(output, directory, 1, 1, 7, forest_trees=1, **options)


@pytest.mark.parametrize("search", SEARCHES)
def test_each_search_defaults_to_fresh_weighted_cache_and_output(search):
    args = search.parser().parse_args(["train"])
    assert args.cache == search.RUNS / "20261009_weighted_stratified_split/prepared_all"
    assert args.output.name.endswith("_weighted_stratified_categorical_balanced")
    assert search.DEFAULT_SMOKE_OUTPUT.name.endswith("_weighted_stratified_categorical_balanced")


@pytest.mark.parametrize("search", SEARCHES)
def test_each_protocol_and_checkpoint_contract_preserves_split_semantics(row_cache, tmp_path, search):
    directory, metadata = row_cache
    protocol = _setup(search, tmp_path / search.__name__.rsplit(".", 1)[-1], directory)
    assert protocol["split_unit"] == "cell_hour"
    assert protocol["original_splits"] == metadata["original_splits"]
    assert protocol["generalization_scope"] == metadata["generalization_scope"]
    assert "split unit: cell_hour" in protocol["training"]
    assert "search.py" in protocol["training_source_sha256"]
    candidate = next(c for c in protocol["candidates"] if c["family"] == "mlp")
    contract = search.make_contract(candidate, metadata, protocol)
    for key in ("split_unit", "original_splits", "generalization_scope"):
        assert contract[key] == protocol[key]
    assert contract["splits"] == metadata["splits"]
    description = kernel_search.split_description(protocol)
    assert "within-fire cell-hour interpolation" in description
    assert "test partition retains its original whole fires" in description
    assert "distinct whole-fire partitions" not in description
    search.verify_protocol(protocol, directory)


@pytest.mark.parametrize("search", SEARCHES)
def test_each_search_rejects_shared_training_validation_row_before_fitting(row_cache, tmp_path, search):
    directory, _ = row_cache
    np.savez_compressed(directory / "validation.npz", **vars(_data(0)))
    args = search.parser().parse_args([
        "train", "--cache", str(directory), "--output", str(tmp_path / "output"),
        "--epochs", "1", "--finalist-epochs", "1", "--threads", "1", "--device", "cpu",
    ] + ([] if search is kernel_search else ["--warmup-epochs", "0"]))
    with pytest.raises(ValueError, match="Shared cell-hour identities"):
        search.train_search(args)
    assert not (args.output / "candidates").exists()


def test_legacy_split_description_retains_whole_fire_claim():
    assert kernel_search.split_description({}) == "Training, validation, and test use distinct whole-fire partitions."


def test_one_epoch_search_checkpoints_and_report_are_truthful_about_shared_fires(row_cache, tmp_path):
    directory, metadata = row_cache
    output = tmp_path / "search"
    protocol = _setup(kernel_search, output, directory)
    partitions = {name: load_split(directory, name, metadata) for name in ("train", "validation", "test")}
    separation = validate_partition_disjointness(partitions, metadata)
    assert not separation["disjoint_contributing_fire_sets"]
    assert separation["disjoint_cell_hour_identities"]
    assert separation["test_fires_disjoint_from_training_validation"]
    training, validation = (crop_split(partitions[name], 3) for name in ("train", "validation"))
    mean, std = fit_normalization(training)
    baseline = fit_global_rate(training)
    device = torch.device("cpu")
    selected = []
    for family in kernel_search.NEURAL_FAMILIES:
        candidate = dict(next(c for c in protocol["candidates"]
                              if c["kernel_size"] == 3 and c["family"] == family))
        candidate.update(hidden_channels=4, depth=1, dropout=0)
        tensors = kernel_search.tensor_data(training, mean, std, family, device)
        validation_tensors = kernel_search.tensor_data(validation, mean, std, family, device)
        summary = kernel_search.fit_candidate(
            candidate, training, validation, tensors, validation_tensors, mean, std,
            baseline, metadata, protocol, output, device, 1,
        )
        assert summary["epochs_completed"] == 1
        model = load_single_trained_model(summary["checkpoint"])
        assert model.contract["split_unit"] == "cell_hour"
        assert model.contract["original_splits"] == metadata["original_splits"]
        selected.append(summary)
    metrics = {}
    for name, data in partitions.items():
        common = common_indices(data)
        models = {}
        for summary in selected:
            model = load_single_trained_model(summary["checkpoint"])
            cropped = crop_split(data, 3)
            with torch.no_grad():
                p = model(torch.from_numpy(cropped.burned), torch.from_numpy(cropped.environment),
                          channel_names=metadata["channels"]).probability[:, 0, 1, 1].numpy()
            thresholds = kernel_search.thresholds(data, p, common)
            metric = kernel_search.probability_metrics_with_all(
                data.target, p, data.weight, cropped.neighbor_count, thresholds=thresholds)
            models[summary["candidate"]["id"]] = dict(native=metric, common=metric)
        metrics[name] = dict(
            common_cohort=cohort_summary(data, common, 3),
            native_cohorts={str(k): cohort_summary(data, native_indices(data, k), k)
                            for k in kernel_search.SIZES}, models=models,
        )
    best = min(selected, key=lambda s: s["validation_common_brier"])
    kernel_search.report(output, protocol, selected, best, metrics)
    report = (output / "report.md").read_text()
    assert "Validation can share fires" in report
    assert "within-fire cell-hour interpolation" in report
    assert "test partition retains its original whole fires" in report
    assert "using distinct whole-fire partitions" not in report
    diagnostics = json.loads((output / "learning_diagnostics.json").read_text())
    assert all("within-fire cell-hour interpolation" in record["interpretation"]
               for record in diagnostics.values())


@pytest.fixture
def categorical_cache(row_cache):
    directory, metadata = row_cache
    source = "biome.biome_class"
    metadata.update(
        channels=["weather.temperature_2m", f"{source}=1", f"{source}=8"],
        source_channels=["weather.temperature_2m", source], categorical_encoding="one_hot",
        categorical_classes={source: [1, 8]}, channel_groups={"weather.temperature_2m": [0], source: [1, 2]},
        channel_info=[dict(name="weather.temperature_2m", source_channel="weather.temperature_2m", encoding="continuous"),
                      dict(name=f"{source}=1", source_channel=source, encoding="one_hot", class_code=1),
                      dict(name=f"{source}=8", source_channel=source, encoding="one_hot", class_code=8)],
    )
    (directory / "metadata.json").write_text(json.dumps(metadata))
    for name, original in (("train", _data(0)), ("validation", _data(0, 100)), ("test", _data(1))):
        arrays = vars(original).copy()
        environment = np.zeros((len(original), 3, 9, 9), dtype=np.float32)
        environment[:, 0] = original.environment[:, 0]
        environment[:, 1] = 1
        environment[-1, 1] = 0
        environment[-1, 2] = 1
        arrays["environment"] = environment
        arrays["target"] = original.target.copy()
        arrays["target"][-1] = 1
        arrays["weight"] = original.weight.copy()
        arrays["weight"][-1] = 1
        np.savez_compressed(directory / f"{name}.npz", **arrays)
    return directory, metadata


@pytest.mark.parametrize("search", SEARCHES)
def test_categorical_tensor_weights_keep_population_data_and_raw_indicators(categorical_cache, tmp_path, search):
    directory, metadata = categorical_cache
    training = crop_split(load_split(directory, "train", metadata), 3)
    before = training.weight.copy()
    mean, std = fit_normalization(training, metadata=metadata)
    np.testing.assert_array_equal(mean[1:], [0, 0])
    np.testing.assert_array_equal(std[1:], [1, 1])
    effective, audit = fit_categorical_balance(training, metadata)
    tensors = search.tensor_data(training, mean, std, "mlp", torch.device("cpu"),
                                 optimization_weight=effective, categorical_balance=audit)
    np.testing.assert_array_equal(training.weight, before)
    np.testing.assert_array_equal(tensors.weight, before)
    np.testing.assert_array_equal(tensors.loss_weight.numpy(), (effective / effective.mean()).astype(np.float32))
    assert effective[-1] / before[-1] > effective[0] / before[0]
    np.testing.assert_array_equal(tensors.features[:, 1:].numpy(), training.environment[:, 1:].mean((2, 3)))
    disabled, _ = fit_categorical_balance(training, metadata, mode="none")
    np.testing.assert_array_equal(disabled, before)


@pytest.mark.parametrize("search", SEARCHES)
def test_active_categorical_one_epoch_fit_scores_population_and_guards_resume(categorical_cache, tmp_path, search):
    directory, metadata = categorical_cache
    archive_before = {name: (directory / f"{name}.npz").read_bytes() for name in ("train", "validation", "test")}
    output = tmp_path / "active_balance"
    protocol = _setup(search, output, directory)
    training, validation = (crop_split(load_split(directory, name, metadata), 3) for name in ("train", "validation"))
    mean, std = fit_normalization(training, metadata=metadata)
    candidate = dict(next(c for c in protocol["candidates"] if c["family"] == "mlp" and c["kernel_size"] == 3))
    candidate.update(hidden_channels=4, depth=1, dropout=0)
    device = torch.device("cpu")
    tensors = search.tensor_data(training, mean, std, "mlp", device)
    val_tensors = search.tensor_data(validation, mean, std, "mlp", device)
    arguments = (candidate, training, validation, tensors, val_tensors, mean, std,
                 fit_global_rate(training), metadata, protocol, output, device, 1)
    summary = search.fit_candidate(*arguments)
    saved = torch.load(summary["checkpoint"], weights_only=True)
    audit = saved["contract"]["categorical_balance"]
    assert audit["sources"][0]["classes"][1]["observed_in_training"]
    assert audit["uses_targets"] is False
    assert audit["optimization_weights_sha256"] != audit["population_weights_sha256"]
    assert saved["train_weighted_prevalence"] == pytest.approx(np.dot(training.weight, training.target) / training.weight.sum())
    assert saved["optimization_weighted_prevalence"] == pytest.approx(
        np.dot(tensors.optimization_weight, training.target) / tensors.optimization_weight.sum())
    loaded = search.load_trained_model(summary["checkpoint"])
    train_predictions = search.probabilities(loaded.model, tensors)
    val_predictions = search.probabilities(loaded.model, val_tensors)
    history_path = output / "candidates" / candidate["id"] / "history.json"
    history = json.loads(history_path.read_text())
    assert history[0]["train_brier"] == pytest.approx(brier(training.target, train_predictions, training.weight))
    assert history[0]["optimization_train_brier"] == pytest.approx(
        brier(training.target, train_predictions, tensors.optimization_weight))
    assert summary["validation_common_brier"] == pytest.approx(brier(validation.target, val_predictions, validation.weight))
    assert summary["categorical_balance"] == audit
    kernel_search.verify_balance_reports(output, protocol, [summary])
    kernel_search.verify_checkpoint_balance(summary)
    checkpoint_path = output / "candidates" / candidate["id"] / "checkpoint.pt"
    checkpoint_bytes = checkpoint_path.read_bytes()
    changed_checkpoint = torch.load(checkpoint_path, weights_only=True)
    changed_checkpoint["contract"]["categorical_balance"]["factor_max"] += 1
    torch.save(changed_checkpoint, checkpoint_path)
    with pytest.raises(ValueError, match="Categorical balance audit"):
        kernel_search.verify_checkpoint_balance(summary)
    checkpoint_path.write_bytes(checkpoint_bytes)
    report_path = output / "categorical_balance" / "k3.json"
    original_report = report_path.read_text()
    altered = json.loads(original_report)
    altered["factor_max"] += 1
    report_path.write_text(json.dumps(altered))
    with pytest.raises(ValueError, match="Categorical balance report"):
        kernel_search.verify_balance_reports(output, protocol, [summary])
    with pytest.raises(ValueError, match="Categorical balance"):
        search.fit_candidate(*arguments)
    report_path.write_text(original_report)
    last_path = output / "candidates" / candidate["id"] / "last.pt"
    state = torch.load(last_path, weights_only=True)
    state["categorical_balance"]["factor_max"] += 1
    torch.save(state, last_path)
    with pytest.raises(ValueError, match="Resume categorical balancing"):
        search.fit_candidate(*arguments)
    for name, expected in archive_before.items():
        assert (directory / f"{name}.npz").read_bytes() == expected


@pytest.mark.parametrize("search", SEARCHES)
def test_each_forest_path_fits_optimization_weights_and_retains_population_selection(
    categorical_cache, tmp_path, monkeypatch, search,
):
    directory, metadata = categorical_cache
    output = tmp_path / "forest_balance"
    args = search.parser().parse_args([
        "forests", "--cache", str(directory), "--output", str(output), "--device", "cpu",
        "--epochs", "1", "--finalist-epochs", "1", "--forest-trees", "1", "--threads", "1",
    ] + ([] if search is kernel_search else ["--warmup-epochs", "0"]))
    received = []
    original_fit = search.PatchRandomForest.fit

    def capture_fit(model, environment, burned, target, weight, **kwargs):
        received.append((model.kernel_size, np.asarray(weight).copy()))
        return original_fit(model, environment, burned, target, weight, **kwargs)

    monkeypatch.setattr(search.PatchRandomForest, "fit", capture_fit)
    search.forest_search(args)
    records = json.loads((output / "forest_selection.json").read_text())
    protocol = json.loads((output / "protocol.json").read_text())
    kernel_search.verify_balance_reports(output, protocol, records)
    assert len(received) == len(records) == 6
    for kernel, actual in received:
        data = crop_split(load_split(directory, "train", metadata), kernel)
        expected, _ = fit_categorical_balance(data, metadata)
        np.testing.assert_array_equal(actual, expected)
        assert not np.array_equal(actual, data.weight)
    for record in records:
        kernel_search.verify_checkpoint_balance(record)
        model = search.PatchRandomForest.load(record["checkpoint"])
        assert model.metadata["categorical_balance"] == record["categorical_balance"]
        assert model.contract["class_rebalancing"] == "none"
        data = crop_split(load_split(directory, "validation", metadata), record["kernel_size"])
        mean = np.asarray(model.metadata["normalization_mean"], dtype=np.float32)
        std = np.asarray(model.metadata["normalization_std"], dtype=np.float32)
        np.testing.assert_array_equal(mean[1:], [0, 0])
        np.testing.assert_array_equal(std[1:], [1, 1])
        predictions = model.predict_probability((data.environment - mean[None, :, None, None]) / std[None, :, None, None],
                                              data.burned, channel_names=metadata["channels"])
        assert record["validation_common_brier"] == pytest.approx(brier(data.target, predictions, data.weight))
    report_path = output / "categorical_balance" / "k3.json"
    report = json.loads(report_path.read_text())
    report["optimization_weights_sha256"] = "0" * 64
    report_path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="Categorical balance report"):
        search.forest_search(args)


@pytest.mark.parametrize("search", SEARCHES)
def test_shared_cli_balance_settings_are_bound_to_resume(categorical_cache, tmp_path, search):
    directory, _ = categorical_cache
    args = search.parser().parse_args([
        "train", "--categorical-balance", "none", "--categorical-balance-min-frequency", ".02",
        "--categorical-balance-max-factor", "3",
    ])
    settings = kernel_search.balance_settings_from_args(args)
    assert settings == dict(mode="none", min_frequency=.02, max_factor=3., chunk_size=512)
    output = tmp_path / "bound_settings"
    _setup(search, output, directory)
    options = {} if search is kernel_search else dict(
        learning_rates=(.001,), schedules=("constant",), warmup_epochs=0, restart_period=2)
    with pytest.raises(ValueError, match="categorical_balance_settings"):
        search.setup(output, directory, 1, 1, 7, forest_trees=1, balance_settings=settings, **options)


@pytest.mark.parametrize("search", SEARCHES)
def test_each_new_checkpoint_rejects_standardized_one_hot_inputs(categorical_cache, tmp_path, search):
    directory, metadata = categorical_cache
    output = tmp_path / "invalid_categorical_normalization"
    protocol = _setup(search, output, directory)
    training, validation = (crop_split(load_split(directory, name, metadata), 3) for name in ("train", "validation"))
    mean, std = fit_normalization(training)
    assert np.any(mean[1:] != 0) and np.any(std[1:] != 1)
    candidate = next(c for c in protocol["candidates"] if c["family"] == "mlp" and c["kernel_size"] == 3)
    device = torch.device("cpu")
    tensors = search.tensor_data(training, mean, std, "mlp", device)
    validation_tensors = search.tensor_data(validation, mean, std, "mlp", device)
    with pytest.raises(ValueError, match="one-hot normalization must retain raw 0/1"):
        search.fit_candidate(candidate, training, validation, tensors, validation_tensors, mean, std,
                             fit_global_rate(training), metadata, protocol, output, device, 1)
    assert not (output / "candidates").exists()
