"""Tiny adversarial fixtures only, no native panel or timing campaign."""
import copy
from fractions import Fraction as F
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from wfg_sipp import known_footprint as kf
from wfg_sipp.adapter import sweep_plan
from wfg_sipp.frontend import sipp_plan
from wfg_synthetic_truth.frozen_checker import check_route

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("_contact_bridge_tests", ROOT / "experimental/scenario-members/bridge_v2.py")
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


def fixture(K=2, H=3, W=3, D=2, dwell=0, horizon=3600):
    z = np.zeros((H, W), dtype=float)
    valid = np.ones((H, W), dtype=bool)
    raw = dict(source_burned_area=z.copy(), source_burned_area_valid=valid.copy(),
               heat__initial_active_burning_probability=z.copy(), heat__initial_burning_valid=valid.copy(),
               heat__initial_remaining_burning_duration_s=z.copy(),
               trajectory_first_burn_hour=np.full((K, H, W), -1, dtype=np.int16),
               affine_transform=np.array([1., 0., 0., 0., -1., float(H)]))
    graph = dict(revision="tiny", crs="EPSG:5179", grid=dict(x0=0, y0=0, resolution=1, width=W, height=H),
                 nodes=[dict(id="a", x=.5, y=.5, waitable=True), dict(id="b", x=W-.5, y=.5, waitable=True)],
                 edges=[dict(id="ab", u="a", v="b", travel_ticks=D)], forbidden_turns=[], mid_edge_reversal=False)
    request = dict(position={"node": "a"}, incoming_edge=None, departure=0, horizon=horizon,
                   as_of="2025-01-01T00:00:00Z", destinations=[dict(node="b", dwell=dwell, open_intervals=[[0, horizon]])],
                   incurred={"original-issued-member": 123},
                   budgets={"dose": {"original-issued-member": 1}, "peak": .01}, exposure_scope="including_dwell")
    return raw, graph, request


def source(raw, **kwargs):
    st = dict(trajectory_indices=list(range(len(raw["trajectory_first_burn_hour"]))),
              cutoff_utc="2025-01-01T00:00:00Z", epsg=5179, source_horizon_s=3600,
              burning_duration_s=3970.4642815249267, seed=20261008, terminal_inclusive=True)
    st.update(kwargs)
    return kf.KnownFootprintSource(raw, **st)


def leg(edge="ab", start=0, end=2):
    return dict(kind="EDGE", edge=edge, start=start, end=end, from_fraction=0, to_fraction=1)


@pytest.mark.parametrize("method", ["sipp", "sweep"])
def test_offroad_unknown_is_irrelevant_and_original_history_stays_verbatim(method):
    raw, graph, request = fixture()
    raw["trajectory_first_burn_hour"][:, 0, 1] = -2
    before = {k: a.tobytes() for k, a in raw.items()}
    request_before = copy.deepcopy(request)
    s = source(raw)
    result = kf.plan_contact_route(graph, request, s, method=method)
    assert result["status"] == kf.CHECKED
    assert result["arrival"] == 2
    assert result["original_request"] == request_before == request
    assert result["full_policy_status"] == "UNKNOWN"
    assert result["peak"] is result["dose"] is result["risk"] is None
    assert result["original_domain_refusal"] == result["original_domain_optimality"] == "UNRESOLVED"
    assert [m["trajectory_index"] for m in result["contact_check"]["per_member"]] == [0, 1]
    assert {k: a.tobytes() for k, a in raw.items()} == before
    for a in list(s.raw.values()) + [s.unknown_native, s.current_native]:
        assert not a.flags.writeable
        with pytest.raises(ValueError):
            a.setflags(write=True)


@pytest.mark.parametrize("method", ["sipp", "sweep"])
@pytest.mark.parametrize("which", ["interior", "issue", "destination", "cutoff-invalid", "endpoint"])
def test_unknown_occupied_footprints_refuse(method, which):
    raw, graph, request = fixture()
    c = {"interior": 1, "issue": 0, "destination": 2, "cutoff-invalid": 1, "endpoint": 2}[which]
    if which == "cutoff-invalid":
        raw["source_burned_area_valid"][2, c] = False
    else:
        raw["trajectory_first_burn_hour"][0, 2, c] = -2
    s = source(raw)
    result = kf.plan_contact_route(graph, request, s, method=method)
    assert result["status"] == kf.UNRESOLVED
    assert not kf.check_contact_route(graph, request, s, [leg()], "b")["ok"]


