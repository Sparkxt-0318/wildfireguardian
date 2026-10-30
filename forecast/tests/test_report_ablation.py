"""Ablation support/comparability controls using synthetic reporting data only."""
import json
from pathlib import Path

import numpy as np
import pytest

from .test_report_readiness import build_fixture, execute, load_report, write


@pytest.fixture
def report():
    return load_report()


@pytest.mark.parametrize("base_weight,variant_weight", [(100., 50.), (100., 100.)])
def test_development_aggregate_scores_never_establish_a_common_cell_effect(report, tmp_path, monkeypatch, base_weight, variant_weight):
    # Equal weights may describe disjoint populations just as unequal weights can.
    records = {}
    for variant, weight in (("base", base_weight), ("burnout", variant_weight)):
        path = tmp_path / report.F.intended_phase(variant, "fold", "2020")["result"]
        path.parent.mkdir(parents=True); path.write_text("{}")
        records[variant] = dict(variant=variant, fold="2020", seed=0,
            validation_per_fire={"SYNTHETIC_FIRE": dict(brier=.1, weight=weight, clipped_nll=.2)},
            fit_seconds=1., parameters=1)
    monkeypatch.setattr(report.F, "phase_result", lambda root, run, variant, stage, fold:
                        (None, records[variant], None, None, None))
    result = report.ablation(tmp_path)
    for variant, weight in (("base", base_weight), ("burnout", variant_weight)):
        row = result[variant]
        assert row["pooled_brier"] == pytest.approx(.1)
        assert row["mean_fire_brier"] == pytest.approx(.1)
        assert row["own_support_weight"] == weight
        assert row["per_fire"]["SYNTHETIC_FIRE"]["weight"] == weight
        assert row["paired_status"].startswith("UNAVAILABLE_")
        assert all(row[name] is None for name in
                   ("difference_vs_base", "interval_95", "excludes_zero", "fires_better_than_base"))


def test_receipt_bound_common_cell_ablation_matches_manual_whole_fire_bootstrap(report, tmp_path, monkeypatch):
    fixture = build_fixture(report, tmp_path, outcome="complete")
    monkeypatch.setattr(report, "REPO", fixture.root)
    heldout = fixture.run / "heldout"
    # Unequal cell populations across fires distinguish pooling from equal-fire averaging.
    y = [np.array([0.]), np.array([1., 0., 1.])]
    base = [np.array([.2]), np.array([.2, .4, .7])]
    candidate = [np.array([.1]), np.array([.3, .8, .8])]
    assessment = json.loads((heldout / "ASSESSMENT.json").read_text())
    for index, fire in enumerate(assessment["events"]):
        predictions = {name: candidate[index] if name == "burnout_spotting_seed0" else base[index]
                       for name in fixture.predictions}
        path = heldout / (fire + ".npz")
        np.savez_compressed(path, y=y[index], interval=np.zeros(len(y[index]), dtype=int),
                            **{"p_" + name: values for name, values in predictions.items()})
        assessment["per_fire_files"][path.name] = report.sha256(path)
    write(heldout / "ASSESSMENT.json", assessment)
    entries, receipt = report.load_assessment(heldout)
    result = report.heldout_ablation(entries, receipt, "SYNTHETIC heldout cohort")
    row = result["variants"]["burnout_spotting"]
    errors = np.array([sum((c - t) ** 2 - (b - t) ** 2) for t, b, c in zip(y, base, candidate)])
    counts = np.array([len(t) for t in y])
    sampled = np.random.default_rng(20261030).integers(0, 2, size=(10000, 2))
    manual = np.array([sum(errors[i] for i in draw) / sum(counts[i] for i in draw) for draw in sampled])
    assert row["point_difference"] == pytest.approx(errors.sum() / counts.sum())
    assert row["point_difference"] != pytest.approx(np.mean(errors / counts))
    np.testing.assert_allclose(row["percentile_95_interval"], np.quantile(manual, [.025, .975]))
    assert row["fires_favouring_candidate"] == int((errors < 0).sum())
    assert row["model"] == "burnout_spotting_seed0"  # Artifact suffixes never change model columns.
    assert row["draws"] == 10000 and row["seed"] == 20261030
    assert result["complete_cohort_pass"] is True and result["promotion_criteria_pass"] is False
    assert result["per_fire_files"] == receipt["per_fire_files"]
    assert result["cohort"] == "SYNTHETIC heldout cohort"
    assert report.heldout_ablation(entries, receipt, result["cohort"]) == result


@pytest.mark.parametrize("outcome", ["empty", "partial", "complete"])
def test_fig03_uses_only_heldout_common_cells_and_never_reopens_hold_gate(report, tmp_path, monkeypatch, outcome):
    fixture = build_fixture(report, tmp_path, outcome=outcome)
    result = execute(report, fixture, monkeypatch)
    paired = result["heldout_ablation"]
    evidence = result["figure_evidence"]["fig03_ablation_forest_plot"]
    assert all(row["difference_vs_base"] is None for row in result["ablation"].values())
    assert paired["promotion_criteria_pass"] is False
    assert paired["unscored_outcomes"] == fixture.assessment["failed_or_unavailable"]
    assert paired["assessment_receipt_sha256"] == report.sha256(fixture.run / "heldout/ASSESSMENT.json")
    svg = (fixture.out / "figures/fig03_ablation_forest_plot.svg").read_text()
    if outcome == "empty":
        assert not paired["variants"] and evidence["metric_data_available"] is False
        assert "UNAVAILABLE" in svg
    else:
        assert len(paired["variants"]) == 6 and evidence["metric_data_available"] is True
        assert "Pooled common-cell Brier minus base" in svg
        assert "2020 to 2022" not in svg
        if outcome == "partial":
            assert paired["complete_cohort_pass"] is False
            assert "HOLD: supported subset only" in svg
            assert result["retrospective_superiority_gate"]["criteria_pass"] is False


def test_development_only_report_generates_unavailable_paired_panel(report, tmp_path, monkeypatch):
    fixture = build_fixture(report, tmp_path, outcome="empty")
    for path in (fixture.run / "heldout").iterdir(): path.unlink()
    result = execute(report, fixture, monkeypatch)
    assert len(result["ablation"]) == 7 and (fixture.out / "ablation.csv").is_file()
    assert result["heldout_ablation"]["status"] == "UNAVAILABLE_NO_AUTHENTICATED_HELDOUT_ASSESSMENT"
    assert result["figure_evidence"]["fig03_ablation_forest_plot"]["metric_data_available"] is False
    assert "UNAVAILABLE" in (fixture.out / "figures/fig03_ablation_forest_plot.svg").read_text()
