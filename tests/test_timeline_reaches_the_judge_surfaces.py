"""WFG-218 — the schedule document has to be findable from the two surfaces a judge starts on.

`WFG-027` wrote `docs/auto/finals/TIMELINE_ROLES.md` and reached two of the four
judge-facing surfaces. 일정 counted **0** on `README.md` and **0** on
`web/finals.html`, and 「일정 및 팀원(개인의 경우 제외) 역할 배분의 타당성」 is a named
sub-item of 설계와 방법론, worth 20 points on **both** KCF scoring tables. The row
that was going to fix that was marked `done` with the gap written into its `done`
cell, where CHARTER §4 step 3 cannot see it, so no later lap would ever pick it up.
That is why this is a test and not a note.

What is asserted here, and why each assertion is the shape it is
---------------------------------------------------------------
The cheap version of this file would be ``assert "일정" in readme``. That passes
the moment someone writes the word and says nothing about whether the sentence is
still true, so the properties below bind the prose to the artifact instead:

1. **Every phase name on `README.md` is the artifact's own.** The README names the
   five phases in hand-typed Korean, which is the exact defect class this
   repository has shipped three times (`tests/test_timeline_roles.py`'s own
   docstring names them). A rename in `scripts/build_timeline_roles.py` now turns
   this red rather than leaving the front door describing a split that no longer
   exists.

2. **The screen hard-codes no phase name at all.** `scripts/finals.template.html`
   renders them from ``DATA.timeline``, which `scripts/build_finals.py` reads from
   the committed artifact at build time. So the generated surface cannot go stale
   between builds, and this test asserts the *absence* of the literals, which is
   the property that keeps it that way. ⚠ **Absence is only half of it, and the
   lap's independent reviewer blocked the first version of this file to prove it:**
   it gutted the card — dropped the phase list and the 「계획서가 아니라 기록」
   caveat, left ``void DATA.timeline;`` behind — while the payload still carried
   all five phases, and every assertion here passed. A payload nobody renders is
   not a surface, so `test_the_schedule_card_actually_renders_the_phases_and_the_caveat`
   reads the card itself, on the built file as well as the template.

3. **Neither surface restates a growing total.** The document's counts (commits,
   active days) grow with every lap; `TIMELINE_ROLES.md` §3.4 argues that a total
   copied out of it stops re-deriving from the artifact the moment it is copied.
   The row's constraint is 「link to it and let it carry its own as-of stamp」, and
   the assertion is scoped to the blocks this row added rather than to the whole
   README, because 42 and 458 are legitimate elsewhere on the page.

What this does NOT show. It does not show that the schedule is *reasonable*, which
is what the criterion actually scores, and it does not show that a judge will look
at either surface. It shows that the pointer exists on both and that the words
around it re-derive.

No clock, no timezone, no network, no file outside the repository (CHARTER §4b).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
ARTIFACT = REPO / "data" / "processed" / "timeline_roles" / "timeline_roles.json"
DOC_PATH = "docs/auto/finals/TIMELINE_ROLES.md"
README = REPO / "README.md"
TEMPLATE = REPO / "scripts" / "finals.template.html"
SCREEN = REPO / "web" / "finals.html"

#: The Korean numerals the README may use for the phase count, indexed by count.
_NUMERAL = {1: "한", 2: "두", 3: "세", 4: "네", 5: "다섯", 6: "여섯", 7: "일곱"}


@pytest.fixture(scope="module")
def art() -> dict:
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def readme() -> str:
    return README.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def readme_blocks(readme: str) -> list[str]:
    """The bullet blocks of `README.md` that carry the schedule pointer.

    A block is the ``- `` bullet containing the document path plus its
    continuation lines, which is the unit the row's 「do not restate a total」
    constraint applies to.
    """
    blocks, cur = [], None
    for line in readme.splitlines():
        if line.startswith("- ") or line.startswith("## ") or line.startswith("### "):
            if cur is not None and DOC_PATH in "\n".join(cur):
                blocks.append("\n".join(cur))
            cur = [line] if line.startswith("- ") else None
        elif cur is not None:
            cur.append(line)
    if cur is not None and DOC_PATH in "\n".join(cur):
        blocks.append("\n".join(cur))
    return blocks


def test_the_readme_points_at_the_schedule_document(readme_blocks: list[str]) -> None:
    """일정 counted 0 here when the row was filed; the pointer is the whole row."""
    assert readme_blocks, (
        f"README.md carries no bullet linking {DOC_PATH}; 일정 및 역할 배분 is a named "
        "sub-item of 설계와 방법론 on both scoring tables (WFG-218)")


def test_the_readme_names_the_artifact_s_own_phases(
    readme_blocks: list[str], art: dict
) -> None:
    """A hand-typed phase name that the builder no longer produces fails here."""
    joined = "\n".join(readme_blocks)
    missing = [p["name_ko"] for p in art["phases"] if p["name_ko"] not in joined]
    assert not missing, (
        "README.md's schedule bullets do not carry these phase names from "
        f"{ARTIFACT.relative_to(REPO)}: {missing}")


def test_the_readme_calls_it_a_record_and_not_a_plan(readme_blocks: list[str]) -> None:
    """`TIMELINE_ROLES.md` forbids calling itself a 계획서; the pointer must not either.

    The document's own status note says 「부스에서 이 문서를 「계획서」라고 부르지
    마십시오 — 「기록입니다」라고 말씀하십시오」. A README bullet that presents it as a
    plan would put the student in front of a judge saying the one thing the source
    document tells them not to say.
    """
    joined = "\n".join(readme_blocks)
    assert "기록" in joined, "the schedule bullets do not say the document is a record"
    assert re.search(r"계획서가\s*아니", joined), (
        "the schedule bullets do not say it is NOT a plan, which is the one thing "
        "TIMELINE_ROLES.md's status note asks every surface quoting it to carry")


def test_neither_readme_block_restates_a_growing_total(
    readme_blocks: list[str], art: dict
) -> None:
    """The row's constraint: link to the document, do not copy its totals out of it."""
    totals = {str(art["total_commits"]), str(art["active_days"])}
    for ph in art["phases"]:
        totals.add(str(ph["commits"]))
        totals.add(str(ph["active_days"]))
    for block in readme_blocks:
        # Dates are not totals and are allowed; strip them before looking.
        prose = re.sub(r"\d{4}-\d{2}-\d{2}", " ", block)
        prose = re.sub(r"Round\s*\d", " ", prose)
        prose = re.sub(r"[1-5]기", " ", prose)
        found = {t for t in totals if re.search(rf"(?<!\d){re.escape(t)}(?!\d)", prose)}
        assert not found, (
            f"a README schedule bullet restates {sorted(found)} from the schedule "
            "document; those grow every lap and the document carries its own as-of "
            "stamp (WFG-218 constraint)")


