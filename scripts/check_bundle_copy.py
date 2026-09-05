#!/usr/bin/env python3
"""Verify a COPY of the finals bundle against the manifest that travels with it.

WFG-037 (the booth recipe), KCF_READINESS R9. Read ``docs/auto/finals/BOOTH_SETUP.md``
before this file; this is the one command in that recipe that has no substitute.

WHY THIS EXISTS, AND WHAT IT IS NOT
-----------------------------------
``scripts/build_finals_bundle.py`` (``make finals-bundle``) checks that the bundle
the REPOSITORY produces is the bundle ``MANIFEST.json`` describes. Its own docstring
claimed a second job — that re-running it on the laptop catches a USB stick that has
silently corrupted a file — and that claim is false, because the first thing it does
is copy every payload file out of the repository over the top of the bundle. Measured
on 2026-09-05 by appending seven bytes to ``release/kcf-finals-2026/web/finals.html``
and running it: the file was overwritten from the tree and the run reported OK. So the
corruption a booth actually suffers — a file that went bad on the stick, in the copy on
the desktop, or in the copy onto the second stick — was checked by nothing.

This script is the missing half. It **reads** a folder and never writes to it, so it
can be pointed at a mounted USB stick, at the copy on the desktop, or at the folder on
a borrowed machine, and it needs neither this repository nor anything outside the
Python standard library. It answers one question: *is this folder, byte for byte, the
bundle its own ``MANIFEST.json`` says it is?*

It cannot tell you the folder is the RIGHT bundle. A stick holding an old bundle and
that bundle's own manifest passes, because both travelled together. The check against
the repository is the other script, and the commit that a bundle came from is a
question for the tree, not for the stick.

USE
---
    python3 scripts/check_bundle_copy.py /media/usb/kcf-finals-2026
    python3 check_bundle_copy.py .          # from inside the copy, no repository

Exit 0 and one line when the copy is intact. Exit 1 and a list naming every file that
is missing, extra or different when it is not. The recovery for a bad file is the
second stick; this script says which file, not how to rebuild it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

MANIFEST_NAME = "MANIFEST.json"
#: Read in blocks so a 2 MB screen does not become 2 MB of resident memory on a
#: machine that is also driving a projector.
BLOCK = 1 << 20


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(BLOCK), b""):
            h.update(chunk)
    return h.hexdigest()


def check(folder: Path) -> list[str]:
    """Return the problems found in ``folder``; an empty list means it is intact.

    The manifest is the folder's own, deliberately: at the booth there is no other
    one to compare against, and a checker that needs the repository is a checker the
    laptop-has-died case cannot run.
    """
    manifest_path = folder / MANIFEST_NAME
    if not manifest_path.is_file():
        return [
            "%s is not there, so this folder cannot be checked at all. "
            "It is not the finals bundle, or the copy did not finish." % MANIFEST_NAME
        ]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries = manifest["files"]
    except (ValueError, KeyError, UnicodeDecodeError) as exc:
        return ["%s is unreadable (%s): %s" % (MANIFEST_NAME, type(exc).__name__, exc)]

    problems: list[str] = []
    described = {MANIFEST_NAME}
    for entry in entries:
        rel = entry["path"]
        described.add(rel)
        target = folder / rel
        if not target.is_file():
            problems.append("MISSING   %s" % rel)
            continue
        size = target.stat().st_size
        if size != entry["bytes"]:
            # Size first: it is the cheap half of the same question and it names the
            # likely cause (a copy that stopped) instead of only saying "different".
            problems.append(
                "SIZE      %s — %d bytes on disk, %d in the manifest"
                % (rel, size, entry["bytes"])
            )
            continue
        if sha256(target) != entry["sha256"]:
            problems.append("CORRUPT   %s — right size, wrong bytes" % rel)

    for found in sorted(p for p in folder.rglob("*") if p.is_file()):
        rel = found.relative_to(folder).as_posix()
        if rel not in described:
            problems.append("EXTRA     %s — in the folder and not in the manifest" % rel)
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check a copy of the finals bundle against the MANIFEST.json inside it. "
            "Reads only; never writes to the folder."
        )
    )
    parser.add_argument(
        "folder",
        nargs="?",
        default=".",
        help="the bundle folder to check (default: the current directory)",
    )
    args = parser.parse_args(argv)

    folder = Path(args.folder).expanduser()
    if not folder.is_dir():
        print("not a folder: %s" % folder, file=sys.stderr)
        return 1

    problems = check(folder)
    if not problems:
        print("OK — %s matches its own %s." % (folder, MANIFEST_NAME))
        return 0
    print("%s does NOT match its own %s:" % (folder, MANIFEST_NAME), file=sys.stderr)
    for line in problems:
        print("  " + line, file=sys.stderr)
    print(
        "\nUse the second USB stick. This check says which file is wrong, "
        "not how to rebuild it.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
