"""Deterministic simulator import, exact endpoint scoring, and distance oracles."""
import json
import math

import numpy as np
import pytest
import torch

from wildfire.farsite_evaluation import (
    evaluate_farsite, farsite_cumulative_prediction, summarize_farsite,
)


def _cutoff(initial, *, known=None, time=10_000, pixel_valid=None):
    values = np.asarray(initial, dtype=np.float64).reshape(1, 1, -1)
    result = dict(burned_area=values,
                  burned_area_valid=np.ones(values.shape, dtype=bool) if known is None
                  else np.asarray(known, dtype=bool).reshape(values.shape),
                  time_utc=np.asarray(time, dtype=np.int64), event_id="fixture")
    if pixel_valid is not None:
        result["pixel_valid"] = np.asarray(pixel_valid, dtype=bool).reshape(1, -1)
    return result


def _reference(initial, endpoint, *, hours=1, initial_known=None, endpoint_known=None,
               pixel_valid=None, time=10_000):
    values = np.asarray([initial, endpoint], dtype=float).reshape(2, 1, 1, -1)
    valid = np.ones(values.shape, dtype=bool)
    if initial_known is not None:
        valid[0, 0, 0] = initial_known
    if endpoint_known is not None:
        valid[1, 0, 0] = endpoint_known
    result = dict(burned_area=values, burned_area_valid=valid,
                  time_utc=np.asarray([time, time + int(hours * 3600)], dtype=np.int64),
                  time_valid=np.ones(2, dtype=bool), event_id="fixture")
    if pixel_valid is not None:
        result["pixel_valid"] = np.asarray(pixel_valid, dtype=bool).reshape(1, -1)
    return result


def _predict(arrivals, initial, *, hours=1, coverage=None, **options):
    cutoff = options.pop("cutoff", _cutoff(initial))
    arrivals = np.asarray(arrivals, dtype=float).reshape(1, -1)
    if coverage is None:
        coverage = np.ones(arrivals.shape, dtype=bool)
    return farsite_cumulative_prediction(
        arrivals, cutoff, hours=hours, arrival_origin_time_utc=options.pop("arrival_origin_time_utc", 10_000),
        no_burn_value=options.pop("no_burn_value", -9999), coverage=np.asarray(coverage, dtype=bool).reshape(arrivals.shape),
        **options,
    )


@pytest.mark.parametrize("arrivals, outcomes, error", [
    ([30, -9999, 60, -9999], [1, 0, 1, 0], 0),
    ([30, -9999, 60, -9999], [0, 0, 1, 1], .5),
    ([30, -9999, 60, -9999], [0, 1, 0, 1], 1),
])
def test_all_nine_distances_have_independent_deterministic_error_fraction_oracles(arrivals, outcomes, error):
    result = _predict(arrivals, [0] * 4)
    scores = result.evaluate(_reference([0] * 4, outcomes), hours=1)["per_horizon"][0]["metrics"]
    for name in ("brier", "bernoulli_total_variation_distance_mean", "bernoulli_hellinger_distance_mean",
                 "bernoulli_wasserstein_1_distance_mean", "bernoulli_wasserstein_2_distance_mean"):
        assert scores[name] == pytest.approx(error, abs=1e-15)
    assert scores["bernoulli_jensen_shannon_divergence_mean"] == pytest.approx(error * math.log(2), abs=1e-15)
    assert scores["bernoulli_jensen_shannon_distance_mean"] == pytest.approx(error * math.sqrt(math.log(2)), abs=1e-15)
    for name in ("exact_negative_log_likelihood_mean", "bernoulli_kl_divergence_mean", "bernoulli_bhattacharyya_distance_mean"):
        assert scores[name] == ("infinity" if error else 0)
    epsilon = scores["log_loss_probability_floor"]
    expected = -(1 - error) * math.log1p(-epsilon) - error * math.log(epsilon)
    # Stored clipping uses float64 (1-epsilon); subtracting it from one has
    # about 5e-10 relative rounding error at epsilon=1e-7. The theoretical
    # symmetric-floor oracle therefore needs a corresponding absolute bound.
    assert scores["floored_bernoulli_kl_divergence_mean"] == pytest.approx(expected, rel=0, abs=1e-9)


def test_requested_horizon_order_exact_endpoint_and_absorbing_initial_burns():
    result = _predict([60, 180, 360, 360.00001, 0, -9999], [0, 0, 0, 0, 0, 1], hours=[6, 1, 3])
    assert result.hours == (6, 1, 3)
    expected = {1: [1, 0, 0, 0, 1, 0], 3: [1, 1, 0, 0, 1, 0], 6: [1, 1, 1, 0, 1, 0]}
    for hour, values in expected.items():
        forecast = result.at(hours=hour)
        np.testing.assert_array_equal(forecast.probability.numpy().ravel(), values)
        assert forecast.burned_probability.numpy().ravel()[-1] == 1
        assert np.isnan(forecast.rate.numpy()).all()
        assert not forecast.rate_valid.any()
        assert forecast.mc_standard_error is None
        assert forecast.confidence_lower is None and forecast.confidence_upper is None
    assert result.metadata["method"] == "farsite_deterministic"
    assert result.metadata["scenario_count"] == 1


