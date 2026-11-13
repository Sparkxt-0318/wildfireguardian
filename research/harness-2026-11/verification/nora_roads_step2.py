"""Nora (verifier), roads step 2: in each current window, widened-graph edges with both ends inside == step-1 graph.
Independent of Daniel's compare_step2.py. Stdlib only.
  python3 -I nora_roads_step2.py WIDENED.json STEP1_UA.json STEP1_YD.json
Checks: sha256 of inputs; window offsets are whole cells; edge-id sets both ways; all fields (u, v, travel_ticks,
direction_evidence, source_way, reverse_edge where the reverse is also inside); segments with cells mapped to absolute
(col, row) (fractions 1e-9); node x/y bit-identical; plus a geometry self-check on BOTH graphs: the cell containing u's
x/y equals the edge's first segment cell, and the cell containing v's x/y equals its last (catches a wrong row/col
convention in either graph)."""
import hashlib, json, sys
def load(p):
    b = open(p, 'rb').read(); return hashlib.sha256(b).hexdigest(), json.loads(b)
hw, W = load(sys.argv[1]); print('sha256 widened', hw)
gw = W['grid']; R = gw['resolution']; print('widened grid', gw)
WN = {n['id']: n for n in W['nodes']}; WE = {e['id']: e for e in W['edges']}
def cell_of(x, y, g):
    c, r = int((x - g['x0']) // g['resolution']), int((y - g['y0']) // g['resolution'])
    return r * g['width'] + c if 0 <= c < g['width'] and 0 <= r < g['height'] else None
def geomcheck(G, N, name):
    bad = 0; n = 0
    for e in G['edges']:
        s = e['segments']
        if not s: continue
        n += 1
        a, b = N[e['u']], N[e['v']]
        cu, cv = cell_of(a['x'], a['y'], G['grid']), cell_of(b['x'], b['y'], G['grid'])
        if (cu is not None and s[0]['start'] == 0 and cu != s[0]['cell']) or (cv is not None and s[-1]['end'] == 1 and cv != s[-1]['cell']):
            bad += 1
    print('  geometry self-check %s: edges %d, endpoint-cell mismatches %d' % (name, n, bad))
geomcheck(W, WN, 'widened')
for path in sys.argv[2:]:
    h1, G = load(path); g = G['grid']; print('== step-1', path.split('/')[-1], 'sha256', h1, 'grid', g)
    dc, dr = (g['x0'] - gw['x0']) / R, (g['y0'] - gw['y0']) / R
    print('  offset cells col %s row %s (whole: %s)' % (dc, dr, dc == int(dc) and dr == int(dr))); dc, dr = int(dc), int(dr)
    N1 = {n['id']: n for n in G['nodes']}; E1 = {e['id']: e for e in G['edges']}
    geomcheck(G, N1, 'step-1')
    X0, Y0, X1, Y1 = g['x0'], g['y0'], g['x0'] + g['width'] * R, g['y0'] + g['height'] * R
    ins = lambda nid: X0 <= WN[nid]['x'] < X1 and Y0 <= WN[nid]['y'] < Y1
    sub = {i: e for i, e in WE.items() if ins(e['u']) and ins(e['v'])}
    miss, extra = set(E1) - set(sub), set(sub) - set(E1)
    def absc(c, gg, oc, orow): return (c % gg['width'] + oc, c // gg['width'] + orow)
    diffs = {}
    for i in set(E1) & set(sub):
        a, b = E1[i], sub[i]; d = [f for f in ('u', 'v', 'travel_ticks', 'direction_evidence', 'source_way') if a.get(f) != b.get(f)]
        if b['reverse_edge'] in sub and a.get('reverse_edge') != b.get('reverse_edge'): d.append('reverse_edge')
        sa = [(absc(s['cell'], g, dc, dr), s['start'], s['end']) for s in a['segments']]
        sb = [(absc(s['cell'], gw, 0, 0), s['start'], s['end']) for s in b['segments']]
        if len(sa) != len(sb) or any(p[0] != q[0] or abs(p[1] - q[1]) > 1e-9 or abs(p[2] - q[2]) > 1e-9 for p, q in zip(sa, sb)): d.append('segments')
        if d: diffs[i] = d
    xy = sum(1 for n in N1 if n not in WN or (N1[n]['x'], N1[n]['y']) != (WN[n]['x'], WN[n]['y']))
    print('  step-1 edges %d | widened in-window edges %d | missing %d extra %d | field diffs %d | node xy diffs or absent %d'
          % (len(E1), len(sub), len(miss), len(extra), len(diffs), xy), sorted(miss)[:3], sorted(extra)[:3], list(diffs.items())[:3])
    win_nodes = {n for n in WN if ins(n)}
    print('  in-window nodes: widened %d, step-1 %d; waitable in window: widened %d, step-1 %d'
          % (len(win_nodes), len(N1), sum(WN[n]['waitable'] for n in win_nodes), sum(n['waitable'] for n in N1.values())))
