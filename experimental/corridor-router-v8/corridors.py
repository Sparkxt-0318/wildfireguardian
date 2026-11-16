"""Reversible contraction of forced directed road movements, with native traversal clocks."""
from collections import defaultdict
from heapq import heappop, heappush
from math import inf


class RoadIndex:
    def __init__(self, graph):
        self.edges = graph['edges']
        self.by_id = {edge['id']: i for i, edge in enumerate(self.edges)}
        self.at = defaultdict(list)
        self.into = defaultdict(list)
        self.forbidden = set(map(tuple, graph['forbidden_turns']))
        self.waitable = {n['id'] for n in graph['nodes'] if n['waitable']}
        for i, edge in enumerate(self.edges):
            if edge['travel_ticks'] <= 0 or int(edge['travel_ticks']) != edge['travel_ticks']:
                raise ValueError('Corridor requires positive integer travel time')
            self.at[edge['u']].append(i)
            self.into[edge['v']].append(i)

    def allowed(self, a, b):
        return (self.edges[a]['id'], self.edges[b]['id']) not in self.forbidden


def partition(index, terminal_nodes):
    """Concatenate movements only when each forces the other in the turn graph."""
    stops = index.waitable | set(terminal_nodes)
    successor = {}
    predecessor = {}
    for node, incoming in index.into.items():
        if node in stops:
            continue
        outgoing = index.at.get(node, ())
        for i in incoming:
            eligible = [j for j in outgoing if index.allowed(i, j)]
            if len(eligible) != 1:
                continue
            j = eligible[0]
            if sum(index.allowed(k, j) for k in incoming) == 1:
                successor[i] = j
                predecessor[j] = i
    parts = []
    owner = {}
    count = len(index.edges)
    def chain(i):
        path = []
        while i is not None and i not in owner:
            owner[i] = len(parts)
            path.append(i)
            i = successor.get(i)
        parts.append(tuple(path))
    for i in range(count):
        if i not in predecessor:
            chain(i)
    for i in range(count):
        if i not in owner:
            chain(i)  # deterministic anchor for an otherwise isolated directed cycle
    return parts, owner


class SearchGraph:
    def __init__(self, index, parts):
        self.index = index
        self.parts = parts
        self.at = defaultdict(list)
        self.ends = []
        self.cost = []
        for k, path in enumerate(parts):
            edges = index.edges
            self.at[edges[path[0]]['u']].append(k)
            self.ends.append(edges[path[-1]]['v'])
            self.cost.append(sum(edges[i]['travel_ticks'] for i in path))

    def duration(self, source, target, incoming):
        if source == target:
            return 0, 0
        queue = []
        distances = {}
        initial = self.index.by_id[incoming] if incoming is not None else None
        def relax(node, last, elapsed):
            for k in self.at.get(node, ()):
                if last is not None and not self.index.allowed(last, self.parts[k][0]):
                    continue
                value = elapsed + self.cost[k]
                if value < distances.get(k, inf):
                    distances[k] = value
                    heappush(queue, (value, k))
        relax(source, initial, 0)
        pops = 0
        while queue:
            value, k = heappop(queue)
            if distances[k] != value:
                continue
            pops += 1
            v = self.ends[k]
            if v == target:
                return value, pops
            relax(v, self.parts[k][-1], value)
        return None, pops


def reconstruct(index, parts, owner, legs):
    """Return the number of macro legs and check exact recovery of all original edge clocks."""
    j = 0
    count = 0
    while j < len(legs):
        leg = legs[j]
        if leg['kind'] == 'WAIT':
            assert leg['node'] in index.waitable
            j += 1
            continue
        sequence = parts[owner[index.by_id[leg['edge']]]]
        t = leg['start']
        for i in sequence:
            actual = legs[j]
            e = index.edges[i]
            assert actual['kind'] == 'EDGE' and actual['edge'] == e['id']
            assert actual.get('from_fraction', 0) == 0 and actual.get('to_fraction', 1) == 1
            assert t == actual['start'] and t + e['travel_ticks'] == actual['end']
            j += 1
            t = actual['end']
        count += 1
    return count
