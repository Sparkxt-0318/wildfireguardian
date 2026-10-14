"""Sitting 2: hold-factor rules, coverage windows, unplug timing, soak analysis, sampler,
the stop logic of --finish, and the dry run."""
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from wfglink.sitting import sitting2 as s2mod
from wfglink.sitting.sitting2 import (Sitting2, choose_hold, choose_hold_coverage, choose_hold_yield, coverage_ok,
                                      coverage_summary, merge_local_config, run_stats, unplug_timing,
                                      window_coverage)
from wfglink.sitting.soak import (analyse_soak, append_row, count_log_events, load_samples, mem_slope,
                                  paint_fps_series, run_sampler, sample_row)

ROOT = Path(__file__).resolve().parents[1]
T0 = 1_760_000_000.0     # a fixed epoch for synthetic soaks


def test_choose_hold_yield():
    assert choose_hold_yield(0.85, None, 0.8)["hold_factor"] == 2
    c = choose_hold_yield(0.72, 0.86, 0.8)
    assert c["hold_factor"] == 3 and c["meets_min"]
    c = choose_hold_yield(0.70, 0.76, 0.8)            # both below: the better one, flagged
    assert c["hold_factor"] == 3 and not c["meets_min"]
    assert choose_hold_yield(0.70, 0.65, 0.8)["hold_factor"] == 2
    assert choose_hold_yield(None, 0.9, 0.8)["hold_factor"] == 3
    assert choose_hold_yield(None, None, 0.8)["hold_factor"] == 2
    assert choose_hold("yield", 0.85, None, None, None, 0.8, 0.98)["rule"] == "yield"
    with pytest.raises(ValueError):
        choose_hold("fastest", 0.85, None, None, None, 0.8, 0.98)


def _recs(pattern: str, start: int = 0, n_src: int = 30) -> list[dict]:
    """Camera frames for consecutive source frames: per source frame, `pattern` gives each of
    its camera frames as c (clean), b (blended), t (torn) or x (no code)."""
    out, i = [], start
    for _ in range(n_src):
        for ch in pattern:
            out.append({"t": len(out) / 30.0, "index": None if ch == "x" else (i if ch == "c" else i + 1),
                        "clean": ch == "c", "blended": ch == "b", "torn": ch == "t"})
        i += 1
    return out


