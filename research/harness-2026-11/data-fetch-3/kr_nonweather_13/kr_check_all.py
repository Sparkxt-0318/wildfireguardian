import sys, json, hashlib, numpy as np, rasterio
from pathlib import Path
env = Path(sys.argv[1]); ev = json.load(open(env/'events.json'))
F = ('terrain/slope_degrees_375m.tif', 'terrain/elevation_m_375m.tif', 'vegetation/tree_cover_percent_375m.tif', 'biome/biome_class_375m.tif')
for e in ev:
    k = e['id']; rec = ((e['height'], e['width']), tuple(round(x, 6) for x in e['transform']), e['epsg'])
    out = [k, f"{e['height']}x{e['width']}"]; ok = True
    for f in F:
        p = env/'regions'/k/f
        with rasterio.open(p) as r:
            a = r.read(1, masked=True); g = (r.shape, tuple(round(x, 6) for x in list(r.transform)[:6]), r.crs.to_epsg())
        ok &= g == rec; v = a.compressed()
        tag = f.split('/')[1].split('_')[0]
        out.append(f"{tag}={v.size}" + (f"[{','.join(map(str, np.unique(v).astype(int)))}]" if 'biome' in f else '') + f":{hashlib.sha256(p.read_bytes()).hexdigest()[:8]}")
    m = json.load(open(env/'regions'/k/'biome/biome_metadata.json'))
    out += [f"grid_ok={ok}", f"arrival_valid={m['valid_arrival_pixels']}", f"arrival_no_biome={m['biome_missing_arrival_pixels']}"]
    print(' '.join(out))
