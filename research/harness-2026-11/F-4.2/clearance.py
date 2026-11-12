"""Spatial clearance margin for routes on a frozen hazard packet (F-4.2 primary definition).

Geometry and timing follow the kit's whole-road contact checker (contact_first.check_contact + mission_contract):
the vehicle moves on straight node-to-node segments with linear timing, stands still at waits and during the
destination dwell, every source is a closed 375 m cell rectangle from the packet affine, a present-fire cell is active
on [0, R_max) and a drawn ignition b on [b, b+T). Contact at dilation r means the moving point comes within Euclidean
distance <= r of an active source rectangle (Minkowski dilation of every flame region by a disc of radius r; r = 0 is
the checker's closed-footprint contact). Members are combined worst-case: a route must clear every member.

* route_clearance(...)  clearance of one fixed route = min distance to any active source over time (metres), with the
  limiting source, member and time. The route's spatial margin r* is exactly this value (contact part only).
* search(r)             earliest arrival over routes whose clearance is > r (time-dependent label-setting search over
  (node, incoming edge) states with the graph's forbidden turns, waiting only at waitable nodes, departure fixed,
  destination opening intervals, dwell and horizon). Dilated sets are nested, so arrival a(r) is nondecreasing in r.

Distances are computed in binary64 with an outward pad (PAD_M) on every blocked interval, so a reported route is
never closer than r - PAD_M; exact rational re-verification of a margin witness at r = 0 is done by the unchanged full
checker (fixed_route_check.py). Radiation dose/peak is NOT part of this margin (see RESULTS.md: dose is far from its
budget on all routed missions).

  python clearance.py --region uljin_2022 --case 20220304T030000Z_FX1 [--route RESULT.json] [--radii 0,100,200]
"""
import argparse, heapq, json, math, sys, time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
PAD_M = 1e-6          # metres added to every distance test (outward: blocks slightly more)
ITERS = 80


def load(region, case_id, inputs=None, packet=None):
    inputs = Path(inputs or REPO / 'data/routing')
    cutoff = case_id.split('_')[0]
    graph = json.loads((inputs / 'graphs' / region / 'graph.json').read_text())
    request = json.loads((inputs / 'latest_inputs_try02/requests' / region / (case_id + '.json')).read_text())
    pk = Path(packet) if packet else inputs / 'latest_inputs_try02/packets' / region / cutoff
    report = json.loads((pk / 'REPORT.json').read_text())
    md = report['native_metadata']; asm = md['construction']['assumptions']
    a, b, c, d, e, f = [float(v) for v in md['affine_transform']]
    assert b == 0 and d == 0
    with np.load(pk / 'constructed_arrays.npz', allow_pickle=False) as z:
        ev = z['ignition_time_s']; cur = z['current_active']
    S, H, W = ev.shape
    T = float(asm['burning_duration_s']); R = float(asm['initial_remaining_s']); horizon = float(asm['horizon_s'])
    src = []   # (x0, x1, y0, y1, birth, expiry, member, kind, cell)
    for row in range(H):
        for col in range(W):
            xs = sorted((c + col * a, c + (col + 1) * a)); ys = sorted((f + row * e, f + (row + 1) * e))
            i = row * W + col
            for s in range(S):
                if cur[row, col] and R > 0:
                    src.append((xs[0], xs[1], ys[0], ys[1], 0.0, R, s, 'CURRENT', i))
                elif np.isfinite(ev[s, row, col]):
                    bb = float(ev[s, row, col]); src.append((xs[0], xs[1], ys[0], ys[1], bb, bb + T, s, 'FUTURE', i))
    # identical (rectangle, phase) entries across members are merged for speed; member list kept
    merged = {}
    for x0, x1, y0, y1, bb, ee, s, k, i in src:
        merged.setdefault((x0, x1, y0, y1, bb, ee, k, i), []).append(s)
    sources = [dict(rect=(k[0], k[1], k[2], k[3]), birth=k[4], expiry=k[5], kind=k[6], cell=k[7], members=v) for k, v in merged.items()]
    hz = dict(T=T, R_max=R, horizon=horizon, members=S, shape=(H, W), domain=(min(c, c + W * a), max(c, c + W * a), min(f, f + H * e), max(f, f + H * e)),
              ignitions_per_member=[int(np.isfinite(ev[s]).sum()) for s in range(S)], present_fire_cells=int(cur.sum()))
    return graph, request, sources, hz


