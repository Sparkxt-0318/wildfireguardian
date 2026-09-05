"""The judge-facing detection documents may not claim the satellite/telephone ordering,
and — since 2026-09-04 (WFG-063, second half of this file) — may not claim 사람 신고
primacy either. Two withdrawn claims of one measurement, one pragma discipline.

WFG-053, from critic #6's F27. The measurement behind `docs/detection_floor.md` reports
how long after a fire's **recorded occurrence time** the first GK2A infrared anomaly
appeared: +22, +34 and +64 minutes. For one window this repository turned that into
「위성은 사람보다 느렸습니다」 on the one finished booth card, in the design document's
verdict, and inside a **T0** answer the student is told to memorise, while
`paper/manuscript.md` §4.7 — written the same night — said the measurement cannot support
it. Both were green. Every gate this repository owns reads a *value*; the ordering claim
is a *sentence*, and no value moves when it is written or withdrawn.

Why the paper is the correct half, from committed artifacts alone:
`docs/data_provenance/fire_manifest.json` marks the field the delays are measured from
(`start`) as `start/end/reported_ha are provenance only` for all four detection fires, and
the only place any entry describes that field it calls it the **ignition**
(`first hit … may lag ignition`; for `yeongdeok_2025`, `first hit (2025-03-25) lags the
2025-03-22 ignition by days`, where `2025-03-22` is that same `start`). No entry contains
the word 신고. No committed artifact records a 신고접수시각 for any of these fires, so the
human's clock was never measured and neither direction of the comparison can be stated.

So this file gates the sentence, not the number. It is deliberately narrow:

* it scans only the documents a judge actually meets, listed in ``GUARDED``;
* it bans the ordering **assertion**, in the spellings this repository actually used;
* a line that names the claim in order to withdraw or forbid it carries the repository's
  own ``<!-- forbidden-ok: ... -->`` line pragma (``scripts/check_forbidden.py``), which is
  the same escape hatch every other claim rule here uses, and it is per-line — there is no
  whole-file exemption, on purpose.

WHAT THIS FILE DOES NOT DO. Read this before citing it as protection, because the lap
that wrote it oversold it and its reviewer proved the point twice.

**This is a string tripwire, not a claim detector.** It catches the spellings listed in
``BANNED``. It does not understand the sentence. The independent reviewer of the lap that
wrote it escaped it twice with two-word edits, and after both fixes it ran twelve mutations
of its own and reported that most still escape. Verified-uncaught shapes, recorded here so
nobody mistakes a green run for a guarantee:

* a line-wrap split of the exact banned sentence — the scan is per line, by design (see
  ``violations``), so 「위성은 사람보다\n늦었습니다」 passes;
* a synonym for the subject: 「위성은 **인간**보다 느렸습니다」, 「위성은 **목격자**보다
  뒤에」, 「**119 신고 전화**보다 22분 늦게」;
* the same claim with the subjects reversed: 「사람의 신고가 위성보다 22분 빨랐습니다」,
  「사람이 먼저였고 위성이 나중이었습니다」, 「전화가 먼저 울렸고, 위성은 그 뒤였습니다」;
* the claim without the comparison word at all: 「사람이 신고한 뒤에 울렸습니다」;
* any of it in English, anywhere — ``BANNED`` is Korean-only and stays that way.
  Since 2026-09-04 (WFG-070) the English spelling of both withdrawn claims has its
  own rule at the foot of this file, ``english_ordering_violations``, over four
  English surfaces. It is a separate instrument with separately measured limits
  (8 of 16 on a set graded after freezing), not an extension of this one, and it
  deliberately does not cover ``paper/manuscript.md``.

So: a determined or merely differently-worded author walks past this file. What it does
buy is that the **exact sentences this repository actually shipped** cannot come back by
copy-paste, and that the three documents keep their provenance text. Treat it as a
ratchet against regression-by-copying, not as a guarantee the claim cannot reappear. The
real fix is a registry of withdrawn claims checkable from any document, filed as WFG-062,
and until that lands the load-bearing protection for this claim is a human reading the
card, not this file.

It also does not prove the delays are correct and does not check any figure against the
registry (that is ``tests/test_detection_floor_card.py``).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

#: The Korean documents a judge physically meets: the booth card, the design document
#: behind it, and the Q&A bank the student memorises. These are checked by banned shape.
GUARDED: tuple[str, ...] = (
    "docs/detection_floor.md",
    "docs/auto/finals/DETECTION_FLOOR_CARD.md",
    "docs/auto/JUDGE_QA.md",
)

#: `paper/manuscript.md` is guarded differently, and the difference is deliberate.
#: It is the half of the repository that got this right first, so what needs protecting
#: there is the WITHDRAWAL, not the absence of a Korean phrase. Banning the English claim
#: shapes outright would fire on the paper's own careful sentences — 「a satellite arriving
#: after the telephone, but no artifact supports that」 and 「Whether that is ahead of or
#: behind the emergency call, this measurement cannot say」 — and licensing those would mean
#: putting HTML pragmas into a manuscript that is converted to .docx, in a file the paper
#: routine owns. So the anchor is positive instead.
#:
#: ⚠ AND IT IS WEAK, SAID PLAINLY BECAUSE THE LAP THAT ADDED IT CALLED IT A REGRESSION
#: ANCHOR AGAINST "HARMONISING BACK", WHICH IT IS NOT. It detects DELETION of the
#: withdrawal, not CONTRADICTION of it: a lap can paste the card's old ordering sentence
#: into §4.7 and keep both phrases, and this passes. Gating English claim shapes properly
#: belongs with the general registry of withdrawn claims, WFG-062.
MANUSCRIPT_ANCHORS: tuple[str, ...] = (
    "recorded occurrence time",
    "this measurement cannot say",
)

#: Documents that must carry the narrow reading in full, i.e. must name the reference
#: clock AND the manifest's own provenance sentence. `JUDGE_QA.md` is a Q&A bank, so it
#: carries these in Q10c rather than in a caveat block, which is why it is in the same
#: list: the point is that the student can reach the provenance from the page they hold.
MUST_STATE_THE_PROVENANCE: tuple[str, ...] = (
    "docs/detection_floor.md",
    "docs/auto/finals/DETECTION_FLOOR_CARD.md",
    "docs/auto/JUDGE_QA.md",
)

#: (pattern, token, why). `token` is what a `forbidden-ok:` pragma must name to allow the
#: line — the same per-token discipline as `scripts/check_forbidden.py`, so a pragma
#: added for one claim shape cannot silently license another.
#:
#: ⚠ VALIDATED BOTH DIRECTIONS before landing, the bar `scripts/check_forbidden.py`
#: sets for a `claim` rule. Against the three guarded documents as this row left them:
#: 0 unpragmaed hits. Against the withdrawn spellings they exist to stop — the card's old
#: front sentence, §9's old title and verdict, §4's 「신고 대비」 table label, Q10's old
#: T0 sentence and Q10a's old closing line: all caught. The negative direction is
#: `test_a_line_that_withdraws_the_claim_is_not_a_violation` plus the mutation tests at
#: the foot of this file, which put each withdrawn sentence back and require a failure.
#:
#: ⚠ THE FIRST DRAFT OF THIS LIST WAS HOLLOW AND THE REVIEWER PROVED IT IN ONE EDIT.
#: The 사람보다 rule read `느[렸리]` — the exact verb the card happened to use. The
#: independent reviewer of this lap put 「위성은 사람보다 **늦었**습니다」 on the card's
#: front line, a synonym any writer might reach for first, and the gate passed. That is
#: MEMO 2026-09-04's anti-pattern in its purest form: mutation-testing a tripwire with the
#: mutations its own author chose. The verb classes below are widened accordingly, and
#: 늦었 is now a mutation case at the foot of this file, credited where it came from.
#:
#: ⚠ AND THE WIDENED VERSION WAS BROKEN AGAIN, BY THE SAME REVIEWER, IN ONE MORE EDIT.
#: The second draft read `사람보다\s*(?:더\s*)?(?:느…|늦…)`, i.e. it allowed only a space
#: or 「더」 between the noun and the verb. The reviewer wrote 「위성은 사람보다 **22분**
#: 늦었습니다」 — the claim with its magnitude in the middle, which is the more natural
#: sentence, not the less — and the gate passed a second time. Hence `[^\n]{0,24}?`: any
#: short run of text between the comparison and the verb. Two escapes from two attempts by
#: one reviewer is the measurement that matters about this gate, and it is why WFG-062 (a
#: general registry of withdrawn claims) is filed rather than treating this file as done.
BANNED: tuple[tuple[str, str, str], ...] = (
    (r"사람보다[^\n]{0,24}?(?:느[렸리린]|늦[었게은는]|뒤[에였])", "사람보다 늦",
     "the card's withdrawn front sentence 「위성은 사람보다 느렸습니다」, in any verb"),
    (r"사람보다[^\n]{0,24}?(?:빠[르른릅]|이르|먼저|앞[서선])", "사람보다 빠",
     "the OPPOSITE ordering claim. Neither direction is available: the human's clock "
     "was never measured, so 「위성이 사람보다 빨랐다」 is exactly as unsupported"),
    (r"신고\s*대비", "신고 대비",
     "the delays labelled as report-relative; they are recorded-occurrence-relative"),
    (r"신고보다", "신고보다",
     "any delay or step stated relative to a 신고 time that was never measured"),
    (r"기준\s*시각은\s*(?:「\s*)?신고", "기준 시각은 신고",
     "§1's withdrawn heading 「기준 시각은 신고 시각입니다」"),
    (r"신고\s*시각\s*(?:대비|기준)", "신고 시각 대비",
     "the same label one synonym over"),
)

#: `scripts/check_forbidden.py`'s pragma, deliberately the same one. A rule with its own
#: private escape hatch is a rule people learn to route around.
PRAGMA = re.compile(r"(?:#|//|<!--)\s*forbidden-ok:\s*(.*?)\s*(?:-->|$)")


def _pragma_tokens(line: str) -> set[str]:
    out: set[str] = set()
    for m in PRAGMA.finditer(line):
        out |= {t.strip() for t in m.group(1).split(",") if t.strip()}
    return out


def violations(text: str) -> list[tuple[int, str, str]]:
    """(line number, token, line) for every banned shape not licensed by a pragma.

    The pragma may sit on the offending line or the line directly above it, matching
    `scripts/check_forbidden.py` — a caveat is naturally written above the thing it
    caveats, and requiring a suffix on the line itself pushes authors to inline noise.
    """
    lines = text.splitlines()
    found = []
    for i, line in enumerate(lines):
        allowed = _pragma_tokens(line)
        if i:
            allowed |= _pragma_tokens(lines[i - 1])
        for pattern, token, _why in BANNED:
            if re.search(pattern, line) and token not in allowed:
                found.append((i + 1, token, line.strip()))
    return found


@pytest.mark.parametrize("rel", GUARDED)
def test_no_judge_facing_document_claims_the_ordering(rel: str):
    """The load-bearing test. A judge reads these four; they must agree with each other."""
    path = REPO / rel
    assert path.is_file(), f"{rel} is missing — the guard list is stale"
    hits = violations(path.read_text(encoding="utf-8"))
    assert not hits, (
        f"{rel} asserts the satellite/telephone ordering, which no committed artifact "
        f"supports (WFG-053, NH-019):\n"
        + "\n".join(f"  {rel}:{n}  [{tok}]  {line}" for n, tok, line in hits)
        + "\n\nNo 신고접수시각 exists in this repository, so neither direction can be "
          "stated. Say the size floor instead: a 2 km pixel does not resolve a fire "
          "below roughly a hectare, which is true under either reading. If you are "
          "naming the claim in order to withdraw it, put "
          "`<!-- forbidden-ok: <token> -->` on the line or the line above."
    )


@pytest.mark.parametrize("rel", MUST_STATE_THE_PROVENANCE)
def test_the_reference_clock_is_named_and_sourced(rel: str):
    """Removing the wrong sentence is only half the fix; the right one has to be there.

    Without this, a lap could satisfy the test above by deleting the caveat altogether
    and leaving a judge with three bare delays and no idea what they are delays from.
    """
    text = (REPO / rel).read_text(encoding="utf-8")
    assert "기록된 발생일시" in text or "recorded occurrence time" in text, (
        f"{rel} states delays without naming the clock they are measured from"
    )
    assert "provenance only" in text, (
        f"{rel} names the clock but not the manifest sentence that makes it unsourced; "
        "quote `start/end/reported_ha are provenance only` so a judge can check it"
    )


def test_the_manifest_still_says_what_this_gate_rests_on():
    """The premise, re-derived from the artifact rather than trusted.

    Every sentence above depends on two facts about
    `docs/data_provenance/fire_manifest.json`. If a future manifest gains a real report
    time, this test fails and the narrowing can be revisited on evidence — which is the
    outcome NH-019 is asking the author for.
    """
    text = (REPO / "docs/data_provenance/fire_manifest.json").read_text(encoding="utf-8")
    assert text.count("start/end/reported_ha are provenance only") >= 4, (
        "the manifest no longer marks the reference field as provenance-only"
    )
    assert "신고" not in text, (
        "the manifest now contains report-time language — re-read NH-019 before "
        "trusting this gate; the ordering may now be statable"
    )


def test_a_line_that_withdraws_the_claim_is_not_a_violation():
    """The negative direction: a detector that always fires is as useless as one that
    never does (`docs/region_literals.md` §5). Withdrawal prose must survive."""
    withdrawn = (
        "<!-- forbidden-ok: 사람보다 늦 -->\n"
        "이전 판은 「위성은 사람보다 느렸습니다」라고 적었고, 철회했습니다.\n"
    )
    assert not violations(withdrawn)
    # ⚠ The last two lines are NOT legitimate prose — they are what WFG-063 withdrew,
    # and `primacy_violations` below fires on both. They stay here because this test is
    # about the ORDERING gate's blast radius: a sentence about primacy or about the 99 %
    # statistic says nothing about who rang first, so the ordering gate must not claim
    # the catch. Two gates, two claims, and neither borrows the other's authority.
    ordinary = (
        "위성 트리거는 기록된 발생일시로부터 +22분 뒤였습니다.\n"
        "한국 산불 신고의 99 %가 목격 신고입니다.\n"
        "사람 신고를 일차 소스로 설계해야 합니다.\n"
    )
    assert not violations(ordinary), "the ordering gate fires outside its own claim"
    assert len(primacy_violations(ordinary)) == 2, (
        "the primacy gate must be the one that catches those last two lines"
    )


@pytest.mark.parametrize("phrase", MANUSCRIPT_ANCHORS)
def test_the_manuscript_keeps_its_withdrawal(phrase: str):
    """`paper/manuscript.md` got this right first; it must not be harmonised backwards.

    A later lap "making the paper agree with the card" is a real failure mode — it is how
    this repository ended up with two answers to one question in the first place, only in
    the other direction. If these sentences leave the manuscript, that is the regression.
    """
    text = (REPO / "paper/manuscript.md").read_text(encoding="utf-8")
    assert phrase in text, (
        f"paper/manuscript.md no longer contains {phrase!r}. §4.7 is the only place that "
        "states the reference clock's provenance in full; if it is being rewritten, the "
        "replacement must still refuse the ordering claim (WFG-053, NH-019)."
    )


@pytest.mark.parametrize(
    "sentence",
    [
        # --- the exact strings this repository shipped, before WFG-053 ---
        "**위성은 사람보다 느렸습니다.** 검증 가능했던 화재 3건에서",
        "어느 쪽으로 읽어도 위성이 사람보다 앞서지 않습니다.",
        "| 화재 | GK2A 지연 (신고 대비) | 레지스트리 키 |",
        "위성 트리거는 신고보다 각각 +22분 · +34분 · +64분 뒤에 울렸을 것입니다",
        "## ⚠ 1. 가장 중요한 단서 — 기준 시각은 신고 시각입니다",
        "GK2A 기반 트리거는 모든 경우에 사람의 신고보다 뒤에 울렸을 것입니다",
        # --- mutations this test's author did NOT choose ---
        # Written onto the card's front line by this lap's independent reviewer, which
        # the first version of this gate passed. MEMO 2026-09-04: take at least one
        # mutation from someone who did not write the test.
        "**위성은 사람보다 늦었습니다.** 2 km 화소는 대략",
        # the same claim in the other direction, which is equally unsupported
        "위성이 사람보다 먼저 불을 봤습니다",
        # the reviewer's SECOND escape: the magnitude sits between noun and verb, which
        # is the more natural sentence rather than the less
        "**위성은 사람보다 22분 늦었습니다.** 2 km 화소는 대략",
        "위성 트리거가 사람보다 22-64분 뒤에 울렸습니다",
        "GK2A 는 신고 시각 대비 22분이었습니다",
    ],
)
def test_each_withdrawn_spelling_is_caught(sentence: str):
    """Mutation, one per spelling this repository shipped or a reviewer reached for.

    Reinstating any of them anywhere in a guarded document must fail.
    """
    assert violations(sentence), f"the gate does not catch: {sentence}"


# ---------------------------------------------------------------------------
# WFG-063 · the SECOND withdrawn claim of the same measurement: 사람 신고 primacy
# ---------------------------------------------------------------------------
#
# The ordering claim above ("the satellite rang after the telephone") was withdrawn by
# WFG-053. Withdrawing it removed the ground under a *different* sentence that had been
# riding on it — 「사람 신고가 일차」 — and §10 reached for 「신고의 99 %가 목격 신고」
# to replace it. That statistic is an unregistered year-to-date interim (경향신문,
# 2023-04-28) and `docs/detection_floor.md` §10 now forbids it as support. What was left
# is the size floor alone, and the size floor **rules the satellite out; it does not rule
# the human in**. So for one window this repository held two T0 answers to one question:
# `JUDGE_QA.md` Q10 told the student to say 「신고 우선」 on that ground, and Q10d — added
# by critic #7 as a guard — listed the same sentence under 「말하면 안 되는 것」.
#
# The claim shape banned here is therefore **primacy**, not ordering: any judge-facing
# document asserting that the human channel is the primary trigger source, and any use of
# the 99 % statistic as support for it. The permitted sentence is the one the finals
# screen already carried and which this row copied into the other four documents:
#
#     이 측정이 말하는 것은 위성을 일차로 둘 수 없다는 것까지이며,
#     어떤 소스가 일차여야 하는지는 재지 않았습니다.
#
# WHAT THIS DOES NOT DO — the same disclaimer as the ordering gate above, and for the
# same reason. This is a string tripwire over the spellings this repository actually
# shipped. It does not read Korean. 「사람의 전화가 먼저 와야 합니다」, 「최초 인지는
# 주민이 담당합니다」 walk straight past it. An English rendering is caught by
# `english_ordering_violations` at the foot of this file since WFG-070, on four English
# surfaces and with its own measured escapes. The general fix is
# a registry of withdrawn claims any document can be checked against (WFG-062); until
# that lands, this is a ratchet against regression-by-copying, not a proof.
#
# ⚠ IT ALSO GUARDS THE BUILT SCREEN, WHICH THE ORDERING GATE DOES NOT. Critic #8's root
# objection was that `web/finals.html` had become the most correct document in the
# repository while every gate pointed at the markdown behind it. The screen is the source
# of the permitted sentence, so it is in both lists here: if a later lap "harmonises" the
# screen back to the card, this fails.

#: Judge-facing surfaces, including the two the ordering gate cannot see.
PRIMACY_GUARDED: tuple[str, ...] = (
    "docs/detection_floor.md",
    "docs/auto/finals/DETECTION_FLOOR_CARD.md",
    "docs/auto/JUDGE_QA.md",
    "scripts/finals.template.html",
    "web/finals.html",
)

#: The permitted sentence, in whitespace-normalised form (these documents hard-wrap, and
#: the screen carries it as one long JavaScript string literal).
PERMITTED_CLAUSE = "어떤 소스가 일차여야 하는지는 재지 않았습니다"

#: (pattern, token, why). Same pragma discipline as `BANNED`.
#:
#: ⚠ VALIDATED BOTH DIRECTIONS. Against the five guarded surfaces as this row left them:
#: 0 unpragmaed hits. Against the spellings they exist to stop — the card's old front
#: sentence, §10's old rank-1 row and 설계 함의, the card's old rank table and Q10's old
#: T0 clause — all caught, in `test_each_withdrawn_primacy_spelling_is_caught`.
#:
#: ⚠ THREE OF THE FIRST DRAFT'S NINE MUTATIONS ESCAPED IT, AND THEY ARE RECORDED HERE
#: BECAUSE THE ESCAPES ARE THE INTERESTING PART. `사람 신고가 일차**이고` escaped because
#: the emphasis markers sit between the noun and its verb — the same class of miss the
#: ordering gate above was broken by twice, reached for a third time by the same author.
#: The **rank-1 table row** escaped because the rank cell comes BEFORE 사람 신고 and the
#: 근거 cell puts sixty characters between them, so no proximity rule over 신고 → 일차 can
#: see it; a table row needs its own rule. And 「트리거의 일차 소스는 사람 신고입니다」
#: escaped because the claim reads right-to-left — the source names the channel rather
#: than the channel claiming the source. Proximity in one direction is half a rule.
BANNED_PRIMACY: tuple[tuple[str, str, str], ...] = (
    (r"신고[^\n]{0,20}?[*\s]{0,4}일차[*\s]{0,4}(?:로|이|입니|였|소스|트리거)", "신고 일차",
     "the card's withdrawn 「사람 신고가 일차」 and §10's 「사람 신고를 일차로 가정」. "
     "The size floor excludes the satellite; it elects nobody"),
    (r"일차[^\n]{0,20}?(?:소스|트리거|자리)[^\n]{0,24}?신고", "일차는 신고",
     "the same claim right-to-left: 「트리거의 일차 소스는 사람 신고입니다」"),
    (r"신고\s*우선", "신고 우선",
     "Q10's withdrawn T0 clause 「트리거 설계가 신고 우선, 위성 확인입니다」"),
    (r"신고[^\n]{0,20}?[*\s]{0,4}(?:1|１|일)\s*순위", "신고 1순위",
     "the same claim written as a rank, which is what §10's table was"),
    (r"^\|\s*\**\s*[1１]\s*\**\s*\|[^\n]*사람\s*신고", "신고 1순위",
     "and the rank as a table row, where the rank cell precedes the channel: this is the "
     "shape both §10 and the booth card actually shipped"),
    (r"99\s*%[^\n]{0,12}?목격\s*신고", "99 % 목격 신고",
     "the unregistered year-to-date interim (경향신문 2023-04-28) that was reached for "
     "as the replacement ground; forbidden as support by detection_floor.md §10. §0 may "
     "keep it as background WITH its source, which is what the pragma there licenses"),
)


def primacy_violations(text: str) -> list[tuple[int, str, str]]:
    """(line number, token, line) for every banned primacy shape not licensed."""
    lines = text.splitlines()
    found = []
    for i, line in enumerate(lines):
        allowed = _pragma_tokens(line)
        if i:
            allowed |= _pragma_tokens(lines[i - 1])
        for pattern, token, _why in BANNED_PRIMACY:
            if re.search(pattern, line) and token not in allowed:
                found.append((i + 1, token, line.strip()))
    return found


@pytest.mark.parametrize("rel", PRIMACY_GUARDED)
def test_no_judge_facing_surface_claims_human_report_primacy(rel: str):
    """WFG-063. Five surfaces, one sentence; the screen is one of the five."""
    path = REPO / rel
    assert path.is_file(), f"{rel} is missing — the primacy guard list is stale"
    hits = primacy_violations(path.read_text(encoding="utf-8"))
    assert not hits, (
        f"{rel} asserts that 사람 신고 is the primary trigger source, or uses the 99 % "
        f"statistic to support it. Neither is available (WFG-063, NH-019):\n"
        + "\n".join(f"  {rel}:{n}  [{tok}]  {line}" for n, tok, line in hits)
        + "\n\nThe size floor rules the SATELLITE OUT; it does not rule the HUMAN IN, and "
          "no committed artifact measures the human channel at all. Say instead: "
          f"「이 측정이 말하는 것은 위성을 일차로 둘 수 없다는 것까지이며, {PERMITTED_CLAUSE}.」 "
          "If you are naming the claim in order to withdraw or forbid it, put "
          "`<!-- forbidden-ok: <token> -->` on the line or the line above."
    )


@pytest.mark.parametrize("rel", PRIMACY_GUARDED)
def test_every_surface_carries_the_permitted_sentence(rel: str):
    """Deleting the claim is half the fix; the narrowed sentence has to be there.

    Whitespace-normalised, because four of the five hard-wrap it and the fifth carries it
    inside a JavaScript string. Requiring the same clause in all five is what makes the
    disagreement critic #8 named — screen right, markdown wrong — a test failure rather
    than something only a reader notices.
    """
    text = (REPO / rel).read_text(encoding="utf-8")
    assert PERMITTED_CLAUSE in " ".join(text.split()), (
        f"{rel} no longer says what the measurement does NOT settle. Add "
        f"「{PERMITTED_CLAUSE}」 — the wording `web/finals.html` has carried since "
        "2026-09-04 and which WFG-063 copied to the other four."
    )


def test_a_line_that_forbids_primacy_is_not_a_violation():
    """Negative direction: Q10d and §310 exist to name the claim and refuse it."""
    withdrawn = (
        "<!-- forbidden-ok: 신고 일차, 99 % 목격 신고 -->\n"
        "「사람 신고를 일차로 두어야 합니다」와 「신고의 99 %가 목격 신고이므로」는 "
        "말하지 마십시오.\n"
    )
    assert not primacy_violations(withdrawn)
    ordinary = (
        "이 측정이 말하는 것은 위성을 일차로 둘 수 없다는 것까지이며, "
        "어떤 소스가 일차여야 하는지는 재지 않았습니다.\n"
        "신고접수시각을 담은 산출물이 없습니다.\n"
        "정지궤도 위성을 일차 트리거로 둘 수 없습니다.\n"
    )
    assert not primacy_violations(ordinary), (
        "the primacy gate fires on the sentence it exists to permit"
    )


@pytest.mark.parametrize(
    "sentence",
    [
        # --- the exact strings this repository shipped, before WFG-063 ---
        "제곱미터입니다. 그래서 이 시스템의 트리거는 **사람 신고가 일차**이고 위성은",
        "**설계 함의:** 트리거 인터페이스는 **사람 신고를 일차로 가정**하고 위성을",
        "| **1** | **사람 신고** (119·산림청·마을 무전) | 정지궤도 위성은 크기 바닥"
        "(0.1–1 ha) 아래에서 구조적으로 아무것도 보지 못합니다. **일차 소스로 설계해야 합니다** |",
        "아카이브보다 앞섭니다. 그래서 트리거 설계가 신고 우선, 위성 확인입니다 — 근거는 순서가",
        "아니라 크기 바닥과 「신고의 99 %가 목격 신고」라는 통계입니다.",
        "| 1 | **사람 신고** (119·산림청·마을 무전) | 위성은 크기 바닥 아래를 구조적으로 보지 못함 |",
        # --- spellings nobody here shipped, reached for the way a rewriter would ---
        "사람 신고를 1순위 소스로 둡니다",
        "트리거의 일차 소스는 사람 신고입니다",
        "저희는 신고 우선 설계를 택했습니다",
    ],
)
def test_each_withdrawn_primacy_spelling_is_caught(sentence: str):
    assert primacy_violations(sentence), f"the primacy gate does not catch: {sentence}"


# ---------------------------------------------------------------------------
# WFG-063, second pass · the rule that does NOT read spellings
# ---------------------------------------------------------------------------
#
# THIS SECTION EXISTS BECAUSE THE INDEPENDENT REVIEWER BLOCKED THE FIRST ONE, AND IT
# WAS RIGHT. The lap above wrote `BANNED_PRIMACY`, validated it against nine mutations
# **its own author wrote in the same session as the patterns**, watched three of them
# escape, widened the patterns, and then described the result as a guarantee. The
# reviewer wrote twenty primacy sentences it had not seen and **nineteen escaped**,
# among them 「사람 신고가 일차 채널입니다」 (one token off a sentence this lap deleted),
# 「사람 신고를 1차 트리거로 둡니다」 (일차/1차 are interchangeable) and the same rank
# table rewritten with a 「1순위」 header cell. `mandela` names that exactly: a scorer
# grading buckets it drew itself is not evidence, and "write the mutations first" does
# not fix it — only a mutation set the pattern author did not write is external ground
# truth.
#
# The repository already owned the answer, one file over and scoped to one file:
# `tests/test_finals_screen.py::test_every_trigger_priority_sentence_on_the_screen_is_a_negation`
# asserts a STRUCTURAL property instead of a list of strings — any sentence naming both
# a **priority word** and a **trigger-source noun** must also carry a **negation** —
# which holds whatever words the next author reaches for. Its own docstring says
# 「WFG-062 is the row that generalises this beyond one file」. This lap should have
# pointed it at the four markdown surfaces instead of writing a second spelling list;
# it does that here.
#
# WHY IT IS A SEPARATE IMPLEMENTATION AND NOT AN IMPORT. The screen version scans the
# template **line by line**, which is correct there because the template holds each
# rendered sentence in one long JavaScript string literal. These documents hard-wrap at
# about ninety columns, so a line-level scan reports the permitted sentence itself as an
# offender — 「…위성을 일차로 둘 수 없다는 것까지이며, 어떤」 carries the priority word and
# the noun while its 「재지 않았습니다」 sits on the next line. Measured before this was
# written: line-level over these five files gives 24 hits, of which 24 are the wrap.
# So the unit here is a **sentence**, rebuilt from the block (paragraph, list item,
# blockquote run, or one table cell) that contains it.
#
# WHAT IT STILL DOES NOT DO, stated because the first pass overclaimed and that is the
# defect the reviewer actually blocked on:
#
# * a primacy claim written with no priority word at all — 「저희 트리거는 전화에서
#   시작합니다」 — carries none of the three signals and passes;
# * an assertion that merely CONTAINS a negation elsewhere in the same sentence passes,
#   because the rule counts morphemes, not scope: 「위성은 볼 수 없으므로 사람 신고를
#   일차로 둡니다」 is caught by `BANNED_PRIMACY` above but not by this;
# * English is not read by THIS rule. Since WFG-070 it is read by
#   `english_ordering_violations` at the foot of this file, which is a different
#   rule over different files and does not make this one bilingual;
# * and neither rule reads meaning. Together they are a **ratchet**, and the honest
#   summary is: `BANNED_PRIMACY` stops the six sentences this repository shipped coming
#   back by copy-paste, and this one stops a large class of rewordings of them. Neither
#   is a proof, no sentence in a judge-facing document should claim they are, and the
#   real fix is still WFG-062.

#: Every surface that discusses this measurement, including the two the first pass
#: missed: the screen's companion document, and the session report that carries the
#: withdrawn table as a record.
PRIORITY_GUARDED: tuple[str, ...] = PRIMACY_GUARDED + (
    "docs/finals_screen_v2.md",
    "docs/SESSION19_REPORT.md",
)

#: Copied deliberately from `tests/test_finals_screen.py` rather than imported, so the
#: two lists can be compared side by side; `test_the_two_word_lists_have_not_drifted`
#: below fails if they diverge.
PRIORITY_WORDS = ("일차", "1차", "１차", "우선", "먼저", "앞서", "앞섭", "앞선",
                  "최초", "주된", "주 소스", "순위")
SOURCE_NOUNS = ("신고", "위성", "GK2A", "FIRMS", "감시카메라", "무전")
#: Negation **morphemes**, not conjugations. 「않습니다 / 않고 / 않은 / 않았」 all share
#: 「않」; listing conjugations is how the first pass got corpus-fitted.
NEGATION_MORPHEMES = ("않", "없", "아니", "못", "말하지")

#: The pragma token for a line that names a priority claim in order to withdraw, forbid,
#: quote or record it. Deliberately its own token: a `신고 일차` pragma licensing a
#: spelling must not silently license a structural claim as well.
PRIORITY_PRAGMA = "trigger-priority"

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _blocks(text: str) -> list[tuple[str, list[int], bool]]:
    """(joined text, source line numbers) per markdown block.

    A block is a run of consecutive prose lines; a blank line, a heading, a rule or a
    fence ends one. A list item and a blockquote run each start a new block, so a caveat
    bullet cannot borrow the negation of the bullet above it.

    A **table row is one unit and is never sentence-split**, and both halves of that are
    load-bearing. Whole-row, because the claim can be spread across cells: the reviewer's
    escape `| 1순위 | **사람 신고** | 크기 바닥 |` puts the priority word in the rank cell
    and the source noun in the next one, so per-cell scanning sees neither together. And
    un-split, because a row's cells are fragments rather than sentences — splitting
    `| 감시카메라 | 최초 발견 0건(경북, 2년). 열감지가 없는 한 트리거 소스가 아님 |` on the
    full stop separates the negation from the words that need it, and the row is a single
    statement about a single source.

    Returns (text, line numbers, whether to split it into sentences).
    """
    lines = text.splitlines()
    out: list[tuple[str, list[int], bool]] = []
    buf: list[str] = []
    bufl: list[int] = []

    def flush() -> None:
        nonlocal buf, bufl
        if buf:
            out.append((" ".join(buf), list(bufl), True))
            buf, bufl = [], []

    in_quote = False
    for i, raw in enumerate(lines, 1):
        s = raw.strip()
        if not s or s.startswith(("#", "---", "```", "|---")):
            flush()
            in_quote = False
            continue
        if s.startswith("|"):
            flush()
            in_quote = False
            out.append((" ".join(c.strip() for c in s.strip("|").split("|")), [i], False))
            continue
        quote = s.startswith(">")
        if quote:
            s = s.lstrip("> ").strip()
            if not s:
                flush()
                in_quote = True
                continue
            if not in_quote:
                flush()
        else:
            if in_quote:
                flush()
            if s.startswith(("- ", "* ")) or re.match(r"^\d+\. ", s):
                flush()
        in_quote = quote
        buf.append(s)
        bufl.append(i)
    flush()
    return out


def priority_violations(text: str) -> list[tuple[int, str]]:
    """(first line number, sentence) for every priority sentence that is not a negation."""
    lines = text.splitlines()
    found: list[tuple[int, str]] = []
    for block, nums, split in _blocks(text):
        licensed = set()
        for n in nums:
            for j in (n - 1, n):
                if 1 <= j <= len(lines):
                    licensed |= _pragma_tokens(lines[j - 1])
        if PRIORITY_PRAGMA in licensed:
            continue
        for sentence in (_SENTENCE_SPLIT.split(block) if split else [block]):
            sentence = sentence.strip()
            if not sentence:
                continue
            if not any(w in sentence for w in PRIORITY_WORDS):
                continue
            if not any(s in sentence for s in SOURCE_NOUNS):
                continue
            if any(n in sentence for n in NEGATION_MORPHEMES):
                continue
            found.append((nums[0], sentence))
    return found


@pytest.mark.parametrize("rel", PRIORITY_GUARDED)
def test_every_trigger_priority_sentence_is_a_negation(rel: str):
    """The load-bearing gate of the second pass, over seven surfaces."""
    path = REPO / rel
    assert path.is_file(), f"{rel} is missing — the priority guard list is stale"
    hits = priority_violations(path.read_text(encoding="utf-8"))
    assert not hits, (
        f"{rel} contains a sentence naming both a trigger priority and a trigger source "
        f"without a negation. This repository measured nothing about the human channel, "
        f"so every such sentence must say what is NOT true (WFG-063, NH-019):\n"
        + "\n".join(f"  {rel}:{n}  {s[:120]}" for n, s in hits)
        + f"\n\nIf the sentence names the claim in order to withdraw, forbid, quote or "
          f"record it, put `<!-- forbidden-ok: {PRIORITY_PRAGMA} -->` on the line or the "
          f"line above."
    )


def test_the_two_word_lists_have_not_drifted():
    """This rule and the screen's are the same idea; if one grows a word, so must the other.

    `tests/test_finals_screen.py` owns the line-level version over the template. The word
    lists there are the parent of the ones here — this file adds `1차`/`１차`/`순위`,
    which the reviewer's escapes proved were missing, and the screen version keeps its
    own because it guards a file with different wrapping. What must never happen is one
    of them silently losing a word: this test reads the other module's source and
    requires every word it lists to be listed here too.
    """
    src = (REPO / "tests/test_finals_screen.py").read_text(encoding="utf-8")
    for name, mine in (("TRIGGER_PRIORITY_WORDS", PRIORITY_WORDS),
                       ("TRIGGER_SOURCE_NOUNS", SOURCE_NOUNS)):
        block = src.split(f"{name} = ", 1)[1].split(")", 1)[0]
        theirs = re.findall(r'"([^"]+)"', block)
        assert theirs, f"could not read {name} from tests/test_finals_screen.py"
        missing = [w for w in theirs if w not in mine]
        assert not missing, (
            f"{name} in tests/test_finals_screen.py lists {missing}, which this file's "
            f"list does not. Add them here, or the markdown surfaces are guarded more "
            f"weakly than the screen."
        )


@pytest.mark.parametrize(
    "sentence",
    [
        # --- the reviewer's escapes: sentences it wrote, not the pattern's author ---
        "사람 신고가 일차 채널입니다",
        "사람 신고를 1차 트리거로 둡니다",
        "| 1순위 | **사람 신고** (119·산림청·마을 무전) | 크기 바닥 |",
        "저희 트리거의 주된 소스는 주민 신고입니다",
        "최초 인지는 주민 신고입니다",
        "전화 신고를 우선 소스로 둡니다",
        "위성보다 신고가 앞섭니다",
        # --- and the six spellings this repository actually shipped ---
        "그래서 이 시스템의 트리거는 **사람 신고가 일차**이고 위성은 보조입니다.",
        "트리거 인터페이스는 **사람 신고를 일차로 가정**하고 위성을 붙입니다.",
        "그래서 트리거 설계가 신고 우선, 위성 확인입니다.",
    ],
)
def test_a_priority_sentence_without_a_negation_is_caught(sentence: str):
    """Mutation, and the first seven were written by someone who had not seen the rule."""
    assert priority_violations(sentence), f"the priority rule does not catch: {sentence}"


def test_the_permitted_sentence_is_not_a_violation():
    """The negative direction, on the exact sentence all five surfaces must carry."""
    permitted = (
        "이 측정이 말하는 것은 위성을 일차로 둘 수 없다는 것까지이며, "
        f"{PERMITTED_CLAUSE}.\n"
    )
    assert not priority_violations(permitted)
    assert not priority_violations(
        "- **어느 채널이 일차여야 하는가.** 크기 바닥은 위성을 배제할 뿐 "
        "사람을 옹립하지 않습니다.\n"
    )


# ---------------------------------------------------------------------------
# WFG-070 · the same two claims, in ENGLISH
# ---------------------------------------------------------------------------
#
# Everything above this line is Korean. Every token in `BANNED`, `BANNED_PRIMACY`,
# `PRIORITY_WORDS`, `SOURCE_NOUNS` and `NEGATION_MORPHEMES` is a Korean string, and the
# docstring of each family says so in one clause — 「any of it in English, anywhere — no
# English pattern is gated」, 「English passes, here as everywhere in this file」. Three
# laps read those clauses as a scoping decision. They were a hole.
#
# Critic #10 found the claim alive at `docs/auto/research/RESEARCH_BRIEF_2026-09-03.md:75`,
# under the heading 「The ten hardest judge questions, with the answers that survive the
# verdicts」 — the student's own drill material, which `docs/auto/ROUTINE_PROMPTS.md` tells
# a routine to read every lap — and at `sweeps_2026-09-03/R3_science_gaps.md:22`. Critic #9
# had certified the same window with 「grepped every `.md` and `.html` in the tree this lap」.
# The grep was Korean too.
#
# HOW THIS RULE WAS CHOSEN, AND THE NUMBER THAT CHOSE IT. Two candidates were run over the
# English half of the repository (both research directories, `README.md`, `paper/manuscript.md`)
# **before anything was annotated**, because a gate whose hit count nobody measured is a
# gate whose noise nobody knows:
#
#   variant A — a direct mirror of `priority_violations` above: a priority word plus ONE
#               source noun, no negation.                          **27 hits, mostly noise.**
#               「first ISEF delegation」, 「primary category」, 「before Round 3–5」: the
#               English priority words are ordinary English, which the Korean ones are not.
#   variant B — the same, but requiring BOTH SIDES of the comparison in one sentence: a
#               machine-detection noun AND a human-channel noun.    **4 hits, 3 of them real.**
#
# ⚠ THE FIRST VERSION OF THIS COMMENT SAID 37, AND THE INDEPENDENT REVIEWER BLOCKED THE PUSH
# OVER IT. 37 came from a throwaway script that matched the nouns BY SUBSTRING in variant A
# and with WORD BOUNDARIES in variant B, so the two arms were never run under one rule and
# 「recall at threshold」 counted as a human-channel noun. The reviewer rebuilt variant A in
# good faith from the shipped constants, got 27, and pointed at CHARTER §3 rule 3: a number
# you cannot register, you do not write. **27 is the reproducible number**, variant A is now
# a committed function (`english_ordering_violations_variant_a`), and
# `test_the_number_that_chose_this_design_is_re_derivable` asserts both counts every run.
# The design call did not change — the ratio is 27:4 rather than 37:4 — but nobody should
# have had to take the first figure on trust.
#
# B is what ships. The asymmetry is the finding: this claim is a *comparison*, and demanding
# that both compared things appear is what separates it from ordinary English prose. The
# fourth hit is `paper/manuscript.md`, discussed under `EN_GUARDED` below.
#
# IT FOUND A THIRD INSTANCE NOBODY HAD SEEN. `sweeps_2026-09-03/R7_rubric_gap.md:109` is a
# prepared answer to a fire scientist — 「a satellite trigger would still have fired 22–64
# minutes *after* the human report in every fire we could test, so the trigger interface is
# designed report-first, satellite-confirm」 — in the same sentence as a 「every fire」 that
# the same file's preamble forbids. Critic #10's manual grep raised this row on two
# instances and this rule found a third, which is the only evidence offered here that it
# beats a reader.
#
# WHAT IT DOES NOT DO. The honest list, in the shape the two families above use, and none
# of these were closed by folding them back in as cases — critic #10's F55 was that the
# previous lap graded its *first draft* against a reviewer's set and then absorbed the
# escapes, which converts external ground truth into internal ground truth:
#
# * it counts negation morphemes, not scope, exactly like `priority_violations`: a sentence
#   carrying `not` anywhere passes, so 「the satellite is not fast, so the call comes first」
#   walks through;
# * it needs both sides named. 「the trigger is designed report-first」 alone — no satellite
#   noun — passes, and that half-sentence is quotable. The three literal spellings WFG-070's
#   contract names all fall here, which is why `BANNED_EN_SPELLINGS` exists further down as
#   a separate, separately-scored family;
# * a claim spread over two sentences passes, since the unit is a sentence;
# * it reads English and Korean and nothing else, and this repository has prose in both;
# * `[GAP: …]` markers and other bracketed conditionals are not understood;
# * **MARKDOWN HEADINGS ARE NEVER SCANNED AT ALL.** `_blocks` flushes on any line starting
#   with `#`, so `## The satellite fired after the human report` escapes both this rule and
#   both Korean families. Inherited from `priority_violations` and not noticed there either;
#   found by this lap's independent reviewer, recorded rather than fixed because changing
#   `_blocks` changes three rules at once and belongs in its own row (WFG-072);
# * **THE PRAGMA LICENSES A WHOLE BLOCK, NOT A LINE**, which the top of this file understates
#   when it says 「it is per-line, on purpose」 — true of `violations` and
#   `english_spelling_violations`, false of this rule and of `priority_violations`, where one
#   comment above a paragraph exempts the entire paragraph for good;
# * **the vocabulary is the floor, and it is lower than 「one side only」 suggests.**
#   `EN_MACHINE_NOUNS` has no `sensor`, `imager`, `pixel`, `hotspot` or `orbit`;
#   `EN_HUMAN_NOUNS` has no bare `report`, no `people`, no `public`. So 「Report first,
#   satellite second」 escapes even though **both sides are named** in ordinary English. That
#   is a different and worse failure than the one-side-only limit, and it is the reviewer's
#   finding, not this lap's.
#
# GRADED A SECOND TIME, BY SOMEONE WHO DID NOT WRITE IT. This lap's independent reviewer
# wrote **18** sentences of its own asserting the two withdrawn claims and measured
# **9 caught, 9 escaped — 50 %**, against this rule's own 8/16 (also 50 %) on the frozen set.
# Two independent sets agreeing at the same rate is the strongest evidence in this lap that
# the number generalises off its author's corpus. **None of the reviewer's nine escapes was
# folded in** — among them 「The primary trigger source is the human report.」, 「People beat
# the satellite every time.」 and 「already dispatched by the time the geostationary imager
# registered anything」. Adding their words would move the score and mean nothing, which is
# critic #10's F55 stated as a rule rather than as a story.
#
# ⚠ AND THE PRE-REGISTRATION BELOW IS NOT EVIDENCE, WHICH THE REVIEWER IS RIGHT ABOUT. The
# claim 「predicted 11, scored 8」 is written in prose that was committed AFTER the run, so
# nothing in this repository can falsify it; it is an honest report of what happened and it
# is not a measurement. The next lap that grades a gate writes its prediction as its own
# committed line BEFORE the run, and then the claim has a witness.
#
# Measured against a fresh set the author of these patterns wrote only AFTER freezing them
# (`test_the_english_rule_was_graded_after_it_was_frozen`): **8 of 16**. The lap that wrote
# them predicted 11 before running it and was wrong by three, which is the whole argument
# for running it. The eight escapes are listed there as failing-by-design documentation and
# none of them is fixed by widening a pattern.
#
# ONE OF THE EIGHT IS A TRADE-OFF THIS RULE MAKES ON PURPOSE, and it only became visible
# because the set was graded after freezing. The semicolon split below is what lets the rule
# see `R3_science_gaps.md:22`, a real instance. It is also why 「Residents call first; the
# satellite catches up 22 minutes later.」 escapes: splitting on the semicolon leaves one
# side of the comparison in each half, and a rule that needs both sides then sees neither.
# So this rule is measurably better on the prose this repository actually wrote and
# measurably worse on one natural English shape, and neither half of that is hidden.

#: The English judge-facing and drill surfaces. `docs/auto/research/` is here because
#: `ROUTINE_PROMPTS.md` sends a routine into it every lap and section (c) is the ten-question
#: drill the student reads before the booth; `README.md` because it is the first English
#: page anyone opens.
#:
#: ⚠ `paper/manuscript.md` IS DELIBERATELY ABSENT, and this is the same call the
#: `MANUSCRIPT_ANCHORS` block above makes for the same file. Variant B's fourth hit is
#: `paper/manuscript.md:657`, inside a `[GAP: …]` marker whose own opening clause is 「the
#: delays cannot be read against either the true ignition or the emergency call」 — the
#: manuscript refusing the claim, split from its negation by a sentence boundary. It is a
#: false positive, and licensing it would mean putting an HTML pragma into a file that
#: `paper/build_docx.py` converts to .docx and that CHARTER §12 gives to another routine.
#: The manuscript keeps the positive anchors above instead. Recorded rather than hidden:
#: the English claim is ungated in the manuscript, and `test_the_manuscript_hit_is_still_the
#: _gap_marker` fails if that one hit ever becomes something else.
EN_GUARDED: tuple[str, ...] = (
    "docs/auto/research/RESEARCH_BRIEF_2026-09-03.md",
    "docs/auto/research/sweeps_2026-09-03/R3_science_gaps.md",
    "docs/auto/research/sweeps_2026-09-03/R7_rubric_gap.md",
    "README.md",
)

#: Ordering AND primacy in one list: 「fired after the report」 and 「the report is primary」
#: are the two withdrawn claims, and in English they share a vocabulary.
EN_PRIORITY_WORDS = (
    "primary", "primarily", "first", "report-first", "satellite-first", "ahead of",
    "earlier", "sooner", "before", "precede", "preceded", "precedes", "preceding",
    "rank", "ranked", "leading", "leads", "after", "later", "behind", "lags",
    "lagged", "beat", "beats", "outpaced", "faster", "slower",
)
EN_MACHINE_NOUNS = (
    "satellite", "satellites", "gk2a", "firms", "viirs", "modis", "geostationary",
    "camera", "cameras",
)
EN_HUMAN_NOUNS = (
    "human report", "human reports", "report-first", "telephone", "phone call",
    "emergency call", "119", "eyewitness", "eyewitnesses", "witness", "human",
    "humans", "resident", "residents", "caller", "call", "calls", "villager",
    "villagers",
)
#: Prefixes, not conjugations — the lesson `NEGATION_MORPHEMES` above records.
EN_NEGATION_PATTERNS = (
    r"\bnot\b", r"\bno\b", r"\bnever\b", r"\bcannot\b", r"\bcan't\b", r"n't\b",
    r"\bwithout\b", r"\bwithdraw", r"\bunsupported\b", r"\brefus", r"\bneither\b",
    r"\bnothing\b", r"\bunmeasured\b", r"\bunknown\b",
)

#: Its own pragma token, for the same reason `PRIORITY_PRAGMA` has one: a pragma added for
#: a Korean spelling must not silently license the English claim as well.
EN_PRAGMA = "en-ordering"

#: A semicolon ends a clause here where it does not in the Korean rule, and that is not a
#: style preference. `R3_science_gaps.md:22` is a table row reading 「+22 / +34 / +64 min
#: after the human report (n = 3); GK2A beat FIRMS in 2/3; "GK2A buys time" is explicitly
#: not claimed」 — three independent statements, the last carrying a negation that a
#: whole-row scan would let cover the first. Without the semicolon split this rule misses
#: one of the three instances it exists for. Measured: adding it caught R3:22 and added
#: **zero** new hits anywhere else in the English half.
_EN_CLAUSE_SPLIT = re.compile(r";\s+")


def _has_word(text: str, words: tuple[str, ...]) -> bool:
    return any(re.search(r"\b" + re.escape(w) + r"\b", text) for w in words)


def english_ordering_violations(text: str) -> list[tuple[int, str]]:
    """(first line number, sentence) for every English sentence that compares the machine
    channel with the human channel on time or on rank, without a negation."""
    lines = text.splitlines()
    found: list[tuple[int, str]] = []
    for block, nums, split in _blocks(text):
        licensed: set[str] = set()
        for n in nums:
            for j in (n - 1, n):
                if 1 <= j <= len(lines):
                    licensed |= _pragma_tokens(lines[j - 1])
        if EN_PRAGMA in licensed:
            continue
        parts = _SENTENCE_SPLIT.split(block) if split else [block]
        for sentence in (c for part in parts for c in _EN_CLAUSE_SPLIT.split(part)):
            sentence = sentence.strip()
            low = sentence.lower()
            if not low:
                continue
            if not _has_word(low, EN_PRIORITY_WORDS):
                continue
            if not (_has_word(low, EN_MACHINE_NOUNS) and _has_word(low, EN_HUMAN_NOUNS)):
                continue
            if any(re.search(p, low) for p in EN_NEGATION_PATTERNS):
                continue
            found.append((nums[0], sentence))
    return found


@pytest.mark.parametrize("rel", EN_GUARDED)
def test_no_english_surface_claims_the_ordering_or_the_primacy(rel: str):
    """The load-bearing English gate. WFG-070."""
    path = REPO / rel
    assert path.is_file(), f"{rel} is missing — the English guard list is stale"
    hits = english_ordering_violations(path.read_text(encoding="utf-8"))
    assert not hits, (
        f"{rel} compares the satellite with the human channel on time or on rank, which no "
        f"committed artifact supports (WFG-053, WFG-063, WFG-070, NH-019):\n"
        + "\n".join(f"  {rel}:{n}  {s[:140]}" for n, s in hits)
        + "\n\nThe delays are measured from a RECORDED OCCURRENCE TIME, not a report; "
          "`docs/data_provenance/fire_manifest.json` marks that field "
          "`start/end/reported_ha are provenance only`, and no committed artifact holds a "
          "신고접수시각. So neither direction can be stated, and the size floor rules the "
          "SATELLITE OUT rather than the HUMAN IN. If the sentence names the claim in "
          f"order to withdraw, forbid, quote or record it, put "
          f"`<!-- forbidden-ok: {EN_PRAGMA} -->` on the line or the line above."
    )


def gap_marker_lines(text: str) -> set[int]:
    """1-based line numbers that fall inside a `[GAP: … ]` marker.

    Containment, not proximity. The first version of this check looked back twelve lines
    for the string `[GAP:`, which the lap's independent reviewer pointed out is a wider
    rule than the docstring claimed: an ordering sentence in the paragraph FOLLOWING a
    marker would have passed. A marker is a bracketed span, so the span is what is
    measured — from each `[GAP:` to the first `]` after it.
    """
    covered: set[int] = set()
    start = 0
    while (open_at := text.find("[GAP:", start)) != -1:
        close_at = text.find("]", open_at)
        if close_at == -1:
            close_at = len(text)
        first = text.count("\n", 0, open_at) + 1
        last = text.count("\n", 0, close_at) + 1
        covered.update(range(first, last + 1))
        start = close_at + 1
    return covered


def test_gap_containment_is_containment_and_not_nearness():
    """The compensating half of the loosened assertion above, measured rather than assumed.

    Three cases: inside a marker, in the paragraph after one, and no marker at all. The
    middle one is the case the twelve-line proximity window got wrong.
    """
    inside = "Intro line.\n[GAP: settling this needs a record that would say whether\na satellite trigger precedes the call]\nAfter.\n"
    assert 2 in gap_marker_lines(inside) and 3 in gap_marker_lines(inside)
    assert 4 not in gap_marker_lines(inside), "the marker's span leaked past its bracket"

    after = "[GAP: something else entirely]\n\nThe satellite trigger fired after the call.\n"
    assert 3 not in gap_marker_lines(after), (
        "a sentence in the paragraph after a marker counts as inside it, which is the "
        "proximity bug this helper replaced"
    )

    assert gap_marker_lines("No marker here at all.\n") == set()


def test_the_manuscript_hit_is_still_the_gap_marker():
    """`paper/manuscript.md` is out of `EN_GUARDED` on the strength of one measurement, so
    the measurement is a test rather than a sentence in a docstring.

    Written when variant B's only hit there was the `[GAP: …]` marker that refuses the
    claim, and pinned to that one sentence. **2026-09-05:** the paper routine rewrote that
    marker at `2b7c3a0` and the sentence 「would let the paper state whether a satellite
    trigger precedes the call」 is gone, so the count is now **0** and the exact-1 assertion
    turned a safe rewrite into a red suite on `auto/dev` and in CI.

    What the exclusion actually needs is that the manuscript never carries an ordering
    sentence OUTSIDE a `[GAP: …]` marker — a marker states what the paper cannot say, which
    is the opposite of claiming it. Zero hits satisfies that as well as one does, so the
    assertion is on the property, not on the count: at most one hit, and any hit must sit
    inside a GAP marker. A second hit, or a first hit outside a marker, still fails and the
    exclusion still has to be argued rather than inherited.
    """
    text = (REPO / "paper/manuscript.md").read_text(encoding="utf-8")
    hits = english_ordering_violations(text)
    assert len(hits) <= 1, (
        f"paper/manuscript.md now has {len(hits)} English ordering hits, more than the one "
        f"a [GAP: ...] marker can account for: {[s[:90] for _, s in hits]}. Re-argue the "
        f"exclusion in EN_GUARDED, or add the file and pragma the marker."
    )
    inside = gap_marker_lines(text)
    for line_no, sentence in hits:
        assert line_no in inside, (
            "the manuscript's ordering hit is not inside a [GAP: ...] marker, so it reads "
            f"as a claim rather than as a refusal of one: {sentence[:140]}"
        )


@pytest.mark.parametrize(
    "sentence",
    [
        # --- the three instances actually found in this repository ---
        "Detection floor measured (Session 19): a satellite trigger would have fired "
        "+22/+34/+64 min after the human report (FIRMS +117/+151/+17).",
        "GK2A detection floor: +22 / +34 / +64 min **after the human report** (n = 3)",
        "We measured the detection floor too: with GK2A at 2-minute cadence, a satellite "
        "trigger would still have fired 22-64 minutes *after* the human report in every "
        "fire we could test, so the trigger interface is designed report-first, "
        "satellite-confirm.",
    ],
)
def test_each_english_instance_found_in_the_tree_is_caught(sentence: str):
    assert english_ordering_violations(sentence), f"the English rule misses: {sentence}"


def test_the_english_rule_does_not_fire_on_the_prose_that_withdraws_the_claim():
    """Negative direction. A detector that always fires is as useless as one that never does."""
    withdrawn = (
        "The delays cannot be read against either the true ignition or the emergency "
        "call, so no comparison with the satellite is available.\n"
    )
    assert not english_ordering_violations(withdrawn)
    ordinary = (
        "The 240-min horizon is grounded on KFS statistics for 2,008 fires.\n"
        "Yeongdeok was the first region routed after the canonical field landed.\n"
        "GK2A has a 2 km pixel and a 2-minute full-disk cadence.\n"
    )
    assert not english_ordering_violations(ordinary), (
        "the English rule fires outside its own claim"
    )


#: Sixteen English sentences written AFTER `EN_PRIORITY_WORDS`, `EN_MACHINE_NOUNS`,
#: `EN_HUMAN_NOUNS` and `EN_NEGATION_PATTERNS` were frozen, without editing them
#: afterwards. The point of freezing first is critic #10's F55: the previous gate graded
#: its first draft against an outside set, then folded six of the eight escapes in as
#: cases, so the version that actually shipped was graded by nobody. Nothing below is fixed
#: by widening a pattern. `caught` is what this rule does today.
_GRADED_AFTER_FREEZING: tuple[tuple[str, bool], ...] = (
    ("A satellite trigger fires later than the phone call.", True),
    ("The human report reaches the desk before any satellite pixel does.", True),
    ("Our eyewitness channel is the primary trigger and GK2A confirms it.", True),
    # the semicolon split that catches R3:22 puts one side of the comparison in each half
    ("Residents call first; the satellite catches up 22 minutes later.", False),
    ("The 119 call precedes the GK2A anomaly in all three testable fires.", True),
    ("GK2A lags the villagers by roughly half an hour.", True),
    ("In rank order the trigger sources are: human report, then satellite.", True),
    ("The camera sees nothing, so the resident is first.", False),   # negation, wrong scope
    ("Ranked by latency the emergency call beats FIRMS by two hours.", True),
    ("Detection is human-led and the satellite is a confirmation layer.", False),
    ("We designed the interface report-first.", False),              # one side only
    ("The satellite is slower.", False),                             # one side only
    # "village" is not "villager" and "orbit" is not a machine noun: both sides missed
    ("Nobody saw the fire from orbit before the village did.", False),
    ("Timeline: villager 14:02, GK2A 14:24 -- the later of the two is the machine.", True),
    ("Our trigger begins with the telephone; the satellite is downstream of it.", False),
    ("A geostationary sensor cannot beat a witness who is standing in the smoke.", False),
)


def test_the_english_rule_was_graded_after_it_was_frozen():
    """8 of 16, and the number is asserted so it cannot quietly drift.

    This is a MEASUREMENT, not a target, and it is the number the rule actually scored
    rather than the 11 its author predicted before running it. The eight misses are real
    and every one is left open: three are the one-side-only limit, one is the semicolon
    trade-off documented above, one is the negation-scope limit this file has carried
    since `priority_violations`, and the rest use no word in any list. Raising the score
    by adding their words is exactly the corpus-fitting MEMO 2026-09-04 and critic #10's
    F55 both name; a later lap wanting a better number must get its sentences from
    someone who did not write the patterns.
    """
    caught = [s for s, _ in _GRADED_AFTER_FREEZING if english_ordering_violations(s)]
    expected = [s for s, want in _GRADED_AFTER_FREEZING if want]
    assert sorted(caught) == sorted(expected), (
        "the English rule's catch set moved. Expected 8 of 16 with these eight open:\n"
        + "\n".join(f"  MISS {s}" for s, want in _GRADED_AFTER_FREEZING if not want)
        + "\n\nIf a change closed one of them, that is good news — move it to True and say "
          "so in the report. If a change OPENED one, the rule regressed."
    )
    assert len(caught) == 8, f"expected 8 of 16, got {len(caught)}"


#: ⚠ REGISTERED BECAUSE THE INDEPENDENT REVIEWER COULD NOT RE-DERIVE IT, WHICH IS CHARTER
#: §3 RULE 3 APPLIED TO A COMMENT. The first version of this lap justified shipping variant
#: B with 「variant A gives 37 hits, mostly noise」 — a number that lived in a prose comment
#: and in a backlog row and in no runnable thing. The reviewer rebuilt variant A in good
#: faith from the shipped constants and got 27, never 37, and blocked on the gap.
#:
#: The reviewer was right and the cause is embarrassing in a useful way: the throwaway
#: script that produced 37 matched the NOUNS BY SUBSTRING for variant A while matching them
#: with word boundaries for variant B, so the two arms of the comparison were never run
#: under the same rule. `\bcall\b` versus `call` is the difference between 「recall at
#: threshold」 counting as a human-channel noun and not counting. **37 is withdrawn.** The
#: number below is variant A implemented with exactly variant B's word-boundary discipline,
#: differing from it in the one dimension the comparison is about, and it is asserted rather
#: than described so the next lap can re-run it.
def english_ordering_violations_variant_a(text: str) -> list[tuple[int, str]]:
    """The rejected design, kept runnable: a priority word plus ONE source noun.

    This is `english_ordering_violations` with the both-sides-of-the-comparison requirement
    removed and nothing else changed. It exists only so the number that chose the shipped
    design is re-derivable by anyone who doubts it.
    """
    lines = text.splitlines()
    found: list[tuple[int, str]] = []
    for block, nums, split in _blocks(text):
        licensed: set[str] = set()
        for n in nums:
            for j in (n - 1, n):
                if 1 <= j <= len(lines):
                    licensed |= _pragma_tokens(lines[j - 1])
        if EN_PRAGMA in licensed:
            continue
        parts = _SENTENCE_SPLIT.split(block) if split else [block]
        for sentence in (c for part in parts for c in _EN_CLAUSE_SPLIT.split(part)):
            low = sentence.strip().lower()
            if not low:
                continue
            if not _has_word(low, EN_PRIORITY_WORDS):
                continue
            if not _has_word(low, EN_MACHINE_NOUNS + EN_HUMAN_NOUNS):   # <-- the only change
                continue
            if any(re.search(p, low) for p in EN_NEGATION_PATTERNS):
                continue
            found.append((nums[0], sentence.strip()))
    return found


#: The file set both variants were measured over: the guarded surfaces plus the manuscript.
_VARIANT_SURFACES: tuple[str, ...] = EN_GUARDED + ("paper/manuscript.md",)

#: Counts over `_VARIANT_SURFACES` on the tree AS IT STANDS, i.e. after the annotating lap
#: put three real instances behind pragmas. Asserted, not described.
#:
#: Re-registered 2026-09-05 from (11, 1) after the paper routine's `2b7c3a0` rewrote the
#: §4.6 and §6 `[GAP: …]` markers: variant B's single hit (「would let the paper state
#: whether a satellite trigger precedes the call」) is gone, and variant A's loose rule,
#: which never needed both sides of the comparison, lost three of its eleven with the same
#: rewrite. The RULE did not move — only the prose it reads — so the design comparison
#: still stands and it is the ratio, not the absolute counts, that carried it: variant A
#: is still the arm that fires on ordinary English while variant B fires on none of it.
_VARIANT_A_HITS = 8
_VARIANT_B_HITS = 0

#: And the numbers on the UNTOUCHED tree, which are the ones that actually chose the design,
#: recorded here with the recipe because they cannot be re-run from this checkout:
#:
#:     git worktree add /tmp/wt0 4ff56d6
#:     # then run both functions over every .md under docs/auto/research/, plus
#:     # README.md and paper/manuscript.md, reading from /tmp/wt0
#:
#: gives **A = 27, B = 4** over that wider English half, and A = 15, B = 4 over
#: `_VARIANT_SURFACES` alone. The independent reviewer of this lap reconstructed variant A
#: from the shipped constants without seeing this recipe and also got **27**, which is the
#: only reason the figure is quotable at all.
_UNTOUCHED_TREE = "4ff56d6"
_UNTOUCHED_WIDE_A, _UNTOUCHED_WIDE_B = 27, 4


def test_the_number_that_chose_this_design_is_re_derivable():
    """The comparison that rejected variant A, run rather than remembered.

    Both arms over the same files under the same word-boundary discipline. The ratio is
    the argument — one source noun admits ordinary English ('the first ISEF delegation',
    'primary category', 'before Round 3-5'); requiring both sides of the comparison does
    not — and the ratio is what must hold, so both counts are asserted.

    These run over the tree as it stands TODAY, i.e. after this lap's annotations, which is
    why the numbers are lower than a run on the untouched tree: three real instances are now
    behind `forbidden-ok: en-ordering` pragmas and no longer counted by either arm.
    """
    a = sum(len(english_ordering_violations_variant_a(
        (REPO / rel).read_text(encoding="utf-8"))) for rel in _VARIANT_SURFACES)
    b = sum(len(english_ordering_violations(
        (REPO / rel).read_text(encoding="utf-8"))) for rel in _VARIANT_SURFACES)
    assert (a, b) == (_VARIANT_A_HITS, _VARIANT_B_HITS), (
        f"variant A now scores {a} and variant B {b}, not the registered "
        f"{_VARIANT_A_HITS} and {_VARIANT_B_HITS}. If prose moved, re-register both here "
        f"and in the report; if the RULE moved, the design comparison has to be re-argued."
    )
    # The live-tree ratio used to be asserted here as `a > b * 4`. With b == 0 after
    # `2b7c3a0` that degenerates to `a > 0` and can never fail again, which the lap's
    # independent reviewer caught: a guard that reads as intact while measuring nothing
    # is worse than no guard. The ratio is now measured on the fixed corpus below, which
    # no rewrite of this repository's prose can empty.


#: Sentences that separate the two arms, chosen because each is ordinary English a
#: document here could legitimately write. Variant A fires on all of them because one
#: source noun and a priority word is all it needs; variant B fires on none, because it
#: requires BOTH sides of the comparison. This is the design argument, run.
_ORDINARY_ENGLISH_VARIANT_A_FLAGS = (
    "The first satellite image of the region was published in 2015.",
    "GK2A was the primary source of the hazard field for this run.",
)

#: And the claim the rule exists to catch, which BOTH arms must still flag, or variant B
#: bought its quiet at the cost of the thing it is for.
_REAL_ORDERING_CLAIMS = (
    "The satellite trigger would have fired after the human report in every case.",
    "A geostationary detection precedes the villager's call by 22 minutes.",
)


def test_variant_b_is_quiet_where_variant_a_is_noisy_and_loud_where_it_counts():
    """The design comparison, on a corpus the repository's prose cannot drain.

    `test_the_number_that_chose_this_design_is_re_derivable` above measures both arms
    over live files, and that measurement is worth having — but it counts what happens
    to be written today, so a rewrite elsewhere can take it to zero and leave a green
    assertion behind. These two tuples are fixed, so the claim 'variant A fires on
    ordinary English and variant B does not, and variant B still catches the real
    thing' is falsifiable on every run regardless of what the tree says this week.
    """
    for sentence in _ORDINARY_ENGLISH_VARIANT_A_FLAGS:
        assert english_ordering_violations_variant_a(sentence), (
            f"variant A no longer flags ordinary English, so the noise it was rejected "
            f"for is gone and the design comparison has to be re-argued: {sentence}"
        )
        assert not english_ordering_violations(sentence), (
            f"variant B now flags ordinary English that names one side only, which is "
            f"exactly what it was chosen to avoid: {sentence}"
        )
    for sentence in _REAL_ORDERING_CLAIMS:
        assert english_ordering_violations(sentence), (
            f"variant B no longer catches a real ordering claim, so its quiet cost the "
            f"thing the rule is for (WFG-053, WFG-063, WFG-070, NH-019): {sentence}"
        )


# ---------------------------------------------------------------------------
# WFG-070 · the three literal spellings the ROW asked for, which the structural
# rule above does not catch on their own
# ---------------------------------------------------------------------------
#
# THE REVIEWER READ THE ROW'S CONTRACT AGAINST THE DIFF AND FOUND THE WEAKER BRANCH TAKEN.
# WFG-070's 「Done when」 offers two ways to close: the test 「either gains the English
# spellings (`after the human report`, `report-first`, `human report is the primary
# trigger`) or its docstring says in one sentence that the family is Korean-only and names
# the surfaces that are therefore unguarded」. `english_ordering_violations` satisfies the
# SECOND branch and reads as though it satisfied the first, and it does not: all three
# named spellings **escape it standalone**, because it requires a machine-detection noun in
# the same clause and none of the three contains one. 「The human report is the primary
# trigger source.」 — the literal withdrawn primacy claim, the sentence WFG-063 spent a lap
# removing — passed clean. The three in-tree instances are caught only because a satellite
# noun happens to sit beside them.
#
# So the row's first branch is honoured here, literally and narrowly: the three spellings it
# names, as strings, in the same per-token pragma discipline as `BANNED` and
# `BANNED_PRIMACY`. This is a copy-paste ratchet and nothing more — it is the shape this
# file already calls 「a string tripwire, not a claim detector」 three times.
#
# ⚠ IT IS DELIBERATELY NOT MERGED INTO THE STRUCTURAL RULE, and the separation is the
# point. `english_ordering_violations` scored 8/16 on a set frozen before it and 9/18 on the
# reviewer's independent set. If the reviewer's escapes were folded into ITS vocabulary the
# score would rise and mean nothing — critic #10's F55 exactly. These three strings come
# from the ROW's contract, written before the rule existed, not from a set anybody used to
# grade it, so they change no measured number. **The 8/16 in
# `test_the_english_rule_was_graded_after_it_was_frozen` is the score of the structural rule
# alone and is not restated anywhere as the score of the two together.**

#: (pattern, token, why). Case-insensitive; these are English spellings, not shapes.
BANNED_EN_SPELLINGS: tuple[tuple[str, str, str], ...] = (
    (r"after\s+the\s+human\s+report", "en after the human report",
     "the ordering claim in the spelling the drill brief actually used. The delays are "
     "measured from a recorded occurrence time; no 신고접수시각 exists in this repository"),
    (r"report[-\s]first", "en report-first",
     "「the design is report-first, satellite-confirm」. The size floor rules the satellite "
     "OUT; it does not rule the human IN"),
    (r"human\s+report\s+is\s+the\s+primary|primary\s+trigger\s+source\s+is\s+the\s+human",
     "en human report is primary",
     "the primacy claim WFG-063 withdrew, in English and in either word order"),
)


def english_spelling_violations(text: str) -> list[tuple[int, str, str]]:
    """(line number, token, line) for every banned English spelling not licensed.

    Line-level and case-insensitive, matching `violations` above rather than the block-level
    structural rule: these are exact strings, so a wrap between two of their words already
    defeats them and nothing is gained by rebuilding blocks.
    """
    lines = text.splitlines()
    found = []
    for i, line in enumerate(lines):
        allowed = _pragma_tokens(line)
        if i:
            allowed |= _pragma_tokens(lines[i - 1])
        for pattern, token, _why in BANNED_EN_SPELLINGS:
            if re.search(pattern, line, re.IGNORECASE) and token not in allowed:
                found.append((i + 1, token, line.strip()))
    return found


@pytest.mark.parametrize("rel", EN_GUARDED)
def test_no_english_surface_carries_the_three_withdrawn_spellings(rel: str):
    """WFG-070's 「Done when」, first branch, taken literally."""
    hits = english_spelling_violations((REPO / rel).read_text(encoding="utf-8"))
    assert not hits, (
        f"{rel} carries a withdrawn English spelling (WFG-053, WFG-063, WFG-070):\n"
        + "\n".join(f"  {rel}:{n}  [{tok}]  {line[:120]}" for n, tok, line in hits)
        + "\n\nIf the line names the claim in order to withdraw or record it, put "
          "`<!-- forbidden-ok: <token> -->` on the line or the line above."
    )


@pytest.mark.parametrize(
    "sentence",
    [
        "a satellite trigger would have fired +22/+34/+64 min after the human report",
        "So the design is report-first, satellite-confirm.",
        "The human report is the primary trigger source.",
        "Our primary trigger source is the human report.",
        "the trigger interface is designed report first, satellite-confirm",
    ],
)
def test_each_named_spelling_is_caught(sentence: str):
    assert english_spelling_violations(sentence), f"not caught: {sentence}"


def test_the_two_english_rules_are_scored_separately():
    """The structural rule's 8/16 must not silently become the pair's score.

    `test_the_english_rule_was_graded_after_it_was_frozen` calls
    `english_ordering_violations` and nothing else. This asserts the separation holds by
    showing the spelling rule DOES catch sentences the graded rule misses — which is the
    whole reason the two numbers may never be added together or quoted as one.
    """
    only_spelling = [
        s for s, want in _GRADED_AFTER_FREEZING
        if not want and english_spelling_violations(s)
    ]
    assert only_spelling == ["We designed the interface report-first."], (
        f"the spelling rule's overlap with the graded set changed: {only_spelling}. "
        "Re-read the note above about not merging the two scores."
    )
