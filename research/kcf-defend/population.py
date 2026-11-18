"""PROTOCOL §5: HRSL general population per place (Voronoi among the 174 places, pixels within 2 km). -> population.csv, population_meta.json"""
import csv, json, math, time
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, rasterio
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[2]
URL = "https://dataforgood-fb-data.s3.amazonaws.com/hrsl-cogs/hrsl_general/hrsl_general-latest.vrt"
places = []
for r in ["yeongdeok_2025", "uiseong_andong_2025"]:
    for f in json.loads((ROOT / f"planner/public/data/regions/{r}/places.geojson").read_text())["features"]:
        p = f["properties"]
        if p["role"] == "origin" and p["checkable"]:
            places.append((p["id"], r, p.get("name") or "", p["category"], *f["geometry"]["coordinates"]))
places.sort(key=lambda x: x[0])
lon = np.array([p[4] for p in places]); lat = np.array([p[5] for p in places])
pad = 0.03
t0 = datetime.now(timezone.utc)
with rasterio.open("/vsicurl/" + URL) as ds:
    files = ds.files[:3] if hasattr(ds, "files") else []
    w = from_bounds(lon.min() - pad, lat.min() - pad, lon.max() + pad, lat.max() + pad, ds.transform)
    a = ds.read(1, window=w, boundless=True, fill_value=np.nan)
    tr = ds.window_transform(w)
vrt_head = None
import urllib.request
txt = urllib.request.urlopen(URL).read(4000).decode("utf-8", "replace")
H, W = a.shape
cols = np.arange(W); rows = np.arange(H)
plon = tr.c + (cols + 0.5) * tr.a
plat = tr.f + (rows + 0.5) * tr.e
LON, LAT = np.meshgrid(plon, plat)
v = np.nan_to_num(a, nan=0.0)
m = v > 0
PL, PA, PV = LON[m], LAT[m], v[m]

def hav(lo1, la1, lo2, la2):
    lo1, la1, lo2, la2 = map(np.radians, (lo1, la1, lo2, la2))
    h = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371008.8 * np.arcsin(np.sqrt(h))

best = np.full(PV.shape, np.inf); who = np.full(PV.shape, -1)
for i in range(len(places)):  # strict < keeps the lower (sorted) place id on ties
    dd = hav(PL, PA, lon[i], lat[i])
    k = (dd <= 2000) & (dd < best)
    best[k] = dd[k]; who[k] = i
pop = np.bincount(who[who >= 0], weights=PV[who >= 0], minlength=len(places))
with open("population.csv", "w", newline="") as fh:
    wr = csv.writer(fh); wr.writerow(["place_id", "region", "name", "category", "lon", "lat", "pop_hrsl_voronoi_2km"])
    for p, x in zip(places, pop):
        wr.writerow([p[0], p[1], p[2], p[3], round(p[4], 5), round(p[5], 5), round(float(x), 1)])
meta = {"url": URL, "retrieved_utc": t0.isoformat(timespec="seconds"), "vrt_head": txt[:600],
        "pixels_window": int(H * W), "pixels_positive": int(m.sum()), "pixels_assigned": int((who >= 0).sum()),
        "total_assigned": round(float(pop.sum()), 1), "places": len(places), "places_zero": int((pop == 0).sum())}
Path("population_meta.json").write_text(json.dumps(meta, indent=1))
print({k: meta[k] for k in meta if k != "vrt_head"})
print(sorted(zip(pop.round(0), [p[2] for p in places]))[-8:])
