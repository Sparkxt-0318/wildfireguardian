"""Step-1 comparison per ROAD_RULE_ADDENDUM_2 section 3 (A strict, B recipe on unchanged ways, C attribution).
usage: compare_step1.py OWNER_graph.json REBUILD_graph.json AREA.json REGION"""
import collections, json, re, sys

own, reb, A, region = json.load(open(sys.argv[1])), json.load(open(sys.argv[2])), json.load(open(sys.argv[3])), sys.argv[4]
MAXN, MAXW, WAYS = A['max_node_id'], A['max_way_id'], A['ways']
OE, RE_ = {e['id']: e for e in own['edges']}, {e['id']: e for e in reb['edges']}
ON, RN = {n['id']: n for n in own['nodes']}, {n['id']: n for n in reb['nodes']}
kof = lambda eid: int(re.search(r':s(\d+):', eid).group(1))
ex = lambda s, n=5: sorted(s)[:n]
P = print
P('=' * 100); P('REGION', region)
P('owner  ', own['revision'], 'nodes', len(ON), 'edges', len(OE), 'forbidden', len(own['forbidden_turns']))
P('rebuild', reb['revision'], 'nodes', len(RN), 'edges', len(RE_), 'forbidden', len(reb['forbidden_turns']))
P('pbf max node id', MAXN, 'max way id', MAXW)


def seg_eq(a, b):
    return len(a) == len(b) and all(x['cell'] == y['cell'] and abs(x['start'] - y['start']) <= 1e-9 and abs(x['end'] - y['end']) <= 1e-9
                                    for x, y in zip(a, b))


def edge_diff(o, r):
    d = []
    for f in ('u', 'v', 'travel_ticks', 'direction_evidence', 'reverse_edge'):
        if o.get(f) != r.get(f):
            d.append(f)
    if not seg_eq(o['segments'], r['segments']):
        d.append('segments')
    return d


def xy_bad(n):
    return n in ON and n in RN and (abs(ON[n]['x'] - RN[n]['x']) > 0.01 or abs(ON[n]['y'] - RN[n]['y']) > 0.01)


# ---------------- A. strict
P('\n--- A. strict (criteria 1-6 + waitable) ---')
on_only, rn_only = set(ON) - set(RN), set(RN) - set(ON)
oe_only, re_only = set(OE) - set(RE_), set(RE_) - set(OE)
common = set(OE) & set(RE_)
fieldbad = {e: edge_diff(OE[e], RE_[e]) for e in common}
fieldbad = {e: d for e, d in fieldbad.items() if d}
xybad = {n for n in set(ON) & set(RN) if xy_bad(n)}
ow = {n for n, v in ON.items() if v['waitable']}; rw = {n for n, v in RN.items() if v['waitable']}
P('1 nodes: owner-only %d, rebuild-only %d' % (len(on_only), len(rn_only)), ex(on_only), ex(rn_only))
P('2 edges: owner-only %d, rebuild-only %d' % (len(oe_only), len(re_only)), ex(oe_only), ex(re_only))
cnt = collections.Counter(f for d in fieldbad.values() for f in d)
P('2-4 common edges %d, with any field difference %d' % (len(common), len(fieldbad)), dict(cnt))
P('5 node xy > 0.01 m on common nodes:', len(xybad), ex(xybad))
P('waitable: owner %d rebuild %d; owner-only %d rebuild-only %d' % (len(ow), len(rw), len(ow - rw), len(rw - ow)))
strict = not (on_only or rn_only or oe_only or re_only or fieldbad or xybad or ow != rw)

# ---------------- B. unchanged ways
P('\n--- B. recipe-exactness on UNCHANGED ways ---')
oway = collections.defaultdict(set)
for e in OE.values():
    k = kof(e['id']); a, b = (e['u'], e['v']) if e['id'].endswith(':f') else (e['v'], e['u'])
    oway[e['source_way']].add((k, a, b))
inside = set(RN)  # not used for membership; membership below uses projected window test via rebuild nodes + owner nodes
xy_in = {}
import math
from pyproj import Transformer
tr = Transformer.from_crs('EPSG:4326', 'EPSG:5179', always_xy=True)
g = reb['grid']; X0, Y0, R, W, H = g['x0'], g['y0'], g['resolution'], g['width'], g['height']


def inwin(nid):
    if nid not in xy_in:
        p = A['nodes'].get(str(nid))
        if p is None:
            xy_in[nid] = False
        else:
            x, y = tr.transform(*p); xy_in[nid] = X0 <= x < X0 + W * R and Y0 <= y < Y0 + H * R
    return xy_in[nid]


unchanged, changed, absent = set(), set(), set()
for s, pairs in oway.items():
    w = WAYS.get(str(s))
    if w is None:
        absent.add(s); continue
    r = w['refs']
    pbfpairs = {(k, 'osm:%d' % r[k], 'osm:%d' % r[k + 1]) for k in range(len(r) - 1) if inwin(r[k]) and inwin(r[k + 1])}
    (unchanged if pbfpairs == pairs else changed).add(s)
