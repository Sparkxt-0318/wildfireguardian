#!/usr/bin/env bash
# Fetch, verify and safely extract the public GitHub Release assets the village
# evacuation planner's data tools read (planner/docs/ARCHITECTURE.md §3).
#
#   planner/.assets/release/<asset>.zip            downloaded once, SHA-256 verified (fail closed)
#   planner/.assets/extracted/<asset stem>/...     safe extraction (no absolute paths, no '..',
#                                                   no symlinks, no duplicate members)
#
# Idempotent: an asset already present with the pinned SHA-256 is not downloaded again, and an
# extraction whose .extracted.sha256 stamp matches the pinned digest is not repeated. A present
# file with a wrong digest is never used: the script stops (delete the file to re-download).
#
# Usage: planner/scripts/fetch_planner_assets.sh            (from anywhere)
#        WFG_ASSETS_DIR=/some/dir planner/scripts/fetch_planner_assets.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLANNER="$(cd "$HERE/.." && pwd)"
ASSETS="${WFG_ASSETS_DIR:-$PLANNER/.assets}"
RELEASE_DIR="$ASSETS/release"
EXTRACT_DIR="$ASSETS/extracted"
REPO_URL="https://github.com/Sparkxt-0318/wildfireguardian/releases/download"
PY="${PYTHON:-python3}"

mkdir -p "$RELEASE_DIR" "$EXTRACT_DIR"

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'
  else shasum -a 256 "$1" | awk '{print $1}'; fi
}

# download_verified <tag> <asset> <sha256>
download_verified() {
  local tag="$1" asset="$2" want="$3" dest="$RELEASE_DIR/$2"
  if [[ -f "$dest" ]]; then
    local have; have="$(sha256_of "$dest")"
    if [[ "$have" == "$want" ]]; then
      echo "ok      $asset (present, SHA-256 verified)"
      return 0
    fi
    echo "ERROR   $asset is present but its SHA-256 is $have, expected $want." >&2
    echo "        Refusing to use or overwrite it. Delete the file to re-download." >&2
    exit 1
  fi
  local tmp="$dest.part.$$"
  echo "fetch   $REPO_URL/$tag/$asset"
  if ! curl -fsSL --retry 5 --retry-delay 3 --connect-timeout 30 -o "$tmp" "$REPO_URL/$tag/$asset"; then
    rm -f "$tmp"; echo "ERROR   download failed: $asset" >&2; exit 1
  fi
  local got; got="$(sha256_of "$tmp")"
  if [[ "$got" != "$want" ]]; then
    rm -f "$tmp"
    echo "ERROR   $asset SHA-256 mismatch after download: got $got, expected $want. Nothing kept." >&2
    exit 1
  fi
  mv "$tmp" "$dest"
  echo "ok      $asset (downloaded, SHA-256 verified)"
}

# extract_safe <asset> <sha256>  -> $EXTRACT_DIR/<asset stem>/
extract_safe() {
  local asset="$1" want="$2" stem="${1%.zip}"
  local out="$EXTRACT_DIR/$stem" stamp="$EXTRACT_DIR/$stem/.extracted.sha256"
  if [[ -f "$stamp" && "$(cat "$stamp")" == "$want" ]]; then
    echo "ok      extracted/$stem (stamp matches)"
    return 0
  fi
  # Re-verify the archive right before extraction (fail closed).
  local have; have="$(sha256_of "$RELEASE_DIR/$asset")"
  if [[ "$have" != "$want" ]]; then
    echo "ERROR   $asset SHA-256 changed before extraction ($have)." >&2; exit 1
  fi
  local staging="$EXTRACT_DIR/.staging.$stem.$$"
  rm -rf "$staging"; mkdir -p "$staging"
  # Isolated interpreter (-I): never imports code from the archive or the current directory.
  if ! "$PY" -I - "$RELEASE_DIR/$asset" "$staging" <<'PYEOF'
import os, stat, sys, zipfile
from pathlib import PurePosixPath
archive, dest = sys.argv[1], os.path.realpath(sys.argv[2])
with zipfile.ZipFile(archive) as z:
    infos = z.infolist()
    names = [i.filename for i in infos]
    if len(names) != len(set(names)):
        sys.exit("unsafe archive: duplicate member names")
    for info in infos:
        name = info.filename
        p = PurePosixPath(name)
        if not name or name.startswith(("/", "\\")) or "\\" in name or p.is_absolute() \
                or ".." in p.parts or (len(name) > 1 and name[1] == ":"):
            sys.exit("unsafe archive member path: %r" % name)
        mode = (info.external_attr >> 16) & 0o170000
        if mode and mode not in (stat.S_IFREG, stat.S_IFDIR):
            sys.exit("unsafe archive member type (symlink/special): %r" % name)
        target = os.path.realpath(os.path.join(dest, name))
        if target != dest and not target.startswith(dest + os.sep):
            sys.exit("archive member escapes destination: %r" % name)
    bad = z.testzip()
    if bad is not None:
        sys.exit("corrupt archive member: %r" % bad)
    for info in infos:
        target = os.path.join(dest, info.filename)
        if info.is_dir():
            os.makedirs(target, exist_ok=True)
            continue
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with z.open(info) as src, open(target, "wb") as dst:
            while True:
                b = src.read(1 << 20)
                if not b:
                    break
                dst.write(b)
        os.chmod(target, 0o644)
print("extracted %d members" % len(infos))
PYEOF
  then
    rm -rf "$staging"; echo "ERROR   extraction refused for $asset" >&2; exit 1
  fi
  rm -rf "$out"
  mv "$staging" "$out"
  printf '%s' "$want" > "$stamp"
  echo "ok      extracted/$stem"
}

# --- Research release assets (ARCHITECTURE.md §3) ---------------------------------------------
#        tag                                       asset                                                      sha256
ASSETS_TABLE=(
  "research-final-20261015|WFG-evaluated-routing-inputs-20261015.zip|d7e0a5fcdd8b968b2542d221b1c4fe6cb6a958681ea69546cd0b92f950882202"
  "research-final-20261015|WildfireGuardian_Latest_Independent_Final_20261015.zip|a3cd27b88d065883ce3d0534592d1406e3f9798c1abd98256c730f0cf3d60d3f"
  "routing-ablation-final-inputs-20261016|WFG-final-input-routing-ablation-20261016-v1.zip|661090bd059a862a9874c4e19977c105d1978bf32ee6d6d3cd7f6d40d244c006"
)

# --- FUTURE planner-specific release assets (cache / basemap) --------------------------------
# Not published yet. When a planner release exists, add rows here with the SAME pattern
# (pinned tag, asset name and SHA-256; download_verified then extract_safe). Never add a row
# without a pinned digest, and never point at a mutable "latest" URL.
#
# ASSETS_TABLE+=(
#   "planner-cache-YYYYMMDD|WFG-planner-cache-YYYYMMDD.zip|<sha256 of the published zip>"
#   "planner-basemap-YYYYMMDD|WFG-planner-basemap-YYYYMMDD.zip|<sha256 of the published zip>"
# )
# ----------------------------------------------------------------------------------------------

for row in "${ASSETS_TABLE[@]}"; do
  IFS='|' read -r tag asset sha <<<"$row"
  download_verified "$tag" "$asset" "$sha"
done
for row in "${ASSETS_TABLE[@]}"; do
  IFS='|' read -r tag asset sha <<<"$row"
  extract_safe "$asset" "$sha"
done
echo "done    assets in $ASSETS"