def _dist(px, py, R):
    dx = np.maximum(np.maximum(R[:, 0] - px, 0.0), px - R[:, 1])
    dy = np.maximum(np.maximum(R[:, 2] - py, 0.0), py - R[:, 3])
    return np.hypot(dx, dy)


def seg_rect(P0, P1, R):
    """Vectorized: for segments P0->P1 (n,2) and rectangles R (n,4): (u_min, d_min) of the convex distance profile."""
    lo = np.zeros(len(R)); hi = np.ones(len(R))
    for _ in range(ITERS):                  # ternary search on a convex function
        m1 = lo + (hi - lo) / 3; m2 = hi - (hi - lo) / 3
        f1 = _dist(P0[:, 0] + (P1[:, 0] - P0[:, 0]) * m1, P0[:, 1] + (P1[:, 1] - P0[:, 1]) * m1, R)
        f2 = _dist(P0[:, 0] + (P1[:, 0] - P0[:, 0]) * m2, P0[:, 1] + (P1[:, 1] - P0[:, 1]) * m2, R)
        left = f1 <= f2
        hi = np.where(left, m2, hi); lo = np.where(left, lo, m1)
    u = (lo + hi) / 2
    cand = np.stack([np.zeros_like(u), u, np.ones_like(u)])
    dd = np.stack([_dist(P0[:, 0] + (P1[:, 0] - P0[:, 0]) * k, P0[:, 1] + (P1[:, 1] - P0[:, 1]) * k, R) for k in cand])
    j = dd.argmin(axis=0)
    return cand[j, np.arange(len(u))], dd[j, np.arange(len(u))]


def sublevel(P0, P1, R, r, umin, dmin):
    """Fraction interval [u0, u1] where distance <= r + PAD (convex => one interval); NaN where empty."""
    rr = r + PAD_M
    inside = dmin <= rr
    def f(u):
        return _dist(P0[:, 0] + (P1[:, 0] - P0[:, 0]) * u, P0[:, 1] + (P1[:, 1] - P0[:, 1]) * u, R)
    # left end: smallest u in [0, umin] with f(u) <= rr ; bisection keeps the outward side
    a = np.zeros_like(umin); b = umin.copy()
    in0 = f(a) <= rr
    for _ in range(ITERS):
        m = (a + b) / 2; ok = f(m) <= rr
        b = np.where(ok, m, b); a = np.where(ok, a, m)
    u0 = np.where(in0, 0.0, a)              # a is the last point known outside -> outward
    a = umin.copy(); b = np.ones_like(umin)
    in1 = f(b) <= rr
    for _ in range(ITERS):
        m = (a + b) / 2; ok = f(m) <= rr
        a = np.where(ok, m, a); b = np.where(ok, b, m)
    u1 = np.where(in1, 1.0, b)
    return np.where(inside, u0, np.nan), np.where(inside, u1, np.nan)


