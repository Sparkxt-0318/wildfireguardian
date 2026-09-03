"""The rescue delay-row bracket has two legitimate homes; prose must say which.

WFG-004 (2026-09-03). `README.md` quoted the dispatch-delay bracket **6 -> 34**
inside a paragraph that was otherwise the 439-series real-OSM lineage (the same
143 origins, exposure 6.12 -> 1.71). That value is not wrong and not a typo: it
is the pre-flip synthetic baseline's own bracket, preserved at
`data/processed/rescue_baseline_synthetic/rescue_verify.json`. Two real runs of
one script, and the README mixed them.

**Why this needs its own test.** `check_number_collisions.py` cannot see it.
That gate fires when a *registered* quantity appears with a different value near
its key's anchor words; here both brackets are correct values of the same
quantity on different lineages, so there is nothing for it to contradict. It ran
green over `README.md:731` every lap since the value landed, and the WFG-018
reconciliation sheet went further and told the student to say at the booth that
34 "appears in no artifact" -- which a judge could have falsified with one grep.

So the gate is a *lineage* gate, not a value gate: every prose mention of the
synthetic bracket must be legible as the synthetic lineage, either from a
document-level do-not-cite banner or from a label beside the number itself.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

CANONICAL = REPO / "data" / "processed" / "rescue_verify.json"
SYNTHETIC = (REPO / "data" / "processed" / "rescue_baseline_synthetic"
             / "rescue_verify.json")

#: The two brackets, as the committed artifacts record them.
CANONICAL_ROW = [6, 11, 24, 51, 66]
SYNTHETIC_ROW = [6, 15, 20, 25, 34]

#: Both files are git-TRACKED, so an absent one is a defect, never a skip
#: (MEMO 2026-09-03: a `pytest.skip` on a tracked artifact hides a failure
#: inside a green summary line).


def _matches(pattern: str, text: str) -> bool:
    return re.search(pattern, text, re.IGNORECASE) is not None


def test_both_lineages_hold_the_brackets_the_prose_attributes_to_them() -> None:
    """Pin both artifacts, so a future edit cannot silently swap the story."""
    assert CANONICAL.exists(), (
        "tracked artifact missing: " + str(CANONICAL)
        + " -- regenerate with scripts/verify_rescue_routing.py")
    assert SYNTHETIC.exists(), (
        "tracked artifact missing: " + str(SYNTHETIC)
        + " -- it is the preserved pre-flip baseline; restore it from git")

    canonical = json.loads(CANONICAL.read_text())
    synthetic = json.loads(SYNTHETIC.read_text())

    assert canonical["unreachable_delay_row_cutoff_0p7"] == CANONICAL_ROW
    assert canonical["n_origins"] == 439

    trend = synthetic["robustness_verdict"]["dispatch_delay_trend"]
    assert trend["unreachable_at_baseline_cutoff_delay_0_to_60"] == SYNTHETIC_ROW
    assert synthetic["n_origins"] == 452

    # The confusable pair: same quantity, same script, different lineage.
    assert CANONICAL_ROW[-1] != SYNTHETIC_ROW[-1]


def test_the_registry_carries_the_canonical_row_and_says_it_is_439_series() -> None:
    entry = json.loads((REPO / "docs" / "NUMBERS.json").read_text())["numbers"][
        "rescue_unreachable_delay_row_cutoff_0p7"]
    assert entry["value"] == CANONICAL_ROW
    assert entry["source_file"] == "data/processed/rescue_verify.json"
    # The caveat is what stops the row being placed beside the 458-series.
    assert "439" in entry["caveat"]


def test_readme_quotes_the_canonical_bracket_in_its_canonical_paragraph() -> None:
    """README's rescue paragraph is 439-series, so its bracket must be too."""
    text = (REPO / "README.md").read_text()
    para = [ln for ln in text.splitlines()
            if "rise monotonically with dispatch delay" in ln]
    assert para, "README lost the dispatch-delay sentence entirely"
    window = text[text.index(para[0]):][:1200]

    assert "6 → 66" in window or "6 -> 66" in window, (
        "README's dispatch-delay sentence must carry the 439-series bracket "
        "6 -> 66; the paragraph's other figures (143 origins, 6.12 -> 1.71) "
        "are 439-series, and quoting the 452-series 6 -> 34 there is the "
        "lineage mix WFG-004 corrected.")


