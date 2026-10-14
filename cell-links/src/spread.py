"""Minimal raster fire-spread model (minimum travel time with elliptical wind and slope effects).

Model (documented in docs/METHODS.md):
- Head-fire rate of spread on flat ground R_head (m/s), scenario input.
- Wind shape: elliptical fire with length-to-breadth ratio LB from Alexander (1985),
  LB = 1 + 8.729 (1 - exp(-0.030 U))^2.155 with U the 10 m wind speed in km/h.
  Spread rate in a direction at angle phi from the head direction (focus at the ignition):
  R(phi) = R_head (1 - e) / (1 - e cos phi), e = sqrt(1 - 1/LB^2).
- Slope: McArthur rule (Noble et al. 1980), R multiplied by exp(0.069 theta) where theta is the
  slope angle (degrees) along the direction of travel, positive upslope; factor floored at 0.2.
- Arrival times from Dijkstra shortest travel time on a 16-neighbour raster graph.
- All land above 1 m elevation burns; there is no fuel map (assumption).
"""
from __future__ import annotations

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

OFFSETS = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1),
           (-2, -1), (-2, 1), (2, -1), (2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2)]


def length_to_breadth(u10_kmh):
    return 1.0 + 8.729 * (1.0 - np.exp(-0.030 * u10_kmh)) ** 2.155


def arrival_times(z, res, ign_rc, r_head, wind_to_deg, u10_kmh, burnable=None, slope_coef=0.069):
    """Fire arrival time (s) on grid z (m) with cell size res (m).

    wind_to_deg: direction the wind blows TOWARD, degrees clockwise from north (grid north = row -1).
    """
    ny, nx = z.shape
    n = ny * nx
    burnable = np.ones_like(z, bool) if burnable is None else burnable
    LB = length_to_breadth(u10_kmh)
    e = np.sqrt(1 - 1 / LB**2)
    head = np.deg2rad(wind_to_deg)
    idx = np.arange(n).reshape(ny, nx)
    rows, cols, w = [], [], []
    for dr, dc in OFFSETS:
        r0, r1 = max(0, -dr), min(ny, ny - dr)
        c0, c1 = max(0, -dc), min(nx, nx - dc)
        src = idx[r0:r1, c0:c1]
        dst = idx[r0 + dr:r1 + dr, c0 + dc:c1 + dc]
        dist = res * np.hypot(dr, dc)
        bearing = np.arctan2(dc, -dr)                    # clockwise from north
        phi = bearing - head
        r_dir = r_head * (1 - e) / (1 - e * np.cos(phi))
        dz = z[r0 + dr:r1 + dr, c0 + dc:c1 + dc] - z[r0:r1, c0:c1]
        theta = np.degrees(np.arctan2(dz, dist))
        sf = np.maximum(np.exp(slope_coef * theta), 0.2)
        ok = burnable[r0:r1, c0:c1] & burnable[r0 + dr:r1 + dr, c0 + dc:c1 + dc]
        rows.append(src[ok])
        cols.append(dst[ok])
        w.append(dist / (r_dir * sf[ok]))
    G = csr_matrix((np.concatenate(w), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n))
    t = dijkstra(G, directed=True, indices=idx[ign_rc])
    return t.reshape(ny, nx), LB


def local_ros(t, res):
    """Local spread rate (m/s) from the arrival-time gradient, and spread direction (rad from north)."""
    gy, gx = np.gradient(t, res)
    g = np.hypot(gx, gy)
    with np.errstate(divide="ignore", invalid="ignore"):
        ros = np.where(np.isfinite(g) & (g > 0), 1.0 / g, np.nan)
    return ros
