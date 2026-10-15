"""Load a recorded session (.wfg, the CSV written by usb_export.py, or a development GPX) into one structure.

Records are decoded only by the vendored, unmodified usb_export.py. Stored positions are never smoothed, snapped,
shifted or interpolated here or anywhere else in the app.
"""
import csv
import datetime as dt
import hashlib
import io
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from .vendor import usb_export as ux

TYPE = {ux.T_START: "START", ux.T_FIX: "FIX", ux.T_NOFIX: "NOFIX", ux.T_EVENT: "EVENT", ux.T_CLOCK: "CLOCK",
        ux.T_END: "END", ux.T_STATUS: "STATUS"}
NOFIX_CODE = {v: k for k, v in ux.NOFIX_NAME.items()}
FIX_TYPE = {1: "NONE", 2: "2D", 3: "3D"}


def utc_est_series(data):
    """utc_est (epoch ms) per whole record, built from mono_ms and the CLOCK records exactly as usb_export.to_csv():
    the first CLOCK offset applies from the start of the file, later CLOCK records replace it, EVENT rows use the
    press time, and a SESSION_END written by boot recovery has none. Labels only; never used for durations."""
    meta = ux.Meta(data)
    off = meta.offset
    out = []
    for _, r in ux.records(data):
        if r is None:
            out.append(None)
            continue
        if r["type"] == ux.T_CLOCK:
            off = r["offset"]
        recovered_end = r["type"] == ux.T_END and r["reason"] == 4
        mono = r["press"] if r["type"] == ux.T_EVENT else r["mono"]
        out.append(None if (off is None or recovered_end) else off + mono)
    return out


class Session:
    """A decoded session. `rows` are the FIX/NOFIX observation rows in file order."""

    def __init__(self):
        self.source = "wfg"
        self.path = None
        self.name = ""
        self.sha256 = ""
        self.size = 0
        self.sid = ""
        self.mode = "UNKNOWN"
        self.device_id = None
        self.session_no = None
        self.start_reason = "OWNER_BUTTON"
        self.resumed_from = ""
        self.fw = None
        self.fmt = None
        self.integrity = None
        self.records = []
        self.rows = []
        self.events = []
        self.status = []
        self.clocks = []
        self.mono0 = 0
        self.end_reason = None
        self.sim = False
        self.sim_meta = None

    # ------------------------------------------------------------------ helpers
    def t(self, mono):
        return None if mono is None else (mono - self.mono0) / 1000.0

    @property
    def device_label(self):
        return "WFG-%08X" % self.device_id if self.device_id is not None else "-"

    def first_utc(self):
        for r in self.records:
            if r.get("utc_ms") is not None:
                return r["utc_ms"] - (r["mono"] - self.mono0 if r.get("mono") is not None else 0)
        return None


def _row_from(rec, d, typ):
    v = d["valid"]
    fix = typ == "FIX"
    row = {
        "idx": rec["idx"], "seq": d["seq"], "mono": d["mono"], "fix": fix,
        "lat": d["lat"] / 1e7 if (v & ux.V_POS) else None,
        "lon": d["lon"] / 1e7 if (v & ux.V_POS) else None,
        "speed": d["speed"] / 100.0 if (v & ux.V_SPEED) else None,
        "course": d["course"] / 100.0 if (v & ux.V_COURSE) else None,
        "alt": d["alt"] / 100.0 if (v & ux.V_ALT) else None,
        "hdop": d["hdop"] / 100.0 if (v & ux.V_HDOP) else None,
        "sats": d["sats"] if (v & ux.V_SATS) else None,
        "fix_type": FIX_TYPE.get(d["fix_type"]) if (v & ux.V_FIXTYPE) else None,
        "nofix_reason": None if fix else ux.NOFIX_NAME.get(d["nofix_reason"], "UNKNOWN"),
        "filler": d["flags0"] == 0xFF,
        "utc_ms": rec["utc_ms"],
    }
    if not fix:
        row["lat"] = row["lon"] = None   # a NOFIX row has no position by definition
    return row


