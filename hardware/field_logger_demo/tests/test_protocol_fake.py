"""Protocol (spec test 14) against the real host fake device of firmware 0.2.0 on a pseudo-terminal, and the shape of
the test double's replies compared with it (section 3C, "Testing without the board")."""
import hashlib
import os
import select
import re
import shutil
import time

import pytest

from app.device import double as dbl
from app.device.manager import DeviceManager
from app.vendor import usb_export as ux
from conftest import FAST, SAMPLES, Recorder, only_extra_ports, wait_for
from fakes.ptybridge import PtyDevice

SAMPLE_WFG = sorted(SAMPLES.glob("*.wfg")) if SAMPLES.exists() else []


@pytest.fixture
def fake(fake_device_bin, tmp_path):
    if not SAMPLE_WFG:
        pytest.skip("sample sessions not available")
    devdir = tmp_path / "device_fs"
    devdir.mkdir()
    names = {}
    for k, p in enumerate(SAMPLE_WFG, 1):
        name = "S%06d.wfg" % k                 # the host fake device lists only S??????.wfg names
        shutil.copy(p, devdir / name)
        names[name] = p.read_bytes()
    dev = PtyDevice(fake_device_bin, devdir)
    time.sleep(0.2)
    yield dev, names
    dev.close()


def _port(dev):
    return {"device": dev.port, "description": "USB Serial", "vid": 0x1A86, "pid": 0x7523, "vidpid": "1A86:7523",
            "serial": None, "chip": "CH340", "usb": True, "likely": True, "simulated": False}


def _manager(rec, dev, **timing):
    port = _port(dev)
    m = DeviceManager(rec, list_ports_fn=lambda **kw: only_extra_ports(extra_ports=[port]), timing=dict(FAST, **timing))
    m._scan()
    return m


def _connected(m, timeout=10):
    return wait_for(lambda: m.conn["state"] == "connected" and m.busy is None, timeout)


def test_handshake_status_list_check_and_dump(fake, tmp_root):
    dev, names = fake
    rec = Recorder()
    m = _manager(rec, dev)
    try:
        m.connect(dev.port)
        assert _connected(m), m.conn
        assert m.hello["board"] == "HOST-FAKE-DEVICE" and m.hello["device"] == "1A2B3C4D"
        assert m.hello["fmt"] == "2" and m.hello["recsize"] == "48" and not m.format_error
        assert m.mode == "basic"                                   # LIVE ON -> ERR LIVE unknown-command
        assert m.vbat_unknown and m.vbat is None                   # VBAT lives in main.cpp, not in the fake device
        notes = {e.get("note") for e in rec.lines() if e.get("raw", "").startswith("ERR")}
        assert {"basic", "vbat_unknown"} <= notes
        assert m.restart_on_open is False
        st = m.cmd_status(visible=True)
        assert st["state"] == "IDLE"
        items = m.cmd_list()
        assert [i["name"] for i in items] == sorted(names)
        for it in items:
            assert it["sha256"] == hashlib.sha256(names[it["name"]]).hexdigest() and it["size"] == len(names[it["name"]])
            lines = m._cmd("CHECK " + it["name"], timeout=5)
            assert lines[-1].startswith("OK CHECK %s " % it["name"])
            data, size, sha = m._dump(it["name"])
            assert data == names[it["name"]] and size == len(data) and sha == hashlib.sha256(data).hexdigest()
        # the page never gets a position from a DUMP: FIX and EVENT records are masked in the stream
        rl = [e for e in rec.lines() if e.get("rec")]
        assert rl and all(("x" * 16) in e["raw"] for e in rl if e["rec"]["type"] in ("FIX", "EVENT"))
        assert any(e["rec"]["type"] == "FIX" for e in rl)
        app_bytes = {n: m._dump(n)[0] for n in names}
    finally:
        m.disconnect()
        m.shutdown()
    # Device.dump() of usb_export.py over the same port returns the same bytes
    d = ux.Device(dev.port, timeout=3)
    try:
        for n in names:
            data, size, sha = d.dump(n)
            assert data == app_bytes[n]
    finally:
        d.s.close()


def test_no_reply_is_reported_and_the_app_keeps_running(fake, tmp_root):
    dev, _ = fake
    rec = Recorder()
    m = _manager(rec, dev, hello_timeout=0.4)
    dev.pause()
    try:
        m.connect(dev.port)
        assert wait_for(lambda: m.conn["state"] == "disconnected" and m.conn["error"] == "noreply", 10), m.conn
        assert "noreply" in rec.codes()
        dev.resume()
        time.sleep(0.5)                       # the stale replies to the two HELLOs arrive; nobody waits for them
        m.connect(dev.port)
        assert _connected(m), m.conn
    finally:
        dev.resume()
        m.shutdown()


