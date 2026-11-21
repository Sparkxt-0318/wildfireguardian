#!/usr/bin/env python3
"""Acceptance test 2 (geometry only), as frozen in ACCEPTANCE_TEST_GEOMETRY_DIXIE.md.
Usage: python3 -I compare_geometry_dixie.py NIROPS.shp BUILT.gpkg"""
import os, sys
import geopandas as gpd, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'nirops_access'))
import nirops_access as na

INC = 'CA-BTU-009205_Dixie'
shp, built_p = sys.argv[1:3]
arch = na.read_incident(shp, INC, {INC}).to_crs(5070)
arch['UTC'] = pd.to_datetime(arch['UTC'])
arch['d'] = arch['UTC'].dt.strftime('%Y-%m-%d')
built = gpd.read_file(built_p).to_crs(5070)
rows = []
for _, b in built.iterrows():
    a = arch[arch.d == b.DateUTC]
    if a.empty:
        rows.append(dict(DateUTC=b.DateUTC, n_archive_same_date=0)); continue
    best = None
    for _, x in a.iterrows():
        iou = b.geometry.intersection(x.geometry).area / b.geometry.union(x.geometry).area
        if best is None or iou > best[0]:
            best = (iou, x)
    iou, x = best
    rel = abs(b.Acres - x.Acres) / x.Acres
    rows.append(dict(DateUTC=b.DateUTC, n_archive_same_date=len(a), archive_UTC=str(x.UTC), iou=round(iou, 5),
                     acres_built=round(b.Acres, 1), acres_archive=round(x.Acres, 1), rel_area_err=round(rel, 5),
                     G1=iou >= 0.99, G2=rel <= 0.005))
r = pd.DataFrame(rows)
m = r[r.n_archive_same_date > 0]
print(r.to_string(index=False))
unbuilt = sorted(set(arch.d) - set(built.DateUTC))
print(f'\nnights built {len(built)}; matched {len(m)}; built with no archive survey {int((r.n_archive_same_date == 0).sum())}; '
      f'archive surveys {len(arch)} on {arch.d.nunique()} dates, dates with no built night {len(unbuilt)}')
print(f'G1 (IoU>=0.99) {int(m.G1.sum())}/{len(m)}; G2 (area err<=0.5%) {int(m.G2.sum())}/{len(m)}; both {int((m.G1 & m.G2).sum())}/{len(m)}')
print(f'IoU median {m.iou.median():.4f} min {m.iou.min():.4f}; rel area err median {m.rel_area_err.median():.4f} max {m.rel_area_err.max():.4f}')
print('multiple archive surveys on the same date:', int((m.n_archive_same_date > 1).sum()), 'nights')
print('RESULT:', 'PASS(geometry)' if bool((m.G1 & m.G2).all()) else 'PARTIAL', '- survey times NOT TESTED (no times in input)')
