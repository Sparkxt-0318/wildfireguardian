"""Stage Z: exact contact-only lattice relaxation by a vectorised time-expanded sweep (own implementation).

States: (directed edge just traversed, integer second, admission flag); the virtual state E is the issue position
with incoming edge None. Transitions are exactly the router's lattice grammar (core.solve): an EDGE e' leaves the head
node of the state at t when (incoming, e') is not a forbidden turn and t + travel_ticks*dt <= horizon, and arrives with
admission at t + D(e'); a WAIT at a waitable node moves to t + dt without admission; an arrival with admission at a
destination node is accepted at t when some opening [a, b] contains [t, t + dwell], t + dwell <= horizon and the dwell
occupancy is admissible. Dose and peak are relaxed to zero (zero-mode budgets: only incurred <= budget at issue).

Contact uses the router's spatial semantics (the open sub-segments between grid-line cuts with the midpoint cell, and
every cut point with its floor cell, from the router's own core.edge_occupancies on the unit clock) and the EXACT
activity intervals of the cell ([b, b+T) per finite ignition, [0, R) present fire; union over members). An occupancy
[lo, hi] of a cell has contact iff lo < e and hi >= b for some interval. Because this is implied by whole-road contact
(closed cell footprint, half-open activity), every whole-road-admissible lattice route is sweep-admissible: the sweep
is a relaxation, and processing seconds in increasing order makes the first accepted arrival the exact relaxed optimum.
This module deliberately shares no code with the integration's independent checker.
"""
from __future__ import annotations

import math
import time
from fractions import Fraction as F

import numpy as np

SCHEMA = 'wfg.rda.contact-sweep/1'


