"""Real-clip plausibility checks (plan 4.5): each check passing and flagging on constructed inputs."""
import json
import math
import re

import numpy as np
import pandas as pd
import pytest
from dots_clip import dots_clip, write_clip_settings

from wfglink.cli import main
from wfglink.config import load_config
from wfglink.validate import plausibility as P

CFG = load_config()


def _frames(t, duplicate=None):
    t = np.asarray(t, float)
    return pd.DataFrame({"frame": np.arange(t.size), "t": t,
                         "duplicate": np.zeros(t.size, bool) if duplicate is None else duplicate,
                         "ready": np.ones(t.size, bool)})


def _tracks(speed, direction=None, static=None, crossings=None):
    speed = np.asarray(speed, float)
    n = speed.size
    d = np.zeros(n) if direction is None else np.asarray(direction, float)
    return pd.DataFrame({"track_id": np.arange(1, n + 1), "static": np.zeros(n, bool) if static is None else static,
                         "track_speed_px_s": speed, "best_speed_px_s": speed, "direction_deg": d,
                         "u_px_s": speed * np.cos(np.radians(d)), "v_px_s": speed * np.sin(np.radians(d)),
                         "crossings_pos": np.zeros(n, int) if crossings is None else crossings,
                         "crossings_neg": np.zeros(n, int)})


# 1. Timing ---------------------------------------------------------------------------------

def test_timing_passes_and_flags():
    t = np.arange(300) / 30.0
    ok = P.check_timing(_frames(t), CFG)
    assert ok.status == "pass" and ok.values["interval_median_s"] == pytest.approx(1 / 30)
    assert ok.values["gaps"] == 0 and not ok.values["variable_frame_rate"]
    gap = P.check_timing(_frames(np.delete(t, [100, 101, 102])), CFG)
    assert gap.status == "flag" and gap.values["gaps"] == 1 and "gaps" in gap.reason
    rng = np.random.default_rng(0)
    vfr = P.check_timing(_frames(np.cumsum(rng.uniform(0.8, 1.2, 300) / 30.0)), CFG)
    assert vfr.status == "flag" and vfr.values["variable_frame_rate"]
    dup = np.zeros(300, bool)
    dup[50:60] = True
    rep = P.check_timing(_frames(t, dup), CFG)
    assert rep.status == "flag" and rep.values["repeated_frames"] == 10 and "repeated" in rep.reason
    back = t.copy()
    back[200] = back[199]
    assert P.check_timing(_frames(back), CFG).values["timestamps_not_increasing"] == 1


def test_timing_against_container_times():
    """Frame times of a run starting at 2 s are matched to the packet times in that segment."""
    pk = np.arange(0, 600) / 30.0
    seg = (2.0, 9.0)
    rel = pk[(pk >= 2.0) & (pk <= 9.0)] - 2.0
    ok = P.check_timing(_frames(rel), CFG, pk, seg)
    assert ok.status == "pass" and ok.values["container_frames_missing"] == 0
    lost = P.check_timing(_frames(np.delete(rel, 40)), CFG, pk, seg)
    assert lost.status == "flag" and lost.values["container_frames_missing"] == 1


# 2. Exposure -------------------------------------------------------------------------------

def _exposure_points(t_exp_by_window, seed=0, offset_px=None):
    """Track points whose streak length is T x speed, 30 tracks per 3 s window at 30 fps.

    offset_px: per window, a length offset (L = offset + T x speed), so that streak length is
    not proportional to speed there (None: proportional everywhere)."""
    rng = np.random.default_rng(seed)
    rows, tid = [], 0
    offset_px = offset_px or [0.0] * len(t_exp_by_window)
    for w, (T, off) in enumerate(zip(t_exp_by_window, offset_px)):
        for k in range(30):
            tid += 1
            sp = rng.uniform(250, 700)
            t0 = 3.0 * w + rng.uniform(0, 2.4)
            for i in range(12):
                rows.append({"track_id": tid, "t": t0 + i / 30, "speed_poly": sp,
                             "length": off + T * sp + rng.normal(0, 0.3), "flags": 0, "interior": 2 <= i <= 9,
                             "static": False})
    return pd.DataFrame(rows)


