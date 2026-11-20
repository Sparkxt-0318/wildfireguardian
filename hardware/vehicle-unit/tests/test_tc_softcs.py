"""MAX31855 software chip select (tc_air on GPIO5) and the shared SPI0 bus, with fakes only (no hardware).

The fakes (``max31855.FakeBench`` and the small doubles below) model the documented behaviour of spidev ``no_cs``
(a property of the shared spi_device) and of a GPIO line; they are not recordings of a real Pi.
"""
import struct
import threading
import time
from pathlib import Path

import pytest
import yaml

from wfgvu import protocol
from wfgvu import __main__ as unit_main
from wfgvu.drivers import max31855 as mx

CTX = protocol.Context(unit_id="VU-01", session_id="VU-01-TEST", sim=False)
ROOT = Path(__file__).resolve().parents[1]
PLATE = {"spi_bus": 0, "spi_dev": 0}
HOUSING = {"spi_bus": 0, "spi_dev": 1}
AIR = {"spi_bus": 0, "spi_dev": 0, "cs_gpio": 5}


def drivers(bench, bus=None, **air_extra):
    bus = bus or bench.bus(0)
    out = {}
    for name, c in (("tc_plate", PLATE), ("tc_housing", HOUSING), ("tc_air", dict(AIR, **air_extra))):
        out[name] = mx.Max31855Driver(name, c, lambda m: None, ctx=CTX, bus=bus,
                                      spi_factory=lambda c=c: bench.spi_factory(c["spi_bus"], c["spi_dev"]))
    return out, bus


def test_config_pin_map_matches_build_manual():
    cfg = yaml.safe_load((ROOT / "config" / "unit.yaml").read_text())
    s = cfg["sensors"]
    assert (s["tc_plate"]["spi_bus"], s["tc_plate"]["spi_dev"], s["tc_plate"].get("cs_gpio")) == (0, 0, None)
    assert (s["tc_housing"]["spi_bus"], s["tc_housing"]["spi_dev"], s["tc_housing"].get("cs_gpio")) == (0, 1, None)
    assert (s["tc_air"]["spi_bus"], s["tc_air"]["spi_dev"], s["tc_air"]["cs_gpio"]) == (0, 0, 5)
    assert s["tc_plate"]["disc_max_c"] == 70
    assert s["thermal"]["model"] == "InfiRay P2 Pro" and s["thermal"]["usb_id"] == "0bda:5830"
    assert s["thermal"]["index"] == "auto"
    text = (ROOT / "config" / "unit.yaml").read_text()
    assert "dtoverlay=spi1" not in text and "spi1-1cs" not in text and "GPIO18" not in text
    assert "spi_bus: 1" not in text
    off = cfg["mount"]["sensor_offsets_mm"]
    assert off == {"camera": {"x": -52, "z": 34, "hole_d": 12},
                   "radar": {"x": -8, "z": 34, "window_w": 52, "window_h": 42, "window_t": 1.2},
                   "flux_disc": {"x": 45, "z": 34, "hole_d": 30.6}}
    h = cfg["housing"]
    assert h["body_mm"] == [180, 140, 72] and h["wall_mm"] == 4 and h["pi_standoff_pattern_mm"] == [58, 49]
    assert h["floor_rails"] == 3 and h["rail_pilot_hole"] == "M3" and h["rail_hole_pitch_mm"] == 10
    assert h["front_plate_mm"] == [172, 66, 3] and h["sensor_centre_line_above_base_mm"] == 34
    assert h["heat_shield"] == {"material": "aluminium", "gap_mm": 10} and h["material"] == "PETG"
    assert cfg["mount"]["radar_height_m"] == cfg["mount"]["camera_height_m"]
    assert cfg["mount"]["plate_height_m"] == cfg["mount"]["camera_height_m"]     # flux disc on the same 34 mm line
    assert unit_main.config_warnings(cfg) == []


