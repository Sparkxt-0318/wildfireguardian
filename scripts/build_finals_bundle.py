#!/usr/bin/env python3
"""Assemble ``release/kcf-finals-2026/`` — the folder that goes on the USB stick.

WFG-036 v1, KCF_READINESS R9. The bundle is what the student carries to the booth:
the four offline screens, the fonts and poster they need, the licence, the citation
file, and a ten-line Korean run recipe. Nothing in it is computed here — every
payload file is copied byte for byte from the repository, so the bundle can never
disagree with the tree it came from.

**Why the payload is not committed.** A second copy of ``web/finals.html`` (2.1 MB,
rebuilt whenever the screen changes) would be a second place for the same bytes to
go stale, which is what CHARTER §3.2 exists to prevent, and it would put a duplicate
of every retired figure into the forbidden-string scan's prose scope. So the payload
is generated and git-ignored, and what the repository commits is the part a clean
clone cannot regenerate: the recipe (``README_KO.md``) and ``MANIFEST.json``, the
SHA-256 of every file the bundle should contain.

That manifest is the byte-identical check R9 asks for, and it does a second job the
booth needs: a USB stick can corrupt a file silently, and re-running this script on
the laptop says so instead of finding out in front of a judge.

Default run assembles the bundle and compares it against the committed manifest,
exiting non-zero on any difference. ``--update`` rewrites the manifest, and is what
a lap runs after deliberately changing a payload file.

No network, no clock, no randomness: two runs on the same tree produce the same
bytes, which is the whole claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BUNDLE = REPO / "release" / "kcf-finals-2026"
MANIFEST = BUNDLE / "MANIFEST.json"

#: (repository path, path inside the bundle). A directory copies its whole subtree.
#: Every entry is a tracked file; the builder refuses if one is missing rather than
#: shipping a bundle with a hole in it.
PAYLOAD: tuple[tuple[str, str], ...] = (
    ("web/finals.html", "web/finals.html"),
    ("web/console.html", "web/console.html"),
    ("web/field_view.html", "web/field_view.html"),
    ("web/refuge_placement.html", "web/refuge_placement.html"),
    ("web/assets", "web/assets"),
    ("web/demo-media", "web/demo-media"),
    ("CITATION.cff", "CITATION.cff"),
    ("LICENSE", "LICENSE"),
)

#: Files that live in the bundle and are written by hand, not copied. They are
#: committed, they are hashed into the manifest like everything else, and the
#: builder never overwrites them.
AUTHORED: tuple[str, ...] = ("README_KO.md",)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _expand(src: Path, dst_rel: str) -> list[tuple[Path, str]]:
    if src.is_dir():
        out = []
        for f in sorted(p for p in src.rglob("*") if p.is_file()):
            out.append((f, f"{dst_rel}/{f.relative_to(src).as_posix()}"))
        return out
    return [(src, dst_rel)]


def plan() -> list[tuple[Path, str]]:
    """Every (source file, bundle-relative path) the bundle should contain."""
    pairs: list[tuple[Path, str]] = []
    missing = []
    for src_rel, dst_rel in PAYLOAD:
        src = REPO / src_rel
        if not src.exists():
            missing.append(src_rel)
            continue
        pairs.extend(_expand(src, dst_rel))
    for rel in AUTHORED:
        p = BUNDLE / rel
        if not p.is_file():
            missing.append(f"release/kcf-finals-2026/{rel}")
            continue
        pairs.append((p, rel))
    if missing:
        raise SystemExit(
            "the bundle is missing sources and would ship with a hole in it:\n  "
            + "\n  ".join(missing)
        )
    return sorted(pairs, key=lambda pair: pair[1])


def assemble(pairs: list[tuple[Path, str]]) -> None:
    for src, dst_rel in pairs:
        dst = BUNDLE / dst_rel
        if dst.resolve() == src.resolve():
            continue  # an authored file is already in place
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)


def manifest_of(pairs: list[tuple[Path, str]]) -> dict:
    return {
        "_readme": (
            "SHA-256 of every file release/kcf-finals-2026/ should contain, written by "
            "scripts/build_finals_bundle.py. Re-run `make finals-bundle` to rebuild the "
            "payload and check it against this file; see docs/finals_bundle.md."
        ),
        "bundle": "kcf-finals-2026",
        "files": [
            {"path": dst_rel, "sha256": sha256(src), "bytes": src.stat().st_size,
             "source": str(src.relative_to(REPO).as_posix())}
            for src, dst_rel in pairs
        ],
    }


def differences(built: dict, committed: dict) -> list[str]:
    a = {f["path"]: (f["sha256"], f["bytes"]) for f in built["files"]}
    b = {f["path"]: (f["sha256"], f["bytes"]) for f in committed["files"]}
    out = []
    for path in sorted(set(a) - set(b)):
        out.append(f"+ {path} is in the bundle and not in the manifest")
    for path in sorted(set(b) - set(a)):
        out.append(f"- {path} is in the manifest and not in the bundle")
    for path in sorted(set(a) & set(b)):
        if a[path] != b[path]:
            out.append(f"~ {path} {b[path][0][:12]} ({b[path][1]} B) -> "
                       f"{a[path][0][:12]} ({a[path][1]} B)")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--update", action="store_true",
                    help="rewrite MANIFEST.json instead of checking against it")
    args = ap.parse_args(argv)

    BUNDLE.mkdir(parents=True, exist_ok=True)
    pairs = plan()
    assemble(pairs)
    built = manifest_of(pairs)

    if args.update:
        MANIFEST.write_text(json.dumps(built, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
        print(f"wrote {MANIFEST.relative_to(REPO)} — {len(built['files'])} files")
        return 0

    if not MANIFEST.is_file():
        print(f"{MANIFEST.relative_to(REPO)} does not exist; run with --update first",
              file=sys.stderr)
        return 1

    committed = json.loads(MANIFEST.read_text(encoding="utf-8"))
    diff = differences(built, committed)
    if diff:
        print("the rebuilt bundle is not the one MANIFEST.json describes:", file=sys.stderr)
        for line in diff:
            print(f"  {line}", file=sys.stderr)
        print("\nIf the change is intended, re-run with --update and commit the manifest.",
              file=sys.stderr)
        return 1
    print(f"OK — release/kcf-finals-2026/ rebuilt byte-identically, "
          f"{len(built['files'])} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
