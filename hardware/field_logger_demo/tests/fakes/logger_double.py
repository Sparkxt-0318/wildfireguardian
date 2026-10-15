"""The scripted test double of spec section 3C (tests/fakes/logger_double.py).

The double itself lives in app/device/double.py, because the app can also run it for development
(--dev-device-double). It talks to the link through an in-process port object instead of a pseudo-terminal: a
pseudo-terminal cannot carry DTR and RTS, and the connection check needs restarts on open (per open method), on close
and on unplug. The real host build of the firmware's protocol is tested on a pseudo-terminal in test_protocol_fake.py.

This module adds session files for the result rows: an outdoor session with fixes, a RECOVERED one, NO_NMEA_DATA,
CHECKSUM_ERRORS_ONLY, one without an EVENT and one with a 3 s step between rows. They carry the device id 1A2B3C4D,
like a real logger. They are written by the SIM writer
(app/simgen.py) with the firmware's real row spacing, so they pass usb_export.py verify.
"""
from app import simgen
from app.device.double import DoublePort, LoggerDouble, ManualClock, RealClock
from app.vendor import usb_export as ux

__all__ = ["DoublePort", "LoggerDouble", "ManualClock", "RealClock", "indoor_filler", "outdoor_fix", "recovered",
           "with_step", "check_ok"]
UTC0 = 1791900000000
DEVICE = 0x1A2B3C4D          # like a real logger; 00000000 is reserved for SIM data and is kept with it


def _base(no, mode="WALK", device_id=DEVICE):
    w = simgen.RecordWriter()
    w.start(98000, device_id, no, mode)
    w.status(98004, 4122, 2_543_616, 2_555_904, 1286)
    return w


def indoor_filler(no=1, rows=40, reason=1, event=True, step_ms=1506):
    """Cold start indoors: a NOFIX filler row every 1.5 s (flags0 0xFF), RECEIVER_NO_FIX unless told otherwise."""
    w = _base(no)
    mono = 98000
    for k in range(1, rows + 1):
        mono = 98000 + k * step_ms
        w.nofix(mono, None, 0, reason)
        if event and k == 8:
            w.event(mono + 100, 1, mono - 100, 180)
    w.end(mono + 300, 1)
    return w.data()


def outdoor_fix(no=1, rows=45, device_id=DEVICE):
    w = _base(no, device_id=device_id)
    w.clock(98100, UTC0 + 100)
    lat, lon = 35.1470, 126.8390
    mono = 98000
    for k in range(1, rows + 1):
        mono = 98000 + k * 1000
        w.fix(mono, UTC0 + k * 1000, lat + k * 1e-5, lon, 31.0, 1.2, 0.0, 0.9, 10)
        if k == 10:
            w.event(mono + 300, 1, mono + 100, 180)
    w.end(mono + 300, 1)
    return w.data()


def recovered(no=1, rows=30):
    w = _base(no)
    mono = 98000
    for k in range(1, rows + 1):
        mono = 98000 + k * 1506
        w.nofix(mono, None, 0, 1)
        if k == 5:
            w.event(mono + 100, 1, mono - 100, 180)
    w.end(0, 4)                              # closed by boot recovery: RECOVERED_ON_BOOT, mono unknown
    return w.data()


def with_step(no=1, rows=40, at=20, step_ms=3000):
    w = _base(no)
    mono = 98000
    for k in range(1, rows + 1):
        mono += step_ms if k == at else 1000
        w.nofix(mono, UTC0 + mono, 3, 1)
        if k == 5:
            w.event(mono + 100, 1, mono - 100, 180)
    w.end(mono + 300, 1)
    return w.data()


def check_ok(data):
    rep = ux.integrity(data)
    assert rep["status"] in ("OK", "RECOVERED"), rep
    return data
