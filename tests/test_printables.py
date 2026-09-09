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


def test_a_strikethrough_announces_itself_on_paper() -> None:
    """Dropping ~~ inverts a sentence, so the renderer says the word instead.

    Every other inline rule here loses only weight - 「**중요**」 reads the same
    without its asterisks. A retraction does not: 「~~틀렸습니다~~」 printed without
    its tildes IS the false sentence, on a sheet a judge is holding.

    ⚠ The parser works a line at a time, so a struck span that WRAPS is not
    matched and its tildes reach the page - the same shape as the unclosed-bold
    defect above. That is caught by the real-sources gate below rather than
    papered over here, and the fix for an author who meets it is to keep the span
    on one line, never to delete the markup.
    """
    blocks = bp.parse_markdown("- ~~그 화면은 아직 침묵합니다~~ 2026-09-09 에 닫혔습니다\n")
    text = " ".join(b.text for b in blocks)
    assert "~~" not in text, f"tildes survive onto the page: {text!r}"
    assert "[철회]" in text, (
        f"the struck span printed as an ordinary sentence: {text!r}. On paper "
        "that is the retracted claim, presented as current.")


def test_no_residual_inline_markup_prints_in_the_real_kit() -> None:
    """The test above grades a string the author typed; this one grades the paper.

    WFG-194's independent reviewer: the gate that existed knew the CLASS -- inline
    markup surviving into a printed line -- and could not see an instance, because
    its subject was a two-line literal rather than the seven documents that
    actually print. In the same lap, `docs/creativity_card.md` struck a claim
    through with ``~~ ~~`` and was added to `SOURCES`, and the renderer had no
    strikethrough rule; on paper the retraction markup vanished and the judge
    would have read a live claim that the screen in front of them was silent on
    창의성.

    ⚠ A strikethrough is the reason this is not cosmetic. Losing ``**`` costs
    emphasis; losing ``~~`` INVERTS the sentence. So ``~~`` is checked here in
    both directions: no raw tildes reach the page, and every struck span still
    announces itself as withdrawn.

    Runs over `SOURCES` itself, so a document added to the kit is graded by the
    fact of being added and no one has to remember to extend a list.
    """
    residues = []
    struck = 0
    for rel, _title in bp.SOURCES:
        md = (bp.ROOT / rel).read_text(encoding="utf-8")
        struck += len(bp._STRIKE.findall(md))
        for block in bp.parse_markdown(md):
            if block.kind == "code":
                continue          # tables and fences print verbatim by design
            for token in ("~~", "**", "__"):
                if token in block.text:
                    residues.append(f"{rel}: {token} in {block.text[:80]!r}")
    assert not residues, (
        "inline markup survives onto the printed page:\n  "
        + "\n  ".join(residues[:20])
        + "\nDropping ** costs emphasis; dropping ~~ turns a retraction back "
          "into a live claim. Teach strip_inline the token, do not delete the "
          "markup from the source.")
    if struck:
        printed = "\n".join(
            b.text for rel, _ in bp.SOURCES
            for b in bp.parse_markdown((bp.ROOT / rel).read_text(encoding="utf-8")))
        assert printed.count("[철회]") >= struck, (
            f"{struck} struck-through span(s) in the kit's sources and only "
            f"{printed.count('[철회]')} of them say so on paper. A retraction "
            "that prints as an ordinary sentence is worse than no retraction.")


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


# --------------------------------------------------------------------------
# The freshness contract (WFG-140)
# --------------------------------------------------------------------------
#
# Everything above this line reads the manifest against itself: the sources it
# lists have a sha256 each, the PDF matches its own recorded hash, no stamp is
# overwritten. All of it stayed green through four consecutive drifts of
# docs/auto/JUDGE_QA.md (critics #27, #28, #29, #30: af955a30fa, 7d5ac4c9c5,
# 175da9e50c, 5ac45ea810 against a recorded 2c8451211e), because nothing here
# compared a recorded source hash against the tree the sources actually live in.
# That is the one comparison that detects a stale printable, and the fourth
# drift was the one that made the printed pages worse rather than merely older:
# the 17 printed Q&A pages held Q19 without the caveat WFG-138 had just made
# mandatory, so the paper in the student's hand and the file the gates read
# disagreed about what the student is allowed to say.

