"""Independent format/units/cutoff tests for the authentic FARSITE input bridge."""
import json
from pathlib import Path
import struct

from affine import Affine
import numpy as np
import pandas as pd
from pyproj import CRS, Geod, Transformer
import pytest
import rasterio
from rasterio.features import rasterize
import shapefile

from wildfire.farsite_inputs import (
    FuelMoistureScenario, LANDSCAPE_FILES, LCP_HEADER_BYTES, WEATHER_FILES,
    _encode_landscape, _station_weather, _write_ignition, _write_lcp,
    prepare_farsite_inputs,
)


def _write_raster(path, array, transform, *, descriptions=None, epsg=5070):
    path.parent.mkdir(parents=True, exist_ok=True)
    array = np.asarray(array, dtype="float32")
    if array.ndim == 2:
        array = array[None]
    with rasterio.open(path, "w", driver="GTiff", height=array.shape[1],
                       width=array.shape[2], count=len(array), dtype="float32",
                       transform=transform, crs=f"EPSG:{epsg}", nodata=-9999) as dst:
        dst.write(np.where(np.isfinite(array), array, -9999))
        if descriptions:
            for i, value in enumerate(descriptions, 1):
                dst.set_band_description(i, value)


@pytest.fixture
def physical_region(tmp_path):
    root = tmp_path / "data"
    region = root / "regions" / "US_test"
    region.mkdir(parents=True)
    transform = Affine(375, 0, -1141125, 0, -375, 2393250)
    grid = {"id": "US_test", "country": "US", "height": 2, "width": 3,
            "epsg": 5070, "transform": list(transform)[:6],
            "t0_utc": "2024-08-21T00:00:00Z", "start_utc": "2024-08-21T00:00:00Z",
            "end_utc": "2024-08-22T00:00:00Z"}
    (region / "grid.json").write_text(json.dumps(grid))
    landscape = (2000, 12, 270, 183, 50, 12.34, 2.56, 0.123)
    for name, value in zip(LANDSCAPE_FILES, landscape):
        _write_raster(region / name, np.full((2, 3), value), transform)
    times = ["2024-08-21T06:00:00Z", "2024-08-21T07:00:00Z"]
    for name, value in zip(WEATHER_FILES, (10, 40, 0.25, 2, 359)):
        # Future data are intentionally unavailable and physically absurd.
        data = np.stack([np.full((2, 3), value), np.full((2, 3), np.nan)])
        _write_raster(region / "weather" / f"{name}_375m.tif", data,
                      transform, descriptions=times)
    arrival = np.array([[1, 7, np.nan], [9, 12, np.nan]])
    _write_raster(region / "arrival_time_hours.tif", arrival, transform)
    return root, region, transform


def _prepare(physical_region, output, **kwargs):
    root, _, _ = physical_region
    return prepare_farsite_inputs("US_test", "2024-08-21T06:00:00Z", 6,
                                  output, data_root=root, **kwargs)


def test_packed_header_matches_independent_native_layout(tmp_path):
    cells = np.zeros((2, 3, 8), dtype="int16")
    cells[..., 3] = 183
    cells[0, 0] = [2000, 12, 270, 183, 50, 123, 26, 12]
    transform = Affine(375, 0, -1141125, 0, -375, 2393250)
    path = tmp_path / "landscape.lcp"
    _write_lcp(path, cells, transform, 5070)
    payload = path.read_bytes()
    assert len(payload) == 7316 + 2 * 3 * 8 * 2
    assert struct.unpack_from("<ii", payload, 0) == (21, 20)
    assert struct.unpack_from("<ii", payload, 4164) == (3, 2)
    assert struct.unpack_from("<4d", payload, 4172) == (-1140000, -1141125, 2393250, 2392500)
    assert struct.unpack_from("<i2d", payload, 4204) == (0, 375, 375)
    assert struct.unpack_from("<10h", payload, 4224) == (0, 0, 2, 0, 1, 1, 1, 1, 0, 0)
    actual = np.frombuffer(payload, dtype="<i2", offset=7316).reshape(2, 3, 8)
    np.testing.assert_array_equal(actual, cells)


def test_decoded_canopy_units_and_flat_aspect_are_encoded_explicitly():
    data = [np.array([[v]], dtype=float) for v in [2000, 0, np.nan, 183, 50, 12.34, 2.56, 0.123]]
    actual, valid, flat = _encode_landscape(data)
    assert valid.item() and flat == 1
    np.testing.assert_array_equal(actual[0, 0], [2000, 0, 0, 183, 50, 123, 26, 12])


def test_unknown_environment_is_unavailable_and_barrier_without_fuel_imputation():
    values = [np.array([[v, v]], dtype=float) for v in [2000, 12, 270, 183, 50, 12, 2, 0.12]]
    values[3][0, 1] = np.nan
    encoded, valid, _ = _encode_landscape(values)
    np.testing.assert_array_equal(valid, [[True, False]])
    assert encoded[0, 0, 3] == 183 and encoded[0, 1, 3] == 99


