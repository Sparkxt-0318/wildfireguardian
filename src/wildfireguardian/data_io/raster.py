"""Raster ingestion: DEM, fuel-type, and landcover loaders.

This module is the place where geographic raster data enters the
WildfireGuardian pipeline. All loaders share a common contract:

- Input: a :class:`RegionConfig` and a ``source`` selector.
- Output: an :class:`xarray.DataArray` with:
    * dims ``('y', 'x')``
    * the EPSG:5179 affine transform attached as ``rio_transform`` attr
    * the CRS attached as ``rio_crs`` attr  (string "EPSG:5179")
    * cell size matching ``cell_size_m``
- Side effect: cached to ``data/cache/`` keyed by ``(region.name, source, cell_size)``.

For Session 3, SRTM 30 m ingestion is implemented (real NASA SRTMGL1
.hgt tiles via the AWS Mapzen archive); NGII Korean DEM and KFS 임상도
are still stubbed with clear acquisition instructions. Synthetic
fallback paths are preserved and clearly labelled in xarray attrs.

Data sources and acquisition
----------------------------

See ``docs/data_sources.md`` for the canonical access process. Quick
summary:

- **DEM (SRTM)**: NASA SRTMGL1 1-arc-second (~30 m) global. Free, no
  registration. Tiles are 1° × 1° lat/lon .hgt files; we auto-download
  from the AWS Mapzen archive (``elevation-tiles-prod.s3.amazonaws.com``)
  the first time a region needs them. Cached locally under
  ``data/raw/dem/srtm/``.
- **DEM (NGII)**: 국토지리정보원 1:5000 digital map. Requires Korean
  registration; place files under ``data/raw/dem/ngii/`` and run with
  ``source='ngii'``.
- **Fuel type (KFS 임상도)**: Korean Forest Service forest type map v1.4.
  Requires Korean registration at https://map.forest.go.kr.
- **Landcover (ME 토지피복지도)**: Ministry of Environment Korea.
"""

from __future__ import annotations

import gzip
import hashlib
import logging
import math
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Literal

import numpy as np
import xarray as xr
from pyproj import Transformer

from ..utils.regions import KOREA_2000_UNIFIED, WGS84, RegionConfig

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------


def _project_root() -> Path:
    """Locate the repository root (3 levels up from this file)."""
    return Path(__file__).resolve().parents[3]


def _cache_dir() -> Path:
    p = _project_root() / "data" / "cache"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _cache_key(region_name: str, source: str, cell_size_m: float, kind: str) -> str:
    """Compute a stable cache filename."""
    raw = f"{kind}_{region_name}_{source}_{cell_size_m:.1f}"
    h = hashlib.sha256(raw.encode()).hexdigest()[:10]
    return f"{kind}_{region_name}_{source}_{int(cell_size_m)}m_{h}.nc"


def _cache_get(key: str) -> xr.DataArray | None:
    """Return a cached DataArray if present, else None."""
    path = _cache_dir() / key
    if not path.exists():
        return None
    try:
        ds = xr.open_dataset(path)
        # Convention: the cached DataArray is stored under its name.
        if len(ds.data_vars) != 1:
            _logger.warning("cache file %s has unexpected layout; ignoring", path)
            return None
        name = list(ds.data_vars)[0]
        arr = ds[name].load()
        return arr
    except Exception as exc:  # corrupt cache or schema change
        _logger.warning("could not read cache %s (%s); regenerating", path, exc)
        return None


def _cache_put(arr: xr.DataArray, key: str) -> None:
    """Persist a DataArray to cache."""
    path = _cache_dir() / key
    arr.to_dataset(name=arr.name or "data").to_netcdf(path)


def clear_cache() -> int:
    """Remove all cached rasters. Returns count removed."""
    n = 0
    for p in _cache_dir().glob("*.nc"):
        p.unlink()
        n += 1
    return n


