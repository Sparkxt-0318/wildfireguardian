"""Convert first-ignition probability to active-burning probability.

A model's probability of a first ignition during an interval is not its
probability of active burning at a particular instant. This module supplies an
explicit temporal assumption for that conversion. Conditional on first ignition
in ``[0, interval_s]``, the ignition time is uniform on that interval; each cell
then burns for a deterministic duration. The trained wildfire model does not
provide this within-interval arrival law or the burning duration.

These are marginal probabilities, so dependence between different cells is not
restricted. The conversion does not simulate fire propagation, reignition,
changing fuel consumption, or a time-varying heat-release rate during a burn.
All times are numeric seconds. No date, timedelta, or implicit unit conversion
is supported.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]


def _numeric_array(value: ArrayLike, name: str) -> FloatArray:
    """Copy finite real values without converting strings or time objects."""
    if np.ma.isMaskedArray(value) and np.any(np.ma.getmaskarray(value)):
        raise ValueError(f"{name} contains masked values; missing values are not zero")
    try:
        original = np.asarray(value)
        if original.dtype.kind not in "biuf":
            raise ValueError(f"{name} must contain real numeric values")
        result = np.array(original, dtype=np.float64, copy=True)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must contain real numeric values") from error
    if result.size == 0:
        raise ValueError(f"{name} must not be empty")
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be finite; missing values are not zero")
    return result


def _probability(value: ArrayLike, name: str) -> FloatArray:
    result = _numeric_array(value, name)
    if np.any((result < 0) | (result > 1)):
        raise ValueError(f"{name} must lie in [0, 1]")
    return result


def _interval(value: float) -> float:
    result = _numeric_array(value, "interval_s")
    if result.ndim != 0 or np.asarray(value).dtype.kind == "b" or result <= 0:
        raise ValueError("interval_s must be a positive numeric scalar in seconds")
    return float(result)


def _duration(
    value: ArrayLike, name: str, shape: tuple[int, ...], *, allow_zero: bool
) -> FloatArray:
    result = _numeric_array(value, name)
    if np.asarray(value).dtype.kind == "b":
        raise ValueError(f"{name} must contain numeric seconds, not booleans")
    if result.ndim != 0 and result.shape != shape:
        raise ValueError(f"{name} must be a scalar or have exactly probability shape {shape}")
    if np.any(result < 0 if allow_zero else result <= 0):
        relation = "nonnegative" if allow_zero else "positive"
        raise ValueError(f"{name} must be {relation}")
    return result


@dataclass(frozen=True)
class BurningOccupancy:
    """Active-burning probabilities averaged over and at the end of an interval.

    ``mean_active_probability`` is the expectation of the fraction of the
    forecast interval for which each cell burns. Equivalently, it is the time
    average of each cell's instantaneous active-burning probability.
    ``endpoint_active_probability`` is each cell's active-burning probability
    at exactly ``interval_s``. Arrays have identical shape and are read-only.

    Multiplying the mean probability by constant conditional heat-release-rate
    density gives the mean expected source density over the interval. That
    source density may be passed through a fixed linear radiation operator to
    obtain mean expected incident heat flux. Multiplying the resulting mean
    flux by the interval duration gives expected incident heat dose.
    """

    mean_active_probability: FloatArray
    endpoint_active_probability: FloatArray

    def __post_init__(self) -> None:
        mean = _probability(self.mean_active_probability, "mean_active_probability")
        endpoint = _probability(self.endpoint_active_probability, "endpoint_active_probability")
        if mean.shape != endpoint.shape:
            raise ValueError("mean and endpoint probability arrays must have identical shapes")
        mean.setflags(write=False)
        endpoint.setflags(write=False)
        object.__setattr__(self, "mean_active_probability", mean)
        object.__setattr__(self, "endpoint_active_probability", endpoint)


def ignition_to_active_probability(
    new_burn_probability: ArrayLike,
    burning_duration_s: ArrayLike,
    interval_s: float,
) -> BurningOccupancy:
    """Convert probability of first ignition during an interval to occupancy.

    For each cell let ``q`` be the unconditional probability of first ignition
    in ``[0, D]``, where ``D = interval_s > 0``. Given that event, assume an
    ignition time ``A ~ Uniform(0, D)`` and a deterministic burning duration
    ``T = burning_duration_s > 0``. The active period is ``[A, A + T)``.
    A cell that does not ignite in this interval contributes zero occupancy
    through this function. Burning already present at time zero must be handled
    separately with :func:`initial_active_occupancy`.

    The time integral of the active indicator over ``[0, D]`` is
    ``min(T, D - A)``. Averaging over ``A`` gives mean occupancy
    ``q * (r - r**2 / 2)`` if ``T <= D``, where ``r = T / D``;
    if ``T >= D``, it gives ``q / 2``. At time ``D``, activity occurs precisely
    when ``D - T < A <= D``, apart from zero-probability endpoints. Hence the
    endpoint probability is ``q * min(T / D, 1)``.

    Input probabilities must be complete, finite, and in ``[0, 1]``. Duration
    may be a scalar or an array with exactly the probability array's shape;
    implicit broadcasting across cells is rejected. Output shape equals input
    probability shape. This function also supports a scalar probability.

    The uniform arrival assumption is additional information supplied by this
    conversion, not a consequence of a model predicting ``q``. Earlier or later
    ignition distributions can produce different mean flux and endpoint flux.
    """
    probability = _probability(new_burn_probability, "new_burn_probability")
    interval = _interval(interval_s)
    duration = _duration(
        burning_duration_s, "burning_duration_s", probability.shape, allow_zero=False
    )
    # Clip before division to avoid overflowing a physically valid T / D.
    ratio = np.minimum(duration, interval) / interval
    mean = probability * (ratio - 0.5 * ratio * ratio)
    endpoint = probability * ratio
    return BurningOccupancy(mean, endpoint)


def initial_active_occupancy(
    initial_active_probability: ArrayLike,
    remaining_burning_duration_s: ArrayLike,
    interval_s: float,
) -> BurningOccupancy:
    """Occupancy from cells that may already be burning at time zero.

    Let ``p`` be the probability a cell is active at time zero and let ``R >= 0``
    be its deterministic remaining duration conditional on that state. It is
    treated as active on ``[0, R)``. For an interval of duration ``D > 0``, mean
    occupancy is ``p * min(R / D, 1)`` and endpoint occupancy is ``p`` if
    ``R > D``, otherwise zero. In particular, ``R == D`` means extinction at
    exactly the forecast endpoint and therefore zero endpoint occupancy.

    ``R == 0`` is allowed and contributes zero at all evaluation times here.
    Duration must be a scalar or have exactly the probability array's shape.
    Probabilities and durations must be complete and finite.

    Combining this result with first-ignition occupancy is justified only when
    the initial-burning event and the forecast first-ignition event are
    disjoint for every cell and their probabilities are unconditional. A
    forecast conditional on being initially unburned must first be weighted
    by that conditioning event's probability.
    """
    probability = _probability(initial_active_probability, "initial_active_probability")
    interval = _interval(interval_s)
    remaining = _duration(
        remaining_burning_duration_s,
        "remaining_burning_duration_s",
        probability.shape,
        allow_zero=True,
    )
    mean = probability * (np.minimum(remaining, interval) / interval)
    endpoint = probability * (remaining > interval)
    return BurningOccupancy(mean, endpoint)
