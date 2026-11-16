#!/usr/bin/env bash
# Full kcf-margin pipeline. DATA holds GOFER/ and NIROPS_2020_2024_R1_R6/ (fetch with
# research/harness-2026-11/data-fetch/fetch.py get gofer_v0.2 nirops_2020_2024_perimeters). WORK is scratch.
set -euo pipefail
DATA=${1:?data dir}; WORK=${2:?work dir}
cd "$(dirname "$0")"
H=../harness-2026-11
python3 score_gofer.py --gofer "$DATA/GOFER" --out "$WORK"                      # ~5 min
python3 fetch_gusts.py --gofer "$DATA/GOFER" --out "$WORK/gofer_gusts.csv.gz"
python3 score_nirops.py --shp "$DATA/NIROPS_2020_2024_R1_R6/NIROPS_2020_2024_R1_R6.shp" \
  --allowlist $H/S-D9/cohort/PART_A_ALLOWLIST_FINAL.csv --out "$WORK/nirops_pairs.csv.gz"
python3 score_gyeongbuk.py --small $H/data-fetch/small/firms --ahi $H/data-fetch-2/ahi_kfs01 --out "$WORK/gyeongbuk_reach.csv"
python3 calibrate.py --work "$WORK" --out numbers.json
python3 apply_frozen.py --work "$WORK" --numbers numbers.json
python3 route.py --work "$WORK" --out route.json --numbers numbers.json
python3 figures.py --numbers numbers.json --route route.json --out fig
python3 -m pytest -q tests -p no:cacheprovider
