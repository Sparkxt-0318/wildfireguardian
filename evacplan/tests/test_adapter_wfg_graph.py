"""Router graph.json -> evacplan RoadGraph, reusing wfg_latest's own admission checks.

The real Korean graphs and packets (fetched release inputs, never copied into the repo) are read
from ``$WFG_ROUTING_INPUTS`` (default: this session's scratchpad); those tests skip when absent.
"""
import copy
import json
import os
from pathlib import Path

import numpy as np
import pytest

import hazard_contract as hc
from hazard_contract.geometry import polyline_cells
from wfg_latest.router_validation import validation as RV
from wfg_latest.router_validation.admission_geometry import make_variants
from evacplan import Budgets, HazardRef, Instance, State, check_itinerary
from evacplan.adapters import from_wfg_graph, router_grid_transform
from evacplan_testkit import drive, itinerary, make_set, quiet, vehicle

ROUTING_INPUTS = Path(os.environ.get(
    "WFG_ROUTING_INPUTS",
    "/tmp/claude-0/-home-user-wildfireguardian/a9efaa5c-c674-5d4b-a7c3-c4ab7b53f43d/scratchpad/routing_inputs"))
GRAPHS = ROUTING_INPUTS / "graphs"
PACKETS = ROUTING_INPUTS / "latest_inputs_try02" / "packets"
REGIONS = ["hongseong_2023", "miryang_2022", "uljin_2022", "uiseong_andong_2025", "yeongdeok_2025"]
real = pytest.mark.skipif(not GRAPHS.is_dir(), reason="routing inputs not present (set WFG_ROUTING_INPUTS)")


# ------------------------------------------------------------- a tiny router graph (always runs)
def tiny_router_graph():
    """3 x 3 grid of 100 m south-up cells; segments from the router's own exact chord geometry."""
    grid = {"x0": 0.0, "y0": 0.0, "resolution": 100.0, "width": 3, "height": 3}
    nodes = [{"id": "a", "x": 50.0, "y": 50.0, "waitable": True}, {"id": "b", "x": 250.0, "y": 50.0, "waitable": False},
             {"id": "c", "x": 250.0, "y": 250.0, "waitable": False}]
    geom = make_variants(RV)["clip_cell_shortcut"]
    by = {n["id"]: n for n in nodes}

    def edge(eid, u, v, ticks, rev=None):
        return {"id": eid, "u": u, "v": v, "travel_ticks": ticks, "reverse_edge": rev,
                "segments": geom(grid, by[u], by[v]), "source_way": 1, "direction_evidence": "explicit_two_way"}

    return {"revision": "tiny-test", "crs": "EPSG:5179", "grid": grid, "nodes": nodes,
            "edges": [edge("ab", "a", "b", 20, "ba"), edge("ba", "b", "a", 20, "ab"), edge("bc", "b", "c", 25)],
            "forbidden_turns": [["ab", "ba"]], "mid_edge_reversal": False,
            "provenance": {"source": "SYNTHETIC test graph", "license": "none"}}


def test_tiny_router_graph_converts():
    raw = tiny_router_graph()
    g = from_wfg_graph(raw)
    assert g.crs_epsg == 5179
    assert [(n.id, n.x, n.y, n.waitable) for n in g.nodes] == [(n["id"], n["x"], n["y"], n["waitable"]) for n in raw["nodes"]]
    assert [(e.id, e.u, e.v, e.travel_time_s, e.geometry) for e in g.edges] == [
        ("ab", "a", "b", 20.0, None), ("ba", "b", "a", 20.0, None), ("bc", "b", "c", 25.0, None)]
    assert g.forbidden_turns == [("ab", "ba")]
    assert g.provenance["graph_revision"] == "tiny-test" and "attribution" not in g.provenance
    assert router_grid_transform(raw) == (100.0, 0.0, 0.0, 0.0, -100.0, 300.0)
    assert [e.travel_time_s for e in from_wfg_graph(raw, dt_s=2.0).edges] == [40.0, 40.0, 50.0]


@pytest.mark.parametrize("tamper,code", [
    (lambda g: g["edges"][0].update(travel_ticks=0), "MALFORMED_INTEGER"),
    (lambda g: g["edges"][2]["segments"][0].update(cell=0), "ROAD_ALIGNMENT"),
    (lambda g: g["edges"][1].update(reverse_edge=None), "REVERSE_GEOMETRY"),
    (lambda g: g["forbidden_turns"].append(["ab", "ab"]), "TURN_RULE"),
    (lambda g: g.update(crs="EPSG:4326"), "UNSUPPORTED_CRS"),
])
def test_router_admission_is_reused(tamper, code):
    raw = tiny_router_graph()
    tamper(raw)
    with pytest.raises(RV.ValidationError) as exc:
        from_wfg_graph(raw)
    assert exc.value.code == code


