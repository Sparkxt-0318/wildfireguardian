"""booth/booth.sh: restart after a crash, restart after a hang, stop on a clean exit."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

FAKE = r'''#!/usr/bin/env bash
# Stand-in for the venv Python: "-m wfglink booth" plays a scripted run, anything else is real Python.
if [[ "$1" == "-m" && "$2" == "wfglink" && "$3" == "booth" ]]; then
  hb=""; prev=""
  for a in "$@"; do [[ "$prev" == "--heartbeat" ]] && hb="$a"; prev="$a"; done
  n=$(cat "$STATE" 2>/dev/null || echo 0); n=$((n + 1)); echo "$n" > "$STATE"
  beat() { echo "{\"status\": \"$1\", \"epoch\": $(date +%s), \"frames\": $2, \"pid\": $$}" > "$hb"; }
  case "$n" in
    1) beat running 5; echo "run 1 crashes"; exit 1 ;;
    2) beat running 7; echo "run 2 hangs"; sleep 600 ;;
    *) beat running 9; sleep 1; beat clean_exit 9; echo "run 3 exits cleanly"; exit 0 ;;
  esac
fi
exec "$REAL_PY" "$@"
'''


@pytest.mark.slow
def test_supervisor_restarts_then_stops_cleanly(tmp_path):
    fake = tmp_path / "python"
    fake.write_text(FAKE)
    fake.chmod(0o755)
    logdir = ROOT / "logs"
    log = logdir / "booth.log"
    before = log.read_text() if log.exists() else ""
    env = {**os.environ, "WFG_PY": str(fake), "REAL_PY": sys.executable, "STATE": str(tmp_path / "state"),
           "WFG_HB_STALE_S": "3", "WFG_WARMUP_S": "1", "WFG_NO_FRAMES_S": "60"}
    res = subprocess.run(["bash", str(ROOT / "booth" / "booth.sh")], env=env, capture_output=True, text=True, timeout=120)
    text = log.read_text()[len(before):]
    assert res.returncode == 0, res.stdout + res.stderr
    assert "app ended (code 1" in text
    assert "hang detected (heartbeat is" in text
    assert "clean exit after" in text
    assert (tmp_path / "state").read_text().strip() == "3"
