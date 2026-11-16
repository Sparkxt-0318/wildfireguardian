#!/usr/bin/env bash
# Look for Chat 1's local ready tag and, if present, list the JSON files in the tagged commit
# so the documented sample can be passed to integrate.js as git:TAG:path. Read-only:
# no checkout, no worktree change, no fetch.
#
#   tools/check_planner_tag.sh [TAG]          (default TAG=kcf/planner-delay-v1-ready)
# Exit 0 = tag found, 3 = tag absent.
set -euo pipefail
TAG="${1:-kcf/planner-delay-v1-ready}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
PINNED=4169cccc427e9e19be3851326a1225df89fe96f2   # commit Chat 1 tagged; published as branch claude/stoic-davinci-eha5j9
if ! git -C "$HERE" rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
  echo "TAG_ABSENT $TAG (Chat 1's git proxy refused the tag push; the tagged commit was published as a branch instead)."
  if git -C "$HERE" cat-file -e "$PINNED^{commit}" 2>/dev/null; then
    echo "PINNED_COMMIT_PRESENT $PINNED — read inputs as git:$PINNED:<path>; recorded run in qa/planner-4169ccc/"
  else
    echo "PINNED_COMMIT_ABSENT — fetch it read-only: git fetch origin claude/stoic-davinci-eha5j9"
  fi
  exit 3
fi
COMMIT="$(git -C "$HERE" rev-list -n 1 "$TAG")"
echo "TAG_FOUND $TAG -> $COMMIT"
echo "JSON files in tagged commit (read with git show; nothing checked out):"
git -C "$HERE" ls-tree -r --name-only "$TAG" | grep -E '\.json$' | grep -Ei 'planner|kcf|sample|delay' || true
echo "Docs mentioning a sample:"
git -C "$HERE" ls-tree -r --name-only "$TAG" | grep -Ei '(readme|sample).*\.md$' | grep -Ei 'planner|kcf' || true
echo
echo "Then run, e.g.:"
echo "  node tools/integrate.js --baseline git:$TAG:<baseline.json> --revised git:$TAG:<revised.json> [--meta <meta.json>]"