def load_wfg_bytes(data, name="S000000.wfg"):
    s = Session()
    s.source = "wfg"
    s.name = name
    s.size = len(data)
    s.sha256 = hashlib.sha256(data).hexdigest()
    s.integrity = ux.integrity(data)
    meta = ux.Meta(data, name)
    s.sid, s.mode = meta.sid, meta.mode
    s.start_reason, s.resumed_from = meta.start_reason, meta.resumed_from
    if meta.start:
        s.device_id = meta.start["device_id"]
        s.session_no = meta.start["session_no"]
        s.fw = meta.start["fw"]
        s.fmt = meta.start["fmt"]
    utc = utc_est_series(data)
    for k, d in ux.records(data):
        raw = data[k * ux.REC:(k + 1) * ux.REC]
        rec = {"idx": k, "ok": d is not None, "hex": raw.hex(), "utc_ms": utc[k]}
        if d is None:
            rec.update({"type": "CORRUPT", "seq": None, "mono": None})
            s.records.append(rec)
            continue
        typ = TYPE.get(d["type"], "UNKNOWN")
        rec.update({"type": typ, "seq": d["seq"], "mono": d["mono"]})
        if typ in ("FIX", "NOFIX"):
            row = _row_from(rec, d, typ)
            rec["row"] = len(s.rows)
            s.rows.append(row)
        elif typ == "EVENT":
            ev = {"idx": k, "seq": d["seq"], "event_no": d["event_no"], "press_mono": d["press"], "mono": d["mono"],
                  "located": bool(d["located"]), "lat": d["lat"] / 1e7 if d["located"] else None,
                  "lon": d["lon"] / 1e7 if d["located"] else None, "dur_ms": d["dur"], "utc_ms": utc[k]}
            rec["event"] = len(s.events)
            s.events.append(ev)
        elif typ == "STATUS":
            st = {"idx": k, "mono": d["mono"], "flags": d["st_flags"],
                  "vbat_mv": d["vbat_mv"] if (d["st_flags"] & ux.ST_BATT_VALID and d["vbat_mv"] != 0xFFFF) else None,
                  "vbat_pin_mv": d["vbat_pin_mv"] if d["vbat_pin_mv"] != 0xFFFF else None,
                  "factor": d["vbat_factor"] / 1000.0 if d["vbat_factor"] else None,
                  "fs_free": d["fs_free"], "fs_total": d["fs_total"], "nmea_ok": d["nmea_ok"],
                  "nmea_bad": d["nmea_bad"]}
            rec["status"] = len(s.status)
            s.status.append(st)
        elif typ == "CLOCK":
            rec["clock"] = len(s.clocks)
            s.clocks.append({"idx": k, "mono": d["mono"], "kind": "FIRST_UTC" if d["kind"] == 1 else "JUMP",
                             "offset": d["offset"], "delta": d["delta"]})
        elif typ == "END":
            s.end_reason = ux.END_NAME.get(d["reason"], "UNKNOWN")
            if d["reason"] == 4:
                rec["mono"] = None   # written by boot recovery: the clock restarted
        s.records.append(rec)
    s.mono0 = _mono0(s)
    _finish(s)
    return s


def _mono0(s):
    for r in s.records:
        if r["type"] == "START" and r["mono"] is not None:
            return r["mono"]
    for r in s.records:
        if r.get("mono") is not None:
            return r["mono"]
    return 0


def _finish(s):
    for r in s.records:
        r["t"] = s.t(r.get("mono"))
    for row in s.rows:
        row["t"] = s.t(row["mono"])
    for ev in s.events:
        ev["t_press"] = s.t(ev["press_mono"])
        ev["t"] = s.t(ev["mono"])
    for st in s.status:
        st["t"] = s.t(st["mono"])


def load_wfg(path):
    p = Path(path)
    s = load_wfg_bytes(p.read_bytes(), p.name)
    s.path = p
    _attach_sim(s, p)
    return s


def _attach_sim(s, p):
    side = p.with_name(p.name + ".sim.json")
    if side.exists():
        s.sim = True
        s.sim_meta = json.loads(side.read_text(encoding="utf-8"))
    if "sim" in p.parts:
        s.sim = True


