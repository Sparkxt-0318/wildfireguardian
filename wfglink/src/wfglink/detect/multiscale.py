"""Multi-scale detection for file mode on large frames: one detector per scale, merged by size.

The detector's scales (top-hat kernel, prefilter, round-blob and streak limits, mirror test
blocks) are in analysed pixels and were chosen on 720p video. In high-resolution video an
ember close to the camera is much larger than that: a defocused streak 10 to 15 px wide is
mostly removed by the top-hat, or masked as a flame, while the same ember at half the
resolution is a normal detection. A blanket downscale would lose the far embers, which can
be a pixel or two wide. So file mode runs the detector at the native resolution and on
downscaled copies, and merges the results:

1. Levels. The native frame, then copies downscaled by 2, 4, ... (block averages of the
   colour frame, after cropping to a multiple of the factor), at most
   [detect.multiscale.max_octaves] of them and each only while it keeps at least
   [detect.multiscale.min_level_pixels] pixels. Frames with fewer than
   [detect.multiscale.min_frame_pixels] pixels get none: a 1280x720 frame, the size the
   detector's scales were chosen at, is analysed at one scale, so the 720p suites and the
   booth (which analyses at most that size, and never with coarse levels) are unchanged.
   Each level has its own detector: its own background, noise maps, mirror test and
   large-region mask, all in that level's pixels.
2. Source pixels. Coarse positions, lengths, widths and moments are converted to source
   pixels: x_src = f x + (f - 1) / 2 for a factor f (pixel centres at integers), lengths
   and widths times f, areas, fluxes and second moments times f^2.
3. Merge, coarse level by coarse level onto the finer result, on the detector's moments.
   A coarse detection covers the finer detections within [detect.multiscale.footprint_sigma]
   of its PSF sigmas (at least [detect.multiscale.footprint_min_px]) of its axis segment.
   Its PSF sigma in source px comes from its minor-axis second moment with the level's
   prefilter removed, s = f sqrt(lam2 - prefilter^2). The native top-hat and streak-width
   limits are assumed to measure an ember whole up to s = [detect.multiscale.native_max_sigma_px], a level
   of factor f up to f times that. A detection too large for the best actual matched finer level replaces
   the finer detections it covers, which are pieces of it (rims the top-hat left) holding
   little of its light, unless together they hold at least
   [detect.multiscale.replace_max_flux_share] of its flux: then the finer level measured
   the light whole, more sharply, or they are separate embers that merged at this scale,
   and they stand. A smaller coarse detection defers to the finer ones it covers, so a far
   ember keeps its native measurement. A coarse detection that covers nothing is kept when
   its s is at least [detect.multiscale.coarse_only_min_sigma_px] times the next finer
   level's factor. This separate empirical cutoff permits extended candidates absent at
   finer levels, including some removed by their large-region masks; it does not prove
   that a finer level could not have detected them.
4. Measurement. The file-mode streak method (detect/streaks.py) then runs once, on the
   detections that are kept, each on the residual of the level that measured it.

This merge is a size/flux heuristic: overlapping footprints or embers unresolved at all
levels can still lose or duplicate candidates. The tracker sees the merged candidates in
source pixels; `scale` records which level measured each one (1 = native).
"""
from __future__ import annotations

import cv2
import numpy as np

from wfglink.detect.candidates import Detections, Detector, DetectorState


def _mcfg(cfg: dict) -> dict:
    m = cfg.get("detect", {}).get("multiscale", {}) or {}
    return {"enabled": bool(m.get("enabled", False)),
            "min_frame_pixels": int(m.get("min_frame_pixels", 1843200)),
            "min_level_pixels": int(m.get("min_level_pixels", 129600)),
            "max_octaves": int(m.get("max_octaves", 2)),
            "native_max_sigma": float(m.get("native_max_sigma_px", 2.0)),
            "footprint_sigma": float(m.get("footprint_sigma", 2.5)),
            "footprint_min": float(m.get("footprint_min_px", 3.0)),
            "coarse_only_min_sigma": float(m.get("coarse_only_min_sigma_px", 1.0)),
            "replace_max_flux_share": float(m.get("replace_max_flux_share", 0.5))}


