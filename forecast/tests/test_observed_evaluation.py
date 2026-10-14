"""Independent survey endpoints, fractional spread, and label-free inputs."""
import json
import math
from pathlib import Path
from types import SimpleNamespace

from affine import Affine
import numpy as np
from pyproj import Transformer
import pytest
from shapely.geometry import box, mapping
from shapely.ops import transform as project_geometry
import torch

from tests.loader.test_dataset import bundle
from tests.test_farsite_inputs import physical_region
from tests.test_rollout import _inputs, _model
from wildfire.data import load_data
from wildfire.farsite_inputs import prepare_farsite_inputs
from wildfire.observed_evaluation import (
    M548_SHA256, ObservedEvaluationConfig, exact_survey_prediction, run_observed_evaluation, survey_reference,
)


START = "2024-08-22T08:02:00Z"
END = "2024-08-23T02:14:00Z"


def _surveys(tmp_path):
    transform = Affine(375, 0, -1141125, 0, -375, 2393250)
    grid = dict(id="WY-BTF-002416_FishCreek", epsg=5070, height=3, width=4,
                transform=list(transform)[:6])
    inverse = Transformer.from_crs(5070, 4326, always_xy=True).transform
    def polygon(first_col, last_col):
        left, top = transform * (first_col, 0)
        right, bottom = transform * (last_col, 1)
        return project_geometry(inverse, box(left + 1, bottom + 1, right - 1, top - 1))
    features = [dict(type="Feature", properties=dict(time_utc=START, source_record_id=1),
                     geometry=mapping(polygon(0, 1))),
                # Later active extent can omit a previously mapped cell. The
                # cumulative reference must retain the initial polygon.
                dict(type="Feature", properties=dict(time_utc=END, source_record_id=2),
                     geometry=mapping(polygon(1, 3))),
                dict(type="Feature", properties=dict(time_utc="2024-08-24T02:14:00Z", source_record_id=3),
                     geometry=mapping(polygon(3, 4)))]
    path = tmp_path / "surveys.geojson"
    path.write_text(json.dumps(dict(type="FeatureCollection", features=features)))
    return path, grid


def test_reference_uses_actual_endpoint_unions_without_future_polygon_leak(tmp_path):
    path, grid = _surveys(tmp_path)
    reference, audit = survey_reference(path, grid, START, END)
    np.testing.assert_array_equal(reference["burned_area"][0, 0, 0], [1, 0, 0, 0])
    np.testing.assert_array_equal(reference["burned_area"][1, 0, 0], [1, 1, 1, 0])
    assert audit["states"][0]["source_record_ids"] == [1]
    assert audit["states"][1]["source_record_ids"] == [1, 2]
    assert not audit["reconstructed_fire_labels_used"]
    assert not audit["survey_coverage_footprint_available"]
    assert (reference["time_utc"][1] - reference["time_utc"][0]).item() == 1092 * 60


def test_reference_rejects_rounded_or_interpolated_endpoint(tmp_path):
    path, grid = _surveys(tmp_path)
    with pytest.raises(ValueError, match="No actual NIROPS survey"):
        survey_reference(path, grid, START, "2024-08-23T02:00:00Z")


def test_fractional_final_transition_matches_exact_directed_chain():
    old_threads = torch.get_num_threads()
    torch.set_num_threads(1)
    try:
        model = _model()
        burned, features = _inputs(leading=(1,))
        sample = dict(burned_area=burned, features=features, channel_names=model.channel_names,
                      burned_area_valid=torch.ones_like(burned, dtype=torch.bool),
                      feature_valid=torch.ones_like(features, dtype=torch.bool))
        n = 8192
        result = exact_survey_prediction(model, sample, 1.5, n_samples=n, seed=7, trajectory_batch_size=32)
        p = result.at(hours=1.5).probability[0, 0]
        expected_b = 1 - 2 ** -1.5
        expected_c = .5 * (1 - 2 ** -.5)
        for actual, expected in ((p[2, 2].item(), expected_b), (p[2, 3].item(), expected_c)):
            tolerance = 6 * math.sqrt(expected * (1 - expected) / n)
            assert abs(actual - expected) <= tolerance
        assert p[2, 1] == 0
        assert result.at(hours=1.5).burned_probability[0, 0, 2, 1] == 1
        assert result.metadata["step_durations_hours"] == [1.0, .5]
        with pytest.raises(ValueError, match="whole-hour"):
            model.predict_cumulative(sample, hours=[1.5])
    finally:
        torch.set_num_threads(old_threads)


