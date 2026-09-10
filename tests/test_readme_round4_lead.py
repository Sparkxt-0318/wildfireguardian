"""WFG-212: the Round-4 section states what the project still claims, and stays caveated.

``README.md``'s Round-4 section is the largest and newest block on the front door and,
until this lap, it stated **only** what Round 4 attacked. Measured at ``4b580df``: 11 ⚠
markers and 28 negative-framing tokens over the section as the backlog row scoped it
(``README.md:200-362``, which is the lead area plus the five numbered items), against a
single affirmative token, and that one is the sentence saying the model-free opponent
scored better than the repository had recorded. Split the two halves and the five
numbered items carry **10** of those markers and the lead area **1**. 「자료의 논리적
구성」 is a named criterion of 제출 자료, worth 20 points on both KCF tables; a judge who
read the front door for sixty seconds at a booth left with the caveats and not the
contribution.

**This file gates the fix in both directions, because the fix is dangerous in both.**

1. The section must **open** with a lead block that says what the project claims after
   Round 4 (``test_the_round_4_section_opens_with_a_lead_block``), and the anchors it
   points at must exist.
2. That lead block may not become a performance claim
   (``test_the_lead_block_makes_an_existence_claim_and_not_a_comparison``,
   ``test_the_claim_half_of_the_lead_does_not_grow``). This is the root objection the lap
   recorded against its own plan: **every headline claim this repository has written on
   this front door has been narrowed or withdrawn within days** — the fire-blind
   baseline, the buffer 「봉우리」, 「어느 심사용 자료에도」, the meaning of the 42. A lead
   paragraph is a fresh surface for exactly that failure.
3. No caveat may leave, and none may be inverted while its wording survives
   (``test_every_caveat_the_section_carried_is_still_there``,
   ``test_the_reading_note_still_says_the_results_cut_against_this_project``,
   ``test_the_dispatch_ordering_result_is_stated_without_a_hedge``,
   ``test_the_warning_markers_in_the_numbered_items_did_not_thin_out``). WFG-212 is not a
   request to soften anything and this is the half that binds that.

⚠ **THREE OF THE ASSERTIONS BELOW EXIST BECAUSE THE LAP'S INDEPENDENT REVIEWER BEAT THE
FIRST VERSION OF THIS FILE, AND THEY ARE ITS MUTATIONS, NOT THIS AUTHOR'S.** The first
version pinned literal substrings written by the same lap after writing them — the
tautology ``mandela`` pattern #4 — and the reviewer walked through it three times with
the whole suite green (1867 passed):

* it inverted the reading note from an audit into a pitch (「유리한 항목은 다섯 항목
  전부입니다 … 신뢰도를 **높여 주는** 결과」) while keeping the pinned prefix 「이 절에서
  이 프로젝트에」;
* it appended an unsourced operational-readiness and novelty sentence inside the lead
  (「현장 담당자가 그대로 사용할 수 있는 수준으로 검증돼 있으며, 국내에서 이만한
  산출물을 내놓은 사례는 확인되지 않았습니다」);
* it softened the dispatch-ordering zero into 「확실하게 이긴 적이 **아직 없을 뿐**,
  실무에서는 **더 나은 순서일 수 있습니다**」 — and the pinned fragment 「이긴 적이」
  survives inside it word for word.

Each is now a property assertion rather than a longer quotation: a **direction** the note
must keep, a **ceiling** on the claim half so an affirmative sentence cannot simply be
appended, and a **hedge ban** on the sentence carrying the adverse result. The three
mutations are kept verbatim in ``_REVIEWER_MUTATIONS`` and re-run as a regression, so a
later rewrite of these patterns has to face the exploits that produced them.

⚠ **The floor in (3) is counted over the numbered items ONLY, deliberately.** The lead
block carries ⚠ markers of its own, so a section-wide floor would be satisfiable by the
very paragraph this row adds — a later lap could delete a real caveat and stay green
because the lead's markers filled the hole.

⚠ **What this file still cannot catch, measured rather than guessed.** It reads
``README.md`` only, so the same lead copied onto ``web/finals.html`` or the printed panel
without its bounds passes everything here; the bilingual lint that would close it is
WFG-168 and does not exist. And a pinned fragment remains a copy-paste ratchet and not a
claim detector: a rewording that keeps none of the pinned strings and states the
overclaim in fresh words escapes, which is the same measured limit
``docs/withdrawn_claims.md`` §4 records for the withdrawn-claim registry and which
``tests/test_future_aware_attribution.py::test_a_reworded_overclaim_still_escapes``
already carries as a declared xfail. The three
assertions added after the review narrow that gap where the reviewer actually walked
through it; they do not close the class.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
README = REPO / "README.md"

_SECTION_START = "## Round 4 (2026-09"
_FIRST_ITEM = "### 1. 가장 강한 주장에"
#: The first heading after item 5 that is no longer Round-4 material.
_SECTION_END = "### 프로젝트 개요"


@pytest.fixture(scope="module")
def readme() -> str:
    return README.read_text(encoding="utf-8")


def _slice(readme: str, start: str, end: str) -> str:
    lines = readme.splitlines()
    try:
        i = next(n for n, line in enumerate(lines) if line.startswith(start))
        j = next(n for n, line in enumerate(lines) if n > i and line.startswith(end))
    except StopIteration:  # pragma: no cover - the assertions below report it
        raise AssertionError(f"README.md has no {start!r} .. {end!r} block") from None
    return "\n".join(lines[i:j])


@pytest.fixture(scope="module")
def lead(readme: str) -> str:
    """Everything between the Round-4 heading and item 1: the section's opening."""
    return _slice(readme, _SECTION_START, _FIRST_ITEM)


