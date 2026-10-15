#!/usr/bin/env bash
# Sitting 1, tonight version: MacBook built-in camera and an iPhone, no new parts.
#
#   cd ~/wfglink-run/wfglink && ./scripts/sitting1_tonight.sh
#
# Steps, in order (each waits for Enter first; Ctrl-C stops, the report keeps what ran):
#   1 setup        ./scripts/setup_mac.sh (installs, asks for camera permission)
#   2 doctor       python -m wfglink doctor
#   3 cameras      the built-in camera is found and opens
#   4 fire mode    60 s on C5 (an approved NIST clip): try keys A and L
#   5 ember mode   the phone page served over Wi-Fi, then 60 s of ember mode with the built-in camera
#   6 calibrate    the printed A4 target held at 2.0 m
# Report: ~/wfglink-sitting1/report.txt (paste it back); details next to it.
set -u
cd "$(dirname "$0")/.."
OUT="$HOME/wfglink-sitting1"
mkdir -p "$OUT"
REPORT="$OUT/report.txt"
PY=".venv/bin/python"
: >"$REPORT"
say() { printf '\n== %s\n' "$*"; }
log() { printf '%s\n' "$*" | tee -a "$REPORT"; }
wait_enter() { printf '\n%s\nPress Enter to start (or type s and Enter to skip): ' "$1"; read -r ans; [[ "$ans" != "s" ]]; }

log "wfglink sitting 1 (tonight) $(date '+%Y-%m-%d %H:%M %z')"
log "commit $(git -C .. rev-parse --short HEAD 2>/dev/null)  macOS $(sw_vers -productVersion 2>/dev/null)  $(uname -m)"

say "1 setup"
if wait_enter "Installs everything (5 to 10 minutes the first time) and asks for camera permission: click Allow."; then
  ./scripts/setup_mac.sh 2>&1 | tee "$OUT/setup.txt"
  log "setup: exit ${PIPESTATUS[0]}"
fi
[[ -x "$PY" ]] || { log "no .venv: setup did not finish; send this report"; exit 1; }

say "2 doctor"
"$PY" -m wfglink doctor 2>&1 | tee "$OUT/doctor.txt"
log "doctor:"; sed 's/^/  /' "$OUT/doctor.txt" >>"$REPORT"

say "3 cameras"
"$PY" -m wfglink cameras --open 3 2>&1 | tee "$OUT/cameras.txt"
log "cameras:"; sed 's/^/  /' "$OUT/cameras.txt" >>"$REPORT"

say "4 fire mode"
if wait_enter "The booth screen plays C5 for 60 s on this screen (or the monitor if one is plugged in). Press A twice (raw, then analysed) and L twice (English, then Korean). Note whether the numbers and orange trails look right."; then
  "$PY" -m wfglink live --clip data/clips/C5_nist_emberometer.yaml --duration 60 --report "$OUT/fire.json" 2>"$OUT/fire.log"
  log "fire mode: exit $? $("$PY" -c "import json,sys; r=json.load(open(sys.argv[1])); print({k: r.get(k) for k in ('frames','paints','errors')}, 'last:', r.get('last'))" "$OUT/fire.json" 2>/dev/null)"
  printf 'Did fire mode look right? (y/n, then a few words): '; read -r ans; log "fire mode, your note: $ans"
fi

say "5 ember mode"
if wait_enter "Step a: the phone page is served over this Wi-Fi. Scan the QR code with the iPhone camera (same Wi-Fi), open the page, set brightness to maximum, tap once."; then
  "$PY" scripts/serve_page.py >"$OUT/page_server.txt" 2>&1 &
  SERVER=$!
  sleep 2; cat "$OUT/page_server.txt"
  log "page: $(head -1 "$OUT/page_server.txt")"
  printf 'Does the ember show on the iPhone? (y/n, then a few words): '; read -r ans; log "page on iPhone, your note: $ans"
  if wait_enter "Step b: 60 s of ember mode with the built-in camera. Stand about 2 m from the MacBook, hold the iPhone screen toward it and move it slowly, then quickly. Then hold it still. Then turn it away."; then
    "$PY" -m wfglink live --ember --duration 60 --report "$OUT/ember.json" 2>"$OUT/ember.log"
    log "ember mode: exit $? $("$PY" -c "import json,sys; r=json.load(open(sys.argv[1])); print({k: r.get(k) for k in ('frames','paints','errors','camera_state')}, 'last:', r.get('last'))" "$OUT/ember.json" 2>/dev/null)"
    printf 'Was the phone tracked (ID, trail, speed)? Any false ember (lamp, window)? ' ; read -r ans; log "ember mode, your note: $ans"
  fi
  kill "$SERVER" 2>/dev/null
fi

say "6 calibrate"
if wait_enter "Hold the printed A4 target (booth/ember/calibration_target_A4.pdf, printed at 100 percent) flat, facing the camera, with its centre 2.0 m from the MacBook camera (measure it). Keep it still until the window says it is done."; then
  "$PY" -m wfglink calibrate 2>&1 | tee "$OUT/calibrate.txt"
  log "calibrate: exit ${PIPESTATUS[0]}"; sed 's/^/  /' "$OUT/calibrate.txt" | tail -12 >>"$REPORT"
  printf 'Measured length of the 100 mm line on your print, in mm: '; read -r ans; log "print check, 100 mm line measured: $ans"
fi

for f in "$OUT"/fire.log "$OUT"/ember.log; do
  [[ -s "$f" ]] && { log "last lines of $(basename "$f"):"; tail -8 "$f" | sed 's/^/  /' >>"$REPORT"; }
done
say "done"
echo "Paste the whole of $REPORT back to Claude:"
echo; cat "$REPORT"
