"""Quantitative validation metrics for wildfire-spread predictions.

Every metric here is a pure function over geometry/raster inputs and
returns a scalar (or :class:`datetime.timedelta` for time gains). Use
:mod:`wildfireguardian.validation.harness` to plug these into the
retrospective-replay loop.

The metric set is chosen to be defensible to forestry reviewers:

- **Spatial agreement**: IoU and Sørensen-Dice — standard ecology /
  remote-sensing perimeter-comparison metrics.
- **Area error**: symmetric-difference area in km².
- **Probabilistic skill**: Brier score over a probability raster vs.
  observed binary truth.
- **Operational signal**: lead-time gain — how much earlier our system
  could have warned vs. the actual official warning timeline.
- **Temporal accuracy**: perimeter-area RMSE at multiple time horizons.

References
----------
- Sørensen, T. (1948). *A method of establishing groups of equal
  amplitude in plant sociology...* Biol. Skr. 5: 1–34.
- Brier, G.W. (1950). *Verification of forecasts expressed in terms of
  probability.* Mon. Weather Rev. 78: 1–3.
- Filippi, J.B. et al. (2014). *Evaluation of forest fire spread
  simulations...* Comput. Geosci. 71: 87–98.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Sequence

import numpy as np
from shapely.geometry.base import BaseGeometry


# ---------------------------------------------------------------------------
# Perimeter agreement metrics
# ---------------------------------------------------------------------------


def perimeter_iou(predicted: BaseGeometry | None, observed: BaseGeometry | None) -> float:
    """Intersection over Union of two polygons.

    Returns 1.0 if both are empty, 0.0 if exactly one is empty.

    Reference: Jaccard index; standard in remote-sensing perimeter validation.
    """
    if predicted is None and observed is None:
        return 1.0
    if predicted is None or observed is None:
        return 0.0
    if predicted.is_empty and observed.is_empty:
        return 1.0
    if predicted.is_empty or observed.is_empty:
        return 0.0
    inter = predicted.intersection(observed).area
    union = predicted.union(observed).area
    if union <= 0.0:
        return 0.0
    return float(inter / union)


def perimeter_sorensen_dice(
    predicted: BaseGeometry | None, observed: BaseGeometry | None,
) -> float:
    """Sørensen-Dice coefficient = 2|A ∩ B| / (|A| + |B|).

    Asymptotically equivalent to IoU for highly-overlapping perimeters but
    weights the intersection more heavily — preferred in the fire-spread
    validation literature (Filippi et al. 2014).
    """
    if predicted is None and observed is None:
        return 1.0
    if predicted is None or observed is None:
        return 0.0
    if predicted.is_empty and observed.is_empty:
        return 1.0
    p_area = predicted.area
    o_area = observed.area
    if p_area + o_area <= 0.0:
        return 0.0
    inter = predicted.intersection(observed).area
    return float(2.0 * inter / (p_area + o_area))


def perimeter_symmetric_difference_area_km2(
    predicted: BaseGeometry | None, observed: BaseGeometry | None,
) -> float:
    """Area of the symmetric difference (misclassified regions), in km².

    Assumes the input polygons are in EPSG:5179 (metres). Returns 0.0 if
    both inputs are empty / None.
    """
    if predicted is None and observed is None:
        return 0.0
    if predicted is None:
        return float(observed.area / 1_000_000.0)  # type: ignore[union-attr]
    if observed is None:
        return float(predicted.area / 1_000_000.0)
    return float(predicted.symmetric_difference(observed).area / 1_000_000.0)


# ---------------------------------------------------------------------------
# Probabilistic skill
# ---------------------------------------------------------------------------


def brier_score(
    predicted_probability_field: np.ndarray,
    observed_binary_field: np.ndarray,
) -> float:
    """Brier (mean-squared) score for a probability raster vs. binary truth.

    .. math:: BS = \\frac{1}{N} \\sum_i (p_i - o_i)^2

    where :math:`p_i \\in [0, 1]` is the predicted probability and
    :math:`o_i \\in \\{0, 1\\}` is the observed binary outcome.

    Brier score ∈ [0, 1]; 0 = perfect, 0.25 = no skill (uniform 0.5),
    1 = perfectly wrong.

    Reference: Brier 1950.
    """
    if predicted_probability_field.shape != observed_binary_field.shape:
        raise ValueError(
            f"shape mismatch: predicted {predicted_probability_field.shape} "
            f"vs observed {observed_binary_field.shape}"
        )
    if predicted_probability_field.size == 0:
        return 0.0
    p = predicted_probability_field.astype(np.float64)
    o = observed_binary_field.astype(np.float64)
    if not (0.0 <= p.min() and p.max() <= 1.0 + 1e-9):
        raise ValueError(
            "predicted_probability_field has values outside [0, 1]"
        )
    return float(np.mean((p - o) ** 2))


def brier_skill_score(
    predicted_probability_field: np.ndarray,
    observed_binary_field: np.ndarray,
) -> float:
    """Brier *skill* score (vs. climatological prevalence) ∈ (-∞, 1].

    BSS = 1 - BS / BS_ref where BS_ref = climatology Brier (constant
    prediction at observed prevalence). 1 = perfect, 0 = climatology, < 0 = worse.
    """
    o = observed_binary_field.astype(np.float64)
    if o.size == 0:
        return float("nan")
    prevalence = float(o.mean())
    bs = brier_score(predicted_probability_field, observed_binary_field)
    bs_ref = prevalence * (1.0 - prevalence)
    if bs_ref <= 0.0:
        # Degenerate climatology (all 0 or all 1). BSS undefined.
        return float("nan")
    return float(1.0 - bs / bs_ref)


# ---------------------------------------------------------------------------
# Operational lead-time signal
# ---------------------------------------------------------------------------


def lead_time_gain(
    predicted_warning_time: datetime,
    actual_official_warning_time: datetime,
) -> timedelta:
    """How much earlier our system *would* have warned vs. the historical
    official warning.

    Positive = our system warns earlier (good). Negative = our system
    would have warned later (bad). Returns a :class:`datetime.timedelta`.

    Both timestamps must be timezone-aware OR timezone-naive consistently;
    do not mix.
    """
    if predicted_warning_time.tzinfo is None and actual_official_warning_time.tzinfo is not None:
        raise ValueError("timestamp tz-awareness inconsistency")
    if predicted_warning_time.tzinfo is not None and actual_official_warning_time.tzinfo is None:
        raise ValueError("timestamp tz-awareness inconsistency")
    return actual_official_warning_time - predicted_warning_time


# ---------------------------------------------------------------------------
# Temporal perimeter accuracy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PerimeterAtTime:
    """One perimeter snapshot at a given simulation time."""

    time_min: float
    polygon: BaseGeometry | None
    area_m2: float


def temporal_perimeter_rmse(
    predicted_series: Sequence[PerimeterAtTime],
    observed_series: Sequence[PerimeterAtTime],
    time_horizons_min: Sequence[float] = (60.0, 180.0, 360.0),
) -> dict[float, float]:
    """RMSE of *burned area* at multiple time horizons.

    For each requested ``t`` in ``time_horizons_min``:

    - Look up the nearest predicted snapshot's burned area.
    - Look up the nearest observed snapshot's burned area.
    - Compute (predicted - observed)² in ha².

    Returns ``{time_min: RMSE_area_ha}`` for each requested time. Single
    snapshot is its own "RMSE" — useful for a tabular display per horizon.
    """
    if not predicted_series or not observed_series:
        return {t: float("nan") for t in time_horizons_min}

    pred_by_time = {p.time_min: p for p in predicted_series}
    obs_by_time = {o.time_min: o for o in observed_series}

    def nearest(series_times: Iterable[float], target: float) -> float:
        return min(series_times, key=lambda t: abs(t - target))

    out: dict[float, float] = {}
    for t in time_horizons_min:
        t_pred = nearest(pred_by_time.keys(), t)
        t_obs = nearest(obs_by_time.keys(), t)
        a_pred = pred_by_time[t_pred].area_m2
        a_obs = obs_by_time[t_obs].area_m2
        diff_ha = (a_pred - a_obs) / 10_000.0
        out[t] = float(math.sqrt(diff_ha * diff_ha))
    return out


__all__ = [
    "perimeter_iou",
    "perimeter_sorensen_dice",
    "perimeter_symmetric_difference_area_km2",
    "brier_score",
    "brier_skill_score",
    "lead_time_gain",
    "PerimeterAtTime",
    "temporal_perimeter_rmse",
]
