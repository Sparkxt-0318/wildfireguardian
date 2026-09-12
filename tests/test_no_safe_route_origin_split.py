"""WFG-262 — the `no_safe_route` bucket, its sheet sentence, and the invariant
that keeps the bucket clean.

`routing/evacuation.py::future_aware_route` has a guard that returns
``reached=False`` **before any search runs**, when the origin's own node is
already at or above ``p_cut`` at departure. `live/pipeline.py`'s classifier
branches only on ``reached`` and ``enters_hazard``, so such an origin lands in
``no_safe_route`` — whose A4 sheet line used to tell a dispatcher that a budget
was consumed and detours were tried.

Measured on the committed fields, that never happens: all three copies of
``candidate_origins`` skip a node with ``hazard.prob_at(x, y, 0.0) >= p_cut``,
which at ``departure_min = 0`` is the same predicate the guard tests. **That
invariant is the only thing keeping the bucket clean, it lives three files from
the branch it protects, and nothing tied the two predicates together before
this file.** These tests are that tie.

They are deliberately clock-free, network-free and DEM-free: the reachability
tests build a small synthetic field, and the artifact tests read the committed
JSON. Nothing here re-runs a scan or moves a committed number.
"""
from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
import numpy as np
import pytest

from wildfireguardian.live.pipeline import BUCKET_TEXT, ORIGIN_REFUSED_TEXT
from wildfireguardian.routing.evacuation import (
    ORIGIN_REFUSED_NOTE, build_time_expanded_field, future_aware_route,
)
from wildfireguardian.routing.future_front import RoadNetwork
from wildfireguardian.routing.hazard import HazardSequence
from wildfireguardian.routing.slope import ELDERLY_FLAT_SPEED_MS
from wildfireguardian.spread_v2.grid import CoarseGrid

REPO = Path(__file__).resolve().parents[1]
ARTIFACT = (REPO / "data/processed/no_safe_route_origin_split"
            / "split_20260912T0026Z.json")

#: The guard's own words. Imported, not restated: the point of WFG-262 is that
#: the note has one home and at least one reader.
GUARD_NOTE = ORIGIN_REFUSED_NOTE

P_CUT = 0.5


def _tiny_field(origin_p: float):
    """Two nodes 100 m apart, one a refuge; the origin sits at ``origin_p``.

    The grid is 1 x 2 cells of 100 m, so each node owns exactly one cell and the
    origin's probability is set directly. No clock, no files, no network.
    """
    grid = CoarseGrid(minx=0.0, miny=0.0, maxx=200.0, maxy=100.0,
                      cell_size_m=100.0, nrows=1, ncols=2)
    surf = np.array([[origin_p, 0.0]], dtype=np.float32)
    hazard = HazardSequence(grid=grid, times_min=np.array([0.0, 600.0]),
                            surfaces=[surf, surf])
    g = nx.Graph()
    g.add_node(1, x=50.0, y=50.0)
    g.add_node(2, x=150.0, y=50.0)
    g.add_edge(1, 2, length_m=100.0,
               time_min=(100.0 / ELDERLY_FLAT_SPEED_MS) / 60.0)
    return RoadNetwork(graph=g, shelters={2}), hazard


# --------------------------------------------------------------------------
# 1. The guard exists, fires, and says why — and the note is READ, not just set
# --------------------------------------------------------------------------

def test_the_guard_fires_when_the_origin_is_already_at_the_cutoff():
    """An origin at/above p_cut at departure is refused before any search."""
    net, hazard = _tiny_field(origin_p=0.9)
    res = future_aware_route(net, 1, hazard, departure_min=0.0,
                             time_budget_min=600.0, p_cut=P_CUT,
                             time_step_min=10.0)
    assert res.reached is False
    assert res.enters_hazard is True
    assert res.route == []
    assert res.note == GUARD_NOTE


def test_the_guard_does_not_fire_just_below_the_cutoff():
    """The predicate is `>= p_cut`, so just below it the search actually runs.

    This is the control for the test above: without it, a guard that fired for
    every origin would pass it.
    """
    net, hazard = _tiny_field(origin_p=P_CUT - 1e-6)
    res = future_aware_route(net, 1, hazard, departure_min=0.0,
                             time_budget_min=600.0, p_cut=P_CUT,
                             time_step_min=10.0)
    assert res.reached is True
    assert res.note != GUARD_NOTE


def test_the_guard_note_is_read_outside_the_module_that_defines_it():
    """Critic #70's finding: one grep hit, the definition, and nothing read it.

    A `note` no caller reads cannot distinguish 「we searched and found nothing」
    from 「the fire is already at the house」, which on a rescue-dispatch sheet
    are opposite instructions. This test fails if the note goes back to being
    write-only: it requires at least one READER outside the definition site.
    """
    readers = []
    for path in sorted((REPO / "src").glob("**/*.py")):
        rel = path.relative_to(REPO).as_posix()
        if rel == "src/wildfireguardian/routing/evacuation.py":
            continue
        if "ORIGIN_REFUSED_NOTE" in path.read_text(encoding="utf-8"):
            readers.append(rel)
    assert readers, (
        "no module outside routing/evacuation.py reads ORIGIN_REFUSED_NOTE. "
        "That is critic #70's finding restored: an origin refused before any "
        "search becomes indistinguishable, downstream, from one whose search "
        "failed, and the dispatch sheet reports the wrong one.")
    assert "src/wildfireguardian/live/pipeline.py" in readers, readers


