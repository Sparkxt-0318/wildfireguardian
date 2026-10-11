"""Independent semantics for wider environmental and burned-cell kernels."""

from copy import deepcopy
import hashlib
import json

from affine import Affine
import numpy as np
import pandas as pd
import pytest
import torch

from wildfire.data import WildfireSequenceDataset
from wildfire.examples import CHANNELS
from wildfire.prepare import filter_contact
from wildfire.evaluate import centered_slice
from wildfire.evaluate import common_selection
from wildfire.evaluate import evaluate_runs
from wildfire.evaluate import frozen_predictions
from wildfire.inference import load_single_trained_model
from wildfire.models import EnvironmentConditionedConvolution
from wildfire.prepare import prepare_event
from wildfire.prepare import resolve_channel_schema
from tests.probability.test_training import _write_raster
from wildfire.train import CachedSplit
from wildfire.train import center_probability
from wildfire.train import fit_global_rate
from wildfire.train import load_split


BIOME_SOURCE = "biome.biome_class"
SOURCE_CHANNELS = tuple(CHANNELS) + (BIOME_SOURCE,)
BIOME_CLASSES = {BIOME_SOURCE: list(range(1, 15))}
ENCODED_CHANNELS = tuple(CHANNELS) + tuple(f"{BIOME_SOURCE}={code}" for code in range(1, 15))


@pytest.fixture
def wider_training_bundle(tmp_path):
    """Five exact hourly snapshots on a rectangle large enough for 9x9."""
    height, width = 13, 15
    transform = Affine(375, 0, 1000000, 0, -375, 2000000)
    times = pd.date_range("2022-03-04T02:00:00Z", periods=5, freq="h")
    event = dict(
        id="KR_WIDER_TEST", name="Independent wider-kernel fixture", country="KR", year=2022,
        epsg=5179, height=height, width=width, transform=list(transform)[:6],
        start_utc=times[0].isoformat(), end_utc=times[-1].isoformat(),
        t0_utc="2022-03-04T02:12:00+00:00",
        arrival_path="regions/KR_WIDER_TEST/arrival_time_hours.tif",
    )
    region = tmp_path / "regions" / event["id"]
    arrival = np.full((height, width), 3.1, dtype=np.float32)
    arrival[2, 7] = -1
    arrival[6, 7] = 0.5
    arrival[8, 10] = 1.4
    arrival[6, 11] = 4.9
    _write_raster(region / "arrival_time_hours.tif", arrival, transform)
    _write_raster(region / "kriging_std_hours.tif", np.ones((height, width)), transform)
    weather = {}
    grid = np.indices((height, width)).sum(axis=0)
    for index, name in enumerate(CHANNELS):
        category, variable = name.split(".", 1)
        if category == "weather":
            values = np.stack([100 + 10 * index + hour + grid for hour in range(5)])
            weather[variable] = {}
        else:
            values = 10 + index + grid
        _write_raster(region / category / f"{variable}_375m.tif", values, transform)
    _write_raster(region / "biome" / "biome_class_375m.tif", np.array([4, 5, 14])[grid % 3], transform)
    (tmp_path / "biome_classes.json").write_text(json.dumps({
        "classes": [{"code": code, "name": f"Fixture biome {code}"} for code in range(1, 15)],
    }))
    (region / "weather" / "ecmwf_ifs_complete.json").write_text(json.dumps({"variables": weather}))
    pd.DataFrame({"band": np.arange(1, 6), "time_utc": times.strftime("%Y-%m-%dT%H:%M:%SZ")}).to_csv(
        region / "weather" / "ecmwf_ifs_bands.csv", index=False,
    )
    (tmp_path / "events.json").write_text(json.dumps([event]))
    return tmp_path, event


def _prepare(root, event, kernel_size):
    return prepare_event(
        root, event, 0, np.random.default_rng(7), 10000, 10000, chunk_hours=2,
        source_channels=SOURCE_CHANNELS, categorical_classes=BIOME_CLASSES,
        channel_names=ENCODED_CHANNELS, kernel_size=kernel_size,
    )


