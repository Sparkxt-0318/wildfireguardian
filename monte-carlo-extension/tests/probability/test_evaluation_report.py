"""Bar charts retain raw scores, zero baselines, cohorts, and all metric fields."""

import importlib.util
import json
import os
from pathlib import Path
import re

import pytest


if os.environ.get("EVALUATION_REPORT_MODULE"):
    spec = importlib.util.spec_from_file_location("evaluation_report", os.environ["EVALUATION_REPORT_MODULE"])
    report = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(report)
else:
    import wildfire.report as report


@pytest.fixture
def completed_run(tmp_path):
    metrics = {}
    for index, split in enumerate(report.evaluation_SPLITS):
        models = {}
        for model, size in (("one", 3), ("two", 5)):
            score = dict(brier=.1 + .05 * index, future_metric=.2 + index,
                         mcc_at_0_5=-.2 if index == 0 else .4,
                         bernoulli_kl_divergence_mean="infinity" if model == "one" else .8,
                         roc_auc=None, classification_at_0_5={"tp": 2., "threshold": .5})
            models[model] = dict(kernel_size=size, common=score, native={**score, "brier": .6},
                                 coverage={"predicted_count": 4})
        metrics[split] = dict(models=models, common_cohort={"sample_count": 4},
                              native_cohorts={"3": {"sample_count": 4}, "5": {"sample_count": 5}})
    selected = [dict(candidate=dict(id=model, family="cnn", kernel_size=size)) for model, size in (("one", 3), ("two", 5))]
    for name, value in (("metrics.json", metrics), ("selection.json", dict(selected=selected, best=selected[1], test_used_for_selection=False)),
                        ("protocol.json", {}), ("complete.json", {"completed": True})):
        (tmp_path / name).write_text(json.dumps(value))
    (tmp_path / "report.md").write_text("# Original comparison\n\nExisting analysis.\n")
    return tmp_path


def test_grouped_bars_include_zero_baseline_and_negative_scores(tmp_path, monkeypatch):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = [dict(metric="mcc_at_0_5", model="one", kernel_size=3, scope=scope,
                 split=split, status="finite", finite_value=value, value=value)
            for scope in ("common", "native") for split, value in zip(report.evaluation_SPLITS, (-.3, 0., .6))]
    captured = []
    monkeypatch.setattr(matplotlib.figure.Figure, "savefig", lambda figure, *args, **kwargs: captured.append(figure))
    report._draw_metric(plt, tmp_path / "mcc.png", "mcc_at_0_5", rows, ["one"], {"one": "One model"})
    for axis in captured[0].axes:
        assert [rectangle.get_width() for rectangle in axis.patches] == [-.3, 0., .6]
        assert all(rectangle.get_x() == 0 for rectangle in axis.patches)
        assert axis.get_xlim()[0] <= -.3 and axis.get_xlim()[1] >= .6


def test_infinite_and_undefined_values_do_not_become_zero_bars(tmp_path, monkeypatch):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = [dict(metric="bernoulli_kl_divergence_mean", model="one", kernel_size=3, scope=scope,
                 split=split, status=status, finite_value=None, value=None)
            for scope in ("common", "native") for split, status in zip(report.evaluation_SPLITS, ("positive_infinity", "undefined", "missing"))]
    captured = []
    monkeypatch.setattr(matplotlib.figure.Figure, "savefig", lambda figure, *args, **kwargs: captured.append(figure))
    report._draw_metric(plt, tmp_path / "kl.png", "bernoulli_kl_divergence_mean", rows, ["one"], {"one": "One model"})
    for axis in captured[0].axes:
        assert not axis.patches
        assert {"+∞", "N/A", "missing"} <= {label.get_text() for label in axis.texts}


def test_dashboard_every_metric_model_split_and_scope_preserves_saved_values(completed_run, monkeypatch):
    inputs = {path: path.read_bytes() for path in completed_run.iterdir() if path.name != "report.md"}
    manifest = report.generate_evaluation_report(completed_run)
    assert manifest["chart_style"] == "grouped_bars"
    assert manifest["overview_model"] == "two"
    assert {path: path.read_bytes() for path in inputs} == inputs
    text = (completed_run / "evaluation/overview.html").read_text()
    payload = json.loads(re.search(r'<script id="evaluation-data" type="application/json">(.*?)</script>', text, re.S).group(1))
    assert {metric["key"] for metric in payload["metrics"]} == set(manifest["scalar_metrics"])
    assert "future_metric" in manifest["scalar_metrics"]
    assert {model["id"] for model in payload["models"]} == {"one", "two"}
    for model in ("one", "two"):
        for key in manifest["scalar_metrics"]:
            scopes = ("full_prediction",) if key.startswith("coverage.") else ("common", "native")
            for scope in scopes:
                assert set(payload["cells"][model][scope][key]) == set(report.evaluation_SPLITS)
    assert payload["cells"]["one"]["common"]["brier"]["train"]["value"] == .1
    assert payload["cells"]["one"]["common"]["brier"]["test"]["value"] == .2
    assert payload["cells"]["one"]["native"]["brier"]["test"]["value"] == .6
    assert payload["cells"]["one"]["common"]["bernoulli_kl_divergence_mean"]["test"]["text"] == "+∞"
    assert payload["cells"]["one"]["common"]["roc_auc"]["test"]["text"] == "N/A"
    assert all((completed_run / "evaluation" / relative).is_file() for relative in manifest["asset_sha256"])
    main = (completed_run / "report.md").read_text()
    assert main.index(report.OVERVIEW_START) < main.index("Existing analysis")
    assert main.count(report.START) == main.count(report.OVERVIEW_START) == 1
    assert "](evaluation/overview.html)" in main

    def no_redraw(*args, **kwargs):
        raise AssertionError("Repeated reporting should reuse verified bar-chart assets")

    monkeypatch.setattr(report, "_draw_metric", no_redraw)
    monkeypatch.setattr(report, "_overview_assets", no_redraw)
    assert report.generate_evaluation_report(completed_run) == manifest
    assert (completed_run / "report.md").read_text() == main
    assert {path: path.read_bytes() for path in inputs} == inputs


def test_undefined_and_missing_are_distinct():
    assert report._status(None) == ("undefined", None)
    assert report._status(None, present=False) == ("missing", None)


def test_default_model_uses_saved_selection_without_looking_at_test():
    assert report._overview_model({"best": {"candidate": {"id": "validation_winner"}}}, ["test_winner", "validation_winner"]) == "validation_winner"


def test_incomplete_run_is_refused(completed_run):
    (completed_run / "complete.json").write_text('{"completed":false}')
    with pytest.raises(ValueError, match="completed comparison"):
        report.generate_evaluation_report(completed_run)
    assert not (completed_run / "evaluation").exists()
