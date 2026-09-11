"""WFG-259: the 영덕 dilation artifact, and the page that quotes it.

The row exists because `docs/present_perimeter_yeongdeok.md` §5 item 5 asserted two
integers that came from a reviewer probe in an ended session and lived in no artifact.
These tests are what stops that happening to §7, and what stops §7's *second* half --
the half that says the flip count does not mean what it looks like -- from being
softened by a later lap.

Committed inputs only: every assertion reads the committed artifact or the committed
registry. No route is re-run here, nothing touches the clock, the network, the
timezone, or a file outside the repository.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
ART = REPO / "data/processed/present_perimeter_buffer_shape_yeongdeok_2025.json"
ZERO = REPO / "data/processed/present_perimeter_yeongdeok_2025.json"
NUMBERS = REPO / "docs/NUMBERS.json"
DOC = REPO / "docs/present_perimeter_yeongdeok.md"

PREFIX = "ppy_yeongdeok_buf_"


@pytest.fixture(scope="module")
def art() -> dict:
    return json.loads(ART.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rows(art) -> dict:
    return {float(r["buffer_m"]): r for r in art["buffer_sensitivity"]}


@pytest.fixture(scope="module")
def moves(art) -> dict:
    return {float(r["buffer_m"]): r for r in art["transitions_out_of_still_entering"]}


def test_the_widths_are_the_three_that_were_pre_registered(art) -> None:
    """0 / 100 / 500 and nothing else.

    100 and 500 are lifted verbatim from prose written BEFORE the run, so no width
    could be chosen after the answer, and 0 is the identity control. A lap that adds
    a width to find a better-scoring opponent has crossed into WFG-033(b), which is
    NH-027 and the author's; this gate is where that shows up.
    """
    assert art["buffers_m"] == [0.0, 100.0, 500.0]
    assert len(art["buffer_sensitivity"]) == 3


def test_the_identity_control_reproduces_the_committed_zero_buffer_outcome(rows) -> None:
    """d = 0 must give back the committed 26 / 16 / 2, or the harness is wrong."""
    committed = json.loads(ZERO.read_text(encoding="utf-8"))["outcomes"]
    z = rows[0.0]
    for k in ("saved", "still_enters_forecast", "not_reached", "origin_removed_by_filter"):
        assert z[k] == committed[k], f"d = 0 {k}: {z[k]} != committed {committed[k]}"
    assert z["n_nodes_removed"] == 162


def test_the_100m_set_is_a_strict_superset_of_the_162(rows) -> None:
    """What §5 item 5 itself asserts, checked rather than assumed."""
    assert rows[100.0]["n_nodes_removed"] > rows[0.0]["n_nodes_removed"] == 162


def test_the_reviewer_probe_reproduces(moves, art) -> None:
    """§5 item 5's two figures, including the origin id it names.

    This is the half of WFG-259 that CONFIRMS the page. It is graded by the origin
    id and not only by the count, because a count that happened to match while a
    different origin moved would be a coincidence dressed as a reproduction.
    """
    assert moves[100.0]["n_of_those_now_saved"] == 1
    assert moves[100.0]["origins_now_saved"] == [11935180417]
    assert moves[500.0]["n_still_entering_at_zero"] == 16
    assert moves[500.0]["n_of_those_now_saved"] == 15
    assert 11935180417 in moves[500.0]["origins_now_saved"]


def test_the_dilated_arm_saves_fewer_at_both_widths(rows) -> None:
    """The half that kills the inference, and the one a later lap might soften.

    「At 500 m, 15 of the 16 flip」 reads as 「a buffered opponent recovers all but
    one of the 42」. It does not: the dilated arm's own `saved` count is LOWER than
    the zero-buffer 26 at both widths, because the dilated set swallows the origins
    the zero-buffer arm was saving. If this ever stops being true the page's §7.2 is
    wrong and must be rewritten, not quietly left standing.
    """
    assert rows[100.0]["saved"] < rows[0.0]["saved"]
    assert rows[500.0]["saved"] < rows[0.0]["saved"]
    # and the mechanism: the loss is origins refused outright, not origins rerouted
    # into the forecast.
    assert rows[500.0]["origin_removed_by_filter"] == 23
    assert rows[500.0]["still_enters_forecast"] == 0


def test_every_buffer_row_accounts_for_all_44_origins(rows) -> None:
    for d, r in rows.items():
        total = (r["saved"] + r["still_enters_forecast"] + r["not_reached"]
                 + r["origin_removed_by_filter"])
        assert total == 44 == r["n_target"], f"buffer {d} m accounts for {total}"


def test_the_registry_keys_match_the_artifact_cell_for_cell(art) -> None:
    """Every ppy_yeongdeok_buf_ key re-derives from its own json_path."""
    numbers = json.loads(NUMBERS.read_text(encoding="utf-8"))["numbers"]
    keys = {k: v for k, v in numbers.items() if k.startswith(PREFIX)}
    assert len(keys) == 8, f"expected 8 {PREFIX} keys, found {len(keys)}"
    for key, entry in keys.items():
        cur = art
        for part in entry["json_path"].split("."):
            cur = cur[int(part)] if isinstance(cur, list) else cur[part]
        assert cur == entry["value"], f"{key}: registry {entry['value']} != artifact {cur}"
        assert entry["source_file"] == (
            "data/processed/present_perimeter_buffer_shape_yeongdeok_2025.json")


def test_the_doc_quotes_the_artifact_and_not_a_memory() -> None:
    """Every integer §7.1's table prints beside a key equals that key's value."""
    numbers = json.loads(NUMBERS.read_text(encoding="utf-8"))["numbers"]
    text = DOC.read_text(encoding="utf-8")
    hits = re.findall(r"`(" + PREFIX + r"\w+)`\s*\*{0,2}(\d+)\*{0,2}", text)
    assert len(hits) >= 6, f"§7 quotes only {len(hits)} keyed figures"
    for key, printed in hits:
        assert key in numbers, f"{key} is quoted in the doc and is not registered"
        assert int(printed) == numbers[key]["value"], (
            f"{key}: the page prints {printed}, the registry holds "
            f"{numbers[key]['value']}")


def test_the_page_still_refuses_the_bias_direction_sentence() -> None:
    """WFG-259's second half came out NOT LICENSED, and §7.3 item 5 records it.

    The row asked for a sentence saying the fair opponent is systematically weakened
    by this project's own input coarseness, in this project's favour. The argument
    rested on dilation moving origins INTO `saved`; the run measures the net saved
    count going DOWN. A later lap that writes the sentence anyway has to delete this
    refusal first, and that is the point of the gate.
    """
    text = DOC.read_text(encoding="utf-8")
    assert "No sentence asserting the direction of" in text
    assert "may be written on any surface, in either direction, on this evidence" in text


def test_the_page_does_not_call_the_dilated_arm_an_opponent_of_record() -> None:
    """WFG-033(b) and NH-027 are the author's, and §7 says so in both directions."""
    text = DOC.read_text(encoding="utf-8")
    assert "WFG-033(b)" in text and "NH-027" in text
    for banned in ("the optimal buffer", "the best buffer width is",
                   "500 m recovers all but one of the 42.",
                   "the buffered opponent is stronger"):
        assert banned not in text, f"§7 asserts {banned!r}"
