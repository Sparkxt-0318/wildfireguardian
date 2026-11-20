"""crossing.link: per-sensor freshness exactly per DESIGN.md 5, link loss, frozen payloads, the WebSocket client.

All messages are SYNTHETIC (built with wfgvu.protocol). Times are a virtual laptop monotonic clock.
"""
import asyncio
import itertools
import math

import pytest

from crossing import decision as dc
from crossing.config import LinkConfig
from crossing.link import LinkClient, LinkState

from wfgvu import protocol

CTX = protocol.Context("VU-T", "VU-T-1", sim=True)


_HB = itertools.count()


def reading(sensor, seq, data, t=None):
    """Pi t_mono defaults to 100 + 0.01 * seq so that consecutive readings advance (D2a checks it)."""
    return CTX.make("reading", sensor=sensor, seq=seq, data=data, t_mono=100.0 + (0.01 * seq if t is None else t),
                    t_utc=None)


def hb(sensor, status="ok", t=None, seq=None):
    """Heartbeat; seq and t_mono advance automatically unless given."""
    n = next(_HB)
    return CTX.make("heartbeat", sensor=sensor, status=status, detail="", last_reading_seq=None, rate_hz=10.0,
                    seq=n if seq is None else seq, t_mono=100.0 + (0.001 * n if t is None else t), t_utc=None)


def tc(v):
    return {"temp_c": v, "cj_c": 25.0, "fault": None}


def payload(sensor, v):
    """A protocol-valid ``data`` for ``sensor`` that differs when ``v`` differs."""
    v = float(v)
    if sensor in protocol.TC_SENSORS:
        return tc(v)
    if sensor == "thermal":
        return {"w": 1, "h": 1, "enc": protocol.THERMAL_ENC, "raw_per_k": 64.0, "pix": "v%r" % v, "gain": "low",
                "shutter": False}
    if sensor == "radar":
        return {"frame": int(v * 10), "range_res_m": 0.2, "n_bins": 1, "range_profile_db": [v], "az_heatmap": None,
                "points": None, "tlv_types": [2], "frame_ok": True}
    if sensor == "imu":
        return {"roll_deg": v, "pitch_deg": 0.0, "heading_deg": 0.0, "grav": None, "calib": None}
    if sensor == "gnss":
        return {"fix": 1, "lat": 37.0, "lon": 128.0, "alt_m": v, "speed_m_s": 0.0, "course_deg": None, "hdop": 1.0,
                "sats": 8, "utc": None}
    return {"cpu_c": v, "throttled_hex": "0x0", "under_voltage_now": False, "under_voltage_ever": False,
            "input_v": None, "disk_free_mb": 1.0, "rec_bytes": 0}


def fresh_state(now=10.0):
    s = LinkState(LinkConfig())
    s.set_connected(True, 0.0)
    s.on_message(hb("tc_plate"), now)
    s.on_message(reading("tc_plate", 0, tc(20.0)), now)
    return s


def test_all_rules_hold_gives_fresh():
    s = fresh_state()
    h = s.status("tc_plate", 10.5)
    assert h.fresh and h.reason == "" and abs(h.age_s - 0.5) < 1e-9


def test_reading_stale_after_2s():
    s = fresh_state()
    s.on_message(hb("tc_plate"), 11.9)           # heartbeats keep coming, readings do not
    assert s.fresh("tc_plate", 12.0)
    st = s.status("tc_plate", 12.01)
    assert not st.fresh and "stale" in st.reason


@pytest.mark.parametrize("status", ["no_device", "error", "stale", "sim_ended"])
def test_pi_status_not_ok_is_not_fresh(status):
    s = fresh_state()
    s.on_message(hb("tc_plate", status), 10.1)
    st = s.status("tc_plate", 10.2)
    assert not st.fresh and status in st.reason


def test_heartbeat_missing_or_old_is_not_fresh():
    s = LinkState()
    s.set_connected(True, 0.0)
    s.on_message(reading("imu", 0, payload("imu", 0.0)), 5.0)
    assert s.status("imu", 5.1).reason == "no Pi heartbeat"
    s.on_message(hb("imu"), 5.0)
    for k in range(1, 20):                       # readings keep changing; heartbeat stops
        s.on_message(reading("imu", k, payload("imu", 0.01 * k)), 5.0 + 0.1 * k)
    assert s.fresh("imu", 7.0)
    st = s.status("imu", 7.01)
    assert not st.fresh and "heartbeat" in st.reason


def test_pi_ok_flag_alone_is_not_trusted():
    s = LinkState()
    s.set_connected(True, 0.0)
    s.on_message(hb("radar"), 1.0)               # Pi says ok, but no reading ever arrived on the laptop
    assert s.status("radar", 1.1).reason == "no reading received"


@pytest.mark.parametrize("sensor,freeze", [("thermal", 1.0), ("radar", 1.0), ("imu", 2.0), ("tc_plate", 5.0),
                                           ("tc_air", 5.0), ("tc_housing", 5.0), ("gnss", 5.0)])
