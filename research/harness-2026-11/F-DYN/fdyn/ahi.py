"""Himawari-9 AHI fire detection for KFS_01: AHI_RULE.md @469796e + amendment 1 @def5016 (fixed before computing).

Outputs (out-dir):
  ahi_first_fire.npz    per pixel: t_f, t_lo (hours since t0), flags, parallax-corrected centre (EPSG:5179)
  ahi_membership.json   cell->pixel (nearest corrected centre) and pixel->cells (footprint + 1 km buffer disc, r=2 km)
  ahi_bounded.npz       F-DYN routing envelope (NOT for training): hi = min(firms hi, t_f(pixel)) for burned cells
  AHI_VALIDATION.json   V1 (by FRP class), V2, V3 (day/night), V4, V5; pass/fail by the pre-fixed criteria

    python3 research/harness-2026-11/F-DYN/fdyn/ahi.py --ahi-dir _data/ahi --firms-dir _data/firms \
        --surface ../F-C1/_data/surface_glo30_5179_30m.npz --toa _data/KFS_01_pswt_ok_toa.tif --out-dir _data/ahi_out
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'F-C1'))

from fdyn.variants import AFFINE, SHAPE  # noqa: E402

T0 = dt.datetime(2025, 3, 22, 2, 24)
BASELINE_FILES = ['kfs01_ahi_20250320T06_20250320T18.npz', 'kfs01_ahi_20250320T18_20250321T06.npz',
                  'kfs01_ahi_20250321T18_20250322T02.npz']
OBS_FILES = ['kfs01_ahi_20250324T06_20250324T18.npz', 'kfs01_ahi_20250324T18_20250325T18.npz']
D_DT, D_B07, SAT_K, CLOUD_B14 = 15.0, 10.0, 399.9, 265.0
SUB_LON, R_GEO, R_E = 140.7, 42164.0e3, 6378137.0
BUFFER_R_M = 2000.0
FRP_CLASSES = [(0, 10), (10, 50), (50, 1e9)]
DAY_UTC = [(dt.time(22, 0), dt.time(23, 59, 59)), (dt.time(0, 0), dt.time(9, 50))]   # 07:00-18:50 KST


def hours(ts):
    return (ts - np.datetime64(T0)).astype('timedelta64[s]').astype(float) / 3600.0


def load(path):
    z = np.load(path, allow_pickle=False)
    t = np.array(z['scan_start_utc'], dtype='datetime64[s]')
    return {k: z[k] for k in ('b07_K', 'b14_K', 'line', 'column', 'lat', 'lon')} | {'t': t}


def slot_of(t):
    s = (t - t.astype('datetime64[D]')).astype(int)            # seconds of day
    return np.round(s / 150.0).astype(int) % 576               # 2.5-min slots


def baseline(files):
    b07, dT, slot = [], [], []
    for f in files:
        d = load(f)
        b07.append(d['b07_K']); dT.append(d['b07_K'] - d['b14_K']); slot.append(slot_of(d['t']))
        clear = d['b14_K'] >= CLOUD_B14
        b07[-1] = np.where(clear, b07[-1], np.nan); dT[-1] = np.where(clear, dT[-1], np.nan)
    b07, dT, slot = np.vstack(b07), np.vstack(dT), np.concatenate(slot)
    npx = b07.shape[1]
    B07 = np.full((576, npx), np.nan); DT = np.full((576, npx), np.nan); N = np.zeros((576, npx), int)
    for s in np.unique(slot):
        m = slot == s
        B07[s] = np.nanmedian(b07[m], axis=0); DT[s] = np.nanmedian(dT[m], axis=0)
        N[s] = np.sum(np.isfinite(b07[m]), axis=0)
    return B07, DT, N


def detect(obs, B07, DT, N):
    b07, b14 = obs['b07_K'], obs['b14_K']
    s = slot_of(obs['t'])
    sat = b07 >= SAT_K
    cloud = (b14 < CLOUD_B14) & ~sat
    base_ok = np.isfinite(B07[s]) & np.isfinite(DT[s])
    fire = sat | (~cloud & base_ok & ((b07 - b14) - DT[s] >= D_DT) & (b07 - B07[s] >= D_B07))
    valid_nonfire = ~cloud & ~fire & base_ok
    nt, npx = fire.shape
    t_f = np.full(npx, np.nan); t_lo = np.full(npx, np.nan); weak = np.zeros(npx, bool); satf = np.zeros(npx, bool)
    th = hours(obs['t'])
    for p in range(npx):
        f = fire[:, p]
        for i in range(nt):
            if f[i] and (f[i + 1:i + 3].any()):
                t_f[p] = th[i]
                prev = np.flatnonzero(valid_nonfire[:i, p])
                t_lo[p] = th[prev[-1]] if prev.size else np.nan
                weak[p] = N[s[i], p] < 2
                satf[p] = bool(sat[i, p])
                break
    return t_f, t_lo, weak, satf, fire, cloud, th


def parallax_corrected(lat, lon, surface):
    """Move each pixel centre toward the sub-satellite point by z * tan(VZA) (terrain only)."""
    from pyproj import Geod, Transformer
    geod = Geod(ellps='WGS84')
    to5179 = Transformer.from_crs(4326, 5179, always_xy=True)
    x, y = to5179.transform(lon, lat)
    z = surface.sample(x, y)
    la, lo_ = np.radians(lat), np.radians(lon)
    p = np.stack([R_E * np.cos(la) * np.cos(lo_), R_E * np.cos(la) * np.sin(lo_), R_E * np.sin(la)], 1)
    s = np.array([R_GEO * math.cos(math.radians(SUB_LON)), R_GEO * math.sin(math.radians(SUB_LON)), 0.0])
    v = s - p
    up = p / np.linalg.norm(p, axis=1, keepdims=True)
    vza = np.arccos(np.sum(v * up, 1) / np.linalg.norm(v, axis=1))
    az, _, _ = geod.inv(lon, lat, np.full_like(lon, SUB_LON), np.zeros_like(lat))
    shift = np.nan_to_num(z) * np.tan(vza)
    lon2, lat2, _ = geod.fwd(lon, lat, az, shift)
    x2, y2 = to5179.transform(lon2, lat2)
    return np.column_stack([x2, y2]), np.degrees(vza), shift


def load_firms_frp(firms_dir):
    import pandas as pd
    from pyproj import Transformer
    fr = []
    for f in ('viirs-snpp', 'viirs-jpss1', 'modis'):
        d = pd.read_csv(firms_dir / f'{f}.csv'); d['src'] = f; fr.append(d)
    d = pd.concat(fr, ignore_index=True)
    d['t'] = pd.to_datetime(d.acq_date + ' ' + d.acq_time.astype(str).str.zfill(4), format='%Y-%m-%d %H%M')
    d = d[(d.t >= '2025-03-21') & (d.t < '2025-03-29')]
    x, y = Transformer.from_crs(4326, 5179, always_xy=True).transform(d.longitude.values, d.latitude.values)
    h = ((d.t - pd.Timestamp(T0)).dt.total_seconds() / 3600.0).values
    return np.column_stack([x, y]), h, d.frp.values.astype(float)


def is_day(th):
    t = [(T0 + dt.timedelta(hours=float(v))).time() for v in th]
    return np.array([any(a <= x <= b for a, b in DAY_UTC) for x in t])


def main():
    from scipy.spatial import cKDTree
    import rasterio
    from seebefore import dem
    ap = argparse.ArgumentParser()
    ap.add_argument('--ahi-dir', type=Path, required=True)
    ap.add_argument('--firms-dir', type=Path, required=True)
    ap.add_argument('--surface', type=Path, required=True)
    ap.add_argument('--toa', type=Path, required=True)
    ap.add_argument('--firms-constrained', type=Path, required=True)
    ap.add_argument('--firms-early', type=Path, required=True)
    ap.add_argument('--out-dir', type=Path, required=True)
    a = ap.parse_args()
    a.out_dir.mkdir(parents=True, exist_ok=True)
    B07, DT, N = baseline([a.ahi_dir / f for f in BASELINE_FILES])
    obs = [load(a.ahi_dir / f) for f in OBS_FILES]
    for o in obs[1:]:
        if not (np.array_equal(o['line'], obs[0]['line']) and np.array_equal(o['column'], obs[0]['column'])):
            raise SystemExit('PIXEL_ORDER_MISMATCH')
    ob = {k: np.vstack([o[k] for o in obs]) for k in ('b07_K', 'b14_K')} | {'t': np.concatenate([o['t'] for o in obs])}
    t_f, t_lo, weak, satf, fire, cloud, th = detect(ob, B07, DT, N)
    surface, _ = dem.load(a.surface)
    cen, vza, shift = parallax_corrected(obs[0]['lat'], obs[0]['lon'], surface)
    npx = len(t_f)
    # membership
    rr, cc = np.nonzero(np.ones(SHAPE, bool))
    cells = np.column_stack([AFFINE[2] + (cc + 0.5) * AFFINE[0], AFFINE[5] + (rr + 0.5) * AFFINE[4]])
    tree = cKDTree(cen)
    _, nearest = tree.query(cells)
    buffered = [sorted(map(int, ix)) for ix in cKDTree(cells).query_ball_point(cen, BUFFER_R_M)]
    np.savez_compressed(a.out_dir / 'ahi_first_fire.npz', t_f_h=t_f, t_lo_h=t_lo, weak_baseline=weak,
                        saturated_at_tf=satf, centre_5179=cen, vza_deg=vza, parallax_shift_m=shift,
                        line=obs[0]['line'], column=obs[0]['column'], t0_utc=T0.isoformat() + 'Z')
    (a.out_dir / 'ahi_membership.json').write_text(json.dumps({
        'cell_index': 'flat row-major north-up index into the 79x237 KFS_01 grid',
        'cell_to_pixel_nearest': nearest.astype(int).tolist(),
        'pixel_to_cells_buffered_r_m': BUFFER_R_M, 'pixel_to_cells_buffered': buffered}))
    # routing envelope
    hi_c = np.load(a.firms_constrained)['arrival_h']; lo_e = np.load(a.firms_early)['arrival_h']
    tf_cell = t_f[nearest].reshape(SHAPE); tlo_cell = t_lo[nearest].reshape(SHAPE)
    burned = np.isfinite(hi_c)
    hi_b = np.where(burned & np.isfinite(tf_cell), np.fmin(hi_c, tf_cell), hi_c)
    lo_b = np.where(burned & np.isfinite(tf_cell), np.fmin(lo_e, np.where(np.isfinite(tlo_cell), tlo_cell, tf_cell)), lo_e)
    lo_b = np.fmin(lo_b, hi_b)
    for name, arr in (('ahi_bounded_hi', hi_b), ('ahi_bounded_lo', lo_b)):
        np.savez_compressed(a.out_dir / f'{name}.npz', arrival_h=arr, affine_transform=AFFINE,
                            t0_utc=T0.replace(tzinfo=dt.timezone.utc).isoformat(), variant=name,
                            provenance=json.dumps({'label': 'ROUTING ENVELOPE, NOT FOR TRAINING (AHI_RULE.md amendment 1)'}))
    # validation
    pxy, ph, pfrp = load_firms_frp(a.firms_dir)
    win = (ph >= th[0]) & (ph <= th[-1])
    _, ppix = tree.query(pxy)
    v1 = {}
    for lo_frp, hi_frp in FRP_CLASSES:
        rows = []
        for p in range(npx):
            m = win & (ppix == p)
            if not m.any():
                continue
            k = np.argmin(np.where(m, ph, np.inf))
            if not (lo_frp <= pfrp[k] < hi_frp):
                continue
            tp = ph[k]
            tf = t_f[p]
            rows.append((tp, tf))
        n = len(rows)
        caught = sum(1 for tp, tf in rows if np.isfinite(tf) and tf <= tp + 10 / 60)
        earlier = [tp - tf for tp, tf in rows if np.isfinite(tf) and tf < tp]
        missed = sum(1 for tp, tf in rows if not np.isfinite(tf))
        v1[f'frp_{lo_frp}_{int(min(hi_frp, 1e4))}'] = {
            'pixels': n, 'caught_in_time': caught, 'caught_share': caught / n if n else None,
            'earlier': len(earlier), 'earlier_h_median': float(np.median(earlier)) if earlier else None,
            'earlier_h_iqr': [float(np.percentile(earlier, 25)), float(np.percentile(earlier, 75))] if earlier else None,
            'missed': missed}
    # V2: rule applied to the baseline windows themselves
    base = [load(a.ahi_dir / f) for f in BASELINE_FILES]
    bo = {k: np.vstack([o[k] for o in base]) for k in ('b07_K', 'b14_K')} | {'t': np.concatenate([o['t'] for o in base])}
    _, _, _, _, bfire, _, _ = detect(bo, B07, DT, N)
    # V3: pixels with no polar detection within 5 km at any time 22-28 Mar
    allp = cKDTree(pxy)
    far = np.array([len(allp.query_ball_point(cen[p], 5000.0)) == 0 for p in range(npx)])
    day = is_day(th)
    hour_idx = np.floor(th).astype(int)

    def pixel_hour_share(mask_px, rows_mask):
        f = fire[rows_mask][:, mask_px]
        hi_ = hour_idx[rows_mask]
        tot = flag = 0
        for h in np.unique(hi_):
            blk = f[hi_ == h]
            tot += blk.shape[1]
            flag += int(blk.any(axis=0).sum())
        return {'pixel_hours': tot, 'flagged': flag, 'share': flag / tot if tot else None}
    v3 = {'far_pixels': int(far.sum()), 'all': pixel_hour_share(far, np.ones_like(day)),
          'day': pixel_hour_share(far, day), 'night': pixel_hour_share(far, ~day)}
    # V5: neighbours (line/column +-1) of firing pixels without polar detection in their own buffered footprint, 24-26 Mar
    line, col = obs[0]['line'], obs[0]['column']
    pos = {(int(l), int(c)): i for i, (l, c) in enumerate(zip(line, col))}
    firing = np.isfinite(t_f)
    w2426 = (ph >= hours(np.datetime64('2025-03-24'))) & (ph < hours(np.datetime64('2025-03-27')))
    poltree = cKDTree(pxy[w2426]) if w2426.any() else None
    cand = set()
    for p in np.flatnonzero(firing):
        for dl in (-1, 0, 1):
            for dc in (-1, 0, 1):
                q = pos.get((int(line[p]) + dl, int(col[p]) + dc))
                if q is not None and q != p:
                    cand.add(q)
    cand = [q for q in cand if poltree is None or len(poltree.query_ball_point(cen[q], BUFFER_R_M)) == 0]
    v5 = {'neighbour_pixels_without_polar': len(cand), 'flagged': int(firing[cand].sum()) if cand else 0}
    # V4: hourly counts
    v4 = {}
    for h in np.unique(hour_idx):
        lab = (T0 + dt.timedelta(hours=int(h))).strftime('%m-%d %H:00 UTC')
        v4[lab] = int(fire[hour_idx == h].any(axis=0).sum())
    hi50 = v1['frp_50_10000']
    passed = (hi50['caught_share'] is not None and hi50['caught_share'] >= 0.80 and
              v3['all']['share'] is not None and v3['all']['share'] <= 0.02)
    res = {'rule': 'AHI_RULE.md @469796e + amendment 1 @def5016', 'pixels': npx, 'firing_pixels': int(firing.sum()),
           'weak_baseline_firing': int((weak & firing).sum()), 'saturated_at_tf': int((satf & firing).sum()),
           'parallax_shift_m': {'median': float(np.median(shift)), 'max': float(np.max(shift))},
           'V1_by_frp_class': v1, 'V2_preignition_flagged_scans': int(bfire.sum()),
           'V2_preignition_pixel_scans': int(bfire.size), 'V3_far_false_alarm': v3, 'V4_hourly_firing_pixels': v4,
           'V5_psf_bleed': v5,
           'PASS': bool(passed), 'criteria': 'V1 caught_share(FRP>=50) >= 0.80 AND V3 all share <= 0.02',
           'inputs_sha256': {f: hashlib.sha256((a.ahi_dir / f).read_bytes()).hexdigest()
                             for f in BASELINE_FILES + OBS_FILES}}
    (a.out_dir / 'AHI_VALIDATION.json').write_text(json.dumps(res, indent=1))
    print(json.dumps({k: res[k] for k in ('firing_pixels', 'V1_by_frp_class', 'V2_preignition_flagged_scans',
                                           'V3_far_false_alarm', 'V5_psf_bleed', 'PASS')}, indent=1))


if __name__ == '__main__':
    main()
