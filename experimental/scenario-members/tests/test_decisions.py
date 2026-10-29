"""Checker wrapper, decisions, acceptance, reduction and cheap-checker tests (routing environment)."""
import json
import math
import sys
from fractions import Fraction as F
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "src"))
import bridge_v2 as B2  # noqa: E402
from wfg_members import acceptance as A  # noqa: E402
from wfg_members import check, coverage, decide, kit, planner, reduction  # noqa: E402
from wfg_members.contact import ContactModel  # noqa: E402

needs_inputs = pytest.mark.skipif(not kit.inputs_available(), reason="frozen routing inputs not present")

# Frozen candidate outcomes (research/routing/request-window-20261029/EXECUTIONS.csv, RDA_CAND, both repetitions).
FROZEN = {"20220304T030000Z_FX1": 3119, "20220601T080000Z_FX1": None, "20230402T070000Z_FX1": None, "20250323T010000Z_FX2": 2540,
          "20250325T190000Z_FX2": 2512, "20220304T060000Z_FL1": 2067, "20220601T020000Z_FW1": 1270, "20230402T140000Z_FW2": 1459,
          "20250324T090000Z_FL2": 2143, "20250325T230000Z_FL2": 1922, "20220304T120000Z_FW2": 1655, "20220601T080000Z_FD1": None,
          "20230402T230000Z_FD1": 531, "20250325T170000Z_FW1": 1064, "20250326T080000Z_FW1": 896, "20220304T030000Z_FD1": 1589,
          "20220531T100000Z_FN1": 1142, "20230402T070000Z_FN1": None, "20250323T010000Z_FD1": 2460, "20250325T190000Z_FD1": None}
SMALL = [(r, t, e, m) for r, t, e, m in kit.missions() if r in ("hongseong_2023", "miryang_2022", "uljin_2022")]


def _load(region, tag, event, mission):
    p = kit.paths(region, tag, event, mission)
    return (json.loads(p["graph"].read_text()), json.loads((p["packet"] / "HAZARD.json").read_text()),
            json.loads(p["request"].read_text()), ContactModel.from_packet(p["packet"]), p)


# ------------------------------------------------------------------------------------------------ pure unit tests
def test_acceptance_rules_and_cvar():
    w = [F(1, 4)] * 4
    assert A.passes([True] * 4, w, {"rule": "all"})
    assert not A.passes([True, True, True, False], w, {"rule": "all"})
    assert A.passes([True, True, True, False], w, {"rule": "k_of_m", "k": 3, "m": 4})
    assert not A.passes([True, True, False, False], w, {"rule": "k_of_m", "k": 3, "m": 4})
    assert A.passes([True, False], [0.95, 0.05], {"rule": "k_of_m", "k": 9, "m": 10})
    assert A.k_of_m_rule(16, 0.9) == {"rule": "k_of_m", "k": 15, "m": 16}
    assert A.k_of_m_rule(4, 0.9)["k"] == 4
    assert A.cvar([10, 20, 30, 40], w, F(1, 4)) == 40
    assert A.cvar([10, 20, 30, 40], w, F(1, 2)) == 35
    assert A.cvar([10, 20, 30, 40], w, 1) == 25
    assert A.cvar([10, 40], [F(9, 10), F(1, 10)], F(1, 5)) == 25
    assert A.member_arrivals(100, [True, False], 3600) == [100.0, 3600.0]


def test_forward_selection_weights_and_costs():
    pts = np.array([0.0, 0.1, 0.2, 10.0, 10.1, 30.0])
    C = np.abs(pts[:, None] - pts[None, :])
    J, costs = reduction.forward_selection(C, 3)
    assert J == [2, 5, 3]          # greedy order with lowest-index ties (not the optimal 3-subset {1, 4, 5})
    assert all(a >= b for a, b in zip(costs, costs[1:]))
    q, cost, _ = reduction.redistribute(C, J)
    assert math.isclose(q.sum(), 1.0) and math.isclose(cost, costs[-1])
    assert np.allclose(sorted(q), sorted([3 / 6, 2 / 6, 1 / 6]))
    km = reduction.k_medoids(C, 3, seed=1)
    assert sorted(km) == sorted(reduction.k_medoids(C, 3, seed=1))
    for K in (1, 2, 3, 4):
        rec = reduction.reduce_members(C, K, "forward_selection", append_extremes=False)
        assert len(rec["indices"]) == K and math.isclose(sum(rec["weights"]), 1.0)
    A_ = np.array([[5.0, 9.0], [1.0, 9.0], [5.0, 2.0], [5.0, 9.0], [5.0, 9.0], [5.0, 9.0]])
    rec = reduction.reduce_members(C, 2, "first_k", A=A_, corridors=[[0], [1]], shared_first=[5.0, 9.0])
    assert rec["selected"] == [0, 1] and rec["extremes"] == [2]


def test_l1_distance_matches_direct_computation():
    rng = np.random.default_rng(0)
    X = rng.integers(0, 3, (40, 7)).astype(float)
    X[5] = X[3]
    w = rng.random(7)
    D = reduction.l1_distance(X, w)
    assert np.allclose(D, (np.abs(X[:, None, :] - X[None, :, :]) * w).sum(axis=2))


