"""Result API, exact forecast-endpoint alignment, plotting, and sample loading."""

from copy import deepcopy
from dataclasses import replace
import json

import matplotlib
matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import numpy as np
import pytest
import torch

from tests.test_api import checkpoint, inputs
from tests.probability.test_training import hourly_training_bundle
from wildfire import Prediction, load_data, load_model, select_time


def _sample(model, inputs):
    burned, features, feature_valid = inputs
    return dict(
        burned_area=burned.copy(), features=features.copy(),
        channel_names=model.channel_names, feature_valid=feature_valid.copy(),
        affine_transform=np.array([0.02, 0, 127, 0, -0.02, 38]), epsg=4326,
        pixel_valid=np.ones((1, 7, 9), dtype=bool),
        time_utc=np.array([10_000, 13_600], dtype=np.int64),
        time_valid=np.ones(2, dtype=bool), event_id="fixture_event",
    )


def _observed(sample, targets, times):
    return dict(
        newly_burned_area=np.asarray(targets),
        newly_burned_area_valid=np.ones(np.shape(targets), dtype=bool),
        time_utc=np.asarray(times, dtype=np.int64),
        time_valid=np.ones(np.shape(times), dtype=bool),
        affine_transform=deepcopy(sample["affine_transform"]),
        epsg=deepcopy(sample["epsg"]), pixel_valid=deepcopy(sample["pixel_valid"]),
        event_id=deepcopy(sample["event_id"]),
    )


def _assert_details_equal(result, details):
    for name in ("probability", "valid", "rate", "rate_valid"):
        torch.testing.assert_close(getattr(result, name), getattr(details, name),
                                   rtol=0, atol=0, equal_nan=True)


def test_raw_prediction_returns_result_and_preserves_the_inference_contract(checkpoint, inputs):
    model = load_model(checkpoint)
    burned, features, feature_valid = inputs
    options = dict(channel_names=model.channel_names, feature_valid=feature_valid)
    details = model.predict_details(burned, features, **options)
    result = model.predict(burned, features, **options)
    assert isinstance(result, Prediction)
    _assert_details_equal(result, details)
    assert result.probability.shape == (2, 1, 7, 9)
    assert result.coordinates is None and result.time_utc is None
    assert not result.probability.requires_grad and not result.rate.requires_grad
    torch.testing.assert_close(result.probability, model.predict_proba(burned, features, **options),
                               rtol=0, atol=0, equal_nan=True)

    arrays = result.numpy()
    assert set(arrays) == {"probability", "valid", "rate", "rate_valid", "dt_hours"}
    assert arrays["valid"].dtype == arrays["rate_valid"].dtype == np.dtype(bool)
    np.testing.assert_array_equal(arrays["probability"], result.probability.numpy())
    arrays["probability"][:] = -10
    assert not torch.any(result.probability == -10)


def test_probability_plot_and_comparison_show_q_instead_of_lambda(checkpoint, inputs):
    model = load_model(checkpoint)
    original = model.predict(_sample(model, inputs))
    q = torch.full_like(original.probability, 0.2)
    rate = torch.full_like(original.rate, 5.0)
    result = replace(original, probability=q, rate=rate)
    known = original.valid[0, 0].numpy()

    figure, ax = result.plot(index=0)
    try:
        values = ax.images[0].get_array()
        np.testing.assert_array_equal(np.ma.getmaskarray(values), ~known)
        np.testing.assert_allclose(values.compressed(), q[0, 0].numpy()[known], rtol=0, atol=0)
        assert not np.any(values.compressed() == 5)
        assert ax.images[0].get_clim() == (0, 1)
        assert "q" in ax.get_title()
        assert "q" in figure.axes[-1].get_ylabel()
        assert "probability" in figure.axes[-1].get_ylabel().lower()
        figure.canvas.draw()
    finally:
        plt.close(figure)

    figure, axes = result.compare(np.zeros((7, 9)), index=0)
    try:
        values = axes[0].images[0].get_array()
        np.testing.assert_array_equal(np.ma.getmaskarray(values), ~known)
        np.testing.assert_allclose(values.compressed(), q[0, 0].numpy()[known], rtol=0, atol=0)
        assert not np.any(values.compressed() == 5)
        assert axes[0].images[0].get_clim() == (0, 1)
        assert "q" in figure.axes[-1].get_ylabel()
        assert "probability" in figure.axes[-1].get_ylabel().lower()
        figure.canvas.draw()
    finally:
        plt.close(figure)


def test_sample_prediction_and_plots_never_read_outcome_labels(checkpoint, inputs):
    model = load_model(checkpoint)
    fields = _sample(model, inputs)

    class CurrentInputs(dict):
        forbidden = {"newly_burned_area", "newly_burned_area_valid", "arrival_hours",
                     "arrival_valid", "future_labels"}

        def __getitem__(self, name):
            assert name not in self.forbidden, f"Inference read outcome field {name}"
            return super().__getitem__(name)

        def get(self, name, default=None):
            assert name not in self.forbidden, f"Inference read outcome field {name}"
            return super().get(name, default)

        def __contains__(self, name):
            assert name not in self.forbidden, f"Inference checked outcome field {name}"
            return super().__contains__(name)

    guarded = CurrentInputs(**fields, newly_burned_area=object(), arrival_hours=object())
    result = model.predict(guarded)
    _assert_details_equal(result, model.predict_sample_details(fields))
    assert result.coordinates.shape == (7, 9, 2)
    assert result.coordinates.device.type == "cpu" and result.coordinates.dtype == torch.float64
    fig, ax = result.plot(index=0, colorbar=False)
    fig.canvas.draw()
    assert ax.images[0].get_clim() == (0, 1)
    plt.close(fig)

    legacy = model.predict_sample(guarded)
    assert isinstance(legacy, tuple) and len(legacy) == 2
    torch.testing.assert_close(legacy[0], result.probability, rtol=0, atol=0, equal_nan=True)
    torch.testing.assert_close(legacy[1], result.coordinates, rtol=0, atol=0, equal_nan=True)
    burned, features, feature_valid = inputs
    raw_tuple = model.predict_coordinates(
        burned, features, channel_names=model.channel_names, feature_valid=feature_valid,
        affine_transform=fields["affine_transform"], epsg=fields["epsg"],
    )
    for actual, expected in zip(raw_tuple, legacy):
        torch.testing.assert_close(actual, expected, rtol=0, atol=0, equal_nan=True)


def test_raw_input_requires_explicit_channels_and_environment(checkpoint, inputs):
    model = load_model(checkpoint)
    burned, features, _ = inputs
    with pytest.raises(ValueError, match="channel_names"):
        model.predict(burned, features)
    with pytest.raises(TypeError, match="environmental_data"):
        model.predict(burned, channel_names=model.channel_names)


