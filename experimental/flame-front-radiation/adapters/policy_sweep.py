"""Five-policy constraint sweep under law v1 (contact only, regression) or law v2 (test-only adapter).

Lattice grammar: re-implemented from the byte-identical copy ``frozen_copy/zsweep.py`` (``contact_sweep``): states are
(directed edge just traversed, integer second, admission flag); the issue state has no incoming edge; an EDGE leaves
the head node at t when the turn is not forbidden and t + travel_ticks <= horizon and arrives with admission at
t + D; a WAIT at a waitable node moves to t + 1 without admission; a destination is accepted on an admitted arrival at
t when an opening contains [t, t + dwell] and t + dwell <= horizon. Contact uses the frozen router geometry
(``core.edge_occupancies`` on the unit clock, closed cells) and the exact v1 activity intervals of every member.

Policies (as in research/routing/final-input-ablation): A0 travel only, A1 flame contact, A2 contact + peak,
A3 contact + dose, A4 full (contact + peak + dose). Under v2 the peak and dose terms come from the planning tables of
``flux_tables`` (probe points, 10 s grid, linear interpolation); every returned route is then re-checked with the
exact law (``journey_check.check_v2``).

* A0, A1, A2: exact earliest arrival of the planning model by a forward sweep (blocked traversals and waits removed).
* A3, A4: lower bound = earliest admitted destination time at which, for every member separately, the minimum planned
  dose over all lattice paths (per-member dynamic programme) plus the dwell dose is within budget; upper bound = the
  earliest route among sweeps that additionally block every traversal and wait whose planned flux exceeds a threshold
  theta (theta from a fixed decreasing ladder), accepted when its planned dose fits every member's budget. Equal
  bounds prove the planning-model optimum; an empty per-member programme proves planning-model infeasibility.
Model-relative only; no physical-safety claim.
"""
from __future__ import annotations

import math
import sys
import time
from fractions import Fraction as F
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "frozen_copy"))
from routing import core  # noqa: E402

THETA_LADDER = (None, 10.0, 5.0, 2.0, 1.0, 0.5, 0.2, 0.1, 0.05, 0.02, 0.01, 0.0)
POLICIES = {"A0": (False, False, False), "A1": (True, False, False), "A2": (True, True, False),
            "A3": (True, False, True), "A4": (True, True, True)}


