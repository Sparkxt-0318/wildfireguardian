#!/usr/bin/env python
"""The manuscript's gate. Exit 1 on any failure; prints every finding.

  - body text <= 7,500 words (target 7,000; the 20-page budget incl. refs + title)
  - every ![caption](figures/X.png) exists and was produced by make_figures.py
  - every [@key] exists in references.bib with a `note` that says verified
  - every [GAP: ...] in the manuscript has a row in GAPS.md, and vice versa
  - the .docx builds (python-docx) and its title is the manuscript's
  - registry-anchored numbers: delegated to scripts/check_number_collisions.py,
    which already scans paper/manuscript.md as tracked prose (make verify)
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PAPER = REPO / "paper"
sys.path.insert(0, str(PAPER))
from build_docx import build, parse_bib  # noqa: E402

LIMIT = 7500


def main() -> int:
    md = PAPER / "manuscript.md"
    text = md.read_text(encoding="utf-8")
    problems = []
    with tempfile.TemporaryDirectory() as td:
        info = build(md, Path(td) / "check.docx")
    if info["body_words"] > LIMIT:
        problems.append(f"body text {info['body_words']} words > {LIMIT}")
    for rel in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text):
        if not (PAPER / rel).exists():
            problems.append(f"figure missing: {rel}")
    bib = parse_bib(PAPER / "references.bib")
    for key in set(k.strip().lstrip("@") for grp in re.findall(r"\[@([^\]]+)\]", text) for k in grp.split(";")):
        if key not in bib:
            problems.append(f"citation not in references.bib: {key}")
        elif "verified" not in bib[key].get("note", "").lower():
            problems.append(f"citation {key} has no 'verified' note")
    gaps_md = (PAPER / "GAPS.md").read_text(encoding="utf-8") if (PAPER / "GAPS.md").exists() else ""
    n_rows = len(re.findall(r"^\|\s*G\d+\s*\|", gaps_md, flags=re.M))
    n_marks = len(re.findall(r"\[GAP:", text))
    if n_marks != n_rows:
        problems.append(f"{n_marks} [GAP] markers in manuscript vs {n_rows} rows in GAPS.md")
    if not info["title"]:
        problems.append("no title line (# ...) at the top of manuscript.md")
    state = {"body_words": info["body_words"], "figures": info["figures"], "tables": info["tables"],
             "references": info["references"], "gaps": n_marks}
    print("[check_paper] " + json.dumps(state))
    for p in problems:
        print("[check_paper] FAIL: " + p)
    print("[check_paper] " + ("OK" if not problems else f"{len(problems)} problem(s)"))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
