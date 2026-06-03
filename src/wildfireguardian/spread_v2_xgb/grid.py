"""The 375 m EPSG:5179 analysis grid and orientation-safe raster sampler.

This module is where the **uljin orientation bug** is fixed for good.

Background
----------
The prior v2 run lost ~85 % of uljin_samcheok_2022's true ignitions because
it built a candidate boolean mask in grid space (row 0 = south, "bottom-up")
and AND-ed it with a burnable mask read straight off the fuel GeoTIFF
(row 0 = north, "top-down"). The two arrays were vertically mirrored, so the
burnable gate was applied to the wrong cells — catastrophic for uljin, a tall
N–S burn corridor where vertical mirroring maximally misaligns.

The fix is structural, not a flag: **every per-cell quantity — including the
burnable gate — is sampled through one transform-aware function**
(:class:`RasterSampler`). A grid cell's EPSG:5179 centre is reprojected to the
raster's own CRS and converted to (row, col) via the raster's affine
transform. rasterio's affine encodes the north-up orientation, so the row
direction is always correct. There are no two masks to mis-AND.

The grid itself is built from a :class:`RegionConfig` (the project's single
source of truth for geometry) at 375 m in EPSG:5179 (Korea 2000 / Unified TM,
the Korean operational CRS), matching the documented v2 methodology.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import rasterio
from pyproj import Transformer

from ..utils.regions import KOREA_2000_UNIFIED, WGS84, RegionConfig

CELL_SIZE_M: float = 375.0


@dataclass
class Grid:
    """A regular 375 m EPSG:5179 grid covering a region's bbox.

    Row 0 is the NORTH edge (max y); column 0 is the WEST edge (min x) — the
    conventional north-up raster orientation. ``cell (i, j)`` has its centre at
    ``(minx + (j+0.5)*cs, maxy - (i+0.5)*cs)`` in EPSG:5179.
    """

    region: RegionConfig
    cell_size_m: float = CELL_SIZE_M

    def __post_init__(self) -> None:
        self.nrows, self.ncols = self.region.grid_dims(self.cell_size_m)
        minx, miny, maxx, maxy = self.region.bbox_epsg5179
        self.minx, self.miny, self.maxx, self.maxy = minx, miny, maxx, maxy
        # Cell-centre coordinate vectors (EPSG:5179 metres).
        self.x_centers = minx + (np.arange(self.ncols) + 0.5) * self.cell_size_m
        self.y_centers = maxy - (np.arange(self.nrows) + 0.5) * self.cell_size_m

    @property
    def shape(self) -> tuple[int, int]:
        return (self.nrows, self.ncols)

    @property
    def cell_area_m2(self) -> float:
        return self.cell_size_m * self.cell_size_m

    def center_mesh(self) -> tuple[np.ndarray, np.ndarray]:
        """Return (XX, YY) EPSG:5179 cell-centre coordinate meshes, shape (nrows, ncols)."""
        return np.meshgrid(self.x_centers, self.y_centers)

    def centers_lonlat(self) -> tuple[np.ndarray, np.ndarray]:
        """Return (lon, lat) WGS84 meshes of cell centres, shape (nrows, ncols)."""
        XX, YY = self.center_mesh()
        tr = Transformer.from_crs(KOREA_2000_UNIFIED, WGS84, always_xy=True)
        lon, lat = tr.transform(XX, YY)
        return np.asarray(lon), np.asarray(lat)

    def lonlat_to_rowcol(self, lon, lat) -> tuple[np.ndarray, np.ndarray]:
        """Map WGS84 (lon, lat) to fractional grid (row, col).

        Returns float row/col; callers round + bounds-check. Cells outside the
        grid yield out-of-range indices (caller must mask).
        """
        tr = Transformer.from_crs(WGS84, KOREA_2000_UNIFIED, always_xy=True)
        x, y = tr.transform(np.asarray(lon), np.asarray(lat))
        col = (np.asarray(x) - self.minx) / self.cell_size_m - 0.5
        row = (self.maxy - np.asarray(y)) / self.cell_size_m - 0.5
        return row, col

    def assign_cells(self, lon, lat) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Snap WGS84 points to integer grid (row, col); return (row, col, inside).

        ``inside`` is a boolean array flagging points that land within grid bounds.
        """
        row_f, col_f = self.lonlat_to_rowcol(lon, lat)
        row = np.round(row_f).astype(np.int64)
        col = np.round(col_f).astype(np.int64)
        inside = (row >= 0) & (row < self.nrows) & (col >= 0) & (col < self.ncols)
        return row, col, inside


