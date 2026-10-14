"""Coarse-cell traversal geometry and conserved phase-energy checks."""

from dataclasses import FrozenInstanceError
import json
from pathlib import Path

import numpy as np
import pytest
from numpy.testing import assert_allclose, assert_array_equal

from tests.heat.test_pipeline import DeterministicPredictor, make_model
from wildfire.heat import AffineGrid, CombustionParameters, FlameResidenceTime
from wildfire.heat_duration import CellBurningDuration


def _point(duration=60.0):
    return FlameResidenceTime(duration, {"source": "explicit test point residence"})


@pytest.mark.parametrize("direction, width", [(0.0, 375.0), (90.0, 375.0), (180.0, 375.0), (45.0, 375.0 * np.sqrt(2.0))])
def test_square_cell_axis_and_diagonal_front_crossing(direction, width):
    result = CellBurningDuration.from_front_crossing(
        _point(), grid=AffineGrid.from_cell_size(375.0),
        spread_rate_m_s=0.05, spread_direction_deg=direction,
    )
    assert_allclose(result.duration_s, width / 0.05 + 60.0, rtol=2e-15)
    assert_allclose(result.provenance_dict()["cell_crossing_duration_s"], width / 0.05, rtol=2e-15)


@pytest.mark.parametrize("transform", [
    (3.0, 1.0, 100.0, 2.0, -4.0, 200.0),
    (0.0, -20.0, -10.0, 10.0, 0.0, 30.0),
    (8.0, 3.0, 0.0, 0.0, 5.0, 0.0),
])
@pytest.mark.parametrize("direction", [0.0, 37.0, 90.0, 135.0, -145.0])
def test_rotated_and_sheared_grid_width_matches_independent_vertex_projection(transform, direction):
    grid = AffineGrid(transform)
    result = CellBurningDuration.from_front_crossing(
        _point(20.0), grid=grid, spread_rate_m_s=0.3,
        spread_direction_deg=direction,
    )
    # Enumerate the four actual projected vertices instead of reusing the
    # edge-vector absolute-value formula in the duration implementation.
    a, b, c, d, e, f = transform
    vertices = np.array([[c, f], [a + c, d + f], [b + c, e + f], [a + b + c, d + e + f]])
    angle = direction * np.pi / 180.0
    projected = vertices @ np.array([np.cos(angle), np.sin(angle)])
    independent_width = projected.max() - projected.min()
    assert_allclose(result.duration_s, independent_width / 0.3 + 20.0, rtol=3e-15, atol=1e-13)


def test_scalar_and_spatial_inputs_broadcast_and_each_cell_has_its_own_front():
    point = _point(np.array([[30.0], [60.0]]))
    rate = np.array([[0.1, 0.2, 0.4]])
    direction = np.array([[0.0, 90.0, 45.0], [180.0, 270.0, -45.0]])
    result = CellBurningDuration.from_front_crossing(
        point, grid=AffineGrid.from_cell_size((20.0, 10.0)),
        spread_rate_m_s=rate, spread_direction_deg=direction,
    )
    expected_width = np.array([[10.0, 20.0, 30.0 / np.sqrt(2.0)], [10.0, 20.0, 30.0 / np.sqrt(2.0)]])
    assert result.duration_s.shape == (2, 3)
    assert_allclose(result.duration_s, expected_width / rate + point.duration_s, rtol=2e-15)


def test_reverse_front_direction_has_the_same_cell_crossing_duration():
    options = dict(grid=AffineGrid((3.0, 1.0, 100.0, 2.0, -4.0, 200.0)), spread_rate_m_s=0.3)
    forward = CellBurningDuration.from_front_crossing(_point(), spread_direction_deg=37.0, **options)
    reverse = CellBurningDuration.from_front_crossing(_point(), spread_direction_deg=217.0, **options)
    assert_allclose(forward.duration_s, reverse.duration_s, rtol=2e-15)


