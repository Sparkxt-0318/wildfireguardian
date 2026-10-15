"""LED turntable suite on dashcam files: analysis core, file names, notes, date-stamp mask, end to end."""
import json
import math
import subprocess
import sys
from pathlib import Path

import av
import cv2
import numpy as np
import pytest
import yaml

from wfglink import PROJECT_ROOT
from wfglink.config import load_config
from wfglink.validate.command import synthetic_command
from wfglink.validate.dashcam import (STAMP_POSITIONS, compare_with_notes, find_recordings, load_notes,
                                      parse_stamp, stamp_boxes, stamp_mask, timing_summary)
from wfglink.validate.drive import false_tracks_per_minute
from wfglink.validate.led import analyse_led_clip, expected_speed, metric_check, shared_center_fit
from wfglink.validate.standins import draw_stamp, led_turntable_clip, night_drive_clip

GOOD_NOTES = {"dashcam_model": "test cam", "file_type": "mp4", "resolution": "640x360", "fps": 30,
              "date_stamp": "bottom-left", "wdr_hdr": False, "camera_height_cm": 40,
              "led_radius_mm": [104, 32, 68], "turns_timed": 30, "time_33rpm_s": 54.0, "time_45rpm_s": 40.0}


def _write_notes(path: Path, notes: dict) -> Path:
    path.write_text(yaml.safe_dump(notes, sort_keys=False))
    return path


# Analysis core ---------------------------------------------------------------------------------
def test_expected_speed_on_a_circle_is_omega_r():
    phi = np.linspace(0, 2 * np.pi, 9)
    assert np.allclose(expected_speed(phi, 50.0, 50.0, -2.0), 100.0)


def test_shared_center_fit_recovers_centre_and_radii():
    rng = np.random.default_rng(0)
    tracks = []
    for r, a0 in ((30, 0.0), (80, 1.0), (80, 4.0), (130, 2.0)):
        ang = a0 + np.linspace(0, 1.2, 25)
        tracks.append({"x_meas": 200 + r * np.cos(ang) + rng.normal(0, 0.3, 25),
                       "y_meas": 150 + r * np.sin(ang) + rng.normal(0, 0.3, 25)})
    c, radii = shared_center_fit(tracks)
    assert np.allclose(c, [200, 150], atol=0.5)
    assert np.allclose(radii, [30, 80, 80, 130], atol=0.5)


@pytest.mark.slow
def test_tilted_turntable_speed_error_and_exposure(tmp_path):
    p = tmp_path / "led.mp4"
    truth = led_turntable_clip(p, rpm=45.0, seconds=5, size=(640, 360), fps=30, radii_px=(40, 90, 150),
                               tilt_ratio=0.97, duty=0.5)
    r = analyse_led_clip([p], truth["omega_rad_s"], load_config())
    assert len(r["rings"]) == 3
    assert abs(r["rings"][-1]["axis_ratio"] - 0.97) < 0.005
    assert abs(r["median_speed_error_pct"]) < 1.0
    assert r["median_speed_error_uncorrected_pct"] < -1.0       # the known gain, removed above
    assert abs(r["exposure"]["t_exp_ms"] / (1000 * truth["exposure_s"]) - 1) < 0.05
    assert r["detection_recall"] > 0.9 and r["detection_precision"] > 0.9
    assert abs(r["omega_disagreement_pct"]) < 0.5
    assert any("straight down" in w for w in r["warnings"])     # axis ratio below 0.99


@pytest.mark.slow
def test_wrong_stopwatch_time_shows_up(tmp_path):
    p = tmp_path / "led.mp4"
    truth = led_turntable_clip(p, rpm=33.333, seconds=4, size=(640, 360), fps=30, radii_px=(40, 90, 150))
    r = analyse_led_clip([p], truth["omega_rad_s"] * 1.05, load_config())
    assert abs(r["median_speed_error_pct"] + 100 * (1 - 1 / 1.05)) < 0.5
    assert "warnings" in r


