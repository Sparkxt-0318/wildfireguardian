"""Tests for fitguard (bound and gradient guard)."""
import numpy as np
import scipy.optimize as so

import fitguard as G


def _q(c):
    return lambda x: (float(np.sum((x - c) ** 2)), 2 * (x - c))


def _run(fun, x0, floor=1e-9):
    log = G.GuardLog()
    m = G.guarded(so.minimize, log)
    res = m(fun, x0, jac=True, method="L-BFGS-B", bounds=[(floor, None)] * len(x0))
    return res, log.summary()


def test_interior_fit_passes_and_result_unchanged():
    x0 = np.full(4, 0.02)
    res, s = _run(_q(np.array([0.1, 0.2, 0.3, 0.4])), x0)
    ref = so.minimize(_q(np.array([0.1, 0.2, 0.3, 0.4])), x0, jac=True, method="L-BFGS-B", bounds=[(1e-9, None)] * 4)
    assert s["ok"] and s["n_calls"] == 1 and np.array_equal(res.x, ref.x)


def test_all_at_floor_fails():
    res, s = _run(_q(np.full(3, -1.0)), np.full(3, 0.02))
    assert not s["ok"] and "all at floor" in s["reasons"]


def test_valid_boundary_mle_flagged_but_passes():
    # 3 of 4 at the floor is a genuine constrained optimum: restarts cannot improve it
    res, s = _run(_q(np.array([-1.0, -1.0, -1.0, 0.5])), np.full(4, 0.02))
    assert s["ok"] and s["n_flagged"] == 1


def test_nonfinite_gradient_fails():
    def f(x):
        return float(np.sum(x ** 2)), np.full_like(x, np.nan)
    res, s = _run(f, np.full(2, 0.5))
    assert not s["ok"] and "non-finite f or gradient" in s["reasons"]
