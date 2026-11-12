"""RADIANT_PLAN.md §4a and §4b: time inside the standoff and fractional dose per route (4a); per mission, the existence
and arrival cost of a route whose clearance exceeds each standoff (4b). Sensitivity under stated flame assumptions,
not a count of unsafe routes.

  python standoff_route.py --part 4a [--routes routes/]          # seconds, fast
  python standoff_route.py --part 4b --out results/STANDOFF_ROUTES.jsonl [--only mission,...]   # route searches
"""
import argparse, json, math, sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import clearance as C  # noqa: E402
import standoff as S   # noqa: E402

FLAMES = [(E, H, W) for W in (375.0, 3750.0) for H in (5.0, 10.0, 20.0) for E in (50.0, 100.0)]
WINDOWS = (1.0, 0.5)
TDU = 80.0


def positions(I, route):
    """(t, x, y, kind) at every integer second of the full mission (issue .. end of dwell)."""
    req = I.req; out = []
    t0 = int(req['departure']); n = I.nodes[req['position']['node']]
    out.append((t0, n['x'], n['y'], 'ISSUE'))
    for L in route['legs']:
        a, b = int(L['start']), int(L['end'])
        if L['kind'] == 'EDGE':
            e = I.edges[I.eidx[L['edge']]]; p0 = I.nodes[e['u']]; p1 = I.nodes[e['v']]
            for t in range(a + 1, b + 1):
                u = (t - a) / (b - a); out.append((t, p0['x'] + (p1['x'] - p0['x']) * u, p0['y'] + (p1['y'] - p0['y']) * u, 'EDGE'))
        else:
            n = I.nodes[L['node']]
            out.extend((t, n['x'], n['y'], 'WAIT') for t in range(a + 1, b + 1))
    dw = [d['dwell'] for d in req['destinations'] if d['node'] == route['destination']][0]
    n = I.nodes[route['destination']]
    out.extend((t, n['x'], n['y'], 'DWELL') for t in range(route['arrival'] + 1, route['arrival'] + dw + 1))
    return out


def nearest_active_distance(I, pos):
    d = np.full(len(pos), np.inf)
    T = np.array([p[0] for p in pos], float); X = np.array([p[1] for p in pos]); Y = np.array([p[2] for p in pos])
    for j in range(len(I.SR)):
        act = (I.SB[j] <= T) & (T < I.SE[j])
        if not act.any():
            continue
        x0, x1, y0, y1 = I.SR[j]
        dx = np.maximum(np.maximum(x0 - X, 0), X - x1); dy = np.maximum(np.maximum(y0 - Y, 0), Y - y1)
        d = np.where(act, np.minimum(d, np.hypot(dx, dy)), d)
    return d


def part_4a(routes_dir):
    rows = []
    for rf in sorted(Path(routes_dir).glob('*.json')):
        r = json.loads(rf.read_text()); region, case = r['mission'].split('__')
        I = C.Instance(*C.load(region, case))
        pos = positions(I, r); d = nearest_active_distance(I, pos)
        kinds = np.array([p[3] for p in pos])
        for window in WINDOWS:
            for E, H, W in FLAMES:
                q = np.array([0.0 if not math.isfinite(x) else window * S.flux(E, H, W, max(x, 1e-3)) for x in d])
                in1, in25 = q >= 1.0, q >= 2.5
                fd = float(np.sum(np.where(in1, q, 0.0) ** (4 / 3)) / TDU)
                rows.append({'mission': r['mission'], 'E': E, 'H': H, 'W': W, 'window': window,
                             'min_distance_m': float(np.min(d)) if np.isfinite(d).any() else None,
                             'seconds_q_ge_1': int(in1.sum()), 'seconds_q_ge_2p5': int(in25.sum()),
                             'stationary_seconds_q_ge_1': int((in1 & np.isin(kinds, ['WAIT', 'DWELL', 'ISSUE'])).sum()),
                             'max_q_kw_m2': float(q.max()), 'fractional_dose': fd, 'fd_ge_1': fd >= 1.0})
    return rows


def part_4b(out, only=None):
    cases = sorted({math.ceil(S.standoff(E, H, W, q0, w)) for (E, H, W) in FLAMES for q0 in (1.0, 2.5) for w in WINDOWS})
    for rf in sorted((HERE / 'routes').glob('*.json')):
        r = json.loads(rf.read_text()); m = r['mission']
        if only and m not in only.split(','):
            continue
        region, case = m.split('__'); g, rq, src, hz = C.load(region, case); I = C.Instance(g, rq, src, hz)
        a0 = I.search(0.0)['arrival']; D = int(rq['horizon'] - max(d['dwell'] for d in rq['destinations']))
        o0 = min(o[0] for x in rq['destinations'] for o in x['open_intervals'])
        for dstar in cases:
            res = I.search(float(dstar))
            rel = None if res is not None else I.relaxed(float(dstar))
            if res is not None and res['arrival'] <= D:
                c, lim = I.route_clearance(res)
                status = 'EXISTS'; extra = res['arrival'] - a0
                wf = HERE / 'results/standoff_witnesses'; wf.mkdir(parents=True, exist_ok=True)
                (wf / ('%s__d%d.json' % (m, dstar))).write_text(json.dumps({'mission': m, 'deadline': 'standoff_%d' % dstar,
                    'arrival': res['arrival'], 'destination': res['destination'], 'legs': res['legs'], 'r_lo_m': float(dstar), 'clearance_m': c}))
            else:
                c = None; extra = None
                sound_none = rel is None or max(rel['arrival'], o0) > D
                status = 'NONE_EXISTS' if sound_none else 'NOT_FOUND_WITNESS_SEARCH'
            row = {'mission': m, 'standoff_m': dstar, 'status': status, 'arrival_cost_s': extra, 'witness_clearance_m': c,
                   'a0': a0, 'upper_bound_certified': not (hz['R_max'] < rq['horizon'] and D > hz['R_max'])}
            with Path(out).open('a') as f:
                f.write(json.dumps(row) + '\n')
            print('%-46s d*=%4d %-24s cost=%s' % (m, dstar, status, extra), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--part', choices=['4a', '4b'], required=True)
    ap.add_argument('--routes', type=Path, default=HERE / 'routes')
    ap.add_argument('--out', type=Path)
    ap.add_argument('--only', default=None)
    a = ap.parse_args()
    if a.part == '4a':
        rows = part_4a(a.routes)
        out = a.out or HERE / 'results/STANDOFF_TIME.json'
        out.write_text(json.dumps(rows, indent=1) + '\n')
        for m in sorted({r['mission'] for r in rows}):
            rr = [r for r in rows if r['mission'] == m and r['window'] == 1.0]
            print('%-46s min d=%7.1f m | s(q>=1) %3d-%3d | stationary %3d-%3d | FD %.3f-%.3f'
                  % (m, rr[0]['min_distance_m'] or -1, min(x['seconds_q_ge_1'] for x in rr), max(x['seconds_q_ge_1'] for x in rr),
                     min(x['stationary_seconds_q_ge_1'] for x in rr), max(x['stationary_seconds_q_ge_1'] for x in rr),
                     min(x['fractional_dose'] for x in rr), max(x['fractional_dose'] for x in rr)))
    else:
        part_4b(a.out or HERE / 'results/STANDOFF_ROUTES.jsonl', a.only)


if __name__ == '__main__':
    main()
