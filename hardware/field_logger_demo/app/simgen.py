"""SIM sessions: real format-2 .wfg files written by a Python writer whose output passes usb_export.py verify.

They behave like real GNSS: 1 Hz rows, a cold start (gap-filler rows every 1.5 s until the receiver has a time, then
no-fix rows until the first fix), position error that wanders slowly (a correlated drift plus a little white noise),
Doppler speed near 0 at stops, a 20 s no-fix gap and a few short dropouts, STATUS every 60 s, button marks at most
stops plus one missed stop and one stray press. The device id is the reserved 00000000, every file gets a .sim.json
sidecar with the ground truth, and the files live only in sessions/sim/.
"""
import binascii
import datetime as dt
import json
import math
import random
import struct

from .geo import Local
from .vendor import usb_export as ux
from . import mapgen

V_FIX = (ux.V_TIME | ux.V_DATE | ux.V_POS | ux.V_ALT | ux.V_SPEED | ux.V_COURSE | ux.V_HDOP | ux.V_SATS | ux.V_RMC
         | ux.V_FIXTYPE)
V_NOFIX_TIMED = ux.V_TIME | ux.V_DATE | ux.V_SATS | ux.V_RMC | ux.V_FIXTYPE
MODE_CODE = {"UNKNOWN": 0, "WALK": 1, "VEHICLE": 2}
LOCATE_MAX_AGE_MS = 2000


def _ymd_ms(epoch_ms):
    d = dt.datetime.fromtimestamp(epoch_ms / 1000.0, tz=dt.timezone.utc)
    return d.year * 10000 + d.month * 100 + d.day, (d.hour * 3600 + d.minute * 60 + d.second) * 1000 + d.microsecond // 1000