def newest_manifest() -> Path | None:
    """The manifest of the most recent build, or None if nothing is committed.

    Older stamps stay valid records of what they were built from (CHARTER §3.2),
    so only the newest one is held to the working tree.
    """
    if not OUT_DIR.exists():
        return None
    manifests = sorted(OUT_DIR.glob("manifest_*.json"))
    return manifests[-1] if manifests else None


def test_the_newest_printable_is_not_stale_against_the_tree() -> None:
    """The kit on paper still says what the repository says today.

    Graded by touching one source: change any byte of a SOURCES document and
    this fails naming that path. It was also confirmed red BEFORE the rebuild it
    ships with, on the JUDGE_QA.md drift above, which is what says it is not
    green by construction (`paper/GAPS.md` G8 point 2).
    """
    manifest_path = newest_manifest()
    if manifest_path is None:
        pytest.skip("no printables have been committed yet")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    drifted = []
    for entry in manifest["sources"]:
        path = ROOT / entry["path"]
        if not path.exists():
            drifted.append(f"{entry['path']}: MISSING from the tree")
            continue
        current = bp.sha256(path)
        if current != entry["sha256"]:
            drifted.append(
                f"{entry['path']}: manifest {entry['sha256'][:10]}... "
                f"tree {current[:10]}...")
    assert not drifted, (
        "the newest booth printable is stale against the documents it prints, so "
        "the paper the student carries to the booth and the files the gates read "
        "no longer agree:\n  " + "\n  ".join(drifted)
        + f"\n{manifest_path.name} was built at stamp {manifest['stamp']}. "
        "Rebuild at a NEW stamp beside it (`make printables`); CHARTER §3.2 "
        "forbids overwriting the committed PDF or its manifest.")


def test_every_source_the_build_prints_is_recorded_by_the_newest_manifest() -> None:
    """A source added to the build after the last rebuild is drift too.

    The test above compares what the manifest lists; this one compares the other
    direction, so adding a SOURCES entry cannot pass unnoticed by leaving the
    manifest short.
    """
    manifest_path = newest_manifest()
    if manifest_path is None:
        pytest.skip("no printables have been committed yet")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    recorded = {e["path"] for e in manifest["sources"]}
    building = {path for path, _title in bp.SOURCES}
    assert recorded == building, (
        "scripts/build_printables.py and the newest manifest disagree about what "
        f"goes on paper.\n  in the build, not in {manifest_path.name}: "
        f"{sorted(building - recorded)}\n  in the manifest, not in the build: "
        f"{sorted(recorded - building)}\nRebuild at a new stamp "
        "(`make printables`).")


# --------------------------------------------------------------------------
# The kit against its own definition of done (WFG-130)
# --------------------------------------------------------------------------
#
# The build was measured against its own SOURCES list from the first lap, and
# never against docs/auto/KCF_READINESS.md R7, which is what says the kit is
# finished. R7 enumerates five printables; the first build carried one of them
# and three of its four documents are not on R7's list at all. That is why R7
# could not tick on a build that was otherwise good, and why its manifest said
# for four windows that a document done(20260903T0653Z) did not exist.

