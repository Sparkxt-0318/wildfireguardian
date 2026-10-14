"""Sitting tools: panel scan analysis, LED quick check, file intake and the dry run."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from wfglink.sitting.console import Console, Report
from wfglink.sitting.panel import analyse_panel_clip
from wfglink.sitting.recordings import SITTING1, basic_checks, intake, led_quick_check
from wfglink.sitting.standins import led_turntable_clip, panel_slowmo_clip


@pytest.mark.slow
@pytest.mark.parametrize("axis", ["vertical", "horizontal"])
def test_panel_scan_axis_is_recovered(tmp_path, axis):
    truth = panel_slowmo_clip(tmp_path / "p.mp4", seconds=1.5, scan_axis=axis, size=(320, 180))
    r = analyse_panel_clip(tmp_path / "p.mp4")
    assert r["ok"]
    assert r["scan_axis"].startswith(axis)
    # Apparent sweep = panel scan minus camera readout along that axis (see panel.py).
    along = r["apparent_sweep_ms_per_screen_height" if axis == "vertical" else "apparent_sweep_ms_per_screen_width"]
    assert 9.0 < along < 17.0
    assert r["transition_period_ms"] == pytest.approx(1000 / truth["content_fps"] * 2, rel=0.05)


@pytest.mark.slow
def test_led_quick_check_flags_tilt_and_passes_straight(tmp_path):
    led_turntable_clip(tmp_path / "ok.mp4", rpm=45, seconds=2.5, size=(960, 540), radii_px=(40, 110, 200))
    led_turntable_clip(tmp_path / "tilt.mp4", rpm=45, seconds=2.5, size=(960, 540), radii_px=(40, 110, 200), tilt_ratio=0.95)
    ok = led_quick_check(tmp_path / "ok.mp4")
    tilt = led_quick_check(tmp_path / "tilt.mp4")
    assert ok["ok"], ok
    assert ok["axis_ratio"] > 0.995
    assert not tilt["ok"]
    assert tilt["axis_ratio"] == pytest.approx(0.95, abs=0.01)


def test_intake_renames_hashes_and_checks(tmp_path):
    led_turntable_clip(tmp_path / "IMG_0001.mov", rpm=33.3, seconds=1.0, size=(640, 360), radii_px=(30, 80, 140))
    spec = next(s for s in SITTING1 if s.rid == "iph_led_s1")
    up = tmp_path / "up"
    up.mkdir()
    entry = intake([tmp_path / "IMG_0001.mov"], spec, up)
    f = entry["files"][0]
    assert f["file"] == "S1_IPH_LED_SPEED1.mov"
    assert len(f["sha256"]) == 64 and (up / f["file"]).exists()
    problems = basic_checks(spec, entry["files"])
    assert any("too short" in p for p in problems)
    assert any("only 640x360" in p for p in problems)


def test_console_parses_dragged_paths(tmp_path):
    a = tmp_path / "my clip.mov"
    a.write_bytes(b"x")
    b = tmp_path / "b.mp4"
    b.write_bytes(b"y")
    c = Console(answers={"k": f"'{a}' {b}"})
    assert c.ask_files("k", "files", []) == [a, b]
    c2 = Console(answers={"k": "2"})
    assert c2.ask_files("k", "files", [b, a]) == [a]
    assert Console(answers={"k": "skip"}).ask_files("k", "files", [a]) is None


def test_report_resumes(tmp_path):
    r = Report(tmp_path / "r.json", "kind")
    r.put("a", {"x": 1})
    r2 = Report(tmp_path / "r.json", "kind")
    assert r2.done("a") and r2.get("a")["x"] == 1


@pytest.mark.slow
def test_sitting1_dry_run_end_to_end(tmp_path):
    out = tmp_path / "s1"
    res = subprocess.run([sys.executable, "-m", "wfglink", "sitting1", "--dry-run", "--out", str(out), "--seconds", "0.5"],
                         capture_output=True, text=True, timeout=1200)
    assert res.returncode == 0, res.stdout[-2000:] + res.stderr[-2000:]
    rep = json.loads((out / "report_sitting1.json").read_text())
    steps = rep["steps"]
    assert all(steps[k]["status"] == "done" for k in steps), {k: v.get("error") for k, v in steps.items() if v["status"] != "done"}
    rows = rep["summary"]["recordings"]
    assert rows["iph_led_s1"] == rows["iph_led_s2"] == rows["dc_led_s1"] == rows["dc_led_s2"] == "ok"
    assert rows["panel_240"] == "ok"
    assert rows["dc_night_drive"] == "deferred"
    assert rep["summary"]["panel_axis"].startswith("vertical")
    assert steps["live_view"]["paint_fps"] > 5
