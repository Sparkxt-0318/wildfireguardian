#!/usr/bin/env python3
"""WildfireGuardian route logger - USB serial export (mandatory fallback; works with no phone, no Wi-Fi).

Requires Python 3.8+ and pyserial (`python3 -m pip install pyserial==3.5`).

  python3 usb_export.py ports                          list serial ports (macOS: /dev/cu.usbmodem*)
  python3 usb_export.py list   --port /dev/cu.usbmodem1101
  python3 usb_export.py dump   --port ... [--session S000003.wfg | --all] [--out exports/]
  python3 usb_export.py dump   --port ... --all --confirm     also mark verified sessions as exported on device
  python3 usb_export.py delete --port ... --session S000003.wfg   (then hold the device button 2.5 s)
  python3 usb_export.py convert FILE.wfg [--out dir]       offline: .wfg -> .csv/.gpx/.geojson + integrity report
  python3 usb_export.py verify  FILE.wfg                    offline integrity check

Every dumped file is checked three ways before it is written: per-record CRC-32, record sequence numbers, and a
SHA-256 of the whole file compared with the SHA-256 the device computed. Only then (and only with --confirm) is the
device told the export is confirmed, which is the precondition for any deletion. The CSV/GPX/GeoJSON written here are
byte-identical to what the device's Wi-Fi page serves (checked by tests/test_usb_export.py).
"""
import argparse
import binascii
import datetime as _dt
import hashlib
import json
import os
import struct
import sys
import time

REC = 48
MAGIC = b"WF"
T_START, T_FIX, T_NOFIX, T_EVENT, T_CLOCK, T_END, T_STATUS = 1, 2, 3, 4, 5, 6, 7
TYPE_NAME = {1: "SESSION_START", 2: "FIX", 3: "NOFIX", 4: "EVENT", 5: "CLOCK", 6: "SESSION_END", 7: "STATUS"}
START_REASON = {0: "OWNER_BUTTON", 1: "AUTO_RESUMED_AFTER_RESET"}
ST_BATT_VALID = 1
MODE_NAME = {1: "WALK", 2: "VEHICLE"}
END_NAME = {1: "USER_STOP", 2: "STORAGE_FULL", 3: "LOW_BATTERY", 4: "RECOVERED_ON_BOOT", 5: "FS_ERROR"}
NOFIX_NAME = {1: "RECEIVER_NO_FIX", 2: "NO_NMEA_DATA", 3: "CHECKSUM_ERRORS_ONLY"}
V_TIME, V_DATE, V_POS, V_ALT, V_SPEED, V_COURSE, V_HDOP, V_SATS = 1, 2, 4, 8, 16, 32, 64, 128
V_RMC, V_RAW, V_FIXTYPE, V_CKSUM = 256, 512, 1024, 2048
U32_NONE = 0xFFFFFFFF

CSV_HEADER = (
    "session_id,movement_mode,mode_source,seq,record_type,mono_ms,gnss_utc,utc_est,utc_est_basis,"
    "fix_valid,nofix_reason,gga_quality,fix_type,sats,hdop,lat,lon,alt_m,speed_mps,course_deg,"
    "epoch_age_ms,nmea_checksum_errors_seen,raw_nmea_available,event_no,event_located,event_ref_fix_seq,"
    "event_ref_fix_age_ms,event_press_mono_ms,clock_kind,clock_offset_ms,clock_delta_ms,end_reason,"
    "end_torn_bytes_removed,status_vbat_mv,status_vbat_pin_mv,status_vbat_factor,status_fs_free_bytes,"
    "status_fs_total_bytes,status_nmea_ok,status_nmea_checksum_errors,session_start_reason,resumed_from_session_id,"
    "owner_annotation\n"
)


