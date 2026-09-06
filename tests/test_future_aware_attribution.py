"""The headline routing contrast never states its size without naming its control.

Backlog row WFG-138, filed by critic #28 and widened by critic #29.

Why this exists
---------------
The number this project leads with is *42 of 458 scanned origins reach a refuge
only under the forecast-aware policy*. The baseline that 42 is measured against
is ``naive``, and ``naive`` is fire-blind in this repository's own words ---
``src/wildfireguardian/routing/evacuation.py:270`` ("Fire-blind shortest path to
the nearest shelter") and ``docs/real_roads_real_hazard.md:50``. So the contrast
establishes that coupling *a hazard field* into the router changes decisions; it
does not separate knowing where the fire **will be** from knowing where it
**is**. The fair opponent that would separate them, a plan refusing only what is
burning now, has been run on 의성·안동 only (``docs/present_perimeter_arm.md``),
never on 영덕, which is where the 42 comes from.

The loop wrote that caveat into ``paper/manuscript.md`` (Abstract and §7), into
the booth script's 3막 (WFG-103) and into the finals template (WFG-109), and for
three windows it did not reach ``README.md`` --- the first file a KCF judge, an
ISEF reviewer or an IEEE reader opens, and the file ``CITATION.cff`` points at.
Every gate in the repository was green over that whole time, because no gate
read for it: the claim was **narrowed**, never withdrawn, so
``docs/auto/withdrawn_claims.json`` and ``check_withdrawn_claims.py`` --- which
do read all 925 gated files --- cannot see it by construction (CHARTER §3.5c).

This module is the gate for that class on the English surfaces. Its Korean twin
is ``tests/test_judge_qa_bank.py::test_no_draft_answer_states_the_future_aware_only_claim_bare``,
which reads the draft answers the student speaks aloud.

What it does NOT do
-------------------
It keys on the strings a correct sentence contains. It catches a caveat that is
deleted, moved out of the claim's own paragraph, or a new surface that never had
one --- which is the whole observed failure mode here, three times. It does not
detect a *reworded* overclaim that keeps the phrase, the same limit
``docs/withdrawn_claims.md`` §4 records for the withdrawn-claim registry. It also
says nothing about whether the 42 itself is right; ``make verify`` does that.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

#: The English surfaces that state the contrast as a claim. Both are read by
#: strangers rather than by the loop, which is the reason they are the two.
SURFACES = ("README.md", "paper/manuscript.md")

#: The claim, as every English surface in this repository has ever written it.
CLAIM = "42 of 458"

#: What an attributing sentence adds to the bare count. A block holding the
#: count without any of these is a table row or a reconciliation entry, not a
#: claim about what the forecast buys, and is left alone.
ATTRIBUTION = ("only when the router", "only under the forecast-aware")

#: The control, spelled as the code and the manuscript spell it.
CONTROL = "fire-blind"


def _flat(block: str) -> str:
    """A block with Markdown emphasis and line breaks taken out.

    Written after the first version of this gate passed on the very README
    bullet it was built to catch: the surface writes 「reach a refuge **only**
    when the router ...」 and 「42 of 458」 in bold, so a literal substring scan
    saw neither the attribution nor, across a line break, the count. A gate
    that is green by construction proves nothing (the 1ec1d06 lesson,
    paper/GAPS.md G8 point 2) --- this one is graded by putting the pre-lap
    bullet back, and it goes red.
    """
    return re.sub(r"\s+", " ", block.replace("*", "").replace("`", ""))


def _blocks(path: Path) -> list[str]:
    """Paragraph-ish blocks: runs of lines with no blank line between them.

    A Markdown bullet and a manuscript paragraph are each one block, so the
    caveat has to sit in the same breath as the claim rather than in a note
    under it. That distinction is the entire finding: on Q19 the correction sat
    in a warning block directly beneath the sentence and never reached it.
    """
    return [_flat(b) for b in path.read_text(encoding="utf-8").split("\n\n")]


@pytest.mark.parametrize("surface", SURFACES)
def test_the_headline_contrast_names_its_fire_blind_control(surface: str) -> None:
    path = REPO / surface
    assert path.exists(), surface + " is gone; WFG-138 assumed it exists"
    bare = [
        b for b in _blocks(path)
        if CLAIM in b
        and any(a in b for a in ATTRIBUTION)
        and CONTROL not in b
    ]
    assert not bare, (
        surface + " states 「" + CLAIM + " ... only ...」 in a block that never "
        "says the baseline is " + CONTROL + ". The comparison is against "
        "naive, which consults no fire at all "
        "(src/wildfireguardian/routing/evacuation.py:270), so the sentence as "
        "written claims the forecast is what buys those origins and the "
        "repository has not measured that: the present-perimeter opponent has "
        "run on 의성·안동 only (docs/present_perimeter_arm.md), never on 영덕. "
        "Put the caveat in the same block as the number --- a note in the "
        "paragraph below it is what failed three times (WFG-138). Offending "
        "block starts: " + bare[0].strip()[:120]
    )


def test_the_control_is_still_called_fire_blind_in_the_code() -> None:
    """The gate above is worth nothing if it keys on a word the code dropped."""
    source = (REPO / "src" / "wildfireguardian" / "routing" / "evacuation.py")
    text = source.read_text(encoding="utf-8").lower()
    assert CONTROL in text, (
        "src/wildfireguardian/routing/evacuation.py no longer contains the word "
        "'" + CONTROL + "'. Either the naive baseline changed meaning --- in "
        "which case every surface quoting the 42 needs rereading, not just this "
        "test --- or the wording moved and this gate has been checking prose "
        "against a phrase the code stopped using."
    )
