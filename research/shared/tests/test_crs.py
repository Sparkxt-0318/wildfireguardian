"""Tests for research/shared/geo/crs.py (T1.5e)."""

from __future__ import annotations

import pytest
from shapely.geometry import Point, Polygon

from research.shared.geo.crs import (
    ANALYSIS_CRS,
    EXCHANGE_CRS,
    assert_projected_crs,
    safe_area_m2,
    safe_length_m,
    to_analysis_crs,
    to_exchange_crs,
    transform_point,
)

# Seoul City Hall, a well-known Korean reference point (WGS84).
SEOUL_CITY_HALL_LON = 126.9780
SEOUL_CITY_HALL_LAT = 37.5665


def test_guard_fires_on_geographic_crs():
    with pytest.raises(ValueError, match="geographic"):
        assert_projected_crs(EXCHANGE_CRS)


def test_guard_fires_on_none_crs():
    with pytest.raises(ValueError):
        assert_projected_crs(None)


def test_guard_passes_silently_on_analysis_crs():
    parsed = assert_projected_crs(ANALYSIS_CRS)
    assert parsed.to_epsg() == 5186


def test_safe_length_and_area_refuse_geographic_crs():
    line_like_poly = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    with pytest.raises(ValueError, match="geographic"):
        safe_length_m(line_like_poly.exterior, EXCHANGE_CRS)
    with pytest.raises(ValueError, match="geographic"):
        safe_area_m2(line_like_poly, EXCHANGE_CRS)


def test_safe_length_and_area_work_on_analysis_crs():
    # a 100 m x 100 m square in a projected (metre) CRS
    square = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])
    assert safe_area_m2(square, ANALYSIS_CRS) == pytest.approx(10_000.0)
    assert safe_length_m(square.exterior, ANALYSIS_CRS) == pytest.approx(400.0)


def test_roundtrip_known_korean_coordinate():
    x, y = transform_point(SEOUL_CITY_HALL_LON, SEOUL_CITY_HALL_LAT)
    # EPSG:5186 is metres, centred near the Korean peninsula; sanity-check
    # the transformed value is in a plausible range before round-tripping.
    assert 100_000 < x < 400_000
    assert 300_000 < y < 700_000

    lon_back, lat_back = transform_point(x, y, src=ANALYSIS_CRS, dst=EXCHANGE_CRS)
    assert lon_back == pytest.approx(SEOUL_CITY_HALL_LON, abs=1e-6)
    assert lat_back == pytest.approx(SEOUL_CITY_HALL_LAT, abs=1e-6)


def test_to_analysis_and_exchange_crs_geodataframe_roundtrip():
    gpd = pytest.importorskip("geopandas")
    gdf = gpd.GeoDataFrame(
        {"id": [1]},
        geometry=[Point(SEOUL_CITY_HALL_LON, SEOUL_CITY_HALL_LAT)],
        crs=EXCHANGE_CRS,
    )
    analysis = to_analysis_crs(gdf)
    assert analysis.crs.to_epsg() == 5186

    back = to_exchange_crs(analysis)
    assert back.crs.to_epsg() == 4326
    assert back.geometry.iloc[0].x == pytest.approx(SEOUL_CITY_HALL_LON, abs=1e-6)
    assert back.geometry.iloc[0].y == pytest.approx(SEOUL_CITY_HALL_LAT, abs=1e-6)


def test_to_analysis_crs_refuses_unset_crs():
    gpd = pytest.importorskip("geopandas")
    gdf = gpd.GeoDataFrame(
        {"id": [1]}, geometry=[Point(SEOUL_CITY_HALL_LON, SEOUL_CITY_HALL_LAT)]
    )
    with pytest.raises(ValueError):
        to_analysis_crs(gdf)
