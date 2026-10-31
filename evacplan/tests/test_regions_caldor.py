"""Real US region 1 (Caldor 2021, South Lake Tahoe) builder: offline tests on tiny hand-made
FIXTURE inputs. The fixtures sit at a made-up place in central California (around -119.49, 37.00),
carry FIXTURE names and addresses, and are not Caldor data. Nothing here touches the network."""
import json
import math
import urllib.error

import networkx as nx
import numpy as np
import osmnx as ox
import pytest
from shapely.geometry import LineString

from evacplan import Oracle, Solution, load_instance, load_scenario_set, validate_solution
from evacplan.cli import main
from evacplan.regions import BuildBlocked
from evacplan.regions.caldor import CaldorConfig, CaldorInputs, build, check_inputs, requirements
from evacplan.regions.cms import download_provider_file, read_provider_file, select
from evacplan.regions.geocode import geocode_census, multipart, parse_batch_response, read_geocodes_csv
from evacplan.regions.osm import ATTRIBUTION, download_drive_graph, load_graph_file, nearest_node, to_road_graph
from evacplan.regions.people import FleetRule, residents_for, split_by_mix, synthetic_fleet
from evacplan.regions.perimeters import grid_for, read_perimeter_geojson

LONS = (-119.495, -119.490, -119.485, -119.480)
LATS = (36.996, 37.000, 37.004, 37.008)
BBOX = (-119.50, 36.99, -119.47, 37.012)
ISSUE = "2000-01-01T12:00:00Z"

CMS_NEW = """CMS Certification Number (CCN),Provider Name,Provider Address,City/Town,State,ZIP Code,County/Parish,\
Number of Certified Beds,Average Number of Residents per Day,Latitude,Longitude
F00001,FIXTURE Facility A,1 Test Way,Testville,CA,95000,Test,60,48.4,37.0010,-119.4950
F00002,FIXTURE Facility B,2 Test Way,Testville,CA,95000,Test,40,,,
F00003,FIXTURE Facility C,3 Test Way,Elsewhere,OR,97000,Other,80,70,44.0,-121.0
F00004,FIXTURE Facility D,4 Test Way,Testville,NV,89000,Test,30,20,,
"""
CMS_OLD = """Federal Provider Number,Provider Name,Provider Address,Provider City,Provider State,Provider Zip Code,\
Number of Certified Beds,Average Number of Residents Per Day,Location
055555,OLD FIXTURE,9 Old Rd,Oldtown,ca,95555-1234,99,80.2,"9 OLD RD
OLDTOWN, CA 95555
(37.5, -120.1)"
"""


# ----------------------------------------------------------------------------- fixtures
def fixture_graph() -> nx.MultiDiGraph:
    """4 x 4 lattice (two-way), primary roads on the east column and the north row, one one-way
    street, a dead-end spur and an unreachable one-way sink (dropped: not strongly connected)."""
    G = nx.MultiDiGraph(crs="EPSG:4326")
    nid = {}
    for r, lat in enumerate(LATS):
        for c, lon in enumerate(LONS):
            nid[r, c] = 100 + 10 * r + c
            G.add_node(nid[r, c], x=lon, y=lat, street_count=4)

    def two(a, b, osmid, hw, geom=None):
        for (u, v), rev in (((a, b), False), ((b, a), True)):
            attrs = dict(osmid=osmid, highway=hw, oneway=False, reversed=rev, length=1.0)
            if geom is not None:
                attrs["geometry"] = LineString(geom[::-1] if rev else geom)
            G.add_edge(u, v, **attrs)

    osmid = 1000
    for r in range(4):
        for c in range(4):
            for dr, dc in ((0, 1), (1, 0)):
                r2, c2 = r + dr, c + dc
                if r2 < 4 and c2 < 4:
                    if (r, c, r2, c2) == (0, 0, 0, 1):
                        continue                                   # replaced by a one-way street below
                    hw = "primary" if (c == 3 and c2 == 3) or (r == 3 and r2 == 3) else "residential"
                    geom = None
                    if (r, c, r2, c2) == (1, 1, 1, 2):            # a bent road with a polyline
                        geom = [(LONS[1], LATS[1]), (0.5 * (LONS[1] + LONS[2]), LATS[1] + 0.001), (LONS[2], LATS[1])]
                    osmid += 1
                    two(nid[r, c], nid[r2, c2], osmid, hw, geom)
    G.add_edge(nid[0, 0], nid[0, 1], osmid=2001, highway="residential", oneway=True, reversed=False, length=1.0)
    G.add_node(900, x=-119.4925, y=37.0060, street_count=1)                       # dead-end spur
    two(nid[2, 1], 900, 2002, "residential")
    G.add_node(901, x=-119.4875, y=36.9930, street_count=1)                       # one-way sink
    G.add_edge(nid[0, 2], 901, osmid=2003, highway="residential", oneway=True, reversed=False, length=1.0)
    return G


