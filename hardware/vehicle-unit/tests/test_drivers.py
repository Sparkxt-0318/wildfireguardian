"""Drivers without hardware: pure decoders on datasheet/known values, live loops on fake devices, sim mode.

Fake devices here are test doubles, not recordings of real hardware.
"""
import struct
import threading
import time

import numpy as np
import pytest

from wfgvu import protocol, recorder, replay
from wfgvu.drivers import base, bno055, gnss_nmea, max31855, pi_health, thermal_tc001, tlv
from wfgvu.drivers.radar_iwr6843 import RadarDriver, cfg_lines, send_cli_config

CTX = protocol.Context(unit_id="VU-01", session_id="VU-01-TEST", sim=False)


class Sink:
    def __init__(self):
        self.msgs = []
        self.lock = threading.Lock()

    def __call__(self, m):
        with self.lock:
            self.msgs.append(m)

    def of(self, mtype, sensor=None):
        with self.lock:
            return [m for m in self.msgs if m["type"] == mtype and (sensor is None or m.get("sensor") == sensor)]


def wait_for(pred, timeout=3.0):
    t_end = time.monotonic() + timeout
    while time.monotonic() < t_end:
        if pred():
            return True
        time.sleep(0.02)
    return False


# ----------------------------------------------------------------------------------------------- MAX31855

TC_TABLE = [(1600.00, 0x1900), (1000.00, 0x0FA0), (100.75, 0x0193), (25.00, 0x0064), (0.00, 0x0000),
            (-0.25, 0x3FFF), (-1.00, 0x3FFC), (-250.00, 0x3C18)]          # datasheet Table 2 (14-bit)
CJ_TABLE = [(127.0000, 0x7F0), (100.5625, 0x649), (25.0000, 0x190), (0.0000, 0x000), (-0.0625, 0xFFF),
            (-1.0000, 0xFF0), (-20.0000, 0xEC0), (-55.0000, 0xC90)]       # datasheet Table 4 (12-bit)


@pytest.mark.parametrize("tc_c,tc_bits", TC_TABLE)
@pytest.mark.parametrize("cj_c,cj_bits", CJ_TABLE[::3])
def test_max31855_datasheet_words(tc_c, tc_bits, cj_c, cj_bits):
    word = (tc_bits << 18) | (cj_bits << 4)
    if word in (0, 0xFFFFFFFF):
        word |= 1 << 17                     # reserved bit, keeps the all-zero word distinct from "no chip"
    d = max31855.decode_max31855(word)
    assert d["fault"] is None
    assert d["temp_c"] == pytest.approx(tc_c)
    assert d["cj_c"] == pytest.approx(cj_c)
    w = max31855.encode_max31855(tc_c, cj_c)
    if w:                                   # 0.00 C hot and cold reads as all zeros = "no chip" (fail closed)
        assert max31855.decode_max31855(w)["temp_c"] == pytest.approx(tc_c)


def test_max31855_faults():
    base_word = (0x0064 << 18) | (0x190 << 4)
    for bit, name in ((1, "open"), (2, "short_gnd"), (4, "short_vcc")):
        d = max31855.decode_max31855(base_word | bit | (1 << 16))
        assert d["fault"] == name and d["temp_c"] is None and d["cj_c"] == pytest.approx(25.0)
    assert max31855.decode_max31855(0)["fault"] == "spi"
    assert max31855.decode_max31855(0xFFFFFFFF)["fault"] == "spi"
    assert max31855.decode_max31855(base_word | (1 << 16))["fault"] == "spi"
    assert max31855.word_from_bytes([0x01, 0x90, 0x19, 0x00]) == 0x01901900


class FakeSPI:
    def __init__(self, words):
        self.words = list(words)
        self.i = 0

    def readbytes(self, n):
        w = self.words[min(self.i, len(self.words) - 1)]
        self.i += 1
        return list(struct.pack(">I", w))

    def close(self):
        pass


