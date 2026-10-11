"""Source-law units, reference-catalog transcription, and missing-data contracts."""

from dataclasses import FrozenInstanceError
from datetime import timedelta
from hashlib import sha256
import json
import sys

import numpy as np
from numpy.testing import assert_allclose, assert_array_equal
import pytest

from wildfire.heat import FlameResidenceTime
from wildfire.heat import AffineGrid


def test_original_minutes_inches_law_and_si_sav_conversion_agree():
    # In the source law, a one-inch particle flames for eight minutes.
    by_diameter = FlameResidenceTime.from_particle_diameter(0.0254)
    assert_allclose(by_diameter.duration_s, 480.0, rtol=1e-14)
    # A long cylinder of diameter one inch has SAV 48 ft^-1, equivalently
    # 4/0.0254 m^-1. The original SAV residence equation is 384/48 minutes.
    by_sav = FlameResidenceTime.from_surface_area_to_volume(48.0 / 0.3048)
    assert_allclose(by_sav.duration_s, 480.0, rtol=1e-14)
    assert by_sav.duration_s.shape == ()


def test_physical_cylinder_geometry_gives_consistent_cell_specific_durations():
    diameter = np.array([[0.001, 0.002], [0.005, 0.010]])
    # Side area pi*d*L divided by volume pi*(d/2)^2*L cancels L.
    length = 2.0
    surface_area = np.pi * diameter * length
    volume = np.pi * (diameter / 2.0) ** 2 * length
    from_geometry = FlameResidenceTime.from_surface_area_to_volume(surface_area / volume)
    from_diameter = FlameResidenceTime.from_particle_diameter(diameter)
    assert_allclose(from_geometry.duration_s, from_diameter.duration_s, rtol=1e-14)
    assert_allclose(from_diameter.duration_s, [[18.89763779527559, 37.79527559055118],
                                             [94.48818897637795, 188.9763779527559]])
    assert from_diameter.duration_s.shape == diameter.shape


def test_duration_and_provenance_are_copied_deeply_and_immutable():
    duration = np.array([[10.0, 20.0]])
    provenance = {"scenario": {"notes": ["measured duration"], "number": 1}}
    result = FlameResidenceTime(duration, provenance)
    duration[0, 0] = 99.0
    provenance["scenario"]["notes"].append("later edit")
    assert_array_equal(result.duration_s, [[10.0, 20.0]])
    assert result.provenance["scenario"]["notes"] == ("measured duration",)
    with pytest.raises(ValueError):
        result.duration_s[0, 0] = 2.0
    with pytest.raises(ValueError):
        result.duration_s.setflags(write=True)
    with pytest.raises(TypeError):
        result.provenance["scenario"]["number"] = 2
    with pytest.raises(FrozenInstanceError):
        result.duration_s = 2.0
    mutable_copy = result.provenance_dict()
    json.dumps(mutable_copy, allow_nan=False)
    mutable_copy["scenario"]["notes"].append("copy only")
    assert result.provenance["scenario"]["notes"] == ("measured duration",)


@pytest.mark.parametrize("bad", [
    0, -1, np.nan, np.inf, -np.inf, True, [[False]], "1", [["2"]],
    complex(1, 0), timedelta(seconds=1), [], [1, 2], np.ones((1, 1, 1)),
    np.ma.array([[2.0]], mask=[[True]]),
])
@pytest.mark.parametrize("constructor", [
    lambda value: FlameResidenceTime(value, {"scenario": "test"}),
    FlameResidenceTime.from_particle_diameter,
    FlameResidenceTime.from_surface_area_to_volume,
])
def test_complete_positive_real_scalar_or_map_contract(bad, constructor):
    with pytest.raises(ValueError):
        constructor(bad)


@pytest.mark.parametrize("bad", [None, [], "source", {1: "source"}, {"x": np.nan},
                                {"x": np.array([1.0])}])
def test_provenance_is_a_finite_json_compatible_mapping(bad):
    with pytest.raises(ValueError):
        FlameResidenceTime(10.0, bad)


