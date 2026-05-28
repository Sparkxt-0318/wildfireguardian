"""Unit tests for the CRS-aware FireGrid features (Session 2)."""

from __future__ import annotations

import math
import tempfile
from pathlib import Path

import numpy as np
import pytest

from wildfireguardian.spread_model.cellular_automaton import (
    CellState,
    FireGrid,
    WindField,
)
from wildfireguardian.utils.regions import (
    KOREA_2000_UNIFIED,
    YEONGDEOK_2025,
    RegionConfig,
)


# ---------------------------------------------------------------------------
# from_region factory
# ---------------------------------------------------------------------------


def test_from_region_attaches_region_and_crs() -> None:
    grid = FireGrid.from_region(YEONGDEOK_2025, cell_size_m=300.0)
    assert grid.is_georeferenced
    assert grid.crs == KOREA_2000_UNIFIED
    assert grid.region is YEONGDEOK_2025


def test_from_region_grid_dims_match_region_bbox() -> None:
    """Constructed grid covers the region bbox at the requested cell size."""
    grid = FireGrid.from_region(YEONGDEOK_2025, cell_size_m=300.0)
    expected_rows, expected_cols = YEONGDEOK_2025.grid_dims(300.0)
    assert (grid.nrows, grid.ncols) == (expected_rows, expected_cols)


def test_session1_constructor_still_yields_non_georeferenced_grid() -> None:
    """The plain FireGrid(nrows=, ncols=) constructor stays non-CRS."""
    grid = FireGrid(nrows=10, ncols=10, cell_size_m=30.0)
    assert not grid.is_georeferenced
    assert grid.crs is None
    assert grid.region is None


# ---------------------------------------------------------------------------
# cell_to_epsg5179
# ---------------------------------------------------------------------------


def test_cell_to_epsg5179_top_left_corner() -> None:
    """Cell (0, 0) centre should be at (minx + cs/2, maxy - cs/2)."""
    cs = 300.0
    grid = FireGrid.from_region(YEONGDEOK_2025, cell_size_m=cs)
    minx, _, _, maxy = YEONGDEOK_2025.bbox_epsg5179
    x, y = grid.cell_to_epsg5179(0, 0)
    assert x == pytest.approx(minx + cs / 2.0)
    assert y == pytest.approx(maxy - cs / 2.0)


def test_cell_to_epsg5179_raises_when_not_georef() -> None:
    grid = FireGrid(nrows=10, ncols=10, cell_size_m=30.0)
    with pytest.raises(RuntimeError):
        grid.cell_to_epsg5179(0, 0)


# ---------------------------------------------------------------------------
# Geographic perimeter
# ---------------------------------------------------------------------------