@pytest.mark.parametrize("geometry", [dict(epsg=4326), dict(affine_transform=[1, 0, 0, 0, -1, 0])])
def test_raw_prediction_rejects_partial_geometry(checkpoint, inputs, geometry):
    model = load_model(checkpoint)
    with pytest.raises(ValueError, match="affine_transform.*epsg"):
        model.predict(inputs[0], inputs[1], channel_names=model.channel_names, **geometry)


@pytest.mark.parametrize("name", ["affine_transform", "epsg"])
def test_georeferencing_masks_are_not_discarded(checkpoint, inputs, name):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    unknown = np.ma.array(sample[name], mask=True)
    masked_sample = {**sample, name: unknown}
    with pytest.raises(ValueError, match=f"{name}.*masked"):
        model.predict(masked_sample)
    observed = _observed(sample, np.zeros_like(inputs[0]), sample["time_utc"] + 3600)
    observed[name] = unknown
    with pytest.raises(ValueError, match=f"{name}.*masked"):
        model.predict(sample).aligned_observations(observed)


@pytest.mark.parametrize("override", [
    dict(environmental_data=np.zeros((2, 2, 7, 9))),
    dict(channel_names=("fixture.a", "fixture.b")),
    dict(burned_area_valid=np.ones((2, 1, 7, 9), dtype=bool)),
    dict(feature_valid=np.ones((2, 2, 7, 9), dtype=bool)),
    dict(affine_transform=[1, 0, 0, 0, -1, 0]), dict(epsg=4326),
    dict(pixel_valid=np.ones((1, 7, 9), dtype=bool)),
    dict(time_valid=np.ones(2, dtype=bool)),
])
def test_sample_rejects_ambiguous_input_overrides(checkpoint, inputs, override):
    model = load_model(checkpoint)
    with pytest.raises(ValueError, match="sample supplies"):
        model.predict(_sample(model, inputs), **override)


def test_padding_masks_invalidate_both_numeric_outputs_but_coordinates_are_static(checkpoint, inputs):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    sample["time_valid"][1] = False
    sample["time_utc"][1] = -1
    sample["pixel_valid"][0, -1, -1] = False
    result = model.predict(sample)
    support = np.broadcast_to(sample["pixel_valid"], result.probability.shape).copy()
    support &= sample["time_valid"][:, None, None, None]
    details = model.predict_details(
        sample["burned_area"], sample["features"], channel_names=sample["channel_names"],
        burned_area_valid=support,
        feature_valid=sample["feature_valid"] & np.broadcast_to(support, sample["features"].shape),
    )
    for output_name, mask_name in (("probability", "valid"), ("rate", "rate_valid")):
        expected_mask = getattr(details, mask_name).numpy() & support
        np.testing.assert_array_equal(getattr(result, mask_name).numpy(), expected_mask)
        values = getattr(result, output_name).numpy()
        assert np.isnan(values[~expected_mask]).all()
        np.testing.assert_array_equal(values[expected_mask], getattr(details, output_name).numpy()[expected_mask])
    assert torch.isnan(result.coordinates[-1, -1]).all()
    assert torch.isfinite(result.coordinates[2, 2]).all()
    unpadded = deepcopy(sample)
    unpadded["time_valid"][:] = True
    unpadded["time_utc"][:] = [10_000, 13_600]
    torch.testing.assert_close(result.coordinates, model.predict(unpadded).coordinates,
                               rtol=0, atol=0, equal_nan=True)
    arrays = result.numpy()
    np.testing.assert_array_equal(arrays["time_utc"], [10_000, -1])
    assert arrays["coordinates"].shape == (7, 9, 2)


def test_spatial_padding_masks_source_cells_before_neighbor_inference(checkpoint, inputs):
    model = load_model(checkpoint)
    burned, features, feature_valid = inputs
    spatial = np.ones((1, 7, 9), dtype=bool)
    spatial[0, 3, 4] = False  # This stored burned value is padding, not a source.
    ordinary = model.predict(burned, features, channel_names=model.channel_names,
                             feature_valid=feature_valid)
    padded = model.predict(burned, features, channel_names=model.channel_names,
                           feature_valid=feature_valid, pixel_valid=spatial)
    assert ordinary.valid[:, 0, 3, 5].all()
    assert not padded.valid[:, 0, 3, 5].any()
    assert torch.isnan(padded.probability[:, 0, 3, 5]).all()
    source_mask = np.broadcast_to(spatial, burned.shape).copy()
    expected = model.predict_details(
        burned, features, channel_names=model.channel_names,
        burned_area_valid=source_mask,
        feature_valid=feature_valid & np.broadcast_to(spatial, features.shape),
    )
    _assert_details_equal(padded, expected)


@pytest.mark.parametrize("name,value,error", [
    ("time_valid", np.array([1, 0]), ValueError),
    ("time_valid", np.array([True]), ValueError),
    ("pixel_valid", np.ones((1, 7, 9), dtype=int), TypeError),
    ("pixel_valid", np.ones((7, 8), dtype=bool), ValueError),
    ("time_utc", np.array([10_000.0, 13_600.0]), ValueError),
    ("time_utc", np.array([10_000]), ValueError),
    ("time_utc", np.array([10_000, -1]), ValueError),
])
def test_result_metadata_validates_mask_types_shapes_and_integer_times(checkpoint, inputs, name, value, error):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    sample[name] = value
    with pytest.raises(error):
        model.predict(sample)


def test_hourly_comparison_uses_the_next_endpoint_and_leaves_last_endpoint_missing(checkpoint, inputs):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    labels = np.zeros_like(sample["burned_area"])
    labels[1, 0, 3, 3] = 1
    observed = _observed(sample, labels, sample["time_utc"])
    result = model.predict(sample)
    aligned, valid = result.aligned_observations(observed)
    np.testing.assert_array_equal(aligned[0], labels[1])
    assert valid[0].all()
    assert not valid[1].any() and np.isnan(aligned[1]).all()
    assert aligned[0, 0, 3, 3] == 1 and labels[0, 0, 3, 3] == 0
    # The dataset's cumulative-state validity is the documented fallback.
    observed["burned_area_valid"] = observed.pop("newly_burned_area_valid")
    fallback, fallback_valid = result.aligned_observations(observed)
    np.testing.assert_array_equal(fallback, aligned)
    np.testing.assert_array_equal(fallback_valid, valid)


