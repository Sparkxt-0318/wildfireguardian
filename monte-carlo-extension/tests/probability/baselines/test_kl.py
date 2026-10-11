"""Independent checks of the directed Bernoulli KL and its scoring wrapper."""

import math

import numpy as np
import pytest

from wildfire.metrics import probability_metrics_with_kl
from wildfire.metrics import weighted_bernoulli_kl
from wildfire.metrics import LOG_LOSS_EPSILON
from wildfire.metrics import probability_metrics


def test_direction_matches_independent_bernoulli_formula_and_is_not_symmetric():
    expected = 0.25 * math.log(0.25 / 0.5) + 0.75 * math.log(0.75 / 0.5)
    actual = weighted_bernoulli_kl([0.25], [0.5], [1])
    reverse = weighted_bernoulli_kl([0.5], [0.25], [1])
    assert actual == pytest.approx(expected, abs=1e-15)
    assert actual == pytest.approx(0.13081203594113697)
    assert reverse != pytest.approx(actual)


@pytest.mark.parametrize("reference,prediction", [([1], [0]), ([0], [1]),
                                                 ([0.25], [0]), ([0.25], [1])])
def test_positive_reference_mass_with_zero_prediction_support_is_infinite(reference, prediction):
    assert weighted_bernoulli_kl(reference, prediction, [1]) == "infinity"


def test_even_tiny_positive_weight_preserves_impossible_outcome_infinity():
    assert weighted_bernoulli_kl([0, 1], [0, 0], [1, 1e-300]) == "infinity"


def test_identical_bernoulli_distributions_and_correct_certain_predictions_give_zero():
    values = np.array([0, 0.1, 0.25, 0.5, 0.9, 1])
    assert weighted_bernoulli_kl(values, values, np.ones(len(values))) == 0
    assert weighted_bernoulli_kl([0, 1], [0, 1], [1, 3]) == 0


def test_weighted_vector_matches_independent_hand_calculation():
    reference = [0.25, 0.8, 0, 1]
    prediction = [0.5, 0.2, 0.3, 0.7]
    weights = [2, 1, 3, 4]
    terms = [
        0.25 * math.log(0.25 / 0.5) + 0.75 * math.log(0.75 / 0.5),
        0.8 * math.log(0.8 / 0.2) + 0.2 * math.log(0.2 / 0.8),
        -math.log(0.7),
        -math.log(0.7),
    ]
    expected = sum(w * term for w, term in zip(weights, terms)) / sum(weights)
    assert weighted_bernoulli_kl(reference, prediction, weights) == pytest.approx(expected, abs=1e-15)


@pytest.mark.parametrize("prediction", [[0, 0.2, 0.75, 1], [1, 0.2, 0.75, 0]])
def test_hard_label_kl_equals_existing_exact_and_floored_nll_and_preserves_original_fields(prediction):
    target = np.array([0, 1, 0, 1])
    probability = np.array(prediction, dtype=float)
    weights = np.array([1, 2, 3, 5], dtype=float)
    counts = np.array([0, 1, 3, 4])
    original = probability_metrics(target, probability, weights, counts)
    scored = probability_metrics_with_kl(target, probability, weights, counts)
    for key, expected in original.items():
        assert scored[key] == expected
    exact = original["exact_negative_log_likelihood_mean"]
    if exact == "infinity":
        assert scored["bernoulli_kl_divergence_mean"] == "infinity"
    else:
        assert scored["bernoulli_kl_divergence_mean"] == pytest.approx(exact, abs=1e-15)
    assert scored["floored_bernoulli_kl_divergence_mean"] == pytest.approx(original["clipped_log_loss"], abs=1e-14)


def test_floor_changes_prediction_distribution_only():
    reference = 0.25
    floor = 0.1
    expected = reference * math.log(reference / floor) + (1 - reference) * math.log((1 - reference) / (1 - floor))
    assert weighted_bernoulli_kl([reference], [0], [1], probability_floor=floor) == pytest.approx(expected)
    assert weighted_bernoulli_kl([1], [0], [1], probability_floor=LOG_LOSS_EPSILON) == pytest.approx(-math.log(LOG_LOSS_EPSILON))


def test_small_probability_for_correct_negative_uses_stable_log1p():
    probability = 1e-20
    assert weighted_bernoulli_kl([0], [probability], [1]) == pytest.approx(probability, rel=1e-15, abs=0)


@pytest.mark.parametrize("floor", [True, np.bool_(False), 0, -0.1, 0.5, 1, np.nan, np.inf, "0.1"])
def test_invalid_floor_is_rejected(floor):
    with pytest.raises(ValueError, match="probability_floor"):
        weighted_bernoulli_kl([0.25], [0.5], [1], probability_floor=floor)


@pytest.mark.parametrize("reference,prediction,weights", [
    ([], [], []), ([[0]], [0], [1]), ([0], [[0]], [1]), ([0], [0], [[1]]),
    ([0, 1], [0], [1, 1]), ([0], [0], [1, 1]),
    ([-0.1], [0], [1]), ([1.1], [1], [1]), ([0], [-0.1], [1]), ([1], [1.1], [1]),
    ([np.nan], [0], [1]), ([0], [np.inf], [1]), ([0], [0], [np.nan]),
    ([0], [0], [0]), ([0], [0], [-1]),
    ([0, 1], [0, 1], [1e308, 1e308]), (["0"], [0], [1]),
])
def test_invalid_shapes_probabilities_and_weights_are_rejected(reference, prediction, weights):
    with pytest.raises(ValueError):
        weighted_bernoulli_kl(reference, prediction, weights)


def test_finite_weight_total_does_not_allow_weighted_term_overflow_to_corrupt_mean():
    assert weighted_bernoulli_kl([1], [1e-300], [1e308]) == pytest.approx(-math.log(1e-300))


def test_empty_metric_scope_retains_original_empty_contract_and_appends_none():
    empty = np.array([], dtype=float)
    scored = probability_metrics_with_kl(empty, empty, empty, empty)
    original = probability_metrics(empty, empty, empty, empty)
    assert {key: scored[key] for key in original} == original
    assert scored["bernoulli_kl_divergence_mean"] is None
    assert scored["floored_bernoulli_kl_divergence_mean"] is None


def test_metric_wrapper_rejects_soft_outcomes_and_mismatched_neighbor_counts():
    with pytest.raises(ValueError, match="binary observed labels"):
        probability_metrics_with_kl([0.25], [0.5], [1], [2])
    with pytest.raises(ValueError, match="equal lengths"):
        probability_metrics_with_kl([0], [0.5], [1], [1, 2])
