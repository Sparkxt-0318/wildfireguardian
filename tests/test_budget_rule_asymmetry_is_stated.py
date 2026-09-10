"""WFG-128 — the `fa_exceeds_budget` counts may not be printed without the rule they were measured under.

THE DEFECT, IN ONE SENTENCE. `fa_exceeds_budget` is the one number in this repository
that runs **against** the project — 「the fire-blind route is safe but the future-aware
router cannot finish in time」 — and `classify()` in
`scripts/run_real_roads_real_hazard_slope.py` measures it with a **600-minute budget on
the future-aware arm and no budget at all on the fire-blind arm**.  `docs/multi_region.md`
§3.1 printed 「2 for Uiseong-Andong and 3 for Uljin-Samcheok」 with no such qualification,
and `README.md` sends a judge to that page for 「완전한 분할」.  `docs/present_perimeter_arm.md`
§2 had already established the opposite for the Uiseong-Andong pair — their fire-blind
routes arrive at 624.8 and 628.2 minutes, so under one rule that bucket is **empty** —
and the two pages had been saying different things for four days.

WHY THIS FILE ASSERTS A DIRECTION AND NOT A VOCABULARY.  `docs/auto/MEMO.md`, 2026-09-10:
*「a gate over prose asserts a DIRECTION, or it asserts nothing」*.  Four token-presence
assertions in `tests/test_output_object_claim_bounds.py` once passed a block asserting the
**inverse** of the claim they were written to protect, because every token survived the
inversion.  So each surface here is graded twice — the qualification in its own words
(`_REQUIRES`), and the sentence that would replace it if somebody 「tidied」 the page
(`_DENIES`).  The `_DENIES` half is the load-bearing one: the realistic failure is not a
lap deleting the caveat, it is a lap smoothing 「different time rules」 into 「the same
rule」 while every required token stays on the page.

AND WHY IT READS A BLOCK RATHER THAN A FILE — WITH THE SCOPE STATED HONESTLY.  WFG-185: an
assertion of the form `assert TOKEN in file` was satisfied by a token two hundred lines from
the sentence it was supposed to scope, and the scope defect shipped to a printed card.  So
both surfaces here are read as a **block**, not a file.  ⚠ But the block is not tight, and
the lap's independent reviewer was right to say the first draft of this docstring implied it
was: `_block_carrying` runs from the count's own paragraph to the **next heading**, which is
about **50 lines** in `docs/multi_region.md` §3.1 and about **9** in the README bullet.  A
qualification that drifts anywhere inside §3.1 still passes.  What this actually buys is that
the qualification cannot leave the SECTION — it cannot sit in §3.2, in §5, or in another
file, which is the WC-004 failure (a correction that reached one card and left the claim
standing eight sections away).  It does not buy adjacency, and no assertion here claims it.

MUTATION GRADING, run by the lap that wrote this (2026-09-10T0625Z), reported as it
actually came out rather than as it was designed:

* **M1**, delete the ⚠⚠ paragraph from §3.1 → **3 red**.
* **M2**, rewrite 「scored under different time rules」 as 「scored under the same time
  rule」, changing nothing else → **2 red**.  ⚠ The first draft of `MR_DENIES` scored
  **1** here, on the `_REQUIRES` side only: the denial pattern was anchored on 「both
  arms」 and the sentence on the page says 「The two arms」, so the inverse assertion
  itself went undetected and only the vanished token was caught.  That is the polarity
  hole this half exists to close, found by running the mutation rather than by reading
  the regex, and the pattern was widened to `(?:both|the two) arms … scored under the
  same rule` before this line was written.
* **M3**, delete the ⚠ clause from the README bullet → **5 red**.
* **M4**, rewrite the README clause as 「두 팔에 같은 규칙을 적용해」 → **2 red**, one on
  each half.

Restored tree: 20 passed.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MULTI_REGION = REPO / "docs" / "multi_region.md"
README = REPO / "README.md"
CLASSIFIER = REPO / "scripts" / "run_real_roads_real_hazard_slope.py"


def _block_carrying(path: Path, needle: str) -> str:
    """The contiguous run of non-blank lines that holds `needle`, plus the ⚠ paragraphs
    that follow it before the next heading.

    A markdown caveat is written as its own paragraph under the sentence it caveats, so
    the unit a reader actually takes in is the sentence's paragraph AND the paragraphs
    between it and the next heading — not the whole file, and not one paragraph.
    """
    text = path.read_text(encoding="utf-8")
    assert needle in text, f"{path.name} no longer carries the sentence this gate scopes"
    lines = text.splitlines()
    hit = next(i for i, line in enumerate(lines) if needle in line)
    start = hit
    while start > 0 and lines[start - 1].strip():
        start -= 1
    end = hit
    while end + 1 < len(lines) and not lines[end + 1].startswith("#"):
        end += 1
    return "\n".join(lines[start:end + 1])


# --- the mechanism, read from the code rather than asserted ----------------------------

def test_the_asymmetry_is_real_in_the_classifier_this_gate_describes():
    """If this ever fails, the DOCS are what should change, and this file is wrong.

    The whole qualification rests on one fact about `classify()`: the future-aware call
    receives `time_budget_min` and the fire-blind call does not.  Pinning it here means a
    lap that budgets the fire-blind arm is told to rewrite the prose rather than left to
    discover that the pages now understate.
    """
    src = CLASSIFIER.read_text(encoding="utf-8")
    naive = re.search(r"nv\s*=\s*naive_route\((?:[^()]|\([^()]*\))*\)", src, re.S)
    future = re.search(r"fa\s*=\s*future_aware_route\((?:[^()]|\([^()]*\))*\)", src, re.S)
    assert naive and future, "classify() no longer calls the two arms the way this gate reads"
    assert "time_budget_min" not in naive.group(0), (
        "the fire-blind arm now takes a time budget. The asymmetry docs/multi_region.md "
        "§3.1 and README.md describe is gone, and those pages are now the thing that is "
        "wrong — update them and this test together."
    )
    assert "time_budget_min" in future.group(0), (
        "the future-aware arm no longer takes a time budget; `fa_exceeds_budget` cannot "
        "mean what either page says it means"
    )


# --- docs/multi_region.md §3.1 ---------------------------------------------------------

MR_REQUIRES = {
    "the two arms are named as differently ruled":
        r"different\s+time\s+rules",
    "the fire-blind arm's missing budget is stated, not implied":
        r"no\s+budget\s*\n?\s*at\s+all",
    "the mechanism is pointed at in code, so a judge can falsify it":
        r"classify\(\)",
    "the Uiseong-Andong bucket is called empty under one rule":
        r"Uiseong-Andong\s+bucket\s+is\s+empty",
    "Uljin-Samcheok is marked NOT re-read":
        r"Uljin-Samcheok's\s+3\s+has\s+not\s+been\s+re-read",
    "Yeongdeok's 0 carries its reason":
        r"can\s+only\s+move\s+origins\s+\*\*out\*\*",
    "the page that established it is linked":
        r"present_perimeter_arm\.md",
    "the committed value is said to stay put":
        r"NH-031",
}

#: The sentences a lap 「tidying」 this section would write.  Each one leaves every
#: MR_REQUIRES token above untouched, which is the entire reason this half exists.
MR_DENIES = {
    "both arms scored the same":
        r"(?:both|the\s+two)\s+arms[^.\n]{0,60}?scored\s+under\s+(?:the\s+same|one)\s+(?:time\s+)?rule",
    "the bucket read as forecast defeat, affirmatively":
        r"(?<!not )(?:are|is)\s+(?:the\s+)?origins?\s+(?:on\s+)?(?:which|where)\s+the\s+forecast\s+lost",
    "the committed value quietly restated as the budgeted one":
        r"mr_uiseong_fa_exceeds_budget\s*(?:=|is|→)\s*0",
}


@pytest.mark.parametrize("why,pattern", sorted(MR_REQUIRES.items()))
def test_the_multi_region_section_states_the_asymmetry(why: str, pattern: str):
    block = _block_carrying(MULTI_REGION, "is **2** for Uiseong-Andong")
    assert re.search(pattern, block), (
        f"docs/multi_region.md §3.1 prints the `fa_exceeds_budget` counts without "
        f"stating {why}.\nWFG-128: the counts and the rule they were measured under "
        f"travel in the same section, or the counts do not travel."
    )


@pytest.mark.parametrize("why,pattern", sorted(MR_DENIES.items()))
def test_the_multi_region_section_refuses_the_inverse(why: str, pattern: str):
    block = _block_carrying(MULTI_REGION, "is **2** for Uiseong-Andong")
    assert not re.search(pattern, block, re.I), (
        f"docs/multi_region.md §3.1 now asserts the opposite of what WFG-128 fixed "
        f"({why}). `classify()` passes a budget to one arm only; see "
        f"docs/present_perimeter_arm.md §2."
    )


# --- README.md, the surface that sends the judge to that page --------------------------

README_REQUIRES = {
    "the two arms are named as differently ruled":
        r"서로\s*다른\s*시간\s*규칙",
    "the fire-blind arm's missing budget is stated":
        r"예보\s*없는\s*팔에는\s*\n?\s*예산이\s*걸려\s*있지\s*않",
    "Uiseong-Andong is called empty under one rule":
        r"의성·안동\s*쪽은\s*\*\*비어\s*있",
    "Uljin-Samcheok is marked NOT re-read":
        r"울진·삼척\s*쪽은\s*아직\s*다시\s*재지\s*않",
    "the section carrying the argument is linked, not just the file":
        r"§3\.1",
}

README_DENIES = {
    "both arms scored the same":
        r"두\s*팔에\s*(?:같은|동일한)\s*(?:시간\s*)?규칙",
    "the counts presented as complete without the rule":
        r"완전한\s*분할입니다\s*$",
}


@pytest.mark.parametrize("why,pattern", sorted(README_REQUIRES.items()))
def test_the_readme_bullet_carries_the_pointer(why: str, pattern: str):
    block = _block_carrying(README, "각 2곳·3곳입니다")
    assert re.search(pattern, block), (
        f"README.md prints 「각 2곳·3곳」 and sends a judge to docs/multi_region.md "
        f"without stating {why}.\nWFG-128: the pointer goes in the same bullet block "
        f"as the count, never one screen away (the WC-004 shape)."
    )


@pytest.mark.parametrize("why,pattern", sorted(README_DENIES.items()))
def test_the_readme_bullet_refuses_the_inverse(why: str, pattern: str):
    block = _block_carrying(README, "각 2곳·3곳입니다")
    assert not re.search(pattern, block, re.M), (
        f"README.md's bucket bullet now asserts the opposite of what WFG-128 fixed ({why})."
    )


# --- what this gate does NOT do --------------------------------------------------------

def test_the_gate_does_not_claim_to_have_re_read_uljin():
    """The honest half, gated so a later lap cannot quietly promote it.

    Nothing in this repository has re-scored Uljin-Samcheok under one rule.  If a lap
    ever does, it will want to delete the 「has not been re-read」 sentence — and this
    assertion is what makes it say so out loud, by requiring the sentence to disappear
    together with a document that reports the re-run.
    """
    block = _block_carrying(MULTI_REGION, "is **2** for Uiseong-Andong")
    claims_rerun = re.search(r"Uljin-Samcheok[^.\n]{0,80}re-scored\s+under\s+one\s+rule", block)
    assert not claims_rerun, (
        "§3.1 claims Uljin-Samcheok was re-scored under one rule. No artifact in this "
        "repository holds that run; docs/present_perimeter_arm.md covers Uiseong-Andong "
        "only. Write the run first, then the sentence."
    )
