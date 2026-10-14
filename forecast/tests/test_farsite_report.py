"""Native completion/geometry oracles and bounded report-runner integration."""
from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
from types import SimpleNamespace

from affine import Affine
import numpy as np
import pytest

import wildfire.farsite_report as report_module
from wildfire.farsite_inputs import FuelMoistureScenario
from wildfire.farsite_report import (
    FarsiteEvaluationConfig, read_engine_output, run_farsite_evaluation,
)


def _prepared(directory, *, padding=1, coverage=None):
    transform = Affine(375, 0, -1141125, 0, -375, 2393250)
    original_shape = (2, 3)
    native_transform = transform @ Affine.translation(-padding, -padding)
    native_shape = (2 + padding * 2, 3 + padding * 2)
    west, north = native_transform.c, native_transform.f
    south = north - native_shape[0] * 375
    east = west + native_shape[1] * 375
    initial = np.array([[True, False, False], [False, False, False]])
    manifest = dict(
        cutoff_utc="2024-08-21T06:00:00+00:00", endpoint_utc="2024-08-21T12:00:00+00:00",
        original_shape=list(original_shape), original_epsg=5070,
        boundary_padding_cells=padding,
        clock=dict(start_local="2024-08-20T23:00:00-07:00",
                   end_local="2024-08-21T05:00:00-07:00", utc_offset_hours=-7),
        landscape=dict(shape=list(native_shape), bounds=[west, south, east, north],
                       transform=list(native_transform)[:6]),
        fuel_moisture_scenario_percent=dict(dead_1h_percent=6, dead_10h_percent=7,
            dead_100h_percent=8, live_herb_percent=60, live_woody_percent=90, foliar_percent=100),
        cloud_cover_scenario_percent=0, scenario_kind="deterministic fixed moisture scenario",
    )
    return SimpleNamespace(manifest=manifest, original_shape=original_shape,
        transform=transform, epsg=5070, boundary_padding=padding,
        initial_burned=initial, initial_burned_valid=np.ones(original_shape, bool),
        environment_valid=np.ones(original_shape, bool) if coverage is None else coverage,
        lcp_path=directory / "landscape.lcp", input_path=directory / "scenario.input",
        ignition_path=directory / "ignition.shp", raws_path=directory / "cutoff_weather.raws",
        manifest_path=directory / "input_manifest.json")


def _native_files(directory, prepared, *, arrival=None, edits=None, timing_edits=None):
    output = directory / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    shape = tuple(prepared.manifest["landscape"]["shape"])
    bounds = prepared.manifest["landscape"]["bounds"]
    header = dict(NCOLS=shape[1], NROWS=shape[0], XLLCORNER=bounds[0],
                  YLLCORNER=bounds[1], CELLSIZE=375, NODATA_VALUE=-9999)
    header.update(edits or {})
    if arrival is None:
        arrival = np.full(shape, -9999., dtype=float)
        pad = prepared.boundary_padding
        rows = slice(pad, pad + prepared.original_shape[0])
        cols = slice(pad, pad + prepared.original_shape[1])
        arrival[rows, cols] = [[0, 60, 360], [-9999, 360.00001, -9999]]
    path = output / "farsite_ArrivalTime.asc"
    with path.open("w") as stream:
        for key, value in header.items():
            stream.write(f"{key} {value}\n")
        np.savetxt(stream, np.asarray(arrival), fmt="%.10g")
    timing = {"Farsite Start Time": "08 20 2300", "Farsite End Time": "08 21 0500",
              "Total Sim Time": "360.000000", "Simulation Started": "8/20 23:00",
              "Simulation Ended": "08/21 05:00", "Elapsed Time": "00 06:00"}
    timing.update(timing_edits or {})
    timing_path = output / "farsite_Timings.txt"
    timing_path.write_text("Farsite BenchMark Results\n\nSimulation Info:\n"
                           + "\n".join(f"\t{key}:   {value}" for key, value in timing.items()) + "\n")
    return path, timing_path