def test_night_drive_without_embers_counts_no_moving_tracks(tmp_path):
    p = tmp_path / "drive.mp4"
    rng = np.random.default_rng(1)
    with av.open(str(p), "w") as c:
        s = c.add_stream("libx264", rate=30)
        s.width, s.height, s.pix_fmt = 640, 360, "yuv420p"
        for i in range(150):
            img = np.clip(10 + rng.normal(0, 2, (360, 640, 3)), 0, 255).astype(np.uint8)
            img[100:103, 500:503] = 255            # a streetlight that never moves
            for pkt in s.encode(av.VideoFrame.from_ndarray(img, format="bgr24")):
                c.mux(pkt)
        for pkt in s.encode():
            c.mux(pkt)
    r = false_tracks_per_minute([p], load_config())
    assert r["minutes"] > 0.07
    assert r["moving_tracks"] == 0 and r["gate_crossings"] == 0
    assert r["false_tracks_per_min"] == 0.0
    assert r["timing"]["fps_measured"] == pytest.approx(30.0, rel=1e-3)


def test_metric_check_pairs_rings_with_radii_and_reports_the_scale():
    cfg = load_config()
    omega = 2 * math.pi * 30 / 54.0
    rings = [{"radius_px": 1.25 * r, "speed_px_s": omega * 1.25 * r * 1.02} for r in (32, 68, 104)]
    m = metric_check(rings, [104, 32, 68], omega, cfg)
    assert m["scale_source"] == "rings" and m["scale_px_per_mm"] == pytest.approx(1.25, abs=1e-3)
    assert m["median_error_pct"] == pytest.approx(2.0, abs=0.01)
    assert [p["radius_mm"] for p in m["pairs"]] == [32, 68, 104]
    assert m["pairs"][0]["true_mm_s"] == pytest.approx(2 * math.pi * 32 * 30 / 54.0, abs=0.01)
    # Two rings found: the radii whose px per mm agree are chosen (the middle LED is missing).
    m2 = metric_check([rings[0], rings[2]], [32, 68, 104], omega, cfg)
    assert [p["radius_mm"] for p in m2["pairs"]] == [32, 104]
    # A ruler scale 10 % larger than the rings' shows as a -9 % mm/s error and in rings_vs_ruler_pct.
    m3 = metric_check(rings, [32, 68, 104], omega, cfg, ruler_px_per_mm=1.375)
    assert m3["scale_source"] == "ruler" and m3["rings_vs_ruler_pct"] == pytest.approx(-9.09, abs=0.01)
    assert m3["median_error_pct"] == pytest.approx(100 * (1.02 / 1.1 - 1), abs=0.01)
    assert "ruler" in metric_check(rings[:1], [32, 68, 104], omega, cfg)["status"]
    # Radii that do not match the picture (one LED measured wrong) are flagged.
    assert "warning" in metric_check(rings, [32, 60, 104], omega, cfg)


