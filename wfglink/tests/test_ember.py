"""The "Become an ember" mode: detector, static rejection, at most six embers, speeds, the A4
calibration, the synthetic suite on a small case and the ruler-path analysis."""
import json

import numpy as np
import pytest
import yaml

from wfglink import cli
from wfglink.config import load_config
from wfglink.ember import synth
from wfglink.ember import validate as V
from wfglink.ember.calibrate import TargetDetector, calibrate_video, write_local
from wfglink.ember.pipeline import EmberPipeline, focal_for
from wfglink.io.frames import Frame

SMALL = (640, 360)


def _cfg(scene=None, **ember):
    cfg = load_config()
    if scene is not None:
        cfg["camera"]["focal_px"] = scene.cam.f
        cfg["ember"]["calibration"] = {"size": [scene.cam.width, scene.cam.height], "camera": None}
    cfg["ember"].update(ember)
    return cfg


def _run(scene, cfg, seconds, fps=30):
    pipe = EmberPipeline(cfg)
    pipe.record()
    states = []
    for i in range(int(seconds * fps)):
        t = i / fps
        states.append(pipe.process(Frame(scene.render(t), t, i)))
    return pipe, states


def _line(z, x0, y, vx, seconds, t_start=0.0):
    t = np.arange(-1.0, seconds + 1.0, 0.002)
    xyz = np.zeros((len(t), 3))
    xyz[:, 0] = x0 + vx * np.clip(t - t_start, 0, None)
    xyz[:, 1], xyz[:, 2] = y, z
    vel = np.gradient(xyz, 0.002, axis=0)
    return synth.Trajectory(t, xyz, vel, np.zeros_like(t), np.zeros_like(t))


def test_page_profile_matches_the_page():
    prof, step = synth.page_profile()
    centre, edge = prof[0], prof[int(round(1.0 / step))]
    assert centre[2] == pytest.approx(1.0) and centre[0] > 0.6           # #FFF1D6: nearly white (BGR)
    mid = prof[int(round(0.45 / step))]
    assert mid[2] == pytest.approx(1.0) and mid[1] < 0.3 and mid[0] < 0.02  # #FF8A1F: orange
    assert np.all(edge < 1e-3) and np.all(prof[-1] == 0)                  # transparent at the disc's edge
    assert synth.DISC_FRAC == 0.36


def test_detector_finds_the_phone_not_the_lamps_and_mirrors():
    traj = _line(2.0, -0.4, -0.05, 0.6, 3.0)
    spec = {"phones": [{"z": 2.0, "trajectory": traj, "landscape": False}], "lamp": True, "bulb": True, "window": True}
    sc = synth.make_scene("custom", size=SMALL, seconds=3.0, seed=4, spec=spec)
    pipe, states = _run(sc, _cfg(sc), 2.5)
    st = states[-1]
    assert st.mode == "ember" and st.ember_count == 1 and st.speed_unit == "m/s" and st.measured_at_m == 2.0
    assert st.calibrated and st.camera_state == "ok" and st.warm == 1.0
    tr = sc.truth(2.5 - 1 / 30)[0]
    e = st.embers[0]
    assert e["id"] == 1 and e["x"] == pytest.approx(SMALL[0] - 1 - tr["x"], abs=1.5)   # mirrored
    assert e["y"] == pytest.approx(tr["y"], abs=1.5)
    # Ceiling lights, the window and the warm lamp and bulb are never embers.
    assert all(s.ember_count <= 1 for s in states)
    assert len(st.trails) == 1 and st.field_uvn.shape == (9, 16, 3) and st.field_uvn[..., 2].sum() >= 1


def test_static_lights_never_become_embers():
    spec = {"phones": [], "lamp": True, "bulb": True, "tv": True, "window": True, "passers": 2}
    sc = synth.make_scene("empty", size=SMALL, seconds=8.0, seed=9, spec=spec)
    pipe, states = _run(sc, _cfg(sc), 8.0)
    assert max(s.ember_count for s in states) == 0
    # The bare bulb is warm and phone-sized: it is seen, and kept as a static light.
    assert any(tr.static for tr in pipe.tracker.tracks + pipe.finished)


