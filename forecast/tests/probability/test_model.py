"""Semantic checks for the probability that an unburned cell becomes burned."""

import math

import pytest
import torch
from torch import nn

from wildfire.models import EnvironmentConditionedConvolution
from wildfire.models import new_burn_probability


def _kernels(burned, kernel_size=3):
    return torch.zeros(
        (*burned.shape[:-3], kernel_size**2, *burned.shape[-2:]),
        dtype=torch.float64,
        device=burned.device,
    )


def test_analytic_sum_of_neighbor_rates_and_new_burn_event():
    burned = torch.zeros((1, 5, 7), dtype=torch.float64)
    burned[0, 1, 2] = 1
    burned[0, 2, 1] = 1
    kernels = _kernels(burned)
    kernels[1, 2, 2] = 0.2  # Neighbor immediately above the target.
    kernels[3, 2, 2] = 0.3  # Neighbor immediately left of the target.
    kernels[5, 2, 2] = 100.0  # An unburned neighbor contributes nothing.
    result = new_burn_probability(burned, kernels, dt_hours=2.0)

    assert result.probability.shape == burned.shape
    assert result.valid.dtype == torch.bool
    assert result.valid[0, 2, 2]
    assert result.rate_valid[0, 2, 2]
    torch.testing.assert_close(result.rate[0, 2, 2], torch.tensor(0.5, dtype=torch.float64))
    torch.testing.assert_close(
        result.probability[0, 2, 2],
        torch.tensor(-math.expm1(-1.0), dtype=torch.float64),
    )
    # This is the probability of a *new* burn, so existing burned cells are zero.
    assert result.valid[0, 1, 2]
    assert result.probability[0, 1, 2] == 0


@pytest.mark.parametrize("kernel_size", [3, 5])
def test_directional_offsets_use_neighbor_at_target_plus_offset(kernel_size):
    burned = torch.zeros((1, 7, 9), dtype=torch.bool)
    radius = kernel_size // 2
    target_row, target_col = 3, 3
    burned[0, target_row - radius, target_col + 1] = True
    kernels = _kernels(burned, kernel_size)
    # The first row of the kernel has delta_row=-radius; column radius+1
    # has delta_col=+1. This catches reversal of convolution orientation.
    offset = radius + 1
    kernels[offset, target_row, target_col] = 0.7
    result = new_burn_probability(burned, kernels)

    assert result.valid[0, target_row, target_col]
    torch.testing.assert_close(
        result.rate[0, target_row, target_col],
        torch.tensor(0.7, dtype=torch.float64),
    )
    torch.testing.assert_close(
        result.probability[0, target_row, target_col],
        torch.tensor(-math.expm1(-0.7), dtype=torch.float64),
    )


def test_no_burned_contact_and_zero_rates_give_zero_probability():
    burned = torch.zeros((1, 4, 6), dtype=torch.bool)
    kernels = torch.ones_like(_kernels(burned))
    result = new_burn_probability(burned, kernels, boundary="zero")
    assert result.valid.all()
    assert result.rate_valid.all()
    assert torch.equal(result.rate, torch.zeros_like(result.rate))
    assert torch.equal(result.probability, torch.zeros_like(result.probability))

    # A zero coefficient does not depend on the corresponding unknown neighbor.
    zero_result = new_burn_probability(burned, torch.zeros_like(kernels))
    assert zero_result.valid.all()
    assert zero_result.rate_valid.all()
    assert torch.equal(zero_result.probability, torch.zeros_like(zero_result.probability))


def test_default_boundary_is_unknown_and_zero_boundary_is_explicit():
    burned = torch.zeros((1, 4, 6), dtype=torch.bool)
    kernels = _kernels(burned)
    kernels[3] = 0.4  # Every cell depends only on its left neighbor.
    unknown = new_burn_probability(burned, kernels)
    zero = new_burn_probability(burned, kernels, boundary="zero")

    assert not unknown.valid[0, :, 0].any()
    assert not unknown.rate_valid[0, :, 0].any()
    assert torch.isnan(unknown.probability[0, :, 0]).all()
    assert unknown.valid[0, :, 1:].all()
    assert zero.valid.all()
    assert torch.equal(zero.probability, torch.zeros_like(zero.probability))


