"""Receipt-bound comparison reporting, using synthetic metadata and no forecasts."""
import ast
import copy
import gzip
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
from PIL import Image
import pytest

from .test_report_readiness import load_report, write


@pytest.fixture
def report():
    return load_report()


def source_map(root):
    paths = sorted(p for p in (root / "forecast/wildfire").rglob("*")
                   if p.is_file() and p.suffix in (".py", ".json"))
    evidence = root / "research/forecast-v2"
    paths += [evidence / "scripts" / name for name in ("run_campaign.py", "pipeline.py", "audit_fit_coverage.py")]
    paths += [evidence / "RUN_PROTOCOL.json", evidence / "RUN_PROTOCOL_EXTENSION_2.json"]
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def resign_aggregate(report, fixture, *, csv=True):
    obj = json.loads(fixture.aggregate.read_text())
    if csv:
        pd.DataFrame(obj["rows"]).to_csv(fixture.aggregate.with_suffix(".csv"), index=False)
    rec = json.loads(fixture.aggregate_receipt.read_text())
    rec["output_sha256"] = report.sha256(fixture.aggregate)
    write(fixture.aggregate_receipt, rec)


def resign(report, fixture, *, case_csv=True, aggregate_rows=True, aggregate_csv=True):
    rows, pins = [], []
    for output, receipt in zip(fixture.outputs, fixture.receipts):
        obj = json.loads(output.read_text())
        if case_csv:
            pd.DataFrame(obj["rows"]).to_csv(output.with_suffix(".csv"), index=False)
        rec = json.loads(receipt.read_text()); rec["output_sha256"] = report.sha256(output)
        write(receipt, rec)
        pins.append(dict(path=str(receipt.relative_to(fixture.root)), sha256=report.sha256(receipt)))
        rows.extend(obj["rows"])
    obj = json.loads(fixture.aggregate.read_text())
    obj["case_receipts"] = pins
    if aggregate_rows:
        obj["rows"] = rows
    write(fixture.aggregate, obj)
    rec = json.loads(fixture.aggregate_receipt.read_text()); rec["case_receipts"] = pins
    write(fixture.aggregate_receipt, rec)
    resign_aggregate(report, fixture, csv=aggregate_csv)


