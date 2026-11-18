"""ERA5 hourly 10 m wind speed and direction at each Arm 2 fire's wind point (Open-Meteo archive, keyless).

One request per fire, cached; a 429 (daily quota) stops the run with everything fetched so far kept.
The value at the issue hour stands in for an observation available then (ASSUMED, PROTOCOL 3.2).

    python fetch_wind.py --work WORK --choi CHOI_DIR --out derived/wind.csv.gz
"""
import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd

import fires as F

URL = ("https://archive-api.open-meteo.com/v1/archive?latitude={lat:.4f}&longitude={lon:.4f}"
       "&start_date={s}&end_date={e}&hourly=wind_speed_10m,wind_direction_10m&models=era5"
       "&wind_speed_unit=kmh&timezone=GMT")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True, type=Path)
    ap.add_argument("--choi", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    cache = a.work / "wind_raw"
    cache.mkdir(parents=True, exist_ok=True)
    kr, _ = F.choi_kr(a.choi)
    allf = F.gofer(a.work) + kr + [F.det()]
    frames, missing = [], []
    for f in allf:
        lon, lat = f.wind_point()
        t = [f.time(x) for h in F.HORIZONS for x in (f.issue[h][0], f.issue[h][-1] + h) if len(f.issue[h])]
        s, e = min(t).date(), (max(t) + pd.Timedelta(days=1)).date()
        path = cache / f"{f.name.replace(' ', '_')}.json"
        if not path.exists():
            url = URL.format(lat=lat, lon=lon, s=s, e=e)
            for attempt in range(4):
                try:
                    with urllib.request.urlopen(url, timeout=90) as r:
                        path.write_bytes(r.read())
                    break
                except urllib.error.HTTPError as exc:
                    if exc.code == 429:
                        print(f"QUOTA (429) at {f.name}; stopping. {exc.read()[:120]!r}", flush=True)
                        missing.append(f.name)
                        break
                    time.sleep(5 * (attempt + 1))
                except Exception as exc:  # noqa: BLE001
                    print(f"{f.name}: {exc}", flush=True)
                    time.sleep(5 * (attempt + 1))
            time.sleep(1.0)
        if not path.exists():
            if f.name not in missing:
                missing.append(f.name)
            if missing and len(missing) == 1 and "QUOTA" in "":
                pass
            continue
        js = json.loads(path.read_text())
        d = pd.DataFrame(dict(t=pd.to_datetime(js["hourly"]["time"]), speed_kmh=js["hourly"]["wind_speed_10m"],
                              dir_from_deg=js["hourly"]["wind_direction_10m"]))
        d["fire"], d["lat"], d["lon"] = f.name, lat, lon
        d["grid_lat"], d["grid_lon"] = js["latitude"], js["longitude"]
        if js["hourly_units"]["wind_speed_10m"] != "km/h":
            raise ValueError("unexpected wind unit")
        frames.append(d)
        print(f"{f.name:28s} {len(d)} h  {s}..{e}  at {lat:.3f},{lon:.3f}", flush=True)
    if frames:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        pd.concat(frames).to_csv(a.out, index=False)
    print("missing:", missing)


if __name__ == "__main__":
    main()
