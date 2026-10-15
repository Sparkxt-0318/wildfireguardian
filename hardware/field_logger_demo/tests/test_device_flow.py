"""The device page's flows with the test double (spec test 16, and the pull, unplug and restart paths of section 3C).

The double follows firmware 0.2.0 (its '#' lines, replies and button rules) on a manual clock, so the tests decide
when the device's time moves. Every test ends with a check that the app sent no DELETE, CONFIRM or FORMAT, and no
CALVBAT (only the calibration form may send it; test_wifi_cal.py covers that).
"""
import json
import re
import time

import pytest

from app import config, library, replay
from app.device import double as dbl
from app.device import test_flow
from app.device.manager import DOUBLE_PORT, DeviceManager, parse_status
from conftest import FAST, Recorder, only_extra_ports, wait_for
from fakes import logger_double as fx

FORBIDDEN = re.compile(r"^(DELETE|CONFIRM|FORMAT|CALVBAT)\b")


class Rig:
    def __init__(self, m, d, rec):
        self.m, self.d, self.rec = m, d, rec

    def connect(self, port=DOUBLE_PORT):
        self.m.connect(port)
        ok = wait_for(lambda: self.m.conn["state"] == "connected" and self.m.busy is None, 10)
        assert ok, (self.m.conn, self.rec.codes()[-8:])

    def steps(self):
        return [s["st"] for s in self.m.test.steps]

    def wait_step(self, i, st="done", timeout=8):
        ok = wait_for(lambda: self.m.test and self.m.test.steps[i]["st"] == st, timeout)
        assert ok, (i, st, self.steps(), self.rec.codes()[-6:])


def _make(tmp_root, monkeypatch, real_port=False, **dkw):
    monkeypatch.setattr(test_flow, "WAIT_S", 0.6)
    d = dbl.LoggerDouble(clock=dbl.ManualClock(), **dkw)
    rec = Recorder()
    if real_port:
        # the double behind an ordinary USB port entry: the app treats it as real hardware (real/ folders, library)
        port = {"device": "/dev/cu.usbserial-TEST", "description": "USB Serial", "vid": 0x1A86, "pid": 0x7523,
                "vidpid": "1A86:7523", "serial": None, "chip": "CH340", "usb": True, "likely": True, "simulated": False}
        m = DeviceManager(rec, list_ports_fn=lambda **kw: only_extra_ports(extra_ports=[port] if d.present else []),
                          factory=lambda p, method: d.open_port(method), timing=FAST)
    else:
        m = DeviceManager(rec, double_obj=d, list_ports_fn=only_extra_ports, timing=FAST)
    m.start()
    return Rig(m, d, rec)


@pytest.fixture
def rig(tmp_root, monkeypatch):
    r = _make(tmp_root, monkeypatch)
    yield r
    r.m.shutdown()
    sent = [x for x in r.d.received if FORBIDDEN.match(x)]
    assert not sent, sent


@pytest.fixture
def real_rig(tmp_root, monkeypatch):
    r = _make(tmp_root, monkeypatch, real_port=True, device_id=0x1A2B3C4D, board="TEST BOARD")
    yield r
    r.m.shutdown()
    r.d.close()
    sent = [x for x in r.d.received if FORBIDDEN.match(x)]
    assert not sent, sent


def _rows(result):
    return {r["id"]: (r["mark"], r["variant"]) for r in result["rows"]}


