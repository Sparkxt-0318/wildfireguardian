"""Mean-field propagation: exact one-step expectation, masks and rollout envelope."""
import math

import torch

from wildfire.meanfield import kernel_source_rate, mean_field_step, propagate_mean_field
from wildfire.models import (
    LearnedNonnegativeKernel, MixedNonnegativeKernel, TrainedBurnModel, new_burn_probability,
)
from wildfire.rollout import simulate


class KernelProvider:
    """Fixed kernels standing in for a generator (inputs are ignored)."""

    def __init__(self, kernels):
        self.kernels = kernels

    def kernel_rates(self, environment, feature_valid=None, *, boundary="zero"):
        return self.kernels


def _random_kernels(generator, shape, k=3, dtype=torch.float64):
    kernels = torch.rand((*shape, k * k, 6, 7), generator=generator, dtype=dtype)
    kernels[..., k * k // 2, :, :] = 0
    return kernels


def test_step_equals_new_burn_probability_for_binary_states():
    g = torch.Generator().manual_seed(3)
    kernels = _random_kernels(g, (2,))
    burned = (torch.rand((2, 1, 6, 7), generator=g) < 0.3).double()
    for dt in (1.0, 0.37, 2.5):
        reference = new_burn_probability(burned, kernels, dt_hours=dt, boundary="zero")
        step = mean_field_step(burned, kernels, dt)
        new = torch.where(burned == 1, torch.zeros_like(step), step - burned)
        assert reference.valid.all()
        assert torch.allclose(new, reference.probability, rtol=0, atol=1e-9)
        result = propagate_mean_field(KernelProvider(kernels), burned, torch.zeros(2, 1, 6, 7, dtype=torch.float64),
                                      [dt], boundary="zero")
        assert torch.allclose(result.new_burn_probability[0], reference.probability, rtol=0, atol=1e-9)
        assert torch.equal(result.valid[0], reference.valid)


def test_step_matches_released_c651_family_in_float64():
    torch.manual_seed(0)
    model = MixedNonnegativeKernel(5, kernel_sizes=(3, 5), hidden_channels=4).double().eval()
    channels = tuple(f"c{i}" for i in range(5))
    contract = {"channels": list(channels), "eligibility": "at_least_one_burned_neighbor"}
    wrapper = TrainedBurnModel(model, torch.zeros(5, dtype=torch.float64), torch.ones(5, dtype=torch.float64),
                               contract, 1).double().eval()
    environment = torch.randn(1, 5, 9, 10, dtype=torch.float64)
    burned = torch.zeros(1, 1, 9, 10, dtype=torch.float64)
    burned[..., 3:5, 4:6] = 1
    valid = torch.ones_like(burned, dtype=torch.bool)
    features = torch.ones_like(environment, dtype=torch.bool)
    with torch.no_grad():
        reference = wrapper(burned, environment, channel_names=channels, burned_area_valid=valid,
                            feature_valid=features, dt_hours=1.0, boundary="zero")
        result = propagate_mean_field(wrapper, burned, environment, [1.0], channel_names=channels,
                                      p0_valid=valid, feature_valid=features, boundary="zero")
    covered = reference.valid & result.valid[0]
    assert bool(covered.any())
    assert torch.allclose(result.new_burn_probability[0][covered], reference.probability[covered], rtol=0, atol=1e-9)


def test_unknown_source_never_contributes_and_dependent_target_is_unknown():
    k = 3
    kernels = torch.zeros(1, k * k, 1, 5, dtype=torch.float64)
    # Target column 2 reads the source to its right (dx = +1), offset index (0, +1) = 5.
    kernels[0, 5, 0, 2] = 0.8
    # Target column 0 reads the source to its right as well.
    kernels[0, 5, 0, 0] = 0.4
    p0 = torch.tensor([[[[1.0, 1.0, 0.0, 0.0, 0.0]]]], dtype=torch.float64)
    known = torch.ones_like(p0, dtype=torch.bool)
    known[..., 3] = False  # the source of target 2 is unknown
    outputs = []
    for hidden_value in (0.0, 1.0):
        state = p0.clone()
        state[..., 3] = hidden_value
        result = propagate_mean_field(KernelProvider(kernels), state, torch.zeros(1, 1, 1, 5, dtype=torch.float64),
                                      [1.0, 1.0], p0_valid=known, boundary="zero")
        outputs.append(result)
        assert not bool(result.valid[0, 0, 0, 0, 2])  # depends on the unknown source
        assert not bool(result.valid[0, 0, 0, 0, 3])  # unknown itself
        assert torch.isnan(result.new_burn_probability[0, 0, 0, 0, 2])
    for a, b in zip(outputs[0].new_burn_probability.flatten(), outputs[1].new_burn_probability.flatten()):
        assert (math.isnan(a) and math.isnan(b)) or a == b


def test_validity_envelope_equals_rollout_coverage():
    torch.manual_seed(1)
    model = LearnedNonnegativeKernel(3, kernel_size=3, architecture="cnn", hidden_channels=4).eval()
    channels = ("a", "b", "c")
    contract = {"channels": list(channels)}
    wrapper = TrainedBurnModel(model, torch.zeros(3), torch.ones(3), contract, 1).eval()
    environment = torch.randn(1, 3, 8, 8)
    features = torch.ones_like(environment, dtype=torch.bool)
    features[0, :, 0, 6] = False
    burned = torch.zeros(1, 1, 8, 8)
    burned[..., 4, 4] = 1
    valid = torch.ones_like(burned, dtype=torch.bool)
    valid[..., 2, 1] = False
    for boundary in ("unknown", "zero"):
        mc = simulate(wrapper, burned, environment, channel_names=channels, burned_area_valid=valid,
                      feature_valid=features, hours=(1.0, 2.0, 3.0), n_samples=4, seed=0,
                      trajectory_batch_size=4, boundary=boundary)
        with torch.no_grad():
            mf = propagate_mean_field(wrapper, burned, environment, [1.0, 1.0, 1.0], channel_names=channels,
                                      p0_valid=valid, feature_valid=features, boundary=boundary)
        for index in range(3):
            assert torch.equal(mc[index]["details"].valid, mf.valid[index])


def test_mean_field_is_differentiable_and_monotone():
    kernels = _random_kernels(torch.Generator().manual_seed(5), (1,)).requires_grad_(True)
    p0 = torch.zeros(1, 1, 6, 7, dtype=torch.float64)
    p0[..., 3, 3] = 1
    result = propagate_mean_field(KernelProvider(kernels), p0, torch.zeros(1, 1, 6, 7, dtype=torch.float64),
                                  [1.0] * 4, boundary="zero")
    steps = result.burned_probability
    assert bool((steps[1:] >= steps[:-1] - 1e-15).all())
    steps[-1].sum().backward()
    assert kernels.grad is not None and bool(torch.isfinite(kernels.grad).all())


def test_kernel_source_rate_convention():
    kernels = torch.zeros(1, 9, 3, 3, dtype=torch.float64)
    kernels[0, 1, 1, 1] = 2.0  # offset (-1, 0): the source one row above the centre
    source = torch.zeros(1, 1, 3, 3, dtype=torch.float64)
    source[0, 0, 0, 1] = 1.0
    assert float(kernel_source_rate(kernels, source)[0, 0, 1, 1]) == 2.0
