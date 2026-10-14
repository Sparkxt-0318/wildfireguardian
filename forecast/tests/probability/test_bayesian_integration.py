"""Independent checks for Bayesian averaging of frozen single-kernel models."""

from copy import deepcopy
from hashlib import sha256
import json
import sys

import numpy as np
import pytest
import torch

from wildfire import WildfireModel, load_model
from wildfire.cache import CachedSplit
from wildfire.heat import AffineGrid, CombustionParameters, WildfireHeatModel
from wildfire.models import build_kernel_model, kernel_model_configuration


CHANNELS = ["fixture.a", "fixture.b"]
TARGET = "currently unburned cell is burned at the exact next-hour snapshot"
TARGET_ALIASES = (
    TARGET,
    "unburned at t becomes burned at exactly t+3600s",
    "Currently unburned at t becomes burned at t+3600 seconds, using current t environmental context",
)


def _checkpoint(path, size, rate, mean, scale):
    model = build_kernel_model(2, size, "constant", hidden_channels=4, depth=1)
    # An independently specified common rate gives an analytic Bernoulli law.
    logit = rate + np.log(-np.expm1(-rate)) if rate > 0 else -1000.0
    with torch.no_grad():
        model.kernel_network.logits.fill_(float(logit))
    contract = {
        "format_version": 1, "architecture": "LearnedNonnegativeKernel",
        "in_channels": 2, "channels": CHANNELS.copy(), "kernel_size": size,
        "kernel_model": kernel_model_configuration(model), "dt_hours": 1.0,
        "center_rate": 0.0, "eligibility": "at_least_one_burned_neighbor",
        "target": TARGET, "output_link": "one_hour_exponential",
        "boundary": "unknown; complete interior patches only",
        "event_ids": ["train", "validation", "test"],
        "splits": {name: name for name in ("train", "validation", "test")},
    }
    torch.save({
        "contract": contract, "model_state_dict": model.state_dict(),
        "normalization_mean": torch.tensor(mean, dtype=torch.float32),
        "normalization_std": torch.tensor(scale, dtype=torch.float32),
        "best_epoch": size, "validation_brier": 0.1,
    }, path)
    return path


@pytest.fixture
def independent_components(tmp_path):
    return [
        _checkpoint(tmp_path / "k3.pt", 3, 0.3, [3.0, 4.0], [2.0, 5.0]),
        _checkpoint(tmp_path / "k5.pt", 5, 0.9, [-7.0, 8.0], [4.0, 9.0]),
    ]


@pytest.fixture
def calibration():
    n = 6
    environment = np.arange(n * 2 * 25, dtype=np.float32).reshape(n, 2, 5, 5) / 100
    burned = np.zeros((n, 1, 5, 5), dtype=np.float32)
    burned[:5, 0, 2, 3] = 1
    burned[[1, 3], 0, 0, 0] = 1
    data = CachedSplit(
        environment=environment, burned=burned,
        target=np.array([1, 0, 1, 0, 0, 1], dtype=np.float32),
        weight=np.array([1, 2, 4, 1, 3, 5], dtype=np.float64),
        event_index=np.ones(n, dtype=np.int64),
        time_utc=np.arange(n, dtype=np.int64) * 3600,
        row=np.zeros(n, dtype=np.int32), col=np.arange(n, dtype=np.int32),
    )
    metadata = {
        "channels": CHANNELS.copy(), "kernel_size": 5, "dt_hours": 1.0,
        "event_ids": ["train", "validation", "test"],
        "splits": {name: name for name in ("train", "validation", "test")},
        "eligibility": "at_least_one_burned_neighbor", "target": TARGET,
    }
    return data, metadata


@pytest.fixture
def prediction_inputs():
    environment = np.linspace(-1, 1, 2 * 11 * 11, dtype=np.float32).reshape(2, 11, 11)
    burned = np.zeros((1, 11, 11), dtype=np.float32)
    burned[0, 5, 5] = 1
    return burned, environment


