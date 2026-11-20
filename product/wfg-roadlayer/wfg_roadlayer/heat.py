"""Heat option: radiant-heat road closure by published methods (research/kcf-radiation, METHOD.md; vendored byte for
byte in vendor/kcf_radiation). Off by default; ``--heat`` or settings [heat] enabled = 1 turns it on.

Chain per 375 m cell: spread rate from the arrival field (|grad t| = 1/R) -> fuel from the bundled Copernicus 2019
land-cover class -> Byram intensity -> Van Wagner crown test -> Byram / Thomas flame length -> Albini tilt -> solid
flame flux -> safe distance d* at the threshold. A road piece closes when the front comes within d* of it
(A - (d* - delta)/R), never later than the contact rule. Wind, humidity and air temperature are one value per run
(settings [heat]), not a weather field.

Supported inputs: fire-arrival GeoTIFFs on the 375 m EPSG:5179 lattice of the road grid, and packets. Other rasters are
refused with HEAT_INPUT_UNSUPPORTED (the spread rate needs the whole arrival field on the road grid).
"""
from __future__ import annotations

import csv
import gzip
import math
from dataclasses import replace
from pathlib import Path

import numpy as np

from . import geotiff
from .errors import Refusal, reason
from .vendor.kcf_radiation import closure, fuels, model, ros
from .vendor.kcf_radiation import protocol as P

PRODUCT = Path(__file__).resolve().parents[1]
LEVELS = {0: "low", 1: "middle", 2: "high"}


def _unsupported(why_ko, why_en):
    return Refusal(reason("HEAT_INPUT_UNSUPPORTED", "열 옵션은 이 입력을 쓸 수 없습니다: %s" % why_ko,
                          "the heat option cannot use this input: %s" % why_en))


def arrival_grid(fire, road):
    """Seconds after issue on the road grid (router rows south-up); +inf not reached, NaN no data."""
    if fire.kind == "packet":
        d = Path(fire.path)
        with np.load(d / "constructed_arrays.npz", allow_pickle=False) as z:
            ev = np.array(z["ignition_time_s"], dtype=float)
            cur = np.array(z["current_active"], dtype=bool)
            burned = np.array(z["mask__known_burned"], dtype=bool) if "mask__known_burned" in z.files else np.zeros_like(cur)
        first = np.where(np.isfinite(ev), ev, np.inf).min(axis=0)
        first = np.where(cur | burned, 0.0, first)
        first = np.where(np.isfinite(first), np.floor(first + 1e-9), np.inf)
        first = np.where(first > fire.horizon_s, np.inf, first)
        return first[::-1].copy()
    r = geotiff.read(Path(fire.path))
    a, b, c, d, e, f = r.affine
    res = float(road.res)
    if not (r.epsg == 5179 and b == 0 and d == 0 and abs(a - res) < 1e-9 and abs(e + res) < 1e-9):
        raise _unsupported("래스터가 375 m EPSG:5179 격자가 아닙니다", "the raster is not on a 375 m EPSG:5179 lattice")
    col0 = (float(road.x0) - c) / a
    row_top = (f - (float(road.y0) + res * road.H)) / -e
    if abs(col0 - round(col0)) > 1e-6 or abs(row_top - round(row_top)) > 1e-6:
        raise _unsupported("래스터 격자가 도로 격자와 어긋납니다", "the raster lattice is offset from the road grid")
    col0, row_top = int(round(col0)), int(round(row_top))
    data = np.asarray(r.data, dtype=float)
    if r.nodata is not None and not math.isnan(r.nodata):
        data = np.where(data == r.nodata, np.nan, data)
    out = np.full((road.H, road.W), np.nan)
    for rr in range(road.H):
        src = row_top + road.H - 1 - rr
        if 0 <= src < data.shape[0]:
            lo, hi = max(col0, 0), min(col0 + road.W, data.shape[1])
            if hi > lo:
                out[rr, lo - col0:hi - col0] = data[src, lo:hi]
    hmin = fire.horizon_s / 60.0
    sec = np.where(np.isfinite(out), np.where(out <= 0, 0.0, np.floor(60.0 * out + 1e-6)), out)
    return np.where(np.isfinite(sec) & (sec > fire.horizon_s), np.inf, sec)