def test_max31855_driver_live_fault_and_missing_chip():
    ok = max31855.encode_max31855(300.0, 25.0)
    flt = max31855.encode_max31855(300.0, 25.0, fault="open")
    sink = Sink()
    d = max31855.Max31855Driver("tc_plate", {"rate_hz": 50}, sink, ctx=CTX,
                                spi_factory=lambda: FakeSPI([ok] * 6 + [flt] * 1000)).start()
    try:
        assert wait_for(lambda: any(m["status"] == "error" for m in sink.of("heartbeat")))
        rs = sink.of("reading", "tc_plate")
        d0 = rs[0]["data"]
        assert {k: d0[k] for k in ("temp_c", "cj_c", "fault")} == {"temp_c": 300.0, "cj_c": 25.0, "fault": None}
        assert d0["bits"] == "0x%08X" % ok and d0["fault_bit"] is False          # VU-R6: raw word kept
        assert any(r["data"]["fault"] == "open" for r in rs)
        hb = [m for m in sink.of("heartbeat") if m["status"] == "error"][0]
        assert "open" in hb["detail"]
    finally:
        d.stop()
    sink2 = Sink()
    d2 = max31855.Max31855Driver("tc_air", {"retry_s": 0.1}, sink2, ctx=CTX,
                                 spi_factory=lambda: FakeSPI([0])).start()
    try:
        assert wait_for(lambda: any(m["status"] == "no_device" for m in sink2.of("heartbeat")))
        assert not sink2.of("reading")
    finally:
        d2.stop()


# ----------------------------------------------------------------------------------------------- BNO055

def test_bno055_decoders():
    eul = struct.pack("<hhh", 16 * 90, -16 * 3, 16 * 5)            # heading 90, roll -3, pitch 5
    grv = struct.pack("<hhh", 0, -98, 971)
    e = bno055.decode_euler(eul)
    assert e == {"heading_deg": 90.0, "roll_deg": -3.0, "pitch_deg": 5.0}
    assert bno055.decode_gravity(grv) == pytest.approx([0.0, -0.98, 9.71])
    assert bno055.decode_calib(0b11100100) == {"sys": 3, "gyro": 2, "accel": 1, "mag": 0}
    r = bno055.to_reading(eul, grv, 0xFF, pitch_sign=-1.0)
    assert r["pitch_deg"] == -5.0 and r["roll_deg"] == -3.0 and r["calib"]["sys"] == 3
    neg = bno055.to_reading(struct.pack("<hhh", -16, 0, 0), grv, 0)
    assert neg["heading_deg"] == pytest.approx(359.0)


class FakeBus:
    def __init__(self, present=True):
        self.present = present
        self.writes = []
        self.mem = {bno055.REG_CHIP_ID: bno055.CHIP_ID, bno055.REG_CALIB_STAT: 0xFF}
        self.eul = list(struct.pack("<hhh", 160, 16, -32))
        self.grv = list(struct.pack("<hhh", 0, 0, 981))

    def read_byte_data(self, addr, reg):
        if not self.present:
            raise OSError(121, "Remote I/O error")
        return self.mem.get(reg, 0)

    def write_byte_data(self, addr, reg, val):
        self.writes.append((reg, val))
        self.mem[reg] = val                          # registers keep what was written (OPR_MODE read back)

    def read_i2c_block_data(self, addr, reg, n):
        return self.eul if reg == bno055.REG_EUL else self.grv

    def close(self):
        pass


def test_bno055_driver_live_and_absent():
    sink = Sink()
    bus = FakeBus()
    d = bno055.Bno055Driver("imu", {"rate_hz": 50}, sink, ctx=CTX, bus_factory=lambda: bus).start()
    try:
        assert wait_for(lambda: len(sink.of("reading", "imu")) >= 3)
        r = sink.of("reading", "imu")[0]["data"]
        assert r["heading_deg"] == 10.0 and r["roll_deg"] == 1.0 and r["pitch_deg"] == -2.0
        assert (bno055.REG_OPR_MODE, bno055.MODE_NDOF) in bus.writes
    finally:
        d.stop()
    sink2 = Sink()
    d2 = bno055.Bno055Driver("imu", {"retry_s": 0.1}, sink2, ctx=CTX,
                             bus_factory=lambda: FakeBus(present=False)).start()
    try:
        assert wait_for(lambda: any(m["status"] == "no_device" and "BNO055" in m["detail"]
                                    for m in sink2.of("heartbeat")), 4.0)
    finally:
        d2.stop()


# ----------------------------------------------------------------------------------------------- GNSS

def nmea(body):
    return "$%s*%02X" % (body, gnss_nmea.checksum(body))


