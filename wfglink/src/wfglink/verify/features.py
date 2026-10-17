"""Per-hit features of one frame's detections (batched, O(n) gathers) and per-window track features.

Per-hit scalars (FEATURE_NAMES, float32): snr = peak / sigma at the point; log_flux; area;
width; length; sat_frac; color (0 when unknown) and color_nan; scale (the level that measured
the detection, detect/multiscale.py); bg_luma (background at the point); bg_grad (mean Sobel
magnitude of the background over the 9 x 9 core); large_near (share of the large-region mask
in the context window, 0 without a mask); codec (the mirror test's seed level at the point's
block over the peak, 0 when the mirror test is off); density = log(1 + other detections within
32 px); hotspot (the hotspot map before this frame is added); pre_presence = 3 x 3 maximum of
(luma three analysed frames back - this frame's background) / sigma, NaN with fewer than three
earlier frames in the ring; ctx_change = median |luma - previous luma| / sigma over the context
window without the 9 x 9 core (every second pixel), NaN without a previous frame. Both persistence features are NaN
while the camera is moving (the frames are not aligned). snr, codec and large_near use the
level that measured the detection, in that level's pixels; everything else is native.

Patches: z = (luma - background) / max(sigma at the centre, 1): a target crop of
patch.target_px around the rounded position, and the patch.context_px window area-averaged to
the same size, each then clipped to [-5, 30] and stored as asinh(z / 2); native analysis pixels
for every detection (a coarse level's detection is cropped from the native map at its source
position); pixels outside the picture are 0; stored float16 (n, 2, P, P).

Budget: at most the profile's max_dets_per_frame rows get features, chosen by priority (rows
of confirmed tracks, then of tentative kinematic tracks, then the rest, each in detection
order); the others have NaN features, zero patches and over_budget set.

Window features (WINDOW_NAMES) of a track summarise its last verify.window_hits measured hits:
kinematics from the measured positions and times, and medians (or extremes) of the hit
features of the hits that have features.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

FEATURE_NAMES = ("snr", "log_flux", "area", "width", "length", "sat_frac", "color", "color_nan", "scale",
                 "bg_luma", "bg_grad", "large_near", "codec", "density", "hotspot", "pre_presence", "ctx_change")
WINDOW_NAMES = ("n_hits", "hit_ratio", "age_s", "speed_med", "speed_cv", "net_disp", "straightness", "accel_rms",
                "turn_med_deg", "align_frac", "n_streak", "snr_med", "snr_min", "peak_cv", "bg_luma_med",
                "bg_grad_med", "large_near_max", "codec_med", "density_med", "hotspot_max", "pre_presence_med",
                "ctx_change_med", "sat_med", "color_med", "scale_max")
FI = {n: i for i, n in enumerate(FEATURE_NAMES)}
WI = {n: i for i, n in enumerate(WINDOW_NAMES)}

CORE_PX = 9                  # core window of bg_grad and the hole of the ctx_change annulus
DENSITY_RADIUS_PX = 32.0
STREAK_MIN_PX = 5.0          # a hit is a streak above this length (as track.angle_min_length_px)
ALIGN_DEG = 30.0
CHUNK = 512                  # detections per gather block (bounds the memory of the 51 x 51 windows)


@dataclass
class HitBatch:
    """Features of one frame's detections, one row per detection in detection order."""

    frame: int
    t: float
    values: np.ndarray        # (n, len(FEATURE_NAMES)) float32, NaN rows when over budget
    patches: np.ndarray       # (n, 2, P, P) float16
    over_budget: np.ndarray   # (n,) bool
    peak: np.ndarray          # (n,) the detections' peaks (for peak_cv)

    def __len__(self) -> int:
        return int(self.values.shape[0])

    def col(self, name: str) -> np.ndarray:
        return self.values[:, FI[name]]


@dataclass(frozen=True, slots=True)
class HitRecord:
    """One measured hit of a track, with its features (None when over budget)."""

    frame: int
    t: float
    x: float                  # measured position, analysis px
    y: float
    length: float
    theta: float
    peak: float
    values: np.ndarray | None
    patch: np.ndarray | None
    supported: bool = True    # the frame was in motion-supported time
    det_index: int = -1


@dataclass(frozen=True, slots=True)
class Kin:
    """Track context of a window: the track's first time and the frames it was alive from the
    window's first hit to its last (records, coasted ones included)."""

    t_first: float
    elapsed: int