def test_exact_minute_alignment_uses_integer_survey_time_difference():
    """65/60 hours has a nonintegral floating-point product with 3600."""
    model = _model()
    burned, features = _inputs(leading=(1,))
    cutoff = 1_724_313_720
    sample = dict(burned_area=burned, features=features, channel_names=model.channel_names,
        burned_area_valid=torch.ones_like(burned, dtype=torch.bool),
        feature_valid=torch.ones_like(features, dtype=torch.bool),
        time_utc=torch.tensor([cutoff]), time_valid=torch.ones(1, dtype=torch.bool))
    hours = 65 / 60
    assert not (hours * 3600).is_integer()
    result = exact_survey_prediction(model, sample, hours, n_samples=4, seed=0, trajectory_batch_size=4)
    reference = dict(burned_area=torch.cat([burned, burned], dim=0),
        burned_area_valid=torch.ones((2, 1, 5, 6), dtype=torch.bool),
        time_utc=torch.tensor([cutoff, cutoff + 65 * 60]), time_valid=torch.ones(2, dtype=torch.bool))
    start, start_valid, end, end_valid = result._aligned_burned_states(reference, hours=hours)
    assert start_valid.all() and end_valid.all()
    np.testing.assert_array_equal(start, end)
    assert result.evaluate(reference, hours=hours, quantity="burned")["per_horizon"][0]["coverage"]["evaluated_cells"] == 30


def test_environment_only_loader_never_opens_reconstruction_files(bundle, monkeypatch):
    from wildfire.data import WildfireSequenceDataset
    original = WildfireSequenceDataset._read
    def guarded(self, path, *args, **kwargs):
        if path.name in ("arrival_time_hours.tif", "kriging_std_hours.tif"):
            raise AssertionError("Reconstructed fire labels were opened")
        return original(self, path, *args, **kwargs)
    monkeypatch.setattr(WildfireSequenceDataset, "_read", guarded)
    with load_data(bundle, events=["KR_TEST"], sequence_length=1, include_fire_labels=False) as dataset:
        sample = dataset[0]
    assert sample["feature_valid"].any()
    assert not sample["burned_area_valid"].any()
    assert not sample["arrival_valid"].any()
    assert not sample["arrival_std_valid"].any()


@pytest.mark.parametrize("hours,expected_local_end,expected_utc_end", [
    (18.2, "08 21 1714", "2024-08-22T00:14:00+00:00"),
    (65 / 60, "08 21 0007", "2024-08-21T07:07:00+00:00"),
    (123 / 60, "08 21 0105", "2024-08-21T08:05:00+00:00"),
])
def test_observed_farsite_inputs_use_survey_not_arrival_and_preserve_minutes(
        physical_region, tmp_path, monkeypatch, hours, expected_local_end, expected_utc_end):
    import wildfire.farsite_inputs as module
    root, _, _ = physical_region
    original = module._read_aligned
    def guarded(path, **kwargs):
        if path.name == "arrival_time_hours.tif":
            raise AssertionError("FARSITE observed ignition read reconstructed arrivals")
        return original(path, **kwargs)
    monkeypatch.setattr(module, "_read_aligned", guarded)
    initial = np.array([[0, 1, 0], [0, 0, 0]], dtype="uint8")
    prepared = prepare_farsite_inputs("US_test", "2024-08-21T06:02:00Z", hours,
        tmp_path / "observed", data_root=root, observed_initial=initial,
        observed_initial_valid=np.ones_like(initial, dtype=bool),
        observed_initial_source=dict(path="direct-survey.geojson", sha256="fixture"))
    np.testing.assert_array_equal(prepared.initial_burned, initial)
    text = prepared.input_path.read_text()
    assert "FARSITE_START_TIME: 08 20 2302" in text
    assert f"FARSITE_END_TIME: {expected_local_end}" in text
    assert prepared.manifest["weather_source_cutoff_utc"] == "2024-08-21T06:00:00+00:00"
    assert prepared.manifest["cutoff_burn_state_source"]["path"] == "direct-survey.geojson"
    assert prepared.manifest["hours"] == hours
    assert prepared.manifest["endpoint_utc"] == expected_utc_end


