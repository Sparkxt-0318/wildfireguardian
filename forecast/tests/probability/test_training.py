"""Independent checks for hourly pairing and weighted sampling semantics."""

from copy import deepcopy
from itertools import combinations
import json
from pathlib import Path

from wildfire.data import DEFAULT_ROOT

from affine import Affine
import numpy as np
import pandas as pd
import pytest
import rasterio
import torch

from wildfire.data import WildfireSequenceDataset
from wildfire.examples import CHANNELS
from wildfire.prepare import prepare_event
from wildfire.prepare import sample_segments
from wildfire.prepare import season_split
from wildfire.models import EnvironmentConditionedConvolution
from wildfire.prepare import filter_contact
from wildfire.inference import load_single_trained_model
from wildfire.train import CachedSplit
from wildfire.train import brier
from wildfire.train import center_probability
from wildfire.train import fit_normalization
from wildfire.train import load_split
from wildfire.train import probability_metrics
from wildfire.train import weighted_rank_metrics


def _write_raster(path, values, transform):
    path.parent.mkdir(parents=True, exist_ok=True)
    values = np.asarray(values, dtype=np.float32)
    if values.ndim == 2:
        values = values[None]
    with rasterio.open(
        path, "w", driver="GTiff", count=len(values), height=values.shape[1],
        width=values.shape[2], dtype="float32", crs="EPSG:5179",
        transform=transform, nodata=-9999,
    ) as output:
        output.write(values)


@pytest.fixture
def hourly_training_bundle(tmp_path):
    """Five snapshots, fractional origin, mixed contact and cold targets."""
    transform = Affine(375, 0, 1000000, 0, -375, 2000000)
    times = pd.date_range("2022-03-04T02:00:00Z", periods=5, freq="h")
    event = dict(
        id="KR_TRAIN_TEST", name="Independent hourly fixture", country="KR",
        year=2022, epsg=5179, width=5, height=5,
        transform=list(transform)[:6], start_utc=times[0].isoformat(),
        end_utc=times[-1].isoformat(), t0_utc="2022-03-04T02:12:00+00:00",
        arrival_path="regions/KR_TRAIN_TEST/arrival_time_hours.tif",
    )
    region = tmp_path / "regions" / event["id"]
    arrival = np.full((5, 5), 3.1, dtype=np.float32)
    arrival[1, 1] = -1.0  # Already burned at the first snapshot.
    arrival[2, 2] = np.float32(0.8)  # Strictly greater than exact 0.8 h.
    arrival[3, 3] = 1.4
    arrival[1, 3] = 2.6
    arrival[3, 1] = 4.9  # Remains at risk at the final available snapshot.
    _write_raster(region / "arrival_time_hours.tif", arrival, transform)
    _write_raster(region / "kriging_std_hours.tif", np.ones((5, 5)), transform)
    weather = {}
    for index, name in enumerate(CHANNELS):
        category, variable = name.split(".", 1)
        if category == "weather":
            values = np.stack([np.full((5, 5), 100 + 10 * index + hour) for hour in range(5)])
            weather[variable] = {}
        else:
            values = np.full((5, 5), 10 + index)
        _write_raster(region / category / f"{variable}_375m.tif", values, transform)
    (region / "weather" / "ecmwf_ifs_complete.json").write_text(json.dumps({"variables": weather}))
    pd.DataFrame({"band": np.arange(1, 6), "time_utc": times.strftime("%Y-%m-%dT%H:%M:%SZ")}).to_csv(
        region / "weather" / "ecmwf_ifs_bands.csv", index=False,
    )
    (tmp_path / "events.json").write_text(json.dumps([event]))
    return tmp_path, event


def test_segment_sampling_census_handles_empty_segments_and_disjoint_starts():
    lengths = np.array([2, 0, 3, 1])
    starts = np.array([5, 100, 9, 2])
    cells, times, weights, total = sample_segments(lengths, starts, 20, np.random.default_rng(7))
    assert total == 6
    assert set(zip(cells.tolist(), times.tolist())) == {(0, 5), (0, 6), (2, 9), (2, 10), (2, 11), (3, 2)}
    np.testing.assert_array_equal(weights, np.ones(6))


