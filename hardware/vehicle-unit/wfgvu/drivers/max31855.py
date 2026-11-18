"""MAX31855 K-type thermocouple converters on SPI (``tc_plate``, ``tc_housing``, ``tc_air``): one driver each.

32-bit word, read MSB first (Maxim MAX31855 datasheet, "Memory Map"):

==========  =====================================================================
D31..D18    14-bit signed thermocouple temperature, 0.25 C per LSB
D17         reserved (always 0)
D16         fault (1 if any of SCV/SCG/OC)
D15..D4     12-bit signed internal (cold-junction) temperature, 0.0625 C per LSB
D3          reserved (always 0)
D2          SCV: thermocouple shorted to VCC
D1          SCG: thermocouple shorted to GND
D0          OC: thermocouple open (no connection)
==========  =====================================================================

Physics/assumptions: the chip linearises for type K around the cold junction itself (about 41.276 uV/C); no
further correction is applied here (the datasheet's NIST-table correction is not implemented, so errors of a few
C above ~700 C are expected). ``temp_c`` is the hot junction (degrees C), ``cj_c`` the die temperature. A
conversion takes up to 100 ms, so 10 Hz is the useful maximum rate; reading faster repeats values.

Fail-closed decoding: a word of all zeros or all ones means no chip is answering on that chip select, and a word
with reserved bit D17 or D3 set is a bad frame (noise, a shifted frame, a floating or fought-over MISO line). Both
give ``fault = "spi"`` (the wire keeps its fault set: null/open/short_gnd/short_vcc/spi) with the cause in the
extra key ``fault_detail`` ("no chip answering ...", "bad frame ..."). On any fault ``temp_c`` is null. LIMIT,
stated: two VALID chips driving MISO at once both send 0 in D17 and D3, so clean contention can produce a word that
passes this check. Contention is prevented, not detected: see the chip-select scheme below.

Wiring (user's printed build manual, 2026-11-17; config/unit.yaml): all three chips on SPI0, shared CLK GPIO11
(pin 23) and DO -> MISO GPIO9 (pin 21), 3.3 V pin 17, GND pin 20.

- ``tc_plate``: CE0 = GPIO8 (pin 24), kernel chip select, ``/dev/spidev0.0``.
- ``tc_housing``: CE1 = GPIO7 (pin 26), kernel chip select, ``/dev/spidev0.1``.
- ``tc_air``: GPIO5 (pin 29), SOFTWARE chip select (config ``cs_gpio: 5``). The driver opens ``/dev/spidev0.0``,
  sets ``no_cs = True`` so the kernel does not assert CE0 for it, and drives GPIO5 itself (lgpio, else gpiod;
  RPi.GPIO is not used).

Software chip select, as built (NOT verified on hardware):

- One process-wide ``SpiBus`` per SPI bus number, shared by every MAX31855 channel on that bus. Every transfer
  (kernel-CS or software-CS) runs under its lock, and the software CS is only ever low inside that lock, so no
  CE0/CE1 transfer of this process can run while GPIO5 is low. CS idles high and is released in ``finally``.
- ``no_cs`` is a property of the kernel's spi_device (``/dev/spidev0.0``), shared by every handle that opens it, so
  ``tc_air`` (no_cs on) and ``tc_plate`` (no_cs off) on the same device would undo each other. Therefore, on a bus
  that has a software CS, EVERY transfer first writes the ``no_cs`` value it needs under the bus lock and reads it
  back. If setting it raises or reads back wrong, the channel raises ``NoCsUnsupported`` and reads nothing (two
  chips on MISO would corrupt words): for ``tc_air`` this is the "no_cs unsupported" fault.
- Every registered software-CS line on the bus is claimed and driven HIGH before the first transfer of any channel
  on that bus (``reserve_cs_from_config`` also reserves the CS of a disabled channel), so a floating/pulled-low
  GPIO5 cannot select the air chip during a plate read. If a CS line cannot be released (write high fails), the bus
  is marked broken and every channel on it faults until all channels close.
- Cross-process: the bus also takes an exclusive ``flock`` on the SPI device node itself (``/dev/spidev<N>.0``,
  opened read-only, never created) for as long as any channel is open, so a second process
  (``python3 -m wfgvu.tccheck`` while ``wfgvu.service`` runs) gets ``SpiAccessError`` instead of interleaving its
  GPIO5 window with the other process's CE0/CE1 transfers. Locking the existing node (group ``spi``) instead of
  creating a lock file in the sticky, world-writable ``/run/lock`` avoids ``fs.protected_regular`` refusing the
  second user's O_CREAT open (service user ``wfgvu`` vs the login user running tccheck). Not tested on a Pi.

Errors: ``SpiAccessError`` (cannot open SPI/GPIO: library missing, device node missing/denied, bus or CS line held
by another process), ``NoCsUnsupported``, ``ChipNotAnswering`` (first word at open is all zeros/ones or a bad
frame). All are ``DeviceUnavailable``, so the driver reports ``no_device`` heartbeats with the reason and retries.

``tc_plate`` also has ``disc_max_c`` (user-set 70 C: the copper disc sits on printed PETG tabs). The Pi decides
nothing: at or above it the driver logs a warning and emits an ``event`` ``kind="disc_over_temp"`` (once per
excursion); the readings themselves are unchanged. The laptop and the field-test scripts stop on it.
"""
from __future__ import annotations