ACCEPTED = {"exposure": {"source": "estimated", "t_exp_s": 0.02, "ci_s": [0.019, 0.021]}, "input": {"fps": 30.0}}


def test_exposure_declined_is_not_applicable():
    s = {"exposure": {"source": "estimated", "status": "not estimated: too few tracks"}, "input": {"fps": 30.0}}
    c = P.check_exposure(s, None, None, CFG)
    assert c.status == "not applicable" and "too few tracks" in c.reason


def test_exposure_stable_passes_unstable_or_too_long_flags():
    s = ACCEPTED
    fr = _frames(np.arange(180) / 30.0)
    ok = P.check_exposure(s, _exposure_points([0.02, 0.02]), fr, CFG)
    assert ok.status == "pass", ok.reason
    assert ok.values["windows_accepted"] == 2 and ok.values["stability"].startswith("stable")
    assert ok.values["stability_tested"] and ok.values["frame_interval_basis"] == "decoded frames"
    bad = P.check_exposure(s, _exposure_points([0.02, 0.026]), fr, CFG)
    assert bad.status == "flag" and "do not overlap" in bad.reason
    long = {"exposure": {"source": "given", "t_exp_s": 0.04}, "input": {"fps": 30.0}}
    c = P.check_exposure(long, None, fr, CFG)
    assert c.status == "flag" and "longer than one frame interval" in c.reason
    given = P.check_exposure({**long, "exposure": {"source": "given", "t_exp_s": 0.02}}, None, fr, CFG)
    assert given.status == "pass" and "stability not applicable" in given.reason
    assert given.values["stability_tested"] is False


def test_exposure_untested_stability_never_passes():
    """Too few tracks in a window, a run too short for two windows, or no track points: stability
    is not tested, and the check flags with a reason that says so first."""
    s, fr = ACCEPTED, _frames(np.arange(180) / 30.0)
    few = _exposure_points([0.02, 0.02])
    few = few[few["track_id"] > 15]
    c = P.check_exposure(s, few, fr, CFG)
    assert c.status == "flag" and c.reason.startswith("stability not tested")
    assert c.values["windows_too_few_tracks"] == 1 and c.values["windows_accepted"] == 1
    assert c.values["stability_tested"] is False and "1 with too few tracks" in c.reason
    one = P.check_exposure(s, _exposure_points([0.02]), fr, CFG)            # 3 s of tracks: one window
    assert one.status == "flag" and one.reason.startswith("stability not tested: 1 of 1 windows")
    none = P.check_exposure(s, None, fr, CFG)
    assert none.status == "flag" and none.reason == "stability not tested: no track points"


def test_exposure_declined_windows_flag():
    """Windows with enough tracks that the estimator declines (streak length not proportional to
    speed) speak against a stable estimate: the check flags even though the run's estimate was accepted."""
    s, fr = ACCEPTED, _frames(np.arange(270) / 30.0)
    both = P.check_exposure(s, _exposure_points([0.012, 0.012], offset_px=[8.0, 8.0]), fr, CFG)
    assert both.status == "flag" and both.reason.startswith("stability not tested: 0 of 2 windows")
    assert both.values["windows_declined"] == 2 and both.values["windows_too_few_tracks"] == 0
    assert "not proportional" in both.reason
    third = P.check_exposure(s, _exposure_points([0.02, 0.02, 0.012], offset_px=[0.0, 0.0, 8.0]), fr, CFG)
    assert third.values["windows_accepted"] == 2 and third.values["windows_declined"] == 1
    assert third.values["stability"] == "stable over 2 of 3 windows"
    assert third.status == "flag" and "1 of 3 windows declined against a stable estimate" in third.reason


