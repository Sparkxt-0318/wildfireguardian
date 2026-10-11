"""Physics and API checks independent of the implementation's FFT/triangle code."""

from __future__ import annotations

import numpy as np
import pytest
from numpy.testing import assert_allclose

from wildfire.heat import AffineGrid
from wildfire.heat import CombustionParameters
from wildfire.heat import ExpectedHeatFluxModel
from wildfire.heat import integrate_heat_flux


def make_model(**overrides):
    parameters = dict(
        grid=AffineGrid.from_cell_size(2.0),
        heat_release_rate_density_w_m2=20_000.0,
        radiative_fraction=0.3,
        emission_height_m=3.0,
    )
    parameters.update(overrides)
    return ExpectedHeatFluxModel(**parameters)


def test_heat_grid_tuple_contains_cell_center_latitude_longitude_and_identical_flux():
    # UTM zone 52N has easting 500000 at longitude 129 at the equator.
    # The first pixel center is exactly (500000 m, 0 m).
    model = make_model(grid=AffineGrid((20.0, 0.0, 499990.0, 0.0, -20.0, 10.0)), epsg=32652)
    probabilities = np.array([[0.0, 0.7], [0.3, 1.0]])
    flux, coordinates = model.predict(probabilities)
    details = model.predict_details(probabilities)
    assert flux.shape == probabilities.shape
    assert coordinates.shape == probabilities.shape + (2,)
    assert coordinates.dtype == np.float64
    assert_allclose(flux, details.incident_heat_flux_w_m2, rtol=0, atol=0)
    assert_allclose(coordinates[0, 0], [0.0, 129.0], atol=1e-12)
    assert coordinates[0, 1, 1] > coordinates[0, 0, 1]
    assert coordinates[1, 0, 0] < coordinates[0, 0, 0]
    assert np.isfinite(coordinates).all()


def test_heat_point_tuple_contains_the_receiver_locations_and_identical_flux():
    model = make_model(epsg=32652)
    points = np.array([[500000.0, 0.0], [500020.0, 0.0]])
    flux, coordinates = model.predict_at_points([[0.5]], points)
    assert flux.shape == (2,)
    assert coordinates.shape == (2, 2)
    assert_allclose(coordinates[0], [0.0, 129.0], atol=1e-12)
    assert_allclose(flux, model.predict_at_points_details([[0.5]], points).incident_heat_flux_w_m2)
    empty_flux, empty_coordinates = model.predict_at_points([[0.5]], np.empty((0, 2)))
    assert empty_flux.shape == (0,)
    assert empty_coordinates.shape == (0, 2)


def test_heat_geographic_output_requires_an_explicit_geographic_grid_crs():
    model = make_model()
    with pytest.raises(ValueError, match="requires epsg"):
        model.predict([[0.5]])
    with pytest.raises(ValueError, match="requires epsg"):
        model.predict_at_points([[0.5]], [[0.0, 0.0]])
    assert np.isfinite(model.predict_details([[0.5]]).incident_heat_flux_w_m2).all()


@pytest.mark.parametrize("epsg", [4326, 2227, True, 32652.0, -1, "32652"])
def test_heat_constructor_rejects_nonmetric_or_ambiguous_epsg(epsg):
    with pytest.raises(ValueError):
        make_model(epsg=epsg)


def rectangle_solid_angle(half_width, half_height, separation):
    """Exact solid angle of a centered horizontal rectangle."""
    return 4.0 * np.arctan2(
        half_width * half_height,
        separation * np.sqrt(separation**2 + half_width**2 + half_height**2),
    )


def quadrature_flux(model, probability, receivers):
    """Independent area integral of h/(4*pi*distance**3) over each cell.

    Tensor Gauss-Legendre quadrature uses the grid's two edge vectors; no solid
    angle calculation, model transfer kernel, FFT, or point predictor is used.
    """
    nodes, weights = np.polynomial.legendre.leggauss(28)
    nodes = 0.5 * nodes
    weights = 0.5 * weights
    column = np.asarray(model.grid.column_vector_m)
    row = np.asarray(model.grid.row_vector_m)
    offsets = nodes[:, None, None] * column + nodes[None, :, None] * row
    area_weights = weights[:, None] * weights[None, :] * model.grid.cell_area_m2
    centers = model.grid.centers(probability.shape)
    sources = (
        probability
        * model.heat_release_rate_density_w_m2
        * model.radiative_fraction
    )
    answer = np.zeros(len(receivers))
    height = model.height_separation_m
    for index in np.ndindex(probability.shape):
        locations = centers[index] + offsets
        displacement = locations[None, :, :, :] - receivers[:, None, None, :]
        distance_squared = np.sum(displacement**2, axis=-1) + height**2
        transfer = height / (4.0 * np.pi * distance_squared**1.5)
        answer += sources[index] * np.sum(transfer * area_weights, axis=(1, 2))
    return answer * model.atmospheric_transmissivity