# ------------------------------------------------------------------ the five steps
def test_steps_turn_green_only_on_the_devices_own_lines(rig):
    m, d = rig.m, rig.d
    rig.connect()
    assert m.mode == "basic" and m.hello["fw"] == "0.2.0" and m.restart_on_open is False
    m.set_view(True)
    m.test_start()
    assert rig.steps() == ["now", "todo", "todo", "todo", "todo"]
    time.sleep(0.6)
    assert rig.steps()[0] == "now"                          # nothing happened on the device: nothing turns green
    d.press("long")
    rig.wait_step(0)
    assert m.test.session == "S000001.wfg" and m.test.steps[0]["variant"] == "started"
    assert m.snapshot()["status"]["state"] == "RECORDING"
    time.sleep(0.8)
    assert rig.steps()[1] == "now"                          # the 30 s wait does not start without the button mark
    d.press("short")
    d.advance(40.0)                                         # 40 s of the device's time: gap-filler rows every 1.5 s
    rig.wait_step(1)
    assert m.test.steps[1]["located"] is False              # indoors: EVENT n (NO POSITION)
    rig.wait_step(2)
    assert m.test.records >= 25
    assert rig.steps()[3] == "now"
    d.press("long")
    rig.wait_step(3)
    assert m.test.steps[3]["reason"] == "stopped"
    rig.wait_step(4, timeout=10)
    assert m.test.phase == "done"
    res = m.result
    assert res["session"] == "S000001.wfg" and res["file"].startswith("sim/device_double/")
    assert _rows(res) == {"file": ("ok", "ok"), "ended": ("ok", "user_stop"), "spacing": ("ok", "filler"),
                          "gnss": ("ok", "talking"), "position": ("info", "none"), "button": ("ok", "ok"),
                          "battery": ("ok", "ok"), "storage": ("ok", "ok"), "screen": ("wait", "ask"),
                          "restart": ("info", "no"), "clock": ("info", "later")}
    assert res["counts"] == {"ok": 7, "info": 3, "bad": 0, "wait": 1}
    assert 38.0 <= res["duration_s"] <= 42.0
    m.screen_answer(True)
    assert _rows(m.result)["screen"] == ("ok", "seen") and m.result["ok"]
    # the pulled file is SIM data from the double: watermarked, under sessions/sim/, never shown as device data
    p = config.SESSIONS / res["file"]
    assert p.exists() and p.with_name(p.name + ".sim.json").exists()
    pay = replay.build(library.entry_for_file(res["file"]))
    assert pay["meta"]["sim"] and pay["meta"]["sim_kind"] == "double" and pay["metrics"] is None
    assert "sha_ok" in rig.rec.codes() and "crc_ok" in rig.rec.codes()


def test_a_long_press_during_step_2_goes_to_step_5(rig):
    m, d = rig.m, rig.d
    rig.connect()
    m.test_start()
    d.press("long")
    rig.wait_step(0)
    d.press("long")                                         # stopped before the button mark
    rig.wait_step(3)
    assert rig.steps()[1:3] == ["skipped", "skipped"]
    rig.wait_step(4, timeout=10)
    rows = _rows(m.result)
    assert rows["button"] == ("bad", "none") and rows["spacing"] == ("bad", "short")


def test_export_mode_shows_its_note(rig):
    m, d = rig.m, rig.d
    rig.connect()
    m.test_start()
    d.press("very_long")
    assert wait_for(lambda: m.test.note == "export_on", 5)
    assert m.export_mode
    d.press("long")                                         # in export mode only the 6 s hold does anything
    time.sleep(0.4)
    assert rig.steps()[0] == "now"
    d.press("very_long")
    assert wait_for(lambda: m.test.note is None and not m.export_mode, 5)
    d.press("long")
    rig.wait_step(0)


def test_a_device_already_recording_starts_at_already_recording(rig):
    m, d = rig.m, rig.d
    d.press("long")                                         # recording before the laptop connects
    rig.connect()
    assert m.rec_before_connect and m.status["state"] == "RECORDING"
    m.test_start()
    assert m.test.steps[0]["st"] == "done" and m.test.steps[0]["variant"] == "already" and m.test.started_before


