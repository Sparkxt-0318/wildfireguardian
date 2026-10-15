"""Booth screen (python -m wfglink live): design rules (contrast, sizes, text, strings), tags and
the Esc prompt, screen choice and monitor hot-plug with fake screens, counts per clip, and end
to end runs on synthetic video and on a playlist of generated clips in both worker modes, with
the keys (Space pause, Esc twice) and the heartbeat."""
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from wfglink.ui import theme
from wfglink.ui.i18n import STRINGS, limit_keys

HEARTBEAT_KEYS = {"status", "time", "epoch", "pid", "uptime_s", "frames", "paints", "fps", "source", "state", "errors",
                  "last_error", "rss_mb", "clip", "paused", "pipeline"}


def test_strings_complete_and_dash_free():
    assert set(STRINGS["ko"]) == set(STRINGS["en"])
    for lang in STRINGS.values():
        for v in lang.values():
            assert "—" not in v and "–" not in v


def test_no_camera_era_strings_and_five_limits():
    for lang in ("ko", "en"):
        assert limit_keys(lang) == [f"limit_{k}" for k in range(1, 6)]
        for key, v in STRINGS[lang].items():
            for word in ("iPad", "iPhone", "×", "0.5", "replay", "녹화 재생"):
                assert word not in v, (lang, key, word)


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


def _state(**kw):
    from wfglink.render.scene import LiveState

    base = dict(image=np.full((360, 640, 3), 40, np.uint8), count_rate=3.2, cpc_gross=42, pnf=0.8, speed=150.0,
                direction_deg=10.0, sparkline=np.arange(60, dtype=float), source_label="Clip", source_credit="Credit: NIST")
    base.update(kw)
    return LiveState(**base)


def _gray(img, x0, y0, x1, y1):
    from PySide6.QtGui import QImage

    q = img.convertToFormat(QImage.Format.Format_RGB888)
    arr = np.frombuffer(q.constBits(), np.uint8, count=q.sizeInBytes()).reshape(q.height(), q.bytesPerLine())
    return arr[y0:y1, x0 * 3:x1 * 3].astype(int)


@pytest.mark.qt
def test_scene_renders_in_both_languages_with_tags_prompt_and_limits():
    from PySide6.QtGui import QGuiApplication

    from wfglink.render.scene import render_image

    QGuiApplication.instance() or QGuiApplication([])
    for lang in ("ko", "en"):
        for kw in ({}, {"paused": True}, {"quit_prompt": True}, {"show_limits": True}):
            img = render_image(1920, 1080, _state(source_state="synthetic"), lang, **kw)
            assert img.width() == 1920 and not img.isNull()


@pytest.mark.qt
def test_tags_and_prompt_are_drawn_where_expected():
    from PySide6.QtGui import QGuiApplication

    from wfglink.render.scene import Layout, render_image

    QGuiApplication.instance() or QGuiApplication([])
    L = Layout(1920, 1080)
    vx, vy = int(L.video.x()), int(L.video.y())
    corner = (vx + 10, vy + 10, vx + 400, vy + 70)
    cx, cy = int(L.video.center().x()), int(L.video.center().y())
    middle = (cx - 150, cy - 20, cx + 150, cy + 20)
    plain = render_image(1920, 1080, _state(), "en")
    for kw, box in (({"paused": True}, corner), ({"quit_prompt": True}, middle)):
        other = render_image(1920, 1080, _state(), "en", **kw)
        assert np.abs(_gray(other, *box) - _gray(plain, *box)).max() > 100, kw
    synth = render_image(1920, 1080, _state(source_state="synthetic"), "en")
    assert np.abs(_gray(synth, *corner) - _gray(plain, *corner)).max() > 100
    # A playing clip and the field are not tagged: the corner shows the picture only.
    assert np.abs(_gray(plain, *corner) - 40).max() < 30


