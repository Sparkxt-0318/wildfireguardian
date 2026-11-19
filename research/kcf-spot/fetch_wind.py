"""ERA5 hourly 10 m wind direction, speed and gust at each fire (Open-Meteo archive, keyless). PROTOCOL section 1.

Fire locations: median lat/lon of the fire's rows in kcf-abstain hours.csv.gz; Korean fires not there: centroid of the
Choi arrival raster. Date range: first to last arrival of the fire's product, padded by 2 days.

    python fetch_wind.py --choi DATA/choi/x --out derived/era5_wind.csv.gz
"""
import argparse, json, subprocess, time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ABSTAIN = HERE.parent / "kcf-abstain/derived/hours.csv.gz"


def fires(choi):
    import rasterio
    from pyproj import Transformer
    h = pd.read_csv(ABSTAIN, low_memory=False, usecols=["fire", "product", "country", "t_utc", "lat", "lon"])
    h = h[h["product"].isin(["GOFER", "CHOI", "DET"])]
    out = {}
    for f, g in h.groupby("fire"):
        t = pd.to_datetime(g.t_utc)
        out[f] = dict(lat=float(g.lat.median()), lon=float(g.lon.median()), t0=t.min(), t1=t.max(),
                      country=g.country.iloc[0])
    ev = pd.read_csv(next(Path(choi).rglob("kr_events_21.csv")))
    tr = Transformer.from_crs(5179, 4326, always_xy=True)
    for _, e in ev[ev.produced == 1].iterrows():
        p = Path(choi) / "rasters_kr" / f"{e.id}_pswt_ok_toa.tif"
        with rasterio.open(p) as ds:
            v = ds.read(1, masked=True).filled(np.nan)
            tf = ds.transform
        r, c = np.nonzero(np.isfinite(v))
        x, y = tf * (c.mean() + 0.5, r.mean() + 0.5)
        lon, lat = tr.transform(x, y)
        t0 = pd.Timestamp(e.t0_utc)
        rec = out.get(e.id, {})
        out[e.id] = dict(lat=rec.get("lat", lat), lon=rec.get("lon", lon), t0=min(rec.get("t0", t0), t0),
                         t1=max(rec.get("t1", t0), t0 + pd.Timedelta(hours=float(np.nanmax(v)))), country="KR")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--choi", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    fr = fires(a.choi)
    rows = []
    for f, d in sorted(fr.items()):
        s = (d["t0"] - pd.Timedelta(days=2)).strftime("%Y-%m-%d")
        e = (d["t1"] + pd.Timedelta(days=2)).strftime("%Y-%m-%d")
        url = (f"https://archive-api.open-meteo.com/v1/archive?latitude={d['lat']:.4f}&longitude={d['lon']:.4f}"
               f"&start_date={s}&end_date={e}&hourly=wind_direction_10m,wind_speed_10m,wind_gusts_10m"
               f"&wind_speed_unit=ms&timezone=GMT&models=era5")
        for k in range(5):
            r = subprocess.run(["curl", "-sf", "--max-time", "300", url], capture_output=True, text=True)
            if r.returncode == 0:
                break
            time.sleep(10 * (k + 1))
        j = json.loads(r.stdout)["hourly"]
        df = pd.DataFrame(j)
        df["fire"], df["lat"], df["lon"] = f, d["lat"], d["lon"]
        rows.append(df)
        print(f, s, e, len(df), flush=True)
    out = pd.concat(rows, ignore_index=True).rename(columns={"time": "t_utc", "wind_direction_10m": "era5_dir_deg",
                                                             "wind_speed_10m": "era5_ws_ms", "wind_gusts_10m": "era5_gust_ms"})
    out.to_csv(a.out, index=False)


if __name__ == "__main__":
    main()