def test_the_result_says_when_the_session_began_before_the_laptop_was_connected(rig):
    m, d = rig.m, rig.d
    d.press("long")
    rig.connect()
    m.test_start()
    assert m.test.started_before
    d.press("long")                                         # stopped: steps 2 and 3 are skipped, then the pull
    rig.wait_step(3)
    rig.wait_step(4, timeout=10)
    assert m.result["started_before"] is True
    m.screen_answer(False)
    assert m.result["started_before"] is True               # kept when the screen answer recomputes the rows


def test_a_session_started_after_connecting_gets_no_before_note(rig):
    m, d = rig.m, rig.d
    rig.connect()
    d.press("long")                                         # started while connected, before T
    assert wait_for(lambda: m.status and m.status["state"] == "RECORDING", 5)
    m.test_start()
    assert m.test.started_before and m.test.steps[0]["variant"] == "already"
    d.press("long")
    rig.wait_step(4, timeout=10)
    assert m.result["started_before"] is False


def test_status_alone_drives_the_pill_and_the_steps(rig):
    m, d = rig.m, rig.d
    rig.connect()
    m.set_view(True)
    m.test_start()
    with d.lock:
        d._start()                                          # recording starts, but no '#' line reaches the laptop
    rig.wait_step(0)
    assert m.test.steps[0]["variant"] == "started" and m.snapshot()["status"]["state"] == "RECORDING"
    # and the flow alone, line by line
    t = test_flow.TestFlow(parse_status("OK STATUS state=IDLE mode=WALK session=- seq=0 free=2500000 total=2555904"))
    assert not t.on_status(parse_status("OK STATUS state=IDLE mode=WALK session=- seq=0 free=2500000 total=2555904"))
    assert t.on_status(parse_status("OK STATUS state=RECORDING mode=WALK session=S000004.wfg seq=3 free=1 total=2"))
    assert t.steps[0]["st"] == "done" and t.session == "S000004.wfg"
    assert t.on_status(parse_status("OK STATUS state=IDLE mode=WALK session=- seq=40 free=1 total=2"))
    assert t.steps[3]["reason"] == "idle" and t.ready_to_pull


def test_full_storage_in_step_1_shows_its_note(rig):
    m, d = rig.m, rig.d
    m.double_action("fill", {"on": True})
    rig.connect()
    m.test_start()
    d.press("long")
    assert wait_for(lambda: m.test.note == "full", 5), rig.rec.raws()[-3:]
    assert rig.steps()[0] == "now"
    assert any(e.get("raw") == "# FULL: cannot start" and e.get("note") == "full" for e in rig.rec.lines())


def test_storage_that_cannot_be_mounted_shows_the_storage_message(rig):
    m, d = rig.m, rig.d
    d.fs_fail_next_boot = True
    d.reset()
    rig.connect()
    assert m.fs_error and m.mode == "basic"
    assert "fs" in rig.rec.codes()
    assert any(e.get("raw") == "ERR FS not-mounted" for e in rig.rec.lines())
    assert m.vbat and m.vbat["valid"]                       # VBAT still works without storage
    with pytest.raises(RuntimeError, match="fs.error"):
        m.test_start()


# ------------------------------------------------------------------ result rows for chosen sessions (P)
CASES = {
    "indoor_cold_start": (fx.indoor_filler(), {"spacing": ("ok", "filler"), "gnss": ("ok", "talking"),
                                               "position": ("info", "none"), "button": ("ok", "ok"),
                                               "ended": ("ok", "user_stop"), "file": ("ok", "ok"),
                                               "clock": ("info", "later")}),
    "outdoor_fix": (fx.outdoor_fix(), {"spacing": ("ok", "normal"), "gnss": ("ok", "talking"),
                                       "position": ("info", "fix"), "clock": ("info", "synced"), "file": ("ok", "ok")}),
    "recovered": (fx.recovered(), {"file": ("ok", "ok"), "ended": ("info", "recovered")}),
    "no_nmea_data": (fx.indoor_filler(reason=2), {"gnss": ("bad", "nodata")}),
    "checksum_errors_only": (fx.indoor_filler(reason=3), {"gnss": ("bad", "cksum")}),
    "no_event": (fx.indoor_filler(event=False), {"button": ("bad", "none")}),
    "three_second_step": (fx.with_step(), {"spacing": ("bad", "step")}),
}