def test_elapsed_minutes_origin_offset_is_applied_before_endpoint_comparison():
    result = _predict([69.99, 70, 70.01], [0, 0, 0], arrival_origin_time_utc=9400)
    np.testing.assert_array_equal(result.at(hours=1).probability.numpy().ravel(), [1, 1, 0])
    iso = _predict([70], [0], arrival_origin_time_utc="1970-01-01T11:36:40+09:00")
    assert iso.at(hours=1).probability.item() == 1
    assert iso.metadata["arrival_origin_time_utc"] == 9400


def test_unknown_initial_state_assumes_zero_but_original_reference_remains_unknown():
    cutoff = _cutoff([1, np.nan, 0, 0], known=[True, False, True, True])
    observed = _reference([1, np.nan, 0, 0], [1, 1, 1, 0], initial_known=[True, False, True, True])
    original_mask = observed["burned_area_valid"].copy()
    prediction, reports = evaluate_farsite(
        np.asarray([[0, 10, 20, -9999]], dtype=float), cutoff, observed, hours=1,
        arrival_origin_time_utc=10_000, no_burn_value=-9999, coverage=np.ones((1, 4), dtype=bool),
    )
    np.testing.assert_array_equal(prediction.at(hours=1).probability.numpy().ravel(), [0, 1, 1, 0])
    np.testing.assert_array_equal(prediction.at(hours=1).burned_probability.numpy().ravel(), [1, 1, 1, 0])
    assert reports["new_burn"]["per_horizon"][0]["metrics"]["sample_count"] == 2
    assert reports["burned"]["per_horizon"][0]["metrics"]["sample_count"] == 4
    np.testing.assert_array_equal(observed["burned_area_valid"], original_mask)
    assert np.isnan(cutoff["burned_area"][0, 0, 1])


def test_no_arrival_sentinel_is_known_unburned_only_on_explicit_successful_coverage():
    result = _predict([-9999, -9999, np.nan, -2], [0, 1, 1, 0], coverage=[True, True, False, False])
    forecast = result.at(hours=1)
    np.testing.assert_array_equal(forecast.valid.numpy().ravel(), [True, True, False, False])
    np.testing.assert_array_equal(forecast.probability.numpy().ravel()[:2], [0, 0])
    np.testing.assert_array_equal(forecast.burned_probability.numpy().ravel()[:2], [0, 1])
    assert np.isnan(forecast.probability.numpy().ravel()[2:]).all()
    assert np.isnan(forecast.burned_probability.numpy().ravel()[2:]).all()


def test_full_rectangle_and_padding_remain_present_but_unavailable():
    cutoff = _cutoff([0, 0, 1], pixel_valid=[True, False, True])
    result = _predict([20, np.nan, -9999], [0, 0, 1], cutoff=cutoff)
    assert result.probability.shape == (1, 1, 1, 3)
    np.testing.assert_array_equal(result.valid.numpy().ravel(), [True, False, True])
    assert np.isnan(result.probability.numpy().ravel()[1])
    observed = _reference([0, 0, 1], [1, 1, 1], pixel_valid=[True, False, True])
    assert result.evaluate(observed, hours=1)["per_horizon"][0]["metrics"]["sample_count"] == 1


def test_independent_cutoff_leading_dimensions_and_time_padding_are_preserved():
    cutoff = dict(burned_area=np.zeros((2, 1, 1, 2)), burned_area_valid=np.ones((2, 1, 1, 2), dtype=bool),
                  time_utc=np.asarray([10_000, -1]), time_valid=np.asarray([True, False]), event_id="fixture")
    result = farsite_cumulative_prediction(np.asarray([[60, -9999]]), cutoff, hours=[1, 2],
                                          arrival_origin_time_utc=10_000, no_burn_value=-9999,
                                          coverage=np.ones((1, 2), dtype=bool))
    assert result.probability.shape == (2, 2, 1, 1, 2)
    assert result.at(hours=1).valid[0].all()
    assert not result.at(hours=1).valid[1].any()
    assert np.isnan(result.at(hours=1).probability[1].numpy()).all()