@pytest.mark.qt
def test_a_long_clip_name_is_cut_before_the_key_hints():
    from PySide6.QtGui import QFontMetrics, QGuiApplication

    from wfglink.render.scene import Layout, render_image
    from wfglink.ui.fonts import ui_font

    QGuiApplication.instance() or QGuiApplication([])
    L = Layout(1920, 1080)
    fm = QFontMetrics(ui_font(theme.px(theme.SIZES["status"], 1080)))
    keys_w = fm.horizontalAdvance("L  한국어 / English     I  Limits")
    img = render_image(1920, 1080, _state(source_label="A very long clip title " * 30), "en")
    right = int(L.status.right() - keys_w)
    gap = _gray(img, right - 32, int(L.status.top()), right - 6, int(L.status.bottom()))
    assert gap.max() < 30                                              # nothing drawn between the two


class _Screen:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name

    def geometry(self):
        return self._name


def test_screen_choice_with_fake_screens():
    from wfglink.ui.booth_app import choose_screen

    builtin, ko_builtin, ext, ext2 = (_Screen("Built-in Retina Display"), _Screen("내장 Retina 디스플레이"),
                                      _Screen("DELL U2720Q"), _Screen("LG HDR 4K"))
    assert choose_screen([builtin, ext], builtin, "auto") is ext                 # external when connected
    assert choose_screen([ext, builtin], ext, "auto") is ext                     # also as the main display
    assert choose_screen([builtin], builtin, "auto") is builtin                  # else the MacBook
    assert choose_screen([ko_builtin, ext], ko_builtin, "auto") is ext           # Korean macOS
    assert choose_screen([_Screen("eDP-1"), _Screen("HDMI-1")], None, None).name() == "HDMI-1"
    assert choose_screen([ext], ext, "auto") is ext                              # lid closed
    a, b = _Screen("A"), _Screen("B")
    assert choose_screen([a, b], a, "auto") is b                                 # unknown names: the second screen
    assert choose_screen([builtin, ext], builtin, "external") is ext
    assert choose_screen([builtin, ext], builtin, "primary") is builtin
    assert choose_screen([builtin, ext, ext2], builtin, "LG HDR 4K") is ext2     # by name
    assert choose_screen([builtin, ext], builtin, "LG HDR 4K") is ext            # named screen absent: auto
    assert choose_screen([builtin, ext], builtin, "auto", builtin=None) is ext


class _Signal:
    def __init__(self):
        self.slots = []

    def connect(self, f):
        self.slots.append(f)

    def emit(self, *a):
        for f in self.slots:
            f(*a)


class _App:
    def __init__(self, screens):
        self.list = list(screens)
        self.screenAdded, self.screenRemoved = _Signal(), _Signal()

    def screens(self):
        return list(self.list)

    def primaryScreen(self):
        return self.list[0]


class _Window:
    def __init__(self):
        self.scr, self.full, self.visible, self.log = None, False, False, []

    def isFullScreen(self):
        return self.full

    def showNormal(self):
        self.full = False
        self.log.append("normal")

    def setScreen(self, s):
        self.scr = s

    def setGeometry(self, g):
        self.geom = g

    def showFullScreen(self):
        self.full = self.visible = True
        self.log.append(self.scr.name())

    def screen(self):
        return self.scr

    def isVisible(self):
        return self.visible

    def hide(self):
        self.visible = self.full = False


def test_the_window_follows_a_monitor_plugged_in_and_out():
    from wfglink.ui.booth_app import ScreenPlacer

    builtin, ext = _Screen("Built-in Retina Display"), _Screen("DELL U2720Q")
    app = _App([builtin])
    win, lim = _Window(), _Window()
    deferred = []
    placer = ScreenPlacer(app, win, "auto", limits=lim, limits_preference="Built-in Retina Display",
                          defer=lambda ms, fn: deferred.append(fn))
    assert win.scr is builtin and win.full and not lim.visible      # one screen: no room for the limits card
    app.list.append(ext)
    app.screenAdded.emit(ext)
    deferred.pop()()                                                 # after the system has rearranged
    assert win.scr is ext and win.log[-2:] == ["normal", "DELL U2720Q"]
    assert lim.visible and lim.scr is builtin                        # the limits card on the MacBook
    app.list.remove(ext)
    app.screenRemoved.emit(ext)
    deferred.pop()()
    assert win.scr is builtin and win.full and not lim.visible
    assert [m["screen"] for m in placer.moves] == ["Built-in Retina Display", "DELL U2720Q", "Built-in Retina Display"]