def test_exposure_limit_uses_the_cameras_interval_with_repeats():
    """A re-encode that repeats every other frame: the camera's frame interval is two decoded
    intervals, so 50 ms fits at 30 decoded fps."""
    t = np.arange(180) / 30.0
    dup = np.arange(180) % 2 == 1
    s = {"exposure": {"source": "given", "t_exp_s": 0.05}, "input": {"fps": 30.0}}
    c = P.check_exposure(s, None, _frames(t, dup), CFG)
    assert c.status == "pass", c.reason
    assert c.values["frame_interval_s"] == pytest.approx(2 / 30)
    assert c.values["decoded_interval_s"] == pytest.approx(1 / 30)
    assert c.values["frame_interval_basis"].startswith("frames that are not repeats")
    assert P.check_exposure(s, None, _frames(t), CFG).status == "flag"


def test_window_kinds_follow_the_estimators_messages():
    assert P.window_kind(False, [None, None], "too few tracks") == "too few tracks"
    assert P.window_kind(False, [None, None], "too few tracks to check the speed cut") == "inconclusive"
    assert P.window_kind(False, [None, None], "estimate changes with the speed cut (streak length not proportional "
                                              "to speed)") == "declined"
    assert P.window_kind(True, [0.01, None], "") == "no interval"
    assert P.window_kind(True, [0.01, 0.02], "") == "accepted"


# 3. Static lights --------------------------------------------------------------------------

def test_static_lights():
    tr = _tracks([100, 1, 1], static=np.array([False, True, True]))
    assert P.check_static(tr).status == "pass" and P.check_static(tr).values["static_tracks"] == 2
    tr.loc[2, "crossings_pos"] = 1
    c = P.check_static(tr)
    assert c.status == "flag" and c.values["static_crossings"] == 1 and c.values["track_ids"] == [3]
    assert P.check_static(pd.DataFrame()).status == "not applicable"
    no_col = P.check_static(tr.drop(columns=["static"]))
    assert no_col.status == "not applicable" and "static column" in no_col.reason


# 4. Speed ----------------------------------------------------------------------------------

def test_speed_rule_at_both_distances():
    """f = 1000 px, Z 10 to 20 m, gust 10 m/s: the limit is 1.5 x 10 + 8 = 23 m/s. 2000 px/s is 20 m/s at
    Z_min and 40 m/s at Z_max: above the limit only at Z_max, so not flagged. 2400 px/s is above at both."""
    cc = {"peak_gust_ms": 10.0, "gust_source": "test station", "z_interval_m": [10, 20], "focal_px": 1000}
    c = P.check_speed(_tracks([500, 2000]), cc, CFG)
    assert c.status == "pass" and c.values["limit_ms"] == pytest.approx(23.0) and c.values["flagged"] == 0
    c = P.check_speed(_tracks([500, 2000, 2400, 2400]), cc, CFG)
    assert c.status == "flag" and c.values["flagged"] == 2 and c.values["flagged_fraction"] == 0.5
    assert c.values["flagged_track_ids"] == [3, 4]
    p99 = np.percentile([500, 2000, 2400, 2400], 99)
    assert c.values["speed_percentile_ms"] == pytest.approx([p99 * 0.01, p99 * 0.02])
    # Focal length from the horizontal field of view of the full frame: 90 deg over 2000 px is 1000 px.
    cc2 = {**cc, "focal_px": None, "hfov_deg": 90.0}
    assert P.check_speed(_tracks([2400]), cc2, CFG, frame_width=2000).values["focal_px"] == pytest.approx(1000)
    assert P.check_speed(_tracks([2400]), cc2, CFG).status == "not applicable"     # width unknown
    na = P.check_speed(_tracks([2400]), {"peak_gust_ms": 10.0}, CFG)
    assert na.status == "not applicable"
    assert na.values["missing"] == ["gust_source", "z_interval_m", "focal_px or hfov_deg"]
    static = _tracks([5000, 100], static=np.array([True, False]))
    assert P.check_speed(static, cc, CFG).values["tracks"] == 1                     # static tracks left out


def test_speed_settings_out_of_range_are_not_applicable():
    cc = {"peak_gust_ms": 10.0, "gust_source": "test station", "z_interval_m": [10, 20], "focal_px": 1000}
    tr = _tracks([500, 2400])
    for bad in ({"focal_px": 0}, {"focal_px": -1000}, {"focal_px": None, "hfov_deg": 0},
                {"focal_px": None, "hfov_deg": 180}, {"peak_gust_ms": -1.0}, {"z_interval_m": [20, 10]},
                {"z_interval_m": [10, 20, 30]}, {"z_interval_m": 15}):
        c = P.check_speed(tr, {**cc, **bad}, CFG, frame_width=2000)
        assert c.status == "not applicable", (bad, c.reason)


