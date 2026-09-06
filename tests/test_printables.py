"""Gates for the booth printables (WFG-007).

The thing being protected is a sheet of paper a judge is holding, and the
failure mode that matters is not a crash: it is a blank where a Korean word
should be. matplotlib draws a missing glyph as nothing and warns, so every test
here is ultimately about whether the committed font subset can draw what the
build hands it.

Two defects from this row's own build are pinned as regressions below, because
both got past the first version of the gate and both were invisible in the exit
code:

  * the renderer's own bullet marker was U+2022, which is in NO source document
    and NOT in the Sans KR subset, so a gate that reads the sources could not
    see it; and
  * table and code lines went to IBM Plex Mono, which has 229 codepoints and no
    hangul at all, so a Korean table row would have printed as blanks.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_printables.py"
DOC = ROOT / "docs" / "printables.md"
OUT_DIR = ROOT / "docs" / "auto" / "finals" / "printables"

sys.path.insert(0, str(ROOT / "scripts"))
import build_printables as bp  # noqa: E402


# --------------------------------------------------------------------------
# The font-coverage contract
# --------------------------------------------------------------------------

def test_every_source_character_can_be_drawn() -> None:
    """The pre-flight gate, run on the tree as it stands.

    This is the check that decides whether the printables can be built at all,
    so it runs on the real sources rather than a fixture: a document that grows
    a new symbol should fail HERE, in the suite, and not at the printer.
    """
    cps = bp.font_codepoints(bp.REGULAR_WOFF2) & bp.font_codepoints(bp.SEMIBOLD_WOFF2)
    texts = {rel: (ROOT / rel).read_text(encoding="utf-8") for rel, _ in bp.SOURCES}
    bad = bp.check_coverage(texts, cps)
    assert not bad, (
        "the committed font subset cannot draw these characters, so the "
        "printable would carry blanks: "
        + "; ".join(f"{k}: {''.join(v)}" for k, v in bad.items())
        + ". Add each to SUBSTITUTIONS in scripts/build_printables.py or remove "
          "it from the source."
    )


def test_the_bullet_marker_the_renderer_adds_is_in_the_font() -> None:
    """Regression: the renderer's own furniture is not covered by a source scan.

    The first build used U+2022 BULLET for list items. It appears in none of the
    four source documents, so check_coverage passed, and it is absent from
    IBMPlexSansKR-Regular.woff2, so every bullet on 29 pages was a blank plus a
    matplotlib warning nobody was reading.
    """
    cps = bp.font_codepoints(bp.REGULAR_WOFF2)
    assert ord("•") not in cps, (
        "U+2022 is now IN the font subset, so this regression's premise has "
        "changed; re-check which marker scripts/build_printables.py uses")
    blocks = bp.parse_markdown("- 항목 하나\n- 항목 둘\n")
    drawn = {ch for b in blocks for ch in bp.substitute(b.text)}
    missing = sorted(c for c in drawn if c not in "\n\r\t " and ord(c) not in cps)
    assert not missing, (
        f"the list renderer emits characters the font cannot draw: {missing}")


def test_mono_cannot_draw_hangul_and_the_renderer_knows_it() -> None:
    """Regression: Korean table rows were being sent to a Latin-only face.

    IBM Plex Mono is used for tables and code so columns line up. It carries no
    hangul, so the renderer must fall back to the Sans face for any line it
    cannot draw. This test pins the fact that makes the fallback necessary, so
    that removing the fallback fails here rather than on paper.
    """
    mono = bp.font_codepoints(bp.MONO_WOFF2)
    assert ord("가") not in mono, (
        "IBM Plex Mono now carries hangul; the fallback in Renderer.draw can be "
        "revisited, but check the whole syllable range, not one character")
    assert ord("A") in mono and ord("|") in mono


# --------------------------------------------------------------------------
# The build itself
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> dict:
    """Build into a temporary directory: the suite never writes to docs/."""
    out = tmp_path_factory.mktemp("printables")
    return bp.build("29991231T2359Z", out)


def test_the_build_produces_a_pdf_with_pages_for_every_source(built: dict) -> None:
    assert built["pages"] > 0
    assert set(built["pages_per_source"]) == {rel for rel, _ in bp.SOURCES}
    for rel, n in built["pages_per_source"].items():
        assert n >= 1, f"{rel} produced no page"


def test_nothing_uncovered_reached_a_page(built: dict) -> None:
    """The post-layout gate reported clean, and the manifest says so.

    build() raises SystemExit(2) when a character reaches a face that cannot
    draw it, so reaching this assertion at all is the result; the manifest
    fields are checked so a later refactor cannot quietly stop recording it.
    """
    assert built["font_codepoints"] > 2000
    assert "mono_fallback_lines" in built, (
        "the manifest no longer records how many lines fell back off the mono "
        "face, so a growing alignment loss would be invisible")
    assert isinstance(built["mono_fallback_lines"], int)


def test_two_builds_at_the_same_stamp_are_byte_identical(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Determinism, so a rebuild can be compared instead of trusted.

    matplotlib stamps a PDF with the wall clock unless CreationDate is set. If
    that regressed, every rebuild would differ and nothing downstream could tell
    a real change from a re-run.
    """
    a = bp.build("29991231T2359Z", tmp_path_factory.mktemp("a"))
    b = bp.build("29991231T2359Z", tmp_path_factory.mktemp("b"))
    assert a["pdf_sha256"] == b["pdf_sha256"], (
        "two builds at the same stamp differ; the PDF has picked up a "
        "wall-clock or a temporary path")


