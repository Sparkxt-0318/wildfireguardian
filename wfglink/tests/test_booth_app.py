"""Booth app: both worker modes run end to end; design rules (contrast, sizes, text, strings);
the paused or absent iPad screen (state, note, fallback and recovery) and the run report."""
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from wfglink.ui import theme
from wfglink.ui.i18n import STRINGS


def test_strings_complete_and_dash_free():
    assert set(STRINGS["ko"]) == set(STRINGS["en"])
    for lang in STRINGS.values():
        for v in lang.values():
            assert "—" not in v and "–" not in v


@pytest.mark.parametrize("fg", [theme.INK, theme.INK2, theme.GREEN, theme.ORANGE])
def test_contrast_on_black_meets_wcag_aa(fg):
    assert theme.contrast_ratio(fg, theme.BG) >= 4.5


def test_two_metre_sizes_at_1080p():
    assert theme.px(theme.SIZES["value"], 1080) >= 96
    assert theme.px(theme.SIZES["label"], 1080) >= 28
    assert theme.px(theme.SIZES["tag"], 1080) >= 18


@pytest.mark.qt
def test_card_labels_fit_the_panel():
    from PySide6.QtGui import QFontMetrics, QGuiApplication

    from wfglink.render.scene import Layout
    from wfglink.ui.fonts import ui_font

    QGuiApplication.instance() or QGuiApplication([])
    L = Layout(1920, 1080)
    fm = QFontMetrics(ui_font(theme.px(theme.SIZES["label"], 1080)))
    for lang in ("ko", "en"):
        for key in ("count_rate", "cpc", "pnf", "speed"):
            assert fm.horizontalAdvance(STRINGS[lang][key]) <= L.panel.width(), (lang, key)


@pytest.mark.qt
def test_scene_renders_in_both_languages():
    import numpy as np
    from PySide6.QtGui import QGuiApplication

    from wfglink.render.scene import LiveState, render_image

    QGuiApplication.instance() or QGuiApplication([])
    s = LiveState(image=np.zeros((360, 640, 3), np.uint8), count_rate=3.2, cpc_gross=42, pnf=0.8, speed=150.0,
                  direction_deg=10.0, sparkline=np.arange(60, dtype=float), playback_speed=0.5)
    for lang in ("ko", "en"):
        img = render_image(1920, 1080, s, lang, show_limits=(lang == "en"))
        assert img.width() == 1920 and not img.isNull()


@pytest.mark.qt
def test_scene_shows_paused_and_absent_screen():
    from PySide6.QtGui import QGuiApplication

    from wfglink.render.scene import Layout, LiveState, render_image

    QGuiApplication.instance() or QGuiApplication([])
    img = np.full((360, 640, 3), 200, np.uint8)
    L = Layout(1920, 1080)
    c = L.video.center()

    def center_level(st: str, note: str = "") -> int:
        q = render_image(1920, 1080, LiveState(image=img, source_state=st, source_note=note), "en")
        return q.pixelColor(int(c.x()) - 300, int(c.y()) + 120).red()     # picture, away from the text

    live = center_level("live")
    for st in ("paused", "no_screen", "reconnecting"):
        assert center_level(st) < 0.6 * live            # the picture is dimmed under the message
    assert center_level("replay", "paused") == live      # a note does not dim the fallback picture
    for lang in ("ko", "en"):
        for st, note in (("paused", ""), ("no_screen", ""), ("replay", "paused"), ("live", "no_screen")):
            assert not render_image(1280, 720, LiveState(image=img, source_state=st, source_note=note), lang).isNull()


@pytest.mark.qt
def test_screen_note_and_source_fields():
    from wfglink.io.capture import ChainStatus, SourceOption
    from wfglink.io.frames import Frame
    from wfglink.ui.booth_app import screen_note, source_fields

    opts = [SourceOption("iphone", None, True), SourceOption("webcam", None, True),
            SourceOption("replay", None, False), SourceOption("synthetic", None, False)]
    ev = [{"event": "activated", "key": "iphone"}, {"event": "failed", "key": "iphone", "reason": "screen paused"},
          {"event": "activated", "key": "webcam"}]
    chain = SimpleNamespace(options=opts, events=ev)
    assert screen_note(chain, "iphone") == ""            # the best camera is in use
    assert screen_note(chain, "webcam") == "paused"
    ev += [{"event": "failed", "key": "webcam", "reason": "no screen markers"}, {"event": "activated", "key": "replay"}]
    assert screen_note(chain, "replay") == "no_screen"   # the latest failure of a better camera
    ev += [{"event": "probe", "key": "iphone"}, {"event": "failed", "key": "iphone", "reason": "device not available"}]
    assert screen_note(chain, "replay") == ""            # unplugged now: not a screen problem
    assert screen_note(None, "replay") == ""

    frame = Frame(np.zeros((4, 4, 3), np.uint8), 0.0, 0, 50.0)
    booth_pipe = SimpleNamespace(booth=object(), screen_status=lambda now: "paused" if now == 50.0 else "ok")
    live = ChainStatus(key="iphone", label="iPhone", live=True, state="live")
    f = source_fields(booth_pipe, live, frame, None)
    assert f == {"source_label": "iPhone", "source_state": "paused", "unprepared": False, "source_note": ""}
    replay = ChainStatus(key="replay", label="clip_hold2.mp4", live=False, state="replay")
    assert source_fields(booth_pipe, replay, frame, chain)["source_state"] == "replay"    # replay is never "paused"
    plain = SimpleNamespace(booth=None, screen_status=lambda now: None)                    # unprepared camera
    f = source_fields(plain, live, frame, None)
    assert f["source_state"] == "live" and f["unprepared"]
    synth = ChainStatus(key="synthetic", label="Synthetic", live=False, state="replay")
    assert source_fields(plain, synth, frame, None)["source_state"] == "synthetic"