def test_segment_sampling_inverse_weights_remain_unbiased_after_validity_rejection():
    """Enumerate every equally likely sample rather than use a noisy simulation."""
    lengths = np.array([2, 3, 1])
    starts = np.array([0, 4, 8])
    estimates = []

    class FixedDraw:
        def __init__(self, selected):
            self.selected = selected

        def choice(self, total, size, replace):
            assert (total, size, replace) == (6, 2, False)
            return np.asarray(self.selected)

    for selected in combinations(range(6), 2):
        cells, times, weights, total = sample_segments(lengths, starts, 2, FixedDraw(selected))
        assert total == 6 and len(set(zip(cells.tolist(), times.tolist()))) == 2
        np.testing.assert_array_equal(weights, np.full(2, 3.0))
        # Environmental validity is a fixed population property. Dropping
        # rejected draws must not alter the original inclusion weights.
        valid = ((cells == 0) & (times == 1)) | (cells == 1)
        estimates.append(weights[valid].sum())
    assert np.mean(estimates) == pytest.approx(4.0)


def test_segment_sampling_empty_population():
    cells, times, weights, total = sample_segments(
        np.zeros(3, dtype=np.int64), np.zeros(3, dtype=np.int64), 3, np.random.default_rng(1),
    )
    assert total == 0 and len(cells) == len(times) == len(weights) == 0


def test_all_catalog_events_remain_inside_fixed_season_partitions():
    catalog_path = DEFAULT_ROOT / "events.json"
    catalog = json.loads(catalog_path.read_text())
    partitions = {season: {season_split(event) for event in catalog if (event["country"], event["year"]) == season}
                  for season in {(event["country"], event["year"]) for event in catalog}}
    assert all(len(values) == 1 for values in partitions.values())
    assert {part: sum(season_split(event) == part for event in catalog)
            for part in ("train", "validation", "test")} == {"train": 27, "validation": 7, "test": 10}
    with pytest.raises(ValueError, match="No predetermined split"):
        season_split({"country": "KR", "year": 2026})


def _expected_hourly_targets(sample):
    result = {}
    burned = sample["burned_area"].numpy()
    features = sample["features"].numpy()
    feature_valid = sample["feature_valid"].numpy()
    for hour in range(len(sample["time_utc"]) - 1):
        current_time = int(sample["time_utc"][hour])
        assert int(sample["time_utc"][hour + 1]) - current_time == 3600
        for row in range(1, burned.shape[-2] - 1):
            for col in range(1, burned.shape[-1] - 1):
                if burned[hour, 0, row, col] == 1:
                    continue
                if not feature_valid[hour, :, row - 1:row + 2, col - 1:col + 2].all():
                    continue
                result[(current_time, row, col)] = (
                    burned[hour + 1, 0, row, col],
                    features[hour, :, row - 1:row + 2, col - 1:col + 2],
                    burned[hour, :, row - 1:row + 2, col - 1:col + 2],
                )
    return result


@pytest.mark.parametrize("missing_current_environment", [False, True])
def test_preparation_matches_exact_loader_next_hour_across_chunks_and_fractional_origin(
    hourly_training_bundle, missing_current_environment,
):
    root, event = hourly_training_bundle
    if missing_current_environment:
        path = root / "regions" / event["id"] / "weather" / "temperature_2m_375m.tif"
        with rasterio.open(path, "r+") as source:
            values = source.read(2)
            values[2, 2] = -9999
            source.write(values, 2)
    dataset = WildfireSequenceDataset(root, events=[event["id"]], channels=CHANNELS, sequence_length=5)
    try:
        reference = dataset[0]
    finally:
        dataset.close()
    expected = _expected_hourly_targets(reference)
    arrays, audit, _ = prepare_event(root, event, 0, np.random.default_rng(7), 1000, 1000, chunk_hours=2)
    obtained = {(int(t), int(r), int(c)): index for index, (t, r, c) in
                enumerate(zip(arrays["time_utc"], arrays["row"], arrays["col"]))}
    assert len(obtained) == len(arrays["target"])  # No duplicated pairs.
    assert obtained.keys() == expected.keys()
    for key, (target, environment, burned) in expected.items():
        index = obtained[key]
        assert arrays["target"][index] == target, key
        np.testing.assert_array_equal(arrays["environment"][index], environment)
        np.testing.assert_array_equal(arrays["burned"][index], burned)
        assert arrays["weight"][index] == 1.0  # All negative candidates sampled.
    assert audit["accepted_samples"] == len(expected)
    assert audit["accepted_positives"] == sum(value[0] for value in expected.values())
    assert (audit["environmental_context_rejections"] > 0) == missing_current_environment
    # np.float32(0.8) lies strictly after the exact fractional-hour cutoff.
    assert reference["burned_area"][:3, 0, 2, 2].tolist() == [0, 0, 1]


