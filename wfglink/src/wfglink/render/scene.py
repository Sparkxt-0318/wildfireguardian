"""One renderer for the booth screen and the exported overlay video.

paint_scene draws a LiveState with QPainter onto any paint device (the fullscreen widget,
or a QImage for video export), so the booth and the exported videos look identical. It
uses only QImage and QPainter (no QPixmap), so export can run off the GUI thread.

Layout at 1920x1080 (all sizes scale with height):
- video, left, 16:9, with glowing orange ember trails, green field arrows (estimate) and
  the dashed gate line;
- four cards, right: count rate, Cumulative Particle Count (gate), Particle Number Flux
  (projected), ember speed with a direction rose; big green numbers, small qualifying tags;
- a 60 s sparkline under the video and a small status line;
- bands for replay, synthetic or reconnecting sources; the limits card on key I.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPen

from wfglink.ui import theme
from wfglink.ui.fonts import ui_font
from wfglink.ui.i18n import t


@dataclass
class LiveState:
    image: np.ndarray | None = None               # BGR uint8, analysis coordinates
    t: float = 0.0
    detections: np.ndarray = field(default_factory=lambda: np.zeros((0, 2)))
    trails: list[np.ndarray] = field(default_factory=list)   # each (k, 2), newest last
    trail_ages: list[float] = field(default_factory=list)    # seconds since last seen
    count_rate: float | None = None
    cpc_gross: int | None = None
    cpc_net: int | None = None
    pnf: float | None = None
    speed: float | None = None
    direction_deg: float | None = None            # image axes: 0 right, 90 down
    field_uvn: np.ndarray | None = None           # (rows, cols, 3): u, v (px/s), n tracks
    field_min_n: int = 5
    gate: tuple[tuple[float, float], tuple[float, float]] | None = None
    sparkline: np.ndarray = field(default_factory=lambda: np.zeros(0))
    calibrated: bool = False
    distance_m: float | None = None
    source_label: str = ""
    source_state: str = "live"                    # live, replay, synthetic, reconnecting, paused
    fps: float = 0.0
    playback_speed: float | None = None
    warm: float = 1.0                             # 0 to 1: numbers fade in after warm-up
    unprepared: bool = False


def _c(hexcode: str, alpha: float = 1.0) -> QColor:
    c = QColor(hexcode)
    c.setAlphaF(max(0.0, min(1.0, alpha)))
    return c


def _font(size: int, weight: str = "regular", tabular: bool = False) -> QFont:
    f = ui_font(size, weight)
    if tabular:
        try:
            f.setFeature(QFont.Tag("tnum"), 1)
        except Exception:  # older Qt: proportional digits are acceptable
            pass
    return f


def _fmt(v: float | None, kind: str) -> str:
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return ""
    if kind == "int":
        return f"{int(round(v)):,}"
    if kind == "rate":
        return f"{v:.1f}"
    if kind == "flux":
        return f"{v:.2f}" if v < 10 else f"{v:.1f}"
    if kind == "speed_px":
        return f"{v:,.0f}"
    if kind == "speed_m":
        return f"{v:.1f}"
    return f"{v}"


class Layout:
    def __init__(self, W: int, H: int):
        m = theme.px(theme.SIZES["margin"], H)
        self.W, self.H, self.m = W, H, m
        panel_w = int(W * 0.255)
        vid_w = W - panel_w - 3 * m
        vid_h = int(vid_w * 9 / 16)
        if vid_h > H * 0.72:
            vid_h = int(H * 0.72)
            vid_w = int(vid_h * 16 / 9)
        self.video = QRectF(m, m, vid_w, vid_h)
        self.panel = QRectF(W - panel_w - m, m, panel_w, H - 2 * m)
        spark_top = self.video.bottom() + m * 0.9
        self.spark = QRectF(m, spark_top, vid_w, H - spark_top - m * 2.2)
        self.status = QRectF(m, H - m * 1.5, W - 2 * m, m)


def _image_rect(L: Layout, img_w: int, img_h: int) -> tuple[QRectF, float]:
    s = min(L.video.width() / img_w, L.video.height() / img_h)
    w, h = img_w * s, img_h * s
    return QRectF(L.video.x() + (L.video.width() - w) / 2, L.video.y() + (L.video.height() - h) / 2, w, h), s


def paint_scene(p: QPainter, W: int, H: int, s: LiveState, lang: str = "ko", *, show_limits: bool = False,
                show_tracks: bool = True, show_field: bool = True, show_gate: bool = True) -> None:
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    p.fillRect(QRectF(0, 0, W, H), _c(theme.BG))
    L = Layout(W, H)
    _paint_video(p, L, s, lang, show_tracks, show_field, show_gate)
    _paint_cards(p, L, s, lang)
    _paint_sparkline(p, L, s, lang)
    _paint_status(p, L, s, lang)
    if show_limits:
        _paint_limits(p, L, lang)


def _paint_video(p: QPainter, L: Layout, s: LiveState, lang: str, tracks: bool, fieldon: bool, gate: bool) -> None:
    p.fillRect(L.video, _c("#050506"))
    if s.image is None:
        p.setPen(_c(theme.INK2))
        p.setFont(_font(theme.px(34, L.H)))
        p.drawText(L.video, Qt.AlignmentFlag.AlignCenter, t(lang, "warming"))
        return
    ih, iw = s.image.shape[:2]
    rect, sc = _image_rect(L, iw, ih)
    qimg = QImage(s.image.data, iw, ih, s.image.strides[0], QImage.Format.Format_BGR888)
    p.drawImage(rect, qimg)
    ox, oy = rect.x(), rect.y()
    p.save()
    p.setClipRect(rect)
    if fieldon and s.field_uvn is not None:
        _paint_field(p, rect, sc, s)
    if gate and s.gate is not None:
        (x1, y1), (x2, y2) = s.gate
        pen = QPen(_c(theme.INK, 0.75), max(1.5, theme.px(2.5, L.H)))
        pen.setDashPattern([6, 5])
        p.setPen(pen)
        p.drawLine(QPointF(ox + x1 * sc, oy + y1 * sc), QPointF(ox + x2 * sc, oy + y2 * sc))
        p.setFont(_font(theme.px(theme.SIZES["tag"], L.H)))
        p.drawText(QPointF(ox + x2 * sc + 8, oy + y2 * sc + 6), t(lang, "gate"))
    if tracks:
        _paint_trails(p, ox, oy, sc, s, L.H)
    p.restore()
    # Field legend (bottom-left) on a dark pill, so it stays readable over flames.
    if fieldon and s.field_uvn is not None:
        _pill(p, QPointF(rect.x() + 14, rect.bottom() - 14), "→  " + t(lang, "field_legend"), theme.GREEN, L.H, "left")
    # Bands: replay, synthetic, reconnecting, paused.
    band_key = {"replay": "replay", "synthetic": "synthetic"}.get(s.source_state)
    if band_key:
        bh = theme.px(56, L.H)
        band = QRectF(rect.x(), rect.y(), rect.width(), bh)
        p.fillRect(band, _c(theme.BAND, 0.92))
        p.setPen(_c(theme.INK))
        p.setFont(_font(theme.px(theme.SIZES["band"], L.H), "semibold"))
        p.drawText(band, Qt.AlignmentFlag.AlignCenter, t(lang, band_key))
    if s.source_state in ("reconnecting", "paused"):
        p.fillRect(rect, _c("#000000", 0.55))
        p.setPen(_c(theme.INK))
        p.setFont(_font(theme.px(40, L.H), "semibold"))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, t(lang, s.source_state))
    if s.playback_speed and abs(s.playback_speed - 1.0) > 0.05:
        _pill(p, QPointF(rect.right() - 14, rect.bottom() - 14), t(lang, "playback", x=f"{s.playback_speed:.2g}"),
              theme.INK, L.H, "right")


def _pill(p: QPainter, anchor: QPointF, text: str, color: str, H: int, align: str) -> None:
    """Text on a dark rounded pill; anchor is the bottom-left (align left) or bottom-right corner."""
    f = _font(theme.px(theme.SIZES["tag"], H))
    p.setFont(f)
    fm = p.fontMetrics()
    padx, pady = theme.px(12, H), theme.px(6, H)
    w, h = fm.horizontalAdvance(text) + 2 * padx, fm.height() + 2 * pady
    x = anchor.x() if align == "left" else anchor.x() - w
    box = QRectF(x, anchor.y() - h, w, h)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_c("#000000", 0.62))
    p.drawRoundedRect(box, h / 2, h / 2)
    p.setPen(_c(color, 0.95))
    p.drawText(box, Qt.AlignmentFlag.AlignCenter, text)


def _paint_trails(p: QPainter, ox: float, oy: float, sc: float, s: LiveState, H: int) -> None:
    w_glow, w_mid, w_core = theme.px(12, H), theme.px(6, H), max(1.5, theme.px(2.4, H))
    ages = s.trail_ages if len(s.trail_ages) == len(s.trails) else [0.0] * len(s.trails)
    p.setBrush(Qt.BrushStyle.NoBrush)
    for pts, age in zip(s.trails, ages):
        if len(pts) < 2:
            continue
        fade = max(0.0, 1.0 - age / 1.0)
        if fade <= 0:
            continue
        path = QPainterPath(QPointF(ox + pts[0, 0] * sc, oy + pts[0, 1] * sc))
        for x, y in pts[1:]:
            path.lineTo(QPointF(ox + x * sc, oy + y * sc))
        for width, color, alpha in ((w_glow, theme.ORANGE, 0.16), (w_mid, theme.ORANGE, 0.42), (w_core, theme.ORANGE_CORE, 0.95)):
            pen = QPen(_c(color, alpha * fade), width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.drawPath(path)
    # Current detections: a soft orange halo with a bright core.
    r1, r2 = theme.px(9, H), theme.px(3.2, H)
    p.setPen(Qt.PenStyle.NoPen)
    for x, y in s.detections:
        c = QPointF(ox + x * sc, oy + y * sc)
        p.setBrush(_c(theme.ORANGE, 0.28))
        p.drawEllipse(c, r1, r1)
        p.setBrush(_c(theme.ORANGE_CORE, 0.95))
        p.drawEllipse(c, r2, r2)


def _paint_field(p: QPainter, rect: QRectF, sc: float, s: LiveState) -> None:
    uvn = s.field_uvn
    rows, cols = uvn.shape[:2]
    cw, ch = rect.width() / cols, rect.height() / rows
    speeds = np.hypot(uvn[..., 0], uvn[..., 1])
    ok = uvn[..., 2] >= s.field_min_n
    vmax = float(np.nanmax(np.where(ok, speeds, np.nan))) if ok.any() else 0.0
    if not vmax or not np.isfinite(vmax):
        return
    for r in range(rows):
        for c in range(cols):
            if not ok[r, c]:
                continue
            u, v, n = uvn[r, c]
            frac = speeds[r, c] / vmax
            L = 0.42 * min(cw, ch) * max(0.25, frac)
            cx, cy = rect.x() + (c + 0.5) * cw, rect.y() + (r + 0.5) * ch
            ang = math.atan2(v, u)
            alpha = 0.35 if n < 10 else 0.7
            pen = QPen(_c(theme.GREEN, alpha), 2.0)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            x1, y1 = cx - L * math.cos(ang), cy - L * math.sin(ang)
            x2, y2 = cx + L * math.cos(ang), cy + L * math.sin(ang)
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
            head = 0.35 * L
            for da in (2.6, -2.6):
                p.drawLine(QPointF(x2, y2), QPointF(x2 + head * math.cos(ang + da), y2 + head * math.sin(ang + da)))


def _card(p: QPainter, box: QRectF, label: str, value: str, unit: str, tags: list[str], H: int, warm: float) -> None:
    pad = theme.px(6, H)
    p.setPen(_c(theme.INK2))
    p.setFont(_font(theme.px(theme.SIZES["label"], H)))
    p.drawText(QRectF(box.x(), box.y(), box.width(), theme.px(40, H)), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)
    vf = _font(theme.px(theme.SIZES["value"], H), "semibold", tabular=True)
    p.setFont(vf)
    vbox = QRectF(box.x() - pad / 2, box.y() + theme.px(38, H), box.width(), theme.px(122, H))
    if value:
        p.setPen(_c(theme.GREEN, warm))
        p.drawText(vbox, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, value)
        vw = p.fontMetrics().horizontalAdvance(value)
        p.setPen(_c(theme.INK2, warm))
        p.setFont(_font(theme.px(theme.SIZES["unit"], H)))
        p.drawText(QRectF(vbox.x() + vw + theme.px(14, H), vbox.y() + theme.px(46, H), box.width() - vw, theme.px(60, H)),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, unit)
    if tags:
        p.setFont(_font(theme.px(theme.SIZES["tag"], H)))
        p.setPen(_c(theme.INK2))
        p.drawText(QRectF(box.x(), vbox.bottom() - theme.px(4, H), box.width(), theme.px(30, H)),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "  ·  ".join(tags))


def _paint_cards(p: QPainter, L: Layout, s: LiveState, lang: str) -> None:
    H = L.H
    x, y, w = L.panel.x(), L.panel.y(), L.panel.width()
    p.setPen(_c(theme.INK))
    p.setFont(_font(theme.px(theme.SIZES["title"], H), "semibold"))
    p.drawText(QRectF(x, y - theme.px(6, H), w, theme.px(34, H)), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, t(lang, "app"))
    p.setPen(_c(theme.INK2))
    p.setFont(_font(theme.px(theme.SIZES["tag"], H)))
    p.drawText(QRectF(x, y + theme.px(26, H), w, theme.px(28, H)), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, t(lang, "subtitle"))
    top = y + theme.px(78, H)
    card_h = (L.panel.bottom() - top - theme.px(8, H)) / 4
    unc = [] if s.calibrated else [t(lang, "uncalibrated")]
    dist = [t(lang, "at_distance", z=f"{s.distance_m:g}")] if s.calibrated and s.distance_m else []
    cards = [
        (t(lang, "count_rate"), _fmt(s.count_rate, "rate"), t(lang, "per_s"), []),
        (t(lang, "cpc"), _fmt(s.cpc_gross, "int"), t(lang, "count"), []),
        (t(lang, "pnf"), _fmt(s.pnf, "flux"), t(lang, "pnf_unit_m" if s.calibrated else "pnf_unit_px"),
         [t(lang, "projected")] + dist + unc),
        (t(lang, "speed"), _fmt(s.speed, "speed_m" if s.calibrated else "speed_px"),
         t(lang, "speed_unit_m" if s.calibrated else "speed_unit_px"), dist + unc),
    ]
    for i, (label, value, unit, tags) in enumerate(cards):
        box = QRectF(x, top + i * card_h, w, card_h)
        if i:
            p.setPen(QPen(_c(theme.INK3), 1))
            p.drawLine(QPointF(x, box.y() - theme.px(6, H)), QPointF(x + w, box.y() - theme.px(6, H)))
        _card(p, box, label, value if s.warm > 0.02 else "", unit, tags, H, s.warm)
        if i == 3 and s.direction_deg is not None and s.warm > 0.02:
            _paint_rose(p, QPointF(x + w - theme.px(62, H), box.y() + theme.px(98, H)), theme.px(46, H), s.direction_deg, s.warm)
    if s.warm <= 0.02:
        p.setPen(_c(theme.INK2))
        p.setFont(_font(theme.px(theme.SIZES["label"], H)))
        p.drawText(QRectF(x, top + 4 * card_h - theme.px(40, H), w, theme.px(36, H)), Qt.AlignmentFlag.AlignLeft, t(lang, "warming"))


def _paint_rose(p: QPainter, c: QPointF, r: float, deg: float, warm: float) -> None:
    p.setPen(QPen(_c(theme.INK3), 1.5))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(c, r, r)
    for k in range(4):
        a = k * math.pi / 2
        p.drawLine(QPointF(c.x() + 0.82 * r * math.cos(a), c.y() + 0.82 * r * math.sin(a)),
                   QPointF(c.x() + r * math.cos(a), c.y() + r * math.sin(a)))
    a = math.radians(deg)
    tip = QPointF(c.x() + 0.85 * r * math.cos(a), c.y() + 0.85 * r * math.sin(a))
    tail = QPointF(c.x() - 0.55 * r * math.cos(a), c.y() - 0.55 * r * math.sin(a))
    pen = QPen(_c(theme.GREEN, warm), 3.0)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.drawLine(tail, tip)
    for da in (2.5, -2.5):
        p.drawLine(tip, QPointF(tip.x() + 0.32 * r * math.cos(a + da), tip.y() + 0.32 * r * math.sin(a + da)))


def _paint_sparkline(p: QPainter, L: Layout, s: LiveState, lang: str) -> None:
    box = L.spark
    H = L.H
    p.setPen(_c(theme.INK2))
    p.setFont(_font(theme.px(theme.SIZES["tag"], H)))
    p.drawText(QRectF(box.x(), box.y(), box.width(), theme.px(26, H)), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, t(lang, "sparkline"))
    area = QRectF(box.x(), box.y() + theme.px(32, H), box.width(), box.height() - theme.px(32, H))
    p.setPen(QPen(_c(theme.INK3), 1))
    p.drawLine(QPointF(area.x(), area.bottom()), QPointF(area.right(), area.bottom()))
    v = np.asarray(s.sparkline, dtype=float)
    if v.size < 2 or np.isfinite(v).sum() < 2:
        return
    vmax = max(float(np.nanmax(v)), 1e-6) * 1.15
    xs_all = np.linspace(area.x(), area.right(), v.size)
    ok = np.isfinite(v)
    xs, ys = xs_all[ok], area.bottom() - v[ok] / vmax * area.height()
    path = QPainterPath(QPointF(xs[0], ys[0]))
    for x, y in zip(xs[1:], ys[1:]):
        path.lineTo(QPointF(x, y))
    fill = QPainterPath(path)
    fill.lineTo(QPointF(xs[-1], area.bottom()))
    fill.lineTo(QPointF(xs[0], area.bottom()))
    fill.closeSubpath()
    g = QLinearGradient(0, area.y(), 0, area.bottom())
    g.setColorAt(0.0, _c(theme.GREEN, 0.28 * s.warm))
    g.setColorAt(1.0, _c(theme.GREEN, 0.0))
    p.fillPath(fill, QBrush(g))
    pen = QPen(_c(theme.GREEN, s.warm), max(2.0, theme.px(3, H)))
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.drawPath(path)


def _paint_status(p: QPainter, L: Layout, s: LiveState, lang: str) -> None:
    H = L.H
    p.setFont(_font(theme.px(theme.SIZES["status"], H)))
    p.setPen(_c(theme.INK2))
    state = {"live": t(lang, "source_live"), "replay": t(lang, "replay"), "synthetic": t(lang, "synthetic"),
             "reconnecting": t(lang, "reconnecting"), "paused": t(lang, "paused")}.get(s.source_state, s.source_state)
    parts = [s.source_label or "", state, f"{s.fps:.0f} {t(lang, 'fps')}" if s.fps else ""]
    if s.unprepared:
        parts.append(t(lang, "unprepared"))
    p.drawText(L.status, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "   ·   ".join(x for x in parts if x))
    p.drawText(L.status, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
               "L  한국어 / English     I  " + ("한계" if lang == "ko" else "Limits"))


def _paint_limits(p: QPainter, L: Layout, lang: str) -> None:
    H = L.H
    box = QRectF(L.m * 2, L.m * 2, L.W - L.m * 4, L.H - L.m * 4)
    p.fillRect(QRectF(0, 0, L.W, L.H), _c("#000000", 0.72))
    p.fillRect(box, _c("#0E0E10"))
    p.setPen(QPen(_c(theme.INK3), 1))
    p.drawRect(box)
    pad = theme.px(48, H)
    inner = box.adjusted(pad, pad, -pad, -pad)
    col_w = (inner.width() - pad) / 2
    for ci, lg in enumerate(("ko", "en")):
        x = inner.x() + ci * (col_w + pad)
        y = inner.y()
        p.setPen(_c(theme.INK))
        p.setFont(_font(theme.px(theme.SIZES["limits_title"], H), "semibold"))
        p.drawText(QRectF(x, y, col_w, theme.px(56, H)), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, t(lg, "limits_title"))
        y += theme.px(78, H)
        p.setFont(_font(theme.px(theme.SIZES["limits_body"], H)))
        for k in range(1, 7):
            text = f"{k}.  " + t(lg, f"limit_{k}")
            r = p.boundingRect(QRectF(x, y, col_w, 1000), int(Qt.TextFlag.TextWordWrap), text)
            p.setPen(_c(theme.INK if k == 1 else theme.INK, 0.92))
            p.drawText(QRectF(x, y, col_w, r.height()), int(Qt.TextFlag.TextWordWrap), text)
            y += r.height() + theme.px(16, H)
    p.setPen(_c(theme.INK2))
    p.setFont(_font(theme.px(theme.SIZES["tag"], H)))
    p.drawText(QRectF(inner.x(), box.bottom() - pad * 0.9, inner.width(), theme.px(30, H)), Qt.AlignmentFlag.AlignRight, t(lang, "limits_hint"))


def render_image(W: int, H: int, s: LiveState, lang: str = "ko", **kw) -> QImage:
    """Render the scene into a new QImage (export, screenshots, tests)."""
    img = QImage(W, H, QImage.Format.Format_RGB888)
    p = QPainter(img)
    paint_scene(p, W, H, s, lang, **kw)
    p.end()
    return img
