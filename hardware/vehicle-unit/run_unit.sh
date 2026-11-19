#!/usr/bin/env bash
# Start the vehicle unit: ./run_unit.sh [--sim SESSION_DIR [--speed 1.0] [--loop]] [--config config/unit.yaml]
# Uses ./.venv if present (create it with: python3 -m venv --system-site-packages .venv).
set -euo pipefail
cd "$(dirname "$0")"
PY="python3"
if [[ -x .venv/bin/python ]]; then
  PY=".venv/bin/python"
fi
exec "$PY" -m wfgvu "$@"
