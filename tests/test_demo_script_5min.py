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
REGISTRY = REPO / "docs" / "NUMBERS.json"

# A registry key in this repository is lower snake case with a digit-free head;
# the mapping table also cites file paths, which carry a dot or a slash.
KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")


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


def test_every_figure_the_table_calls_on_screen_is_on_the_screen(script_text):
    """A 화면 row promises the judge can see the value while the student says it."""
    html = SCREEN.read_text(encoding="utf-8")
    absent = []
    for _, value, where, source in _mapping_rows(script_text):
        if where != "화면":
            continue
        for key in _keys_in(source):
            if f'"{key}"' not in html:
                absent.append((value, key))
    assert not absent, (
        "the script tells the student to point at a value the built screen does "
        "not carry as a registry key. Either the row is 구두, or "
        "scripts/build_finals.py must ship the key: " + str(absent)
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
    assert "180개 셀 중 0승" in script_text
    assert "dispatch_order_deadline_wins_at_committed_window" in script_text


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