def _ignite_and_step(grid: FireGrid, n_steps: int = 5) -> None:
    grid.fuel_moisture[:] = 0.06
    grid.fuel_model_id[:] = "FM1"
    grid.ignite_point(grid.nrows // 2, grid.ncols // 2, time_min=0.0)
    wind = WindField.from_meteo(speed_ms=3.0, from_deg=270.0)
    for s in range(n_steps):
        grid.step(2.0, wind, current_time_min=s * 2.0)


def test_perimeter_geodataframe_has_epsg5179_crs() -> None:
    grid = FireGrid.from_region(YEONGDEOK_2025, cell_size_m=300.0)
    _ignite_and_step(grid)
    gdf = grid.perimeter_geodataframe()
    assert gdf is not None
    assert str(gdf.crs).endswith("5179")


def test_perimeter_geodataframe_bounds_within_region_bbox() -> None:
    """The georeferenced perimeter must sit inside the region's EPSG:5179 bbox."""
    grid = FireGrid.from_region(YEONGDEOK_2025, cell_size_m=300.0)
    _ignite_and_step(grid)
    gdf = grid.perimeter_geodataframe()
    minx, miny, maxx, maxy = gdf.total_bounds
    r_minx, r_miny, r_maxx, r_maxy = YEONGDEOK_2025.bbox_epsg5179
    assert r_minx <= minx and maxx <= r_maxx
    assert r_miny <= miny and maxy <= r_maxy


def test_to_wgs84_perimeter_reprojects_to_lat_lon_range() -> None:
    """to_wgs84_perimeter() reprojects to EPSG:4326 with reasonable lat/lon."""
    grid = FireGrid.from_region(YEONGDEOK_2025, cell_size_m=300.0)
    _ignite_and_step(grid)
    wgs = grid.to_wgs84_perimeter()
    assert str(wgs.crs).endswith("4326")
    minlon, minlat, maxlon, maxlat = wgs.total_bounds
    # Should be inside Yeongdeok bbox.
    r_minlon, r_minlat, r_maxlon, r_maxlat = YEONGDEOK_2025.bbox_wgs84
    assert r_minlon <= minlon and maxlon <= r_maxlon
    assert r_minlat <= minlat and maxlat <= r_maxlat


def test_perimeter_geodataframe_raises_when_not_georef() -> None:
    grid = FireGrid(nrows=10, ncols=10, cell_size_m=30.0)
    with pytest.raises(RuntimeError):
        grid.perimeter_geodataframe()


# ---------------------------------------------------------------------------
# GeoTIFF round-trip
# ---------------------------------------------------------------------------


def test_to_geotiff_writes_readable_file() -> None:
    grid = FireGrid.from_region(YEONGDEOK_2025, cell_size_m=300.0)
    _ignite_and_step(grid)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.tif"
        grid.to_geotiff(path)
        # Read back with rasterio and confirm CRS and content.
        import rasterio
        with rasterio.open(path) as src:
            assert str(src.crs).endswith("5179")
            assert src.width == grid.ncols
            assert src.height == grid.nrows
            data = src.read(1)
        assert data.shape == grid.state.shape
        # At least one cell should be BURNING or BURNED.
        assert int((data >= int(CellState.BURNING)).sum()) > 0


# ---------------------------------------------------------------------------
# Synthetic region still works (backwards compat)
# ---------------------------------------------------------------------------


def test_synthetic_region_grid_is_not_georeferenced() -> None:
    """RegionConfig.synthetic() yields a grid whose CRS export refuses."""
    r = RegionConfig.synthetic(name="testbed",
                                bbox_5179=(0.0, 0.0, 5000.0, 5000.0))
    grid = FireGrid.from_region(r, cell_size_m=50.0)
    # is_georeferenced should be False for the synthetic flag.
    assert not grid.is_georeferenced
    with pytest.raises(RuntimeError):
        grid.perimeter_geodataframe()


# ---------------------------------------------------------------------------
# Backwards compat: pre-Session-2 perimeter() coords differ for georef'd grids
# ---------------------------------------------------------------------------


def test_session1_perimeter_uses_local_cartesian() -> None:
    """Without region, perimeter coords are local Cartesian (SW corner origin)."""
    grid = FireGrid(nrows=10, ncols=10, cell_size_m=30.0)
    grid.fuel_moisture[:] = 0.05
    grid.fuel_model_id[:] = "FM1"
    grid.ignite_point(5, 5)
    grid.run(duration_minutes=10.0, dt_minutes=1.0,
             wind=WindField(0.0, 0.0), return_perimeters=False)
    poly = grid.perimeter()
    assert poly is not None
    minx, miny, maxx, maxy = poly.bounds
    # In local frame, x should be near j*cs and y near (nrows-1-i)*cs;
    # both small (within grid).
    assert 0.0 <= minx <= 10 * 30.0
    assert 0.0 <= miny <= 10 * 30.0


def test_georef_perimeter_uses_epsg5179_coords() -> None:
    """With region, perimeter coords are large EPSG:5179 metres."""
    grid = FireGrid.from_region(YEONGDEOK_2025, cell_size_m=300.0)
    _ignite_and_step(grid)
    poly = grid.perimeter()
    minx, miny, _maxx, _maxy = poly.bounds
    # EPSG:5179 metres for Korea are in the ~ 1e6 range.
    assert 1.0e6 < minx < 1.5e6
    assert 1.5e6 < miny < 2.5e6
