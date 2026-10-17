"""Camera motion (global shift between frames) and a decaying map of where detections recur.

GlobalMotion: per analysed frame the luma is reduced to motion.thumb_width columns (area
average) and opened with a 3 x 3 square (grey erosion, then dilation), which removes bright
specks of a thumbnail pixel or two (embers), while the scene's larger structure stays. The
thumbnail is phase-correlated with the previous one under Hanning windows: in TILES x TILES
tiles, whose median shift ignores local motion (a shower moving with the wind, rising flames)
in a few tiles, and as a whole (a few bright lights panning in a dark scene). Of the two, the
shift that aligns the previous thumbnail best counts, and only when it explains the change:
the mean absolute difference after alignment must be at most ALIGN_GAIN of the unaligned one
(a shift read from noise in a textureless picture, or from flames alone, does not). It is
converted to analysis pixels (times W / thumb_width).

The residual is what alignment leaves of the scene's structure: both thumbnails are high-passed
(less their Gaussian blur of HIGHPASS_SIGMA thumbnail pixels), so smooth changes (drifting
smoke, the light of flames on the scene, an exposure step) drop out, and per tile the current
one less the aligned previous one times their least-squares gain (at least 0), so a change of
brightness or contrast is no change either; moved or replaced edges stay. A thumbnail pixel
has changed when that exceeds 3 noise and at least NOISE_FLOOR_DN (codec noise below it never
counts). The noise is the median, over the last NOISE_FRAMES frames without a global change,
of each frame's median absolute residual: a reference from quiet frames, because a cut or a
zoom inflates the spread of its own residual, and a spread taken from that frame alone would
hide the change it measures. `residual` reports the share of changed pixels over the whole
thumbnail; a tile has changed when more than motion.max_residual_frac of its pixels have, and
the change is global (a zoom, a rotation, a shake that the shift does not explain, a cut) only
when at least CHANGE_TILES of the TILES x TILES tiles have changed. Flames, smoke, a dense
shower or a lit region on a fixed camera change some tiles, not nearly all of them, so they are
not camera motion.

The camera is moving when the shift exceeds motion.max_shift_px, or the change is global, on
motion.consecutive analysed frames in a row; decisions are then withheld until motion.hold_s
after the last such frame. (A single changed frame is not enough: the booth's cuts are signalled
by Pipeline.cut, and file-mode segments are chosen without cuts.)

HotspotMap: a grid of hotspot.cell_px cells holding exponentially
decayed counts of detections (half-life hotspot.half_life_s in real time). `read` gives the
counts before this frame's detections are added (`add`), so a detection never sees itself.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass

import cv2
import numpy as np

from wfglink.verify.config import HotspotCfg, MotionCfg

NOISE_FLOOR_DN = 4.0      # thumbnail DN: a smaller change of a pixel is never counted
TILES = 3                 # tiles per side for the phase correlation and the residual
CHANGE_TILES = 7          # changed tiles (of TILES x TILES) that make a global change
ALIGN_GAIN = 0.7          # a shift counts when alignment leaves at most this share of the change
HIGHPASS_SIGMA = 2.0      # thumbnail px: smoother changes (smoke, light, exposure) drop out
NOISE_FRAMES = 30         # recent frames without a global change that set the noise reference
_OPEN = np.ones((3, 3), np.uint8)


@dataclass(frozen=True, slots=True)
class MotionStatus:
    shift_px: float          # global shift since the previous analysed frame, analysis px
    residual: float          # share of thumbnail pixels that changed after alignment
    unsupported: bool        # camera moving now or within hold_s: decisions withheld
    moving: bool = False     # this frame itself was judged moving
    tiles_changed: int = 0   # tiles whose share of changed pixels exceeds max_residual_frac


class GlobalMotion:
    def __init__(self, cfg: MotionCfg):
        self.cfg = cfg
        self.reset()

    def reset(self) -> None:
        self._prev: np.ndarray | None = None
        self._tiles: list[tuple[slice, slice, np.ndarray]] = []
        self._win: np.ndarray | None = None
        self._run = 0             # frames in a row with a shift above max_shift_px
        self._change_run = 0      # frames in a row with a global change
        self._noise: deque[float] = deque(maxlen=NOISE_FRAMES)
        self.unsupported_until = -math.inf
        self.last = MotionStatus(0.0, 0.0, False)

    def _thumb(self, luma: np.ndarray) -> np.ndarray:
        h, w = luma.shape[:2]
        tw = max(8, min(int(self.cfg.thumb_width), w))
        th = max(8, int(round(h * tw / w)))
        # Two area steps (uint8 to twice the size, then float32) keep fractional levels cheaply.
        mid = cv2.resize(luma, (2 * tw, 2 * th), interpolation=cv2.INTER_AREA)
        small = cv2.resize(mid.astype(np.float32), (tw, th), interpolation=cv2.INTER_AREA)
        return cv2.morphologyEx(small, cv2.MORPH_OPEN, _OPEN)

    def _setup(self, shape: tuple[int, int]) -> None:
        h, w = shape
        ys = np.linspace(0, h, TILES + 1).astype(int)
        xs = np.linspace(0, w, TILES + 1).astype(int)
        self._tiles = []
        for i in range(TILES):
            for j in range(TILES):
                sy, sx = slice(ys[i], ys[i + 1]), slice(xs[j], xs[j + 1])
                win = cv2.createHanningWindow((xs[j + 1] - xs[j], ys[i + 1] - ys[i]), cv2.CV_32F)
                self._tiles.append((sy, sx, win))

    def _candidates(self, prev: np.ndarray, cur: np.ndarray) -> list[tuple[float, float]]:
        """Shift candidates (thumbnail px): the median of the tiles' phase-correlation shifts, and
        the whole thumbnail's (a few bright lights panning in a dark scene)."""
        d = []
        for sy, sx, win in self._tiles:
            # phaseCorrelate writes into its inputs (OpenCV 4), so it gets copies.
            (dx, dy), _ = cv2.phaseCorrelate(prev[sy, sx].copy(), cur[sy, sx].copy(), win)
            d.append((dx, dy))
        mx, my = np.median(np.array(d), axis=0)
        (gx, gy), _ = cv2.phaseCorrelate(prev.copy(), cur.copy(), self._win)
        return [(float(mx), float(my)), (float(gx), float(gy))]

    def _align(self, prev: np.ndarray, dx: float, dy: float) -> np.ndarray:
        m = np.float32([[1, 0, dx], [0, 1, dy]])
        return cv2.warpAffine(prev, m, (prev.shape[1], prev.shape[0]), flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_REPLICATE)

    def _structure_change(self, cur: np.ndarray, prev: np.ndarray) -> np.ndarray:
        """What the aligned previous thumbnail does not explain of the current one's structure:
        both high-passed, then per tile the current one less the previous one times their
        least-squares gain (at least 0), so a change of brightness or contrast is no change."""
        hy = cur - cv2.GaussianBlur(cur, (0, 0), HIGHPASS_SIGMA)
        hx = prev - cv2.GaussianBlur(prev, (0, 0), HIGHPASS_SIGMA)
        out = np.empty_like(hy)
        for sy, sx, _ in self._tiles:
            x, y = hx[sy, sx], hy[sy, sx]
            den = float(np.sum(x * x))
            gain = max(float(np.sum(x * y)) / den, 0.0) if den > 0 else 0.0
            out[sy, sx] = y - gain * x
        return out

    def update(self, luma: np.ndarray, t: float) -> MotionStatus:
        cur = self._thumb(luma)
        scale = luma.shape[1] / cur.shape[1]
        if self._prev is None or self._prev.shape != cur.shape:
            self._prev = cur
            self._setup(cur.shape)
            self._win = cv2.createHanningWindow((cur.shape[1], cur.shape[0]), cv2.CV_32F)
            self._run = self._change_run = 0
            self._noise.clear()
            self.last = MotionStatus(0.0, 0.0, t < self.unsupported_until)
            return self.last
        e0 = float(np.mean(np.abs(cur - self._prev)))
        best = None
        for dx, dy in self._candidates(self._prev, cur):
            aligned = self._align(self._prev, dx, dy)
            e1 = float(np.mean(np.abs(cur - aligned)))
            if best is None or e1 < best[0]:
                best = (e1, dx, dy, aligned)
        e1, dx, dy, aligned = best
        explained = e1 <= ALIGN_GAIN * e0
        shift = math.hypot(dx, dy) * scale if explained else 0.0
        if not explained:
            aligned = self._prev
        diff = self._structure_change(cur, aligned)
        mad = float(np.median(np.abs(diff)))
        noise = float(np.median(self._noise)) if self._noise else mad
        changed = np.abs(diff) > max(3.0 * noise, NOISE_FLOOR_DN)
        residual = float(np.mean(changed))
        tiles = sum(float(np.mean(changed[sy, sx])) > self.cfg.max_residual_frac for sy, sx, _ in self._tiles)
        if tiles < CHANGE_TILES:
            self._noise.append(mad)
        self._run = self._run + 1 if shift > self.cfg.max_shift_px else 0
        self._change_run = self._change_run + 1 if tiles >= CHANGE_TILES else 0
        moving = self._run >= self.cfg.consecutive or self._change_run >= self.cfg.consecutive
        if moving:
            self.unsupported_until = t + self.cfg.hold_s
        self._prev = cur
        self.last = MotionStatus(float(shift), residual, bool(moving or t < self.unsupported_until), bool(moving),
                                 int(tiles))
        return self.last


