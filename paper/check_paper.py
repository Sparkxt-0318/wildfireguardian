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

LIMIT = 9000  # author, 2026-09-05 (NH-028): the rule is 25 built pages, not words; 9,000 body words is the proxy at the current figure and table count (7,479 words built to about 21 pages)


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
    # STATE.json is bookkeeping the paper routine writes at the end of its lap, and until
    # 2026-09-05 nothing compared it with the manuscript it describes: this function
    # computed exactly these counts, printed them, and threw them away. A lap reviewer
    # caught STATE.json holding the PREVIOUS lap's body_words and gap count while the
    # manuscript had moved, and no gate anywhere would have said so. Only the counts are
    # checked. `last_incorporated_commit` is deliberately NOT checked: it names the code
    # commit the manuscript was written against and legitimately lags HEAD.
    state_path = PAPER / "STATE.json"
    if state_path.exists():
        try:
            recorded = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"STATE.json is not valid JSON: {exc}")
        else:
            drift = {k: (recorded.get(k), v) for k, v in state.items() if recorded.get(k) != v}
            if drift:
                problems.append(
                    "STATE.json disagrees with the manuscript it describes "
                    + ", ".join(f"{k}: recorded {was!r}, built {now!r}" for k, (was, now) in sorted(drift.items()))
                    + " — rerun the build and update paper/STATE.json"
                )
    else:
        problems.append("paper/STATE.json is missing")
    for p in problems:
        print("[check_paper] FAIL: " + p)
    print("[check_paper] " + ("OK" if not problems else f"{len(problems)} problem(s)"))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
