"""``firecast-lab decision``: plumbing only, on a SYNTHETIC data root with SYNTHETIC road graphs.

Every row written here is SYNTHETIC and goes to pytest's tmp_path, never to firecast-lab/results/."""
import csv
import json

import pytest
from PIL import Image

import synthetic as syn
from firecast_lab import cli
from firecast_lab import data as fd
from firecast_lab import decision as dm

FIRES = {"SYNTHETIC_A1": "A", "SYNTHETIC_B1": "B"}
SPLITS = syn.splits(**FIRES)


@pytest.fixture(scope="module")
def root(tmp_path_factory):
    return syn.write_root(tmp_path_factory.mktemp("synthetic_root"),
                          {fire: syn.fire(seed=20 + i) for i, fire in enumerate(FIRES)})


@pytest.fixture(scope="module")
def graphs(tmp_path_factory):
    folder = tmp_path_factory.mktemp("synthetic_graphs")
    (folder / "SYNTHETIC_A1").mkdir()                          # SYNTHETIC_B1 has no road graph
    (folder / "SYNTHETIC_A1" / "graph.json").write_text(syn.road_graph((24, 28)).model_dump_json())
    return folder


def _args(root, graphs, out, *extra):
    return ["decision", "--model", "dilation", "--split", "dev", "--members", "3", "--requests", "4", "--repeats", "2",
            "--data-root", str(root), "--graphs", str(graphs), "--out", str(out), *extra]


def test_decision_refuses_without_the_data_root_or_the_road_graphs(monkeypatch, tmp_path, root, graphs):
    monkeypatch.delenv(fd.ENV_VAR, raising=False)
    monkeypatch.delenv(dm.GRAPHS_ENV, raising=False)
    out = tmp_path / "x.csv"
    with pytest.raises(fd.DataRootNotFound, match="data root not found"):
        cli.main(["decision", "--model", "dilation", "--split", "dev", "--graphs", str(graphs), "--out", str(out)],
                 splits=SPLITS)
    with pytest.raises(dm.RoadGraphsNotFound, match="road graphs not found"):
        cli.main(["decision", "--model", "dilation", "--split", "dev", "--data-root", str(root), "--out", str(out)],
                 splits=SPLITS)
    with pytest.raises(PermissionError, match="allow-test"):
        cli.main(_args(root, graphs, out)[:4] + ["test"] + _args(root, graphs, out)[5:], splits=SPLITS)
    monkeypatch.setattr("sys.argv", ["firecast-lab", "decision", "--model", "dilation", "--split", "dev",
                                     "--data-root", str(root)])
    with pytest.raises(SystemExit, match="road graphs not found"):
        cli.console()
    assert not out.exists()


def test_decision_writes_rows_with_provenance(root, graphs, tmp_path, capsys, monkeypatch):
    out = cli.main(_args(root, graphs, tmp_path / "decision_dilation.csv"), splits=SPLITS)
    with out.open() as handle:
        rows = list(csv.DictReader(handle))
    windows = list(fd.load_windows(root, "SYNTHETIC_A1", 24, splits=SPLITS))
    assert len(rows) == len(windows) * 4 * 2 > 0                    # 4 requests per window, 2 couplings
    assert list(rows[0]) == [*dm.COLUMNS, *cli.PROVENANCE]
    assert {r["fire"] for r in rows} == {"SYNTHETIC_A1"} and {r["coupling"] for r in rows} == {"shared", "copula"}
    for r in rows:
        assert r["synthetic"] == "True" and r["truth_kind"] == "reconstruction" and r["truth"] in dm.OUTCOMES
        assert r["cleared"] == str(r["model_state"] == "checked") and len(r["cleared_up_to"].split("|")) == 2
        assert r["length_cells"] == ("8.0" if r["coupling"] == "copula" else "")
        assert r["seed"] == "0" and r["host"] and (r["commit"] == "" or len(r["commit"]) == 40)
    config = json.loads(rows[0]["config"])
    assert (config["command"], config["model"], config["truth_mode"], config["length_cells"]) == (
        "decision", "dilation", "envelope", 8.0)
    assert config["requests"]["n_requests"] == 4 and config["skipped"] == {"SYNTHETIC_B1": "no road graph"}
    assert config["budgets"] == dict(peak_kw_m2=dm.PEAK_KW_M2, dose_kj_m2=dm.DOSE_KJ_M2)
    summary = json.loads(out.with_suffix(".json").read_text())
    assert set(summary["report"]) == {"shared", "copula"} and len(summary["windows"]) == len(windows)
    headline = summary["report"]["shared"]["headline"]
    assert headline["requests"] == len(rows) // 2 and set(dm.RATES) <= set(headline)
    with Image.open(out.with_suffix(".png")) as image:
        assert image.info["Title"].startswith("SYNTHETIC")
    printed = capsys.readouterr().out
    assert "skipped SYNTHETIC_B1: no road graph" in printed and "false-safe" in printed
    monkeypatch.setattr(cli, "RESULTS", tmp_path / "results")
    with pytest.raises(ValueError, match="SYNTHETIC"):
        cli.main(_args(root, graphs, "unused")[:-2], splits=SPLITS)                  # no --out on a SYNTHETIC root
    assert not (tmp_path / "results").exists()


def test_scorable_fires_need_a_graph_and_a_supported_truth(tmp_path):
    for folder in ("SYNTHETIC_K", "SYNTHETIC_U", "uljin_2022"):     # uljin_2022: a SYNTHETIC stand-in folder name
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "graph.json").write_text("{}")
    splits = dict(fires=[dict(id="SYNTHETIC_K", country="KR"), dict(id="SYNTHETIC_U", country="US"),
                         dict(id="KFS_02", country="KR"), dict(id="SYNTHETIC_N", country="KR")])
    found, skipped = dm.scorable_fires(["SYNTHETIC_K", "SYNTHETIC_U", "KFS_02", "SYNTHETIC_N"], splits, tmp_path)
    assert found == {"SYNTHETIC_K": tmp_path / "SYNTHETIC_K" / "graph.json",
                     "KFS_02": tmp_path / "uljin_2022" / "graph.json"}
    assert "NIROPS" in skipped["SYNTHETIC_U"] and skipped["SYNTHETIC_N"] == "no road graph"
    assert "KFS_01" not in dm.GRAPH_FOLDERS                       # the test fire's graphs are never mapped
    with pytest.raises(dm.RoadGraphsNotFound):
        dm.scorable_fires(["SYNTHETIC_K"], splits, tmp_path / "missing")


def test_road_graph_formats(tmp_path):
    graph = syn.road_graph((3, 4))
    (tmp_path / "evacplan.json").write_text(graph.model_dump_json())
    assert dm.load_road_graph(tmp_path / "evacplan.json") == graph
    try:
        import wfg_latest  # noqa: F401
        pytest.skip("wfg_latest is importable here: the router admission runs instead of refusing")
    except ImportError:
        pass
    (tmp_path / "router.json").write_text(json.dumps(dict(crs="EPSG:5179", nodes=[], edges=[])))
    with pytest.raises(ModuleNotFoundError, match="integration/src"):
        dm.load_road_graph(tmp_path / "router.json")
