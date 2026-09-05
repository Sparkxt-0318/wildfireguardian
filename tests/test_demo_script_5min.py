"""The 5-minute booth script is bound to the registry and to the built screen.

WFG-003. `docs/auto/DEMO_SCRIPT_5MIN.md` is the only document in this repository
whose sentences are spoken out loud to a judge, so the failure it can produce is
worse than a wrong document: the student says a number the screen does not show,
or a number that traces to nothing, and cannot recover in the five minutes.

The root objection this lap recorded against its own plan was that a demo script
is prose about a screen the loop cannot rehearse, and that writing it is another
document rather than product. These tests are the answer to the second half: the
script's §3 mapping table is machine-read, every key in it must resolve in
`docs/NUMBERS.json`, and every key the table marks 화면 must actually be present
in the built `web/finals.html`. The first half - whether five minutes of Korean
fits in five minutes - a test cannot answer, and §5 of the document says so.

No clock, no timezone, no network, no file outside the repository (CHARTER §4b).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "docs" / "auto" / "DEMO_SCRIPT_5MIN.md"
SCREEN = REPO / "web" / "finals.html"
TEMPLATE = REPO / "scripts" / "finals.template.html"
REGISTRY = REPO / "docs" / "NUMBERS.json"

# A registry key in this repository is lower snake case with a digit-free head;
# the mapping table also cites file paths, which carry a dot or a slash.
KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")

# Numbers a spoken sentence may emphasise that are NOT results: thresholds,
# instrument constants and bin edges that come from the method, not from a
# measurement. Every entry needs a reason, and a measured value must never be
# parked here to get a test green.
THRESHOLDS = {
    "100": "the 100 ha bin edge the KFS containment artifact bins on, not a result",
}


@pytest.fixture(scope="module")
def script_text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))["numbers"]


def _mapping_rows(text: str) -> list[tuple[str, str, str, str]]:
    """Rows of the §3 table: (구간, 값, 화면/구두, 출처)."""
    rows = []
    in_table = False
    for line in text.splitlines():
        if line.startswith("| 구간 | 값 |"):
            in_table = True
            continue
        if in_table:
            if not line.startswith("|"):
                break
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) != 4 or set(cells[0]) <= {"-", ":"}:
                continue
            rows.append(tuple(cells))  # type: ignore[arg-type]
    return rows


def _keys_in(cell: str) -> list[str]:
    return [t for t in re.findall(r"`([^`]+)`", cell) if KEY_RE.match(t)]


def test_the_mapping_table_is_parseable_and_not_empty(script_text):
    rows = _mapping_rows(script_text)
    assert len(rows) >= 25, (
        "the §3 mapping table lost rows, or its header changed and this test is "
        f"now reading nothing: parsed {len(rows)}"
    )


def test_every_registry_key_the_script_speaks_resolves(script_text, registry):
    unresolved = []
    for _, value, _, source in _mapping_rows(script_text):
        for key in _keys_in(source):
            if key not in registry:
                unresolved.append((value, key))
    assert not unresolved, (
        "the booth script quotes numbers whose registry keys do not exist; the "
        "student would be saying a number that traces to nothing: "
        f"{unresolved}"
    )


def test_every_figure_the_table_calls_on_screen_is_actually_rendered(script_text):
    """A 화면 row promises the judge can SEE the value while the student says it.

    Presence in the built `web/finals.html` is not that promise and this test
    used to make that mistake. `build_finals.py` embeds the whole registry slice
    as one JSON blob, so every declared key appears in the file exactly once
    whether or not any card reads it; the independent reviewer of the lap that
    wrote this document showed that four rows were labelled 화면 on that
    evidence alone, and two of them are contradicted by what the screen really
    renders. The card is in the template, so the template is what decides.
    """
    tpl = TEMPLATE.read_text(encoding="utf-8")
    html = SCREEN.read_text(encoding="utf-8")
    unrendered = []
    for _, value, where, source in _mapping_rows(script_text):
        if where != "화면":
            continue
        for key in _keys_in(source):
            if key not in tpl or f'"{key}"' not in html:
                unrendered.append((value, key))
    assert not unrendered, (
        "the script tells the student to point at a value no card on the screen "
        "draws. Either the row is 구두, or scripts/finals.template.html must "
        "render it: " + str(unrendered)
    )


def test_a_spoken_only_row_is_never_labelled_as_being_on_the_screen(script_text):
    """The 구두 label is the honest half and must stay non-empty.

    Without this, a later lap could relabel every row 화면 and the test above
    would pass by having nothing left to compare.
    """
    wheres = {row[2] for row in _mapping_rows(script_text)}
    assert wheres <= {"화면", "구두"}, f"unknown 화면/구두 label: {wheres}"
    assert "구두" in wheres, (
        "every row now claims to be on the screen. Six figures the script speaks "
        "(the fire-blind-vs-time-aware origin counts and the pipeline latency) "
        "are not registry keys on web/finals.html and must stay labelled 구두."
    )


def _numbers_in(text: str) -> list[str]:
    return [n.replace(",", "").rstrip(".")
            for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)]


def test_every_value_cell_equals_the_registry_value_it_cites(script_text, registry):
    """The 값 column is the number the student says. It must be the real one.

    Without this the table can cite a correct key beside a wrong number, which
    is the failure that puts a fabricated figure in a judge's ear while every
    other gate stays green.
    """
    wrong = []
    for act, value, _, source in _mapping_rows(script_text):
        keys = _keys_in(source)
        if len(keys) != 1:
            continue  # rows sourced to a file path, checked by the reader
        entry = registry.get(keys[0])
        if entry is None:
            continue  # the resolve test owns this failure
        raw = entry["value"]
        if not isinstance(raw, (int, float)) or isinstance(raw, bool):
            continue
        spoken = _numbers_in(value)
        ok = False
        for token in spoken:
            places = len(token.split(".")[1]) if "." in token else 0
            # a fraction in the registry may be spoken as a percentage
            if token == f"{round(float(raw), places):.{places}f}".rstrip("."):
                ok = True
            if token == f"{round(float(raw) * 100, places):.{places}f}".rstrip("."):
                ok = True
        if not ok:
            wrong.append((act, value, keys[0], raw))
    assert not wrong, (
        "a 값 cell does not match the registry value of the key beside it "
        "(act, spoken, key, registry): " + str(wrong)
    )


def test_every_figure_the_student_says_aloud_is_in_the_mapping_table(script_text):
    """§3 must cover §1's mouth, not just itself.

    The lap that wrote this document graded its own gate 6 of 6 against six
    mutations, and the independent reviewer broke it in one edit anyway: change
    a bolded number in the spoken body and leave the table alone, and nothing in
    the tree objected. §3 is only worth having if it is a cover of what is
    actually said, so every emphasised number in a spoken line must appear in
    the table or be a declared threshold.
    """
    body = script_text.split("## 1. 대본", 1)[1].split("## 2. 끼어들 때", 1)[0]
    spoken = " ".join(l[2:] for l in body.splitlines() if l.startswith("> "))
    said = set()
    for span in re.findall(r"\*\*(.+?)\*\*", spoken, re.S):
        said.update(_numbers_in(span))
    tabled = set()
    for _, value, _, _ in _mapping_rows(script_text):
        tabled.update(_numbers_in(value))
    uncovered = sorted(said - tabled - set(THRESHOLDS))
    assert not uncovered, (
        "the script emphasises numbers that §3 does not source, so the student "
        "would say them with nothing behind them: " + str(uncovered)
    )


def test_the_acts_add_up_to_five_minutes(script_text):
    """Per-act timings are contiguous, and the last one ends at 5:00."""
    heads = re.findall(
        r"^### .*?\((\d):(\d\d) → (\d):(\d\d)\) · (\d+)초", script_text, re.M
    )
    assert len(heads) == 6, f"expected six timed segments, parsed {len(heads)}"
    cursor = 0
    total = 0
    for m0, s0, m1, s1, stated in heads:
        start = int(m0) * 60 + int(s0)
        end = int(m1) * 60 + int(s1)
        assert start == cursor, f"segment starting {m0}:{s0} leaves a gap or overlaps"
        assert end - start == int(stated), (
            f"segment {m0}:{s0}-{m1}:{s1} says {stated}s but spans {end - start}s"
        )
        cursor = end
        total += end - start
    assert total == 300, f"the five-minute script runs {total}s"
    assert cursor == 300


def test_the_draft_label_is_on_the_file(script_text):
    """CHARTER §9: text meant for the student's own voice is labelled where read."""
    head = script_text.split("---", 1)[0]
    assert "DRAFT" in head or "초안" in head


