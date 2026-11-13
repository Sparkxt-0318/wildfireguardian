#!/usr/bin/env python3
"""Cell-level check (S-D9 A1 4.1 rule 5): is the kriged arrival raster valid on exactly the final NIROPS union?
usage: arrival_vs_union.py EVENTS_JSON ENV_ROOT NIROPS_SHP ARCHIVE_EXTRACTED OUT_CSV
For each US event in EVENTS_JSON (the 44 exposed project events):
  valid  = finite and != nodata in ENV_ROOT/regions/<id>/arrival_time_hours.tif (inventory output)
  union  = last cumulative state from the repo's wildfire.survival.survey_states over the NIROPS features of that
           Incident_C (cell centres), on the events.json grid
  grid   = regions raster shape/transform/crs vs events.json record vs the archive <id>_pswt_ok_toa.tif
Also: valid-cell counts of the KR rasters (counts only)."""
import csv, hashlib, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'repo_forecast'))
import numpy as np, pandas as pd, pyogrio, rasterio, shapely
from wildfire.survival import survey_states

ev_path, env, shp, arc, out = map(Path, sys.argv[1:6])
events = json.loads(ev_path.read_text())
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()

def valid_mask(p):
    with rasterio.open(p) as r:
        a = r.read(1, masked=True)
        v = ~np.ma.getmaskarray(a) & np.isfinite(a.filled(np.nan))
        return v, r.shape, tuple(round(x, 6) for x in list(r.transform)[:6]), r.crs.to_epsg()

rows = []
for e in events:
    eid = e['id']
    if e['country'] != 'US':
        continue
    rp = env / 'regions' / eid / 'arrival_time_hours.tif'
    ap = arc / 'rasters_us' / f'{eid}_pswt_ok_toa.tif'
    v, shape, tr, epsg = valid_mask(rp)
    va, shape_a, tr_a, epsg_a = valid_mask(ap)
    rec = ((e['height'], e['width']), tuple(round(x, 6) for x in e['transform']), e['epsg'])
    g = pyogrio.read_dataframe(shp, where=f"Incident_C = '{eid}'", fid_as_index=True)
    r = dict(event=eid, grid_h=shape[0], grid_w=shape[1],
             grid_regions_eq_events_json=(shape, tr, epsg) == rec,
             grid_archive_eq_events_json=(shape_a, tr_a, epsg_a) == rec,
             archive_valid_eq_regions_valid=bool(shape_a == shape and (va == v).all()),
             arrival_valid=int(v.sum()), nirops_features=len(g))
    if len(g):
        feats = []
        for fid, row in g.iterrows():
            st = pd.Timestamp(row['UTC']); st = st.tz_localize('UTC') if st.tzinfo is None else st.tz_convert('UTC')
            feats.append(dict(type='Feature', id=int(fid), properties=dict(time_utc=st.isoformat()),
                              geometry=shapely.geometry.mapping(row.geometry)))
        feats.sort(key=lambda f: (f['properties']['time_utc'], f['id']))
        times, states = survey_states(feats, e)
        u = states[-1].astype(bool)
        r.update(nirops_survey_times=len(times), final_union=int(u.sum()),
                 valid_not_union=int((v & ~u).sum()), union_not_valid=int((u & ~v).sum()),
                 identical=bool((v == u).all()), last_survey_utc=str(times[-1]))
    r.update(regions_sha256=sha(rp), archive_sha256=sha(ap))
    rows.append(r); print({k: r.get(k) for k in ('event', 'grid_h', 'grid_w', 'arrival_valid', 'final_union', 'valid_not_union', 'union_not_valid', 'grid_regions_eq_events_json', 'grid_archive_eq_events_json')}, flush=True)

keys = sorted({k for r in rows for k in r}, key=lambda k: list(rows[0]).index(k) if k in rows[0] else 99)
keys = ['event','grid_h','grid_w','grid_regions_eq_events_json','grid_archive_eq_events_json','archive_valid_eq_regions_valid',
        'arrival_valid','nirops_features','nirops_survey_times','last_survey_utc','final_union','valid_not_union','union_not_valid',
        'identical','regions_sha256','archive_sha256']
with open(out, 'w', newline='') as f:
    w = csv.DictWriter(f, keys); w.writeheader(); w.writerows(rows)
kr = sorted((arc / 'rasters_kr').glob('*_toa.tif'))
print('KR toa rasters:', len(kr))
for p in kr:
    v, shape, *_ = valid_mask(p); print(f'  {p.name.split("_pswt")[0]} valid {int(v.sum())} of {shape[0]*shape[1]} ({shape[0]}x{shape[1]})')