class Instance:
    def __init__(self, graph, request, sources, hz):
        self.g, self.req, self.src, self.hz = graph, request, sources, hz
        self.nodes = {n['id']: n for n in graph['nodes']}
        self.edges = graph['edges']; self.eidx = {e['id']: k for k, e in enumerate(self.edges)}
        self.out = {}
        for k, e in enumerate(self.edges):
            self.out.setdefault(e['u'], []).append(k)
        self.forbidden = {tuple(p) for p in graph.get('forbidden_turns', [])}
        self.P0 = np.array([[self.nodes[e['u']]['x'], self.nodes[e['u']]['y']] for e in self.edges], float)
        self.P1 = np.array([[self.nodes[e['v']]['x'], self.nodes[e['v']]['y']] for e in self.edges], float)
        self.tau = np.array([e['travel_ticks'] for e in self.edges], float)
        self.SR = np.array([s['rect'] for s in sources], float).reshape(-1, 4)
        self.SB = np.array([s['birth'] for s in sources], float); self.SE = np.array([s['expiry'] for s in sources], float)
        self._pairs = {}
        self.rcap = 6001.0     # candidate pairs are computed once up to this radius and filtered per r

    def pairs(self, rmax):
        """Candidate (edge, source) pairs whose bounding boxes are within rmax; with u_min / d_min."""
        key = rmax
        if key in self._pairs:
            return self._pairs[key]
        ex0 = np.minimum(self.P0[:, 0], self.P1[:, 0]) - rmax; ex1 = np.maximum(self.P0[:, 0], self.P1[:, 0]) + rmax
        ey0 = np.minimum(self.P0[:, 1], self.P1[:, 1]) - rmax; ey1 = np.maximum(self.P0[:, 1], self.P1[:, 1]) + rmax
        E, Sx = [], []
        for j, (x0, x1, y0, y1) in enumerate(self.SR):
            k = np.flatnonzero((ex0 <= x1) & (ex1 >= x0) & (ey0 <= y1) & (ey1 >= y0))
            E.append(k); Sx.append(np.full(k.size, j))
        E = np.concatenate(E) if E else np.zeros(0, int); Sx = np.concatenate(Sx) if Sx else np.zeros(0, int)
        um, dm = seg_rect(self.P0[E], self.P1[E], self.SR[Sx]) if E.size else (np.zeros(0), np.zeros(0))
        self._pairs[key] = (E, Sx, um, dm)
        return self._pairs[key]

    def blocked(self, r, rmax):
        """edge index -> sorted list of blocked integer-departure half-open intervals [lo, hi) for radius r."""
        E, Sx, um, dm = self.pairs(rmax)
        keep = dm <= r + PAD_M
        E, Sx, um, dm = E[keep], Sx[keep], um[keep], dm[keep]
        u0, u1 = sublevel(self.P0[E], self.P1[E], self.SR[Sx], r, um, dm)
        tau = self.tau[E]
        # departure t is bad iff [t + u0 tau, t + u1 tau] meets [birth, expiry): t in [birth - u1 tau, expiry - u0 tau)
        lo = self.SB[Sx] - u1 * tau; hi = self.SE[Sx] - u0 * tau
        out = {}
        for e, a, b in zip(E.tolist(), lo.tolist(), hi.tolist()):
            # integer departures t with lo <= t < hi, i.e. ceil(lo) .. ceil(hi)-1 (the u-interval is already outward)
            out.setdefault(e, []).append((a, b))
        for e in out:
            iv = sorted(out[e]); merged = [list(iv[0])]
            for a, b in iv[1:]:
                if a <= merged[-1][1]:
                    merged[-1][1] = max(merged[-1][1], b)
                else:
                    merged.append([a, b])
            out[e] = merged
        return out

    def point_blocked(self, node, r):
        """Blocked intervals [lo, hi) for standing at a node (dwell / waits)."""
        n = self.nodes[node]; p = np.array([[n['x'], n['y']]], float)
        d = _dist(p[:, 0].repeat(len(self.SR)), p[:, 1].repeat(len(self.SR)), self.SR)
        k = np.flatnonzero(d <= r + PAD_M)
        return sorted(zip(self.SB[k].tolist(), self.SE[k].tolist()))

    def _dijkstra(self, r, s0, t0, full=False, rmax=None):
        """Earliest-arrival label setting over (node, incoming edge) states from state s0 at time t0 with clearance > r.
        Waiting only at waitable nodes (to skip a blocked departure). Destination test ignores the opening START
        (opening end, dwell, horizon enforced). Returns (found or None, best, parent)."""
        rmax = max(r + 1.0, rmax or self.rcap)
        if getattr(self, '_bad_r', None) != r:
            blk = self.blocked(r, rmax)
            self._bad = {e: [(int(math.ceil(a)), int(math.ceil(b)) - 1) for a, b in iv if math.ceil(b) - 1 >= math.ceil(a)] for e, iv in blk.items()}
            self._bad_r = r
        bad = self._bad
        req = self.req; H = int(req['horizon'])
        dests = {d['node']: d for d in req['destinations']}
        best = {s0: t0}; parent = {}; pq = [(t0, s0)]; found = None
        while pq:
            t, state = heapq.heappop(pq)
            if best.get(state, math.inf) < t:
                continue
            v, inc = state
            if v in dests and found is None:
                d = dests[v]; dw = int(d['dwell'])
                if any(t + dw <= o1 for _, o1 in d['open_intervals']) and t + dw <= H and \
                        not any(a <= t + dw and b >= t for a, b in self.stand_bad(v, r)):
                    found = (t, state)
                    if not full:
                        break
            waitable = self.nodes[v].get('waitable', False)
            for e in self.out.get(v, []):
                if inc is not None and (self.edges[inc]['id'], self.edges[e]['id']) in self.forbidden:
                    continue
                td = t
                for a, b in bad.get(e, []):
                    if a <= td <= b:
                        td = b + 1 if waitable else None
                    if td is None:
                        break
                if td is None:
                    continue
                if td > t and any(a <= td and b >= t for a, b in self.stand_bad(v, r)):
                    continue
                ta = td + int(self.tau[e])
                if ta > H:
                    continue
                key = (self.edges[e]['v'], e)
                if ta < best.get(key, math.inf):
                    best[key] = ta; parent[key] = (state, td); heapq.heappush(pq, (ta, key))
        return found, best, parent

    def _legs(self, best, parent, s0, state):
        legs = []
        while state != s0:
            pstate, td = parent[state]; e = state[1]
            legs.append({'kind': 'EDGE', 'edge': self.edges[e]['id'], 'start': int(td), 'end': int(td + self.tau[e]), 'from_fraction': 0, 'to_fraction': 1})
            if best[pstate] < td:
                legs.append({'kind': 'WAIT', 'node': pstate[0], 'start': int(best[pstate]), 'end': int(td)})
            state = pstate
        legs.reverse(); return legs

    def _start(self):
        inc0 = self.req.get('incoming_edge')
        return (self.req['position']['node'], None if inc0 is None else self.eidx[inc0]), int(self.req['departure'])

    def relaxed(self, r, rmax=None):
        """Earliest arrival with clearance > r ignoring the destination opening start. The real arrival is
        >= max(relaxed arrival, opening start): a valid infeasibility bound when earliest labels dominate."""
        s0, t0 = self._start()
        found, best, parent = self._dijkstra(r, s0, t0, rmax=rmax)
        if found is None:
            return None
        return {'arrival': found[0], 'destination': found[1][0], 'legs': self._legs(best, parent, s0, found[1])}

    def static_to_dest(self):
        """Hazard-free shortest travel ticks from every node to the nearest destination (turns ignored: a lower bound)."""
        if hasattr(self, '_sp'):
            return self._sp
        rev = {}
        for e in self.edges:
            rev.setdefault(e['v'], []).append((e['u'], e['travel_ticks']))
        dist = {d['node']: 0 for d in self.req['destinations']}; pq = [(0, v) for v in dist]
        while pq:
            dd, v = heapq.heappop(pq)
            if dd > dist.get(v, math.inf):
                continue
            for u, w in rev.get(v, []):
                if dd + w < dist.get(u, math.inf):
                    dist[u] = dd + w; heapq.heappush(pq, (dd + w, u))
        self._sp = dist; return dist

    def stand_bad(self, v, r):
        key = (v, r)
        if not hasattr(self, '_sb'):
            self._sb = {}
        if key not in self._sb:
            self._sb[key] = [(int(math.ceil(a)), int(math.ceil(b)) - 1) for a, b in self.point_blocked(v, r) if math.ceil(b) - 1 >= math.ceil(a)]
        return self._sb[key]

    def search(self, r, rmax=None, max_candidates=60):
        """A feasible route with clearance > r meeting the destination opening, or None (witness search; a None here
        is NOT an infeasibility proof - relaxed() gives the bound). If the relaxed earliest route already meets the
        opening it is returned. Otherwise: one full forward search gives earliest labels F at every state; for
        waitable nodes w ordered by max(F + static(w), opening start), the vehicle waits at w until
        opening start - static(w) (standing clear) and a time-dependent search continues from there."""
        rel = self.relaxed(r, rmax)
        if rel is None:
            return None
        d = [x for x in self.req['destinations'] if x['node'] == rel['destination']][0]
        o0 = min(o[0] for o in d['open_intervals'] if rel['arrival'] + d['dwell'] <= o[1])
        if rel['arrival'] >= o0:
            rel['relaxed_arrival'] = rel['arrival']; return rel
        s0, t0 = self._start()
        _, best, parent = self._dijkstra(r, s0, t0, full=True, rmax=rmax)
        sp = self.static_to_dest()
        cands = []
        for (v, inc), F in best.items():
            if self.nodes[v].get('waitable', False) and v in sp:
                cands.append((max(F + sp[v], o0), F, (v, inc)))
        cands.sort(key=lambda x: (x[0], x[1]))
        tried = set(); out = None
        for _, F, w in cands:
            if w[0] in tried:
                continue
            tried.add(w[0])
            if len(tried) > max_candidates:
                break
            td = max(F, int(o0 - sp[w[0]]))
            if td > F and any(a <= td and b >= F for a, b in self.stand_bad(w[0], r)):
                continue
            found, b2, p2 = self._dijkstra(r, w, td, rmax=rmax)
            if found is None or found[0] < o0:
                continue
            legs = self._legs(best, parent, s0, w)
            if td > F:
                legs.append({'kind': 'WAIT', 'node': w[0], 'start': int(F), 'end': int(td)})
            legs += self._legs(b2, p2, w, found[1])
            cand = {'arrival': found[0], 'destination': found[1][0], 'legs': legs, 'relaxed_arrival': rel['arrival'], 'wait_node': w[0]}
            if out is None or cand['arrival'] < out['arrival']:
                out = cand
            if out['arrival'] == o0:
                break
        return out

    def route_clearance(self, route):
        """Exact-geometry (binary64) clearance of a fixed route: min distance over time-overlapping active sources."""
        req = self.req; t = req['departure']; v = req['position']['node']
        segs = []   # (p0, p1, t0, t1)
        for L in route['legs']:
            if L['kind'] == 'EDGE':
                e = self.edges[self.eidx[L['edge']]]
                segs.append(((self.nodes[e['u']]['x'], self.nodes[e['u']]['y']), (self.nodes[e['v']]['x'], self.nodes[e['v']]['y']), L['start'], L['end'], L['edge']))
            else:
                n = self.nodes[L['node']]; segs.append(((n['x'], n['y']), (n['x'], n['y']), L['start'], L['end'], 'WAIT:' + L['node']))
        dw = [d['dwell'] for d in req['destinations'] if d['node'] == route['destination']][0]
        n = self.nodes[route['destination']]
        segs.append(((n['x'], n['y']), (n['x'], n['y']), route['arrival'], route['arrival'] + dw, 'DWELL'))
        best = (math.inf, None)
        for p0, p1, t0, t1, lab in segs:
            # active sources overlapping [t0, t1] (closed occupancy, half-open activity)
            k = np.flatnonzero((self.SB <= t1) & (self.SE > t0))
            if not k.size:
                continue
            # restrict the segment to the time window where each source is active
            span = (t1 - t0) or 1.0
            ua = np.clip((np.maximum(self.SB[k], t0) - t0) / span, 0, 1); ub = np.clip((np.minimum(self.SE[k], t1) - t0) / span, 0, 1)
            P0 = np.array(p0, float) + (np.array(p1, float) - np.array(p0, float)) * ua[:, None]
            P1 = np.array(p0, float) + (np.array(p1, float) - np.array(p0, float)) * ub[:, None]
            _, dm = seg_rect(P0, P1, self.SR[k])
            j = int(dm.argmin())
            if dm[j] < best[0]:
                s = self.src[k[j]]
                best = (float(dm[j]), {'segment': lab, 'segment_time': [t0, t1], 'source_cell': s['cell'], 'source_kind': s['kind'],
                                       'source_active': [s['birth'], s['expiry']], 'members': s['members']})
        return best