def test_duration_and_nested_provenance_are_deeply_immutable_and_json_serializable():
    duration = np.array([[100.0, 200.0]])
    provenance = {"scenario": {"description": "original", "labels": [1, 2]}}
    result = CellBurningDuration(duration, provenance)
    duration[:] = 0.0
    provenance["scenario"]["labels"].append(3)
    assert_array_equal(result.duration_s, [[100.0, 200.0]])
    assert result.provenance_dict()["scenario"]["labels"] == [1, 2]
    with pytest.raises(ValueError):
        result.duration_s.setflags(write=True)
    with pytest.raises(TypeError):
        result.provenance["scenario"]["description"] = "changed"
    with pytest.raises(FrozenInstanceError):
        result.duration_s = np.array([[999.0]])
    detached = result.provenance_dict()
    detached["scenario"]["labels"].append(99)
    assert result.provenance_dict()["scenario"]["labels"] == [1, 2]
    json.dumps(result.provenance_dict(), allow_nan=False)


def test_crossing_provenance_identifies_arrival_profile_energy_and_source_limits():
    result = CellBurningDuration.from_front_crossing(
        _point(), grid=AffineGrid.from_cell_size(375.0),
        spread_rate_m_s=0.05, spread_direction_deg=0.0,
        provenance={"spread_speed": "explicit illustrative value"},
    )
    metadata = result.provenance_dict()
    assert "first cell entry" in metadata["arrival_semantics"]
    assert "rectangular" in metadata["emission_profile"]
    assert "energy preserved" in metadata["energy_policy"]
    assert "geometric" in metadata["equation_origin"]
    assert metadata["point_residence_duration_s"] == 60.0
    assert len(metadata["sources"]) == 2
    assert "does not" in metadata["sources"][0]["supported_role"]
    assert "does not" in metadata["sources"][1]["supported_role"]
    assert metadata["input_provenance"]["spread_speed"] == "explicit illustrative value"
    json.dumps(metadata, allow_nan=False)


@pytest.mark.parametrize("invalid_duration", [0.0, -1.0, np.nan, np.inf, True, "60", [60.0], [], np.zeros((1, 1, 1)), np.ma.array([[60.0]], mask=[[True]])])
def test_direct_cell_duration_requires_positive_finite_real_scalar_or_spatial_matrix(invalid_duration):
    with pytest.raises(ValueError):
        CellBurningDuration(invalid_duration, {"source": "test scenario"})


@pytest.mark.parametrize("invalid_rate", [0.0, -1.0, np.nan, np.inf, True, "0.1", [0.1], np.empty((0, 1)), [[0.1 + 0j]], np.ma.array([[0.1]], mask=[[True]])])
def test_front_crossing_rejects_invalid_spread_rate(invalid_rate):
    with pytest.raises(ValueError):
        CellBurningDuration.from_front_crossing(
            _point(), grid=AffineGrid.from_cell_size(10.0),
            spread_rate_m_s=invalid_rate, spread_direction_deg=0.0,
        )


@pytest.mark.parametrize("invalid_direction", [np.nan, np.inf, True, "90", [90.0], np.empty((1, 0)), [[90.0 + 0j]], np.ma.array([[90.0]], mask=[[True]])])
def test_front_crossing_rejects_invalid_direction(invalid_direction):
    with pytest.raises(ValueError):
        CellBurningDuration.from_front_crossing(
            _point(), grid=AffineGrid.from_cell_size(10.0),
            spread_rate_m_s=0.1, spread_direction_deg=invalid_direction,
        )


def test_front_crossing_requires_typed_point_residence_and_grid():
    with pytest.raises(TypeError):
        CellBurningDuration.from_front_crossing(
            60.0, grid=AffineGrid.from_cell_size(10.0),
            spread_rate_m_s=0.1, spread_direction_deg=0.0,
        )
    with pytest.raises(TypeError):
        CellBurningDuration.from_front_crossing(
            _point(), grid=(10.0, 0.0, 0.0, 0.0, 10.0, 0.0),
            spread_rate_m_s=0.1, spread_direction_deg=0.0,
        )


def test_nonbroadcast_spatial_inputs_and_overflowing_traversal_are_rejected():
    with pytest.raises(ValueError):
        CellBurningDuration.from_front_crossing(
            _point(np.ones((2, 2))), grid=AffineGrid.from_cell_size(10.0),
            spread_rate_m_s=np.ones((3, 2)), spread_direction_deg=0.0,
        )
    with pytest.raises(ValueError):
        CellBurningDuration.from_front_crossing(
            _point(), grid=AffineGrid.from_cell_size(375.0),
            spread_rate_m_s=np.nextafter(0.0, 1.0), spread_direction_deg=0.0,
        )


