"""Explicit fixed-state cumulative horizons, reference alignment, and plotting."""

from copy import deepcopy
from dataclasses import replace

import matplotlib

matplotlib.use("Agg", force=True)

import matplotlib.pyplot as plt
import numpy as np
import pytest
import torch

from tests.test_api import checkpoint, inputs
from tests.test_prediction import _sample
from wildfire import CumulativePrediction, Prediction, load_model


@pytest.fixture(autouse=True)
def close_figures():
    yield
    plt.close("all")


def _reference(sample, states, times):
    states = np.asarray(states)
    return {
        "burned_area": states,
        "burned_area_valid": np.ones(states.shape, dtype=bool),
        "time_utc": np.asarray(times, dtype=np.int64),
        "time_valid": np.ones(np.shape(times), dtype=bool),
        "pixel_valid": deepcopy(sample["pixel_valid"]),
        "event_id": deepcopy(sample["event_id"]),
        "affine_transform": deepcopy(sample["affine_transform"]),
        "epsg": deepcopy(sample["epsg"]),
    }


def _assert_prediction_equal(actual, expected):
    assert isinstance(actual, Prediction)
    for field in ("probability", "valid", "rate", "rate_valid", "coordinates"):
        value = getattr(actual, field)
        other = getattr(expected, field)
        if value is None or other is None:
            assert value is other
        else:
            torch.testing.assert_close(value, other, rtol=0, atol=0, equal_nan=True)
    for field in ("time_utc", "dt_hours"):
        np.testing.assert_array_equal(getattr(actual, field), getattr(expected, field))
    assert actual.event_id == expected.event_id


def test_requested_horizons_preserve_order_and_match_individual_fixed_cutoff_predictions(checkpoint, inputs):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    cumulative = model.predict_cumulative(sample, method="fixed", hours=[6, 1, 3])
    assert isinstance(cumulative, CumulativePrediction)
    assert cumulative.hours == (6.0, 1.0, 3.0)
    assert cumulative.probability.shape == cumulative.rate.shape == (3, 2, 1, 7, 9)
    assert cumulative.valid.shape == cumulative.rate_valid.shape == cumulative.probability.shape
    assert not cumulative.probability.requires_grad and not cumulative.rate.requires_grad
    for i, hours in enumerate(cumulative.hours):
        expected = model.predict(sample, dt_hours=hours)
        _assert_prediction_equal(cumulative.at(hours=hours), expected)
        torch.testing.assert_close(cumulative.probability[i], expected.probability, rtol=0, atol=0, equal_nan=True)
        torch.testing.assert_close(cumulative.valid[i], expected.valid, rtol=0, atol=0)
    np.testing.assert_array_equal(cumulative.time_utc, sample["time_utc"])
    torch.testing.assert_close(cumulative.coordinates, cumulative.at(hours=1).coordinates, rtol=0, atol=0, equal_nan=True)
    assert cumulative.event_id == sample["event_id"]


def test_single_exponential_cumulative_q_uses_the_current_rate_and_does_not_expand_the_fire(checkpoint, inputs):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    cumulative = model.predict_cumulative(sample, method="fixed", hours=[1, 3, 6])
    initial = cumulative.at(hours=1)
    valid_rate = initial.rate_valid
    for hours in cumulative.hours:
        result = cumulative.at(hours=hours)
        expected = -torch.expm1(-initial.rate * hours)
        torch.testing.assert_close(result.probability[valid_rate], expected[valid_rate], rtol=1e-6, atol=1e-7)
        torch.testing.assert_close(result.rate, initial.rate, rtol=0, atol=0, equal_nan=True)
        assert torch.all(result.probability[:, 0, 3, 4] == 0)  # Already burned at the cutoff.
        assert torch.all(result.probability[:, 0, 1, 7] == 0)  # No initial burned neighbor.
    shared = cumulative.valid.all(dim=0)
    assert torch.all(cumulative.probability[0][shared] <= cumulative.probability[1][shared])
    assert torch.all(cumulative.probability[1][shared] <= cumulative.probability[2][shared])


