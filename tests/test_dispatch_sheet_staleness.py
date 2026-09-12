"""`outputs/dispatch/README.md`'s staleness note is bound to the committed tree.

WFG-267 (iii). WFG-264 repaired the 사유 line in the emitter and
`docs/live_pipeline.md` recorded the supersession, but no file said **which printed
page** is the old one. A student at a booth, handed two sheets with two different
sentences for one code condition, cannot answer from either of those documents.

The note now says which. The danger of a note like that is the one this repository has
paid for repeatedly (WFG-117, WFG-138, WFG-262, and critic #73's own F1): a
hand-written enumeration is true when it is written and false when a later lap adds a
run directory or regenerates a sheet, and no gate sees it drift.

So this file does NOT carry the enumeration. It **re-derives** the set from the tree on
every run and asserts the note agrees with it. WFG-266's done-when (d) and WFG-271's
rewritten done-when are the precedent: a gate written against today's list inherits
today's blind spot, so the list lives in the document a human reads and the test checks
the document against the tree.

Deliberately clock-free, network-free and data-free: `git ls-files`, the two constants
parsed out of the emitter, the tracked sheets, and the note. Nothing outside the
repository, nothing regenerated, no PDF opened.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NOTE = REPO / "outputs" / "dispatch" / "README.md"
MEASURE = REPO / "scripts" / "measure_dispatch_sheet_staleness.py"
SECTION = "## ⚠ Which committed page carries the SUPERSEDED 「차량 도달 불가」 사유"


def _measure_module():
    """Load the measurement script by path, as tests/test_live_pipeline_doc_matches_code.py does."""
    sys.path.insert(0, str(REPO / "src"))
    spec = importlib.util.spec_from_file_location(
        "_wfg_measure_dispatch_sheet_staleness", MEASURE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _note_section() -> str:
    text = NOTE.read_text(encoding="utf-8")
    assert SECTION in text, (
        f"{NOTE.relative_to(REPO)} has lost the heading {SECTION!r}. That section is "
        "the only file in this repository that says which committed page carries the "
        "superseded 사유, which is WFG-267 (i). Restore it rather than deleting this "
        "test.")
    start = text.index(SECTION)
    rest = text[start + len(SECTION):]
    end = rest.find("\n## ")
    return rest if end == -1 else rest[:end]


def test_the_note_names_both_reason_constants_by_name():
    """The note must name the constants, not paraphrase them.

    A paraphrase drifts silently; a constant name sends the reader to the one place the
    sentence is defined.
    """
    section = _note_section()
    for const in ("SUPERSEDED_UNREACHABLE_REASON_KO", "UNREACHABLE_REASON_KO"):
        assert const in section, (
            f"{NOTE.relative_to(REPO)}'s staleness section does not name {const}. "
            "WFG-267 (iii) binds the note to the emitter's own constants so that "
            "renaming one breaks the page that explains it.")


def test_the_note_quotes_the_two_sentences_the_emitter_actually_defines():
    """Both 사유 sentences in the note are the literals the emitter carries today."""
    current, superseded = _measure_module().reason_constants()
    section = _note_section()
    assert superseded in section, (
        "the staleness note does not quote SUPERSEDED_UNREACHABLE_REASON_KO verbatim "
        f"({superseded!r}). A judge comparing the note with a sheet in their hand is "
        "comparing strings, so the note carries the string.")
    assert current in section, (
        "the staleness note does not quote UNREACHABLE_REASON_KO verbatim "
        f"({current!r}). Without it the note says which page is old but not what a "
        "regenerated page says instead, which is the half a student is asked for.")
    assert current != superseded


def test_the_note_names_exactly_the_stale_pdfs_the_tree_has():
    """The enumeration in the note equals the set re-derived from the tree.

    This is the whole gate. It is written so that it can FAIL IN BOTH DIRECTIONS: a
    stale PDF the note does not mention, and a path the note mentions that is no longer
    stale. A lap that adds a run directory, regenerates a sheet, or deletes one must
    update the note in the same commit.
    """
    result = _measure_module().measure()
    from_tree = set(result["stale_pdfs"])
    section = _note_section()
    named = {p for p in from_tree if p in section}
    missing = from_tree - named
    assert not missing, (
        "these committed PDFs are rendered from an HTML carrying the superseded 사유 "
        f"and {NOTE.relative_to(REPO)} does not name them: {sorted(missing)}. The note "
        "is the only place a student can look up which page in their hand is the old "
        "one, so a page it does not name is a page nobody can answer for.")

    # The other direction: every path the note lists as stale must still be stale.
    listed = [
        line.strip()[2:].strip("`")
        for line in section.split("\n")
        if line.strip().startswith("- `outputs/")
    ]
    assert listed, (
        f"{NOTE.relative_to(REPO)}'s staleness section lists no paths at all. If the "
        "tree genuinely has none, say so in prose and change this test deliberately; "
        "an empty list that used to be populated is how a note goes stale silently.")
    stray = [p for p in listed if p not in from_tree]
    assert not stray, (
        f"{NOTE.relative_to(REPO)} lists {stray} as carrying the superseded 사유, but "
        "re-deriving from the tree does not agree. Either the sheet was regenerated "
        "and the note was not updated, or the path is misspelled — and a booth "
        "instruction that points at the wrong page is worse than none.")


def test_the_measurement_refuses_to_report_zero_when_a_constant_is_gone():
    """The measurement fails loudly rather than measuring nothing.

    A staleness counter whose needle silently becomes the empty string reports a clean
    tree, which is the most dangerous possible failure for this particular gate.
    """
    mod = _measure_module()
    current, superseded = mod.reason_constants()
    assert current and superseded, "both 사유 constants must be non-empty literals"
    assert mod.EMITTER.exists()


def test_no_committed_sheet_carries_the_current_sentence():
    """Every committed sheet predates the WFG-264 repair — the control for the count.

    If this ever fails it is NOT a defect: it means a lap committed a freshly generated
    run directory, which is allowed. It fails so that the lap doing it has to read this
    docstring and update `docs/dispatch_sheet_staleness.md` §3, where the zero is stated
    as a property of the record rather than a law.
    """
    result = _measure_module().measure()
    assert result["counts"]["html_carrying_current"] == 0, (
        "a committed sheet under outputs/ now prints UNREACHABLE_REASON_KO. That is "
        "allowed — it means a run was committed after 2026-09-12 — but "
        "docs/dispatch_sheet_staleness.md §3 and the dss_html_carrying_current key "
        "both state this count as zero, so update them in the same commit.")
