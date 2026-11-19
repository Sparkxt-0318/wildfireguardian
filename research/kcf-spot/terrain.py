"""Terrain along every spot path (PROTOCOL 2.3): elevation every 375 m from the source cell to the spot, Copernicus
90 m DEM via the Open-Meteo elevation service (keyless, 100 points per request).

    python terrain.py urls  --spots WORK/spots_*.csv --out WORK/terrain     # writes the point list and URLs
    (fetch the URLs with curl)
    python terrain.py join  --spots ... --out WORK/terrain --res derived/spot_terrain.csv
"""
import argparse, glob, json
from pathlib import Path

import numpy as np
import pandas as pd


def points(sp):
    rows = []
    for i, s in sp.iterrows():
        n = max(2, int(np.ceil(s.dist_km / 0.375)) + 1)
        f = np.linspace(0, 1, n)
        for j, u in enumerate(f):
            rows.append((i, j, s.src_lat + u * (s.lat - s.src_lat), s.src_lon + u * (s.lon - s.src_lon)))
    return pd.DataFrame(rows, columns=["row", "j", "lat", "lon"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["urls", "join"])
    ap.add_argument("--spots", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--res")
    a = ap.parse_args()
    sp = pd.concat([pd.read_csv(p) for f in a.spots for p in glob.glob(f)], ignore_index=True)
    pts = points(sp)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if a.mode == "urls":
        with open(out / "urls.txt", "w") as f:
            for k in range(0, len(pts), 100):
                q = pts.iloc[k:k + 100]
                f.write(f"{k:07d}\thttps://api.open-meteo.com/v1/elevation?latitude="
                        + ",".join(f"{v:.5f}" for v in q.lat) + "&longitude=" + ",".join(f"{v:.5f}" for v in q.lon) + "\n")
        print(len(sp), "spots", len(pts), "points")
        return
    el = []
    for k in range(0, len(pts), 100):
        el += json.load(open(out / f"{k:07d}.json"))["elevation"]
    pts["elev"] = el
    res = []
    for i, g in pts.groupby("row"):
        e = g.sort_values("j").elev.values
        s = sp.loc[i]
        top = max(e[0], e[-1])
        res.append(dict(fire=s.fire, region=s.region, spot=s.spot, elev_src_m=e[0], elev_spot_m=e[-1],
                        elev_change_m=e[-1] - e[0], path_max_above_ends_m=e.max() - top,
                        ridge_crossing=bool(e.max() - top > 50),
                        mean_abs_slope=float(np.mean(np.abs(np.diff(e))) / (s.dist_km * 1000 / max(len(e) - 1, 1)))))
    pd.DataFrame(res).to_csv(a.res, index=False)


if __name__ == "__main__":
    main()
