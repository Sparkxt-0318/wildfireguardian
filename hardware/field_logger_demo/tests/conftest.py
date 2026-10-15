"""Shared test setup. Tests never write into the demo's own sessions/, devices/, logs/ or out/: every test that saves
anything gets a temporary copy of those folders (fixture `tmp_root`)."""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import pytest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import config  # noqa: E402

# The key of the privacy circles (app/privacy.py) lives in a temporary folder during the tests, never in sessions/.
config.ZONE_SECRET_FILE = Path(tempfile.mkdtemp(prefix="wfg_secret_")) / "zone_secret"

PKG = ROOT.parent
FIRMWARE = Path(os.environ.get("WFG_FIRMWARE_DIR", PKG / "firmware"))
SAMPLES = Path(os.environ.get("WFG_SAMPLES_DIR", PKG / "phone_export" / "samples"))


@pytest.fixture
def tmp_root(tmp_path, monkeypatch):
    """Point every writable folder of the app at a temporary copy (the SIM library and map data are copied)."""
    sessions = tmp_path / "sessions"
    shutil.copytree(ROOT / "sessions" / "sim", sessions / "sim",
                    ignore=shutil.ignore_patterns("device_double"))
    shutil.copy(ROOT / "sessions" / "sessions.json", sessions / "sessions.json")
    for name, value in {"SESSIONS": sessions, "SIM_DIR": sessions / "sim", "REAL_DIR": sessions / "real",
                        "DEVICE_TESTS_DIR": sessions / "real" / "device_tests",
                        "LIBRARY_FILE": sessions / "sessions.json", "PRIVACY_FILE": sessions / "privacy.json",
                        "OUT": tmp_path / "out", "DEVICES": tmp_path / "devices", "LOGS": tmp_path / "logs"}.items():
        monkeypatch.setattr(config, name, value)
    from app import library
    library._cache.clear()
    return tmp_path


class Recorder:
    """Collects what the device manager emits (the page's WebSocket events)."""

    def __init__(self):
        self.events = []

    def __call__(self, ev):
        self.events.append(ev)

    def lines(self, cls=None):
        return [e for e in self.events if e.get("type") == "line" and (cls is None or e.get("cls") == cls)]

    def codes(self):
        return [e.get("code") for e in self.lines() if e.get("code")]

    def raws(self):
        return [e.get("raw") for e in self.lines() if e.get("raw")]


@pytest.fixture
def recorder():
    return Recorder()


FAST = {"scan_s": 0.1, "watch_s": 0.3, "boot_wait_s": 1.5, "hello_timeout": 1.0, "cmd_timeout": 1.5,
        "dump_inactivity": 2.0, "dump_begin": 3.0, "status_fast": 0.2, "status_slow": 0.4, "vbat_s": 1.0,
        "cc_close_wait": 0.3, "cc_watch": 0.5, "cc_restart_wait": 0.6, "cc_unplug_timeout": 10.0,
        "cc_rec_timeout": 10.0, "cc_replug_settle": 0.1}


def wait_for(fn, timeout=10.0, step=0.05):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        v = fn()
        if v:
            return v
        time.sleep(step)
    return None


def only_extra_ports(extra_candidates=(), extra_ports=()):
    """Port listing for tests: just the simulated port(s), nothing from the machine."""
    from app.device import ports
    out = [dict(p) for p in extra_ports]
    for p in out:
        p["id"] = ports.identity(p)
    return out


# ------------------------------------------------------------------ the real host fake devices (firmware 0.2.0, 0.3.0)
FIRMWARE_LIVE = Path(os.environ.get("WFG_FIRMWARE_LIVE_DIR", PKG / "firmware_v0_3_0_live"))


def _build_fake(fw_dir, out_dir):
    """Compile test/host/fake_device.cpp with the g++ line of run_host_tests.sh (same warnings, no sanitizers)."""
    src = fw_dir / "test" / "host" / "fake_device.cpp"
    gxx = shutil.which(os.environ.get("CXX", "g++"))
    if not src.exists() or not gxx:
        pytest.skip("host fake device not available (firmware folder or g++ missing)")
    out = out_dir / "fake_device"
    core = sorted(str(p) for p in (fw_dir / "lib" / "wfg_core" / "src").glob("*.cpp"))
    cmd = [gxx, "-std=c++17", "-O1", "-Wall", "-Wextra", "-Wno-format-truncation",
           "-I" + str(fw_dir / "lib" / "wfg_core" / "src"), str(src)] + core + ["-o", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip("could not build the host fake device: " + r.stderr[-400:])
    return str(out)


@pytest.fixture(scope="session")
def fake_device_bin(tmp_path_factory):
    return _build_fake(FIRMWARE, tmp_path_factory.mktemp("fake020"))


@pytest.fixture(scope="session")
def fake_device_live_bin(tmp_path_factory):
    return _build_fake(FIRMWARE_LIVE, tmp_path_factory.mktemp("fake030"))


# ------------------------------------------------------------------ a server on a free port, from a temporary copy
def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _start_server(tmp_path_factory, *flags):
    """The app on a free port, run from a temporary copy (app, web, map data, the SIM library), as the owner runs it."""
    work = tmp_path_factory.mktemp("srv")
    for d in ("app", "web", "mapdata"):
        shutil.copytree(ROOT / d, work / d, ignore=shutil.ignore_patterns("__pycache__"))
    (work / "sessions").mkdir()
    shutil.copytree(ROOT / "sessions" / "sim", work / "sessions" / "sim", ignore=shutil.ignore_patterns("device_double"))
    shutil.copy(ROOT / "sessions" / "sessions.json", work / "sessions" / "sessions.json")
    from app import privacy
    privacy.secret()                     # the server draws the same circles as the tests compute
    shutil.copy(config.ZONE_SECRET_FILE, work / "sessions" / "zone_secret")
    port = _free_port()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    # The synthetic browser server must never enumerate or open owner hardware.
    bootstrap = ("import runpy, serial; from serial.tools import list_ports; "
                 "list_ports.comports = lambda *a, **k: []; "
                 "serial.Serial = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('physical serial disabled in tests')); "
                 "runpy.run_module('app.main', run_name='__main__')")
    proc = subprocess.Popen([sys.executable, "-c", bootstrap, "--port", str(port), "--quiet"] + list(flags),
                            cwd=work, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    base = "http://127.0.0.1:%d" % port
    if not wait_for(lambda: _ping(base), timeout=20):
        proc.kill()
        pytest.fail("server did not start: " + proc.stderr.read().decode()[-800:])
    return proc, {"base": base, "root": work, "port": port}


def _stop_server(proc):
    proc.terminate()
    try:
        proc.wait(5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    """With the simulated logger of firmware 0.2.0 (basic mode)."""
    proc, info = _start_server(tmp_path_factory, "--dev-device-double")
    yield info
    _stop_server(proc)


@pytest.fixture(scope="module")
def server_live(tmp_path_factory):
    """With the simulated logger of firmware 0.3.0 (LIVE lines)."""
    proc, info = _start_server(tmp_path_factory, "--dev-double-live")
    yield info
    _stop_server(proc)


def _ping(base):
    try:
        return urllib.request.urlopen(base + "/api/health", timeout=1).status == 200
    except OSError:
        return False
