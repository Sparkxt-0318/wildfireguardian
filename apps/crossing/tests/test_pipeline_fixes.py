"""Regression tests for the fail-safe / physics fixes FS-1, FS-2, FS-3, FS-5, FS-8, FS-9 through crossing.pipeline.

All sessions are SYNTHETIC (built by tests/test_pipeline.py::build_session); nothing here is a measurement. Every
limit exercised here is a placeholder.
"""
import copy
import dataclasses
import json
import math

import numpy as np
import pytest

from crossing import decision as dc
from crossing import pipeline as pl
from crossing.terrain import Dem

from wfgvu import protocol

from test_pipeline import (LAT0, LON0, T0_PI, UTURN, build_session, capture_at, items_of, make_pipe,
                           states_between, thermal_image)

GO = (dc.CROSS_FAST, dc.SPRAY, dc.REOPENED)


def _first(states, pred):
    return next((t for t, s in states if pred(s)), None)


# ------------------------------------------------------------------------------------------------- FS-1: gain
@pytest.mark.parametrize("gain", ["high", None])
def test_high_gain_or_missing_gain_never_builds_the_reopen_hold(tmp_path, gain):
    """FS-1 (e): the after-pass scene that gives REOPENED with low gain, but every thermal frame says gain "high"
    (TC001 high gain tops out near 150 C: no pixel can reach the 300 C flame threshold) or has no gain value. Flame
    pixels are UNKNOWN, never 0: the hold never builds and REOPENED never comes."""
    pipe = make_pipe(tmp_path)
    hello, msgs = build_session("drive_through", duration=62.0, gain=gain, **UTURN)
    states = pl.run_virtual(pipe, items_of(hello, msgs))
    assert all(s["verdict"]["state"] == dc.CLOSED for _, s in states)
    assert max(s["reopen"]["quiet_s"] for _, s in states) == 0.0
    late = states_between(states, 30.0, 62.0)
    assert late and all(s["flame"]["thermal"]["flame_pixels"] is None for _, s in late)
    assert all("SENSOR_FAULT:thermal" in s["verdict"]["reasons"] for _, s in late)
    assert all("VALUE_MISSING:flame_pixels" in s["verdict"]["reasons"] for _, s in late)


def test_high_gain_flame_front_is_never_flame_or_cross_fast(tmp_path):
    pipe = make_pipe(tmp_path)
    hello, msgs = build_session("flame_front", duration=16.0, gain="high")
    states = pl.run_virtual(pipe, items_of(hello, msgs), hooks={4.5: lambda p, now: p.capture_baseline(now, True)})
    assert all(s["flame"]["status"] != "FLAME" for _, s in states)
    assert all(s["verdict"]["state"] == dc.CLOSED for _, s in states)


def test_live_low_gain_frames_unverified_until_configured(tmp_path):
    """FS-1 (c, d): on real (non-simulated) data the gain field is only the configured value and the low-gain
    scale is unverified, so flame absence cannot be shown until thermal.low_gain_verified is set after a lab check."""
    rng = np.random.default_rng(1)
    data = protocol.encode_thermal(thermal_image(rng, False, False), gain="low")
    msg = {"data": data, "sim": False}
    pipe = make_pipe(tmp_path)
    pipe._on_thermal(msg, 10.0)
    assert pipe._th.valid and pipe._th.flame_pixels is None and "not verified" in pipe._th.flame_unknown
    assert pipe.capture_baseline(10.0)["ok"] is False
    ok = make_pipe(tmp_path / "v", thermal={"low_gain_verified": True})
    ok._on_thermal(msg, 10.0)
    assert ok._th.flame_pixels == 0 and ok._th.flame_unknown == ""
    ok._on_thermal({"data": dict(data, gain="high"), "sim": False}, 11.0)
    assert ok._th.flame_pixels is None


