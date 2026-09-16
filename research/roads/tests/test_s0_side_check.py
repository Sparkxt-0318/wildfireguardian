#!/usr/bin/env python
"""Tests for check S0, the pre-labelling side-resolvability check.

    python -m pytest research/roads/tests/test_s0_side_check.py
    python research/roads/tests/test_s0_side_check.py      # no pytest needed

**Every fixture here is synthetic and is generated in-process from a declared
seed.** No Korean data is read, no scene is opened, no label is computed, and no
number produced by this file may be quoted anywhere. The Korean detection record
is behind WJ-001 and has never been downloaded.

These tests exist because condition C2 of `research/eval/signoffs/roads_v0.2.md`
is an arithmetic claim about a sampling distribution, and an arithmetic claim
that nothing re-runs is a claim that decays.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import s0_side_check as s0  # noqa: E402


# --------------------------------------------------------------- the cutoff

def test_statistic_is_t_not_normal():
    """The residual df is `n_det - 3`, so the reference is t on `n_det - 3`."""
    for n in (5, 6, 8, 12, 25, 40):
        assert s0.t_crit(n, 0.01) == pytest_approx(stats.t.isf(0.01, n - 3))
    # And the t cutoff is strictly above the normal one at every finite df.
    for n in (5, 6, 8, 12, 25, 40):
        assert s0.t_crit(n, 0.01) > stats.norm.isf(0.01)


def test_fixed_two_point_zero_reproduces_the_signoff_table():
    """A6's table of what the v0.2 cutoff actually delivered, per tail."""
    want = {5: 0.0918, 6: 0.0697, 8: 0.0510, 12: 0.0383, 25: 0.0290, 40: 0.0264}
    for n, nu, p, z in s0.table_null_rate_at_2():
        assert nu == n - 3
        assert abs(p - want[n]) < 5e-5
        assert abs(z - 0.0228) < 5e-5
    # No value on v0.2's z grid repairs the bottom of the range.
    assert stats.t.sf(2.5, 2) > 0.06
    assert stats.t.sf(1.5, 2) > 0.13


def test_fails_closed_without_residual_degrees_of_freedom():
    assert s0.t_crit(3) == math.inf
    assert s0.t_crit(2) == math.inf
    bad = s0.fit_plane(np.zeros((3, 2)), np.zeros(3), np.zeros(3),
                       np.zeros(2), 1000.0)
    assert bad.ok is False


# --------------------------------------------------- the angle table (5.1.3)

def test_angle_table_matches_the_preregistration():
    tab = s0.table_min_angle()
    assert abs(tab[0.15][0] - 69.1) < 0.1          # n_det = 5, c = 0.15
    assert abs(tab[0.15][3] - 14.1) < 0.1          # n_det = 12
    assert abs(tab[0.30][2] - 45.5) < 0.1          # n_det = 8, c = 0.30
    assert tab[0.20][0] is None                    # unresolvable at any angle
    assert tab[0.50][2] is None


def test_c_max_row():
    for n, want in ((5, 0.161), (6, 0.270), (8, 0.420),
                    (12, 0.614), (25, 0.997), (40, 1.301)):
        assert abs(s0.c_max(n) - want) < 1e-3


def test_correction_is_strictly_costly_in_sample():
    """The fix removes segments. It is not allowed to look free."""
    for n in (5, 6, 8, 12, 25):
        assert (s0.min_resolvable_sin_theta(n, 0.15, 0.01)
                > 2 * 2.0 * 0.15 / math.sqrt(n))


# --------------------------------------------------- null calibration (C2)

def test_null_assignment_rate_matches_alpha_and_two_point_zero_does_not():
    """The point of condition C2, demonstrated rather than asserted.

    A front running perpendicular to the barrier normal has a zero projected
    gradient, so under the pre-registered rule the two-sided assignment rate
    should sit near `2 * alpha`. Under a fixed 2.0 it does not.
    """
    rng = np.random.default_rng(20260916)
    alpha, n_det, n_sim = 0.01, 5, 4000
    hit_t = hit_z = 0
    for _ in range(n_sim):
        seg = s0._synthetic_segment(rng, n_det, 3, theta_deg=90.0, c=0.20)
        fit = s0.fit_plane(seg["xy"], seg["t_min"], seg["epochs"],
                           seg["x0"], s0.TIER_A["radius_m"])
        T = s0.side_statistic(fit, seg["normal"])
        if np.isfinite(T):
            hit_t += abs(T) >= s0.t_crit(n_det, alpha)
            hit_z += abs(T) >= 2.0
    rate_t, rate_z = hit_t / n_sim, hit_z / n_sim
    assert abs(rate_t - 2 * alpha) < 0.012
    assert rate_z > 0.10
    assert rate_z > 3 * rate_t


def test_wrong_side_probability_collapses_once_a_side_is_real():
    """Section 5.1.5: the bound is attained only where there is nothing to get right."""
    for nu in (2, 9, 22):
        tc = stats.t.isf(0.01, nu)
        assert abs(float(stats.nct.cdf(-tc, nu, 0.0)) - 0.01) < 1e-6
        assert float(stats.nct.cdf(-tc, nu, 1.0)) < 2e-3
        assert float(stats.nct.cdf(-tc, nu, 2.0)) < 2e-4


# ------------------------------------------------- the tiers (5.1.2b, 5.1.2c)

