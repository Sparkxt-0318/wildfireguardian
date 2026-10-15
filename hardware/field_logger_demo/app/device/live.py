"""LIVE mode (spec sections 5 and 8; firmware 0.3.0): '#J' JSON lines and '#N' raw NMEA from the device.

The rows of the session being recorded are collected from the 'ep' lines and run through the same stop detector as
REPLAY (app/stops.py), 2 s late with the same centred window, so both give the same stops; when the session ends the
detector runs once more over the whole session, exactly as REPLAY does.

Privacy, as in REPLAY and the exports (spec section 7): positions inside a privacy zone never reach the page. The
zones are the 150 m around the first fix of the live session (from that fix on), the named zones of
sessions/privacy.json (from the start of the session; drawn only once the route enters one) and, once the session has
ended, the 150 m around its last fix. Positions the device reports
while it is not recording are never shown either: before a recording the logger usually sits where the walk will
start, after it where the walk ended. Masking applies to the page's rows, to the raw '#J' lines (coordinates, and the
position bytes and CRC of a record's hex) and to the raw '#N' sentences (every field after the time). When the end
zone is added, the lines already on the page that fall inside it are masked again (event "rezone").
"""
import datetime as dt
import json
import re
from zoneinfo import ZoneInfo

from .. import config, geo, privacy, stops
from ..vendor import usb_export as ux

DETECT_LAG_S = 2.0
GSV = re.compile(r"^\$([A-Z]{2})GSV,")                  # any talker: GP, GL, GA, GB, BD, GQ, GN ...
SENTENCE = re.compile(r"^\$([A-Z]{2})([A-Z]{3}),")
NMEA_LATLON = {"GGA": 2, "RMC": 3, "GLL": 1, "GNS": 2}   # field index of the latitude (then N/S, longitude, E/W)
NMEA_TIME = ("GGA", "RMC", "GNS")                        # field 1 is the time
NO_POSITION = ("GSV", "GSA", "VTG", "ZDA", "TXT", "GST", "GBS", "GRS")   # types that never carry a position


def _utc_ms(iso):
    """The 'utc' of an 'ep' line ("2026-10-03T03:12:17.000Z", or null) in epoch ms."""
    if not iso:
        return None
    try:
        return int(dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp() * 1000)
    except ValueError:
        return None


def nmea_fields(body):
    """What a sentence holds, for masking: ("safe", None) for a type that never carries a position, ("empty", None)
    for a GGA, RMC, GLL or GNS whose position fields are all empty (no fix), ("pos", (lat, lon)), or ("unknown", None)
    for anything else: another type, a proprietary sentence, or a position that cannot be read (a lost comma, a
    garbled digit; the firmware forwards sentences with bad checksums too). Unknown is masked whenever positions are
    hidden at all: masking fails closed."""
    m = SENTENCE.match(body)
    if not m:
        return "unknown", None
    typ = m.group(2)
    if typ in NO_POSITION:
        return "safe", None
    if typ not in NMEA_LATLON:
        return "unknown", None
    f = body.split("*")[0].split(",")
    k = NMEA_LATLON[typ]
    fields = f[k:k + 4]
    if len(fields) == 4 and not any(x.strip() for x in fields):
        return "empty", None
    try:
        la, ns, lo, ew = fields
        if ns not in ("N", "S") or ew not in ("E", "W") or not re.fullmatch(r"\d{4}\.\d+", la) \
                or not re.fullmatch(r"\d{5}\.\d+", lo):
            return "unknown", None
        lat = int(la[:2]) + float(la[2:]) / 60.0
        lon = int(lo[:3]) + float(lo[3:]) / 60.0
    except ValueError:
        return "unknown", None
    if lat > 90.0 or lon > 180.0:
        return "unknown", None
    return "pos", (-lat if ns == "S" else lat, -lon if ew == "W" else lon)


def nmea_position(body):
    """(lat, lon) of a GGA, RMC, GLL or GNS sentence, or None."""
    kind, pos = nmea_fields(body)
    return pos if kind == "pos" else None


