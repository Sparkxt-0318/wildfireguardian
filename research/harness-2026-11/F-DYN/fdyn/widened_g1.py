"""WIDENED_GRAPH_RULE.md §8(iii)2: the old graph G1 and its eligible sub-instances G1' and G1''.

G1   = the rebuilt step-1 graph (same 2025-01-01 snapshot), re-indexed onto the KFS_01 export grid (fdyn/regrid_graph.py)
       so that it reads the v3.7 `/2` packets; its own waitable flags.
G1'  = G1 restricted so that it is, by construction, a sub-instance of the widened instance:
       (a) only edges identical in both graphs (id, u, v, direction, ticks, segments in absolute cells);
       (b) edges touching a padding cell under the closed rule dropped; wait nodes touching one lose waitable; origins
           and destinations touching one are excluded (listed);
       (c) forbidden turns = union of G1's and the widened graph's on the remaining edges;
       (d) G1's waitable flags otherwise.
G1'' = G1' without step (b) (for P4-open).
Touching a padding cell under the closed rule = the closed bounding box of the edge (or the node point) reaches the
export-grid boundary line (all G1 geometry lies inside the export grid).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from fdyn.regrid_graph import FULL, regrid

X0, Y0 = FULL['x0'], FULL['y0']
X1, Y1 = X0 + FULL['width'] * FULL['resolution'], Y0 + FULL['height'] * FULL['resolution']
PAD = 14


def touches_border_box(xmin, xmax, ymin, ymax) -> bool:
    return xmin <= X0 or xmax >= X1 or ymin <= Y0 or ymax >= Y1


def absseg(segs, grid):
    ox, oy = round((grid['x0'] - (X0 - PAD * 375.0)) / 375.0), round((grid['y0'] - (Y0 - PAD * 375.0)) / 375.0)
    return [((s['cell'] % grid['width']) + ox, (s['cell'] // grid['width']) + oy, s['start'], s['end']) for s in segs]


def same_edge(a, b, ga, gb) -> bool:
    if any(a[k] != b[k] for k in ('u', 'v', 'travel_ticks', 'direction_evidence')):
        return False
    sa, sb = absseg(a['segments'], ga), absseg(b['segments'], gb)
    return len(sa) == len(sb) and all(p[0] == q[0] and p[1] == q[1] and abs(p[2] - q[2]) <= 1e-9 and abs(p[3] - q[3]) <= 1e-9
                                      for p, q in zip(sa, sb))


def build(step1: dict, widened: dict) -> dict:
    """Returns {'G1': graph, 'G1p': graph, 'G1pp': graph, 'excluded_points': set of node ids touching padding, 'report': {...}}."""
    g1 = regrid(step1)
    g1['revision'] = step1['revision'] + '+G1-exportgrid'
    N = {n['id']: n for n in g1['nodes']}
    WE = {e['id']: e for e in widened['edges']}
    WF = {tuple(t) for t in widened['forbidden_turns']}
    ident = {e['id'] for e in g1['edges'] if e['id'] in WE and same_edge(e, WE[e['id']], g1['grid'], widened['grid'])}

    def edge_touches(e):
        a, b = N[e['u']], N[e['v']]
        return touches_border_box(min(a['x'], b['x']), max(a['x'], b['x']), min(a['y'], b['y']), max(a['y'], b['y']))

    node_touch = {k for k, n in N.items() if touches_border_box(n['x'], n['x'], n['y'], n['y'])}
    edge_touch = {e['id'] for e in g1['edges'] if edge_touches(e)}

    def restrict(drop_padding: bool):
        g = copy.deepcopy(g1)
        keep = {e['id'] for e in g['edges'] if e['id'] in ident and not (drop_padding and e['id'] in edge_touch)}
        g['edges'] = [e for e in g['edges'] if e['id'] in keep]
        own = {tuple(t) for t in g['forbidden_turns'] if t[0] in keep and t[1] in keep}
        add = {t for t in WF if t[0] in keep and t[1] in keep} - own
        g['forbidden_turns'] = [list(t) for t in sorted(own | add)]
        for e in g['edges']:                      # a reverse edge that was dropped is no longer referenced
            if e.get('reverse_edge') not in keep:
                e['reverse_edge'] = None
        used = {x for e in g['edges'] for x in (e['u'], e['v'])}
        g['nodes'] = [n for n in g['nodes'] if n['id'] in used]
        if drop_padding:
            for n in g['nodes']:
                if n['id'] in node_touch:
                    n['waitable'] = False
        g['revision'] = g1['revision'] + ('+G1p' if drop_padding else '+G1pp')
        return g, len(add)

    g1p, add_p = restrict(True)
    g1pp, add_pp = restrict(False)
    return {'G1': g1, 'G1p': g1p, 'G1pp': g1pp, 'node_touch': node_touch,
            'report': {'g1_edges': len(g1['edges']), 'identical_edges': len(ident),
                       'edges_touching_padding': len(edge_touch), 'nodes_touching_padding': len(node_touch),
                       'G1p_edges': len(g1p['edges']), 'G1pp_edges': len(g1pp['edges']),
                       'forbidden_turns_added_G1p': add_p, 'forbidden_turns_added_G1pp': add_pp}}


def write(g: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(g, separators=(',', ':')))
    return path
