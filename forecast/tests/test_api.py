"""Public API contracts, resident inference, save/reload, and supported training."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest
import torch

from wildfire import TrainingConfig
from wildfire import WildfireModel
from wildfire import load_data
from wildfire import load_model
from wildfire.models import EnvironmentConditionedConvolution


@pytest.fixture
def checkpoint(tmp_path):
    torch.manual_seed(83)
    model = EnvironmentConditionedConvolution(2, 3, 4)
    contract = {
        "format_version": 1, "architecture": type(model).__name__,
        "in_channels": 2, "channels": ["fixture.a", "fixture.b"],
        "kernel_size": 3, "hidden_channels": 4, "dt_hours": 1.0,
        "eligibility": "at_least_one_burned_neighbor",
    }
    contract["center_rate"] = 0.0
    payload = {"contract": contract, "model_state_dict": model.state_dict(),
               "normalization_mean": torch.tensor([3.0, 4.0]),
               "normalization_std": torch.tensor([2.0, 5.0]), "best_epoch": 3,
               "validation_brier": 0.12, "configuration": {"seed": 83}}
    path = tmp_path / "checkpoint.pt"
    torch.save(payload, path)
    return path


@pytest.fixture
def inputs():
    rng = np.random.default_rng(21)
    environment = rng.normal(size=(2, 2, 7, 9)).astype(np.float32)
    burned = np.zeros((2, 1, 7, 9), dtype=np.float32)
    burned[:, :, 3, 4] = 1.0
    feature_valid = np.ones_like(environment, dtype=bool)
    feature_valid[:, :, 2, 2] = False
    return burned, environment, feature_valid


def assert_prediction_equal(left, right):
    assert type(left) is type(right)
    for name in left.__dataclass_fields__:
        torch.testing.assert_close(getattr(left, name), getattr(right, name), rtol=0, atol=0, equal_nan=True)


def test_prediction_matches_original_wrapper_preserves_masks_and_reads_no_labels(checkpoint, inputs):
    model = load_model(checkpoint)
    burned, environment, valid = inputs
    with torch.no_grad():
        original = model.predictor(torch.from_numpy(burned), torch.from_numpy(environment),
                                   channel_names=model.channel_names, feature_valid=torch.from_numpy(valid))
    result = model.predict_details(burned, environment, channel_names=model.channel_names, feature_valid=valid)
    assert_prediction_equal(result, original)
    assert result.probability.shape == (2, 1, 7, 9)
    assert not result.probability.requires_grad
    assert torch.isnan(result.probability[~result.valid]).all()

    class CurrentInputs(dict):
        def __getitem__(self, name):
            assert name not in {"newly_burned_area", "arrival_hours", "future_labels"}
            return super().__getitem__(name)

    sample = CurrentInputs(burned_area=burned, features=environment,
                           channel_names=model.channel_names, feature_valid=valid)
    assert_prediction_equal(model.predict_sample_details(sample), result)
    torch.testing.assert_close(model.predict_proba(burned, environment, channel_names=model.channel_names,
                                                 feature_valid=valid), result.probability, rtol=0, atol=0, equal_nan=True)
    contract = model.contract
    contract["channels"].reverse()
    assert model.channel_names == ("fixture.a", "fixture.b")


def test_predict_rejects_reordered_channels_nonboolean_masks_and_implicit_mask_loss(checkpoint, inputs):
    model = load_model(checkpoint)
    burned, environment, valid = inputs
    with pytest.raises(ValueError, match="channel"):
        model.predict_details(burned, environment, channel_names=model.channel_names[::-1])
    with pytest.raises(TypeError, match="booleans"):
        model.predict_details(burned, environment, channel_names=model.channel_names, feature_valid=valid.astype(int))
    with pytest.raises(ValueError, match="Masked"):
        model.predict_details(burned, np.ma.array(environment, mask=~valid), channel_names=model.channel_names)
    with pytest.raises(TypeError, match="real"):
        model.predict_details(burned, environment.astype(complex), channel_names=model.channel_names)


def test_public_prediction_tuple_aligns_earth_coordinates_and_preserves_probabilities(checkpoint, inputs):
    from pyproj import Transformer

    model = load_model(checkpoint)
    burned, environment, valid = inputs
    # These are two sequence steps on one projected raster, including rotation.
    transform = np.array([375.0, 12.0, 1_000_000.0, -5.0, -375.0, 2_000_000.0])
    pixel_valid = np.ones((1, 7, 9), dtype=bool)
    pixel_valid[:, -1, -1] = False
    sample = dict(burned_area=burned, features=environment, channel_names=model.channel_names,
                  feature_valid=valid, affine_transform=transform, epsg=5179,
                  pixel_valid=pixel_valid, time_valid=np.array([True, False]))
    details = model.predict_sample_details(sample)
    result = model.predict_sample(sample)
    assert type(result) is tuple and len(result) == 2
    probability, coordinates = result
    torch.testing.assert_close(probability, details.probability, rtol=0, atol=0, equal_nan=True)
    assert probability.shape == (2, 1, 7, 9)
    assert coordinates.shape == (7, 9, 2)
    assert coordinates.dtype == torch.float64 and coordinates.device.type == "cpu"
    assert not probability.requires_grad and not coordinates.requires_grad
    # Missing observations and padded time steps share the fixed spatial grid.
    # Only spatial padding removes a cell's Earth coordinates.
    assert not details.valid[0, 0, 2, 2]
    assert torch.isfinite(coordinates[2, 2]).all()
    assert torch.isnan(coordinates[-1, -1]).all()
    row, col = 3, 4
    x = transform[0] * (col + 0.5) + transform[1] * (row + 0.5) + transform[2]
    y = transform[3] * (col + 0.5) + transform[4] * (row + 0.5) + transform[5]
    lon, lat = Transformer.from_crs(5179, 4326, always_xy=True).transform(x, y)
    np.testing.assert_allclose(coordinates[row, col].numpy(), [lat, lon], rtol=0, atol=1e-10)
    raw = model.predict(burned, environment, channel_names=model.channel_names,
                        feature_valid=valid, affine_transform=transform, epsg=5179,
                        pixel_valid=pixel_valid, time_valid=sample["time_valid"])
    for actual, expected in zip(raw, result):
        torch.testing.assert_close(actual, expected, rtol=0, atol=0, equal_nan=True)


def test_coordinate_grid_is_independent_of_sequence_length_and_temporal_padding(checkpoint, inputs):
    model = load_model(checkpoint)
    burned, environment, valid = inputs
    options = dict(channel_names=model.channel_names,
                   affine_transform=[0.02, 0, 127, 0, -0.02, 38], epsg=4326)
    snapshot_probability, snapshot_coordinates = model.predict(
        burned[0], environment[0], feature_valid=valid[0], **options,
    )
    assert snapshot_probability.shape == (1, 7, 9)
    assert snapshot_coordinates.shape == (7, 9, 2)
    torch.testing.assert_close(snapshot_probability, model.predict_proba(
        burned[0], environment[0], channel_names=model.channel_names, feature_valid=valid[0],
    ), rtol=0, atol=0, equal_nan=True)

    for time_valid in (np.array([True, True]), np.array([True, False]), np.array([False, False])):
        probability, coordinates = model.predict(
            burned, environment, feature_valid=valid, time_valid=time_valid, **options,
        )
        assert probability.shape == (2, 1, 7, 9)
        torch.testing.assert_close(coordinates, snapshot_coordinates, rtol=0, atol=0, equal_nan=True)
        torch.testing.assert_close(probability, model.predict_proba(
            burned, environment, channel_names=model.channel_names, feature_valid=valid,
        ), rtol=0, atol=0, equal_nan=True)

    extended_burned = np.concatenate([burned, burned[:1]], axis=0)
    extended_environment = np.concatenate([environment, environment[:1]], axis=0)
    extended_valid = np.concatenate([valid, valid[:1]], axis=0)
    probability, coordinates = model.predict(
        extended_burned, extended_environment, feature_valid=extended_valid,
        time_valid=np.array([True, True, False]), **options,
    )
    assert probability.shape == (3, 1, 7, 9)
    torch.testing.assert_close(coordinates, snapshot_coordinates, rtol=0, atol=0, equal_nan=True)


def test_dataset_batch_tuple_respects_each_crs_and_spatial_time_padding(checkpoint, tmp_path):
    from pyproj import Transformer
    from tests.loader.test_dataset import bundle
    from wildfire import collate_fire_sequences

    root = bundle.__wrapped__(tmp_path / "data")
    saved = torch.load(checkpoint, weights_only=True)
    saved["contract"]["channels"] = ["terrain.elevation_m", "weather.temperature_2m"]
    path = tmp_path / "georeferenced.pt"
    torch.save(saved, path)
    model = load_model(path)
    with model.load_data(root, sequence_length=4) as dataset:
        samples = [dataset[index] for index in range(len(dataset))]
    batch = collate_fire_sequences(samples)
    probability, coordinates = model.predict_sample(batch)
    assert probability.shape == (2, 4, 1, 3, 3)
    assert coordinates.shape == (2, 3, 3, 2)
    details = model.predict_sample_details(batch)
    torch.testing.assert_close(probability, details.probability, rtol=0, atol=0, equal_nan=True)
    for index, sample in enumerate(samples):
        single_probability, single_coordinates = model.predict_sample(sample)
        h, w = single_probability.shape[-2:]
        torch.testing.assert_close(probability[index, :, :, :h, :w], single_probability,
                                   rtol=0, atol=0, equal_nan=True)
        torch.testing.assert_close(coordinates[index, :h, :w], single_coordinates,
                                   rtol=0, atol=0, equal_nan=True)
    assert not batch["time_valid"][:, -1].any()
    assert torch.isfinite(coordinates[:, 0, 0]).all()
    assert torch.isnan(coordinates[0, -1]).all()
    assert torch.isnan(coordinates[1, :, -1]).all()
    # The raw batch interface can carry a distinct CRS and transform per item.
    transforms = batch["affine_transform"].numpy().copy()
    transforms[1] = [375, 0, -1_000_000, 0, -375, 2_000_000]
    _, mixed_coordinates = model.predict(
        batch["burned_area"], batch["features"], channel_names=batch["channel_names"],
        burned_area_valid=batch["burned_area_valid"], feature_valid=batch["feature_valid"],
        affine_transform=transforms, epsg=np.array([5179, 5070]),
        pixel_valid=batch["pixel_valid"], time_valid=batch["time_valid"],
    )
    lon, lat = Transformer.from_crs(5070, 4326, always_xy=True).transform(-999_812.5, 1_999_812.5)
    np.testing.assert_allclose(mixed_coordinates[1, 0, 0].numpy(), [lat, lon], rtol=0, atol=1e-10)
    torch.testing.assert_close(mixed_coordinates[0], coordinates[0], rtol=0, atol=0, equal_nan=True)


def test_coordinate_tuple_requires_georeferencing_and_reads_no_future_labels(checkpoint, inputs):
    model = load_model(checkpoint)
    burned, environment, valid = inputs

    class CurrentInputs(dict):
        def __getitem__(self, name):
            assert name not in {"arrival_hours", "newly_burned_area", "future_labels"}
            return super().__getitem__(name)

        def get(self, name, default=None):
            assert name not in {"arrival_hours", "newly_burned_area", "future_labels"}
            return super().get(name, default)

    sample = CurrentInputs(burned_area=burned, features=environment, channel_names=model.channel_names,
                           feature_valid=valid, affine_transform=[0.02, 0, 127, 0, -0.02, 38],
                           epsg=4326, arrival_hours=object(), newly_burned_area=object())
    _, coordinates = model.predict_sample(sample)
    torch.testing.assert_close(coordinates[0, 0], torch.tensor([37.99, 127.01], dtype=torch.float64))
    with pytest.raises((TypeError, ValueError), match="affine_transform"):
        model.predict(burned, environment, channel_names=model.channel_names)
    with pytest.raises(ValueError, match="epsg|EPSG"):
        model.predict(burned, environment, channel_names=model.channel_names,
                      affine_transform=sample["affine_transform"], epsg=None)


def test_save_reload_preserves_metadata_prediction_and_protects_existing_destinations(checkpoint, inputs, tmp_path):
    model = load_model(checkpoint)
    # Saving must capture the resident parameters, not recopy the source file.
    with torch.no_grad():
        model.predictor.model.kernel_network[-1].bias.add_(0.5)
    burned, environment, valid = inputs
    original = model.predict_details(burned, environment, channel_names=model.channel_names, feature_valid=valid)
    path = model.save(tmp_path / "saved" / "parameters.pt")
    restored = load_model(path)
    assert model.contract == restored.contract
    assert model.family == restored.family
    assert_prediction_equal(original, restored.predict_details(burned, environment, channel_names=restored.channel_names,
                                                       feature_valid=valid))
    saved = torch.load(path, weights_only=True)
    assert saved["best_epoch"] == 3 and saved["validation_brier"] == 0.12
    assert saved["configuration"] == {"seed": 83}
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        model.save(path)
    assert before == path.read_bytes()
    model.save(path, overwrite=True)
    assert not list(path.parent.glob(".checkpoint-*"))


def test_failed_save_keeps_existing_bytes_and_removes_temporary_file(checkpoint, tmp_path, monkeypatch):
    model = load_model(checkpoint)
    destination = tmp_path / "existing.pt"
    destination.write_bytes(b"preserved result")

    def fail(*args, **kwargs):
        raise OSError("serialization failed")

    monkeypatch.setattr(torch, "save", fail)
    with pytest.raises(OSError, match="serialization failed"):
        model.save(destination, overwrite=True)
    assert destination.read_bytes() == b"preserved result"
    assert not list(tmp_path.glob(".checkpoint-*"))


def test_model_bound_loading_and_heat_composition_use_the_same_saved_schema(checkpoint, tmp_path):
    from tests.loader.test_dataset import bundle
    from wildfire.heat import AffineGrid
    from wildfire.heat import CombustionParameters
    from wildfire.heat import WildfireHeatModel

    root = bundle.__wrapped__(tmp_path / "data")
    payload = torch.load(checkpoint, weights_only=True)
    payload["contract"]["channels"] = ["terrain.elevation_m", "weather.temperature_2m"]
    path = tmp_path / "bound.pt"
    torch.save(payload, path)
    model = load_model(path)
    with model.load_data(root, events=["KR_TEST"], sequence_length=1) as dataset:
        assert dataset.channel_names == model.channel_names
        sample = dataset[0]
        assert model.predict_sample_details(sample).probability.shape == (1, 1, 2, 3)
    assert not dataset._readers
    for name, value in (("channels", model.channel_names), ("categorical_encoding", "raw"),
                        ("categorical_classes", {})):
        with pytest.raises(ValueError, match="fixes"):
            model.load_data(root, **{name: value})
    physical = dict(grid=AffineGrid(tuple(sample["affine_transform"].tolist())),
                    combustion=CombustionParameters(fuel_load_kg_m2=1.0,
                                                     heat_of_combustion_j_kg=18_000_000,
                                                     burning_duration_s=120.0),
                    radiative_fraction=0.3, emission_height_m=5.0)
    composed = model.heat_model(**physical)
    assert composed.predictor is model.predictor
    result = composed.predict_sample_details(sample)
    original = WildfireHeatModel.from_checkpoint(path, **physical).predict_sample_details(sample)
    for name in result.__dataclass_fields__:
        if isinstance(getattr(result, name), np.ndarray):
            np.testing.assert_array_equal(getattr(result, name), getattr(original, name))
    assert result.metadata["predictor"]["checkpoint_sha256"] == model.checkpoint_sha256
    heat_flux, heat_coordinates = composed.predict_sample(sample)
    np.testing.assert_allclose(heat_flux, result.expected_heat_flux_w_m2, rtol=1e-12, atol=1e-10, equal_nan=True)
    _, probability_coordinates = model.predict_sample(sample)
    np.testing.assert_array_equal(heat_coordinates, probability_coordinates.numpy())


def test_exponential_duration_rescales_frozen_rate(checkpoint, inputs):
    model = load_model(checkpoint)
    burned, environment, valid = inputs
    result = model.predict_details(burned, environment, channel_names=model.channel_names,
                           dt_hours=np.array([1.0, 2.0]), feature_valid=valid)
    base = model.predict_details(burned, environment, channel_names=model.channel_names, feature_valid=valid)
    known = result.valid[1] & base.valid[1]
    torch.testing.assert_close(result.probability[1][known],
                              1 - (1 - base.probability[1][known])**2, rtol=1e-6, atol=1e-7)
    with pytest.raises((TypeError, ValueError)):
        model.predict_details(burned, environment, channel_names=model.channel_names, dt_hours=torch.tensor(True))


@pytest.mark.parametrize("options", [
    {"epochs": 0}, {"epochs": True}, {"batch_size": 1.5}, {"learning_rate": float("nan")},
    {"learning_rate": 0.0}, {"weight_decay": -1.0}, {"weight_decay": True},
    {"seed": -1}, {"seed": 2**64}, {"device": "invalid"},
])
def test_training_config_rejects_invalid_options(options):
    with pytest.raises(ValueError):
        TrainingConfig(**options)


def test_api_trains_selects_validated_checkpoint_and_restores_threads(tmp_path):
    from wildfire.cache import CachedSplit
    from wildfire.cache import fit_normalization

    def make_split(feature_shift, event_index):
        rng = np.random.default_rng(91 + event_index)
        n, kernel_size = 8, 3
        environment = (rng.normal(size=(n, 2, kernel_size, kernel_size)) + feature_shift).astype(np.float32)
        burned = np.zeros((n, 1, kernel_size, kernel_size), dtype=np.float32)
        for index in range(n):
            burned[index, 0].flat[0] = 1
        target = (np.arange(n) % 3 == 0).astype(np.float32)
        return CachedSplit(
            environment=environment, burned=burned, target=target,
            weight=np.where(target == 1, 1.0, 4.0).astype(np.float64),
            event_index=np.full(n, event_index, dtype=np.int64),
            time_utc=np.arange(n, dtype=np.int64) * 3600,
            row=np.ones(n, dtype=np.int32), col=np.arange(n, dtype=np.int32) + 1,
        )

    cache = tmp_path / "prepared"
    cache.mkdir()
    names = ("train", "validation", "test")
    metadata = {"channels": ["fixture.a", "fixture.b"], "kernel_size": 3, "dt_hours": 1.0,
                "event_ids": list(names), "splits": {name: name for name in names},
                "eligibility": "at_least_one_burned_neighbor"}
    (cache / "metadata.json").write_text(json.dumps(metadata))
    partitions = {name: make_split(feature_shift=shift, event_index=index)
                  for index, (name, shift) in enumerate(zip(names, (0, 100, -100)))}
    for name, split in partitions.items():
        np.savez_compressed(cache / f"{name}.npz", **vars(split))
    threads = torch.get_num_threads()
    trained = WildfireModel.train(cache, tmp_path / "fitted",
                                  config=TrainingConfig(epochs=2, patience=2, batch_size=4,
                                                        hidden_channels=3, threads=1))
    assert trained.family == "exponential"
    assert torch.get_num_threads() == threads
    assert trained.training_metrics["selection"]["test_used_for_selection"] is False
    expected_mean, expected_std = fit_normalization(partitions["train"])
    np.testing.assert_array_equal(trained.predictor.mean[:, 0, 0].numpy(), expected_mean)
    np.testing.assert_array_equal(trained.predictor.std[:, 0, 0].numpy(), expected_std)
    with pytest.raises(FileExistsError):
        WildfireModel.train(cache, tmp_path / "fitted",
                            config=TrainingConfig(epochs=1, threads=1))
    assert torch.get_num_threads() == threads


def test_dataset_context_closes_readers_even_on_exception(tmp_path):
    from tests.loader.test_dataset import bundle

    root = bundle.__wrapped__(tmp_path)
    with pytest.raises(RuntimeError, match="caller failed"):
        with load_data(root, events=["KR_TEST"], sequence_length=1) as dataset:
            dataset[0]
            assert dataset._readers
            raise RuntimeError("caller failed")
    assert not dataset._readers


def test_public_exports_are_lazy_and_prediction_api_imports_no_trainers():
    code = "\nimport sys\nimport wildfire as package\nassert 'torch' not in sys.modules\nassert 'WildfireModel' in dir(package)\nfrom wildfire import WildfireModel\nfrom wildfire import TrainingConfig\nfrom wildfire import load_data\nfrom wildfire import load_model\nassert 'wildfire.train' not in sys.modules\nassert not any(name.startswith('wildfire.direct_convolution') for name in sys.modules)\n"
    subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1], check=True)


def test_signed_checkpoint_is_explicitly_retired_before_model_loading(tmp_path):
    path = tmp_path / "retired.pt"
    torch.save({"contract": {"architecture": "DirectEnvironmentConditionedConvolution"}}, path)
    with pytest.raises(ValueError, match="signed direct-convolution model has been retired"):
        load_model(path)


def test_new_nonnegative_kernel_checkpoint_uses_supported_loader(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import wildfire.inference as inference

    path = tmp_path / "kernel.pt"
    contract = {"architecture": "LearnedNonnegativeKernel"}
    torch.save({"contract": contract}, path)
    predictor = SimpleNamespace(contract=contract)
    calls = []

    def loader(selected_path, *, device):
        calls.append((selected_path, str(device)))
        return predictor

    monkeypatch.setattr(inference, 'load_single_trained_model', loader)
    model = load_model(path)
    assert model.predictor is predictor
    assert model.family == "exponential"
    assert calls == [(path.resolve(), "cpu")]


def test_signed_training_family_is_explicitly_retired(tmp_path):
    with pytest.raises(ValueError, match="signed direct-convolution model has been retired"):
        WildfireModel.train(tmp_path / "absent", tmp_path / "output", family="direct")
    assert not (tmp_path / "output").exists()
