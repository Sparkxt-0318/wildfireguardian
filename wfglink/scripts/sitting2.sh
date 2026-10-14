#!/usr/bin/env bash
# wfglink sitting 2: check B on the booth loop, unplug test, local config, overnight soak.
#
#   bash ~/wfglink-run/wfglink/scripts/sitting2.sh            # the evening (or resume after a stop)
#   bash ~/wfglink-run/wfglink/scripts/sitting2.sh --finish   # the morning: stop the soak, final report
#   bash ~/wfglink-run/wfglink/scripts/sitting2.sh --from unplug_test
#
# The checklist is wfglink/docs/SITTING2.md. Results go to ~/wfglink-sitting2/.
set -uo pipefail
cd "$(dirname "$0")/.."
WFG="$(pwd)"

echo "wfglink sitting 2  ($(date '+%Y-%m-%d %H:%M'))"
echo "Folder: $WFG"

if [[ "$(uname)" != "Darwin" ]]; then
  echo "Note: this is not macOS. Only '--dry-run' makes sense here." >&2
fi
if [[ "$(uname -m)" != "arm64" && "$(uname)" == "Darwin" ]]; then
  echo "Note: this Mac is not Apple Silicon ($(uname -m)); continuing." >&2
fi

# Python 3.12 (python.org installer puts it in /usr/local/bin and the framework folder).
PY=""
for cand in python3.12 /usr/local/bin/python3.12 /Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 /opt/homebrew/bin/python3.12; do
  if command -v "$cand" >/dev/null 2>&1; then PY="$(command -v "$cand")"; break; fi
done
if [[ -z "$PY" ]]; then
  echo "Python 3.12 is not installed. Install it from https://www.python.org/downloads/ (macOS 64-bit universal2 installer, version 3.12.x), then run this again." >&2
  exit 1
fi
echo "Python: $PY ($("$PY" -V 2>&1))"

FINISH=0
for arg in "$@"; do
  [[ "$arg" == "--finish" ]] && FINISH=1
done

# Install or update the environment only when requirements changed. Never in the morning:
# the overnight booth runs from this environment, and reinstalling under it could crash it.
REQ_SHA="$(shasum -a 256 requirements.txt pyproject.toml 2>/dev/null | shasum -a 256 | cut -c1-16 || sha256sum requirements.txt pyproject.toml | sha256sum | cut -c1-16)"
STAMP=".venv/.wfglink_install"
if [[ $FINISH -eq 1 ]]; then
  if [[ ! -x .venv/bin/python ]]; then
    echo "No environment in $WFG/.venv: run --finish from the same folder that started the soak." >&2
    exit 1
  fi
  echo "Morning finish: the environment is used as it is."
elif [[ ! -x .venv/bin/python || ! -f "$STAMP" || "$(cat "$STAMP" 2>/dev/null)" != "$REQ_SHA" ]]; then
  echo "Installing (about 5 to 10 minutes on first run; needs internet)..."
  T0=$(date +%s)
  [[ -x .venv/bin/python ]] || "$PY" -m venv .venv || { echo "Could not create .venv" >&2; exit 1; }
  .venv/bin/python -m pip install --upgrade pip >/dev/null &&
  .venv/bin/python -m pip install -r requirements.txt &&
  .venv/bin/python -m pip install -e . --no-deps >/dev/null
  STATUS=$?
  T1=$(date +%s)
  mkdir -p .venv
  printf '{"seconds": %d, "ok": %s, "python": "%s", "at": "%s"}\n' $((T1 - T0)) "$([[ $STATUS -eq 0 ]] && echo true || echo false)" "$("$PY" -V 2>&1)" "$(date '+%Y-%m-%dT%H:%M:%S%z')" > .venv/.install_info.json
  if [[ $STATUS -ne 0 ]]; then
    echo "Install failed. Check the internet connection and run this again; the log above shows the error." >&2
    exit 1
  fi
  echo "$REQ_SHA" > "$STAMP"
  echo "Installed in $((T1 - T0)) s."
else
  echo "Environment already installed."
fi

# Keep the Mac awake while the script runs (the overnight soak keeps it awake by itself).
if command -v caffeinate >/dev/null 2>&1; then
  caffeinate -dimsu -w $$ &
fi

exec .venv/bin/python -m wfglink sitting2 "$@"