@pytest.mark.parametrize("case", sorted(CASES))
def test_result_rows(rig, case):
    data, expect = CASES[case]
    fx.check_ok(data)
    rig.d.sessions["S000001.wfg"] = data
    rig.connect()
    out = rig.m.pull("S000001.wfg")
    assert out["ok"], out
    rows = _rows(out["result"])
    for k, v in expect.items():
        assert rows[k] == v, (case, k, rows[k])
    if case == "three_second_step":
        step = next(r for r in out["result"]["rows"] if r["id"] == "spacing")
        assert step["p"]["max"] == 3.0
    if case == "outdoor_fix":
        pos = next(r for r in out["result"]["rows"] if r["id"] == "position")
        assert pos["p"] == {"n": 45, "sats": 10, "hdop": 0.9}


def test_a_corrupted_transfer_is_kept_as_bad_and_shown_red(rig):
    rig.d.sessions["S000001.wfg"] = fx.indoor_filler()
    rig.connect()
    rig.m.double_action("corrupt")
    out = rig.m.pull("S000001.wfg")
    assert not out["ok"] and out["status"] == "bad"
    res = out["result"]
    assert _rows(res)["file"] == ("bad", "bad") and not res["ok"] and res["file"] is None
    bad = config.SESSIONS / res["bad"]
    assert bad.exists() and bad.name.endswith(".wfg.bad")
    assert not list(bad.parent.glob("*.wfg"))               # nothing else was written
    assert "sha_bad" in rig.rec.codes()
    rig.m.double_action("samples")                          # the next pull is clean again
    assert rig.m.pull("S000001.wfg")["ok"]


def test_a_session_already_on_the_laptop_is_not_pulled_again(rig):
    rig.d.sessions["S000001.wfg"] = fx.outdoor_fix()
    rig.connect()
    first = rig.m.pull("S000001.wfg")
    dumps = sum(1 for x in rig.d.received if x.startswith("DUMP"))
    again = rig.m.pull("S000001.wfg")
    assert first["status"] == "saved" and again["status"] == "same" and again["file"] == first["file"]
    assert sum(1 for x in rig.d.received if x.startswith("DUMP")) == dumps
    assert "pull_same" in rig.rec.codes()


def test_dump_lines_that_arrive_after_the_pull_gave_up_are_masked_all_the_same(rig):
    """The firmware hashes the whole file before BEGIN (usb_export.py waits 30 s for it). When BEGIN comes after the
    limit the pull fails, and the R and T lines that follow arrive unsolicited: they are masked all the same."""
    data = fx.outdoor_fix()
    rig.d.sessions["S000001.wfg"] = data + data[:30]        # a torn tail too: one 'T' line
    rig.connect()
    rig.m.timing["dump_begin"] = 0.4
    rig.d.dump_delay_s = 1.0
    with pytest.raises(TimeoutError):
        rig.m.pull("S000001.wfg")
    n = len(data) // 48
    assert wait_for(lambda: sum(1 for e in rig.rec.lines("rec") if e["raw"].startswith("R ")) == n, 8)
    assert wait_for(lambda: any(e["raw"].startswith("T ") for e in rig.rec.lines("rec")), 5)
    pos = [data[k * 48 + 20:k * 48 + 28].hex() for k in range(n) if data[k * 48 + 2] == 2]
    page = json.dumps(rig.rec.lines())
    assert len(pos) > 10 and not [h for h in pos if h in page]
    torn = next(e for e in rig.rec.lines("rec") if e["raw"].startswith("T "))
    assert torn["raw"] == "T " + data[:20].hex() + "x" * 20
    assert rig.m.busy is None and rig.m.conn["state"] == "connected"
    # damaged DUMP lines arriving on their own are masked too: extra spaces, a stray character, a lost space
    k = next(i for i in range(n) if data[i * 48 + 2] == 2)
    hx = data[k * 48:(k + 1) * 48].hex()
    n0 = len(rig.rec.lines())
    for bad in ("R %d %s " % (k, hx), "R  %d  %s" % (k, hx), "R %d %sz" % (k, hx[:-1]), "R%d %s" % (k, hx),
                "T %s" % hx[:60].replace("a", "g"), "R %d %s" % (k, hx[:80])):
        rig.m._on_unsolicited(bad)
    late = json.dumps(rig.rec.lines()[n0:])
    assert len(rig.rec.lines()) - n0 == 6 and hx[40:56] not in late and hx[40:48] not in late, late


