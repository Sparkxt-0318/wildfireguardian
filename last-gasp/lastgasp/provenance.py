"""Run provenance: git commit and whether code or config differed from it at run time."""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git_info():
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        # Only code and configuration matter for reproducibility; docs and results may change later.
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "lastgasp", "scripts", "configs",
                                "data/processed", "requirements.txt"], cwd=ROOT, capture_output=True,
                               text=True).stdout.strip()
        return {"commit": head, "code_dirty": bool(dirty)}
    except Exception as exc:  # git missing
        return {"commit": "unknown", "error": str(exc)}
