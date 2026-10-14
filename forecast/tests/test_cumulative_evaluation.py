"""Cumulative target alignment, evaluation cohorts, and independent score oracles."""

from copy import deepcopy
import json
import math
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from wildfire import CumulativePrediction, Prediction


def _result(probability, *, hours=(1,), burned_probability=None, valid=None,
            time_utc=10_000, time_valid=None, pixel_valid=None, event_id="fixture",
            method="recursive"):
    probability = np.asarray(probability, dtype=np.float64)
    if valid is None:
        valid = np.ones(probability.shape, dtype=bool)
    if burned_probability is not None:
        burned_probability = np.asarray(burned_probability, dtype=np.float64)
    predictions = []
    for i, hour in enumerate(hours):
        values = torch.from_numpy(probability[i].copy())
        known = torch.from_numpy(np.asarray(valid[i], dtype=bool).copy())
        details = SimpleNamespace(
            probability=values, valid=known,
            rate=torch.full_like(values, torch.nan), rate_valid=torch.zeros_like(known),
        )
        predictions.append(Prediction.from_details(
            details, dt_hours=hour, time_utc=np.asarray(time_utc, dtype=np.int64),
            time_valid=time_valid, pixel_valid=pixel_valid, event_id=event_id,
            burned_probability=(None if burned_probability is None
                                else torch.from_numpy(burned_probability[i].copy())),
            metadata={"method": method, "n_samples": 16} if method == "recursive"
            else {"method": method},
        ))
    return CumulativePrediction(tuple(hours), tuple(predictions))


def _snapshot(probability, *, hours=(1,), burned_probability=None, valid=None, **options):
    shape = (len(hours), 1, 1, -1)
    return _result(
        np.asarray(probability).reshape(shape), hours=hours,
        burned_probability=(None if burned_probability is None
                            else np.asarray(burned_probability).reshape(shape)),
        valid=None if valid is None else np.asarray(valid).reshape(shape), **options,
    )


def _reference(states, *, times=(10_000, 13_600), valid=None, event_id="fixture", **options):
    values = np.asarray(states, dtype=float).reshape(len(times), 1, 1, -1)
    return dict(
        burned_area=values,
        burned_area_valid=(np.ones(values.shape, dtype=bool) if valid is None
                           else np.asarray(valid, dtype=bool).reshape(values.shape)),
        time_utc=np.asarray(times, dtype=np.int64),
        time_valid=np.ones(len(times), dtype=bool), event_id=event_id, **options,
    )


def _evaluate(prediction, observed, **options):
    options.setdefault("hours", prediction.hours)
    return prediction.evaluate(observed, **options)


def _row(report, hour):
    return next(row for row in report["per_horizon"] if row["hours"] == hour)


def _entropy(p):
    return sum(-q * math.log(q) for q in (p, 1 - p) if q > 0)


def _independent_scores(labels, probabilities, weights):
    rows = []
    for y, p in zip(labels, probabilities):
        error = abs(y - p)
        mass = p if y else 1 - p
        nll = -math.log(mass) if mass else math.inf
        js = max(0, _entropy(error / 2) - _entropy(error) / 2)
        rows.append({
            "brier": error**2,
            "exact_negative_log_likelihood_mean": nll,
            "bernoulli_kl_divergence_mean": nll,
            "bernoulli_total_variation_distance_mean": error,
            "bernoulli_hellinger_distance_mean": math.sqrt(1 - math.sqrt(mass)),
            "bernoulli_jensen_shannon_divergence_mean": js,
            "bernoulli_jensen_shannon_distance_mean": math.sqrt(js),
            "bernoulli_bhattacharyya_distance_mean": nll / 2,
            "bernoulli_wasserstein_1_distance_mean": error,
            "bernoulli_wasserstein_2_distance_mean": math.sqrt(error),
        })
    return {
        name: ("infinity" if any(math.isinf(row[name]) for row in rows)
               else sum(w * row[name] for w, row in zip(weights, rows)) / sum(weights))
        for name in rows[0]
    }


