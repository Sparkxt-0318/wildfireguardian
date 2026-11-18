"""Arrival grids and issue hours for Arm 2, built with the kcf-margin / kcf-abstain rules (PROTOCOL 3.1).

Each fire: A (int32 arrival-hour index, NEVER = never), base (UTC time of index 0), issue hours per horizon,
committed reach values to reproduce, and the lon/lat of the centroid of its first known burned set (wind point).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MARGIN = HERE.parent / "kcf-margin"
ABSTAIN = HERE.parent / "kcf-abstain"
sys.path.insert(0, str(MARGIN))
from reach import CELL_KM, NEVER  # noqa: E402

HORIZONS = (5, 8)
CELL_M = CELL_KM * 1000


@dataclass
class Fire:
    name: str
    product: str                  # GOFER | CHOI | DET
    role: str                     # calibration | test
    A: np.ndarray
    base: pd.Timestamp
    epsg: int
    x0: float
    y1: float
    issue: dict                   # h -> sorted int array of issue-hour indices
    committed: dict = field(default_factory=dict)   # h -> {t_idx: committed reach km} (reproduction gate)
    complete: dict = field(default_factory=dict)    # h -> {t_idx: bool} (DET only)
    label: str = ""

    def time(self, t):
        return self.base + pd.Timedelta(hours=int(t))

    def wind_point(self):
        """lon, lat of the centroid of the first known burned set."""
        from pyproj import Transformer
        first = int(self.A[self.A != NEVER].min())
        r, c = np.nonzero(self.A == first)
        x = self.x0 + (c.mean() + 0.5) * CELL_M
        y = self.y1 - (r.mean() + 0.5) * CELL_M
        lon, lat = Transformer.from_crs(self.epsg, 4326, always_xy=True).transform(x, y)
        return float(lon), float(lat)


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def gofer(work: Path) -> list[Fire]:
    """28 calibration fires. `work` holds gofer_arrival/*.npz written by kcf-margin/score_gofer.py."""
    reach = pd.read_csv(MARGIN / "derived/gofer_reach.csv.gz")
    out = []
    for name, r in reach.groupby("fire", sort=True):
        z = np.load(work / "gofer_arrival" / f"{name}.npz", allow_pickle=False)
        tf = z["transform"]
        issue, committed = {}, {}
        for h in HORIZONS:
            rh = r[r.h == h].sort_values("t_idx")
            issue[h] = rh.t_idx.to_numpy(int)
            committed[h] = dict(zip(rh.t_idx.astype(int), rh.reach_km))
        f = Fire(name, "GOFER", "calibration", z["A"], pd.Timestamp(str(z["t0"])), 3310, float(tf[2]), float(tf[5]),
                 issue, committed)
        row = r.iloc[0]
        if f.time(int(row.t_idx)) != pd.Timestamp(row.t):
            raise ValueError(f"{name}: time base differs from the committed reach table")
        out.append(f)
    return out


def choi_kr(choi_dir: Path) -> tuple[list[Fire], dict]:
    """Korean fires on the Choi et al. 2026 arrival rasters; the arrival-index rule of kcf-abstain/fire_hours.py."""
    import rasterio
    events = {e["id"]: e for e in json.load(open(REPO / "forecast/data/environment/events.json"))}
    base_tab = pd.read_csv(ABSTAIN / "derived/hours_base.csv.gz", low_memory=False)
    base_tab = base_tab[(base_tab["product"] == "CHOI") & (base_tab.country == "KR")]
    out, skipped = [], {}
    for eid in sorted(e for e in events if e.startswith("KFS")):
        with rasterio.open(choi_dir / "rasters_kr" / f"{eid}_pswt_ok_toa.tif") as ds:
            v = ds.read(1, masked=True)
            t0 = pd.Timestamp(ds.tags()["t0_utc"])
            tf, epsg = ds.transform, ds.crs.to_epsg()
        toa = np.ma.filled(v.astype(float), np.nan)
        ok = np.isfinite(toa)
        base = t0.floor("h")
        off = (t0 - base).total_seconds() / 3600
        A = np.full(toa.shape, NEVER, np.int64)
        A[ok] = np.ceil(toa[ok] + off - 1e-9).astype(np.int64)
        shift = int(A[ok].min()) - 1
        A[ok] -= shift
        base = base + pd.Timedelta(hours=shift)
        first, last = int(A[ok].min()), int(A[ok].max())
        issue = {5: np.arange(first, last - 5 + 1), 8: np.arange(first, last - 8 + 1)}
        if len(issue[5]) == 0:
            skipped[eid] = f"no issue hour: arrival spans {last - first} h (NOT TESTED)"
            continue
        pad = 8                                  # room for the wind-aligned shape (the raster is cropped to the fire)
        A = np.pad(A.astype(np.int32), pad, constant_values=NEVER)
        f = Fire(eid, "CHOI", "test", A, base, epsg, float(tf.c) - pad * CELL_M, float(tf.f) + pad * CELL_M, issue,
                 label=events[eid]["name"])
        b = base_tab[base_tab.fire == eid]
        tt = {pd.Timestamp(t): i for i, t in enumerate(b.t_utc)}
        for h, col in ((5, "reach5_km"), (8, "reach8_km")):
            f.committed[h] = {int(t): float(b[col].iloc[tt[f.time(t)]]) for t in issue[h] if f.time(t) in tt}
        out.append(f)
    return out, skipped


def det() -> Fire:
    """25 March 2025 detection product (kcf-margin/score_gyeongbuk.py), issue hours 00-23 KST."""
    sk = _module(MARGIN / "score_gyeongbuk.py", "score_gyeongbuk")
    H = REPO / "research/harness-2026-11"
    A, _, meta = sk.build_arrival(H / "data-fetch/small/firms", H / "data-fetch-2/ahi_kfs01")
    end = int(sk.hour_index(sk.AHI_END))
    t_first = int(sk.hour_index(pd.Timestamp("2025-03-24 15:00")))
    hours = np.arange(t_first, t_first + 24)
    g = pd.read_csv(MARGIN / "derived/gyeongbuk_reach.csv")
    f = Fire("KFS_01_25March", "DET", "test", A, sk.T0, 5179, float(meta["x0"]), float(meta["y1"]),
             {h: hours for h in HORIZONS}, label="Gyeongbuk 25 March 2025 (FIRMS VIIRS + Himawari AHI detections)")
    for h in HORIZONS:
        gh = g[g.h == h].set_index("kst_hour")
        f.committed[h] = {int(t_first + k): float(gh.reach_km[k]) for k in gh.index}
        f.complete[h] = {int(t): bool(t + h <= end) for t in hours}
    return f