@pytest.mark.parametrize("fuel", [0, 100, 110, 125, 150, 170, 190, 205, 101.5])
def test_unrecognized_or_fractional_fuel_codes_rejected(fuel):
    values = [np.array([[v]], dtype=float) for v in [2000, 12, 270, fuel, 50, 12, 2, 0.12]]
    with pytest.raises(ValueError, match="fuel-model|integer"):
        _encode_landscape(values)


def test_vector_average_direction_handles_north_wrap_and_projection():
    shape = (1, 2)
    arrays = [np.full(shape, v) for v in [10, 40, 0, 2]] + [np.array([[359, 1]])]
    transform = Affine(375, 0, -1141125, 0, -375, 2393250)
    station = _station_weather(arrays, np.ones(shape, bool), transform, 5070)
    assert station["wind_speed_10m_m_per_s"] == pytest.approx(2 * np.cos(np.deg2rad(1)))
    true = station["wind_direction_from_true_north_degrees"] % 360
    assert min(true, 360 - true) < 1e-10
    lon, lat = station["centroid_longitude"], station["centroid_latitude"]
    lon2, lat2, _ = Geod(ellps="WGS84").fwd(lon, lat, 0, 100)
    xy = Transformer.from_crs(4326, 5070, always_xy=True)
    x, y = xy.transform(lon, lat)
    x2, y2 = xy.transform(lon2, lat2)
    expected = np.rad2deg(np.arctan2(x2 - x, y2 - y)) % 360
    assert station["wind_direction_from_grid_north_degrees"] == pytest.approx(expected)


def test_prepare_retains_rectangle_buffer_cutoff_only_and_known_ignition(physical_region, tmp_path):
    result = _prepare(physical_region, tmp_path / "input")
    assert result.original_shape == (2, 3)
    np.testing.assert_array_equal(result.initial_burned, [[True, False, False], [False, False, False]])
    np.testing.assert_array_equal(result.initial_burned_valid, [[True, True, False], [True, True, False]])
    assert result.environment_valid.all()
    payload = result.lcp_path.read_bytes()
    assert struct.unpack_from("<ii", payload, 4164) == (5, 4)
    cells = np.frombuffer(payload, "<i2", offset=LCP_HEADER_BYTES).reshape(4, 5, 8)
    assert (cells[0, :, 3] == 99).all() and (cells[-1, :, 3] == 99).all()
    assert (cells[:, 0, 3] == 99).all() and (cells[:, -1, 3] == 99).all()
    assert (cells[1:-1, 1:-1, 3] == 183).all()
    assert result.manifest["weather_source_bands"] == dict.fromkeys(WEATHER_FILES, 1)
    rows = [line.split() for line in result.raws_path.read_text().splitlines()[3:]]
    assert len(rows) == 8
    assert rows[0][:4] == ["2024", "8", "20", "2300"]
    assert rows[-1][:4] == ["2024", "8", "21", "600"]
    assert all(row[4:8] == ["10", "40", "0.25", "7.2"] for row in rows)
    assert len({tuple(row[4:]) for row in rows}) == 1
    text = result.input_path.read_text()
    assert "FARSITE_START_TIME: 08 20 2300" in text
    assert "FARSITE_END_TIME: 08 21 0500" in text
    assert "0 6 7 8 60 90" in text and "FARSITE_SPOT_PROBABILITY: 0" in text
    assert result.manifest["ignition"]["burned_area_projected_m2"] == 375 ** 2
    assert result.manifest["cloud_cover_interpretation"].startswith("caller scenario")
    assert result.manifest["fuel_moisture_interpretation"].startswith("all supplied percentages assumed")
    assert json.loads(result.manifest_path.read_text()) == result.manifest
    assert CRS.from_wkt(result.ignition_path.with_suffix(".prj").read_text()).to_epsg() == 5070


def test_environment_hole_preserves_shape_and_coverage(physical_region, tmp_path):
    _, region, transform = physical_region
    values = np.full((2, 3), 12.34)
    values[0, 2] = np.nan
    _write_raster(region / LANDSCAPE_FILES[5], values, transform)
    result = _prepare(physical_region, tmp_path / "input")
    assert result.environment_valid.sum() == 5
    assert not result.environment_valid[0, 2]
    assert result.manifest["environment_unavailable_pixels"] == 1
    cells = np.frombuffer(result.lcp_path.read_bytes(), "<i2", offset=7316).reshape(4, 5, 8)
    assert cells[1, 3, 3] == 99
    assert result.original_shape == (2, 3)


