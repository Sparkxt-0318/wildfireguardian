"""wfgvu.synth: scenario generator, failure overlays, replay round trip and the committed samples.

Everything here is SIMULATED data produced by wfgvu.synth itself (illustrative physics, see its docstring); these
tests check that the generator writes what it claims (format, truth, overlays, internal consistency), not that the
physics resembles real sensors. All runs are seeded and short.
"""
import gzip
import json
import math
import time
from pathlib import Path

import numpy as np
import pytest

from wfgvu import protocol, replay, synth
from wfgvu.drivers.base import Driver

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "samples"
SAMPLE_NAMES = [n for n, _, _ in synth.SAMPLES]

# short runs: onset at 3 s, vehicle starts at 5 s (crossing) / 2 s (after_pass)
SHORT = {
    "no_fire": dict(duration=8.0),
    "smoke_only": dict(duration=8.0, onset_s=3.0),
    "flame_front": dict(duration=8.0, onset_s=3.0),
    "water_mist": dict(duration=8.0, onset_s=3.0),
    "corner_reflector": dict(duration=8.0, range_m=3.0),
    "crossing": dict(duration=14.0, onset_s=2.0, t_go_s=5.0),
    "after_pass": dict(duration=14.0, t_go_s=2.0),
    # return scenarios cut short: crossing at ~8.6 s, burn-out at 11 s, the turn starts just before 14 s
    "crossing_return": dict(duration=14.0, onset_s=2.0, t_go_s=5.0, flame_out_s=11.0),
    "crossing_return_hot": dict(duration=14.0, onset_s=2.0, t_go_s=5.0, flame_out_s=11.0),
}
RETURN_SAMPLES = ("crossing_return", "crossing_return_hot")


def gen(tmp, scenario, seed=3, overlays=(), name=None, **kw):
    args = dict(SHORT[scenario])
    args.update(kw)
    dur = args.pop("duration")
    args.update(synth.COMPACT)
    return synth.generate(scenario, Path(tmp) / (name or scenario), seed=seed, duration=dur, overlays=overlays,
                          **args)


def raw_messages(session_dir, name):
    out = []
    for path in replay.stream_files(Path(session_dir), name):
        for line in replay.iter_lines(path):
            out.append(protocol.parse(line))
    return out


def readings(session_dir, sensor):
    return [m for m in raw_messages(session_dir, sensor) if m["type"] == "reading"]


def heartbeats(session_dir, sensor):
    return [m for m in raw_messages(session_dir, sensor) if m["type"] == "heartbeat"]


@pytest.fixture(scope="module")
def sessions(tmp_path_factory):
    root = tmp_path_factory.mktemp("synth")
    return {s: gen(root, s) for s in synth.SCENARIOS}


# ----------------------------------------------------------------------------------------------- format / truth

@pytest.mark.parametrize("scenario", synth.SCENARIOS)
def test_scenario_writes_session_that_replays_and_parses(sessions, scenario):
    d = sessions[scenario]
    info = json.loads((d / "session.json").read_text())
    assert info["sim"] is True and "SIMULATED" in info["simulated"]
    assert info["scenario"] == scenario and info["truth"]["scenario"] == scenario
    assert "SIMULATED" in info["truth"]["notice"]
    assert info["t_mono_first"] <= info["t_mono_last"]
    sess = replay.load(d)
    assert set(sess.streams) == set(protocol.SENSORS)
    assert sess.sim is True
    for sensor, stream in sess.streams.items():
        msgs = list(stream)
        assert stream.bad_lines == 0
        t = [m["t_mono"] for m in msgs]
        assert t == sorted(t)
        rs = [m for m in msgs if m["type"] == "reading"]
        hb = [m for m in msgs if m["type"] == "heartbeat"]
        assert rs and hb, sensor
        assert [m["seq"] for m in rs] == list(range(len(rs)))           # no gaps
        assert [m["seq"] for m in hb] == list(range(len(hb)))
        assert np.allclose(np.diff([m["t_mono"] for m in hb]), 0.5, atol=1e-3)
        assert all(m["sim"] is True and m["session_id"] == info["session_id"] for m in msgs)
        for m in msgs:                                                # exact wire text round-trips
            assert protocol.parse(protocol.dumps(m)) == m
        assert all(m["status"] == "ok" for m in hb[3:]), sensor          # no overlay: healthy after start-up
    ev = list(sess.events())
    assert ev and ev[0]["kind"] == "sim_note"