@pytest.mark.parametrize("missing_value", [float("nan"), float("inf"), 255.0])
def test_masked_burned_values_are_unknown_without_numeric_contamination(missing_value):
    burned = torch.zeros((1, 5, 6), dtype=torch.float64)
    burned[0, 1, 3] = missing_value
    burned[0, 1, 1] = 1.0
    mask = torch.ones_like(burned, dtype=torch.bool)
    mask[0, 1, 3] = False
    kernels = _kernels(burned)
    kernels[0, 2, 2] = 0.5  # Known burned source.
    kernels[2, 2, 2] = 0.2  # Unknown source with a positive coefficient.
    result = new_burn_probability(
        burned, kernels, burned_area_valid=mask, boundary="zero"
    )

    assert not result.valid[0, 2, 2]
    assert not result.rate_valid[0, 2, 2]
    assert torch.isnan(result.probability[0, 2, 2])
    assert torch.isnan(result.rate[0, 2, 2])
    # Internal missingness stays unknown even when outside pixels are assumed zero.
    assert not result.valid[0, 1, 3]
    assert torch.isnan(result.probability[0, 1, 3])
    # Other targets whose coefficients are all zero need no unknown neighbor.
    assert result.valid[0, 2, 4]
    assert result.probability[0, 2, 4] == 0


