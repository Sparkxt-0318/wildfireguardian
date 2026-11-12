"""F-C1b: see-before-leave intervals (DEFINITION_C1b.md @ dae181e + amendment 1 @ a285c67).

Documented observer points (6 villages, case studies) and all 174 planner places (unselected set, observer = OSM
place point).

    python3 seebefore/c1b.py --surface _data/surface_glo30_5179_30m.npz --toa TOA.tif --firms-dir DIR --out C1B.json
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
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / 'research' / 'harness-2026-11' / 'F-DYN'))

from seebefore import dem, extract  # noqa: E402
from seebefore.compute import VARIANTS, place_hreq  # noqa: E402
from fdyn.variants import AFFINE, SHAPE, load_firms  # noqa: E402

T0 = dt.datetime(2025, 3, 22, 2, 24, tzinfo=dt.timezone.utc)
KST = dt.timezone(dt.timedelta(hours=9))
SUNSET_H = (dt.datetime(2025, 3, 25, 18, 50, tzinfo=KST) - T0).total_seconds() / 3600   # 09:50 UTC
FOOTPRINT_M = 500.0
FOOTPRINT_SENS_M = (250.0, 1000.0)
V1_SMOKE_TEST_KST = dt.datetime(2025, 3, 25, 16, 30, tzinfo=KST)
SETTINGS = {'optimistic': {'row': 'best9_eye2', 'flame': 10.0, 'smoke': 1000.0, 'cap_m': None},
            'pessimistic': {'row': 'centre_eye2_cellcentre', 'flame': 2.0, 'smoke': 300.0, 'cap_m': 15000.0}}
OBSERVERS = [   # (village, label, lat, lon, anchors) -- DEFINITION_C1b.md table, verbatim coordinates
    ('V1', '지품면사무소', 36.4484609, 129.2818195,
     'smoke from N ~16:30 KST seen by 면장 (VERIFIED); 18:00 order; 20:25 power cut (VERIFIED)'),
    ('V2', '매정1리마을회관', 36.4449605, 129.4209802, '이장 ~20:00; arrival ~20:40; car burned ~21:00 (VERIFIED)'),
    ('V2', '매정2리마을회관', 36.4550118, 129.4069928, 'as V2'),
    ('V2', '매정3리마을회관', 36.4521412, 129.4219661, 'as V2'),
    ('V3', '경정1리마을회관', 36.484571, 129.4350371, 'flames over ridge ~20:00 (SNIPPET)'),
    ('V3', '경정2리마을회관', 36.4919737, 129.4435679, 'as V3'),
    ('V3', '경정3리마을회관', 36.4744058, 129.4335493, 'as V3'),
    ('V4', '노물리마을회관', 36.445841, 129.4335354, 'aware ~midnight (SNIPPET)'),
    ('V5', '강구2리마을회관', 36.3669479, 129.385317, 'text 00:07 26 Mar; fire ~30 min later (SNIPPET)'),
    ('V5', '강구4리마을회관', 36.3612908, 129.3922726, 'as V5'),
    ('V6', '신덕리 (centroid, flagged)', 36.51999, 128.83085,
     'red flames ~17:30-18:00 KST; arrival ~10 min later (VERIFIED)'),
]


def kst(h):
    if h is None or not np.isfinite(h):
        return None
    return (T0 + dt.timedelta(hours=float(h))).astimezone(KST).strftime('%m-%d %H:%M')


def brackets(firms_dir: Path):
    """Per cell: hi = first FIRMS detection (hard upper bound); lo = last overpass with >= 1 grid detection before hi."""
    r, c, h, _ = load_firms(firms_dir)
    first = np.full(SHAPE, np.inf)
    np.minimum.at(first, (r, c), h)
    passes = np.unique(h)
    det = np.isfinite(first)
    idx = np.searchsorted(passes, first[det], side='left') - 1
    lo = np.full(SHAPE, np.nan)
    lo[det] = np.where(idx >= 0, passes[np.clip(idx, 0, None)], np.nan)
    hi = np.where(det, first, np.nan)
    return lo, hi, det


def interval_min(lo, hi, mask):
    """[min lo, min hi] over cells in mask (None when empty)."""
    if not mask.any():
        return None
    return [float(np.nanmin(lo[mask])), float(np.nanmin(hi[mask]))]


def wide_bracket(toa, sd, passes, lo_det, hi_det, det):
    """Detected cells: FIRMS bracket. Undetected burned cells: [last overpass <= toa - 2 sd (or toa - 2 sd), toa + 2 sd]."""
    lo, hi = lo_det.copy(), hi_det.copy()
    und = ~det & np.isfinite(toa)
    a = toa[und] - 2 * sd[und]
    k = np.searchsorted(passes, a, side='right') - 1
    lo[und] = np.where(k >= 0, passes[np.clip(k, 0, None)], a)
    hi[und] = toa[und] + 2 * sd[und]
    return lo, hi


_W = {}


def _init(surface_path, cells, lazy_eval=None):
    _W['surface'] = dem.load(Path(surface_path))[0]
    _W['cells'] = cells
    _W['lazy_eval'] = lazy_eval


class LazyHreq:
    """Per-cell required heights computed on demand in batches (per-cell results are independent of the batch, so
    this equals place_hreq on all cells exactly for every cell it evaluates)."""

    def __init__(self, surface, x, y, cells, batch=256):
        self.s, self.x, self.y, self.cells, self.batch = surface, x, y, cells, batch
        self.h = np.full((4, len(cells)), np.nan)
        self.done = np.zeros(len(cells), bool)

    def ensure(self, idx):
        todo = idx[~self.done[idx]]
        if todo.size:
            self.h[:, todo] = place_hreq(self.s, self.x, self.y, self.cells[todo])
            self.done[todo] = True

    def first_visible(self, order, row, height, extra_mask):
        """Index (into order) of the first cell in order that is visible (h_req[row] < height) and extra_mask."""
        cand = order[extra_mask[order]]
        for i in range(0, cand.size, self.batch):
            blk = cand[i:i + self.batch]
            self.ensure(blk)
            v = np.isfinite(self.h[row, blk]) & (self.h[row, blk] < height)
            if v.any():
                return int(blk[np.argmax(v)])
        return None


def _work(job):
    key, x, y, full = job
    if full:
        return key, place_hreq(_W['surface'], x, y, _W['cells'])
    return key, _W['lazy_eval'](LazyHreq(_W['surface'], x, y, _W['cells']), x, y, key)


def vis_interval(hr, row, height, L, H, mlo, mhi, smoke):
    """[min L over visible cells in mlo, min H over visible cells in mhi]; None if none visible in mlo.
    hr is either the full (4, n) array or a LazyHreq (exactly equal results)."""
    if isinstance(hr, np.ndarray):
        vis = np.isfinite(hr[row]) & (hr[row] < height)
        lo_m, hi_m = vis & mlo, vis & mhi
        if not lo_m.any():
            return None
        return [float(np.min(L[lo_m])), float(np.min(H[hi_m])) if hi_m.any() else (float('inf') if smoke else None)]
    order_lo = np.argsort(np.where(np.isfinite(L), L, np.inf), kind='stable')
    i = hr.first_visible(order_lo, row, height, mlo)
    if i is None:
        return None
    order_hi = np.argsort(np.where(np.isfinite(H), H, np.inf), kind='stable')
    j = hr.first_visible(order_hi, row, height, mhi)
    return [float(L[i]), float(H[j]) if j is not None else (float('inf') if smoke else None)]


def evaluate(hr, d, foot_extra, trip_h, timing_rows):
    """All intervals and signs for one observer (amendment 1 rules)."""
    out = {}
    for timing, (L, H, M) in timing_rows.items():
        res = {}
        arr = {}
        for R in (FOOTPRINT_M,) + FOOTPRINT_SENS_M:
            arr[R] = interval_min(L, H, M & ((d <= R) | foot_extra))
        res['arrival_h'] = {str(int(R)): v for R, v in arr.items()}
        res['arrival_kst'] = {str(int(R)): (None if v is None else [kst(t) for t in v]) for R, v in arr.items()}
        a500 = arr[FOOTPRINT_M]
        leave = None if a500 is None else [a500[0] - trip_h, a500[1] - trip_h]
        res['leave_by_prelim_h'] = leave
        res['leave_by_prelim_kst'] = None if leave is None else [kst(t) for t in leave]
        for sname, st in SETTINGS.items():
            row = VARIANTS.index(st['row'])
            inrange = np.ones_like(d, bool) if st['cap_m'] is None else d <= st['cap_m']
            for ch in ('flame', 'smoke'):
                base = M & inrange
                mlo = base & (L < SUNSET_H) if ch == 'smoke' else base
                mhi = base & (H <= SUNSET_H) if ch == 'smoke' else base
                V = vis_interval(hr, row, st[ch], L, H, mlo, mhi, ch == 'smoke')
                if V is None or leave is None:
                    gap, sign = None, 'not_bracketed'
                else:
                    gap = [(leave[0] - V[1]) * 60, (leave[1] - V[0]) * 60]
                    sign = 'negative' if gap[1] < 0 else 'nonneg' if gap[0] >= 0 else 'indeterminate'
                res[f'{ch}@{sname}'] = {'first_visible_h': V, 'first_visible_kst': None if V is None else [kst(t) for t in V],
                                        'gap_min': gap, 'sign': sign}
        out[timing] = res
    final = {}
    for ch in ('flame', 'smoke'):
        signs = {out[t][f'{ch}@{s}']['sign'] for t in out for s in SETTINGS}
        if signs == {'negative'}:
            final[ch] = 'robust_negative'
        elif signs == {'nonneg'}:
            final[ch] = 'robust_nonneg_not_robust_to_leave_by_simplification'
        elif signs == {'not_bracketed'}:
            final[ch] = 'not_bracketed'
        else:
            final[ch] = 'indeterminate'
    out['final'] = final
    return out


def main():
    from pyproj import Transformer
    import multiprocessing as mp
    import rasterio
    ap = argparse.ArgumentParser()
    ap.add_argument('--surface', type=Path, required=True)
    ap.add_argument('--toa', type=Path, required=True)
    ap.add_argument('--sd', type=Path, required=True)
    ap.add_argument('--firms-dir', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--limit-places', type=int, default=None)
    ap.add_argument('--full', action='store_true', help='compute every cell (reference mode; slow)')
    ap.add_argument('--doc-only', action='store_true')
    ap.add_argument('--places-only', action='store_true')
    ap.add_argument('--places-slice', default=None, help='start:end over the sorted 174 places')
    a = ap.parse_args()
    _, smeta = dem.load(a.surface)
    with rasterio.open(a.toa) as s:
        toa = s.read(1).astype(float)
    with rasterio.open(a.sd) as s:
        sd = s.read(1).astype(float)
    lo, hi, det = brackets(a.firms_dir)
    _, _, hfirms, _ = load_firms(a.firms_dir)
    passes = np.unique(hfirms)
    wlo, whi = wide_bracket(toa, sd, passes, lo, hi, det)
    rr, cc = np.nonzero(np.ones(SHAPE, bool))
    cells_all = np.column_stack([AFFINE[2] + (cc + 0.5) * AFFINE[0], AFFINE[5] + (rr + 0.5) * AFFINE[4]])
    use = (det | np.isfinite(toa)).ravel()
    idx = np.flatnonzero(use)
    cells = cells_all[idx]
    timing_rows = {'bracket_detected_only': (lo.ravel()[idx], hi.ravel()[idx], det.ravel()[idx]),
                   'wide_bracket_all_burned': (wlo.ravel()[idx], whi.ravel()[idx], np.isfinite(wlo.ravel()[idx]))}
    tr = Transformer.from_crs(4326, 5179, always_xy=True)
    cases = extract.build()
    places = {}
    for c in cases:
        places.setdefault((c['region'], c['origin_id']), c)
    jobs, meta = [], {}
    for k, (vid, label, lat, lon, anchors) in enumerate([] if a.places_only else OBSERVERS):
        x, y = tr.transform(lon, lat)
        near = min(places.values(), key=lambda p: np.hypot(p['place_x'] - x, p['place_y'] - y))
        key = f'doc:{k}'
        jobs.append((key, x, y, a.full))
        meta[key] = {'set': 'documented', 'village': vid, 'observer': label, 'lat': lat, 'lon': lon, 'anchors': anchors,
                     'x': x, 'y': y, 'place': near}
    plist = [] if a.doc_only else sorted(places.values(), key=lambda p: (p['region'], p['origin_id']))[: a.limit_places]
    if a.places_slice:
        i0, i1 = (int(v) for v in a.places_slice.split(':'))
        plist = plist[i0:i1]
    for p in plist:
        key = f"place:{p['region']}:{p['origin_id']}"
        jobs.append((key, p['place_x'], p['place_y'], a.full))
        meta[key] = {'set': 'all_places', 'region': p['region'], 'origin_id': p['origin_id'], 'name': p['name'],
                     'x': p['place_x'], 'y': p['place_y'], 'place': p}
    def prep(key):
        m = meta[key]
        p = m['place']
        x, y = m['x'], m['y']
        d = np.hypot(cells[:, 0] - x, cells[:, 1] - y)
        ex, ey = p.get('entry_x'), p.get('entry_y')
        foot_extra = np.zeros(len(cells), bool)
        if ex is not None:
            foot_extra = (np.abs(cells[:, 0] - ex) <= 187.5) & (np.abs(cells[:, 1] - ey) <= 187.5)
        return d, foot_extra, (p['trip_min_s'] or 0) / 3600.0

    def lazy_eval(lazy, x, y, key):
        d, foot_extra, trip_h = prep(key)
        return {'results': evaluate(lazy, d, foot_extra, trip_h, timing_rows), 'cells_evaluated': int(lazy.done.sum())}

    rows = []
    with mp.get_context('fork').Pool(a.workers, initializer=_init,
                                     initargs=(str(a.surface), cells, lazy_eval)) as pool:
        for n, (key, got) in enumerate(pool.imap_unordered(_work, jobs)):
            m = meta[key]
            d, foot_extra, trip_h = prep(key)
            p = m.pop('place')
            m.update({'leave_by_place': p['origin_id'], 'leave_by_place_name': p['name'], 'trip_min_s': p['trip_min_s'],
                      'entry_xy': [p.get('entry_x'), p.get('entry_y')]})
            if isinstance(got, np.ndarray):
                m['results'] = evaluate(got, d, foot_extra, trip_h, timing_rows)
                m['cells_evaluated'] = int(len(cells))
            else:
                m['results'], m['cells_evaluated'] = got['results'], got['cells_evaluated']
            if m['set'] == 'documented':
                b = m['results']['bracket_detected_only']
                m['v1_smoke_by_1630_kst'] = None
                if m['village'] == 'V1':
                    test_h = (V1_SMOKE_TEST_KST - T0).total_seconds() / 3600
                    m['v1_smoke_by_1630_kst'] = {s: (None if b[f'smoke@{s}']['first_visible_h'] is None else
                                                     ('visible_by_then' if b[f'smoke@{s}']['first_visible_h'][1] <= test_h
                                                      else 'possibly' if b[f'smoke@{s}']['first_visible_h'][0] <= test_h
                                                      else 'not_visible_by_then')) for s in SETTINGS}
                print(f"{m['village']} {m['observer']}: arrival500 {b['arrival_kst']['500']} final {m['results']['final']}",
                      flush=True)
            rows.append(m)
            if n % 20 == 0:
                print(f'  {n}/{len(jobs)}', flush=True)
    a.out.write_text(json.dumps({'definition': 'DEFINITION_C1b.md @ dae181e + amendment 1 @ a285c67',
                                 'surface': smeta, 'sunset_kst': '03-25 18:50', 'rows': rows}, ensure_ascii=False,
                                indent=1, default=lambda o: None if isinstance(o, float) and not np.isfinite(o) else o))


if __name__ == '__main__':
    main()
