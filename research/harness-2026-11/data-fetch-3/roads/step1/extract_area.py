"""Extract from the pbf: nodes inside a lon/lat box, all highway ways with >=1 such node (full node lists + tags),
and turn-restriction relations whose members include any such way. Output JSON (derived, scratch only)."""
import json, sys, osmium
from pyproj import Transformer
pbf, out = sys.argv[1], sys.argv[2]
X0, X1, Y0, Y1 = 1085250 - 5000, 1174125 + 5000, 1815750 - 5000, 1845375 + 5000   # export grid + 5 km (EPSG:5179)
t = Transformer.from_crs('EPSG:5179', 'EPSG:4326', always_xy=True)
cs = [t.transform(x, y) for x in (X0, X1) for y in (Y0, Y1)]
lo0, lo1 = min(c[0] for c in cs) - 0.01, max(c[0] for c in cs) + 0.01
la0, la1 = min(c[1] for c in cs) - 0.01, max(c[1] for c in cs) + 0.01
print('lonlat box', lo0, lo1, la0, la1, flush=True)
nodes, maxnode, maxway = {}, 0, 0
for n in osmium.FileProcessor(pbf, osmium.osm.NODE):
    if n.id > maxnode: maxnode = n.id
    if n.location.valid():
        lo, la = n.location.lon, n.location.lat
        if lo0 <= lo <= lo1 and la0 <= la <= la1:
            nodes[n.id] = (lo, la)
print('nodes in box', len(nodes), 'max node id', maxnode, flush=True)
ways = {}
for w in osmium.FileProcessor(pbf, osmium.osm.WAY):
    if w.id > maxway: maxway = w.id
    if 'highway' not in w.tags: continue
    refs = [r.ref for r in w.nodes]
    if any(r in nodes for r in refs):
        ways[w.id] = {'refs': refs, 'tags': {tg.k: tg.v for tg in w.tags}}
print('highway ways touching box', len(ways), 'max way id', maxway, flush=True)
rels = {}
for r in osmium.FileProcessor(pbf, osmium.osm.RELATION):
    tags = {tg.k: tg.v for tg in r.tags}
    if not tags.get('type', '').startswith('restriction'): continue
    mem = [(m.type, m.ref, m.role) for m in r.members]
    if any(m[0] == 'w' and m[1] in ways for m in mem):
        rels[r.id] = {'tags': tags, 'members': mem}
print('restriction relations', len(rels), flush=True)
need = {r for w in ways.values() for r in w['refs']}
json.dump({'box_5179': [X0, X1, Y0, Y1], 'lonlat_box': [lo0, lo1, la0, la1], 'max_node_id': maxnode, 'max_way_id': maxway,
           'nodes': {str(k): v for k, v in nodes.items() if k in need}, 'ways': {str(k): v for k, v in ways.items()},
           'relations': {str(k): v for k, v in rels.items()}}, open(out, 'w'))
print('written', out)