def _fit(checkpoints, calibration, output, **options):
    from wildfire.train import fit_bayesian_model
    data, metadata = calibration
    return fit_bayesian_model(checkpoints, data, metadata, output, **options)


def _manual_posterior(data, priors, *, population_weighted=False, power=1.0):
    # The final no-contact row is outside the shared calibration population.
    counts = np.column_stack((np.ones(5), np.array([1, 2, 1, 2, 1])))
    probabilities = -np.expm1(-counts * np.array([0.3, 0.9]))
    labels = data.target[:5, None]
    terms = np.where(labels == 1, np.log(probabilities), np.log1p(-probabilities))
    if population_weighted:
        terms *= data.weight[:5, None] / data.weight[:5].mean()
    scores = np.log(priors) + power * terms.sum(axis=0)
    relative = np.exp(scores - scores.max())
    return relative / relative.sum()


def _assert_prediction_equal(left, right):
    for name in left.__dataclass_fields__:
        torch.testing.assert_close(getattr(left, name), getattr(right, name),
                                   rtol=0, atol=0, equal_nan=True)


@pytest.mark.parametrize("weighted,power", [(False, 1.0), (False, 0.5), (True, 0.25)])
def test_fit_uses_same_contact_rows_and_manual_bernoulli_evidence(
    independent_components, calibration, prediction_inputs, tmp_path, weighted, power,
):
    priors = np.array([0.4, 0.6])
    fitted = _fit(independent_components, calibration, tmp_path / "fitted",
                  prior_weights=priors, population_weighted=weighted, likelihood_power=power,
                  batch_size=2)
    data, _ = calibration
    posterior = _manual_posterior(data, priors, population_weighted=weighted, power=power)
    assert fitted.family == "mixture_exponential"
    assert fitted.contract["architecture"] == "BayesianModelAverage"
    burned, environment = prediction_inputs
    result = fitted.predict_details(burned, environment, channel_names=CHANNELS, boundary="zero")
    # (5,6) has one burned neighbor in both supports. (5,7) is outside K=3.
    expected_near = np.dot(posterior, -np.expm1(-np.array([0.3, 0.9])))
    expected_far = posterior[1] * -np.expm1(-0.9)
    assert result.probability[0, 5, 6].item() == pytest.approx(expected_near, abs=2e-6)
    assert result.probability[0, 5, 7].item() == pytest.approx(expected_far, abs=2e-6)
    assert result.probability[0, 5, 5].item() == 0
    assert result.probability[0, 0, 0].item() == 0
    # Mean rate followed by the exponential is a different, incorrect rule.
    wrong = -np.expm1(-np.dot(posterior, [0.3, 0.9]))
    assert abs(expected_near - wrong) > 1e-4


def test_embedded_checkpoint_reloads_after_source_deletion_and_saves_resident_state(
    independent_components, calibration, prediction_inputs, tmp_path,
):
    fitted = _fit(independent_components, calibration, tmp_path / "fitted",
                  prior_weights=[0.4, 0.6])
    burned, environment = prediction_inputs
    expected = fitted.predict_details(burned, environment, channel_names=CHANNELS)
    path = fitted.checkpoint_path
    assert fitted.checkpoint_sha256 == sha256(path.read_bytes()).hexdigest()
    for source in independent_components:
        source.unlink()
    loaded = load_model(path)
    _assert_prediction_equal(expected, loaded.predict_details(burned, environment, channel_names=CHANNELS))
    components = loaded.predictor.components
    torch.testing.assert_close(components[0].mean[:, 0, 0], torch.tensor([3.0, 4.0]))
    torch.testing.assert_close(components[1].mean[:, 0, 0], torch.tensor([-7.0, 8.0]))
    torch.testing.assert_close(components[0].std[:, 0, 0], torch.tensor([2.0, 5.0]))
    torch.testing.assert_close(components[1].std[:, 0, 0], torch.tensor([4.0, 9.0]))
    with torch.no_grad():
        components[0].model.kernel_network.logits.add_(0.2)
    changed = loaded.predict_details(burned, environment, channel_names=CHANNELS)
    assert not torch.equal(changed.probability, expected.probability)
    destination = loaded.save(tmp_path / "copied" / "mixture.pt")
    reloaded = WildfireModel.from_checkpoint(destination)
    _assert_prediction_equal(changed, reloaded.predict_details(burned, environment, channel_names=CHANNELS))
    with pytest.raises(FileExistsError):
        loaded.save(destination)
    # Access to a public contract must not mutate the resident mixture.
    copied = deepcopy(reloaded.contract)
    copied["channels"][0] = "wrong"
    assert reloaded.channel_names == tuple(CHANNELS)


