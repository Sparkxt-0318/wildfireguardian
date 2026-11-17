"""End-to-end tests of crossing.pipeline on SYNTHETIC sessions (not measurements).

Sessions are built here message by message (``build_session``) with the wire protocol of wfgvu.protocol, because
``wfgvu.synth`` and ``hardware/vehicle-unit/samples/`` may not exist yet. When they do exist, the tests at the end
also run every sample / synth scenario through the pipeline and check the scenario-independent rules (smoke never
FLAME / CROSS FAST; a failure overlay forces CLOSED).

Illustrative synthetic physics (stated, not verified):
- Scene: vehicle stopped on a flat road (GNSS speed 0, IMU level). Camera 2.6 m above the road, pinhole P2 Pro model.
  A flame front across the road at ``near_m`` (default 10 m) with height ``flame_h`` (1.5 m): pixels whose rays meet
  the ground at >= near_m and lie below the flame top read 800 K; background 293 K + 0.3 K noise; road below the
  horizon 300 K.
- ``spread_m_s``: the front advances towards the stopped vehicle at this rate after it appears.
- Smoke: a warm plume over the upper image, peak < 110 C (no flame-temperature pixels), no radar effect at all.
- Radar: 128 bins x 0.2 m, 4-element lambda/2 array. Static reflectors at 6 m (in front of the flame) and 18 m
  (behind it) at boresight, complex Gaussian noise. Flame effect on echoes beyond the near edge only: 1.5 dB loss,
  0.5 dB amplitude flicker and a phase random walk of 0.4 rad per frame.
- Plate: copper plate warming slowly (about 1 kW/m2 net) from 20 C; tc_air 25 C; tc_housing 30 C (+ noise).
- ``drive_through`` scenario: the vehicle drives east at 4 m/s through a flame zone of thickness ``zone_m`` (20 m
  to 20 + zone_m east of the start): plate temperature integrates q = 40 kW/m2 while inside and 0.3 kW/m2 elsewhere
  (thin-skin energy balance with h = 10 W/m2K). No flame in the camera image. Options: ``turn_at_e`` the vehicle
  turns round there and drives back west (course 270) until ``stop_at_e`` (facing the crossed road); ``stop_at_e``
  alone: it stops there still facing east (crossing behind it). ``hot_after=(t, bearing_deg)``: from t a small
  800 K patch (flame-temperature pixels) on the ground just below the horizon at that camera bearing.
- Overlays (as in DESIGN 4): ``fail=(sensor, T)`` the sensor stops (no readings, no heartbeats from T);
  ``freeze=(sensor, T)`` its data repeats byte for byte from T; ``fault=(tc_sensor, T, kind)`` MAX31855 fault.
"""
import functools
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from crossing import decision as dc
from crossing import pipeline as pl
from crossing.config import load_config
from crossing.radar_flame import DEFAULT_ARRAY
from crossing.thermal import CameraModel
from crossing.vehicles import from_mapping

from wfgvu import protocol

T0_PI = 5000.0
CAM = CameraModel()
CAM_H = 2.6
N_BINS, RES, N_ANT = 128, 0.2, 4
LAT0, LON0 = 37.5, 128.9

# Test-only vehicle: the dose limit is set absurdly high ON PURPOSE so that the synthetic flame gives CROSS FAST and
# the failure overlays have a go state to close. It says nothing about any real vehicle.
TEST_VEHICLE = from_mapping("test_only", {
    "label": "TEST ONLY (absurd dose limit)", "length_m": 5.0, "width_m": 2.0, "height_m": 2.0,
    "sensor_height_m": 2.6, "max_safe_speed_m_s": 10.0, "dose_limit_tdu": 1.0e6, "intake_air_limit_c": 80.0,
    "has_water": False, "placeholder": True})


def _utc(t):
    s = 1763374500.0 + (t - T0_PI)
    return protocol.utc_now_iso(s)


class Builder:
    def __init__(self, ctx):
        self.ctx = ctx
        self.msgs = []
        self.seq = {}
        self.hb_seq = {}

    def reading(self, sensor, t, data):
        n = self.seq.get(sensor, 0)
        self.seq[sensor] = n + 1
        self.msgs.append(self.ctx.make("reading", sensor=sensor, seq=n, data=data, t_mono=t, t_utc=_utc(t)))

    def heartbeat(self, sensor, t, status="ok", detail="", rate=None):
        n = self.hb_seq.get(sensor, 0)
        self.hb_seq[sensor] = n + 1
        last = self.seq.get(sensor)
        self.msgs.append(self.ctx.make("heartbeat", sensor=sensor, status=status, detail=detail,
                                       last_reading_seq=None if last is None else last - 1, rate_hz=rate, seq=n,
                                       t_mono=t, t_utc=_utc(t)))


def thermal_image(rng, flame, smoke, near_m=10.0, flame_h=1.5, half_width_deg=15.0, hot_bearing=None):
    img = (293.15 + rng.normal(0.0, 0.3, (CAM.h, CAM.w))).astype(np.float32)
    rows = np.arange(CAM.h)[:, None].astype(float)
    cols = np.arange(CAM.w)[None, :].astype(float)
    below = rows > CAM.ppy + 0.5
    img[np.broadcast_to(below, img.shape)] += 7.0
    if smoke:
        yy, xx = np.mgrid[0:CAM.h, 0:CAM.w]
        img += (80.0 * np.exp(-((xx - 128) ** 2 / 4000.0 + (yy - 60) ** 2 / 1200.0))).astype(np.float32)
    if flame:
        tan_down = (rows - CAM.ppy) / CAM.fy                      # tan of depression angle of each row
        with np.errstate(divide="ignore"):
            d_ground = np.where(tan_down > 0, CAM_H / np.maximum(tan_down, 1e-9), np.inf)
        top_tan = (CAM_H - flame_h) / near_m                       # rows below the flame top at the near edge
        in_rows = (tan_down >= top_tan) & (d_ground >= near_m)
        bearing = np.degrees(np.arctan((cols - CAM.ppx) / CAM.fx))
        in_cols = np.abs(bearing) <= half_width_deg
        m = in_rows & in_cols
        img[m] = 800.0 + rng.normal(0.0, 5.0, int(m.sum()))
    if hot_bearing is not None:
        c = int(round(CAM.bearing_to_col(hot_bearing)))
        r = int(round(CAM.ppy)) + 12
        img[r:r + 3, c - 1:c + 2] = 800.0
    return img


