"""SYNTHETIC fires, windows, splits and data roots for tests. Nothing in this module is real data."""
from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta

import numpy as np
import rasterio
from rasterio.transform import Affine

from firecast_lab import data as fd

CELL = 375.0
START = "2030-01-01T00:00:00+00:00"


def event(fire_id: str, shape, *, duration_h: int = 72) -> dict:
    """A SYNTHETIC events.json record (t0 = start, EPSG:5179, 375 m), flagged ``synthetic``."""
    h, w = shape
    end = datetime.fromisoformat(START) + timedelta(hours=duration_h)
    return dict(id=fire_id, name="SYNTHETIC", country="KR", year=2030, synthetic=True, t0_utc=START,
                start_utc=START, end_utc=end.isoformat(), arrival_path=f"regions/{fire_id}/arrival_time_hours.tif",
                width=w, height=h, epsg=5179, transform=[CELL, 0.0, 1_000_000.0, 0.0, -CELL, 2_000_000.0])


def fire(shape=(24, 28), *, seed: int = 0, hours_per_cell: float = 4.0, wind_toward_deg: float = 0.0,
         eccentricity: float = 0.6, end_h: float = 60.0, wind_speed: float = 6.0):
    """SYNTHETIC elliptical fire, faster downwind, lognormal noise. Returns arrival (hours since t0, NaN outside the
    scar), slope (degrees), u, v (m/s toward east, north); float32-exact so rasters round-trip unchanged."""
    rng = np.random.default_rng(seed)
    h, w = shape
    r0, c0 = h // 2 + int(rng.integers(-2, 3)), w // 3 + int(rng.integers(-2, 3))
    rows, cols = np.indices(shape)
    north, east = -(rows - r0).astype(float), (cols - c0).astype(float)
    theta = np.deg2rad(wind_toward_deg)
    rate = (1.0 + eccentricity * np.cos(np.arctan2(north, east) - theta)) / hours_per_cell     # cells per hour
    arrival = 2.0 + np.hypot(north, east) / rate * np.exp(0.3 * rng.standard_normal(shape))
    arrival = np.where(arrival <= end_h, arrival, np.nan)
    slope = 10.0 + 5.0 * rng.random(shape)
    speed = wind_speed * (1.0 + 0.1 * rng.standard_normal(shape))
    u, v = speed * np.cos(theta), speed * np.sin(theta)
    return tuple(a.astype(np.float32).astype(np.float64) for a in (arrival, slope, u, v))


def record(fire_id: str, split: str = "dev", fold: str | None = "A") -> dict:
    return dict(id=fire_id, split=split, fold=fold if split == "dev" else None, country="KR", c651_role="none")


def splits(**fold_of) -> dict:
    """A SYNTHETIC splits document: ``fire_id=fold`` for dev fires, ``fire_id="test"`` for test fires."""
    return dict(fires=[record(i, "test" if f == "test" else "dev", f) for i, f in fold_of.items()])


def windows(fire_id: str, arrival, slope=None, u=None, v=None, *, lead_h: int = 24, duration_h: int = 72,
            fold: str = "A", domain: str = "headline") -> list:
    wind_at = (lambda _t: (u, v)) if u is not None else None
    return list(fd.windows_from_arrays(event(fire_id, arrival.shape, duration_h=duration_h), arrival, lead_h,
                                       record=record(fire_id, fold=fold), slope=slope, wind_at=wind_at,
                                       domain=domain))


