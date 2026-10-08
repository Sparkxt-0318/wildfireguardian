"""Environmental kernels acting on current burned cells to predict new burns.

This is a local, constant-rate transition model, not a fitted forecast. A
kernel coefficient has units of inverse hours per burned neighboring cell.
Kernels use the PyTorch cross-correlation convention: coefficient (dy, dx)
multiplies the source at (target_row + dy, target_column + dx).
"""

from dataclasses import dataclass
from math import isqrt
from numbers import Real

import torch
from torch import Tensor, nn
from torch.nn import functional as F


@dataclass(frozen=True)
class BurnProbability:
    """New-burn probability and rate, each shaped ``[..., 1, H, W]``.

    ``valid`` describes the probability; ``rate_valid`` describes the rate.
    Unavailable values are NaN. A known already-burned cell, or a known cell
    with a zero horizon, has probability zero even when its rate is unknown.
    """

    probability: Tensor
    valid: Tensor
    rate: Tensor
    rate_valid: Tensor


def _check_grid(value: Tensor, name: str, channels: int | None = None) -> None:
    if not isinstance(value, Tensor):
        raise TypeError(f"{name} must be a torch.Tensor")
    if value.ndim < 3 or any(size == 0 for size in value.shape):
        raise ValueError(f"{name} must have nonempty shape [..., C, H, W]")
    if channels is not None and value.shape[-3] != channels:
        raise ValueError(f"{name} must have {channels} channel(s)")


def _valid_mask(mask: Tensor | None, value: Tensor, name: str) -> Tensor:
    if mask is None:
        return torch.ones_like(value, dtype=torch.bool)
    if not isinstance(mask, Tensor) or mask.dtype != torch.bool:
        raise TypeError(f"{name} must be a boolean torch.Tensor")
    if mask.shape != value.shape or mask.device != value.device:
        raise ValueError(f"{name} must match the data shape and device exactly")
    return mask


def _duration(dt_hours: Real | Tensor, leading: tuple, reference: Tensor) -> Tensor:
    if isinstance(dt_hours, Tensor):
        if dt_hours.device != reference.device:
            raise ValueError("dt_hours and the input tensors must be on the same device")
        if dt_hours.is_complex() or dt_hours.dtype == torch.bool:
            raise TypeError("dt_hours must be real numeric data")
        duration = dt_hours.to(dtype=reference.dtype)
    elif isinstance(dt_hours, Real) and not isinstance(dt_hours, bool):
        duration = reference.new_tensor(dt_hours)
    else:
        raise TypeError("dt_hours must be a real scalar or torch.Tensor")
    if duration.ndim != 0 and tuple(duration.shape) != leading:
        raise ValueError("dt_hours must be scalar or match the leading dimensions exactly")
    if not bool(torch.isfinite(duration).all()) or bool((duration < 0).any()):
        raise ValueError("dt_hours must be finite and nonnegative")
    # Explicit reshaping prevents a [B] horizon from broadcasting along W.
    return duration.reshape((*duration.shape, 1, 1, 1))


