#!/usr/bin/env bash
# Booth cache: precompute every origin of 의성·안동 and 영덕 for all recorded scenario sets through the
# REAL Route-Check API, on the evaluated host (Apple M5 Pro, native macOS).
#
#   1) terminal 1: start the real Route-Check API (planner/README.md, "Real Route-Check API";
#      `make api` in a checkout that has the API, i.e. branch feat/api)
#   2) terminal 2, repository root:  planner/scripts/precompute_planner.sh
#
# Resumable: interrupt it at any time (Ctrl-C, sleep, API restart) and run the same command again; finished
# dispatch plans and checks are kept in <out>/.state/ and are not recomputed. A scenario set whose cache
# file is already complete is skipped.
#
# Output: planner/cache/ (the booth cache) only when the API host is native macOS on Apple silicon. On any
# other host (e.g. a Linux container) the script refuses, unless ALLOW_NON_MAC=1: the results are then TEST
# DATA and go to planner/.test-cache/ (ignored by Git, never shipped; view them with
# `WFG_CACHE_DIR=.test-cache npm run dev`).
#
# Options (environment):
#   WFG_API_BASE=http://127.0.0.1:8765/v1   API base URL
#   REGIONS=uiseong_andong_2025,yeongdeok_2025
#   STEP_MIN=10                              departure offset step (minutes)
#   SHELTERS_PER_ORIGIN=3                    nearest shelters checked per origin
#   RECHECK_TIMEOUTS=1                       afterwards, re-check unresolved/TIMEOUT attempts one at a time
#   ALLOW_NON_MAC=0                          set to 1 to run on another host (test data → planner/.test-cache)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLANNER="$(cd "$HERE/.." && pwd)"
API="${WFG_API_BASE:-http://127.0.0.1:8765/v1}"
REGIONS="${REGIONS:-uiseong_andong_2025,yeongdeok_2025}"
STEP_MIN="${STEP_MIN:-10}"
K="${SHELTERS_PER_ORIGIN:-3}"
RECHECK="${RECHECK_TIMEOUTS:-1}"
PY="${PYTHON:-python3}"

health="$(curl -fsS --max-time 10 "$API/health" || true)"
if [[ -z "$health" ]]; then
  if [[ -f "$PLANNER/../Makefile" ]] && grep -q '^api:' "$PLANNER/../Makefile"; then
    echo "ERROR  No Route-Check API at $API. Start it first in the repository root: make api" >&2
  else
    echo "ERROR  No Route-Check API at $API. This checkout has no API (it lives on branch feat/api)." >&2
    echo "       See planner/README.md, \"Real Route-Check API\", e.g.:" >&2
    echo "         git fetch origin feat/api && git worktree add --detach ../wfg-api origin/feat/api && (cd ../wfg-api && make api)" >&2
  fi
  exit 1
fi
# Host check BEFORE anything is written: prints "booth" (native macOS arm64) or "test" on the last line.
purpose="$("$PY" - "$health" "${ALLOW_NON_MAC:-0}" <<'PYEOF'
import json, sys
h = json.loads(sys.argv[1]); allow = sys.argv[2] == '1'
if h.get('mode') == 'mock' or h.get('mock') is True:
    sys.exit('ERROR  This is the MOCK server (recorded results only). The booth cache must come from the real API.')
if h.get('status') != 'ok':
    sys.exit('ERROR  API health is %r: %s' % (h.get('status'), h.get('issues')))
host = (h.get('provenance') or {}).get('host') or {}
plat = str(host.get('platform', '')); mach = str(host.get('machine', ''))
print('API    version %s · git %s · workers %s · host %s %s' % (h.get('api_version'), h.get('git_commit', '')[:12],
      h.get('workers'), plat, mach), file=sys.stderr)
if not (plat.startswith('macOS') or 'Darwin' in plat) or mach != 'arm64':
    msg = 'This API host is not native macOS arm64; its results are for testing only, not the booth cache.'
    if not allow:
        sys.exit('ERROR  ' + msg + ' Set ALLOW_NON_MAC=1 to write test data to planner/.test-cache instead.')
    print('WARN   ' + msg, file=sys.stderr)
    print('test')
else:
    print('booth')
PYEOF
)"
if [[ "$purpose" == "booth" ]]; then
  OUT="$PLANNER/cache"
else
  OUT="$PLANNER/.test-cache"
  echo "TEST   results go to planner/.test-cache (not the booth cache, never commit). View: WFG_CACHE_DIR=.test-cache npm run dev"
fi
mkdir -p "$OUT/.state"
LOG="$OUT/.state/precompute-$(date +%Y%m%dT%H%M%S).log"

KEEP_AWAKE=()
if command -v caffeinate >/dev/null 2>&1; then KEEP_AWAKE=(caffeinate -dims); fi

echo "LOG    $LOG"
"$PY" "$HERE/precompute.py" --api "$API" --regions "$REGIONS" --plan-only --step-min "$STEP_MIN" --k "$K" --out "$OUT" 2>&1 | tee -a "$LOG"
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
if [[ "$purpose" == "booth" ]]; then
  cat <<EOF
DONE   Commit the booth cache (the .state/ folder is ignored):
         git add planner/cache/INDEX.json planner/cache/uiseong_andong_2025 planner/cache/yeongdeok_2025
         git commit -m "planner: booth cache from the evaluated host"
EOF
else
  cat <<EOF
DONE   TEST DATA ONLY — computed on a non-evaluation host; do not commit and do not ship it as the booth cache.
         Results: planner/.test-cache/   View: WFG_CACHE_DIR=.test-cache npm run dev
EOF
fi
