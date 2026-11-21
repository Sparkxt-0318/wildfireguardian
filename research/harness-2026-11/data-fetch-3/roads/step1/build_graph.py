"""Build an owner-schema road graph from the area extract (extract_area.py output) for one grid window.

usage: build_graph.py AREA.json OUT.json --grid x0 y0 res width height --region NAME --label TEXT
Recipe (ROAD_RULE.md, ACCEPTANCE_STEP1.md, addenda 1-2), fixed before any comparison:
  ways: highway in CLASSES; excluded if access/vehicle/motor_vehicle/motorcar in {private,no}, any '*:conditional' key,
        or an unsupported oneway value (not yes/true/1/-1/no/false/0)
  nodes: OSM nodes with projected (EPSG:4326->5179, pyproj always_xy) x in [x0, x0+w*res), y in [y0, y0+h*res)
  edges: for each k with refs[k] and refs[k+1] both inside: id w<way>:s<k>:f (refs[k]->refs[k+1]) and/or :r
         direction: oneway yes/true/1 -> f only (explicit_one_way); -1 -> r only (explicit_one_way);
         no/false/0 -> both (explicit_two_way); missing + highway=motorway or junction=roundabout/circular -> f only
         (tag_semantics_implicit_one_way); otherwise both (missing_oneway_assumed_two_way)
  travel_ticks = ceil(chord_m / (40 km/h)), dt = 1 s; segments split at 375 m cell lines, cell = row*width + col (row 0 south)
  waitable = node has exactly 1 distinct neighbour; forbidden_turns = (e, reverse(e)) where head(e) is not a dead end,
  plus OSM restriction relations (no_* forbids from->to at via node; only_* forbids every other out edge from that from edge)
  nodes kept = endpoints of edges only.
"""
import argparse, json, math
from pyproj import Transformer
import pyproj

CLASSES = {'living_street', 'motorway', 'motorway_link', 'primary', 'primary_link', 'residential', 'secondary',
           'secondary_link', 'service', 'tertiary', 'tertiary_link', 'trunk', 'trunk_link', 'unclassified'}
NOACC = {'private', 'no'}
SPEED = 40000 / 3600.0


def excluded(t):
    if any(t.get(k) in NOACC for k in ('access', 'vehicle', 'motor_vehicle', 'motorcar')):
        return 'no_access'
    if any(k.endswith(':conditional') for k in t):
        return 'conditional'
    if 'oneway' in t and t['oneway'] not in ('yes', 'true', '1', '-1', 'no', 'false', '0'):
        return 'unsupported_oneway'
    return None


def direction(t):
    o = t.get('oneway')
    if o in ('yes', 'true', '1'):
        return ('f',), 'explicit_one_way'
    if o == '-1':
        return ('r',), 'explicit_one_way'
    if o in ('no', 'false', '0'):
        return ('f', 'r'), 'explicit_two_way'
    if t.get('highway') == 'motorway' or t.get('junction') in ('roundabout', 'circular'):
        return ('f',), 'tag_semantics_implicit_one_way'
    return ('f', 'r'), 'missing_oneway_assumed_two_way'


