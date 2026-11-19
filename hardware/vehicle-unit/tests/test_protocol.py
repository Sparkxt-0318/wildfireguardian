"""Wire protocol: make/parse round trips, rejection of malformed messages, thermal and IQ codecs."""
import json
import math

import numpy as np
import pytest

from wfgvu import protocol
from wfgvu.protocol import ProtocolError

CTX = protocol.Context(unit_id="VU-01", session_id="VU-01-20261117T101500Z", sim=True)

DATA = {
    "tc_plate": {"temp_c": 25.25, "cj_c": 24.0, "fault": None},
    "tc_housing": {"temp_c": None, "cj_c": 24.0, "fault": "open"},
    "tc_air": {"temp_c": 30.0, "cj_c": 24.0, "fault": None},
    "imu": {"roll_deg": 1.0, "pitch_deg": -2.0, "heading_deg": 90.0, "grav": [0.0, 0.1, 9.8],
            "calib": {"sys": 3, "gyro": 3, "accel": 2, "mag": 1}},
    "gnss": {"fix": 1, "lat": 37.5, "lon": 127.0, "alt_m": 50.0, "speed_m_s": 3.0, "course_deg": 45.0,
             "hdop": 0.9, "sats": 12, "utc": "2026-11-17T10:15:00.000Z"},
    "pi": {"cpu_c": 55.0, "throttled_hex": "0x0", "under_voltage_now": False, "under_voltage_ever": False,
           "input_v": None, "disk_free_mb": 1000.0, "rec_bytes": 0},
}


def test_envelope_and_roundtrip_all_simple_sensors():
    for sensor, data in DATA.items():
        msg = CTX.make("reading", sensor=sensor, seq=3, data=data)
        for k in protocol.ENVELOPE:
            assert k in msg
        assert msg["v"] == 1 and msg["sim"] is True
        back = protocol.parse(protocol.dumps(msg))
        assert back == msg


def test_thermal_and_radar_roundtrip():
    rng = np.random.default_rng(1)
    temps = 280.0 + 50.0 * rng.random((192, 256))
    d = protocol.encode_thermal(temps, gain="low", shutter=False)
    msg = protocol.parse(protocol.dumps(CTX.make("reading", sensor="thermal", seq=0, data=d)))
    back = protocol.decode_thermal(msg["data"])
    assert back.shape == (192, 256) and back.dtype == np.float32
    assert np.max(np.abs(back - temps)) <= 0.5 / 64 + 1e-4

    iq = (rng.integers(-3000, 3000, (64, 12)) + 1j * rng.integers(-3000, 3000, (64, 12))).astype(np.complex64)
    rd = {"frame": 7, "range_res_m": 0.0488, "n_bins": 64, "range_profile_db": [1.0] * 64,
          "az_heatmap": protocol.encode_iq(iq), "points": [[0.1, 2.0, 0.0, -0.5, 12.3]], "tlv_types": [1, 2, 4, 7],
          "frame_ok": True}
    msg = protocol.parse(protocol.dumps(CTX.make("reading", sensor="radar", seq=0, data=rd)))
    assert np.array_equal(protocol.decode_iq(msg["data"]["az_heatmap"]), iq)


def test_thermal_quantisation_and_nonfinite():
    t = np.array([[300.0, np.nan], [np.inf, 1.0 / 64]])
    back = protocol.decode_thermal(protocol.encode_thermal(t))
    assert back[0, 0] == pytest.approx(300.0)
    assert back[0, 1] == 0.0 and back[1, 0] == 0.0          # non-finite -> 0 K = invalid marker
    assert back[1, 1] == pytest.approx(1.0 / 64)


def test_make_turns_nan_into_null_and_numpy_into_json():
    d = dict(DATA["tc_plate"], temp_c=float("nan"), cj_c=np.float32(21.5))
    msg = CTX.make("reading", sensor="tc_plate", seq=np.int64(4), data=d)
    assert msg["data"]["temp_c"] is None and msg["data"]["cj_c"] == 21.5 and msg["seq"] == 4
    json.loads(protocol.dumps(msg))


def test_heartbeat_hello_event():
    hb = CTX.make("heartbeat", sensor="unit", status="ok", detail="", last_reading_seq=None, rate_hz=None, seq=0)
    assert protocol.parse(protocol.dumps(hb))["sensor"] == "unit"
    h = CTX.make("hello", sensors=["thermal", "radar"], version="0.1.0", config_digest="abc")
    assert protocol.parse(protocol.dumps(h))["sensors"] == ["thermal", "radar"]
    e = CTX.make("event", kind="dropped", detail="3")
    assert protocol.parse(protocol.dumps(e))["kind"] == "dropped"


def _good():
    return CTX.make("reading", sensor="tc_plate", seq=0, data=DATA["tc_plate"])


