"""An API body that restates a recorded mission must yield exactly the recorded request object (all 20 missions).
Fast: builds requests only, no routing."""
import json

import pytest

from api.requests_build import build_request, effective_limits

from .conftest import HAS_DATA, INPUTS, body_from_recorded, needs_data, recorded_panel

PANEL = recorded_panel()


def test_recorded_panel_matches_the_published_counts():
    assert len(PANEL) == 20
    assert sum(m["verdict"] == "checked_route" for m in PANEL) == 15 and sum(m["verdict"] == "model_no_route" for m in PANEL) == 5
    fx1 = [m for m in PANEL if (m["region"], m["case_id"]) == ("uljin_2022", "20220304T030000Z_FX1")][0]
    assert fx1["arrival_s"] == 3119 and fx1["n_legs"] == 512


@needs_data
@pytest.mark.parametrize("mission", PANEL, ids=lambda m: "%s/%s" % (m["region"], m["case_id"]))
def test_body_reproduces_recorded_request(mission):
    region, case = mission["region"], mission["case_id"]
    tag = case.split("_")[0]
    hz = json.loads((INPUTS / "packets" / region / tag / "HAZARD.json").read_text())
    sids = [m["id"] for m in hz["members"]]
    body = body_from_recorded(region, case, sids[0].rsplit(":", 1)[0])
    built = build_request(start_node=body["start"]["node_id"], dest_node=body["destination"]["node_id"],
                          depart_offset_s=body["depart_offset_s"], dwell_s=body["dwell_s"], window=body["destination_window"],
                          limits=effective_limits(body), scenario_ids=sids, horizon_s=hz["valid_until"], valid_from=hz["valid_from"],
                          hazard_version=hz["version"], as_of_iso=hz["time_origin"], dt=hz["dt"])
    recorded = json.loads((INPUTS / "requests" / region / (case + ".json")).read_text())
    assert built == recorded
    assert json.dumps(built, sort_keys=True) == json.dumps(recorded, sort_keys=True)
