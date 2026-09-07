"""The headline routing contrast never states its size without naming its control.

Backlog row WFG-138, filed by critic #28, widened by critic #29, and rebuilt once
inside its own lap after the lap reviewer moved the caveat instead of deleting it.

Why this exists
---------------
The number this project leads with is *42 of 458 scanned origins reach a refuge
only under the forecast-aware policy*. The baseline that 42 is measured against
is ``naive``, and ``naive`` is fire-blind in this repository's own words ---
``src/wildfireguardian/routing/evacuation.py:270`` ("Fire-blind shortest path to
the nearest shelter"), which picks its path before the hazard is consulted at
all. So the contrast establishes that coupling *a hazard field* into the router
changes decisions; it does not separate knowing where the fire **will be** from
knowing where it **is**. The fair opponent that would separate them, a plan
refusing only what is burning now, has been run on 의성·안동 only
(``docs/present_perimeter_arm.md``), never on 영덕, which is where the 42 comes
from.

The loop wrote that caveat into ``paper/manuscript.md`` (Abstract and §7), into
the booth script's 3막 (WFG-103) and into the finals template (WFG-109), and for
three windows it did not reach ``README.md`` --- the first file a KCF judge, an
ISEF reviewer or an IEEE reader opens, and the file ``CITATION.cff`` points at.
Every gate in the repository was green over that whole time, because no gate read
for it: the claim was **narrowed**, never withdrawn, so
``docs/auto/withdrawn_claims.json`` and ``check_withdrawn_claims.py`` --- which do
read all 925 gated files --- cannot see it by construction (CHARTER §3.5c).

Its Korean twin is
``tests/test_judge_qa_bank.py::test_no_draft_answer_states_the_future_aware_only_claim_bare``,
which reads the draft answers the student speaks aloud.

Two things this file learned the hard way, in one lap
-----------------------------------------------------
1. **Emphasis marks are adversarial to a substring scan.** The first spelling of
   this gate passed on the very README bullet it was written for, because the
   surface writes ``**only**`` and ``**42 of 458**``. Blocks are flattened before
   matching.
2. **A caveat that MOVES is the failure this row is about, and a delete-only
   mutation cannot see it.** The second spelling split surfaces on blank lines,
   and README's TL;DR is a single 2,159-character block spanning four bullets ---
   so the gate asked only that the word appear *somewhere in the list*. The lap
   reviewer restored the pre-lap overclaim and planted a caveat four bullets
   below it: 3 passed. A Markdown list item is therefore its own block here, and
   both mutations are graded (``docs/auto/MEMO.md``, 2026-09-06T2117Z).

What it does NOT do, measured rather than asserted
--------------------------------------------------
It keys on spellings. ``test_the_gate_is_scored_on_sentences_it_did_not_write``
runs it over fourteen sentences the lap reviewer wrote without seeing these
patterns and records the score in both directions, because a gate that fires on a
*correct* sentence is worse than no gate --- it pressures the next lap to strike a
true sentence off the student's card (MEMO 2026-09-06T1520Z, the WC-004 lesson).
A reworded overclaim that drops every keyed spelling still escapes; that class is
open and belongs to a row, not to a bigger regex.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

#: Judge-facing surfaces that state the contrast as a claim rather than as a
#: bucket count. Two English (read by strangers) and one Korean (spoken at the
#: booth); the Q&A bank's drafts are gated in tests/test_judge_qa_bank.py.
SURFACES = ("README.md", "paper/manuscript.md", "docs/auto/DEMO_SCRIPT_5MIN.md")

#: The count, as every surface in this repository has ever written it. The
#: Korean form is 「458곳 중 42곳」 / 「458개 원점 중 42개」, which flattening
#: reduces to a 458 ... 42 run inside one block.
CLAIM = (
    re.compile(r"42\s*(?:of\s+(?:the\s+)?|/)\s*458"),
    re.compile(r"458\s*(?:곳|개)[^.]{0,20}42\s*(?:곳|개)"),
)

#: What an attributing sentence adds to the bare count. A block holding the
#: count with none of these is a table row or a reconciliation entry, not a
#: claim about what the forecast buys, and is left alone.
ATTRIBUTION = (
    re.compile(r"only\s+(?:when|under|with|because|if)"),
    re.compile(r"only[^.]{0,40}forecast"),
    re.compile(r"(?:시간\s*인지|미래\s*인지|예보)[^.]{0,40}(?:에서만|라야)"),
    # 「... 경로라야 닿습니다」 / 「... 경로에서만 닿습니다」 --- an only-claim that
    # names no keyed forecast word. Added when a reviewer probe used it; it is
    # the route-shaped attribution rather than a spelling of "forecast".
    re.compile(r"경로(?:라야|에서만)"),
)

#: The control, in every spelling this repository actually uses for it. A
#: caveated sentence must contain one of these; accepting the family rather than
#: one token is what keeps the gate off a correctly-worded rewrite.
CONTROL = (
    re.compile(r"fire-blind", re.I),
    re.compile(r"hazard-unaware", re.I),
    re.compile(r"consults?\s+no\s+fire", re.I),
    re.compile(r"sees?\s+no\s+fire", re.I),
    re.compile(r"불을\s*(?:전혀|아예)\s*보지\s*않"),
    re.compile(r"화재를\s*(?:참조|고려)하지\s*않"),
    re.compile(r"불을\s*보지\s*않"),
)


#: The **second** caveat the manuscript calls binding, in the spellings the
#: repository uses for it. ``paper/manuscript.md`` §4.5: "The forecast-aware arm
#: plans on the same hazard field it is graded against, so whatever it is worth
#: against a present-perimeter policy is what a *noiseless* forecast is worth;
#: this project's own model is worth less, by an amount no run here measures."
#: It binds the 42 for the reason ``docs/present_perimeter_arm.md`` §5 gives for
#: the 의성 margin, and ``docs/auto/JUDGE_QA.md`` Q36 is the spoken answer.
ORACLE = (
    re.compile(r"upper\s+bound", re.I),
    re.compile(r"noiseless", re.I),
    re.compile(r"perfect\s+forecast", re.I),
    re.compile(r"oracle", re.I),
    re.compile(r"상한"),
    re.compile(r"완벽한\s*예보"),
)

#: Surfaces required to carry **both** families in the same block as the number.
#: ``paper/manuscript.md`` is deliberately NOT here and the reason is measured,
#: not assumed --- see ``test_the_manuscript_claim_blocks_do_not_yet_name_it``.
ORACLE_SURFACES = ("README.md",)


def _flat(block: str) -> str:
    """A block with Markdown emphasis, quote marks and line breaks taken out."""
    stripped = re.sub(r"^\s*>\s?", "", block, flags=re.M)
    return re.sub(r"\s+", " ", stripped.replace("*", "").replace("`", ""))


def _blocks(path: Path) -> list[str]:
    """Blank-line paragraphs, then each Markdown list item split out of them.

    The list-item split is the load-bearing half. README's TL;DR is one
    blank-line block holding four bullets, so without it the gate is satisfied by
    a caveat sitting under a different bullet --- which is 「a note beside the
    sentence」, the exact thing WFG-138 is about.
    """
    out: list[str] = []
    for para in path.read_text(encoding="utf-8").split("\n\n"):
        pieces = re.split(r"\n(?=\s*[-*+] )", para)
        out.extend(_flat(p) for p in pieces if p.strip())
    return out


def _claim_blocks(path: Path) -> list[str]:
    return [
        b for b in _blocks(path)
        if any(c.search(b) for c in CLAIM) and any(a.search(b) for a in ATTRIBUTION)
    ]


def _is_caveated(block: str) -> bool:
    """Caveat one only: the control is fire-blind.

    Deliberately NOT widened to require ``ORACLE`` as well. This predicate is
    what ``test_the_gate_never_fires_on_a_correctly_caveated_sentence`` scores in
    the safe direction, over sentences a reviewer wrote that name the control and
    say nothing about a noiseless forecast --- correct sentences, every one. Fold
    the second family in here and the gate starts flagging them, which is the
    direction MEMO 2026-09-06T1520Z calls the worse one. The second caveat is a
    per-surface requirement instead, below.
    """
    return any(c.search(block) for c in CONTROL)


def _names_the_oracle_bound(block: str) -> bool:
    return any(o.search(block) for o in ORACLE)


@pytest.mark.parametrize("surface", SURFACES)
def test_the_headline_contrast_names_its_fire_blind_control(surface: str) -> None:
    path = REPO / surface
    assert path.exists(), surface + " is gone; WFG-138 assumed it exists"
    bare = [b for b in _claim_blocks(path) if not _is_caveated(b)]
    assert not bare, (
        surface + " states the 42-of-458 contrast with an 'only' attribution in a "
        "block that never names the control. The comparison is against naive, "
        "which consults no fire at all "
        "(src/wildfireguardian/routing/evacuation.py:270), so the sentence as "
        "written claims the forecast is what buys those origins, and this "
        "repository has not measured that: the present-perimeter opponent has run "
        "on 의성·안동 only (docs/present_perimeter_arm.md), never on 영덕. Put the "
        "caveat in the same block as the number --- a note in the paragraph below "
        "it, or under the next bullet, is what failed three times (WFG-138). "
        "Offending block starts: " + bare[0].strip()[:140]
    )


@pytest.mark.parametrize("surface", SURFACES)
def test_each_surface_still_states_the_claim_this_gate_guards(surface: str) -> None:
    """A gate over zero blocks is green and worthless; this is what says so."""
    found = _claim_blocks(REPO / surface)
    assert found, (
        surface + " no longer holds any block this gate can see: either the "
        "headline contrast was removed from it (in which case say so in the "
        "report and drop the surface here on purpose) or the wording moved and "
        "the gate above has quietly been checking nothing. The second is how a "
        "green suite hides a regression."
    )


@pytest.mark.parametrize("surface", ORACLE_SURFACES)
def test_the_headline_contrast_names_its_oracle_bound(surface: str) -> None:
    """WFG-148: the manuscript says TWO caveats bind this comparison, not one.

    The first gate this module shipped certified a block as caveated on one
    family and asked nothing else, so the README bullet was green under it while
    half of what ``paper/manuscript.md`` §4.5 calls binding was missing. A gate
    that certifies "this sentence is caveated" is only as wide as its list of
    caveats (critic #30).
    """
    path = REPO / surface
    assert path.exists(), surface + " is gone; WFG-148 assumed it exists"
    bare = [b for b in _claim_blocks(path) if not _names_the_oracle_bound(b)]
    assert not bare, (
        surface + " states the 42-of-458 contrast with an 'only' attribution in a "
        "block that never says the forecast-aware arm plans on the hazard field it "
        "is scored against. That makes the 42 an upper bound --- what a noiseless "
        "forecast would buy --- and not a measurement of this project's model, "
        "which is worth less by an amount no run here measures "
        "(paper/manuscript.md 4.5; docs/present_perimeter_arm.md 5 says the same "
        "of the 의성 margin). Put it in the SAME block as the number: a clause "
        "under the next bullet is what failed three times for the first caveat "
        "(WFG-138), and the same locality is what this one is about. The spoken "
        "answer is docs/auto/JUDGE_QA.md Q36. Offending block starts: "
        + bare[0].strip()[:140]
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "paper/manuscript.md states the caveat in 4.5 and not in the two blocks "
        "that carry the 42; it has 17 words of headroom against the 9,000-word "
        "proxy (NH-037 open), so WFG-150 closes this, not WFG-148"
    ),
)
def test_the_manuscript_claim_blocks_do_not_yet_name_it() -> None:
    """The gap WFG-148 did not close, measured on every run instead of quoted.

    WFG-148's done-when asked for both families on ``README.md`` **and**
    ``paper/manuscript.md``. The README half shipped. The manuscript half did
    not, and the reason is a number rather than a judgement: ``paper/check_paper.py``
    reports ``body_words`` 8,983 against a hard fail at 9,000, so the two clauses
    this would add do not fit, and the budget itself is the open question in
    NH-037. The manuscript is not silent on the caveat --- §4.5 states it in the
    words every other surface quotes --- so what is missing is locality, not the
    claim.

    Marked ``strict``: the day the manuscript gains the clause in those blocks
    this test fails and asks ``paper/manuscript.md`` to be promoted into
    ``ORACLE_SURFACES``, rather than sitting here as a permanent excuse.
    """
    blocks = _claim_blocks(REPO / "paper" / "manuscript.md")
    assert blocks, "the manuscript no longer states the claim this gate is about"
    assert all(_names_the_oracle_bound(b) for b in blocks)


def test_the_control_is_still_called_fire_blind_in_the_code() -> None:
    """The gate is worth nothing if it keys on a word the code dropped."""
    source = REPO / "src" / "wildfireguardian" / "routing" / "evacuation.py"
    text = source.read_text(encoding="utf-8").lower()
    assert "fire-blind" in text, (
        "src/wildfireguardian/routing/evacuation.py no longer contains the word "
        "'fire-blind'. Either the naive baseline changed meaning --- in which "
        "case every surface quoting the 42 needs rereading, not just this test "
        "--- or the wording moved and this gate has been checking prose against "
        "a phrase the code stopped using."
    )


# --- independence -----------------------------------------------------------
#
# Written by the lap reviewer of 2026-09-06T2117Z, which had not seen these
# patterns, against the first version of this file. It scored 3 of 7 and 2 of 7
# then. The point of keeping the set is that the score is re-derived on every
# run instead of quoted from a report (MEMO 2026-09-06T1520Z).

#: Overclaims that attribute the 42 to the forecast in so many words. A gate
#: that misses one of these is not yet doing its job.
REVIEWER_SET_BARE = (
    "On Yeongdeok, 42 of 458 scanned origins are saved only by the forecast-aware router.",
    "On Yeongdeok, 42/458 origins survive only with forecast-aware routing.",
    "영덕에서 458곳 중 42곳이 예보를 본 경로에서만 대피 지점에 닿습니다.",
    "영덕에서 458개 원점 중 42개는 미래 인지 경로에서만 안전합니다.",
    "영덕에서는 458곳 중 42곳이 불이 어디로 갈지 아는 경로라야 닿습니다.",
)

#: The open class, kept verbatim rather than reshaped into something catchable.
#: This says the same false thing with no 'only' and no keyed attribution at all,
#: and no spelling list reaches it --- only a claim parser would. Marked strict,
#: so the day someone closes the class this test fails and asks to be promoted
#: into the set above rather than sitting here as a permanent excuse.
REVIEWER_SET_REWORDED = (
    "Our forecast reaches 42 of the 458 scanned origins that the status quo cannot.",
)

#: Correct sentences. A gate that fires on one of these is the dangerous
#: direction: it makes the next lap delete something true.
REVIEWER_SET_CAVEATED = (
    "On Yeongdeok, 42 of 458 scanned origins reach a refuge only under the "
    "forecast-aware policy, measured against a hazard-unaware shortest path that "
    "consults no fire at all.",
    "42 of 458 origins reach a refuge only when the router accounts for where the "
    "fire will be, against a fire-blind baseline.",
    "영덕에서 458곳 중 42곳이 시간 인지 경로에서만 닿습니다. 비교 대상은 불을 아예 "
    "보지 않는 경로입니다.",
    "영덕에서 458개 원점 중 42개가 미래 인지 경로에서만 닿고, 그 대조군은 화재를 "
    "참조하지 않는 최단 경로입니다.",
)


@pytest.mark.parametrize("sentence", REVIEWER_SET_CAVEATED)
def test_the_gate_never_fires_on_a_correctly_caveated_sentence(sentence: str) -> None:
    """The direction that matters most: never push a lap to delete a true sentence."""
    block = _flat(sentence)
    fires = any(c.search(block) for c in CLAIM) and any(
        a.search(block) for a in ATTRIBUTION
    ) and not _is_caveated(block)
    assert not fires, (
        "the attribution gate flags a sentence that already names its control:\n  "
        + sentence + "\nA gate that fires on the correction is worse than no gate: "
        "it pressures the next lap to strike a true sentence off a judge-facing "
        "surface (MEMO 2026-09-06T1520Z). Widen CONTROL to the spelling this "
        "sentence uses; do not narrow the sentence."
    )


@pytest.mark.parametrize("sentence", REVIEWER_SET_BARE)
def test_the_gate_is_scored_on_sentences_it_did_not_write(sentence: str) -> None:
    """Overclaims written by someone who had not seen these patterns."""
    block = _flat(sentence)
    fires = any(c.search(block) for c in CLAIM) and any(
        a.search(block) for a in ATTRIBUTION
    ) and not _is_caveated(block)
    assert fires, (
        "the attribution gate lets this overclaim through:\n  " + sentence
        + "\nIt states the 42 with an 'only' attribution and never names the "
        "fire-blind control, which is the sentence WFG-138 exists to keep off a "
        "judge-facing surface."
    )


@pytest.mark.xfail(strict=True, reason="the reworded-overclaim class is open (WFG-138 notes)")
@pytest.mark.parametrize("sentence", REVIEWER_SET_REWORDED)
def test_a_reworded_overclaim_still_escapes(sentence: str) -> None:
    """Kept as a known hole, so it is measured rather than forgotten.

    Every gate here keys on spellings. This sentence carries the same false
    attribution with none of them, and widening the regex until it fires would
    start flagging correct sentences --- the direction MEMO 2026-09-06T1520Z
    calls the worse one. The honest position is that this class is open and
    belongs to a backlog row, not to a bigger pattern list.
    """
    block = _flat(sentence)
    fires = any(c.search(block) for c in CLAIM) and any(
        a.search(block) for a in ATTRIBUTION
    ) and not _is_caveated(block)
    assert fires
