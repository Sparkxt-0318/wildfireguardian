"""RADIANT_PLAN.md §6: the literature-based flame set (Sofia). Receiver at flame-centre height (4 corner rectangles
of H/2 x W/2). Counts routes whose published clearance is below each standoff. A sensitivity range, not a count of
unsafe routes.   python3 standoff_lit.py"""
import json, math
from pathlib import Path
import standoff as S
HERE = Path(__file__).resolve().parent

def flux(E, H, W, d):
    return E * 4 * S.f_corner(H / 2, W / 2, d)

def sd(E, H, W, q0):
    lo, hi = 1e-6, 1e6
    for _ in range(200):
        m = math.sqrt(lo * hi); lo, hi = (m, hi) if flux(E, H, W, m) > q0 else (lo, m)
    return hi

clear = [(json.loads(l)['mission'], json.loads(l)['published_clearance_m'], json.loads(l)['published_limit_label'])
         for l in (HERE / 'results/CLEARANCE.jsonl').read_text().splitlines() if l.strip()]
rows = []
for window in (1.0, 0.5):
    for W in (100.0, 3750.0):
        for H in (5.0, 10.0, 20.0, 30.0, 40.0):
            for E in (76.0, 112.0, 200.0):
                d1, d25 = sd(E * window, H, W, 1.0), sd(E * window, H, W, 2.5)
                n1 = sum(c < d1 for _, c, _ in clear); n25 = sum(c < d25 for _, c, _ in clear)
                rows.append(dict(E=E, H=H, W=W, window=window, standoff_1p0_m=d1, standoff_2p5_m=d25, below_1p0=n1, below_2p5=n25,
                                 crop_below_1p0=sum(c < d1 and l == 'CROP' for _, c, l in clear)))
for window in (1.0, 0.5):
    for W in (100.0, 3750.0):
        rr = [r for r in rows if r['window'] == window and r['W'] == W]
        print('window %.1f W %5.0f: standoff(1.0) %4.0f-%4.0f m, (2.5) %4.0f-%4.0f m | routes below 1.0: %d-%d, below 2.5: %d-%d (of %d)'
              % (window, W, min(r['standoff_1p0_m'] for r in rr), max(r['standoff_1p0_m'] for r in rr), min(r['standoff_2p5_m'] for r in rr),
                 max(r['standoff_2p5_m'] for r in rr), min(r['below_1p0'] for r in rr), max(r['below_1p0'] for r in rr),
                 min(r['below_2p5'] for r in rr), max(r['below_2p5'] for r in rr), len(clear)))
for r in rows:
    if r['window'] == 1.0 and r['W'] == 100.0:
        print('  E%3.0f H%2.0f W100: %6.1f / %6.1f m  below %d / %d' % (r['E'], r['H'], r['standoff_1p0_m'], r['standoff_2p5_m'], r['below_1p0'], r['below_2p5']))
(HERE / 'results/STANDOFF_LIT.json').write_text(json.dumps({'plan': 'RADIANT_PLAN.md §6', 'rows': rows}, indent=1) + '\n')
