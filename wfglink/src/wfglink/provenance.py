"""Provenance helpers: git state, config hashes, file hashes and the NUMBERS.json registry.

Every number quoted in README, PLAN or LOG summaries is written here by `record_number`,
together with the script, config and git commit that produced it.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import platform
import subprocess
from pathlib import Path
from typing import Any, Mapping

from wfglink import PROJECT_ROOT

NUMBERS_PATH = PROJECT_ROOT / "results" / "NUMBERS.json"
SHANGHAI = _dt.timezone(_dt.timedelta(hours=8), name="Asia/Shanghai")
# Paths whose uncommitted changes make a result irreproducible. Results, logs and docs
# are excluded on purpose: writing a result must not mark its own run as dirty.
SOURCE_PATHS = ("src", "configs", "scripts", "pyproject.toml", "requirements.txt")


def now_shanghai() -> str:
    """Current time in Asia/Shanghai as ISO 8601 with seconds."""
    return _dt.datetime.now(SHANGHAI).isoformat(timespec="seconds")


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=PROJECT_ROOT, check=True, capture_output=True, text=True,
    ).stdout.strip()


def git_state() -> dict[str, Any]:
    """Commit hash and whether the wfglink source tree has uncommitted changes."""
    try:
        commit = _git("rev-parse", "HEAD")
        status = _git("status", "--porcelain", "--", *SOURCE_PATHS)
        return {"git_commit": commit, "git_dirty": bool(status)}
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"git_commit": "unknown", "git_dirty": True}


def sha256_file(path: str | os.PathLike, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def sha256_json(obj: Any) -> str:
    """Stable hash of a JSON-serialisable object (sorted keys, compact separators)."""
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def rel(path: str | os.PathLike) -> str:
    """Path relative to the wfglink root when possible, for portable records."""
    p = Path(path).resolve()
    try:
        return str(p.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(p)


def run_record(script: str, config: Mapping[str, Any] | None = None,
               config_path: str | None = None,
               inputs: Mapping[str, str | os.PathLike] | None = None) -> dict[str, Any]:
    """Provenance block shared by summary JSON files and NUMBERS.json entries."""
    record: dict[str, Any] = {
        "script": script,
        "config": config_path,
        "config_sha256": sha256_json(config) if config is not None else None,
        **git_state(),
        "inputs": {name: sha256_file(p) for name, p in (inputs or {}).items()},
        "produced_at": now_shanghai(),
        "host": f"{platform.system()} {platform.machine()} Python {platform.python_version()}",
    }
    return record


def load_numbers(path: Path = NUMBERS_PATH) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"schema_version": 1, "numbers": {}}


def record_number(key: str, value: float | int, unit: str, description: str, *,
                  script: str, config: Mapping[str, Any] | None = None,
                  config_path: str | None = None,
                  inputs: Mapping[str, str | os.PathLike] | None = None,
                  path: Path = NUMBERS_PATH) -> dict[str, Any]:
    """Insert or replace one entry in NUMBERS.json and return it."""
    data = load_numbers(path)
    entry = {
        "value": value,
        "unit": unit,
        "description": description,
        **run_record(script, config, config_path, inputs),
    }
    data.setdefault("numbers", {})[key] = entry
    data["numbers"] = dict(sorted(data["numbers"].items()))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)
    return entry
