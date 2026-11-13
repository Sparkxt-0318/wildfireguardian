#!/usr/bin/env bash
# Non-weather build of the S-D9 part-a pool (allowlist only). Weather comes later on its quota day.
cd $SCRATCH/parta
SHP="$SCRATCH/dl/nirops/x/NIROPS_2020_2024_R1_R6/NIROPS_2020_2024_R1_R6.shp"
n=0; for inc in $(tail -n +2 PART_A_ALLOWLIST_FINAL.csv | cut -d, -f1); do
  n=$((n+1)); $SCRATCH/envpilot/.venv/bin/python /home/user/wildfireguardian/research/harness-2026-11/data-fetch/build_nirops_event.py "$inc" --shp "$SHP" --allowlist PART_A_ALLOWLIST_FINAL.csv --workspace $SCRATCH/parta > /dev/null 2>> build_err.log || echo "FAIL $inc" >> build_fail.txt
  [ $((n % 25)) -eq 0 ] && echo "BUILT $n $(date -u +%H:%M)"
done
echo "GRIDS DONE $n $(date -u +%H:%M)"
for st in terrain landcover; do s=$(date +%s); $SCRATCH/envpilot/.venv/bin/python -m wildfire environment $st > log_$st.txt 2>&1; echo "STAGE $st rc=$? $(( $(date +%s)-s ))s"; done
s=$(date +%s); $SCRATCH/envpilot/.venv/bin/python -m wildfire biome > log_biome.txt 2>&1; echo "STAGE biome rc=$? $(( $(date +%s)-s ))s"
echo ALLDONE
