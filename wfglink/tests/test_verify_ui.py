"""High-precision mode on screen: the tags in Korean and English, the default screen unchanged, and the
booth drawing only accepted tracks."""
import numpy as np
import pytest

from wfglink.ui.i18n import STRINGS

HP_KEYS = ("hp_mode", "hp_unavailable", "hp_motion", "hp_incomplete", "hp_timebase")


def test_high_precision_strings_exist_in_both_languages_without_dashes():
    for lang in ("ko", "en"):
        for k in HP_KEYS:
            text = STRINGS[lang][k]
            assert text and "\u2014" not in text and "\u2013" not in text, (lang, k)
    assert STRINGS["en"]["hp_mode"].format(m="rules") == "High-precision mode (rules), accepted tracks only"
    assert STRINGS["ko"]["hp_mode"].format(m="rules") == "고정밀 모드 (rules), 검증된 궤적만"
    assert STRINGS["ko"]["hp_motion"] == "카메라 움직임, 판정 보류"
    assert set(STRINGS["ko"]) == set(STRINGS["en"])


@pytest.fixture()
def app(monkeypatch):
    from PySide6.QtGui import QGuiApplication

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    return QGuiApplication.instance() or QGuiApplication([])


def _state(**kw):
    from wfglink.render.scene import LiveState

    img = np.full((180, 320, 3), 30, np.uint8)
    base = dict(image=img, t=5.0, detections=np.array([[50.0, 60.0]]), trails=[np.array([[40.0, 50.0], [50.0, 60.0]])],
                trail_ages=[0.0], count_rate=1.5, cpc_gross=12, cpc_net=4, pnf=0.3, speed=120.0, direction_deg=30.0,
                gate=((200.0, 10.0), (200.0, 170.0)), sparkline=np.arange(60.0) % 3, warm=1.0)
    base.update(kw)
    return LiveState(**base)


def _used(monkeypatch):
    from wfglink.render import scene

    used = []
    translate = scene.t

    def recording(lang, key, **fmt):
        used.append(key)
        text = translate(lang, key, **fmt)
        assert "\u2014" not in text and "\u2013" not in text
        return text

    monkeypatch.setattr(scene, "t", recording)
    return used


@pytest.mark.qt
def test_the_default_live_state_renders_unchanged(app, monkeypatch):
    from wfglink.render import scene

    s = _state()
    assert (s.precision_mode, s.precision_status, s.precision_pending) == ("", "", 0)
    used = _used(monkeypatch)
    calls = []
    real = scene._paint_precision_tags
    monkeypatch.setattr(scene, "_paint_precision_tags", lambda *a, **k: calls.append(1) or real(*a, **k))
    for lang in ("ko", "en"):
        a = scene.render_image(640, 360, s, lang)
        b = scene.render_image(640, 360, _state(precision_mode="", precision_status="", precision_pending=0), lang)
        assert bytes(a.constBits()) == bytes(b.constBits())
    assert not calls and not set(HP_KEYS) & set(used)


LEGACY_SCENE_REF = "8e39d448c8b4"   # the last commit of render/scene.py before high-precision mode


def _legacy_scene(tmp_path, monkeypatch):
    """render/scene.py as it was before high-precision mode (from git), imported beside the current one."""
    import importlib.util
    import shutil
    import subprocess
    import sys

    from wfglink import PROJECT_ROOT

    if shutil.which("git") is None:
        pytest.skip("git is not available")
    res = subprocess.run(["git", "show", f"{LEGACY_SCENE_REF}:./src/wfglink/render/scene.py"], cwd=PROJECT_ROOT,
                         capture_output=True, text=True)
    if res.returncode != 0:
        pytest.skip(f"commit {LEGACY_SCENE_REF} is not in this checkout")
    path = tmp_path / "scene_legacy.py"
    path.write_text(res.stdout, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("wfglink_scene_legacy", path)
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, mod)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.qt
def test_the_default_screen_is_byte_identical_to_the_screen_before_high_precision_mode(app, monkeypatch, tmp_path):
    from wfglink.render import scene

    legacy = _legacy_scene(tmp_path, monkeypatch)
    assert not hasattr(legacy.LiveState(), "precision_mode")
    variants = [{}, {"metrics_scope": "tracking_only"}, {"count_rate": None, "cpc_gross": None, "trails": []}]
    for lang in ("ko", "en"):
        for extra in variants:
            for kw in ({}, {"analysed": 0.0}):
                kwargs = dict(_state().__dict__, **extra)
                kwargs = {k: v for k, v in kwargs.items() if not k.startswith("precision_")}
                now = scene.render_image(640, 360, scene.LiveState(**kwargs), lang, **kw)
                before = legacy.render_image(640, 360, legacy.LiveState(**kwargs), lang, **kw)
                assert bytes(now.constBits()) == bytes(before.constBits()), (lang, extra, kw)


