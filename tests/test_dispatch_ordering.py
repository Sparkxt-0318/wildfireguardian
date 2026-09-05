"""Pins for PHASE 23 — the dispatch-ordering comparison.

Three things have to stay true or the artifact stops meaning what it says:

1. the SHIPPED capacity model was not modified — its occupancy is still
   ``departure + service``, which is exactly why a separate travel-aware model
   had to be written;
2. the "no sort" control is not secretly the shipped ordering — ``dispatch`` comes
   out of ``build_dispatch_list`` already sorted by closing window, so an index
   order would compare contribution ② against itself;
3. the success rule in the experiment is the committed one, not a new one.

These pin BEHAVIOUR, not implementation, so the script stays free to change shape.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from wildfireguardian.routing.rescue import (
    DispatchEntry, RescueCapacityConfig, RescueConfig, build_dispatch_list,
    capacity_triage,
)

REPO = Path(__file__).resolve().parents[1]
ARTIFACT = REPO / "data" / "processed" / "dispatch_ordering_comparison.json"


def _entry(*, home_node, eta, survival, delay=30.0):
    return DispatchEntry(
        home_node=home_node, x=0.0, y=0.0, depot_index=0,
        responder_eta_min=eta, ingress_survival_time_min=survival,
        closing_window_min=survival - eta,
        survival_aware_exposure=0.0, shortest_path_exposure=0.0,
        shortest_path_enters_hazard=False)


# ---------------------------------------------------------------------------
# 1. the shipped model is untouched
# ---------------------------------------------------------------------------


def test_shipped_capacity_model_occupancy_is_still_departure_plus_service():
    """A unit is busy for `service` from DEPARTURE — travel does not occupy it.

    Two homes, identical deadlines, wildly different drive times. If occupancy
    counted travel, the far home would push the second departure past the window
    and only one could be served. Under the shipped rule both are served, because
    the second unit-departure is at delay + service regardless of the first drive.
    """
    cfg = RescueConfig(responder_dispatch_delay_min=30.0,
                       responder_time_budget_min=75.0)
    cap = RescueCapacityConfig(n_rescue_units=1, rescue_service_time_min=25.0)
    far = _entry(home_node=1, eta=30.0 + 40.0, survival=math.inf)   # 40 min drive
    near = _entry(home_node=2, eta=30.0 + 1.0, survival=math.inf)   # 1 min drive
    res = capacity_triage([far, near], cfg, cap)
    assert res.n_rescued_in_time == 2, (
        "the shipped occupancy rule changed: a 40-minute drive now consumes unit "
        "time. If that is deliberate, docs/dispatch_ordering.md §2 and the "
        "committed_model_order_invariance block in the artifact are both stale.")
    # and the second service starts at delay + service, not at the first arrival
    depart = sorted(o.depart_min for o in res.outcomes if o.depart_min is not None)
    assert depart == [30.0, 55.0]


def test_shipped_model_deadline_is_min_of_survival_and_window():
    cfg = RescueConfig(responder_dispatch_delay_min=30.0,
                       responder_time_budget_min=75.0)
    cap = RescueCapacityConfig(n_rescue_units=1, rescue_service_time_min=25.0)
    # arrives at 30 + 20 = 50; corridor shuts at 40 -> missed on the survival term
    shut = _entry(home_node=1, eta=50.0, survival=40.0)
    res = capacity_triage([shut], cfg, cap)
    assert res.n_rescued_in_time == 0
    assert res.outcomes[0].deadline_min == 40.0
    # same home, corridor open past the horizon -> the window term binds at 105
    open_late = _entry(home_node=1, eta=50.0, survival=math.inf)
    res2 = capacity_triage([open_late], cfg, cap)
    assert res2.n_rescued_in_time == 1
    assert res2.outcomes[0].deadline_min == pytest.approx(105.0)


def test_a_missed_home_does_not_consume_a_unit():
    """Why every ordering fills the same slots under the shipped model."""
    cfg = RescueConfig(responder_dispatch_delay_min=30.0,
                       responder_time_budget_min=75.0)
    cap = RescueCapacityConfig(n_rescue_units=1, rescue_service_time_min=25.0)
    dead = _entry(home_node=1, eta=50.0, survival=0.0)          # can never be served
    live = _entry(home_node=2, eta=31.0, survival=math.inf)
    assert capacity_triage([dead, live], cfg, cap).n_rescued_in_time == 1
    assert capacity_triage([live, dead], cfg, cap).n_rescued_in_time == 1


# ---------------------------------------------------------------------------
# 2. build_dispatch_list delivers an ALREADY-SORTED list
# ---------------------------------------------------------------------------


def test_dispatch_list_is_returned_already_sorted_by_closing_window():
    """The reason `list_order` must be the pre-sort scan order.

    If this ever stops holding, the control in run_dispatch_ordering.py is fine
    either way — but the docstring explaining WHY it exists becomes wrong.
    """
    src = (REPO / "src" / "wildfireguardian" / "routing" / "rescue.py").read_text()
    fn = src.split("def build_dispatch_list(", 1)[1].split("\ndef ", 1)[0]
    assert "dispatch.sort(key=lambda e: e.closing_window_min)" in fn, (
        "build_dispatch_list no longer sorts by closing window; "
        "run_dispatch_ordering.fixed_orders() and its docstring need re-reading")
    assert build_dispatch_list is not None


# ---------------------------------------------------------------------------
# 3. the artifact says what the documents claim it says
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not ARTIFACT.exists(),
                    reason="dispatch_ordering_comparison.json not built")
class TestArtifact:
    @staticmethod
    @pytest.fixture(scope="class")
    def doc():
        return json.loads(ARTIFACT.read_text(encoding="utf-8"))

    def test_yeongdeok_arm_is_drift_arm_b_not_the_committed_series(self, doc):
        arm = doc["arms"]["yeongdeok_2025|synthetic"]
        assert arm["reproduces_drift_arm_b"] is True
        p = arm["pipeline"]
        assert (p["n_origins"], p["n_need_rescue"], p["n_unreachable"],
                p["n_dispatch"]) == (441, 174, 32, 142)

    @staticmethod
    def _compared(doc):
        return {k: a for k, a in doc["arms"].items() if "grid" in a}

    def test_list_order_control_is_distinct_from_the_shipped_ordering(self, doc):
        for key, arm in self._compared(doc).items():
            ctl = arm["list_order_control"]
            assert ctl["distinct_from_deadline_order"], key
            assert ctl["n_positions_differing"] > 0, key

    def test_the_weakest_arm_is_run_not_dropped(self, doc):
        """STEP 0 proposed dropping yeongdeok|real for having no power.

        That premise came from a branch-only measurement at a different cutoff. At
        this repository's cutoff the key is near-constant, not constant, so the arm
        is run. If it is ever dropped again the reason has to be re-measured here.
        """
        assert "yeongdeok_2025|real" in doc["arms"]
        arm = doc["arms"]["yeongdeok_2025|real"]
        assert "grid" in arm, "the arm must be compared, not merely profiled"
        assert arm["closure_profile"]["n_distinct_closure_times"] >= 2
        note = doc["⚠ arm_that_was_going_to_be_excluded"]
        assert note["key"] == "yeongdeok_2025|real"
        assert note["decision"].startswith("RUN")

    def test_the_sensitivity_arm_is_labelled_hazard_unchecked(self, doc):
        for key, arm in self._compared(doc).items():
            note = arm["point_to_point_matrix"]["⚠"]
            assert "구간 위험 미검사" in note, key
            assert "HAZARD-UNCHECKED" in note, key

    def test_grid_keys_carry_no_dot(self, doc):
        """NUMBERS.json check paths are dot-separated; `s12.5` would split."""
        for key, arm in self._compared(doc).items():
            for cell in arm["grid"]:
                assert "." not in cell, f"{key}: {cell}"

    def test_every_cell_reports_all_four_orderings_plus_random(self, doc):
        want = {"deadline_closing_window", "nearest_eta", "earliest_closure",
                "list_order", "random"}
        for key, arm in self._compared(doc).items():
            for cell_key, cell in arm["grid"].items():
                assert want <= set(cell), f"{key}/{cell_key}"

    def test_random_arm_has_enough_repeats_to_carry_a_variance(self, doc):
        for key, arm in self._compared(doc).items():
            for cell_key, cell in arm["grid"].items():
                for u, r in cell["random"].items():
                    assert r["n_seeds"] >= 100, f"{key}/{cell_key}/{u}"
                    assert r["min"] <= r["mean"] <= r["max"]

    def test_the_headline_claim_is_the_one_the_document_states(self, doc):
        """docs/dispatch_ordering.md §0 and §5, pinned against the artifact."""
        s = doc["summary"]
        assert s["by_window"]["W75"]["deadline_wins"] == 0
        assert s["deadline_beats_nearest"]["n"] + s["deadline_ties_nearest"]["n"] \
            + s["deadline_loses_to_nearest"]["n"] == s["n_cells_headline_occupancy"]
        # every win is at the exploratory window, not the committed one
        assert all(c["window"] == "W240"
                   for c in s["deadline_beats_nearest"]["configurations"])