def test_at_most_six_embers_with_ids_one_to_six():
    phones = [{"z": z, "trajectory": _line(z, -0.9 + 0.22 * k, -0.25 + 0.06 * (k % 3), 0.5 * (-1) ** k, 4.0),
               "landscape": False} for k, z in enumerate((1.6, 1.8, 2.0, 2.2, 2.4, 2.6, 2.8, 3.0))]
    sc = synth.make_scene("eight", size=(960, 540), seconds=4.0, seed=2, spec={"phones": phones})
    pipe, states = _run(sc, _cfg(sc), 3.0)
    assert max(s.ember_count for s in states) == 6
    ids = {e["id"] for s in states for e in s.embers}
    assert ids <= set(range(1, 7)) and len(ids) == 6


def test_speed_in_m_s_at_the_standing_distance():
    for z, want in ((2.0, 0.5), (1.0, 1.0), (3.0, 0.5 * 2 / 3)):
        traj = _line(z, -0.45 * 1.4 * z, 0.0, 0.5, 2.0)           # stays in the 70 degree picture
        sc = synth.make_scene("line", size=SMALL, seconds=2.0, seed=1, spec={"phones": [{"z": z, "trajectory": traj}]})
        pipe, states = _run(sc, _cfg(sc), 2.0)
        speeds = [s.embers[0]["speed_m_s"] for s in states[30:] if s.embers and s.embers[0]["speed_m_s"]]
        assert len(speeds) >= 25, z
        # 0.5 m/s across the picture, measured at 2.0 m: right at 2 m, twice at 1 m, two thirds at 3 m.
        assert np.median(speeds) == pytest.approx(want, rel=0.03), z


def test_scale_from_calibration_or_nominal_field_of_view():
    cfg = load_config()
    f, cal, src = focal_for(cfg, 1280, 720)
    assert not cal and f == pytest.approx(640 / np.tan(np.radians(35)))
    cfg["camera"]["focal_px"] = 1000.0
    cfg["ember"]["calibration"] = {"size": [1280, 720], "camera": "C920"}
    assert focal_for(cfg, 640, 360, "C920")[:2] == (500.0, True)
    assert not focal_for(cfg, 1280, 720, "MacBook Pro Camera")[1]         # another camera: nominal
    assert not focal_for(cfg, 640, 480)[1]                                 # another aspect: nominal


def test_calibration_on_a_rendered_target(tmp_path):
    video = tmp_path / "target.mp4"
    truth = synth.target_clip(video, hfov_deg=66.0, distance_m=2.0, tilt_deg=(7.0, -10.0, 2.0), seconds=1.2)
    cfg = load_config()
    res = calibrate_video(video, cfg, 2.0)
    assert res["focal_px"] == pytest.approx(truth["focal_px"], rel=0.02)
    assert res["hfov_deg"] == pytest.approx(66.0, abs=1.0) and res["rms_px"] < 1.5
    # The command writes camera.focal_px and ember.calibration, keeping the file's other keys.
    local = tmp_path / "booth_local.yaml"
    local.write_text("ui:\n  screen: external\ncamera:\n  name: c920\n", encoding="utf-8")
    assert cli.main(["calibrate", "--video", str(video), "--distance-m", "2.0", "--out", str(local)]) in (0, 1)
    doc = yaml.safe_load(local.read_text(encoding="utf-8"))
    assert doc["ui"]["screen"] == "external" and doc["camera"]["name"] == "c920"
    assert doc["camera"]["focal_px"] == pytest.approx(truth["focal_px"], rel=0.02)
    assert doc["ember"]["distance_m"] == 2.0 and doc["ember"]["calibration"]["size"] == [1280, 720]
    assert "A4" in doc["ember"]["calibration"]["target"]
    write_local({"focal_px": 900.0, "distance_m": 2.5}, local)
    assert yaml.safe_load(local.read_text(encoding="utf-8"))["camera"]["name"] == "c920"


