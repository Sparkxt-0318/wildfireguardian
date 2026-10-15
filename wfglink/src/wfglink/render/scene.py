"""One renderer for the booth screen and the exported overlay video.

paint_scene draws a LiveState with QPainter onto any paint device (the fullscreen widget,
or a QImage for video export), so the booth and the exported videos look identical. It
uses only QImage and QPainter (no QPixmap), so export can run off the GUI thread.

Layout at 1920x1080 (all sizes scale with height):
- video, left, 16:9, with glowing orange ember trails, green field arrows (estimate) and
  the dashed gate line;
- four cards, right: count rate, Cumulative Particle Count (gate), Particle Number Flux
  (projected), ember speed with a direction rose; big green numbers, small qualifying tags;
- a 60 s sparkline under the video and a small status line (clip name, credit line, what
  the picture is, analysis fps);
- small tags on the video: "synthetic video" when the picture is generated, "paused" while
  playback is paused; a visible prompt after the first Esc; the limits card on key I.

Ember mode (state.mode "ember", "Become an ember", key M): the same design on the live
camera. The panel has the header "당신이 불티입니다 / You are an ember" in both languages (the
screen's language large, the other under it), the live count of
embers (phones showing the ember page) and each ember's speed with its number, in m/s with
the distance that holds ("measured at 2.0 m") and a small "nominal field of view" tag until
an A4 calibration exists. Each ember on the picture carries the same number and speed; the
wind arrows come from all tracked phones and are labelled as an estimate, as in fire mode.
While the camera is missing, not allowed or failing (state.camera_state), the picture area
shows a calm message in both languages with what to do, and that M returns to the fire
footage. With page_url (booth.ember_page_url), the bottom-right of the sparkline row holds a
QR code of the ember page's address with the address, small, and "휴대폰으로 열어 보세요 · Open
on your phone"; the sparkline gives it the room. Nothing shows when the address is empty.

Raw or analysed (key A): analysed=1 draws the full screen above; analysed=0 draws the raw
picture alone, fullscreen, with only a small "raw footage" tag (plus the synthetic and
paused tags, and the clip's credit line bottom-right). Values in between are the fade: the
picture grows from its place to the whole screen while the marks on it fade out; the panel,
sparkline, status line and legend fade in the analysed half of the fade and the raw tags in
the raw half, so the two never show at once.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QImage, QLinearGradient, QPainter, QPainterPath, QPen

from wfglink.ui import theme
from wfglink.ui.fonts import ui_font
from wfglink.ui.i18n import limit_keys, t

# Ember mode camera states that replace the picture with a message (the title key; "<key>_do"
# says what to do). "starting" shows a small line instead; "ok" shows the picture.
CAMERA_MESSAGES = {"missing": "cam_missing", "denied": "cam_denied", "asking": "cam_asking", "error": "cam_error"}
MAX_EMBER_ROWS = 6
FADE_EPS = 0.004         # an overlay this faint (or this close to full) is not drawn (or drawn in full)


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
    field_uvn: np.ndarray | None = None           # (rows, cols, 3): u, v (px/s, or m/s in ember mode), n tracks
    field_min_n: int = 5
    gate: tuple[tuple[float, float], tuple[float, float]] | None = None
    sparkline: np.ndarray = field(default_factory=lambda: np.zeros(0))
    calibrated: bool = False                      # fire: m/px given; ember: an A4 calibration exists (else the nominal field of view)
    distance_m: float | None = None
    source_label: str = ""                        # the clip's name (booth), file name (file mode) or camera name (ember mode)
    source_credit: str = ""                       # the clip's credit line (data/clips.csv)
    source_state: str = "playing"                 # playing (a clip analysed live), synthetic, file (file mode), camera (ember mode)
    fps: float = 0.0
    warm: float = 1.0                             # 0 to 1: numbers fade in after warm-up
    # Ember mode ("Become an ember"); fire mode keeps these defaults.
    mode: str = "fire"                            # fire (clips or synthetic fire video) or ember (the camera)
    embers: list[dict] = field(default_factory=list)   # {"id", "speed_m_s" (or None), "x", "y" (image px), "age_s"}; the booth adds "n", the number shown
    ember_count: int | None = None                # phones tracked now (ember mode)
    ember_max: int | None = None                  # ember mode: at most this many phones are tracked (ember.max_tracks)
    speed_unit: str = "px/s"                      # unit of speed and of the per-ember speeds: px/s or m/s
    measured_at_m: float | None = None            # ember mode: speeds in m/s hold at this distance (ember.distance_m)
    camera_state: str = "off"                     # off (fire mode), starting, ok, missing, denied, asking, error


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


def _ease(a: float) -> float:
    """Smoothstep of a fade position (0 to 1), so the fade starts and ends gently."""
    a = min(1.0, max(0.0, float(a)))
    return a * a * (3.0 - 2.0 * a)


def _lerp_rect(r0: QRectF, r1: QRectF, f: float) -> QRectF:
    return QRectF(r0.x() + (r1.x() - r0.x()) * f, r0.y() + (r1.y() - r0.y()) * f,
                  r0.width() + (r1.width() - r0.width()) * f, r0.height() + (r1.height() - r0.height()) * f)


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
        self.full = QRectF(0, 0, W, H)               # the picture alone (raw)
        self.panel = QRectF(W - panel_w - m, m, panel_w, H - 2 * m)
        spark_top = self.video.bottom() + m * 0.9
        self.spark = QRectF(m, spark_top, vid_w, H - spark_top - m * 2.2)
        self.status = QRectF(m, H - m * 1.5, W - 2 * m, m)


def _fit_rect(box: QRectF, img_w: int, img_h: int) -> tuple[QRectF, float]:
    """The largest rectangle of the image's aspect ratio centred in box, and its scale."""
    s = min(box.width() / img_w, box.height() / img_h)
    w, h = img_w * s, img_h * s
    return QRectF(box.x() + (box.width() - w) / 2, box.y() + (box.height() - h) / 2, w, h), s