def test_nmea_classic_examples():
    gga = gnss_nmea.parse_sentence("$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47")
    assert gga["lat"] == pytest.approx(48 + 7.038 / 60) and gga["lon"] == pytest.approx(11 + 31.0 / 60)
    assert gga["quality"] == 1 and gga["sats"] == 8 and gga["hdop"] == 0.9 and gga["alt_m"] == 545.4
    rmc = gnss_nmea.parse_sentence("$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A")
    assert rmc["valid"] and rmc["date"] == "2094-03-23"      # two-digit years are read as 20yy
    assert rmc["speed_m_s"] == pytest.approx(22.4 * 0.514444) and rmc["course_deg"] == 84.4
    vtg = gnss_nmea.parse_sentence("$GPVTG,054.7,T,034.4,M,005.5,N,010.2,K*48")
    assert vtg["course_deg"] == 54.7 and vtg["speed_m_s"] == pytest.approx(10.2 / 3.6)


def test_nmea_checksum_and_garbage():
    with pytest.raises(gnss_nmea.NMEAError):
        gnss_nmea.split_sentence("$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*48")
    with pytest.raises(gnss_nmea.NMEAError):
        gnss_nmea.split_sentence("GPGGA,no dollar")
    with pytest.raises(gnss_nmea.NMEAError):
        gnss_nmea.split_sentence("$GPGGA,missing checksum")
    assert gnss_nmea.parse_latlon("3730.0000", "S") == pytest.approx(-37.5)
    assert gnss_nmea.parse_latlon("12700.6000", "W") == pytest.approx(-127.01)
    assert gnss_nmea.parse_latlon("", "N") is None and gnss_nmea.parse_latlon("3799.0", "N") is None


def test_gnss_assembler_epochs_fix_and_nofix():
    a = gnss_nmea.GnssAssembler()
    out = []
    out += a.feed(nmea("GNRMC,101500.00,A,3730.0000,N,12700.0000,E,10.0,45.0,171126,,,A"))
    out += a.feed(nmea("GNVTG,45.0,T,,M,10.0,N,18.52,K,A"))
    out += a.feed(nmea("GNGGA,101500.00,3730.0000,N,12700.0000,E,2,14,0.8,51.2,M,20.0,M,,"))
    assert len(out) == 1
    r = out[0]
    assert r["fix"] == 2 and r["lat"] == pytest.approx(37.5) and r["lon"] == pytest.approx(127.0)
    assert r["speed_m_s"] == pytest.approx(18.52 / 3.6) and r["course_deg"] == 45.0
    assert r["utc"] == "2026-11-17T10:15:00.000Z" and r["sats"] == 14 and r["alt_m"] == 51.2
    protocol.make("reading", unit_id="u", session_id="s", sensor="gnss", seq=0, data=r)
    # no fix: GGA quality 0 and RMC void -> all position fields null
    out = a.feed(nmea("GNRMC,101501.00,V,,,,,,,171126,,,N")) + a.feed(nmea("GNGGA,101501.00,,,,,0,00,99.9,,M,,M,,"))
    assert out[0]["fix"] == 0 and out[0]["lat"] is None and out[0]["speed_m_s"] is None
    # dead reckoning (6) is not a fix
    out = a.feed(nmea("GNGGA,101502.00,3730.0,N,12700.0,E,6,05,2.0,50.0,M,,M,,"))
    out += a.feed(nmea("GNGGA,101503.00,3730.0,N,12700.0,E,1,05,2.0,50.0,M,,M,,"))   # newer time flushes
    assert out[0]["fix"] == 0
    assert a.feed("$GNGGA,bad*00") == [] and a.bad == 1


class FakeSerialLines:
    def __init__(self, lines):
        self.lines = [ln.encode() + b"\r\n" for ln in lines]

    def readline(self):
        if self.lines:
            return self.lines.pop(0)
        time.sleep(0.02)
        return b""

    def close(self):
        pass


def test_gnss_driver_live():
    lines = []
    for k in range(3):
        t = "1015%02d.00" % k
        lines += [nmea("GPRMC,%s,A,3730.0000,N,12700.0000,E,0.0,,171126,,,A" % t),
                  nmea("GPGGA,%s,3730.0000,N,12700.0000,E,1,09,1.1,40.0,M,,M,," % t)]
    sink = Sink()
    d = gnss_nmea.GnssDriver("gnss", {}, sink, ctx=CTX, serial_factory=lambda: FakeSerialLines(lines)).start()
    try:
        assert wait_for(lambda: len(sink.of("reading", "gnss")) == 3)
        assert [m["seq"] for m in sink.of("reading", "gnss")] == [0, 1, 2]
        assert sink.of("reading", "gnss")[0]["data"]["course_deg"] is None
    finally:
        d.stop()


