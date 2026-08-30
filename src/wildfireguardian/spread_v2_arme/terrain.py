"""Native-resolution slope, and the directional terrain quantities Arm E needs.

Session 12. Two separate concerns live here.

RESOLUTION. ``spread_v2.grid.elevation_on_grid`` averages the 1-arcsec SRTM
(~25 x 31 m on the ground at these latitudes) into 500 m cells, and
``slope_deg`` then differences that averaged surface over a 500 m baseline.
Both steps remove relief, and the result was a mean slope of 6.28 deg across
Korean mountain terrain, which is implausibly gentle. This module recomputes
slope at native resolution and aggregates it, so the attenuation can be
measured instead of assumed.

WHICH AGGREGATE. Not the mean. Rothermel's (1972) slope factor is
``phi_s = 5.275 * beta^-0.3 * (tan phi)^2`` — QUADRATIC in ``tan phi``. By
Jensen's inequality ``E[tan^2 phi] >= (E[tan phi])^2``, so the mean slope of a
heterogeneous cell systematically understates that cell's mean slope forcing,
and the understatement grows with within-cell roughness. The aggregate that
preserves the physics is therefore the slope whose forcing EQUALS the cell's
mean forcing:

    slope_effective = arctan( sqrt( mean( tan(phi)^2 ) ) )

Mean, median, IQR and max are all reported too, because the choice should be
visible rather than buried. ``slope_effective`` sits between the mean and the
max by construction.

⚠ CALIBRATION RANGE. Rothermel derived that slope function from 12 laboratory
fires at 14.0, 26.6 and 36.9 deg. Every slope in this project — at either
resolution — sits BELOW the lowest calibrated angle, so the functional form is
being extrapolated downward wherever it is used. That bounds how much slope
forcing can be expected at all, and it is stated wherever these numbers appear.
"""

from __future__ import annotations

import numpy as np

#: 500 m / 16 = 31.25 m, the closest integer subdivision to the ~30 m native
#: SRTM posting. A finer factor would interpolate rather than reveal relief.
DEFAULT_SUBDIVISION = 16


def fine_grid(grid, factor: int = DEFAULT_SUBDIVISION):
    """A grid with the SAME extent as ``grid`` but ``factor``x finer cells.

    Built by hand rather than through ``build_grid`` because that function
    derives its dimensions with ``ceil``, so a finer call on the same bbox does
    not generally produce exactly ``factor`` sub-cells per coarse cell. Sharing
    ``minx``/``maxy`` and multiplying the counts guarantees exact nesting, which
    is what makes the block aggregation below valid.
    """
    from ..spread_v2.grid import CoarseGrid

    cs = grid.cell_size_m / factor
    return CoarseGrid(
        minx=grid.minx, maxy=grid.maxy,
        miny=grid.maxy - grid.nrows * grid.cell_size_m,
        maxx=grid.minx + grid.ncols * grid.cell_size_m,
        cell_size_m=cs,
        nrows=grid.nrows * factor, ncols=grid.ncols * factor,
    )


def _blocks(a: np.ndarray, nrows: int, ncols: int, factor: int) -> np.ndarray:
    """Reshape a fine array into (nrows, ncols, factor*factor) sub-cells."""
    return (a.reshape(nrows, factor, ncols, factor)
             .transpose(0, 2, 1, 3)
             .reshape(nrows, ncols, factor * factor))


def native_slope_stats(event, grid, factor: int = DEFAULT_SUBDIVISION) -> dict:
    """Per-coarse-cell slope statistics computed at native DEM resolution.

    Returns a dict of (nrows, ncols) arrays in degrees: ``mean``, ``median``,
    ``p75``, ``p90``, ``max``, ``iqr`` and ``effective`` (the Rothermel-forcing
    equivalent slope defined in the module docstring).
    """
    from ..spread_v2 import grid as gridmod

    fg = fine_grid(grid, factor)
    # bilinear, not average: the target cell (31.25 m) is already at the source
    # posting, so averaging would smooth exactly the relief being measured.
    elev_fine = gridmod._reproject_raster(
        event.dem_path, fg, resampling_name="bilinear")
    slope_fine = gridmod.slope_deg(elev_fine, fg.cell_size_m)

    blk = _blocks(slope_fine, grid.nrows, grid.ncols, factor)
    with np.errstate(invalid="ignore"):
        tan2 = np.tan(np.radians(blk)) ** 2
        eff = np.degrees(np.arctan(np.sqrt(np.nanmean(tan2, axis=2))))
        q25 = np.nanpercentile(blk, 25, axis=2)
        q75 = np.nanpercentile(blk, 75, axis=2)
        out = {
            "mean": np.nanmean(blk, axis=2),
            "median": np.nanmedian(blk, axis=2),
            "p75": q75,
            "p90": np.nanpercentile(blk, 90, axis=2),
            "max": np.nanmax(blk, axis=2),
            "iqr": q75 - q25,
            "effective": eff,
        }
    return out


def upslope_bearing_field(elev: np.ndarray, cell_m: float, smooth_m: float):
    """(east, north) components of steepest ASCENT per cell, optionally smoothed.

    Mirrors ``scripts/direction_drivers.py`` exactly so Arm E's feature and the
    Session 11 measurement describe the same vector field. Nodata is filled
    with the nearest valid elevation first: a boxcar spreads each NaN across
    its whole window, and SRTM here carries up to 2.8 % nodata.
    """
    from scipy.ndimage import distance_transform_edt, uniform_filter

    z = np.asarray(elev, dtype="float64")
    bad = ~np.isfinite(z)
    if bad.any():
        _, (ir, ic) = distance_transform_edt(bad, return_indices=True)
        z = z[ir, ic]
    if smooth_m > 0:
        size = max(1, int(round(smooth_m / cell_m)))
        if size % 2 == 0:
            size += 1
        z = uniform_filter(z, size=size, mode="nearest")
    d_north = -np.gradient(z, cell_m, axis=0)   # row index increases southward
    d_east = np.gradient(z, cell_m, axis=1)
    return d_east, d_north


def rothermel_slope_factor(slope_deg_arr: np.ndarray, beta: float = 0.05) -> np.ndarray:
    """``phi_s = 5.275 * beta^-0.3 * (tan phi)^2`` (Rothermel 1972).

    ⚠ EXTRAPOLATED. Calibrated at 14.0 / 26.6 / 36.9 deg; every slope in this
    project is below 14 deg. ``beta`` (packing ratio) is a placeholder constant
    here because no Korean fuel-bed packing ratio has been measured for this
    project — it scales every cell identically and so cannot change any
    ranking, ordering or correlation, only the absolute magnitude. It is NOT a
    calibrated fuel parameter and must not be reported as one.
    """
    t = np.tan(np.radians(np.asarray(slope_deg_arr, dtype="float64")))
    return 5.275 * (beta ** -0.3) * t ** 2


__all__ = [
    "DEFAULT_SUBDIVISION",
    "fine_grid",
    "native_slope_stats",
    "upslope_bearing_field",
    "rothermel_slope_factor",
]