def _schedule_card(text: str) -> str:
    """The braced block that builds the 개발 일정 evidence card, template or built file.

    ⚠ Read from the SOURCE of the card, not from the payload. The lap's independent
    reviewer broke the first version of this file by gutting the card -- dropping
    the phase list and the caveat, leaving ``void DATA.timeline;`` behind -- while
    the payload still carried all five phases. Every assertion passed and WFG-218's
    deliverable (b) was undone. A payload nobody renders is not a surface.
    """
    marker = "const TL = DATA.timeline;"
    if marker not in text:
        pytest.fail(
            f"no 개발 일정 card: the marker {marker!r} is gone, so nothing on the "
            "screen reads the schedule payload (WFG-218 deliverable (b))")
    start = text.index(marker)
    return text[start:text.index("// registry", start)]


def test_the_screen_renders_the_phases_from_the_payload(art: dict) -> None:
    """The generated surface must hold no phase literal, or it can go stale silently."""
    tpl = TEMPLATE.read_text(encoding="utf-8")
    assert "DATA.timeline" in tpl, (
        "scripts/finals.template.html does not read DATA.timeline, so the screen "
        "either names no schedule or names one that no builder derives")
    hard_coded = [p["name_ko"] for p in art["phases"] if p["name_ko"] in tpl]
    assert not hard_coded, (
        f"these phase names are hard-coded in the template: {hard_coded}. They must "
        "come from the payload, which build_finals.py reads from the artifact")


