"""Fuel-unit, spatial alignment, and ecological missingness contract checks."""

from hashlib import sha256

import numpy as np
import pytest
from numpy.testing import assert_allclose

from wildfire.heat import FCCS_TONS_PER_ACRE_TO_KG_M2
from wildfire.heat import EcologicalFuelMaps
from wildfire.heat import AffineGrid

rasterio = pytest.importorskip("rasterio")
from rasterio.transform import Affine


def raster_pair(tmp_path, loading, coverage, *, crs="EPSG:5070", transform=None):
    transform = transform or Affine(375, 0, 1200000, 0, -375, 1800000)
    paths = [tmp_path / "loading.tif", tmp_path / "coverage.tif"]
    for path, values in zip(paths, (loading, coverage)):
        data = np.array(values, dtype=np.float64)
        with rasterio.open(
            path, "w", driver="GTiff", count=1, height=data.shape[0],
            width=data.shape[1], dtype="float64", crs=crs, transform=transform,
            nodata=-9999,
        ) as destination:
            destination.write(data, 1)
    return paths


def combustion(fuel, **kwargs):
    return fuel.combustion_parameters(
        heat_of_combustion_j_kg=18e6, burning_duration_s=60,
        consumed_fraction=0.5, **kwargs,
    )


def test_loading_si_conversion_alignment_provenance_and_combustion(tmp_path):
    paths = raster_pair(tmp_path, [[1, 2], [3, 4]], np.ones((2, 2)))
    grid = AffineGrid((375, 0, 1200000, 0, -375, 1800000))
    fuel = EcologicalFuelMaps.from_fccs_rasters(*paths, grid=grid, expected_shape=(2, 2))
    assert_allclose(FCCS_TONS_PER_ACRE_TO_KG_M2, 0.2241702312388912, rtol=0, atol=1e-16)
    assert_allclose(fuel.fuel_load_kg_m2, np.array([[1, 2], [3, 4]]) * 0.2241702312388912)
    assert np.all(fuel.valid)
    assert fuel.provenance["loading_sha256"] == sha256(paths[0].read_bytes()).hexdigest()
    assert fuel.provenance["coverage_sha256"] == sha256(paths[1].read_bytes()).hexdigest()
    assert fuel.provenance["shape"] == [2, 2]
    assert "not measured" in fuel.provenance["physical_definition"]
    assert_allclose(combustion(fuel).heat_release_rate_density_w_m2, fuel.fuel_load_kg_m2 * 150000)


def test_partial_mean_preserved_and_fallback_only_fills_unmapped_fraction(tmp_path):
    paths = raster_pair(tmp_path, [[10, 20, 30]], [[1, 0.5, 0]])
    fuel = EcologicalFuelMaps.from_fccs_rasters(*paths)
    mapped = np.array([[10, 20, 30]]) * FCCS_TONS_PER_ACRE_TO_KG_M2
    assert_allclose(fuel.fuel_load_kg_m2, mapped)
    assert np.array_equal(fuel.valid, [[True, False, False]])
    assert_allclose(fuel.fuel_load_lower_bound_kg_m2, mapped * [[1, 0.5, 0]])
    with pytest.raises(ValueError, match="incomplete fuel coverage"):
        combustion(fuel)
    result = combustion(fuel, fallback_fuel_load_kg_m2=2)
    assert_allclose(result.fuel_load_kg_m2, [[mapped[0, 0], 0.5 * mapped[0, 1] + 1, 2]])
    assert_allclose(fuel.fuel_load_kg_m2, mapped)


def test_nodata_invalid_physics_and_explicit_fallback(tmp_path):
    paths = raster_pair(
        tmp_path, [[-9999, -1, 10, 10, np.nan, 0]],
        [[1, 1, -0.2, 1.1, 0.4, 1]],
    )
    fuel = EcologicalFuelMaps.from_fccs_rasters(*paths)
    assert np.array_equal(fuel.valid, [[False, False, False, False, False, True]])
    assert np.isnan(fuel.fuel_load_kg_m2[0, :2]).all()
    assert np.isnan(fuel.coverage_fraction[0, 2:4]).all()
    assert np.isnan(fuel.fuel_load_kg_m2[0, 4])
    assert_allclose(fuel.fuel_load_lower_bound_kg_m2, [[0, 0, 0, 0, 0, 0]])
    fallback = np.array([[1, 2, 3, 4, 5, 6]])
    assert_allclose(combustion(fuel, fallback_fuel_load_kg_m2=fallback).fuel_load_kg_m2,
                    [[1, 2, 3, 4, 5, 0]])


@pytest.mark.parametrize("coverage", [0.999998, 0.9999995, 1.0])
def test_full_coverage_tolerance(tmp_path, coverage):
    paths = raster_pair(tmp_path, [[2]], [[coverage]])
    fuel = EcologicalFuelMaps.from_fccs_rasters(*paths)
    assert bool(fuel.valid[0, 0]) == (coverage >= 1 - 1e-6)
    strict = EcologicalFuelMaps.from_fccs_rasters(*paths, full_coverage_tolerance=0)
    assert bool(strict.valid[0, 0]) == (coverage == 1)