# ---------------------------------------------------------------------------
# Region → xarray geometry
# ---------------------------------------------------------------------------


def _build_geometry(region: RegionConfig, cell_size_m: float) -> tuple[np.ndarray, np.ndarray, tuple[float, ...]]:
    """Return (y_coords, x_coords, affine_transform) for the EPSG:5179 grid."""
    nrows, ncols = region.grid_dims(cell_size_m)
    minx, _miny, _maxx, maxy = region.bbox_epsg5179
    # Cell centres.
    x = minx + (np.arange(ncols) + 0.5) * cell_size_m
    y = maxy - (np.arange(nrows) + 0.5) * cell_size_m
    affine = region.affine_transform(cell_size_m)
    return y, x, affine


def _wrap_array(
    arr: np.ndarray, region: RegionConfig, cell_size_m: float,
    name: str, attrs: dict | None = None,
) -> xr.DataArray:
    """Bundle a 2-D numpy array into an xarray DataArray with CRS metadata."""
    y, x, affine = _build_geometry(region, cell_size_m)
    if arr.shape != (len(y), len(x)):
        raise ValueError(
            f"array shape {arr.shape} != expected ({len(y)}, {len(x)})"
        )
    return xr.DataArray(
        arr, dims=("y", "x"),
        coords={"y": y, "x": x},
        name=name,
        attrs={
            "rio_crs": KOREA_2000_UNIFIED,
            "rio_transform": list(affine),
            "region_name": region.name,
            "cell_size_m": float(cell_size_m),
            **(attrs or {}),
        },
    )


# ---------------------------------------------------------------------------
# Synthetic generators
# ---------------------------------------------------------------------------


def _synthetic_dem(region: RegionConfig, cell_size_m: float) -> np.ndarray:
    """Build a plausible Korean mountainous DEM (synthetic).

    Construction:
    - Base elevation: 200 m at the coast, rising inland.
    - Coastal proxy: distance from the east edge of the EPSG:5179 bbox.
    - Ridge undulation: sinusoidal N-S undulation with ~ 1 km wavelength.

    Result: smooth, defensible mountainous terrain in the 200-1000 m range
    that the slope/aspect operators can chew on. Marked as synthetic via
    the returned DataArray's attrs.
    """
    nrows, ncols = region.grid_dims(cell_size_m)
    ii, jj = np.meshgrid(np.arange(nrows), np.arange(ncols), indexing="ij")
    # In our EPSG:5179 grid, x increases east (j) and y decreases south (i).
    # "Distance from east edge" ~ proportional to (ncols - 1 - j).
    coast_distance = (ncols - 1 - jj) / max(1, ncols - 1)   # 0 at east, 1 at west
    base = 200.0 + 800.0 * coast_distance
    undulation = 60.0 * np.sin(2.0 * np.pi * ii * cell_size_m / 1000.0)
    return (base + undulation).astype(np.float32)


def _synthetic_fuel_raster(
    region: RegionConfig, cell_size_m: float, fill_code: int = 1,
) -> np.ndarray:
    """Build a synthetic fuel-type raster filled with the Korean Pinus code.

    Uses integer codes 0..N where 0 is "non-fuel" (water / urban / barren)
    and 1 is "Korean Pinus densiflora" (KP_PINE). Real KFS 임상도 ingestion
    will produce a richer code set.
    """
    nrows, ncols = region.grid_dims(cell_size_m)
    arr = np.full((nrows, ncols), fill_code, dtype=np.int16)
    return arr


def _synthetic_landcover(region: RegionConfig, cell_size_m: float) -> np.ndarray:
    """Synthetic landcover: all "forest" (code 3) for the Pinus belt."""
    nrows, ncols = region.grid_dims(cell_size_m)
    return np.full((nrows, ncols), 3, dtype=np.int16)


