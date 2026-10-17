"""Selection under protocol amendment 2: reviewed precision, proposal retention, every branch."""
import math

import pytest

from wfglink.verify.calibrate import review_counts, reviewed_metrics, select_reviewed


def _pt(name, family, recall=None, delay=0.1):
    return {"name": name, "family": family, "recall": recall, "median_confirmation_delay_s": delay,
            "available": True, "seed": 0, "q": 0.01 if family == "rules" else None,
            "threshold": None if family == "rules" else 0.9}


def _rev(t, f, a=0, u=0, accepted=None, minutes=10.0):
    shown = t + f + a + u
    return reviewed_metrics({"true": t, "false": f, "ambiguous": a, "unresolved": u},
                            accepted if accepted is not None else shown, minutes)


def test_review_counts_maps_categories_and_unresolved():
    c = review_counts(["ember", "reflection", "codec_artifact", "faint_possible_ember", "unclear", None, "ember"])
    assert c == {"true": 2, "false": 2, "ambiguous": 2, "unresolved": 1}


def test_reviewed_metrics_primary_excludes_ambiguous_and_unresolved():
    m = _rev(18, 2, a=3, u=1, accepted=48, minutes=4.0)
    assert m["precision"] == pytest.approx(0.9)
    assert m["precision_optimistic"] == pytest.approx(21 / 23)
    assert m["precision_pessimistic"] == pytest.approx(18 / 24)      # unresolved and ambiguous count against
    assert m["inclusion_probability"] == pytest.approx(24 / 48)
    assert m["false_per_supported_min"] == pytest.approx((2 / 0.5) / 4.0)
    assert m["precision_lower95"] < 0.9 and m["precision_defined"]
    assert m["true_yield_per_supported_min"] == pytest.approx(0.9 * 48 / 4.0)


def test_lower_bound_of_all_true():
    m = _rev(20, 0)
    assert m["precision"] == 1.0 and m["precision_lower95"] == pytest.approx(0.05 ** (1 / 20))
    assert not _rev(5, 0)["precision_defined"]        # fewer than 10 true + false: undefined


def test_selects_highest_retention_among_precise_points_with_family_ties():
    pts = [_pt("accept_all", "accept_all"), _pt("rules_a", "rules"), _pt("temporal_a", "temporal"),
           _pt("patch_a", "patch"), _pt("rules_loose", "rules")]
    rev = {"accept_all": _rev(10, 90, accepted=1000), "rules_a": _rev(20, 0, accepted=100),
           "temporal_a": _rev(20, 0, accepted=100), "patch_a": _rev(20, 0, accepted=100),
           "rules_loose": _rev(18, 2, accepted=400)}
    s = select_reviewed(pts, rev, observable=3)
    assert s["status"] == "SELECTED" and s["point"]["name"] == "rules_a"      # tie on retention: rules first
    assert "proposal retention" in s["recall_basis"] and "not ember recall" in s["recall_basis"]
    assert s["point"]["proposal_retention"] == pytest.approx((1.0 * 100 / 10) / (0.1 * 1000 / 10))
    assert not s["target_missed"]


def test_window_recall_ranks_when_enough_observable_truth():
    pts = [_pt("accept_all", "accept_all"), _pt("rules_a", "rules", recall=0.2), _pt("patch_a", "patch", recall=0.6)]
    rev = {"accept_all": _rev(10, 90), "rules_a": _rev(20, 0, accepted=500), "patch_a": _rev(20, 0, accepted=50)}
    s = select_reviewed(pts, rev, observable=25)
    assert s["recall_basis"] == "window truth recall" and s["point"]["name"] == "patch_a"


def test_no_precise_point_takes_highest_precision_with_retention_half():
    pts = [_pt("accept_all", "accept_all"), _pt("rules_a", "rules"), _pt("temporal_a", "temporal")]
    rev = {"accept_all": _rev(10, 10, accepted=100), "rules_a": _rev(17, 3, accepted=60),
           "temporal_a": _rev(19, 1, accepted=5)}
    s = select_reviewed(pts, rev, observable=0)
    assert s["point"]["name"] == "rules_a" and "recall >= 0.5" in s["branch"] and s["target_missed"]


def test_no_point_with_retention_half_takes_highest_defined_precision():
    pts = [_pt("accept_all", "accept_all"), _pt("rules_a", "rules"), _pt("temporal_a", "temporal")]
    rev = {"accept_all": _rev(10, 10, accepted=1000), "rules_a": _rev(15, 5, accepted=20),
           "temporal_a": _rev(18, 2, accepted=20)}
    s = select_reviewed(pts, rev, observable=0)
    assert s["point"]["name"] == "temporal_a" and s["status"] == "SELECTED" and s["target_missed"]


def test_no_defined_precision_is_insufficient_evidence():
    pts = [_pt("accept_all", "accept_all"), _pt("rules_a", "rules"), _pt("patch_a", "patch")]
    rev = {"accept_all": _rev(10, 10), "rules_a": _rev(3, 0), "patch_a": _rev(1, 1)}
    s = select_reviewed(pts, rev, observable=0)
    assert s["status"] == "INSUFFICIENT_EVIDENCE" and s["point"]["name"] == "rules_a" and s["target_missed"]


def test_accept_all_is_never_selected():
    pts = [_pt("accept_all", "accept_all"), _pt("rules_a", "rules")]
    rev = {"accept_all": _rev(20, 0, accepted=100), "rules_a": _rev(2, 0)}
    s = select_reviewed(pts, rev, observable=0)
    assert s["point"]["name"] == "rules_a" and s["status"] == "INSUFFICIENT_EVIDENCE"
    assert all(not math.isnan(x["reviewed"]["accepted_tracks"]) for x in s["rows"])
