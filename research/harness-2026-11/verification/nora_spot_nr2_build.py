"""Independent verifier: acceptance-8 spotting half on no_reentry/2, one start. Own clamp (Leo's dilate as the rule names
it), raster checks, then /2 + reopening builds from the v3.7 manifest kriged_mean h5 command with --arrival replaced.
argv: v37 worktree, region, start, out_dir, python"""
import json, sys, subprocess, hashlib, datetime as dt, numpy as np, rasterio
from pathlib import Path
W, region, start, OUT, PY = Path(sys.argv[1]), sys.argv[2], sys.argv[3], Path(sys.argv[4]), sys.argv[5]
FD = W / 'research/harness-2026-11/F-DYN'; sys.path.insert(0, str(FD))
from fdyn import variants
OUT.mkdir(parents=True, exist_ok=True)
with rasterio.open(FD / '_data/KFS_01_pswt_ok_toa.tif') as r:
    a = r.read(1).astype(float); nd = r.nodata
    t0 = dt.datetime.fromisoformat(r.tags()['t0_utc']).replace(tzinfo=dt.timezone.utc)
if nd is not None: a[a == nd] = np.nan
st = dt.datetime.strptime(start, '%Y%m%dT%H%M%SZ').replace(tzinfo=dt.timezone.utc)
h = (st - t0).total_seconds() / 3600
fin = np.isfinite(a); burned = fin & (a <= h)
info = {'h': h, 't0': t0.isoformat()}; prev = None
m = json.load(open(FD / 'MANIFEST_v3_7.json'))
ent = {e['transform']: e for e in m['entries'] if e['region'] == region and e['start'] == start and e['horizon_h'] == 5
       and e['variant'] == 'kriged_mean' and e['transform'] in ('no_reentry/2', 'reopening')}
for d in (0, 500, 1000, 2000):
    D = variants.dilate(a, d, 0.0)
    ad = a.copy()
    sel = ~burned & np.isfinite(D)                      # not burned at start (incl. NaN in a) with a finite dilation
    ad[sel] = np.maximum(D[sel], h); ad[~burned & ~np.isfinite(D)] = np.nan
    clamped = int((sel & (D < h)).sum())
    a_ms = np.where(np.isfinite(ad), np.round(ad * 3600000.0), np.inf); h_ms = round(h * 3600000.0)
    rec = {'clamped': clamped, 'finite': int(np.isfinite(ad).sum()), 'eq_h_ms': int((a_ms == h_ms).sum()),
           'lt_h_ms_not_burned': int(((a_ms < h_ms) & ~burned).sum()),
           'a0_equals_a': bool(np.array_equal(ad, a, equal_nan=True)) if d == 0 else None}
    if prev is not None:
        f1, f2 = np.isfinite(prev), np.isfinite(ad); rec['order_fail_vs_prev'] = int((f1 & ~f2).sum() + (f1 & f2 & (ad > prev)).sum())
    prev = ad
    p = OUT / f'a_d{d}.npz'; rec['npz_sha256'] = variants.save(p, ad, f'spot_clamped_{d}m', {'dilate_m': d, 'clamp_h': h})
    for tr, e in ent.items():
        cmd = list(e['cmd']); cmd[0] = PY
        cmd[cmd.index('--arrival') + 1] = str(p); cmd[cmd.index('--arrival-variant') + 1] = f'spot_clamped_{d}m'
        o = OUT / f"{'nr2' if tr == 'no_reentry/2' else 're'}_d{d}"; cmd[cmd.index('--out') + 1] = str(o)
        if not (o / 'HAZARD.json').exists():
            rr = subprocess.run(cmd, cwd=W, capture_output=True, text=True)
            rec[tr + '_rc'] = rr.returncode
            if rr.returncode: rec[tr + '_err'] = rr.stderr[-300:]
        if tr == 'no_reentry/2':
            pl = np.load(str(o) + '.plan.npz', allow_pickle=True)
            meta = json.loads(str(pl['meta'])) if 'meta' in pl.files else None
            nr2 = (meta or {}).get('no_reentry2', {})
            rec['c0_cells'] = nr2.get('c0_cells'); rec['b0_total'] = [x['b0_total'] for x in nr2.get('added_at_0', [])]
    info[d] = rec; print(d, json.dumps(rec), flush=True)
json.dump(info, open(OUT / 'info.json', 'w'), indent=1)
