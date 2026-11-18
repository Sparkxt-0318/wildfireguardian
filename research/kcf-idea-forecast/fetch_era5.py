"""Fetch hourly ERA5 wind (Open-Meteo archive) for a list of points and date ranges.

    python3 fetch_era5.py ca  OUT.csv.gz     # 28 GOFER fires, point and period from kcf-margin/derived/gofer_gusts.csv.gz
    python3 fetch_era5.py kr  OUT.csv.gz     # five Gyeongbuk county-seat cells of kcf-gust, 2025-03-24..26 (TEST ONLY)

Variables: wind_speed_10m, wind_speed_100m, wind_direction_10m, wind_direction_100m, wind_gusts_10m (m/s, deg, GMT).
"""
import gzip, io, json, sys, time
from pathlib import Path
import pandas as pd, requests

URL = "https://archive-api.open-meteo.com/v1/archive"
VARS = "wind_speed_10m,wind_speed_100m,wind_direction_10m,wind_direction_100m,wind_gusts_10m"
HERE = Path(__file__).resolve().parent
KR = {"Uiseong": (36.25, 128.75), "Andong": (36.5, 128.75), "Cheongsong": (36.5, 129.0),
      "Yeongyang": (36.75, 129.0), "Yeongdeok": (36.5, 129.25)}


def get(lat, lon, d0, d1):
    for k in range(5):
        r = requests.get(URL, params=dict(latitude=lat, longitude=lon, start_date=d0, end_date=d1, hourly=VARS,
                                          models="era5", wind_speed_unit="ms", timezone="GMT"), timeout=60)
        if r.status_code == 200:
            j = r.json(); d = pd.DataFrame(j["hourly"]); d["grid_lat"] = j["latitude"]; d["grid_lon"] = j["longitude"]
            return d
        time.sleep(5 * (k + 1))
    raise RuntimeError(r.text[:200])


def main():
    which, out = sys.argv[1], sys.argv[2]
    rows = []
    if which == "ca":
        g = pd.read_csv(HERE.parent / "kcf-margin/derived/gofer_gusts.csv.gz", parse_dates=["t"])
        for fire, s in g.groupby("fire"):
            d = get(s.lat.iloc[0], s.lon.iloc[0], str(s.t.min().date()), str(s.t.max().date()))
            d.insert(0, "fire", fire); d["lat"] = s.lat.iloc[0]; d["lon"] = s.lon.iloc[0]; rows.append(d)
            print(fire, len(d), flush=True); time.sleep(1)
    else:
        for name, (la, lo) in KR.items():
            d = get(la, lo, "2025-03-24", "2025-03-26"); d.insert(0, "fire", name); d["lat"] = la; d["lon"] = lo
            rows.append(d); time.sleep(1)
    pd.concat(rows).rename(columns={"time": "t"}).to_csv(out, index=False)
    print("wrote", out, "fetched_utc", pd.Timestamp.now("UTC").isoformat())


if __name__ == "__main__":
    main()