def test_center_training_forward_and_gradients_match_public_model():
    torch.manual_seed(23)
    model = EnvironmentConditionedConvolution(5, hidden_channels=4).double()
    efficient_model = deepcopy(model)
    environmental = torch.randn(4, 5, 3, 3, dtype=torch.float64)
    burned = torch.tensor([
        [[0, 0, 0], [0, 0, 0], [0, 0, 0]],
        [[1, 0, 0], [0, 0, 0], [0, 0, 0]],
        [[1, 1, 0], [0, 0, 1], [0, 1, 0]],
        [[1, 1, 1], [1, 0, 1], [1, 1, 1]],
    ], dtype=torch.float64)[:, None]
    public = model(burned, environmental).probability[:, 0, 1, 1]
    efficient = center_probability(efficient_model, environmental, burned)
    torch.testing.assert_close(efficient, public, rtol=0, atol=1e-12)
    assert efficient[0] == 0  # Preserve unsupported cold-start probability.
    weights = torch.tensor([1, 2, 4, 8], dtype=torch.float64)
    target = torch.tensor([1, 0, 1, 0], dtype=torch.float64)
    (((public - target).square() * weights).sum() / weights.sum()).backward()
    (((efficient - target).square() * weights).sum() / weights.sum()).backward()
    for public_parameter, efficient_parameter in zip(model.parameters(), efficient_model.parameters()):
        torch.testing.assert_close(efficient_parameter.grad, public_parameter.grad, rtol=0, atol=1e-12)


def test_weighted_brier_and_rank_metrics_use_population_weights_and_whole_ties():
    target = np.array([1, 0, 1, 0], dtype=np.float32)
    probability = np.array([0.8, 0.8, 0.2, 0.1], dtype=np.float64)
    weight = np.array([1, 3, 2, 4], dtype=np.float64)
    assert brier(target, probability, weight) == pytest.approx(0.328)
    average_precision, roc_auc = weighted_rank_metrics(target, probability, weight)
    assert average_precision == pytest.approx(5 / 12)
    assert roc_auc == pytest.approx(9 / 14)
    # Order inside a tie must never manufacture extra ranking information.
    reordered = np.array([1, 0, 2, 3])
    assert weighted_rank_metrics(target[reordered], probability[reordered], weight[reordered]) == pytest.approx(
        (average_precision, roc_auc),
    )


def test_full_probability_metrics_retain_unsupported_positive_error():
    result = probability_metrics(
        np.array([1, 0, 1], dtype=np.float32),
        np.array([0, 0, 0.5], dtype=np.float32),
        np.array([1, 7, 1], dtype=np.float64),
        np.array([0, 0, 2], dtype=np.float32),
    )
    assert result["represented_population_weight"] == 9
    assert result["positive_population_weight"] == 2
    assert result["brier"] == pytest.approx(5 / 36)
    assert result["exact_negative_log_likelihood_mean"] == "infinity"
    assert result["unsupported_positive_sample_count"] == 1
    assert result["zero_contact_positive_fraction"] == 0.5
    assert np.isfinite(result["clipped_log_loss"])
    assert result["log_loss_probability_floor"] > 0


def test_training_normalization_weights_all_patch_positions_and_retains_constant_channels():
    environment = np.zeros((2, 2, 3, 3), dtype=np.float32)
    environment[0, 0] = np.arange(9).reshape(3, 3)
    environment[1, 0] = np.arange(9).reshape(3, 3) + 10
    environment[:, 1] = 42
    data = CachedSplit(
        environment=environment,
        burned=np.zeros((2, 1, 3, 3), dtype=np.float32),
        target=np.array([1, 0], dtype=np.float32),
        weight=np.array([1, 3], dtype=np.float64),
        event_index=np.zeros(2, dtype=np.int64),
        time_utc=np.array([0, 3600], dtype=np.int64),
        row=np.ones(2, dtype=np.int32), col=np.ones(2, dtype=np.int32),
    )
    mean, scale = fit_normalization(data, chunk_size=1)
    np.testing.assert_allclose(mean, [11.5, 42], rtol=0, atol=1e-6)
    np.testing.assert_allclose(scale, [np.sqrt(305 / 12), 1], rtol=0, atol=1e-6)


