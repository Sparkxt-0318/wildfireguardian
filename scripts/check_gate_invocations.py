#!/usr/bin/env python
"""Fail if a gate is invoked through a pipe without ``pipefail`` in effect.

Session 10 follow-up, task 2. This gate exists because of a specific mistake,
recorded so it cannot be repeated quietly:

    python scripts/verify_numbers.py | tail -2 && python scripts/check_forbidden.py | tail -1 && git commit ...

In POSIX shell a pipeline's exit status is the status of its LAST command, so
the shell read ``tail``'s zero and the ``&&`` chain walked straight past a gate
that had failed. A commit was made on top of a red gate. The gates were never
wrong; the way they were called was.

Two defences, and this is the second:

1. ``Makefile`` sets ``.SHELLFLAGS := -o pipefail -e -c``, so any recipe that
   pipes a gate fails on the gate rather than on the tail of the pipe.
2. This script scans authored, tracked material for the pattern anywhere else —
   shell scripts, the Makefile, CI workflows, and the runnable code blocks in
   documentation, which is where a reader copies a command from.

WHAT COUNTS AS A VIOLATION
A line that invokes one of the GATES, contains a real pipe (``|`` that is not
``||`` and not a Markdown table cell), and has no ``pipefail`` established
before it in the same file or fenced block.

Markdown tables are full of ``|`` and none of them are pipes, so ``.md`` is
scanned ONLY inside fenced code blocks whose language is shell-like.

Run:  python scripts/check_gate_invocations.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

#: The gate entry points. A pipe after any of these is what this script hunts.
GATES = (
    "verify_numbers.py",
    "check_forbidden.py",
    "check_region_literals.py",
    "check_arm_isolation.py",
    "check_gate_invocations.py",
    "freeze_baseline.py",
    "snapshot_external.py",
    "env_check.py",
)

#: `make` targets that run one or more gates.
GATE_TARGETS = ("make verify", "make all-checks", "make baseline-verify",
                "make snapshot-verify", "make env-check", "make check-forbidden",
                "make verify-numbers", "make check-region-literals")

SHELL_FENCE = re.compile(r"^\s*```+\s*(bash|sh|shell|console|zsh)?\s*$", re.I)
PIPEFAIL = re.compile(r"pipefail")

#: A pipe that is not `||`, not `|&`, and not the leading/trailing bar of a
#: Markdown table row. Lookarounds keep `a || b` and `a |& b` out.
REAL_PIPE = re.compile(r"(?<![|&])\|(?![|&])")


def tracked(patterns: tuple[str, ...]) -> list[Path]:
    out = subprocess.check_output(["git", "ls-files", *patterns], cwd=REPO).decode()
    return [REPO / p for p in out.splitlines() if p.strip()]


def has_gate(line: str) -> bool:
    return any(g in line for g in GATES) or any(t in line for t in GATE_TARGETS)


def scan_plain(path: Path) -> list[tuple[int, str]]:
    """Shell / Makefile / YAML: pipefail must appear before the offending line."""
    problems: list[tuple[int, str]] = []
    armed = False
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if PIPEFAIL.search(line):
            armed = True
            continue
        stripped = line.split("#", 1)[0]
        if has_gate(stripped) and REAL_PIPE.search(stripped) and not armed:
            problems.append((i, line.strip()))
    return problems


def scan_markdown(path: Path) -> list[tuple[int, str]]:
    """Documentation: only shell-ish fenced blocks, and pipefail is per block.

    ⚠ Fence state must be tracked for EVERY fence, not only shell ones. The
    first version toggled only on shell fences, so a ```python block's closing
    ``` read as an opening bare fence and every Markdown table after it became
    "inside a shell block" — three table rows full of ``|`` were reported as
    piped gate invocations. Open/close is tracked here independently of whether
    the block is one we actually scan.
    """
    problems: list[tuple[int, str]] = []
    fence_open = False
    scanning = False
    armed = False
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.lstrip().startswith("```"):
            if fence_open:
                fence_open, scanning, armed = False, False, False
            else:
                fence_open = True
                scanning = SHELL_FENCE.match(line) is not None
                armed = False
            continue
        if not scanning:
            continue
        if PIPEFAIL.search(line):
            armed = True
            continue
        stripped = line.split("#", 1)[0]
        if has_gate(stripped) and REAL_PIPE.search(stripped) and not armed:
            problems.append((i, line.strip()))
    return problems


def main() -> int:
    findings: list[str] = []

    for path in tracked(("*.sh", "Makefile", "*.mk", "*.yml", "*.yaml")):
        if not path.exists():
            continue
        if path.name == "Makefile" and PIPEFAIL.search(path.read_text(encoding="utf-8")):
            continue                                   # .SHELLFLAGS covers every recipe
        for lineno, text in scan_plain(path):
            findings.append(f"{path.relative_to(REPO)}:{lineno}  {text}")

    for path in tracked(("*.md",)):
        if not path.exists():
            continue
        for lineno, text in scan_markdown(path):
            findings.append(f"{path.relative_to(REPO)}:{lineno}  {text}")

    n_scanned = len(tracked(("*.sh", "Makefile", "*.mk", "*.yml", "*.yaml", "*.md")))
    print(f"=== gate invocations through pipes ({n_scanned} tracked files) ===")
    if findings:
        print(f"\nFAILED: {len(findings)} gate invocation(s) piped without pipefail:\n")
        for f in findings:
            print("  " + f)
        print("\n  A pipeline's exit status is its LAST command's, so `gate | tail`")
        print("  reports tail's success and an && chain continues past a failure.")
        print("  Fix: put `set -o pipefail` above it, or drop the pipe.")
        return 1
    print("\nOK — no gate is invoked through a pipe without pipefail.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