def empty_batch(frame: int, t: float, patch_px: int) -> HitBatch:
    return HitBatch(frame, t, np.zeros((0, len(FEATURE_NAMES)), np.float32),
                    np.zeros((0, 2, patch_px, patch_px), np.float16), np.zeros(0, bool), np.zeros(0))


def _gather(img: np.ndarray, ix: np.ndarray, iy: np.ndarray, half: int, step: int = 1
            ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Float32 windows of img around integer points, at offsets -half, -half + step, ..., half
    (edge pixels repeated outside the picture); the mask of window pixels inside the picture;
    and which windows lie fully inside. Those are copied from a strided view (one block copy
    each); the others are gathered pixel by pixel."""
    from numpy.lib.stride_tricks import sliding_window_view

    h, w = img.shape[:2]
    k = 2 * half + 1
    offs = np.arange(-half, half + 1, step)
    n, m = ix.shape[0], offs.size
    vals = np.empty((n, m, m), np.float32)
    valid = np.ones((n, m, m), bool)
    inside = (ix >= half) & (ix < w - half) & (iy >= half) & (iy < h - half)
    if inside.any() and h >= k and w >= k:
        win = sliding_window_view(img, (k, k))[:, :, ::step, ::step]
        vals[inside] = win[iy[inside] - half, ix[inside] - half]
    else:
        inside[:] = False
    edge = np.flatnonzero(~inside)
    if edge.size:
        xx = ix[edge, None, None] + offs[None, None, :]
        yy = iy[edge, None, None] + offs[None, :, None]
        valid[edge] = (xx >= 0) & (xx < w) & (yy >= 0) & (yy < h)
        vals[edge] = img[np.clip(yy, 0, h - 1), np.clip(xx, 0, w - 1)]
    return vals, valid, inside


def _int_pos(x: np.ndarray, y: np.ndarray, shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    h, w = shape[:2]
    ix = np.clip(np.rint(np.nan_to_num(x)).astype(np.int64), 0, w - 1)
    iy = np.clip(np.rint(np.nan_to_num(y)).astype(np.int64), 0, h - 1)
    return ix, iy


def _level_pos(x: np.ndarray, y: np.ndarray, f: float) -> tuple[np.ndarray, np.ndarray]:
    """Source px to the px of a level downscaled by f (inverse of multiscale.to_source)."""
    if f == 1:
        return x, y
    return (x - (f - 1) / 2.0) / f, (y - (f - 1) / 2.0) / f


def _annulus_median(vals: np.ndarray, valid: np.ndarray, offs: np.ndarray, core: int) -> np.ndarray:
    """Median of each window (pixels at offsets offs on both axes) over its valid pixels outside
    the central core x core square."""
    hc = core // 2
    ring = (np.abs(offs)[:, None] > hc) | (np.abs(offs)[None, :] > hc)
    out = np.full(vals.shape[0], np.nan)
    full = valid[:, ring].all(axis=1)
    if full.any():
        out[full] = np.median(vals[full][:, ring], axis=1)
    for i in np.flatnonzero(~full):
        m = valid[i] & ring
        if m.any():
            out[i] = float(np.median(vals[i][m]))
    return out


def _sobel_mean(bg: np.ndarray, core: int) -> np.ndarray:
    """Mean 3 x 3 Sobel gradient magnitude over the central core x core pixels of each window."""
    k = bg.shape[1]
    c, h = k // 2, core // 2 + 1
    b = bg[:, c - h:c + h + 1, c - h:c + h + 1]
    gx = (b[:, :-2, 2:] + 2 * b[:, 1:-1, 2:] + b[:, 2:, 2:]) - (b[:, :-2, :-2] + 2 * b[:, 1:-1, :-2] + b[:, 2:, :-2])
    gy = (b[:, 2:, :-2] + 2 * b[:, 2:, 1:-1] + b[:, 2:, 2:]) - (b[:, :-2, :-2] + 2 * b[:, :-2, 1:-1] + b[:, :-2, 2:])
    return np.hypot(gx, gy).reshape(b.shape[0], -1).mean(axis=1)


def hit_features(det, state, ring, hot, motion=None, levels=None, *, patch_cfg, t: float, frame: int,
                 priority: np.ndarray | None = None, cap: int | None = None,
                 mirror_block: int | None = None) -> HitBatch:
    """Features of every detection of this frame (see the module notes).

    det: the frame's Detections (source px); state: the native DetectorState of this frame;
    ring: FrameRing of the earlier analysed frames (this frame not yet pushed); hot: HotspotMap
    (read before add); motion: this frame's MotionStatus or None; levels: {factor: DetectorState}
    of the coarse levels (detect/multiscale.py), or None; priority: per-row rank (0 first);
    cap: rows that get features; mirror_block: the mirror test's block (px of each level).
    """
    P = int(patch_cfg.target_px)
    n = len(det)
    if n == 0 or state is None or state.luma is None or state.background is None or state.sigma is None:
        b = empty_batch(frame, t, P)
        if n:
            b = HitBatch(frame, t, np.full((n, len(FEATURE_NAMES)), np.nan, np.float32),
                         np.zeros((n, 2, P, P), np.float16), np.ones(n, bool), np.asarray(det.peak, np.float64))
        return b
    luma, bg, sigma = state.luma, state.background, state.sigma
    shape = luma.shape[:2]
    x = np.asarray(det.x, np.float64)
    y = np.asarray(det.y, np.float64)
    order = np.arange(n) if priority is None else np.lexsort((np.arange(n), np.asarray(priority)))
    sel = np.sort(order[: (n if cap is None else max(0, int(cap)))])
    over = np.ones(n, bool)
    over[sel] = False
    vals = np.full((n, len(FEATURE_NAMES)), np.nan, np.float32)
    patches = np.zeros((n, 2, P, P), np.float16)
    peak_all = np.asarray(det.peak, np.float64)
    if sel.size == 0:
        return HitBatch(frame, t, vals, patches, over, peak_all)

    xs, ys = x[sel], y[sel]
    peak = peak_all[sel]
    scale = np.asarray(det.scale, np.float64)[sel] if len(det.scale) == n else np.ones(sel.size)
    color = np.asarray(det.color, np.float64)[sel]
    out = np.full((sel.size, len(FEATURE_NAMES)), np.nan, np.float64)
    out[:, FI["log_flux"]] = np.log(np.maximum(np.asarray(det.flux, np.float64)[sel], 1.0))
    out[:, FI["area"]] = np.asarray(det.area, np.float64)[sel]
    out[:, FI["width"]] = np.asarray(det.width, np.float64)[sel]
    out[:, FI["length"]] = np.asarray(det.length, np.float64)[sel]
    out[:, FI["sat_frac"]] = np.asarray(det.sat_frac, np.float64)[sel]
    out[:, FI["color_nan"]] = ~np.isfinite(color)
    out[:, FI["color"]] = np.where(np.isfinite(color), color, 0.0)
    out[:, FI["scale"]] = scale

    # Level features: snr, codec and large_near on the level that measured each detection.
    states = {1.0: state, **{float(f): s for f, s in (levels or {}).items()}}
    for f in np.unique(scale):
        rows = np.flatnonzero(scale == f)
        st = states.get(float(f))
        if st is None or st.sigma is None:
            st, lx, ly = state, xs[rows], ys[rows]
        else:
            lx, ly = _level_pos(xs[rows], ys[rows], float(f))
        ix, iy = _int_pos(lx, ly, st.sigma.shape)
        out[rows, FI["snr"]] = peak[rows] / np.maximum(st.sigma[iy, ix].astype(np.float64), 1e-6)
        ms = getattr(st, "mirror_seed", None)
        if ms is not None and mirror_block:
            by = np.clip(iy // int(mirror_block), 0, ms.shape[0] - 1)
            bx = np.clip(ix // int(mirror_block), 0, ms.shape[1] - 1)
            out[rows, FI["codec"]] = ms[by, bx].astype(np.float64) / np.maximum(peak[rows], 1e-6)
        else:
            out[rows, FI["codec"]] = 0.0
        lm = getattr(st, "large_mask", None)
        if lm is not None and cv2.countNonZero(lm) > 0:
            half = int(patch_cfg.context_px) // 2
            for a in range(0, rows.size, CHUNK):
                r = rows[a:a + CHUNK]
                mv, ok, _ = _gather(lm, ix[a:a + CHUNK], iy[a:a + CHUNK], half)
                out[r, FI["large_near"]] = ((mv > 0) & ok).sum(axis=(1, 2)) / np.maximum(ok.sum(axis=(1, 2)), 1)
        else:
            out[rows, FI["large_near"]] = 0.0

    # Density among all of this frame's detections.
    if n > 1:
        from scipy.spatial import cKDTree

        tree = cKDTree(np.column_stack([np.nan_to_num(x), np.nan_to_num(y)]))
        cnt = tree.query_ball_point(np.column_stack([xs, ys]), DENSITY_RADIUS_PX, return_length=True)
        out[:, FI["density"]] = np.log1p(np.maximum(np.asarray(cnt, np.float64) - 1.0, 0.0))
    else:
        out[:, FI["density"]] = 0.0
    out[:, FI["hotspot"]] = hot.read(xs, ys, t) if hot is not None else 0.0

    # Native windows: background, gradient, persistence, patches.
    moving = bool(motion is not None and getattr(motion, "unsupported", False))
    prev1 = ring.back(1) if ring is not None else None
    prev3 = ring.back(3) if ring is not None else None
    prev1 = prev1 if prev1 is not None and prev1.luma.shape == shape and not moving else None
    prev3 = prev3 if prev3 is not None and prev3.luma.shape == shape and not moving else None
    ix, iy = _int_pos(xs, ys, shape)
    sig_c = np.maximum(sigma[iy, ix].astype(np.float64), 1.0)
    out[:, FI["bg_luma"]] = bg[iy, ix]
    half = int(patch_cfg.context_px) // 2
    th = P // 2
    fac = int(patch_cfg.context_px) // P
    offs2 = np.arange(-half, half + 1, 2)            # ctx_change: every second pixel
    for a in range(0, sel.size, CHUNK):
        b = slice(a, a + CHUNK)
        L, ok, inside = _gather(luma, ix[b], iy[b], half)
        B, _, _ = _gather(bg, ix[b], iy[b], half)
        sc = sig_c[b][:, None, None]
        out[b, FI["bg_grad"]] = _sobel_mean(B, CORE_PX)
        D = L - B
        if not inside.all():
            D[~ok] = 0.0
        m = D.shape[0]
        target = D[:, half - th:half + th + 1, half - th:half + th + 1] / sc
        context = D.reshape(m, P, fac, P, fac).mean(axis=(2, 4)) / sc
        patches[sel[b], 0] = np.arcsinh(np.clip(target, -5.0, 30.0) / 2.0).astype(np.float16)
        patches[sel[b], 1] = np.arcsinh(np.clip(context, -5.0, 30.0) / 2.0).astype(np.float16)
        if prev1 is not None:
            L1, _, _ = _gather(prev1.luma, ix[b], iy[b], half, step=2)
            out[b, FI["ctx_change"]] = _annulus_median(np.abs(L[:, ::2, ::2] - L1) / sc, ok[:, ::2, ::2], offs2,
                                                       CORE_PX)
        if prev3 is not None:
            L3, ok3, _ = _gather(prev3.luma, ix[b], iy[b], 1)
            B3 = B[:, half - 1:half + 2, half - 1:half + 2]
            pp = np.where(ok3, (L3 - B3) / sc, -np.inf)
            out[b, FI["pre_presence"]] = pp.reshape(pp.shape[0], -1).max(axis=1)
    vals[sel] = out.astype(np.float32)
    return HitBatch(frame, t, vals, patches, over, peak_all)


# Window features --------------------------------------------------------------------------

def _pmed(v: list[float]) -> float:
    """Median of the finite values of a short list (plain Python: windows hold a few hits)."""
    v = sorted(x for x in v if math.isfinite(x))
    n = len(v)
    if not n:
        return math.nan
    return v[n // 2] if n % 2 else 0.5 * (v[n // 2 - 1] + v[n // 2])


def _pcv(v: list[float]) -> float:
    """Population standard deviation over the absolute mean of the finite values (NaN below two)."""
    v = [x for x in v if math.isfinite(x)]
    if len(v) < 2:
        return math.nan
    m = sum(v) / len(v)
    if not abs(m) > 0:
        return math.nan
    return math.sqrt(sum((x - m) ** 2 for x in v) / len(v)) / abs(m)


def _axis_off_deg(a: float) -> float:
    """Absolute difference of two axes (radians, mod 180 degrees), in degrees within [0, 90]."""
    return abs(math.degrees(math.remainder(a, math.pi)))


def window_features(hits: list[HitRecord], kin: Kin) -> np.ndarray:
    """WINDOW_NAMES over the given measured hits (oldest first) of one track."""
    nan = math.nan
    out = [nan] * len(WINDOW_NAMES)
    n = len(hits)
    out[WI["n_hits"]] = n
    out[WI["n_streak"]] = 0
    if n == 0:
        return np.array(out)
    out[WI["hit_ratio"]] = n / max(int(kin.elapsed), n)
    out[WI["age_s"]] = hits[-1].t - kin.t_first
    t = [h.t for h in hits]
    x = [h.x for h in hits]
    y = [h.y for h in hits]
    streak = [i for i, h in enumerate(hits) if math.isfinite(h.length) and h.length > STREAK_MIN_PX
              and math.isfinite(h.theta)]
    out[WI["n_streak"]] = len(streak)
    if n >= 2:
        dts = [t[i] - t[i - 1] for i in range(1, n)]
        dxy = [(x[i] - x[i - 1], y[i] - y[i - 1]) for i in range(1, n)]
        seg = [math.hypot(dx, dy) for dx, dy in dxy]
        speeds = [s_ / d_ for s_, d_ in zip(seg, dts) if d_ > 0]
        out[WI["speed_med"]] = _pmed(speeds)
        out[WI["speed_cv"]] = _pcv(speeds)
        net = math.hypot(x[-1] - x[0], y[-1] - y[0])
        path = sum(seg)
        out[WI["net_disp"]] = net
        out[WI["straightness"]] = net / path if path > 0 else nan
        if n >= 3 and all(d_ > 0 for d_ in dts):
            vel = [(dx / d_, dy / d_) for (dx, dy), d_ in zip(dxy, dts)]
            tm = [0.5 * (t[i] + t[i - 1]) for i in range(1, n)]
            acc2 = []
            for i in range(1, len(vel)):
                dtm = tm[i] - tm[i - 1]
                if dtm > 0:
                    acc2.append(((vel[i][0] - vel[i - 1][0]) / dtm) ** 2 + ((vel[i][1] - vel[i - 1][1]) / dtm) ** 2)
            out[WI["accel_rms"]] = math.sqrt(sum(acc2) / len(acc2)) if acc2 else nan
            ang = [math.atan2(dy, dx) for dx, dy in dxy]
            turn = [abs(math.degrees(math.remainder(ang[i] - ang[i - 1], 2 * math.pi))) for i in range(1, len(ang))
                    if seg[i] > 1e-6 and seg[i - 1] > 1e-6]
            out[WI["turn_med_deg"]] = _pmed(turn)
        if streak and net > 1e-6:
            heading = math.atan2(y[-1] - y[0], x[-1] - x[0])
            out[WI["align_frac"]] = sum(_axis_off_deg(hits[i].theta - heading) <= ALIGN_DEG for i in streak) / len(streak)
    out[WI["peak_cv"]] = _pcv([h.peak for h in hits])
    feats = [h.values for h in hits if h.values is not None]
    if feats:
        F = np.vstack(feats).astype(np.float64)
        F[:, FI["color"]] = np.where(F[:, FI["color_nan"]] > 0, np.nan, F[:, FI["color"]])
        med, lo, hi = _col_stats(F)
        for w_name, f_name in _MEDIANS:
            out[WI[w_name]] = med[FI[f_name]]
        out[WI["snr_min"]] = lo[FI["snr"]]
        for w_name, f_name in _MAXIMA:
            out[WI[w_name]] = hi[FI[f_name]]
    return np.array(out, np.float64)


_MEDIANS = (("snr_med", "snr"), ("bg_luma_med", "bg_luma"), ("bg_grad_med", "bg_grad"), ("codec_med", "codec"),
            ("density_med", "density"), ("pre_presence_med", "pre_presence"), ("ctx_change_med", "ctx_change"),
            ("sat_med", "sat_frac"), ("color_med", "color"))
_MAXIMA = (("large_near_max", "large_near"), ("hotspot_max", "hotspot"), ("scale_max", "scale"))


def _col_stats(F: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per column of F: median, minimum and maximum over the finite values (NaN when none)."""
    ok = np.isfinite(F)
    cnt = ok.sum(axis=0)
    srt = np.sort(np.where(ok, F, np.inf), axis=0)
    j = np.arange(F.shape[1])
    a = np.clip((cnt - 1) // 2, 0, F.shape[0] - 1)
    b = np.clip(cnt // 2, 0, F.shape[0] - 1)
    has = cnt > 0
    med = np.where(has, 0.5 * (srt[a, j] + srt[b, j]), np.nan)
    lo = np.where(has, srt[0], np.nan)
    hi = np.where(has, srt[np.clip(cnt - 1, 0, F.shape[0] - 1), j], np.nan)
    return med, lo, hi


def window_patches(hits: list[HitRecord]) -> np.ndarray | None:
    """The patches of the hits that have features, (k, 2, P, P) float16, or None."""
    ps = [h.patch for h in hits if h.patch is not None and h.values is not None]
    return np.stack(ps) if ps else None
