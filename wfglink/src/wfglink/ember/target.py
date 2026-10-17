"""The printed A4 calibration target: geometry, raster image and the print-ready PDF.

booth/ember/calibration_target_A4.pdf (scripts/make_calibration_target.py) is an A4 sheet in
landscape with four ArUco markers (dictionary 4x4_50, ids 0 to 3: top left, top right,
bottom right, bottom left), each MARKER_MM wide with MARGIN_MM of white to the paper's
edge, a LINE_MM line in the middle to check the print scale with a ruler, and "print at
100 percent" in Korean and English. Every size is exact in the PDF (vector, no margins).

Object points are the marker corners in metres relative to the centre of the sheet, x to
the right and y down as printed, in ArUco's corner order (top left, top right, bottom right,
bottom left of each marker).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from wfglink import PROJECT_ROOT

PAGE_MM = (297.0, 210.0)          # A4 landscape
MARKER_MM = 75.0                  # marker side, black border included (6 modules of 12.5 mm)
MARGIN_MM = 15.0                  # white between each marker and the paper's edge (more than one module)
LINE_MM = 100.0                   # print-scale check line
DICTIONARY = "DICT_4X4_50"
IDS = (0, 1, 2, 3)                # top left, top right, bottom right, bottom left
MODULES = 6                       # 4x4 bits plus a one-module black border
TARGET_PDF = PROJECT_ROOT / "booth" / "ember" / "calibration_target_A4.pdf"
TARGET_PNG = PROJECT_ROOT / "booth" / "ember" / "calibration_target_A4.png"
DESCRIPTION = (f"A4 ArUco {DICTIONARY[5:]} ids 0-3, {MARKER_MM:g} mm markers "
               "(booth/ember/calibration_target_A4.pdf)")

TEXT = {
    "title": "wfglink 보정 표적 · calibration target (A4)",
    "print": ["실제 크기(100%)로 인쇄하세요. 아래 선이 정확히 100 mm인지 자로 확인하세요.",
              "Print at 100 percent (actual size). Check with a ruler that the line below is 100 mm."],
    "hold": ["서는 자리에서 카메라를 향해 평평하게 들고 계세요: python -m wfglink calibrate",
             "Hold it flat at the standing spot, facing the camera: python -m wfglink calibrate"],
    "line": "100 mm",
}


def dictionary():
    import cv2

    return cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, DICTIONARY))


def marker_origins_mm() -> dict[int, tuple[float, float]]:
    """Top-left corner of each marker on the sheet, mm from the sheet's top-left corner."""
    w, h = PAGE_MM
    a, b = MARGIN_MM, MARGIN_MM
    return {0: (a, b), 1: (w - a - MARKER_MM, b), 2: (w - a - MARKER_MM, h - b - MARKER_MM), 3: (a, h - b - MARKER_MM)}


def object_points(ids: list[int] | tuple[int, ...] = IDS) -> np.ndarray:
    """(4 n, 3) marker corners in metres, sheet centre at the origin, in ArUco corner order."""
    cx, cy = PAGE_MM[0] / 2, PAGE_MM[1] / 2
    org = marker_origins_mm()
    pts = []
    for i in ids:
        x, y = org[int(i)]
        for dx, dy in ((0, 0), (MARKER_MM, 0), (MARKER_MM, MARKER_MM), (0, MARKER_MM)):
            pts.append(((x + dx - cx) / 1000.0, (y + dy - cy) / 1000.0, 0.0))
    return np.asarray(pts, np.float64)


def marker_bits(marker_id: int) -> np.ndarray:
    """MODULES x MODULES array, 1 for black, border included."""
    import cv2

    img = cv2.aruco.generateImageMarker(dictionary(), int(marker_id), MODULES, borderBits=1)
    return (img < 128).astype(np.uint8)


def line_mm() -> tuple[float, float, float]:
    """(x0, x1, y) of the print-scale line, mm."""
    w, h = PAGE_MM
    return (w - LINE_MM) / 2, (w + LINE_MM) / 2, h / 2 + 8.0


def target_image(px_per_mm: float = 4.0, paper: float = 1.0, ink: float = 0.04) -> np.ndarray:
    """The sheet as a float32 grey image (paper and ink reflectance), markers and line only
    (the small text does not matter to a camera at 2 m). Used by the synthetic target clips."""
    import cv2

    w, h = int(round(PAGE_MM[0] * px_per_mm)), int(round(PAGE_MM[1] * px_per_mm))
    img = np.full((h, w), paper, np.float32)
    s = px_per_mm
    for mid, (x, y) in marker_origins_mm().items():
        bits = marker_bits(mid)
        m = MARKER_MM / MODULES
        for r in range(MODULES):
            for c in range(MODULES):
                if bits[r, c]:
                    x0, y0 = int(round((x + c * m) * s)), int(round((y + r * m) * s))
                    x1, y1 = int(round((x + (c + 1) * m) * s)), int(round((y + (r + 1) * m) * s))
                    img[y0:y1, x0:x1] = ink
    x0, x1, y = line_mm()
    cv2.line(img, (int(round(x0 * s)), int(round(y * s))), (int(round(x1 * s)), int(round(y * s))), float(ink),
             max(1, int(round(0.6 * s))))
    return img