@pytest.fixture(scope="module")
def items(readme: str) -> str:
    """The five numbered items, without the lead block."""
    return _slice(readme, _FIRST_ITEM, _SECTION_END)


@pytest.fixture(scope="module")
def section(readme: str) -> str:
    """The WHOLE Round-4 section: the lead block AND the five numbered items.

    ⚠ Added by WFG-222, and the reason is this file's own defect. Every bound assertion
    here read the ``lead`` fixture, while ``items`` — which contains §5, the 창의성 block —
    asserted only caveat-fragment presence, a ⚠ floor and one hedge ban. So the section
    could answer its own headline claim two ways one hundred and eighty lines apart with
    the whole suite green, and for one window it did: the lead said 지점 단위 with its
    bounds and §5 item ① said 가구 단위 with none (critic #54).
    """
    return _slice(readme, _SECTION_START, _SECTION_END)


# --------------------------------------------------------------------------- (1)

#: The claim's own truth-makers. A judge who opens these settles what the lead asserts.
_ANCHORS = ("outputs/dispatch/README.md", "docs/real_roads_real_hazard.md")


def test_the_round_4_section_opens_with_a_lead_block(lead: str) -> None:
    """The section says what the project claims BEFORE it says what Round 4 attacked."""
    body = "\n".join(line for line in lead.splitlines() if not line.startswith("## "))
    assert body.strip(), "the Round-4 section has nothing between its heading and item 1"
    assert "여전히 주장하는 것" in body, (
        "the Round-4 section no longer opens by stating what this project still claims "
        "after Round 4 (WFG-212). The section documenting what Round 4 attacked is not "
        "the same thing as the section stating the contribution, and a judge reading "
        "the front door for sixty seconds meets this block first."
    )
    for anchor in _ANCHORS:
        assert anchor in body, f"the lead block no longer points at {anchor}"
        assert (REPO / anchor).exists(), f"the lead block points at a missing {anchor}"


# --------------------------------------------------------------------------- (2)

