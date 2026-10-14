#!/usr/bin/env bash
# Tag the current commit as a demo-ready build, if and only if it passes the demo gate.
#
#   bash wfglink/scripts/tag_demo.sh [gate_seconds]
#
# The gate runs the booth UI headless for gate_seconds (default 60) on the synthetic source
# and on an approved clip. It runs on an export of the committed HEAD (git archive into a
# temporary folder), so uncommitted or untracked work in the checkout cannot affect it and
# the tag points at exactly what was tested. On success HEAD is tagged
# wfglink-demo-YYYYMMDD (Asia/Shanghai date; -2, -3 if that day already has one) and only
# that tag is pushed. Tags are never moved or force-pushed. The caller records the tag in
# LOG.md.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(git -C "$ROOT" rev-parse --show-toplevel)"
GATE_SECONDS="${1:-60}"
CLIP="${DEMO_CLIP:-$ROOT/data/raw/C5_nist_emberometer.mp4}"
COMMIT="$(git -C "$REPO" rev-parse HEAD)"
DAY="$(TZ=Asia/Shanghai date +%Y%m%d)"
EXPORT="$(mktemp -d)"
trap 'rm -rf "$EXPORT"' EXIT
git -C "$REPO" archive "$COMMIT" wfglink | tar -x -C "$EXPORT"
OUT="$ROOT/results/runs/demo_gate_$DAY"
# PYTHONPATH puts the exported package ahead of the checkout's editable install.
PYTHONPATH="$EXPORT/wfglink/src" QT_QPA_PLATFORM=offscreen "$ROOT/.venv/bin/python" -m wfglink demo-gate \
  --seconds "$GATE_SECONDS" --clip "$CLIP" --out "$OUT"
"$ROOT/.venv/bin/python" - "$OUT/report.json" "$COMMIT" <<'EOF'
import json, sys
p = sys.argv[1]
r = json.load(open(p))
r["tested_commit"] = sys.argv[2]
json.dump(r, open(p, "w"), indent=2)
EOF
TAG="wfglink-demo-$DAY"
n=2
while git -C "$REPO" rev-parse -q --verify "refs/tags/$TAG" >/dev/null; do TAG="wfglink-demo-$DAY-$n"; n=$((n + 1)); done
git -C "$REPO" tag -a "$TAG" -m "[wfglink] demo build: demo gate passed (${GATE_SECONDS} s synthetic and ${CLIP##*/})" "$COMMIT"
for i in 1 2 3 4; do
  if git -C "$REPO" push origin "refs/tags/$TAG"; then break; fi
  sleep $((2 ** i))
done
echo "TAGGED $TAG ${COMMIT:0:7}"