def _loader_census(sample, kernel_size):
    """Enumerate the target definition directly, independently of sampling."""
    radius = kernel_size // 2
    burned = sample["burned_area"].numpy()
    label_valid = sample["burned_area_valid"].numpy()
    environmental = sample["features"].numpy()
    feature_valid = sample["feature_valid"].numpy()
    result = {}
    for hour in range(len(sample["time_utc"]) - 1):
        assert int(sample["time_utc"][hour + 1] - sample["time_utc"][hour]) == 3600
        for row in range(radius, burned.shape[-2] - radius):
            for col in range(radius, burned.shape[-1] - radius):
                rows = slice(row - radius, row + radius + 1)
                cols = slice(col - radius, col + radius + 1)
                if not label_valid[hour, :, rows, cols].all():
                    continue
                if not label_valid[hour + 1, 0, row, col] or burned[hour, 0, row, col] != 0:
                    continue
                if not feature_valid[hour, :, rows, cols].all():
                    continue
                key = (int(sample["time_utc"][hour]), row, col)
                result[key] = (burned[hour + 1, 0, row, col],
                               environmental[hour, :, rows, cols], burned[hour, :, rows, cols])
    return result


@pytest.mark.parametrize("kernel_size", [5, 7, 9])
@pytest.mark.parametrize("missing", [None, "environment", "burned"])
def test_wider_preparation_matches_loader_census_and_excludes_unknown_full_context(
    wider_training_bundle, kernel_size, missing,
):
    root, event = wider_training_bundle
    if missing is not None:
        variable = "arrival_time_hours.tif" if missing == "burned" else "weather/temperature_2m_375m.tif"
        path = root / "regions" / event["id"] / variable
        import rasterio
        with rasterio.open(path, "r+") as source:
            band = 1 if missing == "burned" else 2
            values = source.read(band)
            values[3, 4] = -9999
            source.write(values, band)
    dataset = WildfireSequenceDataset(
        root, events=[event["id"]], channels=SOURCE_CHANNELS,
        categorical_classes=BIOME_CLASSES, sequence_length=5,
    )
    try:
        sample = dataset[0]
    finally:
        dataset.close()
    expected = _loader_census(sample, kernel_size)
    arrays, audit, _ = _prepare(root, event, kernel_size)
    obtained = {(int(t), int(r), int(c)): index for index, (t, r, c) in enumerate(
        zip(arrays["time_utc"], arrays["row"], arrays["col"]),
    )}
    assert len(obtained) == len(arrays["target"])  # No duplicated pairs.
    assert obtained.keys() == expected.keys()
    assert arrays["environment"].shape == (len(expected), 19, kernel_size, kernel_size)
    assert arrays["burned"].shape == (len(expected), 1, kernel_size, kernel_size)
    for key, (target, environment, burned) in expected.items():
        index = obtained[key]
        assert arrays["target"][index] == target
        assert arrays["weight"][index] == 1  # All negative candidates were sampled.
        np.testing.assert_array_equal(arrays["environment"][index], environment)
        np.testing.assert_array_equal(arrays["burned"][index], burned)
    assert audit["accepted_samples"] == len(expected)
    assert audit["accepted_positives"] == sum(item[0] for item in expected.values())
    assert (audit["environmental_context_rejections"] > 0) == (missing == "environment")
    radius = kernel_size // 2
    assert all(radius <= row < event["height"] - radius and radius <= col < event["width"] - radius
               for _, row, col in obtained)


