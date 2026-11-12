"""Cell-level space-time gap between a published route and every drawn new ignition (diagnostic, router cell model).

For each member and each cell with a finite ignition time b, find the route's visits to that cell (edge segments mapped
to cells by the graph's `segments` fractions, traversal time linear in fraction; destination dwell at the node's cell)
and report b - t_exit for visits before ignition. Under a uniform advance delta of every ignition time, a visit
[t0, t1] to an ignited cell is in flame contact iff b - t1 <= delta < b + T - t0 (T = burning duration), so the smallest
positive b - t1 is the router-cell-model contact margin. This diagnostic uses the router's cell assignment, not the
whole-road checker's closed-footprint geometry (which also touches cells the road only grazes); margins from the real
checker are measured separately by fixed_route_check.py.

  python contact_gap.py --packet DIR --graph G.json --request R.json --route RESULT.json
"""
import argparse, json, math
from pathlib import Path

import numpy as np


def visits(graph, route, request):
    E = {e['id']: e for e in graph['edges']}
    out = []
    for L in route['legs']:
        if L['kind'] != 'EDGE':
            continue
        e = E[L['edge']]; f0, f1 = L.get('from_fraction', 0), L.get('to_fraction', 1)
        span = f1 - f0
        for s in e['segments']:
            lo, hi = max(min(s['start'], s['end']), min(f0, f1)), min(max(s['start'], s['end']), max(f0, f1))
            if hi < lo or span == 0:
                continue
            ta = L['start'] + (L['end'] - L['start']) * (lo - f0) / span
            tb = L['start'] + (L['end'] - L['start']) * (hi - f0) / span
            out.append((s['cell'], min(ta, tb), max(ta, tb)))
    nodes = {n['id']: n for n in graph['nodes']}
    g = graph['grid']; n = nodes[route['destination']]
    col = int((n['x'] - g['x0']) // g['resolution']); row = int((n['y'] - g['y0']) // g['resolution'])
    dwell = [d['dwell'] for d in request['destinations'] if d['node'] == route['destination']][0]
    out.append((row * g['width'] + col, route['arrival'], route['arrival'] + dwell))
    return out


def main():
    ap = argparse.ArgumentParser()
    for k in ('--packet', '--graph', '--request', '--route'):
        ap.add_argument(k, type=Path, required=True)
    a = ap.parse_args()
    graph = json.loads(a.graph.read_text()); request = json.loads(a.request.read_text())
    r = json.loads(a.route.read_text()); route = r.get('result', r) if 'legs' not in r else r
    arr = np.load(a.packet / 'constructed_arrays.npz')
    ev = arr['ignition_time_s']          # [S, H, W] native north-up rows
    md = json.loads((a.packet / 'NATIVE_METADATA.json').read_text())
    T = md['settings']['burning_duration_s']; horizon = md['settings']['horizon_s']
    S, H, W = ev.shape
    g = graph['grid']
    assert (g['height'], g['width']) == (H, W)
    V = visits(graph, route, request)
    res = {'members': [], 'T_s': T, 'horizon_s': horizon, 'arrival_s': route['arrival'], 'n_visits': len(V)}
    for s in range(S):
        # graph cell index is row-major from the south (y0 + row*res); native arrays are north-up rows (row reversal).
        evg = ev[s][::-1, :].reshape(-1)
        ign = np.flatnonzero(np.isfinite(evg))
        best = math.inf; touched = []
        for c, t0, t1 in V:
            b = evg[c]
            if not np.isfinite(b):
                continue
            touched.append({'cell': int(c), 'b': float(b), 't0': t0, 't1': t1, 'gap_b_minus_t1': float(b - t1),
                            'bad_delta_interval': [float(b - t1), float(b + T - t0)]})
            if b - t1 > 0:
                best = min(best, float(b - t1))
        res['members'].append({'member': s, 'ignitions': int(ign.size), 'route_visits_to_ignited_cells': touched,
                               'cell_model_contact_margin_s': best})
    res['cell_model_contact_margin_s'] = min(m['cell_model_contact_margin_s'] for m in res['members'])
    # Spatial clearance (cell Chebyshev distance, router cell model) from route visits to (a) present-fire cells active
    # during the visit ([0, R_max)) and (b) any cell with a drawn ignition in any member (regardless of time).
    cur = arr['current_active'][::-1, :].reshape(-1) if arr['current_active'].ndim == 2 else arr['current_active'][0][::-1, :].reshape(-1)
    R = md['construction']['assumptions']['initial_remaining_s'] if 'construction' in md else None
    def cheb(c, cells):
        if cells.size == 0:
            return math.inf
        r, q = divmod(c, W); rr, qq = np.divmod(cells, W)
        return int(np.max(np.stack([np.abs(rr - r), np.abs(qq - q)]), axis=0).min())
    pf = np.flatnonzero(cur)
    anyign = np.flatnonzero(np.isfinite(ev[:, ::-1, :].reshape(S, -1)).any(axis=0))
    res['present_fire_cells'] = int(pf.size); res['R_max_s'] = R
    res['min_cheb_to_present_fire_cells'] = min((cheb(c, pf) for c, t0, t1 in V if R is None or t0 < R), default=math.inf)
    res['min_cheb_to_any_ignited_cell'] = min((cheb(c, anyign) for c, t0, t1 in V), default=math.inf)
    print(json.dumps(res, default=str))


if __name__ == '__main__':
    main()