def test_payloads_decode_and_have_expected_shapes(sessions):
    d = sessions["flame_front"]
    th = readings(d, "thermal")
    img = protocol.decode_thermal(th[-1]["data"])
    assert img.shape == (192, 256) and img.dtype == np.float32
    rd = readings(d, "radar")[0]["data"]
    iq = protocol.decode_iq(rd["az_heatmap"])
    assert iq.shape == (rd["n_bins"], 4) and len(rd["range_profile_db"]) == rd["n_bins"] == 100
    assert rd["range_res_m"] == 0.25 and rd["frame_ok"] is True and rd["tlv_types"] == [1, 2, 4, 7]
    assert all(len(p) == 5 for p in rd["points"])
    g = readings(d, "gnss")[0]["data"]
    assert g["fix"] == 1 and abs(g["lat"] - 36.39) < 1e-3 and abs(g["lon"] - 128.70) < 1e-3
    imu = readings(d, "imu")[0]["data"]
    assert abs(imu["pitch_deg"] - math.degrees(math.atan(0.04))) < 0.3
    assert abs(math.hypot(*imu["grav"]) - 9.80665) < 0.05
    tc = readings(d, "tc_plate")[0]["data"]
    assert tc["fault"] is None and (tc["temp_c"] * 4) % 1 == 0          # MAX31855 0.25 C steps


def test_truth_blocks(sessions):
    tr = json.loads((sessions["crossing"] / "session.json").read_text())["truth"]
    assert tr["measured_thickness_m"] > tr["flame"]["depth_m"] > 0     # flux > 5 kW/m2 zone includes the halo
    c = tr["crossing"]
    assert c["t_enter_flame_s"] < c["t_exit_flame_s"]
    assert c["speed_in_flame_m_s"] == pytest.approx(5.0, abs=0.01)
    assert tr["flux"]["peak_q_kw_m2"] == pytest.approx(50.0, abs=0.5)
    ff = json.loads((sessions["flame_front"] / "session.json").read_text())["truth"]
    rows = [r for r in ff["timeline"] if "near_edge_m" in r]
    assert rows and rows[0]["t_s"] >= 3.0
    for r in rows:                                                   # stationary: near = range - spread * (t - onset)
        assert r["near_edge_m"] == pytest.approx(14.0 - 0.05 * (r["t_s"] - 3.0), abs=1e-3)
        assert r["far_edge_m"] - r["near_edge_m"] == pytest.approx(3.0, abs=1e-3)
    assert ff["baseline_window_s"] == [0.5, 2.5]
    kinds = {t["kind"] for t in ff["radar"]["targets"]}
    assert {"solid_object", "sign_post"} <= kinds
    ap = json.loads((sessions["after_pass"] / "session.json").read_text())["truth"]
    assert ap["burnt_zone"]["far_world_m"] == 16.0 and ap["flux"]["peak_q_kw_m2"] < 1.0
    cr = json.loads((sessions["corner_reflector"] / "session.json").read_text())["truth"]
    assert cr["corner_reflector"]["range_world_m"] == 3.0


# ----------------------------------------------------------------------------------------------- physics sanity

def _max_c(d, t_min=0.0):
    t0 = json.loads((d / "session.json").read_text())["truth"]["t_mono_at_t0"]
    imgs = [protocol.decode_thermal(m["data"]) for m in readings(d, "thermal") if m["t_mono"] - t0 >= t_min]
    return max(float(i.max()) for i in imgs) - synth.C_TO_K


