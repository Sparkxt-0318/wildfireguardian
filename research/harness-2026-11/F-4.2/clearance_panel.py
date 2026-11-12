"""F-4.2 minimum experiment on the 15 routed missions: spatial clearance margins and the travel-time trade-off.

For each published route in routes/: its clearance r* (metres; the largest flame dilation it survives, contact part),
its limiting source, the closed-form contact time margin (diagnostic), the distance to the packet domain edge (crop),
then the clearance search: a(0) (should equal the published arrival unless radiation binds), and for deadlines
D = a(0) + {0, 60, 300, 600} s and D = horizon - dwell, the largest r with a route arriving by D, with that route.
Margin routes are written to OUT/margin_routes/ for re-checking by the unchanged full checker (fixed_route_check.py).

  python clearance_panel.py --out OUT [--only mission,...]
"""
import argparse, json, math, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import clearance as C  # noqa: E402

SLACKS = [0, 60, 300, 600]


def limit_label(clear, dom, censored):
    if censored:
        return 'CENSORED_SEARCH_CAP'
    if not math.isfinite(clear):
        return 'NO_ACTIVE_SOURCE'
    if clear >= dom:
        return 'CROP'     # a fire beyond the packet domain could be nearer than the represented fire
    return 'FIRE'


def endpoint(lim, route):
    """Which end limits the clearance: 'DESTINATION' (dwell or a wait at the destination), 'ORIGIN' (first edge),
    or None (an interior road segment). An endpoint limit cannot be improved by choosing another route."""
    if not lim:
        return None
    seg = lim['segment']
    if seg == 'DWELL' or seg == 'WAIT:' + route['destination']:
        return 'DESTINATION'
    first = next((L['edge'] for L in route['legs'] if L['kind'] == 'EDGE'), None)
    if seg == first:
        return 'ORIGIN'
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--only', default=None)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True); (a.out / 'margin_routes').mkdir(exist_ok=True)
    for rf in sorted((HERE / 'routes').glob('*.json')):
        route = json.loads(rf.read_text()); m = route['mission']
        if a.only and m not in a.only.split(','):
            continue
        region, case = m.split('__')
        t0 = time.perf_counter()
        g, rq, src, hz = C.load(region, case)
        I = C.Instance(g, rq, src, hz)
        dwell = [d['dwell'] for d in rq['destinations'] if d['node'] == route['destination']][0]
        clear, lim = I.route_clearance(route)
        tm, touched = C.contact_time_margin(I, route)
        dom = C.domain_distance(I, route)
        base = I.search(0.0)
        row = {'mission': m, 'hazard': hz, 'published_arrival': route['arrival'], 'dwell': dwell,
               'published_clearance_m': clear, 'published_limit': lim, 'published_domain_distance_m': dom,
               'published_limit_label': limit_label(clear, dom, False),
               'published_limit_at_endpoint': endpoint(lim, route),
               'contact_time_margin_s': tm, 'ignited_cells_touched_before_ignition': touched,
               'a0': None if base is None else base['arrival'], 'deadlines': []}
        if base is not None:
            Ds = [(('a0+%d' % s), base['arrival'] + s) for s in SLACKS] + [('horizon', int(rq['horizon'] - max(d['dwell'] for d in rq['destinations'])))]
            for name, D in Ds:
                r, res, rfail = C.best_radius(I, D)
                ent = {'deadline_name': name, 'deadline_s': D, 'r_lo_m': r, 'r_fail_m': rfail,
                       'bracket_gap_m': None if (r is None or rfail is None) else rfail - r,
                       # label-setting upper bound relies on earliest labels dominating; a present-fire expiry R_max
                       # before the deadline can make a later route feasible, so the upper side is then uncertified
                       'upper_bound_certified': not (hz['R_max'] < rq['horizon'] and D > hz['R_max'])}
                if res is not None:
                    c2, l2 = I.route_clearance(res); d2 = C.domain_distance(I, res)
                    ent.update(arrival=res['arrival'], clearance_m=c2, limit=l2, domain_distance_m=d2,
                               limit_label=limit_label(c2, d2, rfail is None), limit_at_endpoint=endpoint(l2, res),
                               n_legs=len(res['legs']))
                    p = a.out / 'margin_routes' / ('%s__%s.json' % (m, name))
                    p.write_text(json.dumps({'mission': m, 'deadline': name, 'arrival': res['arrival'], 'destination': res['destination'],
                                             'legs': res['legs'], 'r_lo_m': r, 'clearance_m': c2}))
                    ent['route_file'] = str(p)
                row['deadlines'].append(ent)
        row['elapsed_s'] = time.perf_counter() - t0
        with (a.out / 'CLEARANCE.jsonl').open('a') as f:
            f.write(json.dumps(row, default=str) + '\n')
        dl = ' '.join('%s:r=%.0f/a=%s' % (e['deadline_name'], e['r_lo_m'] or -1, e.get('arrival')) for e in row['deadlines'])
        print('%-46s pub a=%4d r*=%7.1f (%s) dom=%6.0f tmargin=%s a0=%s | %s  [%.0fs]' % (
            m, route['arrival'], clear, row['published_limit_label'], dom, tm, row['a0'], dl, row['elapsed_s']), flush=True)


if __name__ == '__main__':
    main()
