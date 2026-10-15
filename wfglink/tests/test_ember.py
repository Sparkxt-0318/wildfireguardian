"""The "Become an ember" mode: detector, static rejection, at most six embers, speeds, the A4
calibration, the synthetic suite on a small case and the ruler-path analysis."""
import json
import math

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


from wfglink.ui.i18n import t as t_  # noqa: E402


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
    pipe, states = _run(sc, _cfg(sc, max_tracks=6), 3.0)
    assert max(s.ember_count for s in states) == 6
    ids = {e["id"] for s in states for e in s.embers}
    assert ids <= set(range(1, 7)) and len(ids) == 6


def test_the_booth_tracks_at_most_three_phones_and_says_so():
    from PySide6.QtGui import QGuiApplication

    from wfglink.render.scene import render_image

    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841
    phones = [{"z": z, "trajectory": _line(z, -0.9 + 0.22 * k, -0.25 + 0.06 * (k % 3), 0.5 * (-1) ** k, 4.0),
               "landscape": False} for k, z in enumerate((1.6, 1.8, 2.0, 2.2, 2.4, 2.6))]
    sc = synth.make_scene("six", size=(960, 540), seconds=4.0, seed=2, spec={"phones": phones})
    cfg = _cfg(sc)
    assert cfg["ember"]["max_tracks"] == 3                       # the booth's cap (your decision of 2026-10-15)
    pipe, states = _run(sc, cfg, 3.0)
    assert max(s.ember_count for s in states) == 3                # six phones in view, three tracked
    assert {e["id"] for s in states for e in s.embers} <= {1, 2, 3}
    assert states[-1].ember_max == 3
    assert t_("en", "ember_max").format(n=3).startswith("max 3") and "최대 3" in t_("ko", "ember_max").format(n=3)
    assert not render_image(960, 540, states[-1], "en").isNull()


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
    # A calibration through one capture backend is not used for the other (their crops may differ).
    cfg["ember"]["calibration"]["backend"] = "pyav"
    assert focal_for(cfg, 1280, 720, "C920", "pyav")[1] and focal_for(cfg, 1280, 720, "C920")[1]
    f, cal, why = focal_for(cfg, 1280, 720, "C920", "opencv")
    assert not cal and "backend" in why


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
                                        "speed_median_rel_err", "ember_ruler_displacement_rel_err",
                                        "ember_ruler_screen_speed_rel_err",
                                        "ember_free_probable_id_switches_per_phone_per_min"}
    # The recordings' goals are n/a without the recordings; the scenes are said to be the tuning set.
    assert all(saved["goal_check"][k]["status"] == "n/a" for k in saved["goal_check"] if k.startswith("ember_"))
    assert s["tuned_on"] is True and "id_switches_persistent_per_phone_per_min" in s["pooled"]
    assert any(line.startswith("synthetic") and "not held out" in line for line in V.summary_lines(rep))
    # With the recordings, their numbers are judged against the same goals as the synthetic phones.
    fake = dict(saved, ember_ruler={"status": "ok", "displacement_rel_err": -0.15, "screen_speed_rel_err": 0.04},
                ember_free={"status": "ok", "probable_id_switches_per_phone_per_min": 0.5})
    g = V.goal_check(fake, saved["goals"])
    assert g["ember_ruler_displacement_rel_err"]["status"] == "missed"
    assert g["ember_ruler_screen_speed_rel_err"]["status"] == "met"
    assert g["ember_free_probable_id_switches_per_phone_per_min"]["status"] == "met"
    assert V.persistent_switches([[[1, 0.0, 2.0], [2, 2.03, 2.07], [1, 2.1, 5.0]], [[3, 0.0, 1.0], [4, 1.1, 3.0]]], 0.2) == 1
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


