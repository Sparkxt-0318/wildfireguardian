"""Vendor MapLibre GL JS into the KCF scene: planner/public/kcf-scene/vendor/.

Copies, byte for byte, from the planner's installed package (planner/node_modules/maplibre-gl, pinned by
planner/package-lock.json):
  dist/maplibre-gl.js   -> vendor/maplibre-gl.js            (minified UMD build; not the -csp or -dev builds)
  dist/maplibre-gl.css  -> vendor/maplibre-gl.css
  LICENSE.txt           -> vendor/LICENSE-maplibre-gl.txt
and checks the copies against the npm tarball named in the lockfile (sha512 = lockfile integrity), downloaded once to
research/kcf-replay/scene/.cache/npm/ (git-ignored). With --offline and no cached tarball the tarball check is skipped
and says so. The version is read from the package's package.json and must equal the lockfile's.
build_sources.py records the copies, the version and the tarball check in research/kcf-replay/scene/SOURCES.json.

Usage: python3 research/kcf-replay/scene/build_vendor.py [--offline]
"""
from __future__ import annotations

import argparse, base64, hashlib, json, shutil, tarfile, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PKG = "planner/node_modules/maplibre-gl"
LOCK = "planner/package-lock.json"
VENDOR = "planner/public/kcf-scene/vendor"
COPIES = [("dist/maplibre-gl.js", "maplibre-gl.js"), ("dist/maplibre-gl.css", "maplibre-gl.css"),
          ("LICENSE.txt", "LICENSE-maplibre-gl.txt")]
CACHE = HERE / ".cache/npm"


def sha(b):
    return hashlib.sha256(b).hexdigest()


def tarball_check(entry, offline):
    url, integrity = entry["resolved"], entry["integrity"]
    algo, want = integrity.split("-", 1)
    CACHE.mkdir(parents=True, exist_ok=True)
    gi = HERE / ".cache/.gitignore"
    if not gi.exists():
        gi.write_text("# raw downloads of the scene builders; never committed\n*\n")
    tgz = CACHE / url.rsplit("/", 1)[-1]
    if not tgz.exists():
        if offline:
            return {"checked": False, "reason": "--offline and no cached tarball"}
        with urllib.request.urlopen(url, timeout=120) as r:
            tgz.write_bytes(r.read())
    b = tgz.read_bytes()
    got = base64.b64encode(hashlib.new(algo, b).digest()).decode()
    if got != want:
        raise SystemExit(f"tarball {tgz.name} does not match the lockfile integrity")
    files = {}
    with tarfile.open(tgz) as t:
        for src, _ in COPIES:
            files[src] = sha(t.extractfile(f"package/{src}").read())
    return {"checked": True, "url": url, "integrity": integrity, "sha256": files}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()
    pj = json.loads((ROOT / PKG / "package.json").read_text())
    lock = json.loads((ROOT / LOCK).read_text())["packages"]["node_modules/maplibre-gl"]
    if pj["version"] != lock["version"]:
        raise SystemExit(f"installed maplibre-gl {pj['version']} != lockfile {lock['version']}")
    tb = tarball_check(lock, a.offline)
    out = ROOT / VENDOR
    out.mkdir(parents=True, exist_ok=True)
    for src, dst in COPIES:
        b = (ROOT / PKG / src).read_bytes()
        if tb["checked"] and tb["sha256"][src] != sha(b):
            raise SystemExit(f"{PKG}/{src} differs from the npm tarball")
        shutil.copyfile(ROOT / PKG / src, out / dst)
        if sha((out / dst).read_bytes()) != sha(b):
            raise SystemExit(f"copy of {src} differs")
        print(f"  {PKG}/{src} -> {VENDOR}/{dst}: {len(b)} B sha256 {sha(b)[:16]}")
    print(f"maplibre-gl {pj['version']} ({pj.get('license')}); npm tarball check: "
          f"{'PASS (sha512 = lockfile integrity, 3/3 files identical)' if tb['checked'] else tb['reason']}")


if __name__ == "__main__":
    main()
