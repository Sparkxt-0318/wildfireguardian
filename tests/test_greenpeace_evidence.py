"""WFG-020: the survivor-survey figures stay tied to the document they came from.

The failure this file exists to catch is not arithmetic. It is a number that
LOOKS sourced — it sits next to a sha256 and a table reference — but was
actually retyped from someone's notes and no longer matches the report. That is
docs/HANDOFF_ROUND3.md §4-B's class, and a checksum on the PDF does not catch it
because the checksum authenticates the PDF rather than the transcription.

So the gates here are:

* the committed artifact is internally consistent (count / base == percent);
* every figure printed in docs/evidence/greenpeace_2026_survey.md appears in the
  artifact, so prose cannot drift away from it;
* the caveats that make the figures quotable at a booth are actually present;
* the 영덕 death toll stays labelled as the report's own re-citation of 영덕군
  rather than a survey finding;
* none of it leaked into docs/NUMBERS.json, which means something different.

The PDF is git-ignored (3.4 MB, third-party), so the one test that re-reads it
skips with that reason on a fresh clone.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
ARTIFACT = REPO / "data" / "processed" / "evidence" / "greenpeace_2026_survey.json"
DOC = REPO / "docs" / "evidence" / "greenpeace_2026_survey.md"
PDF = REPO / "data" / "raw" / "evidence" / "greenpeace_2026_yeongnam_survey.pdf"
SHA256 = "db15d70580e136b9a636ffbf4c84b29a53ec6d517e5c11d5b8d82a79f6653310"


@pytest.fixture(scope="module")
def survey() -> dict:
    assert ARTIFACT.exists(), f"{ARTIFACT} is committed and must be present"
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def doc_text() -> str:
    assert DOC.exists(), f"{DOC} is committed and must be present"
    return DOC.read_text(encoding="utf-8")


def _cells(survey: dict):
    for table_id, table in survey["tables"].items():
        for region, row in table["rows"].items():
            for name, cell in zip(table["columns"], row["cells"]):
                yield table_id, region, name, row["base"], cell


# --- the artifact ------------------------------------------------------------


def test_the_source_is_identified_by_digest(survey):
    assert survey["source"]["sha256"] == SHA256
    assert survey["source"]["bytes"] == 3406169
    assert survey["source"]["pages"] == 191
    assert survey["source"]["url"].startswith("https://www.greenpeace.org/")


def test_every_printed_percentage_matches_its_own_counts(survey):
    """The report's arithmetic, re-done. Catches a transposed or dropped digit."""
    bad = []
    for table_id, region, name, base, cell in _cells(survey):
        got = 100.0 * cell["count"] / base
        if abs(got - cell["percent"]) > 0.1:
            bad.append(f"{table_id}/{region}/{name}: {cell['count']}/{base} "
                       f"= {got:.2f}% but artifact says {cell['percent']}%")
    assert not bad, "\n".join(bad)


def test_the_headline_evacuation_figures_are_what_the_project_quotes(survey):
    car = survey["tables"]["표 3-3"]
    assert car["rows"]["전체"]["base"] == 291
    counts = {n: c for n, c in zip(car["columns"], car["rows"]["전체"]["cells"])}
    assert (counts["승용차"]["count"], counts["승용차"]["percent"]) == (246, 84.5)
    assert (counts["도보"]["count"], counts["도보"]["percent"]) == (9, 3.1)
    assert (counts["배"]["count"], counts["배"]["percent"]) == (8, 2.7)


def test_the_village_broadcast_channel_outweighs_the_emergency_text(survey):
    """The 근거 behind the Q17 answer; if this flips, the answer is wrong."""
    rows = survey["count_tables"]["표 3-2"]["rows"]
    cols = survey["count_tables"]["표 3-2"]["columns"]
    idx = {name: i for i, name in enumerate(cols)}
    for region, expected_broadcast, expected_text in (("전체", 237, 112), ("영덕", 89, 22)):
        row = rows[region]
        broadcast = row[idx["마을 방송"]] + row[idx["마을 주민"]]
        assert broadcast == expected_broadcast, f"{region}: {broadcast}"
        assert row[idx["재난 문자"]] == expected_text, f"{region}: {row[idx['재난 문자']]}"
        assert broadcast > row[idx["재난 문자"]]


