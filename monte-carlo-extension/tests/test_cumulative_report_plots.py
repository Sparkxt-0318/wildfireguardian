"""Plot exports retain all models and the evaluation's numeric semantics."""
import csv
import hashlib
import json
import math

import numpy as np
import pytest
from PIL import Image

from wildfire.cumulative_report_plots import (
    _number, _select, _threshold_curves, generate_report_plots,
)


class _Store:
    def __init__(self, y, probability):
        self.y = np.asarray(y, dtype=np.uint8)
        self.p = np.asarray(probability, dtype=float)
        self.calls = 0

    def entries(self):
        self.calls += 1
        return dict(y=self.y, p=self.p)


@pytest.fixture(scope="module")
def rendered_report(tmp_path_factory):
    from wildfire.cumulative_evaluation import _score

    output = tmp_path_factory.mktemp("cumulative_comparison_plots")
    report = dict(protocol=dict(hours=6, n_samples=64, threshold=.5, split="test"), models=[], summary=[], per_event=[])
    stores = {}
    target = np.array([0, 1, 1, 0, 1, 0], dtype=np.uint8)
    specifications = (
        ("tensor/checkpoint.pt", "EnvironmentConditionedConvolution", [.1, .7, .8, .1, .7, .1]),
        ("forest/model.joblib", "RandomForestClassifier", [0, 0, .8, .2, .3, 0]),
        ("bayesian/checkpoint.pt", "BayesianKernelAverage", [.1, .8, .7, .2, .6, .1]),
    )
    for index, (model_id, architecture, probability) in enumerate(specifications):
        report["models"].append(dict(model_id=model_id, architecture=architecture, path=str(output / model_id)))
        for quantity in ("new_burn", "burned"):
            metrics, classification, calibration = _score(target, np.array(probability), np.ones(len(target)), .5)
            row = dict(model_id=model_id, cohort="shared_models", quantity=quantity, metrics=metrics, classification=classification, calibration=calibration, native_coverage_fraction=.95, shared_retention_fraction=.9)
            report["summary"].append(row)
            report["per_event"].append(dict(row, event="fixture-event"))
            stores[index, "shared_models", quantity] = _Store(target, probability)
    from matplotlib.figure import Figure
    original_save = Figure.savefig
    distance_axes = []

    def inspect_save(fig, path, *args, **options):
        if str(path).endswith("_distances.png"):
            distance_axes.append([dict(limits=ax.get_ylim(), ticks=ax.get_yticks().copy()) for ax in fig.axes])
        return original_save(fig, path, *args, **options)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(Figure, "savefig", inspect_save)
        manifest = generate_report_plots(report, output, stores=stores)
    return output, report, stores, manifest, distance_axes


def test_all_models_and_probability_quantities_have_valid_exports(rendered_report):
    output, report, stores, manifest, _ = rendered_report
    all_ids = {model["model_id"] for model in report["models"]}
    assert manifest["model_count"] == 3
    assert len(manifest["figures"]) == 14
    assert json.loads((output / "plots/manifest.json").read_text()) == manifest
    for quantity in ("new_burn", "burned"):
        for name in ("metrics", "architectures", "coverage"):
            assert set(manifest["figures"][f"{quantity}_{name}"]["plotted_ids"]) == all_ids
        assert set(manifest["selections"][quantity]["detail_ids"]) == all_ids
    for figure in manifest["figures"].values():
        for format_name, record in figure["outputs"].items():
            path = output / record["path"]
            assert path.stat().st_size == record["size_bytes"] > 5000
            assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]
            if format_name == "png":
                with Image.open(path) as raster:
                    assert raster.width >= 1000 and raster.height >= 600
                    assert np.asarray(raster.convert("RGB")).std() > 10
            else:
                assert "<svg" in path.read_text()
    with (output / manifest["model_index"]).open(newline="") as stream:
        index = list(csv.DictReader(stream))
    assert {row["model_id"] for row in index} == all_ids
    assert len({row["plot_id"] for row in index}) == len(index)
    assert all(store.calls == 1 for store in stores.values())


def test_infinite_exact_losses_remain_distinct_from_floored_losses(rendered_report):
    output, report, _, manifest, _ = rendered_report
    forest = next(row for row in report["summary"] if row["model_id"].startswith("forest") and row["quantity"] == "new_burn")
    assert forest["metrics"]["exact_negative_log_likelihood_mean"] == "infinity"
    assert math.isfinite(forest["metrics"]["clipped_log_loss"])
    keys = manifest["figures"]["new_burn_metrics"]["metric_keys"]
    assert "exact_negative_log_likelihood_mean" in keys
    assert "clipped_log_loss" in keys
    svg = (output / "plots/new_burn_metrics.svg").read_text()
    assert "Exact NLL" in svg and "Probability-floored NLL" in svg
    assert "infinite: 1" in svg
    assert "outside numeric scales" in svg
    distance_keys = manifest["figures"]["new_burn_distances"]["metric_keys"]
    assert len(distance_keys) == 9
    assert "bernoulli_jensen_shannon_divergence_mean" in distance_keys
    assert "bernoulli_wasserstein_1_distance_mean" in distance_keys
    assert "floored_bernoulli_kl_divergence_mean" in distance_keys
    assert "not geographic" in manifest["distance_space"]
    assert "no confidence intervals" in manifest["uncertainty"]


