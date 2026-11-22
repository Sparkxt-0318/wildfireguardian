"""People and buildings of a place (research/kcf-buildings): statuses, the 읍·면·동 totals, buildings at risk."""
from __future__ import annotations

import csv
import types
from pathlib import Path

import pytest

from wfg_roadlayer import cards, demand

PRODUCT = Path(__file__).resolve().parents[1]
REPO = PRODUCT.parents[1]
REGIONS = ("uiseong_andong_2025", "yeongdeok_2025")


@pytest.mark.parametrize("rid", REGIONS)
def test_every_figure_has_a_status_and_matches_the_eupmyeondong_total(rid):
    emd = {(r["sigungu"], r["eupmyeondong"]): r for r in csv.DictReader(open(REPO / "research/kcf-buildings/data/eupmyeondong_202502.csv", encoding="utf-8"))}
    rows = list(cards.load_households(rid).values())
    assert len(rows) in (87 - 1, 92 - 1) or len(rows) > 80
    n_est = 0
    for h in rows:
        d = demand.demo(h)
        if h["kind"] != "village":
            assert d["households"] == 0.0 and d["households_status"].startswith("ASSUMED")
            continue
        assert d["households_status"].startswith(("ESTIMATED", "ASSUMED")) and d["residents_status"] and d["vehicles_status"].startswith(("ESTIMATED", "ASSUMED"))
        e = emd.get((h["sigungu"], h["eupmyeon"]))
        if d["households_status"].startswith("ESTIMATED"):
            n_est += 1
            n = int(e["n_legal_ri"])
            assert abs(d["households"] - int(e["households"]) / n) < 0.01
            assert abs(d["residents"] - int(e["population"]) / n) < 0.01
            assert abs(d["residents65"] - int(e["age65plus"]) / n) < 0.01
            assert d["residents65"] <= d["residents"] and d["residents"] >= d["households"]
    assert n_est >= 70


def _road():
    # 4 x 4 cells of 375 m, origin (0, 0); node 0 sits in cell 5
    return types.SimpleNamespace(x0=0.0, y0=0.0, res=375.0, W=4, H=4, node_cell=[5])


def test_buildings_at_risk_counts_mapped_buildings_in_reached_cells(monkeypatch):
    blds = [(100.0, 100.0, "house"), (400.0, 100.0, "house"), (800.0, 100.0, "unknown"), (1000.0, 800.0, "house"), (2000.0, 2000.0, "house"), (-50.0, 10.0, "house")]
    monkeypatch.setattr(demand, "_buildings", lambda rid: {"p": blds})
    close_s = {0: 100, 1: 28800, 2: 28801, 11: 5}   # cell 2 is reached only after the horizon
    r = demand.at_risk("x", _road(), close_s, 28800, "p", 0, 100.0)
    assert r["mapped"] == 6 and r["at_risk"] == 2          # cells 0 and 1 (cell 2 is after H, cell 11 holds no building)
    assert abs(r["households_at_risk"] - 100.0 * 2 / 6) < 1e-9


def test_few_mapped_buildings_fall_back_to_the_villages_own_cell(monkeypatch):
    monkeypatch.setattr(demand, "_buildings", lambda rid: {"p": [(100.0, 100.0, "house")]})
    reached = demand.at_risk("x", _road(), {5: 10}, 28800, "p", 0, 80.0)
    not_reached = demand.at_risk("x", _road(), {0: 10}, 28800, "p", 0, 80.0)
    assert reached["households_at_risk"] == 80.0 and not_reached["households_at_risk"] == 0.0
    assert "fewer than 5" in reached["households_at_risk_basis"]