def export_blocks(region, case_id, r, packet=None, inputs=None):
    """Blocked integer seconds at dilation r in the F-3.1 deadline-field format (Richard): closed inclusive intervals
    clipped to [0, H].
      B[j]          edge j (graph.json order): blocked departure seconds
      W[node]       waitable node: blocked standing seconds (a wait [t, t+1] occupies the point)
      dwell[node]   destination: blocked dwell START seconds t (standing [t, t + dwell] meets a dilated source)
      issue[node]   origin: blocked issue seconds (standing at the instant t)
    Same geometry and outward rounding as Instance.blocked / point_blocked; r = 0 is the closed-footprint contact."""
    import hashlib
    g, rq, src, hz = load(region, case_id, inputs=inputs, packet=packet)
    I = Instance(g, rq, src, hz); H = int(rq['horizon'])
    def clip(iv):
        out = []
        for a, b in iv:
            a, b = max(0, int(a)), min(H, int(b))
            if a <= b:
                out.append([a, b])
        return out
    blk = I.blocked(r, max(r + 1.0, I.rcap))
    B = [clip([(math.ceil(a), math.ceil(b) - 1) for a, b in blk.get(j, [])]) for j in range(len(I.edges))]
    stand = lambda v: [(math.ceil(a), math.ceil(b) - 1) for a, b in I.point_blocked(v, r)]
    W = {n['id']: clip(stand(n['id'])) for n in g['nodes'] if n.get('waitable', False)}
    dwell = {}
    for d in rq['destinations']:
        dw = int(d['dwell'])
        dwell[d['node']] = clip([(a - dw, b) for a, b in stand(d['node'])])   # [t, t+dw] meets [a, b]  <=>  t in [a-dw, b]
    issue = {rq['position']['node']: clip(stand(rq['position']['node']))}
    order = hashlib.sha256(json.dumps([e['id'] for e in g['edges']]).encode()).hexdigest()
    return {'schema': 'wfg.harness.f42.dilation-blocks/1', 'region': region, 'case': case_id, 'r_m': r, 'H': H,
            'B': B, 'W': W, 'dwell': dwell, 'issue': issue, 'edge_order_sha256': order,
            'geometry': 'isotropic Euclidean dilation of closed cell rectangles; straight node segments; outward integer rounding; PAD_M=%g' % PAD_M}


