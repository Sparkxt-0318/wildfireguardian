"""Overnight soak: sampling, analysis, the PASS or FAIL rules, and a whole soak against a
fake booth supervisor (scripts/mac_soak.py runs the real one)."""
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from wfglink.soak import (analyse_soak, append_row, count_log_events, format_report, judge_soak, load_samples,
                          mem_slope, paint_fps_series, pipeline_progress, reanalyse, run_soak, sample_row)

ROOT = Path(__file__).resolve().parents[1]
T0 = 1_760_000_000.0     # a fixed epoch for synthetic soaks
SC = {"fps_median_min": 20, "fps_p5_min": 10, "mem_slope_max_mb_h": 20.0, "mem_fit_last_h": 6.0, "mem_warmup_s": 600,
      "mem_min_hours": 2.0, "restarts_max": 0, "errors_max": 0, "analysis_stall_s": 180, "live_fraction_min": 0.9,
      "fallback_max": 0.0, "start_grace_s": 120, "stale_s": 30, "stop_timeout_s": 10, "progress_every_s": 600}


def _row(t: float, pid: int, uptime: float, rss: float, paints: float, clip="C5_nist_emberometer", source="playlist",
         state="playing", errors=0, status="running", paused=False) -> dict:
    return {"sample_epoch": t + 0.5, "sample_time": dt.datetime.fromtimestamp(t).isoformat(timespec="seconds"),
            "hb_epoch": t, "hb_age_s": 0.5, "status": status, "pid": pid, "uptime_s": uptime, "frames": paints,
            "paints": paints, "fps": 29.5, "source": source, "state": state, "clip": clip, "paused": int(paused),
            "errors": errors, "last_error": "", "rss_mb": rss, "rss_detail": "{}"}


def _soak_csv(path: Path) -> Path:
    """10 h soak sampled every 10 min: app 1 for 7 h (memory +40 MB/h over its first 3 h, then
    +10 MB/h), a restart, then app 2 for 3 h at +10 MB/h; each starts with a 10 minute warm-up.
    The clip changes every sample; app 2 falls back to synthetic video for a while."""
    t, rows = T0, []
    clips = ["C5_nist_emberometer", "C6_nist_dragon"]
    for k in range(0, 7 * 6):
        up = k * 600.0
        if up < 600:
            rss = 250 + up / 600 * 50          # warm-up, left out of the fit
        elif up < 3 * 3600:
            rss = 300 + 40 * up / 3600
        else:
            rss = 420 + 10 * (up - 3 * 3600) / 3600
        rows.append(_row(t + up, 111, up, rss, paints=30 * up, clip=clips[k % 2]))
    t2 = T0 + 7 * 3600 + 120
    for k in range(0, 3 * 6 + 1):
        up = k * 600.0
        rss = (250 + up / 600 * 50) if up < 600 else 300 + 10 * up / 3600
        fallback = 10 <= k < 15                # no clip could play for a while
        rows.append(_row(t2 + up, 222, up, rss, paints=20 * up, clip="synthetic" if fallback else clips[k % 2],
                         errors=2 if k > 12 else 0))
    for r in rows:
        append_row(path, r)
    return path


def _stamp(e: float) -> str:
    return dt.datetime.fromtimestamp(e).strftime("%Y-%m-%d %H:%M:%S")


# Analysis -------------------------------------------------------------------------------------

def test_mem_slope_is_pooled_within_app_instances(tmp_path):
    rows = load_samples(_soak_csv(tmp_path / "soak.csv"))
    m = mem_slope(rows, last_h=6.0, warmup_s=600)
    # The last 6 h hold the end of app 1 (+10 MB/h) and app 2 (+10 MB/h); the restart's drop
    # and the warm-up do not count.
    assert m["slope_mb_h"] == pytest.approx(10.0, abs=0.05)
    assert m["instances"] == 2
    whole = mem_slope(rows, last_h=24.0, warmup_s=600)
    assert whole["slope_mb_h"] > 12                        # app 1's early growth is in the window
    naive = mem_slope(rows, last_h=6.0, warmup_s=0)
    assert naive["slope_mb_h"] > 10.5                      # the warm-up would inflate the slope