# ----------------------------------------------------------------------------------------------- Pi health

def test_pi_health_parsers_and_macos_tolerance(tmp_path):
    t = pi_health.parse_throttled("throttled=0x50005\n")
    assert t == {"throttled_hex": "0x50005", "under_voltage_now": True, "under_voltage_ever": True}
    assert pi_health.parse_throttled("throttled=0x0")["under_voltage_now"] is False
    assert pi_health.parse_throttled(None)["throttled_hex"] is None
    assert pi_health.parse_ext5v("EXT5V_V volt(24)=5.13421000V") == pytest.approx(5.13421)
    assert pi_health.parse_ext5v("") is None
    zone = tmp_path / "temp"
    zone.write_text("48312\n")
    assert pi_health.read_cpu_c(zone) == pytest.approx(48.312)
    assert pi_health.read_cpu_c(tmp_path / "missing") is None
    d = pi_health.collect(tmp_path, lambda: 1234, cmd=lambda args: None, cpu_path=tmp_path / "missing")
    assert d["cpu_c"] is None and d["throttled_hex"] is None and d["input_v"] is None
    assert d["disk_free_mb"] > 0 and d["rec_bytes"] == 1234
    protocol.make("reading", unit_id="u", session_id="s", sensor="pi", seq=0, data=d)
    # whatever this machine is (macOS dev box or a Pi), collect() must not raise
    pi_health.collect(tmp_path)


# ----------------------------------------------------------------------------------------------- thermal

def test_tc001_split_frame_lower_half_raw():
    raw = (np.arange(192 * 256, dtype=np.uint32) % 65536).astype(np.uint16).reshape(192, 256)
    raw[10, 20] = int(round((273.15 + 400.0) * 64))
    buf = thermal_tc001.frame_from_raw(raw)
    upper, got = thermal_tc001.split_frame(buf.reshape(1, -1))           # OpenCV may hand over a flat row
    assert np.array_equal(got, raw) and upper.shape == (192, 256, 2)
    k = thermal_tc001.raw_to_kelvin(got)
    assert k[10, 20] - 273.15 == pytest.approx(400.0, abs=1 / 64)
    with pytest.raises(ValueError):
        thermal_tc001.split_frame(np.zeros((192, 256, 2), np.uint8))


class FakeCapture:
    def __init__(self, frames, fail_after=None):
        self.frames, self.i, self.fail_after = frames, 0, fail_after

    def read(self):
        time.sleep(0.01)
        if self.fail_after is not None and self.i >= self.fail_after:
            return False, None
        f = self.frames[min(self.i, len(self.frames) - 1)]
        self.i += 1
        return True, f

    def release(self):
        pass


def test_tc001_driver_live_and_unplug():
    rng = np.random.default_rng(3)
    raws = [rng.integers(18000, 20000, (192, 256)).astype(np.uint16) for _ in range(3)]
    frames = [thermal_tc001.frame_from_raw(r) for r in raws]
    sink = Sink()
    caps = iter([FakeCapture(frames + [frames[-1]], fail_after=5)])

    def factory():
        return next(caps)                                   # second open fails: StopIteration -> no_device

    d = thermal_tc001.ThermalTC001Driver("thermal", {"retry_s": 0.1}, sink, ctx=CTX,
                                         capture_factory=factory).start()
    try:
        assert wait_for(lambda: any(m["status"] == "no_device" for m in sink.of("heartbeat")
                                    if sink.of("reading", "thermal")))
        rs = sink.of("reading", "thermal")
        k = protocol.decode_thermal(rs[0]["data"])
        assert np.allclose(k, raws[1] / 64.0)               # frame 0 was consumed by open()'s probe
        assert rs[-1]["data"]["shutter"] is True            # repeated frame flagged by the heuristic
    finally:
        d.stop()


# ----------------------------------------------------------------------------------------------- radar

