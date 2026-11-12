"""Synthetic tests for src/viewshed.py (run: python3 -I src/test_viewshed.py).
Credit context: camera positions in the real analysis come from HPWREN (hpwren.ucsd.edu), UC San Diego.

1. Flat plane z=0, camera at 100 m, a 50 m flat-topped east-west ridge at y in [4950, 5050] m.
   Without curvature (k=1) the analytic shadow is 5050 < y < 10100 m (target angle -100/y must
   be >= ridge-top angle -50/5050). Targets in front of the ridge and beyond the shadow are visible.
2. Same terrain with curvature + refraction k=0.13: polar result must agree with a dense
   brute-force line check on random targets (>= 99 %).
3. Pure curvature: flat sphere, camera at 10 m, targets at 0 m. Ground-level horizon distance is
   sqrt(2 R h / (1 - k)) ~ 12.1 km; targets well beyond it must be hidden, well inside visible.
"""
import sys, pathlib
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from viewshed import polar_visibility, brute_los, R_EARTH


def ridge(x, y):
    return np.where((np.abs(np.asarray(y) - 5000) <= 50) & (np.abs(np.asarray(x)) < 20000), 50.0, 0.0)


def test_ridge_no_curvature():
    ys = np.arange(1000, 20000, 250.0)
    xs = np.zeros_like(ys) + 1.0
    vis, _ = polar_visibility(ridge, 100.0, xs, ys, ridge(xs, ys), dr=10.0, k=1.0)
    v = vis[0.0]
    expected = ~((ys > 5050) & (ys < 10100))
    # allow disagreement only within one 10 m sample of the analytic edges
    bad = (v != expected) & (np.abs(ys - 10100) > 60) & (np.abs(ys - 5050) > 60)
    assert not bad.any(), list(zip(ys[bad], v[bad], expected[bad]))
    print("test 1 ridge (no curvature): OK, shadow 5050-10100 m reproduced")


def test_ridge_vs_brute():
    rng = np.random.default_rng(0)
    xs = rng.uniform(-8000, 8000, 400)
    ys = rng.uniform(500, 25000, 400)
    zt = ridge(xs, ys)
    vis, _ = polar_visibility(ridge, 100.0, xs, ys, zt, dr=10.0, arc_m=5.0)
    ref = np.array([brute_los(ridge, 100.0, x, y, z, step=5.0) for x, y, z in zip(xs, ys, zt)])
    agree = (vis[0.0] == ref).mean()
    assert agree >= 0.99, agree
    print(f"test 2 ridge+curvature vs brute force: agreement {agree:.4f} on 400 random targets")


def test_curvature_horizon():
    flat = lambda x, y: np.zeros(np.shape(x))
    h, k = 10.0, 0.13
    dh = np.sqrt(2 * R_EARTH * h / (1 - k))
    ys = np.array([0.5, 0.8, 0.95, 1.05, 1.2, 2.0]) * dh
    vis, _ = polar_visibility(flat, h, np.zeros_like(ys) + 1, ys, np.zeros_like(ys), dr=20.0)
    exp = ys < dh
    assert (vis[0.0] == exp).all(), (vis[0.0], exp)
    print(f"test 3 curvature horizon {dh/1000:.2f} km: OK")


if __name__ == "__main__":
    test_ridge_no_curvature()
    test_ridge_vs_brute()
    test_curvature_horizon()
    print("all viewshed tests passed")