def test_paint_fps_restarts_and_playback(tmp_path):
    csv_path = _soak_csv(tmp_path / "soak.csv")
    rows = load_samples(csv_path)
    fps = paint_fps_series(rows)
    assert len(fps) == len(rows) - 2                       # no interval across the restart
    assert sorted(set(round(v, 6) for v in fps)) == [20.0, 30.0]
    log = tmp_path / "booth.log"
    log.write_text("\n".join([
        f"{_stamp(T0 - 3600)} [booth.sh] app ended (code 1, status 'none', no hang) after 4 s; restarting in 2 s",
        f"{_stamp(T0 - 5)} [booth.sh] start: /w/.venv/bin/python -m wfglink live",
        "Traceback (most recent call last):",
        f"{_stamp(T0 + 7 * 3600 + 60)} [booth.sh] hang detected (heartbeat is 31 s old); restarting the app",
        f"{_stamp(T0 + 7 * 3600 + 61)} [booth.sh] app ended (code 143, status 'running', heartbeat is 31 s old) after 25200 s; restarting in 2 s",
        f"{_stamp(T0 + 11 * 3600)} [booth.sh] app ended (code 130, status 'none', no hang) after 3 s; restarting in 2 s",
    ]) + "\n")
    rotated = tmp_path / "booth.log.1"
    rotated.write_text(f"{_stamp(T0 + 3600)} [booth.sh] app ended (code 1, status 'none', no hang) after 3600 s; restarting in 2 s\n")
    ev = count_log_events(log, T0, T0 + 10 * 3600 + 300)
    assert ev["restarts"] == 2 and ev["hangs"] == 1        # before the start and after the end are left out
    rep = analyse_soak(csv_path, log, T0, T0 + 10 * 3600 + 300, last_h=6, warmup_s=600, mem_max_mb_h=20, min_hours=1)
    assert rep["hours"] == pytest.approx(10.08, abs=0.01)
    assert rep["paint_fps_median"] == 30.0 and rep["paint_fps_p5"] == 20.0
    assert rep["memory"]["verdict"] == "pass" and rep["memory"]["slope_mb_h"] == pytest.approx(10.0, abs=0.05)
    assert rep["restarts"] == 2 and rep["hangs"] == 1 and rep["instances"] == 2
    pb = rep["playback"]
    assert pb["sources"] == ["playlist"] and set(pb["clips"]) == {"C5_nist_emberometer", "C6_nist_dragon", "synthetic"}
    assert pb["fallback_samples"] == 5 and pb["fallback_fraction"] == pytest.approx(5 / len(rows), abs=1e-3)
    assert rep["errors"] == 2
    strict = analyse_soak(csv_path, log, T0, None, last_h=6, warmup_s=600, mem_max_mb_h=5, min_hours=1)
    assert strict["memory"]["verdict"] == "fail"
    short = analyse_soak(csv_path, log, T0, None, last_h=6, warmup_s=600, mem_max_mb_h=20, min_hours=20)
    assert short["memory"]["verdict"] == "too short to judge"


def test_sample_row_copies_the_heartbeat_and_tolerates_missing_keys():
    hb = {"status": "running", "epoch": T0, "pid": 7, "uptime_s": 12.0, "frames": 300, "paints": 310, "fps": 29.8,
          "source": "playlist", "state": "playing", "clip": "C6_nist_dragon", "paused": True, "errors": 0,
          "last_error": None, "rss_mb": {"7": 410.5, "8": 120.0},
          "pipeline": {"key": "C6_nist_dragon", "frames_in": 90, "frames_analysed": 60, "frames_duplicate": 30}}
    row = sample_row(hb, now=T0 + 1)
    assert row["clip"] == "C6_nist_dragon" and row["paused"] == 1 and row["rss_mb"] == 530.5
    assert row["pipe_key"] == "C6_nist_dragon" and row["pipe_in"] == 90 and row["pipe_analysed"] == 60
    bare = sample_row({"status": "running", "epoch": T0, "pid": 7}, now=T0 + 1)
    assert bare["pipe_in"] == "" and bare["clip"] == "" and bare["paused"] == "" and bare["status"] == "running"
    assert sample_row(hb, now=T0 + 31)["status"] == "stale"
    assert sample_row(None, now=T0)["status"] == "missing"
    # The mode, raw and the camera state are kept, so an ember soak shows what ember mode did.
    ember = sample_row(dict(hb, mode="ember", raw=False, camera_state="ok", clip=None), now=T0 + 1)
    assert (ember["mode"], ember["raw"], ember["camera_state"], ember["clip"]) == ("ember", 0, "ok", "")
    assert bare["mode"] == "" and bare["camera_state"] == ""
    # A child process whose memory could not be read: no sum (it would look like a release).
    assert sample_row({"status": "running", "epoch": T0, "pid": 1, "rss_mb": {"1": 400.0, "2": None}},
                      now=T0 + 1)["rss_mb"] == ""


