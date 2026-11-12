"""Confirmed-clear views and the envelope_sound variant (SOUND_ENVELOPE_RULE.md @c79c510, fixed before computing).

    python3 research/harness-2026-11/F-DYN/fdyn/sound.py --data research/harness-2026-11/F-DYN/_data \
        --ahi-results research/harness-2026-11/F-DYN/ahi_results --out-dir research/harness-2026-11/F-DYN/_data/variants
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from fdyn.ahi import OBS_FILES, hours, load, load_firms_frp  # noqa: E402
from fdyn.variants import AFFINE, SHAPE  # noqa: E402

T0 = dt.datetime(2025, 3, 22, 2, 24)
NEAR_M = 750.0
SCAN_TOL_H = 2.5 / 60
HI_BEYOND_H = 1.0e6       # "still burning at the horizon end": hi far beyond any horizon


def main():
    import pandas as pd
    import rasterio
    from scipy.spatial import cKDTree
    from pyproj import Transformer
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', type=Path, required=True)
    ap.add_argument('--ahi-results', type=Path, required=True)
    ap.add_argument('--out-dir', type=Path, required=True)
    a = ap.parse_args()
    D = a.data
    with rasterio.open(D / 'KFS_01_pswt_ok_toa.tif') as s:
        toa = s.read(1).astype(float)
    # FIRMS with instrument per detection
    fr = []
    for f in ('viirs-snpp', 'viirs-jpss1', 'modis'):
        d = pd.read_csv(D / 'firms' / f'{f}.csv'); d['src'] = f; fr.append(d)
    d = pd.concat(fr, ignore_index=True)
    d['t'] = pd.to_datetime(d.acq_date + ' ' + d.acq_time.astype(str).str.zfill(4), format='%Y-%m-%d %H%M')
    d = d[(d.t >= '2025-03-21') & (d.t < '2025-03-29')]
    x, y = Transformer.from_crs(4326, 5179, always_xy=True).transform(d.longitude.values, d.latitude.values)
    dh = ((d.t - pd.Timestamp(T0)).dt.total_seconds() / 3600.0).values
    src = d.src.values
    dxy = np.column_stack([x, y])
    c = np.floor((x - AFFINE[2]) / AFFINE[0]).astype(int)
    r = np.floor((AFFINE[5] - y) / -AFFINE[4]).astype(int)
    ok = (r >= 0) & (r < SHAPE[0]) & (c >= 0) & (c < SHAPE[1])
    first = np.full(SHAPE, np.inf)
    np.minimum.at(first, (r[ok], c[ok]), dh[ok])
    viirs_passes = np.unique(dh[np.isin(src, ['viirs-snpp', 'viirs-jpss1'])])
    # AHI cloud test per (pixel, scan)
    obs = [load(D / 'ahi' / f) for f in OBS_FILES]
    th = np.concatenate([hours(o['t']) for o in obs])
    b07 = np.vstack([o['b07_K'] for o in obs]); b14 = np.vstack([o['b14_K'] for o in obs])
    clear_px = (b14 >= 265.0) & (b07 < 399.9)
    line, col = obs[0]['line'], obs[0]['column']
    pos = {(int(l), int(cc)): i for i, (l, cc) in enumerate(zip(line, col))}
    neigh = [[pos[(int(line[p]) + i, int(col[p]) + j)] for i in (-1, 0, 1) for j in (-1, 0, 1)
              if (int(line[p]) + i, int(col[p]) + j) in pos] for p in range(len(line))]
    clear_nb = np.stack([clear_px[:, nb].all(axis=1) for nb in neigh], axis=1)      # [scan, pixel]
    memb = json.loads((a.ahi_results / 'ahi_membership.json').read_text())
    cell_pix = np.array(memb['cell_to_pixel_nearest']).reshape(SHAPE)
    ahi = np.load(a.ahi_results / 'ahi_first_fire.npz')
    firing = np.isfinite(ahi['t_f_h'])
    ahi_cells = np.zeros(SHAPE[0] * SHAPE[1], bool)
    for p in np.flatnonzero(firing):
        ahi_cells[memb['pixel_to_cells_buffered'][p]] = True
    ahi_cells = ahi_cells.reshape(SHAPE)
    detected = np.isfinite(first)
    burn_set = np.isfinite(toa) | detected | ahi_cells
    # per VIIRS pass: is it inside AHI coverage, nearest scan, and which cells have a detection within 750 m
    rr, cc = np.nonzero(np.ones(SHAPE, bool))
    cells = np.column_stack([AFFINE[2] + (cc + 0.5) * AFFINE[0], AFFINE[5] + (rr + 0.5) * AFFINE[4]])
    lo_sound = np.zeros(SHAPE)                     # default: ignition time (0 h since t0)
    has_clear = np.zeros(SHAPE, bool)
    prev_clear = np.zeros(SHAPE, bool)              # detected cells: was the LATEST VIIRS pass before first det clear?
    latest_prev = np.full(SHAPE, np.nan)
    det_cells = np.flatnonzero(detected.ravel())
    for tp in viirs_passes:
        lp = np.flatnonzero(detected.ravel() & (first.ravel() > tp))
        latest_prev.ravel()[lp] = np.fmax(latest_prev.ravel()[lp], tp)
    for tp in viirs_passes:
        k = np.argmin(np.abs(th - tp))
        if abs(th[k] - tp) > SCAN_TOL_H:
            continue                                # outside AHI coverage: never confirmed clear
        m = np.isclose(dh, tp)
        tree = cKDTree(dxy[m]) if m.any() else None
        near = np.zeros(len(cells), bool)
        if tree is not None:
            near[[i for i, l in enumerate(tree.query_ball_point(cells, NEAR_M)) if l]] = True
        clear_cell = clear_nb[k][cell_pix.ravel()] & ~near
        eligible = burn_set.ravel() & clear_cell & (first.ravel() > tp)       # before the cell's first detection
        flat = lo_sound.ravel()
        flat[eligible] = np.maximum(flat[eligible], tp)
        has_clear.ravel()[eligible] = True
        isprev = np.isclose(latest_prev.ravel(), tp) & clear_cell
        prev_clear.ravel()[isprev] = True
    lo_sound = np.where(burn_set, lo_sound, np.nan)
    hi = np.where(burn_set, HI_BEYOND_H, np.nan)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    prov = {'rule': 'SOUND_ENVELOPE_RULE.md @c79c510', 'label': 'envelope_sound: conservative routing envelope; '
            'burning from last confirmed-clear VIIRS view (else ignition) to beyond the horizon'}
    for name, arr in (('envelope_sound_lo', lo_sound), ('envelope_sound_hi', hi)):
        np.savez_compressed(a.out_dir / f'{name}.npz', arrival_h=arr, affine_transform=AFFINE,
                            t0_utc=T0.replace(tzinfo=dt.timezone.utc).isoformat(), variant=name,
                            provenance=json.dumps(prov))
    counts = {'burn_set_cells': int(burn_set.sum()), 'of_which_kriged_footprint': int(np.isfinite(toa).sum()),
              'of_which_only_via_ahi_buffer': int((ahi_cells & ~np.isfinite(toa) & ~detected).sum()),
              'detected_cells': int(detected.sum()),
              'detected_with_latest_previous_viirs_pass_confirmed_clear': int(prev_clear[detected].sum()),
              'burn_set_with_any_confirmed_clear_view': int(has_clear.sum()),
              'burn_set_lo_at_ignition': int((burn_set & ~has_clear).sum()),
              'viirs_passes_with_detections': int(len(viirs_passes)),
              'viirs_passes_inside_ahi_coverage': int(sum(np.min(np.abs(th - t)) <= SCAN_TOL_H for t in viirs_passes)),
              'untestable': ['thick smoke', 'warm low cloud', 'sub-threshold fire', 'day/night sensitivity']}
    (a.out_dir / 'envelope_sound_counts.json').write_text(json.dumps(counts, indent=1))
    print(json.dumps(counts, indent=1))


if __name__ == '__main__':
    main()
