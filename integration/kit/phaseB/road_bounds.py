"""Outward road-dose / road-peak bounds for router occupancies (Phase B, road-dose alignment campaign).

For a receiver box X (axis-aligned, outward binary64 corners) and every POTENTIAL source i (a cell that is active
at some time in some member: a finite first-new ignition, or present fire when R > 0) we compute outward per-source
coefficient bounds

    lo_i(X) <= rho*chi*tau*Omega_i(x)/(4*pi) <= hi_i(X)        for every x in X        [W/m^2]

as the intersection of three valid enclosures, all built from the UNCHANGED whole-road checker primitives:
  (a) radial whole-source bounds          radiation_bounds.RadiationBounds._radial formula (vectorised copy,
                                          bit-identical, verified by test against the original method),
  (b) radial 8x8 source-tile bounds        same formula on the checker's exact 8x8 tiles, pairwise directed sums,
  (c) analytic inner/outer rectangles      adaptive_checker.Adaptive.coefficients (ivkernel, outward binary64),
then hi is capped at density/2. Cells never active in any member contribute exactly 0 (explicit absence from the
complete immutable realisation, not a fill).

Exact activity per member comes from constructed_arrays.npz through the checker's own source object
(HybridRadiationBounds.from_case): births are the represented float64 ignition times (exact rationals), expiry is the
exact rational birth + T, present fire is active on [0, R) with R the represented REPORT assumption. The packet's
rounded-up extinction breakpoints are NOT used. On each half-open member interval I_k the active set is constant, so

    F_lo,k(X) = directed-down sum_{i active on I_k} lo_i(X)  <=  flux(x, t)  <=  F_hi,k(X) = directed-up sum hi_i(X)

for every x in X and t in I_k. For an occupancy of X over the closed exact interval [a, b]:

    dose bound  = sum_k |[a,b] cap I_k| * Fraction(F_k) / 1000       [kJ/m^2, exact rational]
    peak bound  = max over k with [a,b] cap I_k nonempty of F_k / 1000 (outward to binary64)   [kW/m^2]

Edge traversals are split into n sub-boxes uniform in the unit-clock fraction z (z_j = j/n exact), each with its exact
time sub-interval (linear motion), so the bound is a sum of box bounds. n follows a fixed, pre-declared spatial span
rule (SETTINGS); refinement only increases n. Any partition is sound; the rule affects only tightness and cost.

Caches are per process, never cross-process. They are keyed under one identity epoch
(graph canonical sha256, checker source cache identity, npz+REPORT sha256, settings digest); a model refuses any
other epoch. No cache entry can change an exposure retroactively: every entry is a pure function of its key.
Model-relative research construction only; no physical-safety claim.
"""
from __future__ import annotations

import bisect
import hashlib
import json
import math
import sys
import time
from fractions import Fraction as F
from pathlib import Path

import numpy as np

SCHEMA = 'wfg.rda.road-bounds/1'
SETTINGS = {
    'version': 'wfg.rda.road-bounds.settings/1',
    # Fixed spatial span rule (pre-declared): an edge sub-box spans at most S(d) metres along its larger axis,
    # S(d) = clamp(d / span_distance_divisor, span_min_m, span_max_m), d = float distance from the edge bounding box
    # to the nearest potential source rectangle (d only selects n; soundness never depends on it).
    'span_min_m': 4.0, 'span_max_m': 400.0, 'span_distance_divisor': 16.0,
    'max_sub_boxes_per_edge': 4096,
    'refine_factor': 4,             # selective refinement: n -> refine_factor * n for the selected witness edges
    'refine_gap_share': 0.8,        # select witness edges by descending (hi - lo) dose gap until this share is covered
    'refine_max_edges': 200,
    'source_tiles_per_axis': 8,     # identical to the checker's radial tiling
    'tile_pairs': 'all',            # 'all' potential (box, source) pairs, or 'near' (< near_distance_m) only
    'near_distance_m': 600.0,
    'analytic': True,
    'pad_m': 1e-6,                  # outward padding of float-evaluated sub-box corners (proof: MATH_PROOF.md 1.3)
    'block_cells': 2,               # lazy batch: edges whose tail node lies in the same block x block graph cells
}


