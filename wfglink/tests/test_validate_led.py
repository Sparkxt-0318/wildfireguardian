"""LED turntable analysis and the night-drive false-alarm count, on rendered stand-ins."""
import math

import av
import numpy as np
import pytest

from wfglink.config import load_config
from wfglink.sitting.standins import led_turntable_clip
from wfglink.validate.drive import false_tracks_per_minute
from wfglink.validate.led import analyse_led_clip, analyze_led_recordings, expected_speed, shared_center_fit


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


@pytest.mark.slow
def test_wrong_stopwatch_time_shows_up(tmp_path):
    p = tmp_path / "led.mp4"
    truth = led_turntable_clip(p, rpm=33.333, seconds=4, size=(640, 360), fps=30, radii_px=(40, 90, 150))
    r = analyse_led_clip([p], truth["omega_rad_s"] * 1.05, load_config())
    assert abs(r["median_speed_error_pct"] + 100 * (1 - 1 / 1.05)) < 0.5
    assert "warnings" in r


@pytest.mark.slow
def test_recordings_entry_point_builds_the_table(tmp_path):
    for name, rpm in (("A.mp4", 33.333), ("B.mp4", 45.0)):
        led_turntable_clip(tmp_path / name, rpm=rpm, seconds=4, size=(640, 360), fps=30, radii_px=(40, 90, 150))
    steps = {"iph_led_s1": {"files": [{"file": "A.mp4"}], "inputs": {"t30_s1": 54.0}},
             "iph_led_s2": {"files": [{"file": "B.mp4"}], "inputs": {"t30_s2": 40.0}},
             "dc_led_s1": {"files": [{"file": "A.mp4"}], "inputs": {}}}
    res = analyze_led_recordings(steps, tmp_path, load_config())
    assert abs(res["iphone"]["median_speed_error_pct"]) < 1.0
    assert res["dashcam"]["speeds"]["speed1"] == {"status": "no stopwatch time"}
    assert [row["device"] for row in res["table"]] == ["iphone", "dashcam"]


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
