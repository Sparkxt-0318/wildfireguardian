#!/usr/bin/env bash
# Reproduce every result and figure (SYNTHETIC). Run from last-gasp/: bash scripts/run_all.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
$PY scripts/01_build_world.py
$PY scripts/02_example_run.py --fire-seed 0 --obs-seed 0 --tag default
$PY scripts/02_example_run.py --fire-seed 0 --obs-seed 0 --tag tags50 --set observe.meter_fraction=0.0 observe.tag_fraction=0.5
$PY scripts/03_sweeps.py --fire-seeds 5 --obs-seeds 2 --workers 4
$PY scripts/04_figures_example.py
$PY scripts/05_figures_sweeps.py
$PY scripts/06_demo_sim.py --n-tags 25 --seeds 10
$PY scripts/07_numbers.py
