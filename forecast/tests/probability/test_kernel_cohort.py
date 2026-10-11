"""Independent tests of current-state contact and matched population semantics."""

from dataclasses import replace

import numpy as np
import pytest

from wildfire.cache import CachedSplit
from wildfire.cohort import centered_slice
from wildfire.cohort import cohort_payload
from wildfire.cohort import cohort_summary
from wildfire.cohort import common_indices
from wildfire.cohort import crop_split
from wildfire.cohort import evaluate_contact_predictions
from wildfire.cohort import kernel_contact_mask
from wildfire.cohort import kernel_neighbor_count
from wildfire.cohort import native_indices


def _population():
    burned = np.zeros((5, 1, 9, 9), dtype=np.float32)
    burned[0, 0, 4, 5] = 1  # Inside centered 3x3.
    burned[1, 0, 4, 6] = 1  # Inside 5x5, outside 3x3.
    burned[2, 0, 4, 8] = 1  # Inside 9x9, outside 7x7.
    burned[4, 0, 4, 4] = 1  # Already burned center is never its own contact.
    return CachedSplit(
        environment=np.arange(5 * 2 * 81, dtype=np.float32).reshape(5, 2, 9, 9),
        burned=burned, target=np.array([1, 0, 1, 1, 0], np.float32),
        weight=np.array([2, 3, 7, 11, 13], np.float64),
        event_index=np.array([0, 1, 1, 2, 2]),
        time_utc=np.arange(5, dtype=np.int64) * 3600,
        row=np.arange(5, dtype=np.int64) + 20, col=np.arange(5, dtype=np.int64) + 30,
    )


def test_native_footprint_contact_and_common_smallest_contact_are_label_free():
    data = _population()
    np.testing.assert_array_equal(native_indices(data, 3), [0])
    np.testing.assert_array_equal(native_indices(data, 5), [0, 1])
    np.testing.assert_array_equal(native_indices(data, 7), [0, 1])
    np.testing.assert_array_equal(native_indices(data, 9), [0, 1, 2])
    np.testing.assert_array_equal(common_indices(data), [0])
    flipped = replace(data, target=1 - data.target)
    np.testing.assert_array_equal(common_indices(flipped), common_indices(data))
    np.testing.assert_array_equal(native_indices(flipped, 9), native_indices(data, 9))
    np.testing.assert_array_equal(kernel_neighbor_count(data.burned, 3), [1, 0, 0, 0, 0])


def test_unknowns_are_not_zero_and_native_crop_does_not_require_outer_known_cells():
    data = _population()
    burned = data.burned.copy()
    burned[0, 0, 0, 0] = np.nan  # Outside 3x3; common requires complete 9x9.
    altered = replace(data, burned=burned)
    np.testing.assert_array_equal(native_indices(altered, 3), [0])
    np.testing.assert_array_equal(common_indices(altered), [])
    validity = np.ones(data.burned.shape, dtype=bool)
    validity[0, 0, 4, 5] = False
    assert not kernel_contact_mask(data.burned, 3, validity).any()
    # A known contact alongside an unknown source still cannot be evaluated.
    validity[0, 0, 4, 5] = True
    validity[0, 0, 3, 3] = False
    assert kernel_neighbor_count(data.burned, 3, validity)[0] == 1
    assert not kernel_contact_mask(data.burned, 3, validity)[0]
    environment = data.environment.copy()
    environment[0, 0, 3, 3] = np.nan
    assert not len(native_indices(replace(data, environment=environment), 3))


def test_cropping_retains_no_contact_inference_rows_and_original_population_identity():
    data = _population()
    all_inputs = crop_split(data, 3)
    assert len(all_inputs) == len(data)
    assert not all_inputs.burned[3].any()
    assert np.shares_memory(all_inputs.environment, data.environment)
    np.testing.assert_array_equal(all_inputs.target, data.target)
    np.testing.assert_array_equal(all_inputs.weight, data.weight)
    selected = np.array([2, 0])
    cropped = crop_split(data, 5, selected)
    np.testing.assert_array_equal(cropped.environment, data.environment[selected, :, 2:7, 2:7])
    payload = cohort_payload(data, selected)
    np.testing.assert_array_equal(payload["source_index"], selected)
    for saved, field in (("y", "target"), ("w", "weight"), ("row", "row"), ("col", "col"),
                         ("event_index", "event_index"), ("time_utc", "time_utc")):
        np.testing.assert_array_equal(payload[saved], getattr(data, field)[selected])
    with pytest.raises(ValueError, match="Duplicate"):
        crop_split(data, 3, np.array([0, 0]))
    duplicate = replace(data, event_index=np.zeros(5, np.int64), time_utc=np.zeros(5, np.int64),
                        row=np.ones(5, np.int64), col=np.ones(5, np.int64))
    with pytest.raises(ValueError, match="event/time/row/column"):
        cohort_payload(duplicate, np.arange(5))


def test_native_metrics_exclude_no_contact_while_common_scores_match_labels_and_weights():
    data = _population()
    prediction = np.array([.5, .5, .5, 1., 0.])
    result = evaluate_contact_predictions(data, {"k3": prediction, "k9": prediction},
                                          kernel_sizes={"k3": 3, "k9": 9})
    assert result["prediction_sample_count"] == 5
    assert result["native"]["k3"]["metrics"]["sample_count"] == 1
    assert result["native"]["k9"]["metrics"]["sample_count"] == 3
    assert result["native"]["k9"]["metrics"]["represented_population_weight"] == 12
    assert result["native"]["k9"]["metrics"]["zero_contact_population_weight"] == 0
    assert result["common"]["k3"]["sample_count"] == result["common"]["k9"]["sample_count"] == 1
    assert result["common"]["k3"]["brier"] == result["common"]["k9"]["brier"] == .25
    summary = cohort_summary(data, native_indices(data, 9), 9)
    assert summary["weighted_prevalence"] == pytest.approx(9 / 12)
    assert summary["excluded_positive_sample_count"] == 1
    with pytest.raises(ValueError, match="every base-cache row"):
        evaluate_contact_predictions(data, {"k3": prediction[:1]}, kernel_sizes={"k3": 3})


@pytest.mark.parametrize("outer,inner", [(8, 3), (9, 4), (9, 11), (3, True), (3, 1)])
def test_invalid_supports_rejected(outer, inner):
    with pytest.raises(ValueError, match="odd integers"):
        centered_slice(outer, inner)


def test_nonbinary_current_state_rejected_and_already_burned_center_excluded():
    data = _population()
    burned = data.burned.copy()
    burned[0, 0, 4, 5] = .5
    with pytest.raises(ValueError, match="zero or one"):
        kernel_contact_mask(burned, 3)
    data.burned[4, 0, 4, 5] = 1
    assert kernel_neighbor_count(data.burned, 3)[4] == 1
    assert not kernel_contact_mask(data.burned, 3)[4]
