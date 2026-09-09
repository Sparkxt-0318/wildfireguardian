"""WFG-027 — the schedule document may not drift from the history it reports.

설계와 방법론's 「일정 및 팀원(개인의 경우 제외) 역할 배분의 타당성」 is worth 20
points on both KCF scoring tables, and until this row the string 일정 counted 0 on
`README.md`, `web/finals.html` and `docs/auto/JUDGE_QA.md`. The answer is now
`docs/auto/finals/TIMELINE_ROLES.md`.

Every count in that document is a hand-typed number in Korean prose, which is the
exact shape of defect this repository has shipped three times (WFG-117; the
「여섯 개」 that survived the very commit correcting it). So each one is checked
here against `data/processed/timeline_roles/timeline_roles.json`, the committed
artifact `scripts/build_timeline_roles.py` writes from `git log`.

⚠ These tests read the ARTIFACT, never `git log`. The routine's clone is shallow
at a depth that is not a constant (50, 51, 149, 294 and 531 measured on different
laps, CHARTER §4), so a test that walked the history would fire on clone depth
rather than on a defect — which is the failure class NH-043 was filed about. The
one test that does need the history skips itself, with the reason, when the clone
cannot resolve the first commit.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DOC = REPO / "docs" / "auto" / "finals" / "TIMELINE_ROLES.md"
ARTIFACT = REPO / "data" / "processed" / "timeline_roles" / "timeline_roles.json"


@pytest.fixture(scope="module")
def art() -> dict:
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def doc() -> str:
    return DOC.read_text(encoding="utf-8")


def test_the_draft_label_is_on_the_file(doc: str) -> None:
    """CHARTER §9: drafts for the student's own voice are labelled where they are read."""
    assert doc.splitlines()[0].rstrip().endswith("(DRAFT)")


def test_every_phase_row_states_the_artifact_s_own_dates(doc: str, art: dict) -> None:
    """A phase whose start date is retyped wrong is a date a judge can catch."""
    for ph in art["phases"]:
        start = ph["start"]                       # 2026-05-27
        assert start in doc, f"{ph['id']} start {start} is not in the document"
        # The end is written month-day only for a closed phase ("2026-05-27 → 06-15").
        if not ph["end_is_open"]:
            tail = ph["end"][5:]                  # 06-15
            assert re.search(rf"{re.escape(start)}\s*→\s*{re.escape(tail)}", doc), (
                f"{ph['id']} does not carry the range {start} → {tail}")


def test_every_phase_row_states_the_artifact_s_own_counts(doc: str, art: dict) -> None:
    """The per-phase 활동일 and 커밋 cells are the artifact's numbers, not a memory of them."""
    rows = [ln for ln in doc.splitlines() if ln.startswith("| **") and "일 |" in ln]
    assert len(rows) == len(art["phases"]), (
        f"the phase table has {len(rows)} rows for {len(art['phases'])} phases")
    for row, ph in zip(rows, art["phases"]):
        assert f"| {ph['active_days']}일 |" in row, (
            f"{ph['id']} row does not state {ph['active_days']}일: {row[:80]}")
        assert f"| {ph['commits']} |" in row, (
            f"{ph['id']} row does not state {ph['commits']} commits: {row[:80]}")


def test_the_anchor_commit_of_every_phase_is_named(doc: str, art: dict) -> None:
    """Each phase is dated by a commit a reader can resolve, not by an assertion."""
    for ph in art["phases"]:
        assert ph["anchor_commit"], f"{ph['id']} has no anchor commit in the artifact"
        assert ph["anchor_commit"] in doc, (
            f"{ph['id']}'s anchor {ph['anchor_commit']} is not named in the document")


def test_the_headline_totals_are_the_artifact_s(doc: str, art: dict) -> None:
    """Containment is not enough when a figure is written twice.

    The independent reviewer of the lap that added this file found the hole by
    mutating ONE of the two 「662개」 and watching the suite stay green: a
    substring check passes as long as any one instance survives, so the realistic
    defect — a single-site typo — was the one it could not see. Each figure is
    therefore counted, not merely looked for.
    """
    for key, needle, times in (
        ("active_days", "활동한 날 {}일", 1),
        ("total_commits", "{}개", 2),
        ("agent_trailer_commits", "**{}개**", 1),
    ):
        text = needle.format(art[key])
        assert doc.count(text) == times, (
            f"the document states {key} = {art[key]} as `{text}` "
            f"{doc.count(text)} times, expected {times}")


def test_the_phase_table_is_a_partition_and_says_so(doc: str, art: dict) -> None:
    """The claim 「분할입니다」 is only true while no commit falls outside a phase."""
    assert art["commits_outside_phases"] == 0
    assert "**0개**" in doc and "분할" in doc


def test_the_three_things_the_counts_do_not_show_travel_with_them(doc: str) -> None:
    """CHARTER §3 rule 5: when a result is weak, the artifact says so.

    A commit count read as a measure of work is the one misreading that would
    actually mislead a judge, and it is the misreading the 417-vs-55 row invites.
    """
    for clause in (
        "커밋 수는 작업량이 아닙니다",           # §3.1
        "기계적인 문자열 검사",                   # §3.2, the trailer is not authorship
        "auto/dev",                               # §3.3, one branch's history
        "지도교사 역할에 대한 기록이 없습니다",    # §2, an absence stated
    ):
        assert clause in doc, f"the document has dropped: {clause}"


def test_the_two_42s_are_kept_apart(doc: str) -> None:
    """42 활동일 sits three lines from a project whose headline number is 42 of 458.

    A judge who hears both in one answer hears one number twice. The document is
    required to say which is which, because nothing else in the tree will.
    """
    assert "42는 「일수」" in doc
    assert "42곳" in doc


def test_the_forbidden_sentences_are_on_the_card(doc: str) -> None:
    for banned in ("계획대로 진행했습니다", "하루도 쉬지 않았습니다"):
        assert f"❌ 「{banned}」" in doc


def _shallow() -> bool:
    out = subprocess.run(["git", "rev-parse", "--is-shallow-repository"],
                         cwd=REPO, capture_output=True, text=True)
    return out.stdout.strip() != "false"


@pytest.mark.skipif(
    _shallow(),
    reason="shallow clone: the 2026-05-27 first commit is not present, so the "
           "artifact cannot be re-derived here (CHARTER §4: the clone depth is "
           "not a constant, so this must skip rather than fail)")
def test_the_artifact_still_agrees_with_the_history_when_the_clone_has_one() -> None:
    """The one check that reads git, and only where git can answer."""
    out = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "build_timeline_roles.py"), "--check"],
        cwd=REPO, capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr
