"""End-to-end source sums for referenced, path-attenuated radiation."""

import numpy as np
import pytest

from wildfire.heat import AffineGrid, CombustionParameters, ExpectedHeatFluxModel, WildfireHeatModel
from wildfire.heat_transfer import HomogeneousAtmosphere, RadiativeFractionEstimate


def make_radiation_model(*, coefficient=0.07, fraction=0.3, **kwargs):
    return ExpectedHeatFluxModel(
        grid=AffineGrid((2., 0.25, 1000., 0.5, -3., 2000.)),
        heat_release_rate_density_w_m2=np.array([[1200., 2400., 600.], [3000., 800., 1400.]]),
        radiative_fraction=fraction,
        emission_height_m=2.5,
        atmosphere=HomogeneousAtmosphere(coefficient, "explicit synthetic transport scenario"),
        **kwargs,
    )


def independent_source_area_sum(model, activity, points, order=48):
    """Gauss integration in affine source coordinates, independent of Ω tiles."""
    nodes, weights = np.polynomial.legendre.leggauss(order)
    u, v = nodes[:, None]/2, nodes[None, :]/2
    area_weights = weights[:, None]*weights[None, :]*model.grid.cell_area_m2/4
    column, row = model.grid.column_vector_m, model.grid.row_vector_m
    offset_x = u*column[0]+v*row[0]
    offset_y = u*column[1]+v*row[1]
    strengths = (np.asarray(activity)*model.heat_release_rate_density_w_m2*model.radiative_fraction).ravel()
    centers = model.grid.centers(np.asarray(activity).shape).reshape(-1, 2)
    coefficient = 0 if model.atmosphere is None else model.atmosphere.absorption_coefficient_m_inv
    height = model.height_separation_m
    flux = np.zeros(len(points))
    for receiver_index, point in enumerate(points):
        for center, strength in zip(centers, strengths):
            x = center[0]-point[0]+offset_x
            y = center[1]-point[1]+offset_y
            distance = np.sqrt(x*x+y*y+height*height)
            integrand = height*np.exp(-coefficient*distance)/(4*np.pi*distance**3)
            flux[receiver_index] += strength*np.sum(area_weights*integrand)
    return flux*model.atmospheric_transmissivity


def test_attenuated_fft_and_independent_point_target_paths_agree_at_cell_centers():
    activity = np.array([[0.2, 0.8, 0.0], [1.0, 0.1, 0.5]])
    model = make_radiation_model()
    grid_result = model.predict_details(activity)
    point_result = model.predict_at_points_details(
        activity, model.grid.centers(activity.shape).reshape(-1, 2),
        target_chunk_size=2, source_chunk_size=2,
    )
    for name in ("incident_heat_flux_w_m2", "incident_heat_flux_lower_bound_w_m2", "incident_heat_flux_upper_bound_w_m2"):
        np.testing.assert_allclose(getattr(point_result, name).reshape(activity.shape),
                                   getattr(grid_result, name), rtol=2e-13, atol=1e-11)
    assert np.all(grid_result.incident_heat_flux_lower_bound_w_m2 < grid_result.incident_heat_flux_upper_bound_w_m2)
    assert point_result.expected_total_radiant_power_w == grid_result.expected_total_radiant_power_w


def test_attenuated_flux_encloses_independent_area_quadrature_for_all_receivers():
    activity = np.array([[0.2, 0.8, 0.0], [1.0, 0.1, 0.5]])
    model = make_radiation_model()
    points = np.vstack((model.grid.centers(activity.shape).reshape(-1, 2), [[1001.25, 1995.5]]))
    result = model.predict_at_points_details(activity, points)
    exact = independent_source_area_sum(model, activity, points)
    refined = independent_source_area_sum(model, activity, points, order=96)
    np.testing.assert_allclose(exact, refined, rtol=3e-13, atol=1e-10)
    assert np.all(result.incident_heat_flux_lower_bound_w_m2 <= refined)
    assert np.all(refined <= result.incident_heat_flux_upper_bound_w_m2)
    assert np.all(np.abs(result.incident_heat_flux_w_m2-refined) <=
                  (result.incident_heat_flux_upper_bound_w_m2-result.incident_heat_flux_lower_bound_w_m2)/2)


