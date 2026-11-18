"""Village cards: exits and dangerous road on graphs with known answers, settings refusals, departure-order arithmetic,
the replay overlap counts, and the worked example (174 cards, audit CSV invariants)."""
from __future__ import annotations

import csv
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from wfg_roadlayer import cards, exits, overlap
from wfg_roadlayer.errors import Refusal
from wfg_roadlayer.regiondata import RoadModel

PRODUCT = Path(__file__).resolve().parents[1]


def graph(edges, nodes, W=10, H=10, res=100):
    """edges: (name, u, v, way, cells); two-way unless name ends with '!'. Node coords in metres."""
    raw = {"grid": {"x0": 0, "y0": 0, "resolution": res, "width": W, "height": H},
           "nodes": [{"id": n, "x": x, "y": y, "waitable": False} for n, (x, y) in nodes.items()], "edges": []}
    for name, u, v, way, cells in edges:
        one = name.endswith("!")
        segs = [{"cell": c, "end": (k + 1) / len(cells)} for k, c in enumerate(cells)]
        raw["edges"].append({"id": name + ":f", "u": u, "v": v, "travel_ticks": 10, "segments": segs, "source_way": way,
                             "reverse_edge": None if one else name + ":r"})
        if not one:
            raw["edges"].append({"id": name + ":r", "u": v, "v": u, "travel_ticks": 10, "segments": segs[::-1], "source_way": way,
                                 "reverse_edge": name + ":f"})
    return RoadModel(raw)


NODES = {"V": (50, 50), "A": (150, 50), "B": (50, 150), "J": (550, 550), "S": (950, 950), "T": (950, 50)}


def run(road, shelters, start="V", k=8):
    fg = exits.FlowGraph(road, {road.nidx[s] for s in shelters})
    return exits.analyse(fg, road.nidx[start], k)


def test_two_separate_roads_two_exits_no_road_cuts_both():
    road = graph([("a", "V", "A", 1, [1]), ("a2", "A", "T", 2, [9]), ("b", "V", "B", 3, [10]), ("b2", "B", "S", 4, [99])],
                 NODES)
    r = run(road, ["T", "S"])
    assert r["exits"] == 2 and len(r["paths"]) == 2
    assert r["danger"]["cut"] == 1


def test_two_roads_through_one_junction_cell_cut_together():
    # both routes pass the junction J in cell 55: losing that one cell cuts both exits
    road = graph([("a", "V", "A", 1, [1]), ("a2", "A", "J", 2, [55]), ("b", "V", "B", 3, [10]), ("b2", "B", "J", 4, [55]),
                  ("j1", "J", "S", 5, [99]), ("j2", "J", "T", 6, [59])], NODES)
    r = run(road, ["T", "S"])
    assert r["exits"] == 2
    assert r["danger"]["cut"] == 2 and r["danger"]["cell"] == 55


def test_dead_end_single_exit_and_entry_cell_ignored():
    road = graph([("a", "V", "A", 1, [0, 1]), ("a2", "A", "S", 2, [99])], NODES)
    r = run(road, ["S"])
    assert r["exits"] == 1
    assert r["danger"]["cell"] != road.node_cell[road.nidx["V"]]
    assert r["danger"]["cut"] == 1


def test_one_way_road_counts_in_its_direction_only():
    road = graph([("a!", "A", "V", 1, [1]), ("b", "V", "B", 2, [10]), ("b2", "B", "S", 3, [99]), ("a2", "A", "S", 4, [9])], NODES)
    r = run(road, ["S"])
    assert r["exits"] == 1  # the one-way road only leads into the village


def test_paths_are_disjoint_and_end_at_shelters():
    road = graph([("a", "V", "A", 1, [1]), ("a2", "A", "T", 2, [9]), ("b", "V", "B", 3, [10]), ("b2", "B", "S", 4, [99]),
                  ("x", "A", "B", 5, [11])], NODES)
    r = run(road, ["T", "S"])
    pieces = [frozenset((road.tail[j], road.head[j])) for p in r["paths"] for j in p]
    assert len(pieces) == len(set(pieces))
    for p in r["paths"]:
        assert road.tail[p[0]] == road.nidx["V"] and road.node_ids[road.head[p[-1]]] in ("T", "S")
        assert all(road.head[a] == road.tail[b] for a, b in zip(p, p[1:]))


def test_card_settings_refusals(tmp_path):
    s = cards.load_settings()
    assert s["trigger"]["margin_min"] == 30 and s["traffic"]["no_car_share"] == 0.36
    for body in ("[trigger]\nmargin_min = -5\n", "[traffic]\nno_car_share = 1.5\n", "[nope]\nx = 1\n", "[pickup]\nvans = 0\n"):
        p = tmp_path / "c.toml"
        p.write_text(body)
        with pytest.raises(Refusal):
            cards.load_settings(p)


def test_departure_order_latest_start():
    road = graph([("s", "A", "J", 7, [55]), ("a", "V", "A", 1, [1])], NODES)
    j = road.edge_ids.index("s:f")
    ways = {7: {"class": "tertiary", "name": "", "ref": ""}}
    tcfg = cards.load_settings()["traffic"]

    def rec(pid, leave_by, veh, clear):
        return {"refusal": None, "origin": {"id": pid, "name": pid}, "route_kind": "last", "route_edges": [j], "vehicles": veh,
                "clearance_s": clear, "row": {"leave_by": leave_by}}
    recs = [rec("x", 3600, 170, 600), rec("y", 3000, 170, 600)]
    assert cards.departure_order(recs, road, ways, tcfg) == 1
    # y (earlier deadline) goes first; x leaves at 3600 - 600; y must clear the shared road (170 veh / 1700 per h = 360 s)
    assert recs[0]["dep_start"] == 3000 and recs[0]["dep_pos"] == 2
    assert recs[1]["dep_start"] == min(3000 - 600, 3000 - 360) and recs[1]["dep_pos"] == 1


