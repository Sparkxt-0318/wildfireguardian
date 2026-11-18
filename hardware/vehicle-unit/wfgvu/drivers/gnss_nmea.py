"""USB GNSS receiver, NMEA 0183 over a serial port (``gnss``). Pure parser + ``pyserial`` reader.

Sentences used (any talker: GP, GN, GL, GA, GB, BD): GGA (time, position, fix quality, satellites, HDOP,
altitude above mean sea level), RMC (time, status, position, speed over ground in knots, course over ground,
date), VTG (course, speed in knots and km/h). Checksums (XOR of the bytes between ``$`` and ``*``) are required;
sentences without or with a wrong checksum are rejected.

Epoch assembly: sentences are grouped by their UTC time field. An epoch is emitted when GGA and RMC for the same
time have both arrived, or when a sentence with a newer time arrives (whatever the old epoch had). VTG (no time
field) is attached to the current epoch.

Wire ``fix`` mapping: 0 = no usable fix (GGA quality 0, 6 = dead reckoning, 7 = manual, 8 = simulation, or RMC
status V); 1 = autonomous GNSS fix (quality 1); 2 = differential/RTK class (2, 3, 4, 5, 9). With fix 0 every
position/speed/course field is null. ``speed_m_s`` = knots x 0.514444 (or km/h / 3.6). ``hdop`` is
dimensionless, not an error in metres. ``alt_m`` is GGA altitude (above the geoid). ``utc`` is ISO 8601 when a
date is known (from RMC), else null. Course is degrees true, clockwise from north; null when the receiver gives
none (typical below ~0.5 m/s). Not verified on the actual receiver.
"""
from __future__ import annotations

import time
from typing import Dict, List, Optional

from .base import DeviceUnavailable, Driver, first_present

KNOT_M_S = 0.514444


class NMEAError(ValueError):
    pass


def checksum(body: str) -> int:
    c = 0
    for ch in body.encode("ascii", "replace"):
        c ^= ch
    return c


def split_sentence(line: str) -> List[str]:
    """Validate ``$...*hh`` and return the comma fields (first = e.g. 'GNGGA'). Raises ``NMEAError``."""
    line = line.strip()
    if not line.startswith("$") or "*" not in line:
        raise NMEAError("not an NMEA sentence")
    body, _, cs = line[1:].rpartition("*")
    if len(cs) < 2:
        raise NMEAError("missing checksum")
    try:
        want = int(cs[:2], 16)
    except ValueError as exc:
        raise NMEAError("bad checksum field") from exc
    if checksum(body) != want:
        raise NMEAError("checksum mismatch")
    return body.split(",")


def _f(x: str) -> Optional[float]:
    try:
        return float(x) if x != "" else None
    except ValueError:
        return None


def parse_latlon(value: str, hemi: str) -> Optional[float]:
    """``ddmm.mmmm`` / ``dddmm.mmmm`` + N/S/E/W -> signed decimal degrees."""
    if not value or hemi not in ("N", "S", "E", "W"):
        return None
    try:
        dot = value.index(".") if "." in value else len(value)
        deg = int(value[:dot - 2])
        minutes = float(value[dot - 2:])
    except ValueError:
        return None
    if minutes >= 60.0:
        return None
    out = deg + minutes / 60.0
    return -out if hemi in ("S", "W") else out


def _time(x: str) -> Optional[str]:
    """``hhmmss.ss`` -> ``hh:mm:ss.sss`` (None if empty/bad)."""
    if len(x) < 6:
        return None
    try:
        hh, mm, ss = int(x[0:2]), int(x[2:4]), float(x[4:])
    except ValueError:
        return None
    if hh > 23 or mm > 59 or ss >= 61:
        return None
    return "%02d:%02d:%06.3f" % (hh, mm, ss)


def parse_sentence(line: str) -> Dict:
    """Parse one GGA/RMC/VTG sentence into a dict with ``kind``; other types -> ``{"kind": "other"}``."""
    f = split_sentence(line)
    kind = f[0][-3:]
    if kind == "GGA" and len(f) >= 10:
        q = int(f[6]) if f[6].isdigit() else 0
        return {"kind": "GGA", "time": _time(f[1]), "lat": parse_latlon(f[2], f[3]),
                "lon": parse_latlon(f[4], f[5]), "quality": q, "sats": int(f[7]) if f[7].isdigit() else None,
                "hdop": _f(f[8]), "alt_m": _f(f[9])}
    if kind == "RMC" and len(f) >= 10:
        knots = _f(f[7])
        date = f[9]
        iso_date = None
        if len(date) == 6 and date.isdigit():
            iso_date = "20%s-%s-%s" % (date[4:6], date[2:4], date[0:2])
        return {"kind": "RMC", "time": _time(f[1]), "valid": f[2] == "A", "lat": parse_latlon(f[3], f[4]),
                "lon": parse_latlon(f[5], f[6]), "speed_m_s": None if knots is None else knots * KNOT_M_S,
                "course_deg": _f(f[8]), "date": iso_date}
    if kind == "VTG" and len(f) >= 8:
        knots, kmh = _f(f[5]), _f(f[7])
        speed = kmh / 3.6 if kmh is not None else (knots * KNOT_M_S if knots is not None else None)
        mode = f[9] if len(f) > 9 else ""
        return {"kind": "VTG", "course_deg": _f(f[1]), "speed_m_s": speed, "valid": mode not in ("N",)}
    return {"kind": "other", "type": f[0]}