def _assert_scores(actual, expected):
    for name, value in expected.items():
        if value == "infinity":
            assert actual[name] == value
        else:
            assert actual[name] == pytest.approx(value, abs=3e-15)


def test_public_function_and_method_pair_new_and_total_targets_with_the_correct_probability_fields():
    from wildfire import evaluate_cumulative

    result = _snapshot([0, .4, .2], burned_probability=[1, .4, .2])
    observed = _reference([[1, 0, 0], [1, 1, 0]])
    weights = np.asarray([[2, 1, 3]], dtype=float)
    new = _evaluate(result, observed, weight=weights)
    total = evaluate_cumulative(result, observed, hours=1, quantity="burned", weight=weights)
    assert new["protocol"]["quantity"] == "new_burn"
    assert new["protocol"]["probability_field"] == "probability"
    assert total["protocol"]["quantity"] == "burned"
    assert total["protocol"]["probability_field"] == "burned_probability"
    new_row, total_row = _row(new, 1), _row(total, 1)
    assert new_row["coverage"]["initially_burned_excluded_cells"] == 1
    assert new_row["metrics"]["sample_count"] == 2
    assert total_row["metrics"]["sample_count"] == 3
    _assert_scores(new_row["metrics"], _independent_scores([1, 0], [.4, .2], [1, 3]))
    _assert_scores(total_row["metrics"], _independent_scores([1, 1, 0], [1, .4, .2], [2, 1, 3]))
    assert new_row["metrics"]["brier"] == pytest.approx(.12)
    assert total_row["metrics"]["brier"] == pytest.approx(.08)
    assert json.loads(json.dumps(total, allow_nan=False)) == total


def test_probability_and_classification_scores_match_independent_weighted_definitions():
    result = _snapshot([.2, .7, .9], burned_probability=[.2, .7, .9])
    observed = _reference([[0, 0, 0], [0, 1, 0]])
    report = _evaluate(result, observed, weight=np.asarray([[1, 2, 3]], dtype=float))
    row = _row(report, 1)
    _assert_scores(row["metrics"], _independent_scores([0, 1, 0], [.2, .7, .9], [1, 2, 3]))
    expected = dict(tp=2, fp=3, tn=1, fn=0, precision=.4, recall=1,
                    f1=4 / 7, mcc=2 / math.sqrt(40), accuracy=.5,
                    specificity=.25, balanced_accuracy=.625,
                    intersection_over_union=.4, threshold=.5)
    for name, value in expected.items():
        assert row["classification"][name] == pytest.approx(value)
    assert row["metrics"]["mean_probability"] == pytest.approx(4.3 / 6)
    assert row["calibration"]["weighted_expected_calibration_error"] == pytest.approx(2.3 / 6)
    assert sum(bin_["sample_count"] for bin_ in row["calibration"]["bins"]) == 3


def test_empirical_zero_probabilities_preserve_infinity_and_average_square_roots_per_cell():
    result = _snapshot([0, 0], burned_probability=[0, 0])
    report = _evaluate(result, _reference([[0, 0], [0, 1]]))
    metrics = _row(report, 1)["metrics"]
    _assert_scores(metrics, _independent_scores([0, 1], [0, 0], [1, 1]))
    for name in ("brier", "bernoulli_total_variation_distance_mean",
                 "bernoulli_hellinger_distance_mean", "bernoulli_wasserstein_1_distance_mean",
                 "bernoulli_wasserstein_2_distance_mean"):
        assert metrics[name] == .5
    assert metrics["bernoulli_jensen_shannon_divergence_mean"] == pytest.approx(math.log(2) / 2)
    assert metrics["bernoulli_jensen_shannon_distance_mean"] == pytest.approx(math.sqrt(math.log(2)) / 2)
    assert math.isfinite(metrics["clipped_log_loss"])
    assert math.isfinite(metrics["floored_bernoulli_kl_divergence_mean"])
    assert metrics["unsupported_positive_sample_count"] == 1
    assert all(not name.startswith("zero_contact_") for name in metrics)
    assert report["protocol"]["prediction_metadata"] == {"method": "recursive", "n_samples": 16}
    json.dumps(report, allow_nan=False)