def test_each_environment_dependent_member_uses_its_own_saved_normalization(
    independent_components, calibration, prediction_inputs, tmp_path,
):
    means = np.array([[3.0, 4.0], [-7.0, 8.0]])
    scales = np.array([[2.0, 5.0], [4.0, 9.0]])
    coefficients = np.array([[0.11, -0.07], [0.08, 0.12]])
    biases = np.array([-0.5, 0.2])
    for index, (path, size) in enumerate(zip(independent_components, (3, 5))):
        payload = torch.load(path, weights_only=True)
        model = build_kernel_model(2, size, "linear", hidden_channels=4, depth=1)
        with torch.no_grad():
            model.kernel_network.spatial.weight.copy_(
                torch.tensor(coefficients[index], dtype=torch.float32)[None, :, None, None]
                .expand(size * size, -1, 1, 1))
            model.kernel_network.spatial.bias.fill_(float(biases[index]))
        payload["model_state_dict"] = model.state_dict()
        payload["contract"]["kernel_model"] = kernel_model_configuration(model)
        torch.save(payload, path)
    data, _ = calibration
    branch_probability = []
    for index, size in enumerate((3, 5)):
        start = (5 - size) // 2
        patch_means = data.environment[:5, :, start:start + size, start:start + size].mean(axis=(2, 3))
        logits = ((patch_means - means[index]) / scales[index]) @ coefficients[index] + biases[index]
        rates = np.logaddexp(0, logits)
        counts = np.ones(5) if size == 3 else np.array([1, 2, 1, 2, 1])
        branch_probability.append(-np.expm1(-rates * counts))
    probabilities = np.column_stack(branch_probability)
    labels = data.target[:5, None]
    scores = np.log([0.3, 0.7]) + np.where(labels == 1, np.log(probabilities), np.log1p(-probabilities)).sum(axis=0)
    posterior = np.exp(scores - scores.max())
    posterior /= posterior.sum()
    fitted = _fit(independent_components, calibration, tmp_path / "linear", prior_weights=[0.3, 0.7])
    burned, environment = prediction_inputs
    environment[:] = np.array([1.2, -0.5], dtype=np.float32)[:, None, None]
    logits = (((np.array([1.2, -0.5]) - means) / scales) * coefficients).sum(axis=1) + biases
    rates = np.logaddexp(0, logits)
    expected = posterior @ (-np.expm1(-rates))
    result = fitted.predict_details(burned, environment, channel_names=CHANNELS)
    assert result.probability[0, 5, 6].item() == pytest.approx(expected, abs=2e-6)
    wrong_logits = (((np.array([1.2, -0.5]) - means[0]) / scales[0]) * coefficients).sum(axis=1) + biases
    wrong = posterior @ (-np.expm1(-np.logaddexp(0, wrong_logits)))
    assert abs(expected - wrong) > 1e-3


def test_probability_mask_requires_every_positive_mass_component(
    independent_components, calibration, prediction_inputs, tmp_path,
):
    fitted = _fit(independent_components, calibration, tmp_path / "fitted")
    burned, environment = prediction_inputs
    known = np.ones_like(burned, dtype=bool)
    # The unknown source (5,6) is outside the 3x3 support of target (5,4).
    known[0, 5, 6] = False
    small = fitted.predictor.components[0](
        torch.from_numpy(burned), torch.from_numpy(environment), channel_names=CHANNELS,
        burned_area_valid=torch.from_numpy(known), boundary="zero",
    )
    assert small.valid[0, 5, 4]
    filled = fitted.predict_details(burned, environment, channel_names=CHANNELS,
                                     burned_area_valid=known)
    assert filled.valid.all()
    assert filled.probability[0, 5, 4] > 0
    result = fitted.predict_details(burned, environment, channel_names=CHANNELS,
                                    burned_area_valid=known, boundary="zero",
                                    missing_burned_area="unknown")
    assert not result.valid[0, 5, 4]
    assert torch.isnan(result.probability[0, 5, 4])


