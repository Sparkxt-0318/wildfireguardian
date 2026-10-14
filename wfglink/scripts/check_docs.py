#!/usr/bin/env python3
"""Documentation guard for wfglink.

Checks, with the standard library only:
1. No em dash (U+2014) or en dash (U+2013) in wfglink Markdown, configs or UI strings.
   docs/PROMPT.md is exempt because it is the user's text, verbatim.
2. Every number tag `<!-- n:KEY -->` refers to an entry in results/NUMBERS.json,
   and the number written just before the tag matches the registry value at the
   precision shown.
3. Every number in result sections carries a tag. Result sections are the README
   "## Current status" section and the "- Results:" bullet (with its indented
   sub-bullets) of each LOG.md entry. Dates, times, identifiers such as C1 or M0,
   and text inside backticks are not treated as numbers.
4. No NUMBERS.json entry was produced from a dirty source tree.

Exit code 0 when everything passes, 1 otherwise.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NUMBERS = ROOT / "results" / "NUMBERS.json"
DASHES = {"—": "em dash", "–": "en dash"}
DASH_EXEMPT = {ROOT / "docs" / "PROMPT.md"}
DASH_GLOBS = ["*.md", "docs/*.md", "data/*.md", "booth/*.md", "configs/**/*.yaml",
              "src/wfglink/ui/*.py", "src/wfglink/render/*.py"]

TAG_RE = re.compile(r"<!--\s*n:([A-Za-z0-9_.\-]+)\s*-->")
# A number not glued to letters, other digits, dots, hyphens, slashes or colons.
NUM_RE = re.compile(r"(?<![\w.\-/:])(\d+(?:\.\d+)?)(?![\w\-/:]|\.\d)")
TAGGED_NUM_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*(?:%|[^\s<]*)?\s*<!--\s*n:([A-Za-z0-9_.\-]+)\s*-->")
EXEMPT_PREV_WORDS = {"section", "sections", "version", "step", "steps", "milestone", "check", "python", "figure", "table", "sitting", "sittings"}


def strip_code(line: str) -> str:
    return re.sub(r"`[^`]*`", "", line)


def dash_problems() -> list[str]:
    problems = []
    seen = set()
    for pattern in DASH_GLOBS:
        for path in ROOT.glob(pattern):
            if path in DASH_EXEMPT or path in seen or ".venv" in path.parts:
                continue
            seen.add(path)
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                for ch, name in DASHES.items():
                    if ch in line:
                        problems.append(f"{path.relative_to(ROOT)}:{i}: {name}")
    return problems


def load_numbers() -> dict:
    data = json.loads(NUMBERS.read_text(encoding="utf-8"))
    return data.get("numbers", {})


def decimals(text: str) -> int:
    return len(text.split(".")[1]) if "." in text else 0


def tag_problems(numbers: dict) -> list[str]:
    problems = []
    for path in [ROOT / "README.md", ROOT / "PLAN.md", ROOT / "LOG.md", *sorted((ROOT / "docs").glob("*.md"))]:
        if not path.exists() or path in DASH_EXEMPT:
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for key in TAG_RE.findall(line):
                if key not in numbers:
                    problems.append(f"{path.relative_to(ROOT)}:{i}: tag n:{key} not in NUMBERS.json")
            for shown, key in TAGGED_NUM_RE.findall(line):
                entry = numbers.get(key)
                if entry is None or not isinstance(entry.get("value"), (int, float)):
                    continue
                want = round(float(entry["value"]), decimals(shown))
                if abs(float(shown) - want) > 1e-9:
                    problems.append(f"{path.relative_to(ROOT)}:{i}: shows {shown} but n:{key} is {entry['value']}")
    return problems


def result_lines() -> list[tuple[Path, int, str]]:
    out = []
    readme = ROOT / "README.md"
    if readme.exists():
        inside = False
        for i, line in enumerate(readme.read_text(encoding="utf-8").splitlines(), 1):
            if line.startswith("## "):
                inside = line.strip().lower() == "## current status"
                continue
            if inside:
                out.append((readme, i, line))
    log = ROOT / "LOG.md"
    if log.exists():
        inside = False
        for i, line in enumerate(log.read_text(encoding="utf-8").splitlines(), 1):
            if line.startswith("- Results:"):
                inside = True
                out.append((log, i, line[len("- Results:"):]))
                continue
            if inside and line.startswith("  "):
                out.append((log, i, line))
                continue
            inside = False
    return out


def untagged_problems() -> list[str]:
    problems = []
    for path, i, line in result_lines():
        text = strip_code(line)
        for m in NUM_RE.finditer(text):
            before = text[: m.start()].rstrip().split()
            if before and before[-1].lower().strip("(,") in EXEMPT_PREV_WORDS:
                continue
            tail = text[m.end(): m.end() + 40]
            if re.match(r"\s*(?:%|[^\s<]*)?\s*<!--\s*n:", tail):
                continue
            problems.append(f"{path.relative_to(ROOT)}:{i}: untagged result number {m.group(1)!r}")
    return problems


def dirty_problems(numbers: dict) -> list[str]:
    return [f"NUMBERS.json: {key} was produced from a dirty tree" for key, e in numbers.items() if e.get("git_dirty")]


def main() -> int:
    numbers = load_numbers()
    problems = dash_problems() + tag_problems(numbers) + untagged_problems() + dirty_problems(numbers)
    if problems:
        print("check_docs: FAIL")
        for p in problems:
            print("  " + p)
        return 1
    print(f"check_docs: OK ({len(numbers)} registered numbers)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