def perimeters_geojson() -> dict:
    def square(lon0, lat0, lon1, lat1):
        return [[[lon0, lat0], [lon1, lat0], [lon1, lat1], [lon0, lat1], [lon0, lat0]]]
    feats = [
        {"type": "Feature", "properties": {"time": "2000-01-01T11:00:00Z"},
         "geometry": {"type": "Polygon", "coordinates": square(-119.4990, 36.9940, -119.4955, 36.9975)}},
        {"type": "Feature", "properties": {"time": "2000-01-01T15:00:00Z"},
         "geometry": {"type": "MultiPolygon", "coordinates": [square(-119.4990, 36.9940, -119.4910, 36.9990),
                                                             square(-119.4990, 37.0040, -119.4975, 37.0050)]}},
    ]
    return {"type": "FeatureCollection", "features": feats}


@pytest.fixture
def files(tmp_path):
    graphml = tmp_path / "roads.graphml"
    ox.save_graphml(fixture_graph(), graphml)
    cms = tmp_path / "NH_ProviderInfo_FIXTURE.csv"
    cms.write_text(CMS_NEW)
    geo = tmp_path / "geocodes.csv"
    geo.write_text("ccn,lat,lon,source\nF00002,37.0000,-119.4800,file\nF00004,39.5,-119.0,file\n")
    per = tmp_path / "perimeters.geojson"
    per.write_text(json.dumps(perimeters_geojson()))
    return CaldorInputs(graph=graphml, cms=cms, geocodes=geo, perimeters=per)


def fixture_config(**kw) -> CaldorConfig:
    return CaldorConfig(region_id="FIXTURE-region", bbox_lonlat=BBOX, issue_time_utc=ISSUE, cell_m=200.0,
                        exit_band_m=300.0, synthetic_hazard=True, **kw)


# ------------------------------------------------------------------------------ parsers
def test_cms_provider_file_new_and_old_headers():
    new = read_provider_file(CMS_NEW)
    assert [f.ccn for f in new] == ["F00001", "F00002", "F00003", "F00004"]
    a, b = new[0], new[1]
    assert (a.name, a.certified_beds, a.avg_residents, a.lat, a.lon, a.coord_source) == \
        ("FIXTURE Facility A", 60, 48.4, 37.001, -119.495, "cms")
    assert b.lat is None and b.avg_residents is None and b.coord_source is None
    old = read_provider_file(CMS_OLD)[0]
    assert (old.ccn, old.state, old.zip, old.certified_beds, old.lat, old.lon) == ("055555", "CA", "95555", 99, 37.5,
                                                                                  -120.1)
    assert [f.ccn for f in select(new, states=("CA", "NV"), bbox_lonlat=BBOX)] == ["F00001", "F00002", "F00004"]
    with pytest.raises(ValueError, match="not a CMS"):
        read_provider_file("a,b\n1,2\n")


def test_census_batch_response_and_request():
    text = ('"F00002","2 Test Way, Testville, CA, 95000","Match","Exact","2 TEST WAY, TESTVILLE, CA, 95000",'
            '"-119.48,37.0","1","L"\n"F00004","4 Test Way","No_Match"\n"F00005","5 Test Way","Tie"\n')
    got, failed = parse_batch_response(text)
    assert got["F00002"].lat == 37.0 and got["F00002"].lon == -119.48 and got["F00002"].source == "census:Exact"
    assert failed == {"F00004": "No_Match", "F00005": "Tie"}
    body, ctype = multipart({"benchmark": "Public_AR_Current"}, {"addressFile": ("a.csv", "x,y\n")})
    assert ctype.startswith("multipart/form-data; boundary=") and b'name="benchmark"' in body and b"x,y" in body
    facs = read_provider_file(CMS_NEW)[1:2]
    seen = {}

    def fake_post(url, body, ctype, timeout):
        seen["url"] = url
        return text
    got2, _ = geocode_census(facs, post=fake_post)
    assert "geocoding.geo.census.gov" in seen["url"] and got2["F00002"].lat == 37.0