#: A mention of the synthetic bracket is legible if any of these sits beside it:
#: an explicit lineage word, the artifact path, or the canonical bracket shown
#: next to it (side-by-side old-vs-new IS the label -- that is how
#: docs/REPORT_ROUND2_P1.md reports the pair).
LINEAGE_LABEL = (r"(452|synthetic|pre-?flip|superseded|retired|legacy|"
                 r"baseline_synthetic|이전|폐기|정본|6\s*→\s*\*?\*?66|"
                 r"6\s*->\s*66)")

#: A document whose first lines carry one of these is marked as a whole.
BANNER = r"(DO NOT CITE|제출·인용 금지|SUPERSEDED|인용 금지)"
BANNER_LINES = 20

#: Matches "6 → 34" / "6->34" / "6 → **34**" and the spaced variants.
SYNTHETIC_MENTION = re.compile(r"6\s*(?:→|->)\s*\*{0,2}34\b")


def _tracked_markdown() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "*.md"], cwd=REPO,
        capture_output=True, text=True, check=True).stdout.split()
    return [REPO / f for f in out if (REPO / f).is_file()]


def test_every_prose_mention_of_the_synthetic_bracket_names_its_lineage() -> None:
    """The gate check_number_collisions.py structurally cannot provide."""
    unlabelled: list[str] = []

    for path in _tracked_markdown():
        lines = path.read_text().splitlines()
        if _matches(BANNER, "\n".join(lines[:BANNER_LINES])):
            continue  # the whole document is marked do-not-cite
        for i, line in enumerate(lines):
            if not SYNTHETIC_MENTION.search(line):
                continue
            # the line itself, plus two either side
            near = "\n".join(lines[max(0, i - 2):i + 3])
            if not _matches(LINEAGE_LABEL, near):
                rel = path.relative_to(REPO)
                unlabelled.append(str(rel) + ":" + str(i + 1) + "  " + line.strip())

    assert not unlabelled, (
        "the synthetic-baseline bracket 6 -> 34 appears without its lineage:\n"
        + "\n".join("  " + u for u in unlabelled)
        + "\n\nBoth brackets are real: 6 -> 66 is the 439-series real-OSM run "
          "(data/processed/rescue_verify.json) and 6 -> 34 is the pre-flip "
          "452-series baseline (data/processed/rescue_baseline_synthetic/). "
          "Name the lineage on the line, or show the canonical bracket beside "
          "it. Do not delete either value -- see docs/ssot_audit_2026-09-03.md.")


def test_the_reconciliation_sheet_no_longer_claims_34_is_absent() -> None:
    """The sheet shipped a falsifiable claim about the repository's own files.

    It told the student to say the value "appears in no artifact" and is a
    typo. It is in a tracked artifact, and `docs/rescue_routing.md` plus
    `docs/REPORT_ROUND2_P1.md` both quote it correctly.
    """
    sheet = (REPO / "docs" / "submission_reconciliation.md").read_text()
    assert "어느 산출물에도 없습니다" not in sheet, (
        "the sheet again claims 34 appears in no artifact; it is in "
        "data/processed/rescue_baseline_synthetic/rescue_verify.json")
    assert "오타" not in sheet or "오타가 아니라" in sheet or "오타는 아닙니다" in sheet, (
        "the sheet again calls the 452-series bracket a typo")


@pytest.mark.parametrize("path,needle", [
    ("docs/HANDOFF_ROUND3.md", "seven times"),
])
def test_the_retired_share_ratio_is_gone_from_the_handoff(path: str,
                                                          needle: str) -> None:
    """24.73 / 9.17 = 2.7x. The 6.7x reading used the RETIRED 3.70 % share.

    Both HANDOFF sentences sat two lines below the canonical shares they
    contradicted.
    """
    text = (REPO / path).read_text()
    for i, line in enumerate(text.splitlines(), start=1):
        if needle in line and "until 2026-09-03" not in line:
            # a mention is allowed only as the annotated history of the fix
            near = "\n".join(text.splitlines()[max(0, i - 3):i + 3])
            assert _matches(r"(retired|2\.7|철회|이전)", near), (
                path + ":" + str(i) + " still asserts the 6.7x ratio, which "
                "is 24.73 / 3.70 on the retired share; the canonical shares "
                "are 24.73 / 9.17 = 2.7x")
