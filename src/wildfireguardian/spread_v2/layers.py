"""Static per-fire grid layers, all sampled through the orientation-safe sampler.

These are the time-invariant fields the feature pipeline reads: the burnable
gate + burnable fraction (from the WorldCover fuel raster) and elevation +
slope + aspect (from the DEM). Critically, **every layer is produced by
sampling the source raster at each 375 m grid cell's centre through one
:class:`~wildfireguardian.spread_v2.grid.RasterSampler`** — so the burnable
gate shares the exact orientation of the feature layers. There is no second,
differently-oriented mask to AND against (the prior uljin bug).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..data_io.raster import compute_slope_aspect
from .dataset import FireData, worldcover_burnable_map
from .grid import Grid, RasterSampler

# Burnable-gate threshold: a 375 m cell is a valid burn candidate if at least
# this fraction of its footprint is burnable WorldCover land. Majority rule —
# the standard "is this cell vegetated land" test. NOT tuned to any target.
BURNABLE_GATE_FRAC: float = 0.5
# Neighbourhood radius (m) for the burnable_frac_nearby feature.
NEARBY_RADIUS_M: float = 1000.0


@dataclass
class StaticLayers:
    """Time-invariant per-cell layers on the 375 m grid."""

    grid: Grid
    fuel_class: np.ndarray        # WorldCover class code at cell centre (int)
    burnable_frac_cell: np.ndarray   # burnable fraction over the cell footprint
    burnable_frac_nearby: np.ndarray  # burnable fraction within NEARBY_RADIUS_M
    burnable_gate: np.ndarray     # bool: passes the burnable gate
    in_fuel_bounds: np.ndarray    # bool: cell centre falls inside the fuel raster
    elevation: np.ndarray         # metres (DEM sampled at cell centre)
    slope_deg: np.ndarray         # degrees
    aspect_deg: np.ndarray        # degrees, 0 = N clockwise (downslope bearing)
    elevation_rel: np.ndarray     # elevation minus local mean (~2 km window)


def _local_mean(field: np.ndarray, half: int) -> np.ndarray:
    """Uniform-box local mean via integral image (NaN-aware)."""
    valid = np.isfinite(field)
    f = np.where(valid, field, 0.0)
    ii = np.pad(f.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    ic = np.pad(valid.astype(np.float64).cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    H, W = field.shape
    out = np.full(field.shape, np.nan)
    # Vectorised window sums over all cells via the summed-area tables:
    rows = np.arange(H)
    cols = np.arange(W)
    r0 = np.clip(rows - half, 0, H)[:, None]
    r1 = np.clip(rows + half + 1, 0, H)[:, None]
    c0 = np.clip(cols - half, 0, W)[None, :]
    c1 = np.clip(cols + half + 1, 0, W)[None, :]
    tot = ii[r1, c1] - ii[r0, c1] - ii[r1, c0] + ii[r0, c0]
    cnt = ic[r1, c1] - ic[r0, c1] - ic[r1, c0] + ic[r0, c0]
    ok = cnt > 0
    out[ok] = tot[ok] / cnt[ok]
    return out


def build_static_layers(fire: FireData, grid: Grid) -> StaticLayers:
    """Build all static layers for a fire by orientation-safe sampling."""
    XX, YY = grid.center_mesh()

    # --- Fuel / burnable (ESA WorldCover) ---
    fuel = RasterSampler(fire.fuel_tif)
    fuel_class = fuel.sample_xy(XX, YY, fill=0.0)  # nodata(0) → 0 (non-burnable)
    in_fuel_bounds = np.isfinite(fuel.sample_xy(XX, YY, fill=np.nan))

    bmap = worldcover_burnable_map()
    burnable_codes = np.array([k for k, v in bmap.items() if v == 1], dtype=np.int64)
    burnable_pred = np.isin(fuel.array.astype(np.int64), burnable_codes).astype(np.float64)
    integral = fuel.integral_image(burnable_pred)

    res = fuel.resolution_m()
    half_cell = max(1, int(round((grid.cell_size_m / 2.0) / res)))
    half_nearby = max(1, int(round(NEARBY_RADIUS_M / res)))
    burnable_frac_cell = fuel.window_fraction(XX, YY, half_cell, integral)
    burnable_frac_nearby = fuel.window_fraction(XX, YY, half_nearby, integral)

    burnable_gate = (
        in_fuel_bounds
        & np.isfinite(burnable_frac_cell)
        & (burnable_frac_cell >= BURNABLE_GATE_FRAC)
    )

    # --- Terrain (DEM) ---
    dem = RasterSampler(fire.dem_tif)
    elevation = dem.sample_xy(XX, YY, fill=np.nan)
    elev_filled = np.where(np.isfinite(elevation), elevation, np.nanmedian(elevation))
    slope_deg, aspect_deg = compute_slope_aspect(elev_filled, grid.cell_size_m)
    half_2km = max(1, int(round(2000.0 / grid.cell_size_m)))
    elevation_rel = elevation - _local_mean(elevation, half_2km)

    return StaticLayers(
        grid=grid,
        fuel_class=fuel_class.astype(np.int64),
        burnable_frac_cell=burnable_frac_cell,
        burnable_frac_nearby=burnable_frac_nearby,
        burnable_gate=burnable_gate,
        in_fuel_bounds=in_fuel_bounds,
        elevation=elevation,
        slope_deg=slope_deg.astype(np.float64),
        aspect_deg=aspect_deg.astype(np.float64),
        elevation_rel=elevation_rel,
    )


__all__ = ["StaticLayers", "build_static_layers", "BURNABLE_GATE_FRAC", "NEARBY_RADIUS_M"]