class RasterSampler:
    """Orientation-safe point/window sampler over a single raster.

    The raster is read fully into memory once (fuel ~43 MB uint8, DEM ~15 MB
    float32 — both fine). Sampling reprojects EPSG:5179 query points to the
    raster CRS and uses the raster's *own* affine transform to get (row, col),
    so the north-up orientation is handled by the geotransform — never by a
    hand-built mask. This is the single sampler the whole feature pipeline and
    the burnable gate flow through.
    """

    def __init__(self, path) -> None:
        with rasterio.open(path) as r:
            self.array = r.read(1)
            self.transform = r.transform
            self.crs = r.crs
            self.nodata = r.nodata
            self.height = r.height
            self.width = r.width
        self._inv = ~self.transform
        # Transformer from the analysis CRS (5179) to the raster CRS.
        self._to_raster = Transformer.from_crs(
            KOREA_2000_UNIFIED, self.crs, always_xy=True
        )

    def _xy5179_to_rowcol(self, x5179, y5179) -> tuple[np.ndarray, np.ndarray]:
        rx, ry = self._to_raster.transform(np.asarray(x5179), np.asarray(y5179))
        # Affine inverse: (col, row) = ~transform * (x, y). rasterio rounds via floor.
        col_f, row_f = self._inv * (np.asarray(rx), np.asarray(ry))
        return np.asarray(row_f), np.asarray(col_f)

    def sample_xy(self, x5179, y5179, fill=np.nan) -> np.ndarray:
        """Nearest-pixel sample at EPSG:5179 points. Out-of-bounds/nodata → fill."""
        row_f, col_f = self._xy5179_to_rowcol(x5179, y5179)
        row = np.floor(row_f).astype(np.int64)
        col = np.floor(col_f).astype(np.int64)
        inside = (row >= 0) & (row < self.height) & (col >= 0) & (col < self.width)
        out = np.full(row.shape, fill, dtype=np.float64)
        rr, cc = row[inside], col[inside]
        vals = self.array[rr, cc].astype(np.float64)
        if self.nodata is not None:
            vals = np.where(vals == float(self.nodata), fill, vals)
        out[inside] = vals
        return out

    def integral_image(self, predicate_array: np.ndarray) -> np.ndarray:
        """Summed-area table of a 0/1 predicate array (for O(1) window fractions)."""
        ii = predicate_array.astype(np.float64).cumsum(0).cumsum(1)
        return np.pad(ii, ((1, 0), (1, 0)), mode="constant")

    def window_fraction(
        self, x5179, y5179, half_window_px: int, integral: np.ndarray
    ) -> np.ndarray:
        """Fraction of predicate-true pixels in a square window centred on each point.

        ``integral`` must be the summed-area table from :meth:`integral_image`
        of the desired 0/1 predicate over this raster. Window is
        ``(2*half+1)`` pixels on a side, clipped to the raster. Out-of-bounds
        centres return NaN.
        """
        row_f, col_f = self._xy5179_to_rowcol(x5179, y5179)
        rc = np.floor(row_f).astype(np.int64)
        cc = np.floor(col_f).astype(np.int64)
        inside = (rc >= 0) & (rc < self.height) & (cc >= 0) & (cc < self.width)
        h = int(half_window_px)
        r0 = np.clip(rc - h, 0, self.height)
        r1 = np.clip(rc + h + 1, 0, self.height)
        c0 = np.clip(cc - h, 0, self.width)
        c1 = np.clip(cc + h + 1, 0, self.width)
        total = (
            integral[r1, c1] - integral[r0, c1] - integral[r1, c0] + integral[r0, c0]
        )
        npix = (r1 - r0) * (c1 - c0)
        out = np.full(rc.shape, np.nan, dtype=np.float64)
        ok = inside & (npix > 0)
        out[ok] = total[ok] / npix[ok]
        return out

    def resolution_m(self) -> float:
        """Approximate native pixel size in metres (for window sizing).

        For a geographic (degree) raster the y-pixel size in degrees is
        converted at ~111.32 km/deg latitude; for a projected raster the
        transform is already metric so |transform.e| is returned directly.
        """
        if self.crs and self.crs.is_geographic:
            return abs(self.transform.e) * 111_320.0  # deg-latitude → m
        return abs(self.transform.e)


def build_region(fire) -> RegionConfig:
    """Build a :class:`RegionConfig` from a fire's manifest WGS84 bbox.

    Uses the bbox from the data manifest (the footprint the rasters were
    fetched to), NOT the slightly different presets in ``utils.regions``, so
    the grid lines up exactly with the v2 data layers.
    """
    return RegionConfig.from_wgs84_bbox(
        name=fire.fire_id,
        bbox_wgs84=tuple(fire.bbox_wgs84),
        name_kr=fire.name_kr,
        event_date_range=(fire.start, fire.end),
    )


__all__ = ["Grid", "RasterSampler", "build_region", "CELL_SIZE_M"]