def test_counts_reset_per_clip_or_run_on_across_loops():
    from wfglink.config import load_config
    from wfglink.io.frames import Frame
    from wfglink.io.synthetic_live import SyntheticLiveSource
    from wfglink.ui.booth_app import LiveAnalyser

    plan = [("A", 0, 0, 20), ("A", 0, 1, 10), ("B", 1, 2, 15), ("A", 2, 3, 15)]   # clip, item, segment, frames

    def run(reset: bool) -> LiveAnalyser:
        src = SyntheticLiveSource(width=320, height=180, realtime=False, seed=2)
        src.open()
        an = LiveAnalyser(load_config(overrides={"booth": {"reset_per_clip": reset}}))
        t = 0.0
        for clip, item, seg, n in plan:
            for _ in range(n):
                f = src.read()
                t += 1 / 30
                s = an.process(Frame(f.image, t, f.index, 0.0, {"clip": clip, "item": item, "segment": seg, "label": f"Clip {clip}",
                                                                 "credit": "Credit: X", "synthetic": False}))
                assert (s.source_label, s.source_credit, s.source_state) == (f"Clip {clip}", "Credit: X", "playing")
            t += 1.0
        return an

    per_clip = run(True)
    assert per_clip.pipes["A"].stats.frames_in == 15 and per_clip.pipes["B"].stats.frames_in == 15
    assert per_clip.active == "A" and per_clip.counters()["key"] == "A"
    across = run(False)
    assert across.pipes["A"].stats.frames_in == 45                   # both segments and the second loop
    assert set(across.counters()) == {"key", "frames_in", "frames_analysed", "frames_duplicate"}


# End to end ------------------------------------------------------------------------------------