class FakeCLI:
    def __init__(self, reject=()):
        self.out = b""
        self.reject = reject
        self.lines = []

    def write(self, b):
        line = b.decode().strip()
        self.lines.append(line)
        resp = line + ("\nError -1\n" if line.split()[0] in self.reject else "\nDone\nmmwDemo:/>")
        self.out += resp.encode()

    def read(self, n):
        chunk, self.out = self.out[:n], self.out[n:]
        return chunk

    def close(self):
        pass


class FakeData:
    def __init__(self, data):
        self.data = data

    def read(self, n):
        time.sleep(0.005)
        chunk, self.data = self.data[:n], self.data[n:]
        return chunk

    def close(self):
        pass


def test_cli_config_send_and_lines():
    lines = cfg_lines("% comment\nsensorStop\n\nprofileCfg 0 60 % trailing\n# hash\nsensorStart\n")
    assert lines == ["sensorStop", "profileCfg 0 60", "sensorStart"]
    res = send_cli_config(FakeCLI(reject=("profileCfg",)), lines, timeout_s=0.2)
    assert [r["status"] for r in res] == ["done", "error", "done"]


def test_radar_driver_live_with_fake_uarts():
    from wfgvu.drivers.radar_iwr6843 import load_profile
    prof = load_profile()
    rng = np.random.default_rng(5)
    frames = []
    for n in range(4):
        rp = tlv.pack_range_profile(rng.integers(0, 5000, prof.n_bins))
        hm = tlv.pack_heatmap(rng.integers(-100, 100, (prof.n_bins, 12)) + 0j)
        frames.append(tlv.build_frame(n, [(2, rp), (4, hm)]))
    stream = b"\x00garbage" + b"".join(frames)
    raw = []
    cli = FakeCLI()
    ports = {"/dev/cli": cli, "/dev/data": FakeData(stream)}
    sink = Sink()
    d = RadarDriver("radar", {"cli_port": "/dev/cli", "data_port": "/dev/data", "cli_timeout_s": 0.2}, sink,
                    ctx=CTX, raw_sink=raw.append, serial_factory=lambda p, b, t: ports[p]).start()
    try:
        assert wait_for(lambda: len(sink.of("reading", "radar")) == 4, 5.0)
        sent = [m for m in sink.of("event") if m["kind"] == "radar_config_sent"]
        assert sent and "iwr6843aop_vu.cfg" in sent[0]["detail"] and "OVER UART BUDGET" not in sent[0]["detail"]
        assert cli.lines[0] == "sensorStop" and cli.lines[-1] == "sensorStart"
        r = sink.of("reading", "radar")[0]["data"]
        assert r["frame_ok"] and r["n_bins"] == prof.n_bins == 128 and r["tlv_types"] == [2, 4] and r["points"] == []
        assert b"".join(raw) == stream                       # every UART byte reached the recorder hook
    finally:
        d.stop()


def test_radar_driver_config_rejected_reports_no_device():
    ports = {"/dev/cli": FakeCLI(reject=("profileCfg",)), "/dev/data": FakeData(b"")}
    sink = Sink()
    d = RadarDriver("radar", {"cli_port": "/dev/cli", "data_port": "/dev/data", "cli_timeout_s": 0.1,
                              "retry_s": 5}, sink, ctx=CTX, serial_factory=lambda p, b, t: ports[p]).start()
    try:
        assert wait_for(lambda: any(m["status"] == "no_device" and "profileCfg" in m["detail"]
                                    for m in sink.of("heartbeat")), 6.0)
    finally:
        d.stop()


# ----------------------------------------------------------------------------------------------- base behaviour

class FlakyDriver(base.Driver):
    """Device absent for the first ``absent`` opens, then gives readings until ``n_readings`` then goes quiet."""

    def __init__(self, *a, absent=2, n_readings=5, **k):
        super().__init__(*a, **k)
        self.absent, self.n, self.opens = absent, n_readings, 0

    def open(self):
        self.opens += 1
        if self.opens <= self.absent:
            raise base.DeviceUnavailable("not plugged in")

    def read(self):
        self.sleep(0.02)
        if self.n > 0:
            self.n -= 1
            return [{"temp_c": 20.0, "cj_c": 20.0, "fault": None}]
        return []


