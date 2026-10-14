#!/usr/bin/env bash
# wfglink booth supervisor: the one command for a booth day.
#
#   bash wfglink/booth/booth.sh [booth options, for example --lang en --limits-screen primary]
#
# - Keeps the Mac awake (caffeinate) while it runs.
# - Starts the booth app (Terminal Python, or WFGLink.app when booth.launcher is app).
# - Esc pressed twice in the app is a clean exit: the supervisor stops too.
# - Any other exit, a crash, or a hang restarts the app after 2 s, doubling up to 60 s
#   while it keeps failing quickly; a run that lasted 5 minutes resets the delay.
# - A hang is a heartbeat file older than 30 s, or no new analysed frame for 90 s.
# - Logs: wfglink/logs/booth.log, rotated at 10 MB, five old files kept;
#   wfglink/logs/heartbeat.json is rewritten every 2 s (fps, source, memory).
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
PY="${WFG_PY:-$ROOT/.venv/bin/python}"
LOGDIR="$ROOT/logs"
LOG="$LOGDIR/booth.log"
HB="$LOGDIR/heartbeat.json"
MAX_BYTES=$((10 * 1024 * 1024))
KEEP=5
HB_STALE_S=${WFG_HB_STALE_S:-30}
NO_FRAMES_S=${WFG_NO_FRAMES_S:-90}
WARMUP_S=${WFG_WARMUP_S:-45}
mkdir -p "$LOGDIR"

if [[ ! -x "$PY" ]]; then
  echo "booth.sh: $PY not found; run wfglink/scripts/sitting1.sh once to install" >&2
  exit 2
fi

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') [booth.sh] $*" | tee -a "$LOG"; }

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

hb_field() {  # hb_field KEY -> value from heartbeat.json, empty if missing
  "$PY" - "$HB" "$1" <<'EOF' 2>/dev/null
import json, sys
try:
    d = json.load(open(sys.argv[1]))
    v = d.get(sys.argv[2])
    print("" if v is None else v)
except Exception:
    print("")
EOF
}

launcher=$("$PY" -c 'from wfglink.config import load_config; print(load_config(local=True)["booth"].get("launcher", "terminal"))' 2>/dev/null || echo terminal)
APP="$ROOT/dist/WFGLink.app"
if [[ "$launcher" == "app" && ! -d "$APP" ]]; then
  log "booth.launcher is app but $APP is missing; building it"
  bash "$ROOT/scripts/make_app.sh" >>"$LOG" 2>&1 || { log "app build failed; using Terminal"; launcher=terminal; }
fi

if command -v caffeinate >/dev/null 2>&1; then
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

trap 'log "supervisor stopped by signal"; [[ -n "${APP_PID:-}" ]] && stop_app "$APP_PID"; exit 130' INT TERM

backoff=2
log "start: launcher=$launcher args=$*"
while true; do
  rotate
  rm -f "$HB"
  started=$(date +%s)
  if [[ "$launcher" == "app" ]]; then
    # open -n starts a new instance as its own app (camera permission belongs to the app);
    # -W waits for it. Its output goes to the same log.
    open -n -W --stdout "$LOG" --stderr "$LOG" "$APP" --args booth --heartbeat "$HB" "$@" &
  else
    "$PY" -m wfglink booth --heartbeat "$HB" "$@" >>"$LOG" 2>&1 &
  fi
  APP_PID=$!
  last_frames=-1
  last_progress=$(date +%s)
  hung=""
  while alive "$APP_PID"; do
    sleep 1
    now=$(date +%s)
    (( (now - started) % 5 == 0 )) || continue
    (( now - started < WARMUP_S )) && continue
    rotate
    if [[ ! -f "$HB" ]]; then
      hung="no heartbeat file"
    else
      epoch=$(hb_field epoch); epoch=${epoch%.*}
      frames=$(hb_field frames)
      if [[ -n "$epoch" ]] && (( now - epoch > HB_STALE_S )); then
        hung="heartbeat is $((now - epoch)) s old"
      elif [[ -n "$frames" ]]; then
        if [[ "$frames" != "$last_frames" ]]; then
          last_frames=$frames
          last_progress=$now
        elif (( now - last_progress > NO_FRAMES_S )); then
          hung="no new frame for $((now - last_progress)) s"
        fi
      fi
    fi
    if [[ -n "$hung" ]]; then
      log "hang detected ($hung); restarting the app"
      if [[ "$launcher" == "app" ]]; then
        app_pid=$(hb_field pid)
        [[ -n "$app_pid" ]] && stop_app "$app_pid"
      fi
      stop_app "$APP_PID"
      break
    fi
  done
  wait "$APP_PID" 2>/dev/null
  code=$?
  status=$(hb_field status)
  ran=$(( $(date +%s) - started ))
  if [[ -z "$hung" && "$status" == "clean_exit" ]]; then
    log "clean exit after ${ran} s (Esc pressed twice, or --duration ended); supervisor done"
    exit 0
  fi
  (( ran >= 300 )) && backoff=2
  log "app ended (code $code, status '${status:-none}', ${hung:-no hang}) after ${ran} s; restarting in ${backoff} s"
  sleep "$backoff"
  backoff=$(( backoff * 2 > 60 ? 60 : backoff * 2 ))
done
