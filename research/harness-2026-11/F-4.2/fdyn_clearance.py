"""F-DYN clearance margins (FDYN_PLAN 'Margins'; orchestrator 14:43 UTC): the same computation as clearance_panel.py
on F-DYN 5-hour requests whose route was published.
- KIT routes: published by the unmodified kit. These are the kit figure.
- TESTKIT routes: published by the modified test kit (FDYN_PLAN A3b). Labelled as such and never pooled with the kit.
Inputs come from each run folder: JOB.json (graph_path, hazard_path, request_path) and RESULT.json (published route).
A temporary inputs tree with symlinks lets clearance.load read them unchanged.

  python fdyn_clearance.py --out OUT --runs LABEL=RUN_DIR [LABEL=RUN_DIR ...]
"""
import argparse, json, math, os, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import clearance as C  # noqa: E402
from clearance_panel import SLACKS, endpoint, limit_label  # noqa: E402


def stage(job):
    tmp = Path(tempfile.mkdtemp(prefix='fdynclr_'))
    region = job['case_id'].split('__')[0]; case = 'R_' + job['case_id'].split('__', 1)[1]
    (tmp / 'graphs' / region).mkdir(parents=True); (tmp / 'latest_inputs_try02/requests' / region).mkdir(parents=True)
    os.symlink(job['graph_path'], tmp / 'graphs' / region / 'graph.json')
    os.symlink(job['request_path'], tmp / 'latest_inputs_try02/requests' / region / (case + '.json'))
    return tmp, region, case, Path(job['hazard_path']).parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--runs', nargs='+', required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True); (a.out / 'margin_routes').mkdir(exist_ok=True)
    for spec in a.runs:
        label, run = spec.split('=', 1)
        for d in sorted(Path(run).glob('runs/*')):
            res = json.loads((d / 'RESULT.json').read_text()) if (d / 'RESULT.json').exists() else {}
            dec = (res.get('decision') or {}).get('authoritative_status') or ''
            route = res.get('result') or {}
            if not route.get('legs'):        # published from Z after its cap: the route is the checked incumbent
                route = route.get('checked_incumbent') or {}
            if not dec.startswith('CHECKED_JOURNEY') or not route.get('legs'):
                continue
            job = json.loads((d / 'JOB.json').read_text())
            tmp, region, case, pk = stage(job)
            t0 = time.perf_counter()
            g, rq, src, hz = C.load(region, case, inputs=tmp, packet=pk)
            I = C.Instance(g, rq, src, hz)
            dwell = [x['dwell'] for x in rq['destinations'] if x['node'] == route['destination']][0]
            clear, lim = I.route_clearance(route)
            dom = C.domain_distance(I, route)
            base = I.search(0.0)
            row = {'label': label, 'tag': d.name, 'decision': dec, 'published_arrival': route['arrival'], 'dwell': dwell,
                   'published_clearance_m': clear, 'published_limit': lim, 'published_domain_distance_m': dom,
                   'published_limit_label': limit_label(clear, dom, False), 'published_limit_at_endpoint': endpoint(lim, route),
                   'hazard': {k: hz[k] for k in ('T', 'R_max', 'horizon', 'members', 'present_fire_cells')},
                   'a0': None if base is None else base['arrival'], 'deadlines': []}
            if base is not None:
                for name, D in [('a0+%d' % s, base['arrival'] + s) for s in SLACKS]:
                    r, rr, rfail = C.best_radius(I, D)
                    ent = {'deadline_name': name, 'deadline_s': D, 'r_lo_m': r, 'r_fail_m': rfail,
                           'upper_bound_certified': not (hz['R_max'] < rq['horizon'] and D > hz['R_max'])}
                    if rr is not None:
                        c2, l2 = I.route_clearance(rr); d2 = C.domain_distance(I, rr)
                        ent.update(arrival=rr['arrival'], clearance_m=c2, limit_label=limit_label(c2, d2, rfail is None),
                                   limit_at_endpoint=endpoint(l2, rr), domain_distance_m=d2)
                        p = a.out / 'margin_routes' / ('%s__%s__%s.json' % (label, d.name, name))
                        p.write_text(json.dumps({'label': label, 'tag': d.name, 'deadline': name, 'arrival': rr['arrival'],
                                                 'destination': rr['destination'], 'legs': rr['legs'], 'r_lo_m': r, 'clearance_m': c2}))
                    row['deadlines'].append(ent)
            row['elapsed_s'] = time.perf_counter() - t0
            with (a.out / 'FDYN_CLEARANCE.jsonl').open('a') as f:
                f.write(json.dumps(row, default=str) + '\n')
            dl = ' '.join('%s:r=%.0f/a=%s' % (e['deadline_name'], e['r_lo_m'] or -1, e.get('arrival')) for e in row['deadlines'])
            print('%-8s %-62s pub a=%5d r*=%8.1f (%s) dom=%7.0f a0=%s | %s [%.0fs]' % (label, d.name[-62:], route['arrival'], clear,
                  row['published_limit_label'], dom, row['a0'], dl, row['elapsed_s']), flush=True)


if __name__ == '__main__':
    main()
