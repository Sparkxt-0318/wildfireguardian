"""booth/booth.sh: restart after a crash or a hang, no hang while paused, stop on a clean exit,
stop the app and exit 130 on SIGTERM, and a clear message when the environment is missing.

A fake "python" stands in for the venv Python: "-m wfglink live" plays a scripted run (one
script per run, chosen by a counter), anything else (the heartbeat reader) is real Python.
"""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

FAKE = r'''#!/usr/bin/env bash
if [[ "$1" == "-m" && "$2" == "wfglink" && "$3" == "live" ]]; then
  hb=""; prev=""
  for a in "$@"; do [[ "$prev" == "--heartbeat" ]] && hb="$a"; prev="$a"; done
  echo "$*" > "$ARGS"
  n=$(cat "$STATE" 2>/dev/null || echo 0); n=$((n + 1)); echo "$n" > "$STATE"
  beat() { echo "{\"status\": \"$1\", \"epoch\": $(date +%s), \"frames\": $2, \"paused\": $3, \"pid\": $$}" > "$hb"; }
  script=$(sed -n "${n}p" "$PLAN"); [[ -z "$script" ]] && script=clean
  case "$script" in
    crash) beat running 5 false; echo "run $n crashes"; exit 1 ;;
    hang) beat running 7 false; echo "run $n hangs"; sleep 600 ;;
    paused) for i in 1 2 3 4 5 6; do beat running 3 true; sleep 1; done; beat clean_exit 3 true; exit 0 ;;
    forever) trap 'beat closed 1 false; exit 0' TERM; while true; do beat running 1 false; sleep 1; done ;;
    *) beat running 9 false; sleep 1; beat clean_exit 9 false; echo "run $n exits cleanly"; exit 0 ;;
  esac
fi
exec "$REAL_PY" "$@"
'''


def _setup(tmp_path: Path, plan: list[str], **env) -> tuple[list[str], dict, Path]:
    fake = tmp_path / "python"
    fake.write_text(FAKE)
    fake.chmod(0o755)
    (tmp_path / "plan").write_text("\n".join(plan) + "\n")
    e = {**os.environ, "WFG_PY": str(fake), "REAL_PY": sys.executable, "STATE": str(tmp_path / "state"),
         "PLAN": str(tmp_path / "plan"), "ARGS": str(tmp_path / "args"), "WFG_LOGDIR": str(tmp_path / "logs"),
         "WFG_HB_STALE_S": "3", "WFG_WARMUP_S": "1", "WFG_NO_FRAMES_S": "60", "WFG_CHECK_S": "1", **env}
    return ["bash", str(ROOT / "booth" / "booth.sh"), "--lang", "en"], e, tmp_path / "logs" / "booth.log"


@pytest.mark.slow
def test_supervisor_restarts_then_stops_cleanly(tmp_path):
    cmd, env, log = _setup(tmp_path, ["crash", "hang", "clean"])
    res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=120)
    text = log.read_text()
    assert res.returncode == 0, res.stdout + res.stderr
    assert "app ended (code 1" in text
    assert "hang detected (heartbeat is" in text
    assert "clean exit after" in text
    assert (tmp_path / "state").read_text().strip() == "3"
    # The app is "python -m wfglink live" with the heartbeat in the log folder and the options passed on.
    assert (tmp_path / "args").read_text().split() == ["-m", "wfglink", "live", "--heartbeat",
                                                       str(tmp_path / "logs" / "heartbeat.json"), "--lang", "en"]


@pytest.mark.slow
def test_a_paused_booth_is_not_a_hang(tmp_path):
    cmd, env, log = _setup(tmp_path, ["paused"], WFG_NO_FRAMES_S="2")
    res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "hang detected" not in log.read_text()
    assert (tmp_path / "state").read_text().strip() == "1"


@pytest.mark.slow
def test_sigterm_stops_the_app_and_exits_130(tmp_path):
    cmd, env, log = _setup(tmp_path, ["forever"])
    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    hb = tmp_path / "logs" / "heartbeat.json"
    t_end = time.monotonic() + 20
    while not hb.exists() and time.monotonic() < t_end:
        time.sleep(0.1)
    time.sleep(0.5)
    app_pid = json.loads(hb.read_text())["pid"]
    proc.send_signal(signal.SIGTERM)
    assert proc.wait(timeout=30) == 130
    assert "supervisor stopped by signal" in log.read_text()
    assert json.loads(hb.read_text())["status"] == "closed"      # the app was asked to stop, not killed
    with pytest.raises(ProcessLookupError):
        os.kill(app_pid, 0)


def test_missing_environment_says_to_run_setup(tmp_path):
    env = {**os.environ, "WFG_PY": str(tmp_path / "no-python"), "WFG_LOGDIR": str(tmp_path / "logs")}
    res = subprocess.run(["bash", str(ROOT / "booth" / "booth.sh")], env=env, capture_output=True, text=True, timeout=30)
    assert res.returncode == 2
    assert "./scripts/setup_mac.sh" in res.stderr


def test_booth_command_starts_booth_sh():
    text = (ROOT / "booth" / "booth.command").read_text()
    assert 'booth.sh" "$@"' in text
    for p in ("booth/booth.sh", "booth/booth.command"):
        assert os.access(ROOT / p, os.X_OK), p
        assert subprocess.run(["bash", "-n", str(ROOT / p)]).returncode == 0