def test_frozen_payload_detected_after_freeze_s(sensor, freeze):
    def fed(until):
        s = LinkState()
        s.set_connected(True, 0.0)
        k = 0
        while 0.1 * k <= until + 1e-9:           # the same payload repeated at 10 Hz, heartbeats ok at 2 Hz
            t = 0.1 * k
            s.on_message(reading(sensor, k, payload(sensor, 1)), t)
            if k % 5 == 0:
                s.on_message(hb(sensor), t)
            k += 1
        return s, k

    s, _ = fed(freeze - 0.1)
    assert s.fresh(sensor, freeze - 0.05)
    s, k = fed(freeze)
    st = s.status(sensor, freeze + 0.05)
    assert not st.fresh and "frozen" in st.reason
    s.on_message(reading(sensor, k, payload(sensor, 2)), freeze + 0.06)   # payload changes again: fresh again
    assert s.fresh(sensor, freeze + 0.1)


def test_value_freeze_ignores_frame_counters_and_flags():
    """D2b: for thermal and radar only the raw values count; a new frame number / shutter flag on identical raw
    data is still frozen."""
    s = LinkState()
    s.set_connected(True, 0.0)
    for k in range(13):
        t = 0.1 * k
        th = dict(payload("thermal", 1), shutter=bool(k % 2))
        rd = dict(payload("radar", 1), frame=k)
        s.on_message(reading("thermal", k, th), t)
        s.on_message(reading("radar", k, rd), t)
        if k % 5 == 0:
            s.on_message(hb("thermal"), t)
            s.on_message(hb("radar"), t)
    for sensor in ("thermal", "radar"):
        st = s.status(sensor, 1.21)
        assert not st.fresh and "frozen" in st.reason, (sensor, st)


@pytest.mark.parametrize("how", ["repeat", "seq_back", "t_mono_same", "t_mono_back"])
def test_pi_side_freeze_is_not_fresh_at_once(how):
    """D2a: a reading that does not advance seq or t_mono (stuck / replaying driver or server) makes the sensor not
    fresh immediately, even for a thermocouple whose value window is 5 s; an advancing reading clears it."""
    s = LinkState()
    s.set_connected(True, 0.0)
    s.on_message(hb("tc_plate"), 0.0)
    for k in range(5):
        s.on_message(reading("tc_plate", k, tc(20.0 + k), t=0.1 * k), 0.1 * k)
    assert s.fresh("tc_plate", 0.45)
    bad = {"repeat": reading("tc_plate", 4, tc(24.0), t=0.4), "seq_back": reading("tc_plate", 2, tc(25.0), t=0.5),
           "t_mono_same": reading("tc_plate", 5, tc(25.0), t=0.4),
           "t_mono_back": reading("tc_plate", 5, tc(25.0), t=0.3)}[how]
    s.on_message(bad, 0.5)
    st = s.status("tc_plate", 0.5)
    assert not st.fresh and "frozen on the Pi" in st.reason, st
    assert s.tracks["tc_plate"].pi_freezes == 1
    s.on_message(reading("tc_plate", 9, tc(26.0), t=0.6), 0.6)
    assert s.fresh("tc_plate", 0.65)


def test_pi_side_heartbeat_freeze_is_not_fresh():
    s = fresh_state()
    s.on_message(hb("tc_plate", seq=10_000, t=50.0), 10.1)
    assert s.fresh("tc_plate", 10.2)
    s.on_message(hb("tc_plate", seq=10_000, t=50.0), 10.3)        # the same heartbeat again
    st = s.status("tc_plate", 10.35)
    assert not st.fresh and "heartbeat" in st.reason
    s.on_message(hb("tc_plate", seq=10_001, t=50.5), 10.4)
    assert s.fresh("tc_plate", 10.45)


@pytest.mark.parametrize("dt,fresh", [(0.0, True), (-1e-7, True), (-1e-3, True), (-0.002, False), (-0.6, False)])
def test_negative_age_tolerance(dt, fresh):
    """D6: a receipt time a hair after ``now`` (float rounding) is fresh; a clearly future one is not. The health
    snapshot then also passes decision._fresh (the old clamp-to-zero workaround in link.py is gone)."""
    s = fresh_state(now=10.0)
    assert s.fresh("tc_plate", 10.0 + dt) is fresh
    ok, _ = dc._fresh(s.health(10.0 + dt).as_dict(), "tc_plate", 2.0)
    assert ok is fresh


def test_tc_can_sit_still_for_less_than_5s():
    s = LinkState()
    s.set_connected(True, 0.0)
    for k in range(45):
        t = 0.1 * k
        s.on_message(reading("tc_plate", k, tc(20.0)), t)
        if k % 5 == 0:
            s.on_message(hb("tc_plate"), t)
    assert s.fresh("tc_plate", 4.45)


def test_link_down_marks_everything_not_fresh_at_once():
    s = LinkState()
    s.set_connected(True, 0.0)
    for k, sensor in enumerate(protocol.SENSORS):
        s.on_message(hb(sensor), 1.0)
        s.on_message(reading(sensor, 0, payload(sensor, k)), 1.0)
    assert all(s.fresh(x, 1.1) for x in protocol.SENSORS)
    s.set_connected(False, 1.2, "socket closed")
    h = s.health(1.2)
    assert h.link_up is False
    assert all(not v["fresh"] and "link down" in v["reason"] for v in h.sensors.values())