@pytest.mark.parametrize("path", [TEMPLATE, SCREEN], ids=["template", "built"])
def test_the_schedule_card_actually_renders_the_phases_and_the_caveat(path) -> None:
    """The card, not the payload — and on the built file, not only its source.

    The reviewer's mutation edited template and output identically, which keeps
    `test_finals_template_sync.py` green because that file asserts the two agree
    and not what they say. So both are checked here, for what they say.
    """
    card = _schedule_card(path.read_text(encoding="utf-8"))
    assert "TL.phases.map" in card, (
        f"{path.name}'s 개발 일정 card does not iterate TL.phases, so the screen "
        "names no phase at all and WFG-218's screen half is undone")
    assert "계획서가 아니라" in card and "기록" in card, (
        f"{path.name}'s 개발 일정 card has lost the 「계획서가 아니라 기록입니다」 "
        "caveat. TIMELINE_ROLES.md's status note asks every surface quoting it to "
        "carry that, and the booth script tells the student to say it out loud")
    assert "TL.phases.length" in card, (
        f"{path.name}'s 개발 일정 card hard-codes how many phases there are. The "
        "list is data-driven; the count must be too, or the screen can say 「다섯」 "
        "over six phases")
    # ⚠ The line above is not enough on its own, and a mutation proved it: the card
    # kept `TL.phases.length` in its headline while the prose said 「다섯 구간」, and
    # the assertion passed. So the numeral itself is refused anywhere in the card.
    literal = [f"{w} 구간" for w in _NUMERAL.values() if f"{w} 구간" in card]
    assert not literal, (
        f"{path.name}'s 개발 일정 card spells the phase count out as {literal}. Every "
        "count on this card comes from TL.phases.length; a Korean numeral typed in "
        "beside it is the hand-typed number that outlives its artifact")


def test_the_built_screen_carries_the_artifact_s_phases(art: dict) -> None:
    """What the judge actually opens is `web/finals.html`, not the template."""
    html = SCREEN.read_text(encoding="utf-8")
    m = re.search(r'"timeline":(\{.*?\}\]\})', html)
    assert m, (
        "web/finals.html carries no timeline block in its payload; run "
        "`make finals PYTHON=.auto/venv/bin/python`")
    block = json.loads(m.group(1))
    assert block["doc"] == DOC_PATH
    names = [p["name"] for p in block["phases"]]
    assert names == [p["name_ko"] for p in art["phases"]], (
        f"the built screen's phases {names} are not the artifact's; the screen is "
        "stale, run `make finals PYTHON=.auto/venv/bin/python`")



def test_the_readme_s_phase_count_word_is_the_artifact_s_count(
    readme_blocks: list[str], art: dict
) -> None:
    """「다섯 구간」 is a hand-typed count and goes stale exactly like a total does."""
    n = len(art["phases"])
    word = _NUMERAL.get(n)
    assert word, f"no Korean numeral known for {n} phases; extend _NUMERAL"
    joined = "\n".join(readme_blocks)
    assert f"{word} 구간" in joined, (
        f"the artifact holds {n} phases, so README.md's schedule bullets should say "
        f"「{word} 구간」; they do not")
    wrong = [w for k, w in _NUMERAL.items() if k != n and f"{w} 구간" in joined]
    assert not wrong, (
        f"README.md's schedule bullets say {wrong} 구간 while the artifact holds {n}")