@pytest.mark.parametrize("method", ["sipp", "sweep"])
def test_unknown_grid_cut_point_refuses_even_with_known_interiors(method):
    raw, graph, request = fixture(H=2, W=2)
    graph["nodes"][0].update(x=.5, y=1.5)
    graph["nodes"][1].update(x=1.5, y=.5)
    raw["trajectory_first_burn_hour"][:, 0, 1] = -2
    s = source(raw)
    node_known, edge_known = kf.support_barriers(graph, s)
    assert node_known.all() and not edge_known.any()
    assert kf.plan_contact_route(graph, request, s, method=method)["status"] == kf.UNRESOLVED
    checked = kf.check_contact_route(graph, request, s, [leg()], "b")
    assert not checked["ok"] and any("UNKNOWN_OCCUPIED_CELL" in v for v in checked["violations"])


@pytest.mark.parametrize("method", ["sipp", "sweep"])
def test_waiting_and_half_open_expiry_follow_original_law(method):
    raw, graph, request = fixture()
    raw["trajectory_first_burn_hour"][:, 2, 1] = 0
    raw["source_burned_area"][2, 1] = 1
    raw["heat__initial_active_burning_probability"][2, 1] = 1
    raw["heat__initial_remaining_burning_duration_s"][2, 1] = 3
    s = source(raw, burning_duration_s=3)
    result = kf.plan_contact_route(graph, request, s, method=method)
    assert result["status"] == kf.CHECKED and result["arrival"] == 5
    assert [l["kind"] for l in result["legs"]] == ["WAIT", "WAIT", "WAIT", "EDGE"]
    assert not kf.check_contact_route(graph, request, s, [leg()], "b")["ok"]
    graph["nodes"][0]["waitable"] = False
    assert kf.plan_contact_route(graph, request, s, method=method)["status"] == kf.UNRESOLVED
    assert not kf.check_contact_route(graph, request, s, result["legs"], "b")["ok"]


@pytest.mark.parametrize("method", ["sipp", "sweep"])
def test_dwell_contact_is_checked_and_unknown_initial_age_encloses_full_T(method):
    raw, graph, request = fixture(dwell=3000)
    raw["trajectory_first_burn_hour"][:, 2, 2] = 1
    s = source(raw)
    assert not kf.check_contact_route(graph, request, s, [leg()], "b")["ok"]
    assert kf.plan_contact_route(graph, request, s, method=method)["status"] == kf.UNRESOLVED
    raw, graph, request = fixture()
    raw["source_burned_area"][2, 1] = 1
    raw["trajectory_first_burn_hour"][:, 2, 1] = 0
    raw["heat__initial_burning_valid"][2, 1] = False
    s = source(raw)
    assert s.R == s.T
    assert kf.plan_contact_route(graph, request, s, method=method)["status"] == kf.UNRESOLVED
    with pytest.raises(ValueError, match="does not enclose"):
        source(raw, initial_remaining_s=1)


@pytest.mark.parametrize("method", ["sipp", "sweep"])
def test_turns_and_original_incoming_edge_context_are_retained(method):
    raw, graph, request = fixture()
    graph["nodes"].append(dict(id="c", x=1.5, y=.5, waitable=False))
    graph["edges"] = [dict(id="ac", u="a", v="c", travel_ticks=1),
                      dict(id="cb", u="c", v="b", travel_ticks=1),
                      dict(id="ba", u="b", v="a", travel_ticks=2)]
    s = source(raw)
    assert kf.plan_contact_route(graph, request, s, method=method)["status"] == kf.CHECKED
    graph["forbidden_turns"] = [["ac", "cb"]]
    assert kf.plan_contact_route(graph, request, s, method=method)["status"] == kf.UNRESOLVED
    assert not kf.check_contact_route(graph, request, s, [leg("ac", 0, 1), leg("cb", 1, 2)], "b")["ok"]
    graph["forbidden_turns"] = [["ba", "ac"]]
    request["incoming_edge"] = "ba"
    assert kf.plan_contact_route(graph, request, s, method=method)["status"] == kf.UNRESOLVED


