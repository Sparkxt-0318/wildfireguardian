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

⚠ **What this file's first version got wrong, kept here because it is the most useful
thing in it.** Rule 3 was enforced on the **English** abstract only, keyed on the
spelling ``42 of 458``, and the docstring named the Korean half as the gap it could
not cover -- while the very same commit added a Korean bullet stating 「42곳」 with
neither caveat. The lap's independent reviewer blocked the push on it. **Naming a
mutation you cannot catch is not a substitute for not shipping it**, and a guard that
lists the sites it knows about, written after looking at them, passes by construction
(that is the leakage the ``mandela`` skill is for). Rule 3 is now enforced on **every**
block that states the number in **either** language, keyed on the bare number so that
dropping the denominator does not buy an escape -- which is exactly how
``tests/test_future_aware_attribution.py`` missed the same line.

⚠ **The mutation this file still cannot catch** (``docs/auto/DIRECTION.md``, critic
#41's rule): it reads ``README.md`` only. The same uncaveated sentence written onto
`web/finals.html`, `docs/auto/JUDGE_QA.md` or the printed panel passes everything
here. ``tests/test_future_aware_attribution.py`` covers some of those surfaces with a
regex that requires the denominator, so a sentence dropping it escapes there too;
closing that properly is **WFG-168**, the bilingual lint, which does not exist yet.
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

#: ⚠ **REWRITTEN 2026-09-09 (WFG-214). The old pattern was
#: ``r"42 is\s+an\s+\*{0,2}upper[- ]bound\*{0,2}"`` and it required the README to
#: ASSERT the very sentence NH-053 asks the author about.** ``docs/oracle_gap.md``
#: §2, built from the committed ``routing_demo_canonical.npz``, establishes that the
#: forecast-aware arm does not plan on truth: it plans on ``haz_stack``, a
#: leave-one-fire-out forward simulation of a fire the model never trained on, and
#: what makes the arm an oracle is that the **grader** treats that same array as
#: truth. That the arm therefore cannot be wrong about its grading field is a
#: MECHANISM this repository derives. That 42 is consequently an **upper bound** on
#: what the real model buys is a further claim, and nothing in the tree derives it --
#: NH-053. A gate may require the mechanism; it may not require the conclusion.
#: So this family matches either wording, and
#: ``test_no_block_asserts_the_bound_without_naming_the_open_question`` below is what
#: keeps the second one honest wherever it is used.
_ORACLE = re.compile(
    r"graded on the \*{0,2}(?:very|same) field it planned on"
    r"|plans on the \*{0,2}same hazard field it is scored against"
    r"|oracle is in the grading"
    r"|oracle sits in the grading"
    r"|42 is\s+an\s+\*{0,2}upper[- ]bound\*{0,2}"
    r"|upper[- ]bound\*{0,2} on the real margin",
    re.I,
)

#: The word this repository may NOT settle in a lap, in either language, and the
#: escalation that owns it. A block using the bound wording about 42 or 91 must name
#: NH-053 in the same block, so a judge who reads the word also reads that it is open.
_BOUND_WORD = re.compile(r"upper[- ]bound|상한", re.I)
_OPEN_QUESTION = re.compile(r"NH-053")

#: ⚠ **THE INDEPENDENT REVIEWER OF THE LAP THAT WIDENED `_ORACLE` FOUND THE HOLE THE
#: WIDENING OPENED, AND THIS IS THE PATCH FOR IT.** `_ORACLE` is a strict superset of
#: the pattern it replaced, and the old pattern had one property incidentally: the only
#: clause that could satisfy it, 「42 is an upper bound」, **contradicts** the overclaim.
#: The mechanism alternatives are merely **compatible** with it, so a block that states
#: the mechanism correctly and then draws the opposite conclusion —
#:
#:     the forecast-aware arm is graded on the very field it planned on, so the oracle
#:     is in the grading. 42 is therefore what this project's own model buys
#:
#: — passed the widened suite green. That sentence is the reviewer's, not this file's
#: author's, which is the whole reason it is worth gating: it is a sentence somebody who
#: had not written the patterns produced while trying to get past them.
#:
#: The claim is banned only in the AFFIRMATIVE. The README's correct prose says exactly
#: this phrase with a negator in front of it ("**not** what this project's own model
#: buys"), and `re` has no variable-length lookbehind, so the negator is checked in a
#: window rather than in the pattern.
_OWN_MODEL_BUYS = re.compile(
    r"what (?:this project'?s|our|the project'?s)(?: own)? model buys"
    r"|이 프로젝트의 모델이 (?:실제로 )?사 준 값"
    r"|모델이 실제로 사 준 값",
    re.I,
)
#: Anything in the 48 characters before the phrase that turns it into a denial. Korean
#: negation trails its verb, so 「…이 아닙니다」 cannot be caught this way; the Korean
#: surfaces are instead covered by the affirmative form being unnatural without one of
#: these, and by `_BOUND_WORD`'s NH-053 requirement in the same block.
_NEGATOR = re.compile(r"\bnot\b|rather than|instead of|아니라|말고|보다\s*$", re.I)


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
    fire-blind caveat says the opponent could not see the fire; the oracle caveat
    says the forecast-aware arm is graded on the field it planned on. A surface
    carrying only the first still tells a judge that 42 is what this project's model
    buys, which is the claim the repository does not have.
    """
    para = _paragraph_stating_42(lines)
    assert _FIRE_BLIND.search(para), (
        "the paragraph stating 42 does not say the contrast is measured against a "
        "fire-blind baseline. ⚠ Naming 'fire-blind' elsewhere in the abstract does "
        "not count: the caveat has to bind THIS number, in this paragraph."
    )
    assert _ORACLE.search(para), (
        "the paragraph stating 42 does not say that the forecast-aware arm is graded "
        "on the same field it planned on. DIRECTION requires BOTH caveats on every "
        "surface stating 42. ⚠ The MECHANISM satisfies this, and since WFG-214 it is "
        "the preferred wording: `docs/oracle_gap.md` §2 shows the planning field is a "
        "leave-one-fire-out model output rather than truth, so the oracle is in the "
        "grading. Calling 42 an 'upper bound' also satisfies it, but that word is "
        "NH-053 and carries its own requirement below."
    )


#: The same two caveats in Korean, again as the binding clause and not a bare token.
_FIRE_BLIND_KO = re.compile(r"불을 전혀\s*보지\s*못하는")
#: ⚠ Widened with ``_ORACLE`` for the same reason (WFG-214): 「상한」 alone was the
#: only Korean spelling that satisfied this, so the gate could be cleared only by
#: writing the word NH-053 asks about. The mechanism clause now satisfies it too.
_UPPER_BOUND_KO = re.compile(r"상한|채점하는 쪽에 있|계획에\s*쓴 바로 그 장으로 채점")

#: The ONE site that states 42 without carrying the caveats, exempted BY NAME with a
#: written reason: the Round-3 table cell is a record of the 제출본 → 정본 correction
#: (「미래 인지 경로로만 안전 | 17곳 | **42곳**」), not an assertion about what the
#: forecast buys. CHARTER §3.7 keeps such records rather than editing them.
#: ⚠ An exemption is a claim too. It is one line, it names the section, and a second
#: exempted site may not be added without the same treatment.
_RECORD_SITE = "미래 인지 경로로만 안전"


def _blocks_stating_42(readme: str) -> list[tuple[int, str]]:
    """(1-indexed start line, whitespace-normalised text) of each block stating 42.

    A *block* is a run of contiguous non-blank lines -- a paragraph, a bullet with
    its continuation lines, or a table. That is the unit a reader actually meets,
    and it is the unit ``_paragraph_stating_42`` already uses for the English side.
    """
    lines = readme.splitlines()
    out: list[tuple[int, str]] = []
    start = 0
    while start < len(lines):
        if not lines[start].strip():
            start += 1
            continue
        end = start
        while end < len(lines) and lines[end].strip():
            end += 1
        block = lines[start:end]
        if any(re.search(r"42 of 458|42곳", ln) for ln in block):
            out.append((start + 1, " ".join(" ".join(block).split())))
        start = end
    return out


def test_every_block_stating_42_carries_both_caveats_in_either_language(readme: str) -> None:
    """DIRECTION's rule, enforced on **every** site rather than on the English one.

    ⚠ **This assertion exists because the lap that wrote this file broke the rule it
    was writing.** The first version keyed on ``42 of 458`` and on a hand-listed count
    of "known sites", and the same commit added a Korean bullet stating 「42곳」 with
    neither caveat in its own block -- the exact mutation the module docstring named
    as uncatchable, shipped while naming it. The lap's independent reviewer blocked
    the push on it.

    Two things were wrong and both are fixed here. The regex required the denominator
    (``458 … 42``), so a sentence that drops it escapes classification entirely --
    which is how ``tests/test_future_aware_attribution.py`` also missed the new site.
    And the "known sites" count *whitelisted* the offending line: the scope of the
    metric was chosen after seeing the artifact, so the artifact passed by
    construction. That is textbook measurement leakage, and it is why this test keys
    on the bare number and exempts exactly one site, by name, with a reason.
    """
    blocks = _blocks_stating_42(readme)
    assert blocks, "the README no longer states 42 anywhere -- that is a change, not a pass"

    offenders = []
    for line_no, text in blocks:
        if _RECORD_SITE in text:
            continue  # the Round-3 correction record, exempted above by name
        fire_blind = bool(_FIRE_BLIND.search(text) or _FIRE_BLIND_KO.search(text))
        oracle = bool(_ORACLE.search(text) or _UPPER_BOUND_KO.search(text))
        if not (fire_blind and oracle):
            missing = []
            if not fire_blind:
                missing.append("fire-blind opponent")
            if not oracle:
                missing.append("graded on the field it planned on / 상한")
            offenders.append(f"README.md:{line_no} is missing: {', '.join(missing)}")

    assert not offenders, (
        "a block states 42 without both binding caveats attached to it:\n  "
        + "\n  ".join(offenders)
        + "\n\nDIRECTION: 'Every judge-facing surface that states 42 or 91 carries "
        "both binding caveats (fire-blind opponent; the forecast-aware arm is graded "
        "on the field it planned on). A new sentence about either number carries both "
        "caveats or it is not written.' A caveat in a neighbouring block does not "
        "count -- a judge reading this sentence would never meet it."
    )


def test_no_block_asserts_the_bound_without_naming_the_open_question(readme: str) -> None:
    """WFG-214, and the constraint that IS the row.

    Until 2026-09-09 three README lines told the reader that 42 is 「what a noiseless
    forecast would buy」 / 「완벽한 예보가 사 줄 값의 상한」, flatly. `docs/oracle_gap.md`
    §2 shows the arm plans on a leave-one-fire-out model output and is graded on that
    same array, so what the number is worth 「when its own prediction is believed」 is
    derived; that this bounds the real model's margin from above is **not** derived by
    anything in this tree, and it is asked of the author as NH-053.

    The row may not settle that word in either direction — deleting it decides the
    question by omission just as asserting it does. So the word stays usable and this
    gate binds it to the escalation: wherever a block about 42 or 91 uses 「upper
    bound」 or 「상한」, the same block names NH-053. A judge who meets the word meets
    the fact that it is open, in the same breath.

    ⚠ Scope is the block, deliberately, and for the reason
    `test_every_block_stating_42_carries_both_caveats_in_either_language` gives above:
    a note two paragraphs away is one a reader never meets.
    """
    offenders = []
    for line_no, text in _blocks_stating_42(readme):
        if _RECORD_SITE in text:
            continue
        if _BOUND_WORD.search(text) and not _OPEN_QUESTION.search(text):
            offenders.append(f"README.md:{line_no}")
    assert not offenders, (
        "a block states 42 or 91, calls it an upper bound / 「상한」, and does not say "
        "the word itself is an open question:\n  " + "\n  ".join(offenders)
        + "\n\nNothing in this repository derives that bound; NH-053 asks the author "
        "whether it survives at all. Name NH-053 in the same block, or describe the "
        "mechanism (`docs/oracle_gap.md` §2) and leave the word out."
    )


def test_no_block_says_42_is_what_this_projects_own_model_buys(readme: str) -> None:
    """The claim the whole caveat apparatus exists to keep off this page.

    ⚠ **This test exists because the independent reviewer of the lap that widened
    `_ORACLE` wrote a sentence that got past it**, reproduced in the comment above
    `_OWN_MODEL_BUYS`: mechanism stated correctly, conclusion inverted. The old
    `_UPPER_BOUND` caught that shape by accident — its only satisfying clause
    contradicted the overclaim — and the widening, which `docs/auto/DIRECTION.md:65-67`
    required, gave the accident up. So the property is asserted directly instead of
    being inherited from a wording.

    Banned in the affirmative only: the correct prose on this page says the same phrase
    with a negator in front of it, and a gate that cannot tell 「X」 from 「not X」 would
    flag the sentence it exists to protect — the direction MEMO 2026-09-06T1520Z calls
    the worse one.
    """
    offenders = []
    for line_no, text in _blocks_stating_42(readme):
        if _RECORD_SITE in text:
            continue
        for m in _OWN_MODEL_BUYS.finditer(text):
            window = text[max(0, m.start() - 48):m.start()]
            if not _NEGATOR.search(window):
                offenders.append(f"README.md:{line_no}: ...{text[max(0, m.start()-70):m.end()+10]}")
    assert not offenders, (
        "a block states 42 and then claims it IS what this project's own model buys:\n  "
        + "\n  ".join(offenders)
        + "\n\nNo run in this repository measures that. `docs/oracle_gap.md` §6 is the "
        "re-grading that would, WFG-213 is the row and it is blocked(NH-052). Say what "
        "the number is — what the policy buys when its own prediction is believed — and "
        "stop there."
    )


def test_the_record_exemption_still_matches_exactly_one_block(readme: str) -> None:
    """The exemption above is a claim, so it is checked like one.

    An exemption that silently widens is how a rule dies. If the Round-3 record cell
    is reworded, or a second block acquires the same anchor text, this fails and the
    next lap re-decides deliberately instead of inheriting a hole.
    """
    exempted = [ln for ln, text in _blocks_stating_42(readme) if _RECORD_SITE in text]
    assert len(exempted) == 1, (
        f"the record exemption matches {len(exempted)} blocks stating 42 (lines "
        f"{exempted}); it is written for exactly one, the Round-3 correction table."
    )
