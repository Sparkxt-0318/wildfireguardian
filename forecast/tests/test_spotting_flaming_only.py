"""Spotting emitters exclude old smoulder without changing local sources."""
from copy import deepcopy
import numpy as np
import pytest
import torch

from wildfire.burnout import FlamingWindow
from wildfire.meanfield import propagate_mean_field
from wildfire.models import StructuredKernelModel
from wildfire.survival import PerimeterSample, sample_forecast, sample_tensors


@pytest.fixture(autouse=True, scope="module")
def one_thread():
    before = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(before)


def sample(age):
    names = ["weather.wind_eastward_10m", "weather.wind_northward_10m", "weather.temperature_2m"]
    with torch.random.fork_rng():
        torch.manual_seed(0)
        model = StructuredKernelModel(3, 3, 2, 0., channel_names=names,
            residence_hours=6., spotting_radius=15).eval()
    environment = np.zeros((3, 45, 45), np.float32)
    environment[0] = 1
    initial = np.zeros((45, 45), bool)
    initial[30, 20] = True
    return model, PerimeterSample("MECHANISM_ONLY", "2021-01-01T00:00:00Z", 1.,
        environment, initial, initial.copy(), ~initial, np.ones(initial.shape), np.full(initial.shape, age))


@pytest.mark.parametrize("age", [6., 100.])
def test_old_smoulder_can_spread_locally_but_cannot_emit_long_range(age):
    model, case = sample(age)
    result, valid = sample_forecast(model, case)
    no_spot, _ = sample_forecast(model, case, use_spotting=False)
    assert valid[30, 30] and result[30, 30] == no_spot[30, 30] == 0
    assert result[30, 21] > 0 and no_spot[30, 21] > 0
    assert float(model.smoulder()) > 0


def test_young_sources_emit_and_match_shared_source_before_any_burnout():
    model, case = sample(0.)
    current, valid = sample_forecast(model, case)
    tensors = sample_tensors(case)
    def callback(source, step):
        return model.spot_rate(source, tensors["environment"])
    callback.source_radius = 15
    result = propagate_mean_field(model, tensors["initial"], tensors["environment"], [1.],
        channel_names=model.channel_names, boundary="zero", burnout=model.flaming_window(),
        initial_age_hours=tensors["age"], extra_rate_fn=callback)
    assert current[30, 30] > 0
    assert torch.equal(valid, result.valid[-1][0, 0])
    assert torch.equal(current, result.new_burn_probability[-1][0, 0])


@pytest.mark.parametrize("residence", [2., torch.tensor([[[[1., 3.]]]])])
def test_flaming_only_tracks_initial_age_and_increment_midpoints(residence):
    law = FlamingWindow(residence, .4)
    initial = torch.tensor([[[[.5, .5]]]])
    ages = torch.tensor([[[[5., 0.]]]])
    history = [(.5, torch.tensor([[[[.1, .2]]]])), (2.5, torch.tensor([[[[.3, .1]]]]))]
    current = initial + sum(value for _, value in history)
    clock = 3.
    r = torch.as_tensor(residence)
    expected = initial * (ages + clock < r)
    for time, value in history:
        expected += value * (clock - time < r)
    actual = law.flaming_source(initial, ages, history, clock, current=current)
    assert torch.equal(actual, expected)
    assert torch.all(law.source(initial, ages, history, clock, current=current) >= actual)


def test_flaming_only_callback_requires_an_explicit_residence_law():
    model, case = sample(0.)
    tensors = sample_tensors(case)
    def callback(source, step): return torch.zeros_like(source)
    callback.source_mode = "flaming_only"
    callback.source_radius = 0
    with pytest.raises(ValueError, match="flaming-window source law"):
        propagate_mean_field(model, tensors["initial"], tensors["environment"], [1.],
            channel_names=model.channel_names, boundary="zero", extra_rate_fn=callback)


def test_callback_source_mode_cannot_be_a_truthy_unrecognized_policy():
    model, case = sample(0.)
    tensors = sample_tensors(case)
    def callback(source, step): return torch.zeros_like(source)
    callback.source_mode = "invented"
    callback.source_radius = 0
    with pytest.raises(ValueError, match="source_mode"):
        propagate_mean_field(model, tensors["initial"], tensors["environment"], [1.],
            channel_names=model.channel_names, boundary="zero", extra_rate_fn=callback)
