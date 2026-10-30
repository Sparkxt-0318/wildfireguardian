"""A global spotting direction must retain its global input dependency."""
from copy import deepcopy
import numpy as np
import pytest
import torch

from wildfire.meanfield import propagate_mean_field
from wildfire.models import StructuredKernelModel
from wildfire.survival import PerimeterSample, sample_forecast, sample_tensors, step_durations


@pytest.fixture(autouse=True, scope="module")
def one_thread():
    before = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(before)


def fixture(*, wind_missing=False, temperature_missing=False, calm=False, radius=15, hours=1):
    names = ["weather.wind_eastward_10m", "weather.wind_northward_10m", "weather.temperature_2m"]
    with torch.random.fork_rng():
        torch.manual_seed(0)
        model = StructuredKernelModel(3, 3, 2, 0., channel_names=names, residence_hours=6,
                                      spotting_radius=radius).eval()
    environment = np.zeros((3, 45, 45), np.float32)
    environment[0] = 0 if calm else 1
    if wind_missing:
        environment[:2, 0, 0] = np.nan
    if temperature_missing:
        environment[2, 0, 0] = np.nan
    initial = np.zeros((45, 45), bool)
    initial[30, 20] = True
    sample = PerimeterSample("MECHANISM_ONLY", "2022-01-01T00:00:00Z", hours, environment,
        initial, initial.copy(), ~initial, np.ones(initial.shape), np.zeros(initial.shape))
    return model, sample


def test_remote_unknown_wind_removes_all_unobserved_spotting_targets():
    model, sample = fixture(wind_missing=True)
    probability, valid = sample_forecast(model, sample)
    assert not valid[30, 30]
    assert torch.isnan(probability[30, 30])
    assert not valid[~torch.from_numpy(sample.initial)].any()
    assert valid[30, 20] and probability[30, 20] == 0


@pytest.mark.parametrize("options", [dict(calm=True), dict(temperature_missing=True), dict(wind_missing=True, radius=0)])
def test_known_calm_nonwind_missingness_and_no_spotting_are_positive_controls(options):
    model, sample = fixture(**options)
    probability, valid = sample_forecast(model, sample)
    assert valid[30, 30] and torch.isfinite(probability[30, 30])


def test_standalone_spotting_rate_refuses_unknown_domain_wind():
    model, sample = fixture(wind_missing=True)
    tensors = sample_tensors(sample)
    with pytest.raises(ValueError, match="globally known wind"):
        model.spot_rate(tensors["initial"], tensors["environment"])


@pytest.mark.parametrize("missing_nonwind", [False, True])
def test_known_wind_guard_preserves_forward_and_parameter_gradients_with_fixed_source_law(missing_nonwind):
    model, sample = fixture(temperature_missing=missing_nonwind, hours=2)
    old = deepcopy(model)
    tensors = sample_tensors(sample)
    fv = torch.isfinite(tensors["environment"])
    environment = torch.where(fv, tensors["environment"], 0)

    def prior_callback(source, step):
        return old.spot_rate(source, environment, boundary="zero")
    prior_callback.source_radius = 15
    # Isolate availability metadata under the same corrected emitter law.
    # Historical smouldering-inclusive fits require their separate rerun.
    prior_callback.source_mode = "flaming_only"
    before = propagate_mean_field(old, tensors["initial"], environment, step_durations(sample.hours),
        channel_names=old.channel_names, p0_valid=torch.ones_like(tensors["initial"], dtype=torch.bool),
        feature_valid=fv, boundary="zero", burnout=old.flaming_window(),
        initial_age_hours=tensors["age"], extra_rate_fn=prior_callback)
    actual, valid = sample_forecast(model, sample)
    expected = before.new_burn_probability[-1][0, 0]
    assert torch.equal(valid, before.valid[-1][0, 0])
    assert torch.equal(torch.nan_to_num(actual), torch.nan_to_num(expected))
    torch.nan_to_num(actual).sum().backward()
    torch.nan_to_num(expected).sum().backward()
    for (name, parameter), (other_name, other) in zip(model.named_parameters(), old.named_parameters()):
        assert name == other_name
        assert (parameter.grad is None) == (other.grad is None)
        if parameter.grad is not None:
            assert torch.equal(parameter.grad, other.grad), name


@pytest.mark.parametrize("invalid", [torch.tensor(0.), torch.ones((2, 2), dtype=torch.bool)])
def test_global_dependency_metadata_must_have_boolean_broadcastable_shape(invalid):
    model, sample = fixture(radius=0)
    tensors = sample_tensors(sample)
    def callback(source, step): return torch.zeros_like(source)
    callback.source_radius = 0
    callback.global_feature_valid = invalid
    with pytest.raises(ValueError, match="global_feature_valid"):
        propagate_mean_field(model, tensors["initial"], tensors["environment"], [1.],
            channel_names=model.channel_names, boundary="zero", extra_rate_fn=callback)