def test_config_warnings_height_mismatch_and_disc_limit():
    w = unit_main.config_warnings({"mount": {"camera_height_m": 2.6, "radar_height_m": 2.5},
                                   "sensors": {"tc_plate": {"disc_max_c": 90}}})
    assert any("radar_height_m" in x for x in w) and any("disc_max_c" in x for x in w)
    w = unit_main.config_warnings({"mount": {"camera_height_m": 2.6, "radar_height_m": 2.6, "plate_height_m": 2.5}})
    assert len(w) == 2 and any("plate_height_m (2.5)" in x for x in w)       # plate + missing disc_max_c
    assert mx.disc_max_c({"disc_max_c": 90}) == 70.0          # never above the user's 70 C
    assert mx.disc_max_c({"disc_max_c": 60}) == 60.0
    assert mx.disc_max_c({"disc_max_c": "x"}) == 70.0 and mx.disc_max_c({}) == 70.0


def test_hello_mount_carries_sensor_offsets():
    cfg = unit_main.load_config(ROOT / "config" / "unit.yaml")
    m = unit_main.hello_mount(cfg)
    assert m["sensor_offsets_mm"]["flux_disc"] == {"x": 45, "z": 34, "hole_d": 30.6}


def test_three_channels_read_their_own_chip():
    bench = mx.FakeBench(temps={"tc_plate": 30.0, "tc_housing": 40.0, "tc_air": 50.0})
    bench.exact |= {"tc_plate", "tc_housing", "tc_air"}
    ds, bus = drivers(bench)
    try:
        for d in ds.values():
            d.open()
        for _ in range(5):
            got = {n: d.read_once()["temp_c"] for n, d in ds.items()}
            assert got == {"tc_plate": 30.0, "tc_housing": 40.0, "tc_air": 50.0}
        assert bench.contention == 0
        assert all(len(sel) == 1 for sel in bench.log)
        assert bench.levels[5] == 1                          # CS idles high between transfers
    finally:
        for d in ds.values():
            d.close()
    assert 5 not in bench.levels                             # line released when the last channel closed


def test_shared_no_cs_is_restored_for_the_kernel_cs_channel():
    """no_cs belongs to the shared spi_device: after a tc_air read the plate read must turn it off again."""
    bench = mx.FakeBench(temps={"tc_plate": 30.0, "tc_air": 50.0})
    bench.exact |= {"tc_plate", "tc_air"}
    ds, bus = drivers(bench)
    try:
        ds["tc_air"].open()
        ds["tc_plate"].open()
        assert ds["tc_air"].read_once()["temp_c"] == 50.0
        assert bench.no_cs[(0, 0)] is True
        assert ds["tc_plate"].read_once()["temp_c"] == 30.0
        assert bench.no_cs[(0, 0)] is False
    finally:
        for d in ds.values():
            d.close()


def test_no_cs_refused_is_a_fault_and_nothing_is_read():
    bench = mx.FakeBench(no_cs_supported=False)
    ds, bus = drivers(bench)
    air = ds["tc_air"]
    with pytest.raises(mx.NoCsUnsupported, match="no_cs unsupported"):
        air.open()
    assert bench.log == []                                   # no transfer happened, CS never went low
    assert bench.levels.get(5) == 1
    air.close()
    assert 5 not in bench.levels


class ReadbackLiar:
    """spidev double whose no_cs never sticks (the controller ignores the bit)."""

    def __init__(self):
        self.reads = 0

    @property
    def no_cs(self):
        return False

    @no_cs.setter
    def no_cs(self, v):
        pass

    def readbytes(self, n):
        self.reads += 1
        return list(struct.pack(">I", mx.encode_max31855(25.0, 24.0)))

    def close(self):
        pass


def test_no_cs_readback_false_is_a_fault():
    bench = mx.FakeBench()
    spi = ReadbackLiar()
    d = mx.Max31855Driver("tc_air", AIR, lambda m: None, ctx=CTX, bus=bench.bus(0), spi_factory=lambda: spi)
    with pytest.raises(mx.NoCsUnsupported):
        d.open()
    assert spi.reads == 0
    d.close()