@pytest.mark.parametrize("tolerance", [-1, 1, np.nan, np.inf, True])
def test_invalid_coverage_tolerance_rejected(tmp_path, tolerance):
    paths = raster_pair(tmp_path, [[1]], [[1]])
    with pytest.raises(ValueError, match="full_coverage_tolerance"):
        EcologicalFuelMaps.from_fccs_rasters(*paths, full_coverage_tolerance=tolerance)


@pytest.mark.parametrize("crs", [None, "EPSG:4326", "EPSG:2263"])
def test_nonmetric_or_missing_crs_rejected(tmp_path, crs):
    paths = raster_pair(tmp_path, [[1]], [[1]], crs=crs)
    with pytest.raises(ValueError, match="metre"):
        EcologicalFuelMaps.from_fccs_rasters(*paths)


@pytest.mark.parametrize("kind", ["shape", "transform", "crs"])
def test_two_rasters_must_match_exactly(tmp_path, kind):
    paths = raster_pair(tmp_path, [[1, 1]], [[1, 1]])
    with rasterio.open(paths[1]) as source:
        profile = source.profile
        data = source.read(1)
    if kind == "shape":
        profile.update(width=1)
        data = data[:, :1]
    elif kind == "transform":
        profile.update(transform=Affine(375, 0, 1200001, 0, -375, 1800000))
    else:
        profile.update(crs="EPSG:5179")
    with rasterio.open(paths[1], "w", **profile) as destination:
        destination.write(data, 1)
    with pytest.raises(ValueError, match={"shape": "shapes", "transform": "transforms", "crs": "CRS"}[kind]):
        EcologicalFuelMaps.from_fccs_rasters(*paths)


def test_grid_shape_and_shape_type_contracts(tmp_path):
    paths = raster_pair(tmp_path, [[1, 1]], [[1, 1]])
    with pytest.raises(ValueError, match="does not match grid"):
        EcologicalFuelMaps.from_fccs_rasters(*paths, grid=AffineGrid.from_cell_size(375))
    with pytest.raises(ValueError, match="expected_shape"):
        EcologicalFuelMaps.from_fccs_rasters(*paths, expected_shape=(2, 1))
    with pytest.raises(ValueError, match="positive integers"):
        EcologicalFuelMaps.from_fccs_rasters(*paths, expected_shape=(1.0, 2))
    with pytest.raises(ValueError, match="AffineGrid"):
        EcologicalFuelMaps.from_fccs_rasters(*paths, grid=(375, 0, 0, 0, -375, 0))


@pytest.mark.parametrize("fallback", [-1, np.nan, np.inf, [[1], [2]], [1 + 2j]])
def test_fallback_physical_and_shape_validation(tmp_path, fallback):
    paths = raster_pair(tmp_path, [[1, 2]], [[0.5, 0.5]])
    fuel = EcologicalFuelMaps.from_fccs_rasters(*paths)
    with pytest.raises(ValueError, match="fallback_fuel_load_kg_m2"):
        combustion(fuel, fallback_fuel_load_kg_m2=fallback)


def test_combustion_rejects_added_time_or_batch_dimensions(tmp_path):
    paths = raster_pair(tmp_path, [[1, 2]], [[1, 1]])
    fuel = EcologicalFuelMaps.from_fccs_rasters(*paths)
    with pytest.raises(ValueError, match="fuel-map shape"):
        fuel.combustion_parameters(
            heat_of_combustion_j_kg=np.ones((2, 1, 2)) * 18e6,
            burning_duration_s=60, consumed_fraction=0.5,
        )


def test_direct_constructor_masks_copy_and_validity():
    source = np.ma.array([[1, 2]], mask=[[False, True]])
    fuel = EcologicalFuelMaps(source, [[True, False]], [[1, 1]], {})
    source[0, 0] = 50
    assert fuel.fuel_load_kg_m2[0, 0] == 1
    assert np.isnan(fuel.fuel_load_kg_m2[0, 1])
    with pytest.raises(ValueError, match="partially covered"):
        EcologicalFuelMaps([[1]], [[True]], [[0.5]], {})
    with pytest.raises(ValueError, match="invalid fuel"):
        EcologicalFuelMaps([[np.nan]], [[True]], [[1]], {})
    with pytest.raises(ValueError, match="boolean matrix"):
        EcologicalFuelMaps([[1]], [[1]], [[1]], {})


def test_single_static_band_requirement(tmp_path):
    paths = raster_pair(tmp_path, [[1]], [[1]])
    with rasterio.open(paths[0]) as source:
        profile = source.profile
    profile.update(count=2)
    with rasterio.open(paths[0], "w", **profile) as destination:
        destination.write(np.ones((2, 1, 1)))
    with pytest.raises(ValueError, match="one static band"):
        EcologicalFuelMaps.from_fccs_rasters(*paths)