def test_calibrate_with_its_preview_window(tmp_path):
    """The live path (camera thread, fullscreen preview, stable result, config written), run in
    its own process (a QApplication) on the offscreen platform, with a rendered target as camera."""
    import os
    import subprocess
    import sys

    video = tmp_path / "target.mp4"
    truth = synth.target_clip(video, hfov_deg=70.0, distance_m=2.0, seconds=1.5)
    out = tmp_path / "local.yaml"
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    res = subprocess.run([sys.executable, "-m", "wfglink", "calibrate", "--fake-camera", str(video), "--out", str(out)],
                         capture_output=True, text=True, timeout=120, env=env)
    assert res.returncode == 0, res.stdout + res.stderr
    doc = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert doc["camera"]["focal_px"] == pytest.approx(truth["focal_px"], rel=0.02)
    assert doc["ember"]["calibration"]["camera"] == "fake: target.mp4" and doc["ember"]["calibration"]["stable"]


def test_target_markers_are_read_from_the_raster_target():
    from wfglink.ember import target as T

    img = (T.target_image(3.0) * 255).astype(np.uint8)
    pad = np.full((img.shape[0] + 80, img.shape[1] + 80), 255, np.uint8)
    pad[40:-40, 40:-40] = img
    ids, pts, obj = TargetDetector().find(pad)
    assert ids == [0, 1, 2, 3] and pts.shape == (16, 2) and obj.shape == (16, 3)
    # Corner 0 of marker 0 lies MARGIN_MM from the sheet's corner.
    assert pts[0] == pytest.approx([40 + T.MARGIN_MM * 3.0, 40 + T.MARGIN_MM * 3.0], abs=1.0)


def test_ruler_analysis_on_a_synthetic_ruler_clip(tmp_path):
    sc = synth.ruler_scene(size=SMALL, seed=3, rest_s=1.2)
    out = synth.write_scene_clip(sc, tmp_path, crf=23, stem="ruler")
    truth_meta = out["meta"]
    cfg = _cfg(sc)
    r = V.ruler_clip(out["video"], cfg, 1.0)
    assert r["status"] == "ok" and r["calibrated"]
    assert r["displacement_m"] == pytest.approx(1.0, rel=0.03)
    assert abs(r["screen_speed_rel_err"]) < 0.06
    # The move time comes from the video; a minimum-jerk 1 s move leaves its rests a little later
    # and arrives a little earlier than its nominal start and end.
    assert 0.6 < r["move_s"] <= truth_meta["ruler"]["move_s"] + 0.05


def test_small_synthetic_suite_writes_its_report(tmp_path):
    cfg = load_config()
    cfg["validate"]["ember"]["size"] = list(SMALL)
    rep = V.run_suite(cfg, raw=tmp_path / "raw", out=tmp_path / "ember_report.json", work_dir=tmp_path / "work",
                      scenes=["two_at_2m", "empty_room"], seconds=5.0, log=lambda m: None)
    saved = json.loads((tmp_path / "ember_report.json").read_text(encoding="utf-8"))
    s = saved["synthetic"]
    assert set(s["scenes"]) == {"two_at_2m", "empty_room"}
    assert s["scenes"]["two_at_2m"]["recall"] > 0.85 and s["scenes"]["two_at_2m"]["precision"] > 0.9
    assert s["pooled"]["static_light_tracks"] == 0 and s["scenes"]["empty_room"]["false_tracks"] == 0
    assert s["ruler"]["status"] == "ok"
    assert saved["ember_free"]["status"] == "missing" and saved["ember_ruler"]["status"] == "missing"
    assert set(saved["goal_check"]) == {"recall_facing", "static_light_tracks_per_min", "id_switches_per_phone_per_min",
                                        "speed_median_rel_err"}
    assert any(line.startswith("synthetic") for line in V.summary_lines(rep))
    # A second run finds the generated scenes and does not make them again.
    before = sorted(p.name for p in (tmp_path / "work").iterdir())
    V.run_suite(cfg, raw=tmp_path / "raw", out=tmp_path / "again.json", work_dir=tmp_path / "work",
                scenes=["empty_room"], seconds=5.0, log=lambda m: None)
    assert sorted(p.name for p in (tmp_path / "work").iterdir()) == before