def test_separate_endpoint_samples_and_reference_masks_align_exactly(checkpoint, inputs):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    result = model.predict(sample)
    labels = np.zeros_like(sample["burned_area"])
    labels[0, 0, 3, 3] = 1
    labels[1, 0, 3, 5] = 1
    observed = _observed(sample, labels, sample["time_utc"] + 3600)
    observed["newly_burned_area_valid"][0, 0, 1, 1] = False
    observed["pixel_valid"][0, 2, 1] = False
    labels[1, 0, 1, 2] = np.nan
    aligned, valid = result.aligned_observations(observed)
    assert aligned[0, 0, 3, 3] == 1 and aligned[1, 0, 3, 5] == 1
    assert not valid[0, 0, 1, 1] and np.isnan(aligned[0, 0, 1, 1])
    assert not valid[:, 0, 2, 1].any() and np.isnan(aligned[:, 0, 2, 1]).all()
    assert not valid[1, 0, 1, 2] and np.isnan(aligned[1, 0, 1, 2])
    np.testing.assert_array_equal(valid[:, 0, 3, 3], [True, True])


@pytest.mark.parametrize("times,expected", [
    ([13_600, 17_201], [True, False]),
    ([17_200], [False, True]),
    ([17_200, 13_600], [True, True]),
])
def test_alignment_uses_exact_times_without_interpolation_or_index_pairing(checkpoint, inputs, times, expected):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    labels = np.zeros((len(times), 1, 7, 9), dtype=float)
    for index in range(len(times)):
        labels[index, 0, 3, index + 2] = 1
    observed = _observed(sample, labels, times)
    aligned, valid = model.predict(sample).aligned_observations(observed)
    np.testing.assert_array_equal(valid[:, 0, 3, 3], expected)
    for index, known in enumerate(expected):
        if known:
            endpoint_index = times.index(int(sample["time_utc"][index]) + 3600)
            np.testing.assert_array_equal(aligned[index], labels[endpoint_index])
        else:
            assert np.isnan(aligned[index]).all()


def test_irregular_prediction_times_align_to_their_own_endpoints(checkpoint, inputs):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    sample["time_utc"][:] = [10_000, 20_000]
    labels = np.zeros_like(sample["burned_area"])
    labels[1, 0, 3, 3] = 1
    observed = _observed(sample, labels, [13_600, 23_600])
    aligned, valid = model.predict(sample).aligned_observations(observed)
    np.testing.assert_array_equal(aligned, labels)
    assert valid.all()


def test_duplicate_valid_reference_times_are_rejected_and_padded_times_are_ignored(checkpoint, inputs):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    labels = np.zeros_like(sample["burned_area"])
    labels[0, 0, 3, 3] = 1
    observed = _observed(sample, labels, [13_600, 13_600])
    result = model.predict(sample)
    with pytest.raises(ValueError, match="unique"):
        result.aligned_observations(observed)
    observed["time_valid"][1] = False
    aligned, valid = result.aligned_observations(observed)
    assert aligned[0, 0, 3, 3] == 1 and valid[0].all()
    assert not valid[1].any()
    sample["time_valid"][0] = False
    aligned, valid = model.predict(sample).aligned_observations(observed)
    assert not valid.any() and np.isnan(aligned).all()


def test_batch_alignment_keeps_events_grids_and_times_separate(checkpoint, inputs):
    model = load_model(checkpoint)
    single = _sample(model, inputs)
    sample = dict(
        burned_area=np.stack([single["burned_area"]] * 2),
        features=np.stack([single["features"]] * 2),
        feature_valid=np.stack([single["feature_valid"]] * 2),
        channel_names=model.channel_names,
        affine_transform=np.array([[0.02, 0, 127, 0, -0.02, 38],
                                   [0.03, 0, -120, 0, -0.03, 40]]),
        epsg=np.array([4326, 4326]),
        pixel_valid=np.ones((2, 1, 7, 9), dtype=bool),
        time_utc=np.array([[10_000, 13_600], [50_000, 53_600]]),
        time_valid=np.ones((2, 2), dtype=bool), event_id=["event_A", "event_B"],
    )
    sample["pixel_valid"][1, 0, -1, :] = False
    labels = np.zeros_like(sample["burned_area"])
    labels[0, 0, 0, 3, 2] = 1
    labels[0, 1, 0, 3, 3] = 1
    labels[1, 0, 0, 3, 4] = 1
    labels[1, 1, 0, 3, 5] = 1
    observed = _observed(sample, labels, [[17_200, 13_600], [53_600, 57_200]])
    result = model.predict(sample)
    aligned, valid = result.aligned_observations(observed)
    np.testing.assert_array_equal(aligned[0, 0], labels[0, 1])
    np.testing.assert_array_equal(aligned[0, 1], labels[0, 0])
    np.testing.assert_array_equal(aligned[1, :, :, :-1], labels[1, :, :, :-1])
    assert not valid[1, :, :, -1].any() and np.isnan(aligned[1, :, :, -1]).all()
    assert result.coordinates.shape == (2, 7, 9, 2)
    torch.testing.assert_close(result.coordinates[0, 0, 0], torch.tensor([37.99, 127.01], dtype=torch.float64))
    torch.testing.assert_close(result.coordinates[1, 0, 0], torch.tensor([39.985, -119.985], dtype=torch.float64))
    assert torch.isnan(result.coordinates[1, -1]).all()
    observed["event_id"].reverse()
    with pytest.raises(ValueError, match="event_id"):
        result.aligned_observations(observed)


@pytest.mark.parametrize("name,value,match", [
    ("event_id", "other_event", "event_id"),
    ("affine_transform", np.array([0.02, 0, 128, 0, -0.02, 38]), "affine_transform"),
    ("epsg", 5179, "epsg"),
    ("time_utc", np.array([13_600.0, 17_200.0]), "integer Unix"),
    ("time_utc", np.array([13_600, -1]), "nonnegative"),
    ("newly_burned_area", np.zeros((2, 1, 7, 8)), "spatial/channel"),
    ("newly_burned_area_valid", np.ones((2, 1, 7, 9), dtype=int), "boolean mask"),
])
def test_sample_alignment_rejects_incompatible_metadata(checkpoint, inputs, name, value, match):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    observed = _observed(sample, np.zeros_like(sample["burned_area"]), [13_600, 17_200])
    observed[name] = value
    with pytest.raises(ValueError, match=match):
        model.predict(sample).aligned_observations(observed)


def test_known_reference_targets_must_be_binary_and_have_validity(checkpoint, inputs):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    labels = np.zeros_like(sample["burned_area"])
    labels[0, 0, 3, 3] = 0.5
    observed = _observed(sample, labels, [13_600, 17_200])
    result = model.predict(sample)
    with pytest.raises(ValueError, match="exactly 0 or 1"):
        result.aligned_observations(observed)
    observed["newly_burned_area_valid"][0, 0, 3, 3] = False
    aligned, valid = result.aligned_observations(observed)
    assert not valid[0, 0, 3, 3] and np.isnan(aligned[0, 0, 3, 3])
    observed.pop("newly_burned_area_valid")
    with pytest.raises(ValueError, match="require.*valid"):
        result.aligned_observations(observed)