def test_tiny_positive_weight_on_an_unsupported_outcome_still_gives_exact_infinity():
    result = _snapshot([0, 0])
    report = _evaluate(result, _reference([[0, 0], [0, 1]]), weight=np.asarray([[1e308, 1e-300]]))
    metrics = _row(report, 1)["metrics"]
    for name in ("exact_negative_log_likelihood_mean", "bernoulli_kl_divergence_mean",
                 "bernoulli_bhattacharyya_distance_mean"):
        assert metrics[name] == "infinity"


def test_cumulative_scoring_uses_exact_interval_states_without_hourly_labels_or_contact_filter():
    result = _snapshot([[0, .5, .75], [0, .25, .1]], hours=(3, 1),
                       burned_probability=[[1, .5, .75], [1, .25, .1]])
    reference = _reference([[1, 1, 1], [1, 0, 0], [1, 1, 0]],
                           times=(20_800, 10_000, 13_600))

    class CumulativeStates(dict):
        def __getitem__(self, name):
            assert name not in {"newly_burned_area", "newly_burned_area_valid"}
            return super().__getitem__(name)

        def get(self, name, default=None):
            assert name not in {"newly_burned_area", "newly_burned_area_valid"}
            return super().get(name, default)

        def __contains__(self, name):
            assert name not in {"newly_burned_area", "newly_burned_area_valid"}
            return super().__contains__(name)

    guarded = CumulativeStates(**reference, newly_burned_area=object())
    report = _evaluate(result, guarded)
    assert [row["hours"] for row in report["per_horizon"]] == [3, 1]
    assert _row(report, 3)["metrics"]["positive_sample_count"] == 2
    assert _row(report, 1)["metrics"]["positive_sample_count"] == 1
    assert _row(report, 3)["metrics"]["sample_count"] == 2
    _assert_scores(_row(report, 3)["metrics"], _independent_scores([1, 1], [.5, .75], [1, 1]))
    _assert_scores(_row(report, 1)["metrics"], _independent_scores([1, 0], [.25, .1], [1, 1]))


def test_shared_coverage_intersects_only_requested_horizons_and_preserves_own_horizon_counts():
    result = _snapshot([[.1, .2, .3, .4, .5], [.2, .3, .4, .5, .6]], hours=(3, 1),
                       valid=[[1, 0, 1, 1, 1], [1, 1, 0, 1, 1]])
    observed = _reference([[0] * 5, [1, 0, 1, 0, 1], [1, 1, 1, 0, 1]],
                          times=(10_000, 13_600, 20_800),
                          valid=[[1] * 5, [1, 1, 1, 0, 1], [0, 1, 1, 1, 1]])
    weights = np.asarray([[1, 2, 3, 4, 5]], dtype=float)
    own = _evaluate(result, observed, weight=weights)
    shared = _evaluate(result, observed, weight=weights, coverage="shared")
    for hour, eligible_weight, covered_weight in ((3, 14, 12), (1, 11, 8)):
        coverage = _row(shared, hour)["coverage"]
        assert coverage["reference_eligible_cells"] == 4
        assert coverage["reference_eligible_weight"] == eligible_weight
        assert coverage["prediction_covered_cells"] == 3
        assert coverage["prediction_covered_weight"] == covered_weight
        assert coverage["evaluated_cells"] == 1
        assert coverage["evaluated_weight"] == 5
        assert coverage["excluded_by_shared_coverage_cells"] == 2
        assert coverage["coverage_fraction"] == pytest.approx(5 / eligible_weight)
        assert coverage["prediction_coverage_fraction"] == pytest.approx(covered_weight / eligible_weight)
        assert _row(own, hour)["coverage"]["evaluated_cells"] == 3
    selected = _evaluate(result, observed, hours=1, coverage="shared", weight=weights)
    assert selected["protocol"]["hours"] == [1.0]
    assert len(selected["per_horizon"]) == 1
    assert _row(selected, 1)["coverage"]["evaluated_cells"] == 3
    assert _row(selected, 1)["metrics"] == _row(own, 1)["metrics"]


