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

from .harness import (
    ModelConfig,
    ValidationCase,
    ValidationResults,
    load_case,
    run_validation,
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
