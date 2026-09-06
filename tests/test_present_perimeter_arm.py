"""WFG-114 — the fair-opponent arm: the artifact, the registry and the prose agree.

These tests never route. Routing the arm takes about four minutes and needs the
snapshot store; what can go wrong between laps is not the routing but the three
copies of its numbers — the artifact, `docs/NUMBERS.json` and the sentences in
`docs/present_perimeter_arm.md`. So the artifact is treated as the source of
truth and the other two are checked against it, which is the failure mode
`12b8ac7` (a prose-only commit no gate could see) exists to prevent.

Nothing here reads the clock, the timezone, the network or a file outside the
repository (CHARTER §4b).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
ARTIFACT = REPO / "data/processed/present_perimeter_arm_uiseong_andong_2025.json"
DOC = REPO / "docs/present_perimeter_arm.md"
NUMBERS = REPO / "docs/NUMBERS.json"

pytestmark = pytest.mark.skipif(
    not ARTIFACT.exists(),
    reason=f"{ARTIFACT.relative_to(REPO)} not built; run "
           "scripts/run_present_perimeter_arm.py")


@pytest.fixture(scope="module")
def art() -> dict:
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def doc() -> str:
    return DOC.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# The warrant: the third column only means anything if the committed arm was
# reproduced first.
# ---------------------------------------------------------------------------

def test_the_committed_arm_was_reproduced_exactly(art):
    repro = art["reproduction_gate"]
    assert repro["reproduced"] is True, repro["differences"]
    assert repro["differences"] == []
    assert repro["recomputed_counts"] == repro["committed_counts"]


def test_the_denominator_is_the_canonical_arm_the_author_asked_about(art):
    """The row asked about the 91, which is the CANONICAL arm's bucket.

    An earlier version of this run answered on the flat arm's 96 instead, on a
    limitation that turned out to be false (see the doc's section 6). This test
    is what stops that happening again silently.
    """
    assert art["reproduction_gate"]["arm"] == "slope_digraph_canonical"
    assert art["headline"]["forecast_only"] == 91
    assert "CANONICAL" in art["parameters"]["timing_model"]
    assert art["parameters"]["slope_sampling_m"] == 60.0
    assert art["flat_arm_crosswalk"]["flat_forecast_only"] == 96


def test_both_origin_rules_are_reported_and_the_honest_one_is_primary(art):
    """The convention is worth more than the margin, so neither may be dropped.

    `strict` strands origins inside the buffer that plainly have a road out, and
    every one it strands is counted against the fair opponent — i.e. it flatters
    this project. If a later lap reports only one rule, this goes red.
    """
    cmp = art["origin_rule_comparison"]
    assert cmp["primary"] == "walk_out"
    assert cmp["walk_out"]["forecast_margin"] <= cmp["strict"]["forecast_margin"], \
        "the strict rule must not flatter the fair opponent"
    assert cmp["walk_out"]["safe_total"] == art["headline"]["safe_present_perimeter"]
    assert cmp["strict"]["unreachable"] >= cmp["walk_out"]["unreachable"]


def test_the_perfect_forecast_caveat_is_on_every_key():
    """The forecast arm plans on the field it is scored against; the keys say so."""
    numbers = json.loads(NUMBERS.read_text(encoding="utf-8"))["numbers"]
    keys = [k for k in numbers if k.startswith("pp_uiseong_")]
    assert keys
    for k in keys:
        assert "NO forecast error" in numbers[k]["caveat"], k


# ---------------------------------------------------------------------------
# Internal arithmetic. Every one of these would be a real defect, not a typo.
# ---------------------------------------------------------------------------

def test_the_forecast_only_bucket_partitions(art):
    h = art["headline"]
    assert h["recovered_by_present_perimeter"] + h["still_forecast_only"] == \
        h["forecast_only"]
    ids = art["origin_nodes"]
    assert len(ids["recovered_by_present_perimeter"]) == h["recovered_by_present_perimeter"]
    assert len(ids["still_forecast_only"]) == h["still_forecast_only"]
    assert not (set(ids["recovered_by_present_perimeter"])
                & set(ids["still_forecast_only"]))
    assert set(ids["recovered_by_present_perimeter"]) | set(ids["still_forecast_only"]) \
        == set(ids["forecast_only"])


def test_the_three_arms_add_up(art):
    h = art["headline"]
    # present-aware total = what the control already saved, plus what the buffer
    # recovered, minus what the buffer broke.
    assert h["safe_present_perimeter"] == (
        h["safe_fire_blind"] + h["recovered_by_present_perimeter"]
        + h["saved_from_no_safe_route"] - h["already_safe_broken_by_buffer"])
    # NOT safe_fire_blind + forecast_only: the fire-blind safe set is
    # both_safe + fa_exceeds_budget, and fa_exceeds_budget is by definition
    # fire-blind-safe but NOT forecast-aware-safe. The forecast-aware total is
    # both_safe + the forecast-only bucket.
    assert h["safe_forecast_aware"] == h["n_both_safe"] + h["forecast_only"]
    assert h["safe_fire_blind"] == h["n_fire_blind_safe_set"]
    # ONE budget rule across all three columns. The committed classification
    # does not budget the fire-blind route; if a later lap silently reverts to
    # that figure the control inflates and so does the buffer's apparent cost.
    assert h["safe_fire_blind"] == (h["safe_fire_blind_unbudgeted"]
                                    - h["fire_blind_late_past_budget"])
    assert h["safe_fire_blind"] <= h["safe_fire_blind_unbudgeted"]
    assert h["n_fire_blind_safe_set"] >= h["n_both_safe"]
    assert h["forecast_margin_over_present"] == (
        h["safe_forecast_aware"] - h["safe_present_perimeter"])
    for k in ("safe_fire_blind", "safe_present_perimeter", "safe_forecast_aware"):
        assert 0 < h[k] <= h["n_origins_scanned"]


def test_every_sweep_row_adds_up_the_same_way(art):
    base = art["headline"]["safe_fire_blind"]
    n = art["headline"]["n_origins_scanned"]
    for row in art["buffer_sensitivity"]:
        assert row["safe_total"] == (base + row["recovered_of_forecast_only"]
                                     + row["saved_from_no_safe_route"]
                                     - row["already_safe_broken"]), row
        # the three failure modes and the safe count are a partition of the scan
        assert (row["safe_total"] + row["failed_enters_hazard"]
                + row["failed_unreachable"] + row["failed_over_budget"]) == n, row


def test_the_buffer_band_brackets_the_headline_width(art):
    """The headline must never be the widest or narrowest thing measured.

    A single width with nothing on either side of it is a tuned number wearing a
    sensitivity check's clothes.
    """
    widths = [r["buffer_m"] for r in art["buffer_sensitivity"]]
    head = art["parameters"]["buffer_m"]
    assert head in widths
    assert min(widths) < head < max(widths)
    assert len(widths) >= 5
    assert widths == sorted(widths)


def test_the_two_failure_regimes_are_present_in_the_band(art):
    """The whole argument of the doc is that thin buffers burn and thick ones strand.

    If a future re-run flattened that into one regime, section 4 of the doc would
    be telling a story the artifact no longer supports.
    """
    rows = {r["buffer_m"]: r for r in art["buffer_sensitivity"]}
    thin = min(rows), rows[min(rows)]
    thick = max(rows), rows[max(rows)]
    assert thin[1]["failed_enters_hazard"] > 0, \
        "the narrowest buffer no longer walks anyone into the fire"
    # Thick buffers fail by stranding OR by making the walk too long to finish;
    # either is the second regime, and the doc names whichever one dominates.
    assert (thick[1]["failed_unreachable"] + thick[1]["failed_over_budget"]) > \
        (thin[1]["failed_unreachable"] + thin[1]["failed_over_budget"]), \
        "the widest buffer no longer costs more than the narrowest"
    assert thick[1]["failed_enters_hazard"] < thin[1]["failed_enters_hazard"], \
        "widening the buffer no longer reduces the walk-into-the-fire failures"


def test_the_detour_is_paired_and_positive(art):
    """Refusing ground can only lengthen a shortest path, never shorten it."""
    for scope in ("on_recovered_origins", "on_all_origins"):
        c = art["cost"][scope]
        assert c["mean_detour_m"] > 0, scope
        assert c["max_detour_m"] >= c["mean_detour_m"], scope
        assert c["present_mean_m"] > c["fire_blind_mean_m"], scope


# ---------------------------------------------------------------------------
# The registry and the prose.
# ---------------------------------------------------------------------------

def test_every_pp_key_matches_the_artifact(art):
    numbers = json.loads(NUMBERS.read_text(encoding="utf-8"))["numbers"]
    keys = [k for k in numbers if k.startswith("pp_uiseong_")]
    assert len(keys) >= 57, keys

    def dig(path):
        cur = art
        for part in path.split("."):
            cur = cur[int(part)] if isinstance(cur, list) else cur[part]
        return cur

    for k in keys:
        e = numbers[k]
        assert e["source_file"] == \
            "data/processed/present_perimeter_arm_uiseong_andong_2025.json", k
        assert e["value"] == dig(e["json_path"]), k


def test_the_caveat_travels_with_every_key():
    """A number from this run quoted without its band is the misuse to prevent."""
    numbers = json.loads(NUMBERS.read_text(encoding="utf-8"))["numbers"]
    for k, e in numbers.items():
        if not k.startswith("pp_uiseong_"):
            continue
        assert "1 km is not a discovered constant" in e["caveat"], k
        assert "NO forecast error" in e["caveat"], k
        for phrase in ("the forecast adds nothing", "1 km is the optimal buffer",
                       "예보는 필요 없다"):
            assert phrase in e["forbidden_phrasings"], (k, phrase)


def test_the_doc_prints_the_artifact_s_numbers(art, doc):
    """The doc's headline sentences are bound to the artifact, not to a lap's memory."""
    h = art["headline"]
    for value in (h["safe_fire_blind"], h["safe_present_perimeter"],
                  h["safe_forecast_aware"], h["forecast_margin_over_present"],
                  h["recovered_by_present_perimeter"], h["forecast_only"],
                  h["still_forecast_only"], h["already_safe_broken_by_buffer"]):
        assert re.search(rf"\b{value}\b", doc), f"{value} is not in the doc"


def test_the_doc_s_sensitivity_table_matches_the_sweep(art, doc):
    """Every row of section 4's table is re-read out of the artifact.

    The table is the one place a later lap could quietly soften the result, so
    each row's five counts are matched against the run that produced them.
    """
    rows = {r["buffer_m"]: r for r in art["buffer_sensitivity"]}
    body = doc.split("## 4.", 1)[1].split("## 5.", 1)[0]
    seen = 0
    for line in body.splitlines():
        m = re.match(r"^\|\s*\**\s*([\d.]+)\s*(m|km)\s*\**\s*\|", line.strip())
        if not m:
            continue
        width = float(m.group(1)) * (1000.0 if m.group(2) == "km" else 1.0)
        assert width in rows, f"the doc has a {width} m row the artifact does not"
        cells = [c.strip().replace("*", "") for c in line.strip().strip("|").split("|")]
        r = rows[width]
        assert [int(c) for c in cells[1:7]] == [
            r["recovered_of_forecast_only"], r["already_safe_broken"],
            r["safe_total"], r["failed_enters_hazard"],
            r["failed_unreachable"], r["failed_over_budget"]], line
        seen += 1
    assert seen == len(rows), f"doc table has {seen} rows, artifact has {len(rows)}"


def test_the_doc_says_what_it_does_not_show(art, doc):
    for phrase in ("does NOT show", "one region", "no forecast error here"):
        assert phrase in doc, phrase
    assert len(art["what_this_does_not_show"]) >= 3
    # ⚠ The artifact's own caveat surface is what 52 registry keys point at and
    # what the paper routine reads. A withdrawn claim left there is invisible to
    # every other gate: this run shipped the v1 "flat-timed / 96" string in it
    # for one round and nothing went red.
    blob = " ".join(art["what_this_does_not_show"])
    for withdrawn in ("flat-timed", "the flat arm's 96", "denominator is the flat"):
        assert withdrawn not in blob, withdrawn
    assert "NO forecast error" in blob
    # The withdrawal of the invented limitation stays in the document.
    assert "invented" in doc and "srtm-dem_uiseong-andong-2025" in doc


def test_no_surface_still_asserts_the_withdrawn_v1_claim():
    """The withdrawal has to reach EVERY surface, not the two that were swept.

    This run wrote its v1 story into the artifact, the doc, the arm-control
    registry and two backlog rows. Rounds two and three of review each found
    another copy still standing after the previous sweep "finished" — the last
    one in `docs/arm_protocol.json`, which `make verify` reads and a judge can
    open. So the sweep is a test, not a habit.
    """
    # The file list is the point. Rounds 2, 3 and 4 of review each found the
    # next copy AFTER the previous sweep "finished" — the last one in MEMO.md,
    # restated as advice to the next lap. So the scan covers every surface this
    # lap wrote the v1 story into, not the two that happened to be checked.
    surfaces = ("docs/arm_protocol.json",
                "data/processed/present_perimeter_arm_uiseong_andong_2025.json",
                "docs/auto/BACKLOG.md")
    for rel in surfaces:
        text = (REPO / rel).read_text(encoding="utf-8")
        for withdrawn in ("flat/DiGraph arm exactly", "every origin node id",
                          "flat-timed", "the flat arm's 96"):
            assert withdrawn not in text, f"{rel} still asserts: {withdrawn}"
    # MEMO.md is scanned too, but it legitimately QUOTES the withdrawn string in
    # the lesson about it, so only the prescriptive restatement is forbidden.
    memo = (REPO / "docs/auto/MEMO.md").read_text(encoding="utf-8")
    assert "bucket counts and every origin node id" not in memo, \
        "MEMO restates the withdrawn overstatement as advice"
    # and the arm registry must describe the arm that was actually run
    arm = json.loads((REPO / "docs/arm_protocol.json").read_text(
        encoding="utf-8"))["arms"]["present_perimeter"]
    assert "slope_digraph_canonical" in arm["reason_no_control"]
    assert "SRTM" in arm["role"]


# ---------------------------------------------------------------------------
# The one piece of NEW routing logic in this lap, on a graph small enough to
# reason about by hand. The real network's invariants were checked directly
# during the lap (364 routes, zero re-entries); these keep them gated without
# paying two minutes to rebuild a slope network in the test suite.
# ---------------------------------------------------------------------------

def _toy():
    """A 1-D corridor: 0 - 1 - 2 - 3 - 4, with 1 and 2 inside the buffer.

    Node 4 is the refuge. An origin at 0 must never pass through 1-2. An origin
    at 1 is inside the buffer and must be allowed to walk out through 2.
    """
    import networkx as nx
    from wildfireguardian.routing.future_front import RoadNetwork
    g = nx.DiGraph()
    for i in range(5):
        g.add_node(i, x=float(i) * 100.0, y=0.0)
    for a, b in [(0, 1), (1, 2), (2, 3), (3, 4)]:
        for u, v in ((a, b), (b, a)):
            g.add_edge(u, v, length_m=100.0, time_min=1.0)
    return RoadNetwork(graph=g, shelters={4}), {1, 2}


def _flat_hazard():
    """A real HazardSequence that is zero everywhere.

    Built rather than faked, because `_evaluate_path` reads `times_min` and
    samples the surfaces: a stub would test the stub.
    """
    import numpy as np
    from wildfireguardian.routing.hazard import HazardSequence
    from wildfireguardian.spread_v2.grid import CoarseGrid
    grid = CoarseGrid(minx=-500.0, miny=-500.0, maxx=1000.0, maxy=500.0,
                      cell_size_m=250.0, nrows=4, ncols=6)
    return HazardSequence(grid=grid, times_min=np.array([0.0, 600.0]),
                          surfaces=[np.zeros((4, 6)), np.zeros((4, 6))])


def test_walk_out_lets_an_in_buffer_origin_leave():
    net, refused = _toy()
    import sys
    sys.path.insert(0, str(REPO / "scripts"))
    sys.path.insert(0, str(REPO / "src"))
    import run_present_perimeter_arm as ppa
    res = ppa.walk_out_route(net, refused, net.shelters, 1, _flat_hazard(), p_cut=0.5)
    assert res.reached, res.note
    assert res.route == [1, 2, 3, 4]


def test_walk_out_never_re_enters_the_buffer():
    """An origin already outside must not transit the buffer at all."""
    import sys
    sys.path.insert(0, str(REPO / "scripts"))
    sys.path.insert(0, str(REPO / "src"))
    import run_present_perimeter_arm as ppa
    net, refused = _toy()
    # Origin 0 is outside; every path to the refuge crosses the buffer, so the
    # honest answer is "no route", NOT a route that walks through the fire.
    res = ppa.walk_out_route(net, refused, net.shelters, 0, _flat_hazard(), p_cut=0.5)
    assert not res.reached
    net2, refused2 = _toy()
    refused2 = {1}  # now 2-3-4 is clear, but 0 still has to pass 1
    res2 = ppa.walk_out_route(net2, refused2, net2.shelters, 0, _flat_hazard(),
                              p_cut=0.5)
    assert not res2.reached, "an outside origin must never transit the buffer"


def test_walk_out_and_strict_agree_for_origins_outside_the_buffer():
    """The two conventions may differ ONLY on origins inside the buffer.

    If they ever differ elsewhere, the rule comparison in the artifact is
    measuring something other than the convention.
    """
    import sys
    sys.path.insert(0, str(REPO / "scripts"))
    sys.path.insert(0, str(REPO / "src"))
    import run_present_perimeter_arm as ppa
    net, refused = _toy()
    refused = {1}
    pruned = ppa.pruned_network(net, refused)
    for origin in (0, 2, 3):
        a = ppa.walk_out_route(net, refused, net.shelters, origin, _flat_hazard(),
                               p_cut=0.5)
        b = ppa.present_perimeter_route(net, pruned, origin, _flat_hazard(),
                                        p_cut=0.5)
        assert a.reached == b.reached, origin
        assert round(a.total_distance_m, 6) == round(b.total_distance_m, 6), origin


def test_the_doc_s_origin_rule_table_matches_the_artifact(art, doc):
    """Section 2b's four numbers are the ones that decide which rule is honest.

    They are bound explicitly because that table, not section 4's, is where a
    later lap could quietly promote the flattering convention.
    """
    cmp = art["origin_rule_comparison"]
    body = doc.split("### 2b.", 1)[1].split("## 3.", 1)[0]
    for rule in ("walk_out", "strict"):
        for field in ("safe_total", "forecast_margin"):
            assert re.search(rf"\b{cmp[rule][field]}\b", body), (rule, field)
    # and the doc must name walk_out as the primary one
    assert "**`walk_out`** (primary)" in body
    assert cmp["primary"] == "walk_out"
