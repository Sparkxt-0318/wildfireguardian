#!/usr/bin/env bash
# Run a wfglink command on exactly the committed HEAD, whatever is uncommitted in the checkout.
#
#   bash wfglink/scripts/run_from_head.sh python scripts/run_suite.py core --record
#
# HEAD's wfglink folder is exported with git archive into a temporary folder. data/raw,
# data/synthetic and results are linked to the checkout's, so inputs are found
# and outputs (including results/NUMBERS.json) land in the checkout. Recorded numbers carry
# HEAD's commit (WFGLINK_EXPORT_COMMIT) and count as clean, because the code that ran is
# exactly that commit. The first word "python" means the checkout's venv Python.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(git -C "$ROOT" rev-parse --show-toplevel)"
COMMIT="$(git -C "$REPO" rev-parse HEAD)"
EXPORT="$(mktemp -d)"
trap 'rm -rf "$EXPORT"' EXIT
git -C "$REPO" archive "$COMMIT" wfglink | tar -x -C "$EXPORT"
W="$EXPORT/wfglink"
mkdir -p "$W/data"
for d in raw synthetic; do
  [[ -e "$ROOT/data/$d" ]] && ln -s "$ROOT/data/$d" "$W/data/$d"
done
rm -rf "$W/results"
ln -s "$ROOT/results" "$W/results"
ln -s "$ROOT/.venv" "$W/.venv"
cmd=("$@")
[[ "${cmd[0]}" == "python" ]] && cmd[0]="$ROOT/.venv/bin/python"
echo "run_from_head: ${COMMIT:0:7} in $W" >&2
cd "$W"
WFGLINK_EXPORT_COMMIT="$COMMIT" PYTHONPATH="$W/src" "${cmd[@]}"
