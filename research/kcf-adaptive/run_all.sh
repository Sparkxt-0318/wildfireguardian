#!/usr/bin/env bash
# Full kcf-adaptive pipeline. WORK is scratch (about 1 GB). Needs network access to zenodo.org and
# archive-api.open-meteo.com, Python 3.12 with: numpy 1.26.4, pandas, scipy, rasterio, pyproj, geopandas, pyogrio,
# shapely, torch 2.5.1, numba 0.60, matplotlib, pytest.
# About 25 CPU-hours in total (Arm 1 adaptation and its leakage reruns are almost all of it).
set -euo pipefail
WORK=${1:?work dir}; PY=${PY:-python3}
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd); H=$REPO/research/harness-2026-11
cd "$HERE"; mkdir -p "$WORK/dl" "$WORK/data/gofer" "$WORK/data/choi" derived

# ---- data
$PY "$H/data-fetch/fetch.py" get gofer_v0.2 --dest "$WORK/dl"
$PY "$H/data-fetch/fetch.py" get toa_kriging_choi2026 --dest "$WORK/dl"
unzip -qo "$WORK/dl/GOFER.zip" -d "$WORK/data/gofer"
unzip -qo "$WORK/dl/wildfire_toa_dataset_and_code.zip" -d "$WORK/data/choi"
$PY ../kcf-margin/score_gofer.py --gofer "$WORK/data/gofer/GOFER" --out "$WORK"          # arrival grids (kcf-margin code)

# ---- Arm 1
$PY arm1_output.py --out derived/arm1_output.json                                         # output-level (1-F), no weather
mkdir -p "$WORK/envroot/sources/zenodo_21788344"
ln -sfn "$WORK/data/choi" "$WORK/envroot/sources/zenodo_21788344/extracted"
US6="ID-BOF-000683_Wapiti_Wapiti ID-BOF-000904_Goat ID-BOF-001080_Lava ID-SCF-240202_RedRock WA-SES-000173_Pioneer WY-BTF-002416_FishCreek"
(cd "$REPO" && $PY research/forecast-v2/scripts/rebuild_environment.py --root "$WORK/envroot/environment_public" \
   --zenodo "$WORK/envroot/sources/zenodo_21788344/extracted" --events $US6 --stages inventory weather)
$PY build_env.py --root "$WORK/envroot/environment_public" --out "$WORK/env"
run() { $PY arm1_run.py --env "$WORK/env" --set "$1" --mode "$2" --out "$WORK/arm1/$3" --penalty "$4" ${5:-}; }
run P4 real P4_real 0.01 &  run P+ real P+_real 0.01 &  run P4 real P4_pen1e-3 0.001 &  run P4 real P4_pen1e-4 0.0001 &  wait
run P4 scramble P4_scramble 0.01 &  run P+ scramble P+_scramble 0.01 &
run P4 real leak_real 0.01 --leak &  run P4 scramble leak_scramble 0.01 --leak &  wait
$PY arm1_eval.py --env "$WORK/env" --runs "$WORK/arm1" --out derived/arm1.json

# ---- Arm 2
$PY fetch_wind.py --work "$WORK" --choi "$WORK/data/choi" --out derived/wind.csv.gz
$PY arm2_scores.py --work "$WORK" --choi "$WORK/data/choi" --wind derived/wind.csv.gz --out "$WORK/arm2_scores"
$PY arm2_eval.py --work "$WORK" --choi "$WORK/data/choi" --scores "$WORK/arm2_scores" --out derived/arm2.json

# ---- report
$PY make_numbers.py
$PY figures.py
$PY -m pytest -q tests -p no:cacheprovider
