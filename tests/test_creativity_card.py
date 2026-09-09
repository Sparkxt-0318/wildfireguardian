"""Gates on Q29a, the 창의성 card. Backlog row WFG-182.

Why this card needs a gate of its own
-------------------------------------
창의성 is 20 points on both KCF tables and the card that answers it is the one
place in this bank where the obvious way to write the answer is the one thing
this repository has spent a week removing: a self-assessment, or a comparison
with somebody else's system. Critic #40's finding was that the score had not
moved in 39 scorecard rows; critic #41 measured that no judge-facing surface
mentioned 창의성 at all. So the card was written, and it is written in the
descriptive register — *what was built*, three items, each pointing at a
committed file — and NOT in the evaluative one.

That register is the whole safety of the card, and prose does not hold a
register on its own. What is checked here:

* the card exists, is T0, its three load-bearing artifacts exist, and the
  spoken draft still makes all three items;
* the spoken draft makes **no novelty claim**. Nothing else in this repository
  catches one: ``scripts/check_forbidden.py``'s only 처음/최초 rule requires
  실측 within 40 characters, so a bare 「이번이 처음입니다」 on a T0 card passed
  every gate until the independent reviewer planted one;
* the spoken draft names **no other system** from a listed set, in either
  direction — a named list, therefore a partial one, and the residual limit is
  written in ``docs/creativity_card.md`` rather than implied. DIRECTION's
  standing rule (critics #37 and #34, ``WC-009``) is that a judge-facing
  sentence about another system carries what opened it — a catalogue entry, a
  named press report — or it is not written. This card carries none, so it must
  name none, and it sends the question to Q16a and the related-work panel where
  the provenance actually is;
* the spoken draft holds **no count** — any multi-digit run, and any digit or
  Korean numeral used with a counter of repository objects. Q30's register
  (WFG-117):
  a count about this repository's own state, typed onto a card the student
  recites, is the defect with the shortest fuse in this project — 「여섯 개」,
  「41문항」 and 「커밋된 33장」 were all written true and were false within a
  lap. This card states no quantity at all, and that is enforced rather than
  hoped for;
* the 없는 것 block still carries the limit that makes the third item honest —
  the withdrawn-claim registry catches a copied *spelling*, not a reworded
  claim.

What this does NOT do. It cannot tell whether the three items are the *right*
three, or whether a judge would find them creative; that is the judge's call
and the card says so in its own first 없는 것 line. The other-system list is a
named list and a system this repository has never named escapes it, and the
anchor check is card-level, so an item whose path is corrupted inside the draft
stays green while the 근거 block still lists the real one. See
``_the_mutation_this_cannot_catch`` at the foot of this file for the mutation
that was tried and stays green (WFG-186), and ``docs/creativity_card.md`` for
what the independent reviewer had to break before these limits were known.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
QA = REPO / "docs" / "auto" / "JUDGE_QA.md"

#: The card's three load-bearing artifacts, in the order the card names them.
#: Each is the file a judge would be handed if they pressed on that item.
ANCHORS = (
    "docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md",
    "docs/real_roads_real_hazard.md",
    "docs/withdrawn_claims.md",
    "docs/auto/withdrawn_claims.json",
    "scripts/check_withdrawn_claims.py",
)

#: Systems this project has written about elsewhere WITH their provenance, plus
#: the ones a student is most likely to reach for at a booth. Naming any of them
#: in THIS card is the defect: the card carries no source line, so a sentence
#: about another system here would be unsourced by construction. Both directions
#: are barred, not only the negative one.
#:
#: ⚠ **This is a named list and therefore a partial one, and the independent
#: reviewer proved it rather than arguing it**: 「FARSITE 는 …」 and 「소방청
#: 시스템에는 …」 were both green against the first version, which held only the
#: five systems this repository had already written about. That is a population
#: drawn to fit the claim — the very shape WFG-185 and WFG-186 are about. The
#: list is widened here and the residual limit is stated in
#: docs/creativity_card.md rather than papered over: a system this repository
#: has never named still escapes, and the cold read is what catches it.
OTHER_SYSTEMS = (
    "NIFoS", "G-DAPS", "산림청", "경기도", "국립산림과학원", "소방청", "소방방재청",
    "FARSITE", "FlamMap", "WRF", "Prometheus", "Phoenix", "행정안전부",
)

#: Novelty claim shapes. The card's own 없는 것 block tells the student not to
#: say these; nothing enforced it until the reviewer planted 「국내에서 이런
#: 접근은 이번이 처음입니다. 최초의 구조 순서 시스템입니다.」 into the draft and
#: watched BOTH this gate and scripts/check_forbidden.py stay green.
#: check_forbidden's only 처음/최초 rule requires 실측 within 40 characters
#: (the docs/decision_shift.md claim shape), so a bare novelty claim on a T0
#: card was caught by nothing at all.
NOVELTY_RE = re.compile(r"처음|최초|유일한|세계\s*최초|국내\s*최초|전례\s*없")


def _card() -> str:
    text = QA.read_text(encoding="utf-8")
    head = "**Q29a · T0"
    assert head in text, (
        "Q29a (창의성) is gone from the bank. It is the only judge-facing "
        "surface that answers the row worth 20 points on both KCF tables "
        "(WFG-182); if it is being retired, retire this gate in the same "
        "commit and say why in the backlog row."
    )
    return text[text.index(head):].split("\n---\n", 1)[0]


def _spoken() -> str:
    """Only the words the student says: 답변(초안) up to the 근거 line.

    Deliberately NOT the whole card. 근거 is a list of paths and 없는 것 is a
    list of things not to say; both legitimately contain digits and file names,
    and the assertions below are about what comes out of the student's mouth in
    front of a judge.
    """
    body = _card()
    assert "답변(초안):" in body, "Q29a has no 답변(초안) block"
    spoken = body.split("답변(초안):", 1)[1]
    assert "근거:" in spoken, "Q29a has no 근거 block; the bank requires one"
    return spoken.split("근거:", 1)[0]


def test_the_card_rests_on_artifacts_that_exist() -> None:
    """Each of the three items points at a file, and each file is here."""
    card = _card()
    missing = [a for a in ANCHORS if not (REPO / a).exists()]
    assert not missing, (
        "Q29a's 근거 names artifacts that are not in the tree: "
        + ", ".join(missing) + ". A creativity claim resting on a path that "
        "does not resolve is the one failure this card cannot afford."
    )
    unnamed = [a for a in ANCHORS if a not in card]
    assert not unnamed, (
        "these artifacts back Q29a's three items but the card no longer names "
        "them: " + ", ".join(unnamed)
    )


def test_the_card_names_no_other_system_in_either_direction() -> None:
    """The register rule, ``WC-009``, made mechanical for this one card.

    Graded: adding 「NIFoS 는 이걸 하지 않습니다」 to the draft turns this red,
    and so does the positive form 「NIFoS 는 진압 지휘용입니다」 — which is the
    half the loop did not have a rule for until critic #37 (WFG-171).
    """
    spoken = _spoken()
    named = [s for s in OTHER_SYSTEMS if s in spoken]
    assert not named, (
        "Q29a's spoken draft names another system: " + ", ".join(named) + ". "
        "This card carries no source line for any of them, so a sentence about "
        "one is unsourced by construction. The card's job is to describe what "
        "THIS project built; the comparison lives in Q16a and the related-work "
        "panel, where what was opened is written beside every clause."
    )


#: Korean numeral words, and the counters that count *repository objects*.
#: 「여섯 개」 — the WFG-178 defect, written onto three judge-facing surfaces by
#: the commit that made it wrong — carries no digit at all, so a digit-only
#: check cannot see the very failure this assertion exists for. It was written
#: digit-only first and a mutation caught that, which is why both halves are
#: here. 가지 and 번째 are deliberately NOT counters: 「세 가지」 counts the
#: card's own three items, which is structural prose, not a claim about state.
#: ⚠ 「한」 is excluded on purpose. It is overwhelmingly idiomatic in Korean
#: prose rather than enumerative — this card's own 「이유를 한 줄씩 적게」 is the
#: measured false positive that forced the exclusion — and a card asserting
#: 「한 개」 of something is not the defect class this guards. Every count this
#: repository has actually shipped wrong was two or more (33장, 여섯 개, 41문항).
_KO_NUMERAL = "두|세|네|다섯|여섯|일곱|여덟|아홉|열|스무"
_OBJECT_COUNTER = "개|건|장|줄|문항|커밋|파일|테스트|시트|항목"
#: ⚠ No trailing ``\b``. Korean particles attach directly to the counter
#: (「여섯 개는」, 「아홉 건이」) and Hangul syllables are word characters, so a
#: word boundary there can never match and the assertion would silently never
#: fire. It was written with ``\b`` first and two mutations stayed green, which
#: is how this was found — a gate that cannot fail is worse than no gate,
#: because it reports coverage it does not have.
KO_COUNT_RE = re.compile(r"(?:" + _KO_NUMERAL + r")\s*(?:" + _OBJECT_COUNTER + r")")


def test_the_card_states_no_number_about_this_repository() -> None:
    """Q30's register (WFG-117), applied before the card can acquire a count.

    The three defects this bank shipped in the week to 2026-09-08 were all the
    same shape: a true count of this repository's own state, typed onto a card,
    made false by a later commit. This card states no quantity at all, and the
    cheapest way to keep it that way is to refuse the first one — in both the
    notations this repository has actually shipped the defect in.
    """
    spoken = _spoken()
    # Any multi-digit run, AND any digit at all that is being used as a count of
    # repository objects. The reviewer's N1 — 「철회 주장은 9건입니다」 — sat one
    # digit under a `\d{2,}` threshold while being the exact WFG-117/WFG-178
    # defect class, so the counter list decides here rather than the width.
    numbers = re.findall(r"\d{2,}", spoken)
    numbers += re.findall(r"\d\s*(?:" + _OBJECT_COUNTER + r")", spoken)
    numbers += KO_COUNT_RE.findall(spoken)
    assert not numbers, (
        "Q29a's spoken draft has acquired a count: " + ", ".join(numbers)
        + ". If a quantity genuinely belongs here, derive it in this file the "
        "way tests/test_responsibility_and_privacy_cards.py derives Q16b's, "
        "and say in the card which set it counts — do not type it and leave it "
        "to go stale (WFG-117, WFG-178, WFG-185)."
    )


def test_the_card_makes_no_novelty_claim() -> None:
    """The one prohibition the card states and nothing enforced.

    The 없는 것 block tells the student not to say 「처음」 or 「최초」, and the
    lap that wrote it recorded in its own doc that
    ``scripts/check_forbidden.py`` was the independent backstop for that. **It
    is not.** That script's only 처음/최초 rule requires 실측 within 40
    characters — it is the docs/decision_shift.md claim shape, not a novelty
    ban — so 「국내에서 이런 접근은 이번이 처음입니다」 passes it, exit 0. The
    independent reviewer planted exactly that and blocked the lap on it.

    A novelty claim is the single most expensive sentence this card could
    acquire: it is unfalsifiable from the literature this project has opened,
    the card's own third item is about not making claims the tree cannot
    support, and it is on a T0 card the student says from memory.
    """
    spoken = _spoken()
    hits = NOVELTY_RE.findall(spoken)
    assert not hits, (
        "Q29a's spoken draft has acquired a novelty claim: " + ", ".join(hits)
        + ". The literature scan is the range of what this project has opened, "
        "and what lies outside it is unknown — the card's own 없는 것 block "
        "says so. Nothing else in this repository catches this: "
        "scripts/check_forbidden.py's 처음/최초 rule fires only next to 실측."
    )


def test_the_spoken_draft_still_makes_all_three_items() -> None:
    """Item-level structure, because the anchor check above is card-level.

    The reviewer's N4: deleting item 2 from the spoken draft entirely left
    every other assertion green, because the 근거 block still listed its file.
    A card that has quietly lost one of its three items still passes an
    anchors-are-named check, and the doc's method table reads as though each
    item were bound to its file. This binds the structure the table describes.
    """
    spoken = _spoken()
    missing = [m for m in ("첫째", "둘째", "셋째") if m not in spoken]
    assert not missing, (
        "Q29a's spoken draft no longer makes all three items: missing "
        + ", ".join(missing) + ". The card answers 창의성 with three things "
        "that were built, each pointing at a committed file; two of them is a "
        "different card and docs/creativity_card.md's method table would be "
        "describing something the bank no longer says."
    )


def test_the_card_keeps_the_limit_that_makes_its_third_item_honest() -> None:
    """The registry catches a copied spelling, not a reworded claim.

    Without this sentence the third item reads as 「we cannot state a withdrawn
    claim by accident」, which is false and is measured to be false in
    docs/withdrawn_claims.md section 4. The card is only allowed to offer the
    registry as a *method* while it also says what the method misses.
    """
    card = _card()
    assert "다시 쓴 문장은 빠져나갑니다" in card, (
        "Q29a no longer states that a REWORDED claim escapes the withdrawn-"
        "claim registry. That limit is what makes offering the registry as a "
        "method honest rather than a boast; docs/withdrawn_claims.md section 4 "
        "measured it."
    )
    assert "docs/withdrawn_claims.md" in card, (
        "the limit above must point at the document that measured it"
    )


# ---------------------------------------------------------------------------
# _the_mutation_this_cannot_catch (WFG-186; not a test, deliberately)
#
# Seven mutations were run against this file. Six go red: deleting the card
# (M4, all four tests); a POSITIVE assertion about another system, 「NIFoS 의
# 콘솔은 진압 지휘용입니다」 (M5 — the half of the register rule the loop had no
# rule for until critic #37); and four count shapes — a digit count 「12건」
# (M6a), and the Korean-numeral forms 「아홉 건」 (M6b) and 「여섯 개」 (M6c),
# which is the exact spelling of the WFG-178 defect; plus deleting the
# 「다시 쓴 문장은 빠져나갑니다」 limit (M7).
#
# Two of those six were GREEN when this file was first written, and finding
# that is the reason the count assertion has the shape it has: the digit-only
# version could not see 「여섯 개」 at all, and the first Korean-numeral version
# ended in ``\b``, which after a Hangul syllable can never match. A gate is not
# graded until its own mutations have been run.
#
# The one that stays GREEN (M8), and it is the one that matters: rewriting the
# draft from the descriptive register into the evaluative one — 「이 접근은 매우
# 독창적입니다」 — while keeping all three anchors, no other system, no count
# and the limit clause. Every assertion above passes and the card has become the
# self-assessment the whole design of it was meant to avoid. Nothing here reads
# tone, and a keyword list for 「독창」-type words would be a spelling ratchet
# with the same limit docs/withdrawn_claims.md section 4 measures for the
# registry. The cold read is what catches this one, so it is written down for
# the next reader rather than left implied.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# WFG-194: the same three items, on the two surfaces a judge actually meets
#
# WFG-182 shipped the card and closed correctly on its own scope. What it left,
# and said so in its own 「what this does NOT show」 block, is that a count of
# 창의 or 독창 answered 0 on `web/finals.html` and 0 on the booth script — the
# two surfaces a judge is in front of, where the Q&A bank is a reference the
# student reads from. Critics #41, #45 and #47 each re-measured the same zero.
#
# ⚠ These gates deliberately bind the ANCHOR PATHS and the register, not the
# word 창의. The row's own 「done when」 is a grep count, and a grep count is
# satisfied by writing the word — which would buy a keyword and not a mark. What
# has to survive is that a judge who presses on any of the three items lands on
# a file that exists and says what the surface said.
# ---------------------------------------------------------------------------

SCREEN = REPO / "web" / "finals.html"
TEMPLATE = REPO / "scripts" / "finals.template.html"
BOOTH = REPO / "docs" / "auto" / "DEMO_SCRIPT_5MIN.md"

#: The three anchors the screen block names, one per item. A subset of ANCHORS:
#: the screen's third item cites the registry and its checker, and sends a
#: reader who wants the measured limits to docs/creativity_card.md.
SCREEN_ANCHORS = (
    "docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md",
    "docs/real_roads_real_hazard.md",
    "docs/auto/withdrawn_claims.json",
    "scripts/check_withdrawn_claims.py",
)


def _screen_block() -> str:
    """The CREATIVE literals in the template, which is what the build emits.

    Read from the template rather than the built page because the template is
    the file a lap edits; `test_the_screen_ships_what_the_template_says` below
    is what binds the two together, so a hand-edited `web/finals.html` cannot
    satisfy this on its own.
    """
    text = TEMPLATE.read_text(encoding="utf-8")
    head = "const CREATIVE = ["
    assert head in text, (
        "the finals screen's 창의성 block is gone from the template. It is one "
        "of the two surfaces WFG-194 exists to reach; if it is being retired, "
        "retire this gate in the same commit and say why in the backlog row."
    )
    return text[text.index(head):].split("\n];", 1)[0]


def test_the_screen_block_rests_on_artifacts_that_exist() -> None:
    """Every path the screen shows a judge resolves in the tree."""
    block = _screen_block()
    named = [a for a in SCREEN_ANCHORS if a in block]
    assert len(named) == len(SCREEN_ANCHORS), (
        "the screen's 창의성 block no longer names all of "
        + ", ".join(SCREEN_ANCHORS) + ". A judge who presses on an item has "
        "nothing to open."
    )
    missing = [a for a in SCREEN_ANCHORS if not (REPO / a).exists()]
    assert not missing, (
        "the screen's 창의성 block points at files that are not in the tree: "
        + ", ".join(missing)
    )


def test_the_screen_ships_what_the_template_says() -> None:
    """`make finals` was run, so the built page carries the block too.

    Without this the template could gain the block and the page a judge opens
    on the booth laptop could stay silent for a whole window — which is the
    exact shape of the defect WFG-194 was filed about, one file upstream.
    """
    page = SCREEN.read_text(encoding="utf-8")
    assert "창의성 · 이 작품이 직접 만든 것" in page, (
        "web/finals.html does not carry the 창의성 block. Run `make finals` "
        "on the commit being pushed; the template alone is not the surface."
    )
    for anchor in SCREEN_ANCHORS:
        assert anchor in page, (
            f"the built screen is missing the anchor {anchor}; it is stale "
            "against the template. Run `make finals`."
        )


def test_the_screen_block_holds_the_same_register_as_the_card() -> None:
    """No novelty claim, no other system, no count - on the screen as well.

    The register is the card's whole design (docs/creativity_card.md), and a
    second surface making the same three claims in the evaluative register
    would undo it while the card's own gate stayed green. The three assertions
    are the card's, applied to the screen's literals.
    """
    block = _screen_block()
    assert not NOVELTY_RE.findall(block), (
        "the screen's 창의성 block has acquired a novelty claim: "
        + ", ".join(NOVELTY_RE.findall(block))
    )
    others = [s for s in OTHER_SYSTEMS if s in block]
    assert not others, (
        "the screen's 창의성 block names another system: " + ", ".join(others)
        + ". This block carries no source line, so a sentence about another "
        "system would be unsourced by construction (WC-009)."
    )
    counts = re.findall(r"\d\s*(?:" + _OBJECT_COUNTER + r")", block)
    counts += KO_COUNT_RE.findall(block)
    assert not counts, (
        "the screen's 창의성 block has acquired a count of this repository's "
        "own state: " + ", ".join(counts)
    )


def test_the_screen_block_says_the_judge_writes_the_verdict() -> None:
    """The closing limit is what keeps a wall of claims from reading as a boast."""
    page = SCREEN.read_text(encoding="utf-8")
    assert "심사위원의 판단입니다" in page, (
        "the screen's 창의성 block no longer says that whether these read as "
        "creative is the judge's call. Without it the block is the "
        "self-assessment the card's register exists to avoid."
    )


def test_the_booth_script_answers_the_creativity_row_out_loud() -> None:
    """One spoken sentence, inside §1, not only in a ⚠ block.

    A ⚠ block is Q&A prose and is not in the 300 seconds by
    `scripts/measure_demo_script_pace.py`'s counting rule, so a 창의성 answer
    that lives only there is said only if a judge happens to ask. 창의성 is
    scored whether or not it is asked.
    """
    text = BOOTH.read_text(encoding="utf-8")
    intro = text.split("### 도입", 1)[1].split("### 1막", 1)[0]
    spoken = "\n".join(l for l in intro.splitlines() if l.startswith("> "))
    assert "창의성" in spoken, (
        "the booth script's spoken 도입 no longer names 창의성. It is 20 points "
        "on both KCF tables and the 심사기준 names it first; a count of 창의 "
        "or 독창 answered 0 on this file for six days (WFG-194)."
    )
    assert "가구 단위 판정" in spoken, (
        "the spoken answer no longer says what the output object IS, which is "
        "the whole content of the first item; naming 창의성 without it is the "
        "keyword and not the claim."
    )


def test_the_booth_script_sends_the_judge_to_the_other_two_items() -> None:
    """The spoken line carries item 1; the screen carries all three."""
    text = BOOTH.read_text(encoding="utf-8")
    for needle in ("창의성 · 이 작품이 직접 만든 것",
                   "docs/creativity_card.md",
                   "Q29a"):
        assert needle in text, (
            f"the booth script no longer points at {needle}. The spoken line "
            "makes one of the three items; without the pointer the other two "
            "are unreachable from the script."
        )


def test_the_booth_script_forbids_the_evaluative_register() -> None:
    """M8, the mutation the card's own gate cannot catch, written down where
    the student reads it.

    Nothing in this suite reads tone, and `docs/creativity_card.md` records
    that rewriting the descriptive register into the evaluative one keeps every
    assertion green. The one control available for a sentence a human speaks is
    to tell the human, on the page they read before speaking.
    """
    text = BOOTH.read_text(encoding="utf-8")
    assert "독창적입니다" in text and "말하지 마십시오" in text, (
        "the booth script no longer tells the student not to call the work "
        "독창적. That prohibition is the only control this repository has over "
        "the evaluative register in a spoken sentence (docs/creativity_card.md, "
        "mutation M8)."
    )


def test_the_screen_states_what_the_withdrawal_registry_does_not_reach() -> None:
    """WFG-194's reviewer: the register gates were ported to the screen and this
    one was not, on the item whose whole content is 「we are honest about being
    wrong」.

    Q29a is permitted to offer the withdrawn-claim registry as a method only
    because its 없는 것 block forces the student to speak the limits, and
    `docs/withdrawn_claims.md` §4 is titled 「이 게이트가 하지 않는 것 — 부스에서
    근거로 들지 마십시오」. The screen's first wording said the checker reads the
    registry back across 「추적 문서 전체」 / 「the tracked documents」, full stop:
    an unqualified scope claim on a booth surface, wider than the measured reach
    (the loop's own record pages are exempt by design, and `.bib` and `.py` are
    out of reach - WFG-155, WFG-168).

    The limit is stated qualitatively rather than as a fraction on purpose: the
    screen block states no quantity at all, a count of this repository's own
    state is the defect with the shortest fuse here (WFG-117), and the
    denominator moves every time a document is added.
    """
    block = _screen_block()
    for needle_ko, needle_en, what in (
        (".md", ".md", "which file types the checker actually reads"),
        ("기록 문서", "record pages", "that the loop's own record class is exempt"),
        ("다시 쓴 문장", "reworded claim", "that a reworded claim escapes"),
    ):
        assert needle_ko in block and needle_en in block, (
            "the screen's withdrawn-claim item no longer says " + what
            + f" (looking for {needle_ko!r} and {needle_en!r}). Without it the "
            "screen claims a wider reach than docs/withdrawn_claims.md §4 "
            "measured, on the one item that is about not overclaiming."
        )
    page = SCREEN.read_text(encoding="utf-8")
    assert "다시 쓴 문장" in page, (
        "the built screen does not carry the limit; run `make finals`.")
