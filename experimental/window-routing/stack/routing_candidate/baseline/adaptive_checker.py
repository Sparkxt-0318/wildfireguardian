"""CANDIDATE R: adaptive certified radiation enclosure used ONLY as a fallback
after the unchanged HybridChecker ends with RADIATION_UNRESOLVED_OR_UNSUPPORTED
following a CLEAR contact check. Kernel and adaptive partition authored by
worker C (work/C_exposure/scripts/ivkernel.py, adaptive_enclosure.py); this
module only binds them to the checker's existing source-law object and mission
trajectory. Baseline certificates/rejections are never overridden."""
import math, time
from fractions import Fraction as F
import numpy as np
from hybrid_checker import HybridChecker as _BaseChecker
from hybrid_radiation import HybridRadiationBounds
from radiation_bounds import interval
from road_exposure import rational, outward_float
from ivkernel import rectangle_bounds, exact_diff, dn, up

def dsum_rows(a, upper):
    """Pairwise directed summation along axis 1 (each row), nonnegative terms."""
    a = np.array(a, dtype=float, copy=True)
    while a.shape[1] > 1:
        n = a.shape[1] // 2
        s = a[:, :2 * n:2] + a[:, 1:2 * n:2]
        s = up(s) if upper else dn(s)
        a = np.concatenate((s, a[:, -1:]), axis=1) if a.shape[1] % 2 else s
    return a[:, 0] if a.shape[1] else np.zeros(a.shape[0])

class Adaptive:
    def __init__(self, rb):
        self.rb = rb
        self.pot = np.flatnonzero(rb._potential)
        R = [rb._rectangles[i] for i in self.pot]
        for r in R:
            for v in r:
                if interval(v)[0] != interval(v)[1]: raise ArithmeticError('source corners must be exact binary64')
        R = np.array([[float(v) for v in r] for r in R])
        self.sx0, self.sx1, self.sy0, self.sy1 = R.T
        if interval(rb._h)[0] != interval(rb._h)[1]: raise ArithmeticError('emitter height must be exact binary64')
        self.h = float(rb._h)
        self.pi_lo, self.pi_hi = rb._pi
        self.dlo, self.dhi = rb._scalar_density
        self.cap = outward_float(rb._density / 2, True)
        self.birth = [b[self.pot] for b in rb._birth]; self.expiry = [e[self.pot] for e in rb._expiry]
        self.possible = [p[self.pot] for p in rb._possible]
        self.ids = list(rb._ids)

    def coefficients(self, boxes):
        """boxes: (B,4) outward float receiver boxes rx0,rx1,ry0,ry1 -> (B,P) lo, hi."""
        rx0, rx1, ry0, ry1 = [boxes[:, j:j + 1] for j in range(4)]
        S = lambda s: s[None, :]
        # inner rectangle (contained in every translate) and outer (contains every translate)
        il, _ = rectangle_bounds(exact_diff(S(self.sx0), rx0), exact_diff(S(self.sx1), rx1),
                                 exact_diff(S(self.sy0), ry0), exact_diff(S(self.sy1), ry1), self.h, self.pi_lo, self.pi_hi)
        _, oh = rectangle_bounds(exact_diff(S(self.sx0), rx1), exact_diff(S(self.sx1), rx0),
                                 exact_diff(S(self.sy0), ry1), exact_diff(S(self.sy1), ry0), self.h, self.pi_lo, self.pi_hi)
        lo = np.maximum(0, dn(il * self.dlo)); hi = np.minimum(self.cap, up(oh * self.dhi))
        if np.any(lo > hi): raise ArithmeticError('reversed coefficient enclosure')
        return lo, hi

    def slab_geometry(self, leg, k, n):
        a = leg['start'] + (leg['end'] - leg['start']) * F(k, n); b = leg['start'] + (leg['end'] - leg['start']) * F(k + 1, n)
        pa, pb = self.rb._point(leg, a), self.rb._point(leg, b)
        box = (outward_float(min(pa[0], pb[0]), False), outward_float(max(pa[0], pb[0]), True),
               outward_float(min(pa[1], pb[1]), False), outward_float(max(pa[1], pb[1]), True))
        return a, b, box

    def evaluate(self, slabs, legs):
        """slabs: list of (leg_index,k,n). Returns arrays (B,M) lo, hi dose and (B,M) peak lo/hi."""
        B = len(slabs); M = len(self.ids)
        geo = [self.slab_geometry(legs[l], k, n) for l, k, n in slabs]
        boxes = np.array([g[2] for g in geo])
        out_lo = np.zeros((B, M)); out_hi = np.zeros((B, M)); pk_lo = np.zeros((B, M)); pk_hi = np.zeros((B, M))
        CH = 256
        for c0 in range(0, B, CH):
            sl = slice(c0, min(B, c0 + CH))
            cl, ch = self.coefficients(boxes[sl])
            a0 = np.array([interval(g[0])[0] for g in geo[sl]])[:, None]; a1 = np.array([interval(g[0])[1] for g in geo[sl]])[:, None]
            b0 = np.array([interval(g[1])[0] for g in geo[sl]])[:, None]; b1 = np.array([interval(g[1])[1] for g in geo[sl]])[:, None]
            for s in range(M):
                birth, expiry, possible = self.birth[s], self.expiry[s], self.possible[s]
                act = possible[None, :] & (birth[None, :, 0] <= b1) & (expiry[None, :, 1] > a0)
                durlo = np.where(act, np.maximum(0, dn(np.minimum(b0, expiry[None, :, 0]) - np.maximum(a1, birth[None, :, 1]))), 0.)
                durhi = np.where(act, np.maximum(0, up(np.minimum(b1, expiry[None, :, 1]) - np.maximum(a0, birth[None, :, 0]))), 0.)
                out_lo[sl, s] = dsum_rows(np.maximum(0, dn(cl * durlo)), False)
                out_hi[sl, s] = dsum_rows(up(ch * durhi), True)
                pk_hi[sl, s] = np.minimum(self.cap, dsum_rows(np.where(act, ch, 0.), True))
                start_act = act & (birth[None, :, 1] <= a0) & (expiry[None, :, 0] > a1)
                pk_lo[sl, s] = dsum_rows(np.where(start_act, cl, 0.), False)
        return out_lo, out_hi, pk_lo, pk_hi

