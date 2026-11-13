"""Bound and gradient guard for L-BFGS-B fits (Iris request, 2026-11-13; rule: TOLERANCE_feature_ablation.md addendum 3).

``guarded(minimize)`` returns a drop-in replacement for scipy.optimize.minimize that runs the fit UNCHANGED and records,
per call, the same checks as cv_part_a._lbfgs (FitFailed) and check_bounds.py:

* gradient/finiteness: the final objective and gradient are finite;
* descent: the final objective is not above the objective at x0 (f <= f0 + 1e-9 * max(1, |f0|));
* all-at-floor: not every parameter sits at the lower bound;
* bound share: if >= 50 % of the parameters sit at the floor, the same objective is re-minimised from x0 = 0.005 and
  x0 = 0.08 (all coordinates); the call FAILS if either restart improves the objective by > 1e-6 relative.

The guard never changes the returned result (the restarts are diagnostics only). ``GuardLog`` collects the records;
a fit FAILS if any of its calls fails (MCEM: any M-step).
"""
from __future__ import annotations

import numpy as np

AT_FLOOR_RTOL = 1e-6
DESCENT_TOL = 1e-9
SHARE_FLAG = 0.5
RESTART_X0 = (0.005, 0.08)
RESTART_REL = 1e-6


class GuardLog:
    def __init__(self):
        self.calls = []

    def reset(self):
        self.calls = []

    def summary(self):
        fails = [c for c in self.calls if c["fail"]]
        return dict(n_calls=len(self.calls), n_fail=len(fails),
                    reasons=sorted({r for c in fails for r in c["reasons"]}),
                    final_share_at_floor=self.calls[-1]["share_at_floor"] if self.calls else None,
                    max_share_at_floor=max((c["share_at_floor"] for c in self.calls), default=None),
                    n_flagged=sum(c["flagged"] for c in self.calls),
                    ok=not fails)


def _value(fun, x, jac):
    out = fun(x)
    return float(out[0]) if jac is True else float(out)


def guarded(minimize, log: GuardLog):
    def wrapped(fun, x0, *args, **kw):
        res = minimize(fun, x0, *args, **kw)
        jac = kw.get("jac")
        bounds = kw.get("bounds")
        floor = bounds[0][0] if bounds else None
        x0 = np.asarray(x0, float)
        f0 = _value(fun, x0, jac)
        f = float(res.fun)
        g = np.asarray(res.jac, float) if getattr(res, "jac", None) is not None else np.array([0.0])
        reasons = []
        if not (np.isfinite(f) and np.all(np.isfinite(g))):
            reasons.append("non-finite f or gradient")
        if np.isfinite(f0) and f > f0 + DESCENT_TOL * max(1.0, abs(f0)):
            reasons.append("f > f0")
        share = 0.0
        flagged = False
        restart = None
        if floor is not None:
            at = res.x <= floor * (1 + AT_FLOOR_RTOL) + 1e-300
            share = float(at.mean())
            if at.all():
                reasons.append("all at floor")
            elif share >= SHARE_FLAG:
                flagged = True
                restart = []
                for v in RESTART_X0:
                    r2 = minimize(fun, np.full_like(x0, v), *args, **kw)
                    restart.append(float(r2.fun))
                    if np.isfinite(r2.fun) and r2.fun < f - RESTART_REL * max(1.0, abs(f)):
                        reasons.append(f"restart x0={v} improves")
        log.calls.append(dict(f0=f0, f=f, share_at_floor=share, flagged=flagged, restart_f=restart,
                              reasons=reasons, fail=bool(reasons)))
        return res
    return wrapped