def test_prediction_reference_and_user_masks_intersect_without_mutating_inputs():
    result = _snapshot([.1, .2, .3, .4, .5], valid=[[1, 1, 0, 1, 1]],
                       pixel_valid=np.asarray([[1, 1, 1, 1, 0]], dtype=bool))
    observed = _reference([[0] * 5, [1, 0, 1, 0, 1]],
                          valid=[[1] * 5, [1, 0, 1, 1, 1]])
    mask = np.asarray([[1, 1, 1, 0, 1]], dtype=bool)
    weights = np.asarray([[2, 3, 4, 5, 6]], dtype=float)
    before = deepcopy(observed)
    arrays = result.numpy()
    report = _evaluate(result, observed, cohort_mask=mask, weight=weights)
    row = _row(report, 1)
    assert row["coverage"]["evaluated_cells"] == 1
    assert row["coverage"]["evaluated_weight"] == 2
    _assert_scores(row["metrics"], _independent_scores([1], [.1], [2]))
    np.testing.assert_array_equal(mask, [[1, 1, 1, 0, 1]])
    np.testing.assert_array_equal(weights, [[2, 3, 4, 5, 6]])
    for name, value in observed.items():
        np.testing.assert_array_equal(value, before[name])
    for name, value in result.numpy().items():
        np.testing.assert_array_equal(value, arrays[name])


def test_total_endpoint_target_remains_identified_when_cutoff_state_is_missing():
    result = _snapshot([.4, .5], burned_probability=[.4, .5])
    observed = _reference([[1, 0]], times=(13_600,))
    new = _row(_evaluate(result, observed), 1)
    total = _row(_evaluate(result, observed, quantity="burned"), 1)
    assert new["coverage"]["reference_eligible_cells"] == 0
    assert new["metrics"]["sample_count"] == 0
    assert total["coverage"]["evaluated_cells"] == 2
    _assert_scores(total["metrics"], _independent_scores([1, 0], [.4, .5], [1, 1]))


def test_missing_exact_endpoint_is_not_replaced_by_a_nearby_reference_state():
    result = _snapshot([.4, .5], burned_probability=[.4, .5])
    observed = _reference([[0, 0], [1, 1]], times=(10_000, 13_601))
    for quantity in ("new_burn", "burned"):
        row = _row(_evaluate(result, observed, quantity=quantity), 1)
        assert row["coverage"]["evaluated_cells"] == 0
        assert row["metrics"]["brier"] is None
        assert row["metrics"]["bernoulli_kl_divergence_mean"] is None
        assert row["calibration"]["bins"] == []
        assert row["calibration"]["weighted_expected_calibration_error"] is None
        assert row["coverage"]["coverage_fraction"] is None


@pytest.mark.parametrize("quantity", ["new_burn", "burned"])
def test_known_cumulative_decrease_is_rejected_but_unavailable_stored_zero_is_not(quantity):
    result = _snapshot([0, .5], burned_probability=[1, .5])
    observed = _reference([[1, 0], [0, 1]])
    with pytest.raises(ValueError, match="nondecreasing|burned.*unburned"):
        _evaluate(result, observed, quantity=quantity)
    observed["burned_area_valid"][1, 0, 0, 0] = False
    row = _row(_evaluate(result, observed, quantity=quantity), 1)
    assert row["coverage"]["evaluated_cells"] == 1


def test_known_nonbinary_targets_are_rejected_but_unknown_stored_values_are_excluded():
    result = _snapshot([.4, .5])
    observed = _reference([[0, 0], [.5, 1]])
    with pytest.raises(ValueError, match="exactly 0 or 1|binary"):
        _evaluate(result, observed)
    observed["burned_area_valid"][1, 0, 0, 0] = False
    assert _row(_evaluate(result, observed), 1)["metrics"]["sample_count"] == 1