#: References to the section's own numbered items and to the four-way partition. These
#: are digits the lead legitimately uses, and they are removed before the numeral ban
#: below is applied, so that 「5번」 is not read as the margin value 5.
_ITEM_REF = re.compile(r"[0-9]+\s*(?:번|-\s*구분)")
#: The five present-perimeter margin values NH-032, NH-034 and NH-052 are open about.
#: Digit-guarded, so 2025 and NH-053 are not false positives.
_MARGIN_VALUE = re.compile(r"(?<![0-9])(?:9|27|5|19|86)(?![0-9])")
#: The headline number. Every surface that states it owes both binding caveats
#: (``tests/test_readme_round4.py``); the lead block's answer is not to state it.
_HEADLINE = re.compile(r"(?<![0-9])42(?![0-9])")
#: The word NH-053 owns and no lap may settle.
_BOUND_WORD = re.compile(r"upper[- ]bound|상한", re.I)
#: Wordings that turn an existence claim into a performance or precedence claim. The
#: last three are the reviewer's: an operational-fitness claim contradicts the standing
#: 「본 시스템은 운영용 소프트웨어가 아닙니다」, and a precedence claim is a statement
#: about the world that no artifact in this tree sources.
_COMPARATIVE = re.compile(
    r"보다 (?:낫|좋|우수)|더 정확|능가|앞섭니다|이깁니다|최고|최초"
    r"|그대로 사용할 수 있|사례는 (?:확인되지|없)|유일"
)


def test_the_lead_block_makes_an_existence_claim_and_not_a_comparison(lead: str) -> None:
    """The lead may only assert what opening a committed file settles.

    This is the lap's own root objection made mechanical. A lead paragraph is the
    natural place for a later lap to put a number, and the numbers available to it are
    all either open questions (the margin values, the meaning of the headline) or
    comparisons this repository has already had to narrow once.
    """
    without_item_refs = _ITEM_REF.sub(" ", lead)
    assert not _MARGIN_VALUE.search(without_item_refs), (
        "the Round-4 lead block states a present-perimeter margin value. NH-032, NH-034 "
        "and NH-052 are open on which of them is canonical, and until they are answered "
        "no judge-facing surface carries one."
    )
    assert not _HEADLINE.search(lead), (
        "the Round-4 lead block states the headline number. Every surface stating it "
        "owes BOTH binding caveats in the same block "
        "(tests/test_readme_round4.py); a lead paragraph is not the place to re-open "
        "that budget."
    )
    assert not _BOUND_WORD.search(lead), (
        "the Round-4 lead block uses the 상한 / upper-bound wording. Nothing in this "
        "tree derives it and NH-053 is open: describe the grading mechanism and point "
        "at the question."
    )
    assert not _COMPARATIVE.search(lead), (
        "the Round-4 lead block makes a comparative, operational-fitness or precedence "
        "claim. WFG-212 asks for what the project claims and what bounds it. The "
        "comparisons live in items 1 and 3, where they are measured and where they cut "
        "against this project; 「운영용 소프트웨어가 아닙니다」 is a standing statement "
        "elsewhere in this README; and a claim about what does or does not exist in "
        "Korea is a claim about the world with no artifact behind it."
    )


#: Sentence terminators in the CLAIM half of the lead (everything before the first ⚠),
#: measured on the shipped block. A ceiling, not a floor: the reviewer's exploit was an
#: APPENDED sentence, and no wording ban catches a sentence nobody has written yet.
_CLAIM_HALF_SENTENCES = 5


def test_the_claim_half_of_the_lead_does_not_grow(lead: str) -> None:
    """An affirmative sentence cannot simply be added to the claim.

    ⚠ The reviewer's second mutation was one appended sentence, and every wording ban is
    a list of things somebody already thought of. A ceiling is the assertion that does
    not depend on guessing the wording: to add a sentence here a lap must raise this
    number in the same commit, where the diff shows a human what was added.
    """
    claim_half = lead.split("⚠")[0]
    count = len(re.findall(r"다\.", claim_half))
    assert count <= _CLAIM_HALF_SENTENCES, (
        f"the claim half of the Round-4 lead now states {count} sentences, above the "
        f"{_CLAIM_HALF_SENTENCES} it shipped with. Every sentence here is an assertion "
        "a judge will hold this project to and that only a committed file can settle. "
        "If the addition is genuinely one of those, raise this ceiling in the same "
        "commit and say in the message what the new sentence's truth-maker is."
    )


