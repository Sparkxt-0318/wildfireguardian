"""ERA5 hourly 10 m wind gust at each GOFER fire's final-perimeter centroid (Open-Meteo archive API, keyless).

Reanalysis used as a perfect-forecast proxy for "forecast max gust" (ASSUMED stand-in, PROTOCOL class c).

    python fetch_gusts.py --gofer /path/to/GOFER --out work/gofer_gusts.csv.gz
"""
import argparse
import io
import json
import time
import urllib.request
from pathlib import Path

import pandas as pd

URL = ("https://archive-api.open-meteo.com/v1/archive?latitude={lat:.4f}&longitude={lon:.4f}"
       "&start_date={s}&end_date={e}&hourly=wind_gusts_10m&wind_speed_unit=ms&timezone=GMT")


def main():
    import geopandas as gpd
    ap = argparse.ArgumentParser()
    ap.add_argument("--gofer", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    gdf = gpd.read_file(Path(a.gofer) / "GOFER_Combined" / "GOFERC_fireProg.shp")
    gdf["t"] = pd.to_datetime(gdf["tUTC"])
    frames = []
    for name, g in gdf.groupby("fname", sort=True):
        g = g.sort_values("t")
        c = g.to_crs(3310).geometry.iloc[-1].centroid
        c = gpd.GeoSeries([c], crs=3310).to_crs(4326).iloc[0]
        s, e = g["t"].min().date(), (g["t"].max() + pd.Timedelta(days=3)).date()
        url = URL.format(lat=c.y, lon=c.x, s=s, e=e)
        for i in range(4):
            try:
                with urllib.request.urlopen(url, timeout=60) as r:
                    js = json.load(r)
                break
            except Exception as exc:  # noqa: BLE001
                print("retry", name, exc)
                time.sleep(2 ** (i + 1))
        df = pd.DataFrame({"t": pd.to_datetime(js["hourly"]["time"]), "gust_ms": js["hourly"]["wind_gusts_10m"]})
        df["fire"], df["lat"], df["lon"] = name, c.y, c.x
        frames.append(df)
        print(name, round(c.y, 3), round(c.x, 3), len(df), float(df.gust_ms.max()), flush=True)
    pd.concat(frames).to_csv(a.out, index=False)


if __name__ == "__main__":
    main()
