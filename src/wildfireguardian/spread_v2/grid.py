"""Coarse overpass-scale gridding for the spread_v2 ignition model.

The FIRMS detections, DEM and fuel raster live at fine resolution (10-30 m),
but the *prediction* problem is at the scale of a satellite overpass: "which
~0.5 km cells that are not yet burning will be detected as burning by the
next overpass?". This module:

1. Builds a regular grid in **EPSG:5179** (Korea 2000 / Unified TM, metres)
   over a fire's bounding box at a configurable cell size (default 500 m).
2. Reprojects the WGS84 DEM and fuel rasters onto that grid (elevation by
   bilinear average; *burnable fraction* by averaging a 0/1 burnable mask).
3. Projects FIRMS detections to grid cells and clusters their timestamps
   into discrete overpasses, yielding a cumulative observed-burned mask per
   overpass.

Everything downstream (feature building, the model, forward simulation, the
routing hazard) is expressed on this grid.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from pyproj import Transformer

KOREA_2000_UNIFIED = "EPSG:5179"
WGS84 = "EPSG:4326"
DEFAULT_CELL_M = 500.0

_to_5179 = Transformer.from_crs(WGS84, KOREA_2000_UNIFIED, always_xy=True)
_to_4326 = Transformer.from_crs(KOREA_2000_UNIFIED, WGS84, always_xy=True)


@dataclass(frozen=True)
class CoarseGrid:
    """A north-up regular grid in EPSG:5179 metres."""

    minx: float
    miny: float
    maxx: float
    maxy: float
    cell_size_m: float
    nrows: int
    ncols: int

    @property
    def transform(self):
        """rasterio/affine transform (north-up)."""
        from affine import Affine

        return Affine(self.cell_size_m, 0.0, self.minx, 0.0, -self.cell_size_m, self.maxy)

    def cell_of_xy(self, x: float, y: float) -> tuple[int, int] | None:
        """(row, col) of EPSG:5179 point, or ``None`` if outside the grid."""
        col = int((x - self.minx) // self.cell_size_m)
        row = int((self.maxy - y) // self.cell_size_m)
        if 0 <= row < self.nrows and 0 <= col < self.ncols:
            return row, col
        return None

    def center_xy(self, row: int, col: int) -> tuple[float, float]:
        """EPSG:5179 centre coordinate of cell (row, col)."""
        x = self.minx + (col + 0.5) * self.cell_size_m
        y = self.maxy - (row + 0.5) * self.cell_size_m
        return x, y

    def center_grids(self) -> tuple[np.ndarray, np.ndarray]:
        """(X, Y) meshgrids of cell-centre EPSG:5179 coordinates."""
        cols = np.arange(self.ncols)
        rows = np.arange(self.nrows)
        X = self.minx + (cols + 0.5) * self.cell_size_m
        Y = self.maxy - (rows + 0.5) * self.cell_size_m
        return np.meshgrid(X, Y)

    def center_lonlat(self) -> tuple[np.ndarray, np.ndarray]:
        """(lon, lat) meshgrids of cell centres (for plotting)."""
        X, Y = self.center_grids()
        lon, lat = _to_4326.transform(X, Y)
        return lon, lat


def build_grid(bbox_wgs84: tuple[float, float, float, float], cell_size_m: float = DEFAULT_CELL_M) -> CoarseGrid:
    """Build a :class:`CoarseGrid` covering a WGS84 bbox, in EPSG:5179."""
    minlon, minlat, maxlon, maxlat = bbox_wgs84
    xs, ys = _to_5179.transform(
        [minlon, maxlon, minlon, maxlon],
        [minlat, minlat, maxlat, maxlat],
    )
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    ncols = int(np.ceil((maxx - minx) / cell_size_m))
    nrows = int(np.ceil((maxy - miny) / cell_size_m))
    # Snap maxy/maxx so the transform exactly covers nrows/ncols cells.
    return CoarseGrid(
        minx=minx, miny=maxy - nrows * cell_size_m,
        maxx=minx + ncols * cell_size_m, maxy=maxy,
        cell_size_m=cell_size_m, nrows=nrows, ncols=ncols,
    )


def _reproject_raster(path, grid: CoarseGrid, *, resampling_name: str, src_nodata=None) -> np.ndarray:
    """Reproject a raster onto ``grid`` (EPSG:5179), returning a float array."""
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import reproject

    resampling = getattr(Resampling, resampling_name)
    with rasterio.open(path) as src:
        src_arr = src.read(1).astype("float64")
        src_crs = src.crs
        src_transform = src.transform
        if src_nodata is None:
            src_nodata = src.nodata
    dst = np.full((grid.nrows, grid.ncols), np.nan, dtype="float64")
    reproject(
        source=src_arr,
        destination=dst,
        src_transform=src_transform,
        src_crs=src_crs,
        dst_transform=grid.transform,
        dst_crs=KOREA_2000_UNIFIED,
        src_nodata=src_nodata,
        dst_nodata=np.nan,
        resampling=resampling,
    )
    return dst


def elevation_on_grid(event, grid: CoarseGrid) -> np.ndarray:
    """Mean elevation (m) per coarse cell, reprojected from the DEM."""
    return _reproject_raster(event.dem_path, grid, resampling_name="average")


def burnable_fraction_on_grid(event, grid: CoarseGrid) -> np.ndarray:
    """Fraction of each coarse cell that is burnable land cover (0-1).

    Reprojects a fine 0/1 burnable mask (from the WorldCover class codes via
    ``data_layers_manifest.json``) with averaging, so a coastal cell that is
    half sea gets ~0.5.
    """
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import reproject

    from .data import burnable_map

    bmap = burnable_map(event.data_dir)
    with rasterio.open(event.fuel_path) as src:
        codes = src.read(1)
        src_crs, src_transform = src.crs, src.transform
    burnable = np.zeros(codes.shape, dtype="float64")
    for code, b in bmap.items():
        if b:
            burnable[codes == code] = 1.0
    dst = np.full((grid.nrows, grid.ncols), np.nan, dtype="float64")
    reproject(
        source=burnable, destination=dst,
        src_transform=src_transform, src_crs=src_crs,
        dst_transform=grid.transform, dst_crs=KOREA_2000_UNIFIED,
        resampling=Resampling.average,
    )
    return np.clip(dst, 0.0, 1.0)


#: Elevation above which a cell is treated as LAND when splitting an uncovered
#: fuel strip into "the bbox includes sea" and "a fuel tile is missing". Sea
#: cells read nan or ~0 from the DEM; 5 m clears tidal noise without excluding
#: real low-lying land.
LAND_ELEV_MIN_M: float = 5.0


def fuel_coverage(event, grid: CoarseGrid) -> dict:
    """How much of ``grid`` the fuel raster actually covers, split sea vs land.

    WHY THIS EXISTS (Round-3 PHASE 13). ``burnable_fraction_on_grid`` reprojects
    the WorldCover mask onto the grid. Where the raster does not reach, the cell
    reads 0 — and :func:`wildfireguardian.spread_v2.features.build_transition_frame`
    uses ``burnable_frac > 0.05`` as a HARD CANDIDATE GATE, so such a cell is
    silently EXCLUDED from prediction rather than merely given a low feature
    value. Nothing raised and nothing logged.

    Found on ``miryang_2022``: ESA WorldCover tiles are 3 x 3 degrees, so a crop
    that fetched only ``N36E126`` stops dead at 129.000 E while that fire's
    analysis bbox runs to 129.05 E. The ``N36E129`` tile was never acquired.

    ⚠ THE SPLIT IS THE POINT. A plain uncovered-fraction reading is useless here
    because a coastal bbox is legitimately uncovered over the sea — ``gangneung_2023``
    is 17.61 % uncovered and 17.2 pp of that is the East Sea, which is correct.
    Crossing that with the DEM separates the two causes: uncovered LAND is the
    quantity a missing tile moves, and it is 0.00 % for every fire whose tiles
    were fully fetched.

    This is a MEASUREMENT and never raises. The gate that consumes it lives in
    ``scripts/run_forward_sim_region.py``, mirroring how ``dem.nodata_*_fraction``
    is enforced in ``scripts/run_multi_region_routing.py``.
    """
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import reproject

    with rasterio.open(event.fuel_path) as src:
        ones = np.ones(src.shape, dtype="float64")
        src_crs, src_transform = src.crs, src.transform
    present = np.full((grid.nrows, grid.ncols), np.nan, dtype="float64")
    reproject(
        source=ones, destination=present,
        src_transform=src_transform, src_crs=src_crs,
        dst_transform=grid.transform, dst_crs=KOREA_2000_UNIFIED,
        src_nodata=None, dst_nodata=np.nan,
        resampling=Resampling.average,
    )
    uncovered = ~np.isfinite(present)

    elev = elevation_on_grid(event, grid)
    land = np.isfinite(elev) & (elev > LAND_ELEV_MIN_M)
    uncovered_land = uncovered & land

    n = int(uncovered.size)
    return {
        "n_cells": n,
        "n_uncovered": int(uncovered.sum()),
        "frac_uncovered": float(uncovered.mean()),
        "n_uncovered_land": int(uncovered_land.sum()),
        "frac_uncovered_land": float(uncovered_land.mean()),
        "uncovered_land_km2": float(uncovered_land.sum()
                                    * (grid.cell_size_m / 1000.0) ** 2),
        "land_elev_min_m": LAND_ELEV_MIN_M,
        "fuel_path": str(event.fuel_path),
    }


def slope_deg(elevation: np.ndarray, cell_size_m: float) -> np.ndarray:
    """Slope (degrees) from a coarse DEM via central differences."""
    z = np.where(np.isfinite(elevation), elevation, np.nanmean(elevation))
    dzdy, dzdx = np.gradient(z, cell_size_m)
    return np.degrees(np.arctan(np.hypot(dzdx, dzdy)))


# ---------------------------------------------------------------------------
# Detections → cells → overpasses
# ---------------------------------------------------------------------------


@dataclass
class Overpass:
    """One discrete satellite overpass snapshot on the coarse grid."""

    index: int
    time: pd.Timestamp
    new_mask: np.ndarray            # cells first detected in THIS overpass
    cumulative_mask: np.ndarray     # cells detected at or before this overpass
    n_detections: int


def detections_to_cells(event, grid: CoarseGrid) -> pd.DataFrame:
    """Map detections to grid (row, col), dropping any outside the grid."""
    df = event.detections.copy()
    xs, ys = _to_5179.transform(df["longitude"].to_numpy(), df["latitude"].to_numpy())
    cols = np.floor((xs - grid.minx) / grid.cell_size_m).astype(int)
    rows = np.floor((grid.maxy - ys) / grid.cell_size_m).astype(int)
    inb = (rows >= 0) & (rows < grid.nrows) & (cols >= 0) & (cols < grid.ncols)
    out = df.loc[inb, ["time"]].copy()
    out["row"] = rows[inb]
    out["col"] = cols[inb]
    return out.reset_index(drop=True)


def cluster_overpasses(times: pd.Series, gap_minutes: float = 90.0) -> np.ndarray:
    """Group sorted detection times into overpass ids (gap-based clustering).

    A new overpass starts whenever the gap to the previous detection exceeds
    ``gap_minutes`` — FIRMS overpasses are near-instantaneous and separated by
    hours, so this cleanly recovers the distinct passes.
    """
    t = pd.to_datetime(times).sort_values().to_numpy()
    if len(t) == 0:
        return np.array([], dtype=int)
    gaps = np.diff(t).astype("timedelta64[s]").astype(float) / 60.0
    ids = np.zeros(len(t), dtype=int)
    ids[1:] = np.cumsum(gaps > gap_minutes)
    return ids


def overpass_snapshots(event, grid: CoarseGrid, *, gap_minutes: float = 90.0) -> list[Overpass]:
    """Build the cumulative observed-burned masks per overpass for a fire."""
    cells = detections_to_cells(event, grid)
    if cells.empty:
        return []
    cells = cells.sort_values("time").reset_index(drop=True)
    cells["op"] = cluster_overpasses(cells["time"], gap_minutes=gap_minutes)
    cumulative = np.zeros((grid.nrows, grid.ncols), dtype=bool)
    snaps: list[Overpass] = []
    for op_id, grp in cells.groupby("op"):
        new = np.zeros((grid.nrows, grid.ncols), dtype=bool)
        new[grp["row"].to_numpy(), grp["col"].to_numpy()] = True
        new_only = new & ~cumulative
        cumulative = cumulative | new
        snaps.append(Overpass(
            index=int(op_id),
            time=pd.Timestamp(grp["time"].max()),
            new_mask=new_only.copy(),
            cumulative_mask=cumulative.copy(),
            n_detections=int(len(grp)),
        ))
    return snaps


__all__ = [
    "CoarseGrid",
    "Overpass",
    "KOREA_2000_UNIFIED",
    "WGS84",
    "DEFAULT_CELL_M",
    "build_grid",
    "elevation_on_grid",
    "burnable_fraction_on_grid",
    "slope_deg",
    "detections_to_cells",
    "cluster_overpasses",
    "overpass_snapshots",
]