ue_o = {e for e in OE if OE[e]['source_way'] in unchanged}
ue_r = {e for e in RE_ if RE_[e]['source_way'] in unchanged}
b_missing, b_extra = ue_o - ue_r, ue_r - ue_o
b_field = {e: fieldbad[e] for e in ue_o & ue_r if e in fieldbad}
unodes = {x for e in ue_o for x in (OE[e]['u'], OE[e]['v'])}
b_xy = {n for n in unodes if xy_bad(n)}
b_pass = not (b_missing or b_extra or b_field or b_xy)
P('owner source ways %d: unchanged %d, changed (C2) %d, absent from pbf extract %d' % (len(oway), len(unchanged), len(changed), len(absent)))
P('edges on unchanged ways: owner %d rebuild %d; missing %d extra %d field-diff %d; nodes %d xy-diff %d'
  % (len(ue_o), len(ue_r), len(b_missing), len(b_extra), len(b_field), len(unodes), len(b_xy)))
for e in ex(b_missing, 10): P('  B missing', e, OE[e]['source_way'], WAYS.get(str(OE[e]['source_way']), {}).get('tags', {}).get('highway'))
for e in ex(b_extra, 10): P('  B extra', e)
for e in ex(b_field, 10): P('  B field', e, b_field[e], 'owner', {f: OE[e].get(f) for f in b_field[e] if f != 'segments'}, 'rebuild', {f: RE_[e].get(f) for f in b_field[e] if f != 'segments'})
for n in ex(b_xy, 5): P('  B xy', n, (ON[n]['x'], ON[n]['y']), (RN[n]['x'], RN[n]['y']))
P('B RESULT:', 'PASS' if b_pass else 'FAIL', '(%d ways, %d edges)' % (len(unchanged), len(ue_o)))

# ---------------- C. attribution of remaining differences
P('\n--- C. attribution of differences outside B ---')
C = collections.defaultdict(list)


def way_cat(s, owner_side):
    if s > MAXW:
        return 'C1'
    if s in changed or s in absent:
        return 'C2'
    if not owner_side and s not in oway:
        return 'C3'
    return 'C4'


for e in oe_only - b_missing:
    C[way_cat(OE[e]['source_way'], True)].append(('edge-owner-only', e))
for e in re_only - b_extra:
    C[way_cat(RE_[e]['source_way'], False)].append(('edge-rebuild-only', e))
for e, d in fieldbad.items():
    if e in b_field:
        continue
    C[way_cat(OE[e]['source_way'], True)].append(('edge-field:' + ','.join(d), e))
inc = collections.defaultdict(set)
for E_ in (OE, RE_):
    for e in E_.values():
        inc[e['u']].add(e['source_way']); inc[e['v']].add(e['source_way'])
for side, ns in (('node-owner-only', on_only), ('node-rebuild-only', rn_only)):
    for n in ns:
        if int(n[4:]) > MAXN:
            C['C1'].append((side, n)); continue
        cats = {way_cat(s, side == 'node-owner-only') for s in inc[n]}
        C['C4' if 'C4' in cats else sorted(cats)[0] if cats else 'C4'].append((side, n))
for n in xybad - b_xy:
    cats = {way_cat(s, True) for s in inc[n]}
    C['C4' if 'C4' in cats else sorted(cats)[0]].append(('node-xy', n))
for c in ('C1', 'C2', 'C3', 'C4'):
    items = C.get(c, [])
    P(c, len(items), dict(collections.Counter(t for t, _ in items)))
    for t, i in items[: (40 if c == 'C4' else 4)]:
        P('   ', t, i)
c3ways = sorted({RE_[i]['source_way'] for t, i in C.get('C3', []) if t.startswith('edge')})
P('C3 ways (rebuild-only, not owner source ways):', len(c3ways))
tagc = collections.Counter()
for s in c3ways:
    t = WAYS[str(s)]['tags']
    tagc[(t.get('highway'), t.get('service'), t.get('access'))] += 1
for k, v in tagc.most_common(15):
    P('    highway/service/access', k, v)

# ---------------- forbidden turns
P('\n--- forbidden_turns ---')
of, rf = {tuple(p) for p in own['forbidden_turns']}, {tuple(p) for p in reb['forbidden_turns']}
isU = lambda p: p[0].rsplit(':', 1)[0] == p[1].rsplit(':', 1)[0]
ofu, rfu = {p for p in of if isU(p)}, {p for p in rf if isU(p)}
uu = {p for p in ofu if OE[p[0]]['source_way'] in unchanged}
P('U-turn pairs: owner %d rebuild %d; on unchanged ways owner %d, of which in rebuild %d' % (len(ofu), len(rfu), len(uu), len(uu & rfu)))
ofn, rfn = of - ofu, rf - rfu
P('non-U pairs: owner %d rebuild %d matched %d; owner-only %s; rebuild-only %s' % (len(ofn), len(rfn), len(ofn & rfn), ex(ofn - rfn, 10), ex(rfn - ofn, 10)))

P('\nSUMMARY %s: strict: %s; recipe on unchanged ways: %s (%d ways, %d edges); C1 %d; C2 %d; C3 %d; C4 %d'
  % (region, 'PASS' if strict else 'FAIL', 'PASS' if b_pass else 'FAIL', len(unchanged), len(ue_o),
     len(C.get('C1', [])), len(C.get('C2', [])), len(C.get('C3', [])), len(C.get('C4', []))))