def test_the_bases_differ_per_question_and_are_never_assumed_to_be_300(survey):
    """Percentages are over each table's own 유효응답수. Flattening them to 300
    is the easiest way to publish a wrong number from a right table."""
    bases = {row["base"] for t in survey["tables"].values() for row in t["rows"].values()}
    assert 291 in bases and 300 in bases, bases
    assert survey["tables"]["표 3-4"]["rows"]["전체"]["base"] == 278
    assert survey["tables"]["표 1-6"]["rows"]["영덕"]["base"] == 99


def test_the_death_toll_is_labelled_as_a_re_citation_not_a_survey_finding(survey):
    sec = survey["secondary_citation"]
    assert sec["deaths"] == 10 and sec["deaths_mean_age"] == 84
    assert "영덕군" in sec["cited_from"]
    assert "NOT a survey finding" in sec["_warning"]
    # and it must not have been smuggled into the answer tables
    for table in survey["tables"].values():
        for row in table["rows"].values():
            assert row["base"] >= 89, row["base"]


# --- the prose ---------------------------------------------------------------


def test_every_figure_in_the_doc_exists_in_the_artifact(doc_text, survey):
    """The anti-drift gate: prose may not invent or stale-copy a figure."""
    known = {(c["count"], c["percent"]) for *_, c in _cells(survey)}
    # the doc writes figures as "246 (84.5%)"
    printed = {(int(a), float(b)) for a, b in re.findall(r"(\d[\d,]*) \((\d+\.\d)%\)",
                                                         doc_text.replace(",", ""))}
    missing = printed - known
    assert not missing, f"figures in the doc that are in no table: {sorted(missing)}"
    assert len(printed) >= 15, f"only {len(printed)} figures parsed; the doc changed shape"


def test_the_doc_carries_the_caveats_that_make_it_quotable(doc_text):
    for needle, why in [
        ("생존자 표본", "survivor bias is the load-bearing caveat"),
        ("눈덩이표집", "the sample is not a probability sample"),
        ("균등할당", "the 전체 column is not population-weighted"),
        ("f = 0.15 / 0.30 / 0.45", "the immobility answer stays 서식1 §4"),
        (SHA256, "the digest must be in the prose, not only the artifact"),
    ]:
        assert needle in doc_text, f"missing: {needle} ({why})"


def test_the_doc_forbids_the_car_less_equals_immobile_reading(doc_text):
    """The one misreading the backlog row named explicitly. 60.1% is a share of
    the 278 who evacuated BY VEHICLE, so '~40% have no car' is not a bracket on
    the 0.30 immobility rate."""
    assert "278" in doc_text
    assert "거동 불가" in doc_text
    section = doc_text[doc_text.index("## 5."):]
    assert "남의 차를 탄 사람" in section


def test_the_doc_says_why_these_numbers_are_not_registered(doc_text):
    section = doc_text[doc_text.index("## 6."):]
    assert "NUMBERS.json" in section
    assert "재현" in section


# --- the boundary with the registry -----------------------------------------


def test_the_survey_figures_did_not_leak_into_the_registry():
    """A deliberate decision, pinned: these are someone else's measurements, so
    they do not get a registry key. If a later lap registers them, it should have
    to delete this test and say why in its report."""
    registry = json.loads((REPO / "docs" / "NUMBERS.json").read_text(encoding="utf-8"))
    blob = json.dumps(registry, ensure_ascii=False)
    assert "greenpeace" not in blob.lower()
    assert "greenpeace_2026_survey.json" not in blob


# --- the source itself (needs the git-ignored PDF) ---------------------------


@pytest.mark.skipif(
    not PDF.exists(),
    reason="the 3.4 MB third-party PDF lives under the git-ignored data/raw/; "
           "re-download it per docs/evidence/greenpeace_2026_survey.md §1 to run this",
)
def test_the_committed_digest_still_matches_the_pdf():
    import hashlib

    h = hashlib.sha256()
    with open(PDF, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    assert h.hexdigest() == SHA256