@pytest.mark.parametrize("duration", [0.5, 2.0, np.array([1.0, 2.0])])
def test_nonhourly_horizon_requires_explicit_interval_targets(checkpoint, inputs, duration):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    observed = _observed(sample, np.zeros_like(sample["burned_area"]), [13_600, 17_200])
    result = model.predict(sample, dt_hours=duration)
    with pytest.raises(ValueError, match="dt_hours=1"):
        result.aligned_observations(observed)
    with pytest.raises(ValueError, match="dt_hours=1"):
        result.compare(observed, index=0)
    fig, axes = result.compare(np.zeros((7, 9)), index=0, mode="overlay", colorbar=False)
    fig.canvas.draw()
    assert len(axes) == 1
    plt.close(fig)


def test_sample_comparison_requires_saved_times_and_its_own_masks(checkpoint, inputs):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    observed = _observed(sample, np.zeros_like(sample["burned_area"]), [13_600, 17_200])
    sample.pop("time_utc")
    with pytest.raises(ValueError, match="time_utc"):
        model.predict(sample).aligned_observations(observed)
    sample["time_utc"] = np.array([10_000, 13_600])
    with pytest.raises(ValueError, match="own validity"):
        model.predict(sample).compare(observed, observed_valid=np.ones((7, 9), dtype=bool), index=0)


@pytest.mark.parametrize("mode,count", [("both", 3), ("side_by_side", 2), ("overlay", 1)])
def test_sample_comparison_draws_all_modes_with_aligned_outcomes(checkpoint, inputs, mode, count):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    labels = np.zeros_like(sample["burned_area"])
    labels[1, 0, 3, 5] = 1
    observed = _observed(sample, labels, sample["time_utc"])
    result = model.predict(sample)
    assert result.valid[0, 0, 3, 5]
    fig, axes = result.compare(observed, index=0, mode=mode, colorbar=False)
    fig.canvas.draw()
    assert len(axes) == count
    if mode != "overlay":
        assert axes[0].images[0].get_array()[3, 5] == 1
    if mode != "side_by_side":
        np.testing.assert_array_equal(axes[-1].collections[0].get_offsets(), [[5, 3]])
    plt.close(fig)


def test_default_comparison_combines_exact_cutoff_burns_and_next_hour_new_burns(checkpoint, inputs):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    # Deliberately reorder reference rows. A matching array index must never
    # substitute for either the cutoff timestamp or its next-hour endpoint.
    reference_times = [17_200, 10_000, 13_600]
    labels = np.zeros((3, 1, 7, 9), dtype=float)
    labels[0, 0, 3, 5] = 1
    labels[2, 0, 2, 2] = 1  # Available reference event outside model coverage.
    observed = _observed(sample, labels, reference_times)
    prior = np.zeros_like(labels)
    prior[1, 0, 3, 4] = 1
    prior[2, 0, 3, 4:6] = 1
    prior[0, 0, 3, 4:7] = 1
    observed["burned_area"] = prior
    observed["burned_area_valid"] = np.ones(prior.shape, dtype=bool)
    selected_sample = dict(sample)
    for name in ("burned_area", "features", "feature_valid", "time_utc", "time_valid"):
        selected_sample[name] = sample[name][1:2]
    result = model.predict(selected_sample)

    aligned_prior, prior_valid = result.aligned_burned_area(observed)
    aligned_new, new_valid = result.aligned_observations(observed)
    np.testing.assert_array_equal(aligned_prior[0], prior[2])
    np.testing.assert_array_equal(aligned_new[0], labels[0])
    assert prior_valid.all() and new_valid.all()
    figure, axes = result.compare(observed, colorbar=False)
    try:
        assert len(axes) == 1 and len(axes[0].images) == 2
        np.testing.assert_array_equal(np.ma.getmaskarray(axes[0].images[0].get_array()),
                                      ~result.valid[0, 0].numpy())
        np.testing.assert_array_equal(np.ma.getmaskarray(axes[0].images[1].get_array()),
                                      prior[2, 0] != 1)
        np.testing.assert_array_equal(axes[0].collections[0].get_offsets(), [[5, 3]])
        figure.canvas.draw()
    finally:
        plt.close(figure)

    first = model.predict(sample)
    assert not first.valid[0, 0, 2, 2]
    figure, axes = first.compare(observed, index=0, colorbar=False)
    try:
        # The reference event remains visible even though its probability is
        # unavailable. The cutoff layer uses the earlier cumulative state.
        np.testing.assert_array_equal(axes[0].collections[0].get_offsets(), [[2, 2]])
        np.testing.assert_array_equal(np.ma.getmaskarray(axes[0].images[1].get_array()),
                                      prior[1, 0] != 1)
    finally:
        plt.close(figure)


def test_missing_cutoff_does_not_use_future_burns_or_hide_probabilities(checkpoint, inputs):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    sample = {**sample, **{name: sample[name][:1] for name in (
        "burned_area", "features", "feature_valid", "time_utc", "time_valid")}}
    result = model.predict(sample)
    future = np.ones((1, 1, 7, 9), dtype=float)
    observed = _observed(sample, np.zeros_like(future), [13_600])
    observed["burned_area"] = future
    observed["burned_area_valid"] = np.ones_like(future, dtype=bool)
    prior, valid = result.aligned_burned_area(observed)
    assert not valid.any() and np.isnan(prior).all()
    figure, axes = result.compare(observed, colorbar=False)
    try:
        assert len(axes) == 1
        assert np.ma.getmaskarray(axes[0].images[1].get_array()).all()
        np.testing.assert_array_equal(np.ma.getmaskarray(axes[0].images[0].get_array()),
                                      ~result.valid[0, 0].numpy())
        figure.canvas.draw()
    finally:
        plt.close(figure)


def test_missing_next_hour_keeps_the_cutoff_layer_and_probability_background(checkpoint, inputs):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    observed = _observed(sample, np.zeros_like(sample["burned_area"]), sample["time_utc"])
    observed["burned_area"] = sample["burned_area"]
    observed["burned_area_valid"] = np.ones_like(sample["burned_area"], dtype=bool)
    result = model.predict(sample)
    figure, axes = result.compare(observed, index=-1, colorbar=False)
    try:
        assert len(axes) == 1 and len(axes[0].collections[0].get_offsets()) == 0
        np.testing.assert_array_equal(np.ma.getmaskarray(axes[0].images[0].get_array()),
                                      ~result.valid[1, 0].numpy())
        np.testing.assert_array_equal(np.ma.getmaskarray(axes[0].images[1].get_array()),
                                      sample["burned_area"][1, 0] != 1)
    finally:
        plt.close(figure)