def test_the_lead_block_carries_its_own_bounds(lead: str) -> None:
    """A claim written without its bounds in the same block is the failure of `12b8ac7`."""
    assert "⚠" in lead, "the Round-4 lead block states a claim with no ⚠ bound attached"
    for fragment in (
        "같은 실행이 아니",  # the two anchors are two pipelines, not one
        "화재 위험면과 지형은 합성",  # and the one that made the sheets had no real fire
        "실제 가구 주소가 아닙니다",  # the origins are sampled candidates
        "「좋다」는 주장은 여기에 없습니다",  # no performance claim is being made
        "이긴 적이",  # the dispatch-ordering negative result
        "「발화 즉시」가",  # the detection floor
        "행정리가",  # the clusters are not administrative villages
        "계획에 쓴 바로 그 장으로 채점",  # the oracle is in the grading
        "NH-053",  # and the question it leaves open is named
    ):
        assert fragment in lead, (
            f"the Round-4 lead block no longer carries the bound {fragment!r}. The lead "
            "states the contribution; these are what keep it from being an overclaim, "
            "and they are load-bearing in the same block, not two screens away."
        )


def _bounds_module():
    """The claim/bound families, loaded from the file that owns them (one definition).

    ``tests/test_output_object_claim_bounds.py`` holds the families for every surface;
    importing them here rather than re-typing them means a later lap that narrows one
    narrows it for the README too.
    """
    import importlib.util

    path = Path(__file__).with_name("test_output_object_claim_bounds.py")
    spec = importlib.util.spec_from_file_location("_wfg222_bounds", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_every_existence_claim_in_the_section_carries_its_bounds(section: str) -> None:
    """The assertion runs over the SECTION, which is what WFG-222 asks for.

    ⚠ This is the fixture-boundary defect made mechanical. The property is per block, not
    per file: a bullet that says committed instances of the output object exist must say,
    in that same bullet, that the run which produced them had a synthetic hazard surface
    and sampled origins. A bound in the lead does not pay for a claim in §5, and that is
    the whole finding — 「같은 파일 안에서 180줄 떨어져 있다」 was critic #54's phrase for it.

    Blocks are cut at top-level ``- `` bullets and ``### `` headings, so the unit is what a
    judge reads as one item. ⚠ A ``>`` blockquote run is ONE block however many bullets it
    holds: the lead block is a single quote whose bullets are its bounds, and cutting it per
    bullet would demand every bound repeat every other bound — the assertion would then be
    about typography rather than about what a judge reads.
    """
    mod = _bounds_module()
    blocks: list[str] = []
    current: list[str] = []
    in_quote = False
    for line in section.splitlines():
        quoted = line.startswith(">")
        new_block = (quoted and not in_quote) or (
            not quoted
            and (in_quote or line.startswith("- ") or line.startswith("### "))
        )
        if new_block and current:
            blocks.append("\n".join(current))
            current = []
        current.append(line)
        in_quote = quoted
    if current:
        blocks.append("\n".join(current))

    naked = []
    for block in blocks:
        if not mod._EXISTENCE.search(block):
            continue
        if not (mod._SYNTHETIC.search(block) and mod._SAMPLED.search(block)):
            naked.append(block.strip().splitlines()[0][:90])
    assert not naked, (
        "a block in README.md's Round-4 section says committed instances of the output "
        "object exist and does not carry, in the same block, that the hazard surface and "
        "terrain of that run are synthetic and the origins sampled: "
        + " || ".join(naked)
        + ". data/processed/rescue_routing.json → provenance.sources says both about "
        "itself; the lead block at the top of this section is the model to copy (WFG-222). "
        "⚠ If a genuinely new block legitimately mentions a committed artifact without "
        "making the output-object existence claim, narrow the family in "
        "tests/test_output_object_claim_bounds.py rather than widening this scan."
    )


def test_the_section_never_puts_the_committed_instances_in_the_household_register(
    section: str,
) -> None:
    """One word, over the section rather than the lead.

    Q20a's definition of 「가구」 as one OSM walk-graph node lives in the Q&A bank and is
    untouched. On the front door, where no definition is within reach of a judge's eye,
    the word for the committed instances is 지점.
    """
    mod = _bounds_module()
    hits = mod._HOUSEHOLD.findall(section)
    assert not hits, (
        "README.md's Round-4 section describes the output object in the household "
        "register again (" + ", ".join(hits) + "). The origins are sampled walk-network "
        "coordinates, not addresses; 지점 단위 is the word this section settled on at "
        "2206Z on 2026-09-09, and WFG-222 is the row that made the other four surfaces "
        "agree with it."
    )


# --------------------------------------------------------------------------- (3)

#: One load-bearing clause per ⚠ caveat carried by the five numbered items at 4b580df.
_ITEM_CAVEATS = (
    "그 완충거리의 폭은 자유 매개변수이고",
    "이 자리에 있던 문장 하나를 내렸습니다",
    "이 프로젝트에 불리한 쪽으로",
    "결과를 다 보고 고른 것입니다",
    "영덕에서는 이 상대를 아직 돌리지 않았습니다",
    "부스에서 말하지 않습니다",
    "이 장치의 한계는 장치 자신이 적어 둡니다",
    "화소 이하 크기의 바닥",
    "얼마나 뛰어난지는 적지 않습니다",
    "복사·붙여넣기를 막는 래칫이지 주장 탐지기가 아니어서",
)

#: ⚠ Counted over the numbered items ONLY (see the module docstring). 10 at 4b580df.
_ITEM_WARNING_FLOOR = 10


def test_every_caveat_the_section_carried_is_still_there(items: str) -> None:
    """WFG-212 adds material; it removes no ⚠ line, and neither may any later lap."""
    for fragment in _ITEM_CAVEATS:
        assert fragment in items, (
            f"the Round-4 numbered items no longer carry the caveat {fragment!r}. "
            "The withdrawn-claim record is this project's strongest card (README "
            "TL;DR) and CHARTER §3 rule 5 forbids rounding a limitation away: a lap "
            "that means to correct a caveat annotates it, it does not delete it."
        )


def test_the_reading_note_still_says_the_results_cut_against_this_project(lead: str) -> None:
    """The note's DIRECTION is the property, not its wording.

    ⚠ The reviewer's first mutation kept the pinned prefix 「이 절에서 이 프로젝트에」 and
    turned the rest of the sentence into its opposite. What must survive is the claim
    that the results in this section cut against this project, so that is what is
    asserted here.
    """
    assert "읽는 법" in lead, "the Round-4 section's 「읽는 법」 note is gone"
    assert "깎는" in lead, (
        "the 「읽는 법」 note no longer says that the section's results CUT against this "
        "project. That direction is the whole reason the section reads as an audit "
        "rather than as a pitch, and a note that keeps its opening words while "
        "reversing its verdict is the mutation this assertion exists for."
    )
    assert "유리한 결과는" in lead and "없습니다" in lead, (
        "the 「읽는 법」 note no longer states that no result in this section favours "
        "this project. If a genuinely favourable RESULT is ever added to the section, "
        "this assertion is the place where a lap has to say so out loud."
    )


#: Hedges that turn a measured zero into an opinion.
_HEDGE = re.compile(r"일 수 있습니다|아직 없을 뿐|가능성이 있|아마|~?정도로 보입니다")


def test_the_dispatch_ordering_result_is_stated_without_a_hedge(items: str) -> None:
    """The adverse result stays a result.

    ⚠ The reviewer's third mutation kept the pinned 「이긴 적이」 and wrapped it in
    「확실하게 … 아직 없을 뿐, 실무에서는 더 나은 순서일 수 있습니다」. The property is
    that the bullet states a count and states it flatly, so both are asserted.
    """
    bullets = [b for b in items.split("\n- ") if "최근접 우선" in b]
    assert len(bullets) == 1, (
        f"expected exactly one Round-4 bullet stating the dispatch-ordering result "
        f"against 최근접 우선, found {len(bullets)}"
    )
    bullet = bullets[0]
    assert "이긴 적이" in bullet and "없습니다" in bullet, (
        "the dispatch-ordering bullet no longer states that deadline-first has never "
        "beaten nearest-first. → docs/dispatch_ordering.md"
    )
    assert "이긴 칸의" in bullet and "0" in bullet, (
        "the dispatch-ordering bullet no longer states the count of cells won. The "
        "count is the result; a sentence without it is an impression."
    )
    assert not _HEDGE.search(bullet), (
        "the dispatch-ordering bullet now hedges its own negative result. CHARTER §3 "
        "rule 5: when a result is weak, say so in the artifact — and when a result is "
        "against this project, it is stated flatly, not softened into a maybe."
    )


def test_the_warning_markers_in_the_numbered_items_did_not_thin_out(items: str) -> None:
    """A floor, not an equality: adding caveats is always allowed."""
    count = items.count("⚠")
    assert count >= _ITEM_WARNING_FLOOR, (
        f"the five numbered Round-4 items carry {count} ⚠ markers, below the "
        f"{_ITEM_WARNING_FLOOR} measured at 4b580df. If a caveat was genuinely "
        "resolved, annotate it in place and lower this floor in the same commit with "
        "the reason; a silent drop is what this gate exists to refuse."
    )


# --------------------------------------------------------------------------- regression

#: The independent reviewer's three exploits, verbatim, each with the assertion that now
#: refuses it. They are kept as data rather than as prose so that a later rewrite of the
#: patterns above has to re-run them.
_REVIEWER_MUTATIONS = (
    (
        "이 절에서 이 프로젝트에 **유리한** 항목은 다섯 항목 전부입니다. 1번과 3번도 "
        "결국 이 프로젝트의 신뢰도를 **높여 주는** 결과이고, 그렇게 적는 것이 이 절의 "
        "목적입니다.",
        "깎는",
    ),
    (
        "이 판정은 현장 담당자가 그대로 사용할 수 있는 수준으로 검증돼 있으며, 국내에서 "
        "이만한 산출물을 내놓은 사례는 확인되지 않았습니다.",
        None,
    ),
    (
        "운영 시점의 창에서 단순한 **최근접 우선**을 확실하게 이긴 적이 아직 없을 뿐, "
        "실무에서는 더 나은 순서일 수 있습니다.",
        None,
    ),
)


def test_the_reviewers_three_exploits_are_each_refused() -> None:
    """The mutations that beat the first version of this file, run as data.

    ⚠ This does not re-run the whole gate on a mutated README — it asserts the property
    each exploit violated, which is what the assertions above are made of. The first
    exploit is caught by the missing 「깎는」 direction, the second by the comparative and
    precedence family, the third by the hedge ban.
    """
    note, must_lose = _REVIEWER_MUTATIONS[0]
    assert must_lose not in note, (
        "the inverted reading note is supposed to have dropped 「깎는」; if it has not, "
        "test_the_reading_note_still_says_the_results_cut_against_this_project is no "
        "longer the assertion that catches it"
    )

    superlative = _REVIEWER_MUTATIONS[1][0]
    assert _COMPARATIVE.search(superlative), (
        "the appended operational-readiness and precedence sentence is no longer caught "
        "by _COMPARATIVE"
    )

    hedged = _REVIEWER_MUTATIONS[2][0]
    assert _HEDGE.search(hedged), "the softened dispatch-ordering bullet escapes _HEDGE"
    assert "이긴 적이" in hedged, (
        "the softened bullet no longer contains the fragment the first version of this "
        "file pinned — the whole point of keeping it here is that it does"
    )