def test_resolved_front_gets_the_right_side():
    rng = np.random.default_rng(11)
    ok = 0
    for _ in range(200):
        seg = s0._synthetic_segment(rng, 40, 5, theta_deg=0.0, c=0.15)
        fa = s0.fit_plane(seg["xy"], seg["t_min"], seg["epochs"],
                          seg["x0"], s0.TIER_A["radius_m"])
        res = s0.assign_side(fa, None, seg["normal"])
        ok += res.assigned and res.windward_sign == -1
    assert ok >= 190


def test_two_epoch_segment_never_reaches_tier_s_a():
    rng = np.random.default_rng(7)
    seg = s0._synthetic_segment(rng, 30, 2, theta_deg=0.0, c=0.15)
    fa = s0.fit_plane(seg["xy"], seg["t_min"], seg["epochs"],
                      seg["x0"], s0.TIER_A["radius_m"])
    assert fa.n_epochs == 2
    res = s0.assign_side(fa, None, seg["normal"])
    assert res.assigned is False
    assert res.reason == "SIDE_2EP"
    assert res.tier == "none"


def test_tier_b_is_only_reached_after_tier_a_fails():
    rng = np.random.default_rng(3)
    a = s0._synthetic_segment(rng, 40, 5, theta_deg=0.0, c=0.15)
    fa = s0.fit_plane(a["xy"], a["t_min"], a["epochs"], a["x0"], 1000.0)
    b = s0._synthetic_segment(rng, 40, 5, theta_deg=0.0, c=0.15, radius=3000.0)
    fb = s0.fit_plane(b["xy"], b["t_min"], b["epochs"], b["x0"], 3000.0)
    assert s0.assign_side(fa, fb, a["normal"]).tier == "S-A"


# ------------------------------------------------------- the reported summary

def test_union_pass_fraction_and_the_quotable_bound():
    res = [s0.SideResult("S-A", True, -1, "", 8.0, 6.9, 2, 5, 3, 0.1)] * 30
    res += [s0.SideResult("none", False, 0, "SIDE", 0.2, 6.9, 2, 5, 3, 0.9)] * 70
    s = s0.summarise(res)
    assert abs(s.pass_fraction_union - 0.30) < 1e-12
    assert abs(s.pass_fraction_by_tier["S_A"] - 0.30) < 1e-12
    # Section 5.1.5: R_obs / R_true >= 1 - alpha_union / q.
    assert abs(s.wrong_side_bound - s0.ALPHA_UNION_BOUND / 0.30) < 1e-12
    assert s.reasons["SIDE"] == 70


def test_tier_b_conditional_pass_fraction_is_conditional():
    res = [s0.SideResult("S-A", True, -1, "", 8.0, 6.9, 2, 5, 3, 0.1)] * 20
    res += [s0.SideResult("S-B", True, +1, "", -8.0, 2.8, 9, 12, 3, 0.2)] * 16
    res += [s0.SideResult("none", False, 0, "SIDE", 0.2, 6.9, 2, 5, 3, 0.9)] * 64
    s = s0.summarise(res)
    assert abs(s.pass_fraction_by_tier["S_B_given_S_A_fail"] - 16 / 80) < 1e-12
    assert abs(s.pass_fraction_union - 0.36) < 1e-12


def test_key_paths_are_the_ones_condition_c2_names():
    res = [s0.SideResult("S-A", True, -1, "", 8.0, 6.9, 2, 5, 3, 0.1)] * 10
    kp = s0.summarise(res).as_keypaths(0.01)
    for want in ("checks.S0.degrees_of_freedom.deciles",
                 "checks.S0.pass_fraction_by_tier",
                 "checks.S0.pass_fraction_union"):
        assert want in kp
    assert set(kp["checks.S0.pass_fraction_by_tier"]) == {"S_A", "S_B_given_S_A_fail"}
    assert kp["meta.side_alpha_union_bound"] == 0.02


def test_module_reads_nothing_from_disk():
    """The provenance firewall of section 6.1, as a test rather than a promise.

    Check S0 is declared to touch no scene and no label. A module that cannot
    open a file cannot open a scene, so this is checked structurally: no raster
    or vector reader is imported, and nothing in the module opens a path.
    """
    import ast
    src = Path(s0.__file__).read_text()
    tree = ast.parse(src)

    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    banned = {"rasterio", "gdal", "osgeo", "geopandas", "fiona", "rioxarray",
              "xarray", "netCDF4", "h5py", "pandas", "requests", "urllib",
              "urllib3", "sqlite3", "json"}
    assert not (imported & banned), "check S0 imports a reader: %s" % (imported & banned)

    openers = {"open", "loadtxt", "genfromtxt", "read_text", "read_bytes",
               "read_csv", "load", "imread"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = fn.id if isinstance(fn, ast.Name) else (
                fn.attr if isinstance(fn, ast.Attribute) else None)
            assert name not in openers, "check S0 opens something: %s" % name


# --------------------------------------------------------------- plumbing

def pytest_approx(v):
    class _A:
        def __eq__(self, other):
            return abs(other - v) < 1e-9
    return _A()


def _run_standalone() -> int:
    fns = [(k, v) for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    bad = 0
    for name, fn in fns:
        try:
            fn()
        except AssertionError as exc:
            print("FAIL %s: %s" % (name, exc))
            bad += 1
        except Exception as exc:              # noqa: BLE001
            print("ERROR %s: %r" % (name, exc))
            bad += 1
    print("%d/%d tests passed" % (len(fns) - bad, len(fns)))
    return bad


if __name__ == "__main__":
    sys.exit(1 if _run_standalone() else 0)