def test_bayesian_horizons_average_component_q_at_each_horizon_instead_of_compounding_q1(tmp_path):
    from tests.probability.test_bayesian_models import _ensemble, _prediction_inputs
    from wildfire.inference import bayesian_checkpoint_payload

    ensemble = _ensemble()
    path = tmp_path / "mixture.pt"
    torch.save(bayesian_checkpoint_payload(ensemble), path)
    model = load_model(path)
    burned, environment = _prediction_inputs()
    cumulative = model.predict_cumulative(
        burned, environment, method="fixed", hours=[1, 3, 6],
        channel_names=model.channel_names, boundary="zero",
    )
    weights = np.array([0.3, 0.7])
    rates = np.array([0.15, 0.8])
    q1 = float(weights @ -np.expm1(-rates))
    for hours in cumulative.hours:
        expected = float(weights @ -np.expm1(-rates * hours))
        result = cumulative.at(hours=hours)
        assert result.probability[0, 0, 3, 5].item() == pytest.approx(expected, abs=1e-12)
        _assert_prediction_equal(result, model.predict(
            burned, environment, channel_names=model.channel_names,
            boundary="zero", dt_hours=hours,
        ))
    expected6 = float(weights @ -np.expm1(-rates * 6))
    mean_rate_rule = float(-np.expm1(-(weights @ rates) * 6))
    compound_q1_rule = 1 - (1 - q1) ** 6
    assert abs(expected6 - mean_rate_rule) > 0.01
    assert abs(expected6 - compound_q1_rule) > 0.01
    assert abs(cumulative.at(hours=1).rate[0, 0, 3, 5].item()
               - cumulative.at(hours=6).rate[0, 0, 3, 5].item()) > 0.01


def test_each_horizon_forwards_current_inputs_and_predict_options_exactly(checkpoint, inputs, monkeypatch):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    original = model.predict
    calls = []

    def observed_call(*args, **options):
        calls.append((args, options.copy()))
        return original(*args, **options)

    monkeypatch.setattr(model, "predict", observed_call)
    model.predict_cumulative(sample, method="fixed", hours=[3, 0.5, 6], boundary="zero")
    assert len(calls) == 3
    assert [call[1]["dt_hours"] for call in calls] == [3, 0.5, 6]
    assert all(call[0][0] is sample for call in calls)
    assert all(call[1]["boundary"] == "zero" for call in calls)


def test_cumulative_prediction_never_reads_outcome_or_arrival_labels(checkpoint, inputs):
    model = load_model(checkpoint)
    fields = _sample(model, inputs)

    class CurrentInputs(dict):
        forbidden = {"newly_burned_area", "newly_burned_area_valid", "arrival_hours",
                     "arrival_valid", "future_labels"}

        def __getitem__(self, name):
            assert name not in self.forbidden, f"Inference read future label {name}"
            return super().__getitem__(name)

        def get(self, name, default=None):
            assert name not in self.forbidden, f"Inference read future label {name}"
            return super().get(name, default)

        def __contains__(self, name):
            assert name not in self.forbidden, f"Inference inspected future label {name}"
            return super().__contains__(name)

    guarded = CurrentInputs(**fields, newly_burned_area=object(), arrival_hours=object())
    actual = model.predict_cumulative(guarded, method="fixed", hours=[1, 6])
    expected = model.predict_cumulative(fields, method="fixed", hours=[1, 6])
    torch.testing.assert_close(actual.probability, expected.probability, rtol=0, atol=0, equal_nan=True)


@pytest.mark.parametrize("hours,expected", [
    (3, (3.0,)), (0.5, (0.5,)), (np.float64(2.5), (2.5,)),
    ((6, 1, 3), (6.0, 1.0, 3.0)), (np.array([3.0, 0.5]), (3.0, 0.5)),
])
def test_hours_accept_positive_scalar_and_iterable_real_values(checkpoint, inputs, hours, expected):
    model = load_model(checkpoint)
    result = model.predict_cumulative(_sample(model, inputs), method="fixed", hours=hours)
    assert result.hours == expected
    assert result.probability.shape[0] == len(expected)


@pytest.mark.parametrize("hours", [
    0, -1, True, np.bool_(True), "3", None, np.nan, np.inf, -np.inf, [],
    [1, 1], [1, 1.0], [1, 0], [1, True], [1, "3"], [1, np.nan], [1, np.inf],
    [[1, 3]], np.array([[1, 3]]),
])
def test_invalid_hours_are_rejected_before_running_inference(checkpoint, inputs, hours, monkeypatch):
    model = load_model(checkpoint)

    def forbidden(*args, **kwargs):
        raise AssertionError("Invalid horizons reached inference")

    monkeypatch.setattr(model, "predict", forbidden)
    with pytest.raises((TypeError, ValueError), match="hours"):
        model.predict_cumulative(_sample(model, inputs), method="fixed", hours=hours)


