"""Price the part-a pool (allowlist only): grid per build_nirops_event rule, O1280 nodes, days.
v2: reads the Incident_C column alone, then UTC + geometry BY FID for allowlisted records only (nirops_access.py).
v1 (uncommitted, run 12 Nov ~13:05 UTC) read Incident_C+UTC for all records and filtered in memory; see ACCESS_LOG.md."""
import os; sys_path_dir = os.path.dirname(os.path.abspath(__file__))
import csv, sys, json, numpy as np, pandas as pd, pyogrio, shapely
from affine import Affine
from wildfire import environment as env
shp, allow, out = sys.argv[1:4]
ids = [r['Incident_C'] for r in csv.DictReader(open(allow))]
assert not {'MossMountain_Chalk', 'Homestead_Salmon33'} & {i.split('_', 1)[-1] for i in ids}
sys.path.insert(0, sys_path_dir); import nirops_access as na
idx = na.id_index(shp)                      # Incident_C only, all records
rows = []
for k, inc in enumerate(sorted(set(idx[idx.isin(ids)]))):
    g0 = na.read_incident(shp, inc, ids, idx)   # geometry + UTC by fid, allowlisted only
    grp = g0; g = g0.to_crs(5070)
    x0, y0, x1, y1 = shapely.union_all(shapely.make_valid(g.geometry.values)).bounds
    gx0 = np.floor((x0 - 2000) / 375) * 375; gy1 = np.ceil((y1 + 2000) / 375) * 375
    w = int(np.ceil((x1 + 2000 - gx0) / 375)); h = int(np.ceil((gy1 - (y0 - 2000)) / 375))
    tr = Affine(375, 0, gx0, 0, -375, gy1)
    e = dict(width=w, height=h, transform=list(tr)[:6]); p = dict(crs='EPSG:5070', transform=tr)
    n = len(env.o1280_locations(e, p))
    t = pd.to_datetime(grp.UTC, utc=True); s, f = t.min().floor('h'), t.max().ceil('h')
    days = (f.floor('D') - s.floor('D')).days + 1
    rows.append(dict(incident=inc, h=h, w=w, nodes=n, start=s.isoformat(), end=f.isoformat(), days=days,
                     slim_calls=round(n * max(1, days / 14) * 1.0, 2)))
    if k % 50 == 0: print(k, inc, h, w, n, days, flush=True)
pd.DataFrame(rows).to_csv(out, index=False)
d = pd.DataFrame(rows)
print('incidents', len(d), 'cells', int((d.h * d.w).sum()), 'median grid', int((d.h * d.w).median()), 'nodes median', d.nodes.median(), 'max', d.nodes.max(),
      'days median', d.days.median(), 'max', d.days.max(), 'TOTAL slim calls', round(d.slim_calls.sum()))
print(d.sort_values('slim_calls').tail(5).to_string())