def paint_scene(p: QPainter, W: int, H: int, s: LiveState, lang: str = "ko", *, show_limits: bool = False,
                show_tracks: bool = True, show_field: bool = True, show_gate: bool = True,
                paused: bool = False, quit_prompt: bool = False, analysed: float = 1.0, page_url: str = "") -> None:
    """Draw the whole screen. paused adds the pause tag; quit_prompt shows the Esc confirm prompt;
    analysed is 1 for the analysed screen, 0 for the raw picture and in between during the fade;
    page_url, in ember mode, adds the ember page's QR code and address (see the module docstring)."""
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    p.fillRect(QRectF(0, 0, W, H), _c(theme.BG))
    L = Layout(W, H)
    level = min(1.0, max(0.0, float(analysed)))
    a = _ease(level)                              # the picture's size and the marks on it
    panel = _ease(2.0 * level - 1.0)              # panel, sparkline, status line, legend: the analysed half
    raw = _ease(1.0 - 2.0 * level)                # the raw tags: the raw half
    if panel > FADE_EPS:
        p.setOpacity(panel)
        spark = L.spark
        if s.mode == "ember":
            _paint_ember_panel(p, L, s, lang)
            url = str(page_url or "").strip()
            if url:
                spark = _paint_page_qr(p, L, url, lang)
        else:
            _paint_cards(p, L, s, lang)
        _paint_sparkline(p, L, s, lang, spark)
        _paint_status(p, L, s, lang)
        p.setOpacity(1.0)
    rect = _paint_video(p, L, s, lang, show_tracks, show_field, show_gate, a, panel)
    _paint_tags(p, L, rect, s, lang, paused, raw)
    if quit_prompt:
        _paint_prompt(p, rect, t(lang, "quit_confirm"), L.H)
    if show_limits:
        _paint_limits(p, L, lang)


def _ember_live(s: LiveState) -> bool:
    """Ember mode shows a camera picture (not a message, not the start)."""
    return s.camera_state not in CAMERA_MESSAGES and s.image is not None