def test_prior_alignment_respects_reference_masks_time_padding_and_prediction_support(checkpoint, inputs):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    sample["time_valid"][1] = False
    sample["time_utc"][1] = -1
    sample["pixel_valid"][0, -1, -1] = False
    result = model.predict(sample)
    prior = np.ma.array(np.ones_like(sample["burned_area"]), mask=False)
    prior.mask[0, 0, 1, 1] = True
    prior[0, 0, 1, 2] = np.nan
    observed = _observed(sample, np.zeros_like(sample["burned_area"]), [10_000, 10_000])
    observed["time_valid"][1] = False  # Padded duplicate must be ignored.
    observed["burned_area"] = prior
    observed["burned_area_valid"] = np.ones(prior.shape, dtype=bool)
    observed["burned_area_valid"][0, 0, 1, 3] = False
    observed["pixel_valid"][0, 2, 2] = False
    aligned, valid = result.aligned_burned_area(observed)
    assert not valid[1].any() and np.isnan(aligned[1]).all()
    for row, column in [(1, 1), (1, 2), (1, 3), (2, 2), (6, 8)]:
        assert not valid[0, 0, row, column]
        assert np.isnan(aligned[0, 0, row, column])
    assert valid[0, 0, 3, 4] and aligned[0, 0, 3, 4] == 1
    observed["time_valid"][:] = True
    with pytest.raises(ValueError, match="unique"):
        result.aligned_burned_area(observed)


def test_reference_layers_exclude_prediction_grid_padding_but_keep_physical_unknown_probabilities(checkpoint, inputs):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    sample["pixel_valid"][0, -1, -1] = False
    sample["feature_valid"][:, :, 3, 5] = False
    result = model.predict(sample)
    assert not result.valid[0, 0, 2, 2] and not result.valid[0, 0, 3, 5]

    labels = np.zeros_like(sample["burned_area"])
    labels[1, 0, 3, 5] = 1
    labels[1, 0, -1, -1] = 1
    observed = _observed(sample, labels, sample["time_utc"])
    # A larger reference footprint must not treat the prediction's padded
    # array cells as physical cells in the displayed event grid.
    observed["pixel_valid"][:] = True
    prior = np.zeros_like(labels)
    prior[0, 0, 2, 2] = 1
    prior[0, 0, -1, -1] = 1
    observed["burned_area"] = prior
    observed["burned_area_valid"] = np.ones_like(prior, dtype=bool)

    aligned_prior, prior_valid = result.aligned_burned_area(observed)
    aligned_new, new_valid = result.aligned_observations(observed)
    assert not prior_valid[0, 0, -1, -1] and np.isnan(aligned_prior[0, 0, -1, -1])
    assert not new_valid[0, 0, -1, -1] and np.isnan(aligned_new[0, 0, -1, -1])
    assert prior_valid[0, 0, 2, 2] and aligned_prior[0, 0, 2, 2] == 1
    assert new_valid[0, 0, 3, 5] and aligned_new[0, 0, 3, 5] == 1

    figure, axes = result.compare(observed, index=0, colorbar=False)
    try:
        prior_mask = np.ma.getmaskarray(axes[0].images[1].get_array())
        assert prior_mask[-1, -1] and not prior_mask[2, 2]
        np.testing.assert_array_equal(axes[0].collections[0].get_offsets(), [[5, 3]])
        assert np.ma.getmaskarray(axes[0].images[0].get_array())[3, 5]
        figure.canvas.draw()
    finally:
        plt.close(figure)


def test_prediction_comparison_outlines_its_loaded_footprint_and_keeps_full_spatial_extent(checkpoint, inputs):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    sample["pixel_valid"][0, :, -1] = False
    result = model.predict(sample)
    target = np.zeros((7, 9), dtype=np.uint8)
    target[3, 5] = 1
    figure, axes = result.compare(target, index=0, colorbar=False)
    try:
        assert len(axes[0].patches) == 1
        vertices = axes[0].patches[0].get_path().vertices
        # The loaded footprint ends at column 7's outer edge, while plotting
        # retains all nine matrix columns and all seven matrix rows.
        assert np.min(vertices[:, 0]) == -0.5
        assert np.max(vertices[:, 0]) == 7.5
        assert np.min(vertices[:, 1]) == -0.5
        assert np.max(vertices[:, 1]) == 6.5
        assert axes[0].get_xlim() == (-0.5, 8.5)
        assert axes[0].get_ylim() == (6.5, -0.5)
        figure.canvas.draw()
    finally:
        plt.close(figure)


def test_prior_alignment_keeps_batch_event_cutoff_and_spatial_padding_separate(checkpoint, inputs):
    model = load_model(checkpoint)
    single = _sample(model, inputs)
    sample = {**single, **{name: np.stack([single[name]] * 2) for name in (
        "burned_area", "features", "feature_valid", "pixel_valid")}}
    sample["affine_transform"] = np.stack([single["affine_transform"]] * 2)
    sample["epsg"] = np.array([4326, 4326])
    sample["event_id"] = ["event_A", "event_B"]
    sample["time_utc"] = np.array([[10_000, 13_600], [50_000, 53_600]])
    sample["time_valid"] = np.ones((2, 2), dtype=bool)
    sample["time_valid"][1, 1] = False
    sample["time_utc"][1, 1] = -1
    sample["pixel_valid"][1, 0, -1] = False
    result = model.predict(sample)
    prior = np.zeros_like(sample["burned_area"])
    prior[0, 0, 0, 3, 2] = 1
    prior[0, 1, 0, 3, 3] = 1
    prior[1, 0, 0, 3, 4] = 1
    prior[1, 0, 0, -1, 4] = 1
    observed = _observed(sample, np.zeros_like(prior), [[13_600, 10_000], [50_000, 53_600]])
    observed["burned_area"] = prior
    observed["burned_area_valid"] = np.ones_like(prior, dtype=bool)
    aligned, valid = result.aligned_burned_area(observed)
    np.testing.assert_array_equal(aligned[0, 0], prior[0, 1])
    np.testing.assert_array_equal(aligned[0, 1], prior[0, 0])
    assert aligned[1, 0, 0, 3, 4] == 1
    assert not valid[1, 0, :, -1].any()
    assert not valid[1, 1].any() and np.isnan(aligned[1, 1]).all()
    figure, axes = result.compare(observed, index=(1, 0), colorbar=False)
    try:
        mask = np.ma.getmaskarray(axes[0].images[1].get_array())
        assert not mask[3, 4] and mask[-1].all()
        assert len(axes[0].patches) == 1
        vertices = axes[0].patches[0].get_path().vertices
        assert np.min(vertices[:, 1]) == -0.5
        assert np.max(vertices[:, 1]) == 5.5
        assert axes[0].get_ylim() == (6.5, -0.5)
        figure.canvas.draw()
    finally:
        plt.close(figure)
    observed["event_id"].reverse()
    with pytest.raises(ValueError, match="event_id"):
        result.aligned_burned_area(observed)


