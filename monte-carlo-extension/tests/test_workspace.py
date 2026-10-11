"""Compatibility and import safety across the reorganized workspace."""

import importlib
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


WORKSPACE = Path(__file__).resolve().parents[1]


def test_training_helpers_keep_their_original_imports():
    import wildfire.cache as cache
    import wildfire.metrics as metrics
    import wildfire.utils as runtime
    import wildfire.train as train

    for module, names in (
        (cache, ("CachedSplit", "cache_kernel_size", "load_split", "fit_normalization")),
        (metrics, ("brier", "weighted_rank_metrics", "probability_metrics",
                   "weighted_calibration", "scoped_metrics", "country_for_event", "split_metrics")),
        (runtime, ("write_json", "choose_device")),
    ):
        for name in names:
            assert getattr(train, name) is getattr(module, name)


def test_evaluation_and_preparation_do_not_import_training_or_examples():
    code = "\nimport importlib\nimport sys\nprefix = 'wildfire'\nfor suffix in ('evaluate', 'prepare'):\n    importlib.import_module(prefix + '.' + suffix)\nassert prefix + '.train' not in sys.modules\nassert prefix + '.examples' not in sys.modules\n"
    subprocess.run([sys.executable, "-c", code], cwd=WORKSPACE, check=True)


def test_radiation_package_remains_usable_without_the_integration_dependencies():
    code = "\nimport importlib.abc\nimport sys\nclass CoreOnly(importlib.abc.MetaPathFinder):\n    def find_spec(self, fullname, path=None, target=None):\n        if fullname.split('.')[0] in {'torch', 'rasterio', 'pandas', 'scipy', 'matplotlib', 'pyproj'}:\n            raise ImportError('Core radiation must not require ' + fullname)\nsys.meta_path.insert(0, CoreOnly())\nfrom wildfire.heat import AffineGrid\nfrom wildfire.heat import ExpectedHeatFluxModel\nfrom wildfire.heat import WildfireHeatModel\ngrid = AffineGrid.from_cell_size(10.0)\nmodel = ExpectedHeatFluxModel(grid=grid, heat_release_rate_density_w_m2=0.0,\n                              radiative_fraction=0.3, emission_height_m=5.0)\nassert model.predict_details([[0.5]]).incident_heat_flux_w_m2.item() == 0.0\n"
    subprocess.run([sys.executable, "-c", code], cwd=WORKSPACE, check=True)


def test_environmental_tools_do_not_run_when_imported(tmp_path, monkeypatch):
    import wildfire.environment as acquire_environment
    import requests

    def forbidden_request(*args, **kwargs):
        raise AssertionError("Importing a tool must not download data")

    monkeypatch.setattr(requests.sessions.Session, "request", forbidden_request)
    monkeypatch.setattr(acquire_environment, "ROOT", tmp_path)
    importlib.reload(acquire_environment)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("raises", [False, True])
def test_unified_command_forwards_original_options_and_restores_arguments(monkeypatch, raises):
    import wildfire.__main__ as cli

    original = sys.argv
    observed = []

    def original_main():
        observed.extend(sys.argv[1:])
        if raises:
            raise ValueError("workflow failure")
        return "completed"

    def load_module(name, *, package):
        assert name == '.train'
        assert package == 'wildfire'
        return SimpleNamespace(train_main=original_main)

    monkeypatch.setattr(cli, "import_module", load_module)
    arguments = ["train", "--data-dir", "a path with spaces", "--help"]
    if raises:
        with pytest.raises(ValueError, match="workflow failure"):
            cli.main(arguments)
    else:
        assert cli.main(arguments) == "completed"
    assert observed == arguments[1:]
    assert sys.argv is original


def test_check_model_forwards_its_supported_output_option(tmp_path, monkeypatch):
    import argparse
    import wildfire.__main__ as cli
    import wildfire.checks as checks

    output = tmp_path / "a directory with spaces" / "model_verification.json"
    original = sys.argv
    observed = []

    def bounded_model_check():
        parser = argparse.ArgumentParser()
        parser.add_argument("--output", type=Path)
        options = parser.parse_args()
        observed.append(options.output)
        return "validated"

    monkeypatch.setattr(checks, "model_main", bounded_model_check)
    assert cli.main(["check-model", "--output", str(output)]) == "validated"
    assert observed == [output]
    assert sys.argv is original
    assert not output.exists()


def test_check_model_help_exits_before_loading_real_data(monkeypatch):
    import wildfire.__main__ as cli
    import wildfire.checks as checks

    def forbidden_dataset(*args, **kwargs):
        raise AssertionError("Help must not load or validate real data")

    monkeypatch.setattr(checks, "WildfireSequenceDataset", forbidden_dataset)
    with pytest.raises(SystemExit) as stopped:
        cli.main(["check-model", "--help"])
    assert stopped.value.code == 0


@pytest.mark.parametrize("command", ["biome", "build-bundle"])
def test_help_cannot_start_argument_free_acquisition_or_reconstruction(monkeypatch, command):
    import wildfire.__main__ as cli

    def forbidden_main():
        raise AssertionError("Help must not run the workflow")

    monkeypatch.setattr(cli, "import_module", lambda *args, **kwargs: SimpleNamespace(
        main=forbidden_main, __doc__="A data workflow",
    ))
    with pytest.raises(SystemExit) as stopped:
        cli.main([command, "--help"])
    assert stopped.value.code == 0
