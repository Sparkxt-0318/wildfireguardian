#!/usr/bin/env python3
"""Cell-by-cell comparison of one region tree in the owner archive against a rebuilt tree (derived statistics only).

usage: cmp_region.py ARCHIVE_REGION_DIR REBUILD_REGION_DIR OUT.csv

For every *.tif under the archive region, the script looks for the same relative path in the rebuild. It reports:
  grid_equal       shape, band count and affine transform identical
  bytes_equal      file sha256 identical
  mask_equal       nodata / validity masks identical in every band
  cells_compared   cells valid in both (summed over bands)
  cells_differing  cells whose values are not exactly equal
  max/mean/median/p95_abs_diff   statistics of |archive - rebuild| over cells_compared
  verdict          'identical bytes', 'identical values (encoding differs)', 'float rounding (max |d| < 1e-4)' or 'VALUES DIFFER'
No raster values are written, only these statistics.
"""
import csv, hashlib, sys
from pathlib import Path
import numpy as np, rasterio

A, B, out = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rows = []
for pa in sorted(A.rglob('*.tif')):
    rel = pa.relative_to(A); pb = B / rel
    r = dict(raster=str(rel), archive_sha256=sha(pa))
    if not pb.exists():
        r['verdict'] = 'not in rebuild'; rows.append(r); continue
    r['rebuild_sha256'] = sha(pb); r['bytes_equal'] = r['archive_sha256'] == r['rebuild_sha256']
    with rasterio.open(pa) as ra, rasterio.open(pb) as rb:
        r['grid_equal'] = ra.shape == rb.shape and ra.count == rb.count and ra.transform == rb.transform
        r['bands'] = ra.count
        if not r['grid_equal']:
            r['verdict'] = 'GRID DIFFERS'; rows.append(r); continue
        a = ra.read(masked=True); b = rb.read(masked=True)
    ma, mb = np.ma.getmaskarray(a), np.ma.getmaskarray(b)
    both = ~ma & ~mb
    d = np.abs(a.data.astype('f8') - b.data.astype('f8'))[both]
    r.update(mask_equal=bool((ma == mb).all()), cells_valid_archive=int((~ma).sum()), cells_valid_rebuild=int((~mb).sum()),
             cells_compared=int(both.sum()), cells_differing=int((d != 0).sum()),
             max_abs_diff=float(d.max()) if d.size else 0.0, mean_abs_diff=float(d.mean()) if d.size else 0.0,
             median_abs_diff=float(np.median(d)) if d.size else 0.0, p95_abs_diff=float(np.percentile(d, 95)) if d.size else 0.0)
    r['verdict'] = ('identical bytes' if r['bytes_equal'] else
                    'identical values (encoding differs)' if r['mask_equal'] and r['cells_differing'] == 0 else
                    'float rounding (max |d| < 1e-4)' if r['mask_equal'] and r['max_abs_diff'] < 1e-4 else 'VALUES DIFFER')
    rows.append(r)
keys = ['raster', 'verdict', 'grid_equal', 'bands', 'bytes_equal', 'mask_equal', 'cells_valid_archive', 'cells_valid_rebuild',
        'cells_compared', 'cells_differing', 'max_abs_diff', 'mean_abs_diff', 'median_abs_diff', 'p95_abs_diff',
        'archive_sha256', 'rebuild_sha256']
with open(out, 'w', newline='') as f:
    w = csv.DictWriter(f, keys); w.writeheader(); w.writerows(rows)
from collections import Counter
print(Counter(r['verdict'] for r in rows))