def test_zero_weights_remove_unsupported_rows_before_exact_distance_computation():
    result = _snapshot([0, .25])
    report = _evaluate(result, _reference([[0, 0], [1, 0]]), weight=np.asarray([[0, 2.0]]))
    row = _row(report, 1)
    assert row["coverage"]["zero_weight_excluded_cells"] == 1
    assert row["coverage"]["reference_eligible_cells"] == 1
    assert row["coverage"]["evaluated_weight"] == 2
    _assert_scores(row["metrics"], _independent_scores([0], [.25], [2]))


def test_scalar_spatial_and_complete_weights_have_the_same_normalized_scores():
    result = _snapshot([.2, .7, .9])
    observed = _reference([[0, 0, 0], [0, 1, 1]])
    reports = [_evaluate(result, observed, weight=weight) for weight in
               (None, 3.0, np.full((1, 3), 3.0), np.full((1, 1, 3), 3.0))]
    expected = _independent_scores([0, 1, 1], [.2, .7, .9], [1, 1, 1])
    for report in reports:
        _assert_scores(_row(report, 1)["metrics"], expected)
    assert _row(reports[0], 1)["metrics"]["represented_population_weight"] == 3
    assert all(_row(report, 1)["metrics"]["represented_population_weight"] == 9
               for report in reports[1:])


@pytest.mark.parametrize("weight", [
    True, np.bool_(True), "1", [1, 2, 3], np.ones((1, 1)), np.ones((2, 1, 1, 3)),
    np.full((1, 3), True), -1, np.nan, np.inf,
    np.asarray([[1, -1, 1]]), np.asarray([[1, np.nan, 1]]),
    np.asarray([[1, np.inf, 1]]), np.ones((1, 3), dtype=complex),
    np.ma.array([[1, 1, 1]], mask=[[0, 1, 0]]),
])
def test_weights_require_an_explicit_allowed_shape_and_finite_nonnegative_real_values(weight):
    result = _snapshot([.2, .7, .9])
    with pytest.raises((TypeError, ValueError), match="weight"):
        _evaluate(result, _reference([[0, 0, 0], [0, 1, 1]]), weight=weight)


def test_all_zero_weights_produce_an_explicit_empty_cohort():
    result = _snapshot([0, 0])
    report = _evaluate(result, _reference([[0, 0], [1, 1]]), weight=0)
    row = _row(report, 1)
    assert row["coverage"]["zero_weight_excluded_cells"] == 2
    assert row["coverage"]["reference_eligible_cells"] == 0
    assert row["metrics"]["sample_count"] == 0
    assert row["metrics"]["exact_negative_log_likelihood_mean"] is None
    json.dumps(report, allow_nan=False)


@pytest.mark.parametrize("mask", [True, [1, 0, 1], np.ones((1, 3)), np.ones((1, 1), dtype=bool),
                                  np.ones((2, 1, 1, 3), dtype=bool),
                                  np.ma.array([[True, True, True]], mask=[[0, 1, 0]])])
def test_cohort_masks_require_boolean_spatial_or_complete_prediction_shape(mask):
    result = _snapshot([.2, .7, .9])
    with pytest.raises((TypeError, ValueError), match="cohort_mask"):
        _evaluate(result, _reference([[0, 0, 0], [0, 1, 1]]), cohort_mask=mask)


def test_complete_cohort_mask_matches_spatial_cohort_mask():
    result = _snapshot([.2, .7, .9])
    observed = _reference([[0, 0, 0], [0, 1, 1]])
    spatial = _evaluate(result, observed, cohort_mask=np.asarray([[1, 0, 1]], dtype=bool))
    complete = _evaluate(result, observed, cohort_mask=np.asarray([[[1, 0, 1]]], dtype=bool))
    assert spatial["per_horizon"] == complete["per_horizon"]


@pytest.mark.parametrize("threshold", [True, np.bool_(True), "0.5", np.nan, np.inf, None, [.5]])
def test_threshold_requires_a_finite_real_scalar_without_fitting(threshold):
    result = _snapshot([.2, .7])
    with pytest.raises((TypeError, ValueError), match="threshold"):
        _evaluate(result, _reference([[0, 0], [0, 1]]), threshold=threshold)


