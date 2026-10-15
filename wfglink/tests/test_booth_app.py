"""Booth screen (python -m wfglink live): design rules (contrast, sizes, text, strings), tags and
the Esc prompt, screen choice and monitor hot-plug with fake screens, counts per clip, and end
to end runs on synthetic video and on a playlist of generated clips in both worker modes, with
the keys (Space pause, Esc twice) and the heartbeat.

The booth change of 2026-10-15: key A (raw or analysed, a fade), key M (fire or ember mode),
ember mode's screen (count, per-ember numbers and speeds, labels, camera messages), the
camera permission on the main thread, the engine's camera handling and 50 mode switches
without leaks, and ember mode end to end in both worker modes. Ember mode's analysis is
core's EmberPipeline; these tests use a stand-in (tests/ember_standin.py)."""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest

from wfglink.ui import theme
from wfglink.ui.i18n import STRINGS, limit_keys

HEARTBEAT_KEYS = {"status", "time", "epoch", "pid", "uptime_s", "frames", "paints", "fps", "source", "state", "errors",
                  "last_error", "rss_mb", "clip", "paused", "pipeline", "mode", "raw", "camera_state"}
TESTS = Path(__file__).resolve().parent
STANDIN = "ember_standin:FakeEmberPipeline"
LIMIT_5 = {"ko": "검증은 합성 영상과 타당성 점검으로 했습니다. 실제 화재에서 NIST 장비와 나란히 비교하지는 않았습니다.",
           "en": "Validated on synthetic video and plausibility checks; not side by side with a NIST Emberometer in a real fire."}


def test_strings_complete_and_dash_free():
    assert set(STRINGS["ko"]) == set(STRINGS["en"])
    for lang in STRINGS.values():
        for v in lang.values():
            assert "—" not in v and "–" not in v


def test_no_iphone_or_led_strings_and_five_limits():
    for lang in ("ko", "en"):
        assert limit_keys(lang) == [f"limit_{k}" for k in range(1, 6)]
        assert STRINGS[lang]["limit_5"] == LIMIT_5[lang]
        for key, v in STRINGS[lang].items():
            for word in ("iPad", "iPhone", "Continuity", "LED", "×", "0.5", "replay", "녹화 재생"):
                assert word not in v, (lang, key, word)


def test_ember_mode_strings():
    assert (STRINGS["ko"]["ember_header"], STRINGS["en"]["ember_header"]) == ("당신이 불티입니다", "You are an ember")
    assert STRINGS["ko"]["measured_at"].format(z="2.0") == "2.0 m 거리에서 측정"
    assert STRINGS["en"]["measured_at"].format(z="2.0") == "measured at 2.0 m"
    assert (STRINGS["ko"]["nominal_fov"], STRINGS["en"]["nominal_fov"]) == ("보정 전", "nominal field of view")
    for lang in ("ko", "en"):     # every camera message says what to do, and M is the way back
        for key in ("cam_missing", "cam_denied", "cam_asking", "cam_error"):
            assert STRINGS[lang][key] and STRINGS[lang][key + "_do"]
        assert STRINGS[lang]["back_to_fire"].startswith("M ")


@pytest.mark.parametrize("fg", [theme.INK, theme.INK2, theme.GREEN, theme.ORANGE])
def test_contrast_on_black_meets_wcag_aa(fg):
    assert theme.contrast_ratio(fg, theme.BG) >= 4.5


def test_two_metre_sizes_at_1080p():
    assert theme.px(theme.SIZES["value"], 1080) >= 96
    assert theme.px(theme.SIZES["label"], 1080) >= 28
    assert theme.px(theme.SIZES["tag"], 1080) >= 18
    # Ember mode: the header and each ember's speed read from 2 m; messages as large as card labels.
    assert theme.px(theme.SIZES["ember_header"], 1080) >= 40
    assert theme.px(theme.SIZES["ember_row"], 1080) >= 48
    assert theme.px(theme.SIZES["ember_badge"], 1080) >= 18
    assert theme.px(theme.SIZES["message_title"], 1080) >= 40
    assert theme.px(theme.SIZES["message_body"], 1080) >= 28


def test_the_badge_number_is_readable_on_orange():
    assert theme.contrast_ratio("#000000", theme.ORANGE) >= 4.5


@pytest.mark.qt
def test_card_labels_fit_the_panel():
    from PySide6.QtGui import QFontMetrics, QGuiApplication

    from wfglink.render.scene import Layout
    from wfglink.ui.fonts import ui_font

    QGuiApplication.instance() or QGuiApplication([])
    L = Layout(1920, 1080)
    fm = QFontMetrics(ui_font(theme.px(theme.SIZES["label"], 1080)))
    for lang in ("ko", "en"):
        for key in ("count_rate", "cpc", "pnf", "speed", "ember_count", "ember_speeds"):
            assert fm.horizontalAdvance(STRINGS[lang][key]) <= L.panel.width(), (lang, key)
    head = QFontMetrics(ui_font(theme.px(theme.SIZES["ember_header"], 1080), "semibold"))
    tag = QFontMetrics(ui_font(theme.px(theme.SIZES["tag"], 1080)))
    title = QFontMetrics(ui_font(theme.px(theme.SIZES["message_title"], 1080), "semibold"))
    for lang in ("ko", "en"):
        assert head.horizontalAdvance(STRINGS[lang]["ember_header"]) <= L.panel.width(), lang
        for key in ("ember_subtitle", "ember_sparkline"):
            assert tag.horizontalAdvance(STRINGS[lang][key]) <= L.panel.width(), (lang, key)
        tags = STRINGS[lang]["measured_at"].format(z="2.0") + "  ·  " + STRINGS[lang]["nominal_fov"]
        assert tag.horizontalAdvance(tags) <= L.panel.width(), lang
        for key in ("cam_missing", "cam_denied", "cam_asking", "cam_error"):     # one line each
            assert title.horizontalAdvance(STRINGS[lang][key]) <= L.video.width() * 0.86, (lang, key)


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


# Ember mode and raw or analysed: the screen ----------------------------------------------------

def _ember_state(n: int = 3, **kw):
    """An ember mode state with n tracked phones; the last of several is still being measured."""
    from wfglink.render.scene import LiveState

    embers = [{"id": 10 + k, "n": k + 1, "speed_m_s": None if (n > 1 and k == n - 1) else 0.6 + 0.7 * k,
               "x": 100.0 + 150 * k, "y": 120.0 + 40 * k, "age_s": 2.0} for k in range(n)]
    base = dict(image=np.full((360, 640, 3), 40, np.uint8), mode="ember", embers=embers, ember_count=n, speed_unit="m/s",
                measured_at_m=2.0, calibrated=False, camera_state="ok", source_state="camera",
                source_label="FaceTime HD Camera", speed=0.9, sparkline=np.arange(60, dtype=float) % 4,
                trails=[np.array([[e["x"] - 30, e["y"]], [e["x"], e["y"]]]) for e in embers], trail_ages=[0.0] * n,
                detections=np.array([[e["x"], e["y"]] for e in embers]).reshape(-1, 2))
    base.update(kw)
    return LiveState(**base)


