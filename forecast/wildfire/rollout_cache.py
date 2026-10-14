"""Private environment preparation for repeated-condition M548 rollouts.

Prepared transitions retain the original inference batch shape. Computing one
kernel map and expanding it across trajectories can change floating-point
convolution results, so this helper deliberately prepares the full batch.
Only the existing linear mixed-kernel fitted wrapper is supported. The caller
must keep its fitted parameters and environmental conditions fixed while the
prepared transition is in use.
"""
from __future__ import annotations

from numbers import Integral

import torch

from .models import MixedNonnegativeKernel, TrainedBurnModel, new_burn_probability


def _instrumented(member):
    """Avoid bypassing either local or global forward instrumentation."""
    for module in member.modules():
        if module._forward_hooks or module._forward_pre_hooks:
            return True
    registry = torch.nn.modules.module
    return any(getattr(registry, name, {}) for name in (
        "_global_forward_hooks", "_global_forward_pre_hooks",
    ))


@torch.inference_mode()
def prepare_transition(member, environment, feature_valid, *, channel_names,
                       batch_size, boundary):
    """Prepare a state-dependent callable, or return ``None`` if unsupported.

    ``environment`` and its optional exact-shape mask contain one cutoff as
    ``[C,H,W]`` or ``[1,C,H,W]``. The returned callable accepts binary states
    ``[batch_size,1,H,W]``, their optional validity mask, and ``dt_hours``.
    It uses the ordinary kernel application and fitted eligibility rule; only
    repeated input validation, normalization, context preparation, and kernel
    generation are removed from subsequent calls.

    Unsupported families, subclasses, training mode, and forward hooks retain
    the original forward path through a ``None`` result. This function never
    modifies the model or consumes random numbers.
    """
    if (type(member) is not TrainedBurnModel
            or type(member.model) is not MixedNonnegativeKernel
            or any(module.training for module in member.modules())
            or _instrumented(member)):
        return None
    if (isinstance(batch_size, bool) or not isinstance(batch_size, Integral)
            or batch_size <= 0):
        raise ValueError("Prepared transition batch_size must be a positive integer excluding booleans")
    if tuple(channel_names) != member.channel_names:
        raise ValueError("Prediction channel names/order differ from the trained checkpoint")
    if not isinstance(environment, torch.Tensor):
        raise TypeError("Prepared transition environment must be a torch tensor")
    if environment.ndim == 4 and environment.shape[0] == 1:
        if feature_valid is not None and tuple(feature_valid.shape) != tuple(environment.shape):
            raise ValueError("Prepared transition feature_valid must exactly match environment shape")
        environment = environment[0]
        feature_valid = None if feature_valid is None else feature_valid[0]
    if environment.ndim != 3:
        raise ValueError("Prepared transition environment must contain one cutoff [C,H,W] or [1,C,H,W]")
    if feature_valid is not None and tuple(feature_valid.shape) != tuple(environment.shape):
        raise ValueError("Prepared transition feature_valid must exactly match environment shape")
    inputs = environment.unsqueeze(0).expand(int(batch_size), -1, -1, -1)
    masks = (None if feature_valid is None
             else feature_valid.unsqueeze(0).expand_as(inputs))
    member._validate_one_hot(inputs, masks)
    clean, available = member.model._features(
        (inputs - member.mean) / member.std, masks, boundary,
    )
    kernels = member.model._kernels(clean)

    @torch.inference_mode()
    def transition(states, burned_area_valid, dt_hours):
        prediction = new_burn_probability(
            states, kernels, burned_area_valid=burned_area_valid,
            kernel_valid=available, dt_hours=dt_hours, boundary=boundary,
        )
        if member.contract.get("eligibility") != "at_least_one_burned_neighbor":
            return prediction
        contact, known, complete_sources = member._contact(
            states, burned_area_valid, boundary=boundary,
        )
        structural_zero = known & (states == 0) & complete_sources & ~contact
        valid = prediction.valid & (contact | (known & (states == 1)) | structural_zero)
        rate_valid = prediction.rate_valid & (contact | structural_zero)
        return type(prediction)(
            prediction.probability.masked_fill(~valid, torch.nan), valid,
            prediction.rate.masked_fill(~rate_valid, torch.nan), rate_valid,
        )

    return transition
