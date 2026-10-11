"""Validate the baseline's data contract, weighting, and fitted persistence."""

import joblib
import numpy as np
import pytest
from sklearn.ensemble import RandomForestClassifier

from wildfire.models import PatchRandomForest


def _patches(n=32, p=5):
    rng = np.random.default_rng(21)
    environment = rng.normal(size=(n, 2, p, p)).astype(np.float32)
    burned = rng.integers(0, 2, size=(n, 1, p, p)).astype(np.float32)
    burned[:, 0, p // 2, p // 2] = 0
    target = (environment[:, 0, p // 2, p // 2] > 0).astype(np.uint8)
    weight = np.linspace(1, 4, n)
    return environment, burned, target, weight


def _fitted(k=3):
    e, b, y, w = _patches()
    return PatchRandomForest(k, n_estimators=9, n_jobs=1).fit(
        e, b, y, w, channel_names=["temperature", "wind_u"],
    )


@pytest.mark.parametrize("kernel_size", [3, 5])
def test_center_crop_and_feature_order_equal_independent_sklearn_fit(kernel_size):
    e, b, y, w = _patches(p=7)
    model = PatchRandomForest(kernel_size, n_estimators=11, n_jobs=1)
    model.fit(e, b, y, w, channel_names=["temperature", "wind_u"])
    radius = kernel_size // 2
    patch = slice(3 - radius, 4 + radius)
    expected = np.concatenate((e[:, :, patch, patch].reshape(len(e), -1),
                               b[:, :, patch, patch].reshape(len(e), -1)), axis=1)
    reference = RandomForestClassifier(
        n_estimators=11, max_depth=15, random_state=7, n_jobs=1,
        criterion="gini", bootstrap=True, max_features="sqrt",
        min_samples_leaf=1, class_weight=None,
    ).fit(expected, y, sample_weight=w / w.mean())
    np.testing.assert_array_equal(model.estimator.feature_importances_, reference.feature_importances_)
    probability = model.predict_probability(e, b, channel_names=["temperature", "wind_u"])
    np.testing.assert_array_equal(probability, reference.predict_proba(expected)[:, 1])
    assert probability.dtype == np.float64
    assert model.contract["n_features"] == 3 * kernel_size**2
    assert model.contract["feature_order"][0] == f"environment:temperature[row={-radius},col={-radius}]"
    assert model.contract["feature_order"][kernel_size**2] == f"environment:wind_u[row={-radius},col={-radius}]"
    assert model.contract["feature_order"][2 * kernel_size**2] == f"burned[row={-radius},col={-radius}]"


def test_mean_normalized_weights_reach_the_estimator(monkeypatch):
    e, b, y, _ = _patches()
    relative_weights = np.arange(1, len(y) + 1, dtype=np.float64)
    # All weights are finite, but summing their absolute magnitudes overflows.
    weights = relative_weights * 1e306
    calls = []
    original = RandomForestClassifier.fit

    def capture_fit(self, features, target, sample_weight=None):
        calls.append((features.copy(), target.copy(), sample_weight.copy()))
        return original(self, features, target, sample_weight=sample_weight)

    monkeypatch.setattr(RandomForestClassifier, "fit", capture_fit)
    model = PatchRandomForest(n_estimators=5, n_jobs=1)
    model.fit(e, b, y, weights, channel_names=["temperature", "wind_u"])
    assert len(calls) == 1
    np.testing.assert_array_equal(calls[0][1], y)
    np.testing.assert_allclose(calls[0][2], relative_weights / relative_weights.mean(), rtol=2e-15)
    assert calls[0][2].mean() == pytest.approx(1)
    assert model.estimator.class_weight is None


def test_save_load_keeps_predictions_metadata_and_rejects_overwrite(tmp_path):
    e, b, _, _ = _patches()
    model = _fitted()
    path = tmp_path / "nested" / "forest.joblib"
    metadata = {"source": "test", "train_only": ["temperature", "wind_u"]}
    assert model.save(path, metadata=metadata) == path
    loaded = PatchRandomForest.load(path)
    assert loaded.contract == model.contract
    assert loaded.metadata == metadata
    loaded.metadata["train_only"].clear()
    assert loaded.metadata == metadata
    np.testing.assert_array_equal(
        model.predict_probability(e, b, channel_names=model.channel_names),
        loaded.predict_probability(e, b, channel_names=loaded.channel_names),
    )
    with pytest.raises(FileExistsError):
        model.save(path)
    assert PatchRandomForest.load(path).contract == model.contract


def test_tampered_contract_is_rejected(tmp_path):
    path = tmp_path / "forest.joblib"
    _fitted().save(path)
    payload = joblib.load(path)
    payload["contract"]["dt_hours"] = 2.0
    joblib.dump(payload, path)
    with pytest.raises(ValueError, match="checkpoint contract"):
        PatchRandomForest.load(path)


@pytest.mark.parametrize("horizon", [0, 2, -1, np.nan, np.inf])
def test_fixed_hour_endpoint_is_enforced(horizon):
    model = _fitted()
    e, b, _, _ = _patches()
    with pytest.raises(ValueError, match="dt_hours=1.0"):
        model.predict_probability(e, b, channel_names=model.channel_names, dt_hours=horizon)


def test_channels_cannot_be_reordered_or_changed_on_prediction_or_refit():
    e, b, y, w = _patches()
    model = _fitted()
    for channels in (["wind_u", "temperature"], ["temperature", "wind_v"]):
        with pytest.raises(ValueError, match="channel names/order"):
            model.predict_probability(e, b, channel_names=channels)
        with pytest.raises(ValueError, match="channel names/order"):
            model.fit(e, b, y, w, channel_names=channels)


@pytest.mark.parametrize("bad_input", ["environment_nan", "burned_inf", "burned_fraction",
                                        "burned_center", "target_fraction", "weight_zero",
                                        "weight_negative", "weight_nan", "target_shape"])
def test_invalid_training_data_are_rejected(bad_input):
    e, b, y, w = _patches()
    y = y.astype(float)
    expected = {
        "environment_nan": "finite", "burned_inf": "finite",
        "burned_fraction": "binary", "burned_center": "center",
        "target_fraction": "binary", "weight_zero": "positive",
        "weight_negative": "positive", "weight_nan": "finite", "target_shape": "shape",
    }[bad_input]
    if bad_input == "environment_nan":
        e[0, 0, 0, 0] = np.nan
    elif bad_input == "burned_inf":
        b[0, 0, 0, 0] = np.inf
    elif bad_input == "burned_fraction":
        b[0, 0, 0, 0] = 0.5
    elif bad_input == "burned_center":
        b[0, 0, 2, 2] = 1
    elif bad_input == "target_fraction":
        y[0] = 0.5
    elif bad_input == "weight_zero":
        w[0] = 0
    elif bad_input == "weight_negative":
        w[0] = -1
    elif bad_input == "weight_nan":
        w[0] = np.nan
    elif bad_input == "target_shape":
        y = y[:, None]
    with pytest.raises(ValueError, match=expected):
        PatchRandomForest(n_estimators=3, n_jobs=1).fit(e, b, y, w, channel_names=["a", "b"])


@pytest.mark.parametrize("value", [0, 1])
def test_one_class_fit_and_empty_burned_neighborhood_are_supported(value):
    e, b, y, w = _patches()
    b[:] = 0
    y[:] = value
    model = PatchRandomForest(n_estimators=3, n_jobs=1).fit(e, b, y, w, channel_names=["a", "b"])
    np.testing.assert_array_equal(model.predict_probability(e, b, channel_names=["a", "b"]),
                                  np.full(len(e), value, dtype=np.float64))
    assert model.predict_probability(e[:0], b[:0], channel_names=["a", "b"]).shape == (0,)


def test_unfitted_model_and_invalid_shapes_have_explicit_errors():
    e, b, y, w = _patches()
    model = PatchRandomForest(n_estimators=3, n_jobs=1)
    with pytest.raises(RuntimeError, match="must be fitted"):
        model.predict_probability(e, b, channel_names=["a", "b"])
    for bad_e, bad_b in ((e[:, :, :4, :4], b[:, :, :4, :4]),
                         (e[:, :, :3, :4], b[:, :, :3, :4]),
                         (e[:, :, :1, :1], b[:, :, :1, :1]),
                         (e, b[:, :, :3, :3])):
        with pytest.raises(ValueError, match="patches|shape"):
            model.fit(bad_e, bad_b, y, w, channel_names=["a", "b"])
