#!/usr/bin/env python3
"""RESULTS.md = RESULTS.template.md with each {{heading}} replaced by that table from derived/tables.md."""
import re
from pathlib import Path

H = Path(__file__).resolve().parent
tabs = (H / "derived/tables.md").read_text()
sec = {}
for m in re.finditer(r"^### (.+?)\n(.*?)(?=^### |\Z)", tabs, re.S | re.M):
    sec[m.group(1).strip()] = m.group(2).strip()


def sub(m):
    k = m.group(1)
    if k not in sec:
        raise SystemExit(f"missing table: {k}")
    body = sec[k]
    body = re.split(r"\n(?:wind choice:|kept:|params \()", body)[0].strip()
    return f"**{k}**\n\n{body}"


out = re.sub(r"\{\{(.+?)\}\}", sub, (H / "RESULTS.template.md").read_text())
(H / "RESULTS.md").write_text(out)
print("RESULTS.md", len(out.splitlines()), "lines")
