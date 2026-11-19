"""Crossing app: flux-disc over-temperature (copper disc on printed PETG tabs, 70 C user-set) and the build-manual
sensor offsets (radar parallax), on SYNTHETIC sessions (tests/test_pipeline.py builder) and the committed SIMULATED
samples. Nothing here is a measurement or was run on hardware.
"""
from __future__ import annotations

import gzip
import json
import math
from pathlib import Path

import pytest

from crossing import decision as dc
from crossing import pipeline as pl
from crossing import research_log as rl
from crossing.config import load_config

from test_failsafe import good_cross, good_reopen, run as decide_run
from test_pipeline import (LAT0, LON0, T0_PI, TEST_VEHICLE, _go_window, build_session, capture_at, items_of,
                           make_pipe, states_between)

VU = Path(__file__).resolve().parents[3] / "hardware" / "vehicle-unit"
OFFSETS = {"camera": {"x": -52, "z": 34, "hole_d": 12},
           "radar": {"x": -8, "z": 34, "window_w": 52, "window_h": 42, "window_t": 1.2},
           "flux_disc": {"x": 45, "z": 34, "hole_d": 30.6}}


# ----------------------------------------------------------------------------------------------- config
def test_config_disc_limit_is_70_and_validated():
    cfg = load_config()
    assert cfg.flux.disc_max_c == 70.0 and cfg.mount.offset_x_sign == 0       # sign unconfirmed: no correction
    for ok in (40.0, 60.0, 70.0):
        assert load_config(overrides={"flux": {"disc_max_c": ok}}).flux.disc_max_c == ok
    # never above the user's 70 C (PETG tabs; the Pi caps it at 70 too)
    for bad in (39.9, 70.01, 71.0, 100.0, 120.0, float("nan"), "70", True):       # (YAML null keeps the default, as for every key)
        with pytest.raises(ValueError):
            load_config(overrides={"flux": {"disc_max_c": bad}})
    for bad in (2, 0.5, True, -2):
        with pytest.raises(ValueError):
            load_config(overrides={"mount": {"offset_x_sign": bad}})
    for ok in (-1, 0, 1):
        assert load_config(overrides={"mount": {"offset_x_sign": ok}}).mount.offset_x_sign == ok


# ----------------------------------------------------------------------------------------------- decision
@pytest.mark.parametrize("make", [good_cross, good_reopen])
def test_decision_closes_on_the_disc_fault(make):
    assert decide_run(make()).state != dc.CLOSED
    v = decide_run(make(faults={"tc_plate": "PLATE_DISC_OVER_TEMP: disc 70.00 C >= 70 C (PETG tabs at risk)"}))
    assert v.state == dc.CLOSED
    assert "PLATE_DISC_OVER_TEMP" in v.reasons and "SENSOR_FAULT:tc_plate" in v.reasons
    assert v.reasons.count("PLATE_DISC_OVER_TEMP") == 1


# ----------------------------------------------------------------------------------------------- pipeline
def plate_overlay(msgs, a, b, temp_c):
    """tc_plate readings with t_rel in [a, b) read temp_c (+-0.05 C alternating, so no value freeze)."""
    out = []
    for m in msgs:
        t_rel = m["t_mono"] - T0_PI
        if m["type"] == "reading" and m["sensor"] == "tc_plate" and a <= t_rel < b:
            m = dict(m, data=dict(m["data"], temp_c=temp_c + (0.05 if m["seq"] % 2 else -0.05) * (temp_c < 70)))
        out.append(m)
    return out


def _run(tmp_path, a, b, temp_c, rlog=None, duration=18.0):
    pipe = make_pipe(tmp_path)
    if rlog is not None:
        pipe.rlog = rlog
    hello, msgs = build_session("flame_front", duration=duration)
    states = pl.run_virtual(pipe, items_of(hello, plate_overlay(msgs, a, b, temp_c)), hooks=capture_at(4.5))
    return pipe, states


def test_pipeline_closes_at_70_0_and_recovers_below(tmp_path):
    root = tmp_path / "records"
    log = rl.ResearchLog(root, "CX-disc", info={"mode": "replay"})
    pipe, states = _run(tmp_path, 13.0, 14.5, 70.0, rlog=log)
    log.close()
    _go_window(states, 13.0)
    t_closed = next(t for t, s in states if t >= 13.0 and s["verdict"]["state"] == dc.CLOSED)
    assert t_closed - 13.0 <= 0.3, t_closed
    during = states_between(states, 13.3, 14.5)
    assert during
    for _, s in during:
        assert s["verdict"]["state"] == dc.CLOSED
        assert "PLATE_DISC_OVER_TEMP" in s["verdict"]["reasons"]
        assert s["flux"]["disc"]["over_temp"] is True and s["flux"]["disc"]["max_c"] == 70.0
        assert s["flux"]["disc"]["warning"] == "Flux disc over 70 C: PETG tabs at risk"
        assert s["flux"]["q_kw_m2"] is None and s["flux"]["valid"] is False
        assert "PLATE_DISC_OVER_TEMP" in s["flux"]["reason"]
    assert pipe.reopen.quiet_since is None or pipe.reopen.quiet_since >= 14.5   # hold never ran through it
    # recovers with the normal freshness: back below the limit -> the go verdict returns within a few ticks
    t_back = next(t for t, s in states if t >= 14.5 and s["verdict"]["state"] == dc.CROSS_FAST)
    assert t_back - 14.5 <= 1.0, t_back
    assert all(s["flux"]["disc"]["over_temp"] is False for _, s in states_between(states, 14.8, 18.0))
    # research log: reason codes in verdicts.csv, transitions in events.csv
    v = rl.read_csv(log.dir / "verdicts.csv")
    assert any("PLATE_DISC_OVER_TEMP" in (r["reasons"] or "") for r in v)
    ev = [r["kind"] for r in rl.read_csv(log.dir / "events.csv")]
    assert "disc_over_temp" in ev and "disc_over_temp_cleared" in ev


