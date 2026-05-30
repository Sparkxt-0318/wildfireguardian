"""End-to-end retrospective validation harness.

Given a :class:`ValidationCase` (region + event metadata + observed-data
paths), :func:`run_validation` executes the cellular-automaton spread
model under retrospective inputs, builds predicted perimeters at the
configured time horizons, and computes every metric from
:mod:`wildfireguardian.validation.metrics` against the observed data.

Session 3 additions:

- :func:`run_validation_with_baselines` runs OUR model + two baselines
  (persistence and isotropic) and compares all three to a
  time-indexed observed perimeter series.
- The harness now respects time-indexed observed perimeters (one
  polygon per snapshot time), so IoU / Dice can be computed at the
  same horizons (1 h, 3 h, 6 h, 24 h) for prediction vs observation.
- All metric outputs carry data-provenance tags from upstream rasters,
  so the report cannot accidentally claim "Yeongdeok IoU 0.6" without
  flagging the SRTM-DEM / synthetic-wind / approximate-observed
  qualifications.

The harness uses :class:`xarray.DataArray` rasters (from
:mod:`wildfireguardian.data_io.raster`) for DEM and fuel inputs, and a
single uniform :class:`wildfireguardian.spread_model.cellular_automaton.WindField`
for the cellular automaton. Spatially-varying winds from KMA AWS
interpolation come in Round 2.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Sequence

import numpy as np
from pyproj import Transformer
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from ..data_io.raster import load_dem, load_fuel_type, populate_firegrid
from ..spread_model.cellular_automaton import (
    CellState,
    FireGrid,
    GriddedWindField,
    WindField,
)
from ..spread_model.rothermel import KOREAN_PINUS, compute_spread_rate
from ..utils.regions import KOREA_2000_UNIFIED, RegionConfig
from .baselines import (
    BaselineConfig,
    run_isotropic_baseline,
    run_persistence_baseline,
)
from .metrics import (
    PerimeterAtTime,
    brier_score,
    brier_skill_score,
    fraction_of_observed_captured,
    front_position_error_m,
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
    # Session 4: initialise the fire from a finite established front (a disc)
    # rather than a single cell, to skip the discretisation warm-up transient
    # (see docs/methodology/spread_warmup.md). 0.0 = single-cell (legacy).
    # This radius is a PRINCIPLED initialisation choice, NOT tuned to the
    # observed perimeter.
    ignition_radius_m: float = 0.0
    # Session 6 fire-type physics (each gated for ablation; default OFF so the
    # Session-5 surface-only baseline is reproduced exactly).
    use_topographic_wind: bool = False
    wind_10m_ms: float | None = None     # ambient 10-m wind for topo field
    waf: float = 0.10                    # 10-m → midflame (Andrews 2012 Korean pine)
    use_crown_fire: bool = False
    use_spotting: bool = False
    spotting_seed: int = 0
    # Session 7: tree-crown foliar moisture (%) for the Van Wagner check.
    # ``None`` reproduces the Session-6 BUG (reuse the surface LFMC, which is
    # the drought-cured understory moisture, ~40% — physically wrong for live
    # tree crowns). The corrected value is the MEASURED Korean foliar moisture
    # (119%); a drought-stressed value is ~80-90%. Decoupling this from the
    # surface LFMC is the Session-7 bug fix.
    crown_foliar_moisture_pct: float | None = None


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


def _ignite_at_wgs84(
    grid: FireGrid, lon: float, lat: float, radius_m: float = 0.0,
) -> tuple[int, int]:
    """Convert a WGS84 (lon, lat) into a grid cell and ignite it.

    If ``radius_m > 0`` the fire is initialised as a disc of that radius
    (skipping the single-cell discretisation warm-up; see
    ``docs/methodology/spread_warmup.md``). Falls back to the grid centre
    if the point is outside the grid bbox.
    """
    if not grid.is_georeferenced:
        # Fall back to grid centre for non-georeferenced grids.
        i, j = grid.nrows // 2, grid.ncols // 2
    else:
        from pyproj import Transformer
        t = Transformer.from_crs("EPSG:4326", grid.crs, always_xy=True)
        x, y = t.transform(lon, lat)
        a, _b, c, _d, e, f = grid.affine  # type: ignore[misc]
        j = int((x - c) / a)
        i = int((y - f) / e)
        if not (0 <= i < grid.nrows and 0 <= j < grid.ncols):
            i, j = grid.nrows // 2, grid.ncols // 2
    if radius_m > 0.0:
        grid.ignite_disc(i, j, radius_m=radius_m)
    else:
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
        _ignite_at_wgs84(grid, lon, lat, radius_m=cfg.ignition_radius_m)
    else:
        if cfg.ignition_radius_m > 0.0:
            grid.ignite_disc(grid.nrows // 2, grid.ncols // 3,
                             radius_m=cfg.ignition_radius_m, time_min=0.0)
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


# ---------------------------------------------------------------------------
# Session 3: full retrospective with baselines + time-indexed observed
# ---------------------------------------------------------------------------


def load_observed_perimeter_series(case: ValidationCase) -> list[PerimeterAtTime]:
    """Load the case's observed perimeter time series in EPSG:5179.

    Reads a GeoJSON file that follows the schema of
    ``data/validation_cases/yeongdeok_2025_perimeter_approx.geojson``:
    each feature has properties ``time_min_since_ignition`` and
    ``area_m2``, plus the wind-aligned ellipse geometry in WGS84.

    The geometries are reprojected to EPSG:5179 so that they can be
    compared apples-to-apples with our model's perimeters (which live in
    EPSG:5179 metres).

    Returns an empty list if the perimeter file is missing.
    """
    if case.observed_perimeters_path is None:
        return []
    path = Path(case.observed_perimeters_path)
    if not path.is_absolute():
        # interpret relative paths as relative to the project root
        repo_root = Path(__file__).resolve().parents[3]
        path = repo_root / path
    if not path.exists():
        return []
    if path.suffix.lower() != ".geojson":
        raise NotImplementedError(
            f"observed perimeter format {path.suffix!r} not yet supported"
        )

    data = json.loads(path.read_text())
    to_5179 = Transformer.from_crs("EPSG:4326", KOREA_2000_UNIFIED, always_xy=True)

    from shapely.geometry import Polygon as _Polygon
    from shapely.ops import transform as _shp_transform

    series: list[PerimeterAtTime] = []
    for feat in data.get("features", []):
        props = feat.get("properties", {})
        if feat.get("geometry") is None:
            continue
        t_min = float(props.get("time_min_since_ignition", 0.0))
        area_m2 = float(props.get("area_m2", 0.0))
        geom_wgs = shape(feat["geometry"])
        geom_5179 = _shp_transform(lambda x, y, z=None: to_5179.transform(x, y), geom_wgs)
        series.append(PerimeterAtTime(time_min=t_min, polygon=geom_5179, area_m2=area_m2))
    series.sort(key=lambda p: p.time_min)
    return series


def _nearest_in_series(series: list[PerimeterAtTime], t_min: float) -> PerimeterAtTime | None:
    if not series:
        return None
    return min(series, key=lambda p: abs(p.time_min - t_min))


@dataclass
class HorizonMetrics:
    """Per-horizon agreement between one predicted series and observed.

    Session 5: adds front-position error (Hausdorff + mean boundary
    distance) and the fraction of observed area captured, so the report is
    about FRONT ACCURACY per horizon, not just the 24 h area total.
    """

    horizon_min: float
    predicted_area_ha: float
    observed_area_ha: float
    iou: float | None
    sorensen_dice: float | None
    symmetric_difference_km2: float | None
    fraction_observed_captured: float | None = None
    area_error_frac: float | None = None          # (pred - obs) / obs
    front_hausdorff_m: float | None = None
    front_mean_boundary_m: float | None = None

    def as_dict(self) -> dict:
        return {
            "horizon_min": self.horizon_min,
            "predicted_area_ha": self.predicted_area_ha,
            "observed_area_ha": self.observed_area_ha,
            "iou": self.iou,
            "sorensen_dice": self.sorensen_dice,
            "symmetric_difference_km2": self.symmetric_difference_km2,
            "fraction_observed_captured": self.fraction_observed_captured,
            "area_error_frac": self.area_error_frac,
            "front_hausdorff_m": self.front_hausdorff_m,
            "front_mean_boundary_m": self.front_mean_boundary_m,
        }


def compute_horizon_metrics(
    predicted: list[PerimeterAtTime],
    observed: list[PerimeterAtTime],
    horizons_min: Sequence[float],
) -> list[HorizonMetrics]:
    """Per-horizon agreement incl. front-position error (Session 5)."""
    out: list[HorizonMetrics] = []
    for h in horizons_min:
        p = _nearest_in_series(predicted, h)
        o = _nearest_in_series(observed, h)
        if p is None or o is None:
            out.append(HorizonMetrics(
                horizon_min=h,
                predicted_area_ha=(p.area_m2 / 1e4) if p else 0.0,
                observed_area_ha=(o.area_m2 / 1e4) if o else 0.0,
                iou=None, sorensen_dice=None, symmetric_difference_km2=None,
            ))
            continue
        iou = perimeter_iou(p.polygon, o.polygon)
        dice = perimeter_sorensen_dice(p.polygon, o.polygon)
        symd = perimeter_symmetric_difference_area_km2(p.polygon, o.polygon)
        captured = fraction_of_observed_captured(p.polygon, o.polygon)
        front = front_position_error_m(p.polygon, o.polygon)
        area_err = (
            (p.area_m2 - o.area_m2) / o.area_m2 if o.area_m2 > 0 else None
        )
        out.append(HorizonMetrics(
            horizon_min=h,
            predicted_area_ha=p.area_m2 / 1e4,
            observed_area_ha=o.area_m2 / 1e4,
            iou=iou, sorensen_dice=dice, symmetric_difference_km2=symd,
            fraction_observed_captured=captured,
            area_error_frac=area_err,
            front_hausdorff_m=front["hausdorff_m"],
            front_mean_boundary_m=front["mean_boundary_m"],
        ))
    return out


@dataclass
class ValidationRunWithBaselines:
    """Full validation outputs: our model + persistence + isotropic."""

    case: ValidationCase
    config: "ModelConfig"
    horizons_min: tuple[float, ...]
    predicted_model: list[PerimeterAtTime]
    predicted_persistence: list[PerimeterAtTime]
    predicted_isotropic: list[PerimeterAtTime]
    observed: list[PerimeterAtTime]
    metrics_model: list[HorizonMetrics]
    metrics_persistence: list[HorizonMetrics]
    metrics_isotropic: list[HorizonMetrics]
    mean_head_rate_m_min: float
    data_provenance: dict
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "region": self.case.region.name,
            "config": self.config.__dict__,
            "horizons_min": list(self.horizons_min),
            "data_provenance": self.data_provenance,
            "mean_head_rate_m_min": self.mean_head_rate_m_min,
            "metrics": {
                "our_model": [m.as_dict() for m in self.metrics_model],
                "persistence_baseline": [m.as_dict() for m in self.metrics_persistence],
                "isotropic_baseline": [m.as_dict() for m in self.metrics_isotropic],
            },
            "predicted_model_areas_ha": [p.area_m2 / 1e4 for p in self.predicted_model],
            "predicted_model_times_min": [p.time_min for p in self.predicted_model],
            "observed_areas_ha": [o.area_m2 / 1e4 for o in self.observed],
            "observed_times_min": [o.time_min for o in self.observed],
            "notes": self.notes,
        }


def run_validation_with_baselines(
    case: ValidationCase,
    config: ModelConfig | None = None,
    horizons_min: Sequence[float] = (60.0, 180.0, 360.0, 1440.0),
) -> ValidationRunWithBaselines:
    """Run our model + persistence + isotropic baselines, compare to observed.

    The cellular automaton uses the case's observed ignition point (lon,
    lat) ignited at t=0, with DEM + fuel + uniform wind per
    :class:`ModelConfig`. Both baselines start from the same ignition.

    The mean head-fire rate (used to size the isotropic baseline) is
    computed by running Rothermel once at the case's nominal conditions
    (cfg.dead_moisture_1h, cfg.live_moisture_lfmc, cfg.wind_speed_midflame_ms,
    a representative slope of 0°) on KOREAN_PINUS — this is intentionally
    NOT the realised mean head rate over the grid; it's a deliberately
    weak baseline that ignores all spatial heterogeneity.

    Returns a :class:`ValidationRunWithBaselines` ready for JSON dump.
    """
    cfg = config or ModelConfig()
    notes: list[str] = []
    provenance: dict = {}

    # ----- raster ingestion -----
    dem = load_dem(case.region, source=cfg.dem_source, cell_size_m=cfg.cell_size_m)
    fuel = load_fuel_type(case.region, source=cfg.fuel_source, cell_size_m=cfg.cell_size_m)
    provenance["dem_source"] = dem.attrs.get("source", "unknown")
    provenance["dem_synthetic"] = bool(dem.attrs.get("synthetic"))
    provenance["dem_provenance"] = dem.attrs.get("provenance", "")
    provenance["fuel_source"] = fuel.attrs.get("source", "unknown")
    provenance["fuel_synthetic"] = bool(fuel.attrs.get("synthetic"))
    provenance["fuel_provenance"] = fuel.attrs.get("provenance", "")
    if dem.attrs.get("synthetic"):
        notes.append("DEM is SYNTHETIC; not real elevation data.")
    if fuel.attrs.get("synthetic"):
        notes.append("fuel-type is SYNTHETIC (100% KP_PINE fill).")

    # ----- model grid + ignition -----
    grid = FireGrid.from_region(
        case.region, cell_size_m=cfg.cell_size_m,
        residence_time_min=cfg.residence_time_min,
    )
    populate_firegrid(grid, dem, fuel_type=fuel, fuel_code_to_model={1: KOREAN_PINUS})
    grid.fuel_moisture[:] = cfg.live_moisture_lfmc

    # Session 6: enable fire-type physics on the grid per the ablation flags.
    grid.enable_crown_fire = cfg.use_crown_fire
    grid.crown_foliar_moisture_pct = cfg.crown_foliar_moisture_pct
    grid.enable_spotting = cfg.use_spotting
    grid.spotting_seed = cfg.spotting_seed
    if cfg.use_crown_fire:
        provenance["crown_fire"] = "ON (Van Wagner 1977 + Cruz/Alexander 2005)"
    if cfg.use_spotting:
        provenance["spotting"] = "ON (Albini 1979 max spot distance)"

    if case.observed_ignition_point_wgs84 is None:
        raise ValueError(
            "run_validation_with_baselines requires observed_ignition_point_wgs84"
        )
    lon, lat = case.observed_ignition_point_wgs84
    _ignite_at_wgs84(grid, lon, lat, radius_m=cfg.ignition_radius_m)

    # Get ignition cell in EPSG:5179 for the baselines.
    to_5179 = Transformer.from_crs("EPSG:4326", KOREA_2000_UNIFIED, always_xy=True)
    ign_x, ign_y = to_5179.transform(lon, lat)

    # ----- wind (uniform or topographic) -----
    if cfg.use_topographic_wind:
        from ..spread_model.topo_wind import topographic_wind_field
        u10 = cfg.wind_10m_ms if cfg.wind_10m_ms is not None \
            else cfg.wind_speed_midflame_ms / max(cfg.waf, 1e-6)
        u10_field, theta_field = topographic_wind_field(
            u10, (cfg.wind_from_deg + 180.0) % 360.0,  # blowing-toward
            grid.elevation_m, grid.cell_size_m,
        )
        wind = GriddedWindField.from_topographic(u10_field, theta_field, cfg.waf)
        provenance["topographic_wind"] = "ON (heuristic; Föhn slope/channel/lee)"
    else:
        wind = WindField.from_meteo(cfg.wind_speed_midflame_ms, cfg.wind_from_deg)
    predicted_model: list[PerimeterAtTime] = []
    t = 0.0
    next_snap = 0.0
    while t < cfg.duration_min - 1e-9:
        if t >= next_snap - 1e-9:
            poly = grid.perimeter()
            predicted_model.append(PerimeterAtTime(
                time_min=t, polygon=poly, area_m2=grid.burned_area_m2(),
            ))
            next_snap += cfg.snapshot_every_min
        grid.step(cfg.dt_min, wind, current_time_min=t)
        t += cfg.dt_min
    predicted_model.append(PerimeterAtTime(
        time_min=t, polygon=grid.perimeter(), area_m2=grid.burned_area_m2(),
    ))

    # ----- Session 6: regime fractions among burned cells (diagnostic) -----
    if cfg.use_crown_fire:
        burned = grid.state >= CellState.BURNING
        nb = int(burned.sum())
        if nb > 0:
            reg = grid.regime[burned]
            provenance["crown_active_frac"] = float((reg == 2).sum()) / nb
            provenance["crown_passive_frac"] = float((reg == 1).sum()) / nb
            provenance["surface_frac"] = float((reg == 0).sum()) / nb

    # ----- baselines -----
    # Mean head rate via a single Rothermel evaluation under case conditions.
    # This is the deliberately-weak isotropic baseline.
    r = compute_spread_rate(
        KOREAN_PINUS,
        dead_moisture=cfg.dead_moisture_1h,
        live_moisture=cfg.live_moisture_lfmc,
        wind_speed_ms=cfg.wind_speed_midflame_ms,
        slope_degrees=0.0,
    )
    mean_head_rate = r.rate_m_min

    bcfg = BaselineConfig(
        ignition_xy_5179=(ign_x, ign_y),
        duration_min=cfg.duration_min,
        snapshot_every_min=cfg.snapshot_every_min,
        cell_size_m=cfg.cell_size_m,
        initial_radius_m=cfg.ignition_radius_m,
    )
    predicted_persistence = run_persistence_baseline(bcfg)
    predicted_isotropic = run_isotropic_baseline(bcfg, head_fire_rate_m_min=mean_head_rate)

    # ----- observed time series -----
    observed = load_observed_perimeter_series(case)
    if not observed:
        notes.append(
            "no observed perimeter time series found; metrics will be NaN/None"
        )
        provenance["observed_perimeter_source"] = "none"
    else:
        provenance["observed_perimeter_source"] = str(case.observed_perimeters_path)
        provenance["observed_perimeter_provenance"] = (
            "APPROXIMATE, reconstructed from public reporting "
            "(see file metadata.provenance)"
        )

    # ----- horizon metrics for all three -----
    horizons_t = tuple(float(h) for h in horizons_min)
    metrics_model = compute_horizon_metrics(predicted_model, observed, horizons_t)
    metrics_persistence = compute_horizon_metrics(predicted_persistence, observed, horizons_t)
    metrics_isotropic = compute_horizon_metrics(predicted_isotropic, observed, horizons_t)

    return ValidationRunWithBaselines(
        case=case, config=cfg, horizons_min=horizons_t,
        predicted_model=predicted_model,
        predicted_persistence=predicted_persistence,
        predicted_isotropic=predicted_isotropic,
        observed=observed,
        metrics_model=metrics_model,
        metrics_persistence=metrics_persistence,
        metrics_isotropic=metrics_isotropic,
        mean_head_rate_m_min=mean_head_rate,
        data_provenance=provenance,
        notes=notes,
    )


__all__ = [
    "ValidationCase",
    "ModelConfig",
    "ValidationResults",
    "load_case",
    "run_validation",
    # Session 3
    "HorizonMetrics",
    "ValidationRunWithBaselines",
    "load_observed_perimeter_series",
    "compute_horizon_metrics",
    "run_validation_with_baselines",
]