def test_fixed_supplied_threshold_can_be_outside_unit_interval_and_does_not_change_probability_metrics():
    result = _snapshot([.2, .7])
    observed = _reference([[0, 0], [0, 1]])
    ordinary = _row(_evaluate(result, observed), 1)
    report = _evaluate(result, observed, threshold=1.1)
    row = _row(report, 1)
    assert report["protocol"]["threshold"] == 1.1
    assert row["classification"]["threshold"] == 1.1
    assert row["classification"]["tp"] == row["classification"]["fp"] == 0
    assert row["classification"]["tn"] == row["classification"]["fn"] == 1
    assert row["metrics"] == ordinary["metrics"]


@pytest.mark.parametrize("options", [
    {"quantity": "fire"}, {"quantity": True}, {"coverage": "complete"}, {"coverage": True},
    {"hours": 2}, {"hours": None}, {"hours": [1, 1]}, {"hours": []},
])
def test_invalid_evaluation_protocols_are_rejected(options):
    result = _snapshot([.2, .7])
    with pytest.raises((TypeError, ValueError)):
        _evaluate(result, _reference([[0, 0], [0, 1]]), **options)


def test_total_evaluation_requires_the_total_probability_output():
    result = _snapshot([.2, .7])
    with pytest.raises(ValueError, match="burned_probability"):
        _evaluate(result, _reference([[0, 0], [0, 1]]), quantity="burned")


@pytest.mark.parametrize("bad", [np.nan, np.inf, -.1, 1.1])
def test_declared_valid_probability_must_be_finite_and_in_range_even_when_reference_is_missing(bad):
    result = _snapshot([bad, .7])
    with pytest.raises((ValueError, RuntimeError), match="probability|finite|\\[0, 1\\]"):
        _evaluate(result, _reference([[0, 0]], times=(10_000,)))


def test_snapshot_and_singleton_sequence_use_the_same_exact_timeline_and_scores():
    snapshot = _snapshot([.2, .7], burned_probability=[.2, .7])
    sequence = _result(np.asarray([[[[.2, .7]]]]).reshape(1, 1, 1, 1, 2),
                       burned_probability=np.asarray([[[[.2, .7]]]]).reshape(1, 1, 1, 1, 2),
                       time_utc=[10_000])
    observed = _reference([[0, 0], [0, 1]])
    for quantity in ("new_burn", "burned"):
        assert _evaluate(snapshot, observed, quantity=quantity)["per_horizon"] == \
            _evaluate(sequence, observed, quantity=quantity)["per_horizon"]


def test_batched_events_keep_exact_times_and_pixel_time_padding_separate():
    new = np.asarray([[[1, 0], [0, 1]], [[0, 1], [1, 0]]], dtype=float).reshape(1, 2, 2, 1, 1, 2)
    total = np.asarray([[[1, 0], [1, 1]], [[0, 1], [1, 1]]], dtype=float).reshape(new.shape)
    result = _result(new, burned_probability=total,
                     time_utc=[[10_000, 13_600], [50_000, 53_600]],
                     time_valid=np.asarray([[1, 1], [1, 0]], dtype=bool),
                     pixel_valid=np.asarray([[[1, 0]], [[1, 1]]], dtype=bool),
                     event_id=["event-A", "event-B"])
    observed = dict(
        burned_area=np.asarray([[[1, 1], [0, 0], [1, 0]],
                                [[0, 1], [1, 1], [0, 0]]], dtype=float).reshape(2, 3, 1, 1, 2),
        burned_area_valid=np.ones((2, 3, 1, 1, 2), dtype=bool),
        time_utc=np.asarray([[17_200, 10_000, 13_600], [53_600, 57_200, 50_000]]),
        time_valid=np.ones((2, 3), dtype=bool), event_id=["event-A", "event-B"],
    )
    row = _row(_evaluate(result, observed), 1)
    assert row["coverage"]["evaluated_cells"] == 3
    assert row["metrics"]["positive_sample_count"] == 2
    assert row["metrics"]["brier"] == 0
    assert row["metrics"]["exact_negative_log_likelihood_mean"] == 0
    total_row = _row(_evaluate(result, observed, quantity="burned"), 1)
    assert total_row["coverage"]["evaluated_cells"] == 4
    assert total_row["metrics"]["positive_sample_count"] == 3
    assert total_row["metrics"]["brier"] == 0