@pytest.mark.parametrize("padding", [0, 1, 2])
def test_native_output_crop_removes_only_configured_exterior_padding(tmp_path, padding):
    prepared = _prepared(tmp_path, padding=padding)
    _native_files(tmp_path, prepared)
    arrival, execution = read_engine_output(tmp_path, prepared, 6)
    np.testing.assert_array_equal(arrival, [[0, 60, 360], [-9999, 360.00001, -9999]])
    assert arrival.shape == (2, 3)
    assert execution["elapsed_minutes"] == 360
    assert execution["arrival_units"] == "minutes since simulation cutoff"
    assert execution["arrived_cells_after_endpoint"] == 1
    assert len(execution["arrival_sha256"]) == len(execution["timings_sha256"]) == 64


@pytest.mark.parametrize("missing", ["arrival", "timings"])
def test_zero_exit_is_insufficient_without_both_native_outputs(tmp_path, missing):
    prepared = _prepared(tmp_path)
    arrival, timing = _native_files(tmp_path, prepared)
    (arrival if missing == "arrival" else timing).unlink()
    with pytest.raises(RuntimeError, match="required output"):
        read_engine_output(tmp_path, prepared, 6)


@pytest.mark.parametrize("edits", [{"NCOLS": 5.5}, {"NROWS": 3}, {"XLLCORNER": -1141125},
    {"YLLCORNER": 2393250}, {"CELLSIZE": 30}, {"NODATA_VALUE": -999}, {"CELLSIZE": np.nan}])
def test_native_grid_and_sentinel_must_match_full_original_landscape(tmp_path, edits):
    prepared = _prepared(tmp_path)
    _native_files(tmp_path, prepared, edits=edits)
    with pytest.raises(ValueError, match="grid|sentinel|header"):
        read_engine_output(tmp_path, prepared, 6)


def test_native_header_duplicate_and_truncated_data_rejected(tmp_path):
    prepared = _prepared(tmp_path)
    arrival, _ = _native_files(tmp_path, prepared)
    text = arrival.read_text()
    arrival.write_text(text.replace("NROWS 4", "NCOLS 4"))
    with pytest.raises(ValueError, match="distinct"):
        read_engine_output(tmp_path, prepared, 6)
    _native_files(tmp_path, prepared, arrival=np.zeros((3, 5)))
    with pytest.raises(ValueError, match="grid"):
        read_engine_output(tmp_path, prepared, 6)


@pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf, -1, -9998])
@pytest.mark.parametrize("location", [(0, 0), (1, 1)])
def test_invalid_arrival_rejected_even_in_buffer_and_on_missing_coverage(tmp_path, value, location):
    coverage = np.ones((2, 3), bool)
    coverage[0, 0] = False
    prepared = _prepared(tmp_path, coverage=coverage)
    arrival = np.full((4, 5), -9999.)
    arrival[location] = value
    _native_files(tmp_path, prepared, arrival=arrival)
    with pytest.raises(ValueError, match="finite nonnegative"):
        read_engine_output(tmp_path, prepared, 6)


@pytest.mark.parametrize("edits", [{"Total Sim Time": "300"}, {"Total Sim Time": "360.1"},
    {"Farsite Start Time": "08 21 0000"}, {"Farsite End Time": "08 21 0600"}])
def test_declared_native_clock_and_duration_are_exact(tmp_path, edits):
    prepared = _prepared(tmp_path)
    _native_files(tmp_path, prepared, timing_edits=edits)
    with pytest.raises(RuntimeError, match="timing"):
        read_engine_output(tmp_path, prepared, 6)


@pytest.mark.parametrize("edits", [{"Simulation Started": "8/21 00:00"},
    {"Simulation Ended": "8/21 04:00"}, {"Elapsed Time": "00 05:00"}])
def test_actual_native_completion_is_required_in_addition_to_configured_clock(tmp_path, edits):
    prepared = _prepared(tmp_path)
    _native_files(tmp_path, prepared, timing_edits=edits)
    with pytest.raises(RuntimeError, match="timing|completion|elapsed|started|ended"):
        read_engine_output(tmp_path, prepared, 6)


