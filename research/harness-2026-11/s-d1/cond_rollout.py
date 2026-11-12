"""Drop-in conditional-Monte-Carlo companion to ``wildfire.rollout.simulate`` (existing hourly model).

For every trajectory the existing recursion already computes, at each hourly step k, every cell's
ignition probability q_i(k) given the trajectory's state. The conditional estimator

    Y_i(t) = sum_{k <= t} 1{i unburned before step k} * q_i(k)

has E[Y_i(t)] = sum_k P(i ignites at step k) = P(i newly burned by t) exactly, so it is unbiased for
the same quantity the existing Monte Carlo output estimates by counting hits. It costs nothing extra:
q_i(k) is already evaluated. Unlike hit counting it is non-zero wherever any trajectory gives the cell
a positive hazard, so it resolves probabilities far below 1/n.

This module re-implements the trajectory loop of ``wildfire.rollout.simulate`` for the supported case
(single non-Bayesian predictor, whole-hour horizons, repeated-current or hourly-forecast environment,
uncached transitions). It uses the SAME random streams (``wildfire.rollout._generator``), coverage
envelopes and ignition rule. Its plain hit-count probabilities are therefore bit-identical to
``simulate``'s, which a test asserts. The frozen predictors (for example ``c651_mc``) are untouched. The
conditional output is meant to be declared as a NEW named predictor variant (for example
``c651_mc_cond``) before any scored use.

It sharpens tail estimates. It does not change the model, so it cannot fix calibration.
"""
from __future__ import annotations

import numpy as np
import torch

from wildfire.models import BayesianBurnModel
from wildfire.rollout import _check_transition, _generator, validate_controls


@torch.inference_mode()
def simulate_with_conditional(predictor, burned_area, environmental_data, *, channel_names,
                              burned_area_valid, feature_valid, hours, n_samples, seed,
                              trajectory_batch_size, boundary, environmental_forecast=None,
                              forecast_valid=None):
    """Return one dict per horizon: ``probability`` (plain, identical to simulate's ``details``),
    ``conditional`` (mean of Y) and ``conditional_se`` (MC standard error of that mean), plus ``valid``
    (the conservative coverage of ``simulate``). Arrays are shaped like ``burned_area``."""
    hours = [float(h) for h in hours]
    validate_controls(hours, n_samples, seed, trajectory_batch_size)
    if isinstance(predictor, BayesianBurnModel):
        raise NotImplementedError("Bayesian mixtures are not supported by this companion")
    predictor.eval()
    if boundary not in ("unknown", "zero"):
        raise ValueError("boundary must be 'unknown' or 'zero'")
    known = burned_area_valid & torch.isfinite(burned_area)
    shape = tuple(burned_area.shape)
    h, w = shape[-2:]
    channels = environmental_data.shape[-3]
    initial = torch.where(known, burned_area, 0).reshape(-1, 1, h, w)
    known = known.reshape(-1, 1, h, w)
    current_environment = environmental_data.reshape(-1, channels, h, w)
    current_feature_valid = feature_valid.reshape(-1, channels, h, w)
    steps = int(max(hours))
    requested = {int(hour): index for index, hour in enumerate(hours)}
    if environmental_forecast is not None:
        forecast = environmental_forecast.reshape(-1, initial.shape[0], channels, h, w)
        forecast_masks = forecast_valid.reshape_as(forecast)
    else:
        forecast = forecast_masks = None
    weights = torch.ones(1, dtype=torch.float64)
    nh = len(hours)
    counts = torch.zeros((nh, *initial.shape), dtype=torch.int64)
    cond1 = torch.zeros((nh, *initial.shape), dtype=torch.float64)
    cond2 = torch.zeros((nh, *initial.shape), dtype=torch.float64)
    coverage = torch.zeros((nh, *initial.shape), dtype=torch.bool)

    for cutoff in range(initial.shape[0]):
        base = initial[cutoff]
        base_known = known[cutoff]
        observed_burns = base_known & (base == 1)

        def environment_at(k):
            if forecast is None:
                return current_environment[cutoff], current_feature_valid[cutoff]
            return forecast[k, cutoff], forecast_masks[k, cutoff]

        def transition(states, masks, environment, available):
            size = states.shape[0]
            return predictor(states, environment.unsqueeze(0).expand(size, -1, -1, -1),
                             channel_names=channel_names, burned_area_valid=masks,
                             feature_valid=available.unsqueeze(0).expand(size, -1, -1, -1),
                             dt_hours=1.0, boundary=boundary)

        masks = [base_known]
        for k in range(steps):
            environment, available = environment_at(k)
            probe = transition(base.unsqueeze(0), masks[-1].unsqueeze(0), environment, available)
            following = masks[-1] & (observed_burns | probe.rate_valid[0])
            _check_transition(probe, following.unsqueeze(0), cutoff=cutoff, hour=k + 1, component=0)
            masks.append(following)
        for hour, index in requested.items():
            coverage[index, cutoff] = masks[hour]

        for block, start in enumerate(range(0, n_samples, trajectory_batch_size)):
            size = min(trajectory_batch_size, n_samples - start)
            ignition_rng = _generator(seed, cutoff, block, 0)
            component_rng = _generator(seed, cutoff, block, 1)
            torch.multinomial(weights, trajectory_batch_size, replacement=True, generator=component_rng)
            states = base.unsqueeze(0).expand(trajectory_batch_size, -1, -1, -1).clone()
            Y = torch.zeros(states.shape, dtype=torch.float64)
            for k in range(steps):
                uniforms = torch.rand((trajectory_batch_size, 1, h, w), generator=ignition_rng,
                                      dtype=initial.dtype, device="cpu").to(initial.device)
                environment, available = environment_at(k)
                required = masks[k + 1].unsqueeze(0).expand_as(states)
                tr = transition(states, masks[k].unsqueeze(0).expand_as(states), environment, available)
                _check_transition(tr, required, cutoff=cutoff, hour=k + 1, component=0)
                safe_q = torch.where(required, tr.probability, 0)
                Y += torch.where(states == 0, safe_q, 0).to(torch.float64)
                ignite = required & (uniforms < safe_q)
                states = torch.logical_or(states == 1, ignite).to(initial.dtype)
                if k + 1 in requested:
                    index = requested[k + 1]
                    counts[index, cutoff] += ((states[:size] == 1) & ~observed_burns).sum(dim=0)
                    y = torch.where(observed_burns, 0.0, Y[:size])
                    cond1[index, cutoff] += y.sum(dim=0)
                    cond2[index, cutoff] += (y * y).sum(dim=0)

    out = []
    for index in range(nh):
        valid = coverage[index].reshape(shape)
        p = (counts[index].to(initial.dtype) / n_samples).reshape(shape)
        mean = cond1[index] / n_samples
        var = (cond2[index] / n_samples - mean * mean).clamp_min(0)
        se = torch.sqrt(var / n_samples)
        out.append(dict(probability=p.masked_fill(~valid, torch.nan),
                        conditional=mean.reshape(shape).to(initial.dtype).masked_fill(~valid, torch.nan),
                        conditional_se=se.reshape(shape).to(initial.dtype).masked_fill(~valid, torch.nan),
                        valid=valid))
    return out