def contact_time_margin(I, route):
    """Diagnostic: for every drawn ignition (any member) whose closed cell the fixed route touches (r = 0) during a
    visit [t_in, t_out] before ignition, the advance that first causes contact is b - t_out. Returns the minimum
    (inf if the route never touches a cell before it ignites) and the count of touched ignited cells."""
    req = I.req
    segs = []
    for L in route['legs']:
        if L['kind'] == 'EDGE':
            e = I.edges[I.eidx[L['edge']]]
            segs.append(((I.nodes[e['u']]['x'], I.nodes[e['u']]['y']), (I.nodes[e['v']]['x'], I.nodes[e['v']]['y']), L['start'], L['end']))
        else:
            n = I.nodes[L['node']]; segs.append(((n['x'], n['y']), (n['x'], n['y']), L['start'], L['end']))
    dw = [d['dwell'] for d in req['destinations'] if d['node'] == route['destination']][0]
    n = I.nodes[route['destination']]; segs.append(((n['x'], n['y']), (n['x'], n['y']), route['arrival'], route['arrival'] + dw))
    fut = [j for j, s in enumerate(I.src) if s['kind'] == 'FUTURE']
    best = math.inf; touched = 0
    if not fut:
        return best, 0
    R = I.SR[fut]
    for p0, p1, t0, t1 in segs:
        P0 = np.repeat([p0], len(fut), axis=0).astype(float); P1 = np.repeat([p1], len(fut), axis=0).astype(float)
        um, dm = seg_rect(P0, P1, R)
        u0, u1 = sublevel(P0, P1, R, 0.0, um, dm)
        for k in np.flatnonzero(~np.isnan(u0)):
            tin, tout = t0 + (t1 - t0) * u0[k], t0 + (t1 - t0) * u1[k]
            b = I.src[fut[k]]['birth']; touched += 1
            if tout < b:
                best = min(best, b - tout)
    return best, touched


