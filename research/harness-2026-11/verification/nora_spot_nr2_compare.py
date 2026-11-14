"""Independent verifier: compare my acceptance-8 spotting /2 runs for one start with the committed per-start rows;
own control vs HEADLINE_NR2 kriged_mean h5 and own monotonicity counts. argv: my dir, F-3.1 results dir, region, start"""
import json, sys, collections
from pathlib import Path
P, R, region, start = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
D = (0, 500, 1000, 2000)
mine = {d: json.load(open(P / f'h_d{d}.json')) for d in D}
his = json.load(open(R / 'ACCEPT8_SPOTTING_NR2.json'))['starts'][f'{region}|{start}']
for d in D:
    for k in ('witness_checks', 'no_route_split'):
        a, b = mine[d][k], his[k][str(d)]
        print(d, k, 'SAME' if a == b else ('DIFF', a, b))
    print(d, 'transform', mine[d]['transform'], his['transform'][str(d)])
LB = lambda d, f: {o: x['leave_by_' + f] for o, x in mine[d]['origins_detail'].items()}
hl = json.load(open(R / 'HEADLINE_NR2_summary.json'))
H = {p['origin']: p for p in hl['places'] if p['region'] == region and p['start'] == start and p['horizon_h'] == 5}
mm = 0
for f in ('nr_cert', 'nr_router'):
    for o, v in LB(0, f).items():
        if v != H[o][f]['per_variant']['kriged_mean'].get('leave_by_s'): mm += 1
print('control d=0 vs HEADLINE /2 kriged h5 mismatches', mm, 'of', 2 * len(H))
viol = []
for a, b in ((0, 500), (500, 1000), (1000, 2000), (0, 2000)):
    for f in ('nr_cert', 'nr_router'):
        C = collections.Counter(); x, y = LB(a, f), LB(b, f)
        for o in x:
            u, w = x[o], y[o]
            if u is None and w is None: C['none_on_both'] += 1
            elif w is None: C['lost'] += 1
            elif u is None: C['violation'] += 1; viol.append((a, b, f, o))
            elif w == u: C['equal'] += 1
            elif w < u: C['earlier'] += 1
            else: C['violation'] += 1; viol.append((a, b, f, o))
        h = his['monotonicity'][f'{a}->{b}:{f}']
        print(f'{a}->{b} {f}', dict(C), 'SAME' if dict(C) == h else ('HIS', h))
print('violations', viol)
