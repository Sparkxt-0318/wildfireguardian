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

For Session 2, real-data ingestion paths (NGII DEM, KFS 임상도) are
stubbed out with clear TODO markers and acquisition instructions; the
synthetic paths produce sensible defaults so the entire pipeline can be
exercised end-to-end without external dependencies.

Data sources and acquisition
----------------------------

See ``docs/data_sources.md`` for the canonical access process. A summary:

- **DEM (NGII)**: 국토지리정보원 1:5000 digital map. Free for research,
  requires Korean registration. Place files under
  ``data/raw/dem/ngii/<sheet>.tif`` and run with ``source='ngii'``.
- **DEM (SRTM)**: NASA SRTM 30 m global. Free, no registration.
  Place files under ``data/raw/dem/srtm/`` and run with ``source='srtm'``.
- **Fuel type (KFS 임상도)**: Korean Forest Service forest type map v1.4.
  Requires Korean registration at https://map.forest.go.kr. Place files
  under ``data/raw/fuel/kfs_impsangdo/`` and run with ``source='kfs_impsangdo'``.
- **Landcover (ME 토지피복지도)**: Ministry of Environment Korea, free
  with registration. Place files under ``data/raw/landcover/me/``.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Literal

import numpy as np
import xarray as xr

from ..utils.regions import KOREA_2000_UNIFIED, RegionConfig

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
            attrs={"units": "m", "source": "synthetic", "synthetic": True},
        )
    elif source == "srtm":
        raise NotImplementedError(
            "SRTM DEM ingestion is a Session 3 task. Place SRTM tiles under "
            "data/raw/dem/srtm/ and add the rasterio mosaic + reproject "
            "logic here. See docs/data_sources.md for download instructions."
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
    # Slope + aspect from gradient.
    cs = grid.cell_size_m
    dz_di, dz_dj = np.gradient(dem.values.astype(np.float32), cs, cs)
    slope_rad = np.arctan(np.hypot(dz_di, dz_dj))
    grid.slope_degrees[:] = np.degrees(slope_rad).astype(np.float32)
    grid.aspect_degrees[:] = (
        (np.degrees(np.arctan2(dz_dj, -dz_di)) + 180.0) % 360.0
    ).astype(np.float32)

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
    "clear_cache",
]
