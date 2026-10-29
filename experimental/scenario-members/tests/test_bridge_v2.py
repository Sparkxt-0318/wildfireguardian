"""Contract B (construction law v2) tests. Routing environment (NumPy, pyproj); frozen inputs for the replay tests."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "src"))
import bridge_v2 as B2  # noqa: E402
from wfg_members import kit  # noqa: E402
from wfg_members.contact import ContactModel  # noqa: E402

needs_inputs = pytest.mark.skipif(not kit.inputs_available(), reason="frozen routing inputs not present")


def _fbh(seed=0, n=6, shape=(9, 10)):
    rng = np.random.default_rng(seed)
    f = np.where(rng.random((n,) + shape) < 0.3, 1, -1).astype(np.int16)
    f[:, 4, 4] = 0
    f[:, 0, 0] = -2
    return f


def test_uniform_and_ordered_timing_share_the_hour_and_the_seconds():
    f = _fbh()
    u = B2.ignition_seconds(f, [0, 3, 5], timing="uniform")
    o = B2.ignition_seconds(f, [0, 3, 5], timing="ordered")
    for s, k in enumerate([0, 3, 5]):
        burn = f[k] == 1
        assert np.array_equal(np.isfinite(u[s]), burn) and np.array_equal(np.isfinite(o[s]), burn)
        assert np.all((u[s][burn] >= 0) & (u[s][burn] < 3600))
        assert np.array_equal(np.sort(u[s][burn]), np.sort(o[s][burn]))      # same multiset of seconds
    # the same trajectory gets the same seconds whatever else is selected
    assert np.array_equal(B2.ignition_seconds(f, [3], timing="uniform")[0], u[1])


def test_ordered_timing_ignites_nearer_cells_first():
    f = _fbh(seed=4)
    o = B2.ignition_seconds(f, [2], timing="ordered")[0]
    burned = np.argwhere(f[2] == 0)
    cells = np.argwhere(f[2] == 1)
    d = ((cells[:, None, :] - burned[None, :, :]) ** 2).sum(-1).min(1)
    t = o[cells[:, 0], cells[:, 1]]
    order = np.argsort(t)
    assert np.all(np.diff(d[order]) >= 0)


@needs_inputs
@pytest.mark.parametrize("region,tag,event", [("uljin_2022", "20220304T060000Z", "KFS_02"),
                                              ("uiseong_andong_2025", "20250323T010000Z", "KFS_01")])
def test_v2_path_with_the_v1_draws_reproduces_the_frozen_packet(region, tag, event):
    """Fed the v1 independent draws as 'trajectories', the v2 path must rebuild the frozen packet arrays exactly."""
    K = kit.install()
    p = kit.paths(region, tag, event)
    fc, record = B2.load_export(p["export_npz"], p["export_record"])
    T = float(fc["contract__cell_duration_s"])
    v1 = K["bridge"].settings_for(T)
    bound = K["contract"].verify_binding(fc, record, kit.cutoff_iso(tag), event, record["epsg"])
    full_v1 = K["bridge"].construct(fc, cutoff_utc=bound["cutoff_utc"], epsg=bound["epsg"], settings=v1)
    settings = B2.v2_settings(T, member_count=4, timing="uniform", selection={"method": "v1_draws_control"}, timing_seed=v1["seed"])
    _, built = B2.construct_v2(fc, record, cutoff_iso=kit.cutoff_iso(tag), event_id=event, epsg=record["epsg"],
                               events_full=full_v1["events"], settings=settings, window=B2.frozen_window(p["packet"]))
    hz = json.loads((p["packet"] / "HAZARD.json").read_text())
    mine = B2.hazard_arrays(built, [m["id"] for m in hz["members"]])
    for a, b in zip(mine["members"], hz["members"]):
        assert a["breakpoints"] == b["breakpoints"]
        assert np.array_equal(a["flame"], np.array(b["flame"], dtype=bool))
        fb = np.array(b["flux"], dtype=float)
        rel = np.abs(a["flux"] - fb).max() / max(float(fb.max()), 1e-300)
        print("max relative flux difference %.3e exact=%s" % (rel, np.array_equal(a["flux"], fb)))
        assert rel < 1e-12      # FFT rounding of the frozen macOS arm64 build host differs from this host in the last bits
    frozen = ContactModel.from_packet(p["packet"])
    rebuilt = ContactModel.from_arrays(built["events"], built["current"], T, built["remaining_s"], ids=frozen.ids)
    assert rebuilt.cell_intervals == frozen.cell_intervals


@needs_inputs
def test_written_v2_packet_has_v1_layout_and_v2_records(tmp_path):
    region, tag, event = "uljin_2022", "20220304T060000Z", "KFS_02"
    K = kit.install()
    p = kit.paths(region, tag, event)
    fc, record = B2.load_export(p["export_npz"], p["export_record"])
    T = float(fc["contract__cell_duration_s"])
    q = np.where(fc["probability_valid"], fc["new_burn_probability"], 0.0)
    rng = np.random.default_rng(1)
    fbh = np.where(fc["probability_valid"][None] & (rng.random((8,) + q.shape) < q[None] * 5), 1, -1).astype(np.int16)
    fbh[:, (fc["source_burned_area_valid"] & (np.nan_to_num(fc["source_burned_area"]) == 1))] = 0
    events = B2.ignition_seconds(fbh, [1, 4, 6], timing="ordered")
    selection = {"method": "first_k", "distance": None, "cost": None, "indices": [1, 4, 6], "weights": [1 / 3] * 3}
    settings = B2.v2_settings(T, member_count=3, timing="ordered", selection=selection,
                              acceptance={"rule": "k_of_m", "k": 2, "m": 3})
    graph = json.loads(p["graph"].read_text())
    out, hz, summary = B2.write_packet_v2(graph, p["graph"], p["export_npz"], record, kit.sha256_file(p["export_record"]),
                                          kit.cutoff_iso(tag), record["epsg"], tmp_path / "pkt", event_id=event,
                                          region_id=region, window=None, events_full=events, settings=settings)
    for name in ("HAZARD.json", "REPORT.json", "NATIVE_METADATA.json", "constructed_arrays.npz", "BUILD_SUMMARY.json"):
        assert (out / name).is_file()
    md = json.loads((out / "NATIVE_METADATA.json").read_text())
    assert md["settings"]["dependence"] == "trajectory" and md["settings"]["timing"] == "ordered"
    assert md["settings"]["member_selection"]["indices"] == [1, 4, 6]
    assert md["settings"]["acceptance"] == {"rule": "k_of_m", "k": 2, "m": 3}
    assert md["construction"]["assumptions"]["dependence"] == "trajectory"
    assert md["construction"]["assumptions"]["version"] == "wfg.hazard.construction/1"   # checkers keep the scalar source law
    assert len(hz["members"]) == 3
    K["validation"].validate_hazard(graph, json.loads((out / "HAZARD.json").read_text()))
    cm = ContactModel.from_packet(out)
    assert cm.new_ignition_counts() == [int(np.isfinite(events[s]).sum()) for s in range(3)]
