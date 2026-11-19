#!/usr/bin/env python3
"""Truth wind at every fire (PROTOCOL section 1): hourly series, one location per fire (mean issue-hour position).

  ERA5 10 m gust and 10 m wind speed     archive-api.open-meteo.com   (reanalysis)
  850 hPa wind speed                      historical-forecast-api.open-meteo.com (model archive, short lead)

    python fetch_truth_wind.py --out derived/truth_wind.csv.gz
"""
import argparse
import json
import time
import urllib.request
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ABSTAIN = HERE.parent / "kcf-abstain"
ERA = ("https://archive-api.open-meteo.com/v1/archive?latitude={lat:.3f}&longitude={lon:.3f}&start_date={a}&end_date={b}"
       "&hourly=wind_gusts_10m,wind_speed_10m&wind_speed_unit=ms&timezone=GMT")
HF = ("https://historical-forecast-api.open-meteo.com/v1/forecast?latitude={lat:.3f}&longitude={lon:.3f}&start_date={a}"
      "&end_date={b}&hourly=wind_speed_850hPa,wind_gusts_10m&wind_speed_unit=ms&timezone=GMT")


def get(u):
    for i in range(6):
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "research-fetch/1"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
        except Exception as e:  # noqa: BLE001
            err = e
            time.sleep(3 + 3 * i)
    raise err


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    h = pd.read_csv(ABSTAIN / "derived/hours.csv.gz", low_memory=False)
    h = h[(h["product"] == "GOFER") | (h.country == "KR")]
    h["t"] = pd.to_datetime(h.t_utc)
    g = h.groupby("fire").agg(lat=("lat", "mean"), lon=("lon", "mean"), t0=("t", "min"), t1=("t", "max")).reset_index()
    out, log = [], []
    for r in g.itertuples():
        d0 = (r.t0 - pd.Timedelta(days=2)).strftime("%Y-%m-%d")
        d1 = (r.t1 + pd.Timedelta(days=2)).strftime("%Y-%m-%d")
        e = get(ERA.format(lat=r.lat, lon=r.lon, a=d0, b=d1))
        f = get(HF.format(lat=r.lat, lon=r.lon, a=d0, b=d1))
        de = pd.DataFrame(e["hourly"]).rename(columns={"wind_gusts_10m": "era5_gust_ms", "wind_speed_10m": "era5_w10_ms"})
        df = pd.DataFrame(f["hourly"]).rename(columns={"wind_speed_850hPa": "hf_w850_ms", "wind_gusts_10m": "hf_gust_ms"})
        m = de.merge(df, on="time", how="outer")
        m.insert(0, "fire", r.fire)
        out.append(m)
        log.append(dict(fire=r.fire, lat=round(r.lat, 3), lon=round(r.lon, 3), start=d0, end=d1,
                        era5_grid=[e["latitude"], e["longitude"]], hf_grid=[f["latitude"], f["longitude"]],
                        n=len(m), era5_gust_missing=int(m.era5_gust_ms.isna().sum()),
                        hf_w850_missing=int(m.hf_w850_ms.isna().sum()),
                        fetched_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))
        print(log[-1], flush=True)
        time.sleep(1.0)
    d = pd.concat(out, ignore_index=True).rename(columns={"time": "t_utc"})
    d["t_utc"] = pd.to_datetime(d.t_utc).dt.strftime("%Y-%m-%d %H:%M:%S")
    d.to_csv(a.out, index=False)
    Path(a.out).with_suffix("").with_suffix(".log.json").write_text(json.dumps(log, indent=1))


if __name__ == "__main__":
    main()