def _pipe_rows(path: Path) -> Path:
    """Booth soak sampled every minute on one app: 10 min of normal analysis of clip A (30
    frames/s in, 25 analysed, 5 repeats), 5 min in which frames keep arriving but none is
    analysed (the heartbeat frame counter still moves: repeats), 3 min paused, 4 min of clip
    B (a new pipeline), then 5 samples in which nothing at all happens."""
    rows, t = [], T0
    c = {"frames": 0.0, "paints": 0.0, "pipe_in": 0.0, "pipe_analysed": 0.0, "pipe_duplicate": 0.0}

    def add(key, minutes, mode, paused=False):
        nonlocal t
        for _ in range(minutes):
            rows.append({**_row(t, 111, t - T0, 300.0, c["paints"], clip=key, paused=paused), **c, "pipe_key": key})
            t += 60.0
            if mode == "normal":
                c.update({k: c[k] + v for k, v in (("frames", 1800), ("paints", 1800), ("pipe_in", 1800),
                                                   ("pipe_analysed", 1500), ("pipe_duplicate", 300))})
            elif mode == "repeats":
                c.update({k: c[k] + v for k, v in (("frames", 1800), ("paints", 1800), ("pipe_in", 1800),
                                                   ("pipe_duplicate", 1800))})

    add("A", 10, "normal")
    add("A", 5, "repeats")
    add("A", 3, "none", paused=True)
    for k in ("pipe_in", "pipe_analysed", "pipe_duplicate"):
        c[k] = 0.0
    add("B", 4, "normal")
    add("B", 5, "none")
    for r in rows:
        append_row(path, r)
    return path


def test_pipeline_progress_finds_analysis_stalls(tmp_path):
    rows = load_samples(_pipe_rows(tmp_path / "soak.csv"))
    p = pipeline_progress(rows, stall_s=180.0)
    assert p["verdict"] == "fail" and p["stalls"] == 2
    first, second = p["stall_list"]
    # 5 minutes of repeats, but the minute that ends paused (Space pressed) is left out.
    assert first["cause"] == "repeated frames only" and first["minutes"] == pytest.approx(4.0)
    assert second["cause"] == "no frames" and second["minutes"] == pytest.approx(4.0)
    # The paused minutes are neither a stall nor progress; paint fps leaves them out too.
    assert len(paint_fps_series(rows)) == len(rows) - 1 - 4
    assert pipeline_progress(rows, stall_s=400.0)["verdict"] == "pass"
    # One short clip in a loop: every minute its pipeline starts again under the same key,
    # and the counters can read the same at both samples (a clip of mostly repeated frames).
    # That is a restart (they grew by far less than the 1800 frames processed), not a stall.
    loop = [{**_row(T0 + 60 * k, 5, 60 * k, 300.0, 1800 * k, clip="C6_nist_dragon"), "frames": 1800 * k,
             "pipe_key": "C6_nist_dragon", "pipe_in": 270, "pipe_analysed": 12, "pipe_duplicate": 258} for k in range(10)]
    lp = tmp_path / "loop.csv"
    for r in loop:
        append_row(lp, r)
    assert pipeline_progress(load_samples(lp), stall_s=180.0)["verdict"] == "pass"
    # An old CSV without the frame counter cannot be judged.
    plain = tmp_path / "plain.csv"
    for r in rows:
        append_row(plain, {k: v for k, v in r.items() if k != "frames"})
    assert pipeline_progress(load_samples(plain))["verdict"] == "not enough data"


