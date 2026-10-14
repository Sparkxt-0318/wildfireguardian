"""Saved forest grids, fitted preprocessing, and shared recursive transitions."""
from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest
import torch

from wildfire.api import load_model
from wildfire.models import PatchRandomForest


def _save(tmp_path, *, kernel=3, labels=None, channels=("temperature", "wind"),
          metadata=None):
    rng = np.random.default_rng(841)
    environment = rng.normal(size=(64, len(channels), kernel, kernel)).astype(np.float32)
    burned = rng.integers(0, 2, size=(64, 1, kernel, kernel)).astype(np.float32)
    burned[:, :, kernel // 2, kernel // 2] = 0
    y = (environment[:, 0, kernel // 2, kernel // 2] > 0).astype(np.uint8) if labels is None else np.full(64, labels)
    forest = PatchRandomForest(kernel, n_estimators=5, max_depth=4, n_jobs=1).fit(
        environment, burned, y, np.linspace(1, 2, 64), channel_names=channels,
    )
    path = tmp_path / "forest.joblib"
    forest.save(path, metadata=metadata)
    return load_model(path), forest


def _grid(leading=(), *, channels=2, h=7, w=8):
    rng = np.random.default_rng(842)
    environment = rng.normal(size=(*leading, channels, h, w)).astype(np.float32)
    burned = np.zeros((*leading, 1, h, w), dtype=np.float32)
    burned[..., 0, h // 2, w // 2] = 1
    return burned, environment


@pytest.mark.parametrize("kernel", [3, 5])
@pytest.mark.parametrize("leading", [(), (2,), (2, 3)])
def test_full_grid_equals_independent_saved_patch_prediction(tmp_path, kernel, leading):
    mean, std = np.array([2, -1], np.float32), np.array([3, .5], np.float32)
    model, forest = _save(tmp_path, kernel=kernel, metadata={
        "normalization_mean": mean.tolist(), "normalization_std": std.tolist(),
    })
    burned, environment = _grid(leading)
    # Include an exterior source so independent padding comparisons exercise
    # nonzero predictions at the edge, not only structural zeros there.
    burned[..., 0, 0, 0] = 1
    actual = model.predict(burned, environment, channel_names=model.channel_names, boundary="zero")
    expected = np.zeros_like(burned)
    radius = kernel // 2
    h, w = burned.shape[-2:]
    for state, env, out in zip(burned.reshape(-1, 1, h, w), environment.reshape(-1, 2, h, w), expected.reshape(-1, 1, h, w)):
        normalized = (env - mean[:, None, None]) / std[:, None, None]
        padded_environment = np.pad(normalized, ((0, 0), (radius, radius), (radius, radius)))
        padded_burned = np.pad(state, ((0, 0), (radius, radius), (radius, radius)))
        for row in range(h):
            for col in range(w):
                ep = padded_environment[:, row:row + kernel, col:col + kernel][None]
                bp = padded_burned[:, row:row + kernel, col:col + kernel][None]
                if state[0, row, col] == 0 and bp.sum() > 0:
                    out[0, row, col] = forest.predict_probability(ep, bp, channel_names=forest.channel_names)[0]
    assert actual.probability.shape == burned.shape
    assert bool(actual.valid.all())
    np.testing.assert_array_equal(actual.probability.numpy(), expected)
    assert model.family == "random_forest"
    assert model.device == torch.device("cpu")
    assert model.contract["preprocessing_policy"] == "saved_training_normalization"
    assert actual.metadata["tree_sampling"] is False


@pytest.mark.parametrize("label", [0, 1])
def test_one_class_and_absorbing_prior_burns(tmp_path, label):
    model, _ = _save(tmp_path, labels=label)
    burned, env = _grid()
    output = model.predict(burned, env, channel_names=model.channel_names, boundary="zero")
    assert output.probability[0, 3, 4] == 0
    assert output.probability[0, 3, 5] == label
    if label:
        assert torch.isinf(output.rate[0, 3, 5])
        assert output.rate_valid[0, 3, 5]
    recursive = model.predict_cumulative(burned, env, channel_names=model.channel_names,
                                         hours=[1, 3], n_samples=5, trajectory_batch_size=3)
    assert bool(recursive.valid.all())
    assert bool(torch.isnan(recursive.rate).all())
    assert not bool(recursive.rate_valid.any())
    assert bool((recursive.probability[:, 0, 3, 4] == 0).all())
    assert bool((recursive.burned_probability[:, 0, 3, 4] == 1).all())
    assert bool((recursive.mc_standard_error[:, 0, 3, 4] == 0).all())
    if label:
        assert recursive.probability[0, 0, 3, 5] == 1


@pytest.mark.parametrize("boundary", ["zero", "unknown"])
def test_no_contact_zero_despite_positive_forest_and_no_initial_fire(tmp_path, boundary):
    model, _ = _save(tmp_path, labels=1)
    burned, env = _grid(h=13, w=14)
    burned[:] = 0
    output = model.predict_cumulative(burned, env, channel_names=model.channel_names,
                                     hours=[1, 2, 3], n_samples=3, boundary=boundary)
    assert output.probability.shape == (3, 1, 13, 14)
    assert bool((output.probability[output.valid] == 0).all())
    assert bool((output.burned_probability[output.valid] == 0).all())
    if boundary == "zero":
        assert bool(output.valid.all())
    else:
        assert not bool(output.valid[:, :, 0].any())
        assert output.valid[0].sum() > output.valid[-1].sum()


def test_recursive_synchronous_binary_spread_chain(tmp_path, monkeypatch):
    model, _ = _save(tmp_path)
    queried = []

    def left_edge_probability(environment, burned, *, channel_names, **unused):
        assert np.isin(burned, (0, 1)).all()
        assert (burned[:, 0, 1, 1] == 0).all()
        queried.append(burned.copy())
        return .5 * burned[:, 0, 1, 0]

    monkeypatch.setattr(model.predictor.forest, "predict_probability", left_edge_probability)
    burned = np.zeros((1, 1, 3), np.float32)
    burned[0, 0, 0] = 1
    env = np.zeros((2, 1, 3), np.float32)
    result = model.predict_cumulative(burned, env, channel_names=model.channel_names,
                                     hours=[1, 2, 3], n_samples=4096,
                                     seed=7, trajectory_batch_size=64)
    assert queried
    assert result.probability[0, 0, 0, 2] == 0
    # Six standard errors are a conservative tolerance for these independent
    # Bernoulli trajectories; a same-hour cascade would make F_C(1)>0.
    assert result.probability[1, 0, 0, 2].item() == pytest.approx(.25, abs=.041)
    assert result.probability[2, 0, 0, 2].item() == pytest.approx(.5, abs=.047)
    assert bool((torch.diff(result.probability, dim=0) >= 0).all())


def test_forecast_hour_alignment_and_later_sources(tmp_path, monkeypatch):
    model, _ = _save(tmp_path)

    def forecast_conditioned_probability(environment, burned, *, channel_names):
        return ((environment[:, 0, 1, 1] > 0) & (burned[:, 0, 1, 0] == 1)).astype(float)

    monkeypatch.setattr(model.predictor.forest, "predict_probability", forecast_conditioned_probability)
    burned = np.zeros((1, 1, 3), np.float32)
    burned[0, 0, 0] = 1
    environment = np.zeros((2, 1, 3), np.float32)
    forecast = np.stack([environment.copy() for _ in range(4)])
    forecast[1:3, 0] = 1  # First interval stays off; second and third turn on.
    forecast[3] = np.nan  # Extra unused interval cannot affect inference.
    output = model.predict_cumulative(burned, environment, channel_names=model.channel_names,
                                     hours=[1, 2, 3], n_samples=2,
                                     environmental_forecast={"features": forecast,
                                                             "channel_names": model.channel_names})
    torch.testing.assert_close(output.probability[:, 0, 0],
                               torch.tensor([[0., 0., 0.], [0., 1., 0.], [0., 1., 1.]]))


@pytest.mark.parametrize("invalid", [np.nan, np.inf, -.1, 1.1])
def test_invalid_actual_forest_probability_is_rejected(tmp_path, monkeypatch, invalid):
    model, _ = _save(tmp_path)
    monkeypatch.setattr(model.predictor.forest, "predict_probability",
                        lambda environment, burned, **unused: np.full(len(burned), invalid))
    burned, environment = _grid()
    with pytest.raises(RuntimeError, match="nonfinite probability|outside"):
        model.predict_cumulative(burned, environment, channel_names=model.channel_names,
                                 hours=2, n_samples=2)


def test_seed_reproducibility_horizon_order_and_global_random_state(tmp_path):
    model, _ = _save(tmp_path)
    burned, env = _grid()
    torch.manual_seed(181)
    np.random.seed(182)
    torch_before = torch.random.get_rng_state().clone()
    numpy_before = deepcopy(np.random.get_state())
    controls = dict(channel_names=model.channel_names, n_samples=31, seed=12,
                    trajectory_batch_size=7)
    first = model.predict_cumulative(burned, env, hours=[1, 3], **controls)
    repeat = model.predict_cumulative(burned, env, hours=[1, 3], **controls)
    reordered = model.predict_cumulative(burned, env, hours=[3, 1, 5], **controls)
    torch.testing.assert_close(first.probability, repeat.probability, rtol=0, atol=0)
    torch.testing.assert_close(first.at(hours=1).probability, reordered.at(hours=1).probability, rtol=0, atol=0)
    torch.testing.assert_close(first.at(hours=3).probability, reordered.at(hours=3).probability, rtol=0, atol=0)
    assert torch.equal(torch.random.get_rng_state(), torch_before)
    numpy_after = np.random.get_state()
    assert numpy_before[0] == numpy_after[0]
    np.testing.assert_array_equal(numpy_before[1], numpy_after[1])
    assert numpy_before[2:] == numpy_after[2:]
    assert first.metadata["probability_model"] == "mean_tree_probability_at_each_hour"


def test_one_hour_mc_agrees_with_analytic_forest_probability(tmp_path):
    model, _ = _save(tmp_path)
    burned, env = _grid(h=4, w=5)
    analytic = model.predict(burned, env, channel_names=model.channel_names, boundary="zero")
    simulated = model.predict_cumulative(burned, env, channel_names=model.channel_names,
                                        hours=1, n_samples=2048, seed=801,
                                        trajectory_batch_size=64).at(hours=1)
    # Hoeffding plus a union bound gives simultaneous nominal 99% coverage
    # across all 20 cells, without assuming independence across output cells.
    tolerance = np.sqrt(np.log(2 * 20 / .01) / (2 * 2048))
    assert torch.max(torch.abs(analytic.probability - simulated.probability)) <= tolerance


def test_large_grid_prediction_queries_are_memory_bounded(tmp_path, monkeypatch):
    model, _ = _save(tmp_path, labels=1)
    burned, env = _grid((2,), h=100, w=101)
    burned[:] = (np.indices((100, 101)).sum(axis=0) % 2)[None, None]
    calls = []
    original = model.predictor.forest.predict_probability

    def bounded(environment, state, **options):
        calls.append(len(state))
        return original(environment, state, **options)

    monkeypatch.setattr(model.predictor.forest, "predict_probability", bounded)
    output = model.predict(burned, env, channel_names=model.channel_names, boundary="zero")
    assert len(calls) == 2
    assert max(calls) <= 8192
    assert sum(calls) == np.count_nonzero(burned == 0)
    np.testing.assert_array_equal(output.probability.numpy(), 1 - burned)


def test_conservative_missing_environment_even_if_every_sample_burns(tmp_path):
    model, _ = _save(tmp_path, labels=1)
    burned, env = _grid(h=9, w=10)
    mask = np.ones_like(env, dtype=bool)
    mask[:, 1, 1] = False
    env[:, 1, 1] = np.nan
    # Original burns are rescued, even when their environmental input is absent.
    burned[0, 1, 1] = 1
    output = model.predict_cumulative(burned, env, channel_names=model.channel_names,
                                     feature_valid=mask, hours=[1, 2, 3], n_samples=2)
    assert bool(output.valid[:, 0, 1, 1].all())
    assert bool((output.probability[:, 0, 1, 1] == 0).all())
    assert not bool(output.valid[:, 0, 2, 2].any())
    assert not output.valid[2, 0, 3, 3]
    assert bool(torch.isnan(output.probability[:, 0, 2, 2]).all())


def test_initial_missing_state_fill_and_physical_temporal_padding(tmp_path):
    model, _ = _save(tmp_path, labels=1)
    burned, env = _grid((2,))
    valid = np.ones_like(burned, bool)
    valid[:, :, 2, 2] = False
    burned[:, :, 2, 2] = np.nan
    pixels = np.ones((7, 8), bool)
    pixels[-1] = False
    sample = dict(burned_area=burned, burned_area_valid=valid, features=env,
                  channel_names=model.channel_names, pixel_valid=pixels,
                  time_valid=np.array([True, False]))
    filled = model.predict_cumulative(sample, hours=[1, 2], n_samples=2)
    unknown = model.predict_cumulative(sample, hours=[1, 2], n_samples=2,
                                      missing_burned_area="unknown")
    assert filled.valid[0, 0, 0, 2, 2]
    assert not unknown.valid[0, 0, 0, 2, 2]
    assert not bool(filled.valid[:, :, :, -1].any())
    assert not bool(filled.valid[:, 1].any())
    assert filled.metadata["assumed_unburned_cells"] == 1


def test_saved_named_one_hot_reordering_forecast_and_validation(tmp_path):
    model, _ = _save(tmp_path, labels=1, channels=("temperature", "biome=1", "biome=2"))
    burned, env = _grid(channels=3)
    env[1] = 1
    env[2] = 0
    sample = dict(burned_area=burned, features=env[[2, 0, 1]],
                  channel_names=("biome=2", "temperature", "biome=1"))
    current = model.predict_cumulative(sample, hours=[1, 2], n_samples=3)
    forecast = dict(features=np.stack([sample["features"]] * 3), channel_names=sample["channel_names"])
    predicted = model.predict_cumulative(sample, environmental_forecast=forecast,
                                        hours=[1, 2], n_samples=3)
    torch.testing.assert_close(current.probability, predicted.probability, rtol=0, atol=0)
    invalid = {**sample, "features": sample["features"].copy()}
    invalid["features"][0, 0, 0] = 1
    with pytest.raises(ValueError, match="one-hot"):
        model.predict(invalid)
    # A caller's extra category outside the frozen vocabulary remains unknown.
    extra = np.concatenate((env, np.zeros((1, 7, 8), np.float32)), axis=0)
    extra[1:3, 0, 0] = 0
    extra[3, 0, 0] = 1
    unrecognized = model.predict(dict(burned_area=burned, features=extra,
                                     channel_names=(*model.channel_names, "biome=3")), boundary="zero")
    assert not unrecognized.valid[0, 0, 0]


@pytest.mark.parametrize("duration", [0, .5, 2, 6])
def test_no_unfitted_temporal_extrapolation(tmp_path, duration):
    model, _ = _save(tmp_path)
    burned, env = _grid()
    with pytest.raises(ValueError, match="dt_hours=1.0"):
        model.predict(burned, env, channel_names=model.channel_names, dt_hours=duration)
    if duration > 0:
        with pytest.raises(ValueError, match="fixed mode supports only hours=1"):
            model.predict_cumulative(burned, env, channel_names=model.channel_names,
                                     method="fixed", hours=duration)


def test_joblib_api_save_roundtrip_and_cpu_policy(tmp_path):
    model, _ = _save(tmp_path, metadata={"normalization_mean": [2, 0], "normalization_std": [3, 1], "source": "unit"})
    burned, env = _grid()
    controls = dict(channel_names=model.channel_names, hours=[1, 2], n_samples=3)
    expected = model.predict_cumulative(burned, env, **controls)
    destination = tmp_path / "copy.joblib"
    model.save(destination)
    restored = load_model(destination)
    assert model.contract == restored.contract
    assert restored.predictor.forest.metadata["source"] == "unit"
    torch.testing.assert_close(expected.probability, restored.predict_cumulative(burned, env, **controls).probability, rtol=0, atol=0)
    with pytest.raises(FileExistsError):
        model.save(destination)
    model.save(destination, overwrite=True)
    assert model.to("auto") is model
    with pytest.raises(ValueError, match="device='cpu'"):
        load_model(destination, device="cuda")
    with pytest.raises(ValueError, match="device='cpu'"):
        model.to("mps")
    with pytest.raises(ValueError, match=".joblib"):
        model.save(tmp_path / "bad.pt")
    fixed = model.predict_cumulative(burned, env, channel_names=model.channel_names,
                                    hours=1, method="fixed", boundary="zero")
    analytic = model.predict(burned, env, channel_names=model.channel_names, boundary="zero")
    torch.testing.assert_close(fixed.at(hours=1).probability, analytic.probability, rtol=0, atol=0)


@pytest.mark.parametrize("metadata", [
    {"normalization_mean": [0, 0]},
    {"normalization_mean": [0], "normalization_std": [1]},
    {"normalization_mean": [0, 0], "normalization_std": [1, 0]},
    {"normalization_mean": [0, float("nan")], "normalization_std": [1, 1]},
])
def test_invalid_saved_normalization_is_rejected(tmp_path, metadata):
    with pytest.raises(ValueError, match="normalization"):
        _save(tmp_path, metadata=metadata)


def test_nonbinary_inputs_and_unavailable_values(tmp_path):
    model, _ = _save(tmp_path)
    burned, env = _grid()
    burned[0, 1, 1] = .5
    with pytest.raises(ValueError, match="exactly 0 or 1"):
        model.predict(burned, env, channel_names=model.channel_names)
    valid = np.ones_like(burned, bool)
    valid[0, 1, 1] = False
    output = model.predict(burned, env, channel_names=model.channel_names,
                           burned_area_valid=valid, boundary="zero", missing_burned_area="unknown")
    assert not output.valid[0, 1, 1]
