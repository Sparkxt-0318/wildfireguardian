"""Sitting 2: hold-factor choice, unplug timing, soak analysis, sampler, and the dry run."""
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from wfglink.sitting.sitting2 import choose_hold, merge_local_config, run_stats, unplug_timing
from wfglink.sitting.soak import (analyse_soak, append_row, count_log_events, load_samples, mem_slope,
                                  paint_fps_series, run_sampler)

ROOT = Path(__file__).resolve().parents[1]
T0 = 1_760_000_000.0     # a fixed epoch for synthetic soaks


def test_choose_hold():
    assert choose_hold(0.85, None, 0.8)["hold_factor"] == 2
    c = choose_hold(0.72, 0.86, 0.8)
    assert c["hold_factor"] == 3 and c["meets_min"]
    c = choose_hold(0.70, 0.76, 0.8)            # both below: the better one, flagged
    assert c["hold_factor"] == 3 and not c["meets_min"]
    assert choose_hold(0.70, 0.65, 0.8)["hold_factor"] == 2
    assert choose_hold(None, 0.9, 0.8)["hold_factor"] == 3
    assert choose_hold(None, None, 0.8)["hold_factor"] == 2


def test_unplug_timing_from_chain_events():
    ev = [{"t": 100.0, "event": "activated", "key": "iphone", "reason": "start"},
          {"t": 116.0, "event": "failed", "key": "iphone", "reason": "no frames"},
          {"t": 116.05, "event": "activated", "key": "replay", "reason": "start"},
          {"t": 116.6, "event": "probe", "key": "iphone"},
          {"t": 116.7, "event": "failed", "key": "iphone", "reason": "device not available"},
          {"t": 137.0, "event": "probe", "key": "iphone"},
          {"t": 142.5, "event": "activated", "key": "iphone", "reason": "switched back after sustained health"}]
    r = unplug_timing(ev, "iphone", 115.0, 135.0, 15.0)
    assert r["fallback_key"] == "replay"
    assert r["detect_s"] == 1.0 and r["fall_back_s"] == 1.05 and r["recover_s"] == 7.5
    assert r["pass"]
    slow = unplug_timing(ev, "iphone", 115.0, 125.0, 15.0)      # back 17.5 s after the prompt
    assert slow["recover_s"] == 17.5 and not slow["pass"]
    never = unplug_timing(ev[:5], "iphone", 115.0, 135.0, 15.0)
    assert never["recover_s"] is None and not never["pass"] and "did not come back" in never["note"]
    idle = unplug_timing(ev[:1], "iphone", 115.0, 135.0, 15.0)
    assert not idle["pass"] and "never failed" in idle["note"]


def test_merge_local_config_keeps_sitting1_settings():
    s1 = {"camera": {"backend": "pyav", "fps": 30, "iphone_uid": "X"}, "booth": {"launcher": "app"}}
    merged = merge_local_config(s1, {"booth": {"hold_factor": 3, "replay_clip": "data/booth/C1_hold3.mp4"},
                                     "live": {"worker_mode": "process"}, "ui": {"screen": "external"}})
    assert merged["camera"] == s1["camera"]
    assert merged["booth"] == {"launcher": "app", "hold_factor": 3, "replay_clip": "data/booth/C1_hold3.mp4"}
    assert merged["live"] == {"worker_mode": "process"} and merged["ui"] == {"screen": "external"}


def test_run_stats_reads_the_booth_report():
    res = {"seconds": 20.0, "frames": 500, "paints": 560, "errors": [], "source": "iphone",
           "last": {"fps": 25.0}, "source_events": [{"t": 1.0, "event": "activated", "key": "iphone"}],
           "pipelines": {"iphone": {"frames_in": 500, "frames_analysed": 150, "frames_duplicate": 230,
                                    "frames_unclean": 120, "frames_blended": 70, "frames_torn": 50,
                                    "frames_no_code": 0, "loops": 0, "clean_frame_yield": 0.76}}}
    st = run_stats(res, "iphone", hold=2)
    assert st["clean_frame_yield"] == 0.76 and st["paint_fps"] == 28.0
    assert st["blended_fraction"] == 0.14 and st["torn_fraction"] == 0.1
    # 500 frames at 25 fps is 20 s; the iPad shows 15 source frames per second at hold 2.
    assert st["source_coverage_est"] == pytest.approx(150 / 300, abs=1e-3)
    assert run_stats(res, "webcam")["clean_frame_yield"] is None


