"""F-C1b: see-before-leave intervals for documented villages (DEFINITION_C1b.md @ dae181e).

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


def main():
    from pyproj import Transformer
    import rasterio
    ap = argparse.ArgumentParser()
    ap.add_argument('--surface', type=Path, required=True)
    ap.add_argument('--toa', type=Path, required=True)
    ap.add_argument('--firms-dir', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    surface, smeta = dem.load(a.surface)
    with rasterio.open(a.toa) as s:
        toa = s.read(1).astype(float)
    lo, hi, det = brackets(a.firms_dir)
    rr, cc = np.nonzero(np.ones(SHAPE, bool))
    cx = AFFINE[2] + (cc + 0.5) * AFFINE[0]
    cy = AFFINE[5] + (rr + 0.5) * AFFINE[4]
    cells = np.column_stack([cx, cy])
    use = det | np.isfinite(toa)               # cells with any fire timing (bracket or kriged)
    idx_use = np.flatnonzero(use.ravel())
    tr = Transformer.from_crs(4326, 5179, always_xy=True)
    cases = extract.build()
    places = {}
    for c in cases:
        places.setdefault((c['region'], c['origin_id']), c)
    rows = []
    for vid, label, lat, lon, anchors in OBSERVERS:
        x, y = tr.transform(lon, lat)
        hr = place_hreq(surface, x, y, cells[idx_use])
        d = np.hypot(cells[idx_use, 0] - x, cells[idx_use, 1] - y)
        # nearest planner place for the preliminary leave-by (fastest fire-free trip from its road entry node)
        near = min(places.values(), key=lambda p: np.hypot(p['place_x'] - x, p['place_y'] - y))
        trip_h = (near['trip_min_s'] or 0) / 3600.0
        row = {'village': vid, 'observer': label, 'lat': lat, 'lon': lon, 'anchors': anchors,
               'nearest_place': near['origin_id'], 'nearest_place_name': near['name'],
               'nearest_place_dist_m': float(np.hypot(near['place_x'] - x, near['place_y'] - y)),
               'trip_min_s': near['trip_min_s'], 'results': {}}
        flat_lo, flat_hi = lo.ravel()[idx_use], hi.ravel()[idx_use]
        flat_det = det.ravel()[idx_use]
        flat_toa = toa.ravel()[idx_use]
        for timing in ('bracket_detected_only', 'kriged_inclusive'):
            if timing == 'bracket_detected_only':
                L, H, M = flat_lo, flat_hi, flat_det
            else:     # undetected cells contribute their kriged point value (labelled; sd ~17 h)
                L = np.where(flat_det, flat_lo, flat_toa)
                H = np.where(flat_det, flat_hi, flat_toa)
                M = np.isfinite(L)
            arrival = interval_min(L, H, M & (d <= FOOTPRINT_M))
            res = {'arrival_h': arrival, 'arrival_kst': None if arrival is None else [kst(v) for v in arrival]}
            if arrival is not None:
                leave = [arrival[0] - trip_h, arrival[1] - trip_h]
            else:
                leave = None
            res['leave_by_prelim_kst'] = None if leave is None else [kst(v) for v in leave]
            for sname, st in SETTINGS.items():
                h_row = hr[VARIANTS.index(st['row'])]
                inrange = np.ones_like(d, bool) if st['cap_m'] is None else d <= st['cap_m']
                for ch in ('flame', 'smoke'):
                    vis = M & inrange & np.isfinite(h_row) & (h_row < st[ch])
                    if ch == 'smoke':
                        v_lo_mask = vis & (L < SUNSET_H)
                        v_hi_mask = vis & (H <= SUNSET_H)
                        V = None if not v_lo_mask.any() else [
                            float(np.nanmin(L[v_lo_mask])),
                            float(np.nanmin(H[v_hi_mask])) if v_hi_mask.any() else float('inf')]
                    else:
                        V = interval_min(L, H, vis)
                    if V is None or leave is None:
                        gap, sign = None, 'not_bracketed'
                    else:
                        gap = [(leave[0] - V[1]) * 60, (leave[1] - V[0]) * 60]        # minutes
                        sign = 'negative' if gap[1] < 0 else 'nonneg' if gap[0] >= 0 else 'indeterminate'
                    res[f'{ch}@{sname}'] = {'first_visible_h': V,
                                            'first_visible_kst': None if V is None else [kst(v) for v in V],
                                            'gap_min': gap, 'sign': sign}
            for ch in ('flame', 'smoke'):
                s1, s2 = res[f'{ch}@optimistic']['sign'], res[f'{ch}@pessimistic']['sign']
                res[f'{ch}@robust'] = s1 if s1 == s2 and s1 in ('negative', 'nonneg') else 'indeterminate'
            row['results'][timing] = res
        rows.append(row)
        b = row['results']['bracket_detected_only']
        print(f"{vid} {label}: arrival {b['arrival_kst']} leave-by(prelim) {b['leave_by_prelim_kst']} | "
              f"flame opt {b['flame@optimistic']['first_visible_kst']} pes {b['flame@pessimistic']['first_visible_kst']} "
              f"-> {b['flame@robust']} | smoke opt {b['smoke@optimistic']['first_visible_kst']} "
              f"pes {b['smoke@pessimistic']['first_visible_kst']} -> {b['smoke@robust']}", flush=True)
    a.out.write_text(json.dumps({'definition': 'DEFINITION_C1b.md @ dae181e', 'surface': smeta,
                                 'sunset_kst': '03-25 18:50', 'rows': rows}, ensure_ascii=False, indent=1,
                                default=lambda o: None if isinstance(o, float) and not np.isfinite(o) else o))


if __name__ == '__main__':
    main()
