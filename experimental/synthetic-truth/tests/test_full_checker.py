from copy import deepcopy
from wfg_synthetic_truth.frozen_checker import check_route


def fixture():
    graph = {"grid": {"x0": 0, "y0": 0, "resolution": 10, "width": 2, "height": 1},
             "nodes": [{"id": "a", "x": 1, "y": 1, "waitable": True}, {"id": "b", "x": 11, "y": 1, "waitable": True}],
             "edges": [{"id": "e", "u": "a", "v": "b", "travel_ticks": 2}], "forbidden_turns": []}
    member = {"id": "m", "breakpoints": [0, 10], "flux": [[2, 2]], "flame": [[False, False]], "support": [[True, True]]}
    hazard = {"dt": 1, "valid_from": 0, "valid_until": 10, "members": [member]}
    request = {"position": {"node": "a"}, "incoming_edge": None, "departure": 0, "horizon": 10,
               "destinations": [{"node": "b", "dwell": 2, "open_intervals": [[0, 10]]}],
               "incurred": {"m": 3}, "budgets": {"dose": {"m": 11}, "peak": 2}, "exposure_scope": "including_dwell"}
    legs = [{"kind": "EDGE", "edge": "e", "start": 0, "end": 2, "from_fraction": 0, "to_fraction": 1}]
    return graph, hazard, request, legs


def test_complete_journey_dose_includes_history_and_dwell_once():
    g, h, r, legs = fixture()
    out = check_route(g, h, r, legs, "b")
    assert out["ok"] and out["per_member"]["m"]["dose_exact"] == "11"
    r["budgets"]["dose"]["m"] = 10
    assert "DOSE_BUDGET" in check_route(g, h, r, legs, "b")["codes"]


def test_peak_contact_support_and_window_all_gate_the_journey():
    g, h, r, legs = fixture()
    r["budgets"]["peak"] = 1
    assert "PEAK_BUDGET" in check_route(g, h, r, legs, "b")["codes"]
    h["members"][0]["flame"][0][1] = True
    assert "FLAME_CONTACT" in check_route(g, h, r, legs, "b")["codes"]
    h["members"][0]["support"][0][1] = False
    assert "MISSING_SUPPORT" in check_route(g, h, r, legs, "b")["codes"]
    r["destinations"][0]["open_intervals"] = [[3, 10]]
    assert check_route(g, h, r, legs, "b")["status"] == "INVALID_ROUTE"