# ---------------------------------------------------------------------------
# SRTM .hgt loader (NASA SRTMGL1 30 m, via AWS Mapzen archive)
# ---------------------------------------------------------------------------
#
# The AWS Mapzen archive (https://github.com/tilezen/joerd) re-hosts NASA
# SRTM as 1° × 1° .hgt.gz tiles at the URL pattern
#
#   https://elevation-tiles-prod.s3.amazonaws.com/skadi/N{lat}/N{lat}E{lon}.hgt.gz
#
# Tiles are SRTMGL1 (1-arc-second, 3601 × 3601 int16 big-endian), nodata
# represented as -32768. Negative non-nodata values are bathymetry; for
# fire spread we clip these to 0 (sea surface).

_SRTM_DIM: int = 3601
_SRTM_NODATA: int = -32768
_SRTM_TILE_URL_TEMPLATE: str = (
    "https://elevation-tiles-prod.s3.amazonaws.com/skadi/"
    "{ns}{lat:02d}/{ns}{lat:02d}{ew}{lon:03d}.hgt.gz"
)


def _srtm_cache_dir() -> Path:
    p = _project_root() / "data" / "raw" / "dem" / "srtm"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _srtm_tile_name(lat_int: int, lon_int: int) -> str:
    """Canonical .hgt filename for an integer-degree corner.

    The (lat_int, lon_int) corner is the **southwest** corner of the
    tile, per the SRTM convention. Returns ``"N36E129.hgt"`` etc.
    """
    ns = "N" if lat_int >= 0 else "S"
    ew = "E" if lon_int >= 0 else "W"
    return f"{ns}{abs(lat_int):02d}{ew}{abs(lon_int):03d}.hgt"


def _srtm_tile_url(lat_int: int, lon_int: int) -> str:
    ns = "N" if lat_int >= 0 else "S"
    ew = "E" if lon_int >= 0 else "W"
    return _SRTM_TILE_URL_TEMPLATE.format(
        ns=ns, ew=ew, lat=abs(lat_int), lon=abs(lon_int),
    )


def _download_srtm_tile(lat_int: int, lon_int: int, timeout_s: float = 60.0) -> Path:
    """Download an SRTM .hgt tile to the local cache; return its path.

    If the tile is already cached, returns the cache path immediately. If
    network access is unavailable or the tile is missing on the server,
    raises ``FileNotFoundError`` so the caller can fall back to synthetic.
    """
    cache = _srtm_cache_dir()
    name = _srtm_tile_name(lat_int, lon_int)
    final = cache / name
    if final.exists():
        return final
    gz_path = cache / (name + ".gz")
    if not gz_path.exists():
        url = _srtm_tile_url(lat_int, lon_int)
        _logger.info("downloading SRTM tile %s from %s", name, url)
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "wildfireguardian/0.1"},
            )
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                gz_path.write_bytes(resp.read())
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise FileNotFoundError(
                f"could not download SRTM tile {name} from {url}: {exc}"
            ) from exc
    # gunzip → final
    with gzip.open(gz_path, "rb") as fin:
        final.write_bytes(fin.read())
    return final


def _read_srtm_hgt(path: Path) -> np.ndarray:
    """Read an SRTMGL1 .hgt file and return a 3601 × 3601 int16 array.

    Row 0 corresponds to the **top** of the tile (max latitude); column 0
    corresponds to the **left** of the tile (min longitude).
    """
    raw = path.read_bytes()
    expected = _SRTM_DIM * _SRTM_DIM * 2
    if len(raw) != expected:
        raise ValueError(
            f"SRTM tile {path.name} has unexpected size {len(raw)} "
            f"(expected {expected} for SRTMGL1)"
        )
    return np.frombuffer(raw, dtype=">i2").reshape(_SRTM_DIM, _SRTM_DIM)


