"""Tests for planner/tools/extract_places.py outputs (ARCHITECTURE.md §4.2).

Output-only checks run whenever the generated place files exist; checks against the recorded mission
requests and the road graph skip cleanly when the release extracts (planner/.assets/) are missing.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
PLANNER = REPO / "planner"
PUBLIC = PLANNER / "public" / "data" / "regions"
OSM = PLANNER / "data" / "osm"
FIXTURES = PLANNER / "mock_api" / "fixtures"
INPUTS = Path(os.environ.get("WFG_ASSETS_DIR", PLANNER / ".assets")) / "extracted" / "WFG-evaluated-routing-inputs-20261015"
REGIONS = ["uljin_2022", "miryang_2022", "hongseong_2023", "uiseong_andong_2025", "yeongdeok_2025"]
ROLES = {"origin", "destination", "research_origin", "research_destination"}
CATEGORIES = {"village", "hamlet", "nursing_home", "social_facility", "shelter", "assembly_point", "school",
              "community_hall", "research"}
EXCLUDED_SHELTER_TYPES = {"gazebo", "public_transport", "picnic_shelter", "sun_shelter", "weather_shelter",
                          "field_shelter", "changing_rooms", "lean_to", "rock_shelter"}

if not (PUBLIC / "index.json").is_file():
    pytest.skip("generated place files missing — run planner/tools/extract_places.py", allow_module_level=True)

needs_assets = pytest.mark.skipif(not (INPUTS / "graphs").is_dir(),
                                  reason="planner/.assets release extracts missing — run planner/scripts/fetch_planner_assets.sh")


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def index():
    return load(PUBLIC / "index.json")


@pytest.fixture(scope="module")
def places():
    return {r: load(PUBLIC / r / "places.geojson") for r in REGIONS}


@pytest.fixture(scope="module")
def reports():
    return {r: load(PUBLIC / r / "places_report.json") for r in REGIONS}


@pytest.fixture(scope="module")
def raw():
    return {r: load(OSM / f"{r}.overpass.json") for r in REGIONS}


_TR = {}


def to_5179(lon, lat):
    if "t" not in _TR:
        from pyproj import Transformer
        _TR["t"] = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
    return _TR["t"].transform(lon, lat)


def props(fc):
    return [f["properties"] for f in fc["features"]]


# ---------------------------------------------------------------------------------------------

def test_index(index, places):
    assert [r["region_id"] for r in index] == REGIONS
    expected = {"uljin_2022": ("울진", "Uljin", 2022, "KFS_02", False),
                "miryang_2022": ("밀양", "Miryang", 2022, "KFS_11", False),
                "hongseong_2023": ("홍성", "Hongseong", 2023, "KFS_05", False),
                "uiseong_andong_2025": ("의성·안동", "Uiseong–Andong", 2025, "KFS_01", True),
                "yeongdeok_2025": ("영덕", "Yeongdeok", 2025, "KFS_01", True)}
    for r in index:
        assert set(r) == {"region_id", "name", "fire_year", "event_id", "bbox", "center", "zoom", "demo", "counts"}
        assert (r["name"]["ko"], r["name"]["en"], r["fire_year"], r["event_id"], r["demo"]) == expected[r["region_id"]]
        w, s, e, n = r["bbox"]
        assert w < r["center"][0] < e and s < r["center"][1] < n
        assert 8 <= r["zoom"] <= 16
        ps = props(places[r["region_id"]])
        assert r["counts"] == {"origins": sum(p["role"] == "origin" for p in ps),
                               "destinations": sum(p["role"] == "destination" for p in ps),
                               "research": sum(p["role"].startswith("research") for p in ps)}


def test_index_matches_regions_fixture(index):
    if not (FIXTURES / "regions.json").is_file():
        pytest.skip("regions.json fixture not built")
    reg = {r["id"]: r for r in load(FIXTURES / "regions.json")["regions"]}
    for r in index:
        assert r["bbox"] == reg[r["region_id"]]["bbox"]
        assert r["event_id"] == reg[r["region_id"]]["event_id"]


def test_feature_properties_well_formed(places):
    all_ids = []
    for region, fc in places.items():
        assert fc["type"] == "FeatureCollection"
        for f in fc["features"]:
            assert f["type"] == "Feature" and f["geometry"]["type"] == "Point"
            lon, lat = f["geometry"]["coordinates"]
            assert 124 < lon < 132 and 33 < lat < 39
            p = f["properties"]
            assert p["role"] in ROLES and p["category"] in CATEGORIES
            assert isinstance(p["source_tag"], str) and p["source_tag"]
            assert p["source"] in ("OpenStreetMap", "연구 패널 기록 임무")
            snap = p["snap"]
            assert isinstance(snap["node"], str) and snap["node"].startswith("osm:")
            assert 0 <= snap["distance_m"] <= 2000
            assert p["checkable"] == (snap["distance_m"] <= 300)
            assert p["vulnerable"] == (p["category"] in ("nursing_home", "social_facility"))
            if p["role"].startswith("research"):
                assert p["category"] == "research"
            else:
                assert p["category"] != "research"
                assert p["scenario_set_id"] is None and p["input_time"] is None and p["case_id"] is None
                assert p["recorded"] is None
            if p["role"] == "origin":
                assert p["category"] in ("village", "hamlet", "nursing_home", "social_facility")
            if p["role"] == "destination":
                assert p["category"] in ("shelter", "assembly_point", "school", "community_hall")
            all_ids.append(p["id"])
    assert len(all_ids) == len(set(all_ids)), "feature ids are not unique"


def test_no_invented_names(places, raw):
    for region, fc in places.items():
        elements = {f"osm:{e['type']}/{e['id']}": e for e in raw[region]["elements"]}
        for f in fc["features"]:
            p = f["properties"]
            if p["source"] != "OpenStreetMap":
                assert p["name"] is None and p["name_en"] is None
                continue
            el = elements[p["id"]]
            tags = el.get("tags", {})
            assert p["name"] == tags.get("name")
            assert p["name_en"] == (tags.get("name:en") or tags.get("name:ko-Latn"))
            assert p["osm"]["tags"] == tags and p["osm"]["id"] == el["id"] and p["osm"]["type"] == el["type"]
            lon = el.get("lon", el.get("center", {}).get("lon"))
            lat = el.get("lat", el.get("center", {}).get("lat"))
            assert f["geometry"]["coordinates"] == [round(lon, 7), round(lat, 7)]


def test_filters_applied_exactly(places):
    for region, fc in places.items():
        for p in props(fc):
            if p["source"] != "OpenStreetMap":
                continue
            t = p["osm"]["tags"]
            assert t.get("amenity") not in ("hospital", "clinic", "kindergarten")
            if p["category"] in ("village", "hamlet"):
                assert p["osm"]["type"] == "node" and t["place"] == p["category"]
                assert p["source_tag"] == f"place={t['place']}"
            assert t.get("place") not in ("town", "quarter", "neighbourhood", "isolated_dwelling")
            if t.get("amenity") == "townhall":
                assert "회관" in t.get("name", "") and p["category"] == "community_hall"
            if p["category"] == "shelter":
                assert t.get("amenity") == "shelter" and t.get("shelter_type") not in EXCLUDED_SHELTER_TYPES
            if p["category"] == "school":
                assert t.get("amenity") == "school" or t.get("building") == "school"
            if p["category"] == "assembly_point":
                assert t.get("emergency") == "assembly_point"
            if p["category"] in ("nursing_home", "social_facility"):
                assert t.get("amenity") in ("nursing_home", "social_facility") or "social_facility" in t


def test_every_osm_element_is_accounted_for(places, reports, raw):
    for region in REGIONS:
        rep = reports[region]
        used = set()
        for p in props(places[region]):
            if p["source"] == "OpenStreetMap":
                used.add(p["id"])
                used.update(p["osm"]["merged_ids"])
        excluded = {e["id"] for e in rep["excluded"]}
        dropped = {e["id"] for e in rep["dropped_far"]}
        merged = {m["merged"] for m in rep["merged"]}
        for e in rep["excluded"] + rep["dropped_far"]:
            assert e["reason"]
        ids = {f"osm:{e['type']}/{e['id']}" for e in raw[region]["elements"]}
        assert ids == used | excluded | dropped | merged, region
        assert not (excluded & used) and not (dropped & used)
        for d in rep["dropped_far"]:
            assert d["snap"]["distance_m"] > 2000
        assert rep["counts"]["osm_elements"] == len(raw[region]["elements"])


def test_school_node_way_dedupe(places, reports):
    for region in REGIONS:
        kept = {p["id"]: p for p in props(places[region])}
        for m in reports[region]["merged"]:
            assert m["kept"].startswith("osm:way/") and m["merged"].startswith("osm:node/")
            assert m["distance_m"] <= 150
            k = kept[m["kept"]]
            assert k["category"] == "school" and k["name"] == m["name"]
            assert m["kept"] in k["osm"]["merged_ids"] and m["merged"] in k["osm"]["merged_ids"]
            assert m["merged"] not in kept


def test_snap_is_nearest_allowed_node(places):
    if not (FIXTURES / "nodes").is_dir():
        pytest.skip("node tables not built")
    for region in REGIONS:
        t = load(FIXTURES / "nodes" / f"{region}.json")
        allowed = np.array(t["allowed"], bool)
        ids = np.array(t["ids"])[allowed]
        x, y = to_5179(np.array(t["lon"])[allowed], np.array(t["lat"])[allowed])
        x, y = np.asarray(x), np.asarray(y)
        id_pos = {nid: i for i, nid in enumerate(ids)}
        for f in places[region]["features"]:
            p = f["properties"]
            if p["source"] != "OpenStreetMap":
                continue
            px, py = to_5179(*f["geometry"]["coordinates"])
            d = np.hypot(x - px, y - py)
            assert p["snap"]["node"] in id_pos, (region, p["id"])
            # node table coordinates are rounded to 6 decimals (~0.1 m): allow 0.5 m slack
            assert abs(d[id_pos[p["snap"]["node"]]] - p["snap"]["distance_m"]) < 0.5
            assert d[id_pos[p["snap"]["node"]]] <= d.min() + 0.5


def test_research_points(places):
    total = 0
    for region, fc in places.items():
        res = [p for p in props(fc) if p["role"].startswith("research")]
        assert len(res) == 8, region
        total += len(res)
        by_id = {p["id"]: p for p in res}
        for p in res:
            word = "origin" if p["role"] == "research_origin" else "destination"
            assert p["id"] == f"research:{region}:{p['case_id']}:{word}"
            assert p["source"] == "연구 패널 기록 임무"
            assert p["source_tag"] == f"request {p['case_id']} {word} node {p['snap']['node']}"
            assert p["snap"]["distance_m"] == 0 and p["checkable"] is True
            assert p["osm"] is None and p["name"] is None
            assert p["scenario_set_id"].startswith("ffb1:" + p["case_id"].split("_")[0] + ":")
            compact = p["input_time"].replace("-", "").replace(":", "")
            assert p["case_id"].startswith(compact)
            if word == "origin":
                rec = p["recorded"]
                assert set(rec) >= {"destination_id", "destination_node", "depart_offset_s", "dwell_s",
                                    "destination_window", "incurred_dose_kj_m2"}
                dest = by_id[rec["destination_id"]]
                assert dest["role"] == "research_destination" and dest["case_id"] == p["case_id"]
                assert dest["snap"]["node"] == rec["destination_node"]
            else:
                assert p["recorded"] is None
    assert total == 40


@needs_assets
def test_research_points_match_requests(places):
    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
    for region, fc in places.items():
        g = load(INPUTS / "graphs" / region / "graph.json")
        xy = {n["id"]: (n["x"], n["y"]) for n in g["nodes"]}
        reqs = sorted((INPUTS / "latest_inputs_try02" / "requests" / region).glob("*.json"))
        assert len(reqs) == 4
        by_id = {p["id"]: (f, p) for f in fc["features"] for p in [f["properties"]]}
        for rp in reqs:
            q = load(rp)
            case = rp.stem
            fo, po = by_id[f"research:{region}:{case}:origin"]
            fd, pd = by_id[f"research:{region}:{case}:destination"]
            assert po["snap"]["node"] == q["position"]["node"]
            assert pd["snap"]["node"] == q["destinations"][0]["node"]
            rec = po["recorded"]
            assert rec["depart_offset_s"] == q["departure"]
            assert rec["dwell_s"] == q["destinations"][0]["dwell"]
            assert rec["destination_window"] == q["destinations"][0]["open_intervals"][0]
            inc = list(q["incurred"].values())
            assert rec["incurred_dose_kj_m2"] == (inc[0] if all(v == inc[0] for v in inc) else None)
            assert rec["limits"]["peak_kw_m2"] == q["budgets"]["peak"]
            for f, node in ((fo, q["position"]["node"]), (fd, q["destinations"][0]["node"])):
                lon, lat = tr.transform(*xy[node])
                x, y = to_5179(*f["geometry"]["coordinates"])
                assert math.hypot(x - xy[node][0], y - xy[node][1]) < 0.5


def test_sources_json(raw):
    src = load(OSM / "SOURCES.json")
    assert "CURRENT" in src["note"] and "HISTORICAL" in src["note"]
    assert "ODbL" in src["license"]
    for region in REGIONS:
        e = src["regions"][region]
        p = OSM / f"{region}.overpass.json"
        assert hashlib.sha256(p.read_bytes()).hexdigest() == e["sha256"]
        assert e["bytes"] == p.stat().st_size
        assert e["timestamp_osm_base"] == raw[region]["osm3s"]["timestamp_osm_base"]
        assert e["endpoint"].startswith("https://") and e["endpoint"].endswith("/interpreter")
        s, w, n, ea = e["bbox_swne"]
        assert ("%.7f,%.7f,%.7f,%.7f" % (s, w, n, ea)) in e["query"]
        assert e["query"].startswith("[out:json][timeout:120];") and e["query"].endswith("out center tags;")
        assert e["fetched_at"] and e["graph_snapshot"]
        for el in raw[region]["elements"]:
            lat = el.get("lat", el.get("center", {}).get("lat"))
            lon = el.get("lon", el.get("center", {}).get("lon"))
            assert s <= lat <= n and w <= lon <= ea


def test_reports_list_reasons(reports):
    for region, rep in reports.items():
        assert rep["region_id"] == region
        reasons = " | ".join(e["reason"] for e in rep["excluded"])
        for e in rep["excluded"]:
            t = e["tags"]
            if t.get("amenity") in ("hospital", "kindergarten", "clinic"):
                assert t["amenity"] in e["reason"]
            if t.get("place") in ("town", "quarter", "neighbourhood", "isolated_dwelling"):
                assert "place=" in e["reason"]
        assert isinstance(reasons, str)