def _run_booth(tmp_path: Path, cfg_text: str, source: str, seconds: float, extra: tuple[str, ...] = ()) -> dict:
    cfgfile = tmp_path / "run.yaml"
    cfgfile.write_text(cfg_text)
    report = tmp_path / "r.json"
    res = subprocess.run([sys.executable, "-m", "wfglink", "booth", "--source", source, "--screen", "primary",
                          "--duration", str(seconds), "--config", str(cfgfile), "--report", str(report), *extra],
                         capture_output=True, text=True, timeout=180,
                         env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert res.returncode == 0, res.stderr[-2000:]
    return json.loads(report.read_text())


@pytest.mark.slow
@pytest.mark.qt
@pytest.mark.parametrize("mode", ["thread", "process"])
def test_booth_runs_end_to_end(tmp_path, mode):
    hb = tmp_path / "heartbeat.json"
    r = _run_booth(tmp_path, f"live:\n  worker_mode: {mode}\n", "synthetic", 6, ("--heartbeat", str(hb)))
    assert r["worker_mode"] == mode
    assert r["errors"] == []
    assert r["frames"] > 20 and r["paints"] > 20
    # Both modes report the source, its chain events and the pipeline stats.
    assert r["source"] == "synthetic"
    assert [e["event"] for e in r["source_events"]][:1] == ["activated"]
    assert r["pipelines"]["synthetic"]["frames_in"] > 20
    assert r["source_states"].get("synthetic", 0) > 20
    # The heartbeat carries the active pipeline's counters for the soak analysis.
    pipe = json.loads(hb.read_text())["pipeline"]
    assert pipe["key"] == "synthetic"
    assert 20 < pipe["frames_analysed"] <= pipe["frames_in"] <= r["pipelines"]["synthetic"]["frames_in"]


# The paused iPad, end to end (camera-in-the-loop simulator) ---------------------------------------

@pytest.fixture(scope="module")
def booth_hold2(tmp_path_factory):
    """A small prepared booth clip: 640x360, 40 source frames at hold 2."""
    import av

    from wfglink.io.synthetic_live import SyntheticLiveSource
    from wfglink.screen.booth_prep import prepare

    d = tmp_path_factory.mktemp("booth")
    src = SyntheticLiveSource(width=640, height=360, realtime=False, seed=5)
    src.open()
    with av.open(str(d / "clip.mp4"), "w") as c:
        s = c.add_stream("libx264", rate=30)
        s.width, s.height, s.pix_fmt = 640, 360, "yuv420p"
        s.options = {"crf": "18", "preset": "veryfast"}
        for _ in range(40):
            for p in s.encode(av.VideoFrame.from_ndarray(src.read().image, format="bgr24")):
                c.mux(p)
        for p in s.encode():
            c.mux(p)
    prepare(d / "clip.mp4", d / "booth", holds=(2,))
    return d / "booth" / "clip_hold2.mp4"


FAST_CAPTURE = ("capture: {stale_s: 0.6, freeze_s: 1.0, backoff_min_s: 0.2, backoff_max_s: 0.5, switch_back_s: 1.0,\n"
                "          probe_every_s: 0.4, open_timeout_s: 4.0}\n"
                "sitting2: {loopsim: {size: [960, 540], camera_fps: 29.0, exp_s: 0.004}}\n")


@pytest.mark.slow
@pytest.mark.qt
@pytest.mark.parametrize("mode", ["thread", "process"])
def test_paused_ipad_falls_back_to_replay_and_returns(tmp_path, booth_hold2, mode):
    clip = str(booth_hold2)
    r = _run_booth(tmp_path, f"live: {{worker_mode: {mode}}}\n"
                             f"booth: {{replay_clip: '{clip}', sim_pause_s: [3.0, 6.5]}}\n"
                             f"camera: {{chain: ['loopsim-pause:{clip}', replay]}}\n" + FAST_CAPTURE, "auto", 15)
    assert r["errors"] == []
    ev = r["source_events"]
    fail = next(e for e in ev if e["event"] == "failed")
    assert fail["key"] == "loopsim" and fail["reason"] == "screen paused", ev
    replay = next(e for e in ev if e["event"] == "activated" and e["key"] == "replay")
    back = [e for e in ev if e["event"] == "activated" and e["key"] == "loopsim" and e["t"] > replay["t"]]
    assert back and "switched back" in back[0]["reason"], ev
    assert r["source"] == "loopsim" and r["last"]["state"] == "live"
    assert r["source_states"].get("replay+paused", 0) > 5          # the fallback said why
    assert {"loopsim", "replay"} <= set(r["pipelines"]) and r["pipelines"]["replay"]["frames_in"] > 5


@pytest.mark.slow
@pytest.mark.qt
def test_paused_ipad_with_one_camera_shows_paused(tmp_path, booth_hold2):
    clip = str(booth_hold2)
    r = _run_booth(tmp_path, f"booth: {{replay_clip: '{clip}', sim_pause_s: [2.0, 6.0], report_events: 3}}\n"
                             f"camera: {{chain: ['loopsim-pause:{clip}']}}\n" + FAST_CAPTURE, "camera", 10)
    assert r["errors"] == []
    states = r["source_states"]
    assert states.get("paused", 0) > 5 and states.get("live", 0) > 5, states
    assert r["last"]["state"] == "live"                  # playing again at the end
    assert len(r["source_events"]) == 3                  # booth.report_events
    assert r["pipelines"]["loopsim"]["frames_duplicate"] > 20