def _paint_video(p: QPainter, L: Layout, s: LiveState, lang: str, tracks: bool, fieldon: bool, gate: bool,
                 a: float = 1.0, legend: float = 1.0) -> QRectF:
    """The picture with its marks (faded by a, the eased analysed level; the field legend by
    legend); returns the rectangle it fills."""
    box = _lerp_rect(L.video, L.full, 1.0 - a) if a < 1.0 - FADE_EPS else QRectF(L.video)
    p.fillRect(box, _c("#050506", a))
    ember = s.mode == "ember"
    if ember and s.camera_state in CAMERA_MESSAGES:
        _paint_camera_message(p, box, s.camera_state, lang, L.H)
        return QRectF(box)
    if s.image is None:
        p.setPen(_c(theme.INK2))
        p.setFont(_font(theme.px(34, L.H)))
        p.drawText(box, Qt.AlignmentFlag.AlignCenter, t(lang, "cam_starting" if ember else "warming"))
        return QRectF(box)
    img = s.image if s.image.flags["C_CONTIGUOUS"] else np.ascontiguousarray(s.image)   # decoders pad odd widths
    ih, iw = img.shape[:2]
    rect, sc = _fit_rect(box, iw, ih)
    qimg = QImage(img.data, iw, ih, img.strides[0], QImage.Format.Format_BGR888)
    p.drawImage(rect, qimg)
    if a <= FADE_EPS:
        return rect
    ox, oy = rect.x(), rect.y()
    p.save()
    p.setClipRect(rect)
    p.setOpacity(a)
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
        if ember:
            _paint_ember_labels(p, rect, sc, s, lang, L.H)
    p.restore()
    # Field legend (bottom-left) on a dark pill, so it stays readable over flames.
    if fieldon and s.field_uvn is not None and legend > FADE_EPS:
        p.setOpacity(legend)
        _pill(p, QPointF(rect.x() + 14, rect.bottom() - 14), "→  " + t(lang, "field_legend"), theme.GREEN, L.H, "left")
        p.setOpacity(1.0)
    return rect


def page_qr_rect(L: Layout) -> QRectF:
    """Where ember mode puts the page's QR code: the bottom-right of the sparkline row."""
    side = min(L.spark.height() - theme.px(6, L.H), theme.px(220, L.H))
    return QRectF(L.spark.right() - side, L.spark.bottom() - side, side, side)


def _paint_page_qr(p: QPainter, L: Layout, url: str, lang: str) -> QRectF:
    """The ember page's QR code with its address and a short ko/en line to its left; returns the
    room left for the sparkline."""
    from wfglink.render.qr import draw_qr

    q = page_qr_rect(L)
    try:
        draw_qr(p, q.x(), q.y(), q.width(), url)
    except ValueError:              # an address too long for a QR code: the address alone
        q = QRectF(L.spark.right(), q.y(), 0, q.height())
    gap = theme.px(22, L.H)
    right = q.x() - gap
    room = max(0.0, min(L.spark.width() * 0.45, right - L.spark.x()))
    right_al = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
    line_f = _font(theme.px(theme.SIZES["tag"], L.H), "semibold")
    url_f = _font(theme.px(18, L.H))
    p.setFont(url_f)
    shown = url
    while len(shown) > 8 and p.fontMetrics().horizontalAdvance(shown) > room:   # long: smaller, then cut in the middle
        if url_f.pixelSize() > theme.px(14, L.H):
            url_f = _font(url_f.pixelSize() - 1)
            p.setFont(url_f)
            continue
        shown = p.fontMetrics().elidedText(url, Qt.TextElideMode.ElideMiddle, int(room))
        break
    h1, h2 = theme.px(30, L.H), theme.px(26, L.H)
    y = q.center().y() - (h1 + h2) / 2
    p.setFont(line_f)
    p.setPen(_c(theme.INK))
    p.drawText(QRectF(right - room, y, room, h1), right_al, t(lang, "ember_page_line"))
    p.setFont(url_f)
    p.setPen(_c(theme.INK2))
    p.drawText(QRectF(right - room, y + h1, room, h2), right_al, shown)
    p.setFont(line_f)
    used = max(p.fontMetrics().horizontalAdvance(t(lang, "ember_page_line")),
               QFontMetricsF(url_f).horizontalAdvance(shown))
    left = right - min(room, used) - gap
    return QRectF(L.spark.x(), L.spark.y(), max(0.0, left - L.spark.x()), L.spark.height())


