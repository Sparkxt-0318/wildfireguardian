#!/usr/bin/env python
"""Compare the running environment against the pins in requirements.txt.

Round-3 PHASE 1-E.

WHY THIS EXISTS
---------------
Round 2 shipped a requirements.txt that DECLARED `networkx`, `osmnx` and
`geopandas` while the working environment had none of them. The consequence was
silent: five real-OSM tests skipped rather than ran, and three geospatial tests
failed in a way that read as a broken build. Lower bounds (`>=`) hid it.

This target makes "declared but not installed" a visible, non-zero exit.

Exit codes
    0  every pinned requirement is installed at the pinned version
    1  something is missing, or installed at a different version

Run:  python scripts/env_check.py
      python scripts/env_check.py --allow-version-drift
"""

from __future__ import annotations

import argparse
import re
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REQ = REPO / "requirements.txt"

PIN = re.compile(r"^\s*([A-Za-z0-9_.\-]+)\s*==\s*([^\s;#]+)")
LOOSE = re.compile(r"^\s*([A-Za-z0-9_.\-]+)\s*(>=|>|~=)\s*([^\s;#]+)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--allow-version-drift", action="store_true",
                    help="only fail on MISSING packages, not on version mismatches")
    args = ap.parse_args()

    if not REQ.exists():
        print(f"missing {REQ}", file=sys.stderr)
        return 1

    pinned: list[tuple[str, str]] = []
    loose: list[tuple[str, str, str]] = []
    for line in REQ.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("#"):
            continue
        if m := PIN.match(line):
            pinned.append((m.group(1), m.group(2)))
        elif m := LOOSE.match(line):
            loose.append((m.group(1), m.group(2), m.group(3)))

    print(f"python {sys.version.split()[0]}  ({sys.executable})")
    print(f"requirements.txt: {len(pinned)} pinned, {len(loose)} unpinned\n")

    missing: list[str] = []
    drifted: list[str] = []
    width = max((len(n) for n, _ in pinned), default=10)

    for name, want in sorted(pinned):
        try:
            got = version(name)
        except PackageNotFoundError:
            print(f"  MISSING  {name:{width}s}  pinned {want}")
            missing.append(name)
            continue
        if got == want:
            print(f"  ok       {name:{width}s}  {got}")
        else:
            print(f"  DRIFT    {name:{width}s}  pinned {want}, installed {got}")
            drifted.append(f"{name} (pinned {want}, installed {got})")

    for name, op, want in sorted(loose):
        try:
            got = version(name)
            print(f"  unpinned {name:{width}s}  {got}  (spec {op}{want}) "
                  "— consider pinning")
        except PackageNotFoundError:
            print(f"  MISSING  {name:{width}s}  spec {op}{want}")
            missing.append(name)

    print()
    if missing:
        print(f"MISSING ({len(missing)}): {', '.join(missing)}")
        print("  A declared-but-absent dependency turns tests into silent skips.")
        print("  Install it, or remove the declaration. See docs/ENVIRONMENT.md.")
    if drifted:
        print(f"VERSION DRIFT ({len(drifted)}):")
        for d in drifted:
            print(f"  - {d}")
        print("  Note: osmnx is pinned to match data/snapshots/osm-*.graphml's")
        print("  `created_with`. Floating it adds a hidden variable to any")
        print("  before/after comparison.")

    if missing or (drifted and not args.allow_version_drift):
        print("\nFAILED")
        return 1
    print("OK — the environment matches requirements.txt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
