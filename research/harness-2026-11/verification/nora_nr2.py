"""Nora: independent check of F-DYN no_reentry/2: C0 = export known-burned ∪ {variant arrival <= start} (own code);
/2 flame in every bin == C0 ∪ present ∪ {cells with /1 first flame <= l}; plus the readers."""
import json, sys, datetime as dt, numpy as np, rasterio
from pathlib import Path
W = Path(sys.argv[1]); F = W / 'research/harness-2026-11/F-DYN/_data'
R = Path('/home/user/wildfireguardian/data/routing/latest_inputs_try02/exports/KFS_01')
with rasterio.open(F / 'KFS_01_pswt_ok_toa.tif') as s:
    toa = s.read(1).astype(float); t0 = dt.datetime.fromisoformat(s.tags()['t0_utc']).replace(tzinfo=dt.timezone.utc)
def arrival(v):
    if v == 'kriged_mean': return toa
    if v == 'firms_early': return np.load(F / 'variants/firms_early.npz')['arrival_h']
    if v == 'envelope': return np.load(F / 'variants/firms_early.npz')['arrival_h']
def first_flame(hz):
    m = hz['members'][0]; fl = np.array(m['flame'], bool); bp = np.array(m['breakpoints'], float)
    first = np.full(fl.shape[1], np.inf)
    for i in range(fl.shape[0] - 1, -1, -1): first[fl[i]] = bp[i]
    return bp, fl, first
for region, start, synth in (('uiseong_andong_2025', '20250324T090000Z', False), ('yeongdeok_2025', '20250325T110000Z', True)):
    st = dt.datetime.strptime(start, '%Y%m%dT%H%M%SZ').replace(tzinfo=dt.timezone.utc)
    h_ms = int(round((st - t0).total_seconds() * 1000))
    exp = (F / 'synthetic_exports' if synth else R) / f'FORECAST_{start}.npz'
    z = np.load(exp); kb = z['source_burned_area_valid'] & (z['source_burned_area'] == 1)
    for v in ('kriged_mean', 'firms_early', 'envelope', 'envelope_burnset'):
        n1 = F / f'packets_v36_noreentry/{region}/{start}_h5_{v}_central_q300'
        if not n1.exists(): n1 = Path(sys.argv[2]) / f'packets_v36_noreentry/{region}/{start}_h5_{v}_central_q300'
        n2 = F / f'packets_v37_noreentry2/{region}/{start}_h5_{v}_central_q300'
        if not n2.exists(): continue
        h2 = json.loads((n2 / 'HAZARD.json').read_text()); bp2, fl2, f2 = first_flame(h2)
        Hh, Ww = h2['grid']['height'], h2['grid']['width']
        if v == 'envelope_burnset':
            c0 = kb.copy()
        else:
            a = arrival(v)
            a_ms = np.where(np.isfinite(a), np.round(a * 3600000.0), np.inf)
            c0 = kb | (a_ms <= h_ms)
        cur = np.load(n2 / 'constructed_arrays.npz')['current_active']
        flat = lambda m: np.flipud(m).ravel()
        C0 = flat(c0); PRES = flat(cur)
        line = f'{region[:2]} {v}: C0 {int(C0.sum())}, present {int(PRES.sum())}'
        if n1.exists():
            h1 = json.loads((n1 / 'HAZARD.json').read_text()); bp1, fl1, f1 = first_flame(h1)
            expect_first = np.where(C0 | PRES, 0.0, f1)
            mism = sum(int((fl2[i] != (expect_first <= bp2[i])).sum()) for i in range(fl2.shape[0]))
            leaves = sum(int((fl2[i] & ~fl2[i + 1]).sum()) for i in range(fl2.shape[0] - 1))
            B0 = (C0 | PRES) & ~(f1 == 0)   # closed at 0 under /2 but not at 0 under /1
            line += f'; B0 (added at 0 vs /1) {int(B0.sum())}; /2 flame vs C0∪present∪/1 mismatches {mism}; cells leaving flame {leaves}'
            line += f'; /1 cells born later that /2 moves to 0: {int(((C0) & (f1 > 0) & np.isfinite(f1)).sum())}'
        line += f'; /2 cells at 0 outside C0∪present: {int(((f2 == 0) & ~(C0 | PRES)).sum())}'
        print(line, flush=True)
