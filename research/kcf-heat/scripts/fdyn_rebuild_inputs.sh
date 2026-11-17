#!/usr/bin/env bash
# Rebuild F-DYN's gitignored _data/ (everything the multi-hour HEADLINE packets need) from this repository's own
# branches, in a scratch checkout of the F-DYN commit F-3.1's headline batch used (819bcb91, "leo819").
#
#   scripts/fdyn_rebuild_inputs.sh REPO DEST ROUTING_DATA PY
#
# REPO          a clone of this repository with these refs fetched (history of leo/f-c1-see-before-leave back to
#               2026-11-12; git fetch --shallow-since=2026-11-09 works on a shallow clone):
#               origin/leo/f-c1-see-before-leave (819bcb91), origin/daniel/data-fetch, origin/daniel/data-fetch-2
# DEST          new directory for the checkout (about 400 MB, plus one packet at a time while the batch runs)
# ROUTING_DATA  the frozen routing inputs (tools/fetch_routing_inputs.py), linked as DEST/data/routing
# PY            a Python with numpy, pandas, pyproj, rasterio, scipy (the F-DYN builders' imports)
#
# Inputs, all from the repository:
#   Choi, Seo & Cha 2026 TOA/std rasters (Zenodo 10.5281/zenodo.21788344, CC-BY-4.0): daniel/data-fetch small/choi2026_kfs01
#   NASA FIRMS 2025 Republic of Korea CSVs (VIIRS S-NPP, NOAA-20, MODIS): daniel/data-fetch small/firms
#   Himawari AHI KFS_01 scans (2 windows used by sound.py): daniel/data-fetch-2 ahi_kfs01
# Checks printed: TOA sha256 = build.py's KRIGED_TOA_SHA256; FIRMS stats; envelope_sound_counts.json identical to the
# committed file; burn set 16,176 cells; INSTANCE 12 instances / 1,044 origin-instances.
set -euo pipefail
REPO=$1; DEST=$2; RD=$3; PY=$4
C=819bcb91
mkdir -p "$DEST"
git -C "$REPO" archive "$C" | tar -x -C "$DEST" --exclude='forecast/*' --exclude='monte-carlo-extension/*' \
  --exclude='hardware/*' --exclude='research/sipp-routing/*' --exclude='research/forecast-v2/*' --exclude='research/next-combined/*'
mkdir -p "$DEST/data"; ln -sfn "$RD" "$DEST/data/routing"
P=research/harness-2026-11/F-DYN; D=$DEST/$P/_data
mkdir -p "$D/firms" "$D/ahi"
DF=research/harness-2026-11/data-fetch/small
for f in KFS_01_pswt_ok_toa.tif KFS_01_pswt_ok_std.tif; do git -C "$REPO" show "origin/daniel/data-fetch:$DF/choi2026_kfs01/$f" > "$D/$f"; done
for f in viirs-snpp viirs-jpss1 modis; do git -C "$REPO" show "origin/daniel/data-fetch:$DF/firms/${f}_2025_Republic_of_Korea.csv" > "$D/firms/$f.csv"; done
for f in kfs01_ahi_20250324T06_20250324T18.npz kfs01_ahi_20250324T18_20250325T18.npz; do
  git -C "$REPO" show "origin/daniel/data-fetch-2:research/harness-2026-11/data-fetch-2/ahi_kfs01/$f" > "$D/ahi/$f"; done
cd "$DEST"
echo "TOA sha256: $(shasum -a 256 $P/_data/KFS_01_pswt_ok_toa.tif | cut -c1-64) (want fe81f945ddb9dd68f9de27b5865ca12d1a345934540934b723bd66b7d01fa953)"
"$PY" -I $P/fdyn/variants.py --toa $P/_data/KFS_01_pswt_ok_toa.tif --firms-dir $P/_data/firms --out-dir $P/_data/variants
"$PY" -I $P/fdyn/sound.py --data $P/_data --ahi-results $P/ahi_results --out-dir $P/_data/variants > /dev/null
"$PY" -c "import json,sys; a=json.load(open('$P/envelope_sound_counts.json')); b=json.load(open('$P/_data/variants/envelope_sound_counts.json')); print('envelope_sound_counts identical to committed:', a == b)"
"$PY" -I $P/fdyn/burnset.py --burn-set-from $P/_data/variants/envelope_sound_lo.npz --out-dir $P/_data/variants
for r in uiseong_andong_2025 yeongdeok_2025; do
  mkdir -p $P/_data/graphs_interim/$r
  "$PY" -I $P/fdyn/regrid_graph.py --region $r --out $P/_data/graphs_interim/$r/graph.json
done
"$PY" -I $P/fdyn/instance.py --out $P/_data/INSTANCE.json
