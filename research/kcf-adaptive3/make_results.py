#!/usr/bin/env python3
"""Assemble RESULTS.md: prose from RESULTS.template.md, tables from derived/tables.md (printed by make_numbers.py)."""
import re
from pathlib import Path

H = Path(__file__).resolve().parent
sec = {}
for blk in re.split(r"\n(?=## )", (H / "derived" / "tables.md").read_text()):
    title, body = blk.split("\n", 1)
    sec[title.lstrip("# ").strip()] = body.strip()
t = (H / "RESULTS.template.md").read_text()
for k, v in sec.items():
    t = t.replace("{{" + k + "}}", v)
assert "{{" not in t, re.findall(r"\{\{.*?\}\}", t)
(H / "RESULTS.md").write_text(t)
