"""Independent-review regressions, leaving the original 47 fixtures unchanged."""
from fractions import Fraction as F

import numpy as np
import pytest

import test_known_footprint as original

kf = original.kf


def _forecast(raw):
    shape = raw["source_burned_area"].shape
    return dict(raw, new_burn_probability=np.zeros(shape), probability_valid=np.ones(shape, dtype=bool),
                rate_per_h=np.zeros(shape), rate_valid=np.ones(shape, dtype=bool))


@pytest.mark.parametrize("case,code", [
    ("active-unburned", "RAW_ACTIVE_OUTSIDE_KNOWN_BURNED"),
    ("active-unknown-cutoff", "RAW_ACTIVE_OUTSIDE_KNOWN_BURNED"),
    ("active-zero-remaining", "RAW_ACTIVE_REMAINING_INVALID"),
    ("inactive-positive-remaining", "RAW_INACTIVE_REMAINING_NOT_ZERO"),
    ("invalid-mask-negative-remaining", "RAW_NEGATIVE_REMAINING"),
])
def test_cutoff_consistency_refusals_match_unchanged_canonical_contract(case, code):
    raw, _, _ = original.fixture()
    if case in ("active-unburned", "active-unknown-cutoff", "active-zero-remaining"):
        raw["heat__initial_active_burning_probability"][2, 1] = 1
        raw["heat__initial_remaining_burning_duration_s"][2, 1] = 100
    if case == "active-unknown-cutoff":
        raw["source_burned_area_valid"][2, 1] = False
    elif case == "active-zero-remaining":
        raw["source_burned_area"][2, 1] = 1
        raw["trajectory_first_burn_hour"][:, 2, 1] = 0
        raw["heat__initial_remaining_burning_duration_s"][2, 1] = 0
    elif case == "inactive-positive-remaining":
        raw["heat__initial_remaining_burning_duration_s"][2, 1] = 100
    elif case == "invalid-mask-negative-remaining":
        raw["heat__initial_burning_valid"][2, 1] = False
        raw["heat__initial_remaining_burning_duration_s"][2, 1] = -1
    with pytest.raises(ValueError, match=code):
        original.source(raw)
    with pytest.raises(original.bridge.v1.CT.ContractError, match=code):
        original.bridge.v1.CT.validate_raw(_forecast(raw), 3970.4642815249267)
    if case == "active-unburned":
        with pytest.raises(original.bridge.v1.CT.ContractError, match=code):
            original.bridge.construct(_forecast(raw), cutoff_utc="2025-01-01T00:00:00Z", epsg=5179,
                                      settings=original.bridge.v1.settings_for(3970.4642815249267))


@pytest.mark.parametrize("state", ["active-known-burned", "inactive-known-burned", "unknown-age", "unknown-offroad"])
def test_valid_cutoff_states_match_canonical_admission_without_filling_unknowns(state):
    raw, graph, request = original.fixture()
    if state != "unknown-offroad":
        raw["source_burned_area"][0, 1] = 1
        raw["trajectory_first_burn_hour"][:, 0, 1] = 0
    if state == "active-known-burned":
        raw["heat__initial_active_burning_probability"][0, 1] = 1
        raw["heat__initial_remaining_burning_duration_s"][0, 1] = 100
    elif state == "unknown-age":
        raw["heat__initial_burning_valid"][0, 1] = False
        raw["heat__initial_active_burning_probability"][0, 1] = np.nan
        raw["heat__initial_remaining_burning_duration_s"][0, 1] = np.nan
    elif state == "unknown-offroad":
        raw["source_burned_area_valid"][0, 1] = False
        raw["source_burned_area"][0, 1] = np.nan
        raw["trajectory_first_burn_hour"][:, 0, 1] = -2
        raw["heat__initial_burning_valid"][0, 1] = False
        raw["heat__initial_active_burning_probability"][0, 1] = np.nan
        raw["heat__initial_remaining_burning_duration_s"][0, 1] = np.nan
    original.bridge.v1.CT.validate_raw(_forecast(raw), 3970.4642815249267)
    source = original.source(raw)
    if state == "active-known-burned":
        assert source.R == 100 and source.current_native[0, 1]
    elif state == "unknown-age":
        assert source.R == source.T and source.current_native[0, 1]
    elif state == "unknown-offroad":
        assert source.unknown_native[:, 0, 1].all() and np.isnan(source.raw["source_burned_area"][0, 1])
    for method in ("sipp", "sweep"):
        assert kf.plan_contact_route(graph, request, source, method=method)["status"] == kf.CHECKED
    assert kf.check_contact_route(graph, request, source, [original.leg()], "b")["ok"]


@pytest.mark.parametrize("key", ["source_burned_area", "heat__initial_active_burning_probability",
                                "heat__initial_remaining_burning_duration_s", "affine_transform"])
def test_consumed_raw_float_types_match_canonical_admission(key):
    raw, _, _ = original.fixture()
    raw[key] = raw[key].astype(np.int64)
    with pytest.raises(ValueError, match="RAW_FIELD_NOT_FLOAT|RAW_AFFINE"):
        original.source(raw)
    with pytest.raises(original.bridge.v1.CT.ContractError, match="RAW_FIELD_NOT_FLOAT|RAW_AFFINE"):
        original.bridge.v1.CT.validate_raw(_forecast(raw), 3970.4642815249267)


