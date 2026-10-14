"""Referenced parameter semantics and independent transfer-integral checks."""

from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from wildfire.heat import AffineGrid, ExpectedHeatFluxModel
from wildfire.heat_transfer import (
    HomogeneousAtmosphere,
    RadiativeFractionEstimate,
    attenuated_cell_transfer,
)


def transfer(dx=0., dy=0., *, coefficient=0.1, column=(2., 0.), row=(0., 3.), height=1., **kwargs):
    return attenuated_cell_transfer(
        dx, dy, column_vector_m=column, row_vector_m=row,
        height_separation_m=height,
        atmosphere=HomogeneousAtmosphere(coefficient, "synthetic test; not calibrated"),
        **kwargs,
    )


def test_pine_litter_reference_has_narrow_primary_source_provenance():
    estimate = RadiativeFractionEstimate.pine_litter_reference()
    assert float(estimate.fraction) == 0.3
    metadata = estimate.metadata()
    assert metadata["provenance"]["doi"] == "10.1007/s10694-016-0632-0"
    assert "not event calibration" in metadata["provenance"]["limitation"]
    assert metadata["provenance"]["online_publication_year"] == 2016
    with pytest.raises(FrozenInstanceError):
        estimate.fraction = 0.4
    with pytest.raises(ValueError):
        estimate.fraction.setflags(write=True)
    with pytest.raises(TypeError):
        estimate.provenance["scope"] = "universal"


def test_matched_energy_budget_preserves_complete_maps_and_energy_semantics():
    radiant = np.array([[1., 2.], [0., 4.]])
    estimate = RadiativeFractionEstimate.from_energy_budget(
        radiant, [[2., 5.], [1., 4.]], provenance={"experiment": "synthetic"},
    )
    radiant[:] = 0
    np.testing.assert_array_equal(estimate.fraction, [[0.5, 0.4], [0, 1]])
    assert "energy-integrated" in estimate.provenance["time_semantics"]
    assert "not theoretical gross" in estimate.provenance["denominator"]


@pytest.mark.parametrize("radiant,total", [
    (-1, 2), (3, 2), (0, 0), (np.nan, 2), (1, np.inf),
    ([1, 2], [2, 3]), ([[1]], 2), ([[1, 2]], [[2], [3]]),
    (1+1j, 2), (np.ma.array([[1]], mask=[[True]]), [[2]]),
])
def test_energy_budget_rejects_missing_invalid_or_broadcast_inputs(radiant, total):
    with pytest.raises(ValueError):
        RadiativeFractionEstimate.from_energy_budget(radiant, total, provenance="test")


@pytest.mark.parametrize("fraction", [-0.1, 1.1, np.nan, np.inf, 1j, [0.3], np.empty((0, 1))])
def test_fraction_validation(fraction):
    with pytest.raises(ValueError):
        RadiativeFractionEstimate(fraction, "test")


def test_atmosphere_reference_calibration_and_transmission_properties():
    atmosphere = HomogeneousAtmosphere.from_reference_transmission(
        0.8, 100., provenance={"measurement": "synthetic matched spectrum"},
    )
    assert atmosphere.absorption_coefficient_m_inv == pytest.approx(-np.log(0.8)/100.)
    np.testing.assert_allclose(atmosphere.transmission([0, 100, 200]), [1, 0.8, 0.64])
    assert atmosphere.metadata()["transport_source"]["doi"] == "10.6028/NIST.GCR.09-922"
    with pytest.raises(FrozenInstanceError):
        atmosphere.absorption_coefficient_m_inv = 0
    with pytest.raises(ValueError):
        atmosphere.transmission([-1])


@pytest.mark.parametrize("coefficient", [-1, np.nan, np.inf, [0.1], 1j])
def test_atmosphere_coefficient_validation(coefficient):
    with pytest.raises(ValueError):
        HomogeneousAtmosphere(coefficient, "test")


@pytest.mark.parametrize("transmission,distance", [(0, 1), (-1, 1), (1.1, 1), (0.5, 0), (0.5, -1), (np.nan, 1)])
def test_reference_path_validation(transmission, distance):
    with pytest.raises(ValueError):
        HomogeneousAtmosphere.from_reference_transmission(transmission, distance, provenance="test")


