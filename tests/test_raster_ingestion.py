"""Unit tests for the raster ingestion scaffolding (Session 2)."""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from wildfireguardian.data_io.raster import (
    clear_cache,
    load_dem,
    load_fuel_type,
    load_landcover,
    populate_firegrid,
)
from wildfireguardian.spread_model.cellular_automaton import FireGrid
from wildfireguardian.utils.regions import YEONGDEOK_2025, RegionConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_cache_between_tests():
    clear_cache()
    yield
    clear_cache()


# ---------------------------------------------------------------------------
# Synthetic loaders
# ---------------------------------------------------------------------------


def test_synthetic_dem_has_correct_shape_and_crs() -> None:
    arr = load_dem(YEONGDEOK_2025, source="synthetic", cell_size_m=300.0, use_cache=False)
    expected = YEONGDEOK_2025.grid_dims(300.0)
    assert arr.shape == expected
    assert arr.attrs["rio_crs"] == "EPSG:5179"
    assert arr.attrs["cell_size_m"] == 300.0
    assert arr.attrs["synthetic"] is True


def test_synthetic_fuel_type_returns_korean_pinus_code() -> None:
    arr = load_fuel_type(YEONGDEOK_2025, source="synthetic", cell_size_m=300.0,
                        use_cache=False)
    expected = YEONGDEOK_2025.grid_dims(300.0)
    assert arr.shape == expected
    assert int(arr.values.max()) == 1   # KP_PINE
    assert int(arr.values.min()) == 1


def test_synthetic_landcover_returns_forest_code() -> None:
    arr = load_landcover(YEONGDEOK_2025, source="synthetic", cell_size_m=300.0,
                         use_cache=False)
    expected = YEONGDEOK_2025.grid_dims(300.0)
    assert arr.shape == expected
    assert int(arr.values.max()) == 3   # forest


def test_dem_synthetic_is_monotonic_inland() -> None:
    """Synthetic DEM rises from east (coast) to west (inland)."""
    arr = load_dem(YEONGDEOK_2025, source="synthetic", cell_size_m=300.0, use_cache=False)
    east_mean = float(arr.isel(x=-1).mean())
    west_mean = float(arr.isel(x=0).mean())
    assert west_mean > east_mean, (west_mean, east_mean)


# ---------------------------------------------------------------------------
# CRS consistency
# ---------------------------------------------------------------------------


def test_dem_and_fuel_have_same_dimensions() -> None:
    dem = load_dem(YEONGDEOK_2025, source="synthetic", cell_size_m=300.0, use_cache=False)
    fuel = load_fuel_type(YEONGDEOK_2025, source="synthetic", cell_size_m=300.0, use_cache=False)
    assert dem.shape == fuel.shape
    assert dem.attrs["rio_crs"] == fuel.attrs["rio_crs"]
    np.testing.assert_array_equal(dem.coords["y"].values, fuel.coords["y"].values)
    np.testing.assert_array_equal(dem.coords["x"].values, fuel.coords["x"].values)


def test_raster_coords_lie_within_region_bbox() -> None:
    dem = load_dem(YEONGDEOK_2025, source="synthetic", cell_size_m=300.0, use_cache=False)
    minx, miny, maxx, maxy = YEONGDEOK_2025.bbox_epsg5179
    assert minx <= dem.coords["x"].min() <= dem.coords["x"].max() <= maxx
    assert miny <= dem.coords["y"].min() <= dem.coords["y"].max() <= maxy


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


def test_cache_round_trip_returns_identical_array() -> None:
    """Loading twice should hit the cache and return identical data."""
    arr1 = load_dem(YEONGDEOK_2025, source="synthetic", cell_size_m=300.0, use_cache=True)
    arr2 = load_dem(YEONGDEOK_2025, source="synthetic", cell_size_m=300.0, use_cache=True)
    np.testing.assert_array_equal(arr1.values, arr2.values)


def test_cache_clear_removes_files() -> None:
    load_dem(YEONGDEOK_2025, source="synthetic", cell_size_m=300.0, use_cache=True)
    n = clear_cache()
    assert n >= 1


# ---------------------------------------------------------------------------
# Stubs are properly flagged as NotImplementedError
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("loader,source", [
    # Session 3: load_dem SRTM is now implemented (covered by tests/test_srtm_dem.py).
    (load_dem, "ngii"),
    (load_fuel_type, "kfs_impsangdo"),
    (load_landcover, "me_korea"),
])
def test_real_data_sources_raise_not_implemented(loader, source: str) -> None:
    with pytest.raises(NotImplementedError):
        loader(YEONGDEOK_2025, source=source, cell_size_m=300.0, use_cache=False)


def test_auto_dem_prefers_srtm_when_tile_available_else_synthetic() -> None:
    """source='auto' returns SRTM if the Yeongdeok tile is cached, else synthetic.

    Either outcome is acceptable; this test just confirms the fallback chain
    does not crash and produces a tagged DataArray.
    """
    arr = load_dem(YEONGDEOK_2025, source="auto", cell_size_m=300.0, use_cache=False)
    # Should be either real SRTM or labelled synthetic, both have valid attrs.
    assert arr.attrs.get("source") in {"srtm", "synthetic"}
    if arr.attrs.get("source") == "synthetic":
        assert arr.attrs.get("synthetic") is True
    else:
        assert "SRTMGL1" in arr.attrs.get("citation", "")


# ---------------------------------------------------------------------------
# populate_firegrid integration
# ---------------------------------------------------------------------------


def test_populate_firegrid_writes_elevation_slope_aspect() -> None:
    grid = FireGrid.from_region(YEONGDEOK_2025, cell_size_m=300.0)
    dem = load_dem(YEONGDEOK_2025, source="synthetic", cell_size_m=300.0, use_cache=False)
    populate_firegrid(grid, dem)
    # Elevation should be ~ 200-1000 m for our synthetic DEM.
    assert grid.elevation_m.min() >= 100
    assert grid.elevation_m.max() <= 1100
    # Slope and aspect arrays got something written.
    assert grid.slope_degrees.max() > 0


def test_populate_firegrid_with_fuel_type_lookup() -> None:
    from wildfireguardian.spread_model.rothermel import KOREAN_PINUS

    grid = FireGrid.from_region(YEONGDEOK_2025, cell_size_m=300.0)
    dem = load_dem(YEONGDEOK_2025, source="synthetic", cell_size_m=300.0, use_cache=False)
    fuel = load_fuel_type(YEONGDEOK_2025, source="synthetic", cell_size_m=300.0, use_cache=False)
    populate_firegrid(grid, dem, fuel_type=fuel, fuel_code_to_model={1: KOREAN_PINUS})
    # Every cell should now point at KOREAN_PINUS.
    assert all(grid.fuel_model_id[i, j] is KOREAN_PINUS
               for i in range(grid.nrows) for j in range(grid.ncols))


# ---------------------------------------------------------------------------
# Different regions all work
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("region_name", [
    "yeongdeok_2025", "uljin_samcheok_2022", "goseong_2019",
])
def test_synthetic_dem_works_for_all_validation_regions(region_name: str) -> None:
    from wildfireguardian.utils.regions import lookup
    region = lookup(region_name)
    arr = load_dem(region, source="synthetic", cell_size_m=300.0, use_cache=False)
    assert arr.shape == region.grid_dims(300.0)
    assert arr.attrs["region_name"] == region_name