def _ceil(q):
    return -((-q.numerator) // q.denominator)


class SweepUnsupported(ValueError):
    pass


def contact_sweep(graph, hazard, request, model, *, wall_s, core, check_route_mode, zero_view):
    """Return a core-format result dict (status, legs, arrival, destination, per_member, metrics, provenance)."""
    t_start = time.perf_counter()
    stop = t_start + max(0.0, float(wall_s))
    metrics = {'sweep_seconds': 0, 'contact_edges': 0, 'contact_nodes': 0, 'states_reached': 0}
    member_ids = [m['id'] for m in hazard['members']]

    def finish(status, reason, **extra):
        metrics['wall_s'] = time.perf_counter() - t_start
        out = {'status': status, 'reason': reason, 'legs': [], 'arrival': None, 'destination': None, 'per_member': {},
               'solver_status': status, 'metrics': dict(metrics), 'hazard_version': hazard.get('version'),
               'provenance': {'solver': 'contact_sweep', 'model': 'EXACT_LATTICE_CONTACT_ONLY_SWEEP',
                              'physical_safety_claim': False, 'exposure_mode': 'zero'},
               'certificate_conditions': [], 'exposure_mode': 'zero', 'z_method': 'own_vectorised_time_expanded_sweep'}
        out.update(extra)
        return out

    dt = hazard['dt']
    if dt != 1 or 'node' not in request['position']:
        raise SweepUnsupported('SWEEP_SCOPE_DT1_NODE_POSITION_ONLY')
    dep, hor = F(request['departure']), F(request['horizon'])
    if dep.denominator != 1 or hor.denominator != 1:
        raise SweepUnsupported('SWEEP_INTEGER_CLOCK_REQUIRED')
    dep, hor = int(dep), int(hor)
    complete = core._globally_supported(hazard, request)
    nodes = {n['id']: n for n in graph['nodes']}
    edges = graph['edges']
    E = len(edges)
    eidx = {e['id']: i for i, e in enumerate(edges)}
    forbidden = set(tuple(t) for t in graph['forbidden_turns'])
    origin = request['position']['node']
    incoming = request['incoming_edge']
    budgets = [F(request['budgets']['dose'][m]) for m in member_ids]
    incurred = [F(request['incurred'][m]) for m in member_ids]
    cells = model.cell_intervals

    def cell_contact(cell, lo, hi):
        for b, e in cells.get(cell, ()):
            if lo < e and hi >= b:
                return True
        return False

    # ---- issue (the router's AT_ISSUE rule with contact-only exposure) --------------------------------------
    ocell = core.node_cell(graph, nodes[origin])
    if cell_contact(ocell, F(dep), F(dep)) or any(v > b for v, b in zip(incurred, budgets)):
        return finish('AT_ISSUE_FAILURE', 'AT_ISSUE_CONSTRAINT_VIOLATION')
    # ---- static structures -----------------------------------------------------------------------------------
    head = np.empty(E + 1, dtype=np.int64)
    node_list = list(nodes); nidx = {n: i for i, n in enumerate(node_list)}
    for i, e in enumerate(edges):
        head[i] = nidx[e['v']]
    head[E] = nidx[origin]
    outgoing = {n: [] for n in nodes}
    for i, e in enumerate(edges):
        outgoing[e['u']].append(i)
    # predecessor CSR: for each edge e', the states s (0..E) that may traverse it next
    preds = [[] for _ in range(E)]
    for s in range(E + 1):
        node = node_list[head[s]]
        inc_id = edges[s]['id'] if s < E else incoming
        for j in outgoing[node]:
            if (inc_id, edges[j]['id']) not in forbidden:
                preds[j].append(s)
    has_pred = np.array([len(p) > 0 for p in preds])
    pidx = np.array([s for p in preds for s in p], dtype=np.int64)
    pptr = np.zeros(E + 1, dtype=np.int64); pptr[1:] = np.cumsum([len(p) for p in preds])
    D = np.array([e['travel_ticks'] * dt for e in edges], dtype=np.int64)
    maxD = int(D.max()) if E else 1
    L = maxD + 2
    start_state = E if incoming is None else eidx[incoming]
    if incoming is not None and edges[start_state]['v'] != origin:
        raise SweepUnsupported('INCOMING_CONTEXT')
    # ---- contact masks over start seconds (only edges/nodes meeting an ever-active cell) --------------------
    T1 = hor + 1
    fire_cells = set(cells)
    res = float(graph['grid']['resolution']); x0 = float(graph['grid']['x0']); y0 = float(graph['grid']['y0'])
    Wg = int(graph['grid']['width'])
    fire_rects = []
    for c in fire_cells:
        r, col = divmod(c, Wg)
        fire_rects.append((x0 + col * res - 1, x0 + (col + 1) * res + 1, y0 + r * res - 1, y0 + (r + 1) * res + 1))
    fr = np.array(fire_rects) if fire_rects else np.zeros((0, 4))
    ux = np.array([float(nodes[e['u']]['x']) for e in edges]); uy = np.array([float(nodes[e['u']]['y']) for e in edges])
    vx = np.array([float(nodes[e['v']]['x']) for e in edges]); vy = np.array([float(nodes[e['v']]['y']) for e in edges])
    cand = np.zeros(E, bool)
    if len(fr):
        bx0, bx1 = np.minimum(ux, vx)[:, None], np.maximum(ux, vx)[:, None]
        by0, by1 = np.minimum(uy, vy)[:, None], np.maximum(uy, vy)[:, None]
        cand = ((bx0 <= fr[None, :, 1]) & (bx1 >= fr[None, :, 0]) & (by0 <= fr[None, :, 3]) & (by1 >= fr[None, :, 2])).any(axis=1)
    # Memory repair (20261014): only candidate edges whose contact mask has a blocked second keep a row (the dense
    # (candidates x T1) zero matrix was read column by column, which materialises every zero page on hosts without a
    # shared zero page). Rows without a blocked second never changed `ok`, so the transition set is identical.
    cand_rows = []
    for i in np.flatnonzero(cand):
        e = edges[i]; Dq = F(int(D[i])); row = None
        for o in core.edge_occupancies(e, 0, 1, 0, 1, graph, nodes):
            ivs = cells.get(o['cell'])
            if not ivs:
                continue
            za, zb = F(o['start']), F(o['end'])
            for b, ee in ivs:
                lo_t = max(dep, _ceil(b - Dq * zb))
                hi_t = min(hor, _ceil(ee - Dq * za) - 1)
                if lo_t <= hi_t:
                    if row is None:
                        row = np.zeros(T1, bool)
                    row[lo_t:hi_t + 1] = True
        if row is not None:
            cand_rows.append((int(i), row))
    cand_idx = np.array([i for i, _ in cand_rows], dtype=np.int64)
    eblock = np.array([r for _, r in cand_rows]) if cand_rows else np.zeros((0, T1), bool)
    del cand_rows
    metrics['contact_edges'] = int(cand_idx.size)
    node_block = {}

    def nblock(ni, length):
        key = (ni, length)
        m = node_block.get(key)
        if m is None:
            c = core.node_cell(graph, nodes[node_list[ni]])
            m = np.zeros(T1, bool)
            for b, ee in cells.get(c, ()):
                lo_t = max(0, _ceil(b - length)); hi_t = min(hor, _ceil(ee) - 1)
                if lo_t <= hi_t:
                    m[lo_t:hi_t + 1] = True
            node_block[key] = m
        return m
    waitable = np.array([bool(nodes[node_list[head[s]]]['waitable']) for s in range(E + 1)])
    fire_nodes = set()
    for s in range(E + 1):
        c = core.node_cell(graph, nodes[node_list[head[s]]]) if node_list[head[s]] not in fire_nodes else None
    for ni, n in enumerate(node_list):
        if core.node_cell(graph, nodes[n]) in fire_cells:
            fire_nodes.add(ni)
    # Memory repair (20261014): the WAIT blocking mask is kept only for the waitable states at fire nodes (the same
    # compact form EarliestArrivalBound uses) instead of a dense (E+1) x T1 matrix whose other rows are all False.
    wstates = np.array([s for s in range(E + 1) if waitable[s] and int(head[s]) in fire_nodes], dtype=np.int64)
    wmat = np.array([nblock(int(head[s]), 1) for s in wstates]) if wstates.size else np.zeros((0, T1), bool)
    metrics['contact_nodes'] = len(fire_nodes)
    dests = {}
    for d in request['destinations']:
        dests.setdefault(nidx[d['node']], []).append(d)
    is_dest = np.array([int(head[s]) in dests for s in range(E + 1)])

    def dest_ok(s, t):
        for d in dests[int(head[s])]:
            w = F(d['dwell']); end = t + w
            if end > hor or not any(F(a) <= t and end <= F(b) for a, b in d['open_intervals']):
                continue
            c = core.node_cell(graph, nodes[node_list[head[s]]])
            if cell_contact(c, F(t), end):
                continue
            return True
        return False
    metrics['static_setup_s'] = time.perf_counter() - t_start
    # ---- sweep ------------------------------------------------------------------------------------------------
    RA = np.zeros((L, E + 1), bool); RW = np.zeros((L, E + 1), bool)
    RA[dep % L, start_state] = True
    hist = {}
    found = None
    t = dep
    while t <= hor:
        if (t - dep) % 16 == 0 and time.perf_counter() >= stop:
            return finish('TIMEOUT', 'WALL_CLOCK', solver_status='INCOMPLETE_CAP')
        A = RA[t % L].copy(); Wt = RW[t % L].copy(); RA[t % L] = False; RW[t % L] = False
        act = A | Wt
        hist[t] = (np.packbits(A), np.packbits(Wt))
        metrics['states_reached'] += int(act.sum())
        dc = np.flatnonzero(A & is_dest)
        for s in dc:
            if dest_ok(s, t):
                found = (int(s), t); break
        if found or t >= hor:
            break
        if act.any():
            fl = act[pidx]
            anyp = np.zeros(E, bool)
            if fl.size:
                red = np.logical_or.reduceat(fl, pptr[:-1][has_pred]) if has_pred.any() else np.zeros(0, bool)
                anyp[has_pred] = red
            end = t + D
            ok = anyp & (end <= hor)
            if cand_idx.size:
                ok[cand_idx] &= ~eblock[:, t]
            j = np.flatnonzero(ok)
            RA[end[j] % L, j] = True
            if t + 1 <= hor:
                ws = act & waitable
                if wstates.size:
                    ws[wstates[wmat[:, t]]] = False
                RW[(t + 1) % L, ws] = True
        elif not RA.any() and not RW.any():
            break
        t += 1
        metrics['sweep_seconds'] += 1
    if found is None:
        if time.perf_counter() >= stop:
            return finish('TIMEOUT', 'WALL_CLOCK', solver_status='INCOMPLETE_CAP')
        # structural (forecast-independent) connectivity, as the router reports it
        seen = np.zeros(E + 1, bool); seen[start_state] = True; frontier = [start_state]
        succ = [[] for _ in range(E + 1)]
        for j in range(E):
            for s in preds[j]:
                succ[s].append(j)
        while frontier:
            s = frontier.pop()
            for j in succ[s]:
                if not seen[j]:
                    seen[j] = True; frontier.append(j)
        if not (seen & is_dest).any():
            return finish('DISCONNECTED', 'TURN_GRAPH_DISCONNECTED', solver_status='STRUCTURAL_DISCONNECT',
                          certificate_conditions=['declared directed graph and turn rules', 'independent of forecast',
                                                  'no physical safety claim'])
        return finish('PROVEN_INFEASIBLE' if complete else 'UNSUPPORTED',
                      'EXACT_CONTACT_SWEEP_EXHAUSTED' if complete else 'MISSING_GLOBAL_SUPPORT',
                      solver_status='EXHAUSTED' if complete else 'SUPPORT_INCOMPLETE',
                      certificate_conditions=(['complete contact-only lattice sweep', 'supplied ensemble only',
                                               'no physical safety claim'] if complete else []))
    # ---- witness reconstruction --------------------------------------------------------------------------------
    def reached(tt, flag, s):
        h = hist.get(tt)
        if h is None:
            return False
        bits = h[0] if flag == 'A' else h[1]
        return bool((bits[s >> 3] >> (7 - (s & 7))) & 1)
    legs = []
    s, tt, flag = found[0], found[1], 'A'
    while not (s == start_state and tt == dep and flag == 'A'):
        if flag == 'W':
            legs.append({'kind': 'WAIT', 'node': node_list[head[s]], 'start': tt - 1, 'end': tt})
            tt -= 1
            flag = 'A' if reached(tt, 'A', s) else 'W'
            if not reached(tt, flag, s):
                raise AssertionError('SWEEP_BACKTRACK_WAIT')
            continue
        t0 = tt - int(D[s])
        p = None
        for q in preds[s]:
            for fl_ in ('A', 'W'):
                if reached(t0, fl_, q):
                    p = (q, fl_); break
            if p:
                break
        if p is None:
            raise AssertionError('SWEEP_BACKTRACK_EDGE')
        legs.append({'kind': 'EDGE', 'edge': edges[s]['id'], 'start': t0, 'end': tt, 'from_fraction': 0, 'to_fraction': 1})
        s, tt, flag = p[0], t0, p[1]
    legs.reverse()
    dest = node_list[head[found[0]]]
    checked = check_route_mode(graph, hazard, request, legs, dest, zero_view)
    if not checked['ok']:
        return finish('UNSUPPORTED', 'INDEPENDENT_CHECK_DISAGREEMENT', checker=checked, solver_status='CHECK_FAILURE')
    if time.perf_counter() >= stop:
        return finish('TIMEOUT', 'WALL_CLOCK_AFTER_CHECK', solver_status='INCOMPLETE_CAP',
                      checked_incumbent={'status': 'CHECKED_ROUTE', 'legs': legs, 'arrival': found[1], 'destination': dest,
                                         'per_member': checked['per_member'], 'checker': checked,
                                         'hazard_version': hazard['version'], 'physical_safety_claim': False})
    return finish('CONDITIONAL_OPTIMUM' if complete else 'CHECKED_ROUTE',
                  'EXACT_CONTACT_SWEEP' if complete else 'PARTIAL_GLOBAL_SUPPORT', legs=legs, arrival=found[1],
                  destination=dest, per_member=checked['per_member'], checker=checked,
                  solver_status='EXACT_OPTIMUM' if complete else 'ADMISSIBLE_ONLY',
                  certificate_conditions=(['contact-only relaxation (dose/peak relaxed to zero)', 'supplied ensemble only',
                                           'declared lattice and geometry', 'complete sweep before caps',
                                           'no physical safety claim'] if complete else ['no global optimality claim']))


class EarliestArrivalBound:
    """Exact contact-only earliest-arrival-to-destination values C[t, s] for every lattice state (s = incoming edge
    index, E = issue state; continuation value WITHOUT accepting the destination at t) by a backward sweep over
    seconds, with the same transitions and exact-activity contact as contact_sweep. For a router label (node, incoming
    edge, t, admission) the value

        bound = t                      if admission and the destination is acceptable at t (contact-only), else
        bound = C[t, s]               (min over EDGE / WAIT successors),

    is a lower bound on the arrival of every completion that is admissible in ANY mode whose contact implies exact
    contact (centre / lo / hi router hazard sampling, see MATH_PROOF.md 7.6); +inf proves no admissible completion.
    road_core uses max(opening-aware bound, this bound) as its A* key (admissible; exactness unchanged)."""

    def __init__(self, graph, hazard, request, model, core, *, deadline=None):
        t0 = time.perf_counter()
        dt = hazard['dt']
        if dt != 1 or 'node' not in request['position']:
            raise SweepUnsupported('SWEEP_SCOPE_DT1_NODE_POSITION_ONLY')
        dep, hor = F(request['departure']), F(request['horizon'])
        if dep.denominator != 1 or hor.denominator != 1:
            raise SweepUnsupported('SWEEP_INTEGER_CLOCK_REQUIRED')
        dep, hor = int(dep), int(hor)
        self.dep, self.hor = dep, hor
        nodes = {n['id']: n for n in graph['nodes']}; edges = graph['edges']; E = len(edges)
        self.eidx = {e['id']: i for i, e in enumerate(edges)}
        forbidden = set(tuple(t) for t in graph['forbidden_turns'])
        origin = request['position']['node']; incoming = request['incoming_edge']
        cells = model.cell_intervals
        node_list = list(nodes); nidx = {n: i for i, n in enumerate(node_list)}
        head = np.array([nidx[e['v']] for e in edges] + [nidx[origin]], dtype=np.int64)
        outgoing = {n: [] for n in nodes}
        for i, e in enumerate(edges):
            outgoing[e['u']].append(i)
        sidx, sedge = [], []
        for s in range(E + 1):
            inc_id = edges[s]['id'] if s < E else incoming
            for j in outgoing[node_list[head[s]]]:
                if (inc_id, edges[j]['id']) not in forbidden:
                    sidx.append(s); sedge.append(j)
        sidx = np.array(sidx, dtype=np.int64); sedge = np.array(sedge, dtype=np.int64)
        order = np.argsort(sidx, kind='stable'); sidx, sedge = sidx[order], sedge[order]
        counts = np.bincount(sidx, minlength=E + 1); has = counts > 0
        starts = np.concatenate(([0], np.cumsum(counts)[:-1]))
        D = np.array([e['travel_ticks'] for e in edges], dtype=np.int64)
        T1 = hor + 1
        # contact masks (same construction as contact_sweep)
        res = float(graph['grid']['resolution']); x0 = float(graph['grid']['x0']); y0 = float(graph['grid']['y0'])
        Wg = int(graph['grid']['width'])
        fr = np.array([(x0 + (c % Wg) * res - 1, x0 + (c % Wg + 1) * res + 1, y0 + (c // Wg) * res - 1, y0 + (c // Wg + 1) * res + 1)
                       for c in cells]) if cells else np.zeros((0, 4))
        U = np.array([[float(nodes[e['u']]['x']), float(nodes[e['u']]['y'])] for e in edges])
        V = np.array([[float(nodes[e['v']]['x']), float(nodes[e['v']]['y'])] for e in edges])
        cand = np.zeros(E, bool)
        if len(fr):
            bx0, bx1 = np.minimum(U[:, 0], V[:, 0])[:, None], np.maximum(U[:, 0], V[:, 0])[:, None]
            by0, by1 = np.minimum(U[:, 1], V[:, 1])[:, None], np.maximum(U[:, 1], V[:, 1])[:, None]
            cand = ((bx0 <= fr[None, :, 1]) & (bx1 >= fr[None, :, 0]) & (by0 <= fr[None, :, 3]) & (by1 >= fr[None, :, 2])).any(axis=1)
        eblock = np.zeros((E, 0), bool)
        blocked_edges = {}
        for i in np.flatnonzero(cand):
            m = np.zeros(T1, bool); Dq = F(int(D[i]))
            for o in core.edge_occupancies(edges[i], 0, 1, 0, 1, graph, nodes):
                for b, ee in cells.get(o['cell'], ()):
                    lo_t = max(0, _ceil(b - Dq * F(o['end']))); hi_t = min(hor, _ceil(ee - Dq * F(o['start'])) - 1)
                    if lo_t <= hi_t:
                        m[lo_t:hi_t + 1] = True
            if m.any():
                blocked_edges[int(i)] = m
        self.blocked_edge_list = np.array(sorted(blocked_edges), dtype=np.int64)
        bmat = np.array([blocked_edges[i] for i in self.blocked_edge_list]) if blocked_edges else np.zeros((0, T1), bool)
        waitable = np.array([bool(nodes[node_list[head[s]]]['waitable']) for s in range(E + 1)])

        def nmask(ni, length):
            c = core.node_cell(graph, nodes[node_list[ni]]); m = np.zeros(T1, bool)
            for b, ee in cells.get(c, ()):
                lo_t = max(0, _ceil(b - length)); hi_t = min(hor, _ceil(ee) - 1)
                if lo_t <= hi_t:
                    m[lo_t:hi_t + 1] = True
            return m
        fire_nodes = {ni for ni, n in enumerate(node_list) if core.node_cell(graph, nodes[n]) in cells}
        wstates = np.array([s for s in range(E + 1) if waitable[s] and int(head[s]) in fire_nodes], dtype=np.int64)
        wmat = np.array([nmask(int(head[s]), 1) for s in wstates]) if wstates.size else np.zeros((0, T1), bool)
        # destination acceptance mask per (state, t): admission at a destination head, opening, dwell contact-free
        dest_states = np.flatnonzero(np.isin(head, [nidx[d['node']] for d in request['destinations']]))
        acc = np.zeros((dest_states.size, T1), bool)
        for r_, s in enumerate(dest_states):
            for d in request['destinations']:
                if nidx[d['node']] != head[s]:
                    continue
                w = int(F(d['dwell'])) if F(d['dwell']).denominator == 1 else None
                ok = np.zeros(T1, bool)
                for a, b in d['open_intervals']:
                    a_, b_ = F(a), F(b)
                    lo_t = max(dep, _ceil(a_)); hi_t = min(hor, int(math.floor(b_ - F(d['dwell']))), int(math.floor(hor - F(d['dwell']))))
                    if lo_t <= hi_t:
                        ok[lo_t:hi_t + 1] = True
                ok &= ~nmask(int(head[s]), F(d['dwell']))
                acc[r_] |= ok
        self.dest_states = dest_states; self.acc = acc
        self.dest_row = -np.ones(E + 1, dtype=np.int64); self.dest_row[dest_states] = np.arange(dest_states.size)
        INF = np.iinfo(np.int16).max
        self.INF = INF
        # Memory repair (20261014): (1) only seconds dep..hor+1 are stored (row i <-> second dep + i; earlier rows were
        # never written nor read); (2) the admission-arrival table Aval is not stored: it equals C except that
        # Aval[t, s] = t where s is a destination state accepting at t (acc), and is derived on demand below with the
        # same values (rows not yet written in the backward sweep stay INF exactly as before).
        C = np.full((hor - dep + 2, E + 1), INF, dtype=np.int16)    # last row (second hor+1): beyond horizon
        dest_row = self.dest_row
        sd_idx = np.flatnonzero(dest_row[sedge] >= 0)      # successor pairs entering a destination state (static)
        sd_row = dest_row[sedge[sd_idx]]
        brow = -np.ones(E, dtype=np.int64); brow[self.blocked_edge_list] = np.arange(self.blocked_edge_list.size)
        wrow = -np.ones(E + 1, dtype=np.int64); wrow[wstates] = np.arange(wstates.size)
        pos_b = self.blocked_edge_list
        for t in range(hor, dep - 1, -1):
            if deadline is not None and (hor - t) % 64 == 0 and time.perf_counter() >= deadline:
                raise TimeoutError('EA_BOUND_WALL_CAP')
            arr = t + D[sedge]
            v = np.full(sedge.size, INF, dtype=np.int16)
            okm = arr <= hor
            v[okm] = C[arr[okm] - dep, sedge[okm]]
            if sd_idx.size:
                a_ = arr[sd_idx]
                k_ = np.flatnonzero((a_ <= hor) & (a_ > t))
                if k_.size:
                    k_ = k_[acc[sd_row[k_], a_[k_]]]
                    v[sd_idx[k_]] = a_[k_]
            if pos_b.size:
                bl = brow[sedge] >= 0
                bl_idx = np.flatnonzero(bl)
                blocked = bmat[brow[sedge[bl_idx]], t]
                v[bl_idx[blocked]] = INF
            row = np.full(E + 1, INF, dtype=np.int16)
            if sedge.size:
                red = np.minimum.reduceat(v, starts[has])
                row[has] = red
            if t + 1 <= hor:
                wv = C[t + 1 - dep].copy()
                wv[~waitable] = INF
                if wstates.size:
                    wb = wmat[:, t]; wv[wstates[wb]] = INF
                row = np.minimum(row, wv)
            C[t - dep] = row
        self.C = C
        self.node_index = {n: i for i, n in enumerate(node_list)}
        self.E = E
        self.build_s = time.perf_counter() - t0
        self.bytes = C.nbytes

    def bound(self, node, incoming, t, admission):
        """Lower bound on any admissible completion's arrival from this label (math.inf if none)."""
        ti = F(t)
        if ti.denominator != 1:
            return 0
        ti = int(ti)
        if ti < self.dep or ti > self.hor:
            return 0 if ti < self.dep else math.inf
        s = self.E if incoming is None else self.eidx[incoming]
        r = int(self.dest_row[s])
        if admission and r >= 0 and self.acc[r, ti]:
            v = ti                                   # = Aval[ti, s] of the unrepaired build
        else:
            v = int(self.C[ti - self.dep, s])        # = Aval[ti, s] (non-accepting) or C[ti, s]
        return math.inf if v == self.INF else v
