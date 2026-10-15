"""Port safety (spec test 13): listing never opens a port; the app starts and runs with no device and with only other
ports; it opens a port only when asked, or by itself after an unplug when the board's profile allows it."""
import time

import pytest
import serial
from serial.tools import list_ports_common

from app.device import double as dbl
from app.device import manager as mgrmod
from app.device import ports as portsmod
from app.device import profiles
from conftest import FAST, Recorder, only_extra_ports, wait_for


def _info(device, vid=None, pid=None, serial_number=None, description="n/a"):
    i = list_ports_common.ListPortInfo(device, skip_link_detection=True)
    i.vid, i.pid, i.serial_number, i.description = vid, pid, serial_number, description
    return i


BT = _info("/dev/cu.Bluetooth-Incoming-Port")
CH340 = _info("/dev/cu.usbserial-1420", 0x1A86, 0x7523, None, "USB Serial")
CH9102 = _info("/dev/cu.wchusbserial54790123451", 0x1A86, 0x55D4, "5479012345", "USB Single Serial")
CP210X = _info("/dev/cu.SLAB_USBtoUART", 0x10C4, 0xEA60, "0001", "CP2102 USB to UART Bridge Controller")
NAMED = _info("/dev/cu.usbserial-A10KXYZ")


@pytest.fixture
def no_open(monkeypatch):
    """Every attempt to open a serial port fails the test (and is recorded)."""
    opened = []

    def refuse(self, *a, **k):
        opened.append(self.port)
        raise serial.SerialException("tests: opening a port is not allowed here")
    monkeypatch.setattr(serial.Serial, "open", refuse)
    return opened


@pytest.mark.parametrize("listing", [[], [BT], [BT, CP210X], [BT, CH340], [CH9102, NAMED, BT]],
                         ids=["no ports", "only bluetooth", "other usb", "ch340", "two loggers"])
def test_starting_and_listing_never_opens_a_port(no_open, monkeypatch, tmp_root, listing):
    monkeypatch.setattr("serial.tools.list_ports.comports", lambda *a, **k: list(listing))
    monkeypatch.setitem(mgrmod.DEFAULT_TIMING, "scan_s", 0.05)
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setitem(main.ARGS, "double", False)
    monkeypatch.setitem(main.ARGS, "quiet", True)
    with TestClient(main.app) as c:
        time.sleep(0.4)                               # several scans
        got = c.get("/api/device/ports").json()["ports"]
        st = c.get("/api/device/state").json()
        assert c.get("/").status_code == 200 and c.get("/api/library").status_code == 200
        with c.websocket_connect("/ws") as ws:
            first = ws.receive_json()
            assert first["type"] == "snapshot" and first["state"]["conn"]["state"] == "disconnected"
    assert not no_open, no_open
    assert st["conn"]["state"] == "disconnected"
    assert [p["device"] for p in got] == [p["device"] for p in portsmod.list_ports()]
    likely = {p["device"] for p in got if p["likely"]}
    assert likely == {p.device for p in listing if p.vid == 0x1A86 or "usbserial" in p.device or "wchusbserial" in p.device}
    for p in got:                                     # candidates first, then other USB ports, then the rest
        if p["chip"]:
            assert p["chip"] == {0x7523: "CH340", 0x55D4: "CH9102"}[p["pid"]]


def test_port_identity_is_stable_and_candidates_are_remembered(tmp_root, monkeypatch):
    monkeypatch.setattr("serial.tools.list_ports.comports", lambda *a, **k: [CP210X, CH340])
    got = portsmod.list_ports()
    cp = next(p for p in got if p["device"] == CP210X.device)
    assert not cp["likely"] and cp["usb"]
    assert next(p for p in got if p["device"] == CH340.device)["id"] == "1A86:7523:/dev/cu.usbserial-1420"
    assert cp["id"] == "10C4:EA60:0001"
    again = portsmod.list_ports(extra_candidates=("10C4:EA60",))
    assert next(p for p in again if p["device"] == CP210X.device)["likely"]


def test_a_failed_open_is_reported_and_the_app_keeps_running(no_open, tmp_root, monkeypatch):
    monkeypatch.setattr("serial.tools.list_ports.comports", lambda *a, **k: [CH340])
    rec = Recorder()
    m = mgrmod.DeviceManager(rec, timing=FAST)
    m.start()
    try:
        m.connect(CH340.device)                       # the owner asked: the app tries, and the open fails
        assert wait_for(lambda: m.conn["state"] == "disconnected" and m.conn["error"] == "open_failed", 5)
        assert no_open == [CH340.device] and "open_failed" in rec.codes()
        time.sleep(0.3)
        assert m.alive and m.ports()
    finally:
        m.shutdown()


def _double_rig(tmp_root, **dkw):
    d = dbl.LoggerDouble(**dkw)
    rec = Recorder()
    m = mgrmod.DeviceManager(rec, double_obj=d, list_ports_fn=only_extra_ports, timing=FAST)
    m.start()
    return m, d, rec


def test_the_double_is_opened_only_after_connect(tmp_root):
    m, d, rec = _double_rig(tmp_root)
    try:
        time.sleep(0.5)
        assert d.port is None and m.conn["state"] == "disconnected"     # listed, never opened by itself
        assert any(p["simulated"] for p in m.ports())
        m.connect(mgrmod.DOUBLE_PORT)
        assert wait_for(lambda: m.conn["state"] == "connected", 5)
        assert d.port is not None and m.conn["simulated"]
    finally:
        m.shutdown()


@pytest.mark.parametrize("allowed", [False, True], ids=["profile says no", "profile says yes"])
def test_reconnects_after_an_unplug_only_when_the_profile_allows(tmp_root, allowed):
    m, d, rec = _double_rig(tmp_root)
    try:
        m.connect(mgrmod.DOUBLE_PORT)
        assert wait_for(lambda: m.conn["state"] == "connected" and m.busy is None, 5)
        profiles.update(m.device_id(), reconnect_ok=allowed, open_method="lines_low")
        d.unplug()
        assert wait_for(lambda: m.conn["state"] == "lost", 5)
        d.replug()
        if allowed:
            assert wait_for(lambda: m.conn["state"] == "connected", 5), m.conn
            assert d.port.method == "lines_low"             # the profile's safe open method
            assert "reconnect" in rec.codes()
        else:
            time.sleep(0.8)
            assert m.conn["state"] == "lost" and d.port is None
            assert "reconnect" not in rec.codes()
    finally:
        m.shutdown()
