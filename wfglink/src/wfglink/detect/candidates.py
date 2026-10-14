"""Ember candidate detection: small bright blobs or streaks above the local background.

Per frame:
1. Luma Y (BT.601) and the background from the background model.
2. Positive residual P = max(Y - background - offset, 0) in uint8 OpenCV operations. The
   offset is a per-tile median of the residual refreshed every few frames, plus a robust
   global term refreshed every frame, so sudden exposure changes do not flood the mask.
3. White top-hat of P removes structures wider than the kernel (flames, glow halos) while
   thin streaks survive.
4. Noise-relative hysteresis: components grow above k_grow sigma and must reach k_seed
   sigma (and an absolute floor) somewhere. Threshold maps are precomputed as uint8.
5. Large bright regions (flames, headlights, glare) are found at quarter resolution by
   area and excluded with a margin.
6. Per component, on pixel lists only (no full-frame passes): intensity-weighted centroid
   and second moments of the signed residual in a slightly dilated window, streak length
   L = sqrt(12 (l1 - l2)), orientation, peak, saturation fraction and a warm-color score
   from the surrounding ring.

Color is only a confidence score: 4:2:0 compression averages the chroma of 2 to 3 px blobs
with the background, so it is never a hard filter.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from wfglink.detect.background import make_background

FLAG_SATURATED = 1
FLAG_NEAR_LARGE = 2

_FIELDS = ("x", "y", "area", "peak", "flux", "lam1", "lam2", "theta", "length", "width",
           "sat_frac", "color")


def _empty() -> np.ndarray:
    return np.zeros(0, dtype=np.float64)


@dataclass
class Detections:
    """Struct of arrays, one entry per detected candidate."""

    x: np.ndarray = field(default_factory=_empty)
    y: np.ndarray = field(default_factory=_empty)
    area: np.ndarray = field(default_factory=_empty)
    peak: np.ndarray = field(default_factory=_empty)     # top-hat peak, DN
    flux: np.ndarray = field(default_factory=_empty)     # summed signed residual in the window, DN px
    lam1: np.ndarray = field(default_factory=_empty)
    lam2: np.ndarray = field(default_factory=_empty)
    theta: np.ndarray = field(default_factory=_empty)    # radians, orientation mod pi (image axes, y down)
    length: np.ndarray = field(default_factory=_empty)   # motion-blur length, px
    width: np.ndarray = field(default_factory=_empty)    # about 4 sigma of the blur spot, px
    sat_frac: np.ndarray = field(default_factory=_empty)
    color: np.ndarray = field(default_factory=_empty)    # chroma excess Cr - Cb versus surroundings; > 0 is warm, NaN if unknown
    flags: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.uint8))

    def __len__(self) -> int:
        return int(self.x.shape[0])

    def subset(self, keep: np.ndarray) -> "Detections":
        return Detections(**{k: getattr(self, k)[keep] for k in (*_FIELDS, "flags")})

    def as_dict(self) -> dict[str, np.ndarray]:
        return {k: getattr(self, k) for k in (*_FIELDS, "flags")}


@dataclass
class DetectorState:
    """Intermediate images of the last frame, for overlays and debugging."""

    positive: np.ndarray | None = None
    tophat: np.ndarray | None = None
    sigma: np.ndarray | None = None
    large_mask: np.ndarray | None = None
    offset: float = 0.0


class Detector:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        d = cfg["detect"]
        self.background = make_background(cfg)
        self.kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (d["tophat_kernel_px"],) * 2)
        self.k_seed = float(d["threshold"]["k_seed"])
        self.k_grow = float(d["threshold"]["k_grow"])
        self.min_seed = float(d["threshold"]["min_seed_dn"])
        c = d["components"]
        self.min_area, self.max_area = int(c["min_area_px"]), int(c["max_area_px"])
        self.large_dilate = int(c["large_mask_dilate_px"])
        md = int(c["moment_dilate_px"])
        self.moment_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2 * md + 1,) * 2)
        n = d["noise"]
        self.tiles = tuple(int(v) for v in n["tiles"])
        self.noise_every = max(1, int(n["update_every"]))
        self.noise_stride = max(1, int(n["subsample"]))
        self.noise_floor = float(n["floor_dn"])
        self.sat_level = int(d["saturation"]["level_dn"])
        self.sat_min_px = int(d["saturation"]["flag_min_px"])
        col = d["color"]
        rp = int(col["ring_px"])
        self.ring_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2 * (md + rp) + 1,) * 2)
        self.luma_lo, self.luma_hi = col["luma_range"]
        self.warm_min = float(col["crcb_warm_min"])
        self.reset()

    @property
    def ready(self) -> bool:
        return self.background.ready and self._sigma is not None

    def reset(self) -> None:
        self.background.reset()
        self._frames = 0
        self._sigma: np.ndarray | None = None
        self._tile_offset: np.ndarray | None = None   # float32, full size
        self._offset_ref = 0.0
        self._grow_thr: np.ndarray | None = None      # uint8: grow where tophat >= this
        self._seed_thr: np.ndarray | None = None      # uint8: seed where tophat >= this
        self.state = DetectorState()

    # Noise and offset maps -------------------------------------------------------------
    def _update_maps(self, y: np.ndarray, bg: np.ndarray) -> None:
        h, w = y.shape
        s = self.noise_stride
        sub = y[::s, ::s].astype(np.float32) - bg[::s, ::s].astype(np.float32)
        cols, rows = self.tiles
        th, tw = max(1, sub.shape[0] // rows), max(1, sub.shape[1] // cols)
        sub = sub[: th * rows, : tw * cols]
        blocks = sub.reshape(rows, th, cols, tw).transpose(0, 2, 1, 3).reshape(rows, cols, -1)
        med = np.median(blocks, axis=2)
        mad = np.median(np.abs(blocks - med[..., None]), axis=2)
        sigma = np.maximum(1.4826 * mad, self.noise_floor).astype(np.float32)
        self._sigma = cv2.resize(sigma, (w, h), interpolation=cv2.INTER_LINEAR)
        self._tile_offset = cv2.resize(med.astype(np.float32), (w, h), interpolation=cv2.INTER_LINEAR)
        self._offset_ref = float(np.median(med))
        off_r = np.rint(self._tile_offset)
        self._off_pos = np.clip(off_r, 0, 255).astype(np.uint8)
        self._off_neg = np.clip(-off_r, 0, 255).astype(np.uint8)
        # tophat is an integer, so "tophat > k sigma" equals "tophat >= floor(k sigma) + 1".
        self._grow_thr = np.clip(np.floor(self.k_grow * self._sigma) + 1, 1, 255).astype(np.uint8)
        seed = np.maximum(np.ceil(self.k_seed * self._sigma), self.min_seed)
        self._seed_thr = np.clip(seed, 1, 255).astype(np.uint8)

    def _large_mask(self, pos: np.ndarray) -> np.ndarray:
        """Bright regions too large to be embers, found by area at quarter resolution."""
        h, w = pos.shape
        sw, sh = max(1, w // 4), max(1, h // 4)
        small = cv2.resize(pos, (sw, sh), interpolation=cv2.INTER_AREA)
        thr = cv2.resize(self._grow_thr, (sw, sh), interpolation=cv2.INTER_NEAREST)
        bright = cv2.compare(small, thr, cv2.CMP_GE)
        n, lab, stats, _ = cv2.connectedComponentsWithStats(bright, connectivity=8)
        big = np.nonzero(stats[1:, cv2.CC_STAT_AREA] * 16 > self.max_area)[0] + 1
        if big.size == 0:
            return np.zeros((h, w), np.uint8)
        mask = np.isin(lab, big).astype(np.uint8)
        r = max(1, int(round(self.large_dilate / 4)))
        mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1,) * 2))
        return cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)

    # Main entry --------------------------------------------------------------------------
    def detect(self, image: np.ndarray, mask: np.ndarray | None = None) -> Detections:
        """Detect candidates in one BGR frame. `mask` (uint8, nonzero = ignore) is optional."""
        y = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        bg = self.background.apply(y)
        self._frames += 1
        if bg is None:
            return Detections()
        if self._sigma is None or self._frames % self.noise_every == 0:
            self._update_maps(y, bg)

        # Global offset change since the last map update (sudden exposure change), applied
        # as a scalar so the per-pixel offset maps stay precomputed uint8.
        s = self.noise_stride * 4
        glob = float(np.median(y[::s, ::s].astype(np.int16) - bg[::s, ::s].astype(np.int16)))
        delta = int(round(glob - self._offset_ref))
        a = cv2.add(y, self._off_neg)
        b = cv2.add(bg, self._off_pos)
        if delta > 0:
            b = cv2.add(b, delta)
        elif delta < 0:
            a = cv2.add(a, -delta)
        pos = cv2.subtract(a, b)
        tophat = cv2.morphologyEx(pos, cv2.MORPH_TOPHAT, self.kernel)
        large = self._large_mask(pos)
        grow = cv2.compare(tophat, self._grow_thr, cv2.CMP_GE)
        if mask is not None:
            grow[mask > 0] = 0
        self.state = DetectorState(positive=pos, tophat=tophat, sigma=self._sigma,
                                   large_mask=large, offset=glob)

        n, labels, stats, _ = cv2.connectedComponentsWithStats(grow, connectivity=8, ltype=cv2.CV_32S)
        if n <= 1:
            return Detections()
        areas = stats[:, cv2.CC_STAT_AREA]
        nz = cv2.findNonZero(grow)
        gx, gy = nz[:, 0, 0], nz[:, 0, 1]
        gl = labels[gy, gx]
        th_vals = tophat[gy, gx]
        has_seed = np.zeros(n, dtype=bool)
        has_seed[gl[th_vals >= self._seed_thr[gy, gx]]] = True
        keep = has_seed & (areas >= self.min_area) & (areas <= self.max_area)
        keep[0] = False
        idx = np.nonzero(keep)[0]
        if idx.size == 0:
            return Detections()
        m = idx.size
        remap = np.zeros(n, dtype=np.int32)
        remap[idx] = np.arange(1, m + 1, dtype=np.int32)

        # Per-component peak and saturation on the component's own pixels.
        cl = remap[gl]
        sel = cl > 0
        cl, cy, cx, cth = cl[sel], gy[sel], gx[sel], th_vals[sel]
        peak = np.zeros(m + 1)
        np.maximum.at(peak, cl, cth)
        sat = np.bincount(cl, (y[cy, cx] >= self.sat_level).astype(np.float64), minlength=m + 1)

        # Kept-label image inside the union of padded bounding boxes only.
        x0 = max(int(stats[idx, cv2.CC_STAT_LEFT].min()) - 8, 0)
        y0 = max(int(stats[idx, cv2.CC_STAT_TOP].min()) - 8, 0)
        x1 = min(int((stats[idx, cv2.CC_STAT_LEFT] + stats[idx, cv2.CC_STAT_WIDTH]).max()) + 8, y.shape[1])
        y1 = min(int((stats[idx, cv2.CC_STAT_TOP] + stats[idx, cv2.CC_STAT_HEIGHT]).max()) + 8, y.shape[0])
        lab = np.zeros((y1 - y0, x1 - x0), np.uint16 if m < 65535 else np.float32)
        lab[cy - y0, cx - x0] = cl

        # Moments of the signed residual in a slightly dilated window.
        lab_d = cv2.dilate(lab, self.moment_kernel)
        nz = cv2.findNonZero((lab_d > 0).astype(np.uint8))
        wx, wy = nz[:, 0, 0], nz[:, 0, 1]
        li = lab_d[wy, wx].astype(np.int64)
        wy_full, wx_full = wy + y0, wx + x0
        wts = (y[wy_full, wx_full].astype(np.float64) - bg[wy_full, wx_full]
               - self._tile_offset[wy_full, wx_full] - (glob - self._offset_ref))
        wsum = np.bincount(li, wts, minlength=m + 1)[1:]
        wsafe = np.where(wsum > 1e-6, wsum, np.nan)
        mx = np.bincount(li, wts * wx_full, minlength=m + 1)[1:] / wsafe
        my = np.bincount(li, wts * wy_full, minlength=m + 1)[1:] / wsafe
        dx = wx_full - np.nan_to_num(mx)[li - 1]
        dy = wy_full - np.nan_to_num(my)[li - 1]
        cxx = np.bincount(li, wts * dx * dx, minlength=m + 1)[1:] / wsafe
        cyy = np.bincount(li, wts * dy * dy, minlength=m + 1)[1:] / wsafe
        cxy = np.bincount(li, wts * dx * dy, minlength=m + 1)[1:] / wsafe
        half_tr = (cxx + cyy) / 2
        disc = np.sqrt(np.maximum(((cxx - cyy) / 2) ** 2 + cxy ** 2, 0))
        lam1 = np.maximum(half_tr + disc, 0)
        lam2 = np.maximum(half_tr - disc, 0)
        theta = 0.5 * np.arctan2(2 * cxy, cxx - cyy)
        length = np.sqrt(np.maximum(12.0 * (lam1 - lam2), 0))
        width = 4.0 * np.sqrt(lam2)

        # Warm-color score: signal-weighted chroma (Cr - Cb, BT.601 scale) of the component's
        # unsaturated pixels, minus the median chroma of a ring just outside the window.
        # Saturated cores are white, so their unsaturated rim carries the color.
        color = np.full(m, np.nan)
        if image.ndim == 3:
            def crcb(py, px):
                b_ = image[py, px, 0].astype(np.float32)
                r_ = image[py, px, 2].astype(np.float32)
                l_ = y[py, px].astype(np.float32)
                return 0.713 * (r_ - l_) - 0.564 * (b_ - l_)

            luma_w = y[wy_full, wx_full]
            ok = (luma_w > self.luma_lo) & (luma_w < self.luma_hi) & (wts > 0)
            cw = np.where(ok, wts, 0.0)
            c_sum = np.bincount(li, cw * crcb(wy_full, wx_full), minlength=m + 1)[1:]
            c_w = np.bincount(li, cw, minlength=m + 1)[1:]
            ring = cv2.dilate(lab, self.ring_kernel)
            ring[lab_d > 0] = 0
            nz = cv2.findNonZero((ring > 0).astype(np.uint8))
            ring_ref = np.zeros(m)
            if nz is not None:
                rx, ry = nz[:, 0, 0], nz[:, 0, 1]
                rli = ring[ry, rx].astype(np.int64)
                rc = crcb(ry + y0, rx + x0).astype(np.float64)
                cnt = np.bincount(rli, minlength=m + 1)[1:]
                ring_ref = np.bincount(rli, rc, minlength=m + 1)[1:] / np.maximum(cnt, 1)
            color = np.where(c_w > 0, c_sum / np.where(c_w > 0, c_w, 1) - ring_ref, np.nan)

        area = areas[idx].astype(np.float64)
        sat_frac = sat[1:] / np.maximum(area, 1)
        flags = np.zeros(m, dtype=np.uint8)
        flags[sat[1:] >= self.sat_min_px] |= FLAG_SATURATED
        h, w = y.shape
        ix = np.clip(np.rint(np.nan_to_num(mx)).astype(int), 0, w - 1)
        iy = np.clip(np.rint(np.nan_to_num(my)).astype(int), 0, h - 1)
        near_large = large[iy, ix] > 0
        flags[near_large] |= FLAG_NEAR_LARGE

        det = Detections(x=mx, y=my, area=area, peak=peak[1:], flux=wsum, lam1=lam1, lam2=lam2,
                         theta=theta, length=length, width=width, sat_frac=sat_frac,
                         color=color, flags=flags)
        good = np.isfinite(mx) & np.isfinite(my) & ~near_large
        return det.subset(good)
