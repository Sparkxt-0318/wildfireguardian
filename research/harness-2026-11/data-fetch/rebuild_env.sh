#!/usr/bin/env bash
# One-command environment rebuild for forecast/wildfire/environment.py, outside git.
#
#   rebuild_env.sh WORKSPACE --project EVENT_ID [EVENT_ID ...]   # one of the 44 Choi events (grid from the Choi archive)
#   rebuild_env.sh WORKSPACE --nirops ALLOWLIST INCIDENT [...]    # NIROPS incidents (grid + labels by build_nirops_event.py)
#
# Stages are run with the repo's own code: weather, boundary_layer, terrain, canopy, gridmet, landfire, landcover,
# biome, enrich-data. A failing stage is reported and the script continues. Needs python3.12 and uv.
# Downloads go to WORKSPACE (Choi archive 1.5 MB, NIROPS 1.39 GB if --nirops, ecoregions 376 MB, LANDFIRE CSV 3.4 MB).
set -u
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../../.." && pwd)
WS=$(mkdir -p "$1" && cd "$1" && pwd); shift; MODE=$1; shift
PY=$WS/.venv/bin/python
if [ ! -x "$PY" ]; then
  uv venv -q -p 3.12 "$WS/.venv"
  uv pip install -q -p "$PY" numpy==1.26.4 pandas==2.2.3 scipy==1.13.1 rasterio==1.4.3 affine==3.0.1 \
    requests==2.34.2 pyproj==3.7.0 pyshp==2.3.1 shapely==2.0.6 pyogrio==0.10.0 geopandas==1.0.1
  uv pip install -q -p "$PY" torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple
fi
rm -rf "$WS/wildfire"; cp -r "$REPO/forecast/wildfire" "$WS/"
ENV=$WS/data/environment; mkdir -p "$ENV/sources" "$WS/dl"
python3 "$HERE/fetch.py" get landfire_consume_loadings --dest "$ENV/sources"
python3 "$HERE/fetch.py" get toa_kriging_choi2026 --dest "$WS/dl"
mkdir -p "$WS/data/sources/zenodo_21788344/extracted"
[ -d "$WS/data/sources/zenodo_21788344/extracted/rasters_us" ] || unzip -qo "$WS/dl/wildfire_toa_dataset_and_code.zip" -d "$WS/data/sources/zenodo_21788344/extracted"

if [ "$MODE" = --project ]; then
  (cd "$WS" && "$PY" -m wildfire environment inventory)        # writes all 44 Choi grids; events.json kept to the requested ids below
  "$PY" - "$ENV/events.json" "$@" <<'EOF'
import json, sys
p, keep = sys.argv[1], set(sys.argv[2:])
ev = [e for e in json.load(open(p)) if e['id'] in keep]
assert len(ev) == len(keep), 'unknown event id'
json.dump(ev, open(p, 'w'), indent=1)
EOF
elif [ "$MODE" = --nirops ]; then
  ALLOW=$1; shift
  python3 "$HERE/fetch.py" get nirops_2020_2024_perimeters --dest "$WS/dl"
  SHP=$WS/dl/nirops/NIROPS_2020_2024_R1_R6/NIROPS_2020_2024_R1_R6.shp
  [ -f "$SHP" ] || unzip -qo "$WS/dl/NIROPS_2020_2024_R1_R6.zip" -d "$WS/dl/nirops"
  for inc in "$@"; do "$PY" "$HERE/build_nirops_event.py" "$inc" --shp "$SHP" --allowlist "$ALLOW" --workspace "$WS" || exit 1; done
else
  echo "usage: rebuild_env.sh WORKSPACE --project ID... | --nirops ALLOWLIST INCIDENT..." >&2; exit 2
fi

cd "$WS"
for st in weather boundary_layer terrain canopy gridmet landfire landcover; do
  s=$(date +%s); "$PY" -m wildfire environment $st > "log_$st.txt" 2>&1; rc=$?
  echo "STAGE $st rc=$rc $(( $(date +%s) - s ))s :: $(grep -v '^\s*$' log_$st.txt | tail -1 | cut -c1-160)"
done
for st in biome enrich-data; do
  s=$(date +%s); "$PY" -m wildfire $st > "log_$st.txt" 2>&1; rc=$?
  echo "STAGE $st rc=$rc $(( $(date +%s) - s ))s :: $(grep -v '^\s*$' log_$st.txt | tail -1 | cut -c1-160)"
done
# Pins manifest for pipeline.Environment(input_sha256=...) / --input-manifest (paths relative to data/)
"$PY" "$HERE/make_input_manifest.py" "$ENV" "$WS/data/input_manifest.json"
