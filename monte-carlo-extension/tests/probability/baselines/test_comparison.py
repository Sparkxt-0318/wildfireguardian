"""Check comparison invariants independently of the forest training routine."""

import numpy as np
import pytest
import json

from wildfire.evaluate import assert_identities
from wildfire.evaluate import cluster_bootstrap_brier
from wildfire.evaluate import score_payload
from wildfire.cache import CachedSplit
from wildfire.metrics import select_classification_threshold
from wildfire.metrics import probability_metrics_with_all
from wildfire.evaluate import assert_preserved
from wildfire.report import generate_report


def test_distance_extension_preserves_nested_candidate_metrics_and_rejects_changed_values():
    previous = {"candidates": [{"name": "rf", "metrics": {"brier": .2}}]}
    extended = {"candidates": [{"name": "rf", "metrics": {"brier": .2, "distance": .3}}]}
    assert_preserved(previous, extended)
    extended["candidates"][0]["metrics"]["brier"] = .21
    with pytest.raises(AssertionError, match="candidates/0/metrics/brier"):
        assert_preserved(previous, extended)
    with pytest.raises(AssertionError, match="Existing list changed"):
        assert_preserved(previous, {"candidates": []})


def test_event_bootstrap_resamples_fires_and_uses_ratio_of_weighted_totals():
    # Two events with different population weights: a rowwise or macro-event
    # average gives a different point estimate from the required pooled score.
    payload = {"event_index": np.array([0, 0, 1]),
               "w": np.array([1., 3., 8.]), "y": np.array([1., 0., 1.]),
               "ours_original_5": np.array([.5, .5, .5]),
               "rf_5": np.array([1., 0., 0.])}
    result = cluster_bootstrap_brier(payload, "rf_5", draws=2000, seed=19)
    # Event0 difference=-1, totalweight=4; event1 difference=6, totalweight=8.
    assert result["point_difference"] == pytest.approx(5 / 12)
    assert result["percentile_95_interval"] == pytest.approx([-.25, .75])
    assert result["contributing_fires"] == 2
    # This equality checks paired deterministic resampling, not fitted outputs.
    assert result == cluster_bootstrap_brier(payload, "rf_5", draws=2000, seed=19)


def test_saved_cohort_rejects_reordered_or_duplicate_cell_hours():
    data = CachedSplit(environment=np.zeros((2, 1, 3, 3), np.float32),
                       burned=np.zeros((2, 1, 3, 3), np.float32),
                       target=np.array([0, 1], np.float32), weight=np.ones(2),
                       event_index=np.array([0, 0]), time_utc=np.array([0, 3600]),
                       row=np.array([1, 1]), col=np.array([2, 2]))
    payload = {"y": data.target.copy(), "w": data.weight.copy(),
               **{key: getattr(data, key).copy() for key in ("event_index", "time_utc", "row", "col")}}
    assert_identities(data, np.arange(2), payload)
    with pytest.raises(AssertionError):
        assert_identities(data, np.array([1, 0]), payload)
    payload["time_utc"][:] = 0
    duplicate = CachedSplit(**{**data.__dict__, "time_utc": np.zeros(2, dtype=np.int64)})
    with pytest.raises(ValueError, match="Duplicate"):
        assert_identities(duplicate, np.arange(2), payload)


def test_native_metrics_filter_each_footprint_while_preserving_all_predictions():
    payload = {"event_index": np.array([0, 0]), "w": np.array([1., 3.]),
               "y": np.array([1., 0.]), "rf_3": np.array([.5, .5]), "rf_5": np.array([.5, .5])}
    metadata = {"event_ids": ["fire"], "per_event": {"fire": {"country": "US"}}}
    record = score_payload(payload, {"rf_3": np.array([0, 1]), "rf_5": np.array([1, 2])}, metadata)
    assert record["models"]["rf_3"]["sample_count"] == 1
    assert record["models"]["rf_5"]["sample_count"] == 2
    assert record["models"]["rf_3"]["zero_contact_positive_sample_count"] == 0
    assert record["models"]["rf_5"]["zero_contact_positive_sample_count"] == 0
    assert record["models"]["rf_3"]["brier"] == record["models"]["rf_5"]["brier"] == .25
    assert record["by_country"]["US"]["models"]["rf_3"]["zero_contact_positive_sample_count"] == 0
    assert record["models"]["rf_3"]["represented_population_weight"] == 3
    assert record["models"]["rf_5"]["represented_population_weight"] == 4
    assert len(payload["rf_3"]) == 2  # Evaluation filtering leaves prediction coverage intact.