def _reference(prepared):
    cutoff = int(np.datetime64("2024-08-21T06:00:00", "s").astype(np.int64))
    states = np.zeros((7, 1, 2, 3))
    states[:, 0] = prepared.initial_burned
    states[-1, 0, 0, 1] = 1
    states[-1, 0, 0, 2] = 1
    valid = np.ones_like(states, bool)
    reference = dict(burned_area=states, burned_area_valid=valid,
        time_utc=cutoff + np.arange(7) * 3600, time_valid=np.ones(7, bool),
        pixel_valid=np.ones((2, 3), bool), event_id="fixture",
        affine_transform=np.asarray(tuple(prepared.transform)[:6]), epsg=5070)
    cutoff_sample = dict(reference, burned_area=states[:1].copy(), burned_area_valid=valid[:1].copy(),
                         time_utc=reference["time_utc"][:1], time_valid=np.ones(1, bool))
    return reference, cutoff_sample


def _mock_runner(monkeypatch, tmp_path, *, native=True, returncode=0, coverage=None, log_text=""):
    from wildfire.cumulative_report import _sha256
    engine = tmp_path / "engine"
    engine.write_bytes(b"verified fixture binary")
    engine_record = dict(revision=report_module.REVISION, executable_sha256=_sha256(engine))
    prepared = _prepared(tmp_path, coverage=coverage)
    reference, cutoff_sample = _reference(prepared)
    seen = []
    monkeypatch.setattr(report_module, "_engine_record", lambda config: (engine, engine_record))
    monkeypatch.setattr(report_module, "_load_reference", lambda config: (reference, cutoff_sample))
    def prepare(event, cutoff, hours, directory, **kwargs):
        directory.mkdir(parents=True)
        prepared.lcp_path = directory / "landscape.lcp"
        prepared.input_path = directory / "scenario.input"
        prepared.ignition_path = directory / "ignition.shp"
        prepared.manifest_path = directory / "input_manifest.json"
        for path in (prepared.lcp_path, prepared.input_path, prepared.ignition_path):
            path.write_bytes(b"fixture")
        prepared.manifest_path.write_text(json.dumps(prepared.manifest))
        assert kwargs["moisture"] == FuelMoistureScenario()
        return prepared
    monkeypatch.setattr(report_module, "prepare_farsite_inputs", prepare)
    def run(args, *, cwd, stdout, stderr, timeout, check):
        seen.append(dict(args=args, cwd=cwd, timeout=timeout))
        assert (cwd / "command.txt").read_text() == "landscape.lcp scenario.input ignition.shp 0 outputs/farsite 1\n"
        assert args == [str(engine), "command.txt"] and not check
        if native:
            _native_files(cwd, prepared)
        stdout.write(log_text)
        return SimpleNamespace(returncode=returncode)
    monkeypatch.setattr(report_module.subprocess, "run", run)
    config = FarsiteEvaluationConfig(event="fixture", output_dir=tmp_path / "report", plots=False)
    return config, prepared, seen


def test_bounded_end_to_end_runner_scores_exact_endpoint_and_writes_distances(monkeypatch, tmp_path):
    config, prepared, seen = _mock_runner(monkeypatch, tmp_path)
    result = run_farsite_evaluation(config)
    assert result["status"] == "complete"
    assert len(seen) == 1 and len(result["summary"]) == 4
    assert result["scenario_counts"] == dict(initial_burned_cells=1, predicted_new_burned_cells=2,
        predicted_total_burned_cells=3, environment_covered_cells=6)
    # The future integration overshoot is present in native output but excluded
    # from the six-hour occupancy. Arrival360 itself is included exactly.
    with np.load(config.output_dir / "prediction.npz") as data:
        np.testing.assert_array_equal(data["probability"].ravel(), [0, 1, 1, 0, 0, 0])
        np.testing.assert_array_equal(data["burned_probability"].ravel(), [1, 1, 1, 0, 0, 0])
        assert data["arrival_time_minutes"][1, 1] > 360
    written = json.loads((config.output_dir / "report.json").read_text())
    assert written["status"] == "complete" and written["protocol"]["scenario_count"] == 1
    for row in result["summary"]:
        assert row["metrics"]["brier"] == 0
        assert row["metrics"]["bernoulli_total_variation_distance_mean"] == 0
        assert "bernoulli_jensen_shannon_distance_mean" in row["metrics"]
    assert (config.output_dir / "report.md").is_file()
    assert (config.output_dir / "summary.csv").is_file()
    assert (config.output_dir / "per_event.csv").is_file()
    assert (config.output_dir / "per_cutoff.csv").is_file()
    assert (config.output_dir / "calibration.csv").is_file()


