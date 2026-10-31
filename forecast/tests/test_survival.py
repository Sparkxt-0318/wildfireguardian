"""Interval-censored survival loss and perimeter interval helpers."""
import math

import numpy as np
import pandas as pd
import torch

from wildfire.meanfield import propagate_mean_field
from wildfire.survival import (
    ages_from_states, biome_balance_factors, clipped_nll, consecutive_intervals, endpoint_brier,
    kriging_weight, step_durations,
)


class TwoCellHazard(torch.nn.Module):
    """Cell 0 is burned; cell 1 receives hazard ``lambda`` from its west neighbour."""

    def __init__(self, log_rate):
        super().__init__()
        self.log_rate = torch.nn.Parameter(torch.tensor(float(log_rate), dtype=torch.float64))

    def kernel_rates(self, environment, feature_valid=None, *, boundary="zero"):
        kernels = torch.zeros(1, 9, 1, 2, dtype=torch.float64)
        kernels[0, 3, 0, 1] = torch.exp(self.log_rate)  # offset (0, -1): the western source
        return kernels


def _forecast(model, hours):
    p0 = torch.tensor([[[[1.0, 0.0]]]], dtype=torch.float64)
    result = propagate_mean_field(model, p0, torch.zeros(1, 1, 1, 2, dtype=torch.float64),
                                  step_durations(hours), boundary="zero")
    return result.new_burn_probability[-1][0, 0, 0, 1]


def test_two_cell_survival_product_is_the_analytic_interval_probability():
    rate, hours = 0.21, 7.35
    model = TwoCellHazard(math.log(rate))
    assert step_durations(hours) == [1.0] * 7 + [step_durations(hours)[-1]]
    assert abs(float(_forecast(model, hours)) - (1 - math.exp(-rate * hours))) < 1e-12


def test_survival_loss_recovers_the_analytic_hazard():
    true_rate, hours = 0.15, 12.5
    target = 1 - math.exp(-true_rate * hours)
    # 1,000 replicate cells whose mapped outcome frequency equals the model probability.
    positives = round(1000 * target)
    labels = torch.tensor([1.0] * positives + [0.0] * (1000 - positives), dtype=torch.float64)
    frequency = positives / 1000
    model = TwoCellHazard(math.log(0.02))
    optimizer = torch.optim.Adam(model.parameters(), lr=0.05)
    mask = torch.ones_like(labels, dtype=torch.bool)
    weight = torch.ones_like(labels)
    for _ in range(600):
        optimizer.zero_grad()
        p = _forecast(model, hours).expand_as(labels)
        loss, total = endpoint_brier(p, labels, weight, mask)
        (loss / total).backward()
        optimizer.step()
    fitted = math.exp(float(model.log_rate))
    assert abs(fitted - (-math.log(1 - frequency) / hours)) < 1e-4
    assert abs(fitted - true_rate) < 2e-3
    nll, total = clipped_nll(_forecast(model, hours).expand_as(labels).detach(), labels, weight, mask)
    assert math.isfinite(float(nll / total))


def test_interval_rule_is_label_free_and_capped():
    times = list(pd.to_datetime(["2021-08-01T04:00Z", "2021-08-02T03:30Z", "2021-08-05T05:00Z",
                                 "2021-08-06T04:00Z"], utc=True))
    assert [(i, j) for i, j, _ in consecutive_intervals(times, 48)] == [(0, 1), (2, 3)]
    states = np.zeros((4, 1, 3), dtype=np.uint8)
    states[0, 0, 0] = 1
    states[1:, 0, :2] = 1
    states[3, 0, 2] = 1
    age = ages_from_states(times, states, 3)
    assert age[0, 0] == (times[3] - times[0]).total_seconds() / 3600
    midpoint = times[0] + (times[1] - times[0]) / 2
    assert age[0, 1] == (times[3] - midpoint).total_seconds() / 3600


def test_kriging_weight_and_balance_factors():
    w = kriging_weight(np.array([0.0, 6.0, np.nan]), 6.0)
    assert w.tolist() == [1.0, 0.5, 0.0]
    factors = biome_balance_factors({1: 900.0, 2: 100.0})
    assert factors[2] > factors[1]
    assert abs(900 * factors[1] + 100 * factors[2] - 1000) < 1e-9
