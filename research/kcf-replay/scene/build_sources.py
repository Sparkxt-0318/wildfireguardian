"""Provenance of the KCF scene's shipped static assets: research/kcf-replay/scene/SOURCES.json.

One entry per file under planner/public/kcf-scene/vendor/ and for data/terrain.js, data/basemap.js, data/fonts.js:
{path, bytes, sha256, built_by, inputs, license, attribution}. Data-file inputs are read from each file's own
`built.inputs` (terrain: summarised, the 171 tile URLs are listed in terrain.js itself). Vendor inputs are the
planner's installed npm packages, pinned by planner/package-lock.json; the maplibre-gl copies are also checked
against the npm tarball cached by build_vendor.py (skipped, and said so, when the tarball is not cached).
Run after build_vendor.py, build_terrain.py, build_basemap.py and build_fonts.py (re-run whenever one of them is).

Usage: python3 research/kcf-replay/scene/build_sources.py
"""
from __future__ import annotations

import hashlib, json, sys
from pathlib import Path

sys.dont_write_bytecode = True  # importing the sibling builder must not leave __pycache__ in the repository
import build_vendor  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SCENE = "planner/public/kcf-scene"
OUT = HERE / "SOURCES.json"
LOCK = "planner/package-lock.json"
DATA = ["terrain", "basemap", "fonts"]
S = "research/kcf-replay/scene/"


def sha(b):
    return hashlib.sha256(b).hexdigest()


def file_rec(rel):
    b = (ROOT / rel).read_bytes()
    return {"path": rel, "bytes": len(b), "sha256": sha(b)}


def read_data(name):
    rel = f"{SCENE}/data/{name}.js"
    lines = (ROOT / rel).read_text(encoding="utf-8").split("\n")
    pre = f"(window.KCF=window.KCF||{{}}).{name}="
    if len(lines) != 3 or not lines[0].startswith("// ") or not lines[1].startswith(pre) or not lines[1].endswith(";") \
            or lines[2] != "":
        raise SystemExit(f"{rel}: not a one-line-header data file")
    return json.loads(lines[1][len(pre):-1])


def lock_entry(lock, pkg):
    e = lock["packages"][f"node_modules/{pkg}"]
    return {"package": pkg, "version": e["version"], "resolved": e["resolved"], "integrity": e["integrity"],
            "license": e.get("license"), "lockfile": LOCK}