@pytest.mark.parametrize("provenance", [None, [], {1: "bad key"}, {"bad": np.inf}, {"bad": object()}])
def test_direct_cell_duration_requires_json_compatible_mapping_provenance(provenance):
    with pytest.raises(ValueError):
        CellBurningDuration(60.0, provenance)


def test_crossing_allows_large_finite_angles_without_conversion_overflow():
    result = CellBurningDuration.from_front_crossing(
        _point(), grid=AffineGrid.from_cell_size(10.0),
        spread_rate_m_s=0.1, spread_direction_deg=1e308,
    )
    assert np.isfinite(result.duration_s).all()
    equivalent = CellBurningDuration.from_front_crossing(
        _point(), grid=AffineGrid.from_cell_size(10.0),
        spread_rate_m_s=0.1, spread_direction_deg=np.remainder(1e308, 360.0),
    )
    assert_array_equal(result.duration_s, equivalent.duration_s)


def test_retimed_model_preserves_total_phase_energy_and_includes_older_cell_burning():
    point = _point(60.0)
    grid = AffineGrid.from_cell_size(375.0)
    cell = CellBurningDuration.from_front_crossing(
        point, grid=grid, spread_rate_m_s=0.05, spread_direction_deg=0.0,
    )
    original = CombustionParameters.from_flame_residence(
        point, fuel_load_kg_m2=2.0, heat_of_combustion_j_kg=18e6, consumed_fraction=0.4,
    )
    from wildfire.heat import WildfireHeatModel

    model = WildfireHeatModel(
        None, grid=grid, combustion=original,
        radiative_fraction=0.3, emission_height_m=5.0,
        residence_time=point, cell_burning_duration=cell,
    )
    phase_energy = 2.0 * 0.4 * 18e6
    assert_allclose(model.combustion.heat_release_rate_density_w_m2 * cell.duration_s, phase_energy, rtol=2e-15)
    assert_allclose(original.heat_release_rate_density_w_m2 * point.duration_s, phase_energy, rtol=2e-15)
    assert_array_equal(original.burning_duration_s, 60.0)
    assert_array_equal(model.combustion.burning_duration_s, 7560.0)
    assert model.residence_time is point
    assert model.cell_burning_duration is cell
    # The point front has passed by t=1800; a 375 m cell at this supplied
    # speed still has active coarse-cell emission throughout the next hour.
    result = model.predict_from_new_burn_probability_details(
        [[0.0]], already_burned_mask=np.array([[True]]),
        arrival_time_s=[[0.0]], current_time_s=1800.0,
    )
    assert_array_equal(result.initial_active_burning_probability, [[1.0]])
    assert_array_equal(result.initial_remaining_burning_duration_s, [[5760.0]])
    assert_array_equal(result.mean_active_burning_probability, [[1.0]])
    conditional = model.heat_model.predict_details([[1.0]]).incident_heat_flux_w_m2
    assert_allclose(result.expected_heat_flux_w_m2, conditional, rtol=2e-15)
    assert_allclose(result.expected_incident_energy_j_m2, conditional * 3600.0, rtol=2e-15)
    assert result.complete


def test_public_api_composition_uses_the_supplied_cell_duration_and_keeps_the_energy_budget():
    import wildfire
    from wildfire.api import WildfireModel

    assert wildfire.CellBurningDuration is CellBurningDuration
    predictor = DeterministicPredictor([[0.0]])
    predictor.contract = {"architecture": "EnvironmentConditionedConvolution"}
    api = WildfireModel(predictor, {"contract": predictor.contract}, Path("/tmp/synthetic-cell-duration.pt"), "synthetic-digest")
    point = _point(60.0)
    physical = make_model(duration=60.0)
    cell = CellBurningDuration.from_front_crossing(
        point, grid=physical.heat_model.grid,
        spread_rate_m_s=0.001, spread_direction_deg=0.0,
    )
    model = api.heat_model(
        grid=physical.heat_model.grid, combustion=physical.combustion,
        radiative_fraction=0.3, emission_height_m=5.0,
        residence_time=point, cell_burning_duration=cell,
    )
    result = model.predict_details(
        [[1.0]], np.zeros((2, 1, 1)), channel_names=predictor.channel_names,
        arrival_time_s=[[0.0]], current_time_s=1800.0,
    )
    assert_array_equal(result.mean_active_burning_probability, [[1.0]])
    assert_array_equal(model.combustion.burning_duration_s, 10_060.0)
    assert_allclose(
        model.combustion.heat_release_rate_density_w_m2 * cell.duration_s,
        physical.combustion.heat_release_rate_density_w_m2 * point.duration_s,
        rtol=2e-15,
    )
    assert result.complete
    assert result.metadata["cell_burning_duration"] == cell.provenance_dict()


