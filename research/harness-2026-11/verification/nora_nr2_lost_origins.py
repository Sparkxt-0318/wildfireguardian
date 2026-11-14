"""Independent verifier: for /2 lost routes labelled origin_point_in_flame_at_departure, map each origin's entry node
to its export-grid cell (own code) and test: closed at t=0 under /2, not closed at t=0 under /1 (i.e. a B0 cell).
argv: results_dir F_DYN_data_v37 F_DYN_data_v36"""
import json, sys, collections, numpy as np
from pathlib import Path
R, F37, F36 = map(Path, sys.argv[1:4])
n1 = json.load(open(R / 'HEADLINE_NR1_VARIANT_summary.json')); n2 = json.load(open(R / 'HEADLINE_NR2_summary.json'))
key = lambda p: (p['region'], p['start'], p['horizon_h'], p['origin'])
P1 = {key(p): p for p in n1['places']}
I = json.load(open(F37 / 'INSTANCE.json'))['instances']
entry = {(i['region'], i['start_tag'], o['origin_id']): o['entry_node'] for i in I for o in i['origins']}
G = json.load(open(F37 / 'graphs_interim/uiseong_andong_2025/graph.json'))
xy = {n['id']: (n['x'], n['y']) for n in G['nodes']}
def first0(pk):
    h = json.loads((pk / 'HAZARD.json').read_text()); m = h['members'][0]
    fl = np.array(m['flame'], bool); bp = np.array(m['breakpoints'], float); g = h['grid']
    return fl[0] & (bp[0] == 0), g
def pkt(base, rel):
    for b in base:
        p = b / rel
        if p.exists(): return p
C = collections.Counter(); bad = []
for p in n2['places']:
    if p['region'] != 'uiseong_andong_2025' or p['horizon_h'] != 5: continue
    for v, a in p['nr_cert']['per_variant'].items():
        if a.get('no_route') != 'origin_point_in_flame_at_departure': continue
        if P1[key(p)]['nr_cert']['per_variant'][v].get('leave_by_s') is None: continue   # not a lost route
        rel = f"{p['region']}/{p['start']}_h5_{v}_central_q300"
        p2 = pkt([F37 / 'packets_v37_noreentry2'], rel); p1 = pkt([F37 / 'packets_v36_noreentry', F36 / 'packets_v36_noreentry'], rel)
        if not (p1 and p2): C['no_local_packets'] += 1; continue
        z2, g = first0(p2); z1, _ = first0(p1)
        x, y = xy[entry[(p['region'], p['start'], p['origin'])]]
        c = int((x - g['x0']) // g['resolution']); rb = int((y - g['y0']) // g['resolution'])
        i = rb * g['width'] + c
        nb = [ (rb + dr) * g['width'] + (c + dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1)
               if 0 <= rb + dr < g['height'] and 0 <= c + dc < g['width']]
        tag = ('cell_B0' if z2[i] and not z1[i] else 'cell_closed_both' if z2[i] and z1[i]
               else 'neighbour_B0' if any(z2[j] and not z1[j] for j in nb) else 'NOT_ON_B0')
        C[(p['start'], v, tag)] += 1
        if tag in ('NOT_ON_B0', 'cell_closed_both'): bad.append((p['start'], v, p['origin'], tag))
for k in sorted(C, key=str): print(k, C[k])
print('flagged', len(bad), bad[:10])