@pytest.mark.parametrize("name,value", [
    ("burned_area", np.zeros((2, 1, 7, 8))),
    ("burned_area", np.full((2, 1, 7, 9), 0.5)),
    ("burned_area_valid", np.ones((2, 1, 7, 9), dtype=int)),
    ("time_utc", np.array([10_000.0, 13_600.0])),
    ("affine_transform", np.array([0.02, 0, 128, 0, -0.02, 38])),
    ("epsg", 5179),
])
def test_prior_alignment_rejects_mismatched_geometry_and_malformed_known_fields(checkpoint, inputs, name, value):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    observed = _observed(sample, np.zeros_like(sample["burned_area"]), sample["time_utc"])
    observed["burned_area"] = sample["burned_area"]
    observed["burned_area_valid"] = np.ones_like(sample["burned_area"], dtype=bool)
    observed[name] = value
    with pytest.raises((TypeError, ValueError)):
        model.predict(sample).aligned_burned_area(observed)


def test_cutoff_state_alignment_is_independent_of_forecast_duration_and_handles_snapshots(checkpoint, inputs):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    for name in ("burned_area", "features", "feature_valid"):
        sample[name] = sample[name][0]
    sample["time_utc"] = np.array([10_000])
    sample["time_valid"] = np.array([True])
    observed = _observed(sample, np.zeros_like(sample["burned_area"]), [10_000])
    observed["burned_area"] = sample["burned_area"]
    observed["burned_area_valid"] = np.ones_like(sample["burned_area"], dtype=bool)
    result = model.predict(sample, dt_hours=2)
    aligned, valid = result.aligned_burned_area(observed)
    assert result.probability.shape == (1, 7, 9)
    np.testing.assert_array_equal(aligned, sample["burned_area"])
    assert valid.all()


@pytest.mark.parametrize("prior_shape", ["selected", "full"])
def test_explicit_selected_targets_can_include_selected_or_full_prior_states(checkpoint, inputs, prior_shape):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    result = model.predict(sample)
    prior = sample["burned_area"] if prior_shape == "full" else sample["burned_area"][1, 0]
    valid = np.ones_like(prior, dtype=bool)
    figure, axes = result.compare(np.zeros((7, 9)), index=1, burned_area=prior,
                                  burned_area_valid=valid, colorbar=False)
    try:
        assert len(axes) == 1 and len(axes[0].images) == 2
        np.testing.assert_array_equal(np.ma.getmaskarray(axes[0].images[1].get_array()),
                                      sample["burned_area"][1, 0] != 1)
        figure.canvas.draw()
    finally:
        plt.close(figure)


def test_explicit_2d_target_compares_the_selected_probability_matrix(checkpoint, inputs):
    model = load_model(checkpoint)
    result = model.predict(_sample(model, inputs))
    target = np.zeros((7, 9), dtype=np.uint8)
    target[3, 5] = 1
    known = np.ones_like(target, dtype=bool)
    known[3, 5] = False
    assert result.valid[1, 0, 3, 5]
    fig, axes = result.compare(target, observed_valid=known, index=1, mode="both", colorbar=False)
    fig.canvas.draw()
    image = axes[1].images[0].get_array()
    np.testing.assert_array_equal(np.ma.getmaskarray(image), ~result.valid[1, 0].numpy())
    np.testing.assert_allclose(image.compressed(), result.probability[1, 0].numpy()[result.valid[1, 0].numpy()], rtol=0, atol=0)
    assert len(axes[2].collections[0].get_offsets()) == 0
    assert not np.ma.getmaskarray(axes[2].images[0].get_array())[3, 5]
    plt.close(fig)
    with pytest.raises(ValueError, match="ambiguous"):
        result.compare(target, colorbar=False)
    with pytest.raises(ValueError, match="binary"):
        result.compare(np.full((7, 9), 0.5), index=1, colorbar=False)
    fig, axes = result.compare(np.zeros(result.probability.shape), index=1, colorbar=False)
    fig.canvas.draw()
    assert len(axes) == 1
    plt.close(fig)


def test_snapshot_alignment_accepts_one_timestamp_without_a_time_axis(checkpoint, inputs):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    for name in ("burned_area", "features", "feature_valid"):
        sample[name] = sample[name][0]
    sample["time_utc"] = np.array([10_000])
    sample["time_valid"] = np.array([True])
    labels = np.zeros_like(sample["burned_area"])
    labels[0, 3, 3] = 1
    observed = _observed(sample, labels, [13_600])
    result = model.predict(sample)
    aligned, valid = result.aligned_observations(observed)
    assert result.probability.shape == (1, 7, 9)
    assert result.time_utc.shape == () and result.coordinates.shape == (7, 9, 2)
    np.testing.assert_array_equal(aligned, labels)
    assert valid.all()


@pytest.fixture
def data_model(checkpoint, tmp_path):
    from tests.loader.test_dataset import bundle

    root = bundle.__wrapped__(tmp_path / "data")
    saved = torch.load(checkpoint, weights_only=True)
    saved["contract"]["channels"] = ["terrain.elevation_m", "weather.temperature_2m"]
    path = tmp_path / "data-model.pt"
    torch.save(saved, path)
    return load_model(path), root


def test_independent_full_timeline_is_projected_to_the_model_channel_schema(data_model):
    model, root = data_model
    with load_data(root, events=["KR_TEST"], sequence_length=None) as dataset:
        sample = dataset[0]
        assert sample["features"].shape[0] == 3
        assert len(sample["channel_names"]) > len(model.channel_names)
    indices = [sample["channel_names"].index(name) for name in model.channel_names]
    result = model.predict(sample)
    details = model.predict_details(
        sample["burned_area"], sample["features"][:, indices],
        channel_names=model.channel_names, burned_area_valid=sample["burned_area_valid"],
        feature_valid=sample["feature_valid"][:, indices],
    )
    _assert_details_equal(result, details)
    assert result.probability.shape == (3, 1, 2, 3)
    assert sample["channel_names"] == dataset.channel_names
    assert not dataset._readers


