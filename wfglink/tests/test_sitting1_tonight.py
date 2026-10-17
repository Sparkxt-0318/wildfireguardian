"""Exercise the interactive checklist with stand-ins, never a real camera or network server."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

import pytest

from wfglink import PROJECT_ROOT


@pytest.fixture
def sitting(tmp_path):
    root = tmp_path / "wfglink"
    (root / "scripts").mkdir(parents=True)
    (root / ".venv" / "bin").mkdir(parents=True)
    (root / "configs").mkdir()
    shutil.copy2(PROJECT_ROOT / "scripts" / "sitting1_tonight.sh", root / "scripts")
    (root / ".venv" / "bin" / "python").symlink_to(sys.executable)
    setup = root / "scripts" / "setup_mac.sh"
    setup.write_text('#!/bin/bash\nprintf "setup stand-in\\n"\nexit "${SITTING_SETUP_EXIT:-0}"\n')
    setup.chmod(0o755)
    fake = tmp_path / "standins" / "wfglink"
    (fake / "io").mkdir(parents=True)
    (fake / "__init__.py").write_text("")
    (fake / "io" / "__init__.py").write_text("")
    (fake / "io" / "camera.py").write_text('''
import os
def list_cameras():
    cams = [{"name": "USB PC CAMERA", "kind": "usb", "usable": True}]
    if not os.environ.get("SITTING_NO_BUILTIN"):
        cams += [{"name": "MacBook Camera", "kind": "builtin", "usable": True}]
    return cams
''')
    (fake / "__main__.py").write_text('''
import json, os, pathlib, sys
cmd = sys.argv[1]
if cmd == "doctor":
    print("camera normal settings OK")
elif cmd == "cameras":
    cfg = json.loads(pathlib.Path(sys.argv[sys.argv.index("--config") + 1]).read_text())
    assert cfg["camera"]["name"] == "MacBook Camera"
    print("MacBook Camera builtin; camera permission authorized; opened OK")
elif cmd == "live":
    if os.environ.get("SITTING_FIRE_FAIL") and "--ember" not in sys.argv:
        print("deliberate fire failure", file=sys.stderr)
        raise SystemExit(17)
    if "--ember" in sys.argv:
        cfg = json.loads(pathlib.Path(sys.argv[sys.argv.index("--config") + 1]).read_text())
        assert cfg["camera"]["name"] == "MacBook Camera"
        assert cfg["camera"]["focal_px"] is None
        assert cfg["camera"]["mask"] == []
        assert cfg["booth"]["ember_page_url"].startswith("http://192.168.")
    p = pathlib.Path(sys.argv[sys.argv.index("--report") + 1])
    p.write_text(json.dumps({"frames": 120, "paints": 120,
                            "errors": ["deliberate worker error"] if os.environ.get("SITTING_APP_ERROR") else [],
                            "states": {"playing": 120}, "camera_state": os.environ.get("SITTING_CAMERA_STATE", "ok")}))
elif cmd == "calibrate":
    p = pathlib.Path(sys.argv[sys.argv.index("--out") + 1])
    cfg = json.loads(p.read_text())
    cfg["camera"]["focal_px"] = 999.0
    cfg["ember"]["calibration"] = {"stable": True, "camera": "MacBook Camera"}
    p.write_text(json.dumps(cfg))
    print("stable calibration written to " + str(p))
else:
    raise SystemExit("unexpected stand-in command: " + cmd)
''')
    (root / "scripts" / "serve_page.py").write_text('''
import os, pathlib, time
pathlib.Path("server.pid").write_text(str(os.getpid()))
print("Ember page: http://192.168.1.20:8000/")
print("QR STAND-IN")
print("Ctrl-C to stop.")
while True:
    time.sleep(1)
''')
    local = root / "configs" / "booth_local.yaml"
    local.write_text("camera:\n  name: Old camera\n  focal_px: 1234\nbooth:\n  ember_page_url: https://example.invalid/\n")
    env = dict(os.environ, PYTHONPATH=str(fake.parent))
    return root, env


def run_sitting(sitting, **extra_env):
    root, env = sitting
    before = set((root / "results" / "runs" / "sitting1").glob("*"))
    result = subprocess.run(["bash", "scripts/sitting1_tonight.sh"], cwd=root,
                            env=dict(env, **extra_env), input="\n\nyes\n\nyes\n\ntracked\n\n100\n",
                            text=True, capture_output=True, timeout=15)
    new = set((root / "results" / "runs" / "sitting1").glob("*")) - before
    assert len(new) == 1
    out = new.pop()
    return result, out, json.loads((out / "report.json").read_text())


def test_tonight_uses_builtin_preserves_settings_and_shows_page_before_prompt(sitting):
    root, _ = sitting
    old_local = (root / "configs" / "booth_local.yaml").read_bytes()
    result, out, report = run_sitting(sitting)
    assert result.returncode == 0, result.stdout + result.stderr
    assert report["status"] == "COMPLETED"
    assert all(s["status"] == "OK" for s in report["steps"])
    assert result.stdout.index("Ember page: http://192.168.") < result.stdout.index("Scan/open the address")
    assert "QR STAND-IN" in result.stdout
    assert report["fire"]["errors"] == report["ember"]["errors"] == []
    assert (root / "configs" / "booth_local.yaml").read_bytes() == old_local
    cfg = json.loads((out / "tonight.yaml").read_text())
    assert cfg["camera"]["name"] == "MacBook Camera"
    assert cfg["camera"]["focal_px"] == 999.0
    assert cfg["ember"]["calibration"]["stable"]
    with pytest.raises(ProcessLookupError):
        os.kill(int((root / "server.pid").read_text()), 0)


def test_failed_repeat_cannot_reuse_a_previous_fire_report(sitting):
    _, first, old = run_sitting(sitting)
    result, second, report = run_sitting(sitting, SITTING_FIRE_FAIL="1")
    assert result.returncode == 1
    assert first != second
    assert old["fire"]["frames"] == 120
    assert "fire" not in report
    assert not (second / "fire.json").exists()
    fire = next(s for s in report["steps"] if s["name"] == "fire")
    assert fire["status"] == "FAIL" and fire["exit_code"] == 17
    assert "deliberate fire failure" in fire["output"]
    assert report["status"] == "FAIL"


def test_no_builtin_does_not_substitute_usb_or_iphone(sitting):
    result, out, report = run_sitting(sitting, SITTING_NO_BUILTIN="1")
    assert result.returncode == 1
    assert report["status"] == "FAIL"
    steps = {s["name"]: s for s in report["steps"]}
    assert steps["camera_selection"]["status"] == "FAIL"
    assert steps["cameras"]["status"] == steps["ember"]["status"] == steps["calibrate"]["status"] == "SKIPPED"
    assert not (out / "tonight.yaml").exists()
    assert "ember" not in report


@pytest.mark.parametrize("env", [{"SITTING_APP_ERROR": "1"}, {"SITTING_CAMERA_STATE": "missing"}])
def test_live_zero_exit_does_not_hide_reported_worker_or_camera_failures(sitting, env):
    result, _, report = run_sitting(sitting, **env)
    assert result.returncode == 1
    assert report["status"] == "FAIL"
    assert any(s["name"] == "ember_report" and s["status"] == "FAIL" for s in report["steps"])


def test_interrupt_keeps_a_combined_report(sitting):
    root, env = sitting
    proc = subprocess.Popen(["bash", "scripts/sitting1_tonight.sh"], cwd=root, env=env,
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    # Wait until the initial report exists while the script waits for setup Enter.
    deadline = time.monotonic() + 5
    reports = []
    while not reports and time.monotonic() < deadline:
        reports = list((root / "results" / "runs" / "sitting1").glob("*/report.json"))
        time.sleep(0.02)
    assert reports
    proc.send_signal(signal.SIGTERM)
    stdout, stderr = proc.communicate(timeout=10)
    assert proc.returncode == 130, stdout + stderr
    assert json.loads(reports[0].read_text())["status"] == "INTERRUPTED"
