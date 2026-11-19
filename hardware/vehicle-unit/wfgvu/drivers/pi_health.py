"""Raspberry Pi health (``pi``, 1 Hz): CPU temperature, throttling/under-voltage, input voltage, disk, record size.

Sources (each optional; a missing source gives null, never an exception, so this also runs on macOS):

- CPU temperature: ``/sys/class/thermal/thermal_zone0/temp`` (millidegrees C).
- ``vcgencmd get_throttled`` -> ``throttled=0x50005``. Bits: 0 under-voltage now, 1 ARM frequency capped now,
  2 throttled now, 3 soft temperature limit now, 16..19 the same "has occurred since boot".
  Under-voltage on a Pi 4 means the 5 V rail fell below about 4.63 V; on a 12 V vehicle socket that points at
  the 12 V -> 5 V converter or cabling and makes every sensor reading suspect.
- Input voltage: Pi 5 only, ``vcgencmd pmic_read_adc EXT5V_V`` (``EXT5V_V volt(24)=5.1234V``); Pi 4 has no ADC
  for it, so null.
- ``disk_free_mb``: free space where records are written; ``rec_bytes``: bytes recorded this session (from the
  recorder, via a callable).
"""
from __future__ import annotations

import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable, List, Optional

from .base import Driver

THERMAL_ZONE = Path("/sys/class/thermal/thermal_zone0/temp")
_THROTTLED_RE = re.compile(r"throttled=(0x[0-9a-fA-F]+)")
_EXT5V_RE = re.compile(r"EXT5V_V\s+volt\(\d+\)=([0-9.]+)V")


def parse_throttled(text: Optional[str]) -> dict:
    """``vcgencmd get_throttled`` output -> ``{"throttled_hex","under_voltage_now","under_voltage_ever"}``."""
    m = _THROTTLED_RE.search(text or "")
    if not m:
        return {"throttled_hex": None, "under_voltage_now": None, "under_voltage_ever": None}
    v = int(m.group(1), 16)
    return {"throttled_hex": m.group(1).lower(), "under_voltage_now": bool(v & 0x1),
            "under_voltage_ever": bool(v & 0x10000)}


def parse_ext5v(text: Optional[str]) -> Optional[float]:
    """Pi 5 ``pmic_read_adc`` output -> EXT5V input voltage [V] or None."""
    m = _EXT5V_RE.search(text or "")
    return float(m.group(1)) if m else None


def read_cpu_c(path: Path = THERMAL_ZONE) -> Optional[float]:
    try:
        return int(path.read_text().strip()) / 1000.0
    except (OSError, ValueError):
        return None


def run_cmd(args: List[str], timeout: float = 1.0) -> Optional[str]:
    """Run a command, return stdout or None if it is missing/fails (e.g. ``vcgencmd`` on macOS)."""
    if shutil.which(args[0]) is None:
        return None
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def collect(records_dir: Path, rec_bytes_fn: Optional[Callable[[], Optional[int]]] = None,
            cmd: Callable[[List[str]], Optional[str]] = run_cmd, cpu_path: Path = THERMAL_ZONE) -> dict:
    """One ``pi`` reading."""
    thr = parse_throttled(cmd(["vcgencmd", "get_throttled"]))
    try:
        disk = shutil.disk_usage(str(records_dir if Path(records_dir).exists() else Path.cwd())).free / 1e6
    except OSError:
        disk = None
    rec = None
    if rec_bytes_fn is not None:
        try:
            rec = rec_bytes_fn()
        except Exception:                                   # noqa: BLE001
            rec = None
    return {"cpu_c": read_cpu_c(cpu_path), "throttled_hex": thr["throttled_hex"],
            "under_voltage_now": thr["under_voltage_now"], "under_voltage_ever": thr["under_voltage_ever"],
            "input_v": parse_ext5v(cmd(["vcgencmd", "pmic_read_adc", "EXT5V_V"])), "disk_free_mb": disk,
            "rec_bytes": rec}


class PiHealthDriver(Driver):
    """cfg: ``rate_hz`` (1), ``records_dir``. ``rec_bytes_fn`` returns the recorder's byte count."""

    def __init__(self, name, cfg, emit, sim_source=None, *, ctx=None, rec_bytes_fn=None, cmd=run_cmd):
        super().__init__(name, cfg, emit, sim_source, ctx=ctx)
        self.rec_bytes_fn = rec_bytes_fn
        self.cmd = cmd
        self._next = 0.0

    def open(self) -> None:
        return None                       # the host is always there

    def read(self) -> List[dict]:
        period = 1.0 / float(self.cfg.get("rate_hz", 1.0))
        now = time.monotonic()
        if self._next > now and not self.sleep(self._next - now):
            return []
        self._next = max(self._next + period, time.monotonic())
        return [collect(Path(self.cfg.get("records_dir", "records")), self.rec_bytes_fn, self.cmd)]

    def assess(self, data: dict):
        if data.get("under_voltage_now"):
            return False, "under-voltage now (throttled=%s)" % data.get("throttled_hex")
        return True, ""
