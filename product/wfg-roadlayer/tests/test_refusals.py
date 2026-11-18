"""Failure tests: a missing or stale input gives exit status 2, a REFUSED.txt/.json naming the input, and no number."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from wfg_roadlayer import cli, geotiff, regiondata

PRODUCT = Path(__file__).resolve().parents[1]
REPO = PRODUCT.parents[1]
RASTER = PRODUCT / "examples/fire_arrival_20250325T0300Z_MEASURED_8h.tif"
ISSUE = "2025-03-25T12:00+09:00"
REGION = "uiseong_andong_2025"


def run(tmp_path, *args, name="out"):
    out = tmp_path / name
    code = cli.main(["run", "--out", str(out), "--workers", "2"] + [str(a) for a in args])
    return code, out


def refused(out: Path):
    j = json.loads((out / "REFUSED.json").read_text(encoding="utf-8"))
    assert j["refused"] is True
    assert (out / "REFUSED.txt").read_text(encoding="utf-8").startswith("계산 거부")
    # no number anywhere: no CSV, no sheet, no certificate
    assert not list(out.rglob("*.csv")) and not list(out.rglob("*.pdf")) and not list(out.rglob("certificates"))
    return [r["code"] for r in j["reasons"]]


def variant(tmp_path, name, *, data=None, metadata=None, epsg=5179, nodata=float("nan"), drop_md=()):
    r = geotiff.read(RASTER)
    md = dict(r.metadata)
    md.update(metadata or {})
    for k in drop_md:
        md.pop(k, None)
    p = tmp_path / name
    geotiff.write(p, r.data if data is None else data, r.affine, epsg, nodata=nodata, metadata=md)
    return p


def test_missing_raster_file(cache, tmp_path):
    code, out = run(tmp_path, "--region", REGION, "--issue-time", ISSUE, "--raster", tmp_path / "nope.tif", "--as-of", ISSUE)
    assert code == 2 and refused(out) == ["FIRE_INPUT_MISSING"]


def test_no_fire_input(cache, tmp_path):
    code, out = run(tmp_path, "--region", REGION, "--issue-time", ISSUE, "--as-of", ISSUE)
    assert code == 2 and refused(out) == ["FIRE_INPUT_MISSING"]


def test_missing_issue_time(cache, tmp_path):
    code, out = run(tmp_path, "--region", REGION, "--raster", RASTER, "--as-of", ISSUE)
    assert code == 2 and refused(out) == ["ISSUE_TIME_MISSING"]
    assert "2025-03-25" in (out / "REFUSED.txt").read_text(encoding="utf-8")  # says what the raster declares


def test_issue_time_without_zone(cache, tmp_path):
    code, out = run(tmp_path, "--region", REGION, "--raster", RASTER, "--issue-time", "2025-03-25T15:00", "--as-of", ISSUE)
    assert code == 2 and refused(out) == ["ISSUE_TIME_INVALID"]


def test_issue_time_conflicts_with_raster(cache, tmp_path):
    code, out = run(tmp_path, "--region", REGION, "--raster", RASTER, "--issue-time", "2025-03-25T16:00+09:00",
                    "--as-of", "2025-03-25T16:00+09:00")
    assert code == 2 and refused(out) == ["ISSUE_TIME_CONFLICT"]


def test_missing_region(cache, tmp_path):
    code, out = run(tmp_path, "--raster", RASTER, "--issue-time", ISSUE, "--as-of", ISSUE)
    assert code == 2 and refused(out) == ["REGION_MISSING"]


def test_unknown_region(cache, tmp_path):
    code, out = run(tmp_path, "--region", "울릉", "--raster", RASTER, "--issue-time", ISSUE, "--as-of", ISSUE)
    assert code == 2 and refused(out) == ["REGION_UNKNOWN"]


def test_missing_horizon(cache, tmp_path):
    p = variant(tmp_path, "nohz.tif", drop_md=("WFG_HORIZON_MIN",))
    code, out = run(tmp_path, "--region", REGION, "--raster", p, "--issue-time", ISSUE, "--as-of", ISSUE)
    assert code == 2 and refused(out) == ["HORIZON_MISSING"]
    code, out = run(tmp_path, "--region", REGION, "--raster", p, "--issue-time", ISSUE, "--as-of", ISSUE, "--horizon-min", 480,
                    name="with_horizon")
    assert code == 0 and (out / "run.json").is_file()


def test_missing_crs(cache, tmp_path):
    p = variant(tmp_path, "nocrs.tif", epsg=32767)  # user-defined: no EPSG code
    code, out = run(tmp_path, "--region", REGION, "--raster", p, "--issue-time", ISSUE, "--as-of", ISSUE)
    assert code == 2 and refused(out) == ["CRS_MISSING"]


def test_unreadable_raster(cache, tmp_path):
    p = tmp_path / "bad.tif"
    p.write_bytes(b"not a tiff at all")
    code, out = run(tmp_path, "--region", REGION, "--raster", p, "--issue-time", ISSUE, "--as-of", ISSUE)
    assert code == 2 and refused(out) == ["FIRE_INPUT_UNREADABLE"]


def test_stale_fire_input(cache, tmp_path):
    """Default as-of is the clock: a 2025 raster is stale today; an as-of 3 h after the issue is stale too."""
    code, out = run(tmp_path, "--region", REGION, "--raster", RASTER, "--issue-time", ISSUE)
    assert code == 2 and refused(out) == ["FIRE_INPUT_STALE"]
    code, out = run(tmp_path, "--region", REGION, "--raster", RASTER, "--issue-time", ISSUE, "--as-of", "2025-03-25T15:00+09:00",
                    name="later")
    assert code == 2 and refused(out) == ["FIRE_INPUT_STALE"]
    txt = (out / "REFUSED.txt").read_text(encoding="utf-8")
    assert "180" in txt and "90" in txt  # age and limit in minutes


def test_issue_time_in_future(cache, tmp_path):
    code, out = run(tmp_path, "--region", REGION, "--raster", RASTER, "--issue-time", ISSUE, "--as-of", "2025-03-25T11:00+09:00")
    assert code == 2 and refused(out) == ["ISSUE_TIME_IN_FUTURE"]


def test_stale_roads_and_places(cache, tmp_path):
    late = "2027-01-10T15:00+09:00"  # roads (2025-03-21) are 660 days older, places (2026-10-17) 85 days
    p = variant(tmp_path, "late.tif", metadata={"WFG_ISSUE_TIME": "2027-01-10T06:00:00Z"})
    code, out = run(tmp_path, "--region", REGION, "--raster", p, "--issue-time", late, "--as-of", late)
    assert code == 2 and refused(out) == ["ROADS_STALE"]
    later = "2028-01-10T15:00+09:00"
    p = variant(tmp_path, "later.tif", metadata={"WFG_ISSUE_TIME": "2028-01-10T06:00:00Z"})
    code, out = run(tmp_path, "--region", REGION, "--raster", p, "--issue-time", later, "--as-of", later, name="later")
    assert code == 2 and sorted(refused(out)) == ["PLACES_STALE", "ROADS_STALE"]


def test_uncovered_road_cells_refused_then_assumed(cache, tmp_path):
    r = geotiff.read(RASTER)
    d = r.data.copy()
    d[:, :20] = np.nan  # western strip of 의성·안동 has no data
    p = variant(tmp_path, "holes.tif", data=d)
    code, out = run(tmp_path, "--region", REGION, "--raster", p, "--issue-time", ISSUE, "--as-of", ISSUE)
    assert code == 2 and refused(out) == ["FIRE_INPUT_UNCOVERED"]
    code, out = run(tmp_path, "--region", REGION, "--raster", p, "--issue-time", ISSUE, "--as-of", ISSUE,
                    "--assume-uncovered-not-reached", name="assumed")
    assert code == 0
    m = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert m["fire_input"]["assumed_uncovered_not_reached"] is True and m["fire_input"]["road_cells_uncovered"] > 0
    # villages whose own entry cell has no data still get no number
    rows = (out / "en/villages_road_cut_uiseong_andong_2025.csv").read_text(encoding="utf-8-sig")
    assert "no fire-arrival data at the entry cell" in rows


def test_cache_not_set_up(tmp_path):
    code, out = run(tmp_path, "--region", REGION, "--raster", RASTER, "--issue-time", ISSUE, "--as-of", ISSUE,
                    "--cache", tmp_path / "empty-cache")
    assert code == 2 and refused(out) == ["DATA_NOT_SET_UP"]


def test_corrupt_cache_file(cache, tmp_path):
    c2 = tmp_path / "cache2"
    shutil.copytree(cache, c2)
    g = c2 / "graphs" / REGION / "graph.json"
    g.write_bytes(g.read_bytes()[:-10] + b"          ")
    code, out = run(tmp_path, "--region", REGION, "--raster", RASTER, "--issue-time", ISSUE, "--as-of", ISSUE, "--cache", c2)
    assert code == 2 and refused(out) == ["DATA_CORRUPT"]


def test_invalid_settings(cache, tmp_path):
    s = tmp_path / "s.toml"
    s.write_text("[stage]\nstandby_hours = 4\nimmediate_hours = 5\n")
    code, out = run(tmp_path, "--region", REGION, "--raster", RASTER, "--issue-time", ISSUE, "--as-of", ISSUE, "--settings", s)
    assert code == 2 and refused(out) == ["SETTINGS_INVALID"]


def test_output_folder_not_overwritten(cache, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "old.csv").write_text("old numbers")
    code, _ = run(tmp_path, "--region", REGION, "--raster", RASTER, "--issue-time", ISSUE, "--as-of", ISSUE)
    assert code == 2 and (out / "old.csv").read_text() == "old numbers" and not (out / "REFUSED.txt").exists()


PACKETS = REPO / "data/routing/latest_inputs_try02/packets"


@pytest.mark.skipif(not PACKETS.is_dir(), reason="repository packets not fetched (tools/fetch_routing_inputs.py)")
def test_packet_uncovered_and_wrong_region(cache, tmp_path):
    pk = PACKETS / "uiseong_andong_2025/20250325T170000Z"
    t = "2025-03-26T02:00+09:00"
    code, out = run(tmp_path, "--region", REGION, "--packet", pk, "--issue-time", t, "--as-of", t)
    assert code == 2 and refused(out) == ["FIRE_INPUT_UNCOVERED"]
    code, out = run(tmp_path, "--region", "yeongdeok_2025", "--packet", pk, "--issue-time", t, "--as-of", t, name="wrong")
    assert code == 2 and refused(out) == ["GRID_MISMATCH"]


def test_per_village_refusal_has_no_number(example_out):
    import csv
    rows = list(csv.DictReader(open(example_out["path"] / "uiseong_andong_20250325_1200KST/en/villages_road_cut_uiseong_andong_2025.csv",
                                    encoding="utf-8-sig")))
    ref = [r for r in rows if r["refusal reason"]]
    assert ref
    numeric = ("leave by (KST)", "last road out cut (KST)", "fire arrival (KST)", "minutes from road cut to fire arrival", "stage now",
               "leave by (s after issue)", "road cut (s after issue)", "fire arrival (s after issue)", "certificate")
    for r in ref:
        assert all(r[k] == "" for k in numeric), r
