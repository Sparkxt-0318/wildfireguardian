"""Scoring domain and scoring masks (definitions and reasons: METRICS.md, "Scoring domain").

Headline domain: cells within ``HEADLINE_BUFFER_M`` of the final perimeter, on the event grid. Secondary domain:
the full event rectangle. In both, a cell is scored only if it is in the domain, its label is known at the cutoff
and at the verification time, it was not burned at the cutoff, and every compared model supports it.
Cells beyond the grid were never mapped: they are excluded, never padded as unburned.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

HEADLINE_BUFFER_M = 3000.0  # fixed on 2026-10-31, before any Track A model output; changes need Siyeong's approval


def headline_domain(final_perimeter, cell_size_m: float, buffer_m: float = HEADLINE_BUFFER_M) -> np.ndarray:
    """Cells whose centre lies within ``buffer_m`` (Euclidean, centre to centre) of a final-perimeter cell."""
    perimeter = np.asarray(final_perimeter, dtype=bool)
    if not perimeter.any():
        raise ValueError("the final perimeter is empty")
    distance = ndimage.distance_transform_edt(~perimeter, sampling=float(cell_size_m))
    return distance <= buffer_m * (1 + 1e-12)


def full_rectangle(shape) -> np.ndarray:
    return np.ones(shape, dtype=bool)


def ring_cells_off_grid(final_perimeter, cell_size_m: float, buffer_m: float = HEADLINE_BUFFER_M) -> int:
    """How many cells of the headline ring would fall beyond the grid (they are never mapped and never scored)."""
    perimeter = np.asarray(final_perimeter, dtype=bool)
    pad = int(np.ceil(buffer_m / cell_size_m))
    padded = np.pad(perimeter, pad)
    inside = np.zeros(padded.shape, dtype=bool)
    inside[pad:pad + perimeter.shape[0], pad:pad + perimeter.shape[1]] = True
    return int((headline_domain(padded, cell_size_m, buffer_m) & ~inside).sum())


def scoring_mask(domain, label_known, burned_at_cutoff, *supported) -> np.ndarray:
    """``domain & label_known & ~burned_at_cutoff & supported_1 & supported_2 & ...`` (one array per model).

    Every compared model is scored on the same cells. Report how many domain cells each model's support
    removes: a model must not look better by leaving hard cells unsupported.
    """
    arrays = [np.asarray(a, dtype=bool) for a in (domain, label_known, burned_at_cutoff, *supported)]
    if len({a.shape for a in arrays}) != 1:
        raise ValueError("domain, label, cutoff-state and support masks must share one shape")
    mask = arrays[0] & arrays[1] & ~arrays[2]
    for s in arrays[3:]:
        mask &= s
    return mask
