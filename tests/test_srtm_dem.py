"""Real SRTM DEM ingestion tests (Session 3).

These tests exercise the SRTM .hgt ingestion path; they assume the
Yeongdeok-area tile (N36E129.hgt) is already cached under
``data/raw/dem/srtm/``. If it is not, the network-download step in
:func:`wildfireguardian.data_io.raster._download_srtm_tile` will fetch
it from the AWS Mapzen archive. Network failures (which can happen in
sandboxed CI) will cause these tests to be skipped via
``pytest.importorskip``-style guards rather than failing.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from wildfireguardian.data_io.raster import (
    _srtm_tile_name,
    _srtm_tile_url,
    _srtm_tiles_covering,
    compute_slope_aspect,
    load_dem,
)
from wildfireguardian.utils.regions import (
    GOSEONG_2019,
    ULJIN_SAMCHEOK_2022,
    YEONGDEOK_2025,
)


# ---------------------------------------------------------------------------
# Tile-name math (no network needed)
# ---------------------------------------------------------------------------


def test_srtm_tile_name_format() -> None:
    assert _srtm_tile_name(36, 129) == "N36E129.hgt"
    assert _srtm_tile_name(38, 128) == "N38E128.hgt"


def test_srtm_tile_url_format() -> None:
    url = _srtm_tile_url(36, 129)
    assert url == (
        "https://elevation-tiles-prod.s3.amazonaws.com/skadi/"
        "N36/N36E129.hgt.gz"
    )


def test_srtm_tiles_for_yeongdeok_single_tile() -> None:
    """Yeongdeok bbox sits inside the single 1° × 1° tile (36N, 129E)."""
    tiles = _srtm_tiles_covering(YEONGDEOK_2025.bbox_wgs84)
    assert tiles == [(36, 129)]


def test_srtm_tiles_for_uljin_samcheok_spans_two_lats() -> None:
    """Uljin/Samcheok spans both 36N and 37N → 2 tiles needed."""
    tiles = _srtm_tiles_covering(ULJIN_SAMCHEOK_2022.bbox_wgs84)
    assert (36, 129) in tiles
    assert (37, 129) in tiles


def test_srtm_tiles_for_goseong() -> None:
    """Goseong is entirely inside N38E128."""
    tiles = _srtm_tiles_covering(GOSEONG_2019.bbox_wgs84)
    assert tiles == [(38, 128)]


# ---------------------------------------------------------------------------
# Real SRTM DEM ingestion — needs network or pre-cached tile
# ---------------------------------------------------------------------------


def _srtm_tile_available() -> bool:
    """True iff the Yeongdeok-area .hgt tile is locally cached."""
    repo_root = Path(__file__).resolve().parents[1]
    return (repo_root / "data" / "raw" / "dem" / "srtm" / "N36E129.hgt").exists()


@pytest.mark.skipif(
    not _srtm_tile_available(),
    reason="SRTM N36E129.hgt not cached; skipping real-data test",
)
def test_real_srtm_dem_for_yeongdeok_loads() -> None:
    dem = load_dem(YEONGDEOK_2025, source="srtm", cell_size_m=300.0, use_cache=False)
    expected = YEONGDEOK_2025.grid_dims(300.0)
    assert dem.shape == expected
    assert dem.attrs["source"] == "srtm"
    assert dem.attrs["synthetic"] is False
    assert "SRTMGL1" in dem.attrs["citation"]


@pytest.mark.skipif(
    not _srtm_tile_available(),
    reason="SRTM N36E129.hgt not cached; skipping real-data test",
)
def test_real_srtm_dem_elevation_plausible() -> None:
    """Yeongdeok terrain: must include ocean (~0 m) and mountains (~500-800 m)."""
    dem = load_dem(YEONGDEOK_2025, source="srtm", cell_size_m=300.0, use_cache=False)
    vals = dem.values
    assert vals.min() >= 0.0, "ocean cells should be clipped to 0"
    # Yeongdeok has the Taebaek range to the west — should reach 500m+
    assert vals.max() >= 400.0, f"max elev {vals.max()} too low for Yeongdeok area"
    # And the East Sea on the east side: at least some 0-elevation cells
    assert (vals == 0.0).sum() > 100, "expected sea / coastline cells"


@pytest.mark.skipif(
    not _srtm_tile_available(),
    reason="SRTM N36E129.hgt not cached; skipping real-data test",
)
def test_real_srtm_dem_eastern_edge_is_sea() -> None:
    """Yeongdeok's east edge is the East Sea — average elevation there ≈ 0."""
    dem = load_dem(YEONGDEOK_2025, source="srtm", cell_size_m=300.0, use_cache=False)
    east_strip_mean = float(dem.isel(x=slice(-3, None)).mean())
    west_strip_mean = float(dem.isel(x=slice(0, 3)).mean())
    assert east_strip_mean < west_strip_mean, (
        f"east coast should be lower than inland: east={east_strip_mean:.1f}, "
        f"west={west_strip_mean:.1f}"
    )
    # East strip dominated by sea → mean elev close to 0 (some cells may be land too)
    assert east_strip_mean < 100.0, f"east strip mean {east_strip_mean:.1f} too high"