# Soak analysis ----------------------------------------------------------------------------------

def _row(t: float, pid: int, uptime: float, rss: float, paints: float, source="iPhone", state="live",
         errors=0, status="running") -> dict:
    return {"sample_epoch": t + 0.5, "sample_time": dt.datetime.fromtimestamp(t).isoformat(timespec="seconds"),
            "hb_epoch": t, "hb_age_s": 0.5, "status": status, "pid": pid, "uptime_s": uptime, "frames": paints,
            "paints": paints, "fps": 29.5, "source": source, "state": state, "errors": errors, "last_error": "",
            "rss_mb": rss, "rss_detail": "{}"}


def _soak_csv(path: Path) -> Path:
    """10 h soak sampled every 10 min: app 1 for 7 h (memory +40 MB/h over its first 3 h, then
    +10 MB/h), a restart, then app 2 for 3 h at +10 MB/h; each starts with a 10 minute warm-up."""
    t, rows = T0, []
    for k in range(0, 7 * 6):
        up = k * 600.0
        if up < 600:
            rss = 250 + up / 600 * 50          # warm-up, left out of the fit
        elif up < 3 * 3600:
            rss = 300 + 40 * up / 3600
        else:
            rss = 420 + 10 * (up - 3 * 3600) / 3600
        rows.append(_row(t + up, 111, up, rss, paints=30 * up, errors=0))
    t2 = T0 + 7 * 3600 + 120
    for k in range(0, 3 * 6 + 1):
        up = k * 600.0
        rss = (250 + up / 600 * 50) if up < 600 else 300 + 10 * up / 3600
        replay = 10 <= k < 15                  # the iPhone dropped out for a while
        rows.append(_row(t2 + up, 222, up, rss, paints=20 * up, source="C1_hold2.mp4" if replay else "iPhone",
                         state="replay" if replay else "live", errors=2 if k > 12 else 0))
    for r in rows:
        append_row(path, r)
    return path


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


def test_paint_fps_and_soak_report(tmp_path):
    csv_path = _soak_csv(tmp_path / "soak.csv")
    rows = load_samples(csv_path)
    fps = paint_fps_series(rows)
    assert len(fps) == len(rows) - 2                       # no interval across the restart
    assert sorted(set(round(v, 6) for v in fps)) == [20.0, 30.0]
    log = tmp_path / "booth.log"
    stamp = lambda e: dt.datetime.fromtimestamp(e).strftime("%Y-%m-%d %H:%M:%S")  # noqa: E731
    log.write_text("\n".join([
        f"{stamp(T0 - 3600)} [booth.sh] app ended (code 1, status 'none', no hang) after 4 s; restarting in 2 s",
        f"{stamp(T0 - 5)} [booth.sh] start: launcher=terminal args=--replay-clip x",
        "Traceback (most recent call last):",
        f"{stamp(T0 + 7 * 3600 + 60)} [booth.sh] hang detected (heartbeat is 31 s old); restarting the app",
        f"{stamp(T0 + 7 * 3600 + 61)} [booth.sh] app ended (code 143, status 'running', heartbeat is 31 s old) after 25200 s; restarting in 2 s",
        f"{stamp(T0 + 11 * 3600)} [booth.sh] app ended (code 130, status 'none', no hang) after 3 s; restarting in 2 s",
    ]) + "\n")
    rotated = tmp_path / "booth.log.1"
    rotated.write_text(f"{stamp(T0 + 3600)} [booth.sh] app ended (code 1, status 'none', no hang) after 3600 s; restarting in 2 s\n")
    ev = count_log_events(log, T0, T0 + 10 * 3600 + 300)
    assert ev["restarts"] == 2 and ev["hangs"] == 1        # before the start and after the end are left out
    rep = analyse_soak(csv_path, log, T0, T0 + 10 * 3600 + 300, last_h=6, warmup_s=600, mem_max_mb_h=20, min_hours=1)
    assert rep["hours"] == pytest.approx(10.08, abs=0.01)
    assert rep["paint_fps_median"] == 30.0 and rep["paint_fps_p5"] == 20.0
    assert rep["memory"]["verdict"] == "pass" and rep["memory"]["slope_mb_h"] == pytest.approx(10.0, abs=0.05)
    assert rep["restarts"] == 2 and rep["hangs"] == 1
    assert rep["source_switches"] == 2                      # to replay and back; the restart itself is none
    assert rep["errors"] == 2
    strict = analyse_soak(csv_path, log, T0, None, last_h=6, warmup_s=600, mem_max_mb_h=5, min_hours=1)
    assert strict["memory"]["verdict"] == "fail"
    short = analyse_soak(csv_path, log, T0, None, last_h=6, warmup_s=600, mem_max_mb_h=20, min_hours=20)
    assert short["memory"]["verdict"] == "not enough data"