def test_the_refused_origin_gets_its_own_sheet_line_asserting_no_cause():
    """It must not silently inherit `no_safe_route`'s line.

    Nothing was routed for this origin: no budget was consumed, no detour was
    tried, no search ran. The line may claim none of the three.
    """
    text = ORIGIN_REFUSED_TEXT
    for banned in ("예산", "우회", "경로가 없음"):
        assert banned not in text, (
            f"the refused-origin sheet line asserts {banned!r}, which did not "
            f"happen for this origin: {text!r}")
    assert "탐색 없음" in text, text
    assert "—" not in text, (
        f"CHARTER §8: no em-dashes in shipped screens (font subset): {text!r}")
    assert text != BUCKET_TEXT["no_safe_route"][1], (
        "the refused origin must not print the bucket's own line")


# --------------------------------------------------------------------------
# 2. The sheet sentence asserts no cause
# --------------------------------------------------------------------------

def test_the_no_safe_route_sheet_sentence_asserts_no_cause():
    """docs/routing_limitations.md §6: state the code condition and no more.

    The bucket's condition is only 「naive enters the hazard AND the
    future-aware search reached no refuge」. A budget claim is not established
    by it — the ceil-rounded hazard gate closes every detour with the budget
    nowhere near binding, which is §1's mechanism unchanged.
    """
    _, text = BUCKET_TEXT["no_safe_route"]
    assert "예산" not in text, (
        f"the no_safe_route sheet line asserts a BUDGET as the cause: {text!r}. "
        "The code condition does not establish one (docs/routing_limitations.md "
        "§1 and §6).")
    assert "우회 포함" not in text, (
        f"the no_safe_route sheet line asserts detours were tried and "
        f"exhausted: {text!r}. The code condition does not establish that.")
    assert "확인되지 않음" in text, (
        f"the no_safe_route sheet line should report a NON-CONFIRMATION, the "
        f"form §1 settled on for fa_exceeds_budget: {text!r}")


def test_the_walk_unreachable_fallback_asserts_no_cause_either():
    """Found by this lap's independent reviewer, 29 lines above the dict.

    It is the line printed when an unreachable point carries no `reason_ko` at
    all, so it stands in for a cause nobody computed. A budget claim is worse
    there than in the dict, not better.
    """
    from wildfireguardian.live.pipeline import WALK_UNREACHABLE_FALLBACK as fb
    assert "예산" not in fb, (
        f"the walk-side unreachable fallback asserts a BUDGET: {fb!r}")
    assert "우회" not in fb, (
        f"the walk-side unreachable fallback asserts detours were tried: {fb!r}")


def test_both_audited_buckets_use_the_same_non_assertive_form():
    """§1 and §6 are the same audit; their sheet lines should read the same way."""
    for bucket in ("no_safe_route", "fa_exceeds_budget"):
        _, text = BUCKET_TEXT[bucket]
        assert text.endswith("확인되지 않음"), (
            f"{bucket} was audited for cause assertion and should close on a "
            f"non-confirmation: {text!r}")


def test_no_shipped_bucket_sentence_carries_an_em_dash_regression():
    """CHARTER §8: no em-dashes in shipped screens (font subset).

    `naive_into_FA_safe` carries one and is the known, committed exception; this
    pins that the WFG-262 edit did not add a second.
    """
    offenders = [k for k, (_, t) in BUCKET_TEXT.items()
                 if "—" in t and k != "naive_into_FA_safe"]
    assert not offenders, offenders


# --------------------------------------------------------------------------
# 3. The invariant: the origin rule and the guard test the same predicate
# --------------------------------------------------------------------------

def test_the_origin_filter_and_the_guard_are_the_same_predicate_at_departure():
    """The whole reason the committed bucket is clean, pinned in one place.

    `candidate_origins` skips a node with `hazard.prob_at(x, y, 0.0) >= p_cut`;
    `build_time_expanded_field` fills `table[:, 0]` with
    `prob_at_points(nx, ny, departure_min + 0)`. At `departure_min = 0` those
    must agree exactly, or an origin the scan admits is one the router refuses
    before searching — and the sheet then reports the wrong thing about a
    household the fire has already reached.
    """
    net, hazard = _tiny_field(origin_p=0.42)
    field = build_time_expanded_field(net, hazard, departure_min=0.0,
                                      time_budget_min=600.0, p_cut=P_CUT,
                                      time_step_min=10.0)
    for n in net.graph.nodes:
        x, y = net.node_xy(n)
        scan_side = hazard.prob_at(x, y, 0.0)
        guard_side = field.table[field.idx[n], 0]
        assert scan_side == pytest.approx(guard_side, abs=0.0), (
            f"node {n}: candidate_origins reads {scan_side} and the guard reads "
            f"{guard_side}. These must be the same number at departure_min = 0.")