import logging
import math
import os
import threading
import time
from typing import Callable, Dict, Iterable, List, Optional

from .base import DeviceUnavailable, Driver, first_present

log = logging.getLogger(__name__)

TC_LSB_C = 0.25
CJ_LSB_C = 0.0625
RESERVED_MASK = (1 << 17) | (1 << 3)
DISC_MAX_C_USER = 70.0          # user-set limit for the flux disc (PETG tabs); not a placeholder
LOCK_DIR = "/dev"               # cross-process flock on the existing node <LOCK_DIR>/spidev<bus>.0
BCM_GPIO_MAX = 27


class SpiAccessError(DeviceUnavailable):
    """SPI or chip-select GPIO cannot be opened (library missing, node missing/denied, held by another process)."""


class NoCsUnsupported(DeviceUnavailable):
    """The SPI controller refused ``no_cs`` (or it did not read back): a software-CS channel must not read."""


class ChipNotAnswering(DeviceUnavailable):
    """The first word at open was all zeros/ones or a bad frame: no MAX31855 answering on that chip select."""


class BusFault(IOError):
    """A chip-select line could not be released: every channel on the bus faults until all of them close."""


def _signed(value: int, bits: int) -> int:
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


def decode_max31855(word: int) -> dict:
    """Decode one 32-bit MAX31855 word -> ``{"temp_c","cj_c","fault","fault_bit","bits","fault_detail"}``.

    ``fault`` is one of None, "open", "short_gnd", "short_vcc", "spi". "spi" (no chip / bad frame / D16 without a
    cause bit) wins over the cause bits, which are meaningless in a corrupted word.
    """
    word &= 0xFFFFFFFF
    if word in (0x00000000, 0xFFFFFFFF):
        return {"temp_c": None, "cj_c": None, "fault": "spi", "fault_bit": False, "bits": word,
                "fault_detail": "no chip answering (all %s)" % ("zeros" if word == 0 else "ones")}
    fault_bit = bool(word & (1 << 16))
    if word & RESERVED_MASK:
        return {"temp_c": None, "cj_c": None, "fault": "spi", "fault_bit": fault_bit, "bits": word,
                "fault_detail": "bad frame (reserved bit %s set)" % "/".join(
                    n for n, b in (("D17", 17), ("D3", 3)) if word & (1 << b))}
    tc = _signed((word >> 18) & 0x3FFF, 14) * TC_LSB_C
    cj = _signed((word >> 4) & 0xFFF, 12) * CJ_LSB_C
    fault: Optional[str] = None
    detail: Optional[str] = None
    if word & 0x1:
        fault = "open"
    elif word & 0x2:
        fault = "short_gnd"
    elif word & 0x4:
        fault = "short_vcc"
    elif fault_bit:
        fault, detail = "spi", "D16 set without a cause bit"   # inconsistent word, treat as a bus error
    return {"temp_c": None if fault else tc, "cj_c": cj, "fault": fault, "fault_bit": fault_bit, "bits": word,
            "fault_detail": detail}


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
    out = {"temp_c": d["temp_c"], "cj_c": d["cj_c"], "fault": d["fault"],
           "bits": "0x%08X" % (int(d["bits"]) & 0xFFFFFFFF), "fault_bit": bool(d["fault_bit"])}
    if d.get("fault_detail"):
        out["fault_detail"] = d["fault_detail"]       # extra key, only on a fault (normal readings unchanged)
    return out