def test_soak_edge_cases(tmp_path):
    # A file begun by an older sampler keeps its columns.
    old = tmp_path / "old.csv"
    old.write_text("sample_epoch,status,pid\n1.0,running,5\n")
    append_row(old, {"sample_epoch": 2.0, "status": "running", "pid": 6, "hb_status": "running"})
    assert old.read_text().splitlines()[-1] == "2.0,running,6"
    rows = []
    # One app for 3 h, sampled twice per heartbeat at first (duplicates); its child process is
    # replaced after 2 h (memory starts again from 100 MB); 5 MB/h throughout.
    for k in range(0, 37):
        up = k * 300.0
        child = "11" if up < 7200 else "12"
        cmem = 100 + 5 * (up if up < 7200 else up - 7200) / 3600
        r = _row(T0 + up, 10, up, 300 + 5 * up / 3600 + cmem, paints=30 * up)
        r["rss_detail"] = json.dumps({"10": 1.0, child: 1.0})
        rows.append(r)
        if k < 3:
            rows.append({**r, "sample_epoch": r["sample_epoch"] + 0.2})
    # Esc pressed twice at 3 h; then a booth started for the rehearsal (another pid) wrote the
    # heartbeat for another hour, and the Mac slept for 40 minutes before that.
    t_exit = T0 + 3 * 3600 + 30
    rows.append({**_row(t_exit, 10, 3 * 3600 + 30, 330, paints=30 * 3 * 3600), "status": "stale",
                 "hb_status": "clean_exit"})
    for k in range(1, 4):
        rows.append(_row(t_exit + 2400 + k * 600, 99, k * 600.0, 900, paints=10 * k * 600))
    csv_path = tmp_path / "soak.csv"
    for r in rows:
        append_row(csv_path, r)
    soak_rows = [r for r in load_samples(csv_path) if r["pid"] == "10"]
    assert len(paint_fps_series(soak_rows)) == 36                    # duplicates dropped
    m = mem_slope(soak_rows, last_h=6.0, warmup_s=0)
    assert m["slope_mb_h"] == pytest.approx(10.0, abs=0.05) and m["instances"] == 2
    rep = analyse_soak(csv_path, tmp_path / "none.log", T0, T0 + 5 * 3600, last_h=6, warmup_s=0,
                       mem_max_mb_h=20, min_hours=1)
    assert rep["ended_by"].startswith("clean exit")
    assert rep["hours"] == pytest.approx(3.0, abs=0.02)              # the soak ended at the clean exit
    assert rep["instances"] == 1 and rep["pid_changes"] == 0         # the rehearsal booth is not the soak
    assert rep["hours_running"] == pytest.approx(3.0, abs=0.01)
    # Without the clean exit, the rehearsal app would count; the gap shows up in the samples.
    for r in rows:
        r.pop("hb_status", None)
    plain = tmp_path / "plain.csv"
    for r in rows:
        if r.get("status") != "stale":
            append_row(plain, r)
    rep2 = analyse_soak(plain, tmp_path / "none.log", T0, T0 + 5 * 3600, last_h=6, warmup_s=0)
    assert rep2["instances"] == 2 and rep2["pid_changes"] == 1 and rep2["sampling_gaps"] == 1
    assert rep2["live_fraction"] == 1.0
    # The same file can hold an earlier soak, and the first sample can still read the heartbeat
    # an earlier booth left behind after Esc (before booth.sh removes it): neither belongs to
    # this soak, nor ends it. Missing heartbeats while the app starts are not downtime.
    early = tmp_path / "early.csv"
    for k in range(6):
        append_row(early, _row(T0 - 3600 + k * 300, 7, k * 300.0, 500, paints=30 * k * 300))
    append_row(early, sample_row({"status": "clean_exit", "epoch": T0 - 1800, "pid": 7, "rss_mb": {"7": 500.0}},
                                 now=T0 + 0.3))
    append_row(early, sample_row(None, now=T0 + 0.4))
    for r in rows[:40]:              # the soak app only (37 heartbeats, 3 read twice)
        append_row(early, r)
    rep3 = analyse_soak(early, tmp_path / "none.log", T0, T0 + 3 * 3600, last_h=6, warmup_s=0)
    assert rep3["ended_by"] == "finish" and rep3["hours"] == pytest.approx(3.0, abs=0.01)
    assert rep3["samples_live"] == 37 and rep3["paint_fps_intervals"] == 36
    assert rep3["instances"] == 1 and rep3["samples"] == 42 and rep3["samples_startup"] == 2
    assert rep3["live_fraction"] == 1.0


# Verdict --------------------------------------------------------------------------------------