def test_ignition_polygon_holes_preserve_exact_initial_area(tmp_path):
    burned = np.ones((3, 3), bool)
    burned[1, 1] = False
    transform = Affine(375, 0, -1141125, 0, -375, 2393250)
    path = tmp_path / "ignition.shp"
    summary = _write_ignition(path, burned, transform, 5070)
    assert summary["burned_area_projected_m2"] == 8 * 375 ** 2
    with shapefile.Reader(str(path)) as reader:
        geometries = [s.__geo_interface__ for s in reader.shapes()]
    restored = rasterize([(g, 1) for g in geometries], out_shape=burned.shape,
                         transform=transform, dtype="uint8")
    np.testing.assert_array_equal(restored.astype(bool), burned)


def test_no_future_reference_or_weather_needed_for_inputs(physical_region, tmp_path):
    first = _prepare(physical_region, tmp_path / "one")
    _, region, transform = physical_region
    # Change all future reconstructed arrival values while preserving cutoff state.
    _write_raster(region / "arrival_time_hours.tif", [[1, 10000, np.nan], [10000, 10000, np.nan]], transform)
    second = _prepare(physical_region, tmp_path / "two")
    assert first.lcp_path.read_bytes() == second.lcp_path.read_bytes()
    assert first.raws_path.read_bytes() == second.raws_path.read_bytes()
    np.testing.assert_array_equal(first.initial_burned, second.initial_burned)
    for suffix in [".shp", ".shx", ".dbf"]:
        assert first.ignition_path.with_suffix(suffix).read_bytes() == second.ignition_path.with_suffix(suffix).read_bytes()


@pytest.mark.parametrize("kwargs", [{"hours": True}, {"hours": 1.5}, {"hours": 0},
    {"boundary_padding": True}, {"boundary_padding": -1}, {"cloud_cover_percent": -1},
    {"cloud_cover_percent": np.nan}, {"utc_offset_hours": 15}, {"utc_offset_hours": 5.5}, {"timestep_minutes": 61},
    {"distance_resolution_m": 0}, {"perimeter_resolution_m": np.nan},
    {"moisture": {"dead_1h_percent": 6}}])
def test_invalid_scenario_controls_fail_before_writing(physical_region, tmp_path, kwargs):
    root, _, _ = physical_region
    args = {"hours": 6, "output_dir": tmp_path / "input", "data_root": root, **kwargs}
    with pytest.raises(ValueError):
        prepare_farsite_inputs("US_test", "2024-08-21T06:00:00Z", **args)
    assert not (tmp_path / "input").exists()


@pytest.mark.parametrize("kwargs", [{"dead_1h_percent": True}, {"dead_10h_percent": 6.1},
                                   {"live_herb_percent": 0}, {"foliar_percent": 301}])
def test_moisture_percentages_are_explicit_valid_integers(kwargs):
    with pytest.raises(ValueError, match="percent"):
        FuelMoistureScenario(**kwargs)


def test_non_us_fuel_grid_and_naive_cutoff_rejected(physical_region, tmp_path):
    root, region, _ = physical_region
    with pytest.raises(ValueError, match="UTC offset"):
        prepare_farsite_inputs("US_test", "2024-08-21T06:00:00", 6, tmp_path / "one", data_root=root)
    grid = json.loads((region / "grid.json").read_text())
    grid["country"] = "KR"
    (region / "grid.json").write_text(json.dumps(grid))
    with pytest.raises(ValueError, match="non-U.S."):
        _prepare(physical_region, tmp_path / "two")


def test_exact_weather_cutoff_no_clamping_and_geometry_validation(physical_region, tmp_path):
    root, region, transform = physical_region
    with pytest.raises(ValueError, match="Exact cutoff weather"):
        prepare_farsite_inputs("US_test", "2024-08-21T08:00:00Z", 6,
                              tmp_path / "one", data_root=root)
    _write_raster(region / LANDSCAPE_FILES[0], np.full((2, 3), 2000), transform @ Affine.translation(1, 0))
    with pytest.raises(ValueError, match="original rectangle"):
        _prepare(physical_region, tmp_path / "two")


def test_no_fire_and_output_overwrite_are_rejected(physical_region, tmp_path):
    root, region, transform = physical_region
    result = _prepare(physical_region, tmp_path / "input")
    with pytest.raises(ValueError, match="new or empty"):
        _prepare(physical_region, tmp_path / "input")
    _write_raster(region / "arrival_time_hours.tif", np.full((2, 3), 1000), transform)
    with pytest.raises(ValueError, match="no known initial fire"):
        _prepare(physical_region, tmp_path / "other")
    assert result.input_path.is_file()


def test_native_bundle_paths_reject_whitespace_before_writing(physical_region, tmp_path):
    directory = tmp_path / "native input"
    with pytest.raises(ValueError, match="without whitespace"):
        _prepare(physical_region, directory)
    assert not directory.exists()