def _rgb(img, box):
    """RGB pixels (int) of a QImage inside a QRectF or (x0, y0, x1, y1)."""
    from PySide6.QtGui import QImage

    if hasattr(box, "x"):
        box = (int(box.x()), int(box.y()), int(box.right()), int(box.bottom()))
    x0, y0, x1, y1 = box
    q = img.convertToFormat(QImage.Format.Format_RGB888)
    arr = np.frombuffer(q.constBits(), np.uint8, count=q.sizeInBytes()).reshape(q.height(), q.bytesPerLine())
    return arr[y0:y1, x0 * 3:x1 * 3].reshape(y1 - y0, x1 - x0, 3).astype(int)


def _near(px, hexcode: str, tol: int = 40) -> int:
    """How many pixels are within tol of a color."""
    c = np.array([int(hexcode[i:i + 2], 16) for i in (1, 3, 5)])
    return int((np.abs(px - c).max(axis=2) <= tol).sum())


@pytest.mark.qt
def test_ember_screen_shows_count_numbers_speeds_and_labels():
    from PySide6.QtGui import QGuiApplication

    from wfglink.render.scene import Layout, ember_panel_layout, render_image

    QGuiApplication.instance() or QGuiApplication([])
    G = ember_panel_layout(Layout(1920, 1080))
    for lang in ("ko", "en"):
        three, none = render_image(1920, 1080, _ember_state(3), lang), render_image(1920, 1080, _ember_state(0), lang)
        assert _near(_rgb(three, G["count"]), theme.GREEN) > 300                       # the live count, in green
        assert np.abs(_rgb(three, G["count"]) - _rgb(none, G["count"])).max() > 100   # 3, not 0
        rows = [_rgb(three, r) for r in G["rows"]]
        for k in (0, 1):                                  # number on an orange disc, speed in green
            assert _near(rows[k], theme.ORANGE) > 300 and _near(rows[k], theme.GREEN) > 300, (lang, k)
        assert _near(rows[2], theme.ORANGE) > 300 and _near(rows[2], theme.GREEN) == 0   # still measuring
        assert all(_near(r, theme.ORANGE) == 0 for r in rows[3:])
        # "measured at 2.0 m" always, "nominal field of view" only without the A4 calibration.
        cal = render_image(1920, 1080, _ember_state(3, calibrated=True), lang)
        tags_unc, tags_cal = _rgb(three, G["tags"]), _rgb(cal, G["tags"])
        assert tags_cal.max() > 100 and np.abs(tags_unc - tags_cal).max() > 100
        w_unc, w_cal = (np.nonzero(t.max(axis=(0, 2)) > 60)[0].max() for t in (tags_unc, tags_cal))
        assert w_unc > w_cal + 40                         # the nominal tag makes the line longer
        # Each phone carries its number and speed on the picture.
        bare = render_image(1920, 1080, _ember_state(3, embers=[]), lang)
        v = Layout(1920, 1080).video
        assert _near(_rgb(three, v), theme.ORANGE, 30) > _near(_rgb(bare, v), theme.ORANGE, 30) + 300
        assert _near(_rgb(three, Layout(1920, 1080).spark), theme.ORANGE, 60) == 0    # the sparkline is a green line
        # A narrow (4:3) screen: the header gets smaller instead of running off the panel.
        small = Layout(1024, 768)
        narrow = render_image(1024, 768, _ember_state(3), lang)
        hdr = ember_panel_layout(small)["header"]
        assert _rgb(narrow, (int(small.panel.right()) + 2, int(hdr.y()) + 4, 1024, int(hdr.bottom()))).max() < 40


@pytest.mark.qt
def test_ember_header_is_in_both_languages():
    """The header reads "당신이 불티입니다 / You are an ember": the screen's language large, the other under it."""
    from PySide6.QtGui import QGuiApplication

    from wfglink.render.scene import Layout, ember_panel_layout, render_image

    QGuiApplication.instance() or QGuiApplication([])
    G = ember_panel_layout(Layout(1920, 1080))
    for lang in ("ko", "en"):
        img = render_image(1920, 1080, _ember_state(2), lang)
        big, other = _rgb(img, G["header"]), _rgb(img, G["header_other"])
        assert big.max() > 200 and other.max() > 100                   # both lines are drawn
        assert big.max() > other.max() or (big > 200).sum() > (other > 200).sum()   # the screen's language leads
    ko, en = render_image(1920, 1080, _ember_state(2), "ko"), render_image(1920, 1080, _ember_state(2), "en")
    assert np.abs(_rgb(ko, G["header"]) - _rgb(en, G["header"])).max() > 100      # L swaps the two


@pytest.mark.qt
def test_ember_screen_shows_the_page_address_and_its_qr_code():
    """booth.ember_page_url set: a QR code of it and the address, bottom-right, away from the picture's centre;
    nothing when the address is empty."""
    import cv2
    from PySide6.QtGui import QGuiApplication

    from wfglink.render.scene import Layout, page_qr_rect, render_image

    QGuiApplication.instance() or QGuiApplication([])
    url = "https://example-user.github.io/ember/"
    L = Layout(1920, 1080)
    q = page_qr_rect(L)
    assert q.right() <= L.spark.right() + 1 and q.top() >= L.video.bottom()       # below the picture, at the right
    for lang in ("ko", "en"):
        with_url = render_image(1920, 1080, _ember_state(3), lang, page_url=url)
        without = render_image(1920, 1080, _ember_state(3), lang, page_url="")
        arr = _rgb(with_url, (0, 0, 1920, 1080)).astype(np.uint8)[..., ::-1].copy()
        assert cv2.QRCodeDetector().detectAndDecode(arr)[0] == url                 # a phone camera reads it
        box = (int(q.x()), int(q.y()), int(q.right()), int(q.bottom()))
        assert (_rgb(with_url, box) > 240).all(axis=2).mean() > 0.4                # a white square ...
        assert (_rgb(without, box) > 240).all(axis=2).mean() < 0.01                # ... only with an address
        assert np.abs(_rgb(with_url, L.video) - _rgb(without, L.video)).max() == 0  # the picture is untouched
        left = (int(L.spark.x()), int(q.y()), int(q.x()) - 4, int(q.bottom()))
        assert np.abs(_rgb(with_url, left) - _rgb(without, left)).max() > 100      # the address and the line
    fire = render_image(1920, 1080, _state(), "ko", page_url=url)                   # fire mode: no QR code
    assert _rgb(fire, (int(q.x()), int(q.y()), int(q.right()), int(q.bottom()))).max() < 250