def directed_total(start, values, upper):
    t = start
    for v in values:
        t = float(up(t + v)) if upper else max(0., float(dn(t + v)))
    return t



def adaptive_bound(rb, trajectory, request, stop, span0=16, max_slabs=400000, split_fraction=0.5):
    T0 = time.perf_counter()
    A = Adaptive(rb); legs = rb._normalise(trajectory)
    unsupported = list(rb._unsupported)
    if any(not rb._inside(p) for leg in legs for p in (leg['p0'], leg['p1'])): unsupported.append('OUTSIDE_SOURCE_GRID')
    if unsupported: return {'status': 'UNSUPPORTED', 'detail': unsupported}
    ids = A.ids
    budgets = [rational(request['budgets']['dose'][mid]) * 1000 for mid in ids]
    peak_budget = rational(request['budgets']['peak']) * 1000
    inc_lo = [interval(rational(request['incurred'][mid]) * 1000)[0] for mid in ids]
    inc_hi = [interval(rational(request['incurred'][mid]) * 1000)[1] for mid in ids]
    span = rational(span0); slabs = []
    for li, leg in enumerate(legs):
        extent = max(abs(v - u) for u, v in zip(leg['p0'], leg['p1']))
        n = max(1, math.ceil(extent / span)); slabs += [(li, k, n) for k in range(n)]
    moving = lambda s: legs[s[0]]['p0'] != legs[s[0]]['p1']
    contrib = {}
    lo, hi, pl, ph = A.evaluate(slabs, legs)
    for i, s in enumerate(slabs): contrib[s] = (lo[i], hi[i], pl[i], ph[i])
    rounds = 0; status = 'UNRESOLVED'; cap = None
    while True:
        rounds += 1; keys = list(contrib)
        L = np.array([contrib[s][0] for s in keys]); H = np.array([contrib[s][1] for s in keys])
        PL = np.array([contrib[s][2] for s in keys]); PH = np.array([contrib[s][3] for s in keys])
        tot_lo = [directed_total(inc_lo[j], L[:, j], False) for j in range(len(ids))]
        tot_hi = [directed_total(inc_hi[j], H[:, j], True) for j in range(len(ids))]
        peak_lo = [float(PL[:, j].max()) for j in range(len(ids))]; peak_hi = [float(PH[:, j].max()) for j in range(len(ids))]
        rej = [F(tot_lo[j]) > budgets[j] or F(peak_lo[j]) > peak_budget for j in range(len(ids))]
        cert = [F(tot_hi[j]) <= budgets[j] and F(peak_hi[j]) <= peak_budget for j in range(len(ids))]
        if any(rej): status = 'DEFINITE_REJECT'; break
        if all(cert): status = 'CERTIFIED_RADIATION'; break
        if len(keys) >= max_slabs: cap = 'SLAB_CAP'; break
        if time.perf_counter() >= stop: cap = 'WALL_CAP'; break
        unresolved = [j for j in range(len(ids)) if not cert[j]]
        width = (H[:, unresolved] - L[:, unresolved]).sum(axis=1)
        width = np.where(np.array([moving(s) for s in keys]), width, 0.)
        if width.max() <= 0: cap = 'NO_SPLITTABLE_WIDTH'; break
        order = np.argsort(-width); csum = np.cumsum(width[order])
        nsplit = min(int(np.searchsorted(csum, split_fraction * csum[-1]) + 1), max(1, max_slabs - len(keys)))
        chosen = [keys[i] for i in order[:nsplit]]
        timed_out = False
        for b0 in range(0, len(chosen), 128):
            if time.perf_counter() >= stop: timed_out = True; break
            batch = chosen[b0:b0 + 128]
            children = [c for (l, k, n) in batch for c in ((l, 2 * k, 2 * n), (l, 2 * k + 1, 2 * n))]
            lo, hi, pl, ph = A.evaluate(children, legs)
            # replace parents only after their children are evaluated: partition stays complete
            for parent in batch: del contrib[parent]
            for i, s in enumerate(children): contrib[s] = (lo[i], hi[i], pl[i], ph[i])
        if timed_out: cap = 'WALL_CAP'; break
    return {'status': status, 'cap': cap, 'rounds': rounds, 'final_slabs': len(contrib), 'elapsed_s': time.perf_counter() - T0,
            'per_member': {ids[j]: {'dose_lower_kj_m2': tot_lo[j] / 1000, 'dose_upper_kj_m2': tot_hi[j] / 1000, 'budget_kj_m2': float(budgets[j] / 1000),
                                    'peak_lower_kw_m2': peak_lo[j] / 1000, 'peak_upper_kw_m2': peak_hi[j] / 1000,
                                    'certified_le_budget': cert[j], 'rejected_gt_budget': rej[j]} for j in range(len(ids))}}


