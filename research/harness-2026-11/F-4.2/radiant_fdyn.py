"""RADIANT_PLAN.md §2 on F-DYN: (a) linear dose binds; (b) physiological flux reached on the published route (kit
checker's certified peak upper bound, an enclosure: 0 proves 'never reached', >0 may be an artefact); (c) packet-wide
maximum cell-centre model flux over cells containing a routed road segment, excluding flaming cells in that interval.
Routes are labelled KIT / TESTKIT by source run and never pooled. Window factor 1.0 default; 0.5 as labelled sensitivity.
  python radiant_fdyn.py --runs KIT=RUN TESTKIT=RUN --out OUT.json
"""
import argparse, json, math
from pathlib import Path


def road_cells(graph, step=50.0):
    g = graph['grid'] if 'grid' in graph else None
    nodes = {n['id']: n for n in graph['nodes']}; cells = set()
    return nodes, cells


def cells_of_graph(graph, grid):
    x0, y0, res, W, H = grid['x0'], grid['y0'], grid['resolution'], grid['width'], grid['height']
    nodes = {n['id']: n for n in graph['nodes']}; out = set()
    def add(x, y):
        c, r = int(math.floor((x - x0) / res)), int(math.floor((y - y0) / res))
        if 0 <= c < W and 0 <= r < H:
            out.add(r * W + c)
    for e in graph['edges']:
        a, b = nodes[e['u']], nodes[e['v']]
        L = math.hypot(b['x'] - a['x'], b['y'] - a['y']); n = max(1, int(L / 25.0))
        for k in range(n + 1):
            u = k / n; add(a['x'] + (b['x'] - a['x']) * u, a['y'] + (b['y'] - a['y']) * u)
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--runs', nargs='+', required=True); ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    out = {'requests': [], 'packets': {}}
    for spec in a.runs:
        label, run = spec.split('=', 1)
        for d in sorted(Path(run).glob('runs/*')):
            if not (d / 'RESULT.json').exists():
                continue
            res = json.loads((d / 'RESULT.json').read_text()); job = json.loads((d / 'JOB.json').read_text())
            req = json.loads((d / 'ORIGINAL_REQUEST.json').read_text())
            dec = (res.get('decision') or {}); st = dec.get('authoritative_status')
            wr = res.get('whole_road_check') or {}; rad = wr.get('adaptive_fallback') or wr.get('radiation') or {}
            pm = rad.get('per_member') or []
            if isinstance(pm, dict):
                pm = [dict(v, id=k) for k, v in pm.items()]
            published = str(st).startswith('CHECKED_JOURNEY')
            row = {'label': label, 'tag': d.name, 'status': st, 'published': published}
            if published and pm:
                dose = max(m['dose_upper_kj_m2'] for m in pm); peak = max(m['peak_upper_kw_m2'] for m in pm)
                row.update(dose_upper_max_kj_m2=dose, peak_upper_max_kw_m2=peak,
                           a_linear_dose_binds=dose >= 100.0,
                           b_flux_ge_1=peak >= 1.0, b_flux_ge_2p5=peak >= 2.5,
                           b_flux_ge_1_window0p5=0.5 * peak >= 1.0, b_flux_ge_2p5_window0p5=0.5 * peak >= 2.5)
            else:
                reason = str(dec.get('unresolved_reason') or '') + ' ' + str(wr.get('reason') or '')
                row.update(a_linear_dose_binds=('DOSE' in reason.upper()) if not published else None, refusal_or_unresolved_reason=reason.strip())
            out['requests'].append(row)
            pk = str(Path(job['hazard_path']).parent)
            if pk not in out['packets']:
                hz = json.loads(Path(job['hazard_path']).read_text()); graph = json.loads(Path(job['graph_path']).read_text())
                cells = cells_of_graph(graph, hz['grid']); best = (0.0, None)
                for m in hz['members']:
                    for i, (fx, fl) in enumerate(zip(m['flux'], m['flame'])):
                        for c in cells:
                            if not fl[c] and fx[c] is not None and fx[c] > best[0]:
                                best = (fx[c], {'member': m['id'], 'interval': i, 'cell': c})
                units = (hz.get('units') or {}).get('flux')
                out['packets'][pk] = {'c_max_nonflame_road_cell_flux': best[0], 'units': units, 'where': best[1], 'road_cells': len(cells),
                                      'label': 'cell-centre model flux; not an enclosure of road-segment flux'}
            print(row)
    for pk, v in out['packets'].items():
        print(pk.split('/')[-1], v['c_max_nonflame_road_cell_flux'], v['units'], v['road_cells'])
    a.out.write_text(json.dumps(out, indent=1, default=str) + '\n')


if __name__ == '__main__':
    main()