# ----------------------------------------------------------------------------- record decoding
def decode(b):
    """Return a dict for a valid 48-byte record, or None if magic/CRC/type is wrong."""
    if len(b) != REC or b[0:2] != MAGIC:
        return None
    if struct.unpack_from("<I", b, 44)[0] != (binascii.crc32(b[:44]) & 0xFFFFFFFF):
        return None
    t, flags0, seq, mono = struct.unpack_from("<BBII", b, 2)
    r = {"type": t, "flags0": flags0, "seq": seq, "mono": mono}
    if t == T_START:
        (r["device_id"], r["session_no"], r["mode"], r["board_rev"], r["fw"], r["interval"], r["fmt"], r["recsize"],
         r["boot"], a, bb, r["locate_max_age"]) = struct.unpack_from("<IIBBHHBBIIII", b, 12)
        if r["fmt"] <= 1:  # format v1: UTC at start; no resume attribution
            r["utc_date"], r["utc_ms"], r["start_reason"], r["resumed_from"], r["reset_reason"] = a, bb, 0, 0, 0
        else:              # format v2
            r["resumed_from"], r["reset_reason"], r["start_reason"] = a, bb & 0xFF, flags0
    elif t in (T_FIX, T_NOFIX):
        (r["utc_date"], r["utc_ms"], r["lat"], r["lon"], r["alt"], r["speed"], r["course"], r["hdop"], r["sats"],
         r["gga_q"], r["fix_type"], r["nofix_reason"], r["valid"]) = struct.unpack_from("<IIiiiHHHBBBBH", b, 12)
    elif t == T_EVENT:
        (r["event_no"], r["ref_seq"], r["lat"], r["lon"], r["ref_age"], r["press"], r["dur"], r["located"],
         r["source"]) = struct.unpack_from("<IIiiIIHBB", b, 12)
    elif t == T_CLOCK:
        r["utc_date"], r["utc_ms"], r["offset"], r["delta"], r["kind"] = struct.unpack_from("<IIqqB", b, 12)
    elif t == T_STATUS:
        (r["vbat_mv"], r["vbat_pin_mv"], r["vbat_factor"], r["st_flags"], r["fs_free"], r["fs_total"], r["nmea_ok"],
         r["nmea_bad"], r["free_heap"]) = struct.unpack_from("<HHHBxIIIII", b, 12)
    elif t == T_END:
        r["reason"] = b[12]
        (r["n_before"], r["n_fix"], r["n_nofix"], r["n_events"], r["crc_before"], r["torn"],
         r["n_clock"]) = struct.unpack_from("<IIIIIII", b, 16)
    else:
        return None
    return r