@pytest.mark.parametrize("native, returncode, expected", [(False, 0, "required output"),
                                                         (True, 2, "status 2")])
def test_runner_failure_writes_failed_record_and_no_complete_metrics(monkeypatch, tmp_path, native, returncode, expected):
    config, prepared, seen = _mock_runner(monkeypatch, tmp_path, native=native, returncode=returncode)
    with pytest.raises(RuntimeError, match=expected):
        run_farsite_evaluation(config)
    result = json.loads((config.output_dir / "report.json").read_text())
    assert result["status"] == "failed" and result["summary"] == []
    assert result["failures"] and len(seen) == 1
    assert not (config.output_dir / "report.md").exists()
    assert not (config.output_dir / "summary.csv").exists()


def test_interior_unknown_environment_prevents_false_coverage_claim(monkeypatch, tmp_path):
    coverage = np.ones((2, 3), bool)
    coverage[0, 2] = False
    config, prepared, seen = _mock_runner(monkeypatch, tmp_path, coverage=coverage)
    with pytest.raises(ValueError, match="complete physical environmental coverage"):
        run_farsite_evaluation(config)
    assert seen == []
    assert json.loads((config.output_dir / "report.json").read_text())["status"] == "failed"


@pytest.mark.parametrize("log_text", ["Error: failed input validation\n", "LaunchFarsite failure\n"])
def test_zero_exit_and_existing_native_files_do_not_override_engine_error(monkeypatch, tmp_path, log_text):
    config, prepared, seen = _mock_runner(monkeypatch, tmp_path, log_text=log_text)
    with pytest.raises(RuntimeError, match="execution/input error"):
        run_farsite_evaluation(config)
    result = json.loads((config.output_dir / "report.json").read_text())
    assert result["status"] == "failed" and result["summary"] == []


def test_existing_results_are_preserved_before_any_reference_or_engine_action(monkeypatch, tmp_path):
    directory = tmp_path / "existing"
    directory.mkdir()
    path = directory / "report.json"
    path.write_text('{"status":"complete"}')
    monkeypatch.setattr(report_module, "_load_reference", lambda config: pytest.fail("must preserve before any load"))
    with pytest.raises(FileExistsError, match="not empty"):
        run_farsite_evaluation(FarsiteEvaluationConfig(output_dir=directory))
    assert path.read_text() == '{"status":"complete"}'


def test_plan_prepares_case_without_native_run_or_metrics(monkeypatch, tmp_path):
    config, prepared, seen = _mock_runner(monkeypatch, tmp_path)
    result = run_farsite_evaluation(replace(config, plan_only=True))
    assert result["status"] == "planned" and result["summary"] == []
    assert seen == []
    assert (config.output_dir / "protocol.json").is_file()
    assert not (config.output_dir / "summary.csv").exists()
    assert not (config.output_dir / "prediction.npz").exists()


@pytest.mark.parametrize("kwargs", [{"hours": 0}, {"hours": 1.5}, {"hours": True},
    {"timeout_seconds": False}, {"boundary_padding": 0}, {"timestep_minutes": 0},
    {"threshold": np.nan}, {"threshold": 1.1}, {"threshold": True},
    {"cutoff": "2024-08-21T06:01:00Z"}, {"cutoff": "2024-08-21T06:00:00"}])
def test_configuration_rejects_invalid_horizons_and_exact_time_contract(kwargs):
    with pytest.raises(ValueError):
        FarsiteEvaluationConfig(**kwargs)


def test_explicit_integer_fuel_moisture_cli_controls_are_accepted(monkeypatch, tmp_path):
    seen = []
    def run(config):
        seen.append(config)
        return dict(status="planned", output_dir=str(tmp_path))
    monkeypatch.setattr(report_module, "run_farsite_evaluation", run)
    report_module.main(["--hours", "6", "--dead-1h-percent", "6", "--live-herb-percent", "60", "--plan-only", "--no-plots"])
    assert seen[0].moisture == FuelMoistureScenario()
    assert not seen[0].plots and seen[0].plan_only