def test_extreme_valid_inputs_cannot_create_infinite_or_zero_durations():
    with pytest.raises(ValueError):
        FlameResidenceTime.from_particle_diameter(np.finfo(float).max)
    with pytest.raises(ValueError):
        FlameResidenceTime.from_surface_area_to_volume(np.nextafter(0.0, 1.0))


def test_all_forty_models_match_published_rounded_characteristic_sav():
    codes = np.array([
        101, 102, 103, 104, 105, 106, 107, 108, 109,
        121, 122, 123, 124, 141, 142, 143, 144, 145, 146, 147, 148, 149,
        161, 162, 163, 164, 165, 181, 182, 183, 184, 185, 186, 187, 188,
        189, 201, 202, 203, 204,
    ]).reshape(5, 8)
    # Source values from Scott--Burgan fuel-model pages, independently printed
    # again by Andrews (2018), tables 8b--8f. GS4 uses Andrews' 1631 value;
    # Scott--Burgan's GS4 summary has 1674, inconsistent with its table 7.
    expected_sigma_ft_inv = np.array([
        2054, 1820, 1290, 1826, 1631, 2006, 1834, 1302, 1612,
        1832, 1827, 1614, 1631, 1674, 1672, 1371, 1682, 1252, 1144, 1233,
        1386, 1378, 1606, 1767, 1611, 2216, 1224, 1716, 1806, 1532,
        1568, 1713, 1936, 1229, 1770, 1733, 1653, 1884, 1935, 1907,
    ]).reshape(codes.shape)
    result = FlameResidenceTime.from_fbfm40(codes)
    recovered_sigma_ft_inv = (384.0 * 60.0) / result.duration_s
    assert_array_equal(np.rint(recovered_sigma_ft_inv), expected_sigma_ft_inv)
    assert result.provenance["catalog_cell_count"] == 40
    assert result.provenance["fallback_cell_count"] == 0
    assert len(result.provenance["catalog_codes_used"]) == 40
    assert result.duration_s.shape == codes.shape


def test_gr1_zero_load_placeholder_has_no_weight_and_original_unit_law_holds():
    # GR1 carries 0.1 t/ac at sigma2200 and 0.3 t/ac at sigma2000. Its
    # published characteristic sigma is2054, and exact area weighting is
    # 2053.658536585366. The zero-load woody placeholder9999 contributes zero.
    result = FlameResidenceTime.from_fbfm40(101)
    assert_allclose(result.duration_s, 11.219002375296912, rtol=1e-13)
    assert result.duration_s.shape == ()
    assert "preserves SAV" in result.provenance["dynamic_curing"]


@pytest.mark.parametrize("codes", [91, 92, 93, 98, 99, 0, -9999, 13, 250,
                                  [[101, np.nan]], np.ma.array([[101]], mask=True)])
def test_missing_custom_and_nonburnable_models_require_explicit_scenario(codes):
    with pytest.raises(ValueError, match="fallback_sav_m_inv"):
        FlameResidenceTime.from_fbfm40(codes)


def test_explicit_fallback_is_used_only_where_reference_duration_is_unavailable():
    codes = np.ma.array([[101.0, 99.0], [np.nan, 108.0]], mask=[[False, False], [False, True]])
    fallback = np.array([[9000.0, 1000.0], [2000.0, 3000.0]])
    result = FlameResidenceTime.from_fbfm40(codes, fallback_sav_m_inv=fallback,
                                         provenance={"fallback": "specified scenario"})
    expected = FlameResidenceTime.from_surface_area_to_volume(fallback).duration_s.copy()
    expected[0, 0] = FlameResidenceTime.from_fbfm40(101).duration_s
    assert_allclose(result.duration_s, expected)
    assert result.provenance["catalog_cell_count"] == 1
    assert result.provenance["fallback_cell_count"] == 3
    assert result.provenance["missing_code_cell_count"] == 2
    assert result.provenance["unsupported_finite_codes"] == (99,)
    assert result.provenance["fallback_scenario_supplied"] is True
    json.dumps(result.provenance_dict(), allow_nan=False)