def test_the_script_keeps_the_result_that_lost(script_text):
    """CHARTER §3.5: when a result is weak the artifact says so.

    The dispatch-ordering rule loses at the committed window, and the registry
    entry's own caveat opens `⚠ THE SHIPPED ORDERING LOSES`. A booth script that
    quietly drops it is the failure this repository exists to gate against, so
    the sentence is pinned here rather than left to a reviewer's memory.
    """
    assert "0승" in script_text
    assert "dispatch_order_deadline_wins_at_committed_window" in script_text
    # and the screen's own figure, which is a different slice of the same result
    assert "dispatch_order_deadline_wins_pct" in script_text


def test_every_judge_type_has_exactly_one_interruption_sentence(script_text):
    """WFG-003: one sentence per judge type, for the five lenses the critic uses."""
    block = script_text.split("## 2. 끼어들 때", 1)[1].split("## 3.", 1)[0]
    rows = [l for l in block.splitlines()
            if l.startswith("|") and not set(l.strip()) <= {"-", ":", " ", "|"}]
    # header + five judge rows
    assert len(rows) == 6, f"expected five judge rows, parsed {len(rows) - 1}"
    for line in rows[1:]:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        assert len(cells) == 4
        assert cells[2], f"no sentence for judge type {cells[0]}"


