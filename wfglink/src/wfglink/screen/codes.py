"""Corner codes for the camera-in-the-loop booth: ArUco markers plus a Gray-coded frame index.

Every corner of a prepared clip carries the same block (in source pixels, scaled with the
frame height):

    +--------+---------------------------------+
    | ArUco  | W B b15 b14 ... b8  P_hi          |   2 rows x 11 cells
    | marker | W B b7  b6  ... b0  P_lo          |   W and B are white and black references
    +--------+---------------------------------+

The marker (DICT_4X4_50; ids 0, 1, 2, 3 for top-left, top-right, bottom-right, bottom-left)
lets the camera find and rectify the screen. The 16-bit source frame index is Gray coded,
so consecutive frames differ in exactly one bit: a camera frame that blends two source
frames shows one mid-gray data cell (plus that row's parity cell) whose level gives the
blend weight. Each row ends
with an even-parity bit over its 8 data bits. A frame is clean only when all four corner
codes decode, agree, and contain no gray cell.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

DICT = cv2.aruco.DICT_4X4_50
CORNER_IDS = (0, 1, 2, 3)          # top-left, top-right, bottom-right, bottom-left
N_BITS = 16
COLS, ROWS = 11, 2                 # cells per strip row (W, B, 8 data bits, parity), strip rows


@dataclass(frozen=True)
class Layout:
    """Geometry of the corner blocks for a W x H source frame (source pixels)."""

    width: int
    height: int
    marker: int                    # marker side
    cell: int                      # code cell side
    margin: int                    # gap from the frame edge and between marker and strip

    @classmethod
    def for_frame(cls, width: int, height: int, scale: float = 1.0) -> "Layout":
        marker = int(round(0.085 * height * scale))
        cell = max(6, int(round(marker / 4)))
        return cls(width, height, marker, cell, max(2, int(round(marker / 12))))

    @property
    def block_w(self) -> int:
        return self.margin + self.marker + self.margin + COLS * self.cell + self.margin

    @property
    def block_h(self) -> int:
        return self.margin + max(self.marker, ROWS * self.cell) + self.margin

    def block_origin(self, corner: int) -> tuple[int, int]:
        """Top-left of the block for corner 0..3 (TL, TR, BR, BL)."""
        x = 0 if corner in (0, 3) else self.width - self.block_w
        y = 0 if corner in (0, 1) else self.height - self.block_h
        return x, y

    def marker_corners(self, corner: int) -> np.ndarray:
        """Marker corner points (TL, TR, BR, BL order, as ArUco reports) in source pixels."""
        bx, by = self.block_origin(corner)
        mx = bx + (self.margin if corner in (0, 3) else self.block_w - self.margin - self.marker)
        my = by + self.margin
        m = self.marker
        return np.array([[mx, my], [mx + m, my], [mx + m, my + m], [mx, my + m]], np.float32)

    def cell_centers(self, corner: int) -> np.ndarray:
        """(ROWS, COLS, 2) cell centers in source pixels. Strips sit on the inner side of the marker."""
        bx, by = self.block_origin(corner)
        if corner in (0, 3):
            sx = bx + self.margin + self.marker + self.margin
        else:
            sx = bx + self.margin
        sy = by + self.margin
        cx = sx + (np.arange(COLS) + 0.5) * self.cell
        cy = sy + (np.arange(ROWS) + 0.5) * self.cell
        return np.stack(np.meshgrid(cx, cy), axis=-1).astype(np.float32)

    def mask(self) -> np.ndarray:
        """uint8 mask (255 = covered by a corner block) for excluding codes from detection."""
        m = np.zeros((self.height, self.width), np.uint8)
        for c in range(4):
            x, y = self.block_origin(c)
            m[y:y + self.block_h, x:x + self.block_w] = 255
        return m


def gray_encode(i: int) -> int:
    return int(i) ^ (int(i) >> 1)


def gray_decode(g: int) -> int:
    g = int(g)
    mask = g >> 1
    while mask:
        g ^= mask
        mask >>= 1
    return g


def code_bits(index: int) -> np.ndarray:
    """(ROWS, COLS) values in {0, 1}: references, Gray bits and parity."""
    g = gray_encode(index % (1 << N_BITS))
    bits = [(g >> (N_BITS - 1 - k)) & 1 for k in range(N_BITS)]
    hi, lo = bits[:8], bits[8:]
    rows = []
    for data in (hi, lo):
        rows.append([1, 0, *data, sum(data) % 2])
    return np.array(rows, np.uint8)


_MARKERS: dict[tuple[int, int], np.ndarray] = {}


def _marker_image(marker_id: int, side: int) -> np.ndarray:
    key = (marker_id, side)
    if key not in _MARKERS:
        d = cv2.aruco.getPredefinedDictionary(DICT)
        _MARKERS[key] = cv2.aruco.generateImageMarker(d, marker_id, side, borderBits=1)
    return _MARKERS[key]


def draw_codes(image: np.ndarray, index: int, layout: Layout) -> np.ndarray:
    """Draw the four corner blocks onto a BGR source frame (in place) and return it."""
    bits = code_bits(index)
    for corner, mid in zip(range(4), CORNER_IDS):
        bx, by = layout.block_origin(corner)
        image[by:by + layout.block_h, bx:bx + layout.block_w] = 255  # white quiet zone
        mk = layout.marker_corners(corner).astype(int)
        x0, y0 = mk[0]
        image[y0:y0 + layout.marker, x0:x0 + layout.marker] = _marker_image(mid, layout.marker)[:, :, None]
        centers = layout.cell_centers(corner)
        half = layout.cell / 2
        for r in range(ROWS):
            for c in range(COLS):
                cx, cy = centers[r, c]
                x1, y1 = int(round(cx - half)), int(round(cy - half))
                v = 255 if bits[r, c] else 0
                image[y1:y1 + layout.cell, x1:x1 + layout.cell] = v
    return image


@dataclass
class CornerCode:
    corner: int
    index: int | None              # decoded source frame index, None if unreadable
    gray_cells: int                # cells between the black and white references
    blend: float | None            # level of the gray cell (0 = earlier frame, 1 = later), if one
    parity_ok: bool


def read_corner(rect: np.ndarray, layout: Layout, corner: int, gray_band: float = 0.25) -> CornerCode:
    """Decode one corner from a rectified grayscale frame in source pixel coordinates."""
    centers = layout.cell_centers(corner)
    r = max(1, int(layout.cell * 0.25))
    vals = np.zeros((ROWS, COLS), np.float32)
    h, w = rect.shape[:2]
    for i in range(ROWS):
        for j in range(COLS):
            cx, cy = int(round(centers[i, j, 0])), int(round(centers[i, j, 1]))
            patch = rect[max(cy - r, 0):min(cy + r + 1, h), max(cx - r, 0):min(cx + r + 1, w)]
            vals[i, j] = float(patch.mean()) if patch.size else np.nan
    white = np.nanmean(vals[:, 0])
    black = np.nanmean(vals[:, 1])
    if not np.isfinite(white) or not np.isfinite(black) or white - black < 30:
        return CornerCode(corner, None, 0, None, False)
    norm = (vals - black) / (white - black)
    data = norm[:, 2:]
    gray = (data > gray_band) & (data < 1 - gray_band)
    bits = (data >= 0.5).astype(int)
    parity_ok = all(int(bits[k, :8].sum() % 2) == int(bits[k, 8]) for k in range(ROWS))
    g = 0
    for b in [*bits[0, :8], *bits[1, :8]]:
        g = (g << 1) | int(b)
    gray_data = gray[:, :8]          # the parity cell of the same row flips too; ignore it here
    blend = float(data[:, :8][gray_data][0]) if gray_data.sum() == 1 else None
    return CornerCode(corner, gray_decode(g), int(gray.sum()), blend, parity_ok)


@dataclass
class FrameCode:
    index: int | None
    clean: bool
    blended: bool
    torn: bool
    corners: list[CornerCode]


def read_frame_code(rect_gray: np.ndarray, layout: Layout) -> FrameCode:
    """Combine the four corners: clean only if all decode, agree, have parity and no gray cell."""
    corners = [read_corner(rect_gray, layout, c) for c in range(4)]
    idx = [c.index for c in corners if c.index is not None and c.parity_ok and c.gray_cells == 0]
    any_gray = any(c.gray_cells > 0 for c in corners)
    readable = [c.index for c in corners if c.index is not None]
    distinct = set(readable)
    torn = len(distinct) > 1 and not any_gray
    clean = len(idx) == 4 and len(set(idx)) == 1
    index = idx[0] if clean else (max(set(readable), key=readable.count) if readable else None)
    return FrameCode(index, clean, any_gray, torn, corners)