@pytest.mark.parametrize("mutate", [
    lambda m: m.update(v=2),
    lambda m: m.update(v=True),
    lambda m: m.update(type="bogus"),
    lambda m: m.pop("t_mono"),
    lambda m: m.update(t_mono="12"),
    lambda m: m.update(sim="yes"),
    lambda m: m.update(unit_id=""),
    lambda m: m.update(session_id=None),
    lambda m: m.update(sensor="smoke"),
    lambda m: m.update(seq=-1),
    lambda m: m.update(seq=1.5),
    lambda m: m.update(seq=True),
    lambda m: m.pop("data"),
    lambda m: m["data"].pop("fault"),
    lambda m: m["data"].update(fault="melted"),
    lambda m: m["data"].update(temp_c="hot"),
    lambda m: m.update(data=[1, 2]),
])
def test_parse_rejects_malformed(mutate):
    m = _good()
    mutate(m)
    with pytest.raises(ProtocolError):
        protocol.parse(json.dumps(m))


@pytest.mark.parametrize("text", [
    "", "{", "[]", "null", "42", b"\xff\xfe",
    '{"v":1,"type":"reading","unit_id":"u","session_id":"s","sim":false,"t_mono":NaN,"t_utc":null,'
    '"sensor":"tc_air","seq":0,"data":{"temp_c":1,"cj_c":1,"fault":null}}',
    '{"v":1,"type":"reading","unit_id":"u","session_id":"s","sim":false,"t_mono":1,"t_utc":null,'
    '"sensor":"tc_air","seq":0,"data":{"temp_c":Infinity,"cj_c":1,"fault":null}}',
])
def test_parse_rejects_bad_text(text):
    with pytest.raises(ProtocolError):
        protocol.parse(text)


def test_heartbeat_validation():
    base = dict(sensor="imu", status="ok", detail="", last_reading_seq=3, rate_hz=20.0, seq=1)
    for bad in (dict(status="fine"), dict(sensor="engine"), dict(last_reading_seq=-2), dict(rate_hz="x"),
                dict(detail=None)):
        with pytest.raises(ProtocolError):
            CTX.make("heartbeat", **dict(base, **bad))
    for st in protocol.STATUSES:
        CTX.make("heartbeat", **dict(base, status=st))


def test_per_sensor_data_validation():
    with pytest.raises(ProtocolError):
        CTX.make("reading", sensor="gnss", seq=0, data=dict(DATA["gnss"], fix=3))
    with pytest.raises(ProtocolError):
        CTX.make("reading", sensor="imu", seq=0, data=dict(DATA["imu"], grav=[1, 2]))
    with pytest.raises(ProtocolError):
        CTX.make("reading", sensor="pi", seq=0, data=dict(DATA["pi"], under_voltage_now="no"))
    t = protocol.encode_thermal(np.full((4, 4), 300.0))
    with pytest.raises(ProtocolError):
        CTX.make("reading", sensor="thermal", seq=0, data=dict(t, enc="png"))
    with pytest.raises(ProtocolError):
        CTX.make("reading", sensor="radar", seq=0, data={"frame": 1, "range_res_m": 0.05, "n_bins": 2,
                                                         "range_profile_db": [1, 2], "az_heatmap": None,
                                                         "points": [[1, 2, 3]], "tlv_types": [], "frame_ok": True})


def test_decoders_reject_inconsistent_payloads():
    d = protocol.encode_thermal(np.full((4, 4), 300.0))
    with pytest.raises(ProtocolError):
        protocol.decode_thermal(dict(d, w=5))
    with pytest.raises(ProtocolError):
        protocol.decode_thermal(dict(d, pix="!!notbase64"))
    iq = protocol.encode_iq(np.ones((4, 3), dtype=np.complex64))
    with pytest.raises(ProtocolError):
        protocol.decode_iq(dict(iq, n_ant=5))
    with pytest.raises(ProtocolError):
        protocol.decode_iq(dict(iq, enc="f32"))


def test_make_requires_ids_and_defaults_time():
    with pytest.raises(ProtocolError):
        protocol.make("event", kind="x", detail="")
    m = protocol.make("event", unit_id="VU-01", session_id="s", kind="x", detail="", t_mono=5.0, t_utc=None)
    assert m["t_mono"] == 5.0 and m["t_utc"] is None and m["sim"] is False
    m2 = protocol.make("event", unit_id="VU-01", session_id="s", kind="x", detail="")
    assert math.isfinite(m2["t_mono"]) and m2["t_utc"].endswith("Z")


def test_extra_keys_allowed_and_digest_stable():
    m = _good()
    m["extra"] = {"anything": 1}
    protocol.parse(json.dumps(m))
    assert protocol.config_digest({"a": 1, "b": [1, 2]}) == protocol.config_digest({"b": [1, 2], "a": 1})
    assert protocol.make_session_id("VU-01", 0.0) == "VU-01-19700101T000000Z"