def fix_from_quality(q: int) -> int:
    if q == 1:
        return 1
    if q in (2, 3, 4, 5, 9):
        return 2
    return 0


class GnssAssembler:
    """Groups GGA/RMC/VTG by time into ``gnss`` readings. ``feed(line) -> list[data]``."""

    def __init__(self):
        self.cur: Dict = {}
        self.cur_time: Optional[str] = None
        self.last_date: Optional[str] = None
        self.bad = 0

    def feed(self, line: str) -> List[dict]:
        try:
            s = parse_sentence(line)
        except NMEAError:
            self.bad += 1
            return []
        out: List[dict] = []
        if s["kind"] in ("GGA", "RMC"):
            if s["time"] is not None and self.cur_time is not None and s["time"] != self.cur_time and self.cur:
                out.append(self._flush())
            self.cur_time = s["time"]
            self.cur[s["kind"]] = s
            if s["kind"] == "RMC" and s["date"]:
                self.last_date = s["date"]
            if "GGA" in self.cur and "RMC" in self.cur:
                out.append(self._flush())
        elif s["kind"] == "VTG":
            self.cur["VTG"] = s
        return out

    def _flush(self) -> dict:
        gga, rmc, vtg = self.cur.get("GGA"), self.cur.get("RMC"), self.cur.get("VTG")
        t = self.cur_time
        self.cur = {}
        if gga is not None:
            fix = fix_from_quality(gga["quality"])
            if rmc is not None and not rmc["valid"]:
                fix = 0
        else:
            fix = 1 if (rmc is not None and rmc["valid"]) else 0
        src = gga if gga is not None else (rmc or {})
        lat, lon = src.get("lat"), src.get("lon")
        speed = course = None
        if rmc is not None:
            speed, course = rmc["speed_m_s"], rmc["course_deg"]
        if vtg is not None and vtg["valid"]:
            speed = vtg["speed_m_s"] if vtg["speed_m_s"] is not None else speed
            course = vtg["course_deg"] if vtg["course_deg"] is not None else course
        if lat is None or lon is None:
            fix = 0
        date = (rmc or {}).get("date") or self.last_date
        utc = "%sT%sZ" % (date, t) if (date and t) else None
        if fix == 0:
            return {"fix": 0, "lat": None, "lon": None, "alt_m": None, "speed_m_s": None, "course_deg": None,
                    "hdop": gga["hdop"] if gga else None, "sats": gga["sats"] if gga else None, "utc": utc}
        return {"fix": fix, "lat": lat, "lon": lon, "alt_m": gga["alt_m"] if gga else None, "speed_m_s": speed,
                "course_deg": course, "hdop": gga["hdop"] if gga else None, "sats": gga["sats"] if gga else None,
                "utc": utc}


class GnssDriver(Driver):
    """cfg: ``port`` (/dev/ttyACM0), ``baud`` (9600). ``raw_sink(bytes)`` (VU-R6) receives every raw serial line
    (bad checksums and GSA/GSV included) prefixed with the Pi ``time.monotonic()`` (b"%.6f " % t), so the recorder's
    ``gnss_nmea.bin`` can be re-analysed with timing. ``parser_stats`` reports the rejected-sentence count."""

    def __init__(self, name, cfg, emit, sim_source=None, *, ctx=None, serial_factory=None, raw_sink=None):
        super().__init__(name, cfg, emit, sim_source, ctx=ctx)
        self.raw_sink = raw_sink
        self._serial_factory = serial_factory
        self._ser = None
        self.asm = GnssAssembler()

    def open(self) -> None:
        if self._serial_factory is not None:
            self._ser = self._serial_factory()
        else:
            serial = first_present(["serial"])
            if serial is None:
                raise DeviceUnavailable("python module pyserial not installed")
            self._ser = serial.Serial(self.cfg.get("port", "/dev/ttyACM0"), int(self.cfg.get("baud", 9600)),
                                      timeout=0.2)
        self.asm = GnssAssembler()

    def read(self) -> List[dict]:
        raw = self._ser.readline()
        if not raw:
            return []                # serial timeout: nothing this time
        if self.raw_sink is not None:
            try:
                self.raw_sink(b"%.6f " % time.monotonic() + bytes(raw) + (b"" if bytes(raw).endswith(b"\n")
                                                                          else b"\n"))
            except Exception:                                # noqa: BLE001 - recording must not stop the GNSS
                pass
        return self.asm.feed(raw.decode("ascii", "replace"))

    def parser_stats(self) -> str:
        return "nmea_bad=%d" % int(getattr(self.asm, "bad", 0))

    def close(self) -> None:
        if self._ser is not None:
            try:
                self._ser.close()
            finally:
                self._ser = None

    def assess(self, data: dict):
        # a reading without a fix is still a live receiver: good for freshness; the laptop checks fix itself
        return True, ""