def landcover(rid: str):
    p = PRODUCT / "data/fuel" / ("%s_landcover.csv.gz" % rid)
    if not p.is_file():
        raise _unsupported("이 지역의 토지피복 표가 없습니다 (%s)" % p.name, "no land-cover table for this region (%s)" % p.name)
    out = {}
    with gzip.open(p, "rt", newline="") as f:
        for row in csv.DictReader(f):
            out[int(row["cell"])] = int(row["lc"]) if row["lc"] else None
    return out


def setting_from(cfg):
    h = cfg["heat"]
    level = LEVELS.get(int(h["fuel_level"]))
    if level is None:
        raise Refusal(reason("SETTINGS_INVALID", "heat.fuel_level 은 0, 1, 2 중 하나", "heat.fuel_level must be 0, 1 or 2"))
    return replace(P.BASELINE, level=level, thresholds=(float(h["threshold_kw_m2"]),))


def build(region, fire, cfg):
    """-> (HeatClosure, info dict for run.json)."""
    road = region.road
    q = float(cfg["heat"]["threshold_kw_m2"])
    st = setting_from(cfg)
    A = arrival_grid(fire, road)
    # PROTOCOL A7: a cell already burning at issue (arrival 0) with a flat arrival field takes the spread rate of the
    # nearest cells with a real gradient, not the 150 m/min cap
    R, rinfo, _src = ros.rate_of_spread_with_source(np.where(np.isfinite(A), A, np.nan), float(road.res), P.R_MIN_M_S,
                                                    P.R_MAX_M_S, known_fire=np.isfinite(A) & (A == 0))
    burning = [int(r * road.W + c) for r, c in zip(*np.nonzero(np.isfinite(A) & (A <= fire.horizon_s)))]
    lc = landcover(region.id)
    groups = np.array([fuels.group_of(lc.get(c)) if lc.get(c) is not None else "grass" for c in burning])
    Rb = np.array([R[divmod(c, road.W)] for c in burning])
    n = len(burning)
    h = cfg["heat"]
    has_rate = np.isfinite(Rb)       # a known-fire cell with no donor cell in the input has no rate: no flame
    phys = model.Evaluator(st).cells(np.where(has_rate, Rb, 1.0), groups, np.full(n, float(h["wind10_m_s"])),
                                     np.full(n, float(h["rh_pct"])), np.full(n, float(h["air_temp_c"])))
    ds = np.where(has_rate, phys["dstar_%g" % q], 0.0)
    hc = closure.HeatClosure(road, fire.arrival_s, {c: float(Rb[i]) for i, c in enumerate(burning)},
                             {c: float(ds[i]) for i, c in enumerate(burning)}, H=fire.horizon_s)
    road_d = [float(ds[i]) for i, c in enumerate(burning) if c in fire.arrival_s]
    info = {"method": "research/kcf-radiation (published methods; METHOD.md), vendored in vendor/kcf_radiation",
            "threshold_kw_m2": q, "fuel_level": st.level, "wind10_m_s": float(h["wind10_m_s"]), "rh_pct": float(h["rh_pct"]),
            "air_temp_c": float(h["air_temp_c"]), "flame_temperature_K": st.T_flame_K, "view_factor": st.vf_kind,
            "spread_rate": rinfo, "burning_cells": n,
            "road_cells_safe_distance_m_max": round(max(road_d), 1) if road_d else 0.0,
            "road_cells_safe_distance_below_375m": sum(1 for x in road_d if x < 375.0), "road_cells_reached": len(road_d),
            "crown_cells": int(np.sum(phys["crown"]))}
    return hc, info
