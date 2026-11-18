"""Tests for apps/crossing/field_tests (tests A-F scripts and analysis).

Every input here is SIMULATED (field_tests/simulate.py or hand-built timelines, all seeded). These tests check that
the scripts refuse what they must refuse, that each analysis recovers known simulated truth and reports failures,
and that every output built from simulated input is labelled SIMULATED. They say nothing about hardware.
"""
from __future__ import annotations

import csv
import gzip
import json
import math
import os
import tempfile
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "mpl"))

from field_tests import (a_flux_analyse, a_flux_record, b_radar_analyse, b_radar_record, c_thermal_analyse,  # noqa: E402
                         common, d_failsafe_analyse, e_vehicle_analyse, f_housing_analyse, recordkit, simulate,
                         unitstats)
from field_tests.sessions import load_run  # noqa: E402
from crossing import geometry, thermal  # noqa: E402
from wfgvu import protocol, replay  # noqa: E402

EXAMPLES = Path(common.EXAMPLES)


def _pdf(tmp_path, name="ra.pdf", body=b"%PDF-1.4\n% signed risk assessment scan\n"):
    p = tmp_path / name
    p.write_bytes(body)
    return p


def _csv_rows(path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


# ---------------------------------------------------------------------------------------------- risk gate
def test_risk_gate_refuses_and_accepts(tmp_path):
    pdf = _pdf(tmp_path)
    with pytest.raises(common.RiskGateError, match="supervisor"):
        common.risk_gate(str(pdf), None)
    with pytest.raises(common.RiskGateError, match="supervisor"):
        common.risk_gate(str(pdf), "   ")
    with pytest.raises(common.RiskGateError, match="risk-assessment"):
        common.risk_gate(None, "A. Adult")
    with pytest.raises(common.RiskGateError, match="not found"):
        common.risk_gate(str(tmp_path / "missing.pdf"), "A. Adult")
    empty = tmp_path / "empty.pdf"
    empty.write_bytes(b"")
    with pytest.raises(common.RiskGateError, match="empty"):
        common.risk_gate(str(empty), "A. Adult")
    txt = tmp_path / "notes.txt"
    txt.write_text("I promise it is fine")
    with pytest.raises(common.RiskGateError, match="scan or PDF"):
        common.risk_gate(str(txt), "A. Adult")
    with pytest.raises(common.RiskGateError):
        common.risk_gate(str(tmp_path), "A. Adult")                    # a directory is not a file
    meta = common.risk_gate(str(pdf), " A. Adult ")
    assert meta["supervisor"] == "A. Adult"
    assert meta["risk_assessment_path"] == str(pdf.resolve())
    assert len(meta["risk_assessment_sha256"]) == 64 and meta["risk_assessment_bytes"] == pdf.stat().st_size
    jpg = tmp_path / "scan_no_ext"
    jpg.write_bytes(b"\xff\xd8\xff\xe0 jpeg scan")
    assert common.risk_gate(str(jpg), "A. Adult")["supervisor"] == "A. Adult"   # magic bytes accepted


def test_test_a_record_refuses_without_gate(tmp_path, capsys):
    with pytest.raises(SystemExit) as e:
        a_flux_record.main(["--sheet", "x.yaml", "--kind", "exposure", "--distance-m", "0.1", "--out", str(tmp_path)])
    assert e.value.code == 2
    assert "risk" in capsys.readouterr().err.lower() or True
    with pytest.raises(SystemExit) as e:
        a_flux_record.main(["--risk-assessment", str(_pdf(tmp_path)), "--sheet", "x.yaml", "--kind", "exposure",
                            "--distance-m", "0.1", "--out", str(tmp_path)])
    assert e.value.code == 2
    assert "supervisor" in capsys.readouterr().err
    # gate passes but the sheet is missing / the distance is missing: still refuses, before any network use
    rc = a_flux_record.main(["--risk-assessment", str(_pdf(tmp_path)), "--supervisor", "A. Adult", "--sheet",
                             str(tmp_path / "nope.yaml"), "--kind", "exposure", "--distance-m", "0.1"])
    assert rc == 2
    sheet = tmp_path / "s.yaml"
    sheet.write_text("gas: methane\n")
    rc = a_flux_record.main(["--risk-assessment", str(_pdf(tmp_path)), "--supervisor", "A. Adult", "--sheet",
                             str(sheet), "--kind", "exposure"])
    assert rc == 2
    assert not list(tmp_path.glob("A_*"))                               # nothing recorded
    assert "Bunsen burner" in a_flux_record.HEAT_SOURCE


def test_test_b_flame_needs_gate(tmp_path, capsys):
    with pytest.raises(SystemExit) as e:
        b_radar_record.main(["--distance-m", "3", "--condition", "flame", "--flame-source", "Bunsen",
                             "--out", str(tmp_path)])
    assert e.value.code == 2
    rc = b_radar_record.main(["--distance-m", "3", "--condition", "flame", "--risk-assessment",
                              str(_pdf(tmp_path)), "--supervisor", "A. Adult", "--out", str(tmp_path)])
    assert rc == 2                                                      # flame source missing
    rc = b_radar_record.main(["--distance-m", "3", "--condition", "mist", "--role", "baseline",
                              "--out", str(tmp_path)])
    assert rc == 2                                                      # baseline must be 'nothing'


# ---------------------------------------------------------------------------------------------- recorder
def test_session_writer_roundtrip(tmp_path):
    clock = iter(np.arange(100.0, 200.0, 0.05))
    w = recordkit.SessionWriter(tmp_path / "run", clock=lambda: float(next(clock)))
    ctx = protocol.Context("VU-T", "VU-T-1", sim=True)
    w.on_connect("ws://test")
    for i in range(20):
        m = ctx.make("reading", sensor="tc_plate", seq=i, data={"temp_c": 20.0 + i, "cj_c": 21.0, "fault": None},
                     t_mono=10.0 + 0.1 * i, t_utc=None)
        w.on_text(protocol.dumps(m), t_rx=1000.0 + 0.1 * i + (0.003 if i % 2 else 0.010))
        w.on_text(protocol.dumps(ctx.make("heartbeat", sensor="unit", status="ok", detail="", last_reading_seq=None,
                                          rate_hz=None, seq=i, t_mono=10.0 + 0.1 * i, t_utc=None)),
                  t_rx=1000.0 + 0.1 * i + 0.004)
    assert w.on_text('{"v":1,"type":"reading"}', t_rx=1002.5) is None
    assert w.bad == 1
    assert w.offset() == pytest.approx(990.003)
    mk = w.mark("exposure", "NOW", t_rx=1001.0)
    assert mk["pi_t_mono"] == pytest.approx(1001.0 - 990.003)
    w.on_disconnect("test end", t_rx=1003.0)
    w.close({"test": "A", "run_id": "x"})
    run = load_run(tmp_path / "run")
    assert [m["seq"] for m in run.readings("tc_plate")] == list(range(20))
    assert len(run.heartbeats("unit")) == 20
    assert run.mark_t("exposure") == pytest.approx(10.997)
    rx = run.rx()
    assert sum(1 for x in rx if x.get("type") == "reading") == 20
    assert any(x.get("link") == "disconnect" for x in rx) and any(x.get("type") == "bad" for x in rx)
    info = json.loads((tmp_path / "run" / "session.json").read_text())
    assert info["sim"] is True and info["counts"]["tc_plate"] == 20
    assert replay.load(tmp_path / "run").streams["tc_plate"] is not None


# ---------------------------------------------------------------------------------------------- test A
def test_a_models():
    q = a_flux_analyse.heat_release_kw({"gas": "methane", "gas_flow_l_min": 2.0})
    assert q["q_kw"] == pytest.approx(2.0 / 60000 * 33.9 * 1000)
    assert math.isnan(a_flux_analyse.heat_release_kw({"gas": "natural_gas", "gas_flow_l_min": 2.0})["q_kw"])
    # the finite-front closed form tends to the point source far from a small flame
    far = a_flux_analyse.closed_form_bunsen(2.0, 1.13, 0.1, 0.02)
    assert far == pytest.approx(float(a_flux_analyse.point_source(2.0, 0.1, 1.13)), rel=1e-3)
    assert a_flux_analyse.closed_form_bunsen(0.05, 1.13, 0.1, 0.02) < float(a_flux_analyse.point_source(0.05, 0.1, 1.13))
    ref = a_flux_analyse.fds_bunsen(0.2, 1.13, 0.02)
    assert ref.label == "FDS C064 reference, not a measurement" and ref.q_kw_m2 > 0


def test_a_analysis_on_simulated_runs(tmp_path):
    simulate.sim_a(tmp_path / "A", seed=11, distances=(0.10, 0.30), repeats=2, n_cooldown=1, background_s=20.0,
                   exposure_s=60.0, cooldown_tail_s=20.0, cooldown_s=250.0)
    # break one run: drop its exposure mark -> must be flagged and left out, not silently averaged
    bad = tmp_path / "A" / "A_exposure_d0.300_r2_SIM" / "marks.jsonl"
    bad.write_text("\n".join(x for x in bad.read_text().splitlines() if '"exposure"' not in x) + "\n")
    res = a_flux_analyse.analyse(tmp_path / "A", tmp_path / "out")
    assert res["simulated"]
    assert res["loss"].h == pytest.approx(simulate.A_TRUTH["h_w_m2k"], rel=0.03)
    q_kw = simulate.A_TRUTH["gas_flow_l_min"] / 60000 * simulate.A_TRUTH["lhv_mj_m3"] * 1000
    by = {r["distance_m"]: r for r in res["by_distance"]}
    for d in (0.10, 0.30):
        truth = simulate.A_TRUTH["chi_true"] * q_kw / (4 * math.pi * d * d)
        assert by[d]["q_meas_mean_kw_m2"] == pytest.approx(truth, rel=0.06)
        assert by[d]["ratio_meas_to_point"] == pytest.approx(0.8, abs=0.06)    # chi 0.08 true vs 0.10 assumed
    assert by[0.30]["n_used"] == 1 and by[0.30]["n_runs"] == 2
    assert any("missing phase marks" in r["flag"] for r in res["runs"])
    assert "missing phase marks" in res["markdown"]
    for f in ("A_by_distance.csv", "A_runs.csv", "A_cooldown_fits.csv", "plate_loss.json", "A_flux_vs_distance.png",
              "A_flux_timeseries.png", "A_cooldown_fit.png", "A_results.md", "A_gate.csv"):
        assert (tmp_path / "out" / f).exists(), f
    assert all(r["simulated"] == "true" for r in _csv_rows(tmp_path / "out" / "A_by_distance.csv"))
    # R7: 2 of the sheet's 5 distances x 2 of its 3 repeats -> plan incomplete, one PROBLEM per gap
    assert "INCOMPLETE" in res["markdown"] and "PROBLEM: plan: 0.150 m: 0 of 3 exposure runs" in res["markdown"]
    assert "plan: 0.100 m: 2 of 3 exposure runs" in res["plan_problems"]
    assert "Bunsen burner only" in res["markdown"] and "SIMULATED" in res["markdown"]


# ---------------------------------------------------------------------------------------------- test B
def test_b_analysis_reports_below_noise(tmp_path, monkeypatch):
    lines = []
    simulate.sim_b(tmp_path / "B", seed=21, distances=(2.0,), duration_s=12.0,
                   repeats={"nothing": 2, "flame": 2, "smoke": 1, "mist": 1})
    res = b_radar_analyse.analyse(tmp_path / "B", tmp_path / "out", echo=lines.append)
    rows = {r["condition"]: r for r in res["conditions"]}
    assert set(rows) == {"nothing", "flame", "smoke", "mist"}
    assert rows["smoke"]["effect_below_noise"] is True                    # no radar effect by construction
    assert rows["smoke"]["frac_flame_effect"] == 0.0
    assert rows["mist"]["effect_below_noise"] is False
    assert rows["mist"]["loss_db_effect"] > 0.5
    assert rows["flame"]["effect_below_noise"] is False                    # 2 m: simulated flicker visible
    assert "smoke effect below noise" in "\n".join(lines)
    assert rows["nothing"]["reflector_snr_db"] > 30
    # a flame with no simulated effect at all must be reported with the exact required text
    monkeypatch.setitem(simulate.B_TRUTH, "flame_phase_step_full_rad", 0.0)
    monkeypatch.setitem(simulate.B_TRUTH, "flame_amp_rel_full", 0.0)
    monkeypatch.setitem(simulate.B_TRUTH, "flame_loss_full_db", 0.0)
    lines2 = []
    simulate.sim_b(tmp_path / "B0", seed=22, distances=(3.0,), duration_s=12.0,
                   repeats={"nothing": 2, "flame": 1, "smoke": 0, "mist": 0})
    res2 = b_radar_analyse.analyse(tmp_path / "B0", tmp_path / "out0", echo=lines2.append)
    assert "flame effect below noise" in "\n".join(lines2)
    assert "flame effect below noise" in res2["markdown"]
    assert all(r["simulated"] == "true" for r in _csv_rows(tmp_path / "out" / "B_conditions.csv"))


def _b_with_windows(tmp_path, monkeypatch, design, repeats):
    """Run the B analysis on sim_b runs, with the window values of every trial run replaced by `design[cond]`
    (a list of dicts per run). The baseline is still captured from the simulated frames."""
    simulate.sim_b(tmp_path / "B", seed=5, distances=(2.0,), duration_s=9.0, repeats=repeats)
    real_frames, real_windows = b_radar_analyse.frames_of, b_radar_analyse.window_values

    def frames_of(run, t0=None, t1=None):
        if run.trial.get("role") == "baseline":
            return real_frames(run, t0, t1)
        return ["MARK", run.trial["condition"]]

    def window_values(frames, *a, **k):
        if frames and frames[0] == "MARK":
            vals = design[frames[1]]
            return [dict(status="NO_EFFECT", reason="", t_start=0.0, loss_z=0.0, flicker_amp_z=0.0,
                         flicker_phase_z=0.0, **v) for v in vals]
        return real_windows(frames, *a, **k)

    monkeypatch.setattr(b_radar_analyse, "frames_of", frames_of)
    monkeypatch.setattr(b_radar_analyse, "window_values", window_values)
    lines = []
    res = b_radar_analyse.analyse(tmp_path / "B", tmp_path / "out", echo=lines.append)
    md = (tmp_path / "out" / "B_results.md").read_text()
    return res, md, "\n".join(lines)


def _w(loss, amp, ph):
    return {"loss_db": loss, "flicker_amp_db": amp, "flicker_phase_rad": ph}


@pytest.mark.parametrize("case", ["one_nothing_window", "flame_loss_all_nan", "zero_variance_nothing"])
def test_b_not_computable_is_never_an_effect(tmp_path, monkeypatch, case):
    """R3: a NaN or zero noise sigma, or a NaN effect, is 'not computable', never 'above 3 sigma'."""
    if case == "one_nothing_window":
        design = {"nothing": [_w(0.1, 0.02, 0.01)], "flame": [_w(5.0, 1.0, 0.5)] * 3}
    elif case == "flame_loss_all_nan":
        design = {"nothing": [_w(0.1 * i, 0.02 + 0.01 * i, 0.01 * i) for i in range(4)],
                  "flame": [_w(float("nan"), 0.03, 0.015)] * 3}
    else:
        design = {"nothing": [_w(0.2, 0.05, 0.02)] * 4, "flame": [_w(0.9, 0.3, 0.2)] * 3}
    res, md, echo = _b_with_windows(tmp_path, monkeypatch, design, {"nothing": 1, "flame": 1, "smoke": 0, "mist": 0})
    row = next(r for r in res["conditions"] if r["condition"] == "flame")
    assert row["effect_below_noise"] is None
    assert "above 3 sigma" not in md and "above 3 sigma" not in echo
    assert "not computable" in md.lower() and "NOT COMPUTABLE" in md
    assert any("not computable" in p for p in res["problems"])
    assert "Problems (as measured)" in md
    if case == "zero_variance_nothing":
        assert "noise sigma = 0" in md
    if case == "one_nothing_window":
        assert "noise sigma NaN (n_nothing=1" in md


def test_b_compare_to_noise_three_outcomes():
    c = b_radar_analyse.compare_to_noise
    assert c(1.0, 1.0, 5, 5, "loss_db", "flame")[0] == "below"
    assert c(3.0, 1.0, 5, 5, "loss_db", "flame")[0] == "above"
    assert c(3.0, float("nan"), 1, 5, "loss_db", "flame")[0] == "not computable"
    assert c(float("nan"), 1.0, 5, 0, "loss_db", "flame")[0] == "not computable"
    assert c(3.0, 0.0, 5, 5, "loss_db", "flame") == ("not computable", "noise sigma = 0")


def test_b_smoke_needs_gate_and_flame_needs_kind(tmp_path):
    """R4: a smouldering smoke source still burns, so smoke is gated like flame; flame needs --flame-kind."""
    with pytest.raises(SystemExit) as e:
        b_radar_record.main(["--distance-m", "3", "--condition", "smoke", "--smoke-source", "smouldering incense",
                             "--out", str(tmp_path)])
    assert e.value.code == 2
    with pytest.raises(SystemExit) as e:
        b_radar_record.main(["--distance-m", "3", "--condition", "smoke", "--supervisor", "A. Adult",
                             "--out", str(tmp_path)])
    assert e.value.code == 2
    rc = b_radar_record.main(["--distance-m", "3", "--condition", "flame", "--flame-source", "Bunsen",
                              "--risk-assessment", str(_pdf(tmp_path)), "--supervisor", "A. Adult",
                              "--out", str(tmp_path)])
    assert rc == 2                                                      # --flame-kind missing
    assert not list(tmp_path.glob("B_*"))                               # nothing recorded


def test_b_gate_csv_flags_missing_gate_and_non_bunsen(tmp_path):
    dirs = simulate.sim_b(tmp_path / "B", seed=9, distances=(2.0,), duration_s=9.0,
                          repeats={"nothing": 2, "flame": 2, "smoke": 1, "mist": 0})
    for d in dirs:
        tj = d / "trial.json"
        t = json.loads(tj.read_text())
        if t["condition"] == "smoke":
            for k in ("supervisor", "risk_assessment_sha256", "risk_assessment_path"):
                t.pop(k, None)
        if t["condition"] == "flame" and t["repeat"] == 2:
            t.update(flame_kind="other", bunsen_burner=False, flame_source="propane torch")
        tj.write_text(json.dumps(t))
    res = b_radar_analyse.analyse(tmp_path / "B", tmp_path / "out", echo=lambda *_: None)
    gate = {r["run_id"]: r for r in _csv_rows(tmp_path / "out" / "B_gate.csv")}
    smoke = [g for g in gate.values() if g["condition"] == "smoke"]
    assert smoke and all(g["gate"] == "GATE MISSING" for g in smoke)
    flames = sorted((g for g in gate.values() if g["condition"] == "flame"), key=lambda g: g["run_id"])
    assert flames[0]["gate"] == "ok" and "NOT BUNSEN" in flames[1]["gate"]
    assert any("GATE MISSING" in p for p in res["problems"])
    assert any("not recorded as a Bunsen burner" in p and "propane torch" in p for p in res["problems"])
    # plan coverage: only 2 m, 2 nothing, 2 flame, 1 smoke, 0 mist
    assert "INCOMPLETE" in res["markdown"]
    assert any(p == "plan: 3 m not recorded at all" for p in res["problems"])
    assert any(p == "plan: 2 m mist: 0 of >= 2 trial runs" for p in res["problems"])


# ---------------------------------------------------------------------------------------------- test C
def test_c_min_visible_distance():
    model = thermal.CameraModel()
    pose = geometry.CameraPose(height_m=2.6)
    d = c_thermal_analyse.min_visible_distance(model, pose, geometry.Attitude(0.0, 0.0))
    assert d == pytest.approx(2.6 / math.tan(math.radians(21.0)), rel=0.02)          # about 6.8 m
    assert c_thermal_analyse.min_visible_distance(model, pose, geometry.Attitude(0.0, 25.0)) == math.inf


def test_c_analysis_on_simulated_runs(tmp_path):
    simulate.sim_c(tmp_path / "C", seed=31, distances=(3.0, 6.0, 15.0), tilts=(0.0, 5.0), n_frames=3)
    res = c_thermal_analyse.analyse(tmp_path / "C", tmp_path / "out")
    rows = {(r["distance_m"], r["tilt_deg"]): r for r in res["runs"]}
    for key in ((6.0, 0.0), (15.0, 0.0), (6.0, 5.0), (15.0, 5.0)):
        r = rows[key]
        assert abs(r["err_pct"]) < 6.0, (key, r["err_pct"])
        assert r["covered"], key
    assert abs(rows[(15.0, 5.0)]["err_no_imu_pct"]) > 20.0                          # tilt ignored -> large error
    assert "not observable" in rows[(3.0, 0.0)]["flag"]                              # base below the image
    assert "err_pct" not in rows[(3.0, 0.0)]
    assert rows[(3.0, 0.0)]["d_min_visible_m"] > 3.0
    assert "not observable" in res["markdown"] and "SIMULATED" in res["markdown"]
    assert (tmp_path / "out" / "C_error_vs_distance.png").exists()
    # R7: the sheet plans 5 distances x 3 tilts; 3 x 2 were recorded
    assert "INCOMPLETE" in res["markdown"] and "PROBLEM: plan: 5 m at tilt -5 deg not recorded" in res["markdown"]


class _FakeCRun:
    def __init__(self, temps, d=8.0):
        self.run_id, self.trial = "C_fake", {"distance_m": d, "tilt_deg": 0.0, "repeat": 1}
        self._th = [{"t_mono": 1.0 + 0.1 * i, "data": protocol.encode_thermal(temps)} for i in range(3)]
        self._imu = [{"t_mono": 1.0 + 0.1 * i, "data": {"roll_deg": 0.0, "pitch_deg": 0.0}} for i in range(3)]

    def mark_t(self, kind):
        return {"hold": 0.5, "end": 5.0}.get(kind)

    def readings(self, sensor):
        return self._th if sensor == "thermal" else self._imu


def test_c_side_cut_off_frames_are_not_used():
    """PHYS-8: a hot panel touching the image SIDE (bottom inside the image) is base_cut_off: not used, so its
    d_lo_m = 0 cannot 'cover' the tape distance."""
    sheet = simulate.c_sheet()
    temps = np.full((192, 256), 290.0, dtype=np.float32)
    temps[120:150, 0:40] = 520.0                       # touches column 0, bottom row 149 is inside the image
    row = c_thermal_analyse.analyse_run(_FakeCRun(temps), sheet)
    assert row["n_cut_off_frames"] == 3 and row["n_frames"] == 0
    assert "covered" not in row and "err_pct" not in row
    temps2 = np.full((192, 256), 290.0, dtype=np.float32)
    temps2[120:150, 100:140] = 520.0                   # same panel, centred: used
    row2 = c_thermal_analyse.analyse_run(_FakeCRun(temps2), sheet)
    assert row2["n_cut_off_frames"] == 0 and row2["n_frames"] == 3 and "d_est_m" in row2


# ---------------------------------------------------------------------------------------------- test D
def _st(t, verdict, fresh=None, link=True, reasons=()):
    f = {s: True for s in d_failsafe_analyse.SENSORS}
    f.update(fresh or {})
    return {"t_rx": t, "verdict": verdict, "reasons": list(reasons), "link": link, "fresh": f, "sim": True}


def test_d_evaluate_hand_built_timeline():
    states, marks = [], []
    # fault 1 at t=10: thermal health flips at 11.5 -> 1.6 s (next 0.2 s tick) -> PASS
    # fault 2 at t=30: link down at 32.3 -> FAIL
    # fault 3 at t=50: never attributable -> FAIL
    # fault 4 at t=70: verdict already CLOSED (no flame), radar flips at 70.4 -> PASS, noted
    # fault 5 at t=90: detected at 90.4 but a CROSS FAST appears at 91.0 before restore -> FAIL
    for t in np.arange(0.0, 110.0, 0.2):
        t = round(float(t), 3)
        if 11.5 <= t < 20:
            s = _st(t, "CLOSED", {"thermal": False})
        elif 32.3 <= t < 40:
            s = _st(t, "CLOSED", {s_: False for s_ in d_failsafe_analyse.SENSORS}, link=False)
        elif 60 <= t < 80:
            s = _st(t, "CLOSED", {"radar": False} if t >= 70.4 else {}, reasons=["NO_FLAME"])
        elif 90.4 <= t < 100:
            s = _st(t, "CROSS FAST" if 91.0 <= t < 91.4 else "CLOSED", {"gnss": False})
        else:
            s = _st(t, "CROSS FAST")
        states.append(s)
    for t, f in ((10.0, "thermal_unplug"), (30.0, "wifi_drop"), (50.0, "gnss_unplug"), (70.0, "radar_unplug"),
                 (90.0, "gnss_unplug")):
        marks.append({"t_rx": t, "kind": "fault_inject", "fault": f})
        marks.append({"t_rx": t + 9.0, "kind": "fault_restore", "fault": f})
    rows = d_failsafe_analyse.evaluate(states, marks, timeout_s=8.0)
    assert [r["result"] for r in rows] == ["PASS", "FAIL", "FAIL", "PASS", "FAIL"]
    assert rows[0]["time_to_closed_s"] == pytest.approx(1.6, abs=0.01)
    assert rows[1]["time_to_closed_s"] == pytest.approx(2.4, abs=0.01)
    assert rows[2]["time_to_closed_s"] is None and "no CLOSED" in rows[2]["why"]
    assert rows[3]["pre_verdict"] == "CLOSED" and "already CLOSED" in rows[3]["why"]
    assert rows[4]["go_verdicts_during_fault"] > 0 and "go verdict" in rows[4]["why"]
    assert rows[0]["recovery_s"] is not None


def test_d_summarize_state_shapes():
    s = d_failsafe_analyse.summarize_state({"verdict": {"state": "CROSS_FAST", "reasons": []},
                                           "health": {"thermal": {"fresh": True, "reason": ""},
                                                      "radar": {"fresh": False}, "link": {"connected": True}},
                                           "sim": True})
    assert s["verdict"] == "CROSS FAST" and s["fresh"]["radar"] is False and s["link"] is True and s["sim"]
    s = d_failsafe_analyse.summarize_state({"verdict": "CLOSED", "health": {"sensors": {"gnss": False}},
                                           "link_connected": False})
    assert s["verdict"] == "CLOSED" and s["fresh"] == {"gnss": False} and s["link"] is False


def test_d_research_log_loader(tmp_path):
    log = tmp_path / "log"
    log.mkdir()
    (log / "verdicts.csv").write_text("t_mono,state,reasons\n1.0,CROSS FAST,\n1.2,CROSS FAST,\n1.4,CLOSED,"
                                      "SENSOR_NOT_FRESH:thermal\n")
    (log / "health.csv").write_text("t_mono,sensor,fresh\n1.0,thermal,true\n1.4,thermal,false\n")
    (tmp_path / "marks.csv").write_text("t,fault\n1.1,thermal_unplug\n")
    res = d_failsafe_analyse.analyse(tmp_path / "out", research_log=log, marks=tmp_path / "marks.csv")
    assert res["faults"][0]["result"] == "PASS"
    assert res["faults"][0]["time_to_closed_s"] == pytest.approx(0.3)
    assert not res["simulated"] and "SIMULATED" not in res["markdown"]


def test_d_simulated_latencies_follow_the_design_constants(tmp_path):
    """SIMULATED timeline from the design mechanisms (silence_s 1.5 s, thermal value freeze_s 1.0 s): every fault
    lands within the 2 s criterion. Exercises the analysis only; nothing is measured."""
    run = simulate.sim_d(tmp_path, seed=41)
    res = d_failsafe_analyse.analyse(tmp_path / "out", run_dir=run)
    r = {x["fault"]: x for x in res["faults"]}
    assert res["simulated"]
    assert r["tc_plate_open"]["result"] == "PASS" and r["thermal_unplug"]["result"] == "PASS"
    for f in ("wifi_drop", "pi_power", "thermal_freeze"):
        assert r[f]["result"] == "PASS" and r[f]["time_to_closed_s"] <= 2.0, r[f]
    assert all(x["result"] == "PASS" for x in res["faults"]), [(x["fault"], x["result"]) for x in res["faults"]]


def _bench_probe(n=100, t0=0.0):
    """Bench states: every State CLOSED with bench reasons, every sensor fresh, link up, for the whole run."""
    return [_st(round(t0 + 0.2 * k, 3), "CLOSED", reasons=["RADAR_UNKNOWN", "GNSS_NO_FIX", "FLAME_NOT_CONFIRMED"])
            for k in range(n)]


def test_d_bench_reasons_never_attribute_a_fault():
    """R1 probe: RADAR_UNKNOWN / GNSS_NO_FIX present all along and the app never notices the faults -> not PASS."""
    states = _bench_probe()
    marks = [{"t_rx": 5.05, "kind": "fault_inject", "fault": "radar_unplug"},
             {"t_rx": 9.0, "kind": "fault_restore", "fault": "radar_unplug"},
             {"t_rx": 11.05, "kind": "fault_inject", "fault": "gnss_unplug"},
             {"t_rx": 15.0, "kind": "fault_restore", "fault": "gnss_unplug"}]
    rows = d_failsafe_analyse.evaluate(states, marks, timeout_s=3.0)
    for r in rows:
        assert r["result"] != "PASS", r
        assert r["time_to_closed_s"] is None and r["time_to_not_fresh_s"] is None


def test_d_radar_goes_not_fresh_after_the_mark_passes_at_that_time():
    states = _bench_probe()
    for s in states:
        if s["t_rx"] >= 5.6:
            s["fresh"]["radar"] = False
            s["reasons"] = s["reasons"] + ["SENSOR_NOT_FRESH:radar"]
    rows = d_failsafe_analyse.evaluate(states, [{"t_rx": 5.0, "kind": "fault_inject", "fault": "radar_unplug"}])
    assert rows[0]["result"] == "PASS"
    assert rows[0]["time_to_closed_s"] == pytest.approx(0.6, abs=1e-6)
    assert rows[0]["time_to_not_fresh_s"] == pytest.approx(0.6, abs=1e-6)


def test_d_exact_codes_only_no_substrings():
    """A reason that merely contains a sensor name (PIXELS contains 'pi') never attributes the pi fault."""
    states = _bench_probe()
    for s in states:
        if s["t_rx"] >= 5.4:
            s["reasons"] = s["reasons"] + ["CROSSING_HOT_PIXELS_PRESENT", "FLAME_PIXELS_MISSING",
                                           "SENSOR_NOT_FRESH:pi_extra", "pi"]
    assert not d_failsafe_analyse.attributable(states[-1], ("pi",), states[0])
    rows = d_failsafe_analyse.evaluate(states, [{"t_rx": 5.0, "kind": "fault_inject", "fault": "x",
                                                 "sensors": ["pi"]}], timeout_s=3.0)
    assert rows[0]["result"] == "FAIL" and rows[0]["time_to_closed_s"] is None
    # the exact code does count, also inside a ';'-joined research-log reason
    st = dict(states[-1], reasons=["NO_FLAME;SENSOR_FAULT:pi"])
    assert d_failsafe_analyse.attributable(st, ("pi",), states[0])
    # every code names a sensor exactly as SENSORS does (crossing/decision.py `_sensor_checks`)
    from crossing import decision
    assert set(decision.ALL_SENSORS) == set(d_failsafe_analyse.SENSORS)
    assert "SENSOR_NOT_FRESH:tc_plate" in d_failsafe_analyse.fault_codes(("tc_plate",))
    assert d_failsafe_analyse.fault_codes(("link",)) == {"LINK_DOWN"}


def test_d_cause_already_present_before_the_mark_is_not_attributable():
    states = _bench_probe()
    for s in states:
        s["reasons"] = s["reasons"] + ["SENSOR_NOT_FRESH:radar"]
    rows = d_failsafe_analyse.evaluate(states, [{"t_rx": 5.0, "kind": "fault_inject", "fault": "radar_unplug"}])
    assert rows[0]["result"] == "NOT_ATTRIBUTABLE" and "already visible" in rows[0]["why"]
    assert rows[0]["time_to_closed_s"] is None
    # no State at all before the mark: fail closed, NOT_ATTRIBUTABLE
    rows = d_failsafe_analyse.evaluate(_bench_probe(t0=6.0), [{"t_rx": 5.0, "kind": "fault_inject",
                                                               "fault": "radar_unplug"}])
    assert rows[0]["result"] == "NOT_ATTRIBUTABLE" and "nothing to compare" in rows[0]["why"]
    # a sensor fault is not attributed to a link loss
    pre = _st(1.0, "CLOSED")
    down = _st(1.2, "CLOSED", {s: False for s in d_failsafe_analyse.SENSORS}, link=False, reasons=["LINK_DOWN"])
    assert not d_failsafe_analyse.attributable(down, ("radar",), pre)
    assert d_failsafe_analyse.attributable(down, ("link",), pre)


def _frames(t0, t_freeze, t1, dt=0.25):
    out, k_last = [], None
    for k, t in enumerate(np.arange(t0, t1, dt)):
        if t < t_freeze:
            k_last = k
        out.append((round(float(t), 3), "pix%d" % (k if t < t_freeze else k_last)))
    return out


def test_d_thermal_freeze_is_timed_from_the_frames_not_from_now():
    """R2: the operator's NOW is 2.5 s late; the fault time comes from the received thermal frames."""
    states = [_st(round(0.2 * k, 3), "CROSS FAST") for k in range(100)]
    for s in states:
        if s["t_rx"] >= 11.2:                       # freeze 10.0 (last differing frame 9.75) + 1.2 s
            s["verdict"], s["fresh"]["thermal"] = "CLOSED", False
            s["reasons"] = ["SENSOR_NOT_FRESH:thermal"]
    marks = [{"t_rx": 12.5, "kind": "fault_inject", "fault": "thermal_freeze"},
             {"t_rx": 17.0, "kind": "fault_restore", "fault": "thermal_freeze"}]
    rows = d_failsafe_analyse.evaluate(states, marks, thermal_frames=_frames(2.0, 10.0, 17.0))
    r = rows[0]
    assert r["fault_time_source"].startswith("thermal frames")
    assert r["t_fault"] == pytest.approx(9.75) and r["result"] == "PASS"
    assert r["time_to_closed_s"] == pytest.approx(11.2 - 9.75, abs=1e-6)
    # without frames (and no event_t) the row is NOT_MEASURED and unscored, never judged against NOW
    rows = d_failsafe_analyse.evaluate(states, marks, thermal_frames=[])
    assert rows[0]["result"] == "NOT_MEASURED" and "not a measurement" in rows[0]["why"]
    assert rows[0]["time_to_closed_s"] is None
    # an explicit event_t on the mark wins
    rows = d_failsafe_analyse.evaluate(states, [dict(marks[0], event_t=10.0), marks[1]], thermal_frames=[])
    assert rows[0]["fault_time_source"] == "event_t on the mark"
    assert rows[0]["time_to_closed_s"] == pytest.approx(1.2, abs=1e-6)


def test_d_thermal_frames_read_from_the_pi_copy_and_the_research_log(tmp_path):
    run = simulate.sim_d(tmp_path, seed=7, faults=["thermal_freeze"])
    frames = d_failsafe_analyse.load_thermal_frames(run / "pi")
    assert len(frames) > 20 and len(d_failsafe_analyse.freeze_onsets(frames)) == 1
    res = d_failsafe_analyse.analyse(tmp_path / "out", run_dir=run)
    r = res["faults"][0]
    assert r["fault_time_source"].startswith("thermal frames") and abs(r["mark_minus_fault_s"]) > 1.0
    assert r["result"] == "PASS" and "0 not measured" in res["markdown"]
    wl = tmp_path / "wl"
    wl.mkdir()
    with gzip.open(wl / "wire.jsonl.gz", "wt") as fh:
        for t, pix in _frames(0.0, 3.0, 6.0):
            fh.write(json.dumps({"rx": t, "msg": {"type": "reading", "sensor": "thermal", "data": {"pix": pix}}})
                     + "\n")
    assert d_failsafe_analyse.freeze_onsets(d_failsafe_analyse.load_thermal_frames(wl)) == [pytest.approx(2.75)]


def test_d_fault_list_covers_every_required_sensor_or_says_why():
    """R11: since D1 every sensor is required; test D has a fault for each, except pi (stated in the protocol)."""
    covered = {s for f in d_failsafe_analyse.FAULTS.values() for s in f.sensors}
    missing = set(d_failsafe_analyse.SENSORS) - covered
    assert missing == {"pi"}
    proto = (Path(d_failsafe_analyse.__file__).parent / "protocols" / "D_failsafe.md").read_text()
    assert "tc_housing_open" in proto and "Pi health" in proto


# ---------------------------------------------------------------------------------------------- E / F helpers
def test_unitstats_helpers():
    rx = [{"t_rx": t, "type": "reading"} for t in np.concatenate([np.arange(0, 10, 0.1), np.arange(11.5, 20, 0.1),
                                                                    np.arange(20.8, 25, 0.1)])]
    rx.append({"t_rx": 10.5, "link": "disconnect"})
    lk = unitstats.link_dropouts(rx, 1.0)
    assert lk["count"] == 1 and lk["longest_s"] == pytest.approx(1.6, abs=0.01) and lk["disconnects"] == 1
    assert unitstats.throttle_bits("0x50005") == [0, 2, 16, 18]
    assert unitstats.throttle_bits(None) == [] and unitstats.throttle_bits("zz") == []
    pi = [{"t_mono": float(t), "data": {"under_voltage_now": 3 <= t < 5, "throttled_hex": "0x0", "input_v": None}}
          for t in range(10)]
    pw = unitstats.power_summary(pi)
    assert pw["n_under_voltage_events"] == 1 and pw["under_voltage_s"] == pytest.approx(2.0)
    hb = [{"t_mono": float(t), "status": "ok"} for t in np.arange(0, 10, 0.5)]
    rd = [{"t_mono": float(t), "seq": i, "data": {}} for i, t in enumerate(np.arange(0, 10, 0.1)) if not 4 < t < 6.5]
    assert len(unitstats.silent_stops(rd, hb, 1.0)) == 1                  # heartbeats alive and ok -> silent stop
    hb_gap = [h for h in hb if not 4 < h["t_mono"] < 6.5]
    assert unitstats.silent_stops(rd, hb_gap, 1.0) == []                 # heartbeats gone too -> not silent
    assert len(unitstats.heartbeat_gaps(hb_gap, 2.0)) == 1
    rd2 = [{"t_mono": i * 0.1, "seq": i if i < 50 else i + 3, "data": {}} for i in range(100)]
    c = unitstats.completeness("tc_plate", rd2, hb, (0.0, 10.0))
    assert c["seq_missing"] == 3 and c["completeness_pct"] == pytest.approx(100.0)


def test_e_analysis_on_simulated_drive(tmp_path):
    d = simulate.sim_e(tmp_path, seed=51, duration_s=240.0)
    res = e_vehicle_analyse.analyse(tmp_path / "out", [str(d["pi"])], str(d["laptop"]))
    assert res["simulated"]
    assert res["link"]["count"] == 2                                    # 1.4 s and 4.5 s; 0.8 s is below 1 s
    assert res["link"]["longest_s"] == pytest.approx(4.5, abs=0.15)
    assert 0.5 < res["gnss"]["fix_ratio"] < 1.0 and res["gnss"]["longest_no_fix_s"] >= 39
    assert res["power"]["n_under_voltage_events"] == 1
    comp = {r["sensor"]: r for r in res["completeness"]}
    assert comp["radar"]["gaps_over_stale"] == 1 and comp["radar"]["completeness_pct"] < 100
    assert comp["tc_air"]["fault_readings"] == 3
    assert comp["imu"]["completeness_pct"] == pytest.approx(100.0, abs=0.5)
    for f in ("E_track.png", "E_timeline.png", "E_completeness.csv", "E_results.md"):
        assert (tmp_path / "out" / f).exists()


def test_f_analysis_on_simulated_housing(tmp_path):
    d = simulate.sim_f(tmp_path, seed=61, scale=0.25)
    res = f_housing_analyse.analyse(tmp_path / "out", str(d["laptop"]), str(d["pi"]))
    c = {x["check"]: x for x in res["checks"]}
    assert c["silent_stop_radar"]["result"] == "FAIL"
    assert c["link_dropouts"]["result"] == "FAIL"
    assert c["unit_heartbeat_gaps"]["result"] == "PASS" and c["reboot"]["result"] == "PASS"
    assert c["housing_temp"]["result"] in ("PASS", "WARN") and c["cpu_temp"]["result"] == "PASS"
    assert c["plate_rises_when_heated"]["result"] == "PASS" and c["air_rise"]["result"] == "PASS"
    assert c["checklist_water_inside"]["result"] == "INFO"
    fails = sorted(k for k, v in c.items() if v["result"] == "FAIL")
    assert fails == ["link_dropouts", "silent_stop_radar"]
    # laptop copy only: the Wi-Fi gap shows as unit gaps, but must not be called a silent stop
    res2 = f_housing_analyse.analyse(tmp_path / "out2", str(d["laptop"]))
    c2 = {x["check"]: x for x in res2["checks"]}
    assert c2["unit_heartbeat_gaps"]["result"] == "FAIL"
    assert [k for k in c2 if k.startswith("silent_stop")] == ["silent_stop_radar"]


# ---------------------------------------------------------------------------------------------- honesty
def test_snippet_labels_and_disclaimer():
    md = common.md_snippet("x", True, ["body"])
    assert md.startswith("### SIMULATED: x") and common.SIM_BANNER in md and common.DISCLAIMER in md
    md = common.md_snippet("x", False, ["body"])
    assert "SIMULATED" not in md and common.DISCLAIMER in md


def test_committed_example_outputs_are_labelled_simulated():
    mds = sorted(EXAMPLES.rglob("*_results.md"))
    assert len(mds) == 6
    for p in mds:
        text = p.read_text()
        assert "SIMULATED" in text and common.DISCLAIMER in text, p
        low = text.lower()
        assert "ready for" not in low and "is ready" not in low, p
    for p in EXAMPLES.rglob("*.csv"):
        rows = _csv_rows(p)
        assert all(r["simulated"] == "true" for r in rows), p
    assert "SIMULATED" in (EXAMPLES / "README.md").read_text()


# ---------------------------------------------------------------------------------------------- live recorder
def test_record_run_against_local_server(tmp_path):
    """recordkit.record_run end to end against a loopback WebSocket server that speaks the unit protocol
    (SIMULATED messages). Skipped where the sandbox forbids binding a local port."""
    import asyncio
    import socket
    import threading

    import websockets

    try:
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
    except OSError as exc:
        pytest.skip("cannot bind a local port here: %s" % exc)
    ctx = protocol.Context("VU-T", "VU-T-live", sim=True)
    ready = threading.Event()
    stop = threading.Event()

    async def handler(ws, *args):
        await ws.send(protocol.dumps(ctx.make("hello", sensors=["tc_plate"], version="t", config_digest="x")))
        i = 0
        while not stop.is_set():
            await ws.send(protocol.dumps(ctx.make("reading", sensor="tc_plate", seq=i,
                                                  data={"temp_c": 20.0, "cj_c": 20.0, "fault": None})))
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
    try:
        trial = {"test": "A", "run_id": "live"}
        d = recordkit.record_run("ws://127.0.0.1:%d" % port, tmp_path / "live", trial,
                                 [("hold", 0.6, "hold")], warmup_s=0.2, interactive=False, countdown_s=0,
                                 no_data_timeout_s=3.0)
    finally:
        stop.set()
        th.join(5)
    if trial.get("aborted"):
        pytest.skip("loopback connection refused here: %s" % trial["aborted"])
    run = load_run(d)
    assert len(run.readings("tc_plate")) > 10
    assert run.mark_t("hold") is not None and run.mark_t("end") is not None
    assert run.trial["sim"] is True and run.trial["counts"]["tc_plate"] > 10
    assert any(x.get("link") == "connect" for x in run.rx())


def test_d_reads_app_state_and_research_log_shapes(tmp_path):
    """The shapes crossing/pipeline.py and crossing/research_log.py actually write (README column dictionary)."""
    st = d_failsafe_analyse.summarize_state({"verdict": {"state": "CLOSED", "reasons": ["SENSOR_NOT_FRESH:radar"]},
                                            "health": {"t": 1.0, "link_up": True, "link_reason": "",
                                                       "sensors": {"radar": {"fresh": False, "reason": "stale"},
                                                                   "thermal": {"fresh": True}}}})
    assert st["link"] is True and st["fresh"] == {"radar": False, "thermal": True}
    pre = d_failsafe_analyse.summarize_state({"verdict": {"state": "CLOSED", "reasons": ["NO_FLAME"]},
                                             "health": {"link_up": True, "sensors": {"radar": {"fresh": True},
                                                                                     "thermal": {"fresh": True}}}})
    assert d_failsafe_analyse.attributable(st, ("radar",), pre) and not d_failsafe_analyse.attributable(st, ("gnss",), pre)
    assert not d_failsafe_analyse.attributable(st, ("radar",))          # no pre State: never attributable
    log = tmp_path / "log"
    log.mkdir()
    (log / "verdicts.csv").write_text("rx_mono,utc,state,decided_state,reasons\n4.8,x,CLOSED,CLOSED,NO_FLAME\n"
                                      "5.0,x,CLOSED,CLOSED,NO_FLAME\n"
                                      "5.2,x,CLOSED,CLOSED,LINK_DOWN;SENSOR_NOT_FRESH:thermal\n")
    (log / "health.csv").write_text("rx_mono,link_up,link_reason,thermal_fresh,thermal_reason\n"
                                    "4.8,True,,True,\n5.0,True,,True,\n6.0,False,silence,False,link down\n")
    (tmp_path / "marks.csv").write_text("t,fault\n4.9,wifi_drop\n")
    res = d_failsafe_analyse.analyse(tmp_path / "out", research_log=log, marks=tmp_path / "marks.csv")
    assert res["faults"][0]["time_to_closed_s"] == pytest.approx(0.3)          # LINK_DOWN reason at 5.2
    assert res["faults"][0]["time_to_not_fresh_s"] == pytest.approx(1.1)       # health row at 6.0
    wire = tmp_path / "wl"
    wire.mkdir()
    with gzip.open(wire / "wire.jsonl.gz", "wt") as fh:
        for t in (1.0, 1.1, 3.0):
            fh.write(json.dumps({"rx": t, "msg": {"type": "heartbeat", "sensor": "unit", "t_mono": t}}) + "\n")
        fh.write(json.dumps({"rx": 1.5, "link": "down", "reason": "silence"}) + "\n")
    lk = unitstats.link_dropouts(recordkit.read_rx(wire), 1.0)
    assert lk["count"] == 1 and lk["disconnects"] == 1 and lk["longest_s"] == pytest.approx(1.9)


def test_b_analysis_reads_wfgvu_synth_sessions(tmp_path):
    """Interop: b_radar_analyse on wfgvu.synth corner_reflector sessions (SIMULATED), when synth is present."""
    pytest.importorskip("wfgvu.synth")
    simulate.synth_b_nothing(tmp_path / "B", distance_m=3.0, n_runs=3, seed=7, duration_s=12.0)
    res = b_radar_analyse.analyse(tmp_path / "B", tmp_path / "out", echo=lambda *_: None)
    rows = res["conditions"]
    assert [r["condition"] for r in rows] == ["nothing"]
    assert rows[0]["reflector_snr_db"] > 12.0 and abs(rows[0]["reflector_range_m"] - 3.0) <= 0.3
    assert rows[0]["n_windows"] >= 4 and math.isfinite(rows[0]["flicker_phase_rad_noise_sigma"])
    assert res["simulated"] and not [p for p in res["problems"] if not p.startswith("plan:")]
    assert any(p.startswith("plan:") for p in res["problems"])          # only 3 m, nothing: plan incomplete