class HybridChecker(_BaseChecker):
    schema = 'wfg.hybrid.fixed-mission+adaptive-fallback/1'

    def check(self, graph, request, legs, destination, *, wall_s=30, deadline=None, **kw):
        started = time.perf_counter()
        stop = started + float(wall_s)
        if deadline is not None: stop = min(stop, float(deadline))
        import copy as _copy
        from hybrid_checker import file_sha, rss_mb, RSS_LIMIT_MB, settings_digest
        from mission_contract import graph_digest
        req_copy = _copy.deepcopy(request); legs_copy = _copy.deepcopy(legs); g_digest = graph_digest(graph)
        base = super().check(graph, request, legs, destination, wall_s=wall_s, deadline=deadline, **kw)
        if not (base.get('status') == 'UNRESOLVED' and base.get('reason') == 'RADIATION_UNRESOLVED_OR_UNSUPPORTED'
                and base.get('contact', {}).get('status') == 'CLEAR' and self._radiation is not None and 'trajectory' in base):
            return base
        if time.perf_counter() >= stop:
            return base
        try:
            ad = adaptive_bound(self._radiation, base['trajectory'], req_copy, stop - 1.0)
        except (ValueError, TypeError, KeyError, ArithmeticError, AssertionError) as exc:
            base['adaptive_fallback'] = {'status': 'ERROR', 'reason': repr(exc)}; return base
        out = dict(base); out['radiation_baseline_unresolved'] = base.get('radiation'); out['adaptive_fallback'] = ad
        if ad['status'] == 'CERTIFIED_RADIATION':
            out.update(status='CERTIFIED_ADMISSIBLE', reason='COMPLETE_CONTACT_AND_ADAPTIVE_RADIATION')
        elif ad['status'] == 'DEFINITE_REJECT':
            out.update(status='DEFINITE_REJECT', reason='ADAPTIVE_RADIATION_LOWER_BOUND_VIOLATION')
        # Authority recheck after the fallback, before any certificate (review finding 4).
        if (str(self.directory) != self._directory_identity or
                settings_digest(self.settings) != self._settings_identity or
                self._source_identity != file_sha(self.directory / 'constructed_arrays.npz') + ':' + file_sha(self.directory / 'REPORT.json') or
                graph_digest(graph) != g_digest or request != req_copy or legs != legs_copy):
            out = {'status': 'UNRESOLVED', 'reason': 'AUTHORITY_CHANGED_DURING_ADAPTIVE_FALLBACK', 'checked_result': out, 'checked_result_is_secondary': True}
        elif rss_mb() > RSS_LIMIT_MB:
            out = {'status': 'UNRESOLVED', 'reason': 'RSS_LIMIT_AFTER_ADAPTIVE_FALLBACK', 'checked_result': out, 'checked_result_is_secondary': True}
        if time.perf_counter() >= stop:
            out = {'status': 'UNRESOLVED', 'reason': 'WALL_CAP_AFTER_ADAPTIVE_FALLBACK', 'checked_result': out, 'checked_result_is_secondary': True}
        out['elapsed_s'] = time.perf_counter() - started
        return out