def test_thermal_levels(sessions):
    assert _max_c(sessions["smoke_only"], 3.5) < 100.0                 # smoke-only well below 120 C
    assert _max_c(sessions["water_mist"], 3.5) < 60.0
    assert _max_c(sessions["no_fire"]) < 60.0
    assert _max_c(sessions["after_pass"]) < 300.0                     # no flame-temperature pixel
    assert _max_c(sessions["flame_front"], 3.5) == pytest.approx(550.0, abs=0.1)   # low-gain ceiling
    t0 = json.loads((sessions["flame_front"] / "session.json").read_text())["truth"]["t_mono_at_t0"]
    pre = [m for m in readings(sessions["flame_front"], "thermal") if m["t_mono"] - t0 < 2.9]
    assert max(float(protocol.decode_thermal(m["data"]).max()) for m in pre) - synth.C_TO_K < 100.0


def test_consecutive_thermal_frames_always_differ(sessions):
    for s in ("no_fire", "after_pass", "flame_front"):
        pix = [m["data"]["pix"] for m in readings(sessions[s], "thermal")]
        assert all(a != b for a, b in zip(pix, pix[1:])), s


def test_flame_base_matches_truth_geometry(sessions):
    """Independent pinhole back-projection of the lowest flame pixel onto the graded ground (camera 2.6 m,
    pitch = atan(grade), no roll/mount angles) recovers the truth near-edge distance."""
    d = sessions["flame_front"]
    tr = json.loads((d / "session.json").read_text())["truth"]
    t0, g, H = tr["t_mono_at_t0"], tr["ground"]["grade"], tr["camera"]["height_m"]
    fy = 96.0 / math.tan(math.radians(21.0))
    pitch = math.atan(g)
    checked = 0
    for m in readings(d, "thermal"):
        t = m["t_mono"] - t0
        if t < 4.0:
            continue
        img = protocol.decode_thermal(m["data"]) - synth.C_TO_K
        col = img[:, 120:136] >= 300.0
        rows = np.flatnonzero(col.any(axis=1))
        low = rows.max() + 0.5                                       # bottom edge of the lowest flame pixel
        elev = pitch + math.atan(-(low - 95.5) / fy)                 # ray elevation above level (centre columns)
        x = H / (g - math.tan(elev))                                 # meet ground z = g*x
        truth = 14.0 - 0.05 * (t - 3.0)
        assert x == pytest.approx(truth, rel=0.05), t
        checked += 1
    assert checked >= 10


def _beam0(d, t_lo, t_hi, rng_m):
    tr = json.loads((d / "session.json").read_text())["truth"]
    t0 = tr["t_mono_at_t0"]
    b = int(round(rng_m / 0.25))
    out = []
    for m in readings(d, "radar"):
        if t_lo <= m["t_mono"] - t0 < t_hi:
            iq = protocol.decode_iq(m["data"]["az_heatmap"])
            out.append(iq[b].sum() / iq.shape[1])                     # boresight beam (steering = ones)
    return np.array(out)


def _dphase_std(y):
    return float(np.std(np.angle(y[1:] * np.conj(y[:-1]))))


def test_radar_flame_smoke_and_mist_effects(tmp_path):
    kw = dict(duration=14.0, onset_s=7.0)
    ff = gen(tmp_path, "flame_front", seed=5, **kw)
    so = gen(tmp_path, "smoke_only", seed=5, **kw)
    wm = gen(tmp_path, "water_mist", seed=5, **kw)
    r_obj = synth.solid_object_x(synth.make_params("flame_front"))    # 21 m, behind the flame
    pre, post = _beam0(ff, 0.0, 7.0, r_obj), _beam0(ff, 7.0, 14.0, r_obj)
    assert _dphase_std(post) > 3 * _dphase_std(pre)                  # phase walk behind the flame
    r_s = synth.solid_object_x(synth.make_params("smoke_only"))
    pre, post = _beam0(so, 0.0, 7.0, r_s), _beam0(so, 7.0, 14.0, r_s)
    assert _dphase_std(post) < 1.5 * _dphase_std(pre) + 0.02         # smoke: no radar effect
    assert abs(20 * math.log10(np.abs(post).mean() / np.abs(pre).mean())) < 0.5
    pre, post = _beam0(wm, 0.0, 7.0, r_s), _beam0(wm, 7.0, 14.0, r_s)
    loss = 20 * math.log10(np.abs(pre).mean() / np.abs(post).mean())
    assert 1.0 < loss < 3.0                                          # mist: 1-3 dB loss ...
    assert _dphase_std(post) < 1.5 * _dphase_std(pre) + 0.02         # ... and no phase walk


