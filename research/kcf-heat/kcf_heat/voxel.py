"""Front metrics and a voxel-sum radiometer on FDS cell-centred HRRPUV snapshots (model-to-model check, B.1).

Each voxel of volume dV radiates chi*HRRPUV*dV isotropically. A receiver at P with unit normal n gets
    q(P) = sum_v chi*HRRPUV_v*dV * max(0, cos theta_v) / (4*pi*r_v^2),   cos theta_v = (X_v - P).n / r_v,
with no absorption, no occlusion and no emission from hot soot outside the HRR voxels. chi is the run's own
-Q_RADI/HRR. Arrays are ordered [z, y, x] as in csiro-volume-dt5-120.npz.
"""
from __future__ import annotations

import numpy as np


def grid_volume(x, y, z):
    dx = float(np.median(np.diff(x))); dy = float(np.median(np.diff(y))); dz = float(np.median(np.diff(z)))
    return dx * dy * dz, (dx, dy, dz)


def voxel_flux(h, x, y, z, receiver, normal=(-1.0, 0.0, 0.0), chi=0.316, min_r=0.0):
    """Irradiance (kW/m2) at ``receiver`` (x, y, z) from one [z,y,x] HRRPUV snapshot (kW/m3)."""
    dv, _ = grid_volume(x, y, z)
    n = np.asarray(normal, dtype=float); n = n / np.linalg.norm(n)
    rx = x[None, None, :] - receiver[0]
    ry = y[None, :, None] - receiver[1]
    rz = z[:, None, None] - receiver[2]
    r2 = rx * rx + ry * ry + rz * rz
    r = np.sqrt(r2)
    with np.errstate(divide="ignore", invalid="ignore"):
        cos = (rx * n[0] + ry * n[1] + rz * n[2]) / r
        w = np.where((r > min_r) & (cos > 0), cos / (4.0 * np.pi * r2), 0.0)
    return float(chi * dv * np.sum(h * w))


def front_metrics(h, x, y, z, threshold_kw_m3=20.0, band_half_width_m=2.5, head_depth_m=25.0):
    """Centreline front geometry of one [z,y,x] snapshot.

    leading edge (le) and trailing edge (te): downstream / upstream faces of the outermost voxels in the centreline
    band |y| <= band_half_width with HRRPUV > threshold; depth = le - te;
    centroid: HRR-weighted mean x in the band over x in [le - head_depth, le];
    intensity: HRR per metre of front in the band (kW/m) = Byram intensity of the model head (threshold-free);
    flame_height: top face of the highest band voxel above threshold;
    effective_width: HRR of the head region (all y, x in [le - head_depth, le]) / intensity.
    """
    dv, (dx, dy, dz) = grid_volume(x, y, z)
    band = np.abs(y) <= band_half_width_m
    hb = h[:, band, :]
    hot = hb > threshold_kw_m3
    colhot = hot.any(axis=(0, 1))
    if not colhot.any():
        return None
    le = float(x[colhot].max() + dx / 2); te = float(x[colhot].min() - dx / 2)
    head = (x >= le - head_depth_m) & (x <= le)
    width_band = band.sum() * dy
    col = hb.sum(axis=(0, 1)) * dv / width_band          # kW per m of front per x column
    intensity = float(col[head].sum())
    centroid = float((col[head] * x[head]).sum() / col[head].sum()) if col[head].sum() > 0 else float("nan")
    zhot = hot.any(axis=(1, 2))
    flame_height = float(z[zhot].max() + dz / 2) if zhot.any() else float("nan")
    head_hrr = float(h[:, :, head].sum() * dv)
    return {"le": le, "te": te, "depth": le - te, "centroid": centroid, "intensity": intensity,
            "flame_height": flame_height, "effective_width": head_hrr / intensity if intensity > 0 else float("nan")}


def spread_rate(times, positions):
    """Least-squares slope (m/s)."""
    t = np.asarray(times, dtype=float); p = np.asarray(positions, dtype=float)
    return float(np.polyfit(t, p, 1)[0])
