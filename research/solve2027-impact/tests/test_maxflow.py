"""Road-redundancy max-flow, common road segments and fire-free trips (path A) on small graphs with hand-computed
answers, and seeded property tests on random graphs with random forbidden turns (against networkx and against brute
force edge removal)."""
import json
import random

import networkx as nx
import pytest

from wfg_impact.maxflow import RedundancySolver, RoadGraph
from wfg_impact.trips import fastest_trips, walk_length_to_edge_end


def make_graph(tmp_path, edges, forbidden=(), name='g', ticks=None, xy=None):
    nodes = sorted({u for u, v, _ in edges} | {v for u, v, _ in edges})
    g = {'revision': name, 'crs': 'EPSG:5179', 'grid': {},
         'nodes': [{'id': n, 'x': float((xy or {}).get(n, (i, 0))[0]), 'y': float((xy or {}).get(n, (i, 0))[1])}
                   for i, n in enumerate(nodes)],
         'edges': [{'id': eid, 'u': u, 'v': v, 'travel_ticks': (ticks or {}).get(eid, 1), 'source_way': 1}
                   for u, v, eid in edges],
         'forbidden_turns': [list(t) for t in forbidden]}
    p = tmp_path / f'{name}.json'
    p.write_text(json.dumps(g))
    graph = RoadGraph(p)
    return graph, RedundancySolver(graph)


def q(graph, solver, origin, dests):
    o, d = graph.node_index[origin], [graph.node_index[x] for x in dests]
    ta, cut, _ = solver.turn_aware(o, d)
    return ta, solver.plain(o, d), cut


def common_ids(graph, solver, origin, dests):
    o, d = graph.node_index[origin], [graph.node_index[x] for x in dests]
    ta, _, common = solver.turn_aware(o, d, chain=True)
    return ta, None if common is None else [graph.edge_ids[e] for e in common]


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


# ------------------------------------------------------------------------------------------------ common road segments

def test_common_segments_are_every_edge_on_all_walks_in_walking_order(tmp_path):
    g, s = make_graph(tmp_path, [('s', 'a1', 'e1'), ('s', 'a2', 'e2'), ('a1', 'a', 'e3'), ('a2', 'a', 'e4'),
                                 ('a', 'b', 'e5'), ('b', 't', 'e6')])
    assert common_ids(g, s, 's', ['t']) == (1, ['e5', 'e6'])
    g, s = make_graph(tmp_path, [('s', 'a', 'e1'), ('a', 't', 'e2'), ('s', 'b', 'e3'), ('b', 't', 'e4')], name='g2')
    assert common_ids(g, s, 's', ['t']) == (2, None)          # only asked for (and defined at) max-flow 1


def test_common_segments_respect_forbidden_turns(tmp_path):
    # two parallel branches, but the turn from the lower branch into the exit is forbidden: every legal walk drives
    # the upper branch, so its edges are common although the plain graph has an alternative
    edges = [('s', 'x', 'e1'), ('x', 'j', 'e2'), ('s', 'y', 'e3'), ('y', 'j', 'e4'), ('j', 't', 'e5')]
    g, s = make_graph(tmp_path, edges, forbidden=[('e4', 'e5')])
    assert common_ids(g, s, 's', ['t']) == (1, ['e1', 'e2', 'e5'])


def _without_edge(edges, forbidden, drop):
    return [e for e in edges if e[2] != drop], {t for t in forbidden if drop not in t}


def _nx_line_graph(edges, forbidden, origin, ticks):
    """Turn-expanded graph: node = directed edge; weight = travel ticks of the edge entered."""
    L = nx.DiGraph()
    by_tail = {}
    for u, v, e in edges:
        by_tail.setdefault(u, []).append(e)
    for u, v, a in edges:
        L.add_node(a)
        for b in by_tail.get(v, []):
            if (a, b) not in forbidden:
                L.add_edge(a, b, weight=ticks[b])
    L.add_node('S*')
    for b in by_tail.get(origin, []):
        L.add_edge('S*', b, weight=ticks[b])
    return L


