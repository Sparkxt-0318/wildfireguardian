"""Nora: independent F-DYN checks (D1 thresholding, D2 plan==flame, crop, dose)."""
import json, datetime as dt, numpy as np, rasterio, sys
from pathlib import Path
S = Path('/tmp/claude-0/-home-user-wildfireguardian/9b9ef843-00d9-5e9a-94ab-328b695155e8/scratchpad')
R = Path('/home/user/wildfireguardian/data/routing'); I = R/'latest_inputs_try02'
with rasterio.open(S/'zen/x/rasters_kr/KFS_01_pswt_ok_toa.tif') as s:
    toa = s.read(1).astype(float); tr = s.transform; t0 = dt.datetime.fromisoformat(s.tags()['t0_utc']).replace(tzinfo=dt.timezone.utc)
    print('raster', toa.shape, tr, 't0', t0, 'crs', s.crs)
starts = sorted(p.name[9:-4] for p in (I/'exports'/'KFS_01').glob('FORECAST_*.npz'))
for st in starts:
    z = np.load(I/'exports'/'KFS_01'/f'FORECAST_{st}.npz')
    a = z['affine_transform']; assert tuple(a) == (tr.a, tr.b, tr.c, tr.d, tr.e, tr.f), (a, tr)
    h = (dt.datetime.strptime(st,'%Y%m%dT%H%M%SZ').replace(tzinfo=dt.timezone.utc)-t0).total_seconds()/3600
    T = float(z['contract__cell_duration_s'])/3600
    fin = np.isfinite(toa)
    act = z['heat__initial_active_burning_probability'] > 0
    bur = z['source_burned_area_valid'] & (z['source_burned_area']==1)
    mism_valid = int((z['source_burned_area_valid'] != fin).sum())
    mism_b = int((bur != (fin & (toa<=h))).sum()); mism_a = int((act != (fin & (toa<=h) & (toa>h-T))).sum())
    # margin: how close is TOA to the thresholds (sensitivity to float/t0 rounding)
    d = np.abs(np.concatenate([(toa-h)[fin], (toa-(h-T))[fin]]))
    print(f'{st}: h={h:.4f} T={T:.4f}h active {int(act.sum())} mismatches valid/burned/active {mism_valid}/{mism_b}/{mism_a} min|toa-threshold| {d.min()*3600:.1f}s')
# ---- D2 and crop on the built packet
pk = S/'wt/dyn/research/harness-2026-11/F-DYN/_data/packets/yeongdeok_2025/20250325T230000Z_h5'
st = '20250325T230000Z'; H = 18000.0
h = (dt.datetime.strptime(st,'%Y%m%dT%H%M%SZ').replace(tzinfo=dt.timezone.utc)-t0).total_seconds()/3600
rule = [(1.0,0.0),(0.75,0.0),(0.5,0.0),(1.0,3600.0)]
plan = []
for s_, sh in rule:
    t = s_*(toa-h)*3600 - sh
    t = np.floor(np.maximum(t,0)/300)*300
    ok = np.isfinite(toa) & (toa > h) & (t < H)
    plan.append(np.where(ok, t, np.inf))
md = json.loads((R/'latest_inputs_try02'/'packets'/'yeongdeok_2025'/st/'NATIVE_METADATA.json').read_text())
w = md['regional']['window_rows_cols_north_up']; print('window', w)
inwin = np.zeros_like(toa, bool); inwin[w['r0']:w['r1']+1, w['c0']:w['c1']+1] = True
hz = json.loads((pk/'HAZARD.json').read_text()); G = hz['grid']; Wd, Ht = G['width'], G['height']
print('valid_until', hz['valid_until'], 'grid', G, 'members', [m['id'] for m in hz['members']])
nonflame = 0.0
for k, m in enumerate(hz['members']):
    bp = m['breakpoints']; fl = np.array(m['flame'], bool); fx = np.array(m['flux'], float)
    nonflame = max(nonflame, fx[~fl].max())
    first = {}
    for i in range(fl.shape[0]):
        for c in np.flatnonzero(fl[i]):
            if c not in first: first[c] = bp[i]
    pres = set(np.flatnonzero(fl[0])) if bp[0]==0 else set()
    written = {}
    for c, t in first.items():
        pr, pc = divmod(c, Wd); er, ec = w['r1'] - pr, w['c0'] + pc
        written[(er, ec)] = t
    planned = {(r, c): plan[k][r, c] for r, c in zip(*np.nonzero(np.isfinite(plan[k]) & inwin))}
    # present cells at t=0 have first=0; planned ignitions at 0 also first=0 -> compare non-present
    act0 = np.load(I/'exports'/'KFS_01'/f'FORECAST_{st}.npz')['heat__initial_active_burning_probability'] > 0
    wr_new = {rc: t for rc, t in written.items() if not act0[rc]}
    diff = set(wr_new.items()) ^ set(planned.items())
    out_ign = int((np.isfinite(plan[k]) & ~inwin).sum())
    print(f'member {k}: planned in-window {len(planned)} written new {len(wr_new)} symmetric diff {len(diff)} | outside-window ignitions {out_ign} | max flux {fx.max():.4f}')
print('max non-flame flux', nonflame, 'x 18000 s =', nonflame*18000, 'kJ/m2 (limit 100)')
act0 = np.load(I/'exports'/'KFS_01'/f'FORECAST_{st}.npz')['heat__initial_active_burning_probability'] > 0
print('present fire outside window', int((act0 & ~inwin).sum()), 'of', int(act0.sum()))