# 5. Direction ------------------------------------------------------------------------------

def test_direction_convention_and_tolerance():
    """direction_deg is atan2(v, u) in image axes: 0 = right, +90 = down."""
    tr = _tracks([100, 100, 300], direction=[80, 100, 90])
    cc = {"drift_deg": 90.0, "drift_basis": "smoke drift"}
    c = P.check_direction(tr, cc, CFG)
    assert c.status == "pass" and c.values["mean_direction_deg"] == pytest.approx(90.0)
    assert c.values["difference_deg"] == pytest.approx(0.0, abs=1e-9)
    up = P.check_direction(tr, {**cc, "drift_deg": -90.0}, CFG)
    assert up.status == "flag" and abs(up.values["difference_deg"]) == pytest.approx(180.0)
    # Speed weighting: one fast track at 0 deg and two slow ones at 90 deg.
    w = P.check_direction(_tracks([300, 50, 50], direction=[0, 90, 90]), {**cc, "drift_deg": 0.0}, CFG)
    assert w.values["mean_direction_deg"] == pytest.approx(math.degrees(math.atan2(100, 300)))
    # Across +-180: 170 and -170 average to 180, 20 deg from a drift of -160.
    c = P.check_direction(_tracks([1, 1], direction=[170, -170]), {**cc, "drift_deg": -160.0,
                                                                   "drift_tolerance_deg": 25}, CFG)
    assert c.status == "pass" and abs(c.values["mean_direction_deg"]) == pytest.approx(180.0)
    assert c.values["difference_deg"] == pytest.approx(-20.0) and c.values["tolerance_source"] == "drift_tolerance_deg"
    assert P.check_direction(_tracks([1, 1], direction=[170, -170]), {**cc, "drift_deg": -160.0}, CFG).values[
        "tolerance_deg"] == CFG["plausibility"]["direction"]["tolerance_deg"]
    spread = P.check_direction(_tracks([1, 1, 1, 1], direction=[0, 90, 180, -90]), cc, CFG)
    assert spread.status == "flag" and "no dominant direction" in spread.reason
    assert P.check_direction(tr, {"drift_deg": 90.0}, CFG).values["missing"] == ["drift_basis"]


# 6. Determinism ----------------------------------------------------------------------------

def test_compare_tables_reports_first_difference():
    a = {"frames": pd.DataFrame({"frame": [0, 1], "t": [0.0, 0.033], "ms": [1.0, 2.0]}),
         "tracks": pd.DataFrame({"track_id": [1], "u_px_s": [np.nan]})}
    b = {"frames": pd.DataFrame({"frame": [0, 1], "t": [0.0, 0.033], "ms": [9.0, 9.0]}),
         "tracks": pd.DataFrame({"track_id": [1], "u_px_s": [np.nan]})}
    assert P.compare_tables(a, b, {"frames": ["ms"]}) is None           # timing ignored, NaN equals NaN
    assert P.compare_tables(a, b)["column"] == "ms"
    b["tracks"].loc[0, "u_px_s"] = 1.0
    d = P.compare_tables(a, b, {"frames": ["ms"]})
    assert d["table"] == "tracks" and d["column"] == "u_px_s" and d["row"] == 0


# All checks on a real run ------------------------------------------------------------------

@pytest.fixture(scope="module")
def dots_run(tmp_path_factory):
    d = tmp_path_factory.mktemp("plaus")
    clip = d / "dots.mp4"
    dots_clip(clip, frames=60)                # dots move 4 px right and 3 px down per frame
    cs = write_clip_settings(d / "dots.yaml", clip, roi=[20, 10, 300, 230], segments_s=[[0.3, 2.0]])
    assert main(["process", str(cs), "--out", str(d / "run"), "--no-overlay"]) == 0
    return d, cs