# ------------------------------------------------------------------------------------------- chip-select GPIO

class _LgpioCS:
    """One output line via lgpio (python3-lgpio, Bookworm default; Pi 4 and Pi 5). Claimed HIGH (CS idle)."""

    def __init__(self, lgpio, gpio: int, chip):
        self._lg, self.gpio, self._h = lgpio, gpio, None
        chips = [int(chip)] if chip not in (None, "auto") else [0, 4]   # Pi 5 RP1: gpiochip0 (new) or 4 (old kernels)
        errors = []
        for c in chips:
            try:
                h = lgpio.gpiochip_open(c)
            except Exception as exc:                                     # noqa: BLE001
                errors.append("gpiochip%d: %s" % (c, exc))
                continue
            label = ""
            try:
                info = lgpio.gpio_get_chip_info(h)
                label = next((x for x in info if isinstance(x, str) and x.startswith("pinctrl")), "")
            except Exception:                                            # noqa: BLE001
                label = ""
            if chip in (None, "auto") and not label:
                errors.append("gpiochip%d: not the header GPIO (no pinctrl label)" % c)
                lgpio.gpiochip_close(h)
                continue
            try:
                lgpio.gpio_claim_output(h, gpio, 1)                      # idle HIGH = chip not selected
            except Exception as exc:                                     # noqa: BLE001 - e.g. "GPIO busy"
                lgpio.gpiochip_close(h)
                raise SpiAccessError("cannot claim GPIO%d on gpiochip%d (%s): %s" % (gpio, c, label, exc))
            self._h = h
            return
        raise SpiAccessError("no header GPIO chip for GPIO%d: %s" % (gpio, "; ".join(errors) or "none"))

    def write(self, level: int) -> None:
        self._lg.gpio_write(self._h, self.gpio, 1 if level else 0)

    def close(self) -> None:
        if self._h is None:
            return
        try:
            try:
                self._lg.gpio_write(self._h, self.gpio, 1)
            finally:
                try:
                    self._lg.gpio_free(self._h, self.gpio)
                finally:
                    self._lg.gpiochip_close(self._h)
        finally:
            self._h = None


class _GpiodCS:
    """Fallback via libgpiod Python bindings (v2 API ``request_lines``, else the v1 API of Bookworm's apt
    python3-libgpiod). Claimed HIGH. Neither API has been run on the target Pi."""

    def __init__(self, gpiod, gpio: int, chip):
        self.gpio, self._req, self._line, self._chip = gpio, None, None, None
        chips = [int(chip)] if chip not in (None, "auto") else [0, 4]
        errors = []
        for c in chips:
            path = "/dev/gpiochip%d" % c
            try:
                if hasattr(gpiod, "request_lines"):                     # v2
                    with gpiod.Chip(path) as ch:
                        label = str(ch.get_info().label)
                    if chip in (None, "auto") and not label.startswith("pinctrl"):
                        errors.append("%s: label %s" % (path, label))
                        continue
                    from gpiod.line import Direction, Value               # type: ignore
                    self._val = Value
                    self._req = gpiod.request_lines(path, consumer="wfgvu-cs", config={
                        gpio: gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.ACTIVE)})
                    return
                ch = gpiod.Chip("gpiochip%d" % c)                         # v1
                label = str(ch.label() if callable(getattr(ch, "label", None)) else getattr(ch, "label", ""))
                if chip in (None, "auto") and not label.startswith("pinctrl"):
                    ch.close()
                    errors.append("%s: label %s" % (path, label))
                    continue
                line = ch.get_line(gpio)
                line.request(consumer="wfgvu-cs", type=gpiod.LINE_REQ_DIR_OUT, default_vals=[1])
                self._chip, self._line = ch, line
                return
            except Exception as exc:                                     # noqa: BLE001 - busy, missing, denied
                errors.append("%s: %s" % (path, exc))
        raise SpiAccessError("cannot claim GPIO%d with gpiod: %s" % (gpio, "; ".join(errors) or "no chip"))

    def write(self, level: int) -> None:
        if self._req is not None:
            self._req.set_value(self.gpio, self._val.ACTIVE if level else self._val.INACTIVE)
        else:
            self._line.set_value(1 if level else 0)

    def close(self) -> None:
        try:
            try:
                self.write(1)
            finally:
                if self._req is not None:
                    self._req.release()
                elif self._line is not None:
                    self._line.release()
                    self._chip.close()
        finally:
            self._req = self._line = self._chip = None