def test_infinite_last_representative_row_is_visible_on_every_distance_axis(rendered_report):
    _, _, _, manifest, distance_axes = rendered_report
    assert len(distance_axes) == 2
    for quantity, axes in zip(("new_burn", "burned"), distance_axes):
        count = len(manifest["selections"][quantity]["detail_ids"])
        assert len(axes) == 8
        for axis in axes:
            np.testing.assert_array_equal(axis["ticks"], np.arange(count))
            lower, upper = sorted(axis["limits"])
            assert lower < 0 and upper > count - 1


def test_display_selection_is_deterministic_and_preserves_forest_bayes_families():
    rows = {f"tensor-{i:03d}": dict(metrics=dict(brier=i / 1000)) for i in range(100)}
    rows.update({"rf": dict(metrics=dict(brier=.9)), "bayes": dict(metrics=dict(brier=.8))})
    families = {model_id: "Tensor" for model_id in rows}
    families.update(rf="RandomForestClassifier", bayes="BayesianKernelAverage")
    before = np.random.get_state()
    selected = _select(rows, families, 8)
    after = np.random.get_state()
    assert selected == _select(dict(reversed(list(rows.items()))), families, 8)
    assert len(selected) == 8 and {"rf", "bayes"} <= set(selected)
    assert "tensor-000" in selected
    assert all(np.array_equal(left, right) for left, right in zip(before, after))


@pytest.mark.parametrize("value, expected", [("infinity", math.inf), ("-infinity", -math.inf), (None, math.nan), (False, math.nan), ("undefined", math.nan)])
def test_numeric_decoding_does_not_replace_undefined_or_infinite_values_with_zero(value, expected):
    actual = _number(value)
    assert math.isnan(actual) if math.isnan(expected) else actual == expected


def test_exact_curves_group_ties_and_match_independent_threshold_enumeration():
    target, probability = np.array([1, 0, 1, 0]), np.array([.5, .5, .9, .1])
    curves = _threshold_curves(target, probability)
    # At thresholds >.9, .9, .5, .1: (FP,TP)=(0,0),(0,1),(1,2),(2,2).
    np.testing.assert_array_equal(curves["roc"][0], [0, 0, .5, 1])
    np.testing.assert_array_equal(curves["roc"][1], [0, .5, 1, 1])
    np.testing.assert_array_equal(curves["pr"][0], [0, .5, 1, 1])
    np.testing.assert_allclose(curves["pr"][1], [1, 1, 2 / 3, .5])
    assert curves["positive_count"] == curves["negative_count"] == 2


@pytest.mark.parametrize("target, expected_roc, expected_pr", [([], False, False), ([0, 0], False, False), ([1, 1], False, True)])
def test_empty_and_single_class_curves_are_explicitly_undefined(target, expected_roc, expected_pr):
    curves = _threshold_curves(target, np.full(len(target), .5))
    assert (curves["roc"] is not None) == expected_roc
    assert (curves["pr"] is not None) == expected_pr


@pytest.mark.parametrize("target, probability", [([1, 0], [.5]), ([2], [.5]), ([1], [math.nan]), ([0], [1.1])])
def test_invalid_pooled_curve_entries_are_rejected(target, probability):
    with pytest.raises(ValueError):
        _threshold_curves(target, probability)


def test_empty_report_writes_explicit_no_results_plot(tmp_path):
    manifest = generate_report_plots(dict(protocol=dict(hours=6), summary=[], models=[], per_event=[]), tmp_path)
    assert manifest["model_count"] == 0
    assert set(manifest["figures"]) == {"no_results"}
    assert manifest["figures"]["no_results"]["plotted_ids"] == []
    assert "No metric values or model rankings" in (tmp_path / "plots/no_results.svg").read_text()


def test_empty_evaluation_cohort_remains_undefined_in_plots_and_curves(tmp_path):
    from wildfire.cumulative_evaluation import _score

    metrics, classification, calibration = _score(np.empty(0), np.empty(0), np.empty(0), .5)
    row = dict(model_id="forest", cohort="shared_models", quantity="new_burn", metrics=metrics, classification=classification, calibration=calibration, native_coverage_fraction=None, shared_retention_fraction=None)
    report = dict(protocol=dict(hours=6, n_samples=64), models=[dict(model_id="forest", architecture="RandomForestClassifier")], summary=[row], per_event=[])
    manifest = generate_report_plots(report, tmp_path, stores={(0, "shared_models", "new_burn"): _Store([], [])})
    svg = (tmp_path / "plots/new_burn_metrics.svg").read_text()
    assert svg.count("undefined: 1") == 6
    assert "No nonempty reliability bins" in (tmp_path / "plots/new_burn_reliability.svg").read_text()
    curves = manifest["figures"]["new_burn_curves"]
    assert curves["plotted_ids"] == []
    assert curves["class_counts"]["forest"] == dict(positive_count=0, negative_count=0)
    assert "forest" in curves["unavailable_curves"]