def test_corner_reflector_echo(sessions):
    y = _beam0(sessions["corner_reflector"], 0.0, 8.0, 3.0)
    noise = _beam0(sessions["corner_reflector"], 0.0, 8.0, 24.0)
    assert 20 * math.log10(np.abs(y).mean() / np.abs(noise).mean()) > 35.0


def test_crossing_plate_and_air_respond(sessions):
    d = sessions["crossing"]
    tr = json.loads((d / "session.json").read_text())["truth"]
    plate = [m["data"]["temp_c"] for m in readings(d, "tc_plate")]
    air = [m["data"]["temp_c"] for m in readings(d, "tc_air")]
    assert max(plate) > 25.0 + 5.0 and max(air) > 25.0 + 30.0
    gn = readings(d, "gnss")
    assert max(m["data"]["speed_m_s"] for m in gn) == pytest.approx(5.0, abs=0.15)
    assert gn[-1]["data"]["lat"] > gn[0]["data"]["lat"]               # course 30 deg: north-east
    assert tr["vehicle"]["stop_at_world_m"] > tr["crossing"]["far_edge_world_m_at_crossing"]


def test_plate_follows_the_laptops_energy_balance(sessions):
    """Truth q and the truth plate/air series satisfy rho*cp*d*dT/dt = alpha*q - loss(T, Ta) (h 10, eps 0.95)."""
    tr = json.loads((sessions["crossing"] / "session.json").read_text())["truth"]
    tl = tr["timeline"]
    for a, b in zip(tl, tl[1:]):
        if a["q_kw_m2"] != b["q_kw_m2"] or a["q_kw_m2"] == 0.0:
            continue                                                 # only stretches of constant flux
        tm = 0.5 * (a["plate_c"] + b["plate_c"]) + synth.C_TO_K
        ta = 0.5 * (a["air_c"] + b["air_c"]) + synth.C_TO_K
        lhs = 8960 * 385 * 0.001 * (b["plate_c"] - a["plate_c"]) / (b["t_s"] - a["t_s"])
        rhs = 0.95 * a["q_kw_m2"] * 1000 - 10 * (tm - ta) - 0.95 * synth.SIGMA * (tm ** 4 - ta ** 4)
        assert lhs == pytest.approx(rhs, abs=60.0)


# ----------------------------------------------------------------------------------------------- overlays

def test_fail_overlay_stops_readings_and_reports_no_device(tmp_path):
    ov = [synth.parse_overlay("fail", "radar@4")]
    d = gen(tmp_path, "flame_front", overlays=ov, name="fail")
    t0 = json.loads((d / "session.json").read_text())["truth"]["t_mono_at_t0"]
    assert all(m["t_mono"] - t0 < 4.0 for m in readings(d, "radar"))
    hb = {round(m["t_mono"] - t0, 2): m for m in heartbeats(d, "radar")}
    assert hb[4.25]["status"] == "ok"                                  # within stale_s
    assert hb[5.25]["status"] == "stale"
    assert hb[6.25]["status"] == "no_device" and hb[7.75]["status"] == "no_device"
    assert hb[7.75]["rate_hz"] == 0.0
    assert hb[7.75]["last_reading_seq"] == len(readings(d, "radar")) - 1
    info = json.loads((d / "session.json").read_text())
    assert info["truth"]["overlays"][0]["sensor"] == "radar" and "fail-radar4" in info["session_id"]
    assert any(e["kind"] == "synth_overlay" for e in replay.load(d).events())