def test_source_timeline_index_is_selected_before_predicting_and_plotting_one_time(data_model):
    model, root = data_model
    with load_data(root, events=["KR_TEST"], sequence_length=None) as dataset:
        timeline = dataset[0]
    # The loaded index is 1, while the resulting prediction has one local time.
    sample = select_time(timeline, index=1)
    result = model.predict(sample)
    assert result.probability.shape == (1, 1, 2, 3)
    np.testing.assert_array_equal(result.time_utc, timeline["time_utc"][1:2])
    fig, ax = result.plot(colorbar=False)
    try:
        fig.canvas.draw()
        np.testing.assert_array_equal(np.ma.getmaskarray(ax.images[0].get_array()),
                                      ~result.valid[0, 0].numpy())
        np.testing.assert_allclose(ax.images[0].get_array().compressed(),
                                   result.probability[0, 0].numpy()[result.valid[0, 0].numpy()],
                                   rtol=0, atol=0)
    finally:
        plt.close(fig)
    targets, target_valid = result.aligned_observations(timeline)
    expected_valid = timeline["burned_area_valid"][2:3].numpy()
    np.testing.assert_array_equal(target_valid, expected_valid)
    np.testing.assert_array_equal(targets[expected_valid],
                                  timeline["newly_burned_area"][2:3].numpy()[expected_valid])
    fig, axes = result.compare(timeline, mode="both", colorbar=False)
    try:
        fig.canvas.draw()
        assert len(axes) == 3
        displayed = axes[0].images[0].get_array()
        np.testing.assert_array_equal(np.ma.getmaskarray(displayed), ~expected_valid[0, 0])
        np.testing.assert_array_equal(displayed.compressed(), targets[0, 0][expected_valid[0, 0]])
    finally:
        plt.close(fig)
    assert timeline["features"].shape[0] == 3


def test_prediction_plot_index_selects_prediction_time_and_explains_out_of_bounds_source_indices(data_model):
    model, root = data_model
    with load_data(root, events=["KR_TEST"], sequence_length=None) as dataset:
        timeline = dataset[0]
    complete = model.predict(timeline)
    fig, ax = complete.plot(index=1, colorbar=False)
    try:
        fig.canvas.draw()
        np.testing.assert_array_equal(np.ma.getmaskarray(ax.images[0].get_array()),
                                      ~complete.valid[1, 0].numpy())
        np.testing.assert_allclose(ax.images[0].get_array().compressed(),
                                   complete.probability[1, 0].numpy()[complete.valid[1, 0].numpy()],
                                   rtol=0, atol=0)
    finally:
        plt.close(fig)
    selected = model.predict(select_time(timeline, index=1))
    for index in (1, 48):
        with pytest.raises(IndexError, match="Prediction.*select_time|select_time.*Prediction"):
            selected.plot(index=index, colorbar=False)
        with pytest.raises(IndexError, match="Prediction.*select_time|select_time.*Prediction"):
            selected.compare(timeline, index=index, colorbar=False)


@pytest.mark.parametrize("backend", ["numpy", "torch"])
def test_named_channel_superset_and_reordering_preserve_features_masks_and_inputs(checkpoint, inputs, backend):
    model = load_model(checkpoint)
    original = _sample(model, inputs)
    expected = model.predict(original)
    features = original["features"]
    masks = original["feature_valid"]
    sample = dict(original)
    sample["features"] = np.concatenate([
        np.full_like(features[:, :1], np.nan), features[:, 1:2],
        features[:, :1], np.full_like(features[:, :1], 999_999),
    ], axis=1)
    sample["feature_valid"] = np.concatenate([
        np.zeros_like(masks[:, :1]), masks[:, 1:2], masks[:, :1],
        np.zeros_like(masks[:, :1]),
    ], axis=1)
    sample["channel_names"] = ("unused.left", "fixture.b", "fixture.a", "unused.right")
    if backend == "torch":
        sample["features"] = torch.from_numpy(sample["features"])
        sample["feature_valid"] = torch.from_numpy(sample["feature_valid"])
    input_features = sample["features"]
    input_mask = sample["feature_valid"]
    actual = model.predict(sample)
    _assert_details_equal(actual, expected)
    torch.testing.assert_close(actual.coordinates, expected.coordinates, rtol=0, atol=0, equal_nan=True)
    assert sample["features"] is input_features and sample["feature_valid"] is input_mask
    assert sample["channel_names"] == ("unused.left", "fixture.b", "fixture.a", "unused.right")
    assert sample["features"].shape == (2, 4, 7, 9)
    assert not actual.valid[0, 0, 2, 2]


def test_named_projection_preserves_batch_and_time_axes(checkpoint, inputs):
    model = load_model(checkpoint)
    original = _sample(model, inputs)
    for name in ("features", "feature_valid", "burned_area", "pixel_valid", "time_utc", "time_valid"):
        original[name] = np.stack([original[name], original[name]])
    original["affine_transform"] = np.stack([original["affine_transform"]] * 2)
    original["epsg"] = np.array([4326, 4326])
    original["event_id"] = ["event_A", "event_B"]
    sample = dict(original)
    sample["features"] = original["features"][:, :, ::-1].copy()
    sample["feature_valid"] = original["feature_valid"][:, :, ::-1].copy()
    sample["channel_names"] = model.channel_names[::-1]
    actual = model.predict(sample)
    expected = model.predict(original)
    _assert_details_equal(actual, expected)
    assert actual.probability.shape == (2, 2, 1, 7, 9)
    assert actual.time_utc.shape == (2, 2)


@pytest.mark.parametrize("names", [
    ("fixture.a", "other"), ("fixture.a", "fixture.a"),
    ("fixture.a",), ("fixture.a", "fixture.b", "extra"),
])
def test_named_projection_rejects_missing_duplicate_or_mismatched_channel_schema(checkpoint, inputs, names):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    sample["channel_names"] = names
    with pytest.raises(ValueError, match="channel|schema"):
        model.predict(sample)


def test_named_projection_rejects_a_mask_that_omits_extra_channels(checkpoint, inputs):
    model = load_model(checkpoint)
    sample = _sample(model, inputs)
    sample["features"] = np.concatenate([sample["features"], sample["features"][:, :1]], axis=1)
    sample["channel_names"] = (*model.channel_names, "extra")
    with pytest.raises(ValueError, match="mask|shape|feature_valid"):
        model.predict(sample)


def test_raw_prediction_retains_strict_saved_channel_order(checkpoint, inputs):
    model = load_model(checkpoint)
    burned, features, masks = inputs
    with pytest.raises(ValueError, match="channel"):
        model.predict(burned, features[:, ::-1].copy(),
                      channel_names=model.channel_names[::-1], feature_valid=masks[:, ::-1].copy())
    with pytest.raises(ValueError, match="channel"):
        model.predict(burned, np.concatenate([features, features[:, :1]], axis=1),
                      channel_names=(*model.channel_names, "extra"))


