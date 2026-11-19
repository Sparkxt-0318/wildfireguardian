"""crossing.research_log (step 10, DESIGN.md section 11) on a SYNTHETIC session run through the pipeline: every file
exists with the documented columns, arrays round-trip, session.json carries versions/config/vehicle/fuel/sim, Parquet
copies match, and the wire log replays to the same verdict sequence."""
import gzip
import json

import numpy as np
import pytest

from crossing import pipeline as pl
from crossing import research_log as rl
from crossing.config import load_config

from test_pipeline import TEST_VEHICLE, build_session, capture_at, items_of

README = __import__("pathlib").Path(__file__).resolve().parents[1] / "research_log" / "README.md"


@pytest.fixture(scope="module")
def logged(tmp_path_factory):
    root = tmp_path_factory.mktemp("records")
    cfg = load_config(overrides={"paths": {"records_dir": str(root), "pairs_path": str(root / "p.jsonl"),
                                           "sim_pairs_path": str(root / "ps.jsonl")}, "log": {"chunk_frames": 20}})
    log = rl.ResearchLog(root, "CX-test", info={"mode": "replay", "config": cfg.to_dict()}, chunk_frames=20)
    pipe = pl.Pipeline(cfg, TEST_VEHICLE, "GR1", research_log=log, mode="replay", source="synthetic")
    log.update_info(vehicle=pipe.vehicle.to_dict(), fuel=pipe.fuel.to_dict())
    hello, msgs = build_session("flame_front", duration=12.0)
    states = pl.run_virtual(pipe, items_of(hello, msgs), hooks=capture_at(4.5))
    pipe.mark_crossing(1000.0 + 12.0, measured_m=3.0)
    pipe.set_fuel("GR2", 1000.0 + 12.0)
    log.close()
    return log.dir, states, msgs, cfg


def test_files_and_columns(logged):
    d, states, msgs, cfg = logged
    for name, cols in rl.TABLES.items():
        p = d / ("%s.csv" % name)
        assert p.exists(), name
        with open(p) as fh:
            assert fh.readline().strip().split(",") == list(cols), name
    n_tc = sum(1 for m in msgs if m["type"] == "reading" and m["sensor"] == "tc_plate")
    assert len(rl.read_csv(d / "readings_tc_plate.csv")) == n_tc
    v = rl.read_csv(d / "verdicts.csv")
    assert len(v) == len(states)
    assert {r["state"] for r in v} >= {"CLOSED", "CROSS FAST"}
    assert all(r["sim"] == "true" for r in v)
    pairs = rl.read_csv(d / "pairs.csv")
    assert len(pairs) == 1 and pairs[0]["source"] == "manual" and float(pairs[0]["measured_m"]) == 3.0
    assert float(pairs[0]["est_byram_m"]) > 0
    h = rl.read_csv(d / "health.csv")
    assert 10 <= len(h) <= 14                                      # 1 Hz over 12 s
    assert any(r["kind"] == "change_fuel" for r in rl.read_csv(d / "events.csv"))


def test_arrays_round_trip(logged):
    d, states, msgs, cfg = logged
    th_rows = rl.read_csv(d / "readings_thermal.csv")
    files = sorted(d.glob("thermal_frames.*.npz"))
    assert files and sum(np.load(f)["raw_u16"].shape[0] for f in files) == len(th_rows)
    r = th_rows[-1]
    z = np.load(d / ("thermal_frames.%s.npz" % r["chunk"]))
    img = z["raw_u16"][int(r["index"])] / z["raw_per_k"][int(r["index"])]
    from wfgvu import protocol
    last = [m for m in msgs if m["type"] == "reading" and m["sensor"] == "thermal"][-1]
    assert np.allclose(img, protocol.decode_thermal(last["data"]), atol=1e-6)
    rr = rl.read_csv(d / "readings_radar.csv")[5]
    zr = np.load(d / ("radar_frames.%s.npz" % rr["chunk"]))
    iq = zr["iq"][int(rr["index"])]
    rmsg = [m for m in msgs if m["type"] == "reading" and m["sensor"] == "radar"][5]
    assert np.array_equal(iq, protocol.decode_iq(rmsg["data"]["az_heatmap"]))
    assert bool(zr["has_iq"][int(rr["index"])]) and not bool(zr["has_profile"][int(rr["index"])])


def test_session_json(logged):
    d, states, msgs, cfg = logged
    s = json.loads((d / "session.json").read_text())
    assert s["schema"] == rl.SCHEMA and s["sim"] is True and s["ended_utc"]
    for k in ("crossing", "wfgvu", "protocol", "python", "numpy"):
        assert s["versions"][k]
    assert s["config"]["link"]["stale_s"] == 2.0
    assert s["vehicle"]["name"] == "test_only" and s["fuel"]["code"] == "GR1"
    assert [c["what"] for c in s["changes"]].count("fuel") == 1
    assert s["pi"]["session_id"].startswith("VU-SYN")
    assert s["baselines"] and (d / s["baselines"][0]["file"]).exists()


def test_parquet_copies(logged):
    pq = pytest.importorskip("pyarrow.parquet")
    d, states, msgs, cfg = logged
    for name, cols in rl.TABLES.items():
        p = d / ("%s.parquet" % name)
        assert p.exists(), name
        t = pq.read_table(p)
        assert t.column_names == list(cols)
        assert t.num_rows == len(rl.read_csv(d / ("%s.csv" % name)))


def test_wire_log_replays_to_the_same_verdicts(logged, tmp_path):
    d, states, msgs, cfg = logged
    with gzip.open(d / "wire.jsonl.gz", "rt") as fh:
        first = json.loads(fh.readline())
    assert first.get("link") == "up"
    assert pl.is_research_log(d)
    pipe = pl.Pipeline(load_config(overrides={"paths": {"records_dir": str(tmp_path),
                                                        "sim_pairs_path": str(tmp_path / "ps.jsonl")}}),
                       TEST_VEHICLE, "GR1", mode="replay")
    again = pl.run_virtual(pipe, pl.iter_source(d), hooks=capture_at(4.5))
    a = [s["verdict"]["state"] for _, s in states]
    b = [s["verdict"]["state"] for _, s in again][:len(a)]
    assert a == b


def test_readme_documents_every_column():
    text = README.read_text()
    missing = sorted({c for cols in rl.TABLES.values() for c in cols if "`%s`" % c not in text})
    assert not missing, missing


def test_export_parquet_without_csv_is_empty(tmp_path):
    assert rl.export_parquet(tmp_path) == []
