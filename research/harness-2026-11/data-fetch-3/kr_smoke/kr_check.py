import sys, json, hashlib, numpy as np, rasterio
from pathlib import Path
env = Path(sys.argv[1]); ev = {e['id']: e for e in json.load(open(env/'events.json'))}
for k in ('KFS_02', 'KFS_03'):
    e = ev[k]; rec = ((e['height'], e['width']), tuple(round(x, 6) for x in e['transform']), e['epsg'])
    for f in ('terrain/slope_degrees_375m.tif', 'terrain/elevation_m_375m.tif', 'vegetation/tree_cover_percent_375m.tif', 'biome/biome_class_375m.tif'):
        p = env/'regions'/k/f
        if not p.exists():
            print(k, f, 'MISSING', sorted(x.name for x in p.parent.glob('*.tif'))[:12]); continue
        with rasterio.open(p) as r:
            a = r.read(1, masked=True); g = (r.shape, tuple(round(x, 6) for x in list(r.transform)[:6]), r.crs.to_epsg())
        v = a.compressed()
        print(k, f, 'grid_ok', g == rec, 'valid', v.size, '/', a.size, 'range %.2f..%.2f' % (v.min(), v.max()) if v.size else '', 'distinct', len(np.unique(v)) if 'biome' in f else '', hashlib.sha256(p.read_bytes()).hexdigest())