class Radar:
    def __init__(self, seed):
        rng = np.random.default_rng(seed)
        self.rng = np.random.default_rng(seed + 1)
        self.targets = [(6.0, 0.0, 1500.0, rng.uniform(-np.pi, np.pi)), (18.0, 0.0, 3000.0, rng.uniform(-np.pi, np.pi))]
        self.psi = 0.0

    def iq(self, flame, near_m=10.0):
        x = np.zeros((N_BINS, N_ANT), complex)
        if flame:
            self.psi += self.rng.normal(0.0, 0.4)
        for r, b, a, ph in self.targets:
            g = 1.0
            if flame and r > near_m:
                ldb = 1.5 + self.rng.normal(0.0, 0.5)
                g = 10 ** (-ldb / 20.0) * np.exp(1j * self.psi)
            sv = DEFAULT_ARRAY.steering(b, N_ANT)
            b0 = int(round(r / RES))
            for db, w in ((-1, 0.3), (0, 1.0), (1, 0.3)):
                x[b0 + db] += a * w * g * np.exp(1j * ph) * sv
        x += (self.rng.normal(0, 15.0, x.shape) + 1j * self.rng.normal(0, 15.0, x.shape))
        return x


def build_session(scenario="flame_front", duration=20.0, seed=0, t_flame=6.0, fail=None, freeze=None, fault=None,
                  near_m=10.0, flame_h=1.5, zone_m=6.0, t_drive=8.0, spread_m_s=0.0, turn_at_e=None, stop_at_e=None,
                  hot_after=None, gain="low", reverse_speed=None, imu_heading_after=None):
    """Return (hello, [messages]) of one SYNTHETIC session (see module docstring). Messages are sorted by t_mono.
    The clean session is cached (generation dominates test time); overlays are applied to a copy.

    gain: the thermal ``gain`` field ("low" default; FS-1: "high" / None can never show flame absence).
    turn_at_e: a U-turn at 4 m/s whose GNSS course rotates 90 -> 270 deg over 2 s (lateral offset of the turn
    ignored: lat stays constant; stated simplification). reverse_speed: instead of turning, the vehicle REVERSES
    west from turn_at_e at this speed (GNSS course flips to 270 at once, the camera still faces east).
    imu_heading_after=(t, deg): IMU heading from t (default 90, east)."""
    hello, msgs = _base_session(scenario, float(duration), seed, t_flame, near_m, flame_h, zone_m, t_drive,
                                spread_m_s, turn_at_e, stop_at_e, hot_after, gain, reverse_speed, imu_heading_after)
    return hello, apply_overlays(msgs, fail, freeze, fault)


def apply_overlays(msgs, fail=None, freeze=None, fault=None):
    """DESIGN 4 failure overlays on a message list (messages are not mutated):
    fail=(sensor, T) drops its readings and heartbeats from T; freeze=(sensor, T) repeats the last data before T;
    fault=(tc_sensor, T, kind) MAX31855 fault from T (reading temp_c null + fault, heartbeat status error)."""
    out, last, frozen = [], {}, {}
    for m in msgs:
        t_rel = m["t_mono"] - T0_PI
        s = m.get("sensor")
        if fail and s == fail[0] and t_rel >= fail[1] - 1e-9:
            continue
        if m["type"] == "reading":
            if freeze and s == freeze[0] and t_rel >= freeze[1] - 1e-9:
                frozen.setdefault(s, last.get(s, m["data"]))
                m = dict(m, data=frozen[s])
            if fault and s == fault[0] and t_rel >= fault[1] - 1e-9:
                m = dict(m, data=dict(m["data"], temp_c=None, fault=fault[2]))
            last[s] = m["data"]
        elif m["type"] == "heartbeat" and fault and s == fault[0] and t_rel >= fault[1] - 1e-9:
            m = dict(m, status="error", detail="fault %s" % fault[2])
        out.append(m)
    return out