def _srtm_tiles_covering(
    bbox_wgs84: tuple[float, float, float, float],
) -> list[tuple[int, int]]:
    """Return integer-degree (lat_int, lon_int) corners covering the bbox.

    Each tile's SW corner is (lat_int, lon_int); the tile covers
    [lat_int, lat_int+1] × [lon_int, lon_int+1] in WGS84.
    """
    minlon, minlat, maxlon, maxlat = bbox_wgs84
    lat0 = int(math.floor(minlat))
    lat1 = int(math.floor(maxlat - 1e-9))
    lon0 = int(math.floor(minlon))
    lon1 = int(math.floor(maxlon - 1e-9))
    return [
        (lat, lon)
        for lat in range(lat0, lat1 + 1)
        for lon in range(lon0, lon1 + 1)
    ]


def _srtm_dem_for_region(
    region: RegionConfig, cell_size_m: float, allow_download: bool = True,
) -> np.ndarray:
    """Build an EPSG:5179-aligned DEM for ``region`` from SRTM .hgt tiles.

    Algorithm:
    1. Find all SRTM tiles covering the region's WGS84 bbox.
    2. Read each as a (3601, 3601) array, clipping nodata to 0 and
       bathymetry (negative non-nodata) to 0 (sea surface).
    3. For each output grid cell, compute its WGS84 (lon, lat) center,
       look up the corresponding SRTM cell via nearest-neighbour.

    For the Yeongdeok bbox (one tile, 30 m native), this is essentially a
    high-quality nearest-neighbour resample to EPSG:5179. We deliberately
    use nearest rather than bilinear so that slope/aspect from
    np.gradient remain sharp; bilinear would smooth slopes by ~30 %.

    Raises FileNotFoundError if a needed tile cannot be obtained.
    """
    tiles_needed = _srtm_tiles_covering(region.bbox_wgs84)

    # Pre-load all needed tiles into memory (each ~ 25 MB).
    tile_data: dict[tuple[int, int], np.ndarray] = {}
    for lat_i, lon_i in tiles_needed:
        cache = _srtm_cache_dir()
        path = cache / _srtm_tile_name(lat_i, lon_i)
        if not path.exists():
            if not allow_download:
                raise FileNotFoundError(
                    f"SRTM tile {path.name} not in cache and download disabled"
                )
            path = _download_srtm_tile(lat_i, lon_i)
        arr = _read_srtm_hgt(path)
        # Clip nodata + bathymetry to 0 (sea surface).
        arr = arr.astype(np.int32)
        arr[arr == _SRTM_NODATA] = 0
        arr[arr < 0] = 0
        tile_data[(lat_i, lon_i)] = arr

    # Build the output EPSG:5179 grid.
    nrows, ncols = region.grid_dims(cell_size_m)
    minx, _miny, _maxx, maxy = region.bbox_epsg5179
    cs = cell_size_m

    # Output cell-centre coords in EPSG:5179.
    js = np.arange(ncols)
    is_ = np.arange(nrows)
    xs = minx + (js + 0.5) * cs              # shape (ncols,)
    ys = maxy - (is_ + 0.5) * cs             # shape (nrows,)
    XX, YY = np.meshgrid(xs, ys)             # shapes (nrows, ncols)

    # Bulk-reproject EPSG:5179 → WGS84.
    to_wgs = Transformer.from_crs(KOREA_2000_UNIFIED, WGS84, always_xy=True)
    lon_grid, lat_grid = to_wgs.transform(XX, YY)

    out = np.zeros((nrows, ncols), dtype=np.float32)
    # For each tile, find the output cells whose (lat, lon) falls inside it.
    for (lat_i, lon_i), arr in tile_data.items():
        in_tile = (
            (lon_grid >= lon_i) & (lon_grid < lon_i + 1)
            & (lat_grid >= lat_i) & (lat_grid < lat_i + 1)
        )
        if not in_tile.any():
            continue
        # Local (row, col) inside the SRTM tile.
        # Row 0 = top (lat_i + 1); within tile, lat goes from (lat_i + 1) → lat_i.
        # Column 0 = left (lon_i); lon goes lon_i → (lon_i + 1).
        local_lat = lat_grid[in_tile]
        local_lon = lon_grid[in_tile]
        srtm_row = ((lat_i + 1.0 - local_lat) * (_SRTM_DIM - 1)).astype(np.int32)
        srtm_col = ((local_lon - lon_i) * (_SRTM_DIM - 1)).astype(np.int32)
        np.clip(srtm_row, 0, _SRTM_DIM - 1, out=srtm_row)
        np.clip(srtm_col, 0, _SRTM_DIM - 1, out=srtm_col)
        out[in_tile] = arr[srtm_row, srtm_col].astype(np.float32)

    return out


