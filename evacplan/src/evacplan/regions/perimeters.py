"""Observed fire perimeters (GeoJSON) -> a ``hazard_contract`` scenario set via ``from_perimeters``.

Input: a GeoJSON FeatureCollection in WGS84 lon/lat (RFC 7946) whose features are Polygons or
MultiPolygons with a timezone-aware ISO-8601 time property (default ``"time"``); features with the
same time are one perimeter. Rings are projected to the hazard CRS with pyproj.

Hazard: ``from_perimeters`` brackets each cell's ignition between the last perimeter that excludes
it and the first that includes it (``stratified``: member k at fraction (k+0.5)/K of the gap;
``envelope``: one conservative member burning over the whole gap). As for the SYNTHETIC
instances, ignited cells stay burning through the horizon (burned roads stay closed) and the flux
uses the repo packets' heat-source parameters; the horizon is the last perimeter (nothing is known
after it).
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

import hazard_contract as hc

PERSIST_S = 48 * 3600.0
PACKET_HEAT = dict(fuel_load_kg_m2=10.0, consumed_fraction=0.1, heat_content_kj_kg=18608.0, radiative_fraction=0.3,
                   burn_duration_s=3970.4642815249267, emission_height_m=5.0, receiver_height_m=0.0)


def _time(v) -> datetime:
    t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    if t.tzinfo is None:
        raise ValueError(f"perimeter time {v!r} has no timezone")
    return t.astimezone(timezone.utc)


def read_perimeter_geojson(source, *, time_property: str = "time", crs_epsg: int = 3310) -> list[tuple[datetime, list]]:
    """``[(time, [polygon, ...]), ...]`` sorted by time; each polygon is ``[exterior, *holes]`` with
    rings ``[n, 2]`` in EPSG:``crs_epsg`` metres."""
    from pyproj import Transformer
    data = source if isinstance(source, dict) else json.loads(Path(source).read_text())
    feats = data.get("features", [data]) if data.get("type") == "FeatureCollection" else [data]
    legacy = (data.get("crs") or {}).get("properties", {}).get("name", "")
    if legacy and not any(s in legacy for s in ("CRS84", "4326")):
        raise ValueError(f"GeoJSON CRS {legacy!r}: expected WGS84 lon/lat (RFC 7946)")
    tr = Transformer.from_crs("EPSG:4326", f"EPSG:{crs_epsg}", always_xy=True)

    def ring(coords) -> np.ndarray:
        a = np.asarray(coords, dtype=float)[:, :2]
        x, y = tr.transform(a[:, 0], a[:, 1])
        return np.column_stack([x, y])

    groups: dict[datetime, list] = {}
    for f in feats:
        props = f.get("properties") or {}
        if time_property not in props:
            raise ValueError(f"a perimeter feature has no {time_property!r} property")
        geom = f.get("geometry") or {}
        if geom.get("type") == "Polygon":
            polys = [geom["coordinates"]]
        elif geom.get("type") == "MultiPolygon":
            polys = geom["coordinates"]
        else:
            raise ValueError(f"perimeter geometry must be Polygon or MultiPolygon, got {geom.get('type')!r}")
        groups.setdefault(_time(props[time_property]), []).extend([[ring(r) for r in p] for p in polys])
    return sorted(groups.items(), key=lambda kv: kv[0])


def grid_for(bounds_xy: tuple[float, float, float, float], cell_m: float, margin_cells: int):
    """North-up grid aligned to multiples of ``cell_m`` covering ``(xmin, ymin, xmax, ymax)`` plus a
    margin. Returns ``(transform, height, width)``."""
    xmin, ymin, xmax, ymax = bounds_xy
    x0 = math.floor(xmin / cell_m) * cell_m - margin_cells * cell_m
    y0 = math.floor(ymin / cell_m) * cell_m - margin_cells * cell_m
    x1 = math.ceil(xmax / cell_m) * cell_m + margin_cells * cell_m
    y1 = math.ceil(ymax / cell_m) * cell_m + margin_cells * cell_m
    width, height = int(round((x1 - x0) / cell_m)), int(round((y1 - y0) / cell_m))
    return (float(cell_m), 0.0, float(x0), 0.0, -float(cell_m), float(y1)), height, width


def hazard_from_perimeters(series, *, transform, height: int, width: int, crs_epsg: int, issue_time_utc, K: int = 4,
                           mode: str = "stratified", burn_duration_s: float = PERSIST_S, heat: hc.HeatSource | None = None,
                           synthetic: bool = False, horizon_s: float | None = None, mapped_mask=None,
                           model_version: str | None = None) -> hc.ScenarioSet:
    heat = heat or hc.HeatSource(**PACKET_HEAT, note="the repo packets' heat-source parameters")
    return hc.from_perimeters(series, burn_duration_s, transform=transform, height=height, width=width,
                              crs_epsg=crs_epsg, issue_time_utc=issue_time_utc, K=K, mode=mode,
                              mapped_mask=mapped_mask, horizon_s=horizon_s, heat=heat, synthetic=synthetic,
                              model_version=model_version or f"perimeter-{mode}-persistent-v1")