def test_fire_mode_draws_only_confirmed_tracks():
    """Fire mode's glowing points are the measured positions of confirmed, moving tracks: a faint
    detection that never became a track is not drawn (ui.show_unconfirmed true draws them all).
    The counts are the same either way."""
    from wfglink.config import load_config
    from wfglink.io.frames import Frame
    from wfglink.io.synthetic_live import SyntheticLiveSource
    from wfglink.ui.booth_app import LiveAnalyser, confirmed_points

    src = SyntheticLiveSource(seed=3, realtime=False)
    src.open()
    an_all = LiveAnalyser(load_config(overrides={"ui": {"show_unconfirmed": True}}))
    an_trk = LiveAnalyser(load_config())
    n_all = n_trk = 0
    for i in range(120):
        f = src.read()
        meta = dict(f.meta or {}, clip="synth", item=0, segment=0)
        a = an_all.process(Frame(f.image, f.t, i, f.t_wall, meta))
        b = an_trk.process(Frame(f.image, f.t, i, f.t_wall, dict(meta)))
        assert (a.cpc_gross, a.count_rate, a.speed, len(a.trails)) == (b.cpc_gross, b.count_rate, b.speed, len(b.trails))
        n_all += len(a.detections)
        n_trk += len(b.detections)
        if len(b.detections):                         # every drawn point sits on a confirmed track's measurement
            pts = confirmed_points(an_trk.pipes["synth"], b.t)
            assert np.array_equal(pts, b.detections)
    assert 0 < n_trk < n_all


@pytest.mark.qt
def test_permission_is_asked_without_freezing_the_screen():
    _in_child_qapp("_window_async_permission")


def _window_async_permission():
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from wfglink.ui.booth_app import CameraPermission

    answers = {"status": "not_determined", "sent": 0}

    def send():
        answers["sent"] += 1
        return "not_determined"                       # the dialog is open: the call returns at once

    perm = CameraPermission(True, 5.0, send=send, read=lambda: answers["status"])
    perm.status = "not_determined"
    allowed = []
    win = _window(permission=perm, on_permission=allowed.append)
    _key(win, Qt.Key.Key_M)
    QTest.qWait(300)
    assert answers["sent"] == 1 and win._perm_timer.isActive() and win.camera_state_shown() == "asking"
    assert allowed == []                              # no answer yet, and nothing waited for it
    answers["status"] = "authorized"                  # the visitor clicks Allow
    QTest.qWait(800)
    assert not win._perm_timer.isActive() and allowed == [True] and perm.allowed
    assert win.camera_state_shown() == "starting"
    win.close()


def test_demo_gate_judges_the_key_run_and_the_ember_count():
    from wfglink.ui.demo_gate import KEY_SCRIPT, _healthy, _keys_healthy, ember_over_share, scene_phones

    assert scene_phones({}) == 3
    res = {"errors": [], "frames": 100, "paints": 100, "last": {}, "camera_state": "ok",
           "ember": {"states": 100, "max_count": 4, "speeds": 50, "counts": {"2": 40, "3": 59, "4": 1}}}
    assert ember_over_share(res, 3) == pytest.approx(0.01)
    assert _healthy(res, 10, False, ember=True, phones=3, over_max=0.01)[0]
    res["ember"]["counts"] = {"3": 80, "4": 20}       # a lamp shown as an ember most of the time
    ok, why = _healthy(res, 10, False, ember=True, phones=3, over_max=0.01)
    assert not ok and "more embers than the scene's 3 phones" in why[0]
    pressed = [{"key": "A", "mode": "fire", "raw": True, "paused": False},
               {"key": "A", "mode": "fire", "raw": False, "paused": False},
               {"key": "M", "mode": "ember", "raw": False, "paused": False},
               {"key": "Space", "mode": "ember", "raw": False, "paused": True},
               {"key": "Space", "mode": "ember", "raw": False, "paused": False},
               {"key": "M", "mode": "fire", "raw": False, "paused": False}]
    good = {"keys_pressed": pressed, "modes": {"fire": 50, "ember": 40}, "raw_toggles": 2, "mode_switches": 2,
            "pauses": 2, "mode": "fire", "camera_state": "off", "raw": False, "threads_start": 9, "threads_end": 9}
    assert [k for _, k in KEY_SCRIPT] == [k["key"] for k in pressed] and _keys_healthy(good) == []
    assert _keys_healthy(dict(good, modes={"fire": 50})) and _keys_healthy(dict(good, threads_end=14))
    assert _keys_healthy(dict(good, keys_pressed=pressed[:3]))


@pytest.mark.qt
def test_ember_screen_at_most_six_rows_in_number_order():
    from wfglink.render.scene import ember_rows

    s = _ember_state(0, embers=[{"id": 30 + k, "n": 8 - k, "speed_m_s": 1.0, "x": 10.0, "y": 10.0, "age_s": 1.0}
                                for k in range(8)], ember_count=8)
    assert [e["n"] for e in ember_rows(s)] == [1, 2, 3, 4, 5, 6]


@pytest.mark.qt
def test_raw_picture_is_the_plain_footage_and_the_fade_is_clean():
    from PySide6.QtGui import QGuiApplication

    from wfglink.render.scene import Layout, render_image

    QGuiApplication.instance() or QGuiApplication([])
    L = Layout(1920, 1080)
    field = np.zeros((9, 16, 3))
    field[..., 0], field[..., 2] = 50.0, 12
    marks = dict(trails=[np.array([[100.0, 100.0], [300.0, 200.0]])], trail_ages=[0.0], detections=np.array([[300.0, 200.0]]),
                 gate=((400.0, 20.0), (400.0, 340.0)), field_uvn=field)
    for state in (_state(**marks), _ember_state(3, **marks)):
        full = render_image(1920, 1080, state, "en")
        assert np.array_equal(_rgb(full, (0, 0, 1920, 1080)), _rgb(render_image(1920, 1080, state, "en", analysed=1.0), (0, 0, 1920, 1080)))
        raw = render_image(1920, 1080, state, "en", analysed=0.0)
        plain = render_image(1920, 1080, type(state)(image=state.image, mode=state.mode, camera_state=state.camera_state),
                             "en", analysed=0.0)
        px = _rgb(raw, (0, 0, 1920, 1080))
        assert np.abs(px[300:900, 400:1500] - 40).max() == 0            # the picture alone, fullscreen
        assert np.abs(px[540, 1700] - 40).max() == 0                    # also where the panel was
        assert _near(px, theme.GREEN) == 0 and _near(px, theme.ORANGE) == 0 and _near(px, theme.ORANGE_CORE) == 0
        middle = _rgb(raw, (0, 120, 1920, 960))                         # only the small tags differ from no marks at all
        assert np.array_equal(middle, _rgb(plain, (0, 120, 1920, 960)))
        # Half way: the picture is growing and its marks fade; the panel is already gone (no half-covered numbers).
        half = render_image(1920, 1080, state, "en", analysed=0.5)
        hp = _rgb(half, (0, 0, 1920, 1080))
        assert np.abs(hp - px).max() > 100 and np.abs(hp - _rgb(full, (0, 0, 1920, 1080))).max() > 100
        assert hp[40:1040, 1645:1880].max() < 10                        # panel area, right of the growing picture
        assert _rgb(full, (1645, 40, 1880, 1040)).max() > 100