def test_overlap_counts():
    t = datetime(2025, 3, 25, 12)
    cuts = {("r", "a"): t, ("r", "b"): t.replace(hour=13), ("r", "c"): t.replace(hour=20), ("r", "d"): overlap.NEVER}
    flags = {("r", "a"): {"single_exit": True, "dangerous_road": False}, ("r", "b"): {"single_exit": False, "dangerous_road": False},
             ("r", "c"): {"single_exit": True, "dangerous_road": True}, ("r", "d"): {"single_exit": False, "dangerous_road": False}}
    tab = overlap.table(flags, cuts)
    row = next(r for r in tab["rows"] if r["flag"] == "single_exit" and r["region"] == "r")
    assert (row["places"], row["flagged"], row["earliest"], row["both"], row["neither"]) == (4, 2, 1, 1, 2)


def test_earliest_cut_from_replay():
    cuts = overlap.earliest_cut()
    assert len(cuts) == 174
    assert cuts[("uiseong_andong_2025", "osm:node/415158323")] >= datetime(2025, 3, 25, 12)


# ------------------------------------------------------------------------------------------------ worked example
@pytest.fixture(scope="session")
def cards_out(cache, tmp_path_factory):
    from wfg_roadlayer import cli
    out = tmp_path_factory.mktemp("cards") / "cx"
    assert cli.main(["cards-example", "--out", str(out), "--cache", str(cache)]) == 0
    return out


def _pages(p: Path) -> int:
    b = p.read_bytes()
    return b.count(b"/Type /Page") - b.count(b"/Type /Pages")


def test_174_cards_ko_and_en(cards_out):
    n = 0
    for case in ("uiseong_andong_20250325_1200KST", "yeongdeok_20250325_1800KST"):
        man = json.loads((cards_out / case / "cards.json").read_text(encoding="utf-8"))
        rid = man["region"]
        ko, en = _pages(cards_out / case / ("cards_ko_%s.pdf" % rid)), _pages(cards_out / case / ("cards_en_%s.pdf" % rid))
        assert ko == en == man["counts"]["cards"]
        n += ko
        if shutil.which("pdftotext"):
            for lang, want in (("ko", "모델 출력 · 참고용 · 명령 아님"), ("en", "Model output · advisory · not an order")):
                txt = subprocess.run(["pdftotext", str(cards_out / case / ("cards_%s_%s.pdf" % (lang, rid))), "-"],
                                     capture_output=True, text=True).stdout
                assert txt.count(want) >= 2 * ko
    assert n == 174


def _audit(cards_out):
    rows = []
    for p in sorted(cards_out.glob("*/audit_*.csv")):
        rows += list(csv.DictReader(open(p, encoding="utf-8-sig")))
    return rows


def test_audit_invariants(cards_out):
    rows = _audit(cards_out)
    ok = [r for r in rows if not r["refusal"]]
    assert len(ok) == 174 and len(rows) == 177
    for r in ok:
        assert int(r["exits"].rstrip("+")) >= 1
        assert r["households_status"] == "ASSUMED" and r["vehicles_status"].startswith("ASSUMED")
        assert r["exit_conifer_share"].startswith("NOT AVAILABLE")
        assert r["capacity_status"] in ("ASSUMED", "CITED (two-lane assumed)", "ASSUMED lanes x CITED per-lane")
        if r["single_exit"] == "yes":
            assert r["exits"] == "1"
        if r["dangerous_road_cuts_all"] == "yes":
            assert r["danger_exits_cut"] == r["exits"] != "1"
        lb, lbc, lbm, trig = r["leave_by_kst"], r["leave_by_with_clearance_kst"], r["leave_by_with_margin_kst"], r["trigger_kst"]
        if lb[:2] == "20":
            assert lbc and lbc <= lb
            if lbm[:2] == "20":
                assert lbm <= lb
        if trig:
            assert lbm[:2] == "20" and trig <= lbm
        if r["departure_group"]:
            assert int(r["departure_position"]) <= int(r["departure_group_size"])


def test_overlap_report_written(cards_out):
    tab = json.loads((cards_out / "overlap.json").read_text(encoding="utf-8"))
    tot = {r["flag"]: r for r in tab["rows"] if r["region"] == "all"}
    assert tot["either"]["places"] == 174
    for r in tab["rows"]:
        assert r["both"] + r["flagged_only"] + r["earliest_only"] + r["neither"] == r["places"]
    assert "Overlap" in (cards_out / "OVERLAP.md").read_text(encoding="utf-8")


def test_sheets_unchanged_by_cards(cards_out, example_out):
    """The cards reuse the field without changing the sheets: the golden test still holds (run in test_golden.py); here
    the cards' leave-by equals the sheet CSV's for every place."""
    for case, rid in (("uiseong_andong_20250325_1200KST", "uiseong_andong_2025"), ("yeongdeok_20250325_1800KST", "yeongdeok_2025")):
        sheet = {r["place id"]: r for r in csv.DictReader(open(example_out["path"] / case / ("en/villages_road_cut_%s.csv" % rid),
                                                                 encoding="utf-8-sig"))}
        for r in csv.DictReader(open(cards_out / case / ("audit_%s.csv" % rid), encoding="utf-8-sig")):
            if r["leave_by_kst"][:2] == "20":
                assert sheet[r["place_id"]]["leave by"] == r["leave_by_kst"]
