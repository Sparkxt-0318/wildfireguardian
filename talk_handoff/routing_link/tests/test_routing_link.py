"""Synthetic checks of blocking.py, osm_graph.py and route.py (no real data)."""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import blocking as B  # noqa: E402
import osm_graph as G  # noqa: E402

K = 6
EDGES = np.linspace(0, 3600, K + 1)


def hour(ny=1, nx=3, q=0.0, co_ppm=0.0, p=0.0, unresolved=False):
    return B.HourFields(bin_edges_s=EDGES, p_vis=np.full((ny, nx), p, float), pm25_ug_m3=np.zeros((ny, nx)),
                        q_rad_kw_m2=np.full((K, ny, nx), q, float), thermal_resolved=np.full((ny, nx), not unresolved),
                        co_mg_m3=np.full((K, ny, nx), co_ppm * B.MG_M3_PER_PPM, float))


def test_thresholds_are_the_protocol_values():
    assert B.RADIANT_KW_M2 == {"residents": 2.5, "responders": 7.0}
    assert B.CO_AEGL2_PPM == {600: 420.0, 1800: 150.0, 3600: 83.0}
    assert B.VIS_LEVEL_MAIN == 0.5 and B.VIS_LEVELS == (0.1, 0.5, 0.9)


def test_radiant_audiences():
    hs = [hour(q=0.0), hour(q=3.0), hour(q=8.0)]
    crit, comp, _, _ = B.criteria_by_hour(hs)
    res = B.first_blocked_minutes(B.audience_rule(crit, "residents"), comp)
    rsp = B.first_blocked_minutes(B.audience_rule(crit, "responders"), comp)
    assert np.all(res == 60.0) and np.all(rsp == 120.0)


def test_radiant_exact_threshold_blocks():
    crit, *_ = B.criteria_by_hour([hour(q=2.5)])
    assert crit["radiant_residents"].all() and not crit["radiant_responders"].any()


def test_co_ten_minute_spike_only():
    h0 = hour()
    co = np.zeros((K, 1, 3))
    co[2] = 420.0 * B.MG_M3_PER_PPM  # one 10 min bin at exactly 420 ppm in hour 0
    h0.co_mg_m3 = co
    crit, *_ = B.criteria_by_hour([h0, hour()])
    assert crit["co_10min"][0].all() and not crit["co_30min"].any() and not crit["co_60min"].any()


def test_co_sixty_minute_across_hour_boundary():
    # 90 ppm in the last 30 min of hour 0 and the first 30 min of hour 1: only a window crossing the boundary reaches 83
    a, b = hour(), hour()
    ca, cb = np.zeros((K, 1, 3)), np.zeros((K, 1, 3))
    ca[3:] = 90 * B.MG_M3_PER_PPM
    cb[:3] = 90 * B.MG_M3_PER_PPM
    a.co_mg_m3, b.co_mg_m3 = ca, cb
    crit, comp, _, _ = B.criteria_by_hour([a, b])
    assert not crit["co_60min"][0].any() and crit["co_60min"][1].all()
    assert np.all(B.first_blocked_minutes(crit["co_60min"], comp) == 60.0)


def test_co_hourly_mean_fallback_is_60_min_only():
    h = hour()
    h.co_mg_m3 = None
    h.co_mean_mg_m3 = np.full((1, 3), 83 * B.MG_M3_PER_PPM)
    crit, _, _, notes = B.criteria_by_hour([h])
    assert crit["co_60min"].all() and "co_10min" not in crit and any("not computable" in n for n in notes)


def test_visibility_levels():
    crit, comp, _, _ = B.criteria_by_hour([hour(p=0.3)])
    assert crit["vis_p10"].all() and not crit["vis_p50"].any() and not crit["vis_p90"].any()
    assert np.all(np.isinf(B.first_blocked_minutes(B.audience_rule(crit, "residents", 0.5), comp)))
    assert np.all(B.first_blocked_minutes(B.audience_rule(crit, "residents", 0.1), comp) == 0.0)


def test_nan_cell_not_computed_and_earlier_of():
    h = hour(p=0.0)
    h.p_vis[0, 1] = np.nan
    crit, comp, _, _ = B.criteria_by_hour([h])
    t = B.first_blocked_minutes(B.audience_rule(crit, "residents"), comp)
    assert np.isinf(t[0, 0]) and np.isnan(t[0, 1])
    fire = np.array([[30.0, np.nan, np.inf]])
    e = B.earlier_of(t, fire)
    assert e[0, 0] == 30.0 and np.isnan(e[0, 1]) and np.isinf(e[0, 2])


