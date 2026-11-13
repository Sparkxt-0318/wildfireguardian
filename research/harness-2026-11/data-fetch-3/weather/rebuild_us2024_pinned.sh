#!/usr/bin/env bash
# Reproduce the pinned US2024 six-fire environment (pins: weather/pins/us2024_input_manifest_night1.json,
# sha256 286f4c47..., 347 files) in a fresh workspace, then verify every pin. Outside git; run as a tracked task.
#
#   rebuild_us2024_pinned.sh WORKSPACE
#
# What it does, in the order the pinned environment was made:
#  1. rebuild_env.sh --project <6 ids>, EXCEPT its 'weather' and 'boundary_layer' stages. In the pinned build those
#     two stages stopped on the Open-Meteo daily limit and wrote no pinned file; running them now would spend quota
#     and write files that are not in the pins. The edited copy is made at run time from data-fetch/rebuild_env.sh,
#     whose sha256 is checked first (4776dffe...).
#  2. weather_night.py (the night-1 driver) on a one-step plan for the 6 fires: slim weather, 3 channels.
#     Quota cost on 13 Nov: 13 requests, 662.58 weighted Open-Meteo calls (well under the 10,000/day limit).
#  3. make_input_manifest.py for the 6 fires, then a comparison with the committed pins: missing, extra, mismatched.
#
# Exit 0 only if all 347 pins match exactly and there is no extra pinned-class file.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../../../.." && pwd)
DF=$REPO/research/harness-2026-11/data-fetch
PINS=$HERE/pins/us2024_input_manifest_night1.json
IDS="ID-BOF-000683_Wapiti_Wapiti ID-BOF-000904_Goat ID-BOF-001080_Lava ID-SCF-240202_RedRock WA-SES-000173_Pioneer WY-BTF-002416_FishCreek"
WS=$(mkdir -p "$1" && cd "$1" && pwd)

echo "$(sha256sum "$DF/rebuild_env.sh" | cut -d' ' -f1)" | grep -q '^4776dffe593840fb4f957f092331746fd33b6e1fef5cf09b790fb612e26c55f2$' \
  || { echo "rebuild_env.sh is not the expected version (4776dffe...)"; exit 2; }
echo "$(sha256sum "$PINS" | cut -d' ' -f1)" | grep -q '^286f4c47d1c21d12485b4ec2079ce09c698c21af73d64037921b34284e6592c2$' \
  || { echo "pins file is not 286f4c47..."; exit 2; }

# 1. rebuild_env.sh without the weather / boundary_layer stages (HERE pinned to data-fetch/ so its helpers resolve)
NOW=$WS/rebuild_env_noweather.sh
sed -e "s#^HERE=.*#HERE=$DF; REPO=$REPO#" \
    -e 's/^for st in weather boundary_layer terrain canopy gridmet landfire landcover; do/for st in terrain canopy gridmet landfire landcover; do/' \
    "$DF/rebuild_env.sh" > "$NOW"
grep -q '^for st in terrain canopy gridmet landfire landcover; do' "$NOW" || { echo "stage-list edit did not apply"; exit 2; }
bash "$NOW" "$WS" --project $IDS || { echo "rebuild_env (no weather) failed"; exit 3; }

# 2. slim weather for the 6 fires with the night-1 driver (resumable; cached by request signature)
PLAN=$WS/plan_us2024.json
python3 -c "import json,sys; json.dump([{'workspace': sys.argv[1], 'events': sys.argv[2:]}], open(sys.argv[1]+'/plan_us2024.json','w'))" "$WS" $IDS
(cd "$WS" && WN_LOG="$WS/weather_requests.csv" WN_RUNLOG="$WS/weather_runlog.txt" \
   "$WS/.venv/bin/python" -I "$HERE/weather_night.py" "$PLAN") || { echo "weather step failed; see $WS/weather_runlog.txt"; exit 4; }

# 3. pins for the 6 fires, then compare with the committed manifest
"$WS/.venv/bin/python" -I "$DF/make_input_manifest.py" "$WS/data/environment" "$WS/pins_check.json" $IDS
python3 -I - "$PINS" "$WS/pins_check.json" <<'EOF'
import json, sys
a, b = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
missing = sorted(set(a) - set(b)); extra = sorted(set(b) - set(a))
mism = sorted(k for k in set(a) & set(b) if a[k] != b[k])
print(f"pinned {len(a)}  rebuilt {len(b)}  missing {len(missing)}  extra {len(extra)}  mismatched {len(mism)}")
for name, lst in (('MISSING', missing), ('EXTRA', extra), ('MISMATCH', mism)):
    for k in lst[:50]:
        print(name, k)
sys.exit(0 if not (missing or extra or mism) else 1)
EOF