def test_base_retry_reconnect_stale_and_stop():
    sink = Sink()
    d = FlakyDriver("tc_housing", {"retry_s": 0.15, "stale_s": 0.3}, sink, ctx=CTX).start()
    try:
        assert wait_for(lambda: len(sink.of("reading")) == 5, 3.0)
        hbs = sink.of("heartbeat")
        assert hbs[0]["status"] == "no_device" and "not plugged in" in hbs[0]["detail"]
        assert d.opens == 3
        assert any(e["kind"] == "sensor_reconnected" for e in sink.of("event"))
        assert wait_for(lambda: sink.of("heartbeat")[-1]["status"] == "stale", 2.0)
        assert [m["seq"] for m in sink.of("reading")] == [0, 1, 2, 3, 4]
        assert sink.of("heartbeat")[-1]["last_reading_seq"] == 4
    finally:
        d.stop()
    last = sink.of("heartbeat")[-1]
    assert last["status"] == "no_device" and last["detail"] == "driver stopped"
    seqs = [m["seq"] for m in sink.of("heartbeat")]
    assert seqs == list(range(len(seqs)))


def test_base_heartbeat_period_and_rate():
    sink = Sink()

    class Steady(base.Driver):
        def open(self):
            pass

        def read(self):
            self.sleep(0.05)
            return [{"temp_c": 1.0, "cj_c": 1.0, "fault": None}]

    d = Steady("tc_air", {}, sink, ctx=CTX).start()
    try:
        time.sleep(1.6)
    finally:
        d.stop()
    hbs = [m for m in sink.of("heartbeat") if m["status"] == "ok"]
    assert len(hbs) >= 2
    gaps = np.diff([m["t_mono"] for m in hbs])
    assert np.all(gaps < 0.65)
    assert 12.0 < hbs[-1]["rate_hz"] < 22.0


# ----------------------------------------------------------------------------------------------- sim mode

def _session(tmp_path, n=6, dt=0.05):
    """A tiny synthetic session with one reading stream per sensor (illustrative values, not measurements)."""
    ctx = protocol.Context("VU-01", "VU-01-SYNTH", sim=True)
    datas = {
        "thermal": protocol.encode_thermal(np.full((4, 6), 300.0)),
        "radar": {"frame": 1, "range_res_m": 0.05, "n_bins": 3, "range_profile_db": [1.0, 2.0, 3.0],
                  "az_heatmap": protocol.encode_iq(np.ones((3, 2), np.complex64)), "points": [],
                  "tlv_types": [2, 4], "frame_ok": True},
        "tc_plate": {"temp_c": 40.0, "cj_c": 25.0, "fault": None},
        "tc_housing": {"temp_c": 35.0, "cj_c": 25.0, "fault": None},
        "tc_air": {"temp_c": 30.0, "cj_c": 25.0, "fault": None},
        "imu": {"roll_deg": 0.0, "pitch_deg": 1.0, "heading_deg": 10.0, "grav": [0, 0, 9.81],
                "calib": {"sys": 3, "gyro": 3, "accel": 3, "mag": 3}},
        "gnss": {"fix": 1, "lat": 37.5, "lon": 127.0, "alt_m": 40.0, "speed_m_s": 0.0, "course_deg": None,
                 "hdop": 1.0, "sats": 9, "utc": None},
        "pi": {"cpu_c": 50.0, "throttled_hex": "0x0", "under_voltage_now": False, "under_voltage_ever": False,
               "input_v": None, "disk_free_mb": 5000.0, "rec_bytes": 0},
    }
    msgs = []
    for i in range(n):
        for s, d in datas.items():
            msgs.append(ctx.make("reading", sensor=s, seq=i, data=d, t_mono=1000.0 + i * dt))
    return recorder.write_session(tmp_path / "sess", {"unit_id": "VU-01", "session_id": "VU-01-SYNTH"}, msgs), datas


DRIVER_CLASSES = {"thermal": thermal_tc001.ThermalTC001Driver, "radar": RadarDriver,
                  "tc_plate": max31855.Max31855Driver, "tc_housing": max31855.Max31855Driver,
                  "tc_air": max31855.Max31855Driver, "imu": bno055.Bno055Driver, "gnss": gnss_nmea.GnssDriver,
                  "pi": pi_health.PiHealthDriver}