def test_freeze_overlay_repeats_identical_data(tmp_path):
    d = gen(tmp_path, "flame_front", overlays=[synth.parse_overlay("freeze", "thermal@4")], name="freeze")
    t0 = json.loads((d / "session.json").read_text())["truth"]["t_mono_at_t0"]
    rs = readings(d, "thermal")
    before = [m for m in rs if m["t_mono"] - t0 < 4.0]
    after = [m for m in rs if m["t_mono"] - t0 >= 4.0]
    assert len(after) >= 10
    assert all(m["data"] == before[-1]["data"] for m in after)
    assert [m["seq"] for m in rs] == list(range(len(rs)))
    assert all(m["status"] == "ok" for m in heartbeats(d, "thermal")[2:])
    assert before[-2]["data"] != before[-1]["data"]


def test_fault_overlay_and_independence_of_other_sensors(tmp_path):
    base = gen(tmp_path, "flame_front", name="base")
    d = gen(tmp_path, "flame_front", overlays=[synth.parse_overlay("fault", "tc_plate@4:open")], name="fault")
    t0 = json.loads((d / "session.json").read_text())["truth"]["t_mono_at_t0"]
    for m in readings(d, "tc_plate"):
        if m["t_mono"] - t0 >= 4.0:
            assert m["data"]["temp_c"] is None and m["data"]["fault"] == "open" and m["data"]["cj_c"] is not None
        else:
            assert m["data"]["fault"] is None
    hb = [m for m in heartbeats(d, "tc_plate") if m["t_mono"] - t0 > 4.1]
    assert hb and all(m["status"] == "error" and "open" in m["detail"] for m in hb)
    for s in ("thermal", "radar", "imu", "gnss", "tc_air"):          # other streams unchanged by the overlay
        a = [m["data"] for m in readings(base, s)]
        b = [m["data"] for m in readings(d, s)]
        assert a == b, s
    spi = gen(tmp_path, "no_fire", overlays=[synth.parse_overlay("fault", "tc_air@2:spi")], name="spi")
    last = readings(spi, "tc_air")[-1]["data"]
    assert last == {"temp_c": None, "cj_c": None, "fault": "spi"}


@pytest.mark.parametrize("kind,spec", [("fail", "radar"), ("fail", "lidar@3"), ("freeze", "thermal@-1"),
                                       ("fault", "imu@3:open"), ("fault", "tc_plate@3:melted"),
                                       ("fault", "tc_plate@3")])
def test_bad_overlay_specs_rejected(kind, spec):
    with pytest.raises(ValueError):
        synth.parse_overlay(kind, spec)


def test_sim_driver_adopts_recorded_no_device(tmp_path):
    # gnss stops at 1 s; recorded no_device from 1 + 2.0 (stale_s) + 1 = 4 s to the end (8 s): 0.4 s at speed 10
    d = gen(tmp_path, "no_fire", overlays=[synth.parse_overlay("fail", "gnss@1")], name="drv", duration=8.0)
    sess = replay.load(d)
    got = []
    drv = Driver("gnss", {}, got.append, sess.streams["gnss"], ctx=protocol.Context("VU-01", "X", sim=True))
    sess.start(speed=10.0)
    drv.start()
    try:
        t_end = time.monotonic() + 5.0
        while time.monotonic() < t_end and not any(m.get("status") == "sim_ended" for m in got):
            time.sleep(0.02)
    finally:
        drv.stop()
    rs = [m for m in got if m["type"] == "reading"]
    assert rs and all(m["sim"] for m in rs) and len(rs) <= 6                 # 5 Hz for 1 s
    assert any(m["type"] == "heartbeat" and m["status"] == "no_device" and "fail" in m["detail"] for m in got)


# ----------------------------------------------------------------------------------------------- determinism, CLI