def fixture_comparison(report, tmp_path, monkeypatch, *, all_null=False):
    root = tmp_path / "synthetic-repo"
    evidence = root / "research/forecast-v2"
    for rel, text in {"forecast/wildfire/model.py": "# synthetic numerical module\n",
                      "research/forecast-v2/scripts/pipeline.py": "# synthetic immutable comparison producer\n",
                      "research/forecast-v2/scripts/run_campaign.py": "# synthetic immutable controller\n",
                      "research/forecast-v2/scripts/audit_fit_coverage.py": "# synthetic original auditor\n"}.items():
        path = root / rel; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text)
    cases = []
    for index in range(12):
        country = "KR" if index < 6 else "US"
        event = ("SYNTHETIC_KR_A" if index < 3 else "SYNTHETIC_KR_B" if index < 5 else "SYNTHETIC_KR_C") if index < 6 else f"SYNTHETIC_US_{index}"
        cases.append(dict(country=country, event=event, cutoff=f"2022-01-{index + 1:02d}T00:00:00+00:00",
                          initial_sha256="0" * 64, shape=[2, 2], survey_hours=None if index < 6 else [30.083333333333332, 24.75, 24.233333333333334, 23.833333333333332, 24.666666666666668, 46.266666666666666][index - 6]))
    settings = dict(cases=cases, n_samples=1024, seed=0, trajectory_batch_size=32, horizons_hours=[1, 3, 6, 12, 24])
    protocol = dict(data_manifest_sha256="d" * 64, mean_field_compare=settings)
    write(evidence / "RUN_PROTOCOL.json", protocol)
    write(evidence / "RUN_PROTOCOL_EXTENSION_2.json", dict(synthetic=True))
    sources = source_map(root)
    auditor = sources["research/forecast-v2/scripts/audit_fit_coverage.py"]
    # Only this synthetic fixture installs a reviewed catalog before mutations.
    # The production loader and original-source reader still execute unchanged.
    monkeypatch.setattr(report, "REPO", root)
    monkeypatch.setattr(report, "COMPARISON_PROTOCOL_SHA256", report.sha256(evidence / "RUN_PROTOCOL.json"))
    monkeypatch.setattr(report, "COMPARISON_AUDITOR_SHA256", auditor)
    monkeypatch.setattr(report, "COMPARISON_CURRENT_AUDITORS", {auditor})
    monkeypatch.setattr(report, "COMPARISON_SOURCE_SHA256", hashlib.sha256(json.dumps(sources, sort_keys=True, separators=(",", ":")).encode()).hexdigest())
    run = root / "forecast/runs/synthetic-comparison"
    outputs, receipts, all_rows, pins = [], [], [], []
    for index, case in enumerate(cases):
        horizons = [("fixed", h) for h in [1, 3, 6, 12, 24]]
        if case["country"] == "US":
            horizons.append(("survey", case["survey_hours"]))
        rows = []
        for kind, hours in horizons:
            empty = all_null or case["country"] == "KR" and (hours == 24 or hours == 12 and index >= 3)
            no_active = empty or case["country"] == "KR" and hours == 12
            cells, active = (0 if empty else 3), (0 if no_active else 2)
            row = dict(country=case["country"], event=case["event"], cutoff=case["cutoff"], horizon_kind=kind, hours=float(hours),
                mc_seconds=1.2345678901234567 + index if kind == "fixed" else 2.5 + index,
                mf_seconds=.12345678901234566 + index if kind == "fixed" else .25 + index,
                n_samples=1024, seed=0,
                timing_scope="one joint 24h call, shared across five horizon rows" if kind == "fixed" else "one fractional survey-endpoint call",
                status="UNAVAILABLE_SHARED_SUPPORT" if empty else "COMPARABLE", cells=cells, active_cells=active,
                rmse_all=None if empty else 0. if no_active else .1,
                rmse_active=None if no_active else .12, mean_mc=None if empty else 0. if no_active else .2,
                mean_mf=None if empty else 0. if no_active else .25,
                expected_new_cells_mc=None if empty else 0. if no_active else .6,
                expected_new_cells_mf=None if empty else 0. if no_active else .75,
                max_abs_difference=None if empty else 0. if no_active else .2)
            if kind == "survey" or case["country"] == "KR":
                row.update(reference_status="UNAVAILABLE_REFERENCE_SUPPORT" if empty else "SCORED", label_cells=cells,
                    positives=None if empty else 1, brier_mc=None if empty else 1 / 3 if no_active else .1,
                    brier_mf=None if empty else 1 / 3 if no_active else .12,
                    brier_persistence=None if empty else 1 / 3,
                    label_kind="kriged reconstruction (not observed)" if case["country"] == "KR" else "NIROPS mapped extent at the next survey")
            rows.append(row)
        output = run / f"meanfield_vs_mc/case_{index:02d}_a06/meanfield_vs_mc.json"
        write(output, dict(rows=rows, host=dict(synthetic=True, torch_threads=2), checkpoint_sha256=report.COMPARISON_CHECKPOINT_SHA256))
        pd.DataFrame(rows).to_csv(output.with_suffix(".csv"), index=False)
        receipt = evidence / f"executions/a06_compare_case{index:02d}.json"
        receipt.parent.mkdir(exist_ok=True)
        log = receipt.with_suffix(".log"); log.write_text(f"Synthetic metadata case {index}\n")
        command = ["synthetic-python", str(evidence / "scripts/pipeline.py"), "compare", "--compare-case-index", str(index),
                   "--artifact-suffix", "_a06", "--n-samples", "1024", "--seed", "0", "--data-manifest-sha256", protocol["data_manifest_sha256"]]
        write(receipt, dict(job=f"a06_compare_case{index:02d}", command=command, exit_code=0, source_sha256=sources,
            output=str(output), output_sha256=report.sha256(output), log_sha256=report.sha256(log),
            data_manifest_sha256=protocol["data_manifest_sha256"], elapsed_seconds=30.))
        outputs.append(output); receipts.append(receipt); all_rows.extend(rows)
        pins.append(dict(path=str(receipt.relative_to(root)), sha256=report.sha256(receipt)))
    aggregate = run / "meanfield_vs_mc/meanfield_vs_mc.json"
    write(aggregate, dict(rows=all_rows, checkpoint_sha256=report.COMPARISON_CHECKPOINT_SHA256, case_receipts=pins,
        host=dict(synthetic=True, torch_threads=2), timing="Each fixed-horizon group shares one joint24h MC and MF call"))
    pd.DataFrame(all_rows).to_csv(aggregate.with_suffix(".csv"), index=False)
    aggregate_receipt = evidence / "executions/a06_compare.json"
    write(aggregate_receipt, dict(job="a06_compare", exit_code=0, source_sha256=sources, output=str(aggregate),
                                 output_sha256=report.sha256(aggregate), case_receipts=pins))
    return SimpleNamespace(root=root, run=run, evidence=evidence, outputs=outputs, receipts=receipts,
                           aggregate=aggregate, aggregate_receipt=aggregate_receipt, sources=sources, cases=cases)


