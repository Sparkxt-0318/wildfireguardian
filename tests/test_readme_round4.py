"""Guards for the README's Round-4 section and its English abstract draft (WFG-010).

These are readiness line **R8**'s two conditions, and until this file existed nothing
read them: R8 was graded by a human running ``grep -nE '^## Round' README.md`` in a
critic report, four windows running. A checklist line whose only detector is a person
remembering to grep is a line that goes stale silently, which is the failure class
``docs/auto/DIRECTION.md`` names for hand-typed facts about this repository itself.

Three rules are bound here, and each of the three has actually been broken by this
project at least once:

1. **CHARTER §3.12** — the Round-2 section is a record; Round-4 material goes BELOW
   Round 3. A section inserted in the wrong place would read as an edit to the
   submitted entry, which the KCF 운영요강 treats as a different 작품.
2. **CHARTER §9** — a draft written in the agent's voice for the student to rewrite
   is labelled a draft *where it is read*, not in a file the reader never opens.
   ``paper/AUTHORSHIP.md`` carries the rule; the label has to be on the page.
3. **``docs/auto/DIRECTION.md``'s standing rule** — every judge-facing surface that
   states the 42 carries BOTH binding caveats: the opponent is fire-blind, and the
   forecast-aware arm plans on the field it is scored against, so 42 is an upper
   bound. This is the rule the loop breaks most often, because the second caveat is
   the one that is easy to forget when the first one has already been written.

⚠ **The mutation this file CANNOT catch, stated rather than left for the next
reader** (``docs/auto/DIRECTION.md``, critic #41's rule about mutation scores):
rule 3 is enforced on the **English** abstract only. A lap that writes a fresh
「42곳은 예보를 본 경로에서만 안전했습니다」 sentence into the Korean half, with
neither caveat, passes every assertion below. Binding the Korean spelling needs the
bilingual lint that does not exist yet (WFG-168), and the four sites where 42 appears
today are listed in ``test_the_places_the_readme_states_42_are_the_known_ones`` so
that a fifth one fails here instead of being found by a judge.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
README = REPO / "README.md"


@pytest.fixture(scope="module")
def readme() -> str:
    return README.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def lines(readme: str) -> list[str]:
    return readme.splitlines()


def _heading_line(lines: list[str], pattern: str) -> int:
    """1-indexed line of the single heading matching ``pattern``, or fail saying so."""
    rx = re.compile(pattern)
    hits = [i + 1 for i, ln in enumerate(lines) if rx.match(ln)]
    assert len(hits) == 1, (
        f"expected exactly one README heading matching {pattern!r}, found {hits}. "
        "R8 is graded on this heading existing exactly once."
    )
    return hits[0]


def _section(lines: list[str], start_pattern: str) -> str:
    """The text of a section, from its heading to the next heading of the same level."""
    start = _heading_line(lines, start_pattern)
    level = len(lines[start - 1]) - len(lines[start - 1].lstrip("#"))
    end = len(lines)
    for i in range(start, len(lines)):
        stripped = lines[i]
        if stripped.startswith("#"):
            this = len(stripped) - len(stripped.lstrip("#"))
            if this <= level:
                end = i
                break
    return "\n".join(lines[start - 1 : end])


# ---------------------------------------------------------------------------
# R8 condition (a): the Round-4 section exists, and it is BELOW Round 3.
# ---------------------------------------------------------------------------


def test_the_readme_has_a_round_4_section(lines: list[str]) -> None:
    """R8's first condition. The grep the critic ran by hand, run by the suite."""
    _heading_line(lines, r"^## Round 4\b")


def test_round_4_sits_below_round_3_and_round_2_is_untouched(lines: list[str]) -> None:
    """CHARTER §3.12: Round 2 is a record, and Round-4 material goes below Round 3.

    Ordering is the mechanical half of "do not edit the submitted section". A lap
    that inserted Round 4 above Round 3 would also be rewriting the reading order a
    judge follows, and the 운영요강 rule is about what the finals entry reads as.
    """
    r2 = _heading_line(lines, r"^## Round 2\b")
    r3 = _heading_line(lines, r"^## Round 3\b")
    r4 = _heading_line(lines, r"^## Round 4\b")
    assert r2 < r3 < r4, (
        f"README round sections are out of order: Round 2 at :{r2}, Round 3 at :{r3}, "
        f"Round 4 at :{r4}. CHARTER §3.12 puts Round-4 material below Round 3."
    )


def test_round_4_points_at_files_that_exist(lines: list[str]) -> None:
    """Every repository path the Round-4 section links to resolves.

    The section's whole claim is "a judge can open these"; a dead link is that claim
    being false. Written after this lap's own first draft linked
    ``docs/rescue_dispatch.md``, which has never existed -- the correct page is
    ``docs/dispatch_ordering.md``.
    """
    section = _section(lines, r"^## Round 4\b")
    targets = re.findall(r"\]\((?!https?:)([^)#]+)\)", section)
    assert targets, "the Round-4 section links to no file at all"
    missing = sorted({t for t in targets if not (REPO / t).exists()})
    assert not missing, (
        f"the Round-4 section links to paths that do not exist: {missing}. "
        "The section tells a judge these are openable."
    )


# ---------------------------------------------------------------------------
# R8 condition (b): the English abstract draft, labelled as a draft.
# ---------------------------------------------------------------------------