def test_an_unsupported_record_format_allows_no_pull_no_test_and_no_check(rig, monkeypatch):
    """Spec 3C step 3: a HELLO with another record format gets "이 펌웨어의 기록 형식은 ..." and no pulls."""
    proto = dbl.LoggerDouble._proto

    def other_format(self, line):
        if line.split()[:1] == ["HELLO"]:
            self.out('OK HELLO fw=0.9.0 board="FUTURE" device=00000000 fmt=3 recsize=64 state=IDLE')
            return
        proto(self, line)
    monkeypatch.setattr(dbl.LoggerDouble, "_proto", other_format)
    rig.d.sessions["S000001.wfg"] = fx.outdoor_fix()
    rig.connect()
    assert rig.m.format_error and "format" in rig.rec.codes()
    for fn in (rig.m.test_start, rig.m.device_sessions, lambda: rig.m.pull("S000001.wfg"), rig.m.conncheck_start,
               lambda: rig.m.wifi_pull("S000001.wfg")):
        with pytest.raises(RuntimeError, match="format.error"):
            fn()
    assert not [x for x in rig.d.received if x.split()[0] in ("LIST", "CHECK", "DUMP")]
    assert rig.m.busy is None


def test_device_errors_reach_the_page_as_short_409_codes():
    """app.main._call: a timeout, a lost link or a port error during P (or any device action) is a 409 with a code
    the page turns into a sentence, never an HTTP 500."""
    from fastapi import HTTPException

    from app.device.link import LinkLost
    from app.main import _call

    def raises(ex):
        def f():
            raise ex
        return f
    for ex, detail in ((TimeoutError("no reply to DUMP"), "timeout: no reply to DUMP"),
                       (LinkLost("connection lost"), "lost: connection lost"),
                       (OSError("[Errno 6] Device not configured"), "port: [Errno 6] Device not configured"),
                       (RuntimeError("busy: pull"), "busy: pull"), (ValueError("bad session name"), "bad session name")):
        with pytest.raises(HTTPException) as e:
            _call(raises(ex))
        assert e.value.status_code == 409 and e.value.detail == detail


def test_pull_is_refused_while_recording(rig):
    rig.connect()
    rig.d.press("long")
    assert wait_for(lambda: rig.m.status and rig.m.status["state"] == "RECORDING", 5)
    with pytest.raises(RuntimeError, match="pull.recording"):
        rig.m.device_sessions()