def test_complete_metric_set_applies_validation_thresholds_without_test_reselection():
    probability, weight = np.array([.1, .2]), np.ones(2)
    validation_labels = np.array([0, 1])
    thresholds = {criterion: select_classification_threshold(validation_labels, probability, weight, criterion=criterion)
                  for criterion in ("f1", "mcc")}
    # The labels reverse on test: its optimal F1 threshold differs. The metric
    # wrapper must still use the frozen validation choice, yielding F1=0.
    test_labels = np.array([1, 0])
    test = probability_metrics_with_all(test_labels, probability, weight, np.ones(2), thresholds=thresholds)
    assert test["validation_f1_threshold"] == test["validation_mcc_threshold"] == .2
    assert test["f1_at_validation_f1_threshold"] == 0
    assert test["mcc_at_validation_mcc_threshold"] == -1
    assert test["bernoulli_total_variation_distance_mean"] == pytest.approx(.55)
    assert test["bernoulli_wasserstein_1_distance_mean"] == test["bernoulli_total_variation_distance_mean"]
    assert test["bernoulli_bhattacharyya_distance_mean"] == pytest.approx(test["bernoulli_kl_divergence_mean"] /2)
    assert select_classification_threshold(test_labels, probability, weight, criterion="f1")["threshold"] == .1


def test_active_report_uses_exponential_reference_and_per_footprint_contact_counts(tmp_path):
    payload = {"event_index": np.array([0, 0]), "w": np.array([1., 3.]), "y": np.array([1., 0.]),
               "ours_original_5": np.array([.7, .2]), "rf_3": np.array([.5, .3]), "rf_5": np.array([.6, .1]),
               "control_train_prevalence": np.array([.25, .25]), "control_no_spread": np.array([0., 0.])}
    metadata = {"event_ids": ["fire"], "per_event": {"fire": {"country": "US"}}}
    thresholds = {name: {criterion: select_classification_threshold(payload["y"], payload[name], payload["w"], criterion=criterion)
                         for criterion in ("f1", "mcc")}
                  for name in payload if name.startswith(("rf_", "ours_", "control_"))}
    shared = score_payload(payload, np.array([1, 1]), metadata, thresholds)
    counts = {name: np.array([0, 1]) if name == "rf_3" else np.ones(2) for name in thresholds}
    native = score_payload(payload, counts, metadata, thresholds)
    data = {"protocol": {"n_estimators": 1, "seed": 7, "depth_grid": [1]},
            "selection": {"training_sample_count": 2, "training_event_count": 1, "training_weighted_prevalence": .25,
                          "selected": {name: {"max_depth": 1, "n_features": 180 if name == "rf_3" else 500, "validation_brier": .2}
                                       for name in ("rf_3", "rf_5")}},
            "shared": {"test": shared}, "native": {"test": native}}
    (tmp_path / "metrics.json").write_text(json.dumps(data))
    generate_report(tmp_path)
    report = (tmp_path / "report.md").read_text()
    assert "Nonnegative exponential kernel" in report
    assert "signed" not in report
    assert "per-model sample counts can differ" in report
    assert (tmp_path / "comparison.png").stat().st_size > 1000
    rows = (tmp_path / "metrics.csv").read_text()
    assert "ours_original_5" in rows and "ours_direct_5" not in rows
    assert native["models"]["rf_3"]["sample_count"] == 1
