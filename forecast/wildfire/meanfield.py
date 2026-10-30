"""Deterministic, differentiable mean-field propagation of burned occupancy.

The recursive Monte Carlo engine (``rollout.simulate``) samples binary burned
maps. Each synchronous step draws conditionally independent ignitions with
probability ``q_i = 1 - exp(-dt * lambda_i)``, where
``lambda_i = sum_delta K[i, delta] * B[i + delta]``. The mean field replaces
the binary map ``B`` by a continuous occupancy ``p`` in [0, 1] and evolves

    p_{t+dt} = p_t + (1 - p_t) * (1 - exp(-dt * lambda_t)),
    lambda_t[i] = sum_delta K[i, delta] * s_t[i + delta],

with ``s_t = p_t`` (absorbing sources) or a burnout-weighted source field
(``burnout.FlamingWindow``). The kernels ``K`` are produced by the model's own
generation path (``kernel_rates``), never re-implemented, so for a binary
``p_t`` one mean-field step equals the expectation of the Monte Carlo
transition exactly (``new_burn_probability``). After the first step the mean
field ignores the correlation between neighbouring sources and between source
and target states (``E[(1 - B_i) * B_j] != (1 - p_i) * p_j``), so it is an
approximation of the Monte Carlo mean, not an identity; see
``research/forecast-v2`` for the measured error.

Availability follows the rollout's conservative envelope exactly: the target
mask after step k is ``mask_k & (known_initial_burn | rate_valid_k)``, where
``rate_valid_k`` is evaluated on the binary initial state with ``mask_k`` as
the burned-state availability. Unknown cells are never interpreted as zero:
an invalid cell can still hold a numeric value internally, but every target
with a positive kernel weight on it is itself invalid, and the returned
probability is NaN outside the envelope.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from math import isqrt
from numbers import Real

import torch
from torch import Tensor
from torch.nn import functional as F

from .models import (
    BayesianBurnModel, EnvironmentConditionedConvolution, NeuralMixedNonnegativeKernel,
    NormalizedBurnModel, TrainedBurnModel, new_burn_probability,
)

__all__ = [
    "MeanFieldResult", "kernel_source_rate", "mean_field_step", "model_kernel_components",
    "propagate_mean_field",
]


@dataclass(frozen=True)
class MeanFieldResult:
    """Mean-field forecast at every step endpoint.

    ``burned_probability[s]`` is the cumulative occupancy after step ``s``
    (known initial burns are one). ``new_burn_probability[s]`` excludes known
    initial burns (zero there), matching the rollout's ``details.probability``.
    ``valid[s]`` is the conservative envelope. Shapes are ``[S, ..., 1, H, W]``.
    ``elapsed_hours`` lists the cumulative step endpoints.
    """

    burned_probability: Tensor
    new_burn_probability: Tensor
    valid: Tensor
    elapsed_hours: tuple[float, ...]

    def at(self, hours: float) -> tuple[Tensor, Tensor]:
        """Return ``(new_burn_probability, valid)`` at one exact step endpoint."""
        matches = [i for i, value in enumerate(self.elapsed_hours) if abs(value - hours) <= 1e-9]
        if len(matches) != 1:
            raise ValueError(f"{hours} h is not a step endpoint of this forecast")
        return self.new_burn_probability[matches[0]], self.valid[matches[0]]


def kernel_source_rate(kernels: Tensor, source: Tensor) -> Tensor:
    """Return ``lambda[..., 1, H, W] = sum_delta K[..., delta, H, W] * s[i + delta]``.

    ``kernels`` has ``K*K`` row-major offset channels in the PyTorch
    cross-correlation convention of ``new_burn_probability``. Sources outside
    the tensor contribute zero; callers decide whether that is an assumption
    ('zero' boundary) or an availability failure (validity envelope).
    Nonfinite kernel entries must be replaced before calling.
    """
    k = isqrt(kernels.shape[-3])
    if k * k != kernels.shape[-3] or k < 3 or k % 2 != 1:
        raise ValueError("kernels must have K*K channels with odd K >= 3")
    if source.shape[-3] != 1 or source.shape[-2:] != kernels.shape[-2:]:
        raise ValueError("source must be [..., 1, H, W] on the kernel grid")
    if source.shape[:-3] != kernels.shape[:-3] or source.device != kernels.device:
        raise ValueError("source and kernels must share leading shape and device")
    if not bool(torch.isfinite(kernels).all()) or bool((kernels < 0).any()):
        raise ValueError("kernel_source_rate requires finite nonnegative kernels")
    if not bool(torch.isfinite(source).all()) or bool(((source < 0) | (source > 1)).any()):
        raise ValueError("source occupancy must be finite and lie in [0,1]")
    leading = tuple(kernels.shape[:-3])
    h, w = kernels.shape[-2:]
    unfolded = F.unfold(source.reshape(-1, 1, h, w).to(kernels.dtype), k, padding=k // 2)
    unfolded = unfolded.reshape(*leading, k * k, h, w)
    return (kernels * unfolded).sum(dim=-3, keepdim=True)


def mean_field_step(p: Tensor, kernels: Tensor, dt_hours: Real | Tensor, *,
                    source: Tensor | None = None, extra_rate: Tensor | None = None) -> Tensor:
    """One differentiable step ``p + (1 - p) * (1 - exp(-dt * lambda))``.

    ``source`` defaults to ``p`` (absorbing sources). ``extra_rate`` adds a
    nonnegative hourly rate, for example a long-range branch.
    """
    rate = kernel_source_rate(kernels, p if source is None else source)
    if extra_rate is not None:
        if extra_rate.shape != rate.shape or not bool(torch.isfinite(extra_rate).all()) or bool((extra_rate < 0).any()):
            raise ValueError("extra_rate must match the rate grid and be finite nonnegative")
        rate = rate + extra_rate
    return p + (1 - p) * -torch.expm1(-rate * dt_hours)


def model_kernel_components(model, environmental_data: Tensor, *, channel_names=None,
                            feature_valid: Tensor | None = None, boundary: str = "zero"):
    """Return ``[(component, weight, kernels)]`` from the model's own generator.

    Supported: ``TrainedBurnModel`` (raw channels; its saved normalization and
    one-hot validation are applied), ``BayesianBurnModel`` (each supported
    component with its posterior mass), any ``EnvironmentConditionedConvolution``
    with a burned-independent kernel (inputs already normalized), and any
    module exposing ``kernel_rates(environment, feature_valid, boundary=...)``.
    Kernels keep NaN where the environmental context is unknown.
    """
    if isinstance(model, BayesianBurnModel):
        if channel_names is None or tuple(channel_names) != model.channel_names:
            raise ValueError("Prediction channel names/order differ from the Bayesian checkpoint")
        active = torch.isfinite(model.log_posterior_weights)
        weights = torch.softmax(model.log_posterior_weights[active].double(), dim=0)
        members = [member for member, ok in zip(model.components, active) if bool(ok)]
        result = []
        for member, weight in zip(members, weights):
            (_, _, kernels), = model_kernel_components(
                member, environmental_data, channel_names=channel_names,
                feature_valid=feature_valid, boundary=boundary)
            result.append((member, float(weight), kernels))
        return result
    if isinstance(model, NormalizedBurnModel):
        if channel_names is None or tuple(channel_names) != model.channel_names:
            raise ValueError("Prediction channel names/order differ from the trained checkpoint")
        if isinstance(model.model, NeuralMixedNonnegativeKernel):
            raise TypeError("A neural mixed model's rate depends nonlinearly on burned inputs; "
                            "the mean field is undefined for it")
        model._validate_one_hot(environmental_data, feature_valid)
        kernels = model.model.kernel_rates((environmental_data - model.mean) / model.std,
                                           feature_valid, boundary=boundary)
        return [(model, 1.0, kernels)]
    if isinstance(model, NeuralMixedNonnegativeKernel):
        raise TypeError("A neural mixed model's rate depends nonlinearly on burned inputs; "
                        "the mean field is undefined for it")
    if isinstance(model, EnvironmentConditionedConvolution) or hasattr(model, "kernel_rates"):
        return [(model, 1.0, model.kernel_rates(environmental_data, feature_valid, boundary=boundary))]
    raise TypeError("Unsupported model for mean-field propagation")


def _probe_valid(component, base: Tensor, mask: Tensor, environment: Tensor,
                 feature_valid: Tensor | None, kernels: Tensor, channel_names, boundary: str) -> Tensor:
    """Rate availability on the binary initial state, exactly as the rollout envelope."""
    if isinstance(component, TrainedBurnModel):
        available = (feature_valid if feature_valid is not None
                     else torch.ones_like(environment, dtype=torch.bool))
        probe = component(base, environment, channel_names=channel_names,
                          burned_area_valid=mask, feature_valid=available,
                          dt_hours=1.0, boundary=boundary)
        return probe.rate_valid
    finite = torch.isfinite(kernels).all(dim=-3, keepdim=True)
    probe = new_burn_probability(base, torch.where(torch.isfinite(kernels), kernels, 0),
                                 burned_area_valid=mask, kernel_valid=finite, boundary=boundary)
    return probe.rate_valid


def propagate_mean_field(
    model, p0: Tensor, environment_sequence: Tensor | Sequence[Tensor],
    step_durations: Sequence[float], *, channel_names=None, p0_valid: Tensor | None = None,
    feature_valid: Tensor | Sequence[Tensor] | None = None, boundary: str = "zero",
    burnout=None, initial_age_hours: Tensor | None = None,
    extra_rate_fn: Callable[[Tensor, int], Tensor] | None = None,
) -> MeanFieldResult:
    """Evolve occupancy ``p0`` over ``step_durations`` (hours) in one pass per step.

    Args:
        model: see :func:`model_kernel_components`.
        p0: initial occupancy ``[..., 1, H, W]`` in [0, 1]; a binary map is the
            usual cutoff state. Values at unknown cells are ignored.
        environment_sequence: one ``[..., C, H, W]`` tensor repeated for every
            step (kernels generated once), or one tensor per step.
        step_durations: positive finite step lengths in hours, e.g. ``[1]*n``
            plus one final fraction for an exact survey endpoint.
        p0_valid: boolean availability of ``p0`` (default: finite values).
        feature_valid: availability of the environmental channels (one mask or
            one per step).
        boundary: 'zero' or 'unknown', as in ``new_burn_probability``.
        burnout: optional ``burnout.FlamingWindow``; sources then follow the
            flaming window instead of being absorbing forever.
        initial_age_hours: age since ignition of the initial occupancy at the
            cutoff (used only with ``burnout``; default zero).
        extra_rate_fn: optional ``f(source, step_index) -> rate`` added to the
            kernel rate (long-range branch); it must be nonnegative and
            should return NaN-free values. A callback using global covariates
            declares ``global_feature_valid`` as a Boolean tensor broadcastable
            to p0. Unknown global inputs remove unobserved targets from support;
            a finite internal placeholder never makes them known probabilities.

    Gradients flow through ``p0``, the environment and model parameters. The
    validity envelope is computed without gradients from the binary base
    state ``p0 == 1``; for binary inputs it is identical to the rollout.
    """
    if boundary not in ("zero", "unknown"):
        raise ValueError("boundary must be 'zero' or 'unknown'")
    durations = [float(value) for value in step_durations]
    if not durations or any(not torch.isfinite(torch.tensor(v)) or v <= 0 for v in durations):
        raise ValueError("step_durations must be a nonempty sequence of positive finite hours")
    sequence = (list(environment_sequence) if not isinstance(environment_sequence, Tensor)
                else None)
    if sequence is not None and len(sequence) != len(durations):
        raise ValueError("Supply one environment per step or a single repeated tensor")
    masks_seq = (list(feature_valid) if feature_valid is not None and not isinstance(feature_valid, Tensor)
                 else None)
    if masks_seq is not None and len(masks_seq) != len(durations):
        raise ValueError("Supply one feature mask per step")
    if p0.ndim < 3 or p0.shape[-3] != 1 or not p0.is_floating_point():
        raise ValueError("p0 must be floating [...,1,H,W]")
    if p0_valid is not None and (p0_valid.dtype != torch.bool or p0_valid.shape != p0.shape):
        raise ValueError("p0_valid must be Boolean and match p0")
    known = torch.isfinite(p0) if p0_valid is None else (p0_valid & torch.isfinite(p0))
    clean = torch.where(known, p0, torch.zeros_like(p0))
    if bool(((clean < 0) | (clean > 1)).any()):
        raise ValueError("p0 must lie in [0, 1] at known cells")
    observed_burns = known & (clean == 1)
    base = observed_burns.to(clean.dtype)

    def environment_at(k):
        env = environment_sequence if sequence is None else sequence[k]
        fv = masks_seq[k] if masks_seq is not None else feature_valid
        return env, fv

    cache: dict[int, list] = {}

    def components_at(k):
        env, fv = environment_at(k)
        key = 0 if sequence is None and masks_seq is None else k
        if key not in cache:
            cache.clear()
            cache[key] = model_kernel_components(model, env, channel_names=channel_names,
                                                 feature_valid=fv, boundary=boundary)
        return cache[key], env, fv

    first, _, _ = components_at(0)
    count = len(first)
    states = [clean for _ in range(count)]
    masks = [known for _ in range(count)]
    history = [[] for _ in range(count)]
    age0 = (torch.zeros_like(clean) if initial_age_hours is None
            else torch.where(known, initial_age_hours.to(clean.dtype), torch.zeros_like(clean)))
    if burnout is not None and (not bool(torch.isfinite(age0).all()) or bool((age0 < 0).any())):
        raise ValueError("Initial burnout ages must be finite and nonnegative")
    outputs, valids, elapsed = [], [], []
    clock = 0.0
    repeated = sequence is None and masks_seq is None
    # With repeated inputs the probe depends only on the mask; once a probe
    # leaves the mask unchanged every later probe returns the same mask, so
    # it is skipped (exact, not an approximation).
    converged = [False] * count
    safe_cache: dict[int, Tensor] = {}
    for k, dt in enumerate(durations):
        components, env, fv = components_at(k)
        for j, (component, _, kernels) in enumerate(components):
            if not (repeated and converged[j]):
                with torch.no_grad():
                    rate_valid = _probe_valid(component, base, masks[j], env, fv, kernels,
                                              channel_names, boundary)
                    following = masks[j] & (observed_burns | rate_valid)
                    converged[j] = bool(torch.equal(following, masks[j]))
                    masks[j] = following
            if not repeated or j not in safe_cache:
                safe_cache[j] = torch.where(torch.isfinite(kernels), kernels, torch.zeros_like(kernels))
            safe = safe_cache[j]
            if burnout is None:
                source = states[j]
            else:
                source = burnout.source(clean, age0, history[j], clock, current=states[j])
            if extra_rate_fn is not None:
                global_valid = getattr(extra_rate_fn, "global_feature_valid", None)
                if global_valid is not None:
                    if (not isinstance(global_valid, Tensor) or global_valid.dtype != torch.bool
                            or global_valid.device != masks[j].device):
                        raise ValueError("Extra-rate global_feature_valid must be a Boolean tensor on the forecast device")
                    try:
                        global_valid = torch.broadcast_to(global_valid, masks[j].shape)
                    except RuntimeError as error:
                        raise ValueError("Extra-rate global_feature_valid must broadcast to the forecast grid") from error
                    masks[j] = masks[j] & (observed_burns | global_valid)
            extra = None if extra_rate_fn is None else extra_rate_fn(source, k)
            if extra_rate_fn is not None:
                radius = getattr(extra_rate_fn, "source_radius", None)
                if radius is None:
                    if not bool(masks[j].all()):
                        raise ValueError("Extra-rate callbacks need a source_radius when source support is incomplete")
                else:
                    if type(radius) is not int or radius < 0:
                        raise ValueError("extra-rate source_radius must be a nonnegative integer")
                    h, w = masks[j].shape[-2:]
                    missing = (~masks[j]).to(states[j].dtype).reshape(-1, 1, h, w)
                    complete = F.max_pool2d(missing, 2 * radius + 1, stride=1, padding=radius) == 0
                    masks[j] = masks[j] & (observed_burns | complete.reshape_as(masks[j]))
            updated = mean_field_step(states[j], safe, dt, source=source, extra_rate=extra)
            # Cells outside the envelope keep their value; their dependents are invalid.
            updated = torch.where(masks[j], updated, states[j])
            history[j].append((clock + 0.5 * dt, updated - states[j]))
            states[j] = updated
        clock += dt
        weights = [weight for _, weight, _ in components]
        combined = sum(w * s for w, s in zip(weights, states)) if count > 1 else states[0]
        valid = torch.stack(masks).all(dim=0) if count > 1 else masks[0]
        outputs.append(combined)
        valids.append(valid)
        elapsed.append(clock)
    burned = torch.stack(outputs)
    valid = torch.stack(valids)
    new = torch.where(observed_burns.unsqueeze(0), torch.zeros_like(burned), burned)
    return MeanFieldResult(
        burned_probability=burned.masked_fill(~valid, torch.nan),
        new_burn_probability=new.masked_fill(~valid, torch.nan),
        valid=valid, elapsed_hours=tuple(elapsed),
    )
