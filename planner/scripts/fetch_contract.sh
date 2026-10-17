#!/usr/bin/env bash
# Refresh the planner's copy of the official Route-Check API contract
# (planner/docs/ARCHITECTURE.md §5).
#
#   origin/feat/api:contracts/wfg_api_v1.yaml -> planner/contract/wfg_api_v1.yaml
#                                                (first line: comment naming the source commit)
#   origin/feat/api:contracts/CHANGELOG.md    -> planner/contract/CHANGELOG.md
#   source commit id                          -> planner/contract/SOURCE_COMMIT
#
# Only `git fetch` (remote-tracking ref), `git rev-parse`, `git cat-file`, `git show` and
# `git ls-remote` are used: the working branch, the index and the working tree outside
# planner/contract/ are never touched (no checkout, no stash, no reset).
#
# Usage: planner/scripts/fetch_contract.sh [--check] [--offline] [--branch NAME] [--remote NAME]
#   --check      fetch and print the diff summary, but do not write planner/contract/
#                (exit 0 = copy is current, 4 = the copy differs from the source)
#   --offline    do not run git fetch; use the remote-tracking ref already present
#   --branch     source branch on the remote (default feat/api, or $WFG_CONTRACT_BRANCH)
#   --remote     remote name (default origin)
#
# Exit codes: 0 ok (updated or already current), 1 error, 2 no remote head has the contract,
#             3 the contract exists only on other heads (listed; rerun with --branch),
#             4 --check found a difference.
#
# When CHANGELOG.md gains a version, planner/src/api/ (wire types, client, adapter) and
# planner/mock_api/ must be updated to the new contract — see planner/contract/README.md.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLANNER="$(cd "$HERE/.." && pwd)"
DEST="$PLANNER/contract"
REMOTE="origin"
BRANCH="${WFG_CONTRACT_BRANCH:-feat/api}"
CHECK=0
OFFLINE=0
SRC_PATH="contracts/wfg_api_v1.yaml"
CL_PATH="contracts/CHANGELOG.md"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) CHECK=1 ;;
    --offline) OFFLINE=1 ;;
    --branch) BRANCH="${2:?--branch needs a value}"; shift ;;
    --branch=*) BRANCH="${1#--branch=}" ;;
    --remote) REMOTE="${2:?--remote needs a value}"; shift ;;
    --remote=*) REMOTE="${1#--remote=}" ;;
    -h|--help) sed -n '2,27p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1 (see --help)" >&2; exit 1 ;;
  esac
  shift
done

REPO="$(git -C "$PLANNER" rev-parse --show-toplevel 2>/dev/null)" || {
  echo "ERROR   $PLANNER is not inside a git repository" >&2; exit 1; }
g() { git -C "$REPO" "$@"; }

TRACK="refs/remotes/$REMOTE/$BRANCH"
ONLINE=0          # 1 = the remote answered ls-remote, so its list of heads is authoritative
HEADS=""
BRANCH_GONE=0
if [[ $OFFLINE -eq 0 ]]; then
  if HEADS="$(g ls-remote --heads "$REMOTE" 2>/dev/null)"; then
    ONLINE=1
    if grep -q "[[:space:]]refs/heads/$BRANCH\$" <<< "$HEADS"; then
      echo "fetch   $REMOTE $BRANCH"
      # Updates only the remote-tracking ref; never the checked-out branch.
      g fetch --quiet --no-tags "$REMOTE" "+refs/heads/$BRANCH:$TRACK" || {
        echo "ERROR   git fetch $REMOTE $BRANCH failed" >&2; exit 1; }
    else
      BRANCH_GONE=1   # a stale local remote-tracking ref must not be used
    fi
  else
    echo "WARNING $REMOTE is unreachable; using the local remote-tracking refs (as with --offline)" >&2
  fi
fi

COMMIT=""
if [[ $BRANCH_GONE -eq 0 ]] && g rev-parse --verify --quiet "$TRACK^{commit}" >/dev/null; then
  COMMIT="$(g rev-parse "$TRACK^{commit}")"
fi

