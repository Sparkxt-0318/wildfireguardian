"""Prepared M548 transitions must preserve the ordinary fitted forward path."""
from copy import deepcopy

import pytest
import torch

from wildfire.models import (
    BurnProbability, MixedNonnegativeKernel, NeuralMixedNonnegativeKernel,
    TrainedBurnModel, build_kernel_model,
)
from wildfire.rollout_cache import prepare_transition


@pytest.fixture(autouse=True)
def few_threads():
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(previous)


def model(dtype=torch.float32, *, eligibility=True, categorical=False, kernel=None):
    channels = ["fixture.a", "fixture.b"]
    contract = {"channels": channels,
                "eligibility": "at_least_one_burned_neighbor" if eligibility else "all_known"}
    if categorical:
        channels = ["fixture.fuel=1", "fixture.fuel=2"]
        contract.update(channels=channels, source_channels=["fixture.fuel"],
            channel_info=[dict(name=name, source_channel="fixture.fuel",
                               encoding="one_hot", class_code=index+1)
                          for index, name in enumerate(channels)],
            categorical_encoding="one_hot", categorical_classes={"fixture.fuel": [1, 2]},
            channel_groups={"fixture.fuel": [0, 1]})
    with torch.random.fork_rng():
        torch.manual_seed(809)
        kernel = kernel or MixedNonnegativeKernel(2, (3, 5), hidden_channels=3)
        result = TrainedBurnModel(kernel, torch.tensor([1.5, -2.]),
            torch.tensor([2., 4.]), contract, 1).to(dtype=dtype).eval()
    return result


def inputs(dtype, batch=4):
    generator = torch.Generator().manual_seed(34)
    environment = torch.randn(2, 13, 14, generator=generator, dtype=dtype)
    feature_valid = torch.ones_like(environment, dtype=torch.bool)
    feature_valid[0, 7, 8] = False
    environment[1, 9, 4] = torch.nan
    states = (torch.rand(batch, 1, 13, 14, generator=generator) < .15).to(dtype)
    burned_valid = torch.ones_like(states, dtype=torch.bool)
    burned_valid[::2, 0, 6, 5] = False
    states[::2, 0, 6, 5] = torch.nan
    return environment, feature_valid, states, burned_valid


def equal_prediction(actual, expected):
    assert isinstance(actual, BurnProbability)
    for name in ("probability", "valid", "rate", "rate_valid"):
        torch.testing.assert_close(getattr(actual, name), getattr(expected, name),
                                   rtol=0, atol=0, equal_nan=True)


@pytest.mark.parametrize("dtype", [torch.float32, torch.float64])
@pytest.mark.parametrize("boundary", ["unknown", "zero"])
@pytest.mark.parametrize("duration", [0., .25, 1.])
@pytest.mark.parametrize("eligibility", [False, True])
def test_cached_transition_is_bitwise_equal_with_varying_states_masks_and_durations(
    dtype, boundary, duration, eligibility,
):
    member = model(dtype, eligibility=eligibility)
    environment, feature_valid, states, burned_valid = inputs(dtype)
    before = torch.random.get_rng_state().clone()
    prepared = prepare_transition(member, environment, feature_valid,
        channel_names=member.channel_names, batch_size=4, boundary=boundary)
    assert prepared is not None
    # Reusing the prepared environment across different absorbing binary states
    # must retain all ordinary environmental and burned-state coverage rules.
    for iteration in range(3):
        states[:, 0, 2+iteration, 3+iteration] = 1
        with torch.inference_mode():
            expected = member(states, environment.unsqueeze(0).expand(4, -1, -1, -1),
                channel_names=member.channel_names, burned_area_valid=burned_valid,
                feature_valid=feature_valid.unsqueeze(0).expand(4, -1, -1, -1),
                boundary=boundary, dt_hours=duration)
        actual = prepared(states, burned_valid, duration)
        equal_prediction(actual, expected)
        assert not actual.probability.requires_grad
    assert torch.equal(torch.random.get_rng_state(), before)


def test_preparation_keeps_full_original_batch_shape_and_only_generates_once(monkeypatch):
    member = model()
    environment, feature_valid, states, burned_valid = inputs(torch.float32, batch=32)
    seen = []
    original = member.model._kernels
    def record(clean):
        seen.append((tuple(clean.shape), torch.is_inference_mode_enabled()))
        return original(clean)
    monkeypatch.setattr(member.model, "_kernels", record)
    prepared = prepare_transition(member, environment[None], feature_valid[None],
        channel_names=member.channel_names, batch_size=32, boundary="zero")
    assert seen == [((32, 2, 13, 14), True)]
    for duration in (1., 1., .5):
        result = prepared(states, burned_valid, duration)
        assert not result.probability.requires_grad
    assert len(seen) == 1