@functools.lru_cache(maxsize=8)
def _base_session(scenario, duration, seed, t_flame, near_m, flame_h, zone_m, t_drive, spread_m_s, turn_at_e=None,
                  stop_at_e=None, hot_after=None, gain="low", reverse_speed=None, imu_heading_after=None):
    rng = np.random.default_rng(seed)
    ctx = protocol.Context("VU-SYN", "VU-SYN-%s-%d" % (scenario, seed), sim=True)
    b = Builder(ctx)
    radar = Radar(seed + 100)
    plate_c = 20.0
    pos_e = 0.0
    direction = 1.0                                  # +1 east, -1 west (after the turn)
    stopped = False
    turn_t0 = None                                   # U-turn in progress since (t_rel)
    TURN_S = 2.0
    dt_tc = 0.1
    hb_period = 0.5
    sensors = ("thermal", "radar", "tc_plate", "tc_housing", "tc_air", "imu", "gnss", "pi")
    rates = {"thermal": 4.0, "radar": 10.0, "tc_plate": 10.0, "tc_housing": 10.0, "tc_air": 10.0, "imu": 20.0,
             "gnss": 5.0, "pi": 1.0}
    n_steps = int(round(duration / 0.05))
    for k in range(n_steps + 1):
        t_rel = k * 0.05
        t = T0_PI + t_rel
        flame_on = scenario == "flame_front" and t_rel >= t_flame
        near_now = near_m - spread_m_s * max(0.0, t_rel - t_flame)      # front advancing towards the vehicle
        smoke_on = scenario == "smoke_only" or scenario == "flame_front"
        if scenario == "drive_through" and t_rel >= t_drive and not stopped:
            if turn_at_e is not None and direction > 0 and pos_e >= turn_at_e and turn_t0 is None:
                if reverse_speed is not None:
                    direction = -1.0                 # reversing: course flips, the camera keeps facing east
                else:
                    turn_t0 = t_rel                  # gradual U-turn (course rotates over TURN_S)
            if turn_t0 is not None and direction > 0 and t_rel - turn_t0 >= TURN_S:
                direction = -1.0
            if stop_at_e is not None and ((turn_at_e is None and pos_e >= stop_at_e)
                                          or (turn_at_e is not None and direction < 0 and pos_e <= stop_at_e)):
                stopped = True
        moving = scenario == "drive_through" and t_rel >= t_drive and not stopped
        speed = 4.0 if moving else 0.0
        turning = moving and turn_t0 is not None and direction > 0
        course_now = 90.0 if direction > 0 else 270.0
        if turning:
            course_now = 90.0 + 180.0 * min(1.0, (t_rel - turn_t0) / TURN_S)
        if moving and direction < 0 and reverse_speed is not None:
            speed = float(reverse_speed)
        if moving:
            pos_e += (speed * math.sin(math.radians(course_now)) if turning else direction * speed) * 0.05
        # plate energy balance (thin skin), q in kW/m2
        q = 1.0 if scenario != "drive_through" else 0.3
        if scenario == "drive_through" and moving and 20.0 <= pos_e <= 20.0 + zone_m:
            q = 40.0
        loss = 10.0 * (plate_c - 20.0)
        plate_c += (q * 1000.0 * 0.95 - loss) * 0.05 / (8960.0 * 385.0 * 0.001)

        def due(sensor):
            p = 1.0 / rates[sensor]
            return abs((t_rel / p) - round(t_rel / p)) < 1e-6

        for s in sensors:
            if due(s):
                if s == "thermal":
                    hot = hot_after[1] if hot_after is not None and t_rel >= hot_after[0] else None
                    data = protocol.encode_thermal(thermal_image(rng, flame_on, smoke_on and scenario != "drive_through",
                                                                 near_now, flame_h, hot_bearing=hot), gain="low")
                    data["gain"] = gain
                elif s == "radar":
                    data = {"frame": b.seq.get("radar", 0), "range_res_m": RES, "n_bins": N_BINS,
                            "range_profile_db": None, "az_heatmap": protocol.encode_iq(radar.iq(flame_on, near_now)),
                            "points": None, "tlv_types": [4], "frame_ok": True}
                elif s == "tc_plate":
                    data = {"temp_c": round(plate_c + rng.normal(0, 0.05), 2), "cj_c": round(25.0 + rng.normal(0, 0.05), 4),
                            "fault": None}
                elif s == "tc_housing":
                    data = {"temp_c": round(30.0 + rng.normal(0, 0.1), 2), "cj_c": 25.0 + rng.normal(0, 0.05),
                            "fault": None}
                elif s == "tc_air":
                    data = {"temp_c": round(25.0 + rng.normal(0, 0.1), 2), "cj_c": 25.0 + rng.normal(0, 0.05),
                            "fault": None}
                elif s == "imu":
                    hd = imu_heading_after[1] if imu_heading_after and t_rel >= imu_heading_after[0] else 90.0
                    data = {"roll_deg": rng.normal(0, 0.05), "pitch_deg": rng.normal(0, 0.05), "heading_deg": hd,
                            "grav": [0.0, 0.0, 9.81], "calib": {"sys": 3, "gyro": 3, "accel": 3, "mag": 3}}
                elif s == "gnss":
                    lat = LAT0 + rng.normal(0, 2e-7)
                    lon = LON0 + pos_e / (6371008.8 * math.cos(math.radians(LAT0))) * 180.0 / math.pi
                    data = {"fix": 1, "lat": lat, "lon": lon, "alt_m": 100.0,
                            "speed_m_s": speed + abs(rng.normal(0, 0.02)),
                            "course_deg": course_now if moving else None,
                            "hdop": 0.9, "sats": 9, "utc": _utc(t)[:-5] + "Z"}
                else:
                    data = {"cpu_c": 55.0 + rng.normal(0, 0.2), "throttled_hex": "0x0", "under_voltage_now": False,
                            "under_voltage_ever": False, "input_v": None, "disk_free_mb": 20000.0,
                            "rec_bytes": int(1000 * t_rel)}
                b.reading(s, t, data)
            if abs((t_rel / hb_period) - round(t_rel / hb_period)) < 1e-6:
                b.heartbeat(s, t, "ok", "", rates[s])
        if abs((t_rel / hb_period) - round(t_rel / hb_period)) < 1e-6:
            b.heartbeat("unit", t, "ok", "1 client")
    hello = ctx.make("hello", sensors=list(sensors), version="synthetic", config_digest="0" * 16, t_mono=T0_PI,
                     t_utc=_utc(T0_PI), mount={"camera_height_m": CAM_H, "camera_pitch_deg": 0.0})
    b.msgs.sort(key=lambda m: m["t_mono"])
    return hello, tuple(b.msgs)


def items_of(hello, msgs, latency=0.02):
    """Virtual receipt: every message arrives ``latency`` s after its Pi time (relative to the session start)."""
    yield 0.0, "link", (True, "synthetic")
    yield 0.0, "msg", hello
    for m in msgs:
        yield m["t_mono"] - T0_PI + latency, "msg", m


@functools.lru_cache(maxsize=1)
def flat_dem():
    """Level SYNTHETIC DEM (local-enu, +-300 m around the scene): FS-8 needs a DEM to show line of sight."""
    from crossing.terrain import Dem
    return Dem(z=np.full((600, 600), 100.0, np.float32), x0=-300.0, y_top=300.0, res=1.0, crs="local-enu",
               lat0=LAT0, lon0=LON0)


def make_pipe(tmp_path, vehicle=TEST_VEHICLE, dem="flat", mode="replay", **over):
    cfg = load_config(overrides={"paths": {"records_dir": str(tmp_path),
                                           "pairs_path": str(tmp_path / "pairs.jsonl"),
                                           "sim_pairs_path": str(tmp_path / "pairs_sim.jsonl"),
                                           "replay_pairs_path": str(tmp_path / "pairs_replay.jsonl")}, **over})
    return pl.Pipeline(cfg, vehicle, "DEFAULT", dem=flat_dem() if dem == "flat" else dem, mode=mode,
                       source="synthetic")