def _paint_tags(p: QPainter, L: Layout, rect: QRectF, s: LiveState, lang: str, paused: bool, raw: float = 0.0) -> None:
    """Small tags in the picture's top-left corner: synthetic video, paused, and (fading in with the
    raw picture, by raw) raw footage; in the raw picture the clip's name and its credit line sit
    bottom-right, each on its own pill (the credit line at the bottom, never cut first)."""
    picture = s.mode != "ember" or s.camera_state not in CAMERA_MESSAGES
    tags = ([t(lang, "ember_synthetic" if s.mode == "ember" else "synthetic")] if s.source_state == "synthetic" and picture else []) + ([t(lang, "paused")] if paused else [])
    x, y = rect.x() + theme.px(14, L.H), rect.y() + theme.px(14, L.H)
    for text in tags:
        x += _pill(p, QPointF(x, y), text, theme.INK, L.H, "left", top=True) + theme.px(10, L.H)
    if raw <= FADE_EPS or not picture:
        return
    p.setOpacity(raw)
    _pill(p, QPointF(x, y), t(lang, "raw"), theme.INK, L.H, "left", top=True)
    lines = [v for v in (s.source_label, s.source_credit) if v] if s.mode != "ember" else []
    yb = rect.bottom() - theme.px(14, L.H)
    for text in reversed(lines):          # the credit line at the bottom, the clip's name above it
        p.setFont(_font(theme.px(theme.SIZES["tag"], L.H)))
        room = int(rect.width() * 0.9) - 2 * theme.px(12, L.H)
        text = p.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, max(room, 0))
        _pill(p, QPointF(rect.right() - theme.px(14, L.H), yb), text, theme.INK2, L.H, "right")
        yb -= p.fontMetrics().height() + 2 * theme.px(6, L.H) + theme.px(8, L.H)
    p.setOpacity(1.0)


def _paint_prompt(p: QPainter, rect: QRectF, text: str, H: int) -> None:
    """A clearly visible prompt in the middle of the picture (the Esc confirm)."""
    p.setFont(_font(theme.px(theme.SIZES["label"], H), "semibold"))
    fm = p.fontMetrics()
    padx, pady = theme.px(36, H), theme.px(22, H)
    w, h = fm.horizontalAdvance(text) + 2 * padx, fm.height() + 2 * pady
    box = QRectF(rect.center().x() - w / 2, rect.center().y() - h / 2, w, h)
    p.setPen(QPen(_c(theme.INK, 0.9), max(1.5, theme.px(2, H))))
    p.setBrush(_c("#000000", 0.82))
    p.drawRoundedRect(box, theme.px(14, H), theme.px(14, H))
    p.setPen(_c(theme.INK))
    p.drawText(box, Qt.AlignmentFlag.AlignCenter, text)


def _pill(p: QPainter, anchor: QPointF, text: str, color: str, H: int, align: str, top: bool = False) -> float:
    """Text on a dark rounded pill; anchor is the bottom-left (align left), bottom-right (right) or
    bottom-center (center) point, or the top one with top=True. Returns the pill's width."""
    f = _font(theme.px(theme.SIZES["tag"], H))
    p.setFont(f)
    fm = p.fontMetrics()
    padx, pady = theme.px(12, H), theme.px(6, H)
    w, h = fm.horizontalAdvance(text) + 2 * padx, fm.height() + 2 * pady
    x = {"left": anchor.x(), "center": anchor.x() - w / 2}.get(align, anchor.x() - w)
    box = QRectF(x, anchor.y() if top else anchor.y() - h, w, h)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_c("#000000", 0.62))
    p.drawRoundedRect(box, h / 2, h / 2)
    p.setPen(_c(color, 0.95))
    p.drawText(box, Qt.AlignmentFlag.AlignCenter, text)
    return w


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


def ember_rows(s: LiveState) -> list[dict]:
    """The embers shown, at most MAX_EMBER_ROWS, ordered by the number shown ("n", else the id)."""
    rows = [e for e in (s.embers or []) if isinstance(e, dict)]
    return sorted(rows, key=lambda e: (int(e.get("n", e.get("id", 0)) or 0), int(e.get("id", 0) or 0)))[:MAX_EMBER_ROWS]


def _ember_number(e: dict) -> str:
    return str(int(e.get("n", e.get("id", 0)) or 0))


def _speed_text(e: dict, s: LiveState) -> str:
    return _fmt(e.get("speed_m_s"), "speed_m" if s.speed_unit == "m/s" else "speed_px")


def _speed_unit(s: LiveState, lang: str) -> str:
    return t(lang, "speed_unit_m" if s.speed_unit == "m/s" else "speed_unit_px")


