#!/usr/bin/env bash
# The test suite (README.md, section 7). Writes nothing into this folder: no __pycache__, no .pytest_cache.
#   ./run_tests.sh             everything, including the browser tests (Playwright's Chromium)
#   ./run_tests.sh --quick     without the browser tests
#   ./run_tests.sh tests/test_stops.py -k lead      any pytest arguments
set -eu
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
"$PY" -c 'import pytest, httpx' 2>/dev/null || { echo "Run: $PY -m pip install -r requirements-tools.txt"; exit 1; }
ARGS=()
for a in "$@"; do
  if [ "$a" = "--quick" ]; then ARGS+=("--ignore=tests/test_web.py"); else ARGS+=("$a"); fi
done
export PYTHONDONTWRITEBYTECODE=1
exec "$PY" -m pytest -q ${ARGS[@]+"${ARGS[@]}"}
