"""run --fragility (research/kcf-robust): optional columns and one page per town; off by default.

Checked here: the standard columns are byte-identical with and without the switch (the switch only appends columns),
the pages exist, and the values for the 의성·안동 12:00 KST example agree with the definition re-checked directly:
at the tolerated reach a safe route exists and at the next 0.125 km step none does; same for the timing error at
1-minute steps. research/kcf-robust/fragility_table.py compares every value with an independent backward pass."""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import numpy as np

from wfg_roadlayer import cli, fragility, pipeline

PRODUCT = Path(__file__).resolve().parents[1]
RASTER = PRODUCT / "examples/fire_arrival_20250325T0300Z_MEASURED_8h.tif"
ISSUE = "2025-03-25T12:00+09:00"


def _csv(p):
    return list(csv.reader(io.StringIO(p.read_text(encoding="utf-8-sig"))))


def test_fragility_columns_and_pages(cache, tmp_path):
    a, b = tmp_path / "plain", tmp_path / "frag"
    base = ["run", "--region", "uiseong_andong_2025", "--issue-time", ISSUE, "--raster", str(RASTER), "--as-of", ISSUE, "--workers", "2"]
    assert cli.main(base + ["--out", str(a)]) == 0
    assert cli.main(base + ["--out", str(b), "--fragility"]) == 0
    pa, pb = _csv(a / "en/villages_road_cut_uiseong_andong_2025.csv"), _csv(b / "en/villages_road_cut_uiseong_andong_2025.csv")
    assert len(pa) == len(pb)
    n = len(pa[0])
    assert all(x == y[:n] for x, y in zip(pa, pb)), "the switch must only append columns"
    assert pb[0][n:] == [c[2] for c in __import__("wfg_roadlayer.report", fromlist=["x"]).FRAGILITY_COLUMNS]
    assert not (a / "en/fragility").exists() and "fragility" not in json.loads((a / "run.json").read_text())
    pages = sorted((b / "en/fragility").glob("*.pdf"))
    assert len(pages) == len(sorted((b / "en/sheets").glob("*.pdf"))) > 0
    run = json.loads((b / "run.json").read_text())
    assert len(run["fragility"]["villages"]) == 84


def test_fragility_definition(cache):
    c = pipeline.compute(region_name="uiseong_andong_2025", issue_time=ISSUE, raster=str(RASTER), as_of=ISSUE,
                         out="/nonexistent-unused", workers=2, log=lambda *x: None)
    fr = fragility.compute(c, str(RASTER), PRODUCT, log=lambda *x: None)
    road = c["region"].road
    ed = fragility._Edges(road)
    levels, radii = fragility._levels_reach(str(RASTER), road, c["fire"].issue_utc, c["fire"].horizon_s / 60.0, None)[0]
    base = fragility.close_array(c["close_s"], road.W * road.H)
    checked = 0
    for row in c["rows"]:
        if row["refusal"]:
            continue
        f = fr[row["origin"]["id"]]
        sns = [s["node"] for s in row["candidates"]]

        def ok(arr):
            return fragility.route_now(ed, ed.lo(arr, c["H"]), arr, row["origin"]["node"], sns, c["H"], c["dwell"], road.node_cell) is not None

        if f["reach_km"] is None:
            assert not ok(levels[0])
        else:
            k = radii.index(f["reach_km"])
            assert ok(levels[k]) and (k == len(levels) - 1 or not ok(levels[k + 1]))

        def sh(m):
            s = base.copy(); s[s < fragility.NONE] = np.maximum(s[s < fragility.NONE] - m, 0)
            return s

        if f["timing_s"] is None:
            assert not ok(base)
        else:
            assert ok(sh(f["timing_s"])) and (f["timing_censored"] or not ok(sh(f["timing_s"] + 60)))
        # leaving now along the product's own deadline: a safe departure now exists iff the product has a window at 0
        assert (f["timing_s"] is not None) == (row["L"] is not None and row["windows"] and row["windows"][0][0] == 0)
        checked += 1
    assert checked == 84
