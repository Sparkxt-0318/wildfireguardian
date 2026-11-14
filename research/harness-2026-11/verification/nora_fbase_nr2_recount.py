"""Independent verifier: recount F-BASE rule (f) no_reentry/2 rows (fdyn_f_nr2) and compare with reopening (fdyn_d) and /1 (fdyn_f_nr1).
argv: F-BASE dir"""
import json, sys, collections, glob, os
B = sys.argv[1]
def load(d):
    out = {}; hdr = {}
    for f in sorted(glob.glob(f'{B}/{d}/*.jsonl')):
        L = [json.loads(l) for l in open(f)]; pk = L[0]['packet']; hdr[pk] = L[0]
        for r in L[1:]: out[(pk, r['origin'], r['departure'])] = r
    return out, hdr
N2, H2 = load('fdyn_f_nr2'); N1, _ = load('fdyn_f_nr1'); D, _ = load('fdyn_d')
print('packets', len(H2), 'rows', len(N2), 'same keys as /1', set(N2) == set(N1), 'as reopening', set(N2) == set(D))
C = collections.Counter(); P = collections.Counter(); S3 = collections.Counter(); sig = collections.Counter(); mono = collections.Counter(); bad = []
for k, r in N2.items():
    n = r['no_reentry']; e = n['exact']
    C['exact ' + e[0]] += 1
    if e[0] == 'NO_ROUTE': P[k[0].split(':')[0][:2]] += 1
    # recompute flags
    i = n['s1'][0] == 'NO_ROUTE' and e[0] == 'ROUTE'          # S1 rejects a true route? (i) as defined: S1 ROUTE rejected by truth
    i = n['s1'][0] == 'ROUTE' and e[0] == 'NO_ROUTE'
    ii = n['s2'][0] == 'NO_ROUTE' and e[0] == 'ROUTE'
    if i != n['i_s1_route_rejected'] or ii != n['ii_s2_refuses_resolvable']: bad.append(('flag', k))
    C['(i)'] += i; C['(ii)'] += ii
    if n['s1'][0] == 'ROUTE':
        C['s1 route'] += 1; C['s1 T==exact'] += n['s1'][1] == e[1]; C['s1 replays'] += bool(n['s1_replays_true'])
    if n['s1'] != e: C['s1 != exact'] += 1
    for d in ('600', '1800', '3600'):
        s = n['s3_' + d]; o = s['outcome']
        S3[(d, o)] += 1
        if o == 'ROUTE' and (s['T'] != e[1] or not s['replays']): bad.append(('s3', k, d))
        if s['i_violation'] or s['ii_refuses_resolvable']: S3[(d, 'flag')] += 1
        if (o == 'ROUTE') != (e[0] == 'ROUTE'): S3[(d, 'disagree_exact')] += 1
    re = D[k]['reopening']['exact'][0]
    sig[(k[2], ('both ROUTE' if e[0] == re == 'ROUTE' else 'NR-only NO_ROUTE' if re == 'ROUTE' else 'both NO_ROUTE' if e[0] == 'NO_ROUTE' else 'reopen-only NO_ROUTE'))] += 1
    e1 = N1[k]['no_reentry']['exact']
    if e1[0] == 'ROUTE' and e[0] == 'NO_ROUTE': mono['ROUTE->NO_ROUTE ' + k[0][:2]] += 1
    elif e1[0] == 'NO_ROUTE' and e[0] == 'ROUTE': mono['NO_ROUTE->ROUTE'] += 1
    elif e1[0] == e[0] == 'ROUTE': mono['both route, /2 ' + ('same' if e[1] == e1[1] else 'later' if e[1] > e1[1] else 'EARLIER')] += 1
    else: mono['both NO_ROUTE'] += 1
    if r['instance_sha256'] == N1[k]['instance_sha256']: C['instance sha = /1'] += 1
print(dict(C)); print('NO_ROUTE by region', dict(P))
per = collections.Counter(k[0] for k, r in N2.items() if r['no_reentry']['exact'][0] == 'NO_ROUTE'); print('per packet NO_ROUTE', sorted(per.values()))
print('S3', dict(S3)); print('signature', dict(sorted(sig.items()))); print('vs /1', dict(mono))
print('flag/S3 problems', len(bad), bad[:5])
print('headers: script', {h['script_sha256'][:8] for h in H2.values()}, 'transform', {h['transform'] for h in H2.values()})
pk = json.load(open(f'{B}/NR2_PACKETS.json'))
print('NR2_PACKETS type', type(pk).__name__, (list(pk)[:3] if isinstance(pk, dict) else pk[:1]))
