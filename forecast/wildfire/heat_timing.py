"""Exact flaming occupancy for a finite, constant first-ignition hazard.

The exponential survival law ``S(t) = exp(-rate * t)`` is documented by
NIST: https://www.itl.nist.gov/div898/handbook/apr/section1/apr161.htm .
The occupancy integrals and extrema here are derived from that law with a
deterministic flaming duration. A frozen neural-kernel rate can supply this
scenario; a one-hour probability alone does not establish a physical arrival
law. Forest probabilities and Bayesian probability mixtures must not silently
be identified with a fitted constant hazard. A mixture of exponential arrival
laws generally requires averaging the component occupancies separately.

All times are seconds and all hazard rates are inverse seconds. Existing fire
is handled separately by ``wildfire.heat.initial_active_occupancy``. Combining
initial and first-ignition occupancy requires disjoint events and unconditional
probabilities; no independence between different cells is required.
"""

from __future__ import annotations

from math import factorial
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import ArrayLike, NDArray

if TYPE_CHECKING:
    from .heat import BurningOccupancy

__all__ = [
    "constant_hazard_occupancy",
    "infer_ignition_rate",
    "constant_hazard_unknown_occupancy_upper",
]

FloatArray = NDArray[np.float64]
_SMALL_Y_COEFFICIENTS = tuple(
    (-1.0) ** (power + 1) / factorial(power + 1) for power in range(1, 11)
)


def _finite_real(value: ArrayLike, name: str) -> FloatArray:
    if np.ma.isMaskedArray(value) and np.any(np.ma.getmaskarray(value)):
        raise ValueError(f"{name} contains masked values; supply complete inputs")
    try:
        original = np.asarray(value)
        if original.dtype.kind not in "iuf":
            raise ValueError(f"{name} must contain real numeric values, not booleans or strings")
        result = np.array(original, dtype=np.float64, copy=True)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{name} must contain real numeric values") from error
    if result.size == 0 or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be nonempty and finite")
    return result


def _interval(interval_s: float) -> float:
    value = _finite_real(interval_s, "interval_s")
    if value.ndim != 0 or value <= 0:
        raise ValueError("interval_s must be a positive numeric scalar in seconds")
    return float(value)


def _duration(burning_duration_s: ArrayLike, shape: tuple[int, ...] | None = None) -> FloatArray:
    duration = _finite_real(burning_duration_s, "burning_duration_s")
    if np.any(duration <= 0):
        raise ValueError("burning_duration_s must be positive")
    if shape is not None and duration.ndim != 0 and duration.shape != shape:
        raise ValueError("burning_duration_s must be scalar or exactly match the ignition rate shape")
    return duration


def _one_minus_exponential_mean(y: FloatArray) -> FloatArray:
    """Evaluate 1 - (1 - exp(-y))/y, including y=0 and overflowed y=inf."""
    result = np.ones_like(y)
    small = y < 0.1
    small_y = y[small]
    polynomial = np.zeros_like(small_y)
    for coefficient in reversed(_SMALL_Y_COEFFICIENTS):
        polynomial = coefficient + small_y * polynomial
    result[small] = small_y * polynomial
    finite_large = (~small) & np.isfinite(y)
    large_y = y[finite_large]
    result[finite_large] = 1.0 + np.expm1(-large_y) / large_y
    return result