# ---------------------------------------------------------------------------------------- FS-2: occluded base
def test_occluded_flame_base_closes_with_near_edge_not_observed(tmp_path, monkeypatch):
    """FS-2 / PHYS-2: a flame base hidden behind terrain (geometry ``occluded``: d_m only a near bound, d_hi inf)
    is not an observed base: never CROSS FAST / SPRAY, NEAR_EDGE_NOT_OBSERVED, intensity invalid."""
    real = pl.near_edge

    def occluded(*a, **k):
        ne = real(*a, **k)
        return None if ne is None else dataclasses.replace(ne, occluded=True, d_hi_m=math.inf)

    monkeypatch.setattr(pl, "near_edge", occluded)
    pipe = make_pipe(tmp_path)
    hello, msgs = build_session("flame_front", duration=16.0)
    states = pl.run_virtual(pipe, items_of(hello, msgs), hooks=capture_at(4.5))
    assert all(s["verdict"]["state"] not in GO for _, s in states)
    late = states_between(states, 10.0, 16.0)
    assert late and all("NEAR_EDGE_NOT_OBSERVED" in s["verdict"]["reasons"] for _, s in late)
    assert all(s["intensity"]["valid"] is False for _, s in late)
    assert all("occluded" in s["geometry"]["reason"] for _, s in late)


# ----------------------------------------------------------------------------------------------- FS-3: facing
REVERSE = dict(zone_m=6.0, t_drive=8.0, turn_at_e=50.0, stop_at_e=42.0)


@pytest.mark.parametrize("speed,duration", [(0.5, 72.0), (2.5, 62.0)])
def test_reversing_away_from_the_crossing_never_reopens(tmp_path, speed, duration):
    """FS-3 (probe p3): the vehicle crosses eastwards, drives on to 50 m, REVERSES west to 42 m and stops: the
    camera still faces east, away from the crossing, while the GNSS course reads 270. The facing must not take the
    reversed course: never in view, never REOPENED."""
    pipe = make_pipe(tmp_path)
    hello, msgs = build_session("drive_through", duration=duration, reverse_speed=speed, **REVERSE)
    states = pl.run_virtual(pipe, items_of(hello, msgs))
    assert pipe.crossing_ref is not None
    assert all(s["verdict"]["state"] != dc.REOPENED for _, s in states)
    late = [s for t, s in states if t >= duration - 25.0]
    assert late and all(s["reopen"]["passed"] for s in late)
    assert all(not s["reopen"]["view"]["in_view"] for s in late)
    assert all("REOPEN_CROSSING_NOT_IN_VIEW" in s["verdict"]["reasons"] for s in late)
    v = late[-1]["reopen"]["view"]
    assert v["heading_deg"] is None or abs(((v["heading_deg"] - 90.0) + 180.0) % 360.0 - 180.0) < 1.0, v


def test_trusted_imu_heading_facing_the_crossing_allows_reopen(tmp_path):
    """FS-3 (d): the same GNSS track (course flips to 270 at 0.5 m/s) but a TRUSTED IMU heading says the vehicle
    faces west, at the crossing: the IMU wins, the crossing is in view and REOPENED is reachable."""
    pipe = make_pipe(tmp_path, mount={"imu_heading_trusted": True})
    hello, msgs = build_session("drive_through", duration=72.0, reverse_speed=0.5, imu_heading_after=(20.0, 270.0),
                                **REVERSE)
    states = pl.run_virtual(pipe, items_of(hello, msgs))
    reo = [t for t, s in states if s["verdict"]["state"] == dc.REOPENED]
    assert reo, sorted({r for _, s in states[-10:] for r in s["verdict"]["reasons"]})
    v = dict(states)[reo[0]]["reopen"]["view"]
    assert v["in_view"] and v["heading_source"] == "imu (trusted)" and abs(v["heading_deg"] - 270.0) < 1e-6


