"""One-hour direct convolution scores, with clipping only for evaluation.

Coefficients are dimensionless. A score is the cross-correlation of a
position-dependent learned kernel and the current binary burned map; it is
not an hourly rate. Training must use ``raw_score`` or ``center_raw_score``.
The separately exposed ``probability`` is ``clamp(raw_score, 0, 1)``.
"""

from dataclasses import dataclass
from math import isqrt
from numbers import Real

import torch
from torch import Tensor, nn
from torch.nn import functional as F

from ..model import EnvironmentConditionedConvolution, _check_grid, _valid_mask


@dataclass(frozen=True)
class DirectBurnPrediction:
    """Raw score and evaluation probability, shaped ``[...,1,H,W]``.

    ``valid`` describes both outputs. Unknown targets are NaN; a known
    already-burned target has zero new-burn score and probability. A raw
    score may be negative or exceed one. Only probability is clipped.
    """

    raw_score: Tensor
    probability: Tensor
    valid: Tensor


def _one_hour(dt_hours: Real | Tensor, leading: tuple, reference: Tensor) -> None:
    """Reject horizons other than the fixed one-hour training endpoint."""
    if isinstance(dt_hours, Tensor):
        if dt_hours.device != reference.device:
            raise ValueError("dt_hours and input tensors must share a device")
        if dt_hours.is_complex() or dt_hours.dtype == torch.bool:
            raise TypeError("dt_hours must be real numeric data")
        if dt_hours.ndim and tuple(dt_hours.shape) != leading:
            raise ValueError("dt_hours must be scalar or match leading dimensions")
        valid = bool(torch.isfinite(dt_hours).all() & (dt_hours == 1).all())
    elif isinstance(dt_hours, Real) and not isinstance(dt_hours, bool):
        valid = dt_hours == 1.0
    else:
        raise TypeError("dt_hours must be a real scalar or torch.Tensor")
    if not valid:
        raise ValueError("Direct convolution is fitted only for dt_hours=1.0")


def apply_direct_convolution(
    burned_area: Tensor,
    kernel_coefficients: Tensor,
    *,
    dt_hours: Real | Tensor = 1.0,
    burned_area_valid: Tensor | None = None,
    kernel_valid: Tensor | None = None,
    boundary: str = "unknown",
) -> DirectBurnPrediction:
    """Return the unclipped kernel sum and its clipped evaluation view.

    Channels enumerate offsets in row order. Each coefficient multiplies
    the source at target + offset. Full source context must be observed;
    missing sources are never interpreted as known unburned cells. 'zero'
    explicitly assumes no outside-grid burned sources.
    """
    _check_grid(burned_area, "burned_area", 1)
    _check_grid(kernel_coefficients, "kernel_coefficients")
    if not kernel_coefficients.is_floating_point():
        raise TypeError("kernel_coefficients must have a floating-point dtype")
    if burned_area.is_complex():
        raise TypeError("burned_area must contain real binary values")
    if burned_area.device != kernel_coefficients.device:
        raise ValueError("burned_area and coefficients must share a device")
    leading = tuple(burned_area.shape[:-3])
    if (kernel_coefficients.shape[:-3] != burned_area.shape[:-3]
            or kernel_coefficients.shape[-2:] != burned_area.shape[-2:]):
        raise ValueError("Burned map and coefficients must share the same grid")
    k = isqrt(kernel_coefficients.shape[-3])
    if k * k != kernel_coefficients.shape[-3] or k < 3 or k % 2 != 1:
        raise ValueError("Coefficients need K*K channels with odd K >= 3")
    if boundary not in ("unknown", "zero"):
        raise ValueError("boundary must be 'unknown' or 'zero'")
    _one_hour(dt_hours, leading, kernel_coefficients)
    observed = _valid_mask(burned_area_valid, burned_area, "burned_area_valid")
    observed = observed & torch.isfinite(burned_area)
    if bool((observed & (burned_area != 0) & (burned_area != 1)).any()):
        raise ValueError("Valid burned_area values must be exactly 0 or 1")
    available = _valid_mask(kernel_valid, burned_area, "kernel_valid")
    available = available & torch.isfinite(kernel_coefficients).all(-3, keepdim=True)
    h, w = burned_area.shape[-2:]
    radius = k // 2
    source = torch.where(observed, burned_area, 0).to(kernel_coefficients.dtype)
    patches = F.unfold(source.reshape(-1, 1, h, w), k, padding=radius)
    patches = patches.reshape(*leading, k * k, h, w)
    known = observed.to(kernel_coefficients.dtype).reshape(-1, 1, h, w)
    known = F.pad(known, (radius,) * 4, value=float(boundary == "zero"))
    complete_sources = (F.avg_pool2d(known, k, stride=1) == 1).reshape_as(burned_area)
    safe_coefficients = torch.where(available.expand_as(kernel_coefficients), kernel_coefficients, 0)
    raw = (safe_coefficients * patches).sum(-3, keepdim=True)
    already_burned = observed & (burned_area == 1)
    valid = observed & (already_burned | (available & complete_sources & torch.isfinite(raw)))
    raw = torch.where(already_burned, 0, raw).masked_fill(~valid, torch.nan)
    return DirectBurnPrediction(raw, torch.clamp(raw, 0, 1), valid)


