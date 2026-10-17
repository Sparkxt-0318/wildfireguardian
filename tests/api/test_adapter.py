"""spread_zones adapter unit tests on a synthetic grid (no recorded data needed), plus one packet build on recorded data."""
import json
import math
from types import SimpleNamespace

import numpy as np
import pytest

from api.adapters import spread_zones as SZ
from api.errors import APIError

from .conftest import INPUTS, needs_data

RES = 375.0
GRID = {"x0": 0.0, "y0": 0.0, "resolution": RES, "width": 8, "height": 6}
T = 3970.4642815249267


def to_xy(lon, lat):
    """Synthetic projection: 1 degree = 1000 m, so lon/lat stay valid WGS84 numbers."""
    return np.asarray(lon, dtype=float) * 1000.0, np.asarray(lat, dtype=float) * 1000.0


def deg(m):
    return m / 1000.0


def rect(x0, y0, x1, y1, h):
    lo0, la0, lo1, la1 = deg(x0), deg(y0), deg(x1), deg(y1)
    return {"type": "Feature", "properties": {"arrival_h_max": h},
            "geometry": {"type": "Polygon", "coordinates": [[[lo0, la0], [lo1, la0], [lo1, la1], [lo0, la1], [lo0, la0]]]}}


def run(features, *, issued="2023-04-02T07:00:00Z", margin=None, present=None):
    region = SimpleNamespace(id="synthetic", graph=SimpleNamespace(grid=GRID, bbox=(0, 0, 1, 1)))
    sset = SimpleNamespace(time_origin="2023-04-02T07:00:00+00:00", scenario_set_id="ffb1:20230402T070000Z:synthetic",
                           tag="20230402T070000Z", packet_dir="/nonexistent", event_id="KFS_X")
    fi = {"type": "spread_zones", "issued_at": issued, "zones": {"type": "FeatureCollection", "features": features}}
    if margin is not None:
        fi["margin_min"] = margin
    pf = np.zeros((GRID["height"], GRID["width"]), bool) if present is None else present
    return SZ.plan(region=region, sset=sset, fire_input=fi, to_5179=to_xy, horizon_s=3600.0, active_duration_s=T,
                   present_fire=pf, window=None)


