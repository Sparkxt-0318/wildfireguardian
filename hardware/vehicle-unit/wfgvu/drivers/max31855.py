"""MAX31855 K-type thermocouple converters on SPI (``tc_plate``, ``tc_housing``, ``tc_air``): one driver each.

32-bit word, read MSB first (Maxim MAX31855 datasheet, "Memory Map"):

==========  =====================================================================
D31..D18    14-bit signed thermocouple temperature, 0.25 C per LSB
D17         reserved
D16         fault (1 if any of SCV/SCG/OC)
D15..D4     12-bit signed internal (cold-junction) temperature, 0.0625 C per LSB
D3          reserved
D2          SCV: thermocouple shorted to VCC
D1          SCG: thermocouple shorted to GND
D0          OC: thermocouple open (no connection)
==========  =====================================================================

Physics/assumptions: the chip linearises for type K around the cold junction itself (about 41.276 uV/C); no
further correction is applied here (the datasheet's NIST-table correction is not implemented, so errors of a few
C above ~700 C are expected). ``temp_c`` is the hot junction (degrees C), ``cj_c`` the die temperature. A
conversion takes up to 100 ms, so 10 Hz is the useful maximum rate; reading faster repeats values.

A word of all zeros or all ones means no chip is answering on that chip select (``fault = "spi"``). On any fault
``temp_c`` is null. Live wiring (three chips: SPI0 CE0, SPI0 CE1, SPI1 CE0 by default) is set in
``config/unit.yaml``. Not verified on hardware.
"""
from __future__ import annotations

from typing import Iterable, List, Optional

from .base import DeviceUnavailable, Driver, first_present

TC_LSB_C = 0.25
CJ_LSB_C = 0.0625


def _signed(value: int, bits: int) -> int:
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


def decode_max31855(word: int) -> dict:
    """Decode one 32-bit MAX31855 word -> ``{"temp_c","cj_c","fault","fault_bit","bits"}``.

    ``fault`` is one of None, "open", "short_gnd", "short_vcc", "spi" (priority in that order after "spi").
    """
    word &= 0xFFFFFFFF
    if word in (0x00000000, 0xFFFFFFFF):
        return {"temp_c": None, "cj_c": None, "fault": "spi", "fault_bit": False, "bits": word}
    tc = _signed((word >> 18) & 0x3FFF, 14) * TC_LSB_C
    cj = _signed((word >> 4) & 0xFFF, 12) * CJ_LSB_C
    fault_bit = bool(word & (1 << 16))
    fault: Optional[str] = None
    if word & 0x1:
        fault = "open"
    elif word & 0x2:
        fault = "short_gnd"
    elif word & 0x4:
        fault = "short_vcc"
    elif fault_bit:
        fault = "spi"            # D16 set without a cause bit: inconsistent word, treat as a bus error
    return {"temp_c": None if fault else tc, "cj_c": cj, "fault": fault, "fault_bit": fault_bit, "bits": word}


def word_from_bytes(b: Iterable[int]) -> int:
    bs = list(b)
    if len(bs) != 4:
        raise ValueError("MAX31855 read must return 4 bytes, got %d" % len(bs))
    return (bs[0] << 24) | (bs[1] << 16) | (bs[2] << 8) | bs[3]


def encode_max31855(temp_c: float, cj_c: float, fault: Optional[str] = None) -> int:
    """Build a word (synthetic tests). Inverse of ``decode_max31855`` for valid words."""
    tc = int(round(temp_c / TC_LSB_C)) & 0x3FFF
    cj = int(round(cj_c / CJ_LSB_C)) & 0xFFF
    word = (tc << 18) | (cj << 4)
    bit = {"open": 1, "short_gnd": 2, "short_vcc": 4}.get(fault or "", 0)
    if bit:
        word |= bit | (1 << 16)
    return word


def reading_from_word(word: int) -> dict:
    d = decode_max31855(word)
    # VU-R6: the raw 32-bit word and the D16 fault bit are kept (extra reading keys; fault stays "spi" etc.)
    return {"temp_c": d["temp_c"], "cj_c": d["cj_c"], "fault": d["fault"],
            "bits": "0x%08X" % (int(d["bits"]) & 0xFFFFFFFF), "fault_bit": bool(d["fault_bit"])}


class Max31855Driver(Driver):
    """One MAX31855. cfg: ``spi_bus`` (0), ``spi_dev`` (0), ``spi_hz`` (1 MHz; chip max 5 MHz), ``rate_hz`` (10)."""

    def __init__(self, name, cfg, emit, sim_source=None, *, ctx=None, spi_factory=None):
        super().__init__(name, cfg, emit, sim_source, ctx=ctx)
        self._spi_factory = spi_factory
        self._spi = None
        self._next = 0.0

    def open(self) -> None:
        if self._spi_factory is not None:
            spi = self._spi_factory()
        else:
            spidev = first_present(["spidev"])
            if spidev is None:
                raise DeviceUnavailable("python module spidev not installed")
            spi = spidev.SpiDev()
            spi.open(int(self.cfg.get("spi_bus", 0)), int(self.cfg.get("spi_dev", 0)))
            spi.max_speed_hz = int(self.cfg.get("spi_hz", 1_000_000))
            spi.mode = 0
        self._spi = spi
        # a missing chip reads as all zeros/ones: refuse to call it a device
        first = decode_max31855(word_from_bytes(self._spi.readbytes(4)))
        if first["fault"] == "spi":
            raise DeviceUnavailable("no MAX31855 answering (word 0x%08X)" % first["bits"])

    def read(self) -> List[dict]:
        import time
        period = 1.0 / float(self.cfg.get("rate_hz", 10.0))
        now = time.monotonic()
        if self._next > now and not self.sleep(self._next - now):
            return []
        self._next = max(self._next + period, time.monotonic())
        return [reading_from_word(word_from_bytes(self._spi.readbytes(4)))]

    def close(self) -> None:
        if self._spi is not None:
            try:
                self._spi.close()
            finally:
                self._spi = None

    def assess(self, data: dict):
        if data.get("fault"):
            return False, "thermocouple fault: %s" % data["fault"]
        if data.get("temp_c") is None:
            return False, "no temperature"
        return True, ""
