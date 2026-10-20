#!/bin/bash
# WildfireGuardian offline: serves this folder at http://localhost:8840 and opens the browser (double-click; close the window to stop)
cd "$(dirname "$0")"
if command -v python3 >/dev/null 2>&1; then
  (sleep 1; open "http://localhost:8840/") &
  python3 -m http.server 8840 --bind 127.0.0.1
else
  echo "python3 not found: opening the file directly (road view will not work this way)"; open index.html
fi
