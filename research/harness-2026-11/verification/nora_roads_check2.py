"""Nora (verifier), follow-up to nora_roads_check.py: edges with the SAME id AND the same (u, v) in both graphs AND both
endpoints unmoved (<= 0.01 m). On that set the recipe alone decides travel_ticks, segments, direction_evidence and
reverse_edge. Stdlib only.  python3 -I nora_roads_check2.py OWNER.json REBUILD.json"""
import hashlib, json, sys, collections
def load(p):
    b = open(p, 'rb').read(); return hashlib.sha256(b).hexdigest(), json.loads(b)
(ho, O), (hr, R) = load(sys.argv[1]), load(sys.argv[2])
print('sha256 owner', ho); print('sha256 rebuild', hr)
ON = {n['id']: n for n in O['nodes']}; RN = {n['id']: n for n in R['nodes']}
OE = {e['id']: e for e in O['edges']}; RE = {e['id']: e for e in R['edges']}
def unmoved(n): return n in ON and n in RN and ((ON[n]['x'] - RN[n]['x']) ** 2 + (ON[n]['y'] - RN[n]['y']) ** 2) ** 0.5 <= 0.01
S = [e for e in set(OE) & set(RE) if (OE[e]['u'], OE[e]['v']) == (RE[e]['u'], RE[e]['v']) and unmoved(OE[e]['u']) and unmoved(OE[e]['v'])]
c = collections.Counter(); worst = 0.0; ex = []
for e in S:
    a, b = OE[e], RE[e]; d = [f for f in ('travel_ticks', 'direction_evidence', 'reverse_edge', 'source_way') if a.get(f) != b.get(f)]
    sa, sb = a['segments'], b['segments']
    if len(sa) != len(sb) or any(x['cell'] != y['cell'] for x, y in zip(sa, sb)): d.append('segments_cells')
    else:
        w = max((max(abs(x['start'] - y['start']), abs(x['end'] - y['end'])) for x, y in zip(sa, sb)), default=0.0); worst = max(worst, w)
        if w > 1e-9: d.append('segments_frac>1e-9')
    for f in d: c[f] += 1
    if d: ex.append((e, d))
print('edges: same id, same (u,v), both endpoints unmoved:', len(S), '| diffs', dict(c), '| max fraction diff %.3e' % worst)
for x in sorted(ex)[:20]: print('   ', x)
same_id_diff_uv = sum(1 for e in set(OE) & set(RE) if (OE[e]['u'], OE[e]['v']) != (RE[e]['u'], RE[e]['v']))
print('common edge ids whose (u,v) differ (way renumbered between dates):', same_id_diff_uv)
