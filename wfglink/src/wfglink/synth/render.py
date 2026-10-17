"""Render one frame exposure of point sources (embers, sparks, lamps) with motion blur.

Method:
1. The exposure [t_start, t_start + exposure_s] is split into N_sub equal intervals and
   every source is sampled at the interval midpoints. N_sub = max(n_sub_min,
   ceil(samples_per_px x longest path length in px), ceil(samples_per_tumble_cycle x
   fastest tumbling frequency x exposure_s)), capped at n_sub_max. With samples_per_px = 2
   this is N_sub = max(8, ceil(2 max |v| exposure_s)), so samples are at most half a pixel
   apart and the streak is smooth.
2. Each sample carries flux x emission(t) / N_sub and is drawn as a Gaussian spot of its
   source's PSF sigma, integrated exactly over every pixel's area (pixel centres at
   integer coordinates): sample k adds w_k gx_k(i) gy_k(j) to pixel (column i, row j),
   with gx_k(i) = Phi((i + 1/2 - x_k) / s) - Phi((i - 1/2 - x_k) / s) and Phi the standard
   normal distribution function. A spot therefore has the same shape at every sub-pixel
   phase: its second moments are s^2 + 1/12 on both axes (the 1/12 is the pixel's own
   width), so a static source has no spurious streak length and a streak's moment length
   sqrt(12 (l1 - l2)) is its true length times sqrt(1 - 1 / N_sub^2) (the sampling of the
   exposure; under 1 percent short for N_sub >= 8). (Bilinear splatting followed by a blur, the
   usual shortcut, adds up to 1/4 px^2 of variance on one axis depending on the phase: a
   static spot then measures up to 1.7 px long and a 2.5 px horizontal streak 2.25 to
   2.87 px.) The profiles are cut at psf_cut_sigma x s + 1 px (5 s by default) and
   renormalised, so each sample's light is kept in full. The samples of one source share a canvas (their bounding box padded
   by the cut radius), which is the matrix product of their column and row profiles; the
   canvases of one sigma level are computed in one batched product and added into the
   frame. Canvases extend beyond the frame, so light from sources just outside the frame
   still lands inside it correctly.
3. The canvases are 3-channel (B, G, R): each sample is multiplied by its source's
   color ratio, which has unit BT.601 luma, so the luma of the rendered image integrates
   to the flux. The output is a float32 BGR image of linear intensity (flux units per
   px^2).

Rolling shutter: when readout_s > 0, image row r is exposed from
t_start + (r / H) readout_s. A source sample at exposure fraction f is taken at the time t
that solves t = t_start + f exposure_s + (y(t) / H) readout_s (fixed-point iteration,
which converges fast because |v_y| readout_s / H is small). This is exact up to the
sub-pixel row spread of the PSF.

Per-source truth for the frame: positions at the (row-dependent) exposure start, midpoint
and end, clamped to the source's lifetime; mean velocity = displacement / duration over
the part of the exposure the source was alive; streak length; and the flux actually
rendered (sum of the sample fluxes, whether or not all of it lands inside the frame).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy.special import ndtr

from wfglink.synth.particles import PointSources

TRUTH_KEYS = ("pid", "kind", "t_mid", "x_mid", "y_mid", "x_start", "y_start", "x_end", "y_end",
              "u", "v", "flux", "sigma_px", "alive_frac", "alive_mid", "streak_length_px", "group", "idx")


@dataclass
class RenderSettings:
    """Sub-frame sampling settings (the config's `render` section)."""

    n_sub_min: int = 8
    n_sub_max: int = 48
    samples_per_px: float = 2.0
    samples_per_tumble_cycle: float = 8.0
    rs_iterations: int = 10
    psf_cut_sigma: float = 5.0

    @classmethod
    def from_config(cls, cfg: dict | None) -> "RenderSettings":
        cfg = cfg or {}
        return cls(n_sub_min=int(cfg.get("n_sub_min", 8)), n_sub_max=int(cfg.get("n_sub_max", 48)),
                   samples_per_px=float(cfg.get("samples_per_px", 2.0)),
                   samples_per_tumble_cycle=float(cfg.get("samples_per_tumble_cycle", 8.0)),
                   rs_iterations=int(cfg.get("rs_iterations", 10)),
                   psf_cut_sigma=float(cfg.get("psf_cut_sigma", 5.0)))


def n_substeps(max_path_px: float, exposure_s: float, max_tumble_hz: float, settings: RenderSettings) -> int:
    """Number of sub-frame samples for one exposure."""
    n = max(settings.n_sub_min, int(math.ceil(settings.samples_per_px * max_path_px - 1e-9)),
            int(math.ceil(settings.samples_per_tumble_cycle * max_tumble_hz * exposure_s - 1e-9)))
    return int(min(max(n, 1), settings.n_sub_max))


def solve_row_times(src: PointSources, idx: np.ndarray, base_t: np.ndarray, readout_s: float,
                    height: int, n_iter: int, tol_s: float = 1e-10) -> np.ndarray:
    """Sample times with a rolling shutter: t = base_t + (y(t) / H) readout_s, per source row.

    Fixed-point iteration (at most n_iter steps, stopping when no time moves by more than
    tol_s). It contracts by |v_y| readout_s / H per step, a few percent for embers.
    """
    if readout_s <= 0 or idx.size == 0:
        return base_t
    ii = idx[:, None] if base_t.ndim == 2 else idx
    t = base_t
    for _ in range(max(1, n_iter)):
        _, y = src.position(ii, t)
        t_new = base_t + np.clip(y, 0.0, height - 1.0) / height * readout_s
        done = float(np.max(np.abs(t_new - t))) <= tol_s
        t = t_new
        if done:
            break
    return t


def draw_spots(x: np.ndarray, y: np.ndarray, w: np.ndarray, color: np.ndarray, sigma: np.ndarray,
               frame_size: Sequence[int], out: np.ndarray | None = None,
               owner: np.ndarray | None = None, n_sigma: float = 5.0) -> np.ndarray:
    """Add pixel-integrated Gaussian spots of weighted samples into a BGR frame.

    x, y, w: flat sample arrays (px, pixel centres at integers; weights in flux units);
    color (n, 3) BGR ratios, sigma (n,) PSF sigmas and owner (n,) source ids per sample.
    Sample k adds w_k color_k gx_k(i) gy_k(j) to pixel (column i, row j), where gx_k is the
    Gaussian of sigma_k integrated over the pixel's width, gx_k(i) = Phi((i + 1/2 - x_k) /
    sigma_k) - Phi((i - 1/2 - x_k) / sigma_k), and gy_k likewise over its height. Profiles
    are cut at n_sigma sigma + 1 px and renormalised, so each weight lands in full (part of
    it outside the frame near an edge, where it is dropped). The samples of one owner and
    sigma share a canvas (their bounding box padded by the cut radius) equal to the matrix
    product of their row and column profiles; all canvases of one sigma are computed in one
    batched product. Returns out, (H, W, 3) float32.
    """
    width, height = int(frame_size[0]), int(frame_size[1])
    if out is None:
        out = np.zeros((height, width, 3), np.float32)
    x = np.asarray(x, dtype=np.float64)
    if x.size == 0:
        return out
    y = np.asarray(y, dtype=np.float64)
    w = np.asarray(w, dtype=np.float64)
    color = np.asarray(color, dtype=np.float64).reshape(-1, 3)
    sigma = np.asarray(sigma, dtype=np.float64)
    owner = np.zeros(x.size, np.int64) if owner is None else np.asarray(owner)
    for s in np.unique(sigma):
        r = int(math.ceil(n_sigma * float(s))) + 1
        # Samples farther than the cut radius outside the frame cannot light it.
        sel = (sigma == s) & (w != 0) & (x > -r) & (x < width - 1 + r) & (y > -r) & (y < height - 1 + r)
        if not sel.any():
            continue
        order = np.argsort(owner[sel], kind="stable")
        px, py, pw, pc, po = (a[sel][order] for a in (x, y, w, color, owner))
        first = np.r_[True, po[1:] != po[:-1]]
        starts = np.nonzero(first)[0]
        gid = np.cumsum(first) - 1                      # canvas of each sample
        slot = np.arange(po.size) - starts[gid]         # position of the sample within its canvas
        cx0 = np.floor(np.minimum.reduceat(px, starts)).astype(np.int64) - r
        cy0 = np.floor(np.minimum.reduceat(py, starts)).astype(np.int64) - r
        wc = int((np.ceil(np.maximum.reduceat(px, starts)).astype(np.int64) + r - cx0).max()) + 1
        hc = int((np.ceil(np.maximum.reduceat(py, starts)).astype(np.int64) + r - cy0).max()) + 1
        inv = 1.0 / float(s)
        # Normal distribution function at the pixel edges (centre - 1/2), differenced.
        gx = np.diff(ndtr(((cx0[gid] - 0.5)[:, None] + np.arange(wc + 1) - px[:, None]) * inv), axis=1)
        gy = np.diff(ndtr(((cy0[gid] - 0.5)[:, None] + np.arange(hc + 1) - py[:, None]) * inv), axis=1)
        gx /= gx.sum(axis=1, keepdims=True)
        gy /= gy.sum(axis=1, keepdims=True)
        n_c, n_s = starts.size, int(np.diff(np.r_[starts, po.size]).max())
        cols = np.zeros((n_c, n_s, wc))
        cols[gid, slot] = gx
        one_color = bool(np.all(pc == pc[starts][gid]))
        rows = np.zeros((n_c, n_s, hc))
        if one_color:
            rows[gid, slot] = gy * pw[:, None]
            canvas = np.matmul(rows.transpose(0, 2, 1), cols)[..., None] * pc[starts][:, None, None, :]
        else:
            canvas = np.empty((n_c, hc, wc, 3))
            for c in range(3):
                rows[gid, slot] = gy * (pw * pc[:, c])[:, None]
                canvas[..., c] = np.matmul(rows.transpose(0, 2, 1), cols)
        canvas = canvas.astype(np.float32)
        for j in range(n_c):
            fx0, fy0 = int(cx0[j]), int(cy0[j])
            ax0, ax1 = max(fx0, 0), min(fx0 + wc, width)
            ay0, ay1 = max(fy0, 0), min(fy0 + hc, height)
            if ax1 <= ax0 or ay1 <= ay0:
                continue
            out[ay0:ay1, ax0:ax1] += canvas[j, ay0 - fy0:ay1 - fy0, ax0 - fx0:ax1 - fx0]
    return out


def _empty_truth() -> dict[str, np.ndarray]:
    t = {k: np.zeros(0) for k in TRUTH_KEYS}
    t["pid"] = np.zeros(0, np.int64)
    t["kind"] = np.zeros(0, "<U9")
    t["alive_mid"] = np.zeros(0, bool)
    t["group"] = np.zeros(0, np.int64)
    t["idx"] = np.zeros(0, np.int64)
    return t


def render_exposure(sources: Sequence[PointSources], t_start: float, exposure_s: float,
                    frame_size: Sequence[int], settings: RenderSettings | None = None, *,
                    readout_s: float = 0.0, n_sub: int | None = None,
                    out: np.ndarray | None = None) -> tuple[np.ndarray, dict[str, np.ndarray], int]:
    """Render the sources over one exposure. Returns (image, truth, n_sub).

    image: (H, W, 3) float32 linear BGR. truth: per-source arrays (TRUTH_KEYS) for every
    source alive during its exposure window; `group` and `idx` locate the source in
    `sources`. n_sub may be forced (tests); otherwise it follows the sampling rule.
    """
    settings = settings or RenderSettings()
    width, height = int(frame_size[0]), int(frame_size[1])
    t_lo, t_hi = t_start, t_start + exposure_s + max(readout_s, 0.0)
    fr3 = np.array([0.0, 0.5, 1.0])
    groups: list[dict[str, np.ndarray]] = []
    max_path, max_tumble = 0.0, 0.0
    for g, src in enumerate(sources):
        idx = src.alive_in(t_lo, t_hi)
        if idx.size == 0:
            continue
        base3 = t_start + fr3[None, :] * exposure_s + np.zeros((idx.size, 1))
        t3 = solve_row_times(src, idx, base3, readout_s, height, settings.rs_iterations)
        tb, td = src.t_birth[idx][:, None], src.t_death[idx][:, None]
        t3c = np.clip(t3, tb, td)
        dur = t3[:, 2] - t3[:, 0]
        alive_frac = np.where(dur > 0, (t3c[:, 2] - t3c[:, 0]) / np.where(dur > 0, dur, 1.0), 0.0)
        keep = alive_frac > 0
        if not keep.any():
            continue
        idx, t3, t3c, alive_frac = idx[keep], t3[keep], t3c[keep], alive_frac[keep]
        x3, y3, vx3, vy3 = src.state(idx[:, None], t3c)
        path = np.hypot(np.diff(x3, axis=1), np.diff(y3, axis=1)).sum(axis=1)
        max_path = max(max_path, float(path.max()))
        tum = src.tumble_hz[idx][src.tumble_amp[idx] > 0]
        if tum.size:
            max_tumble = max(max_tumble, float(tum.max()))
        dt_alive = t3c[:, 2] - t3c[:, 0]
        ok = dt_alive > 1e-12
        u = np.where(ok, (x3[:, 2] - x3[:, 0]) / np.where(ok, dt_alive, 1.0), vx3[:, 1])
        v = np.where(ok, (y3[:, 2] - y3[:, 0]) / np.where(ok, dt_alive, 1.0), vy3[:, 1])
        groups.append({
            "src": src, "g": g, "idx": idx, "t3": t3, "t3c": t3c, "x3": x3, "y3": y3, "u": u, "v": v,
            "alive_frac": alive_frac,
            "alive_mid": (t3[:, 1] >= src.t_birth[idx]) & (t3[:, 1] <= src.t_death[idx]),
        })
    if n_sub is None:
        n_sub = n_substeps(max_path, exposure_s, max_tumble, settings)
    fr = (np.arange(n_sub) + 0.5) / n_sub

    xs, ys, ws, cols, sigs, owners = [], [], [], [], [], []
    truth_parts = []
    n_owner = 0
    for gr in groups:
        src, idx = gr["src"], gr["idx"]
        base = t_start + fr[None, :] * exposure_s + np.zeros((idx.size, 1))
        tk = solve_row_times(src, idx, base, readout_s, height, settings.rs_iterations)
        x, y = src.position(idx[:, None], tk)
        e = src.emission(idx[:, None], tk)
        w = src.flux[idx][:, None] * e / n_sub
        xs.append(x.ravel())
        ys.append(y.ravel())
        ws.append(w.ravel())
        cols.append(np.repeat(src.color[idx], n_sub, axis=0))
        sigs.append(np.repeat(src.sigma[idx], n_sub))
        owners.append(np.repeat(np.arange(n_owner, n_owner + idx.size), n_sub))
        n_owner += idx.size
        x3, y3 = gr["x3"], gr["y3"]
        truth_parts.append({
            "pid": src.pid[idx], "kind": src.kind[idx], "t_mid": gr["t3c"][:, 1],
            "x_mid": x3[:, 1], "y_mid": y3[:, 1], "x_start": x3[:, 0], "y_start": y3[:, 0],
            "x_end": x3[:, 2], "y_end": y3[:, 2], "u": gr["u"], "v": gr["v"], "flux": w.sum(axis=1),
            "sigma_px": src.sigma[idx], "alive_frac": gr["alive_frac"], "alive_mid": gr["alive_mid"],
            "streak_length_px": np.hypot(x3[:, 2] - x3[:, 0], y3[:, 2] - y3[:, 0]),
            "group": np.full(idx.size, gr["g"], np.int64), "idx": idx.astype(np.int64),
        })
    if xs:
        image = draw_spots(np.concatenate(xs), np.concatenate(ys), np.concatenate(ws),
                           np.concatenate(cols), np.concatenate(sigs), frame_size, out=out,
                           owner=np.concatenate(owners), n_sigma=settings.psf_cut_sigma)
        truth = {k: np.concatenate([p[k] for p in truth_parts]) for k in TRUTH_KEYS}
    else:
        image = out if out is not None else np.zeros((height, width, 3), np.float32)
        truth = _empty_truth()
    return image, truth, int(n_sub)


def image_moments(img: np.ndarray) -> dict[str, float]:
    """Flux, centroid, principal second moments and streak length sqrt(12 (l1 - l2)) of a
    single-channel, background-free image (used by tests and diagnostics)."""
    img = np.asarray(img, dtype=np.float64)
    yy, xx = np.mgrid[0:img.shape[0], 0:img.shape[1]]
    f = img.sum()
    mx, my = (img * xx).sum() / f, (img * yy).sum() / f
    cxx = (img * (xx - mx) ** 2).sum() / f
    cyy = (img * (yy - my) ** 2).sum() / f
    cxy = (img * (xx - mx) * (yy - my)).sum() / f
    half, disc = (cxx + cyy) / 2, math.sqrt(((cxx - cyy) / 2) ** 2 + cxy ** 2)
    l1, l2 = half + disc, half - disc
    return {"flux": float(f), "x": float(mx), "y": float(my), "lam1": l1, "lam2": l2,
            "theta": 0.5 * math.atan2(2 * cxy, cxx - cyy), "length": math.sqrt(max(12 * (l1 - l2), 0.0))}
