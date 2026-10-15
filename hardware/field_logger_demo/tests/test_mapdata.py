"""Offline map data (spec section 7): the converter of tools/fetch_mapdata.py on small OSM extracts, the venue area
that ships with the app, the choice of map for real and simulated sessions, and time zones by place."""
import json
import sys

import pytest

from app import config, geo, replay
from conftest import ROOT

sys.path.insert(0, str(ROOT / "tools"))
import fetch_mapdata as fm  # noqa: E402

OSM = b"""<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
 <node id="1" lat="35.1400000" lon="126.8400000"/><node id="2" lat="35.1400000" lon="126.8410000"/>
 <node id="3" lat="35.1400000" lon="126.8420000"/><node id="4" lat="35.1410000" lon="126.8400000"/>
 <node id="5" lat="35.1410000" lon="126.8410000"/><node id="6" lat="35.1405000" lon="126.8405000"/>
 <node id="10" lat="35.1420000" lon="126.8400000"/><node id="11" lat="35.1420000" lon="126.8404000"/>
 <node id="12" lat="35.1424000" lon="126.8404000"/><node id="13" lat="35.1424000" lon="126.8400000"/>
 <node id="20" lat="35.1430000" lon="126.8400000"/><node id="21" lat="35.1430000" lon="126.8410000"/>
 <node id="22" lat="35.1440000" lon="126.8410000"/><node id="23" lat="35.1440000" lon="126.8400000"/>
 <node id="24" lat="35.1433000" lon="126.8403000"/><node id="25" lat="35.1433000" lon="126.8406000"/>
 <node id="26" lat="35.1436000" lon="126.8406000"/><node id="27" lat="35.1436000" lon="126.8403000"/>
 <node id="30" lat="35.1450000" lon="126.8400000"/><node id="31" lat="35.1451000" lon="126.8420000"/>
 <way id="100"><nd ref="1"/><nd ref="2"/><nd ref="3"/><tag k="highway" v="residential"/></way>
 <way id="101"><nd ref="4"/><nd ref="5"/><tag k="highway" v="footway"/></way>
 <way id="102"><nd ref="1"/><nd ref="6"/><tag k="highway" v="proposed"/></way>
 <way id="103"><nd ref="10"/><nd ref="11"/><nd ref="12"/><nd ref="13"/><nd ref="10"/><tag k="building" v="yes"/></way>
 <way id="104"><nd ref="20"/><nd ref="21"/><nd ref="22"/></way>
 <way id="105"><nd ref="22"/><nd ref="23"/><nd ref="20"/></way>
 <way id="106"><nd ref="24"/><nd ref="25"/><nd ref="26"/><nd ref="27"/><nd ref="24"/></way>
 <way id="107"><nd ref="30"/><nd ref="31"/><tag k="waterway" v="stream"/></way>
 <way id="108"><nd ref="4"/><nd ref="5"/><nd ref="6"/><nd ref="4"/><tag k="leisure" v="park"/></way>
 <way id="109"><nd ref="10"/><nd ref="11"/><nd ref="12"/><tag k="building" v="yes"/></way>
 <way id="110"><nd ref="1"/><nd ref="2"/><nd ref="5"/><nd ref="4"/><nd ref="1"/><tag k="natural" v="water"/></way>
 <relation id="200"><member type="way" ref="104" role="outer"/><member type="way" ref="105" role="outer"/>
  <member type="way" ref="106" role="inner"/><tag k="type" v="multipolygon"/><tag k="building" v="school"/></relation>
</osm>"""


def _overpass_equivalent():
    """The same features as Overpass returns them with 'out geom'."""
    d = fm.read_osm_xml(OSM)
    fm._resolve_members(d)
    els = []
    for wid, w in d.ways.items():
        els.append({"type": "way", "id": wid, "tags": w["tags"], "geometry": [{"lat": y, "lon": x} for x, y in w["coords"]]})
    for rid, r in d.relations.items():
        els.append({"type": "relation", "id": rid, "tags": r["tags"],
                    "members": [{"type": "way", "ref": ref, "role": role, "geometry": [{"lat": y, "lon": x} for x, y in c]}
                                for role, ref, c in r["members"]]})
    return {"elements": els}


def _summary(layers):
    return {k: sorted((f["geometry"]["type"], f["properties"].get("kind"), f["properties"].get("w"),
                       len(f["geometry"]["coordinates"])) for f in fc["features"]) for k, fc in layers.items()}


