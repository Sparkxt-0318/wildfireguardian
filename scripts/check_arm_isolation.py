#!/usr/bin/env python
"""Arm isolation gate — Arm A must not move while other arms are explored.

Session 10 Phase 0. Session 10 runs experimental arms (C: terrain-resolved wind,
D: observed-front assimilation) alongside the frozen Arm A configuration that
the 본선 posters cite. The rule for the session is that Arm A does not change:
not a number, not an artifact, not a config default. A rule nobody can check is
a hope, so this is the check.

Every entry in docs/NUMBERS.json carries an explicit ``arm`` field. Entries that
predate Session 10 are Arm A and were backfilled as such. This script freezes a
sha256 of each Arm A entry and fails if any of them later differs, disappears,
or is quietly relabelled into another arm.

    python scripts/check_arm_isolation.py --backfill   # one-time: label as A
    python scripts/check_arm_isolation.py --freeze     # record the Arm A state
    python scripts/check_arm_isolation.py              # check (the gate)

Exit 1 on any drift.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NUMBERS = REPO / "docs" / "NUMBERS.json"
FREEZE = REPO / "docs" / "arm_a_freeze.json"

#: The formatting NUMBERS.json is written in. Verified to round-trip the file
#: byte-for-byte, so a backfill adds one line per entry and reformats nothing.
DUMP = dict(indent=2, ensure_ascii=False)


def load_numbers() -> dict:
    return json.loads(NUMBERS.read_text(encoding="utf-8"))


def write_numbers(doc: dict) -> None:
    NUMBERS.write_text(json.dumps(doc, **DUMP) + "\n", encoding="utf-8")


def entry_digest(entry: dict) -> str:
    """Stable digest of one registry entry, independent of key order."""
    return hashlib.sha256(
        json.dumps(entry, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def backfill() -> int:
    doc = load_numbers()
    changed = 0
    for key, entry in doc["numbers"].items():
        if "arm" not in entry:
            entry["arm"] = "A"          # appended last: a one-line diff per entry
            changed += 1
    write_numbers(doc)
    print(f"backfilled arm='A' on {changed} entries "
          f"({len(doc['numbers'])} total, {len(doc['numbers']) - changed} already labelled)")
    return 0


def freeze() -> int:
    doc = load_numbers()
    arm_a = {k: v for k, v in doc["numbers"].items() if v.get("arm") == "A"}
    if not arm_a:
        raise SystemExit("no Arm A entries found — run --backfill first")
    payload = {
        "schema_version": 1,
        "title": "Arm A immutability freeze — Session 10 Phase 0",
        "note": "Every entry below is Arm A and must not change while Session 10 "
                "runs. Regenerate ONLY when Arm A is deliberately revised, which "
                "Session 10 does not do.",
        "n_arm_a_entries": len(arm_a),
        "digests": {k: entry_digest(v) for k, v in sorted(arm_a.items())},
    }
    FREEZE.write_text(json.dumps(payload, **DUMP) + "\n", encoding="utf-8")
    print(f"froze {len(arm_a)} Arm A entries -> {FREEZE.relative_to(REPO)}")
    return 0


def check() -> int:
    if not FREEZE.exists():
        print(f"FAIL: {FREEZE.relative_to(REPO)} missing — nothing to check against")
        return 1
    frozen = json.loads(FREEZE.read_text(encoding="utf-8"))["digests"]
    live = load_numbers()["numbers"]

    problems: list[str] = []
    for key, digest in frozen.items():
        entry = live.get(key)
        if entry is None:
            problems.append(f"MISSING Arm A entry: {key}")
            continue
        if entry.get("arm") != "A":
            problems.append(f"RELABELLED out of Arm A: {key} -> arm={entry.get('arm')!r}")
            continue
        if entry_digest(entry) != digest:
            problems.append(f"CHANGED Arm A entry: {key}")

    new_a = [k for k, v in live.items() if v.get("arm") == "A" and k not in frozen]
    if new_a:
        problems.append("NEW entries claiming arm='A' (new work belongs to its own "
                        f"arm): {', '.join(sorted(new_a))}")

    unlabelled = [k for k, v in live.items() if "arm" not in v]
    if unlabelled:
        problems.append(f"UNLABELLED entries (no arm field): {', '.join(sorted(unlabelled))}")

    if problems:
        print("=== ARM ISOLATION VIOLATED ===")
        for p in problems:
            print("  " + p)
        return 1

    others = sorted({v.get("arm") for v in live.values()} - {"A"})
    print(f"OK — {len(frozen)} Arm A entries unchanged; "
          f"{len(live) - len(frozen)} entries in other arms "
          f"({', '.join(others) if others else 'none yet'}).")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", action="store_true")
    ap.add_argument("--freeze", action="store_true")
    args = ap.parse_args()
    if args.backfill:
        return backfill()
    if args.freeze:
        return freeze()
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