# ------------------------------------------------------------------ real hardware paths (the double behind a USB port)
def test_real_device_test_goes_to_device_tests_and_p_goes_to_the_library(real_rig):
    m, d = real_rig.m, real_rig.d
    real_rig.connect("/dev/cu.usbserial-TEST")
    assert not m.conn["simulated"] and m.hello["device"] == "1A2B3C4D"
    m.test_start()
    d.press("long")
    real_rig.wait_step(0)
    d.press("short")
    d.advance(32.0)
    real_rig.wait_step(2)
    d.press("long")
    real_rig.wait_step(4, timeout=10)
    f = m.result["file"]
    assert f.startswith("real/device_tests/WFG-1A2B3C4D-000001_WALK") and m.result["device_test"]
    assert (config.SESSIONS / f).exists() and not (config.SESSIONS / (f + ".sim.json")).exists()
    pay = replay.build(library.entry_for_file(f))
    assert pay["meta"]["device_test"] and not pay["meta"]["sim"]
    assert library.by_key(5) is None                        # device tests are not added to the start screen
    # P: a real pull is saved under sessions/real/ and gets the next free key on the start screen
    d.sessions["S000002.wfg"] = fx.outdoor_fix(no=2)
    out = m.pull("S000002.wfg")
    assert out["file"] == "real/WFG-1A2B3C4D-000002_WALK.wfg"       # named from the file's own session id
    entry = library.entry_for_file(out["file"])
    assert entry["key"] == 5 and entry["privacy"]["auto_zones"] is True


def test_a_name_clash_with_different_bytes_is_saved_with_a_suffix(real_rig):
    m, d = real_rig.m, real_rig.d
    d.sessions["S000001.wfg"] = fx.outdoor_fix()
    real_rig.connect("/dev/cu.usbserial-TEST")
    a = m.pull("S000001.wfg")
    d.sessions["S000001.wfg"] = fx.outdoor_fix(rows=50)      # same session id, other bytes (a reformatted board)
    b = m.pull("S000001.wfg")
    assert a["status"] == "saved" and b["status"] == "renamed" and b["file"].endswith("-2.wfg")
    sha_line = (config.SESSIONS / (b["file"] + ".sha256")).read_text().split()
    assert sha_line[1] == b["file"].split("/")[-1]


# ------------------------------------------------------------------ unplug, restart, flashing mode
def test_unplug_shows_the_banner_and_enter_reconnects(rig):
    m, d = rig.m, rig.d
    rig.connect()
    d.unplug()
    assert wait_for(lambda: m.conn["state"] == "lost", 5)
    assert wait_for(lambda: "lost" in rig.rec.codes(), 5)
    d.replug()
    assert wait_for(lambda: any(p["device"] == DOUBLE_PORT for p in m.ports()), 5)
    time.sleep(0.5)
    assert m.conn["state"] == "lost" and d.port is None        # no profile allows it: the app does not reopen
    rig.connect()


def test_a_restart_while_connected_is_marked(rig):
    m, d = rig.m, rig.d
    rig.connect()
    n = m.restarts
    d.reset()
    assert wait_for(lambda: m.restarts == n + 1, 5)
    assert wait_for(lambda: "restart" in rig.rec.codes(), 5)
    assert m.conn["state"] == "connected"


def test_flashing_mode_then_rst_finishes_the_handshake(rig):
    m, d = rig.m, rig.d
    d.restart_on["open_default"] = True
    d.download_next_boot = True
    m.connect(DOUBLE_PORT)
    assert wait_for(lambda: m.conn.get("error") == "download", 5), m.conn
    assert "download" in rig.rec.codes()
    d.restart_on["open_default"] = False
    d.reset()                                               # the owner presses RST
    assert wait_for(lambda: m.conn["state"] == "connected" and m.hello is not None, 8), m.conn


def test_a_file_with_the_reserved_sim_id_never_goes_to_the_real_folders(real_rig):
    """00000000 is the SIM device id: such a file stays with the simulated data even when it comes over a real port."""
    m, d = real_rig.m, real_rig.d
    d.sessions["S000001.wfg"] = fx.outdoor_fix(device_id=0)
    real_rig.connect("/dev/cu.usbserial-TEST")
    out = m.pull("S000001.wfg")
    assert out["file"].startswith("sim/device_double/WFG-00000000-000001")
    p = config.SESSIONS / out["file"]
    assert p.with_name(p.name + ".sim.json").exists()
    assert library.entry_for_file(out["file"])["key"] is None            # not on the start screen
    assert not (config.REAL_DIR.exists() and list(config.REAL_DIR.rglob("*.wfg")))