def _badge(p: QPainter, c: QPointF, r: float, text: str, H: int) -> None:
    """An ember's number: dark type on an orange disc (orange marks embers only)."""
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_c(theme.ORANGE))
    p.drawEllipse(c, r, r)
    p.setPen(_c("#000000"))
    p.setFont(_font(max(theme.px(theme.SIZES["tag"], H), int(r * 1.15)), "bold", tabular=True))
    p.drawText(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r), Qt.AlignmentFlag.AlignCenter, text)


def _paint_ember_labels(p: QPainter, rect: QRectF, sc: float, s: LiveState, lang: str, H: int) -> None:
    """Each tracked phone's number and speed next to it, on a dark pill."""
    if s.image is None:
        return
    ih, iw = s.image.shape[:2]
    rows = ember_rows(s)
    if not rows:
        return
    # Positions are image pixels; positions all inside the unit square on a larger image are fractions.
    frac = all(0.0 <= float(e.get("x", 0)) <= 1.0 and 0.0 <= float(e.get("y", 0)) <= 1.0 for e in rows) and min(iw, ih) > 4
    f = _font(theme.px(theme.SIZES["tag"], H), "semibold", tabular=True)
    pady, padx = theme.px(6, H), theme.px(10, H)
    for e in rows:
        try:
            x, y = float(e["x"]), float(e["y"])
        except (KeyError, TypeError, ValueError):
            continue
        if frac:
            x, y = x * iw, y * ih
        cx, cy = rect.x() + x * sc, rect.y() + y * sc
        p.setFont(f)
        fm = p.fontMetrics()
        speed = _speed_text(e, s)
        text = f"{speed} {_speed_unit(s, lang)}" if speed else ""
        h = fm.height() + 2 * pady
        r = h / 2 - theme.px(3, H)
        w = 2 * r + theme.px(6, H) + (fm.horizontalAdvance(text) + padx if text else theme.px(2, H)) + theme.px(6, H)
        off = theme.px(22, H)
        bx = cx + off if cx + off + w <= rect.right() - 4 else cx - off - w
        by = max(rect.y() + 4, min(cy - off - h, rect.bottom() - h - 4))
        box = QRectF(bx, by, w, h)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_c("#000000", 0.62))
        p.drawRoundedRect(box, h / 2, h / 2)
        _badge(p, QPointF(bx + theme.px(3, H) + r, by + h / 2), r, _ember_number(e), H)
        if text:
            p.setFont(f)
            p.setPen(_c(theme.GREEN))
            p.drawText(QRectF(bx + 2 * r + theme.px(12, H), by, w, h), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)


def _paint_camera_message(p: QPainter, box: QRectF, state: str, lang: str, H: int) -> None:
    """Ember mode without a usable camera: what happened and what to do, in the screen's language
    and below it, smaller, in the other one; then the way back (M)."""
    key = CAMERA_MESSAGES[state]
    other = "en" if lang == "ko" else "ko"
    width = min(box.width() * 0.86, theme.px(1100, H))
    wrap = int(Qt.AlignmentFlag.AlignHCenter) | int(Qt.TextFlag.TextWordWrap)
    blocks = [(t(lang, key), _font(theme.px(theme.SIZES["message_title"], H), "semibold"), theme.INK, 1.0, theme.px(18, H)),
              (t(lang, key + "_do"), _font(theme.px(theme.SIZES["message_body"], H)), theme.INK, 0.86, theme.px(44, H)),
              (t(other, key), _font(theme.px(26, H), "semibold"), theme.INK2, 1.0, theme.px(10, H)),
              (t(other, key + "_do"), _font(theme.px(22, H)), theme.INK2, 1.0, theme.px(46, H))]
    sized = []
    for text, f, color, alpha, gap in blocks:
        p.setFont(f)
        r = p.boundingRect(QRectF(0, 0, width, 10000), wrap, text)
        sized.append((text, f, color, alpha, gap, r.height()))
    hint = t(lang, "back_to_fire")
    p.setFont(_font(theme.px(theme.SIZES["tag"], H)))
    hint_h = p.fontMetrics().height() + 2 * theme.px(6, H)
    total = sum(h + gap for *_, gap, h in sized) + hint_h
    y = box.center().y() - total / 2
    x = box.center().x() - width / 2
    for text, f, color, alpha, gap, h in sized:
        p.setFont(f)
        p.setPen(_c(color, alpha))
        p.drawText(QRectF(x, y, width, h), wrap, text)
        y += h + gap
    _pill(p, QPointF(box.center().x(), y), hint, theme.INK, H, "center", top=True)


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
        (t(lang, "cpc"), _fmt(s.cpc_gross, "int"), t(lang, "count_one" if s.cpc_gross == 1 else "count"), []),
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


