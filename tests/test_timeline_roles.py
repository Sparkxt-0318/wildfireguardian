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


#: The commit the committed artifact was BUILT on, which is the only honest as-of for
#: its totals. `data/processed/timeline_roles/timeline_roles.json` records 662 commits
#: and 513 trailers; at `359fd15`, the commit that carries the artifact, the history
#: already held 664 and 515, because two commits landed between the build and the push.
#: 662 is reached at `359fd15~2` = `89da7d3`, the WFG-027 claim commit. Nothing in the
#: artifact records this, which is why the number lives here and in the document rather
#: than being re-derived: the clone is shallow (CHARTER §4) and cannot resolve it.
AS_OF = "89da7d3"


def test_the_two_growing_totals_carry_the_commit_they_were_counted_at(
    doc: str, art: dict
) -> None:
    """A flat present-tense total in a document about a repository that grows.

    Critic #52 found `513 of 662` false within six hours of it being written — at
    `375be25` the same builder answers 517 of 666. The repair is NOT to retype today's
    values, because a retyped value re-derives from nothing; it is to say which tree
    the value was counted on. §3.4 already disclosed that the LAST phase grows, and
    that disclosure covered the per-phase cells while leaving the two headline totals
    reading as timeless facts.
    """
    trailer_rows = [ln for ln in doc.splitlines()
                    if f"**{art['agent_trailer_commits']}개**" in ln]
    assert len(trailer_rows) == 1, (
        f"expected one row stating {art['agent_trailer_commits']} trailers, "
        f"found {len(trailer_rows)}")
    assert AS_OF in trailer_rows[0], (
        "§2's trailer row states a total with no as-of commit, which is the exact "
        "defect critic #52 measured")
    assert f"`{AS_OF}` 기준" in doc, "§0 does not date the totals it opens with"
    #: ⚠ The independent reviewer's residual weakness (b), closed here: `AS_OF` is a
    #: literal no gate can re-derive in a shallow clone, so a rebuilt artifact would
    #: leave the stamp silently pointing at the wrong tree. Pinning the two values it
    #: was measured against makes a rebuild LOUD instead: this line goes red and the
    #: next lap re-derives the stamp deliberately rather than inheriting it.
    assert (art["total_commits"], art["agent_trailer_commits"]) == (662, 513), (
        f"the artifact was rebuilt ({art['total_commits']} commits, "
        f"{art['agent_trailer_commits']} trailers). `AS_OF` = {AS_OF} was measured "
        f"against 662/513 and is now wrong. Re-derive it: it is the commit at which "
        f"`build_timeline_roles.py` produces the artifact's own totals, which is NOT "
        f"the commit that carries the artifact — 662 is reached two commits before "
        f"`359fd15`, and writing `359fd15` would have been a false as-of."
    )


def test_the_boundary_claim_is_the_weaker_one_the_script_actually_proves(
    doc: str, art: dict
) -> None:
    """The document may not claim the record chose its phase boundaries.

    `scripts/build_timeline_roles.py` hard-codes all five `start`/`end`/`anchor`
    literals and `build()` only counts inside them, so there is no gap-selecting rule
    anywhere in the tree: the boundaries ARE a choice, and a software-engineering judge
    falsifies the old sentence by opening the builder. Registered as `WC-012`; the
    spelling itself is gated across every tracked document by
    `scripts/check_withdrawn_claims.py`, so what is checked HERE is the positive half —
    that the replacement says who chose, and that the claim which survives is stated.
    """
    #: Whitespace-tolerant on purpose. The first version of this assertion was a plain
    #: substring and went red the moment the paragraph was re-wrapped by one word, which
    #: is a gate firing on typography rather than on the claim — the failure class
    #: CHARTER §4 keeps paying for in a different costume.
    assert re.search(r"어디서\s*끊을지는\s*제가\s*골랐습니다", doc), (
        "the document does not say who chose the boundaries")
    assert art["commits_outside_phases"] == 0
    assert re.search(r"밖(?:에 남는|으로 새는)\s*커밋이\s*하나도\s*없다", doc), (
        "the partition proof — the claim that survives the withdrawal — is not stated "
        "beside the correction")


def test_the_unsplit_six_day_gap_is_disclosed(doc: str) -> None:
    """The evidence that the split is a choice is the gap it did NOT split on.

    Measured on a full clone (668 commits at `b5de13e`, `--is-shallow-repository`
    false) with the builder's own predicate: the record's empty-day gaps are 32, 15,
    **6**, 5, 2 and four of one day. The document splits on the 32, the 15, the 5 and
    ONE one-day gap (09-01 → 09-03), and leaves the six-day 06-06 → 06-13 inside 1기.
    A reader who checks the boundaries finds that gap first, so the document names it
    before they do (CHARTER §3 rule 5).
    """
    assert "06-06" in doc and "06-13" in doc, (
        "the six-day gap the split passed over is not named anywhere")
    six = [ln for ln in doc.splitlines() if "06-06" in ln and "06-13" in ln]
    assert any("엿새" in ln or "6일" in ln for ln in six), (
        "the gap is named but its length is not, so a reader cannot tell it is the "
        "third longest in the record")


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
