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
# that tag is pushed when the remote allows it. Every passing build is also appended to
# DEMO_BUILDS.md, which the caller commits with a LOG.md entry. Tags are never moved or
# force-pushed.
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
pushed=no
for i in 1 2 3; do
  if git -C "$REPO" push origin "refs/tags/$TAG" 2>&1 | tee /dev/stderr | grep -q "\[new tag\]"; then pushed=yes; break; fi
  sleep $((2 ** i))
done
# The session's git proxy may refuse tag pushes; the branch always carries the record.
SUMMARY=$("$ROOT/.venv/bin/python" - "$OUT/report.json" <<'EOF2'
import json, sys
r = json.load(open(sys.argv[1]))
print("; ".join(f"{k} {v['frames']} frames, {v['paints']} paints, {len(v['errors'])} errors" for k, v in r["runs"].items()))
EOF2
)
BUILDS="$ROOT/DEMO_BUILDS.md"
if [[ ! -f "$BUILDS" ]]; then
  cat >"$BUILDS" <<'EOF2'
# Demo builds

Each row is a commit that passed the demo gate (`scripts/tag_demo.sh`: the booth UI runs headless on the synthetic source and on an approved clip with no errors). Any of them is a working demo even if later work breaks something.

To run one: `git fetch origin && git worktree add ~/wfglink-demo <commit>`, then `bash ~/wfglink-demo/wfglink/booth/booth.sh` (after `scripts/sitting1.sh` has installed the environment there).

To make a real tag (this project's cloud session cannot push tags): `git tag <tag> <commit> && git push origin <tag>`.

| Date (Asia/Shanghai) | Tag | Commit | Gate | Tag pushed |
|---|---|---|---|---|
EOF2
fi
echo "| $DAY | $TAG | ${COMMIT:0:12} | ${GATE_SECONDS} s each: $SUMMARY | $pushed |" >>"$BUILDS"
echo "TAGGED $TAG ${COMMIT:0:7} (pushed: $pushed; recorded in DEMO_BUILDS.md)"