def test_cell_hours():
    m = B.blocked_cell_hours(np.array([[0.0, 61.0, np.inf]]), 3)
    assert m[:, 0, 0].tolist() == [True, True, True]
    assert m[:, 0, 1].tolist() == [False, True, True]
    assert not m[:, 0, 2].any()


def test_pm25_never_blocks():
    h = hour()
    h.pm25_ug_m3 = np.full((1, 3), 1e6)
    crit, comp, _, _ = B.criteria_by_hour([h])
    assert not B.audience_rule(crit, "residents").any()


# ---------------------------------------------------------------- graph and routing on a 3 x 1 strip
GRID = {"transform": [375.0, 0.0, 0.0, 0.0, -375.0, 375.0], "width": 3, "height": 1, "epsg": 5070}


def test_chord_segments_fractions():
    g = G.Grid(GRID["transform"], 3, 1, 5070)
    s = G.chord_segments(g, (10.0, 100.0), (760.0, 100.0))
    assert [x["cell"] for x in s] == [0, 1, 2]
    assert math.isclose(s[0]["end"], 365 / 750) and s[-1]["end"] == 1.0


def _strip_graph():
    g = G.Grid(GRID["transform"], 3, 1, 5070)
    pts = {1: (100.0, 200.0), 2: (500.0, 200.0), 3: (1000.0, 200.0)}
    nodes = [{"id": "osm:%d" % k, "x": x, "y": y, "waitable": False} for k, (x, y) in pts.items()]
    edges = []
    for a, b in ((1, 2), (2, 3)):
        L = math.dist(pts[a], pts[b])
        t = max(1, math.ceil(L / G.SPEED_M_S))
        sg = G.chord_segments(g, pts[a], pts[b])
        rs = [{"cell": s["cell"], "start": 1 - s["end"], "end": 1 - s["start"]} for s in reversed(sg)]
        rs[-1]["end"] = 1.0
        edges.append({"id": "e%d%d" % (a, b), "u": "osm:%d" % a, "v": "osm:%d" % b, "travel_ticks": t, "segments": sg})
        edges.append({"id": "e%d%d" % (b, a), "u": "osm:%d" % b, "v": "osm:%d" % a, "travel_ticks": t, "segments": rs})
    graph = {"grid": g.json(), "crs": "EPSG:5070", "nodes": nodes, "edges": edges, "forbidden_turns": []}
    origins = [{"id": "o1", "name": "", "category": "test", "entry_node_id": "osm:1", "checkable": True, "lonlat": (0, 0)}]
    exits = [{"id": "x3", "name": "map edge", "category": "map_edge_exit", "entry_node_id": "osm:3", "checkable": True,
              "lonlat": (1, 0)}]
    return g, graph, origins, exits


def _raster(tmp_path, g, values, hmin=360):
    sys.path.insert(0, str(HERE.parents[1] / "product" / "wfg-roadlayer"))
    from wfg_roadlayer import geotiff
    p = tmp_path / "r.tif"
    geotiff.write(p, np.array([values], float), g.affine, 5070, nodata=float("nan"), dtype="float32",
                  metadata={"WFG_HORIZON_MIN": hmin, "WFG_UNITS": "minutes", "WFG_ISSUE_TIME": "2024-08-23T00:00:00Z"})
    return p


def test_route_last_departure_moves_with_block(tmp_path):
    pytest.importorskip("pyproj")
    import route as R
    g, graph, origins, exits = _strip_graph()
    rows0, info0, _ = R.run(graph, origins, exits, _raster(tmp_path, g, [np.inf, np.inf, np.inf]), g)
    assert rows0[0]["refusal"] is None and rows0[0]["cut_s"] is None  # nothing blocked: no cut inside the horizon
    rows1, _, cs = R.run(graph, origins, exits, _raster(tmp_path, g, [np.inf, 60.0, np.inf]), g)
    L = rows1[0]["last_safe_departure_s"]
    assert L is not None and L < 3600 and rows1[0]["cut_s"] == L + 1
    rows2, _, _ = R.run(graph, origins, exits, _raster(tmp_path, g, [np.inf, 30.0, np.inf]), g)
    assert rows2[0]["last_safe_departure_s"] == L - 1800  # blocked 30 min earlier -> last departure 30 min earlier


