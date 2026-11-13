"""Independent verifier: for F-BASE (f) /2 rows that were ROUTE on /1 and NO_ROUTE on /2, test whether the origin's
INSTANCE entry node lies in a B0 cell (closed at 0 on /2, open at 0 on /1), on locally built packets.
argv: F-BASE dir, F-DYN _data (v37), F-DYN _data (v36) [all]; without 'all' only UA h5 (the row 75 sample)"""
import json, sys, glob, collections, numpy as np
from pathlib import Path
B, F37, F36 = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
def rows(d):
    out = {}
    for f in glob.glob(str(B / d / '*.jsonl')):
        L = [json.loads(l) for l in open(f)]
        for r in L[1:]: out[(L[0]['packet'], r['origin'], r['departure'])] = r['no_reentry']['exact'][0]
    return out
N1, N2 = rows('fdyn_f_nr1'), rows('fdyn_f_nr2')
I = json.load(open(F37 / 'INSTANCE.json'))['instances']
entry = {(i['region'], i['start_tag'], o['origin_id'].replace(':', '_').replace('/', '_')): o['entry_node'] for i in I for o in i['origins']}
ALL = len(sys.argv) > 4 and sys.argv[4] == 'all'
xy = {}
for reg in ('uiseong_andong_2025', 'yeongdeok_2025'):
    G = json.load(open(F37 / f'graphs_interim/{reg}/graph.json')); xy[reg] = {n['id']: (n['x'], n['y']) for n in G['nodes']}
def z0(p):
    h = json.loads((p / 'HAZARD.json').read_text()); m = h['members'][0]
    return np.array(m['flame'][0], bool) & (float(m['breakpoints'][0]) == 0), h['grid']
C = collections.Counter(); cache = {}; LOST = {}
for k, e2 in N2.items():
    pk, o, dep = k; r, s, h, v = pk.split(':')
    if not ALL and not (r == 'uiseong_andong_2025' and h == '5'): continue
    rel = f'{r}/{s}_h{h}_{v}_central_q300'
    p2 = F37 / 'packets_v37_noreentry2' / rel
    p1 = next((b / 'packets_v36_noreentry' / rel for b in (F37, F36) if (b / 'packets_v36_noreentry' / rel).exists()), None)
    if not (p2.exists() and p1): C['no local packets'] += 1; continue
    if rel not in cache:
        a, g = z0(p2); b, _ = z0(p1); cache[rel] = (a & ~b, a, g)
    b0, closed2, g = cache[rel]
    x, y = xy[r][entry[(r, s, o)]]
    i = int((y - g['y0']) // g['resolution']) * g['width'] + int((x - g['x0']) // g['resolution'])
    tr = N1[k] + '->' + e2
    cls = 'origin in B0' if b0[i] else 'origin closed at 0 (not B0)' if closed2[i] else 'origin open'
    C[(tr, cls)] += 1
    if tr == 'ROUTE->NO_ROUTE': LOST[k] = cls
for k in sorted(C, key=str): print(k, C[k])
if ALL:
    R = collections.Counter((k[0].split(':')[0], c) for k, c in LOST.items()); print('lost by region/class', dict(R))
    json.dump({'|'.join(map(str, k)): c for k, c in LOST.items()}, open(sys.argv[5], 'w'), indent=0) if len(sys.argv) > 5 else None
print('packets checked', sorted(cache))