def test_osm_xml_is_converted_into_the_four_layers():
    layers = fm.convert(fm.read_osm_xml(OSM))
    roads = layers["roads"]["features"]
    assert sorted((f["properties"]["hw"], f["properties"]["kind"], f["properties"]["w"]) for f in roads) == \
        [("footway", "minor", 2.5), ("residential", "minor", 8)]
    res = next(f for f in roads if f["properties"]["hw"] == "residential")
    assert len(res["geometry"]["coordinates"]) == 2                  # the collinear middle point is simplified away
    b = layers["buildings"]["features"]
    assert len(b) == 2                                               # way 103 and relation 200; 109 is not closed
    multi = next(f for f in b if len(f["geometry"]["coordinates"]) == 2)
    assert len(multi["geometry"]["coordinates"][0]) == 4 + 1 and len(multi["geometry"]["coordinates"][1]) == 5
    w = layers["water"]["features"]
    assert sorted(f["geometry"]["type"] for f in w) == ["LineString", "Polygon"]
    assert next(f for f in w if f["geometry"]["type"] == "LineString")["properties"] == {"kind": "stream", "w": 4}
    assert len(layers["parks"]["features"]) == 1
    for fc in layers.values():
        for f in fc["features"]:
            pts = f["geometry"]["coordinates"] if f["geometry"]["type"] == "LineString" else f["geometry"]["coordinates"][0]
            assert all(round(x, 6) == x and round(y, 6) == y for x, y in pts)


def test_overpass_json_gives_the_same_layers():
    a = fm.convert(fm.read_osm_xml(OSM))
    b = fm.convert(fm.read_overpass_json(_overpass_equivalent()))
    assert _summary(a) == _summary(b)


def test_join_rings_and_simplify():
    a, b, c = (0.0, 0.0), (0.001, 0.0), (0.001, 0.001)
    rings = fm.join_rings([[a, b], [c, b], [c, a]])                 # one piece reversed
    assert len(rings) == 1 and rings[0][0] == rings[0][-1] and len(rings[0]) == 4
    assert fm.join_rings([[a, b], [b, c]]) == []                    # never closes: dropped
    line = [(126.84 + k * 1e-5, 35.14) for k in range(20)]
    assert fm.simplify(line) == [line[0], line[-1]]


def test_write_area_and_the_app_reads_it(tmp_path):
    layers = fm.convert(fm.read_osm_xml(OSM))
    meta = fm.write_area(tmp_path / "t", "t", layers, (35.139, 126.839, 35.146, 126.843), "test", "q")
    assert meta["synthetic"] is False and meta["counts"]["buildings"] == 2
    src = (tmp_path / "t" / "SOURCE.txt").read_text(encoding="utf-8")
    assert "OpenStreetMap contributors" in src and "ODbL" in src
    assert json.loads((tmp_path / "t" / "meta.json").read_text(encoding="utf-8"))["bounds"] == [126.839, 35.139, 126.843, 35.146]


def test_bbox_arguments():
    assert fm.parse_bbox("35.1382,126.8324,35.1516,126.8488") == (35.1382, 126.8324, 35.1516, 126.8488)
    with pytest.raises(SystemExit):
        fm.parse_bbox("35.2,126.8,35.1,126.9")
    q = fm.overpass_query((35.1382, 126.8324, 35.1516, 126.8488))
    assert q.startswith("[out:json]") and q.endswith("out geom;") and q.count("35.1382000,126.8324000,35.1516000,126.8488000") == 10


# ------------------------------------------------------------------ the venue area that ships with the app
def test_the_venue_area_is_real_osm_data_around_the_convention_centre():
    d = config.MAPDATA / "gwangju_kdj"
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    assert meta["synthetic"] is False and "ODbL" in (d / "SOURCE.txt").read_text(encoding="utf-8")
    w, s, e, n = meta["bounds"]
    for lat, lon in ((35.1465, 126.8400), (35.1432, 126.8413)):    # the convention centre and its subway station
        assert s < lat < n and w < lon < e
    assert (n - s) * 111320 > 1400 and (e - w) * 111320 * 0.818 > 1400
    for k in ("roads", "buildings", "water", "parks"):
        fc = json.loads((d / ("%s.geojson" % k)).read_text(encoding="utf-8"))
        assert fc["type"] == "FeatureCollection" and fc["features"], k


def test_real_sessions_get_real_map_data_and_sim_sessions_the_synthetic_map():
    b = [126.8390, 35.1470, 126.8392, 35.1472]
    assert replay.detect_area(b, sim=False) == "gwangju_kdj"
    assert replay.detect_area(b, sim=True) == "sim_city"
    outside = [126.80, 35.10, 126.801, 35.101]                     # the synthetic map covers it, real data does not
    assert replay.detect_area(outside, sim=True) == "sim_city" and replay.detect_area(outside, sim=False) is None
    assert replay.detect_area([121.4, 31.2, 121.5, 31.3]) is None                      # Shanghai: the grid


def test_time_zone_by_place():
    assert geo.tz_for(35.1465, 126.84) == "Asia/Seoul"
    assert geo.tz_for(31.209, 121.439) == "Asia/Shanghai"
    assert geo.tz_for(35.68, 139.76) == "Asia/Tokyo"
    assert geo.tz_for(22.30, 114.17) == "Asia/Hong_Kong"
    assert geo.tz_for(51.5, -0.12) is None and geo.tz_for(None, None) is None
