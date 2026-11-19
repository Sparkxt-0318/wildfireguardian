"""Thermocouple bench check: ``python3 -m wfgvu.tccheck [--config PATH] [--seconds N] [--hz F] [--fake]
[--fake-disc-c X]``.

Reads the three MAX31855 (``tc_plate``, ``tc_housing``, ``tc_air``) with the SAME driver classes and config as the
unit (``wfgvu.drivers.max31855``, ``config/unit.yaml``), prints one line per read (hot junction C, cold junction C,
fault and the SCV/SCG/OC fault bits for each chip), then a verdict. It is a wiring and plausibility check at room
temperature, not a calibration. Run it with the service stopped (``sudo systemctl stop wfgvu``).

Exit codes:
  0  all three answer, no fault, readings plausible for a bench check
  1  a fault or an implausible reading: open thermocouple, short, no chip answering, bad frame, no_cs unsupported,
     cold-junction spread between chips > 5 C, hot junction outside -20..60 C
  2  flux disc (tc_plate) at or above ``sensors.tc_plate.disc_max_c`` (user-set 70 C, PETG tabs): the check stops
     at once and prints "STOP: flux disc at X C >= 70 C (PETG tabs)"
  3  cannot open SPI/GPIO (spidev/lgpio missing, /dev/spidev0.x missing or denied, the SPI bus lock or GPIO5 held
     by another process, e.g. wfgvu.service: stop it first with ``sudo systemctl stop wfgvu``)
  64 bad command line (argparse would use 2, which here means "disc over temperature")
A missing --config file, or a config whose three channels do not have distinct chip selects, is exit 1 (the
built-in defaults would put every channel on /dev/spidev0.0 kernel CS: that must never PASS).

``--fake`` uses a simulated bench (``max31855.FakeBench``: a test double, not hardware) through the same driver,
bus lock and software chip-select code; ``--fake-disc-c X`` sets the simulated disc temperature (to see the 70 C
stop). Bench limits (-20..60 C hot junction, 5 C CJ spread) are placeholders for a bench check. Not run on hardware.
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .drivers import max31855 as mx

CHANNELS = ("tc_plate", "tc_housing", "tc_air")
HOT_MIN_C, HOT_MAX_C = -20.0, 60.0          # bench plausibility (placeholder)
CJ_SPREAD_MAX_C = 5.0                        # max spread of the chips' cold-junction medians (placeholder)
EXIT_OK, EXIT_FAULT, EXIT_DISC, EXIT_ACCESS, EXIT_USAGE = 0, 1, 2, 3, 64
SERVICE_HINT = "If the unit service is running, stop it first: sudo systemctl stop wfgvu"


class _Parser(argparse.ArgumentParser):
    def error(self, message):                # exit 2 is reserved for "disc over temperature"
        self.print_usage(sys.stderr)
        self.exit(EXIT_USAGE, "%s: error: %s\n" % (self.prog, message))


def _parser() -> argparse.ArgumentParser:
    from .__main__ import DEFAULT_CONFIG
    ap = _Parser(prog="python3 -m wfgvu.tccheck",
                 description="Bench check of the three MAX31855 thermocouple channels (no decisions, not a "
                             "calibration). Stop wfgvu.service first.",
                 epilog="exit codes: 0 OK; 1 fault or implausible reading; 2 flux disc >= disc_max_c (70 C, PETG "
                        "tabs), stopped at once; 3 cannot open SPI/GPIO (service running?); 64 bad command line",
                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="unit config (default config/unit.yaml)")
    ap.add_argument("--seconds", type=float, default=10.0, help="how long to read (default 10)")
    ap.add_argument("--hz", type=float, default=2.0, help="reads per second per chip (default 2, max 10)")
    ap.add_argument("--fake", action="store_true", help="no hardware: simulated bench (test double)")
    ap.add_argument("--fake-disc-c", type=float, metavar="X", help="with --fake: simulated flux disc temperature, C")
    return ap


def _bits(d: dict) -> str:
    try:
        w = int(str(d.get("bits", "0")), 16)
    except ValueError:
        return "???"
    return "%d%d%d" % ((w >> 2) & 1, (w >> 1) & 1, w & 1)


def _fmt(name: str, d: Optional[dict], err: Optional[str]) -> str:
    if err is not None:
        return "%-10s NOT OPEN (%s)" % (name, err)
    t = "  null " if d["temp_c"] is None else "%7.2f" % d["temp_c"]
    cj = "  null " if d["cj_c"] is None else "%7.2f" % d["cj_c"]
    f = d["fault"] or "-"
    if d.get("fault_detail"):
        f += " (%s)" % d["fault_detail"]
    return "%-10s hot %s C  cj %s C  fault %s  SCV/SCG/OC %s  D16 %d  %s" % (
        name, t, cj, f, _bits(d), 1 if d.get("fault_bit") else 0, d.get("bits", ""))


KERNEL_CS_GPIO = {0: {0: 8, 1: 7}}            # SPI0 CE0 = GPIO8 (pin 24), CE1 = GPIO7 (pin 26)


def _chip_select_problem(sensors: dict) -> Optional[str]:
    """None when the three channels have distinct chip selects, else why not. Kernel CS = (bus, dev); software CS
    = its GPIO (and it must not be a kernel CE line of that bus). A kernel-CS and a software-CS channel may share
    a spidev node (tc_plate CE0 and tc_air no_cs + GPIO5 on /dev/spidev0.0): that is the build manual's map."""
    seen: Dict[tuple, str] = {}
    for name in CHANNELS:
        c = sensors.get(name) or {}
        try:
            bus, dev = int(c.get("spi_bus", 0)), int(c.get("spi_dev", 0))
            cs = mx.parse_cs_gpio(c.get("cs_gpio"))
        except (TypeError, ValueError) as exc:
            return "%s: bad spi_bus / spi_dev / cs_gpio: %s" % (name, exc)
        if cs is None:
            key, what = ("kernel", bus, dev), "kernel CS of spidev%d.%d" % (bus, dev)
        else:
            if cs in KERNEL_CS_GPIO.get(bus, {}).values():
                return "%s: cs_gpio %d is a kernel chip-select line of SPI%d" % (name, cs, bus)
            key, what = ("gpio", cs), "software CS GPIO%d" % cs
        if key in seen:
            return "%s and %s share the same chip select (%s)" % (seen[key], name, what)
        seen[key] = name
    return None