def test_record_force_replaces_and_a_cancelled_recording_is_not_kept(tmp_path, monkeypatch):
    from wfglink.ember import preview as P
    from wfglink.ember.record import record

    cfg = load_config(overrides={"camera": {"width": 640, "height": 360}, "ember": {"record": {"countdown_s": 0.0}}})
    first = record(cfg, "ember_free", 1.0, out_dir=tmp_path, fake="one_at_2m", preview=False)
    assert (tmp_path / "ember_free.mp4").exists() and first["frames"] > 10
    again = record(cfg, "ember_free", 1.0, out_dir=tmp_path, fake="one_at_2m", preview=False, force=True)
    assert again["frames"] > 10                                   # the same command with --force records it again

    def cancelled_preview(cfg, on_frame, *, source, on_capture, **kw):   # Esc after a few frames
        for _ in range(8):
            f = source.read()
            if f is not None:
                on_capture(f)
        source.close()
        return {"cancelled": True}

    monkeypatch.setattr(P, "run_preview", cancelled_preview)
    res = record(cfg, "ember_ruler", 5.0, out_dir=tmp_path, fake="one_at_2m", preview=True)
    assert res["cancelled"] and res["removed"] and not (tmp_path / "ember_ruler.mp4").exists()
    # A cancelled retake with --force keeps the earlier good recording.
    before = (tmp_path / "ember_free.mp4").read_bytes()
    res = record(cfg, "ember_free", 5.0, out_dir=tmp_path, fake="one_at_2m", preview=True, force=True)
    assert res["cancelled"] and res["kept_earlier"] and (tmp_path / "ember_free.mp4").read_bytes() == before
    assert not list(tmp_path.glob(".*.part.mp4"))


def test_calibrate_writes_only_a_stable_result_and_warns_on_an_odd_field_of_view(tmp_path, monkeypatch, capsys):
    from wfglink.ember import calibrate as K

    base = {"focal_px": 914.0, "hfov_deg": 70.0, "distance_m": 2.0, "m_per_px": 0.00219, "size": [1280, 720],
            "target": "A4", "frames": 30, "spread": 0.004, "rms_px": 0.4, "stable": True, "camera": "c920"}
    local = tmp_path / "booth_local.yaml"
    monkeypatch.setattr(K, "calibrate_video", lambda video, cfg, dist: dict(base, stable=False, spread=0.05))
    assert cli.main(["calibrate", "--video", "x.mp4", "--out", str(local)]) == 1
    assert not local.exists() and "nothing written" in capsys.readouterr().err
    monkeypatch.setattr(K, "calibrate_video", lambda video, cfg, dist: dict(base, hfov_deg=93.0, focal_px=607.0))
    assert cli.main(["calibrate", "--video", "x.mp4", "--out", str(local)]) == 0
    assert "WARNING" in capsys.readouterr().err and local.exists()
    monkeypatch.setattr(K, "calibrate_video", lambda video, cfg, dist: dict(base))
    assert cli.main(["calibrate", "--video", "x.mp4", "--out", str(local)]) == 0
    assert "WARNING" not in capsys.readouterr().err


def _blobs(pts, diam=20.0, light=0.0, on_bg=False):
    from wfglink.ember.detect import Blobs

    n = len(pts)
    if not n:
        return Blobs()
    return Blobs(np.array([p[0] for p in pts], float), np.array([p[1] for p in pts], float), np.full(n, diam),
                 np.full(n, 255.0), np.ones(n), np.ones(n), np.full(n, on_bg), [(0, 0, 4, 4)] * n,
                 np.full(n, float(light)))