def test_gradual_u_turn_at_speed_keeps_a_valid_facing(tmp_path):
    """A U-turn driven at 4 m/s (course rotating over 2 s) is forward travel: the facing follows it (the REOPENED
    test in test_pipeline.py relies on this)."""
    pipe = make_pipe(tmp_path)
    hello, msgs = build_session("drive_through", duration=30.0, **UTURN)
    pl.run_virtual(pipe, items_of(hello, msgs))
    assert pipe.facing_valid and abs(pipe.facing_deg - 270.0) < 1e-6


# ------------------------------------------------------------------------------------ FS-8: line of sight
def test_no_dem_means_line_of_sight_unverifiable_and_never_reopened(tmp_path):
    pipe = make_pipe(tmp_path, dem=None)
    hello, msgs = build_session("drive_through", duration=62.0, **UTURN)
    states = pl.run_virtual(pipe, items_of(hello, msgs))
    assert all(s["verdict"]["state"] != dc.REOPENED for _, s in states)
    late = states_between(states, 40.0, 62.0)
    assert late and all("no DEM" in s["reopen"]["view"]["reason"] for _, s in late)
    assert max(s["reopen"]["quiet_s"] for _, s in late) == 0.0


def _ridge_dem():
    """Level SYNTHETIC DEM with a north-south ridge (+4 m) between 30 and 36 m east: from 42 m east (camera 2.6 m)
    the crossed road at 20-26 m east lies behind it."""
    e = -300.0 + (np.arange(600) + 0.5)
    z = 100.0 + np.interp(e, [0.0, 30.0, 33.0, 36.0, 300.0], [0.0, 0.0, 4.0, 0.0, 0.0])
    return Dem(z=np.tile(z.astype(np.float32), (600, 1)), x0=-300.0, y_top=300.0, res=1.0, crs="local-enu",
               lat0=LAT0, lon0=LON0)


def test_crossing_hidden_behind_a_ridge_is_not_in_view(tmp_path):
    """FS-8: facing the crossing at 16-22 m, all corners inside the FOV and range, but a 4 m ridge lies between:
    the geometry-only check said in view (and zero hot pixels = quiet). Now: hidden, never REOPENED."""
    pipe = make_pipe(tmp_path, dem=_ridge_dem())
    hello, msgs = build_session("drive_through", duration=62.0, **UTURN)
    states = pl.run_virtual(pipe, items_of(hello, msgs))
    assert all(s["verdict"]["state"] != dc.REOPENED for _, s in states)
    late = states_between(states, 40.0, 62.0)
    assert late and all(not s["reopen"]["view"]["in_view"] and "hidden" in s["reopen"]["view"]["reason"]
                        for _, s in late)


def test_view_image_check_needs_ground_temperature_at_the_patch(tmp_path):
    """FS-8 (3): with the patch in view over the DEM, pixels at its ground points reading sky-cold (or flame-hot)
    are not shown to be the road: not in view."""
    pipe = make_pipe(tmp_path)
    hello, msgs = build_session("drive_through", duration=50.0, **UTURN)
    states = pl.run_virtual(pipe, items_of(hello, msgs))
    imu_d, gnss_d = pipe.link.tracks["imu"].last_msg["data"], pipe.link.tracks["gnss"].last_msg["data"]
    pos = pipe.en(gnss_d["lat"], gnss_d["lon"])
    good = pipe._th.temps_k
    assert pipe.crossing_view(pos, 270.0, imu_d, gnss_d, good)["in_view"] is True
    for t_c in (-60.0, 400.0):
        v = pipe.crossing_view(pos, 270.0, imu_d, gnss_d, np.full_like(good, t_c + 273.15))
        assert v["in_view"] is False and "ground temperature" in v["reason"], v["reason"]
    assert pipe.crossing_view(pos, 270.0, imu_d, gnss_d, None)["in_view"] is False


# --------------------------------------------------------------------------- FS-5: replays, loops, repeated marks
def _as_real(hello, msgs):
    """The same SYNTHETIC session relabelled as a recording of REAL data (sim false), as a replayed Pi record."""
    return dict(hello, sim=False), tuple(dict(m, sim=False) for m in msgs)


