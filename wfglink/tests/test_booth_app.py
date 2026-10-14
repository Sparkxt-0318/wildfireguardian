"""Booth app: both worker modes run end to end; design rules (contrast, sizes, text, strings)."""
import json
import subprocess
import sys

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


@pytest.mark.slow
@pytest.mark.qt
@pytest.mark.parametrize("mode", ["thread", "process"])
def test_booth_runs_end_to_end(tmp_path, mode):
    cfgfile = tmp_path / "mode.yaml"
    cfgfile.write_text(f"live:\n  worker_mode: {mode}\n")
    report = tmp_path / "r.json"
    res = subprocess.run([sys.executable, "-m", "wfglink", "booth", "--source", "synthetic", "--screen", "primary",
                          "--duration", "6", "--config", str(cfgfile), "--report", str(report)],
                         capture_output=True, text=True, timeout=120,
                         env={**__import__("os").environ, "QT_QPA_PLATFORM": "offscreen"})
    assert res.returncode == 0, res.stderr[-2000:]
    r = json.loads(report.read_text())
    assert r["worker_mode"] == mode
    assert r["errors"] == []
    assert r["frames"] > 20 and r["paints"] > 20
