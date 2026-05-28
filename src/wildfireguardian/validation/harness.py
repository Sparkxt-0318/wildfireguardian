"""End-to-end retrospective validation harness.

Given a :class:`ValidationCase` (region + event metadata + observed-data
paths), :func:`run_validation` executes the cellular-automaton spread
model under retrospective inputs, builds predicted perimeters at the
configured time horizons, and computes every metric from
:mod:`wildfireguardian.validation.metrics` against the observed data.

For Session 2, observed data may be stub / synthetic placeholders; real
KFS shapefile ingestion comes in Session 3. The pipeline is structured
so that swapping in real observed shapes does NOT change any call site.

The harness uses :class:`xarray.DataArray` rasters (from
:mod:`wildfireguardian.data_io.raster`) for DEM and fuel inputs, and a
single uniform :class:`wildfireguardian.spread_model.cellular_automaton.WindField`
for now. Spatially varying winds from KMA AWS interpolation come in
Session 3.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Sequence

from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from ..data_io.raster import load_dem, load_fuel_type, populate_firegrid
from ..spread_model.cellular_automaton import (
    CellState,
    FireGrid,
    WindField,
)
from ..spread_model.rothermel import KOREAN_PINUS
from ..utils.regions import RegionConfig
from .metrics import (
    PerimeterAtTime,
    brier_score,
    brier_skill_score,
    lead_time_gain,
    perimeter_iou,
    perimeter_sorensen_dice,
    perimeter_symmetric_difference_area_km2,
    temporal_perimeter_rmse,
)


# ---------------------------------------------------------------------------
# ValidationCase
# ---------------------------------------------------------------------------


@dataclass
class ValidationCase:
    """One retrospective validation case (e.g. Yeongdeok 2025).

    Attributes
    ----------
    region : RegionConfig
        The region preset (must have ``event_date_range`` set).
    observed_perimeters_path : Path | None
        Path to the observed final perimeter shapefile or GeoJSON.
        ``None`` if observed data not yet ingested (Session 2 stub case).
    observed_ignition_point_wgs84 : tuple[float, float] | None
        (lon, lat) approximate ignition location.
    observed_official_warnings : list[(datetime, area_threshold_m2)]
        Historical timeline of (warning_issued_at, burned_area_when_issued).
    notes : str
        Free-text caveats.
    """

    region: RegionConfig
    observed_perimeters_path: Path | None = None
    observed_ignition_point_wgs84: tuple[float, float] | None = None
    observed_official_warnings: list[tuple[datetime, float]] = field(default_factory=list)
    observed_total_burn_area_ha: float | None = None
    notes: str = ""


def load_case(manifest_path: Path) -> ValidationCase:
    """Load a ValidationCase from a JSON manifest under data/validation_cases/."""
    from ..utils.regions import lookup
    data = json.loads(Path(manifest_path).read_text())
    region = lookup(data["region"])
    warnings: list[tuple[datetime, float]] = []
    for w in data.get("observed_official_warnings", []):
        ts = datetime.fromisoformat(w["issued_at_iso"])
        warnings.append((ts, float(w["burned_area_m2_when_issued"])))

    obs_perim = data.get("observed_perimeters_path")
    return ValidationCase(
        region=region,
        observed_perimeters_path=Path(obs_perim) if obs_perim else None,
        observed_ignition_point_wgs84=tuple(data["observed_ignition_point_wgs84"])
            if data.get("observed_ignition_point_wgs84") else None,
        observed_official_warnings=warnings,
        observed_total_burn_area_ha=data.get("observed_total_burn_area_ha"),
        notes=data.get("notes", ""),
    )


# ---------------------------------------------------------------------------
# Model config
# ---------------------------------------------------------------------------


@dataclass
class ModelConfig:
    """Inputs for one retrospective model run.

    Defaults are tuned for the Yeongdeok 2025 dry-run case.
    """

    cell_size_m: float = 100.0
    wind_speed_midflame_ms: float = 5.0
    wind_from_deg: float = 270.0
    dead_moisture_1h: float = 0.08
    live_moisture_lfmc: float = 0.40
    residence_time_min: float = 30.0
    duration_min: float = 1440.0          # 24 hours
    dt_min: float = 2.0
    snapshot_every_min: float = 60.0      # snapshot every hour
    dem_source: str = "synthetic"
    fuel_source: str = "synthetic"


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


@dataclass
class ValidationResults:
    """Structured outputs of one validation run."""

    case: ValidationCase
    config: ModelConfig
    predicted_perimeters: list[PerimeterAtTime] = field(default_factory=list)
    observed_perimeter: BaseGeometry | None = None
    final_iou: float | None = None
    final_sorensen_dice: float | None = None
    final_symmetric_difference_km2: float | None = None
    brier_score_final: float | None = None
    brier_skill_score_final: float | None = None
    temporal_area_rmse_ha: dict[float, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        """Render to a plain dict, suitable for JSON serialisation."""
        return {
            "region": self.case.region.name,
            "config": self.config.__dict__,
            "n_predicted_snapshots": len(self.predicted_perimeters),
            "final_iou": self.final_iou,
            "final_sorensen_dice": self.final_sorensen_dice,
            "final_symmetric_difference_km2": self.final_symmetric_difference_km2,
            "brier_score_final": self.brier_score_final,
            "brier_skill_score_final": self.brier_skill_score_final,
            "temporal_area_rmse_ha": {str(k): v for k, v in self.temporal_area_rmse_ha.items()},
            "predicted_areas_m2": [p.area_m2 for p in self.predicted_perimeters],
            "predicted_times_min": [p.time_min for p in self.predicted_perimeters],
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# The harness
# ---------------------------------------------------------------------------


def _ignite_at_wgs84(grid: FireGrid, lon: float, lat: float) -> tuple[int, int]:
    """Convert a WGS84 (lon, lat) into a grid cell and ignite it.

    Falls back to the grid centre if the point is outside the grid bbox.
    """
    if not grid.is_georeferenced:
        # Fall back to grid centre for non-georeferenced grids.
        i, j = grid.nrows // 2, grid.ncols // 2
        grid.ignite_point(i, j)
        return i, j
    from pyproj import Transformer
    t = Transformer.from_crs("EPSG:4326", grid.crs, always_xy=True)
    x, y = t.transform(lon, lat)
    a, _b, c, _d, e, f = grid.affine  # type: ignore[misc]
    j = int((x - c) / a)
    i = int((y - f) / e)
    if not (0 <= i < grid.nrows and 0 <= j < grid.ncols):
        i, j = grid.nrows // 2, grid.ncols // 2
    grid.ignite_point(i, j)
    return i, j


def _load_observed_perimeter(case: ValidationCase) -> BaseGeometry | None:
    """Load the observed final perimeter as a shapely geometry, or None."""
    if case.observed_perimeters_path is None:
        return None
    path = Path(case.observed_perimeters_path)
    if not path.exists():
        return None
    if path.suffix == ".geojson":
        data = json.loads(path.read_text())
        # Take the union of all features.
        from shapely.ops import unary_union
        geoms = []
        for feat in data.get("features", []):
            if feat.get("geometry"):
                geoms.append(shape(feat["geometry"]))
        if not geoms:
            return None
        return unary_union(geoms)
    raise NotImplementedError(
        f"observed perimeter format {path.suffix!r} not yet supported"
    )


def run_validation(case: ValidationCase, config: ModelConfig | None = None) -> ValidationResults:
    """Execute the retrospective validation pipeline end to end.

    Steps:
    1. Load DEM and fuel-type rasters for the case's region.
    2. Construct a CRS-aware :class:`FireGrid` and populate metadata.
    3. Ignite at the observed point (or centre if unknown).
    4. Step the CA for ``config.duration_min`` minutes, recording perimeter
       snapshots at ``config.snapshot_every_min`` intervals.
    5. Load the observed perimeter (or None if Session 2 stub).
    6. Compute every metric and pack into a :class:`ValidationResults`.

    Returns
    -------
    ValidationResults
    """
    cfg = config or ModelConfig()
    notes: list[str] = []

    # 1. Rasters.
    dem = load_dem(case.region, source=cfg.dem_source, cell_size_m=cfg.cell_size_m)
    fuel = load_fuel_type(case.region, source=cfg.fuel_source, cell_size_m=cfg.cell_size_m)
    if dem.attrs.get("synthetic"):
        notes.append("DEM is SYNTHETIC; real NGII/SRTM ingestion is a Session 3 task.")
    if fuel.attrs.get("synthetic"):
        notes.append("fuel-type is SYNTHETIC; real KFS 임상도 ingestion is a Session 3 task.")

    # 2. Grid.
    grid = FireGrid.from_region(
        case.region, cell_size_m=cfg.cell_size_m,
        residence_time_min=cfg.residence_time_min,
    )
    populate_firegrid(
        grid, dem, fuel_type=fuel,
        fuel_code_to_model={1: KOREAN_PINUS},
    )
    grid.fuel_moisture[:] = cfg.live_moisture_lfmc

    # 3. Ignite.
    if case.observed_ignition_point_wgs84:
        lon, lat = case.observed_ignition_point_wgs84
        _ignite_at_wgs84(grid, lon, lat)
    else:
        grid.ignite_point(grid.nrows // 2, grid.ncols // 3, time_min=0.0)
        notes.append("ignition point not specified; defaulted to (nrows/2, ncols/3).")

    # 4. Step + snapshot.
    wind = WindField.from_meteo(cfg.wind_speed_midflame_ms, cfg.wind_from_deg)
    predicted: list[PerimeterAtTime] = []
    t = 0.0
    next_snap = 0.0
    while t < cfg.duration_min - 1e-9:
        if t >= next_snap - 1e-9:
            poly = grid.perimeter()
            predicted.append(PerimeterAtTime(
                time_min=t, polygon=poly,
                area_m2=grid.burned_area_m2(),
            ))
            next_snap += cfg.snapshot_every_min
        grid.step(cfg.dt_min, wind, current_time_min=t)
        t += cfg.dt_min
    # Final snapshot.
    poly = grid.perimeter()
    predicted.append(PerimeterAtTime(
        time_min=t, polygon=poly,
        area_m2=grid.burned_area_m2(),
    ))

    # 5. Observed.
    observed = _load_observed_perimeter(case)
    if observed is None and case.observed_total_burn_area_ha is None:
        notes.append(
            "no observed perimeter or area available; metrics that compare "
            "to ground-truth will be skipped or use placeholder values"
        )

    # 6. Metrics.
    res = ValidationResults(case=case, config=cfg, predicted_perimeters=predicted,
                            observed_perimeter=observed, notes=notes)
    final_pred = predicted[-1].polygon

    if observed is not None and final_pred is not None:
        res.final_iou = perimeter_iou(final_pred, observed)
        res.final_sorensen_dice = perimeter_sorensen_dice(final_pred, observed)
        res.final_symmetric_difference_km2 = perimeter_symmetric_difference_area_km2(
            final_pred, observed,
        )

        # Brier needs raster rep; convert observed polygon to a binary
        # raster on the grid and compare to a "probability" of 1.0 in
        # predicted-burned cells. This is a simplified single-run brier
        # (a proper one needs a MC ensemble — Session 3).
        if grid.is_georeferenced:
            import numpy as np
            import rasterio.features as rfeat

            transform = grid.affine
            from rasterio.transform import Affine
            obs_raster = rfeat.rasterize(
                [(observed, 1)],
                out_shape=(grid.nrows, grid.ncols),
                transform=Affine(*transform),  # type: ignore[arg-type]
                dtype=np.uint8,
                fill=0,
            )
            pred_prob = (grid.burned_mask().astype(np.float64))
            res.brier_score_final = brier_score(pred_prob, obs_raster.astype(np.float64))
            res.brier_skill_score_final = brier_skill_score(pred_prob, obs_raster.astype(np.float64))

    # Temporal RMSE — for Session 2 with stub observed, compare to a
    # linearly-growing area baseline from observed_total_burn_area_ha
    # over the event duration.
    if case.observed_total_burn_area_ha is not None and case.region.event_date_range is not None:
        start, end = case.region.event_date_range
        event_duration_h = (end - start).total_seconds() / 3600.0
        observed_series = []
        for h in (1.0, 3.0, 6.0, 12.0, 24.0):
            t_min = h * 60.0
            # linear growth model
            frac = min(1.0, h / max(event_duration_h, 1.0))
            area_m2 = case.observed_total_burn_area_ha * 10_000.0 * frac
            observed_series.append(PerimeterAtTime(
                time_min=t_min, polygon=None, area_m2=area_m2,
            ))
        res.temporal_area_rmse_ha = temporal_perimeter_rmse(
            predicted, observed_series,
            time_horizons_min=(60.0, 180.0, 360.0, 1440.0),
        )

    return res


__all__ = [
    "ValidationCase",
    "ModelConfig",
    "ValidationResults",
    "load_case",
    "run_validation",
]