def test_closing_the_pseudo_terminal_shows_the_banner_without_a_crash(fake, tmp_root):
    dev, _ = fake
    rec = Recorder()
    m = _manager(rec, dev)
    m.start()
    try:
        m.connect(dev.port)
        assert _connected(m)
        dev.unplug()
        assert wait_for(lambda: m.conn["state"] == "lost", 5), m.conn
        assert wait_for(lambda: "lost" in rec.codes(), 5)
        assert m.link is None and m.alive
        time.sleep(0.5)                        # the scanner and the poller keep running
        assert m.snapshot()["conn"]["state"] == "lost"
    finally:
        m.shutdown()


# ------------------------------------------------------------------ the double answers like the real fake device
SHAPES = {
    "HELLO": [r'OK HELLO fw=\S+ board="[^"]*" device=[0-9A-F]{8} fmt=2 recsize=48 state=(IDLE|RECORDING|FULL|ERROR)'],
    "STATUS": [r"OK STATUS state=\w+ mode=\w+ session=\S+ seq=\d+ free=\d+ total=\d+"],
    "LIST": [r"SESS S\d{6}\.wfg \d+ \d+ \w+ [01] \S+ [01] [0-9a-f]{64}", r"OK LIST \d+"],
    "CHECK S000001.wfg": [r"OK CHECK S000001\.wfg \w+ rec=\d+ crc_err=\d+ seq_err=\d+ trailing=\d+ fix=\d+ nofix=\d+ "
                          r"events=\d+ status=\d+"],
    "CHECK S999999.wfg": [r"OK CHECK S999999\.wfg MISSING rec=0 crc_err=0 seq_err=0 trailing=0 fix=0 nofix=0 events=0 "
                          r"status=0"],
    "DUMP S000001.wfg": [r"BEGIN S000001\.wfg \d+ [0-9a-f]{64}", r"R \d+ [0-9a-f]{96}", r"OK DUMP S000001\.wfg \d+"],
    "DUMP S999999.wfg": [r"ERR DUMP not-found"],
    "LIVE ON": [r"ERR LIVE unknown-command"],
}


def _shape_ok(lines, pats):
    """Every line matches one of the patterns, the first and the last match the first and the last pattern."""
    if not lines:
        return False
    rx = [re.compile(p + r"\Z") for p in pats]
    return (all(any(r.match(ln) for r in rx) for ln in lines) and rx[0].match(lines[0]) is not None
            and rx[-1].match(lines[-1]) is not None)


def _ask_fake(dev, cmd):
    """Send one command straight into the device's input (as the host would) and collect the complete reply lines."""
    with dev.lock:
        start = len(dev.to_app)
    dev.inject(cmd)
    end = time.monotonic() + 5
    while time.monotonic() < end:
        # This helper is the host consumer. Drain the app side just as pyserial
        # would, so a large DUMP cannot fill the PTY and stall the bridge.
        ready, _, _ = select.select([dev.s_app], [], [], 0)
        if ready:
            os.read(dev.s_app, 65536)
        with dev.lock:
            text = bytes(dev.to_app[start:]).decode("utf-8", "replace").replace("\r", "")
        complete = text[:text.rfind("\n") + 1] if "\n" in text else ""
        got = [x for x in complete.split("\n") if x and not x.startswith("#")]
        if got and (got[-1].startswith("OK ") or got[-1].startswith("ERR")):
            return got
        time.sleep(0.05)
    return []


def _ask_double(port, cmd):
    port.buf.clear()
    port.write((cmd + "\n").encode())
    text = bytes(port.buf).decode()
    return [x for x in text.replace("\r", "").split("\n") if x and not x.startswith("#")]


def test_the_double_answers_with_the_same_shape(fake):
    dev, names = fake
    d = dbl.LoggerDouble(autostart=False, sessions=dict(names))
    port = d.open_port("default")
    try:
        for cmd, pats in SHAPES.items():
            a, b = _ask_fake(dev, cmd), _ask_double(port, cmd)
            assert _shape_ok(a, pats), ("fake device", cmd, a[:3])
            assert _shape_ok(b, pats), ("double", cmd, b[:3])
            if cmd.startswith("DUMP S000001"):
                assert a[0] == b[0] and a[-1] == b[-1] and len(a) == len(b)     # same bytes, same lines
            if cmd.startswith("CHECK S000001") or cmd == "LIST":
                assert a == b
    finally:
        d.close()