def test_the_pdf_embeds_truetype_outlines() -> None:
    """pdf.fonttype must stay 42.

    At the default (Type 3) matplotlib inlines glyph procedures, and several
    PDF viewers and printer RIPs render CJK from Type 3 badly or not at all.
    This one rcParam decides whether the Korean survives printing.
    """
    import matplotlib
    assert matplotlib.rcParams["pdf.fonttype"] == 42


# --------------------------------------------------------------------------
# Markdown handling that is about the paper, not about markdown
# --------------------------------------------------------------------------

def test_gate_pragmas_do_not_reach_the_paper() -> None:
    """HTML comments in these sources are check_forbidden.py pragmas.

    The first preview printed "<!-- forbidden-ok: 신고보다 -->" in the middle of
    a judge-facing answer card. Repository machinery on a handout.
    """
    blocks = bp.parse_markdown("답변입니다.\n<!-- forbidden-ok: 신고보다 -->\n다음 줄.\n")
    text = " ".join(b.text for b in blocks)
    assert "forbidden-ok" not in text and "<!--" not in text


def test_unclosed_emphasis_does_not_print_its_asterisks() -> None:
    """A bold span that opens on one line and closes on another.

    This parser works a line at a time, so neither regex matches, and the first
    preview printed literal asterisks on six lines of page 1. On paper that
    reads as a typo.
    """
    blocks = bp.parse_markdown("**행 WFG-037 · 준비도 R3\n게이트: tests/test_booth_setup.py**\n")
    for b in blocks:
        assert "**" not in b.text, f"asterisks survive into the page: {b.text!r}"


def test_table_separator_rows_are_dropped() -> None:
    blocks = bp.parse_markdown("| 시점 | 무엇 |\n|---|---|\n| 10-23 | 짐 |\n")
    texts = [b.text for b in blocks if b.kind == "code"]
    assert not any(set(t) <= set("|- :") for t in texts), (
        f"a markdown table separator row printed as dashes: {texts}")
    assert any("시점" in t for t in texts)


def test_every_substitution_target_is_itself_drawable() -> None:
    """A substitution that maps one missing glyph onto another fixes nothing."""
    cps = bp.font_codepoints(bp.REGULAR_WOFF2) & bp.font_codepoints(bp.SEMIBOLD_WOFF2)
    for src, dst in bp.SUBSTITUTIONS.items():
        bad = [c for c in dst if ord(c) not in cps]
        assert not bad, (
            f"SUBSTITUTIONS maps {src!r} to {dst!r}, which the font still "
            f"cannot draw: {bad}")


# --------------------------------------------------------------------------
# The documentation contract (CHARTER §4 step 4, §9)
# --------------------------------------------------------------------------

def test_the_doc_exists_and_states_what_it_does_not_show() -> None:
    assert DOC.exists(), "docs/printables.md is missing"
    text = DOC.read_text(encoding="utf-8")
    for needle in ("what this does NOT show", "WFG-007", "build_printables.py",
                   "2,460", "mono_fallback_lines"):
        assert needle in text, f"docs/printables.md no longer states: {needle}"