# ------------------------------------------------------------------------------------------------ frozen inputs
@needs_inputs
@pytest.mark.parametrize("region,tag", [("uljin_2022", "20220304T060000Z"), ("uiseong_andong_2025", "20250323T010000Z")])
def test_contact_model_equals_the_frozen_road_bound_model_intervals(region, tag):
    K = kit.install()
    import road_bounds
    p = kit.paths(region, tag)
    graph = json.loads(p["graph"].read_text())
    M = road_bounds.RoadBoundModel(graph, p["packet"])
    assert ContactModel.from_packet(p["packet"]).cell_intervals == M.cell_intervals


@needs_inputs
@pytest.mark.parametrize("region,tag,event,mission", SMALL)
def test_v1_decisions_reproduce_the_frozen_candidate_outcomes(region, tag, event, mission):
    graph, hz, req, cm, _ = _load(region, tag, event, mission)
    d = decide.decide(graph, hz, req, cm)
    expected = FROZEN["%s_%s" % (tag, mission)]
    if expected is None:
        assert d["verdict"] == decide.NOROUTE
    else:
        assert d["verdict"] == decide.CHECKED and d["arrival_s"] == expected


@needs_inputs
@pytest.mark.parametrize("region,tag,event,mission", [("uljin_2022", "20220304T060000Z", "KFS_02", "FL1"),
                                                      ("hongseong_2023", "20230402T230000Z", "KFS_05", "FD1")])
def test_one_pass_member_reports_equal_per_member_frozen_checks(region, tag, event, mission):
    graph, hz, req, cm, _ = _load(region, tag, event, mission)
    for model in (cm.empty(), cm):                      # travel-only route (may contact) and the checked route
        plan = planner.sweep_plan(graph, req, model)
        fast = check.member_reports(graph, hz, req, plan["legs"], plan["destination"])
        slow = check.member_reports(graph, hz, req, plan["legs"], plan["destination"], per_member_runs=True)
        for a, b in zip(fast, slow):
            for k in ("contact", "peak_kw_m2", "dose_exact", "passed", "peak_ok", "dose_ok"):
                assert a[k] == b[k], (k, a, b)


@needs_inputs
def test_cheap_checker_agrees_with_the_frozen_checker_on_built_members():
    region, tag, event, mission = "uljin_2022", "20220304T060000Z", "KFS_02", "FL1"
    K = kit.install()
    graph, _, req0, cm, p = _load(region, tag, event, mission)
    fc, record = B2.load_export(p["export_npz"], p["export_record"])
    T = float(fc["contract__cell_duration_s"])
    q = np.where(fc["probability_valid"], fc["new_burn_probability"], 0.0)
    rng = np.random.default_rng(7)
    fbh = np.where(fc["probability_valid"][None] & (rng.random((12,) + q.shape) < np.minimum(1, q[None] * 40)), 1, -1).astype(np.int16)
    fbh[:, (fc["source_burned_area_valid"] & (np.nan_to_num(fc["source_burned_area"]) == 1))] = 0
    sel = list(range(12))
    ev = B2.ignition_seconds(fbh, sel)
    settings = B2.v2_settings(T, member_count=12, timing="uniform", selection={"method": "test", "indices": sel})
    _, built = B2.construct_v2(fc, record, cutoff_iso=kit.cutoff_iso(tag), event_id=event, epsg=record["epsg"], events_full=ev,
                               settings=settings, window=None)
    ids = B2.member_ids("t", 12)
    hz = B2.hazard_arrays(built, ids)
    model = ContactModel.from_arrays(built["events"], built["current"], T, built["remaining_s"], ids=ids)
    req = B2.rekey_request_k(req0, ids, kit.cutoff_iso(tag))
    md = json.loads((p["packet"] / "NATIVE_METADATA.json").read_text())
    kern = coverage.Kernels(md["affine_transform"], K["bridge"].settings_for(T), record["epsg"], tuple(md["shape"]))
    with np.load(p["packet"] / "constructed_arrays.npz") as a:
        cur_flux = kern.of_mask(a["current_active"])
    nodes = {n["id"]: n for n in graph["nodes"]}
    issue = K["independent"]._cell(graph, nodes[req["position"]["node"]])
    agree = 0
    for m in (model.empty(), model.shared_only(), model):
        plan = planner.sweep_plan(graph, req, m)
        if plan["status"] != planner.ROUTE:
            continue
        full = check.member_reports(graph, hz, req, plan["legs"], plan["destination"])
        ev_ = coverage.JourneyEvaluator(check.journey_spans(graph, req, plan["legs"], plan["destination"]), issue, req["departure"], req)
        _, flags = coverage.coverage(ev_, model, kernels=kern, current_flux=cur_flux)
        for k, r in enumerate(full):
            assert flags[k] == r["passed"]
            ok, info = ev_.passes(model.events[k], model.T, set(model.current), model.R, kern, cur_flux)
            if not info["contact"]:
                assert info["dose_kj_m2"] >= r["dose_kj_m2"] - 1e-9
                assert info["dose_kj_m2"] <= r["dose_kj_m2"] * (1 + 1e-5) + 1e-6   # conservative, within 1e-5
            agree += 1
    assert agree >= 12