def test_imported_inputs_numpy_exports_and_metadata_are_independent_copies():
    arrivals = np.asarray([[60, -9999]], dtype=float)
    coverage = np.ones((1, 2), dtype=bool)
    initial = _cutoff([0, 1])
    extra = {"scenario": {"wind": "cutoff"}}
    result = farsite_cumulative_prediction(arrivals, initial, hours=[1, 2],
                                          arrival_origin_time_utc=10_000, no_burn_value=-9999,
                                          coverage=coverage, metadata=extra)
    arrivals[:] = -9999
    initial["burned_area"][:] = 0
    coverage[:] = False
    extra["scenario"]["wind"] = "changed"
    exported = result.numpy()
    assert result.at(hours=1).probability.flatten()[0] == 1
    assert result.at(hours=1).burned_probability.flatten()[1] == 1
    assert result.at(hours=1).valid.all()
    assert result.metadata["scenario"]["wind"] == "cutoff"
    assert json.loads(str(exported["metadata_json"]))["method"] == "farsite_deterministic"
    exported["probability"][:] = 99
    exported["burned_probability"][:] = 99
    exported["valid"][:] = False
    assert result.probability.max() <= 1 and result.burned_probability.max() <= 1
    assert result.valid.all()
    assert "mc_standard_error" not in exported and "confidence_lower" not in exported


def test_summary_rows_use_original_truth_and_shared_intersection_entries():
    result = _predict([20, -9999, 50, -9999], [0, 0, 0, 1])
    observed = _reference([0, 0, 0, 1], [1, 1, 0, 1])
    rows, entries = summarize_farsite(result, observed, hours=1, model_id="scenario", cohort_mask=np.asarray([[True, False, True, True]]))
    assert len(rows) == 4
    shared = next(row for row in rows if row["quantity"] == "new_burn" and row["cohort"] == "shared_models")
    native = next(row for row in rows if row["quantity"] == "new_burn" and row["cohort"] == "native")
    assert shared["metrics"]["sample_count"] == 2
    assert native["metrics"]["sample_count"] == 3
    assert shared["shared_retention_fraction"] == pytest.approx(2 / 3)
    np.testing.assert_array_equal(entries[("shared_models", "new_burn")]["y"], [1, 0])
    np.testing.assert_array_equal(entries[("shared_models", "new_burn")]["p"], [1, 1])
    assert shared["metrics"]["brier"] == .5
    json.dumps(rows, allow_nan=False)
    with pytest.raises(ValueError, match="exactly one"):
        summarize_farsite(result, observed, hours=[1, 2])


@pytest.mark.parametrize("arrivals", [[np.nan], [np.inf], [-1]])
def test_unavailable_or_undocumented_arrivals_on_declared_coverage_are_rejected(arrivals):
    with pytest.raises(ValueError, match="declared coverage"):
        _predict(arrivals, [0])


@pytest.mark.parametrize("sentinel", [0, 1, np.nan, np.inf, True])
def test_no_burn_sentinel_requires_explicit_finite_negative_value(sentinel):
    with pytest.raises(ValueError, match="finite negative"):
        _predict([-9999], [0], no_burn_value=sentinel)


@pytest.mark.parametrize("origin", [True, 10_000.0, "1970-01-01T02:46:40", "1970-01-01T02:46:40.001Z", -1, 10_001])
def test_origin_requires_unambiguous_whole_second_clock_not_after_cutoff(origin):
    with pytest.raises((ValueError, TypeError), match="arrival_origin_time_utc"):
        _predict([60], [0], arrival_origin_time_utc=origin)


def test_shape_mask_binary_and_metadata_contracts_are_checked_before_import():
    cutoff = _cutoff([0, 0])
    with pytest.raises(ValueError, match="original"):
        farsite_cumulative_prediction(np.zeros((2, 1)), cutoff, hours=1, arrival_origin_time_utc=10_000,
                                      no_burn_value=-9999, coverage=np.ones((1, 2), dtype=bool))
    with pytest.raises(TypeError, match="booleans"):
        farsite_cumulative_prediction(np.zeros((1, 2)), cutoff, hours=1, arrival_origin_time_utc=10_000,
                                      no_burn_value=-9999, coverage=np.ones((1, 2), dtype=int))
    with pytest.raises(ValueError, match="binary"):
        _predict([60], [.2])
    bad_mask = _cutoff([0, 0])
    bad_mask["burned_area_valid"] = np.ones((1, 2), dtype=bool)
    with pytest.raises(ValueError, match="exact complete shape"):
        _predict([60, 60], [0, 0], cutoff=bad_mask)
    with pytest.raises(ValueError, match="must not override"):
        _predict([60], [0], metadata={"method": "recursive", "n_samples": 1024})


def test_future_outcome_fields_are_never_read_during_import_and_random_state_is_unchanged():
    class Forbidden:
        def __array__(self, *args, **kwargs):
            raise AssertionError("Future outcome field was read during simulator import")

    cutoff = _cutoff([0, 1])
    cutoff.update(arrival_hours=Forbidden(), newly_burned_area=Forbidden(), arrival_valid=Forbidden())
    numpy_state = np.random.get_state()
    torch_state = torch.random.get_rng_state().clone()
    _predict([60, -9999], [0, 1], cutoff=cutoff)
    updated = np.random.get_state()
    assert numpy_state[0] == updated[0] and numpy_state[2:] == updated[2:]
    np.testing.assert_array_equal(numpy_state[1], updated[1])
    assert torch.equal(torch_state, torch.random.get_rng_state())
