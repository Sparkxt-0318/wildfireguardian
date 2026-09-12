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

import pytest

REPO = Path(__file__).resolve().parents[1]
NOTE = REPO / "outputs" / "dispatch" / "README.md"
MEASURE = REPO / "scripts" / "measure_dispatch_sheet_staleness.py"
SECTION = "## ⚠ Which committed page carries the SUPERSEDED 「차량 도달 불가」 사유"

#: ⚠ TWO files enumerate the stale sheets, and both are gated, because this lap's own
#: `sip` pass caught the second one unguarded. `outputs/dispatch/README.md` is the note
#: beside the sheets and `docs/dispatch_sheet_staleness.md` §3 is the method page a judge
#: may open; a gate that bound only the first would let the second go stale in silence,
#: which is the exact class critic #73 filed F1 about. Each entry is (path, heading of
#: the enumerating section); the paths themselves are never listed here — every test
#: below re-derives them from the tree.
ENUMERATING_PAGES = [
    (NOTE, SECTION),
    (REPO / "docs" / "dispatch_sheet_staleness.md", "## 3. 결과"),
]


def _load(name: str, path: Path):
    """Load a script by path, as tests/test_live_pipeline_doc_matches_code.py does."""
    sys.path.insert(0, str(REPO / "src"))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _measure_module():
    return _load("_wfg_measure_dispatch_sheet_staleness", MEASURE)


def _section(page: Path, heading: str) -> str:
    """The body of `heading`'s section in `page`, up to the next `## `."""
    text = page.read_text(encoding="utf-8")
    assert heading in text, (
        f"{page.relative_to(REPO)} has lost the heading {heading!r}. These sections are "
        "what says which committed page carries the superseded 사유, which is "
        "WFG-267 (i). Restore it rather than deleting this test.")
    start = text.index(heading)
    rest = text[start + len(heading):]
    end = rest.find("\n## ")
    return rest if end == -1 else rest[:end]


def _note_section() -> str:
    return _section(NOTE, SECTION)


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


@pytest.mark.parametrize("page,heading",
                         ENUMERATING_PAGES,
                         ids=lambda v: str(v)[-40:])
def test_every_enumerating_page_names_exactly_the_stale_pdfs_the_tree_has(page, heading):
    """Each enumeration equals the set re-derived from the tree.

    This is the whole gate. It is written so that it can FAIL IN BOTH DIRECTIONS: a
    stale PDF a page does not mention, and a path a page mentions that is no longer
    stale. A lap that adds a run directory, regenerates a sheet, or deletes one must
    update BOTH pages in the same commit.
    """
    result = _measure_module().measure()
    from_tree = set(result["stale_pdfs"])
    section = _section(page, heading)
    rel = page.relative_to(REPO)
    missing = {p for p in from_tree if p not in section}
    assert not missing, (
        "these committed PDFs are rendered from an HTML carrying the superseded 사유 "
        f"and {rel} does not name them: {sorted(missing)}. These pages are the only "
        "place a student can look up which page in their hand is the old one, so a "
        "sheet they do not name is a sheet nobody can answer for.")

    # The other direction: every path the page lists as stale must still be stale.
    listed = [
        line.strip()[2:].strip("`")
        for line in section.split("\n")
        if line.strip().startswith("- `outputs/")
    ]
    assert listed, (
        f"{rel}'s staleness section lists no paths at all. If the tree genuinely has "
        "none, say so in prose and change this test deliberately; an empty list that "
        "used to be populated is how a page goes stale silently.")
    stray = [p for p in listed if p not in from_tree]
    assert not stray, (
        f"{rel} lists {stray} as carrying the superseded 사유, but re-deriving from "
        "the tree does not agree. Either the sheet was regenerated and the page was "
        "not updated, or the path is misspelled — and a booth instruction that points "
        "at the wrong page is worse than none.")


def test_the_measurement_refuses_to_report_zero_when_a_constant_is_gone():
    """The measurement fails loudly rather than measuring nothing.

    A staleness counter whose needle silently becomes the empty string reports a clean
    tree, which is the most dangerous possible failure for this particular gate.
    """
    mod = _measure_module()
    current, superseded = mod.reason_constants()
    assert current and superseded, "both 사유 constants must be non-empty literals"
    assert mod.EMITTER.exists()