def test_same_seed_gives_identical_files_and_other_seed_differs(tmp_path):
    a = gen(tmp_path, "water_mist", seed=9, name="a")
    b = gen(tmp_path, "water_mist", seed=9, name="b")
    c = gen(tmp_path, "water_mist", seed=10, name="c")
    for f in sorted(p.name for p in a.iterdir()):
        if f == "session.json":
            ia, ib = json.loads((a / f).read_text()), json.loads((b / f).read_text())
            assert ia == ib
        else:
            assert (a / f).read_bytes() == (b / f).read_bytes(), f
    assert (a / "radar.jsonl.gz").read_bytes() != (c / "radar.jsonl.gz").read_bytes()


def test_cli(tmp_path, capsys):
    out = tmp_path / "cli"
    rc = synth.main(["after_pass", str(out), "--seed", "2", "--duration", "5", "--compact", "--speed", "2.0",
                     "--fail", "pi@2", "--freeze", "imu@3", "--fault", "tc_housing@1:short_gnd"])
    assert rc == 0
    info = json.loads((out / "session.json").read_text())
    assert info["params"]["speed_m_s"] == 2.0 and info["params"]["scene_quant_k"] == 0.25
    assert {o["kind"] for o in info["truth"]["overlays"]} == {"fail", "freeze", "fault"}
    assert synth.main(["no_fire", str(tmp_path / "bad"), "--fail", "radar"]) == 2
    with pytest.raises(SystemExit):
        synth.main(["volcano", str(tmp_path / "x")])
    out.joinpath("thermal.3.jsonl.gz").write_bytes(gzip.compress(b""))      # stale part from an earlier run
    synth.main(["no_fire", str(out), "--duration", "2", "--compact"])
    assert not out.joinpath("thermal.3.jsonl.gz").exists()
    assert json.loads((out / "session.json").read_text())["scenario"] == "no_fire"


# ----------------------------------------------------------------------------------------------- committed samples

def test_samples_present_small_and_simulated():
    total = 0
    for name in SAMPLE_NAMES:
        d = SAMPLES_DIR / name
        assert (d / "session.json").exists(), name
        total += sum(p.stat().st_size for p in d.iterdir())
        info = json.loads((d / "session.json").read_text())
        assert info["sim"] is True and "truth" in info and "SIMULATED" in info["simulated"]
        assert 40.0 <= info["params"]["duration_s"] <= (70.0 if name in RETURN_SAMPLES else 60.0)
        sess = replay.load(d)
        assert set(sess.streams) == set(protocol.SENSORS)
        assert sess.duration == pytest.approx(info["params"]["duration_s"], abs=0.5)
    assert total < 5_000_000
    assert (SAMPLES_DIR / "README.md").read_text().count("SIMULATED") >= 1
    assert len({json.loads((SAMPLES_DIR / n / "session.json").read_text())["session_id"]
                for n in SAMPLE_NAMES}) == len(SAMPLE_NAMES)


@pytest.mark.parametrize("name", SAMPLE_NAMES)
def test_sample_every_line_parses(name):
    d = SAMPLES_DIR / name
    for f in sorted(d.glob("*.jsonl.gz")):
        n = 0
        with gzip.open(f, "rt") as fh:
            for line in fh:
                m = protocol.parse(line)
                assert m["sim"] is True
                n += 1
        assert n > 0, f.name


def test_sample_overlays_and_truth():
    t0 = json.loads((SAMPLES_DIR / "flame_front_fail_radar" / "session.json").read_text())["truth"]["t_mono_at_t0"]
    assert all(m["t_mono"] - t0 < 20.0 for m in readings(SAMPLES_DIR / "flame_front_fail_radar", "radar"))
    assert heartbeats(SAMPLES_DIR / "flame_front_fail_radar", "radar")[-1]["status"] == "no_device"
    fz = readings(SAMPLES_DIR / "flame_front_freeze_thermal", "thermal")
    frozen = [m for m in fz if m["t_mono"] - t0 >= 20.0]
    assert frozen and all(m["data"] == frozen[0]["data"] for m in frozen)
    tr = json.loads((SAMPLES_DIR / "crossing" / "session.json").read_text())["truth"]
    assert tr["measured_thickness_m"] > 0
    for name in ("no_fire", "after_pass", "crossing") + RETURN_SAMPLES:
        pix = [m["data"]["pix"] for m in readings(SAMPLES_DIR / name, "thermal")]
        assert all(a != b for a, b in zip(pix, pix[1:])), name