def _lossy() -> list[dict]:
    """Two camera frames per source frame, both unclean for every other source frame."""
    recs = _recs("cc")
    for k, r in enumerate(recs):
        if (k // 2) % 2:
            r.update(clean=False, blended=True, index=None)
    return recs


def test_window_coverage_counts_source_frames_not_camera_frames():
    both = window_coverage(_recs("cc"))                   # a lucky phase: two clean views each
    assert both["yield"] == 1.0 and both["coverage"] == 1.0 and both["spare"] == 1.0
    one = window_coverage(_recs("cb"))                    # the usual hold-2 phase: one view each
    assert one["yield"] == 0.5 and one["coverage"] == 1.0 and one["spare"] == 0.0
    assert one["unclean_per_shown"] == pytest.approx(1.0, abs=0.05)
    lossy = window_coverage(_lossy())
    assert lossy["coverage"] == pytest.approx(15 / 29, abs=1e-3) and lossy["max_gap"] == 1
    # The worst phase: codes are read, but no frame is ever clean. That is coverage 0 (with
    # the shown frames from the decoded indices), not a window without data.
    never = window_coverage(_recs("bt"))
    assert never["coverage"] == 0.0 and never["shown"] >= 29 and never["yield"] == 0.0
    assert window_coverage(_recs("xx"))["coverage"] is None          # no codes at all: no data
    # The clip loops: indices go back to 0; each pass counts from its first to its last index.
    loop = window_coverage(_recs("cc", start=50, n_src=10) + _recs("cc", start=0, n_src=10))
    assert loop["passes"] == 2 and loop["shown"] == 20 and loop["coverage"] == 1.0
    # Dropped camera frames are found from the frame times.
    gappy = _recs("cc", n_src=10)
    for r in gappy[10:]:
        r["t"] += 2 / 30.0
    assert window_coverage(gappy, fps=30.0)["dropped"] == 2
    assert window_coverage([])["coverage"] is None


def test_coverage_rule_needs_every_window_and_a_spare_view():
    one = [window_coverage(_recs("cb")) for _ in range(4)]
    spare = [window_coverage(_recs("cc"))] + one[:3]
    c_one = coverage_summary(one)
    assert c_one["coverage"] == 1.0 and c_one["spare_windows"] == 0
    assert not coverage_ok(c_one, 0.98)               # covered at this phase, but unproven at others
    c_spare = coverage_summary(spare)
    assert coverage_ok(c_spare, 0.98) and c_spare["spare_windows"] == 1
    assert c_spare["yield_min"] == 0.5 and c_spare["yield_max"] == 1.0 and c_spare["margin"] > 0
    c_bad = coverage_summary(spare + [window_coverage(_lossy())])
    assert c_bad["coverage_worst"] < 0.6 and not coverage_ok(c_bad, 0.98)   # one bad phase is enough
    c_dark = coverage_summary(spare + [window_coverage(_recs("bt"))])
    assert c_dark["windows_used"] == 5 and c_dark["coverage_worst"] == 0.0 and not coverage_ok(c_dark, 0.98)
    errored = coverage_summary([{"error": "OSError: busy"}, {"shown": 3, "seen": 3}])
    assert errored["windows_used"] == 0 and not coverage_ok(errored, 0.98)
    # Hold 3 shows each source frame to three camera frames.
    h3 = coverage_summary([window_coverage(_recs("ccb")) for _ in range(4)])
    assert choose_hold_coverage(c_spare, None, 0.98)["hold_factor"] == 2
    c = choose_hold_coverage(c_one, h3, 0.98)
    assert c["hold_factor"] == 3 and c["meets_min"]
    c = choose_hold_coverage(c_one, None, 0.98)
    assert c["hold_factor"] == 2 and not c["meets_min"]
    worse3 = coverage_summary([window_coverage(_lossy())] * 4)
    assert choose_hold_coverage(c_one, worse3, 0.98)["hold_factor"] == 2       # hold 3 did worse
    assert choose_hold_coverage(c_bad, c_bad, 0.98)["hold_factor"] == 3        # a tie: more views wins
    assert choose_hold("coverage", 0.5, 0.67, c_one, h3, 0.8, 0.98)["rule"] == "coverage"


def test_coverage_rule_counts_sparse_windows_and_needs_enough_windows():
    # Codes read in every frame of 60 source frames, but only the first three read clean: the
    # window lost most of them. It must fail, not be left out as a short window.
    sparse = [{"t": k / 30.0, "index": k // 2, "clean": k < 6, "blended": k >= 6, "torn": False} for k in range(120)]
    w = window_coverage(sparse)
    assert w["shown"] >= 59 and w["coverage"] < 0.1
    good = window_coverage(_recs("cc"))
    c = coverage_summary([good, w])
    assert c["windows_used"] == 2 and c["coverage_worst"] < 0.1 and not coverage_ok(c, 0.98)
    # A normal window keeps its clean range: an unclean frame at each end decodes to a neighbour.
    edged = [{"t": 0.0, "index": 0, "clean": False, "blended": True, "torn": False}] + _recs("cb", start=1)
    assert window_coverage(edged)["shown"] == 30 and window_coverage(edged)["coverage"] == 1.0
    # One measured window out of eight (seven could not open) is not enough to keep hold 2.
    errs = [{"error": "SourceError: device busy", "frames": 0, "shown": 0} for _ in range(7)]
    one = coverage_summary([good] + errs)
    assert one["windows_used"] == 1 and not one["enough_windows"] and not coverage_ok(one, 0.98)
    half = coverage_summary([good] * 4 + errs[:4])
    assert half["enough_windows"] and coverage_ok(half, 0.98)
    assert choose_hold_coverage(one, None, 0.98)["hold_factor"] == 2 and "without a measurement" in \
        choose_hold_coverage(one, None, 0.98)["reason"]


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
    # Back in time, but it dropped out again a few seconds later: not a pass.
    flap = unplug_timing(ev + [{"t": 146.0, "event": "failed", "key": "iphone", "reason": "no frames"}],
                         "iphone", 115.0, 135.0, 15.0)
    assert flap["recover_s"] == 7.5 and not flap["stable_after_recover"] and not flap["pass"]
    assert "failed again" in flap["note"]


def test_measure_windows_samples_new_phases(tmp_path):
    # Each window reopens the simulated camera, which then samples a new phase; at hold 2 with
    # a global shutter every window covers every source frame.
    import av

    from wfglink.io.synthetic_live import SyntheticLiveSource
    from wfglink.screen.booth_prep import prepare
    from wfglink.screen.codes import Layout
    from wfglink.screen.loopsim import LoopSimSource
    from wfglink.screen.rectify import ScreenRectifier

    syn = SyntheticLiveSource(width=640, height=360, realtime=False, seed=5)
    syn.open()
    with av.open(str(tmp_path / "clip.mp4"), "w") as c:
        s = c.add_stream("libx264", rate=30)
        s.width, s.height, s.pix_fmt = 640, 360, "yuv420p"
        for _ in range(20):
            for p in s.encode(av.VideoFrame.from_ndarray(syn.read().image, format="bgr24")):
                c.mux(p)
        for p in s.encode():
            c.mux(p)
    meta = prepare(tmp_path / "clip.mp4", tmp_path / "booth", holds=(2,))
    lay = Layout(**{k: meta["layout"][k] for k in ("width", "height", "marker", "cell", "margin")})
    src = LoopSimSource(tmp_path / "booth" / "clip_hold2.mp4", size=(960, 540), exp_s=0.008, seed=1)
    wins = s2mod.measure_windows(lambda: src, ScreenRectifier(lay, 640), 4, 0.8, fps=30.0, pause_s=0.0,
                                 clock=lambda: 0.0)
    assert src.opens == 4 and len(wins) == 4
    assert all(w["frames"] == 24 and w["coverage"] == 1.0 and w["dropped"] == 0 for w in wins), wins
    summ = coverage_summary(wins)
    assert summ["windows_used"] == 4 and summ["coverage_worst"] == 1.0
    # A camera that cannot open is recorded as such and does not count.
    def broken():
        raise OSError("device busy")
    bad = s2mod.measure_windows(broken, ScreenRectifier(lay, 640), 2, 0.5, pause_s=0.0, clock=lambda: 0.0)
    assert all("device busy" in w["error"] for w in bad) and coverage_summary(bad)["windows_used"] == 0


# The stop logic of --finish ------------------------------------------------------------------------

def test_parse_etime():
    assert s2mod._parse_etime("05") == 5
    assert s2mod._parse_etime("01:02") == 62
    assert s2mod._parse_etime("03:00:01") == 10801
    assert s2mod._parse_etime("2-00:00:10") == 2 * 86400 + 10
    assert s2mod._parse_etime("x") is None


def test_is_ours_checks_arguments_and_start_time():
    p = {"pid": 7, "pgid": 7, "start_epoch": 1000.0, "command": "bash /w/booth/booth.sh --replay-clip /c/x.mp4"}
    toks = ["/w/booth/booth.sh", "--replay-clip /c/x.mp4"]
    assert s2mod._is_ours(p, toks, 999.0, 1059.0)
    assert not s2mod._is_ours(p, toks, 1100.0)                      # started before the soak: a reused pid
    assert not s2mod._is_ours(p, toks, 900.0, 920.0)                # started long after the soak began
    assert not s2mod._is_ours(p, ["/w/booth/booth.sh", "--replay-clip /c/y.mp4"], 999.0)
    assert not s2mod._is_ours(None, toks, 0.0)
    ss = {"start_epoch": 999.0, "replay_clip_abs": "/c/x.mp4"}
    app = {"pid": 9, "pgid": 7, "start_epoch": 2000.0,
           "command": "/w/.venv/bin/python -m wfglink booth --heartbeat /w/logs/heartbeat.json --replay-clip /c/x.mp4"}
    assert Sitting2._is_soak_app(app, ss, 7)
    assert not Sitting2._is_soak_app({**app, "pgid": 9}, ss, 7)     # same arguments, another group
    assert Sitting2._is_soak_app({**app, "pgid": 9, "command": "/w/dist/WFGLink.app/Contents/MacOS/WFGLink booth "
                                  "--heartbeat /w/logs/heartbeat.json --replay-clip /c/x.mp4"}, ss, 7)
    rehearsal = {**app, "command": "/w/.venv/bin/python -m wfglink booth --heartbeat /w/logs/heartbeat.json"}
    assert not Sitting2._is_soak_app(rehearsal, ss, 7)
    old = {"start_epoch": 999.0, "args": ["bash", "/w/booth/booth.sh", "--replay-clip", "/c/x.mp4"]}
    assert s2mod._soak_tokens(old)["app"] == ["--heartbeat", "--replay-clip /c/x.mp4"]


def test_other_booths_are_booths_not_the_sampler(monkeypatch):
    # A sampler left by an earlier soak names the heartbeat too; it must not block a new soak
    # as "a booth is already running" (Esc cannot quit it).
    hb = str(s2mod.HEARTBEAT)
    rows = [{"pid": 11, "command": f"/v/bin/python -m wfglink.sitting.soak sample --heartbeat {hb} --out /o/soak.csv"},
            {"pid": 12, "command": f"/v/bin/python -m wfglink booth --heartbeat {hb}"},
            {"pid": 13, "command": f"bash {s2mod.BOOTH_SH}"},
            {"pid": 14, "command": "/v/bin/python -m wfglink booth --heartbeat /elsewhere/logs/heartbeat.json"}]
    monkeypatch.setattr(s2mod, "_ps", lambda pid=None: rows)
    assert [p["pid"] for p in Sitting2._other_booths()] == [12, 13]


def _spawn(script: Path, *args: str) -> subprocess.Popen:
    script.write_text("#!/usr/bin/env bash\nsleep 30\n")
    return subprocess.Popen(["bash", str(script), *args], start_new_session=True,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def test_stop_booth_never_signals_a_process_that_is_not_the_soak(tmp_path, monkeypatch):
    fake_sh = tmp_path / "booth" / "booth.sh"
    fake_sh.parent.mkdir()
    monkeypatch.setattr(s2mod, "BOOTH_SH", fake_sh)
    clip = str(tmp_path / "clip_hold2.mp4")
    s = Sitting2.__new__(Sitting2)                       # only the stop logic is used
    procs = []
    try:
        # A booth.sh with the soak's arguments, but the soak "started" a minute after it: pid reuse.
        other = _spawn(fake_sh, "--replay-clip", clip)
        procs.append(other)
        time.sleep(0.3)
        ss = {"supervisor_pid": other.pid, "start_epoch": time.time() + 60, "replay_clip_abs": clip}
        sup_ok, app_ok, left = s._stop_booth(ss)
        assert other.poll() is None and left and left[0]["pid"] == other.pid
        # A booth.sh for another clip (a booth started by hand) is left alone too.
        ss = {"supervisor_pid": other.pid, "start_epoch": time.time() - 1, "replay_clip_abs": "/x/other.mp4"}
        s._stop_booth(ss)
        assert other.poll() is None
        # The soak's own supervisor is stopped, with its process group.
        ss = {"supervisor_pid": other.pid, "start_epoch": time.time() - 1, "replay_clip_abs": clip}
        sup_ok, app_ok, left = s._stop_booth(ss)
        assert sup_ok and not left and not s2mod._alive(other.pid)
    finally:
        for p in procs:
            if p.poll() is None:
                p.kill()
                p.wait()


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


def test_soak_edge_cases(tmp_path):
    # A worker whose memory could not be read: no sum (it would look like a 120 MB release).
    hb = {"status": "running", "epoch": T0, "pid": 1, "rss_mb": {"1": 400.0, "2": None}}
    assert sample_row(hb, now=T0 + 1)["rss_mb"] == ""
    # A file begun by an older sampler keeps its columns.
    old = tmp_path / "old.csv"
    old.write_text("sample_epoch,status,pid\n1.0,running,5\n")
    append_row(old, {"sample_epoch": 2.0, "status": "running", "pid": 6, "hb_status": "running"})
    assert old.read_text().splitlines()[-1] == "2.0,running,6"
    rows = []
    # One app for 3 h, sampled twice per heartbeat at first (duplicates); its process worker is
    # replaced after 2 h (memory starts again from 100 MB); 5 MB/h throughout.
    for k in range(0, 37):
        up = k * 300.0
        worker = "11" if up < 7200 else "12"
        wmem = 100 + 5 * (up if up < 7200 else up - 7200) / 3600
        r = _row(T0 + up, 10, up, 300 + 5 * up / 3600 + wmem, paints=30 * up)
        r["rss_detail"] = json.dumps({"10": 1.0, worker: 1.0})
        rows.append(r)
        if k < 3:
            rows.append({**r, "sample_epoch": r["sample_epoch"] + 0.2})
    # Esc pressed twice at 3 h; then a booth started for the rehearsal (another pid) wrote the
    # heartbeat for another hour before --finish, and the Mac slept for 40 minutes before that.
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
    # The same file can hold an earlier soak (started again with --from soak_start), and the
    # sampler's first sample can still read the heartbeat an earlier booth left behind after
    # Esc (before booth.sh removes it): neither belongs to this soak, nor ends it.
    early = tmp_path / "early.csv"
    for k in range(6):
        append_row(early, _row(T0 - 3600 + k * 300, 7, k * 300.0, 500, paints=30 * k * 300))
    append_row(early, sample_row({"status": "clean_exit", "epoch": T0 - 1800, "pid": 7, "rss_mb": {"7": 500.0}},
                                 now=T0 + 0.3))
    for r in rows[:40]:              # the soak app only (37 heartbeats, 3 read twice)
        append_row(early, r)
    rep3 = analyse_soak(early, tmp_path / "none.log", T0, T0 + 3 * 3600, last_h=6, warmup_s=0)
    assert rep3["ended_by"] == "finish" and rep3["hours"] == pytest.approx(3.0, abs=0.01)
    assert rep3["samples_live"] == 37 and rep3["paint_fps_intervals"] == 36
    assert rep3["instances"] == 1 and rep3["samples"] == 41


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
    assert s["hold_factor"] in (2, 3) and s["hold_rule"] == "coverage"
    for h in ("2", "3"):
        run = steps["check_b_yield"]["runs"][h]
        assert run["frames_in"] > 30 and run["frames_no_code"] <= 5
        assert 0.3 < run["clean_frame_yield"] <= 1.0
        cov = steps["check_b_yield"]["coverage"][h]
        assert cov["windows_used"] == 4 and cov["coverage_worst"] >= 0.8, cov
        assert s[f"coverage_hold{h}"][0] == cov["coverage"]
    assert s["unplug"]["pass"] and s["unplug"]["recover_s"] <= 20
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