# File names ----------------------------------------------------------------------------------------
def _touch(folder: Path, *names: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for n in names:
        (folder / n).write_bytes(b"")


def test_find_recordings_accepts_upper_case_and_orders_parts(tmp_path):
    _touch(tmp_path, "led_33rpm_b.MP4", "led_33rpm_a.MP4", "LED_45RPM.AVI", "led_ruler.MOV", "room_test.ts",
           "night_drive_a.TS", "night_drive_b.mp4", "night_drive_c.avi", "led_notes.yaml", "C5_nist.mp4", ".DS_Store")
    recs, problems, ignored = find_recordings(tmp_path)
    assert problems == [] and ignored == []
    assert [p.name for p in recs["led_33rpm"].files] == ["led_33rpm_a.MP4", "led_33rpm_b.MP4"]
    assert recs["led_33rpm"].parts == ["a", "b"]
    assert [p.name for p in recs["led_45rpm"].files] == ["LED_45RPM.AVI"]
    assert recs["led_ruler"].parts == [""]
    assert [p.suffix for p in recs["night_drive"].files] == [".TS", ".mp4", ".avi"]
    assert set(recs) == {"led_33rpm", "led_45rpm", "led_ruler", "room_test", "night_drive"}


def test_find_recordings_reports_missing_parts_mixed_names_and_duplicates(tmp_path):
    _touch(tmp_path, "led_33rpm_a.mp4", "led_33rpm_c.mp4",              # _b missing
           "led_45rpm.mp4", "led_45rpm_a.mp4",                           # plain and parts together
           "led_ruler.mp4", "led_ruler.MOV",                             # the same name twice
           "night_drive_b.mp4",                                          # _a missing
           "room_test.mkv", "led_33rpm (1).mp4")                         # unsupported extension, unknown name
    recs, problems, ignored = find_recordings(tmp_path)
    assert recs == {}
    text = "\n".join(problems)
    assert "led_33rpm: part led_33rpm_b is missing" in text
    assert "led_45rpm: found both led_45rpm.mp4 and parts led_45rpm_a.mp4" in text
    assert "led_ruler: led_ruler.MOV and led_ruler.mp4 have the same name" in text
    assert "night_drive: part night_drive_a is missing" in text
    assert len(problems) == 4
    assert any(i.startswith("room_test.mkv: extension .mkv") for i in ignored)
    assert any(i.startswith("led_33rpm (1).mp4: not a recording name") for i in ignored)


# Notes ------------------------------------------------------------------------------------------------
def test_template_lists_every_key_and_each_empty_value_says_what_to_write(tmp_path):
    cfg = load_config()
    template = PROJECT_ROOT / "data" / "led_notes_template.yaml"
    notes, errors, _ = load_notes(template, cfg)
    assert notes == {}
    assert len(errors) == len(GOOD_NOTES)
    for key in GOOD_NOTES:
        assert any(e.startswith(f"led_notes_template.yaml: {key} is missing. Write ") for e in errors), key


def test_good_notes_parse_and_yaml_off_means_off(tmp_path):
    cfg = load_config()
    p = tmp_path / "led_notes.yaml"
    p.write_text("dashcam_model: 700\nfile_type: .MP4\nresolution: 1080p\nfps: '29.97'\ndate_stamp: off\n"
                 "wdr_hdr: off\ncamera_height_cm: 35\nled_radius_mm: [140, 30, 80]\nturns_timed: 30\n"
                 "time_33rpm_s: 54.2\ntime_45rpm_s: 40.1\nruler_rpm: 33\n")
    notes, errors, warnings = load_notes(p, cfg)
    assert errors == [] and warnings == []
    assert notes["dashcam_model"] == "700" and notes["file_type"] == "mp4"
    assert notes["resolution"] == [1920, 1080] and notes["fps"] == pytest.approx(29.97)
    assert notes["date_stamp"] == "off" and notes["wdr_hdr"] == "off"
    assert notes["led_radius_mm"] == [30, 80, 140] and notes["ruler_rpm"] == 33


def test_malformed_notes_give_one_line_per_key(tmp_path):
    cfg = load_config()
    bad = {**GOOD_NOTES, "fps": "thirty", "led_radius_mm": [30, 80], "date_stamp": "middle", "resolution": "big",
           "wdr_hdr": "maybe", "turns_timed": -3, "file_type": "mkv", "camera_height_cm": 4000,
           "ruler_rpm": 78, "led_radiuss_mm": [1, 2, 3]}
    del bad["time_45rpm_s"]
    notes, errors, warnings = load_notes(_write_notes(tmp_path / "led_notes.yaml", bad), cfg)
    keys = ["fps", "led_radius_mm", "date_stamp", "resolution", "wdr_hdr", "turns_timed", "file_type",
            "camera_height_cm", "ruler_rpm", "time_45rpm_s"]
    assert len(errors) == len(keys)
    for key in keys:
        line = next(e for e in errors if e.startswith(f"led_notes.yaml: {key} "))
        assert "Write " in line and "for example" in line
    assert any("unknown key led_radiuss_mm" in w for w in warnings)


def test_notes_warnings_for_swapped_times_wdr_and_file_mismatch(tmp_path):
    cfg = load_config()
    swapped = {**GOOD_NOTES, "time_33rpm_s": 40.0, "time_45rpm_s": 54.0, "wdr_hdr": "on"}
    notes, errors, warnings = load_notes(_write_notes(tmp_path / "led_notes.yaml", swapped), cfg)
    assert errors == []
    assert sum("check both values" in w for w in warnings) == 2
    assert any("wdr_hdr is on" in w for w in warnings)
    probes = {"led_33rpm_a.AVI": {"width": 1280, "height": 720, "fps": 25.0, "codec": "mjpeg"}}
    out = compare_with_notes("led_33rpm", probes, notes, cfg)
    assert len(out) == 3 and "1280x720" in out[0] and "25 fps" in out[1] and ".avi" in out[2]


def test_missing_or_broken_notes_file(tmp_path):
    cfg = load_config()
    _, errors, _ = load_notes(tmp_path / "led_notes.yaml", cfg)
    assert "data/led_notes_template.yaml" in errors[0]
    (tmp_path / "led_notes.yaml").write_text("fps: [30\n")
    _, errors, _ = load_notes(tmp_path / "led_notes.yaml", cfg)
    assert len(errors) == 1 and "YAML" in errors[0]


# Date-stamp mask ------------------------------------------------------------------------------------
@pytest.mark.parametrize("position", STAMP_POSITIONS)
def test_stamp_mask_covers_the_drawn_stamp_and_nothing_else(position):
    cfg = load_config()
    band = cfg["validate"]["led_files"]["stamp_band_frac"]
    corner = cfg["validate"]["led_files"]["stamp_corner_frac"]
    spec, err = parse_stamp(position.replace("-", "_").upper())
    assert err is None and spec == position
    (box,) = stamp_boxes(spec, cfg)
    x0, y0, x1, y1 = box
    assert (y0, y1) == ((0.0, band) if position.startswith("top") else (1.0 - band, 1.0))
    if position in ("top", "bottom"):
        assert (x0, x1) == (0.0, 1.0)
    else:
        assert x1 - x0 == pytest.approx(corner) and (x0 == 0.0) == position.endswith("left")
    for w, h in ((640, 360), (1920, 1080), (2560, 1440)):
        img = np.zeros((h, w, 3), np.uint8)
        draw_stamp(img, position, 0.25)
        mask = stamp_mask(h, w, [box])
        lit = img.max(axis=2) > 0
        assert lit.any() and not (lit & (mask == 0)).any()
        assert abs(mask.mean() - (x1 - x0) * (y1 - y0)) < 0.01


def test_stamp_boxes_off_box_and_lists():
    cfg = load_config()
    assert parse_stamp(False) == ("off", None) and stamp_boxes("off", cfg) == []
    spec, err = parse_stamp([0.0, 0.9, 0.6, 1.0])
    assert err is None and stamp_boxes(spec, cfg) == [(0.0, 0.9, 0.6, 1.0)]
    spec, err = parse_stamp(["bottom", "top-right"])
    assert err is None and len(stamp_boxes(spec, cfg)) == 2
    assert parse_stamp([0.5, 0.9, 0.2, 1.0])[1].startswith("not a box")
    assert parse_stamp("middle")[1].startswith("not off or one of")
    mask = stamp_mask(100, 200, [(0.0, 0.9, 0.6, 1.0)])
    assert mask[90:, :120].all() and not mask[:90].any() and not mask[:, 120:].any()


@pytest.mark.slow
def test_an_unmasked_stamp_does_not_pose_as_an_led_ring(tmp_path):
    cfg = load_config()
    p = tmp_path / "led.mp4"
    t = led_turntable_clip(p, rpm=100 / 3, seconds=4, size=(640, 360), radii_px=(40, 85, 130), stamp="top-left")
    r = analyse_led_clip([p], t["omega_rad_s"], cfg)                       # date stamp not masked
    assert [round(x["radius_px"]) for x in r["rings"]] == [40, 85, 130]
    assert r["rings_rejected"] and r["rings_rejected"][0]["arc_deg"] < 180     # the blinking dot's tracks
    assert abs(r["median_speed_error_pct"]) < 1.0
    masked = analyse_led_clip([p], t["omega_rad_s"], cfg, stamp_boxes("top-left", cfg))
    assert "rings_rejected" not in masked and masked["tracks_used"] == 3


def test_masking_the_stamp_removes_its_false_tracks(tmp_path):
    cfg = load_config()
    p = tmp_path / "night_drive.mp4"
    night_drive_clip(p, seconds=4, stamp="top-right")
    open_ = false_tracks_per_minute([p], cfg)
    masked = false_tracks_per_minute([p], cfg, boxes=stamp_boxes("top-right", cfg))
    assert open_["detections"] > 0 and open_["moving_tracks"] > 0      # the blinking recording dot
    assert masked["detections"] == 0 and masked["moving_tracks"] == 0


def test_timing_summary_flags_gaps_and_backward_times():
    t = np.arange(0, 3, 1 / 30)
    s = timing_summary([np.delete(t, [10, 11, 50]), t + 0.07], 0.25, repeated=2)   # two parts, the second offset
    assert s["frame_interval_median_ms"] == pytest.approx(1000 / 30, abs=1e-3) and s["frames"] == 177
    assert s["fps_measured"] == pytest.approx(175 / (89 / 30 + 89 / 30), rel=1e-4)    # 3 frames lost in 175 intervals
    ms = np.round(np.arange(0, 10, 1 / 29.97), 3)                                    # 29.97 fps in a 1 ms time base
    assert timing_summary([ms], 0.25)["fps_measured"] == pytest.approx(29.97, abs=0.01)
    assert s["frames_missing_est"] == 3 and s["timestamps_not_increasing"] == 0
    assert s["repeated_frames"] == 2 and "warning" not in s
    assert 0 < s["irregular_interval_fraction"] < 0.03
    back = t.copy()
    back[20] = back[19]
    s = timing_summary([back], 0.25)
    assert s["timestamps_not_increasing"] == 1 and "warning" in s


# End to end ------------------------------------------------------------------------------------------
def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "wfglink", *args], capture_output=True, text=True,
                          cwd=str(PROJECT_ROOT))


