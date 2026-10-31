#!/usr/bin/env bash
# End-to-end FIXTURE smoke run of the track 1B pipeline (synthetic environment, real NIROPS labels).
# Usage: bash research/forecast-v2/scripts/fixture_smoke.sh VENV_PYTHON DATA_DIR
set -euo pipefail
PY="$1"
DATA="$2"
HERE="$(cd "$(dirname "$0")" && pwd)"
COMMON=(--data-root "$DATA/fixture_root" --perimeters "$DATA/perimeters" --work "$DATA/work_fixture" --run "$DATA/run_fixture" --threads 2)
export OMP_NUM_THREADS=2
"$PY" "$HERE/pipeline.py" fold "${COMMON[@]}" --variant base --fold 2022 --epochs 1 --intervals-per-epoch 16
"$PY" "$HERE/pipeline.py" fold "${COMMON[@]}" --variant burnout_spotting --fold 2022 --epochs 1 --intervals-per-epoch 8
"$PY" "$HERE/pipeline.py" fold "${COMMON[@]}" --variant d4_wind --fold 2022 --epochs 1 --intervals-per-epoch 8
"$PY" "$HERE/pipeline.py" baselines "${COMMON[@]}"
"$PY" "$HERE/pipeline.py" final "${COMMON[@]}" --variant base --epochs 1 --intervals-per-epoch 16
"$PY" "$HERE/pipeline.py" heldout "${COMMON[@]}" --n-samples 32 --events ID-BOF-000904_Goat
echo FIXTURE_SMOKE_DONE
