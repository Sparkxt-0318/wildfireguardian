"""Known fire area per issue hour, exactly as frozen in HOTSPOT_RULE.md (commit 796e91c).

Outputs a JSON list of fire 'discs' {src, t_utc, x, y, r_m} in EPSG:5179 plus the held-out AHI false-alarm count.
Usage: python3 -I fire_area.py OUT.json
"""
import csv, json, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[2]
FIRMS = ROOT / "research/harness-2026-11/data-fetch/small/firms"
AHI = ROOT / "research/harness-2026-11/data-fetch-2/ahi_kfs01"
TO5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
T0 = datetime(2025, 3, 22, 0, 0, tzinfo=timezone.utc)
T_LAST = datetime(2025, 3, 25, 15, 0, tzinfo=timezone.utc)


def utc(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def firms_discs():
    out = []
    for fn, inst in (("viirs-snpp_2025_Republic_of_Korea.csv", "VIIRS"), ("viirs-jpss1_2025_Republic_of_Korea.csv", "VIIRS"),
                     ("modis_2025_Republic_of_Korea.csv", "MODIS")):
        for r in csv.DictReader(open(FIRMS / fn)):
            lat, lon = float(r["latitude"]), float(r["longitude"])
            if not (128.2 <= lon <= 129.7 and 36.1 <= lat <= 36.8):
                continue
            t = datetime.strptime(r["acq_date"] + r["acq_time"].zfill(4), "%Y-%m-%d%H%M").replace(tzinfo=timezone.utc)
            if t < T0 or t > T_LAST + timedelta(hours=9):
                continue
            if r.get("type", "0") not in ("0", ""):
                continue
            if inst == "VIIRS":
                if r["confidence"] not in ("n", "h"):
                    continue
                rad = 375.0
            else:
                if int(r["confidence"]) < 30:
                    continue
                rad = 1000.0
            x, y = TO5179.transform(lon, lat)
            out.append({"src": "FIRMS-" + r["satellite"], "t_utc": t.isoformat(), "x": x, "y": y, "r_m": rad})
    return out


def load(fn):
    z = np.load(AHI / fn, allow_pickle=False)
    return z


def ahi_baseline():
    b7, bd, hrs = [], [], []
    for fn in ("kfs01_ahi_20250320T06_20250320T18.npz", "kfs01_ahi_20250320T18_20250321T06.npz"):
        z = load(fn)
        b7.append(z["b07_K"]); bd.append(z["b07_minus_b14_K"])
        hrs += [utc(s).hour for s in z["scan_start_utc"]]
    b7, bd, hrs = np.concatenate(b7), np.concatenate(bd), np.array(hrs)
    base7 = np.zeros((24, b7.shape[1])); baseD = np.zeros_like(base7)
    for hh in range(24):
        m = np.isin(hrs, [(hh - 1) % 24, hh, (hh + 1) % 24])
        base7[hh] = b7[m].max(0); baseD[hh] = bd[m].max(0)
    return base7, baseD


def ahi_hotspots(fn, base7, baseD):
    z = load(fn)
    starts = [utc(s) for s in z["scan_start_utc"]]
    ends = [utc(s) for s in z["scan_end_utc"]]
    b7, bd = z["b07_K"], z["b07_minus_b14_K"]
    hh = np.array([s.hour for s in starts])
    flag = ((b7 >= base7[hh] + 10.0) | (b7 >= 399.9)) & (bd >= baseD[hh] + 10.0)
    first = {}
    for k in range(1, len(starts)):
        both = flag[k] & flag[k - 1]
        for p in np.nonzero(both)[0]:
            if p not in first:
                first[int(p)] = ends[k]
    return first, z


def main(out):
    base7, baseD = ahi_baseline()
    held, _ = ahi_hotspots("kfs01_ahi_20250321T18_20250322T02.npz", base7, baseD)
    discs = firms_discs()
    hot, z = ahi_hotspots("kfs01_ahi_20250324T18_20250325T18.npz", base7, baseD)
    for p, t in sorted(hot.items(), key=lambda kv: kv[1]):
        discs.append({"src": "AHI", "t_utc": t.isoformat(), "x": float(z["x5179"][p]), "y": float(z["y5179"][p]),
                      "r_m": 2000.0, "pixel": p})
    # AHI coverage starts 2025-03-24 18:00 UTC; earlier fire seen only by FIRMS (stated in RESULTS.md)
    res = {"rule": "HOTSPOT_RULE.md @ 796e91c", "heldout_false_alarm_hotspots": len(held),
           "heldout_window_utc": "2025-03-21T18:00 to 2025-03-22T01:57:30", "ahi_pixels_hot": len(hot),
           "ahi_coverage_utc": ["2025-03-24T18:00:00", "2025-03-25T17:57:30"],
           "discs": sorted(discs, key=lambda d: d["t_utc"])}
    Path(out).write_text(json.dumps(res, indent=0))
    print("held-out false-alarm hotspots:", len(held), "| AHI hot pixels:", len(hot), "| FIRMS discs:",
          sum(d["src"] != "AHI" for d in discs))


if __name__ == "__main__":
    main(sys.argv[1])