@pytest.mark.slow
def test_validate_led_end_to_end_on_a_fake_raw_folder(tmp_path):
    raw = tmp_path / "raw"
    kw = dict(size=(640, 360), fps=30, radii_px=(40, 85, 130), stamp="bottom-left")
    led_turntable_clip(raw / "led_33rpm.MP4", rpm=100 / 3, seconds=4, parts=2, **kw)
    led_turntable_clip(raw / "led_45rpm.MP4", rpm=45.0, seconds=4, parts=2, duty=0.5, seed=1, **kw)
    led_turntable_clip(raw / "led_ruler.avi", rpm=0.0, seconds=1.5, ruler_px_per_mm=1.25, codec="mpeg4", **kw)
    led_turntable_clip(raw / "room_test.MOV", rpm=100 / 3, seconds=2.5, seed=2, **kw)
    night_drive_clip(raw / "night_drive.ts", seconds=3, stamp="bottom-left")
    _write_notes(raw / "led_notes.yaml", {**GOOD_NOTES, "ruler_rpm": 0})
    out = tmp_path / "validation" / "led_report.json"

    r = _run("validate", "--suite", "led", "--raw", str(raw), "--out", str(out))
    assert r.returncode == 0, r.stdout + r.stderr
    lines = r.stdout.splitlines()
    for role in ("led_33rpm", "led_45rpm"):
        line = next(x for x in lines if x.startswith(f"{role}: LEDs tracked"))
        assert "LEDs tracked 3 of 3" in line and "median speed error" in line
    assert any(x.startswith("led_ruler: LEDs tracked 0 of 3 (turntable stopped") for x in lines)
    assert any(x.startswith("room_test:") and "LED rings found: 3" in x for x in lines)
    assert any(x.startswith("night_drive:") and "false counts per minute" in x for x in lines)
    summary = next(x for x in lines if x.startswith("summary: "))
    assert "PASS" in summary and "night drive false counts per minute" in summary
    assert not any("passes under the date-stamp mask" in x for x in lines)

    rep = json.loads(out.read_text())
    assert rep["summary"]["status"] == "PASS" and rep["summary"]["tracks"] >= 6
    assert rep["summary"]["median_abs_speed_error_pct"] < 1.0
    c33 = rep["clips"]["led_33rpm"]
    assert c33["files"] == ["led_33rpm_a.MP4", "led_33rpm_b.MP4"] and c33["parts_used"] == 2
    assert c33["truth"]["omega_rad_s"] == pytest.approx(2 * math.pi * 30 / 54.0, abs=1e-4)
    assert c33["metric"]["scale_source"] == "rings" and abs(c33["metric"]["median_error_pct"]) < 1.5
    assert rep["clips"]["night_drive"]["false_tracks_per_min"] == 0.0
    assert rep["date_stamp"]["masked_boxes_frac"] == [[0.0, 0.9, 0.5, 1.0]]
    assert set(rep["provenance"]["inputs"]) == {p.name for p in raw.iterdir() if p.suffix != ".yaml"}
    stills = out.parent / "led_stills"
    for name in ("led_33rpm_mask.jpg", "led_45rpm_mask.jpg", "led_ruler_mask.jpg", "room_test_mask.jpg",
                 "night_drive_mask.jpg", "led_ruler_full.png", "led_ruler_centre_2x.png"):
        assert (stills / name).exists(), name
    full = cv2.imread(str(stills / "led_ruler_full.png"))
    crop = cv2.imread(str(stills / "led_ruler_centre_2x.png"))
    assert full.shape == (360, 640, 3) and crop.shape == (360, 640, 3)


