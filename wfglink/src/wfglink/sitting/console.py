"""Terminal helpers for the guided sittings: headers, prompts, file intake and a resumable report.

The report is saved after every step, so a crash, a closed window or a re-run with
--from STEP never loses earlier results. In --yes mode (dry runs and tests) every prompt
takes its default answer.
"""
from __future__ import annotations

import json
import os
import shlex
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from wfglink.provenance import git_state, now_shanghai

BOLD = "\033[1m" if sys.stdout.isatty() else ""
DIM = "\033[2m" if sys.stdout.isatty() else ""
GREEN = "\033[32m" if sys.stdout.isatty() else ""
YELLOW = "\033[33m" if sys.stdout.isatty() else ""
RED = "\033[31m" if sys.stdout.isatty() else ""
RESET = "\033[0m" if sys.stdout.isatty() else ""


@dataclass
class Console:
    assume_yes: bool = False
    answers: dict[str, str] = field(default_factory=dict)   # scripted answers for tests

    def header(self, number: str, title: str, minutes: float | None = None) -> None:
        budget = f"  (about {minutes:g} min)" if minutes else ""
        print(f"\n{BOLD}== Step {number}: {title}{budget} =={RESET}", flush=True)

    def say(self, text: str = "") -> None:
        print(text, flush=True)

    def bullet(self, lines: list[str]) -> None:
        for i, line in enumerate(lines, 1):
            print(f"  {i}. {line}", flush=True)

    def ok(self, text: str) -> None:
        print(f"{GREEN}OK{RESET}  {text}", flush=True)

    def warn(self, text: str) -> None:
        print(f"{YELLOW}CHECK{RESET}  {text}", flush=True)

    def fail(self, text: str) -> None:
        print(f"{RED}PROBLEM{RESET}  {text}", flush=True)

    def ask(self, key: str, prompt: str, default: str = "") -> str:
        if key in self.answers:
            return self.answers[key]
        if self.assume_yes:
            return default
        suffix = f" [{default}]" if default else ""
        try:
            value = input(f"{BOLD}?{RESET} {prompt}{suffix}: ").strip()
        except EOFError:
            value = ""
        return value or default

    def ask_yes(self, key: str, prompt: str, default: bool = True) -> bool:
        d = "Y/n" if default else "y/N"
        value = self.ask(key, f"{prompt} ({d})", "").lower()
        if not value:
            return default
        return value.startswith("y")

    def ask_float(self, key: str, prompt: str, default: float | None = None,
                  lo: float | None = None, hi: float | None = None) -> float | None:
        while True:
            raw = self.ask(key, prompt, "" if default is None else f"{default:g}")
            if raw == "" or raw.lower() == "skip":
                return default
            try:
                value = float(raw.replace(",", "."))
            except ValueError:
                self.warn("Please type a number, or skip.")
                if self.assume_yes or key in self.answers:
                    return default
                continue
            if (lo is not None and value < lo) or (hi is not None and value > hi):
                self.warn(f"That looks wrong (expected between {lo:g} and {hi:g}). Please re-check.")
                if self.assume_yes or key in self.answers:
                    return value
                continue
            return value

    def wait_enter(self, key: str, prompt: str = "Press Enter when done") -> None:
        self.ask(key, prompt, "")

    def ask_files(self, key: str, prompt: str, suggestions: list[Path]) -> list[Path] | None:
        """Ask for one or more files. Drag files from Finder into the window, or accept the
        numbered suggestion. Returns None when the user types skip."""
        if suggestions:
            self.say("  Suggested (newest first):")
            for i, p in enumerate(suggestions[:6], 1):
                try:
                    size = p.stat().st_size / 1e6
                    when = time.strftime("%H:%M", time.localtime(p.stat().st_mtime))
                except OSError:
                    size, when = 0, "?"
                self.say(f"    [{i}] {p}  ({size:.0f} MB, {when})")
        raw = self.ask(key, prompt + " (number, dragged file(s), or skip)", "1" if suggestions else "skip")
        if raw.lower() == "skip":
            return None
        if raw.isdigit() and suggestions and 1 <= int(raw) <= len(suggestions):
            return [suggestions[int(raw) - 1]]
        if all(part.isdigit() for part in raw.replace(",", " ").split()) and suggestions:
            picks = [suggestions[int(x) - 1] for x in raw.replace(",", " ").split() if 1 <= int(x) <= len(suggestions)]
            if picks:
                return picks
        # Dragged paths: shell-quoted, possibly several, possibly with escaped spaces.
        try:
            parts = shlex.split(raw)
        except ValueError:
            parts = [raw]
        paths = [Path(os.path.expanduser(p)) for p in parts]
        missing = [str(p) for p in paths if not p.exists()]
        if missing:
            self.warn("Not found: " + ", ".join(missing))
            if self.assume_yes or key in self.answers:
                return None
            return self.ask_files(key, prompt, suggestions)
        return paths


def newest_files(folders: list[Path], suffixes: set[str], max_age_h: float = 12.0, limit: int = 6) -> list[Path]:
    """Recently modified files with the given suffixes in the folders (recursive, shallow)."""
    found = []
    cutoff = time.time() - max_age_h * 3600
    for folder in folders:
        if not folder.exists():
            continue
        try:
            for p in folder.rglob("*"):
                if p.suffix.lower() in suffixes and p.is_file() and not p.name.startswith("._"):
                    try:
                        if p.stat().st_mtime >= cutoff:
                            found.append(p)
                    except OSError:
                        continue
        except (PermissionError, OSError):
            continue
    found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return found[:limit]


class Report:
    """Combined JSON report for a sitting, saved after every step."""

    def __init__(self, path: Path, kind: str):
        self.path = Path(path)
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.data = {"kind": kind, "schema": 1, "started_at": now_shanghai(),
                         "git": git_state(), "steps": {}}
        self._t0 = time.monotonic()

    def done(self, step: str) -> bool:
        return self.data["steps"].get(step, {}).get("status") == "done"

    def put(self, step: str, payload: dict[str, Any], status: str = "done") -> None:
        self.data["steps"][step] = {"status": status, "at": now_shanghai(), **payload}
        self.save()

    def get(self, step: str) -> dict[str, Any]:
        return self.data["steps"].get(step, {})

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data["updated_at"] = now_shanghai()
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False, default=_jsonable) + "\n", encoding="utf-8")
        tmp.replace(self.path)


def _jsonable(obj: Any) -> Any:
    try:
        import numpy as np

        if isinstance(obj, np.generic):
            return obj.item()
        if isinstance(obj, np.ndarray):
            return obj.tolist()
    except Exception:
        pass
    if isinstance(obj, Path):
        return str(obj)
    return str(obj)
