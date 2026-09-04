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

What this file does NOT do, stated so nobody reads more into a green run: it does not
prove the delays are correct, it does not check any figure against the registry (that is
``tests/test_detection_floor_card.py``), and it constrains only the four documents named
below. A fifth document may assert the ordering tomorrow and this test will pass. Widening
the claim-shape gate to the whole tree is WFG-059.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

#: The documents a judge meets, and the one that already says it correctly.
#: `paper/manuscript.md` is here as a REGRESSION anchor: it is the half of the
#: repository that got this right first, and a later lap "harmonising" it back to the
#: card's old wording is exactly the failure this row exists to stop.
GUARDED: tuple[str, ...] = (
    "docs/detection_floor.md",
    "docs/auto/finals/DETECTION_FLOOR_CARD.md",
    "docs/auto/JUDGE_QA.md",
    "paper/manuscript.md",
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
#: sets for a `claim` rule. Against the four guarded documents as this row left them:
#: 0 unpragmaed hits. Against the withdrawn spellings they exist to stop — the card's old
#: front sentence, §9's old title and verdict, §4's 「신고 대비」 table label, Q10's old
#: T0 sentence and Q10a's old closing line: all caught. The negative direction is
#: `test_a_line_that_withdraws_the_claim_is_not_a_violation` plus the mutation tests at
#: the foot of this file, which put each withdrawn sentence back and require a failure.
BANNED: tuple[tuple[str, str, str], ...] = (
    (r"위성은?\s*사람보다\s*(?:더\s*)?느[렸리]", "사람보다 느",
     "the card's withdrawn front sentence 「위성은 사람보다 느렸습니다」"),
    (r"위성이?\s*사람보다\s*앞서지", "사람보다 앞서지",
     "§9's withdrawn 「어느 쪽으로 읽어도 위성이 사람보다 앞서지 않습니다」"),
    (r"신고\s*대비", "신고 대비",
     "the delays labelled as report-relative; they are recorded-occurrence-relative"),
    (r"신고보다", "신고보다",
     "any delay or step stated relative to a 신고 time that was never measured"),
    (r"기준\s*시각은\s*(?:「\s*)?신고", "기준 시각은 신고",
     "§1's withdrawn heading 「기준 시각은 신고 시각입니다」"),
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
        "<!-- forbidden-ok: 사람보다 느 -->\n"
        "이전 판은 「위성은 사람보다 느렸습니다」라고 적었고, 철회했습니다.\n"
    )
    assert not violations(withdrawn)
    ordinary = (
        "위성 트리거는 기록된 발생일시로부터 +22분 뒤였습니다.\n"
        "한국 산불 신고의 99 %가 목격 신고입니다.\n"
        "사람 신고를 일차 소스로 설계해야 합니다.\n"
    )
    assert not violations(ordinary), "the gate fires on legitimate neighbouring prose"


@pytest.mark.parametrize(
    "sentence",
    [
        "**위성은 사람보다 느렸습니다.** 검증 가능했던 화재 3건에서",
        "어느 쪽으로 읽어도 위성이 사람보다 앞서지 않습니다.",
        "| 화재 | GK2A 지연 (신고 대비) | 레지스트리 키 |",
        "위성 트리거는 신고보다 각각 +22분 · +34분 · +64분 뒤에 울렸을 것입니다",
        "## ⚠ 1. 가장 중요한 단서 — 기준 시각은 신고 시각입니다",
        "GK2A 기반 트리거는 모든 경우에 사람의 신고보다 뒤에 울렸을 것입니다",
    ],
)
def test_each_withdrawn_spelling_is_caught(sentence: str):
    """Mutation, one per spelling this repository actually shipped.

    These are the exact strings that stood in `DETECTION_FLOOR_CARD.md`,
    `docs/detection_floor.md` §1/§4/§9 and `docs/auto/JUDGE_QA.md` Q10 before WFG-053.
    Reinstating any of them anywhere in a guarded document must fail.
    """
    assert violations(sentence), f"the gate does not catch: {sentence}"
