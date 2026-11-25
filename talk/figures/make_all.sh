#!/usr/bin/env bash
# Rebuild every talk figure, the editable pptx, the docs, the contact sheet and the zip.
set -euo pipefail
cd "$(dirname "$0")/../.."                      # repository root
PY=.venv-fig/bin/python
if [ ! -x "$PY" ]; then
  python3 -m venv .venv-fig
  .venv-fig/bin/pip install -q matplotlib numpy pandas pillow python-pptx pyproj tifffile
fi
export MPLCONFIGDIR="${TMPDIR:-/tmp}/mpl-talk-figures"
# read-only files of the data repository (not committed here)
WGD=talk/figures/.cache/wgd
if [ ! -f "$WGD/COMMITS.txt" ]; then
  mkdir -p "$WGD"
  for f in release/records-v0.1/run_summary_us.json release/live-v0.1/onset_labels.csv \
           release/records-v0.1/patches_us.jsonl.gz results/HEADLINE_NUMBERS.md results/RECORDS_RESULTS.md; do
    gh api -H "Accept: application/vnd.github.raw" "repos/Sparkxt-0318/wildfireguardiandata/contents/$f" > "$WGD/$(basename "$f")"
    echo "$f $(gh api "repos/Sparkxt-0318/wildfireguardiandata/commits?path=$f&per_page=1" --jq '.[0].sha[0:8]')" >> "$WGD/COMMITS.txt"
  done
fi
git fetch -q origin "research/kcf-fastpath:refs/remotes/origin/research/kcf-fastpath" || true
# F04 inputs: the deadline field (needs the frozen road graph, tools/fetch_routing_inputs.py) and the M548 run (needs the
# forecast workspace and a Python 3.12 venv with its pinned packages, DECISIONS.md D29). Both write committed files in
# build/, so they are skipped when their input is not on the machine.
if [ -f "${WFG_ROUTING:-/Users/jp/wildfireguardian-forecast/data/routing}/graphs/uiseong_andong_2025/graph.json" ]; then
  "$PY" talk/figures/src/F04_routing.py
fi
if [ -f "${WFG_ROUTING:-/Users/jp/wildfireguardian-forecast/data/routing}/graphs/uiseong_andong_2025/graph.json" ]; then
  PYTHONDONTWRITEBYTECODE=1 "$PY" talk/figures/src/F07_map_data.py      # inputs of F07_map and F08_map
fi
if [ -x .venv-model/bin/python ] && [ -d "${WILDFIRE:-/Users/jp/Desktop/wildfire}" ]; then
  PYTHONDONTWRITEBYTECODE=1 .venv-model/bin/python talk/figures/src/F04_forecast.py
fi
for s in F01_title_map F02_road_cut F03_comparison_grid F04_overview F05_data_foundation F06_safety_distance F07_forward_backward F07_map \
         F08_backward_step_checker F08_map F09_speed F09b_speed_fastpath F10_camp_fire F11a_village_card F12_forecast_example \
         F13_kernels F14_reliability F15_exposure F16_safety_zones; do
  "$PY" "talk/figures/src/$s.py"
done
"$PY" talk/figures/src/build_pptx.py
"$PY" talk/figures/src/make_docs.py