def test_every_driver_runs_in_sim_mode_from_a_recorded_file(tmp_path):
    path, datas = _session(tmp_path)
    sess = replay.load(path)
    ctx = protocol.Context("VU-01", "VU-01-REPLAY", sim=True)
    sink = Sink()
    drivers = [DRIVER_CLASSES[s](s, {}, sink, sess.streams[s], ctx=ctx) for s in protocol.SENSORS]
    sess.start(speed=2.0)
    for d in drivers:
        d.start()
    try:
        assert wait_for(lambda: all(any(m["status"] == "sim_ended" for m in sink.of("heartbeat", s))
                                    for s in protocol.SENSORS), 4.0)
    finally:
        for d in drivers:
            d.stop()
    for s in protocol.SENSORS:
        rs = sink.of("reading", s)
        assert len(rs) == 6, s
        assert all(r["sim"] is True and r["session_id"] == "VU-01-REPLAY" for r in rs)
        assert rs[0]["data"] == protocol.sanitize(datas[s])
        gaps = np.diff([r["t_mono"] for r in rs])
        assert np.all(gaps > 0.01) and np.all(gaps < 0.08)  # recorded 0.05 s at speed 2 -> 0.025 s


# ------------------------------------------------------------------------- VU-R2 / VU-R3 / VU-R6 regression tests

class ResettingBus(FakeBus):
    """A BNO055 that resets (brown-out) after ``after`` NDOF readings: CONFIG mode, UNIT_SEL 0x80, all-zero fusion
    registers, until the driver writes NDOF again."""

    def __init__(self, after=5):
        super().__init__()
        self.after, self.n = after, 0

    def read_i2c_block_data(self, addr, reg, n):
        if reg == bno055.REG_EUL:
            self.n += 1
            if self.n == self.after:
                self.mem.update({bno055.REG_OPR_MODE: bno055.MODE_CONFIG, bno055.REG_UNIT_SEL: 0x80,
                                 bno055.REG_CALIB_STAT: 0x00})
        if self.mem.get(bno055.REG_OPR_MODE) != bno055.MODE_NDOF:
            return [0] * 6
        return super().read_i2c_block_data(addr, reg, n)


def test_bno055_chip_reset_is_detected_and_reinitialised():
    """VU-R2: after a chip reset (CONFIG mode, zero registers) read() raises, the base loop re-opens the chip and
    open() writes PAGE 0, UNIT_SEL 0 and NDOF again; no all-zero reading is published as good."""
    sink = Sink()
    bus = ResettingBus(after=5)
    d = bno055.Bno055Driver("imu", {"rate_hz": 50, "retry_s": 0.1}, sink, ctx=CTX, bus_factory=lambda: bus).start()
    try:
        assert wait_for(lambda: bus.writes.count((bno055.REG_OPR_MODE, bno055.MODE_NDOF)) >= 2, 4.0)
        assert (bno055.REG_PAGE_ID, 0) in bus.writes and bus.writes.count((bno055.REG_UNIT_SEL, 0x00)) >= 2
        assert any(m["status"] == "error" and "NDOF" in m["detail"] for m in sink.of("heartbeat", "imu"))
        assert wait_for(lambda: any(m["type"] == "event" and m["kind"] == "sensor_reconnected" for m in sink.msgs))
        for r in sink.of("reading", "imu"):
            assert r["data"]["grav"] != [0.0, 0.0, 0.0]
    finally:
        d.stop()


def test_bno055_assess_rejects_implausible_gravity_and_reports_calibration():
    d = bno055.Bno055Driver("imu", {}, Sink(), ctx=CTX)
    good = {"roll_deg": 1.0, "pitch_deg": -2.0, "heading_deg": 0.0, "grav": [0.0, 0.0, 9.81],
            "calib": {"sys": 3, "gyro": 3, "accel": 3, "mag": 3}}
    assert d.assess(good) == (True, "")
    assert d.assess(dict(good, grav=[0.0, 0.0, 0.0]))[0] is False
    assert d.assess(dict(good, grav=[0.0, 0.0, 13.0]))[0] is False
    zero = {"roll_deg": 0.0, "pitch_deg": 0.0, "heading_deg": 0.0, "grav": [0.0, 0.0, 0.0],
            "calib": {"sys": 0, "gyro": 0, "accel": 0, "mag": 0}}
    assert d.assess(zero) == (False, "all-zero reading (chip reset?)")
    ok, why = d.assess(dict(good, calib={"sys": 0, "gyro": 3, "accel": 3, "mag": 1}))
    assert ok and "calib sys=0" in why


