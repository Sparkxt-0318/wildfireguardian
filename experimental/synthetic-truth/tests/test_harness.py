"""Synthetic-truth harness tests: the four required behaviours, device_offline masking, truth builders."""
import json
import sys
from fractions import Fraction as F
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
from wfg_osse import harness, score, truth as TR  # noqa: E402
from wfg_members import kit, planner  # noqa: E402
from wfg_members.contact import ContactModel  # noqa: E402
from wfg_sipp.frontend import sipp_plan  # noqa: E402

needs_inputs = pytest.mark.skipif(not kit.inputs_available(), reason="frozen routing inputs not present")
T = F(100)


def line_case():
    """Four cells in a row; nodes at cell centres; a direct road n0-n1-n2-n3 (10 s per edge) and a slow bypass
    n0-n4-n3 through a fifth cell row above (60 s per edge)."""
    nodes = [{"id": "n%d" % i, "x": 50.0 + 100 * i, "y": 50.0, "waitable": True} for i in range(4)]
    nodes.append({"id": "n4", "x": 150.0, "y": 150.0, "waitable": True})
    edges = [{"id": "e%d" % i, "u": "n%d" % i, "v": "n%d" % (i + 1), "travel_ticks": 10} for i in range(3)]
    edges += [{"id": "b0", "u": "n0", "v": "n4", "travel_ticks": 60}, {"id": "b1", "u": "n4", "v": "n3", "travel_ticks": 60}]
    graph = {"nodes": nodes, "edges": edges, "forbidden_turns": [],
             "grid": {"x0": 0.0, "y0": 0.0, "resolution": 100.0, "width": 4, "height": 2}}
    request = {"position": {"node": "n0"}, "incoming_edge": None, "departure": 0, "horizon": 300.0,
               "destinations": [{"node": "n3", "dwell": 0, "open_intervals": [[0, 300]]}],
               "incurred": {"m0": 0}, "budgets": {"peak": 10, "dose": {"m0": 100}}, "hazard_version": 1}
    return graph, request


def members(events, duration=T):
    return ContactModel(shape=(2, 4), T=duration, R=0, current_native=[], events_native=events, ids=["m%d" % i for i in range(len(events))])


def graph_cell(row_from_south, col):
    return row_from_south * 4 + col


def native(row_from_south, col):
    return (1 - row_from_south) * 4 + col


def test_route_through_a_cell_burning_at_traversal_time_is_false_safe():
    graph, req = line_case()
    model = members([{}])
    dec = harness.decide(graph, req, model)
    assert dec["verdict"] == "checked_route" and dec["arrival_s"] == 30
    shared = sipp_plan(graph, req, model.shared_only())
    burning = TR.Truth("holdout_trajectory", "burns_during_traversal", {graph_cell(0, 1): F(5)}, [], F(0), T)
    later = TR.Truth("holdout_trajectory", "burns_after_traversal", {graph_cell(0, 1): F(150)}, [], F(0), T)
    rec = harness.score_against(graph, req, dec, [burning, later], cutoff="test", region="test", mission="M",
                                forecast_source="no_fire", shared_route=shared)
    assert rec[0]["true_contact"] and rec[0]["false_safe"] and not rec[0]["false_refusal"]
    assert rec[0]["clairvoyant_arrival_s"] == 120 and rec[0]["regret_s"] == 30 - 120   # the truth forces the bypass
    assert not rec[1]["true_contact"] and not rec[1]["false_safe"] and rec[1]["regret_s"] == 0


def test_refusal_with_a_clairvoyant_route_is_false_refusal():
    graph, req = line_case()
    blocked = members([{native(0, 1): F(0), native(1, 1): F(0)}], F(400))   # both routes blocked over the horizon
    dec = harness.decide(graph, req, blocked)
    assert dec["verdict"] == "model_no_route"
    shared = sipp_plan(graph, req, blocked.shared_only())
    clear = TR.Truth("holdout_trajectory", "no_fire", {}, [], F(0), T)
    fire = TR.Truth("holdout_trajectory", "fire", {graph_cell(0, 1): F(0), graph_cell(1, 1): F(0)}, [], F(0), F(400))
    rec = harness.score_against(graph, req, dec, [clear, fire], cutoff="t", region="t", mission="M", forecast_source="f",
                                shared_route=shared)
    assert rec[0]["false_refusal"] is True and rec[0]["refusal_kind"] == "model_no_route" and not rec[0]["false_safe"]
    assert rec[1]["false_refusal"] is False                               # no clairvoyant route: a correct refusal