def test_observed_farsite_import_includes_exact_final_minute():
    from wildfire.farsite_evaluation import farsite_cumulative_prediction
    hours = 123 / 60
    assert hours * 60 < 123
    sample = dict(burned_area=np.zeros((1, 1, 1, 3)), time_utc=np.array([1_724_313_720]))
    result = farsite_cumulative_prediction(np.array([[123., 123.0001, -9999.]]), sample,
        hours=[hours], arrival_origin_time_utc=1_724_313_720, no_burn_value=-9999,
        coverage=np.ones((1, 3), dtype=bool), _exact_duration_minutes=123)
    np.testing.assert_array_equal(result.at(hours=hours).probability, [[[[1, 0, 0]]]])
    assert result.metadata["exact_duration_minutes"] == 123
    with pytest.raises(ValueError, match="positive integer"):
        farsite_cumulative_prediction(np.array([[123., 123.0001, -9999.]]), sample,
            hours=[hours], arrival_origin_time_utc=1_724_313_720, no_burn_value=-9999,
            coverage=np.ones((1, 3), dtype=bool), _exact_duration_minutes=124)


def test_cli_help_does_not_run_evaluation():
    from wildfire.observed_evaluation import main
    with pytest.raises(SystemExit) as result:
        main(["--help"])
    assert result.value.code == 0


@pytest.mark.parametrize("command,result", [("evaluate-observed", {}),
                                            ("evaluate-observed-combined", {}),
                                            ("audit-observed", None),
                                            ("acquire-observed-data", Path("observations.geojson"))])
def test_console_commands_return_success_without_dumping_python_results(monkeypatch, command, result):
    import wildfire.__main__ as module
    monkeypatch.setattr(module, "import_module", lambda *args, **kwargs: SimpleNamespace(main=lambda: result))
    assert module.main([command]) is None