class HotspotMap:
    def __init__(self, cfg: HotspotCfg):
        self.cell = max(1, int(cfg.cell_px))
        self.half_life = float(cfg.half_life_s)
        self.reset()

    def reset(self) -> None:
        self.grid: np.ndarray | None = None
        self._shape: tuple[int, int] | None = None
        self._t: float | None = None

    def ensure(self, shape: tuple[int, int]) -> None:
        shape = (int(shape[0]), int(shape[1]))
        if self._shape != shape:
            self._shape = shape
            self.grid = np.zeros((-(-shape[0] // self.cell), -(-shape[1] // self.cell)), np.float64)
            self._t = None

    def _decay(self, t: float | None) -> float:
        if t is None or self._t is None or not self.half_life > 0:
            return 1.0
        return 2.0 ** (-max(0.0, t - self._t) / self.half_life)

    def _cells(self, xs: np.ndarray, ys: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        g = self.grid
        cx = np.clip((np.nan_to_num(np.asarray(xs, np.float64)) // self.cell).astype(np.int64), 0, g.shape[1] - 1)
        cy = np.clip((np.nan_to_num(np.asarray(ys, np.float64)) // self.cell).astype(np.int64), 0, g.shape[0] - 1)
        return cy, cx

    def read(self, xs, ys, t: float | None = None) -> np.ndarray:
        """Decayed counts at the points, before this frame's add (0 before the first add)."""
        xs = np.asarray(xs, np.float64)
        if self.grid is None or xs.size == 0:
            return np.zeros(xs.shape[0], np.float64)
        cy, cx = self._cells(xs, ys)
        return self.grid[cy, cx] * self._decay(t)

    def add(self, xs, ys, t: float) -> None:
        xs = np.asarray(xs, np.float64)
        if self.grid is None:
            return
        if self._t is not None:
            self.grid *= self._decay(t)
        self._t = float(t)
        if xs.size:
            cy, cx = self._cells(xs, ys)
            np.add.at(self.grid, (cy, cx), 1.0)
