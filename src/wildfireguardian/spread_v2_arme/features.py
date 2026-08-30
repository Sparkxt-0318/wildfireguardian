"""Arm E feature construction: a directional slope term beside the wind one.

Reference frame — confirmed against ``spread_v2/features.py::build_candidate_frame``
rather than assumed. ``wind_alignment`` is built as:

    dist, (src_r, src_c) = distance_transform_edt(~active, return_indices=True)
    east  = (col - src_c) * cell_size_m
    north = (src_r - row) * cell_size_m          # row index increases southward
    ux, uy = east/|.|, north/|.|
    wind_alignment = ux*wind_u + uy*wind_v       # wind_u,wind_v are UNIT vectors

So the bearing is measured from the NEAREST ACTIVE CELL, not from the fire
centroid, and the result is a true cosine in [-1, 1]. ``upslope_alignment`` is
built on exactly that frame and normalisation, which is what makes the two
directly comparable in a permutation-importance ranking.
"""

from __future__ import annotations

import numpy as np

from .terrain import upslope_bearing_field

#: Session 11 swept these windows; 1.5 km gave the strongest circular
#: correlation between observed spread bearing and upslope bearing.
SMOOTH_WINDOWS_M = (0.0, 1500.0, 2500.0, 3500.0, 5500.0)
PRIMARY_SMOOTH_M = 1500.0

#: The directional feature, at the primary window, plus the magnitude term.
ARM_E_FEATURE_COLUMNS: tuple[str, ...] = (
    "upslope_alignment",
    "slope_forcing",
)

#: Non-feature columns carried for stratification and sensitivity reporting.
ARM_E_EXTRA_COLUMNS: tuple[str, ...] = (
    ("native_slope_deg",)
    + tuple(f"upslope_alignment_s{int(w)}" for w in SMOOTH_WINDOWS_M)
)


def alignment_from_field(rows, cols, src_r, src_c, ge, gn, cell_m) -> np.ndarray:
    """Cosine between each cell's bearing-from-source and the upslope vector."""
    east = (cols - src_c[rows, cols]).astype("float64") * cell_m
    north = (src_r[rows, cols] - rows).astype("float64") * cell_m
    n1 = np.hypot(east, north)
    ge_c, gn_c = ge[rows, cols], gn[rows, cols]
    n2 = np.hypot(ge_c, gn_c)
    out = np.full(len(rows), np.nan, dtype="float64")
    ok = (n1 > 1e-9) & (n2 > 1e-9) & np.isfinite(n2)
    out[ok] = ((east[ok] / n1[ok]) * (ge_c[ok] / n2[ok])
               + (north[ok] / n1[ok]) * (gn_c[ok] / n2[ok]))
    return out


def arm_e_columns(rows, cols, active, elev, native_slope, cell_m) -> dict:
    """Arm E columns for candidate cells ``(rows, cols)`` at one transition.

    Undefined values stay NaN — never filled.
    ``HistGradientBoostingClassifier`` consumes NaN natively, so a cell on flat
    ground (where "upslope" has no direction) remains in the dataset and
    remains visible as undefined rather than being imputed to zero, which would
    read as "perpendicular to the slope" and is a different claim.
    """
    from scipy.ndimage import distance_transform_edt

    _, (src_r, src_c) = distance_transform_edt(~active, return_indices=True)

    out: dict[str, np.ndarray] = {}
    for w in SMOOTH_WINDOWS_M:
        ge, gn = upslope_bearing_field(elev, cell_m, w)
        out[f"upslope_alignment_s{int(w)}"] = alignment_from_field(
            rows, cols, src_r, src_c, ge, gn, cell_m)

    out["upslope_alignment"] = out[f"upslope_alignment_s{int(PRIMARY_SMOOTH_M)}"].copy()

    ns = native_slope[rows, cols].astype("float64")
    out["native_slope_deg"] = ns
    # Rothermel's functional form WITHOUT his packing-ratio coefficient: that
    # constant scales every cell identically and so cannot change any split a
    # tree makes, while pretending to a fuel calibration this project has not
    # done. tan^2 is the part that carries the physics.
    with np.errstate(invalid="ignore"):
        out["slope_forcing"] = np.tan(np.radians(ns)) ** 2
    return out


__all__ = [
    "ARM_E_FEATURE_COLUMNS",
    "ARM_E_EXTRA_COLUMNS",
    "SMOOTH_WINDOWS_M",
    "PRIMARY_SMOOTH_M",
    "arm_e_columns",
    "alignment_from_field",
]