def alter_row(fixture, index, operation):
    path = fixture.outputs[index]; obj = json.loads(path.read_text())
    operation(obj["rows"])
    write(path, obj)


def test_complete_twelve_case_fixture_authenticates_before_refusal_controls(report, tmp_path, monkeypatch):
    f = fixture_comparison(report, tmp_path, monkeypatch)
    frame, result = report.load_comparison(f.run)
    assert len(frame) == 66 and result["execution_complete"] is True
    assert result["metric_data_available"] is True
    assert len(result["authentication"]["producer_source_sha256"]) == len(f.sources)
    hashes = result["authentication"]["artifacts_sha256"]
    assert len([p for p in hashes if p.endswith(".csv")]) == 13
    assert len([p for p in hashes if p.endswith(".log")]) == 12
    assert hashes[str(f.aggregate_receipt.relative_to(f.root))] == report.sha256(f.aggregate_receipt)
    runtime = result["runtime"]
    assert runtime["joint24h"]["mc_calls"] == runtime["joint24h"]["mf_calls"] == 12
    assert runtime["survey_endpoint"]["mc_calls"] == runtime["survey_endpoint"]["mf_calls"] == 6
    assert runtime["joint24h"]["mc_seconds"] == pytest.approx(sum(1.2345678901234567 + i for i in range(12)))
    assert runtime["joint24h"]["mc_seconds"] != pytest.approx(frame.loc[frame.horizon_kind == "fixed", "mc_seconds"].sum())
    assert "False" in runtime["joint24h"]["mc_path"] and "True" in runtime["survey_endpoint"]["mc_path"]
    assert "not independently recomputed" in result["authentication"]["limit"]


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "cutoff", "horizon", "seed", "samples", "field", "order", "timing"])
def test_resigned_case_population_or_controls_cannot_change(report, tmp_path, monkeypatch, mutation):
    f = fixture_comparison(report, tmp_path, monkeypatch)
    def change(rows):
        if mutation == "missing": rows.pop()
        elif mutation == "duplicate": rows[1] = copy.deepcopy(rows[0])
        elif mutation == "order": rows[0], rows[1] = rows[1], rows[0]
        elif mutation == "timing": rows[1]["mc_seconds"] += 1
        else: rows[0][{"cutoff": "cutoff", "horizon": "hours", "seed": "seed", "samples": "n_samples", "field": "extra"}[mutation]] = {"cutoff": "2022-02-01T00:00:00+00:00", "horizon": 2., "seed": 1, "samples": 7, "field": "unknown"}[mutation]
    alter_row(f, 0, change); resign(report, f)
    with pytest.raises(ValueError): report.load_comparison(f.run)


