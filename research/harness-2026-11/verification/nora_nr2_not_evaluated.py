"""Independent verifier: recount the /2 not-evaluated split from its rows and from the two HEADLINE summaries; then, on
locally built UA packets, recompute membership (entry node's export cell closed at 0 on /2 and not on /1) with own code.
argv: results_dir F_DYN_data_v37 F_DYN_data_v36"""
import json, sys, collections, numpy as np
from pathlib import Path
R, F37, F36 = map(Path, sys.argv[1:4])
d = json.load(open(R / 'HEADLINE_NR2_not_evaluated_split.json'))
n1 = json.load(open(R / 'HEADLINE_NR1_VARIANT_summary.json')); n2 = json.load(open(R / 'HEADLINE_NR2_summary.json'))
key = lambda p: (p['region'], p['start'], p['horizon_h'], p['origin'])
P1 = {key(p): p for p in n1['places']}; P2 = {key(p): p for p in n2['places']}
TV = ('kriged_mean', 'firms_early', 'envelope')
rows = [r for r in d['rows'] if r['variant'] in TV]
print('rows', len(d['rows']), 'timing-variant rows', len(rows), 'classes', dict(collections.Counter(r['class'] for r in rows)))
print('burnset classes', dict(collections.Counter(r['class'] for r in d['rows'] if r['variant'] == 'envelope_burnset')))
C = collections.Counter(); bad = []
for r in rows:
    k = (r['region'], r['start'], r['horizon_h'], r['origin'])
    a1 = P1[k]['nr_cert']['per_variant'][r['variant']]; a2 = P2[k]['nr_cert']['per_variant'][r['variant']]
    r1 = a1.get('leave_by_s') is not None; nr = a2.get('no_route')
    if bool(r['route_on_nr1']) != r1: bad.append(('nr1 flag', k, r['variant']))
    if r['class'] == 'route' and nr is not None: bad.append(('route but no_route', k))
    if r['class'] != 'route' and nr is None: bad.append(('no route class but route', k))
    if (nr is not None) and (r.get('no_route_split_nr2') != nr): bad.append(('split mismatch', k, r['variant']))
    if r['class'] == 'not_evaluated': C['NE lost' if r1 else 'NE no route on /1'] += 1; C['NE split ' + str(nr)] += 1
    elif nr is not None and r1: C['dep ' + nr] += 1
    elif nr is not None: C['rest ' + nr] += 1
for k in sorted(C): print(' ', k, C[k])
print('summary/rows mismatches', len(bad), bad[:5])
for c in ('origin_point_in_flame_at_departure', 'fire_limited_within_loaded_graph', 'possibly_road_limited'):
    print('sum', c, C['NE split ' + c] + C['dep ' + c] + C['rest ' + c])
print('5h == 8h:', collections.Counter((r['region'], r['start'], r['variant'], r['origin'], r['class']) for r in rows if r['horizon_h'] == 5)
      == collections.Counter((r['region'], r['start'], r['variant'], r['origin'], r['class']) for r in rows if r['horizon_h'] == 8))
# own membership on local packets
I = json.load(open(F37 / 'INSTANCE.json'))['instances']
entry = {(i['region'], i['start_tag'], o['origin_id']): o['entry_node'] for i in I for o in i['origins']}
G = json.load(open(F37 / 'graphs_interim/uiseong_andong_2025/graph.json')); xy = {n['id']: (n['x'], n['y']) for n in G['nodes']}
def zero(pk):
    h = json.loads((pk / 'HAZARD.json').read_text()); m = h['members'][0]
    return np.array(m['flame'][0], bool) & (float(m['breakpoints'][0]) == 0), h['grid']
cache = {}; M = collections.Counter(); mm = []
for r in d['rows']:
    if r['region'] != 'uiseong_andong_2025' or r['horizon_h'] != 5: continue
    rel = f"{r['region']}/{r['start']}_h5_{r['variant']}_central_q300"
    p2 = F37 / 'packets_v37_noreentry2' / rel
    p1 = next((b / 'packets_v36_noreentry' / rel for b in (F37, F36) if (b / 'packets_v36_noreentry' / rel).exists()), None)
    if not (p2.exists() and p1): continue
    if rel not in cache:
        z2, g = zero(p2); z1, _ = zero(p1); cache[rel] = (z2 & ~z1, g); print('B0', rel, int((z2 & ~z1).sum()))
    b0, g = cache[rel]
    x, y = xy[entry[(r['region'], r['start'], r['origin'])]]
    i = int((y - g['y0']) // g['resolution']) * g['width'] + int((x - g['x0']) // g['resolution'])
    mine = bool(b0[i]); his = r['class'] == 'not_evaluated'
    M[(mine, his)] += 1
    if mine != his: mm.append((rel, r['origin'], mine, r['class']))
print('local membership (mine, his):', dict(M), 'mismatches', len(mm), mm[:8])
