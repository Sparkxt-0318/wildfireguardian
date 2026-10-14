"""Reference energy units, phase-mass conservation, and provenance contracts."""

from dataclasses import FrozenInstanceError
import json

import numpy as np
from numpy.testing import assert_allclose, assert_array_equal
import pytest

from wildfire.heat import CombustionParameters, FlameResidenceTime
from wildfire.heat_parameters import heat_content_from_fbfm40


def test_all_forty_catalog_codes_use_nominal_heat_except_gr6():
    codes = np.array([
        101, 102, 103, 104, 105, 106, 107, 108, 109,
        121, 122, 123, 124, 141, 142, 143, 144, 145, 146, 147, 148, 149,
        161, 162, 163, 164, 165, 181, 182, 183, 184, 185, 186, 187, 188,
        189, 201, 202, 203, 204,
    ]).reshape(5, 8)
    result = heat_content_from_fbfm40(codes)
    # NIST SP811, printed p.46: 1 Btu_IT/lb = 2326 J/kg. These numerical
    # expectations are deliberately independent of the implementation constant.
    expected = np.full((5, 8), 18_608_000.0)
    expected[0, 5] = 20_934_000.0
    assert_array_equal(result, expected)
    assert heat_content_from_fbfm40(106).shape == ()
    assert float(heat_content_from_fbfm40(106)) == 20_934_000.0
    with pytest.raises(ValueError):
        result.setflags(write=True)


def test_reference_constructor_uses_explicit_phase_fraction_and_reference_duration():
    result = CombustionParameters.from_fbfm40(
        [[101, 106]], fuel_load_kg_m2=[[2.0, 3.0]], consumed_fraction=0.25,
    )
    assert_array_equal(result.heat_of_combustion_j_kg, [[18_608_000.0, 20_934_000.0]])
    assert_allclose(result.burning_duration_s[0, 0], 11.219002375296913, rtol=1e-13)
    # Multiplying the uniform rate by its duration recovers ONLY the explicitly
    # selected consumed mass energy; total loading is not silently consumed.
    assert_allclose(result.heat_release_rate_density_w_m2 * result.burning_duration_s,
                    [[9_304_000.0, 15_700_500.0]])
    metadata = result.provenance_dict()
    assert metadata["btu_convention"].startswith("International Table")
    assert metadata["catalog_codes_used"] == {"101": "GR1", "106": "GR6"}
    assert "not event-specific measured" in metadata["energy_basis"]
    assert "explicit supplied consumed_fraction" in metadata["consumption_origin"]
    assert metadata["residence_time"]["catalog_cell_count"] == 2
    json.dumps(metadata, allow_nan=False)


def test_explicit_duration_is_kept_distinct_from_nominal_fuel_heat():
    residence = FlameResidenceTime(75.0, {"source": "supplied phase-duration measurement"})
    result = CombustionParameters.from_fbfm40(
        [[101, 106]], fuel_load_kg_m2=2.0, consumed_fraction=[[0.1, 0.4]],
        residence_time=residence,
    )
    assert float(result.burning_duration_s) == 75.0
    assert_allclose(result.heat_release_rate_density_w_m2,
                    [[3_721_600.0 / 75.0, 16_747_200.0 / 75.0]])
    assert result.provenance["duration_origin"] == "explicit supplied flaming-duration scenario"
    assert result.provenance["residence_time"]["source"] == "supplied phase-duration measurement"


def test_phase_consumption_mass_energy_and_zero_initial_mass_are_conserved():
    initial = np.array([[0.0, 2.0], [3.0, 4.0]])
    consumed = np.array([[0.0, 0.5], [3.0, 1.0]])
    result = CombustionParameters.from_phase_consumption(
        initial, consumed, heat_of_combustion_j_kg=17_000_000.0,
        burning_duration_s=[[10.0, 20.0], [30.0, 40.0]],
        provenance={"consumption_source": "external CONSUME flaming output"},
    )
    assert_array_equal(result.fuel_load_kg_m2, initial)
    assert_array_equal(result.consumed_fraction, [[0.0, 0.25], [1.0, 0.25]])
    assert_allclose(result.heat_release_rate_density_w_m2 * result.burning_duration_s,
                    [[0.0, 8_500_000.0], [51_000_000.0, 17_000_000.0]])
    # The supplied effective heat is retained rather than overwritten with a
    # nominal FBFM40 value or an invented moisture correction.
    assert float(result.heat_of_combustion_j_kg) == 17_000_000.0
    assert "does not run CONSUME" in result.provenance["limitations"][0]


def test_consumed_mass_adapter_matches_initial_mass_fraction_adapter():
    initial = np.array([[1.0], [2.0]])
    consumed = np.array([[0.2, 0.4], [0.5, 0.8]])
    heat = np.array([[16_000_000.0, 17_000_000.0]])
    duration = np.array([[20.0], [40.0]])
    from_phase = CombustionParameters.from_phase_consumption(
        initial, consumed, heat_of_combustion_j_kg=heat, burning_duration_s=duration,
    )
    from_consumed = CombustionParameters.from_consumed_fuel(
        consumed, heat_of_combustion_j_kg=heat, burning_duration_s=duration,
    )
    assert_allclose(from_phase.heat_release_rate_density_w_m2,
                    from_consumed.heat_release_rate_density_w_m2)
    assert float(from_consumed.consumed_fraction) == 1.0
    assert "already consumed" in from_consumed.provenance["stored_fuel_load_meaning"]
    assert_allclose(from_consumed.heat_release_rate_density_w_m2 * duration,
                    consumed * heat)