def test_validate_led_lists_missing_inputs_and_exits_2(tmp_path):
    _touch(tmp_path / "raw", "led_33rpm_a.mp4", "led_33rpm_c.mp4")
    r = _run("validate", "--suite", "led", "--raw", str(tmp_path / "raw"), "--out", str(tmp_path / "rep.json"))
    assert r.returncode == 2
    assert "part led_33rpm_b is missing" in r.stdout
    assert "led_45rpm: no file led_45rpm.<ext>" in r.stdout
    assert "led_notes.yaml: not found" in r.stdout
    assert not (tmp_path / "rep.json").exists()


def test_held_out_suites_need_final(tmp_path):
    r = _run("validate", "--suite", "mismatch")
    assert r.returncode == 2 and "held out" in r.stderr and "--final" in r.stderr
    import argparse

    from wfglink.validate.command import add_arguments

    ap = argparse.ArgumentParser()
    add_arguments(ap)
    cmd = synthetic_command(ap.parse_args(["--suite", "core", "--workers", "1", "--no-generate"]))
    assert cmd[1].endswith("scripts/run_suite.py") and cmd[2:] == ["core", "--workers", "1", "--no-generate"]
    cmd = synthetic_command(ap.parse_args(["--suite", "coverage", "--final", "--record"]))
    assert cmd[2:] == ["coverage", "--record"]
