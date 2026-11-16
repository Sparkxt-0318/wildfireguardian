"""Time-dependent, turn-aware optimistic search on reversible road corridors."""
from collections import defaultdict
from fractions import Fraction as F
from heapq import heappop, heappush
from math import ceil, inf


def union(spans):
    ans = []
    for a, b in sorted(spans):
        if a >= b:
            continue
        if ans and a <= ans[-1][1]:
            ans[-1] = (ans[-1][0], max(b, ans[-1][1]))
        else:
            ans.append((a, b))
    return ans


def clip(p, q, rect):
    """Exact closed intersection including a single point on a rectangle boundary."""
    lo, hi = F(0), F(1)
    for i, (left, right) in enumerate(((rect[0], rect[1]), (rect[2], rect[3]))):
        delta = q[i] - p[i]
        if delta == 0:
            if not left <= p[i] <= right:
                return None
            continue
        a, b = sorted(((left-p[i])/delta, (right-p[i])/delta))
        lo, hi = max(lo, a), min(hi, b)
        if lo > hi:
            return None
    return lo, hi


def make_entry_sets(graph, compiled, contact, horizon, subset=None):
    """Read native edge-cell proposals, verify each by clipping the original road."""
    index = compiled.index
    grid = graph['grid']
    width, res = grid['width'], F(grid['resolution'])
    x0, y0 = F(grid['x0']), F(grid['y0'])
    rects = {}
    for cell in contact:
        rr, cc = divmod(cell, width)
        x, y = x0 + res*cc, y0 + res*rr
        rects[cell] = (x, x+res, y, y+res)
    nodes = {n['id']:n for n in graph['nodes']}
    xy = {}
    def point(n):
        if n not in xy:
            xy[n] = F(nodes[n]['x']), F(nodes[n]['y'])
        return xy[n]
    out = []
    events = 0
    part_ids = range(len(compiled.parts)) if subset is None else subset
    for k_part in part_ids:
        part = compiled.parts[k_part]
        blocked = []
        offset = 0
        for k in part:
            edge = index.edges[k]
            duration = edge['travel_ticks']
            # Only stored candidate cells are examined. Extraneous proposals are clipped away.
            for cell in {s['cell'] for s in edge['segments'] if s['cell'] in contact}:
                segment = clip(point(edge['u']), point(edge['v']), rects[cell])
                if segment is None:
                    continue
                left, right = segment
                for begin, end in contact[cell]:
                    lo = max(0, ceil(begin-duration*right)-offset)
                    hi = min(horizon+1, ceil(end-duration*left)-offset)
                    if lo < hi:
                        events += 1
                        blocked.append((lo,hi))
            offset += duration
        out.append(union(blocked))
    return out, events


def next_entry(blocks, t):
    for a,b in blocks:
        if t < a:
            break
        if t < b:
            return b
    return t


def destination_bound(arrival, target, horizon):
    if arrival is None:
        return None
    best = inf
    for lo, hi in target['open_intervals']:
        t = max(arrival, lo)
        if t+target['dwell'] <= min(hi,horizon):
            best = min(best,t)
    return None if best == inf else best


def temporal_bound(compiled, forbidden, request):
    """Optimistically allow waiting through hazard at corridor boundaries."""
    start = request['departure']
    source = request['position']['node']
    dest, = request['destinations']
    horizon = request['horizon']
    if source == dest['node']:
        return destination_bound(start,dest,horizon), 0
    Q = []
    ds = {}
    def relax(node, previous, current):
        for k in compiled.at.get(node, ()):
            if previous is not None and not compiled.index.allowed(previous, compiled.parts[k][0]):
                continue
            t = next_entry(forbidden[k],current)+compiled.cost[k]
            if t <= horizon and t < ds.get(k,inf):
                ds[k] = t
                heappush(Q,(t,k))
    incoming = request['incoming_edge']
    relax(source, None if incoming is None else compiled.index.by_id[incoming], start)
    pops=0
    while Q:
        arrival,k = heappop(Q)
        if ds[k] != arrival:
            continue
        pops+=1
        v=compiled.ends[k]
        if v == dest['node']:
            return destination_bound(arrival,dest,horizon),pops
        relax(v,compiled.parts[k][-1],arrival)
    return None,pops