def test_people_rules():
    assert split_by_mix(48) == (36, 9, 3) and split_by_mix(30) == (23, 5, 2) and split_by_mix(0) == (0, 0, 0)
    for n in range(0, 200, 7):
        assert sum(split_by_mix(n)) == n
    a, b = read_provider_file(CMS_NEW)[:2]
    ra, src_a = residents_for(a)
    rb, src_b = residents_for(b)
    assert ra.vector() == (36, 9, 3) and "average number of residents" in src_a
    assert rb.vector() == (23, 5, 2) and "certified beds" in src_b
    fleet = synthetic_fleet(["n1", "n2"], (59, 14, 5), "exit", FleetRule())
    kinds = [v.kind for v in fleet]
    assert kinds.count("van (SYNTHETIC)") == 2 and kinds.count("bus (SYNTHETIC)") == 1
    assert kinds.count("ambulance (SYNTHETIC)") == 2
    assert all(v.start_s == 1800.0 for v in fleet if v.depot == "exit") and fleet[0].depot == "n1"


def test_osm_conversion_follows_the_router_conventions():
    rg, info = to_road_graph(fixture_graph(), crs_epsg=3310, waitable_nodes=[111])
    ids = {n.id for n in rg.nodes}
    assert "osm:901" not in ids and info["dropped_nodes"] == 1                  # not strongly connected
    assert rg.crs_epsg == 3310 and rg.provenance["attribution"] == ATTRIBUTION
    nodes = {n.id: n for n in rg.nodes}
    assert all(abs(n.x) < 1e6 and abs(n.y) < 1e6 for n in rg.nodes) and nodes["osm:100"].x != -119.495
    edges = {e.id: e for e in rg.edges}
    for e in rg.edges:
        g = [(nodes[e.u].x, nodes[e.u].y), (nodes[e.v].x, nodes[e.v].y)] if e.geometry is None else e.geometry
        length = sum(math.dist(p, q) for p, q in zip(g, g[1:]))
        assert e.travel_time_s == max(1, math.ceil(length / (40 / 3.6)))
    bent = [e for e in rg.edges if e.geometry is not None]
    assert len(bent) == 2 and all(len(e.geometry) == 3 for e in bent)
    turns = set(rg.forbidden_turns)
    assert ("osm:111>112#0", "osm:112>111#0") in turns                  # U-turn on the same way
    assert ("osm:121>900#0", "osm:900>121#0") not in turns              # allowed at the dead end
    assert ("osm:900>121#0", "osm:121>900#0") in turns
    assert not any(a == "osm:100>101#0" for a, _ in turns)                  # one-way: no reverse edge
    assert nodes["osm:900"].waitable and nodes["osm:111"].waitable and not nodes["osm:112"].waitable
    assert "primary" in info["highway"]["osm:103>113#0"]
    node, dist = nearest_node(rg, nodes["osm:122"].x + 3.0, nodes["osm:122"].y)
    assert node == "osm:122" and dist == pytest.approx(3.0)
    assert set(edges) == {e.id for e in rg.edges}


def test_perimeters_geojson_and_grid():
    series = read_perimeter_geojson(perimeters_geojson(), crs_epsg=3310)
    assert [t.isoformat() for t, _ in series] == ["2000-01-01T11:00:00+00:00", "2000-01-01T15:00:00+00:00"]
    assert len(series[1][1]) == 2 and series[0][1][0][0].shape == (5, 2)
    x, y = series[0][1][0][0][0]
    assert 40_000 < x < 50_000 and -120_000 < y < -110_000                      # metres in California Albers
    bad = perimeters_geojson()
    bad["features"][0]["properties"]["time"] = "2000-01-01T11:00:00"
    with pytest.raises(ValueError, match="timezone"):
        read_perimeter_geojson(bad)
    transform, h, w = grid_for((1000.0, 2000.0, 2950.0, 2100.0), 375.0, 2)
    assert transform == (375.0, 0.0, 0.0, 0.0, -375.0, 3000.0) and (h, w) == (5, 10)


