"""Nora (verifier): independent road-graph comparison, owner vs rebuild. Stdlib only, reads two graph.json files.
Does not use the pbf or Daniel's code. Run:  python3 -I nora_roads_check.py OWNER.json REBUILD.json
Prints: file sha256; id-set differences; per-field differences on common edges; the same restricted to edges whose
u and v positions agree within 0.01 m in both graphs (the 'data unchanged at the endpoints' set, independent of any
way-level classification); largest |fraction| difference there; moved-node stats; waitable vs dead-end (1 distinct
neighbour) recomputed on BOTH graphs; U-turn forbidden pairs vs dead ends on both graphs."""
import hashlib, json, sys, collections
def load(p):
    b = open(p, 'rb').read(); return hashlib.sha256(b).hexdigest(), json.loads(b)
(ho, O), (hr, Rb) = load(sys.argv[1]), load(sys.argv[2])
print('sha256 owner', ho); print('sha256 rebuild', hr)
for name, G in (('owner', O), ('rebuild', Rb)):
    print(name, 'nodes', len(G['nodes']), 'edges', len(G['edges']), 'forbidden', len(G['forbidden_turns']), 'grid', G.get('grid'))
ON = {n['id']: n for n in O['nodes']}; RN = {n['id']: n for n in Rb['nodes']}
OE = {e['id']: e for e in O['edges']}; RE = {e['id']: e for e in Rb['edges']}
print('node ids: owner-only', len(set(ON) - set(RN)), 'rebuild-only', len(set(RN) - set(ON)))
print('edge ids: owner-only', len(set(OE) - set(RE)), 'rebuild-only', len(set(RE) - set(OE)))
moved = {}
for n in set(ON) & set(RN):
    d = ((ON[n]['x'] - RN[n]['x']) ** 2 + (ON[n]['y'] - RN[n]['y']) ** 2) ** 0.5
    if d > 0.01: moved[n] = d
same = {n for n in set(ON) & set(RN) if n not in moved}
mx_same = max((((ON[n]['x'] - RN[n]['x']) ** 2 + (ON[n]['y'] - RN[n]['y']) ** 2) ** 0.5 for n in same), default=0)
md = sorted(moved.values())
print('common nodes', len(set(ON) & set(RN)), 'moved > 0.01 m', len(moved), 'max offset among unmoved %.3e m' % mx_same,
      'moved min/median/max %.3f/%.3f/%.3f m' % (md[0], md[len(md) // 2], md[-1]) if md else '')
FIELDS = ('u', 'v', 'travel_ticks', 'direction_evidence', 'reverse_edge', 'source_way')
def fdiff(a, b):
    d = [f for f in FIELDS if a.get(f) != b.get(f)]
    sa, sb = a['segments'], b['segments']
    worst = 0.0
    if len(sa) != len(sb) or any(x['cell'] != y['cell'] for x, y in zip(sa, sb)): d.append('segments_cells')
    else:
        worst = max((max(abs(x['start'] - y['start']), abs(x['end'] - y['end'])) for x, y in zip(sa, sb)), default=0.0)
        if worst > 1e-9: d.append('segments_frac>1e-9')
    return d, worst
common = set(OE) & set(RE)
allc, fixed = collections.Counter(), collections.Counter(); ex = []; worst_fixed = 0.0; nfixed = 0
for e in common:
    d, w = fdiff(OE[e], RE[e])
    for f in d: allc[f] += 1
    if OE[e]['u'] in same and OE[e]['v'] in same:
        nfixed += 1; worst_fixed = max(worst_fixed, w)
        for f in d: fixed[f] += 1
        if d and len(ex) < 10: ex.append((e, d, '%.3e' % w))
print('common edges', len(common), 'field diffs (any endpoint state)', dict(allc))
print('common edges with both endpoints unmoved', nfixed, 'field diffs', dict(fixed), 'max fraction diff %.3e' % worst_fixed)
for x in ex: print('   ', x)
def deadend(G):
    nb = collections.defaultdict(set)
    for e in G['edges']: nb[e['u']].add(e['v']); nb[e['v']].add(e['u'])
    return {n for n, s in nb.items() if len(s) == 1}
for name, G in (('owner', O), ('rebuild', Rb)):
    w = {n['id'] for n in G['nodes'] if n.get('waitable')}; de = deadend(G)
    E = {e['id']: e for e in G['edges']}
    U = {tuple(p) for p in G['forbidden_turns'] if p[0].rsplit(':', 1)[0] == p[1].rsplit(':', 1)[0]}
    uat = sum(E[p[0]]['v'] in de for p in U)
    print(name, 'waitable', len(w), 'dead-ends', len(de), 'equal', w == de, '| U-turn pairs', len(U), 'banned at a dead-end head (should be 0)', uat)
