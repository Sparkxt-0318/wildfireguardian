from fractions import Fraction as F
import numpy as np
import pytest
from wfg_scenario_members.contact import ContactModel
from wfg_scenario_members.features import road_arrival_features
from wfg_scenario_members.reduction import distances, reduce_scenarios
from wfg_scenario_members.acceptance import accept, weighted_cvar


def fixture():
    graph = {"crs": "EPSG:3857", "grid": {"x0": 0, "y0": 0, "resolution": 10, "width": 3, "height": 2},
             "nodes": [{"id": "a", "x": 1, "y": 1}, {"id": "b", "x": 21, "y": 1}],
             "edges": [{"id": "e", "u": "a", "v": "b", "travel_ticks": 20}]}
    ign = np.full((3, 2, 3), np.inf); ign[0, 1, 1] = 30; ign[1, 1, 1] = 40
    model = ContactModel.from_arrays(ign, np.zeros((2, 3), bool), 10, 0)
    return graph, model


def test_exact_full_traversal_first_departure_and_selector_compatibility():
    g, m = fixture()
    f = road_arrival_features(g, m, horizon=100)
    # Middle-cell occupied at [9/20,19/20] along traversal, so 30-19=11.
    assert f["first_unsafe_departure_s"][:, 0].tolist() == [11, 21, np.inf]
    assert f["capped_arrival_s"][:, 0].tolist() == [11, 21, 100]
    assert f["edge_lengths_m"].tolist() == [20]
    d = distances(np.full((3, 2, 3), -2), horizon_hours=100/3600, method="edge_arrival",
                  edge_arrival_s=f["first_unsafe_departure_s"], edge_lengths_m=f["edge_lengths_m"])
    assert d[0, 1] == 200
    assert sum(reduce_scenarios(d, 2)["weights"]) == pytest.approx(1)


def test_boundary_point_contact_is_not_lost_and_expiry_is_half_open():
    g, m = fixture(); g["nodes"][1]["x"] = 10
    # At final gridline endpoint the point is in middle cell at z=1.
    assert road_arrival_features(g, m, horizon=100)["first_unsafe_departure_s"][0, 0] == 10
    # Event [30,40) cannot block traversal wholly starting at40.
    assert np.isinf(road_arrival_features(g, m, departure=40, horizon=100)["first_unsafe_departure_s"][0, 0])


def test_unknown_outside_and_native_orientation_preserved():
    g, m = fixture(); u = np.zeros((3, 2, 3), bool); u[0, 0, 1] = True
    assert road_arrival_features(g, m, horizon=100, unknown_native=u)["known"].all()
    u[0, 1, 1] = True
    f = road_arrival_features(g, m, horizon=100, unknown_native=u)
    assert not f["known"][0, 0] and np.isnan(f["capped_arrival_s"][0, 0])
    with pytest.raises(ValueError, match="Unknown positive"):
        distances(np.zeros((3, 2, 3), int), horizon_hours=1, method="edge_arrival", edge_arrival_s=f["first_unsafe_departure_s"], edge_lengths_m=[20])
    assert not distances(np.zeros((3, 2, 3), int), horizon_hours=1, method="edge_arrival", edge_arrival_s=f["first_unsafe_departure_s"], edge_lengths_m=[0]).any()
    m.supported = False
    assert not road_arrival_features(g, m, horizon=100)["known"].any()
    g["nodes"][1]["x"] = 30  # invalid col W must not alias the following row
    with pytest.raises(ValueError, match="Outside"):
        road_arrival_features(g, m, horizon=100)


def test_stable_extreme_weights_and_tail_boundary():
    assert weighted_cvar([10, 20], [1e308, 1e308], alpha=1, horizon=30) == 15
    assert weighted_cvar([10, 20], [1, 3], alpha=.5, horizon=30) == 20
    assert weighted_cvar([10, 20], [1, 3], alpha=1, horizon=30) == 17.5
    assert weighted_cvar([10, 20], [1, 3], alpha=1e-20, horizon=30) == 20
    assert accept([True, False], rule="k_of_m", k=1, weights=[1e308, 1e308])["weights"] == [.5, .5]
    for bad in ([0, 0], [np.nan, 1], [np.inf, 1], [-1, 1]):
        with pytest.raises(ValueError): weighted_cvar([10, 20], bad, alpha=1, horizon=30)
        with pytest.raises(ValueError): accept([True, False], weights=bad)
    assert weighted_cvar([10, 20], [0, 1], alpha=1, horizon=30) == 20


def test_feature_matches_independent_integer_departure_enumeration():
    from wfg_sipp.geometry import edge_occupancies
    g, m = fixture()
    rng = np.random.default_rng(20261030)
    occ = edge_occupancies(g["edges"][0], 0, 20, graph=g)
    for _ in range(100):
        b = F(int(rng.integers(0, 100)), 3)
        m.events = [{1: b}]  # middle cell, graph south-up
        m.ids = ["m"]
        candidate = []
        for t in range(81):
            if any(o["cell"] == 1 and F(t)+o["end"] >= b and F(t)+o["start"] < b+m.T for o in occ):
                candidate.append(t)
        observed = road_arrival_features(g, m, horizon=100)["first_unsafe_departure_s"][0, 0]
        assert observed == (min(candidate) if candidate else np.inf)


def test_byte_audit_distinguishes_dtype_and_nan_payload_bits():
    import runpy
    from pathlib import Path
    root = Path(__file__).resolve().parents[3]
    compare = runpy.run_path(str(root/"research/scenario-members/audit_export_bytes.py"))["compare_arrays"]
    a = np.array([0x7ff8000000000001], dtype=np.uint64).view(np.float64)
    b = np.array([0x7ff8000000000002], dtype=np.uint64).view(np.float64)
    assert np.array_equal(a, b, equal_nan=True)
    assert compare(a, b)["payload_bytes_equal"] is False
    assert compare(np.array([1], np.int16), np.array([1], np.int32))["dtype_equal"] is False


def test_weight_underflow_refused_and_tail_arithmetic_keeps_tiny_alpha():
    with pytest.raises(ValueError, match="underflows"):
        accept([True, False], weights=[1e-308, 1e308])
    with pytest.raises(ValueError, match="underflows"):
        weighted_cvar([1, 2], [1e-308, 1e308], alpha=1, horizon=3)
    assert weighted_cvar([.1, .2], [1, 1], alpha=1e-320, horizon=1) == .2