def test_the_three_origin_rules_still_carry_the_p_cut_filter():
    """Three duplicated copies, and the invariant needs all three.

    The duplication is deliberate (each file says why), which is exactly what
    makes it easy for one copy to drift. Losing the filter in any of them
    readmits the origins the guard refuses.
    """
    needle = "hazard.prob_at(x, y, 0.0) >= p_cut"
    for rel in ("scripts/run_real_roads_real_hazard_slope.py",
                "scripts/run_multi_region_routing.py",
                "src/wildfireguardian/live/pipeline.py"):
        src = (REPO / rel).read_text(encoding="utf-8")
        assert needle in src, (
            f"{rel} no longer skips origins already at/above the cutoff at "
            f"departure. That readmits exactly the origins "
            f"routing/evacuation.py refuses before searching, and puts them in "
            f"no_safe_route (WFG-262, docs/routing_limitations.md §6).")


# --------------------------------------------------------------------------
# 4. The committed artifact says what the doc says
# --------------------------------------------------------------------------

@pytest.mark.skipif(not ARTIFACT.exists(),
                    reason="WFG-262 split artifact not in this checkout")
def test_the_split_artifact_passed_its_identity_controls():
    art = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert art["identity_controls_failed"] == [], art["identity_controls_failed"]
    for row in art["regions"]:
        c = row["identity_controls"]
        assert c["n_nodes_match"], row["region"]
        assert c["n_origins_match"], row["region"]


@pytest.mark.skipif(not ARTIFACT.exists(),
                    reason="WFG-262 split artifact not in this checkout")
def test_the_split_artifact_covers_the_three_committed_regions():
    art = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    got = {r["region"] for r in art["regions"]}
    assert got == {"yeongdeok_2025", "uiseong_andong_2025",
                   "uljin_samcheok_2022"}, got
    # The committed bucket counts the row was filed about, unmoved.
    by = {r["region"]: r["no_safe_route_committed"] for r in art["regions"]}
    assert by == {"yeongdeok_2025": 2, "uiseong_andong_2025": 12,
                  "uljin_samcheok_2022": 10}, by


@pytest.mark.skipif(not ARTIFACT.exists(),
                    reason="WFG-262 split artifact not in this checkout")
def test_every_committed_member_was_checked_individually_where_recorded():
    """Two of the three artifacts recorded their bucket membership.

    For those, the aggregate is not enough: each listed member must have been
    resolved in the rebuilt graph and tested, or the zero is an inference.
    """
    art = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    checked = 0
    for row in art["regions"]:
        mc = row["committed_membership_check"]
        if mc is None:
            continue
        checked += 1
        assert (mc["n_members_resolvable_in_rebuilt_graph"]
                == mc["n_members_committed"]), row["region"]
        assert mc["n_members_at_or_above_p_cut_at_departure"] == 0, row["region"]
    assert checked == 2, (
        f"expected 2 regions to carry origin_nodes_by_bucket, got {checked}")


@pytest.mark.skipif(not ARTIFACT.exists(),
                    reason="WFG-262 split artifact not in this checkout")
def test_the_doc_and_the_artifact_agree_that_the_count_is_zero():
    """§6's table and the artifact are one fact, not two."""
    art = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert art["total_origins_removed_before_search"] == 0
    for row in art["regions"]:
        assert row["n_origins_removed_before_search"] == 0, row["region"]
    doc = (REPO / "docs/routing_limitations.md").read_text(encoding="utf-8")
    assert "## 6. `no_safe_route` named a cause too" in doc
    assert "refused before any search" in doc


@pytest.mark.skipif(not ARTIFACT.exists(),
                    reason="WFG-262 split artifact not in this checkout")
def test_the_yeongdeok_margin_is_recorded_because_it_is_thin():
    """The invariant holds by arithmetic, not by design intent.

    If a later field pushes a scanned origin's departure probability up to the
    cutoff, the origin rule stops excluding it and the guard starts firing. The
    margin is recorded so that day is visible rather than surprising.
    """
    art = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    yd = next(r for r in art["regions"] if r["region"] == "yeongdeok_2025")
    margin = yd["max_prob_at_departure_over_scanned_origins"]
    assert margin < P_CUT, (
        "a scanned Yeongdeok origin is at or above the cutoff at departure; the "
        "guard now fires inside the committed scan and no_safe_route is "
        "contaminated (WFG-262)")
    assert P_CUT - margin < 0.01, (
        f"the recorded margin is {P_CUT - margin}, no longer the thin one §6 "
        f"describes. Update the doc rather than the assertion.")
