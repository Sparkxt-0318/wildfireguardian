"""CHARTER §3 rule 5b, made mechanical for the figures this repository actually prints.

Rule 5b says a figure taken from **outside** this repository is written only with its
**agency, as-of date and scope**, and that an interim tally is never presented as a final
one.  Until this file there was no check of it at all, and the failure it exists for has
already happened twice:

* `12b8ac7` restated the README's opening figures from an interim provincial tally and was
  wrong by 54,000 ha (NH-015, WFG-049);
* `docs/detection_floor.md` §0 opened, until WFG-069, with 「보도된 해에 … 신고의 99 %가
  목격 신고」 — a 2023-04-28 year-to-date accumulation written as a settled annual fact,
  eight lines above a measurement that says nothing of the kind, in the file
  `JUDGE_QA.md` Q10 · Q10d both name as their 근거 (critic #9, F48).

**How strong this is, as a number.**  Critic #9's standing instruction is that a new gate
is graded against a mutation set its author did not write, and the rate printed.  This
file's first draft was defended in its own docstring with the argument that a **closed,
enumerated registry of literal figures** is not subject to the 2-of-20 result that broke
the previous lap's spelling gate, because 「a sentence escapes it only by not containing
the figure」.  **That argument is false and the reviewer measured it: 12 of 20.**  A closed
registry closes the set of *figures*; it does not close the set of *spellings*, and the
spellings are what the escapes were about.  Eight plausible Korean blocks printing a
registered figure walked through — a line wrap between the number and its noun (this
repository hard-wraps every Korean paragraph), 「99 퍼센트」, 「99.0 %」, twenty-six
characters of padding between the two halves, a markdown table row licensed by a label in
a *different* row of the same table, 「백오십이 대」 in Korean numerals, and — worst — the
whole 「최초 발견 0건」 half of the camera figure, which the first draft could not see at
all because it looked only for ``152``.

Six of the eight are fixed below and the patterns now allow wraps, the Korean word for
percent, a decimal, a wider gap, and the 0건 half; ``_blocks`` now cuts a markdown table
into rows so a neighbouring row cannot license this one.  **Two are not fixed and are not
fixable by this instrument:** a figure written in Korean numerals, and a paraphrase that
carries no digits (「신고 거의 전부가 목격 신고였다」).  Nothing in a judge-facing document
should cite this check as proof; it is a ratchet against the shapes that have actually been
written, not a reader of meaning.

Two more limits, stated rather than discovered later:

* it does **not** catch a new external figure nobody added to ``EXTERNAL_FIGURES``.  The
  registry is hand-maintained and that is its real weakness;
* it does **not** read whether the surrounding sentence draws a *conclusion* from the
  figure.  That is the WFG-063/WFG-069 defect and a different axis; ``BANNED_PRIMACY`` in
  ``tests/test_detection_ordering_is_not_claimed.py`` is the instrument for it, and its
  own docstring says how weak it is.

**What is guarded is two files, not seven.**  ``GUARDED`` lists seven surfaces, but only
``docs/detection_floor.md`` and ``docs/auto/JUDGE_QA.md`` contain either figure today; the
other five are there so that moving a figure onto the screen, the booth card or the
manuscript fails here.  Counting list entries as coverage is how a report overstates a
gate, so: **coverage today is two files.**  Outside ``GUARDED``, the reviewer found the
camera figure printed unlabelled in about twenty blocks across the loop's own records —
``docs/auto/BACKLOG.md``, ``MEMO.md``, ``NEEDS_HUMAN.md``, ``SCORECARD.md``,
``KCF_READINESS.md``, ``dashboard.html`` and five reports.  Those are records of a moment
and are expected to age (MEMO, 2026-09-04, on line-number citations); a judge is handed
none of them.  They are out of scope deliberately, which is a different thing from being
clean.

**Records are out of scope on purpose.**  ``docs/SESSION19_REPORT.md`` prints both figures
inside a dated withdrawal block; CHARTER §3 rule 7 says a record is annotated, never
edited, so requiring it to carry today's labels would demand the one edit the charter
forbids.  It is therefore not in ``GUARDED`` — stated here rather than left implicit.

**The escape hatch, and why it takes a reason.**  A block may license itself with

    <!-- scope-ok: <figure key> — <why this block is not a use of the figure> -->

The reason is not decoration: ``test_a_scope_pragma_states_a_reason`` fails a pragma whose
reason is shorter than twelve characters.  F48 happened underneath a bare
``<!-- forbidden-ok: 99 % 목격 신고 -->`` that licensed the figure while the conclusion
standing on it went unexamined; a licence that has to say what it is for is at least read
once by the person writing it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

#: The live judge-facing surfaces.  Deliberately the same five as ``PRIMACY_GUARDED`` in
#: ``tests/test_detection_ordering_is_not_claimed.py`` plus the screen's companion
#: document and the manuscript, which is prose a reviewer reads.  Copied rather than
#: imported for the same reason that file copies its word lists: two short lists that can
#: be compared by eye beat one import whose direction nobody remembers.
GUARDED: tuple[str, ...] = (
    "docs/detection_floor.md",
    "docs/auto/finals/DETECTION_FLOOR_CARD.md",
    "docs/auto/JUDGE_QA.md",
    "docs/finals_screen_v2.md",
    "scripts/finals.template.html",
    "web/finals.html",
    "paper/manuscript.md",
)

#: One entry per figure this repository quotes from outside itself.
#:
#: ``detect``   — the figure's appearance.  A literal, or a literal pair close together.
#: ``agency``   — spellings that name whose figure it is.
#: ``as_of``    — spellings of the date the figure was taken.
#: ``scope``    — spellings of what period or population it covers.  For an interim tally
#:                this is where 「잠정 / 연중 누계」 has to appear, which is rule 5b's
#:                「never presented as a final one」 in the only form a test can check.
#: ``why``      — what goes wrong when the labels are missing.  Printed on failure.
EXTERNAL_FIGURES: tuple[dict[str, object], ...] = (
    {
        "key": "khan2023_witness_share",
        # `[\s\S]` rather than `[^\n]`: every Korean paragraph in this repository is
        # hard-wrapped at ninety columns, so a wrap between the number and its noun was
        # the reviewer's first escape.  60 rather than 24 because the second escape put
        # twenty-six characters of agency names between the two halves.
        "detect": re.compile(
            r"99(?:\.\d+)?\s*(?:%|퍼센트)[\s\S]{0,60}목격"
            r"|목격[\s\S]{0,60}99(?:\.\d+)?\s*(?:%|퍼센트)"
        ),
        "agency": ("경향신문", "khan.co.kr"),
        "as_of": ("2023-04-28", "2023년 4월 28일"),
        "scope": ("잠정", "연중 누계", "누계"),
        "why": (
            "산림청·119 접수 신고의 99 % 목격 신고 비율은 경향신문 2023-04-28 기사의 "
            "「올해」, 즉 4개월치 연중 누계입니다. 확정 연간치로 읽히면 CHARTER §3 규칙 5b "
            "위반이고, 이것이 critic #9 F48 / WFG-069 입니다."
        ),
    },
    {
        "key": "khan2023_gyeongbuk_camera_zero",
        # The second alternative is the reviewer's worst escape: the half of this figure
        # that carries the meaning is 「최초 발견 0건」, and the first draft looked only
        # for `152`, so the sentence §0 now opens on was undetectable by its own gate.
        "detect": re.compile(
            r"152[\s\S]{0,60}(?:대|개)"
            r"|카메라[\s\S]{0,60}152"
            r"|카메라[\s\S]{0,80}최초[\s\S]{0,20}(?:발견|감지)[\s\S]{0,20}0\s*건"
        ),
        "agency": ("경향신문", "khan.co.kr"),
        "as_of": ("2023-04-28", "2023년 4월 28일"),
        "scope": ("2022",),
        "why": (
            "경북 산불감시카메라 152대와 최초 발견 0건은 경향신문 2023-04-28 기사의 값이고, "
            "0건이 덮는 기간은 2022년 한 해와 2023년 4월 28일까지입니다. 기간을 적지 않으면 "
            "「지금까지 한 번도」로 읽힙니다."
        ),
    },
)

SCOPE_PRAGMA = re.compile(r"<!--\s*scope-ok:\s*([A-Za-z0-9_]+)\s*[—-]\s*(.*?)\s*-->")

#: A licence has to say what it is for; twelve characters is the shortest sentence that
#: is not just the key repeated.
MIN_REASON_CHARS = 12


def _blocks(text: str) -> list[tuple[int, str]]:
    """Split into blocks, keeping each block's 1-based start line.

    A paragraph or a list is one block, which is the unit a reader takes the labels from:
    a scope written three paragraphs away is not a label on this figure, and ``WFG-041``
    is the row about a ±2-line window that a stray keyword satisfied.

    **A markdown table row is its own block.**  The reviewer's fourteenth escape was a
    table whose 감시카메라 row printed the figure bare while a *different* row carried
    2022 and the article date — which is the shape ``docs/detection_floor.md`` §10's own
    trigger table has.  A cell reader does not read the row above for the provenance of
    this one, so neither does this.
    """
    blocks: list[tuple[int, str]] = []
    start = 1
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf
        if buf:
            blocks.append((start, "\n".join(buf)))
            buf = []

    for i, line in enumerate(text.split("\n"), start=1):
        if not line.strip():
            flush()
            continue
        if line.lstrip().startswith("|"):
            flush()
            blocks.append((i, line))
            continue
        if not buf:
            start = i
        buf.append(line)
    flush()
    return blocks


def _licensed(block: str, key: str) -> bool:
    return any(m.group(1) == key for m in SCOPE_PRAGMA.finditer(block))


def _missing(block: str, figure: dict[str, object]) -> list[str]:
    out = []
    for label in ("agency", "as_of", "scope"):
        if not any(tok in block for tok in figure[label]):  # type: ignore[operator]
            out.append(f"{label} (하나라도: {' | '.join(figure[label])})")  # type: ignore[arg-type]
    return out


@pytest.mark.parametrize("rel", GUARDED)
def test_every_external_figure_carries_agency_as_of_and_scope(rel: str) -> None:
    path = REPO / rel
    if not path.exists():  # web/finals.html is a build product
        pytest.skip(f"{rel} is not present in this checkout")
    text = path.read_text(encoding="utf-8")
    failures: list[str] = []
    for start, block in _blocks(text):
        for figure in EXTERNAL_FIGURES:
            key = figure["key"]
            if not figure["detect"].search(block):  # type: ignore[union-attr]
                continue
            if _licensed(block, str(key)):
                continue
            missing = _missing(block, figure)
            if missing:
                failures.append(
                    f"{rel}:{start} — 「{key}」 이(가) 나오는데 {', '.join(missing)} 이(가) "
                    f"같은 블록에 없습니다.\n    {figure['why']}\n"
                    f"    블록: {block[:160]}..."
                )
    assert not failures, (
        "CHARTER §3 규칙 5b: 외부 출처 수치는 기관·기준시점·범위와 함께만 적습니다.\n\n"
        + "\n\n".join(failures)
    )


def test_a_scope_pragma_states_a_reason() -> None:
    """A licence that says nothing is the shape F48 slipped through."""
    bad: list[str] = []
    for rel in GUARDED:
        path = REPO / rel
        if not path.exists():
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").split("\n"), start=1):
            for m in SCOPE_PRAGMA.finditer(line):
                if len(m.group(2).strip()) < MIN_REASON_CHARS:
                    bad.append(f"{rel}:{i} — scope-ok: {m.group(1)} 에 이유가 없습니다")
    assert not bad, "\n".join(bad)


def test_a_scope_pragma_names_a_registered_figure() -> None:
    """A key nobody registered licenses nothing, and would rot silently."""
    keys = {str(f["key"]) for f in EXTERNAL_FIGURES}
    bad: list[str] = []
    for rel in GUARDED:
        path = REPO / rel
        if not path.exists():
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").split("\n"), start=1):
            for m in SCOPE_PRAGMA.finditer(line):
                if m.group(1) not in keys:
                    bad.append(f"{rel}:{i} — 등록되지 않은 키 '{m.group(1)}'")
    assert not bad, "\n".join(bad)


#: Written to be failed.  Each is a block that prints a guarded figure with one of the
#: three labels missing; the point of keeping them is that a later edit which loosens
#: ``_missing`` or ``_blocks`` fails here rather than in a judge-facing document.
INCOMPLETE_BLOCKS: tuple[tuple[str, str], ...] = (
    ("no labels at all", "산불 신고의 99 %가 목격 신고였습니다."),
    ("agency only", "경향신문에 따르면 신고의 99 %가 목격 신고였습니다."),
    (
        "agency and date, no interim scope",
        "경향신문 2023-04-28: 산불 신고의 99 %가 목격 신고였습니다.",
    ),
    (
        "scope word but no date",
        "경향신문 보도에서 신고의 99 %가 목격 신고였고, 이는 연중 누계입니다.",
    ),
    ("camera count with no period", "경북에는 산불감시카메라 152대가 있습니다."),
    (
        "camera count, agency and date, no period",
        "경향신문 2023-04-28 기준 경북 감시카메라 152대는 최초 발견 0건이었습니다.",
    ),
    (
        "the sentence WFG-069 withdrew, verbatim",
        "한국의 산불 탐지는 사실상 전부 사람입니다. 보도된 해에 산림청·119 가 접수한 "
        "산불 신고의 99 %가 목격 신고였습니다.",
    ),
    # --- Written by this lap's independent reviewer, who had not seen the patterns.
    # Six of its eight escapes; each broke the first draft and each is now a rule.
    # They are external ground truth in the sense critic #9 asked for, and they stop
    # being that the moment they are folded in here, which is why the catch rate above
    # is quoted as the number the reviewer measured and not re-measured against these.
    (
        "reviewer #2 · a line wrap between the number and its noun",
        "산림청과 119 가 접수한 산불 신고 가운데 99 %가\n목격 신고였습니다.",
    ),
    ("reviewer #3 · the Korean word for percent", "접수된 산불 신고의 99 퍼센트가 목격 신고였습니다."),
    (
        "reviewer #4 · twenty-six characters between the halves",
        "신고의 99 %는 산림청과 119 상황실로 들어온 것 가운데 목격 신고였습니다.",
    ),
    (
        "reviewer #5 · the same gap, right to left",
        "목격에 의해 접수된 신고가 산림청 집계 기준으로 전체의 99 % 였습니다.",
    ),
    ("reviewer #6 · a decimal", "산불 신고의 99.0 %가 목격 신고였습니다."),
    (
        "reviewer #7 · the half of the camera figure that carries the meaning",
        "경북의 산불감시카메라가 산불을 최초로 발견한 건수는 0건입니다.",
    ),
)

#: The two escapes this instrument cannot close, kept as executable documentation.  A
#: string gate cannot enumerate Korean numerals, and it cannot see a claim with no digits
#: in it at all.  If either of these ever starts being caught, the rule has been widened
#: past what it can defend and this test says so out loud.
KNOWN_ESCAPES: tuple[tuple[str, str], ...] = (
    ("reviewer #12 · Korean numerals", "경북에는 산불감시카메라 백오십이 대가 있습니다."),
    ("a paraphrase with no digits", "산불 신고는 거의 전부가 목격 신고였습니다."),
)


@pytest.mark.parametrize("name,block", KNOWN_ESCAPES, ids=[n for n, _ in KNOWN_ESCAPES])
def test_the_escapes_this_gate_cannot_close_are_still_open(name: str, block: str) -> None:
    """Not a passing gate — a written-down limit, so no report can claim otherwise."""
    caught = any(f["detect"].search(block) for f in EXTERNAL_FIGURES)  # type: ignore[union-attr]
    assert not caught, (
        f"'{name}' 이(가) 이제 잡힙니다. 좋은 소식일 수도 있지만, 이 파일의 docstring 이 "
        "「잡지 못한다」고 적어 둔 항목이므로 docstring 과 보고서를 함께 고치십시오."
    )


@pytest.mark.parametrize("name,block", INCOMPLETE_BLOCKS, ids=[n for n, _ in INCOMPLETE_BLOCKS])
def test_an_unlabelled_block_is_caught(name: str, block: str) -> None:
    hit = False
    for figure in EXTERNAL_FIGURES:
        if figure["detect"].search(block) and _missing(block, figure):  # type: ignore[union-attr]
            hit = True
    assert hit, f"'{name}' 이(가) 잡히지 않습니다: {block}"


#: The complements: fully labelled blocks that must NOT fail, so the rule cannot be
#: tightened into one that no honest sentence can satisfy.
COMPLETE_BLOCKS: tuple[tuple[str, str], ...] = (
    (
        "the figure with all three labels",
        "경향신문 2023-04-28 기사의 「올해」 기준 연중 누계 잠정치로, 신고의 99 %가 "
        "목격 신고였습니다.",
    ),
    (
        "the camera count with its period",
        "경향신문 2023-04-28 기준 경북 감시카메라 152대는 2022년과 2023년 4월까지 "
        "최초 발견 0건이었습니다.",
    ),
    ("a block with neither figure", "GK2A 는 한반도를 2분마다 훑습니다."),
    ("a bare 99 % that is not this figure", "라우팅이 전체 시간의 99 % 입니다."),
    ("a bare 152 that is not this figure", "테스트가 152 초 걸렸습니다."),
)


@pytest.mark.parametrize("name,block", COMPLETE_BLOCKS, ids=[n for n, _ in COMPLETE_BLOCKS])
def test_a_labelled_block_passes(name: str, block: str) -> None:
    for figure in EXTERNAL_FIGURES:
        if figure["detect"].search(block):  # type: ignore[union-attr]
            assert not _missing(block, figure), f"'{name}' 이(가) 잘못 잡힙니다"


def test_the_withdrawn_opening_sentence_is_gone_from_the_file_it_opened() -> None:
    """WFG-069's own regression, named after the defect rather than after a spelling.

    Narrow on purpose: it asserts one deleted sentence is absent from one file, which is
    a claim this test can actually keep.  It is **not** a guard against the claim being
    rewritten — see the docstring at the top of this file, and WFG-062.
    """
    text = (REPO / "docs/detection_floor.md").read_text(encoding="utf-8")
    section = text.split("## 0.", 1)[1].split("\n## ", 1)[0]
    # drop the remainder of the heading line itself, so blocks[0] is §0's first paragraph
    section = section.split("\n", 1)[1]
    blocks = _blocks(section)
    assert blocks, "§0 이 비어 있습니다"
    assert "경북" in blocks[0][1], (
        "§0 의 첫 문단이 예상과 다릅니다 — 이 검사가 무엇을 읽고 있는지 확인하십시오"
    )
    assert "사실상 전부 사람" not in blocks[0][1], (
        "docs/detection_floor.md §0 이 다시 「탐지는 사실상 전부 사람」으로 시작합니다 "
        "(WFG-069). 크기 바닥은 위성을 배제할 뿐 사람을 옹립하지 않습니다."
    )
    # The sentence may still be quoted, but only where it is being withdrawn: a
    # withdrawal that cannot name what it withdraws is not a record (CHARTER §3 rule 7).
    for start, block in _blocks(text):
        if "사실상 전부 사람" in block:
            assert "철회" in block, (
                f"docs/detection_floor.md:{start} — 「사실상 전부 사람」이 철회 표시 없이 "
                "나옵니다 (WFG-069)."
            )
