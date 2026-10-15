#!/usr/bin/env bash
# wfglink setup on the Mac: one command, safe to run again (a second run only checks).
#
#   cd ~/wfglink-run/wfglink && ./scripts/setup_mac.sh      # first time, and after every update
#   ./scripts/setup_mac.sh --no-clips                       # do not download the booth clips
#
# - Finds python.org Python 3.12: /Library/Frameworks/Python.framework/Versions/3.12, then
#   /usr/local/bin/python3.12, then any python3.12 on PATH (with a warning: python.org's is expected).
# - Creates .venv, or makes it again when it was made with another Python.
# - Installs requirements.txt and wfglink itself (pip install -e . --no-deps) only when
#   requirements.txt or pyproject.toml changed since the last successful install
#   (stamp: .venv/.wfglink_install). The first install takes 5 to 10 minutes and needs internet.
# - Creates data/raw, logs and results/validation.
# - Downloads the playlist clips (booth/playlist.yaml) missing from data/raw through
#   scripts/fetch_clips.py, unless --no-clips is given or there is no network (a warning).
#   data/clips.csv and data/SOURCES.md, which fetch_clips.py rewrites, are kept as they are in git.
# - On macOS, runs python -m wfglink cameras --request: the first time, macOS asks whether
#   Terminal may use the camera (click Allow); it lists the cameras and the one the booth picks.
# - Runs python -m wfglink doctor and prints the next commands.
# Exit code: 0 when every doctor check is OK, 1 when setup or a check failed.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
WFG="$(pwd)"
PYORG=/Library/Frameworks/Python.framework/Versions/3.12
NO_CLIPS=0
for arg in "$@"; do
  case "$arg" in
    --no-clips) NO_CLIPS=1 ;;
    -h|--help) awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"; exit 0 ;;
    *) echo "setup_mac.sh: unknown option $arg (only --no-clips)" >&2; exit 2 ;;
  esac
done

say() { echo "setup: $*"; }
warn() { echo "setup: WARNING: $*" >&2; }

say "wfglink folder $WFG ($(date '+%Y-%m-%d %H:%M'))"
if [[ "$(uname)" != "Darwin" ]]; then
  say "this is $(uname), not macOS: continuing (the python.org and screen checks are for the Mac)"
fi

# Python 3.12 ---------------------------------------------------------------------------------
PY=""
for cand in "$PYORG/bin/python3.12" /usr/local/bin/python3.12; do
  if [[ -x "$cand" ]]; then PY="$cand"; break; fi
done
if [[ -z "$PY" ]] && command -v python3.12 >/dev/null 2>&1; then
  PY="$(command -v python3.12)"
fi
if [[ -z "$PY" ]] || ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)' 2>/dev/null; then
  echo "Python 3.12 is not installed. Download the macOS installer for the latest Python 3.12.x from" >&2
  echo "  https://www.python.org/downloads/macos/" >&2
  echo "run it, then run ./scripts/setup_mac.sh again." >&2
  exit 1
fi
BASE="$("$PY" -c 'import sys; print(sys.base_prefix)')"
say "Python $("$PY" -c 'import platform; print(platform.python_version())') at $PY"
if [[ "$(uname)" == "Darwin" && "$BASE" != "$PYORG"* ]]; then
  warn "this Python 3.12 ($BASE) is not python.org's. The manual expects python.org's installer:"
  warn "https://www.python.org/downloads/macos/ ; after installing it, run this again and .venv is made with it."
fi

# .venv ---------------------------------------------------------------------------------------
if [[ -e .venv ]]; then
  have="$(.venv/bin/python -c 'import sys; print("%d.%d %s" % (sys.version_info[0], sys.version_info[1], sys.base_prefix))' 2>/dev/null || echo broken)"
  if [[ "$have" != "3.12 $BASE" ]]; then
    say "making .venv again: it was made with ${have} and this setup uses 3.12 $BASE"
    rm -rf .venv
  fi
fi
if [[ ! -x .venv/bin/python ]]; then
  say "creating .venv"
  "$PY" -m venv .venv || { echo "Could not create .venv with $PY" >&2; exit 1; }
fi