def capture_at(t):
    def hook(pipe, now):
        res = pipe.capture_baseline(now)
        assert res["ok"], res
    return {t: hook}


def run(tmp_path, scenario="flame_front", baseline_t=4.5, tail_s=0.0, **kw):
    pipe = make_pipe(tmp_path)
    hello, msgs = build_session(scenario, **kw)
    states = pl.run_virtual(pipe, items_of(hello, msgs), tail_s=tail_s,
                            hooks=capture_at(baseline_t) if baseline_t is not None else None)
    return pipe, states


def states_between(states, a, b):
    return [(t, s) for t, s in states if a <= t < b]


# ----------------------------------------------------------------------------------------------- tests
def _first(states, pred):
    return next((t for t, s in states if pred(s)), None)


def test_flame_front_gives_flame_and_cross_fast(tmp_path):
    pipe, states = run(tmp_path, duration=16.0)
    before = states_between(states, 0.0, 6.0)
    assert all(s["verdict"]["state"] == dc.CLOSED for _, s in before)
    assert all(s["flame"]["status"] != "FLAME" for _, s in before)
    # D4: CROSS FAST only after FLAME has held min_flame_evidence_s (3.0 s) continuously. (FLAME itself needs the
    # radar effect to persist first: radar_flame.py, owned elsewhere; about 2 s after onset in this build.)
    t_flame = _first(states, lambda s: s["flame"]["status"] == "FLAME")
    t_cross = _first(states, lambda s: s["verdict"]["state"] == dc.CROSS_FAST)
    assert t_flame is not None and t_cross is not None and t_flame <= 9.0, (t_flame, t_cross)
    assert all(s["flame"]["status"] == "FLAME" for _, s in states_between(states, t_flame, 16.0))
    assert 3.0 - 1e-6 <= t_cross - t_flame <= 3.0 + 0.2 + 1e-6, (t_flame, t_cross)
    early = states_between(states, t_flame, t_cross)
    assert early and all("FLAME_EVIDENCE_TOO_SHORT" in s["verdict"]["reasons"] for _, s in early)
    after = states_between(states, t_cross, 16.0)
    assert all(s["verdict"]["state"] == dc.CROSS_FAST for _, s in after), after[0][1]["verdict"]["reasons"]
    s = after[-1][1]
    assert s["sim"] is True
    assert s["flame"]["held_s"] >= 3.0 and s["geometry"]["base_cut_off"] is False
    assert abs(s["geometry"]["near_edge_m"] - 10.0) < 0.6
    assert s["geometry"]["slope_source"] == "imu"
    assert 1.2 < s["geometry"]["flame_height_m"] < 1.8
    assert s["geometry"]["far_echo_m"] > s["geometry"]["near_edge_m"]
    assert s["depth"]["valid"] and s["depth"]["lo_m"] <= s["depth"]["depth_m"] <= s["depth"]["hi_m"]
    assert s["intensity"]["valid"]
    assert s["heat"]["valid"] and s["heat"]["label"].startswith("FDS C064 reference")
    assert len(s["flame"]["radar"]["per_bin"]["range_m"]) <= 128
    assert s["verdict"]["placeholder"] is True
    pl.state_json(s)                                         # JSON-safe (no NaN)


def test_spread_rate_estimator_on_an_advancing_front(tmp_path):
    pipe, states = run(tmp_path, duration=16.0, spread_m_s=0.2)
    est = {e["name"]: e for e in states[-1][1]["depth"]["estimators"]}
    a = est["spread_burn"]
    assert a["valid"], a["reason"]
    assert a["details"]["frame"] == "vehicle"
    assert abs(a["details"]["spread_m_s"] - 0.2) < 0.04             # pixel quantisation of the near edge
    assert "spread_burn" in states[-1][1]["depth"]["used"]
    assert abs(a["value_m"] - a["details"]["spread_m_s"] * pipe.fuel.residence_s) < 1e-6


def test_smoke_only_never_flame_or_cross_fast(tmp_path):
    pipe, states = run(tmp_path, scenario="smoke_only", duration=20.0)
    assert states
    assert all(s["flame"]["status"] != "FLAME" for _, s in states)
    assert all(s["verdict"]["state"] == dc.CLOSED for _, s in states)
    late = states_between(states, 8.0, 20.0)
    assert all(s["flame"]["radar"]["status"] == "NO_EFFECT" for _, s in late)   # baseline present, smoke invisible
    assert all(s["flame"]["thermal"]["flame_pixels"] == 0 for _, s in late)


def test_min_flame_evidence_is_configurable(tmp_path):
    """D4: min_flame_evidence_s holds CROSS FAST back for that long of continuous FLAME (the build without the rule
    gave CROSS FAST 0.38 s after flame onset). FS-4: it can be raised (5 s here) but not set below 3.0 s."""
    pipe = make_pipe(tmp_path, decision={"min_flame_evidence_s": 5.0})
    hello, msgs = build_session("flame_front", duration=16.0)
    states = pl.run_virtual(pipe, items_of(hello, msgs), hooks=capture_at(4.5))
    t_flame = _first(states, lambda s: s["flame"]["status"] == "FLAME")
    t_cross = _first(states, lambda s: s["verdict"]["state"] == dc.CROSS_FAST)
    assert t_cross is not None and 5.0 - 1e-6 <= t_cross - t_flame <= 5.2 + 1e-6
    with pytest.raises(ValueError):
        make_pipe(tmp_path / "zero", decision={"min_flame_evidence_s": 0.0})


def _go_window(states, t_fault):
    """States from the first CROSS FAST up to the fault; asserts there is a go state to close (>= 0.6 s of it)."""
    t_cross = _first(states, lambda s: s["verdict"]["state"] == dc.CROSS_FAST)
    assert t_cross is not None and t_cross <= t_fault - 0.6, (t_cross, t_fault)
    pre = states_between(states, t_cross, t_fault)
    assert pre and all(s["verdict"]["state"] == dc.CROSS_FAST for _, s in pre)
    return pre


