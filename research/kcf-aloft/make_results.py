#!/usr/bin/env python3
"""Fill RESULTS.template.md with the tables printed by tables.py (so no table is typed by hand).

    python3 tables.py numbers.json > derived/tables.md && python3 make_results.py
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
sec, cur = {}, None
for line in (HERE / "derived" / "tables.md").read_text().splitlines():
    m = re.match(r"## (T\d+b?) ", line)
    if m:
        cur = m.group(1)
        sec[cur] = []
    elif line.startswith("## "):
        cur = None
    elif cur:
        sec[cur].append(line)
tpl = (HERE / "RESULTS.template.md").read_text()


def fill(m):
    key, part = m.group(1), m.group(2)
    body = "\n".join(sec[key]).strip("\n")
    if part:                                   # {{T1:2}} = the 2nd blank-line-separated block of the section
        blocks = [b for b in re.split(r"\n\s*\n", body) if b.strip()]
        return blocks[int(part) - 1]
    return body


out = re.sub(r"\{\{(T\d+b?)(?::(\d+))?\}\}", fill, tpl)
(HERE / "RESULTS.md").write_text(out)
print("wrote RESULTS.md,", len(out.splitlines()), "lines; sections available:", ", ".join(sec))
