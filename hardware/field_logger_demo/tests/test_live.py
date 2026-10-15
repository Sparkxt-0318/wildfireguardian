"""LIVE (spec test 9): the host fake device of firmware 0.3.0 on a pseudo-terminal streams '#J' and '#N' lines; the
app shows them with positions masked inside privacy zones; P works on the same connection; unplugging shows the
banner without a crash; with the double, plugging back in resumes. Also the LIVE state on its own: masking, the
satellite count and stop detection that agrees with REPLAY."""
import datetime as dt
import json
import math
import re
import time

import pytest

from app import config, library, stops
from app.device import double as dbl
from app.device import profiles
from app.device.live import LiveState
from app.device.manager import DOUBLE_PORT, DeviceManager
from conftest import FAST, Recorder, only_extra_ports, wait_for
from fakes import nmea
from fakes.ptybridge import PtyDevice
from fakes.tracks import build

LAT0, LON0 = 35.1470, 126.8390
M_PER_DEG_LON = 111320.0 * math.cos(math.radians(LAT0))


@pytest.fixture
def live_dev(fake_device_live_bin, tmp_path):
    devdir = tmp_path / "device_fs"
    devdir.mkdir()
    dev = PtyDevice(fake_device_live_bin, devdir)
    time.sleep(0.2)
    yield dev
    dev.close()


def _feed(dev, t, lat=None, lon=None, speed=0.0):
    for s in nmea.epoch(t, lat, lon, speed):
        dev.inject("!NMEA " + s)
    time.sleep(0.3)                                    # an epoch is committed after 250 ms without a sentence


def _raw_seen(rec, text, timeout=5):
    return wait_for(lambda: any(e.get("raw") == text for e in rec.lines()), timeout)