def test_run_all_end_to_end(tmp_path, monkeypatch):
    """Six synthetic hours on a 4 x 2 grid; a road through both rows; exposure blocks one cell before fire."""
    pyproj = pytest.importorskip("pyproj")
    pytest.importorskip("matplotlib")
    import run_all
    x0, ytop, res = -1141125.0, 2393250.0, 375.0
    grid = {"transform": [res, 0.0, x0, 0.0, -res, ytop], "width": 4, "height": 2, "epsg": 5070}
    (tmp_path / "grid.json").write_text(json.dumps(grid))
    inv = pyproj.Transformer.from_crs("EPSG:5070", "EPSG:4326", always_xy=True)
    pts = [(x0 + 20, ytop - 190), (x0 + 100, ytop - 190), (x0 + 1400, ytop - 190), (x0 + 1700, ytop - 190),
           (x0 + 100, ytop - 600)]
    els = []
    for k, (x, y) in enumerate(pts, start=1):
        lon, lat = inv.transform(x, y)
        els.append({"type": "node", "id": k, "lon": lon, "lat": lat})
    els.append({"type": "way", "id": 10, "nodes": [1, 2, 3, 4], "tags": {"highway": "primary"}})
    els.append({"type": "way", "id": 11, "nodes": [2, 5], "tags": {"highway": "track"}})
    lon, lat = inv.transform(x0 + 120, ytop - 560)
    els.append({"type": "node", "id": 99, "lon": lon, "lat": lat, "tags": {"place": "hamlet", "name": "Test"}})
    (tmp_path / "osm.json").write_text(json.dumps({"elements": els}))
    hd = tmp_path / "hours"
    hd.mkdir()
    for h in range(6):
        p = np.zeros((2, 4))
        if h >= 2:
            p[0, 2] = 0.6  # visibility event in the middle of the road from hour 2
        np.savez(hd / ("hour_%02d.npz" % h), bin_edges_s=EDGES, p_vis=p, pm25_ug_m3=np.ones((2, 4)),
                 q_rad_kw_m2=np.zeros((K, 2, 4)), thermal_resolved=np.ones((2, 4), bool), co_mg_m3=np.zeros((K, 2, 4)))
    sys.path.insert(0, str(HERE.parents[1] / "product" / "wfg-roadlayer"))
    from wfg_roadlayer import geotiff
    fire = np.full((2, 4), np.inf)
    fire[0, 2] = 300.0  # fire reaches that cell at 5 h
    a = (res, 0.0, x0, 0.0, -res, ytop)
    geotiff.write(tmp_path / "fire.tif", fire, a, 5070, nodata=float("nan"), dtype="float32",
                  metadata={"WFG_HORIZON_MIN": 480, "WFG_UNITS": "minutes", "WFG_ISSUE_TIME": "2024-08-23T00:00:00Z"})
    monkeypatch.setenv("MPLCONFIGDIR", str(tmp_path / "mpl"))
    monkeypatch.setattr(sys, "argv", ["run_all", "--hours", str(hd), "--fire", str(tmp_path / "fire.tif"), "--grid",
                                      str(tmp_path / "grid.json"), "--osm", str(tmp_path / "osm.json"), "--out",
                                      str(tmp_path / "out"), "--workers", "1"])
    assert run_all.main() == 0
    s = json.loads((tmp_path / "out" / "summary.json").read_text())
    assert s["n_hours"] == 6 and s["n_cell_hours"] == 48
    assert s["criterion_cell_hours"]["vis_p50"] == 4 and s["criterion_cell_hours"]["vis_p90"] == 0
    assert s["fire_blocked_cell_hours"] == 1  # blocked from 300 min: hour 5 only
    assert s["added_cell_hours"]["residents_vis50"]["exposure_blocked_not_fire"] == 3
    assert s["routing"]["n_origins"] == 1 and s["routing"]["n_exits"] == 1
    o = s["origins"]["residents_vis50"]
    assert o["n_origins_routed"] == 1 and o["n_changed"] == 1 and o["earlier_by_min_largest"] > 0
    assert s["origins"]["residents_vis90"]["n_changed"] == 0
    assert (tmp_path / "out" / "fig_blocked_cells.png").is_file()
