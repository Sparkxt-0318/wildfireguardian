#!/usr/bin/env python3
"""Pre-commit guard for wfglink, run by hand before every commit.

Fails (exit 1) when any staged file:
- lies outside wfglink/ (other sessions own the rest of the repository),
- is a video file (raw video is never committed),
- is larger than 5 MB.

Standard library only, so it runs before the virtual environment exists.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

MAX_BYTES = 5 * 1024 * 1024
VIDEO_SUFFIXES = {
    ".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm", ".ogv", ".ts",
    ".h264", ".h265", ".hevc", ".mpg", ".mpeg", ".wmv", ".flv", ".3gp", ".mts",
}


def staged_files(repo: Path) -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"],
        cwd=repo, check=True, capture_output=True,
    ).stdout.decode("utf-8")
    return [p for p in out.split("\0") if p]


def main() -> int:
    repo = Path(subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], check=True, capture_output=True, text=True,
    ).stdout.strip())
    problems: list[str] = []
    files = staged_files(repo)
    for rel in files:
        path = repo / rel
        if not rel.startswith("wfglink/"):
            problems.append(f"outside wfglink/: {rel}")
            continue
        if path.suffix.lower() in VIDEO_SUFFIXES:
            problems.append(f"video file: {rel}")
        if path.is_file() and path.stat().st_size > MAX_BYTES:
            problems.append(f"larger than 5 MB ({path.stat().st_size} bytes): {rel}")
    if problems:
        print("check_staged: FAIL")
        for p in problems:
            print("  " + p)
        return 1
    print(f"check_staged: OK ({len(files)} staged files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