def main():
    lockb = (ROOT / LOCK).read_bytes()
    lock = json.loads(lockb)
    lock_rec = {"path": LOCK, "bytes": len(lockb), "sha256": sha(lockb)}
    ml = lock_entry(lock, "maplibre-gl")
    pr = lock_entry(lock, "pretendard")
    tb = build_vendor.tarball_check(lock["packages"]["node_modules/maplibre-gl"], offline=True)
    ml_check = ({"npm_tarball": tb["url"], "sha512_equals_lockfile_integrity": True,
                 "files_identical_to_tarball": True} if tb["checked"] else {"npm_tarball": "not checked: " + tb["reason"]})
    ml_lic = f"BSD-3-Clause ({SCENE}/vendor/LICENSE-maplibre-gl.txt)"
    ml_attr = f"MapLibre GL JS {ml['version']}, Copyright (c) 2023, MapLibre contributors"
    pr_attr = "Pretendard, Copyright (c) 2021, Kil Hyung-jin (https://github.com/orioncactus/pretendard)"

    entries = []
    vend = sorted(p.name for p in (ROOT / SCENE / "vendor").iterdir() if p.is_file())
    known = {dst: src for src, dst in build_vendor.COPIES}
    for name in vend:
        rel = f"{SCENE}/vendor/{name}"
        e = file_rec(rel)
        if name in known:
            src = f"{build_vendor.PKG}/{known[name]}"
            inp = {"path": src, "note": "planner/node_modules is not committed; pinned by the lockfile", "npm": ml,
                   "check": ml_check}
            if (ROOT / src).exists():
                s = file_rec(src)
                if s["sha256"] != e["sha256"]:
                    raise SystemExit(f"{rel} differs from {src}: re-run build_vendor.py")
                inp.update(bytes=s["bytes"], sha256=s["sha256"])
            if tb["checked"] and tb["sha256"][known[name]] != e["sha256"]:
                raise SystemExit(f"{rel} differs from the npm tarball")
            e.update(built_by=S + "build_vendor.py (verbatim copy)", inputs=[inp, lock_rec], license=ml_lic,
                     attribution=ml_attr)
        elif name == "LICENSE-pretendard.txt":
            src = "planner/node_modules/pretendard/dist/LICENSE.txt"
            inp = {"path": src, "note": "planner/node_modules is not committed; pinned by the lockfile", "npm": pr}
            if (ROOT / src).exists():
                s = file_rec(src)
                if s["sha256"] != e["sha256"]:
                    raise SystemExit(f"{rel} differs from {src}: re-run build_fonts.py")
                inp.update(bytes=s["bytes"], sha256=s["sha256"])
            e.update(built_by=S + "build_fonts.py (verbatim copy)", inputs=[inp, lock_rec],
                     license="SIL Open Font License 1.1 (this file)", attribution=pr_attr)
        else:
            raise SystemExit(f"unknown vendor file {rel}: add it to build_sources.py")
        entries.append(e)

    for name in DATA:
        rel = f"{SCENE}/data/{name}.js"
        e = file_rec(rel)
        d = read_data(name)
        b = d["built"]
        e.update(built_by=b["script"], built_commit=b["commit"])
        if name == "terrain":
            ins = b["inputs"]
            agg = sha("".join(f"{i['url']} {i['sha256']} {i['bytes']}\n" for i in ins).encode())
            srcs = sorted({s.strip().split("/")[0] for i in ins for s in i["imagery_sources"].split(",") if s.strip()})
            e.update(inputs={"count": len(ins), "url_template": d["source"]["url_template"],
                             "bytes": sum(i["bytes"] for i in ins), "fetched_utc": d["source"]["fetched_utc"],
                             "listed_in": f"{rel} built.inputs (url, bytes, sha256, etag, imagery_sources)",
                             "aggregate_sha256": agg,
                             "aggregate_sha256_definition": "sha256 over lines '<url> <sha256> <bytes>\\n' in built.inputs order",
                             "imagery_sources": srcs},
                     license=("AWS Open Data Terrain Tiles; the sources in these tiles (x-amz-meta-x-imagery-sources) are "
                              + ", ".join(srcs) + " only, US Government (NASA / USGS / NOAA) datasets; terms: "
                              "https://github.com/tilezen/joerd/blob/master/docs/attribution.md"),
                     attribution=d["attribution"])
        elif name == "basemap":
            e.update(inputs=b["inputs"], license="ODbL 1.0 (OpenStreetMap data)", attribution=d["attribution"])
        else:
            e.update(inputs=b["inputs"],
                     license=("glyphs: Noto Sans, SIL OFL 1.1 (no Noto license text in the repository; provenance in "
                              "planner/public/basemap/ATTRIBUTION.md and SOURCES.json); ui face: SIL OFL 1.1, "
                              f"{SCENE}/vendor/LICENSE-pretendard.txt"),
                     attribution=("Noto Sans glyph PBFs (protomaps/basemaps-assets); " + pr_attr +
                                  f", subset renamed '{d['ui']['family']}' (Reserved Font Name not used)"))
        entries.append(e)

    obj = {"schema": "kcf-scene-sources/1", "generated_by": S + "build_sources.py",
           "rule": "every shipped static asset: repository path, byte size, SHA-256, the script that made it, its inputs",
           "entries": sorted(entries, key=lambda x: x["path"])}
    OUT.write_text(json.dumps(obj, sort_keys=True, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(entries)} entries")
    for e in obj["entries"]:
        print(f"  {e['path']}: {e['bytes']} B {e['sha256'][:16]}")


if __name__ == "__main__":
    main()