def cell_rc(x, y):
    """native north-up (row, col) of the cell containing projected point (x, y)."""
    return GRID["height"] - 1 - int(y // RES), int(x // RES)


def test_nested_zones_take_the_innermost_band():
    inner = rect(375, 375, 1125, 1125, 0.5)      # cells c1..c2, south rows 1..2
    outer = rect(0, 0, 1875, 1875, 2.0)
    p = run([inner, outer], issued="2023-04-02T06:45:00Z")   # zones issued 15 min before input_time
    t = np.array(p["times"])
    r, c = cell_rc(750, 750)
    # innermost band (0, 0.5 h]: earliest = max(0, 0 - 1 h) = 0 h -> -900 s on the packet clock -> clamped to 0
    assert t[0, r, c] == 0.0
    # later offsets at 1/3, 2/3, 1 of the band, minus the 15 min issue offset (600 s - 900 s clamps to 0)
    assert t[1, r, c] == 0.0
    assert t[2, r, c] == pytest.approx(0.5 * 2 / 3 * 3600 - 900)
    assert t[3, r, c] == pytest.approx(0.5 * 3600 - 900)
    # a cell only in the outer band (0.5 h, 2 h]: earliest = max(0, 0.5 - 1) = 0 h -> clamped; later offsets 1.0, 1.5, 2.0 h
    r2, c2 = cell_rc(1700, 1700)
    assert t[0, r2, c2] == 0.0 and t[1, r2, c2] == pytest.approx(3600 - 900)
    assert math.isinf(t[2, r2, c2]) and math.isinf(t[3, r2, c2])         # 4500 s and 6300 s are beyond the 1 h horizon
    # boundary-only contact does not claim the neighbouring cells of the inner zone
    assert math.isinf(t[3, cell_rc(200, 750)[0], cell_rc(200, 750)[1]]) or t[0, cell_rc(200, 750)[0], cell_rc(200, 750)[1]] == 0.0
    bands = p["assumptions"]["bands_detail"]
    assert [b["arrival_h_max"] for b in bands] == [0.5, 2.0] and [b["h_prev"] for b in bands] == [0.0, 0.5]
    assert p["assumptions"]["label"] == "approximation, requires expert review"
    # cells outside every zone never ignite
    r3, c3 = cell_rc(2800, 1900)
    assert all(math.isinf(t[k, r3, c3]) for k in range(4))


def test_empty_zones_give_no_ignitions():
    p = run([])
    assert np.isinf(np.array(p["times"])).all()
    assert p["assumptions"]["cells_in_zones"] == 0 and p["assumptions"]["bands_detail"] == []


def test_zone_outside_region_is_rejected():
    with pytest.raises(APIError) as e:
        run([rect(50_000, 50_000, 51_000, 51_000, 5)])
    assert e.value.status == 422 and e.value.code == "ZONES_OUTSIDE_REGION"


def test_margin_parameter_moves_the_earliest_scenario_only():
    zones = [rect(375, 375, 1125, 1125, 0.25), rect(0, 0, 1875, 1875, 0.75)]
    r, c = cell_rc(1700, 1700)          # outer band (0.25 h, 0.75 h]
    t60 = np.array(run(zones)["times"])
    t0 = np.array(run(zones, margin=0)["times"])
    t5 = np.array(run(zones, margin=5)["times"])
    assert t60[0, r, c] == 0.0                         # max(0, 0.25 h - 60 min)
    assert t0[0, r, c] == pytest.approx(0.25 * 3600)   # no margin: starts at H_prev
    assert t5[0, r, c] == pytest.approx(0.25 * 3600 - 300)
    for k in (1, 2, 3):                                # later scenarios are margin independent
        assert t60[k, r, c] == t0[k, r, c] == t5[k, r, c]
    assert t60[3, r, c] == pytest.approx(0.75 * 3600)
    assert run(zones, margin=0)["assumptions"]["margin_min"] == 0


def test_conservative_rasterization_marks_touched_cells():
    tiny = rect(400, 400, 410, 410, 0.5)                 # 10 m square inside one cell, missing its centre
    t = np.array(run([tiny])["times"])
    assert np.isfinite(t[0]).sum() == 1 and np.isfinite(t[0, cell_rc(405, 405)[0], cell_rc(405, 405)[1]])


def test_present_fire_cells_stay_as_recorded():
    present = np.zeros((GRID["height"], GRID["width"]), bool)
    r, c = cell_rc(750, 750)
    present[r, c] = True
    p = run([rect(375, 375, 1125, 1125, 0.5)], present=present)
    t = np.array(p["times"])
    assert np.isinf(t[:, r, c]).all()
    assert p["assumptions"]["bands_detail"][0]["present_fire_cells_kept_as_recorded"] == 1


def test_times_after_horizon_stay_unignited_and_echoed():
    p = run([rect(375, 375, 1125, 1125, 6)])
    t = np.array(p["times"])
    assert np.isfinite(t[0]).any() and np.isinf(t[1:]).all()   # 2 h, 4 h, 6 h are beyond the 1 h horizon
    assert p["assumptions"]["clock"]["beyond_horizon_cell_scenarios"] > 0


@pytest.mark.parametrize("bad", [
    {"type": "Feature", "properties": {"arrival_h_max": 0}, "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}},
    {"type": "Feature", "properties": {"arrival_h_max": 5}, "geometry": {"type": "Point", "coordinates": [0, 0]}},
    {"type": "Feature", "properties": {}, "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}},
    {"type": "Feature", "properties": {"arrival_h_max": 5}, "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0]]]}},
])
def test_invalid_zones_are_rejected(bad):
    with pytest.raises(APIError) as e:
        run([bad])
    assert e.value.status == 422 and e.value.code == "INVALID_ZONES"


@needs_data
def test_packet_build_on_recorded_export(tmp_path):
    """The child process writes a packet with the unchanged writer: new scenario ids, the plan's ignitions, recorded fire."""
    import sys
    from api.regions import Registry, to_5179
    from api.config import load_settings, Settings
    s = load_settings()
    reg = Registry(Settings(data_root=INPUTS.parent, runtime_dir=tmp_path, workers=1, python=s.python, host=s.host, port=s.port)).load()
    region = reg.regions["hongseong_2023"]
    sset = region.scenario_sets["20230402T230000Z"]
    md = json.loads((sset.packet_dir / "NATIVE_METADATA.json").read_text())
    with np.load(sset.packet_dir / "constructed_arrays.npz") as z:
        present = z["current_active"].copy()
    zone = {"type": "Feature", "properties": {"arrival_h_max": 5},
            "geometry": {"type": "Polygon", "coordinates": [[[126.49, 36.55], [126.51, 36.55], [126.51, 36.57], [126.49, 36.57], [126.49, 36.55]]]}}
    fi = {"type": "spread_zones", "issued_at": "2023-04-02T23:00:00Z", "zones": {"type": "FeatureCollection", "features": [zone]}}
    plan = SZ.plan(region=region, sset=sset, fire_input=fi, to_5179=to_5179, horizon_s=sset.horizon_s,
                   active_duration_s=md["construction"]["assumptions"]["burning_duration_s"], present_fire=present,
                   window=md["regional"]["window_rows_cols_north_up"])
    out, meta = SZ.build_packet(plan, graph_path=region.graph_path, out_dir=tmp_path / "packet", python=sys.executable)
    with np.load(out / "constructed_arrays.npz") as z:
        assert np.array_equal(z["ignition_time_s"], np.array(plan["times"]))
        assert np.array_equal(z["current_active"], present)
    hz = json.loads((out / "HAZARD.json").read_text())
    ids = [m["id"] for m in hz["members"]]
    assert ids == meta["scenario_ids"] and not set(ids) & set(sset.scenario_ids)
    nm = json.loads((out / "NATIVE_METADATA.json").read_text())
    assert nm["settings"]["zone_adapter"]["plan_sha256"] == plan["plan_sha256"]
    assert meta["ignitions_per_member"][0] > 0


def test_unrelated_zone_does_not_shift_another_fires_band():
    """Fire A (nested 0.5 h / 2 h) plus an unrelated fire B (0.25 h): A's innermost cells keep H_prev = 0."""
    fire_a = [rect(375, 375, 1125, 1125, 0.5), rect(0, 0, 1875, 1875, 2.0)]
    fire_b = [rect(2625, 1875, 3000, 2250, 0.25)]
    alone = np.array(run(fire_a)["times"])
    both = run(fire_a + fire_b)
    t = np.array(both["times"])
    r, c = cell_rc(750, 750)
    assert t[0, r, c] == alone[0, r, c] == 0.0 and t[3, r, c] == alone[3, r, c]
    bands = {(b["arrival_h_max"], b["h_prev"]) for b in both["assumptions"]["bands_detail"]}
    assert bands == {(0.25, 0.0), (0.5, 0.0), (2.0, 0.5)}


def test_issued_after_input_time_keeps_the_margin():
    """Product issued 30 min after input_time: innermost cells may already burn at input_time (floor on packet clock)."""
    p = run([rect(375, 375, 1125, 1125, 5)], issued="2023-04-02T07:30:00Z")
    t = np.array(p["times"])
    r, c = cell_rc(750, 750)
    assert t[0, r, c] == 0.0                                    # 1800 s + (0 - 60 min) -> -1800 s -> 0
    assert p["assumptions"]["cells_igniting_within_horizon"] > 0


def test_zone_igniting_only_after_horizon_is_reported():
    p = run([rect(375, 375, 1125, 1125, 2.0), rect(0, 0, 1875, 1875, 8.0)])
    # outer band (2 h, 8 h]: earliest 1 h -> exactly the horizon -> unignited; innermost band still ignites at 0
    assert p["assumptions"]["cells_igniting_within_horizon"] == 4


def test_malformed_multipolygon_is_422():
    bad = {"type": "Feature", "properties": {"arrival_h_max": 5}, "geometry": {"type": "MultiPolygon", "coordinates": [5]}}
    with pytest.raises(APIError) as e:
        run([bad])
    assert e.value.status == 422 and e.value.code == "INVALID_ZONES"


def test_three_concentric_bands_take_the_next_edge_in():
    """0.5 h inside 1 h inside 2 h (one fire): the 2 h band starts at 1 h, not at the innermost 0.5 h."""
    p = run([rect(375, 375, 1125, 1125, 0.5), rect(0, 0, 1500, 1500, 1.0), rect(0, 0, 1875, 1875, 2.0)])
    bands = {(b["arrival_h_max"], b["h_prev"]) for b in p["assumptions"]["bands_detail"]}
    assert bands == {(0.5, 0.0), (1.0, 0.5), (2.0, 1.0)}


def test_zone_beside_the_inner_zone_does_not_raise_h_prev():
    """Fire A (0.5 h inside 2 h) plus a 1 h zone lying inside A's 2 h band beside A's 0.5 h zone (no fire ids).

    The 1 h zone adds a second outermost nested zone of the 2 h zone; H_prev of the 2 h band stays 0.5 h (not 1 h), so
    the band cells outside it ignite exactly as with fire A alone.
    """
    fire_a = [rect(375, 375, 1125, 1125, 0.5), rect(0, 0, 1875, 1875, 2.0)]
    fire_b = [rect(1500, 1500, 1875, 1875, 1.0)]
    alone = np.array(run(fire_a)["times"])
    both = run(fire_a + fire_b)
    t = np.array(both["times"])
    r, c = cell_rc(200, 200)                    # in A's 2 h band, outside A's 0.5 h zone and outside B
    assert np.array_equal(t[:, r, c], alone[:, r, c], equal_nan=True)
    bands = {(b["arrival_h_max"], b["h_prev"]) for b in both["assumptions"]["bands_detail"]}
    assert bands == {(0.5, 0.0), (1.0, 0.0), (2.0, 0.5)}


def test_plan_digest_covers_adapter_version_and_ignition_times(monkeypatch):
    zones = [rect(375, 375, 1125, 1125, 0.5), rect(0, 0, 1875, 1875, 2.0)]
    p = run(zones)
    t = np.array(p["times"], dtype="<f8")
    import hashlib
    assert p["assumptions"]["ignition_times_sha256"] == hashlib.sha256(t.tobytes()).hexdigest()
    assert p["assumptions"]["plan_sha256"] == p["plan_sha256"]
    monkeypatch.setattr(SZ, "ADAPTER_VERSION", SZ.ADAPTER_VERSION + "-test")
    assert run(zones)["plan_sha256"] != p["plan_sha256"]


def test_too_many_zones_is_422():
    with pytest.raises(APIError) as e:
        run([rect(0, 0, 375, 375, 1.0)] * (SZ.MAX_ZONES + 1))
    assert e.value.status == 422 and e.value.code == "INVALID_ZONES"


def fire(f, fire_id):
    f = json.loads(json.dumps(f))
    f["properties"]["fire_id"] = fire_id
    return f


def test_zone_cut_off_by_the_grid_edge_is_never_nested():
    """A 2 h zone that mostly lies east of the grid only shows its western tip inside a 4 h zone: it is not nested."""
    a = [rect(1500, 0, 3000, 2250, 4.0)]
    b = [rect(2600, 750, 9000, 1500, 2.0)]                 # grid is x 0..3000 m
    alone, both = run(a), run(a + b)
    r, c = cell_rc(1700, 2000)                             # in the 4 h zone, outside the 2 h zone
    assert np.array_equal(np.array(both["times"])[:, r, c], np.array(alone["times"])[:, r, c])
    assert np.array(alone["times"])[0, r, c] == 0.0
    assert both["assumptions"]["zones_cut_off_by_grid_edge"] == [1]
    assert {(x["arrival_h_max"], x["h_prev"]) for x in both["assumptions"]["bands_detail"]} == {(2.0, 0.0), (4.0, 0.0)}


def test_fire_id_keeps_a_contained_zone_of_another_fire_out_of_the_band():
    """A single 4 h zone (fire A) with a 2 h zone inside it.

    As one fire (no ids) the 2 h zone is A's inner band, so the 4 h band starts at 2 h (the band rule). With different
    fire ids the 4 h zone keeps H_prev 0, exactly as fire A alone.
    """
    a = rect(0, 0, 3000, 2250, 4.0)
    b = rect(1125, 750, 1875, 1500, 2.0)
    r, c = cell_rc(200, 200)                               # in A, outside B
    alone = np.array(run([a])["times"])
    one_fire = run([a, b])
    assert {(x["arrival_h_max"], x["h_prev"]) for x in one_fire["assumptions"]["bands_detail"]} == {(2.0, 0.0), (4.0, 2.0)}
    two = run([fire(a, "A"), fire(b, "B")])
    assert np.array_equal(np.array(two["times"])[:, r, c], alone[:, r, c])
    assert two["assumptions"]["fire_ids"] == ["A", "B"]
    assert {(x["arrival_h_max"], x["h_prev"]) for x in two["assumptions"]["bands_detail"]} == {(2.0, 0.0), (4.0, 0.0)}


def test_cell_takes_the_smallest_h_prev_of_every_zone_touching_it():
    """Fire A (1.5 h inside 2 h) and fire K (one 3 h zone) overlap: the overlap cell may ignite from 0, as K alone says."""
    a = [fire(rect(0, 0, 750, 750, 1.5), "A"), fire(rect(0, 0, 2250, 2250, 2.0), "A")]
    k = [fire(rect(1500, 1500, 3000, 2250, 3.0), "K")]
    r, c = cell_rc(1900, 1900)
    t_k, t_a, t = (np.array(run(z)["times"])[:, r, c] for z in (k, a, a + k))
    assert t[0] == 0.0
    assert np.all(t <= t_k) and np.all(t <= t_a)


def test_adding_another_fire_never_delays_any_ignition(monkeypatch):
    """Property check on random rectangles: with a distinct fire_id per fire, A+B ignites every cell no later than A or B."""
    monkeypatch.setattr(SZ, "_densify", lambda ring, step=None: ring)   # straight edges under the synthetic projection
    rng = np.random.default_rng(20261017)
    for trial in range(600):
        fires = []
        for name in ("A", "B"):
            zs = []
            for _ in range(int(rng.integers(1, 4))):
                x0, y0 = rng.uniform(-600, 2800), rng.uniform(-600, 2100)
                w, hgt = rng.uniform(200, 2400), rng.uniform(200, 1800)
                zs.append(fire(rect(x0, y0, x0 + w, y0 + hgt, float(rng.choice([0.25, 0.5, 1.0, 1.5, 2.0, 3.0]))), name))
            fires.append(zs)
        a, b = fires
        try:
            ta, tb, tab = (np.array(run(z)["times"]) for z in (a, b, a + b))
        except APIError:                                   # a random zone may miss the grid entirely
            continue
        assert np.all(tab <= ta) and np.all(tab <= tb), trial


def test_invalid_fire_id_is_422():
    bad = rect(375, 375, 1125, 1125, 1.0)
    bad["properties"]["fire_id"] = 7
    with pytest.raises(APIError) as e:
        run([bad])
    assert e.value.status == 422 and e.value.code == "INVALID_ZONES"