def _median(xs: List[float]) -> float:
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def run(argv=None, *, out=None, bench: Optional[mx.FakeBench] = None,
        drivers: Optional[Dict[str, mx.Max31855Driver]] = None,
        sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic) -> int:
    """CLI body. Test hooks: ``bench`` (a FakeBench to use instead of a new one), ``drivers`` (prebuilt drivers),
    ``sleep``/``clock``."""
    out = out or sys.stdout

    def say(s=""):
        print(s, file=out, flush=True)

    a = _parser().parse_args(argv)
    if a.fake_disc_c is not None and not a.fake:
        _parser().error("--fake-disc-c needs --fake")
    if not (a.seconds > 0 and math.isfinite(a.seconds)) or not (0 < a.hz <= 10):
        _parser().error("--seconds must be > 0 and --hz in (0, 10]")
    from .__main__ import load_config
    if not Path(a.config).is_file():
        # load_config would fall back to DEFAULTS (every channel on spidev0.0 kernel CS): never check that
        say("ERROR: config file not found: %s (run from hardware/vehicle-unit or pass --config PATH)" % a.config)
        say("VERDICT: FAIL (exit 1): no config, wiring not checked")
        return EXIT_FAULT
    cfg = load_config(a.config)
    sensors = cfg.get("sensors") or {}
    disc_max = mx.disc_max_c(sensors.get("tc_plate") or {})
    cs_problem = _chip_select_problem(sensors)
    if cs_problem:
        say("ERROR: config: %s" % cs_problem)
        say("VERDICT: FAIL (exit 1): chip selects not distinct, wiring not checked")
        return EXIT_FAULT

    if drivers is None:
        drivers = {}
        if a.fake:
            bench = bench or mx.FakeBench()
            if a.fake_disc_c is not None:
                bench.temps["tc_plate"] = float(a.fake_disc_c)
                bench.exact.add("tc_plate")
            buses: Dict[int, mx.SpiBus] = {}

            def getter(n: int) -> mx.SpiBus:
                return buses.setdefault(n, bench.bus(n))
        else:
            getter = mx.get_bus
        try:
            mx.reserve_cs_from_config(sensors, getter)
        except ValueError as exc:
            say("ERROR: config: %s" % exc)
            return EXIT_FAULT
        for name in CHANNELS:
            c = dict(sensors.get(name) or {})
            kw = {}
            if a.fake:
                b, d = int(c.get("spi_bus", 0)), int(c.get("spi_dev", 0))
                kw = {"spi_factory": (lambda b=b, d=d: bench.spi_factory(b, d)), "bus": getter(b)}
            drivers[name] = mx.Max31855Driver(name, c, lambda m: None, **kw)

    say("wfgvu.tccheck: %s; config %s; %.0f s at %g Hz; disc stop at %.0f C (PETG tabs)"
        % ("SIMULATED bench (--fake, not hardware)" if a.fake else "LIVE", a.config, a.seconds, a.hz, disc_max))
    for name in CHANNELS:
        en = (sensors.get(name) or {}).get("enabled", True)
        say("  %-10s %s%s" % (name, drivers[name].describe(), "" if en else "  (disabled in config; checked anyway)"))

    open_err: Dict[str, Optional[str]] = {}
    try:
        for name in CHANNELS:
            try:
                drivers[name].open()
                open_err[name] = None
            except mx.SpiAccessError as exc:
                say("ERROR: cannot open SPI/GPIO for %s: %s" % (name, exc))
                say(SERVICE_HINT)
                return EXIT_ACCESS
            except mx.NoCsUnsupported as exc:
                open_err[name] = str(exc)
            except Exception as exc:                                     # noqa: BLE001 - chip absent, bad frame
                open_err[name] = "%s: %s" % (type(exc).__name__, exc)

        samples: Dict[str, List[dict]] = {n: [] for n in CHANNELS}
        read_err: Dict[str, List[str]] = {n: [] for n in CHANNELS}
        n_reads = max(1, int(round(a.seconds * a.hz)))
        t0 = clock()
        for i in range(n_reads):
            target = t0 + i / a.hz
            dt = target - clock()
            if dt > 0:
                sleep(dt)
            parts = []
            for name in CHANNELS:
                if open_err[name] is not None:
                    parts.append(_fmt(name, None, open_err[name]))
                    continue
                try:
                    d = drivers[name].read_once()
                except mx.SpiAccessError as exc:
                    say("ERROR: SPI/GPIO lost on %s: %s" % (name, exc))
                    say(SERVICE_HINT)
                    return EXIT_ACCESS
                except Exception as exc:                                 # noqa: BLE001
                    read_err[name].append("%s: %s" % (type(exc).__name__, exc))
                    parts.append(_fmt(name, None, read_err[name][-1]))
                    continue
                samples[name].append(d)
                parts.append(_fmt(name, d, None))
                if name == "tc_plate" and d["temp_c"] is not None and d["temp_c"] >= disc_max:
                    say("[%3d] t=%5.1fs  %s" % (i + 1, clock() - t0, parts[-1]))
                    say("STOP: flux disc at %.2f C >= %.0f C (PETG tabs)" % (d["temp_c"], disc_max))
                    say("WARNING: remove the heat source and let the disc cool below %.0f C before any run; check "
                        "the PETG tabs for softening." % disc_max)
                    return EXIT_DISC
            say("[%3d] t=%5.1fs  %s" % (i + 1, clock() - t0, " | ".join(parts)))

        # ---- verdict
        problems: List[str] = []
        cj_medians: Dict[str, float] = {}
        say("")
        for name in CHANNELS:
            ss = samples[name]
            if open_err[name] is not None:
                problems.append("%s: not open (%s)" % (name, open_err[name]))
                say("%-10s FAIL  not open: %s" % (name, open_err[name]))
                continue
            faults = sorted({(d["fault"] + (" (%s)" % d["fault_detail"] if d.get("fault_detail") else ""))
                             for d in ss if d["fault"]})
            hots = [d["temp_c"] for d in ss if d["temp_c"] is not None]
            cjs = [d["cj_c"] for d in ss if d["cj_c"] is not None]
            bad = []
            if read_err[name]:
                bad.append("%d read errors (%s)" % (len(read_err[name]), read_err[name][-1]))
            if faults:
                bad.append("faults: %s" % ", ".join(faults))
            if not hots:
                bad.append("no hot-junction reading")
            elif min(hots) < HOT_MIN_C or max(hots) > HOT_MAX_C:
                bad.append("hot junction %.2f..%.2f C outside the bench range %g..%g C"
                           % (min(hots), max(hots), HOT_MIN_C, HOT_MAX_C))
            if cjs:
                cj_medians[name] = _median(cjs)
            rng = ("hot %.2f..%.2f C" % (min(hots), max(hots)) if hots else "hot -") + \
                  ("  cj %.2f..%.2f C" % (min(cjs), max(cjs)) if cjs else "  cj -")
            say("%-10s %s  n=%d  %s%s" % (name, "FAIL" if bad else "OK  ", len(ss), rng,
                                         ("  " + "; ".join(bad)) if bad else ""))
            problems += ["%s: %s" % (name, b) for b in bad]
        if len(cj_medians) >= 2:
            spread = max(cj_medians.values()) - min(cj_medians.values())
            ok = spread <= CJ_SPREAD_MAX_C
            say("cold-junction spread between chips: %.2f C (limit %.1f C) %s" % (spread, CJ_SPREAD_MAX_C,
                                                                                  "OK" if ok else "FAIL"))
            if not ok:
                problems.append("cold-junction spread %.2f C > %.1f C" % (spread, CJ_SPREAD_MAX_C))
        words = {n: [d.get("bits") for d in samples[n]] for n in CHANNELS if samples[n]}
        names = sorted(words)
        for i, n1 in enumerate(names):
            for n2 in names[i + 1:]:
                if len(words[n1]) >= 5 and words[n1] == words[n2]:
                    say("WARNING: %s and %s returned identical words on every read: check the chip-select wiring"
                        % (n1, n2))
        if problems:
            say("VERDICT: FAIL (exit 1): " + "; ".join(problems))
            return EXIT_FAULT
        say("VERDICT: PASS (exit 0): all three answer, no faults, plausible bench readings. This does not show "
            "which probe is on which chip: warm each probe by hand and check that only its channel rises.")
        return EXIT_OK
    finally:
        for name in CHANNELS:
            d = (drivers or {}).get(name)
            if d is not None:
                try:
                    d.close()
                except Exception:                                        # noqa: BLE001
                    pass


def main(argv=None) -> int:
    return run(argv)


if __name__ == "__main__":
    sys.exit(main())