def test_tracker_keeps_a_lamp_on_its_own_track_as_a_phone_sweeps_past():
    """A phone ember whose prediction lies as near a lamp as its phone takes the phone; the lamp
    (hidden for a moment by a passer-by) goes back to its own track and never becomes an ember."""
    from wfglink.ember.track import EmberTracker

    cfg = load_config()
    tr = EmberTracker(cfg, 457.0)
    lamp = (500.0, 300.0)
    t = 0.0
    for _ in range(90):                                    # the lamp alone for 3 s: a static light
        tr.update(_blobs([lamp], light=1.0), t)
        t += 1 / 30
    (light_track,) = tr.tracks
    assert light_track.static and not light_track.shown
    # A phone comes from the left fast while a passer-by hides the lamp, and stops just short of
    # it: the ember's prediction runs on to the lamp, 3 px from it and 20 px from the phone.
    x = 277.0
    for k in range(13):
        x = 297.0 + 20.0 * k if k <= 9 else 477.0
        pts = [(x, 300.0)] + ([] if k in (7, 8, 9) else [lamp])
        tr.update(_blobs(pts), t)
        t += 1 / 30
    shown = tr.shown()
    assert len(shown) == 1 and abs(shown[0].x - 477.0) < 1.0      # the ember stays on the phone, not the lamp
    assert not light_track.shown and abs(light_track.x - lamp[0]) < 1.0


def test_tracker_ends_an_ember_that_rests_on_a_light():
    """An ember that comes to rest where the light map is bright (a lamp it caught) ends after
    ember.track.light_rest_s; one resting on a dark wall stays (a visitor holding still)."""
    from wfglink.ember.track import EmberTracker

    cfg = load_config()
    for light, stays in ((0.9, False), (0.0, True)):
        tr = EmberTracker(cfg, 457.0)
        t, x = 0.0, 200.0
        for _ in range(20):                                # a phone moves and shows
            x += 10.0
            tr.update(_blobs([(x, 300.0)]), t)
            t += 1 / 30
        assert len(tr.shown()) == 1
        for _ in range(int(2.0 * 30)):                      # then rests for 2 s
            tr.update(_blobs([(x, 300.0)], light=light), t)
            t += 1 / 30
        assert (len(tr.shown()) == 1) == stays, light


def test_tracker_does_not_show_a_track_on_a_jump():
    """A blob that jumps (a TV picture's cut) has not moved like a phone: the jump does not count."""
    from wfglink.ember.track import EmberTracker

    cfg = load_config()
    tr = EmberTracker(cfg, 457.0)
    t = 0.0
    for k in range(40):
        p = (400.0, 300.0) if k < 20 else (460.0, 300.0)    # 0.13 m in one frame, then still
        tr.update(_blobs([p]), t)
        t += 1 / 30
    assert tr.shown() == []


@pytest.mark.slow
def test_the_booth_scene_shows_no_lamp_as_an_ember():
    """The demo scene (live --synthetic, the demo gate): LiveScene('booth', seed 1) for 40 s. No
    ember sits on a static light for longer than the rest rule allows, and the count of embers
    stays at or below the phones seen in the last 0.5 s in at least 97 percent of frames."""
    seconds, fps = 40.0, 30
    scene = synth.LiveScene("booth", size=(1280, 720), fps=fps, seed=1)
    W = 1280
    lights = [l["box"] for l in scene.scene.room.lights]
    cfg = load_config()
    pipe = EmberPipeline(cfg)
    vis, over, run, longest = [], 0, 0, 0
    n = int(seconds * fps)
    for i in range(n):
        t = i / fps
        st = pipe.process(Frame(scene.render(t), t, i, t, {"camera": "fake: booth", "synthetic": True}))
        truth = scene.scene.truth(t)
        vis.append((t, sum(1 for p in truth if p.get("vis"))))
        if (st.ember_count or 0) > max(k for tt, k in vis if tt >= t - 0.5):
            over += 1
        on_light = False
        for e in st.embers:
            near_phone = min((math.hypot(e["x"] - (W - 1 - p["x"]), e["y"] - p["y"]) for p in truth), default=1e9) <= 60
            in_box = any(W - 1 - b[2] - 5 <= e["x"] <= W - 1 - b[0] + 5 and b[1] - 5 <= e["y"] <= b[3] + 5 for b in lights)
            on_light |= in_box and not near_phone
        run = run + 1 if on_light else 0
        longest = max(longest, run)
    assert longest / fps <= cfg["ember"]["track"]["light_rest_s"] + 1.0, longest / fps
    assert 1 - over / n >= 0.97, over / n


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
