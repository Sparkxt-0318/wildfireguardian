"""All maintained machine learning models for hourly new-burn probability.

Each family preserves its input, availability, probability-link, and saved
checkpoint contracts. Models are defined here in dependency order: the base
transition, learned kernels, multiscale mixtures, neural mixtures, and random
forest. Construction does not fit model parameters or data preprocessing.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass
from math import isqrt
from numbers import Real
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import torch
from torch import Tensor, nn
from torch.nn import functional as F

from .paths import resolve_recorded_path
from .schema import SCHEMA_KEYS, one_hot_groups, probability_target_id

__all__ = [
    "BurnProbability", "EnvironmentConditionedConvolution", "new_burn_probability",
    "center_probability", "KERNEL_ARCHITECTURES", "LearnedNonnegativeKernel",
    "build_kernel_model", "kernel_model_configuration", "initialize_kernel_rate",
    "MIXING_CONSTRAINTS", "MixedNonnegativeKernel", "build_mixed_kernel_model",
    "mixed_model_configuration", "mixed_kernel_model_configuration",
    "initialize_mixed_kernel_rate", "NeuralMixedNonnegativeKernel",
    "build_neural_mixed_kernel_model", "neural_mixed_model_configuration",
    "initialize_neural_mixed_kernel_rate", "PatchRandomForest",
    "NormalizedBurnModel", "TrainedBurnModel", "BayesianBurnModel",
    "bayesian_model_weights",
]


# Base transition model
# ---------------------
# Environmental kernels acting on current burned cells to predict new burns.
#
# This is a local, constant-rate transition model, not a fitted forecast. A
# kernel coefficient has units of inverse hours per burned neighboring cell.
# Kernels use the PyTorch cross-correlation convention: coefficient (dy, dx)
# multiplies the source at (target_row + dy, target_column + dx).

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
    implementation = getattr(model, "center_probability", None)
    if implementation is not None:
        return implementation(environment, burned)
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


# Learned kernel families
# -----------------------
# Nonnegative environmental kernel families with one common probability link.
#
# Every family predicts hourly offset contributions, fixes the center to zero,
# and computes ``q = 1 - exp(-sum(kernel * current_burned_neighbors))``. Neural
# families read the complete K-by-K environmental patch. CNN preserves every
# patch position; linear and MLP families use its per-channel spatial mean.
# The ``linear`` family is linear in that mean before softplus; ``constant`` ignores its values and
# learns a separate parameter for each offset. All families retain the same
# complete-context availability contract for comparable saved inference.

KERNEL_ARCHITECTURES = ("constant", "linear", "cnn", "mlp", "residual_mlp")


class _ConstantGenerator(nn.Module):
    def __init__(self, offsets: int):
        super().__init__()
        self.logits = nn.Parameter(torch.zeros(1, offsets, 1, 1))

    def forward(self, environment: Tensor) -> Tensor:
        return self.logits.expand(environment.shape[0], -1, *environment.shape[-2:])

    def center_logits(self, environment: Tensor) -> Tensor:
        return self.logits.expand(environment.shape[0], -1, 1, 1)


class _ResidualBlock(nn.Module):
    def __init__(self, width: int, dropout: float):
        super().__init__()
        self.update = nn.Sequential(
            nn.Conv2d(width, width, 1), nn.SiLU(), nn.Dropout2d(dropout),
            nn.Conv2d(width, width, 1),
        )

    def forward(self, hidden: Tensor) -> Tensor:
        return F.silu(hidden + self.update(hidden))


class _PatchGenerator(nn.Module):
    def __init__(self, in_channels: int, size: int, architecture: str,
                 width: int, depth: int, dropout: float):
        super().__init__()
        self.kernel_size = size
        self.pooled = architecture != "cnn"
        spatial_size = 1 if self.pooled else size
        self.spatial = nn.Conv2d(
            in_channels, size * size if architecture == "linear" else width,
            spatial_size, padding=spatial_size // 2,
        )
        if architecture == "linear":
            self.hidden = nn.Identity()
            self.output = nn.Identity()
            return
        layers: list[nn.Module] = [nn.SiLU(), nn.Dropout2d(dropout)]
        if architecture == "mlp":
            for _ in range(depth - 1):
                layers.extend((nn.Conv2d(width, width, 1), nn.SiLU(), nn.Dropout2d(dropout)))
        elif architecture == "residual_mlp":
            layers.extend(_ResidualBlock(width, dropout) for _ in range(depth - 1))
        self.hidden = nn.Sequential(*layers)
        self.output = nn.Conv2d(width, size * size, 1)

    def forward(self, environment: Tensor) -> Tensor:
        if self.pooled:
            environment = F.avg_pool2d(
                environment, self.kernel_size, stride=1,
                padding=self.kernel_size // 2, count_include_pad=True,
            )
        return self.output(self.hidden(self.spatial(environment)))

    def center_logits(self, environment: Tensor) -> Tensor:
        if self.pooled:
            environment = environment.mean(dim=(-2, -1), keepdim=True)
        hidden = F.conv2d(environment, self.spatial.weight, self.spatial.bias, padding=0)
        return self.output(self.hidden(hidden))

    def features_logits(self, features: Tensor) -> Tensor:
        if self.pooled:
            features = features[:, :, None, None]
        hidden = F.conv2d(features, self.spatial.weight, self.spatial.bias, padding=0)
        return self.output(self.hidden(hidden))


class LearnedNonnegativeKernel(EnvironmentConditionedConvolution):
    """Configurable environment-to-kernel architecture using the public grid API.

    ``depth`` is the number of hidden transformations for MLP families. The
    first reads the full environmental patch's channel means; later ones act
    on its embedding. CNN reads every environmental patch position.
    A residual transformation contains two width-by-width affine maps. CNN
    always has one hidden transformation. Constant and linear have no hidden
    transformations. Dropout acts only while training and can be combined
    with optimizer weight decay without altering the probability link.
    """

    def __init__(self, in_channels: int, kernel_size: int = 3,
                 architecture: str = "cnn", hidden_channels: int = 16,
                 depth: int = 2, dropout: float = 0.0):
        super().__init__(in_channels, kernel_size, hidden_channels)
        if architecture not in KERNEL_ARCHITECTURES:
            raise ValueError(f"architecture must be one of {KERNEL_ARCHITECTURES}")
        if not isinstance(depth, int) or isinstance(depth, bool) or depth < 1:
            raise ValueError("depth must be a positive integer")
        if (isinstance(dropout, bool) or not isinstance(dropout, (int, float))
                or not math.isfinite(dropout) or not 0 <= dropout < 1):
            raise ValueError("dropout must be a finite probability in [0, 1)")
        if architecture in ("constant", "linear") and dropout != 0:
            raise ValueError("constant and linear kernels do not use dropout")
        self.architecture = architecture
        self.hidden_channels = hidden_channels
        self.depth = depth if architecture in ("mlp", "residual_mlp") else (1 if architecture == "cnn" else 0)
        self.dropout = float(dropout)
        if architecture == "constant":
            self.kernel_network = _ConstantGenerator(kernel_size * kernel_size)
        else:
            self.kernel_network = _PatchGenerator(
                in_channels, kernel_size, architecture, hidden_channels, self.depth, self.dropout,
            )

    def center_probability(self, environment: Tensor, burned: Tensor) -> Tensor:
        """Evaluate complete N,C,K,K patches without materializing grid unfolds.

        Environmental and burned states must be known. Both currently burned
        centers and completely unburned neighborhoods yield exact zero new-
        burn probability, matching the full-grid forward method at one hour.
        """
        return self.center_from_features(self.center_features(environment), burned)

    def center_features(self, environment: Tensor) -> Tensor:
        """Cache data-only patch features before repeated training epochs.

        The returned tensor is N,C for constant/linear/MLP families and the
        original N,C,K,K tensor for CNN. Apply saved/training-only normalization
        before this method. No model parameter participates in this transform.
        """
        size = self.kernel_size
        if environment.ndim != 4 or tuple(environment.shape[1:]) != (self.in_channels, size, size):
            raise ValueError("Center evaluation requires complete N,C,K,K environmental patches")
        parameter = next(self.parameters())
        if environment.device != parameter.device or environment.dtype != parameter.dtype:
            raise ValueError("Center input data must match the model device and environmental dtype")
        if not bool(torch.isfinite(environment).all()):
            raise ValueError("Center environmental patches must be finite and completely known")
        if self.architecture == "cnn":
            return environment
        return environment.mean(dim=(-2, -1))

    def center_from_features(self, features: Tensor, burned: Tensor) -> Tensor:
        """Evaluate precomputed normalized features and complete burned patches."""
        size = self.kernel_size
        expected = (self.in_channels, size, size) if self.architecture == "cnn" else (self.in_channels,)
        if tuple(features.shape[1:]) != expected or features.ndim != len(expected) + 1:
            raise ValueError("Cached center features have the wrong architecture-specific shape")
        if burned.shape != (features.shape[0], 1, size, size):
            raise ValueError("Center evaluation requires matching N,1,K,K burned patches")
        parameter = next(self.parameters())
        if (features.device != parameter.device or features.dtype != parameter.dtype
                or burned.device != parameter.device):
            raise ValueError("Center input data must match the model device and environmental dtype")
        if not bool(torch.isfinite(features).all()):
            raise ValueError("Cached center features must be finite and completely known")
        if not bool(torch.isfinite(burned).all()) or bool(((burned != 0) & (burned != 1)).any()):
            raise ValueError("Center burned patches must contain known binary states")
        logits = (self.kernel_network.logits.expand(features.shape[0], -1, 1, 1)
                  if self.architecture == "constant" else self.kernel_network.features_logits(features))
        if not bool(torch.isfinite(logits).all()):
            raise RuntimeError("The center kernel generator produced nonfinite logits")
        rates = F.softplus(logits) * self.off_center
        rate = (rates.flatten(1) * burned.flatten(1)).sum(dim=1)
        if not bool(torch.isfinite(rate).all()):
            raise RuntimeError("The center convolution produced a nonfinite transition rate")
        probability = -torch.expm1(-rate)
        return torch.where(burned[:, 0, size // 2, size // 2] == 1, 0, probability)


def build_kernel_model(in_channels: int, kernel_size: int = 3,
                       architecture: str = "cnn", hidden_channels: int = 16,
                       depth: int = 2, dropout: float = 0.0) -> LearnedNonnegativeKernel:
    """Construct an untrained kernel; no data or normalization is fitted here."""
    return LearnedNonnegativeKernel(
        in_channels, kernel_size, architecture, hidden_channels, depth, dropout,
    )


def kernel_model_configuration(model: nn.Module) -> dict:
    """Return the reconstructible architecture fields for a checkpoint contract."""
    if not isinstance(model, LearnedNonnegativeKernel):
        raise TypeError("kernel_model_configuration requires a LearnedNonnegativeKernel")
    return {
        "architecture": model.architecture, "hidden_channels": model.hidden_channels,
        "depth": max(1, model.depth), "dropout": model.dropout,
    }


@torch.no_grad()
def initialize_kernel_rate(model: nn.Module, rate: float) -> None:
    """Initialize every noncenter offset to a common finite positive hourly rate.

    Only the final affine output is reset. Earlier neural layers retain their
    sampled initialization and start learning once the output weights move.
    A zero fitted baseline can be represented by a small positive seed supplied
    by the caller; softplus has no finite parameter giving an exact zero rate.
    """
    if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not math.isfinite(rate) or rate <= 0:
        raise ValueError("rate must be finite and strictly positive")
    # Numerically stable inverse softplus, including large positive rates.
    logit = rate + math.log(-math.expm1(-rate))
    if isinstance(model, LearnedNonnegativeKernel):
        if model.architecture == "constant":
            model.kernel_network.logits.fill_(logit)
            return
        output = model.kernel_network.spatial if model.architecture == "linear" else model.kernel_network.output
    elif isinstance(model, EnvironmentConditionedConvolution):
        output = model.kernel_network[-1]
    else:
        raise TypeError("initialize_kernel_rate requires a nonnegative kernel model")
    output.weight.zero_()
    output.bias.fill_(logit)


# Multiscale rate mixture
# -----------------------
# Combine learned kernels of several sizes before the exponential link.
#
# At a known unburned target ``i``, branch ``k`` generates nonnegative offset
# rates ``K[k,i,delta]`` and the current burned map supplies ``B[i+delta]``.
# The model computes ``r[k,i] = sum_delta K[k,i,delta] * B[i+delta]``, followed
# by ``lambda[i] = sum_k a[k] * r[k,i]`` and
# ``q[i] = 1 - exp(-dt_hours * lambda[i])``. The learned scalar coefficients
# ``a[k]`` are global. By default they are nonnegative with unrestricted sum;
# the explicit ``simplex`` option instead constrains their sum to one.
#
# This is a mixture of rates, not a weighted average of probabilities. Branch
# rates and mixture coefficients are not individually identifiable: scaling
# a branch rate and inversely scaling its coefficient leaves predictions
# unchanged. Coefficients must therefore not be read as causal importance.

MIXING_CONSTRAINTS = ("nonnegative", "simplex")


class MixedNonnegativeKernel(EnvironmentConditionedConvolution):
    """Independent environmental kernels combined as a nonnegative rate.

    Each branch reads its own centered environmental patch and acts on the
    burned sources within that patch. The inherited grid interface requires
    complete environmental context over the largest patch, fixes every
    branch's center offset to zero, and retains masks and boundary semantics.
    Cached center features retain the full largest patch because different
    branches can require different environmental means or spatial features.
    """

    def __init__(self, in_channels: int, kernel_sizes: Sequence[int] = (3, 5, 7, 9),
                 branch_architecture: str = "cnn", hidden_channels: int = 16,
                 depth: int = 2, dropout: float = 0.0,
                 mixing_constraint: str = "nonnegative"):
        if (not isinstance(kernel_sizes, (list, tuple)) or not kernel_sizes
                or any(not isinstance(size, int) or isinstance(size, bool)
                       or size < 3 or size % 2 != 1 for size in kernel_sizes)
                or list(kernel_sizes) != sorted(set(kernel_sizes))):
            raise ValueError("kernel_sizes must be distinct ascending odd integers >= 3")
        if branch_architecture not in KERNEL_ARCHITECTURES:
            raise ValueError(f"branch_architecture must be one of {KERNEL_ARCHITECTURES}")
        if mixing_constraint not in MIXING_CONSTRAINTS:
            raise ValueError(f"mixing_constraint must be one of {MIXING_CONSTRAINTS}")
        super().__init__(in_channels, max(kernel_sizes), hidden_channels)
        # The parent supplies the grid/mask contract. Only branch generators
        # participate in the mixed model; remove its unused single generator.
        del self.kernel_network
        self.kernel_sizes = tuple(kernel_sizes)
        self.branch_architecture = branch_architecture
        self.hidden_channels = hidden_channels
        self.mixing_constraint = mixing_constraint
        self.branches = nn.ModuleDict({
            str(size): build_kernel_model(
                in_channels, size, branch_architecture, hidden_channels, depth, dropout,
            ) for size in self.kernel_sizes
        })
        first = self.branches[str(self.kernel_sizes[0])]
        self.depth = max(1, first.depth)
        self.dropout = first.dropout
        # Unrestricted nonnegative coefficients initially equal one. Simplex
        # coefficients initially equal 1 / number_of_branches.
        initial_logit = math.log(math.expm1(1.0)) if mixing_constraint == "nonnegative" else 0.0
        self.mixing_logits = nn.Parameter(torch.full((len(self.kernel_sizes),), initial_logit))
        for size in self.kernel_sizes:
            radius = self.kernel_size // 2
            branch_radius = size // 2
            offsets = torch.arange(size) + radius - branch_radius
            indices = (offsets[:, None] * self.kernel_size + offsets[None, :]).flatten()
            self.register_buffer(f"_indices_{size}", indices, persistent=False)

    def mixing_weights(self) -> Tensor:
        """Return differentiable global coefficients in ``kernel_sizes`` order."""
        if not bool(torch.isfinite(self.mixing_logits).all()):
            raise RuntimeError("The mixing coefficients contain nonfinite logits")
        weights = (F.softplus(self.mixing_logits) if self.mixing_constraint == "nonnegative"
                   else F.softmax(self.mixing_logits, dim=0))
        if not bool(torch.isfinite(weights).all()):
            raise RuntimeError("The mixing coefficients produced nonfinite weights")
        return weights

    def _embed(self, branch_rates: Tensor, size: int) -> Tensor:
        """Embed row-major branch offsets centrally into largest-patch offsets."""
        shape = (*branch_rates.shape[:-3], self.kernel_size ** 2, *branch_rates.shape[-2:])
        return branch_rates.new_zeros(shape).index_copy(
            -3, getattr(self, f"_indices_{size}"), branch_rates,
        )

    def _combine(self, branch_rates: dict[int, Tensor]) -> Tensor:
        weights = self.mixing_weights()
        combined = sum(
            weights[index] * self._embed(branch_rates[size], size)
            for index, size in enumerate(self.kernel_sizes)
        )
        if not bool(torch.isfinite(combined).all()):
            raise RuntimeError("The mixed kernel produced nonfinite transition rates")
        return combined

    def _kernels(self, clean: Tensor) -> Tensor:
        return self._combine({size: self.branches[str(size)]._kernels(clean)
                              for size in self.kernel_sizes})

    def branch_kernel_rates(self, environmental_data: Tensor,
                            feature_valid: Tensor | None = None,
                            *, boundary: str = "unknown") -> dict[int, Tensor]:
        """Inspect unmixed hourly offset rates, keyed by branch kernel size.

        A branch has native ``[..., size*size, H, W]`` row-major offset shape.
        All branches use the same complete largest-patch availability mask as
        the combined prediction. No coefficient or exponential is applied.
        """
        clean, available = self._features(environmental_data, feature_valid, boundary)
        return {size: self.branches[str(size)]._kernels(clean).masked_fill(
            ~available.expand(*available.shape[:-3], size * size, *available.shape[-2:]),
            torch.nan,
        ) for size in self.kernel_sizes}

    def center_features(self, environment: Tensor) -> Tensor:
        """Validate and retain complete normalized ``N,C,maxK,maxK`` patches."""
        size = self.kernel_size
        if environment.ndim != 4 or tuple(environment.shape[1:]) != (self.in_channels, size, size):
            raise ValueError("Mixed center evaluation requires complete N,C,maxK,maxK patches")
        parameter = next(self.parameters())
        if environment.device != parameter.device or environment.dtype != parameter.dtype:
            raise ValueError("Center input data must match the model device and environmental dtype")
        if not bool(torch.isfinite(environment).all()):
            raise ValueError("Center environmental patches must be finite and completely known")
        return environment

    def branch_center_kernel_rates(self, environment: Tensor) -> dict[int, Tensor]:
        """Inspect unmixed branch offsets as ``N,size*size,1,1`` tensors."""
        features = self.center_features(environment)
        result = {}
        for size in self.kernel_sizes:
            margin = (self.kernel_size - size) // 2
            patch = features[..., margin:margin + size, margin:margin + size]
            branch = self.branches[str(size)]
            logits = branch.kernel_network.center_logits(patch)
            if not bool(torch.isfinite(logits).all()):
                raise RuntimeError("A mixed branch center generator produced nonfinite logits")
            result[size] = F.softplus(logits) * branch.off_center
        return result

    def _validate_burned_center(self, features: Tensor, burned: Tensor) -> None:
        size = self.kernel_size
        if burned.shape != (features.shape[0], 1, size, size):
            raise ValueError("Mixed center evaluation requires matching N,1,maxK,maxK burned patches")
        if burned.device != next(self.parameters()).device:
            raise ValueError("Center input data must match the model device and environmental dtype")
        if burned.is_complex() or not bool(torch.isfinite(burned).all()) or bool(((burned != 0) & (burned != 1)).any()):
            raise ValueError("Center burned patches must contain known binary states")

    def branch_center_convolution_rates(self, environment: Tensor, burned: Tensor) -> Tensor:
        """Return unmixed branch rates ``N,number_of_branches`` before the link."""
        features = self.center_features(environment)
        self._validate_burned_center(features, burned)
        branch_rates = self.branch_center_kernel_rates(features)
        rates = []
        for size in self.kernel_sizes:
            margin = (self.kernel_size - size) // 2
            sources = burned[..., margin:margin + size, margin:margin + size]
            rates.append((branch_rates[size].flatten(1) * sources.flatten(1)).sum(dim=1))
        result = torch.stack(rates, dim=1)
        if not bool(torch.isfinite(result).all()):
            raise RuntimeError("A mixed branch convolution produced nonfinite transition rates")
        return result

    def center_from_features(self, features: Tensor, burned: Tensor) -> Tensor:
        """Apply the pre-exponential mixture to complete cached center inputs."""
        branch_rates = self.branch_center_convolution_rates(features, burned)
        rate = (branch_rates * self.mixing_weights()).sum(dim=1)
        if not bool(torch.isfinite(rate).all()):
            raise RuntimeError("The mixed center convolution produced nonfinite transition rates")
        probability = -torch.expm1(-rate)
        size = self.kernel_size
        return torch.where(burned[:, 0, size // 2, size // 2] == 1, 0, probability)

    def center_probability(self, environment: Tensor, burned: Tensor) -> Tensor:
        """Return one-hour new-burn probabilities on complete largest patches."""
        return self.center_from_features(self.center_features(environment), burned)


def build_mixed_kernel_model(in_channels: int, kernel_sizes: Sequence[int] = (3, 5, 7, 9),
                             branch_architecture: str = "cnn", hidden_channels: int = 16,
                             depth: int = 2, dropout: float = 0.0,
                             mixing_constraint: str = "nonnegative") -> MixedNonnegativeKernel:
    """Construct an untrained mixed kernel without fitting any preprocessing."""
    return MixedNonnegativeKernel(
        in_channels, kernel_sizes, branch_architecture, hidden_channels, depth, dropout,
        mixing_constraint,
    )


def mixed_model_configuration(model: nn.Module) -> dict:
    """Return the exact reconstructible mixed checkpoint configuration fields."""
    if not isinstance(model, MixedNonnegativeKernel):
        raise TypeError("mixed_model_configuration requires a MixedNonnegativeKernel")
    return {
        "kernel_sizes": list(model.kernel_sizes), "branch_architecture": model.branch_architecture,
        "hidden_channels": model.hidden_channels, "depth": model.depth, "dropout": model.dropout,
        "mixing_constraint": model.mixing_constraint,
    }


mixed_kernel_model_configuration = mixed_model_configuration


@torch.no_grad()
def initialize_mixed_kernel_rate(model: MixedNonnegativeKernel, rate: float) -> None:
    """Initialize the *combined* effective noncenter kernel uniformly to rate.

    Overlapping offsets divide their target contribution equally among the
    branches covering that offset, accounting for their current coefficients.
    Thus adding branches does not multiply the initial total rate. Existing
    mixing logits and earlier neural layers are retained. Only final affine
    output weights/biases (or constant logits) are reset.
    """
    if not isinstance(model, MixedNonnegativeKernel):
        raise TypeError("initialize_mixed_kernel_rate requires a MixedNonnegativeKernel")
    if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not math.isfinite(rate) or rate <= 0:
        raise ValueError("rate must be finite and strictly positive")
    weights = model.mixing_weights()
    if bool((weights <= 0).any()):
        raise ValueError("Uniform mixed initialization requires strictly positive mixing coefficients")
    counts = weights.new_zeros(model.kernel_size ** 2)
    for size in model.kernel_sizes:
        counts.index_add_(0, getattr(model, f"_indices_{size}"), counts.new_ones(size * size))
    for index, size in enumerate(model.kernel_sizes):
        target = rate / (counts[getattr(model, f"_indices_{size}")] * weights[index])
        if not bool(torch.isfinite(target).all()) or bool((target <= 0).any()):
            raise ValueError("Uniform mixed initialization produced an invalid branch rate")
        logits = target + torch.log(-torch.expm1(-target))
        branch = model.branches[str(size)]
        if branch.architecture == "constant":
            branch.kernel_network.logits.copy_(logits.reshape(1, size * size, 1, 1))
        else:
            output = (branch.kernel_network.spatial if branch.architecture == "linear"
                      else branch.kernel_network.output)
            output.weight.zero_()
            output.bias.copy_(logits)


# Neural multiscale rate combiner
# -------------------------------
# A small neural network combines multiscale burned-state convolution rates.
#
# The independent branches first compute nonnegative raw rates ``r_k`` using
# their own environmental kernels and the current burned map. A two-affine
# SiLU network computes one positive gain, and the combined hourly rate is
# ``lambda = sum_k(r_k) * softplus(MLP(r))``. Thus ``lambda`` is nonnegative
# and is exactly zero when every branch rate is zero. One exponential then
# gives ``q = 1 - exp(-dt_hours * lambda)`` at an unburned target.
#
# The combiner reads rates, not branch probabilities or environmental patches.
# It learns a single rate rather than a vector of branch mixing coefficients.
# Unlike a linear rate mixture, its effective rate depends nonlinearly on the
# current burned-source pattern, so it has no burned-independent offset kernel.

class NeuralMixedNonnegativeKernel(MixedNonnegativeKernel):
    """Independent spatial kernels followed by a zero-preserving scalar MLP.

    The combiner has one hidden affine layer, SiLU, optional dropout, and one
    scalar affine output followed by softplus. Its gain can vary with the
    branch rates; nonnegativity alone does not impose monotonicity. All branch
    kernels still have nonnegative rates and zero center contributions.
    """

    def __init__(self, in_channels: int, kernel_sizes: Sequence[int] = (3, 5, 7, 9),
                 branch_architecture: str = "cnn", hidden_channels: int = 16,
                 depth: int = 2, dropout: float = 0.0,
                 combiner_hidden_channels: int = 8, combiner_dropout: float = 0.0,
                 combiner_input_transform: str = "identity"):
        if (not isinstance(combiner_hidden_channels, int)
                or isinstance(combiner_hidden_channels, bool) or combiner_hidden_channels <= 0):
            raise ValueError("combiner_hidden_channels must be a positive integer")
        if (isinstance(combiner_dropout, bool) or not isinstance(combiner_dropout, (int, float))
                or not math.isfinite(combiner_dropout) or not 0 <= combiner_dropout < 1):
            raise ValueError("combiner_dropout must be a finite probability in [0, 1)")
        if combiner_input_transform not in ("identity", "log1p"):
            raise ValueError("combiner_input_transform must be 'identity' or 'log1p'")
        super().__init__(in_channels, kernel_sizes, branch_architecture, hidden_channels,
                         depth, dropout, mixing_constraint="nonnegative")
        # The neural model has no linear mixing coefficients. Its only
        # combination parameters belong to the one-output neural network.
        del self.mixing_logits
        del self.mixing_constraint
        self.combiner_hidden_channels = combiner_hidden_channels
        self.combiner_dropout = float(combiner_dropout)
        self.combiner_input_transform = combiner_input_transform
        self.combiner = nn.Sequential(
            nn.Linear(len(self.kernel_sizes), combiner_hidden_channels), nn.SiLU(),
            nn.Dropout(self.combiner_dropout), nn.Linear(combiner_hidden_channels, 1),
        )
        self._initialize_unit_gain()

    @torch.no_grad()
    def _initialize_unit_gain(self) -> None:
        output = self.combiner[-1]
        output.weight.zero_()
        output.bias.fill_(math.log(math.expm1(1.0)))

    def mixing_weights(self):
        raise TypeError("A neural mixed model produces one scalar rate and has no linear mixing weights")

    def _kernels(self, clean):
        raise TypeError("A neural mixed model has no burned-independent combined offset kernel")

    def kernel_rates(self, environmental_data, feature_valid=None, *, boundary="unknown"):
        raise TypeError(
            "A neural mixed model's combined rate depends on burned inputs; "
            "inspect branch_kernel_rates or call forward for the combined rate"
        )

    def combined_rate(self, raw_rates: Tensor) -> Tensor:
        """Return a scalar hourly rate from last-axis branch rates ``[..., B]``.

        Inputs must be finite nonnegative floating data in the model dtype
        and device. This public method accepts center and grid layouts and
        remains differentiable in both the rates and combiner parameters.
        """
        if not isinstance(raw_rates, Tensor) or not raw_rates.is_floating_point():
            raise TypeError("Neural combiner inputs must be floating torch tensors")
        if raw_rates.ndim < 1 or raw_rates.shape[-1] != len(self.kernel_sizes):
            raise ValueError("Neural combiner inputs must have one last-axis rate per branch")
        parameter = next(self.parameters())
        if raw_rates.device != parameter.device or raw_rates.dtype != parameter.dtype:
            raise ValueError("Neural combiner inputs must match the model device and dtype")
        if not bool(torch.isfinite(raw_rates).all()) or bool((raw_rates < 0).any()):
            raise ValueError("Neural combiner inputs must be finite nonnegative rates")
        inputs = torch.log1p(raw_rates) if self.combiner_input_transform == "log1p" else raw_rates
        logits = self.combiner(inputs).squeeze(-1)
        if not bool(torch.isfinite(logits).all()):
            raise RuntimeError("The neural rate combiner produced nonfinite logits")
        rate = raw_rates.sum(dim=-1) * F.softplus(logits)
        if not bool(torch.isfinite(rate).all()):
            raise RuntimeError("The neural rate combiner produced a nonfinite transition rate")
        return rate

    def center_from_features(self, features: Tensor, burned: Tensor) -> Tensor:
        """Combine raw center branch convolutions and apply one exponential."""
        raw_rates = self.branch_center_convolution_rates(features, burned)
        rate = self.combined_rate(raw_rates)
        probability = -torch.expm1(-rate)
        size = self.kernel_size
        return torch.where(burned[:, 0, size // 2, size // 2] == 1, 0, probability)

    def _branch_grid_predictions(self, burned_area: Tensor, environmental_data: Tensor,
                                 *, burned_area_valid: Tensor | None = None,
                                 feature_valid: Tensor | None = None,
                                 boundary: str = "unknown") -> list[BurnProbability]:
        _check_grid(burned_area, "burned_area", 1)
        clean, available = self._features(environmental_data, feature_valid, boundary)
        if (burned_area.shape[:-3] != clean.shape[:-3]
                or burned_area.shape[-2:] != clean.shape[-2:]):
            raise ValueError("burned_area and environmental_data must be on the same grid")
        return [new_burn_probability(
            burned_area, self.branches[str(size)]._kernels(clean),
            burned_area_valid=burned_area_valid, kernel_valid=available, boundary=boundary,
        ) for size in self.kernel_sizes]

    def branch_convolution_rates(self, burned_area: Tensor, environmental_data: Tensor,
                                 *, burned_area_valid: Tensor | None = None,
                                 feature_valid: Tensor | None = None,
                                 boundary: str = "unknown") -> Tensor:
        """Inspect unmixed hourly convolution maps ``[..., B,H,W]``.

        Unavailable rates are NaN. Branch environmental masks require the
        largest patch; source dependencies retain each branch's own support.
        The combined forward call requires all branch rates to be available.
        """
        branches = self._branch_grid_predictions(
            burned_area, environmental_data, burned_area_valid=burned_area_valid,
            feature_valid=feature_valid, boundary=boundary,
        )
        return torch.cat([prediction.rate for prediction in branches], dim=-3)

    def forward(self, burned_area: Tensor, environmental_data: Tensor, *, dt_hours=1.0,
                burned_area_valid: Tensor | None = None, feature_valid: Tensor | None = None,
                boundary: str = "unknown") -> BurnProbability:
        """Return nonlinear combined rates and masked new-burn probabilities."""
        branches = self._branch_grid_predictions(
            burned_area, environmental_data, burned_area_valid=burned_area_valid,
            feature_valid=feature_valid, boundary=boundary,
        )
        rate_valid = torch.stack([prediction.rate_valid for prediction in branches], dim=0).all(dim=0)
        branch_rates = torch.cat([prediction.rate for prediction in branches], dim=-3)
        safe_rates = torch.where(rate_valid.expand_as(branch_rates), branch_rates, 0)
        raw_rate = self.combined_rate(safe_rates.movedim(-3, -1)).unsqueeze(-3)
        observed = _valid_mask(burned_area_valid, burned_area, "burned_area_valid") & torch.isfinite(burned_area)
        duration = _duration(dt_hours, tuple(burned_area.shape[:-3]), raw_rate)
        probability = -torch.expm1(-raw_rate * duration)
        already_burned = observed & (burned_area == 1)
        probability = torch.where(already_burned, 0, probability)
        valid = observed & (already_burned | (duration == 0) | rate_valid)
        return BurnProbability(
            probability.masked_fill(~valid, torch.nan), valid,
            raw_rate.masked_fill(~rate_valid, torch.nan), rate_valid,
        )


def build_neural_mixed_kernel_model(in_channels: int, kernel_sizes: Sequence[int] = (3, 5, 7, 9),
                                   branch_architecture: str = "cnn", hidden_channels: int = 16,
                                   depth: int = 2, dropout: float = 0.0,
                                   combiner_hidden_channels: int = 8, combiner_dropout: float = 0.0,
                                   combiner_input_transform: str = "identity") -> NeuralMixedNonnegativeKernel:
    """Construct an untrained model with an initially unit-gain combiner."""
    return NeuralMixedNonnegativeKernel(
        in_channels, kernel_sizes, branch_architecture, hidden_channels, depth, dropout,
        combiner_hidden_channels, combiner_dropout, combiner_input_transform,
    )


def neural_mixed_model_configuration(model: nn.Module) -> dict:
    """Return exact reconstructible branch and neural-combiner configuration."""
    if not isinstance(model, NeuralMixedNonnegativeKernel):
        raise TypeError("neural_mixed_model_configuration requires a NeuralMixedNonnegativeKernel")
    return {
        "kernel_sizes": list(model.kernel_sizes), "branch_architecture": model.branch_architecture,
        "hidden_channels": model.hidden_channels, "depth": model.depth, "dropout": model.dropout,
        "combiner_hidden_channels": model.combiner_hidden_channels,
        "combiner_dropout": model.combiner_dropout,
        "combiner_input_transform": model.combiner_input_transform,
    }


@torch.no_grad()
def initialize_neural_mixed_kernel_rate(model: NeuralMixedNonnegativeKernel, rate: float) -> None:
    """Initialize the combined rate to the uniform largest-support baseline.

    Each offset's baseline contribution is divided across branches containing
    that offset. The neural output is reset to a unit gain; earlier branch and
    combiner layers retain their sampled initialization. Therefore the initial
    combined convolution equals ``rate * number_of_burned_neighbors`` rather
    than counting overlapping source offsets several times.
    """
    if not isinstance(model, NeuralMixedNonnegativeKernel):
        raise TypeError("initialize_neural_mixed_kernel_rate requires a NeuralMixedNonnegativeKernel")
    if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not math.isfinite(rate) or rate <= 0:
        raise ValueError("rate must be finite and strictly positive")
    parameter = next(model.parameters())
    counts = parameter.new_zeros(model.kernel_size ** 2)
    for size in model.kernel_sizes:
        counts.index_add_(0, getattr(model, f"_indices_{size}"), counts.new_ones(size * size))
    for size in model.kernel_sizes:
        target = rate / counts[getattr(model, f"_indices_{size}")]
        logits = target + torch.log(-torch.expm1(-target))
        if not bool(torch.isfinite(logits).all()):
            raise ValueError("Uniform neural mixed initialization produced invalid branch logits")
        branch = model.branches[str(size)]
        if branch.architecture == "constant":
            branch.kernel_network.logits.copy_(logits.reshape(1, size * size, 1, 1))
        else:
            output = (branch.kernel_network.spatial if branch.architecture == "linear"
                      else branch.kernel_network.output)
            output.weight.zero_()
            output.bias.copy_(logits)
    model._initialize_unit_gain()


# Patch random forest
# -------------------
# Patch random forest adapted from the Huot et al. pixelwise baseline.
#
# The source baseline uses flattened 3 x 3 environmental and current-fire
# neighborhoods. Here, the target is the existing project's next-hour new-burn
# label for a previously unburned center, rather than the paper's next-day
# active-fire mask. A 5 x 5 model additionally permits a matched-neighborhood
# comparison. This module does not reproduce the paper's dataset or scores.
#
# Source: https://arxiv.org/abs/2112.02447
# The optional ``scikit-learn`` dependency is imported only when fitting,
# loading, or querying a fitted estimator. No target label enters the features.

_FORMAT_VERSION = 1
_ARCHITECTURE = "PatchRandomForest"


def _dependencies():
    try:
        import joblib
        import sklearn
        from sklearn.ensemble import RandomForestClassifier
    except ImportError as error:
        raise ImportError(
            "PatchRandomForest requires the optional scikit-learn baseline dependency"
        ) from error
    return joblib, sklearn, RandomForestClassifier


def _channel_names(channel_names: Sequence[str]) -> tuple[str, ...]:
    if isinstance(channel_names, (str, bytes)):
        raise ValueError("channel_names must be an ordered sequence of channel names")
    try:
        names = tuple(channel_names)
    except TypeError as error:
        raise ValueError("channel_names must be an ordered sequence of channel names") from error
    if (not names or any(not isinstance(name, str) or not name.strip() for name in names)
            or len(set(names)) != len(names)):
        raise ValueError("channel_names must contain unique nonempty strings")
    return names


def _array(value: Any, name: str) -> np.ndarray:
    """Accept NumPy-compatible real data, including CPU tensors without gradients."""
    try:
        array = np.asarray(value)
    except (TypeError, ValueError, RuntimeError) as error:
        raise ValueError(f"{name} must be NumPy-compatible real numeric data") from error
    if array.dtype.kind not in "biuf":
        raise ValueError(f"{name} must be real numeric data")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain complete finite data")
    return array


class PatchRandomForest:
    """Weighted binary classification using a centered 3 x 3 or 5 x 5 patch.

    ``environment`` is ``N x C x P x P`` and ``burned`` is ``N x 1 x P x P``.
    ``P`` must be odd and at least ``kernel_size``. Both inputs are centered
    cropped before flattening. Features are all environmental values, ordered
    by channel and then by row and column, followed by binary burned values
    ordered by row and column. The center must be unburned. A patch may contain
    no burned neighbors; cohort eligibility is the caller's responsibility.

    Channels must be provided in the fitted order on every prediction and
    refit. Values must already use the caller's fixed training preprocessing;
    this estimator learns no normalization and performs no calibration,
    class balancing, or temporal extrapolation. The probability is sklearn's
    mean tree probability for class 1 at the fixed one-hour endpoint.
    """

    def __init__(self, kernel_size: int = 3, n_estimators: int = 100,
                 max_depth: int | None = 15, random_state: int = 7,
                 n_jobs: int = 4):
        if type(kernel_size) is not int or kernel_size not in (3, 5):
            raise ValueError("kernel_size must be 3 or 5")
        if type(n_estimators) is not int or n_estimators <= 0:
            raise ValueError("n_estimators must be a positive integer")
        if max_depth is not None and (type(max_depth) is not int or max_depth <= 0):
            raise ValueError("max_depth must be a positive integer or None")
        if type(random_state) is not int or not 0 <= random_state < 2**32:
            raise ValueError("random_state must be an integer in [0, 2**32)")
        if type(n_jobs) is not int or n_jobs == 0:
            raise ValueError("n_jobs must be a nonzero integer")
        self.kernel_size = kernel_size
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.random_state = random_state
        self.n_jobs = n_jobs
        self._channels: tuple[str, ...] | None = None
        self._estimator: Any = None
        self._sklearn_version: str | None = None
        self._metadata: dict[str, Any] = {}

    @property
    def channel_names(self) -> tuple[str, ...]:
        """Fitted channel order; querying an unfitted model raises an error."""
        self._require_fitted()
        return self._channels

    @property
    def estimator(self):
        """The fitted sklearn estimator, for inspection of its tree parameters."""
        self._require_fitted()
        return self._estimator

    @property
    def metadata(self) -> dict[str, Any]:
        """Copy of caller-supplied metadata from the loaded checkpoint."""
        return deepcopy(self._metadata)

    @property
    def contract(self) -> Mapping[str, Any]:
        """A fresh mapping specifying every input column and the fixed endpoint."""
        self._require_fitted()
        radius = self.kernel_size // 2
        offsets = [(row, col) for row in range(-radius, radius + 1)
                   for col in range(-radius, radius + 1)]
        feature_order = [
            f"environment:{name}[row={row},col={col}]"
            for name in self._channels for row, col in offsets
        ]
        feature_order.extend(f"burned[row={row},col={col}]" for row, col in offsets)
        return {
            "format_version": _FORMAT_VERSION,
            "architecture": _ARCHITECTURE,
            "kernel_size": self.kernel_size,
            "in_channels": len(self._channels),
            "channels": list(self._channels),
            "source_features": {
                "environment": list(self._channels),
                "burned": "current_binary_burned_area",
            },
            "feature_layout": "environment_channel_row_column_then_burned_row_column",
            "feature_order": feature_order,
            "n_features": len(feature_order),
            "dt_hours": 1.0,
            "target": "next_hour_new_burn_at_previously_unburned_center",
            "center_burned": 0,
            "burned_neighborhood_may_be_empty": True,
            "output": "mean_tree_probability_for_class_1",
            "calibration": "none",
            "class_rebalancing": "none",
            "sample_weight": "positive_input_weights_divided_by_their_mean",
            "hyperparameters": self._forest_parameters(),
            "sklearn_version": self._sklearn_version,
            "reference": "https://arxiv.org/abs/2112.02447",
        }

    def _config(self) -> dict[str, Any]:
        return {
            "kernel_size": self.kernel_size,
            "n_estimators": self.n_estimators,
            "max_depth": self.max_depth,
            "random_state": self.random_state,
            "n_jobs": self.n_jobs,
        }

    def _forest_parameters(self) -> dict[str, Any]:
        return {
            "n_estimators": self.n_estimators,
            "max_depth": self.max_depth,
            "random_state": self.random_state,
            "n_jobs": self.n_jobs,
            "criterion": "gini",
            "bootstrap": True,
            "max_features": "sqrt",
            "min_samples_leaf": 1,
            "class_weight": None,
        }

    def _require_fitted(self) -> None:
        if self._estimator is None or self._channels is None:
            raise RuntimeError("PatchRandomForest must be fitted before prediction or saving")

    def _features(self, environment: Any, burned: Any, *,
                  channel_names: Sequence[str]) -> tuple[np.ndarray, tuple[str, ...]]:
        names = _channel_names(channel_names)
        if self._channels is not None and names != self._channels:
            raise ValueError("channel names/order must exactly match the fitted model")
        environmental = _array(environment, "environment")
        burned_array = _array(burned, "burned")
        if environmental.ndim != 4:
            raise ValueError("environment must have shape N x C x P x P")
        n, c, height, width = environmental.shape
        if c != len(names):
            raise ValueError("environment channel count must match channel_names")
        if height != width or height % 2 != 1 or height < self.kernel_size:
            raise ValueError("environment patches must be square, odd, and at least kernel_size")
        if burned_array.shape != (n, 1, height, width):
            raise ValueError("burned must have shape N x 1 x P x P matching environment")
        if ((burned_array != 0) & (burned_array != 1)).any():
            raise ValueError("burned must contain binary values, exactly 0 or 1")
        if (burned_array[:, 0, height // 2, width // 2] != 0).any():
            raise ValueError("burned center must be unburned (0)")
        start = (height - self.kernel_size) // 2
        stop = start + self.kernel_size
        environment_crop = environmental[:, :, start:stop, start:stop]
        burned_crop = burned_array[:, :, start:stop, start:stop]
        feature_count = (c + 1) * self.kernel_size**2
        features = np.concatenate((
            environment_crop.reshape(n, c * self.kernel_size**2),
            burned_crop.reshape(n, self.kernel_size**2),
        ), axis=1)
        # sklearn converts to float32 internally; reject otherwise finite values
        # that become infinite there, rather than changing their magnitude.
        with np.errstate(over="ignore", invalid="ignore"):
            features = np.asarray(features, dtype=np.float32)
        if features.shape != (n, feature_count) or not np.isfinite(features).all():
            raise ValueError("features must remain finite when converted to float32")
        return features, names

    def fit(self, environment: Any, burned: Any, target: Any, weight: Any, *,
            channel_names: Sequence[str]) -> PatchRandomForest:
        """Fit binary labels with positive weights, preserving relative weights.

        ``target`` and ``weight`` each have shape ``(N,)``. Weight scaling by
        the mean avoids large absolute tree weights and leaves the relative
        contribution of every row unchanged. Refitting accepts only the same
        ordered channels. Fit failures leave any previous fitted model intact.
        """
        features, names = self._features(environment, burned, channel_names=channel_names)
        n = len(features)
        if n == 0:
            raise ValueError("fit requires at least one training row")
        labels = _array(target, "target")
        weights = _array(weight, "weight")
        if labels.shape != (n,) or weights.shape != (n,):
            raise ValueError("target and weight must each have shape (N,)")
        if ((labels != 0) & (labels != 1)).any():
            raise ValueError("target must contain binary values, exactly 0 or 1")
        if (weights <= 0).any():
            raise ValueError("weight must contain strictly positive values")
        weights = weights.astype(np.float64, copy=False)
        # Scaling first prevents overflow in a sum of large finite weights.
        normalized_weight = weights / weights.max()
        normalized_weight /= normalized_weight.mean()
        if not np.isfinite(normalized_weight).all() or (normalized_weight <= 0).any():
            raise ValueError("weight dynamic range cannot be represented after normalization")
        _, sklearn, classifier = _dependencies()
        fitted = classifier(**self._forest_parameters())
        fitted.fit(features, labels.astype(np.uint8), sample_weight=normalized_weight)
        self._estimator = fitted
        self._channels = names
        self._sklearn_version = sklearn.__version__
        self._metadata = {}
        return self

    def predict_probability(self, environment: Any, burned: Any, *,
                            channel_names: Sequence[str],
                            dt_hours: float = 1.0) -> np.ndarray:
        """Return a float64 vector of one-hour probabilities for unburned centers."""
        self._require_fitted()
        if not isinstance(dt_hours, Real) or isinstance(dt_hours, (bool, np.bool_)):
            raise TypeError("dt_hours must be a real numeric scalar")
        if not np.isfinite(dt_hours) or dt_hours != 1.0:
            raise ValueError("PatchRandomForest is fitted only for dt_hours=1.0")
        features, _ = self._features(environment, burned, channel_names=channel_names)
        if len(features) == 0:
            return np.empty(0, dtype=np.float64)
        classes = np.asarray(self._estimator.classes_)
        positive_column = np.flatnonzero(classes == 1)
        if len(positive_column) == 0:
            return np.zeros(len(features), dtype=np.float64)
        probabilities = self._estimator.predict_proba(features)[:, positive_column[0]]
        return np.asarray(probabilities, dtype=np.float64)

    def save(self, path: str | Path, *, metadata: dict[str, Any] | None = None) -> Path:
        """Save a fitted model without overwriting any existing file.

        Joblib is a pickle-based format. Save and load checkpoints only in
        trusted local workflows: loading an untrusted checkpoint can execute
        arbitrary code. The file preserves the estimator, ordered input
        columns, fixed horizon, feature layout, and caller metadata.
        """
        self._require_fitted()
        if metadata is not None and not isinstance(metadata, dict):
            raise TypeError("metadata must be a dict or None")
        joblib, _, _ = _dependencies()
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "format_version": _FORMAT_VERSION,
            "config": self._config(),
            "contract": dict(self.contract),
            "estimator": self._estimator,
            "metadata": deepcopy(self._metadata if metadata is None else metadata),
        }
        # Exclusive creation also protects against an overwrite race.
        with destination.open("xb") as stream:
            try:
                joblib.dump(payload, stream, compress=3)
            except BaseException:
                destination.unlink(missing_ok=True)
                raise
        return destination

    @classmethod
    def load(cls, path: str | Path) -> PatchRandomForest:
        """Load and validate a trusted local joblib checkpoint.

        Validation occurs after unpickling and cannot make an untrusted file
        safe. Use only files produced by a trusted local process. A version
        mismatch is rejected because sklearn does not support loading across
        sklearn versions.
        """
        joblib, sklearn, classifier = _dependencies()
        payload = joblib.load(resolve_recorded_path(path))
        if not isinstance(payload, dict) or payload.get("format_version") != _FORMAT_VERSION:
            raise ValueError("incompatible random forest checkpoint format")
        try:
            model = cls(**payload["config"])
            contract = payload["contract"]
            fitted = payload["estimator"]
            if not isinstance(contract, dict) or not isinstance(fitted, classifier):
                raise ValueError("checkpoint must contain a random forest contract and estimator")
            model._channels = _channel_names(contract["channels"])
            model._sklearn_version = contract["sklearn_version"]
            model._estimator = fitted
            metadata = payload["metadata"]
            if not isinstance(metadata, dict):
                raise ValueError("checkpoint metadata must be a dict")
            model._metadata = deepcopy(metadata)
            if model._sklearn_version != sklearn.__version__:
                raise ValueError("checkpoint sklearn version differs from the installed version")
            if contract != dict(model.contract):
                raise ValueError("checkpoint contract does not match its saved configuration")
            if not hasattr(fitted, "estimators_") or len(fitted.estimators_) != model.n_estimators:
                raise ValueError("checkpoint estimator is not fitted as specified")
            if fitted.n_features_in_ != contract["n_features"]:
                raise ValueError("checkpoint estimator feature count differs from the contract")
            if not np.isin(fitted.classes_, [0, 1]).all() or len(fitted.classes_) not in (1, 2):
                raise ValueError("checkpoint estimator classes must be binary")
            if any(fitted.get_params()[key] != value
                   for key, value in model._forest_parameters().items()):
                raise ValueError("checkpoint estimator parameters differ from the contract")
        except (KeyError, TypeError, AttributeError) as error:
            raise ValueError("incomplete or incompatible random forest checkpoint") from error
        return model


# Fitted model wrappers
# ---------------------
# Saved preprocessing, channel order, and availability masks are part of the
# fitted model. Checkpoint validation and loading remain in inference.py.


class NormalizedBurnModel(nn.Module):
    """Common checkpoint state; subclasses retain their distinct output links."""

    def __init__(self, model, mean, std, contract, best_epoch):
        super().__init__()
        self.model = model
        self.register_buffer("mean", mean.reshape(-1, 1, 1))
        self.register_buffer("std", std.reshape(-1, 1, 1))
        self.channel_names = tuple(contract["channels"])
        self.contract = contract
        self.source_channels = tuple(contract.get("source_channels", self.channel_names))
        self.categorical_classes = contract.get("categorical_classes", {})
        self.one_hot_groups = one_hot_groups(contract)
        self.best_epoch = best_epoch
        stencil = torch.ones(1, 1, model.kernel_size, model.kernel_size)
        stencil[:, :, model.kernel_size // 2, model.kernel_size // 2] = 0
        self.register_buffer("neighbor_stencil", stencil)

    def _validate_one_hot(self, environmental_data, feature_valid):
        for source, indices in self.one_hot_groups.items():
            values = environmental_data[..., list(indices), :, :]
            known = torch.isfinite(values).all(dim=-3)
            if feature_valid is not None:
                known = known & feature_valid[..., list(indices), :, :].all(dim=-3)
            binary = ((values == 0) | (values == 1)).all(dim=-3)
            if not bool((~known | (binary & (values.sum(dim=-3) == 1))).all()):
                raise ValueError(f"Invalid known one-hot input group: {source}")

    def _contact(self, burned_area, burned_area_valid, *, boundary="unknown"):
        """Return burned contact, known targets, and complete source context.

        No observed burned neighbor establishes a structural zero only when
        the entire source neighborhood is known. Unknown interior states are
        never made known by the explicit outside-grid zero boundary assumption.
        """
        known = torch.isfinite(burned_area)
        if burned_area_valid is not None:
            known = known & burned_area_valid
        sources = torch.where(known, burned_area, 0).to(dtype=self.mean.dtype)
        h, w = sources.shape[-2:]
        contact = F.conv2d(
            sources.reshape(-1, 1, h, w), self.neighbor_stencil,
            padding=self.model.kernel_size // 2,
        ).reshape_as(burned_area) > 0
        radius = self.model.kernel_size // 2
        padded_known = F.pad(
            known.to(dtype=self.mean.dtype).reshape(-1, 1, h, w),
            (radius,) * 4, value=float(boundary == "zero"),
        )
        complete_sources = (
            F.avg_pool2d(padded_known, self.model.kernel_size, stride=1) == 1
        ).reshape_as(burned_area)
        return contact, known, complete_sources


class TrainedBurnModel(NormalizedBurnModel):
    """Fitted probability model accepting raw, ordered environmental channels."""

    def forward(self, burned_area, environmental_data, *, channel_names,
                burned_area_valid=None, feature_valid=None, dt_hours=1.0, boundary="unknown"):
        if tuple(channel_names) != self.channel_names:
            raise ValueError("Prediction channel names/order differ from the trained checkpoint")
        self._validate_one_hot(environmental_data, feature_valid)
        prediction = self.model(
            burned_area, (environmental_data - self.mean) / self.std,
            burned_area_valid=burned_area_valid, feature_valid=feature_valid,
            dt_hours=dt_hours, boundary=boundary,
        )
        if self.contract.get("eligibility") != "at_least_one_burned_neighbor":
            return prediction
        contact, known, complete_sources = self._contact(
            burned_area, burned_area_valid, boundary=boundary,
        )
        structural_zero = known & (burned_area == 0) & complete_sources & ~contact
        valid = prediction.valid & (contact | (known & (burned_area == 1)) | structural_zero)
        rate_valid = prediction.rate_valid & (contact | structural_zero)
        return BurnProbability(
            prediction.probability.masked_fill(~valid, torch.nan), valid,
            prediction.rate.masked_fill(~rate_valid, torch.nan), rate_valid,
        )


def bayesian_model_weights(
    probabilities,
    target,
    prior_weights=None,
    sample_weight=None,
    likelihood_power: Real = 1.0,
) -> dict[str, Any]:
    """Update model probabilities with an exact held-out Bernoulli likelihood.

    ``probabilities[n, j]`` is the frozen prediction of component ``j`` for
    calibration observation ``n``; ``target[n]`` is its binary outcome. With
    default arguments, posterior model mass is proportional to
    ``prior[j] * product_n p[n,j]**y[n] * (1-p[n,j])**(1-y[n])``. This is
    conditional, plug-in Bayesian model averaging: component parameters are
    already fitted, rather than integrated over a parameter posterior. The
    product additionally assumes conditional independence of observations.

    Optional strictly positive sampling weights are normalized to mean one.
    They raise each observation's likelihood to its normalized weight; a
    positive ``likelihood_power`` raises the entire likelihood to that power.
    Either option defines a generalized Bayesian update, rather than the
    ordinary unweighted likelihood. No probability clipping is performed:
    an impossible observed outcome gives that component zero evidence.

    The result contains only JSON primitives. ``None`` in a log-valued list
    represents negative infinity (exactly zero evidence or mass). Posterior
    logs retain finite support even when exponentiation underflows to zero.
    ``effective_sample_count`` is the Kish count of normalized sampling
    weights, while ``likelihood_exponent_total`` is their sum times the power.
    """
    def array(value, name):
        if isinstance(value, Tensor):
            value = value.detach().cpu().numpy()
        result = np.asarray(value)
        if result.dtype.kind not in "biuf":
            raise TypeError(f"{name} must contain real numeric values")
        return result.astype(np.float64, copy=False)

    values = array(probabilities, "probabilities")
    labels = array(target, "target")
    if values.ndim != 2 or any(size == 0 for size in values.shape):
        raise ValueError("probabilities must have nonempty shape [N, J]")
    n, j = values.shape
    if labels.shape != (n,) or not np.isin(labels, (0, 1)).all():
        raise ValueError("target must have shape [N] with exactly binary outcomes")
    if not np.isfinite(values).all() or ((values < 0) | (values > 1)).any():
        raise ValueError("probabilities must be finite and lie in [0, 1]")
    if (not isinstance(likelihood_power, Real) or isinstance(likelihood_power, bool)
            or not math.isfinite(likelihood_power) or likelihood_power <= 0):
        raise ValueError("likelihood_power must be finite and strictly positive")
    power = float(likelihood_power)
    if not math.isfinite(power * n):
        raise ValueError("likelihood_power times the calibration sample count must be representable as a finite number")
    priors = np.ones(j, dtype=np.float64) if prior_weights is None else array(
        prior_weights, "prior_weights",
    )
    if (priors.shape != (j,) or not np.isfinite(priors).all()
            or (priors < 0).any() or not (priors > 0).any()):
        raise ValueError("prior_weights must have shape [J], be finite and nonnegative, and have positive mass")

    def logsumexp(value):
        maximum = float(np.max(value))
        return maximum + math.log(float(np.exp(value - maximum).sum()))

    log_prior = np.full(j, -np.inf, dtype=np.float64)
    positive_prior = priors > 0
    log_prior[positive_prior] = np.log(priors[positive_prior])
    log_prior -= logsumexp(log_prior)
    weights = np.ones(n, dtype=np.float64)
    if sample_weight is not None:
        supplied = array(sample_weight, "sample_weight")
        if (supplied.shape != (n,) or not np.isfinite(supplied).all()
                or not (supplied > 0).all()):
            raise ValueError("sample_weight must have shape [N] and be finite and strictly positive")
        # Scaling before summing prevents overflow for large positive weights.
        weights = supplied / supplied.max()
        weights /= weights.mean()
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        terms = np.where(labels[:, None] == 1, np.log(values), np.log1p(-values))
        impossible = np.isneginf(terms).any(axis=0)
        # A strictly positive mathematical sampling weight cannot rescue an
        # impossible outcome, even if its normalized float underflows to zero.
        safe_terms = np.where(np.isfinite(terms), terms, 0)
        # Contiguous last-axis reduction uses NumPy's pairwise summation,
        # avoiding linear accumulation error on long calibration cohorts.
        log_likelihood = np.ascontiguousarray((weights[:, None] * safe_terms).T).sum(axis=1)
        log_likelihood[impossible] = -np.inf
    possible = positive_prior & np.isfinite(log_likelihood)
    if not possible.any():
        raise ValueError("All components with positive prior mass assign zero likelihood to the calibration outcomes")
    # Subtract a shared likelihood constant before tempering. This preserves
    # the posterior while avoiding overflow of large finite likelihood powers.
    reference = float(log_likelihood[possible].max())
    scores = np.full(j, -np.inf, dtype=np.float64)
    with np.errstate(over="ignore"):
        scores[possible] = log_prior[possible] + power * (log_likelihood[possible] - reference)
    if not np.isfinite(scores[possible]).all():
        raise ValueError("The powered log likelihood exceeds the finite precision available for posterior model mass")
    log_posterior = scores - logsumexp(scores)

    def log_list(value):
        return [None if np.isneginf(item) else float(item) for item in value]

    normalized_prior = priors / priors.max()
    normalized_prior /= normalized_prior.sum()
    return {
        "prior_weights": normalized_prior.tolist(),
        "log_prior_weights": log_list(log_prior),
        "log_likelihood": log_list(log_likelihood),
        "log_posterior_weights": log_list(log_posterior),
        "posterior_weights": np.exp(log_posterior).tolist(),
        "sample_count": int(n),
        "effective_sample_count": float(weights.sum() ** 2 / np.square(weights).sum()),
        "likelihood_exponent_total": float(power * weights.sum()),
        "sample_weight_normalization": "none" if sample_weight is None else "mean_one",
        "likelihood_power": power,
        "evidence_mode": (
            "ordinary_conditional_plug_in_bayes" if sample_weight is None and power == 1.0
            else "generalized_conditional_plug_in_bayes"
        ),
    }


class BayesianBurnModel(nn.Module):
    """Average independently fitted probabilities with frozen posterior mass.

    Each single-kernel component retains its own fitted normalization. For
    horizon ``t``, the output probability is ``sum_j pi[j] * p[j](t)``. The
    returned rate is the effective *interval* rate
    ``-log(sum_j pi[j] * exp(-lambda[j] * t)) / t``; its limit at ``t=0`` is
    ``sum_j pi[j] * lambda[j]``. This rate generally changes with the horizon,
    so it must not be reused as a constant rate for another interval.

    Availability is the intersection over every component with finite log
    posterior mass, including components whose mass underflows on conversion
    to floating-point probabilities. A component with log mass ``-inf`` is
    excluded. Missing data never cause local posterior renormalization.
    Known burned targets and known zero-duration events have probability zero.
    """

    _ENDPOINT_KEYS = ("eligibility", "dt_hours", "center_rate")
    _SHARED_KEYS = ("channels", "in_channels", *SCHEMA_KEYS, *_ENDPOINT_KEYS)

    def __init__(self, components, log_posterior_weights, contract):
        super().__init__()
        members = list(components)
        if len(members) < 2 or any(not isinstance(member, TrainedBurnModel) for member in members):
            raise ValueError("BayesianBurnModel requires at least two independently trained single-kernel components")
        if not isinstance(contract, Mapping):
            raise TypeError("The Bayesian model contract must be a mapping")
        baseline = members[0].contract
        sizes = []
        reference = members[0].mean
        for member in members:
            saved = member.contract
            if (saved.get("architecture") not in ("EnvironmentConditionedConvolution", "LearnedNonnegativeKernel")
                    or saved.get("dt_hours") != 1.0 or saved.get("center_rate") != 0.0):
                raise ValueError("Bayesian components must be supported single-kernel hourly probability models")
            size = saved.get("kernel_size")
            if (not isinstance(size, int) or isinstance(size, bool) or size < 3 or size % 2 != 1
                    or size != member.model.kernel_size):
                raise ValueError("A Bayesian component kernel_size must match its odd single kernel")
            sizes.append(size)
            if (any(saved.get(key) != baseline.get(key) for key in (*self._SHARED_KEYS, "output_link"))
                    or probability_target_id(saved) != probability_target_id(baseline)):
                raise ValueError("Bayesian components must share their ordered channel schema and probability endpoint")
            groups = one_hot_groups(saved)
            if (tuple(saved["channels"]) != member.channel_names or groups != member.one_hot_groups
                    or len(member.channel_names) != saved.get("in_channels")
                    or not member.channel_names or len(set(member.channel_names)) != len(member.channel_names)
                    or any(not isinstance(name, str) or not name for name in member.channel_names)):
                raise ValueError("Invalid Bayesian component channel schema")
            if (not reference.is_floating_point() or member.mean.shape != (len(member.channel_names), 1, 1)
                    or member.std.shape != member.mean.shape or not torch.isfinite(member.mean).all()
                    or not torch.isfinite(member.std).all() or not (member.std > 0).all()):
                raise ValueError("Bayesian components require finite saved normalization with positive scales")
            for tensor in (*member.parameters(), *member.buffers()):
                if (tensor.device != reference.device
                        or (tensor.is_floating_point() and tensor.dtype != reference.dtype)):
                    raise ValueError("All Bayesian component parameters and preprocessing must share one device and dtype")
        if len(set(sizes)) < 2:
            raise ValueError("Bayesian components must include at least two distinct kernel sizes")
        if (contract.get("architecture") != "BayesianModelAverage"
                or ("format_version" in contract and contract["format_version"] != 1)
                or contract.get("kernel_size") != max(sizes)
                or probability_target_id(contract) != probability_target_id(baseline)
                or any(contract.get(key) != baseline.get(key) for key in self._SHARED_KEYS)):
            raise ValueError("The Bayesian contract must match its components and largest kernel size")
        if "kernel_sizes" in contract:
            declared_sizes = contract["kernel_sizes"]
            if not isinstance(declared_sizes, (list, tuple)) or list(declared_sizes) != sizes:
                raise ValueError("The Bayesian contract kernel_sizes must preserve component order")
        original_logs = torch.as_tensor(log_posterior_weights, device="cpu", dtype=torch.float64)
        if (original_logs.shape != (len(members),) or bool(torch.isnan(original_logs).any())
                or bool(torch.isposinf(original_logs).any()) or not bool(torch.isfinite(original_logs).any())):
            raise ValueError("log_posterior_weights must have shape [J] with finite or negative-infinite normalized log mass")
        logs = original_logs.to(device=reference.device, dtype=reference.dtype)
        if not torch.equal(torch.isfinite(original_logs), torch.isfinite(logs).cpu()):
            raise ValueError("Finite posterior log mass must be representable in the component dtype")
        log_total = torch.logsumexp(logs, dim=0)
        tolerance = max(1e-12, 100 * torch.finfo(reference.dtype).eps)
        if not bool(torch.abs(log_total) <= tolerance):
            raise ValueError("log_posterior_weights must be normalized to total posterior mass one")
        self.register_buffer("log_posterior_weights", (logs - log_total).detach().clone())
        self.components = nn.ModuleList(members)
        self.contract = deepcopy(dict(contract))
        self.channel_names = tuple(baseline["channels"])
        self.source_channels = tuple(baseline.get("source_channels", self.channel_names))
        self.categorical_classes = deepcopy(baseline.get("categorical_classes", {}))
        self.one_hot_groups = one_hot_groups(self.contract)
        self.kernel_size = max(sizes)
        self.best_epoch = 0
        for parameter in self.parameters():
            parameter.requires_grad_(False)
        self.train(False)

    @property
    def posterior_weights(self):
        """Posterior mass; use finite log mass to determine supported models."""
        return self.log_posterior_weights.exp()

    def train(self, mode: bool = True):
        """Keep every fitted component in evaluation mode, including dropout."""
        if not isinstance(mode, bool):
            raise ValueError("training mode is expected to be boolean")
        return super().train(False)

    def forward(self, burned_area, environmental_data, *, channel_names,
                burned_area_valid=None, feature_valid=None, dt_hours=1.0, boundary="unknown"):
        if tuple(channel_names) != self.channel_names:
            raise ValueError("Prediction channel names/order differ from the Bayesian checkpoint")
        active = torch.isfinite(self.log_posterior_weights)
        predictions = [
            component(
                burned_area, environmental_data, channel_names=channel_names,
                burned_area_valid=burned_area_valid, feature_valid=feature_valid,
                dt_hours=dt_hours, boundary=boundary,
            )
            for component, supported in zip(self.components, active)
            if bool(supported)
        ]
        probabilities = torch.stack([result.probability for result in predictions])
        rates = torch.stack([result.rate for result in predictions])
        probability_valid = torch.stack([result.valid for result in predictions]).all(dim=0)
        rate_valid = torch.stack([result.rate_valid for result in predictions]).all(dim=0)
        logs = self.log_posterior_weights[active].reshape((-1,) + (1,) * (probabilities.ndim - 1))
        weights = logs.exp()
        safe_probability = torch.where(torch.isfinite(probabilities), probabilities, 0)
        probability = (weights * safe_probability).sum(dim=0).clamp(0, 1)
        safe_rate = torch.where(torch.isfinite(rates), rates, 0)
        duration = _duration(dt_hours, tuple(burned_area.shape[:-3]), environmental_data)
        attenuation = safe_rate * duration
        minimum_rate = safe_rate.min(dim=0).values
        shifted_attenuation = (safe_rate - minimum_rate) * duration
        log_shifted_survival = torch.logsumexp(logs - shifted_attenuation, dim=0).clamp_max(0)
        # log1p gives the same expression without cancellation near t=0;
        # factoring out the smallest rate retains survival information when
        # p rounds to one, including when every unshifted lambda*t overflows.
        rate_probability = (weights * -torch.expm1(-attenuation)).sum(dim=0)
        positive_duration = duration > 0
        denominator = torch.where(positive_duration, duration, 1)
        interval_rate = torch.where(
            rate_probability < 0.5,
            -torch.log1p(-rate_probability) / denominator,
            minimum_rate - log_shifted_survival / denominator,
        )
        rate = torch.where(
            positive_duration, interval_rate, (weights * safe_rate).sum(dim=0),
        ).clamp_min(0)
        rate_valid = rate_valid & torch.isfinite(rate)
        known = _valid_mask(burned_area_valid, burned_area, "burned_area_valid") & torch.isfinite(burned_area)
        exact_zero = known & ((burned_area == 1) | (duration == 0))
        probability = torch.where(exact_zero, 0, probability)
        probability_valid = probability_valid | exact_zero
        return BurnProbability(
            probability.masked_fill(~probability_valid, torch.nan), probability_valid,
            rate.masked_fill(~rate_valid, torch.nan), rate_valid,
        )


# Structured kernels (track 1B, additive)
# ---------------------------------------
# One 9x9 environment-conditioned generator (the ablation's favoured family)
# with optional structure: an Anderson (1983) elliptical template multiplied
# by a learned nonnegative residual, wind-frame canonicalization or exact D4
# group averaging of the generator, a flaming window with a learned
# smouldering multiplier, and a wind-aligned long-range branch. Nothing above
# this block is changed; existing classes keep their behaviour and contracts.

STRUCTURED_PRIORS = ("free", "ellipse")
MPH_PER_M_S = 2.2369362920544


def anderson_length_to_breadth(midflame_wind_m_s: Tensor) -> Tensor:
    """Anderson/Finney ellipse length-to-breadth from midflame wind in m/s.

    LB = 0.936 exp(0.2566 U) + 0.461 exp(-0.1548 U) - 0.397 (Anderson 1983,
    USDA Forest Service Research Paper INT-305; Finney 1998, FARSITE,
    RMRS-RP-4). The 0.2566 and -0.1548 coefficients require m/s, not mph;
    the corresponding mph coefficients are 0.1147 and -0.0692.
    https://research.fs.usda.gov/download/treesearch/4617.pdf
    LB(0) = 1 (circle). The ratio is capped at 8, the
    usual FARSITE limit, to keep the template finite at strong winds.
    """
    if not bool(torch.isfinite(midflame_wind_m_s).all()) or bool((midflame_wind_m_s < 0).any()):
        raise ValueError("Midflame wind must be finite and nonnegative in m/s")
    u = midflame_wind_m_s.clamp_max(30)
    lb = 0.936 * torch.exp(0.2566 * u) + 0.461 * torch.exp(-0.1548 * u) - 0.397
    return lb.clamp(1.0, 8.0)


def elliptical_template(u: Tensor, v: Tensor, kernel_size: int, length_cells: Tensor,
                        wind_adjustment_factor: float = 0.4) -> Tensor:
    """Nonnegative ``[..., K*K, H, W]`` template from target wind ``u, v`` (m/s, [..., 1, H, W]).

    A source at offset (dy, dx) reaches the target along the map displacement
    (east, north) = (-dx, dy). With eccentricity e = sqrt(1 - 1/LB^2) and theta
    the angle between that displacement and the wind, the fire-from-rear-focus
    ellipse radius relative to the head is r(theta) = (1 - e) / (1 - e cos theta),
    and the template is exp(-|delta| / (L * r(theta))). Midflame wind is the
    10 m wind times ``wind_adjustment_factor`` (0.4, a typical open-canopy
    value; an assumption, not a measured factor).
    """
    radius = kernel_size // 2
    dy, dx = torch.meshgrid(torch.arange(-radius, radius + 1, dtype=u.dtype, device=u.device),
                            torch.arange(-radius, radius + 1, dtype=u.dtype, device=u.device),
                            indexing="ij")
    east, north = (-dx).flatten(), dy.flatten()
    distance = torch.hypot(east, north)
    shape = (1,) * (u.ndim - 3) + (kernel_size * kernel_size, 1, 1)
    east, north, distance = east.reshape(shape), north.reshape(shape), distance.reshape(shape)
    speed = torch.hypot(u, v)
    lb = anderson_length_to_breadth(speed * wind_adjustment_factor)
    e = torch.sqrt((1 - 1 / lb.square()).clamp_min(0))
    cos = torch.where(speed > 1e-9, (east * u + north * v) / (distance.clamp_min(1e-12) * speed.clamp_min(1e-12)),
                      torch.zeros_like(east * u))
    relative = (1 - e) / (1 - e * cos)
    return torch.exp(-distance / (length_cells * relative))


class StructuredKernelModel(EnvironmentConditionedConvolution):
    """Single-generator nonnegative kernel with optional physical structure.

    Inputs are *raw* ordered channels; the model holds its own training-only
    normalization (``mean``, ``std``), so the wind template and the wind-frame
    rotation can use physical wind vectors. ``kernel_rates`` keeps the parent
    availability contract (NaN where the K x K environmental context is
    unknown). ``forward`` returns the one-interval probability through
    ``new_burn_probability`` exactly like the released families.

    Options: ``prior`` 'free' or 'ellipse'; ``frame`` 'none', 'd4' (exact
    group averaging of the generator) or 'wind' (canonicalization);
    ``residence_hours`` enables a flaming window with a learned smouldering
    multiplier (used by the mean field); ``spotting_radius`` > K//2 adds a
    wind-aligned long-range branch acting on flaming sources.
    """

    def __init__(self, in_channels: int, kernel_size: int = 9, hidden_channels: int = 16,
                 dropout: float = 0.0, *, channel_names: Sequence[str],
                 mean: Tensor | None = None, std: Tensor | None = None,
                 wind_channels: tuple[str, str] = ("weather.wind_eastward_10m", "weather.wind_northward_10m"),
                 prior: str = "free", frame: str = "none", residence_hours: float | None = None,
                 spotting_radius: int = 0, wind_adjustment_factor: float = 0.4,
                 initial_length_cells: float = 2.0):
        super().__init__(in_channels, kernel_size, hidden_channels)
        if prior not in STRUCTURED_PRIORS:
            raise ValueError(f"prior must be one of {STRUCTURED_PRIORS}")
        if frame not in ("none", "d4", "wind"):
            raise ValueError("frame must be 'none', 'd4' or 'wind'")
        names = tuple(channel_names)
        if len(names) != in_channels or len(set(names)) != len(names):
            raise ValueError("channel_names must list every input channel exactly once")
        if any(name not in names for name in wind_channels):
            raise ValueError("Both wind channels must be among channel_names")
        if spotting_radius and spotting_radius <= kernel_size // 2:
            raise ValueError("spotting_radius must exceed the local kernel radius")
        if residence_hours is not None and (not math.isfinite(residence_hours) or residence_hours <= 0):
            raise ValueError("residence_hours must be finite and positive")
        self.channel_names = names
        self.wind_index = (names.index(wind_channels[0]), names.index(wind_channels[1]))
        self.prior, self.frame = prior, frame
        self.hidden_channels, self.dropout = hidden_channels, float(dropout)
        self.residence_hours = residence_hours
        self.spotting_radius = int(spotting_radius)
        self.wind_adjustment_factor = float(wind_adjustment_factor)
        self.kernel_network = _PatchGenerator(in_channels, kernel_size, "cnn", hidden_channels, 1, dropout)
        self.register_buffer("mean", torch.zeros(in_channels, 1, 1) if mean is None else mean.reshape(-1, 1, 1).clone())
        self.register_buffer("std", torch.ones(in_channels, 1, 1) if std is None else std.reshape(-1, 1, 1).clone())
        self.log_length = nn.Parameter(torch.tensor(math.log(math.expm1(initial_length_cells))))
        self.smoulder_logit = nn.Parameter(torch.tensor(-2.0)) if residence_hours is not None else None
        if self.spotting_radius:
            self.spot_amplitude_logit = nn.Parameter(torch.tensor(-9.0))
            self.spot_speed_coefficient = nn.Parameter(torch.tensor(0.0))
            self.spot_log_length = nn.Parameter(torch.tensor(math.log(math.expm1(5.0))))
            self.spot_log_width = nn.Parameter(torch.tensor(math.log(math.expm1(1.5))))

    def configuration(self) -> dict:
        return dict(architecture="StructuredKernelModel", in_channels=self.in_channels,
                    kernel_size=self.kernel_size, hidden_channels=self.hidden_channels,
                    dropout=self.dropout, channel_names=list(self.channel_names),
                    wind_channels=[self.channel_names[i] for i in self.wind_index],
                    prior=self.prior, frame=self.frame, residence_hours=self.residence_hours,
                    spotting_radius=self.spotting_radius,
                    wind_adjustment_factor=self.wind_adjustment_factor)

    @torch.no_grad()
    def initialize_rate(self, rate: float) -> None:
        """Start every noncentre offset near ``rate`` per hour (output layer only)."""
        if not math.isfinite(rate) or rate <= 0:
            raise ValueError("rate must be finite and positive")
        if self.prior == "ellipse":
            # The zero-wind template averages exp(-|delta|/L) over offsets.
            radius = self.kernel_size // 2
            grid = torch.arange(-radius, radius + 1, dtype=torch.float64)
            distance = torch.hypot(grid[:, None], grid[None, :]).flatten()
            mean_template = float(torch.exp(-distance / float(F.softplus(self.log_length.double()))).mean())
            rate = rate / max(mean_template, 1e-6)
        self.kernel_network.output.weight.zero_()
        self.kernel_network.output.bias.fill_(rate + math.log(-math.expm1(-rate)))

    def smoulder(self) -> Tensor | None:
        return None if self.smoulder_logit is None else torch.sigmoid(self.smoulder_logit)

    def flaming_window(self):
        if self.residence_hours is None:
            return None
        from .burnout import FlamingWindow
        return FlamingWindow(self.residence_hours, self.smoulder())

    def _raw_wind(self, clean: Tensor) -> tuple[Tensor, Tensor]:
        iu, iv = self.wind_index
        u = clean[..., iu:iu + 1, :, :] * self.std[iu] + self.mean[iu]
        v = clean[..., iv:iv + 1, :, :] * self.std[iv] + self.mean[iv]
        return u, v

    def _positive(self, clean: Tensor) -> Tensor:
        logits = self.kernel_network(clean)
        if not bool(torch.isfinite(logits).all()):
            raise RuntimeError("The structured kernel generator produced nonfinite values")
        return F.softplus(logits)

    def _structured(self, clean: Tensor, available: Tensor) -> Tensor:
        leading = tuple(clean.shape[:-3])
        c, h, w = clean.shape[-3:]
        flat = clean.reshape(-1, c, h, w)
        valid = available.reshape(-1, 1, h, w)
        if self.frame == "wind":
            from .canonical import local_canonical_kernels
            residual = local_canonical_kernels(self._positive, flat, self.wind_index,
                                               self.mean, self.std, self.kernel_size)
        else:
            residual = self._positive(flat)
        kernels = residual
        if self.prior == "ellipse":
            u, v = self._raw_wind(flat)
            kernels = kernels * elliptical_template(u, v, self.kernel_size, F.softplus(self.log_length),
                                                    self.wind_adjustment_factor)
        kernels = kernels * self.off_center
        return kernels.reshape(*leading, self.kernel_size ** 2, h, w)

    def kernel_rates(self, environmental_data: Tensor, feature_valid: Tensor | None = None,
                     *, boundary: str = "unknown") -> Tensor:
        """Hourly offset rates ``[..., K*K, H, W]`` from raw channels; NaN where unknown."""
        normalized = (environmental_data - self.mean) / self.std
        clean, available = self._features(normalized, feature_valid, boundary)
        if self.frame == "wind":
            from .canonical import canonical_context_size
            width = canonical_context_size(self.kernel_size)
            known = torch.isfinite(environmental_data)
            if feature_valid is not None:
                known = known & feature_valid
            h, w = known.shape[-2:]
            known = known.all(-3, keepdim=True).to(clean.dtype).reshape(-1, 1, h, w)
            known = F.pad(known, (width // 2,) * 4, value=float(boundary == "zero"))
            context = F.avg_pool2d(known, width, stride=1) == 1
            available = available & context.reshape_as(available)
        if self.frame == "d4":
            rates = self._d4_rates(environmental_data, feature_valid, clean, available)
        else:
            rates = self._structured(clean, available)
        return rates.masked_fill(~available.expand_as(rates), torch.nan)

    def _d4_rates(self, raw: Tensor, feature_valid, clean: Tensor, available: Tensor) -> Tensor:
        from .canonical import d4_symmetrize_kernels
        leading = tuple(clean.shape[:-3])
        c, h, w = clean.shape[-3:]
        # The group acts on raw values (wind sign/swap); unknown inputs are
        # replaced by the training mean, and their targets stay masked.
        raw_clean = torch.where(torch.isfinite(raw), raw, self.mean.expand_as(raw)).reshape(-1, c, h, w)
        if feature_valid is not None:
            raw_clean = torch.where(feature_valid.reshape(-1, c, h, w), raw_clean, self.mean.expand_as(raw_clean))

        def generator(moved_raw):
            positive = self._positive((moved_raw - self.mean) / self.std)
            if self.prior == "ellipse":
                iu, iv = self.wind_index
                positive = positive * elliptical_template(
                    moved_raw[:, iu:iu + 1], moved_raw[:, iv:iv + 1], self.kernel_size,
                    F.softplus(self.log_length), self.wind_adjustment_factor)
            return positive

        kernels = d4_symmetrize_kernels(generator, raw_clean, self.wind_index) * self.off_center
        return kernels.reshape(*leading, self.kernel_size ** 2, h, w)

    def spot_rate(self, source: Tensor, environmental_data: Tensor, *, boundary: str = "zero") -> Tensor:
        """Long-range hourly rate ``[..., 1, H, W]`` from flaming ``source``.

        Support: Chebyshev distance in (K//2, spotting_radius], downwind only.
        Weight exp(-d_par / L) exp(-d_perp^2 / (2 w^2)) along the domain-mean
        wind direction, times a target amplitude softplus(a0 + a1 * speed).
        Only the explicit 'zero' boundary (fully known in-grid states) is
        supported, because the branch does not track unknown sources.
        """
        if not self.spotting_radius:
            return torch.zeros_like(source)
        if boundary != "zero":
            raise ValueError("The long-range branch requires boundary='zero' with fully known in-grid states")
        from .canonical import mean_wind_angle
        leading = tuple(source.shape[:-3])
        h, w = source.shape[-2:]
        raw = environmental_data.reshape(-1, environmental_data.shape[-3], h, w)
        src = source.reshape(-1, 1, h, w)
        iu, iv = self.wind_index
        radius = self.spotting_radius
        offsets = torch.arange(-radius, radius + 1, dtype=src.dtype, device=src.device)
        dy, dx = torch.meshgrid(offsets, offsets, indexing="ij")
        east, north = -dx, dy
        local = torch.maximum(dy.abs(), dx.abs()) > self.kernel_size // 2
        length, width = F.softplus(self.spot_log_length), F.softplus(self.spot_log_width)
        rates = []
        for n in range(src.shape[0]):
            u, v = raw[n, iu], raw[n, iv]
            finite = torch.isfinite(u) & torch.isfinite(v)
            angle = mean_wind_angle(u, v, finite)
            parallel = east * math.cos(angle) + north * math.sin(angle)
            perpendicular = -east * math.sin(angle) + north * math.cos(angle)
            weight = torch.exp(-parallel / length) * torch.exp(-perpendicular.square() / (2 * width.square()))
            weight = torch.where(local & (parallel > 0), weight, torch.zeros_like(weight))
            spread = F.conv2d(src[n:n + 1], weight[None, None], padding=radius)
            speed = torch.hypot(torch.where(finite, u, 0), torch.where(finite, v, 0))
            amplitude = F.softplus(self.spot_amplitude_logit + self.spot_speed_coefficient * speed / 5.0)
            rates.append(amplitude * spread[0])
        return torch.stack(rates).reshape(*leading, 1, h, w)

    def forward(self, burned_area: Tensor, environmental_data: Tensor, *, dt_hours: Real | Tensor = 1.0,
                burned_area_valid: Tensor | None = None, feature_valid: Tensor | None = None,
                boundary: str = "unknown") -> BurnProbability:
        """One-interval new-burn probability (local kernel only, absorbing sources)."""
        kernels = self.kernel_rates(environmental_data, feature_valid, boundary=boundary)
        finite = torch.isfinite(kernels).all(dim=-3, keepdim=True)
        return new_burn_probability(burned_area, torch.where(torch.isfinite(kernels), kernels, 0),
                                    dt_hours=dt_hours, burned_area_valid=burned_area_valid,
                                    kernel_valid=finite, boundary=boundary)


__all__ += ["STRUCTURED_PRIORS", "anderson_length_to_breadth", "elliptical_template",
            "StructuredKernelModel"]