@pytest.mark.parametrize("where", ["case", "aggregate"])
def test_wrong_checkpoint_is_refused_even_when_all_file_hashes_are_resigned(report, tmp_path, monkeypatch, where):
    f = fixture_comparison(report, tmp_path, monkeypatch)
    p = f.outputs[0] if where == "case" else f.aggregate
    obj = json.loads(p.read_text()); obj["checkpoint_sha256"] = "f" * 64; write(p, obj)
    resign(report, f) if where == "case" else resign_aggregate(report, f)
    with pytest.raises(ValueError, match="checkpoint|model"): report.load_comparison(f.run)


@pytest.mark.parametrize("target", ["value", "order", "missing"])
@pytest.mark.parametrize("where", ["case", "aggregate"])
def test_csv_must_round_trip_exact_ordered_json_rows(report, tmp_path, monkeypatch, target, where):
    f = fixture_comparison(report, tmp_path, monkeypatch)
    p = (f.outputs[0] if where == "case" else f.aggregate).with_suffix(".csv")
    frame = pd.read_csv(p, float_precision="round_trip")
    if target == "value": frame.loc[0, "rmse_all"] += .000000000000001
    elif target == "order": frame = frame.iloc[::-1]
    else: frame = frame.iloc[:-1]
    frame.to_csv(p, index=False)
    with pytest.raises(ValueError, match="CSV"): report.load_comparison(f.run)


@pytest.mark.parametrize("mutation", ["metric", "order", "duplicate", "typed_seed"])
def test_resigned_aggregate_cannot_disagree_with_cases(report, tmp_path, monkeypatch, mutation):
    f = fixture_comparison(report, tmp_path, monkeypatch)
    obj = json.loads(f.aggregate.read_text())
    if mutation == "metric": obj["rows"][0]["rmse_active"] = .2
    elif mutation == "order": obj["rows"].reverse()
    elif mutation == "duplicate": obj["rows"][1] = copy.deepcopy(obj["rows"][0])
    else: obj["rows"][0]["seed"] = False  # Python numeric equality must not erase JSON type changes.
    write(f.aggregate, obj)
    resign_aggregate(report, f)
    with pytest.raises(ValueError, match="all twelve ordered"): report.load_comparison(f.run)


@pytest.mark.parametrize("target", ["source", "source_extra", "source_missing", "source_auditor", "new_source_file", "protocol", "receipt", "log", "output", "missing_receipt", "receipt_pin_order", "aggregate_hash"])
def test_source_and_receipt_custody_is_complete(report, tmp_path, monkeypatch, target):
    f = fixture_comparison(report, tmp_path, monkeypatch)
    if target == "source":
        (f.root / "forecast/wildfire/model.py").write_text("# changed consumed model source\n")
    elif target == "new_source_file":
        (f.root / "forecast/wildfire/new_dependency.py").write_text("# unlisted new source\n")
    elif target == "protocol":
        write(f.evidence / "RUN_PROTOCOL.json", dict(changed=True))
    elif target.startswith("source_"):
        rec = json.loads(f.receipts[0].read_text())
        if target == "source_extra": rec["source_sha256"]["unknown.py"] = "a" * 64
        elif target == "source_auditor": rec["source_sha256"]["research/forecast-v2/scripts/audit_fit_coverage.py"] = "f" * 64
        else: rec["source_sha256"].pop("forecast/wildfire/model.py")
        write(f.receipts[0], rec); resign(report, f)
    elif target == "receipt":
        rec = json.loads(f.receipts[0].read_text()); rec["exit_code"] = 1; write(f.receipts[0], rec); resign(report, f)
    elif target == "log": f.receipts[0].with_suffix(".log").write_text("Changed after receipt\n")
    elif target == "output": f.outputs[0].write_text(f.outputs[0].read_text() + " ")
    elif target == "missing_receipt": f.receipts[0].unlink()
    elif target == "receipt_pin_order":
        obj = json.loads(f.aggregate.read_text()); obj["case_receipts"].reverse(); write(f.aggregate, obj); resign_aggregate(report, f)
    else:
        rec = json.loads(f.aggregate_receipt.read_text()); rec["output_sha256"] = "a" * 64; write(f.aggregate_receipt, rec)
    with pytest.raises((ValueError, FileNotFoundError)): report.load_comparison(f.run)


