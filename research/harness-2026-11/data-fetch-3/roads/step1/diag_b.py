"""Diagnosis after the step-1 comparison (not part of the pass rule): are B field differences explained by node moves?"""
import json, sys, math, re, collections
own, reb, A = json.load(open(sys.argv[1])), json.load(open(sys.argv[2])), json.load(open(sys.argv[3]))
MAXW = A['max_way_id']; WAYS = A['ways']
OE = {e['id']: e for e in own['edges']}; RE_ = {e['id']: e for e in reb['edges']}
ON = {n['id']: n for n in own['nodes']}; RN = {n['id']: n for n in reb['nodes']}
d = {n: math.hypot(ON[n]['x'] - RN[n]['x'], ON[n]['y'] - RN[n]['y']) for n in set(ON) & set(RN)}
moved = {n for n, v in d.items() if v > 0.01}
vals = sorted(d.values())
print('common nodes', len(d), 'max diff among non-moved (<=0.01 m)', max(v for v in vals if v <= 0.01))
print('moved nodes', len(moved), 'diff quantiles m: min %.3f median %.3f max %.1f' % (min(d[n] for n in moved), sorted(d[n] for n in moved)[len(moved)//2], max(d[n] for n in moved)))
def seg_eq(a, b):
    return len(a) == len(b) and all(x['cell'] == y['cell'] and abs(x['start']-y['start']) <= 1e-9 and abs(x['end']-y['end']) <= 1e-9 for x, y in zip(a, b))
common = set(OE) & set(RE_)
bad = [e for e in common if OE[e]['u'] == RE_[e]['u'] and OE[e]['v'] == RE_[e]['v'] and
       (OE[e]['travel_ticks'] != RE_[e]['travel_ticks'] or not seg_eq(OE[e]['segments'], RE_[e]['segments']))]
unexpl = [e for e in bad if OE[e]['u'] not in moved and OE[e]['v'] not in moved]
print('common edges with same u,v but ticks/segments differ:', len(bad), '; with NEITHER endpoint moved:', len(unexpl), unexpl[:5])
# owner-only non-U forbidden pairs: ways involved
of = {tuple(p) for p in own['forbidden_turns']}; rf = {tuple(p) for p in reb['forbidden_turns']}
isU = lambda p: p[0].rsplit(':', 1)[0] == p[1].rsplit(':', 1)[0]
for p in sorted(of - rf):
    if isU(p): continue
    ws = [OE[x]['source_way'] for x in p]
    print('owner-only non-U', p, 'ways', ws, 'any way > pbf max', any(w > MAXW for w in ws), 'in pbf', [str(w) in WAYS for w in ws])