@pytest.fixture
def unfiltered_training_cache(tmp_path):
    source = tmp_path / "all_targets"
    source.mkdir()
    event_ids = ["train_contact", "train_cold_only", "validation_contact", "test_contact"]
    splits = {event_ids[0]: "train", event_ids[1]: "train", event_ids[2]: "validation", event_ids[3]: "test"}
    metadata = {
        "channels": ["weather.temperature_2m"], "kernel_size": 3, "dt_hours": 1.0,
        "event_ids": event_ids, "splits": splits,
        "sampling": {"metric_scope": "all eligible targets", "all_positives": True},
        "per_event": [],
    }
    for split, event_index in (("train", 0), ("validation", 2), ("test", 3)):
        n = 5 if split == "train" else 4
        burned = np.zeros((n, 1, 3, 3), dtype=np.float32)
        burned[1, 0, 0, 1] = 1
        burned[2, 0, 2, 0] = 1
        indices = np.full(n, event_index, dtype=np.int64)
        if split == "train":
            indices[3:] = 1
        arrays = dict(
            environment=np.arange(n * 9, dtype=np.float32).reshape(n, 1, 3, 3),
            burned=burned,
            target=np.array([1, 0, 1, 1, 0] if split == "train" else [1, 0, 1, 0], dtype=np.float32),
            weight=np.array([1, 3, 1, 1, 7] if split == "train" else [1, 3, 1, 7], dtype=np.float64),
            event_index=indices,
            time_utc=np.arange(n, dtype=np.int64) * 3600,
            row=np.arange(n, dtype=np.int32) + 1, col=np.ones(n, dtype=np.int32),
        )
        np.savez_compressed(source / f"{split}.npz", **arrays)
        for index in np.unique(indices):
            selection = indices == index
            metadata["per_event"].append(dict(
                id=event_ids[int(index)], accepted_samples=int(selection.sum()),
                accepted_positives=int(arrays["target"][selection].sum()),
                accepted_no_contact_positives=int(((burned.sum(axis=(1, 2, 3)) == 0) & selection & (arrays["target"] == 1)).sum()),
                estimated_environment_valid_cell_hours=float(arrays["weight"][selection].sum()),
                exclusion=None,
            ))
    (source / "metadata.json").write_text(json.dumps(metadata))
    return source, metadata


def test_contact_filter_applies_all_partitions_retains_weights_and_records_exclusions(
    unfiltered_training_cache, tmp_path,
):
    source, original = unfiltered_training_cache
    before = {path.name: path.read_bytes() for path in source.iterdir()}
    output = tmp_path / "contact_targets"
    metadata = filter_contact(source, output)
    assert metadata["eligibility"] == "at_least_one_burned_neighbor"
    assert metadata["event_ids"] == original["event_ids"]
    assert metadata["splits"] == original["splits"]
    assert metadata["parent_prepared_directory"] == str(source.resolve())
    assert "retained exactly" in metadata["sampling"]["contact_filter_weights"]
    assert {path.name: path.read_bytes() for path in source.iterdir()} == before
    for split in ("train", "validation", "test"):
        with np.load(source / f"{split}.npz", allow_pickle=False) as archive:
            arrays = {name: archive[name] for name in archive.files}
        selection = arrays["burned"].sum(axis=(1, 2, 3)) > 0
        with np.load(output / f"{split}.npz", allow_pickle=False) as archive:
            assert set(archive.files) == set(arrays)
            for name, values in arrays.items():
                np.testing.assert_array_equal(archive[name], values[selection])
        cached = load_split(output, split, metadata)
        assert (cached.neighbor_count > 0).all()
        summary = metadata["split_summary"][split]
        assert summary["samples"] == 2
        assert summary["positives"] == 1
        assert summary["contributing_events"] == 1
        assert summary["estimated_eligible_cell_hours"] == 4
        assert summary["excluded_no_contact_samples"] == (3 if split == "train" else 2)
        assert summary["excluded_no_contact_positives"] == (2 if split == "train" else 1)
    by_event = {event["id"]: event for event in metadata["per_event"]}
    assert by_event["train_cold_only"]["unfiltered_accepted_samples"] == 2
    assert by_event["train_cold_only"]["accepted_samples"] == 0
    assert by_event["train_cold_only"]["excluded_no_contact_positives"] == 1
    assert "No targets with a previously burned neighbor" in by_event["train_cold_only"]["exclusion"]
    assert all(event["accepted_no_contact_positives"] == 0 for event in metadata["per_event"])


@pytest.mark.parametrize("split", ["train", "validation", "test"])
def test_contact_only_cache_contract_rejects_unfiltered_targets(unfiltered_training_cache, split):
    source, metadata = unfiltered_training_cache
    metadata = {**metadata, "eligibility": "at_least_one_burned_neighbor"}
    with pytest.raises(ValueError, match="no-contact target despite its contact-only contract"):
        load_split(source, split, metadata)


