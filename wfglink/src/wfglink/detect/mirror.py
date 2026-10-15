"""Mirror test: count the encoder's dark specks to know how bright its bright specks get.

Glowing embers only add light, so they never make the residual (frame minus background)
negative. Compression error is zero mean: a quantised transform coefficient is a cosine
pattern, so a block that comes out too bright in one place comes out too dark a few pixels
away, and an edge that the encoder's quality cycle sharpens or shifts (a keyframe or refresh
frame, then a slow return) gets a bright lobe on one side and a dark lobe on the other. On a
clean, static, textured scene this error is sparse and heavy tailed: isolated lobes a few
pixels wide along edges and textures, where the encoder quantises hardest, and nearly
nothing in flat areas. The per-tile MAD sees the flat majority and reads almost zero, the
seed threshold sits on its floor, and the bright lobes pass it. Their dark mirror images are
just as many and just as strong, and nothing else makes them, so they count the false
alarms to expect in each neighbourhood of each frame: a constant-false-alarm threshold that
needs no history and follows the quality cycle frame by frame.

Per frame:
1. N = max(background - Y, 0), the negative residual (offsets applied as for the positive one),
   max-pooled 2 x 2 (half resolution keeps the cost low; max pooling keeps the lobes' peaks),
   and its top-hat with a square of half the detector's top-hat size: dark lobes as small as
   an ember; broad dark regions (a flame dying down, a light switched off) drop out, as broad
   bright ones do on the positive side.
2. Dark lobes count where they reach the seed level, so that each would have been a detection
   if it were bright, and are at most [detect.mirror.cap_dn]: stronger dark structures (an
   overlay or object that moved away) and a rim of RIM_PX around them are changes of the
   scene, not quantisation error. Each lobe is counted once, at its local maximum.
3. Per block of [detect.mirror.block_px], the lobes in the 3 x 3 blocks around it are counted.
   With at least [detect.mirror.count] of them the encoder's error dominates there, and the
   block's seeds must reach [detect.mirror.ratio] times the strongest of them. Elsewhere
   nothing changes: on sensor noise, even compressed, dark lobes at the seed level are rare
   and scattered, so the test stays silent.

Only the seed test changes; growth, moments and the large-region mask are untouched, so an
ember that passes keeps its shape and length.
"""
from __future__ import annotations

import cv2
import numpy as np

_POOL = np.ones((2, 2), np.uint8)
_K3 = np.ones((3, 3), np.uint8)
_PREV = np.array([[1, 1, 1], [1, 0, 0], [0, 0, 0]], np.uint8)   # neighbours before a pixel in raster order
RIM_PX = 4          # rim (full-resolution px) around a dark structure stronger than the cap


def _pool2(img: np.ndarray) -> np.ndarray:
    """2 x 2 max pooling; output size ceil(h / 2) x ceil(w / 2)."""
    return np.ascontiguousarray(cv2.dilate(img, _POOL, anchor=(0, 0))[::2, ::2])


class MirrorTest:
    def __init__(self, cfg: dict):
        d = cfg["detect"]
        m = d.get("mirror", {}) or {}
        self.enabled = bool(m.get("enabled", False))
        self.block = max(4, 2 * int(round(float(m.get("block_px", 32)) / 2)))
        self.count = max(1, int(m.get("count", 3)))
        self.ratio = float(m.get("ratio", 2.0))
        self.cap = int(np.clip(m.get("cap_dn", 16), 1, 255))
        kh = max(3, (int(d["tophat_kernel_px"]) + 1) // 2 | 1)        # the top-hat size at half resolution
        self.k_tophat = cv2.getStructuringElement(cv2.MORPH_RECT, (kh, kh))
        r = max(1, RIM_PX // 2)
        self.k_rim = cv2.getStructuringElement(cv2.MORPH_RECT, (2 * r + 1, 2 * r + 1))
        self._seed_half: np.ndarray | None = None

    def grid(self, shape: tuple[int, int]) -> tuple[int, int]:
        """Blocks (rows, columns) covering a frame of this shape."""
        return -(-shape[0] // self.block), -(-shape[1] // self.block)

    def set_seed(self, seed_thr: np.ndarray) -> None:
        """New seed map of the detector (uint8, full resolution; smooth, so decimation keeps it)."""
        self._seed_half = np.ascontiguousarray(seed_thr[::2, ::2])

    def lobes(self, neg: np.ndarray, seed_thr: np.ndarray | None = None) -> np.ndarray:
        """Counted dark lobes: local maxima of the dark top-hat at half resolution (uint8 DN, 0 elsewhere)."""
        if seed_thr is not None:
            self.set_seed(seed_thr)
        th = cv2.morphologyEx(_pool2(neg), cv2.MORPH_TOPHAT, self.k_tophat)
        strong = cv2.dilate(cv2.compare(th, self.cap, cv2.CMP_GT), self.k_rim)
        keep = cv2.bitwise_and(cv2.compare(th, self._seed_half, cv2.CMP_GE), cv2.bitwise_not(strong))
        half = cv2.bitwise_and(th, keep)
        # One pixel per lobe: a local maximum, and on a plateau the first pixel in raster order.
        peak = cv2.bitwise_and(cv2.compare(half, cv2.dilate(half, _K3), cv2.CMP_GE),
                               cv2.compare(half, cv2.dilate(half, _PREV), cv2.CMP_GT))
        return cv2.bitwise_and(half, peak)

    def seed_levels(self, neg: np.ndarray, seed_thr: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
        """(seed, lobes): per block the uint8 seed level of the mirror test (0 where it does not
        apply), and the counted dark lobes at half resolution. seed_thr is the detector's seed
        map; without it the one last given to set_seed is used."""
        lobes = self.lobes(neg, seed_thr)
        nby, nbx = self.grid(neg.shape)
        seed = np.zeros((nby, nbx), np.uint8)
        if cv2.countNonZero(lobes) < self.count:
            return seed, lobes
        nz = cv2.findNonZero(lobes)
        b2 = self.block // 2
        lx, ly = nz[:, 0, 0], nz[:, 0, 1]
        v = lobes[ly, lx]
        bi = (ly // b2) * nbx + lx // b2
        n = np.bincount(bi, minlength=nby * nbx).astype(np.float32).reshape(nby, nbx)
        order = np.argsort(bi, kind="stable")
        bs, vs = bi[order], v[order]
        start = np.flatnonzero(np.r_[True, bs[1:] != bs[:-1]])
        top = np.zeros(nby * nbx, np.uint8)
        top[bs[start]] = np.maximum.reduceat(vs, start)
        # Sum and maximum over the 3 x 3 blocks around each block.
        n = cv2.boxFilter(n, -1, (3, 3), normalize=False, borderType=cv2.BORDER_CONSTANT)
        top = cv2.dilate(top.reshape(nby, nbx), _K3)
        level = np.where(n >= self.count - 0.5, top, 0)
        seed[:] = np.clip(np.ceil(self.ratio * level), 0, 255)
        return seed, lobes

    def seed_ok(self, vals: np.ndarray, gy: np.ndarray, gx: np.ndarray, seed: np.ndarray) -> np.ndarray:
        """True where a candidate pixel's top-hat value passes the block's mirror seed level."""
        return vals >= seed[gy // self.block, gx // self.block]