def test_four_positional_parameter_api_and_flame_residence_keep_supplied_values():
    direct = CombustionParameters(2.0, 16_000_000.0, 10.0, 0.25)
    assert float(direct.heat_release_rate_density_w_m2) == 800_000.0
    assert direct.provenance_dict() == {}
    residence = FlameResidenceTime(10.0, {"scenario": "measured local duration"})
    derived = CombustionParameters.from_flame_residence(
        residence, fuel_load_kg_m2=2.0, heat_of_combustion_j_kg=16_000_000.0,
        consumed_fraction=0.25, provenance={"fuel": "supplied local loading"},
    )
    assert float(derived.heat_release_rate_density_w_m2) == 800_000.0
    assert derived.provenance["residence_time"]["scenario"] == "measured local duration"


def test_provenance_is_json_safe_independent_and_deeply_immutable():
    original = {"source": {"notes": ["consumed flaming mass"], "count": np.int64(1)}}
    result = CombustionParameters.from_consumed_fuel(
        0.5, heat_of_combustion_j_kg=18_000_000.0, burning_duration_s=20.0,
        provenance=original,
    )
    original["source"]["notes"].append("later caller edit")
    assert result.provenance["input_provenance"]["source"]["notes"] == ("consumed flaming mass",)
    with pytest.raises(TypeError):
        result.provenance["input_provenance"]["source"]["count"] = 2
    with pytest.raises(FrozenInstanceError):
        result.provenance = {}
    copied = result.provenance_dict()
    json.dumps(copied, allow_nan=False)
    copied["input_provenance"]["source"]["notes"].append("copy only")
    assert result.provenance["input_provenance"]["source"]["notes"] == ("consumed flaming mass",)


@pytest.mark.parametrize("bad", [
    np.nan, np.inf, -np.inf, 101.5, 0, -9999, 91, 92, 93, 98, 99, 13, 250,
    "101", True, [[False]], [101, 106], np.ones((1, 1, 1)),
    [], np.ma.array([[101]], mask=True),
])
def test_reference_heat_does_not_assign_missing_custom_or_nonburnable_codes(bad):
    with pytest.raises(ValueError):
        heat_content_from_fbfm40(bad)
    with pytest.raises(ValueError):
        CombustionParameters.from_fbfm40(bad, fuel_load_kg_m2=1.0, consumed_fraction=0.5)


@pytest.mark.parametrize("fraction", [-0.1, 1.1, np.nan, np.inf, True, "0.5", [0.5]])
def test_nominal_reference_constructor_requires_explicit_valid_fraction(fraction):
    with pytest.raises(ValueError):
        CombustionParameters.from_fbfm40(101, fuel_load_kg_m2=1.0, consumed_fraction=fraction)


def test_reference_constructor_does_not_supply_a_default_consumption_fraction():
    with pytest.raises(TypeError):
        CombustionParameters.from_fbfm40(101, fuel_load_kg_m2=1.0)
    with pytest.raises(TypeError, match="residence_time"):
        CombustionParameters.from_fbfm40(
            101, fuel_load_kg_m2=1.0, consumed_fraction=0.5, residence_time=20.0,
        )


@pytest.mark.parametrize("initial,consumed", [
    (0.0, 0.1), (1.0, 1.001), (-1.0, 0.0), (1.0, -0.1),
    (1.0, np.nan), ([[1.0, 2.0]], [[0.1, 0.2, 0.3]]),
])
def test_phase_adapter_rejects_unphysical_or_incompatible_masses(initial, consumed):
    with pytest.raises(ValueError):
        CombustionParameters.from_phase_consumption(
            initial, consumed, heat_of_combustion_j_kg=18_000_000.0, burning_duration_s=20.0,
        )


@pytest.mark.parametrize("bad", [
    -0.1, np.nan, np.inf, True, "0.5", [0.5], np.ones((1, 1, 1)), [],
    np.ma.array([[0.5]], mask=True),
])
def test_phase_mass_requires_complete_numeric_scalar_or_spatial_map(bad):
    with pytest.raises(ValueError):
        CombustionParameters.from_consumed_fuel(
            bad, heat_of_combustion_j_kg=18_000_000.0, burning_duration_s=20.0,
        )


@pytest.mark.parametrize("parameter,bad", [
    ("heat_of_combustion_j_kg", 0.0), ("heat_of_combustion_j_kg", -1.0),
    ("heat_of_combustion_j_kg", True), ("heat_of_combustion_j_kg", [18_000_000.0]),
    ("burning_duration_s", 0.0), ("burning_duration_s", -1.0),
    ("burning_duration_s", True), ("burning_duration_s", [20.0]),
    ("burning_duration_s", np.ones((2, 2, 2))),
])
def test_supplied_phase_heat_and_duration_have_explicit_units_and_valid_shapes(parameter, bad):
    options = {"heat_of_combustion_j_kg": 18_000_000.0, "burning_duration_s": 20.0}
    options[parameter] = bad
    with pytest.raises(ValueError):
        CombustionParameters.from_consumed_fuel(0.5, **options)


@pytest.mark.parametrize("bad", [[], "source", {1: "bad key"}, {"bad": np.nan}, {"bad": np.array([1.0])}])
def test_combustion_provenance_rejects_nonmapping_or_nonjson_values(bad):
    with pytest.raises(ValueError):
        CombustionParameters(1.0, 18_000_000.0, 20.0, 0.5, bad)
    with pytest.raises(ValueError):
        CombustionParameters.from_fbfm40(
            101, fuel_load_kg_m2=1.0, consumed_fraction=0.5, provenance=bad,
        )