# Packages, only when requirements.txt or pyproject.toml changed ------------------------------
STAMP=.venv/.wfglink_install
WANT="$("$PY" - requirements.txt pyproject.toml <<'EOF'
import hashlib, sys
h = hashlib.sha256()
for name in sys.argv[1:]:
    with open(name, "rb") as f:
        h.update(f.read())
print(h.hexdigest()[:16])
EOF
)"
if [[ -z "$WANT" ]]; then
  echo "Could not read requirements.txt and pyproject.toml in $WFG" >&2
  exit 1
fi
if [[ "$(cat "$STAMP" 2>/dev/null)" == "$WANT" ]]; then
  say "packages already installed (requirements.txt and pyproject.toml unchanged)"
else
  say "installing packages (5 to 10 minutes the first time; needs internet)..."
  T0=$(date +%s)
  if .venv/bin/python -m pip install --quiet --upgrade pip &&
     .venv/bin/python -m pip install -r requirements.txt &&
     .venv/bin/python -m pip install --quiet -e . --no-deps; then
    echo "$WANT" >"$STAMP"
    say "installed in $(( $(date +%s) - T0 )) s"
  else
    echo "Install failed. Check the internet connection and run ./scripts/setup_mac.sh again; the lines above show the error." >&2
    exit 1
  fi
fi

# Folders -------------------------------------------------------------------------------------
mkdir -p data/raw logs results/validation

# Booth clips ---------------------------------------------------------------------------------
if (( NO_CLIPS )); then
  say "booth clips not checked (--no-clips)"
else
  # One line per missing playlist clip: its id, and "yes" when data/clips_manifest.yaml can download it.
  MISSING="$(.venv/bin/python - <<'EOF' 2>/dev/null
from wfglink.doctor import playlist_clips
for c in playlist_clips()["clips"]:
    if not c["present"]:
        print(c["id"], "yes" if c["downloadable"] else "no")
EOF
)"
  FETCH=()
  while read -r id can; do
    [[ -z "$id" ]] && continue
    if [[ "$can" == "yes" ]]; then FETCH+=("$id"); else warn "playlist clip $id is not in data/clips_manifest.yaml: copy its file into data/raw by hand"; fi
  done <<<"$MISSING"
  if (( ${#FETCH[@]} == 0 )); then
    say "booth clips: nothing to download"
  elif ! curl -sS -o /dev/null --max-time 10 -I https://upload.wikimedia.org/ 2>/dev/null; then
    warn "no network: ${#FETCH[@]} booth clips not downloaded (${FETCH[*]}). Run ./scripts/setup_mac.sh again when online."
  else
    say "downloading ${#FETCH[@]} booth clips: ${FETCH[*]}"
    KEEP="$(mktemp -d)"
    cp data/clips.csv data/SOURCES.md "$KEEP"/ 2>/dev/null
    .venv/bin/python scripts/fetch_clips.py --only "${FETCH[@]}" ||
      warn "some booth clips did not download (see above). Run ./scripts/setup_mac.sh again later."
    cp "$KEEP"/clips.csv data/clips.csv 2>/dev/null
    cp "$KEEP"/SOURCES.md data/SOURCES.md 2>/dev/null
    rm -rf "$KEEP"
  fi
fi

# Camera permission (macOS) ---------------------------------------------------------------------
# The first time, macOS shows "Terminal would like to access the camera": click Allow. Later
# runs only list the cameras. A missing camera or permission is reported by the doctor below.
if [[ "$(uname)" == "Darwin" ]]; then
  echo
  say "camera permission and the booth camera (click Allow if macOS asks):"
  .venv/bin/python -m wfglink cameras --request ||
    warn "no usable camera or no permission yet: the camera line of the doctor below says how to fix it"
fi

# Doctor and the next commands ------------------------------------------------------------------
echo
.venv/bin/python -m wfglink doctor
DOC=$?
echo
if (( DOC == 0 )); then
  say "done: every check is OK."
else
  say "done, but some checks FAILed: each FAIL line above says how to fix it; then run ./scripts/setup_mac.sh again."
fi
echo "Next, in this Terminal window:"
echo "  source .venv/bin/activate"
echo "  python -m wfglink live --synthetic"
exit $(( DOC == 0 ? 0 : 1 ))