@pytest.mark.parametrize("kernel_size", [5, 7, 9])
def test_wider_contact_includes_source_at_outer_radius_and_preserves_original_weights(
    wider_training_bundle, tmp_path, kernel_size,
):
    root, event = wider_training_bundle
    radius = kernel_size // 2
    arrival = np.full((event["height"], event["width"]), 3.1, dtype=np.float32)
    arrival[6 - radius, 7] = -1
    arrival[6, 7] = 0.5
    _write_raster(root / event["arrival_path"], arrival, Affine(*event["transform"]))
    broad, audit, _ = _prepare(root, event, kernel_size)
    narrow, _, _ = _prepare(root, event, kernel_size - 2)
    utc = int(pd.Timestamp(event["start_utc"]).timestamp())
    def target_index(arrays):
        positions = np.flatnonzero((arrays["time_utc"] == utc) & (arrays["row"] == 6) & (arrays["col"] == 7))
        assert len(positions) == 1
        return int(positions[0])
    broad_index, narrow_index = target_index(broad), target_index(narrow)
    assert broad["target"][broad_index] == narrow["target"][narrow_index] == 1
    assert broad["burned"][broad_index].sum() == 1
    assert narrow["burned"][narrow_index].sum() == 0

    source = tmp_path / f"source_{kernel_size}"
    source.mkdir()
    schema = resolve_channel_schema(root, source_channels=SOURCE_CHANNELS)
    event_ids = [f"{partition}_event" for partition in ("train", "validation", "test")]
    per_event = []
    for index, partition in enumerate(("train", "validation", "test")):
        arrays = {name: values.copy() for name, values in broad.items()}
        arrays["event_index"][:] = index
        # A nonunit weight proves the filter preserves the assigned population
        # weight rather than replacing it with a conditional class weight.
        arrays["weight"][broad_index] = 3
        np.savez_compressed(source / f"{partition}.npz", **arrays)
        per_event.append({**audit, "id": event_ids[index]})
    metadata = {**schema, "kernel_size": kernel_size, "dt_hours": 1.0,
                "event_ids": event_ids, "splits": dict(zip(event_ids, ("train", "validation", "test"))),
                "sampling": {}, "per_event": per_event}
    (source / "metadata.json").write_text(json.dumps(metadata))
    output = tmp_path / f"filtered_{kernel_size}"
    filtered_metadata = filter_contact(source, output)
    assert f"{kernel_size}x{kernel_size}" in filtered_metadata["population_condition"]
    for partition in ("train", "validation", "test"):
        cached = load_split(output, partition, filtered_metadata)
        assert (cached.neighbor_count > 0).all()
        selected = (cached.time_utc == utc) & (cached.row == 6) & (cached.col == 7)
        assert selected.sum() == 1 and cached.weight[selected].item() == 3
        assert cached.target[selected].item() == 1


@pytest.mark.parametrize("kernel_size", [5, 7, 9])
def test_wider_center_forward_and_parameter_and_environment_gradients_match_public_model(kernel_size):
    torch.manual_seed(90 + kernel_size)
    radius = kernel_size // 2
    model = EnvironmentConditionedConvolution(19, kernel_size=kernel_size, hidden_channels=4).double()
    with torch.no_grad():
        model.kernel_network[-1].weight.mul_(0.1)
        model.kernel_network[-1].bias.fill_(-4)
    efficient_model = deepcopy(model)
    environmental = torch.randn(4, 19, kernel_size, kernel_size, dtype=torch.float64, requires_grad=True)
    efficient_environment = environmental.detach().clone().requires_grad_()
    burned = torch.zeros(4, 1, kernel_size, kernel_size, dtype=torch.float64)
    burned[1, 0, 0, radius] = 1  # A source beyond the old 3x3 support.
    burned[2, 0, ::2, ::2] = 1
    burned[3, 0] = 1
    burned[:, 0, radius, radius] = 0
    public = model(burned, environmental).probability[:, 0, radius, radius]
    efficient = center_probability(efficient_model, efficient_environment, burned)
    torch.testing.assert_close(efficient, public, rtol=0, atol=1e-12)
    assert public[0] == 0 and public[1] > 0
    target = torch.tensor([1, 0, 1, 0], dtype=torch.float64)
    weights = torch.tensor([1, 19, 1, 19], dtype=torch.float64)
    (((public - target).square() * weights).sum() / weights.sum()).backward()
    (((efficient - target).square() * weights).sum() / weights.sum()).backward()
    torch.testing.assert_close(efficient_environment.grad, environmental.grad, rtol=0, atol=1e-12)
    for parameter, efficient_parameter in zip(model.parameters(), efficient_model.parameters()):
        torch.testing.assert_close(efficient_parameter.grad, parameter.grad, rtol=0, atol=1e-12)