def domain_distance(I, route):
    """Smallest distance from the route (any node it uses) to the boundary of the packet's source domain. Fire outside
    the domain is not represented, so a clearance at least this large is CROP-limited, not fire-limited."""
    x0, x1, y0, y1 = I.hz['domain']
    ids = [route['destination']] + [I.edges[I.eidx[L['edge']]][k] for L in route['legs'] if L['kind'] == 'EDGE' for k in ('u', 'v')]
    pts = np.array([[I.nodes[v]['x'], I.nodes[v]['y']] for v in set(ids)])
    return float(np.min(np.minimum.reduce([pts[:, 0] - x0, x1 - pts[:, 0], pts[:, 1] - y0, y1 - pts[:, 1]])))


def best_radius(I, deadline, r_hi=6000.0, tol=1.0):
    """Bracket the largest dilation r with a route arriving by `deadline`.

    Upper side: the relaxed earliest arrival is nondecreasing in r (nested dilations), and the real arrival is
    >= max(relaxed, opening start), so bisection on `relaxed fits the deadline` gives r_fail: no route at any
    r >= r_fail (exact when earliest labels dominate). Lower side: a repaired route found at r_lo is a feasible
    witness. Returns (r_lo, witness, r_fail); r_fail None means censored at r_hi."""
    d = I.req['destinations']
    o0 = min(o[0] for x in d for o in x['open_intervals'])
    def up(r):
        rel = I.relaxed(r)
        return rel is not None and max(rel['arrival'], o0) <= deadline
    def low(r):
        res = I.search(r)
        return res if (res is not None and res['arrival'] <= deadline) else None
    if not up(0.0):
        return None, None, 0.0
    if up(r_hi):
        r_fail = None
    else:
        lo, hi = 0.0, r_hi
        while hi - lo > tol:
            m = (lo + hi) / 2
            lo, hi = (m, hi) if up(m) else (lo, m)
        r_fail = hi
    top = r_hi if r_fail is None else r_fail
    w = low(top - tol) if top - tol >= 0 else None
    if w is not None:
        return top - tol, w, r_fail
    lo, hi, best = 0.0, top, low(0.0)
    if best is None:
        return None, None, r_fail
    while hi - lo > tol:
        m = (lo + hi) / 2; res = low(m)
        if res is not None:
            lo, best = m, res
        else:
            hi = m
    return lo, best, r_fail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--region', required=True); ap.add_argument('--case', required=True)
    ap.add_argument('--route', type=Path); ap.add_argument('--packet', type=Path)
    ap.add_argument('--radii', default='0')
    a = ap.parse_args()
    g, rq, src, hz = load(a.region, a.case, packet=a.packet)
    I = Instance(g, rq, src, hz)
    out = {'region': a.region, 'case': a.case, 'hazard': hz, 'sources': len(src)}
    if a.route:
        r = json.loads(a.route.read_text()); r = r.get('result', r) if 'legs' not in r else r
        c, info = I.route_clearance(r)
        out['published'] = {'arrival': r['arrival'], 'clearance_m': c, 'limit': info}
    rows = []
    for rad in [float(x) for x in a.radii.split(',')]:
        t0 = time.perf_counter(); res = I.search(rad)
        row = {'r_m': rad, 'arrival': None if res is None else res['arrival'], 'search_s': time.perf_counter() - t0}
        if res is not None:
            row['clearance_m'], row['limit'] = I.route_clearance(res); row['n_legs'] = len(res['legs'])
        rows.append(row)
    out['curve'] = rows
    print(json.dumps(out, default=str))


if __name__ == '__main__':
    main()
