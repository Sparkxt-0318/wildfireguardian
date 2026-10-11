"""Independent population, coverage, and randomization checks for row splits."""

import json

import numpy as np
import pytest

from wildfire.prepare import weighted_row_assignment


def _zero_patches(count, outer=9):
    return np.zeros((count, 1, outer, outer), dtype=np.float32)


def test_allocation_uses_inverse_weight_mass_rather_than_sampled_class_frequency():
    # Positive population mass is 10. Negative population mass is 20 even
    # though its sample has only five rows: four weight-1 rows and one weight-16
    # row. The exact 20% allocation is positive mass 2 and negative mass 4.
    target = np.array([1] * 10 + [0] * 5, dtype=np.float32)
    weight = np.array([1] * 14 + [16], dtype=np.float64)
    original_weight = weight.copy()
    validation, audit = weighted_row_assignment(target, weight, _zero_patches(15), seed=7)
    assert weight[validation & (target == 1)].sum() == 2
    assert weight[validation & (target == 0)].sum() == 4
    assert weight[validation].sum() == 6  # 20% of population mass 30.
    assert validation.sum() == 6  # 40% of sampled rows, rather than 20%.
    np.testing.assert_array_equal(weight, original_weight)
    row = audit["cohorts"]["base"]
    assert row["pooled"]["weighted_frequency"] == pytest.approx(1 / 3)
    assert row["train"]["weighted_frequency"] == pytest.approx(1 / 3)
    assert row["validation"]["weighted_frequency"] == pytest.approx(1 / 3)
    assert target[validation].mean() != pytest.approx(target.mean())
    assert audit["inverse_inclusion_weights_unchanged"] is True


