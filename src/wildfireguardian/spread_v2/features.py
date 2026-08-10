"""Per-cell feature construction for the spread_v2 ignition model.

For every consecutive overpass transition ``k -> k+1`` of a fire we build a
supervised table: each row is a candidate cell (not yet detected as burning
at overpass ``k``, burnable, within a buffer of the active footprint) and the
label is whether that cell is detected as burning by overpass ``k+1``.

Feature groups (the names matter for the permutation-importance grouping):

- **state / geometry**: ``dist_to_fire_m``, ``active_frac_1500m``,
  ``active_frac_3000m``, ``n_active_adjacent`` — where the fire already is.
- **terrain**: ``elevation_m``, ``slope_deg``, ``elev_above_source_m`` (cell
  elevation minus the nearest active cell's — fire runs uphill).
- **fuel**: ``burnable_frac``.
- **fire-weather SEVERITY** (grouped for the importance sum — ⚠ the
  "severity ≫ direction" reading of that sum is WITHDRAWN as not
  established; docs/MODEL_CARD.md):
  ``wind_speed_ms``, ``temp_c``, ``rh_pct``, ``vpd_kpa``,
  ``days_since_rain``, ``precip_24h_mm``.
- **interval**: ``dt_hours`` — length of the overpass window (the label is
  "by next overpass", whose spacing varies 3-12 h).
- **DIRECTION control**: ``wind_alignment`` = cosine between the wind's
  blow-toward vector and the bearing from the nearest active cell to the
  candidate. ⚠ Its low measured importance does NOT establish that wind
  direction is unimportant — ERA5's 0.25° grid cannot resolve the wind the
  comparison is about, which is one reason the conclusion drawn from this
  control was withdrawn (docs/MODEL_CARD.md).

``dist_band`` (a non-feature tag) buckets each row by distance to the fire so
the evaluation can report a separate **far-band AUC**.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import grid as gridmod
from .weather import WeatherSeries

#: Ordered feature columns the model consumes.
FEATURE_COLUMNS: tuple[str, ...] = (
    "dist_to_fire_m",
    "active_frac_1500m",
    "active_frac_3000m",
    "n_active_adjacent",
    "elevation_m",
    "slope_deg",
    "elev_above_source_m",
    "burnable_frac",
    "wind_speed_ms",
    "temp_c",
    "rh_pct",
    "vpd_kpa",
    "days_since_rain",
    "precip_24h_mm",
    "dt_hours",
    "wind_alignment",
)

#: Severity features (used for the "severity, not direction" analysis).
SEVERITY_FEATURES: tuple[str, ...] = (
    "wind_speed_ms", "temp_c", "rh_pct", "vpd_kpa",
    "days_since_rain", "precip_24h_mm",
)


@dataclass
class StaticLayers:
    """Per-fire static rasters on the coarse grid (computed once)."""

    elevation: np.ndarray
    slope: np.ndarray
    burnable_frac: np.ndarray

    @classmethod
    def from_event(cls, event, grid: gridmod.CoarseGrid) -> "StaticLayers":
        elev = gridmod.elevation_on_grid(event, grid)
        return cls(
            elevation=elev,
            slope=gridmod.slope_deg(elev, grid.cell_size_m),
            burnable_frac=gridmod.burnable_fraction_on_grid(event, grid),
        )


def _active_fraction(active: np.ndarray, radius_cells: int) -> np.ndarray:
    """Fraction of cells within a square radius that are active."""
    from scipy.ndimage import uniform_filter

    size = 2 * radius_cells + 1
    return uniform_filter(active.astype(float), size=size, mode="constant", cval=0.0)


def _n_adjacent(active: np.ndarray) -> np.ndarray:
    """Count of the 8 neighbours that are active."""
    from scipy.ndimage import convolve

    k = np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]], dtype=float)
    return convolve(active.astype(float), k, mode="constant", cval=0.0)


def geometry_layers(active: np.ndarray, cell_size_m: float):
    """Distance-to-fire, nearest-source indices, and neighbourhood activity.

    Returns ``(dist_m, src_row, src_col, frac_1500, frac_3000, n_adj)``.
    """
    from scipy.ndimage import distance_transform_edt

    if not active.any():
        nan = np.full(active.shape, np.nan)
        zeros = np.zeros(active.shape)
        return nan, None, None, zeros, zeros, zeros
    dist_cells, (src_r, src_c) = distance_transform_edt(
        ~active, return_indices=True,
    )
    dist_m = dist_cells * cell_size_m
    r1 = max(1, int(round(1500.0 / cell_size_m)))
    r2 = max(1, int(round(3000.0 / cell_size_m)))
    return dist_m, src_r, src_c, _active_fraction(active, r1), _active_fraction(active, r2), _n_adjacent(active)


def dist_band(dist_m: np.ndarray) -> np.ndarray:
    """Bucket distance-to-fire into bands for stratified evaluation."""
    bands = np.full(dist_m.shape, "near", dtype=object)
    bands[dist_m > 1000.0] = "mid"
    bands[dist_m > 3000.0] = "far"
    return bands


def build_candidate_frame(
    event,
    grid: gridmod.CoarseGrid,
    static: StaticLayers,
    active: np.ndarray,
    when,
    dt_hours: float,
    weather: WeatherSeries | None,
    *,
    buffer_m: float = 6000.0,
    require_burnable: bool = True,
) -> pd.DataFrame:
    """Unlabelled feature rows for every candidate cell around ``active``.

    A candidate is a cell that is not yet active, lies within ``buffer_m`` of
    the active footprint, and (optionally) is burnable. Used both to attach
    labels for training (:func:`build_transition_frame`) and to drive the
    forward simulation (which has no future label).
    """
    cs = grid.cell_size_m
    dist_m, src_r, src_c, f1, f2, nadj = geometry_layers(active, cs)
    cand = (~active) & (dist_m <= buffer_m)
    if require_burnable:
        cand = cand & (static.burnable_frac > 0.05)
    if not cand.any():
        return pd.DataFrame(columns=("fire_id", "row", "col", *FEATURE_COLUMNS, "dist_band"))
    rr, cc = np.where(cand)

    # Direction from nearest active source to candidate (east, north).
    s_r = src_r[rr, cc]
    s_c = src_c[rr, cc]
    east = (cc - s_c).astype(float) * cs
    north = (s_r - rr).astype(float) * cs  # row increases southward
    norm = np.hypot(east, north)
    norm_safe = np.where(norm > 1e-6, norm, 1.0)
    ux, uy = east / norm_safe, north / norm_safe

    wx = weather.at(when) if weather is not None else None
    align = (ux * wx["wind_u"] + uy * wx["wind_v"]) if wx is not None else np.full(len(rr), np.nan)

    elev = static.elevation[rr, cc]
    src_elev = static.elevation[s_r, s_c]

    df = pd.DataFrame({
        "fire_id": event.meta.id,
        "row": rr,
        "col": cc,
        "dist_to_fire_m": dist_m[rr, cc],
        "active_frac_1500m": f1[rr, cc],
        "active_frac_3000m": f2[rr, cc],
        "n_active_adjacent": nadj[rr, cc],
        "elevation_m": elev,
        "slope_deg": static.slope[rr, cc],
        "elev_above_source_m": elev - src_elev,
        "burnable_frac": static.burnable_frac[rr, cc],
        "dt_hours": float(dt_hours),
        "wind_alignment": align,
    })
    for key in ("wind_speed_ms", "temp_c", "rh_pct", "vpd_kpa",
                "days_since_rain", "precip_24h_mm"):
        df[key] = wx[key] if wx is not None else np.nan
    df["dist_band"] = dist_band(df["dist_to_fire_m"].to_numpy())
    return df


def build_transition_frame(
    event,
    grid: gridmod.CoarseGrid,
    static: StaticLayers,
    overpasses: list[gridmod.Overpass],
    weather: WeatherSeries | None,
    *,
    buffer_m: float = 6000.0,
    require_burnable: bool = True,
) -> pd.DataFrame:
    """Supervised rows for all overpass transitions of one fire."""
    rows: list[pd.DataFrame] = []
    for k in range(len(overpasses) - 1):
        cur, nxt = overpasses[k], overpasses[k + 1]
        active = cur.cumulative_mask
        if not active.any():
            continue
        dt_hours = (nxt.time - cur.time).total_seconds() / 3600.0
        df = build_candidate_frame(
            event, grid, static, active, cur.time, dt_hours, weather,
            buffer_m=buffer_m, require_burnable=require_burnable,
        )
        if df.empty:
            continue
        newly = nxt.cumulative_mask & ~active  # label = 1 here
        df.insert(1, "op_from", cur.index)
        df.insert(4, "label", newly[df["row"].to_numpy(), df["col"].to_numpy()].astype(int))
        rows.append(df)

    if not rows:
        return pd.DataFrame(columns=("fire_id", "op_from", "row", "col", "label",
                                     *FEATURE_COLUMNS, "dist_band"))
    return pd.concat(rows, ignore_index=True)


def build_dataset(
    fire_ids: list[str],
    *,
    cell_size_m: float = gridmod.DEFAULT_CELL_M,
    gap_minutes: float = 90.0,
    buffer_m: float = 6000.0,
    data_dir=None,
    require_weather: bool = True,
) -> pd.DataFrame:
    """Build the pooled supervised dataset across multiple fires.

    Fires without usable ERA5 are skipped when ``require_weather`` (so the
    severity features are never silently NaN for a whole fire).
    """
    from . import data as datamod
    from .weather import weather_series_from_event

    frames: list[pd.DataFrame] = []
    for fid in fire_ids:
        ev = datamod.load_event(fid, data_dir=data_dir)
        ws = weather_series_from_event(ev)
        if ws is None and require_weather:
            continue
        g = gridmod.build_grid(ev.meta.bbox_wgs84, cell_size_m=cell_size_m)
        snaps = gridmod.overpass_snapshots(ev, g, gap_minutes=gap_minutes)
        if len(snaps) < 2:
            continue
        static = StaticLayers.from_event(ev, g)
        frames.append(build_transition_frame(
            ev, g, static, snaps, ws, buffer_m=buffer_m))
    if not frames:
        return pd.DataFrame(columns=("fire_id", "op_from", "row", "col", "label",
                                     *FEATURE_COLUMNS, "dist_band"))
    return pd.concat(frames, ignore_index=True)


__all__ = [
    "FEATURE_COLUMNS",
    "SEVERITY_FEATURES",
    "StaticLayers",
    "geometry_layers",
    "dist_band",
    "build_candidate_frame",
    "build_transition_frame",
    "build_dataset",
]