def test_zero_probability_zero_radiative_fraction_and_zero_transmission():
    probability = np.zeros((3, 4))
    result = make_model().predict_details(probability)
    assert_allclose(result.incident_heat_flux_w_m2, probability, atol=0)
    assert result.expected_total_radiant_power_w == 0.0
    assert_allclose(
        make_model(radiative_fraction=0.0).predict_details(np.ones((3, 4))).incident_heat_flux_w_m2,
        probability,
        atol=0,
    )
    extinguished_path = make_model(atmospheric_transmissivity=0.0).predict_details(np.ones((3, 4)))
    assert_allclose(extinguished_path.incident_heat_flux_w_m2, probability, atol=0)
    assert extinguished_path.expected_total_radiant_power_w == 12 * 4 * 20_000 * 0.3


def test_probability_and_source_strength_linearity():
    rng = np.random.default_rng(246)
    first = rng.uniform(0, 0.4, (3, 5))
    second = rng.uniform(0, 0.4, (3, 5))
    model = make_model(
        heat_release_rate_density_w_m2=rng.uniform(5_000, 30_000, (3, 5)),
        radiative_fraction=rng.uniform(0.1, 0.4, (3, 5)),
    )
    first_result = model.predict_details(first)
    second_result = model.predict_details(second)
    combined = model.predict_details(first + second)
    assert_allclose(
        combined.incident_heat_flux_w_m2,
        first_result.incident_heat_flux_w_m2 + second_result.incident_heat_flux_w_m2,
        rtol=1e-13,
    )
    assert_allclose(
        model.predict_details(0.25 * first).incident_heat_flux_w_m2,
        0.25 * first_result.incident_heat_flux_w_m2,
        rtol=1e-13,
    )
    assert_allclose(
        combined.expected_total_radiant_power_w,
        first_result.expected_total_radiant_power_w + second_result.expected_total_radiant_power_w,
    )


def test_expectation_does_not_require_independent_burning_cells():
    model = make_model()
    marginal_probability = np.array([[0.4, 0.4]])
    expected = model.predict_details(marginal_probability).incident_heat_flux_w_m2
    # Perfect correlation: both cells burn together with probability 0.4.
    correlated = (
        0.4 * model.predict_details([[1.0, 1.0]]).incident_heat_flux_w_m2
        + 0.6 * model.predict_details([[0.0, 0.0]]).incident_heat_flux_w_m2
    )
    # Mutually exclusive burning: exactly one burns with probability 0.8.
    exclusive = (
        0.4 * model.predict_details([[1.0, 0.0]]).incident_heat_flux_w_m2
        + 0.4 * model.predict_details([[0.0, 1.0]]).incident_heat_flux_w_m2
        + 0.2 * model.predict_details([[0.0, 0.0]]).incident_heat_flux_w_m2
    )
    assert_allclose(correlated, expected, rtol=1e-13)
    assert_allclose(exclusive, expected, rtol=1e-13)


@pytest.mark.parametrize("separation", [1e-5, 0.2, 3.0, 10_000.0])
def test_single_rectangle_matches_analytic_solid_angle(separation):
    model = make_model(
        grid=AffineGrid.from_cell_size((4.0, 6.0)),
        emission_height_m=separation,
    )
    result = model.predict_details([[0.7]])
    expected = (
        0.7 * 20_000.0 * 0.3
        * rectangle_solid_angle(3.0, 2.0, separation) / (4.0 * np.pi)
    )
    # Near the source plane, the triangle denominator subtracts comparable
    # terms; allow several more rounding units while checking the finite limit.
    tolerance = 2e-11 if separation < 1e-4 else 1e-12
    assert_allclose(result.incident_heat_flux_w_m2, [[expected]], rtol=tolerance)
    assert result.incident_heat_flux_w_m2[0, 0] <= 0.5 * 0.7 * 20_000 * 0.3
    assert result.expected_total_radiant_power_w == pytest.approx(0.7 * 20_000 * 0.3 * 24)


