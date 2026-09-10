"""WFG-220 — the screen five judges stand in front of has to say what grades its own verdicts.

`web/finals.html` ACT 3 tells the judge, in as many words, that every origin is
classified by comparing its fire-blind direct route with its time-aware route and
that 「이 판정이 화면의 점 하나하나입니다」. `docs/oracle_gap.md` §2 establishes that
those verdicts are graded on ``haz_stack`` — the very array the time-aware arm
planned on — while ``obs_stack``, the observed FIRMS footprint, sits in the same
npz on the same grid and scores nothing. The screen never said anything false
about this; it said nothing at all, which on the surface with the longest exposure
(five judges, about ten minutes each, offline) is the more expensive of the two.

Why the placement assertion is here, and it is the load-bearing one
-------------------------------------------------------------------
The obvious fix is to append a card to the 신뢰성과 한계 grid. That grid already
held **ten** cards and spent them on walking-network coverage, the ERA5
publication lag, OSM 정자 tagging and the dispatch-ordering negative result --
every one of them a smaller caveat than this one. An eleventh card at the end
would have made the row cosmetically `done` while leaving the defect it names --
the biggest omission gets the least prominence -- exactly where it was. So the
card is **first** in the grid, and this file asserts that rather than asserting
mere presence, because presence is what a later edit would keep while quietly
reordering it away.

⚠ POLARITY, AND THE FIRST VERSION OF THIS FILE DID NOT HAVE IT
--------------------------------------------------------------
The lap's own independent reviewer blocked this file by keeping every token it
asked for -- ``haz_stack``, ``obs_stack``, 채점, leave-one-fire-out, the
``docs/oracle_gap.md §2`` citation -- and replacing the body with 「채점은
obs_stack 으로 합니다」, the **inverse** of what §2 establishes. Six assertions
passed in under a second while the screen told five judges the opposite of the
repository's own finding. That is `tests/test_output_object_claim_bounds.py`'s
polarity lesson, one lap old, repeated by the lap that had just read it: **token
presence is not polarity.**

So the card is now held against a direction, in both senses:

* the **positive** -- the array the arm planned on is the array it is graded on,
  and ``obs_stack`` grades nothing -- must be asserted in the card's own words;
* the **inverse** -- anything that makes ``obs_stack`` the grading field -- is
  refused outright, because a later editor 「tidying」 the sentence is exactly how
  this defect travels.

And the anchor is not this file's own opinion: `test_the_card_agrees_with_the_document_it_cites`
reads the claim out of `docs/oracle_gap.md` §2, which a different lap wrote for a
different purpose, so if that document ever changes its position the card is
forced to be revisited rather than quietly left behind.

The three constraints inherited from WFG-214 are asserted too, since a card that
buys prominence by settling an open question is worse than no card:

* it may not settle 「상한」 / "upper bound" -- where the word appears, **NH-053**
  must appear in the same card, naming it as an open question;
* no present-perimeter margin value (9, 27, 5, 19, 86) reaches the screen while
  NH-032, NH-034 and NH-052 are open;
* it removes no caveat -- the ten cards that were there are still there.

What this does NOT show. It does not show that a judge reads the card, that the
Korean is clear, or that the re-grading in `docs/oracle_gap.md` §6 has been run --
it has not, and the card says so. It reads the template's source and the built
screen's text; it does not render either.

No clock, no timezone, no network, no file outside the repository (CHARTER §4b).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "scripts" / "finals.template.html"
SCREEN = REPO / "web" / "finals.html"

#: The five present-perimeter margin values that may not reach a judge-facing
#: surface while NH-032, NH-034 and NH-052 are open (DIRECTION.md, WFG-214).
FORBIDDEN_MARGINS = ("9", "27", "5", "19", "86")

#: How many `rel()` cards the 신뢰성 grid held before this row. The floor is here so
#: that "make the new card prominent" can never be satisfied by deleting others.
CARDS_BEFORE = 10

#: THE CLAIM, positively: the arm is graded on the array it planned on. `docs/oracle_gap.md`
#: §2: 「the grader uses `haz_stack` as if it were truth ... it cannot be wrong」.
_GRADED_ON_THE_PLANNED_ARRAY = re.compile(
    r"채점(?:도|은|을|이|하는)?[^.。]{0,40}같은\s*배열"
    r"|채점하는\s*배열이[^.。]{0,30}계획한"
)

#: And the other half: the observation committed beside it scores nothing.
#: `docs/oracle_gap.md` §2: 「Nothing scores against it.」
_OBS_GRADES_NOTHING = re.compile(
    r"obs_stack[^.。]{0,80}?채점하지\s*않"
    r"|obs_stack[^.。]{0,80}?아무것도\s*채점"
)

#: ⚠ THE POLARITY ANCHOR. The reviewer's exploit, turned into a property: a sentence that
#: makes ``obs_stack`` the grading field is refused outright rather than merely unrewarded.
#: The 으로/로 must follow ``obs_stack`` immediately, so 「obs_stack 이 같은 격자로 ...
#: 아무것도 채점하지 않습니다」 -- the true sentence -- does not trip it.
_DENIES = re.compile(
    r"obs_stack\s*(?:으로|로|에|를|을)\s*(?:채점|평가|비교)"
    r"|채점(?:은|도|을)?\s*obs_stack"
    r"|graded\s+(?:against|on)\s+(?:the\s+)?obs_stack"
)


def _rel_cards(text: str) -> list[str]:
    """Every `rel(...)` call in the template, in source order.

    Split on the call itself rather than parsed as JS: the arguments are Korean
    string literals with no nested `rel(`, so the segment from one call to the
    next is that card and only that card.
    """
    parts = re.split(r"\n\s*rel\(", text)
    return parts[1:]


@pytest.fixture(scope="module")
def cards() -> list[str]:
    return _rel_cards(TEMPLATE.read_text(encoding="utf-8"))


def test_the_grid_still_holds_every_caveat_it_held_before(cards: list[str]) -> None:
    """This row ADDS a limitation; it may not buy room by dropping one."""
    assert len(cards) >= CARDS_BEFORE + 1, (
        f"the 신뢰성 grid holds {len(cards)} rel() cards; it held {CARDS_BEFORE} "
        "before WFG-220 added one, so a caveat has been removed")


def test_the_oracle_card_is_first_in_the_grid(cards: list[str]) -> None:
    """Presence is not the property; prominence is (see this file's docstring)."""
    assert cards, "the 신뢰성 grid has no rel() cards at all"
    first = cards[0]
    assert "docs/oracle_gap.md" in first, (
        "the first card of the 신뢰성과 한계 grid does not cite docs/oracle_gap.md. "
        "The grid's biggest caveat is the one that says what grades the dots on "
        "the map, and WFG-220 was filed because it was last -- absent, in fact")


def test_the_card_states_the_mechanism_in_the_document_s_own_terms(
    cards: list[str],
) -> None:
    """`haz_stack` planned on, `haz_stack` graded on, `obs_stack` grading nothing."""
    first = cards[0]
    for token in ("haz_stack", "obs_stack", "채점"):
        assert token in first, (
            f"the oracle card does not name {token!r}; docs/oracle_gap.md §2 names "
            "all three and the card is supposed to state that section's mechanism, "
            "not gesture at it")
    assert "leave-one-fire-out" in first or "LOFO" in first, (
        "the card does not say that the planning field is a leave-one-fire-out "
        "model output, which is the half that keeps it from reading as 'the router "
        "cheats by using truth'")


def test_the_card_asserts_the_direction_and_not_merely_the_tokens(
    cards: list[str],
) -> None:
    """The block that broke this file's first version (see the module docstring)."""
    first = cards[0]
    assert _GRADED_ON_THE_PLANNED_ARRAY.search(first), (
        "the oracle card names haz_stack but never says the arm is GRADED on the "
        "array it PLANNED on. That sentence is the whole finding; without it the "
        "card is a glossary entry and a judge learns nothing from it")
    assert _OBS_GRADES_NOTHING.search(first), (
        "the oracle card names obs_stack but never says it scores nothing. "
        "docs/oracle_gap.md §2: 「Nothing scores against it.」")
    assert not _DENIES.search(first), (
        "the oracle card makes obs_stack the grading field, which is the INVERSE "
        "of docs/oracle_gap.md §2 and the mutation this file's first version "
        "passed. If the repository's finding has genuinely changed, change "
        "docs/oracle_gap.md and this pattern in the same commit")


def test_the_card_agrees_with_the_document_it_cites() -> None:
    """The anchor is another lap's document, not this file's own opinion.

    `mandela` #5 (verifier = designer): every assertion above was written from the
    card it checks, so none of them can tell whether the card is *right*. This one
    reads the claim out of `docs/oracle_gap.md` §2 -- written by a different lap for
    a different purpose -- and fails if the document and the screen drift apart.
    """
    doc = (REPO / "docs" / "oracle_gap.md").read_text(encoding="utf-8")
    section = doc[doc.index("## 2."):doc.index("## 3.")]
    assert "Nothing scores against it" in section, (
        "docs/oracle_gap.md §2 no longer says obs_stack scores nothing; the finals "
        "card was written from that sentence and must be revisited with it")
    assert re.search(r"grader uses `?haz_stack`? as if it were", section), (
        "docs/oracle_gap.md §2 no longer says the grader uses haz_stack as if it "
        "were truth; the finals card asserts exactly that and must be revisited")
    first = _rel_cards(TEMPLATE.read_text(encoding="utf-8"))[0]
    assert _OBS_GRADES_NOTHING.search(first) and not _DENIES.search(first), (
        "the finals card and docs/oracle_gap.md §2 disagree about which array "
        "grades the routing verdicts")


def test_the_card_leaves_the_upper_bound_question_open(cards: list[str]) -> None:
    """NH-053 is open; a screen card is not where a judged headline gets settled."""
    first = cards[0]
    if "상한" in first or "upper bound" in first.lower():
        assert "NH-053" in first, (
            "the oracle card uses 상한/upper bound without naming NH-053, so it "
            "settles a claim about a judged headline number that nothing in this "
            "repository derives (DIRECTION.md: 'do not settle the word 상한')")


def test_no_margin_value_reaches_the_card(cards: list[str]) -> None:
    """NH-032, NH-034 and NH-052 are open; no margin number goes on the screen."""
    first = cards[0]
    prose = re.sub(r"docs/[\w./§ ]+", " ", first)          # §2 · §6 · §7 are not margins
    prose = prose.replace("NH-053", " ").replace("§", " ")
    found = [v for v in FORBIDDEN_MARGINS
             if re.search(rf"(?<!\d){v}(?!\d)", prose)]
    assert not found, (
        f"the oracle card carries the margin value(s) {found}; NH-032, NH-034 and "
        "NH-052 are open and no margin value may reach a judge-facing surface")


def test_the_built_screen_carries_the_card_with_the_same_direction() -> None:
    """The template is the source; `web/finals.html` is what five judges open.

    Every assertion above runs again here, on the built file, because the reviewer's
    mutation edited template and output **identically** — which keeps
    `test_finals_template_sync.py` green, since that file asserts the two agree and
    not what they say.
    """
    built = _rel_cards(SCREEN.read_text(encoding="utf-8"))
    assert built, "web/finals.html has no rel() cards; the build is broken"
    first = built[0]
    assert "docs/oracle_gap.md" in first, (
        "the first card of the built screen's 신뢰성 grid does not cite "
        "docs/oracle_gap.md. Run `make finals PYTHON=.auto/venv/bin/python`")
    assert _GRADED_ON_THE_PLANNED_ARRAY.search(first), (
        "the built screen's oracle card does not say the arm is graded on the "
        "array it planned on")
    assert _OBS_GRADES_NOTHING.search(first), (
        "the built screen's oracle card does not say obs_stack scores nothing")
    assert not _DENIES.search(first), (
        "the built screen tells a judge that obs_stack is the grading field, "
        "which is the inverse of docs/oracle_gap.md §2")
