"""Line notes (spec test 15) and how the link routes lines: replies complete the command in flight, nothing else does."""
import json
import re
import threading
import time

import pytest

from app.device import double as dbl
from app.device import link as linkmod
from app.device import notes
from app.device.manager import DeviceManager
from conftest import FIRMWARE, ROOT, Recorder, wait_for

# Every '#' line firmware 0.2.0 prints from main.cpp (banner() and setup()), with an example and the note the app adds.
# None means: shown unchanged on purpose (the delete results come from usb_export.py's delete, which the app never
# starts; the format lines follow a FORMAT the app never sends).
FIXTURE = [
    ("# FLASH SIZE MISMATCH: chip reports 4194304 bytes, board header expects 8 MB", "fs_error"),
    ("# FLASH SIZE MISMATCH", "fs_error"),
    ("# LittleFS partition is blank: formatting (no data to lose)", "fs_blank"),
    ("# RECOVERED S000003.wfg records=812 torn_bytes=17 closed=1 unrecoverable=0", "recovered_detail"),
    ("# RECOVERED 1 session", "recovered"),
    ("# RECOVERED 2 sessions", "recovered"),
    ("# RESUME decision RESUME (was S000003 mode WALK, reset_reason 4, quick_fails 0)", "resume_decision"),
    ("# RESUME decision GIVE_UP_LOOP (was S000003 mode VEHICLE, reset_reason 12, quick_fails 3)", "resume_decision"),
    ("# AUTO-RESUMED after reset", "resumed"),
    ("# RESUME FAILED", "resume_failed"),
    ("# RESET LOOP: not resuming", "reset_loop"),
    ("# FULL: not resuming", "full"),
    ("# LOW BATT: not resuming", "low_batt_noresume"),
    ("# FS ERROR: see README", "fs_error"),
    ("# LittleFS mount failed and partition is not blank. Not formatting automatically.", "fs_error"),
    ("# To erase ALL data: send 'FORMAT ERASE-ALL-SESSIONS' over USB.", None),
    ("# WFG logger fw 0.2.0 board FireBeetle2 ESP32-E + TEL0157 (fallback) device 1A2B3C4D", "boot"),
    ("# EVENT 3 marked", "event"),
    ("# EVENT 4 (NO POSITION)", "event"),
    ("# STOPPED - saved", "stopped"),
    ("# PENDING S000004.wfg", None),
    ("# DELETED S000004.wfg", None),
    ("# FAILED S000004.wfg", None),
    ("# TIMEOUT S000004.wfg", None),
    ("# Export mode OFF", "export_off"),
    ("# MODE: VEHICLE", "mode"),
    ("# FULL: export+delete first", "full"),
    ("# REC S000005.wfg WALK", "rec"),
    ("# FULL: cannot start", "full"),
    ("# START FAILED", "start_failed"),
    ("# Export mode ON", "export_on"),
    ("# formatting LittleFS (all sessions erased by owner request)", None),
    ("# STORAGE FULL - stopped", "full_stop"),
    ("# LOW BATTERY - stopped", "low_batt_stop"),
    ("# Export mode timed out", "export_timeout"),
]
LIT = r'"((?:[^"\\]|\\.)*)"'


def _firmware_templates():
    """The '#' lines in firmware 0.2.0's source: banner() arguments, the snprintf formats passed to banner(b), the
    '#' printf/println lines, and the delete results of wfg_proto.cpp (shown through banner())."""
    main = FIRMWARE / "src" / "main.cpp"
    proto = FIRMWARE / "lib" / "wfg_core" / "src" / "wfg_proto.cpp"
    if not main.exists():
        pytest.skip("firmware 0.2.0 source not available")
    src = main.read_text(encoding="utf-8")
    out = set()
    for m in re.finditer(r"\bbanner\(((?:[^()]|\([^()]*\))*)\)", src):
        for lit in re.findall(LIT, m.group(1)):
            out.add("# " + lit)
    for fmt in re.findall(r"snprintf\(b, sizeof\(b\), " + LIT, src):
        out.add("# " + fmt)
    for lit in re.findall(r"Serial\.(?:printf|println|print)\(" + LIT, src):
        if lit.startswith("#") and not lit.startswith("# %s"):
            out.add(lit.replace("\\n", ""))
    for fmt in re.findall(r"snprintf\(last_del_, sizeof\(last_del_\), " + LIT, proto.read_text(encoding="utf-8")):
        out.add("# " + fmt)
    return out


