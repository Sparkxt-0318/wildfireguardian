"""Synthetic radial power distribution network along roads.

Construction:
1. Road polylines are densified into candidate pole positions every
   `pole_spacing_m`; road vertices closer than 3 m are merged so intersections
   connect.
2. A shortest-path tree is grown from the pole nearest the substation.
3. Each building is connected to its nearest pole (service drop).
4. The tree is pruned to poles that lead to at least one building.
5. Protection: every child of the root starts a feeder with a breaker. At
   every branch point the child with the largest downstream load continues the
   main line; every other child starts a lateral protected by a fuse. Every
   pole that serves buildings has a transformer with its own cutout fuse.
A permanent fault on a span operates the nearest protective device upstream
and de-energises everything below it.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np
from scipy import sparse
from scipy.sparse.csgraph import dijkstra, connected_components
from scipy.spatial import cKDTree


def _densify(roads, spacing):
    pts, edges = [], []
    key_to_idx = {}

    def get(p):
        k = (round(p[0] / 3.0), round(p[1] / 3.0))
        if k not in key_to_idx:
            key_to_idx[k] = len(pts)
            pts.append(p)
        return key_to_idx[k]

    for r in roads:
        xy = np.asarray(r["xy"], dtype=float)
        for a, b in zip(xy[:-1], xy[1:]):
            L = float(np.hypot(*(b - a)))
            n = max(1, int(np.ceil(L / spacing)))
            prev = get(tuple(a))
            for i in range(1, n + 1):
                q = a + (b - a) * i / n
                cur = get(tuple(q))
                if cur != prev:
                    edges.append((prev, cur, L / n))
                prev = cur
    return np.asarray(pts), edges


class PowerNetwork:
    def __init__(self, world, buildings_xy, cfg):
        self.cfg = cfg
        P, E = _densify(world["roads"], cfg["pole_spacing_m"])
        n = len(P)
        e = np.asarray(E)
        A = sparse.coo_matrix((e[:, 2], (e[:, 0].astype(int), e[:, 1].astype(int))), shape=(n, n)).tocsr()
        A = A.maximum(A.T)
        sub = np.array([world["substation"]["x"], world["substation"]["y"]])
        # Root: nearest pole in the largest connected road component.
        ncomp, lab = connected_components(A, directed=False)
        big = np.argmax(np.bincount(lab))
        cand = np.where(lab == big)[0]
        root = int(cand[np.argmin(np.hypot(*(P[cand] - sub).T))])
        dist, pred = dijkstra(A, directed=False, indices=root, return_predecessors=True)
        reach = np.isfinite(dist)
        tree = cKDTree(P[reach])
        reach_idx = np.where(reach)[0]
        d_b, j = tree.query(buildings_xy)
        self.building_pole = reach_idx[j]
        self.service_drop_m = d_b
        served = np.zeros(n, bool)
        served[self.building_pole] = True
        # Prune: keep poles on paths from root to served poles.
        keep = np.zeros(n, bool)
        for p in np.where(served)[0]:
            while p >= 0 and not keep[p]:
                keep[p] = True
                p = pred[p]
        old_ids = np.where(keep)[0]
        remap = -np.ones(n, int)
        remap[old_ids] = np.arange(len(old_ids))
        self.pole_xy = P[old_ids]
        self.n_poles = len(old_ids)
        self.root = int(remap[root])
        self.parent = np.array([remap[pred[o]] if pred[o] >= 0 else -1 for o in old_ids])
        self.parent[self.root] = -1
        self.building_pole = remap[self.building_pole]
        self.children = defaultdict(list)
        for c, p in enumerate(self.parent):
            if p >= 0:
                self.children[p].append(c)
        self._order()
        self._protection()

    def _order(self):
        order = [self.root]
        i = 0
        while i < len(order):
            order.extend(self.children[order[i]])
            i += 1
        self.topo = np.array(order)  # parents before children
        load = np.bincount(self.building_pole, minlength=self.n_poles).astype(int)
        self.direct_load = load.copy()
        for p in self.topo[::-1]:
            if self.parent[p] >= 0:
                load[self.parent[p]] += load[p]
        self.load = load

    def _protection(self):
        """Assign protective devices. dev_on_edge[c] = device protecting the span parent(c)->c, or -1.

        - breaker: head of a feeder circuit. Children of the root, plus the
          heaviest laterals up to n_feeders in total. Such laterals are modelled
          as separate circuits from the substation bus that share the road
          right-of-way, so faults upstream of their head do not reach them.
        - recloser: on every main line, every recloser_spacing_m of line length.
        - fuse: head of every other lateral.
        - transformer: cutout fuse of every pole with buildings attached.
        """
        cfg = self.cfg
        devices = []
        dev_on_edge = -np.ones(self.n_poles, int)
        heads = list(self.children[self.root])
        laterals = []
        self.main_child = -np.ones(self.n_poles, int)
        for p in self.topo:
            ch = self.children[p]
            if not ch:
                continue
            main = max(ch, key=lambda c: self.load[c])
            if p != self.root:
                self.main_child[p] = main
                laterals.extend(c for c in ch if c != main)
        laterals.sort(key=lambda c: -self.load[c])
        n_extra = max(0, cfg.get("n_feeders", 1) - len(heads))
        heads += laterals[:n_extra]
        for c in heads:
            dev_on_edge[c] = len(devices)
            devices.append({"kind": "breaker", "pole": int(c)})
        for c in laterals[n_extra:]:
            dev_on_edge[c] = len(devices)
            devices.append({"kind": "fuse", "pole": int(c)})
        # Reclosers along main lines, by cumulative line length from the circuit head.
        spacing = cfg.get("recloser_spacing_m", 0)
        if spacing > 0:
            run = np.zeros(self.n_poles)
            for p in self.topo:
                if p == self.root:
                    continue
                q = self.parent[p]
                seg = float(np.hypot(*(self.pole_xy[p] - self.pole_xy[q])))
                if dev_on_edge[p] >= 0:
                    run[p] = 0.0
                else:
                    run[p] = run[q] + seg
                    if run[p] >= spacing and self.load[p] >= cfg.get("recloser_min_load", 20):
                        dev_on_edge[p] = len(devices)
                        devices.append({"kind": "recloser", "pole": int(p)})
                        run[p] = 0.0
        # Transformer cutouts: one per pole with buildings attached.
        self.xfmr_of_pole = -np.ones(self.n_poles, int)
        for p in np.where(self.direct_load > 0)[0]:
            self.xfmr_of_pole[p] = len(devices)
            devices.append({"kind": "transformer", "pole": int(p)})
        self.devices = devices
        self.dev_on_edge = dev_on_edge
        # Nearest upstream line device for every pole (protects span parent(p)->p).
        up = -np.ones(self.n_poles, int)
        for p in self.topo:
            if p == self.root:
                continue
            up[p] = dev_on_edge[p] if dev_on_edge[p] >= 0 else up[self.parent[p]]
        self.upstream_device = up
        # Ancestor line devices for each pole (for outage propagation).
        anc = [[] for _ in range(self.n_poles)]
        for p in self.topo:
            if p == self.root:
                continue
            d = dev_on_edge[p]
            if d >= 0 and devices[d]["kind"] == "breaker":
                base = [int(d)]
            else:
                base = list(anc[self.parent[p]])
                if d >= 0:
                    base.append(int(d))
            anc[p] = base
        self.pole_ancestors = anc
        # Buildings downstream of each device.
        nb = len(self.building_pole)
        self.building_devices = []
        for b in range(nb):
            p = self.building_pole[b]
            self.building_devices.append(anc[p] + [int(self.xfmr_of_pole[p])])
        self.device_buildings = defaultdict(list)
        for b, devs in enumerate(self.building_devices):
            for d in devs:
                self.device_buildings[d].append(b)
        # Depth of devices (number of device ancestors) to order upstream->downstream.
        self.device_depth = np.zeros(len(devices), int)
        for d, dev in enumerate(devices):
            p = dev["pole"]
            self.device_depth[d] = len(anc[p]) - (1 if dev["kind"] != "transformer" else 0)

    def spans(self):
        """List of (child_pole, midpoint_xy) for every span parent->child."""
        c = np.array([p for p in range(self.n_poles) if self.parent[p] >= 0])
        mid = 0.5 * (self.pole_xy[c] + self.pole_xy[self.parent[c]])
        return c, mid

    def simulate_outages(self, fire_T_at, cfg_grid, t_end, rng):
        """Device operation times (min, inf if none) and cause.

        Causes: 'fire_grid' (fire faults a span; the nearest upstream device
        operates), 'fire_local' (fire reaches a transformer pole; only that
        transformer's customers lose power), 'random_grid' (unrelated).

        fire_T_at: callable mapping (N,2) xy -> fire arrival minutes.
        """
        mult = cfg_grid["grid_failure_multiplier"]
        nd = len(self.devices)
        t_op = np.full(nd, np.inf)
        cause = np.array(["none"] * nd, dtype=object)
        # Fire-caused span faults.
        c, mid = self.spans()
        Ts = np.minimum(np.minimum(fire_T_at(mid), fire_T_at(self.pole_xy[c])), fire_T_at(self.pole_xy[self.parent[c]]))
        p_fault = min(1.0, cfg_grid["p_span_fault_given_fire"] * mult)
        p_xf = min(1.0, cfg_grid["p_transformer_fault_given_fire"] * mult)
        hit = (Ts <= t_end) & (rng.random(len(c)) < p_fault)
        lo, hi = cfg_grid["span_fault_delay_min"]
        tf = Ts + rng.uniform(lo, hi, len(c))
        for child, t in zip(c[hit], tf[hit]):
            d = self.upstream_device[child]
            if d >= 0 and t < t_op[d]:
                t_op[d], cause[d] = t, "fire_grid"
        # Transformer faults when fire reaches the transformer pole.
        for d, dev in enumerate(self.devices):
            if dev["kind"] == "transformer":
                tp = float(fire_T_at(self.pole_xy[dev["pole"]][None, :])[0])
                if tp <= t_end and rng.random() < p_xf:
                    t = tp + rng.uniform(lo, hi)
                    if t < t_op[d]:
                        t_op[d], cause[d] = t, "fire_local"
        # Random unrelated device operations.
        for d, dev in enumerate(self.devices):
            rate = (cfg_grid["random_breaker_rate_per_h"] if dev["kind"] in ("breaker", "recloser")
                    else cfg_grid["random_fuse_rate_per_h"]) * mult
            if rng.random() < 1 - np.exp(-rate * t_end / 60.0):
                t = rng.uniform(0, t_end)
                if t < t_op[d]:
                    t_op[d], cause[d] = t, "random_grid"
        # Optional upstream event (transmission trip or precautionary shutoff) that drops every feeder.
        t_sub = cfg_grid.get("substation_trip_min")
        if t_sub is not None:
            for d, dev in enumerate(self.devices):
                if dev["kind"] == "breaker" and t_sub < t_op[d]:
                    t_op[d], cause[d] = float(t_sub), "upstream_grid"
        # Building power-loss time = earliest operation among its devices.
        nb = len(self.building_pole)
        t_b = np.full(nb, np.inf)
        dev_b = -np.ones(nb, int)
        for b, devs in enumerate(self.building_devices):
            for d in devs:
                if t_op[d] < t_b[b]:
                    t_b[b], dev_b[b] = t_op[d], d
        return {"t_op": t_op, "cause": cause, "t_building": t_b, "device_building": dev_b}