def test_a_second_route_that_imports_nothing_finds_the_same_stale_set():
    """Independence check: re-derive the set WITHOUT `measure()`, and without the emitter.

    Found by this lap's independent reviewer, under `mandela`'s tautology pattern. Every
    other test in this file calls `measure()` — the same function that produced the
    committed artifact, the two enumerating pages and the six `dss_` keys. Scorer and
    subject were the same code, so a wrong glob or a mis-parsed constant would have made
    the artifact, the pages, the registry and the gate wrong TOGETHER, and this file
    would still have been green. The lap struck the word 「control」 off
    `dss_html_carrying_current` for exactly that reason and then left the gate with the
    identical shape.

    So this test walks a different road to the same place: it reads the two sentences out
    of the COMMITTED ARTIFACT rather than parsing the emitter, and it globs the tree with
    `git ls-files` directly rather than calling `tracked_outputs()`. The two routes share
    only the repository itself. They must agree.
    """
    import json  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    art_dir = REPO / "data" / "processed" / "dispatch_sheet_staleness"
    artifacts = sorted(art_dir.glob("staleness_*.json"))
    assert artifacts, f"no committed staleness artifact under {art_dir.relative_to(REPO)}"
    art = json.loads(artifacts[-1].read_text(encoding="utf-8"))
    superseded = art["reasons"]["superseded"]

    listing = subprocess.run(["git", "ls-files", "-z", "outputs"], cwd=REPO,
                             capture_output=True, text=True, check=True).stdout
    files = [f for f in listing.split("\0") if f]
    stale_by_hand = sorted(
        p for p in files
        if p.endswith(".pdf")
        and (p[:-4] + ".html") in files
        and superseded in (REPO / (p[:-4] + ".html")).read_text(encoding="utf-8")
    )

    assert stale_by_hand == sorted(art["stale_pdfs"]), (
        "two independent derivations of the stale set disagree. The committed artifact "
        f"says {sorted(art['stale_pdfs'])} and a scan that imports none of the "
        f"measurement code says {stale_by_hand}. One of them is wrong, and until you "
        "know which, neither the note nor the dss_ keys can be trusted.")

    # And the same for the headline counts, so a miscount cannot hide behind a correct list.
    htmls = [f for f in files if f.endswith(".html")]
    assert len([f for f in files if f.endswith(".pdf")]) == art["counts"]["tracked_pdf"]
    assert len(htmls) == art["counts"]["tracked_html"]
    assert sum(
        1 for h in htmls
        if superseded in (REPO / h).read_text(encoding="utf-8")
    ) == art["counts"]["html_carrying_superseded"]


def test_the_pdf_bytes_themselves_agree_with_the_render_path_classing():
    """A third route, which never looks at an HTML file at all.

    The reviewer that blocked this lap refused the caveat 「no extractor, SO we classify
    by the sibling HTML」 as a non-sequitur, and was right: these sheets embed a Korean
    font SUBSET, a subset holds only the glyphs the page actually set, and the
    `/ToUnicode` CMaps that name them are Flate streams that `zlib` opens. So the PDFs
    can be interrogated directly, with the standard library, and that is an independent
    check on the classing rather than a restatement of it.

    One-directional by construction, and the assertion is written to match: a subset is
    a property of the WHOLE page, so a syllable could in principle arrive from other
    text. What it can establish is that a sheet classed stale CAN spell the superseded
    sentence and CANNOT spell the current one, which is enough to catch a PDF that was
    swapped or re-rendered away from its sibling HTML — the one failure the render-path
    method is blind to.
    """
    probe = _load("_wfg_probe_dispatch_pdf_fonts",
                  REPO / "scripts" / "probe_dispatch_pdf_fonts.py")
    current, superseded = probe._reasons()

    def hangul(s: str) -> set[str]:
        return {c for c in s if "가" <= c <= "힣"}

    only_sup = hangul(superseded) - hangul(current)
    only_cur = hangul(current) - hangul(superseded)
    assert only_sup and only_cur, (
        "the two 사유 sentences no longer have syllables unique to each, so this probe "
        "cannot discriminate them. Re-think the test rather than deleting it.")

    stale = set(_measure_module().measure()["stale_pdfs"])
    for rel in sorted(stale):
        cps = probe._codepoints(REPO / rel)
        assert only_sup <= cps, (
            f"{rel} is classed stale from its sibling HTML, but its own embedded font "
            f"subset cannot spell the superseded 사유 (missing {sorted(only_sup - cps)}). "
            "Either the PDF was re-rendered or swapped away from its HTML, or the "
            "classing is wrong. Both matter more than this test.")
        assert not only_cur <= cps, (
            f"{rel} is classed stale, yet its font subset can spell the CURRENT 사유. "
            "That is the opposite of what the render path says; resolve it before "
            "trusting either page.")


def test_only_runs_committed_after_the_repair_carry_the_current_sentence():
    """The control for the count, re-pointed 2026-09-12 (NH-057).

    Until 2026-09-12 no committed sheet carried the current 사유, because every one
    predated the WFG-264 repair, and this test asserted zero. That day the author's
    laptop run on the real spread surface was committed under
    ``outputs/dispatch_real_hazard/20260912T153043Z/``. The property is now: a sheet
    that prints the current sentence lives only under a run directory stamped on or
    after 2026-09-12, and every sheet that predates the repair still does not.
    If this fails, read ``docs/dispatch_sheet_staleness.md`` §3 and move it with the tree.
    """
    mod = _measure_module()
    current, _superseded = mod.reason_constants()
    htmls = [f for f in mod.tracked_outputs() if f.endswith(mod.HTML_SUFFIX)]
    carrying = [h for h in htmls if current in (REPO / h).read_text(encoding="utf-8")]
    result = mod.measure()
    assert len(carrying) == result["counts"]["html_carrying_current"]
    for h in carrying:
        stamp = Path(h).parts[2] if len(Path(h).parts) > 2 else ""
        assert stamp[:8].isdigit() and stamp[:8] >= "20260912", (
            f"{h} prints UNREACHABLE_REASON_KO but sits under a run directory stamped before "
            "the WFG-264 repair (2026-09-12). Committed sheets are the record and are never "
            "rewritten; a sheet that predates the repair cannot carry the sentence the emitter "
            "prints today unless something rewrote it.")
