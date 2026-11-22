#!/usr/bin/env python3
"""Build a per-incident perimeter series (NIROPS archive schema) from a folder of raw nightly IR shapefiles.

Rule frozen in ACCEPTANCE_TEST_GEOMETRY_DIXIE.md (commit 30806ce8):
 1. one input file = one night; date D = the first 8 characters of the file name (YYYYMMDD);
 2. files whose name contains IntenseHeat or ScatteredHeat are dropped;
 3. inside a file, if any feature's Name contains "Heat", keep only features whose Name contains "Perimeter";
 4. geometry: buffer(0), union of the kept features (EPSG:4326);
 5. output: Incident_C, UTC (empty: no flight time in KMZ-derived input), DateUTC = D, Acres (area in EPSG:5070),
    time_source, geometry; one feature per night, sorted by DateUTC.
Usage: python3 -I build_ir_series.py INCIDENT_C RAW_DIR OUT.gpkg
"""
import glob, os, re, sys
import geopandas as gpd, pandas as pd, pyogrio
from shapely.ops import unary_union

ACRE = 4046.8564224


def build(incident, raw_dir):
    rows = []
    for f in sorted(glob.glob(os.path.join(raw_dir, '*.shp'))):
        b = os.path.basename(f)
        if re.search(r'IntenseHeat|ScatteredHeat', b):
            continue
        d = pd.to_datetime(b[:8], format='%Y%m%d')
        g = pyogrio.read_dataframe(f)
        g = g.set_crs(4326) if g.crs is None else g.to_crs(4326)
        if 'Name' in g and g['Name'].astype(str).str.contains('Heat').any():
            g = g[g['Name'].astype(str).str.contains('Perimeter')]
        if g.empty:
            continue
        geom = unary_union([x.buffer(0) for x in g.geometry if x is not None])
        rows.append(dict(Incident_C=incident, UTC=None, DateUTC=d.strftime('%Y-%m-%d'),
                         time_source='none (KMZ-derived; date from file name)', source_file=b, geometry=geom))
    out = gpd.GeoDataFrame(rows, crs=4326)
    out['Acres'] = out.to_crs(5070).area / ACRE
    return out.sort_values(['DateUTC', 'source_file']).reset_index(drop=True)


if __name__ == '__main__':
    inc, raw, outp = sys.argv[1:4]
    o = build(inc, raw)
    if os.path.exists(outp):
        os.remove(outp)
    o.to_file(outp, driver='GPKG')
    print(f'{inc}: {len(o)} nights -> {outp}')
