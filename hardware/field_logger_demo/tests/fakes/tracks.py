"""Synthetic tracks for the detector and session tests: second-by-second rows in a local metric frame, and the same
rows written as a real format-2 .wfg (optionally with a CLOCK JUMP) by the SIM writer."""
import random
import struct

from app import simgen
from app.geo import Local
from app.vendor import usb_export as ux

LOC = Local(35.1470, 126.8390)
UTC0 = 1791900000000


def build(plan, seed=1, jitter=0.6):
    """plan: list of (kind, seconds, value): ("move", s, speed) | ("stop", s, spread_m) | ("nofix", s, None).
    Returns rows with mono, t, fix, lat, lon, speed, hdop (1 row per second, t from 0)."""
    rnd = random.Random(seed)
    rows, x, t = [], 0.0, 0
    for kind, secs, val in plan:
        for _ in range(int(secs)):
            if kind == "nofix":
                rows.append({"mono": 100000 + t * 1000, "t": float(t), "fix": False, "lat": None, "lon": None,
                             "speed": None, "hdop": None})
                t += 1
                continue
            if kind == "move":
                x += val
                px, py, sp = x + rnd.gauss(0, jitter * 0.3), rnd.gauss(0, jitter * 0.3), val + rnd.gauss(0, 0.03)
            else:
                spread = val if val is not None else jitter
                px, py, sp = x + rnd.gauss(0, spread), rnd.gauss(0, spread), abs(rnd.gauss(0.05, 0.04))
            lat, lon = LOC.ll(px, py)
            rows.append({"mono": 100000 + t * 1000, "t": float(t), "fix": True, "lat": lat, "lon": lon,
                         "speed": max(0.0, sp), "hdop": 0.9})
            t += 1
    return rows


def to_wfg(rows, jump_at_t=None, jump_ms=-3_600_000, mode="WALK"):
    """Write rows as a .wfg: START, STATUS, CLOCK (first UTC) and one FIX/NOFIX record per row, END. With jump_at_t,
    a CLOCK JUMP record moves the receiver's time by jump_ms at that row (UTC labels change; mono does not)."""
    w = simgen.RecordWriter()
    mono0 = rows[0]["mono"] - 1000
    w.start(mono0, 0, 1, mode)
    w.status(mono0 + 4, 4100, 2_500_000, 2_555_904, 1200)
    w.clock(mono0 + 500, UTC0 + 500)
    offset = UTC0 - mono0
    for r in rows:
        if jump_at_t is not None and r["t"] == jump_at_t:
            offset += jump_ms
            utc = offset + r["mono"] - 300
            ymd, ms = simgen._ymd_ms(utc)
            w._add("CLOCK", ux.T_CLOCK, 0, r["mono"] - 300, struct.pack("<IIqqB", ymd, ms, offset, jump_ms, 2))
            w.n["clock"] += 1
        utc = offset + r["mono"]
        if r["fix"]:
            w.fix(r["mono"], utc, r["lat"], r["lon"], 30.0, r["speed"] or 0.0, 0.0, r["hdop"] or 1.0, 10)
        else:
            w.nofix(r["mono"], utc, 3, 1)
    w.end(rows[-1]["mono"] + 300, 1)
    return w.data()