def test_reference_point_duration_must_match_the_combustion_before_cell_retiming():
    point = _point(60.0)
    physical = make_model(duration=120.0)
    cell = CellBurningDuration.from_front_crossing(
        point, grid=physical.heat_model.grid,
        spread_rate_m_s=0.1, spread_direction_deg=0.0,
    )
    from wildfire.heat import WildfireHeatModel

    with pytest.raises(ValueError):
        WildfireHeatModel(
            None, grid=physical.heat_model.grid, combustion=physical.combustion,
            radiative_fraction=0.3, emission_height_m=5.0,
            residence_time=point, cell_burning_duration=cell,
        )


def _compose(entry, *, point=None, combustion=None, grid=None, **options):
    """Exercise the direct constructor and resident-model public API equally."""
    from wildfire.api import WildfireModel
    from wildfire.heat import WildfireHeatModel

    grid = AffineGrid.from_cell_size(375.0) if grid is None else grid
    if combustion is None:
        combustion = CombustionParameters(
            1.0, 18e6, 1200.0 if point is None else point.duration_s,
            consumed_fraction=0.6,
        )
    parameters = dict(
        grid=grid, combustion=combustion, radiative_fraction=0.3,
        emission_height_m=5.0, residence_time=point, **options,
    )
    if entry == "direct":
        return WildfireHeatModel(None, **parameters)
    predictor = DeterministicPredictor([[0.0]])
    predictor.contract = {"architecture": "EnvironmentConditionedConvolution"}
    api = WildfireModel(
        predictor, {"contract": predictor.contract},
        Path("/tmp/synthetic-default-cell-duration.pt"), "synthetic-digest",
    )
    return api.heat_model(**parameters)


def test_front_crossing_factory_defaults_to_exported_reported_speed_and_projected_x_direction():
    import wildfire
    from wildfire.heat_duration import DEFAULT_FRONT_SPREAD_RATE_M_S

    assert wildfire.DEFAULT_FRONT_SPREAD_RATE_M_S == DEFAULT_FRONT_SPREAD_RATE_M_S
    assert DEFAULT_FRONT_SPREAD_RATE_M_S == 341.0 / 3600.0
    duration = CellBurningDuration.from_front_crossing(
        _point(60.0), grid=AffineGrid.from_cell_size(375.0),
    )
    assert_allclose(duration.duration_s, 375.0 / (341.0 / 3600.0) + 60.0, rtol=2e-15)
    provenance = duration.provenance_dict()
    assert_allclose(provenance["spread_rate_m_s"], DEFAULT_FRONT_SPREAD_RATE_M_S, rtol=0.0, atol=0.0)
    assert provenance["spread_direction_deg"] == 0.0
    assert "median" in json.dumps(provenance).lower()


@pytest.mark.parametrize("entry", ["direct", "api"])
def test_point_residence_automatically_uses_the_reported_speed_cell_duration(entry):
    point = _point(60.0)
    model = _compose(entry, point=point)
    expected = 375.0 / (341.0 / 3600.0) + 60.0
    assert isinstance(model.cell_burning_duration, CellBurningDuration)
    assert_allclose(model.combustion.burning_duration_s, expected, rtol=2e-15)
    assert model.residence_time is point
    assert "median" in json.dumps(model.cell_burning_duration.provenance_dict()).lower()
    assert_allclose(model.combustion.heat_release_rate_density_w_m2 * expected, 0.6 * 18e6, rtol=2e-15)
    result = model.predict_from_new_burn_probability_details(
        [[0.0]], already_burned_mask=np.array([[True]]),
        arrival_time_s=[[0.0]], current_time_s=1800.0,
    )
    assert_array_equal(result.initial_active_burning_probability, [[1.0]])
    assert_allclose(result.initial_remaining_burning_duration_s, [[expected - 1800.0]], rtol=2e-15)
    assert result.complete