def _live(tmp_path: Path, args: list[str], cfg_text: str = "", seconds: float = 8, timeout: int = 240) -> tuple[dict, dict]:
    cfgfile = tmp_path / "run.yaml"
    cfgfile.write_text(cfg_text or "{}\n")
    report, hb = tmp_path / "r.json", tmp_path / "heartbeat.json"
    res = subprocess.run([sys.executable, "-m", "wfglink", "live", *args, "--screen", "primary", "--duration", str(seconds),
                          "--config", str(cfgfile), "--report", str(report), "--heartbeat", str(hb)],
                         capture_output=True, text=True, timeout=timeout, env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert res.returncode == 0, res.stderr[-2000:]
    return json.loads(report.read_text()), json.loads(hb.read_text())


def _check_heartbeat(hb: dict, source: str) -> None:
    assert HEARTBEAT_KEYS <= set(hb), HEARTBEAT_KEYS - set(hb)
    assert hb["status"] == "clean_exit" and hb["source"] == source and hb["paused"] is False
    assert set(hb["pipeline"]) == {"key", "frames_in", "frames_analysed", "frames_duplicate"}
    assert hb["pipeline"]["key"] == hb["clip"]
    assert 0 < hb["pipeline"]["frames_analysed"] <= hb["pipeline"]["frames_in"]
    assert hb["frames"] > 0 and hb["paints"] > 0 and hb["errors"] == 0


@pytest.mark.slow
@pytest.mark.qt
@pytest.mark.parametrize("mode", ["thread", "process"])
def test_live_on_synthetic_video(tmp_path, mode):
    r, hb = _live(tmp_path, ["--synthetic"], f"live: {{worker_mode: {mode}}}\n", seconds=6)
    assert r["worker_mode"] == mode and r["errors"] == [] and r["source"] == "synthetic"
    assert r["frames"] > 20 and r["paints"] > 20
    assert r["states"] == {"synthetic": r["states"]["synthetic"]} and r["clip"] == "synthetic"
    assert r["pipelines"]["synthetic"]["frames_in"] > 20
    _check_heartbeat(hb, "synthetic")
    assert hb["clip"] == "synthetic" and hb["state"] == "synthetic"


@pytest.fixture(scope="module")
def generated_playlist(tmp_path_factory):
    """Two generated 1 s clips with settings files, and a third entry whose file is missing."""
    from wfglink.io.synthetic_live import SyntheticLiveSource
    import av

    d = tmp_path_factory.mktemp("playlist")
    for k, (name, seed) in enumerate((("a", 5), ("b", 6))):
        src = SyntheticLiveSource(width=640, height=360, realtime=False, seed=seed)
        src.open()
        with av.open(str(d / f"{name}.mp4"), "w") as c:
            s = c.add_stream("libx264", rate=30)
            s.width, s.height, s.pix_fmt = 640, 360, "yuv420p"
            for _ in range(45):
                for p in s.encode(av.VideoFrame.from_ndarray(src.read().image, format="bgr24")):
                    c.mux(p)
            for p in s.encode():
                c.mux(p)
        (d / f"{name}.yaml").write_text(f"clip_id: clip_{name}\nfile: {d / f'{name}.mp4'}\nsegments_s: [[0.2, 1.4]]\n"
                                        f"roi: {'[0.0, 0.0, 0.75, 1.0]' if name == 'a' else 'null'}\n")
    (d / "gone.yaml").write_text(f"clip_id: clip_gone\nfile: {d / 'gone.mp4'}\n")
    pl = d / "playlist.yaml"
    pl.write_text(f"clips:\n  - clip: {d / 'a.yaml'}\n    label: Clip A\n  - clip: {d / 'gone.yaml'}\n"
                  f"  - clip: {d / 'b.yaml'}\n    label: Clip B\n")
    return pl


@pytest.mark.slow
@pytest.mark.qt
@pytest.mark.parametrize("mode", ["thread", "process"])
def test_live_on_a_playlist_skips_the_missing_clip(tmp_path, generated_playlist, mode):
    r, hb = _live(tmp_path, ["--playlist", str(generated_playlist)], f"live: {{worker_mode: {mode}}}\n", seconds=9)
    assert r["errors"] == [] and r["source"] == "playlist"
    assert set(r["states"]) == {"playing"}                                         # clips, never synthetic
    assert r["clips"].get("Clip A", 0) > 5 and r["clips"].get("Clip B", 0) > 5
    assert {"clip_a", "clip_b"} <= set(r["pipelines"]) and "clip_gone" not in r["pipelines"]
    ev = r["events"]
    assert any(e["event"] == "skipped" and e["clip"] == "clip_gone" for e in ev), ev
    assert sum(e["event"] == "started" and e["clip"] == "clip_a" for e in ev) >= 2   # it looped
    assert r["playback"]["loops"] >= 1
    _check_heartbeat(hb, "playlist")
    assert hb["clip"] in ("clip_a", "clip_b") and hb["state"] == "playing"


def _start_live(tmp_path: Path, mode: str) -> tuple[subprocess.Popen, Path]:
    """live --synthetic in the background; returns once its heartbeat shows analysed frames."""
    import time

    cfgfile = tmp_path / "run.yaml"
    cfgfile.write_text(f"live: {{worker_mode: {mode}}}\n")
    hb = tmp_path / "heartbeat.json"
    proc = subprocess.Popen([sys.executable, "-m", "wfglink", "live", "--synthetic", "--screen", "primary",
                             "--config", str(cfgfile), "--heartbeat", str(hb)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
                            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    t_end = time.monotonic() + 90
    while time.monotonic() < t_end:
        try:
            d = json.loads(hb.read_text())
            if d["frames"] > 5 and len(d["rss_mb"]) == (2 if mode == "process" else 1):
                return proc, hb
        except (OSError, ValueError, KeyError):
            pass
        time.sleep(0.2)
    proc.kill()
    raise AssertionError("live did not start: " + proc.stderr.read()[-2000:])


def _gone(pid: int, seconds: float) -> bool:
    import time

    t_end = time.monotonic() + seconds
    while time.monotonic() < t_end:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        try:   # an exited process nobody has reaped yet (a container's init may not) counts as gone
            if Path(f"/proc/{pid}/stat").read_text().split()[2] == "Z":
                return True
        except OSError:
            pass
        time.sleep(0.1)
    return False


@pytest.mark.slow
@pytest.mark.qt
@pytest.mark.parametrize("mode", ["thread", "process"])
def test_sigterm_closes_the_app_with_its_worker(tmp_path, mode):
    import signal

    proc, hb = _start_live(tmp_path, mode)
    pids = [int(p) for p in json.loads(hb.read_text())["rss_mb"]]
    proc.send_signal(signal.SIGTERM)
    assert proc.wait(timeout=30) == 1                                   # closed, not a clean exit
    assert json.loads(hb.read_text())["status"] == "closed"
    assert all(_gone(p, 10) for p in pids)


@pytest.mark.slow
@pytest.mark.qt
def test_the_process_worker_stops_when_the_app_is_killed(tmp_path):
    import signal

    proc, hb = _start_live(tmp_path, "process")
    child = next(int(p) for p in json.loads(hb.read_text())["rss_mb"] if int(p) != proc.pid)
    proc.send_signal(signal.SIGKILL)
    proc.wait(timeout=10)
    assert _gone(child, 15)                                             # no orphan decoding video all night


KEYS = r'''
import json, sys
from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
app = QApplication([])
from wfglink.config import load_config
from wfglink.ui.booth_app import BoothWindow, run_live
cfg = load_config(overrides={"live": {"worker_mode": sys.argv[2]}, "ui": {"quit_confirm_s": 1.0}})
marks = {}
def win():
    return next(w for w in app.topLevelWidgets() if isinstance(w, BoothWindow))
def mark(tag):
    w = win()
    marks[tag] = {"states": sum(w.states_seen.values()), "paused": w.paused, "prompt": w.quit_prompt(),
                  "visible": w.isVisible()}
    try:
        marks[tag]["hb_paused"] = json.load(open(sys.argv[1]))["paused"]
    except Exception:
        pass
def key(k, tag):
    QTest.keyClick(win(), k)
    mark(tag)
# The Esc presses are timed from the previous press as it actually happened, so a timer that
# fires late on a loaded machine cannot squeeze the "too late" press into the confirm window.
def esc2():
    key(Qt.Key.Key_Escape, "esc2")
def esc_late():
    key(Qt.Key.Key_Escape, "esc_late")
    QTimer.singleShot(300, esc2)
def esc1():
    key(Qt.Key.Key_Escape, "esc1")
    QTimer.singleShot(1500, esc_late)
for ms, fn in ((5000, lambda: key(Qt.Key.Key_Space, "pause")), (5700, lambda: mark("paused_a")),
               (8000, lambda: mark("paused_b")), (8100, lambda: key(Qt.Key.Key_Space, "resume")), (11000, esc1)):
    QTimer.singleShot(ms, fn)
res = run_live(cfg, source={"kind": "synthetic"}, screen="primary", heartbeat=sys.argv[1], duration_s=40)
res["marks"] = marks
print("RESULT " + json.dumps(res, default=str))
'''


@pytest.mark.slow
@pytest.mark.qt
@pytest.mark.parametrize("mode", ["thread", "process"])
def test_space_pauses_and_esc_twice_quits(tmp_path, mode):
    hb = tmp_path / "heartbeat.json"
    res = subprocess.run([sys.executable, "-c", KEYS, str(hb), mode], capture_output=True, text=True, timeout=240,
                         env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert res.returncode == 0, res.stderr[-2000:]
    r = json.loads(res.stdout.split("RESULT ", 1)[1])
    m = r["marks"]
    assert m["pause"]["paused"] and m["paused_b"]["paused"] and m["paused_b"]["hb_paused"] is True
    assert m["paused_b"]["states"] == m["paused_a"]["states"]          # the picture holds: no new analysis
    # Analysis resumes (at least one new state; a loaded machine may analyse only a few per second).
    assert not m["resume"]["paused"] and m["esc1"]["states"] > m["resume"]["states"]
    assert m["esc1"]["prompt"] and m["esc1"]["visible"]                 # the first Esc only asks
    assert m["esc_late"]["prompt"] and m["esc_late"]["visible"]         # too late: asks again
    assert not m["esc2"]["visible"] and r["quit_confirmed"] and r["pauses"] == 2
    assert json.loads(hb.read_text())["status"] == "clean_exit"