def test_dt_hours_cannot_conflict_with_requested_cumulative_horizons(checkpoint, inputs):
    model = load_model(checkpoint)
    with pytest.raises((TypeError, ValueError), match="dt_hours|hours"):
        model.predict_cumulative(_sample(model, inputs), method="fixed", hours=[1, 3], dt_hours=1)


@pytest.mark.parametrize("hours", [2, True, "1", np.nan])
def test_horizon_selection_requires_an_exact_requested_real_duration(checkpoint, inputs, hours):
    model = load_model(checkpoint)
    result = model.predict_cumulative(_sample(model, inputs), method="fixed", hours=[1, 3])
    with pytest.raises((TypeError, ValueError, KeyError), match="hours|horizon|requested"):
        result.at(hours=hours)


def test_cumulative_numpy_exports_are_independent_copies(checkpoint, inputs):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    result = model.predict_cumulative(sample, method="fixed", hours=[1, 3])
    exported = result.numpy()
    assert {"probability", "valid", "rate", "rate_valid", "hours", "coordinates", "time_utc"} <= set(exported)
    np.testing.assert_array_equal(exported["hours"], [1, 3])
    assert exported["valid"].dtype == exported["rate_valid"].dtype == np.dtype(bool)
    np.testing.assert_array_equal(exported["time_utc"], sample["time_utc"])
    exported["probability"][:] = -10
    exported["valid"][:] = False
    exported["hours"][:] = -1
    exported["coordinates"][:] = -10
    assert not torch.any(result.probability == -10)
    assert result.valid.any()
    assert result.hours == (1.0, 3.0)
    assert not torch.all(result.coordinates == -10)


def test_cumulative_plot_selects_the_requested_q_not_its_rate(checkpoint, inputs):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    initial = model.predict(sample, dt_hours=3)
    prediction = replace(initial, probability=torch.full_like(initial.probability, 0.2),
                         rate=torch.full_like(initial.rate, 5.0))
    result = CumulativePrediction(hours=(3,), _predictions=(prediction,))
    figure, axis = result.plot(hours=3, index=1)
    known = prediction.valid[1, 0].numpy()
    np.testing.assert_array_equal(np.ma.getmaskarray(axis.images[0].get_array()), ~known)
    np.testing.assert_allclose(axis.images[0].get_array().compressed(), np.full(known.sum(), 0.2), atol=1e-7)
    assert axis.images[0].get_clim() == (0, 1)
    assert "q" in figure.axes[-1].get_ylabel()
    assert "probability" in figure.axes[-1].get_ylabel().lower()
    figure.canvas.draw()


def test_cumulative_targets_use_exact_start_and_endpoint_states_in_reordered_reference_rows(checkpoint, inputs):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    sample["burned_area"][1, 0, 3, 5] = 1
    result = model.predict_cumulative(sample, method="fixed", hours=[1, 3, 6])
    times = [31_600, 13_600, 10_000, 20_800, 24_400, 35_200, 17_200]
    states = np.zeros((len(times), 1, 7, 9), dtype=float)
    states[:, 0, 3, 4] = 1
    for i, time in enumerate(times):
        if time >= 13_600:
            states[i, 0, 3, 5] = 1
        if time >= 20_800:
            states[i, 0, 2, 2] = 1
        if time >= 24_400:
            states[i, 0, 4, 5] = 1
        if time >= 31_600:
            states[i, 0, 4, 4] = 1
    reference = _reference(sample, states, times)
    for hours in (1, 3, 6):
        labels, known = result.aligned_observations(reference, hours=hours)
        assert known.all()
        for t, cutoff in enumerate(sample["time_utc"]):
            start = states[times.index(int(cutoff))]
            endpoint = states[times.index(int(cutoff + hours * 3600))]
            np.testing.assert_array_equal(labels[t], ((start == 0) & (endpoint == 1)).astype(float))
            assert labels[t, 0, 3, 4] == 0
    figure, axes = result.compare(reference, hours=3, index=0, colorbar=False)
    assert len(axes) == 1 and len(axes[0].images) == 2
    np.testing.assert_array_equal(axes[0].collections[0].get_offsets(), [[2, 2], [5, 3]])
    assert not result.at(hours=3).valid[0, 0, 2, 2]
    assert np.ma.getmaskarray(axes[0].images[0].get_array())[2, 2]
    assert not np.ma.getmaskarray(axes[0].images[1].get_array())[3, 4]
    figure.canvas.draw()