def test_corner_impulse_fft_has_no_wrap_and_matches_independent_integral():
    probability = np.zeros((3, 7))
    probability[0, 0] = 1.0
    model = make_model()
    receivers = model.grid.centers(probability.shape).reshape(-1, 2)
    expected = quadrature_flux(model, probability, receivers).reshape(probability.shape)
    actual = model.predict_details(probability).incident_heat_flux_w_m2
    assert_allclose(actual, expected, rtol=3e-12, atol=1e-11)
    assert actual[0, -1] < actual[0, 1] / 20.0


@pytest.mark.parametrize(
    "transform",
    [
        (0.0, -3.0, 80.0, 2.0, 0.0, -40.0),  # rotated, area 6 m^2
        (2.0, 0.6, 10.0, 0.4, -1.5, 20.0),  # shear + reversed row direction
    ],
)
def test_affine_grid_geometry_and_radiation_against_quadrature(transform):
    grid = AffineGrid(transform)
    a, b, c, d, e, f = transform
    assert grid.cell_area_m2 == pytest.approx(abs(a * e - b * d))
    assert_allclose(grid.centers((2, 3))[0, 0], [0.5 * (a + b) + c, 0.5 * (d + e) + f])
    assert_allclose(grid.centers((2, 3))[1, 2], [2.5 * a + 1.5 * b + c, 2.5 * d + 1.5 * e + f])
    probability = np.array([[0.1, 0.3, 0.8], [0.5, 0.0, 1.0]])
    model = make_model(grid=grid, atmospheric_transmissivity=0.72)
    receivers = grid.centers(probability.shape).reshape(-1, 2)
    expected = quadrature_flux(model, probability, receivers)
    assert_allclose(model.predict_details(probability).incident_heat_flux_w_m2.ravel(), expected, rtol=3e-12)
    assert_allclose(
        model.predict_at_points_details(probability, receivers, target_chunk_size=2, source_chunk_size=2)
        .incident_heat_flux_w_m2,
        expected,
        rtol=3e-12,
    )


def test_rectangular_spacing_row_direction_and_translation_invariance():
    first_grid = AffineGrid.from_cell_size((3.0, 5.0), origin_xy_m=(100.0, 200.0), row_direction=-1)
    assert_allclose(first_grid.centers((2, 2)), [[[102.5, 198.5], [107.5, 198.5]], [[102.5, 195.5], [107.5, 195.5]]])
    assert first_grid.cell_area_m2 == 15.0
    translated = AffineGrid.from_cell_size((3.0, 5.0), origin_xy_m=(-400.0, 1200.0), row_direction=-1)
    probability = np.array([[0.1, 0.9], [0.4, 0.7]])
    assert_allclose(
        make_model(grid=first_grid).predict_details(probability).incident_heat_flux_w_m2,
        make_model(grid=translated).predict_details(probability).incident_heat_flux_w_m2,
        rtol=1e-14,
    )


def test_arbitrary_points_match_independent_cell_integrals_and_chunks():
    model = make_model()
    probability = np.array([[0.4, 0.0], [0.9, 0.3]])
    receivers = np.array([[-5.0, -3.0], [1.2, 0.7], [4.0, 5.0], [12.0, 8.0]])
    reference = quadrature_flux(model, probability, receivers)
    for target_chunk, source_chunk in [(1, 1), (3, 2), (128, 1024)]:
        actual = model.predict_at_points_details(
            probability, receivers,
            target_chunk_size=target_chunk, source_chunk_size=source_chunk,
        )
        assert_allclose(actual.incident_heat_flux_w_m2, reference, rtol=3e-12)
    assert model.predict_at_points_details(probability, np.empty((0, 2))).incident_heat_flux_w_m2.shape == (0,)


def test_far_field_converges_to_projected_isotropic_point_source_formula():
    model = make_model(emission_height_m=10.0, atmospheric_transmissivity=0.8)
    probability = np.array([[0.6]])
    center = model.grid.centers((1, 1))[0, 0]
    receiver = center + [1000.0, 400.0]
    result = model.predict_at_points_details(probability, receiver[None, :])
    distance = np.sqrt(np.sum((receiver - center)**2) + 10.0**2)
    # NIST point-source irradiance multiplied by receiver cos(theta)=h/r.
    expected = 0.8 * result.expected_total_radiant_power_w / (4.0 * np.pi * distance**2) * (10.0 / distance)
    assert_allclose(result.incident_heat_flux_w_m2, [expected], rtol=3e-6)