def test_matched_runner_exports_every_score_from_identical_observed_entries(tmp_path, monkeypatch, capsys):
    """Exercise actual preparation/scoring/export orchestration with fake native I/O.

    The learned transition is real; only environmental file loading and the
    external simulator process are replaced. No real-data evaluation is run.
    """
    import wildfire.observed_evaluation as module
    from wildfire.observed_data import ARCHIVE_SHA256, DOI
    path, grid = _surveys(tmp_path)
    data_root = tmp_path / "data"
    region = data_root / "regions" / grid["id"]
    region.mkdir(parents=True)
    (region / "grid.json").write_text(json.dumps(grid))
    checkpoint = tmp_path / "checkpoint.pt"
    checkpoint.write_bytes(b"pinned-checkpoint-fixture")
    original_digest = module._sha256
    monkeypatch.setattr(module, "_sha256", lambda value: M548_SHA256 if Path(value) == checkpoint else original_digest(value))
    (tmp_path / "provenance.json").write_text(json.dumps(dict(geojson_sha256=original_digest(path),
        archive_sha256=ARCHIVE_SHA256, dataset_doi=DOI, incident_number="WY-BTF-002416")))
    model = _model()
    monkeypatch.setattr(module, "load_model", lambda *args, **kwargs: model)
    def environment(model, config, reference):
        features = torch.full((1, 2, 3, 4), math.log(2), dtype=torch.float64)
        features[:, 1] = 7
        sample = dict(features=features, feature_valid=torch.ones_like(features, dtype=torch.bool),
            channel_names=model.channel_names, burned_area=reference["burned_area"][:1].double(),
            burned_area_valid=reference["burned_area_valid"][:1],
            **{key: reference[key] for key in ("pixel_valid", "epsg", "affine_transform", "event_id")},
            time_valid=torch.ones(1, dtype=torch.bool), time_utc=reference["time_utc"][:1])
        return sample, "2024-08-22T08:00:00+00:00"
    monkeypatch.setattr(module, "observed_environment", environment)
    engine = tmp_path / "engine" / "src" / "TestFARSITE"
    engine.parent.mkdir(parents=True)
    engine.write_bytes(b"fake-native-engine")
    probe = engine.parent.parent / "probe"
    probe.write_bytes(b"fake-clock-probe")
    manifest = dict(executable_sha256=original_digest(engine), clock_loading_changes=True,
                    native_clock_probe=str(probe), native_clock_probe_sha256=original_digest(probe),
                    clock_assignment_correction="fixture minute preserving")
    (engine.parent.parent / "observed_build_manifest.json").write_text(json.dumps(manifest))
    def prepare(event, cutoff, hours, output, **kwargs):
        output.mkdir()
        lcp, scenario = output / "landscape.lcp", output / "scenario.input"
        lcp.write_bytes(b"fixture")
        scenario.write_text("fixture")
        affine = Affine(*grid["transform"]) @ Affine.translation(-1, -1)
        left, top = affine * (0, 0)
        right, bottom = affine * (6, 5)
        return SimpleNamespace(lcp_path=lcp, input_path=scenario, original_shape=(3, 4), boundary_padding=1,
            environment_valid=np.ones((3, 4), dtype=bool),
            manifest=dict(clock=dict(start_local=START.replace("Z", "+00:00"), end_local=END.replace("Z", "+00:00")),
                fuel_moisture_scenario_percent=dict(dead_1h_percent=6),
                landscape=dict(shape=[5, 6], bounds=[left, bottom, right, top], transform=list(affine)[:6])))
    monkeypatch.setattr(module, "prepare_farsite_inputs", prepare)
    def native(args, **kwargs):
        if Path(args[0]) == probe:
            return SimpleNamespace(stdout='{"start_hhmm":802,"end_hhmm":214,"duration_minutes":1092}\n', returncode=0)
        simulation = kwargs["cwd"]
        affine = Affine(*grid["transform"]) @ Affine.translation(-1, -1)
        left, bottom = affine * (0, 5)
        header = f"ncols 6\nnrows 5\nxllcorner {left}\nyllcorner {bottom}\ncellsize 375\nNODATA_value -9999\n"
        (simulation / "outputs/farsite_ArrivalTime.asc").write_text(header + "\n".join([" ".join(["-9999"] * 6)] * 5))
        (simulation / "outputs/farsite_Timings.txt").write_text(
            "Total Sim Time: 1092\nFarsite Start Time: 08 22 0800\nFarsite End Time: 08 23 0200\n"
            "Simulation Started: 8/22 8:00\nSimulation Ended: 8/23 2:14\nElapsed Time: 0 18:12\n")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(module.subprocess, "run", native)
    output = tmp_path / "result"
    monkeypatch.chdir(tmp_path)
    report = run_observed_evaluation(ObservedEvaluationConfig(observations=path, data_root=data_root,
        checkpoint=checkpoint, output_dir=output, n_samples=8, trajectory_batch_size=4,
        threads=1, plots=True, engine=engine.relative_to(tmp_path), hours=18.2))
    assert report["status"] == "complete"
    assert report["native_clock_verification"]["duration_minutes"] == 1092
    assert report["counts"]["initial_mapped_cells"] == 1
    assert report["counts"]["newly_mapped_cells"] == 2
    assert len(report["summary"]) == 8
    shared = [row for row in report["summary"] if row["cohort"] == "shared_models"]
    for quantity in ("new_burn", "burned"):
        rows = [row for row in shared if row["quantity"] == quantity]
        assert len({row["metrics"]["sample_count"] for row in rows}) == 1
        assert len({row["metrics"]["positive_sample_count"] for row in rows}) == 1
        for row in rows:
            assert "bernoulli_kl_divergence_mean" in row["metrics"]
            assert "bernoulli_wasserstein_2_distance_mean" in row["metrics"]
            assert "mcc" in row["classification"]
    with np.load(output / "reference.npz", allow_pickle=False) as saved:
        assert saved["time_utc"][1] - saved["time_utc"][0] == 1092 * 60
    assert (output / "report.md").exists()
    assert (output / "m548_prediction.npz").exists()
    assert (output / "farsite_prediction.npz").exists()
    assert len(report["plots"]["figures"]) == 20
    assert len(list((output / "plots").glob("*.png"))) == 20
    assert len(list((output / "plots").glob("*.svg"))) == 20
    markdown = (output / "report.md").read_text()
    assert "Shared coverage" in markdown and "Individual model coverage" in markdown
    assert "Fixed calibration bins" in markdown and "zero-denominator" in markdown
    assert "NIROPS mapped-perimeter outcome fraction" in (output / "plots/burned_reliability.svg").read_text()
    display = capsys.readouterr()
    assert "M548 simulation steps" in display.err and "ETA" in display.err
    assert "FARSITE simulation [complete]" in display.err
    assert "M548: simulating" not in display.out
    assert "FARSITE: preparing" not in display.out
