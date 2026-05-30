"""Deliverable 0 -- data audit (run BEFORE any modelling).

Loads the two manifests, and for every fire reports detection count, time
span, distinct overpasses, bbox, DEM/fuel shape+range, burnable fraction,
and -- the critical check -- what fraction of the fire's detections fall
*inside* the fuel raster's coverage. The yeongdeok fuel raster is clipped at
the WorldCover 129 deg E tile boundary; this audit quantifies that and the
same defect on any other fire, then records a keep/flag/drop decision.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

from .config import (
    DROP_FIRES,
    FUEL_BROKEN_FIRES,
    PipelineConfig,
    SPARSE_FIRES,
)


@dataclass
class RasterInfo:
    shape: tuple[int, int]
    crs: str
    bounds: tuple[float, float, float, float]  # left, bottom, right, top
    res: tuple[float, float]
    nodata: float | None


@dataclass
class FireAudit:
    fire_id: str
    name: str
    bbox: list[float]
    reported_ha: float
    n_detections_manifest: int
    n_detections_csv: int
    overpass_hours_manifest: int
    first_detection: str
    last_detection: str
    time_span_hours: float
    n_overpasses_clustered: int
    detections_per_overpass: list[int]
    timestamps_parseable: bool
    timestamps_ordered_ok: bool
    dem: RasterInfo
    fuel: RasterInfo
    burnable_frac_manifest: float
    frac_detections_in_fuel: float
    fuel_decision: str
    fuel_reason: str
    instruments: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {k: getattr(self, k) for k in self.__dataclass_fields__}
        d["dem"] = self.dem.__dict__
        d["fuel"] = self.fuel.__dict__
        return d


def _raster_info(path: Path) -> RasterInfo:
    with rasterio.open(path) as ds:
        b = ds.bounds
        return RasterInfo(
            shape=(ds.height, ds.width),
            crs=str(ds.crs),
            bounds=(b.left, b.bottom, b.right, b.top),
            res=(abs(ds.res[0]), abs(ds.res[1])),
            nodata=None if ds.nodata is None else float(ds.nodata),
        )


def cluster_overpasses(timestamps: pd.Series, gap_minutes: float) -> list[pd.Timestamp]:
    """Return the end-time of each overpass cluster.

    Detections are grouped by walking the sorted *unique* timestamps and
    starting a new cluster whenever the gap from the previous one exceeds
    ``gap_minutes``.
    """
    ts = timestamps.dropna()
    if getattr(ts.dtype, "tz", None) is not None:
        ts = ts.dt.tz_convert("UTC").dt.tz_localize(None)
    uniq = np.sort(ts.unique())
    if len(uniq) == 0:
        return []
    clusters: list[list[pd.Timestamp]] = [[uniq[0]]]
    gap = np.timedelta64(int(gap_minutes * 60), "s")
    for t in uniq[1:]:
        if t - clusters[-1][-1] > gap:
            clusters.append([t])
        else:
            clusters[-1].append(t)
    return [pd.Timestamp(c[-1]) for c in clusters]


def load_detections(csv_path: Path) -> pd.DataFrame:
    """Load a FIRMS detection CSV with a parsed, tz-aware ``timestamp``."""
    df = pd.read_csv(csv_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    return df


def _assign_overpass(timestamps: pd.Series, cluster_ends: list[pd.Timestamp]) -> np.ndarray:
    """Map each detection timestamp to its overpass index (0-based)."""
    ends = np.array([np.datetime64(pd.Timestamp(e).tz_localize(None)) for e in cluster_ends])
    ts_ser = timestamps
    if getattr(ts_ser.dtype, "tz", None) is not None:
        ts_ser = ts_ser.dt.tz_convert("UTC").dt.tz_localize(None)
    ts = ts_ser.values.astype("datetime64[ns]")
    # smallest cluster-end >= timestamp
    idx = np.searchsorted(ends, ts, side="left")
    idx = np.clip(idx, 0, len(ends) - 1)
    return idx


def audit_fire(fire: dict, data_dir: Path, config: PipelineConfig) -> FireAudit:
    fire_id = fire["id"]
    csv_path = data_dir / fire["csv"]
    df = load_detections(csv_path)

    parseable = bool(df["timestamp"].notna().all())
    ordered_ok = bool(df["timestamp"].is_monotonic_increasing) or bool(
        df["timestamp"].sort_values().equals(df["timestamp"].sort_values())
    )

    cluster_ends = cluster_overpasses(df["timestamp"], config.overpass_gap_minutes)
    op_idx = _assign_overpass(df["timestamp"], cluster_ends)
    det_per_op = [int((op_idx == i).sum()) for i in range(len(cluster_ends))]

    dem = _raster_info(data_dir / f"{fire_id}_dem.tif")
    fuel = _raster_info(data_dir / f"{fire_id}_fuel.tif")

    # Critical check: fraction of detections inside the fuel raster extent.
    fl, fb, fr, ft = fuel.bounds
    inside = (
        (df["longitude"] >= fl)
        & (df["longitude"] <= fr)
        & (df["latitude"] >= fb)
        & (df["latitude"] <= ft)
    )
    frac_in_fuel = float(inside.mean())

    # Decision logic.
    if fire_id in config.drop_fires:
        decision, reason = "DROP", "Too few overpasses to observe spread."
    elif frac_in_fuel < 0.5:
        decision = "FLAG_FUEL_BLIND"
        reason = (
            f"Only {frac_in_fuel:.1%} of detections fall inside the fuel raster "
            "(clipped at the WorldCover 129E tile boundary). Fuel features set "
            "to NaN per-cell; is_burnable hard-gate disabled; predicted fuel-blind; "
            "excluded from the headline mean."
        )
    elif fire_id in config.sparse_fires:
        decision = "KEEP_SPARSE"
        reason = "Temporally sparse; train-pool only, held-out reported separately."
    else:
        decision = "KEEP"
        reason = f"{frac_in_fuel:.1%} of detections inside fuel coverage -- adequate."

    span_h = (df["timestamp"].max() - df["timestamp"].min()).total_seconds() / 3600.0

    return FireAudit(
        fire_id=fire_id,
        name=fire["name"],
        bbox=fire["bbox"],
        reported_ha=float(fire["reported_ha"]),
        n_detections_manifest=int(fire["n_detections"]),
        n_detections_csv=int(len(df)),
        overpass_hours_manifest=int(fire["distinct_overpass_hours"]),
        first_detection=str(df["timestamp"].min()),
        last_detection=str(df["timestamp"].max()),
        time_span_hours=round(span_h, 2),
        n_overpasses_clustered=len(cluster_ends),
        detections_per_overpass=det_per_op,
        timestamps_parseable=parseable,
        timestamps_ordered_ok=ordered_ok,
        dem=dem,
        fuel=fuel,
        burnable_frac_manifest=float("nan"),  # filled from layers manifest in run_audit
        frac_detections_in_fuel=round(frac_in_fuel, 4),
        fuel_decision=decision,
        fuel_reason=reason,
        instruments={k: int(v) for k, v in df["instrument"].value_counts().items()},
    )


def run_audit(config: PipelineConfig | None = None) -> dict:
    """Run the full Deliverable-0 audit; return a JSON-serialisable dict."""
    config = config or PipelineConfig()
    manifest = json.loads((config.data_dir / "fire_manifest.json").read_text())
    layers = json.loads((config.data_dir / "data_layers_manifest.json").read_text())
    burnable_map = {int(k): int(v) for k, v in layers["worldcover_burnable_map"].items()}
    layer_by_id = {l["id"]: l for l in layers["layers"]}

    audits: list[FireAudit] = []
    for fire in manifest["fires"]:
        a = audit_fire(fire, config.data_dir, config)
        # pull manifest burnable_frac from the layers manifest
        a.burnable_frac_manifest = float(layer_by_id[a.fire_id]["burnable_frac"])
        audits.append(a)

    return {
        "provenance": "NASA FIRMS (VIIRS+MODIS) / SRTM DEM / ESA WorldCover 2021",
        "worldcover_burnable_map": burnable_map,
        "fires": [a.to_dict() for a in audits],
    }


def format_audit_table(audit: dict) -> str:
    """Human-readable audit summary (printed by the audit script)."""
    lines: list[str] = []
    h = (
        f"{'fire_id':24s} {'det':>5s} {'ovp':>4s} {'span_h':>7s} "
        f"{'rep_ha':>7s} {'%inFuel':>8s} {'burn_frac':>9s}  decision"
    )
    lines.append(h)
    lines.append("-" * len(h))
    for f in audit["fires"]:
        lines.append(
            f"{f['fire_id']:24s} {f['n_detections_csv']:5d} "
            f"{f['n_overpasses_clustered']:4d} {f['time_span_hours']:7.1f} "
            f"{f['reported_ha']:7.0f} {100*f['frac_detections_in_fuel']:7.1f}% "
            f"{f['burnable_frac_manifest']:9.3f}  {f['fuel_decision']}"
        )
    return "\n".join(lines)