def test_session_records_render_mount(tmp_path):
    """session.json config.mount = the mount the frames were rendered with (the Pi's sim hello sends it), for new
    sessions and for every committed sample (level camera)."""
    d = gen(tmp_path, "no_fire", name="m", mount_pitch_deg=-18.0)
    m = json.loads((d / "session.json").read_text())["config"]["mount"]
    assert m["camera_pitch_deg"] == -18.0 and m["camera_height_m"] == 2.6
    for name in SAMPLE_NAMES:
        info = json.loads((SAMPLES_DIR / name / "session.json").read_text())
        assert info["config"]["mount"]["camera_pitch_deg"] == info["truth"]["camera"]["mount_pitch_deg"] == 0.0


# ----------------------------------------------------------------------------------------------- return scenarios

def _wrap(a):
    return (a + 180.0) % 360.0 - 180.0


def test_return_sample_path_gnss_imu_and_stop():
    """The committed crossing_return sample: forward teardrop turnaround at a speed the laptop's facing logic accepts
    (>= 2 m/s, course steps far below its 120 deg jump limit), course and IMU heading follow the heading, and the
    vehicle stops 25 m past the far edge facing back along the road (course 30 + 180 = 210 deg)."""
    d = SAMPLES_DIR / "crossing_return"
    tr = json.loads((d / "session.json").read_text())["truth"]
    rp, t0 = tr["return_path"], tr["t_mono_at_t0"]
    assert rp["t_turn_start_s"] < rp["t_turn_end_s"] < rp["t_stop_s"]
    gn = [(m["t_mono"] - t0, m["data"]) for m in readings(d, "gnss")]
    turn = [g for t, g in gn if rp["t_turn_start_s"] + 0.5 <= t <= rp["t_turn_end_s"] - 0.5]
    assert turn and min(g["speed_m_s"] for g in turn) >= 2.5
    steps = [abs(_wrap(b["course_deg"] - a["course_deg"])) for a, b in zip(turn, turn[1:])]
    assert max(steps) < 10.0                                       # 21.5 deg/s at 5 Hz + noise
    total = sum(_wrap(b["course_deg"] - a["course_deg"]) for a, b in zip(turn, turn[1:]))
    assert abs(total) > 150.0                                      # most of the 180 deg turn is in the window
    stopped = [g for t, g in gn if t >= rp["t_stop_s"] + 0.5]
    assert stopped and max(g["speed_m_s"] for g in stopped) < 0.2
    assert all(abs(_wrap(g["course_deg"] - rp["heading_at_stop_deg"])) < 1e-6 for g in stopped)   # static hold
    k = math.pi / 180.0 * 6371008.8
    for g in stopped:
        dn = (g["lat"] - rp["stop_lat"]) * k
        de = (g["lon"] - rp["stop_lon"]) * k * math.cos(math.radians(g["lat"]))
        assert math.hypot(dn, de) < 3.0                            # 0.5 m Gauss-Markov GNSS error
    imu = [(m["t_mono"] - t0, m["data"]) for m in readings(d, "imu")]
    last = [i for t, i in imu if t >= rp["t_stop_s"] + 0.5]
    hd = np.mean([_wrap(i["heading_deg"] - (rp["heading_at_stop_deg"] - synth.MAG_DECLINATION_DEG)) for i in last])
    assert abs(hd) < 0.5
    # facing downhill on the 4 % road: nose down
    assert np.mean([i["pitch_deg"] for i in last]) == pytest.approx(-math.degrees(math.atan(0.04)), abs=0.1)