#: R7's five items, each resolved to what it is in the tree. An entry with a
#: reason is deliberately NOT printed here and the reason is the whole point of
#: writing it down: an exclusion nobody can read is how the first kit lost three
#: of these without anyone noticing.
R7_ITEMS: tuple[tuple[str, str | None, str | None], ...] = (
    ("evidence sheet (A4)", "docs/submission_reconciliation.md", None),
    # R7's first two items are one document. WFG-018 (「제출본 대비 정본
    # reconciliation sheet as NEAR-labelled prose (Korean, one page)」) is
    # done(20260903T0653Z) and its artifact is this file, whose fourth line says
    # 「인쇄본은 양면 한 장입니다」.
    ("reconciliation sheet", "docs/submission_reconciliation.md", None),
    # ⚠ WFG-026 shipped 2026-09-07T0630Z; this entry had `None` for its path and
    # 「the document does not exist, so there is nothing to print」 for its
    # reason, and it was the LAST of R7's five to be written. The booth wording
    # is RELATED_WORK_PANEL.md and the survey behind it is docs/related_work.md.
    ("related-work and SFTD059T differentiation panel",
     "docs/auto/finals/RELATED_WORK_PANEL.md", None),
    ("booth checklist", "docs/auto/finals/BOOTH_SETUP.md", None),
    # ⚠ REWORDED 2026-09-07T0630Z (WFG-153). R7's own line said 「29 dispatch
    # sheets sample」 and no count of 29 exists anywhere in this repository: the
    # tree holds 33 clusters, and 「29」 traces to an aspiration in
    # docs/auto/research/RESEARCH_BRIEF_2026-09-03.md with no key in
    # docs/NUMBERS.json (CHARTER §3.3). The reword drops the unregistered number
    # and keeps the item; R7's definition cell was changed in the same commit,
    # and test_r7_still_enumerates_... reads that cell rather than the file.
    ("village dispatch sheets sample", "outputs/dispatch",
     # ⚠ CORRECTED 2026-09-07T0320Z (WFG-151). This reason read 「already a set of
     # committed PDFs that print directly; re-rendering them through this build
     # would put a second, worse copy in the repository (CHARTER §3.2)」, and the
     # first half was false. It was copied from here into the judge-facing
     # release/kcf-finals-2026/README_KO.md by WFG-151 and caught by that lap's
     # independent reviewer, which checked it against the tree instead of against
     # this string. outputs/dispatch/20260801T163042Z/ holds 33 clusters; the HTML,
     # SMS drafts and broadcast scripts are committed for all 33, but only the
     # THREE largest clusters' dispatch_a4.pdf are -- outputs/dispatch/README.md
     # says so, because 33 Korean-font-subset PDFs are 6.7 MB of regenerable
     # output. R7's own wording 「29 dispatch sheets sample」 does not match the 33
     # either, and neither number is registered; that half is WFG-153, because
     # rewording R7 needs the critic and the manifest needs a new stamp.
     "the sheets are regenerable from a committed artifact rather than "
     "re-rendered here: outputs/dispatch/README.md commits the HTML, SMS drafts "
     "and broadcast scripts for all 33 clusters and only the three largest "
     "clusters' PDFs, with `python scripts/generate_dispatch_outputs.py` as the "
     "rebuild; putting a second, worse copy in this build would breach "
     "CHARTER §3.2"),
)