def compute_slope_aspect(dem: np.ndarray, cell_size_m: float) -> tuple[np.ndarray, np.ndarray]:
    """Compute slope (degrees) and aspect (degrees, 0 = N, clockwise) from a DEM.

    Uses np.gradient — the standard central-difference approximation,
    equivalent at interior cells to Horn (1981) eq. 14–15 with a 3 × 3
    kernel for sufficiently smooth terrain (this is what GRASS r.slope.aspect
    and rasterio's slope tool fall back to for the gradient method).

    For SRTM 30 m terrain, central-difference is the appropriate choice;
    Zevenbergen-Thorne is for finer DEMs.

    Reference: Horn, B.K.P. (1981). *Hill shading and the reflectance map.*
    Proc. IEEE 69(1): 14-47.
    """
    dz_di, dz_dj = np.gradient(dem.astype(np.float32), cell_size_m, cell_size_m)
    slope_rad = np.arctan(np.hypot(dz_di, dz_dj))
    slope_deg = np.degrees(slope_rad).astype(np.float32)
    # Aspect: compass bearing of the downslope direction.
    # Gradient points in the direction of steepest ASCENT; downslope = -gradient.
    # In array coords, di > 0 is south (lat decreases), dj > 0 is east.
    # Downslope vector = (-dz_di, -dz_dj); its compass bearing (N=0, clockwise) is
    #   atan2(east-component, north-component) = atan2(-dz_dj, dz_di)
    aspect_deg = (np.degrees(np.arctan2(-dz_dj, dz_di)) + 360.0) % 360.0
    aspect_deg = aspect_deg.astype(np.float32)
    return slope_deg, aspect_deg


# ---------------------------------------------------------------------------
# Public loaders
# ---------------------------------------------------------------------------

DemSource = Literal["auto", "synthetic", "srtm", "ngii"]


