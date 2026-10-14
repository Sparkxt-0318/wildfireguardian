"""Observed comparison figures retain matched cohorts and exact loss policy."""
from copy import deepcopy
import hashlib
import json

import numpy as np
import pytest

from wildfire.observed_report_plots import _spatial_inputs, generate_observed_report_plots


class _Store:
    def __init__(self, y, p):
        self.y, self.p = np.asarray(y, dtype=np.uint8), np.asarray(p, dtype=float)

    def entries(self):
        return dict(y=self.y, p=self.p)


def _fixture():
    from wildfire.cumulative_evaluation import _score

    initial = np.array([[1, 0, 0], [0, 0, 0]], dtype=bool)
    observed = np.array([[1, 1, 0], [0, 1, 0]], dtype=bool)
    total = np.array([[1, .8, .1], [.2, .5, .1]])
    farsite_total = np.array([[1, 1, 0], [1, 0, 0]], dtype=float)
    models = [dict(model_id="checkpoint", display_label="M548", architecture="MixedNonnegativeKernel"),
              dict(model_id="farsite", display_label="FARSITE", architecture="FARSITE")]
    report = dict(models=models, protocol=dict(hours=24, threshold=.5, n_samples=64), summary=[], per_event=[])
    stores, predictions = {}, {}
    for index, (model, probability) in enumerate(zip(models, (total, farsite_total))):
        predictions[model["model_id"]] = dict(burned=probability, new_burn=np.where(initial, 0, probability))
        for quantity in ("new_burn", "burned"):
            mask = ~initial if quantity == "new_burn" else np.ones_like(initial)
            y = (observed & ~initial if quantity == "new_burn" else observed)[mask]
            p = predictions[model["model_id"]][quantity][mask]
            metrics, classification, calibration = _score(y, p, np.ones(len(y)), .5)
            row = dict(model_id=model["model_id"], cohort="shared_models", quantity=quantity,
                       metrics=metrics, classification=classification, calibration=calibration,
                       native_coverage_fraction=1., shared_retention_fraction=1.)
            report["summary"].append(row)
            report["per_event"].append(dict(row, event="Survey fixture"))
            stores[index, "shared_models", quantity] = _Store(y, p)
    spatial = dict(initial_burned=initial, observed_burned=observed,
                   observed_valid=np.ones_like(initial), shared_valid=np.ones_like(initial),
                   predictions=predictions, extent=[100, 1225, 200, 950], coordinate_label="EPSG:5070 metres")
    return report, stores, spatial


@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    report, stores, spatial = _fixture()
    original = deepcopy(report)
    output = tmp_path_factory.mktemp("observed_report_plots")
    manifest = generate_observed_report_plots(report, output, stores=stores, spatial=spatial)
    assert report == original
    return output, manifest


def test_complete_named_observation_plot_set_has_valid_saved_hashes(rendered):
    output, manifest = rendered
    assert len(manifest["figures"]) == 20
    assert manifest["prediction_kind"] == "mixed_recursive_monte_carlo_and_deterministic_farsite"
    assert manifest["reference_kind"] == "observation_derived_survey_perimeter"
    assert json.loads((output / "plots/manifest.json").read_text()) == manifest
    for quantity in ("new_burn", "burned"):
        svg = (output / f"plots/{quantity}_reliability.svg").read_text()
        assert "Observed perimeter outcome fraction" in svg
        assert "matched observed-perimeter evaluation" in svg
        assert "M548" in svg and "FARSITE" in svg
        assert len(manifest["figures"][f"{quantity}_classification"]["metric_keys"]) == 8
        assert "Fixed threshold 0.5" in (output / f"plots/{quantity}_confusion.svg").read_text()
        assert manifest["figures"][f"{quantity}_spatial_comparison"]["shared_cell_count"] == (5 if quantity == "new_burn" else 6)
    assert "infinite: 1" in (output / "plots/burned_metrics.svg").read_text()
    for record in manifest["figures"].values():
        for extension, saved in record["outputs"].items():
            path = output / saved["path"]
            assert saved["size_bytes"] == path.stat().st_size > 5000
            assert saved["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_different_observed_cohorts_are_rejected_before_rendering(tmp_path):
    report, stores, _ = _fixture()
    stores[1, "shared_models", "burned"].y[0] = 0
    with pytest.raises(ValueError, match="same ordered observed cohort"):
        generate_observed_report_plots(report, tmp_path, stores=stores)
    assert not (tmp_path / "plots").exists()


def test_missing_entries_and_single_model_cannot_silently_omit_curves(tmp_path):
    report, stores, _ = _fixture()
    del stores[1, "shared_models", "new_burn"]
    with pytest.raises(ValueError, match="Complete pooled entries"):
        generate_observed_report_plots(report, tmp_path, stores=stores)
    report["models"] = report["models"][:1]
    with pytest.raises(ValueError, match="exactly two distinct"):
        generate_observed_report_plots(report, tmp_path, stores={})


@pytest.mark.parametrize("problem", ["mask_shape", "numeric_mask", "unknown_shared", "probability", "extent"])
def test_invalid_or_unavailable_spatial_inputs_remain_explicit(problem):
    _, _, spatial = _fixture()
    if problem == "mask_shape":
        spatial["observed_valid"] = np.ones(2, dtype=bool)
    elif problem == "numeric_mask":
        spatial["observed_valid"] = np.ones((2, 3), dtype=int)
    elif problem == "unknown_shared":
        spatial["observed_valid"][0, 0] = False
    elif problem == "probability":
        spatial["predictions"]["checkpoint"]["burned"][0, 0] = np.nan
    else:
        spatial["extent"] = [0, 0, 0, 100]
    with pytest.raises(ValueError):
        _spatial_inputs(spatial, ["checkpoint", "farsite"])
