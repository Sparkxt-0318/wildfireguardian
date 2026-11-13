"""Waitable (dead-end) set per current window: step-1 graph vs widened graph, by OSM node id.
usage: waitable_delta.py WIDE.json OUT.json STEP1_A.json NAME_A [STEP1_B.json NAME_B ...]"""
import json, sys
wide = json.load(open(sys.argv[1])); WN = {n['id']: n for n in wide['nodes']}
out = {'widened_graph_sha256_note': 'see MANIFEST.json kfs01_grid5km.json', 'rule': 'waitable = exactly 1 distinct neighbour (addendum 1), computed on each graph', 'windows': {}}
for f, name in zip(sys.argv[3::2], sys.argv[4::2]):
    s1 = json.load(open(f)); g = s1['grid']
    X0, Y0, X1, Y1 = g['x0'], g['y0'], g['x0'] + g['width'] * g['resolution'], g['y0'] + g['height'] * g['resolution']
    old = {n['id'] for n in s1['nodes'] if n['waitable']}
    inwin = {i for i, n in WN.items() if X0 <= n['x'] < X1 and Y0 <= n['y'] < Y1}
    assert {n['id'] for n in s1['nodes']} <= inwin
    new = {i for i in inwin if WN[i]['waitable']}
    key = lambda s: sorted(s, key=lambda x: int(x[4:]))
    d = {'step1_waitable': len(old), 'widened_waitable_in_window': len(new), 'unchanged': len(old & new),
         'removed': key(old - new), 'added': key(new - old),
         'in_window_nodes_step1': len(s1['nodes']), 'in_window_nodes_widened': len(inwin)}
    out['windows'][name] = d
    print(name, {k: (len(v) if isinstance(v, list) else v) for k, v in d.items()})
json.dump(out, open(sys.argv[2], 'w'), indent=1)
