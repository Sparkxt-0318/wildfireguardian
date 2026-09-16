#!/usr/bin/env python
"""Tests for instruments 2 and 2b, the recoverability harness.

    python -m pytest research/roads/tests/test_recoverability.py
    python research/roads/tests/test_recoverability.py

**Every fixture is synthetic and generated in-process from a declared seed.** No
Korean data is read. No number here is a measurement and none may be quoted. The
real geometry and the real `sigma_u` arrive with WJ-009.

What these tests protect is the part of the design condition C4 is about: that an
instrument carries the name of the geometry it ran on, that the R-set and the
candidate set give different answers, and that the fast backend can never be
mistaken for the pre-registered one.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import recoverability as rc  # noqa: E402


def _sets(seed=20260916, n=500):
    rng = np.random.default_rng(seed)
    cand = rc._synthetic_geometry(rng, n, name="candidate", theta_low=5.0)
    keep = cand.theta_deg >= 20.0
    rset = rc.Geometry("rset", cand.w_cleared_m[keep], cand.theta_deg[keep],
                       cand.fire_id[keep], cand.sigma_u_m)
    return cand, rset


# ------------------------------------------------------- the covariate algebra

def test_w_eff_and_v_follow_the_preregistration():
    w = np.array([3.0, 6.0])
    th = np.array([90.0, 90.0])
    assert np.allclose(rc.w_eff(w, th), w)                  # sin(90) = 1
    assert np.allclose(rc.v_of(w, th), np.log(w + 1.0))
    # The 15 degree clip binds below 15 degrees and nowhere above it.
    assert rc.w_eff(np.array([3.0]), np.array([5.0]))[0] == \
           rc.w_eff(np.array([3.0]), np.array([15.0]))[0]
    assert rc.w_eff(np.array([3.0]), np.array([30.0]))[0] < \
           rc.w_eff(np.array([3.0]), np.array([15.0]))[0]


def test_contrast_sign_convention_matches_F1():
    """`H-ROADS` predicts a lower probability at 6 m, which needs a negative slope."""
    b = rc.beta_for_contrast(0.03, 0.0, 50.0)
    assert b < 0
    assert abs(rc.contrast_probability(0.0, b, 50.0) - 0.03) < 1e-8
    assert rc.contrast_probability(0.0, 0.0, 50.0) == 0.0


def test_unreachable_contrast_raises_instead_of_clipping():
    try:
        rc.beta_for_contrast(0.45, 0.0, 50.0)
        assert False, "an unreachable contrast must raise"
    except ValueError as exc:
        assert "unreachable" in str(exc)


# --------------------------------------------------------- condition C4 itself

def test_geometry_must_declare_which_set_it_is():
    try:
        rc.Geometry("the real one", [3.0], [40.0], [0], 0.5)
        assert False, "an undeclared geometry name must be refused"
    except ValueError:
        pass
    for name in rc.GEOMETRIES:
        rc.Geometry(name, [3.0], [40.0], [0], 0.5)


def test_the_two_geometries_give_different_kappa_v():
    cand, rset = _sets()
    assert len(rset) < len(cand)
    # Mechanism 1 of section 5.1.4: truncating grazing angles lowers Var(v_true).
    assert rset.var_v_true() < cand.var_v_true()
    # Mechanism 2 pulls the other way: it removes the worst-measured segments.
    assert rset.mean_sigma_v_sq() <= cand.mean_sigma_v_sq()
    # So the net sign is arithmetic, which is the whole point of reporting both.
    assert rset.kappa_v() != cand.kappa_v()


def test_every_result_records_its_geometry_and_backend():
    _, rset = _sets(n=150)
    r = rc.run(rset, "detection_power", n_draws=40, seed=4)
    kp = r.as_keypaths()
    assert kp["recoverability.geometry"] == "rset"
    assert kp["recoverability.backend"] == "laplace"
    assert "recoverability.detection_power.rset.value" in kp
    assert "recoverability.detection_power.rset.mc_standard_error" in kp


def test_candidate_set_overstates_the_r_set():
    """A6's finding, demonstrated on synthetic geometry rather than argued.

    This is the defect condition C4 exists to close: a power figure computed on
    the candidate set is a figure for a fit that will not be run.
    """
    cand, rset = _sets(n=600)
    d_cand = rc.run(cand, "detection_power", n_draws=60, seed=8)
    d_rset = rc.run(rset, "detection_power", n_draws=60, seed=8)
    assert d_cand.value > d_rset.value
    assert d_cand.geometry != d_rset.geometry


# ------------------------------------------------------------ the two arms

def test_detection_and_exclusion_are_different_instruments():
    _, rset = _sets(n=300)
    d = rc.run(rset, "detection_power", n_draws=40, seed=6)
    x = rc.run(rset, "exclusion_power", n_draws=40, seed=6)
    assert d.threshold == rc.GATE_R0 and x.threshold == rc.GATE_M2
    assert d.instrument != x.instrument
    # They address different key paths, so neither can be quoted as the other.
    assert set(d.as_keypaths()) != set(x.as_keypaths())


def test_power_does_not_fall_with_a_larger_sample():
    rng = np.random.default_rng(31)
    small = rc._synthetic_geometry(rng, 120)
    big = rc._synthetic_geometry(rng, 900)
    a = rc.run(small, "detection_power", n_draws=60, seed=12)
    b = rc.run(big, "detection_power", n_draws=60, seed=12)
    assert b.value >= a.value


# ------------------------------------------------------------ the backend rule

def test_the_preregistered_backend_cannot_be_faked():
    _, rset = _sets(n=80)
    try:
        rc.run(rset, "detection_power", backend="nuts", n_draws=1)
        assert False, "the nuts backend must not be silently substituted"
    except NotImplementedError as exc:
        assert "WJ-009" in str(exc) or "WJ-001" in str(exc)


def test_a_fast_number_is_never_gate_readable():
    _, rset = _sets(n=80)
    for inst in ("detection_power", "exclusion_power"):
        r = rc.run(rset, inst, n_draws=20, seed=2)
        assert r.backend == "laplace"
        assert r.gate_readable is False
        assert "diagnostic" in r.notes


def test_unknown_instrument_and_backend_are_refused():
    _, rset = _sets(n=40)
    for kwargs in (dict(instrument="power"), dict(instrument="detection_power",
                                                  backend="stan")):
        try:
            rc.run(rset, n_draws=1, **kwargs)
            assert False, "an unknown %r must be refused" % kwargs
        except ValueError:
            pass


def test_sigma_u_must_come_from_instrument_one():
    try:
        rc.Geometry("rset", [3.0], [40.0], [0], 0.0)
        assert False, "a zero measurement error must be refused"
    except ValueError:
        pass


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
