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
    def __init__(self, spans, issue_cell, departure, request, member_id=None):
        self.spans = [(int(c), F(a), F(b)) for c, a, b in spans]
        self.issue = (int(issue_cell), F(departure))
        self.request = request
        self.cells = sorted({c for c, _, _ in self.spans} | {self.issue[0]})
        self.budget_peak = float(request["budgets"]["peak"])
        member_id = member_id or next(iter(request["budgets"]["dose"]))
        self.budget_dose = F(request["budgets"]["dose"][member_id])
        self.incurred = F(request["incurred"][member_id])
        self.duration = float(sum(b - a for _, a, b in self.spans))

    def contact(self, births, T, current, R):
        """births {graph cell: second}; current: set of graph cells active on [0, R)."""
        T = float(T)
        for c, a, b in self.spans + [(self.issue[0], self.issue[1], self.issue[1])]:
            if c in current and R > 0 and a < F(float(R)):
                return True
            t = births.get(c)
            if t is not None:
                ext = round_up_sum(t, T)
                if a < F(ext) and b >= F(float(t)):
                    return True
        return False

    def dose_peak(self, births, T, R, kernels, current_flux):
        """(dose kJ/m2 upper bound incl. incurred, peak kW/m2 upper bound) along the journey."""
        T = float(T)
        sources = [(float(t), round_up_sum(t, T), kernels.of_graph_cell(c)) for c, t in births.items()]
        total = float(self.incurred)
        peak = 0.0
        fmax = float(current_flux.max()) + sum(float(k.max()) for _, _, k in sources)
        margin = 1e-8 * max(1.0, fmax)
        R = float(R)
        for c, a, b in self.spans:
            a, b = float(a), float(b)
            f_cur = float(current_flux[c])
            if a < R:
                total += f_cur * (min(b, R) - a) / 1000.0
                peak = max(peak, f_cur)
            for t0, t1, k in sources:
                lo, hi = max(a, t0), min(b, t1)
                if hi > lo:
                    total += float(k[c]) * (hi - lo) / 1000.0
                if a < t1 and b >= t0:
                    peak = max(peak, f_cur + float(k[c]))
            total += margin * (b - a) / 1000.0
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
