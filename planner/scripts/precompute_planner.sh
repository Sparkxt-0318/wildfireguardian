#!/usr/bin/env bash
# Booth cache: precompute every origin of 의성·안동 and 영덕 for all recorded scenario sets through the
# REAL Route-Check API, on the evaluated host (Apple M5 Pro, native macOS).
#
#   1) terminal 1, repository root:  make api            (real API on http://127.0.0.1:8765/v1)
#   2) terminal 2, repository root:  planner/scripts/precompute_planner.sh
#
# Resumable: interrupt it at any time (Ctrl-C, sleep, API restart) and run the same command again; finished
# dispatch plans and checks are kept in planner/cache/.state/ and are not recomputed. A scenario set whose
# cache file is already complete is skipped.
#
# Options (environment):
#   WFG_API_BASE=http://127.0.0.1:8765/v1   API base URL
#   REGIONS=uiseong_andong_2025,yeongdeok_2025
#   STEP_MIN=10                              departure offset step (minutes)
#   SHELTERS_PER_ORIGIN=3                    nearest shelters checked per origin
#   RECHECK_TIMEOUTS=1                       afterwards, re-check unresolved/TIMEOUT attempts one at a time
#   ALLOW_NON_MAC=0                          set to 1 to run on another host (results are then for testing only)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLANNER="$(cd "$HERE/.." && pwd)"
API="${WFG_API_BASE:-http://127.0.0.1:8765/v1}"
REGIONS="${REGIONS:-uiseong_andong_2025,yeongdeok_2025}"
STEP_MIN="${STEP_MIN:-10}"
K="${SHELTERS_PER_ORIGIN:-3}"
RECHECK="${RECHECK_TIMEOUTS:-1}"
OUT="$PLANNER/cache"
PY="${PYTHON:-python3}"
mkdir -p "$OUT/.state"
LOG="$OUT/.state/precompute-$(date +%Y%m%dT%H%M%S).log"

health="$(curl -fsS --max-time 10 "$API/health" || true)"
if [[ -z "$health" ]]; then
  echo "ERROR  No Route-Check API at $API. Start it first in the repository root: make api" >&2
  exit 1
fi
"$PY" - "$health" "${ALLOW_NON_MAC:-0}" <<'PYEOF'
import json, sys
h = json.loads(sys.argv[1]); allow = sys.argv[2] == '1'
if h.get('mode') == 'mock' or h.get('mock') is True:
    sys.exit('ERROR  This is the MOCK server (recorded results only). The booth cache must come from the real API.')
if h.get('status') != 'ok':
    sys.exit('ERROR  API health is %r: %s' % (h.get('status'), h.get('issues')))
host = (h.get('provenance') or {}).get('host') or {}
plat = str(host.get('platform', '')); mach = str(host.get('machine', ''))
print('API    version %s · git %s · workers %s · host %s %s' % (h.get('api_version'), h.get('git_commit', '')[:12],
      h.get('workers'), plat, mach))
if not (plat.startswith('macOS') or 'Darwin' in plat) or mach != 'arm64':
    msg = 'This API host is not native macOS arm64; its results are for testing only, not the booth cache.'
    if not allow:
        sys.exit('ERROR  ' + msg + ' Set ALLOW_NON_MAC=1 to run anyway.')
    print('WARN   ' + msg)
PYEOF

KEEP_AWAKE=()
if command -v caffeinate >/dev/null 2>&1; then KEEP_AWAKE=(caffeinate -dims); fi

echo "LOG    $LOG"
"$PY" "$HERE/precompute.py" --api "$API" --regions "$REGIONS" --plan-only --step-min "$STEP_MIN" --k "$K" 2>&1 | tee -a "$LOG"
set +e
"${KEEP_AWAKE[@]}" "$PY" "$HERE/precompute.py" --api "$API" --regions "$REGIONS" --step-min "$STEP_MIN" --k "$K" \
  --out "$OUT" 2>&1 | tee -a "$LOG"
rc=${PIPESTATUS[0]}
if [[ $rc -eq 0 && "$RECHECK" == "1" ]]; then
  "${KEEP_AWAKE[@]}" "$PY" "$HERE/precompute.py" --api "$API" --regions "$REGIONS" --step-min "$STEP_MIN" --k "$K" \
    --out "$OUT" --recheck-timeouts 2>&1 | tee -a "$LOG"
  rc=${PIPESTATUS[0]}
fi
set -e
if [[ $rc -ne 0 ]]; then
  echo "STOPPED (exit $rc). Run the same command again to resume." >&2
  exit "$rc"
fi

"$PY" - "$OUT/INDEX.json" <<'PYEOF'
import json, sys
rows = json.load(open(sys.argv[1]))
total = 0
for r in rows:
    total += r.get('bytes', 0)
    print('CACHE  %-22s %s  %5.1f MB  %s' % (r['region_id'], r['input_time'], r.get('bytes', 0) / 1e6, r.get('verdicts')))
print('CACHE  total %.1f MB' % (total / 1e6))
big = [r for r in rows if r.get('bytes', 0) > 50 * 1024 * 1024]
if big:
    print('NOTE   files over 50 MB must go to Git LFS or a Release asset, not a normal commit:', [r['path'] for r in big])
PYEOF
cat <<EOF
DONE   Commit the booth cache (the .state/ folder is ignored):
         git add planner/cache/INDEX.json planner/cache/uiseong_andong_2025 planner/cache/yeongdeok_2025
         git commit -m "planner: booth cache from the evaluated host"
EOF