def test_transparent_transfer_matches_existing_exact_affine_solid_angle():
    column, row = (2., 0.7), (0.3, -3.)
    grid = AffineGrid((column[0], row[0], 0., column[1], row[1], 0.))
    model = ExpectedHeatFluxModel(grid=grid, heat_release_rate_density_w_m2=1,
                                 radiative_fraction=1, emission_height_m=1)
    dx, dy = np.array([0., 1., 100.]), np.array([0., -2., 30.])
    result = transfer(dx, dy, coefficient=0, column=column, row=row)
    exact = model._cell_transfer(dx, dy)
    np.testing.assert_allclose(result.midpoint, exact, rtol=1e-14, atol=0)
    np.testing.assert_array_equal(result.lower_bound, result.upper_bound)


@pytest.mark.parametrize("dx,dy,column,row,height,coefficient", [
    (0., 0., (2., 0.), (0., 3.), 0.7, 0.3),
    (2.5, -1., (1.5, 0.4), (0.3, -2.), 1.2, 0.12),
    (0., 0., (250., 0.), (0., 2.), 0.2, 0.003),
])
def test_enclosure_contains_independent_source_area_integral(dx, dy, column, row, height, coefficient):
    integrate = pytest.importorskip("scipy.integrate")
    area = abs(column[0]*row[1] - column[1]*row[0])
    def integrand(v, u):
        x = dx + u*column[0] + v*row[0]
        y = dy + u*column[1] + v*row[1]
        distance = np.sqrt(x*x+y*y+height*height)
        return area*height*np.exp(-coefficient*distance)/(4*np.pi*distance**3)
    exact, error = integrate.dblquad(integrand, -0.5, 0.5, lambda _: -0.5, lambda _: 0.5,
                                     epsabs=1e-10, epsrel=1e-10)
    result = transfer(dx, dy, coefficient=coefficient, column=column, row=row, height=height)
    assert float(result.lower_bound) - error <= exact <= float(result.upper_bound) + error
    width = float(result.upper_bound - result.lower_bound)
    assert width <= 1e-7 + 1e-2*float(result.lower_bound)
    assert abs(float(result.midpoint)-exact) <= width/2 + error


def test_375m_same_cell_converges_and_reports_bounded_numerical_error():
    result = transfer(column=(375., 0.), row=(0., -375.), height=2., coefficient=1e-3)
    assert 0 < float(result.lower_bound) < float(result.upper_bound) < 0.5
    assert float(result.upper_bound-result.lower_bound) <= 1e-7 + 1e-2*float(result.lower_bound)


def test_attenuation_is_monotone_with_coefficient_within_quadrature_enclosures():
    transparent = transfer(coefficient=0)
    weak = transfer(coefficient=0.1)
    strong = transfer(coefficient=0.5)
    assert float(strong.upper_bound) < float(weak.lower_bound)
    assert float(weak.upper_bound) < float(transparent.midpoint)


def test_rotation_preserves_bounds_for_sheared_cell():
    column, row, center = np.array([2., 0.7]), np.array([0.3, -3.]), np.array([1., 4.])
    theta = 0.5
    rotation = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])
    original = transfer(*center, column=column, row=row)
    rotated = transfer(*(rotation@center), column=rotation@column, row=rotation@row)
    np.testing.assert_allclose(rotated.lower_bound, original.lower_bound, rtol=1e-12)
    np.testing.assert_allclose(rotated.upper_bound, original.upper_bound, rtol=1e-12)


def test_array_displacements_broadcast_and_immutable_results():
    result = transfer(np.array([[0.], [2.]]), np.array([[0., 3.]]), coefficient=0)
    assert result.midpoint.shape == (2, 2)
    with pytest.raises(ValueError):
        result.midpoint.setflags(write=True)


@pytest.mark.parametrize("kwargs", [
    {"height": 0}, {"height": -1}, {"column": (1., 0.), "row": (2., 0.)},
    {"column": (1.,)}, {"atol": -1}, {"rtol": -1}, {"atol": 0, "rtol": 0},
    {"chunk_size": 0}, {"max_tiles": True}, {"max_depth": 0},
])
def test_geometry_and_tolerance_validation(kwargs):
    with pytest.raises(ValueError):
        transfer(**kwargs)


def test_insufficient_leaf_and_depth_budgets_fail_explicitly():
    with pytest.raises(ValueError, match="max_tiles"):
        transfer(max_tiles=1)
    with pytest.raises(ValueError, match="max_depth"):
        transfer(max_depth=1, atol=1e-10, rtol=1e-10)