def segments(p, q, g):
    x0, y0, res, w, h = g
    ts = {0.0, 1.0}
    for a, b, o in ((p[0], q[0], x0), (p[1], q[1], y0)):
        if a != b:
            lo, hi = sorted((a, b))
            i = math.floor((lo - o) / res) + 1
            while o + i * res < hi:
                ts.add((o + i * res - a) / (b - a)); i += 1
    ts = sorted(t for t in ts if 0.0 <= t <= 1.0)
    out = []
    for s, e in zip(ts, ts[1:]):
        if e <= s:
            continue
        m = (s + e) / 2
        x, y = p[0] + m * (q[0] - p[0]), p[1] + m * (q[1] - p[1])
        col, row = math.floor((x - x0) / res), math.floor((y - y0) / res)
        out.append({'cell': row * w + col, 'start': s, 'end': e})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('area'); ap.add_argument('out')
    ap.add_argument('--grid', nargs=5, type=float, required=True)
    ap.add_argument('--region', required=True); ap.add_argument('--label', required=True)
    a = ap.parse_args()
    x0, y0, res, w, h = a.grid; w, h = int(w), int(h); G = (x0, y0, res, w, h)
    A = json.load(open(a.area))
    tr = Transformer.from_crs('EPSG:4326', 'EPSG:5179', always_xy=True)
    xy = {}
    for k, (lo, la) in A['nodes'].items():
        x, y = tr.transform(lo, la)
        if x0 <= x < x0 + w * res and y0 <= y < y0 + h * res:
            xy[int(k)] = (x, y)
    edges, excl = {}, {}
    for wid_s, wy in A['ways'].items():
        t = wy['tags']
        if t.get('highway') not in CLASSES:
            continue
        r = wy['refs']
        if not any(n in xy for n in r):
            continue
        why = excluded(t)
        if why:
            excl[why] = excl.get(why, 0) + 1; continue
        dirs, ev = direction(t)
        wid = int(wid_s)
        for k in range(len(r) - 1):
            u, v = r[k], r[k + 1]
            if u not in xy or v not in xy:
                continue
            p, q = xy[u], xy[v]
            ticks = math.ceil(math.hypot(q[0] - p[0], q[1] - p[1]) / SPEED)
            ids = {d: 'w%d:s%d:%s' % (wid, k, d) for d in dirs}
            for d in dirs:
                a_, b_ = (u, v) if d == 'f' else (v, u)
                pa, pb = (p, q) if d == 'f' else (q, p)
                other = 'r' if d == 'f' else 'f'
                edges[ids[d]] = {'id': ids[d], 'u': 'osm:%d' % a_, 'v': 'osm:%d' % b_, 'travel_ticks': ticks,
                                 'reverse_edge': ids.get(other), 'segments': segments(pa, pb, G),
                                 'source_way': wid, 'direction_evidence': ev}
    nb = {}
    for e in edges.values():
        nb.setdefault(e['u'], set()).add(e['v']); nb.setdefault(e['v'], set()).add(e['u'])
    dead = {n for n, s in nb.items() if len(s) == 1}
    nodes = [{'id': n, 'x': xy[int(n[4:])][0], 'y': xy[int(n[4:])][1], 'waitable': n in dead} for n in sorted(nb)]
    ft = set()
    for e in edges.values():
        if e['reverse_edge'] and e['v'] not in dead:
            ft.add((e['id'], e['reverse_edge']))
    out_by_node, in_by = {}, {}
    for e in edges.values():
        out_by_node.setdefault(e['u'], []).append(e); in_by.setdefault(e['v'], []).append(e)
    rel_stats = {'used': 0, 'skipped': 0}
    for rid, rel in A['relations'].items():
        rt = rel['tags'].get('restriction') or next((v for k, v in rel['tags'].items() if k.startswith('restriction:')), '')
        frm = [m[1] for m in rel['members'] if m[0] == 'w' and m[2] == 'from']
        to = [m[1] for m in rel['members'] if m[0] == 'w' and m[2] == 'to']
        via = [m[1] for m in rel['members'] if m[0] == 'n' and m[2] == 'via']
        if len(frm) != 1 or len(to) != 1 or len(via) != 1 or not rt[:3] in ('no_', 'onl'):
            rel_stats['skipped'] += 1; continue
        vn = 'osm:%d' % via[0]
        ins = [e for e in in_by.get(vn, []) if e['source_way'] == frm[0]]
        outs = out_by_node.get(vn, [])
        if not ins:
            rel_stats['skipped'] += 1; continue
        rel_stats['used'] += 1
        for ei in ins:
            for eo in outs:
                if (rt.startswith('no_') and eo['source_way'] == to[0]) or (rt.startswith('only_') and eo['source_way'] != to[0]):
                    ft.add((ei['id'], eo['id']))
    g = {'revision': '%s-osm-20250101-owner-pbf-9b67fc95-rebuild' % a.region, 'crs': 'EPSG:5179',
         'grid': {'x0': x0, 'y0': y0, 'resolution': res, 'width': w, 'height': h},
         'nodes': nodes, 'edges': sorted(edges.values(), key=lambda e: e['id']),
         'forbidden_turns': sorted(list(p) for p in ft), 'mid_edge_reversal': False,
         'provenance': {'source': 'OpenStreetMap contributors; Geofabrik south-korea extract, replication timestamp '
                                  '2025-01-01T21:21:00Z (owner-supplied copy, sha256 9b67fc951d535639b2a12e96a0ff069943d6da4d75883e42d377e6f76c7483ab; '
                                  'not compared with the Geofabrik published checksum)',
                        'label': a.label, 'license': 'ODbL; https://www.openstreetmap.org/copyright',
                        'recipe': 'data-fetch-3/roads ROAD_RULE.md + ACCEPTANCE_STEP1.md + addenda 1-2; build_graph.py',
                        'pyproj': pyproj.__version__, 'excluded_way_counts': excl, 'restriction_relations': rel_stats,
                        'waitable_rule': 'exactly 1 distinct neighbour (addendum 1; owner rule undocumented)'}}
    json.dump(g, open(a.out, 'w'))
    print(a.region, 'nodes', len(nodes), 'edges', len(edges), 'forbidden', len(ft), 'waitable', len(dead), 'excluded', excl, rel_stats)


if __name__ == '__main__':
    main()
