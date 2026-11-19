"""Gust-rule flag (research/kcf-aloft rule G) and out-of-range flag (research/kcf-abstain primary score). PROTOCOL §5."""
from __future__ import annotations

import math
import shutil
import tempfile
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

import numpy as np

from . import common as C


def _npz(inputs: Path, manifest):
    m = manifest["sources"].get("gfs")
    if not m or not m.get("file") or not (inputs / m["file"]).exists():
        return None, m
    z = np.load(inputs / m["file"])
    return (z["arr"], z["leads"], z["lat"], z["lon"]), m


def window(gfs, t: datetime, cycle: datetime, lat: float, lon: float):
    """[8 valid hours, 7 fields, 4 points] at the four lattice points around (lat, lon); the kcf-abstain indexing."""
    arr, leads, la, lo = gfs
    i = int(math.floor((lat - la[0]) / 0.25 + 1e-9))
    j = int(math.floor((lon % 360.0 - lo[0]) / 0.25 + 1e-9))
    if not (0 <= i < la.size - 1 and 0 <= j < lo.size - 1):
        return None
    first = int((t - cycle).total_seconds() // 3600) + 1
    li = [int(np.flatnonzero(leads == L)[0]) if (leads == L).any() else -1 for L in range(first, first + 8)]
    if min(li) < 0:
        return None
    b = arr[li][:, :, i:i + 2, j:j + 2].astype(np.float64)
    return b.reshape(b.shape[0], b.shape[1], 4)


def gust_rule(gfs, t, cycle, lat, lon) -> dict:
    import rules  # research/kcf-aloft, unchanged
    col, thr, strict = rules.RULES["G"]
    b = None if gfs is None else window(gfs, t, cycle, lat, lon)
    if b is None:
        return {"state": None, "reason": "no forecast window"}
    gust = b[:, 0]
    w850 = np.hypot(b[:, 5], b[:, 6])
    lv = rules.levels(gust, w850)
    st = rules.fires(lv[col], thr, strict)
    on = None if np.isnan(st) else bool(st == 1)
    return {"state": on, "level_g_k2_ms": None if math.isnan(lv[col]) else round(lv[col], 2), "threshold_ms": thr,
            "max_gust_ms": None if np.isnan(gust).any() else round(float(gust.max()), 2),
            "reason": None if on is not None else "missing forecast values"}


@lru_cache(maxsize=1)
def _calib_frame():
    import pandas as pd
    import abstain as A  # research/kcf-abstain, unchanged
    df = pd.read_csv(C.REPO / "research/kcf-abstain/derived/hours.csv.gz", low_memory=False)
    cal = df[df["product"] == "GOFER"].copy()
    cal["scored"] = np.isfinite(cal[A.PRED].to_numpy(float)).all(axis=1)   # abstain.main's definition
    fires = sorted(cal.fire.unique())
    assert len(fires) == 28, len(fires)
    return cal.reset_index(drop=True), fires


def oor_score(values: dict) -> dict:
    """values: gust_ms, w850_ms, rhmin_pct, hdw, prior3_km (prior3 may be None). Score against all 28 calibration fires."""
    import pandas as pd
    import abstain as A
    cal, fires = _calib_frame()
    partial = values.get("prior3_km") is None
    q = {k: (np.nan if values.get(k) is None else float(values[k])) for k in A.PRED}
    q.update(fire="__query__", product="QUERY", scored=False)
    df = pd.concat([cal, pd.DataFrame([q])], ignore_index=True)
    calib = A.Calib(df, fires)
    s, p = calib.p(np.array([len(df) - 1]), fires)
    p = p[0]
    use = p[:4] if partial else p
    score = float(use.min())
    tau = C.settings()["flags"]["oor_tau"]
    j = int(np.argmin(use))
    return {"score": score, "tau": tau, "state": bool(score <= tau), "partial": partial,
            "p": {n: float(v) for n, v in zip(A.PRED, p) if not (partial and n == "prior3_km")},
            "lowest_predictor": A.PRED[j]}


def predictors(inputs: Path, manifest, t: datetime, lat: float, lon: float) -> dict:
    """The four forecast predictors, by research/kcf-abstain/predictors.one unchanged."""
    import pandas as pd
    import predictors as P
    m = manifest["sources"].get("gfs")
    if not m or not m.get("file"):
        return {"fc_note": "no_gfs"}
    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / "gfs_KOR"
        d.mkdir()
        shutil.copy(inputs / m["file"], d / (m["file"][4:]))     # gfs_YYYYMMDDHH.npz -> YYYYMMDDHH.npz
        P.load.cache_clear()
        row = pd.Series({"t_utc": pd.Timestamp(t), "model": "gfs", "region": "KOR", "lat": lat, "lon": lon})
        out = P.one(row, td)
        P.load.cache_clear()
    return out


def fire_flags(inputs: Path, manifest, t_hour: datetime, centroid: dict, prior3_km) -> dict:
    gfs, m = _npz(inputs, manifest)
    cyc = C.parse_iso(m.get("cycle_utc")) if m else None
    res = {"issue_hour_utc": C.iso(t_hour), "gfs_cycle_utc": C.iso(cyc), "gfs_complete": bool(m and m.get("complete"))}
    if gfs is None or not res["gfs_complete"]:
        res["gust"] = {"state": None, "reason": "GFS cycle missing or incomplete"}
        res["oor"] = {"state": None, "reason": "GFS cycle missing or incomplete"}
        return res
    res["gust"] = gust_rule(gfs, t_hour, cyc, centroid["lat"], centroid["lon"])
    pr = predictors(inputs, manifest, t_hour, centroid["lat"], centroid["lon"])
    vals = {k: (None if pr.get(k) is None or (isinstance(pr.get(k), float) and math.isnan(pr[k])) else round(float(pr[k]), 4))
            for k in ("gust_ms", "w850_ms", "rhmin_pct", "hdw")}
    vals["prior3_km"] = None if prior3_km is None else round(float(prior3_km), 4)
    res["predictors"] = vals
    res["predictor_note"] = pr.get("fc_note") or None
    if any(vals[k] is None for k in ("gust_ms", "w850_ms", "rhmin_pct", "hdw")):
        res["oor"] = {"state": None, "reason": "forecast predictor missing: %s" % pr.get("fc_note")}
    else:
        res["oor"] = oor_score(vals)
    return res


def bulletin_cells(inputs: Path, manifest, t_hour: datetime) -> dict:
    """Rule G for every 0.25 deg lattice cell inside the bulletin box (PROTOCOL §6)."""
    gfs, m = _npz(inputs, manifest)
    box = C.settings()["bulletin"]["box"]
    res = {"issue_hour_utc": C.iso(t_hour), "gfs_cycle_utc": m.get("cycle_utc") if m else None, "cells": []}
    if gfs is None or not (m and m.get("complete")):
        res["error"] = "GFS cycle missing or incomplete"
        return res
    cyc = C.parse_iso(m["cycle_utc"])
    lat0, lat1, lon0, lon1 = box
    for la in np.arange(lat0, lat1 - 1e-9, 0.25):
        for lo in np.arange(lon0, lon1 - 1e-9, 0.25):
            g = gust_rule(gfs, t_hour, cyc, la + 0.125, lo + 0.125)
            res["cells"].append({"lat0": round(float(la), 2), "lon0": round(float(lo), 2), "state": g["state"],
                                 "level_g_k2_ms": g.get("level_g_k2_ms"), "max_gust_ms": g.get("max_gust_ms")})
    return res