def default_gpio_factory(gpio: int, chip="auto"):
    """Claim ``gpio`` as an output, HIGH. lgpio first, then gpiod; neither -> ``SpiAccessError`` (fail closed)."""
    lgpio = first_present(["lgpio"])
    if lgpio is not None:
        return _LgpioCS(lgpio, gpio, chip)
    gpiod = first_present(["gpiod"])
    if gpiod is not None:
        return _GpiodCS(gpiod, gpio, chip)
    raise SpiAccessError("no GPIO library for software chip select GPIO%d (install python3-lgpio)" % gpio)


# ------------------------------------------------------------------------------------------- shared bus

SPI_IOC_RD_MODE = 0x80016B01    # _IOR('k', 1, __u8) (linux/spi/spidev.h)
SPI_NO_CS = 0x40


def _kernel_no_cs(spi) -> Optional[bool]:
    """SPI_NO_CS as the KERNEL holds it (ioctl SPI_IOC_RD_MODE on the handle's descriptor), or None when the handle
    has no ``fileno()`` (test doubles). py-spidev's ``no_cs`` getter only returns its cached mode, and py-spidev 3.4's
    setter ignores a refused ioctl, so the attribute alone cannot prove the kernel took the value."""
    fileno = getattr(spi, "fileno", None)
    if not callable(fileno):
        return None
    import array
    import fcntl
    buf = array.array("B", [0])
    fcntl.ioctl(int(fileno()), SPI_IOC_RD_MODE, buf, True)
    return bool(buf[0] & SPI_NO_CS)


def _set_no_cs(spi, want: bool) -> None:
    """Write ``no_cs`` and read it back (it is shared by every handle of the same spidev node). The read-back is the
    kernel's mode byte (``_kernel_no_cs``) when the handle has ``fileno()`` (real py-spidev), else the attribute."""
    try:
        spi.no_cs = bool(want)
        got = _kernel_no_cs(spi)
        if got is None:
            got = spi.no_cs
    except Exception as exc:                                             # noqa: BLE001 - EINVAL, SystemError ...
        raise NoCsUnsupported("no_cs unsupported: setting no_cs=%s failed: %s: %s"
                              % (want, type(exc).__name__, exc))
    if bool(got) != bool(want):
        raise NoCsUnsupported("no_cs unsupported: no_cs=%s reads back %r" % (want, got))


