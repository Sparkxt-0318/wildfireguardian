#!/usr/bin/env python3
"""POST HOC (not in PROTOCOL.md): is the GFS 850 hPa wind that drove the 25 March abstentions an artefact of one model?

    python3 crosscheck_ecmwf.py --hours derived/hours.csv.gz --nwp NWP_DIR --out derived/ecmwf_crosscheck.json

For each 25 March issue hour (DET rows), the same cycle rule (latest 00/06/12/18 UTC cycle at least 5 h old) and the same
four 0.25 deg lattice points, the ECMWF IFS 0.25 deg open-data forecast (AWS `ecmwf-forecasts`, 3-hourly steps) gives the
maximum 850 hPa wind over the valid times inside (t, t+8]. GFS is read at the same valid times for a like-for-like
comparison. Also: where the 25 March predictor values sit in the calibration distribution (fire-weighted quantiles
and the maximum over all 28 fires). Nothing here changes any score, threshold or result.
"""
import argparse
import json
import math
import urllib.request

import numpy as np
import pandas as pd
import pygrib

B = "https://ecmwf-forecasts.s3.amazonaws.com"


def get(url, rng=None, attempts=6):
    import time
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "wfg-kcf-abstain/1"})
            if rng:
                req.add_header("Range", f"bytes={rng[0]}-{rng[1]}")
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except Exception:
            if i == attempts - 1:
                raise
            time.sleep(2 ** (i + 1))


def ifs_uv850(cyc, step):
    d, hh = cyc.strftime("%Y%m%d"), cyc.strftime("%H")
    stream = "oper" if hh in ("00", "12") else "scda"
    base = f"{B}/{d}/{hh}z/ifs/0p25/{stream}/{d}{hh}0000-{step}h-{stream}-fc"
    idx = [json.loads(x) for x in get(base + ".index").decode().splitlines() if x.strip()]
    out = {}
    for p in ("u", "v"):
        e = [x for x in idx if x.get("levelist") == "850" and x.get("param") == p][0]
        m = pygrib.fromstring(get(base + ".grib2", (e["_offset"], e["_offset"] + e["_length"] - 1)))
        out[p] = m
    lats, lons = out["u"].latlons()
    return out["u"].values, out["v"].values, lats[:, 0], lons[0, :]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", required=True)
    ap.add_argument("--nwp", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    df = pd.read_csv(a.hours, low_memory=False)
    det = df[df["product"] == "DET"].sort_values("kst_hour")
    cache, rows = {}, []
    for r in det.itertuples():
        t = pd.Timestamp(r.t_utc)
        c = (t - pd.Timedelta(hours=5)).floor("6h")
        lat_lo = math.floor(r.lat / 0.25) * 0.25
        lon_lo = math.floor(r.lon / 0.25) * 0.25
        pts = [(lat_lo + i * 0.25, lon_lo + j * 0.25) for i in (0, 1) for j in (0, 1)]
        steps = [s for s in range(0, 25, 3) if t < c + pd.Timedelta(hours=s) <= t + pd.Timedelta(hours=8)]
        ifs, gfs = [], []
        z = np.load(f"{a.nwp}/gfs_KOR/{c.strftime('%Y%m%d%H')}.npz")
        for s in steps:
            key = (c, s)
            if key not in cache:
                cache[key] = ifs_uv850(c, s)
            u, v, la, lo = cache[key]
            for (pla, plo) in pts:
                i = int(np.argmin(abs(la - pla)))
                j = int(np.argmin(abs(lo - (plo if plo <= 180 else plo - 360))))
                ifs.append(float(np.hypot(u[i, j], v[i, j])))
                gi = int(np.argmin(abs(z["lat"] - pla)))
                gj = int(np.argmin(abs(z["lon"] - plo)))
                li = int(np.flatnonzero(z["leads"] == s)[0])
                gfs.append(float(np.hypot(z["arr"][li, 5, gi, gj], z["arr"][li, 6, gi, gj])))
        rows.append(dict(kst_hour=int(r.kst_hour), cycle_utc=str(c), steps_h=steps,
                         ifs_max_w850_ms=max(ifs), gfs_same_times_max_w850_ms=max(gfs),
                         gfs_hourly_max_w850_ms=float(r.w850_ms)))
        print(rows[-1], flush=True)
    cal = df[(df["product"] == "GOFER") & df.score.notna()]
    ctx = {}
    for col in ("gust_ms", "w850_ms", "rhmin_pct", "hdw", "prior3_km"):
        w = 1.0 / cal.groupby("fire")[col].transform("size")
        v = cal[col].to_numpy()
        o = np.argsort(v)
        cw = np.cumsum(w.to_numpy()[o]) / w.sum()
        q = {f"q{int(p * 100)}": float(v[o][np.searchsorted(cw, p)]) for p in (0.01, 0.5, 0.9, 0.99)}
        q.update(min=float(v.min()), max=float(v.max()), fire_at_max=cal.fire.iloc[int(np.argmax(v))] if col != "rhmin_pct"
                 else cal.fire.iloc[int(np.argmin(v))])
        ctx[col] = q
    out = dict(label="POST HOC, not in PROTOCOL.md; changes nothing", hours=rows,
               calibration_distribution_fire_weighted=ctx)
    json.dump(out, open(a.out, "w"), indent=1)
    print(json.dumps(ctx, indent=1))


if __name__ == "__main__":
    main()
