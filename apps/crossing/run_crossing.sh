#!/usr/bin/env bash
# Crossing app launcher (laptop). Serves http://127.0.0.1:8781/ and opens it in a browser.
# Verdicts are ADVISORY for trained crews; every limit is a PLACEHOLDER for the fire service to set.
#   ./run_crossing.sh                                        live, roof unit at ws://10.42.0.1:8770/stream
#   ./run_crossing.sh --pi ws://10.42.0.1:8770/stream --vehicle fire_engine --fuel GR1
#   ./run_crossing.sh --replay ../../hardware/vehicle-unit/samples/flame_front --speed 1 --loop
#   ./run_crossing.sh --sim-link ws://127.0.0.1:8765/v1/live/closures --region <id>   (step 9, opt-in)
#   WFG_PORT=8790 ./run_crossing.sh          another port
#   WFG_BROWSER=none ./run_crossing.sh       no browser window;  WFG_BROWSER=/path/to/browser  a specific browser
#   PYTHON=/path/to/python ./run_crossing.sh another interpreter (default: .venv/bin/python if present)
set -eu
cd "$(dirname "$0")"
PORT="${WFG_PORT:-8781}"
if [ -z "${PYTHON:-}" ] && [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY="${PYTHON:-python3}"; fi
URL="http://127.0.0.1:${PORT}/"

"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null || {
  echo "Python 3.11 or newer is needed (3.12 is what the tests use)."; exit 1; }
"$PY" -c 'import fastapi, uvicorn, websockets, numpy, yaml' 2>/dev/null || {
  echo "Packages missing. Run:  $PY -m pip install -r requirements.txt"; exit 1; }
if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $PORT is already in use (is the app already running?). Try: WFG_PORT=8790 ./run_crossing.sh"; exit 1
fi

PYTHONDONTWRITEBYTECODE=1 "$PY" -m crossing --port "$PORT" "$@" &
SERVER=$!
cleanup() { kill "$SERVER" 2>/dev/null || true; wait "$SERVER" 2>/dev/null || true; }
trap cleanup EXIT
trap 'exit 130' INT TERM

up=0
for _ in $(seq 1 100); do
  if curl -s -o /dev/null "${URL}api/health" 2>/dev/null; then up=1; break; fi
  kill -0 "$SERVER" 2>/dev/null || { echo "The app stopped; see the messages above."; exit 1; }
  sleep 0.1
done
[ "$up" = 1 ] || { echo "The app did not answer on $URL"; exit 1; }

# Keep the Mac awake while the app runs (display, idle and system sleep).
if command -v caffeinate >/dev/null 2>&1; then caffeinate -dims -w "$SERVER" & fi

case "${WFG_BROWSER:-}" in
  none) echo "Open $URL in a browser. Ctrl+C stops the app." ;;
  "")   (command -v open >/dev/null 2>&1 && open "$URL") || (command -v xdg-open >/dev/null 2>&1 && xdg-open "$URL") \
          || echo "Open $URL in a browser."
        echo "Ctrl+C stops the app." ;;
  *)    "$WFG_BROWSER" "$URL" >/dev/null 2>&1 & echo "Ctrl+C stops the app." ;;
esac
wait "$SERVER"