def test_uniform_sheet_tiles_exactly_and_approaches_half_emission_density():
    shape = (61, 81)
    model = make_model(grid=AffineGrid.from_cell_size(1.0), heat_release_rate_density_w_m2=1.0, radiative_fraction=1.0, emission_height_m=2.0)
    result = model.predict_details(np.ones(shape))
    center_value = result.incident_heat_flux_w_m2[shape[0] // 2, shape[1] // 2]
    expected = rectangle_solid_angle(shape[1] / 2, shape[0] / 2, 2.0) / (4.0 * np.pi)
    assert_allclose(center_value, expected, rtol=2e-13)
    assert 0.47 < center_value < 0.5
    assert result.expected_total_radiant_power_w == np.prod(shape)


def test_infinite_upward_receiving_plane_intercepts_half_radiant_power():
    model = make_model(grid=AffineGrid.from_cell_size(1.0), heat_release_rate_density_w_m2=1.0, radiative_fraction=1.0, emission_height_m=2.0)
    # Independent polar integration over 0 <= r < infinity: r=h*t/(1-t).
    nodes, weights = np.polynomial.legendre.leggauss(80)
    t = (nodes + 1.0) / 2.0
    t_weights = weights / 2.0
    radius = 2.0 * t / (1.0 - t)
    dr_dt = 2.0 / (1.0 - t)**2
    angle = np.arange(48) * (2.0 * np.pi / 48)
    receivers = np.stack(
        (radius[:, None] * np.cos(angle), radius[:, None] * np.sin(angle)), axis=-1
    ) + model.grid.centers((1, 1))[0, 0]
    flux = model.predict_at_points_details([[1.0]], receivers.reshape(-1, 2)).incident_heat_flux_w_m2.reshape(80, 48)
    power = np.sum(flux * (t_weights * radius * dr_dt)[:, None]) * (2.0 * np.pi / 48)
    assert_allclose(power, 0.5, rtol=3e-10)


def test_transmission_reduces_flux_without_redefining_emitted_power():
    probability = np.array([[0.4, 0.8], [0.2, 1.0]])
    unattenuated = make_model().predict_details(probability)
    attenuated = make_model(atmospheric_transmissivity=0.25).predict_details(probability)
    assert_allclose(attenuated.incident_heat_flux_w_m2, 0.25 * unattenuated.incident_heat_flux_w_m2, rtol=1e-14)
    assert attenuated.expected_total_radiant_power_w == unattenuated.expected_total_radiant_power_w


def test_combustion_energy_units_broadcasting_and_zero_consumption():
    fuel = np.array([[1.0], [2.0]])
    duration = np.array([[20.0, 40.0, 80.0]])
    parameters = CombustionParameters(fuel, 18e6, duration, consumed_fraction=0.6)
    assert_allclose(parameters.heat_release_rate_density_w_m2 * duration, fuel * 18e6 * 0.6 + np.zeros((2, 3)))
    assert_allclose(CombustionParameters(2.0, 18e6, 100.0, consumed_fraction=0.0).heat_release_rate_density_w_m2, 0.0)


def test_incident_flux_units_area_power_and_constant_exposure_dose():
    result = make_model().predict_details([[0.2, 0.7]])
    flux = result.incident_heat_flux_w_m2
    assert_allclose(result.incident_heat_flux_kw_m2 * 1000, flux)
    assert_allclose(result.incident_energy_j_m2(120.0), flux * 120.0)
    assert_allclose(result.incident_energy_j_m2(0.0), np.zeros_like(flux))
    assert_allclose(result.incident_power_w(0.1), flux * 0.1)
    assert_allclose(result.incident_power_w([[0.2, 0.5]]), flux * [[0.2, 0.5]])
    assert_allclose(result.incident_energy_j(60.0, 0.2), flux * 60.0 * 0.2)


def test_trapezoidal_temporal_integral_for_constant_and_linear_flux():
    times = np.array([10.0, 12.0, 17.0, 25.0])
    spatial = np.array([[3.0, 5.0], [1.0, 0.0]])
    constant = np.repeat(spatial[None, :, :], len(times), axis=0)
    assert_allclose(integrate_heat_flux(constant, times), spatial * 15.0)
    linear = times[:, None, None] * spatial
    assert_allclose(integrate_heat_flux(linear, times), spatial * (25.0**2 - 10.0**2) / 2.0)
    assert_allclose(integrate_heat_flux([2.0, 6.0], [0.0, 3.0]), 12.0)


@pytest.mark.parametrize("probability", [
    [[np.nan]], [[np.inf]], [[-0.1]], [[1.01]], [[1j]],
    np.ma.array([[0.5]], mask=[[True]]),
    0.5, [0.5], np.zeros((1, 1, 1)), np.zeros((0, 2)),
])
def test_invalid_or_missing_probability_is_rejected(probability):
    with pytest.raises(ValueError):
        make_model().predict_details(probability)


@pytest.mark.parametrize("overrides", [
    {"heat_release_rate_density_w_m2": -1.0},
    {"heat_release_rate_density_w_m2": np.nan},
    {"heat_release_rate_density_w_m2": [1.0, 2.0]},
    {"radiative_fraction": -0.1}, {"radiative_fraction": 1.01},
    {"radiative_fraction": np.inf},
    {"emission_height_m": 0.0}, {"emission_height_m": -1.0},
    {"emission_height_m": 3.0, "receiver_height_m": 3.0},
    {"receiver_height_m": np.nan},
    {"atmospheric_transmissivity": -0.1}, {"atmospheric_transmissivity": 1.01},
])
def test_invalid_physical_model_parameters_are_rejected(overrides):
    with pytest.raises(ValueError):
        make_model(**overrides)


def test_common_height_datum_can_be_negative_and_only_separation_matters():
    first = make_model(emission_height_m=3.0, receiver_height_m=0.0)
    second = make_model(emission_height_m=-7.0, receiver_height_m=-10.0)
    assert_allclose(first.predict_details([[0.4]]).incident_heat_flux_w_m2, second.predict_details([[0.4]]).incident_heat_flux_w_m2)


@pytest.mark.parametrize("parameters", [
    (-1.0, 18e6, 10.0, 1.0), (1.0, 0.0, 10.0, 1.0),
    (1.0, 18e6, 0.0, 1.0), (1.0, 18e6, -10.0, 1.0),
    (1.0, 18e6, 10.0, 1.1), (1.0, 18e6, 10.0, -0.1),
    (np.nan, 18e6, 10.0, 1.0), (1.0, 18e6, np.inf, 1.0),
])
def test_invalid_combustion_parameters_are_rejected(parameters):
    with pytest.raises(ValueError):
        CombustionParameters(*parameters)


def test_source_parameter_maps_must_match_probability_shape_exactly():
    for parameter in ["heat_release_rate_density_w_m2", "radiative_fraction"]:
        with pytest.raises(ValueError):
            make_model(**{parameter: np.ones((1, 2))}).predict_details(np.ones((2, 2)))


@pytest.mark.parametrize("grid_argument", [0.0, -1.0, (2.0, -3.0), np.nan])
def test_invalid_cell_sizes_are_rejected(grid_argument):
    with pytest.raises(ValueError):
        AffineGrid.from_cell_size(grid_argument)


def test_degenerate_affine_grid_and_nonfinite_points_are_rejected():
    with pytest.raises(ValueError):
        AffineGrid((1.0, 2.0, 0.0, 2.0, 4.0, 0.0))
    with pytest.raises(ValueError):
        make_model().predict_at_points_details([[1.0]], [[np.nan, 0.0]])
    with pytest.raises(ValueError):
        make_model().predict_at_points_details([[1.0]], [0.0, 1.0])


@pytest.mark.parametrize("chunk", [0, -1, 1.5, True])
def test_invalid_chunk_sizes_are_rejected(chunk):
    with pytest.raises(ValueError):
        make_model().predict_at_points_details([[1.0]], [[0.0, 0.0]], target_chunk_size=chunk)
    with pytest.raises(ValueError):
        make_model().predict_at_points_details([[1.0]], [[0.0, 0.0]], source_chunk_size=chunk)


@pytest.mark.parametrize("flux,times", [
    ([1.0, 2.0], [1.0, 1.0]), ([1.0, 2.0], [2.0, 1.0]),
    ([1.0, 2.0], [0.0, np.nan]), ([1.0, np.nan], [0.0, 1.0]),
    ([1.0, -2.0], [0.0, 1.0]), ([1.0], [0.0]),
    ([1.0, 2.0], [0.0, 1.0, 2.0]), ([1.0, 2.0], [[0.0, 1.0]]),
])
def test_invalid_time_series_and_missing_flux_are_rejected(flux, times):
    with pytest.raises(ValueError):
        integrate_heat_flux(flux, times)


def test_invalid_receiver_area_and_exposure_duration_are_rejected():
    result = make_model().predict_details([[1.0, 0.5]])
    for duration in [-1.0, np.nan, np.inf]:
        with pytest.raises(ValueError):
            result.incident_energy_j_m2(duration)
        with pytest.raises(ValueError):
            result.incident_energy_j(duration, 0.2)
    for area in [-1.0, np.nan, [[1.0]]]:
        with pytest.raises(ValueError):
            result.incident_power_w(area)
        with pytest.raises(ValueError):
            result.incident_energy_j(60.0, area)
