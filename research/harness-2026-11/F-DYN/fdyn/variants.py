"""Arrival-raster variants for F-DYN (all on the KFS_01 export grid, hours since t0 = 2025-03-22 02:24 UTC).

  kriged_mean        Choi 2026 TOA as published (Zenodo 10.5281/zenodo.21788344).
  firms_constrained  min(kriged TOA, first FIRMS detection in the cell): a detection proves fire by then (late bound),
                     so the cell can never arrive later than its first detection. Cells without a detection keep TOA.
  firms_early        BRACKET-START, NOT A LOWER BOUND (orchestrator/Iris correction 2026-11-12: non-detection is not
                     absence of fire; documented accounts fall before it). detected cells: the previous overpass (any of VIIRS S-NPP, NOAA-20, MODIS that recorded >= 1
                     detection in the grid) before the cell's first detection, i.e. the earliest arrival consistent
                     with a clear-sky non-detection; undetected cells: as firms_constrained. Clouds/smoke can hide fire
                     at that overpass, so the true arrival may be earlier still; this is a bracket under clear sky.
  dilate_<d>m_lag<L>s  isotropic spotting envelope: a_d(x) = min over cells y with centre distance <= d of a(y),
                     plus a lag L for cells that were moved earlier; cells inside the source footprint keep a(x) if it
                     is earlier. Proposed as the shared implementation for Richard/Priya (downwind stretching needs a
                     wind field; none is in the KFS_01 inputs).
Only cells with a finite kriged TOA (inside the final perimeter) can burn in any variant except dilation, which may
extend the footprint by d (that is its purpose). FIRMS detections outside the kriged footprint are counted, not used.

    python3 research/harness-2026-11/F-DYN/fdyn/variants.py --toa TOA.tif --firms-dir DIR --out-dir DIR
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

import numpy as np

T0 = dt.datetime(2025, 3, 22, 2, 24)
AFFINE = np.array([375.0, 0.0, 1085250.0, 0.0, -375.0, 1845375.0])
SHAPE = (79, 237)
FIRMS_FILES = ('viirs-snpp', 'viirs-jpss1', 'modis')


def load_firms(firms_dir: Path):
    import pandas as pd
    from pyproj import Transformer
    frames = []
    for f in FIRMS_FILES:
        d = pd.read_csv(firms_dir / f'{f}.csv')
        d['src'] = f
        frames.append(d)
    d = pd.concat(frames, ignore_index=True)
    d['t'] = pd.to_datetime(d.acq_date + ' ' + d.acq_time.astype(str).str.zfill(4), format='%Y-%m-%d %H%M')
    d = d[(d.t >= '2025-03-21') & (d.t < '2025-03-29')]
    x, y = Transformer.from_crs(4326, 5179, always_xy=True).transform(d.longitude.values, d.latitude.values)
    c = np.floor((x - AFFINE[2]) / AFFINE[0]).astype(int)
    r = np.floor((AFFINE[5] - y) / -AFFINE[4]).astype(int)
    ok = (r >= 0) & (r < SHAPE[0]) & (c >= 0) & (c < SHAPE[1])
    h = ((d.t - pd.Timestamp(T0)).dt.total_seconds() / 3600.0).values
    return r[ok], c[ok], h[ok], d.src.values[ok]


def firms_variants(toa: np.ndarray, r, c, h, src):
    first = np.full(SHAPE, np.inf)
    np.minimum.at(first, (r, c), h)
    passes = np.unique(h)                                  # overpass times with >= 1 detection in the grid
    det = np.isfinite(first)
    foot = np.isfinite(toa)
    constrained = np.where(det & foot, np.minimum(toa, first), toa)
    prev = np.full(SHAPE, np.nan)
    idx = np.searchsorted(passes, first[det], side='left') - 1          # last pass strictly before first detection
    pv = np.where(idx >= 0, passes[np.clip(idx, 0, None)], np.nan)
    prev[det] = pv
    early = constrained.copy()
    use = det & foot & np.isfinite(prev)
    early[use] = np.minimum(constrained[use], prev[use])
    stats = {'detections_in_grid': int(len(h)), 'overpasses_with_detections': int(len(passes)),
             'burned_cells': int(foot.sum()), 'burned_cells_with_detection': int((det & foot).sum()),
             'detected_cells_outside_kriged_footprint_not_used': int((det & ~foot).sum()),
             'first_detection_minus_kriged_h': {
                 'median': float(np.median((first - toa)[det & foot])),
                 'p10': float(np.percentile((first - toa)[det & foot], 10)),
                 'p90': float(np.percentile((first - toa)[det & foot], 90))},
             'cells_moved_earlier_constrained': int((constrained < toa).sum()),
             'cells_moved_earlier_early': int((early < toa).sum())}
    return constrained, early, stats


def dilate(a: np.ndarray, d_m: float, lag_s: float, cell: float = 375.0) -> np.ndarray:
    """Isotropic spotting envelope on cell centres: min over neighbours within d (inclusive) plus lag for moved cells."""
    k = int(np.floor(d_m / cell))
    out = a.copy()
    H, W = a.shape
    for dr in range(-k, k + 1):
        for dc in range(-k, k + 1):
            if (dr == 0 and dc == 0) or (dr * dr + dc * dc) * cell * cell > d_m * d_m + 1e-9:
                continue
            sh = np.full_like(a, np.inf)
            rs, re = max(0, dr), H + min(0, dr)
            cs, ce = max(0, dc), W + min(0, dc)
            src = a[rs - dr:re - dr, cs - dc:ce - dc]
            sh[rs:re, cs:ce] = np.where(np.isfinite(src), src + lag_s / 3600.0, np.inf)
            out = np.fmin(out, sh)
    out[~np.isfinite(out)] = np.nan
    return out


def save(path: Path, arr: np.ndarray, variant: str, provenance: dict, timestamp_exact=None):
    """timestamp_exact (v3.1, QUANT_v3_1_RULE.md): cells whose value is a FIRMS overpass time (whole minutes)."""
    extra = {} if timestamp_exact is None else {'timestamp_exact': np.asarray(timestamp_exact, bool)}
    np.savez_compressed(path, arrival_h=arr, affine_transform=AFFINE, t0_utc=T0.replace(tzinfo=dt.timezone.utc).isoformat(),
                        variant=variant, provenance=json.dumps(provenance), **extra)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    import rasterio
    ap = argparse.ArgumentParser()
    ap.add_argument('--toa', type=Path, required=True)
    ap.add_argument('--firms-dir', type=Path, required=True)
    ap.add_argument('--out-dir', type=Path, required=True)
    a = ap.parse_args()
    with rasterio.open(a.toa) as s:
        toa = s.read(1).astype(float)
    r, c, h, src = load_firms(a.firms_dir)
    constrained, early, stats = firms_variants(toa, r, c, h, src)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    firms_sha = {f: hashlib.sha256((a.firms_dir / f'{f}.csv').read_bytes()).hexdigest() for f in FIRMS_FILES}
    prov = {'soundness': {'firms_constrained': 'upper side is a fact (burning by first detection)',
                          'firms_early': 'BRACKET-START, NOT A LOWER BOUND'},
            'toa_sha256': hashlib.sha256(a.toa.read_bytes()).hexdigest(), 'firms_csv_sha256': firms_sha,
            'firms_source': 'NASA FIRMS standard processing (daniel/data-fetch small/firms)', 'stats': stats}
    out = {}
    foot = np.isfinite(toa)
    for name, arr in (('firms_constrained', constrained), ('firms_early', early)):
        exact = foot & np.isfinite(arr) & (arr != toa)            # value taken from a FIRMS overpass time
        out[name] = save(a.out_dir / f'{name}.npz', arr, name, prov, exact)
    print(json.dumps({'stats': stats, 'sha256': out}, indent=1))


if __name__ == '__main__':
    main()
