"""The motivating event's scale figures may not drift, and may not lose their scope.

WFG-043 / critic #4 F16, F17, F18. This is the one paragraph in the repository that a
judge reads first and that no other gate can see: the figures describe an external
event, so they have no artifact to re-derive from and no `docs/NUMBERS.json` key, and
`make verify` is therefore structurally blind to them. That blindness has now produced
two wrong paragraphs in a row, in opposite directions:

  * before `12b8ac7`: ~116,000 ha, larger than the entire nationwide total;
  * `12b8ac7` itself: 45,157 ha for a chain that burned 99,289 ha, and 영덕 8명
    against this repository's own correction to 10 at `f2eecf9`.

Both passed every gate. So this file is the gate, built the way
`tests/test_detection_floor_card.py` is built: each figure is pinned in its own test,
in the spelling the document uses, so a swapped digit or a dropped scope label fails
by name rather than as one opaque assertion.

What this file does NOT do, said plainly:

  * It does not verify the figures against the outside world. It cannot; there is no
    artifact. It pins them to the sources tabulated in `docs/data_sources.md`, which
    the 2026-09-04 lap opened by URL. If those sources are wrong, this test is wrong
    with them, and only a human re-reading the sources can say so.
  * **It has a known leakage, named by the lap's own independent reviewer under
    `mandela` patterns #3/#4/#5 and left open on purpose.** The ground truth it
    enforces (`docs/data_sources.md`) was written by the same agent, in the same
    commit, as the README it grades: two documents by one author agreeing with each
    other. The repository already owns the fix — `docs/evidence/greenpeace_2026_survey.md`
    pins its source with a sha256 and a retrieval date — but table A's rows carry bare
    news URLs whose content can change or vanish with nothing pinning them. Closing
    this means snapshotting each cited page and asserting README <-> snapshot instead
    of README <-> sibling doc. Filed as **WFG-050**. Until then, this file constrains
    *drift*, not *truth*, and the difference is not cosmetic.
  * It does not prove the paragraph is complete or well written.
  * It is a tripwire against *drift and scope loss*, which is the failure this
    repository actually has, twice.

Every assertion here has been checked to FAIL on a mutation, not merely to pass: see
the lap report for the six mutations run. The first version of this file passed all
thirteen of its own tests while the chain's death toll was replaced by the nationwide
one, because it pinned the substring "26" (satisfied by "2026") and asserted
`"9" in README` (satisfied 156 times). Both are fixed. **A pin that neighbouring text
already satisfies is not a pin**, and the only way to know is to break the document
and watch.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
README = (REPO / "README.md").read_text(encoding="utf-8")
SOURCES = (REPO / "docs" / "data_sources.md").read_text(encoding="utf-8")
ROUTING = (REPO / "docs" / "ROUTING_INTEGRATION_REPORT.md").read_text(encoding="utf-8")

# The judge-facing documents that state the motivating event's scale. Record files
# under docs/auto/ (reports, SCORECARD, CRITIC_LATEST, NEEDS_HUMAN, BACKLOG) are
# deliberately NOT here: they quote the retired values *as the finding*, and
# CHARTER §3 rule 7 keeps them.
JUDGE_FACING = {
    "README.md": README,
    "docs/data_sources.md": SOURCES,
    "docs/ROUTING_INTEGRATION_REPORT.md": ROUTING,
}

# The chain's final tally: 경상북도 최종 집계, confirmed by 중대본, reported 2025-05-06.
# https://view.asiae.co.kr/article/2025050610030818823
#
# ⚠ EACH ENTRY IS THE FULL SPELLING THE DOCUMENT USES, NOT A BARE NUMBER. The first
# version of this file pinned the substring "26" for the death toll, and the lap's own
# independent reviewer broke it in ten seconds: "26" is satisfied by "2026", which
# appears 35 times in README.md as a date and a competition year, so substituting the
# NATIONWIDE toll (32) for the chain's passed 13/13. A pin that any neighbouring text
# already satisfies is not a pin. Spellings, always.
FINAL_TALLY = [
    ("최종 피해면적 **99,289 ha**", "surveyed area, Korean"),
    ("burned **99,289 ha**", "surveyed area, English"),
    ("사망 **26명**", "deaths in the chain, Korean"),
    ("killed **26**\npeople", "deaths in the chain, English"),
    ("**3,819동** 피해", "houses destroyed, Korean"),
    ("**3,819\nhomes**", "houses destroyed, English"),
    ("**영덕 10명**", "Yeongdeok toll, Korean"),
    ("**10 of them in 영덕", "Yeongdeok toll, English"),
]


@pytest.mark.parametrize("literal,what", FINAL_TALLY, ids=[w for _, w in FINAL_TALLY])
def test_readme_states_the_final_tally(literal: str, what: str) -> None:
    """The README leads with the surveyed final figures, not a pre-containment interim."""
    assert literal in README, (
        f"README.md no longer states {literal!r} ({what}). This is the chain's final "
        "tally per 경상북도/중대본 2025-05-06; see docs/data_sources.md § 동기 사건의 "
        "피해 규모 table A."
    )


# Values that belong to scope B (the nationwide spring-season total) and must never be
# attributed to this chain. This is the A/B confusion the whole section exists to stop,
# and it is the mutation that broke the first version of this file.
NATIONWIDE_ONLY = [
    ("사망 **32명**", "the nationwide death toll, Korean"),
    ("killed **32**", "the nationwide death toll, English"),
    ("피해면적 **104,788", "the nationwide area as the chain's, Korean"),
    ("burned **104,788", "the nationwide area as the chain's, English"),
]


@pytest.mark.parametrize("literal,what", NATIONWIDE_ONLY, ids=[w for _, w in NATIONWIDE_ONLY])
def test_nationwide_figures_are_never_the_chains(literal: str, what: str) -> None:
    """Scope B's figures may be named as scope B, never as this chain's own tally."""
    assert literal not in README, (
        f"README.md attributes {literal!r} ({what}) to the 의성발 경북 chain. That "
        "figure is the 2025 spring-season nationwide total (산림청, 2025-01-24 ~ "
        "05-15). The chain's own tally is 99,289 ha and 26 deaths."
    )


def test_readme_states_the_area_in_both_languages() -> None:
    """Both opening paragraphs carry the same area. `12b8ac7` changed both at once and
    got both wrong; a fix that lands in only one language is the same defect."""
    assert README.count("99,289") >= 2, (
        "the Korean and English opening paragraphs must both state 99,289 ha; "
        f"found {README.count('99,289')} occurrence(s)"
    )


@pytest.mark.parametrize("doc", sorted(JUDGE_FACING))
def test_retired_yeongdeok_death_toll_is_gone(doc: str) -> None:
    """영덕 8명 appears in no source this repository has opened.

    critic #4 F17: `f2eecf9` corrected 8 to 10 on 2026-09-03T1821Z and `12b8ac7`
    reasserted 8 twelve hours later, in both languages, leaving two judge-facing
    documents disagreeing about the region the routing work is built around.
    """
    text = JUDGE_FACING[doc]
    for spelling in ("영덕 8명", "영덕 8 명", "8 in 영덕", "영덕(Yeongdeok) 8"):
        assert spelling not in text, (
            f"{doc} states {spelling!r}. The county's own notice of 2025-04-29 gives "
            "10 (re-quoted in docs/evidence/greenpeace_2026_survey.md §3) and the "
            "province's 2025-03-30 interim gives 9. 8 is neither."
        )


def test_yeongdeok_toll_keeps_its_requoted_caveat() -> None:
    """10 is a re-quoted figure, not a survey result, and never travels without saying so.

    The evidence card that carries it says this in its §3; a README that drops the
    caveat turns a 재인용값 into a measurement.
    """
    assert "재인용값" in README, (
        "the Korean paragraph cites 영덕 10명 without marking it 재인용값; the figure is "
        "quoted by the Greenpeace report from a 영덕군 notice, not measured by it "
        "(docs/evidence/greenpeace_2026_survey.md §7)"
    )
    assert "a re-cited figure, not a survey result" in README, (
        "the English paragraph dropped the same caveat"
    )
    assert "2025-04-29" in README, (
        "the 영덕 figure must carry the 영덕군 공지 date it was re-quoted from"
    )


def test_both_yeongdeok_figures_survive() -> None:
    """Sources disagree (9 vs 10) on different bases and dates. The repository keeps
    both rather than picking the flattering one; that is CHARTER §3 rule 5.

    ⚠ The first version of this test asserted `"9" in README and "10" in README`, which
    is a pure no-op: those substrings occur 156 and 31 times in dates and section
    numbers. Caught by the lap's independent reviewer. Pin the sentences instead.
    """
    assert "경상북도 재난안전대책본부\n2025-03-30 중간 집계는 9명" in README, (
        "the README dropped the province's 2025-03-30 interim figure of 9 for 영덕. "
        "Both figures stay: collapsing a live disagreement into one confident number "
        "is how this paragraph got wrong twice."
    )
    assert "against 9 in the\nprovince's interim tally" in README, (
        "the English paragraph dropped the 9 figure; the two languages must agree"
    )
    for token in ("10명", "9명"):
        assert token in SOURCES, (
            f"docs/data_sources.md must tabulate {token} for 영덕 with its own source "
            "row; collapsing the disagreement hides it"
        )


def test_the_interim_estimate_never_appears_bare() -> None:
    """45,157 ha is a different *quantity*, not a stale version of 99,289 ha.

    It is the 「산불영향구역」 estimate; 99,289 ha is surveyed 산림피해 면적. Quoting the
    former as the chain's burned area is what F16 is. Wherever it appears it must be
    within a few lines of the label that says which quantity it is.
    """
    for doc, text in JUDGE_FACING.items():
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if "45,157" not in line:
                continue
            window = "\n".join(lines[max(0, i - 3) : i + 4])
            assert "산불영향구역" in window or "fire-affected area" in window, (
                f"{doc}:{i + 1} quotes 45,157 ha without the 「산불영향구역」 label "
                "within three lines. Bare, it reads as the chain's burned area, "
                "which is 99,289 ha."
            )


def test_the_nationwide_total_is_never_divided_by_the_chain() -> None:
    """104,788 ha (nationwide, 347 fires) and 99,289 ha (this chain, surveyed) come
    from different bodies on different bases. critic #4 computed "about 95 %" from
    them; that ratio mixes the bases and this repository does not print it.

    Scoped deliberately, three times over. "95 %" is a legitimate string in this
    repository (bootstrap CIs), so the tripwire fires only on a percentage sitting on
    the same line as the nationwide total. Percent-encoded URLs (`...2025%EB%85%84...`)
    are stripped first, because a link target is not prose. And the scan covers
    **README.md only**: `docs/data_sources.md` is where the bad ratios are named and
    refuted by 함정 6, and where the 산림청 release is quoted verbatim ("12% 감소한
    347건"), so a blanket ban there would forbid the discussion that prevents the error.
    """
    share = re.compile(r"\d{1,3}\s*%")
    link_target = re.compile(r"\]\([^)]*\)")
    for i, line in enumerate(README.splitlines()):
        if "104,788" not in line:
            continue
        prose = link_target.sub("]()", line)
        assert not share.search(prose), (
            f"README.md:{i + 1} states a percentage beside the nationwide total. "
            "The chain's share is 95 % or 43 % depending on which of its own areas "
            "you put on top, so it is a choice of framing, not a quantity."
        )


def test_the_nationwide_total_carries_its_period() -> None:
    """104,788 ha / 347 fires is a *spring-season* total, not a March total.

    The first version of this section said "2025년 3월 ... 347건", cited to a
    ko.wikipedia page that does not contain 347 at all. The lap's independent reviewer
    opened the 산림청 release and found the period: 봄철 산불조심기간, 2025-01-24 to
    05-15. Getting the period wrong on the comparison figure is the same defect class
    as getting the basis wrong on the headline figure.
    """
    assert "봄철 산불조심기간" in README and "1월 24일" in README, (
        "the Korean scope note must state that 104,788 ha / 347건 is the spring "
        "fire-prevention season total (2025-01-24 ~ 05-15), not a March total"
    )
    assert "spring fire-prevention season" in README and "24 January to 15 May" in README, (
        "the English scope note must state the same period"
    )
    assert "pcccr.go.kr" in README and "pcccr.go.kr" in SOURCES, (
        "the 산림청 press release is the primary source for 347건 / 104,788 ha and "
        "must be linked; a ko.wikipedia page that does not contain 347 is not"
    )


def test_wwa_figure_is_not_cited() -> None:
    """The 2026-09-04 lap could not open the WWA page (404), and the figure's real
    scope is 'southeastern Korea', not this chain. F18's rule: a row whose URL the lap
    cannot open is removed, not quietly kept."""
    for doc in ("README.md", "docs/ROUTING_INTEGRATION_REPORT.md"):
        assert "48,000 ha" not in JUDGE_FACING[doc], (
            f"{doc} cites the WWA 48,000 ha figure again. It is for southeastern "
            "Korea, and the page did not resolve when last checked."
        )


def test_every_figure_row_in_table_a_carries_a_source_link() -> None:
    """F18: the document named 데이터 출처 may not hold a figure with no retrievable
    source. Every data row of table A carries a markdown link or an in-repo path."""
    block = SOURCES.split("### A. 의성발 경북 산불")[1].split("### B.")[0]
    rows = [
        ln
        for ln in block.splitlines()
        if ln.startswith("|") and "---" not in ln and "| 항목 " not in ln
    ]
    assert len(rows) >= 8, f"table A lost rows: {len(rows)} found"
    for row in rows:
        has_url = bool(re.search(r"\]\(https?://", row))
        has_repo_path = "docs/evidence/" in row
        assert has_url or has_repo_path, (
            f"table A row without a retrievable source:\n{row}\n"
            "F18: delete the row or source it; do not keep it unsourced."
        )