def _ceil(q):
    return -((-q.numerator) // q.denominator)


class Problem:
    """Static lattice structure, contact masks and (optionally) v2 planning exposure for one mission."""

    def __init__(self, case, *, tables=None, probes=None, grid_dt=10.0, E_panel=100.0, E_inflame=100.0):
        g, req = case.graph, case.request
        self.case = case
        self.graph = g
        self.req = req
        self.dep, self.hor = int(F(req["departure"])), int(F(req["horizon"]))
        nodes = {n["id"]: n for n in g["nodes"]}
        self.nodes = nodes
        edges = g["edges"]; self.edges = edges
        E = len(edges); self.E = E
        self.eidx = {e["id"]: i for i, e in enumerate(edges)}
        forbidden = set(tuple(t) for t in g["forbidden_turns"])
        origin = req["position"]["node"]; incoming = req["incoming_edge"]
        self.node_list = list(nodes); nidx = {n: i for i, n in enumerate(self.node_list)}; self.nidx = nidx
        head = np.empty(E + 1, np.int64)
        for i, e in enumerate(edges):
            head[i] = nidx[e["v"]]
        head[E] = nidx[origin]
        self.head = head
        outgoing = {n: [] for n in nodes}
        for i, e in enumerate(edges):
            outgoing[e["u"]].append(i)
        preds = [[] for _ in range(E)]
        for s in range(E + 1):
            node = self.node_list[head[s]]
            inc_id = edges[s]["id"] if s < E else incoming
            for j in outgoing[node]:
                if (inc_id, edges[j]["id"]) not in forbidden:
                    preds[j].append(s)
        self.preds = preds
        self.has_pred = np.array([len(p) > 0 for p in preds])
        self.pidx = np.array([s for p in preds for s in p], dtype=np.int64)
        self.pptr = np.zeros(E + 1, np.int64); self.pptr[1:] = np.cumsum([len(p) for p in preds])
        self.D = np.array([e["travel_ticks"] for e in edges], np.int64)   # dt = 1 s in every frozen packet
        self.L = int(self.D.max()) + 2
        self.start_state = E if incoming is None else self.eidx[incoming]
        self.waitable = np.array([bool(nodes[self.node_list[head[s]]]["waitable"]) for s in range(E + 1)])
        self.dests = {}
        for d in req["destinations"]:
            self.dests.setdefault(nidx[d["node"]], []).append(d)
        self.is_dest = np.array([int(head[s]) in self.dests for s in range(E + 1)])
        self.T1 = self.hor + 1
        self._contact_masks()
        self.tables = tables
        self.probes = probes
        self.grid_dt = grid_dt
        self.E_panel, self.E_inflame = E_panel, E_inflame
        self.M = len(case.member_ids)
        if tables is not None:
            self._prepare_exposure()

    # ---- contact (exact v1 activity, frozen router geometry) ---------------------------------------------------
    def _contact_masks(self):
        case, g = self.case, self.graph
        H, Wd = case.grid.height, case.grid.width
        cells = {}
        for m in case.members:
            ign = np.asarray(m["ignition_time_s"], float); T = F(m["burning_duration_s"])
            for r, c in zip(*np.nonzero(np.isfinite(ign))):
                b = F(float(ign[r, c]))
                cells.setdefault((H - 1 - r) * Wd + c, set()).add((b, b + T))
            R = F(m["remaining_s"])
            if R > 0:
                for r, c in zip(*np.nonzero(np.asarray(m["current_active"], bool))):
                    cells.setdefault((H - 1 - r) * Wd + c, set()).add((F(0), R))
        self.cell_intervals = {k: sorted(v) for k, v in cells.items()}
        dep, hor, T1 = self.dep, self.hor, self.T1
        nodes, edges = self.nodes, self.edges
        res = float(g["grid"]["resolution"]); x0 = float(g["grid"]["x0"]); y0 = float(g["grid"]["y0"])
        Wg = int(g["grid"]["width"])
        fr = np.array([(x0 + (c % Wg) * res - 1, x0 + (c % Wg + 1) * res + 1, y0 + (c // Wg) * res - 1,
                        y0 + (c // Wg + 1) * res + 1) for c in self.cell_intervals]) if self.cell_intervals else np.zeros((0, 4))
        U = np.array([[float(nodes[e["u"]]["x"]), float(nodes[e["u"]]["y"])] for e in edges])
        V = np.array([[float(nodes[e["v"]]["x"]), float(nodes[e["v"]]["y"])] for e in edges])
        cand = np.zeros(len(edges), bool)
        if len(fr):
            bx0, bx1 = np.minimum(U[:, 0], V[:, 0])[:, None], np.maximum(U[:, 0], V[:, 0])[:, None]
            by0, by1 = np.minimum(U[:, 1], V[:, 1])[:, None], np.maximum(U[:, 1], V[:, 1])[:, None]
            cand = ((bx0 <= fr[None, :, 1]) & (bx1 >= fr[None, :, 0]) & (by0 <= fr[None, :, 3]) & (by1 >= fr[None, :, 2])).any(1)
        rows = []
        for i in np.flatnonzero(cand):
            e = edges[i]; Dq = F(int(self.D[i])); row = None
            for o in core.edge_occupancies(e, 0, 1, 0, 1, g, nodes):
                for b, ee in self.cell_intervals.get(o["cell"], ()):
                    lo_t = max(dep, _ceil(b - Dq * F(o["end"]))); hi_t = min(hor, _ceil(ee - Dq * F(o["start"])) - 1)
                    if lo_t <= hi_t:
                        if row is None:
                            row = np.zeros(T1, bool)
                        row[lo_t:hi_t + 1] = True
            if row is not None:
                rows.append((int(i), row))
        self.c_idx = np.array([i for i, _ in rows], np.int64)
        self.c_block = np.array([r for _, r in rows]) if rows else np.zeros((0, T1), bool)

        def nmask(ni, length):
            c = core.node_cell(g, nodes[self.node_list[ni]]); m = np.zeros(T1, bool)
            for b, ee in self.cell_intervals.get(c, ()):
                lo_t = max(0, _ceil(b - length)); hi_t = min(hor, _ceil(ee) - 1)
                if lo_t <= hi_t:
                    m[lo_t:hi_t + 1] = True
            return m
        self.nmask = nmask
        fire_nodes = {ni for ni, n in enumerate(self.node_list) if core.node_cell(g, nodes[n]) in self.cell_intervals}
        self.w_states = np.array([s for s in range(self.E + 1) if self.waitable[s] and int(self.head[s]) in fire_nodes], np.int64)
        self.w_block = np.array([nmask(int(self.head[s]), 1) for s in self.w_states]) if self.w_states.size else np.zeros((0, T1), bool)

    def contact_at_issue(self):
        c = core.node_cell(self.graph, self.nodes[self.req["position"]["node"]])
        return any(F(self.dep) < e and F(self.dep) >= b for b, e in self.cell_intervals.get(c, ()))

    # ---- v2 planning exposure -------------------------------------------------------------------------------------
    def _prepare_exposure(self):
        pr = self.probes
        ed, pk, zz, Dk = [], [], [], []
        for ei, (idx, z) in pr.edge_probes.items():
            ed.append(np.full(idx.size, ei)); pk.append(idx); zz.append(z); Dk.append(np.full(idx.size, self.D[ei]))
        if ed:
            self.ep_edge = np.concatenate(ed); self.ep_probe = np.concatenate(pk); self.ep_z = np.concatenate(zz)
            self.ep_D = np.concatenate(Dk).astype(float)
            starts = np.r_[0, np.flatnonzero(np.diff(self.ep_edge)) + 1]
            self.ep_starts = starts
            self.near_edges = self.ep_edge[starts]
        else:
            self.ep_edge = np.zeros(0, np.int64); self.near_edges = np.zeros(0, np.int64)
        # combined planning flux per member on the grid: q = E * rad + eng * E_inflame
        self.Q = [(self.E_panel * rad.astype(np.float64) + self.E_inflame * eng.astype(np.float64))
                  for rad, eng in self.tables]
        self.nt = self.Q[0].shape[1] if self.Q else 0
        # node probes of every lattice state's head node (waits and dwell)
        self.state_probe = pr.node_probe[self.head]

    def _interp(self, m, probe, tt):
        g = tt / self.grid_dt
        i0 = np.clip(np.floor(g).astype(np.int64), 0, self.nt - 2)
        w = np.clip(g - i0, 0.0, 1.0)
        Q = self.Q[m]
        return (1 - w) * Q[probe, i0] + w * Q[probe, i0 + 1]

    def edge_exposure(self, t):
        """Planned (peak[M, nE], dose[M, nE]) for traversals of the near edges starting at second t."""
        if self.ep_edge.size == 0:
            return np.zeros((self.M, 0)), np.zeros((self.M, 0))
        tt = t + self.ep_D * self.ep_z
        peaks, doses = [], []
        for m in range(self.M):
            v = self._interp(m, self.ep_probe, tt)
            pk = np.maximum.reduceat(v, self.ep_starts)
            trap = 0.5 * (v[:-1] + v[1:]) * np.diff(tt)
            same = self.ep_edge[:-1] == self.ep_edge[1:]
            trap = np.where(same, trap, 0.0)
            ds = np.add.reduceat(np.r_[trap, 0.0], self.ep_starts)
            peaks.append(pk); doses.append(ds)
        return np.array(peaks), np.array(doses)

    def node_series(self, ni, t0, t1):
        """Planned flux [M, n] of node ni at integer seconds t0..t1 (zero if the node has no probe)."""
        pid = self.probes.node_probe[ni] if self.tables is not None else -1
        ts = np.arange(t0, t1 + 1, dtype=float)
        if pid < 0:
            return np.zeros((self.M, ts.size))
        return np.array([self._interp(m, np.full(ts.size, pid), ts) for m in range(self.M)])

    def wait_exposure(self, t):
        """Planned (peak[M, S], dose[M, S]) of a one-second wait starting at t, for every state with a node probe."""
        sp = self.state_probe
        ok = sp >= 0
        pk = np.zeros((self.M, self.E + 1)); ds = np.zeros((self.M, self.E + 1))
        if ok.any():
            for m in range(self.M):
                a = self._interp(m, sp[ok], np.full(ok.sum(), float(t)))
                b = self._interp(m, sp[ok], np.full(ok.sum(), float(t + 1)))
                pk[m, ok] = np.maximum(a, b); ds[m, ok] = 0.5 * (a + b)
        return pk, ds


def _dest_ok_factory(P, contact, peak_lim, budgets=None):
    hor = P.hor
    cache = {}

    def dest_ok(s, t, dose_vec=None):
        ni = int(P.head[s])
        for d in P.dests[ni]:
            w = F(d["dwell"]); end = t + w
            if end > hor or not any(F(a) <= t and end <= F(b) for a, b in d["open_intervals"]):
                continue
            if contact:
                c = core.node_cell(P.graph, P.nodes[P.node_list[ni]])
                if any(F(t) < e and end >= b for b, e in P.cell_intervals.get(c, ())):
                    continue
            if peak_lim is not None or budgets is not None:
                key = (ni, t, int(d["dwell"]))
                ser = cache.get(key)
                if ser is None:
                    ser = cache[key] = P.node_series(ni, t, t + int(d["dwell"]))
                if peak_lim is not None and ser.max(initial=0.0) > peak_lim:
                    continue
                if budgets is not None and dose_vec is not None:
                    dd = 0.5 * (ser[:, :-1] + ser[:, 1:]).sum(axis=1)
                    if np.any(dose_vec + dd > budgets):
                        continue
            return True
        return False
    return dest_ok


def reach_sweep(P, *, contact=True, peak_lim=None, theta=None, wall_s=600.0):
    """Earliest admitted arrival (exact for the planning model) with optional peak limit and flux threshold theta.

    Returns dict(status, arrival, legs, destination)."""
    t_start = time.perf_counter()
    E, L, dep, hor = P.E, P.L, P.dep, P.hor
    block_lim = None
    if peak_lim is not None or theta is not None:
        block_lim = min(x for x in (peak_lim, theta) if x is not None)
    if contact and P.contact_at_issue():
        return {"status": "AT_ISSUE_FAILURE"}
    if peak_lim is not None and P.tables is not None:
        if P.node_series(int(P.head[P.start_state]), dep, dep).max() > peak_lim:
            return {"status": "AT_ISSUE_FAILURE"}
    dest_ok = _dest_ok_factory(P, contact, block_lim if P.tables is not None else None)
    RA = np.zeros((L, E + 1), bool); RW = np.zeros((L, E + 1), bool)
    RA[dep % L, P.start_state] = True
    hist = {}
    found = None
    t = dep
    while t <= hor:
        if time.perf_counter() - t_start > wall_s:
            return {"status": "TIMEOUT"}
        A = RA[t % L].copy(); Wt = RW[t % L].copy(); RA[t % L] = False; RW[t % L] = False
        act = A | Wt
        hist[t] = (np.packbits(A), np.packbits(Wt))
        for s in np.flatnonzero(A & P.is_dest):
            if dest_ok(s, t):
                found = (int(s), t); break
        if found or t >= hor:
            break
        if act.any():
            fl = act[P.pidx]
            anyp = np.zeros(E, bool)
            if fl.size:
                anyp[P.has_pred] = np.logical_or.reduceat(fl, P.pptr[:-1][P.has_pred])
            end = t + P.D
            ok = anyp & (end <= hor)
            if contact and P.c_idx.size:
                ok[P.c_idx] &= ~P.c_block[:, t]
            if block_lim is not None and P.tables is not None and P.near_edges.size:
                pk, _ = P.edge_exposure(t)
                ok[P.near_edges] &= ~(pk.max(axis=0) > block_lim)
            j = np.flatnonzero(ok)
            RA[end[j] % L, j] = True
            if t + 1 <= hor:
                ws = act & P.waitable
                if contact and P.w_states.size:
                    ws[P.w_states[P.w_block[:, t]]] = False
                if block_lim is not None and P.tables is not None:
                    wpk, _ = P.wait_exposure(t)
                    ws &= ~(wpk.max(axis=0) > block_lim)
                RW[(t + 1) % L, ws] = True
        elif not RA.any() and not RW.any():
            break
        t += 1
    if found is None:
        return {"status": "EXHAUSTED"}
    legs = _backtrack(P, hist, found)
    return {"status": "ROUTE", "arrival": found[1], "legs": legs, "destination": P.node_list[P.head[found[0]]]}


def _backtrack(P, hist, found):
    E, dep = P.E, P.dep

    def reached(tt, flag, s):
        h = hist.get(tt)
        if h is None:
            return False
        bits = h[0] if flag == "A" else h[1]
        return bool((bits[s >> 3] >> (7 - (s & 7))) & 1)
    legs = []
    s, tt, flag = found[0], found[1], "A"
    while not (s == P.start_state and tt == dep and flag == "A"):
        if flag == "W":
            legs.append({"kind": "WAIT", "node": P.node_list[P.head[s]], "start": tt - 1, "end": tt})
            tt -= 1
            flag = "A" if reached(tt, "A", s) else "W"
            continue
        t0 = tt - int(P.D[s])
        p = None
        for q in P.preds[s]:
            for fl_ in ("A", "W"):
                if reached(t0, fl_, q):
                    p = (q, fl_); break
            if p:
                break
        if p is None:
            raise AssertionError("SWEEP_BACKTRACK_EDGE")
        legs.append({"kind": "EDGE", "edge": P.edges[s]["id"], "start": t0, "end": tt, "from_fraction": 0, "to_fraction": 1})
        s, tt, flag = p[0], t0, p[1]
    legs.reverse()
    return legs


def mindose_lower_bound(P, *, peak_lim=None, wall_s=900.0):
    """Earliest admitted destination time compatible with every member's separate minimum planned dose (contact on).

    Returns dict(status, lb_arrival or None)."""
    t_start = time.perf_counter()
    E, L, dep, hor, M = P.E, P.L, P.dep, P.hor, P.M
    budgets = np.array([float(P.req["budgets"]["dose"][m]) for m in P.case.member_ids])
    inc = np.array([float(P.req["incurred"][m]) for m in P.case.member_ids])
    if P.contact_at_issue() or np.any(inc > budgets):
        return {"status": "AT_ISSUE_FAILURE"}
    dest_ok = _dest_ok_factory(P, True, peak_lim, budgets)
    INF = np.inf
    DA = np.full((L, E + 1, M), INF, np.float32); DW = np.full((L, E + 1, M), INF, np.float32)
    DA[dep % L, P.start_state] = inc
    near = P.near_edges
    t = dep
    while t <= hor:
        if time.perf_counter() - t_start > wall_s:
            return {"status": "TIMEOUT"}
        A = DA[t % L].copy(); Wv = DW[t % L].copy(); DA[t % L] = INF; DW[t % L] = INF
        for s in np.flatnonzero(np.isfinite(A).all(axis=1) & P.is_dest):
            if dest_ok(s, t, A[s].astype(float)):
                return {"status": "BOUND", "lb_arrival": t}
        if t >= hor:
            break
        best = np.minimum(A, Wv)
        fin = np.isfinite(best).any(axis=1)
        if fin.any():
            vals = best[P.pidx]
            cand = np.full((E, M), INF, np.float32)
            if vals.size:
                cand[P.has_pred] = np.minimum.reduceat(vals, P.pptr[:-1][P.has_pred], axis=0)
            end = t + P.D
            ok = np.isfinite(cand).any(axis=1) & (end <= hor)
            if P.c_idx.size:
                ok[P.c_idx] &= ~P.c_block[:, t]
            if near.size:
                pk, ds = P.edge_exposure(t)
                if peak_lim is not None:
                    ok[near] &= ~(pk.max(axis=0) > peak_lim)
                cand[near] = cand[near] + ds.T.astype(np.float32)
            cand[cand > budgets[None, :].astype(np.float32) * (1 + 1e-6)] = INF
            j = np.flatnonzero(ok)
            slots = end[j] % L
            DA[slots, j] = np.minimum(DA[slots, j], cand[j])
            if t + 1 <= hor:
                wv = best.copy()
                wv[~P.waitable] = INF
                if P.w_states.size:
                    wv[P.w_states[P.w_block[:, t]]] = INF
                if P.tables is not None:
                    wpk, wds = P.wait_exposure(t)
                    if peak_lim is not None:
                        wv[wpk.max(axis=0) > peak_lim] = INF
                    wv = wv + wds.T.astype(np.float32)
                    wv[wv > budgets[None, :].astype(np.float32) * (1 + 1e-6)] = INF
                DW[(t + 1) % L] = np.minimum(DW[(t + 1) % L], wv)
        t += 1
    return {"status": "INFEASIBLE"}


def planned_route_exposure(P, legs, destination):
    """Planned per-member (peak, dose added) of a route under the planning tables (incurred excluded)."""
    M = P.M
    peak = np.zeros(M); dose = np.zeros(M)
    near = {int(e): k for k, e in enumerate(P.near_edges)} if P.tables is not None else {}
    for leg in legs:
        if leg["kind"] == "EDGE":
            ei = P.eidx[leg["edge"]]
            if ei in near:
                pk, ds = P.edge_exposure(int(leg["start"]))
                peak = np.maximum(peak, pk[:, near[ei]]); dose += ds[:, near[ei]]
        else:
            ni = P.nidx[leg["node"]]
            ser = P.node_series(ni, int(leg["start"]), int(leg["end"]))
            peak = np.maximum(peak, ser.max(axis=1)); dose += 0.5 * (ser[:, :-1] + ser[:, 1:]).sum(axis=1)
    arrival = int(legs[-1]["end"]) if legs else P.dep
    d = {x["node"]: x for x in P.req["destinations"]}[destination]
    ser = P.node_series(P.nidx[destination], arrival, arrival + int(d["dwell"]))
    peak = np.maximum(peak, ser.max(axis=1)); dose += 0.5 * (ser[:, :-1] + ser[:, 1:]).sum(axis=1)
    return peak, dose