class DirectEnvironmentConditionedConvolution(nn.Module):
    """Generate a distinct kernel from each target's environmental KxK patch.

    Signed coefficients are the default. ``kernel_constraint='nonnegative'``
    additionally supports softplus coefficients. The center coefficient is
    always zero. Neither mode applies an output link or clips training scores.
    Features must already be encoded and normalized with training statistics.
    """

    _features = EnvironmentConditionedConvolution._features

    def __init__(self, in_channels: int, kernel_size: int = 3,
                 hidden_channels: int = 16, kernel_constraint: str = "signed"):
        super().__init__()
        for name, value in (("in_channels", in_channels), ("hidden_channels", hidden_channels)):
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if (not isinstance(kernel_size, int) or isinstance(kernel_size, bool)
                or kernel_size < 3 or kernel_size % 2 != 1):
            raise ValueError("kernel_size must be an odd integer >= 3")
        if kernel_constraint not in ("signed", "nonnegative"):
            raise ValueError("kernel_constraint must be 'signed' or 'nonnegative'")
        self.in_channels = in_channels
        self.kernel_size = kernel_size
        self.hidden_channels = hidden_channels
        self.kernel_constraint = kernel_constraint
        self.kernel_network = nn.Sequential(
            nn.Conv2d(in_channels, hidden_channels, kernel_size, padding=kernel_size // 2),
            nn.SiLU(),
            nn.Conv2d(hidden_channels, kernel_size * kernel_size, 1),
        )
        off_center = torch.ones(1, kernel_size * kernel_size, 1, 1)
        off_center[:, kernel_size * kernel_size // 2] = 0
        self.register_buffer("off_center", off_center)

    def coefficients_from_logits(self, logits: Tensor) -> Tensor:
        """Apply the coefficient constraint and fixed zero center only."""
        if not bool(torch.isfinite(logits).all()):
            raise RuntimeError("Kernel generator produced nonfinite coefficients")
        values = F.softplus(logits) if self.kernel_constraint == "nonnegative" else logits
        return values * self.off_center

    def _kernels(self, clean: Tensor) -> Tensor:
        leading = tuple(clean.shape[:-3])
        c, h, w = clean.shape[-3:]
        logits = self.kernel_network(clean.reshape(-1, c, h, w))
        return self.coefficients_from_logits(logits).reshape(
            *leading, self.kernel_size * self.kernel_size, h, w,
        )

    def kernel_coefficients(self, environmental_data: Tensor, feature_valid: Tensor | None = None,
                            *, boundary: str = "unknown") -> Tensor:
        """Return dimensionless coefficients; unknown neighborhoods are NaN."""
        clean, valid = self._features(environmental_data, feature_valid, boundary)
        return self._kernels(clean).masked_fill(~valid, torch.nan)

    def forward(self, burned_area: Tensor, environmental_data: Tensor, *,
                dt_hours: Real | Tensor = 1.0,
                burned_area_valid: Tensor | None = None,
                feature_valid: Tensor | None = None,
                boundary: str = "unknown") -> DirectBurnPrediction:
        """Calculate a raw training score and separate clipped evaluation view."""
        _check_grid(burned_area, "burned_area", 1)
        clean, available = self._features(environmental_data, feature_valid, boundary)
        if burned_area.shape[:-3] != clean.shape[:-3] or burned_area.shape[-2:] != clean.shape[-2:]:
            raise ValueError("Burned map and environmental features must share a grid")
        return apply_direct_convolution(
            burned_area, self._kernels(clean), dt_hours=dt_hours,
            burned_area_valid=burned_area_valid, kernel_valid=available, boundary=boundary,
        )


def center_raw_score(model: DirectEnvironmentConditionedConvolution,
                     burned_area: Tensor, environmental_data: Tensor) -> Tensor:
    """Efficient unclipped center scores for complete NxCxKxK training patches.

    This is the exact center calculation of the public spatial forward pass.
    No padding, exponential, sigmoid, or output clipping is performed.
    """
    k = model.kernel_size
    if (environmental_data.ndim != 4 or environmental_data.shape[1:] != (model.in_channels, k, k)
            or burned_area.shape != (len(environmental_data), 1, k, k)):
        raise ValueError("Center scoring requires NxCxKxK features and Nx1xKxK burned patches")
    parameter = next(model.parameters())
    if environmental_data.device != parameter.device or environmental_data.dtype != parameter.dtype:
        raise ValueError("Environmental features must match model device and dtype")
    if burned_area.device != parameter.device:
        raise ValueError("Burned patches must share model device")
    if not bool(torch.isfinite(environmental_data).all() & torch.isfinite(burned_area).all()):
        raise ValueError("Center scoring requires complete finite patches")
    if bool(((burned_area != 0) & (burned_area != 1)).any()):
        raise ValueError("Burned patches must contain binary values")
    first = model.kernel_network[0]
    hidden = F.silu(F.conv2d(environmental_data, first.weight, first.bias))
    logits = model.kernel_network[2](hidden)
    coefficients = model.coefficients_from_logits(logits).flatten(1)
    raw = (coefficients * burned_area.to(environmental_data.dtype).flatten(1)).sum(1)
    return torch.where(burned_area[:, 0, k // 2, k // 2] == 1, 0, raw)