def test_clairvoyant_without_fire_equals_travel_only_optimum():
    graph, req = line_case()
    model = members([{native(0, 1): F(0)}])
    none = TR.Truth("holdout_trajectory", "none", {}, [], F(0), T)
    cl = score.clairvoyant(graph, req, none, planner=sipp_plan, shared_route=None,
                           evaluator_for=lambda r: score.journey_evaluator(graph, req, r, kit.install()["independent"]))
    assert cl["arrival"] == sipp_plan(graph, req, model.empty())["arrival"] == 30


def _offline(observations):
    return TR.device_offline({"schema": TR.DEVICE_SCHEMA, "label": "fixture", "horizon_s": 300,
                              "observations": observations, "provenance": {"fixture": True}})


def test_device_offline_unknown_cells_can_neither_cause_nor_clear_false_safe():
    graph, req = line_case()
    dec = harness.decide(graph, req, members([{}]))
    shared = sipp_plan(graph, req, members([{}]).shared_only())
    seen = [{"cell": graph_cell(0, c), "not_burning": [[0, 301]]} for c in (0, 2, 3)]
    unknown_only = _offline(seen)                                           # cell 1 on the route is never observed
    rec = harness.score_against(graph, req, dec, [unknown_only], cutoff="t", region="t", mission="M", forecast_source="f",
                                shared_route=shared)[0]
    assert rec["unknown_exposure"] is True and rec["true_contact"] is False and rec["false_safe"] is False
    known_and_unknown = _offline([{"cell": graph_cell(0, 0), "not_burning": [[0, 301]]},
                                  {"cell": graph_cell(0, 2), "burning": [[0, 301]]},
                                  {"cell": graph_cell(0, 3), "not_burning": [[0, 301]]}])
    rec = harness.score_against(graph, req, dec, [known_and_unknown], cutoff="t", region="t", mission="M", forecast_source="f",
                                shared_route=shared)[0]
    assert rec["unknown_exposure"] is True and rec["true_contact"] is True and rec["false_safe"] is True
    assert rec["true_peak"] is None and rec["true_dose"] is None
    # the hidden state of an unknown cell cannot change any record: both hidden worlds give the same observation packet
    hidden_a = _offline(seen)
    hidden_b = _offline(seen)
    ra = harness.score_against(graph, req, dec, [hidden_a], cutoff="t", region="t", mission="M", forecast_source="f", shared_route=shared)
    rb = harness.score_against(graph, req, dec, [hidden_b], cutoff="t", region="t", mission="M", forecast_source="f", shared_route=shared)
    assert ra == rb


def test_device_offline_refusal_is_unscorable_when_only_unknown_routes_exist():
    graph, req = line_case()
    blocked = members([{native(0, 1): F(0), native(1, 1): F(0)}], F(400))
    dec = harness.decide(graph, req, blocked)
    obs = _offline([{"cell": graph_cell(0, c), "not_burning": [[0, 301]]} for c in (0, 2, 3)])
    cells = {graph_cell(r, c) for r in range(2) for c in range(4)}
    rec = harness.score_against(graph, req, dec, [obs], cutoff="t", region="t", mission="M", forecast_source="f",
                                shared_route=None, cells=cells)[0]
    assert rec["verdict"] == "model_no_route" and rec["false_refusal"] is None
    full = _offline([{"cell": c, "not_burning": [[0, 301]]} for c in cells])
    rec = harness.score_against(graph, req, dec, [full], cutoff="t", region="t", mission="M", forecast_source="f",
                                shared_route=None, cells=cells)[0]
    assert rec["false_refusal"] is True                                     # a fully observed clear route existed


def test_device_offline_schema_is_enforced():
    with pytest.raises(ValueError):
        TR.device_offline({"schema": "other", "observations": []})
    with pytest.raises(ValueError):
        _offline([{"cell": 1, "burning": [[0, 10]], "not_burning": [[5, 20]]}])
    with pytest.raises(ValueError):
        _offline([{"cell": 1, "burning": [[10, 10]]}])