def load_dem(
    region: RegionConfig,
    *,
    source: DemSource = "auto",
    cell_size_m: float = 30.0,
    use_cache: bool = True,
) -> xr.DataArray:
    """Load a Digital Elevation Model for a region in EPSG:5179.

    Parameters
    ----------
    region : RegionConfig
        Which region to load DEM for.
    source : str
        - ``"synthetic"``: synthesise a plausible Korean mountainous DEM.
        - ``"srtm"``: load SRTM 30 m global DEM from ``data/raw/dem/srtm/``
          (Session 3 — currently raises NotImplementedError).
        - ``"ngii"``: load NGII 1:5000 Korean digital map from
          ``data/raw/dem/ngii/`` (Session 3 — currently raises NotImplementedError).
        - ``"auto"``: try ngii → srtm → synthetic in order.
    cell_size_m : float, default 30.0
        Target resolution in metres.
    use_cache : bool, default True
        If True, look up ``data/cache/`` before computing.

    Returns
    -------
    xarray.DataArray
        DEM in metres, dims ``('y', 'x')``, with CRS / affine attrs.
    """
    if source == "auto":
        for candidate in ("ngii", "srtm", "synthetic"):
            try:
                return load_dem(region, source=candidate,  # type: ignore[arg-type]
                                cell_size_m=cell_size_m, use_cache=use_cache)
            except NotImplementedError:
                continue
        raise RuntimeError("no DEM source available")

    key = _cache_key(region.name, source, cell_size_m, "dem")
    if use_cache:
        cached = _cache_get(key)
        if cached is not None:
            return cached

    if source == "synthetic":
        arr = _synthetic_dem(region, cell_size_m)
        out = _wrap_array(
            arr, region, cell_size_m, name="dem",
            attrs={
                "units": "m", "source": "synthetic", "synthetic": True,
                "provenance": (
                    "SYNTHETIC — not derived from real elevation data. "
                    "Mountainous-Korean-coast-like topography for "
                    "demonstrations; NOT for scientific claims."
                ),
            },
        )
    elif source == "srtm":
        arr = _srtm_dem_for_region(region, cell_size_m, allow_download=True)
        out = _wrap_array(
            arr, region, cell_size_m, name="dem",
            attrs={
                "units": "m", "source": "srtm",
                "synthetic": False,
                "provenance": (
                    "NASA SRTMGL1 (1-arc-second, ~30 m) via the AWS Mapzen "
                    "archive (elevation-tiles-prod.s3.amazonaws.com). "
                    "Nodata and bathymetry clipped to 0 (sea surface). "
                    "Resampled to EPSG:5179 by nearest-neighbour."
                ),
                "citation": (
                    "NASA JPL (2013). NASA Shuttle Radar Topography Mission "
                    "Global 1 arc second [SRTMGL1] V003. NASA EOSDIS Land "
                    "Processes DAAC. doi:10.5067/MEaSUREs/SRTM/SRTMGL1.003"
                ),
            },
        )
    elif source == "ngii":
        raise NotImplementedError(
            "NGII DEM ingestion is a Session 3 task. Requires Korean NGII "
            "registration; place files under data/raw/dem/ngii/. See "
            "docs/data_sources.md for the access process."
        )
    else:
        raise ValueError(f"unknown DEM source {source!r}")

    if use_cache:
        _cache_put(out, key)
    return out


FuelSource = Literal["auto", "synthetic", "kfs_impsangdo"]


def load_fuel_type(
    region: RegionConfig,
    *,
    source: FuelSource = "auto",
    cell_size_m: float = 30.0,
    use_cache: bool = True,
) -> xr.DataArray:
    """Load a fuel-type raster for a region.

    Returned codes:
    - 0: non-fuel (water, urban, barren)
    - 1: Korean Pinus densiflora (KP_PINE) — surrogate for any fire-prone
         conifer dominated stand
    - 2: hardwood / mixed (FM9 / FM10 analog)
    - 3: grass / herbaceous (FM1 analog)
    - 4: agriculture (light fuel)

    The synthetic source returns code 1 (KP_PINE) everywhere; real KFS
    임상도 ingestion will return the realistic code mix.

    Session 3 will resolve fuel-type codes → fuel-model instances via a
    lookup that lives alongside this module.
    """
    if source == "auto":
        for candidate in ("kfs_impsangdo", "synthetic"):
            try:
                return load_fuel_type(region, source=candidate,  # type: ignore[arg-type]
                                       cell_size_m=cell_size_m, use_cache=use_cache)
            except NotImplementedError:
                continue
        raise RuntimeError("no fuel-type source available")

    key = _cache_key(region.name, source, cell_size_m, "fuel")
    if use_cache:
        cached = _cache_get(key)
        if cached is not None:
            return cached

    if source == "synthetic":
        arr = _synthetic_fuel_raster(region, cell_size_m, fill_code=1)
        out = _wrap_array(
            arr, region, cell_size_m, name="fuel_type",
            attrs={
                "source": "synthetic", "synthetic": True,
                "legend": "0=non-fuel, 1=KP_PINE, 2=hardwood, 3=grass, 4=agriculture",
            },
        )
    elif source == "kfs_impsangdo":
        raise NotImplementedError(
            "KFS 임상도 ingestion is a Session 3 task. Place 임상도 v1.4 "
            "files under data/raw/fuel/kfs_impsangdo/ and implement the "
            "vector-to-raster rasterisation here. See "
            "docs/data_sources.md for access details."
        )
    else:
        raise ValueError(f"unknown fuel-type source {source!r}")

    if use_cache:
        _cache_put(out, key)
    return out