def _iso_ms(text):
    if not text:
        return None
    t = dt.datetime.strptime(text.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S.%f%z")
    return int(t.timestamp() * 1000)


def load_csv(path):
    """The CSV written by usb_export.py (same columns as the device's Wi-Fi page). It has no record bytes."""
    p = Path(path)
    raw = p.read_bytes()
    s = Session()
    s.source = "csv"
    s.path, s.name, s.size = p, p.name, len(raw)
    s.sha256 = hashlib.sha256(raw).hexdigest()
    rd = csv.DictReader(io.StringIO(raw.decode("utf-8")))
    counts = {"records": 0, "crc_errors": 0, "seq_errors": 0, "fix": 0, "nofix": 0, "events": 0}
    for k, c in enumerate(rd):
        counts["records"] += 1
        typ = c["record_type"]
        if typ != "CORRUPT" and c["seq"] and int(c["seq"]) != k:
            counts["seq_errors"] += 1
        if not s.sid and c["session_id"]:
            s.sid, s.mode = c["session_id"], c["movement_mode"] or "UNKNOWN"
            s.start_reason = c.get("session_start_reason") or "OWNER_BUTTON"
            s.resumed_from = c.get("resumed_from_session_id") or ""
            try:
                s.device_id = int(s.sid.split("-")[1], 16)
                s.session_no = int(s.sid.split("-")[2])
            except (IndexError, ValueError):
                pass
        mono = int(c["mono_ms"]) if c["mono_ms"] else None
        rec = {"idx": k, "ok": typ != "CORRUPT", "hex": None, "type": typ,
               "seq": int(c["seq"]) if c["seq"] else None, "mono": mono, "utc_ms": _iso_ms(c["utc_est"])}
        f = lambda key: float(c[key]) if c.get(key) else None   # noqa: E731
        if typ == "CORRUPT":
            counts["crc_errors"] += 1
        elif typ in ("FIX", "NOFIX"):
            fix = typ == "FIX"
            counts["fix" if fix else "nofix"] += 1
            row = {"idx": k, "seq": rec["seq"], "mono": mono, "fix": fix, "lat": f("lat") if fix else None,
                   "lon": f("lon") if fix else None, "speed": f("speed_mps"), "course": f("course_deg"),
                   "alt": f("alt_m"), "hdop": f("hdop"), "sats": int(c["sats"]) if c["sats"] else None,
                   "fix_type": c["fix_type"] or None, "nofix_reason": c["nofix_reason"] or None,
                   "filler": c["epoch_age_ms"] == "", "utc_ms": rec["utc_ms"]}
            rec["row"] = len(s.rows)
            s.rows.append(row)
        elif typ == "EVENT":
            counts["events"] += 1
            ev = {"idx": k, "seq": rec["seq"], "event_no": int(c["event_no"]), "mono": mono,
                  "press_mono": int(c["event_press_mono_ms"]), "located": c["event_located"] == "1",
                  "lat": f("lat"), "lon": f("lon"), "dur_ms": None, "utc_ms": rec["utc_ms"]}
            rec["event"] = len(s.events)
            s.events.append(ev)
        elif typ == "STATUS":
            st = {"idx": k, "mono": mono, "flags": 1 if c["status_vbat_mv"] else 0,
                  "vbat_mv": int(c["status_vbat_mv"]) if c["status_vbat_mv"] else None,
                  "vbat_pin_mv": int(c["status_vbat_pin_mv"]) if c["status_vbat_pin_mv"] else None,
                  "factor": f("status_vbat_factor"), "fs_free": int(c["status_fs_free_bytes"] or 0),
                  "fs_total": int(c["status_fs_total_bytes"] or 0), "nmea_ok": int(c["status_nmea_ok"] or 0),
                  "nmea_bad": int(c["status_nmea_checksum_errors"] or 0)}
            rec["status"] = len(s.status)
            s.status.append(st)
        elif typ == "CLOCK":
            rec["clock"] = len(s.clocks)
            s.clocks.append({"idx": k, "mono": mono, "kind": c["clock_kind"] or "FIRST_UTC",
                             "offset": int(c["clock_offset_ms"]) if c["clock_offset_ms"] else None,
                             "delta": int(c["clock_delta_ms"]) if c["clock_delta_ms"] else 0})
        elif typ == "SESSION_END":
            rec["type"] = "END"
            s.end_reason = c["end_reason"] or None
        elif typ == "SESSION_START":
            rec["type"] = "START"
        s.records.append(rec)
    counts["ok"] = counts["crc_errors"] == 0 and counts["seq_errors"] == 0
    counts["status"] = "OK" if counts["ok"] else "CORRUPT"
    s.integrity = counts
    s.mono0 = _mono0(s)
    _finish(s)
    _attach_sim(s, p)
    return s


def load_gpx(path):
    """Development only: a phone or other GPX file. Never presented as device data."""
    p = Path(path)
    raw = p.read_bytes()
    s = Session()
    s.source = "gpx"
    s.path, s.name, s.size = p, p.name, len(raw)
    s.sha256 = hashlib.sha256(raw).hexdigest()
    s.sid, s.mode = "GPX-" + p.stem, "UNKNOWN"
    root = ET.fromstring(raw)
    ns = {"g": root.tag.split("}")[0].strip("{")} if root.tag.startswith("{") else {}
    pts = root.findall(".//g:trkpt", ns) if ns else root.findall(".//trkpt")
    t0 = None
    for k, pt in enumerate(pts):
        tm = pt.find("g:time", ns) if ns else pt.find("time")
        if tm is None or not tm.text:
            continue
        when = dt.datetime.fromisoformat(tm.text.replace("Z", "+00:00"))
        ms = int(when.timestamp() * 1000)
        t0 = ms if t0 is None else t0
        mono = ms - t0
        rec = {"idx": k, "ok": True, "hex": None, "type": "FIX", "seq": k, "mono": mono, "utc_ms": ms}
        row = {"idx": k, "seq": k, "mono": mono, "fix": True, "lat": float(pt.get("lat")), "lon": float(pt.get("lon")),
               "speed": None, "course": None, "alt": None, "hdop": None, "sats": None, "fix_type": None,
               "nofix_reason": None, "filler": False, "utc_ms": ms}
        rec["row"] = len(s.rows)
        s.rows.append(row)
        s.records.append(rec)
    s.integrity = {"records": len(s.records), "crc_errors": 0, "ok": True, "status": "GPX"}
    s.mono0 = 0
    _finish(s)
    return s


def load_any(path):
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".wfg":
        return load_wfg(p)
    if ext == ".csv":
        return load_csv(p)
    if ext == ".gpx":
        return load_gpx(p)
    raise ValueError("unsupported session file: " + p.name)
