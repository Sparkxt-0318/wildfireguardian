"""Synthetic future support controls, with no source data or model checkpoint access."""
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from .test_blind_forecast_protocol import blind


@pytest.fixture
def fields(blind):
    shape = (2, 2)
    initial = np.array([[True, False], [False, False]])
    sample = SimpleNamespace(initial=initial, score_mask=np.ones(shape, bool),
                             environment=np.ones((2, *shape)), hours=1., event_id="SYNTHETIC_ONLY")
    names = ["c651_meanfield", *(variant + "_seed0" for variant in blind.VARIANTS)]
    values = {name: np.full(shape, .25) for name in names}
    validities = {name: ~initial for name in names}
    logistic = np.full(shape, .2)
    features = np.ones((4, 2))
    gradient = np.zeros((2, *shape))
    calls = []

    def sample_forecast(model, given, **kwargs):
        assert given is sample
        assert kwargs == dict(use_burnout=model != "c651_meanfield", use_spotting=model != "c651_meanfield")
        calls.append(model)
        return torch.tensor(values[model]), torch.tensor(validities[model])

    def logistic_features(given, columns, terrain):
        assert given is sample and columns == ["a", "b"] and terrain is gradient
        return features

    def logistic_predict(model, given, columns, terrain):
        assert given is sample and columns == ["a", "b"] and terrain is gradient
        return logistic

    def terrain_gradient(event):
        assert event == sample.event_id
        return gradient

    environment = SimpleNamespace(names=["a", "b"], terrain_gradient=terrain_gradient)
    pipeline = SimpleNamespace(sample_forecast=sample_forecast, logistic_features=logistic_features,
                               logistic_predict=logistic_predict)
    runtime = (pipeline, environment, SimpleNamespace(predictor="c651_meanfield"),
               {name: name for name in names if name != "c651_meanfield"}, object())
    return SimpleNamespace(runtime=runtime, sample=sample, registry=dict(best_dilation_hours_per_cell=4),
                           values=values, validities=validities, features=features, logistic=logistic, calls=calls)


def derive(blind, fields):
    return blind.deterministic_fields(fields.runtime, fields.sample, fields.registry)


def test_three_cell_reference_support_is_preserved_and_c651_values_are_checked_not_stored(blind, fields):
    predictions, mask = derive(blind, fields)
    np.testing.assert_array_equal(mask, ~fields.sample.initial)
    assert mask.sum() == 3 and "c651_meanfield" not in predictions and "c651_mc" not in predictions
    assert set(fields.calls) == set(fields.values)
    for name in fields.runtime[3]:
        np.testing.assert_array_equal(predictions[name], fields.values[name])


def test_declared_invalid_neural_unknown_values_do_not_become_numeric_failures(blind, fields):
    for name in fields.values:
        fields.values[name][0, 0] = np.nan
    _, mask = derive(blind, fields)
    assert mask.sum() == 3


@pytest.mark.parametrize("name", ["c651_meanfield", *(variant + "_seed0" for variant in
                         ("base", "d4", "d4_wind", "ellipse", "burnout", "burnout_spotting", "mixed_base"))])
@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf, -.01, 1.01])
def test_each_neural_failure_on_declared_support_refuses_instead_of_shrinking(blind, fields, name, bad):
    fields.values[name][0, 1] = bad
    with pytest.raises(ValueError, match="model numerical failure"):
        derive(blind, fields)


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf, -.01, 1.01])
def test_logistic_failure_on_finite_features_refuses_instead_of_shrinking(blind, fields, bad):
    fields.logistic[0, 1] = bad
    with pytest.raises(ValueError, match="logistic numerical failure"):
        derive(blind, fields)


def test_input_feature_unknowns_define_logistic_support_even_with_unknown_output(blind, fields):
    fields.features[2, 0] = np.nan
    fields.logistic[1, 0] = np.nan
    _, mask = derive(blind, fields)
    np.testing.assert_array_equal(mask, [[False, True], [False, True]])


def test_model_failures_outside_the_final_common_population_still_refuse(blind, fields):
    fields.sample.score_mask[0, 1] = False
    fields.validities["base_seed0"][0, 1] = False
    fields.values["mixed_base_seed0"][0, 1] = np.nan
    with pytest.raises(ValueError, match="model numerical failure"):
        derive(blind, fields)


def test_logistic_failure_cannot_hide_behind_another_models_unknown_support(blind, fields):
    fields.validities["base_seed0"][0, 1] = False
    fields.logistic[0, 1] = np.nan
    with pytest.raises(ValueError, match="logistic numerical failure"):
        derive(blind, fields)
