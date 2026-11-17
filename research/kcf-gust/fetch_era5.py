"""Fetch ERA5 wind_gusts_10m (Open-Meteo archive, models=era5) at the 5 county seats, 2025-03-22..26. Logs source + fetch time."""
import json, sys, urllib.request, datetime as dt
PTS = {"Uiseong": (36.3527, 128.6970), "Andong": (36.5684, 128.7294), "Cheongsong": (36.4361, 129.0572),
       "Yeongyang": (36.6669, 129.1124), "Yeongdeok": (36.4150, 129.3654)}
URL = ("https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date=2025-03-22&end_date=2025-03-26"
       "&hourly=wind_gusts_10m&wind_speed_unit=ms&timezone=GMT&models=era5")
out, log = {}, []
for n, (la, lo) in PTS.items():
    u = URL.format(lat=la, lon=lo)
    t = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    import time
    for i in range(5):
        try:
            js = json.load(urllib.request.urlopen(u, timeout=60)); break
        except Exception as e:
            print("retry", n, e, file=sys.stderr); time.sleep(3 * 2 ** i)
    else:
        raise SystemExit("fetch failed: " + n)
    out[n] = dict(time_utc=js["hourly"]["time"], gust_ms=js["hourly"]["wind_gusts_10m"], grid_lat=js["latitude"], grid_lon=js["longitude"])
    log.append(dict(point=n, url=u, fetched_utc=t, grid=(js["latitude"], js["longitude"]), n=len(js["hourly"]["time"])))
json.dump(out, open("work/era5_gusts.json", "w"))
json.dump(dict(series="ERA5 via Open-Meteo archive (models=era5)", kma="NOT FETCHED: DATA_GO_KR_KEY not set; data.go.kr not reachable", fetches=log), open("work/fetch_log.json", "w"), indent=1)
print(json.dumps(log, indent=1))