def test_return_sample_dem_is_the_session_ground_plane():
    for name in RETURN_SAMPLES:
        d = SAMPLES_DIR / name
        info = json.loads((d / "session.json").read_text())
        par = info["params"]
        assert info["dem"]["file"] == synth.DEM_FILE and info["dem"]["simulated"] is True
        with np.load(d / synth.DEM_FILE, allow_pickle=False) as z:
            assert str(z["crs"]) == "local-enu" and float(z["lat0"]) == par["lat0"] and float(z["lon0"]) == par["lon0"]
            dem, res = np.asarray(z["z"], dtype=float), float(z["res"])
            x0, y_top = float(z["x0"]), float(z["y_top"])
        assert dem.dtype == float and list(dem.shape) == info["dem"]["shape"] and res == 2.0
        gy, gx = np.gradient(dem, res)                             # rows run south: d/dnorth = -gy
        c = math.radians(par["course_deg"])
        assert np.allclose(gx, par["grade"] * math.sin(c), atol=2e-3)
        assert np.allclose(-gy, par["grade"] * math.cos(c), atol=2e-3)
        j = int((0.0 - x0) / res - 0.5 + 0.5)                      # cell around the start fix
        i = int((y_top - 0.0) / res - 0.5 + 0.5)
        assert dem[i, j] == pytest.approx(par["alt0_m"], abs=par["grade"] * res * 2)
        # the turnaround, the stop and the crossing lie inside the grid
        assert (d / synth.DEM_FILE).stat().st_size < 50_000


def test_return_samples_cool_or_keep_the_hot_spot():
    """After burn-out the crossed strip cools below the flame threshold in crossing_return; in crossing_return_hot
    the hot area keeps flame-temperature pixels in view. The plate sees almost no flux once stopped (both)."""
    def frames(name, t_min):
        d = SAMPLES_DIR / name
        t0 = json.loads((d / "session.json").read_text())["truth"]["t_mono_at_t0"]
        return [protocol.decode_thermal(m["data"]) - synth.C_TO_K for m in readings(d, "thermal")
                if m["t_mono"] - t0 >= t_min]
    rp = json.loads((SAMPLES_DIR / "crossing_return" / "session.json").read_text())["truth"]["return_path"]
    cool = frames("crossing_return", rp["t_stop_s"])
    hot = frames("crossing_return_hot", rp["t_stop_s"])
    assert max(float(f.max()) for f in cool) < 100.0
    assert all(int((f >= 300.0).sum()) > 0 for f in hot)
    assert max(float(f.max()) for f in hot) > 500.0       # 600 C under the distance haze, near the 550 C ceiling
    for name in RETURN_SAMPLES:
        tr = json.loads((SAMPLES_DIR / name / "session.json").read_text())["truth"]
        late = [r for r in tr["timeline"] if r["t_s"] >= tr["burn_out"]["flame_out_s"] + 5.0]
        assert late and max(r["q_kw_m2"] for r in late) < 0.5
        assert tr["flux"]["peak_q_kw_m2"] == pytest.approx(50.0, abs=0.5)           # the crossing itself


def test_return_scenario_is_deterministic_and_validated(tmp_path):
    a = gen(tmp_path, "crossing_return_hot", seed=4, name="a")
    b = gen(tmp_path, "crossing_return_hot", seed=4, name="b")
    for f in sorted(p.name for p in a.iterdir()):
        if f != "session.json":
            assert (a / f).read_bytes() == (b / f).read_bytes(), f
    assert (a / synth.DEM_FILE).exists()
    with pytest.raises(ValueError, match="before the turn"):          # flame still burning in the turn
        synth.Scene(synth.make_params("crossing_return", duration_s=30.0, flame_out_s=25.0))
    with pytest.raises(ValueError, match="after the vehicle has crossed"):
        synth.Scene(synth.make_params("crossing_return", duration_s=30.0, flame_out_s=10.0))
    with pytest.raises(ValueError):
        synth.make_params("crossing_return", return_lane_m=20.0)
    gen(tmp_path, "crossing_return", name="c")                    # regenerating into a dir drops nothing extra
    gen(tmp_path, "no_fire", name="c")
    assert not (tmp_path / "c" / synth.DEM_FILE).exists()