class LiveState:
    def __init__(self, named_zones=None, radius_m=150.0, auto_zones=True):
        self.named = named_zones if named_zones is not None else privacy.load_named_zones()
        self.radius_m = radius_m
        self.auto_zones = auto_zones
        self.reset(None, None)
        self.sats_signal = None
        self.gsv = {}
        self.drops = 0
        self.last_ep = None

    def reset(self, session_no, mode):
        self.session_no = session_no
        self.mode = mode or "UNKNOWN"
        self.rows = []
        self.events = []
        self.mono0 = None
        self.activity = {"count": None, "span": 0.0, "samples": 0, "fix": None, "reason": None}
        self.record_first_ms = None
        # the named zones (home, school) hold from the start of a session, before any fix
        self.zones = [privacy._offset_zone(z["lat"], z["lon"], z["radius_m"], "live:%s:%d" % (z["name"], k), "named",
                                           z["name"]) for k, z in enumerate(self.named)]
        self.named_used = set()          # named zones a recorded fix of this session fell in: only these are drawn
        self.start_zone = None
        self.end_zone = None
        self.announced = {}
        self.recording = session_no is not None
        self.ended = None

    # ------------------------------------------------------------------ privacy
    def _zones(self):
        return [z for z in (self.start_zone, self.end_zone) if z] + self.zones

    def hidden(self, lat, lon):
        return privacy.inside(self._zones(), lat, lon)

    def _zone_list(self):
        """The zones the page draws: start and end, and a named zone only once the recorded route has entered it
        (privacy.page_zones). Hiding uses every zone, drawn or not."""
        zs = [z for z in (self.start_zone, self.end_zone) if z] + [z for k, z in enumerate(self.zones)
                                                                   if k in self.named_used]
        return [{"la": round(z["lat"], 7), "lo": round(z["lon"], 7), "r": z["radius_m"], "kind": z["kind"]} for z in zs]

    def _start_pending(self):
        """Recording, but the first fix (the centre of the start zone) has not arrived yet: the device sends an
        epoch's NMEA sentences before its 'ep' line, so until then every position is hidden."""
        return self.recording and self.auto_zones and self.start_zone is None

    def _ep_hidden(self, obj):
        """An epoch's position is hidden while the device is not recording, and inside a zone."""
        if obj.get("la") is None:
            return False
        return obj.get("rs") != "RECORDING" or self.hidden(obj["la"], obj["lo"])

    def mask_json_line(self, text, obj):
        """The raw '#J' line for the page: coordinates masked when hidden, and the record hex masked like the replay
        console does (bytes 20 to 27 and the CRC). Call it after on_json(), so a zone that line opens applies."""
        if obj.get("t") == "ep" and self._ep_hidden(obj):
            o = dict(obj, la="x" * 10, lo="x" * 11)
            return "#J " + json.dumps(o, separators=(",", ":"))
        if obj.get("t") == "rec" and obj.get("ty") in (2, 4) and self._rec_hidden(obj.get("hx", "")):
            o = dict(obj, hx=privacy.mask_hex(obj["hx"], "FIX" if obj["ty"] == 2 else "EVENT"), crc="x" * 8)
            return "#J " + json.dumps(o, separators=(",", ":"))
        return text

    def _rec_hidden(self, hx):
        try:
            b = bytes.fromhex(hx)
            lat = int.from_bytes(b[20:24], "little", signed=True) / 1e7
            lon = int.from_bytes(b[24:28], "little", signed=True) / 1e7
        except ValueError:
            return True
        if lat == 0 and lon == 0:
            return False
        return self._start_pending() or self.hidden(lat, lon)

    def mask_nmea(self, line, recording=None):
        """'#N $GNGGA,...': a sentence with a position keeps its type (and time) and loses the rest when the position
        is hidden: while not recording, before the first fix of a recording, or inside a zone. A sentence whose
        position cannot be read is masked always (nmea_fields). recording: the state when the line arrived."""
        body = line[3:]
        kind, pos = nmea_fields(body)
        if kind in ("safe", "empty"):
            return line
        rec = self.recording if recording is None else recording
        if kind == "pos" and rec and not self._start_pending() and not self.hidden(*pos):
            return line
        m = SENTENCE.match(body)
        if not m:
            return "#N " + "x" * 6
        keep = m.group(0)
        if m.group(2) in NMEA_TIME:
            keep += body[len(keep):].split(",")[0] + ","          # the time
        return "#N " + keep + "x" * 6

    # ------------------------------------------------------------------ input
    def on_json(self, obj):
        """Returns a list of events for the page."""
        t = obj.get("t")
        out = []
        if t == "rec":
            try:
                r = ux.decode(bytes.fromhex(obj.get("hx", "")))
            except (ValueError, TypeError):
                r = None
            ss = r.get("session_no", self.session_no) if r is not None else None
            if r is not None and (ss is None or isinstance(ss, int) and ss > 0) and obj.get("seq") == r["seq"] and obj.get("ty") == r["type"]:
                if ss is not None and ss != self.session_no:
                    self.reset(ss, None)
                if self.activity["count"] is not None and r["seq"] < self.activity["count"]:
                    return out
                if self.record_first_ms is None:
                    self.record_first_ms = r["mono"]
                self.activity["count"] = max(self.activity["count"] or 0, r["seq"] + 1)
                self.activity["span"] = ((r["mono"] - self.record_first_ms) & 0xFFFFFFFF) / 1000.0
                if r["type"] in (2, 3):
                    self.activity["samples"] += 1
                    self.activity["fix"] = r["type"] == 2
                    self.activity["reason"] = r.get("nofix_reason")
                out.append({"ev": "activity", **self.activity})
        elif t == "ss":
            activity, first_ms = self.activity, self.record_first_ms
            same = obj.get("ss") == self.session_no
            self.reset(obj.get("ss"), obj.get("md"))
            if same:
                self.activity, self.record_first_ms = activity, first_ms
            out.append({"ev": "session", "ss": obj.get("ss"), "md": obj.get("md"), "sr": obj.get("sr")})
        elif t == "se":
            self.recording = False
            self.ended = {"er": obj.get("er"), "n": obj.get("n")}
            out.append({"ev": "session_end", "ss": obj.get("ss"), "er": obj.get("er"), "n": obj.get("n")})
            fixes = [r for r in self.rows if r["fix"]]
            if fixes and self.auto_zones and self.end_zone is None:
                last = fixes[-1]
                self.end_zone = privacy._offset_zone(last["lat"], last["lon"], self.radius_m,
                                                     "live-end:%s:%s" % (self.session_no, last["mono"]), "end")
            out += self._detect(final=True)
            summ = self.summary()
            out.append({"ev": "rezone", "zones": summ["zones"], "rows": summ["rows"], "stops": summ["stops"]})
        elif t == "ep":
            self.last_ep = obj
            out += self._epoch(obj)
        elif t == "ev":
            self.events.append({"event_no": obj.get("n"), "located": bool(obj.get("loc")), "t_press": self._now_t()})
            out.append({"ev": "event", "n": obj.get("n"), "loc": obj.get("loc"), "t": self._now_t()})
        elif t == "st":
            out.append({"ev": "status", "vb": obj.get("vb"), "ff": obj.get("ff")})
        elif t == "drop":
            self.drops += int(obj.get("n") or 0)
            out.append({"ev": "drop", "n": obj.get("n"), "total": self.drops})
        return out

    def _now_t(self):
        return self.rows[-1]["t"] if self.rows else 0.0

    def _epoch(self, ep):
        out = []
        rs = ep.get("rs")
        if rs == "RECORDING" and ep.get("ss") is not None and ep.get("ss") != self.session_no:
            self.reset(ep.get("ss"), ep.get("md"))      # connected mid-session: start from here
        if rs != "RECORDING" or self.session_no is None:
            out.append({"ev": "ep", "row": self._page_row(ep, None), "recording": False})
            return out
        if self.mono0 is None:
            self.mono0 = ep["ms"]
        fix = bool(ep.get("fix")) and ep.get("la") is not None
        row = {"idx": len(self.rows), "seq": None, "mono": ep["ms"], "fix": fix,
               "lat": ep.get("la") if fix else None, "lon": ep.get("lo") if fix else None,
               "speed": ep.get("sp"), "course": ep.get("co"), "alt": ep.get("al"), "hdop": ep.get("hd"),
               "sats": ep.get("su"), "fix_type": ep.get("ft"), "nofix_reason": None if fix else ep.get("nr"),
               "filler": False, "utc_ms": _utc_ms(ep.get("utc")), "t": (ep["ms"] - self.mono0) / 1000.0}
        drawn = len(self._zone_list())
        if fix and self.start_zone is None and self.auto_zones:
            self.start_zone = privacy._offset_zone(row["lat"], row["lon"], self.radius_m,
                                                   "live:%s:%s" % (self.session_no, ep.get("ms")), "start")
        if fix:
            self.named_used.update(k for k, z in enumerate(self.zones) if privacy.inside([z], row["lat"], row["lon"]))
        if len(self._zone_list()) != drawn:
            out.append({"ev": "zones", "zones": self._zone_list()})
        self.rows.append(row)
        out.append({"ev": "ep", "row": self._page_row(ep, row), "recording": True})
        out += self._detect()
        return out

    def clock_label(self, t):
        """Local clock time (HH:MM:SS) of session time t, from the receiver's UTC on the nearest row, in the time zone
        of the place (as REPLAY labels it); None when no row has a time. Labels only: durations use mono_ms."""
        best = None
        for r in self.rows:
            if r.get("utc_ms") is not None and (best is None or abs(r["t"] - t) < abs(best["t"] - t)):
                best = r
        if best is None:
            return None
        first = next((r for r in self.rows if r["fix"]), None)
        tz = (geo.tz_for(first["lat"], first["lon"]) if first else None) or config.DEFAULT_TZ
        ms = best["utc_ms"] + (t - best["t"]) * 1000.0
        return dt.datetime.fromtimestamp(ms / 1000.0, ZoneInfo(tz)).strftime("%H:%M:%S")

    def _page_row(self, ep, row):
        hid = self._ep_hidden(ep)
        return {"t": row["t"] if row else None, "ms": ep.get("ms"), "f": 1 if ep.get("fix") else 0,
                "la": None if hid else ep.get("la"), "lo": None if hid else ep.get("lo"), "h": 1 if hid else 0,
                "v": ep.get("sp"), "n": ep.get("su"), "hd": ep.get("hd"), "ft": ep.get("ft"), "nr": ep.get("nr"),
                "rs": ep.get("rs"), "ss": ep.get("ss"), "md": ep.get("md")}

    def _detect(self, final=False):
        """Same detector as REPLAY over the rows up to 2 s ago; announce new stops and closed stops."""
        if len(self.rows) < 10:
            return []
        until = None if final else self.rows[-1]["t"] - DETECT_LAG_S
        res = stops.analyse(self.rows, self.mode, events=self.events, sensitivity=False, until_t=until,
                            open_end=not final)
        out = []
        found = {s["n"] for s in res["stops"]}
        for n in [k for k in self.announced if k not in found]:
            del self.announced[n]                       # withdrawn by the final run (it was the lead-out)
            out.append({"ev": "stop_removed", "n": n})
        for s in res["stops"]:
            n = s["n"]
            hid = self.hidden(s["lat"], s["lon"])
            info = {"n": n, "t0": s["t0"], "t1": s["t1"], "dur": s["dur"], "la": None if hid else round(s["lat"], 7),
                    "lo": None if hid else round(s["lon"], 7), "h": 1 if hid else 0}
            prev = self.announced.get(n)
            open_now = until is not None and s["t1"] >= until - 1.0
            if prev is None:
                out.append(dict(info, ev="stop_detected", v=res["params"]["v_stop"], tmin=res["params"]["t_min"]))
            if not open_now and (prev is None or prev.get("open")):
                out.append(dict(info, ev="stop_ended"))
            self.announced[n] = dict(info, open=open_now)
        m = res["metrics"]
        if m:
            out.append({"ev": "metrics", "metrics": m, "span": list(res["span"]) if res["span"] else None})
        return out

    def on_nmea(self, line):
        """Count satellites with an SNR value from GSV sentences (the firmware does not parse GSV)."""
        body = line[3:].strip()
        m = GSV.match(body)
        if not m:
            return None
        talker = m.group(1)
        fields = body.split("*")[0].split(",")
        try:
            total_msgs, msg_no = int(fields[1]), int(fields[2])
        except (IndexError, ValueError):
            return None
        sats = self.gsv.setdefault(talker, {})
        if msg_no == 1:
            sats.clear()
        for k in range(4, len(fields) - 3, 4):
            prn, snr = fields[k], fields[k + 3] if k + 3 < len(fields) else ""
            if prn:
                sats[prn] = bool(snr.strip())
        if msg_no == total_msgs:
            self.sats_signal = sum(sum(1 for v in s.values() if v) for s in self.gsv.values())
            return {"ev": "sats", "n": self.sats_signal}
        return None

    def summary(self):
        return {"session": self.session_no, "mode": self.mode, "recording": self.recording, "ended": self.ended,
                "activity": dict(self.activity),
                "rows": [self._page_row({"ms": r["mono"], "fix": 1 if r["fix"] else 0, "la": r["lat"], "lo": r["lon"],
                                         "sp": r["speed"], "su": r["sats"], "hd": r["hdop"], "ft": r["fix_type"],
                                         "nr": r["nofix_reason"], "rs": "RECORDING", "ss": self.session_no,
                                         "md": self.mode}, r) for r in self.rows[-3600:]],
                "stops": [dict(v, ev="stop_detected" if v.get("open") else "stop_ended") for v in self.announced.values()],
                "sats_signal": self.sats_signal, "drops": self.drops,
                "zones": self._zone_list()}