class SpiBus:
    """Process-wide state of one SPI bus: transfer lock, software chip selects, cross-process lock.

    ``gpio_factory(gpio) -> line`` (``line.write(level)``, ``line.close()``) claims a CS line HIGH; default
    ``default_gpio_factory``. ``lock_dir``: directory holding the node ``spidev<bus>.0`` that is flocked (default
    ``/dev``; tests pass a directory with a plain file of that name); None = no cross-process lock (tests, fakes).
    The node is opened read-only and never created; a missing node (laptop) means no cross-process lock."""

    def __init__(self, bus: int, *, gpio_factory: Optional[Callable] = None, gpio_chip="auto",
                 lock_dir: Optional[str] = LOCK_DIR):
        self.bus = int(bus)
        self.lock = threading.Lock()              # held for every transfer, CS window included
        self._state = threading.Lock()            # users / claimed lines (never taken inside ``lock``)
        self._gpio_factory = gpio_factory
        self._gpio_chip = gpio_chip
        self.lock_dir = lock_dir
        self.soft_cs: set = set()
        self._cs: Dict[int, object] = {}
        self._users = 0
        self._flock_fd: Optional[int] = None
        self.broken: Optional[str] = None
        self.transfers = 0

    # ---- registration / attach
    def register_cs(self, gpio: int) -> None:
        with self._state:
            self.soft_cs.add(int(gpio))

    @property
    def has_soft_cs(self) -> bool:
        return bool(self.soft_cs)

    def _take_flock(self) -> None:
        if not self.lock_dir:
            return
        path = os.path.join(self.lock_dir, "spidev%d.0" % self.bus)
        if not os.path.exists(path):
            return                                    # not a Pi (laptop) or SPI off: nothing to share, the open fails
        import fcntl
        try:
            fd = os.open(path, os.O_RDONLY)           # existing node, no O_CREAT (protected_regular-safe)
        except OSError as exc:
            raise SpiAccessError("cannot open SPI bus lock %s: %s" % (path, exc))
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            raise SpiAccessError("SPI bus %d is in use by another process (lock %s held); if wfgvu.service is "
                                 "running, stop it first: sudo systemctl stop wfgvu" % (self.bus, path))
        self._flock_fd = fd

    def _drop_flock(self) -> None:
        if self._flock_fd is not None:
            try:
                os.close(self._flock_fd)              # closing the descriptor releases the flock
            finally:
                self._flock_fd = None

    def attach(self) -> None:
        """A channel opens: take the cross-process lock (first user) and claim every registered CS line HIGH."""
        with self._state:
            first = self._users == 0
            if first:
                self._take_flock()
            try:
                with self.lock:
                    for g in sorted(self.soft_cs - set(self._cs)):
                        factory = self._gpio_factory or (lambda n: default_gpio_factory(n, self._gpio_chip))
                        self._cs[g] = factory(g)
            except Exception as exc:
                if first:
                    self._release_lines()
                    self._drop_flock()
                if isinstance(exc, DeviceUnavailable):
                    raise
                raise SpiAccessError("cannot claim chip-select GPIO: %s: %s" % (type(exc).__name__, exc))
            self._users += 1

    def _release_lines(self) -> None:
        for g, line in list(self._cs.items()):
            try:
                line.close()
            except Exception:                         # noqa: BLE001
                log.warning("SPI%d: releasing CS GPIO%d failed", self.bus, g)
        self._cs.clear()

    def detach(self) -> None:
        with self._state:
            if self._users <= 0:
                return
            self._users -= 1
            if self._users == 0:
                with self.lock:
                    self._release_lines()
                    self.broken = None
                self._drop_flock()

    # ---- transfer
    def transfer(self, spi, nbytes: int, cs_gpio: Optional[int] = None) -> List[int]:
        """One read of ``nbytes`` under the bus lock. ``cs_gpio`` None = kernel chip select."""
        with self.lock:
            if self.broken:
                raise BusFault(self.broken)
            if cs_gpio is not None:
                _set_no_cs(spi, True)
            elif self.soft_cs:
                _set_no_cs(spi, False)                # undo a no_cs left on the shared spi_device by a soft-CS read
            self.transfers += 1
            if cs_gpio is None:
                return list(spi.readbytes(nbytes))
            line = self._cs.get(int(cs_gpio))
            if line is None:
                raise BusFault("chip-select GPIO%d not claimed" % cs_gpio)
            try:
                line.write(0)
                data = list(spi.readbytes(nbytes))
            finally:
                try:
                    line.write(1)
                except Exception as exc:              # noqa: BLE001 - CS may be stuck low: poison the bus
                    self.broken = "chip-select GPIO%d could not be released: %s" % (cs_gpio, exc)
                    raise BusFault(self.broken)
            return data


_BUSES: Dict[int, SpiBus] = {}
_BUSES_LOCK = threading.Lock()


def get_bus(bus: int) -> SpiBus:
    """The process-wide ``SpiBus`` for this bus number (real GPIO backend, flock on /dev/spidev<bus>.0)."""
    with _BUSES_LOCK:
        b = _BUSES.get(int(bus))
        if b is None:
            b = _BUSES[int(bus)] = SpiBus(int(bus))
        return b


def reset_buses() -> None:
    """Forget the process-wide buses (tests)."""
    with _BUSES_LOCK:
        _BUSES.clear()


def parse_cs_gpio(value) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= BCM_GPIO_MAX:
        raise ValueError("cs_gpio must be a BCM GPIO number 0..%d, got %r" % (BCM_GPIO_MAX, value))
    return int(value)


def reserve_cs_from_config(sensors_cfg: dict, buses: Optional[Callable[[int], SpiBus]] = None) -> None:
    """Register every MAX31855 software chip select in the config (enabled or not), so each is held HIGH before
    any transfer on its bus (a disabled tc_air's GPIO5 must not float low and select the air chip)."""
    getter = buses or get_bus
    for name in ("tc_plate", "tc_housing", "tc_air"):
        c = (sensors_cfg or {}).get(name) or {}
        g = parse_cs_gpio(c.get("cs_gpio"))
        if g is not None:
            getter(int(c.get("spi_bus", 0))).register_cs(g)


