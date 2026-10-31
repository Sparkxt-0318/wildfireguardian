"""SYNTHETIC scenario sets for tests and synthetic Track C instances (always labeled synthetic)."""
from __future__ import annotations

import numpy as np

from ..meta import HeatSource, ScenarioMeta
from ..scenario import ScenarioSet
from ._common import nominal_heat, parse_time


def _smooth_field(rng: np.random.Generator, h: int, w: int, scale: float) -> np.ndarray:
    """Unit-variance smooth random field: bilinear upsampling of coarse white noise."""
    ch, cw = int(np.ceil(h / scale)) + 2, int(np.ceil(w / scale)) + 2
    coarse = rng.standard_normal((ch, cw))
    yy = np.linspace(0, ch - 2, h)
    xx = np.linspace(0, cw - 2, w)
    y0, x0 = np.floor(yy).astype(int), np.floor(xx).astype(int)
    fy, fx = (yy - y0)[:, None], (xx - x0)[None, :]
    f = (coarse[y0][:, x0] * (1 - fy) * (1 - fx) + coarse[y0 + 1][:, x0] * fy * (1 - fx)
         + coarse[y0][:, x0 + 1] * (1 - fy) * fx + coarse[y0 + 1][:, x0 + 1] * fy * fx)
    sd = f.std()
    return (f - f.mean()) / (sd if sd > 0 else 1.0)


def synthetic(*, K: int = 8, height: int = 64, width: int = 64, cell_m: float = 375.0,
              x0: float = 0.0, y0: float = 0.0, crs_epsg: int = 3310,
              ignition_xy: tuple[float, float] | None = None, t_ignition_s: float = -3600.0,
              ros_m_s: float = 0.15, spread_dir_deg: float = 45.0, head_ratio: float = 3.0,
              ros_cv: float = 0.25, dir_sd_deg: float = 15.0, noise_sd: float = 0.2,
              noise_scale_cells: float = 8.0, horizon_s: float = 6 * 3600.0,
              burn_duration_s: float = 3600.0, unsupported_mask: np.ndarray | None = None,
              issue_time_utc: str = "2021-08-17T00:00:00Z", heat: HeatSource | None = None,
              seed: int = 0, model_version: str = "synthetic-ellipse-v1") -> ScenarioSet:
    """Elliptical-ish spread from one ignition with per-member rate, direction and smooth noise.

    ``spread_dir_deg`` is the fastest-spread direction, counter-clockwise from +x (east).
    Members are spatially coherent (one smooth noise field per member).
    """
    rng = np.random.default_rng(seed)
    transform = (float(cell_m), 0.0, float(x0), 0.0, -float(cell_m), float(y0) + height * float(cell_m))
    rows, cols = np.mgrid[0:height, 0:width]
    cx = x0 + (cols + 0.5) * cell_m
    cy = y0 + height * cell_m - (rows + 0.5) * cell_m
    if ignition_xy is None:
        ignition_xy = (x0 + width * cell_m / 2.0, y0 + height * cell_m / 2.0)
    dx, dy = cx - ignition_xy[0], cy - ignition_xy[1]
    dist = np.hypot(dx, dy)
    phi = np.arctan2(dy, dx)

    ig = np.empty((K, height, width))
    for k in range(K):
        ros_head = ros_m_s * float(np.exp(rng.normal(0.0, ros_cv) - 0.5 * ros_cv ** 2))
        theta = np.deg2rad(spread_dir_deg + rng.normal(0.0, dir_sd_deg))
        ros_back = ros_head / head_ratio
        v = ros_back + (ros_head - ros_back) * 0.5 * (1.0 + np.cos(phi - theta))
        noise = np.exp(noise_sd * _smooth_field(rng, height, width, noise_scale_cells))
        ig[k] = t_ignition_s + dist / v * noise
    ig = np.where(ig > horizon_s, np.inf, ig)
    ex = ig + burn_duration_s  # inf stays inf
    sup = np.ones_like(ig, dtype=bool)
    if unsupported_mask is not None:
        m = np.broadcast_to(np.asarray(unsupported_mask, dtype=bool), ig.shape)
        sup = ~m
        ig = np.where(m, np.nan, ig)
        ex = np.where(m, np.nan, ex)
    meta = ScenarioMeta(
        crs_epsg=crs_epsg, transform=transform, height=height, width=width, K=K,
        issue_time_utc=parse_time(issue_time_utc), horizon_s=float(horizon_s), source="synthetic",
        synthetic=True, model_version=model_version, weather_source="SYNTHETIC",
        heat_source=heat or nominal_heat(burn_duration_s, "SYNTHETIC nominal heat-source parameters"),
        provenance={"seed": int(seed), "generator": "hazard_contract.adapters.synthetic"},
    )
    return ScenarioSet(ig, ex, sup, meta)
