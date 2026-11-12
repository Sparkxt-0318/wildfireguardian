"""Account-based F-C1b (DEFINITION_C1b_accounts.md @0674f70 + amendment 1 @02c312d + sources @2ba8a85).

Reads only the documented-observer rows of a C1B_documented JSON (c1b.py --doc-only) and the fixed case table below.
No viewshed is recomputed; no setting is changed.

    python3 research/harness-2026-11/F-C1/seebefore/c1b_accounts.py --documented C1B_documented.json --out C1B_accounts.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

T0 = dt.datetime(2025, 3, 22, 2, 24, tzinfo=dt.timezone.utc)
KST = dt.timezone(dt.timedelta(hours=9))
SETTINGS = ('optimistic', 'pessimistic')
ROWS = ('bracket_detected_only', 'wide_bracket_all_burned')


def h_of(kst_str):
    """'03-25 16:30' (KST, 2025) -> hours since t0."""
    t = dt.datetime.strptime('2025-' + kst_str, '%Y-%m-%d %H:%M').replace(tzinfo=KST)
    return (t - T0).total_seconds() / 3600.0


def kst(h):
    if h is None or h != h or h in (float('inf'), float('-inf')):
        return None
    return (T0 + dt.timedelta(hours=float(h))).astimezone(KST).strftime('%m-%d %H:%M')


# Fixed case table (§1 + sources). S, A as reported; None = not documented (rule consequence recorded at 2ba8a85).
CASES = [
    {'case': 'C1', 'village': 'V1', 'observers': ['지품면사무소'],
     'S': {'kind': 'about', 't': '03-25 16:30', 'what': 'black smoke from the north (면장, at the office)'},
     'A': None, 'A_note': '17:55 not in the dgmbc source (Sofia); not an arrival at this observer',
     'url': 'https://dgmbc.com/NewsArticle/628364'},
    {'case': 'C2', 'village': 'V2', 'observers': ['매정1리마을회관', '매정2리마을회관', '매정3리마을회관'],
     'S': None, 'S_note': '20:00 door-knock is a warning, not a sighting',
     'A': {'kind': 'about', 't': '03-25 20:40',
           'what': "'내가 피하고 10분 뒤 불길이 마을을 집어삼켰다' (body); departure ~20:30 from the photo caption"},
     'url': 'https://www.hankookilbo.com/news/article/A2025032714350000238'},
    {'case': 'C3', 'village': 'V6', 'observers': ['신덕리 (centroid, flagged)'],
     'S': {'kind': 'range', 't': ('03-25 17:30', '03-25 18:00'), 'what': 'red flames coming over (hedged: ~였던 것 같다)'},
     'A': None, 'A_note': "'약 10분 만에 불이 번져' - arrival at the place implied, not stated in words",
     'url': 'https://www.nocutnews.co.kr/news/6318424'},
]


def window(spec, w_min):
    if spec is None:
        return None
    if spec['kind'] == 'about':
        c = h_of(spec['t'])
        return [c - w_min / 60, c + w_min / 60]
    a, b = spec['t']
    return [h_of(a) - w_min / 60, h_of(b) + w_min / 60]


def vis_class(v, s):
    """§5: possible if V_lo <= S_hi; not possible if V_lo > S_hi; certain by S if V_hi <= S_lo."""
    if v is None or v[0] is None:
        return 'not possible (nothing visible in the model)'
    lo, hi = v[0], v[1]
    if hi is not None and hi <= s[0]:
        return 'certain by S'
    if lo <= s[1]:
        return 'possible'
    return 'not possible'


def margin(A, S, trip_h):
    if A is None or S is None:
        return None, 'no account-based sign (S or A not documented)'
    L = [A[0] - trip_h, A[1] - trip_h]
    m = [(L[0] - S[1]) * 60, (L[1] - S[0]) * 60]
    if m[1] < 0:
        return m, 'saw with less time left than the route needed (account-based, about the documented sighting)'
    if m[0] >= 0:
        return m, 'saw with enough time (account-based; not robust to the leave-by simplification)'
    return m, 'indeterminate'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--documented', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    doc = json.loads(a.documented.read_text())
    rows = {(r['village'], r['observer']): r for r in doc['rows'] if r['set'] == 'documented'}
    out = []
    for c in CASES:
        for obs in c['observers']:
            r = rows[(c['village'], obs)]
            trip_h = (r['trip_min_s'] or 0) / 3600.0
            entry = {'case': c['case'], 'village': c['village'], 'observer': obs, 'url': c['url'],
                     'trip_min_s': r['trip_min_s'],
                     'trip_note': 'fire-free drive from the road entry point at model speed; no time to get ready',
                     'S_reported': c['S'], 'S_note': c.get('S_note'), 'A_reported': c['A'], 'A_note': c.get('A_note'),
                     'satellite_arrival_kst_500m': r['results']['bracket_detected_only']['arrival_kst']['500'],
                     'fdyn_leave_by': 'not available (Richard F-3.1 field not present at computation; no substitute)',
                     'windows': {}}
            for w in (30, 15):
                S, A = window(c['S'], w), window(c['A'], w)
                m, sign = margin(A, S, trip_h)
                e = {'S_h': S, 'S_kst': None if S is None else [kst(S[0]), kst(S[1])],
                     'A_h': A, 'A_kst': None if A is None else [kst(A[0]), kst(A[1])],
                     'L_kst': None if A is None else [kst(A[0] - trip_h), kst(A[1] - trip_h)],
                     'margin_min': m, 'sign': sign, 'sign_called': w == 30}
                if S is not None:
                    e['visibility_at_S'] = {row: {f'{k}@{s}': vis_class(r['results'][row][f'{k}@{s}']['first_visible_h'], S)
                                                  for k in ('flame', 'smoke') for s in SETTINGS} for row in ROWS}
                    e['first_visible_kst'] = {row: {f'{k}@{s}': r['results'][row][f'{k}@{s}']['first_visible_kst']
                                                    for k in ('flame', 'smoke') for s in SETTINGS} for row in ROWS}
                entry['windows'][f'pm{w}'] = e
            out.append(entry)
    a.out.write_text(json.dumps({'definition': 'DEFINITION_C1b_accounts.md @0674f70 + amendment 1 @02c312d + sources @2ba8a85',
                                 'input': str(a.documented), 'label': 'ACCOUNT-BASED', 'cases': out},
                                ensure_ascii=False, indent=1))
    for e in out:
        w = e['windows']['pm30']
        print(e['case'], e['observer'], 'S', w['S_kst'], 'A', w['A_kst'], 'sat', e['satellite_arrival_kst_500m'],
              'trip', e['trip_min_s'], '|', w['sign'])
        if 'visibility_at_S' in w:
            for row, v in w['visibility_at_S'].items():
                print('   ', row, v)


if __name__ == '__main__':
    main()