def _analysis(**over) -> dict:
    a = {"ok": True, "hours": 8.0, "hours_running": 8.0, "ended_by": "finish", "samples": 480, "samples_startup": 1,
         "samples_live": 479, "live_fraction": 1.0, "paint_fps_median": 29.9, "paint_fps_p5": 28.0,
         "paint_fps_intervals": 478, "instances": 1,
         "memory": {"slope_mb_h": 2.0, "span_h": 7.8, "max_mb_h": 20.0, "min_hours": 2.0, "verdict": "pass"},
         "restarts": 0, "hangs": 0, "errors": 0, "last_error": None,
         "pipeline": {"intervals": 478, "stall_s": 180.0, "stalls": 0, "stall_minutes": 0.0, "stall_list": [],
                      "verdict": "pass"},
         "playback": {"sources": ["playlist"], "clips": {"C5": 240, "C6": 239}, "clip_changes": 300,
                      "playlist_samples": 479, "fallback_samples": 0, "fallback_fraction": 0.0}}
    a.update(over)
    return a


def test_judge_soak_pass_and_each_failure():
    j = judge_soak(_analysis(), SC, 8, "the time limit")
    assert j["verdict"] == "PASS" and not j["not_judged"]
    assert [c["name"] for c in j["checks"]] == ["duration", "paint fps", "memory", "restarts", "analysis", "errors",
                                               "heartbeat", "playlist"]
    text = format_report({"judgement": j, "files": {"report": "r.json"}})
    assert text.splitlines()[0] == "wfglink soak: PASS" and all(ln.split()[0] == "OK" for ln in text.splitlines()[1:-1])
    assert text.splitlines()[-1].split() == ["report", "r.json"]
    bad = {
        "paint fps": _analysis(paint_fps_p5=8.0),
        "memory": _analysis(memory={"slope_mb_h": 25.0, "span_h": 7.8, "max_mb_h": 20.0, "min_hours": 2.0,
                                    "verdict": "fail"}),
        "restarts": _analysis(restarts=1, hangs=1),
        "analysis": _analysis(pipeline={"intervals": 9, "stall_s": 180.0, "stalls": 1, "stall_minutes": 4.0,
                                        "stall_list": [{"at": "x", "minutes": 4.0, "cause": "no frames"}],
                                        "verdict": "fail"}),
        "errors": _analysis(errors=3, last_error="ValueError: x"),
        "heartbeat": _analysis(live_fraction=0.5),
        "playlist": _analysis(playback={"sources": ["playlist"], "clips": {"synthetic": 9}, "clip_changes": 0,
                                        "playlist_samples": 9, "fallback_samples": 9, "fallback_fraction": 1.0}),
    }
    for name, a in bad.items():
        j = judge_soak(a, SC, 8, "the time limit")
        assert j["verdict"] == "FAIL" and j["failed"] == [name], name
    # The supervisor ending by itself with an error fails; Esc pressed twice does not.
    assert judge_soak(_analysis(), SC, 8, "booth.sh ended by itself (exit code 2)", 2)["failed"] == ["duration"]
    assert judge_soak(_analysis(ended_by="clean exit (Esc pressed twice)"), SC, 8,
                      "booth.sh ended by itself (exit code 0)", 0)["verdict"] == "PASS"
    # A short soak passes without judging memory, and says so; synthetic video has no playlist check.
    short = judge_soak(_analysis(memory={"slope_mb_h": 1.0, "span_h": 0.2, "max_mb_h": 20.0, "min_hours": 2.0,
                                         "verdict": "too short to judge"},
                                 playback={"sources": ["synthetic"], "clips": {"synthetic": 9}, "clip_changes": 0,
                                           "playlist_samples": 0, "fallback_samples": 0, "fallback_fraction": None}),
                       SC, 0.5, "Ctrl-C")
    assert short["verdict"] == "PASS" and short["not_judged"] == ["memory", "playlist"]
    assert "too short to judge" in format_report({"judgement": short})
    assert judge_soak({"ok": False, "error": "no soak samples"}, SC)["verdict"] == "FAIL"


# A whole soak against a fake supervisor --------------------------------------------------------