def test_fractional_fixed_horizon_uses_its_exact_integer_second_endpoint():
    result = _snapshot([.2, .7], hours=(.5,), burned_probability=[.2, .7], method="fixed")
    observed = _reference([[0, 0], [0, 1]], times=(10_000, 11_800))
    row = _row(_evaluate(result, observed), .5)
    assert row["metrics"]["sample_count"] == 2
    _assert_scores(row["metrics"], _independent_scores([0, 1], [.2, .7], [1, 1]))


def test_reference_event_identity_and_boolean_validity_are_required():
    result = _snapshot([.2, .7])
    observed = _reference([[0, 0], [0, 1]], event_id="other")
    with pytest.raises(ValueError, match="event_id"):
        _evaluate(result, observed)
    observed["event_id"] = "fixture"
    observed["burned_area_valid"] = observed["burned_area_valid"].astype(int)
    with pytest.raises(ValueError, match="boolean"):
        _evaluate(result, observed)
    with pytest.raises(TypeError):
        _evaluate(result, np.asarray([[0, 1]]))


def test_evaluation_requires_an_explicit_duration_in_both_public_entry_points():
    from wildfire import evaluate_cumulative

    result = _snapshot([.2, .7])
    observed = _reference([[0, 0], [0, 1]])
    with pytest.raises(TypeError, match="hours"):
        result.evaluate(observed)
    with pytest.raises(TypeError, match="hours"):
        evaluate_cumulative(result, observed)
    assert result.evaluate(observed, hours=1) == evaluate_cumulative(result, observed, hours=1)


def test_actual_seeded_recursive_predictions_evaluate_multi_step_contact_and_preserve_global_rng():
    from tests.test_rollout import _inputs, _model, CHANNELS, SECOND_CELL, THIRD_CELL

    model = _model()
    burned, environment = _inputs()
    sample = dict(burned_area=burned, features=environment, channel_names=CHANNELS,
                  time_utc=np.asarray(10_000, dtype=np.int64))
    before = torch.get_rng_state().clone()
    result = model.predict_cumulative(sample, hours=[1, 3], n_samples=256,
                                      seed=23, trajectory_batch_size=32, boundary="zero")
    later = model.predict_cumulative(sample, hours=[1, 3], n_samples=256,
                                     seed=23, trajectory_batch_size=32, boundary="zero")
    torch.testing.assert_close(result.probability, later.probability, rtol=0, atol=0, equal_nan=True)
    next_state, end_state = burned.numpy().copy(), burned.numpy().copy()
    next_state[SECOND_CELL] = 1
    end_state[SECOND_CELL] = end_state[THIRD_CELL] = 1
    observed = dict(
        burned_area=np.stack((burned.numpy(), next_state, end_state)),
        burned_area_valid=np.ones((3, *burned.shape), dtype=bool),
        time_utc=np.asarray([10_000, 13_600, 20_800]),
    )
    selected = np.zeros(burned.shape[-2:], dtype=bool)
    selected[SECOND_CELL[-2:]] = selected[THIRD_CELL[-2:]] = True
    report = result.evaluate(observed, hours=[3, 1], cohort_mask=selected)
    assert report == later.evaluate(observed, hours=[3, 1], cohort_mask=selected)
    torch.testing.assert_close(torch.get_rng_state(), before, rtol=0, atol=0)
    assert result.at(hours=1).probability[THIRD_CELL].item() == 0
    assert result.at(hours=3).probability[THIRD_CELL].item() > 0
    assert report["protocol"]["cutoff_neighbor_contact_required"] is False
    for hour, labels in ((1, [1, 0]), (3, [1, 1])):
        row = _row(report, hour)
        assert row["coverage"]["evaluated_cells"] == 2
        probabilities = [result.at(hours=hour).probability[cell].item()
                         for cell in (SECOND_CELL, THIRD_CELL)]
        _assert_scores(row["metrics"], _independent_scores(labels, probabilities, [1, 1]))


