#!/usr/bin/env python3
"""Pack rebuilt static layers per event into one npz aligned to the event grid (forecast-v2 rectangle).

usage: pack_static_layers.py REGIONS_DIR OUT_DIR EVENT_ID [EVENT_ID ...] [--cases CASES_DIR]

Per event, OUT_DIR/<event>_static.npz holds 2-D arrays [height, width] on the Choi/forecast-v2 grid:
  fbfm40 (int16, LANDFIRE 2016 Remap FBFM40 code, mode-resampled), biome (int16, RESOLVE 2017 BIOME_NUM),
  slope_degrees, tree_cover_percent, elevation_m (float32), and one boolean *_valid per layer
  (not nodata and finite, the same rule as forecast/wildfire/data.py), all_static_valid (logical AND),
  plus transform, crs and shape. Weather is not included (see the Open-Meteo note).
With --cases, it checks that every stored forecast-v2 heldout case for the event has the same rectangle
and that its row/col indices fall inside the grid.
"""
import argparse, glob, json, os

import numpy as np
import rasterio

LAYERS = {
    'fbfm40': ('fuel/landfire_2016_fbfm40_375m.tif', 'int16'),
    'biome': ('biome/biome_class_375m.tif', 'int16'),
    'slope_degrees': ('terrain/slope_degrees_375m.tif', 'float32'),
    'tree_cover_percent': ('vegetation/tree_cover_percent_375m.tif', 'float32'),
    'elevation_m': ('terrain/elevation_m_375m.tif', 'float32'),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('regions'); ap.add_argument('out'); ap.add_argument('events', nargs='+')
    ap.add_argument('--cases')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for ev in a.events:
        d = os.path.join(a.regions, ev)
        with rasterio.open(os.path.join(d, 'arrival_time_hours.tif')) as g:
            shape, tr, crs = (g.height, g.width), g.transform, g.crs.to_string()
        arrays, report = {}, {}
        for name, (rel, dt) in LAYERS.items():
            p = os.path.join(d, rel)
            if not os.path.exists(p):
                report[name] = 'MISSING'; continue
            with rasterio.open(p) as s:
                assert (s.height, s.width) == shape and s.transform == tr, (ev, name)
                m = s.read(1, masked=True)
                valid = ~np.ma.getmaskarray(m) & np.isfinite(np.asarray(m.data, dtype='float64'))
                arrays[name] = m.filled(-9999).astype(dt)
                arrays[name + '_valid'] = valid
                report[name] = f'{int(valid.sum())}/{valid.size} valid'
        present = [k for k in LAYERS if k in arrays]
        arrays['all_static_valid'] = np.logical_and.reduce([arrays[k + '_valid'] for k in present])
        np.savez_compressed(os.path.join(a.out, f'{ev}_static.npz'), transform=np.array(list(tr)[:6]),
                            crs=np.array(crs), shape=np.array(shape), **arrays)
        line = f'{ev} grid {shape[0]}x{shape[1]} ' + ' '.join(f'{k}:{v}' for k, v in report.items())
        if a.cases:
            n = bad = 0
            for f in glob.glob(os.path.join(a.cases, '*.json')):
                c = json.load(open(f))
                if c['case']['event'] != ev: continue
                n += 1
                z = np.load(f[:-5] + '.npz')
                ok = tuple(c['rectangle']) == shape and z['row'].max() < shape[0] and z['col'].max() < shape[1]
                bad += not ok
            line += f' | heldout cases {n}, rectangle/index mismatches {bad}'
        print(line)


if __name__ == '__main__':
    main()
