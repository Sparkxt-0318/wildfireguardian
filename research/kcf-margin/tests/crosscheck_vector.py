"""Independent cross-check (needs GOFER data): vector reach vs raster reach_nosep_km for random (fire, t, h=5).

Vector reach = max distance from the vertices of the h-hour-later cumulative perimeter union to the union at t (shapely).
Raster and vector differ by cell quantisation (375 m, cell-centre inclusion); expect |diff| below ~0.6 km.
    python tests/crosscheck_vector.py GOFER_DIR WORK_DIR
"""
import sys
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely import get_coordinates, points, distance, union_all

gofer, work = sys.argv[1], sys.argv[2]
g = gpd.read_file(f"{gofer}/GOFER_Combined/GOFERC_fireProg.shp").to_crs(3310)
g["t"] = pd.to_datetime(g["tUTC"])
r = pd.read_csv(f"{work}/gofer_reach.csv.gz")
r = r[(r.h == 5) & (r.reach_nosep_km > 0)].sample(40, random_state=1)
diffs = []
for _, row in r.iterrows():
    gf = g[g.fname == row.fire].sort_values("t").reset_index(drop=True)
    known = union_all(gf.geometry.iloc[:row.t_idx + 1].values)
    later = union_all(gf.geometry.iloc[:row.t_idx + 6].values)
    v = distance(points(get_coordinates(later.boundary)), known).max() / 1000
    diffs.append(v - row.reach_nosep_km)
    print(f"{row.fire:22s} t={row.t_idx:5d} raster {row.reach_nosep_km:6.2f} vector {v:6.2f}")
d = np.array(diffs)
print("diff km: median", np.median(d), "abs q90", np.quantile(abs(d), .9), "max", abs(d).max())