@pytest.mark.parametrize("kernel_size", [5, 7, 9])
def test_wider_uniform_rate_fits_weighted_probability_with_more_than_eight_neighbor_sources(kernel_size):
    """For constant count c, weighted Brier is minimized at p=weighted y."""
    radius = kernel_size // 2
    n = 4
    burned = np.ones((n, 1, kernel_size, kernel_size), dtype=np.float32)
    burned[:, 0, radius, radius] = 0
    data = CachedSplit(
        environment=np.zeros((n, 1, kernel_size, kernel_size), dtype=np.float32),
        burned=burned, target=np.array([1, 1, 0, 0], dtype=np.float32),
        weight=np.array([1, 1, 9, 9], dtype=np.float64),
        event_index=np.zeros(n, dtype=np.int64), time_utc=np.arange(n, dtype=np.int64) * 3600,
        row=np.full(n, radius, dtype=np.int32), col=np.full(n, radius, dtype=np.int32),
    )
    count = kernel_size ** 2 - 1
    np.testing.assert_array_equal(data.neighbor_count, np.full(n, count))
    baseline = fit_global_rate(data)
    expected_rate = -np.log1p(-0.1) / count
    assert baseline["per_neighbor_rate_per_hour"] == pytest.approx(expected_rate, rel=1e-5, abs=1e-9)
    assert -np.expm1(-baseline["per_neighbor_rate_per_hour"] * count) == pytest.approx(0.1, abs=1e-7)
    assert baseline["train_brier"] == pytest.approx(0.09, abs=1e-12)


@pytest.mark.parametrize("kernel_size", [5, 7, 9])
def test_wider_checkpoint_inference_uses_saved_radius_for_contact_and_unknown_context(tmp_path, kernel_size):
    radius = kernel_size // 2
    model = EnvironmentConditionedConvolution(2, kernel_size=kernel_size, hidden_channels=4).eval()
    channels = ("weather.temperature_2m", "terrain.slope_degrees")
    contract = dict(format_version=1, architecture="EnvironmentConditionedConvolution", dt_hours=1.0,
                    center_rate=0.0, channels=list(channels), in_channels=2,
                    kernel_size=kernel_size, hidden_channels=4,
                    eligibility="at_least_one_burned_neighbor")
    path = tmp_path / f"wider_{kernel_size}.pt"
    torch.save(dict(contract=contract, model_state_dict=model.state_dict(),
                    normalization_mean=torch.tensor([10.0, -3.0]),
                    normalization_std=torch.tensor([2.0, 5.0]), best_epoch=2), path)
    trained = load_single_trained_model(path)
    burned = torch.zeros(1, 15, 15)
    burned[0, 7 - radius, 7] = 1
    raw = torch.ones(2, 15, 15)
    result = trained(burned, raw, channel_names=channels)
    assert result.valid[0, 7, 7] and result.probability[0, 7, 7] > 0
    assert result.valid[0, 8, 7]  # Source lies beyond the radius; the full neighborhood is known unburned.
    assert result.probability[0, 8, 7] == result.rate[0, 8, 7] == 0
    assert result.rate_valid[0, 8, 7]
    assert not result.valid[0, 0, 0]  # Exterior burned/environmental context is unknown.
    validity = torch.ones_like(raw, dtype=torch.bool)
    validity[0, 7, 7 + radius] = False  # Missing outer environmental value matters.
    unavailable = trained(burned, raw, channel_names=channels, feature_valid=validity)
    assert not unavailable.valid[0, 7, 7] and torch.isnan(unavailable.probability[0, 7, 7])


def _common_comparison_data(event_index=0):
    """One largest-kernel sampled cohort, with unequal original weights."""
    n, channels, size = 6, 2, 9
    environment = np.arange(n * channels * size * size, dtype=np.float32).reshape(n, channels, size, size) / 100
    burned = np.zeros((n, 1, size, size), dtype=np.float32)
    burned[0, 0, 3, 4] = 1  # Inside 3x3.
    burned[1, 0, 0, 4] = 1  # Only the 9x9 kernel can see this source.
    burned[2, 0, 4, 5] = 1  # Inside 3x3.
    burned[2, 0, 4, 0] = 1  # An additional far source must remain for 9x9.
    burned[3, 0, 2, 4] = 1  # Outside 3x3, inside 5x5.
    burned[4, 0, 5, 5] = 1  # Diagonal source inside 3x3.
    burned[5, 0, 0, 0] = 1  # A far-only positive must also be excluded.
    return CachedSplit(
        environment=environment, burned=burned,
        target=np.array([1, 0, 0, 1, 1, 1], dtype=np.float32),
        weight=np.array([1, 17, 13, 1, 1, 1], dtype=np.float64),
        event_index=np.full(n, event_index, dtype=np.int64),
        time_utc=np.arange(n, dtype=np.int64) * 3600,
        row=np.arange(n, dtype=np.int32) + 10, col=np.arange(n, dtype=np.int32) + 20,
    )