@pytest.mark.parametrize("sensor", ["thermal", "radar", "tc_plate", "tc_air", "tc_housing", "imu", "gnss", "pi"])
def test_failure_overlay_closes_within_2s(tmp_path, sensor):
    t_fail = 14.0
    pipe, states = run(tmp_path, duration=20.0, fail=(sensor, t_fail))
    _go_window(states, t_fail)
    post = states_between(states, t_fail + 2.0, 20.0)
    assert post and all(s["verdict"]["state"] == dc.CLOSED for _, s in post), \
        [(t, s["verdict"]["state"]) for t, s in post if s["verdict"]["state"] != dc.CLOSED][:3]
    first_closed = min(t for t, s in states if t >= t_fail and s["verdict"]["state"] == dc.CLOSED)
    assert first_closed - t_fail <= 2.0


@pytest.mark.parametrize("sensor", ["imu", "tc_plate", "tc_air", "tc_housing", "gnss"])
def test_frozen_overlay_closes_after_freeze_s(tmp_path, sensor):
    """Value freeze with seq / t_mono still advancing (the synth --freeze kind) on sensors whose values can repeat
    legitimately: caught after their long freeze_s window (imu 2.0 s, tc_* / gnss 5.0 s). Documented: NOT within
    the 2 s test D criterion; a Pi-side freeze (repeated seq / t_mono) is caught at once (test below)."""
    t_fz = 13.0
    pipe, states = run(tmp_path, duration=20.0, freeze=(sensor, t_fz))
    _go_window(states, t_fz)
    fz = pipe.cfg.link.freeze_s[sensor]
    post = states_between(states, t_fz + fz + 0.3, 20.0)
    assert post and all(s["verdict"]["state"] == dc.CLOSED for _, s in post)
    assert any("frozen" in (s["health"]["sensors"][sensor]["reason"] or "") for _, s in post)


def _freeze_latency(tmp_path, sensor, t_fz, latency):
    pipe = make_pipe(tmp_path)
    hello, msgs = build_session("flame_front", duration=16.0, freeze=(sensor, t_fz))
    states = pl.run_virtual(pipe, items_of(hello, msgs, latency=latency), hooks=capture_at(4.5))
    _go_window(states, t_fz)
    t_closed = _first([(t, s) for t, s in states if t >= t_fz], lambda s: s["verdict"]["state"] == dc.CLOSED)
    st = dict(states)[t_closed]
    assert "frozen" in st["health"]["sensors"][sensor]["reason"], st["health"]["sensors"][sensor]
    assert "SENSOR_NOT_FRESH:%s" % sensor in st["verdict"]["reasons"]
    assert all(s["verdict"]["state"] == dc.CLOSED for t, s in states if t >= t_closed)
    return t_closed - t_fz


@pytest.mark.parametrize("sensor", ["thermal", "radar"])
def test_value_freeze_closes_within_1p5s_worst_case(tmp_path, sensor):
    """D2b: identical thermal pixels / radar IQ (seq and t_mono still advancing, exactly what wfgvu.synth --freeze
    and field test D's thermal_freeze produce) reach CLOSED <= 1.5 s after the fault at the laptop. Swept over the
    phase of the fault within a frame period and the phase of the 5 Hz tick (Wi-Fi latency 0.02-0.17 s)."""
    lat = []
    for k, t_fz in enumerate((13.0, 13.05, 13.1, 13.15, 13.2)):
        for j, latency in enumerate((0.02, 0.07, 0.12, 0.17)):
            lat.append(_freeze_latency(tmp_path / ("%d_%d" % (k, j)), sensor, t_fz, latency))
    print("value freeze %s: fault -> CLOSED latency min %.2f max %.2f s (n = %d)" % (sensor, min(lat), max(lat),
                                                                                       len(lat)))
    assert max(lat) <= 1.5, lat
    assert min(lat) > 0.0


def test_pi_side_freeze_repeated_seq_closes_at_once(tmp_path):
    """D2a: a Pi stream that re-sends its last reading unchanged (same seq and t_mono: a stuck driver or server)
    is not fresh from the first repeat, also for a thermocouple (whose VALUE window is 5 s)."""
    hello, msgs = build_session("flame_front", duration=16.0)
    out, last_good = [], None
    for m in msgs:
        if m.get("sensor") == "tc_plate" and m["type"] == "reading":
            if m["t_mono"] - T0_PI >= 13.0:
                out.append((m["t_mono"], last_good))          # identical message re-sent at the normal times
                continue
            last_good = m
        out.append((m["t_mono"], m))
    items = [(0.0, "link", (True, "synthetic")), (0.0, "msg", hello)] + [(t - T0_PI + 0.02, "msg", m)
                                                                        for t, m in out]
    pipe = make_pipe(tmp_path)
    states = pl.run_virtual(pipe, items, hooks=capture_at(4.5))
    _go_window(states, 13.0)
    t_closed = _first([(t, s) for t, s in states if t >= 13.0], lambda s: s["verdict"]["state"] == dc.CLOSED)
    assert t_closed - 13.0 <= 0.5, t_closed
    st = dict(states)[t_closed]
    assert "frozen on the Pi" in st["health"]["sensors"]["tc_plate"]["reason"]
    assert all(s["verdict"]["state"] == dc.CLOSED for t, s in states if t >= t_closed)


def test_thermocouple_fault_closes(tmp_path):
    pipe, states = run(tmp_path, duration=16.0, fault=("tc_air", 10.0, "open"))
    post = states_between(states, 10.3, 16.0)
    assert post and all(s["verdict"]["state"] == dc.CLOSED for _, s in post)