def draw_target(p: Any, dpmm: float) -> None:
    """Draw the sheet with a QPainter on a device with dpmm device pixels per millimetre."""
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QPainterPath, QPen

    from wfglink.ui.fonts import ui_font

    def R(x: float, y: float, w: float, h: float) -> QRectF:
        return QRectF(x * dpmm, y * dpmm, w * dpmm, h * dpmm)

    def P(x: float, y: float) -> QPointF:
        return QPointF(x * dpmm, y * dpmm)

    w, h = PAGE_MM
    black, gray = QColor("#000000"), QColor("#555555")
    p.fillRect(R(0, 0, w, h), QColor("#FFFFFF"))
    m = MARKER_MM / MODULES
    for mid, (x, y) in marker_origins_mm().items():
        # A black square with its white modules cut out as one merged shape: no seams between modules.
        bits = marker_bits(mid)
        white = QPainterPath()
        for r in range(MODULES):
            for c in range(MODULES):
                if not bits[r, c]:
                    white.addRect(R(x + c * m, y + r * m, m, m))
        p.fillRect(R(x, y, MARKER_MM, MARKER_MM), black)
        p.fillPath(white.simplified(), QColor("#FFFFFF"))

    def text(x: float, y: float, cw: float, ch: float, s: str, size_mm: float, color: QColor = black,
             bold: bool = False) -> None:
        f = ui_font(max(1, round(size_mm * dpmm)), "semibold" if bold else "regular")
        p.setFont(f)
        p.setPen(color)
        p.drawText(R(x, y, cw, ch), int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
                                        | Qt.TextFlag.TextWordWrap), s)

    col0 = MARGIN_MM + MARKER_MM + 5.0
    col_w = w - 2 * col0
    text(col0, MARGIN_MM, col_w, 14.0, TEXT["title"], 3.6, bold=True)
    text(col0, MARGIN_MM + 13.0, col_w, 16.0, TEXT["print"][0], 2.9)
    text(col0, MARGIN_MM + 27.0, col_w, 16.0, TEXT["print"][1], 2.9)
    x0, x1, y = line_mm()
    pen = QPen(black, 0.5 * dpmm)
    pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    p.setPen(pen)
    p.drawLine(P(x0, y), P(x1, y))
    for x in (x0, x1):
        p.drawLine(P(x, y - 5.0), P(x, y + 5.0))
    pen.setWidthF(0.3 * dpmm)
    p.setPen(pen)
    for k in range(1, 10):
        xx = x0 + k * 10.0
        p.drawLine(P(xx, y - (3.0 if k == 5 else 1.8)), P(xx, y))
    text(x0, y - 11.0, LINE_MM, 6.0, TEXT["line"], 3.2, bold=True)
    text(col0, y + 8.0, col_w, 16.0, TEXT["hold"][0], 2.7, gray)
    text(col0, y + 21.0, col_w, 16.0, TEXT["hold"][1], 2.7, gray)
    text(0, h - MARGIN_MM + 4.0, w, 6.0, DESCRIPTION, 2.2, gray)


def write_target(pdf: str | Path = TARGET_PDF, png: str | Path | None = TARGET_PNG, png_dpi: float = 100.0) -> dict:
    """Write the PDF (A4 landscape, no margins, exact millimetres) and a PNG preview."""
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QMarginsF
    from PySide6.QtGui import QGuiApplication, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter

    from wfglink.ui.fonts import load_fonts

    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841  (keeps Qt alive)
    load_fonts()
    pdf = Path(pdf)
    pdf.parent.mkdir(parents=True, exist_ok=True)
    writer = QPdfWriter(str(pdf))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageOrientation(QPageLayout.Orientation.Landscape)
    writer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter)
    writer.setResolution(1200)
    writer.setTitle("wfglink calibration target (A4, print at 100 percent)")
    writer.setCreator("wfglink (scripts/make_calibration_target.py)")
    devices: list[tuple[Any, float]] = [(writer, float(writer.resolution()))]
    img = None
    if png is not None:
        img = QImage(round(PAGE_MM[0] / 25.4 * png_dpi), round(PAGE_MM[1] / 25.4 * png_dpi), QImage.Format.Format_RGB32)
        devices.append((img, png_dpi))
    for device, dpi in devices:
        p = QPainter(device)
        try:
            p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            draw_target(p, dpi / 25.4)
        finally:
            p.end()
    out = {"pdf": str(pdf)}
    if img is not None:
        Path(png).parent.mkdir(parents=True, exist_ok=True)
        img.convertToFormat(QImage.Format.Format_Grayscale8).save(str(png))
        out["png"] = str(png)
    return out