@pytest.mark.parametrize("fallback", [0, -1, np.nan, np.inf, True, [2000], [[2000], [3000]]])
def test_fallback_must_be_positive_complete_and_exactly_aligned(fallback):
    with pytest.raises(ValueError):
        FlameResidenceTime.from_fbfm40([[101, 99]], fallback_sav_m_inv=fallback)


@pytest.mark.parametrize("bad_codes", [101.5, [[101.0, 102.1]], "101", True, [[False]], [101, 102]])
def test_fuel_identifiers_are_numeric_integer_scalar_or_maps(bad_codes):
    with pytest.raises(ValueError):
        FlameResidenceTime.from_fbfm40(bad_codes, fallback_sav_m_inv=2000.0)


def test_burrows_jarrah_twig_scenario_records_distinct_domain_and_seconds():
    result = FlameResidenceTime.from_eucalypt_wood_diameter([[1.0, 16.0]])
    # Equation6-1 has seconds at the output and millimetres at the input.
    # 16^(15/8) = 128*sqrt(2), so this boundary has an independent exact form.
    assert_allclose(result.duration_s, [[0.871, 111.488 * np.sqrt(2.0)]], rtol=1e-13)
    metadata = result.provenance_dict()
    assert metadata["tested_diameter_range_mm"] == [1.0, 16.0]
    assert metadata["laboratory_conditions"]["fuel_moisture"] == "oven-dried"
    assert metadata["sources"][0]["author_year"] == "Burrows 1994"
    assert "individual" in metadata["meaning"]
    assert not any("Anderson" in source["author_year"] for source in metadata["sources"])


@pytest.mark.parametrize("bad", [0, 0.999, 16.001, np.nan, np.inf, True,
                                 "1", [[1.0, 17.0]], [1.0, 2.0]])
def test_burrows_diameter_does_not_extrapolate_outside_experiment(bad):
    with pytest.raises(ValueError):
        FlameResidenceTime.from_eucalypt_wood_diameter(bad)


def _fuel_raster(tmp_path, codes=None, *, crs="EPSG:5070", count=1):
    rasterio = pytest.importorskip("rasterio")
    from affine import Affine

    codes = np.array([[101, 102], [108, 165]], dtype=np.int16) if codes is None else np.asarray(codes)
    path = tmp_path / "fuel.tif"
    transform = Affine(375.0, 0.0, 1500.0, 0.0, -375.0, 2250.0)
    with rasterio.open(
        path, "w", driver="GTiff", height=codes.shape[0], width=codes.shape[1],
        count=count, dtype=codes.dtype, crs=crs, transform=transform, nodata=-9999,
    ) as target:
        for band in range(1, count + 1):
            target.write(codes, band)
        target.update_tags(source="LANDFIRE 2016 Remap, LF2.0.0", resampling="mode")
    return path, AffineGrid(tuple(transform)[:6])


def test_fbfm40_raster_preserves_cell_specific_durations_and_hashed_source(tmp_path):
    codes = np.array([[101, 102], [108, 165]], dtype=np.int16)
    path, grid = _fuel_raster(tmp_path, codes)
    result = FlameResidenceTime.from_fbfm40_raster(
        path, grid=grid, expected_shape=(2, 2), epsg=5070,
    )
    assert_allclose(result.duration_s, FlameResidenceTime.from_fbfm40(codes).duration_s)
    metadata = result.provenance_dict()["input_provenance"]
    assert metadata["path"] == str(path.resolve())
    assert metadata["sha256"] == sha256(path.read_bytes()).hexdigest()
    assert metadata["epsg"] == 5070
    assert metadata["transform"] == list(grid.transform)
    assert metadata["shape"] == [2, 2]
    assert metadata["source_tags"]["source"] == "LANDFIRE 2016 Remap, LF2.0.0"
    assert metadata["alignment_checks"] == {"affine_transform": True, "shape": True, "epsg": True}
    assert "not measured" in metadata["physical_definition"]
    json.dumps(result.provenance_dict(), allow_nan=False)