def disc_max_c(cfg: dict) -> float:
    """``disc_max_c`` of a tc_plate config, never above the user's 70 C (PETG tabs). Missing or bad -> 70."""
    v = (cfg or {}).get("disc_max_c", DISC_MAX_C_USER)
    try:
        f = float(v)
    except (TypeError, ValueError):
        return DISC_MAX_C_USER
    if not math.isfinite(f) or f <= 0 or f > DISC_MAX_C_USER:
        return DISC_MAX_C_USER
    return f


# ------------------------------------------------------------------------------------------- driver

class Max31855Driver(Driver):
    """One MAX31855. cfg: ``spi_bus`` (0), ``spi_dev`` (0), ``cs_gpio`` (None = kernel CS; an int = software CS on
    that BCM GPIO, spidev opened with no_cs), ``spi_hz`` (1 MHz; chip max 5 MHz), ``rate_hz`` (10), tc_plate
    ``disc_max_c`` (70, user-set).

    Test hooks: ``spi_factory()`` returns an object with ``readbytes(n)`` (and ``no_cs`` for software CS);
    ``bus`` a ``SpiBus`` (default: the process-wide one, or a private one when ``spi_factory`` is given)."""

    def __init__(self, name, cfg, emit, sim_source=None, *, ctx=None, spi_factory=None, bus: Optional[SpiBus] = None):
        super().__init__(name, cfg, emit, sim_source, ctx=ctx)
        self._spi_factory = spi_factory
        self._spi = None
        self._next = 0.0
        self.spi_bus = int(self.cfg.get("spi_bus", 0))
        self.spi_dev = int(self.cfg.get("spi_dev", 0))
        self.cs_gpio = parse_cs_gpio(self.cfg.get("cs_gpio"))
        if bus is None:
            bus = SpiBus(self.spi_bus, lock_dir=None) if spi_factory is not None else get_bus(self.spi_bus)
        self.bus = bus
        if self.cs_gpio is not None and not self.sim:
            self.bus.register_cs(self.cs_gpio)
        self._attached = False
        self.disc_max_c = disc_max_c(self.cfg) if name == "tc_plate" else None
        self._disc_over = False

    def describe(self) -> str:
        if self.cs_gpio is not None:
            return "spidev%d.%d no_cs + software CS GPIO%d" % (self.spi_bus, self.spi_dev, self.cs_gpio)
        return "spidev%d.%d kernel CS" % (self.spi_bus, self.spi_dev)

    def _open_spi(self):
        if self._spi_factory is not None:
            return self._spi_factory()
        spidev = first_present(["spidev"])
        if spidev is None:
            raise SpiAccessError("python module spidev not installed (sudo apt install python3-spidev)")
        spi = spidev.SpiDev()
        try:
            spi.open(self.spi_bus, self.spi_dev)
        except OSError as exc:
            raise SpiAccessError("cannot open /dev/spidev%d.%d: %s (SPI enabled? user in group spi?)"
                                 % (self.spi_bus, self.spi_dev, exc))
        spi.max_speed_hz = int(self.cfg.get("spi_hz", 1_000_000))
        spi.mode = 0
        return spi

    def open(self) -> None:
        self.bus.attach()
        self._attached = True
        self._spi = self._open_spi()
        # first read: also proves no_cs works for a software-CS channel (NoCsUnsupported before any CS goes low)
        first = decode_max31855(word_from_bytes(self.bus.transfer(self._spi, 4, self.cs_gpio)))
        if first["fault"] == "spi":
            raise ChipNotAnswering("no MAX31855 answering on %s (word 0x%08X: %s)"
                                   % (self.describe(), first["bits"], first.get("fault_detail") or "spi"))

    def read_once(self) -> dict:
        """One reading (no pacing): used by ``read`` and by ``wfgvu.tccheck``."""
        return reading_from_word(word_from_bytes(self.bus.transfer(self._spi, 4, self.cs_gpio)))

    def read(self) -> List[dict]:
        period = 1.0 / float(self.cfg.get("rate_hz", 10.0))
        now = time.monotonic()
        if self._next > now and not self.sleep(self._next - now):
            return []
        self._next = max(self._next + period, time.monotonic())
        data = self.read_once()
        self._check_disc(data)
        return [data]

    def _check_disc(self, data: dict) -> None:
        if self.disc_max_c is None:
            return
        t = data.get("temp_c")
        over = t is not None and t >= self.disc_max_c
        if over and not self._disc_over:
            msg = "flux disc at %.1f C >= %.0f C (PETG tabs): stop the run" % (t, self.disc_max_c)
            log.warning("%s: %s", self.name, msg)
            self.emit(self.ctx.make("event", kind="disc_over_temp", detail="%s: %s" % (self.name, msg)))
        self._disc_over = over

    def close(self) -> None:
        try:
            if self._spi is not None:
                try:
                    self._spi.close()
                finally:
                    self._spi = None
        finally:
            if self._attached:
                self._attached = False
                self.bus.detach()

    def assess(self, data: dict):
        if data.get("fault"):
            extra = data.get("fault_detail")
            return False, "thermocouple fault: %s%s" % (data["fault"], " (%s)" % extra if extra else "")
        if data.get("temp_c") is None:
            return False, "no temperature"
        return True, ""