def test_weighted_balance_for_every_centered_contact_support():
    # Ten positives of weight one and ten negatives of weight (band_index+1)
    # are placed in each of five independently specified contact bands.
    targets, weights, first_contacts = [], [], []
    for band_index, support in enumerate((0, 3, 5, 7, 9)):
        targets.extend([1] * 10 + [0] * 10)
        weights.extend([1] * 10 + [band_index + 1] * 10)
        first_contacts.extend([support] * 20)
    target = np.array(targets, dtype=np.float32)
    weight = np.array(weights, dtype=np.float64)
    bands = np.array(first_contacts)
    burned = _zero_patches(100)
    for index, support in enumerate(bands):
        if support:
            # A neighbor at distance d first enters a centered (2d+1) crop.
            burned[index, 0, 4, 4 + (support - 1) // 2] = 1
    validation, audit = weighted_row_assignment(target, weight, burned, seed=13)
    assert audit["stratum_count"] == 10
    expected = {"base": (50, 150), "native_3": (10, 20),
                "native_5": (20, 50), "native_7": (30, 90),
                "native_9": (40, 140)}
    for name, (positive, negative) in expected.items():
        support = 9 if name == "base" else int(name.removeprefix("native_"))
        members = np.ones(100, dtype=bool) if name == "base" else ((bands > 0) & (bands <= support))
        assert weight[members & validation & (target == 1)].sum() == .2 * positive
        assert weight[members & validation & (target == 0)].sum() == .2 * negative
        row = audit["cohorts"][name]
        assert row["pooled"]["positive_weight"] == positive
        assert row["pooled"]["negative_weight"] == negative
        assert row["train"]["weighted_frequency"] == pytest.approx(positive / (positive + negative))
        assert row["validation"]["weighted_frequency"] == pytest.approx(positive / (positive + negative))
        assert row["validation_positive_mass_share"] == pytest.approx(.2)
        assert row["validation_negative_mass_share"] == pytest.approx(.2)
        assert row["frequency_difference_validation_minus_training"] == pytest.approx(0)


def test_singleton_signature_stays_in_training_and_preserves_categorical_coverage():
    target = np.zeros(11, dtype=np.float32)
    weight = np.ones(11, dtype=np.float64)
    # The last row alone contains categorical column 1. It must stay in train.
    presence = np.zeros((11, 2), dtype=bool)
    presence[:10, 0] = True
    presence[10, 1] = True
    validation, audit = weighted_row_assignment(target, weight, _zero_patches(11), presence)
    assert not validation[10]
    assert validation[:10].sum() == 2
    assert audit["singleton_stratum_count"] == 1
    assert audit["training_categorical_presence_columns"] == [0, 1]
    assert audit["validation_categorical_presence_columns"] == [0]
    assert audit["validation_categories_subset_of_training"] is True
    assert not (presence[validation].any(axis=0) & ~presence[~validation].any(axis=0)).any()
    # Empty contact populations have no defined prevalence, rather than zero.
    assert audit["cohorts"]["native_3"]["validation"]["weighted_frequency"] is None
    assert audit["cohorts"]["native_3"]["validation_positive_mass_share"] is None
    json.dumps(audit, allow_nan=False)


@pytest.mark.parametrize("fraction", [.001, .2, .999])
def test_two_row_strata_keep_both_sides_despite_unattainable_fraction(fraction):
    target = np.array([0, 0, 1, 1], dtype=np.float32)
    weight = np.array([1, 100, 1, 100], dtype=np.float64)
    validation, audit = weighted_row_assignment(target, weight, _zero_patches(4),
                                                validation_fraction=fraction)
    assert validation[:2].sum() == 1
    assert validation[2:].sum() == 1
    assert all(row["training_rows"] == row["validation_rows"] == 1 for row in audit["strata"])
    assert all(row["target_validation_population_weight"] == pytest.approx(101 * fraction)
               for row in audit["strata"])
    assert audit["exact_weighted_subset_optimization"] is False


def test_seeded_rows_are_randomized_without_largest_weight_first_bias():
    # A largest-weight-first allocation would select six weight-10 rows and
    # no weight-1 rows for every seed. Random rows should include many light
    # rows while still allocating exactly 60 of the 300 population units.
    target = np.zeros(120, dtype=np.float32)
    weight = np.array([1] * 100 + [10] * 20, dtype=np.float64)
    selected_light_counts, selected_row_counts = [], []
    for seed in range(16):
        validation, _ = weighted_row_assignment(target, weight, _zero_patches(120), seed=seed)
        assert weight[validation].sum() == 60
        selected_light_counts.append(validation[:100].sum())
        selected_row_counts.append(validation.sum())
    # Wide deterministic bounds test the intended random-order behavior;
    # they are not a statistical claim about optimal inclusion probabilities.
    assert np.mean(selected_light_counts) > 10
    assert np.mean(selected_row_counts) > 15


def test_reproducibility_coverage_and_count_guards_for_multiple_signatures():
    rng = np.random.default_rng(981)
    count = 400
    target = rng.integers(0, 2, count).astype(np.float32)
    weight = rng.integers(1, 25, count).astype(np.float64)
    presence = rng.integers(0, 2, (count, 4)).astype(bool)
    burned = _zero_patches(count, outer=5)
    original = (target.copy(), weight.copy(), presence.copy(), burned.copy())
    first, first_audit = weighted_row_assignment(target, weight, burned, presence, seed=12)
    second, second_audit = weighted_row_assignment(target, weight, burned, presence, seed=12)
    third, _ = weighted_row_assignment(target, weight, burned, presence, seed=13)
    np.testing.assert_array_equal(first, second)
    assert first_audit == second_audit
    assert not np.array_equal(first, third)
    for value, preserved in zip((target, weight, presence, burned), original):
        np.testing.assert_array_equal(value, preserved)
    assert first.dtype == np.bool_ and first.shape == (count,)
    assert first_audit["training_rows"] + first_audit["validation_rows"] == count
    # Check strata independently from the input target and supplied signature.
    signatures = {(int(target[i]), tuple(presence[i])) for i in range(count)}
    for label, signature in signatures:
        rows = (target == label) & (presence == signature).all(axis=1)
        if rows.sum() == 1:
            assert not first[rows].any()
        else:
            assert first[rows].any() and (~first[rows]).any()
    assert not (presence[first].any(axis=0) & ~presence[~first].any(axis=0)).any()
    assert first_audit["test_labels_used"] is False
    assert first_audit["test_partition_received"] is False


@pytest.mark.parametrize("presence,target", [
    (np.array([[1, 0], [0, 1]], dtype=bool), np.array([0, 0])),
    (np.ones((2, 1), dtype=bool), np.array([0, 1])),
])
def test_all_singleton_strata_cannot_create_a_covered_validation_partition(presence, target):
    with pytest.raises(ValueError, match="No stratum contains two rows"):
        weighted_row_assignment(target, np.ones(2), _zero_patches(2), presence)


@pytest.mark.parametrize("fraction", [0, 1, -.1, 1.1, np.nan, np.inf, True])
def test_invalid_fractions_rejected(fraction):
    with pytest.raises(ValueError, match="validation_fraction"):
        weighted_row_assignment(np.zeros(3), np.ones(3), _zero_patches(3),
                                validation_fraction=fraction)


@pytest.mark.parametrize("seed", [-1, True, 1.5])
def test_invalid_seeds_rejected(seed):
    with pytest.raises(ValueError, match="seed"):
        weighted_row_assignment(np.zeros(3), np.ones(3), _zero_patches(3), seed=seed)


@pytest.mark.parametrize("weight", [np.array([1, 0, 1]), np.array([1, .5, 1]),
                                    np.array([1, np.nan, 1]), np.array([1, np.inf, 1]),
                                    np.array([1e308, 1e308, 1e308])])
def test_invalid_or_overflowing_inverse_weights_rejected(weight):
    with pytest.raises(ValueError, match="weight"):
        weighted_row_assignment(np.zeros(3), weight, _zero_patches(3))


@pytest.mark.parametrize("target", [np.array([0, .5, 1]), np.array([0, np.nan, 1]),
                                    np.array([0, -1, 1])])
def test_nonbinary_or_unknown_targets_rejected(target):
    with pytest.raises(ValueError, match="Targets"):
        weighted_row_assignment(target, np.ones(3), _zero_patches(3))


@pytest.mark.parametrize("value", [.5, np.nan, np.inf])
def test_unknown_or_nonbinary_burned_states_rejected(value):
    burned = _zero_patches(3)
    burned[0, 0, 0, 0] = value
    with pytest.raises(ValueError, match="known and exactly zero or one"):
        weighted_row_assignment(np.zeros(3), np.ones(3), burned)


def test_already_burned_centers_rejected():
    burned = _zero_patches(3)
    burned[0, 0, 4, 4] = 1
    with pytest.raises(ValueError, match="currently be unburned"):
        weighted_row_assignment(np.zeros(3), np.ones(3), burned)


@pytest.mark.parametrize("burned", [np.zeros((3, 9, 9)), np.zeros((3, 1, 8, 8)),
                                    np.zeros((3, 1, 9, 7)), np.zeros((2, 1, 9, 9))])
def test_invalid_spatial_shapes_rejected(burned):
    with pytest.raises(ValueError, match="burned must have shape"):
        weighted_row_assignment(np.zeros(3), np.ones(3), burned)


@pytest.mark.parametrize("presence", [np.ones((3, 2), dtype=int), np.ones((2, 2), dtype=bool),
                                      np.ones(3, dtype=bool)])
def test_categorical_presence_requires_explicit_bool_columns(presence):
    with pytest.raises(ValueError, match="categorical_presence"):
        weighted_row_assignment(np.zeros(3), np.ones(3), _zero_patches(3), presence)


@pytest.mark.parametrize("target,weight", [(np.zeros((3, 1)), np.ones(3)),
                                          (np.zeros(3), np.ones(2)),
                                          (np.zeros(1), np.ones(1))])
def test_invalid_target_weight_shapes_or_insufficient_population_rejected(target, weight):
    with pytest.raises(ValueError, match="target and weight"):
        weighted_row_assignment(target, weight, _zero_patches(len(target)))