# Memory repair (20261014): upper bound on the bytes of one numpy temporary in the coefficient / activity batches.
# It only selects how many box rows are processed together; it is NOT part of SETTINGS (values are bit-identical for
# every chunk size, so the bound-model identity and settings digest are unchanged).
MEM_CHUNK_BYTES = 8 * 1024 * 1024


def settings_digest(settings):
    return hashlib.sha256(json.dumps(dict(settings), sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def graph_canonical_sha(graph):
    return hashlib.sha256(json.dumps(graph, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def dn(x):
    return np.nextafter(x, -np.inf)


def up(x):
    return np.nextafter(x, np.inf)


def dsum_last(a, upper):
    """Pairwise directed summation of nonnegative terms along the last axis (same reduction as the checker's
    positive_sum / adaptive dsum_rows); result clipped at 0 from below."""
    a = np.array(a, dtype=float, copy=True)
    while a.shape[-1] > 1:
        n = a.shape[-1] // 2
        x, y = a[..., :2 * n:2], a[..., 1:2 * n:2]
        s = x + y
        # a sum with a zero operand is exact; every other partial sum is rounded outward by one ulp
        s = np.where((x == 0) | (y == 0), s, up(s) if upper else dn(s))
        a = np.concatenate((s, a[..., -1:]), axis=-1) if a.shape[-1] % 2 else s
    if a.shape[-1] == 0:
        return np.zeros(a.shape[:-1])
    return np.maximum(0.0, a[..., 0])


_REGISTRY = {}   # identity -> shared per-process coefficient cache {box tuple: (lo row, hi row)}


class Unsupported(ValueError):
    pass


class RoadBoundModel:
    """Exact-activity outward bounds for one (graph, packet, settings) epoch. Mode-independent store; use .view(mode)."""

    def __init__(self, graph, packet_dir, *, settings=None, graph_sha=None, deadline=None):
        t0 = time.perf_counter()
        self.settings = {**SETTINGS, **(settings or {})}
        from hybrid_radiation import HybridRadiationBounds
        from radiation_bounds import interval
        from road_exposure import outward_float
        self._interval, self._outward = interval, outward_float
        packet_dir = Path(packet_dir)
        rb = HybridRadiationBounds.from_case(packet_dir)
        self.rb = rb
        self.unsupported = list(rb._unsupported)
        self.ids = list(rb._ids)
        self.S = len(self.ids)
        self.pot = np.flatnonzero(rb._potential)
        self.P = int(self.pot.size)
        self.cap = outward_float(rb._density / 2, True)
        self.density = rb._density
        self.T, self.R = rb._duration, rb._remaining
        self.source_sha = file_sha(packet_dir / 'constructed_arrays.npz') + ':' + file_sha(packet_dir / 'REPORT.json')
        self.graph_sha = graph_sha or graph_canonical_sha(graph)
        self.identity = hashlib.sha256(json.dumps([SCHEMA, self.graph_sha, rb.cache_identity, self.source_sha,
                                                   settings_digest(self.settings)]).encode()).hexdigest()
        self._coef = _REGISTRY.setdefault(self.identity, {})
        # --- sources (potential only) ---------------------------------------------------------------------------
        if self.P:
            from adaptive_checker import Adaptive
            self.adaptive = Adaptive(rb)           # analytic ivkernel enclosure, potential sources only
            assert np.array_equal(self.adaptive.pot, self.pot)
            self.sl, self.sh, self.areas = rb._source_lo[self.pot], rb._source_hi[self.pot], rb._areas[self.pot]
            n = self.settings['source_tiles_per_axis']
            tiles, tareas = [], []
            for i in self.pot:
                r = rb._rectangles[i]
                area = (r[1] - r[0]) * (r[3] - r[2]) / n / n
                for x in range(n):
                    for y in range(n):
                        tiles.append((r[0] + (r[1] - r[0]) * F(x, n), r[0] + (r[1] - r[0]) * F(x + 1, n),
                                      r[2] + (r[3] - r[2]) * F(y, n), r[2] + (r[3] - r[2]) * F(y + 1, n)))
                        tareas.append(interval(area))
            self.tl = np.array([[interval(v)[0] for v in t] for t in tiles])
            self.th = np.array([[interval(v)[1] for v in t] for t in tiles])
            self.tareas = np.array(tareas)
            self.src_rect = np.array([[float(v) for v in rb._rectangles[i]] for i in self.pot])
        # --- exact activity per member ------------------------------------------------------------------------
        self.cuts, self.cutsf, self.active = [], [], []
        current = set(rb._current) if self.R > 0 else set()
        col = {int(c): j for j, c in enumerate(self.pot)}
        for s in range(self.S):
            births = dict(rb._events[s])             # source cell index -> exact Fraction(float64 birth)
            cuts = {F(0)}
            for b in births.values():
                cuts.add(b); cuts.add(b + self.T)
            if current:
                cuts.add(self.R)
            cuts = sorted(cuts)
            act = np.zeros((len(cuts), self.P), bool)
            for k, left in enumerate(cuts):
                for c, b in births.items():
                    if b <= left < b + self.T:
                        act[k, col[c]] = True
                if left < self.R:
                    for c in current:
                        act[k, col[c]] = True
            self.cuts.append(cuts)
            self.active.append(act)
        # --- extinction-rounding gaps (router flame shows a cell on [e, up(e)) when e = birth+T is not binary64) ---
        grid = graph['grid']; W, H = int(grid['width']), int(grid['height'])
        res_ = F(grid['resolution']); r0 = rb._rectangles[0]
        if (len(rb._rectangles) != H * W or r0[0] != F(grid['x0']) or r0[1] - r0[0] != res_ or r0[3] - r0[2] != res_
                or r0[3] != F(grid['y0']) + H * res_):
            # graph cell g = (H-1-row_source)*W + col (south-up graph rows, north-up source rows)
            raise Unsupported('GRID_SOURCE_ALIGNMENT_MISMATCH')
        self.gaps = {}
        self.cell_intervals = {}   # graph cell -> exact half-open activity intervals [b, e) over all members
        def gcell(c):
            r_s, col_ = divmod(int(c), W)
            return (H - 1 - r_s) * W + col_
        for s in range(self.S):
            for c, b in rb._events[s]:
                e = b + self.T
                self.cell_intervals.setdefault(gcell(c), []).append((b, e))
                if F(float(e)) != e:
                    self.gaps.setdefault(gcell(c), []).append((e, F(outward_float(e, True)), s))
        if self.R > 0:
            for c in rb._current:
                self.cell_intervals.setdefault(gcell(c), []).append((F(0), self.R))
        self.cell_intervals = {k: sorted(set(v)) for k, v in self.cell_intervals.items()}
        # --- graph geometry (floats; only selects sub-box counts) ----------------------------------------------
        self.node_xy = {n['id']: (float(n['x']), float(n['y'])) for n in graph['nodes']}
        self.edge_index = {e['id']: i for i, e in enumerate(graph['edges'])}
        self.edges = graph['edges']
        U = np.array([self.node_xy[e['u']] for e in self.edges]); V = np.array([self.node_xy[e['v']] for e in self.edges])
        self.U, self.V = U, V
        self.extent = np.maximum(np.abs(V[:, 0] - U[:, 0]), np.abs(V[:, 1] - U[:, 1]))
        if self.P:
            bx0 = np.minimum(U[:, 0], V[:, 0])[:, None]; bx1 = np.maximum(U[:, 0], V[:, 0])[:, None]
            by0 = np.minimum(U[:, 1], V[:, 1])[:, None]; by1 = np.maximum(U[:, 1], V[:, 1])[:, None]
            sr = self.src_rect
            gx = np.maximum(0, np.maximum(sr[None, :, 0] - bx1, bx0 - sr[None, :, 1]))
            gy = np.maximum(0, np.maximum(sr[None, :, 2] - by1, by0 - sr[None, :, 3]))
            self.dist = np.sqrt(gx * gx + gy * gy).min(axis=1)
        else:
            self.dist = np.full(len(self.edges), np.inf)
        st = self.settings
        span = np.clip(self.dist / st['span_distance_divisor'], st['span_min_m'], st['span_max_m'])
        self.n_default = np.clip(np.ceil(self.extent / span), 1, st['max_sub_boxes_per_edge']).astype(int)
        self.n_override = {}
        bc = st['block_cells'] * float(grid['resolution'])
        self.block = {}
        for i in range(len(self.edges)):
            key = (math.floor((U[i, 0] - grid['x0']) / bc), math.floor((U[i, 1] - grid['y0']) / bc))
            self.block.setdefault(key, []).append(i)
        self.block_of = {i: k for k, v in self.block.items() for i in v}
        # --- caches --------------------------------------------------------------------------------------------
        self._edge = {}       # (edge index, n) -> (box ids array, per member Flo (n,K), Fhi (n,K))
        self._node = {}       # node id -> (per member Flo (K,), Fhi (K,))
        self._sum = {}        # (edge index, n, member, k, mode) -> (Fraction sum_j F[j,k], max_j F[j,k])
        self._fr = {}
        self.stats = {'boxes_computed': 0, 'coef_batches': 0, 'coef_s': 0.0, 'activity_s': 0.0, 'edge_evals': 0,
                      'node_evals': 0, 'partial_evals': 0, 'fast_path': 0, 'general_path': 0, 'box_cache_hits': 0,
                      'refined_edges': 0}
        self.construct_s = time.perf_counter() - t0

    # ------------------------------------------------------------------ identity / views ---------------------
    def key(self):
        return {'identity': self.identity, 'graph_canonical_sha256': self.graph_sha, 'checker_source_cache_identity':
                self.rb.cache_identity, 'source_sha256': self.source_sha, 'settings_digest': settings_digest(self.settings)}

    def view(self, mode):
        if mode not in ('lo', 'hi', 'zero'):
            raise ValueError('mode must be lo, hi or zero')
        if mode != 'zero' and self.unsupported:
            raise Unsupported(';'.join(self.unsupported))
        return ExposureView(self, mode)

    def cache_info(self):
        nb = len(self._coef)
        return {'identity': self.identity, 'coefficient_boxes': nb, 'coefficient_bytes': nb * 2 * 8 * self.P,
                'edge_entries': len(self._edge), 'node_entries': len(self._node), 'sum_entries': len(self._sum),
                'fraction_entries': len(self._fr), 'potential_sources': self.P,
                'activity_intervals': [len(c) for c in self.cuts], 'n_override_edges': len(self.n_override),
                'stats': dict(self.stats), 'construct_s': self.construct_s,
                'scope': 'per-process numeric store; Python object overhead is in process RSS'}

    # ------------------------------------------------------------------ coefficient primitive ----------------
    def _radial(self, sl, sh, areas, B):
        """Vectorised copy of radiation_bounds.RadiationBounds._radial over (box, source); boxes are binary64
        (interval(v) == (v, v)), so rl = rh = B. Identical operation order and rounding directions."""
        rb = self.rb
        from radiation_bounds import sublo, subhi, addlo, addhi, mullo, mulhi, sqrt_bracket
        rl0, rl1, rl2, rl3 = (B[:, j:j + 1] for j in range(4)); rh0, rh1, rh2, rh3 = rl0, rl1, rl2, rl3
        S0, S1, S2, S3 = (sl[None, :, j] for j in range(4)); H0, H1, H2, H3 = (sh[None, :, j] for j in range(4))
        dx = np.maximum(0, np.maximum(sublo(S0, rh1), sublo(rl0, H1)))
        dy = np.maximum(0, np.maximum(sublo(S2, rh3), sublo(rl2, H3)))
        farx = np.maximum(np.maximum(np.abs(sublo(S0, rh1)), np.abs(subhi(H0, rl1))),
                          np.maximum(np.abs(sublo(S1, rh0)), np.abs(subhi(H1, rl0))))
        fary = np.maximum(np.maximum(np.abs(sublo(S2, rh3)), np.abs(subhi(H2, rl3))),
                          np.maximum(np.abs(sublo(S3, rh2)), np.abs(subhi(H3, rl2))))
        h0, h1 = rb._scalar_h
        d0 = np.maximum(0, addlo(addlo(mullo(dx, dx), mullo(dy, dy)), mullo(h0, h0)))
        d1 = addhi(addhi(mulhi(farx, farx), mulhi(fary, fary)), mulhi(h1, h1))
        root0 = sqrt_bracket(d0)[0]; root1 = sqrt_bracket(d1)[1]
        den0 = mullo(mullo(mullo(4.0, rb._pi[0]), d0), root0)
        den1 = mulhi(mulhi(mulhi(4.0, rb._pi[1]), d1), root1)
        num0 = mullo(mullo(rb._scalar_density[0], areas[None, :, 0]), h0)
        num1 = mulhi(mulhi(rb._scalar_density[1], areas[None, :, 1]), h1)
        num0 = np.broadcast_to(num0, den1.shape); num1 = np.broadcast_to(num1, den0.shape)
        lo = np.maximum(0, down_div(num0, den1))
        den0 = np.maximum(0, den0)
        hi = np.full_like(den0, self._outward(rb._density / 2, True))
        valid = den0 > 0
        hi[valid] = up(np.divide(num1[valid], den0[valid]))
        return lo, hi, dx, dy

    def coefficients(self, boxes):
        """boxes (B,4) float rx0,rx1,ry0,ry1 (outward) -> lo, hi (B,P) W/m^2 per potential source.

        Memory repair (20261014): the boxes are processed in row chunks so that no (rows, P*64) tile temporary exceeds
        MEM_CHUNK_BYTES. Every operation in _coefficients is elementwise per box row (broadcast over sources, pairwise
        directed sums along the source/tile axis only), so the chunked result is bit-identical to the single batch.
        If any chunk raises an arithmetic/precondition error, the original single-batch computation is re-run so the
        caller observes exactly the original outcome (the same exception, or the same values)."""
        boxes = np.asarray(boxes, dtype=float)
        if boxes.ndim != 2 or boxes.shape[1] != 4 or np.any(boxes[:, 0] > boxes[:, 1]) or np.any(boxes[:, 2] > boxes[:, 3]):
            raise ValueError('boxes (B,4) with x0<=x1, y0<=y1 required')
        with np.errstate(over='raise', invalid='raise', divide='raise', under='ignore'):
            B = boxes.shape[0]
            rows = max(1, MEM_CHUNK_BYTES // max(1, self.P * self.settings['source_tiles_per_axis'] ** 2 * 8))
            if B <= rows:
                return self._coefficients(boxes)
            try:
                parts = [self._coefficients(boxes[i:i + rows]) for i in range(0, B, rows)]
            except (ArithmeticError, ValueError):
                return self._coefficients(boxes)
            return np.concatenate([p[0] for p in parts]), np.concatenate([p[1] for p in parts])

    def _coefficients(self, boxes):
        lo, hi, dx, dy = self._radial(self.sl, self.sh, self.areas, boxes)
        n = self.settings['source_tiles_per_axis']
        if n > 1:
            if self.settings['tile_pairs'] == 'all':
                rows = np.arange(boxes.shape[0])
            else:
                rows = np.flatnonzero((np.maximum(dx, dy) < float(self.settings['near_distance_m'])).any(axis=1))
            if rows.size:
                tl, th, _, _ = self._radial(self.tl, self.th, self.tareas, boxes[rows])
                tl = dsum_last(tl.reshape(rows.size, self.P, n * n), False)
                th = dsum_last(th.reshape(rows.size, self.P, n * n), True)
                lo[rows] = np.maximum(lo[rows], tl); hi[rows] = np.minimum(hi[rows], th)
        if self.settings['analytic']:
            la, ha = self.adaptive.coefficients(boxes)
            lo = np.maximum(lo, la); hi = np.minimum(hi, ha)
        hi = np.minimum(hi, self.cap)
        if np.any(lo > hi):
            raise ArithmeticError('INCOMPATIBLE_SAME_LAW_ENCLOSURES')
        return lo, hi

    def _activity(self, lo, hi):
        """(B,P) coefficients -> per member (Flo (B,K), Fhi (B,K)) directed sums over the exact active sets.

        Memory repair (20261014): the (rows, K, P) masked arrays are formed for row chunks of at most MEM_CHUNK_BYTES
        each; every row's directed sum is the same pairwise reduction along P as before (bit-identical)."""
        out = []
        B = lo.shape[0]
        for s in range(self.S):
            act = self.active[s]                                    # (K,P)
            rows = max(1, MEM_CHUNK_BYTES // max(1, act.shape[0] * self.P * 8))
            fl, fh = [], []
            for i in range(0, B, rows) if B > rows else [0]:
                l_, h_ = (lo, hi) if B <= rows else (lo[i:i + rows], hi[i:i + rows])
                ml = np.where(act[None, :, :], l_[:, None, :], 0.0)
                mh = np.where(act[None, :, :], h_[:, None, :], 0.0)
                # Active cell footprints are disjoint up to area-zero edges, so the total solid angle is <= 2*pi and the
                # total flux <= density/2: capping the directed-up sum at density/2 keeps it an upper bound.
                fl.append(dsum_last(ml, False)); fh.append(np.minimum(self.cap, dsum_last(mh, True)))
                del ml, mh
            out.append((fl[0], fh[0]) if len(fl) == 1 else (np.concatenate(fl), np.concatenate(fh)))
        return out

    def _batch(self, boxes):
        t = time.perf_counter()
        boxes = np.asarray(boxes, dtype=float)
        keys = [tuple(b) for b in boxes.tolist()]
        need = [i for i, k in enumerate(keys) if k not in self._coef]
        self.stats['box_cache_hits'] += len(keys) - len(need)
        if need:
            lo, hi = self.coefficients(boxes[need])
            for j, i in enumerate(need):
                self._coef[keys[i]] = (lo[j], hi[j])
            self.stats['boxes_computed'] += len(need); self.stats['coef_batches'] += 1
        lo = np.array([self._coef[k][0] for k in keys]).reshape(len(keys), self.P)
        hi = np.array([self._coef[k][1] for k in keys]).reshape(len(keys), self.P)
        t1 = time.perf_counter(); self.stats['coef_s'] += t1 - t
        out = self._activity(lo, hi)
        self.stats['activity_s'] += time.perf_counter() - t1
        return out

    # ------------------------------------------------------------------ geometry -------------------------------
    def n_for(self, ei):
        return self.n_override.get(ei, int(self.n_default[ei]))

    def sub_boxes(self, ei, n):
        """Outward boxes of the n uniform sub-pieces z in [j/n,(j+1)/n] of edge ei (float corners, padded)."""
        u, v = self.U[ei], self.V[ei]
        z = np.arange(n + 1, dtype=float) / n
        x = u[0] + (v[0] - u[0]) * z; y = u[1] + (v[1] - u[1]) * z
        x[0], y[0], x[-1], y[-1] = u[0], u[1], v[0], v[1]       # exact endpoints
        pad = self.settings['pad_m']
        x0 = np.minimum(x[:-1], x[1:]) - pad; x1 = np.maximum(x[:-1], x[1:]) + pad
        y0 = np.minimum(y[:-1], y[1:]) - pad; y1 = np.maximum(y[:-1], y[1:]) + pad
        return np.stack([x0, x1, y0, y1], axis=1)

    def _ensure_edges(self, eis, n_of=None):
        eis = [ei for ei in eis if (ei, (n_of or self.n_for)(ei)) not in self._edge]
        if not eis or not self.P:
            for ei in eis:
                n = (n_of or self.n_for)(ei)
                self._edge[(ei, n)] = [(np.zeros((n, len(self.cuts[s]))), np.zeros((n, len(self.cuts[s])))) for s in range(self.S)]
            return
        parts, sizes = [], []
        for ei in eis:
            n = (n_of or self.n_for)(ei); parts.append(self.sub_boxes(ei, n)); sizes.append(n)
        res = self._batch(np.concatenate(parts))
        off = 0
        for ei, n in zip(eis, sizes):
            self._edge[(ei, n)] = [(res[s][0][off:off + n], res[s][1][off:off + n]) for s in range(self.S)]
            off += n

    def edge_store(self, ei, n=None):
        n = self.n_for(ei) if n is None else n
        st = self._edge.get((ei, n))
        if st is None:
            if n == self.n_for(ei):
                self._ensure_edges([j for j in self.block[self.block_of[ei]] if j not in self.n_override] + [ei])
            else:
                self._ensure_edges([ei], n_of=lambda _e: n)
            st = self._edge[(ei, n)]
        return n, st

    def node_store(self, node):
        st = self._node.get(node)
        if st is None:
            x, y = self.node_xy[node]
            if self.P:
                res = self._batch(np.array([[x, x, y, y]]))
                st = [(res[s][0][0], res[s][1][0]) for s in range(self.S)]
            else:
                st = [(np.zeros(len(self.cuts[s])), np.zeros(len(self.cuts[s]))) for s in range(self.S)]
            self._node[node] = st
        return st

    def select_refinement(self, traversals):
        """LazySP-style selection: traversals = [(edge_id, start, end)] of rejected / unresolved witnesses. Rank edges by
        their summed (hi - lo) dose gap over all members and select the largest until refine_gap_share of the total gap
        is covered (at most refine_max_edges). Only tightness depends on this choice."""
        lo, hi = self.view('lo'), self.view('hi')
        gap = {}
        for e, a, b in traversals:
            vl, vh = lo.edge(e, a, b), hi.edge(e, a, b)
            gap[e] = gap.get(e, 0.0) + sum(float(h[0] - l[0]) for l, h in zip(vl, vh))
        order = sorted(gap, key=lambda k: -gap[k]); total = sum(gap.values()); out, acc = [], 0.0
        for e in order:
            if len(out) >= self.settings['refine_max_edges'] or (total > 0 and acc >= self.settings['refine_gap_share'] * total) or gap[e] <= 0:
                break
            out.append(e); acc += gap[e]
        return out, {'candidate_edges': len(gap), 'selected': len(out), 'gap_total_kj_m2': total, 'gap_selected_kj_m2': acc}

    def prepare_route(self, edge_ids):
        """Compute the sub-box bounds of exactly these edges in one vectorised batch (no block prefetch); later
        evaluations of the same (edge, n) reuse them. Returns the number of edges computed."""
        eis = sorted({self.edge_index[e] for e in edge_ids} - {ei for (ei, n) in self._edge if n == self.n_for(ei)})
        self._ensure_edges(eis)
        return len(eis)

    def refine_edges(self, edge_ids):
        """Selective refinement: n -> refine_factor * n for these edges (only increases n). Returns count."""
        eis = []
        for e in edge_ids:
            ei = self.edge_index[e]
            n = int(min(self.settings['max_sub_boxes_per_edge'], self.n_for(ei) * int(self.settings['refine_factor'])))
            if n > self.n_for(ei):
                self.n_override[ei] = n; eis.append(ei)
        self._ensure_edges(eis)
        self.stats['refined_edges'] += len(eis)
        return len(eis)

    def exact_contact_any(self, occupancy):
        for occ in occupancy:
            lo, hi = F(occ['start']), F(occ['end'])
            for b, e in self.cell_intervals.get(occ['cell'], ()):
                if lo < e and hi >= b:
                    return True
        return False

    def frac(self, x):
        f = self._fr.get(x)
        if f is None:
            f = self._fr[x] = F(x)
        return f


def down_div(a, b):
    return dn(np.divide(a, b))


class ExposureView:
    """Mode view used by road_core: per-member (dose kJ/m^2 exact Fraction, peak kW/m^2 float) per occupancy."""

    def __init__(self, model, mode):
        self.m, self.mode = model, mode
        self.zero = tuple((F(0), 0.0) for _ in range(model.S))
        self._j = 0 if mode == 'lo' else 1

    def _peak_kw(self, w):
        return self.m._outward(self.m.frac(float(w)) / 1000, self.mode == 'hi')

    def stats(self):
        st = dict(self.m.stats)
        st.update(coefficient_boxes=len(self.m._coef), edge_entries=len(self.m._edge), sum_entries=len(self.m._sum),
                  mode=self.mode, identity=self.m.identity)
        return st

    def gap_probe(self, occupancy):
        """Called only when the router's hazard sampling reported FLAME_CONTACT for this occupancy. Returns a
        non-empty record iff NO occupancy piece meets an exact activity interval of its own cell
        ([lo,hi] meets [b,e) iff lo < e and hi >= b), i.e. the router contact is not implied by road contact
        (extinction-rounding gap, or the clamped final bin at the horizon)."""
        return [] if self.m.exact_contact_any(occupancy) else [{'pieces': len(occupancy), 'reason': 'ROUTER_ONLY_FLAME'}]

    def edge_plain(self, edge_id, t, end):
        """Route re-integration path: plain per-sub-box summation, no fast-path sums."""
        if self.mode == 'zero':
            return self.zero
        m = self.m
        n, store = m.edge_store(m.edge_index[edge_id])
        t, end = F(t), F(end)
        return tuple((lambda dp: (dp[0] / 1000, self._peak_kw(dp[1])))(self._general(store[s], n, t, end - t, m.cuts[s]))
                     for s in range(m.S))

    def node_plain(self, node, t, end):
        return self.node(node, t, end)

    def _general(self, store_s, n, t, D, cuts):
        """Plain per-sub-box summation (also the route re-integration path)."""
        Fm = store_s[self._j]
        dose, peak = F(0), 0.0
        K = len(cuts)
        for j in range(n):
            a = t + D * F(j, n)
            b = t + D * F(j + 1, n)
            k = bisect.bisect_right(cuts, a) - 1
            while k < K and cuts[k] <= b:
                hiedge = cuts[k + 1] if k + 1 < K else None
                lo_t = a if a > cuts[k] else cuts[k]
                hi_t = b if hiedge is None or b < hiedge else hiedge
                if hiedge is None or a < hiedge:
                    w = float(Fm[j][k])
                    if hi_t > lo_t:
                        dose += (hi_t - lo_t) * self.m.frac(w)
                    if w > peak:
                        peak = w
                k += 1
        return dose, peak

    def edge(self, edge_id, t, end):
        """Full traversal of edge (z 0 -> 1) over [t, end]."""
        if self.mode == 'zero':
            return self.zero
        m = self.m; m.stats['edge_evals'] += 1
        ei = m.edge_index[edge_id]
        n, store = m.edge_store(ei)
        t, end = F(t), F(end); D = end - t
        out = []
        for s in range(m.S):
            cuts = m.cuts[s]
            k0 = bisect.bisect_right(cuts, t) - 1; k1 = bisect.bisect_right(cuts, end) - 1
            if k1 == k0 or (k1 == k0 + 1 and cuts[k1] == end):
                key = (ei, n, s, k0, self.mode)
                v = m._sum.get(key)
                if v is None:
                    col = store[s][self._j][:, k0]
                    v = m._sum[key] = (sum((m.frac(float(w)) for w in col), F(0)), float(col.max()))
                dose = D * v[0] / n; peak = v[1]
                if k1 != k0:
                    peak = max(peak, float(store[s][self._j][n - 1, k1]))
                m.stats['fast_path'] += 1
            else:
                dose, peak = self._general(store[s], n, t, D, cuts=cuts); m.stats['general_path'] += 1
            out.append((dose / 1000, self._peak_kw(peak)))
        return tuple(out)

    def node(self, node, t, end):
        if self.mode == 'zero':
            return self.zero
        m = self.m; m.stats['node_evals'] += 1
        store = m.node_store(node)
        t, end = F(t), F(end)
        out = []
        for s in range(m.S):
            st = (store[s][0][None, :], store[s][1][None, :])
            dose, peak = self._general(st, 1, t, end - t, cuts=m.cuts[s])
            out.append((dose / 1000, self._peak_kw(peak)))
        return tuple(out)

    def partial(self, edge_id, start, end, f, q):
        """Traversal of the sub-range z in [f, q] of an edge over [start, end] (exact boxes, uncached)."""
        if self.mode == 'zero':
            return self.zero
        m = self.m; m.stats['partial_evals'] += 1
        ei = m.edge_index[edge_id]; f, q = F(f), F(q); start, end = F(start), F(end)
        e = m.edges[ei]; u = [F(m.node_xy[e['u']][0]), F(m.node_xy[e['u']][1])]; v = [F(m.node_xy[e['v']][0]), F(m.node_xy[e['v']][1])]
        n = max(1, math.ceil(m.n_for(ei) * (q - f))) if q > f else 1
        zs = [f + (q - f) * F(j, n) for j in range(n + 1)]
        pts = [(u[0] + z * (v[0] - u[0]), u[1] + z * (v[1] - u[1])) for z in zs]
        o = m._outward
        boxes = [[o(min(a[0], b[0]), False), o(max(a[0], b[0]), True), o(min(a[1], b[1]), False), o(max(a[1], b[1]), True)]
                 for a, b in zip(pts[:-1], pts[1:])]
        if m.P:
            res = m._batch(np.array(boxes))
        else:
            res = [(np.zeros((n, len(m.cuts[s]))), np.zeros((n, len(m.cuts[s])))) for s in range(m.S)]
        out = []
        for s in range(m.S):
            dose, peak = self._general(res[s], n, start, end - start, cuts=m.cuts[s])
            out.append((dose / 1000, self._peak_kw(peak)))
        return tuple(out)
