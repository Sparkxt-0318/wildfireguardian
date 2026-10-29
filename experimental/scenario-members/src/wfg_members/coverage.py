"""Cheap after-the-fact checker: does a fixed journey pass in each of N trajectories?

Used for coverage statistics (the weighted fraction of all N trajectories in which a returned route passes) and for
synthetic-truth scoring at scale. It is not the certifying checker; tests compare its pass flags with the frozen centre
checker on built members.

  contact  exact: the checker's occupancy spans (closed) against half-open activity [b, ext) with ext the bridge's
           rounded-up extinction (round_up_sum(b, T)) and present fire [0, R).
  dose     incurred + sum over spans of the integral of centre flux, the flux of a member being the linear
           superposition of single-cell kernels of the inherited radiation operator (present fire plus active first-new
           cells). The bridge adds a numerical margin of at most 1e-8 * max(1 W/m2, interval maximum) per cell; this
           checker adds the upper bound of that margin, so its dose is never below the packet dose by more than rounding.
  peak     maximum superposed flux plus the same margin.
"""
from __future__ import annotations

from fractions import Fraction as F

import numpy as np

from . import kit


def round_up_sum(a, b):
    s = float(a) + float(b)
    if F(s) < F(float(a)) + F(float(b)):
        s = float(np.nextafter(s, np.inf))
    return s


class Kernels:
    """Single-cell radiation kernels (W/m2, graph cell order) of the inherited operator on one window grid."""

    def __init__(self, affine_transform, settings, epsg, shape):
        B = kit.install()["bridge"]
        self.model = B.radiation_model(affine_transform, settings, epsg)
        self.shape = tuple(shape)
        self.cache = {}

    def native_to_graph(self, arr):
        return np.ascontiguousarray(np.asarray(arr)[::-1, :]).ravel()

    def of_mask(self, mask_native):
        f = self.model.predict_details(np.asarray(mask_native, dtype=float)).incident_heat_flux_w_m2
        return self.native_to_graph(f)

    def of_graph_cell(self, gcell):
        k = self.cache.get(gcell)
        if k is None:
            H, W = self.shape
            gr, c = divmod(int(gcell), W)
            m = np.zeros((H, W))
            m[H - 1 - gr, c] = 1.0
            k = self.cache[gcell] = self.of_mask(m)
        return k


class JourneyEvaluator:
    """Fixed journey (its occupancy spans and issue point) evaluated against many members cheaply: spans are indexed by
    cell for contact (exact rational comparisons) and held as arrays for the dose integral (binary64)."""

    def __init__(self, spans, issue_cell, departure, request, member_id=None):
        self.spans = [(int(c), F(a), F(b)) for c, a, b in spans]
        self.issue = (int(issue_cell), F(departure))
        self.request = request
        self.by_cell = {}
        for c, a, b in self.spans + [(self.issue[0], self.issue[1], self.issue[1])]:
            self.by_cell.setdefault(c, []).append((a, b))
        self.cells = sorted(self.by_cell)
        self.budget_peak = float(request["budgets"]["peak"])
        member_id = member_id or next(iter(request["budgets"]["dose"]))
        self.budget_dose = F(request["budgets"]["dose"][member_id])
        self.incurred = F(request["incurred"][member_id])
        self.c = np.array([c for c, _, _ in self.spans], dtype=np.int64)
        self.a = np.array([float(a) for _, a, _ in self.spans])
        self.b = np.array([float(b) for _, _, b in self.spans])
        self.duration = float((self.b - self.a).sum())
        self._shared = {}

    def contact(self, births, T, current, R):
        """births {graph cell: second}; current: set of graph cells active on [0, R)."""
        key = ("contact", tuple(sorted(current)), F(float(R)))
        if key not in self._shared:
            Rq = F(float(R))
            self._shared[key] = R > 0 and any(a < Rq for c in current for a, _ in self.by_cell.get(c, ()))
        if self._shared[key]:
            return True
        T = float(T)
        for c, t in births.items():
            spans = self.by_cell.get(c)
            if spans:
                ext, start = F(round_up_sum(t, T)), F(float(t))
                if any(a < ext and b >= start for a, b in spans):
                    return True
        return False

    def dose_peak(self, births, T, R, kernels, current_flux):
        """(dose kJ/m2 upper bound incl. incurred, peak kW/m2 upper bound) along the journey."""
        T, R = float(T), float(R)
        fcur = current_flux[self.c]
        cur_on = self.a < R
        total = float(self.incurred) + float((fcur * np.clip(np.minimum(self.b, R) - self.a, 0, None)).sum()) / 1000.0
        peak_arr = np.where(cur_on, fcur, 0.0)
        summ = current_flux.copy()
        extra = np.zeros(self.c.size)
        for c, t in births.items():
            k = kernels.of_graph_cell(c)
            summ = summ + k
            t0, t1 = float(t), round_up_sum(t, T)
            kc = k[self.c]
            total += float((kc * np.clip(np.minimum(self.b, t1) - np.maximum(self.a, t0), 0, None)).sum()) / 1000.0
            extra = extra + np.where((self.a < t1) & (self.b >= t0), kc, 0.0)
        peak = float((peak_arr + extra).max()) if self.c.size else 0.0
        margin = 1e-8 * max(1.0, float(summ.max()))           # >= the bridge margin of every interval map
        total += margin * self.duration / 1000.0
        return total, (peak + margin) / 1000.0

    def passes(self, births, T, current, R, kernels=None, current_flux=None):
        if self.contact(births, T, current, R):
            return False, {"contact": True}
        if kernels is None:
            return True, {"contact": False}
        dose, peak = self.dose_peak(births, T, R, kernels, current_flux)
        ok = dose <= float(self.budget_dose) and peak <= self.budget_peak
        return ok, {"contact": False, "dose_kj_m2": dose, "peak_kw_m2": peak}


def coverage(evaluator, model, *, weights=None, kernels=None, current_flux=None, members=None):
    """Weighted fraction of the members of a ContactModel in which the journey passes, and the per-member flags."""
    members = range(len(model.events)) if members is None else members
    current = set(model.current) if model.R > 0 else set()
    flags = []
    for j in members:
        ok, _ = evaluator.passes(model.events[j], model.T, current, model.R, kernels, current_flux)
        flags.append(ok)
    w = np.full(len(flags), 1.0 / len(flags)) if weights is None else np.asarray(weights, float)
    return float(np.dot(w, flags) / w.sum()), flags