def new_burn_probability(
    burned_area: Tensor,
    kernel_rates: Tensor,
    *,
    dt_hours: Real | Tensor = 1.0,
    burned_area_valid: Tensor | None = None,
    kernel_valid: Tensor | None = None,
    boundary: str = "unknown",
) -> BurnProbability:
    """Apply position-dependent kernels and return new-burn probabilities.

    Args:
        burned_area: Binary current cumulative burned state, [..., 1, H, W].
            Values at missing/invalid cells are ignored. Nonfinite values are
            automatically unavailable; a finite value other than 0 or 1 at
            a valid cell is an error (mask NoData such as 255 explicitly).
        kernel_rates: Nonnegative hourly contributions, [..., K*K, H, W],
            where K is odd and at least 3. Channels enumerate offsets in row
            order, from (-r, -r) through (r, r), where r = K//2. Each target has
            its own kernel. No normalization over neighbors is performed.
        dt_hours: Finite nonnegative scalar, or tensor of exact shape [...]
            matching the input leading dimensions. The rate is frozen over
            this interval; this call does not recursively propagate fire.
        burned_area_valid: Boolean mask of the same shape as burned_area.
        kernel_valid: Boolean target-level mask [..., 1, H, W], for example
            indicating that all environmental predictors are available.
        boundary: 'unknown' invalidates targets depending on outside-grid
            sources; 'zero' explicitly assumes no contribution from outside
            the tensor. Missing cells inside the tensor always stay unknown.

    For a known unburned target i, lambda_i = sum_delta K_i,delta B_i+delta
    and P(newly burned during dt) = 1 - exp(-dt * lambda_i). Already burned
    cells have new-burn probability zero. Every positive-weight source must
    be known; unknown sources are never interpreted as observed zeros.
    """
    _check_grid(burned_area, "burned_area", 1)
    _check_grid(kernel_rates, "kernel_rates")
    if not kernel_rates.is_floating_point():
        raise TypeError("kernel_rates must have a floating-point dtype")
    if burned_area.is_complex():
        raise TypeError("burned_area must contain real binary values")
    if burned_area.device != kernel_rates.device:
        raise ValueError("burned_area and kernel_rates must be on the same device")
    leading = tuple(burned_area.shape[:-3])
    if (tuple(kernel_rates.shape[:-3]) != leading
            or kernel_rates.shape[-2:] != burned_area.shape[-2:]):
        raise ValueError("burned_area and kernel_rates must share leading and spatial dimensions")
    k = isqrt(kernel_rates.shape[-3])
    if k * k != kernel_rates.shape[-3] or k < 3 or k % 2 != 1:
        raise ValueError("kernel_rates must have K*K channels with odd K >= 3")
    if boundary not in ("unknown", "zero"):
        raise ValueError("boundary must be 'unknown' or 'zero'")
    observed = _valid_mask(burned_area_valid, burned_area, "burned_area_valid")
    observed = observed & torch.isfinite(burned_area)
    if bool((observed & (burned_area != 0) & (burned_area != 1)).any()):
        raise ValueError("Valid burned_area values must be exactly 0 or 1")
    target_valid = _valid_mask(kernel_valid, burned_area, "kernel_valid")
    finite_kernels = torch.isfinite(kernel_rates).all(dim=-3, keepdim=True)
    if bool(((kernel_rates < 0) & target_valid.expand_as(kernel_rates)).any()):
        raise ValueError("Valid kernel_rates must be nonnegative")
    target_valid = target_valid & finite_kernels
    duration = _duration(dt_hours, leading, kernel_rates)
    h, w = burned_area.shape[-2:]
    radius = k // 2
    source = torch.where(observed, burned_area, 0).to(dtype=kernel_rates.dtype)
    sources = F.unfold(source.reshape(-1, 1, h, w), k, padding=radius)
    sources = sources.reshape(*leading, k * k, h, w)
    # Pad availability separately from numeric values, so zero padding does
    # not turn an unknown neighbor into a known unburned neighbor.
    known = observed.to(dtype=kernel_rates.dtype).reshape(-1, 1, h, w)
    known = F.pad(known, (radius,) * 4, value=1.0 if boundary == "zero" else 0.0)
    known = F.unfold(known, k).reshape(*leading, k * k, h, w) > 0.5
    safe_kernels = torch.where(target_valid.expand_as(kernel_rates), kernel_rates, 0)
    dependencies_known = (known | (safe_kernels == 0)).all(dim=-3, keepdim=True)
    raw_rate = (safe_kernels * sources).sum(dim=-3, keepdim=True)
    rate_valid = observed & target_valid & dependencies_known & torch.isfinite(raw_rate)
    safe_rate = torch.where(rate_valid, raw_rate, 0)
    probability = -torch.expm1(-safe_rate * duration)
    already_burned = observed & (burned_area == 1)
    probability = torch.where(already_burned, 0, probability)
    valid = observed & (already_burned | (duration == 0) | rate_valid)
    return BurnProbability(
        probability=probability.masked_fill(~valid, torch.nan),
        valid=valid,
        rate=raw_rate.masked_fill(~rate_valid, torch.nan),
        rate_valid=rate_valid,
    )


