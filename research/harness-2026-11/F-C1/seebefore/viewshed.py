"""Line of sight as a required target height (F-C1).

For an observer eye E (ground-referenced elevation z_e) and a target point T at horizontal distance D, the surface
between them is sampled every ``step`` metres. With curvature-and-refraction drop c*s^2 (c = (1-k)/(2R)) applied to
every surface elevation relative to the observer's tangent plane, the sight line to a point h metres above the
target's surface clears every sample k (fraction f_k = s_k/D) iff

    z_e + f_k * (g_t + h - z_e) > g_k      <=>     h > (g_k - z_e)/f_k - (g_t - z_e)

so the minimum visible height is  h_req = max(0, max_k[(g_k - z_e)/f_k] - (g_t - z_e)).
A target of height H above its surface is visible iff H > h_req (strict). One pass serves every height threshold.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

R_EARTH = 6_371_000.0
K_REFRACTION = 0.13


@dataclass
class Surface:
    """Elevation raster in a projected CRS: z[row, col], row 0 at the NORTH edge (GeoTIFF convention)."""
    z: np.ndarray
    x0: float          # west edge
    y_top: float       # north edge
    res: float

    def sample(self, x, y):
        """Bilinear interpolation at points (x, y); NaN outside the raster or where any corner is NaN."""
        x = np.asarray(x, float)
        y = np.asarray(y, float)
        cf = (x - self.x0) / self.res - 0.5
        rf = (self.y_top - y) / self.res - 0.5
        cf = np.where(np.isfinite(cf), cf, -2.0)          # non-finite points fall outside (NaN result)
        rf = np.where(np.isfinite(rf), rf, -2.0)
        h, w = self.z.shape
        c0 = np.floor(cf).astype(np.int64)
        r0 = np.floor(rf).astype(np.int64)
        ok = (c0 >= 0) & (r0 >= 0) & (c0 < w - 1) & (r0 < h - 1)
        c0c = np.clip(c0, 0, w - 2)
        r0c = np.clip(r0, 0, h - 2)
        dc = cf - c0c
        dr = rf - r0c
        z = self.z
        v = (z[r0c, c0c] * (1 - dc) * (1 - dr) + z[r0c, c0c + 1] * dc * (1 - dr) +
             z[r0c + 1, c0c] * (1 - dc) * dr + z[r0c + 1, c0c + 1] * dc * dr)
        return np.where(ok, v, np.nan)


def required_height(surface: Surface, ox: float, oy: float, eye_heights, tx, ty, step: float = 15.0,
                    k: float = K_REFRACTION, max_samples_per_chunk: int = 4_000_000):
    """Minimum target height above the surface for line of sight, for each target and each eye height.

    Returns an array (len(eye_heights), n_targets). NaN where the surface is unknown on the path."""
    eyes = np.atleast_1d(np.asarray(eye_heights, float))
    tx = np.asarray(tx, float)
    ty = np.asarray(ty, float)
    n = tx.size
    out = np.full((eyes.size, n), np.nan)
    c = (1.0 - k) / (2.0 * R_EARTH)
    zo = float(surface.sample(ox, oy))
    if not np.isfinite(zo):
        return out
    d = np.hypot(tx - ox, ty - oy)
    gt = surface.sample(tx, ty) - c * d * d
    order = np.argsort(d)
    i = 0
    while i < n:
        # chunk by sample budget (targets sorted by distance)
        j = i
        budget = 0
        while j < n:
            ns = max(int(d[order[j]] // step), 1)
            if j > i and budget + ns > max_samples_per_chunk:
                break
            budget += ns
            j += 1
        idx = order[i:j]
        dd = d[idx]
        nmax = max(int(dd.max() // step), 1)
        s = np.arange(1, nmax + 1, dtype=float) * step                       # distances from observer
        valid = s[None, :] < dd[:, None]                                       # strictly before the target
        f = np.where(valid, s[None, :] / np.where(dd > 0, dd, 1.0)[:, None], np.nan)
        px = ox + f * (tx[idx] - ox)[:, None]
        py = oy + f * (ty[idx] - oy)[:, None]
        g = surface.sample(px, py) - c * (s[None, :] ** 2)
        bad = np.any(valid & ~np.isfinite(g), axis=1) | ~np.isfinite(gt[idx])
        for e_i, eye in enumerate(eyes):
            ze = zo + eye
            ratio = np.where(valid, (g - ze) / f, -np.inf)
            worst = np.max(ratio, axis=1) if ratio.shape[1] else np.full(idx.size, -np.inf)
            h = np.maximum(0.0, worst - (gt[idx] - ze))
            h = np.where(dd <= step, 0.0, h)                                   # no intervening sample
            h[bad] = np.nan
            out[e_i, idx] = h
        i = j
    return out


def subpoints(xy: np.ndarray, cell: float = 375.0, n: int = 3) -> np.ndarray:
    """n x n sub-points per cell centre, spaced cell/n, centred on the cell: shape (len(xy), n*n, 2)."""
    off = (np.arange(n) - (n - 1) / 2.0) * (cell / n)
    ox, oy = np.meshgrid(off, off)
    o = np.column_stack([ox.ravel(), oy.ravel()])
    return xy[:, None, :] + o[None, :, :]


def ring_points(x: float, y: float, radius: float = 250.0, n: int = 8) -> np.ndarray:
    a = np.arange(n) * 2 * np.pi / n
    return np.vstack([[x, y], np.column_stack([x + radius * np.cos(a), y + radius * np.sin(a)])])