def test_pipeline_does_not_close_at_69_9(tmp_path):
    pipe, states = _run(tmp_path, 13.0, 14.5, 69.9)
    _go_window(states, 13.0)
    win = states_between(states, 13.0, 15.0)
    assert win and all(s["verdict"]["state"] == dc.CROSS_FAST for _, s in win), \
        [(t, s["verdict"]["reasons"]) for t, s in win if s["verdict"]["state"] != dc.CROSS_FAST][:2]
    assert all(s["flux"]["disc"]["over_temp"] is False for _, s in win)


@pytest.mark.parametrize("parity", [0, 1])
def test_pipeline_closes_on_alternating_70_5_69_5(tmp_path, parity):
    """tc_plate at 10 Hz, ticks at 5 Hz: readings alternating 70.5 / 69.5 C must close EVERY tick whatever the
    phase of readings against ticks (an over-limit reading between two ticks is latched by the reading handler)."""
    def overlay(msgs):
        out = []
        for m in msgs:
            t_rel = m["t_mono"] - T0_PI
            if m["type"] == "reading" and m["sensor"] == "tc_plate" and 13.0 <= t_rel < 16.0:
                m = dict(m, data=dict(m["data"], temp_c=70.5 if (m["seq"] + parity) % 2 else 69.5))
            out.append(m)
        return out
    pipe = make_pipe(tmp_path)
    hello, msgs = build_session("flame_front", duration=16.0)
    states = pl.run_virtual(pipe, items_of(hello, overlay(msgs)), hooks=capture_at(4.5))
    win = states_between(states, 13.3, 16.0)
    assert win
    for _, s in win:
        assert s["verdict"]["state"] == dc.CLOSED, s["verdict"]
        assert "PLATE_DISC_OVER_TEMP" in s["verdict"]["reasons"]
        assert s["flux"]["disc"]["over_temp"] is True and s["flux"]["disc"]["over_c"] == 70.5
    assert pipe.reopen.quiet_since is None or pipe.reopen.quiet_since >= 15.9


def test_pipeline_disc_limit_follows_config(tmp_path):
    pipe = make_pipe(tmp_path, flux={"disc_max_c": 60.0})
    hello, msgs = build_session("flame_front", duration=16.0)
    states = pl.run_virtual(pipe, items_of(hello, plate_overlay(msgs, 13.0, 16.0, 65.0)), hooks=capture_at(4.5))
    late = states_between(states, 13.4, 16.0)
    assert late and all("PLATE_DISC_OVER_TEMP" in s["verdict"]["reasons"] for _, s in late)
    assert late[-1][1]["flux"]["disc"]["warning"] == "Flux disc over 60 C: PETG tabs at risk"


def test_crossing_with_hot_disc_gives_no_calibration_pair(tmp_path):
    """drive_through (zone 20-26 m east at 4 m/s: pulse from about 13 s): the disc reads 75 C from 13.5 to 15.5 s.
    No pair is stored; the far edge for REOPENED is still recorded, never before the true zone end (26 m): the pulse
    is held open while the disc is hot (flux sample times are window centres, 1.1 s behind the readings)."""
    from crossing.depth import DepthResult
    pipe = make_pipe(tmp_path)
    hello, msgs = build_session("drive_through", duration=22.0, zone_m=6.0, t_drive=8.0)
    pred = DepthResult(valid=True, depth_m=5.0, lo_m=3.0, hi_m=8.0, sigma_log=0.3, estimates=[])

    def inject(p, now):
        p._last_valid_depth = {"rx": now, "depth": pred, "loss_db": 1.0, "lat": LAT0, "lon": LON0}

    pl.run_virtual(pipe, items_of(hello, plate_overlay(msgs, 13.5, 15.5, 75.0)), hooks={7.0: inject})
    last = pipe.crossing["last"]
    assert last and last["ok"] is False and last.get("disc_over_temp") is True, last
    assert "PLATE_DISC_OVER_TEMP" in last["reason"]
    assert pipe.calib.n_pairs == 0 and not (tmp_path / "pairs_sim.jsonl").exists()
    fe = pipe.far_edge_ref
    assert fe is not None and "disc over limit" in fe["kind"]
    assert fe["t_pi"] >= T0_PI + 15.5 - pipe.cfg.flux_window_s / 2 - 0.2      # held until the disc cooled
    assert fe["pos"][0] >= 26.0 - 0.3                                          # not inside the zone (20-26 m)


