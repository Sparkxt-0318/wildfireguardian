"""Independent definitions and boundary checks for Bernoulli distances."""

import math

import numpy as np
import pytest

from wildfire.metrics import STATISTICAL_DISTANCE_FIELDS
from wildfire.metrics import probability_metrics_with_statistical_distances
from wildfire.metrics import weighted_bernoulli_distances
from wildfire.metrics import probability_metrics


def _field(short):
    return f"bernoulli_{short}_mean"


def _independent_terms(r, p):
    reference = (1 - r, r)
    prediction = (1 - p, p)
    mixture = tuple((a + b) / 2 for a, b in zip(reference, prediction))
    kl_pm = sum(a * math.log(a / m) for a, m in zip(reference, mixture) if a)
    kl_qm = sum(b * math.log(b / m) for b, m in zip(prediction, mixture) if b)
    js = (kl_pm + kl_qm) / 2
    coefficient = sum(math.sqrt(a * b) for a, b in zip(reference, prediction))
    return {
        _field("total_variation_distance"): abs(r - p),
        _field("hellinger_distance"): math.sqrt(sum((math.sqrt(a) - math.sqrt(b))**2
                                                    for a, b in zip(reference, prediction)) / 2),
        _field("jensen_shannon_divergence"): js,
        _field("jensen_shannon_distance"): math.sqrt(max(js, 0)),
        _field("bhattacharyya_distance"): -math.log(coefficient) if coefficient else "infinity",
        _field("wasserstein_1_distance"): abs(r - p),
        _field("wasserstein_2_distance"): math.sqrt(abs(r - p)),
    }


def test_general_soft_pair_matches_independent_definitions_and_is_symmetric():
    actual = weighted_bernoulli_distances([0.25], [0.7], [1])
    expected = _independent_terms(0.25, 0.7)
    reverse = weighted_bernoulli_distances([0.7], [0.25], [1])
    assert set(actual) == set(STATISTICAL_DISTANCE_FIELDS)
    for name in actual:
        assert actual[name] == pytest.approx(expected[name], abs=2e-15)
        assert reverse[name] == pytest.approx(actual[name], abs=2e-15)


def test_identical_soft_and_endpoint_distributions_have_zero_distance():
    values = [0, 0.01, 0.25, 0.5, 0.7, 1]
    actual = weighted_bernoulli_distances(values, values, np.ones(len(values)))
    assert all(distance == 0 for distance in actual.values())


@pytest.mark.parametrize("reference,prediction", [(0, 1), (1, 0)])
def test_disjoint_endpoints_have_exact_bounds_and_infinite_bhattacharyya(reference, prediction):
    actual = weighted_bernoulli_distances([reference], [prediction], [1])
    for short in ("total_variation_distance", "hellinger_distance", "wasserstein_1_distance", "wasserstein_2_distance"):
        assert actual[_field(short)] == 1
    assert actual[_field("jensen_shannon_divergence")] == math.log(2)
    assert actual[_field("jensen_shannon_distance")] == math.sqrt(math.log(2))
    assert actual[_field("bhattacharyya_distance")] == "infinity"


def test_weighted_means_match_independent_per_row_calculation():
    r, p, w = [0, 0.25, 0.9, 1], [0.2, 0.7, 0.6, 0.8], [1, 2, 3, 4]
    rows = [_independent_terms(a, b) for a, b in zip(r, p)]
    actual = weighted_bernoulli_distances(r, p, w)
    for name in actual:
        expected = sum(weight * row[name] for weight, row in zip(w, rows)) / sum(w)
        assert actual[name] == pytest.approx(expected, abs=2e-15)


def test_square_roots_are_taken_before_weighted_averaging():
    actual = weighted_bernoulli_distances([0, 1], [0, 0], [1, 1])
    assert actual[_field("wasserstein_1_distance")] == 0.5
    assert actual[_field("wasserstein_2_distance")] == 0.5
    assert actual[_field("wasserstein_2_distance")] != math.sqrt(actual[_field("wasserstein_1_distance")])
    assert actual[_field("jensen_shannon_distance")] == pytest.approx(math.sqrt(math.log(2)) / 2)
    assert actual[_field("jensen_shannon_distance")] != pytest.approx(math.sqrt(actual[_field("jensen_shannon_divergence")]))
    assert actual[_field("hellinger_distance")] == 0.5