def test_link_loss_marks_everything_stale_at_once(tmp_path):
    pipe = make_pipe(tmp_path)
    hello, msgs = build_session("flame_front", duration=16.0)
    items = [it for it in items_of(hello, msgs) if it[0] < 13.0]
    items.append((13.0, "link", (False, "test: socket closed")))
    states = pl.run_virtual(pipe, items, tail_s=1.0, hooks=capture_at(4.5))
    _go_window(states, 13.0)
    post = states_between(states, 13.0, 14.0)
    assert post
    for _, s in post:
        assert s["verdict"]["state"] == dc.CLOSED and "LINK_DOWN" in s["verdict"]["reasons"]
        assert all(not h["fresh"] for h in s["health"]["sensors"].values())


def test_no_baseline_means_radar_unknown_and_closed(tmp_path):
    pipe, states = run(tmp_path, baseline_t=None, duration=16.0)
    for _, s in states:
        assert s["flame"]["radar"]["status"] == "UNKNOWN"
        assert s["flame"]["status"] != "FLAME"
        assert s["verdict"]["state"] == dc.CLOSED


def test_baseline_refused_with_flame_in_view(tmp_path):
    pipe, states = run(tmp_path, baseline_t=None, duration=16.0)
    res = pipe.capture_baseline(1000.0 + 16.05)
    assert res["ok"] is False and "flame" in res["reason"]


def test_snapshot_expires_verdict_without_ticks(tmp_path):
    pipe, states = run(tmp_path, duration=16.0)
    assert pipe.state["verdict"]["state"] == dc.CROSS_FAST
    last = 1000.0 + states[-1][0]
    assert pipe.snapshot(last + 4.9)["verdict"]["state"] == dc.CROSS_FAST
    snap = pipe.snapshot(last + 5.01)
    assert snap["verdict"]["state"] == dc.CLOSED and "VERDICT_EXPIRED" in snap["verdict"]["reasons"]


def test_garbage_and_malformed_messages_are_counted_not_fatal(tmp_path):
    pipe = make_pipe(tmp_path)
    pipe.set_connected(True, 1.0, "test")
    assert pipe.on_text("{not json", 1.0) is None
    assert pipe.on_text('{"v":1,"type":"reading","x":NaN}', 1.0) is None
    pipe.feed({"v": 1, "type": "reading"}, 1.0)
    assert pipe.link.parse_errors == 3
    st = pipe.tick(1.2)
    assert st["verdict"]["state"] == dc.CLOSED


def test_drive_through_stores_auto_pair_in_sim_store(tmp_path):
    pipe = make_pipe(tmp_path)
    hello, msgs = build_session("drive_through", duration=21.0, zone_m=6.0, t_drive=8.0)
    pipe._last_valid_depth = None
    # a prediction must exist before the pulse: inject one valid depth (the drive-through scene has no flame image)
    from crossing.depth import DepthResult
    pred = DepthResult(valid=True, depth_m=5.0, lo_m=3.0, hi_m=8.0, sigma_log=0.3, estimates=[])

    def inject(p, now):
        p._last_valid_depth = {"rx": now, "depth": pred, "loss_db": 1.0, "lat": LAT0, "lon": LON0}

    pl.run_virtual(pipe, items_of(hello, msgs), hooks={7.0: inject})
    last = pipe.crossing["last"]
    assert last and last["ok"], last
    # measure_thickness counts the time the ESTIMATED flux is above 5 kW/m2. The 1 s derivative window of the
    # flux estimator smears the 40 kW/m2 top hat, so the measured thickness is biased high by up to about one
    # window x speed (4 m here); calibrate.py documents this bias (conservative: wider intervals).
    assert 6.0 <= last["measured_m"] <= 6.0 + 4.0 * 1.0
    assert last["sim"] is True
    assert Path(last["store"]) == tmp_path / "pairs_sim.jsonl"
    assert not (tmp_path / "pairs.jsonl").exists()            # real store untouched by simulated data
    assert pipe.calib.n_pairs == 1


UTURN = dict(zone_m=6.0, t_drive=8.0, turn_at_e=50.0, stop_at_e=42.0)   # drive through, turn round, face it


def test_reopened_after_pass_facing_the_crossing_then_failure_closes(tmp_path):
    """D3: the vehicle crosses the zone (20-26 m east), turns round at 50 m, drives back and stops at 42 m FACING
    the crossed road (12-22 m ahead, in the camera view); quiet for the 30 s hold -> REOPENED; thermal fails -> CLOSED."""
    from crossing.simlink import SimLink
    pipe = make_pipe(tmp_path)
    pipe.simlink = Recorder(SimLink("test-region"))
    hello, msgs = build_session("drive_through", duration=62.0, fail=("thermal", 58.0), **UTURN)
    states = pl.run_virtual(pipe, items_of(hello, msgs))
    assert pipe.far_edge_ref is not None and pipe.crossing_ref is not None
    reo = [t for t, s in states if s["verdict"]["state"] == dc.REOPENED]
    assert reo, [s["verdict"]["reasons"] for t, s in states[-30:-25]]
    first = reo[0]
    s_first = dict(states)[first]
    assert s_first["reopen"]["passed"] and s_first["reopen"]["quiet_s"] >= 30.0
    v = s_first["reopen"]["view"]
    assert v["in_view"] is True and v["hot_pixels"] == 0 and v["heading_source"].startswith("gnss course")
    assert abs(v["heading_deg"] - 270.0) < 1e-6 and v["d_far_m"] <= 40.0
    assert all(s["verdict"]["state"] != dc.REOPENED for t, s in states if t < first)
    # before the turn (driving away after the crossing) the crossing was not in view
    away = states_between(states, 15.5, 20.0)
    assert away and all(not s["reopen"]["view"]["in_view"] for _, s in away)
    assert all(s["verdict"]["state"] == dc.CLOSED for t, s in states if t >= 58.0 + 2.0)
    # R9-01: this scene never measured a flame it judged uncrossable (no flame image), so nothing was closed by this
    # link: the startup CLOSED, the crossing, the REOPENED and the CLOSED after the failure send nothing
    assert pipe.simlink.sent == []