def test_cumulative_comparison_reads_burned_states_without_reading_hourly_event_labels(checkpoint, inputs):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    result = model.predict_cumulative(sample, method="fixed", hours=3)
    reference = _reference(sample, np.zeros((4, 1, 7, 9)), [10_000, 13_600, 20_800, 24_400])
    reference["burned_area"][2:, 0, 3, 5] = 1

    class CumulativeStates(dict):
        forbidden = {"newly_burned_area", "newly_burned_area_valid"}

        def __getitem__(self, name):
            assert name not in self.forbidden, f"Cumulative comparison read hourly label {name}"
            return super().__getitem__(name)

        def get(self, name, default=None):
            assert name not in self.forbidden, f"Cumulative comparison read hourly label {name}"
            return super().get(name, default)

        def __contains__(self, name):
            assert name not in self.forbidden, f"Cumulative comparison inspected hourly label {name}"
            return super().__contains__(name)

    guarded = CumulativeStates(**reference, newly_burned_area=object())
    figure, axes = result.compare(guarded, hours=3, index=0, colorbar=False)
    np.testing.assert_array_equal(axes[0].collections[0].get_offsets(), [[5, 3]])
    assert any("3 h" in text.get_text() for text in axes[0].get_legend().get_texts())
    figure.canvas.draw()


def test_cumulative_reference_states_cannot_change_from_known_burned_to_unburned(checkpoint, inputs):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    result = model.predict_cumulative(sample, method="fixed", hours=3)
    reference = _reference(sample, np.zeros((4, 1, 7, 9)), [10_000, 13_600, 20_800, 24_400])
    reference["burned_area"][0, 0, 3, 4] = 1
    with pytest.raises(ValueError, match="nondecreasing|burned.*unburned"):
        result.aligned_observations(reference, hours=3)
    reference["burned_area_valid"][2, 0, 3, 4] = False
    labels, known = result.aligned_observations(reference, hours=3)
    assert not known[0, 0, 3, 4] and np.isnan(labels[0, 0, 3, 4])


def test_explicit_cumulative_interval_targets_compare_the_selected_horizon(checkpoint, inputs):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    result = model.predict_cumulative(sample, method="fixed", hours=[1, 6])
    target = np.zeros((7, 9), dtype=np.uint8)
    target[3, 5] = 1
    figure, axes = result.compare(target, hours=6, index=1,
                                  burned_area=sample["burned_area"][1, 0], colorbar=False)
    expected = result.at(hours=6)
    known = expected.valid[1, 0].numpy()
    np.testing.assert_array_equal(np.ma.getmaskarray(axes[0].images[0].get_array()), ~known)
    np.testing.assert_allclose(axes[0].images[0].get_array().compressed(),
                               expected.probability[1, 0].numpy()[known], rtol=0, atol=0)
    np.testing.assert_array_equal(axes[0].collections[0].get_offsets(), [[5, 3]])
    assert any("6 h" in text.get_text() for text in axes[0].get_legend().get_texts())
    figure.canvas.draw()


def test_cumulative_container_rejects_mixed_cutoffs_and_wrong_horizon_metadata(checkpoint, inputs):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    first = model.predict(sample, dt_hours=1)
    third = model.predict(sample, dt_hours=3)
    with pytest.raises(ValueError, match="horizon|dt_hours"):
        CumulativePrediction(hours=(3,), _predictions=(first,))
    with pytest.raises(ValueError, match="one Prediction|horizon"):
        CumulativePrediction(hours=(1, 3), _predictions=(first,))
    shifted = replace(third, time_utc=third.time_utc + 3600)
    with pytest.raises(ValueError, match="time_utc|metadata"):
        CumulativePrediction(hours=(1, 3), _predictions=(first, shifted))