@pytest.fixture
def frozen_kernel_runs(tmp_path):
    """Saved models with deliberately different frozen preprocessing."""
    sizes = [3, 5, 7, 9]
    event_ids = ["training_event", "validation_event", "test_event"]
    partitions = ["train", "validation", "test"]
    channels = ["weather.temperature_2m", "terrain.slope_degrees"]
    schema = dict(
        channels=channels, source_channels=channels, categorical_encoding="one_hot",
        categorical_classes={}, channel_groups={name: [index] for index, name in enumerate(channels)},
        channel_info=[dict(name=name, source_channel=name, encoding="continuous") for name in channels],
    )
    metadata = dict(**schema, kernel_size=9, dt_hours=1.0, event_ids=event_ids,
                    splits=dict(zip(event_ids, partitions)), eligibility="at_least_one_burned_neighbor")
    runs = []
    for size in sizes:
        directory = tmp_path / f"kernel_{size}"
        (directory / "fitted").mkdir(parents=True)
        runs.append(directory)
    largest = runs[-1]
    (largest / "prepared").mkdir()
    metadata_path = largest / "prepared" / "metadata.json"
    metadata_path.write_text(json.dumps(metadata))
    metadata_hash = hashlib.sha256(metadata_path.read_bytes()).hexdigest()
    for event_index, partition in enumerate(partitions):
        data = _common_comparison_data(event_index)
        np.savez_compressed(largest / "prepared" / f"{partition}.npz", **vars(data))
    for size, directory in zip(sizes, runs):
        torch.manual_seed(100 + size)
        model = EnvironmentConditionedConvolution(2, kernel_size=size, hidden_channels=4).eval()
        with torch.no_grad():
            model.kernel_network[-1].weight.mul_(0.1)
            model.kernel_network[-1].bias.fill_(-4)
        contract = dict(**schema, format_version=1, architecture="EnvironmentConditionedConvolution",
                        dt_hours=1.0, center_rate=0.0, in_channels=2, kernel_size=size, hidden_channels=4,
                        eligibility="at_least_one_burned_neighbor", event_ids=event_ids,
                        splits=metadata["splits"], cache_metadata_sha256=metadata_hash)
        torch.save(dict(contract=contract, model_state_dict=model.state_dict(), best_epoch=2,
                        normalization_mean=torch.tensor([size / 10, -size / 5]),
                        normalization_std=torch.tensor([size / 3, size / 2])),
                   directory / "fitted" / "checkpoint.pt")
        (directory / "fitted" / "metrics.json").write_text(json.dumps(dict(
            contract=contract, baselines={"global_neighbor_rate": {"per_neighbor_rate_per_hour": 0.01}},
        )))
    output = tmp_path / "comparison"
    output.mkdir()
    (output / "protocol.json").write_text(json.dumps({"kernel_sizes": sizes}))
    return runs, output


