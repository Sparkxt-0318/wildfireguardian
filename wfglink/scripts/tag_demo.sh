#!/usr/bin/env bash
# Tag the current commit as a demo-ready build, if and only if it passes the demo gate.
#
#   bash wfglink/scripts/tag_demo.sh [gate_seconds]
#
# The gate runs the booth UI headless for gate_seconds (default 60) on the synthetic source
# and on an approved clip. On success HEAD is tagged wfglink-demo-YYYYMMDD (Asia/Shanghai
# date; -2, -3 if that day already has one) and only that tag is pushed. Tags are never
# moved or force-pushed. The caller records the tag in LOG.md.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -n "$(git status --porcelain --untracked-files=all -- src configs scripts pyproject.toml requirements.txt)" ]]; then
  echo "tag_demo: wfglink sources have uncommitted or untracked changes; commit first so the gate tests what the tag points at" >&2
  git status --short -- src configs scripts pyproject.toml requirements.txt >&2
  exit 1
fi
GATE_SECONDS="${1:-60}"
CLIP="${DEMO_CLIP:-data/raw/C5_nist_emberometer.mp4}"
QT_QPA_PLATFORM=offscreen .venv/bin/python -m wfglink demo-gate --seconds "$GATE_SECONDS" --clip "$CLIP"
DAY="$(TZ=Asia/Shanghai date +%Y%m%d)"
TAG="wfglink-demo-$DAY"
n=2
while git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; do TAG="wfglink-demo-$DAY-$n"; n=$((n + 1)); done
COMMIT="$(git rev-parse --short HEAD)"
git tag -a "$TAG" -m "[wfglink] demo build: demo gate passed (${GATE_SECONDS} s synthetic and ${CLIP##*/})" HEAD
for i in 1 2 3 4; do
  if git push origin "refs/tags/$TAG"; then break; fi
  sleep $((2 ** i))
done
echo "TAGGED $TAG $COMMIT"
