"""Options (spec test 18): the Wi-Fi pull against a local server with the endpoints of firmware web_export.cpp, and
the battery calibration form's exact commands."""
import hashlib
import json
import threading
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app import config, library
from app.device import double as dbl
from app.device import wifi
from app.device.manager import DOUBLE_PORT, DeviceManager
from conftest import FAST, Recorder, only_extra_ports, wait_for
from fakes import logger_double as fx


class Device:
    """What the logger's export mode serves (web_export.cpp: hStatus, hList, hSha, hDownload)."""

    def __init__(self):
        self.sessions = {"S000001.wfg": fx.outdoor_fix(1), "S000002.wfg": fx.indoor_filler(2)}
        self.active = "S000003.wfg"
        self.sessions[self.active] = fx.indoor_filler(3)
        self.wrong_header = set()
        self.wrong_api = set()
        self.requests = []


def make_handler(dev):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, code, obj):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            dev.requests.append(("POST", self.path))
            self._json(404, {"error": "not in this test"})

        def do_GET(self):
            dev.requests.append(("GET", self.path))
            u = urllib.parse.urlparse(self.path)
            q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
            name = q.get("name", "")
            if u.path == "/api/status":
                return self._json(200, {"device": "1A2B3C4D", "board": "FireBeetle2 ESP32-E + TEL0157 (fallback)",
                                        "fw": "0.2.0", "state": "RECORDING", "used": 40960, "total": 2555904,
                                        "last_delete": ""})
            if u.path == "/api/list":
                out = []
                for n, d in sorted(dev.sessions.items()):
                    out.append({"name": n, "session_id": "WFG-1A2B3C4D-%06d" % int(n[1:7]), "mode": "WALK",
                                "size": len(d), "records": len(d) // 48, "closed": n != dev.active,
                                "end_reason": "" if n == dev.active else "USER_STOP", "exported": False, "ok_sha": "",
                                "active": n == dev.active, "start_reason": "OWNER_BUTTON"})
                return self._json(200, out)
            if name == dev.active or name not in dev.sessions:
                return self._json(400, {"error": "bad-or-active-session"})
            data = dev.sessions[name]
            sha = hashlib.sha256(data).hexdigest()
            if u.path == "/api/sha":
                return self._json(200, {"sha256": "0" * 64 if name in dev.wrong_api else sha, "size": len(data)})
            if u.path == "/dl":
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("X-WFG-SHA256", "f" * 64 if name in dev.wrong_header else sha)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            self._json(404, {"error": "not-found"})
    return H


@pytest.fixture
def wifi_dev(monkeypatch):
    dev = Device()
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(dev))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(wifi, "BASE", "http://127.0.0.1:%d" % srv.server_address[1])
    urls = []
    real_open = urllib.request.OpenerDirector.open

    def spy(self, fullurl, *a, **k):
        urls.append(fullurl if isinstance(fullurl, str) else fullurl.full_url)
        return real_open(self, fullurl, *a, **k)
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", spy)
    yield dev, urls
    srv.shutdown()


def test_the_wifi_address_is_the_devices_access_point():
    import importlib
    fresh = importlib.reload(wifi)                     # the module's own value, not a test's
    assert fresh.BASE == "http://192.168.4.1"


