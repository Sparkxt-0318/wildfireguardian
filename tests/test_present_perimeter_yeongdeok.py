"""WFG-129 — the Yeongdeok present-perimeter contrast, bound to its artifact.

Why these tests and not others
------------------------------
The measurement itself needs the committed OSM/DEM snapshots and about a minute
of routing, so re-running it inside the suite would be a slow duplicate of
``scripts/measure_present_perimeter_yeongdeok.py``.  What CAN drift without
anyone noticing is the prose: ``docs/present_perimeter_yeongdeok.md`` quotes six
counts and a reproduction table, and a later lap editing that page has nothing
stopping it from writing a number the artifact does not hold.  That is the
failure this file is written for, and it is the failure this repository has
actually paid for (WFG-117, WFG-180: hand-written numbers going stale beside the
artifact they came from).

So: the artifact's internal arithmetic must close, the registry must agree with
the artifact, and every count the document states in bold must be the artifact's
own.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
ARTIFACT = REPO / "data/processed/present_perimeter_yeongdeok_2025.json"
DOC = REPO / "docs/present_perimeter_yeongdeok.md"
NUMBERS = REPO / "docs/NUMBERS.json"
CANON = REPO / "data/processed/real_roads_real_hazard_canonical.json"

pytestmark = pytest.mark.skipif(
    not ARTIFACT.exists(),
    reason="present_perimeter_yeongdeok_2025.json is not present in this checkout",
)


@pytest.fixture(scope="module")
def art() -> dict:
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def doc() -> str:
    return DOC.read_text(encoding="utf-8")


def test_the_reproduction_gate_passed_and_says_what_it_reproduced(art):
    """The run refuses to write unless the committed partition re-derives first.

    The flag alone would be self-reported, so the recomputed block is compared
    against the committed artifact rather than against the expectation the
    script carries.
    """
    gate = art["reproduction_gate"]
    assert gate["passed"] is True
    committed = json.loads(CANON.read_text(encoding="utf-8"))["arms"]["slope_digraph_canonical"]
    assert gate["recomputed"]["n_origins_scanned"] == committed["n_origins_scanned"]
    for bucket in ("both_safe", "naive_into_FA_safe", "no_safe_route"):
        assert gate["recomputed"][bucket] == committed["counts"][bucket], bucket


def test_the_target_set_is_the_two_fire_blind_failing_buckets(art):
    """44 is 42 + 2 and not a number the script chose."""
    committed = json.loads(CANON.read_text(encoding="utf-8"))["arms"]["slope_digraph_canonical"]
    expected = committed["counts"]["naive_into_FA_safe"] + committed["counts"]["no_safe_route"]
    assert art["target_set"]["n"] == expected
    assert len(art["per_origin"]) == expected
    by_bucket = art["target_set"]["by_bucket"]
    assert by_bucket["naive_into_FA_safe"] == committed["counts"]["naive_into_FA_safe"]
    assert by_bucket["no_safe_route"] == committed["counts"]["no_safe_route"]


def test_the_three_outcomes_partition_the_target_set(art):
    """No origin is counted twice and none is dropped."""
    outcomes = art["outcomes"]
    assert sum(outcomes.values()) == art["target_set"]["n"]
    seen = [r["outcome"] for r in art["per_origin"]]
    assert len(set(r["origin"] for r in art["per_origin"])) == len(seen)
    for name, n in outcomes.items():
        assert seen.count(name) == n, name


def test_a_not_reached_origin_is_the_filter_and_the_artifact_says_so(art):
    """The caveat that makes the saved count readable, asserted rather than trusted.

    Every origin in the target set was REACHED by the fire-blind router on the
    unfiltered graph — that is what both committed buckets require — so a
    not-reached outcome here is the node filter's doing. The artifact must carry
    that fact and the per-origin rows must agree with it.
    """
    assert art["target_set"]["all_reached_fire_blind"] is True
    assert all(r["blind_distance_m"] > 0 for r in art["per_origin"])
    assert "not the fire" in art["what_this_is_not"]


#: The artifacts a `ppy_yeongdeok_` key is allowed to come from. This test was
#: written when the prefix had exactly one artifact behind it and asserted that
#: directly; WFG-260 added two keys about the same run's INPUT FIELD, which live in
#: their own artifact with their own caveat band and are checked cell-for-cell
#: against the canonical array by tests/test_slice0_is_observation.py. The prefix is
#: deliberately shared, because it is what makes 「no ppy_yeongdeok_ count on a
#: judge-facing surface while NH-059 is open」 a greppable rule; so the partition is
#: made explicit here instead, and an unknown artifact under this prefix still fails.
#: ⚠ WFG-259 adds a THIRD kind, and the partition above is why it had to declare
#: itself here rather than slip in under the shared prefix: outcomes of the same
#: routing run with the burning set DILATED, at the two widths §5 item 5 already
#: named. It has its own artifact, its own `ppy_yeongdeok_buf_` sub-prefix, its own
#: caveat band (scripts/register_ppy_yeongdeok_buffer.py) and its own tests
#: (tests/test_ppy_yeongdeok_buffer.py), which is exactly the price this gate's
#: message asks for. The shared `ppy_yeongdeok_` prefix is kept deliberately, so
#: 「no ppy_yeongdeok_ count on a judge-facing surface while NH-059 is open」 stays
#: one grep.
_OUTCOMES = "data/processed/present_perimeter_yeongdeok_2025.json"
_SLICE0 = "data/processed/present_perimeter_yeongdeok_slice0_2025.json"
_DILATED = "data/processed/present_perimeter_buffer_shape_yeongdeok_2025.json"


def test_the_registry_entries_are_the_artifact_s_own_values(art):
    numbers = json.loads(NUMBERS.read_text(encoding="utf-8"))["numbers"]
    keys = {k: v for k, v in numbers.items() if k.startswith("ppy_yeongdeok_")}
    assert keys, "no ppy_yeongdeok_ keys registered"
    strays = {k: v["source_file"] for k, v in keys.items()
              if v["source_file"] not in (_OUTCOMES, _SLICE0, _DILATED)}
    assert not strays, (
        f"ppy_yeongdeok_ keys from an unregistered artifact: {strays}. Every key "
        "under this prefix is an OUTCOME of the zero-buffer routing run, a property "
        "of its INPUT FIELD, or an outcome of the DILATED run at a pre-registered "
        "width; a fourth kind needs its own caveat band and its own test before it "
        "is registered here."
    )
    for key, entry in keys.items():
        if entry["source_file"] != _OUTCOMES:
            continue  # tests/test_slice0_is_observation.py owns these
        cur = art
        for part in entry["json_path"].split("."):
            cur = cur[part]
        assert entry["value"] == cur, key
        assert "NOT A MARGIN" in entry["caveat"], key


def test_every_count_the_document_states_in_bold_is_the_artifact_s(doc, art):
    """The page's §4 table and its one-sentence reading, checked against the file.

    Graded by mutation when it was written: changing 26 to 25 on the page turns
    this red and names the count.
    """
    expected = {
        "saved": art["outcomes"]["saved"],
        "still_enters_forecast": art["outcomes"]["still_enters_forecast"],
        "not_reached": art["outcomes"]["not_reached"],
        "target": art["target_set"]["n"],
        "nodes_removed": art["present_perimeter_filter"]["n_nodes_removed"],
        "shelters_removed": art["present_perimeter_filter"]["n_shelters_removed"],
    }
    for key, value in (
        ("saved", "ppy_yeongdeok_saved_by_present_perimeter"),
        ("still_enters_forecast", "ppy_yeongdeok_still_enter_forecast"),
        ("not_reached", "ppy_yeongdeok_not_reached_under_filter"),
        ("nodes_removed", "ppy_yeongdeok_filter_nodes_removed"),
        ("shelters_removed", "ppy_yeongdeok_filter_shelters_removed"),
    ):
        row = next((ln for ln in doc.splitlines() if value in ln), None)
        assert row is not None, f"the document no longer names {value}"
        found = [int(t) for t in re.findall(r"\*\*(\d+)\*\*", row)]
        assert expected[key] in found, (
            f"{value}: the document's row states {found}, the artifact holds "
            f"{expected[key]}"
        )
    assert f"`ppy_yeongdeok_target_origins` **{expected['target']}**" in doc

    # The one-sentence reading is the line a reader carries away, so it is bound
    # separately from the table above it.
    reading = next(ln for ln in doc.splitlines() if "already saves" in ln)
    assert str(expected["saved"]) in reading and str(expected["still_enters_forecast"]) in reading


def test_the_saved_and_entering_counts_come_out_of_the_committed_42(art):
    """The split is along the committed buckets, which is what makes it readable."""
    committed = json.loads(CANON.read_text(encoding="utf-8"))["arms"]["slope_digraph_canonical"]
    fa_only = [r for r in art["per_origin"] if r["bucket"] == "naive_into_FA_safe"]
    assert len(fa_only) == committed["counts"]["naive_into_FA_safe"]
    saved = sum(1 for r in fa_only if r["outcome"] == "saved")
    enters = sum(1 for r in fa_only if r["outcome"] == "still_enters_forecast")
    assert saved + enters == len(fa_only), (
        "an origin from the committed naive_into_FA_safe bucket ended up outside the two "
        "outcomes the document's §4 attributes to it; the page's arithmetic no longer holds"
    )


def test_the_document_declines_to_write_the_judge_facing_sentence(doc):
    """WFG-129's own constraint: nothing reaches a judge until it has been read.

    ⚠ This test is deliberately written to be REMOVED by the lap that is licensed
    to write §6, not edited around. While it stands, the page may not carry a
    booth sentence.
    """
    assert "## 6. What a judge should hear, once this has been read" in doc
    body = doc.split("## 6. What a judge should hear, once this has been read", 1)[1]
    assert "deliberately empty" in body
    assert "부스에서 할 말" not in doc
