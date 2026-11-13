#!/usr/bin/env python3
"""Independent archive-vs-rebuild check of one region tree (Hannah, verifier). Read-only, no network.
Written independently of data-fetch-3/archive_vs_rebuild/cmp_region.py.

Run UNMODIFIED where both trees are:
    python3 -I region_check.py ARCHIVE_REGION_DIR REBUILD_REGION_DIR > region_check_out.json

For every *.tif in EITHER tree it prints: presence on each side, sha256, same-file-on-disk, dtype, nodata, crs (WKT sha),
transform, shape, band count, and, if both exist on the same grid, per band: validity-mask equality (nodata and NaN
handled explicitly), cells valid in both, cells differing, and max |difference|. No raster values are printed.
"""
import hashlib, json, os, sys
from pathlib import Path
import numpy as np
import rasterio


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def meta(p):
    with rasterio.open(p) as r:
        return dict(dtype=list(r.dtypes), nodata=None if r.nodata is None else float(r.nodata),
                    crs_wkt_sha=hashlib.sha256((r.crs.to_wkt() if r.crs else '').encode()).hexdigest()[:16],
                    transform=[round(x, 9) for x in tuple(r.transform)[:6]], shape=[r.height, r.width], count=r.count)


def valid(arr, nodata):
    v = np.ones(arr.shape, bool)
    if np.issubdtype(arr.dtype, np.floating):
        v &= ~np.isnan(arr)
    if nodata is not None and not (isinstance(nodata, float) and np.isnan(nodata)):
        v &= arr != nodata
    return v


def main():
    A, B = Path(sys.argv[1]), Path(sys.argv[2])
    rels = sorted({p.relative_to(A).as_posix() for p in A.rglob('*.tif')} | {p.relative_to(B).as_posix() for p in B.rglob('*.tif')})
    out = {'script': 'region_check.py (Hannah)', 'n_union': len(rels), 'files': {}}
    for rel in rels:
        pa, pb = A / rel, B / rel
        e = {'in_archive': pa.is_file(), 'in_rebuild': pb.is_file()}
        if e['in_archive']:
            e['archive_sha256'] = sha(pa); e['archive_meta'] = meta(pa)
        if e['in_rebuild']:
            e['rebuild_sha256'] = sha(pb); e['rebuild_meta'] = meta(pb)
        if e['in_archive'] and e['in_rebuild']:
            e['same_file_on_disk'] = os.path.samefile(pa, pb)
            e['bytes_equal'] = e['archive_sha256'] == e['rebuild_sha256']
            ma, mb = e['archive_meta'], e['rebuild_meta']
            e['grid_equal'] = ma['shape'] == mb['shape'] and ma['count'] == mb['count'] and ma['transform'] == mb['transform'] \
                and ma['crs_wkt_sha'] == mb['crs_wkt_sha']
            if e['grid_equal']:
                bands = []
                with rasterio.open(pa) as ra, rasterio.open(pb) as rb:
                    for i in range(1, ma['count'] + 1):
                        a = ra.read(i); b = rb.read(i)
                        va, vb = valid(a, ra.nodata), valid(b, rb.nodata)
                        both = va & vb
                        d = np.abs(a.astype('f8')[both] - b.astype('f8')[both])
                        bands.append(dict(mask_equal=bool((va == vb).all()), valid_a=int(va.sum()), valid_b=int(vb.sum()),
                                          both=int(both.sum()), differing=int((d != 0).sum()),
                                          max_abs=float(d.max()) if d.size else 0.0))
                e['bands'] = bands
        out['files'][rel] = e
    json.dump(out, sys.stdout, indent=1, sort_keys=True)
    print()


if __name__ == '__main__':
    main()