def level_factors(shape: tuple[int, int], cfg: dict) -> list[int]:
    """Downscale factors of the coarse levels for a frame of this (height, width)."""
    m = _mcfg(cfg)
    if not m["enabled"]:
        return []
    h, w = int(shape[0]), int(shape[1])
    out: list[int] = []
    if h * w < m["min_frame_pixels"]:
        return out
    for k in range(1, max(m["max_octaves"], 0) + 1):
        f = 2 ** k
        if (h // f) * (w // f) < m["min_level_pixels"]:
            break
        out.append(f)
    return out


def downscale(img: np.ndarray, f: int) -> np.ndarray:
    """Block average by an integer factor (the frame is cropped to a multiple of f first),
    so coarse pixel (i, j) covers source pixels f i .. f i + f - 1."""
    h, w = img.shape[:2]
    hh, ww = (h // f) * f, (w // f) * f
    return cv2.resize(img[:hh, :ww], (ww // f, hh // f), interpolation=cv2.INTER_AREA)


def _rescale(det: Detections, k: float, off: float, scale: float) -> Detections:
    return Detections(x=det.x * k + off, y=det.y * k + off, area=det.area * k * k, peak=det.peak,
                      flux=det.flux * k * k, lam1=det.lam1 * k * k, lam2=det.lam2 * k * k, theta=det.theta,
                      length=det.length * k, width=det.width * k, sat_frac=det.sat_frac, color=det.color,
                      flags=det.flags, scale=np.full(len(det), float(scale)))


def to_source(det: Detections, f: int) -> Detections:
    """Detections of a level downscaled by f, in source pixels."""
    if f == 1 or len(det) == 0:
        return det
    return _rescale(det, float(f), (f - 1) / 2.0, f)


def from_source(det: Detections, f: int) -> Detections:
    """The inverse of to_source: detections in the pixels of the level downscaled by f."""
    if f == 1 or len(det) == 0:
        return det
    return _rescale(det, 1.0 / f, -(f - 1) / (2.0 * f), f)


def _segment_distance(px, py, cx, cy, th, half):
    """Distance of points (px, py) from segments centred at (cx, cy) with direction th and
    half-length half (arrays broadcast)."""
    ux, uy = np.cos(th), np.sin(th)
    dx, dy = px - cx, py - cy
    t = np.clip(dx * ux + dy * uy, -half, half)
    return np.hypot(dx - t * ux, dy - t * uy)


def merge_levels(fine: Detections, coarse: Detections, sigma_src: np.ndarray, length_src: np.ndarray,
                 cfg: dict, finer_factor: int = 1) -> Detections:
    """Merge one coarse level (in source px) onto the finer result (see the module notes).

    sigma_src: each coarse detection's PSF sigma in source px; length_src: the length its
    footprint uses (source px); finer_factor: the next finer level's factor, used for
    unmatched candidates. For matched candidates the best actual fine.scale determines
    the empirical size cutoff; a missing intermediate level cannot measure native pieces
    more completely merely by existing."""
    m = _mcfg(cfg)
    if len(coarse) == 0:
        return fine
    nc = len(coarse)
    radius = np.maximum(m["footprint_min"], m["footprint_sigma"] * np.nan_to_num(sigma_src))
    half = 0.5 * np.nan_to_num(np.maximum(length_src, 0.0))
    large = np.nan_to_num(sigma_src) > m["native_max_sigma"] * finer_factor
    replace = large.copy()                    # large coarse detections that are kept
    covered = np.zeros(len(fine), bool)       # finer detections they replace
    hits = np.zeros(nc, bool)                 # coarse detections that cover a finer one
    if len(fine):
        from scipy.spatial import cKDTree

        tree = cKDTree(np.column_stack([fine.x, fine.y]))
        reach = half + radius
        for j, idx in enumerate(tree.query_ball_point(np.column_stack([coarse.x, coarse.y]), reach)):
            if not idx:
                continue
            idx = np.asarray(idx, int)
            d = _segment_distance(fine.x[idx], fine.y[idx], coarse.x[j], coarse.y[j], coarse.theta[j], half[j])
            inside = idx[d <= radius[j]]
            if inside.size:
                hits[j] = True
                # The accumulated fine result may contain only native pieces, with no
                # detection from the immediately preceding level. Use the best level
                # that actually measured these candidates, not an absent measurement.
                best_factor = float(np.max(fine.scale[inside]))
                replace[j] = sigma_src[j] > m["native_max_sigma"] * best_factor
                if not replace[j]:
                    continue
                # Pieces of a large ember (rims the top-hat left) hold little of its light;
                # finer detections that hold most of it measured it whole, more sharply (or
                # are separate embers that merged at this scale), and stand.
                share = np.nansum(fine.flux[inside]) / coarse.flux[j] if coarse.flux[j] > 0 else np.inf
                if share >= m["replace_max_flux_share"]:
                    replace[j] = False
                else:
                    covered[inside] = True
    # Found only at the coarse scale: kept when extended at the finer level too (a point-like
    # one is in that level's range, and that level found nothing there).
    keep_c = replace | (~hits & (np.nan_to_num(sigma_src) >= m["coarse_only_min_sigma"] * finer_factor))
    if not keep_c.any():
        return fine if not covered.any() else fine.subset(~covered)
    return concat(fine.subset(~covered), coarse.subset(keep_c))


def concat(a: Detections, b: Detections) -> Detections:
    if len(a) == 0:
        return b
    if len(b) == 0:
        return a
    da, db = a.as_dict(), b.as_dict()
    return Detections(**{k: np.concatenate([da[k], db[k]]) for k in da})


class MultiScaleDetector:
    """The detector of candidates.py at the native scale and, on large frames in file mode,
    on downscaled copies (module notes). Same interface as Detector: detect(), ready, state,
    reset(); detect() also applies the file-mode streak method when `refine` is set."""

    def __init__(self, cfg: dict, refine: bool = False, coarse: bool = True):
        self.cfg = cfg
        self.refine = refine
        self.coarse = coarse            # False: native scale only (the booth)
        self.prefilter = float(cfg["detect"].get("prefilter_sigma_px", 0.0))
        self.native = Detector(cfg)
        self.levels: list[tuple[int, Detector]] = []
        self._shape: tuple[int, int] | None = None
        self.counts: dict[int, int] = {}      # detections per level in the last frame, before the merge

    @property
    def ready(self) -> bool:
        return self.native.ready and all(d.ready for _, d in self.levels)

    @property
    def state(self) -> DetectorState:
        return self.native.state

    def reset(self) -> None:
        self.native.reset()
        for _, d in self.levels:
            d.reset()
        self.counts = {}

    def measure(self, det: Detections) -> Detections:
        """The file-mode streak method on the merged detections, each on the residual of the
        level that measured it (in that level's pixels)."""
        if not self.refine or len(det) == 0:
            return det
        from wfglink.detect.streaks import measure_streaks

        states = {1: self.native.state, **{f: d.state for f, d in self.levels}}
        if len(states) == 1:
            return measure_streaks(det, states[1], self.cfg)
        cols = {k: v.copy() for k, v in det.as_dict().items()}
        for f in np.unique(det.scale):
            idx = np.flatnonzero(det.scale == f)
            sub = measure_streaks(from_source(det.subset(idx), int(f)), states[int(f)], self.cfg)
            for k, v in to_source(sub, int(f)).as_dict().items():
                cols[k][idx] = v
        return Detections(**cols)

    def _setup(self, shape: tuple[int, int]) -> None:
        if self._shape == shape:
            return
        if self._shape is not None:
            # The native detector's noise/offset maps belong to the old shape too.
            self.native.reset()
        self._shape = shape
        factors = level_factors(shape, self.cfg) if self.coarse else []
        self.levels = [(f, Detector(self.cfg)) for f in factors]

    def detect(self, image: np.ndarray, mask: np.ndarray | None = None, *, measure: bool = True) -> Detections:
        self._setup(image.shape[:2])
        det = self.native.detect(image, mask)
        self.counts = {1: len(det)}
        # Preserve clipping before any colour averaging. Counts keep flag_min_px in source
        # pixels even when two clipped pixels fall within a single coarse sample.
        saturated = None
        if self.levels:
            if image.ndim == 3:
                below = cv2.inRange(image, (0, 0, 0), (self.native.sat_level - 1,) * 3)
                saturated = (below == 0).astype(np.float32)
            else:
                saturated = (image >= self.native.sat_level).astype(np.float32)
        mask_source = (np.asarray(mask) != 0).astype(np.float32) if mask is not None else None
        prev = 1
        for f, d in self.levels:
            # Average the original frame once at every factor; cascaded uint8 averages
            # round twice and no longer equal the stated block average at factor four.
            img = downscale(image, f)
            msk = None if mask_source is None else downscale(mask_source, f) > 0
            sat_counts = downscale(saturated, f) * (f * f)
            c = d.detect(img, msk, saturation_counts=sat_counts, pixels_per_sample=f * f)
            self.counts[f] = len(c)
            if len(c):
                # The merge uses the detector's moments; the streak method then runs once, on
                # the detections that are kept.
                sig = f * np.sqrt(np.maximum(np.asarray(c.lam2, np.float64) - self.prefilter ** 2, 0.0))
                det = merge_levels(det, to_source(c, f), sig, f * np.asarray(c.length, np.float64), self.cfg,
                                   finer_factor=prev)
            prev = f
        return self.measure(det) if measure else det
