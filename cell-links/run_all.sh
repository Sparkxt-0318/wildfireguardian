#!/usr/bin/env bash
# Reproduce every result in cell-links/ from scratch (about 25 minutes on 4 cores).
# Requires the DEM tiles and the OpenMRG zip in data/raw/ (see README.md for download commands).
set -euo pipefail
cd "$(dirname "$0")"
if ! git diff --quiet HEAD -- src configs; then
  echo "Commit src/ and configs/ first so NUMBERS.json can name the producing commit." >&2
  exit 1
fi
export CELL_LINKS_COMMIT="$(git rev-parse --short=12 HEAD)"
PY=.venv/bin/python
rm -f results/NUMBERS.json
$PY src/run_geometry.py
$PY src/run_physics.py
$PY src/run_crossings.py
$PY -I src/run_detection.py
$PY -I src/run_confounders.py
$PY -I src/run_extras.py
echo "Done. Numbers pinned to commit $CELL_LINKS_COMMIT"