def test_run_plausibility_on_a_run(dots_run, tmp_path):
    d, cs = dots_run
    out = P.run_plausibility(d / "run", cs, CFG, determinism_seconds=1.0, work_dir=tmp_path)
    saved = json.loads((d / "run" / "plausibility.json").read_text())
    assert set(saved["checks"]) == {"timing", "exposure", "static_lights", "speed", "direction", "determinism"}
    for c in saved["checks"].values():
        assert c["status"] in ("pass", "flag", "not applicable") and c["reason"] and "\n" not in c["reason"]
    ch = out["checks"]
    assert out["clip_file_is_run_input"] and out["clip_settings_match_run"] and len(out["clip_settings_sha256"]) == 64
    assert ch["timing"]["status"] == "pass" and ch["timing"]["values"]["container_frames_missing"] == 0
    assert ch["determinism"]["status"] == "pass", ch["determinism"]["reason"]
    assert ch["determinism"]["values"]["rows"]["detections"] > 0 and "field" in ch["determinism"]["values"]["tables"]
    assert ch["speed"]["status"] == "not applicable" and ch["direction"]["status"] == "not applicable"
    assert not list(tmp_path.iterdir())                                    # rerun folders removed
    # summary.json carries the statuses (plan section 6); the tables are untouched.
    summ = json.loads((d / "run" / "summary.json").read_text())
    assert summ["plausibility"]["file"] == "plausibility.json"
    assert summ["plausibility"]["status"] == {k: c["status"] for k, c in saved["checks"].items()}
    # The angle convention end to end: motion right and down is atan2(3, 4) = 36.9 deg.
    cc = {"file": str((d / "dots.mp4").resolve()), "drift_deg": 37.0, "drift_basis": "test motion"}
    r = P.run_plausibility(d / "run", cc, CFG, determinism_seconds=0, write=False)
    assert r["checks"]["direction"]["status"] == "pass"
    assert r["checks"]["direction"]["values"]["mean_direction_deg"] == pytest.approx(36.87, abs=1.0)
    # With the rerun switched off, the earlier determinism result of the same run and config is kept.
    det = r["checks"]["determinism"]
    assert det["status"] == "pass" and det["reason"].startswith("kept from")
    assert det["values"]["kept_from"]["created"] == saved["created"]
    other_cfg = load_config(overrides={"plausibility": {"speed": {"margin_ms": 9.0}}})
    r2 = P.run_plausibility(d / "run", cc, other_cfg, determinism_seconds=0, write=False)
    assert r2["checks"]["determinism"]["status"] == "not applicable"
    r = P.run_plausibility(d / "run", {**cc, "drift_deg": -37.0}, CFG, determinism_seconds=0, write=False)
    assert r["checks"]["direction"]["status"] == "flag"


def test_speed_from_hfov_uses_the_full_frame_on_a_roi_run(dots_run):
    """The run's ROI is 280 px wide inside a 320 px frame; the focal length from a 90 deg field of
    view is that of the full frame (summary input.source_size): 160 px."""
    d, cs = dots_run
    cc = {"file": str((d / "dots.mp4").resolve()), "peak_gust_ms": 10.0, "gust_source": "test station",
          "z_interval_m": [10.0, 20.0], "hfov_deg": 90.0}
    summ = json.loads((d / "run" / "summary.json").read_text())
    assert summ["input"]["width"] == 280 and summ["input"]["source_size"] == [320, 240]
    sp = P.run_plausibility(d / "run", cc, CFG, determinism_seconds=0, write=False)["checks"]["speed"]
    assert sp["status"] in ("pass", "flag") and sp["values"]["focal_px"] == pytest.approx(160.0)
    assert sp["values"]["focal_source"] == "hfov_deg 90 over 320 px"