def _regex(tpl):
    parts = re.split(r"(%[-0-9.]*[sduXx])", tpl)
    rx = ""
    for p in parts:
        if not p.startswith("%"):
            rx += re.escape(p)
        elif p.endswith("s"):
            rx += ".*"
        elif p.endswith("d"):
            rx += r"-?\d+"
        elif p.endswith("u"):
            rx += r"\d+"
        else:
            rx += "[0-9A-Fa-f]+"
    return re.compile(rx + r"\Z")


def test_the_fixture_covers_every_hash_line_of_firmware_0_2_0():
    tpls = _firmware_templates()
    assert len(tpls) >= 30
    missing = [t for t in sorted(tpls) if not any(_regex(t).match(line) for line, _ in FIXTURE)]
    assert not missing, "firmware lines without a fixture entry: %s" % missing
    invented = [line for line, _ in FIXTURE if not any(_regex(t).match(line) for t in tpls)]
    assert not invented, "fixture lines the firmware never prints: %s" % invented


@pytest.mark.parametrize("line,code", FIXTURE)
def test_every_firmware_line_has_its_note_or_is_shown_unchanged(line, code):
    got, groups = notes.classify(line)
    assert got == code, (line, got)
    if code:
        assert notes.english(code, groups)


def test_every_note_has_page_text_in_both_languages():
    ko = json.loads((ROOT / "web" / "i18n" / "ko.json").read_text(encoding="utf-8"))
    en = json.loads((ROOT / "web" / "i18n" / "en.json").read_text(encoding="utf-8"))
    codes = {c for c, _ in notes.PATTERNS} | {"rom_boot", "download_mode", "basic", "vbat_unknown", "fs"}
    codes.discard("event")
    codes |= {"event_marked", "event_nopos"}
    missing = sorted(c for c in codes if "note." + c not in ko or "note." + c not in en)
    assert not missing, missing


def test_rom_boot_text_and_the_firmware_line_mark_a_restart():
    marks = [notes.classify(x)[0] for x in dbl.ROM_BOOT]
    assert "rom_boot" in marks
    assert all(m in ("rom_boot", None) for m in marks)
    assert notes.classify("# WFG logger fw 0.3.0 board X device 00000000")[0] == "boot"
    assert [notes.classify(x)[0] for x in dbl.DOWNLOAD_BOOT][-1] == "download_mode"


def test_rec_never_matches_recovered_and_events_are_told_apart():
    assert notes.classify("# RECOVERED 1 session")[0] == "recovered"
    assert notes.classify("# RECOVERED S000002.wfg records=10 torn_bytes=0 closed=1 unrecoverable=0")[0] == "recovered_detail"
    assert notes.classify("# REC S000002.wfg WALK")[0] == "rec"
    assert notes.classify("# REC S000002.wfg WALK and more")[0] is None
    a, b = notes.classify("# EVENT 7 marked"), notes.classify("# EVENT 8 (NO POSITION)")
    assert a == ("event", ("7", "marked")) and b == ("event", ("8", "(NO POSITION)"))
    assert "with position" in notes.english(*a) and "no position" in notes.english(*b)


def test_unknown_hash_line_is_shown_unchanged():
    assert notes.classify("# SOMETHING NEW 42") == (None, ())
    rec = Recorder()
    m = DeviceManager(rec, list_ports_fn=lambda **kw: [])
    m._on_unsolicited("# SOMETHING NEW 42")
    ev = rec.lines()[-1]
    assert ev["raw"] == "# SOMETHING NEW 42" and "note" not in ev and ev["cls"] == "hash"


def test_manager_marks_events_and_restarts_from_the_lines():
    rec = Recorder()
    m = DeviceManager(rec, list_ports_fn=lambda **kw: [])
    m._on_unsolicited("# REC S000009.wfg VEHICLE")
    assert m.status["state"] == "RECORDING" and m.status["session"] == "S000009.wfg" and m.status["mode"] == "VEHICLE"
    m._on_unsolicited("# EVENT 1 marked")
    assert m.last_event["located"] is True
    m._on_unsolicited("# EVENT 2 (NO POSITION)")
    assert m.last_event["located"] is False and m.events_seen == 2
    m._on_unsolicited("# STOPPED - saved")
    assert m.status["state"] == "IDLE" and m.last_session == "S000009.wfg"
    before = m.restarts
    m._on_unsolicited("rst:0x1 (POWERON_RESET),boot:0x13 (SPI_FAST_FLASH_BOOT)")
    m._on_unsolicited("# WFG logger fw 0.2.0 board B device 1A2B3C4D")
    assert m.restarts == before + 1
    assert "restart" in rec.codes()
    for line, code in FIXTURE:
        m._on_unsolicited(line)
        ev = rec.lines()[-1] if rec.lines()[-1].get("raw") == line else next(e for e in reversed(rec.lines()) if e.get("raw") == line)
        assert ev["raw"] == line and ev.get("note") == code, (line, ev)


