"""Clip settings files (data/clips/<id>.yaml), read the same way by every command.

The settings path is taken as given (relative to the working directory), as `process`
always did, and the project folder is tried when that path does not exist. The video
named by `file` is relative to the project folder. `process` analyses the first segment of
`segments_s`, so a file-mode run of a clip starts at that segment's start, and its frame
indices and times count from there.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from wfglink import PROJECT_ROOT


def load_clip_settings(path: str | Path) -> tuple[dict[str, Any], Path, Path]:
    """(settings, video path, settings path) of a clip settings file."""
    p = Path(path)
    if not p.exists() and not p.is_absolute() and (PROJECT_ROOT / p).exists():
        p = PROJECT_ROOT / p
    cc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not cc.get("file"):
        raise ValueError(f"{p}: no 'file' entry")
    return cc, PROJECT_ROOT / cc["file"], p


def segments(cc: dict[str, Any]) -> list[tuple[float, float | None]]:
    """The clip's segments as (start, end) in clip seconds; the whole clip when none are given."""
    out = []
    for seg in cc.get("segments_s") or [[None, None]]:
        a, b = (list(seg) + [None, None])[:2]
        out.append((float(a or 0.0), None if b is None else float(b)))
    return out


def clip_id(cc: dict[str, Any], video: Path) -> str:
    return str(cc.get("clip_id") or video.stem)