@needs_inputs
def test_frozen_uljin_verdict_is_reproduced_and_truth_equal_to_members_gives_no_false_safe():
    K = kit.install()
    from wfg_members import coverage, decide as D
    region, tag, event, mission = "uljin_2022", "20220304T030000Z", "KFS_02", "FX1"
    p = kit.paths(region, tag, event, mission)
    graph, req = json.loads(p["graph"].read_text()), json.loads(p["request"].read_text())
    hz = json.loads((p["packet"] / "HAZARD.json").read_text())
    model = ContactModel.from_packet(p["packet"])
    md = json.loads((p["packet"] / "NATIVE_METADATA.json").read_text())
    kern = coverage.Kernels(md["affine_transform"], K["bridge"].settings_for(float(model.T)), 5179, tuple(md["shape"]))
    with np.load(p["packet"] / "constructed_arrays.npz") as a:
        cur = kern.of_mask(a["current_active"])
    dec = harness.decide(graph, req, model, kernels=kern, current_flux=cur)
    frozen = D.decide(graph, hz, req, model)
    assert dec["verdict"] == frozen["verdict"] == "checked_route" and dec["arrival_s"] == frozen["arrival_s"] == 3119
    truths = [TR.Truth("holdout_trajectory", "member_%d" % k, dict(model.events[k]), list(model.current), model.R, model.T)
              for k in range(len(model.ids))]
    shared = sipp_plan(graph, req, model.shared_only())
    recs = harness.score_against(graph, req, dec, truths, cutoff=tag, region=region, mission=mission, forecast_source="v1_frozen",
                                 shared_route=shared, kernels=kern, current_flux=cur)
    assert all(r["false_safe"] is False and r["false_refusal"] is False for r in recs)
    none = TR.Truth("holdout_trajectory", "none", {}, [], F(0), model.T)
    cl = score.clairvoyant(graph, req, none, planner=sipp_plan, shared_route=None, kernels=kern, current_flux=np.zeros_like(cur),
                           evaluator_for=lambda r: score.journey_evaluator(graph, req, r, K["independent"]))
    assert cl["arrival"] == sipp_plan(graph, req, model.empty())["arrival"]


@needs_inputs
def test_reconstructed_arrival_truth_matches_the_export_cutoff_state():
    toa = Path("/home/user/wfg-data-1c/zenodo_21788344/extracted/rasters_kr/KFS_02_pswt_ok_toa.tif")
    if not toa.is_file():
        pytest.skip("Zenodo time-of-arrival archive not extracted on this host")
    p = kit.paths("uljin_2022", "20220304T060000Z", "KFS_02")
    rec = json.loads(p["export_record"].read_text())
    with np.load(p["export_npz"]) as a:
        export = {k: a[k] for k in a.files}
    model = ContactModel.from_packet(p["packet"])
    t = TR.reconstructed_arrival(toa, t0_utc="2022-03-04T02:17:00+00:00", cutoff_utc="2022-03-04T06:00:00Z", window=None,
                                 export=export, expected_sha256=rec["data_identity_sha256"]["regions/KFS_02/arrival_time_hours.tif"],
                                 current_graph=model.current, R=model.R, T=model.T, shape=model.shape)
    assert t.source == "reconstructed_arrival" and all(0 < float(b) < 3600 for b in t.births.values())
    assert not set(t.births) & set(model.current)


def test_external_simulator_arrival_grid_becomes_first_new_ignitions(tmp_path):
    # 4 x 4 simulator pixels of 50 m over a 2 x 2 routing grid of 100 m cells; arrivals in minutes since start
    grid = {"x0": 0.0, "y0": 0.0, "resolution": 100.0, "width": 2, "height": 2}
    rows = ["-9999 30 -9999 -9999", "-9999 -9999 70 80", "5 10 -9999 -9999", "-1 20 -9999 90"]
    (tmp_path / "a.asc").write_text("NCOLS 4\nNROWS 4\nXLLCORNER 0\nYLLCORNER 0\nCELLSIZE 50\nNODATA_VALUE -9999\n"
                                    + "\n".join(rows) + "\n")
    t = TR.external_simulator(tmp_path / "a.asc", grid=grid, start_offset_s=-600, current_graph=[], R=0, T=T)
    # north row (graph row 1): cell 2 earliest 30 min -> 1200 s; cell 3 earliest 70 min -> 3600 s (not inside the horizon)
    # south row (graph row 0): cell 0 earliest 5 min -> -300 s (before the cutoff); cell 1 at 90 min -> beyond the horizon
    assert t.births == {2: F(1200)}
    assert t.source == "external_simulator"


FARSITE_OUT = Path("/home/user/wfg-farsite-1c/run_flatland/out/flat_ArrivalTime.asc")


@pytest.mark.skipif(not FARSITE_OUT.is_file(), reason="FARSITE flatland example output not present on this host")
def test_external_simulator_reads_a_real_farsite_arrival_grid():
    grid = {"x0": 20000.0, "y0": 20000.0, "resolution": 375.0, "width": 8, "height": 8}
    t = TR.external_simulator(FARSITE_OUT, grid=grid, start_offset_s=0, current_graph=[], R=0, T=T, horizon_s=7 * 3600)
    assert t.births and all(0 < float(b) < 7 * 3600 for b in t.births.values())