def test_no_cs_refused_in_live_loop_reports_no_device_and_never_reads():
    bench = mx.FakeBench(no_cs_supported=False)
    msgs = []
    lock = threading.Lock()

    def sink(m):
        with lock:
            msgs.append(m)

    d = mx.Max31855Driver("tc_air", dict(AIR, retry_s=0.05), sink, ctx=CTX, bus=bench.bus(0),
                          spi_factory=lambda: bench.spi_factory(0, 0)).start()
    try:
        t_end = time.monotonic() + 2.0
        while time.monotonic() < t_end:
            with lock:
                hb = [m for m in msgs if m["type"] == "heartbeat" and "no_cs unsupported" in m["detail"]]
            if hb:
                break
            time.sleep(0.02)
        assert hb and hb[0]["status"] == "no_device"
        with lock:
            assert not [m for m in msgs if m["type"] == "reading"]
        assert bench.log == []
    finally:
        d.stop()


class FailingSpi:
    def __init__(self, bench):
        self.bench = bench
        self._no_cs = False

    @property
    def no_cs(self):
        return self._no_cs

    @no_cs.setter
    def no_cs(self, v):
        self._no_cs = bool(v)

    def readbytes(self, n):
        assert self.bench.levels[5] == 0                     # CS was low during the transfer
        raise OSError(5, "Input/output error")

    def close(self):
        pass


def test_cs_released_when_the_transfer_raises():
    bench = mx.FakeBench()
    bus = bench.bus(0)
    bus.register_cs(5)
    bus.attach()
    try:
        with pytest.raises(OSError):
            bus.transfer(FailingSpi(bench), 4, cs_gpio=5)
        assert bench.levels[5] == 1                          # released in finally
        assert not bus.lock.locked()
        assert bus.broken is None
    finally:
        bus.detach()


def test_cs_stuck_low_poisons_the_bus_for_every_channel():
    bench = mx.FakeBench()
    ds, bus = drivers(bench)
    try:
        for d in ds.values():
            d.open()
        real_factory_line = bus._cs[5]

        class Stuck:
            def write(self, level):
                if level:
                    raise OSError(5, "write failed")
                real_factory_line.write(level)

            def close(self):
                real_factory_line.close()

        bus._cs[5] = Stuck()
        with pytest.raises(mx.BusFault):
            ds["tc_air"].read_once()
        for name in ("tc_plate", "tc_housing", "tc_air"):
            with pytest.raises(mx.BusFault):
                ds[name].read_once()                         # fail closed: CS may still be low
    finally:
        for d in ds.values():
            d.close()
    assert bus.broken is None                                # cleared once every channel closed


def test_lock_ordering_no_kernel_cs_transfer_while_gpio5_low():
    """Hammer all three channels from three threads: never two chips selected, never overlapping transfers."""
    bench = mx.FakeBench()
    ds, bus = drivers(bench)
    inside = [0]
    overlap = []
    bad = []
    orig = bench.spi_factory

    def spi_factory(b, dv):
        spi = orig(b, dv)
        inner = spi.readbytes

        class Wrapped:
            @property
            def no_cs(self):
                return spi.no_cs

            @no_cs.setter
            def no_cs(self, v):
                spi.no_cs = v

            def readbytes(self, n):
                inside[0] += 1
                if inside[0] > 1:
                    overlap.append(1)
                if dv in (0, 1) and not spi.no_cs and bench.levels.get(5) == 0:
                    bad.append("kernel CS transfer while GPIO5 low")
                time.sleep(0.0005)
                r = inner(n)
                inside[0] -= 1
                return r

            def close(self):
                spi.close()

        return Wrapped()

    for name, c in (("tc_plate", PLATE), ("tc_housing", HOUSING), ("tc_air", AIR)):
        ds[name] = mx.Max31855Driver(name, c, lambda m: None, ctx=CTX, bus=bus,
                                     spi_factory=lambda c=c: spi_factory(c["spi_bus"], c["spi_dev"]))
    for d in ds.values():
        d.open()
    errs = []

    def worker(d):
        try:
            for _ in range(150):
                r = d.read_once()
                if r["fault"]:
                    errs.append(r)
        except Exception as exc:                             # noqa: BLE001
            errs.append(exc)

    ts = [threading.Thread(target=worker, args=(d,)) for d in ds.values()]
    for t in ts:
        t.start()
    for t in ts:
        t.join(20)
    for d in ds.values():
        d.close()
    assert not errs and not overlap and not bad
    assert bench.contention == 0
    assert bus.transfers >= 450