def test_zero_absorption_reproduces_exact_transparent_grid_and_point_baselines():
    activity = np.array([[0.2, 0.8, 0.0], [1.0, 0.1, 0.5]])
    with_zero = make_radiation_model(coefficient=0)
    baseline = ExpectedHeatFluxModel(
        grid=with_zero.grid, heat_release_rate_density_w_m2=with_zero.heat_release_rate_density_w_m2,
        radiative_fraction=with_zero.radiative_fraction, emission_height_m=with_zero.emission_height_m,
    )
    points = with_zero.grid.centers(activity.shape).reshape(-1, 2)
    for method, arguments in (("predict_details", (activity,)), ("predict_at_points_details", (activity, points))):
        result, exact = getattr(with_zero, method)(*arguments), getattr(baseline, method)(*arguments)
        np.testing.assert_array_equal(result.incident_heat_flux_w_m2, exact.incident_heat_flux_w_m2)
        np.testing.assert_array_equal(result.incident_heat_flux_lower_bound_w_m2, result.incident_heat_flux_upper_bound_w_m2)
        assert result.provenance_dict()["integration"] == "exact_solid_angle"


def test_unknown_activity_bounds_include_attenuation_integration_enclosures():
    model = WildfireHeatModel(
        None, grid=AffineGrid.from_cell_size(2.),
        combustion=CombustionParameters(1., 18e6, 1800., consumed_fraction=0.4),
        radiative_fraction=0.3, emission_height_m=2.5,
        atmosphere=HomogeneousAtmosphere(0.07, "synthetic scenario"),
    )
    unknown = model.predict_from_new_burn_probability_details([[0.4, np.nan]])
    known_low = model.predict_from_new_burn_probability_details([[0.4, 0.]])
    known_high = model.predict_from_new_burn_probability_details([[0.4, 1.]])
    assert not unknown.complete and np.isnan(unknown.expected_heat_flux_w_m2).all()
    # Uniform initiation with T/D=1/2 gives m=q*(1/2-1/8)=3q/8.
    activity_low, activity_high = np.array([[0.15, 0.]]), np.array([[0.15, 0.375]])
    points = model.heat_model.grid.centers(activity_low.shape).reshape(-1, 2)
    independent_low = independent_source_area_sum(model.heat_model, activity_low, points).reshape(activity_low.shape)
    independent_high = independent_source_area_sum(model.heat_model, activity_high, points).reshape(activity_high.shape)
    assert np.all(unknown.heat_flux_lower_bound_w_m2 <= independent_low)
    assert np.all(independent_high <= unknown.heat_flux_upper_bound_w_m2)
    np.testing.assert_allclose(unknown.heat_flux_lower_bound_w_m2, known_low.heat_flux_lower_bound_w_m2)
    np.testing.assert_allclose(unknown.heat_flux_upper_bound_w_m2, known_high.heat_flux_upper_bound_w_m2)
    assert np.all(unknown.heat_flux_lower_bound_w_m2 < known_low.expected_heat_flux_w_m2)
    assert np.all(known_high.expected_heat_flux_w_m2 < unknown.heat_flux_upper_bound_w_m2)
    assert "integration enclosures" in unknown.metadata["numerical_integration"]["policy"]


def test_scalar_transmission_and_path_atmosphere_cannot_be_combined():
    with pytest.raises(ValueError, match="choose either"):
        make_radiation_model(atmospheric_transmissivity=0.8)
    with pytest.raises(TypeError, match="HomogeneousAtmosphere"):
        ExpectedHeatFluxModel(
            grid=AffineGrid.from_cell_size(2.), heat_release_rate_density_w_m2=1.,
            radiative_fraction=0.3, emission_height_m=2.5, atmosphere=0.8,
        )


def test_fraction_reference_provenance_survives_the_radiation_result():
    fraction = RadiativeFractionEstimate.pine_litter_reference()
    model = make_radiation_model(fraction=fraction)
    result = model.predict_details(np.ones((2, 3)))
    record = result.provenance_dict()["radiative_fraction"]
    assert record == fraction.metadata()
    assert record["provenance"]["doi"] == "10.1007/s10694-016-0632-0"
    record["provenance"]["scope"] = "mutated exported copy"
    assert result.provenance_dict()["radiative_fraction"] == fraction.metadata()