# ---------------------------------------------------------------------------
# Slope / aspect derivation
# ---------------------------------------------------------------------------


def test_compute_slope_aspect_on_flat_terrain_returns_zero_slope() -> None:
    flat = np.full((50, 50), 100.0, dtype=np.float32)
    slope, aspect = compute_slope_aspect(flat, cell_size_m=30.0)
    assert np.allclose(slope, 0.0)


def test_compute_slope_aspect_on_east_facing_slope() -> None:
    """A plane rising linearly to the WEST should yield aspect = 90° (east).

    Rising to the west means elevation increases as j decreases — gradient
    in the j (east) direction is negative; downslope points east → aspect = 90°.
    """
    # Build DEM rising to the west: elev = (ncols - 1 - j) * gain
    nrows, ncols = 20, 20
    j = np.arange(ncols)[None, :]
    dem = (ncols - 1 - j).repeat(nrows, axis=0).astype(np.float32) * 5.0
    slope, aspect = compute_slope_aspect(dem, cell_size_m=30.0)
    # Interior cells should have aspect ≈ 90° (east)
    interior = aspect[5:15, 5:15]
    assert np.allclose(interior, 90.0, atol=0.1), interior.flatten()[:5]
    # Slope should be arctan(5/30) ≈ 9.46° at interior cells
    expected_slope = np.degrees(np.arctan(5.0 / 30.0))
    assert np.allclose(slope[5:15, 5:15], expected_slope, atol=0.1)


def test_compute_slope_aspect_on_south_facing_slope() -> None:
    """A plane rising linearly to the NORTH should yield aspect ≈ 180° (south).

    Rising to the north = elev increases as i (row) decreases (row 0 is top).
    Gradient in i is negative → downslope in i is positive (south) → aspect = 180°.
    """
    nrows, ncols = 20, 20
    i = np.arange(nrows)[:, None]
    dem = (nrows - 1 - i).repeat(ncols, axis=1).astype(np.float32) * 5.0
    slope, aspect = compute_slope_aspect(dem, cell_size_m=30.0)
    interior = aspect[5:15, 5:15]
    assert np.allclose(interior, 180.0, atol=0.1)


@pytest.mark.skipif(
    not _srtm_tile_available(),
    reason="SRTM N36E129.hgt not cached; skipping real-data test",
)
def test_slope_aspect_on_real_yeongdeok_terrain_physical_range() -> None:
    dem = load_dem(YEONGDEOK_2025, source="srtm", cell_size_m=300.0, use_cache=False)
    slope, aspect = compute_slope_aspect(dem.values, 300.0)
    assert (slope >= 0).all() and (slope <= 90.0).all()
    assert (aspect >= 0).all() and (aspect < 360.0001).all()
    # At least some cells should be steep (Taebaek foothills)
    assert (slope > 15.0).sum() > 100, (
        f"only {(slope > 15.0).sum()} cells have slope > 15 deg"
    )