def test_fbfm40_raster_general_loading_records_unspecified_alignment_checks(tmp_path):
    path, _ = _fuel_raster(tmp_path)
    result = FlameResidenceTime.from_fbfm40_raster(path)
    assert result.duration_s.shape == (2, 2)
    assert result.provenance_dict()["input_provenance"]["alignment_checks"] == {
        "affine_transform": False, "shape": False, "epsg": False,
    }


@pytest.mark.parametrize("mismatch, message", [
    ({"grid": AffineGrid.from_cell_size(375.0)}, "affine transform"),
    ({"expected_shape": (1, 4)}, "shape"),
    ({"epsg": 5179}, "CRS"),
])
def test_fbfm40_raster_rejects_spatially_misaligned_duration_maps(tmp_path, mismatch, message):
    path, grid = _fuel_raster(tmp_path)
    options = dict(grid=grid, expected_shape=(2, 2), epsg=5070)
    options.update(mismatch)
    with pytest.raises(ValueError, match=message):
        FlameResidenceTime.from_fbfm40_raster(path, **options)


@pytest.mark.parametrize("crs, message", [
    (None, "projected CRS"),
    ("EPSG:4326", "projected CRS"),
    ("EPSG:2277", "metre linear units"),
])
def test_fbfm40_raster_requires_declared_projected_metre_coordinates(tmp_path, crs, message):
    path, _ = _fuel_raster(tmp_path, crs=crs)
    with pytest.raises(ValueError, match=message):
        FlameResidenceTime.from_fbfm40_raster(path)


def test_fbfm40_raster_rejects_multiple_static_bands(tmp_path):
    path, _ = _fuel_raster(tmp_path, count=2)
    with pytest.raises(ValueError, match="one static band"):
        FlameResidenceTime.from_fbfm40_raster(path)


def test_fbfm40_raster_does_not_turn_missing_or_nonburnable_fuel_into_duration(tmp_path):
    path, grid = _fuel_raster(tmp_path, np.array([[101, 99, -9999]], dtype=np.int16))
    with pytest.raises(ValueError, match="fallback_sav_m_inv"):
        FlameResidenceTime.from_fbfm40_raster(path, grid=grid, expected_shape=(1, 3), epsg=5070)
    result = FlameResidenceTime.from_fbfm40_raster(
        path, grid=grid, expected_shape=(1, 3), epsg=5070,
        fallback_sav_m_inv=2000.0 / 0.3048,
    )
    assert_allclose(result.duration_s, [[11.219002375296912, 11.52, 11.52]])
    assert result.provenance["catalog_cell_count"] == 1
    assert result.provenance["fallback_cell_count"] == 2
    assert result.provenance["missing_code_cell_count"] == 1
    assert result.provenance["unsupported_finite_codes"] == (99,)


@pytest.mark.parametrize("options, message", [
    ({"grid": (375.0, 0.0, 0.0, 0.0, 375.0, 0.0)}, "AffineGrid"),
    ({"expected_shape": True}, "two positive integers"),
    ({"expected_shape": (True, 2)}, "two positive integers"),
    ({"expected_shape": (2.0, 2)}, "two positive integers"),
    ({"expected_shape": (0, 2)}, "two positive integers"),
    ({"epsg": True}, "positive integer"),
    ({"epsg": 5070.0}, "positive integer"),
    ({"epsg": 0}, "positive integer"),
])
def test_fbfm40_raster_validates_alignment_arguments_before_opening_file(options, message):
    with pytest.raises(ValueError, match=message):
        FlameResidenceTime.from_fbfm40_raster("unused.tif", **options)


def test_rasterio_is_optional_for_numeric_residence_and_required_only_for_raster_loading(monkeypatch):
    monkeypatch.setitem(sys.modules, "rasterio", None)
    assert_allclose(FlameResidenceTime.from_fbfm40(101).duration_s, 11.219002375296912)
    with pytest.raises(ImportError, match="optional rasterio dependency"):
        FlameResidenceTime.from_fbfm40_raster("unused.tif")