def test_tiny_router_graph_runs_through_the_oracle():
    raw = tiny_router_graph()
    g = from_wfg_graph(raw)
    ig = quiet(3, 3)
    ig[0, 0, 2] = 0.0                                    # top-right cell (north-up row 0) burns: node c
    ss = make_set(ig)
    meta = ss.meta.model_copy(update={"crs_epsg": 5179, "transform": router_grid_transform(raw)})
    ss = hc.ScenarioSet(ss.ignite_s, ss.extinguish_s, ss.supported, meta)
    inst = Instance(name="SYNTHETIC tiny router graph", synthetic=True, graph=g, vehicles=[vehicle("V", "a")],
                    hazard=HazardRef(scenario_set="hazard", budgets=Budgets(peak_kw_m2=10.0, dose_kj_m2=100.0)))
    ok = check_itinerary(inst, ss, itinerary("V", drive(["ab"], 0.0)))
    hit = check_itinerary(inst, ss, itinerary("V", drive(["ab", "bc"], 0.0)))
    assert ok.state is State.CHECKED and hit.state is State.MODEL_NO_ROUTE and hit.cause == "FLAME_CONTACT"


# --------------------------------------------------------------------- real study graphs
@real
@pytest.mark.parametrize("region", REGIONS)
def test_real_router_graphs_convert_with_router_admission(region):
    path = GRAPHS / region / "graph.json"
    if not path.exists():
        pytest.skip(f"{region} graph absent")
    raw = json.loads(path.read_text())
    g = from_wfg_graph(raw, validate=True)
    assert g.crs_epsg == 5179 and len(g.nodes) == len(raw["nodes"]) and len(g.edges) == len(raw["edges"])
    assert sum(n.waitable for n in g.nodes) == sum(n["waitable"] for n in raw["nodes"])
    ticks = {e["id"]: e["travel_ticks"] for e in raw["edges"]}
    assert all(e.travel_time_s == float(ticks[e.id]) and e.geometry is None for e in g.edges)
    assert len(g.forbidden_turns) == len(raw["forbidden_turns"])
    assert g.provenance["graph_revision"] == raw["revision"]
    assert g.provenance["attribution"].startswith("Road data (c) OpenStreetMap contributors")


@real
@pytest.mark.parametrize("region", REGIONS)
def test_real_graph_grid_is_the_packet_grid(region):
    raw = json.loads((GRAPHS / region / "graph.json").read_text())
    tags = sorted(p.name for p in (PACKETS / region).iterdir()) if (PACKETS / region).is_dir() else []
    if not tags:
        pytest.skip(f"no packets for {region}")
    want = router_grid_transform(raw)
    for tag in tags:
        md = json.loads((PACKETS / region / tag / "NATIVE_METADATA.json").read_text())
        assert tuple(float(v) for v in md["affine_transform"]) == want
        assert md["graph_revision"] == raw["revision"]


ULJIN = PACKETS / "uljin_2022" / "20220304T060000Z"


@real
@pytest.mark.skipif(not ULJIN.is_dir(), reason="Uljin 06Z packet absent")
def test_real_graph_and_packet_through_the_oracle():
    """Present fire -> model_no_route; unknown cells (program rule 4) -> unresolved; quiet supported -> checked."""
    raw = json.loads((GRAPHS / "uljin_2022" / "graph.json").read_text())
    g = from_wfg_graph(raw, validate=False)
    ss = hc.from_wfg_packet(ULJIN)
    assert ss.meta.transform == router_grid_transform(raw) and ss.meta.source == "packet" and not ss.meta.synthetic
    nodes = {n.id: n for n in g.nodes}
    burning = ss.supported & (ss.extinguish_s > ss.ignite_s) & (ss.ignite_s <= ss.meta.horizon_s)
    picks = {}
    for e in g.edges:
        u, v = nodes[e.u], nodes[e.v]
        r, c, out = polyline_cells(ss.grid, np.array([[u.x, u.y], [v.x, v.y]]))
        if out or e.travel_time_s > 120:
            continue
        sup = ss.supported[:, r, c]
        now = ss.supported[:, r, c] & (ss.ignite_s[:, r, c] <= 0.0) & (ss.extinguish_s[:, r, c] > e.travel_time_s)
        if now.any() and "fire" not in picks:
            picks["fire"] = e
        elif not sup.any() and "unknown" not in picks:
            picks["unknown"] = e
        elif sup.all() and not burning[:, r, c].any() and "quiet" not in picks:
            picks["quiet"] = e
        if len(picks) == 3:
            break
    assert set(picks) == {"fire", "unknown", "quiet"}
    vehicles = [vehicle(f"V_{k}", e.u) for k, e in picks.items()]
    inst = Instance(name="SYNTHETIC vehicles on the Uljin study graph", synthetic=True, graph=g, vehicles=vehicles,
                    hazard=HazardRef(scenario_set=str(ULJIN), budgets=Budgets(peak_kw_m2=10.0, dose_kj_m2=100.0)))
    got = {k: check_itinerary(inst, ss, itinerary(f"V_{k}", drive([e.id], 0.0))) for k, e in picks.items()}
    assert got["fire"].state is State.MODEL_NO_ROUTE and got["fire"].cause == "FLAME_CONTACT"
    assert got["unknown"].state is State.UNRESOLVED and got["unknown"].cause == "UNSUPPORTED_HAZARD"
    assert got["quiet"].state is State.CHECKED and got["quiet"].min_slack_s is None   # no trip delivered
    assert got["quiet"].legs[0].slack_s > 0