def test_cumulative_unknown_start_or_endpoint_states_and_padding_remain_unknown(checkpoint, inputs):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    sample["pixel_valid"][0, -1, -1] = False
    sample["time_valid"][1] = False
    sample["time_utc"][1] = -1
    result = model.predict_cumulative(sample, method="fixed", hours=3)
    states = np.zeros((2, 1, 7, 9), dtype=float)
    states[1, 0, 3, 5] = 1
    states[1, 0, -1, -1] = 1
    states[0, 0, 2, 2] = np.nan
    reference = _reference(sample, states, [10_000, 20_800])
    reference["pixel_valid"][:] = True  # Prediction padding still constrains the physical footprint.
    reference["burned_area_valid"][0, 0, 1, 1] = False
    reference["burned_area_valid"][1, 0, 1, 2] = False
    labels, known = result.aligned_observations(reference, hours=3)
    for row, column in [(1, 1), (1, 2), (2, 2), (6, 8)]:
        assert not known[0, 0, row, column] and np.isnan(labels[0, 0, row, column])
    assert known[0, 0, 3, 5] and labels[0, 0, 3, 5] == 1
    assert not known[1].any() and np.isnan(labels[1]).all()


@pytest.mark.parametrize("times", [[10_000, 20_801], [20_800], [10_000]])
def test_missing_exact_cutoff_or_endpoint_never_substitutes_a_nearby_state(checkpoint, inputs, times):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    sample = {**sample, **{name: sample[name][:1] for name in (
        "burned_area", "features", "feature_valid", "time_utc", "time_valid")}}
    result = model.predict_cumulative(sample, method="fixed", hours=3)
    reference = _reference(sample, np.ones((len(times), 1, 7, 9)), times)
    labels, known = result.aligned_observations(reference, hours=3)
    assert not known.any() and np.isnan(labels).all()
    figure, axes = result.compare(reference, hours=3, colorbar=False)
    assert len(axes[0].collections[0].get_offsets()) == 0
    np.testing.assert_array_equal(np.ma.getmaskarray(axes[0].images[0].get_array()),
                                  ~result.at(hours=3).valid[0, 0].numpy())
    figure.canvas.draw()


@pytest.mark.parametrize("hours", [0.5, 1.5])
def test_fractional_hour_comparison_matches_an_exact_fractional_endpoint(checkpoint, inputs, hours):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    sample = {**sample, **{name: sample[name][:1] for name in (
        "burned_area", "features", "feature_valid", "time_utc", "time_valid")}}
    result = model.predict_cumulative(sample, method="fixed", hours=hours)
    states = np.zeros((2, 1, 7, 9))
    states[:, 0, 3, 4] = 1
    states[1, 0, 3, 5] = 1
    reference = _reference(sample, states, [10_000, 10_000 + int(hours * 3600)])
    labels, known = result.aligned_observations(reference, hours=hours)
    assert known.all() and labels[0, 0, 3, 5] == 1
    assert labels[0, 0, 3, 4] == 0


def test_fractional_horizon_without_an_exact_half_hour_reference_remains_unknown(checkpoint, inputs):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    sample = {**sample, **{name: sample[name][:1] for name in (
        "burned_area", "features", "feature_valid", "time_utc", "time_valid")}}
    result = model.predict_cumulative(sample, method="fixed", hours=1.5)
    reference = _reference(sample, np.ones((3, 1, 7, 9)), [10_000, 13_600, 17_200])
    labels, known = result.aligned_observations(reference, hours=1.5)
    assert not known.any() and np.isnan(labels).all()


@pytest.mark.parametrize("hours", [1e-12, 1 / 7])
def test_subsecond_endpoints_do_not_round_or_truncate_into_integer_reference_times(checkpoint, inputs, hours):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    sample = {**sample, **{name: sample[name][:1] for name in (
        "burned_area", "features", "feature_valid", "time_utc", "time_valid")}}
    cutoff = 1_700_000_000
    sample["time_utc"][:] = cutoff
    result = model.predict_cumulative(sample, method="fixed", hours=hours)
    # Tiny offsets can round back to the cutoff at this Unix epoch. For other
    # nonintegral-second offsets, a floor timestamp is equally ineligible.
    times = [cutoff] if hours < 1e-6 else [cutoff, cutoff + int(hours * 3600)]
    reference = _reference(sample, np.zeros((len(times), 1, 7, 9)), times)
    labels, known = result.aligned_observations(reference, hours=hours)
    assert not known.any() and np.isnan(labels).all()


