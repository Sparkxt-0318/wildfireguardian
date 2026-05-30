"""Deliverable 1 -- build the observed spread sequence per fire.

For each fire we:

1. Project FIRMS detections to EPSG:5179 (metres) and lay down a 375 m grid
   (one VIIRS pixel = one cell), snapped to a global 375 m lattice so cell
   indices are deterministic.
2. Cluster detections into overpass epochs (see config).
3. Build, per epoch, the cumulative burned-cell mask (every cell containing a
   detection at or before that epoch). The cells that switch from unburned to
   burned between epoch t and t+1 are the positive prediction targets.
4. Resample the DEM (-> elevation, slope, uphill vector) and the WorldCover
   fuel raster (-> fuel class, burnable mask/fraction, coverage mask) onto the
   same grid, so every feature lives in one aligned array stack.

Cumulative burned area is monotone by construction; we report observed-vs-
reported hectares (VIIRS 375 m pixels over-estimate area -- reported, not
"fixed").
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from affine import Affine
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.warp import reproject
from scipy import ndimage

from .audit import cluster_overpasses, load_detections
from .config import GEOGRAPHIC_CRS, PROJECTED_CRS, PipelineConfig

CELL_HA = None  # set per-instance from cell size


@dataclass
class FireGridSequence:
    """Aligned per-fire raster stack + overpass burn history."""

    fire_id: str
    transform: Affine
    shape: tuple[int, int]  # (H, W)
    cell_size_m: float
    cluster_ends: list[pd.Timestamp]

    # Per-cell observation history
    burn_overpass: np.ndarray  # (H,W) int: epoch of first burn, -1 if never
    cell_frp: np.ndarray  # (H,W) float: FRP at first-burn (0 where never)

    # Terrain
    elevation: np.ndarray  # (H,W) float metres (nan = no DEM / ocean void)
    slope_deg: np.ndarray  # (H,W) float
    uphill_e: np.ndarray  # (H,W) east component of unit uphill vector
    uphill_n: np.ndarray  # (H,W) north component of unit uphill vector
    aspect_deg: np.ndarray  # (H,W) downslope azimuth (0=N, 90=E)

    # Fuel (NaN where outside WorldCover coverage)
    fuel_class: np.ndarray  # (H,W) float (WorldCover code; nan = no coverage)
    is_burnable: np.ndarray  # (H,W) float 0/1 (nan = no coverage)
    burnable_frac_cell: np.ndarray  # (H,W) float [0,1] (nan = no coverage)
    fuel_covered: np.ndarray  # (H,W) bool: WorldCover present for this cell

    @property
    def n_overpasses(self) -> int:
        return len(self.cluster_ends)

    @property
    def cell_area_ha(self) -> float:
        return (self.cell_size_m**2) / 10_000.0

    def burned_mask(self, t: int) -> np.ndarray:
        """Cumulative burned cells at or before overpass index ``t``."""
        return (self.burn_overpass >= 0) & (self.burn_overpass <= t)

    def frp_at(self, t: int) -> np.ndarray:
        """Per-cell FRP for cells burned by ``t`` (0 elsewhere)."""
        m = self.burned_mask(t)
        out = np.zeros(self.shape, dtype=float)
        out[m] = self.cell_frp[m]
        return out

    def land_mask(self) -> np.ndarray:
        return np.isfinite(self.elevation)

    # --- caching (the reprojection is the pipeline's bottleneck) ---
    _ARRAYS = (
        "burn_overpass", "cell_frp", "elevation", "slope_deg", "uphill_e",
        "uphill_n", "aspect_deg", "fuel_class", "is_burnable",
        "burnable_frac_cell", "fuel_covered",
    )

    def save_npz(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            path,
            fire_id=self.fire_id,
            transform=np.array(self.transform.to_gdal(), dtype=float),
            shape=np.array(self.shape, dtype=int),
            cell_size_m=self.cell_size_m,
            cluster_ends=np.array([str(t) for t in self.cluster_ends]),
            **{k: getattr(self, k) for k in self._ARRAYS},
        )

    @classmethod
    def load_npz(cls, path: Path) -> "FireGridSequence":
        z = np.load(path, allow_pickle=False)
        g = z["transform"]
        transform = Affine.from_gdal(*g.tolist())
        return cls(
            fire_id=str(z["fire_id"]),
            transform=transform,
            shape=tuple(int(s) for s in z["shape"]),
            cell_size_m=float(z["cell_size_m"]),
            cluster_ends=[pd.Timestamp(str(s)) for s in z["cluster_ends"]],
            **{k: z[k] for k in cls._ARRAYS},
        )


def _snap_grid(xmin, ymin, xmax, ymax, cell, buffer):
    """Return (transform, H, W) for a north-up grid snapped to the cell lattice."""
    xmin -= buffer
    ymin -= buffer
    xmax += buffer
    ymax += buffer
    x0 = np.floor(xmin / cell) * cell
    y1 = np.ceil(ymax / cell) * cell
    W = int(np.ceil((xmax - x0) / cell))
    H = int(np.ceil((y1 - ymin) / cell))
    transform = Affine(cell, 0.0, x0, 0.0, -cell, y1)
    return transform, H, W


def _reproject_to_grid(src_path, transform, shape, resampling, src_band=1):
    """Reproject one band of a raster onto the target grid; return (data, nodata)."""
    with rasterio.open(src_path) as ds:
        src = ds.read(src_band)
        src_nodata = ds.nodata
        dst = np.zeros(shape, dtype="float32")
        reproject(
            source=src.astype("float32"),
            destination=dst,
            src_transform=ds.transform,
            src_crs=ds.crs,
            dst_transform=transform,
            dst_crs=PROJECTED_CRS,
            resampling=resampling,
            src_nodata=src_nodata,
            dst_nodata=np.nan,
        )
    return dst, src_nodata


def _terrain(elevation: np.ndarray, cell: float):
    """Slope (deg), uphill unit vector (E,N), downslope aspect (deg) from a DEM."""
    elev = elevation.copy()
    # Fill NaN locally so gradients near voids are finite-ish; mask restored after.
    finite = np.isfinite(elev)
    if not finite.all():
        elev = np.where(finite, elev, np.nanmean(elev[finite]) if finite.any() else 0.0)
    gcol = np.gradient(elev, axis=1) / cell  # d(elev)/d(east)
    grow = np.gradient(elev, axis=0) / cell  # d(elev)/d(row) = -d(elev)/d(north)
    ge = gcol
    gn = -grow
    mag = np.hypot(ge, gn)
    slope_deg = np.degrees(np.arctan(mag))
    with np.errstate(invalid="ignore", divide="ignore"):
        ue = np.where(mag > 0, ge / mag, 0.0)
        un = np.where(mag > 0, gn / mag, 0.0)
    # Downslope azimuth (direction water flows): opposite of uphill.
    aspect = (np.degrees(np.arctan2(-ue, -un)) + 360.0) % 360.0
    slope_deg = np.where(finite, slope_deg, np.nan)
    aspect = np.where(finite, aspect, np.nan)
    return slope_deg, ue, un, aspect


def build_fire_sequence(
    fire_id: str, config: PipelineConfig | None = None
) -> FireGridSequence:
    config = config or PipelineConfig()
    cell = config.cell_size_m
    data = config.data_dir

    df = load_detections(data / f"{fire_id}_detections.csv")
    tf = Transformer.from_crs(GEOGRAPHIC_CRS, PROJECTED_CRS, always_xy=True)
    x, y = tf.transform(df["longitude"].values, df["latitude"].values)
    x = np.asarray(x)
    y = np.asarray(y)

    transform, H, W = _snap_grid(
        x.min(), y.min(), x.max(), y.max(), cell, config.extra_buffer_m
    )
    inv = ~transform
    cols, rows = inv * (x, y)
    cols = np.floor(cols).astype(int)
    rows = np.floor(rows).astype(int)
    valid = (rows >= 0) & (rows < H) & (cols >= 0) & (cols < W)

    cluster_ends = cluster_overpasses(df["timestamp"], config.overpass_gap_minutes)
    ends = np.array(
        [np.datetime64(pd.Timestamp(e).tz_localize(None)) for e in cluster_ends]
    )
    ts = df["timestamp"].dt.tz_convert("UTC").dt.tz_localize(None).values.astype(
        "datetime64[ns]"
    )
    op_idx = np.clip(np.searchsorted(ends, ts, side="left"), 0, len(ends) - 1)

    frp = df["frp"].fillna(0.0).values.astype(float)

    burn_overpass = np.full((H, W), -1, dtype=int)
    cell_frp = np.zeros((H, W), dtype=float)
    # Earliest overpass per cell, and FRP at that first burn (max over coincident).
    order = np.argsort(op_idx, kind="stable")
    for k in order:
        if not valid[k]:
            continue
        r, c = rows[k], cols[k]
        o = op_idx[k]
        if burn_overpass[r, c] == -1 or o < burn_overpass[r, c]:
            burn_overpass[r, c] = o
            cell_frp[r, c] = frp[k]
        elif o == burn_overpass[r, c]:
            cell_frp[r, c] = max(cell_frp[r, c], frp[k])

    # Terrain from DEM.
    elevation, _ = _reproject_to_grid(
        data / f"{fire_id}_dem.tif", transform, (H, W), Resampling.bilinear
    )
    slope_deg, ue, un, aspect = _terrain(elevation, cell)

    # Fuel: mode class, burnable fraction, coverage mask.
    fuel_class, _ = _reproject_to_grid(
        data / f"{fire_id}_fuel.tif", transform, (H, W), Resampling.mode
    )
    layers = _load_burnable_map(data)
    fuel_path = data / f"{fire_id}_fuel.tif"
    burnable_frac_cell, fuel_covered = _reproject_burnable(
        fuel_path, transform, (H, W), layers
    )
    fuel_class = np.where(fuel_covered, fuel_class, np.nan)
    # Class 0 inside coverage shouldn't happen, but guard:
    fuel_class = np.where((fuel_class == 0) & ~fuel_covered, np.nan, fuel_class)
    is_burnable = np.full((H, W), np.nan, dtype=float)
    covered_idx = fuel_covered & np.isfinite(fuel_class)
    classes = np.round(fuel_class[covered_idx]).astype(int)
    is_burnable[covered_idx] = np.array(
        [layers.get(int(c), 0) for c in classes], dtype=float
    )

    return FireGridSequence(
        fire_id=fire_id,
        transform=transform,
        shape=(H, W),
        cell_size_m=cell,
        cluster_ends=list(cluster_ends),
        burn_overpass=burn_overpass,
        cell_frp=cell_frp,
        elevation=elevation,
        slope_deg=slope_deg,
        uphill_e=ue,
        uphill_n=un,
        aspect_deg=aspect,
        fuel_class=fuel_class,
        is_burnable=is_burnable,
        burnable_frac_cell=burnable_frac_cell,
        fuel_covered=fuel_covered,
    )


def get_fire_sequence(
    fire_id: str, config: PipelineConfig | None = None, cache: bool = True
) -> FireGridSequence:
    """Build a fire sequence, using an on-disk npz cache when available."""
    config = config or PipelineConfig()
    cache_path = config.output_dir / "seq_cache" / f"{fire_id}.npz"
    if cache and cache_path.exists():
        return FireGridSequence.load_npz(cache_path)
    seq = build_fire_sequence(fire_id, config)
    if cache:
        seq.save_npz(cache_path)
    return seq


def _load_burnable_map(data_dir: Path) -> dict[int, int]:
    import json

    layers = json.loads((data_dir / "data_layers_manifest.json").read_text())
    return {int(k): int(v) for k, v in layers["worldcover_burnable_map"].items()}


def _reproject_burnable(fuel_path, transform, shape, burnable_map):
    """Return (burnable_frac in [0,1], coverage bool) on the target grid."""
    with rasterio.open(fuel_path) as ds:
        src = ds.read(1)
        src_nodata = ds.nodata if ds.nodata is not None else 0
        burnable_src = np.zeros(src.shape, dtype="float32")
        for code, flag in burnable_map.items():
            if flag:
                burnable_src[src == code] = 1.0
        valid_src = (src != src_nodata).astype("float32")

        burnable_frac = np.full(shape, np.nan, dtype="float32")
        coverage = np.zeros(shape, dtype="float32")
        reproject(
            source=valid_src,
            destination=coverage,
            src_transform=ds.transform,
            src_crs=ds.crs,
            dst_transform=transform,
            dst_crs=PROJECTED_CRS,
            resampling=Resampling.average,
            src_nodata=None,
            dst_nodata=0.0,
        )
        # burnable fraction *among covered* source pixels.
        burnable_sum = np.zeros(shape, dtype="float32")
        reproject(
            source=burnable_src,
            destination=burnable_sum,
            src_transform=ds.transform,
            src_crs=ds.crs,
            dst_transform=transform,
            dst_crs=PROJECTED_CRS,
            resampling=Resampling.average,
            src_nodata=None,
            dst_nodata=0.0,
        )
    covered = coverage > 0.05  # need >5% of the cell actually covered
    with np.errstate(invalid="ignore", divide="ignore"):
        frac = np.where(covered, np.clip(burnable_sum / np.maximum(coverage, 1e-6), 0, 1), np.nan)
    return frac.astype(float), covered


def observed_vs_reported(seq: FireGridSequence, reported_ha: float) -> dict:
    """Final burned area vs reported (VIIRS 375 m over-estimates -- reported)."""
    final = seq.burned_mask(seq.n_overpasses - 1)
    n = int(final.sum())
    obs_ha = n * seq.cell_area_ha
    # monotonicity check
    areas = [int(seq.burned_mask(t).sum()) for t in range(seq.n_overpasses)]
    monotone = all(b >= a for a, b in zip(areas, areas[1:]))
    return {
        "fire_id": seq.fire_id,
        "n_burned_cells": n,
        "observed_ha": round(obs_ha, 1),
        "reported_ha": reported_ha,
        "ratio_obs_over_reported": round(obs_ha / reported_ha, 2) if reported_ha else None,
        "cumulative_cells_per_overpass": areas,
        "monotone_nondecreasing": monotone,
    }
