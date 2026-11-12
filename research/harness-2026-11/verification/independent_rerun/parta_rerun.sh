#!/usr/bin/env bash
# Independent part-a rerun (Owen). One command, from a clean checkout:
#
#   research/harness-2026-11/verification/independent_rerun/parta_rerun.sh WORK_DIR [PYTHON]
#
# PYTHON must be the pinned environment (requirements-rerun.txt; Python 3.12, torch 2.5.1).
# Part a only. Keys are Incident_C. NIROPS is read only through nirops_access.py (ID column, then by fid).
# Exit codes: 0 = every stage ran and every hash matched; 1 = a mismatch or failure (fail closed);
#             3 = every runnable stage matched but PENDING inputs (PINS.json "pending") stop the rest.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(git -C "$HERE" rev-parse --show-toplevel)"
WORK="${1:?usage: parta_rerun.sh WORK_DIR [PYTHON]}"
PY="${2:-python3}"
mkdir -p "$WORK"; WORK="$(cd "$WORK" && pwd)"
PINS="$HERE/PINS.json"
log() { echo "[parta_rerun $(date -u +%H:%M:%SZ)] $*"; }
pin() { "$PY" -I -c "import json,sys;print(json.load(open('$PINS'))$1)"; }

# Make sure every pinned commit is present (a clean CI checkout may be shallow).
for rev in $("$PY" -I -c "import json;print(' '.join(sorted({s['rev'] for s in json.load(open('$PINS'))['sources']})))"); do
  git -C "$REPO" cat-file -e "$rev^{commit}" 2>/dev/null || git -C "$REPO" fetch -q origin "$rev" || { log "cannot fetch $rev"; exit 1; }
done

log "S0 pinned sources"
"$PY" -I "$HERE/s0_pins.py" "$REPO" "$PINS"; S0=$?
[ $S0 -eq 1 ] && { log "S0 FAIL"; exit 1; }

log "S0b environment preflight (check_refit_env.py at its pinned commit)"
mkdir -p "$WORK/envcheck"
git -C "$REPO" show 39cd863b9ee158a693e97066ff1a3cc132726471:research/harness-2026-11/s-d1/refit/check_refit_env.py > "$WORK/envcheck/check_refit_env.py"
git -C "$REPO" show 39cd863b9ee158a693e97066ff1a3cc132726471:research/harness-2026-11/s-d1/refit/requirements-refit.txt > "$WORK/envcheck/requirements-refit.txt"
"$PY" -I "$WORK/envcheck/check_refit_env.py" --out "$WORK/envcheck" >/dev/null || { log "S0b FAIL: environment differs from the refit pins"; cat "$WORK/envcheck/REFIT_ENV_CHECK.json"; exit 1; }

log "S1 raw NIROPS -> part-a labels"
POOL_REV=adbfcda581122b52290f95e401bece2590ca7b29
SRC="$WORK/src-pool"
[ -d "$SRC" ] || git -C "$REPO" worktree add -f --detach "$SRC" "$POOL_REV" >/dev/null || exit 1
SHP="$WORK/nirops/NIROPS_2020_2024_R1_R6/NIROPS_2020_2024_R1_R6.shp"
if [ ! -f "$SHP" ]; then
  mkdir -p "$WORK/nirops"
  git -C "$REPO" show 6babc5ec7b8d66f07e6d547ea827453f095e9ad4:research/harness-2026-11/data-fetch/fetch.py > "$WORK/nirops/fetch.py"
  git -C "$REPO" show 6babc5ec7b8d66f07e6d547ea827453f095e9ad4:research/harness-2026-11/data-fetch/resources.json > "$WORK/nirops/resources.json"
  ( cd "$WORK/nirops" && "$PY" -I fetch.py get nirops_2020_2024_perimeters --dest dl ) || { log "S1 FAIL: download"; exit 1; }
  ZIP="$(ls "$WORK"/nirops/dl/*.zip | head -1)"
  [ "$(sha256sum "$ZIP" | cut -c1-64)" = "$(pin "['raw']['nirops_zip_sha256']")" ] || { log "S1 FAIL: zip sha"; exit 1; }
  ( cd "$WORK/nirops" && "$PY" -I -m zipfile -e "$ZIP" . ) || exit 1
  SHP="$(find "$WORK/nirops" -name 'NIROPS_2020_2024_R1_R6.shp' | head -1)"
fi
"$PY" -I "$HERE/s1_labels.py" --repo "$REPO" --src "$SRC" --pool-rev "$POOL_REV" --shp "$SHP" \
  --work "$WORK/s1work" --out "$WORK/S1_LABELS.json" --jobs "${JOBS:-4}" ${LIMIT:+--limit "$LIMIT"} || { log "S1 FAIL (see $WORK/S1_LABELS.json)"; exit 1; }

if [ $S0 -eq 3 ]; then
  log "S2 environment + weather inputs, S3 refit predictions, S4 table: NOT YET RUNNABLE (PINS.json pending)."
  log "Every stage that could run matched. Exit 3."
  exit 3
fi

# S2-S4 are filled in when PINS.json has no pending items: see README.md, "Remaining stages".
log "S2-S4 not implemented for these pins"; exit 1