@pytest.mark.parametrize("method", ["sipp", "sweep"])
def test_finite_censoring_horizon_equality_and_full_dwell(method):
    raw, graph, request = fixture(D=3480, dwell=120)
    s = source(raw)
    result = kf.plan_contact_route(graph, request, s, method=method)
    assert result["status"] == kf.CHECKED
    assert result["contact_check"]["finish_including_dwell"] == 3600
    assert "finite" in s.provenance()["right_censoring"]
    request["horizon"] = 3601
    request["destinations"][0]["open_intervals"] = [[0, 3601]]
    request["destinations"][0]["dwell"] = 121
    checked = kf.check_contact_route(graph, request, s, [leg(end=3480)], "b")
    assert not checked["ok"] and any("OUTSIDE_FINITE_SOURCE_CLOCK" in v for v in checked["violations"])
    assert kf.plan_contact_route(graph, request, s, method=method)["status"] == kf.UNRESOLVED
    request["destinations"][0]["dwell"] = 120
    assert kf.plan_contact_route(graph, request, source(raw, terminal_inclusive=False), method=method)["status"] == kf.UNRESOLVED
    assert kf.plan_contact_route(graph, request, source(raw, member_valid_until_s=[3599, 3600]), method=method)["status"] == kf.UNRESOLVED


def test_timing_matches_bridge_for_prefixes_original_ids_and_exact_regional_view():
    raw, _, _ = fixture(K=4, H=5, W=5)
    raw["trajectory_first_burn_hour"][:] = 1
    full = source(raw).represented_events()
    np.testing.assert_array_equal(full, bridge.ignition_seconds(raw["trajectory_first_burn_hour"], seed=20261008))
    for K in (1, 2, 3):
        f = dict(raw, trajectory_first_burn_hour=raw["trajectory_first_burn_hour"][:K])
        np.testing.assert_array_equal(source(f).represented_events(), full[:K])
    selected = dict(raw, trajectory_first_burn_hour=raw["trajectory_first_burn_hour"][[3, 1]])
    s = source(selected, trajectory_indices=[3, 1], window=dict(r0=1, r1=3, c0=1, c1=3))
    np.testing.assert_array_equal(s.represented_events(), full[[3, 1], 1:4, 1:4])


@pytest.mark.parametrize("method", ["sipp", "sweep"])
@pytest.mark.parametrize("forgery", ["support", "flame"])
def test_independent_raw_checker_rejects_forged_search_evidence(monkeypatch, method, forgery):
    raw, graph, request = fixture()
    if forgery == "support":
        raw["trajectory_first_burn_hour"][:, 2, 1] = -2
        monkeypatch.setattr(kf, "support_barriers", lambda g, s: (np.ones(len(g["nodes"]), dtype=bool), np.ones(len(g["edges"]), dtype=bool)))
    else:
        raw["source_burned_area"][2, 1] = 1
        raw["trajectory_first_burn_hour"][:, 2, 1] = 0
        raw["heat__initial_burning_valid"][2, 1] = False
    class ForgedView:
        cell_intervals = {}
        ids = ()
        supported = True
        def __init__(self, s):
            pass
    monkeypatch.setattr(kf, "_SearchView", ForgedView)
    result = kf.plan_contact_route(graph, request, source(raw), method=method)
    assert result["status"] == kf.UNRESOLVED
    assert result["reason"] == "INDEPENDENT_ORIGINAL_DATA_CHECK_REFUSED"
    assert not result["contact_check"]["ok"]


@pytest.mark.parametrize("method", ["sipp", "sweep"])
def test_restricted_exhaustion_cannot_be_original_domain_no_route(method):
    raw, graph, request = fixture()
    graph["edges"] = [dict(id="ba", u="b", v="a", travel_ticks=2)]
    result = kf.plan_contact_route(graph, request, source(raw), method=method)
    assert result["status"] == kf.UNRESOLVED
    assert result["original_domain_refusal"] == "UNRESOLVED"
    assert "restricted_problem_optimality" not in result


def test_contact_source_cannot_masquerade_as_default_or_full_policy_packet():
    raw, graph, request = fixture()
    s = source(raw)
    assert sipp_plan(graph, request, s)["status"] == "UNRESOLVED"
    assert sweep_plan(graph, request, s)["status"] == "UNRESOLVED"
    with pytest.raises(TypeError, match="CONTACT_ONLY_SOURCE"):
        check_route(graph, s, request, [leg()], "b")