def test_the_default_region_the_script_assumes_is_the_one_the_screen_ships():
    """§0 tells the student to check the region; §1's act-3 numbers depend on it.

    If a later lap changes `default_region` in the builder, act 3 would quote
    의성·안동's counts over a screen showing another region.
    """
    builder = (REPO / "scripts" / "build_finals.py").read_text(encoding="utf-8")
    m = re.search(r'"default_region":\s*"([a-z0-9_]+)"', builder)
    assert m, "build_finals.py no longer declares a default_region"
    assert m.group(1) == "uiseong_andong_2025", (
        "the screen's default region moved; DEMO_SCRIPT_5MIN.md §0 and act 3 "
        f"still assume 의성·안동, but the builder now ships {m.group(1)}"
    )
    assert "의성·안동(2025)" in SCRIPT.read_text(encoding="utf-8")


DROP_MARKER = "[버림]"


def _spoken_lines_with_the_drop_marker(text: str) -> list[str]:
    """The §1 lines that carry the [버림] marker, quoted lines only.

    The ⚠ blocks talk *about* the marker in prose and must not be counted as
    one; only a `> ` line is something the student says.
    """
    body = text.split("## 1. 대본", 1)[1].split("## 2. 끼어들 때", 1)[0]
    return [line[2:] for line in body.splitlines()
            if line.startswith("> ") and DROP_MARKER in line]


def test_a_droppable_sentence_takes_its_own_number_with_it(script_text):
    """WFG-095: the marker never sits on a caveat whose claim stays behind.

    The script tells a student who is running long which sentence to cut. When
    that marker sits on a caveat-only sentence, cutting it leaves the number the
    caveat was guarding in the judge's ear with nothing qualifying it - which is
    how critic #15 found 2막 and 3막: dropping 2막's marked line left 1막's
    22/34/64분 and 2막's 79.23 % spoken as if they were the same clock (the
    WFG-053 conflation, NH-018/NH-019), and dropping 3막's left four regional
    percentages with nothing saying OSM mapping density is inside the difference,
    while §4 item 4 of the same document lists 지역 간 순위 among the sentences
    this script never says. Both deletions were measured against every claim gate
    in the tree and all of them exited 0.

    The invariant this pins is the one §1 now states: a marker only ever goes on a
    sentence that carries its own number, so cutting it cuts the number too.
    Caveats that guard a surviving claim live in the ⚠ blocks instead.

    What this cannot catch: it reads the marker's own line, not the whole
    sentence-group the student would drop, so a marker moved to the *head* of a
    numbered group would still pass. It is the head of the run that has been
    getting this wrong, and a stricter test would need a closing marker the
    spoken text should not have to carry.
    """
    marked = _spoken_lines_with_the_drop_marker(script_text)
    assert marked, (
        "no spoken line carries the [버림] marker any more; §1 tells a student "
        "who is running long to drop the marked sentence, and there is none"
    )
    tabled = set()
    for _, value, _, _ in _mapping_rows(script_text):
        tabled.update(_numbers_in(value))
    naked = [line for line in marked
             if not (set(_numbers_in(line)) & (tabled | set(THRESHOLDS)))]
    assert not naked, (
        "a [버림] marker sits on a sentence carrying no sourced number of its "
        "own. Dropping it drops a caveat and leaves the claim it guards: "
        + str(naked)
    )


def test_the_rule_that_places_the_marker_is_written_down(script_text):
    """The bad placements came from the rule, not from two slips.

    §1 used to say 「넘치면 그 구간의 마지막 문장을 버리고」 - drop the *last*
    sentence - and a well-written segment ends on its caveat, so the rule
    manufactured the failure above twice. Re-introducing that rule would
    reproduce it in the next segment anyone adds, and the test above would not
    see it until the marker moved.
    """
    body = script_text.split("## 1. 대본", 1)[1].split("### 도입", 1)[0]
    assert "표시한 문장을 버리고" in body, (
        "§1 no longer says that the marked sentence is the one to drop"
    )
    assert "단서만 있는 문장에는 붙이지 않습니다" in body, (
        "§1 no longer forbids marking a caveat-only sentence as droppable"
    )
