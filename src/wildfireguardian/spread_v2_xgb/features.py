"""Feature assembly for the per-cell spread classifier (Deliverable 2).

For every candidate cell at every overpass transition we assemble a feature
row. Feature groups (matching the documented v2 methodology):

- **proximity**: ``dist_to_nearest_burning``, ``n_burning_within_500m/1km``,
  ``frp_sum_nearby``, ``frp_max_nearby`` (FRP from the *current* overpass).
- **terrain**: ``slope``, ``aspect``, ``slope_alignment`` (cos angle between the
  upslope direction and the fire→candidate spread direction), ``elevation_rel``.
- **fuel**: ``fuel_class`` (WorldCover code), ``burnable_frac_nearby``.
- **weather (ERA5)**: ``wind_speed``, ``wind_direction``, ``wind_alignment``
  (cos angle between wind-toward and spread direction), ``downwind_distance_proj``
  (m, spread vector projected onto wind-toward), ``temperature``,
  ``relative_humidity``, ``days_since_rain``. NaN when a fire has no ERA5
  (XGBoost handles NaN natively).
- **v1 proxy**: ``v1_alignment`` — cos angle between the fire's *observed recent
  growth direction* (computed from past overpasses only, no leakage) and the
  spread direction. The weather-free directional analogue of ``wind_alignment``,
  kept for the head-to-head comparison.

The spread direction for a candidate is the unit vector from its nearest
burning cell (via the EDT nearest-index transform) to the candidate, in
EPSG:5179 metres (east = +x, north = +y). Meridian convergence over a single
fire (~1–2°) is neglected — a documented approximation given ERA5's 31 km
coarseness already dominates the directional error budget.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import ndimage

from .candidates import Transition, count_within, max_within, sum_within
from .detections import ObservedSequence, overpass_frp_grid
from .era5 import WeatherSeries
from .grid import Grid
from .layers import StaticLayers

PROXIMITY = [
    "dist_to_nearest_burning", "n_burning_within_500m", "n_burning_within_1km",
    "frp_sum_nearby", "frp_max_nearby",
]
TERRAIN = ["slope", "aspect", "slope_alignment", "elevation_rel"]
FUEL = ["fuel_class", "burnable_frac_nearby"]
WEATHER = [
    "wind_speed", "wind_direction", "wind_alignment", "downwind_distance_proj",
    "temperature", "relative_humidity", "days_since_rain",
]
V1_PROXY = ["v1_alignment"]

ALL_FEATURES = PROXIMITY + TERRAIN + FUEL + WEATHER + V1_PROXY
NO_WEATHER_FEATURES = PROXIMITY + TERRAIN + FUEL + V1_PROXY
DISTANCE_ONLY_FEATURES = ["dist_to_nearest_burning"]

META_COLUMNS = ["fire_id", "k", "row", "col", "label", "dt_hours"]
FRP_RADIUS_M = 1000.0


def _centroid_xy(mask: np.ndarray, grid: Grid):
    if not mask.any():
        return None
    rr, cc = np.where(mask)
    return grid.x_centers[cc].mean(), grid.y_centers[rr].mean()


def _v1_growth_hat(seq: ObservedSequence, k: int, grid: Grid):
    """Observed recent-growth unit vector entering transition k (past data only).

    Displacement of the burned-area centroid from overpass k-1 to the cells
    newly added at overpass k. For k = 0 (no prior), uses the direction from the
    ignition seed centroid to the overpass-0 centroid. Returns (e, n) or None.
    """
    added_k = seq.cumulative[k] & (
        ~seq.cumulative[k - 1] if k >= 1 else np.zeros(grid.shape, bool)
    )
    if k >= 1:
        prev_c = _centroid_xy(seq.cumulative[k - 1], grid)
        new_c = _centroid_xy(added_k, grid)
    else:
        prev_c = _centroid_xy(seq.cumulative[0], grid)  # seed centroid
        # crude growth direction at the very first step: from seed centroid
        # outward to the seed's own spread is undefined → use None-safe fallback
        new_c = prev_c
    if prev_c is None or new_c is None:
        return None
    de, dn = new_c[0] - prev_c[0], new_c[1] - prev_c[1]
    norm = np.hypot(de, dn)
    if norm < 1e-6:
        return None
    return de / norm, dn / norm


def build_feature_table(
    fire_id: str,
    grid: Grid,
    seq: ObservedSequence,
    static: StaticLayers,
    transitions: list[Transition],
    weather: WeatherSeries | None,
) -> pd.DataFrame:
    """Assemble the full candidate feature table for one fire."""
    cs = grid.cell_size_m
    lon_grid, lat_grid = grid.centers_lonlat()
    rows_out: list[pd.DataFrame] = []

    # Precompute upslope unit vectors from aspect (downslope bearing, 0=N CW).
    up_bearing = np.radians((static.aspect_deg + 180.0) % 360.0)
    up_e = np.sin(up_bearing)
    up_n = np.cos(up_bearing)

    for t in transitions:
        burned = t.burned_now
        # Nearest burning cell index for every grid cell (for spread direction).
        _, (nr, nc) = ndimage.distance_transform_edt(
            ~burned, return_indices=True
        )
        n_burn_500 = count_within(burned, cs, 500.0)
        n_burn_1km = count_within(burned, cs, 1000.0)
        frp_grid = overpass_frp_grid(grid, seq.overpasses[t.k])
        frp_sum = sum_within(frp_grid, cs, FRP_RADIUS_M)
        frp_max = max_within(frp_grid, cs, FRP_RADIUS_M)

        r, c = t.rows, t.cols
        # Spread unit vector (nearest burning → candidate), EPSG:5179 metres.
        bx = grid.x_centers[nc[r, c]]
        by = grid.y_centers[nr[r, c]]
        cx = grid.x_centers[c]
        cy = grid.y_centers[r]
        dx = cx - bx
        dy = cy - by
        sdist = np.hypot(dx, dy)
        safe = np.where(sdist > 1e-6, sdist, 1.0)
        sx, sy = dx / safe, dy / safe

        df = pd.DataFrame({
            "fire_id": fire_id,
            "k": t.k,
            "row": r,
            "col": c,
            "label": t.labels,
            "dt_hours": t.dt_hours,
            # proximity
            "dist_to_nearest_burning": t.dist_to_burning,
            "n_burning_within_500m": n_burn_500[r, c],
            "n_burning_within_1km": n_burn_1km[r, c],
            "frp_sum_nearby": frp_sum[r, c],
            "frp_max_nearby": frp_max[r, c],
            # terrain
            "slope": static.slope_deg[r, c],
            "aspect": static.aspect_deg[r, c],
            "slope_alignment": up_e[r, c] * sx + up_n[r, c] * sy,
            "elevation_rel": static.elevation_rel[r, c],
            # fuel
            "fuel_class": static.fuel_class[r, c],
            "burnable_frac_nearby": static.burnable_frac_nearby[r, c],
        })

        # v1 observed-growth proxy alignment (constant direction per transition).
        v1 = _v1_growth_hat(seq, t.k, grid)
        df["v1_alignment"] = (v1[0] * sx + v1[1] * sy) if v1 is not None else np.nan

        # weather (ERA5)
        if weather is not None:
            w = weather.sample(t.time_now, lon_grid[r, c], lat_grid[r, c])
            df["wind_speed"] = w["wind_speed"]
            df["wind_direction"] = w["wind_direction"]
            df["wind_alignment"] = w["wind_toward_e"] * sx + w["wind_toward_n"] * sy
            df["downwind_distance_proj"] = dx * w["wind_toward_e"] + dy * w["wind_toward_n"]
            df["temperature"] = w["temperature"]
            df["relative_humidity"] = w["relative_humidity"]
            df["days_since_rain"] = w["days_since_rain"]
        else:
            for col in WEATHER:
                df[col] = np.nan

        rows_out.append(df)

    if not rows_out:
        return pd.DataFrame(columns=META_COLUMNS + ALL_FEATURES)
    return pd.concat(rows_out, ignore_index=True)


def distance_band(dist_m: np.ndarray) -> np.ndarray:
    """Bin distance-to-nearest-burning into the reporting bands (str labels)."""
    bins = [0.0, 375.0, 750.0, 1500.0, np.inf]
    labels = ["0-375", "375-750", "750-1500", ">1500"]
    idx = np.digitize(dist_m, bins[1:-1], right=True)
    return np.array(labels)[np.clip(idx, 0, len(labels) - 1)]


__all__ = [
    "PROXIMITY", "TERRAIN", "FUEL", "WEATHER", "V1_PROXY",
    "ALL_FEATURES", "NO_WEATHER_FEATURES", "DISTANCE_ONLY_FEATURES",
    "META_COLUMNS", "build_feature_table", "distance_band",
]