def _two_destinations():
    raw, graph, request = original.fixture()
    graph["nodes"][1]["x"] = 1.5
    graph["nodes"].append(dict(id="c", x=2.5, y=.5, waitable=True))
    graph["edges"] = [dict(id="ab", u="a", v="b", travel_ticks=1), dict(id="ac", u="a", v="c", travel_ticks=2)]
    request["destinations"] = [dict(node="b", dwell=1.5, open_intervals=[[0, 3600]]),
                                dict(node="c", dwell=0, open_intervals=[[0, 3600]])]
    return raw, graph, request


@pytest.mark.parametrize("method", ["sipp", "sweep"])
def test_fractional_member_clock_refuses_instead_of_rounding_earliest_problem(method):
    raw, graph, request = _two_destinations()
    source = original.source(raw, member_valid_until_s=[3, 3])
    checked = kf.check_contact_route(graph, request, source, [original.leg(end=1)], "b")
    assert checked["ok"] and checked["finish_including_dwell"] == "5/2"
    planned = kf.plan_contact_route(graph, request, source, method=method)
    assert planned["status"] == kf.CHECKED and planned["arrival"] == 1 and planned["destination"] == "b"
    with pytest.raises(ValueError, match="whole-second member validity"):
        original.source(raw, member_valid_until_s=[F(5, 2), F(5, 2)])


@pytest.mark.parametrize("method", ["sipp", "sweep"])
def test_exclusive_terminal_fractional_dwell_is_explicitly_unsupported(method):
    raw, graph, request = _two_destinations()
    source = original.source(raw, member_valid_until_s=[3, 3], terminal_inclusive=False)
    planned = kf.plan_contact_route(graph, request, source, method=method)
    checked = kf.check_contact_route(graph, request, source, [original.leg(end=1)], "b")
    assert planned["status"] == kf.UNRESOLVED and "whole-second dwell" in planned["reason"]
    assert "restricted_problem_optimality" not in planned
    assert not checked["ok"] and "whole-second dwell" in checked["violations"][0]
    request["destinations"][0]["dwell"] = 1
    planned = kf.plan_contact_route(graph, request, source, method=method)
    assert planned["status"] == kf.CHECKED and planned["arrival"] == 1
    request["destinations"][0]["dwell"] = 2
    planned = kf.plan_contact_route(graph, request, source, method=method)
    assert planned["status"] == kf.CHECKED and planned["arrival"] == 2 and planned["destination"] == "c"
    assert not kf.check_contact_route(graph, request, source, [original.leg(end=1)], "b")["ok"]


@pytest.mark.parametrize("timestamp", ["2025-01-01T00:00:00.000000001Z", "2025-01-01T00:00:00.1234567Z",
                                      "2025-01-01T00:00:00.000000000Z", "2025-01-01T00:00:00+00:00:00.000000001"])
def test_source_clock_rejects_unrepresentable_or_out_of_contract_precision(timestamp):
    raw, _, _ = original.fixture()
    with pytest.raises(ValueError, match="at most six fractional digits"):
        original.source(raw, cutoff_utc=timestamp)


@pytest.mark.parametrize("method", ["sipp", "sweep"])
def test_request_clock_cannot_alias_nanoseconds_or_mismatched_microseconds(method):
    raw, graph, request = original.fixture()
    source = original.source(raw)
    request["as_of"] = "2025-01-01T00:00:00.000000001Z"
    assert kf.plan_contact_route(graph, request, source, method=method)["status"] == kf.UNRESOLVED
    assert not kf.check_contact_route(graph, request, source, [original.leg()], "b")["ok"]
    source = original.source(raw, cutoff_utc="2025-01-01T00:00:00.000001Z")
    request["as_of"] = "2025-01-01T00:00:00Z"
    assert kf.plan_contact_route(graph, request, source, method=method)["status"] == kf.UNRESOLVED
    assert not kf.check_contact_route(graph, request, source, [original.leg()], "b")["ok"]
    request["as_of"] = "2025-01-01T08:00:00.000001+08:00"
    assert kf.plan_contact_route(graph, request, source, method=method)["status"] == kf.CHECKED
    assert kf.check_contact_route(graph, request, source, [original.leg()], "b")["ok"]


@pytest.mark.parametrize("method", ["sipp", "sweep"])
def test_far_year_microseconds_compare_as_exact_UTC_instants(method):
    raw, graph, request = original.fixture()
    source = original.source(raw, cutoff_utc="9999-01-01T00:00:00.000001Z")
    request["as_of"] = "9999-01-01T00:00:00.000000Z"
    assert kf._utc(source.cutoff_utc) != kf._utc(request["as_of"])
    assert kf.plan_contact_route(graph, request, source, method=method)["status"] == kf.UNRESOLVED
    assert not kf.check_contact_route(graph, request, source, [original.leg()], "b")["ok"]
    request["as_of"] = "9999-01-01T08:00:00.000001+08:00"
    assert kf._utc(source.cutoff_utc) == kf._utc(request["as_of"])
    assert kf.plan_contact_route(graph, request, source, method=method)["status"] == kf.CHECKED
    assert kf.check_contact_route(graph, request, source, [original.leg()], "b")["ok"]
