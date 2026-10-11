"""Independent weighted sklearn and analytical classification references."""

import math

import numpy as np
import pytest
from sklearn.metrics import (auc, average_precision_score, confusion_matrix,
                             f1_score, matthews_corrcoef, precision_recall_curve,
                             precision_score, recall_score)

from wildfire.metrics import select_classification_threshold
from wildfire.metrics import weighted_classification_metrics
from wildfire.metrics import weighted_pr_auc


def _sample():
    return (np.array([0, 1, 0, 1, 1, 0, 1]),
            np.array([0.1, 0.2, 0.2, 0.6, 0.8, 0.8, 1]),
            np.array([1, 2, 3, 4, 2, 1, 5], dtype=float))


def test_pr_auc_matches_independent_weighted_sklearn_curve_with_ties():
    y, p, w = _sample()
    precision, recall, _ = precision_recall_curve(y, p, sample_weight=w)
    assert weighted_pr_auc(y, p, w) == pytest.approx(auc(recall, precision), abs=1e-15)


def test_constant_predictor_trapezoid_area_is_distinct_from_average_precision():
    y = np.array([0, 0, 1])
    p = np.full(3, 0.5)
    w = np.array([1, 2, 1], dtype=float)
    prevalence = 0.25
    assert weighted_pr_auc(y, p, w) == pytest.approx((1 + prevalence) / 2)
    assert average_precision_score(y, p, sample_weight=w) == prevalence
    assert weighted_pr_auc(y, p, w) != prevalence


def test_confusion_scores_match_hand_computed_weighted_counts():
    y = [1, 0, 0, 1]
    p = [0.9, 0.8, 0.1, 0.2]
    w = [3, 2, 5, 4]
    scores = weighted_classification_metrics(y, p, w, threshold=0.5)
    assert {name: scores[name] for name in ("tp", "fp", "tn", "fn")} == {
        "tp": 3, "fp": 2, "tn": 5, "fn": 4,
    }
    assert scores["precision"] == pytest.approx(3 / 5)
    assert scores["recall"] == pytest.approx(3 / 7)
    assert scores["f1"] == pytest.approx(6 / 12)
    assert scores["mcc"] == pytest.approx((3 * 5 - 2 * 4) / math.sqrt(5 * 7 * 7 * 9))


@pytest.mark.parametrize("threshold", [0, 0.2, 0.5, 0.8, 1, np.nextafter(1, np.inf), -1, 2])
def test_weighted_metrics_equal_sklearn_at_finite_thresholds(threshold):
    y, p, w = _sample()
    decision = p >= threshold
    scores = weighted_classification_metrics(y, p, w, threshold=threshold)
    tn, fp, fn, tp = confusion_matrix(y, decision, sample_weight=w, labels=[0, 1]).ravel()
    assert [scores[key] for key in ("tn", "fp", "fn", "tp")] == [tn, fp, fn, tp]
    assert scores["precision"] == pytest.approx(precision_score(y, decision, sample_weight=w, zero_division=0))
    assert scores["recall"] == pytest.approx(recall_score(y, decision, sample_weight=w, zero_division=0))
    assert scores["f1"] == pytest.approx(f1_score(y, decision, sample_weight=w, zero_division=0))
    assert scores["mcc"] == pytest.approx(matthews_corrcoef(y, decision, sample_weight=w), abs=1e-15)


@pytest.mark.parametrize("criterion", ["f1", "mcc"])
def test_selected_validation_threshold_equals_independent_enumeration(criterion):
    y, p, w = _sample()
    candidates = np.r_[np.unique(p), np.nextafter(p.max(), np.inf)]
    sklearn_metric = f1_score if criterion == "f1" else matthews_corrcoef
    expected = []
    for threshold in candidates:
        options = {"sample_weight": w}
        if criterion == "f1":
            options["zero_division"] = 0
        expected.append((sklearn_metric(y, p >= threshold, **options), threshold))
    value, threshold = max(expected)
    selected = select_classification_threshold(y, p, w, criterion=criterion)
    assert selected["threshold"] == threshold
    assert selected["validation_metric_value"] == pytest.approx(value, abs=1e-15)
    assert selected["candidate_count"] == len(candidates)
    assert selected["decision_rule"] == "prediction_probability >= threshold"
    assert selected["selected_on"] == "validation"
    assert not selected["unidentifiable"]


