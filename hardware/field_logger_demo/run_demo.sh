#!/usr/bin/env bash
# Booth demo (spec section 8): the server on 127.0.0.1 only, Chrome full screen in app mode with its own profile,
# the Mac kept awake. Closing the window (or Ctrl+C here) stops the server, which closes the logger's port.
#   ./run_demo.sh                         the demo
#   ./run_demo.sh --dev-device-double     with a simulated logger (firmware 0.2.0 behaviour), for development
#   ./run_demo.sh --dev-double-live       with a simulated logger that sends LIVE lines (firmware 0.3.0)
#   WFG_PORT=8800 ./run_demo.sh           another port;  WFG_BROWSER=none ./run_demo.sh   no browser window
set -eu
cd "$(dirname "$0")"
PORT="${WFG_PORT:-8765}"
PY="${PYTHON:-python3}"
URL="http://127.0.0.1:${PORT}/"

"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null || {
  echo "Python 3.11 or newer is needed (see README.md, section 1)."; exit 1; }
"$PY" -c 'import fastapi, uvicorn, serial' 2>/dev/null || {
  echo "Packages missing. Run:  $PY -m pip install -r requirements.txt"; exit 1; }
if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $PORT is already in use (is the demo already running?). Try: WFG_PORT=8800 ./run_demo.sh"; exit 1
fi

# The server prints the device stream (every line sent and received) in this terminal.
PYTHONDONTWRITEBYTECODE=1 "$PY" -m app.main --port "$PORT" "$@" &
SERVER=$!
cleanup() { kill "$SERVER" 2>/dev/null || true; wait "$SERVER" 2>/dev/null || true; }
trap cleanup EXIT
trap 'exit 130' INT TERM

up=0
for _ in $(seq 1 100); do
  if curl -s -o /dev/null "${URL}api/health" 2>/dev/null; then up=1; break; fi
  kill -0 "$SERVER" 2>/dev/null || { echo "The server stopped; see the messages above."; exit 1; }
  sleep 0.05
done
[ "$up" = 1 ] || { echo "The server did not answer on $URL"; exit 1; }

# Keep the Mac awake while the server runs (display, idle and system sleep).
if command -v caffeinate >/dev/null 2>&1; then caffeinate -dims -w "$SERVER" & fi

find_browser() {
  local c
  for c in "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
           "$HOME/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
           "/Applications/Chromium.app/Contents/MacOS/Chromium"; do
    [ -x "$c" ] && { echo "$c"; return; }
  done
  for c in "$HOME"/Library/Caches/ms-playwright/chromium-*/chrome-mac*/"Google Chrome for Testing.app"/Contents/MacOS/"Google Chrome for Testing" \
           "$HOME"/Library/Caches/ms-playwright/chromium-*/chrome-mac*/Chromium.app/Contents/MacOS/Chromium; do
    [ -x "$c" ] && { echo "$c"; return; }
  done
  for c in google-chrome google-chrome-stable chromium chromium-browser; do
    command -v "$c" >/dev/null 2>&1 && { command -v "$c"; return; }
  done
}

if [ "${WFG_BROWSER:-}" = "none" ]; then
  echo "Open $URL in Chrome. Ctrl+C stops the demo."
  wait "$SERVER"
  exit 0
fi
BROWSER="${WFG_BROWSER:-$(find_browser || true)}"     # no browser found: the fallback below, not an exit (set -e)
if [ -n "$BROWSER" ]; then
  # Its own profile, so an already running Chrome does not take over the window and its flags.
  "$BROWSER" --user-data-dir="$PWD/.chrome-profile" --app="$URL" --start-fullscreen --no-first-run \
    --no-default-browser-check --disable-features=Translate --disable-translate --disable-sync \
    --disable-background-networking --disable-component-update --password-store=basic >/dev/null 2>&1 || true
  echo "Window closed: stopping the server."
else
  echo "Chrome was not found. Opening $URL in the default browser; Ctrl+C here stops the demo."
  (command -v open >/dev/null 2>&1 && open "$URL") || (command -v xdg-open >/dev/null 2>&1 && xdg-open "$URL") || true
  wait "$SERVER"
fi