def test_without_the_bus_lock_the_fake_shows_contention():
    """Control: the fake bench does report two selected chips when GPIO5 is low during a CE0 read."""
    bench = mx.FakeBench(temps={"tc_plate": 30.0, "tc_air": 50.0})
    line = bench.gpio_factory(5)
    line.write(0)
    spi = bench.spi_factory(0, 0)
    spi.readbytes(4)
    assert bench.contention == 1 and bench.log[-1] == ("tc_plate", "tc_air")


def test_unclaimed_gpio5_is_claimed_high_before_the_first_plate_read():
    """A registered soft CS is driven high on attach, so a plate read never sees the air chip selected."""
    bench = mx.FakeBench()
    bus = bench.bus(0)
    mx.reserve_cs_from_config({"tc_air": dict(AIR, enabled=False)}, lambda n: bus)
    plate = mx.Max31855Driver("tc_plate", PLATE, lambda m: None, ctx=CTX, bus=bus,
                              spi_factory=lambda: bench.spi_factory(0, 0))
    plate.open()
    try:
        assert bench.levels[5] == 1
        assert plate.read_once()["fault"] is None
        assert bench.contention == 0
    finally:
        plate.close()


@pytest.mark.parametrize("word,detail", [
    (mx.encode_max31855(25.0, 24.0) | (1 << 17), "D17"),
    (mx.encode_max31855(25.0, 24.0) | (1 << 3), "D3"),
    (mx.encode_max31855(25.0, 24.0, "open") | (1 << 3), "D3"),        # bad frame wins over a cause bit
    (0xFFFFFFFF, "all ones"),
    (0x00000000, "all zeros"),
])
def test_garbage_words_are_faults(word, detail):
    r = mx.reading_from_word(word)
    assert r["fault"] == "spi" and r["temp_c"] is None and detail in r["fault_detail"]
    msg = CTX.make("reading", sensor="tc_air", seq=0, data=r)      # still a valid wire message
    assert protocol.parse(protocol.dumps(msg))["data"]["fault"] == "spi"


def test_normal_reading_has_no_fault_detail_key():
    r = mx.reading_from_word(mx.encode_max31855(25.0, 24.0))
    assert set(r) == {"temp_c", "cj_c", "fault", "bits", "fault_bit"}


def test_contention_garbage_in_live_loop_gives_error_heartbeat():
    bench = mx.FakeBench()
    words = iter([mx.encode_max31855(25.0, 24.0)] + [mx.encode_max31855(25.0, 24.0) | (1 << 17)] * 10000)

    class Spi:
        no_cs = False

        def readbytes(self, n):
            return list(struct.pack(">I", next(words)))

        def close(self):
            pass

    msgs = []
    d = mx.Max31855Driver("tc_plate", dict(PLATE, rate_hz=50), msgs.append, ctx=CTX, bus=bench.bus(0),
                          spi_factory=Spi).start()
    try:
        t_end = time.monotonic() + 2.0
        while time.monotonic() < t_end and not any(m["type"] == "heartbeat" and m["status"] == "error"
                                                   for m in list(msgs)):
            time.sleep(0.02)
        hb = [m for m in list(msgs) if m["type"] == "heartbeat" and m["status"] == "error"]
        assert hb and "bad frame" in hb[0]["detail"]
    finally:
        d.stop()


def test_hardware_cs_channel_unchanged_without_soft_cs_on_the_bus():
    """A bus with no software CS does not touch no_cs (old wiring / existing tests stay as they were)."""

    class PlainSpi:                                          # no no_cs attribute at all
        def readbytes(self, n):
            return list(struct.pack(">I", mx.encode_max31855(25.0, 24.0)))

        def close(self):
            pass

    d = mx.Max31855Driver("tc_housing", HOUSING, lambda m: None, ctx=CTX, spi_factory=PlainSpi)
    d.open()
    try:
        assert d.read_once()["temp_c"] == 25.0
        assert not hasattr(d._spi, "no_cs")
    finally:
        d.close()