def test_passed_but_facing_away_never_reopens(tmp_path):
    """D3: same crossing, but the vehicle stops 24 m past the zone still facing away (course held at 90 deg). The
    burnt crossing is behind the camera, so 'no hot pixels' says nothing about it: never REOPENED."""
    pipe = make_pipe(tmp_path)
    hello, msgs = build_session("drive_through", duration=62.0, zone_m=6.0, t_drive=8.0, stop_at_e=50.0)
    states = pl.run_virtual(pipe, items_of(hello, msgs))
    assert pipe.crossing_ref is not None
    late = states_between(states, 25.0, 62.0)
    assert late and all(s["reopen"]["passed"] for _, s in late)
    assert all(s["verdict"]["state"] == dc.CLOSED for _, s in states)
    assert all("REOPEN_CROSSING_NOT_IN_VIEW" in s["verdict"]["reasons"] for _, s in late)
    v = late[-1][1]["reopen"]["view"]
    assert v["in_view"] is False and "outside the view" in v["reason"] and "Face the crossed road" in v["hint"]
    assert late[-1][1]["reopen"]["quiet_s"] == 0.0


def test_facing_the_crossing_with_a_hot_column_over_it_stays_closed(tmp_path):
    """D3: facing the crossing (as in the REOPENED test) but flame-temperature pixels appear on the crossed road
    (camera bearing 0, in the crossing's image columns) from 30 s: the hold never completes, never REOPENED."""
    pipe = make_pipe(tmp_path)
    hello, msgs = build_session("drive_through", duration=62.0, hot_after=(30.0, 0.0), **UTURN)
    states = pl.run_virtual(pipe, items_of(hello, msgs))
    assert all(s["verdict"]["state"] == dc.CLOSED for _, s in states)
    late = states_between(states, 31.0, 62.0)
    assert late and all(s["reopen"]["view"]["in_view"] and s["reopen"]["view"]["hot_pixels"] > 0 for _, s in late)
    assert all("CROSSING_HOT_PIXELS_PRESENT" in s["verdict"]["reasons"] for _, s in late)
    assert max(s["reopen"]["quiet_s"] for _, s in late) == 0.0


class Recorder:
    """Wraps a SimLink like SimLinkClient.offer, keeping what would be sent."""

    def __init__(self, link):
        self.link, self.sent, self.evidence = link, [], []

    def set_ids(self, unit_id, session_id):
        self.link.unit_id, self.link.session_id = unit_id or "u", session_id or "s"

    def offer(self, verdict, position=None):
        m = self.link.outgoing(verdict, position)
        if m is not None:
            self.sent.append(m)
        return m

    def offer_tick(self, evidence):
        self.evidence.append(evidence)
        o = self.link.step(evidence)
        if o is not None:
            self.sent.append(o.message)
        return o.message if o is not None else None

    def status(self):
        return {"enabled": True, "sent": len(self.sent)}


def test_simlink_flame_front_over_limit_sends_one_closed_at_the_flame(tmp_path):
    """R9-01 through the pipeline: a stationary fire engine (placeholder limits) facing the flame front decides CLOSED
    DOSE_OVER_LIMIT. With a known GNSS course (injected: the synthetic scene never moves) the pipeline records the
    flame location and exactly one CLOSED leaves the app, at that flame location (not the vehicle position); the
    startup CLOSEDs and every later CLOSED of the same flame send nothing."""
    from crossing import simlink as sl
    from crossing.vehicles import get_vehicle
    pipe = make_pipe(tmp_path, vehicle=get_vehicle("fire_engine"))
    pipe.simlink = Recorder(sl.SimLink("test-region"))
    hello, msgs = build_session("flame_front", duration=20.0)

    def course(p, now):
        p.course_deg = 90.0
        p.facing_deg, p.facing_valid = 90.0, True      # FS-3: the flame location follows the camera facing

    hooks = dict(capture_at(4.5))
    hooks[1.0] = course
    states = pl.run_virtual(pipe, items_of(hello, msgs), hooks=hooks)
    over = [s for _, s in states if "DOSE_OVER_LIMIT" in s["verdict"]["reasons"]]
    assert over, sorted({r for _, s in states for r in s["verdict"]["reasons"]})
    assert [m["event"] for m in pipe.simlink.sent] == [dc.CLOSED]
    m = pipe.simlink.sent[0]
    veh = pipe.simlink.evidence[-1]
    fr = pipe.flame_ref
    exp = sl.en_to_latlon(pipe.origin, fr["pos"][0], fr["pos"][1])
    assert abs(m["lat"] - exp["lat"]) < 1e-4 and abs(m["lon"] - exp["lon"]) < 1e-4      # within ~10 m
    gnss_lat, gnss_lon = pipe.origin
    assert sl.distance_m(m, {"lat": gnss_lat, "lon": gnss_lon}) > 3.0       # not where the vehicle stands
    assert veh.sim is True and veh.mode == "replay"


def test_simlink_without_a_course_sends_nothing(tmp_path):
    """No GNSS course (stationary from the start, IMU heading not trusted): no flame location, so nothing is sent
    even for DOSE_OVER_LIMIT (no fallback to the vehicle position)."""
    from crossing import simlink as sl
    from crossing.vehicles import get_vehicle
    pipe = make_pipe(tmp_path, vehicle=get_vehicle("fire_engine"))
    pipe.simlink = Recorder(sl.SimLink("test-region"))
    hello, msgs = build_session("flame_front", duration=20.0)
    states = pl.run_virtual(pipe, items_of(hello, msgs), hooks=capture_at(4.5))
    assert any("DOSE_OVER_LIMIT" in s["verdict"]["reasons"] for _, s in states)
    assert pipe.flame_ref is None and pipe.simlink.sent == []


def test_simlink_smoke_only_sends_nothing(tmp_path):
    from crossing import simlink as sl
    pipe = make_pipe(tmp_path)
    pipe.simlink = Recorder(sl.SimLink("test-region"))
    hello, msgs = build_session("smoke_only", duration=20.0)
    pl.run_virtual(pipe, items_of(hello, msgs), hooks={1.0: lambda p, now: setattr(p, "course_deg", 90.0),
                                                       4.5: lambda p, now: p.capture_baseline(now)})
    assert pipe.simlink.sent == []