@pytest.mark.parametrize("entry", ["direct", "api"])
@pytest.mark.parametrize("speed", [0.2, np.array([[0.1, 0.2]])])
def test_automatic_cell_duration_accepts_custom_scalar_or_map_spread_speed(entry, speed):
    point = _point(np.array([[30.0, 60.0]]))
    direction = np.array([[0.0, 45.0]])
    model = _compose(entry, point=point, spread_rate_m_s=speed, spread_direction_deg=direction)
    expected = np.array([[375.0, 375.0 * np.sqrt(2.0)]]) / speed + point.duration_s
    assert_allclose(model.combustion.burning_duration_s, expected, rtol=2e-15)
    assert_allclose(model.combustion.heat_release_rate_density_w_m2 * expected, np.full((1, 2), 0.6 * 18e6), rtol=2e-15)


@pytest.mark.parametrize("entry", ["direct", "api"])
def test_explicit_combustion_duration_without_point_residence_is_preserved(entry):
    model = _compose(entry)
    assert model.residence_time is None
    assert model.cell_burning_duration is None
    assert_array_equal(model.combustion.burning_duration_s, 1200.0)


@pytest.mark.parametrize("entry", ["direct", "api"])
@pytest.mark.parametrize("requested", [dict(spread_rate_m_s=0.1), dict(spread_direction_deg=45.0)])
def test_spread_scenario_without_point_residence_is_rejected(entry, requested):
    with pytest.raises(ValueError):
        _compose(entry, **requested)


@pytest.mark.parametrize("entry", ["direct", "api"])
def test_explicit_cell_duration_option_false_preserves_point_duration(entry):
    point = _point(60.0)
    model = _compose(entry, point=point, use_cell_burning_duration=False)
    assert model.cell_burning_duration is None
    assert_array_equal(model.combustion.burning_duration_s, point.duration_s)


@pytest.mark.parametrize("entry", ["direct", "api"])
@pytest.mark.parametrize("conflicting", [
    dict(spread_rate_m_s=0.1),
    dict(cell_burning_duration=CellBurningDuration(1800.0, {})),
])
def test_disabled_cell_duration_rejects_conflicting_inputs(entry, conflicting):
    with pytest.raises(ValueError):
        _compose(entry, point=_point(), use_cell_burning_duration=False, **conflicting)


@pytest.mark.parametrize("entry", ["direct", "api"])
def test_explicit_cell_duration_rejects_simultaneous_spread_rate(entry):
    with pytest.raises(ValueError):
        _compose(
            entry, point=_point(), cell_burning_duration=CellBurningDuration(1800.0, {}),
            spread_rate_m_s=0.1,
        )


@pytest.mark.parametrize("entry", ["direct", "api"])
def test_factory_cell_duration_rejects_a_different_model_affine_grid(entry):
    grid = AffineGrid.from_cell_size(375.0)
    cell = CellBurningDuration.from_front_crossing(
        _point(), grid=AffineGrid.from_cell_size(10.0),
        spread_rate_m_s=0.1, spread_direction_deg=0.0,
    )
    with pytest.raises(ValueError):
        _compose(entry, point=_point(), grid=grid, cell_burning_duration=cell)


@pytest.mark.parametrize("entry", ["direct", "api"])
def test_factory_cell_duration_rejects_mismatched_point_residence_metadata_without_residence_argument(entry):
    grid = AffineGrid.from_cell_size(375.0)
    cell = CellBurningDuration.from_front_crossing(
        _point(60.0), grid=grid, spread_rate_m_s=0.1, spread_direction_deg=0.0,
    )
    incompatible = CombustionParameters(1.0, 18e6, 120.0, consumed_fraction=0.6)
    with pytest.raises(ValueError):
        _compose(entry, grid=grid, combustion=incompatible, cell_burning_duration=cell)


@pytest.mark.parametrize("entry", ["direct", "api"])
def test_literal_cell_duration_with_empty_explicit_provenance_remains_supported(entry):
    literal = CellBurningDuration(1800.0, {})
    model = _compose(entry, cell_burning_duration=literal)
    assert model.cell_burning_duration is literal
    assert_array_equal(model.combustion.burning_duration_s, 1800.0)
    assert_allclose(model.combustion.heat_release_rate_density_w_m2 * 1800.0, 0.6 * 18e6, rtol=2e-15)