def test_survey_endpoint_is_the_exact_frozen_fraction_and_json_keys_cannot_duplicate(report, tmp_path, monkeypatch):
    f = fixture_comparison(report, tmp_path, monkeypatch)
    original = f.outputs[6].read_bytes()
    alter_row(f, 6, lambda rows: rows[-1].update(hours=24.))
    resign(report, f)
    with pytest.raises(ValueError, match="cutoff/horizon"): report.load_comparison(f.run)
    f.outputs[6].write_bytes(original); resign(report, f)
    duplicate = f.aggregate.read_text().replace('"checkpoint_sha256":', '"checkpoint_sha256": "untrusted", "checkpoint_sha256":', 1)
    f.aggregate.write_text(duplicate)
    rec = json.loads(f.aggregate_receipt.read_text()); rec["output_sha256"] = report.sha256(f.aggregate); write(f.aggregate_receipt, rec)
    with pytest.raises(ValueError, match="duplicate object keys"): report.load_comparison(f.run)


def test_effective_last_command_controls_are_checked(report, tmp_path, monkeypatch):
    f = fixture_comparison(report, tmp_path, monkeypatch)
    rec = json.loads(f.receipts[0].read_text()); rec["command"] += ["--seed", "7", "--seed", "0"]
    write(f.receipts[0], rec); resign(report, f)
    assert report.load_comparison(f.run)[1]["execution_complete"] is True
    rec["command"] += ["--seed", "7"]; write(f.receipts[0], rec); resign(report, f)
    with pytest.raises(ValueError, match="effective command"): report.load_comparison(f.run)
    rec["command"].pop(); write(f.receipts[0], rec); resign(report, f)
    with pytest.raises(ValueError, match="effective command"): report.load_comparison(f.run)


def test_unknown_original_auditor_is_refused_and_reviewed_current_repair_preserves_original(report, tmp_path, monkeypatch):
    f = fixture_comparison(report, tmp_path, monkeypatch)
    auditor = f.root / "research/forecast-v2/scripts/audit_fit_coverage.py"
    old = auditor.read_bytes(); old_sha = report.sha256(auditor)
    snapshot = f.evidence / f"source_snapshots/{old_sha}/audit_fit_coverage.py.gz"
    snapshot.parent.mkdir(parents=True); snapshot.write_bytes(gzip.compress(old, mtime=0))
    auditor.write_text("# explicitly reviewed synthetic auditor metadata repair\n")
    with pytest.raises(ValueError, match="reviewed current auditor"): report.load_comparison(f.run)
    monkeypatch.setattr(report, "COMPARISON_CURRENT_AUDITORS", {old_sha, report.sha256(auditor)})
    _, result = report.load_comparison(f.run)
    assert result["authentication"]["original_auditor_sha256"] == old_sha
    assert result["authentication"]["current_auditor_sha256"] == report.sha256(auditor)
    snapshot.write_bytes(gzip.compress(b"corrupted original", mtime=0))
    with pytest.raises(ValueError): report.load_comparison(f.run)