def test_the_docs_uncovered_symbol_count_is_the_derived_one(built: dict) -> None:
    """The number in the prose must be the number the build computed.

    ⚠ This test exists because the first version of docs/printables.md said
    「기호 17 개가 없습니다」 and then listed NINETEEN characters underneath. 17 was
    docs/auto/JUDGE_QA.md's own count, mistaken for the union of the four
    sources. Every other figure in that document was checkable against the
    manifest and correct; this one was the only figure the manifest did not
    carry, and it was the only one that was wrong. The lap's independent
    reviewer found it, and blocked, and was right.

    That is the leakage worth naming: a documentation gate that asserts the
    PRESENCE of strings its own author chose confirms the author, not the
    artifact. So the count is now derived by build() into the manifest, and this
    test makes the prose agree with it rather than the other way round.
    """
    derived = built["n_chars_needing_substitution"]
    assert derived == len(set(built["chars_needing_substitution"]))
    text = DOC.read_text(encoding="utf-8")
    assert f"기호 **{derived} 개**" in text, (
        f"docs/printables.md does not state the derived count of characters the "
        f"font cannot draw. The build computed {derived} "
        f"({built['chars_needing_substitution']}); update the prose to match the "
        f"manifest, never the manifest to match the prose.")
    # And the enumerated list must be the derived set, not a stale copy of it.
    listed = {c for c in text.split("`§")[1].split("`")[0]} | {"§"}
    missing = sorted(set(built["chars_needing_substitution"]) - listed - {" "})
    assert not missing, (
        f"docs/printables.md's enumerated list omits {missing}, which the build "
        f"says the font cannot draw")


def test_every_character_the_build_flags_has_a_substitution(built: dict) -> None:
    """The derived set and the hand-written table must not drift apart.

    If a source grows a symbol that is missing from the font, the build refuses
    — but only if SUBSTITUTIONS covers it. This asserts the two stay in step,
    so the failure arrives here rather than as a refused build mid-lap.
    """
    for ch in built["chars_needing_substitution"]:
        assert ch in bp.SUBSTITUTIONS, (
            f"{ch!r} U+{ord(ch):04X} is used by a source, is not in the font, "
            f"and has no entry in SUBSTITUTIONS")


def test_the_manifest_records_what_the_pdf_was_built_from(built: dict) -> None:
    """A printable whose sources have moved on is stale, and must be detectable.

    The manifest carries the sha256 of every source and every font, so a reader
    can tell a current printable from one built before the document changed
    without opening either.
    """
    assert len(built["sources"]) == len(bp.SOURCES)
    for entry in built["sources"]:
        assert len(entry["sha256"]) == 64
        assert (ROOT / entry["path"]).exists()
    assert built["fonts"] and all(len(f["sha256"]) == 64 for f in built["fonts"])
    assert "what_this_does_not_show" in built


def test_check_only_mode_exits_zero_on_the_current_tree() -> None:
    """The cheap gate a lap can run without drawing 29 pages."""
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--check-only"],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert r.returncode == 0, f"--check-only failed: {r.stdout}\n{r.stderr}"


def test_a_committed_printable_never_overwrites_an_earlier_one() -> None:
    """CHARTER §3.2: new results get new filenames.

    Every PDF under docs/auto/finals/printables/ must carry a distinct stamp,
    and each must have its manifest beside it.
    """
    if not OUT_DIR.exists():
        pytest.skip("no printables have been committed yet")
    pdfs = sorted(OUT_DIR.glob("WFG_printables_*.pdf"))
    stamps = [p.stem.replace("WFG_printables_", "") for p in pdfs]
    assert len(stamps) == len(set(stamps)), f"duplicate printable stamps: {stamps}"
    for stamp in stamps:
        manifest = OUT_DIR / f"manifest_{stamp}.json"
        assert manifest.exists(), f"{stamp} has no manifest beside it"
        m = json.loads(manifest.read_text(encoding="utf-8"))
        pdf = OUT_DIR / m["pdf"]
        assert bp.sha256(pdf) == m["pdf_sha256"], (
            f"{m['pdf']} does not match the sha256 its manifest records; a "
            f"committed artifact was modified in place (CHARTER §3.2)")