def test_sampler_writes_rows_and_cleans_up(tmp_path):
    hb = tmp_path / "heartbeat.json"
    hb.write_text(json.dumps({"status": "running", "epoch": __import__("time").time(), "pid": 4242, "uptime_s": 12.0,
                              "frames": 300, "paints": 310, "fps": 29.8, "source": "iPhone", "state": "live",
                              "errors": 0, "last_error": None, "rss_mb": {"4242": 410.5, "4243": 120.0}}))
    out = tmp_path / "soak.csv"
    assert run_sampler(hb, out, every_s=0.01, pid_file=tmp_path / "s.pid", max_samples=2) == 0
    rows = load_samples(out)
    assert len(rows) == 2 and rows[0]["rss_mb"] == 530.5 and rows[0]["status"] == "running"
    assert not (tmp_path / "s.pid").exists()
    hb.unlink()
    run_sampler(hb, out, every_s=0.01, pid_file=tmp_path / "s.pid", max_samples=1)
    assert load_samples(out)[-1]["status"] == "missing"


# The whole sitting, simulated --------------------------------------------------------------------

@pytest.mark.slow
@pytest.mark.qt
def test_sitting2_dry_run_end_to_end(tmp_path):
    local = ROOT / "configs" / "booth_local.yaml"
    before = local.read_bytes() if local.exists() else None
    out = tmp_path / "s2"
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    res = subprocess.run([sys.executable, "-m", "wfglink.sitting.sitting2", "--dry-run", "--yes", "--out", str(out)],
                         capture_output=True, text=True, timeout=1200, env=env, cwd=str(ROOT))
    assert res.returncode == 0, res.stdout[-3000:] + res.stderr[-3000:]
    rep = json.loads((out / "report_sitting2.json").read_text())
    steps = rep["steps"]
    assert all(v["status"] == "done" for v in steps.values()), {k: v.get("error") for k, v in steps.items()}
    s = rep["summary"]
    assert s["hold_factor"] in (2, 3)
    for h in ("2", "3"):
        run = steps["check_b_yield"]["runs"][h]
        assert run["frames_in"] > 30 and run["frames_no_code"] <= 5
        assert 0.3 < run["clean_frame_yield"] <= 1.0
    assert s["unplug"]["pass"] and s["unplug"]["recover_s"] <= 15
    assert steps["unplug_test"]["fallback_key"] == "replay"
    assert s["worker_mode"] in ("thread", "process")
    assert all(v and v > 1 for v in s["paint_fps"].values())
    soak = steps["finish"]["analysis"]
    assert soak["samples_live"] >= 4 and soak["paint_fps_median"] > 1
    assert soak["restarts"] == 0 and soak["errors"] == 0
    assert steps["finish"]["supervisor_stopped"] and steps["finish"]["sampler_stopped"]
    written = steps["write_local_config"]
    assert Path(written["path"]).parent == out             # a dry run never touches configs/booth_local.yaml
    assert written["merged"]["booth"]["hold_factor"] == s["hold_factor"]
    assert (local.read_bytes() if local.exists() else None) == before
    assert "Paste this summary to Claude:" in res.stdout
    line = res.stdout.split("Paste this summary to Claude:\n", 1)[1].splitlines()[0]
    assert json.loads(line)["dry_run"] is True