def test_the_readme_has_an_english_abstract_draft(lines: list[str]) -> None:
    """R8's second condition."""
    _heading_line(lines, r"^### Abstract \(draft\)")


def test_the_abstract_is_labelled_a_draft_where_it_is_read(lines: list[str]) -> None:
    """CHARTER §9: the label goes on the page, not only in ``paper/AUTHORSHIP.md``.

    The heading alone is not enough. A reader who has been told "(draft)" and nothing
    else does not know *whose* draft it is or what happens next; §9's requirement is
    that the student's own voice is identified as the thing still owed.
    """
    section = _section(lines, r"^### Abstract \(draft\)")
    head = "\n".join(section.splitlines()[:8])
    assert "DRAFT" in head or "draft" in head.lower(), (
        "the abstract section does not say it is a draft in its own opening lines"
    )
    assert "AUTHORSHIP.md" in head, (
        "the abstract draft does not point at paper/AUTHORSHIP.md, which is the rule "
        "saying the student rewrites it in their own voice (CHARTER §9)."
    )


# ---------------------------------------------------------------------------
# DIRECTION's standing rule: the 42 never travels without both caveats.
# ---------------------------------------------------------------------------

#: The two caveats, as the CLAUSE that does the binding and not as a bare token.
#:
#: ⚠ This distinction is the whole value of the assertion, and it was found by
#: grading rather than by design. The first version of this test asserted that the
#: substring ``fire-blind`` appeared somewhere in the abstract section. Deleting the
#: caveat from the 42's own sentence left the test GREEN, because the section names
#: ``fire-blind`` a second time four lines later, in the *present-perimeter*
#: sentence -- a different claim. That is critic #41's finding (WFG-185, WFG-186)
#: reproducing in a test written after it: a scope assertion satisfied by a string
#: standing in some other claim's neighbourhood. Matching the binding clause, inside
#: the paragraph that states the number, is what closes it.
_FIRE_BLIND = re.compile(r"against a \*{0,2}fire-blind\*{0,2} baseline", re.I)
_UPPER_BOUND = re.compile(r"42 is\s+an\s+\*{0,2}upper[- ]bound\*{0,2}", re.I)


def _paragraph_stating_42(lines: list[str]) -> str:
    """The abstract paragraph that states 42, whitespace-normalised.

    Paragraph scope, not section scope: a caveat two paragraphs away is not attached
    to the number, and a judge reading the sentence would never meet it.
    """
    section = _section(lines, r"^### Abstract \(draft\)")
    paras = [" ".join(p.split()) for p in re.split(r"\n\s*\n", section)]
    hits = [p for p in paras if "42 of 458" in p]
    assert len(hits) == 1, (
        f"expected exactly one abstract paragraph stating '42 of 458', found "
        f"{len(hits)}. If the abstract no longer states it, the headline result has "
        "left the abstract; if it states it twice, one of the two is uncaveated."
    )
    return hits[0]


def test_the_abstract_draft_states_42_with_both_binding_caveats(lines: list[str]) -> None:
    """``docs/auto/DIRECTION.md``: a new sentence about 42 carries both caveats.

    Both, not either, and both in the paragraph that states the number. The
    fire-blind caveat says the opponent could not see the fire; the upper-bound
    caveat says the forecast-aware arm was scored on the field it planned on. A
    surface carrying only the first still tells a judge that 42 is what this
    project's model buys, which is the claim the repository does not have.
    """
    para = _paragraph_stating_42(lines)
    assert _FIRE_BLIND.search(para), (
        "the paragraph stating 42 does not say the contrast is measured against a "
        "fire-blind baseline. ⚠ Naming 'fire-blind' elsewhere in the abstract does "
        "not count: the caveat has to bind THIS number, in this paragraph."
    )
    assert _UPPER_BOUND.search(para), (
        "the paragraph stating 42 does not say that 42 is an upper bound -- that the "
        "forecast-aware arm plans on the same hazard field it is scored against, so "
        "42 is what a noiseless forecast would buy, not what this project's model "
        "buys. DIRECTION requires BOTH caveats on every surface stating 42."
    )


def test_the_places_the_readme_states_42_are_the_known_ones(readme: str) -> None:
    """A fifth site for the 42 fails here rather than being found by a judge.

    This is the guard the file's own docstring names as its weak point: the caveat
    assertions above read the English abstract only, so what protects the rest of the
    README is knowing exactly where the number appears. Today that is four places:
    the TL;DR (English, both caveats present), the Round-3 re-derivation table (a
    record of the correction), the Round-4 cross-reference (which states in its own
    sentence that the fair opponent has NOT been run on this figure's region), and
    the abstract draft.

    A new occurrence is not necessarily wrong -- it is unreviewed. Add it here once
    it carries what DIRECTION requires.
    """
    sites = [i + 1 for i, ln in enumerate(readme.splitlines())
             if re.search(r"42 of 458|\*\*42곳\*\*", ln)]
    assert len(sites) == 4, (
        f"the README states 42 at lines {sites}; this guard knows four sites. A new "
        "one must carry the fire-blind and upper-bound caveats (or, in Korean, say "
        "which region it does not cover) before it is added here. WFG-168 is the "
        "bilingual lint that would make this count unnecessary."
    )