# ------------------------------------------------------------------------------------------- bench fake

class FakeBench:
    """TEST DOUBLE (not hardware): three MAX31855 on one simulated SPI0 with kernel CE0/CE1 and GPIO chip selects.

    A read returns the word of the ONE selected chip: a kernel CS chip is selected when its handle's spi_device has
    no_cs off; a GPIO chip when its line is low. No chip selected -> 0x00000000 (MISO pulled down); two or more ->
    the bitwise AND of their words (``contention`` counts it). ``no_cs_supported=False`` makes setting no_cs raise
    (like a controller without SPI_NO_CS). ``temps`` maps chip name -> hot-junction C (callable or float)."""

    def __init__(self, temps: Optional[dict] = None, cj_c: float = 24.0, no_cs_supported: bool = True,
                 seed: int = 1):
        import random
        self.rng = random.Random(seed)
        self.temps = {"tc_plate": 22.0, "tc_housing": 23.5, "tc_air": 21.0}
        self.temps.update(temps or {})
        self.cj_c = cj_c
        self.exact: set = set()                      # chips read without noise (e.g. a set disc temperature)
        self.no_cs_supported = no_cs_supported
        self.no_cs: Dict[tuple, bool] = {}           # (bus, dev) -> shared spi_device flag
        self.levels: Dict[int, int] = {}             # gpio -> level (absent = not claimed, floats LOW)
        self.kernel_chips = {(0, 0): "tc_plate", (0, 1): "tc_housing"}
        self.gpio_chips = {5: "tc_air"}
        self.contention = 0
        self.log: List[tuple] = []                   # (chip names selected) per transfer

    def word_for(self, chip: str) -> int:
        t = self.temps[chip]
        t = float(t() if callable(t) else t)
        noise = 0.0 if chip in self.exact else self.rng.uniform(-0.25, 0.25)
        return encode_max31855(t + noise, self.cj_c + self.rng.uniform(-0.1, 0.1))

    def spi_factory(self, bus: int, dev: int):
        bench = self

        class _Spi:
            def __init__(self):
                self.closed = False

            @property
            def no_cs(self):
                return bench.no_cs.get((bus, dev), False)

            @no_cs.setter
            def no_cs(self, v):
                if v and not bench.no_cs_supported:
                    raise OSError(22, "Invalid argument")
                bench.no_cs[(bus, dev)] = bool(v)

            def readbytes(self, n):
                sel = []
                chip = bench.kernel_chips.get((bus, dev))
                if chip and not bench.no_cs.get((bus, dev), False):
                    sel.append(chip)
                sel += [c for g, c in bench.gpio_chips.items() if bench.levels.get(g, 0) == 0]
                bench.log.append(tuple(sel))
                if not sel:
                    w = 0
                else:
                    w = 0xFFFFFFFF
                    for c in sel:
                        w &= bench.word_for(c)
                    if len(sel) > 1:
                        bench.contention += 1
                return [(w >> s) & 0xFF for s in (24, 16, 8, 0)][:n]

            def close(self):
                self.closed = True

        return _Spi()

    def gpio_factory(self, gpio: int):
        bench = self
        bench.levels[gpio] = 1

        class _Line:
            def write(self, level):
                bench.levels[gpio] = 1 if level else 0

            def close(self):
                bench.levels.pop(gpio, None)

        return _Line()

    def bus(self, bus: int = 0) -> SpiBus:
        return SpiBus(bus, gpio_factory=self.gpio_factory, lock_dir=None)
