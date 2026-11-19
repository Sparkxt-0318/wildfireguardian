"""Per-cell environment on the 375 m KFS lattice (land cover, canopy height, hourly 10 m wind, RH, temperature).

Source: the forecast workspace's prepared environment, data/environment/regions/<KFS id>/ (Copernicus Global Land
Cover v3.0.1 2019 at 100 m, mode-resampled; UMD GLAD GEDI-Landsat 2019 canopy height; ECMWF IFS hourly weather at
~9 km, nearest-cell resampled). Recovered for this study from the owner-local archive ``wildfire (2).zip``
(DATA.md); the files are not in git. EPSG:5179, 375 m, the same lattice as the routing grids.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


def _read(path):
    import rasterio
    with rasterio.open(path) as r:
        a = r.read().astype(float)
        nd = r.nodata
        if nd is not None and not np.isnan(nd):
            a[a == nd] = np.nan
        return a, r.transform, list(r.descriptions)


class Environment:
    def __init__(self, region_dir: Path):
        region_dir = Path(region_dir)
        self.dir = region_dir
        self.grid = json.loads((region_dir / "grid.json").read_text())
        tr = self.grid["transform"]
        self.res = float(tr[0])
        self.x0 = float(tr[2])
        self.ytop = float(tr[5])
        self.W, self.H = int(self.grid["width"]), int(self.grid["height"])
        self.t0 = datetime.fromisoformat(self.grid["t0_utc"])
        a, _, _ = _read(region_dir / "arrival_time_hours.tif")
        self.arrival_h = a[0]          # hours since t0_utc, north-up
        self.landcover = _read(region_dir / "vegetation/landcover_class_375m.tif")[0][0]
        self.forest_type = _read(region_dir / "vegetation/forest_type_375m.tif")[0][0]
        self.tree_cover = _read(region_dir / "vegetation/tree_cover_percent_375m.tif")[0][0]
        self.canopy_h = _read(region_dir / "vegetation/canopy_height_2019_m_375m.tif")[0][0]
        self.slope_deg = _read(region_dir / "terrain/slope_degrees_375m.tif")[0][0]
        self._wx = {}

    def weather(self, var: str):
        """(bands, times) for an hourly variable, e.g. wind_speed_10m, wind_direction_10m, relative_humidity_2m,
        temperature_2m."""
        if var not in self._wx:
            a, _, desc = _read(self.dir / ("weather/%s_375m.tif" % var))
            times = [datetime.fromisoformat(d.replace("Z", "+00:00")) for d in desc]
            self._wx[var] = (a, times)
        return self._wx[var]

    def at_hour(self, var: str, when: datetime):
        a, times = self.weather(var)
        ts = np.array([t.timestamp() for t in times])
        k = int(np.argmin(np.abs(ts - when.astimezone(timezone.utc).timestamp())))
        return a[k], times[k]

    def cell_index(self, x, y):
        """(row, col) on this north-up lattice for EPSG:5179 points; -1 where outside."""
        c = np.floor((np.asarray(x) - self.x0) / self.res).astype(int)
        r = np.floor((self.ytop - np.asarray(y)) / self.res).astype(int)
        ok = (c >= 0) & (c < self.W) & (r >= 0) & (r < self.H)
        return np.where(ok, r, -1), np.where(ok, c, -1)