def ember_tags(s: LiveState, lang: str) -> list[str]:
    """What qualifies the per-ember speeds: the distance they hold at, and the nominal field of
    view until an A4 calibration exists (pixel speeds say uncalibrated instead)."""
    if s.speed_unit != "m/s":
        return [t(lang, "uncalibrated")]
    tags = [t(lang, "measured_at", z=f"{s.measured_at_m:.1f}")] if s.measured_at_m else []
    return tags + ([] if s.calibrated else [t(lang, "nominal_fov")])


def ember_panel_layout(L: Layout) -> dict[str, object]:
    """Where ember mode's panel puts things: header, subtitle, count card, speeds label, tags and
    the MAX_EMBER_ROWS rows (QRectF each; rows is a list)."""
    H = L.H
    x, y, w = L.panel.x(), L.panel.y(), L.panel.width()
    count_top = y + theme.px(140, H)
    speeds_top = count_top + theme.px(204, H)   # room for the small "max 3" note under the count
    rows_top = speeds_top + theme.px(76, H)
    row_h = theme.px(78, H)
    return {"header": QRectF(x, y - theme.px(10, H), w, theme.px(62, H)),
            "header_other": QRectF(x, y + theme.px(50, H), w, theme.px(38, H)),
            "subtitle": QRectF(x, y + theme.px(88, H), w, theme.px(28, H)),
            "count": QRectF(x, count_top, w, theme.px(170, H)),
            "speeds": QRectF(x, speeds_top, w, theme.px(40, H)),
            "tags": QRectF(x, speeds_top + theme.px(40, H), w, theme.px(28, H)),
            "rows": [QRectF(x, rows_top + i * row_h, w, row_h) for i in range(MAX_EMBER_ROWS)]}


def _paint_ember_panel(p: QPainter, L: Layout, s: LiveState, lang: str) -> None:
    """Ember mode's panel: the header, the live count, and each ember's number and speed."""
    H = L.H
    G = ember_panel_layout(L)
    left = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    # The header in both languages: "당신이 불티입니다 / You are an ember", the screen's language
    # first and large, the other under it (L swaps them).
    other = "en" if lang == "ko" else "ko"
    for key, lg, color, base, floor in (("header", lang, theme.INK, theme.SIZES["ember_header"], theme.SIZES["label"]),
                                        ("header_other", other, theme.INK2, 32, theme.SIZES["tag"])):
        header, size = t(lg, "ember_header"), theme.px(base, H)
        p.setPen(_c(color))
        p.setFont(_font(size, "semibold"))
        while size > theme.px(floor, H) and p.fontMetrics().horizontalAdvance(header) > G[key].width():
            size -= 1                          # a narrow screen (4:3): smaller, never cut
            p.setFont(_font(size, "semibold"))
        p.drawText(G[key], left, header)
    p.setPen(_c(theme.INK2))
    p.setFont(_font(theme.px(theme.SIZES["tag"], H)))
    p.drawText(G["subtitle"], left, t(lang, "ember_subtitle"))
    live = _ember_live(s)
    count = _fmt(s.ember_count, "int") if live else ""
    cap = [t(lang, "ember_max").format(n=s.ember_max)] if s.ember_max else []
    _card(p, G["count"], t(lang, "ember_count"), count, t(lang, "ember_count_unit"), cap, H, 1.0)
    sp = G["speeds"]
    x, w = sp.x(), sp.width()
    p.setPen(QPen(_c(theme.INK3), 1))
    p.drawLine(QPointF(x, sp.y() - theme.px(6, H)), QPointF(x + w, sp.y() - theme.px(6, H)))
    p.setPen(_c(theme.INK2))
    p.setFont(_font(theme.px(theme.SIZES["label"], H)))
    p.drawText(sp, left, t(lang, "ember_speeds"))
    tags = ember_tags(s, lang) if live else []
    if tags:      # what qualifies the speeds, right under their label
        p.setFont(_font(theme.px(theme.SIZES["tag"], H)))
        p.drawText(G["tags"], left, "  ·  ".join(tags))
    rows = ember_rows(s) if live else []
    r = theme.px(theme.SIZES["ember_badge"], H) * 0.95
    unit = _speed_unit(s, lang)
    for e, box in zip(rows, G["rows"]):
        _badge(p, QPointF(x + r, box.center().y()), r, _ember_number(e), H)
        speed = _speed_text(e, s)
        tx = x + 2 * r + theme.px(22, H)
        tbox = QRectF(tx, box.y(), w - (tx - x), box.height())
        if speed:
            p.setFont(_font(theme.px(theme.SIZES["ember_row"], H), "semibold", tabular=True))
            p.setPen(_c(theme.GREEN))
            p.drawText(tbox, left, speed)
            vw = p.fontMetrics().horizontalAdvance(speed)
            p.setFont(_font(theme.px(theme.SIZES["unit"], H)))
            p.setPen(_c(theme.INK2))
            p.drawText(QRectF(tx + vw + theme.px(12, H), box.y() + theme.px(8, H), w, box.height()), left, unit)
        else:
            p.setFont(_font(theme.px(theme.SIZES["label"], H)))
            p.setPen(_c(theme.INK2))
            p.drawText(tbox, left, t(lang, "measuring"))
    if live and not rows:
        first = G["rows"][0]
        p.setFont(_font(theme.px(theme.SIZES["label"], H)))
        p.setPen(_c(theme.INK2))
        p.drawText(QRectF(x, first.y() + theme.px(8, H), w * 0.92, first.height() * 3), int(Qt.TextFlag.TextWordWrap),
                   t(lang, "ember_none"))


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


