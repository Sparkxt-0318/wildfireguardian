"""Independent controls for repaired unit, availability and fitting failures."""
import math

import numpy as np
import pytest
import torch

from wildfire.canonical import local_canonical_kernels
from wildfire.meanfield import mean_field_step, propagate_mean_field
from wildfire.models import anderson_length_to_breadth
from wildfire.survival import clipped_nll, endpoint_brier, evaluate_samples, fit_mean_field, kriging_weight


def test_wind_canonicalization_uses_each_target_not_a_cancelling_domain_mean():
    environment = torch.zeros(1, 2, 11, 21, dtype=torch.float64)
    environment[:, 0, :, :10] = 1
    environment[:, 0, :, 10:] = -1

    def west_offset(patch):
        output = torch.zeros(patch.shape[0], 9, *patch.shape[-2:], dtype=patch.dtype)
        output[:, 3] = 1
        return output

    rates = local_canonical_kernels(west_offset, environment, (0, 1),
                                    torch.zeros(2, 1, 1, dtype=torch.float64),
                                    torch.ones(2, 1, 1, dtype=torch.float64), 3)
    assert rates[0, 3, 5, 4] == 1
    assert abs(float(rates[0, 5, 5, 16]) - 1) < 1e-12
    assert abs(float(rates[0, 3, 5, 16])) < 1e-12


@pytest.mark.parametrize("speed", [0., 1., 2., 4., 6.])
def test_anderson_metre_per_second_formula_matches_independent_mph_form(speed):
    mph = speed * 2.2369362920544
    reference = min(8, max(1, 0.936 * math.exp(.1147 * mph) + .461 * math.exp(-.0692 * mph) - .397))
    assert abs(float(anderson_length_to_breadth(torch.tensor(speed, dtype=torch.float64))) - reference) < 2e-3


def test_negative_extra_source_rate_cannot_reduce_cumulative_occupancy():
    p = torch.zeros(1, 1, 2, 2)
    kernels = torch.zeros(1, 9, 2, 2)
    with pytest.raises(ValueError, match="extra_rate"):
        mean_field_step(p, kernels, 1, extra_rate=-torch.ones_like(p))


@pytest.mark.parametrize("function", [endpoint_brier, clipped_nll])
def test_masked_unknown_labels_are_not_nan_losses(function):
    p = torch.tensor([.2, float("nan")])
    label = torch.tensor([1., float("nan")])
    weight = torch.tensor([2., float("nan")])
    loss, total = function(p, label, weight, torch.tensor([True, False]))
    assert bool(torch.isfinite(loss)) and total == 2
    with pytest.raises(ValueError, match="weights"):
        function(torch.tensor([.5]), torch.tensor([1.]), torch.tensor([-1.]), torch.tensor([True]))


def test_missing_kriging_sd_does_not_receive_full_confidence():
    assert kriging_weight(np.array([np.nan]), 2).item() == 0
    with pytest.raises(ValueError):
        kriging_weight(np.array([-1.]), 2)


def test_empty_training_and_evaluation_cannot_report_zero_brier():
    model = torch.nn.Linear(1, 1)
    with pytest.raises(ValueError, match="nonempty"):
        fit_mean_field(model, [], [], log=lambda *_: None)
    with pytest.raises(ValueError, match="No supported"):
        evaluate_samples(model, [])


def test_validity_mask_shape_and_type_are_not_broadcast_silently():
    class Provider:
        def kernel_rates(self, environment, feature_valid=None, *, boundary="zero"):
            return torch.zeros(1, 9, 2, 2)
    with pytest.raises(ValueError, match="p0_valid"):
        propagate_mean_field(Provider(), torch.zeros(1, 1, 2, 2), torch.zeros(1, 1, 2, 2),
                             [1], p0_valid=torch.ones(1, 1, 2, 2, dtype=torch.int64))
