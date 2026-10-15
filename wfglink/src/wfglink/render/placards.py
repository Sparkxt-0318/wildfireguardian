"""Print-ready A5 placards for the booth (booth/placards/), in Korean and English.

    python scripts/make_placards.py         # writes the PDFs and their PNG previews

- sensor_ko.pdf, sensor_en.pdf: "This is the sensor", for the dashcam stand. The dashcam is
  the kind of camera wfglink reads; what wfglink measures in ordinary video; a pointer to
  the limits card.
- limits_ko.pdf, limits_en.pdf: the five limits (limit_1 to limit_5 of wfglink.ui.i18n,
  read at render time), large enough to read from 1 m.

Drawn with Qt: QPdfWriter at A5 portrait (148 x 210 mm), text as vector with Pretendard
embedded; each PNG preview is drawn by the same code into an image. Black on white only, so
grayscale printers print it as designed; every mark stays at least MARGIN_MM from the edge
(crop-safe). Each card takes the largest type that fits its page, and refuses to render
below MIN_TEXT_MM. Lines break only at spaces, so Korean words stay whole, and a last line
holding one word takes the word before it along.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from wfglink import PROJECT_ROOT

PAGE_MM = (148.0, 210.0)       # A5 portrait
MARGIN_MM = 14.0               # crop-safe margin on every side (at least 8 mm)
MIN_TEXT_MM = 5.0              # smallest body type (em) on a card: about 14 pt, read from 1 m
U = 10.0                       # layout units per mm: fonts take integer pixel sizes, so 0.1 mm steps
LIMIT_KEYS = [f"limit_{k}" for k in range(1, 6)]   # the five booth limits (PLAN.md section 14)
OUT_DIR = PROJECT_ROOT / "booth" / "placards"

# Placard text; the measured quantities and the limits come from wfglink.ui.i18n, so the
# cards name things exactly as the booth screen does.
TEXT: dict[str, dict[str, str]] = {
    "ko": {
        "sensor_title": "이것이 센서입니다",
        "sensor_lead": "거치대 위의 이 블랙박스가 wfglink가 읽는 바로 그 카메라입니다. 특별한 장비 없이, 평범한 영상에서 불티를 잽니다.",
        "measures": "평범한 영상에서 재는 것",
        "tracks": "불티 궤적",
        "pointer": "할 수 없는 것은 ‘{limits}’ 카드에 있습니다.",
    },
    "en": {
        "sensor_title": "This is the sensor",
        "sensor_lead": "The dashcam on this stand is the kind of camera wfglink reads: ordinary video, no special equipment.",
        "measures": "What it measures in ordinary video",
        "tracks": "Ember tracks",
        "pointer": "What it cannot do: see the limits card.",
    },
}


# Layout --------------------------------------------------------------------------------------

def _tokens(text: str) -> list[str]:
    """Words, with every one-character word kept on the line of the word after it: Korean
    "알 수 없습니다" and "약 0.25~0.8초" stay whole, as do "a line" and "8 m/s"."""
    words = text.split()
    out: list[str] = []
    for w in words:
        if out and len(out[-1].rsplit(" ", 1)[-1]) == 1:
            out[-1] = f"{out[-1]} {w}"
        else:
            out.append(w)
    return out


def wrap(text: str, advance: Callable[[str], float], width: float) -> list[str]:
    """Lines of at most `width`, broken at spaces only (a word longer than a line is split
    between characters), never after a one-character word. A last line with a single word
    takes the previous line's last word along when that leaves the previous line at least
    two words."""
    lines: list[list[str]] = []
    cur: list[str] = []
    todo = _tokens(text)
    while todo:
        word = todo.pop(0)
        if advance(" ".join(cur + [word])) <= width:
            cur.append(word)
            continue
        if advance(word) > width and " " in word:     # a glued pair that cannot fit a line: unglue it
            todo[:0] = word.split(" ")
            continue
        if cur:
            lines.append(cur)
        cur = []
        while advance(word) > width:     # only a very long token (a path, a URL) is cut
            k = len(word)
            while k > 1 and advance(word[:k]) > width:
                k -= 1
            lines.append([word[:k]])
            word = word[k:]
        cur = [word]
    if cur:
        lines.append(cur)
    if len(lines) >= 2 and len(lines[-1]) == 1 and len(lines[-2]) >= 3:
        moved = [lines[-2][-1]] + lines[-1]
        if advance(" ".join(moved)) <= width:
            lines[-2], lines[-1] = lines[-2][:-1], moved
    return [" ".join(line) for line in lines]


@dataclass
class Flow:
    """Places text and rules down the page in layout units (0.1 mm). Without a painter it
    only measures, so a card can be laid out at several scales before it is drawn."""
    painter: Any
    x0: float
    width: float
    y: float
    scale: float

    def font(self, size_mm: float, weight: str = "regular"):
        from wfglink.ui.fonts import ui_font

        return ui_font(max(1, round(size_mm * self.scale * U)), weight)

    def text(self, s: str, size_mm: float, weight: str = "regular", gap_mm: float = 0.0, indent_mm: float = 0.0,
             label: str | None = None, label_weight: str = "bold", leading: float = 1.38, bullet: bool = False) -> int:
        """A wrapped paragraph; `label` (a number) or `bullet` sits in the indent on the first line."""
        from PySide6.QtCore import QPointF, Qt
        from PySide6.QtGui import QFontMetricsF

        f = self.font(size_mm, weight)
        fm = QFontMetricsF(f)
        ind = indent_mm * self.scale * U
        lines = wrap(s, fm.horizontalAdvance, self.width - ind)
        step = f.pixelSize() * leading
        if self.painter is not None:
            p = self.painter
            p.setFont(f)
            for i, line in enumerate(lines):
                p.drawText(QPointF(self.x0 + ind, self.y + fm.ascent() + i * step), line)
            if label is not None:
                p.setFont(self.font(size_mm, label_weight))
                p.drawText(QPointF(self.x0, self.y + fm.ascent()), label)
            if bullet:
                r = f.pixelSize() * 0.13
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(Qt.GlobalColor.black)
                p.drawEllipse(QPointF(self.x0 + r * 1.5, self.y + fm.ascent() - f.pixelSize() * 0.33), r, r)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(Qt.GlobalColor.black)
        self.y += fm.ascent() + fm.descent() + (len(lines) - 1) * step + gap_mm * self.scale * U
        return len(lines)

    def rule(self, thickness_mm: float, gap_mm: float) -> None:
        from PySide6.QtCore import QRectF, Qt

        t = thickness_mm * U
        if self.painter is not None:
            self.painter.fillRect(QRectF(self.x0, self.y, self.width, t), Qt.GlobalColor.black)
        self.y += t + gap_mm * self.scale * U

    def space(self, mm: float) -> None:
        self.y += mm * self.scale * U


def _strings(lang: str) -> dict[str, str]:
    from wfglink.ui.i18n import STRINGS

    s = dict(STRINGS[lang])
    s.update(TEXT[lang])
    return s


def _footer(flow: Flow, lang: str) -> None:
    """The wfglink name, small, at the bottom margin."""
    s = _strings(lang)
    flow.text(f"wfglink · {s['subtitle']}", 3.6, "medium")


def _title_size(text: str, width: float, max_mm: float) -> float:
    """The largest title size (mm) up to max_mm at which `text` fits one line."""
    from PySide6.QtGui import QFontMetricsF

    from wfglink.ui.fonts import ui_font

    size = max_mm
    while size > 4.0 and QFontMetricsF(ui_font(round(size * U), "bold")).horizontalAdvance(text) > width:
        size -= 0.2
    return size


def _limits_body(flow: Flow, lang: str) -> None:
    s = _strings(lang)
    flow.text(s["limits_title"], 10.0, "bold", gap_mm=4.0, leading=1.18)
    flow.rule(0.7, 7.0)
    for k, key in enumerate(LIMIT_KEYS, 1):
        flow.text(s[key], 6.2, "regular", gap_mm=6.0 if k < len(LIMIT_KEYS) else 0.0, indent_mm=9.0, label=str(k))


def _sensor_body(flow: Flow, lang: str, title_mm: float) -> None:
    s = _strings(lang)
    flow.text(s["sensor_title"], title_mm / flow.scale, "bold", gap_mm=4.0, leading=1.18)
    flow.rule(1.2, 6.0)
    flow.text(s["sensor_lead"], 5.9, "medium", gap_mm=6.0)
    flow.text(s["measures"], 5.4, "bold", gap_mm=2.5)
    for k, key in enumerate(("tracks", "speed", "count_rate", "cpc", "pnf", "field_legend")):
        flow.text(s[key], 5.6, gap_mm=1.2 if k < 5 else 0.0, indent_mm=5.0, bullet=True)


def _sensor_pointer(flow: Flow, lang: str) -> None:
    s = _strings(lang)
    flow.text(s["pointer"].format(limits=s["limits_title"]), 5.2, "medium")


def draw_card(card: str, lang: str, painter: Any = None) -> dict[str, Any]:
    """Lay out one card and draw it (with a painter scaled to layout units). The body takes
    the largest scale, at most 1.25, at which it fits above the bottom block; the bottom
    block (the pointer on the sensor card, then the footer) sits on the bottom margin."""
    from PySide6.QtGui import QFontMetricsF  # noqa: F401  (Qt must be importable before measuring)

    w_u, h_u, m = PAGE_MM[0] * U, PAGE_MM[1] * U, MARGIN_MM * U
    width = w_u - 2 * m

    def bottom(flow: Flow) -> None:
        if card == "sensor":
            flow.rule(0.35, 4.0)
            _sensor_pointer(flow, lang)
            flow.space(6.0)
        _footer(flow, lang)

    probe = Flow(None, m, width, 0.0, 1.0)
    bottom(probe)
    bottom_h = probe.y
    room = h_u - 2 * m - bottom_h - 8.0 * U
    title_mm = _title_size(_strings(lang)["sensor_title"], width, 15.0) if card == "sensor" else 0.0

    def body(flow: Flow) -> None:
        if card == "sensor":
            _sensor_body(flow, lang, min(title_mm, 15.0 * flow.scale))
        else:
            _limits_body(flow, lang)

    scale = 1.25
    while scale > 0.5:
        probe = Flow(None, m, width, 0.0, scale)
        body(probe)
        if probe.y <= room:
            break
        scale = round(scale - 0.01, 2)
    body_mm = (6.2 if card == "limits" else 5.6) * scale
    if body_mm < MIN_TEXT_MM:
        raise ValueError(f"{card}_{lang}: body type {body_mm:.1f} mm is below {MIN_TEXT_MM} mm; shorten the text")
    if painter is not None:
        from PySide6.QtCore import QRectF, Qt

        painter.fillRect(QRectF(0, 0, w_u, h_u), Qt.GlobalColor.white)
        painter.setPen(Qt.GlobalColor.black)
        body(Flow(painter, m, width, m, scale))
        bottom(Flow(painter, m, width, h_u - m - bottom_h, 1.0))
    return {"card": card, "lang": lang, "scale": scale, "body_mm": round(body_mm, 2)}


def _app():
    if os.environ.get("QT_QPA_PLATFORM") is None:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtGui import QGuiApplication

    from wfglink.ui.fonts import load_fonts

    app = QGuiApplication.instance() or QGuiApplication([])
    load_fonts()
    return app


def write_card(card: str, lang: str, out_dir: str | Path, png_dpi: float = 120.0) -> dict[str, Any]:
    """<card>_<lang>.pdf (A5, vector text, Pretendard embedded) and its <card>_<lang>.png preview."""
    from PySide6.QtCore import QMarginsF
    from PySide6.QtGui import QImage, QPageLayout, QPageSize, QPainter, QPdfWriter

    _app()
    info = draw_card(card, lang, None)      # lays out only: a card that does not fit raises here
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pdf, png = out / f"{card}_{lang}.pdf", out / f"{card}_{lang}.png"
    title = f"wfglink: {_strings(lang)['sensor_title' if card == 'sensor' else 'limits_title']}"
    writer = QPdfWriter(str(pdf))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A5))
    writer.setPageOrientation(QPageLayout.Orientation.Portrait)
    writer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter)
    writer.setResolution(1200)
    writer.setTitle(title)
    writer.setCreator("wfglink (scripts/make_placards.py)")
    w_px, h_px = round(PAGE_MM[0] / 25.4 * png_dpi), round(PAGE_MM[1] / 25.4 * png_dpi)
    img = QImage(w_px, h_px, QImage.Format.Format_RGB32)
    for device, dpi in ((writer, writer.resolution()), (img, png_dpi)):
        p = QPainter(device)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            p.scale(dpi / 25.4 / U, dpi / 25.4 / U)
            draw_card(card, lang, p)
        finally:
            p.end()
    img.convertToFormat(QImage.Format.Format_Grayscale8).save(str(png))
    return {**info, "pdf": str(pdf), "png": str(png)}


def make_placards(out_dir: str | Path = OUT_DIR, langs: tuple[str, ...] = ("ko", "en"),
                  cards: tuple[str, ...] = ("sensor", "limits")) -> list[dict]:
    return [write_card(card, lang, out_dir) for card in cards for lang in langs]
