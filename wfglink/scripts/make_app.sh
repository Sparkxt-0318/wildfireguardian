#!/usr/bin/env bash
# Build WFGLink.app in py2app alias mode (macOS only). Takes a few seconds.
# Output: wfglink/dist/WFGLink.app. Rebuilding requires granting camera permission again.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname)" != "Darwin" ]]; then
  echo "make_app.sh: macOS only" >&2
  exit 1
fi
PY=".venv/bin/python"
[[ -x "$PY" ]] || { echo "make_app.sh: run scripts/sitting1.sh (or create .venv) first" >&2; exit 1; }
rm -rf build/app dist/WFGLink.app
mkdir -p build dist
"$PY" packaging/setup_app.py py2app -A --dist-dir dist --bdist-base build/app >build/make_app.log 2>&1 || {
  echo "make_app.sh: py2app failed; see wfglink/build/make_app.log" >&2
  tail -20 build/make_app.log >&2
  exit 1
}
/usr/libexec/PlistBuddy -c "Print :NSCameraUseContinuityCameraDeviceType" dist/WFGLink.app/Contents/Info.plist >/dev/null
echo "Built $(pwd)/dist/WFGLink.app (alias mode)"
