"""QR codes of the ember page's address (booth.ember_page_url), for the ember screen and the
A5 placard, made with OpenCV's own encoder (cv2.QRCodeEncoder: no other package).

qr_modules(text) is the code as a square boolean array, True for a dark module, including
the standard quiet zone of four light modules on every side; draw_qr paints it with QPainter
(dark modules on a white square), so the screen and the PDF draw the same code.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

import numpy as np

QUIET = 4          # light modules around the code (the QR standard's quiet zone)


@lru_cache(maxsize=8)
def _modules(text: str) -> np.ndarray:
    import cv2

    img = cv2.QRCodeEncoder.create().encode(text)
    if img is None or img.size == 0:
        raise ValueError(f"cannot make a QR code of {text!r}")
    dark = img < 128
    # The encoder leaves a margin of light modules; keep exactly QUIET of them.
    rows, cols = np.flatnonzero(dark.any(axis=1)), np.flatnonzero(dark.any(axis=0))
    core = dark[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]
    out = np.pad(core, QUIET, constant_values=False)
    out.setflags(write=False)
    return out


def qr_modules(text: str) -> np.ndarray:
    """The QR code of text: (n, n) bool, True = dark, with the quiet zone included."""
    return _modules(str(text).strip())


def draw_qr(p: Any, x: float, y: float, size: float, text: str) -> None:
    """The QR code of text on a white square of side `size` at (x, y) (QPainter units)."""
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QPainter, QPainterPath

    m = qr_modules(text)
    n = m.shape[0]
    cell = size / n
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    p.fillRect(QRectF(x, y, size, size), Qt.GlobalColor.white)
    # All dark modules form one path, filled once: separately antialiased rectangles leave light
    # seams where they meet, which can lower scan reliability on a printed card.
    path = QPainterPath()
    path.setFillRule(Qt.FillRule.WindingFill)
    for r in range(n):
        row = m[r]
        c = 0
        while c < n:            # one rectangle per run of dark modules
            if not row[c]:
                c += 1
                continue
            c0 = c
            while c < n and row[c]:
                c += 1
            path.addRect(QRectF(x + c0 * cell, y + r * cell, (c - c0) * cell, cell))
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)   # crisp module edges, no seams
    p.fillPath(path, Qt.GlobalColor.black)
    p.restore()
