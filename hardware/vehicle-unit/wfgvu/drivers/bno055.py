"""Bosch BNO055 absolute-orientation IMU on I2C (``imu``, 20 Hz). ``smbus2`` is an optional import.

Registers used (BNO055 datasheet, page 0): CHIP_ID 0x00 (= 0xA0), EUL_DATA 0x1A..0x1F (heading, roll, pitch as
int16 LE, 16 LSB per degree), GRV_DATA 0x2E..0x33 (gravity vector x, y, z, int16 LE, 100 LSB per m/s2),
CALIB_STAT 0x35 (sys bits 7-6, gyro 5-4, accel 3-2, mag 1-0; 0 = uncalibrated .. 3 = fully), UNIT_SEL 0x3B,
OPR_MODE 0x3D (CONFIG 0x00, NDOF 0x0C fusion), SYS_TRIGGER 0x3F, AXIS_MAP_CONFIG 0x41, AXIS_MAP_SIGN 0x42,
PAGE_ID 0x07, SYS_STATUS 0x39 (1 = system error), SYS_ERR 0x3A.

Chip reset (VU-R2): after a brown-out, the clock-stretching lock-up or a power glitch the chip reboots into CONFIG
mode with UNIT_SEL 0x80 (other pitch sign) and its fusion registers read 0. ``read`` therefore checks OPR_MODE on
every reading and raises IOError when it is not NDOF (or SYS_STATUS says system error), so the base loop closes and
re-opens the chip (``open`` selects page 0 and rewrites UNIT_SEL, the axis map and NDOF). ``assess`` rejects a
gravity vector whose norm is outside 8.8..10.8 m/s2 (placeholder band; NDOF gravity excludes linear acceleration)
and an all-zero reading; calibration below 3 is reported in the heartbeat detail, not treated as bad (sys is 0 for
seconds after start; pitch and roll do not depend on the magnetometer). Not verified on hardware.

UNIT_SEL is written as 0x00: m/s2, degrees, dps, Celsius, "Windows" orientation convention.

Wire convention (DESIGN.md section 2): pitch positive = nose up, roll positive = right side down, heading clockwise
from magnetic north. How the chip's own Euler signs map to this depends on how the board is mounted, so the
mapping is configurable (``axis_map_config``, ``axis_map_sign`` written to the chip; ``pitch_sign``,
``roll_sign`` applied after decoding). The defaults (+1, +1, chip default axis map) are NOT verified: a tilt test
on the vehicle (nose-up ramp, right-side-down kerb) must confirm the signs before any slope estimate is trusted.

Known Pi issue: the BNO055 uses I2C clock stretching, which the Pi's hardware I2C handles badly; use a low bus
clock (``dtparam=i2c_arm_baudrate=10000``) or the ``i2c-gpio`` overlay. Not verified on hardware.
"""
from __future__ import annotations

import struct
import time
from typing import List, Sequence

from .base import DeviceUnavailable, Driver, first_present

ADDRESS = 0x28
REG_CHIP_ID = 0x00
CHIP_ID = 0xA0
REG_EUL = 0x1A
REG_GRV = 0x2E
REG_CALIB_STAT = 0x35
REG_UNIT_SEL = 0x3B
REG_OPR_MODE = 0x3D
REG_PAGE_ID = 0x07
REG_SYS_STATUS = 0x39
REG_SYS_ERR = 0x3A
GRAVITY_BAND_MS2 = (8.8, 10.8)          # placeholder: |g| of the NDOF gravity vector outside this = bad reading
REG_SYS_TRIGGER = 0x3F
REG_AXIS_MAP_CONFIG = 0x41
REG_AXIS_MAP_SIGN = 0x42
MODE_CONFIG = 0x00
MODE_NDOF = 0x0C
EUL_LSB_PER_DEG = 16.0
GRV_LSB_PER_MS2 = 100.0


def decode_euler(b: Sequence[int]) -> dict:
    """6 bytes from EUL_DATA -> ``{"heading_deg","roll_deg","pitch_deg"}`` in the chip's own convention."""
    h, r, p = struct.unpack("<hhh", bytes(b[:6]))
    return {"heading_deg": h / EUL_LSB_PER_DEG, "roll_deg": r / EUL_LSB_PER_DEG, "pitch_deg": p / EUL_LSB_PER_DEG}


def decode_gravity(b: Sequence[int]) -> List[float]:
    """6 bytes from GRV_DATA -> [gx, gy, gz] in m/s2."""
    return [v / GRV_LSB_PER_MS2 for v in struct.unpack("<hhh", bytes(b[:6]))]


def decode_calib(byte: int) -> dict:
    """CALIB_STAT -> ``{"sys","gyro","accel","mag"}`` each 0..3."""
    return {"sys": (byte >> 6) & 3, "gyro": (byte >> 4) & 3, "accel": (byte >> 2) & 3, "mag": byte & 3}


def to_reading(eul: Sequence[int], grv: Sequence[int], calib: int, pitch_sign: float = 1.0,
               roll_sign: float = 1.0) -> dict:
    """Raw register bytes -> the ``imu`` reading ``data`` in the wire convention."""
    e = decode_euler(eul)
    heading = e["heading_deg"] % 360.0
    return {"roll_deg": roll_sign * e["roll_deg"], "pitch_deg": pitch_sign * e["pitch_deg"],
            "heading_deg": heading, "grav": decode_gravity(grv), "calib": decode_calib(calib)}


