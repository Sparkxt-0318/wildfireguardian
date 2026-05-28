"""Retrospective validation against historical Korean wildfires.

Session 2 deliverable. The package exposes:

- :mod:`.metrics`: standalone metric functions (IoU, Sørensen-Dice,
  symmetric difference, Brier score, lead-time gain, temporal area RMSE).
- :mod:`.harness`: end-to-end :class:`ValidationCase` /
  :func:`run_validation` pipeline.

Quickstart::

    from wildfireguardian.validation import (
        ValidationCase, ModelConfig, run_validation, load_case,
    )
    case = load_case("data/validation_cases/yeongdeok_2025.json")
    results = run_validation(case)
    print(results.as_dict())
"""

from __future__ import annotations

from .baselines import (
    BaselineConfig,
    run_isotropic_baseline,
    run_persistence_baseline,
)
from .harness import (
    HorizonMetrics,
    ModelConfig,
    ValidationCase,
    ValidationResults,
    ValidationRunWithBaselines,
    compute_horizon_metrics,
    load_case,
    load_observed_perimeter_series,
    run_validation,
    run_validation_with_baselines,
)
from .metrics import (
    PerimeterAtTime,
    brier_score,
    brier_skill_score,
    lead_time_gain,
    perimeter_iou,
    perimeter_sorensen_dice,
    perimeter_symmetric_difference_area_km2,
    temporal_perimeter_rmse,
)

__all__ = [
    # harness
    "ValidationCase",
    "ModelConfig",
    "ValidationResults",
    "load_case",
    "run_validation",
    # Session 3 — with baselines + time-indexed observed
    "HorizonMetrics",
    "ValidationRunWithBaselines",
    "compute_horizon_metrics",
    "load_observed_perimeter_series",
    "run_validation_with_baselines",
    "BaselineConfig",
    "run_persistence_baseline",
    "run_isotropic_baseline",
    # metrics
    "PerimeterAtTime",
    "perimeter_iou",
    "perimeter_sorensen_dice",
    "perimeter_symmetric_difference_area_km2",
    "brier_score",
    "brier_skill_score",
    "lead_time_gain",
    "temporal_perimeter_rmse",
]