def test_exact_archived_old1753_producer_with_live65_and_fully_resigned_numeric_drift(report, tmp_path, monkeypatch):
    f = fixture_comparison(report, tmp_path, monkeypatch)
    archive = Path(__file__).resolve().parents[2] / "research/forecast-v2/review/comparison_reporting_repair_v1/producer_auditors"
    old = gzip.decompress((archive / "F1753.py.gz").read_bytes())
    current = gzip.decompress((archive / "F65.py.gz").read_bytes())
    old_sha = hashlib.sha256(old).hexdigest()
    current_sha = hashlib.sha256(current).hexdigest()
    assert old_sha == "1753cf31b21be093e13d61a107e407cf41542e9ec6dbe4c8ced924f5a5320cf4"
    assert current_sha == "65a7917868b70e00881722bda8ab2af71688fe78bf88128fad0376537f1d6536"
    auditor = f.evidence / "scripts/audit_fit_coverage.py"
    auditor.write_bytes(old)
    sources = source_map(f.root)
    frozen_anchor = hashlib.sha256(json.dumps(sources, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    monkeypatch.setattr(report, "COMPARISON_SOURCE_SHA256", frozen_anchor)
    monkeypatch.setattr(report, "COMPARISON_AUDITOR_SHA256", old_sha)
    monkeypatch.setattr(report, "COMPARISON_CURRENT_AUDITORS", {old_sha, current_sha})
    snapshot = f.evidence / f"source_snapshots/{old_sha}/audit_fit_coverage.py.gz"
    snapshot.parent.mkdir(parents=True); snapshot.write_bytes(gzip.compress(old, mtime=0))
    def replace_all_maps(mapping):
        for p in [*f.receipts, f.aggregate_receipt]:
            rec = json.loads(p.read_text()); rec["source_sha256"] = mapping; write(p, rec)
        resign(report, f)
    replace_all_maps(sources)
    assert report.load_comparison(f.run)[1]["authentication"]["current_auditor_sha256"] == old_sha
    auditor.write_bytes(current)
    assert report.load_comparison(f.run)[1]["authentication"]["current_auditor_sha256"] == current_sha
    auditor.write_bytes(current + b"\n# unknown auditor version\n")
    unknown = source_map(f.root); unknown["research/forecast-v2/scripts/audit_fit_coverage.py"] = old_sha
    replace_all_maps(unknown)
    with pytest.raises(ValueError, match="reviewed current auditor"): report.load_comparison(f.run)
    auditor.write_bytes(current)
    (f.root / "forecast/wildfire/model.py").write_text("# changed numerical dependency, all receipts resigned\n")
    changed = source_map(f.root); changed["research/forecast-v2/scripts/audit_fit_coverage.py"] = old_sha
    replace_all_maps(changed)
    assert report.COMPARISON_SOURCE_SHA256 == frozen_anchor
    with pytest.raises(ValueError, match="complete original producer source closure"): report.load_comparison(f.run)


@pytest.mark.parametrize("mutation", ["false_zero", "active_zero", "bad_reference", "nonfinite", "range", "count"])
def test_metric_absence_and_support_are_never_fabricated(report, tmp_path, monkeypatch, mutation):
    f = fixture_comparison(report, tmp_path, monkeypatch, all_null=mutation in ("false_zero", "bad_reference"))
    def change(rows):
        if mutation == "false_zero": rows[0]["rmse_all"] = 0.
        elif mutation == "bad_reference": rows[0]["brier_mc"] = 0.
        elif mutation == "active_zero": rows[3]["rmse_active"] = 0.
        elif mutation == "nonfinite": rows[0]["rmse_active"] = float("inf")
        elif mutation == "range": rows[0]["rmse_active"] = 1.1
        else: rows[0]["active_cells"] = rows[0]["cells"] + 1
    alter_row(f, 0, change); resign(report, f)
    with pytest.raises(ValueError): report.load_comparison(f.run)


@pytest.mark.parametrize("all_null", [False, True])
def test_plot_preserves_null_positions_and_discloses_cutoff_event_counts(report, tmp_path, monkeypatch, all_null):
    f = fixture_comparison(report, tmp_path, monkeypatch, all_null=all_null)
    frame, result = report.load_comparison(f.run)
    saved = []
    real_save = report.save
    def capture(fig, out, name):
        saved.append(fig)
        real_save(fig, out, name)
    monkeypatch.setattr(report, "save", capture)
    out = tmp_path / "figures"
    evidence = report.figure_meanfield(report.style(), frame, out, " [SYNTHETIC]")
    lines = saved[0].axes[0].lines
    assert list(lines[0].get_xdata()) == [1, 3, 6, 12, 24]
    assert np.isnan(lines[0].get_ydata()[-2:]).all()
    support = evidence["support_by_horizon"]
    for h in (12, 24):
        row = next(r for r in support if r["country"] == "KR" and r["hours"] == h)
        assert (row["available_cutoffs"], row["declared_cutoffs"]) == (0, 6)
        assert (row["available_catalog_events"], row["declared_catalog_events"]) == (0, 3)
    us = next(r for r in support if r["country"] == "US" and r["hours"] == 1)
    assert us["declared_catalog_events"] == us["declared_cutoffs"] == 6
    assert evidence["metric_data_available"] is (not all_null)
    assert result["execution_complete"] is True
    assert result["metric_data_available"] is (not all_null)
    svg = (out / "fig04_meanfield_vs_mc_rmse_by_horizon.svg").read_text()
    assert "unique catalog events" in svg and "not CI" in svg and "not physical flaming" in svg
    assert "C 0/6" in svg and "E 0/3 U" in svg
    if all_null:
        assert "UNAVAILABLE: no active supported cells" in svg
        assert np.isnan(lines[0].get_ydata()).all()
    assert Image.open(out / "fig04_meanfield_vs_mc_rmse_by_horizon.png").size == (1050, 720)


def test_known_support_metrics_are_separate_from_absent_active_figure_points(report, tmp_path, monkeypatch):
    f = fixture_comparison(report, tmp_path, monkeypatch)
    for index in range(12):
        def zero_active(rows):
            for row in rows:
                if row["cells"]:
                    row.update(active_cells=0, rmse_active=None, rmse_all=.00005,
                        mean_mc=.0002, mean_mf=.00025, expected_new_cells_mc=.0006,
                        expected_new_cells_mf=.00075, max_abs_difference=.00005)
                    if "brier_mc" in row:
                        row.update(brier_mc=((1 - .0002) ** 2 + 2 * .0002 ** 2) / 3,
                                   brier_mf=((1 - .00025) ** 2 + 2 * .00025 ** 2) / 3)
        alter_row(f, index, zero_active)
    resign(report, f)
    frame, result = report.load_comparison(f.run)
    assert result["execution_complete"] is True and result["metric_data_available"] is True
    assert result["metric_availability"]["known_support_rmse"] is True
    assert result["metric_availability"]["fixed_horizon_active_rmse"] is False
    evidence = report.figure_meanfield(report.style(), frame, tmp_path / "figure", "")
    assert evidence["metric_data_available"] is False


def test_main_uses_authenticated_loader_and_retains_execution_metric_distinction(report, tmp_path, monkeypatch):
    f = fixture_comparison(report, tmp_path, monkeypatch, all_null=True)
    out = tmp_path / "report-output"
    monkeypatch.setattr(sys, "argv", ["report.py", "--run", str(f.run), "--out", str(out), "--label", "SYNTHETIC"])
    report.main()
    result = json.loads((out / "RESULTS.json").read_text())
    assert result["meanfield_vs_mc"]["execution_complete"] is True
    assert result["meanfield_vs_mc"]["metric_data_available"] is False
    assert result["figure_evidence"]["fig04_meanfield_vs_mc_rmse_by_horizon"]["metric_data_available"] is False
    f.aggregate_receipt.unlink()
    with pytest.raises(FileNotFoundError): report.main()


def test_all_existing_metric_selection_and_gate_functions_keep_exact_ast():
    repo = Path(__file__).resolve().parents[2]
    before = gzip.decompress((repo / "research/forecast-v2/review/comparison_reporting_repair_v1/report_before.py.gz").read_bytes()).decode()
    after = (repo / "research/forecast-v2/scripts/report.py").read_text()
    old = {node.name: ast.dump(node, include_attributes=False) for node in ast.parse(before).body if isinstance(node, ast.FunctionDef)}
    new = {node.name: ast.dump(node, include_attributes=False) for node in ast.parse(after).body if isinstance(node, ast.FunctionDef)}
    for name, body in old.items():
        if name not in ("main", "figure_meanfield"):
            assert new[name] == body, name
