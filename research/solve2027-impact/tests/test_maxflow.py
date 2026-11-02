"""Road-redundancy max-flow (path A) on small graphs with hand-computed answers, and a seeded property test against
networkx on random graphs with random forbidden turns."""
import json
import random

import networkx as nx
import pytest

from wfg_impact.maxflow import RedundancySolver, RoadGraph


def make_graph(tmp_path, edges, forbidden=(), name='g'):
    nodes = sorted({u for u, v, _ in edges} | {v for u, v, _ in edges})
    g = {'revision': name, 'crs': 'EPSG:5179', 'grid': {},
         'nodes': [{'id': n, 'x': float(i), 'y': 0.0} for i, n in enumerate(nodes)],
         'edges': [{'id': eid, 'u': u, 'v': v, 'travel_ticks': 1, 'source_way': 1} for u, v, eid in edges],
         'forbidden_turns': [list(t) for t in forbidden]}
    p = tmp_path / f'{name}.json'
    p.write_text(json.dumps(g))
    graph = RoadGraph(p)
    return graph, RedundancySolver(graph)


def q(graph, solver, origin, dests):
    o, d = graph.node_index[origin], [graph.node_index[x] for x in dests]
    ta, cut = solver.turn_aware(o, d)
    return ta, solver.plain(o, d), cut


def test_two_disjoint_routes(tmp_path):
    g, s = make_graph(tmp_path, [('s', 'a', 'e1'), ('a', 't', 'e2'), ('s', 'b', 'e3'), ('b', 't', 'e4')])
    assert q(g, s, 's', ['t'])[:2] == (2, 2)


def test_bridge_away_from_the_entry_node(tmp_path):
    g, s = make_graph(tmp_path, [('s', 'a1', 'e1'), ('s', 'a2', 'e2'), ('a1', 'a', 'e3'), ('a2', 'a', 'e4'),
                                 ('a', 'b', 'e5'), ('b', 't', 'e6')])
    ta, pl, cut = q(g, s, 's', ['t'])
    assert (ta, pl) == (1, 1)
    assert cut == ['e5']                       # source-side minimum cut: the bridge, not an edge at the entry node


def test_forbidden_turn_removes_a_route(tmp_path):
    edges = [('s', 'x', 'e1'), ('x', 't', 'e3'), ('s', 'y', 'e2'), ('y', 't', 'e4')]
    g, s = make_graph(tmp_path, edges, forbidden=[('e2', 'e4')])
    ta, pl, cut = q(g, s, 's', ['t'])
    assert (ta, pl) == (1, 2)


def test_dead_end_spur_needs_a_u_turn_and_shares_the_exit(tmp_path):
    # s sits between a dead end d and a junction j; leaving towards d requires the dead-end U-turn and then the same
    # edge s->j as the direct route, so only one edge-disjoint legal walk exists; the cut is the edge s->j.
    edges = [('s', 'd', 'f1'), ('d', 's', 'r1'), ('s', 'j', 'f2'), ('j', 's', 'r2'), ('j', 't', 'f3'), ('t', 'j', 'r3')]
    forbidden = [('r2', 'f2'), ('f3', 'r3')]    # U-turns at the non-dead-end nodes; the U-turn at d is allowed
    g, s = make_graph(tmp_path, edges, forbidden)
    ta, pl, cut = q(g, s, 's', ['t'])
    assert (ta, pl) == (1, 1) and cut == ['f2']
    assert all(g.eu[g.edge_index[e]] == g.node_index['s'] for e in cut)


def test_any_of_several_destinations(tmp_path):
    g, s = make_graph(tmp_path, [('s', 'a', 'e1'), ('a', 't1', 'e2'), ('s', 'b', 'e3'), ('b', 't2', 'e4')])
    assert q(g, s, 's', ['t1', 't2'])[:2] == (2, 2)
    assert q(g, s, 's', ['t1'])[:2] == (1, 1)


def test_queries_do_not_leak_state(tmp_path):
    g, s = make_graph(tmp_path, [('s', 'a', 'e1'), ('a', 't', 'e2'), ('s', 'b', 'e3'), ('b', 't', 'e4'),
                                 ('t', 's', 'e5')])
    first = [q(g, s, o, d)[:2] for o, d in [('s', ['t']), ('a', ['t']), ('t', ['s']), ('s', ['t'])]]
    again = [q(g, s, o, d)[:2] for o, d in [('s', ['t']), ('t', ['s']), ('a', ['t']), ('s', ['t'])]]
    assert first[0] == first[3] == again[0] == again[3] == (2, 2)
    assert first[1] == again[2] and first[2] == again[1]


def _nx_plain(edges, origin, dests):
    G = nx.DiGraph()
    for u, v, _ in edges:
        G.add_edge(u, v, capacity=1)
    G.add_node('T*')
    for d in dests:
        G.add_edge(d, 'T*')
    return nx.maximum_flow_value(G, origin, 'T*') if origin in G else 0


def _nx_turn_aware(edges, forbidden, origin, dests):
    L = nx.DiGraph()
    by_head, by_tail = {}, {}
    for u, v, e in edges:
        L.add_edge(('i', e), ('o', e), capacity=1)
        by_tail.setdefault(u, []).append(e)
        by_head.setdefault(v, []).append(e)
    for u, v, a in edges:
        for b in by_tail.get(v, []):
            if (a, b) not in forbidden:
                L.add_edge(('o', a), ('i', b))
    L.add_nodes_from(['S*', 'T*'])
    for b in by_tail.get(origin, []):
        L.add_edge('S*', ('i', b))
    for d in dests:
        for a in by_head.get(d, []):
            L.add_edge(('o', a), 'T*')
    return nx.maximum_flow_value(L, 'S*', 'T*')


@pytest.mark.parametrize('seed', range(60))
def test_matches_networkx_on_random_graphs(tmp_path, seed):
    rng = random.Random(seed)
    n = rng.randint(4, 12)
    names = [f'n{i}' for i in range(n)]
    pairs = {(rng.choice(names), rng.choice(names)) for _ in range(rng.randint(n, 4 * n))}
    edges = [(u, v, f'e{k}') for k, (u, v) in enumerate(sorted(p for p in pairs if p[0] != p[1]))]
    if not edges:
        return
    turns = [(a, b) for (_, v, a) in edges for (u2, _, b) in edges if u2 == v]
    forbidden = {t for t in turns if rng.random() < 0.3}
    g, s = make_graph(tmp_path, edges, forbidden, name=f'r{seed}')
    for _ in range(5):
        origin = rng.choice([u for u, _, _ in edges])
        dests = rng.sample([x for x in g.node_ids if x != origin], k=min(3, len(g.node_ids) - 1))
        ta, pl, cut = q(g, s, origin, dests)
        assert pl == _nx_plain(edges, origin, dests)
        assert ta == _nx_turn_aware(edges, forbidden, origin, dests)
        assert ta <= pl and len(cut) == ta     # a minimum cut has exactly max-flow many edges