class EnvironmentConditionedConvolution(nn.Module):
    """Learn a different nonnegative burned-source kernel at every target.

    A spatial neural network reads the K-by-K environmental neighborhood of
    each target and generates K*K rate contributions. The generated kernels
    then act on burned_area only.
    The center contribution is fixed to zero. Features must already use an
    appropriate numeric encoding and training-only normalization; categorical
    source codes are not automatically encoded. Initial weights are untrained.

    Sample [T,C,H,W] and batch [B,T,C,H,W] layouts from WildfireSequenceDataset
    work directly. Leading dimensions are independent snapshots, not a time
    recurrence. Supply only information available at the current cutoff.
    """

    def __init__(self, in_channels: int, kernel_size: int = 3, hidden_channels: int = 16):
        super().__init__()
        for name, value in (("in_channels", in_channels), ("hidden_channels", hidden_channels)):
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if (not isinstance(kernel_size, int) or isinstance(kernel_size, bool)
                or kernel_size < 3 or kernel_size % 2 != 1):
            raise ValueError("kernel_size must be an odd integer >= 3")
        self.in_channels = in_channels
        self.kernel_size = kernel_size
        self.kernel_network = nn.Sequential(
            nn.Conv2d(in_channels, hidden_channels, kernel_size, padding=kernel_size // 2),
            nn.SiLU(),
            nn.Conv2d(hidden_channels, kernel_size * kernel_size, 1),
        )
        off_center = torch.ones(1, kernel_size * kernel_size, 1, 1)
        off_center[:, kernel_size * kernel_size // 2] = 0
        self.register_buffer("off_center", off_center)

    def _features(self, environmental_data: Tensor, feature_valid: Tensor | None, boundary: str):
        _check_grid(environmental_data, "environmental_data", self.in_channels)
        if not environmental_data.is_floating_point():
            raise TypeError("environmental_data must have a floating-point dtype")
        parameter = next(self.parameters())
        if environmental_data.device != parameter.device or environmental_data.dtype != parameter.dtype:
            raise ValueError("environmental_data must match the model device and dtype")
        available = _valid_mask(feature_valid, environmental_data, "feature_valid")
        available = available & torch.isfinite(environmental_data)
        clean = torch.where(available, environmental_data, 0)
        if boundary not in ("unknown", "zero"):
            raise ValueError("boundary must be 'unknown' or 'zero'")
        h, w = clean.shape[-2:]
        known = available.all(dim=-3, keepdim=True).to(dtype=clean.dtype).reshape(-1, 1, h, w)
        radius = self.kernel_size // 2
        known = F.pad(known, (radius,) * 4, value=1.0 if boundary == "zero" else 0.0)
        context_known = F.avg_pool2d(known, self.kernel_size, stride=1) == 1
        context_known = context_known.reshape(*clean.shape[:-3], 1, h, w)
        return clean, context_known

    def _kernels(self, clean: Tensor) -> Tensor:
        leading = tuple(clean.shape[:-3])
        c, h, w = clean.shape[-3:]
        logits = self.kernel_network(clean.reshape(-1, c, h, w))
        if not bool(torch.isfinite(logits).all()):
            raise RuntimeError(
                "The kernel generator produced nonfinite values; check feature "
                "scaling and model parameters before computing probabilities"
            )
        rates = F.softplus(logits) * self.off_center
        return rates.reshape(*leading, self.kernel_size * self.kernel_size, h, w)

    def kernel_rates(
        self, environmental_data: Tensor, feature_valid: Tensor | None = None,
        *, boundary: str = "unknown",
    ) -> Tensor:
        """Return hourly weights [..., K*K, H, W]; unknown contexts are NaN.

        The full environmental neighborhood must be available. 'zero' opts
        into zero-valued environmental features outside the tensor as well
        as the no-exterior-burned-source assumption used by forward().
        """
        clean, available = self._features(environmental_data, feature_valid, boundary)
        rates = self._kernels(clean)
        return rates.masked_fill(~available.expand_as(rates), torch.nan)

    def forward(
        self,
        burned_area: Tensor,
        environmental_data: Tensor,
        *,
        dt_hours: Real | Tensor = 1.0,
        burned_area_valid: Tensor | None = None,
        feature_valid: Tensor | None = None,
        boundary: str = "unknown",
    ) -> BurnProbability:
        """Return differentiable probabilities for newly burning cells."""
        _check_grid(burned_area, "burned_area", 1)
        clean, available = self._features(environmental_data, feature_valid, boundary)
        if (burned_area.shape[:-3] != clean.shape[:-3]
                or burned_area.shape[-2:] != clean.shape[-2:]):
            raise ValueError("burned_area and environmental_data must be on the same grid")
        return new_burn_probability(
            burned_area, self._kernels(clean), dt_hours=dt_hours,
            burned_area_valid=burned_area_valid, kernel_valid=available,
            boundary=boundary,
        )


def center_probability(model: EnvironmentConditionedConvolution, environment: Tensor, burned: Tensor) -> Tensor:
    """Evaluate exactly the public model's center on complete K-by-K patches."""
    size = model.kernel_size
    if environment.ndim != 4 or tuple(environment.shape[1:]) != (model.in_channels, size, size):
        raise ValueError("Center evaluation requires complete N,C,K,K environmental patches")
    if burned.shape != (environment.shape[0], 1, size, size):
        raise ValueError("Center evaluation requires matching N,1,K,K burned patches")
    first, activation, second = model.kernel_network
    hidden = activation(F.conv2d(environment, first.weight, first.bias, padding=0))
    logits = F.conv2d(hidden, second.weight, second.bias)
    if not bool(torch.isfinite(logits).all()):
        raise RuntimeError("The center kernel generator produced nonfinite logits")
    rates = F.softplus(logits) * model.off_center
    rate = (rates.flatten(1) * burned.flatten(1)).sum(dim=1)
    if not bool(torch.isfinite(rate).all()):
        raise RuntimeError("The center convolution produced a nonfinite transition rate")
    return -torch.expm1(-rate)