def test_settings_of_another_video_are_not_applied(dots_run, tmp_path):
    """Clip settings that name another video than the run's input give no speed or direction verdict."""
    d, cs = dots_run
    other = tmp_path / "other.mp4"
    dots_clip(other, frames=6, seed=1)
    cc = {"file": str(other), "peak_gust_ms": 10.0, "gust_source": "test station", "z_interval_m": [10.0, 20.0],
          "focal_px": 1000.0, "drift_deg": 37.0, "drift_basis": "test motion"}
    r = P.run_plausibility(d / "run", cc, CFG, determinism_seconds=0, write=False)
    assert not r["clip_file_is_run_input"] and not r["clip_settings_match_run"]
    for name in ("speed", "direction", "determinism"):
        assert r["checks"][name]["status"] == "not applicable", name
    assert "another video" in r["checks"]["speed"]["reason"]
    assert r["checks"]["timing"]["values"]["container_frames_in_segment"] is None


def test_determinism_reruns_get_the_runs_exposure(dots_run, tmp_path, monkeypatch):
    """A run with an accepted T_exp passes it to both reruns (the tracking pass that wrote the run's
    tables); a run whose estimate declined lets each rerun estimate again."""
    import wfglink.outputs.process as proc

    d, cs = dots_run
    real = proc.process_clip
    seen = []

    def spy(clip, out, *a, **k):
        seen.append(k.get("t_exp"))
        return real(clip, out, *a, **k)

    monkeypatch.setattr(proc, "process_clip", spy)
    summary = json.loads((d / "run" / "summary.json").read_text())
    acc = {**summary, "exposure": {"source": "estimated", "t_exp_s": 0.01, "ci_s": [0.009, 0.011]}}
    c = P.check_determinism(d / "dots.mp4", acc, {}, CFG, seconds=0.5, work_dir=tmp_path)
    assert seen == [0.01, 0.01] and c.values["t_exp_from"] == "the run (estimated)" and c.status == "pass"
    seen.clear()
    dec = {**summary, "exposure": {"source": "estimated", "status": "not estimated: too few tracks"}}
    c = P.check_determinism(d / "dots.mp4", dec, {}, CFG, seconds=0.5, work_dir=tmp_path)
    assert seen == [None, None] and c.values["t_exp_from"].startswith("estimated again")


def test_determinism_without_detections_is_not_applicable(tmp_path):
    clip = tmp_path / "dark.mp4"
    dots_clip(clip, frames=30, amp=0.0)
    c = P.check_determinism(clip, {"input": {"segment_s": [0.0, None]}}, {}, CFG, seconds=0.6, work_dir=tmp_path)
    assert c.status == "not applicable" and "no detections" in c.reason
    assert c.values["rows"]["detections"] == 0


def test_determinism_flags_a_differing_rerun(dots_run, tmp_path, monkeypatch):
    """When the second rerun writes a different table, the check flags and names table and column."""
    import wfglink.outputs.process as proc

    d, cs = dots_run
    real = proc.process_clip
    calls = []

    def perturbed(clip, out, *a, **k):
        s = real(clip, out, *a, **k)
        calls.append(out)
        if len(calls) == 2:
            det = pd.read_parquet(out / "detections.parquet")
            det.loc[3, "peak"] += 1.0
            det.to_parquet(out / "detections.parquet", index=False)
        return s

    monkeypatch.setattr(proc, "process_clip", perturbed)
    summary = json.loads((d / "run" / "summary.json").read_text())
    frames = pd.read_parquet(d / "run" / "frames.parquet")
    c = P.check_determinism(d / "dots.mp4", summary, {}, CFG, seconds=1.0, work_dir=tmp_path, frames=frames)
    assert len(calls) == 2 and c.status == "flag"
    assert c.values["first_difference"]["table"] == "detections" and c.values["first_difference"]["column"] == "peak"
    assert c.values["first_difference"]["row"] == 3 and "detections.peak" in c.reason


def test_plausibility_command(dots_run, capsys):
    d, cs = dots_run
    assert main(["plausibility", str(d / "run"), "--clip", str(cs), "--determinism-seconds", "0"]) == 0
    text = capsys.readouterr().out
    # Determinism is switched off: not applicable, or kept from an earlier check of this run.
    assert "timing: pass" in text and re.search(r"determinism: (not applicable|pass: kept from)", text)
    assert (d / "run" / "plausibility.json").exists()
    with pytest.raises(SystemExit, match="plausibility: "):
        main(["plausibility", str(d / "run"), "--clip", str(d / "missing.yaml")])