def _inject(p, now):
    from crossing.depth import DepthResult
    pred = DepthResult(valid=True, depth_m=5.0, lo_m=3.0, hi_m=8.0, sigma_log=0.3, estimates=[])
    p._last_valid_depth = {"rx": now, "depth": pred, "loss_db": 1.0, "lat": LAT0, "lon": LON0}


def test_replay_loop_and_repeated_marks_never_grow_the_pairs(tmp_path):
    """FS-5 (probe p2): a replay of a recorded real session, looped (same pipeline, again and again) and replayed in
    a fresh app run, plus repeated 'mark crossing' presses: one pair in pairs_replay.jsonl, nothing in pairs.jsonl."""
    hello, msgs = _as_real(*build_session("drive_through", duration=21.0, zone_m=6.0, t_drive=8.0))
    pipe = make_pipe(tmp_path)
    pl.run_virtual(pipe, items_of(hello, msgs), hooks={7.0: _inject})
    assert pipe.sim is False and pipe.crossing["last"]["ok"], pipe.crossing["last"]
    store = tmp_path / "pairs_replay.jsonl"
    assert pipe.crossing["last"]["store"] == str(store) and not (tmp_path / "pairs.jsonl").exists()
    assert pipe.calib.n_pairs == 1
    for k in range(3):                                      # --loop: the same pipeline replays it again
        pl.run_virtual(pipe, items_of(hello, msgs), t0=2000.0 + 100.0 * k, hooks={7.0: _inject})
        assert pipe.crossing["last"]["ok"] is False and pipe.crossing["last"].get("duplicate"), pipe.crossing["last"]
    fresh = make_pipe(tmp_path)                             # a new app run replaying the same recording
    pl.run_virtual(fresh, items_of(hello, msgs), hooks={7.0: _inject})
    assert fresh.crossing["last"].get("duplicate") and fresh.calib.n_pairs == 1
    for _ in range(3):                                      # repeated presses of POST /api/mark_crossing
        r = fresh.mark_crossing(1000.0 + 21.0)
        assert r["ok"] is False and r.get("duplicate"), r
    assert len(store.read_text().splitlines()) == 1 and fresh.calib.n_pairs == 1
    assert not (tmp_path / "pairs.jsonl").exists()


def test_repeated_tape_marks_for_the_same_prediction_are_refused(tmp_path):
    pipe = make_pipe(tmp_path)
    hello, msgs = build_session("flame_front", duration=16.0)
    pl.run_virtual(pipe, items_of(hello, msgs), hooks=capture_at(4.5))
    first = pipe.mark_crossing(1000.0 + 16.0, measured_m=2.5)
    assert first["ok"]
    for _ in range(3):
        again = pipe.mark_crossing(1000.0 + 16.1, measured_m=2.5)
        assert again["ok"] is False and again.get("duplicate")
    assert pipe.calib.n_pairs == 1


# ----------------------------------------------------------------------------------------------- FS-9: IMU calib
def test_uncalibrated_imu_accel_or_gyro_is_an_imu_fault(tmp_path):
    hello, msgs = build_session("flame_front", duration=18.0)
    out = []
    for m in msgs:
        if m.get("sensor") == "imu" and m["type"] == "reading" and m["t_mono"] - T0_PI >= 14.0:
            m = copy.deepcopy(m)
            m["data"]["calib"] = {"sys": 0, "gyro": 3, "accel": 0, "mag": 0}
        out.append(m)
    pipe = make_pipe(tmp_path)
    states = pl.run_virtual(pipe, items_of(hello, out), hooks=capture_at(4.5))
    assert any(s["verdict"]["state"] == dc.CROSS_FAST for t, s in states if t < 14.0)
    post = states_between(states, 14.3, 18.0)
    assert post and all(s["verdict"]["state"] == dc.CLOSED and "SENSOR_FAULT:imu" in s["verdict"]["reasons"]
                        for _, s in post)
