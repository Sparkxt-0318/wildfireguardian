"""Validation robustness — how much do the metrics depend on the
approximate observed perimeter? (Session 4 Deliverable 3.)

The observed perimeter is APPROXIMATE (reconstructed from public
reporting). A reviewer will rightly ask: "if your ground truth is itself
uncertain, how much should I trust the IoU?" This module answers that by
perturbing the observed perimeter (area scaling, centroid shift) and
reporting the resulting IoU range against a fixed model prediction.
"""

from __future__ import annotations

from dataclasses import dataclass

from shapely.affinity import scale, translate
from shapely.geometry.base import BaseGeometry

from .metrics import PerimeterAtTime, perimeter_iou, perimeter_sorensen_dice


@dataclass
class PerturbationResult:
    """IoU/Dice of a fixed prediction against perturbed observed perimeters."""

    horizon_min: float
    baseline_iou: float
    iou_min: float
    iou_max: float
    baseline_dice: float
    dice_min: float
    dice_max: float
    perturbations: list[dict]

    def as_dict(self) -> dict:
        return {
            "horizon_min": self.horizon_min,
            "baseline_iou": self.baseline_iou,
            "iou_min": self.iou_min,
            "iou_max": self.iou_max,
            "iou_range": self.iou_max - self.iou_min,
            "baseline_dice": self.baseline_dice,
            "dice_min": self.dice_min,
            "dice_max": self.dice_max,
            "perturbations": self.perturbations,
        }


def _perturb(poly: BaseGeometry, area_scale: float, shift_m: tuple[float, float]) -> BaseGeometry:
    """Scale a polygon's area by ``area_scale`` and shift its centroid."""
    # Area scales as the square of the linear scale factor.
    linear = area_scale ** 0.5
    c = poly.centroid
    scaled = scale(poly, xfact=linear, yfact=linear, origin=(c.x, c.y))
    return translate(scaled, xoff=shift_m[0], yoff=shift_m[1])


def iou_sensitivity_at_horizon(
    predicted: BaseGeometry,
    observed: BaseGeometry,
    area_scales: tuple[float, ...] = (0.8, 0.9, 1.0, 1.1, 1.2),
    shifts_m: tuple[tuple[float, float], ...] = (
        (0.0, 0.0), (500.0, 0.0), (-500.0, 0.0), (0.0, 500.0), (0.0, -500.0),
    ),
    horizon_min: float = 0.0,
) -> PerturbationResult:
    """Vary the observed perimeter (±20% area, ±500 m centroid) and report
    the IoU / Dice range against a FIXED predicted perimeter.

    This bounds "how much should we trust the IoU number" given that the
    observed perimeter is itself approximate.
    """
    baseline_iou = perimeter_iou(predicted, observed)
    baseline_dice = perimeter_sorensen_dice(predicted, observed)

    ious: list[float] = []
    dices: list[float] = []
    records: list[dict] = []
    for a in area_scales:
        for sh in shifts_m:
            obs_p = _perturb(observed, a, sh)
            iou = perimeter_iou(predicted, obs_p)
            dice = perimeter_sorensen_dice(predicted, obs_p)
            ious.append(iou)
            dices.append(dice)
            records.append({
                "area_scale": a, "shift_m": list(sh),
                "iou": iou, "dice": dice,
            })
    return PerturbationResult(
        horizon_min=horizon_min,
        baseline_iou=baseline_iou,
        iou_min=min(ious), iou_max=max(ious),
        baseline_dice=baseline_dice,
        dice_min=min(dices), dice_max=max(dices),
        perturbations=records,
    )


__all__ = [
    "PerturbationResult",
    "iou_sensitivity_at_horizon",
]
