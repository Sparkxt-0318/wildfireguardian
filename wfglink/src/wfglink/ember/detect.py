"""Detection of phone screens showing the ember page.

A phone held 1 to 3 m from the camera shows the page's disc as a compact blob: its centre
is far brighter than the room (an emitting screen; it clips in a webcam), and its edge is
orange or yellow. Per frame, at ember.detect_scale of the analysed size:

1. Brightness V = max(R, G, B) and hue and saturation (HSV).
2. Blobs: connected pixels brighter than ember.detect.blob_dn, with an area between the
   sizes a phone's bright disc can have between the near and far ends of
   ember.distance_range_m (ember.blob_m at the focal length in use), the largest allowing
   for motion blur (ember.detect.area_blur_factor).
3. Core: the blob's brightest pixel reaches ember.detect.core_dn.
4. Colour: within the blob and ember.detect.ring_px around it, the pixels brighter than
   ember.detect.warm_dn that carry colour (saturation at least ember.detect.chroma_min) must
   be mostly warm (hue in ember.detect.warm_hue, or a red above ember.detect.warm_hue_wrap,
   saturation at least ember.detect.warm_sat): at least ember.detect.warm_frac_min of them and
   ember.detect.warm_px_min in number. White lamps, windows and ceiling lights fail here. The
   warm pixels must also ring the core: their centre may lie at most
   ember.detect.warm_offset_max blob radii from the blob's centre (a bright patch merely next
   to a phone's glow, such as a piece of window by the hand, has its warm pixels on one side).
   And they must form a halo: at least ember.detect.halo_min times the blob's area (the page's
   disc is mostly orange around a small white centre; a lamp shade or a window clips to a large
   white blob with a thin warm edge).
5. Shape: no longer than ember.detect.max_elongation times its width (second moments).
6. Background: an approximate running median of V (ember.background, the fire detector's
   ApproxMedianBackground), updated everywhere except under the embers being shown, so a
   visitor who pauses is never absorbed. A blob whose core lies mostly on background brighter
   than ember.background.bright_dn is on a static light; the tracker never starts showing a
   track while its blob is on background.

Positions are intensity-weighted centroids (V above blob_dn), in pixels of the analysed
frame (pixel centres at integers).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import cv2
import numpy as np

from wfglink.detect.background import ApproxMedianBackground


@dataclass
class Blobs:
    x: np.ndarray = field(default_factory=lambda: np.zeros(0))
    y: np.ndarray = field(default_factory=lambda: np.zeros(0))
    diam: np.ndarray = field(default_factory=lambda: np.zeros(0))        # equivalent diameter, px
    peak: np.ndarray = field(default_factory=lambda: np.zeros(0))
    warm: np.ndarray = field(default_factory=lambda: np.zeros(0))        # warm fraction of the coloured pixels
    elong: np.ndarray = field(default_factory=lambda: np.zeros(0))
    on_bg: np.ndarray = field(default_factory=lambda: np.zeros(0, bool))
    boxes: list[tuple[int, int, int, int]] = field(default_factory=list)  # detection-scale boxes (x0, y0, x1, y1)

    def __len__(self) -> int:
        return int(self.x.size)


def size_limits(cfg: dict, f_px: float, scale: float) -> tuple[float, float]:
    """(smallest, largest) blob area in detection px for a phone between the ends of
    ember.distance_range_m, with the blur allowance on the largest."""
    e = cfg.get("ember") or {}
    d = e.get("detect") or {}
    z_min, z_max = (float(v) for v in e.get("distance_range_m", [1.0, 3.0]))
    b_min, b_max = (float(v) for v in e.get("blob_m", [0.008, 0.11]))
    d_min = b_min * f_px / z_max * scale
    d_max = b_max * f_px / z_min * scale
    return max(2.0, math.pi / 4 * d_min ** 2), math.pi / 4 * d_max ** 2 * float(d.get("area_blur_factor", 4.0))


class EmberDetector:
    def __init__(self, cfg: dict, f_px: float):
        e = cfg.get("ember") or {}
        d = e.get("detect") or {}
        b = e.get("background") or {}
        self.scale = float(e.get("detect_scale", 0.5))
        self.blob_dn = int(d.get("blob_dn", 170))
        self.core_dn = int(d.get("core_dn", 235))
        self.warm_dn = int(d.get("warm_dn", 80))
        self.ring_px = int(d.get("ring_px", 3))
        self.chroma_min = int(d.get("chroma_min", 60))
        self.warm_sat = int(d.get("warm_sat", 60))
        self.hue_lo, self.hue_hi = (int(v) for v in d.get("warm_hue", [0, 35]))
        self.hue_wrap = int(d.get("warm_hue_wrap", 172))
        self.warm_frac_min = float(d.get("warm_frac_min", 0.6))
        self.warm_px_min = int(d.get("warm_px_min", 3))
        self.warm_offset_max = float(d.get("warm_offset_max", 1.0))
        self.halo_min = float(d.get("halo_min", 0.5))
        self.max_elong = float(d.get("max_elongation", 12.0))
        self.max_candidates = int(d.get("max_candidates", 40))
        self.bg_bright = int(b.get("bright_dn", 200))
        self.bg_on_frac = float(b.get("on_frac", 0.5))
        self.background = ApproxMedianBackground(int(b.get("step_dn", 1)), int(b.get("warmup_frames", 5)))
        self.a_min, self.a_max = size_limits(cfg, f_px, self.scale)
        self._kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * self.ring_px + 1, 2 * self.ring_px + 1))
        self._protect: list[tuple[int, int, int, int]] = []

    @property
    def ready(self) -> bool:
        return self.background.ready

    def protect(self, boxes: list[tuple[int, int, int, int]]) -> None:
        """Detection-scale boxes the next background update leaves alone (the embers on screen)."""
        self._protect = list(boxes)

    def detect(self, image: np.ndarray) -> Blobs:
        s = self.scale
        small = image if s == 1.0 else cv2.resize(image, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        hue, sat, val = cv2.split(hsv)
        bg = self.background.apply(val)
        if bg is not None and self._protect:
            for x0, y0, x1, y1 in self._protect:
                self.background.bg[y0:y1, x0:x1] = bg[y0:y1, x0:x1]
        _, mask = cv2.threshold(val, self.blob_dn - 1, 255, cv2.THRESH_BINARY)
        n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        if n <= 1:
            return Blobs()
        areas = stats[1:, cv2.CC_STAT_AREA]
        cand = np.flatnonzero((areas >= self.a_min) & (areas <= self.a_max)) + 1
        if cand.size > self.max_candidates:
            cand = cand[np.argsort(-stats[cand, cv2.CC_STAT_AREA])[: self.max_candidates]]
        H, W = val.shape
        out: dict[str, list] = {k: [] for k in ("x", "y", "diam", "peak", "warm", "elong", "on_bg")}
        boxes = []
        pad = self.ring_px
        for i in cand:
            x0, y0, w, h, area = (int(v) for v in stats[i])
            X0, Y0, X1, Y1 = max(0, x0 - pad), max(0, y0 - pad), min(W, x0 + w + pad), min(H, y0 + h + pad)
            lab = labels[Y0:Y1, X0:X1] == i
            vv = val[Y0:Y1, X0:X1]
            vin = vv[lab]
            peak = int(vin.max())
            if peak < self.core_dn:
                continue
            ring = cv2.dilate(lab.view(np.uint8), self._kernel) > 0
            hh, ss = hue[Y0:Y1, X0:X1], sat[Y0:Y1, X0:X1]
            coloured = ring & (vv >= self.warm_dn) & (ss >= self.chroma_min)
            n_col = int(coloured.sum())
            warm = coloured & (ss >= self.warm_sat) & (((hh >= self.hue_lo) & (hh <= self.hue_hi)) | (hh >= self.hue_wrap))
            n_warm = int(warm.sum())
            frac = n_warm / max(n_col, 1)
            if n_warm < self.warm_px_min or frac < self.warm_frac_min or n_warm < self.halo_min * area:
                continue
            ys, xs = np.nonzero(lab)
            # The warm pixels ring the core, so their centre is the blob's centre; a bright patch
            # merely next to a phone's glow (a window fragment by the hand) has them on one side.
            wy, wx = np.nonzero(warm)
            off = math.hypot(float(wx.mean() - xs.mean()), float(wy.mean() - ys.mean()))
            if off > self.warm_offset_max * math.sqrt(area / math.pi):
                continue
            if xs.size >= 3:
                cov = np.cov(np.vstack([xs, ys]).astype(np.float64))
                ev = np.linalg.eigvalsh(cov)
                elong = math.sqrt(max(ev[1], 0.0) / max(ev[0], 0.25))
            else:
                elong = 1.0
            if elong > self.max_elong:
                continue
            wts = vin.astype(np.float64) - (self.blob_dn - 1)
            sw = float(wts.sum())
            cx = float((wts * xs).sum() / sw) + X0
            cy = float((wts * ys).sum() / sw) + Y0
            on_bg = False
            if bg is not None:
                core = lab & (vv >= self.core_dn)
                if core.any():
                    on_bg = bool((bg[Y0:Y1, X0:X1][core] >= self.bg_bright).mean() >= self.bg_on_frac)
            out["x"].append((cx + 0.5) / s - 0.5)
            out["y"].append((cy + 0.5) / s - 0.5)
            out["diam"].append(2.0 * math.sqrt(area / math.pi) / s)
            out["peak"].append(peak)
            out["warm"].append(frac)
            out["elong"].append(elong)
            out["on_bg"].append(on_bg)
            boxes.append((X0, Y0, X1, Y1))
        if not boxes:
            return Blobs()
        return Blobs(np.array(out["x"]), np.array(out["y"]), np.array(out["diam"]), np.array(out["peak"], float),
                     np.array(out["warm"]), np.array(out["elong"]), np.array(out["on_bg"], bool), boxes)
