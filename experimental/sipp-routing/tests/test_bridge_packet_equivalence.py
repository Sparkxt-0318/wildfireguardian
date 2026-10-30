"""A complete, explicit trajectory fixture through bridge v2 and both planners."""
import importlib.util
import copy
import json
from pathlib import Path
import numpy as np
from wfg_scenario_members.contact import ContactModel
from wfg_sipp.frontend import sipp_plan
from wfg_sipp.adapter import sweep_plan

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("_bridge_fixture", ROOT / "experimental/scenario-members/bridge_v2.py")
bridge = importlib.util.module_from_spec(spec); spec.loader.exec_module(bridge)


def test_trajectory_bridge_packet_gives_identical_arrival_and_full_centre_check(tmp_path):
    from wfg_synthetic_truth.frozen_checker import check_route
    from wfg_latest.router_validation.validation import chord_segments
    z = np.zeros((3, 3), dtype=float); valid = np.ones((3, 3), dtype=bool)
    f = dict(new_burn_probability=z.copy(), probability_valid=valid.copy(), rate_per_h=z.copy(), rate_valid=valid.copy(),
             source_burned_area=z.copy(), source_burned_area_valid=valid.copy(),
             heat__initial_active_burning_probability=z.copy(), heat__initial_remaining_burning_duration_s=z.copy(),
             heat__initial_burning_valid=valid.copy(), affine_transform=np.array([10., 0., 0., 0., -10., 30.]))
    first = np.full((2, 3, 3), -1, dtype=np.int16); first[:, 1, 1] = 1
    f["new_burn_probability"][1, 1] = 0.5; f["trajectory_first_burn_hour"] = first
    built = bridge.construct(f, cutoff_utc="2025-01-01T00:00:00Z", epsg=5179, settings=bridge.v1.settings_for(100))
    graph = {"revision": "fixture", "crs": "EPSG:5179", "grid": {"x0": 0, "y0": 0, "resolution": 10, "width": 3, "height": 3},
             "nodes": [{"id": "a", "x": 1, "y": 1, "waitable": False}, {"id": "b", "x": 21, "y": 1, "waitable": False}],
             "edges": [{"id": "e", "u": "a", "v": "b", "travel_ticks": 2}], "forbidden_turns": [], "mid_edge_reversal": False}
    graph["edges"][0]["segments"] = chord_segments(graph["grid"], *graph["nodes"])
    hazard = bridge.to_edgegrid(graph, built, cutoff_utc="2025-01-01T00:00:00Z",
        identity={"crs": "EPSG:5179", "affine_transform": built["affine_transform"], "scenario_ids": ["m0", "m1"]})
    request = {"position": {"node": "a"}, "incoming_edge": None, "departure": 0, "horizon": 3600,
               "destinations": [{"node": "b", "dwell": 0, "open_intervals": [[0, 3600]]}],
               "incurred": {"m0": 0, "m1": 0}, "budgets": {"peak": 10, "dose": {"m0": 1000, "m1": 1000}}, "exposure_scope": "including_dwell"}
    model = ContactModel.from_arrays(built["events"], built["current"], 100, built["remaining_s"], ids=["m0", "m1"])
    a = sipp_plan(graph, request, model); b = sweep_plan(graph, request, model)
    assert (a["status"], a["arrival"]) == (b["status"], b["arrival"]) == ("ROUTE", 2)
    assert check_route(graph, hazard, request, a["legs"], a["destination"])["ok"]
    identity = bridge.packet_identity(graph, built, cutoff_utc="2025-01-01T00:00:00Z", forecast_identity={"fixture": True})
    new_request = copy.deepcopy(request)
    new_request["incurred"] = {mid: 0 for mid in identity["scenario_ids"]}
    new_request["budgets"]["dose"] = {mid: 1000 for mid in identity["scenario_ids"]}
    metadata = {"construction": {"assumptions": dict(built["settings"]),
                  "parent_forecast": {"cutoff_utc": "2025-01-01T00:00:00Z"}},
                "time_origin": "2025-01-01T00:00:00Z", "crs": graph["crs"]}
    folder = tmp_path / "packet"
    pins = bridge.write_packet(folder, graph, built, cutoff_utc="2025-01-01T00:00:00Z",
                               template_metadata=metadata, request_template=new_request,
                               forecast_identity={"fixture": True})
    assert set(pins) == {"HAZARD.json", "REPORT.json", "NATIVE_METADATA.json", "constructed_arrays.npz"}
    native_spec = importlib.util.spec_from_file_location("_ffi_native_fixture", ROOT / "integration/kit/runner/ffi_independent_checker.py")
    native = importlib.util.module_from_spec(native_spec); native_spec.loader.exec_module(native)
    parsed = native.Packet(folder, native.Graph(graph))
    assert parsed.ids == identity["scenario_ids"]
    written_hazard = json.loads((folder / "HAZARD.json").read_text())
    assert check_route(graph, written_hazard, new_request, a["legs"], a["destination"])["ok"]
