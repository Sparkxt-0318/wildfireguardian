"""Flux-disc stop in the field-test scripts (copper disc on printed PETG tabs; 70 C, user-set).

Every input here is SIMULATED (hand-built messages, field_tests/simulate.py, a loopback WebSocket server). The tests
check the guard rule (stop at 70.0, not at 69.9; missing / faulted disc temperature > 2 s while needed), that a stop
ends a recorded run and is written into trial.json / marks.jsonl, and that every analysis keeps and labels stopped
runs. They say nothing about hardware.
"""
from __future__ import annotations

import asyncio
import csv
import json
import os
import socket
import tempfile
import threading

import pytest

os.environ.setdefault("MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "mpl"))

from field_tests import (a_flux_analyse, b_radar_analyse, c_thermal_analyse, common, d_failsafe_analyse,  # noqa: E402
                         e_vehicle_analyse, f_housing_analyse, recordkit, simulate)
from field_tests.sessions import load_run  # noqa: E402
from wfgvu import protocol  # noqa: E402

CTX = protocol.Context("VU-T", "VU-T-disc", sim=True)


def plate(temp_c, seq=0, t_mono=1.0, fault=None):
    return CTX.make("reading", sensor="tc_plate", seq=seq, t_mono=t_mono,
                    data={"temp_c": temp_c, "cj_c": 25.0, "fault": fault})


def other(t_mono=1.0, seq=0):
    return CTX.make("reading", sensor="tc_air", seq=seq, t_mono=t_mono, data={"temp_c": 25.0, "cj_c": 25.0,
                                                                            "fault": None})


# ---------------------------------------------------------------------------------------------- the rule
def test_limit_is_the_users_70c_from_crossing_yaml():
    assert common.disc_max_c() == 70.0
    assert recordkit.DiscGuard().disc_max_c == 70.0


@pytest.mark.parametrize("asked", [71.0, 100.0, 120.0, float("nan"), float("inf"), 0.0, "x"])
def test_guard_limit_never_above_the_users_70c(asked):
    g = recordkit.DiscGuard(disc_max_c=asked, needs_plate=False)
    assert g.disc_max_c == 70.0
    assert common.cap_disc_max_c(60.0) == 60.0


def test_report_end_aborted_run_is_not_done(tmp_path):
    import io
    buf = io.StringIO()
    rc = recordkit.report_end({"aborted": "no data from the unit within 15 s", "stop_reason": None}, tmp_path,
                              out=buf)
    assert rc == recordkit.EXIT_ABORTED == 4
    assert buf.getvalue().startswith("ABORTED: no data from the unit") and "Done" not in buf.getvalue()
    assert recordkit.report_end({"stop_reason": None}, tmp_path, out=io.StringIO()) == 0


def test_stops_at_70_0_not_at_69_9():
    g = recordkit.DiscGuard(disc_max_c=70.0, needs_plate=False)
    for i, v in enumerate((25.0, 60.0, 69.75, 69.9, 69.99)):
        assert g.on_message(plate(v, i, 1.0 + i * 0.1), 1.0 + i * 0.1) is None, v
    assert g.stop_reason is None and g.peak_c == 69.99
    assert g.on_message(plate(70.0, 9, 2.0), 2.0) == common.STOP_DISC_OVER
    assert g.stop_c == 70.0 and "70.00 C >= 70 C (PETG tabs)" in g.stop_detail
    assert g.warning().startswith("STOP: flux disc at 70.00 C >= 70 C (PETG tabs)")
    # latched: a cooler reading afterwards does not clear it
    assert g.on_message(plate(30.0, 10, 2.1), 2.1) == common.STOP_DISC_OVER
    trial = g.annotate({})
    assert trial["stop_reason"] == "DISC_OVER_70C" and trial["disc_max_c"] == 70.0
    assert trial["disc_guard"]["peak_c"] == 70.0 and common.stop_label(trial) == "STOPPED: disc 70 C"


def test_fault_reading_is_not_a_temperature_and_missing_data_stops_only_when_needed():
    g = recordkit.DiscGuard(disc_max_c=70.0, needs_plate=True)
    assert g.on_message(plate(30.0, 0, 0.0), 10.0) is None
    assert g.on_message(plate(None, 1, 0.1, fault="open"), 10.1) is None          # a fault is not > 70 C
    assert g.check(11.9) is None                                                    # 1.9 s after the last good
    assert g.check(12.1) == common.STOP_DISC_UNKNOWN
    assert "missing or faulted tc_plate" in g.stop_detail
    assert common.stop_label(g.annotate({})) == "STOPPED: disc temperature unknown"
    # not needed: never stops for missing data (test C / E / D)
    g2 = recordkit.DiscGuard(disc_max_c=70.0, needs_plate=False)
    g2.on_message(other(), 0.0)
    assert g2.check(100.0) is None
    assert g2.on_message(plate(75.0), 100.0) == common.STOP_DISC_OVER             # but 70 C always stops


def test_phase_dependent_need_gives_2s_grace_from_the_phase_start():
    g = recordkit.DiscGuard(disc_max_c=70.0, needs_plate=False)
    g.on_message(other(), 0.0)                       # no tc_plate at all
    assert g.check(50.0) is None
    g.set_needs_plate(True, 50.0)
    assert g.check(51.9) is None and g.check(52.1) == common.STOP_DISC_UNKNOWN


def test_state_input_for_test_d():
    g = recordkit.DiscGuard(disc_max_c=70.0, needs_plate=False)
    st = {"flux": {"tc_plate_c": 69.9}, "tc": {"tc_plate": {"temp_c": 69.9, "fault": None}}}
    assert g.on_state(st, 1.0) is None
    st = {"flux": {"tc_plate_c": 70.0}, "tc": {"tc_plate": {"temp_c": 70.0, "fault": None}}}
    assert g.on_state(st, 1.2) == common.STOP_DISC_OVER


# ---------------------------------------------------------------------------------------------- simulated runs
def test_simulated_run_is_cut_at_the_stop_and_marked(tmp_path):
    run = simulate.SimRun(tmp_path / "r", "VU-SIM-x")
    for i in range(100):                                          # 60 C + 0.25 C per 0.1 s: 70 C at i = 40
        run.reading("tc_plate", 10.0 + i * 0.1, simulate.tc_data(60.0 + 0.25 * i))
    run.mark("heat", 10.0)
    run.mark("end", 19.5)
    g = simulate.apply_disc_guard(run, needs_plate=True)
    assert g.stop_reason == common.STOP_DISC_OVER and g.stop_c == 70.0
    temps = [m["data"]["temp_c"] for m in run.msgs]
    assert max(temps) == 70.0 and len(temps) == 41
    kinds = [m["kind"] for m in run.marks]
    assert kinds == ["heat", "disc_stop"]
    trial = g.annotate({"test": "A", "run_id": "r", "kind": "cooldown"})
    d = run.write(trial)
    r = load_run(d)
    assert r.trial["stop_reason"] == "DISC_OVER_70C" and r.mark_t("disc_stop") is not None


def test_a_analysis_keeps_stopped_and_over_limit_runs(tmp_path):
    simulate.sim_a(tmp_path / "A", seed=12, distances=(0.10,), repeats=2, n_cooldown=1, background_s=20.0,
                   exposure_s=60.0, cooldown_tail_s=20.0, cooldown_s=250.0, stopped_cooldown=True)
    # a run recorded before the guard existed, whose data crossed 70 C: the analysis must flag it by itself
    r2 = tmp_path / "A" / "A_exposure_d0.100_r2_SIM"
    t = json.loads((r2 / "trial.json").read_text())
    for k in ("stop_reason", "stop_detail", "disc_guard"):
        t.pop(k, None)
    (r2 / "trial.json").write_text(json.dumps(t))
    import gzip
    p = r2 / "tc_plate.jsonl.gz"
    lines = gzip.open(p, "rt").read().splitlines()
    idx = [i for i, x in enumerate(lines) if '"reading"' in x]
    k = idx[len(idx) // 2]
    m = json.loads(lines[k])
    m["data"]["temp_c"] = 71.0
    lines[k] = protocol.dumps(m)
    with gzip.open(p, "wt") as fh:
        fh.write("\n".join(lines) + "\n")
    res = a_flux_analyse.analyse(tmp_path / "A", tmp_path / "out")
    fits = {f["run_id"]: f for f in res["fits"]}
    stopped = fits["A_cooldown_r2_SIM_overheated"]
    assert stopped["stop_reason"] == "DISC_OVER_70C" and "STOPPED: disc 70 C" in stopped["flag"]
    assert stopped["n_disc_over_limit"] >= 1
    assert not fits["A_cooldown_r1_SIM"]["flag"] and fits["A_cooldown_r1_SIM"]["t_max_c"] < 70.0
    assert "median of 1 cool-down fit" in res["loss"].note               # the stopped run is not pooled
    runs = {r["run_id"]: r for r in res["runs"]}
    assert runs["A_exposure_d0.100_r2_SIM"]["n_disc_over_limit"] == 1
    assert "disc sample(s) >= 70 C" in runs["A_exposure_d0.100_r2_SIM"]["flag"]
    assert {r["run_id"] for r in res["runs"]} == {"A_exposure_d0.100_r1_SIM", "A_exposure_d0.100_r2_SIM"}
    md = res["markdown"]
    assert "A_cooldown_r2_SIM_overheated: STOPPED: disc 70 C" in md and "run kept, reported as measured" in md
    with open(tmp_path / "out" / "A_cooldown_fits.csv", newline="") as fh:
        rows = {r["run_id"]: r for r in csv.DictReader(fh)}                  # the CSV keeps it too
    assert rows["A_cooldown_r2_SIM_overheated"]["stop_reason"] == "DISC_OVER_70C"


def _set_stop(run_dir, reason=common.STOP_DISC_OVER, detail="flux disc at 70.25 C >= 70 C (PETG tabs)"):
    p = run_dir / "trial.json"
    t = json.loads(p.read_text())
    t.update(stop_reason=reason, stop_detail=detail, disc_max_c=70.0)
    p.write_text(json.dumps(t))


def test_b_c_e_f_d_analyses_report_stopped_runs(tmp_path):
    dirs = simulate.sim_b(tmp_path / "B", seed=9, distances=(2.0,), duration_s=9.0)
    _set_stop(dirs[-1])
    rb = b_radar_analyse.analyse(tmp_path / "B", tmp_path / "outB", echo=lambda *a: None)
    assert "STOPPED: disc 70 C" in rb["markdown"] and "1 run(s) stopped" in rb["markdown"]

    simulate.sim_c(tmp_path / "C", seed=31, distances=(3.0, 6.0), tilts=(0.0,), n_frames=2)
    cdir = sorted(p.parent for p in (tmp_path / "C").rglob("trial.json"))[0]
    _set_stop(cdir)
    rc = c_thermal_analyse.analyse(tmp_path / "C", tmp_path / "outC")
    assert len(rc["runs"]) == 2 and sum("STOPPED: disc 70 C" in (r.get("flag") or "") for r in rc["runs"]) == 1

    d = simulate.sim_f(tmp_path / "F", seed=61, scale=0.25)
    rf0 = f_housing_analyse.analyse(tmp_path / "outF0", str(d["laptop"]), str(d["pi"]))
    c0 = {x["check"]: x for x in rf0["checks"]}
    assert c0["disc_limit"]["result"] == "PASS" and c0["disc_limit"]["value"] < 70.0
    assert c0["disc_guard_stop"]["result"] == "PASS"
    _set_stop(d["laptop"], common.STOP_DISC_UNKNOWN, "no valid flux-disc temperature for > 2 s")
    rf = f_housing_analyse.analyse(tmp_path / "outF", str(d["laptop"]), str(d["pi"]))
    c = {x["check"]: x for x in rf["checks"]}
    assert c["disc_guard_stop"]["result"] == "FAIL" and "STOPPED: disc temperature unknown" in c["disc_guard_stop"]["detail"]

    e = simulate.sim_e(tmp_path / "E", seed=51, duration_s=120.0)
    _set_stop(e["laptop"])
    re_ = e_vehicle_analyse.analyse(tmp_path / "outE", [str(e["pi"])], str(e["laptop"]))
    assert "STOPPED: disc 70 C" in re_["markdown"]

    run = simulate.sim_d(tmp_path / "D", seed=41)
    _set_stop(run)
    rd = d_failsafe_analyse.analyse(tmp_path / "outD", run_dir=run)
    assert rd["stop_reason"] == "DISC_OVER_70C" and "STOPPED: disc 70 C" in rd["markdown"]
    assert rd["faults"]                                                  # rows still reported


def test_committed_example_outputs_include_a_stopped_run():
    md = (common.EXAMPLES / "A_flux" / "A_results.md").read_text()
    assert "STOPPED: disc 70 C" in md and "A_cooldown_r3_SIM_overheated" in md
    assert "SIMULATED" in md
    f = (common.EXAMPLES / "F_housing" / "F_results.md").read_text()
    assert "disc_limit | PASS" in f


# ---------------------------------------------------------------------------------------------- live recorder
def test_record_run_stops_at_70c_against_a_local_server(tmp_path):
    """recordkit.record_run against a loopback server whose disc warms 66 -> 74 C (SIMULATED messages): the run
    stops at the first reading >= 70 C, long before its 30 s phase ends. Skipped where binding is not permitted."""
    import websockets

    try:
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
    except OSError as exc:
        pytest.skip("cannot bind a local port here: %s" % exc)
    ready, stop = threading.Event(), threading.Event()

    async def handler(ws, *args):
        await ws.send(protocol.dumps(CTX.make("hello", sensors=["tc_plate"], version="t", config_digest="x")))
        i = 0
        while not stop.is_set():
            v = min(66.0 + 0.25 * (i // 2), 74.0)                        # +0.25 C every 0.04 s
            await ws.send(protocol.dumps(CTX.make("reading", sensor="tc_plate", seq=i,
                                                  data={"temp_c": v, "cj_c": 25.0, "fault": None})))
            i += 1
            await asyncio.sleep(0.02)

    def serve():
        async def main():
            try:
                async with websockets.serve(handler, "127.0.0.1", port):
                    ready.set()
                    while not stop.is_set():
                        await asyncio.sleep(0.05)
            except OSError:
                ready.set()
        asyncio.run(main())

    th = threading.Thread(target=serve, daemon=True)
    th.start()
    ready.wait(5)
    import time
    t0 = time.monotonic()
    try:
        trial = {"test": "A", "run_id": "live"}
        d = recordkit.record_run("ws://127.0.0.1:%d" % port, tmp_path / "live", trial,
                                 [("exposure", 30.0, "exposure")], warmup_s=0.1, interactive=False, countdown_s=0,
                                 no_data_timeout_s=3.0, needs_plate=True)
    finally:
        stop.set()
        th.join(5)
    elapsed = time.monotonic() - t0
    if trial.get("aborted"):
        pytest.skip("loopback connection refused here: %s" % trial["aborted"])
    assert elapsed < 10.0, elapsed                                   # not the 30 s phase
    assert trial["stop_reason"] == common.STOP_DISC_OVER
    assert recordkit.report_end(trial, d, out=open(os.devnull, "w")) == 3
    run = load_run(d)
    assert run.trial["stop_reason"] == "DISC_OVER_70C" and run.trial["disc_guard"]["stop_disc_c"] == 70.0
    stops = [m for m in run.marks if m["kind"] == "disc_stop"]
    assert len(stops) == 1 and stops[0]["stop_reason"] == "DISC_OVER_70C"
    assert run.mark_t("end") is None                                 # the protocol did not finish
    temps = [m["data"]["temp_c"] for m in run.readings("tc_plate")]
    assert temps and max(temps) <= 74.0 and 70.0 in temps