def test_cross_process_lock_refuses_a_second_bus_owner(tmp_path):
    (tmp_path / "spidev0.0").write_text("")                  # stands in for the /dev/spidev0.0 node
    a = mx.SpiBus(0, lock_dir=str(tmp_path))
    b = mx.SpiBus(0, lock_dir=str(tmp_path))                 # flock: separate open file description = other owner
    a.attach()
    try:
        with pytest.raises(mx.SpiAccessError, match="systemctl stop wfgvu"):
            b.attach()
    finally:
        a.detach()
    b.attach()                                               # free again once the first owner detached
    b.detach()


def test_gpio_claim_failure_is_access_error_and_releases_the_lock(tmp_path):
    def busy(n):
        raise mx.SpiAccessError("cannot claim GPIO%d: GPIO busy" % n)

    (tmp_path / "spidev0.0").write_text("")
    bus = mx.SpiBus(0, gpio_factory=busy, lock_dir=str(tmp_path))
    bus.register_cs(5)
    with pytest.raises(mx.SpiAccessError, match="GPIO busy"):
        bus.attach()
    other = mx.SpiBus(0, lock_dir=str(tmp_path))
    other.attach()                                           # the failed attach did not keep the flock
    other.detach()


def test_cross_process_lock_never_creates_a_file_and_needs_no_write_access(tmp_path):
    """The flock is taken on the existing SPI node (read-only open, no O_CREAT), so a lock file owned by another user
    in a sticky directory (fs.protected_regular) cannot lock anyone out. Here: a missing node is not created (and is
    no error: nothing to share), and a read-only node is still locked exclusively."""
    a = mx.SpiBus(0, lock_dir=str(tmp_path))
    a.attach()
    a.detach()
    assert list(tmp_path.iterdir()) == []                    # nothing created
    node = tmp_path / "spidev0.0"
    node.write_text("")
    node.chmod(0o444)                                        # not writable by the caller
    a, b = mx.SpiBus(0, lock_dir=str(tmp_path)), mx.SpiBus(0, lock_dir=str(tmp_path))
    a.attach()
    try:
        with pytest.raises(mx.SpiAccessError, match="in use by another process"):
            b.attach()
    finally:
        a.detach()
    assert mx.LOCK_DIR == "/dev" and sorted(p.name for p in tmp_path.iterdir()) == ["spidev0.0"]


def test_no_gpio_library_is_access_error(monkeypatch):
    monkeypatch.setattr(mx, "first_present", lambda mods: None)
    with pytest.raises(mx.SpiAccessError, match="lgpio"):
        mx.default_gpio_factory(5)


class FakeLgpio:
    """lgpio double: chip 0 labelled like a Pi 5 old-kernel brcmstb chip, chip 4 = pinctrl-rp1."""

    class error(Exception):
        pass

    def __init__(self, labels, busy=()):
        self.labels, self.busy = labels, set(busy)
        self.levels, self.closed, self.freed = {}, [], []

    def gpiochip_open(self, c):
        if c not in self.labels:
            raise self.error("can not open gpiochip")
        return c

    def gpio_get_chip_info(self, h):
        return (0, 54, "gpiochip%d" % h, self.labels[h])

    def gpio_claim_output(self, h, g, level=0, lFlags=0):
        if g in self.busy:
            raise self.error("GPIO busy")
        self.levels[(h, g)] = level

    def gpio_write(self, h, g, level):
        self.levels[(h, g)] = level

    def gpio_free(self, h, g):
        self.freed.append((h, g))

    def gpiochip_close(self, h):
        self.closed.append(h)


def test_lgpio_picks_the_pinctrl_chip_and_claims_high():
    lg = FakeLgpio({0: "gpio-brcmstb@107d508500", 4: "pinctrl-rp1"})
    line = mx._LgpioCS(lg, 5, "auto")
    assert lg.levels[(4, 5)] == 1 and lg.closed == [0]
    line.write(0)
    assert lg.levels[(4, 5)] == 0
    line.close()
    assert lg.levels[(4, 5)] == 1 and lg.freed == [(4, 5)] and 4 in lg.closed