# ------------------------------------------------------------------ the link: what completes a command
class FakeSerial:
    def __init__(self):
        self.buf = bytearray()
        self.cond = threading.Condition()
        self.closed = False
        self.written = []

    def feed(self, text):
        with self.cond:
            self.buf += text.encode()
            self.cond.notify_all()

    def read(self, n):
        with self.cond:
            if not self.buf and not self.closed:
                self.cond.wait(0.05)
            if self.closed:
                raise OSError("closed")
            out = bytes(self.buf[:n])
            del self.buf[:n]
            return out

    def write(self, data):
        self.written.append(data.decode())
        return len(data)

    def flush(self):
        pass

    def close(self):
        with self.cond:
            self.closed = True
            self.cond.notify_all()


@pytest.fixture
def fake_link(tmp_path):
    ser = FakeSerial()
    seen = []
    lk = linkmod.Link("FAKE", listener=lambda kind, text, p: seen.append((kind, text)), factory=lambda port, m: ser,
                      log_dir=tmp_path)
    lk.open()
    yield lk, ser, seen
    lk.close()


def test_lines_that_are_not_the_reply_complete_nothing(fake_link):
    lk, ser, seen = fake_link
    out = {}
    th = threading.Thread(target=lambda: out.update(lines=lk.command("STATUS", timeout=5.0)))
    th.start()
    assert wait_for(lambda: ser.written)
    for junk in ("ets Jul 29 2019 12:21:46\r\n", "rst:0x1 (POWERON_RESET),boot:0x13 (SPI_FAST_FLASH_BOOT)\r\n",
                 "OK DELETE S000001.wfg\n", "# EVENT 1 marked\n", "OK LIST 0\n", "ERR LIVE unknown-command\n",
                 "SESS S000001.wfg 48 1 WALK 1 USER_STOP 0 abc\n"):
        ser.feed(junk)
    time.sleep(0.3)
    assert th.is_alive(), "a line that is not the reply completed the command"
    ser.feed("OK STATUS state=IDLE mode=WALK session=- seq=0 free=2500000 total=2555904\r\n")
    th.join(3)
    assert out["lines"] == ["OK STATUS state=IDLE mode=WALK session=- seq=0 free=2500000 total=2555904"]
    unsolicited = [t for k, t in seen if k == "line"]
    assert "OK DELETE S000001.wfg" in unsolicited and "# EVENT 1 marked" in unsolicited and "OK LIST 0" in unsolicited
    assert any(t.startswith("rst:0x1") for t in unsolicited)


def test_refusals_and_storage_errors_complete_their_command(fake_link):
    lk, ser, _ = fake_link
    for cmd, reply in (("DUMP S000001.wfg", "ERR DUMP  recording-active (stop recording first)"),
                       ("LIST", "ERR LIST recording-active (stop recording first)"),
                       ("CHECK S000001.wfg", "ERR CHECK recording-active (stop recording first)"),
                       ("HELLO", "ERR FS not-mounted"), ("VBAT", "ERR VBAT unknown-command")):
        th = threading.Timer(0.1, lambda r=reply: ser.feed(r + "\r\n"))
        th.start()
        assert lk.command(cmd, timeout=3.0) == [reply]


def test_no_reply_times_out_and_the_link_stays_usable(fake_link):
    lk, ser, _ = fake_link
    with pytest.raises(TimeoutError):
        lk.command("HELLO", timeout=0.3)
    threading.Timer(0.1, lambda: ser.feed("OK STATUS state=IDLE\n")).start()
    assert lk.command("STATUS", timeout=3.0) == ["OK STATUS state=IDLE"]


def test_hello_with_the_quoted_board_name():
    kv = linkmod.parse_kv('OK HELLO fw=0.2.0 board="FireBeetle2 ESP32-E + TEL0157 (fallback)" device=1A2B3C4D '
                          'fmt=2 recsize=48 state=IDLE')
    assert kv == {"fw": "0.2.0", "board": "FireBeetle2 ESP32-E + TEL0157 (fallback)", "device": "1A2B3C4D",
                  "fmt": "2", "recsize": "48", "state": "IDLE"}


def test_every_line_goes_to_the_device_log(fake_link, tmp_path):
    lk, ser, _ = fake_link
    threading.Timer(0.1, lambda: ser.feed("OK STATUS state=IDLE\n")).start()
    lk.command("STATUS", timeout=3.0)
    log = next(tmp_path.glob("device_*.log")).read_text(encoding="utf-8")
    assert ">  STATUS" in log and "<  OK STATUS state=IDLE" in log
