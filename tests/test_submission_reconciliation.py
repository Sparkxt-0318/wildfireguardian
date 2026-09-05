"""The 제출본 대비 정본 sheet must stay resolvable, and must stay the only copy.

WFG-018.

THE TWO FAILURES THESE PREVENT
------------------------------
1. **A key that stops resolving.** ``docs/submission_reconciliation.md`` ends
   with a list of the registry keys behind every CURRENT value on the sheet.
   That list is the sheet's whole claim to being checkable: a judge is told
   "every current number here is a key in ``docs/NUMBERS.json``". If a key is
   renamed — and one was renamed during this row's own build, because the
   collision checker anchors on key words — the sentence silently becomes
   false. ``make verify`` cannot catch it: it verifies entries that exist, not
   prose that names them.

2. **The table growing a second copy.** ``docs/auto/JUDGE_QA.md`` §0 carried
   its own version of this table and had already drifted from the artifacts
   (it recorded the README delay row as an unresolved question after the row
   was known). §0 now links to the sheet instead. A future edit that pastes the
   table back in is the drift starting again, so the link is held in place
   here.

⚠ WHAT THESE DO NOT CHECK. Not whether a number is *right* — that is
``scripts/verify_numbers.py``. Not whether a retired value is labelled — that
is ``scripts/check_forbidden.py`` LABEL_NEAR. These hold the sheet's
*references*, which no other gate reads.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SHEET = REPO / "docs" / "submission_reconciliation.md"
JUDGE_QA = REPO / "docs" / "auto" / "JUDGE_QA.md"
NUMBERS = REPO / "docs" / "NUMBERS.json"

#: The sheet's closing section, which lists the keys behind its current values.
_SOURCES_HEADING = "## 출처"


def _sheet() -> str:
    return SHEET.read_text(encoding="utf-8")


def _registry() -> dict:
    return json.loads(NUMBERS.read_text(encoding="utf-8"))["numbers"]


def _keys_cited_in_sources() -> list[str]:
    text = _sheet()
    tail = text[text.index(_SOURCES_HEADING):]
    # Backticked tokens that look like registry keys: lower_snake_case, no dots
    # and no slashes, so file paths and JSON paths are excluded.
    return [t for t in re.findall(r"`([a-z0-9_]+)`", tail) if "_" in t]


def test_the_sheet_exists_and_names_its_sources() -> None:
    assert SHEET.exists(), "the reconciliation sheet is the WFG-018 deliverable"
    keys = _keys_cited_in_sources()
    # A silently-emptied list would make every other assertion here vacuous.
    assert len(keys) >= 20, f"expected the sources list to name the keys, got {keys}"


def test_every_key_the_sheet_cites_resolves_in_the_registry() -> None:
    registry = _registry()
    missing = sorted(k for k in _keys_cited_in_sources() if k not in registry)
    assert not missing, (
        "docs/submission_reconciliation.md tells a judge that every current "
        "value on it is a docs/NUMBERS.json key. These do not resolve: "
        f"{missing}"
    )


def test_the_sheet_keeps_both_sides_of_the_459_series_row() -> None:
    """Deleting the retired value would destroy what the sheet is for."""
    text = _sheet()
    for literal in ("438 / 18 / 3", "414 / 42 / 2"):
        assert literal in text, (
            f"{literal!r} is missing. The sheet exists to put the submitted "
            "value and the canonical value on one line; dropping either half "
            "turns it into an ordinary numbers table."
        )


def test_judge_qa_links_to_the_sheet_rather_than_copying_it() -> None:
    text = JUDGE_QA.read_text(encoding="utf-8")
    assert "submission_reconciliation.md" in text, (
        "JUDGE_QA.md §0 must point at the reconciliation sheet"
    )
    section = text[text.index("## 0."):text.index("## 1.")]
    # The duplicated table was a markdown table of submitted-vs-current rows.
    # One or two rows of context are fine; a full restatement is the drift.
    row_count = sum(1 for line in section.splitlines()
                    if line.startswith("|") and line.count("|") >= 4)
    assert row_count == 0, (
        "JUDGE_QA §0 has grown a table again. The sheet is the single home for "
        f"these rows (found {row_count} table lines)."
    )