def test_lgpio_busy_line_is_access_error():
    lg = FakeLgpio({0: "pinctrl-bcm2711"}, busy={5})
    with pytest.raises(mx.SpiAccessError, match="GPIO busy"):
        mx._LgpioCS(lg, 5, "auto")
    assert lg.closed == [0]


def test_live_build_reserves_gpio5_on_the_process_bus(tmp_path):
    mx.reset_buses()
    try:
        cfg = unit_main.load_config(ROOT / "config" / "unit.yaml")
        cfg["sensors"] = {n: dict(cfg["sensors"][n], enabled=False) for n in cfg["sensors"]}
        unit_main.build(cfg, records_dir=tmp_path, record=False, port=0)
        assert 5 in mx.get_bus(0).soft_cs
    finally:
        mx.reset_buses()


def test_plate_over_disc_limit_emits_one_event_per_excursion():
    temps = iter([30.0, 30.0, 71.0, 72.0, 69.0, 70.0] + [30.0] * 50)
    bench = mx.FakeBench(temps={"tc_plate": lambda: next(temps)})
    bench.exact.add("tc_plate")
    bus = bench.bus(0)
    bus.register_cs(5)                                       # GPIO5 held high (else the fake air chip floats in)
    msgs = []
    d = mx.Max31855Driver("tc_plate", dict(PLATE, rate_hz=1000, disc_max_c=70), msgs.append, ctx=CTX,
                          bus=bus, spi_factory=lambda: bench.spi_factory(0, 0))
    d.open()                                                 # consumes 30.0
    try:
        got = [d.read()[0]["temp_c"] for _ in range(5)]
    finally:
        d.close()
    assert got == [30.0, 71.0, 72.0, 69.0, 70.0]             # readings are passed through unchanged
    ev = [m for m in msgs if m["type"] == "event" and m["kind"] == "disc_over_temp"]
    assert len(ev) == 2 and "PETG" in ev[0]["detail"] and "71.0 C" in ev[0]["detail"]
    other = mx.Max31855Driver("tc_housing", dict(HOUSING, disc_max_c=70), lambda m: None, ctx=CTX,
                              spi_factory=lambda: bench.spi_factory(0, 1))
    assert other.disc_max_c is None                          # only the flux disc channel


class _Spidev34Like:
    """py-spidev 3.4 behaviour: the no_cs setter ignores a refused ioctl and caches the value; the getter returns the
    cache. Only the kernel's mode byte (SPI_IOC_RD_MODE on fileno()) shows whether no_cs took."""

    def __init__(self, fd):
        self._fd = fd
        self._cached = False

    def fileno(self):
        return self._fd

    @property
    def no_cs(self):
        return self._cached

    @no_cs.setter
    def no_cs(self, v):
        self._cached = bool(v)


@pytest.mark.parametrize("kernel_mode,ok", [(0x00, False), (0x40, True), (0x41, True)])
def test_no_cs_read_back_is_the_kernel_mode_not_the_cached_attribute(monkeypatch, kernel_mode, ok):
    import fcntl
    seen = []

    def fake_ioctl(fd, req, buf, mutate):
        seen.append(req)
        buf[0] = kernel_mode
        return 0

    monkeypatch.setattr(fcntl, "ioctl", fake_ioctl)
    spi = _Spidev34Like(7)
    if ok:
        mx._set_no_cs(spi, True)
    else:
        with pytest.raises(mx.NoCsUnsupported, match="reads back"):
            mx._set_no_cs(spi, True)
    assert seen == [mx.SPI_IOC_RD_MODE]


def test_no_cs_kernel_read_back_failure_is_a_fault(tmp_path):
    """fileno() of something that is not an SPI node: the SPI_IOC_RD_MODE ioctl fails -> NoCsUnsupported."""
    f = open(tmp_path / "not_spi", "w")
    try:
        with pytest.raises(mx.NoCsUnsupported, match="no_cs unsupported"):
            mx._set_no_cs(_Spidev34Like(f.fileno()), True)
    finally:
        f.close()
