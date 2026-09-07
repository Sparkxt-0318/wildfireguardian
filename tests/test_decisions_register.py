"""The decision register must keep pointing at the records that hold its evidence.

`docs/DECISIONS.md` deliberately holds no evidence of its own: every row cites
the document that carries the measurement. That design has exactly one failure
mode — a cited document is renamed or moved and the register keeps claiming the
decision is written down somewhere, which is worse than not claiming it at all.

The second test guards the status vocabulary. The register's value is that
"SETTLED" and "STOPPED" and "ACCEPTED" mean fixed things; a row that invents a
sixth status reads as if it had one of the five.
"""

from __future__ import annotations

import re
from pathlib import Path

REGISTER = Path(__file__).resolve().parents[1] / "docs" / "DECISIONS.md"

#: The statuses defined in the register's own "How to read" table.
STATUSES = {"SETTLED", "STOPPED", "ACCEPTED", "OPEN", "REVERSED"}

_LINK = re.compile(r"\]\(([^)]+)\)")


def _text() -> str:
    return REGISTER.read_text(encoding="utf-8")


def test_every_link_in_the_decision_register_resolves():
    broken = []
    for target in _LINK.findall(_text()):
        if target.startswith(("http://", "https://")):
            continue
        rel = target.split("#", 1)[0]
        if rel and not (REGISTER.parent / rel).exists():
            broken.append(target)
    assert not broken, f"DECISIONS.md cites files that do not exist: {broken}"


def test_the_register_uses_only_the_statuses_it_defines():
    used = set()
    for line in _text().splitlines():
        if not line.startswith("|"):
            continue
        for cell in (c.strip() for c in line.split("|")):
            if re.fullmatch(r"[A-Z]{4,}", cell):
                used.add(cell)
    assert used, "no status cell found — has the table shape changed?"
    assert used <= STATUSES, f"undefined status in DECISIONS.md: {used - STATUSES}"
    assert STATUSES <= used, f"status defined but never used: {STATUSES - used}"