def test_batched_cumulative_alignment_keeps_event_times_and_padded_footprints_separate(checkpoint, inputs):
    model = load_model(checkpoint)
    single = _sample(model, inputs)
    sample = {**single, **{name: np.stack([single[name]] * 2) for name in (
        "burned_area", "features", "feature_valid", "pixel_valid")}}
    sample["affine_transform"] = np.stack([single["affine_transform"]] * 2)
    sample["epsg"] = np.array([4326, 4326])
    sample["event_id"] = ["event_A", "event_B"]
    sample["time_utc"] = np.array([[10_000, 13_600], [50_000, 53_600]])
    sample["time_valid"] = np.ones((2, 2), dtype=bool)
    sample["pixel_valid"][1, 0, -1] = False
    result = model.predict_cumulative(sample, method="fixed", hours=[1, 3])
    states = np.zeros((2, 4, 1, 7, 9))
    states[:, :, 0, 3, 4] = 1
    states[0, [0, 2], 0, 3, 5] = 1
    states[0, 2, 0, 4, 4] = 1
    states[1, [1, 3], 0, 2, 4] = 1
    states[1, 1, 0, 3, 3] = 1
    states[1, [1, 3], 0, -1, 4] = 1
    reference = _reference(sample, states, [[20_800, 10_000, 24_400, 13_600],
                                          [50_000, 64_400, 53_600, 60_800]])
    labels, known = result.aligned_observations(reference, hours=3)
    assert labels.shape == (2, 2, 1, 7, 9)
    assert labels[0, 0, 0, 3, 5] == labels[0, 1, 0, 3, 5] == 1
    assert labels[0, 0, 0, 4, 4] == 0 and labels[0, 1, 0, 4, 4] == 1
    assert labels[1, 0, 0, 2, 4] == labels[1, 1, 0, 2, 4] == 1
    assert labels[1, 0, 0, 3, 3] == 0 and labels[1, 1, 0, 3, 3] == 1
    assert not known[1, :, :, -1].any() and np.isnan(labels[1, :, :, -1]).all()
    figure, axes = result.compare(reference, hours=3, index=(1, 0), colorbar=False)
    np.testing.assert_array_equal(axes[0].collections[0].get_offsets(), [[4, 2]])
    assert axes[0].get_ylim() == (6.5, -0.5)
    figure.canvas.draw()


def test_snapshot_cumulative_alignment_needs_no_time_axis(checkpoint, inputs):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    for name in ("burned_area", "features", "feature_valid"):
        sample[name] = sample[name][0]
    sample["time_utc"] = np.array([10_000])
    sample["time_valid"] = np.array([True])
    result = model.predict_cumulative(sample, method="fixed", hours=3)
    states = np.zeros((2, 1, 7, 9))
    states[:, 0, 3, 4] = 1
    states[1, 0, 3, 5] = 1
    # A reference snapshot describes one timestamp without a time axis.
    cutoff = _reference(sample, states[0], [10_000])
    endpoint = _reference(sample, states[1], [20_800])
    # A single snapshot can represent one timestamp only, so either missing
    # the start or missing the endpoint makes the cumulative label unknown.
    for reference in (cutoff, endpoint):
        labels, known = result.aligned_observations(reference, hours=3)
        assert labels.shape == (1, 7, 9)
        assert not known.any() and np.isnan(labels).all()