def test_live_lines_privacy_and_p_on_the_same_connection(live_dev, tmp_root):
    dev = live_dev
    rec = Recorder()
    port = {"device": dev.port, "description": "USB Serial", "vid": 0x1A86, "pid": 0x7523, "vidpid": "1A86:7523",
            "serial": None, "chip": "CH340", "usb": True, "likely": True, "simulated": False}
    m = DeviceManager(rec, list_ports_fn=lambda **kw: only_extra_ports(extra_ports=[port]), timing=FAST)
    m.start()
    try:
        m.connect(dev.port)
        assert wait_for(lambda: m.conn["state"] == "connected" and m.busy is None, 10), m.conn
        assert m.mode == "live"
        sent = [e["raw"] for e in rec.lines() if e.get("dir") == "→"]
        assert "LIVE ON" in sent and "LIVE NMEA ON" in sent
        for k in range(3):                             # idle: epochs stream, nothing is recorded
            _feed(dev, 30000 + k, LAT0, LON0)
        dev.inject("!START WALK")
        assert _raw_seen(rec, "# REC S000001.wfg WALK")
        track = []
        for k in range(25):                            # 40 m per epoch eastwards: out of the start zone after a few
            lat, lon = LAT0, LON0 + k * 40.0 / M_PER_DEG_LON
            _feed(dev, 30010 + k, lat, lon, 1.3)
            track.append((lat, lon))
            if k == 12:
                dev.inject("!MARK")
        dev.inject("!STOP")
        assert _raw_seen(rec, "# STOPPED - saved")
        live = [e for e in rec.events if e.get("type") == "live"]
        kinds = [e["ev"] for e in live]
        assert "session" in kinds and "session_end" in kinds and "event" in kinds and "sats" in kinds
        eps = [e for e in live if e["ev"] == "ep" and e["recording"]]
        assert len(eps) == 25
        hidden = [e for e in eps if e["row"]["h"]]
        shown = [e for e in eps if not e["row"]["h"]]
        assert len(hidden) >= 3 and len(shown) >= 10
        assert all(not e["row"]["la"] for e in live if e["ev"] == "ep" and not e["recording"])   # idle: never shown
        assert all(e["row"]["la"] is None and e["row"]["lo"] is None for e in hidden)
        assert m.live.sats_signal == 6                 # satellites with an SNR in the GSV sentences
        jl = [e["raw"] for e in rec.lines() if e.get("cls") == "live"]
        nl = [e["raw"] for e in rec.lines() if e.get("cls") == "nmea"]
        assert any('"t":"ep"' in x for x in jl) and any('"t":"rec"' in x for x in jl) and nl
        # no hidden position reaches the page: not in the rows, not in the raw '#J' or '#N' lines. Hidden are the idle
        # epochs, the start zone and, once the session has ended, the end zone (lines already shown are masked again).
        rz = next(e for e in live if e["ev"] == "rezone")
        assert len(rz["zones"]) == 2 and {z["kind"] for z in rz["zones"]} == {"start", "end"}
        final_rows = [r for r in rz["rows"] if r["t"] is not None]
        assert final_rows[-1]["h"] == 1 and final_rows[0]["h"] == 1 and any(not r["h"] for r in final_rows)
        remasked = {x["n"]: x["raw"] for e in rec.events if e.get("type") == "remask" for x in e["lines"]}
        assert remasked
        page_lines = [dict(e, raw=remasked.get(e["n"], e["raw"])) for e in rec.lines()]
        page = json.dumps(page_lines) + json.dumps(rz)
        tokens = set(re.findall(r"\d+\.\d+", page))               # whole numbers only: 126.839 is not 126.8391
        hidden_pts = [(LAT0, LON0)] + [pt for r, pt in zip(final_rows, track) if r["h"]]
        for lat, lon in hidden_pts:                      # the latitude is the same everywhere here: check longitudes
            forms = {"%.7f" % lon, json.dumps(round(lon, 7)), nmea._ll(lat, lon)[1].split(",")[0]}
            assert not forms & tokens, forms & tokens
        shown_pts = [pt for r, pt in zip(final_rows, track) if not r["h"]]
        assert shown_pts and nmea._ll(*shown_pts[0])[1].split(",")[0] in tokens   # the check sees a shown position
        assert any('"la":"xxxxxxxxxx"' in x["raw"] for x in page_lines if x.get("cls") == "live")
        # P works on the same connection, and the file holds the positions the live view showed
        assert m.conn["state"] == "connected" and m.mode == "live"
        names = [s["name"] for s in m.device_sessions()["sessions"]]
        assert names == ["S000001.wfg"]
        out = m.pull("S000001.wfg")
        assert out["ok"] and out["file"].startswith("real/WFG-1A2B3C4D-000001_WALK")
        s = library.load(config.SESSIONS / out["file"])
        fixes = [(r["lat"], r["lon"]) for r in s.rows if r["fix"]]
        assert len(fixes) >= 8                         # the logger writes at most one row a second; epochs came faster
        for lat, lon in fixes:
            assert any(abs(lat - a) < 2e-7 and abs(lon - b) < 2e-7 for a, b in track)
        assert len(s.events) == 1
        # LIVE OFF before LIST and DUMP, LIVE ON again afterwards (spec section 8, P)
        sent = [e["raw"] for e in rec.lines() if e.get("dir") == "→"]
        i_off = sent.index("LIVE OFF")
        i_dump = max(i for i, x in enumerate(sent) if x.startswith("DUMP "))
        assert "LIST" in sent[i_off:i_dump] and "LIVE ON" in sent[i_dump:] and m.mode == "live"
        # every '#J rec' line is a record of the file: same seq, and the same bytes where nothing is masked
        data = (config.SESSIONS / out["file"]).read_bytes()
        recs = [json.loads(x["raw"][3:]) for x in page_lines if x.get("live") == "rec"]
        assert [r["seq"] for r in recs] == list(range(len(data) // 48))
        assert sum(1 for r in recs if r["ty"] == 2) == len(fixes)
        plain = [r for r in recs if "x" not in r["hx"]]
        assert plain and all(r["hx"] == data[r["seq"] * 48:(r["seq"] + 1) * 48].hex() for r in plain)
        # unplugging shows the banner, and the app keeps running
        dev.unplug()
        assert wait_for(lambda: m.conn["state"] == "lost", 5)
        assert wait_for(lambda: "lost" in rec.codes(), 5)
        time.sleep(0.3)
        assert m.alive and m.snapshot()["conn"]["state"] == "lost"
    finally:
        m.shutdown()


def test_plugging_back_in_resumes_live(tmp_root):
    d = dbl.LoggerDouble(fw="0.3.0", gnss="fix")
    rec = Recorder()
    m = DeviceManager(rec, double_obj=d, list_ports_fn=only_extra_ports, timing=FAST)
    m.start()
    try:
        m.connect(DOUBLE_PORT)
        assert wait_for(lambda: m.conn["state"] == "connected" and m.busy is None, 8)
        assert m.mode == "live"
        profiles.update(m.device_id(), reconnect_ok=True, open_method="default")
        d.press("long")
        assert wait_for(lambda: any(e.get("ev") == "ep" and e.get("recording") for e in rec.events), 5)
        d.unplug()
        assert wait_for(lambda: m.conn["state"] == "lost", 5)
        n = len(rec.events)
        d.replug()
        assert wait_for(lambda: m.conn["state"] == "connected", 8), m.conn
        assert m.mode == "live" and d.received.count("LIVE ON") == 2
        assert wait_for(lambda: any(e.get("ev") == "ep" and e.get("recording") for e in rec.events[n:]), 5)
        assert m.snapshot()["live"]["recording"]
    finally:
        m.shutdown()


def test_firmware_0_2_0_gives_basic_mode_and_0_3_0_live_mode(tmp_root):
    for fw, mode in (("0.2.0", "basic"), ("0.3.0", "live")):
        d = dbl.LoggerDouble(fw=fw)
        m = DeviceManager(Recorder(), double_obj=d, list_ports_fn=only_extra_ports, timing=FAST)
        m.start()
        try:
            m.connect(DOUBLE_PORT)
            assert wait_for(lambda: m.conn["state"] == "connected" and m.busy is None, 8)
            assert m.mode == mode
        finally:
            m.shutdown()


# ------------------------------------------------------------------ the LIVE state on its own
def _ep(r, ss=1, rs="RECORDING", utc0=None):
    """The '#J ep' object of one row; utc0 (epoch ms at mono 0) adds the receiver's UTC as the firmware writes it."""
    utc = None
    if utc0 is not None:
        utc = dt.datetime.fromtimestamp((utc0 + r["mono"]) / 1000.0, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return {"v": 1, "t": "ep", "ms": int(r["mono"]), "utc": utc, "fix": 1 if r["fix"] else 0, "la": r["lat"],
            "lo": r["lon"], "sp": r["speed"], "su": 9, "hd": r["hdop"], "ft": "3D" if r["fix"] else "NONE",
            "nr": None if r["fix"] else "RECEIVER_NO_FIX", "rs": rs, "ss": ss, "md": "WALK"}


def test_live_stops_agree_with_replay():
    rows = build([("stop", 60, 0.8), ("move", 60, 1.3), ("stop", 30, 0.5), ("move", 60, 1.3), ("stop", 25, 0.5),
                  ("move", 60, 1.3), ("stop", 30, 0.8)])
    ls = LiveState(named_zones=[], auto_zones=False)
    ls.on_json({"t": "ss", "ss": 1, "md": "WALK", "sr": "OWNER_BUTTON"})
    detected, ended = [], []
    for r in rows:
        for e in ls.on_json(_ep(r)):
            if e["ev"] == "stop_detected":
                detected.append((e, r["t"]))
            elif e["ev"] == "stop_ended":
                ended.append((e, r["t"]))
    final = ls.on_json({"t": "se", "ss": 1, "er": "USER_STOP", "n": len(rows)})
    ref = stops.analyse(rows, "WALK", sensitivity=False)["stops"]
    # while recording, standing at the end looks like a stop (the session might go on); when it ends, the same run as
    # REPLAY finds it is the lead-out and withdraws it
    assert len(ref) == 2 and len(detected) == 3 and detected[2][0]["t0"] >= rows[-30]["t"] - 1
    assert [e["n"] for e in final if e["ev"] == "stop_removed"] == [3]
    ended = [x for x in ended if x[0]["n"] != 3]
    assert len(ended) == 2
    for (e, t_seen), s in zip(detected, ref):
        assert abs(e["t0"] - s["t0"]) <= 1.0            # the same start as REPLAY
        assert s["t0"] + 9.0 + 2.0 <= t_seen <= s["t0"] + 9.0 + 2.0 + 2.0   # announced when it reaches 10 s, 2 s late
    for (e, _), s in zip(ended, ref):
        assert (e["t0"], e["t1"]) == (s["t0"], s["t1"])
    assert [(v["t0"], v["t1"]) for v in ls.summary()["stops"]] == [(s["t0"], s["t1"]) for s in ref]


def test_live_masks_positions_inside_zones():
    ls = LiveState(named_zones=[], auto_zones=True)
    ls.on_json({"t": "ss", "ss": 3, "md": "WALK", "sr": "OWNER_BUTTON"})
    first = {"mono": 1000, "fix": True, "lat": LAT0, "lon": LON0, "speed": 0.0, "hdop": 0.9}
    out = ls.on_json(_ep(first, ss=3))
    ep = next(e for e in out if e["ev"] == "ep")
    assert ep["row"]["h"] == 1 and ep["row"]["la"] is None              # the start zone covers the first fix
    assert [z["kind"] for z in next(e for e in out if e["ev"] == "zones")["zones"]] == ["start"]
    near = _ep({"mono": 2000, "fix": True, "lat": LAT0, "lon": LON0 + 50 / M_PER_DEG_LON, "speed": 1.2, "hdop": 0.9},
               ss=3)
    line = "#J " + json.dumps(near, separators=(",", ":"))
    ls.on_json(near)
    masked = ls.mask_json_line(line, near)
    assert '"la":"xxxxxxxxxx"' in masked and ("%.7f" % near["lo"]).rstrip("0") not in masked
    gga = "#N " + nmea.epoch(30000.0, LAT0, LON0)[0]
    assert re.match(r"^#N \$GNGGA,082000\.000,x{6}$", ls.mask_nmea(gga))
    far_lon = LON0 + 900 / M_PER_DEG_LON
    far = _ep({"mono": 3000, "fix": True, "lat": LAT0, "lon": far_lon, "speed": 1.2, "hdop": 0.9}, ss=3)
    ls.on_json(far)
    far_line = "#J " + json.dumps(far, separators=(",", ":"))
    assert ls.mask_json_line(far_line, far) == far_line
    assert ls.mask_nmea("#N " + nmea.epoch(30001.0, LAT0, far_lon)[0]).count("x") < 6
    # a FIX record inside the zone: position bytes and CRC masked in the '#J rec' line
    from app import simgen
    w = simgen.RecordWriter()
    w.start(1000, 0, 3, "WALK")
    w.fix(2000, 1791900000000, LAT0, LON0 + 50 / M_PER_DEG_LON, 31.0, 1.2, 90.0, 0.9, 9)
    hx = w.recs[-1].hex()
    rec = {"v": 1, "t": "rec", "seq": 1, "ty": 2, "b": 96, "crc": hx[88:96], "hx": hx}
    rl = ls.mask_json_line("#J " + json.dumps(rec), rec)
    assert '"crc":"xxxxxxxx"' in rl and hx[40:56] not in rl


def test_live_counts_drops_and_follows_a_session_started_before_connecting():
    ls = LiveState(named_zones=[], auto_zones=False)
    ls.on_json({"t": "drop", "n": 3})
    ev = ls.on_json({"t": "drop", "n": 2})
    assert ev[0]["total"] == 5 and ls.drops == 5
    out = ls.on_json(_ep({"mono": 5000, "fix": False, "lat": None, "lon": None, "speed": None, "hdop": None}, ss=7))
    assert ls.session_no == 7 and ls.recording and out[0]["recording"]
    assert out[0]["row"]["nr"] == "RECEIVER_NO_FIX"


def test_live_hides_every_position_until_the_first_fix_and_named_zones_hold_from_the_start():
    """Firmware 0.3.0 sends an epoch's NMEA sentences before its 'ep' line, so once a recording has started every
    position stays hidden until the first fix has opened the start zone. Any talker counts: a BeiDou-only receiver
    sends $BDGGA and $BDRMC. Named zones hold from the start of a session, before any fix."""
    ls = LiveState(named_zones=[], auto_zones=True)
    ls.on_json({"t": "ss", "ss": 4, "md": "WALK", "sr": "OWNER_BUTTON"})
    lon_text = nmea._ll(LAT0, LON0)[1].split(",")[0]
    with_pos = [x for x in nmea.epoch(30000.0, LAT0, LON0) if x[3:6] in ("GGA", "RMC")]
    assert len(with_pos) == 2
    for x in with_pos:
        for talker in ("GN", "GP", "BD", "GB"):
            line = "#N $" + talker + x[3:]
            masked = ls.mask_nmea(line)
            assert masked.endswith("x" * 6) and lon_text not in masked, masked
    # idle (not recording) BeiDou sentences are hidden too
    idle = LiveState(named_zones=[], auto_zones=True)
    bd = "#N $BD" + with_pos[0][3:]
    assert idle.mask_nmea(bd).endswith("x" * 6)
    # the first fix opens the start zone: from then on the zone decides
    ls.on_json(_ep({"mono": 1000, "fix": True, "lat": LAT0, "lon": LON0, "speed": 0.0, "hdop": 0.9}, ss=4))
    far = "#N " + nmea.epoch(30001.0, LAT0, LON0 + 900 / M_PER_DEG_LON)[0]
    assert ls.mask_nmea(far) == far
    assert ls.mask_nmea("#N " + with_pos[0]).endswith("x" * 6)
    # a named zone (privacy.json) hides from the start of a session, with or without the automatic zones, but it is
    # drawn only once the recorded route enters it: a circle the route never touches would only show where it is
    home = {"name": "home", "lat": LAT0 + 0.01, "lon": LON0, "radius_m": 300.0}
    ln = LiveState(named_zones=[home], auto_zones=False)
    ln.on_json({"t": "ss", "ss": 5, "md": "WALK", "sr": "OWNER_BUTTON"})
    assert ln.summary()["zones"] == []
    assert ln.mask_nmea("#N " + nmea.epoch(30000.0, LAT0 + 0.01, LON0)[0]).endswith("x" * 6)
    away = "#N " + nmea.epoch(30000.0, LAT0 - 0.02, LON0)[0]
    assert ln.mask_nmea(away) == away
    out = ln.on_json(_ep({"mono": 1000, "fix": True, "lat": LAT0 - 0.02, "lon": LON0, "speed": 1.2, "hdop": 0.9}, ss=5))
    assert not [e for e in out if e["ev"] == "zones"] and ln.summary()["zones"] == []
    out = ln.on_json(_ep({"mono": 2000, "fix": True, "lat": LAT0 + 0.01, "lon": LON0, "speed": 1.2, "hdop": 0.9}, ss=5))
    assert next(e for e in out if e["ev"] == "ep")["row"]["h"] == 1
    assert [z["kind"] for z in next(e for e in out if e["ev"] == "zones")["zones"]] == ["named"]
    assert [z["kind"] for z in ln.summary()["zones"]] == ["named"]


def test_nmea_masking_fails_closed():
    """A sentence whose position cannot be read (a lost comma, a garbled digit: the firmware forwards sentences with
    bad checksums too), a GNS sentence, or an unknown or proprietary type is masked whenever positions are hidden;
    types that never carry a position, and position types with empty fields, are shown as they are."""
    ls = LiveState(named_zones=[], auto_zones=True)
    ls.on_json({"t": "ss", "ss": 8, "md": "WALK", "sr": "OWNER_BUTTON"})
    ls.on_json(_ep({"mono": 1000, "fix": True, "lat": LAT0, "lon": LON0, "speed": 0.0, "hdop": 0.9}, ss=8))
    gga = nmea.epoch(30000.0, LAT0, LON0)[0]                       # inside the start zone
    lost_comma = gga.replace(",N,", ",N", 1)
    garbled = gga.replace("3508.", "35O8.", 1)
    gns = gga.replace("GNGGA", "GNGNS", 1)
    pubx = "$PUBX,00,082000.00,3508.8200,N,12650.3400,E,31.0,G3,2.1,2.0,0.0,0,0.0,0.9,1.0,1.1,10,0,0*00"
    for bad in (lost_comma, garbled, gns, pubx, "3508.8200,N,12650.3400,E"):
        masked = ls.mask_nmea("#N " + bad)
        assert "12650" not in masked and masked.endswith("x" * 6), masked
    far = nmea.epoch(30001.0, LAT0, LON0 + 900 / M_PER_DEG_LON)
    assert ls.mask_nmea("#N " + far[0]) == "#N " + far[0]           # a readable position outside every zone
    assert ls.mask_nmea("#N " + far[0].replace("GNGGA", "GNGNS", 1)).startswith("#N $GNGNS,")
    for safe in far[2:] + nmea.epoch(30002.0)[:2]:                 # GSA, GSV, and GGA and RMC without a fix
        assert ls.mask_nmea("#N " + safe) == "#N " + safe


def test_rezone_carries_the_stops_so_a_stop_inside_the_end_zone_loses_its_position():
    """Walk 520 m, stop 25 s, walk 104 m, end: the stop was announced with its position; the end zone covers it, so
    the 'rezone' event carries it masked and the page replaces its stops with these."""
    rows = build([("stop", 60, 0.8), ("move", 400, 1.3), ("stop", 25, 0.5), ("move", 80, 1.3)])
    ls = LiveState(named_zones=[], auto_zones=True)
    ls.on_json({"t": "ss", "ss": 6, "md": "WALK", "sr": "OWNER_BUTTON"})
    ended = []
    for r in rows:
        ended += [e for e in ls.on_json(_ep(r, ss=6)) if e["ev"] == "stop_ended"]
    assert len(ended) == 1 and ended[0]["la"] is not None and ended[0]["h"] == 0
    out = ls.on_json({"t": "se", "ss": 6, "er": "USER_STOP", "n": len(rows)})
    rz = next(e for e in out if e["ev"] == "rezone")
    st = [x for x in rz["stops"] if x["n"] == ended[0]["n"]]
    assert len(st) == 1 and st[0]["la"] is None and st[0]["lo"] is None and st[0]["h"] == 1
    assert {z["kind"] for z in rz["zones"]} == {"start", "end"}


def test_live_stops_are_written_into_the_device_stream(tmp_root):
    """Spec 6.9: the REPLAY console's stop lines also appear in the device stream in LIVE, with the circled number
    and the start on the local clock of the place (Korea here)."""
    rows = build([("stop", 60, 0.8), ("move", 60, 1.3), ("stop", 30, 0.5), ("move", 60, 1.3)])
    rec = Recorder()
    m = DeviceManager(rec, timing=FAST, list_ports_fn=only_extra_ports)
    m.live = LiveState(named_zones=[], auto_zones=False)
    utc0 = 1792800000000                       # 2026-10-24 06:40:00 UTC = 15:40:00 in Seoul
    m._on_live_json('#J {"v":1,"t":"ss","ss":2,"md":"WALK","sr":"OWNER_BUTTON"}')
    for r in rows:
        m._on_live_json("#J " + json.dumps(_ep(r, ss=2, utc0=utc0), separators=(",", ":")))
    m._on_live_json('#J {"v":1,"t":"se","ss":2,"er":"USER_STOP","n":%d}' % len(rows))
    lines = [e for e in rec.lines() if e.get("code") in ("live_stop", "live_stop_end", "live_stop_removed")]
    assert [e["code"] for e in lines] == ["live_stop", "live_stop_end"]
    det, end = lines
    ref = stops.analyse(rows, "WALK", sensitivity=False)["stops"][0]
    t0 = dt.datetime.fromtimestamp((utc0 + rows[0]["mono"]) / 1000.0 + ref["t0"], dt.timezone(dt.timedelta(hours=9)))
    assert det["args"]["n"] == "\u2460" and det["args"]["time"] == t0.strftime("%H:%M:%S")
    assert det["args"]["v"] == 0.35 and det["args"]["t"] == 10 and det["cls"] == "det"
    assert end["args"]["dur"] == "%d:%02d" % divmod(int(ref["dur"]), 60)
    assert "Stop \u2460 detected" in det["text"] and det["text"].endswith("(speed under 0.35 m/s for 10 s)")


def test_saved_record_activity_crc_and_no_positions():
    """Synthetic records: validate progress without exposing or inventing coordinates."""
    import binascii
    import struct
    live = LiveState(named_zones=[], auto_zones=False)
    def rec(seq, mono):
        b = bytearray(48)
        b[:2] = b"WF"
        struct.pack_into("<BBII", b, 2, 3, 0, seq, mono)
        struct.pack_into("<I", b, 44, binascii.crc32(b[:44]) & 0xffffffff)
        return {"t": "rec", "seq": seq, "ty": 3, "hx": b.hex()}
    first = rec(8, 1000)
    assert live.on_json(first) == [{"ev": "activity", "count": 9, "span": 0.0, "samples": 1, "fix": False, "reason": 0}]
    assert live.on_json(rec(9, 4000))[0]["span"] == 3.0
    assert live.on_json(first) == []
    bad = rec(10, 5000)
    bad["hx"] = bad["hx"][:-2] + "ff"
    assert live.on_json(bad) == []
    assert live.summary()["activity"]["samples"] == 2
    assert live.rows == []