@pytest.mark.qt
def test_raw_picture_keeps_the_credit_and_the_honesty_tags():
    from PySide6.QtGui import QGuiApplication

    from wfglink.render.scene import render_image

    QGuiApplication.instance() or QGuiApplication([])
    plain = render_image(1920, 1080, _state(source_label="", source_credit=""), "en", analysed=0.0)
    credit = render_image(1920, 1080, _state(), "en", analysed=0.0)
    assert np.abs(_rgb(credit, (1400, 1000, 1920, 1080)) - _rgb(plain, (1400, 1000, 1920, 1080))).max() > 60
    synth = render_image(1920, 1080, _state(source_state="synthetic", source_label="", source_credit=""), "en", analysed=0.0)
    paused = render_image(1920, 1080, _state(source_label="", source_credit=""), "en", analysed=0.0, paused=True)
    for other in (synth, paused):    # the synthetic tag and the pause tag stay; the raw tag moves right
        assert np.abs(_rgb(other, (0, 0, 700, 70)) - _rgb(plain, (0, 0, 700, 70))).max() > 100


@pytest.mark.qt
@pytest.mark.parametrize("cam", ["missing", "denied", "asking", "error"])
def test_camera_messages_replace_the_picture_in_both_languages(cam):
    from PySide6.QtGui import QGuiApplication

    from wfglink.render.scene import Layout, ember_panel_layout, render_image

    QGuiApplication.instance() or QGuiApplication([])
    L = Layout(1920, 1080)
    G = ember_panel_layout(L)
    for lang in ("ko", "en"):
        ok = render_image(1920, 1080, _ember_state(3, source_state="synthetic"), lang)
        msg = render_image(1920, 1080, _ember_state(3, source_state="synthetic", camera_state=cam), lang)
        v = _rgb(msg, L.video)
        assert np.abs(v - _rgb(ok, L.video)).max() > 100
        assert _near(v, theme.ORANGE) == 0 and _near(v, theme.GREEN) == 0     # no marks, no stale values
        assert v[: v.shape[0] // 7].max() < 60                                # calm: nothing at the top (no tags)
        assert v[v.shape[0] // 4: 3 * v.shape[0] // 4].max() > 200            # the message, in the middle
        assert _near(_rgb(msg, G["count"]), theme.GREEN) == 0
        assert all(_near(_rgb(msg, r), theme.ORANGE) == 0 for r in G["rows"])
        assert _rgb(msg, (int(L.status.x()), int(L.status.y()), 900, int(L.status.bottom()))).max() < 60   # no fps line


@pytest.mark.qt
def test_ember_mode_starting_shows_a_quiet_line_and_no_numbers():
    from PySide6.QtGui import QGuiApplication

    from wfglink.render.scene import Layout, LiveState, ember_panel_layout, render_image

    QGuiApplication.instance() or QGuiApplication([])
    L = Layout(1920, 1080)
    img = render_image(1920, 1080, LiveState(mode="ember", camera_state="starting"), "ko")
    v = _rgb(img, L.video)
    assert 60 < v.max() < 200                                     # a gray line, nothing bright
    assert _near(_rgb(img, ember_panel_layout(L)["count"]), theme.GREEN) == 0
    assert _rgb(img, ember_panel_layout(L)["tags"]).max() < 60    # no "uncalibrated (px)" before any value


def test_ember_numbers_are_small_and_steady():
    from wfglink.ui.booth_app import EmberNumbers

    nums = EmberNumbers()

    def n(ids):
        return {e["id"]: e["n"] for e in nums.assign([{"id": i, "age_s": 10.0 - k} for k, i in enumerate(ids)])}

    assert n([57, 60]) == {57: 1, 60: 2}
    assert n([57, 60, 61]) == {57: 1, 60: 2, 61: 3}
    assert n([60, 61]) == {60: 2, 61: 3}                     # 57 left: its number is free
    assert n([60, 61, 70]) == {60: 2, 61: 3, 70: 1}           # the lowest free number
    assert n([]) == {} and n([80]) == {80: 1}


def _phone_cfg(**live):
    from wfglink.config import load_config

    return load_config(overrides={"live": {"ember_pipeline": STANDIN, "camera_start_s": 2.0, "camera_lost_s": 0.4,
                                           "camera_retry_s": [0.05, 0.2], **live}})


def test_ember_analyser_numbers_counts_labels_and_sparkline():
    sys.path.insert(0, str(TESTS))
    from ember_standin import FakeEmberPipeline

    from wfglink.ui.booth_app import EmberAnalyser
    from wfglink.ui.phone_scene import PhoneSceneSource

    src = PhoneSceneSource(width=640, height=360, realtime=False, seed=4)
    src.open()
    an = EmberAnalyser(_phone_cfg(), "camera", FakeEmberPipeline)
    states = [an.process(src.read()) for _ in range(90)]
    s = states[-1]
    assert s.mode == "ember" and s.camera_state == "ok" and s.source_state == "synthetic"
    # A generated scene is named by the status line ("generated phone scene"), not by its source's name.
    assert s.source_label == "" and s.speed_unit == "m/s" and s.measured_at_m == 2.0 and not s.calibrated
    assert 1 <= s.ember_count == len(s.embers) <= 6
    assert sorted(e["n"] for e in s.embers) == list(range(1, len(s.embers) + 1))
    assert all(e["speed_m_s"] is None or 0 <= e["speed_m_s"] < 20 for e in s.embers)
    assert np.isfinite(s.sparkline[-3:]).all() and s.ember_count <= s.sparkline[-1] <= 6   # most embers per second
    assert s.image.shape == (360, 640, 3) and s.image.flags["C_CONTIGUOUS"]
    assert an.counters() == {"key": "ember", "frames_in": 90, "frames_analysed": 90, "frames_duplicate": 0}


# Keys A and M, the camera permission ------------------------------------------------------------
# The window is a QWidget, which needs a QApplication; this pytest process may already hold a
# QGuiApplication from other tests, so each window check runs in a child process.

def _in_child_qapp(fn_name: str, timeout: int = 120) -> None:
    """Run one of this file's _window_* checks in a child process that owns a QApplication."""
    code = ("import sys; sys.path.insert(0, sys.argv[1])\n"
            "from PySide6.QtWidgets import QApplication\napp = QApplication([])\n"
            "import test_booth_app as T\ngetattr(T, sys.argv[2])()\nprint('CHILD OK')\n")
    res = subprocess.run([sys.executable, "-c", code, str(TESTS), fn_name], capture_output=True, text=True, timeout=timeout,
                         env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert res.returncode == 0 and "CHILD OK" in res.stdout, res.stdout[-2000:] + res.stderr[-4000:]


class _Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def _window(**kw):
    from wfglink.ui.booth_app import BoothWindow

    return BoothWindow("ko", 3.0, **kw)


def _key(win, key, repeat=False):
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent

    win.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier, "", repeat))


@pytest.mark.qt
def test_key_a_fades_between_analysed_and_raw():
    _in_child_qapp("_window_key_a")


@pytest.mark.qt
def test_key_m_switches_modes_and_asks_permission_on_the_main_thread():
    _in_child_qapp("_window_key_m")


@pytest.mark.qt
def test_window_survives_fifty_switches_with_two_states():
    _in_child_qapp("_window_fifty_switches")


def _window_key_a():
    from PySide6.QtCore import Qt

    clock = _Clock()
    win = _window(raw_fade_s=0.5, clock=clock)
    assert win.mode == "fire" and win.raw is False and win.analysed_level() == 1.0 and not win.fading()   # starts analysed
    _key(win, Qt.Key.Key_A)
    assert win.raw is True and win.fading() and win._fade_timer.isActive()
    clock.now += 0.25
    assert win.analysed_level() == pytest.approx(0.5)                  # half way through the fade
    clock.now += 0.3
    assert win.analysed_level() == 0.0 and not win.fading()            # raw after about 0.5 s
    win._fade_tick()
    assert not win._fade_timer.isActive()
    _key(win, Qt.Key.Key_A, repeat=True)                               # a held key does nothing
    assert win.raw is True
    _key(win, Qt.Key.Key_A)
    clock.now += 0.1
    assert win.raw is False and win.analysed_level() == pytest.approx(0.2)
    _key(win, Qt.Key.Key_A)                                            # reversed mid-fade: from where it is
    assert win.raw is True and win.analysed_level() == pytest.approx(0.2)
    clock.now += 0.1
    assert win.analysed_level() == 0.0
    instant = _window(raw_fade_s=0.0, clock=clock)
    _key(instant, Qt.Key.Key_A)
    assert instant.analysed_level() == 0.0
    # A acts on the fire footage only: ember mode is always analysed, and the fire footage's
    # choice is kept for when M returns to it.
    assert instant.raw and instant.shown_level() == 0.0
    instant.set_mode("ember")
    assert instant.shown_level() == 1.0 and instant.raw
    toggles = instant.raw_toggles
    _key(instant, Qt.Key.Key_A)
    assert instant.raw and instant.raw_toggles == toggles and instant.shown_level() == 1.0
    instant.set_mode("fire")
    assert instant.shown_level() == 0.0
    for w in (win, instant):
        w.close()


def _window_key_m():
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from wfglink.render.scene import LiveState
    from wfglink.ui.booth_app import CameraPermission

    answers, asked_on = ["denied", "authorized"], []

    def request(timeout_s):
        asked_on.append(threading.current_thread() is threading.main_thread())
        return answers.pop(0)

    perm = CameraPermission(True, 5.0, request)
    modes, allowed, pauses = [], [], []
    win = _window(on_mode=modes.append, permission=perm, on_permission=allowed.append, on_pause=pauses.append)
    win.on_state(LiveState(source_label="clip"))
    assert win.mode == "fire" and win.camera_state_shown() == "off"            # starts in fire mode
    _key(win, Qt.Key.Key_M)
    assert win.mode == "ember" and modes == ["ember"] and win.camera_state_shown() == "asking"
    QTest.qWait(300)                                                          # the ask follows the first paint
    assert asked_on == [True] and perm.status == "denied" and allowed == [False]
    assert win.camera_state_shown() == "denied"
    _key(win, Qt.Key.Key_M, repeat=True)                                      # a held key does nothing
    assert win.mode == "ember"
    _key(win, Qt.Key.Key_M)
    assert win.mode == "fire" and modes == ["ember", "fire"] and win.camera_state_shown() == "off"
    assert win.state.source_label == "clip"                                   # the fire picture is still there
    _key(win, Qt.Key.Key_Space)
    assert win.paused and pauses == [True]
    _key(win, Qt.Key.Key_M)                                                   # a switch ends the pause
    assert win.mode == "ember" and not win.paused and pauses == [True, False]
    QTest.qWait(300)
    assert asked_on == [True, True] and allowed == [False, True] and perm.allowed
    assert win.camera_state_shown() == "starting"                             # until the worker has the camera
    win.set_camera_state("ok")
    assert win.camera_state_shown() == "ok"
    win.set_camera_state("missing")
    assert win.camera_state_shown() == "missing" and win.shown_state().camera_state == "missing"
    win.on_state(LiveState(mode="ember", ember_count=2))
    assert win.state.ember_count == 2 and win.states["fire"].source_label == "clip"
    _key(win, Qt.Key.Key_M)
    _key(win, Qt.Key.Key_M)                                                   # ember mode starts empty again
    assert win.state.ember_count is None and len(win.states) == 2 and asked_on == [True, True]
    win.close()


def test_camera_permission_is_never_asked_off_the_main_thread():
    from wfglink.ui.booth_app import CameraPermission

    perm = CameraPermission(True, 1.0, lambda t: "authorized")
    out = []

    def worker():
        try:
            perm.ask()
        except RuntimeError as exc:
            out.append(str(exc))

    th = threading.Thread(target=worker)
    th.start()
    th.join()
    assert out and "main thread" in out[0] and perm.asks == 0
    assert perm.ask() == "authorized" and perm.asks == 1 and perm.camera_state() is None
    assert perm.ask() == "authorized" and perm.asks == 1                      # decided: not asked again
    assert CameraPermission(False).allowed and CameraPermission(False).ask() == "authorized"   # fake cameras need none
    for status, shown in (("denied", "denied"), ("restricted", "denied"), ("not_determined", "asking")):
        p = CameraPermission(True, 1.0, lambda t, s=status: s)
        p.ask()
        assert not p.allowed and p.camera_state() == shown
    assert CameraPermission(True, 1.0, lambda t: "unsupported").ask() == "unsupported"   # not macOS: capture is tried


# The engine: camera only in ember mode, camera states, 50 switches -------------------------------

@pytest.fixture
def scripted_camera(monkeypatch):
    """make_ember_source returns ScriptedCamera instances (recorded); kw sets their behaviour."""
    sys.path.insert(0, str(TESTS))
    from ember_standin import ScriptedCamera

    from wfglink.ui import booth_app
    from wfglink.ui.phone_scene import PhoneSceneSource

    made, kw = [], {}

    def make(cfg, spec):
        cam = ScriptedCamera(PhoneSceneSource(width=320, height=180, realtime=False, seed=len(made)), **kw)
        made.append(cam)
        return cam

    monkeypatch.setattr(booth_app, "make_ember_source", make)
    return made, kw


def _until(fn, seconds=5.0):
    t_end = time.monotonic() + seconds
    while time.monotonic() < t_end:
        v = fn()
        if v:
            return v
        time.sleep(0.01)
    return fn()


def _steps(engine, mode, seconds=5.0):
    """Step the engine until it gives a state of this mode."""
    def one():
        s = engine.step()
        return s if s is not None and s.mode == mode else None
    return _until(one, seconds)


@pytest.mark.slow
def test_engine_opens_the_camera_only_in_ember_mode_and_holds_playback(scripted_camera):
    sys.path.insert(0, str(TESTS))
    from ember_standin import FakeEmberPipeline

    from wfglink.ui.booth_app import BoothEngine

    made, _ = scripted_camera
    eng = BoothEngine(_phone_cfg(), {"kind": "synthetic"}, {"kind": "camera"}, pipeline_class=FakeEmberPipeline)
    eng.start("fire")
    try:
        assert _steps(eng, "fire") and eng.camera_state() == "off" and not made      # no camera in fire mode
        eng.set_mode("ember")
        s = _steps(eng, "ember")
        assert s is not None and s.source_label == "FaceTime HD Camera" and s.source_state == "camera"
        assert eng.player.paused and len(made) == 1 and made[0].opened == 1 and eng.camera_state() == "ok"
        assert eng.counters()["key"] == "ember"
        eng.set_paused(True)                                                           # Space holds ember mode too
        time.sleep(0.1)
        assert eng.step() is None
        eng.set_paused(False)
        eng.set_mode("fire")
        assert made[0].closed == 1 and not eng.player.paused                           # closed when M returns
        assert _steps(eng, "fire") and eng.counters()["key"] == eng.clip
    finally:
        eng.stop()


@pytest.mark.slow
def test_m_back_to_fire_never_waits_for_a_camera_still_opening(scripted_camera):
    """M while the camera is still opening: the fire picture comes back at once; the camera
    thread ends by itself once its open returns, and stop() waits for it."""
    sys.path.insert(0, str(TESTS))
    from ember_standin import FakeEmberPipeline

    from wfglink.ui.booth_app import BoothEngine

    made, kw = scripted_camera
    kw["open_s"] = 2.0
    eng = BoothEngine(_phone_cfg(), {"kind": "synthetic"}, {"kind": "camera"}, pipeline_class=FakeEmberPipeline)
    eng.start("fire")
    try:
        assert _steps(eng, "fire")
        eng.set_mode("ember")
        eng.step()                                   # the camera thread starts and is opening
        assert _until(lambda: made)
        t0 = time.monotonic()
        eng.set_mode("fire")
        assert time.monotonic() - t0 < 1.0 and _steps(eng, "fire", 2.0)       # no freeze of the fire picture
        assert len(eng.retired) == 1 and eng.retired[0].is_alive()
        assert _until(lambda: not eng.retired[0].is_alive(), 5.0) and made[0].closed == 1
    finally:
        eng.stop()
    assert eng.retired == []


@pytest.mark.slow
def test_engine_camera_states(scripted_camera):
    sys.path.insert(0, str(TESTS))
    from ember_standin import BrokenEmberPipeline, FakeEmberPipeline

    from wfglink.ui.booth_app import BoothEngine

    made, kw = scripted_camera
    allowed = [False]
    eng = BoothEngine(_phone_cfg(), {"kind": "synthetic"}, {"kind": "camera"}, camera_allowed=lambda: allowed[0],
                      pipeline_class=FakeEmberPipeline)
    eng.start("ember")
    try:
        assert eng.step() is None and eng.camera_state() == "off" and not made        # no permission: never opened
        allowed[0] = True
        assert _steps(eng, "ember") and eng.camera_state() == "ok"
        eng.set_mode("fire")
        kw.update(stop_after=5)                                                         # unplugged after 5 frames
        eng.set_mode("ember")
        assert _until(lambda: eng.step() is None and eng.camera_state() == "missing")
        assert _until(lambda: len(made) >= 3)                                           # tried again by itself
        eng.set_mode("fire")
        kw.update(stop_after=None, fail_open=True)                                      # no camera at all
        eng.set_mode("ember")
        assert _until(lambda: eng.step() is None and eng.camera_state() == "missing", 2.0)
        kw.update(fail_open=False)                                                      # plugged in: comes back
        assert _steps(eng, "ember") and eng.camera_state() == "ok"
    finally:
        eng.stop()
    broken = BoothEngine(_phone_cfg(), {"kind": "synthetic"}, {"kind": "camera"}, pipeline_class=BrokenEmberPipeline)
    n = len(made)
    broken.start("ember")
    try:
        assert broken.step() is None and broken.camera_state() == "error" and len(made) == n   # no camera opened
        broken.set_mode("fire")
        assert _steps(broken, "fire") and broken.camera_state() == "off"               # fire mode still works
    finally:
        broken.stop()


@pytest.mark.slow
def test_fifty_mode_switches_leak_no_threads_or_memory(scripted_camera):
    sys.path.insert(0, str(TESTS))
    from ember_standin import FakeEmberPipeline

    from wfglink.ui.booth_app import BoothEngine, rss_mb

    made, _ = scripted_camera
    eng = BoothEngine(_phone_cfg(), {"kind": "synthetic"}, {"kind": "camera"}, pipeline_class=FakeEmberPipeline)
    eng.start("fire")
    try:
        def switch(k):
            eng.set_mode("ember")
            assert _steps(eng, "ember"), k
            eng.set_mode("fire")
            assert _steps(eng, "fire"), k

        for k in range(5):                     # warm up: imports, caches, first allocations
            switch(k)
        threads, mem = threading.active_count(), rss_mb(os.getpid())
        for k in range(50):
            switch(k)
        assert threading.active_count() == threads
        assert not any(t.name == "camera" and t.is_alive() for t in threading.enumerate())
        assert all(c.opened == c.closed == 1 for c in made) and eng.entries == 55
        assert rss_mb(os.getpid()) - mem < 40, (mem, rss_mb(os.getpid()))
    finally:
        eng.stop()


def _window_fifty_switches():
    from PySide6.QtCore import Qt

    from wfglink.render.scene import LiveState

    modes = []
    win = _window(on_mode=modes.append)
    for _ in range(50):
        _key(win, Qt.Key.Key_M)
        win.on_state(LiveState(mode=win.mode))
    assert win.mode == "fire" and len(modes) == 50 and modes[-2:] == ["ember", "fire"]
    assert set(win.states) == {"fire", "ember"} and win.mode_switches == 50
    win.close()


@pytest.mark.qt
def test_screenshots_at_1080p_both_languages_both_modes(tmp_path):
    """Writes the screens to look at (a person or an agent with an image viewer); checks they render."""
    from PySide6.QtGui import QGuiApplication

    from wfglink.render.scene import render_image

    QGuiApplication.instance() or QGuiApplication([])
    sys.path.insert(0, str(TESTS))
    from ember_standin import FakeEmberPipeline

    from wfglink.ui.booth_app import EmberAnalyser
    from wfglink.ui.phone_scene import PhoneSceneSource

    src = PhoneSceneSource(realtime=False, seed=1)
    src.open()
    an = EmberAnalyser(_phone_cfg(), "camera", FakeEmberPipeline)
    for _ in range(100):
        ember = an.process(src.read())
    out = Path(os.environ.get("WFG_SHOTS", tmp_path))
    out.mkdir(parents=True, exist_ok=True)
    for lang in ("ko", "en"):
        for name, s, kw in (("fire", _state(source_state="synthetic"), {}), ("ember", ember, {}),
                            ("fire_raw", _state(), {"analysed": 0.0}), ("ember_fade", ember, {"analysed": 0.5}),
                            ("ember_nocam", type(ember)(mode="ember", camera_state="missing"), {})):
            img = render_image(1920, 1080, s, lang, **kw)
            assert img.width() == 1920 and img.height() == 1080
            assert img.save(str(out / f"{name}_{lang}.png"))


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

def _child_env() -> dict:
    """The environment for child processes: offscreen Qt, and tests/ importable (the ember stand-in)."""
    path = os.pathsep.join(p for p in (str(TESTS), os.environ.get("PYTHONPATH", "")) if p)
    return {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONPATH": path}


def _live(tmp_path: Path, args: list[str], cfg_text: str = "", seconds: float = 8, timeout: int = 240) -> tuple[dict, dict]:
    cfgfile = tmp_path / "run.yaml"
    cfgfile.write_text(cfg_text or "{}\n")
    report, hb = tmp_path / "r.json", tmp_path / "heartbeat.json"
    res = subprocess.run([sys.executable, "-m", "wfglink", "live", *args, "--screen", "primary", "--duration", str(seconds),
                          "--config", str(cfgfile), "--report", str(report), "--heartbeat", str(hb)],
                         capture_output=True, text=True, timeout=timeout, env=_child_env())
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


# Ember mode end to end ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def phone_clip(tmp_path_factory):
    """A recording of the generated phone scene (3 s, 640x360), for --fake-camera."""
    import av

    from wfglink.ui.phone_scene import PhoneSceneSource

    path = tmp_path_factory.mktemp("ember") / "ember_free.mp4"
    src = PhoneSceneSource(width=640, height=360, realtime=False, seed=7)
    src.open()
    with av.open(str(path), "w") as c:
        s = c.add_stream("libx264", rate=30)
        s.width, s.height, s.pix_fmt = 640, 360, "yuv420p"
        for _ in range(90):
            for p in s.encode(av.VideoFrame.from_ndarray(src.read().image, format="bgr24")):
                c.mux(p)
        for p in s.encode():
            c.mux(p)
    return path


def _check_ember_heartbeat(hb: dict) -> None:
    assert HEARTBEAT_KEYS <= set(hb), HEARTBEAT_KEYS - set(hb)
    assert hb["status"] == "clean_exit" and hb["mode"] == "ember" and hb["camera_state"] == "ok" and hb["raw"] is False
    assert hb["pipeline"]["key"] == "ember" and 0 < hb["pipeline"]["frames_analysed"] <= hb["pipeline"]["frames_in"]
    assert hb["frames"] > 0 and hb["paints"] > 0 and hb["errors"] == 0


@pytest.mark.slow
@pytest.mark.qt
@pytest.mark.parametrize("mode,source", [("thread", "synthetic"), ("process", "file")])
def test_live_in_ember_mode(tmp_path, phone_clip, mode, source):
    args = ["--synthetic", "--ember"] + (["--fake-camera", str(phone_clip)] if source == "file" else [])
    r, hb = _live(tmp_path, args, f"live: {{worker_mode: {mode}, ember_pipeline: '{STANDIN}'}}\n", seconds=7)
    assert r["worker_mode"] == mode and r["errors"] == [] and r["mode"] == "ember" and r["ember_source"] == source
    assert set(r["modes"]) == {"ember"} and r["camera_state"] == "ok" and r["permission"] == "authorized"
    assert set(r["states"]) == {"synthetic" if source == "synthetic" else "playing"}     # what the picture is, said
    e = r["ember"]
    assert e["states"] > 20 and 1 <= e["max_count"] <= 6 and e["speeds"] > 0 and e["numbers"][0] == 1
    _check_ember_heartbeat(hb)


MODES = r'''
import json, sys, time
from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
app = QApplication([])
from wfglink.config import load_config
from wfglink.ui.booth_app import BoothWindow, run_live
hb_path, mode = sys.argv[1], sys.argv[2]
cfg = load_config(overrides={"live": {"worker_mode": mode, "ember_pipeline": "ember_standin:FakeEmberPipeline"},
                             "ui": {"quit_confirm_s": 3.0, "raw_fade_s": 0.5}})
marks, pressed = {}, {}
def win():
    return next(w for w in app.topLevelWidgets() if isinstance(w, BoothWindow))
def mark(tag):
    w = win()
    marks[tag] = {"mode": w.mode, "raw": w.raw, "level": w.analysed_level(), "fading": w.fading(),
                  "shown_level": w.shown_level(),
                  "since_a": time.monotonic() - pressed.get("A", 0.0), "fire": w.modes_seen.get("fire", 0),
                  "ember": w.modes_seen.get("ember", 0), "camera": w.camera_state_shown(), "visible": w.isVisible(),
                  "count": w.state.ember_count, "shown": w.state.mode, "prompt": w.quit_prompt(), "t": time.monotonic()}
    try:
        hb = json.load(open(hb_path))
        marks[tag]["hb"] = {k: hb.get(k) for k in ("mode", "raw", "camera_state", "pipeline", "state", "clip")}
    except Exception:
        pass
def key(k, tag):
    if k == Qt.Key.Key_A:
        pressed["A"] = time.monotonic()
    QTest.keyClick(win(), k)
    mark(tag)
def esc2():
    key(Qt.Key.Key_Escape, "esc2")
def esc1():
    key(Qt.Key.Key_Escape, "esc1")
    QTimer.singleShot(300, esc2)
plan = ((0, lambda: mark("start")), (100, lambda: key(Qt.Key.Key_A, "a_down")), (300, lambda: mark("a_mid")),
        (3000, lambda: mark("a_done")), (3100, lambda: key(Qt.Key.Key_A, "a_back")), (4000, lambda: mark("analysed")),
        (4100, lambda: key(Qt.Key.Key_A, "a_raw_again")), (4900, lambda: mark("raw_before_m")),
        (5000, lambda: key(Qt.Key.Key_M, "m_ember")), (11000, lambda: mark("ember")),
        (11100, lambda: key(Qt.Key.Key_A, "ember_a")), (14000, lambda: mark("ember_after_a")),
        (14200, lambda: key(Qt.Key.Key_M, "m_fire")), (16000, lambda: mark("fire_raw")),
        (16100, lambda: key(Qt.Key.Key_A, "fire_a")), (19000, lambda: mark("fire_again")), (19100, esc1))
timers = []
def when_ready():     # the plan starts once the booth shows analysed frames (precise timers keep its order)
    w = next((w for w in app.topLevelWidgets() if isinstance(w, BoothWindow)), None)
    if w is None or w.modes_seen.get("fire", 0) < 3:
        QTimer.singleShot(100, when_ready)
        return
    for ms, fn in plan:
        t = QTimer()
        t.setSingleShot(True)
        t.setTimerType(Qt.TimerType.PreciseTimer)
        t.timeout.connect(fn)
        t.start(ms)
        timers.append(t)
QTimer.singleShot(100, when_ready)
res = run_live(cfg, source={"kind": "synthetic"}, screen="primary", heartbeat=hb_path, duration_s=90,
               ember={"kind": "synthetic"})
res["marks"] = marks
print("RESULT " + json.dumps(res, default=str))
'''


@pytest.mark.slow
@pytest.mark.qt
@pytest.mark.parametrize("mode", ["thread", "process"])
def test_keys_a_and_m_in_the_running_booth(tmp_path, mode):
    hb = tmp_path / "heartbeat.json"
    res = subprocess.run([sys.executable, "-c", MODES, str(hb), mode], capture_output=True, text=True, timeout=300,
                         env=_child_env())
    assert res.returncode == 0, res.stderr[-3000:]
    r = json.loads(res.stdout.split("RESULT ", 1)[1])
    m = r["marks"]
    s = m["start"]                                    # starts in fire mode, analysed
    assert (s["mode"], s["raw"], s["level"], s["camera"]) == ("fire", False, 1.0, "off") and s["fire"] > 0
    assert s["hb"]["mode"] == "fire" and s["hb"]["raw"] is False and s["hb"]["camera_state"] == "off"
    assert m["a_down"]["raw"] and m["a_down"]["fading"]
    mid = m["a_mid"]                                  # the fade runs in about 0.5 s, from wherever it is
    assert mid["level"] == pytest.approx(max(0.0, 1.0 - mid["since_a"] / 0.5), abs=0.1)
    assert mid["fading"] if mid["since_a"] < 0.45 else (mid["since_a"] < 0.55 or not mid["fading"])
    d = m["a_done"]
    assert d["raw"] and d["level"] == 0.0 and not d["fading"] and d["hb"]["raw"] is True
    assert d["fire"] > m["a_down"]["fire"]            # analysis keeps running under the raw picture
    assert m["analysed"]["level"] == 1.0 and not m["analysed"]["raw"]
    assert m["raw_before_m"]["raw"] and m["raw_before_m"]["shown_level"] == 0.0       # the raw fire footage ...
    assert m["m_ember"]["mode"] == "ember" and m["m_ember"]["shown"] == "ember"
    e = m["ember"]                                    # ... and M shows the ember screen analysed all the same
    assert e["ember"] > 10 and e["camera"] == "ok" and e["count"] >= 1 and e["shown_level"] == 1.0
    assert e["hb"]["mode"] == "ember" and e["hb"]["camera_state"] == "ok" and e["hb"]["pipeline"]["key"] == "ember"
    assert e["hb"]["clip"] is None and e["hb"]["state"] == "synthetic"   # ember mode names no fire clip
    ea = m["ember_after_a"]                           # A does nothing in ember mode
    assert ea["mode"] == "ember" and ea["raw"] and ea["shown_level"] == 1.0 and ea["ember"] > e["ember"]
    assert m["m_fire"]["mode"] == "fire" and m["m_fire"]["camera"] == "off"
    fr = m["fire_raw"]                                # the fire footage comes back as it was left: raw
    assert fr["raw"] and fr["shown_level"] == 0.0
    fa = m["fire_again"]
    assert not fa["raw"] and fa["shown_level"] == 1.0 and fa["hb"]["clip"] is not None    # the fire clip is named again
    assert fa["fire"] > m["m_fire"]["fire"] and fa["ember"] - m["m_fire"]["ember"] <= 3   # back on the playlist
    assert r["errors"] == [] and (r["mode_switches"], r["raw_toggles"]) == (2, 4)
    assert r["quit_confirmed"], (m.get("esc1"), m.get("esc2"), r["seconds"])
    assert json.loads(hb.read_text())["status"] == "clean_exit"


NOCAM = r'''
import json, sys
from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
app = QApplication([])
from wfglink.config import load_config
from wfglink.ui.booth_app import BoothWindow, run_live
hb_path, mode, answer = sys.argv[1], sys.argv[2], sys.argv[3]
cfg = load_config(overrides={"live": {"worker_mode": mode, "ember_pipeline": "ember_standin:FakeEmberPipeline",
                                      "camera_start_s": 2.0, "camera_retry_s": [0.2, 1.0]}, "ui": {"quit_confirm_s": 3.0}})
marks = {}
def win():
    return next(w for w in app.topLevelWidgets() if isinstance(w, BoothWindow))
def mark(tag):
    w = win()
    marks[tag] = {"mode": w.mode, "camera": w.camera_state_shown(), "fire": w.modes_seen.get("fire", 0),
                  "ember": w.modes_seen.get("ember", 0)}
    try:
        hb = json.load(open(hb_path))
        marks[tag]["hb"] = {k: hb.get(k) for k in ("mode", "camera_state", "paused")}
    except Exception:
        pass
def key(k, tag):
    QTest.keyClick(win(), k)
    mark(tag)
def esc2():
    key(Qt.Key.Key_Escape, "esc2")
def esc1():
    key(Qt.Key.Key_Escape, "esc1")
    QTimer.singleShot(300, esc2)
plan = ((0, lambda: mark("start")), (100, lambda: key(Qt.Key.Key_M, "m_ember")), (7000, lambda: mark("ember")),
        (7100, lambda: key(Qt.Key.Key_M, "m_fire")), (10000, lambda: mark("fire_again")), (10100, esc1))
timers = []
def when_ready():     # the plan starts once the booth shows analysed frames (precise timers keep its order)
    w = next((w for w in app.topLevelWidgets() if isinstance(w, BoothWindow)), None)
    if w is None or w.modes_seen.get("fire", 0) < 3:
        QTimer.singleShot(100, when_ready)
        return
    for ms, fn in plan:
        t = QTimer()
        t.setSingleShot(True)
        t.setTimerType(Qt.TimerType.PreciseTimer)
        t.timeout.connect(fn)
        t.start(ms)
        timers.append(t)
QTimer.singleShot(100, when_ready)
res = run_live(cfg, source={"kind": "synthetic"}, screen="primary", heartbeat=hb_path, duration_s=90,
               ember={"kind": "camera"}, permission=lambda timeout_s: answer)
res["marks"] = marks
print("RESULT " + json.dumps(res, default=str))
'''


@pytest.mark.slow
@pytest.mark.qt
@pytest.mark.parametrize("mode,answer,shown", [("thread", "unsupported", "missing"), ("process", "unsupported", "missing"),
                                               ("process", "denied", "denied"), ("thread", "not_determined", "asking")])
def test_ember_mode_without_a_camera_or_permission(tmp_path, mode, answer, shown):
    """No camera here (Linux, no camera module or no device): a calm message, and M still returns."""
    hb = tmp_path / "heartbeat.json"
    res = subprocess.run([sys.executable, "-c", NOCAM, str(hb), mode, answer], capture_output=True, text=True,
                         timeout=300, env=_child_env())
    assert res.returncode == 0, res.stderr[-3000:]
    r = json.loads(res.stdout.split("RESULT ", 1)[1])
    m = r["marks"]
    assert m["start"]["mode"] == "fire" and m["start"]["fire"] > 0
    e = m["ember"]
    assert e["mode"] == "ember" and e["camera"] == shown and e["ember"] == 0
    assert e["hb"]["mode"] == "ember" and e["hb"]["camera_state"] == shown and e["hb"]["paused"] is False
    assert m["m_fire"]["camera"] == "off" and m["fire_again"]["fire"] > m["m_fire"]["fire"]   # M returns to the fire footage
    assert r["errors"] == [] and r["permission"] == answer
    assert r["quit_confirmed"], (m.get("esc1"), m.get("esc2"), r["seconds"])
    assert r["permission_asks"] == (1 if answer == "unsupported" else 2)       # at start-up, and again at M while not allowed