def constant_hazard_occupancy(
    ignition_rate_s_inv: ArrayLike,
    burning_duration_s: ArrayLike,
    interval_s: float,
) -> BurningOccupancy:
    """Return mean and endpoint activity from a finite constant ignition hazard.

    Each initially unburned cell has first-ignition time A with exponential
    survival exp(-lambda*t), for a finite lambda >= 0. At lambda=0 no ignition
    occurs. Given ignition, a cell is active on [A,A+T), with supplied finite
    T>0. Output shape is the rate input's shape; duration must be scalar or have
    exactly that shape. Inputs are complete scalar values or nonempty arrays.

    Write D=interval_s, x=lambda*D and r=min(T/D,1). For x>0, endpoint occupancy
    is E=exp(-x*(1-r))-exp(-x), and mean occupancy is M=r-E/x. Stable equivalent
    expressions are used near zero and when products overflow. In particular,
    T==D has endpoint probability 1-exp(-lambda*D): finite exponential arrival
    has no atom at A=0. This differs from a fire already active at time zero
    with remaining duration exactly D, which is extinct at the endpoint.

    No probability is conditioned on ignition here: both output probabilities
    include the probability that no ignition occurs during the interval.
    """
    from .heat import BurningOccupancy

    rate = _finite_real(ignition_rate_s_inv, "ignition_rate_s_inv")
    if np.any(rate < 0):
        raise ValueError("ignition_rate_s_inv must be nonnegative")
    interval = _interval(interval_s)
    duration = _duration(burning_duration_s, rate.shape)
    overlap = np.minimum(duration, interval)
    ratio = overlap / interval
    # Products of finite inputs can overflow. Their nonnegative exponential
    # factors still have well-defined limits. Subtract durations before scaling
    # to preserve the distinction between T==D and T just below D.
    with np.errstate(over="ignore", under="ignore"):
        y = rate * overlap
        z = rate * np.maximum(interval - duration, 0.0)
        survival_before_window = np.exp(-z)
        endpoint = survival_before_window * (-np.expm1(-y))
        mean = ratio * (
            -np.expm1(-z) + survival_before_window * _one_minus_exponential_mean(y)
        )
    return BurningOccupancy(mean, endpoint)


def infer_ignition_rate(new_burn_probability: ArrayLike, interval_s: float) -> FloatArray:
    """Infer a constant-hazard scenario rate from a complete q in [0,1).

    Returns -log1p(-q)/D in inverse seconds, preserving the input shape. This
    inversion chooses a constant-hazard interpolation; it does not establish
    the physical within-interval arrival law from one endpoint probability.
    Exactly q=1 is rejected because no finite hazard gives that probability.
    Supply an original finite model rate when its floating-point q saturated.
    """
    probability = _finite_real(new_burn_probability, "new_burn_probability")
    if np.any((probability < 0) | (probability >= 1)):
        raise ValueError("new_burn_probability must lie in [0,1); q=1 has no finite constant hazard")
    interval = _interval(interval_s)
    with np.errstate(over="ignore", under="ignore"):
        rate = -np.log1p(-probability) / interval
    if not np.all(np.isfinite(rate)):
        raise ValueError("inferred ignition rate exceeds the supported finite numeric range")
    return rate


def constant_hazard_unknown_occupancy_upper(
    burning_duration_s: ArrayLike, interval_s: float,
) -> BurningOccupancy:
    """Return occupancy suprema over all finite nonnegative ignition hazards.

    The lower mean and endpoint occupancies are zero. Let r=min(T/D,1). Mean
    occupancy has supremum r as lambda tends to infinity. For 0<r<1, endpoint
    occupancy is nonmonotone: its maximum is r*(1-r)**((1-r)/r), attained at
    lambda*D=-log1p(-r)/r. For T>=D the endpoint supremum is one. These are
    bounds under the supplied constant-hazard/deterministic-duration scenario,
    not confidence intervals or bounds over arbitrary ignition-time laws.

    Output shape equals the duration input's shape. A ratio that underflows to
    zero has zero representable occupancy; no zero physical duration is allowed.
    """
    from .heat import BurningOccupancy

    interval = _interval(interval_s)
    duration = _duration(burning_duration_s)
    ratio = np.minimum(duration, interval) / interval
    endpoint = np.ones_like(ratio)
    short = (ratio > 0) & (ratio < 1)
    short_ratio = ratio[short]
    # Divide only after multiplication; (1-r)/r can overflow for tiny r.
    exponent = ((1.0 - short_ratio) * np.log1p(-short_ratio)) / short_ratio
    endpoint[short] = short_ratio * np.exp(exponent)
    endpoint[ratio == 0] = 0.0
    return BurningOccupancy(ratio, endpoint)