def test_free_clip_and_record_command_on_a_fake_camera(tmp_path):
    from wfglink.synth.degrade import read_video

    # `record` with a generated scene as the camera, without a window: countdown, then the clip.
    cfg_path = tmp_path / "rec.yaml"
    cfg_path.write_text("camera:\n  width: 640\n  height: 360\nember:\n  record:\n    countdown_s: 0.3\n", encoding="utf-8")
    code = cli.main(["record", "ember_free", "--seconds", "2.5", "--out-dir", str(tmp_path), "--no-preview",
                     "--fake-camera", "one_at_2m", "--config", str(cfg_path)])
    assert code == 0
    frames, pts = read_video(tmp_path / "ember_free.mp4")
    assert len(frames) >= 30 and np.all(np.diff(pts) > 0) and frames[0].shape == (360, 640, 3)
    assert cli.main(["record", "ember_free", "--seconds", "1", "--out-dir", str(tmp_path), "--no-preview",
                     "--fake-camera", "one_at_2m"]) == 2            # never overwritten without --force
    r = V.free_clip(tmp_path / "ember_free.mp4", load_config(str(cfg_path)), phones=1)
    assert r["status"] == "ok" and r["tracks_shown"] >= 1 and r["most_at_once"] <= 1
    assert r["coverage"] > 0.5 and not r["calibrated"]


def test_record_with_its_preview_window(tmp_path):
    """`record` with the countdown window, in its own process on the offscreen platform."""
    import os
    import subprocess
    import sys

    from wfglink.synth.degrade import read_video

    cfg_path = tmp_path / "rec.yaml"
    cfg_path.write_text("camera:\n  width: 640\n  height: 360\nember:\n  record:\n    countdown_s: 0.5\n", encoding="utf-8")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    res = subprocess.run([sys.executable, "-m", "wfglink", "record", "ember_ruler", "--seconds", "1.5", "--out-dir",
                          str(tmp_path), "--fake-camera", "two_at_2m", "--config", str(cfg_path)],
                         capture_output=True, text=True, timeout=120, env=env)
    assert res.returncode == 0, res.stdout + res.stderr
    frames, pts = read_video(tmp_path / "ember_ruler.mp4")
    assert len(frames) >= 20 and pts[-1] <= 1.5 + 1e-6


def test_ember_state_renders_on_the_booth_screen():
    from PySide6.QtGui import QGuiApplication

    from wfglink.render.scene import render_image

    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841

    traj = _line(2.0, -0.3, 0.0, 0.7, 2.0)
    sc = synth.make_scene("one", size=SMALL, seconds=2.0, seed=5, spec={"phones": [{"z": 2.0, "trajectory": traj}]})
    _, states = _run(sc, _cfg(sc), 1.5)
    img = render_image(960, 540, states[-1], "ko")
    assert img.width() == 960 and not img.isNull()


def test_pipeline_cost_per_frame():
    sc = synth.make_scene("three_mixed", size=(1280, 720), seconds=3.0, seed=6)
    pipe, _ = _run(sc, _cfg(sc), 2.0)
    # About 10 ms per 1280x720 frame is the budget; this machine is shared, so allow some room.
    assert pipe.stats.as_dict()["proc_ms_median"] < 20.0