def test_r7_still_enumerates_the_five_printables_this_list_resolves() -> None:
    """If R7's wording moves, this mapping is stale and must be re-read.

    The list above is a reading of one line in another file. Binding to that
    line is what stops the reading from quietly outliving it.
    """
    readiness = (ROOT / "docs" / "auto" / "KCF_READINESS.md").read_text(encoding="utf-8")
    # ⚠ WFG-156, applied 2026-09-07T0630Z. This read the WHOLE of
    # KCF_READINESS.md, and critic #32 measured that all five of R7's names
    # already occur outside R7's row (2, 8, 3, 3 and 4 occurrences, on lines
    # predating that lap), so the test was VACUOUS: R7's definition could lose a
    # name and the loop's own commentary elsewhere in the file would keep this
    # green. The twin at tests/test_finals_bundle.py::
    # test_r9_still_enumerates_the_contents_this_list_resolves narrows to the
    # definition cell and spells out the reason; it was written by the 0355Z lap
    # and not applied one file over. Applied here by the lap that had to REWORD
    # R7 (「29 dispatch sheets sample」 -> 「village dispatch sheets sample」,
    # WFG-153) --- a lap rewording the specification it is measured against is
    # exactly when a vacuous binding costs something.
    r7 = [line for line in readiness.splitlines() if line.startswith("| R7 |")]
    assert len(r7) == 1, f"expected exactly one R7 row in KCF_READINESS.md, found {len(r7)}"
    cells = r7[0].split(" | ")
    assert len(cells) >= 3, f"R7's row is not the expected 4-cell table row: {cells[:2]}"
    definition = cells[1]
    missing = [name for name, _path, _why in R7_ITEMS if name not in definition]
    assert not missing, (
        "docs/auto/KCF_READINESS.md R7's DEFINITION cell no longer enumerates "
        + str(missing)
        + ", so R7_ITEMS here is a reading of a line that has changed. Re-read "
        "R7 and rewrite the mapping; do not delete this test. (It reads the "
        "definition cell only: the status cell is the loop's own narrative and "
        "would satisfy this test with commentary --- WFG-156.)")


def test_every_r7_printable_that_exists_is_actually_printed() -> None:
    """R7 is the definition of done for the booth kit; SOURCES is the build.

    Graded by removing one entry from bp.SOURCES and seeing this go red naming
    it.
    """
    building = {path for path, _title in bp.SOURCES}
    problems = []
    for name, path, why in R7_ITEMS:
        if path is None:
            assert why, f"R7 item {name!r} has neither a path nor a reason"
            continue
        exists = (ROOT / path).exists()
        if why:
            assert exists, (
                f"R7 item {name!r} is excluded from the printables because "
                f"{why}, but {path} is not in the tree, so the reason no longer "
                "holds and the exclusion needs re-reading")
            continue
        if not exists:
            problems.append(f"{name}: {path} is not in the tree")
        elif path not in building:
            problems.append(
                f"{name}: {path} exists but scripts/build_printables.py does not "
                "print it")
    assert not problems, (
        "the booth kit does not contain every R7 printable that exists in the "
        "tree, which is the defect WFG-130 was filed for — the first build was "
        "measured against its own source list and never against R7:\n  "
        + "\n  ".join(problems)
        + "\nAdd the path to SOURCES in scripts/build_printables.py and rebuild "
        "at a new stamp (`make printables`), or record here why it is not "
        "printed.")


def test_the_per_source_page_counts_sum_to_the_page_count(built: dict) -> None:
    """The two-second check that had never been run.

    `pages_per_source` was one too large for every source, because the value was
    computed as `r.page - start + 1` while the h1 branch of the renderer had
    already advanced the page. The error telescoped, so it was invisible in the
    breakdown and visible only in the sum: the 20260906T0620Z manifest records
    6+7+17+3 = 33 against a `pages` of 29, and 20260907T0032Z recorded
    6+7+18+4+3 = 38 against 33. Both decompositions had been copied onto
    judge-facing prose --- `docs/printables.md` §3 and
    `docs/auto/KCF_READINESS.md` R7 --- under a sentence saying they were
    re-derived from the manifest rather than retyped, which was true and is
    exactly how the wrong numbers travelled. Re-derived is not checked.
    """
    per_source = built["pages_per_source"]
    assert sum(per_source.values()) == built["pages"], (
        "the per-source page counts do not sum to the total the same build "
        f"reports: {per_source} sums to {sum(per_source.values())}, `pages` is "
        f"{built['pages']}. One of the two is wrong and both get printed into "
        "docs/printables.md and docs/auto/KCF_READINESS.md R7.")
    assert all(v >= 1 for v in per_source.values()), (
        f"a source drew fewer than one page: {per_source}")
