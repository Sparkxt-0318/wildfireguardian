"""The ``firecast-lab`` CLI and the cross-fitting harness: plumbing only, on a SYNTHETIC data root.

Every row written here is SYNTHETIC and goes to pytest's tmp_path, never to firecast-lab/results/: these tests
produce no leaderboard numbers."""
import csv
import json

import numpy as np
import pytest

import synthetic as syn
from firecast_lab import baselines as bl
from firecast_lab import cli, harness
from firecast_lab import data as fd

FIRES = {"SYNTHETIC_A1": "A", "SYNTHETIC_A2": "A", "SYNTHETIC_B1": "B", "SYNTHETIC_B2": "B", "SYNTHETIC_T": "test"}
SPLITS = syn.splits(**FIRES)
DEV = [f for f, fold in FIRES.items() if fold != "test"]


@pytest.fixture(scope="module")
def root(tmp_path_factory):
    fires = {}
    for i, fire_id in enumerate(FIRES):
        arrival, slope, u, v = syn.fire(seed=10 + i, wind_toward_deg=30.0 * i)
        if i == 0:
            slope[3, 3] = np.nan                                      # a missing input inside the grid
        fires[fire_id] = (arrival, slope, u, v)
    return syn.write_root(tmp_path_factory.mktemp("synthetic_root"), fires)


def _run(root, tmp_path, *args):
    name = args[args.index("--baseline") + 1]
    path = cli.main(["run", *args, "--data-root", str(root), "--out", str(tmp_path / f"{name}.csv")], splits=SPLITS)
    with path.open() as handle:
        return list(csv.DictReader(handle))


def test_commands_refuse_without_the_data_root(monkeypatch, tmp_path):
    monkeypatch.delenv(fd.ENV_VAR, raising=False)
    with pytest.raises(fd.DataRootNotFound, match="data root not found"):
        cli.main(["run", "--baseline", "persistence", "--split", "dev", "--out", str(tmp_path / "x.csv")],
                 splits=SPLITS)
    with pytest.raises(fd.DataRootNotFound, match="data root not found"):
        cli.main(["time-c651", "--fire", "SYNTHETIC_A1"], splits=SPLITS)
    monkeypatch.setattr("sys.argv", ["firecast-lab", "run", "--baseline", "dilation", "--split", "dev"])
    with pytest.raises(SystemExit, match="data root not found"):
        cli.console()
    assert not (tmp_path / "x.csv").exists()


def test_run_writes_provenance_rows_scored_on_identical_cells(root, tmp_path):
    out = {name: _run(root, tmp_path, "--baseline", name, "--split", "dev", "--members", "8")
           for name in ("persistence", "dilation", "calibrated_dilation", "logistic")}
    first = out["persistence"]
    windows = [w for f in DEV for w in fd.load_windows(root, f, 24, splits=SPLITS)]
    assert len(first) == len(windows) > 0
    for name, rows in out.items():
        assert [(r["fire"], r["cutoff_utc"]) for r in rows] == [(r["fire"], r["cutoff_utc"]) for r in first]
        for r, p in zip(rows, first):
            assert (r["mask_sha256"], r["n_cells"], r["positives"]) == (p["mask_sha256"], p["n_cells"], p["positives"])
            assert r["brier_reference_sum"] == p["brier_reference_sum"]          # same reference, same draws
            assert r["removed_by_support"] == "0" and r["synthetic"] == "True" and r["in_sample"] == "False"
            assert (r["baseline"], r["split"], r["members"], r["seed"]) == (name, "dev", "8", "0")
            assert r["host"] and (r["commit"] == "" or len(r["commit"]) == 40)
            config = json.loads(r["config"])
            assert config["baseline"] == name and config["coupling"] == "shared" and config["lead_h"] == 24
    assert all(float(r["brier_sum"]) == float(r["brier_persistence_sum"]) for r in out["persistence"])
    assert all(r["brier_sum"] == r["brier_reference_sum"] for r in out["calibrated_dilation"])
    assert json.loads(out["dilation"][0]["fit"])["hours_per_cell"] in bl.DILATION_CANDIDATES
    masked = [r for r in first if r["fire"] == "SYNTHETIC_A1"]               # its missing slope cell is not scored
    w = windows[0]
    assert int(masked[0]["n_cells"]) == int((w.domain & ~w.inputs.burned & w.inputs.inputs_valid).sum())


def test_crossfit_holds_out_whole_fire_groups(root):
    calls = []

    def windows_of(ids):
        calls.append(sorted(ids))
        return fd.WindowSource(root, ids, 24, splits=SPLITS)

    seen = [(w.fire, w.cutoff_utc, model.describe()) for w, model, _ in harness.crossfit("dilation", "dev", windows_of,
                                                                                         SPLITS)]
    trains, predicts = calls[0::2], calls[1::2]
    assert predicts == [["SYNTHETIC_A1", "SYNTHETIC_A2"], ["SYNTHETIC_B1", "SYNTHETIC_B2"]]
    assert trains == [["SYNTHETIC_B1", "SYNTHETIC_B2"], ["SYNTHETIC_A1", "SYNTHETIC_A2"]]
    assert len(seen) == len(set((f, c) for f, c, _ in seen))                   # every window predicted once
    fit_on_b = bl.Dilation().fit(fd.WindowSource(root, ["SYNTHETIC_B1", "SYNTHETIC_B2"], 24, splits=SPLITS))
    assert all(d == fit_on_b.describe() for f, _, d in seen if f.startswith("SYNTHETIC_A"))


def test_test_split_copula_and_synthetic_guards(root, tmp_path, monkeypatch):
    with pytest.raises(PermissionError, match="allow-test"):
        _run(root, tmp_path, "--baseline", "persistence", "--split", "test")
    rows = _run(root, tmp_path, "--baseline", "calibrated_dilation", "--split", "test", "--allow-test",
                "--members", "4", "--coupling", "copula", "--length-cells", "3")
    assert {r["fire"] for r in rows} == {"SYNTHETIC_T"} and {r["split"] for r in rows} == {"test"}
    assert json.loads(rows[0]["config"])["length_cells"] == 3.0 and rows[0]["coupling"] == "copula"
    with pytest.raises(ValueError, match="length-cells"):
        _run(root, tmp_path, "--baseline", "persistence", "--split", "dev", "--coupling", "copula")
    monkeypatch.setattr(cli, "RESULTS", tmp_path / "results")
    with pytest.raises(ValueError, match="SYNTHETIC"):
        cli.main(["run", "--baseline", "persistence", "--split", "dev", "--data-root", str(root)], splits=SPLITS)
    assert not (tmp_path / "results").exists()


def test_c651_run_needs_torch(root, tmp_path):
    try:
        import torch  # noqa: F401
        pytest.skip("torch is installed here; the c651 run needs the real data root instead")
    except ImportError:
        pass
    with pytest.raises(ModuleNotFoundError, match="PyTorch"):
        _run(root, tmp_path, "--baseline", "c651", "--split", "dev", "--members", "4")
    with pytest.raises(ModuleNotFoundError, match="PyTorch"):
        cli.main(["time-c651", "--fire", "SYNTHETIC_A1", "--data-root", str(root), "--out", str(tmp_path / "t.csv")],
                 splits=SPLITS)