def test_committed_samples_never_reach_70c():
    """The committed SIMULATED samples peak far below the disc limit, so no committed verdict can change."""
    samples = sorted(p for p in (VU / "samples").glob("*") if (p / "tc_plate.jsonl.gz").exists())
    if not samples:
        pytest.skip("no committed samples")
    peak = -1e9
    for d in samples:
        for f in sorted(d.glob("tc_plate*.jsonl.gz")):
            with gzip.open(f, "rt") as fh:
                for line in fh:
                    m = json.loads(line)
                    if m.get("type") == "reading" and isinstance(m["data"].get("temp_c"), (int, float)):
                        peak = max(peak, float(m["data"]["temp_c"]))
    assert peak < 60.0, peak
    print("committed samples: tc_plate peak %.2f C (limit 70 C)" % peak)


# ----------------------------------------------------------------------------------------------- sensor offsets
def test_offsets_absent_are_zero_and_present_give_the_parallax(tmp_path):
    # default offset_x_sign 0 (sign UNCONFIRMED): offsets present, but no lateral correction (flip-insensitive)
    unconf = make_pipe(tmp_path / "u")
    unconf._apply_sensor_offsets({"sensor_offsets_mm": OFFSETS}, "test")
    assert unconf.sensor_parallax_deg(10.0) == 0.0 and unconf.sensor_offsets["correction_applied"] is False
    assert unconf.sensor_offsets["camera_radar_dx_abs_m"] == pytest.approx(0.044)
    assert unconf.radar_height_m == unconf.cfg.mount.camera_height_m
    pipe = make_pipe(tmp_path, mount={"offset_x_sign": 1})
    assert pipe.sensor_offsets["present"] is False and pipe.sensor_parallax_deg(10.0) == 0.0
    assert pipe.radar_height_m == pipe.cfg.mount.radar_height_m
    pipe._apply_sensor_offsets({"sensor_offsets_mm": OFFSETS}, "test")
    assert pipe.sensor_offsets["correction_applied"] is True
    p10 = pipe.sensor_parallax_deg(10.0)
    assert p10 == pytest.approx(-math.degrees(math.atan(0.044 / 10.0)))          # -0.252 deg
    assert abs(p10) < 0.26 and abs(pipe.sensor_parallax_deg(2.5)) == pytest.approx(1.008, abs=0.01)
    assert pipe.radar_height_m == pipe.cfg.mount.camera_height_m                  # same 34 mm line
    assert pipe.sensor_offsets["sign_confirmed"] is False
    flipped = make_pipe(tmp_path / "f", mount={"offset_x_sign": -1})
    flipped._apply_sensor_offsets({"sensor_offsets_mm": OFFSETS}, "test")
    assert flipped.sensor_parallax_deg(10.0) == pytest.approx(-p10)
    # a later hello without offsets (old session) resets them to 0
    pipe._apply_sensor_offsets({"camera_pitch_deg": -18.0}, "old hello")
    assert pipe.sensor_parallax_deg(10.0) == 0.0


@pytest.mark.parametrize("sign", [1, 0, -1])
def test_offsets_in_hello_do_not_change_the_flame_front_verdicts(tmp_path, sign):
    """The parallax (0.25 deg at 10 m) is a tenth of the 2.5 deg baseline-beam tolerance: with either sign the
    synthetic flame front gives the same verdict sequence as without offsets."""
    hello, msgs = build_session("flame_front", duration=16.0)
    base = pl.run_virtual(make_pipe(tmp_path / "a"), items_of(hello, msgs), hooks=capture_at(4.5))
    h2 = dict(hello, mount=dict(hello["mount"], sensor_offsets_mm=OFFSETS))
    pipe = make_pipe(tmp_path / "b", mount={"offset_x_sign": sign})
    with_off = pl.run_virtual(pipe, items_of(h2, msgs), hooks=capture_at(4.5))
    assert [s["verdict"]["state"] for _, s in base] == [s["verdict"]["state"] for _, s in with_off]
    so = with_off[-1][1]["geometry"]["sensor_offsets"]
    assert so["present"] is True and so["camera_x_mm"] == -52 and so["radar_x_mm"] == -8
    assert so["flux_disc_x_mm"] == 45 and so["offset_x_sign"] == sign
    assert so["parallax_deg"] == pytest.approx(-sign * math.degrees(math.atan2(0.044, so["parallax_at_m"])))
    assert so["parallax_abs_deg"] == pytest.approx(math.degrees(math.atan2(0.044, so["parallax_at_m"])))
    assert so["correction_applied"] is (sign != 0)
    assert with_off[-1][1]["geometry"]["camera"]["fov_note"] == "P2 Pro FOV UNVERIFIED (vendor 56 deg)"
    assert "InfiRay P2 Pro" in with_off[-1][1]["geometry"]["camera"]["model"]