def test_heat_conversion_preserves_bayesian_probability_and_masks(
    independent_components, calibration, prediction_inputs, tmp_path,
):
    fitted = _fit(independent_components, calibration, tmp_path / "fitted")
    physical = {
        "grid": AffineGrid.from_cell_size(10),
        "combustion": CombustionParameters(1, 18e6, 900),
        "radiative_fraction": 0.3, "emission_height_m": 5,
    }
    burned, environment = prediction_inputs
    expected = fitted.predict_details(burned, environment, channel_names=CHANNELS,
                                       boundary="unknown", missing_burned_area="unknown")
    resident = fitted.heat_model(**physical)
    loaded = WildfireHeatModel.from_checkpoint(fitted.checkpoint_path, **physical)
    assert resident.predictor is fitted.predictor
    for heat in (resident, loaded):
        result = heat.predict_details(burned, environment, channel_names=CHANNELS)
        np.testing.assert_allclose(result.new_burn_probability, expected.probability[0].numpy(), equal_nan=True)
        np.testing.assert_array_equal(result.original_probability_valid, expected.valid[0].numpy())
        assert result.metadata["predictor"]["architecture"] == "BayesianModelAverage"


def test_fit_rejects_zero_evidence_without_silently_clipping_probabilities(calibration, tmp_path):
    checkpoints = [
        _checkpoint(tmp_path / "zero3.pt", 3, 0, [0, 0], [1, 1]),
        _checkpoint(tmp_path / "zero5.pt", 5, 0, [0, 0], [1, 1]),
    ]
    with pytest.raises(ValueError, match="[Ee]vidence|[Ll]ikelihood|impossible"):
        _fit(checkpoints, calibration, tmp_path / "impossible")


def test_fit_rejects_different_channel_contracts(independent_components, calibration, tmp_path):
    path = independent_components[1]
    payload = torch.load(path, weights_only=True)
    payload["contract"]["channels"].reverse()
    torch.save(payload, path)
    with pytest.raises(ValueError, match="channel|schema|contract"):
        _fit(independent_components, calibration, tmp_path / "different_schema")


@pytest.mark.parametrize("mismatch,message", [
    ("endpoint", "endpoint"), ("support", "kernel_size"), ("training_rows", "wrong cache split"),
])
def test_fit_rejects_false_calibration_contracts(
    independent_components, calibration, tmp_path, mismatch, message,
):
    data, metadata = deepcopy(calibration)
    if mismatch == "endpoint":
        metadata["target"] = "currently active flame occupancy"
    elif mismatch == "support":
        metadata["kernel_size"] = 7
    else:
        data.event_index[:] = 0
    output = tmp_path / "rejected"
    with pytest.raises(ValueError, match=message):
        _fit(independent_components, (data, metadata), output)
    assert not output.exists()


@pytest.mark.parametrize("first_alias", range(3))
def test_fit_accepts_all_maintained_endpoint_aliases_across_components_and_cache(
    independent_components, calibration, tmp_path, first_alias,
):
    from wildfire.schema import probability_target_id
    data, metadata = deepcopy(calibration)
    for index, path in enumerate(independent_components):
        payload = torch.load(path, weights_only=True)
        payload["contract"]["target"] = TARGET_ALIASES[(first_alias + index) % 3]
        torch.save(payload, path)
    metadata["target"] = TARGET_ALIASES[(first_alias + 2) % 3]
    fitted = _fit(independent_components, (data, metadata), tmp_path / "aliases")
    assert probability_target_id(fitted.contract) == "first_new_cumulative_burn_at_exact_next_hour"
    assert fitted.contract["target"] == TARGET_ALIASES[first_alias]
    assert fitted.family == "mixture_exponential"