def test_manual_mark_crossing_with_measured_value(tmp_path):
    pipe, states = run(tmp_path, duration=16.0)
    res = pipe.mark_crossing(1000.0 + 16.0, measured_m=2.5)
    assert res["ok"] and res["source"] == "manual" and res["measured_m"] == 2.5
    assert pipe.calib.n_pairs == 1
    bad = pipe.mark_crossing(1000.0 + 16.0, measured_m=-1)
    assert bad["ok"] is False


# ----------------------------------------------------------------------------------------------- samples / synth
VU = Path(__file__).resolve().parents[3] / "hardware" / "vehicle-unit"


def _external_sessions(tmp_path_factory):
    """(name, dir) of committed samples, or sessions generated with wfgvu.synth when it exists."""
    samples = VU / "samples"
    out = [(p.name, p) for p in sorted(samples.glob("*")) if p.is_dir() and list(p.glob("*.jsonl.gz"))]
    if out:
        return out
    if (VU / "wfgvu" / "synth.py").exists():
        base = tmp_path_factory.mktemp("synth")
        jobs = []
        for scen, extra in (("smoke_only", []), ("flame_front", ["--fail", "tc_plate@10"])):
            d = base / scen
            cmd = [sys.executable, "-m", "wfgvu.synth", scen, str(d), "--seed", "1", "--duration", "16"] + extra
            jobs.append((scen + ("_fail" if extra else ""), d, subprocess.Popen(
                cmd, cwd=str(VU), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)))
        for name, d, proc in jobs:
            if proc.wait(timeout=120) == 0 and list(d.glob("*.jsonl.gz")):
                out.append((name, d))
    return out


def test_external_sessions_smoke_and_failures(tmp_path, tmp_path_factory):
    sessions = _external_sessions(tmp_path_factory)
    if not sessions:
        pytest.skip("no hardware/vehicle-unit/samples and no wfgvu.synth yet")
    for name, d in sessions:
        pipe = make_pipe(tmp_path / name)
        states = pl.run_virtual(pipe, pl.iter_source(d), tail_s=3.0,
                                hooks={3.0: lambda p, now: p.capture_baseline(now)})
        assert states, name
        if "smoke" in name:
            assert all(s["flame"]["status"] != "FLAME" for _, s in states), name
            assert all(s["verdict"]["state"] == dc.CLOSED for _, s in states), name
        # after the last message every sensor goes stale: CLOSED within 2 s of stream end
        end = states[-1][0]
        assert all(s["verdict"]["state"] == dc.CLOSED for t, s in states if t >= end - 1.0), name


@pytest.mark.parametrize("name,limit_s", [("flame_front_freeze_thermal", 1.5), ("flame_front_fail_radar", 2.0)])
def test_committed_fault_samples_close_in_time(tmp_path, name, limit_s):
    """SIMULATED committed samples (wfgvu.synth, fault at 20 s): replayed with the TEST-ONLY vehicle so there is a
    CROSS FAST to close; the fault-attributed CLOSED must come within 1.5 s (value freeze) / 2.0 s (sensor stops)."""
    d = VU / "samples" / name
    if not (d / "session.json").exists():
        pytest.skip("no committed %s sample" % name)
    from wfgvu import replay
    info = json.loads((d / "session.json").read_text())
    ov = info["truth"]["overlays"][0]
    off = info["truth"]["t_mono_at_t0"] - replay.load(d).t0
    t_fault = ov["t_s"] + off                                   # relative replay time of the fault
    pipe = make_pipe(tmp_path)
    states = pl.run_virtual(pipe, pl.iter_source(d), hooks={7.0 + off: lambda p, now: p.capture_baseline(now)})
    _go_window(states, t_fault)
    hit = [(t, s) for t, s in states if t >= t_fault and s["verdict"]["state"] == dc.CLOSED
           and "SENSOR_NOT_FRESH:%s" % ov["sensor"] in s["verdict"]["reasons"]]
    assert hit and hit[0][0] - t_fault <= limit_s, hit[:1]
    assert all(s["verdict"]["state"] == dc.CLOSED for t, s in states if t >= hit[0][0])
    print("%s: fault %s %s@%.1f s -> CLOSED +%.2f s" % (name, ov["kind"], ov["sensor"], ov["t_s"],
                                                       hit[0][0] - t_fault))


def test_crossing_sample_far_edge_recorded_at_pulse_end(tmp_path):
    """SIMULATED committed `crossing` sample: the far edge used for REOPENED is where the plate flux fell below the
    thickness threshold (conservatively beyond the true far edge, by the radiant zone and the derivative lag), not
    where the vehicle was when the pulse was declared over; the stopped vehicle (25 m past the far edge) has passed."""
    d = VU / "samples" / "crossing"
    if not (d / "session.json").exists():
        pytest.skip("no committed crossing sample")
    truth = json.loads((d / "session.json").read_text())["truth"]
    far_true = truth["crossing"]["far_edge_world_m_at_crossing"]
    pipe = make_pipe(tmp_path, vehicle="fire_engine")
    states = pl.run_virtual(pipe, pl.iter_source(d), hooks={3.0: lambda p, now: p.capture_baseline(now)})
    ref = pipe.far_edge_ref
    assert ref is not None and ref.get("t_pi") is not None
    along = ref["pos"][0] * ref["dir"][0] + ref["pos"][1] * ref["dir"][1]     # metres along course from the start
    assert far_true <= along <= far_true + 6.0, (along, far_true)
    assert states[-1][1]["reopen"]["passed"] is True
    # D3: the vehicle stops 25 m past the crossing still facing away: the crossing is behind the camera
    late = [s for t, s in states if 30.0 <= t <= 44.0]
    assert late and all(not s["reopen"]["view"]["in_view"] and "behind the camera" in s["reopen"]["view"]["reason"]
                        for s in late)
    assert all(s["verdict"]["state"] != dc.REOPENED for _, s in states)
    last = pipe.crossing["last"]
    assert last["ok"] and last["sim"] and Path(last["store"]).name == "pairs_sim.jsonl"
