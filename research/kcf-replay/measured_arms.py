"""Arms 4 (MEASURED) and 5 (MEASURED_GUST), as frozen in MEASURED_RULE.md. R values copied from research/kcf-margin/numbers.json
(table, all28, alpha 0.10); asserted against it at import when the file is present."""
from __future__ import annotations
import json, math
from datetime import datetime, timedelta, timezone
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
R_KM = {  # class -> (R5, R8) km
    "all": (3.8, 5.0), "quiet": (2.6, 3.5), "slow": (5.0, 6.4), "running": (7.6, 10.0),
    "g<10": (2.6, 3.0), "g10-20": (4.7, 5.9), "g>=20": (8.6, 12.0),
}
ARMS = ("MEASURED", "MEASURED_GUST", "MEASURED_GUST_KMA")


def _check():
    p = HERE.parent / "kcf-margin/numbers.json"
    if not p.exists():
        return
    N = json.loads(p.read_text())["table"]
    want = {"all": "all", "quiet": "quiet", "slow": "slow", "running": "running", "g<10": "gust<10", "g10-20": "gust10-20", "g>=20": "gust>=20"}
    seen = 0
    for r in N:
        if r["fire_set"] == "all28" and abs(r["alpha"] - .1) < 1e-9 and r["h"] in (5, 8):
            for k, name in want.items():
                if r["cls"] == name:
                    assert abs(r["R_km"] - R_KM[k][0 if r["h"] == 5 else 1]) < 0.06, (k, r["h"], r["R_km"])
                    seen += 1
    assert seen == 14, seen
_check()


def spread_class(discs, T):
    """Prior-3 h spread class at T from the known-fire-area discs (MEASURED_RULE.md)."""
    cut = T - timedelta(hours=3)
    prior = [d for d in discs if d["t"] < cut]
    new = [d for d in discs if cut <= d["t"] < T]
    if not prior:
        return "all", None
    PX = np.array([d["x"] for d in prior]); PY = np.array([d["y"] for d in prior]); PR = np.array([d["r_m"] for d in prior])
    spread = 0.0
    for d in new:
        dd = max(0.0, float((np.hypot(PX - d["x"], PY - d["y"]) - PR).min()))
        if dd <= 5000.0:
            spread = max(spread, dd)
    km = spread / 1000.0
    return ("quiet" if km < 1 else "slow" if km < 3 else "running"), km


_GUST = None
def gust_class(T, H_h):
    """Max over the five points of the max gust over (T, T+H] from ERA5 (KMA if fetched; see kcf-gust). Stamp = end of hour."""
    global _GUST
    if _GUST is None:
        _GUST = json.loads((HERE.parent / "kcf-gust/work/era5_gusts.json").read_text())
    m = -1.0
    for k in range(1, H_h + 1):
        s = (T + timedelta(hours=k)).strftime("%Y-%m-%dT%H:00")
        for p, v in _GUST.items():
            m = max(m, v["gust_ms"][v["time_utc"].index(s)])
    return ("g<10" if m < 10 else "g10-20" if m < 20 else "g>=20"), m


_KMA = None
def _kma_val(stn, stamp_utc):
    """KMA ASOS hourly gust at a stamp (UTC datetime = end of hour), PROTOCOL amendments 2-3 of research/kcf-gust: a record counts only if
    GST_TM is inside the hour before the stamp; no record (-9) = no gust >= 10 m/s = 0; no row = None."""
    global _KMA
    if _KMA is None:
        rows = json.loads((HERE.parent / "kcf-gust/work/kma_asos_hourly.json").read_text())
        _KMA = {(r["tm"], r["stn"]): r for r in rows}
    k = stamp_utc + timedelta(hours=9)
    r = _KMA.get((k.strftime("%Y%m%d%H00"), stn))
    if r is None:
        return None
    g = float(r["gst_ws"])
    if g < 0:
        return 0.0
    gm = int(r["gst_tm"].zfill(4)[:2]) * 60 + int(r["gst_tm"].zfill(4)[2:])
    hd = k.hour; lo = ((hd - 1) % 24) * 60; hi = hd * 60 if hd else 1440
    ok = (lo < gm <= hi) if hd else (gm > 1380 or gm == 0)
    return g if ok else 0.0


def gust_class_kma(T, H_h):
    m = -1.0
    for k in range(1, H_h + 1):
        for stn in (278, 136, 276, 277):
            v = _kma_val(stn, T + timedelta(hours=k))
            if v is not None:
                m = max(m, v)
    return ("g<10" if m < 10 else "g10-20" if m < 20 else "g>=20"), m


def curve(arm, discs, T, H_h):
    """-> (R5_m, R8_m, label, info)"""
    if arm == "MEASURED":
        c, info = spread_class(discs, T)
    elif arm == "MEASURED_GUST_KMA":
        c, info = gust_class_kma(T, H_h)
    else:
        c, info = gust_class(T, H_h)
    r5, r8 = R_KM[c]
    return r5 * 1000.0, r8 * 1000.0, c, info


def closure_s(R5, R8, d_m):
    """Seconds after issue when a cell at distance d_m closes: curve (0,0)-(5 h,R5)-(8 h,R8) linear; beyond R8 never."""
    if d_m <= R5:
        return d_m / R5 * 5 * 3600.0
    if d_m <= R8:
        return (5 + (d_m - R5) / (R8 - R5) * 3) * 3600.0
    return math.inf
