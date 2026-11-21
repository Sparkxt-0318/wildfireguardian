"""Step-2 check (rule fixed in STEP1_RESULT.md): inside each current window, widened-graph edges with both ends inside the
window equal the step-1 graph (cells mapped to absolute col,row; fractions 1e-9; node x/y identical)."""
import json, sys
from pyproj import Transformer
wide, area = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
lo0, lo1, la0, la1 = area['lonlat_box']
g = wide['grid']; t = Transformer.from_crs('EPSG:5179', 'EPSG:4326', always_xy=True)
corners = [t.transform(g['x0'] + i * g['width'] * 375, g['y0'] + j * g['height'] * 375) for i in (0, 1) for j in (0, 1)]
# densify the grid outline to be safe
edge_pts = [t.transform(g['x0'] + f * g['width'] * 375, g['y0'] + s * g['height'] * 375) for f in [k / 50 for k in range(51)] for s in (0, 1)] + \
           [t.transform(g['x0'] + s * g['width'] * 375, g['y0'] + f * g['height'] * 375) for f in [k / 50 for k in range(51)] for s in (0, 1)]
print('grid outline inside extract lon/lat box:', all(lo0 <= x <= lo1 and la0 <= y <= la1 for x, y in edge_pts))
WN = {n['id']: n for n in wide['nodes']}; WE = {e['id']: e for e in wide['edges']}
def absseg(segs, gr):
    return [((s['cell'] % gr['width']) + round((gr['x0'] - 1080000) / 375), (s['cell'] // gr['width']) + round((gr['y0'] - 1810500) / 375), s['start'], s['end']) for s in segs]
ok_all = True
for f, name in zip(sys.argv[3::1][::2], sys.argv[4::2]):
    s1 = json.load(open(f)); gr = s1['grid']
    X0, Y0, X1, Y1 = gr['x0'], gr['y0'], gr['x0'] + gr['width'] * 375, gr['y0'] + gr['height'] * 375
    inside = lambda n: n in WN and X0 <= WN[n]['x'] < X1 and Y0 <= WN[n]['y'] < Y1
    wsub = {e: v for e, v in WE.items() if inside(v['u']) and inside(v['v'])}
    S1E = {e['id']: e for e in s1['edges']}; S1N = {n['id']: n for n in s1['nodes']}
    miss, extra = set(S1E) - set(wsub), set(wsub) - set(S1E)
    bad = []
    for e in set(S1E) & set(wsub):
        a, b = S1E[e], wsub[e]
        if any(a[k] != b[k] for k in ('u', 'v', 'travel_ticks', 'direction_evidence', 'source_way')):
            bad.append((e, 'field')); continue
        if b['reverse_edge'] in wsub and a['reverse_edge'] != b['reverse_edge']:
            bad.append((e, 'reverse')); continue
        sa, sb = absseg(a['segments'], gr), absseg(b['segments'], g)
        if len(sa) != len(sb) or any(p[0] != q[0] or p[1] != q[1] or abs(p[2] - q[2]) > 1e-9 or abs(p[3] - q[3]) > 1e-9 for p, q in zip(sa, sb)):
            bad.append((e, 'segments'))
    xy = [n for n in S1N if n in WN and (S1N[n]['x'] != WN[n]['x'] or S1N[n]['y'] != WN[n]['y'])]
    nmiss = [n for n in S1N if n not in WN]
    ok = not (miss or extra or bad or xy or nmiss); ok_all &= ok
    wsubn = {x for e in wsub.values() for x in (e['u'], e['v'])}
    print('%s: step-1 edges %d, widened in-window edges %d, missing %d, extra %d, field/segment diffs %d, node xy diffs %d, nodes absent %d -> %s'
          % (name, len(S1E), len(wsub), len(miss), len(extra), len(bad), len(xy), len(nmiss), 'PASS' if ok else 'FAIL'), sorted(miss)[:3], sorted(extra)[:3], bad[:3])
    w1 = sum(S1N[n]['waitable'] for n in S1N); w2 = sum(WN[n]['waitable'] for n in wsubn)
    print('   waitable in window: step-1 %d, widened %d (boundary effect, reported only)' % (w1, w2))
win = set()
for f in sys.argv[3::2]:
    gr = json.load(open(f))['grid']
    win |= {n for n, v in WN.items() if gr['x0'] <= v['x'] < gr['x0'] + gr['width'] * 375 and gr['y0'] <= v['y'] < gr['y0'] + gr['height'] * 375}
print('widened graph: nodes %d (outside both windows %d), edges %d, forbidden %d, waitable %d, distinct ways %d'
      % (len(WN), len(set(WN) - win), len(WE), len(wide['forbidden_turns']), sum(n['waitable'] for n in WN.values()), len({e['source_way'] for e in WE.values()})))
print('STEP 2:', 'PASS' if ok_all else 'FAIL')