def window(burned, outcome_h, *, lead_h: int = 24, initial_h=None, u=None, v=None, slope=None,
           fire_id: str = "SYNTHETIC_W", cutoff_utc: str = "2030-01-01T12:00:00Z", domain=None) -> fd.Window:
    """One SYNTHETIC window built directly from a cutoff state and outcome hours after the cutoff."""
    burned = np.asarray(burned, dtype=bool)
    initial = np.where(burned, -1.0, np.nan) if initial_h is None else initial_h
    inputs = fd.Cutoff(burned=burned, initial_h=initial, cell_m=CELL, wind_u=u, wind_v=v, slope=slope)
    return fd.Window(fire=fire_id, record=record(fire_id), cutoff_utc=cutoff_utc, cutoff_h=12.0, lead_h=lead_h,
                     transform=(CELL, 0.0, 1_000_000.0, 0.0, -CELL, 2_000_000.0), epsg=5179, synthetic=True,
                     inputs=inputs, outcome_h=np.asarray(outcome_h, dtype=np.float64),
                     domain=np.ones(burned.shape, bool) if domain is None else domain)


def road_graph(shape, *, travel_s: float = 34.0, step: int = 1, forbidden=()):
    """A SYNTHETIC evacplan road graph on the synthetic event grid: a 4-neighbour lattice through the centres of every
    ``step``-th cell, edges of ``travel_s`` (375 m at 40 km/h, rounded up like the router graphs); nodes with
    ``(r + c) % 4 == 0`` are waitable. Node ``n{r}_{c}``, edge ``n{r}_{c}>n{r2}_{c2}``."""
    from evacplan import Edge, Node, RoadGraph

    h, w = shape
    keep = [(r, c) for r in range(0, h, step) for c in range(0, w, step)]
    nodes = [Node(id=f"n{r}_{c}", x=1_000_000.0 + (c + 0.5) * CELL, y=2_000_000.0 - (r + 0.5) * CELL,
                  waitable=(r + c) % 4 == 0) for r, c in keep]
    cells = set(keep)
    edges = [Edge(id=f"n{r}_{c}>n{r + dr}_{c + dc}", u=f"n{r}_{c}", v=f"n{r + dr}_{c + dc}", travel_time_s=travel_s)
             for r, c in keep for dr, dc in ((step, 0), (-step, 0), (0, step), (0, -step)) if (r + dr, c + dc) in cells]
    return RoadGraph(crs_epsg=5179, nodes=nodes, edges=edges, forbidden_turns=list(forbidden),
                     provenance={"generator": "SYNTHETIC lattice (firecast-lab tests)"})


def _tif(path, bands, ev: dict, nodata: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    bands = np.asarray(bands, dtype=np.float64)
    with rasterio.open(path, "w", driver="GTiff", height=ev["height"], width=ev["width"], count=bands.shape[0],
                       dtype="float32", crs=f"EPSG:{ev['epsg']}", transform=Affine(*ev["transform"]),
                       nodata=nodata) as dst:
        dst.write(np.where(np.isfinite(bands), bands, nodata).astype("float32"))


def write_root(path, fires: dict, *, duration_h: int = 72):
    """A SYNTHETIC data root: events.json and, per fire, arrival, slope, hourly wind bands and their band table.
    ``fires``: ``{fire_id: (arrival, slope, u, v)}``. Wind band i holds ``(u, v) * (1 + i / 1000)``."""
    events = []
    for fire_id, (arrival, slope, u, v) in fires.items():
        ev = event(fire_id, arrival.shape, duration_h=duration_h)
        events.append(ev)
        region = path / "regions" / fire_id
        _tif(region / "arrival_time_hours.tif", arrival[None], ev, nodata=-1.0)
        _tif(region / fd.SLOPE, slope[None], ev, nodata=-9999.0)
        scale = 1.0 + np.arange(duration_h + 1)[:, None, None] / 1000.0
        _tif(region / fd.WIND[0], u[None] * scale, ev, nodata=-9999.0)
        _tif(region / fd.WIND[1], v[None] * scale, ev, nodata=-9999.0)
        start = datetime.fromisoformat(START)
        with (region / fd.WEATHER_BANDS).open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["band", "time_utc"])
            for i in range(duration_h + 1):
                writer.writerow([i + 1, (start + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ")])
    (path / "events.json").write_text(json.dumps(events))
    return path
