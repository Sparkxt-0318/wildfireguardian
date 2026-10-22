#!/bin/bash
# WildfireGuardian offline: serves this folder at http://localhost:8840 and opens the browser (double-click; close the window to stop)
cd "$(dirname "$0")"
PY=$(command -v python3)
# macOS ships a /usr/bin/python3 stub that only asks to install developer tools; use it only when those tools exist
if [ "$PY" = "/usr/bin/python3" ] && ! xcode-select -p >/dev/null 2>&1; then PY=""; fi
if [ -n "$PY" ] && lsof -i :8840 >/dev/null 2>&1; then
  echo "Port 8840 is already in use: opening the page that is already running."; open "http://localhost:8840/"
elif [ -n "$PY" ]; then
  (sleep 1; open "http://localhost:8840/") &
  "$PY" -m http.server 8840 --bind 127.0.0.1
else
  echo "python3 not found: opening the file directly (everything that works offline works this way too)"; open index.html
fi