@pytest.mark.parametrize("method", ["sipp", "sweep"])
def test_all_known_equivalence_to_unchanged_reference_and_strict_unknown_default(method):
    raw, graph, request = fixture()
    request["incurred"] = {"m0": 0, "m1": 0}
    request["budgets"]["dose"] = {"m0": 100, "m1": 100}
    s = source(raw)
    model = bridge.to_contact_model(dict(events=s.represented_events(), current=s.current_native,
                                        settings=dict(burning_duration_s=float(s.T), member_selection=dict(weights=[.5, .5])),
                                        remaining_s=float(s.R), masks=dict(trajectory_unknown=s.unknown_native)), ids=["m0", "m1"])
    baseline = (sipp_plan if method == "sipp" else sweep_plan)(graph, request, model)
    current = kf.plan_contact_route(graph, request, s, method=method)
    assert baseline["status"] == "ROUTE" and current["status"] == kf.CHECKED
    assert baseline["arrival"] == current["arrival"]
    assert baseline["legs"] == current["legs"]
    raw["trajectory_first_burn_hour"][:, 0, 1] = -2
    unknown = source(raw)
    model = bridge.to_contact_model(dict(events=unknown.represented_events(), current=unknown.current_native,
                                        settings=dict(burning_duration_s=float(unknown.T), member_selection=dict(weights=[.5, .5])),
                                        remaining_s=float(unknown.R), masks=dict(trajectory_unknown=unknown.unknown_native)), ids=["m0", "m1"])
    assert model.supported is False
    assert sipp_plan(graph, request, model)["status"] == "UNRESOLVED"
    assert kf.plan_contact_route(graph, request, unknown, method=method)["status"] == kf.CHECKED


@pytest.mark.parametrize("change", ["clock", "grid", "outside", "initial-position", "incoming"])
def test_clock_grid_outside_and_initial_context_refuse(change):
    raw, graph, request = fixture()
    s = source(raw)
    if change == "clock":
        request["as_of"] = "2025-01-01T00:00:00.001Z"
    elif change == "grid":
        graph["grid"]["x0"] = 1
    elif change == "outside":
        graph["nodes"][0]["x"] = -0.5
    elif change == "initial-position":
        request["position"] = dict(edge="ab", fraction=.5)
    else:
        request["incoming_edge"] = "ab"
    assert kf.plan_contact_route(graph, request, s)["status"] == kf.UNRESOLVED
    assert not kf.check_contact_route(graph, request, s, [leg()], "b")["ok"]


def test_reference_and_geometry_hashes_stay_frozen():
    base = ROOT / "experimental/sipp-routing/src/wfg_sipp"
    assert hashlib.sha256((base / "frozen_sweep.py").read_bytes()).hexdigest() == "04b7387f670a5999fe267dede15afe3523f4eca6c20b9d1f5053aac25ab74057"
    assert hashlib.sha256((base / "geometry.py").read_bytes()).hexdigest() == "ac048a76387c4d46cdb8b16f4af05aa59144427608cd340c6b1d0c9cedddfcc8"


@pytest.mark.parametrize("method", ["sipp", "sweep"])
def test_private_history_omission_retains_kinematic_issue_state(monkeypatch, method):
    raw, graph, request = fixture()
    graph["edges"].append(dict(id="ba", u="b", v="a", travel_ticks=2))
    request["incoming_edge"] = "ba"
    original = json.dumps(request).encode()
    called = []
    if method == "sipp":
        original_call = kf.frontend.build_instance
        def spy(g, r, model, **kw):
            called.append((copy.deepcopy(r), model.ids))
            return original_call(g, r, model, **kw)
        monkeypatch.setattr(kf.frontend, "build_instance", spy)
    else:
        from wfg_sipp import restricted_sweep
        original_call = restricted_sweep.contact_sweep
        def spy(g, h, r, model, **kw):
            called.append((copy.deepcopy(r), model.ids))
            return original_call(g, h, r, model, **kw)
        monkeypatch.setattr(restricted_sweep, "contact_sweep", spy)
    s = source(raw)
    result = kf.plan_contact_route(graph, request, s, method=method)
    assert result["status"] == kf.CHECKED
    search_request, ids = called[0]
    assert ids == () and search_request["incurred"] == {} and search_request["budgets"] == {"dose": {}}
    for key in ("position", "incoming_edge", "departure", "as_of"):
        assert search_request[key] == request[key]
    assert json.dumps(result["original_request"]).encode() == json.dumps(request).encode() == original
    assert result["history_handling"] == dict(contact_search="THERMAL_HISTORY_AND_BUDGETS_OMITTED",
                                              history_rebinding=False, thermal_history_checked=False,
                                              kinematic_issue_context="UNCHANGED")
    assert result["full_policy_status"] == "UNKNOWN"
    with pytest.raises(AttributeError, match="immutable"):
        s.seed = 0
    graph["forbidden_turns"] = [["ba", "ab"]]
    assert kf.plan_contact_route(graph, request, s, method=method)["status"] == kf.UNRESOLVED