@pytest.mark.parametrize('seed', range(40))
def test_common_segments_match_brute_force_edge_removal(tmp_path, seed):
    rng = random.Random(1000 + seed)
    n = rng.randint(4, 10)
    names = [f'n{i}' for i in range(n)]
    pairs = {(rng.choice(names), rng.choice(names)) for _ in range(rng.randint(n, 3 * n))}
    edges = [(u, v, f'e{k}') for k, (u, v) in enumerate(sorted(p for p in pairs if p[0] != p[1]))]
    if not edges:
        return
    turns = [(a, b) for (_, v, a) in edges for (u2, _, b) in edges if u2 == v]
    forbidden = {t for t in turns if rng.random() < 0.3}
    g, s = make_graph(tmp_path, edges, forbidden, name=f'c{seed}')
    for k in range(6):
        origin = rng.choice([u for u, _, _ in edges])
        dests = rng.sample([x for x in g.node_ids if x != origin], k=min(3, len(g.node_ids) - 1))
        ta, common = common_ids(g, s, origin, dests)
        if ta != 1:
            continue
        must = []
        for _, _, e in edges:              # an edge is on every legal walk iff removing it leaves none
            e2, f2 = _without_edge(edges, forbidden, e)
            if not e2:
                must.append(e)
                continue
            g2, s2 = make_graph(tmp_path, e2, f2, name=f'c{seed}_{k}_{e}')
            if origin not in g2.node_index or not any(d in g2.node_index for d in dests):
                must.append(e)
                continue
            if q(g2, s2, origin, [d for d in dests if d in g2.node_index])[0] == 0:
                must.append(e)
        assert sorted(common) == sorted(must)
        # walking order: along one shortest legal walk, the common edges appear in the reported order
        L = _nx_line_graph(edges, forbidden, origin, {e: 1 for _, _, e in edges})
        heads = {e: v for _, v, e in edges}
        ends = [e for e in L if e != 'S*' and heads[e] in dests]
        dist, path = nx.single_source_dijkstra(L, 'S*')
        best = min((e for e in ends if e in dist), key=lambda e: (dist[e], e))
        walk = path[best][1:]
        first = [walk.index(e) for e in common]
        assert first == sorted(first)


# ------------------------------------------------------------------------------------------------ fire-free trips

def test_fastest_trip_takes_the_legal_detour(tmp_path):
    # direct s->a->t is 2 + 2 ticks but the turn a->t is forbidden; the legal route is s->b->t (3 + 3)
    edges = [('s', 'a', 'e1'), ('a', 't', 'e2'), ('s', 'b', 'e3'), ('b', 't', 'e4')]
    ticks = {'e1': 2, 'e2': 2, 'e3': 3, 'e4': 3}
    g, _ = make_graph(tmp_path, edges, forbidden=[('e1', 'e2')], ticks=ticks)
    o, t = g.node_index['s'], g.node_index['t']
    assert fastest_trips(g, o, [t]) == {t: 6}
    g, _ = make_graph(tmp_path, edges, ticks=ticks, name='free')
    assert fastest_trips(g, g.node_index['s'], [g.node_index['t']]) == {g.node_index['t']: 4}


def test_fastest_trip_unreachable_is_none(tmp_path):
    g, _ = make_graph(tmp_path, [('s', 'a', 'e1'), ('t', 'a', 'e2')])
    assert fastest_trips(g, g.node_index['s'], [g.node_index['t']]) == {g.node_index['t']: None}


def test_walk_length_to_edge_end_sums_chords_along_legal_walks(tmp_path):
    xy = {'s': (0, 0), 'a': (3, 4), 'b': (3, -4), 't': (6, 0)}
    edges = [('s', 'a', 'e1'), ('a', 't', 'e2'), ('s', 'b', 'e3'), ('b', 't', 'e4'), ('t', 'u', 'e5')]
    xy['u'] = (6, 10)
    g, _ = make_graph(tmp_path, edges, forbidden=[('e2', 'e5')], xy=xy)
    # e5 can only be reached through b (5 + 5 + 10 m); through a the turn into e5 is forbidden
    assert walk_length_to_edge_end(g, g.node_index['s'], g.edge_index['e5']) == pytest.approx(20.0)
    assert walk_length_to_edge_end(g, g.node_index['s'], g.edge_index['e2']) == pytest.approx(10.0)


@pytest.mark.parametrize('seed', range(40))
def test_fastest_trips_match_networkx_on_random_graphs(tmp_path, seed):
    rng = random.Random(2000 + seed)
    n = rng.randint(4, 12)
    names = [f'n{i}' for i in range(n)]
    pairs = {(rng.choice(names), rng.choice(names)) for _ in range(rng.randint(n, 4 * n))}
    edges = [(u, v, f'e{k}') for k, (u, v) in enumerate(sorted(p for p in pairs if p[0] != p[1]))]
    if not edges:
        return
    ticks = {e: rng.randint(1, 9) for _, _, e in edges}
    turns = [(a, b) for (_, v, a) in edges for (u2, _, b) in edges if u2 == v]
    forbidden = {t for t in turns if rng.random() < 0.3}
    g, _ = make_graph(tmp_path, edges, forbidden, name=f't{seed}', ticks=ticks)
    heads = {e: v for _, v, e in edges}
    for _ in range(5):
        origin = rng.choice([u for u, _, _ in edges])
        dests = rng.sample([x for x in g.node_ids if x != origin], k=min(3, len(g.node_ids) - 1))
        dist = nx.single_source_dijkstra_path_length(_nx_line_graph(edges, forbidden, origin, ticks), 'S*')
        want = {d: min((dist[e] for e in dist if e != 'S*' and heads[e] == d), default=None) for d in dests}
        got = fastest_trips(g, g.node_index[origin], [g.node_index[d] for d in dests])
        assert {d: got[g.node_index[d]] for d in dests} == want
