"""Acceptance-window regression on the native Korean panel (Marcus, F-BASE eec16027; relayed 2026-11-12).

A naive solver that ignores the destination acceptance windows reports the earliest unconstrained arrival. All 11
naive-solver failures on the panel trip one rule, pinned here against the router itself (frontend.build_instance +
sipp.solve):
  - the five FW missions arrive exactly at the opening of a destination acceptance window
    (1459, 1270, 1064, 1655, 896 s), NOT at the earliest unconstrained arrival (968, 1032, 573, 1400, 776 s);
  - 20250325T190000Z_FD1 has no route (a naive solver reports 2921 s).
The expected values are also the F-3.2 certificate results (research/harness-2026-11/F-3.2, results/
panel_summary_py312.json), each accepted by two independent checkers.

Checked to catch the bug it targets: with every destination acceptance window widened to [0, H] (a naive solver),
sipp.solve returns exactly the naive values above for all six missions, and each would fail this test.

Needs the frozen panel inputs (`python3 tools/fetch_routing_inputs.py`, about 76 MB, into data/routing). When they are
absent the test is SKIPPED with that reason; the verified-window-routing workflow does not fetch them, so CI does not
exercise this test until it does. Inputs are identity-checked against the panel's recorded sha256 before use.
"""
import hashlib
import json
from fractions import Fraction
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PANEL = ROOT / "research/sipp-routing/native-panel-20261030"
DATA = ROOT / "data/routing"

# mission -> (expected arrival, earliest unconstrained arrival a naive solver reports); None = no route
EXPECTED = {
    "20230402T140000Z_FW2": (1459, 968),
    "20220601T020000Z_FW1": (1270, 1032),
    "20250325T170000Z_FW1": (1064, 573),
    "20220304T120000Z_FW2": (1655, 1400),
    "20250326T080000Z_FW1": (896, 776),
    "20250325T190000Z_FD1": (None, 2921),
}


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _case(mission):
    for f in sorted(PANEL.glob("case_*.json")):
        c = json.loads(f.read_text())
        if c["panel"] == "Korean" and c["mission"] == mission:
            return c
    raise AssertionError("mission %s not in the panel" % mission)


def _inputs(c):
    region, mission = c["region"], c["mission"]
    graph = DATA / "graphs" / region / "graph.json"
    request = DATA / "latest_inputs_try02/requests" / region / (mission + ".json")
    packet = DATA / "latest_inputs_try02/packets" / region / mission.split("_")[0]
    if not (graph.exists() and request.exists() and (packet / "HAZARD.json").exists()):
        pytest.skip("frozen panel inputs not fetched (python3 tools/fetch_routing_inputs.py)")
    assert _sha(graph) == c["input_sha256"]["graph"]
    assert _sha(request) == c["input_sha256"]["request"]
    for name in ("REPORT.json", "NATIVE_METADATA.json", "constructed_arrays.npz", "HAZARD.json"):
        assert _sha(packet / name) == c["input_sha256"][name], name
    return json.loads(graph.read_text()), json.loads(request.read_text()), packet


@pytest.mark.parametrize("mission", sorted(EXPECTED))
def test_arrival_is_the_acceptance_window_opening(mission):
    from wfg_scenario_members.contact import ContactModel
    from wfg_sipp import sipp
    from wfg_sipp.frontend import build_instance

    graph, request, packet = _inputs(_case(mission))
    inst, _ = build_instance(graph, request, ContactModel.from_packet(packet))
    res = sipp.solve(inst)
    want, naive = EXPECTED[mission]
    if want is None:
        assert res["status"] != "FOUND", "expected no route, got arrival %s (naive solver: %s)" % (res.get("arrival"), naive)
        return
    assert res["status"] == "FOUND"
    arrival = Fraction(res["arrival"])
    assert arrival == want, "arrival %s; expected the window opening %s, not the unconstrained %s" % (arrival, want, naive)
    assert arrival != naive
    openings = {Fraction(b) for ivs in inst.accept.values() for b, _ in ivs}
    assert arrival in openings, "arrival is not the opening of any destination acceptance window"