class SilentData:
    """Open data UART that never delivers a byte (stalled stock demo) or only garbage."""

    def __init__(self, garbage=False):
        self.garbage = garbage

    def read(self, n):
        time.sleep(0.01)
        return b"\x11\x22\x33" * 10 if self.garbage else b""

    def close(self):
        pass


@pytest.mark.parametrize("garbage", [False, True])
def test_radar_watchdog_reopens_a_silent_or_garbage_only_radar(garbage):
    """VU-R3: an open radar whose data UART delivers no complete frame (silent, or bytes that never form a frame)
    raises after frame_watchdog_s, so the base loop closes (sensorStop) and re-opens it (config sent again)."""
    opens = []

    def factory(port, baud, timeout):
        opens.append(port)
        return FakeCLI() if port == "/dev/cli" else SilentData(garbage)

    sink = Sink()
    d = RadarDriver("radar", {"cli_port": "/dev/cli", "data_port": "/dev/data", "cli_timeout_s": 0.05,
                              "frame_watchdog_s": 0.4, "retry_s": 0.1}, sink, ctx=CTX, serial_factory=factory).start()
    try:
        assert wait_for(lambda: opens.count("/dev/cli") >= 2, 2 * (0.4 + 0.1) + 2.0)
        assert any(m["kind"] == "radar_watchdog" for m in sink.of("event"))
        assert any(m["status"] == "error" and "no radar frames" in m["detail"] for m in sink.of("heartbeat"))
        if garbage:
            assert wait_for(lambda: any("garbage_bytes=" in m["detail"] for m in sink.of("event")
                                        if m["kind"] == "radar_watchdog"))
    finally:
        d.stop()


def test_gnss_raw_lines_and_rejected_sentences_reach_recording_and_heartbeat():
    """VU-R6: every raw NMEA line (bad checksum, GSV included) goes to raw_sink with a Pi time stamp, and the
    rejected-sentence count appears in the live heartbeat detail."""
    good = nmea("GPRMC,101500.00,A,3730.0000,N,12700.0000,E,0.0,,171126,,,A")
    bad = good[:-2] + "00"                                       # wrong checksum
    gsv = nmea("GPGSV,1,1,01,01,40,083,46")
    raw = []
    sink = Sink()
    d = gnss_nmea.GnssDriver("gnss", {}, sink, ctx=CTX, raw_sink=raw.append,
                             serial_factory=lambda: FakeSerialLines([bad, bad, gsv, bad, good])).start()
    try:
        assert wait_for(lambda: len(raw) == 5)
        assert all(re_line.split(b" ", 1)[0].replace(b".", b"").isdigit() for re_line in raw)
        assert raw[2].split(b" ", 1)[1].startswith(b"$GPGSV")
        assert wait_for(lambda: any("nmea_bad=3" in m["detail"] for m in sink.of("heartbeat", "gnss")))
    finally:
        d.stop()


def test_radar_parser_counts_reach_heartbeat_detail():
    """VU-R6: FrameSync counters (frames / garbage / bad / truncated) are in the live radar heartbeat detail."""
    from wfgvu.drivers.radar_iwr6843 import load_profile
    prof = load_profile()
    rp = tlv.pack_range_profile(np.arange(prof.n_bins) % 50)
    good = tlv.build_frame(0, [(2, rp)])
    broken = bytearray(tlv.build_frame(1, [(2, rp)]))
    broken[12:16] = struct.pack("<I", 40)                         # totalPacketLen too short for its TLVs
    stream = b"junk" + good + bytes(broken) + good
    ports = {"/dev/cli": FakeCLI(), "/dev/data": FakeData(stream)}
    sink = Sink()
    d = RadarDriver("radar", {"cli_port": "/dev/cli", "data_port": "/dev/data", "cli_timeout_s": 0.05,
                              "frame_watchdog_s": 30}, sink, ctx=CTX, serial_factory=lambda p, b, t: ports[p]).start()
    try:
        assert wait_for(lambda: any("garbage_bytes=" in m["detail"] and "frames=" in m["detail"]
                                    for m in sink.of("heartbeat", "radar")), 4.0)
    finally:
        d.stop()
