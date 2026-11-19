#!/usr/bin/env python3
"""Label GlobFire v3 (2021) fire-days as run or quiet by the frozen rule of PROTOCOL.md section 1.1.

    python3 build_archive.py --shp .../Daily_GlobFirev3_GWIS_MCD64A1__2021.shp --out derived/archive_days.csv.gz

Daily reach of day d = largest distance from any vertex of the polygons newly burned on day d to the area burned on
all earlier days of the same fire. Distances in a local plane around the fire (x = lon * 111.32 km * cos(lat0),
y = lat * 110.57 km; equal-area to first order, error below 1% for fires under 200 km across). The first burn day is
dropped. Fires kept: at least 3 burn days and at least 10 km2 in total. Run if daily reach > 3.75 km.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
import pyogrio
import shapely

RUN_KM = 3.75
KX, KY = 111.32, 110.57


def one_fire(args):
    fid, days, geoms = args
    b = shapely.total_bounds(geoms)
    lon0, lat0 = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    c = np.cos(np.radians(lat0))
    g = shapely.transform(geoms, lambda xy: np.column_stack([(xy[:, 0] - lon0) * KX * c, (xy[:, 1] - lat0) * KY]))
    g = shapely.make_valid(g)
    rows, burned = [], None
    for d in np.unique(days):
        new = g[days == d]
        area = float(shapely.area(new).sum())
        cen = shapely.centroid(shapely.union_all(new))
        if burned is not None:
            pts = shapely.points(shapely.get_coordinates(new))
            reach = float(shapely.distance(pts, burned).max())
            rows.append(dict(fire=int(fid), day=str(d)[:10], lat=lat0 + cen.y / KY, lon=lon0 + cen.x / (KX * c),
                             new_km2=round(area, 3), reach_km=round(reach, 3), run=int(reach > RUN_KM)))
        burned = shapely.union_all(new) if burned is None else shapely.union_all([burned, *new])
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--procs", type=int, default=3)
    a = ap.parse_args()
    df = pyogrio.read_dataframe(a.shp)
    print("polygons", len(df), "fires", df.Id.nunique(), flush=True)
    geoms = df.geometry.values
    lat = shapely.get_y(shapely.centroid(geoms))
    df["km2"] = shapely.area(geoms) * KX * KY * np.cos(np.radians(lat))
    agg = df.groupby("Id").agg(days=("IDate", "nunique"), km2=("km2", "sum"))
    keep = agg[(agg.days >= 3) & (agg.km2 >= 10)].index
    print("fires kept", len(keep), "of", len(agg), flush=True)
    df = df[df.Id.isin(keep)].sort_values(["Id", "IDate"])
    jobs = [(fid, g.IDate.values.astype("datetime64[D]"), g.geometry.values) for fid, g in df.groupby("Id")]
    rows = []
    with ProcessPoolExecutor(a.procs) as ex:
        for r in ex.map(one_fire, jobs, chunksize=200):
            rows += r
    out = pd.DataFrame(rows)
    out.to_csv(a.out, index=False)
    print("fire-days", len(out), "fires", out.fire.nunique(), flush=True)


if __name__ == "__main__":
    main()