# ----------------------------------------------------------------------------- the build
def test_build_on_fixtures_end_to_end(files, tmp_path):
    built = build(files, fixture_config())
    inst, ss = built.instance, built.hazard
    assert inst.synthetic and "SYNTHETIC" in inst.name and inst.name.startswith("FIXTURE-region")
    assert inst.provenance["attribution"] == ATTRIBUTION and "SYNTHETIC" in inst.provenance["label"]
    assert [f.id for f in inst.facilities] == ["CMS-F00001", "CMS-F00002"]          # OR excluded, NV outside bbox
    assert [f.residents.vector() for f in inst.facilities] == [(36, 9, 3), (23, 5, 2)]
    assert [f.name for f in inst.facilities] == ["FIXTURE Facility A", "FIXTURE Facility B"]
    assert [s.id for s in inst.shelters] == ["EXIT1", "EXIT2"] and all("SYNTHETIC" in s.name for s in inst.shelters)
    east, north = inst.shelters[0].node, inst.shelters[1].node                     # major-road exits
    assert east in {"osm:103", "osm:113", "osm:123", "osm:133"} and north in {"osm:130", "osm:131", "osm:132", "osm:133"}
    assert east != north
    assert len(inst.vehicles) == 5 and all("SYNTHETIC" in v.kind for v in inst.vehicles)
    assert ss.meta.source == "perimeter" and ss.meta.synthetic and ss.K == 4 and ss.meta.horizon_s == 3 * 3600.0
    assert ss.meta.crs_epsg == inst.graph.crs_epsg == 3310 and np.isinf(ss.extinguish_s[np.isfinite(ss.ignite_s)]).sum() == 0
    burned_first = np.isneginf(ss.ignite_s[0])
    assert burned_first.any() and np.isfinite(ss.ignite_s[0]).any()
    nodes = {n.id: n for n in inst.graph.nodes}
    for f in inst.facilities:
        assert nodes[f.node].waitable
    report = built.report
    assert {r["ccn"] for r in report["facilities"] if r["kept"]} == {"F00001", "F00002"}
    empty = Solution(instance=inst.name, method="empty")
    assert validate_solution(inst, empty).ok
    r = Oracle(inst, ss).check_plan(empty)
    assert r.not_planned_total == inst.residents_total == 78 and r.label == "SYNTHETIC"
    out = built.write(tmp_path / "out")
    back = load_instance(out / "instance.json")
    assert back == inst and load_scenario_set(back).meta == ss.meta and (out / "build_report.json").is_file()


def test_missing_coordinates_block_the_build(files):
    no_geo = CaldorInputs(graph=files.graph, cms=files.cms, perimeters=files.perimeters)
    with pytest.raises(BuildBlocked) as exc:
        build(no_geo, fixture_config())
    text = exc.value.report()
    assert "BLOCKED" in text and "geocoding.geo.census.gov" in text and "F00002" in text


def test_blocked_without_inputs_names_every_host_and_file(capsys):
    missing = check_inputs(CaldorInputs())
    assert sorted(m.item for m in missing) == sorted(m.item for m in requirements())
    needs = " ".join(m.needs for m in missing)
    for want in ("overpass-api.de", "data.cms.gov", "geocoding.geo.census.gov", "--graph", "--cms", "--geocodes",
                 "--perimeters", "NIROPS", "10.17632/95rj5d379g.1"):
        assert want in needs
    with pytest.raises(BuildBlocked):
        build(CaldorInputs())
    assert main(["build-caldor"]) == 2
    out = capsys.readouterr().out
    assert out.startswith("BLOCKED: US1-caldor-2021-slt cannot be built here") and "overpass-api.de" in out
    assert [m.item for m in check_inputs(CaldorInputs(online=True))] == ["Caldor fire perimeters"]


def test_downloads_report_blocked_hosts(monkeypatch, tmp_path):
    def refuse(*a, **k):
        raise ConnectionError("blocked by the network policy")
    monkeypatch.setattr(ox, "graph_from_bbox", refuse)
    with pytest.raises(BuildBlocked, match="overpass-api.de"):
        download_drive_graph(BBOX)

    def no_route(*a, **k):
        raise urllib.error.URLError("403 Forbidden")
    with pytest.raises(BuildBlocked, match="data.cms.gov"):
        download_provider_file(tmp_path / "cms.csv", opener=no_route)
    with pytest.raises(BuildBlocked, match="geocoding.geo.census.gov"):
        geocode_census(read_provider_file(CMS_NEW)[:1], post=no_route)
    assert not (tmp_path / "cms.csv").exists()


def test_graph_file_formats(files, tmp_path):
    G = load_graph_file(files.graph)
    assert G.number_of_nodes() == fixture_graph().number_of_nodes()
    bad = tmp_path / "roads.shp"
    bad.write_text("")
    with pytest.raises(ValueError):
        load_graph_file(bad)
    assert read_geocodes_csv(files.geocodes)["F00002"].lon == -119.48