def test_hard_outcomes_give_total_variation_absolute_error_and_half_nll_bhattacharyya():
    labels, prediction, weights = [0, 1, 1], [0.2, 0.7, 0.9], [1, 2, 3]
    actual = weighted_bernoulli_distances(labels, prediction, weights)
    expected_error = (0.2 + 2 * 0.3 + 3 * 0.1) / 6
    expected_nll = (-math.log(0.8) - 2 * math.log(0.7) - 3 * math.log(0.9)) / 6
    assert actual[_field("total_variation_distance")] == pytest.approx(expected_error)
    assert actual[_field("wasserstein_1_distance")] == actual[_field("total_variation_distance")]
    assert actual[_field("bhattacharyya_distance")] == pytest.approx(expected_nll / 2)


def test_tiny_positive_weight_on_disjoint_support_preserves_infinite_mean():
    actual = weighted_bernoulli_distances([0, 1], [0, 0], [1e308, 1e-300])
    assert actual[_field("bhattacharyya_distance")] == "infinity"


def test_nearly_disjoint_positive_support_remains_finite_without_flooring():
    actual = weighted_bernoulli_distances([1], [1e-300], [1])
    assert actual[_field("bhattacharyya_distance")] == pytest.approx(-0.5 * math.log(1e-300))
    assert math.isfinite(actual[_field("jensen_shannon_divergence")])


def test_tiny_js_support_and_nearly_identical_bhattacharyya_are_numerically_safe():
    tiny = np.nextafter(0, 1)
    actual = weighted_bernoulli_distances([0], [tiny], [1])
    assert all(value != "infinity" and math.isfinite(value) for value in actual.values())
    close = weighted_bernoulli_distances([0.5], [0.5 + 1e-10], [1])
    assert close[_field("bhattacharyya_distance")] > 0
    assert close[_field("bhattacharyya_distance")] == pytest.approx(0.5e-20, rel=1e-5, abs=0)
    assert close[_field("jensen_shannon_divergence")] > 0
    assert close[_field("jensen_shannon_divergence")] == pytest.approx(0.5e-20, rel=1e-5, abs=0)


def test_common_weight_scaling_preserves_every_finite_mean():
    reference, prediction, weights = [0.2, 0.7], [0.5, 0.4], np.array([1, 2], dtype=float)
    small = weighted_bernoulli_distances(reference, prediction, weights)
    large = weighted_bernoulli_distances(reference, prediction, weights * 5e307)
    for name in small:
        assert large[name] == pytest.approx(small[name], abs=1e-15)


@pytest.mark.parametrize("reference,prediction,weights", [
    ([], [], []), ([[0]], [0], [1]), ([0], [[0]], [1]), ([0], [0], [[1]]),
    ([0, 1], [0], [1, 1]), ([0], [0], [1, 1]),
    ([-0.1], [0], [1]), ([1.1], [1], [1]), ([0], [-0.1], [1]), ([1], [1.1], [1]),
    ([np.nan], [0], [1]), ([0], [np.inf], [1]), ([0], [0], [np.nan]),
    ([0], [0], [0]), ([0], [0], [-1]),
    ([0, 1], [0, 1], [1e308, 1e308]), (["0"], [0], [1]),
])
def test_invalid_inputs_are_rejected(reference, prediction, weights):
    with pytest.raises(ValueError):
        weighted_bernoulli_distances(reference, prediction, weights)


def test_metric_wrapper_preserves_existing_fields_and_adds_hard_reference_means():
    labels = np.array([0, 1, 1])
    prediction = np.array([0.2, 0.7, 0.9])
    weights = np.array([1, 2, 3], dtype=float)
    neighbors = np.array([1, 3, 4])
    original = probability_metrics(labels, prediction, weights, neighbors)
    actual = probability_metrics_with_statistical_distances(labels, prediction, weights, neighbors)
    assert {name: actual[name] for name in original} == original
    assert {name: actual[name] for name in STATISTICAL_DISTANCE_FIELDS} == weighted_bernoulli_distances(labels, prediction, weights)


def test_empty_wrapper_scope_and_binary_reference_requirement():
    empty = np.array([], dtype=float)
    actual = probability_metrics_with_statistical_distances(empty, empty, empty, empty)
    assert all(actual[name] is None for name in STATISTICAL_DISTANCE_FIELDS)
    with pytest.raises(ValueError, match="binary observed labels"):
        probability_metrics_with_statistical_distances([0.25], [0.5], [1], [1])