class Bno055Driver(Driver):
    """cfg: ``i2c_bus`` (1), ``address`` (0x28), ``rate_hz`` (20), ``axis_map_config`` (0x24),
    ``axis_map_sign`` (0x00), ``pitch_sign`` (1), ``roll_sign`` (1)."""

    def __init__(self, name, cfg, emit, sim_source=None, *, ctx=None, bus_factory=None):
        super().__init__(name, cfg, emit, sim_source, ctx=ctx)
        self._bus_factory = bus_factory
        self._bus = None
        self._next = 0.0
        self.addr = int(self.cfg.get("address", ADDRESS))

    def _w(self, reg: int, val: int) -> None:
        self._bus.write_byte_data(self.addr, reg, val)

    def open(self) -> None:
        if self._bus_factory is not None:
            bus = self._bus_factory()
        else:
            smbus2 = first_present(["smbus2"])
            if smbus2 is None:
                raise DeviceUnavailable("python module smbus2 not installed")
            bus = smbus2.SMBus(int(self.cfg.get("i2c_bus", 1)))
        self._bus = bus
        chip = None
        for _ in range(10):                                   # the chip needs ~650 ms after power-on
            try:
                chip = self._bus.read_byte_data(self.addr, REG_CHIP_ID)
            except OSError:
                chip = None
            if chip == CHIP_ID:
                break
            if not self.sleep(0.1):
                return
        if chip != CHIP_ID:
            raise DeviceUnavailable("BNO055 not found at 0x%02X (chip id %r)" % (self.addr, chip))
        self._w(REG_PAGE_ID, 0x00)                            # a chip left on page 1 has other registers there
        self._w(REG_OPR_MODE, MODE_CONFIG)
        time.sleep(0.025)
        self._w(REG_UNIT_SEL, 0x00)
        self._w(REG_AXIS_MAP_CONFIG, int(self.cfg.get("axis_map_config", 0x24)))
        self._w(REG_AXIS_MAP_SIGN, int(self.cfg.get("axis_map_sign", 0x00)))
        self._w(REG_OPR_MODE, MODE_NDOF)
        time.sleep(0.02)

    def read(self) -> List[dict]:
        period = 1.0 / float(self.cfg.get("rate_hz", 20.0))
        now = time.monotonic()
        if self._next > now and not self.sleep(self._next - now):
            return []
        self._next = max(self._next + period, time.monotonic())
        mode = self._bus.read_byte_data(self.addr, REG_OPR_MODE)
        if (int(mode) & 0x0F) != MODE_NDOF:
            raise IOError("BNO055 not in NDOF (opr_mode 0x%02X), chip reset?" % int(mode))
        sys_status = self._bus.read_byte_data(self.addr, REG_SYS_STATUS)
        if int(sys_status) == 1:
            err = self._bus.read_byte_data(self.addr, REG_SYS_ERR)
            raise IOError("BNO055 system error (SYS_ERR 0x%02X)" % int(err))
        eul = self._bus.read_i2c_block_data(self.addr, REG_EUL, 6)
        grv = self._bus.read_i2c_block_data(self.addr, REG_GRV, 6)
        cal = self._bus.read_byte_data(self.addr, REG_CALIB_STAT)
        mode = self._bus.read_byte_data(self.addr, REG_OPR_MODE)     # a reset during the block reads: discard
        if (int(mode) & 0x0F) != MODE_NDOF:
            raise IOError("BNO055 not in NDOF (opr_mode 0x%02X) after the data read, chip reset?" % int(mode))
        return [to_reading(eul, grv, cal, float(self.cfg.get("pitch_sign", 1.0)),
                           float(self.cfg.get("roll_sign", 1.0)))]

    def close(self) -> None:
        if self._bus is not None:
            try:
                self._bus.close()
            finally:
                self._bus = None

    def assess(self, data: dict):
        if data.get("pitch_deg") is None or data.get("roll_deg") is None:
            return False, "no orientation"
        g = data.get("grav")
        cal = data.get("calib") if isinstance(data.get("calib"), dict) else {}
        if isinstance(g, (list, tuple)) and len(g) == 3 and all(isinstance(v, (int, float)) for v in g):
            norm = sum(float(v) ** 2 for v in g) ** 0.5
            if norm == 0.0 and data.get("pitch_deg") == 0 and data.get("roll_deg") == 0 \
                    and not any(cal.get(k) for k in ("sys", "gyro", "accel", "mag")):
                return False, "all-zero reading (chip reset?)"
            if not GRAVITY_BAND_MS2[0] <= norm <= GRAVITY_BAND_MS2[1]:
                return False, "gravity |g|=%.2f implausible" % norm
        else:
            return False, "no gravity vector"
        if cal and any(cal.get(k) != 3 for k in ("sys", "gyro", "accel", "mag")):
            return True, "calib sys=%s gyro=%s accel=%s mag=%s" % tuple(cal.get(k) for k in ("sys", "gyro", "accel",
                                                                                            "mag"))
        return True, ""

