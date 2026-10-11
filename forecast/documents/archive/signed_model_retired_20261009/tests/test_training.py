"""Independent checks of raw training and clipped evaluation semantics."""

import json

import numpy as np
import pytest
import torch

from wildfire_burned_area_hourly.probability_model.train import CachedSplit, brier, fit_normalization
from wildfire_burned_area_hourly.probability_model.direct_convolution import train as training_module
from wildfire_burned_area_hourly.probability_model.direct_convolution.inference import load_trained_model
from wildfire_burned_area_hourly.probability_model.direct_convolution.train import clipped_probability, fit_uniform_linear, parser, raw_score_diagnostics, train, training_loss


def make_split(kernel_size=3, n=8, feature_shift=0.0, event_index=0):
    rng = np.random.default_rng(91 + event_index)
    environment = (rng.normal(size=(n, 2, kernel_size, kernel_size)) + feature_shift).astype(np.float32)
    burned = np.zeros((n, 1, kernel_size, kernel_size), dtype=np.float32)
    offsets = np.arange(kernel_size**2)
    offsets = offsets[offsets != kernel_size**2 // 2]
    for row in range(n):
        burned[row, 0].flat[offsets[:1 + row % len(offsets)]] = 1
    target = (np.arange(n) % 3 == 0).astype(np.float32)
    return CachedSplit(
        environment=environment, burned=burned, target=target,
        weight=np.where(target == 1, 1.0, 4.0).astype(np.float64),
        event_index=np.full(n, event_index, dtype=np.int64),
        time_utc=np.arange(n, dtype=np.int64) * 3600,
        row=np.full(n, kernel_size // 2, dtype=np.int32),
        col=np.arange(n, dtype=np.int32) + kernel_size // 2,
    )


@pytest.mark.parametrize("kernel_size", [3, 5, 7, 9])
def test_uniform_signed_initializer_is_exact_raw_weighted_least_squares(kernel_size):
    data = make_split(kernel_size)
    fitted = fit_uniform_linear(data)
    n = data.neighbor_count.astype(np.float64)
    expected = sum(w * count * y for w, count, y in zip(data.weight, n, data.target)) / sum(
        w * count**2 for w, count in zip(data.weight, n))
    assert fitted["per_burned_neighbor_coefficient"] == pytest.approx(expected, abs=1e-15)
    assert fitted["fitted_partition"] == "train"
    assert np.dot(data.weight, n * (expected * n - data.target)) == pytest.approx(0, abs=1e-12)
    assert fitted["train_raw_brier"] <= brier(data.target, (expected + .01) * n, data.weight)
    assert fitted["train_raw_brier"] <= brier(data.target, (expected - .01) * n, data.weight)


def test_training_loss_keeps_out_of_range_scores_and_their_gradients():
    raw = torch.tensor([-2.0, 2.0, 0.4], dtype=torch.float64, requires_grad=True)
    y = torch.tensor([1.0, 0.0, 1.0], dtype=torch.float64)
    weight = torch.tensor([1.0, 5.0, 2.0], dtype=torch.float64)
    prevalence = float((weight * y).sum() / weight.sum())
    mean_weight = float(weight.mean())
    loss = training_loss(raw, y, weight, mean_weight, prevalence)
    expected = sum(w * (p - target)**2 for w, p, target in zip(weight, raw, y)) / weight.sum() / prevalence
    torch.testing.assert_close(loss, expected)
    loss.backward()
    analytic = 2 * weight * (raw.detach() - y) / weight.sum() / prevalence
    torch.testing.assert_close(raw.grad, analytic)
    assert raw.grad[0] < 0 and raw.grad[1] > 0
    clipped = raw.detach().clone().requires_grad_()
    training_loss(clipped.clamp(0, 1), y, weight, mean_weight, prevalence).backward()
    assert clipped.grad[:2].tolist() == [0.0, 0.0]


def test_raw_diagnostics_and_probability_metrics_preserve_ipw_clipping_effect():
    data = make_split(n=4)
    raw = np.array([-.25, 1.5, 0.0, 1.0], dtype=np.float32)
    p = clipped_probability(raw)
    np.testing.assert_array_equal(p, [0, 1, 0, 1])
    np.testing.assert_array_equal(raw, [-.25, 1.5, 0, 1])
    d = raw_score_diagnostics(data, raw)
    assert d["below_zero_sample_count"] == d["above_one_sample_count"] == 1
    assert d["clipped_sample_fraction"] == .5
    assert d["below_zero_population_fraction"] == pytest.approx(data.weight[0] / data.weight.sum())
    assert d["above_one_population_fraction"] == pytest.approx(data.weight[1] / data.weight.sum())
    assert d["raw_brier"] > d["clipped_brier"]
    assert d["clipped_brier"] == brier(data.target, p, data.weight)
    assert d["raw_scores_are_probabilities"] is False


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_evaluation_rejects_nonfinite_scores(bad):
    with pytest.raises(ValueError, match="nonfinite"):
        clipped_probability(np.array([0.2, bad], dtype=np.float32))


@pytest.mark.parametrize("kernel_size", [3, 5, 7, 9])
def test_end_to_end_selects_clipped_validation_then_reads_test_and_reload(tmp_path, monkeypatch, kernel_size):
    cache, output = tmp_path / "cache", tmp_path / "fitted"
    cache.mkdir()
    data = {name: make_split(kernel_size, feature_shift=shift, event_index=index)
            for index, (name, shift) in enumerate((("train", 0), ("validation", 100), ("test", -100)))}
    metadata = {
        "channels": ["fixture.a", "fixture.b"], "kernel_size": kernel_size, "dt_hours": 1.0,
        "event_ids": ["train_fire", "validation_fire", "test_fire"],
        "splits": {"train_fire": "train", "validation_fire": "validation", "test_fire": "test"},
        "eligibility": "at_least_one_burned_neighbor",
    }
    (cache / "metadata.json").write_text(json.dumps(metadata))
    for name, split in data.items():
        np.savez_compressed(cache / f"{name}.npz", **vars(split))
    real_load = training_module.load_split
    loading = []

    def checked_load(directory, name, cache_metadata):
        loading.append(name)
        if name == "test":
            assert (output / "checkpoint.pt").exists()
            assert len(json.loads((output / "history.json").read_text())) == 2
        return real_load(directory, name, cache_metadata)

    monkeypatch.setattr(training_module, "load_split", checked_load)
    args = parser().parse_args([
        "--data-dir", str(cache), "--output-dir", str(output), "--device", "cpu",
        "--epochs", "2", "--patience", "2", "--batch-size", "4", "--hidden-channels", "3", "--threads", "1",
    ])
    metrics = train(args)
    assert loading == ["train", "validation", "test"]
    history = json.loads((output / "history.json").read_text())
    selected = min(history, key=lambda record: record["validation_clipped_brier"])
    assert metrics["selection"]["best_epoch"] == selected["epoch"]
    assert metrics["selection"]["test_used_for_selection"] is False
    saved = torch.load(output / "checkpoint.pt", weights_only=True)
    expected_mean, expected_std = fit_normalization(data["train"])
    np.testing.assert_array_equal(saved["normalization_mean"].numpy(), expected_mean)
    np.testing.assert_array_equal(saved["normalization_std"].numpy(), expected_std)
    assert saved["contract"]["training_clipping"] is False
    assert saved["contract"]["output_link"] == "identity"
    fitted = load_trained_model(output / "checkpoint.pt")
    for name, split in data.items():
        with np.load(output / f"{name}_predictions.npz") as a:
            np.testing.assert_array_equal(a["p"], np.clip(a["p_raw"], 0, 1))
            np.testing.assert_array_equal(a["w"], split.weight)
            np.testing.assert_array_equal(a["y"], split.target)
            np.testing.assert_array_equal(a["event_index"], split.event_index)
            assert metrics["splits"][name]["raw_score_diagnostics"]["raw_brier"] == brier(a["y"], a["p_raw"], a["w"])
            assert metrics["splits"][name]["models"]["learned_environment_kernel"]["all_eligible"]["brier"] == brier(
                a["y"], a["p"], a["w"])
            with torch.no_grad():
                public = fitted(torch.from_numpy(split.burned), torch.from_numpy(split.environment),
                                channel_names=metadata["channels"])
            np.testing.assert_allclose(public.raw_score[:, 0, kernel_size // 2, kernel_size // 2].numpy(),
                                       a["p_raw"], rtol=0, atol=1e-6)
    with pytest.raises(FileExistsError):
        train(args)
