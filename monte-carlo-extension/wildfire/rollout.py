"""Private binary-state Monte Carlo engine for cumulative hourly spread.

The learned conditional marginal probabilities define a joint transition by
conditionally independent cell ignitions. Burning is absorbing and updates are
synchronous. Coverage is a deterministic conservative envelope, never a count
of the trajectories that happened to remain available.
"""
from __future__ import annotations

from numbers import Integral

import numpy as np
import torch

from .models import BayesianBurnModel, BurnProbability


def validate_controls(hours, n_samples, seed, trajectory_batch_size):
    if any(not hour.is_integer() for hour in hours):
        raise ValueError("Recursive hours must be positive whole-hour horizons; use method='fixed' for fractional hours")
    for name, value, minimum in (("n_samples", n_samples, 1),
                                 ("trajectory_batch_size", trajectory_batch_size, 1),
                                 ("seed", seed, 0)):
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
            raise TypeError(f"{name} must be an integer excluding booleans")
        if value < minimum:
            qualifier = "positive" if minimum else "nonnegative"
            raise ValueError(f"{name} must be a {qualifier} integer")


def _generator(seed, cutoff, block, stream):
    # Neither requested horizons nor sample count participate in stream seeds.
    derived = np.random.SeedSequence([seed, cutoff, block, stream]).generate_state(
        1, dtype=np.uint64,
    )[0]
    return torch.Generator(device="cpu").manual_seed(int(derived))


def _check_transition(prediction, required, *, cutoff, hour, component):
    q = prediction.probability
    invalid = required & (~prediction.valid | ~torch.isfinite(q) | (q < 0) | (q > 1))
    if bool(invalid.any()):
        raise RuntimeError(
            "Recursive transition is invalid, nonfinite or outside [0,1] on "
            f"declared coverage (cutoff={cutoff}, hour={hour}, component={component})"
        )


