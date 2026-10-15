"""A5 booth placards: line breaking, the sensor card's text, page size, embedded font and crop-safe margins."""
import re

import cv2
import numpy as np
import pytest

from wfglink import PROJECT_ROOT
from wfglink.render import placards as pl


def _adv(s: str) -> float:
    return float(len(s))      # one unit per character


def test_wrap_breaks_at_spaces_and_keeps_short_words_with_the_next():
    text = "카메라 하나로는 깊이를 알 수 없습니다. 속도와 플럭스는 화면에 투영된 값입니다."
    lines = pl.wrap(text, _adv, 14)
    assert " ".join(lines) == text and all(len(ln) <= 14 for ln in lines)
    words = set(text.split())
    assert all(w in words for ln in lines for w in ln.split())          # no word is cut
    assert not any(ln.endswith((" 알", " 수", "알", "수")) for ln in lines)   # "알 수 없습니다" stays together
    assert "알 수 없습니다." in lines[1]
    # A one-word last line takes the word before it along.
    assert pl.wrap("aaa bbb ccc ddd eee", _adv, 15) == ["aaa bbb ccc", "ddd eee"]
    assert pl.wrap("aa bb", _adv, 2) == ["aa", "bb"]                     # two words: nothing to move
    # Only a token longer than a line is cut; a glued pair that cannot fit is unglued first.
    assert pl.wrap("x " + "y" * 12, _adv, 5) == ["x", "yyyyy", "yyyyy", "yy"]


def test_sensor_card_has_no_led_test():
    """The LED turntable test was dropped (booth change of 2026-10-15): the sensor card says
    what the dashcam is and what wfglink measures, with no LED result line."""
    assert not hasattr(pl, "led_result") and not hasattr(pl, "LED_REPORT")
    for lang in ("ko", "en"):
        text = " ".join(pl.TEXT[lang].values())
        assert "LED" not in text and "턴테이블" not in text and "turntable" not in text.lower()
        assert {"sensor_title", "sensor_lead", "measures", "tracks", "pointer"} <= set(pl.TEXT[lang])


def test_limits_come_from_i18n():
    from wfglink.ui.i18n import STRINGS

    for lang in ("ko", "en"):
        s = pl._strings(lang)
        assert [s[k] for k in pl.LIMIT_KEYS] == [STRINGS[lang][k] for k in pl.LIMIT_KEYS]
    assert pl.LIMIT_KEYS == ["limit_1", "limit_2", "limit_3", "limit_4", "limit_5"]


@pytest.mark.qt
def test_placards_are_print_ready(tmp_path):
    res = pl.make_placards(tmp_path / "out")
    assert [(r["card"], r["lang"]) for r in res] == [("sensor", "ko"), ("sensor", "en"), ("limits", "ko"), ("limits", "en")]
    for r in res:
        assert r["body_mm"] >= pl.MIN_TEXT_MM
        assert "led_line" not in r
        pdf = open(r["pdf"], "rb").read()
        assert pdf.startswith(b"%PDF") and b"/BaseFont /Pretendard" in pdf and len(pdf) < 200_000
        box = [float(v) for v in re.search(rb"/MediaBox \[([\d.\s]+)\]", pdf).group(1).split()]
        assert box[2] / 72 * 25.4 == pytest.approx(148, abs=0.5) and box[3] / 72 * 25.4 == pytest.approx(210, abs=0.5)
        img = cv2.imread(r["png"], cv2.IMREAD_GRAYSCALE)
        h, w = img.shape
        assert (w, h) == (round(148 / 25.4 * 120), round(210 / 25.4 * 120))
        ink = np.argwhere(img < 250)
        px_per_mm = w / 148
        top, left = ink.min(axis=0) / px_per_mm
        bottom, right = (np.array([h, w]) - 1 - ink.max(axis=0)) / px_per_mm
        assert min(top, left, bottom, right) >= 8.0 - 0.5, (r["png"], top, left, bottom, right)
        assert len(np.unique(img)) > 2 and img.max() == 255                 # white paper, black and its antialiasing


@pytest.mark.qt
def test_committed_placards_exist():
    out = PROJECT_ROOT / "booth" / "placards"
    for card in ("sensor", "limits"):
        for lang in ("ko", "en"):
            assert (out / f"{card}_{lang}.pdf").stat().st_size > 1000
            assert cv2.imread(str(out / f"{card}_{lang}.png")) is not None