@pytest.fixture
def categorical_model(tmp_path):
    from tests.probability.test_categorical_training import metadata
    from wildfire.models import EnvironmentConditionedConvolution

    torch.manual_seed(97)
    network = EnvironmentConditionedConvolution(4, kernel_size=3, hidden_channels=4)
    contract = metadata(tmp_path)
    contract.update(format_version=1, architecture=type(network).__name__,
                    in_channels=4, hidden_channels=4, center_rate=0.0)
    path = tmp_path / "categorical.pt"
    torch.save(dict(contract=contract, model_state_dict=network.state_dict(),
                    normalization_mean=torch.zeros(4), normalization_std=torch.ones(4),
                    best_epoch=1), path)
    return load_model(path)


def _categorical_sample(model, inputs):
    """A valid larger vocabulary in a deliberately different channel order."""
    sample = _sample(model, inputs)
    temperature = inputs[1][:, :1].copy()
    temperature_valid = inputs[2][:, :1].copy()
    zero = np.zeros_like(temperature)
    valid = np.ones_like(temperature, dtype=bool)
    sample["features"] = np.concatenate([
        zero, zero, temperature, np.ones_like(temperature), zero,
    ], axis=1)
    sample["feature_valid"] = np.concatenate([
        valid, valid, temperature_valid, valid, valid,
    ], axis=1)
    sample["channel_names"] = (
        "biome.biome_class=13", "biome.biome_class=5", "weather.temperature_2m",
        "biome.biome_class=4", "biome.biome_class=8",
    )
    return sample


def test_independent_larger_one_hot_vocabulary_preserves_unseen_and_structural_zero_semantics(
    categorical_model, hourly_training_bundle,
):
    from tests.probability.test_training import _write_raster
    from affine import Affine

    root, event = hourly_training_bundle
    biome = np.full((5, 5), 4, dtype=np.float32)
    biome[0, 2] = 13  # Class 13 is available in data but absent from this checkpoint.
    biome[4, 4] = 5
    _write_raster(root / "regions" / event["id"] / "biome" / "biome_class_375m.tif",
                  biome, Affine(*event["transform"]))
    (root / "biome_classes.json").write_text(json.dumps({"classes": [
        {"code": code, "name": f"Biome {code}"} for code in (4, 5, 8, 13)
    ]}))
    with load_data(root, events=[event["id"]], sequence_length=None) as dataset:
        sample = dataset[0]
    assert dataset.categorical_classes["biome.biome_class"] == (4, 5, 8, 13)
    assert sample["features"].shape[1] > len(categorical_model.channel_names)
    unseen = sample["channel_names"].index("biome.biome_class=13")
    assert sample["features"][0, unseen, 0, 2] == 1
    assert sample["feature_valid"][0, unseen, 0, 2]
    result = categorical_model.predict(sample)
    # This unburned cell has contact but requires an unrecognized category in
    # its environmental context; dropping the extra indicator must not turn
    # the required indicators into a known all-zero categorical vector.
    assert sample["burned_area"][0, 0, 1, 2] == 0
    assert not result.valid[0, 0, 1, 2] and torch.isnan(result.probability[0, 0, 1, 2])
    # Existing cumulative burned cells still cannot newly burn, even when
    # their rate needs unavailable environmental context.
    assert sample["burned_area"][0, 0, 1, 1] == 1
    assert result.valid[0, 0, 1, 1] and result.probability[0, 0, 1, 1] == 0
    assert not result.rate_valid[0, 0, 1, 1]
    # A distant complete, known and unburned neighborhood retains rate and
    # next-hour probability zero under the existing contact model.
    assert result.valid[0, 0, 3, 3] and result.rate_valid[0, 0, 3, 3]
    assert result.probability[0, 0, 3, 3] == 0 and result.rate[0, 0, 3, 3] == 0
    _assert_details_equal(result, categorical_model.predict_sample_details(sample))
    probability, coordinates = categorical_model.predict_sample(sample)
    torch.testing.assert_close(probability, result.probability, rtol=0, atol=0, equal_nan=True)
    torch.testing.assert_close(coordinates, result.coordinates, rtol=0, atol=0, equal_nan=True)


@pytest.mark.parametrize("values", [
    [0, 0, 0, 0], [1, 1, 0, 0], [.5, .5, 0, 0], [1, 0, 0, -1],
])
def test_known_malformed_larger_one_hot_groups_are_rejected(categorical_model, inputs, values):
    sample = _categorical_sample(categorical_model, inputs)
    indices = [sample["channel_names"].index(f"biome.biome_class={code}") for code in (4, 5, 8, 13)]
    sample["features"][0, indices, 1, 1] = values
    with pytest.raises(ValueError, match="one-hot"):
        categorical_model.predict(sample)


@pytest.mark.parametrize("padding", ["time", "pixel"])
def test_categorical_projection_ignores_malformed_values_outside_valid_support(categorical_model, inputs, padding):
    sample = _categorical_sample(categorical_model, inputs)
    categorical = [index for index, name in enumerate(sample["channel_names"]) if name.startswith("biome.")]
    if padding == "time":
        sample["time_valid"][1] = False
        sample["time_utc"][1] = -1
        sample["features"][1, categorical] = .5
    else:
        sample["pixel_valid"][0, -1, -1] = False
        sample["features"][:, categorical, -1, -1] = .5
    result = categorical_model.predict(sample)
    _assert_details_equal(result, categorical_model.predict_sample_details(sample))
    if padding == "time":
        assert not result.valid[1].any() and torch.isnan(result.probability[1]).all()
    else:
        assert not result.valid[:, :, -1, -1].any()
        assert torch.isnan(result.coordinates[-1, -1]).all()


def test_reordered_categorical_superset_retains_all_masks_and_legacy_result_parity(categorical_model, inputs):
    sample = _categorical_sample(categorical_model, inputs)
    sample["time_valid"][1] = False
    sample["time_utc"][1] = -1
    sample["pixel_valid"][0, 3, 4] = False  # The stored burned source is padding.
    ordered = dict(sample)
    indices = [sample["channel_names"].index(name) for name in categorical_model.channel_names]
    ordered["features"] = sample["features"][:, indices].copy()
    ordered["feature_valid"] = sample["feature_valid"][:, indices].copy()
    ordered["channel_names"] = categorical_model.channel_names
    expected = categorical_model.predict(ordered)
    result = categorical_model.predict(sample)
    _assert_details_equal(result, expected)
    assert not result.valid[1].any()
    assert not result.valid[0, 0, 3, 5]
    assert torch.isnan(result.coordinates[3, 4]).all()
    _assert_details_equal(result, categorical_model.predict_sample_details(sample))
    probability, coordinates = categorical_model.predict_sample(sample)
    torch.testing.assert_close(probability, result.probability, rtol=0, atol=0, equal_nan=True)
    torch.testing.assert_close(coordinates, result.coordinates, rtol=0, atol=0, equal_nan=True)