@pytest.mark.parametrize("mode", ["empty", "current", "new", "window", "forbidden"])
def test_all_known_both_methods_match_frozen_reference_with_dynamic_constraints(mode):
    raw, graph, request = fixture()
    if mode == "current":
        raw["source_burned_area"][2, 1] = 1
        raw["trajectory_first_burn_hour"][:, 2, 1] = 0
        raw["heat__initial_active_burning_probability"][2, 1] = 1
        raw["heat__initial_remaining_burning_duration_s"][2, 1] = 3
    elif mode == "new":
        raw["trajectory_first_burn_hour"][:, 2, 1] = 1
    elif mode == "window":
        request["destinations"][0].update(dwell=2, open_intervals=[[10, 20]])
    elif mode == "forbidden":
        graph["edges"].append(dict(id="ba", u="b", v="a", travel_ticks=2))
        request["incoming_edge"] = "ba"
        graph["forbidden_turns"] = [["ba", "ab"]]
    s = source(raw, burning_duration_s=3 if mode == "current" else 3970.4642815249267)
    model = kf._SearchView(s)
    contact_request = copy.deepcopy(request)
    contact_request.update(incurred={}, budgets={"dose": {}})
    baseline = sweep_plan(graph, contact_request, model)
    for method in ("sipp", "sweep"):
        result = kf.plan_contact_route(graph, request, s, method=method)
        if baseline["status"] == "ROUTE":
            assert result["status"] == kf.CHECKED
            assert baseline["arrival"] == result["arrival"]
        else:
            assert baseline["status"] == "NO_ROUTE" and result["status"] == kf.UNRESOLVED


def test_checker_keeps_fractional_dwell_exact_at_finite_terminal_point():
    raw, graph, request = fixture(D=3600)
    request["destinations"][0]["dwell"] = 1e-15
    # Binary64 addition at 3600 rounds this positive dwell away. The independent
    # checker must use exact represented rationals rather than that sum.
    assert 3600 + request["destinations"][0]["dwell"] == 3600
    assert not kf.check_contact_route(graph, request, source(raw), [leg(end=3600)], "b")["ok"]


def test_full_bridge_construction_timing_matches_K4_8_16_32_and_existing_window_rule():
    raw, _, _ = fixture(K=32, H=3, W=4)
    first = raw["trajectory_first_burn_hour"]
    first[:, 1:, 1] = 1
    first[:, 0, 0] = -2
    raw.update(new_burn_probability=np.full((3, 4), .5), probability_valid=np.ones((3, 4), dtype=bool),
               rate_per_h=np.zeros((3, 4)), rate_valid=np.ones((3, 4), dtype=bool))
    st = bridge.v1.settings_for(3970.4642815249267)
    assert st["seed"] == 20261008 and st["horizon_s"] == 3600 and st["timing"] == "uniform"
    full_events = source(raw).represented_events()
    window = dict(r0=1, r1=2, c0=1, c1=2)
    for K in (4, 8, 16, 32):
        forecast = dict(raw, trajectory_first_burn_hour=first[:K])
        built = bridge.construct(forecast, cutoff_utc="2025-01-01T00:00:00Z", epsg=5179, settings=st)
        represented = source(forecast).represented_events()
        np.testing.assert_array_equal(represented, built["events"])
        np.testing.assert_array_equal(represented, full_events[:K])
        # A global support refusal does not make known-cell timing disappear.
        assert not bridge.to_contact_model(built).supported
        regional = source(forecast, window=window).represented_events()
        np.testing.assert_array_equal(regional, built["events"][:, 1:3, 1:3])
        # The existing packet construct_regional rule is full construction then
        # exact slicing. Constructing a new cropped domain would redraw jitter.
        cropped = {key: (a[:, 1:3, 1:3].copy() if a.ndim == 3 else a[1:3, 1:3].copy())
                   for key, a in forecast.items() if key != "affine_transform"}
        cropped["affine_transform"] = np.array([1., 0., 1., 0., -1., 2.])
        wrong_domain = bridge.construct(cropped, cutoff_utc="2025-01-01T00:00:00Z", epsg=5179, settings=st)
        assert not np.array_equal(regional, wrong_domain["events"])
