"""The decision-metric timing script (firecast-lab/scripts/time_decision.py): plumbing only, on a SYNTHETIC road graph
laid on the KFS_02 dev grid, with tiny settings. Nothing is written outside pytest's tmp_path."""
import importlib.util
import json

import pytest

import synthetic as syn
from firecast_lab.splits import LAB


def _script():
    spec = importlib.util.spec_from_file_location("time_decision", LAB / "scripts" / "time_decision.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_timing_script_runs_one_window_and_says_synthetic(tmp_path):
    graph = syn.road_graph((62, 58), step=3)                    # SYNTHETIC lattice, moved onto the KFS_02 grid
    dx, dy = 1149000.0 - 1_000_000.0, 1912125.0 - 2_000_000.0
    graph = graph.model_copy(update=dict(nodes=[n.model_copy(update=dict(x=n.x + dx, y=n.y + dy))
                                                for n in graph.nodes]))
    (tmp_path / "uljin_2022").mkdir()                          # the KFS_02 folder name, holding the SYNTHETIC graph
    (tmp_path / "uljin_2022" / "graph.json").write_text(graph.model_dump_json())
    script = _script()
    out = script.main(["--graphs", str(tmp_path), "--members", "2", "--requests", "2", "--repeats", "1",
                       "--out", str(tmp_path / "timing.json")])
    assert out["synthetic"] is True and "SYNTHETIC" in out["note"] and out["requests_built"] == 2
    assert out["window_s"] >= 0 and out["korean_dev_windows_with_graphs_approx"] == 17
    assert out["config"]["members"] == 2 and out["seed"] == 0 and out["host"]
    assert json.loads((tmp_path / "timing.json").read_text()) == out
    with pytest.raises(PermissionError, match="test fire"):
        script.main(["--graphs", str(tmp_path), "--fire", "KFS_01"])          # test fires are refused