def test_link_silence_counts_as_link_loss():
    s = fresh_state(now=1.0)
    assert s.link_up(2.5)
    assert not s.link_up(2.51)
    assert "silent" in s.status("tc_plate", 2.6).reason


def test_parse_errors_and_seq_gaps_are_counted():
    s = LinkState()
    s.set_connected(True, 0.0)
    assert s.on_text("not json", 1.0) is None
    assert s.on_text('{"v": 1, "type": "reading", "t": NaN}', 1.0) is None
    assert s.on_text(protocol.dumps(reading("tc_air", 0, tc(1.0))), 1.0) is not None
    assert s.parse_errors == 2
    s.on_message(reading("tc_air", 5, tc(2.0)), 1.1)           # 4 lost
    s.on_message(reading("thermal", 0, payload("thermal", 1)), 1.1)
    s.on_message(reading("thermal", 3, payload("thermal", 2)), 1.2)          # decimated on the wire: not a drop
    assert s.tracks["tc_air"].drops == 4
    assert s.tracks["thermal"].drops == 0
    s.on_message(CTX.make("event", kind="dropped", detail="12 messages"), 1.3)
    assert s.dropped_events == 1


def test_new_pi_session_resets_tracks():
    s = fresh_state()
    s.on_message(CTX.make("hello", sensors=["tc_plate"], version="x", config_digest="0"), 10.1)
    other = protocol.Context("VU-T", "VU-T-2", sim=True)
    s.on_message(other.make("hello", sensors=["tc_plate"], version="x", config_digest="0"), 10.2)
    assert s.session_id == "VU-T-2"
    assert s.tracks["tc_plate"].last_rx_mono is None and not s.fresh("tc_plate", 10.3)


def test_health_snapshot_is_accepted_by_decision():
    s = fresh_state()
    h = s.health(10.5)
    hmap = dc._health_map(h)
    ok, why = dc._fresh(hmap, "tc_plate", 2.0)
    assert ok
    ok, why = dc._fresh(hmap, "radar", 2.0)
    assert not ok
    assert set(h.as_dict()) == set(protocol.SENSORS)


def test_sim_flag_is_sticky():
    s = LinkState()
    assert s.sim is False
    s.on_message(reading("pi", 0, payload("pi", 1.0)), 1.0)
    assert s.sim is True


def test_backoff_doubles_and_caps():
    c = LinkClient("ws://127.0.0.1:9/stream", sink=None, cfg=LinkConfig(reconnect_min_s=0.5, reconnect_max_s=5.0))
    seq = [c.next_backoff() for _ in range(7)]
    assert seq == [0.5, 1.0, 2.0, 4.0, 5.0, 5.0, 5.0]


class Sink:
    def __init__(self):
        self.state = LinkState(LinkConfig(reconnect_min_s=0.05, reconnect_max_s=0.1))
        self.events = []

    def on_text(self, text, now):
        return self.state.on_text(text, now)

    def set_connected(self, flag, now, reason=""):
        self.events.append(flag)
        self.state.set_connected(flag, now, reason)


def test_client_receives_and_reconnects_over_a_real_socket():
    """Loopback WebSocket server (needs local port binding; skipped where the sandbox forbids it)."""
    from websockets.asyncio.server import serve

    async def scenario():
        sink = Sink()
        served = []

        async def handler(ws):
            served.append(1)
            await ws.send(protocol.dumps(CTX.make("hello", sensors=["tc_air"], version="t", config_digest="0")))
            await ws.send(protocol.dumps(hb("tc_air")))
            await ws.send(protocol.dumps(reading("tc_air", len(served), tc(21.0 + len(served)))))
            await ws.send("garbage")
            if len(served) == 1:
                await ws.close()                     # first connection drops: client must reconnect
            else:
                await asyncio.sleep(0.3)

        try:
            server = await serve(handler, "127.0.0.1", 0)
        except OSError as exc:
            pytest.skip("cannot bind a loopback port here: %s" % exc)
        port = server.sockets[0].getsockname()[1]
        client = LinkClient("ws://127.0.0.1:%d/stream" % port, sink, sink.state.cfg)
        stop = asyncio.Event()
        task = asyncio.ensure_future(client.run(stop))
        for _ in range(100):
            await asyncio.sleep(0.02)
            if len(served) >= 2 and sink.state.tracks["tc_air"].n_readings >= 2:
                break
        stop.set()
        await asyncio.wait_for(task, 3.0)
        server.close()
        await server.wait_closed()
        return sink, served

    sink, served = asyncio.run(scenario())
    assert len(served) >= 2
    assert sink.events[:3] == [True, False, True]
    assert sink.state.tracks["tc_air"].n_readings >= 2
    assert sink.state.parse_errors >= 2
    assert sink.state.connected is False                      # stopped: link down, nothing fresh
    assert not sink.state.fresh("tc_air", math.inf)