def test_wifi_pull_lists_downloads_checks_and_saves(tmp_root, wifi_dev):
    dev, urls = wifi_dev
    m = DeviceManager(Recorder(), list_ports_fn=lambda **kw: [], timing=FAST)
    st = m.wifi_status()
    assert st["ok"] and st["status"]["device"] == "1A2B3C4D"
    items = m.wifi_list()["sessions"]
    assert [s["name"] for s in items] == ["S000001.wfg", "S000002.wfg"]          # the active one is not offered
    out = m.wifi_pull("S000001.wfg")
    assert out["ok"] and out["file"].startswith("real/WFG-1A2B3C4D-000001_WALK")
    p = config.SESSIONS / out["file"]
    assert p.read_bytes() == dev.sessions["S000001.wfg"]
    assert library.entry_for_file(out["file"])["key"] == 5
    rows = {r["id"]: r for r in out["result"]["rows"]}
    assert rows["file"]["mark"] == "ok" and rows["position"]["variant"] == "fix" and out["result"]["via"] == "wifi"
    # nothing went anywhere but the device's address, and nothing was posted
    assert urls and all(u.startswith(wifi.BASE + "/") for u in urls)
    assert all(method == "GET" for method, _ in dev.requests)
    assert {urllib.parse.urlparse(path).path for _, path in dev.requests} <= {"/api/status", "/api/list", "/api/sha", "/dl"}


@pytest.mark.parametrize("where", ["header", "api"])
def test_a_wrong_sha256_is_refused(tmp_root, wifi_dev, where):
    dev, _ = wifi_dev
    (dev.wrong_header if where == "header" else dev.wrong_api).add("S000002.wfg")
    m = DeviceManager(Recorder(), list_ports_fn=lambda **kw: [], timing=FAST)
    with pytest.raises(wifi.WifiError, match="SHA-256 mismatch"):
        m.wifi_pull("S000002.wfg")
    assert not list(config.REAL_DIR.glob("*.wfg*"))          # nothing saved, not even a partial file
    assert m.busy is None


def test_an_active_or_bad_name_is_refused(tmp_root, wifi_dev):
    dev, _ = wifi_dev
    m = DeviceManager(Recorder(), list_ports_fn=lambda **kw: [], timing=FAST)
    with pytest.raises(wifi.WifiError):
        m.wifi_pull("S000003.wfg")                     # still recording: the device answers 400
    n = len(dev.requests)
    for bad in ("../../etc/passwd", "S1.wfg", "S000001.csv", None):
        with pytest.raises(ValueError):
            m.wifi_pull(bad)
    assert len(dev.requests) == n                      # refused before any request


def test_no_device_on_the_network_is_reported(tmp_root, monkeypatch):
    monkeypatch.setattr(wifi, "BASE", "http://127.0.0.1:9")    # nothing listens there
    m = DeviceManager(Recorder(), list_ports_fn=lambda **kw: [], timing=FAST)
    st = m.wifi_status()
    assert st["ok"] is False and st["error"]


# ------------------------------------------------------------------ battery calibration
@pytest.fixture
def cal_rig(tmp_root):
    d = dbl.LoggerDouble()
    m = DeviceManager(Recorder(), double_obj=d, list_ports_fn=only_extra_ports, timing=FAST)
    m.start()
    m.connect(DOUBLE_PORT)
    assert wait_for(lambda: m.conn["state"] == "connected" and m.busy is None, 8)
    yield m, d
    m.shutdown()


def test_the_calibration_form_sends_exactly_calvbat(cal_rig):
    m, d = cal_rig
    ok = m.calibrate(mv="4100")
    assert ok["ok"] and ok["reply"].startswith("OK CALVBAT cal=0.99") and "vbat_mv=" in ok["reply"]
    bad = m.calibrate(mv=5000)
    assert not bad["ok"] and bad["reply"] == "ERR CALVBAT out-of-range (expect 3000-4300 mV and a correction within 20 %)"
    reset = m.calibrate(reset=True)
    assert reset["ok"] and reset["reply"] == "OK CALVBAT cal=1.000 vbat_mv=4122"
    with pytest.raises(ValueError, match="cal.bad_input"):
        m.calibrate(mv="4.1 V")
    with pytest.raises(ValueError, match="cal.bad_input"):
        m.calibrate(mv="")
    sent = [x for x in d.received if x.startswith("CALVBAT")]
    assert sent == ["CALVBAT 4100", "CALVBAT 5000", "CALVBAT RESET"]
    assert m.vbat and m.vbat["cal"] == "1.000"         # the VBAT read after the reply shows the stored value