def records(data):
    """Yield (index, dict-or-None) for each whole record."""
    for k in range(len(data) // REC):
        yield k, decode(data[k * REC:(k + 1) * REC])


def integrity(data):
    rep = {"records": len(data) // REC, "trailing_bytes": len(data) % REC, "crc_errors": 0, "seq_errors": 0,
           "has_start": False, "has_end": False, "end_reason": None, "end_counts_match": False,
           "end_crc_match": False, "fix": 0, "nofix": 0, "events": 0, "clock": 0, "status_records": 0}
    crc = 0
    n = rep["records"]
    for k, r in records(data):
        crc_before = crc
        crc = binascii.crc32(data[k * REC:(k + 1) * REC], crc) & 0xFFFFFFFF
        if r is None:
            rep["crc_errors"] += 1
            continue
        if r["seq"] != k:
            rep["seq_errors"] += 1
        t = r["type"]
        if t == T_START and k == 0:
            rep["has_start"] = True
        elif t == T_FIX:
            rep["fix"] += 1
        elif t == T_NOFIX:
            rep["nofix"] += 1
        elif t == T_EVENT:
            rep["events"] += 1
        elif t == T_CLOCK:
            rep["clock"] += 1
        elif t == T_STATUS:
            rep["status_records"] += 1
        elif t == T_END:
            if k == n - 1:
                rep["has_end"] = True
                rep["end_reason"] = END_NAME.get(r["reason"], "UNKNOWN")
                rep["end_counts_match"] = (r["n_before"] == k and r["n_fix"] == rep["fix"] and
                                           r["n_nofix"] == rep["nofix"] and r["n_events"] == rep["events"] and
                                           r["n_clock"] == rep["clock"])
                rep["end_crc_match"] = r["crc_before"] == crc_before
            else:
                rep["seq_errors"] += 1
    ok = (rep["crc_errors"] == 0 and rep["seq_errors"] == 0 and rep["trailing_bytes"] == 0 and rep["has_start"]
          and rep["has_end"] and rep["end_counts_match"] and rep["end_crc_match"])
    if ok:
        rep["status"] = "RECOVERED" if rep["end_reason"] == "RECOVERED_ON_BOOT" else "OK"
    elif rep["crc_errors"] == 0 and rep["seq_errors"] == 0 and rep["has_start"] and not rep["has_end"]:
        rep["status"] = "TORN_TAIL" if rep["trailing_bytes"] else "OPEN"
    else:
        rep["status"] = "CORRUPT"
    rep["ok"] = ok
    return rep


# ----------------------------------------------------------------------------- formatting (mirrors wfg_export.cpp)
def fmt_e7(v):
    s = "-" if v < 0 else ""
    v = abs(v)
    return "%s%d.%07d" % (s, v // 10000000, v % 10000000)


def fmt_centi(v):
    s = "-" if v < 0 else ""
    v = abs(v)
    return "%s%d.%02d" % (s, v // 100, v % 100)


def fmt_iso(ymd, ms):
    return "%04d-%02d-%02dT%02d:%02d:%02d.%03dZ" % (ymd // 10000, ymd // 100 % 100, ymd % 100, ms // 3600000,
                                                    ms // 60000 % 60, ms // 1000 % 60, ms % 1000)


_EPOCH_ORD = _dt.date(1970, 1, 1).toordinal()


def fmt_iso_epoch(epoch_ms):
    days, ms = divmod(epoch_ms, 86400000)
    d = _dt.date.fromordinal(_EPOCH_ORD + days)
    return fmt_iso(d.year * 10000 + d.month * 100 + d.day, ms)


FIX_TYPE_NAME = {1: "NONE", 2: "2D", 3: "3D"}


class Meta:
    def __init__(self, data, fname="S000000.wfg"):
        self.start = None
        self.offset = None
        for _, r in records(data):
            if r is None:
                continue
            if r["type"] == T_START and self.start is None:
                self.start = r
            if r["type"] == T_CLOCK and self.offset is None:
                self.offset = r["offset"]
        self.start_reason = "OWNER_BUTTON"
        self.resumed_from = ""
        if self.start:
            self.sid = "WFG-%08X-%06u" % (self.start["device_id"], self.start["session_no"])
            self.mode = MODE_NAME.get(self.start["mode"], "UNKNOWN")
            self.start_reason = START_REASON.get(self.start["start_reason"], "OWNER_BUTTON")
            if self.start["resumed_from"]:
                self.resumed_from = "WFG-%08X-%06u" % (self.start["device_id"], self.start["resumed_from"])
        else:
            self.sid = "WFG-UNKNOWN-%s" % os.path.basename(fname)[1:7]
            self.mode = "UNKNOWN"


def to_csv(data, fname="S000000.wfg"):
    m = Meta(data, fname)
    out = [CSV_HEADER]
    off = m.offset
    for _, r in records(data):
        c = [""] * 43
        c[0], c[1], c[2] = m.sid, m.mode, "owner_selected_on_device"
        c[40], c[41] = m.start_reason, m.resumed_from
        if r is None:
            c[4] = "CORRUPT"
            out.append(",".join(c) + "\n")
            continue
        t = r["type"]
        if t == T_CLOCK:
            off = r["offset"]
        c[3] = str(r["seq"])
        c[4] = TYPE_NAME[t]
        recovered_end = t == T_END and r["reason"] == 4
        if not recovered_end:
            c[5] = str(r["mono"])
        est_mono = r["press"] if t == T_EVENT else r["mono"]
        if off is not None and not recovered_end:
            c[7] = fmt_iso_epoch(off + est_mono)
            c[8] = "mono_ms+gnss_clock_offset"
        if t in (T_FIX, T_NOFIX):
            v = r["valid"]
            if v & V_TIME and v & V_DATE:
                c[6] = fmt_iso(r["utc_date"], r["utc_ms"])
            c[9] = "1" if t == T_FIX else "0"
            c[10] = NOFIX_NAME.get(r["nofix_reason"], "")
            if r["gga_q"] != 0xFF:
                c[11] = str(r["gga_q"])
            if v & V_FIXTYPE:
                c[12] = FIX_TYPE_NAME.get(r["fix_type"], "")
            if v & V_SATS:
                c[13] = str(r["sats"])
            if v & V_HDOP:
                c[14] = fmt_centi(r["hdop"])
            if v & V_POS:
                c[15], c[16] = fmt_e7(r["lat"]), fmt_e7(r["lon"])
            if v & V_ALT:
                c[17] = fmt_centi(r["alt"])
            if v & V_SPEED:
                c[18] = fmt_centi(r["speed"])
            if v & V_COURSE:
                c[19] = fmt_centi(r["course"])
            if r["flags0"] != 0xFF:
                c[20] = str(r["flags0"] * 10)
            c[21] = "1" if v & V_CKSUM else "0"
            c[22] = "1" if v & V_RAW else "0"
        elif t == T_EVENT:
            if r["located"]:
                c[15], c[16] = fmt_e7(r["lat"]), fmt_e7(r["lon"])
            c[23] = str(r["event_no"])
            c[24] = "1" if r["located"] else "0"
            if r["ref_seq"] != U32_NONE:
                c[25] = str(r["ref_seq"])
            if r["ref_age"] != U32_NONE:
                c[26] = str(r["ref_age"])
            c[27] = str(r["press"])
        elif t == T_CLOCK:
            c[6] = fmt_iso(r["utc_date"], r["utc_ms"])
            c[28] = "FIRST_UTC" if r["kind"] == 1 else "JUMP"
            c[29], c[30] = str(r["offset"]), str(r["delta"])
        elif t == T_STATUS:
            if r["st_flags"] & ST_BATT_VALID and r["vbat_mv"] != 0xFFFF:
                c[33] = str(r["vbat_mv"])
            if r["vbat_pin_mv"] != 0xFFFF:
                c[34] = str(r["vbat_pin_mv"])
            if r["vbat_factor"]:
                c[35] = "%d.%03d" % (r["vbat_factor"] // 1000, r["vbat_factor"] % 1000)
            c[36], c[37], c[38], c[39] = str(r["fs_free"]), str(r["fs_total"]), str(r["nmea_ok"]), str(r["nmea_bad"])
        elif t == T_END:
            c[31] = END_NAME.get(r["reason"], "UNKNOWN")
            c[32] = str(r["torn"])
        out.append(",".join(c) + "\n")
    return "".join(out)


def to_gpx(data, fname="S000000.wfg"):
    m = Meta(data, fname)
    o = ['<?xml version="1.0" encoding="UTF-8"?>\n<gpx version="1.1" creator="WildfireGuardian route logger" '
         'xmlns="http://www.topografix.com/GPX/1/1" xmlns:wfg="urn:wildfireguardian:route-logger:1">\n',
         "<metadata><name>%s</name><desc>movement_mode=%s (owner_selected_on_device). start_reason=%s%s. "
         "Coordinates as received from GNSS, not map-matched. HDOP is a unitless dilution factor, not metres. Track "
         "segments break at every NOFIX row. STATUS rows (battery, storage) are in the CSV only.</desc></metadata>\n"
         % (m.sid, m.mode, m.start_reason, (" resumed_from=" + m.resumed_from) if m.resumed_from else "")]
    recs = [r for _, r in records(data)]
    off = m.offset
    for r in recs:
        if r is None:
            continue
        if r["type"] == T_CLOCK:
            off = r["offset"]
        if r["type"] == T_EVENT and r["located"]:
            s = '<wpt lat="%s" lon="%s">' % (fmt_e7(r["lat"]), fmt_e7(r["lon"]))
            if off is not None:
                s += "<time>%s</time>" % fmt_iso_epoch(off + r["press"])
            s += ("<name>EVENT %d</name><type>event_marker</type><extensions><wfg:seq>%d</wfg:seq>"
                  "<wfg:ref_fix_seq>%d</wfg:ref_fix_seq><wfg:ref_fix_age_ms>%d</wfg:ref_fix_age_ms>"
                  "<wfg:position_source>last_fix_before_press</wfg:position_source></extensions></wpt>\n"
                  % (r["event_no"], r["seq"], r["ref_seq"], r["ref_age"]))
            o.append(s)
    o.append("<trk><name>%s</name><type>%s</type>\n" % (m.sid, m.mode))
    in_seg = False
    for r in recs:
        if r is None:
            continue
        if r["type"] == T_FIX:
            v = r["valid"]
            if not in_seg:
                o.append("<trkseg>\n")
                in_seg = True
            s = '<trkpt lat="%s" lon="%s">' % (fmt_e7(r["lat"]), fmt_e7(r["lon"]))
            if v & V_ALT:
                s += "<ele>%s</ele>" % fmt_centi(r["alt"])
            if v & V_TIME and v & V_DATE:
                s += "<time>%s</time>" % fmt_iso(r["utc_date"], r["utc_ms"])
            if v & V_FIXTYPE and r["fix_type"] in (2, 3):
                s += "<fix>%s</fix>" % ("2d" if r["fix_type"] == 2 else "3d")
            if v & V_SATS:
                s += "<sat>%d</sat>" % r["sats"]
            if v & V_HDOP:
                s += "<hdop>%s</hdop>" % fmt_centi(r["hdop"])
            s += "<extensions><wfg:seq>%d</wfg:seq><wfg:mono_ms>%d</wfg:mono_ms>" % (r["seq"], r["mono"])
            if v & V_SPEED:
                s += "<wfg:speed_mps>%s</wfg:speed_mps>" % fmt_centi(r["speed"])
            if v & V_COURSE:
                s += "<wfg:course_deg>%s</wfg:course_deg>" % fmt_centi(r["course"])
            s += "</extensions></trkpt>\n"
            o.append(s)
        elif r["type"] == T_NOFIX and in_seg:
            o.append("</trkseg>\n")
            in_seg = False
    if in_seg:
        o.append("</trkseg>\n")
    o.append("</trk>\n")
    ext = False
    off = m.offset
    for r in recs:
        if r is None:
            continue
        if r["type"] == T_CLOCK:
            off = r["offset"]
        if r["type"] == T_EVENT and not r["located"]:
            if not ext:
                o.append("<extensions>\n")
                ext = True
            t = fmt_iso_epoch(off + r["press"]) if off is not None else ""
            o.append('<wfg:unlocated_event no="%d" seq="%d" press_mono_ms="%d" utc_est="%s"/>\n'
                     % (r["event_no"], r["seq"], r["press"], t))
    if ext:
        o.append("</extensions>\n")
    o.append("</gpx>\n")
    return "".join(o)


def to_geojson(data, fname="S000000.wfg"):
    m = Meta(data, fname)
    recs = [r for _, r in records(data)]

    def pos(r):
        if r["valid"] & V_ALT:
            return "[%s,%s,%s]" % (fmt_e7(r["lon"]), fmt_e7(r["lat"]), fmt_centi(r["alt"]))
        return "[%s,%s]" % (fmt_e7(r["lon"]), fmt_e7(r["lat"]))

    rf = '"%s"' % m.resumed_from if m.resumed_from else "null"
    o = ['{"type":"FeatureCollection","wfg":{"session_id":"%s","movement_mode":"%s",'
         '"mode_source":"owner_selected_on_device","start_reason":"%s","resumed_from_session_id":%s,'
         '"coordinates":"as received from GNSS, not map-matched",'
         '"hdop_note":"unitless dilution factor, not metres"},"features":[\n' % (m.sid, m.mode, m.start_reason, rf),
         '{"type":"Feature","properties":{"kind":"track","session_id":"%s","movement_mode":"%s",'
         '"segment_break":"NOFIX row"},"geometry":{"type":"MultiLineString","coordinates":[' % (m.sid, m.mode)]
    run, pend, first = 0, None, True
    for r in recs:
        if r is None:
            continue
        if r["type"] == T_FIX:
            run += 1
            if run == 1:
                pend = r
                continue
            if run == 2:
                o.append("\n[" if first else ",\n[")
                first = False
                o.append(pos(pend))
            o.append("," + pos(r))
        elif r["type"] == T_NOFIX:
            if run >= 2:
                o.append("]")
            run = 0
    if run >= 2:
        o.append("]")
    o.append("]}}")
    run = 0
    for r in recs:
        if r is None:
            continue
        if r["type"] == T_FIX:
            run += 1
            if run == 1:
                pend = r
        elif r["type"] == T_NOFIX:
            if run == 1:
                o.append(',\n{"type":"Feature","properties":{"kind":"isolated_fix","seq":%d},'
                         '"geometry":{"type":"Point","coordinates":%s}}' % (pend["seq"], pos(pend)))
            run = 0
    if run == 1:
        o.append(',\n{"type":"Feature","properties":{"kind":"isolated_fix","seq":%d},'
                 '"geometry":{"type":"Point","coordinates":%s}}' % (pend["seq"], pos(pend)))
    off = m.offset
    for r in recs:
        if r is None:
            continue
        if r["type"] == T_CLOCK:
            off = r["offset"]
        if r["type"] != T_EVENT:
            continue
        t = '"%s"' % fmt_iso_epoch(off + r["press"]) if off is not None else "null"
        rs = str(r["ref_seq"]) if r["ref_seq"] != U32_NONE else "null"
        ra = str(r["ref_age"]) if r["ref_age"] != U32_NONE else "null"
        o.append(',\n{"type":"Feature","properties":{"kind":"event_marker","event_no":%d,"seq":%d,"located":%s,'
                 '"utc_est":%s,"ref_fix_seq":%s,"ref_fix_age_ms":%s,"source":"device_button"},"geometry":'
                 % (r["event_no"], r["seq"], "true" if r["located"] else "false", t, rs, ra))
        if r["located"]:
            o.append('{"type":"Point","coordinates":[%s,%s]}}' % (fmt_e7(r["lon"]), fmt_e7(r["lat"])))
        else:
            o.append("null}")
    o.append("\n]}\n")
    return "".join(o)


def write_outputs(data, wfg_name, out_dir):
    """Write .wfg + converted files + .sha256 + integrity json. Returns (base_path, report)."""
    m = Meta(data, wfg_name)
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.join(out_dir, "%s_%s" % (m.sid, m.mode))
    rep = integrity(data)
    sha = hashlib.sha256(data).hexdigest()
    with open(base + ".wfg", "wb") as f:
        f.write(data)
    for ext, fn in ((".csv", to_csv), (".gpx", to_gpx), (".geojson", to_geojson)):
        with open(base + ext, "w", encoding="utf-8", newline="") as f:
            f.write(fn(data, wfg_name))
    with open(base + ".wfg.sha256", "w") as f:
        f.write("%s  %s\n" % (sha, os.path.basename(base) + ".wfg"))
    rep.update({"sha256": sha, "device_file": wfg_name, "session_id": m.sid, "movement_mode": m.mode,
                "exported_utc": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    with open(base + ".integrity.json", "w") as f:
        json.dump(rep, f, indent=1)
    return base, rep


# ----------------------------------------------------------------------------- serial protocol
class Device:
    def __init__(self, port, baud=115200, timeout=5.0):
        import serial  # pyserial
        self.s = serial.serial_for_url(port, baudrate=baud, timeout=timeout)
        time.sleep(0.3)
        self.s.reset_input_buffer()

    def cmd(self, line):
        self.s.write((line + "\n").encode())
        self.s.flush()

    def readline(self, timeout=10.0):
        end = time.time() + timeout
        while time.time() < end:
            raw = self.s.readline()
            if not raw:
                continue
            ln = raw.decode("utf-8", "replace").rstrip("\r\n")
            if not ln or ln.startswith("#"):
                continue  # firmware log lines
            return ln
        raise TimeoutError("no reply from device (is it the right port? is it recording?)")

    def hello(self):
        self.cmd("HELLO")
        while True:
            ln = self.readline()
            if ln.startswith("OK HELLO") or ln.startswith("ERR"):
                return ln

    def list(self):
        self.cmd("LIST")
        out = []
        while True:
            ln = self.readline()
            if ln.startswith("SESS "):
                p = ln.split()
                out.append({"name": p[1], "size": int(p[2]), "records": int(p[3]), "mode": p[4],
                            "closed": p[5] == "1", "end_reason": p[6], "exported": p[7] == "1", "sha256": p[8]})
            elif ln.startswith("OK LIST"):
                return out
            elif ln.startswith("ERR"):
                raise RuntimeError(ln)

    def dump(self, name):
        self.cmd("DUMP " + name)
        ln = self.readline(30)
        if ln.startswith("ERR"):
            raise RuntimeError(ln)
        p = ln.split()
        if p[0] != "BEGIN" or p[1] != name:
            raise RuntimeError("unexpected reply: " + ln)
        size, sha = int(p[2]), p[3]
        buf = bytearray()
        expect = 0
        while True:
            ln = self.readline(30)
            if ln.startswith("R "):
                _, idx, hx = ln.split()
                if int(idx) != expect:
                    raise RuntimeError("record index gap at %d (got %s)" % (expect, idx))
                buf += bytes.fromhex(hx)
                expect += 1
            elif ln.startswith("T "):
                buf += bytes.fromhex(ln.split()[1])
            elif ln.startswith("OK DUMP"):
                break
            elif ln.startswith("ERR"):
                raise RuntimeError(ln)
        return bytes(buf), size, sha

    def simple(self, line, ok_prefix):
        self.cmd(line)
        while True:
            ln = self.readline(30)
            if ln.startswith(ok_prefix) or ln.startswith("ERR") or ln.startswith("PENDING"):
                return ln


def cmd_dump(dev, names, out_dir, confirm):
    failures = 0
    for name in names:
        data, size, dev_sha = dev.dump(name)
        sha = hashlib.sha256(data).hexdigest()
        rep = integrity(data)
        if len(data) != size or sha != dev_sha:
            print("FAIL %s: transfer mismatch (len %d/%d, sha %s.. vs device %s..)" % (name, len(data), size, sha[:12],
                                                                                     dev_sha[:12]))
            failures += 1
            continue
        base, rep = write_outputs(data, name, out_dir)
        print("%s -> %s.{wfg,csv,gpx,geojson}  status=%s records=%d fix=%d nofix=%d events=%d crc_err=%d sha256=%s"
              % (name, base, rep["status"], rep["records"], rep["fix"], rep["nofix"], rep["events"],
                 rep["crc_errors"], sha))
        if not rep["has_end"]:
            print("  note: session not closed on device (still recording or not yet recovered); not confirmable")
            continue
        if confirm:
            # Re-read what we wrote, so confirmation proves the copy on disk, not just the bytes in memory.
            with open(base + ".wfg", "rb") as f:
                disk_sha = hashlib.sha256(f.read()).hexdigest()
            if disk_sha != dev_sha:
                print("  FAIL: file on disk does not match; NOT confirming")
                failures += 1
                continue
            print("  " + dev.simple("CONFIRM %s %s" % (name, disk_sha), "OK CONFIRM"))
    return failures


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["ports", "list", "dump", "delete", "convert", "verify", "check"])
    ap.add_argument("file", nargs="?")
    ap.add_argument("--port")
    ap.add_argument("--session")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--out", default="exports")
    ap.add_argument("--confirm", action="store_true", help="mark verified, closed sessions as exported on the device")
    a = ap.parse_args(argv)

    if a.action == "ports":
        from serial.tools import list_ports
        for p in list_ports.comports():
            print(p.device, "-", p.description, "VID:PID=%s:%s" % (hex(p.vid or 0), hex(p.pid or 0)))
        return 0
    if a.action in ("convert", "verify"):
        if not a.file:
            ap.error("give a .wfg file")
        with open(a.file, "rb") as f:
            data = f.read()
        rep = integrity(data)
        if a.action == "convert":
            base, rep = write_outputs(data, os.path.basename(a.file), a.out)
            print("wrote %s.{wfg,csv,gpx,geojson,integrity.json}" % base)
        print(json.dumps(rep, indent=1))
        return 0 if rep["status"] in ("OK", "RECOVERED") else 1
    if not a.port:
        ap.error("--port is required (see: usb_export.py ports)")
    dev = Device(a.port)
    print(dev.hello())
    if a.action == "list":
        for s in dev.list():
            print("%-12s %8d B %6d rec %-8s closed=%d %-18s exported=%d %s" % (
                s["name"], s["size"], s["records"], s["mode"], s["closed"], s["end_reason"], s["exported"],
                s["sha256"][:16]))
        return 0
    if a.action == "check":
        print(dev.simple("CHECK " + a.session, "OK CHECK"))
        return 0
    if a.action == "dump":
        sessions = dev.list()
        names = [s["name"] for s in sessions] if a.all else ([a.session] if a.session else [])
        if not names:
            ap.error("use --session NAME or --all")
        return 1 if cmd_dump(dev, names, a.out, a.confirm) else 0
    if a.action == "delete":
        if not a.session:
            ap.error("--session required")
        s = [x for x in dev.list() if x["name"] == a.session]
        if not s:
            print("no such session")
            return 1
        if not s[0]["exported"]:
            print("Refusing: session is not export-confirmed. Run: dump --session %s --confirm" % a.session)
            return 1
        ln = dev.simple("DELETE %s %s" % (a.session, s[0]["sha256"]), "OK DELETE")
        print(ln)
        if ln.startswith("PENDING"):
            print("Now HOLD the device button for 2.5 s (within 30 s) to delete...")
            ln = dev.readline(40)
            print(ln)
        return 0 if ln.startswith("OK DELETE") else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
