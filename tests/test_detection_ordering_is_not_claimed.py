"""The judge-facing detection documents may not claim the satellite/telephone ordering.

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
* any of it in English, anywhere — no English pattern is gated.

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
    ordinary = (
        "위성 트리거는 기록된 발생일시로부터 +22분 뒤였습니다.\n"
        "한국 산불 신고의 99 %가 목격 신고입니다.\n"
        "사람 신고를 일차 소스로 설계해야 합니다.\n"
    )
    assert not violations(ordinary), "the gate fires on legitimate neighbouring prose"


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
