"""The bucket-wording table in `docs/live_pipeline.md` is bound to the code.

WFG-262. `docs/routing_limitations.md` §1 rewrote `fa_exceeds_budget`'s A4 sheet
line on 2026-08-10 because it asserted the budget as a cause the classification
condition does not establish. That repair was made in the file that PRINTS the
string and never in the file that DOCUMENTS it, so `docs/live_pipeline.md`'s
mapping table went on showing the superseded wording for a month, until the lap
that made the identical repair to `no_safe_route` read the table.

A stale row in that table is not cosmetic: it is the page a reader consults to
learn what the operator actually sees, so it is where a judge or a county office
would check the claim that the sheets state only what the code establishes.

This file is the tie. It is deliberately clock-free, network-free and
data-free: it reads two files in the repository and nothing else.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

from wildfireguardian.live.pipeline import BUCKET_TEXT, ORIGIN_REFUSED_TEXT

REPO = Path(__file__).resolve().parents[1]
DOC = REPO / "docs" / "live_pipeline.md"

#: The doc's mapping table lives under this heading.
SECTION = "### Resident-side, so the sheets do not say 차량"

#: WFG-264. The 439 responder series' own table, which is the sheet a judge is
#: physically handed. Its wording lives in a script rather than in the package,
#: so it is loaded by path — the binding matters more than the import style.
VEHICLE_SECTION = "### Responder-side, the 439 series — the sheet the booth hands over"
DISPATCH_SCRIPT = REPO / "scripts" / "generate_dispatch_outputs.py"


def _dispatch_module():
    sys.path.insert(0, str(REPO / "src"))
    spec = importlib.util.spec_from_file_location(
        "_wfg_generate_dispatch_outputs", DISPATCH_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _live_table_wordings() -> set[str]:
    """Every `wording` cell of the LIVE mapping table (not the record table)."""
    text = DOC.read_text(encoding="utf-8")
    start = text.index(SECTION)
    body = text[start:]
    # The live table ends at the first warning line after it; the superseded
    # table below deliberately carries the old strings and must not be read.
    body = body.split("⚠ **Two of those wordings are replacements", 1)[0]
    out = set()
    for line in body.splitlines():
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 3 or cells[0] == "bucket":
            continue
        if cells[2] and cells[2] != "":
            out.add(cells[2])
    return out


def test_every_shipped_bucket_sentence_appears_in_the_doc_table():
    """The code's strings are the authority; the doc must show them verbatim."""
    doc_wordings = _live_table_wordings()
    missing = []
    for bucket, (_, text) in BUCKET_TEXT.items():
        if bucket in ("both_enter", "naive_unreachable"):
            continue  # not part of the 459-series three-bucket mapping
        if text not in doc_wordings:
            missing.append((bucket, text))
    assert not missing, (
        "docs/live_pipeline.md's mapping table does not show the sentence the "
        f"code actually prints: {missing}. That is the WFG-262 defect: a sheet "
        "line repaired in live/pipeline.py and not in the page that documents "
        "it. Update the table AND move the old wording into the superseded "
        "table below it (HANDOFF §5 rule 7: annotate, never delete).")


def test_the_refused_origin_line_appears_in_the_doc_table():
    assert ORIGIN_REFUSED_TEXT in _live_table_wordings(), (
        "the refused-origin sheet line is not in docs/live_pipeline.md's table")


def test_no_superseded_wording_is_still_shown_as_live():
    """The two known-stale strings must appear only in the record table."""
    superseded = (
        "예산 내 안전한 보행 경로가 없음(우회 포함)",
        "보행 경로는 있으나 대피 시간 예산 초과",
    )
    live = _live_table_wordings()
    for old in superseded:
        assert old not in live, (
            f"{old!r} is a superseded sheet line (routing_limitations.md §1/§6) "
            "and is being shown as the live wording")


def test_the_record_table_keeps_both_superseded_wordings():
    """CHARTER §3.7 / HANDOFF §5 rule 7: the old string is kept, not deleted."""
    text = DOC.read_text(encoding="utf-8")
    for old in ("예산 내 안전한 보행 경로가 없음(우회 포함)",
                "보행 경로는 있으나 대피 시간 예산 초과"):
        assert old in text, (
            f"the superseded wording {old!r} was deleted rather than recorded")


@pytest.mark.parametrize("bucket", ["no_safe_route", "fa_exceeds_budget"])
def test_the_doc_points_at_the_section_that_justifies_each_repair(bucket):
    text = DOC.read_text(encoding="utf-8")
    section = "§6" if bucket == "no_safe_route" else "§1"
    assert section in text, (
        f"docs/live_pipeline.md should cite routing_limitations.md {section} "
        f"for {bucket}'s wording")


# ---------------------------------------------------------------------------
# WFG-264: the same binding for the 439 responder series
# ---------------------------------------------------------------------------


def _vehicle_table_wordings() -> set[str]:
    """Every `wording` cell of the LIVE vehicle table (not the record table)."""
    text = DOC.read_text(encoding="utf-8")
    body = text[text.index(VEHICLE_SECTION):]
    body = body.split("⚠ **The first of those is a replacement", 1)[0]
    out = set()
    for line in body.splitlines():
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 3 or cells[0] == "class":
            continue
        if cells[2]:
            out.add(cells[2])
    return out


def test_the_vehicle_sheet_sentence_appears_in_the_doc_table():
    """The script's string is the authority; the doc must show it verbatim."""
    shipped = _dispatch_module().UNREACHABLE_REASON_KO
    assert shipped in _vehicle_table_wordings(), (
        "docs/live_pipeline.md's 439-series table does not show the sentence "
        f"scripts/generate_dispatch_outputs.py actually prints ({shipped!r}). "
        "That is the WFG-262 defect on the responder arm: the sheet a judge is "
        "handed, repaired in the emitter and not in the page that documents it.")


def test_the_superseded_vehicle_wording_is_not_shown_as_live():
    mod = _dispatch_module()
    old = mod.SUPERSEDED_UNREACHABLE_REASON_KO
    assert old != mod.UNREACHABLE_REASON_KO
    assert old not in _vehicle_table_wordings(), (
        f"{old!r} is a superseded sheet line (routing_limitations.md §7) and is "
        "being shown as the live wording")


def test_the_record_keeps_the_superseded_vehicle_wording():
    """CHARTER §3.7 / HANDOFF §5 rule 7: the old string is kept, not deleted."""
    old = _dispatch_module().SUPERSEDED_UNREACHABLE_REASON_KO
    assert old in DOC.read_text(encoding="utf-8"), (
        f"the superseded wording {old!r} was deleted rather than recorded")
    assert old in DISPATCH_SCRIPT.read_text(encoding="utf-8"), (
        "the emitter no longer carries the sentence it used to print")


def test_the_vehicle_sentence_asserts_no_cause():
    """The whole of WFG-264: the line may not name fire, a budget or a detour.

    Each banned token is a thing the classification condition does not establish.
    `rescuer_reachable` fails for three different reasons and the sheet gets one
    sentence, so the sentence may say what was searched for and not why it failed.
    """
    shipped = _dispatch_module().UNREACHABLE_REASON_KO
    for token in ("화재", "예산", "우회", "차단"):
        assert token not in shipped, (
            f"the 439 unreachable sheet line asserts {token!r}, which its code "
            "condition does not establish (routing_limitations.md §7)")


def test_the_doc_points_at_section_7_for_the_vehicle_repair():
    assert "§7" in DOC.read_text(encoding="utf-8"), (
        "docs/live_pipeline.md should cite routing_limitations.md §7 for the "
        "439-series wording")
