#!/usr/bin/env bash
# Reproduce kcf-abstain end to end (PROTOCOL.md, commit ef50d2a).
#   research/kcf-abstain/run_all.sh WORK_DIR
# WORK_DIR receives the downloads (about 260 GB is streamed, about 4 GB is kept) and the unpacked archives.
# Needs: numpy scipy pandas pygrib rasterio pyproj shapely geopandas matplotlib; network access to
# noaa-gfs-bdp-pds.s3.amazonaws.com, noaa-hrrr-bdp-pds.s3.amazonaws.com and zenodo.org.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
W="${1:?usage: run_all.sh WORK_DIR}"
mkdir -p "$W/dl_choi" "$W/dl_gofer" "$W/x_choi" "$W/x_gofer" "$W/nwp"
FETCH="$HERE/../harness-2026-11/data-fetch/fetch.py"
python3 "$FETCH" get toa_kriging_choi2026 --dest "$W/dl_choi"     # checksums verified by fetch.py
python3 "$FETCH" get gofer_v0.2 --dest "$W/dl_gofer"
unzip -q -o "$W/dl_choi/wildfire_toa_dataset_and_code.zip" -d "$W/x_choi"
unzip -q -o "$W/dl_gofer/GOFER.zip" -d "$W/x_gofer"

F="python3 $HERE/fetch_nwp.py"
# HRRR: GOFER 2019-2020 and the 2020 catalog fires
$F --model hrrr --region WUS --start 2019-09-04T06 --end 2019-09-12T18 --out "$W/nwp"
$F --model hrrr --region WUS --start 2019-10-23T18 --end 2019-10-29T12 --out "$W/nwp"
$F --model hrrr --region WUS --start 2020-07-22T06 --end 2020-11-09T12 --out "$W/nwp"
$F --model hrrr --region WUS --start 2020-11-09T12 --end 2020-11-22T06 --out "$W/nwp"
# GFS: GOFER 2021 and US 2021, US 2022, US 2024; Korea 2022, 2023, 2025
$F --model gfs --region WUS --start 2021-06-30T12 --end 2021-10-13T12 --out "$W/nwp"
$F --model gfs --region WUS --start 2022-04-06T18 --end 2022-10-29T00 --out "$W/nwp"
$F --model gfs --region WUS --start 2024-06-11T18 --end 2024-10-28T12 --out "$W/nwp"
for r in "2022-02-14T06 2022-02-17T00" "2022-03-03T18 2022-03-12T12" "2022-04-09T18 2022-04-11T12" \
         "2022-05-27T18 2022-06-02T12" "2023-03-07T18 2023-03-09T18" "2023-04-01T18 2023-04-04T00" \
         "2025-03-21T00 2025-04-01T00" "2025-04-27T18 2025-04-30T12"; do
  set -- $r; $F --model gfs --region KOR --start "$1" --end "$2" --out "$W/nwp"
done

cd "$HERE"
python3 fire_hours.py --gofer "$W/x_gofer/GOFER" --choi "$W/x_choi" --out derived/hours_base.csv.gz
python3 predictors.py --hours derived/hours_base.csv.gz --nwp "$W/nwp" --out "$W/hours_pred.csv.gz"
python3 abstain.py --hours "$W/hours_pred.csv.gz" --out-json "$W/abstain_numbers.json" --out-hours "$W/hours_full.csv.gz"
python3 evt.py --out derived/evt.json
python3 make_numbers.py --abstain "$W/abstain_numbers.json" --evt derived/evt.json --hours "$W/hours_full.csv.gz" \
  --nwp "$W/nwp" --out numbers.json --hours-out derived/hours.csv.gz
python3 figures.py --numbers numbers.json --fig fig
python3 -m pytest -q tests