def test_exact_ties_choose_highest_candidate_and_group_equal_scores():
    # MCC is zero for every threshold with a single observed class.
    selected = select_classification_threshold([0, 0, 0], [0.2, 0.2, 1], [1, 2, 3], criterion="mcc")
    assert selected["threshold"] == np.nextafter(1, np.inf)
    assert selected["candidate_count"] == 3
    assert selected["unidentifiable"]
    assert selected["validation_metric_value"] == 0
    assert selected["validation_metrics"]["tp"] == selected["validation_metrics"]["fp"] == 0


def test_selection_is_applied_unchanged_to_test_data():
    selected = select_classification_threshold([0, 1], [0.1, 0.8], [1, 1])
    assert selected["threshold"] == 0.8
    test = weighted_classification_metrics([0, 1], [0.6, 0.7], [1, 1],
                                           threshold=selected["threshold"])
    assert test["threshold"] == 0.8
    assert test["tp"] == test["fp"] == 0
    assert test["f1"] == 0


@pytest.mark.parametrize("label", [0, 1])
def test_single_class_degenerate_mcc_and_threshold_identifiability(label):
    scores = weighted_classification_metrics([label, label], [0.2, 0.8], [1, 3], threshold=0.5)
    assert scores["mcc"] == 0
    assert select_classification_threshold([label, label], [0.2, 0.8], [1, 3])["unidentifiable"]
    assert weighted_pr_auc([label, label], [0.2, 0.8], [1, 3]) == (None if label == 0 else 1)


def test_scores_and_selected_threshold_are_invariant_to_common_weight_scale():
    y, p, w = _sample()
    normal = weighted_classification_metrics(y, p, w, threshold=0.5)
    # Raw fourth-order MCC arithmetic and 2*TP would overflow at this scale.
    scale = 9e306
    large = weighted_classification_metrics(y, p, w * scale, threshold=0.5)
    for metric in ("precision", "recall", "f1", "mcc"):
        assert large[metric] == pytest.approx(normal[metric], abs=1e-15)
    for count in ("tp", "fp", "tn", "fn"):
        assert large[count] == pytest.approx(normal[count] * scale)
    assert weighted_pr_auc(y, p, w * scale) == pytest.approx(weighted_pr_auc(y, p, w))
    for criterion in ("f1", "mcc"):
        assert select_classification_threshold(y, p, w * scale, criterion=criterion)["threshold"] == select_classification_threshold(y, p, w, criterion=criterion)["threshold"]


def test_perfect_mcc_retains_an_extreme_rare_class_without_underflow():
    scores = weighted_classification_metrics([0, 1], [0, 1], [1e308, 1e-300], threshold=0.5)
    assert scores["precision"] == scores["recall"] == scores["f1"] == scores["mcc"] == 1


@pytest.mark.parametrize("threshold", [True, np.nan, np.inf, -np.inf, "0.5"])
def test_invalid_threshold_is_rejected(threshold):
    with pytest.raises(ValueError, match="threshold"):
        weighted_classification_metrics([0], [0.5], [1], threshold=threshold)


@pytest.mark.parametrize("y,p,w", [
    ([], [], []), ([[0]], [0.5], [1]), ([0], [[0.5]], [1]), ([0], [0.5], [[1]]),
    ([0, 1], [0.5], [1, 1]), ([0.25], [0.5], [1]), ([0], [-0.1], [1]),
    ([0], [1.1], [1]), ([np.nan], [0.5], [1]), ([0], [np.inf], [1]),
    ([0], [0.5], [0]), ([0], [0.5], [-1]), ([0], [0.5], [np.nan]),
    ([0, 1], [0.2, 0.8], [1e308, 1e308]),
])
def test_invalid_inputs_are_rejected_by_every_api(y, p, w):
    for call in (lambda: weighted_pr_auc(y, p, w),
                 lambda: weighted_classification_metrics(y, p, w, threshold=0.5),
                 lambda: select_classification_threshold(y, p, w)):
        with pytest.raises(ValueError):
            call()


def test_invalid_selection_criterion_is_rejected():
    with pytest.raises(ValueError, match="criterion"):
        select_classification_threshold([0, 1], [0.2, 0.8], [1, 1], criterion="accuracy")