def _paint_sparkline(p: QPainter, L: Layout, s: LiveState, lang: str, box: QRectF | None = None) -> None:
    box = L.spark if box is None else box
    if box.width() < theme.px(120, L.H):
        return
    H = L.H
    p.setPen(_c(theme.INK2))
    p.setFont(_font(theme.px(theme.SIZES["tag"], H)))
    p.drawText(QRectF(box.x(), box.y(), box.width(), theme.px(26, H)), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
               t(lang, "ember_sparkline" if s.mode == "ember" else "sparkline"))
    area = QRectF(box.x(), box.y() + theme.px(32, H), box.width(), box.height() - theme.px(32, H))
    p.setPen(QPen(_c(theme.INK3), 1))
    p.drawLine(QPointF(area.x(), area.bottom()), QPointF(area.right(), area.bottom()))
    v = np.asarray(s.sparkline, dtype=float)
    if v.size < 2 or np.isfinite(v).sum() < 2 or (s.mode == "ember" and not _ember_live(s)):
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
    p.setBrush(Qt.BrushStyle.NoBrush)       # the line only (a brush left by the panel would fill it)
    p.drawPath(path)


def _paint_status(p: QPainter, L: Layout, s: LiveState, lang: str) -> None:
    H = L.H
    p.setFont(_font(theme.px(theme.SIZES["status"], H)))
    p.setPen(_c(theme.INK2))
    state = {"playing": t(lang, "playing"), "file": t(lang, "source_file"),
             "synthetic": t(lang, "ember_synthetic" if s.mode == "ember" else "synthetic"),
             "camera": t(lang, "camera")}.get(s.source_state, s.source_state)
    if s.mode == "ember" and not _ember_live(s):
        parts = []
    else:
        parts = [s.source_label or "", s.source_credit or "", state, f"{s.fps:.0f} {t(lang, 'fps')}" if s.fps else ""]
    keys = "L  한국어 / English     I  " + ("한계" if lang == "ko" else "Limits")
    fm = p.fontMetrics()
    room = int(L.status.width() - fm.horizontalAdvance(keys) - theme.px(40, H))
    left = fm.elidedText("   ·   ".join(x for x in parts if x), Qt.TextElideMode.ElideRight, max(room, 0))
    p.drawText(L.status, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, left)
    p.drawText(L.status, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, keys)


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
        for k, key in enumerate(limit_keys(lg), 1):
            text = f"{k}.  " + t(lg, key)
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