LandcoverSource = Literal["auto", "synthetic", "me_korea"]


def load_landcover(
    region: RegionConfig,
    *,
    source: LandcoverSource = "auto",
    cell_size_m: float = 30.0,
    use_cache: bool = True,
) -> xr.DataArray:
    """Load landcover raster for a region.

    Returned codes follow the ME 토지피복 v3 1-digit scheme:
    1=urban, 2=agriculture, 3=forest, 4=grass, 5=wetland, 6=barren, 7=water.

    Synthetic returns ``3`` (forest) everywhere — suitable for the Pinus
    belt; ME ingestion is Session 3.
    """
    if source == "auto":
        for candidate in ("me_korea", "synthetic"):
            try:
                return load_landcover(region, source=candidate,  # type: ignore[arg-type]
                                       cell_size_m=cell_size_m, use_cache=use_cache)
            except NotImplementedError:
                continue
        raise RuntimeError("no landcover source available")

    key = _cache_key(region.name, source, cell_size_m, "landcover")
    if use_cache:
        cached = _cache_get(key)
        if cached is not None:
            return cached

    if source == "synthetic":
        arr = _synthetic_landcover(region, cell_size_m)
        out = _wrap_array(
            arr, region, cell_size_m, name="landcover",
            attrs={
                "source": "synthetic", "synthetic": True,
                "legend": "1=urban,2=agri,3=forest,4=grass,5=wetland,6=barren,7=water",
            },
        )
    elif source == "me_korea":
        raise NotImplementedError(
            "ME 토지피복 ingestion is a Session 3 task. Place files under "
            "data/raw/landcover/me/ and implement the parse+reproject here. "
            "See docs/data_sources.md."
        )
    else:
        raise ValueError(f"unknown landcover source {source!r}")

    if use_cache:
        _cache_put(out, key)
    return out


# ---------------------------------------------------------------------------
# Convenience: pack rasters onto an existing FireGrid
# ---------------------------------------------------------------------------


def populate_firegrid(grid, dem: xr.DataArray, fuel_type: xr.DataArray | None = None,
                     fuel_code_to_model: dict | None = None) -> None:
    """Copy DEM and fuel-type rasters into a :class:`FireGrid` instance.

    The DEM's slope and aspect are computed from the DEM gradient. If a
    fuel-type code → fuel-model lookup is provided, the grid's
    ``fuel_model_id`` is populated. Otherwise the default (KP_PINE) is
    used everywhere.
    """
    if dem.shape != (grid.nrows, grid.ncols):
        raise ValueError(
            f"DEM shape {dem.shape} doesn't match grid {(grid.nrows, grid.ncols)}"
        )
    grid.elevation_m[:] = dem.values.astype(np.float32)
    slope, aspect = compute_slope_aspect(dem.values, grid.cell_size_m)
    grid.slope_degrees[:] = slope
    grid.aspect_degrees[:] = aspect

    if fuel_type is not None and fuel_code_to_model is not None:
        if fuel_type.shape != (grid.nrows, grid.ncols):
            raise ValueError("fuel_type raster shape mismatch")
        # Build an object-array of fuel models by code lookup.
        ft = fuel_type.values
        for code, model in fuel_code_to_model.items():
            grid.fuel_model_id[ft == code] = model


__all__ = [
    "DemSource",
    "FuelSource",
    "LandcoverSource",
    "load_dem",
    "load_fuel_type",
    "load_landcover",
    "populate_firegrid",
    "compute_slope_aspect",
    "clear_cache",
]