if [[ -z "$COMMIT" ]] || ! g cat-file -e "$COMMIT:$SRC_PATH" 2>/dev/null; then
  if [[ -z "$COMMIT" ]]; then
    echo "MISSING $REMOTE/$BRANCH does not exist" >&2
  else
    echo "MISSING $REMOTE/$BRANCH ($COMMIT) has no $SRC_PATH" >&2
  fi
  echo "scan    other heads of $REMOTE for $SRC_PATH" >&2
  FOUND=()
  if [[ $ONLINE -eq 1 ]]; then
    while read -r sha ref; do
      [[ -z "${ref:-}" ]] && continue
      head="${ref#refs/heads/}"
      [[ "$head" == "$BRANCH" ]] && continue
      if ! g cat-file -e "$sha^{commit}" 2>/dev/null; then
        # Fetch the objects only (FETCH_HEAD); no local or remote-tracking ref is created.
        g fetch --quiet --no-tags "$REMOTE" "$ref" 2>/dev/null || { echo "        $head: fetch failed" >&2; continue; }
      fi
      if g cat-file -e "$sha:$SRC_PATH" 2>/dev/null; then
        FOUND+=("$head $sha")
        echo "found   $head ($sha) has $SRC_PATH" >&2
      fi
    done <<< "$HEADS"
  else
    while read -r ref; do
      head="${ref#refs/remotes/$REMOTE/}"
      [[ "$head" == "$BRANCH" || "$head" == "HEAD" ]] && continue
      if g cat-file -e "$ref:$SRC_PATH" 2>/dev/null; then
        FOUND+=("$head $(g rev-parse "$ref")")
        echo "found   $head has $SRC_PATH (local remote-tracking ref)" >&2
      fi
    done < <(g for-each-ref --format='%(refname)' "refs/remotes/$REMOTE/")
  fi
  if [[ ${#FOUND[@]} -eq 0 ]]; then
    echo "ERROR   no head of $REMOTE contains $SRC_PATH; planner/contract/ left unchanged" >&2
    exit 2
  fi
  echo "ERROR   the contract is not on $REMOTE/$BRANCH but exists on the head(s) above." >&2
  echo "        planner/contract/ left unchanged. If one of them is the API session's branch, rerun:" >&2
  echo "          planner/scripts/fetch_contract.sh --branch <head>" >&2
  exit 3
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

{
  echo "# Fetched from $REMOTE/$BRANCH commit $COMMIT ($SRC_PATH). Do not edit; re-run planner/scripts/fetch_contract.sh."
  g show "$COMMIT:$SRC_PATH"
} > "$TMP/wfg_api_v1.yaml"
HAVE_CL=0
if g cat-file -e "$COMMIT:$CL_PATH" 2>/dev/null; then
  g show "$COMMIT:$CL_PATH" > "$TMP/CHANGELOG.md"
  HAVE_CL=1
else
  echo "WARNING $REMOTE/$BRANCH has no $CL_PATH" >&2
fi
echo "$COMMIT" > "$TMP/SOURCE_COMMIT"

# Sanity: the fetched file must parse as YAML/OpenAPI 3.1 (when PyYAML is available).
PY="${PYTHON:-python3}"
if command -v "$PY" >/dev/null 2>&1 && "$PY" -c 'import yaml' 2>/dev/null; then
  "$PY" - "$TMP/wfg_api_v1.yaml" <<'PYEOF' || { echo "ERROR   fetched contract does not parse as an OpenAPI 3.1 document" >&2; exit 1; }
import sys, yaml
d = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
assert isinstance(d, dict) and str(d.get("openapi", "")).startswith("3.1"), "not OpenAPI 3.1"
assert d.get("paths") and d.get("components", {}).get("schemas"), "no paths/schemas"
PYEOF
fi

OLD_COMMIT="(none)"
[[ -f "$DEST/SOURCE_COMMIT" ]] && OLD_COMMIT="$(tr -d '[:space:]' < "$DEST/SOURCE_COMMIT")"
echo "source  $REMOTE/$BRANCH $COMMIT (previous copy: $OLD_COMMIT)"

# Diff summary vs the previous copy (the first, comment-only line is ignored).
CHANGED=0
if [[ -f "$DEST/wfg_api_v1.yaml" ]]; then
  if diff -q <(tail -n +2 "$DEST/wfg_api_v1.yaml") <(tail -n +2 "$TMP/wfg_api_v1.yaml") >/dev/null; then
    echo "same    wfg_api_v1.yaml content unchanged"
  else
    CHANGED=1
    STAT="$(diff <(tail -n +2 "$DEST/wfg_api_v1.yaml") <(tail -n +2 "$TMP/wfg_api_v1.yaml") | grep -c '^[<>]' || true)"
    ADDS="$(diff <(tail -n +2 "$DEST/wfg_api_v1.yaml") <(tail -n +2 "$TMP/wfg_api_v1.yaml") | grep -c '^>' || true)"
    DELS="$(diff <(tail -n +2 "$DEST/wfg_api_v1.yaml") <(tail -n +2 "$TMP/wfg_api_v1.yaml") | grep -c '^<' || true)"
    echo "CHANGED wfg_api_v1.yaml: +$ADDS / -$DELS lines ($STAT changed lines)"
    if command -v "$PY" >/dev/null 2>&1 && "$PY" -c 'import yaml' 2>/dev/null; then
      "$PY" - "$DEST/wfg_api_v1.yaml" "$TMP/wfg_api_v1.yaml" <<'PYEOF' || true
import json, sys, yaml
old = yaml.safe_load(open(sys.argv[1], encoding="utf-8")) or {}
new = yaml.safe_load(open(sys.argv[2], encoding="utf-8")) or {}
ov, nv = old.get("info", {}).get("version"), new.get("info", {}).get("version")
print(f"        info.version: {ov} -> {nv}" if ov != nv else f"        info.version: {nv} (unchanged)")
def ops(d):
    return {f"{m.upper()} {p}": v for p, item in (d.get("paths") or {}).items()
            for m, v in (item or {}).items() if m in ("get", "post", "put", "patch", "delete")}
oo, no = ops(old), ops(new)
for k in sorted(no.keys() - oo.keys()): print(f"        + endpoint {k}")
for k in sorted(oo.keys() - no.keys()): print(f"        - endpoint {k}")
for k in sorted(no.keys() & oo.keys()):
    if json.dumps(no[k], sort_keys=True, default=str) != json.dumps(oo[k], sort_keys=True, default=str):
        print(f"        ~ endpoint {k}")
os_ = (old.get("components") or {}).get("schemas") or {}
ns = (new.get("components") or {}).get("schemas") or {}
for k in sorted(ns.keys() - os_.keys()): print(f"        + schema {k}")
for k in sorted(os_.keys() - ns.keys()): print(f"        - schema {k}")
for k in sorted(ns.keys() & os_.keys()):
    if json.dumps(ns[k], sort_keys=True, default=str) != json.dumps(os_[k], sort_keys=True, default=str):
        print(f"        ~ schema {k}")
PYEOF
    fi
    echo "        --- unified diff (first 120 lines) ---"
    diff -u --label "previous copy" --label "$COMMIT" <(tail -n +2 "$DEST/wfg_api_v1.yaml") <(tail -n +2 "$TMP/wfg_api_v1.yaml") | head -n 120 || true
  fi
else
  CHANGED=1
  echo "new     no previous planner/contract/wfg_api_v1.yaml"
fi

if [[ $HAVE_CL -eq 1 ]]; then
  if [[ -f "$DEST/CHANGELOG.md" ]] && diff -q "$DEST/CHANGELOG.md" "$TMP/CHANGELOG.md" >/dev/null; then
    echo "same    CHANGELOG.md unchanged"
  else
    CHANGED=1
    echo "CHANGED CHANGELOG.md — new or edited lines:"
    if [[ -f "$DEST/CHANGELOG.md" ]]; then
      diff "$DEST/CHANGELOG.md" "$TMP/CHANGELOG.md" | sed -n 's/^> /        + /p' | head -n 60 || true
    else
      sed 's/^/        + /' "$TMP/CHANGELOG.md" | head -n 60
    fi
    OLDV="$(grep -cE '^## ' "$DEST/CHANGELOG.md" 2>/dev/null || echo 0)"
    NEWV="$(grep -cE '^## ' "$TMP/CHANGELOG.md" || echo 0)"
    if [[ "$NEWV" -gt "$OLDV" ]]; then
      echo "ACTION  CHANGELOG.md gained a version: update planner/src/api/ and planner/mock_api/ to the new contract"
    fi
  fi
fi
[[ "$OLD_COMMIT" != "$COMMIT" ]] && CHANGED=1

if [[ $CHECK -eq 1 ]]; then
  if [[ $CHANGED -eq 1 ]]; then
    echo "check   planner/contract/ differs from $REMOTE/$BRANCH $COMMIT (not written: --check)"
    exit 4
  fi
  echo "check   planner/contract/ is current"
  exit 0
fi

mkdir -p "$DEST"
cp "$TMP/wfg_api_v1.yaml" "$DEST/wfg_api_v1.yaml.tmp" && mv "$DEST/wfg_api_v1.yaml.tmp" "$DEST/wfg_api_v1.yaml"
if [[ $HAVE_CL -eq 1 ]]; then
  cp "$TMP/CHANGELOG.md" "$DEST/CHANGELOG.md.tmp" && mv "$DEST/CHANGELOG.md.tmp" "$DEST/CHANGELOG.md"
fi
cp "$TMP/SOURCE_COMMIT" "$DEST/SOURCE_COMMIT.tmp" && mv "$DEST/SOURCE_COMMIT.tmp" "$DEST/SOURCE_COMMIT"
if [[ $CHANGED -eq 1 ]]; then
  echo "wrote   planner/contract/{wfg_api_v1.yaml,CHANGELOG.md,SOURCE_COMMIT} from $COMMIT"
  echo "NEXT    review the diff above; if the contract changed, update planner/src/api/ and planner/mock_api/,"
  echo "        then run: python3 -m pytest tests/planner/test_mock_api.py -q"
else
  echo "ok      planner/contract/ is current ($COMMIT)"
fi