@pytest.mark.parametrize("missing_value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_burned_values_are_unknown_even_when_mask_says_valid(missing_value):
    burned = torch.zeros((1, 3, 4), dtype=torch.float64)
    burned[0, 1, 1] = missing_value
    kernels = _kernels(burned)
    kernels[3, 1, 2] = 0.5
    for mask in (None, torch.ones_like(burned, dtype=torch.bool)):
        result = new_burn_probability(
            burned, kernels, burned_area_valid=mask, boundary="zero"
        )
        assert not result.valid[0, 1, 1]
        assert not result.valid[0, 1, 2]
        assert torch.isnan(result.probability[0, 1, 2])


def test_probability_can_be_known_when_exposure_rate_is_unknown():
    burned = torch.zeros((1, 3, 4), dtype=torch.bool)
    burned[0, 0, 0] = True
    kernels = torch.ones_like(_kernels(burned))
    kernel_valid = torch.zeros_like(burned, dtype=torch.bool)
    mask = torch.ones_like(burned)
    mask[0, 2, 3] = False
    positive_horizon = new_burn_probability(
        burned, kernels, burned_area_valid=mask, kernel_valid=kernel_valid
    )

    assert positive_horizon.valid[0, 0, 0]
    assert positive_horizon.probability[0, 0, 0] == 0
    assert not positive_horizon.rate_valid[0, 0, 0]
    assert torch.isnan(positive_horizon.rate[0, 0, 0])
    assert not positive_horizon.valid[0, 1, 1]
    assert torch.isnan(positive_horizon.probability[0, 1, 1])

    zero_horizon = new_burn_probability(
        burned, kernels, dt_hours=0.0,
        burned_area_valid=mask, kernel_valid=kernel_valid,
    )
    assert torch.equal(zero_horizon.valid, mask)
    assert (zero_horizon.probability[mask] == 0).all()
    assert torch.isnan(zero_horizon.probability[~mask]).all()
    assert not zero_horizon.rate_valid.any()


def test_horizon_probability_is_monotone_and_survival_multiplies_for_fixed_rate():
    burned = torch.zeros((1, 3, 4), dtype=torch.float64)
    burned[0, 1, 1] = 1
    kernels = _kernels(burned)
    kernels[3, 1, 2] = 0.25
    horizons = (0.0, 0.5, 1.5, 2.0)
    probabilities = [
        new_burn_probability(burned, kernels, dt_hours=dt).probability[0, 1, 2]
        for dt in horizons
    ]
    assert probabilities[0] == 0
    assert all(a < b for a, b in zip(probabilities, probabilities[1:]))
    # The identity holds with the same burned map and fixed exposure rate.
    torch.testing.assert_close(
        1 - probabilities[3], (1 - probabilities[1]) * (1 - probabilities[2])
    )


def test_rectangular_batch_time_grids_and_per_frame_horizon():
    burned = torch.zeros((2, 3, 1, 4, 7), dtype=torch.bool)
    burned[:, :, 0, 1, 1] = True
    kernels = _kernels(burned)
    kernels[:, :, 3, 1, 2] = 0.4
    horizons = torch.tensor([[0.0, 0.5, 1.0], [2.0, 4.0, 8.0]], dtype=torch.float64)
    result = new_burn_probability(burned, kernels, dt_hours=horizons)

    assert result.probability.shape == (2, 3, 1, 4, 7)
    assert result.valid.all()
    torch.testing.assert_close(result.probability[:, :, 0, 1, 2], -torch.expm1(-0.4 * horizons))
    assert (result.probability[:, :, 0, 1, 1] == 0).all()


def test_small_rates_retain_probability_precision():
    burned = torch.zeros((1, 3, 4), dtype=torch.float64)
    burned[0, 1, 1] = 1
    kernels = _kernels(burned)
    kernels[3, 1, 2] = 1e-18
    result = new_burn_probability(burned, kernels)
    assert result.probability[0, 1, 2] > 0
    torch.testing.assert_close(
        result.probability[0, 1, 2],
        torch.tensor(-math.expm1(-1e-18), dtype=torch.float64),
        rtol=1e-12, atol=0.0,
    )


@pytest.mark.parametrize("dt", [-1.0, float("nan"), float("inf")])
def test_invalid_horizons_are_rejected(dt):
    burned = torch.zeros((1, 3, 4))
    with pytest.raises((ValueError, TypeError)):
        new_burn_probability(burned, _kernels(burned), dt_hours=dt)


@pytest.mark.parametrize("bad_value", [-0.1, 0.5, 2.0, 255.0])
def test_finite_nonbinary_values_at_known_burned_cells_are_rejected(bad_value):
    burned = torch.zeros((1, 3, 4))
    burned[0, 1, 1] = bad_value
    with pytest.raises((ValueError, TypeError)):
        new_burn_probability(burned, _kernels(burned))


def test_negative_kernel_rates_are_rejected():
    burned = torch.zeros((1, 3, 4))
    kernels = _kernels(burned)
    kernels[3, 1, 2] = -0.1
    with pytest.raises((ValueError, TypeError)):
        new_burn_probability(burned, kernels)


@pytest.mark.parametrize("missing_rate", [float("nan"), float("inf")])
def test_nonfinite_kernel_rates_mark_the_target_unavailable(missing_rate):
    burned = torch.zeros((1, 3, 4))
    burned[0, 1, 1] = 1
    kernels = _kernels(burned)
    kernels[3, 1, 2] = missing_rate
    result = new_burn_probability(burned, kernels)

    assert not result.valid[0, 1, 2]
    assert not result.rate_valid[0, 1, 2]
    assert torch.isnan(result.probability[0, 1, 2])
    assert torch.isnan(result.rate[0, 1, 2])
    assert result.valid[0, 2, 2]
    assert result.probability[0, 2, 2] == 0


@pytest.mark.parametrize("kernel_channels", [1, 8, 16, 24])
def test_kernel_requires_square_odd_size_at_least_three(kernel_channels):
    burned = torch.zeros((1, 3, 4))
    with pytest.raises((ValueError, TypeError)):
        new_burn_probability(burned, torch.zeros((kernel_channels, 3, 4)))


def test_shape_mask_and_boundary_errors_are_rejected():
    burned = torch.zeros((2, 3, 1, 4, 7))
    kernels = _kernels(burned)
    with pytest.raises((ValueError, TypeError)):
        new_burn_probability(burned, kernels, dt_hours=torch.ones(2))
    with pytest.raises((ValueError, TypeError)):
        new_burn_probability(burned, kernels[..., :-1])
    with pytest.raises((ValueError, TypeError)):
        new_burn_probability(burned, kernels, burned_area_valid=torch.ones(4, 7, dtype=torch.bool))
    with pytest.raises((ValueError, TypeError)):
        new_burn_probability(burned, kernels, kernel_valid=torch.ones_like(burned))
    with pytest.raises((ValueError, TypeError)):
        new_burn_probability(burned, kernels, boundary="reflect")


def _controlled_conditioner(conditioning_offset=(0, 0)):
    model = EnvironmentConditionedConvolution(1, hidden_channels=1)
    layers = [layer for layer in model.kernel_network if isinstance(layer, nn.Conv2d)]
    assert len(layers) == 2
    with torch.no_grad():
        layers[0].weight.zero_()
        dy, dx = conditioning_offset
        layers[0].weight[0, 0, 1 + dy, 1 + dx] = 1.0
        layers[0].bias.zero_()
        layers[1].weight.zero_()
        layers[1].bias.zero_()
        layers[1].weight[3, 0, 0, 0] = 1.0  # Only left-neighbor rate changes with the feature.
    return model


def test_conditioner_changes_kernel_at_target_using_target_environment():
    model = _controlled_conditioner()
    burned = torch.zeros((1, 5, 7), dtype=torch.bool)
    burned[0, 2, 1] = True
    burned[0, 2, 4] = True
    environment = torch.zeros((1, 5, 7))
    environment[0, 2, 5] = 2.0
    rates = model.kernel_rates(environment, boundary="zero")
    result = model(burned, environment, boundary="zero")

    assert rates.shape == (9, 5, 7)
    assert torch.isfinite(rates).all()
    assert (rates >= 0).all()
    assert (rates[4] == 0).all()
    assert rates[3, 2, 5] > rates[3, 2, 2]
    assert result.probability[0, 2, 5] > result.probability[0, 2, 2]
    torch.testing.assert_close(result.rate[0, 2, 2], rates[3, 2, 2])
    torch.testing.assert_close(result.rate[0, 2, 5], rates[3, 2, 5])
    torch.testing.assert_close(result.probability[0, 2, 2], -torch.expm1(-rates[3, 2, 2]))


def test_surrounding_environment_changes_target_kernel_without_changing_target_feature():
    # The conditioning network selects the environmental pixel directly above
    # each target; the generated rate acts on the burned source to its left.
    model = _controlled_conditioner(conditioning_offset=(-1, 0))
    burned = torch.zeros((1, 5, 7), dtype=torch.bool)
    burned[0, 2, 1] = True
    environment = torch.zeros((1, 5, 7))
    base = model(burned, environment, boundary="zero")
    changed_environment = environment.clone()
    changed_environment[0, 1, 2] = 2.0
    changed = model(burned, changed_environment, boundary="zero")
    rates = model.kernel_rates(changed_environment, boundary="zero")

    assert changed_environment[0, 2, 2] == environment[0, 2, 2]
    assert changed.probability[0, 2, 2] > base.probability[0, 2, 2]
    torch.testing.assert_close(changed.rate[0, 2, 2], rates[3, 2, 2])
    torch.testing.assert_close(
        rates[3, 2, 2], torch.nn.functional.softplus(torch.nn.functional.silu(torch.tensor(2.0)))
    )
    # This separate target's selected environmental neighbor did not change.
    torch.testing.assert_close(changed.rate[0, 2, 0], base.rate[0, 2, 0])


def test_conditioner_preserves_batch_time_dimensions_and_rectangular_shape():
    model = EnvironmentConditionedConvolution(2, kernel_size=5, hidden_channels=3)
    environment = torch.zeros((2, 3, 2, 4, 7))
    burned = torch.zeros((2, 3, 1, 4, 7), dtype=torch.bool)
    burned[:, :, 0, 1, 1] = True
    rates = model.kernel_rates(environment, boundary="zero")
    result = model(burned, environment, boundary="zero")

    assert rates.shape == (2, 3, 25, 4, 7)
    assert (rates[:, :, 12] == 0).all()
    assert result.probability.shape == burned.shape
    assert result.valid.all()
    assert ((result.probability >= 0) & (result.probability <= 1)).all()


def test_feature_missingness_is_sanitized_before_neighborhood_conditioning():
    model = EnvironmentConditionedConvolution(2, hidden_channels=3)
    burned = torch.zeros((1, 4, 6), dtype=torch.bool)
    burned[0, 1, 1] = True
    burned[0, 0, 5] = True
    environment = torch.zeros((2, 4, 6))
    environment[0, 1, 2] = float("nan")
    environment[1, 2, 3] = 255.0
    environment.requires_grad_()
    feature_valid = torch.ones_like(environment, dtype=torch.bool)
    feature_valid[1, 2, 3] = False
    feature_valid[:, 1, 1] = False
    rates = model.kernel_rates(environment, feature_valid=feature_valid, boundary="zero")
    clean_rates = model.kernel_rates(torch.zeros_like(environment), boundary="zero")
    result = model(
        burned, environment, feature_valid=feature_valid, boundary="zero"
    )

    assert torch.isnan(rates[:, 1, 2]).all()
    assert torch.isnan(rates[:, 2, 3]).all()
    assert torch.isnan(rates[:, 1, 1]).all()
    torch.testing.assert_close(rates[:, 0, 5], clean_rates[:, 0, 5])
    assert not result.valid[0, 1, 2]  # Nonfinite feature, despite a true supplied mask.
    assert not result.valid[0, 2, 3]  # One of the supplied channels is missing.
    assert torch.isnan(result.probability[0, 1, 2])
    assert result.valid[0, 1, 1]  # Existing burned state determines the new-burn event.
    assert result.probability[0, 1, 1] == 0
    assert not result.rate_valid[0, 1, 1]
    assert not result.valid[0, 2, 2]  # Its neighboring environmental context is missing.
    assert result.valid[0, 0, 4]
    # Missing values must be replaced before the network, not merely hidden
    # afterwards: NaN inputs would otherwise poison parameter gradients.
    result.probability[result.valid].sum().backward()
    assert all(torch.isfinite(parameter.grad).all() for parameter in model.parameters())
    assert torch.isfinite(environment.grad).all()
    assert environment.grad[0, 1, 2] == 0
    assert environment.grad[1, 2, 3] == 0


@pytest.mark.parametrize("kernel_size", [3, 5])
def test_every_environmental_channel_across_full_context_must_be_known(kernel_size):
    model = EnvironmentConditionedConvolution(2, kernel_size=kernel_size, hidden_channels=2)
    environment = torch.zeros((2, 7, 9))
    feature_valid = torch.ones_like(environment, dtype=torch.bool)
    feature_valid[1, 3, 4] = False
    environment[1, 3, 4] = 255.0
    burned = torch.zeros((1, 7, 9), dtype=torch.bool)
    radius = kernel_size // 2
    expected = torch.ones_like(burned)
    expected[0, 3 - radius:4 + radius, 4 - radius:5 + radius] = False
    rates = model.kernel_rates(environment, feature_valid, boundary="zero")
    result = model(burned, environment, feature_valid=feature_valid, boundary="zero")

    assert torch.equal(torch.isfinite(rates).all(dim=0, keepdim=True), expected)
    assert torch.equal(result.rate_valid, expected)
    assert torch.equal(result.valid, expected)
    assert torch.isnan(result.probability[~expected]).all()
    assert (result.probability[expected] == 0).all()

    # Zero time makes the transition event known despite missing context.
    zero_horizon = model(
        burned, environment, dt_hours=0, feature_valid=feature_valid, boundary="zero"
    )
    assert zero_horizon.valid.all()
    assert (zero_horizon.probability == 0).all()
    assert torch.equal(zero_horizon.rate_valid, expected)


def test_environmental_exterior_is_unknown_unless_explicitly_assumed_zero():
    model = _controlled_conditioner(conditioning_offset=(-1, -1))
    environment = torch.ones((1, 5, 7))
    burned = torch.zeros((1, 5, 7), dtype=torch.bool)
    expected = torch.zeros_like(burned)
    expected[0, 1:-1, 1:-1] = True
    unknown_rates = model.kernel_rates(environment)
    zero_rates = model.kernel_rates(environment, boundary="zero")
    unknown = model(burned, environment)
    zero = model(burned, environment, boundary="zero")

    assert torch.equal(torch.isfinite(unknown_rates).all(dim=0, keepdim=True), expected)
    assert torch.equal(unknown.valid, expected)
    assert torch.isnan(unknown.probability[~expected]).all()
    assert torch.isfinite(zero_rates).all()
    assert zero.valid.all()
    assert (zero.probability == 0).all()
    torch.testing.assert_close(zero_rates[3, 0, 0], torch.tensor(math.log(2.0)))
    assert zero_rates[3, 1, 1] > zero_rates[3, 0, 0]

    burned[0, 0, 0] = True
    known_burned = model(burned, environment)
    assert known_burned.valid[0, 0, 0]
    assert known_burned.probability[0, 0, 0] == 0
    assert not known_burned.rate_valid[0, 0, 0]


@pytest.mark.parametrize("conditioning_offset", [(0, 0), (-1, 0)])
def test_gradients_reach_conditioner_parameters_and_selected_environment(conditioning_offset):
    model = _controlled_conditioner(conditioning_offset)
    burned = torch.zeros((1, 4, 6), dtype=torch.bool)
    burned[0, 1, 1] = True
    environment = torch.full((1, 4, 6), 0.5, requires_grad=True)
    result = model(burned, environment, boundary="zero")
    result.probability[0, 1, 2].backward()

    assert environment.grad is not None
    assert torch.isfinite(environment.grad).all()
    dy, dx = conditioning_offset
    assert environment.grad[0, 1 + dy, 2 + dx] > 0
    assert environment.grad[0, 1, 1] == 0
    gradients = [parameter.grad for parameter in model.parameters()]
    assert all(gradient is not None for gradient in gradients)
    assert all(torch.isfinite(gradient).all() for gradient in gradients)
    assert all(gradient.abs().sum() > 0 for gradient in gradients)


def test_finite_feature_overflow_in_conditioner_is_rejected():
    model = EnvironmentConditionedConvolution(1, hidden_channels=1)
    with torch.no_grad():
        for parameter in model.parameters():
            parameter.fill_(10.0)
    environment = torch.full((1, 3, 4), 1e38)
    burned = torch.zeros((1, 3, 4), dtype=torch.bool)
    burned[0, 1, 1] = True
    # The inputs and parameters are individually finite, but their products
    # overflow float32. Returning saturated probabilities would hide the
    # corrupted neural calculation and could leave unusable gradients.
    assert torch.isfinite(environment).all()
    with pytest.raises(RuntimeError):
        model.kernel_rates(environment)
    with pytest.raises(RuntimeError):
        model(burned, environment, boundary="zero")


@pytest.mark.parametrize("arguments", [
    {"in_channels": 0},
    {"in_channels": 1, "kernel_size": 2},
    {"in_channels": 1, "kernel_size": 1},
    {"in_channels": 1, "hidden_channels": 0},
])
def test_invalid_conditioner_architecture_is_rejected(arguments):
    with pytest.raises((ValueError, TypeError)):
        EnvironmentConditionedConvolution(**arguments)


def test_conditioner_rejects_incompatible_feature_shapes_and_masks():
    model = EnvironmentConditionedConvolution(2)
    burned = torch.zeros((1, 4, 6), dtype=torch.bool)
    environment = torch.zeros((2, 4, 6))
    with pytest.raises((ValueError, TypeError)):
        model.kernel_rates(torch.zeros((1, 4, 6)))
    with pytest.raises((ValueError, TypeError)):
        model.kernel_rates(environment, feature_valid=torch.ones_like(environment))
    with pytest.raises((ValueError, TypeError)):
        model(burned, environment[..., :-1])
