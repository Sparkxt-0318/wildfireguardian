"""RADIANT_PLAN.md §7: (a) surface vs crown standoff table; (b) spotting-distance counts and time within d.
Sensitivity under stated assumptions; not a count of unsafe routes.   python radiant_s7.py"""
import json, math, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import clearance as C, standoff_route as SR, standoff_lit as SL  # noqa: E402

clear = [(json.loads(l)['mission'], json.loads(l)['published_clearance_m'], json.loads(l)['published_limit_label'])
         for l in (HERE / 'results/CLEARANCE.jsonl').read_text().splitlines() if l.strip()]
CASES = [('surface', 76.0, H) for H in (1.0, 2.0, 5.0, 10.0)] + [('crown', E, H) for E in (112.0, 118.0, 150.0, 200.0) for H in (10.0, 20.0, 30.0, 40.0, 50.0)]
rows = []
for window in (1.0, 0.5):
    for W in (100.0, 3750.0):
        for kind, E, H in CASES:
            d1, d25 = SL.sd(E * window, H, W, 1.0), SL.sd(E * window, H, W, 2.5)
            rows.append(dict(kind=kind, E=E, H=H, W=W, window=window, standoff_1p0_m=d1, standoff_2p5_m=d25,
                             below_1p0=sum(c < d1 for _, c, _ in clear), below_2p5=sum(c < d25 for _, c, _ in clear),
                             crop_below_1p0=sum(c < d1 and l == 'CROP' for _, c, l in clear),
                             sensitivity=(W != 100.0 or window != 1.0 or E >= 150.0)))
print('7a  (main: W 100, window 1.0, E <= 118; others are labelled sensitivities)')
for kind in ('surface', 'crown'):
    for main in (True, False):
        rr = [r for r in rows if r['kind'] == kind and (not r['sensitivity']) == main]
        if rr:
            print('  %-7s %-11s standoff(1.0) %5.0f-%5.0f m (2.5) %5.0f-%5.0f m | routes below 1.0: %d-%d, 2.5: %d-%d (of %d)'
                  % (kind, 'main' if main else 'sensitivity', min(r['standoff_1p0_m'] for r in rr), max(r['standoff_1p0_m'] for r in rr),
                     min(r['standoff_2p5_m'] for r in rr), max(r['standoff_2p5_m'] for r in rr), min(r['below_1p0'] for r in rr),
                     max(r['below_1p0'] for r in rr), min(r['below_2p5'] for r in rr), max(r['below_2p5'] for r in rr), len(clear)))
# 7b
spot = []
for rf in sorted((HERE / 'routes').glob('*.json')):
    r = json.loads(rf.read_text()); region, case = r['mission'].split('__')
    I = C.Instance(*C.load(region, case)); pos = SR.positions(I, r); d = SR.nearest_active_distance(I, pos)
    kinds = np.array([p[3] for p in pos]); stat = np.isin(kinds, ['WAIT', 'DWELL']); issue = kinds == 'ISSUE'   # departure instant kept separate (Mira)
    for D in (500.0, 1000.0, 2000.0):
        inside = d < D
        spot.append(dict(mission=r['mission'], d_m=D, clearance_m=dict((m, c) for m, c, _ in clear)[r['mission']],
                         seconds_inside=int(inside.sum()), moving_s=int((inside & ~stat & ~issue).sum()), stationary_s=int((inside & stat).sum()),
                         issue_s=int((inside & issue).sum())))
print('7b  spotting distance (route side)')
for D in (500.0, 1000.0, 2000.0):
    ss = [s for s in spot if s['d_m'] == D]
    print('  d=%4.0f m: routes with clearance < d: %2d of %d | routes with a real wait/dwell inside d: %d | total s inside: moving %d, stationary %d'
          % (D, sum(s['clearance_m'] < D for s in ss), len(ss), sum(s['stationary_s'] > 0 for s in ss),
             sum(s['moving_s'] for s in ss), sum(s['stationary_s'] for s in ss)))
    for s in ss:
        if s['seconds_inside']:
            print('      %-46s clearance %7.1f m  inside %4d s (moving %4d, stationary %3d)' % (s['mission'], s['clearance_m'], s['seconds_inside'], s['moving_s'], s['stationary_s']))
(HERE / 'results/RADIANT_S7.json').write_text(json.dumps({'plan': 'RADIANT_PLAN.md §7', 'standoff': rows, 'spotting': spot}, indent=1) + '\n')
