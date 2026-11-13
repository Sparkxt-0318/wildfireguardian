"""SUPPORT_READ_RULE.md (+ amendment 1): support-aware READ path in PacketModel.

Inputs: F31_SUPPORT_INPUTS = a directory written by batch/support_read_inputs.py (packets A, C, D and the four T1
HEADLINE packets, INPUTS.json). The T1 reference digests (code at 969a2ca2) are results/SUPPORT_READ_T1_REFERENCE.json.
Without the inputs the tests skip, as the other data-dependent tests do.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import numpy as np
import pytest

from deadline_field import verify
from deadline_field.core import backward, issue_set
from deadline_field.pm_digest import digest
from deadline_field.real import PacketModel, load_packet
from tools.explain_deadlines.packet import Packet, PacketError

HERE = Path(__file__).resolve().parents[1]
INP = Path(os.environ.get("F31_SUPPORT_INPUTS", "/nonexistent"))
REF = HERE / "results" / "SUPPORT_READ_T1_REFERENCE.json"
pytestmark = pytest.mark.skipif(not (INP / "INPUTS.json").exists(), reason="F31_SUPPORT_INPUTS not built")

A_SHA = "d581ba929d1fb1086e1c92857f14bff25c94a7d21e224264a433b5ca4ca44198"
D_SHA = "39140349cada70644152a761b4564786da3d929202b70b2561f1f70880ce59bd"


def _inputs():
    return json.loads((INP / "INPUTS.json").read_text())


def _inst(inp):
    doc = json.loads(Path(inp["instance_json"]).read_text())
    return next(i for i in doc["instances"] if i["region"] == "uiseong_andong_2025" and i["horizon_s"] == 18000
                and i["start_tag"] == "20250325T170000Z")


def _d(graph, packet, inst, fields=True):
    d, pm = digest(PacketModel, issue_set, backward, graph, packet, inst, fields)
    return d, pm


COMPARED = ("H", "phases", "B_router", "B_closed", "present_cells", "burning_cells", "instances", "n_instances",
            "issue_sets", "n_issue_sets", "origins_not_in_graph")


# ------------------------------------------------------------------------------------------------ T1 regression
@pytest.mark.parametrize("tag", ["kriged_mean_no_reentry2", "kriged_mean_reopening", "firms_early_no_reentry2",
                                 "firms_early_reopening", "A"])
def test_t1_unmasked_packets_byte_identical_to_969a2ca2(tag):
    inp, ref = _inputs(), json.loads(REF.read_text())
    if tag == "A":
        graph, packet = inp["window_graph"], inp["A"]["dir"]
    else:
        graph, packet = inp["fdyn_graph"], inp["t1"][tag]["dir"]
    got, _ = _d(graph, packet, _inst(inp))
    want = ref[tag]
    assert want["packet_npz_sha256"] == (inp["A"]["npz_sha256"] if tag == "A" else inp["t1"][tag]["npz_sha256"])
    for k in COMPARED:
        assert got.get(k) == want.get(k), (tag, k)


# ------------------------------------------------------------------------------------------------ T2 masked loads
def test_t2_masked_twin_loads_and_equals_unmasked():
    inp = _inputs()
    assert inp["A"]["npz_sha256"] == A_SHA and inp["D"]["npz_sha256"] == D_SHA
    inst = _inst(inp)
    da, pma = _d(inp["window_graph"], inp["A"]["dir"], inst)
    dd, pmd = _d(inp["window_graph"], inp["D"]["dir"], inst)
    for k in COMPARED:
        assert da.get(k) == dd.get(k), k
    assert getattr(pmd.pk, "support_masked", False) is True
    assert getattr(pma.pk, "support_masked", False) is False
    with np.load(Path(inp["D"]["dir"]) / "constructed_arrays.npz", allow_pickle=False) as z:
        sup = np.array(z["support"]).astype(bool)
    assert all((sup[s] == sup[0]).all() for s in range(sup.shape[0]))
    want = sorted(pmd.pk.native_to_router(int(i)) for i in np.flatnonzero(~sup[0].ravel()))
    assert len(want) == 1267
    assert sorted(pmd.pk.support_false_cells) == want
    assert sorted(pmd.support_false_cells) == want


# ------------------------------------------------------------------------------------------------ T3 refusals
def test_t3a_tools_packet_reader_still_refuses_masked():
    inp = _inputs()
    from tools.explain_deadlines.geometry import Grid
    g = json.loads(Path(inp["window_graph"]).read_text())
    with pytest.raises(PacketError, match="npz contract violated"):
        Packet(inp["D"]["dir"], Grid.from_graph(g["grid"]))


def test_t3b_full_check_refuses_masked_without_running_checkers(monkeypatch):
    inp = _inputs()
    pm = PacketModel(inp["window_graph"], inp["D"]["dir"])
    hz = json.loads((Path(inp["D"]["dir"]) / "HAZARD.json").read_text())

    def boom(*a, **k):
        raise AssertionError("a checker was called on a support-masked packet")
    monkeypatch.setattr(verify, "check_route", boom)
    monkeypatch.setattr(verify, "first_contact", boom)
    node = pm.node_ids[0]
    r = verify.full_check(pm, hz, origin=node, legs=[], dest=node, dwell=60, window=[0, pm.H], departure=0)
    assert r["full_policy_ok"] is False
    assert r["full_status"] == "REFUSED_SUPPORT_MASKED"
    assert r["closed_and_router_replay_clear"] is None


def _strip_declaration(src: Path, dst: Path):
    shutil.copytree(src, dst)
    bs = json.loads((dst / "BUILD_SUMMARY.json").read_text())
    bs.pop("support_writer", None)
    (dst / "BUILD_SUMMARY.json").write_text(json.dumps(bs))
    hz = json.loads((dst / "HAZARD.json").read_text())
    hz["provenance"]["identity"].pop("support_writer", None)
    (dst / "HAZARD.json").write_text(json.dumps(hz))


def test_t3c_undeclared_mask_still_refused(tmp_path):
    inp = _inputs()
    p = tmp_path / "undeclared"
    _strip_declaration(Path(inp["D"]["dir"]), p)
    g = json.loads(Path(inp["window_graph"]).read_text())
    from tools.explain_deadlines.geometry import Grid
    with pytest.raises(PacketError, match="npz contract violated"):
        load_packet(p, Grid.from_graph(g["grid"]))


def test_t3d_kit_check_route_refuses_support_false_cell():
    inp = _inputs()
    pm = PacketModel(inp["window_graph"], inp["D"]["dir"])
    hz = json.loads((Path(inp["D"]["dir"]) / "HAZARD.json").read_text())
    false = set(pm.support_false_cells)
    node = next(n for n in pm.node_ids if pm.g.grid.cell_of(*pm.g.xy(n)) in false)
    members = [m["id"] for m in hz["members"]]
    req = {"position": {"node": node}, "incoming_edge": None, "departure": 0, "horizon": pm.H,
           "destinations": [{"node": node, "dwell": 60, "open_intervals": [[0, pm.H]]}],
           "budgets": {"peak": 10.0, "dose": {m: 100.0 for m in members}},
           "incurred": {m: 0.0 for m in members}, "exposure_scope": "including_dwell"}
    res = verify.check_route(pm.raw, hz, req, [], node)
    assert not res["ok"]
    assert "MISSING_SUPPORT" in res["codes"]


def test_t3e_c651_declared_mask_still_refused():
    inp = _inputs()
    with pytest.raises(PacketError, match="npz contract violated"):
        PacketModel(inp["window_graph"], inp["C"]["dir"])