FAKE_BOOTH = r'''
import json, os, signal, sys, time
logdir, mode = sys.argv[1], sys.argv[2]
hb, log = os.path.join(logdir, "heartbeat.json"), os.path.join(logdir, "booth.log")
def say(text):
    with open(log, "a") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S") + " [booth.sh] " + text + "\n")
def bye(signum, frame):
    say("supervisor stopped by signal")
    sys.exit(130)
signal.signal(signal.SIGTERM, bye)
say("start: fake booth " + mode)
if mode == "broken":
    sys.exit(2)
t0, n = time.time(), 0
while True:
    n += 1
    status = "clean_exit" if mode == "esc" and time.time() - t0 > 1.5 else "running"
    data = {"status": status, "epoch": time.time(), "pid": os.getpid(), "uptime_s": time.time() - t0,
            "frames": 30 * n, "paints": 30 * n, "fps": 30.0, "source": "playlist", "state": "playing",
            "clip": "C5_nist_emberometer" if n % 10 < 5 else "C6_nist_dragon", "paused": False, "errors": 0,
            "last_error": None, "rss_mb": {str(os.getpid()): 300.0},
            "pipeline": {"key": "C5", "frames_in": 30 * n, "frames_analysed": 30 * n, "frames_duplicate": 0}}
    with open(hb + ".tmp", "w") as f:
        json.dump(data, f)
    os.replace(hb + ".tmp", hb)
    if status == "clean_exit":
        say("clean exit after 2 s (Esc pressed twice, or --duration ended); supervisor done")
        sys.exit(0)
    time.sleep(0.1)
'''


@pytest.mark.parametrize("mode", ["run", "esc", "broken"])
def test_run_soak_against_a_fake_supervisor(tmp_path, mode):
    fake = tmp_path / "fake_booth.py"
    fake.write_text(FAKE_BOOTH)
    logdir = tmp_path / "logs"
    logdir.mkdir()
    cmd = [sys.executable, str(fake), str(logdir), mode]
    lines: list[str] = []
    t = time.monotonic()
    rep = run_soak(4.0 / 3600, cmd, tmp_path / "soak", every_s=0.5, sc={**SC, "progress_every_s": 1.0},
                   logdir=logdir, echo=lines.append)
    assert time.monotonic() - t < 30
    out = tmp_path / "soak"
    assert json.loads((out / "soak_report.json").read_text())["verdict"] == rep["verdict"]
    assert (out / "soak.csv").exists() and json.loads((out / "soak_meta.json").read_text())["ended_by"] == rep["ended_by"]
    checks = {c["name"]: c["status"] for c in rep["judgement"]["checks"]}
    if mode == "run":
        assert rep["ended_by"] == "the time limit" and rep["supervisor_exit_code"] == 130
        assert "supervisor stopped by signal" in (logdir / "booth.log").read_text()
        assert rep["verdict"] == "PASS", format_report(rep)
        assert checks["memory"] == "not judged" and checks["paint fps"] == "OK" and checks["playlist"] == "OK"
        assert any("of 0.00111 h" in ln or "paint" in ln for ln in lines[2:])      # a progress line
    elif mode == "esc":
        assert rep["ended_by"] == "booth.sh ended by itself (exit code 0)"
        assert rep["analysis"]["ended_by"].startswith("clean exit") and checks["duration"] == "OK"
    else:
        assert rep["verdict"] == "FAIL" and checks["duration"] == "FAIL" and rep["supervisor_exit_code"] == 2
    # The soak folder can be analysed again (for a soak cut off before its report).
    again = reanalyse(out, sc=SC)
    assert again["verdict"] == rep["verdict"]
    assert not any(str(fake) in p for p in _ps())                   # nothing left running


def _ps() -> list[str]:
    out = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True).stdout
    return out.splitlines()


def test_mac_soak_script_help_and_python_choice(tmp_path):
    env = {**os.environ, "WFG_PY": sys.executable, "PYTHONPATH": str(ROOT / "src")}
    res = subprocess.run([sys.executable, str(ROOT / "scripts" / "mac_soak.py"), "--help"], capture_output=True,
                         text=True, env=env, timeout=60)
    assert res.returncode == 0 and "--hours" in res.stdout
    # Without the project's .venv and no WFG_PY, the script says how to install.
    env.pop("WFG_PY")
    fake_root = tmp_path / "wfglink"
    (fake_root / "scripts").mkdir(parents=True)
    (fake_root / "scripts" / "mac_soak.py").write_text((ROOT / "scripts" / "mac_soak.py").read_text())
    res = subprocess.run([sys.executable, str(fake_root / "scripts" / "mac_soak.py"), "--hours", "1"],
                         capture_output=True, text=True, env=env, timeout=60)
    assert res.returncode == 2 and "setup_mac.sh" in res.stderr