@torch.inference_mode()
def simulate(
    predictor, burned_area, environmental_data, *, channel_names,
    burned_area_valid, feature_valid, hours, n_samples, seed,
    trajectory_batch_size, boundary, environmental_forecast=None,
    forecast_valid=None, missing_burned_area="unknown", assumed_unburned_cells=0,
):
    """Return one details/optional-output mapping per supplied horizon."""
    predictor.eval()
    if boundary not in ("unknown", "zero"):
        raise ValueError("boundary must be 'unknown' or 'zero'")
    if tuple(channel_names) != predictor.channel_names:
        raise ValueError("Prediction channel names/order differ from the trained checkpoint")
    if environmental_data.shape[-3] != len(predictor.channel_names):
        raise ValueError("environmental_data channel count must match the trained checkpoint")
    known = burned_area_valid & torch.isfinite(burned_area)
    if bool((known & (burned_area != 0) & (burned_area != 1)).any()):
        raise ValueError("Valid burned_area values must be exactly 0 or 1")
    shape = tuple(burned_area.shape)
    h, w = shape[-2:]
    channels = environmental_data.shape[-3]
    initial = torch.where(known, burned_area, 0).reshape(-1, 1, h, w)
    known = known.reshape(-1, 1, h, w)
    current_environment = environmental_data.reshape(-1, channels, h, w)
    current_feature_valid = feature_valid.reshape(-1, channels, h, w)
    steps = int(max(hours))
    requested = {int(hour): index for index, hour in enumerate(hours)}
    counts = torch.zeros((len(hours), *initial.shape), device=initial.device, dtype=torch.int64)
    coverage = torch.zeros_like(counts, dtype=torch.bool)
    if environmental_forecast is not None:
        forecast = environmental_forecast.reshape(-1, initial.shape[0], channels, h, w)
        forecast_masks = forecast_valid.reshape_as(forecast)
    else:
        forecast = forecast_masks = None

    if isinstance(predictor, BayesianBurnModel):
        supported = torch.isfinite(predictor.log_posterior_weights)
        components = [member for member, active in zip(predictor.components, supported) if bool(active)]
        logs = predictor.log_posterior_weights[supported].detach().cpu().double()
        # Global posterior normalization only; coverage never changes weights.
        weights = torch.softmax(logs, dim=0)
    else:
        components = [predictor]
        weights = torch.ones(1, dtype=torch.float64)

    for cutoff in range(initial.shape[0]):
        base = initial[cutoff]
        base_known = known[cutoff]
        observed_burns = base_known & (base == 1)

        def environment_at(k):
            if forecast is None:
                return current_environment[cutoff], current_feature_valid[cutoff]
            return forecast[k, cutoff], forecast_masks[k, cutoff]

        envelopes = []
        for component_index, member in enumerate(components):
            masks = [base_known]
            for k in range(steps):
                environment, available = environment_at(k)
                probe = member(
                    base.unsqueeze(0), environment.unsqueeze(0), channel_names=channel_names,
                    burned_area_valid=masks[-1].unsqueeze(0), feature_valid=available.unsqueeze(0),
                    dt_hours=1.0, boundary=boundary,
                )
                following = masks[-1] & (observed_burns | probe.rate_valid[0])
                _check_transition(probe, following.unsqueeze(0), cutoff=cutoff,
                                  hour=k + 1, component=component_index)
                masks.append(following)
            envelopes.append(masks)
        for hour, index in requested.items():
            coverage[index, cutoff] = torch.stack([masks[hour] for masks in envelopes]).all(dim=0)

        for block, start in enumerate(range(0, n_samples, trajectory_batch_size)):
            size = min(trajectory_batch_size, n_samples - start)
            ignition_rng = _generator(seed, cutoff, block, 0)
            component_rng = _generator(seed, cutoff, block, 1)
            assignments = torch.multinomial(
                weights, trajectory_batch_size, replacement=True, generator=component_rng,
            )
            groups = [(j, torch.nonzero(assignments == j, as_tuple=False).flatten().to(initial.device))
                      for j in range(len(components))]
            # Infer full blocks as well as drawing them: changing only N then
            # leaves neural inference batch shapes and trajectory prefixes fixed.
            states = base.unsqueeze(0).expand(trajectory_batch_size, -1, -1, -1).clone()
            for k in range(steps):
                # Always draw full blocks, including the final partial block,
                # so increasing N preserves all existing trajectory prefixes.
                uniforms = torch.rand(
                    (trajectory_batch_size, 1, h, w), generator=ignition_rng,
                    dtype=initial.dtype, device="cpu",
                ).to(initial.device)
                environment, available = environment_at(k)
                for j, indices in groups:
                    if indices.numel() == 0:
                        continue
                    member_states = states[indices]
                    required = envelopes[j][k + 1].unsqueeze(0).expand_as(member_states)
                    transition = components[j](
                        member_states, environment.unsqueeze(0).expand(len(indices), -1, -1, -1),
                        channel_names=channel_names,
                        burned_area_valid=envelopes[j][k].unsqueeze(0).expand_as(member_states),
                        feature_valid=available.unsqueeze(0).expand(len(indices), -1, -1, -1),
                        dt_hours=1.0, boundary=boundary,
                    )
                    _check_transition(transition, required, cutoff=cutoff,
                                      hour=k + 1, component=j)
                    safe_q = torch.where(required, transition.probability, 0)
                    ignite = required & (uniforms[indices] < safe_q)
                    states[indices] = torch.logical_or(member_states == 1, ignite).to(initial.dtype)
                if k + 1 in requested:
                    index = requested[k + 1]
                    counts[index, cutoff] += ((states[:size] == 1) & ~observed_burns).sum(dim=0)

    probability = (counts.to(initial.dtype) / n_samples).reshape(len(hours), *shape)
    coverage = coverage.reshape(len(hours), *shape)
    known_burns = (known & (initial == 1)).reshape(shape)
    metadata = dict(
        method="recursive", n_samples=n_samples, seed=seed,
        trajectory_batch_size=trajectory_batch_size, confidence_level=0.95,
        environment_policy="repeated_current" if forecast is None else "hourly_forecast",
        uncertainty_kind="monte_carlo", conditional_cell_independence=True,
        coverage_policy="conservative", update_interval_hours=1,
        boundary=boundary,
        missing_burned_area=missing_burned_area,
        assumed_unburned_cells=assumed_unburned_cells,
    )
    results = []
    z = 1.95996398454
    denominator = 1 + z * z / n_samples
    for index in range(len(hours)):
        q = probability[index]
        valid = coverage[index]
        se = torch.sqrt(q * (1 - q) / n_samples)
        center = (q + z * z / (2 * n_samples)) / denominator
        half_width = z / denominator * torch.sqrt(q * (1 - q) / n_samples + z * z / (4 * n_samples ** 2))
        lower = (center - half_width).clamp(0, 1)
        upper = (center + half_width).clamp(0, 1)
        lower = torch.where(known_burns, 0, lower)
        upper = torch.where(known_burns, 0, upper)
        total = torch.where(known_burns, 1, q)
        results.append(dict(
            details=BurnProbability(q.masked_fill(~valid, torch.nan), valid,
                                    torch.full_like(q, torch.nan), torch.zeros_like(valid)),
            burned_probability=total.masked_fill(~valid, torch.nan),
            mc_standard_error=se.masked_fill(~valid, torch.nan),
            confidence_lower=lower.masked_fill(~valid, torch.nan),
            confidence_upper=upper.masked_fill(~valid, torch.nan),
            metadata=metadata,
        ))
    return results