@pytest.fixture
def synthetic_trained_checkpoints(tmp_path):
    torch.manual_seed(41)
    model = EnvironmentConditionedConvolution(2, hidden_channels=4).eval()
    mean = torch.tensor([10.0, -3.0])
    scale = torch.tensor([2.0, 5.0])
    channels = ("weather.temperature_2m", "terrain.slope_degrees")
    contract = dict(
        format_version=1, architecture="EnvironmentConditionedConvolution",
        dt_hours=1.0, center_rate=0.0, channels=list(channels),
        in_channels=2, kernel_size=3, hidden_channels=4,
    )
    saved = dict(
        contract=contract, model_state_dict=model.state_dict(),
        normalization_mean=mean, normalization_std=scale, best_epoch=3,
    )
    legacy = tmp_path / "legacy_all_targets.pt"
    torch.save(saved, legacy)
    contact = tmp_path / "contact_targets.pt"
    torch.save({**saved, "contract": {**contract, "eligibility": "at_least_one_burned_neighbor"}}, contact)
    raw_environment = torch.arange(2 * 9 * 9, dtype=torch.float32).reshape(2, 9, 9) / 100
    raw_environment += mean[:, None, None]
    burned = torch.zeros(1, 9, 9)
    burned[0, 2, 2] = 1
    return model, mean, scale, channels, raw_environment, burned, contact, legacy


def test_trained_inference_applies_saved_normalization_and_rejects_reversed_channels(
    synthetic_trained_checkpoints,
):
    model, mean, scale, channels, raw, burned, contact_path, _ = synthetic_trained_checkpoints
    trained = load_single_trained_model(contact_path)
    result = trained(burned, raw, channel_names=channels)
    normalized = (raw - mean[:, None, None]) / scale[:, None, None]
    expected = model(burned, normalized)
    assert trained.best_epoch == 3 and trained.channel_names == channels
    torch.testing.assert_close(trained.mean[:, 0, 0], mean)
    torch.testing.assert_close(trained.std[:, 0, 0], scale)
    assert result.valid[0, 3, 3] and result.rate_valid[0, 3, 3]
    torch.testing.assert_close(result.probability[0, 3, 3], expected.probability[0, 3, 3])
    torch.testing.assert_close(result.rate[0, 3, 3], expected.rate[0, 3, 3])
    assert not torch.isclose(result.probability[0, 3, 3], model(burned, raw).probability[0, 3, 3])
    with pytest.raises(ValueError, match="channel names/order differ"):
        trained(burned, raw, channel_names=channels[::-1])


def test_contact_only_trained_inference_preserves_complete_unburned_structural_zero_and_burned_zero(
    synthetic_trained_checkpoints,
):
    _, _, _, channels, raw, burned, contact_path, _ = synthetic_trained_checkpoints
    trained = load_single_trained_model(contact_path)
    feature_valid = torch.ones_like(raw, dtype=torch.bool)
    # Missing context makes the already-burned target's rate unavailable;
    # its known new-burn probability nevertheless remains exactly zero.
    feature_valid[0, 1, 1] = False
    result = trained(burned, raw, channel_names=channels, feature_valid=feature_valid)
    assert result.valid[0, 6, 6] and result.rate_valid[0, 6, 6]
    assert result.probability[0, 6, 6] == result.rate[0, 6, 6] == 0
    assert result.valid[0, 2, 2] and result.probability[0, 2, 2] == 0
    assert not result.rate_valid[0, 2, 2] and torch.isnan(result.rate[0, 2, 2])
    assert result.valid[0, 3, 3] and result.probability[0, 3, 3] > 0


def test_legacy_all_target_checkpoint_preserves_structural_zero_for_unburned_cold_cells(
    synthetic_trained_checkpoints,
):
    model, mean, scale, channels, raw, burned, _, legacy_path = synthetic_trained_checkpoints
    trained = load_single_trained_model(legacy_path)
    result = trained(burned, raw, channel_names=channels)
    expected = model(burned, (raw - mean[:, None, None]) / scale[:, None, None])
    assert result.valid[0, 6, 6] and result.rate_valid[0, 6, 6]
    assert result.probability[0, 6, 6] == result.rate[0, 6, 6] == 0
    torch.testing.assert_close(result.valid, expected.valid)
    torch.testing.assert_close(result.rate_valid, expected.rate_valid)
    torch.testing.assert_close(result.probability, expected.probability, equal_nan=True)
    torch.testing.assert_close(result.rate, expected.rate, equal_nan=True)