@pytest.mark.parametrize("target", [
    "unburned at t becomes burned at exactly t+3600s with active flames",
    "currently unburned cell is burned at the exact next-hour snapshot averaged over the hour",
])
def test_fit_rejects_component_targets_outside_exact_maintained_aliases(
    independent_components, calibration, tmp_path, target,
):
    payload = torch.load(independent_components[1], weights_only=True)
    payload["contract"]["target"] = target
    torch.save(payload, independent_components[1])
    with pytest.raises(ValueError, match="endpoint"):
        _fit(independent_components, calibration, tmp_path / "different_endpoint")


@pytest.mark.parametrize("member_split,message", [
    ("test", "designated test fires"), ("train", "training-only fires"),
])
def test_component_designated_fires_cannot_be_relabelled_as_calibration(
    independent_components, calibration, tmp_path, member_split, message,
):
    # The caller's metadata declares these rows as validation, but one source
    # member's own saved contract establishes their actual training/test role.
    payload = torch.load(independent_components[1], weights_only=True)
    payload["contract"]["splits"]["validation"] = member_split
    torch.save(payload, independent_components[1])
    output = tmp_path / "leaking"
    with pytest.raises(ValueError, match=message):
        _fit(independent_components, calibration, output)
    assert not output.exists()


def test_cli_needs_training_identities_and_validation_outcomes_only(
    independent_components, calibration, tmp_path, monkeypatch, capsys,
):
    from wildfire.train import bayesian_main
    data, metadata = deepcopy(calibration)
    # A broader input cache may include no-contact rows; shared contact
    # membership is recomputed before any model receives evidence.
    metadata["eligibility"] = "all_known_currently_unburned_targets"
    metadata["target"] = TARGET_ALIASES[2]
    source_metadata_hashes = ["1" * 64, "2" * 64]
    for path, digest in zip(independent_components, source_metadata_hashes):
        payload = torch.load(path, weights_only=True)
        payload["contract"]["cache_metadata_sha256"] = digest
        payload["contract"]["target"] = TARGET_ALIASES[1]
        torch.save(payload, path)
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "metadata.json").write_text(json.dumps(metadata))
    np.savez_compressed(cache / "validation.npz", **vars(data))
    # Training labels/features deliberately do not exist, nor does test.npz.
    np.savez_compressed(cache / "train.npz",
                        event_index=np.zeros(1, dtype=np.int64),
                        time_utc=np.zeros(1, dtype=np.int64),
                        row=np.zeros(1, dtype=np.int32), col=np.zeros(1, dtype=np.int32))
    output = tmp_path / "cli"
    monkeypatch.setattr(sys, "argv", [
        "mix-bayesian", "--checkpoints", *map(str, independent_components),
        "--cache", str(cache), "--output", str(output), "--batch-size", "2",
    ])
    bayesian_main()
    printed = json.loads(capsys.readouterr().out)
    assert printed["kernel_sizes"] == [3, 5]
    assert printed["checkpoint"] == str(output / "checkpoint.pt")
    fitted = load_model(output / "checkpoint.pt")
    assert fitted.family == "mixture_exponential"
    assert fitted.contract["bayesian"]["test_used_for_weights"] is False
    assert "cache_metadata_sha256" not in fitted.contract
    assert [item["cache_metadata_sha256"] for item in fitted.contract["bayesian"]["components"]] == source_metadata_hashes
    report = json.loads((output / "metrics.json").read_text())
    current_metadata_hash = sha256((cache / "metadata.json").read_bytes()).hexdigest()
    assert report["verification"]["calibration_cache_metadata_file_sha256"] == current_metadata_hash
    assert report["verification"]["metadata_file_matches_component_cache"] == [False, False]
    assert [item["cache_metadata_sha256"] for item in report["evidence"]["components"]] == source_metadata_hashes
    with np.load(output / "calibration_predictions.npz", allow_pickle=False) as saved:
        np.testing.assert_array_equal(saved["source_index"], np.arange(5))