def test_finite_individual_weights_with_overflowing_selected_total_are_rejected():
    result = _snapshot([.2, .7])
    with pytest.raises(ValueError, match="weight total.*finite|finite.*weight"):
        result.evaluate(_reference([[0, 0], [0, 1]]), hours=1,
                        weight=np.asarray([[1e308, 1e308]]))


def test_intersection_over_union_preserves_a_correct_positive_with_a_tiny_relative_weight():
    result = _snapshot([0, .8])
    row = _row(result.evaluate(_reference([[0, 0], [0, 1]]), hours=1,
                              weight=np.asarray([[1e308, 1e-300]])), 1)
    assert row["classification"]["tp"] == 1e-300
    assert row["classification"]["fp"] == row["classification"]["fn"] == 0
    assert row["classification"]["intersection_over_union"] == 1


def test_subnormal_common_weight_scale_preserves_brier_mean_probability_and_calibration():
    result = _snapshot([.2, .7])
    observed = _reference([[0, 0], [0, 1]])
    unit = _row(result.evaluate(observed, hours=1), 1)
    tiny = np.nextafter(0.0, 1.0)
    subnormal = _row(result.evaluate(observed, hours=1, weight=tiny), 1)
    for name, expected in (("brier", .065), ("mean_probability", .45),
                           ("positive_class_brier", .09), ("negative_class_brier", .04)):
        assert subnormal["metrics"][name] == pytest.approx(expected, abs=2e-15)
        assert subnormal["metrics"][name] == unit["metrics"][name]
    assert subnormal["calibration"]["weighted_expected_calibration_error"] == pytest.approx(.25)
    assert subnormal["calibration"]["weighted_expected_calibration_error"] == \
        unit["calibration"]["weighted_expected_calibration_error"]


def test_perfect_rare_negative_class_keeps_roc_auc_defined_and_equal_to_one():
    result = _snapshot([0, 1])
    row = _row(result.evaluate(_reference([[0, 0], [0, 1]]), hours=1,
                              weight=np.asarray([[1e-300, 1e308]])), 1)
    assert row["metrics"]["roc_auc"] == 1
    assert row["metrics"]["brier"] == 0
    assert row["metrics"]["exact_negative_log_likelihood_mean"] == 0


def test_empty_and_nonempty_evaluation_cohorts_share_the_same_metric_schema():
    result = _snapshot([.2, .7])
    observed = _reference([[0, 0], [0, 1]])
    nonempty = _row(result.evaluate(observed, hours=1), 1)
    empty = _row(result.evaluate(observed, hours=1, weight=0), 1)
    assert set(empty["metrics"]) == set(nonempty["metrics"])
    assert set(empty["classification"]) == set(nonempty["classification"])
    assert set(empty["coverage"]) == set(nonempty["coverage"])
    assert empty["metrics"]["classification_at_0_5"] is None


def test_mcc_preserves_a_representable_rare_positive_correlation_against_decimal_oracle():
    from decimal import Decimal, localcontext

    result = _snapshot([.7, .9, .1])
    row = _row(result.evaluate(_reference([[0, 0, 0], [1, 0, 0]]), hours=1,
                              weight=np.asarray([[1e-300, 1e307, 1e307]])), 1)
    # At threshold .5 these rows give TP=1e-300, FP=TN=1e307, FN=0.
    # Evaluate the unscaled definition independently with enough exponent
    # range to retain all products and a representable final correlation.
    with localcontext() as context:
        context.prec = 80
        tp, fp, tn, fn = map(Decimal, ("1e-300", "1e307", "1e307", "0"))
        numerator = tp * tn - fp * fn
        denominator = ((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)).sqrt()
        expected = float(numerator / denominator)
    assert expected == pytest.approx(2.2360679774997897e-304, rel=2e-15, abs=0)
    for actual in (row["classification"]["mcc"], row["metrics"]["mcc_at_0_5"]):
        assert actual > 0
        assert actual == pytest.approx(expected, rel=2e-14, abs=0)
