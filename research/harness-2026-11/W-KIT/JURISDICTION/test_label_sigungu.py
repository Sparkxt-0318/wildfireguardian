"""Tests of label_sigungu.py against SYNTHETIC boundary files (the real file is not in the repo).

Run: python3.12 -m pytest research/harness-2026-11/W-KIT/JURISDICTION -q   (requirements.txt)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import shapefile
from pyproj import CRS, Transformer
from pyproj.enums import WktVersion

sys.path.insert(0, str(Path(__file__).parent))
import label_sigungu as L  # noqa: E402

UTMK = CRS.from_epsg(5179)
TO_WGS = Transformer.from_crs(UTMK, "EPSG:4326", always_xy=True)
X0, Y0 = 1_100_000.0, 1_800_000.0  # a synthetic block in UTM-K (roughly central Korea)


def square(x: float, y: float, w: float) -> list[list[tuple[float, float]]]:
    return [[(x, y), (x, y + w), (x + w, y + w), (x + w, y), (x, y)]]  # clockwise ring (shapefile outer ring)


def write_shp(dirpath: Path, polys: list[tuple[str, str, list]], encoding: str = "cp949", prj: str | None = None) -> Path:
    base = dirpath / "sgg"
    w = shapefile.Writer(str(base), shapeType=shapefile.POLYGON, encoding=encoding)
    w.field("SIGUNGU_CD", "C", 10)
    w.field("SIGUNGU_NM", "C", 40)
    for code, name, rings in polys:
        w.poly(rings)
        w.record(code, name)
    w.close()
    (dirpath / "sgg.prj").write_text(prj if prj is not None else UTMK.to_wkt(WktVersion.WKT1_ESRI), encoding="utf-8")
    (dirpath / "sgg.cpg").write_text(encoding.upper(), encoding="ascii")
    return base.with_suffix(".shp")


def wgs(x: float, y: float) -> dict:
    lon, lat = TO_WGS.transform(x, y)
    return {"lon": lon, "lat": lat}


def place(pid: str, pt: tuple[float, float], entry: tuple[float, float] | None, region: str = "r1") -> dict:
    return {"id": pid, "region": region, "name": None, "point": wgs(*pt), "entry": ({"node": "n", **wgs(*entry)} if entry else None)}


# two adjacent 10 km squares: 합성군 (west) and 다른군 (east); the shared edge is x = X0 + 10 000
TWO = [("47901", "합성군", square(X0, Y0, 10_000)), ("47902", "다른군", square(X0 + 10_000, Y0, 10_000))]
EDGE = X0 + 10_000


@pytest.fixture()
def shp(tmp_path: Path) -> Path:
    return write_shp(tmp_path, TWO)


def places_file(tmp_path: Path, places: list[dict]) -> Path:
    p = tmp_path / "places.json"
    p.write_text(json.dumps({"places": places}, ensure_ascii=False), encoding="utf-8")
    return p


def test_rule_cases_and_reasons_in_order(tmp_path: Path, shp: Path) -> None:
    ps = [
        place("deep", (X0 + 5_000, Y0 + 5_000), (X0 + 5_010, Y0 + 5_000)),
        place("near", (EDGE - 10, Y0 + 5_000), (EDGE - 20, Y0 + 5_000)),  # 10 m inside 합성군
        place("sea", (X0 - 5_000, Y0 + 5_000), (X0 - 5_000, Y0 + 5_000)),
        place("entry_east", (EDGE - 500, Y0 + 5_000), (EDGE + 30, Y0 + 5_000)),  # point in 합성군, entry in 다른군
        place("no_entry", (X0 + 5_000, Y0 + 6_000), None),
    ]
    res = L.run(shp, places_file(tmp_path, ps), 50, fixture=True)
    lab = res["labels"]
    assert lab["deep"]["status"] == "established" and lab["deep"]["ko"] == "합성군"
    assert lab["near"] == {**lab["near"], "status": "not_established", "reason": "near_boundary", "ko": None}
    assert 9.5 <= lab["near"]["boundary_m"] <= 10.5
    assert lab["sea"]["reason"] == "outside_all" and lab["sea"]["ko"] is None
    assert lab["entry_east"]["reason"] == "entry_differs" and lab["entry_east"]["entry_in"] == ["다른군"]
    assert lab["entry_east"]["ko"] is None  # never assigned to the entry node's county
    assert lab["no_entry"]["reason"] == "entry_differs"
    for v in lab.values():
        assert v["source"] == L.SOURCE_LINE
        assert (v["status"] == "established") == (v["reason"] is None)
        assert v["reason"] in (None, *L.REASONS)
    assert res["fixture"] is True


def test_margin_sensitivity_counts(tmp_path: Path, shp: Path) -> None:
    ps = [place("near", (EDGE - 10, Y0 + 5_000), (EDGE - 20, Y0 + 5_000)), place("mid", (EDGE - 40, Y0 + 5_000), (EDGE - 45, Y0 + 5_000)), place("far", (EDGE - 80, Y0 + 5_000), (EDGE - 90, Y0 + 5_000))]
    res = L.run(shp, places_file(tmp_path, ps), 50, fixture=True)
    c = res["counts_by_margin"]
    assert set(c) == {"0m", "25m", "50m", "100m"}
    assert c["0m"]["r1"] == {"합성군": 3}
    assert c["25m"]["r1"] == {"near_boundary": 1, "합성군": 2}
    assert c["50m"]["r1"] == {"near_boundary": 2, "합성군": 1}
    assert c["100m"]["r1"] == {"near_boundary": 3}


def test_margin_zero_would_establish_a_point_10m_inside(tmp_path: Path, shp: Path) -> None:
    """Mutation (c) of the pass rule: with the margin at 0 m, a point 10 m inside a boundary is established."""
    p = places_file(tmp_path, [place("near", (EDGE - 10, Y0 + 5_000), (EDGE - 20, Y0 + 5_000))])
    assert L.run(shp, p, 0, fixture=True)["labels"]["near"]["status"] == "established"
    assert L.run(shp, p, 50, fixture=True)["labels"]["near"]["status"] == "not_established"


def test_overlap_is_multiple(tmp_path: Path) -> None:
    shp = write_shp(tmp_path, [*TWO, ("47903", "겹친군", square(X0 + 4_000, Y0 + 4_000, 2_000))])
    lab = L.run(shp, places_file(tmp_path, [place("o", (X0 + 5_000, Y0 + 5_000), (X0 + 5_000, Y0 + 5_001))]), 50, fixture=True)["labels"]["o"]
    assert lab["reason"] == "multiple" and sorted(lab["candidates"]) == ["겹친군", "합성군"]


def test_korean_names_read_from_cp949_and_utf8(tmp_path: Path) -> None:
    for enc in ("cp949", "utf-8"):
        d = tmp_path / enc
        d.mkdir()
        shp = write_shp(d, TWO, encoding=enc)
        counties, _, files = L.read_counties(shp)
        assert [c.name for c in counties] == ["합성군", "다른군"]
        assert set(files) >= {"sgg.shp", "sgg.dbf", "sgg.shx", "sgg.prj"} and all(len(h) == 64 for h in files.values())


def test_geographic_crs_is_refused(tmp_path: Path) -> None:
    shp = write_shp(tmp_path, TWO, prj=CRS.from_epsg(4326).to_wkt(WktVersion.WKT1_ESRI))
    with pytest.raises(L.SanityError, match="projected metric"):
        L.read_counties(shp)


def real_like(gunwi_code: str) -> list:
    names = [("47730", "의성군"), ("47170", "안동시"), ("47750", "청송군"), ("47760", "영양군"), ("47770", "영덕군"), (gunwi_code, "군위군")]
    return [(code, n, square(X0 + i * 10_000, Y0, 10_000)) for i, (code, n) in enumerate(names)]


def test_sanity_required_counties_and_gunwi(tmp_path: Path) -> None:
    ok = tmp_path / "ok"; ok.mkdir()
    counties, _, _ = L.read_counties(write_shp(ok, real_like("27720")))  # 군위군 under 대구 (27)
    L.sanity(counties)
    bad = tmp_path / "bad"; bad.mkdir()
    counties, _, _ = L.read_counties(write_shp(bad, real_like("47720")))  # 군위군 under 경북: wrong vintage
    with pytest.raises(L.SanityError, match="군위군"):
        L.sanity(counties)
    missing = tmp_path / "missing"; missing.mkdir()
    counties, _, _ = L.read_counties(write_shp(missing, TWO))
    with pytest.raises(L.SanityError, match="의성군"):
        L.sanity(counties)


def test_cli_stops_on_sanity_without_fixture_and_marks_fixture_output(tmp_path: Path, shp: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p = places_file(tmp_path, [place("deep", (X0 + 5_000, Y0 + 5_000), (X0 + 5_010, Y0 + 5_000))])
    out = tmp_path / "labels.json"
    assert L.main(["--shp", str(shp), "--places", str(p), "--out", str(out)]) == 2
    assert not out.exists()
    assert L.main(["--shp", str(shp), "--places", str(p), "--out", str(out), "--fixture"]) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["fixture"] is True and doc["margin_m"] == 50 and doc["labels"]["deep"]["ko"] == "합성군"
    assert "FIXTURE" in capsys.readouterr().out


def test_real_places_input_is_complete() -> None:
    doc = json.loads((Path(__file__).with_name("places_input.json")).read_text(encoding="utf-8"))
    ps = doc["places"]
    assert doc["crs"] == "EPSG:4326" and len(ps) == 177
    assert {p["region"] for p in ps} == {"uiseong_andong_2025", "yeongdeok_2025"}
    assert sum(p["region"] == "yeongdeok_2025" for p in ps) == 91
    assert len({p["id"] for p in ps}) == 177
    for p in ps:
        assert 128.0 < p["point"]["lon"] < 130.0 and 35.5 < p["point"]["lat"] < 37.5
        assert p["entry"] and p["entry"]["lon"] is not None