class RecordWriter:
    """Writes 48-byte format-2 records exactly as laid out in DATA_SCHEMA.md / wfg_record.h."""

    def __init__(self):
        self.recs = []
        self.kinds = []
        self.crc = 0
        self.n = {"fix": 0, "nofix": 0, "events": 0, "clock": 0, "status": 0}
        self.last_fix = None   # (seq, mono, lat, lon)

    @property
    def seq(self):
        return len(self.recs)

    def _add(self, kind, rtype, flags0, mono, payload):
        body = (struct.pack("<2sBBII", b"WF", rtype, flags0, self.seq, mono) + payload).ljust(44, b"\0")
        rec = body + struct.pack("<I", binascii.crc32(body) & 0xFFFFFFFF)
        self.crc = binascii.crc32(rec, self.crc) & 0xFFFFFFFF
        self.recs.append(rec)
        self.kinds.append(kind)
        return self.seq - 1

    def start(self, mono, device_id, session_no, mode, boot=3, reset_reason=1, start_reason=0, resumed_from=0):
        """start_reason 0 OWNER_BUTTON, 1 AUTO_RESUMED_AFTER_RESET (stored in header flags0, as encode() does)."""
        p = struct.pack("<IIBBHHBBIIII", device_id, session_no, MODE_CODE[mode], 80, 2, 1000, 2, 48, boot,
                        resumed_from, reset_reason, LOCATE_MAX_AGE_MS)
        return self._add("START", ux.T_START, start_reason, mono, p)

    def status(self, mono, vbat_mv, free, total, nmea_ok, nmea_bad=0):
        pin = vbat_mv // 2
        p = struct.pack("<HHHBxIIIII", pin * 2, pin, 2000, 1 | 2 | 4, free, total, nmea_ok, nmea_bad, 182344)
        self.n["status"] += 1
        return self._add("STATUS", ux.T_STATUS, 0, mono, p)

    def clock(self, mono, utc_epoch_ms):
        ymd, ms = _ymd_ms(utc_epoch_ms)
        p = struct.pack("<IIqqB", ymd, ms, utc_epoch_ms - mono, 0, 1)
        self.n["clock"] += 1
        return self._add("CLOCK", ux.T_CLOCK, 0, mono, p)

    def fix(self, mono, utc_epoch_ms, lat, lon, alt, speed, course, hdop, sats, age_ms=50):
        ymd, ms = _ymd_ms(utc_epoch_ms)
        p = struct.pack("<IIiiiHHHBBBBH", ymd, ms, int(round(lat * 1e7)), int(round(lon * 1e7)), int(round(alt * 100)),
                        max(0, int(round(speed * 100))), int(round(course * 100)) % 36000, int(round(hdop * 100)),
                        sats, 1, 3, 0, V_FIX)
        self.n["fix"] += 1
        s = self._add("FIX", ux.T_FIX, min(254, age_ms // 10), mono, p)
        self.last_fix = (s, mono, lat, lon)
        return s

    def nofix(self, mono, utc_epoch_ms=None, sats=0, reason=1):
        """utc_epoch_ms None: a gap-filler row (no epoch, receiver without time): flags0 0xFF like writeFiller(),
        which sets the checksum-error bit only for CHECKSUM_ERRORS_ONLY."""
        if utc_epoch_ms is None:
            p = struct.pack("<IIiiiHHHBBBBH", 0, 0xFFFFFFFF, 0, 0, 0, 0, 0, 0, 0, 0xFF, 0, reason,
                            ux.V_CKSUM if reason == 3 else 0)
            flags0 = 0xFF
        else:
            ymd, ms = _ymd_ms(utc_epoch_ms)
            p = struct.pack("<IIiiiHHHBBBBH", ymd, ms, 0, 0, 0, 0, 0, 0, sats, 0, 1, reason, V_NOFIX_TIMED)
            flags0 = 5
        self.n["nofix"] += 1
        return self._add("NOFIX", ux.T_NOFIX, flags0, mono, p)

    def event(self, now_mono, event_no, press_mono, dur_ms):
        ref_seq, ref_age, located, lat, lon = 0xFFFFFFFF, 0xFFFFFFFF, 0, 0, 0
        if self.last_fix and press_mono - self.last_fix[1] >= 0:
            ref_seq, ref_age = self.last_fix[0], press_mono - self.last_fix[1]
            if ref_age <= LOCATE_MAX_AGE_MS:
                located, lat, lon = 1, int(round(self.last_fix[2] * 1e7)), int(round(self.last_fix[3] * 1e7))
        p = struct.pack("<IIiiIIHBB", event_no, ref_seq, lat, lon, ref_age, press_mono, dur_ms, located, 1)
        self.n["events"] += 1
        return self._add("EVENT", ux.T_EVENT, 0, now_mono, p)

    def end(self, mono, reason=1):
        p = bytes([reason, 0, 0, 0]) + struct.pack("<IIIIIII", self.seq, self.n["fix"], self.n["nofix"],
                                                   self.n["events"], self.crc, 0, self.n["clock"])
        return self._add("END", ux.T_END, 0, mono, p)

    def data(self):
        return b"".join(self.recs)


class Path:
    def __init__(self, pts):
        self.pts = pts
        self.cum = [0.0]
        for a, b in zip(pts, pts[1:]):
            self.cum.append(self.cum[-1] + math.dist(a, b))
        self.length = self.cum[-1]

    def at(self, d):
        d = max(0.0, min(self.length, d))
        for k in range(len(self.pts) - 1):
            if d <= self.cum[k + 1] or k == len(self.pts) - 2:
                seg = self.cum[k + 1] - self.cum[k] or 1.0
                f = (d - self.cum[k]) / seg
                (x0, y0), (x1, y1) = self.pts[k], self.pts[k + 1]
                return x0 + (x1 - x0) * f, y0 + (y1 - y0) * f, math.degrees(math.atan2(x1 - x0, y1 - y0)) % 360


def offset_path(pts, off):
    """Shift a polyline sideways by `off` metres (positive = right of travel), e.g. onto a pavement or a lane."""
    out = []
    for k in range(len(pts)):
        if k == 0:
            dx, dy = pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]
        elif k == len(pts) - 1:
            dx, dy = pts[k][0] - pts[k - 1][0], pts[k][1] - pts[k - 1][1]
        else:
            ax, ay = pts[k][0] - pts[k - 1][0], pts[k][1] - pts[k - 1][1]
            bx, by = pts[k + 1][0] - pts[k][0], pts[k + 1][1] - pts[k][1]
            la, lb = math.hypot(ax, ay) or 1, math.hypot(bx, by) or 1
            dx, dy = ax / la + bx / lb, ay / la + by / lb
        n = math.hypot(dx, dy) or 1.0
        rx, ry = dy / n, -dx / n          # right-hand normal for x east, y north
        out.append((pts[k][0] + rx * off, pts[k][1] + ry * off))
    return out


def simulate(spec, seed=1):
    """spec: dict with name, mode, route (list of (x, y) metres), stops [(dist_m, dur_s, press)], gaps [(dist_m, s)],
    dropouts [(dist_m, s)], stray [dist_m], speed (m/s), utc_start (aware datetime), session_no, lead_in, lead_out."""
    rnd = random.Random(seed)
    loc = Local(*mapgen.CENTER)
    path = Path(spec["route"])
    mode = spec["mode"]
    veh = mode == "VEHICLE"
    sigma = 1.5 if veh else 1.0
    w = RecordWriter()
    mono0 = 100000 + rnd.randint(0, 50000)
    utc0 = int(spec["utc_start"].timestamp() * 1000)
    w.start(mono0, 0, spec["session_no"], mode)
    free = 2_400_000 - spec["session_no"] * 37_000
    nmea = 900 + rnd.randint(0, 400)
    vbat = 4060 - spec["session_no"] * 12
    w.status(mono0 + 4, vbat, free, 2_555_904, nmea)
    bias = [0.0, 0.0]

    def noisy(x, y, moving):
        s = sigma * (1.25 if moving else 1.0)
        bias[0] = 0.96 * bias[0] + rnd.gauss(0, s * 0.18)
        bias[1] = 0.96 * bias[1] + rnd.gauss(0, s * 0.18)
        return x + bias[0] + rnd.gauss(0, s * 0.2), y + bias[1] + rnd.gauss(0, s * 0.2)

    truth = {"stops": [], "presses": [], "gaps": [], "lead_in_s": spec["lead_in"], "lead_out_s": spec["lead_out"]}
    t = 0.0
    last_status = 0.0
    event_no = 0
    rows = 0

    def mono_at(tt):
        return mono0 + int(round(tt * 1000))

    def tick_status(tt):
        nonlocal last_status, vbat, free
        while tt - last_status >= 60.0:
            last_status += 60.0
            vbat -= rnd.randint(1, 3)
            free = 2_400_000 - spec["session_no"] * 37_000 - ((w.seq * 48) // 4096) * 4096
            w.status(mono_at(last_status), vbat, free, 2_555_904, nmea)

    def press(tt, stray=False):
        nonlocal event_no
        event_no += 1
        dur = rnd.randint(140, 260)
        pm = mono_at(tt)
        w.event(pm + dur + 20, event_no, pm, dur)
        truth["presses"].append({"event_no": event_no, "t_press": round(tt, 3), "stray": stray})

    def utc(tt):
        return utc0 + int(round(tt * 1000))

    # --- cold start: no time for ~12 s (gap filler every 1.5 s), then time without fix, then fixes while standing
    x0, y0, crs = path.at(0.0)
    k = 1
    while 1.5 * k < 12.0:
        tt = 1.5 * k + 0.006 * k
        nmea += 9
        w.nofix(mono_at(tt), None, 0, 1)
        k += 1
    w.clock(mono_at(12.2), utc(12.2))
    t = 13.0
    first_fix_t = 31.0
    while t < spec["lead_in"]:
        tick_status(t)
        nmea += 13
        if t < first_fix_t:
            w.nofix(mono_at(t), utc(t), rnd.randint(2, 5), 1)
        else:
            x, y = noisy(x0, y0, False)
            lat, lon = loc.ll(x, y)
            w.fix(mono_at(t), utc(t), lat, lon, 31.0 + rnd.gauss(0, 0.4), abs(rnd.gauss(0.04, 0.03)),
                  (crs + rnd.gauss(0, 20)) % 360, rnd.choice([0.9, 1.0, 1.1, 1.3]), rnd.randint(7, 10))
        rows += 1
        t += 1.0

    # --- movement with stops, gaps, dropouts and stray presses
    stops = sorted(spec["stops"])
    gaps = sorted(spec.get("gaps", []))
    drops = sorted(spec.get("dropouts", []))
    strays = sorted(spec.get("stray", []))
    d = 0.0
    v_cruise = spec["speed"]
    stop_i = 0
    nofix_left = 0
    in_gap = False
    v_prev = 0.0
    while d < path.length - 1e-6:
        tick_status(t)
        nmea += 13
        # speed for this second
        if veh:
            nxt = stops[stop_i][0] if stop_i < len(stops) else path.length
            room = max(0.0, nxt - d)
            v = min(v_cruise * (0.92 + 0.08 * math.sin(t / 23.0)), math.sqrt(2 * 1.3 * room) + 0.4, v_prev + 2.0)
            v = max(v, 0.6)
        else:
            v = v_cruise + 0.07 * math.sin(t / 9.0) + rnd.gauss(0, 0.03)
        v_prev = v
        nd = d + v
        # stop reached during this second?
        if stop_i < len(stops) and nd >= stops[stop_i][0]:
            nd = stops[stop_i][0]
        x, y, crs = path.at(nd)
        # gap / dropout handling: positions are not recorded while no fix
        for gd, gs in gaps:
            if d < gd <= nd and not in_gap:
                nofix_left, in_gap = gs, True
                truth["gaps"].append({"t0": round(t, 3), "t1": round(t + gs, 3), "s": gs})
        for dd, ds in drops:
            if d < dd <= nd and nofix_left == 0:
                nofix_left = ds
        if nofix_left > 0:
            w.nofix(mono_at(t), utc(t), rnd.randint(3, 6), 1)
            nofix_left -= 1
            if nofix_left == 0:
                in_gap = False
        else:
            xn, yn = noisy(x, y, True)
            lat, lon = loc.ll(xn, yn)
            w.fix(mono_at(t), utc(t), lat, lon, 31.0 + rnd.gauss(0, 0.6), v + rnd.gauss(0, 0.04),
                  (crs + rnd.gauss(0, 3)) % 360, rnd.choice([0.8, 0.9, 0.9, 1.0]), rnd.randint(9, 12))
        for sd in strays:
            if d < sd <= nd:
                press(t + 0.4, stray=True)
        rows += 1
        d = nd
        t += 1.0
        if stop_i < len(stops) and d >= stops[stop_i][0] - 1e-6:
            sd, dur, has_press = stops[stop_i]
            t_stop0 = t
            for s in range(int(dur)):
                tick_status(t)
                nmea += 13
                xs, ys = noisy(x, y, False)
                lat, lon = loc.ll(xs, ys)
                w.fix(mono_at(t), utc(t), lat, lon, 31.0 + rnd.gauss(0, 0.4), abs(rnd.gauss(0.05, 0.035)),
                      (crs + rnd.gauss(0, 15)) % 360, rnd.choice([0.9, 0.9, 1.0]), rnd.randint(9, 12))
                if has_press and s == 2:
                    press(t + 0.3)
                rows += 1
                t += 1.0
            lat_c, lon_c = loc.ll(x, y)
            truth["stops"].append({"n": len(truth["stops"]) + 1, "t0": round(t_stop0, 3), "t1": round(t - 1.0, 3),
                                   "dur": dur, "lat": round(lat_c, 7), "lon": round(lon_c, 7), "press": has_press})
            stop_i += 1
            v_prev = 0.0
    # --- lead-out: standing at the end
    xe, ye, crs = path.at(path.length)
    for _ in range(int(spec["lead_out"])):
        tick_status(t)
        xs, ys = noisy(xe, ye, False)
        lat, lon = loc.ll(xs, ys)
        w.fix(mono_at(t), utc(t), lat, lon, 31.0, abs(rnd.gauss(0.04, 0.03)), crs, 0.9, rnd.randint(9, 12))
        rows += 1
        t += 1.0
    w.end(mono_at(t + 0.3), 1)
    data = w.data()
    rep = ux.integrity(data)
    if not rep["ok"]:
        raise RuntimeError("SIM writer produced an invalid file: %r" % rep)
    truth["duration_s"] = round(t, 3)
    truth["path_m"] = round(path.length, 1)
    return data, truth


# ----------------------------------------------------------------------------- the four library sessions
KST = dt.timezone(dt.timedelta(hours=9))


def _route(corners, off):
    return offset_path([mapgen.g2m(u, v) for u, v in corners], off)


def _along(route_pts, corner_index):
    p = Path(route_pts)
    return p.cum[corner_index]


def library_specs():
    walk_pts = _route([(-3.6, 2), (-1, 2), (-1, 1), (1, 1), (1, -1), (2, -1), (2, -2), (3.4, -2)], 7.0)
    wp = Path(walk_pts)
    river_cross = wp.cum[4] - 1.0 * mapgen.BLOCK - 8.0      # on the 4th leg, where the river runs
    walk = {"name": "sim_walk_4_crossings", "mode": "WALK", "route": walk_pts, "speed": 1.34, "session_no": 1,
            "utc_start": dt.datetime(2026, 10, 14, 16, 5, 23, tzinfo=KST), "lead_in": 60, "lead_out": 30,
            "stops": [(wp.cum[1], 42, True), (wp.cum[3], 18, True), (wp.cum[5], 52, True), (wp.cum[6], 25, False)],
            "gaps": [(river_cross + 12.0, 20)], "dropouts": [(wp.cum[2] + 40.0, 1), (wp.cum[6] + 60.0, 2)],
            "stray": [wp.cum[2] + 70.0],
            "title_ko": "도보 · 교차로 4곳", "title_en": "Walk · 4 crossings", "marks_are_stops": True}
    veh_pts = _route([(-8, -4), (-8, 2), (0, 2), (0, -4), (6, -4), (6, 7), (14, 7), (14, 0), (7, 0)], 3.5)
    vp = Path(veh_pts)
    veh = {"name": "sim_vehicle_6_lights", "mode": "VEHICLE", "route": veh_pts, "speed": 11.5, "session_no": 2,
           "utc_start": dt.datetime(2026, 10, 16, 17, 40, 10, tzinfo=KST), "lead_in": 60, "lead_out": 25,
           "stops": [(vp.cum[1], 38, True), (vp.cum[2], 55, True), (vp.cum[3], 27, True), (vp.cum[4], 44, True),
                     (vp.cum[5] + 150.0, 31, True), (vp.cum[7], 48, True)],
           "gaps": [(vp.cum[6] + 400.0, 20)], "dropouts": [(vp.cum[2] + 300.0, 2)], "stray": [],
           "title_ko": "차량 · 신호등 6곳", "title_en": "Vehicle · 6 traffic lights", "marks_are_stops": True}
    # 30 m loop: a 10 m x 5 m rounded loop in the park, three laps with one stop
    cx, cy = mapgen.g2m(-2.5, -1.5)
    loop = []
    for k in range(25):
        a = 2 * math.pi * k / 24
        loop.append((cx + 6.0 * math.cos(a), cy + 3.0 * math.sin(a)))
    loop_pts = loop[:-1] * 3 + [loop[0]]
    lp = Path(loop_pts)
    small = {"name": "sim_walk_30m_loop", "mode": "WALK", "route": loop_pts, "speed": 1.0, "session_no": 3,
             "utc_start": dt.datetime(2026, 10, 14, 16, 40, 0, tzinfo=KST), "lead_in": 60, "lead_out": 20,
             "stops": [(lp.length / 3.0, 20, True)], "gaps": [], "dropouts": [], "stray": [],
             "title_ko": "도보 · 30 m 작은 순환", "title_en": "Walk · small 30 m loop", "marks_are_stops": True,
             "auto_zones": False}   # a 30 m loop lies wholly inside 150 m zones; SIM data has no home to hide
    drive_pts = _route([(0, 0), (28, 0), (28, 21), (7, 21)], 3.5)
    dp = Path(drive_pts)
    drive = {"name": "sim_drive_10km", "mode": "VEHICLE", "route": drive_pts, "speed": 15.0, "session_no": 4,
             "utc_start": dt.datetime(2026, 10, 17, 10, 12, 0, tzinfo=KST), "lead_in": 60, "lead_out": 25,
             "stops": [(dp.cum[1], 41, True), (dp.cum[2] + 1050.0, 33, True), (dp.cum[2] + 2100.0, 36, True)],
             "gaps": [(dp.cum[2] - 900.0, 20)], "dropouts": [(dp.cum[1] + 1500.0, 2)], "stray": [],
             "title_ko": "차량 · 10 km 주행", "title_en": "Vehicle · 10 km drive", "marks_are_stops": True}
    return [walk, veh, small, drive]


def write_library(sim_dir, seed=7):
    """Write the four SIM sessions and their sidecars. Returns sessions.json entries."""
    sim_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for key, spec in enumerate(library_specs(), 1):
        data, truth = simulate(spec, seed=seed + key)
        name = "%s.wfg" % spec["name"]
        (sim_dir / name).write_bytes(data)
        side = {"generator": "app/simgen.py", "seed": seed + key, "simulated": True,
                "device_id": "00000000", "area": mapgen.AREA, "mode": spec["mode"],
                "note": "SIMULATED: not a real recording. Ground truth below is what the generator did.",
                "truth": truth}
        (sim_dir / (name + ".sim.json")).write_text(json.dumps(side, indent=1), encoding="utf-8")
        entries.append({"key": key, "file": "sim/" + name, "title_ko": spec["title_ko"], "title_en": spec["title_en"],
                        "area": mapgen.AREA, "tz": "Asia/Seoul", "marks_are_stops": spec["marks_are_stops"],
                        "privacy": {"auto_zones": spec.get("auto_zones", True), "radius_m": 150}})
    return entries