@pytest.mark.qt
@pytest.mark.parametrize("lang", ["ko", "en"])
def test_high_precision_tags_show_the_method_and_why_decisions_wait(app, monkeypatch, lang):
    from wfglink.render import scene

    plain = bytes(scene.render_image(640, 360, _state(), lang).constBits())
    used = _used(monkeypatch)
    hp = scene.render_image(640, 360, _state(precision_mode="rules"), lang)
    assert bytes(hp.constBits()) != plain and "hp_mode" in used
    for status, key in (("unavailable", "hp_unavailable"), ("camera_motion", "hp_motion"),
                        ("incomplete", "hp_incomplete"), ("not_real_time", "hp_timebase")):
        used.clear()
        img = scene.render_image(640, 360, _state(precision_mode="patch", precision_status=status), lang)
        assert used.count("hp_mode") == 1 and key in used and bytes(img.constBits()) != plain
    used.clear()
    # The raw picture (key A) shows no high-precision tag.
    raw_hp = scene.render_image(640, 360, _state(precision_mode="rules", precision_status="camera_motion"), lang,
                                analysed=0.0)
    raw = scene.render_image(640, 360, _state(), lang, analysed=0.0)
    assert bytes(raw_hp.constBits()) == bytes(raw.constBits()) and "hp_mode" not in used
    # Tracking-only clips keep their own panel and still say why nothing is decided.
    used.clear()
    scene.render_image(640, 360, _state(precision_mode="rules", precision_status="not_real_time",
                                        metrics_scope="tracking_only"), lang)
    assert "hp_timebase" in used and "tracking_only" in used


def test_the_booth_draws_only_accepted_tracks_in_high_precision_mode():
    from wfglink.config import load_config
    from wfglink.io.frames import Frame
    from wfglink.io.synthetic_live import SyntheticLiveSource
    from wfglink.ui.booth_app import LiveAnalyser, confirmed_points
    from wfglink.verify.config import hp_config

    rules = {"lower": {"speed_med": 1e6}, "iqr": {"speed_med": 1.0}}       # nothing passes
    src = SyntheticLiveSource(width=480, height=270, seed=3, realtime=False)
    src.open()
    plain = LiveAnalyser(load_config())
    ctrl = LiveAnalyser(hp_config("accept_all", local=False))
    strict = LiveAnalyser(hp_config("rules", overrides={"verify": {"rules": {"thresholds": {"live_downscaled": rules}}}}))
    drawn = {"plain": 0, "ctrl": 0, "strict": 0}
    for i in range(90):
        f = src.read()
        meta = dict(f.meta or {}, clip="synth", item=0, segment=0)
        a = plain.process(Frame(f.image, f.t, i, f.t_wall, dict(meta)))
        b = ctrl.process(Frame(f.image, f.t, i, f.t_wall, dict(meta)))
        c = strict.process(Frame(f.image, f.t, i, f.t_wall, dict(meta)))
        obs = ctrl.pipes["synth"].observer
        assert np.array_equal(b.detections, obs.accepted_points(b.t))
        assert np.array_equal(confirmed_points(plain.pipes["synth"], a.t), a.detections)
        assert b.precision_mode == "accept_all" and c.precision_mode == "rules" and a.precision_mode == ""
        assert len(c.detections) == 0 and c.cpc_gross in (0, None) and c.trails == []
        drawn["plain"] += len(a.detections)
        drawn["ctrl"] += len(b.detections)
        drawn["strict"] += len(c.detections)
    assert plain.pipes["synth"].observer is None
    assert drawn["ctrl"] > 0 and drawn["strict"] == 0
