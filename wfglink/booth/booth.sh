#!/usr/bin/env bash
# wfglink booth supervisor: the one command for a booth day.
#
#   ./booth/booth.sh [live options]        (from wfglink/; or double-click booth/booth.command)
#
# It runs "python -m wfglink live --heartbeat logs/heartbeat.json [live options]": the
# approved clips of booth/playlist.yaml play in a loop and are analysed live, fullscreen on
# the external monitor when one is connected, else on the MacBook screen. Live options pass
# through, for example --lang en, --limits-screen NAME, --synthetic or --clip FILE.
#
# - Keeps the Mac awake (caffeinate, macOS only) while it runs.
# - Esc, then Esc again in the app, is a clean exit (heartbeat status clean_exit): the
#   supervisor stops too and exits 0.
# - Any other exit, a crash, or a hang restarts the app after 2 s, doubling up to 60 s
#   while it keeps failing quickly; a run that lasted 5 minutes resets the delay.
# - A hang is a heartbeat file older than 30 s, or no new analysed frame for 90 s while
#   playback is not paused (Space pauses on purpose) and ember mode is not showing its
#   camera message (no camera, or camera permission off).
# - SIGTERM, SIGINT (Ctrl-C) or SIGHUP (the Terminal window closed) stops the app and exits 130.
# - Logs: wfglink/logs/booth.log, rotated at 10 MB, five old files kept;
#   wfglink/logs/heartbeat.json is rewritten every 2 s by the app.
#
# Environment (tests and special cases): WFG_PY (Python, default wfglink/.venv/bin/python),
# WFG_LOGDIR (default wfglink/logs), WFG_HB_STALE_S, WFG_NO_FRAMES_S, WFG_WARMUP_S, WFG_CHECK_S.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
PY="${WFG_PY:-$ROOT/.venv/bin/python}"
LOGDIR="${WFG_LOGDIR:-$ROOT/logs}"
LOG="$LOGDIR/booth.log"
HB="$LOGDIR/heartbeat.json"
MAX_BYTES=$((10 * 1024 * 1024))   # rotate the log at this size
KEEP=5                            # old logs kept
HB_STALE_S=${WFG_HB_STALE_S:-30}  # hang: heartbeat older than this
NO_FRAMES_S=${WFG_NO_FRAMES_S:-90}  # hang: no new analysed frame for this long (unless paused or waiting for the camera)
WARMUP_S=${WFG_WARMUP_S:-45}      # no hang checks in the first seconds of a run
CHECK_S=${WFG_CHECK_S:-5}         # seconds between hang checks

if [[ ! -x "$PY" ]]; then
  echo "booth.sh: $PY not found. Run ./scripts/setup_mac.sh once (from the wfglink folder) to install." >&2
  exit 2
fi
mkdir -p "$LOGDIR"
cd "$ROOT" || exit 2      # relative paths (booth/playlist.yaml, data/clips) resolve from wfglink/

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') [booth.sh] $*" | tee -a "$LOG"; }

nap() { sleep "$1" & wait $! 2>/dev/null; }   # a sleep that a signal interrupts at once

rotate() {
  [[ -f "$LOG" ]] || return 0
  local size
  size=$(wc -c <"$LOG" | tr -d ' ')
  (( size < MAX_BYTES )) && return 0
  local i
  for (( i = KEEP - 1; i >= 1; i-- )); do
    [[ -f "$LOG.$i" ]] && mv -f "$LOG.$i" "$LOG.$((i + 1))"
  done
  cp "$LOG" "$LOG.1" && : >"$LOG"     # copy then truncate: the app keeps appending
}

hb_read() {  # hb_read: "epoch frames status waiting" from heartbeat.json ("- - - -" when unreadable)
  # waiting is "yes" while new frames stop on purpose: paused (Space), or ember mode showing its
  # camera message (no camera, permission off or undecided, or ember mode could not start).
  "$PY" - "$HB" <<'EOF' 2>/dev/null || echo "- - - -"
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    print("- - - -")
    raise SystemExit
def f(k):
    v = d.get(k)
    return "-" if v is None or v == "" else str(v).split()[0]
waiting = d.get("paused") or (d.get("mode") == "ember" and d.get("camera_state") in ("missing", "denied", "asking", "error"))
print(f("epoch").split(".")[0], f("frames"), f("status"), "yes" if waiting else "no")
EOF
}

if [[ "$(uname)" == "Darwin" ]] && command -v caffeinate >/dev/null 2>&1; then
  caffeinate -dimsu -w $$ &
fi

alive() {  # alive PID: running and not a zombie (kill -0 also succeeds on an exited, unreaped child)
  local st
  st=$(ps -o stat= -p "$1" 2>/dev/null) || return 1
  [[ -n "$st" && "$st" != Z* ]]
}

stop_app() {  # stop_app PID: polite, then forceful
  local pid=$1
  kill -TERM "$pid" 2>/dev/null
  for _ in 1 2 3 4 5 6 7 8 9 10; do alive "$pid" || return 0; sleep 1; done
  kill -KILL "$pid" 2>/dev/null
}

on_signal() {
  trap - INT TERM HUP
  log "supervisor stopped by signal"
  [[ -n "${APP_PID:-}" ]] && alive "$APP_PID" && stop_app "$APP_PID"
  exit 130
}
trap on_signal INT TERM HUP

backoff=2
log "start: $PY -m wfglink live $*"
while true; do
  rotate
  rm -f "$HB"
  started=$(date +%s)
  "$PY" -m wfglink live --heartbeat "$HB" "$@" >>"$LOG" 2>&1 &
  APP_PID=$!
  last_frames=-1
  last_progress=$started
  next_check=$(( started + WARMUP_S ))
  hung=""
  while alive "$APP_PID"; do
    nap 1
    now=$(date +%s)
    (( now >= next_check )) || continue
    next_check=$(( now + CHECK_S ))
    rotate
    if [[ ! -f "$HB" ]]; then
      hung="no heartbeat file"
    else
      read -r epoch frames status waiting <<<"$(hb_read)"
      if [[ "$epoch" != "-" ]] && (( now - epoch > HB_STALE_S )); then
        hung="heartbeat is $((now - epoch)) s old"
      elif [[ "$waiting" == "yes" || "$frames" != "$last_frames" ]]; then
        last_frames=$frames                 # analysing, paused, or waiting for the camera on purpose
        last_progress=$now
      elif (( now - last_progress > NO_FRAMES_S )); then
        hung="no new frame for $((now - last_progress)) s"
      fi
    fi
    if [[ -n "$hung" ]]; then
      log "hang detected ($hung); restarting the app"
      stop_app "$APP_PID"
      break
    fi
  done
  wait "$APP_PID" 2>/dev/null
  code=$?
  read -r _ _ status _ <<<"$(hb_read)"
  ran=$(( $(date +%s) - started ))
  if [[ -z "$hung" && "$status" == "clean_exit" ]]; then
    log "clean exit after ${ran} s (Esc pressed twice, or --duration ended); supervisor done"
    exit 0
  fi
  (( ran >= 300 )) && backoff=2
  log "app ended (code $code, status '${status/#-/none}', ${hung:-no hang}) after ${ran} s; restarting in ${backoff} s"
  nap "$backoff"
  backoff=$(( backoff * 2 > 60 ? 60 : backoff * 2 ))
done