def test_common_membership_uses_smallest_sources_and_is_independent_of_target_labels():
    data = _common_comparison_data()
    selected = common_selection(data.burned, 3)
    np.testing.assert_array_equal(selected, [True, False, True, False, True, False])
    # Every row has a 9x9 source; using that criterion would admit far-only
    # positives and negatives into the smaller model's risk population.
    assert common_selection(data.burned, 9).all()
    relabeled = CachedSplit(**{**vars(data), "target": 1 - data.target})
    np.testing.assert_array_equal(common_selection(relabeled.burned, 3), selected)
    for size in (3, 5, 7, 9):
        crop = centered_slice(9, size)
        cropped = data.environment[:, :, crop, crop]
        np.testing.assert_array_equal(cropped[:, :, size // 2, size // 2], data.environment[:, :, 4, 4])


@pytest.mark.parametrize("kernel_size", [3, 5, 7, 9])
def test_common_frozen_prediction_matches_public_center_with_original_cropped_pixels(frozen_kernel_runs, kernel_size):
    runs, _ = frozen_kernel_runs
    directory = next(directory for directory in runs if directory.name == f"kernel_{kernel_size}")
    model = load_single_trained_model(directory / "fitted" / "checkpoint.pt")
    before = {name: value.detach().clone() for name, value in model.state_dict().items()}
    data = _common_comparison_data()
    indices = np.flatnonzero(common_selection(data.burned, 3))
    probability, counts, error = frozen_predictions(model, data, indices, batch_size=2)
    crop = centered_slice(9, kernel_size)
    raw = torch.from_numpy(data.environment[indices, :, crop, crop].copy())
    burned = torch.from_numpy(data.burned[indices, :, crop, crop].copy())
    expected = model(burned, raw, channel_names=model.channel_names)
    radius = kernel_size // 2
    np.testing.assert_allclose(probability, expected.probability[:, 0, radius, radius].detach().numpy(), rtol=0, atol=1e-6)
    np.testing.assert_array_equal(counts, burned.sum(dim=(1, 2, 3)).numpy())
    assert error <= 1e-6
    if kernel_size == 9:
        np.testing.assert_array_equal(counts, [1, 2, 1])
    else:
        np.testing.assert_array_equal(counts, [1, 1, 1])
    for name, value in model.state_dict().items():
        torch.testing.assert_close(value, before[name], rtol=0, atol=0)


def test_common_evaluation_reads_only_largest_cohort_preserves_targets_weights_and_freezes_fitting(
    frozen_kernel_runs, monkeypatch,
):
    runs, output = frozen_kernel_runs
    import wildfire.evaluate as evaluate_kernels
    import wildfire.train as train
    loaded_splits = []
    original_load = evaluate_kernels.load_split
    def record_load(directory, partition, metadata):
        assert directory == runs[-1] / "prepared"
        if partition == "test":
            assert (output / "common_selection.json").exists()  # Selection precedes reading test data.
        loaded_splits.append(partition)
        return original_load(directory, partition, metadata)
    def forbidden_fit(*args, **kwargs):
        pytest.fail("Common evaluation must not fit models, normalization, or baseline parameters")
    monkeypatch.setattr(evaluate_kernels, "load_split", record_load)
    monkeypatch.setattr(train, "fit_normalization", forbidden_fit)
    monkeypatch.setattr(train, "fit_global_rate", forbidden_fit)
    monkeypatch.setattr(train, "train", forbidden_fit)
    before = {path: path.read_bytes() for directory in runs for path in directory.rglob("*") if path.is_file()}
    result = evaluate_runs(runs, output, device="cpu")
    assert loaded_splits == ["validation", "test", "train"]
    assert result["selection"]["test_used_for_selection"] is False
    assert {path: path.read_bytes() for path in before} == before
    for event_index, partition in enumerate(("train", "validation", "test")):
        original = _common_comparison_data(event_index)
        indices = np.array([0, 2, 4])
        with np.load(output / "common_predictions" / f"{partition}.npz", allow_pickle=False) as saved:
            np.testing.assert_array_equal(saved["y"], original.target[indices])
            np.testing.assert_array_equal(saved["w"], original.weight[indices])
            for field in ("event_index", "time_utc", "row", "col"):
                np.testing.assert_array_equal(saved[field], getattr(original, field)[indices])
            assert saved["w"].dtype == np.float64
            for size in (3, 5, 7, 9):
                expected_baseline = -np.expm1(-0.01 * saved[f"neighbor_count_{size}"].astype(np.float64))
                np.testing.assert_array_equal(saved[f"uniform_{size}"], expected_baseline)
        record = result["splits"][partition]
        assert record["sample_count"] == 3 and record["positive_sample_count"] == 2
        assert record["represented_population_weight"] == 15
        assert record["excluded_largest_only_contact_samples"] == 3
        for size in (3, 5, 7, 9):
            assert record["models"][str(size)]["weighted_prevalence"] == pytest.approx(2 / 15)
            assert record["verification"][str(size)]["checkpoint_mean_std_used_without_fitting"] is True


def test_common_evaluation_rejects_duplicate_kernel_runs_before_any_cohort_is_read(frozen_kernel_runs, monkeypatch):
    runs, output = frozen_kernel_runs
    import wildfire.evaluate as evaluate_kernels
    def forbidden_read(*args, **kwargs):
        pytest.fail("An invalid duplicate model list must be rejected before reading a target cohort")
    monkeypatch.setattr(evaluate_kernels, "load_split", forbidden_read)
    with pytest.raises(ValueError, match="Each kernel size must occur exactly once"):
        evaluate_runs([runs[0], runs[0], *runs[1:]], output, device="cpu")
    assert not (output / "common_predictions").exists()
