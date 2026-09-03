#!/usr/bin/env bash
# Bootstrap a fresh checkout so `make verify` and `pytest` can run — in a cloud
# sandbox, in CI, or on a laptop. Idempotent; never touches tracked files.
#
#   bash scripts/auto/bootstrap.sh                       # creates .auto/venv
#   PYTHON=/path/to/python3.11 bash scripts/auto/bootstrap.sh
#
# Writes .auto/bootstrap.json (interpreter, pins_ok, stack_ok). Exit 0 means the
# geospatial + ML stack imports. requirements.txt pins install from PyPI wheels
# alone on Linux x86_64/aarch64 and macOS arm64 with Python 3.11 (verified
# 2026-09-03); conda is NOT required for the automated loop.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
mkdir -p .auto
VENV="${WFG_VENV:-$ROOT/.auto/venv}"
note() { printf '[bootstrap] %s\n' "$*"; }

pick_python() {
  local c v
  for c in "${PYTHON:-}" python3.11 python3.12 python3.13 python3; do
    [ -n "$c" ] || continue
    command -v "$c" >/dev/null 2>&1 || continue
    v="$("$c" -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null || true)"
    case "$v" in 3.11|3.12|3.13) printf '%s' "$c"; return 0;; esac
  done
  return 1
}

BASE="$(pick_python || true)"
if [ -z "$BASE" ]; then
  note "no python 3.11-3.13 on PATH; trying uv to fetch 3.11"
  if ! command -v uv >/dev/null 2>&1; then
    python3 -m pip install -q --user uv >/dev/null 2>&1 || python3 -m pip install -q uv >/dev/null 2>&1 || true
  fi
  if command -v uv >/dev/null 2>&1; then
    uv python install 3.11 >/dev/null 2>&1 || true
    BASE="$(uv python find 3.11 2>/dev/null || true)"
  fi
fi
if [ -z "$BASE" ]; then
  BASE="$(command -v python3)"
  note "WARNING: falling back to $BASE ($("$BASE" --version 2>&1)); pins may not resolve"
fi
note "base interpreter: $BASE ($("$BASE" --version 2>&1))"

STACK='import osmnx, rasterio, geopandas, sklearn, networkx, xarray, h5netcdf, pyproj, shapely, yaml, pytest'
if [ -x "$VENV/bin/python" ] && "$VENV/bin/python" -c "$STACK" >/dev/null 2>&1; then
  note "reusing $VENV"
else
  rm -rf "$VENV"
  "$BASE" -m venv "$VENV"
fi
PY="$VENV/bin/python"
"$PY" -m pip install -q --upgrade pip wheel >/dev/null

PINS_OK=true
if ! "$PY" -m pip install -q -r requirements.txt; then
  # one retry for a transient PyPI failure before relaxing anything
  if ! "$PY" -m pip install -q -r requirements.txt; then
    PINS_OK=false
    note "pinned install failed twice; falling back to the unpinned extras (env-check will report drift)"
    # fastapi/uvicorn/httpx live only in requirements.txt (no extra); without them
    # tests/test_api.py importorskips silently, the Round-2 failure mode.
    "$PY" -m pip install -q -e ".[geospatial,ml,routing,dev]" fastapi uvicorn httpx "osmnx==2.0.7"
  fi
fi
# fontTools reads the vendored .woff2 fonts (tests/test_screen_checks.py) only with
# brotli, which no pin pulls in; conda's wfg311 had it by accident.
"$PY" -m pip install -q brotli
"$PY" -m pip install -q -e . --no-deps
# the paper loop builds paper/*.docx with python-docx (pure Python, small); no pandoc
"$PY" -m pip install -q "python-docx>=1.1" >/dev/null 2>&1 || note "python-docx not installed; paper build will skip"

STACK_OK=true
if ! "$PY" -c "$STACK"; then STACK_OK=false; fi

"$PY" - "$PY" "$PINS_OK" "$STACK_OK" <<'PYEOF'
import json, platform, subprocess, sys, datetime
py, pins_ok, stack_ok = sys.argv[1], sys.argv[2] == "true", sys.argv[3] == "true"
ver = subprocess.run([py, "-c", "import sys;print(sys.version.split()[0])"], capture_output=True, text=True).stdout.strip()
try:
    import osmnx, sklearn, numpy
    versions = {"osmnx": osmnx.__version__, "scikit-learn": sklearn.__version__, "numpy": numpy.__version__}
except Exception as e:  # pragma: no cover
    versions = {"error": str(e)}
state = {
    "written_at_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "python": py, "python_version": ver, "platform": platform.platform(),
    "pins_ok": pins_ok, "stack_ok": stack_ok, "versions": versions,
}
json.dump(state, open(".auto/bootstrap.json", "w"), indent=2)
print("[bootstrap] " + json.dumps(state))
PYEOF

if [ "$STACK_OK" != true ]; then
  note "FAILED: geospatial/ML stack does not import"; exit 1
fi
note "OK: use $PY  (e.g. make verify PYTHON=$PY)"