def test_snapshot_cumulative_comparison_aligns_a_full_reference_timeline_without_changing_snapshot_shape(checkpoint, inputs):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    for name in ("burned_area", "features", "feature_valid"):
        sample[name] = sample[name][0]
    sample["time_utc"] = np.array([10_000])
    sample["time_valid"] = np.array([True])
    sample["pixel_valid"][0, -1] = False
    result = model.predict_cumulative(sample, method="fixed", hours=[1, 3])
    assert result.probability.shape == (2, 1, 7, 9)
    assert result.time_utc.shape == ()
    states = np.zeros((3, 1, 7, 9))
    states[:, 0, 3, 4] = 1
    states[[0, 2], 0, 2, 4] = 1  # First burn occurs in the first hour.
    states[0, 0, 3, 5] = 1       # Another first burn occurs before hour three.
    states[0, 0, -1, 5] = 1      # Reference reports a cell outside the snapshot footprint.
    reference = _reference(sample, states, [20_800, 10_000, 13_600])
    reference["pixel_valid"][:] = True
    first, first_valid = result.aligned_observations(reference, hours=1)
    third, third_valid = result.aligned_observations(reference, hours=3)
    assert first.shape == third.shape == (1, 7, 9)
    assert first[0, 2, 4] == third[0, 2, 4] == 1
    assert first[0, 3, 5] == 0 and third[0, 3, 5] == 1
    assert third[0, 3, 4] == 0
    assert not first_valid[:, -1].any() and not third_valid[:, -1].any()
    assert np.isnan(third[:, -1]).all()
    figure, axes = result.compare(reference, hours=3, colorbar=False)
    np.testing.assert_array_equal(axes[0].collections[0].get_offsets(), [[4, 2], [5, 3]])
    assert len(axes[0].images) == 2
    prior_mask = np.ma.getmaskarray(axes[0].images[1].get_array())
    expected_prior_mask = np.ones((7, 9), dtype=bool)
    expected_prior_mask[3, 4] = False
    np.testing.assert_array_equal(prior_mask, expected_prior_mask)
    assert axes[0].get_xlim() == (-0.5, 8.5)
    assert axes[0].get_ylim() == (6.5, -0.5)
    figure.canvas.draw()
    # Promotion used for reference lookup must not alter the public snapshot
    # organization or turn its scalar cutoff into a temporal dimension.
    assert result.probability.shape == (2, 1, 7, 9)
    assert result.at(hours=3).probability.shape == (1, 7, 9)
    assert result.at(hours=3).time_utc.shape == ()
    # A caller can replace the display's prior layer with an explicitly
    # aligned snapshot without changing how reference interval events align.
    explicit_prior = np.zeros((1, 7, 9), dtype=np.uint8)
    explicit_prior[0, 3, 2] = 1
    override_figure, override_axes = result.compare(
        reference, hours=3, burned_area=explicit_prior,
        burned_area_valid=np.ones_like(explicit_prior, dtype=bool), colorbar=False,
    )
    np.testing.assert_array_equal(override_axes[0].collections[0].get_offsets(), [[4, 2], [5, 3]])
    expected_override_mask = np.ones((7, 9), dtype=bool)
    expected_override_mask[3, 2] = False
    np.testing.assert_array_equal(np.ma.getmaskarray(override_axes[0].images[1].get_array()),
                                  expected_override_mask)
    override_figure.canvas.draw()


@pytest.mark.parametrize("name,value", [
    ("event_id", "other_event"), ("epsg", 5179),
    ("affine_transform", np.array([0.02, 0, 128, 0, -0.02, 38])),
    ("burned_area", np.zeros((2, 1, 7, 8))),
    ("burned_area", np.full((2, 1, 7, 9), 0.5)),
    ("burned_area_valid", np.ones((2, 1, 7, 9), dtype=int)),
    ("time_utc", np.array([10_000.0, 20_800.0])),
])
def test_cumulative_reference_rejects_incompatible_or_malformed_fields(checkpoint, inputs, name, value):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    result = model.predict_cumulative(sample, method="fixed", hours=3)
    reference = _reference(sample, np.zeros_like(sample["burned_area"]), [10_000, 20_800])
    reference[name] = value
    with pytest.raises((TypeError, ValueError)):
        result.aligned_observations(reference, hours=3)


def test_cumulative_plot_index_selects_a_prediction_time_not_a_loaded_source_time(checkpoint, inputs):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    sample = {**sample, **{name: sample[name][1:2] for name in (
        "burned_area", "features", "feature_valid", "time_utc", "time_valid")}}
    result = model.predict_cumulative(sample, method="fixed", hours=[1, 3])
    with pytest.raises(IndexError, match="Prediction.*select_time|select_time.*Prediction"):
        result.plot(hours=3, index=10, colorbar=False)
    figure, axis = result.plot(hours=3, colorbar=False)
    assert axis.images[0].get_array().shape == (7, 9)
    figure.canvas.draw()