@pytest.mark.parametrize("target", ["wrapper", "kernel", "branch", "generator"])
@pytest.mark.parametrize("pre", [False, True])
def test_local_forward_hooks_fall_back_without_bypassing_instrumentation(target, pre):
    member = model()
    modules = {"wrapper": member, "kernel": member.model,
        "branch": member.model.branches["3"],
        "generator": member.model.branches["3"].kernel_network}
    module = modules[target]
    handle = (module.register_forward_pre_hook(lambda *args: None) if pre
              else module.register_forward_hook(lambda *args: None))
    try:
        assert prepare_transition(member, torch.zeros(2, 6, 7), None,
            channel_names=member.channel_names, batch_size=2, boundary="zero") is None
    finally:
        handle.remove()


@pytest.mark.parametrize("pre", [False, True])
def test_global_forward_hooks_fall_back(pre):
    member = model()
    registry = torch.nn.modules.module
    handle = (registry.register_module_forward_pre_hook(lambda *args: None) if pre
              else registry.register_module_forward_hook(lambda *args: None))
    try:
        assert prepare_transition(member, torch.zeros(2, 6, 7), None,
            channel_names=member.channel_names, batch_size=2, boundary="zero") is None
    finally:
        handle.remove()


@pytest.mark.parametrize("family", ["single", "neural", "unfitted", "subclass", "training"])
def test_unsupported_models_keep_original_forward_path(family):
    if family == "single":
        member = model(kernel=build_kernel_model(2, 3))
    elif family == "neural":
        member = model(kernel=NeuralMixedNonnegativeKernel(2, (3, 5)))
    elif family == "unfitted":
        member = MixedNonnegativeKernel(2, (3, 5)).eval()
    elif family == "subclass":
        class CustomizedMixed(MixedNonnegativeKernel):
            pass
        member = model(kernel=CustomizedMixed(2, (3, 5)))
    else:
        member = model().train()
    assert prepare_transition(member, torch.zeros(2, 6, 7), None,
        channel_names=("fixture.a", "fixture.b"), batch_size=2, boundary="zero") is None


def test_channel_and_one_hot_validation_is_retained():
    member = model(categorical=True)
    environment = torch.zeros(2, 6, 7)
    with pytest.raises(ValueError, match="channel names/order"):
        prepare_transition(member, environment, None,
            channel_names=tuple(reversed(member.channel_names)), batch_size=2, boundary="zero")
    with pytest.raises(ValueError, match="one-hot"):
        prepare_transition(member, environment, None,
            channel_names=member.channel_names, batch_size=2, boundary="zero")
    environment[0] = 1
    environment[0, 2, 3] = .25
    feature_valid = torch.ones_like(environment, dtype=torch.bool)
    feature_valid[:, 2, 3] = False
    prepared = prepare_transition(member, environment, feature_valid,
        channel_names=member.channel_names, batch_size=2, boundary="zero")
    states = torch.zeros(2, 1, 6, 7)
    states[:, :, 2, 3] = 1
    known = torch.ones_like(states, dtype=torch.bool)
    result = prepared(states, known, 1.)
    assert result.valid[:, :, 2, 3].all() and result.probability[:, :, 2, 3].eq(0).all()
    with torch.inference_mode():
        expected = member(states, environment[None].expand(2, -1, -1, -1),
            channel_names=member.channel_names, burned_area_valid=known,
            feature_valid=feature_valid[None].expand(2, -1, -1, -1), boundary="zero")
    equal_prediction(result, expected)


@pytest.mark.parametrize("batch_size", [True, 0, -1, 1.5])
def test_invalid_batch_size_rejected(batch_size):
    member = model()
    with pytest.raises(ValueError, match="batch_size"):
        prepare_transition(member, torch.zeros(2, 6, 7), None,
            channel_names=member.channel_names, batch_size=batch_size, boundary="zero")


@pytest.mark.parametrize("singleton", [False, True])
def test_mask_must_match_complete_environment_shape(singleton):
    member = model()
    environment = torch.zeros(2, 6, 7)
    if singleton:
        environment = environment[None]
    with pytest.raises(ValueError, match="exactly match"):
        prepare_transition(member, environment, torch.ones(1, 6, 7, dtype=torch.bool),
            channel_names=member.channel_names, batch_size=2, boundary="zero")


def test_state_validation_and_original_batch_size_remain_required():
    member = model()
    prepared = prepare_transition(member, torch.zeros(2, 6, 7), None,
        channel_names=member.channel_names, batch_size=2, boundary="zero")
    with pytest.raises(ValueError, match="share leading"):
        prepared(torch.zeros(1, 1, 6, 7), None, 1.)
    states = torch.zeros(2, 1, 6, 7)
    states[0, 0, 2, 3] = .5
    with pytest.raises(ValueError, match="exactly 0 or 1"):
        prepared(states, None, 1.)


def test_preparation_never_changes_model_parameters_or_buffers():
    member = model()
    before = deepcopy(member.state_dict())
    prepared = prepare_transition(member, torch.zeros(2, 6, 7), None,
        channel_names=member.channel_names, batch_size=2, boundary="zero")
    prepared(torch.zeros(2, 1, 6, 7), None, .5)
    for name, value in member.state_dict().items():
        torch.testing.assert_close(value, before[name], rtol=0, atol=0)
